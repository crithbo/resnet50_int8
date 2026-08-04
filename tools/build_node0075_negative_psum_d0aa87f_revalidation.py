from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


RUN_REL = Path(
    "outputs/node0075_negative_psum_d0aa87f_revalidation/"
    "current_rtl_and_recurrence.json"
)
DEFAULT_OUTPUT = Path(
    "contracts/operator_config/"
    "node0075_negative_psum_d0aa87f_revalidation_v1.json"
)

RECEIPTS = (
    Path(".agents/agent.md"),
    Path(".agents/plan.md"),
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/服务器测试包生成规则.md"),
    Path(".agents/rules/INT8_SA点积专项规则.md"),
    Path(".agents/rules/精确UINT8量化尾专项规则.md"),
    Path(
        ".agents/task_records/"
        "20260803_node0071_node0075_uint8_identity_alias_integration.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_node0075_materializer_mainline_authorization.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_node0075_a_repeated_read_diagnostic_bypass_authorization.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_node0075_operator_family_owner_split.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_trassic_master_d0aa87f_active_rtl_sync.md"
    ),
    Path(
        "contracts/operator_config/"
        "node0071_node0075_uint8_identity_alias_integration_v1.json"
    ),
    Path("artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json"),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_CSA.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_Control.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Mul_Array.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_ALU.v"
    ),
    Path("tests/rtl/node0075_negative_psum_d0aa87f_recheck_tb.sv"),
    Path("tools/run_node0075_negative_psum_d0aa87f_recheck.py"),
    RUN_REL,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_run(run: dict[str, Any]) -> None:
    scan = run["frozen_recurrence"]
    cases = run["directed_rtl"]["cases"]
    required = {
        "status": run.get("status") == "BLOCKER_RETAINED_CURRENT_RTL",
        "compile": run["directed_rtl"].get("compile_exit") == 0,
        "simulation": run["directed_rtl"].get("simulation_exit") == 0,
        "exact_observed": (
            cases["neg19_plus19"]["observed_bits"] == "0x80000000"
        ),
        "exact_expected": (
            cases["neg19_plus19"]["expected_bits"] == "0x00000000"
        ),
        "adjacent": all(
            cases[label]["pass"] is True
            for label in (
                "neg20_plus19",
                "neg18_plus19",
                "zero_plus19",
                "pos7_plus19",
            )
        ),
        "complete": (
            scan["planned_occurrences"]
            == scan["enumerated_occurrences"]
            == 8_192_000
        ),
        "negative_count": scan["negative_psum_occurrences"] == 4_343_952,
        "zero_hits": scan["negative_to_exact_zero"] == 272,
        "formal": scan["formal_accumulator_mismatch_count"] == 0,
    }
    failures = [name for name, passed in required.items() if not passed]
    if failures:
        raise RuntimeError(f"d0aa87f revalidation failed gates: {failures}")


def build(root: Path) -> dict[str, Any]:
    missing = [path.as_posix() for path in RECEIPTS if not (root / path).is_file()]
    if missing:
        raise RuntimeError(f"missing required receipts: {missing}")
    run = json.loads((root / RUN_REL).read_text(encoding="utf-8"))
    require_run(run)
    first = run["frozen_recurrence"]["first_stream_order_hit"]
    return {
        "schema": "resnet50-node0075-negative-psum-d0aa87f-revalidation-v1",
        "test_id": "r5-node0075-negative-psum-d0aa87f-revalidation-v1",
        "status": "HARDWARE_CAPABILITY_BLOCKED",
        "package_release": "NONE",
        "candidate_release": False,
        "owner": {
            "family": "QLinearMatMul/node0075",
            "owner_thread": "019fc775-8de0-7f10-bc4a-026a4673776f",
            "mainline_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        },
        "current_rtl_identity": run["current_rtl_identity"],
        "directed_rtl_gate": {
            "compile_exit": run["directed_rtl"]["compile_exit"],
            "simulation_exit": run["directed_rtl"]["simulation_exit"],
            "cases": run["directed_rtl"]["cases"],
            "adjudication": (
                "Four adjacent controls pass; only frozen exact cancellation "
                "-19+19 observes 0x80000000 instead of 0x00000000."
            ),
        },
        "full_frozen_recurrence_gate": run["frozen_recurrence"],
        "first_divergence": {
            "id": (
                "B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE"
            ),
            "witness": first,
            "live_leaf": (
                "SA_PE_Float_Control now provides full-width magnitude "
                "0x00000013, but SA_PE_Float_CSA computes Int_Res_Sign as "
                "c_Result0_wire[31] XOR i_SignC. Exact magnitude cancellation "
                "has c_Result0_wire=0 and retains i_SignC=1, while result "
                "bits[30:0] are zero, producing noncanonical 0x80000000."
            ),
            "config_expressible": False,
            "functional_rtl_mutation_authorized": False,
        },
        "materializer_and_traffic": {
            "actual_materialized_reload_passes": 0,
            "actual_accepted_32byte_reads": 0,
            "actual_accepted_a_traffic_bytes": 0,
            "actual_unique_consumer_accepted_bytes": 0,
            "authorized_post_fix_minimum": {
                "formula": "ceil(1000/(16*8))=8",
                "passes": 8,
                "accepted_reads_per_slice": 512,
                "accepted_reads_total": 8192,
                "accepted_a_traffic_bytes": 262144,
                "unique_producer_owned_storage_bytes": 32768,
            },
            "reason": (
                "Fail-fast precedes consumer materialization; the authorized "
                "8-pass figures remain counterfactual and are not acceptance."
            ),
        },
        "outputs": {
            "op_json_schema_or_template": False,
            "handler_or_registry": False,
            "consumer_materializer": False,
            "target_json": False,
            "mapping": False,
            "bitstream": False,
            "execplan": False,
            "sca": False,
            "config_bound_e2": False,
            "server_package": False,
        },
        "blocker_delta": {
            "source_sync": "UPDATED_8F2F318_TO_D0AA87F",
            "closed": [],
            "retained_exact": [
                "B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE"
            ],
            "not_reached": [
                "B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING",
                "B_MATMUL_TAIL",
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
            ],
        },
        "source_receipts": {
            path.as_posix(): sha256_file(root / path) for path in RECEIPTS
        },
        "rule_confirmation": {
            "rule_ids": [
                "CDA-SA-INT8-RTL-COMPATIBILITY-001",
                "CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001",
                "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            ],
            "evidence": (
                "Exact d0aa87f active RTL fails one reachable frozen "
                "exact-cancellation occurrence while adjacent controls pass; "
                "the complete recurrence has 272 such hits."
            ),
            "claim_boundary": (
                "Frozen node0075 natural C-order recurrence and exact active "
                "d0aa87f RTL only; no family-wide or server-side claim."
            ),
        },
        "rule_delta_proposal": {
            "required": False,
            "reason": (
                "Current rules already require current-identity arithmetic "
                "compatibility and fail-fast before materialization/package."
            ),
        },
        "mutations": {
            "functional_rtl": False,
            "plan": False,
            "public_rules": False,
            "other_operator_family_assets": False,
            "server_upload_run_or_lease": False,
        },
        "claim_boundary": (
            "Fresh owner-side d0aa87f directed and complete recurrence "
            "revalidation. PACKAGE_RELEASE=NONE; no downstream node0075 "
            "materialization or server artifact was emitted."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    report = build(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    print(sha256_file(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
