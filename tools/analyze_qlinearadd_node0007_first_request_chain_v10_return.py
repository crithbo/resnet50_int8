from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import qlinearadd_first_request_canonical_decision as canonical


DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_qadd_n7_first_request_chain_v10_return.zip"
)
DEFAULT_SIDECAR = Path(str(DEFAULT_RETURN) + ".sha256")
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_first_request_chain_v10.zip"
)
SOURCE_SHA256 = "573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf"
INSTALL_NAME = "r5_qadd_n7_first_request_chain_v10"
REPORT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-first-request-v10-return-analysis"
    / "report.json"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _key_values(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _load_return(path: Path) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        names = archive.namelist()
        roots = sorted({name.split("/", 1)[0] for name in names})
        if bad is not None or roots != [f"{INSTALL_NAME}_return"]:
            raise ValueError(f"return ZIP structure differs: bad={bad} roots={roots}")
        if len(names) != len(set(names)):
            raise ValueError("return ZIP has duplicate members")
        members = {name: archive.read(name) for name in names}
    root = f"{INSTALL_NAME}_return/"
    manifest = json.loads(members[root + "RETURN_MANIFEST.json"])
    structure = {
        "crc_valid": True,
        "root_exact": True,
        "duplicate_members_absent": True,
        "member_count": len(members),
    }
    return members, manifest, structure


def analyze(
    return_zip: Path = DEFAULT_RETURN,
    sidecar: Path = DEFAULT_SIDECAR,
) -> dict[str, Any]:
    actual_return_sha = sha256(return_zip)
    sidecar_text = sidecar.read_text(encoding="ascii")
    expected_sidecar = f"{actual_return_sha}  {return_zip.name}\n"
    members, return_manifest, structure = _load_return(return_zip)
    root = f"{INSTALL_NAME}_return/"
    listed = {item["path"]: item for item in return_manifest["files"]}
    actual_relative = {
        name.removeprefix(root)
        for name in members
        if name != root + "RETURN_MANIFEST.json"
    }
    listed_valid = set(listed) == actual_relative and all(
        listed[path]["sha256"] == sha256_bytes(members[root + path])
        and listed[path]["size_bytes"] == len(members[root + path])
        for path in listed
    )

    with zipfile.ZipFile(SOURCE_ZIP) as source:
        source_bad = source.testzip()
        source_manifest = source.read(
            f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
        )
    returned_package_manifest = members[root + "evidence/PACKAGE_MANIFEST.json"]
    package_preflight = json.loads(
        members[root + "evidence/package_preflight.json"]
    )
    installed_preflight = json.loads(
        members[root + "evidence/installed_preflight.json"]
    )
    gate = json.loads(members[root + "evidence/SERVER_RESULT_GATE.json"])
    progress_contract = json.loads(
        members[root + "evidence/progress_contract.json"]
    )
    observer = members[root + "runs/return_observer.log"]
    canonical_return = canonical.load_unique_record(
        members[root + "evidence/CANONICAL_PROGRESS_DECISION.json"]
    )
    canonical_recomputed = canonical.decide(
        observer,
        stall_window_cycles=progress_contract["stall_window_cycles"],
        minimum_monotonic_windows=progress_contract[
            "minimum_monotonic_windows_for_progress"
        ],
    )
    base_samples = canonical.parse_base_samples(
        observer.decode("utf-8", errors="replace")
    )
    chain_samples = canonical.parse_chain_samples(
        observer.decode("utf-8", errors="replace")
    )
    heartbeats = [
        sample for sample in base_samples if sample["event"] == "HEARTBEAT"
    ]
    last_active = heartbeats[-1]["active_cycles"] if heartbeats else 0
    stall_windows = (
        last_active // progress_contract["stall_window_cycles"]
    )
    timing = {
        key: int(value)
        for key, value in _key_values(
            members[root + "evidence/host_timing.txt"]
        ).items()
    }
    signal = _key_values(members[root + "evidence/signal_status.txt"])
    compile_argv = members[root + "evidence/actual_compile_argv.txt"].decode()
    sim_log = members[root + "runs/sim.log"].decode(
        "utf-8", errors="replace"
    )
    formal = gate["result_gate_conjunction"]
    missing_paths = return_manifest["required_missing"]
    report: dict[str, Any] = {
        "schema": "qlinearadd-node0007-first-request-v10-return-analysis-v1",
        "status": "VALID_DIAGNOSTIC_RETURN_FUNCTIONAL_RESULT_FAILED",
        "return_receipt": {
            "path": str(return_zip),
            "sha256": actual_return_sha,
            "bytes": return_zip.stat().st_size,
            "sidecar_path": str(sidecar),
            "sidecar_sha256": sha256(sidecar),
            "sidecar_exact": sidecar_text == expected_sidecar,
        },
        "zip_and_allowlist": {
            **structure,
            "allowlist_only": return_manifest.get("allowlist_only") is True,
            "manifest_install_name": return_manifest.get("install_name"),
            "manifest_file_count": len(listed),
            "exact_set_and_hashes": listed_valid,
        },
        "source_binding": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "expected_sha256": SOURCE_SHA256,
            "actual_sha256": sha256(SOURCE_ZIP),
            "crc_valid": source_bad is None,
            "returned_package_manifest_byte_equal": (
                returned_package_manifest == source_manifest
            ),
        },
        "preflight": {
            "package_valid": package_preflight.get("valid") is True,
            "installed_valid": installed_preflight.get("valid") is True,
            "package_runtime_d_absent": package_preflight.get(
                "formal_readback_targets_absent"
            )
            is True,
            "installed_runtime_d_absent": installed_preflight.get(
                "formal_readback_targets_absent"
            )
            is True,
            "server_source_files_inspected": (
                package_preflight.get("server_source_files_inspected")
                or installed_preflight.get("server_source_files_inspected")
            ),
            "v10_identity_duplication_defect_triggered": False,
            "compile_reached_despite_quarantined_defect": True,
        },
        "execution": {
            "compile_exit_status": int(signal["compile_status"]),
            "simulation_exit_status": int(signal["simulation_status"]),
            "signal": signal["signal"],
            "natural_terminal": formal["natural_completion"],
            "observer_enabled_and_returned": (
                _key_values(
                    members[root + "evidence/observer_binding.txt"]
                ).get("observer_enabled_and_returned")
                == "true"
            ),
            "observer_compile_incdir_bound": (
                "+incdir+" in compile_argv
                and "tb_probe" in compile_argv
            ),
            "observer_compile_macro_bound": (
                "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_argv
            ),
            "host_total_seconds": (
                timing["final_epoch_ns"] - timing["package_start_epoch_ns"]
            )
            / 1e9,
            "simulation_seconds": (
                timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
            )
            / 1e9,
            "sim_interrupt_time": int(
                re.search(r"Interrupt at time (\d+)", sim_log).group(1)
            ),
        },
        "progress": {
            "base_sample_count": len(base_samples),
            "heartbeat_count": len(heartbeats),
            "first_request_chain_sample_count": len(chain_samples),
            "last_base_active_cycles": last_active,
            "completed_stall_windows": stall_windows,
            "stall_window_cycles": progress_contract["stall_window_cycles"],
            "last_base_counters": (
                heartbeats[-1]["counters"] if heartbeats else {}
            ),
            "canonical_record_exact_recompute": (
                canonical_return == canonical_recomputed
            ),
            "canonical_decision": canonical_return["decision"],
            "canonical_boundary": canonical_return["boundary"],
            "canonical_reason": canonical_return["reason"],
            "qualified_progress_observed": False,
            "active_clock_cycles_only_not_progress": True,
        },
        "formal_d": {
            "expected_count": gate["expected_readback_count"],
            "observed_count": gate["observed_readback_count"],
            "missing_count": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "missing_exact_set": len(missing_paths) == gate["missing_count"],
            "all_terms_true": formal["all_terms_true"],
            "mismatch_zero_not_numeric_pass": True,
        },
        "first_divergence": {
            "last_good": (
                "compile/elaboration and op_a_dequant EXEC_START; "
                "base clk_db observer heartbeat remains active"
            ),
            "first_bad": (
                "no qualified request/read/write or buffer transaction through "
                f"{stall_windows} stall windows"
            ),
            "first_unobservable": (
                "actual slice_start_run -> physical LC2/4/6/13/18 -> "
                "selected MSE0/MSE4 -> first request"
            ),
        },
        "hang_root_cause": {
            "functional_root_cause": "UNRESOLVED_INSIDE_EXEC_START_TO_FIRST_REQUEST",
            "hang_adjudication": "LONG_RUNNING_HANG_PENDING_INTERNAL_BOUNDARY",
            "diagnostic_root_cause": (
                "DETERMINISTIC_OBSERVER_CLOCK_DOMAIN_BINDING_ERROR"
            ),
            "diagnostic_detail": (
                "base heartbeat/active_cycles are owned by clk_db, while v10 "
                "emits FIRST_REQUEST_CHAIN only on clk_sg and tests a cross-domain "
                "active_cycles modulo equality; a stopped/gated clk_sg or missed "
                "cross-domain equality suppresses the entire chain stream"
            ),
        },
        "stage_gates": {
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "claim_boundary": {
            "v10_package_status": (
                "QUARANTINED_RUNTIME_PREFLIGHT_IDENTITY_DUPLICATION"
            ),
            "dynamic_evidence_independently_consumable": True,
            "may_count_as_v11_or_successor_dynamic_pass": False,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "consumed_reuse_assets": True,
        },
        "errors": [],
    }
    structural = [
        report["return_receipt"]["sidecar_exact"],
        report["zip_and_allowlist"]["exact_set_and_hashes"],
        report["source_binding"]["actual_sha256"] == SOURCE_SHA256,
        report["source_binding"]["returned_package_manifest_byte_equal"],
        report["preflight"]["package_valid"],
        report["preflight"]["installed_valid"],
        report["progress"]["canonical_record_exact_recompute"],
    ]
    if not all(structural):
        report["errors"].append("one or more formal return receipt checks failed")
        report["status"] = "RETURN_RECEIPT_FAILED_CLOSED"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", nargs="?", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--sidecar", type=Path)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    sidecar = args.sidecar or Path(str(args.return_zip) + ".sha256")
    report = analyze(args.return_zip, sidecar)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
