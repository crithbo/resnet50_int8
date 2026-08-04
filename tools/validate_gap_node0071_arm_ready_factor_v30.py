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

from tools import validate_gap_node0071_mse0_buffer_prep_group0_v29 as base


ROOT_NAME = "r5_n71_gap_v30_arm_ready_factor_diag"
TEST_ID = "r5-gap-node0071-v30-buffer0-arm-read-ready-factor-diagnostic"
CURRENT_SERVER_RULE_SHA256 = (
    "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
)
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
FEATURE_RECORDS = [
    "BUFFER0_ARM_READY_FACTOR_EVENT_V1",
    "BUFFER0_ARM_READY_FACTOR_COUNTS_V1",
    "BUFFER0_ARM_READY_FACTOR_STATE_V1",
    "BUFFER0_ARM_READY_FACTOR_WITNESS_V1",
]
XMR_LEAVES = [
    ".u_Buffer.buffer_mask",
    ".u_Buffer.buf2arm_rreq_bank_ready",
    ".u_Buffer.arm_clear_reg",
    ".u_Buffer.nrm2buf_rd_barrier",
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
        if archive.testzip() is not None:
            raise ValueError("CRC differs")
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise ValueError("ZIP root differs")
            relative = info.filename[len(prefix):]
            if not relative or relative in files:
                raise ValueError("ZIP exact set differs")
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
    contract = manifest.get("buffer0_arm_ready_factor_diagnostic_contract", {})
    if manifest.get("test_id") != TEST_ID:
        errors.append("v30 test identity differs")
    if manifest.get("package_class") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        errors.append("v30 package class differs")
    if contract.get("runtime_enable") != "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS":
        errors.append("ARM-ready factor runtime enable contract differs")
    if contract.get("runtime_limit") != (
        "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256"
    ):
        errors.append("ARM-ready factor runtime limit contract differs")
    if contract.get("stable_level_counts_as_progress") is not False:
        errors.append("ARM-ready factor stable-level exclusion differs")
    if contract.get("read_only") is not True or contract.get("drives_dut") is not False:
        errors.append("ARM-ready factor read-only contract differs")
    runner_bindings = {
        "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS": (
            "\n  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS\n" in runner
            and " +RETURN_OBS_BUFFER0_ARM_READY_FACTORS " in runner
        ),
        "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256": (
            "\n  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256\n" in runner
            and " +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256 " in runner
        ),
        "buffer0_arm_ready_factors_enabled=true":
            "buffer0_arm_ready_factors_enabled=true" in runner,
        "buffer0_arm_ready_factors_records_returned=true":
            "buffer0_arm_ready_factors_records_returned=true" in runner,
    }
    for token, present in runner_bindings.items():
        if not present:
            errors.append(f"runner ARM-ready factor binding absent: {token}")
    for token in (
        "RETURN_OBS_BUFFER0_ARM_READY_FACTORS",
        "RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=%d",
        "buffer0_arm_ready_factors=%0d buffer0_arm_ready_factors_limit=%0d",
        *FEATURE_RECORDS,
    ):
        if token not in observer:
            errors.append(f"observer ARM-ready factor marker absent: {token}")
    for leaf in XMR_LEAVES:
        if observer.count(leaf + ";") != 1:
            errors.append(f"ARM-ready factor XMR leaf differs: {leaf}")
    for token in (
        "return_obs_armf_accept_count++;",
        "return_obs_armf_bank_edge_count++;",
        "return_obs_armf_barrier_edge_count++;",
        "return_obs_armf_ready_edge_count++;",
        "return_obs_armf_block_entry_count++;",
    ):
        if token not in observer:
            errors.append(f"ARM-ready qualified update absent: {token}")
    if (
        "(|return_obs_ga_group_out_tag_mon[return_obs_group_id]"
        "[return_obs_local_slice_id][0][0])"
    ) in observer:
        errors.append("v29 group0 stable-level expression remains")
    for token in (
        "m0_group0_accept |= return_obs_ga_group_out_tag_mon",
        "[m0_group_row][`GA_INPORT_TAG-1]",
        "m0_group0_accept &=",
    ):
        if token not in observer:
            errors.append(f"v30 qualified group0 correction absent: {token}")
    canonical = files[
        "package_tools/gap_node0071_canonical_decision.py"
    ].decode("utf-8")
    if "BUFFER0_ARM_READY_FACTOR_" in canonical:
        errors.append("ARM-ready factor records incorrectly enter progress")
    rtl = manifest.get("active_rtl_identity", {})
    if rtl.get("commit") != "d0aa87f682880a260fb792aaac88f70a23aba414":
        errors.append("active RTL identity differs")
    if rtl.get("gap_fix_assumed") is not False:
        errors.append("active RTL incorrectly assumed to fix GAP")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "arm_ready_factor_contract_valid": not any(
                "ARM-ready" in error for error in errors
            ),
            "v29_group0_observer_defect_corrected": not any(
                "group0" in error for error in errors
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

    def run(name: str, mutated: dict[str, bytes], changed: str, expected: str) -> None:
        mutated = base.base.refresh(mutated, changed)
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
        .replace(b"  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS\n", b"", 1)
        .replace(b"+RETURN_OBS_BUFFER0_ARM_READY_FACTORS ", b"", 1)
    )
    run(
        "arm_ready_runtime_enable_removed", mutated, RUNNER,
        "runner ARM-ready factor binding absent",
    )

    mutated = dict(files)
    mutated[RUNNER] = (
        files[RUNNER]
        .replace(b"  +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256\n", b"", 1)
        .replace(b"+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256 ", b"", 1)
    )
    run(
        "arm_ready_runtime_limit_removed", mutated, RUNNER,
        "runner ARM-ready factor binding absent",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"buffer0_arm_ready_factors=%0d buffer0_arm_ready_factors_limit=%0d",
        b"arm_ready_marker_removed",
        1,
    )
    run(
        "arm_ready_time0_removed", mutated, OBSERVER,
        "observer ARM-ready factor marker absent",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b".u_Buffer.nrm2buf_rd_barrier",
        b".u_Buffer.nrm_barrier_removed",
        1,
    )
    run(
        "arm_ready_barrier_xmr_removed", mutated, OBSERVER,
        "ARM-ready factor XMR leaf differs",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"return_obs_armf_block_entry_count++;",
        b"return_obs_armf_block_entry_removed++;",
        1,
    )
    run(
        "arm_ready_critical_update_removed", mutated, OBSERVER,
        "ARM-ready qualified update absent",
    )

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"[m0_group_row][`GA_INPORT_TAG-1]",
        b"[m0_group_row]",
        1,
    )
    run(
        "qualified_group0_valid_bit_removed", mutated, OBSERVER,
        "v30 qualified group0 correction absent",
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
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
