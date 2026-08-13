#!/usr/bin/env python3
"""Build the e1fb0f7 node0071->node0075 barrier field-leaf adjudication."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "r5-node0071-node0075-e1fb0f7-barrier-field-leaf-v1"
CONTRACT = (
    ROOT
    / "contracts/operator_config"
    / "node0071_node0075_e1fb0f7_barrier_field_leaf_v1.json"
)
REPORT = (
    ROOT
    / "artifacts/operator_config_validation"
    / TEST_ID
    / "report.json"
)
CURRENT_RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
CURRENT_RTL_TREE = (
    "70334ce5f9addcfa409d566e7f7215b9870f815a7afc813d55f020a3af3ae647"
)

SYNC_REPORT = Path(
    "artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json"
)
NODE0071_ROOT = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
)
NODE0071_MANIFEST = NODE0071_ROOT / "TEST_PACKAGE_MANIFEST.json"
NODE0071_SCA = NODE0071_ROOT / "workload/sca_cfg.json"
NODE0071_SCA_D = NODE0071_ROOT / "workload/sca_cfg_D.json"
NODE0071_EXECPLAN = NODE0071_ROOT / "workload/install/execplan.txt"
NODE0071_RETURN_REPORT = Path(
    "artifacts/operator_config_validation/r5-gap-node0071-v33-return-analysis/"
    "report.json"
)

NODE0075_REPORT = Path(
    "artifacts/operator_config_validation/"
    "r5-node0075-df23e4d-eight-pass-materializer-v1/materializer_report.json"
)
NODE0075_VALIDATION = Path(
    "artifacts/operator_config_validation/"
    "r5-node0075-df23e4d-eight-pass-materializer-v1/"
    "determinism_and_config_binding_validation.json"
)
NODE0075_TARGET = Path(
    "artifacts/operator_config_validation/"
    "r5-node0075-df23e4d-eight-pass-materializer-v1/"
    "node0075_df23e4d_eight_pass_target.json"
)

SLICE_EXEC = Path("NDP_copy01/rtl/Slice/Slice_Execution_Manager.sv")
WR_DATA = Path(
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
)
STREAM_CONNECT = Path(
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv"
)
SLICE_XBAR = Path("NDP_copy01/rtl/Slice/slice2hub_crossbar.sv")
LOCAL_WR_QUEUE = Path(
    "NDP_copy01/rtl/Datahub/Request_Queue/local_wr_req_queue.sv"
)
GLOBAL_EXEC = Path("NDP_copy01/rtl/Global/global_exec_manager.sv")
INSTRUCTION_GENERATOR = Path(
    "ndp-sim/model_execplan/src/execution_plan_generator/"
    "instruction_generator.py"
)

READ_RECEIPTS = [
    Path(".agents/agent.md"),
    Path(".agents/plan.md"),
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/INT8_SA点积专项规则.md"),
    Path(".agents/rules/精确UINT8量化尾专项规则.md"),
    Path(".agents/rules/Flatten_View算子配置规则.md"),
    Path(".agents/rules/服务器测试包生成规则.md"),
    Path("NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
]

AUTHORITY_RECEIPTS = [
    Path(
        "contracts/operator_config/"
        "node0071_node0075_uint8_identity_alias_integration_v1.json"
    ),
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
        "20260804_node0075_df23e4d_compositional_e2_server_barrier_blocker.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_quantize_node0074_dq_view_q_identity_fusion.md"
    ),
    Path(
        ".agents/task_records/"
        "20260804_trassic_master_e1fb0f7_direct_checkout_and_ndp_copy_sync.md"
    ),
    Path(
        ".agents/task_records/"
        "20260804_gap_node0071_v33_return_dispatch.md"
    ),
]

GOLDEN_NPY = [
    Path(
        "artifacts/w3/golden_batch16/tensors/"
        "tensor-6fbd5707d5f08110.npy"
    ),
    Path(
        "artifacts/w3/subop_batch16/tensors/"
        "tensor-internal-node-0075-accumulate.npy"
    ),
    Path(
        "artifacts/w3/golden_batch16/tensors/"
        "tensor-6cc774b369e8dea4.npy"
    ),
]


class BarrierAuditError(RuntimeError):
    """Fail-closed audit error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(relative: Path) -> str:
    return sha256_bytes((ROOT / relative).read_bytes())


def receipt(relative: Path) -> dict[str, Any]:
    path = ROOT / relative
    if not path.is_file():
        raise BarrierAuditError(f"missing required file: {relative.as_posix()}")
    return {
        "path": relative.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(relative),
    }


