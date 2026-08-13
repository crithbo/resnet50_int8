from __future__ import annotations

import argparse
import json
import stat
import sys
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_buffer_ag_idx_queue_v33 as prior


ROOT_NAME = "r5_n71_gap_v36_dbclk_rdready_diag"
TEST_ID = "r5-gap-node0071-v36-dbclk-rdready-information-gain-diagnostic"
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
RECORDS = {
    "DBCLK_RD_READY_EVENT_V1",
    "DBCLK_RD_READY_COUNTS_V1",
    "DBCLK_RD_READY_STATE_V1",
    "DBCLK_RD_READY_WITNESS_V1",
}
CURRENT_RULE_SHA = "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1"


def configure() -> None:
    prior.base.ROOT_NAME = ROOT_NAME
    prior.base.TEST_ID = TEST_ID


def read_zip(path: Path, root_name: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    prefix = f"{root_name}/"
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC differs")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or not info.filename.startswith(prefix)
            ):
                raise ValueError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = pure.relative_to(root_name).as_posix()
            if relative in files:
                raise ValueError(f"duplicate ZIP member: {relative}")
            files[relative] = archive.read(info)
    return files


def validate_payload(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> dict[str, Any]:
    configure()
    result = prior.validate_payload(files, root_name, runner_report)
    inherited = list(result["errors"])
    stale_exact = {
        "test_id differs",
        "runner canonical manifest binding absent",
        "current server rule receipt differs",
        "material rule drift current SHA differs",
        "v21 test identity differs",
        "v24 test identity differs",
        "v28 test identity differs",
        "v29 test identity differs",
        "v30 test identity differs",
    }
    errors = [error for error in inherited if error not in stale_exact]
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    runner = files[RUNNER].decode()
    observer = files[OBSERVER].decode()
    contract = manifest.get("dbclk_rdready_information_gain_contract", {})
    bq_contract = manifest.get("buffer_ag_index_pair_diagnostic_contract", {})
    budget = manifest.get("path_length_budget", {})
    canonical = manifest.get("canonical_decision_contract", {})
    v34_sampler = observer.split(
        "// v34 sampler: all qualified events are sampled in their clk_db owner domain.",
        1,
    )[1].split(
        "// v33 sampler: qualified input accepts and FIFO accepts only.", 1
    )[0]
    v33_sampler = observer.split(
        "// v33 sampler: qualified input accepts and FIFO accepts only.", 1
    )[1].split(
        "// v31 sampler: accepted transactions only; stable levels are state.", 1
    )[0]
    checks = {
        "test_id": manifest.get("test_id") == TEST_ID,
        "identity_exact":
            manifest.get("install_name") == ROOT_NAME
            and manifest.get("run_name") == f"run_{ROOT_NAME}"
            and manifest.get("return_name") == f"{ROOT_NAME}_return"
            and f'install_name="{ROOT_NAME}"' in runner,
        "current_rule_receipt":
            manifest.get("rule_receipts", {}).get("server_rule_sha256")
            == CURRENT_RULE_SHA
            and manifest.get("rule_receipts", {}).get("current_match") is True,
        "diagnostic_only":
            manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
            and manifest.get("evidence_ceiling") == "E2_LOCAL_ONLY",
        "owner_clock_contract":
            contract.get("owner_clock") == "u_NDP_Top_new.clk (Slice clk_db)"
            and bq_contract.get("clock")
            == "u_NDP_Top_new.clk (Slice clk_db)"
            and bq_contract.get("v33_clk_sg_occurrence_evidence_superseded")
            is True,
        "owner_clock_implementation":
            "always @(posedge u_NDP_Top_new.clk)" in v34_sampler
            and "clk_sg" not in v34_sampler
            and "always @(posedge u_NDP_Top_new.clk)" in v33_sampler
            and "clk_sg" not in v33_sampler,
        "runtime_enable":
            "\n  +RETURN_OBS_DBCLK_RD_READY\n" in runner
            and " +RETURN_OBS_DBCLK_RD_READY " in runner,
        "runtime_limit":
            "\n  +RETURN_OBS_DBCLK_RD_READY_LIMIT=256\n" in runner
            and " +RETURN_OBS_DBCLK_RD_READY_LIMIT=256 " in runner,
        "runtime_receipt":
            "dbclk_rd_ready_enabled=true" in runner
            and "dbclk_rd_ready_records_returned=true" in runner,
        "time0":
            "dbclk_rd_ready=%0d dbclk_rd_ready_limit=%0d" in observer,
        "records": all(record in observer for record in RECORDS),
        "qualified_updates": all(
            token in v34_sampler
            for token in (
                "return_obs_dbrr_req_accept[dbrr_flow]++;",
                "return_obs_dbrr_queue_enqueue[dbrr_flow]++;",
                "return_obs_dbrr_queue_dequeue[dbrr_flow]++;",
                "return_obs_dbrr_ib_write[dbrr_flow]++;",
                "return_obs_dbrr_ib_read[dbrr_flow]++;",
                "return_obs_dbrr_prep_write[dbrr_flow]++;",
                "return_obs_dbrr_prep_read[dbrr_flow]++;",
                "return_obs_dbrr_wr_accept[dbrr_flow]++;",
            )
        ),
        "stable_not_progress":
            contract.get("stable_levels_count_as_progress") is False
            and "DBCLK_RD_READY_" not in files[
                "package_tools/gap_node0071_canonical_decision.py"
            ].decode(),
        "information_gain_matrix":
            len(contract.get("candidate_observation_matrix", {})) >= 6
            and contract.get("observer_budget", {}).get(
                "qualified_event_record_limit"
            )
            == 256,
        "causal_slice":
            contract.get("causal_slice", {}).get("drop") == []
            and contract.get("causal_slice", {}).get(
                "estimated_stage_reduction"
            )
            == "0/8",
        "path_budget":
            budget.get("max_projected_absolute_path_chars") == 240
            and budget.get("max_inner_suffix_chars") == 128
            and budget.get("measured_max_inner_suffix_chars", 999) <= 128
            and budget.get("measured_max_inner_depth", 999) <= 8
            and budget.get("measured_max_component_chars", 999) <= 48
            and budget.get("identity_repeated_in_inner_path") is False
            and "path_budget_preflight.json" in runner,
        "ordered_stage_scope":
            canonical.get("final_stage_scope_required") is True
            and len(canonical.get("expected_ordered_stage_list", [])) == 8,
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(f"v36 dbclk RD-ready contract differs: {name}")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "inherited_stale_identity_or_rule_receipt_errors_ignored": [
                error for error in inherited if error in stale_exact
            ],
            "dbclk_rdready_checks": checks,
            "dbclk_rdready_contract_valid": all(checks.values()),
        }
    )
    return result


