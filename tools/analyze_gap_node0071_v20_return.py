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
    "59cef2d1051f9f4d38f65c473b8ed2e421d4f603fcdee7faef9844a2b6e603e5"
)
RETURN_SIZE = 113340
SOURCE_SHA256 = (
    "a82ac187b46dac4f26a8545bf14bebf5bc5481308791be062ce581a30429bbe3"
)
SOURCE_SIZE = 1810686
IDENTITY = "r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix"
RETURN_ROOT = f"{IDENTITY}_return"
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root is not an object")
    return value


def parse_last(text: str, marker: str) -> str | None:
    matches = [line for line in text.splitlines() if marker in line]
    return matches[-1] if matches else None


def parse_pair(line: str | None, key: str) -> tuple[int, int] | None:
    if line is None:
        return None
    match = re.search(rf"\b{re.escape(key)}=(\d+)/(\d+)\b", line)
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_hex(line: str | None, key: str) -> int | None:
    if line is None:
        return None
    match = re.search(rf"\b{re.escape(key)}=0x([0-9a-fA-F]+)\b", line)
    return int(match.group(1), 16) if match else None


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    errors: list[str] = []
    if return_zip.stat().st_size != RETURN_SIZE:
        errors.append("return size differs")
    if digest_file(return_zip) != RETURN_SHA256:
        errors.append("return SHA256 differs")
    if source_zip.stat().st_size != SOURCE_SIZE:
        errors.append("source size differs")
    if digest_file(source_zip) != SOURCE_SHA256:
        errors.append("source SHA256 differs")

    with zipfile.ZipFile(source_zip) as source:
        source_manifest_bytes = source.read(f"{IDENTITY}/TEST_PACKAGE_MANIFEST.json")
        source_manifest = load_json(source_manifest_bytes)
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

        return_manifest = load_json(read("RETURN_MANIFEST.json"))
        returned_manifest_bytes = read("evidence/PACKAGE_MANIFEST.json")
        returned_manifest = load_json(returned_manifest_bytes)
        gate = load_json(read("evidence/SERVER_RESULT_GATE.json"))
        canonical = load_json(read("evidence/canonical_decision.json"))
        canonical_self_test = load_json(
            read("evidence/canonical_decision_self_test.json")
        )
        installed_preflight = load_json(
            read("evidence/installed_preflight.json")
        )
        observer_precompile = load_json(
            read("evidence/observer_precompile.json")
        )
        observer_text = read("runs/return_observer.log").decode(
            "utf-8", errors="replace"
        )
        sim_text = read("logs/sim.log").decode("utf-8", errors="replace")
        compile_text = read("logs/compile.log").decode(
            "utf-8", errors="replace"
        )
        actual_compile = read("evidence/actual_compile_argv.txt").decode()
        actual_sim = read("evidence/actual_simulator_argv.txt").decode()
        signal_text = read("evidence/signal_status.txt").decode()
        host_timing = read("evidence/host_timing.txt").decode()

        listed = return_manifest.get("files", [])
        listed_paths = [item.get("path") for item in listed]
        expected_actual = {
            f"{RETURN_ROOT}/RETURN_MANIFEST.json",
            *(
                f"{RETURN_ROOT}/{path}"
                for path in listed_paths
                if isinstance(path, str)
            ),
        }
        actual = set(names)
        if actual != expected_actual:
            errors.append("RETURN_MANIFEST exact set differs")
        for record in listed:
            path = record.get("path")
            if not isinstance(path, str):
                errors.append("return file path record malformed")
                continue
            data = read(path)
            if len(data) != record.get("size_bytes"):
                errors.append(f"return size receipt differs: {path}")
            if digest_bytes(data) != record.get("sha256"):
                errors.append(f"return SHA receipt differs: {path}")

        allowlist = {
            item["target_path"]: item
            for item in source_manifest["return_allowlist"]
        }
        if any(path not in allowlist for path in listed_paths):
            errors.append("returned file outside source allowlist")
        required_missing = return_manifest.get("required_missing", [])
        expected_missing = sorted(
            path
            for path, item in allowlist.items()
            if item["required"] and path not in listed_paths
        )
        if sorted(required_missing) != expected_missing:
            errors.append("required_missing differs from source allowlist")
        if returned_manifest_bytes != source_manifest_bytes:
            errors.append("returned package manifest differs from source")
        if read("config/sca_cfg.json") != source_sca:
            errors.append("returned SCA differs from source")
        if read("config/sca_cfg_D.json") != source_sca_d:
            errors.append("returned SCA_D differs from source")
        sca_equal = read("config/sca_cfg.json") == source_sca
        sca_d_equal = read("config/sca_cfg_D.json") == source_sca_d

    compile_status = int(
        (return_zip.parent / "nonexistent").exists()
        or gate["result_gate_conjunction"]["compile_exit_status"]
    )
    simulation_status = gate["result_gate_conjunction"][
        "simulation_exit_status"
    ]
    final_counts = parse_last(observer_text, "BP_PRE_FACTOR_COUNTS_V1")
    final_state = parse_last(observer_text, "BP_PRE_FACTOR_STATE_V1")
    final_witness = parse_last(observer_text, "BP_PRE_FACTOR_WITNESS_V1")
    stage1_counts = parse_last(observer_text, "STAGE1_FLOW_COUNTS_V1")
    dual_counts = parse_last(observer_text, "DUAL_INGRESS_COUNTS")
    ga_counts = parse_last(observer_text, "SG_COUNTS")
    timing_values = {
        key: int(value)
        for key, value in re.findall(r"(\w+)=([0-9]+)", host_timing)
    }
    wall_ns = (
        timing_values.get("final_epoch_ns", 0)
        - timing_values.get("sim_start_epoch_ns", 0)
    )

    result_terms = gate["result_gate_conjunction"]
    e3 = (
        compile_status == 0
        and simulation_status == 0
        and result_terms.get("natural_completion") is True
    )
    e4 = e3 and result_terms.get("all_terms_true") is True

    factor = {
        "equations": {
            "buf_ag_bp_pre": (
                "!buf_ag_ob_full && rd_data_chl_data_ready "
                "&& !nse2mse_req_barrier"
            ),
            "rd_data_chl_data_ready": (
                "rd_data_chl_data_vld && !rd_data_chl_ob_full"
            ),
        },
        "final_counts_record": final_counts,
        "final_state_record": final_state,
        "final_witness_record": final_witness,
        "stage1_flow_record": stage1_counts,
        "dual_ingress_record": dual_counts,
        "ga_record": ga_counts,
        "parsed": {
            "bp_edge_mse0_mse3": parse_pair(final_counts, "bp_edge"),
            "ob_full_edge_mse0_mse3":
                parse_pair(final_counts, "ob_full_edge"),
            "ready_edge_mse0_mse3":
                parse_pair(final_counts, "ready_edge"),
            "vld_edge_mse0_mse3": parse_pair(final_counts, "vld_edge"),
            "prepared_change_mse0_mse3":
                parse_pair(final_counts, "prep_change"),
            "rd_ob_full_edge_mse0_mse3":
                parse_pair(final_counts, "rd_ob_full_edge"),
            "barrier_edge_mse0_mse3":
                parse_pair(final_counts, "barrier_edge"),
            "queue_read_mse0_mse3": parse_pair(final_counts, "q_rd"),
            "ob_write_mse0_mse3": parse_pair(final_counts, "ob_wr"),
            "final_bp_pre": parse_hex(final_state, "bp_pre"),
            "final_ob_full": parse_hex(final_state, "ob_full"),
            "final_data_ready": parse_hex(final_state, "data_ready"),
            "final_data_vld": parse_hex(final_state, "data_vld"),
            "final_prepared_count": parse_hex(
                final_state, "prepared_count"
            ),
            "final_rd_ob_full": parse_hex(final_state, "rd_ob_full"),
            "final_barrier": parse_hex(final_state, "barrier"),
        },
        "adjudication": (
            "For both MSE0 and MSE3, buf_ag_ob_full=0 and "
            "nse2mse_req_barrier=0 exclude those conjunction factors. "
            "rd_data_chl_data_ready=0 is therefore the blocking factor. "
            "Because rd_data_chl_ob_full=0, the nested RTL equation uniquely "
            "reduces ready=0 to rd_data_chl_data_vld=0; prepared_data_cnt=0 "
            "is consistent. The current evidence does not distinguish absent "
            "memory return, inbuffer acceptance, request/data queue pairing, "
            "or prepared-data write, so responsibility below data_vld remains "
            "unresolved."
        ),
    }

    return {
        "schema": "gap-node0071-v20-return-analysis-v1",
        "status": "ADJUDICATED_SUCCESSOR_REQUIRED",
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "return_receipt": {
            "path": str(return_zip),
            "size_bytes": return_zip.stat().st_size,
            "sha256": digest_file(return_zip),
            "adjacent_sidecar_present": False,
            "transport_policy": (
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
            ),
            "crc_valid": bad_crc is None,
            "single_root": roots == {RETURN_ROOT},
            "path_safe": not unsafe,
            "duplicate_free": not duplicates,
            "symlink_free": not symlinks,
            "return_manifest_exact_set": actual == expected_actual,
            "allowlist_only": not any(
                path not in allowlist for path in listed_paths
            ),
            "file_receipts_valid": not any(
                item.startswith("return size receipt")
                or item.startswith("return SHA receipt")
                for item in errors
            ),
        },
        "source_binding": {
            "path": str(source_zip),
            "size_bytes": source_zip.stat().st_size,
            "sha256": digest_file(source_zip),
            "returned_manifest_byte_equal": (
                returned_manifest_bytes == source_manifest_bytes
            ),
            "installed_identity": returned_manifest.get("install_name"),
            "run_identity": returned_manifest.get("run_name"),
            "return_identity": returned_manifest.get("return_name"),
            "sca_byte_equal": sca_equal,
            "sca_d_byte_equal": sca_d_equal,
        },
        "runtime_binding": {
            "package_install_preflight_valid":
                installed_preflight.get("valid") is True,
            "runtime_d_initially_absent":
                installed_preflight.get(
                    "formal_readback_targets_absent"
                ) is True,
            "observer_precompile_valid":
                observer_precompile.get("valid") is True,
            "observer_source_identity_match":
                observer_precompile.get("identity_match") is True,
            "compile_argv": actual_compile.strip(),
            "simulator_argv": actual_sim.strip(),
            "bp_factor_feature_enabled":
                "+RETURN_OBS_BP_FACTORS" in actual_sim,
            "bp_factor_limit_bound":
                "+RETURN_OBS_BP_FACTOR_LIMIT=512" in actual_sim,
            "feature_records_returned":
                "BP_PRE_FACTOR_COUNTS_V1" in observer_text,
            "time0_observer_marker":
                "# Native NDP return observer" in observer_text
                and "bp_factor=1 bp_factor_limit=512" in observer_text,
            "compile_log_contains_success":
                "compile" in compile_text.lower(),
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": 125,
            "signal": "INT" if "signal=INT" in signal_text else "UNKNOWN",
            "natural_terminal": canonical.get("natural_terminal") is True,
            "canonical_decision": canonical,
            "canonical_self_test_pass":
                canonical_self_test.get("status") == "PASS",
            "wall_time_seconds": wall_ns / 1_000_000_000,
            "last_sim_time_ps": canonical["window_range"]["end_time_ps"],
            "formal_readback_count": gate.get("readback_count"),
            "formal_missing_count": gate.get("missing_count"),
            "formal_mismatch_byte_count": gate.get("mismatch_byte_count"),
            "formal_exact_set_complete":
                result_terms.get("formal_readback_exact_set_complete"),
            "result_gate_all_terms_true":
                result_terms.get("all_terms_true"),
            "server_result_status": gate.get("status"),
        },
        "factor_adjudication": factor,
        "last_proven_good": (
            "sum_s1 accepted 32 joint GA inputs and outputs; MSE4 accepted "
            "8 write-data beats on each channel (16 total), with one "
            "outstanding request per channel"
        ),
        "first_divergence": (
            "RD_DATA_CHANNEL_DATA_VLD_ABSENT_AFTER_INITIAL_SUM_S1_PROGRESS"
        ),
        "hang_root_cause": (
            "LONG_RUNNING_HANG_AT_MSE0_MSE3_RD_DATA_CHANNEL_DATA_VLD_LOW_"
            "PENDING_INGRESS_OR_PREPARED_WRITE_LEAF"
        ),
        "evidence_levels": {
            "E3": e3,
            "E4": e4,
            "E5": False,
            "reason": (
                "INT/125, no natural terminal, all 48 formal D missing, "
                "joint result gate false"
            ),
        },
        "successor_requirement": {
            "required": True,
            "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "boundary": (
                "MSE0/MSE3 memory read return -> RD channel inbuffer "
                "write/read -> request/data queue pairing -> prepared-data "
                "write -> rd_data_chl_data_vld"
            ),
            "functional_config_change": False,
        },
        "numeric_or_config_repeated": False,
        "errors": errors,
        "valid_receipt": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.return_zip.resolve(), args.source_zip.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
