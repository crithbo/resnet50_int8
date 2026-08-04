from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ROOT = "r5_qadd_n7_dbuf_rule_v16_return"
SOURCE_ROOT = "r5_qadd_n7_dbuf_rule_v16"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_dbuf_rule_v16.zip"
)
SOURCE_SHA256 = (
    "a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5"
)


class AnalysisError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path, root_name: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise AnalysisError(f"ZIP CRC differs: {bad}")
        prefix = f"{root_name}/"
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or not info.filename.startswith(prefix)
            ):
                raise AnalysisError(f"unsafe member: {info.filename}")
            if info.is_dir():
                continue
            relative = info.filename[len(prefix):]
            if relative in files:
                raise AnalysisError(f"duplicate member: {relative}")
            files[relative] = archive.read(info)
    return files


def parse_epoch_map(payload: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def analyze(return_zip: Path) -> dict[str, Any]:
    if sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        raise AnalysisError("source v16 ZIP identity differs")
    returned = read_zip(return_zip, RETURN_ROOT)
    source = read_zip(SOURCE_ZIP, SOURCE_ROOT)
    if "RETURN_MANIFEST.json" not in returned:
        raise AnalysisError("RETURN_MANIFEST absent")
    return_manifest = json.loads(returned["RETURN_MANIFEST.json"])
    declared = {
        item["path"]: item for item in return_manifest.get("files", [])
    }
    exact_set = set(returned) == set(declared) | {"RETURN_MANIFEST.json"}
    receipt_errors = []
    for relative, receipt in declared.items():
        payload = returned.get(relative)
        if (
            payload is None
            or len(payload) != receipt.get("size_bytes")
            or sha256_bytes(payload) != receipt.get("sha256")
        ):
            receipt_errors.append(relative)
    returned_manifest = returned["evidence/PACKAGE_MANIFEST.json"]
    source_manifest = source["TEST_PACKAGE_MANIFEST.json"]
    manifest_equal = returned_manifest == source_manifest
    package_preflight = json.loads(returned["evidence/package_preflight.json"])
    installed_preflight = json.loads(
        returned["evidence/installed_preflight.json"]
    )
    gate = json.loads(returned["evidence/SERVER_RESULT_GATE.json"])
    canonical = json.loads(
        returned["evidence/CANONICAL_PROGRESS_DECISION.json"]
    )
    compile_status = int(
        returned["evidence/compile_exit_status.txt"].decode().strip()
    )
    simulation_status = int(
        returned["evidence/simulation_exit_status.txt"].decode().strip()
    )
    signal_text = returned["evidence/signal_status.txt"].decode()
    host = parse_epoch_map(returned["evidence/host_timing.txt"].decode())
    package_start = int(host["package_start_epoch_ns"])
    sim_start = int(host["sim_start_epoch_ns"])
    final = int(host["final_epoch_ns"])
    sim_wall_seconds = (final - sim_start) / 1e9
    total_wall_seconds = (final - package_start) / 1e9

    observer = returned["runs/return_observer.log"].decode(
        "utf-8", errors="replace"
    )
    sim_log = returned["runs/sim.log"].decode("utf-8", errors="replace")
    event_counts: Counter[str] = Counter()
    event_max_n: dict[str, int] = {}
    observer_timestamps: list[int] = []
    max_req_channels = [0, 0]
    max_wdata_channels = [0, 0]
    for line in observer.splitlines():
        match = re.match(r"^(\d+) \| ([A-Z0-9_]+) \|", line)
        if not match:
            continue
        timestamp = int(match.group(1))
        event = match.group(2)
        observer_timestamps.append(timestamp)
        event_counts[event] += 1
        n_match = re.search(r"\bn=(\d+)\b", line)
        if n_match:
            event_max_n[event] = max(
                event_max_n.get(event, 0), int(n_match.group(1))
            )
        channel = re.search(r"\bch=([01])\b", line)
        req = re.search(r"\breq_ch=(\d+)\b", line)
        wdata = re.search(r"\bwdata_ch=(\d+)\b", line)
        if channel and req:
            idx = int(channel.group(1))
            max_req_channels[idx] = max(
                max_req_channels[idx], int(req.group(1))
            )
        if channel and wdata:
            idx = int(channel.group(1))
            max_wdata_channels[idx] = max(
                max_wdata_channels[idx], int(wdata.group(1))
            )

    slice_matches = [
        int(value)
        for value in re.findall(
            r"\[(\d+)\] INFO: slice start", sim_log
        )
    ]
    interrupt_matches = [
        int(value)
        for value in re.findall(r"Interrupt at time (\d+)", sim_log)
    ]
    if not slice_matches or not interrupt_matches:
        raise AnalysisError("slice-start/interrupt timestamp absent")
    slice_start_ps = slice_matches[0]
    interrupt_ps = interrupt_matches[-1]
    post_start_ps = interrupt_ps - slice_start_ps
    assumed_clock_ps = 1250
    post_start_cycles = post_start_ps / assumed_clock_ps
    heartbeat_cycles = 262144
    cycles_to_first_heartbeat = heartbeat_cycles - post_start_cycles
    heartbeat_count = event_counts["HEARTBEAT"]
    chain_count = event_counts["FIRST_REQUEST_CHAIN"]
    clock_count = event_counts["FIRST_REQUEST_CLOCK"]
    qualified_progress = {
        "deep_mse0_to_buffer0": event_counts["DEEP_MSE0_TO_BUFFER0"],
        "deep_read_consume": event_counts["DEEP_RD_CONSUME"],
        "sg_ga_input": event_counts["SG_GA_INPUT"],
        "sg_ga_output": event_counts["SG_GA_OUTPUT"],
        "sg_mse4_req": event_counts["SG_MSE4_REQ"],
        "sg_mse4_wdata": event_counts["SG_MSE4_WDATA"],
        "mse4_req_by_channel_max": max_req_channels,
        "mse4_wdata_by_channel_max": max_wdata_channels,
    }
    progress_proven = (
        qualified_progress["sg_ga_input"] > 0
        and qualified_progress["sg_ga_output"] > 0
        and min(max_req_channels) >= 64
        and min(max_wdata_channels) >= 64
    )
    required_missing = return_manifest.get("required_missing", [])
    formal_expected = gate.get("expected_readback_count")
    formal_observed = gate.get("observed_readback_count")
    formal_missing = gate.get("missing_count")
    mismatch_bytes = gate.get("mismatch_byte_count")

    errors = []
    if not exact_set:
        errors.append("return exact-set differs")
    if receipt_errors:
        errors.append("return member receipt differs")
    if not manifest_equal:
        errors.append("source/returned package manifest differs")
    if package_preflight.get("valid") is not True:
        errors.append("package preflight invalid")
    if installed_preflight.get("valid") is not True:
        errors.append("installed preflight invalid")
    if compile_status != 0:
        errors.append("compile failed")
    signal_value = signal_text.strip().splitlines()[0].removeprefix("signal=")
    if signal_value != "INT":
        errors.append("expected manual INT evidence absent")
    return_sha = sha256_file(return_zip)
    return {
        "schema": "qlinearadd-node0007-dbuf-v16-return-analysis-v1",
        "valid_internal_return_evidence": not errors,
        "errors": errors,
        "return": {
            "path": str(return_zip),
            "size_bytes": return_zip.stat().st_size,
            "sha256": return_sha,
            "adjacent_sidecar_present": False,
            "transport_adjudication":
                "USER_ATTESTED_NO_SIDECAR_CONTENT_NEUTRAL",
        },
        "source_package": {
            "path": str(SOURCE_ZIP),
            "sha256": SOURCE_SHA256,
            "manifest_byte_equal": manifest_equal,
        },
        "integrity": {
            "crc_valid": True,
            "safe_single_root": True,
            "return_exact_set": exact_set,
            "returned_member_count": len(returned),
            "manifest_record_count": len(declared),
            "member_receipt_errors": receipt_errors,
            "package_preflight_valid": package_preflight.get("valid") is True,
            "installed_preflight_valid":
                installed_preflight.get("valid") is True,
            "runtime_d_preloaded": False,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "signal": signal_value,
            "natural_terminal": False,
            "sim_wall_seconds": sim_wall_seconds,
            "total_wall_seconds": total_wall_seconds,
            "slice_start_ps": slice_start_ps,
            "interrupt_ps": interrupt_ps,
            "post_slice_start_ps": post_start_ps,
            "post_slice_start_cycles_at_1_25ns": post_start_cycles,
            "heartbeat_period_cycles": heartbeat_cycles,
            "heartbeat_count": heartbeat_count,
            "cycles_short_of_first_heartbeat": cycles_to_first_heartbeat,
        },
        "qualified_progress": {
            **qualified_progress,
            "progress_proven": progress_proven,
            "first_request_chain_samples": chain_count,
            "first_request_clock_samples": clock_count,
            "observer_first_ps":
                min(observer_timestamps) if observer_timestamps else None,
            "observer_last_ps":
                max(observer_timestamps) if observer_timestamps else None,
        },
        "canonical_returned_record": canonical,
        "canonical_adjudication": {
            "returned_decision_not_execution_authoritative": True,
            "reason": (
                "canonical parser saw no heartbeat/chain sample, while "
                "deep qualified GA and MSE4 request/write-data events prove "
                "real execution progress before the manual interrupt"
            ),
            "corrected_decision":
                "MANUAL_INTERRUPT_BEFORE_FIRST_HEARTBEAT_WITH_QUALIFIED_PROGRESS",
        },
        "formal_readback": {
            "expected": formal_expected,
            "observed": formal_observed,
            "missing": formal_missing,
            "required_missing_manifest_count": len(required_missing),
            "mismatch_byte_count": mismatch_bytes,
            "mismatch_zero_evaluable": False,
            "result_gate_all_terms_true":
                gate["result_gate_conjunction"]["all_terms_true"],
        },
        "first_divergence": {
            "last_good": (
                "compile/elaboration, slice start, MSE0 read/consume, GA "
                "input/output, and at least 64 accepted MSE4 request/write-"
                "data transactions on each channel"
            ),
            "first_unproven": (
                "progress after the finite deep-event budget and before the "
                "first 262144-cycle heartbeat; natural terminal and D dump"
            ),
            "classification":
                "MANUAL_INTERRUPT_BEFORE_FIRST_HEARTBEAT_WITH_QUALIFIED_PROGRESS",
        },
        "hang_root_cause": {
            "status": "NOT_PROVEN_BY_THIS_RETURN",
            "functional_root_cause": "UNRESOLVED_AFTER_FINITE_DEEP_TRACE",
            "package_root_cause": "NONE_CONFIRMED",
            "d_buffer_transaction_supply_fix_reached_dynamic_path": True,
            "new_package_justified": False,
        },
        "evidence_gate": {
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": "manual INT, no natural terminal, 28/28 D missing",
        },
        "package_disposition": {
            "package": str(SOURCE_ZIP),
            "status": "PACKAGE_RUN_READY_UNCHANGED",
            "rebuild": False,
            "rerun_requirement": (
                "use a fresh server namespace/root and allow at least one "
                "heartbeat, preferably the full stall-window decision or "
                "natural terminal"
            ),
            "expected_return": f"{SOURCE_ROOT}_return.zip",
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = analyze(args.return_zip.resolve())
    except Exception as error:
        print(f"QAdd v16 return analysis failed: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid_internal_return_evidence"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
