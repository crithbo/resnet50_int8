from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from resnet50_pipeline.hashing import sha256_file
from resnet50_pipeline.node0075_negative_psum_reachability import (
    Node0075NegativePsumError,
    build_report,
    write_report,
)


DEFAULT_CONTRACT = Path(
    "contracts/operator_config/"
    "node0075_negative_psum_reachability_v1.json"
)
DEFAULT_REPORT = Path(
    "artifacts/operator_config_validation/"
    "r5-node0075-negative-psum-reachability-v1/report.json"
)


def _assert_terminal_contract(contract: dict) -> None:
    if contract.get("status") != "HARDWARE_CAPABILITY_BLOCKED":
        raise Node0075NegativePsumError("terminal status differs")
    if contract.get("package_release") != "NONE":
        raise Node0075NegativePsumError("package release must remain NONE")
    scan = contract["exact_occurrence_scan"]
    if scan["enumerated_occurrence_count"] != 8_192_000:
        raise Node0075NegativePsumError("occurrence count differs")
    if scan["boundary_hit_count"] != 272:
        raise Node0075NegativePsumError("boundary hit count differs")
    if scan["formal_final_accumulator_match"] is not True:
        raise Node0075NegativePsumError("formal final accumulator differs")
    witness = contract["current_rtl_witness"]
    if (
        witness["current_rtl_mismatch_reproduced"] is not True
        or witness["observed_result_bits"] != "0x80000000"
        or witness["expected_math_bits"] != "0x00000000"
    ):
        raise Node0075NegativePsumError("current RTL mismatch receipt differs")
    if any(contract["outputs"].values()):
        raise Node0075NegativePsumError("downstream output claimed after blocker")
    accounting = contract["materializer_and_reload_accounting"]
    if (
        accounting["actual_materialized_reload_passes"] != 0
        or accounting["actual_materialized_accepted_a_traffic_bytes"] != 0
    ):
        raise Node0075NegativePsumError(
            "unmaterialized reload traffic was claimed"
        )


def _fails_closed(contract: dict) -> bool:
    try:
        _assert_terminal_contract(contract)
    except Node0075NegativePsumError:
        return True
    return False


def _negative_controls(contract: dict) -> dict[str, bool]:
    controls: dict[str, bool] = {}

    missing_hit = copy.deepcopy(contract)
    missing_hit["exact_occurrence_scan"]["boundary_hit_count"] = 0
    controls["zero_boundary_hits_fail_closed"] = _fails_closed(missing_hit)

    fake_e2 = copy.deepcopy(contract)
    fake_e2["outputs"]["config_bound_e2"] = True
    controls["premature_e2_claim_fail_closed"] = _fails_closed(fake_e2)

    fake_reload = copy.deepcopy(contract)
    fake_reload["materializer_and_reload_accounting"][
        "actual_materialized_reload_passes"
    ] = 8
    controls["unmaterialized_reload_claim_fail_closed"] = _fails_closed(
        fake_reload
    )

    fake_rtl = copy.deepcopy(contract)
    fake_rtl["current_rtl_witness"]["observed_result_bits"] = "0x00000000"
    controls["rtl_mismatch_erasure_fail_closed"] = _fails_closed(fake_rtl)
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    contract_path = (
        args.contract if args.contract.is_absolute() else root / args.contract
    )
    report_path = args.report if args.report.is_absolute() else root / args.report
    stored = json.loads(contract_path.read_text(encoding="utf-8"))
    expected = build_report(root)
    controls = _negative_controls(stored)
    _assert_terminal_contract(stored)

    checks = {
        "stored_matches_current_deterministic_build": stored == expected,
        "terminal_status_exact": stored.get("status")
        == "HARDWARE_CAPABILITY_BLOCKED",
        "package_release_none": stored.get("package_release") == "NONE",
        "all_occurrences_enumerated": stored["exact_occurrence_scan"][
            "enumerated_occurrence_count"
        ]
        == 8_192_000,
        "boundary_reachable": stored["exact_occurrence_scan"][
            "boundary_hit_count"
        ]
        == 272,
        "formal_final_accumulator_matches": stored["exact_occurrence_scan"][
            "formal_final_accumulator_match"
        ]
        is True,
        "current_rtl_witness_mismatch": stored["current_rtl_witness"][
            "current_rtl_mismatch_reproduced"
        ]
        is True,
        "no_target_or_package_outputs": not any(stored["outputs"].values()),
        "actual_reload_and_traffic_zero": (
            stored["materializer_and_reload_accounting"][
                "actual_materialized_reload_passes"
            ]
            == 0
            and stored["materializer_and_reload_accounting"][
                "actual_materialized_accepted_a_traffic_bytes"
            ]
            == 0
        ),
        "negative_controls_pass": all(controls.values()),
    }
    passed = all(checks.values())
    report = {
        "schema": "node0075-negative-psum-reachability-validation-v1",
        "status": "PASS" if passed else "FAIL",
        "contract_path": contract_path.relative_to(root).as_posix(),
        "contract_sha256": sha256_file(contract_path),
        "checks": checks,
        "negative_controls": controls,
        "claim_boundary": stored.get("claim_boundary"),
    }
    write_report(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if not passed:
        raise Node0075NegativePsumError(
            "node0075 negative-psum reachability validation failed"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
