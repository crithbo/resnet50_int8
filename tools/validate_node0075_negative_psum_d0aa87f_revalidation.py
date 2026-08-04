from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_node0075_negative_psum_d0aa87f_revalidation import (  # noqa: E402
    build,
    sha256_file,
)


DEFAULT_CONTRACT = Path(
    "contracts/operator_config/"
    "node0075_negative_psum_d0aa87f_revalidation_v1.json"
)
DEFAULT_REPORT = Path(
    "artifacts/operator_config_validation/"
    "r5-node0075-negative-psum-d0aa87f-revalidation-v1/report.json"
)

EXPECTED_RTL = {
    "SA_PE_Float_CSA.v": (
        "429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a"
    ),
    "SA_PE_Float_Control.v": (
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
    ),
    "functional_fix_commit": "cb11353d4196b4af26aac18b4dcc39ba0027e8bc",
    "trassic_commit": "d0aa87f682880a260fb792aaac88f70a23aba414",
}
BLOCKER = "B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE"


class Node0075D0aa87fRevalidationError(RuntimeError):
    pass


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Node0075D0aa87fRevalidationError(message)


def assert_terminal_contract(root: Path, contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema")
        == "resnet50-node0075-negative-psum-d0aa87f-revalidation-v1",
        "schema differs",
    )
    _require(
        contract.get("status") == "HARDWARE_CAPABILITY_BLOCKED",
        "terminal status differs",
    )
    _require(contract.get("package_release") == "NONE", "package release differs")
    _require(contract.get("candidate_release") is False, "candidate must be false")
    _require(
        contract.get("current_rtl_identity") == EXPECTED_RTL,
        "current RTL identity differs",
    )

    directed = contract["directed_rtl_gate"]
    _require(directed["compile_exit"] == 0, "directed compile did not pass")
    _require(directed["simulation_exit"] == 0, "directed simulation did not pass")
    exact = directed["cases"]["neg19_plus19"]
    _require(exact["pass"] is False, "exact-cancellation mismatch was erased")
    _require(exact["magnitude_bits"] == "0x00000013", "magnitude receipt differs")
    _require(exact["csa_raw_bits"] == "0x00000000", "CSA raw receipt differs")
    _require(exact["int_result_sign"] == "1", "result sign receipt differs")
    _require(exact["observed_bits"] == "0x80000000", "observed bits differ")
    _require(exact["expected_bits"] == "0x00000000", "expected bits differ")
    for label in (
        "neg20_plus19",
        "neg18_plus19",
        "zero_plus19",
        "pos7_plus19",
    ):
        _require(
            directed["cases"][label]["pass"] is True,
            f"adjacent control {label} did not pass",
        )

    scan = contract["full_frozen_recurrence_gate"]
    _require(scan["complete"] is True, "recurrence is not complete")
    _require(
        scan["planned_occurrences"]
        == scan["enumerated_occurrences"]
        == 8_192_000,
        "recurrence occurrence count differs",
    )
    _require(
        scan["negative_psum_occurrences"] == 4_343_952,
        "negative psum count differs",
    )
    _require(scan["negative_to_exact_zero"] == 272, "boundary count differs")
    _require(scan["dot4_range"] == [-3539, 13286], "dot4 range differs")
    _require(scan["psum_in_range"] == [-45141, 121038], "psum range differs")
    _require(scan["formal_accumulator_match"] is True, "formal match differs")
    _require(
        scan["formal_accumulator_mismatch_count"] == 0,
        "formal mismatch count differs",
    )
    first = scan["first_stream_order_hit"]
    _require(
        (first["m"], first["n"], first["k_group"]) == (0, 65, 3),
        "first stream-order occurrence differs",
    )
    _require(first["a_u8_lanes"] == [28, 13, 1, 0], "first A lanes differ")
    _require(first["b_s8_lanes"] == [1, -2, 17, -2], "first B lanes differ")
    _require(first["psum_in_s32"] == -19, "first psum differs")
    _require(first["dot4_s32"] == 19, "first dot4 differs")
    _require(first["expected_next_s32"] == 0, "first next value differs")

    divergence = contract["first_divergence"]
    _require(divergence["id"] == BLOCKER, "first blocker differs")
    _require(divergence["witness"] == first, "first blocker witness differs")
    _require(divergence["config_expressible"] is False, "leaf claimed configurable")
    _require(
        divergence["functional_rtl_mutation_authorized"] is False,
        "unauthorized RTL mutation claimed",
    )
    _require(
        contract["blocker_delta"]["retained_exact"] == [BLOCKER],
        "retained blocker list differs",
    )
    _require(
        contract["blocker_delta"]["closed"] == [],
        "a blocker was falsely closed",
    )

    traffic = contract["materializer_and_traffic"]
    _require(
        (
            traffic["actual_materialized_reload_passes"],
            traffic["actual_accepted_32byte_reads"],
            traffic["actual_accepted_a_traffic_bytes"],
            traffic["actual_unique_consumer_accepted_bytes"],
        )
        == (0, 0, 0, 0),
        "unmaterialized consumer traffic was claimed",
    )
    authorized = traffic["authorized_post_fix_minimum"]
    _require(
        (
            authorized["passes"],
            authorized["accepted_reads_per_slice"],
            authorized["accepted_reads_total"],
            authorized["accepted_a_traffic_bytes"],
            authorized["unique_producer_owned_storage_bytes"],
        )
        == (8, 512, 8192, 262144, 32768),
        "authorized post-fix accounting differs",
    )
    _require(not any(contract["outputs"].values()), "downstream output was claimed")
    _require(
        contract["rule_delta_proposal"]["required"] is False,
        "unexpected public rule delta",
    )

    receipts = contract["source_receipts"]
    for relative, expected_sha in receipts.items():
        path = root / relative
        _require(path.is_file(), f"source receipt missing: {relative}")
        _require(
            sha256_file(path) == expected_sha,
            f"source receipt drifted: {relative}",
        )


