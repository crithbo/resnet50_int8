#!/usr/bin/env python3
"""Build the fail-closed node0075 server-package barrier receipt."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "r5-node0075-df23e4d-compositional-e2-server-barrier-blocker-v1"
OUT = ROOT / "artifacts/operator_config_validation" / TEST_ID
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0075_df23e4d_compositional_e2_server_barrier_blocker_v1.json"
)
MATERIALIZER_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-df23e4d-eight-pass-materializer-v1"
)
MATERIALIZER_REPORT = MATERIALIZER_ROOT / "materializer_report.json"
VALIDATION_REPORT = MATERIALIZER_ROOT / "determinism_and_config_binding_validation.json"
TARGET = MATERIALIZER_ROOT / "node0075_df23e4d_eight_pass_target.json"
PIPELINE_ROOT = ROOT / "ndp-sim/model_execplan/output/node0075_df23e4d_eight_pass_target"
SCA = PIPELINE_ROOT / "sca_cfg.json"
SCA_D = PIPELINE_ROOT / "sca_cfg_D.json"
ALIAS_CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0071_node0075_uint8_identity_alias_integration_v1.json"
)
AUTHORIZATION = ROOT / ".agents/task_records/20260803_node0075_materializer_mainline_authorization.md"
RELOAD_AUTHORIZATION = (
    ROOT
    / ".agents/task_records/"
    "20260803_node0075_a_repeated_read_diagnostic_bypass_authorization.md"
)
ROUTING_INDEX = ROOT / ".agents/rules/生成前必读索引.md"
OPERATOR_RULES = ROOT / ".agents/rules/算子配置规则.md"
HARDWARE_RULES = ROOT / ".agents/rules/NDP硬件字段语义.md"
SERVER_RULES = ROOT / ".agents/rules/服务器测试包生成规则.md"
INT8_SA_RULES = ROOT / ".agents/rules/INT8_SA点积专项规则.md"
UINT8_TAIL_RULES = ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"


class BlockerError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BlockerError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build() -> dict[str, Any]:
    materializer = load_json(MATERIALIZER_REPORT)
    validation = load_json(VALIDATION_REPORT)
    target = load_json(TARGET)
    sca = load_json(SCA)
    sca_d = load_json(SCA_D)
    alias = load_json(ALIAS_CONTRACT)
    if materializer.get("status") != "CONFIG_BOUND_LOCAL_E2_PASS":
        raise BlockerError("materializer E2 did not pass")
    if validation.get("status") != "DETERMINISTIC_CONFIG_BOUND_LOCAL_E2_PASS":
        raise BlockerError("independent deterministic validation did not pass")
    operators = target.get("operators")
    if not isinstance(operators, list) or len(operators) != 24:
        raise BlockerError("node0075 target operator count differs")
    if any(str(op.get("id", "")).startswith("node0071") for op in operators):
        raise BlockerError("target unexpectedly contains a node0071 producer")
    if operators[0].get("type") != "MatMulInt32Accumulate":
        raise BlockerError("first target occurrence is not the node0075 consumer")
    a_preloads = sorted(key for key in sca if "_matrixA_" in key)
    if a_preloads:
        raise BlockerError("forbidden A/intermediate host replay is present")
    if len([key for key in sca if "_matrixB_" in key]) != 128 or len(sca_d) != 128:
        raise BlockerError("node0075 SCA counts differ")
    producer_accepted = alias["frozen_handoff"]["known_source_storage"][
        "producer_local_visibility_evidence_accepted"
    ]
    cross_barrier = alias["visibility_and_lifetime"][
        "cross_operator_visibility_barrier_materialized"
    ]
    if producer_accepted is not True or cross_barrier is not False:
        raise BlockerError("approved alias barrier state differs")

    receipt = {
        "schema": "node0075-df23e4d-compositional-e2-server-barrier-blocker-v1",
        "test_id": TEST_ID,
        "status": "COMPOSITIONAL_E2_PASS_SERVER_PACKAGE_BLOCKED",
        "owner": {
            "operator_family": "QLinearMatMul/node0075",
            "owner_thread": "019fc775-8de0-7f10-bc4a-026a4673776f",
            "mainline_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        },
        "local_closure": {
            "config_bound_e2": True,
            "deterministic_double_rebuild": True,
            "target_operator_count": 24,
            "start_comp_count": 24,
            "reload_pass_count": 8,
            "configured_qualified_a_read_occurrences": 8192,
            "configured_qualified_a_read_traffic_bytes": 262144,
            "unique_a_bytes": 32768,
            "accumulator_mismatch_count": 0,
            "uint8_d_mismatch_count": 0,
            "formal_d_fragment_count": 128,
            "host_a_or_intermediate_preload_count": 0,
        },
        "barrier_adjudication": {
            "producer_visibility_receipt_accepted": producer_accepted,
            "producer_event": (
                "node0071 final uint8 D byte-set accepted AND node0071 completion/final barrier accepted"
            ),
            "consumer_first_configured_occurrence": (
                "node0075_accum_pass00 first qualified READ_STREAM1 occurrence"
            ),
            "compositional_happens_before_precondition_present": True,
            "node0071_producer_occurrence_in_final_execplan": False,
            "cross_operator_visibility_barrier_materialized_in_final_execplan": cross_barrier,
            "dynamic_consumer_acceptance_observed": False,
            "server_fresh_memory_precondition_satisfied": False,
        },
        "first_blocking_leaf": {
            "id": (
                "B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED"
            ),
            "stage": "server package pre-simulation fresh-memory gate",
            "first_missing_asset": (
                "one authorized integrated execution stream containing the true node0071 "
                "producer-final event, an explicit happens-before barrier, then node0075 pass00"
            ),
            "reason": (
                "the node0075-only execplan starts with its consumer and intentionally emits no A "
                "preload; a fresh simulator memory therefore has no legal writer for the aliased bytes"
            ),
        },
        "prohibited_substitution_matrix": [
            {
                "candidate": "preload frozen node0075 A bytes through SCA",
                "disposition": "FORBIDDEN",
                "reason": "intermediate tensor replay",
            },
            {
                "candidate": "copy/precompute/relayout A into a new allocation",
                "disposition": "FORBIDDEN",
                "reason": "explicit authorization boundary",
            },
            {
                "candidate": "assume producer-owned bases are initialized in a fresh simulator",
                "disposition": "FORBIDDEN",
                "reason": "producer base is not consumer acceptance or a runtime writer",
            },
            {
                "candidate": "silently import/modify another operator family's server workload",
                "disposition": "FORBIDDEN",
                "reason": "node0075 owner scope and foreign-family asset ownership",
            },
        ],
        "minimum_unblock_condition": (
            "mainline supplies or authorizes a single integrated producer-prefix materializer whose "
            "boundary starts from a legal non-intermediate input and whose final write/barrier shares "
            "the same simulator execution stream with this node0075 consumer"
        ),
        "outputs": {
            "handler_registry": True,
            "target_json": True,
            "mapping": True,
            "bitstream": True,
            "execplan": True,
            "sca": True,
            "config_bound_e2": True,
            "server_package": False,
        },
        "release": {
            "package_release": "NONE",
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY_COMPOSITIONAL",
            "server_uploaded": False,
            "server_run": False,
            "lease_taken": False,
        },
        "termination": {
            "status": "WAIT_USER_DECISION",
            "reason": (
                "the only legal unblock requires mainline authorization or supply of a "
                "cross-family true-producer prefix in the same execution stream"
            ),
            "node0075_owner_can_continue_without_scope_expansion": False,
        },
        "input_receipts": [
            identity(path)
            for path in (
                MATERIALIZER_REPORT,
                VALIDATION_REPORT,
                TARGET,
                SCA,
                SCA_D,
                ALIAS_CONTRACT,
                AUTHORIZATION,
                RELOAD_AUTHORIZATION,
                ROUTING_INDEX,
                OPERATOR_RULES,
                HARDWARE_RULES,
                SERVER_RULES,
                INT8_SA_RULES,
                UINT8_TAIL_RULES,
            )
        ],
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed_rule_ids": [
                "CDA-VIEW-ACCEPTED-LIFETIME-001",
                "CDA-SERVER-WORKLOAD-PROVENANCE-001",
                "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
            ],
            "evidence": (
                "the current rules distinguish a compositional E2 precondition from a legal "
                "fresh-memory runtime writer, require a legal typed/checkpoint/frozen-stimulus "
                "boundary for a reduced execution, and prevent an A preload from escaping as replay"
            ),
            "rule_delta_proposal": [],
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / "report.json", receipt)
    contract = dict(receipt)
    contract["artifact_report"] = identity(OUT / "report.json")
    write_json(CONTRACT, contract)
    return {
        "status": receipt["status"],
        "report": identity(OUT / "report.json"),
        "contract": identity(CONTRACT),
        "package_release": "NONE",
        "blocking_leaf": receipt["first_blocking_leaf"]["id"],
    }


def main() -> int:
    result = build()
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
