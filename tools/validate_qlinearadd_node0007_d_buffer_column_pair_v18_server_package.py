from __future__ import annotations

import copy
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    build_configs,
    validate_d_buffer_column_pair,
)
from tools import validate_qlinearadd_node0007_d_buffer_supply_v15_server_package as base
from tools import validate_qlinearadd_node0007_d_buffer_column_pair_v18 as local


INSTALL_NAME = "r5_qadd_n7_dbuf_colpair_v18"
SOURCE_NAME = "r5_qadd_n7_dbuf_rule_v16"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5"
SERVER_RULE_SHA256 = "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
QADD_RULE_SHA256 = "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"
TAIL_RULE_SHA256 = "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-d-buffer-column-pair-v18"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"
PIPELINE = EVIDENCE_ROOT / "execplan/pipeline_output"
RULE_ID = "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001"


def _configure_base(zip_sha256: str) -> None:
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_NAME = SOURCE_NAME
    base.ZIP_SHA256 = zip_sha256
    base.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    base.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    base.ZIP_PATH = ZIP_PATH
    base.SIDECAR_PATH = SIDECAR_PATH
    base.SOURCE_ZIP = SOURCE_ZIP
    base.BUILD_RECEIPT = BUILD_RECEIPT
    base.EVIDENCE_ROOT = EVIDENCE_ROOT
    base.REPORT_PATH = REPORT_PATH
    base.PIPELINE = PIPELINE
    base.build_configs = build_configs
    base.validate_d_buffer_supply = validate_d_buffer_column_pair
    base.v11.base.QADD_RULE_SHA256 = QADD_RULE_SHA256


def _contract_errors(
    manifest: dict[str, Any],
    *,
    override: dict[str, Any] | None = None,
) -> list[str]:
    record = copy.deepcopy(
        override
        if override is not None
        else manifest.get("functional_configuration_fix")
    )
    if not isinstance(record, dict):
        return ["D-buffer column-pair contract absent"]
    expected = {
        "rule_id": RULE_ID,
        "changed_stages": [
            "op_relocation_pad",
            "op_tail_mul",
            "op_tail_round",
        ],
        "transaction_bytes": 32,
        "buffer_row_bytes": 32,
        "mse_read_bytes": 16,
        "accepted_row_col_pairs": [[0, 0], [0, 16]],
        "byte_windows": [[0, 16], [16, 32]],
        "window_union_exact": [0, 32],
        "buffer5_actual_max_row": 0,
        "functional_rtl_modified": False,
        "w3_qparams_tail_workload_golden_changed": False,
        "dram_loop_address_occurrence_changed": False,
    }
    errors = [
        f"D-buffer column-pair field differs: {key}"
        for key, value in expected.items()
        if record.get(key) != value
    ]
    if record.get("changed_leaves_per_stage") != {
        "buffer_loop_configs.GROUP2.ROW_LC.end": [2, 1],
        "buffer_loop_configs.GROUP2.COL_LC.end": [4, 32],
        "buffer_loop_configs.GROUP2.COL_LC.stride": [2, 16],
        "buffer_config.buffer5.buf_end_row_addr": [1, 0],
    }:
        errors.append("D-buffer exact leaf delta differs")
    return errors


def _contract_negatives(manifest: dict[str, Any]) -> dict[str, Any]:
    original = copy.deepcopy(manifest["functional_configuration_fix"])
    cases: dict[str, dict[str, Any]] = {}
    mutations = (
        ("delete_window", "byte_windows", [[0, 16]]),
        ("overlap_window", "byte_windows", [[0, 16], [8, 24]]),
        ("gap_window", "byte_windows", [[0, 16], [17, 32]]),
        ("restore_col_stride_2", "changed_leaves_per_stage", {
            **original["changed_leaves_per_stage"],
            "buffer_loop_configs.GROUP2.COL_LC.stride": [2, 2],
        }),
        ("unused_second_row", "buffer5_actual_max_row", 1),
        ("tamper_mse_read_width", "mse_read_bytes", 8),
        ("tamper_transaction_length", "transaction_bytes", 16),
        ("only_buf_spatial_size", "accepted_row_col_pairs", [[0, 0]]),
    )
    for name, key, value in mutations:
        candidate = copy.deepcopy(original)
        candidate[key] = value
        cases[name] = candidate
    result = {}
    for name, candidate in cases.items():
        errors = _contract_errors(manifest, override=candidate)
        result[name] = {
            "failed_closed": bool(errors),
            "exit_code": 1 if errors else 0,
            "first_error": errors[0] if errors else None,
        }
    return result


