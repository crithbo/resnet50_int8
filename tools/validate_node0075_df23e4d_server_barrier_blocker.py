#!/usr/bin/env python3
"""Independently validate the fail-closed node0075 server barrier receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "r5-node0075-df23e4d-compositional-e2-server-barrier-blocker-v1"
REPORT = ROOT / "artifacts/operator_config_validation" / TEST_ID / "report.json"
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0075_df23e4d_compositional_e2_server_barrier_blocker_v1.json"
)
TARGET = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-df23e4d-eight-pass-materializer-v1/"
    "node0075_df23e4d_eight_pass_target.json"
)
PIPELINE_ROOT = ROOT / "ndp-sim/model_execplan/output/node0075_df23e4d_eight_pass_target"
SCA = PIPELINE_ROOT / "sca_cfg.json"
SCA_D = PIPELINE_ROOT / "sca_cfg_D.json"
EXECPLAN = PIPELINE_ROOT / "install/execplan.txt"
EXPLAINED = PIPELINE_ROOT / "instructions_explained.txt"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object at {path}")
    return value


def main() -> int:
    report = load_json(REPORT)
    contract = load_json(CONTRACT)
    target = load_json(TARGET)
    sca = load_json(SCA)
    sca_d = load_json(SCA_D)

    assert report["status"] == "COMPOSITIONAL_E2_PASS_SERVER_PACKAGE_BLOCKED"
    assert report["release"] == {
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY_COMPOSITIONAL",
        "lease_taken": False,
        "package_release": "NONE",
        "server_run": False,
        "server_uploaded": False,
    }
    assert report["first_blocking_leaf"]["id"] == (
        "B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED"
    )
    assert report["termination"] == {
        "node0075_owner_can_continue_without_scope_expansion": False,
        "reason": (
            "the only legal unblock requires mainline authorization or supply of a "
            "cross-family true-producer prefix in the same execution stream"
        ),
        "status": "WAIT_USER_DECISION",
    }
    assert report["barrier_adjudication"]["producer_visibility_receipt_accepted"] is True
    assert report["barrier_adjudication"][
        "cross_operator_visibility_barrier_materialized_in_final_execplan"
    ] is False
    assert report["barrier_adjudication"]["node0071_producer_occurrence_in_final_execplan"] is False
    assert report["barrier_adjudication"]["server_fresh_memory_precondition_satisfied"] is False

    operators = target["operators"]
    assert len(operators) == 24
    assert operators[0]["type"] == "MatMulInt32Accumulate"
    assert not any(str(op.get("id", "")).startswith("node0071") for op in operators)
    assert len([key for key in sca if "_matrixA_" in key]) == 0
    assert len([key for key in sca if "_matrixB_" in key]) == 128
    assert len(sca_d) == 128

    execplan_text = EXECPLAN.read_text(encoding="utf-8")
    explained_text = EXPLAINED.read_text(encoding="utf-8")
    assert len(execplan_text.splitlines()) == 505
    assert explained_text.count("Start_Comp") == 24

    report_identity = contract["artifact_report"]
    assert report_identity["bytes"] == REPORT.stat().st_size
    assert report_identity["sha256"] == sha256(REPORT)
    assert report_identity["path"] == REPORT.relative_to(ROOT).as_posix()
    assert contract["first_blocking_leaf"] == report["first_blocking_leaf"]
    assert contract["release"] == report["release"]
    assert contract["rule_feedback"] == report["rule_feedback"]

    result = {
        "status": "INDEPENDENT_SERVER_BARRIER_BLOCKER_VALIDATION_PASS",
        "blocking_leaf": report["first_blocking_leaf"]["id"],
        "package_release": report["release"]["package_release"],
        "termination_status": report["termination"]["status"],
        "target_operator_count": len(operators),
        "execplan_line_count": len(execplan_text.splitlines()),
        "start_comp_count": explained_text.count("Start_Comp"),
        "a_preload_count": len([key for key in sca if "_matrixA_" in key]),
        "b_preload_count": len([key for key in sca if "_matrixB_" in key]),
        "formal_d_fragment_count": len(sca_d),
        "report_sha256": sha256(REPORT),
        "contract_sha256": sha256(CONTRACT),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