def load_json(relative: Path) -> Any:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def line_witness(relative: Path, needle: str) -> dict[str, Any]:
    text = (ROOT / relative).read_text(encoding="utf-8")
    hits = [
        {"line": index, "text": line.strip()}
        for index, line in enumerate(text.splitlines(), start=1)
        if needle in line
    ]
    if not hits:
        raise BarrierAuditError(
            f"missing source witness {needle!r} in {relative.as_posix()}"
        )
    return {"path": relative.as_posix(), "needle": needle, "hits": hits}


def tree_receipt(relative: Path) -> dict[str, Any]:
    root = ROOT / relative
    files = sorted(path for path in root.rglob("*") if path.is_file())
    records = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        records.append(
            f"{rel}\0{path.stat().st_size}\0"
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}\n"
        )
    payload = "".join(records).encode("utf-8")
    return {
        "path": relative.as_posix(),
        "file_count": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "tree_sha256": sha256_bytes(payload),
    }


def decode_execplan(relative: Path) -> dict[str, Any]:
    lines = (ROOT / relative).read_text(encoding="ascii").splitlines()
    commands: list[int] = []
    for line_number, raw in enumerate(lines, start=1):
        bits = raw.strip()
        if len(bits) != 128 or set(bits) - {"0", "1"}:
            raise BarrierAuditError(
                f"invalid execplan line {line_number}: {relative.as_posix()}"
            )
        word = int(bits, 2)
        # FIFO_128to64 consumes the low 64-bit command before the high half.
        commands.extend((word & ((1 << 64) - 1), word >> 64))
    commands = [command for command in commands if command != 0]
    opcodes = [command & 0b111 for command in commands]
    counts = Counter(opcodes)
    return {
        **receipt(relative),
        "line_count_128b": len(lines),
        "command_count_64b_nonzero": len(commands),
        "opcode_counts": {str(key): counts[key] for key in sorted(counts)},
        "barrier_opcode": "0b110",
        "barrier_command_count": counts[0b110],
        "start_comp_count": counts[0b101],
    }


def audit_barrier_field() -> dict[str, Any]:
    sem_text = (ROOT / SLICE_EXEC).read_text(encoding="utf-8")
    wr_text = (ROOT / WR_DATA).read_text(encoding="utf-8")
    queue_text = (ROOT / LOCAL_WR_QUEUE).read_text(encoding="utf-8")
    generator_text = (ROOT / INSTRUCTION_GENERATOR).read_text(encoding="utf-8")

    if "localparam BARR_CMD_OP = 3'b110;" not in sem_text:
        raise BarrierAuditError("BARR opcode declaration drifted")
    absent = {
        "barrier_valid_decode_absent": "barr_cmd_vld" not in sem_text.lower(),
        "barrier_fsm_state_absent": not any(
            token in sem_text
            for token in (
                "localparam BARR =",
                "BARR: begin",
                "sem_ns = BARR;",
            )
        ),
        "barrier_drain_or_outstanding_input_absent": not any(
            token in sem_text.lower()
            for token in (
                "data_fifo_empty",
                "write_outstanding",
                "wdata_outstanding",
                "memory_visibility",
            )
        ),
        "instruction_generator_barrier_encoder_absent": not any(
            token in generator_text
            for token in ("BarrierEncoder", "OPCODE_BARRIER")
        ),
    }
    if not all(absent.values()):
        raise BarrierAuditError(f"barrier field audit drifted: {absent}")

    finish_condition = (
        "else if (|(wr_data_chl_ob_last_data_flag & "
        "mem2mse_wdata_ready)) begin"
    )
    if finish_condition not in wr_text:
        raise BarrierAuditError("slice finish condition drifted")
    if (
        "assign slice_cmpt_finish = "
        "wr_data_chl_ob_last_data_arv_arr_flag;"
        not in wr_text
    ):
        raise BarrierAuditError("slice finish assignment drifted")
    if "assign slice_wr_req_data_ready = !data_fifo_full;" not in queue_text:
        raise BarrierAuditError("Datahub FIFO ingress-ready equation drifted")

    return {
        "declared_barrier_opcode": "0b110",
        "declared_but_live_semantics_absent": True,
        "absence_checks": absent,
        "source_receipts": [
            receipt(SLICE_EXEC),
            receipt(WR_DATA),
            receipt(STREAM_CONNECT),
            receipt(SLICE_XBAR),
            receipt(LOCAL_WR_QUEUE),
            receipt(GLOBAL_EXEC),
            receipt(INSTRUCTION_GENERATOR),
        ],
        "source_witnesses": [
            line_witness(SLICE_EXEC, "localparam BARR_CMD_OP = 3'b110;"),
            line_witness(SLICE_EXEC, "if (slice_cmpt_finish) begin"),
            line_witness(SLICE_EXEC, "slice2gexec_ready"),
            line_witness(
                WR_DATA,
                "wr_data_chl_ob_last_data_flag & mem2mse_wdata_ready",
            ),
            line_witness(
                WR_DATA,
                "assign slice_cmpt_finish = "
                "wr_data_chl_ob_last_data_arv_arr_flag;",
            ),
            line_witness(
                STREAM_CONNECT,
                "assign mem2mse_wdata_ready   = hub2mse_wdata_ready;",
            ),
            line_witness(
                SLICE_XBAR,
                "hub2mse_wdata_ready[MSE_IDX][CHL_IDX]",
            ),
            line_witness(
                LOCAL_WR_QUEUE,
                "assign slice_wr_req_data_ready = !data_fifo_full;",
            ),
        ],
        "semantic_chain": [
            {
                "event": "producer terminal write-data accepted by WR_Data_Channel",
                "meaning": (
                    "last-data flag AND mem2mse_wdata_ready; the event retires "
                    "the Slice compute command"
                ),
            },
            {
                "event": "mem2mse_wdata_ready",
                "meaning": (
                    "for local traffic it resolves to Datahub "
                    "slice_local_wdata_ready"
                ),
            },
            {
                "event": "Datahub slice_wr_req_data_ready",
                "meaning": (
                    "!data_fifo_full: acceptance into the local write-data FIFO, "
                    "not FIFO empty, memory commit, or outstanding zero"
                ),
            },
            {
                "event": "opcode 0b110 after Start_Comp",
                "meaning": (
                    "constant is declared but has no valid decode/FSM/drain "
                    "condition, so IDLE consumes it as a no-op"
                ),
            },
        ],
        "formal_conclusion": (
            "The current command/field path can serialize the next command after "
            "slice_cmpt_finish, but cannot express or prove producer write-data "
            "FIFO drain, outstanding=0, or final memory visibility before the "
            "node0075 pass00 read."
        ),
    }


