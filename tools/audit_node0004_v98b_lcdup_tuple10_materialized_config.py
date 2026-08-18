#!/usr/bin/env python3
"""Exact materialized-config and frozen-payload audit for v98."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v98b_lcdup_tuple10"
OLD = "r5_n4_hw_v91b_normfix"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_serialized_node0004/r5_n4_hw_v91b_normfix/r5_n4_hw_v91b_normfix.zip"
B_PIPE = ROOT / "artifacts/operator_config_validation/r5-node0004-lc-branch-duplication-ab-v3/B/execplan/pipeline_output"
AB_REPORT = ROOT / "outputs/conv_node0004_lc_branch_duplication_ab_v3/mapper_ab_report.json"
TEXT = {".json", ".md", ".sh", ".py", ".sv", ".svh", ".v", ".vh", ".txt"}
AUTHORIZED = {
    "runtime/runs/c0/install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin": B_PIPE / "install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
    "runtime/runs/c0/install/execplan.txt": B_PIPE / "install/execplan.txt",
    "runtime/runs/c0/install/execplan_op_w0.txt": B_PIPE / "install/execplan_op_w0.txt",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as current, zipfile.ZipFile(SOURCE) as source:
        if current.testzip() is not None or source.testzip() is not None:
            errors.append("zip_crc")
        current_workload = {
            name.split("/workload/", 1)[1]: current.read(name)
            for name in current.namelist() if "/workload/" in name and not name.endswith("/")
        }
        source_workload = {
            name.split("/workload/", 1)[1]: source.read(name)
            for name in source.namelist() if "/workload/" in name and not name.endswith("/")
        }
        manifest = json.loads(current.read(f"{PACKAGE}/package_manifest.json"))
    if set(current_workload) != set(source_workload):
        errors.append("workload_member_set_drift")
    changed: list[str] = []
    frozen_mismatches: list[str] = []
    for relative in sorted(set(current_workload) & set(source_workload)):
        expected = source_workload[relative]
        if PurePosixPath(relative).suffix.lower() in TEXT:
            expected = expected.decode("utf-8").replace(OLD, PACKAGE).encode("utf-8")
        if relative in AUTHORIZED:
            b_data = AUTHORIZED[relative].read_bytes()
            if current_workload[relative] != b_data:
                errors.append(f"authorized_B_materialization_mismatch:{relative}")
            if current_workload[relative] != expected:
                changed.append(relative)
        elif current_workload[relative] != expected:
            frozen_mismatches.append(relative)
    if set(changed) != set(AUTHORIZED):
        errors.append(f"authorized_change_set_differs:{changed}")
    if frozen_mismatches:
        errors.append(f"frozen_workload_drift:{frozen_mismatches}")
    report = json.loads(AB_REPORT.read_text(encoding="utf-8"))
    b_exec = json.loads((ROOT / "artifacts/operator_config_validation/r5-node0004-lc-branch-duplication-ab-v3/B/execplan/execplan_validation_report.json").read_text(encoding="utf-8"))
    b_stage = b_exec.get("facts", {}).get("stages", [{}])[0]
    checks = {
        "zip_crc_and_member_set": "zip_crc" not in errors and "workload_member_set_drift" not in errors,
        "exact_three_authorized_runtime_changes": set(changed) == set(AUTHORIZED),
        "all_other_workload_numeric_golden_payload_frozen": not frozen_mismatches,
        "B_files_byte_exact": not any(item.startswith("authorized_B_materialization_mismatch") for item in errors),
        "mapper_ab_equivalence_pass": report.get("status") == "LOCAL_EQUIVALENCE_AND_NEGLIGIBLE_COST_PASS",
        "mapper_ab_negligible_cost": report.get("cost", {}).get("negligible") is True,
        "current_shared_execplan_gate_pass": b_exec.get("valid") is True,
        "odd_71_word_zero_pad_bound": b_stage.get("config_length_64bit_words") == 71 and b_stage.get("transport_rows_128bit") == 36 and b_stage.get("last_row_high_half_is_transport_padding") is True,
        "manifest_authorized_config_only": manifest.get("config_workaround") == "DUPLICATE_LC_BRANCH_LC9_TO_LC3_FOR_PE1_INPUT2" and manifest.get("frozen", {}).get("functional_rtl") is True,
        "retired_ack_comparator_absent": manifest.get("retired_buf_idx_queue_bp_pre_comparator_present") is False,
    }
    errors.extend(key for key, value in checks.items() if not value and key not in errors)
    value = {
        "schema": "node0004-v98b-materialized-config-final-zip-audit-v1",
        "package_id": PACKAGE,
        "pass": all(checks.values()) and not errors,
        "errors": sorted(set(errors)),
        "checks": checks,
        "authorized_changed_members": changed,
        "frozen_workload_member_count": len(current_workload) - len(changed),
        "mapper_ab": {
            "address_sequence_equal": report.get("address_sequence", {}).get("equal"),
            "output_math_equal": report.get("output_math", {}).get("equal"),
            "command_count_equal": report.get("commands", {}).get("same_command_count"),
            "data_plane_memory_traffic_equal": report.get("memory_traffic", {}).get("equal"),
            "configured_data_plane_cycle_bound_delta": report.get("cycle_upper_bound", {}).get("data_plane_bound_delta"),
            "additional_lc": report.get("cost", {}).get("additional_lc"),
            "spare_lc_after": report.get("cost", {}).get("spare_B"),
        },
        "claim_boundary": "Exact local package materialization and mapper A/B equivalence only; no production tuple10, natural terminal or Formal-D claim.",
    }
    write(args.output, value)
    return 0 if value["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
