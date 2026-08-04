from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
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
STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
    "op_tail_mul",
    "op_tail_round",
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
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            roots.add(pure.parts[0] if pure.parts else "")
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
            ):
                raise AnalysisError(f"unsafe member: {info.filename}")
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise AnalysisError(f"member outside bound root: {info.filename}")
            relative = info.filename[len(prefix) :]
            if relative in files:
                raise AnalysisError(f"duplicate member: {relative}")
            files[relative] = archive.read(info)
        if roots != {root_name}:
            raise AnalysisError(f"root exact-set differs: {sorted(roots)}")
    return files


def _epoch_map(payload: str) -> dict[str, int]:
    return {
        key.strip(): int(value.strip())
        for line in payload.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }


def _kv(line: str) -> dict[str, str]:
    return {
        key: value
        for key, value in re.findall(r"\b([a-zA-Z0-9_]+)=([^\s|]+)", line)
    }


def _int(value: str) -> int:
    return int(value, 0)


def analyze(return_zip: Path) -> dict[str, Any]:
    if sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        raise AnalysisError("source v16 ZIP identity differs")
    returned = read_zip(return_zip, RETURN_ROOT)
    source = read_zip(SOURCE_ZIP, SOURCE_ROOT)
    return_manifest = json.loads(returned["RETURN_MANIFEST.json"])
    source_manifest = json.loads(source["TEST_PACKAGE_MANIFEST.json"])
    returned_package_manifest = json.loads(
        returned["evidence/PACKAGE_MANIFEST.json"]
    )
    declared = {item["path"]: item for item in return_manifest["files"]}
    exact_set = set(returned) == set(declared) | {"RETURN_MANIFEST.json"}
    member_errors = [
        path
        for path, item in declared.items()
        if path not in returned
        or len(returned[path]) != int(item["size_bytes"])
        or sha256_bytes(returned[path]) != item["sha256"]
    ]
    allowlist = {
        item["target_path"] for item in source_manifest["return_allowlist"]
    }
    allowlist_valid = set(declared) <= allowlist
    manifest_equal = returned_package_manifest == source_manifest
    package_preflight = json.loads(returned["evidence/package_preflight.json"])
    installed_preflight = json.loads(
        returned["evidence/installed_preflight.json"]
    )
    compile_status = int(
        returned["evidence/compile_exit_status.txt"].decode().strip()
    )
    simulation_status = int(
        returned["evidence/simulation_exit_status.txt"].decode().strip()
    )
    signal = _kv(returned["evidence/signal_status.txt"].decode())["signal"]
    host = _epoch_map(returned["evidence/host_timing.txt"].decode())
    sim_wall_seconds = (
        host["final_epoch_ns"] - host["sim_start_epoch_ns"]
    ) / 1e9
    total_wall_seconds = (
        host["final_epoch_ns"] - host["package_start_epoch_ns"]
    ) / 1e9
    gate = json.loads(returned["evidence/SERVER_RESULT_GATE.json"])
    canonical = json.loads(
        returned["evidence/CANONICAL_PROGRESS_DECISION.json"]
    )
    canonical_reset_bug = any(
        int(window["end_active_cycles"]) < int(window["start_active_cycles"])
        for window in canonical.get("windows", [])
    )

    observer = returned["runs/return_observer.log"].decode(
        "utf-8", errors="replace"
    )
    stage_records: list[dict[str, Any]] = []
    active_stage = -1
    for line_number, line in enumerate(observer.splitlines(), start=1):
        match = re.match(r"^(\d+) \| ([A-Z0-9_]+) \|", line)
        if not match:
            continue
        timestamp = int(match.group(1))
        event = match.group(2)
        values = _kv(line)
        if event == "EXEC_START":
            active_stage += 1
            stage_records.append(
                {
                    "stage": STAGES[active_stage],
                    "exec_start_ps": timestamp,
                    "exec_start_line": line_number,
                    "exec_start_snapshot": values,
                    "comp_finish_ps": None,
                    "heartbeats": [],
                    "chains": [],
                    "deep_counts": [],
                    "sg_counts": [],
                    "internal_states": [],
                }
            )
        elif active_stage >= 0:
            record = stage_records[active_stage]
            if event == "COMP_FINISH":
                record["comp_finish_ps"] = timestamp
                record["comp_finish_line"] = line_number
                record["comp_finish_snapshot"] = values
            elif event == "HEARTBEAT":
                record["heartbeats"].append(
                    {"ps": timestamp, "line": line_number, **values}
                )
            elif event == "FIRST_REQUEST_CHAIN":
                record["chains"].append(
                    {"ps": timestamp, "line": line_number, **values}
                )
            elif event == "DEEP_COUNTS":
                record["deep_counts"].append(
                    {"ps": timestamp, "line": line_number, **values}
                )
            elif event == "SG_COUNTS":
                record["sg_counts"].append(
                    {"ps": timestamp, "line": line_number, **values}
                )
            elif event == "INTERNAL_STATE" and values.get("event") == "HEARTBEAT":
                record["internal_states"].append(
                    {"ps": timestamp, "line": line_number, **values}
                )

    sim_log = returned["runs/sim.log"].decode("utf-8", errors="replace")
    slice_starts = [
        int(value)
        for value in re.findall(r"\[(\d+)\] INFO: slice start", sim_log)
    ]
    interrupts = [
        int(value) for value in re.findall(r"Interrupt at time (\d+)", sim_log)
    ]
    if len(stage_records) != 3 or len(slice_starts) != 3 or not interrupts:
        raise AnalysisError("expected three started stages and final interrupt")
    stage3 = stage_records[2]
    heartbeats = stage3["heartbeats"]
    deep = stage3["deep_counts"]
    sg = stage3["sg_counts"]
    if len(heartbeats) < 2 or not deep or not sg:
        raise AnalysisError("stage3 periodic evidence absent")

    stable_fields = ("req", "rdata", "wdata")
    base_frozen = all(
        len({_int(item[field]) for item in heartbeats}) == 1
        for field in stable_fields
    )
    deep_fields = (
        "addr_enqueue",
        "req_hs",
        "meta",
        "consume",
        "buffer",
        "ga",
        "mse4_idx",
    )
    deep_frozen = all(
        len({_int(item[field]) for item in deep}) == 1 for field in deep_fields
    )
    sg_fields = (
        "ga_input",
        "ga_output",
        "mse4_req0",
        "mse4_req1",
        "mse4_wdata0",
        "mse4_wdata1",
        "mse4_outstanding0",
        "mse4_outstanding1",
    )
    sg_frozen = all(
        len({_int(item[field]) for item in sg}) == 1 for field in sg_fields
    )
    first_active = _int(heartbeats[0]["active_cycles"])
    last_active = _int(heartbeats[-1]["active_cycles"])
    stall_window = int(
        json.loads(returned["evidence/progress_contract.json"])[
            "stall_window_cycles"
        ]
    )
    complete_flat_windows = (last_active - first_active) // stall_window
    last_deep = {field: _int(deep[-1][field]) for field in deep_fields}
    last_sg = {field: _int(sg[-1][field]) for field in sg_fields}

    errors: list[str] = []
    if not exact_set:
        errors.append("return exact-set differs")
    if member_errors:
        errors.append("return member receipt differs")
    if not allowlist_valid:
        errors.append("return contains non-allowlisted target")
    if not manifest_equal:
        errors.append("returned/source package manifest differs")
    if package_preflight.get("valid") is not True:
        errors.append("package preflight invalid")
    if installed_preflight.get("valid") is not True:
        errors.append("installed preflight invalid")
    if compile_status != 0:
        errors.append("compile failed")

    return {
        "schema": "qlinearadd-node0007-dbuf-rule-v16-return2-analysis-v1",
        "valid_internal_return_evidence": not errors,
        "errors": errors,
        "return": {
            "path": str(return_zip),
            "size_bytes": return_zip.stat().st_size,
            "sha256": sha256_file(return_zip),
            "download_suffix_identity_effect": "NONE",
            "adjacent_sidecar_required": False,
            "transport_adjudication": (
                "USER_ATTESTED_NO_SIDECAR_CONTENT_NEUTRAL"
            ),
        },
        "source_package": {
            "path": str(SOURCE_ZIP),
            "sha256": SOURCE_SHA256,
            "manifest_byte_equal": manifest_equal,
        },
        "integrity": {
            "crc_valid": True,
            "single_exact_root": True,
            "root": RETURN_ROOT,
            "entry_count": len(returned),
            "return_exact_set": exact_set,
            "manifest_allowlist_subset": allowlist_valid,
            "member_receipt_errors": member_errors,
            "package_preflight_valid": package_preflight.get("valid") is True,
            "installed_preflight_valid": installed_preflight.get("valid")
            is True,
            "runtime_d_absent_package_and_install": (
                package_preflight.get("formal_readback_targets_absent") is True
                and installed_preflight.get("formal_readback_targets_absent")
                is True
            ),
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "signal": signal,
            "natural_terminal": False,
            "sim_wall_seconds": sim_wall_seconds,
            "total_wall_seconds": total_wall_seconds,
            "slice_start_ps": slice_starts,
            "interrupt_ps": interrupts[-1],
        },
        "stage_timeline": stage_records,
        "progress_adjudication": {
            "stage1_complete": stage_records[0]["comp_finish_ps"] is not None,
            "stage1_active_cycles": _int(
                stage_records[0]["comp_finish_snapshot"]["active_cycles"]
            ),
            "stage2_complete": stage_records[1]["comp_finish_ps"] is not None,
            "stage2_active_cycles": _int(
                stage_records[1]["comp_finish_snapshot"]["active_cycles"]
            ),
            "hang_stage": "op_relocation_pad",
            "stage3_base_qualified_frozen": base_frozen,
            "stage3_deep_downstream_frozen": deep_frozen,
            "stage3_sg_downstream_frozen": sg_frozen,
            "complete_flat_stall_windows": complete_flat_windows,
            "last_deep_snapshot": last_deep,
            "last_sg_snapshot": last_sg,
            "level_counters_excluded": [
                "buf5_wr",
                "buf5_rd",
                "mse0_in2_hs repeated without queue write",
                "mse4_in2_hs repeated without queue write",
            ],
            "decision": (
                "LONG_RUNNING_HANG_AT_STAGE3_WRITE_BACKEND_CHAIN"
            ),
        },
        "canonical_adjudication": {
            "returned_record": canonical,
            "execution_authoritative": False,
            "cross_stage_active_cycle_reset_detected": canonical_reset_bug,
            "reason": (
                "canonical compared samples across stage-local active-cycle "
                "resets; raw stage3 qualified downstream counters are used"
            ),
        },
        "formal_readback": {
            "expected": gate["expected_readback_count"],
            "observed": gate["observed_readback_count"],
            "missing": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "mismatch_zero_evaluable": False,
            "result_gate_all_terms_true": gate["result_gate_conjunction"][
                "all_terms_true"
            ],
        },
        "first_divergence": {
            "last_good": (
                "op_a_dequant and op_b_dequant natural completion; stage3 "
                "accepted finite read/address/GA/write-request activity"
            ),
            "first_bad": (
                "op_relocation_pad Buffer5/Buffer_AG/RD_Buffer_AG/"
                "WR_Data_Channel downstream chain freezes with "
                "MSE4 request=(2,1), wdata=(1,0), outstanding=(1,1)"
            ),
            "dynamic_only_unique_leaf": False,
        },
        "hang_root_cause": {
            "dynamic_boundary": "STAGE3_WRITE_BACKEND_CHAIN",
            "dynamic_only_root_cause": "NOT_UNIQUELY_IDENTIFIED",
            "old_d_buffer_fix_closed": False,
            "old_scalar_supply_formula_dynamically_refuted": True,
        },
        "evidence_gate": {
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": "INT/125, no natural terminal, 28/28 D missing",
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "config_numeric_analysis_repeated": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = analyze(args.return_zip.resolve())
    except Exception as error:
        print(f"QAdd v16 return2 analysis failed: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["valid_internal_return_evidence"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
