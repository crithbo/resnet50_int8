from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_prep_count_cause_v24 as base


ROOT_NAME = "r5_n71_gap_v28_ga_mse4_final_pair_diag"
TEST_ID = "r5-gap-node0071-v28-ga-mse4-final-pair-diagnostic"
CURRENT_SERVER_RULE_SHA256 = (
    "559ce2660cfe34d567ab45f6c2573f7d0ad2ad3f3d751337432616ce9a9690b2"
)
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
FEATURE_RECORDS = [
    "GA_MSE4_FINAL_PAIR_GA_EVENT_V1",
    "GA_MSE4_FINAL_PAIR_M4_EVENT_V1",
    "GA_MSE4_FINAL_PAIR_COUNTS_V1",
    "GA_MSE4_FINAL_PAIR_STATE_V1",
    "GA_MSE4_FINAL_PAIR_WITNESS_V1",
]
MSE4_XMR_LEAVES = [
    ".wr_data_chl_req_valid",
    ".wr_data_chl_req_ready",
    ".wr_chl_queue_wr_en",
    ".wr_chl_queue_rd_en",
    ".wr_chl_queue_full",
    ".wr_chl_queue_empty",
    ".buf2mse_rvalid",
    ".wr_data_chl_ready",
    ".buf_ag_last_req_flag",
    ".wr_data_chl_hold_data_vld",
    ".wr_data_chl_prepared_data_wr_hs",
    ".wr_data_chl_prepared_data_rd_hs",
    ".wr_data_chl_prepared_data_vld",
    ".wr_data_chl_prepared_data_cnt",
    ".wr_chl_ob_vld_in",
    ".wr_chl_ob_wr_hs",
    ".wr_chl_ob_rd_hs",
    ".wr_chl_ob_vld",
    ".wr_chl_ob_vld_o",
    ".mem2mse_wdata_ready",
    ".wr_data_chl_ob_last_data_flag",
    ".wr_data_chl_ob_last_data_arv_arr_flag",
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
    contract = manifest.get("ga_mse4_final_pair_diagnostic_contract", {})
    if manifest.get("test_id") != TEST_ID:
        errors.append("v28 test identity differs")
    if manifest.get("package_class") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("v28 package class differs")
    if contract.get("runtime_enable") != "+RETURN_OBS_GA_MSE4_FINAL_PAIR":
        errors.append("GA/MSE4 pair runtime enable contract differs")
    if contract.get("runtime_limit") != (
        "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512"
    ):
        errors.append("GA/MSE4 pair runtime limit contract differs")
    if contract.get("clock") != "clk_sg":
        errors.append("GA/MSE4 pair clock owner differs")
    if contract.get("stable_level_counts_as_progress") is not False:
        errors.append("GA/MSE4 pair stable-level exclusion differs")
    if contract.get("read_only") is not True or (
        contract.get("drives_dut") is not False
    ):
        errors.append("GA/MSE4 pair read-only contract differs")
    bindings = {
        "+RETURN_OBS_GA_MSE4_FINAL_PAIR": (
            "\n  +RETURN_OBS_GA_MSE4_FINAL_PAIR\n" in runner
            and " +RETURN_OBS_GA_MSE4_FINAL_PAIR +" in runner
        ),
        "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512": (
            "\n  +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512\n" in runner
            and " +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512 " in runner
        ),
        "ga_mse4_final_pair_enabled=true":
            "ga_mse4_final_pair_enabled=true" in runner,
        "ga_mse4_final_pair_records_returned=true":
            "ga_mse4_final_pair_records_returned=true" in runner,
    }
    for token, present in bindings.items():
        if not present:
            errors.append(f"runner GA/MSE4 pair binding absent: {token}")
    for token in (
        "RETURN_OBS_GA_MSE4_FINAL_PAIR",
        "RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=%d",
        "ga_mse4_final_pair=%0d ga_mse4_final_pair_limit=%0d",
        *FEATURE_RECORDS,
    ):
        if token not in observer:
            errors.append(f"observer GA/MSE4 pair marker absent: {token}")
    for leaf in MSE4_XMR_LEAVES:
        if leaf not in observer:
            errors.append(f"GA/MSE4 required MSE4 XMR leaf absent: {leaf}")
    for leaf in (
        ".normal_mode_wr_req",
        ".normal_mode_wr_handshake",
        ".normal_mode_rd_handshake",
        ".ga_pe_outbuffer_full",
    ):
        if observer.count(leaf) != 2:
            errors.append(f"GA/MSE4 two-column GA XMR leaf differs: {leaf}")
    for token in (
        "return_obs_pair_ga_accept_count",
        "return_obs_pair_ga_p0_retire_count",
        "return_obs_pair_m4_req_accept_count",
        "return_obs_pair_m4_buf_accept_count",
        "return_obs_pair_m4_ob_wr_count",
        "return_obs_pair_m4_ob_rd_count",
    ):
        if token not in observer:
            errors.append(f"GA/MSE4 qualified counter absent: {token}")
    canonical = files[
        "package_tools/gap_node0071_canonical_decision.py"
    ].decode("utf-8")
    if "GA_MSE4_FINAL_PAIR_" in canonical:
        errors.append("GA/MSE4 diagnostic records incorrectly enter progress")
    hdl_rule = (
        "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
    )
    applicable = manifest.get(
        "final_zip_rule_self_audit_contract", {}
    ).get("applicable_rule_ids", [])
    if hdl_rule not in applicable:
        errors.append("current focused package-local HDL rule receipt absent")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "ga_mse4_final_pair_contract_valid": not any(
                "GA/MSE4" in error for error in errors
            ),
        }
    )
    return result