def build_report() -> dict[str, Any]:
    sync = load_json(SYNC_REPORT)
    if sync["source_repository"]["head"] != CURRENT_RTL_COMMIT:
        raise BarrierAuditError("current RTL commit mismatch")
    if sync["ndp_copy_sync"]["target_tree_sha256"] != CURRENT_RTL_TREE:
        raise BarrierAuditError("current RTL tree mismatch")
    if sync["ndp_copy_sync"]["exact_match"] is not True:
        raise BarrierAuditError("current RTL source/target tree is not exact")

    node0071_sca = load_json(NODE0071_SCA)
    node0071_return = load_json(NODE0071_RETURN_REPORT)
    node0075_report = load_json(NODE0075_REPORT)
    reloads = node0075_report["a_consumer_coverage"]

    if node0071_sca["Repeat_Num"] != 8:
        raise BarrierAuditError("node0071 stage count drifted")
    if reloads["reload_pass_count"] != 8:
        raise BarrierAuditError("node0075 reload count drifted")
    if reloads["accepted_traffic_bytes"] != 262144:
        raise BarrierAuditError("node0075 configured traffic drifted")

    node0071_exec = decode_execplan(NODE0071_EXECPLAN)
    if node0071_exec["barrier_command_count"] != 8:
        raise BarrierAuditError("node0071 execplan barrier count drifted")
    if node0071_exec["start_comp_count"] != 8:
        raise BarrierAuditError("node0071 execplan Start_Comp count drifted")

    input_tree = tree_receipt(NODE0071_ROOT / "workload/input")
    golden_trees = {
        name: tree_receipt(NODE0071_ROOT / "workload/golden" / name)
        for name in ("sum_int32", "scaled_fp32", "final_uint8")
    }
    if input_tree["file_count"] != 16:
        raise BarrierAuditError("node0071 graph external input set drifted")
    if any(tree["file_count"] != 16 for tree in golden_trees.values()):
        raise BarrierAuditError("node0071 per-stage golden set drifted")

    field_audit = audit_barrier_field()
    recurrence = receipt(
        Path(
            "outputs/node0075_negative_psum_df23e4d_revalidation/"
            "current_rtl_and_recurrence.json"
        )
    )
    active_sa = receipt(
        Path(
            "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
            "SA_PE_Float_CSA.v"
        )
    )
    old_recurrence_json = load_json(Path(recurrence["path"]))
    recurrence_source_sha = old_recurrence_json["current_rtl_identity"][
        "SA_PE_Float_CSA.v"
    ]
    if recurrence_source_sha != active_sa["sha256"]:
        raise BarrierAuditError(
            "historical exhaustive recurrence source bytes differ from e1fb0f7"
        )

    report = {
        "schema": "node0071-node0075-e1fb0f7-barrier-field-leaf-v1",
        "test_id": TEST_ID,
        "status": "HARDWARE_FIELD_LEAF_UNEXPRESSIBLE",
        "package_release": "NONE",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "mainline_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "owner_scope": "QLinearMatMul/node0075 integration only",
        "user_authorization": {
            "authorized": True,
            "scope": (
                "read-only consume current node0071 producer assets and create a "
                "fresh integration stream only if a true final-write accepted, "
                "outstanding-cleared visibility barrier can be expressed"
            ),
            "stop_condition": (
                "If the current hardware field cannot express/prove the barrier, "
                "stop at the exact field leaf with PACKAGE_RELEASE=NONE"
            ),
            "upload_run_or_lease_authorized": False,
        },
        "current_rtl_binding": {
            "commit": CURRENT_RTL_COMMIT,
            "tree_sha256": CURRENT_RTL_TREE,
            "sync_report": receipt(SYNC_REPORT),
            "active_sa_member": active_sa,
            "arithmetic_recurrence_reuse": {
                "report": recurrence,
                "source_byte_identity_matches_e1fb0f7": True,
                "cases": old_recurrence_json["frozen_recurrence"][
                    "enumerated_occurrences"
                ],
                "mismatch_count": old_recurrence_json[
                    "frozen_recurrence"
                ]["formal_accumulator_mismatch_count"],
                "negative_to_exact_zero_count": old_recurrence_json[
                    "frozen_recurrence"
                ]["negative_to_exact_zero"],
                "claim_boundary": (
                    "The complete recurrence consumed the exact same "
                    "SA_PE_Float_CSA bytes now present in e1fb0f7. This binds "
                    "arithmetic only; it does not supply a visibility barrier."
                ),
            },
        },
        "current_node0071_read_only_inputs": {
            "source_profile": (
                "current plan-selected v33 full eight-stage producer workload; "
                "read-only and not copied into a new target"
            ),
            "package_manifest": receipt(NODE0071_MANIFEST),
            "sca": receipt(NODE0071_SCA),
            "sca_d": receipt(NODE0071_SCA_D),
            "execplan": node0071_exec,
            "graph_external_typed_input": input_tree,
            "per_stage_golden": golden_trees,
            "ordered_stages": node0071_return["execution"][
                "ordered_stage_scope"
            ]["expected_ordered_stage_list"],
            "dynamic_current_return": {
                "compile_exit_status": node0071_return["execution"][
                    "compile_exit_status"
                ],
                "natural_terminal": node0071_return["execution"][
                    "natural_terminal"
                ],
                "started_stages": node0071_return["execution"][
                    "ordered_stage_scope"
                ]["started_ordered_stage_list"],
                "completed_stages": node0071_return["execution"][
                    "ordered_stage_scope"
                ]["completed_ordered_stage_list"],
                "formal_d_present": node0071_return["formal_d"][
                    "present_count"
                ],
                "formal_d_expected": node0071_return["formal_d"][
                    "expected_count"
                ],
                "claim_boundary": (
                    "The current source workload begins from graph external "
                    "typed input, but the returned run did not reach producer "
                    "final D. It cannot supply a dynamic final barrier witness."
                ),
            },
        },
        "node0075_existing_local_e2": {
            "materializer_report": receipt(NODE0075_REPORT),
            "determinism_validation": receipt(NODE0075_VALIDATION),
            "target": receipt(NODE0075_TARGET),
            "configured_reload_passes": reloads["reload_pass_count"],
            "configured_32byte_read_occurrences": reloads[
                "accepted_occurrence_count"
            ],
            "configured_a_traffic_bytes": reloads[
                "accepted_traffic_bytes"
            ],
            "unique_a_bytes": reloads["unique_consumer_byte_count"],
            "runtime_accepted_reads": None,
            "golden_tensors": [receipt(path) for path in GOLDEN_NPY],
            "claim_boundary": (
                "These are comparison/oracle assets and configured consumer "
                "occurrences. They are not an A preload, producer execution, "
                "runtime acceptance, or barrier witness."
            ),
        },
        "hardware_field_audit": field_audit,
        "first_missing_leaf": {
            "id": (
                "B_MATMUL_NODE0075_E1FB0F7_PRODUCER_VISIBILITY_"
                "BARRIER_FIELD_UNEXPRESSIBLE"
            ),
            "parent_blocker": (
                "B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_"
                "PRODUCER_BARRIER_UNMATERIALIZED"
            ),
            "stage_boundary": "node0071 tail_round -> node0075 accum pass00",
            "required": (
                "producer final-write accepted AND producer write outstanding=0 "
                "or equivalent proven visibility, before pass00 first A read"
            ),
            "available": (
                "Start_Comp retires on last write-data FIFO ingress acceptance; "
                "opcode 0b110 is an unimplemented no-op"
            ),
            "why_observer_is_insufficient": (
                "A read-only observer can report drain state after the fact but "
                "cannot gate dispatch of node0075 pass00. Using TB control would "
                "change the execution mechanism and is not authorized."
            ),
        },
        "generation_decision": {
            "integration_target_generated": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_generated": False,
            "sca_generated": False,
            "sca_d_generated": False,
            "server_package_generated": False,
            "reason": "user-authorized exact hardware-field stop condition",
        },
        "blocker_delta": {
            "closed": [],
            "remains_open": [
                "B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED"
            ],
            "refined_to": (
                "B_MATMUL_NODE0075_E1FB0F7_PRODUCER_VISIBILITY_"
                "BARRIER_FIELD_UNEXPRESSIBLE"
            ),
            "downstream_not_reached": [
                "joint target/mapping/bitstream/execplan/SCA",
                "runtime producer-final accepted write set",
                "runtime eight-pass A acceptance",
                "formal node0075 D",
                "server package and final-ZIP audit",
            ],
        },
        "negative_controls": {
            "barrier_opcode_presence_alone_rejected": True,
            "slice_finish_fifo_ingress_as_outstanding_zero_rejected": True,
            "observer_only_barrier_as_dispatch_gate_rejected": True,
            "preloaded_node0071_output_rejected": True,
            "producer_base_as_consumer_acceptance_rejected": True,
        },
        "rule_feedback": {
            "type": "RULE_DELTA_PROPOSAL",
            "proposed_rule_id": (
                "CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001"
            ),
            "problem": (
                "Current materializers/contracts can count opcode 0b110 as a "
                "barrier even when the active execution manager does not decode "
                "it and compute completion occurs at a write FIFO ingress."
            ),
            "proposed_text": (
                "A cross-stage or cross-operator barrier may be credited only "
                "when the active RTL identity decodes the emitted opcode/field "
                "into a live state transition whose release condition proves "
                "all required producer writes accepted into the visibility "
                "domain and write outstanding zero (or a formally equivalent "
                "ordered-visibility condition). Command presence, Start_Comp "
                "serialization, last-data acceptance into an ingress FIFO, or "
                "observer-only evidence must fail closed."
            ),
            "positive_control": (
                "focused RTL/harness shows the barrier stalls the next command "
                "while a producer write remains queued and releases only after "
                "the declared visibility condition"
            ),
            "negative_control": (
                "declared-but-undecoded opcode 0b110 and last-data FIFO ingress "
                "completion must not close a scratch/alias visibility edge"
            ),
            "scope": (
                "all multi-stage or multi-operator execplans that reload DRAM "
                "scratch or a producer-owned alias"
            ),
            "claim_boundary": (
                "This proposal does not prescribe a functional RTL fix and does "
                "not invalidate purely numeric goldens; it prevents materialized "
                "barrier claims without live hardware semantics."
            ),
        },
        "read_receipts": [receipt(path) for path in READ_RECEIPTS],
        "authority_receipts": [receipt(path) for path in AUTHORITY_RECEIPTS],
        "mutation_boundary": {
            "functional_rtl_modified": False,
            "plan_modified": False,
            "public_rules_modified": False,
            "node0071_or_other_family_asset_modified": False,
            "server_uploaded_run_or_lease": False,
        },
        "claim_boundary": (
            "Exact e1fb0f7 field-level fail-closed adjudication only. Existing "
            "node0071/node0075 numeric goldens remain valid comparison assets, "
            "but no self-contained joint runtime, dynamic barrier, accepted "
            "eight-pass traffic, formal D, package, E3, E4, or E5 is claimed."
        ),
    }
    return report


def canonical_json(data: Any) -> bytes:
    return (
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def main() -> None:
    report = build_report()
    payload = canonical_json(report)
    CONTRACT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT.write_bytes(payload)
    REPORT.write_bytes(payload)
    print(
        json.dumps(
            {
                "status": report["status"],
                "package_release": report["package_release"],
                "contract": str(CONTRACT.relative_to(ROOT)),
                "contract_sha256": sha256_bytes(payload),
                "report": str(REPORT.relative_to(ROOT)),
                "report_sha256": sha256_bytes(payload),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
