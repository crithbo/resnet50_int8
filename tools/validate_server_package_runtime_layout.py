#!/usr/bin/env python3
"""Validate install-subtree runtime layout from exact final-ZIP bytes.

The validator is intentionally family-neutral.  It binds the embedded layout
contract, exact runner, manifest, SCA consumers, shared layout helper and a
safe-harness report derived from the same final ZIP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
DEFAULT_CONTRACT_MEMBER = "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"
REQUIRED_PARENTS = ["install"]
PACKAGE_CREATABLE_PARENTS = ["install/cfg_pkg", "install/codex_runs"]
REQUIRED_SCENARIOS = [
    "normal",
    "preflight_fail",
    "compile_fail",
    "HUP",
    "INT",
    "TERM",
]
REPEAT_EXECUTION_CONTRACT = {
    "mode": "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS",
    "cfg_root_policy": "RESET_AND_RECREATE_EXACT_INSTALL_NAME",
    "run_root_policy": "RESET_AND_RECREATE_EXACT_PACKAGE_ATTEMPT",
    "foreign_sibling_policy": "PRESERVE",
    "symlink_or_special_entry_policy": "FAIL_CLOSED",
    "ownership_marker": ".codex_owner.{name}.json",
    "return_name_policy": "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS",
}
RUNTIME_VARIABLE_PREFIXES = {
    "work_root": ("$server_root/install/codex_runs/", "${server_root}/install/codex_runs/"),
    "cfg_root": ("$server_root/install/cfg_pkg/", "${server_root}/install/cfg_pkg/"),
    "run_root": ("$server_root/install/codex_runs/", "${server_root}/install/codex_runs/"),
    "evidence_root": ("$server_root/install/codex_runs/", "${server_root}/install/codex_runs/"),
    "compile_root": ("$server_root/install/codex_runs/", "${server_root}/install/codex_runs/"),
}
HELPER_VARIABLES = {
    "work_root": ("$RUN_ROOT", "${RUN_ROOT}"),
    "cfg_root": ("$CFG_ROOT", "${CFG_ROOT}"),
    "run_root": ("$RUN_ROOT", "${RUN_ROOT}"),
    "evidence_root": ("$EVIDENCE_ROOT", "${EVIDENCE_ROOT}"),
    "compile_root": ("$COMPILE_ROOT", "${COMPILE_ROOT}"),
}
HEREDOC_PATTERN = re.compile(
    r"<<(?P<strip>-?)[ \t]*"
    r"(?P<word>'[^'\r\n]+'|\"[^\"\r\n]+\"|\\?[A-Za-z_][A-Za-z0-9_]*)"
)
SHELL_MEMBER_SUFFIXES = {".sh", ".bash"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: Any, *, allow_template: bool = False) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts:
        return False
    if not allow_template and ("{" in value or "}" in value):
        return False
    return True


def _read_zip(zip_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    members: dict[str, bytes] = {}
    roots: set[str] = set()
    names: set[str] = set()
    try:
        archive = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as error:
        return {"errors": [f"cannot open ZIP: {error}"], "members": {}, "root": None}
    with archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            errors.append(f"CRC failure: {bad_crc}")
        for info in archive.infolist():
            name = info.filename
            pure = PurePosixPath(name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in name
                or not pure.parts
            ):
                errors.append(f"unsafe ZIP path: {name}")
                continue
            if name in names:
                errors.append(f"duplicate ZIP path: {name}")
            names.add(name)
            roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                errors.append(f"symlink ZIP member: {name}")
            if info.is_dir() or stat.S_ISLNK(mode):
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative:
                members[relative] = archive.read(info)
    if len(roots) != 1:
        errors.append(f"ZIP root set must contain exactly one entry: {sorted(roots)}")
    return {
        "errors": sorted(set(errors)),
        "members": members,
        "root": next(iter(roots)) if len(roots) == 1 else None,
    }


def _json_member(
    members: dict[str, bytes], name: Any, errors: list[str], label: str
) -> dict[str, Any]:
    if not _safe_relative(name):
        errors.append(f"{label} member path is unsafe")
        return {}
    data = members.get(name)
    if data is None:
        errors.append(f"{label} member is absent: {name}")
        return {}
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        errors.append(f"{label} JSON is invalid: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return value


def _contract_shape(contract: dict[str, Any], errors: list[str]) -> None:
    required = {
        "schema",
        "package_id",
        "install_name",
        "runner_member",
        "manifest_member",
        "shared_layout_helper",
        "tb_cwd",
        "fixed_result_root",
        "required_preexisting_parents",
        "package_creatable_parent_dirs",
        "runtime_roots",
        "payload_mounts",
        "sca_consumers",
        "runner_bindings",
        "path_budget",
        "repeat_execution",
        "finalizer",
        "claim_boundary",
    }
    missing = sorted(required - set(contract))
    if missing:
        errors.append(f"layout contract fields are missing: {missing}")
    if contract.get("schema") != "server_package_runtime_layout_v1":
        errors.append("layout contract schema mismatch")
    if contract.get("tb_cwd") != "$server_root":
        errors.append("TB cwd must be $server_root")
    if contract.get("fixed_result_root") != FIXED_RESULT_ROOT:
        errors.append("fixed result root mismatch")
    if contract.get("required_preexisting_parents") != REQUIRED_PARENTS:
        errors.append("required pre-existing install parents mismatch")
    if contract.get("package_creatable_parent_dirs") != PACKAGE_CREATABLE_PARENTS:
        errors.append("package-creatable install parents mismatch")
    if contract.get("repeat_execution") != REPEAT_EXECUTION_CONTRACT:
        errors.append("repeat-execution package-owned reset contract mismatch")
    roots = contract.get("runtime_roots")
    if not isinstance(roots, dict):
        errors.append("runtime_roots must be an object")
        roots = {}
    expected_roots = {
        "cfg_root": f"install/cfg_pkg/{contract.get('install_name')}",
        "run_root": f"install/codex_runs/{contract.get('package_id')}/{{attempt}}",
        "evidence_root": (
            f"install/codex_runs/{contract.get('package_id')}/"
            "{attempt}/evidence"
        ),
        "compile_root": (
            f"install/codex_runs/{contract.get('package_id')}/"
            "{attempt}/compile"
        ),
    }
    for key, expected in expected_roots.items():
        if roots.get(key) != expected:
            errors.append(f"runtime root mismatch: {key}")
    finalizer = contract.get("finalizer")
    if not isinstance(finalizer, dict):
        errors.append("finalizer contract must be an object")
    elif finalizer.get("required_scenarios") != REQUIRED_SCENARIOS:
        errors.append("finalizer scenario set/order mismatch")


def _noncomment_lines(text: str) -> list[tuple[int, str]]:
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _marker_line(
    lines: list[tuple[int, str]], marker: Any, errors: list[str], label: str
) -> int:
    if not isinstance(marker, str) or not marker:
        errors.append(f"{label} marker is missing")
        return 10**9
    matches = [number for number, line in lines if marker in line]
    if len(matches) != 1:
        errors.append(f"{label} marker occurrence count is {len(matches)}, expected 1")
        return matches[0] if matches else 10**9
    return matches[0]


def _runner_checks(
    runner: bytes, contract: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    try:
        text = runner.decode("utf-8")
    except UnicodeError as error:
        errors.append(f"runner is not UTF-8: {error}")
        return {}
    lines = _noncomment_lines(text)
    bindings = contract.get("runner_bindings", {})
    finalizer = contract.get("finalizer", {})
    layout_line = _marker_line(
        lines, bindings.get("layout_prepare_marker"), errors, "layout prepare"
    )
    cwd_line = _marker_line(
        lines, bindings.get("tb_cwd_marker"), errors, "TB cwd"
    )
    compile_line = _marker_line(
        lines, bindings.get("compile_marker"), errors, "compile"
    )
    simulation_line = _marker_line(
        lines, bindings.get("simulation_marker"), errors, "simulation"
    )
    arm_line = _marker_line(
        lines, finalizer.get("arm_marker"), errors, "finalizer arm"
    )
    preflight_line = _marker_line(
        lines,
        finalizer.get("first_preflight_marker"),
        errors,
        "first preflight",
    )
    if not arm_line < min(preflight_line, layout_line, compile_line, simulation_line):
        errors.append("shared finalizer is armed after a fallible preflight/action")
    if not layout_line < compile_line < simulation_line:
        errors.append("layout prepare/compile/simulation order is invalid")
    if not cwd_line < simulation_line:
        errors.append("TB cwd is not bound before simulation")

    return_tag_lines = [
        (number, line)
        for number, line in lines
        if line.startswith("return_tag=")
    ]
    return_zip_lines = [
        (number, line)
        for number, line in lines
        if line.startswith("return_zip=")
    ]
    if len(return_tag_lines) != 1:
        errors.append(
            "runner must define exactly one per-execution return_tag"
        )
    elif (
        "%s%N" not in return_tag_lines[0][1]
        or "$$" not in return_tag_lines[0][1]
    ):
        errors.append(
            "runner return_tag must bind nanosecond epoch and process id"
        )
    if len(return_zip_lines) != 1:
        errors.append(
            "runner must define exactly one return_zip assignment"
        )
    elif (
        "${return_tag}" not in return_zip_lines[0][1]
        or "_return.zip" not in return_zip_lines[0][1]
    ):
        errors.append(
            "runner return ZIP is not unique per execution"
        )

    assignment_pattern = re.compile(
        r"^(work_root|cfg_root|run_root|evidence_root|compile_root)=(.*)$"
    )
    assignment_receipts: list[dict[str, Any]] = []
    for number, line in lines:
        match = assignment_pattern.match(line)
        if match is None:
            continue
        name, raw_value = match.groups()
        value = raw_value.strip().strip("\"'")
        allowed = (
            value == ""
            or any(value.startswith(prefix) for prefix in RUNTIME_VARIABLE_PREFIXES[name])
            or value in HELPER_VARIABLES[name]
        )
        assignment_receipts.append(
            {"line": number, "variable": name, "value": value, "allowed": allowed}
        )
        if not allowed:
            errors.append(f"runtime assignment escapes install subtree: {name}")

    cfg_root = contract.get("runtime_roots", {}).get("cfg_root", "")
    plusarg_receipts: list[dict[str, Any]] = []
    for consumer in contract.get("sca_consumers", []):
        if not isinstance(consumer, dict):
            errors.append("SCA consumer must be an object")
            continue
        member = consumer.get("member")
        runtime_path = None
        for mount in contract.get("payload_mounts", []):
            source = mount.get("source_prefix")
            target = mount.get("runtime_prefix")
            if (
                isinstance(member, str)
                and isinstance(source, str)
                and isinstance(target, str)
                and member.startswith(source)
            ):
                runtime_path = target + member[len(source) :]
                break
        plusarg = consumer.get("plusarg")
        if runtime_path is None or not runtime_path.startswith(cfg_root + "/"):
            errors.append(f"SCA config is not projected below cfg_root: {member}")
            continue
        suffix = runtime_path[len(cfg_root) :]
        token = f"+{plusarg}=$cfg_root{suffix}"
        occurrences = sum(token in line for _, line in lines)
        plusarg_receipts.append(
            {
                "plusarg": plusarg,
                "member": member,
                "expected_token": token,
                "occurrences": occurrences,
            }
        )
        if occurrences < 1:
            errors.append(f"runner SCA plusarg does not resolve through cfg_root: {plusarg}")
    return {
        "line_order": {
            "finalizer_arm": arm_line,
            "first_preflight": preflight_line,
            "layout_prepare": layout_line,
            "tb_cwd": cwd_line,
            "compile": compile_line,
            "simulation": simulation_line,
        },
        "runtime_assignments": assignment_receipts,
        "sca_plusargs": plusarg_receipts,
        "repeat_execution": {
            "return_tag_lines": return_tag_lines,
            "return_zip_lines": return_zip_lines,
            "contract": contract.get("repeat_execution"),
        },
    }


def _heredoc_word(raw: str) -> tuple[str, bool]:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        return raw[1:-1], True
    if raw.startswith("\\"):
        return raw[1:], True
    return raw, False


def _heredoc_language(command_prefix: str, delimiter: str) -> str:
    if re.search(
        r"(^|[^A-Za-z0-9_])python(?:[0-9]+(?:\.[0-9]+)*)?"
        r"([^A-Za-z0-9_]|$)",
        command_prefix,
        flags=re.IGNORECASE,
    ):
        return "python"
    if delimiter.upper().startswith(("PY", "PYTHON")):
        return "python"
    return "literal"


def _generated_heredoc_syntax_checks(
    members: dict[str, bytes],
    runner_member: Any,
    errors: list[str],
) -> dict[str, Any]:
    """Compile every executable heredoc from exact final-ZIP shell bytes.

    The safe runner harness already executes shell control flow.  This
    complementary gate compiles each embedded Python body separately so a
    branch-local fallback cannot hide an outer-generator escaping loss.
    Literal/data heredocs are still enumerated and delimiter-closed, but are
    not executed as code.
    """

    rows: list[dict[str, Any]] = []
    members_with_heredocs: set[str] = set()
    candidates = [
        (name, data)
        for name, data in sorted(members.items())
        if name == runner_member or PurePosixPath(name).suffix in SHELL_MEMBER_SUFFIXES
    ]
    for member, data in candidates:
        if b"<<" not in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeError as error:
            errors.append(
                f"generated heredoc shell member is not UTF-8: {member}: {error}"
            )
            continue
        lines = text.splitlines()
        index = 0
        while index < len(lines):
            command = lines[index]
            matches = list(HEREDOC_PATTERN.finditer(command))
            if not matches:
                index += 1
                continue
            next_body = index + 1
            for match in matches:
                raw_word = match.group("word")
                delimiter, quoted = _heredoc_word(raw_word)
                strip_tabs = match.group("strip") == "-"
                end = next_body
                while end < len(lines):
                    candidate = lines[end].lstrip("\t") if strip_tabs else lines[end]
                    if candidate == delimiter:
                        break
                    end += 1
                language = _heredoc_language(
                    command[: match.start()], delimiter
                )
                receipt = {
                    "member": member,
                    "member_sha256": sha256_bytes(data),
                    "command_line": index + 1,
                    "body_start_line": next_body + 1,
                    "body_end_line": end,
                    "delimiter": delimiter,
                    "delimiter_quoted": quoted,
                    "strip_tabs": strip_tabs,
                    "language": language,
                    "syntax_mode": (
                        "python_compile"
                        if language == "python"
                        else "literal_exact_delimiter"
                    ),
                    "body_sha256": None,
                    "syntax_pass": False,
                }
                members_with_heredocs.add(member)
                if end >= len(lines):
                    errors.append(
                        "generated heredoc delimiter is unterminated: "
                        f"{member}:{index + 1}:{delimiter}"
                    )
                    rows.append(receipt)
                    next_body = len(lines)
                    break
                body = "\n".join(lines[next_body:end]) + "\n"
                receipt["body_sha256"] = sha256_bytes(body.encode("utf-8"))
                if language == "python":
                    try:
                        compile(
                            body,
                            f"{member}:heredoc@{index + 1}",
                            "exec",
                            dont_inherit=True,
                        )
                    except SyntaxError as error:
                        receipt["syntax_error"] = {
                            "message": error.msg,
                            "line": error.lineno,
                            "offset": error.offset,
                        }
                        errors.append(
                            "generated heredoc syntax failed: "
                            f"{member}:{index + 1}: python {error.msg} "
                            f"at body line {error.lineno}"
                        )
                    else:
                        receipt["syntax_pass"] = True
                else:
                    receipt["syntax_pass"] = True
                rows.append(receipt)
                next_body = end + 1
            index = max(index + 1, next_body)
    failed = sum(row["syntax_pass"] is not True for row in rows)
    return {
        "members_scanned": len(candidates),
        "members_with_heredocs": sorted(members_with_heredocs),
        "heredoc_count": len(rows),
        "python_compile_count": sum(
            row["syntax_mode"] == "python_compile" for row in rows
        ),
        "literal_delimiter_count": sum(
            row["syntax_mode"] == "literal_exact_delimiter" for row in rows
        ),
        "failed": failed,
        "uncovered": 0,
        "rows": rows,
    }


def _runner_early_exit_visibility_checks(
    runner: bytes,
    runner_member: Any,
    generated_heredocs: dict[str, Any],
    enforce: bool,
    errors: list[str],
) -> dict[str, Any]:
    """Bind nonzero runner exits to an exact-runner stderr diagnostic.

    This is deliberately an opt-in migration gate.  Frozen predecessors may
    keep their byte-equal receipt, while every next-fresh package whose runner
    changes can enable fail-closed enforcement on the exact final-ZIP member.
    A compile stub is not consulted here and therefore cannot substitute for
    visibility in the server-consumed runner.
    """

    findings: list[str] = []
    try:
        text = runner.decode("utf-8")
    except UnicodeError as error:
        findings.append(f"runner visibility scan is not UTF-8: {error}")
        text = ""

    helper_match = re.search(
        r"(?ms)^[ \t]*runner_fail[ \t]*\(\)[ \t]*\{(?P<body>.*?)^[ \t]*\}",
        text,
    )
    helper_body = helper_match.group("body") if helper_match else ""
    helper_requirements = {
        "definition": helper_match is not None,
        "marker": "RUNNER_ERROR" in helper_body,
        "numeric_code": "code=%s" in helper_body,
        "package_identity": "package=%s" in helper_body,
        "descriptive_message": "message=%s" in helper_body,
        "stderr": ">&2" in helper_body,
        "nonzero_exit": re.search(
            r"\bexit[ \t]+[\"']?\$[A-Za-z_][A-Za-z0-9_]*[\"']?",
            helper_body,
        )
        is not None,
    }
    missing_helper = sorted(
        key for key, value in helper_requirements.items() if not value
    )
    if missing_helper:
        findings.append(
            "runner_fail stderr contract is incomplete: "
            + ",".join(missing_helper)
        )

    final_status_requirements = {
        "marker": "RUNNER_FINAL_STATUS" in text,
        "package_identity": re.search(
            r"RUNNER_FINAL_STATUS[^\r\n]*package=%s", text
        )
        is not None,
        "exit_code": re.search(
            r"RUNNER_FINAL_STATUS[^\r\n]*exit=%s", text
        )
        is not None,
        "stderr": any(
            "RUNNER_FINAL_STATUS" in line and ">&2" in line
            for line in text.splitlines()
        ),
    }
    missing_final = sorted(
        key for key, value in final_status_requirements.items() if not value
    )
    if missing_final:
        findings.append(
            "runner final-status stderr contract is incomplete: "
            + ",".join(missing_final)
        )

    call_rows: list[dict[str, Any]] = []
    malformed_calls: list[dict[str, Any]] = []
    call_pattern = re.compile(
        r"\brunner_fail[ \t]+(?P<code>[^ \t;]+)[ \t]+"
        r"(?P<quote>['\"])(?P<message>.*?)(?P=quote)"
    )
    for line_number, line in enumerate(text.splitlines(), start=1):
        if "runner_fail" not in line or re.search(
            r"runner_fail[ \t]*\(\)", line
        ):
            continue
        matches = list(call_pattern.finditer(line))
        if not matches:
            malformed_calls.append(
                {"line": line_number, "text": line.strip()}
            )
            continue
        for match in matches:
            code = match.group("code")
            message = match.group("message").strip()
            code_bound = bool(
                re.fullmatch(r"[1-9][0-9]*", code)
                or re.fullmatch(
                    r"[\"']?\$\{?[A-Za-z_][A-Za-z0-9_]*\}?[\"']?",
                    code,
                )
            )
            message_bound = len(message) >= 8
            row = {
                "line": line_number,
                "code": code,
                "message": message,
                "code_bound": code_bound,
                "descriptive_gate_or_recovery_hint": message_bound,
            }
            call_rows.append(row)
            if not code_bound or not message_bound:
                malformed_calls.append(row)
    if malformed_calls:
        findings.append(
            "runner_fail invocation lacks numeric/variable code or "
            "descriptive gate/recovery hint"
        )
    if not call_rows:
        findings.append("runner has no package-owned runner_fail call sites")

    heredoc_lines: set[int] = set()
    for row in generated_heredocs.get("rows", []):
        if row.get("member") != runner_member:
            continue
        start = row.get("body_start_line")
        end = row.get("body_end_line")
        if isinstance(start, int) and isinstance(end, int):
            heredoc_lines.update(range(start, end + 1))

    bare_exit_rows: list[dict[str, Any]] = []
    bare_exit_pattern = re.compile(
        r"(?<![A-Za-z0-9_])exit[ \t]+(?P<code>[1-9][0-9]*)"
        r"(?=[ \t;#]|$)"
    )
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if (
            line_number in heredoc_lines
            or not stripped
            or stripped.startswith("#")
            or stripped.startswith("trap ")
        ):
            continue
        for match in bare_exit_pattern.finditer(line):
            bare_exit_rows.append(
                {
                    "line": line_number,
                    "code": int(match.group("code")),
                    "text": stripped,
                }
            )
    if bare_exit_rows:
        findings.append(
            "silent package-owned nonzero exit is present in exact runner"
        )

    if enforce:
        errors.extend(findings)
        disposition = "blocking_applicable"
    else:
        disposition = "receipt_reuse"
    return {
        "enforced": enforce,
        "applicable": enforce,
        "disposition": disposition,
        "pass": not findings if enforce else True,
        "shadow_pass": not findings,
        "runner_member": runner_member,
        "runner_member_sha256": sha256_bytes(runner),
        "helper_contract": helper_requirements,
        "final_status_contract": final_status_requirements,
        "call_count": len(call_rows),
        "calls": call_rows,
        "malformed_calls": malformed_calls,
        "bare_nonzero_exit_count": len(bare_exit_rows),
        "bare_nonzero_exits": bare_exit_rows,
        "findings": findings,
        "uncovered": 0,
        "safe_compile_stub_is_authoritative": False,
    }


def _walk_paths(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "path" and isinstance(child, str):
                yield child
            else:
                yield from _walk_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_paths(child)


def _projected_payload_paths(
    members: dict[str, bytes], contract: dict[str, Any], errors: list[str]
) -> set[str]:
    projected: set[str] = set()
    for mount in contract.get("payload_mounts", []):
        if not isinstance(mount, dict):
            errors.append("payload mount must be an object")
            continue
        source = mount.get("source_prefix")
        target = mount.get("runtime_prefix")
        if (
            not isinstance(source, str)
            or not source.endswith("/")
            or not _safe_relative(source[:-1])
            or not isinstance(target, str)
            or not target.startswith("install/cfg_pkg/")
            or not target.endswith("/")
        ):
            errors.append("payload mount prefix is invalid")
            continue
        matched = False
        for member in members:
            if member.startswith(source):
                matched = True
                projected.add(target + member[len(source) :])
        if not matched:
            errors.append(f"payload mount source prefix has no members: {source}")
    return projected


def _sca_checks(
    members: dict[str, bytes],
    contract: dict[str, Any],
    projected: set[str],
    errors: list[str],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    all_read_paths: list[str] = []
    for consumer in contract.get("sca_consumers", []):
        if not isinstance(consumer, dict):
            continue
        member = consumer.get("member")
        document = _json_member(members, member, errors, "SCA consumer")
        paths = sorted(set(_walk_paths(document)))
        mode = consumer.get("mode")
        if mode == "read_inputs":
            for path in paths:
                if not _safe_relative(path):
                    errors.append(f"SCA input path is unsafe: {path}")
                elif not path.startswith("install/cfg_pkg/"):
                    errors.append(f"SCA input path has wrong prefix: {path}")
                elif path not in projected:
                    errors.append(f"SCA input path has no projected payload: {path}")
            all_read_paths.extend(paths)
        elif mode == "write_outputs":
            for path in paths:
                if not _safe_relative(path, allow_template=True):
                    errors.append(f"SCA output path is unsafe: {path}")
                elif not path.startswith("install/codex_runs/"):
                    errors.append(f"SCA output path has wrong prefix: {path}")
        else:
            errors.append(f"unknown SCA consumer mode: {mode}")
        rows.append(
            {
                "plusarg": consumer.get("plusarg"),
                "member": member,
                "mode": mode,
                "path_count": len(paths),
                "paths": paths,
            }
        )
    return {
        "consumers": rows,
        "read_path_count": len(all_read_paths),
        "read_paths_unique": len(all_read_paths) == len(set(all_read_paths)),
    }


def _path_budget(
    members: dict[str, bytes],
    manifest: dict[str, Any],
    contract: dict[str, Any],
    projected: set[str],
    errors: list[str],
) -> dict[str, Any]:
    budget = contract.get("path_budget", {})
    manifest_budget = manifest.get("path_length_budget")
    if not isinstance(manifest_budget, dict):
        errors.append("manifest path_length_budget is missing")
        manifest_budget = {}
    attempt_max = budget.get("attempt_max_chars")
    root_max = budget.get("declared_target_root_max_chars")
    limit = budget.get("absolute_path_limit_chars")
    if not isinstance(attempt_max, int) or not 1 <= attempt_max <= 48:
        errors.append("attempt_max_chars is invalid")
        attempt_max = 1
    if not isinstance(root_max, int) or root_max < 1:
        errors.append("declared_target_root_max_chars is invalid")
        root_max = 1
    if not isinstance(limit, int) or limit < 1:
        errors.append("absolute_path_limit_chars is invalid")
        limit = 1
    attempt = "a" * attempt_max
    candidates = set(projected)
    roots = contract.get("runtime_roots", {})
    for value in roots.values() if isinstance(roots, dict) else []:
        if isinstance(value, str):
            candidates.add(value.replace("{attempt}", attempt))
    for value in budget.get("additional_projected_paths", []):
        if isinstance(value, str):
            candidates.add(value.replace("{attempt}", attempt))
    if not candidates:
        errors.append("no projected runtime paths were computed")
        candidates.add("install")
    outside = sorted(path for path in candidates if not path.startswith("install/"))
    if outside:
        errors.append(f"projected package-owned path escapes install: {outside}")
    longest = max(candidates, key=lambda item: (len(item), item))
    longest_len = len(longest)
    projected_absolute = root_max + 1 + longest_len
    expected_manifest = {
        "declared_target_root_max_chars": root_max,
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": longest_len,
        "max_projected_absolute_path_chars": projected_absolute,
        "absolute_path_limit_chars": limit,
    }
    for key, expected in expected_manifest.items():
        if manifest_budget.get(key) != expected:
            errors.append(
                f"manifest path budget mismatch: {key}; "
                f"declared={manifest_budget.get(key)!r}; computed={expected!r}"
            )
    if budget.get("max_projected_absolute_path_chars") != projected_absolute:
        errors.append("contract max projected absolute path is not exact")
    if projected_absolute > limit:
        errors.append(
            f"projected absolute path exceeds limit: {projected_absolute} > {limit}"
        )
    return {
        "candidate_count": len(candidates),
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": longest_len,
        "declared_target_root_max_chars": root_max,
        "max_projected_absolute_path_chars": projected_absolute,
        "absolute_path_limit_chars": limit,
    }


def _harness_checks(
    harness: dict[str, Any],
    zip_sha: str,
    contract: dict[str, Any],
    runner_sha: str,
    errors: list[str],
) -> dict[str, Any]:
    if harness.get("schema") != "server_package_runtime_layout_harness_v1":
        errors.append("harness report schema mismatch")
    if harness.get("derived_from_zip_sha256") != zip_sha:
        errors.append("harness report is not bound to exact final ZIP")
    if harness.get("runner_member_sha256") != runner_sha:
        errors.append("harness report is not bound to exact runner bytes")
    if harness.get("fixed_result_root") != FIXED_RESULT_ROOT:
        errors.append("harness fixed result root mismatch")
    scenarios = harness.get("scenarios")
    if not isinstance(scenarios, dict):
        errors.append("harness scenarios are missing")
        scenarios = {}
    receipts: dict[str, Any] = {}
    return_pattern = re.compile(
        re.escape(
            f"{FIXED_RESULT_ROOT}/{contract.get('package_id')}_r"
        )
        + r"[0-9]{19,}_[0-9]+_return\.zip$"
    )
    for name in REQUIRED_SCENARIOS:
        row = scenarios.get(name)
        if not isinstance(row, dict):
            errors.append(f"harness scenario is missing: {name}")
            continue
        required_true = [
            "finalizer_reached",
            "fixed_result_return_published",
            "root_exact_set_unchanged",
            "preexisting_parents_verified",
            "preexisting_install_verified",
            "creatable_parents_initially_absent",
            "creatable_parents_real_after",
        ]
        if name != "normal":
            required_true.append("partial_return_published")
        for key in required_true:
            if row.get(key) is not True:
                errors.append(f"harness {name} did not prove {key}")
        if not isinstance(row.get("command"), str) or not row["command"]:
            errors.append(f"harness {name} command is missing")
        if not isinstance(row.get("cwd"), str) or not row["cwd"]:
            errors.append(f"harness {name} cwd is missing")
        observed_return_zip = row.get("return_zip")
        if (
            not isinstance(observed_return_zip, str)
            or return_pattern.fullmatch(observed_return_zip) is None
        ):
            errors.append(f"harness {name} return ZIP path mismatch")
        if row.get("return_sidecar") != f"{observed_return_zip}.sha256":
            errors.append(f"harness {name} return sidecar path mismatch")
        if row.get("writes_outside_install") is not False:
            errors.append(f"harness {name} wrote package state outside install")
        if row.get("unknown_items_deleted_or_overwritten") is not False:
            errors.append(
                f"harness {name} deleted or overwrote an unknown install item"
            )
        if row.get("root_direct_entries_before") != row.get(
            "root_direct_entries_after"
        ):
            errors.append(f"harness {name} root exact-set receipt diverged")
        if name == "normal":
            if row.get("compile_started") is not True:
                errors.append("normal harness did not reach compile")
            if row.get("simulation_started") is not True:
                errors.append("normal harness did not reach simulation")
        if name == "preflight_fail":
            if row.get("compile_started") is not False:
                errors.append("preflight-fail harness reached compile")
        if name == "compile_fail":
            if row.get("compile_started") is not True:
                errors.append("compile-fail harness did not reach compile")
            if row.get("simulation_started") is not False:
                errors.append("compile-fail harness reached simulation")
        receipts[name] = row
    return {
        "report_sha256": harness.get("_report_sha256"),
        "scenario_count": len(receipts),
        "required_scenarios": contract.get("finalizer", {}).get(
            "required_scenarios"
        ),
    }


def validate(
    zip_path: Path,
    harness_path: Path,
    helper_reference: Path = DEFAULT_HELPER,
    contract_member: str = DEFAULT_CONTRACT_MEMBER,
    require_runner_visibility: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    snapshot = _read_zip(zip_path)
    errors.extend(snapshot["errors"])
    members = snapshot["members"]
    contract = _json_member(members, contract_member, errors, "layout contract")
    _contract_shape(contract, errors)
    runner_member = contract.get("runner_member")
    manifest_member = contract.get("manifest_member")
    runner = members.get(runner_member)
    if runner is None:
        errors.append(f"runner member is absent: {runner_member}")
        runner = b""
    manifest = _json_member(members, manifest_member, errors, "package manifest")

    helper_binding = contract.get("shared_layout_helper")
    if not isinstance(helper_binding, dict):
        errors.append("shared layout helper binding is missing")
        helper_binding = {}
    helper_member = helper_binding.get("member")
    helper_bytes = members.get(helper_member)
    if helper_bytes is None:
        errors.append(f"shared layout helper member is absent: {helper_member}")
        helper_bytes = b""
    helper_sha = sha256_bytes(helper_bytes)
    if helper_binding.get("sha256") != helper_sha:
        errors.append("embedded shared layout helper SHA mismatch")
    if not helper_reference.is_file():
        errors.append("shared layout helper reference is absent")
        reference_sha = None
    else:
        reference_sha = sha256_file(helper_reference)
        if reference_sha != helper_sha:
            errors.append("embedded helper differs from current shared helper")

    runner_receipt = _runner_checks(runner, contract, errors)
    heredoc_receipt = _generated_heredoc_syntax_checks(
        members, runner_member, errors
    )
    visibility_receipt = _runner_early_exit_visibility_checks(
        runner,
        runner_member,
        heredoc_receipt,
        require_runner_visibility,
        errors,
    )
    projected = _projected_payload_paths(members, contract, errors)
    sca_receipt = _sca_checks(members, contract, projected, errors)
    path_receipt = _path_budget(
        members, manifest, contract, projected, errors
    )
    try:
        harness = json.loads(harness_path.read_text(encoding="utf-8"))
        if not isinstance(harness, dict):
            raise ValueError("root must be an object")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        errors.append(f"cannot read harness report: {error}")
        harness = {}
    harness["_report_sha256"] = (
        sha256_file(harness_path) if harness_path.is_file() else None
    )
    zip_sha = sha256_file(zip_path)
    harness_receipt = _harness_checks(
        harness, zip_sha, contract, sha256_bytes(runner), errors
    )
    errors = sorted(set(errors))
    checks = {
        "exact_zip_core": not snapshot["errors"],
        "contract_shape": not any(
            "contract" in error or "runtime root mismatch" in error
            for error in errors
        ),
        "path_budget_exact": not any(
            "path budget" in error
            or "projected absolute path" in error
            for error in errors
        ),
        "sca_tb_cwd_open_paths": not any(
            "SCA " in error or "TB cwd" in error for error in errors
        ),
        "install_subtree_only": not any(
            "install subtree" in error
            or "escapes install" in error
            or "outside install" in error
            for error in errors
        ),
        "install_parent_creation_safety": not any(
            "install parents mismatch" in error
            or "unknown install item" in error
            for error in errors
        ),
        "repeat_execution_safe_reset": not any(
            "repeat-execution" in error
            or "return_tag" in error
            or "unique per execution" in error
            for error in errors
        ),
        "finalizer_early_arm_and_scenarios": not any(
            "finalizer" in error or "harness" in error for error in errors
        ),
        "generated_heredoc_syntax": not any(
            "generated heredoc" in error for error in errors
        ),
        "runner_early_exit_visibility": visibility_receipt["pass"],
        "shared_helper_exact": not any(
            "helper" in error for error in errors
        ),
    }
    return {
        "schema": "server_package_runtime_layout_validation_v1",
        "pass": not errors,
        "errors": errors,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size if zip_path.is_file() else None,
            "sha256": zip_sha if zip_path.is_file() else None,
            "single_root": snapshot["root"],
        },
        "contract": {
            "member": contract_member,
            "sha256": (
                sha256_bytes(members[contract_member])
                if contract_member in members
                else None
            ),
            "package_id": contract.get("package_id"),
            "install_name": contract.get("install_name"),
        },
        "shared_helper": {
            "member": helper_member,
            "embedded_sha256": helper_sha,
            "reference_path": str(helper_reference),
            "reference_sha256": reference_sha,
        },
        "checks": checks,
        "runner": runner_receipt,
        "generated_heredocs": heredoc_receipt,
        "runner_early_exit_visibility": visibility_receipt,
        "sca": sca_receipt,
        "path_budget": path_receipt,
        "harness": harness_receipt,
        "claim_boundary": (
            "Exact final-ZIP package runtime layout, path-budget arithmetic, "
            "SCA/TB-cwd open-path projection, pre-existing real install "
            "directory, safely package-created install parents, exact "
            "same-package cfg/attempt reset, unique per-execution return names, "
            "NDP-root direct-entry preservation, exact generated-heredoc syntax and "
            "exact-runner nonzero-exit stderr visibility (when explicitly "
            "enabled for a next-fresh runner changed-surface), and signal-safe "
            "fixed-result publication only. No config/numeric, "
            "production compile, simulation, natural "
            "terminal, formal-D, E4 or E5 claim."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate install-subtree runtime layout from exact final ZIP."
    )
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--harness-report", required=True, type=Path)
    parser.add_argument(
        "--helper-reference", type=Path, default=DEFAULT_HELPER
    )
    parser.add_argument(
        "--contract-member", default=DEFAULT_CONTRACT_MEMBER
    )
    parser.add_argument(
        "--require-runner-error-visibility",
        action="store_true",
        help=(
            "Fail closed unless the exact final-ZIP runner binds every "
            "package-owned early failure to RUNNER_ERROR and final status."
        ),
    )
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate(
        args.zip.resolve(),
        args.harness_report.resolve(),
        args.helper_reference.resolve(),
        args.contract_member,
        args.require_runner_error_visibility,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "errors": len(report["errors"]),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
