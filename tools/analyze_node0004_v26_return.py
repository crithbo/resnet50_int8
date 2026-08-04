from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (  # noqa: E402
    integer_entry,
    load_json,
    parse_kv_record,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL_NAME = "r5_n4_hw_v26_transout_threshold_fix"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = (
    "2a3e041737376a8afdfcb70d85e30c9f4c7fbc12d5bdad94c9ec2c9b7fa78d68"
)
SOURCE_SHA256 = (
    "94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb"
)


def one(records: list[dict[str, str]], name: str, errors: list[str]) -> dict[str, str]:
    if len(records) != 1:
        errors.append(f"{name} count differs: {len(records)}")
        return {}
    return records[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    sidecar = args.source_sidecar.resolve()
    errors: list[str] = []

    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    sidecar_valid = sidecar.read_text(encoding="ascii").strip() == (
        f"{source_sha}  {source_zip.name}"
    )
    if not sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors += return_errors + source_errors
    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    return_manifest = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipts: dict[str, bool] = {}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        receipts[path] = (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        )
        if not receipts[path]:
            errors.append(f"return receipt differs: {path}")
    exact_set = set(entries) == expected
    if not exact_set:
        errors.append("return exact-set differs")

    returned_manifest = entries.get("evidence/returned_package_manifest.json", b"")
    source_manifest_payload = source.get("package_manifest.json", b"")
    return_binding = (
        return_manifest.get("install_name") == INSTALL_NAME
        and return_manifest.get("records") == records
        and returned_manifest == source_manifest_payload
    )
    if not return_binding:
        errors.append("return/source manifest binding differs")
    source_manifest = json.loads(source_manifest_payload or b"{}")
    source_files = source_manifest.get("files", {})
    source_exact = (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    )
    if not source_exact:
        errors.append("source exact-set differs")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(entries, "evidence/observer_precompile.json")
    feature_binding = load_json(entries, "evidence/diagnostic_feature_binding.json")
    compile_status = integer_entry(entries, "evidence/compile_exit_status.txt", 125)
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    observer = entries.get("runs/c0/return_observer.log", b"").decode(
        "utf-8", errors="replace"
    )
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    simulator_argv = entries.get("runs/c0/simulator_argv.txt", b"").decode()
    canonical = one(
        parse_kv_record(observer, "CANONICAL_DIAG_DECISION_V1"),
        "canonical decision",
        errors,
    )
    terminal = one(
        parse_kv_record(observer, "TERMINAL_MATCH_BOUNDARY_V1"),
        "terminal boundary",
        errors,
    )
    final_release = one(
        parse_kv_record(observer, "FINAL_RELEASE_BOUNDARY_V1"),
        "final-release boundary",
        errors,
    )
    abpe = one(
        parse_kv_record(observer, "ABPE_BOUNDARY_V1"),
        "ABPE boundary",
        errors,
    )
    progress = parse_kv_record(observer, "PROGRESS_WINDOW")
    time0 = parse_kv_record(observer, "DIAGNOSTIC_FEATURE_ENABLE_V1")
    dynamic_checks = {
        "compile_run_signal": compile_status == 0 and run_status == 0 and signal == "NONE",
        "compile_elaboration_clean": (
            ("0 error(s)" in compile_log or "0 errors" in compile_log)
            and "elaboration done" in compile_log
        ),
        "observer_compile_binding": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
            and f"/{INSTALL_NAME}/tb_probe" in compile_driver
        ),
        "observer_runtime_binding": all(
            token in simulator_argv
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_HANG_DIAG",
                "+RETURN_OBS_DEEP",
                "+RETURN_OBS_ABPE",
                "+RETURN_OBS_FINAL_RELEASE",
            )
        ),
        "feature_time0_binding": (
            feature_binding.get("valid") is True
            and len(feature_binding.get("features", [])) == 4
            and len(time0) == 4
        ),
        "old_terminal_ignore_crossed": (
            terminal.get("qualified_terminal_accepts") == "128"
            and terminal.get("terminal_equal") == "128"
            and terminal.get("terminal_ignore") == "0"
            and terminal.get("hist5") == "128"
        ),
        "d_request_and_data_advanced": (
            canonical.get("d_req") == "28"
            and canonical.get("d_wdata") == "28"
        ),
        "stall_windows_exact": (
            len(progress) == 5
            and canonical.get("qualified_progress") == "234"
            and canonical.get("qualified_delta") == "0"
            and canonical.get("no_progress_windows") == "4"
        ),
        "canonical_new_boundary": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and canonical.get("slice_finish") == "0"
        ),
    }
    if not all(dynamic_checks.values()):
        errors.append("qualified v26 dynamic evidence differs")

    formal_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_claimed = gate.get("formal_readback_claimed") is True
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and natural_terminal
        and formal_claimed
        and len(formal_members) == 320
        and gate.get("e4_claimed") is True
        and gate.get("e5_claimed") is True
    )
    observer_sha = sha256_bytes(
        source.get("tb_probe/native_return_observer.svh", b"")
    )
    report: dict[str, Any] = {
        "schema": "node0004-v26-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "NEW_BOUNDARY_AFTER_TRANSOUT_FIX",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_bytes": sidecar.stat().st_size,
                "sidecar_sha256": sha256_file(sidecar),
                "sidecar_valid": sidecar_valid,
            },
            "return_crc_path_root_duplicate_symlink_valid": not return_errors,
            "return_meta": return_meta,
            "return_exact_set_allowlist_valid": exact_set and all(receipts.values()),
            "return_manifest_source_binding_valid": return_binding,
            "source_crc_path_root_valid": not source_errors,
            "source_meta": source_meta,
            "source_manifest_exact_set_valid": source_exact,
            "package_preflight_valid": package_preflight.get("valid") is True,
            "install_preflight_valid": install_preflight.get("valid") is True,
            "runtime_d_initially_absent": (
                install_preflight.get("runtime_d_initially_absent") is True
            ),
            "observer_identity_valid": (
                observer_preflight.get("valid") is True
                and observer_preflight.get("identity_match") is True
                and observer_preflight.get("observed_sha256") == observer_sha
            ),
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "simulation_started": "[RETURN_OBSERVER] enabled" in sim_log,
            "diagnostic_finish_observed": "$finish" in sim_log,
            "natural_terminal": natural_terminal,
            "formal_d_expected": 320,
            "formal_d_present": len(formal_members),
            "formal_d_missing": 320 - len(formal_members),
            "formal_d_mismatch": 0,
            "joint_result_gate": joint_gate,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "qualified_evidence": {
            "canonical": canonical,
            "progress_windows": progress,
            "terminal_boundary": terminal,
            "final_release": final_release,
            "abpe": abpe,
            "dynamic_checks": dynamic_checks,
        },
        "LAST_PROVEN_GOOD": (
            "D_WRITE_REQUEST_AND_WRITE_DATA_ACCEPTED_28_AFTER_"
            "TRANSOUT_TERMINAL_MATCH"
        ),
        "FIRST_DIVERGENCE": (
            "D_WRITE_DATA_ACCEPT_TO_BUFFER5_NEXT_READ_OR_LAST_INDEX0_"
            "SLICE_FINISH"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AFTER_STATIC_AUDIT_REQUIRES_ONE_NARROW_BOUNDARY",
            "excluded": [
                "old SA outbuffer occupancy claim",
                "transout terminal-ignore threshold",
                "D request/data channel absence",
            ],
            "missing_boundary": (
                "MSE4 RD_Buffer_AG tag/queue/read accept through "
                "WR_Data_Channel last propagation"
            ),
            "functional_rtl_defect_claimed": False,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL",
                "B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED",
            ],
            "opened": "B_CONV_NODE0004_D_WRITE_TO_LAST_INDEX0_SLICE_FINISH_UNOBSERVED",
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "scope": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_analysis_repeated": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
