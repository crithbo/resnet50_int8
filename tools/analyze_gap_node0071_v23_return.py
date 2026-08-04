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
RETURN_SHA256 = (
    "b00dd10f4710509a5a7701182a6fdd09309e5e50a3a9debbadd44a688612b0a6"
)
RETURN_SIZE = 112916
SOURCE_SHA256 = (
    "07ea69a9b647542751c3e47b192d5d1ddb497dad97801e75c9fe002331244c19"
)
SOURCE_SIZE = 1810719
IDENTITY = "r5_n71_gap_v23_rd_data_vld_path_rulefix"
RETURN_ROOT = f"{IDENTITY}_return"
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def object_json(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root is not an object")
    return value


def last_line(text: str, marker: str) -> str | None:
    matches = [line for line in text.splitlines() if marker in line]
    return matches[-1] if matches else None


def pair(line: str | None, key: str) -> tuple[int, int] | None:
    if line is None:
        return None
    match = re.search(rf"\b{re.escape(key)}=(\d+)/(\d+)\b", line)
    return (int(match.group(1)), int(match.group(2))) if match else None


def quad(line: str | None, key: str) -> tuple[int, int, int, int] | None:
    if line is None:
        return None
    match = re.search(
        rf"\b{re.escape(key)}=(\d+),(\d+)/(\d+),(\d+)\b", line
    )
    return tuple(int(item) for item in match.groups()) if match else None


def parse_events(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if "RD_DATA_VLD_PATH_EVENT_V1" not in line:
            continue
        values = {
            key: value
            for key, value in re.findall(r"(\w+)=([^\s]+)", line)
        }
        records.append(
            {
                "time_ps": int(line.split("|", 1)[0].strip()),
                "n": int(values["n"]),
                "mse": int(values["mse"]),
                "sg_edge": int(values["sg_edge"]),
                "req_hs": int(values["req_hs"]),
                "mem_vld": int(values["mem_vld"], 16),
                "mem_ready": int(values["mem_ready"], 16),
                "ib_wr": int(values["ib_wr"], 16),
                "ib_rd": int(values["ib_rd"], 16),
                "prep_wr": int(values["prep_wr"]),
                "prep_rd": int(values["prep_rd"]),
                "prep_count": int(values["prep_count"]),
                "queue_tsf": (
                    None if values["queue_tsf"] == "X"
                    else int(values["queue_tsf"])
                ),
                "spatial": int(values["spatial"]),
                "data_vld": int(values["data_vld"]),
            }
        )
    return records


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    errors: list[str] = []
    if return_zip.stat().st_size != RETURN_SIZE:
        errors.append("return size differs")
    if sha256_file(return_zip) != RETURN_SHA256:
        errors.append("return SHA256 differs")
    if source_zip.stat().st_size != SOURCE_SIZE:
        errors.append("source size differs")
    if sha256_file(source_zip) != SOURCE_SHA256:
        errors.append("source SHA256 differs")

    with zipfile.ZipFile(source_zip) as source:
        source_manifest_bytes = source.read(
            f"{IDENTITY}/TEST_PACKAGE_MANIFEST.json"
        )
        source_manifest = object_json(source_manifest_bytes)
        source_sca = source.read(f"{IDENTITY}/workload/sca_cfg.json")
        source_sca_d = source.read(f"{IDENTITY}/workload/sca_cfg_D.json")

    with zipfile.ZipFile(return_zip) as archive:
        bad_crc = archive.testzip()
        infos = archive.infolist()
        names = [item.filename for item in infos]
        duplicates = sorted(
            name for name in set(names) if names.count(name) != 1
        )
        unsafe: list[str] = []
        symlinks: list[str] = []
        roots: set[str] = set()
        for item in infos:
            path = PurePosixPath(item.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in item.filename
                or not path.parts
            ):
                unsafe.append(item.filename)
            else:
                roots.add(path.parts[0])
            mode = (item.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(item.filename)
        if bad_crc is not None:
            errors.append(f"CRC failed at {bad_crc}")
        if duplicates:
            errors.append("duplicate ZIP entries")
        if unsafe:
            errors.append("unsafe ZIP paths")
        if symlinks:
            errors.append("symlink ZIP entries")
        if roots != {RETURN_ROOT}:
            errors.append("return root differs")

        def read(relative: str) -> bytes:
            return archive.read(f"{RETURN_ROOT}/{relative}")

        return_manifest = object_json(read("RETURN_MANIFEST.json"))
        returned_manifest_bytes = read("evidence/PACKAGE_MANIFEST.json")
        returned_manifest = object_json(returned_manifest_bytes)
        gate = object_json(read("evidence/SERVER_RESULT_GATE.json"))
        canonical = object_json(read("evidence/canonical_decision.json"))
        canonical_self_test = object_json(
            read("evidence/canonical_decision_self_test.json")
        )
        preflight = object_json(read("evidence/installed_preflight.json"))
        observer_precompile = object_json(
            read("evidence/observer_precompile.json")
        )
        observer = read("runs/return_observer.log").decode(
            "utf-8", errors="replace"
        )
        compile_log = read("logs/compile.log").decode(
            "utf-8", errors="replace"
        )
        actual_compile = read("evidence/actual_compile_argv.txt").decode()
        actual_sim = read("evidence/actual_simulator_argv.txt").decode()
        binding = read("evidence/observer_binding.txt").decode()
        signal_status = read("evidence/signal_status.txt").decode()
        host_timing = read("evidence/host_timing.txt").decode()
        compile_status = int(
            read("evidence/compile_exit_status.txt").decode().strip()
        )
        simulation_status = int(
            read("evidence/simulation_exit_status.txt").decode().strip()
        )
        runner_status = int(
            read("evidence/runner_exit_status.txt").decode().strip()
        )

        listed = return_manifest.get("files", [])
        listed_paths = [item.get("path") for item in listed]
        expected_set = {
            f"{RETURN_ROOT}/RETURN_MANIFEST.json",
            *(
                f"{RETURN_ROOT}/{path}"
                for path in listed_paths
                if isinstance(path, str)
            ),
        }
        actual_set = set(names)
        if actual_set != expected_set:
            errors.append("RETURN_MANIFEST exact set differs")
        for item in listed:
            path = item.get("path")
            if not isinstance(path, str):
                errors.append("return file path record malformed")
                continue
            data = read(path)
            if len(data) != item.get("size_bytes"):
                errors.append(f"return size receipt differs: {path}")
            if sha256_bytes(data) != item.get("sha256"):
                errors.append(f"return SHA receipt differs: {path}")

        allowlist = {
            item["target_path"]: item
            for item in source_manifest["return_allowlist"]
        }
        outside_allowlist = [
            path for path in listed_paths if path not in allowlist
        ]
        if outside_allowlist:
            errors.append("returned file outside source allowlist")
        required_missing = sorted(return_manifest.get("required_missing", []))
        expected_missing = sorted(
            path for path, item in allowlist.items()
            if item["required"] and path not in listed_paths
        )
        if required_missing != expected_missing:
            errors.append("required_missing differs from source allowlist")
        if returned_manifest_bytes != source_manifest_bytes:
            errors.append("returned package manifest differs from source")
        sca_equal = read("config/sca_cfg.json") == source_sca
        sca_d_equal = read("config/sca_cfg_D.json") == source_sca_d
        if not sca_equal:
            errors.append("returned SCA differs from source")
        if not sca_d_equal:
            errors.append("returned SCA_D differs from source")

    rd_counts = last_line(observer, "RD_DATA_VLD_PATH_COUNTS_V1")
    rd_state = last_line(observer, "RD_DATA_VLD_PATH_STATE_V1")
    rd_witness = last_line(observer, "RD_DATA_VLD_PATH_WITNESS_V1")
    bp_counts = last_line(observer, "BP_PRE_FACTOR_COUNTS_V1")
    sg_counts = last_line(observer, "SG_COUNTS")
    events = parse_events(observer)
    mse0_events = [item for item in events if item["mse"] == 0]
    mse3_events = [item for item in events if item["mse"] == 3]
    mse3_prep_events = [
        item for item in mse3_events if item["prep_wr"] == 1
    ]
    mse0_valid_events = [
        item for item in mse0_events if item["data_vld"] == 1
    ]
    mse3_valid_events = [
        item for item in mse3_events if item["data_vld"] == 1
    ]
    timing = {
        key: int(value)
        for key, value in re.findall(r"(\w+)=([0-9]+)", host_timing)
    }
    result_terms = gate["result_gate_conjunction"]
    e3 = (
        compile_status == 0
        and simulation_status == 0
        and result_terms.get("natural_completion") is True
    )
    e4 = e3 and result_terms.get("all_terms_true") is True

    return {
        "schema": "gap-node0071-v23-return-analysis-v1",
        "status": "ADJUDICATED_SUCCESSOR_REQUIRED",
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "return_analysis": {
            "return_path": str(return_zip),
            "return_size_bytes": return_zip.stat().st_size,
            "return_sha256": sha256_file(return_zip),
            "adjacent_sidecar_present": False,
            "transport_policy":
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            "crc_valid": bad_crc is None,
            "single_root": roots == {RETURN_ROOT},
            "path_safe": not unsafe,
            "duplicate_free": not duplicates,
            "symlink_free": not symlinks,
            "return_manifest_exact_set": actual_set == expected_set,
            "allowlist_only": not outside_allowlist,
            "required_missing_exact": required_missing == expected_missing,
            "returned_file_receipts_valid": not any(
                "return size receipt" in item
                or "return SHA receipt" in item
                for item in errors
            ),
        },
        "source_binding": {
            "source_path": str(source_zip),
            "source_size_bytes": source_zip.stat().st_size,
            "source_sha256": sha256_file(source_zip),
            "returned_manifest_byte_equal": (
                returned_manifest_bytes == source_manifest_bytes
            ),
            "package_identity": returned_manifest.get("package_name"),
            "install_identity": returned_manifest.get("install_name"),
            "run_identity": returned_manifest.get("run_name"),
            "return_identity": returned_manifest.get("return_name"),
            "sca_byte_equal": sca_equal,
            "sca_d_byte_equal": sca_d_equal,
        },
        "runtime_binding": {
            "installed_preflight_valid": preflight.get("valid") is True,
            "runtime_d_initially_absent": preflight.get(
                "formal_readback_targets_absent"
            ) is True,
            "observer_precompile_valid":
                observer_precompile.get("valid") is True,
            "observer_source_identity_match":
                observer_precompile.get("identity_match") is True,
            "compile_argv": actual_compile.strip(),
            "simulator_argv": actual_sim.strip(),
            "rd_path_enable_in_argv":
                "+RETURN_OBS_RD_DATA_PATH" in actual_sim,
            "rd_path_limit_in_argv":
                "+RETURN_OBS_RD_DATA_PATH_LIMIT=512" in actual_sim,
            "time0_marker":
                "rd_data_path=1 rd_data_path_limit=512" in observer,
            "returned_binding":
                "rd_data_vld_path_enabled=true" in binding
                and "rd_data_vld_path_records_returned=true" in binding,
            "compile_log_nonempty": bool(compile_log),
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": runner_status,
            "signal": "INT" if "signal=INT" in signal_status else "UNKNOWN",
            "natural_terminal": canonical.get("natural_terminal") is True,
            "ordered_stage_scope": canonical.get("final_stage_scope"),
            "canonical_decision": canonical.get("decision"),
            "canonical_self_test_pass":
                canonical_self_test.get("status") == "PASS",
            "host_wall_time_seconds": (
                timing.get("final_epoch_ns", 0)
                - timing.get("sim_start_epoch_ns", 0)
            ) / 1_000_000_000,
        },
        "formal_d": {
            "expected_count": gate.get("readback_count"),
            "present_count": (
                gate.get("readback_count", 0) - gate.get("missing_count", 0)
            ),
            "missing_count": gate.get("missing_count"),
            "mismatch_byte_count": gate.get("mismatch_byte_count"),
            "mismatch_zero_evaluable": (
                gate.get("missing_count") == 0
                and result_terms.get("formal_readback_exact_set_complete")
                is True
            ),
            "exact_set_complete":
                result_terms.get("formal_readback_exact_set_complete"),
            "server_result_gate_all_terms_true":
                result_terms.get("all_terms_true"),
            "server_result_status": gate.get("status"),
        },
        "qualified_path_evidence": {
            "final_rd_counts_record": rd_counts,
            "final_rd_state_record": rd_state,
            "final_rd_witness_record": rd_witness,
            "final_bp_counts_record": bp_counts,
            "final_sg_counts_record": sg_counts,
            "request_hs_mse0_mse3": pair(rd_counts, "req_hs"),
            "rdata_hs_mse0_ch0_ch1_mse3_ch0_ch1":
                quad(rd_counts, "rdata_hs"),
            "inbuffer_write_mse0_ch0_ch1_mse3_ch0_ch1":
                quad(rd_counts, "ib_wr"),
            "inbuffer_read_mse0_ch0_ch1_mse3_ch0_ch1":
                quad(rd_counts, "ib_rd"),
            "prepared_write_mse0_mse3": pair(rd_counts, "prep_wr"),
            "prepared_read_mse0_mse3": pair(rd_counts, "prep_rd"),
            "event_record_count": len(events),
            "mse0_data_vld_event_count": len(mse0_valid_events),
            "mse3_data_vld_event_count": len(mse3_valid_events),
            "mse3_prepared_write_event_count": len(mse3_prep_events),
            "mse3_prepared_write_event_counts_all_zero": (
                bool(mse3_prep_events)
                and all(item["prep_count"] == 0 for item in mse3_prep_events)
            ),
            "first_mse3_prepared_write": (
                mse3_prep_events[0] if mse3_prep_events else None
            ),
            "last_mse3_prepared_write": (
                mse3_prep_events[-1] if mse3_prep_events else None
            ),
            "stable_levels_count_as_progress": False,
        },
        "last_proven_good": (
            "MSE0 and MSE3 each accepted five memory-return beats on each "
            "memory channel; both reached prepared-data writes (MSE0=6, "
            "MSE3=10); frozen sum_s1 GA input/output remained 32/32 and "
            "MSE4 write-data remained 8/8"
        ),
        "first_divergence": (
            "MSE3_PREPARED_DATA_COUNT_NOT_RETAINED_AFTER_QUALIFIED_WRITES"
        ),
        "hang_root_cause": (
            "LONG_RUNNING_HANG_AT_MSE3_PREPARED_DATA_COUNT_UPDATE_"
            "PENDING_LOCAL_RESET_OR_UPDATE_CAUSE"
        ),
        "root_cause_scope": {
            "excluded": [
                "memory return absent",
                "MSE3 RD inbuffer read absent",
                "MSE3 prepared-data write absent",
                "MSE0 prepared-data count equation globally broken",
            ],
            "remaining": [
                "MSE3 local slice_rst/rst_n clear active around updates",
                "MSE3 counter update equation input/priority anomaly",
                "observer XMR identity/sampling inconsistency",
            ],
            "unique_functional_root": False,
        },
        "e3_e4_e5": {
            "E3": e3,
            "E4": e4,
            "E5": False,
            "reason": (
                "INT/125 is not a natural terminal; all 48 formal D targets "
                "are missing, so mismatch=0 is unevaluable and the joint "
                "server gate is false"
            ),
        },
        "successor": {
            "required": True,
            "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "boundary": (
                "MSE0/MSE3 prepared_data_wr/rd -> local reset/clear and "
                "count-update priority -> prepared_data_cnt/data_vld"
            ),
            "config_change": False,
            "timeout_change": False,
        },
        "numeric_sum_tail_workload_config_golden_repeated": False,
        "errors": errors,
        "valid_receipt": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve(), args.source_zip.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