def fails_closed(root: Path, contract: dict[str, Any]) -> bool:
    try:
        assert_terminal_contract(root, contract)
    except (KeyError, TypeError, Node0075D0aa87fRevalidationError):
        return True
    return False


def negative_controls(root: Path, contract: dict[str, Any]) -> dict[str, bool]:
    controls: dict[str, bool] = {}

    corrected = copy.deepcopy(contract)
    exact = corrected["directed_rtl_gate"]["cases"]["neg19_plus19"]
    exact["pass"] = True
    exact["observed_bits"] = "0x00000000"
    controls["exact_mismatch_erasure_fail_closed"] = fails_closed(root, corrected)

    unreachable = copy.deepcopy(contract)
    unreachable["full_frozen_recurrence_gate"]["negative_to_exact_zero"] = 0
    controls["zero_reachable_hits_fail_closed"] = fails_closed(root, unreachable)

    fake_materializer = copy.deepcopy(contract)
    traffic = fake_materializer["materializer_and_traffic"]
    traffic["actual_materialized_reload_passes"] = 8
    traffic["actual_accepted_32byte_reads"] = 8192
    traffic["actual_accepted_a_traffic_bytes"] = 262144
    controls["unmaterialized_traffic_claim_fail_closed"] = fails_closed(
        root, fake_materializer
    )

    fake_output = copy.deepcopy(contract)
    fake_output["outputs"]["config_bound_e2"] = True
    controls["premature_e2_claim_fail_closed"] = fails_closed(root, fake_output)

    stale_rtl = copy.deepcopy(contract)
    stale_rtl["current_rtl_identity"]["trassic_commit"] = "8f2f318"
    controls["stale_rtl_identity_fail_closed"] = fails_closed(root, stale_rtl)

    release = copy.deepcopy(contract)
    release["candidate_release"] = True
    release["package_release"] = "PACKAGE_READY_NOT_RUN"
    controls["premature_package_claim_fail_closed"] = fails_closed(root, release)
    return controls


def validate(root: Path, contract: dict[str, Any]) -> dict[str, Any]:
    expected = build(root)
    assert_terminal_contract(root, contract)
    controls = negative_controls(root, contract)
    checks = {
        "stored_matches_current_deterministic_build": contract == expected,
        "current_rtl_identity_exact": contract["current_rtl_identity"]
        == EXPECTED_RTL,
        "directed_exact_mismatch_reproduced": (
            contract["directed_rtl_gate"]["cases"]["neg19_plus19"][
                "observed_bits"
            ]
            == "0x80000000"
        ),
        "all_adjacent_controls_pass": all(
            contract["directed_rtl_gate"]["cases"][label]["pass"] is True
            for label in (
                "neg20_plus19",
                "neg18_plus19",
                "zero_plus19",
                "pos7_plus19",
            )
        ),
        "complete_recurrence_reaches_boundary": (
            contract["full_frozen_recurrence_gate"]["enumerated_occurrences"]
            == 8_192_000
            and contract["full_frozen_recurrence_gate"][
                "negative_to_exact_zero"
            ]
            == 272
        ),
        "formal_accumulator_matches": contract["full_frozen_recurrence_gate"][
            "formal_accumulator_mismatch_count"
        ]
        == 0,
        "blocker_retained": contract["blocker_delta"]["retained_exact"]
        == [BLOCKER],
        "actual_materializer_and_traffic_zero": all(
            contract["materializer_and_traffic"][field] == 0
            for field in (
                "actual_materialized_reload_passes",
                "actual_accepted_32byte_reads",
                "actual_accepted_a_traffic_bytes",
                "actual_unique_consumer_accepted_bytes",
            )
        ),
        "no_downstream_outputs": not any(contract["outputs"].values()),
        "package_release_none": contract["package_release"] == "NONE"
        and contract["candidate_release"] is False,
        "negative_controls_pass": all(controls.values()),
    }
    passed = all(checks.values())
    return {
        "schema": "node0075-negative-psum-d0aa87f-revalidation-validation-v1",
        "test_id": "r5-node0075-negative-psum-d0aa87f-revalidation-v1",
        "status": "PASS_FAIL_CLOSED" if passed else "FAIL",
        "checks": checks,
        "negative_controls": controls,
        "claim_boundary": contract["claim_boundary"],
    }


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
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    report = validate(root, contract)
    report["contract_path"] = contract_path.relative_to(root).as_posix()
    report["contract_sha256"] = sha256_file(contract_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["status"] != "PASS_FAIL_CLOSED":
        raise Node0075D0aa87fRevalidationError(
            "node0075 d0aa87f revalidation validation failed"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
