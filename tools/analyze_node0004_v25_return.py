from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
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


RETURN_SHA256 = "e6b35bc2f311b9cdf184c65bdd6f8ad834ededf6888ffb390943b83d87d1ac5f"
SOURCE_SHA256 = "e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab"
INSTALL_NAME = "r5_n4_hw_v25_terminal_match_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--source-sidecar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
    sidecar_text = sidecar.read_text(encoding="ascii").strip()
    sidecar_valid = sidecar_text == f"{source_sha}  {source_zip.name}"
    if not sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(
        return_zip, RETURN_ROOT
    )
    source, source_errors, source_meta = safe_entries(
        source_zip, INSTALL_NAME
    )
    errors.extend(return_errors)
    errors.extend(source_errors)

    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    return_manifest = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    record_valid: dict[str, bool] = {}
    for record in records:
        path = record.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        passed = (
            payload is not None
            and len(payload) == record.get("size_bytes")
            and sha256_bytes(payload) == record.get("sha256")
        )
        record_valid[path] = passed
        if not passed:
            errors.append(f"allowlist receipt differs: {path}")
    exact_set = set(entries) == expected
    if not exact_set:
        errors.append("return exact-set differs")

    allow_payload = entries.get("RETURN_ALLOWLIST.json", b"")
    returned_manifest = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    source_manifest_payload = source.get("package_manifest.json", b"")
    return_manifest_valid = (
        return_manifest.get("schema") == "node0004-return-manifest-v24"
        and return_manifest.get("install_name") == INSTALL_NAME
        and return_manifest.get("records") == records
        and return_manifest.get("return_allowlist", {}).get("size_bytes")
        == len(allow_payload)
        and return_manifest.get("return_allowlist", {}).get("sha256")
        == sha256_bytes(allow_payload)
        and return_manifest.get("source_package_manifest", {}).get(
            "size_bytes"
        )
        == len(returned_manifest)
        and return_manifest.get("source_package_manifest", {}).get("sha256")
        == sha256_bytes(returned_manifest)
        and returned_manifest == source_manifest_payload
    )
    if not return_manifest_valid:
        errors.append("RETURN_MANIFEST/source binding differs")

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
        errors.append("source package exact-set differs")
    observer_payload = source.get("tb_probe/native_return_observer.svh", b"")
    observer_sha = sha256_bytes(observer_payload)

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(
        entries, "evidence/observer_precompile.json"
    )
    feature_binding = load_json(
        entries, "evidence/diagnostic_feature_binding.json"
    )
    compile_status = integer_entry(
        entries, "evidence/compile_exit_status.txt", 125
    )
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get(
        "evidence/signal_status.txt", b"MISSING"
    ).decode("ascii", errors="replace").strip()
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    simulator_argv = entries.get(
        "runs/c0/simulator_argv.txt", b""
    ).decode("utf-8", errors="replace")
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    observer_log = entries.get(
        "runs/c0/return_observer.log", b""
    ).decode("utf-8", errors="replace")

    compile_bound = (
        "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
        and f"/{INSTALL_NAME}/tb_probe" in compile_driver
    )
    runtime_bound = all(
        token in simulator_argv
        for token in (
            "+RETURN_OBSERVER",
            "+RETURN_HANG_DIAG",
            "+RETURN_OBS_DEEP",
            "+RETURN_OBS_ABPE",
            "+RETURN_OBS_FINAL_RELEASE",
        )
    )
    time0 = parse_kv_record(observer_log, "DIAGNOSTIC_FEATURE_ENABLE_V1")
    canonical = parse_kv_record(observer_log, "CANONICAL_DIAG_DECISION_V1")
    progress = parse_kv_record(observer_log, "PROGRESS_WINDOW")
    abpe = parse_kv_record(observer_log, "ABPE_BOUNDARY_V1")
    final_release = parse_kv_record(
        observer_log, "FINAL_RELEASE_BOUNDARY_V1"
    )
    terminal_edges = parse_kv_record(
        observer_log, "TERMINAL_MATCH_EDGE_V1"
    )
    terminal_boundary = parse_kv_record(
        observer_log, "TERMINAL_MATCH_BOUNDARY_V1"
    )
    feature_valid = (
        feature_binding.get("valid") is True
        and len(feature_binding.get("features", [])) == 4
        and all(
            item.get("valid") is True
            for item in feature_binding.get("features", [])
        )
        and len(time0) == 4
    )

    accepted = [row for row in terminal_edges if row.get("accepted") == "1"]
    terminal_accepted = [
        row for row in accepted if row.get("terminal_accept") == "1"
    ]
    histogram = Counter(
        int(row["buffer_index"]) for row in terminal_accepted
    )
    terminal_checks = {
        "edge_records_256": len(terminal_edges) == 256,
        "all_accepted": len(accepted) == 256,
        "all_terminal_accepted": len(terminal_accepted) == 256,
        "all_raw_valid_0x3": all(
            row.get("raw_valid") == "0x3" for row in terminal_accepted
        ),
        "all_masked_valid_0x3": all(
            row.get("masked_valid") == "0x3"
            for row in terminal_accepted
        ),
        "all_masked_last_0x3": all(
            row.get("masked_last") == "0x3"
            for row in terminal_accepted
        ),
        "all_matched_and_pipeline_enabled": all(
            row.get("all_matched") == "1"
            and row.get("pipeline_enable") == "1"
            for row in terminal_accepted
        ),
        "configured_threshold_2": all(
            row.get("transout_cfg") == "2" for row in terminal_accepted
        ),
        "all_ignored": all(
            row.get("ignore") == "1"
            and row.get("matched") == "0"
            and row.get("out") == "0"
            for row in terminal_accepted
        ),
        "index_histogram_4x64_5x192": histogram == Counter({4: 64, 5: 192}),
        "summary_exact": (
            len(terminal_boundary) == 1
            and terminal_boundary[0].get("qualified_terminal_accepts")
            == "256"
            and terminal_boundary[0].get("terminal_equal") == "0"
            and terminal_boundary[0].get("terminal_ignore") == "256"
            and terminal_boundary[0].get("terminal_out") == "0"
            and terminal_boundary[0].get("hist4") == "64"
            and terminal_boundary[0].get("hist5") == "192"
        ),
    }
    if not all(terminal_checks.values()):
        errors.append("terminal-match qualified evidence differs")

    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_claimed = gate.get("formal_readback_claimed") is True
    formal_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
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
    compile_clean = (
        compile_status == 0
        and ("0 error(s)" in compile_log or "0 errors" in compile_log)
        and "elaboration done" in compile_log
    )

    report: dict[str, Any] = {
        "schema": "node0004-v25-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "CONFIG_TRANSOUT_THRESHOLD_TOO_LOW",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": (
                    "CDA-SERVER-RETURN-TRANSPORT-"
                    "USER-ATTESTED-NO-SIDECAR-001"
                ),
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
            "return_exact_set_allowlist_valid": exact_set
            and all(record_valid.values()),
            "return_manifest_source_binding_valid": return_manifest_valid,
            "source_crc_path_root_valid": not source_errors,
            "source_meta": source_meta,
            "source_manifest_exact_set_valid": source_exact,
            "observer_sha256": observer_sha,
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
            "compile_argv_bound": compile_bound,
            "runtime_argv_bound": runtime_bound,
            "diagnostic_feature_binding_valid": feature_valid,
            "compile_exit": compile_status,
            "compile_elaboration_zero_errors": compile_clean,
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
            "canonical": canonical[0] if canonical else None,
            "progress_windows": progress,
            "abpe": abpe[-1] if abpe else None,
            "final_release": final_release[-1] if final_release else None,
            "terminal_boundary": (
                terminal_boundary[-1] if terminal_boundary else None
            ),
            "terminal_checks": terminal_checks,
            "terminal_index_histogram": {
                str(key): value for key, value in sorted(histogram.items())
            },
            "terminal_edge_record_count": len(terminal_edges),
        },
        "LAST_PROVEN_GOOD": (
            "QUALIFIED_A_B_TERMINAL_ACCEPT_WITH_ALL_OPERANDS_MATCHED"
        ),
        "FIRST_DIVERGENCE": (
            "ACCEPTED_TERMINAL_INDEX_TO_TRANSOUT_THRESHOLD_CLASSIFICATION"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "DETERMINISTIC_CONFIG_ERROR",
            "leaf": "special_array.transout_last_index",
            "materialized_value": 2,
            "required_value": 5,
            "formula": "max accepted A/B terminal last_index",
            "mechanism": (
                "active RTL computes accepted_index - threshold; every "
                "accepted index4/5 was positive relative to threshold2, "
                "therefore all 256 were ignore=1 and none asserted "
                "matched/out to release the outbuffer"
            ),
            "active_rtl": {
                "path": (
                    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
                    "SA_PE_Control_Block.sv"
                ),
                "sha256": (
                    "e254af41c5354d93d31cd9196d79a0a365ea880b86286ea0c15e3a4f41122ca6"
                ),
                "lines": [161, 162, 163, 164, 166, 167],
            },
            "old_occupancy_root_cause_invalidated": True,
            "functional_rtl_defect": False,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_RAW_TERMINAL_TO_QUALIFIED_TRANSOUT_MATCH_UNOBSERVED"
            ],
            "opened_and_fixed_by_successor": (
                "B_CONV_NODE0004_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL"
            ),
            "preserved_until_dynamic_return": [
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
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
