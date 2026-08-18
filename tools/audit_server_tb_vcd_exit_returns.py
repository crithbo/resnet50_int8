#!/usr/bin/env python3
"""Read-only cross-family audit for TB-VCD runtime/exit returns."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


SCHEMA = "server-tb-vcd-cross-family-exit-audit-v1"


def sha_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


def _unique_entry(archive: zipfile.ZipFile, suffix: str) -> zipfile.ZipInfo:
    matches = [item for item in archive.infolist() if item.filename.endswith(suffix)]
    if len(matches) != 1:
        raise ValueError(f"expected one ZIP member ending {suffix!r}, observed {len(matches)}")
    return matches[0]


def _read_json(archive: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    value = json.loads(archive.read(_unique_entry(archive, suffix)).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{suffix}: JSON root must be an object")
    return value


def _scan_vcd(archive: zipfile.ZipFile, suffix: str) -> dict[str, Any]:
    entry = _unique_entry(archive, suffix)
    last_timestamp = -1
    timestamp_rows = 0
    var_rows = 0
    with archive.open(entry) as stream:
        for raw in stream:
            line = raw.strip()
            if line.startswith(b"#") and line[1:].isdigit():
                last_timestamp = int(line[1:])
                timestamp_rows += 1
            elif line.startswith(b"$var "):
                var_rows += 1
    return {
        "member": entry.filename,
        "bytes": entry.file_size,
        "crc32": f"{entry.CRC:08x}",
        "last_timestamp_ticks": last_timestamp,
        "timestamp_rows": timestamp_rows,
        "var_rows": var_rows,
    }


def classify_evidence(
    runtime: dict[str, Any], request: dict[str, Any], process: dict[str, Any],
    stop: dict[str, Any], sim_exit: dict[str, Any], vcd: dict[str, Any],
) -> dict[str, Any]:
    samples = request.get("samples") if isinstance(request.get("samples"), list) else []
    last_sample = samples[-1] if samples and isinstance(samples[-1], dict) else {}
    sampled_timestamp = last_sample.get("appended_vcd_timestamp_ticks", last_sample.get("sim_time_ticks", -1))
    runtime_timestamp = (runtime.get("time_event_counts") or {}).get("final_sim_time_ticks", -1)
    archive_timestamp = vcd.get("last_timestamp_ticks", -1)
    runtime_reason = runtime.get("stop_reason")
    outer_reason = process.get("stop_reason") or stop.get("stop_reason")
    signal = sim_exit.get("signal")
    natural = runtime.get("natural_terminal") is True or stop.get("natural_terminal") is True
    counters = runtime.get("final_counters") if isinstance(runtime.get("final_counters"), dict) else {}
    dump_control = runtime.get("dump_control") if isinstance(runtime.get("dump_control"), dict) else {}
    thresholds = runtime.get("thresholds") if isinstance(runtime.get("thresholds"), dict) else {}
    minimum_plateau = int(thresholds.get("plateau_dump_off_cycles", 4_194_304)) + int(thresholds.get("post_dump_grace_cycles", 262_144))
    timestamp_lag = max(int(runtime_timestamp), int(sampled_timestamp)) < int(archive_timestamp)
    finalization_pass = stop.get("pass")
    runtime_incomplete = runtime.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_INCOMPLETE" or runtime.get("completeness") == "PARTIAL"
    gaps: list[str] = []

    if natural:
        classification = "E_NORMAL_COMPLETION"
    elif signal not in (None, "", "NONE") and outer_reason not in {"SIM_TIME_FREEZE", "CAUSAL_PLATEAU"}:
        classification = "D_EXTERNAL_OR_MANUAL_TERMINATION"
    elif outer_reason == "SIM_TIME_FREEZE" or runtime_reason == "SIM_TIME_FREEZE":
        if dump_control.get("planned_dumpoff_observed") is True:
            classification = "B_DIFFERENT_SHARED_SUPERVISOR_DEFECT"
            gaps.append("PLANNED_DUMPOFF_VCD_STALL_MISCLASSIFIED_AS_FREEZE")
        elif timestamp_lag:
            classification = "A_QADD_V63_CLASS_FALSE_FREEZE"
            gaps.append("ARCHIVED_VCD_ADVANCED_BEYOND_SUPERVISOR_TIMESTAMP")
        else:
            classification = "C_GENUINE_NO_PROGRESS_PROTECTION"
    elif outer_reason == "CAUSAL_PLATEAU":
        premature = bool(
            runtime_reason != "CAUSAL_PLATEAU"
            or counters.get("dump_off_cycle") is None
            or int(counters.get("no_progress_cycles", 0)) < minimum_plateau
            or dump_control.get("planned_dumpoff_observed") is not True
            or dump_control.get("state_monotonic") is not True
            or dump_control.get("stop_marker_one_shot") is not True
            or dump_control.get("stop_marker_count") != 1
        )
        if premature:
            classification = "B_DIFFERENT_SHARED_SUPERVISOR_DEFECT"
            gaps.append("OUTER_PLATEAU_STOP_DIVERGED_FROM_SHARED_EVALUATOR")
        else:
            classification = "C_GENUINE_NO_PROGRESS_PROTECTION"
    else:
        classification = "B_DIFFERENT_SHARED_SUPERVISOR_DEFECT"
        gaps.append("UNCLASSIFIED_NON_NATURAL_EXIT")

    if finalization_pass is True and runtime_incomplete:
        gaps.append("FINALIZATION_PASS_CONTRADICTS_INCOMPLETE_RUNTIME")
    process_tree = runtime.get("process_tree") if isinstance(runtime.get("process_tree"), dict) else {}
    if process_tree.get("all_reaped") is not True or process.get("process_tree_reaped") is False:
        gaps.append("PROCESS_TREE_NOT_REAPED")
    return {
        "classification": classification,
        "runtime_stop_reason": runtime_reason,
        "outer_stop_reason": outer_reason,
        "natural_terminal": natural,
        "sampled_timestamp_ticks": sampled_timestamp,
        "runtime_final_timestamp_ticks": runtime_timestamp,
        "archived_vcd_last_timestamp_ticks": archive_timestamp,
        "archived_timestamp_ahead": timestamp_lag,
        "no_progress_cycles": counters.get("no_progress_cycles"),
        "minimum_full_plateau_cycles": minimum_plateau,
        "dump_off_cycle": counters.get("dump_off_cycle"),
        "dump_control": dump_control,
        "runtime_diagnostic_status": runtime.get("diagnostic_status"),
        "runtime_completeness": runtime.get("completeness"),
        "finalization_pass": finalization_pass,
        "process_tree_reaped": process_tree.get("all_reaped") is True and process.get("process_tree_reaped") is not False,
        "shared_findings": sorted(set(gaps)),
    }


def audit_case(case: dict[str, Any]) -> dict[str, Any]:
    path = Path(case["zip_path"])
    size, digest = sha_file(path)
    if size != case.get("zip_bytes") or digest != case.get("zip_sha256"):
        raise ValueError(f"{case.get('case_id')}: return ZIP identity drift")
    suffixes = case["members"]
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"{case.get('case_id')}: bad ZIP member {bad}")
        runtime = _read_json(archive, suffixes["runtime"])
        request = _read_json(archive, suffixes["request"])
        process = _read_json(archive, suffixes["process"])
        stop = _read_json(archive, suffixes["stop"])
        sim_exit = _read_json(archive, suffixes["sim_exit"])
        vcd = _scan_vcd(archive, suffixes["vcd"])
    result = classify_evidence(runtime, request, process, stop, sim_exit, vcd)
    result.update({
        "case_id": case["case_id"], "family": case["family"],
        "return_zip": {"path": path.as_posix(), "bytes": size, "sha256": digest},
        "vcd": vcd,
    })
    return result


def audit(request: dict[str, Any]) -> dict[str, Any]:
    cases = [audit_case(item) for item in request.get("cases", [])]
    return {
        "schema": SCHEMA,
        "pass": len(cases) == 3,
        "cases": cases,
        "classification_counts": {
            key: sum(item["classification"] == key for item in cases)
            for key in (
                "A_QADD_V63_CLASS_FALSE_FREEZE", "B_DIFFERENT_SHARED_SUPERVISOR_DEFECT",
                "C_GENUINE_NO_PROGRESS_PROTECTION", "D_EXTERNAL_OR_MANUAL_TERMINATION", "E_NORMAL_COMPLETION",
            )
        },
        "rule_disposition": "EXISTING_OPTIONAL_VCD_RULE_IMPLEMENTATION_DELTA_REQUIRED",
        "shared_delta": [
            "outer runner consumes only the shared evaluator decision",
            "exact packaged helper replays advancing timestamp, suspected-only plateau, full plateau and true freeze cases",
            "quiescent archived VCD SHA/bytes/last timestamp exactly bind the final runtime timestamp",
            "incomplete runtime or unreaped process tree cannot coexist with finalization pass",
        ],
        "claim_boundary": "Exit-mechanism comparison only; family signal/root diagnosis remains with each family owner.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text(encoding="utf-8"))
    report = audit(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
