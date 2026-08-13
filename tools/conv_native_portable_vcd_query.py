#!/usr/bin/env python3
"""Build the native-Conv first-fresh portable query receipt from one direct VCD.

The parser is streaming and has no byte, event, or time-window limit.  It emits
one ordered row for every value record of every profile candidate.  The shared
portable-waveform helper remains authoritative for the generic runtime receipt;
this adapter adds the first-fresh requirement that *both* direct VCD and the
registered query receipt must be complete.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import sys
import uuid
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any, Iterable


QUERY_SCHEMA = "server-waveform-signal-query-receipt-v1"
STATUS_SCHEMA = "conv-native-portable-first-fresh-status-v1"
VALUE_RE = re.compile(r"^[01xXzZ]")
VECTOR_RE = re.compile(r"^[bB]([01xXzZ]+)\s+(\S+)$")


class QueryError(ValueError):
    """The VCD/query evidence cannot satisfy the registered profile."""


def pretty(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temporary.write_bytes(pretty(value))
    os.replace(temporary, path)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def file_identity(path: Path, relative: str | None = None) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return {
        "path": relative if relative is not None else str(path),
        "bytes": size,
        "sha256": digest.hexdigest(),
    }


def normalize_name(value: str) -> str:
    # Escaped VCD identifiers retain their payload but not the leading escape.
    return value[1:] if value.startswith("\\") else value


def normalize_vector(value: str, width: int) -> str:
    lowered = value.lower()
    if len(lowered) < width:
        fill = lowered[0] if lowered and lowered[0] in "xz" else "0"
        lowered = fill * (width - len(lowered)) + lowered
    if len(lowered) > width:
        lowered = lowered[-width:]
    if not re.fullmatch(rf"[01xz]{{{width}}}", lowered):
        raise QueryError(f"invalid {width}-bit VCD value: {value!r}")
    return lowered


def parse_vcd(vcd: Path, profile: dict[str, Any]) -> dict[str, Any]:
    candidates = profile["probe_catalog"]
    by_path = {row["hierarchical_path"]: row for row in candidates}
    by_id: dict[str, dict[str, Any]] = {}
    scopes: list[str] = []
    timescale_parts: list[str] = []
    timescale: str | None = None
    in_timescale = False
    header_done = False
    current_time = 0
    sequence = 0
    events: list[dict[str, Any]] = []
    end_states: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    with vcd.open("r", encoding="utf-8", errors="replace", newline="") as stream:
        for raw in stream:
            line = raw.strip()
            if not line:
                continue
            if not header_done:
                if in_timescale:
                    before, marker, _ = line.partition("$end")
                    if before:
                        timescale_parts.append(before.strip())
                    if marker:
                        timescale = " ".join(timescale_parts).strip()
                        in_timescale = False
                    continue
                if line.startswith("$timescale"):
                    remainder = line[len("$timescale") :].strip()
                    before, marker, _ = remainder.partition("$end")
                    if before:
                        timescale_parts.append(before.strip())
                    if marker:
                        timescale = " ".join(timescale_parts).strip()
                    else:
                        in_timescale = True
                    continue
                if line.startswith("$scope "):
                    tokens = line.split()
                    if len(tokens) >= 4:
                        scopes.append(normalize_name(tokens[2]))
                    continue
                if line.startswith("$upscope"):
                    if scopes:
                        scopes.pop()
                    continue
                if line.startswith("$var "):
                    tokens = line.split()
                    if len(tokens) < 6 or tokens[-1] != "$end":
                        errors.append(f"malformed VCD var declaration: {line[:160]}")
                        continue
                    try:
                        width = int(tokens[2])
                    except ValueError:
                        errors.append(f"non-decimal VCD width: {tokens[2]}")
                        continue
                    reference = " ".join(tokens[4:-1])
                    reference = normalize_name(reference)
                    path = ".".join([*scopes, reference])
                    candidate = by_path.get(path)
                    if candidate is not None:
                        if width != candidate["width"]:
                            errors.append(
                                f"candidate width mismatch: {candidate['candidate_id']} "
                                f"expected={candidate['width']} actual={width}"
                            )
                        if tokens[3] in by_id:
                            errors.append(f"duplicate candidate VCD id: {tokens[3]}")
                        by_id[tokens[3]] = candidate
                    continue
                if line.startswith("$enddefinitions"):
                    header_done = True
                continue

            if line.startswith("#"):
                try:
                    current_time = int(line[1:])
                except ValueError:
                    errors.append(f"invalid VCD timestamp: {line[:80]}")
                continue
            candidate: dict[str, Any] | None = None
            value: str | None = None
            vector = VECTOR_RE.match(line)
            if vector:
                candidate = by_id.get(vector.group(2))
                if candidate is not None:
                    try:
                        value = "b" + normalize_vector(vector.group(1), candidate["width"])
                    except QueryError as error:
                        errors.append(str(error))
            elif VALUE_RE.match(line):
                candidate = by_id.get(line[1:])
                if candidate is not None:
                    if candidate["width"] != 1:
                        errors.append(
                            f"scalar record for vector candidate: {candidate['candidate_id']}"
                        )
                    else:
                        value = line[0].lower()
            if candidate is None or value is None:
                continue
            row = {
                "sequence": sequence,
                "time_tick": current_time,
                "candidate_id": candidate["candidate_id"],
                "hierarchical_path": candidate["hierarchical_path"],
                "width": candidate["width"],
                "value": value,
            }
            events.append(row)
            end_states[candidate["candidate_id"]] = {
                key: row[key]
                for key in (
                    "candidate_id",
                    "hierarchical_path",
                    "width",
                    "time_tick",
                    "value",
                )
            }
            sequence += 1

    expected = [row["candidate_id"] for row in candidates]
    covered = [
        row["candidate_id"]
        for row in candidates
        if row["hierarchical_path"] in {
            declared["hierarchical_path"] for declared in by_id.values()
        }
        and row["candidate_id"] in end_states
    ]
    missing = [item for item in expected if item not in covered]
    if not header_done:
        errors.append("VCD lacks $enddefinitions")
    if not timescale:
        errors.append("VCD timescale is absent")
    if missing:
        errors.append(f"candidate exact-set incomplete: {missing}")
    return {
        "timescale": timescale or "UNKNOWN",
        "events": events,
        "end_states": [end_states[item] for item in expected if item in end_states],
        "expected": expected,
        "covered": covered,
        "missing": missing,
        "errors": errors,
    }


def load_shared(path: Path):
    spec = importlib.util.spec_from_file_location("codex_portable_shared", path)
    if spec is None or spec.loader is None:
        raise QueryError(f"cannot load shared portable helper: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise QueryError(f"artifact is outside asset root: {path}") from error


def argv_json(text_path: Path, output: Path) -> int:
    lines = text_path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise QueryError("actual simulator argv text must contain exactly one line")
    argv = shlex.split(lines[0], posix=True)
    write_json(output, argv)
    return 0


def incomplete_query(
    profile: dict[str, Any],
    package_id: str,
    execution_id: str,
    attempt_id: str,
    source_identity: dict[str, Any],
    completeness: str,
    parsed: dict[str, Any] | None,
) -> dict[str, Any]:
    parsed = parsed or {
        "timescale": "UNKNOWN",
        "events": [],
        "end_states": [],
        "expected": [row["candidate_id"] for row in profile["probe_catalog"]],
        "covered": [],
        "missing": [row["candidate_id"] for row in profile["probe_catalog"]],
        "errors": ["portable VCD parse did not start"],
    }
    return {
        "schema": QUERY_SCHEMA,
        "package_id": package_id,
        "execution_id": execution_id,
        "attempt_id": attempt_id,
        "profile_sha256": hashlib.sha256(pretty(profile)).hexdigest(),
        "probe_catalog_sha256": profile["probe_catalog_sha256"],
        "timescale": parsed["timescale"],
        "completeness": completeness,
        "catalog": profile["probe_catalog"],
        "capture": {
            "format": "REGISTERED_EVENT_ROWS",
            "ordered": True,
            "every_transition": True,
            "no_byte_limit": True,
            "no_event_limit": True,
            "sampling": False,
            "truncation": False,
            "flush_complete": not parsed["errors"],
            "source_generation_report": source_identity,
        },
        "candidate_coverage": {
            "expected": parsed["expected"],
            "covered": parsed["covered"],
            "missing": parsed["missing"],
            "unexpected": [],
        },
        "events": parsed["events"],
        "candidate_end_states": parsed["end_states"],
        "claim_boundary": (
            "Same-attempt direct-VCD transition transport only; no DUT result or "
            "family root-cause claim."
        ),
    }


def collect_portable(args: argparse.Namespace) -> int:
    profile = load_json(args.profile)
    shared = load_shared(args.shared_helper)
    profile_errors = shared.validate_profile(profile)
    asset_root = args.asset_root.resolve()
    attempt_root = relative_to_root(args.attempt_root, asset_root)
    attempt_id = args.attempt_id
    evidence = args.output_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    source_copy = evidence / "PORTABLE_QUERY_SOURCE_REPORT.json"
    shutil.copyfile(args.source_report, source_copy)
    source_relative = relative_to_root(source_copy, asset_root)
    source_file_identity = file_identity(source_copy, source_relative)
    source_identity = {
        "path": source_file_identity["path"],
        "sha256": source_file_identity["sha256"],
    }
    completeness = "COMPLETE" if args.exit_kind == "NATURAL" else "PARTIAL"
    query_path = evidence / "SIGNAL_QUERY_RECEIPT.json"
    errors = [f"profile: {item}" for item in profile_errors]
    parsed: dict[str, Any] | None = None
    try:
        parsed = parse_vcd(args.vcd, profile)
        errors.extend(parsed["errors"])
    except (OSError, QueryError) as error:
        errors.append(f"VCD query parse: {type(error).__name__}: {error}")
    query = incomplete_query(
        profile,
        args.package_id,
        args.execution_id,
        attempt_id,
        source_identity,
        completeness,
        parsed,
    )
    write_json(query_path, query)

    raw = load_json(args.raw_receipt)
    allowlist = [
        f"{attempt_root}/{row['source_path']}"
        for row in raw.get("waveforms", [])
        if isinstance(row, dict) and isinstance(row.get("source_path"), str)
    ]
    vcd_relative = relative_to_root(args.vcd, asset_root)
    query_relative = relative_to_root(query_path, asset_root)
    allowlist.extend([vcd_relative, query_relative, source_relative])
    # Stable order with exact duplicate rejection.
    allowlist = list(dict.fromkeys(allowlist))
    allowlist_path = evidence / "PORTABLE_RETURN_ALLOWLIST.json"
    write_json(allowlist_path, allowlist)
    request = {
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": attempt_id,
        "attempt_root": attempt_root,
        "first_fresh_for_profile": True,
        "capture_mode": "DIRECT_VCD_AND_QUERY",
        "simulation_started": True,
        "exit_kind": args.exit_kind,
        "actual_sim_argv_path": relative_to_root(args.actual_sim_argv, asset_root),
        "dump_tcl_path": relative_to_root(args.dump_tcl, asset_root),
        "raw_vpd_runtime_receipt_path": relative_to_root(args.raw_receipt, asset_root),
        "portable_vcd_path": vcd_relative,
        "signal_query_receipt_path": query_relative,
        "return_allowlist_path": relative_to_root(allowlist_path, asset_root),
    }
    request_path = evidence / "PORTABLE_RUNTIME_REQUEST.json"
    write_json(request_path, request)
    runtime_path = evidence / "PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json"
    runtime: dict[str, Any] | None = None
    shared_report: dict[str, Any] | None = None
    try:
        runtime = shared.make_runtime_receipt(profile, request, asset_root)
        identities = {
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": attempt_id,
            "profile_sha256": hashlib.sha256(pretty(profile)).hexdigest(),
        }
        query_errors = shared.validate_query_receipt(query, profile, identities)
        errors.extend(f"query: {item}" for item in query_errors)
        shared_report = shared.validate_runtime_receipt(runtime, profile, asset_root)
        errors.extend(f"shared structural: {item}" for item in shared_report["errors"])
        errors.extend(
            f"shared diagnostic: {item}" for item in shared_report["diagnostic_findings"]
        )
        direct_ok = runtime.get("portable_vcd", {}).get("status") == "AVAILABLE"
        query_ok = (
            runtime.get("signal_query_receipt", {}).get("status") == "AVAILABLE"
            and not query_errors
            and not parsed["errors"] if parsed is not None else False
        )
        strict_complete = bool(
            not profile_errors
            and shared_report.get("contract_valid") is True
            and direct_ok
            and query_ok
        )
        runtime["diagnostic_status"] = (
            "COMPLETE" if strict_complete else "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
        )
        write_json(runtime_path, runtime)
    except (OSError, KeyError, QueryError, ValueError) as error:
        errors.append(f"runtime receipt: {type(error).__name__}: {error}")
        strict_complete = False
        if runtime is not None:
            runtime["diagnostic_status"] = "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
            write_json(runtime_path, runtime)

    identities: dict[str, Any] = {}
    for name, path in (
        ("actual_compile_argv", args.actual_compile_argv),
        ("actual_sim_argv", args.actual_sim_argv),
        ("dump_tcl", args.dump_tcl),
        ("raw_vpd_runtime_receipt", args.raw_receipt),
        ("portable_vcd", args.vcd),
        ("signal_query_receipt", query_path),
        ("source_generation_report", source_copy),
        ("portable_runtime_receipt", runtime_path),
    ):
        if path.is_file() and not path.is_symlink():
            identities[name] = file_identity(path, relative_to_root(path, asset_root))
        else:
            identities[name] = {"path": relative_to_root(path, asset_root), "available": False}
            errors.append(f"missing {name}: {path}")
    status = {
        "schema": STATUS_SCHEMA,
        "rule_id": "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
        "activation_epoch": profile.get("activation_epoch"),
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": attempt_id,
        "capture_mode": "DIRECT_VCD_AND_QUERY",
        "first_fresh_for_profile": True,
        "diagnostic_status": (
            "COMPLETE" if strict_complete and not errors else "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
        ),
        "pass": bool(strict_complete and not errors),
        "errors": errors,
        "identities": identities,
        "candidate_exact_set": [row["candidate_id"] for row in profile["probe_catalog"]],
        "no_byte_limit": True,
        "no_file_limit": True,
        "no_event_limit": True,
        "no_time_window": True,
        "sampling": False,
        "truncation": False,
        "size_based_deletion": False,
        "preserve_on_failure": [
            "raw_vpd",
            "compile_core",
            "sim_core",
            "signal_core",
            "return_core",
        ],
        "return_must_publish": True,
        "shared_validation": shared_report,
        "claim_boundary": (
            "Portable evidence integrity only. Production simulation and native-Conv "
            "root-cause conclusions remain dynamic."
        ),
    }
    write_json(evidence / "PORTABLE_FIRST_FRESH_STATUS.json", status)
    return 0 if status["pass"] else 1


def validate_final_zip(zip_path: Path, shared_helper: Path) -> dict[str, Any]:
    errors: list[str] = []
    details: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
            if not names or archive.testzip() is not None:
                raise QueryError("final ZIP is empty or has a CRC failure")
            if len(names) != len(set(names)):
                errors.append("final ZIP contains duplicate members")
            if any(
                PurePosixPath(name).is_absolute()
                or ".." in PurePosixPath(name).parts
                or "\\" in name
                for name in names
            ):
                errors.append("final ZIP contains an unsafe member")
            roots = {name.split("/", 1)[0] for name in names}
            if len(roots) != 1:
                raise QueryError(f"final ZIP root mismatch: {sorted(roots)}")
            root = next(iter(roots))

            def read(relative: str) -> bytes:
                member = f"{root}/{relative}"
                if member not in names:
                    raise QueryError(f"missing final ZIP member: {relative}")
                return archive.read(member)

            profile = json.loads(read("contracts/server_waveform_portable_profile.json"))
            dump = read("contracts/server_waveform_portable_dump.tcl").decode("utf-8")
            runner = read("PREPARE_AND_RUN.sh").decode("utf-8")
            request = json.loads(read("contracts/server_post_sim_return_request.json"))
            source = read("diagnostics/portable_query_source_report.json")
            source_value = json.loads(source)
            layout = json.loads(read("SERVER_RUNTIME_LAYOUT_CONTRACT.json"))
            compile_helper = read("package_tools/compile_core_evidence.py").decode("utf-8")
            packaged_shared = read("package_tools/server_waveform_portable_query.py")
            packaged_adapter = read("package_tools/conv_native_portable_vcd_query.py")
            shared = load_shared(shared_helper)
            profile_errors = shared.validate_profile(profile)
            errors.extend(f"profile: {item}" for item in profile_errors)
            if hashlib.sha256(packaged_shared).hexdigest() != file_identity(shared_helper)["sha256"]:
                errors.append("packaged shared portable helper identity differs from current disk")
            if hashlib.sha256(packaged_adapter).hexdigest() != file_identity(Path(__file__))["sha256"]:
                errors.append("packaged native portable adapter identity differs from current disk")
            expected_attempt = f"install/codex_runs/{root}/a0"
            expected_lines = [
                f"dump -file {expected_attempt}/run/sim_results/wave.vpd -type VPD",
                f"dump -file {expected_attempt}/run/sim_results/wave.vcd -type VCD",
                "dump -add tb_NDP_Top_new_phy -depth 0 -aggregates",
                "run",
                "quit",
            ]
            if dump.count(expected_lines[0]) != 1 or dump.count(expected_lines[1]) != 1:
                errors.append("portable dump lacks one exact VPD/VCD destination")
            if dump.count(expected_lines[2]) != 2:
                errors.append("portable dump lacks two exact full-hierarchy depth-0 scopes")
            if "run CODEX_" in dump or "run 12h" in dump:
                errors.append("portable dump introduced a simulation time window")
            for token in (
                "DUMP_VCD=1",
                "DUMP_FSDB=0",
                "TB_DUMP_FSDB=0",
                "DUMP_PORTABLE_VCD=1",
                '"$portable_family_helper" collect',
                '"$portable_shared_helper"',
                '"$post_sim_helper" finalize',
            ):
                if token not in runner:
                    errors.append(f"runner lacks portable token: {token}")
            if "DUMP_VCD=0" in runner:
                errors.append("runner cancels authoritative raw VPD")
            if runner.find('"$portable_family_helper" collect') > runner.find(
                '"$post_sim_helper" finalize'
            ):
                errors.append("portable collector is not before post-sim publication")
            if "portable_collection_status" not in runner:
                errors.append("runner does not preserve portable collection status")
            if any(
                token not in compile_helper
                for token in (
                    '"DUMP_VCD=1"',
                    '"DUMP_FSDB=0"',
                    '"TB_DUMP_FSDB=0"',
                    '"DUMP_PORTABLE_VCD=1"',
                )
            ):
                errors.append("compile-core receipt does not bind actual portable make argv")
            if layout.get("runtime_roots", {}).get("compile_root") != (
                f"install/codex_runs/{root}/{{attempt}}/compile"
            ):
                errors.append("runtime compile root changed from the frozen p42 layout")
            source_sha = hashlib.sha256(source).hexdigest()
            if profile.get("portable_vcd", {}).get("source_bound_scope", {}).get(
                "source_receipt_sha256"
            ) != source_sha:
                errors.append("portable source report/profile identity mismatch")
            candidates = profile.get("probe_catalog", [])
            expected_ids = [
                "mse4_memag_valid",
                "mse4_memag_bp_pre",
                "mse4_descriptor_valid",
                "mse4_descriptor_ready",
                "mse4_buffer_rvalid",
                "mse4_buffer_ready",
                "mse4_wdata_valid",
                "mse4_wdata_ready",
                "mse4_slice_finish",
            ]
            if [row.get("candidate_id") for row in candidates] != expected_ids:
                errors.append("portable MSE4 candidate exact-set differs")
            if source_value.get("catalog_complete") is not True:
                errors.append("portable source report does not claim exact catalog completeness")
            entries = {row.get("archive"): row for row in request.get("core_entries", [])}
            required_entries = {
                "runs/c0/actual_sim_argv.json",
                "runs/run/codex_waveform_portable.tcl",
                "waveforms/run/sim_results/wave.vcd",
                "evidence/portable/PORTABLE_QUERY_SOURCE_REPORT.json",
                "evidence/portable/SIGNAL_QUERY_RECEIPT.json",
                "evidence/portable/PORTABLE_RETURN_ALLOWLIST.json",
                "evidence/portable/PORTABLE_RUNTIME_REQUEST.json",
                "evidence/portable/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json",
                "evidence/portable/PORTABLE_FIRST_FRESH_STATUS.json",
            }
            if not required_entries.issubset(entries):
                errors.append("post-sim return request misses portable evidence members")
            status_entry = entries.get("evidence/portable/PORTABLE_FIRST_FRESH_STATUS.json", {})
            if status_entry.get("required") is not True:
                errors.append("portable first-fresh diagnostic status is not return-required")
            vcd_entry = entries.get("waveforms/run/sim_results/wave.vcd", {})
            if vcd_entry.get("required") is not False:
                errors.append("missing VCD would block core return instead of marking evidence incomplete")
            failures = profile.get("failure_semantics", {})
            if failures.get("return_must_publish") is not True or failures.get(
                "diagnostic_status"
            ) != "DIAGNOSTIC_EVIDENCE_INCOMPLETE":
                errors.append("portable failure isolation contract differs")
            if any(
                value is not None
                for value in (
                    profile.get("raw_vpd", {}).get("hard_limit_bytes"),
                    profile.get("portable_vcd", {}).get("hard_limit_bytes"),
                    profile.get("signal_query", {}).get("hard_limit_bytes"),
                    profile.get("signal_query", {}).get("hard_limit_events"),
                )
            ):
                errors.append("portable profile introduced a hard limit")
            details = {
                "package_id": root,
                "candidate_count": len(candidates),
                "capture_mode": "DIRECT_VCD_AND_QUERY",
                "raw_vpd_preserved": "DUMP_VCD=1" in runner,
                "direct_vcd_enabled": "DUMP_PORTABLE_VCD=1" in runner,
                "query_receipt_registered": bool(
                    entries.get("evidence/portable/SIGNAL_QUERY_RECEIPT.json")
                ),
                "return_failure_isolated": vcd_entry.get("required") is False,
            }
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, QueryError) as error:
        errors.append(f"{type(error).__name__}: {error}")
    return {
        "schema": "conv-native-portable-first-fresh-final-zip-validation-v1",
        "path": str(zip_path),
        "pass": not errors,
        "errors": errors,
        "details": details,
        "claim_boundary": "Exact final-ZIP portable plumbing only; no server or DUT claim.",
        "server_action": False,
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    argv = commands.add_parser("argv-json")
    argv.add_argument("--text", type=Path, required=True)
    argv.add_argument("--output", type=Path, required=True)
    run = commands.add_parser("collect")
    for name in (
        "profile",
        "shared-helper",
        "asset-root",
        "attempt-root",
        "output-dir",
        "source-report",
        "vcd",
        "actual-compile-argv",
        "actual-sim-argv",
        "dump-tcl",
        "raw-receipt",
    ):
        run.add_argument(f"--{name}", type=Path, required=True)
    run.add_argument("--package-id", required=True)
    run.add_argument("--execution-id", required=True)
    run.add_argument("--attempt-id", required=True)
    run.add_argument(
        "--exit-kind",
        choices=("NATURAL", "TIMEOUT", "HUP", "INT", "TERM", "SIMULATION_NONZERO"),
        required=True,
    )
    final_zip = commands.add_parser("validate-final-zip")
    final_zip.add_argument("--zip", dest="zip_path", type=Path, required=True)
    final_zip.add_argument("--shared-helper", type=Path, required=True)
    final_zip.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    try:
        if args.command == "argv-json":
            return argv_json(args.text, args.output)
        if args.command == "validate-final-zip":
            report = validate_final_zip(args.zip_path, args.shared_helper)
            write_json(args.output, report)
            return 0 if report["pass"] else 1
        return collect_portable(args)
    except (OSError, json.JSONDecodeError, QueryError) as error:
        if getattr(args, "command", None) == "collect":
            output = args.output_dir / "PORTABLE_FIRST_FRESH_STATUS.json"
            write_json(
                output,
                {
                    "schema": STATUS_SCHEMA,
                    "package_id": args.package_id,
                    "execution_id": args.execution_id,
                    "attempt_id": args.attempt_id,
                    "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
                    "pass": False,
                    "errors": [f"{type(error).__name__}: {error}"],
                    "return_must_publish": True,
                },
            )
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
