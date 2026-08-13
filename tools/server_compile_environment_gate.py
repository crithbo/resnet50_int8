#!/usr/bin/env python3
"""Provider-aware compile preflight and compile-failure return audit.

This helper deliberately distinguishes an argv path from a proven module
provider.  A missing ``-y``/``+incdir`` path is recorded, but it is blocking
only after the complete provider set or an exact production provider probe
shows that a required module cannot be resolved.  The helper never launches a
DUT compile or simulation.  Its optional probe launches only the explicitly
bound, package-owned module-lookup probe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


REQUEST_SCHEMA = "server-compile-provider-closure-request-v1"
RECEIPT_SCHEMA = "server-compile-provider-closure-receipt-v1"
PROBE_RECEIPT_SCHEMA = "server-compile-provider-probe-receipt-v1"
CORE_REQUEST_SCHEMA = "server-compile-failure-core-audit-request-v1"
CORE_RECEIPT_SCHEMA = "server-compile-failure-core-audit-receipt-v1"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json_sha(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return _sha256_bytes(payload.encode("utf-8"))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError(f"JSON pointer must start with '/': {pointer!r}")
    current = value
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    return current


def _path_bound_in_argv(argv: list[str], candidate: dict[str, Any]) -> tuple[bool, list[str]]:
    path = candidate["path"]
    matched: list[str] = []
    invalid = False
    for binding in candidate.get("argv_bindings", []):
        form = binding.get("form")
        if form == "pair":
            option = binding.get("option")
            for idx, token in enumerate(argv[:-1]):
                if token == option and argv[idx + 1] == path:
                    matched.append(f"{option} {path}")
        elif form == "plus_prefix":
            expected = f"{binding.get('prefix')}{path}"
            if expected in argv:
                matched.append(expected)
        elif form == "exact_token":
            if path in argv:
                matched.append(path)
        else:
            invalid = True
    return bool(matched) and not invalid, matched


_MODULE_RE_TEMPLATE = r"(?m)^\s*module\s+(?:automatic\s+)?{name}(?:\s|#|\(|;)"


def _find_modules(root: Path, required: Iterable[str]) -> tuple[dict[str, str], list[str]]:
    pending = set(required)
    found: dict[str, str] = {}
    unreadable: list[str] = []
    if not pending:
        return found, unreadable
    candidates = [root] if root.is_file() else sorted(root.rglob("*"))
    for source in candidates:
        if not source.is_file() or source.suffix.lower() not in {".v", ".sv", ".vh", ".svh"}:
            continue
        try:
            text = source.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            unreadable.append(f"{source}:{exc}")
            continue
        for name in tuple(pending):
            if re.search(_MODULE_RE_TEMPLATE.format(name=re.escape(name)), text):
                found[name] = source.as_posix()
                pending.remove(name)
        if not pending:
            break
    return found, unreadable


def _compiler_identity(argv0: str) -> dict[str, Any]:
    raw = Path(argv0)
    resolved: Path | None = None
    if raw.is_absolute() and raw.exists():
        resolved = raw.resolve()
    else:
        located = shutil.which(argv0)
        if located:
            resolved = Path(located).resolve()
    result: dict[str, Any] = {"argv0": argv0, "resolved": None, "exists": False}
    if resolved is not None and resolved.is_file():
        result.update(
            {
                "resolved": resolved.as_posix(),
                "exists": True,
                "bytes": resolved.stat().st_size,
                "sha256": _sha256_file(resolved),
            }
        )
    return result


def _make_payload(argv: list[str]) -> list[str] | None:
    for idx, token in enumerate(argv):
        if Path(token).name.lower() in {"make", "gmake"}:
            return argv[idx:]
    return None


def _resolved_dependency_argv(
    compile_spec: dict[str, Any], launcher_argv: list[str], errors: list[dict[str, Any]]
) -> tuple[list[str], dict[str, Any]]:
    make_payload = _make_payload(launcher_argv)
    resolver = compile_spec.get("resolver")
    if make_payload is None:
        return launcher_argv, {"method": "DIRECT_COMPILER_ARGV", "pass": True}
    if not isinstance(resolver, dict):
        errors.append({"code": "COMPILE_WRAPPER_RESOLUTION_ABSENT", "blocking_category": "server_start"})
        return [], {"method": None, "pass": False}
    resolver_argv = resolver.get("argv")
    stdout_path_text = resolver.get("stdout_path")
    expected_sha = resolver.get("stdout_sha256")
    compiler_basename = resolver.get("compiler_basename")
    receipt: dict[str, Any] = {
        "method": resolver.get("method"),
        "argv": resolver_argv,
        "stdout_path": stdout_path_text,
        "stdout_sha256": expected_sha,
        "compiler_basename": compiler_basename,
        "exit_code": resolver.get("exit_code"),
        "pass": False,
    }
    if resolver.get("method") != "make_just_print" or not isinstance(resolver_argv, list):
        errors.append({"code": "COMPILE_WRAPPER_RESOLUTION_INVALID", "blocking_category": "server_start"})
        return [], receipt
    if resolver.get("exit_code") != 0:
        errors.append({"code": "COMPILE_WRAPPER_RESOLUTION_NONZERO", "blocking_category": "server_start"})
    resolver_make = _make_payload(resolver_argv)
    if resolver_make is None:
        errors.append({"code": "COMPILE_WRAPPER_RESOLVER_NOT_MAKE", "blocking_category": "server_start"})
        return [], receipt
    normalized_resolver = [x for x in resolver_make if x not in {"-n", "--just-print", "--dry-run", "--recon"}]
    if normalized_resolver != make_payload:
        errors.append({"code": "COMPILE_WRAPPER_RESOLVER_ARGUMENT_DRIFT", "blocking_category": "server_start"})
    if not isinstance(stdout_path_text, str):
        errors.append({"code": "COMPILE_WRAPPER_RESOLUTION_OUTPUT_ABSENT", "blocking_category": "server_start"})
        return [], receipt
    stdout_path = Path(stdout_path_text)
    if not stdout_path.is_file():
        errors.append({"code": "COMPILE_WRAPPER_RESOLUTION_OUTPUT_ABSENT", "path": stdout_path_text, "blocking_category": "server_start"})
        return [], receipt
    actual_sha = _sha256_file(stdout_path)
    receipt["actual_stdout_sha256"] = actual_sha
    if actual_sha != expected_sha:
        errors.append({"code": "COMPILE_WRAPPER_RESOLUTION_OUTPUT_IDENTITY_MISMATCH", "blocking_category": "server_start"})
    resolved: list[str] = []
    for line in stdout_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            tokens = shlex.split(line)
        except ValueError:
            continue
        compiler_indexes = [idx for idx, token in enumerate(tokens) if Path(token).name == compiler_basename]
        if compiler_indexes:
            if resolved:
                errors.append({"code": "COMPILE_WRAPPER_MULTIPLE_COMPILER_COMMANDS", "blocking_category": "server_start"})
                return [], receipt
            resolved = tokens[compiler_indexes[0] :]
    if not resolved:
        errors.append({"code": "COMPILE_WRAPPER_COMPILER_COMMAND_ABSENT", "blocking_category": "server_start"})
    receipt["resolved_argv_sha256"] = _canonical_json_sha(resolved)
    receipt["pass"] = not any(e["code"].startswith("COMPILE_WRAPPER_") for e in errors)
    return resolved, receipt


def _runtime_context(request: dict[str, Any], compiler: dict[str, Any]) -> dict[str, Any]:
    declared = request.get("runtime_context", {})
    return {
        "execution_epoch": declared.get("execution_epoch"),
        "boot_id": declared.get("boot_id"),
        "hostname": declared.get("hostname") or socket.gethostname(),
        "platform": declared.get("platform") or platform.platform(),
        "machine": declared.get("machine") or platform.machine(),
        "compiler": compiler,
    }


def _provider_flag_projection(argv: list[str], provider_sets: list[dict[str, Any]]) -> list[str]:
    selected: list[str] = []
    for provider_set in provider_sets:
        for candidate in provider_set.get("candidates", []):
            _, matches = _path_bound_in_argv(argv, candidate)
            selected.extend(matches)
    for token in argv:
        if token.startswith("+define+") or token in {"-sverilog", "-v2005", "-full64"}:
            selected.append(token)
    return selected


def _semantic_fingerprint(
    request: dict[str, Any], dependency_argv: list[str], compiler: dict[str, Any], provider_state: list[dict[str, Any]]
) -> tuple[dict[str, Any], str]:
    semantic = request.get("semantic_identity", {})
    value = {
        "compiler": compiler,
        "selected_makefile_sha256": semantic.get("selected_makefile_sha256"),
        "recursive_source_identity_sha256": semantic.get("recursive_source_identity_sha256"),
        "top_filelist_sha256": semantic.get("top_filelist_sha256"),
        "compile_environment": semantic.get("compile_environment", {}),
        "provider_flag_projection": _provider_flag_projection(dependency_argv, request.get("provider_sets", [])),
        "provider_state": provider_state,
    }
    return value, _canonical_json_sha(value)


def _validate_probe_receipt(
    request: dict[str, Any], receipt: dict[str, Any], semantic_sha: str, provider_state_sha: str
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    expected_modules = sorted({m for item in request.get("provider_sets", []) for m in item.get("required_modules", [])})
    checks = {
        "schema": receipt.get("schema") == PROBE_RECEIPT_SCHEMA,
        "semantic_fingerprint": receipt.get("semantic_fingerprint_sha256") == semantic_sha,
        "provider_state": receipt.get("provider_state_sha256") == provider_state_sha,
        "required_modules": sorted(receipt.get("required_modules", [])) == expected_modules,
        "exit_zero": receipt.get("compile_exit") == 0,
        "no_unresolved": receipt.get("unresolved_modules") == [],
        "no_dut_compile": receipt.get("dut_compile_invoked") is False,
        "no_simulation": receipt.get("simulation_invoked") is False,
        "not_truncated": receipt.get("log_truncated") is False,
    }
    for name, ok in checks.items():
        if not ok:
            errors.append({"code": f"PROVIDER_PROBE_{name.upper()}_INVALID", "blocking_category": "server_start"})
    return errors


def attest(request: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if request.get("schema") != REQUEST_SCHEMA:
        errors.append({"code": "REQUEST_SCHEMA_MISMATCH", "blocking_category": "server_start"})
    compile_spec = request.get("actual_compile", {})
    argv = compile_spec.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        argv = []
        errors.append({"code": "ACTUAL_COMPILE_ARGV_INVALID", "blocking_category": "server_start"})
    dependency_argv, resolution_receipt = _resolved_dependency_argv(compile_spec, argv, errors)
    compiler = _compiler_identity(dependency_argv[0]) if dependency_argv else {"argv0": None, "resolved": None, "exists": False}
    if dependency_argv and not compiler["exists"]:
        errors.append({"code": "COMPILER_EXECUTABLE_UNAVAILABLE", "path": dependency_argv[0], "blocking_category": "server_start"})

    provider_set_receipts: list[dict[str, Any]] = []
    provider_state: list[dict[str, Any]] = []
    unresolved: set[str] = set()
    all_required = {m for item in request.get("provider_sets", []) for m in item.get("required_modules", [])}
    for provider_set in request.get("provider_sets", []):
        required = list(provider_set.get("required_modules", []))
        found: dict[str, str] = {}
        candidate_receipts: list[dict[str, Any]] = []
        for candidate in provider_set.get("candidates", []):
            path_text = candidate.get("path")
            kind = candidate.get("kind")
            c: dict[str, Any] = {"id": candidate.get("id"), "path": path_text, "kind": kind}
            if not isinstance(path_text, str) or not Path(path_text).is_absolute():
                c["status"] = "INVALID_PATH"
                errors.append({"code": "PROVIDER_PATH_NOT_ABSOLUTE", "id": candidate.get("id"), "blocking_category": "server_start"})
                candidate_receipts.append(c)
                continue
            bound, matches = _path_bound_in_argv(dependency_argv, candidate)
            c["argv_binding_matches"] = matches
            if not bound:
                c["status"] = "UNBOUND"
                errors.append({"code": "PROVIDER_NOT_BOUND_TO_ACTUAL_ARGV", "id": candidate.get("id"), "blocking_category": "server_start"})
            path = Path(path_text)
            exists = path.exists()
            expected_type = "directory" if kind == "source_directory" else "file"
            correct_type = path.is_dir() if expected_type == "directory" else path.is_file()
            c.update({"exists": exists, "correct_type": correct_type})
            if not exists:
                warnings.append(
                    {
                        "code": "NAMED_PROVIDER_PATH_ABSENT_RECORD_ONLY",
                        "id": candidate.get("id"),
                        "path": path_text,
                        "reason": "path_absence_is_not_module-provider-closure",
                    }
                )
            elif not correct_type:
                warnings.append(
                    {
                        "code": "NAMED_PROVIDER_PATH_WRONG_TYPE_RECORD_ONLY",
                        "id": candidate.get("id"),
                        "path": path_text,
                        "reason": "other providers or a production probe may still close the module set",
                    }
                )
            module_sources: dict[str, str] = {}
            unreadable: list[str] = []
            if exists and correct_type and kind in {"source_directory", "source_file"}:
                module_sources, unreadable = _find_modules(path, required)
                found.update(module_sources)
            c["module_sources"] = module_sources
            c["unreadable_sources"] = unreadable
            c["status"] = "SOURCE_PROVEN" if module_sources else "AVAILABLE_UNENUMERATED" if exists and correct_type else c.get("status", "ABSENT_RECORD_ONLY")
            candidate_receipts.append(c)
            try:
                stat = path.stat() if exists else None
            except OSError:
                stat = None
            provider_state.append(
                {
                    "id": candidate.get("id"),
                    "path": path_text,
                    "kind": kind,
                    "exists": exists,
                    "correct_type": correct_type,
                    "size": stat.st_size if stat else None,
                    "mtime_ns": stat.st_mtime_ns if stat else None,
                }
            )
        missing = sorted(set(required) - set(found))
        unresolved.update(missing)
        provider_set_receipts.append(
            {
                "id": provider_set.get("id"),
                "required_modules": required,
                "source_proven_modules": found,
                "unresolved_before_probe": missing,
                "candidates": candidate_receipts,
            }
        )

    provider_state = sorted(provider_state, key=lambda x: (str(x.get("id")), str(x.get("path"))))
    provider_state_sha = _canonical_json_sha(provider_state)
    semantic, semantic_sha = _semantic_fingerprint(request, dependency_argv, compiler, provider_state)
    known_good = request.get("known_good_compile")
    known_good_comparison = None
    if isinstance(known_good, dict):
        known_good_resolved = set(known_good.get("resolved_modules", []))
        known_good_comparison = {
            "compile_exit_zero": known_good.get("compile_exit") == 0,
            "required_modules_resolved": all_required.issubset(known_good_resolved),
            "semantic_fingerprint_match": known_good.get("semantic_fingerprint_sha256") == semantic_sha,
            "claim_boundary": "historical comparison only; never proves current provider availability",
        }

    probe_receipt = request.get("production_probe_receipt")
    probe_errors: list[dict[str, Any]] = []
    probe_valid = False
    if probe_receipt is not None:
        if not isinstance(probe_receipt, dict):
            probe_errors.append({"code": "PROVIDER_PROBE_RECEIPT_INVALID", "blocking_category": "server_start"})
        else:
            probe_errors = _validate_probe_receipt(request, probe_receipt, semantic_sha, provider_state_sha)
            probe_valid = not probe_errors
        errors.extend(probe_errors)

    source_closed = not unresolved
    ready = not errors and (source_closed or probe_valid)
    if errors:
        disposition = "BLOCKED_BEFORE_PROVIDER_PROBE"
    elif ready:
        disposition = "MODULE_PROVIDER_CLOSURE_READY"
    else:
        disposition = "PROVIDER_PROBE_REQUIRED"
    runtime_context = _runtime_context(request, compiler)
    reuse_projection = {
        "runtime_context": runtime_context,
        "semantic_fingerprint_sha256": semantic_sha,
        "provider_state_sha256": provider_state_sha,
        "required_modules": sorted(all_required),
    }
    return {
        "schema": RECEIPT_SCHEMA,
        "package_id": request.get("package_id"),
        "family": request.get("family"),
        "execution_group": request.get("execution_group"),
        "pass": ready,
        "ready_for_full_compile": ready,
        "disposition": disposition,
        "compile_invoked": False,
        "all_errors_collected": True,
        "blocking_category": "server_start",
        "actual_compile_argv_sha256": _canonical_json_sha(argv),
        "resolved_compiler_argv_sha256": _canonical_json_sha(dependency_argv),
        "compile_wrapper_resolution": resolution_receipt,
        "runtime_context": runtime_context,
        "semantic_fingerprint": semantic,
        "semantic_fingerprint_sha256": semantic_sha,
        "provider_state": provider_state,
        "provider_state_sha256": provider_state_sha,
        "reuse_projection_sha256": _canonical_json_sha(reuse_projection),
        "provider_sets": provider_set_receipts,
        "unresolved_before_probe": sorted(unresolved),
        "source_provider_closure": source_closed,
        "production_probe_valid": probe_valid,
        "known_good_comparison": known_good_comparison,
        "warnings": warnings,
        "errors": errors,
        "claim_boundary": "Current module-provider closure only. A named path absence is record-only; readiness requires complete source declarations or an exact same-context production provider probe. No DUT compile/simulation claim.",
    }


def reuse_receipt(prior: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    current = attest({**request, "production_probe_receipt": None})
    same_projection = prior.get("reuse_projection_sha256") == current.get("reuse_projection_sha256")
    prior_valid = (
        prior.get("schema") == RECEIPT_SCHEMA
        and prior.get("compile_invoked") is False
        and prior.get("disposition") in {"MODULE_PROVIDER_CLOSURE_READY", "BLOCKED_BEFORE_PROVIDER_PROBE"}
    )
    reusable = bool(prior_valid and same_projection)
    prior_ready = prior.get("ready_for_full_compile") is True
    return {
        "schema": "server-compile-provider-closure-reuse-receipt-v1",
        "reuse_applicable": reusable,
        "same_reuse_projection": same_projection,
        "prior_receipt_valid": prior_valid,
        "prior_ready": prior_ready,
        "disposition": (
            "READY_BY_REUSED_PROVIDER_RECEIPT"
            if reusable and prior_ready
            else "BLOCKED_BY_REUSED_PROVIDER_RECEIPT"
            if reusable
            else "FRESH_PROVIDER_PROBE_REQUIRED"
        ),
        "compile_invoked": False,
        "blocking_category": "server_start",
    }


def _safe_under(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def run_provider_probe(request: dict[str, Any]) -> dict[str, Any]:
    base = attest({**request, "production_probe_receipt": None})
    spec = request.get("probe_spec", {})
    errors = list(base.get("errors", []))
    required_modules = sorted({m for item in request.get("provider_sets", []) for m in item.get("required_modules", [])})
    runtime_root = Path(spec.get("runtime_root", ""))
    source_path = Path(spec.get("source_path", ""))
    log_path = Path(spec.get("log_path", ""))
    cwd = Path(spec.get("cwd", ""))
    argv = spec.get("argv")
    if not runtime_root.is_dir() or runtime_root.is_symlink():
        errors.append({"code": "PROBE_RUNTIME_ROOT_INVALID", "blocking_category": "server_start"})
    for role, path in (("source", source_path), ("log", log_path), ("cwd", cwd)):
        if not _safe_under(runtime_root, path):
            errors.append({"code": "PROBE_PATH_ESCAPE", "role": role, "blocking_category": "server_start"})
    if not cwd.is_dir() or cwd.is_symlink():
        errors.append({"code": "PROBE_CWD_INVALID", "blocking_category": "server_start"})
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
        errors.append({"code": "PROBE_ARGV_INVALID", "blocking_category": "server_start"})
        argv = []
    if argv and base.get("semantic_fingerprint", {}).get("compiler", {}).get("resolved") != _compiler_identity(argv[0]).get("resolved"):
        errors.append({"code": "PROBE_COMPILER_IDENTITY_DRIFT", "blocking_category": "server_start"})
    full_projection = base.get("semantic_fingerprint", {}).get("provider_flag_projection", [])
    probe_projection = _provider_flag_projection(argv, request.get("provider_sets", [])) if argv else []
    if probe_projection != full_projection:
        errors.append({"code": "PROBE_PROVIDER_FLAG_PROJECTION_DRIFT", "blocking_category": "server_start"})
    if str(source_path) not in argv:
        errors.append({"code": "PROBE_SOURCE_NOT_BOUND_TO_ARGV", "blocking_category": "server_start"})

    source_text = "module codex_required_module_provider_probe;\n" + "".join(
        f"  {name} codex_probe_{idx}();\n" for idx, name in enumerate(required_modules)
    ) + "endmodule\n"
    compile_exit: int | None = None
    log_bytes = b""
    if not errors:
        source_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source_text, encoding="utf-8")
        completed = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        compile_exit = completed.returncode
        log_bytes = completed.stdout
        log_path.write_bytes(log_bytes)
    log_text = log_bytes.decode("utf-8", errors="replace")
    unresolved_from_log = sorted(
        set(re.findall(r"(?m)^\s*(?:Error-\[URMI\].*|.*Unresolved modules?.*)$", log_text, flags=re.IGNORECASE))
    )
    return {
        "schema": PROBE_RECEIPT_SCHEMA,
        "package_id": request.get("package_id"),
        "execution_group": request.get("execution_group"),
        "semantic_fingerprint_sha256": base.get("semantic_fingerprint_sha256"),
        "provider_state_sha256": base.get("provider_state_sha256"),
        "required_modules": required_modules,
        "actual_probe_argv": argv,
        "actual_probe_argv_sha256": _canonical_json_sha(argv),
        "probe_source": {
            "path": str(source_path),
            "bytes": len(source_text.encode("utf-8")),
            "sha256": _sha256_bytes(source_text.encode("utf-8")),
        },
        "probe_log": {
            "path": str(log_path),
            "bytes": len(log_bytes),
            "sha256": _sha256_bytes(log_bytes),
        },
        "compile_exit": compile_exit,
        "unresolved_modules": unresolved_from_log,
        "dut_compile_invoked": False,
        "simulation_invoked": False,
        "log_truncated": False,
        "pass": not errors and compile_exit == 0 and not unresolved_from_log,
        "errors": errors,
        "claim_boundary": "Package-owned module lookup probe only; no DUT compile, elaborated DUT, simulation, natural terminal or formal-D claim.",
    }


_PRIMARY_ERROR_PATTERNS = [
    re.compile(r"^(?:Fatal|Error)-\[[^]]+\]", re.IGNORECASE),
    re.compile(r"\b(?:fatal error|syntax error|undefined reference|unresolved modules?)\b", re.IGNORECASE),
    re.compile(r"^\s*[^:]+:\d+(?::\d+)?:\s*(?:fatal\s+)?error\b", re.IGNORECASE),
]


def extract_first_error(log_text: str, context_lines: int = 3) -> dict[str, Any]:
    lines = log_text.splitlines()
    match_index: int | None = None
    for idx, line in enumerate(lines):
        if any(pattern.search(line) for pattern in _PRIMARY_ERROR_PATTERNS):
            match_index = idx
            break
    if match_index is None:
        return {"found": False, "line_number": None, "line": None, "context": [], "selection_policy": "compiler_error_or_fatal_before_platform_prose"}
    lo = max(0, match_index - context_lines)
    hi = min(len(lines), match_index + context_lines + 1)
    return {
        "found": True,
        "line_number": match_index + 1,
        "line": lines[match_index],
        "context": [{"line_number": i + 1, "text": lines[i]} for i in range(lo, hi)],
        "selection_policy": "compiler_error_or_fatal_before_platform_prose",
    }


def audit_compile_failure_core(request: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if request.get("schema") != CORE_REQUEST_SCHEMA:
        errors.append({"code": "REQUEST_SCHEMA_MISMATCH", "blocking_category": "return"})
    root = Path(request.get("return_root", ""))
    required = request.get("required_members", {})
    loaded: dict[str, Any] = {}
    identities: dict[str, Any] = {}
    for role, rel in required.items():
        path = root / rel
        if not path.is_file():
            errors.append({"code": "REQUIRED_COMPILE_CORE_MEMBER_ABSENT", "role": role, "path": rel, "blocking_category": "return"})
            continue
        identities[role] = {"path": rel, "bytes": path.stat().st_size, "sha256": _sha256_file(path)}
        try:
            loaded[role] = _load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append({"code": "COMPILE_CORE_MEMBER_INVALID_JSON", "role": role, "path": rel, "detail": str(exc), "blocking_category": "return"})

    expected = request.get("expected", {})
    argv_doc = loaded.get("actual_compile_sim_argv")
    if argv_doc is not None:
        try:
            actual_argv = _json_pointer(argv_doc, request.get("actual_argv_pointer", "/compile/argv"))
            actual_cwd = _json_pointer(argv_doc, request.get("actual_cwd_pointer", "/compile/cwd"))
            if actual_argv != expected.get("compile_argv") or actual_cwd != expected.get("compile_cwd"):
                errors.append({"code": "RETURNED_ACTUAL_COMPILE_ARGV_STALE", "blocking_category": "return"})
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            errors.append({"code": "RETURNED_ACTUAL_COMPILE_ARGV_UNREADABLE", "detail": str(exc), "blocking_category": "return"})

    sim_exit = loaded.get("sim_exit_receipt")
    if sim_exit is not None and sim_exit.get("simulation_started") is not False:
        errors.append({"code": "COMPILE_FAILURE_SIM_STARTED_SENTINEL_INVALID", "blocking_category": "return"})
    compile_core = loaded.get("compile_core")
    if compile_core is not None:
        if not isinstance(compile_core.get("compile_exit"), int) or compile_core.get("compile_exit") == 0:
            errors.append({"code": "COMPILE_FAILURE_EXIT_INVALID", "blocking_category": "return"})
        first_error = compile_core.get("first_error", {})
        if not first_error.get("found") or not first_error.get("line"):
            errors.append({"code": "COMPILE_FIRST_TRUE_ERROR_ABSENT", "blocking_category": "return"})
    manifest = loaded.get("return_core_manifest")
    if manifest is not None:
        declared = manifest.get("members")
        if not isinstance(declared, list):
            errors.append({"code": "RETURN_CORE_MANIFEST_MEMBER_SET_INVALID", "blocking_category": "return"})
        else:
            declared_by_path = {item.get("path"): item for item in declared if isinstance(item, dict)}
            required_paths = set(required.values()) - {required.get("return_core_manifest")}
            if set(declared_by_path) != required_paths:
                errors.append({"code": "RETURN_CORE_MANIFEST_EXACT_SET_MISMATCH", "missing": sorted(required_paths - set(declared_by_path)), "unexpected": sorted(set(declared_by_path) - required_paths), "blocking_category": "return"})
            for rel in sorted(required_paths & set(declared_by_path)):
                path = root / rel
                if path.is_file():
                    item = declared_by_path[rel]
                    if item.get("bytes") != path.stat().st_size or item.get("sha256") != _sha256_file(path):
                        errors.append({"code": "RETURN_CORE_MANIFEST_IDENTITY_MISMATCH", "path": rel, "blocking_category": "return"})
    return {
        "schema": CORE_RECEIPT_SCHEMA,
        "package_id": expected.get("package_id"),
        "execution_id": expected.get("execution_id"),
        "pass": not errors,
        "all_errors_collected": True,
        "blocking_category": "return",
        "member_identities": identities,
        "errors": errors,
        "claim_boundary": "Compile-not-started return-core completeness and actual launch binding only; no DUT or simulation result claim.",
    }


def _main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_attest = sub.add_parser("attest")
    p_attest.add_argument("--request", required=True, type=Path)
    p_attest.add_argument("--output", required=True, type=Path)
    p_probe = sub.add_parser("run-probe")
    p_probe.add_argument("--request", required=True, type=Path)
    p_probe.add_argument("--output", required=True, type=Path)
    p_reuse = sub.add_parser("reuse")
    p_reuse.add_argument("--receipt", required=True, type=Path)
    p_reuse.add_argument("--request", required=True, type=Path)
    p_reuse.add_argument("--output", required=True, type=Path)
    p_error = sub.add_parser("first-error")
    p_error.add_argument("--log", required=True, type=Path)
    p_error.add_argument("--output", required=True, type=Path)
    p_core = sub.add_parser("audit-core")
    p_core.add_argument("--request", required=True, type=Path)
    p_core.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "attest":
        result = attest(_load_json(args.request))
    elif args.command == "run-probe":
        result = run_provider_probe(_load_json(args.request))
    elif args.command == "reuse":
        result = reuse_receipt(_load_json(args.receipt), _load_json(args.request))
    elif args.command == "first-error":
        result = extract_first_error(args.log.read_text(encoding="utf-8", errors="replace"))
    else:
        result = audit_compile_failure_core(_load_json(args.request))
    _write_json(args.output, result)
    return 0 if result.get("pass", result.get("reuse_applicable", result.get("found", False))) else 1


if __name__ == "__main__":
    sys.exit(_main())
