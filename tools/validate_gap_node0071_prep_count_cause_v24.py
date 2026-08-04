from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_rd_data_vld_diag_v21 as base


ROOT_NAME = "r5_n71_gap_v24_prep_count_cause_diag"
TEST_ID = "r5-gap-node0071-v24-prep-count-cause-diagnostic"
CURRENT_SERVER_RULE_SHA256 = (
    "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
)
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
FEATURE_RECORDS = [
    "PREP_COUNT_CAUSE_EVENT_V1",
    "PREP_COUNT_CAUSE_COUNTS_V1",
    "PREP_COUNT_CAUSE_STATE_V1",
    "PREP_COUNT_CAUSE_WITNESS_V1",
]
XMR_LEAVES = [
    ".rst_n",
    ".slice_rst",
    ".rd_data_chl_prepared_data_wr_hs",
    ".rd_data_chl_prepared_data_rd_hs",
    ".rd_data_chl_prepared_data_cnt",
    ".rd_chl_queue_rd_tsf_size",
    ".mse_buf_spatial_size",
    ".prepared_data_lt_req",
    ".rd_data_chl_prepared_data_bp_pre",
    ".rd_data_chl_ob_bp_pre",
    ".rd_data_chl_data_vld",
]


def configure() -> None:
    base.ROOT_NAME = ROOT_NAME
    base.TEST_ID = TEST_ID
    base.CURRENT_SERVER_RULE_SHA256 = CURRENT_SERVER_RULE_SHA256
    base.configure()


def refresh(files: dict[str, bytes], path: str) -> dict[str, bytes]:
    return base.refresh(files, path)


def validate_payload(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> dict[str, Any]:
    result = base.validate_payload(files, root_name, runner_report)
    errors = list(result["errors"])
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    runner = files[RUNNER].decode("utf-8")
    observer = files[OBSERVER].decode("utf-8")
    contract = manifest.get("prepared_count_cause_diagnostic_contract", {})
    if manifest.get("test_id") != TEST_ID:
        errors.append("v24 test identity differs")
    if manifest.get("package_class") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("v24 package class differs")
    if contract.get("runtime_enable") != "+RETURN_OBS_PREP_COUNT_CAUSE":
        errors.append("prepared count runtime enable contract differs")
    if contract.get("runtime_limit") != (
        "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512"
    ):
        errors.append("prepared count runtime limit contract differs")
    if contract.get("clock") != "clk_sg":
        errors.append("prepared count clock owner differs")
    if contract.get("stable_level_counts_as_progress") is not False:
        errors.append("prepared count stable-level exclusion differs")
    if contract.get("read_only") is not True or (
        contract.get("drives_dut") is not False
    ):
        errors.append("prepared count read-only contract differs")
    bindings = {
        "+RETURN_OBS_PREP_COUNT_CAUSE": (
            "\n  +RETURN_OBS_PREP_COUNT_CAUSE\n" in runner
            and " +RETURN_OBS_PREP_COUNT_CAUSE +" in runner
        ),
        "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512": (
            "\n  +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512\n" in runner
            and " +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512 " in runner
        ),
        "prep_count_cause_enabled=true":
            "prep_count_cause_enabled=true" in runner,
        "prep_count_cause_records_returned=true":
            "prep_count_cause_records_returned=true" in runner,
    }
    for token, present in bindings.items():
        if not present:
            errors.append(f"runner prepared count binding absent: {token}")
    for token in (
        "RETURN_OBS_PREP_COUNT_CAUSE",
        "RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=%d",
        "prep_count_cause=%0d prep_count_cause_limit=%0d",
        *FEATURE_RECORDS,
    ):
        if token not in observer:
            errors.append(f"observer prepared count marker absent: {token}")
    for mse in (0, 3):
        if observer.count(f"MSE_INST[{mse}].RD_MSE") < len(XMR_LEAVES):
            errors.append(f"MSE{mse} prepared count XMR coverage differs")
    for leaf in XMR_LEAVES:
        if observer.count(leaf) < 2:
            errors.append(
                f"prepared count leaf not bound for both MSEs: {leaf}"
            )
    for token in (
        "return_obs_pc_wr_mon",
        "return_obs_pc_rd_mon",
        "return_obs_pc_count_change",
        "return_obs_pc_slice_rst_edge",
        "return_obs_pc_rst_n_edge",
        "return_obs_pc_no_effect_count",
    ):
        if token not in observer:
            errors.append(f"prepared count qualified evidence absent: {token}")
    for target in (
        "assign return_obs_pc_slice_rst_mon",
        "assign return_obs_pc_count_mon",
    ):
        if observer.count(target) != 2:
            errors.append(
                f"prepared count dedicated XMR assignment differs: {target}"
            )
    canonical = files[
        "package_tools/gap_node0071_canonical_decision.py"
    ].decode("utf-8")
    if "PREP_COUNT_CAUSE_" in canonical:
        errors.append(
            "prepared count diagnostic records incorrectly enter progress"
        )
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "prepared_count_cause_contract_valid": not any(
                "prepared count" in error for error in errors
            ),
        }
    )
    return result