def _load_zip() -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        if archive.testzip() is not None:
            raise ValueError("final ZIP CRC failed")
        members = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
        }
    manifest = json.loads(
        members[f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"]
    )
    return members, manifest


def _stage_reset_parser_checks(
    members: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    name = (
        f"{INSTALL_NAME}/package_tools/"
        "qlinearadd_progress_canonical_decision.py"
    )
    text = members[name].decode("utf-8")
    checks = {
        "active_cycle_decrease_is_stage_transition": (
            'if after["active_cycles"] < before["active_cycles"]:' in text
            and '"stage_transition_reset": True' in text
        ),
        "within_stage_negative_counter_still_fails": (
            "if any(value < 0 for value in delta.values()):" in text
            and "monotonic = False" in text
        ),
        "manifest_parser_hash_matches": (
            manifest["canonical_decision_contract"]["parser_sha256"]
            == base.hashlib.sha256(members[name]).hexdigest()
        ),
    }
    negatives = {
        "delete_stage_transition_branch": {
            "failed_closed": '"stage_transition_reset": True'
            not in text.replace('"stage_transition_reset": True', "", 1),
            "exit_code": 1,
        },
        "delete_within_stage_regression_guard": {
            "failed_closed": "if any(value < 0 for value in delta.values()):"
            not in text.replace(
                "if any(value < 0 for value in delta.values()):", "", 1
            ),
            "exit_code": 1,
        },
    }
    return {
        "passed": all(checks.values())
        and all(item["failed_closed"] for item in negatives.values()),
        "checks": checks,
        "negative_controls": negatives,
    }


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    zip_sha = base.sha256(ZIP_PATH)
    _configure_base(zip_sha)
    old_errors = base._supply_contract_errors
    old_negatives = base._supply_negative_controls
    base._supply_contract_errors = _contract_errors
    base._supply_negative_controls = _contract_negatives
    try:
        report = base.validate_final_zip(write_report=False)
    finally:
        base._supply_contract_errors = old_errors
        base._supply_negative_controls = old_negatives
    members, manifest = _load_zip()
    local_report = local.validate(write_report=False)
    contract_errors = _contract_errors(manifest)
    negatives = _contract_negatives(manifest)
    parser = _stage_reset_parser_checks(members, manifest)
    receipts = manifest["final_zip_rule_self_audit"]["rule_receipts"]
    current_receipts = {
        "qlinearadd": (
            receipts["qlinearadd_rule"]["sha256"] == QADD_RULE_SHA256
            and receipts["qlinearadd_rule"]["current_match"] is True
        ),
        "exact_tail": (
            receipts["exact_uint8_tail_rule"]["sha256"] == TAIL_RULE_SHA256
            and receipts["exact_uint8_tail_rule"]["current_match"] is True
        ),
        "server": (
            receipts["server_package_rule"]["sha256"] == SERVER_RULE_SHA256
            and receipts["server_package_rule"]["current_match"] is True
        ),
        "formal_rule_id": RULE_ID
        in manifest["final_zip_rule_self_audit"][
            "applicable_qlinearadd_rule_ids"
        ],
        "exact_tail_rule_ids": bool(
            manifest["final_zip_rule_self_audit"].get(
                "applicable_exact_tail_rule_ids"
            )
        ),
    }
    report["checks"].update(
        {
            # The inherited v10 validator requires the rule receipt map to
            # have exactly three keys. v18 intentionally adds the active
            # exact-tail receipt, so validate the superset here.
            "rule_receipts_current": all(current_receipts.values()),
            "local_v18_current_rule_validation": local_report[
                "local_candidate_valid"
            ],
            "direct_final_zip_column_pair_contract": not contract_errors,
            "current_rule_receipts": all(current_receipts.values()),
            "stage_scoped_canonical_parser": parser["passed"],
            "column_pair_negative_controls": all(
                item["failed_closed"] for item in negatives.values()
            ),
        }
    )
    errors = [name for name, passed in report["checks"].items() if not passed]
    errors.extend(f"column_pair: {error}" for error in contract_errors)
    all_negatives = (
        report.get("all_required_negative_controls_fail_closed") is True
        and all(item["failed_closed"] for item in negatives.values())
        and all(
            item["failed_closed"]
            for item in parser["negative_controls"].values()
        )
    )
    if not all_negatives:
        errors.append("all_required_negative_controls_fail_closed")
    report.update(
        {
            "schema": (
                "qlinearadd-node0007-d-buffer-column-pair-"
                "final-zip-self-audit-v1"
            ),
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if not errors
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "errors": errors,
            "error_count": len(errors),
            "all_required_negative_controls_fail_closed": all_negatives,
            "current_rule_receipts": current_receipts,
            "d_buffer_window_proof": local_report["current_rule_match"],
            "d_buffer_negative_controls": negatives,
            "stage_scoped_canonical_parser": parser,
            "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
            "zip_sha256": zip_sha,
            "zip_bytes": ZIP_PATH.stat().st_size,
            "sidecar": SIDECAR_PATH.relative_to(ROOT).as_posix(),
            "sidecar_sha256": base.sha256(SIDECAR_PATH),
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "config_numeric_analysis_repeated": False,
            "expected_return": f"{INSTALL_NAME}_return.zip",
            "server_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
        }
    )
    if write_report:
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        build.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(
                    ROOT
                ).as_posix(),
                "final_self_audit_report_sha256": base.sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate_final_zip()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
