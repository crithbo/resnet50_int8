from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_bp_pre_factor_diag_v20 as base


ROOT_NAME = "r5_n71_gap_v23_rd_data_vld_path_rulefix"
TEST_ID = "r5-gap-node0071-v23-rd-data-vld-path-rulefix"
CURRENT_SERVER_RULE_SHA256 = (
    "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
)
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
FEATURE_RECORDS = [
    "RD_DATA_VLD_PATH_EVENT_V1",
    "RD_DATA_VLD_PATH_COUNTS_V1",
    "RD_DATA_VLD_PATH_STATE_V1",
    "RD_DATA_VLD_PATH_WITNESS_V1",
]
XMR_LEAVES = [
    "rd_data_chl_req_valid",
    "rd_data_chl_req_ready",
    "rd_chl_queue_wr_en",
    "rd_chl_queue_rd_en",
    "rd_chl_queue_full",
    "rd_chl_queue_empty",
    "mem2mse_rdata_valid",
    "mse2mem_rdata_ready",
    "rd_chl_ib_wr_hs",
    "rd_chl_ib_rd_hs",
    "rd_chl_ib_vld",
    "rd_chl_ib_sel",
    "rd_data_chl_prepared_data_wr_hs",
    "rd_data_chl_prepared_data_rd_hs",
    "rd_data_chl_prepared_data_cnt",
    "rd_chl_queue_rd_tsf_size",
    "mse_buf_spatial_size",
    "rd_data_chl_data_vld",
]


def configure() -> None:
    base.configure()
    base.ROOT_NAME = ROOT_NAME
    base.TEST_ID = TEST_ID
    base.stage.ROOT_NAME = ROOT_NAME
    base.stage.TEST_ID = TEST_ID
    base.stage.SERVER_RULE_SHA256 = CURRENT_SERVER_RULE_SHA256
    base.stage.factor.ROOT_NAME = ROOT_NAME
    base.stage.factor.TEST_ID = TEST_ID


def refresh(files: dict[str, bytes], path: str) -> dict[str, bytes]:
    return base.stage.factor._refresh_record(files, path)


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
    contract = manifest.get("rd_data_vld_path_diagnostic_contract", {})
    if manifest.get("test_id") != TEST_ID:
        errors.append("v21 test identity differs")
    if manifest.get("package_class") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("v21 package class differs")
    if contract.get("runtime_enable") != "+RETURN_OBS_RD_DATA_PATH":
        errors.append("RD path runtime enable contract differs")
    if contract.get("runtime_limit") != "+RETURN_OBS_RD_DATA_PATH_LIMIT=512":
        errors.append("RD path runtime limit contract differs")
    if contract.get("clock") != "clk_sg":
        errors.append("RD path clock owner differs")
    if contract.get("stable_level_counts_as_progress") is not False:
        errors.append("RD path stable-level exclusion differs")
    if contract.get("read_only") is not True or contract.get("drives_dut") is not False:
        errors.append("RD path read-only contract differs")
    runner_bindings = {
        "+RETURN_OBS_RD_DATA_PATH": (
            "\n  +RETURN_OBS_RD_DATA_PATH\n" in runner
            and " +RETURN_OBS_RD_DATA_PATH +" in runner
        ),
        "+RETURN_OBS_RD_DATA_PATH_LIMIT=512": (
            "\n  +RETURN_OBS_RD_DATA_PATH_LIMIT=512\n" in runner
            and " +RETURN_OBS_RD_DATA_PATH_LIMIT=512 " in runner
        ),
        "rd_data_vld_path_enabled=true":
            "rd_data_vld_path_enabled=true" in runner,
        "rd_data_vld_path_records_returned=true":
            "rd_data_vld_path_records_returned=true" in runner,
    }
    for token, present in runner_bindings.items():
        if not present:
            errors.append(f"runner RD path binding absent: {token}")
    for token in (
        "RETURN_OBS_RD_DATA_PATH",
        "RETURN_OBS_RD_DATA_PATH_LIMIT=%d",
        "rd_data_path=%0d rd_data_path_limit=%0d",
        *FEATURE_RECORDS,
    ):
        if token not in observer:
            errors.append(f"observer RD path marker absent: {token}")
    for mse in (0, 3):
        if observer.count(f"MSE_INST[{mse}].RD_MSE") < len(XMR_LEAVES):
            errors.append(f"MSE{mse} RD path XMR coverage count differs")
    for leaf in XMR_LEAVES:
        if observer.count(leaf) < 2:
            errors.append(f"RD path leaf not bound for both MSEs: {leaf}")
    for event in (
        "return_obs_rd_req_valid_mon",
        "return_obs_rd_mem_vld_mon",
        "return_obs_rd_ib_wr_hs_mon",
        "return_obs_rd_ib_rd_hs_mon",
        "return_obs_rd_prep_wr_mon",
        "return_obs_rd_prep_rd_mon",
    ):
        if event not in observer:
            errors.append(f"qualified RD event absent: {event}")
    canonical = files[
        "package_tools/gap_node0071_canonical_decision.py"
    ].decode("utf-8")
    if "RD_DATA_VLD_PATH_" in canonical:
        errors.append("RD state/edge records incorrectly enter canonical progress")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "rd_data_vld_path_contract_valid": not any(
                "RD path" in error or "qualified RD" in error
                for error in errors
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
        .replace(b"  +RETURN_OBS_RD_DATA_PATH\n", b"", 1)
        .replace(b"+RETURN_OBS_RD_DATA_PATH ", b"", 1)
    )
    mutated = refresh(mutated, RUNNER)
    run("rd_path_runtime_enable_removed", mutated, "runner RD path binding absent")

    mutated = dict(files)
    mutated[RUNNER] = (
        files[RUNNER]
        .replace(b"  +RETURN_OBS_RD_DATA_PATH_LIMIT=512\n", b"", 1)
        .replace(b"+RETURN_OBS_RD_DATA_PATH_LIMIT=512 ", b"", 1)
    )
    mutated = refresh(mutated, RUNNER)
    run("rd_path_runtime_limit_removed", mutated, "runner RD path binding absent")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"rd_data_path=%0d rd_data_path_limit=%0d",
        b"rd_path_marker_removed",
        1,
    )
    mutated = refresh(mutated, OBSERVER)
    run("rd_path_time0_marker_removed", mutated, "observer RD path marker absent")

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"rd_data_vld_path_records_returned=true",
        b"rd_data_vld_path_records_returned=removed",
        1,
    )
    mutated = refresh(mutated, RUNNER)
    run("rd_path_return_binding_removed", mutated, "runner RD path binding absent")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b".rd_data_chl_prepared_data_wr_hs",
        b".rd_data_chl_prepared_data_wr_removed",
        1,
    )
    mutated = refresh(mutated, OBSERVER)
    run("rd_path_direct_consumer_xmr_removed", mutated, "RD path leaf not bound")
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
        files = base.stage.factor.read_zip(args.zip_path, args.root_name)
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