def negative_controls(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    controls = [
        item
        for item in base.negative_controls(
            files, root_name, runner_report
        )
        if item["name"] != "rd_path_direct_consumer_xmr_removed"
    ]

    def run(
        name: str,
        mutated: dict[str, bytes],
        expected: str,
    ) -> None:
        check = validate_payload(mutated, root_name, runner_report)
        controls.append(
            {
                "name": name,
                "failed_closed": not check["valid"],
                "expected_error_observed": any(
                    expected in error for error in check["errors"]
                ),
                "errors": check["errors"],
            }
        )

    mutated = dict(files)
    mutated[RUNNER] = (
        files[RUNNER]
        .replace(b"  +RETURN_OBS_PREP_COUNT_CAUSE\n", b"", 1)
        .replace(b"+RETURN_OBS_PREP_COUNT_CAUSE ", b"", 1)
    )
    mutated = refresh(mutated, RUNNER)
    run(
        "prep_count_runtime_enable_removed",
        mutated,
        "runner prepared count binding absent",
    )

    mutated = dict(files)
    mutated[RUNNER] = (
        files[RUNNER]
        .replace(b"  +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512\n", b"", 1)
        .replace(b"+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512 ", b"", 1)
    )
    mutated = refresh(mutated, RUNNER)
    run(
        "prep_count_runtime_limit_removed",
        mutated,
        "runner prepared count binding absent",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"prep_count_cause=%0d prep_count_cause_limit=%0d",
        b"prep_count_marker_removed",
        1,
    )
    mutated = refresh(mutated, OBSERVER)
    run(
        "prep_count_time0_marker_removed",
        mutated,
        "observer prepared count marker absent",
    )

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"prep_count_cause_records_returned=true",
        b"prep_count_cause_records_returned=removed",
        1,
    )
    mutated = refresh(mutated, RUNNER)
    run(
        "prep_count_return_binding_removed",
        mutated,
        "runner prepared count binding absent",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"assign return_obs_pc_slice_rst_mon",
        b"assign return_obs_pc_slice_rst_removed",
        1,
    )
    mutated = refresh(mutated, OBSERVER)
    run(
        "prep_count_local_reset_xmr_removed",
        mutated,
        "prepared count dedicated XMR assignment differs",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"assign return_obs_pc_count_mon",
        b"assign return_obs_pc_count_removed",
        1,
    )
    mutated = refresh(mutated, OBSERVER)
    run(
        "prep_count_direct_counter_xmr_removed",
        mutated,
        "prepared count dedicated XMR assignment differs",
    )
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
        files = base.base.stage.factor.read_zip(
            args.zip_path, args.root_name
        )
        runner_report = (
            json.loads(args.runner_report.read_text(encoding="utf-8"))
            if args.runner_report
            else None
        )
        result = validate_payload(files, args.root_name, runner_report)
        controls = negative_controls(files, args.root_name, runner_report)
        result["negative_controls"] = controls
        result["all_negative_controls_fail_closed"] = all(
            item["failed_closed"] and item["expected_error_observed"]
            for item in controls
        )
        result["valid"] = (
            result["valid"]
            and result["all_negative_controls_fail_closed"]
        )
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
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