def negative_controls(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    controls = base.negative_controls(files, root_name, runner_report)

    def run(name: str, mutated: dict[str, bytes], expected: str) -> None:
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
        .replace(b"  +RETURN_OBS_GA_MSE4_FINAL_PAIR\n", b"", 1)
        .replace(b"+RETURN_OBS_GA_MSE4_FINAL_PAIR ", b"", 1)
    )
    mutated = refresh(mutated, RUNNER)
    run(
        "ga_mse4_pair_runtime_enable_removed",
        mutated,
        "runner GA/MSE4 pair binding absent",
    )

    mutated = dict(files)
    mutated[RUNNER] = (
        files[RUNNER]
        .replace(
            b"  +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512\n", b"", 1
        )
        .replace(b"+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512 ", b"", 1)
    )
    mutated = refresh(mutated, RUNNER)
    run(
        "ga_mse4_pair_runtime_limit_removed",
        mutated,
        "runner GA/MSE4 pair binding absent",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"ga_mse4_final_pair=%0d ga_mse4_final_pair_limit=%0d",
        b"ga_mse4_pair_marker_removed",
        1,
    )
    mutated = refresh(mutated, OBSERVER)
    run(
        "ga_mse4_pair_time0_marker_removed",
        mutated,
        "observer GA/MSE4 pair marker absent",
    )

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"ga_mse4_final_pair_records_returned=true",
        b"ga_mse4_final_pair_records_returned=removed",
        1,
    )
    mutated = refresh(mutated, RUNNER)
    run(
        "ga_mse4_pair_return_binding_removed",
        mutated,
        "runner GA/MSE4 pair binding absent",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b".wr_data_chl_ob_last_data_arv_arr_flag",
        b".wr_data_chl_ob_last_data_arv_arr_removed",
        1,
    )
    mutated = refresh(mutated, OBSERVER)
    run(
        "ga_mse4_pair_finish_xmr_removed",
        mutated,
        "GA/MSE4 required MSE4 XMR leaf absent",
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
        files = base.base.base.stage.factor.read_zip(
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
            result["valid"] and result["all_negative_controls_fail_closed"]
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
