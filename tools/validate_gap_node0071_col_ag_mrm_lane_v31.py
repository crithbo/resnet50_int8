from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_arm_ready_factor_v30 as base


ROOT_NAME = "r5_n71_gap_v31_col_ag_mrm_lane_diag"
TEST_ID = "r5-gap-node0071-v31-col-ag-mrm-byte-lane-diagnostic"
CURRENT_SERVER_RULE_SHA256 = (
    "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
)
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
RECORDS = [
    "COL_AG_MRM_LANE_EVENT_V1",
    "COL_AG_MRM_LANE_COUNTS_V1",
    "COL_AG_MRM_LANE_STATE_V1",
    "COL_AG_MRM_LANE_WITNESS_V1",
]


def configure() -> None:
    base.ROOT_NAME = ROOT_NAME
    base.TEST_ID = TEST_ID
    base.CURRENT_SERVER_RULE_SHA256 = CURRENT_SERVER_RULE_SHA256
    base.configure()


def validate_payload(
    files: dict[str, bytes], root_name: str, runner_report: dict[str, Any] | None
) -> dict[str, Any]:
    result = base.validate_payload(files, root_name, runner_report)
    errors = list(result["errors"])
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    runner = files[RUNNER].decode("utf-8")
    observer = files[OBSERVER].decode("utf-8")
    contract = manifest.get("col_ag_mrm_byte_lane_diagnostic_contract", {})
    checks = {
        "test_id": manifest.get("test_id") == TEST_ID,
        "package_class":
            manifest.get("package_class") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "runtime_enable":
            contract.get("runtime_enable") == "+RETURN_OBS_COL_AG_MRM_LANE",
        "runtime_limit":
            contract.get("runtime_limit") == "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256",
        "stable_excluded": contract.get("stable_level_counts_as_progress") is False,
        "read_only":
            contract.get("read_only") is True and contract.get("drives_dut") is False,
        "runner_enable":
            "\n  +RETURN_OBS_COL_AG_MRM_LANE\n" in runner
            and " +RETURN_OBS_COL_AG_MRM_LANE " in runner,
        "runner_limit":
            "\n  +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256\n" in runner
            and " +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256 " in runner,
        "runner_receipt":
            "col_ag_mrm_lane_enabled=true" in runner
            and "col_ag_mrm_lane_records_returned=true" in runner,
        "observer_enable": "RETURN_OBS_COL_AG_MRM_LANE" in observer,
        "observer_limit": "RETURN_OBS_COL_AG_MRM_LANE_LIMIT=%d" in observer,
        "time0":
            "col_ag_mrm_lane=%0d col_ag_mrm_lane_limit=%0d" in observer,
        "records": all(token in observer for token in RECORDS),
        "accepted_updates": all(
            token in observer
            for token in (
                "return_obs_lane_col_accept_count++;",
                "return_obs_lane_bag_accept_count++;",
                "return_obs_lane_mse_write_accept_count++;",
                "return_obs_lane_mrm_write_accept_count++;",
            )
        ),
        "not_canonical_progress":
            "COL_AG_MRM_LANE_" not in files[
                "package_tools/gap_node0071_canonical_decision.py"
            ].decode("utf-8"),
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(f"v31 COL/AG/MRM lane contract differs: {name}")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "col_ag_mrm_lane_checks": checks,
            "col_ag_mrm_lane_contract_valid": all(checks.values()),
        }
    )
    return result


def negative_controls(
    files: dict[str, bytes], root_name: str, runner_report: dict[str, Any] | None
) -> list[dict[str, Any]]:
    controls = base.negative_controls(files, root_name, runner_report)

    def check(name: str, mutated: dict[str, bytes], changed: str, expected: str) -> None:
        mutated = base.base.base.refresh(mutated, changed)
        result = validate_payload(mutated, root_name, runner_report)
        controls.append(
            {
                "name": name,
                "failed_closed": not result["valid"],
                "expected_error_observed": any(
                    expected in error for error in result["errors"]
                ),
                "errors": result["errors"],
            }
        )

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"  +RETURN_OBS_COL_AG_MRM_LANE\n", b"", 1
    ).replace(b"+RETURN_OBS_COL_AG_MRM_LANE ", b"", 1)
    check("lane_runtime_enable_removed", mutated, RUNNER, "runner_enable")

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"  +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256\n", b"", 1
    ).replace(b"+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256 ", b"", 1)
    check("lane_runtime_limit_removed", mutated, RUNNER, "runner_limit")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"col_ag_mrm_lane=%0d col_ag_mrm_lane_limit=%0d",
        b"lane_time0_removed",
        1,
    )
    check("lane_time0_removed", mutated, OBSERVER, "time0")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"return_obs_lane_mrm_write_accept_count++;",
        b"return_obs_lane_mrm_write_update_removed++;",
        1,
    )
    check("lane_critical_update_removed", mutated, OBSERVER, "accepted_updates")
    return controls


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument("--runner-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        files = base.read_zip(args.zip_path, args.root_name)
        runner_report = (
            json.loads(args.runner_report.read_text(encoding="utf-8"))
            if args.runner_report else None
        )
        result = validate_payload(files, args.root_name, runner_report)
        controls = negative_controls(files, args.root_name, runner_report)
        result["negative_controls"] = controls
        result["all_negative_controls_fail_closed"] = all(
            item["failed_closed"] and item["expected_error_observed"]
            for item in controls
        )
        result["valid"] = result["valid"] and result["all_negative_controls_fail_closed"]
        result["status"] = "PASS" if result["valid"] else "FAIL"
    except Exception as error:
        result = {
            "valid": False,
            "errors": [str(error)],
            "negative_controls": [],
            "all_negative_controls_fail_closed": False,
            "status": "FAIL",
        }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