def negative_controls(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    controls = prior.negative_controls(files, root_name, runner_report)

    def check(
        name: str, mutated: dict[str, bytes], changed: str, expected: str
    ) -> None:
        if changed != "TEST_PACKAGE_MANIFEST.json":
            mutated = prior.base.base.base.base.refresh(mutated, changed)
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
        b"  +RETURN_OBS_DBCLK_RD_READY\n", b"", 1
    ).replace(b"+RETURN_OBS_DBCLK_RD_READY ", b"", 1)
    check("dbrr_runtime_enable_removed", mutated, RUNNER, "runtime_enable")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"dbclk_rd_ready=%0d dbclk_rd_ready_limit=%0d",
        b"dbrr_time0_removed",
        1,
    )
    check("dbrr_time0_removed", mutated, OBSERVER, "time0")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"return_obs_dbrr_queue_enqueue[dbrr_flow]++;",
        b"return_obs_dbrr_queue_enqueue_removed[dbrr_flow]++;",
        1,
    )
    check("dbrr_critical_update_removed", mutated, OBSERVER, "qualified_updates")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"always @(posedge u_NDP_Top_new.clk)",
        b"always @(posedge u_NDP_Top_new.clk_sg)",
        1,
    )
    check("dbrr_owner_clock_reverted", mutated, OBSERVER, "owner_clock_implementation")

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    manifest["path_length_budget"]["measured_max_inner_suffix_chars"] = 129
    mutated = dict(files)
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    )
    check("path_budget_over_limit", mutated, "TEST_PACKAGE_MANIFEST.json", "path_budget")

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    manifest["path_length_budget"]["measured_max_inner_depth"] = 9
    mutated = dict(files)
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    )
    check("path_budget_deep_member", mutated, "TEST_PACKAGE_MANIFEST.json", "path_budget")

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    manifest["path_length_budget"]["identity_repeated_in_inner_path"] = True
    mutated = dict(files)
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    )
    check("path_budget_identity_repeated", mutated, "TEST_PACKAGE_MANIFEST.json", "path_budget")

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    manifest["install_name"] = "stale_gap_identity"
    mutated = dict(files)
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    )
    check("path_budget_stale_identity_reference", mutated, "TEST_PACKAGE_MANIFEST.json", "identity_exact")

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    manifest["canonical_decision_contract"]["expected_ordered_stage_list"] = []
    mutated = dict(files)
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    )
    check("ordered_stage_scope_removed", mutated, "TEST_PACKAGE_MANIFEST.json", "ordered_stage_scope")
    return controls


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument("--runner-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
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
        exit_code = 0 if result["valid"] else 1
    except Exception as error:
        result = {
            "valid": False,
            "status": "FAIL",
            "errors": [str(error)],
            "negative_controls": [],
            "all_negative_controls_fail_closed": False,
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
