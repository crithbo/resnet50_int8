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


INSTALL_NAME = "r5_n4_hw_v28_dwrite_path_diag_bind"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = (
    "959b945ebaa40dfcbedbdac73b3fcbb98f5fdf96f3dfa77dde8bd0971009c4a9"
)
SOURCE_SHA256 = (
    "a3b2be33d395356b06c96e8311c017544cbdcc7b3e553006ae582acea176101f"
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
    source_sidecar = args.source_sidecar.resolve()
    errors: list[str] = []

    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    source_sidecar_valid = source_sidecar.read_text(encoding="ascii").strip() == (
        f"{source_sha}  {source_zip.name}"
    )
    if not source_sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors += return_errors + source_errors
    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    return_manifest = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipt_valid: dict[str, bool] = {}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        receipt_valid[path] = (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        )
        if not receipt_valid[path]:
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
    dwrite = one(
        [
            item
            for item in parse_kv_record(observer, "DWRITE_PATH_BOUNDARY_V1")
            if item.get("event") == "DIAG_DECISION"
        ],
        "D-write decision boundary",
        errors,
    )
    terminal = one(
        parse_kv_record(observer, "TERMINAL_MATCH_BOUNDARY_V1"),
        "terminal boundary",
        errors,
    )
    progress = parse_kv_record(observer, "PROGRESS_WINDOW")
    sg_counts = [
        item
        for item in parse_kv_record(observer, "SG_COUNTS")
        if item.get("event") == "DIAG_SUMMARY"
    ]
    sg = one(sg_counts, "SG summary", errors)
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
                "+RETURN_OBS_DWRITE_PATH",
            )
        ),
        "feature_time0_binding": (
            feature_binding.get("valid") is True
            and len(feature_binding.get("features", [])) == 5
            and len(time0) == 5
        ),
        "old_terminal_ignore_crossed": (
            terminal.get("qualified_terminal_accepts") == "128"
            and terminal.get("terminal_equal") == "128"
            and terminal.get("terminal_ignore") == "0"
            and terminal.get("hist5") == "128"
        ),
        "stall_windows_exact": (
            len(progress) == 5
            and canonical.get("qualified_progress") == "234"
            and canonical.get("qualified_delta") == "0"
            and canonical.get("no_progress_windows") == "4"
        ),
        "canonical_dwrite_boundary": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and canonical.get("slice_finish") == "0"
        ),
        "source_dwrite_queue_stall": (
            dwrite.get("tag_accept") == "19"
            and dwrite.get("buf_read_accept") == "17"
            and dwrite.get("prepare_accept") == "16"
            and dwrite.get("ob_write_accept") == "14"
            and dwrite.get("queue_count") == "2"
            and dwrite.get("queue_full") == "1"
            and dwrite.get("wr_ready") == "0"
            and dwrite.get("prepared_count") == "32"
            and dwrite.get("slice_finish") == "0"
        ),
        "sink_domain_pairs_balanced": (
            sg.get("mse4_req0") == "7"
            and sg.get("mse4_req1") == "7"
            and sg.get("mse4_wdata0") == "7"
            and sg.get("mse4_wdata1") == "7"
            and sg.get("mse4_outstanding0") == "0"
            and sg.get("mse4_outstanding1") == "0"
        ),
    }
    if not all(dynamic_checks.values()):
        errors.append("qualified v28 dynamic evidence differs")

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
        "schema": "node0004-v28-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "LONG_RUNNING_HANG_REFINED_TO_DATAHUB_DRAIN_BOUNDARY",
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
                "sidecar_bytes": source_sidecar.stat().st_size,
                "sidecar_sha256": sha256_file(source_sidecar),
                "sidecar_valid": source_sidecar_valid,
            },
            "return_crc_path_root_duplicate_symlink_valid": not return_errors,
            "return_meta": return_meta,
            "return_exact_set_allowlist_valid": exact_set and all(receipt_valid.values()),
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
            "dwrite_boundary": dwrite,
            "sink_group_counts": sg,
            "dynamic_checks": dynamic_checks,
        },
        "LAST_PROVEN_GOOD": (
            "MSE4_SOURCE_PREPARED_16_CHUNKS_AND_DATAHUB_ACCEPTED_"
            "7_ADDRESS_PLUS_7_DATA_PER_CHANNEL_WITH_ZERO_OUTSTANDING"
        ),
        "FIRST_DIVERGENCE": (
            "DATAHUB_LOCAL_WRITE_QUEUE_HEAD_TO_BANK_CROSSBAR_DRAIN_"
            "WHILE_MSE4_SOURCE_REMAINS_BACKPRESSURED"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AFTER_EXHAUSTIVE_V28_BOUNDARY",
            "excluded": [
                "old SA outbuffer occupancy claim",
                "transout terminal-ignore threshold",
                "MSE4 address-channel absence",
                "MSE4 write-data-channel absence",
                "address/data imbalance at the datahub ingress",
                "last-index0 as the first current-epoch failure",
            ],
            "important_clock_domain_boundary": (
                "source clk_db valid/ready observations are not treated as "
                "one-to-one sink transactions; sink clk_sg accepted counts are authoritative"
            ),
            "missing_unique_boundary": (
                "local_wr_req_queue head valid/read enable -> local channel arbiter "
                "grant -> datahub bank match/crossbar ready"
            ),
            "candidate_causes": [
                "queue head address contains X/out-of-range bank selector",
                "local read/write arbiter does not present the queued write",
                "bank match exists but bank crossbar ready never asserts",
            ],
            "functional_rtl_defect_claimed": False,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_D_WRITE_REQUEST_OR_DATA_ABSENT",
                "B_CONV_NODE0004_D_WRITE_ADDRESS_DATA_INGRESS_IMBALANCE",
            ],
            "opened": "B_CONV_NODE0004_DATAHUB_LOCAL_WRITE_QUEUE_TO_BANK_DRAIN_UNOBSERVED",
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
