from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_ga_mse4_final_pair_v28 as base


ROOT_NAME = "r5_n71_gap_v29_mse0_buffer_prep_group0_diag"
TEST_ID = "r5-gap-node0071-v29-mse0-buffer-prepared-group0-diagnostic"
CURRENT_SERVER_RULE_SHA256 = (
    "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
)
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
FEATURE_RECORDS = [
    "MSE0_BUFFER_PREP_GROUP0_EVENT_V1",
    "MSE0_BUFFER_PREP_GROUP0_COUNTS_V1",
    "MSE0_BUFFER_PREP_GROUP0_STATE_V1",
    "MSE0_BUFFER_PREP_GROUP0_WITNESS_V1",
]


def configure() -> None:
    base.ROOT_NAME = ROOT_NAME
    base.TEST_ID = TEST_ID
    base.CURRENT_SERVER_RULE_SHA256 = CURRENT_SERVER_RULE_SHA256
    base.configure()


def read_zip(path: Path, root_name: str) -> dict[str, bytes]:
    prefix = root_name + "/"
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"CRC failure: {bad}")
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise ValueError("ZIP root differs")
            relative = info.filename[len(prefix):]
            if not relative or relative in files:
                raise ValueError("ZIP member set differs")
            files[relative] = archive.read(info)
    return files


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
    contract = manifest.get(
        "mse0_buffer_prepared_group0_diagnostic_contract", {}
    )
    if manifest.get("test_id") != TEST_ID:
        errors.append("v29 test identity differs")
    if manifest.get("package_class") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("v29 package class differs")
    if contract.get("runtime_enable") != "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0":
        errors.append("MSE0 path runtime enable contract differs")
    if contract.get("runtime_limit") != (
        "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512"
    ):
        errors.append("MSE0 path runtime limit contract differs")
    if contract.get("clock") != "clk_sg":
        errors.append("MSE0 path clock owner differs")
    if contract.get("stable_level_counts_as_progress") is not False:
        errors.append("MSE0 path stable-level exclusion differs")
    if contract.get("read_only") is not True or (
        contract.get("drives_dut") is not False
    ):
        errors.append("MSE0 path read-only contract differs")
    bindings = {
        "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0": (
            "\n  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0\n" in runner
            and " +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0 " in runner
        ),
        "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512": (
            "\n  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512\n" in runner
            and " +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512 " in runner
        ),
        "mse0_buffer_prep_group0_enabled=true":
            "mse0_buffer_prep_group0_enabled=true" in runner,
        "mse0_buffer_prep_group0_records_returned=true":
            "mse0_buffer_prep_group0_records_returned=true" in runner,
    }
    for token, present in bindings.items():
        if not present:
            errors.append(f"runner MSE0 path binding absent: {token}")
    for token in (
        "RETURN_OBS_MSE0_BUFFER_PREP_GROUP0",
        "RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=%d",
        "mse0_buffer_prep_group0=%0d mse0_buffer_prep_group0_limit=%0d",
        *FEATURE_RECORDS,
    ):
        if token not in observer:
            errors.append(f"observer MSE0 path marker absent: {token}")
    for token in (
        "return_obs_m0path_buf_accept_count",
        "return_obs_m0path_arm_accept_count",
        "return_obs_m0path_arm_clear_count",
        "return_obs_m0path_prep_wr_count",
        "return_obs_m0path_prep_rd_count",
        "return_obs_m0path_data_vld_count",
        "return_obs_m0path_group0_accept_count",
    ):
        if token not in observer:
            errors.append(f"MSE0 path qualified counter absent: {token}")
    if "return_obs_m0path_group0_accept_count++;" not in observer:
        errors.append("MSE0 path critical group0 update absent")
    canonical = files[
        "package_tools/gap_node0071_canonical_decision.py"
    ].decode("utf-8")
    if "MSE0_BUFFER_PREP_GROUP0_" in canonical:
        errors.append("MSE0 path diagnostic records incorrectly enter progress")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "mse0_buffer_prep_group0_contract_valid": not any(
                "MSE0 path" in error for error in errors
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
        mutated = base.refresh(mutated, next(
            path for path in (RUNNER, OBSERVER)
            if mutated.get(path) != files.get(path)
        ))
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
        .replace(b"  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0\n", b"", 1)
        .replace(b"+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0 ", b"", 1)
    )
    run("mse0_path_runtime_enable_removed", mutated, "runner MSE0 path binding absent")

    mutated = dict(files)
    mutated[RUNNER] = (
        files[RUNNER]
        .replace(
            b"  +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512\n", b"", 1
        )
        .replace(b"+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512 ", b"", 1)
    )
    run("mse0_path_runtime_limit_removed", mutated, "runner MSE0 path binding absent")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"mse0_buffer_prep_group0=%0d mse0_buffer_prep_group0_limit=%0d",
        b"mse0_path_marker_removed",
        1,
    )
    run("mse0_path_time0_marker_removed", mutated, "observer MSE0 path marker absent")

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"mse0_buffer_prep_group0_records_returned=true",
        b"mse0_buffer_prep_group0_records_returned=removed",
        1,
    )
    run("mse0_path_return_binding_removed", mutated, "runner MSE0 path binding absent")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"return_obs_m0path_group0_accept_count++;",
        b"return_obs_m0path_group0_accept_removed++;",
        1,
    )
    run(
        "mse0_path_critical_update_removed",
        mutated,
        "MSE0 path critical group0 update absent",
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
        files = read_zip(args.zip_path, args.root_name)
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
