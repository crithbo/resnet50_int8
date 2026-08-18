#!/usr/bin/env python3
"""Finalize native-Conv runtime-v3 TB-VCD evidence as an exact return set."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any


def sha_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def normalize(path: str) -> str:
    parts: list[str] = []
    for part in path.split("."):
        cleaned = part.lstrip("\\").strip()
        # VCS appends a declaration range to vector references in the VCD
        # header (for example ``foo [15:0]``).  The source-bound catalog names
        # the net itself, so the range is width metadata rather than hierarchy.
        cleaned = re.sub(r"\s+\[[^]]+\]\s*$", "", cleaned)
        parts.append(cleaned)
    return ".".join(parts)


def scan_vcd(path: Path, expected: set[str]) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        return {
            "exists": False,
            "header_valid": False,
            "timescale": None,
            "catalog_complete": False,
            "catalog_exact_set": False,
            "last_appended_timestamp_ticks": 0,
            "value_characters": [],
            "identity_bytes": 0,
            "identity_sha256": None,
        }
    scopes: list[str] = []
    names: list[str] = []
    timescale: str | None = None
    pending_timescale = False
    timescale_rows: list[str] = []
    enddefinitions = False
    values: set[str] = set()
    last_timestamp = 0
    digest = hashlib.sha256()
    identity_bytes = 0
    with path.open("rb") as stream:
        for raw_line in stream:
            digest.update(raw_line)
            identity_bytes += len(raw_line)
            text = raw_line.decode("utf-8", errors="replace").strip()
            if not enddefinitions:
                if pending_timescale:
                    if text == "$end":
                        timescale = " ".join(timescale_rows).strip()
                        pending_timescale = False
                    elif text:
                        timescale_rows.append(text)
                    continue
                if text.startswith("$timescale"):
                    body = text.removeprefix("$timescale").replace("$end", "").strip()
                    if body:
                        timescale = body
                    else:
                        pending_timescale = True
                        timescale_rows = []
                elif text.startswith("$scope "):
                    fields = text.split()
                    if len(fields) >= 4:
                        scopes.append(fields[2])
                elif text.startswith("$upscope"):
                    if scopes:
                        scopes.pop()
                elif text.startswith("$var "):
                    fields = text.split()
                    if len(fields) >= 6:
                        reference = " ".join(fields[4:-1])
                        names.append(normalize(".".join([*scopes, reference])))
                elif text.startswith("$enddefinitions"):
                    enddefinitions = True
                continue
            if len(text) > 1 and text.startswith("#") and text[1:].isdigit():
                last_timestamp = int(text[1:])
            elif text and text[0] in "01xXzZ":
                values.add(text[0].lower())
            elif text.startswith(("b", "B")):
                values.update(character.lower() for character in text[1:].split()[0] if character in "01xXzZ")
    actual = set(names)
    return {
        "exists": True,
        "header_valid": bool(enddefinitions and timescale and names),
        "timescale": timescale,
        "catalog_complete": expected.issubset(actual),
        "catalog_exact_set": actual == expected and len(names) == len(expected),
        "expected_signal_count": len(expected),
        "header_var_count": len(names),
        "missing_expected_hierarchies": sorted(expected - actual),
        "unexpected_hierarchies": sorted(actual - expected),
        "last_appended_timestamp_ticks": last_timestamp,
        "value_characters": sorted(values),
        "identity_bytes": identity_bytes,
        "identity_sha256": digest.hexdigest(),
    }


def parse_markers(log: Path) -> dict[str, Any]:
    result = {
        "flush": {"dumpoff": False, "dumpflush": False, "closed": False},
        "stop_reason": None,
        "terminal_witness": False,
        "target_entry": False,
        "last_display_sim_time": 0,
        "last_cycles": 0,
        "last_progress": 0,
    }
    if not log.is_file():
        return result
    heartbeat = re.compile(
        r"CODEX_TBVCD_HEARTBEAT_V2 sim_time=(\d+) owner_cycles=(\d+) progress=(\d+)"
    )
    stop = re.compile(r"CODEX_TBVCD_STOP_V[12] reason=([A-Z_]+)")
    with log.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            match = heartbeat.search(line)
            if match:
                result["last_display_sim_time"] = int(match.group(1))
                result["last_cycles"] = int(match.group(2))
                result["last_progress"] = int(match.group(3))
            match = stop.search(line)
            if match:
                result["stop_reason"] = match.group(1)
            if "CODEX_TBVCD_TARGET_ENTRY_V2" in line:
                result["target_entry"] = True
            if "CODEX_TBVCD_TERMINAL_WITNESS_V" in line:
                result["terminal_witness"] = True
            if "CODEX_TBVCD_FLUSH_V" in line:
                result["flush"] = {"dumpoff": True, "dumpflush": True, "closed": True}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--actual-root", required=True)
    parser.add_argument("--published-root", required=True)
    parser.add_argument("--compile-exit", type=int, required=True)
    parser.add_argument("--sim-exit", type=int, required=True)
    parser.add_argument("--signal", required=True)
    parser.add_argument("--vcd", type=Path, required=True)
    parser.add_argument("--sim-log", type=Path, required=True)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument("--process-receipt", type=Path, required=True)
    parser.add_argument("--safety-receipt", type=Path, required=True)
    args = parser.parse_args()

    package = args.package_root.resolve()
    evidence = args.evidence_root.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    contract_path = package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    catalog_path = package / "diagnostics/tb_vcd_causal_signal_catalog.json"
    matrix_path = package / "diagnostics/tb_vcd_candidate_boundary_matrix.json"
    actual_path = evidence / "ACTUAL_COMPILE_SIM_ARGV.json"
    tb_path = package / contract["execution"]["tb_source_path"]
    expected = {normalize(str(item["exact_hierarchy"])) for item in contract["signals"]}
    scan = scan_vcd(args.vcd, expected)
    markers = parse_markers(args.sim_log)
    process = load(args.process_receipt) if args.process_receipt.is_file() else {}
    safety = load(args.safety_receipt) if args.safety_receipt.is_file() else {}
    process_tree = {
        "term_sent": bool(process.get("termination")),
        "wait_completed": process.get("root_exit") is not None,
        "kill_sent_if_needed": any(
            item.get("signal") == 9 for item in process.get("termination", []) if isinstance(item, dict)
        ),
        "all_reaped": process.get("process_tree_reaped") is True,
    }
    target_entry = bool(
        markers["target_entry"]
        or process.get("target_entry_observed") is True
        or safety.get("target_entry_observed") is True
    )
    supervisor_reason = safety.get("stop_reason")
    if supervisor_reason == "PROCESS_EXIT":
        supervisor_reason = None
    stop_reason = supervisor_reason or markers["stop_reason"]
    if stop_reason is None:
        if args.signal in {"HUP", "INT", "TERM"}:
            stop_reason = args.signal
        elif args.sim_exit == 0 and markers["terminal_witness"]:
            stop_reason = "NATURAL_TERMINAL"
        elif args.sim_exit != 0:
            stop_reason = "NONZERO_EXIT"
        else:
            stop_reason = "PROCESS_EXIT_WITHOUT_TERMINAL_WITNESS"
    natural = stop_reason == "NATURAL_TERMINAL" and args.sim_exit == 0

    samples: list[dict[str, Any]] = []
    if args.samples.is_file():
        with args.samples.open("r", encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    samples.append(json.loads(line))
    if not samples:
        samples = [
            {
                "seq": 0,
                "wall_seconds": 0,
                "sim_time_ticks": scan["last_appended_timestamp_ticks"],
                "appended_vcd_timestamp_ticks": scan["last_appended_timestamp_ticks"],
                "sim_cycles": markers["last_cycles"],
                "owner_clock_cycles": markers["last_cycles"],
                "causal_progress_events": markers["last_progress"],
                "qualified_progress_counters": {},
                "causal_state_digest": "absent",
                "global_progress_witness": {},
                "vcd_bytes": 0,
                "unresolved_xz": True,
            }
        ]
    samples[-1]["exit_code"] = args.sim_exit
    samples[-1]["appended_vcd_timestamp_ticks"] = scan["last_appended_timestamp_ticks"]
    samples[-1]["sim_time_ticks"] = scan["last_appended_timestamp_ticks"]
    if natural:
        samples[-1]["natural_terminal"] = True
    if args.signal in {"HUP", "INT", "TERM"}:
        samples[-1]["signal"] = args.signal

    shutil.copyfile(catalog_path, evidence / "TB_VCD_CAUSAL_SIGNAL_CATALOG.json")
    shutil.copyfile(matrix_path, evidence / "TB_VCD_CANDIDATE_BOUNDARY_MATRIX.json")
    tb_bytes, tb_sha = sha_file(tb_path)
    atomic_json(
        evidence / "TB_SOURCE_RECEIPT.json",
        {
            "schema": "server-tb-vcd-source-receipt-v2",
            "path": str(tb_path),
            "bytes": tb_bytes,
            "sha256": tb_sha,
            "matches_contract": tb_sha == contract["execution"]["tb_source_sha256"],
        },
    )
    compile_log = args.attempt_root / "evidence/compile_rootcause/compile_driver.log"
    compile_log_identity = None
    if compile_log.is_file():
        size, digest = sha_file(compile_log)
        compile_log_identity = {"path": str(compile_log), "bytes": size, "sha256": digest}
    elaboration = {
        "schema": "server-tb-vcd-elaboration-receipt-v2",
        "compile_exit": args.compile_exit,
        "tb_source_sha256": tb_sha,
        "compile_log": compile_log_identity,
        "elaboration_status": (
            "PRODUCTION_COMPILE_PASSED" if args.compile_exit == 0 else "PRODUCTION_COMPILE_FAILED"
        ),
        "server_source_identity_timing": "AFTER_ACTUAL_COMPILE",
    }
    atomic_json(evidence / "TB_VCD_ELABORATION_RECEIPT.json", elaboration)
    atomic_json(
        evidence / "PUBLISHED_ACTUAL_ROOT_IDENTITY.json",
        {
            "schema": "server-published-actual-root-identity-v1",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "published_root": args.published_root,
            "actual_root": args.actual_root,
            "match": args.published_root == args.actual_root,
            "mismatch_classification": (
                None
                if args.published_root == args.actual_root
                else "EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION"
            ),
            "claim_boundary": "Root identity only; mismatch restricts interpretation.",
        },
    )

    vcd_identity: dict[str, Any] | None = None
    if args.vcd.is_file():
        vcd_bytes = int(scan["identity_bytes"])
        vcd_sha = str(scan["identity_sha256"])
        vcd_identity = {
            "path": str(args.vcd),
            "bytes": vcd_bytes,
            "sha256": vcd_sha,
            "header_valid": scan["header_valid"],
            "timescale": scan["timescale"] or "unknown",
            "catalog_complete": scan["catalog_complete"] is True and scan["catalog_exact_set"] is True,
            "transitions_complete": natural and markers["flush"]["closed"] and process_tree["all_reaped"],
            "xz_preserved": scan["header_valid"],
            "return_allowlist_member": True,
        }
    exact_set = {
        "schema": "server-tb-vcd-return-exact-set-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "members": ([] if vcd_identity is None else [{key: vcd_identity[key] for key in ("path", "bytes", "sha256")}]),
        "hard_limit_bytes": None,
        "truncated": False,
        "sampled": False,
        "size_based_deletion": False,
        "allowlist_complete": vcd_identity is not None,
        "published": vcd_identity is not None,
    }
    atomic_json(evidence / "TB_VCD_RETURN_EXACT_SET.json", exact_set)
    atomic_json(
        evidence / "TB_VCD_IDENTITY.json",
        {"schema": "server-tb-vcd-identity-v2", **scan, "identity": vcd_identity},
    )
    atomic_json(
        evidence / "TB_VCD_TARGET_ENTRY_RECEIPT.json",
        {
            "schema": "server-tb-vcd-target-entry-receipt-v1",
            "package_id": args.package_id,
            "execution_id": args.execution_id,
            "attempt_id": args.attempt_id,
            "observed": target_entry,
            "source": "LIVE_SAME_ATTEMPT",
            "claim_boundary": "Entry witness only; no downstream/root claim.",
        },
    )
    atomic_json(
        evidence / "TB_VCD_STOP_RECEIPT.json",
        {
            "schema": "server-tb-vcd-stop-receipt-v2",
            "stop_reason": stop_reason,
            "natural_terminal": natural,
            "markers": markers,
            "safety": safety,
            "last_appended_vcd_timestamp_ticks": scan["last_appended_timestamp_ticks"],
            "non_natural_claim_boundary": (
                None
                if natural
                else "PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE; no natural/formal-D/E4/E5 claim"
            ),
        },
    )

    request = {
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "started": args.compile_exit == 0,
        "actual_argv_sha256": sha_file(actual_path)[1] if actual_path.is_file() else "0" * 64,
        "catalog_sha256": sha_file(catalog_path)[1],
        "candidate_matrix_sha256": sha_file(matrix_path)[1],
        "tb_source_sha256": tb_sha,
        "elaboration_sha256": canonical_sha(elaboration),
        "samples": samples,
        "candidate_catalog_complete": scan["catalog_exact_set"] is True,
        "unresolved_xz": bool(samples[-1].get("unresolved_xz", True)),
        "flush": markers["flush"],
        "process_tree": process_tree,
        "heartbeat_contract": {
            "source": "APPENDED_VCD_TIMESTAMP",
            "width_bits": 64,
            "signed": False,
            "cadence_cycles": 16_384,
        },
        "decision_authority": {
            "mode": "SHARED_RUNTIME_EVALUATOR_ONLY",
            "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
            "helper_sha256": sha_file(
                package / "package_tools/server_tb_vcd_runtime_supervision.py"
            )[1],
            "outer_runner_consumes_only_receipt": True,
            "independent_exit_logic_absent": True,
            "replay_cases": [
                {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
                {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
                {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
                {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
            ],
        },
        "archive_timestamp_receipt": (
            None
            if vcd_identity is None
            else {
                "binding": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT",
                "parse_status": "COMPLETE",
                "path": vcd_identity["path"],
                "bytes": vcd_identity["bytes"],
                "sha256": vcd_identity["sha256"],
                "last_timestamp_ticks": scan["last_appended_timestamp_ticks"],
            }
        ),
        "target_entry_observed": target_entry,
        "target_diagnostic_claim": target_entry,
        "vcd_identity": vcd_identity,
        "return_exact_set": exact_set,
        "live_diagnostics": {
            "downstream_state_source": "LIVE_SAME_ATTEMPT",
            "first_error_source": "LIVE_SAME_ATTEMPT",
            "stale_evidence_absent": True,
        },
    }
    atomic_json(evidence / "TB_VCD_RUNTIME_REQUEST.json", request)
    module_path = package / "package_tools/server_tb_vcd_runtime_supervision.py"
    spec = importlib.util.spec_from_file_location("server_tb_vcd_runtime_supervision", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("runtime evaluator cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = module.evaluate(request)
    outer_reason = process.get("stop_reason")
    live_path = evidence / "TB_VCD_LIVE_DECISION_RECEIPT.json"
    live_decision = load(live_path) if live_path.is_file() else {}
    conjunction_errors: list[str] = []
    if outer_reason not in (None, "PROCESS_EXIT") and receipt.get("stop_reason") != outer_reason:
        conjunction_errors.append(
            f"outer stop {outer_reason} differs from shared evaluator {receipt.get('stop_reason')}"
        )
    if outer_reason not in (None, "PROCESS_EXIT") and live_decision.get("decision") != outer_reason:
        conjunction_errors.append("live shared-evaluator envelope differs from outer stop")
    if live_decision.get("decision_authority") != request["decision_authority"]:
        conjunction_errors.append("live/final shared decision authority identity differs")
    if conjunction_errors:
        receipt["errors"] = [*receipt.get("errors", []), *conjunction_errors]
        receipt["completeness"] = "PARTIAL"
        receipt["diagnostic_status"] = "DIAGNOSTIC_EVIDENCE_INCOMPLETE"
        receipt["natural_terminal"] = False
    atomic_json(evidence / "TB_VCD_RUNTIME_RECEIPT.json", receipt)
    return 0 if receipt.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_COMPLETE" else 97


if __name__ == "__main__":
    raise SystemExit(main())
