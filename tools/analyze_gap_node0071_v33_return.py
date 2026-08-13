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

from tools import analyze_gap_node0071_v32_return as base


IDENTITY = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 134495
RETURN_SHA256 = (
    "94e1abd19246b773cb3d3dd19c9bcfafa398da35fa09c310c27b8a4fca661daa"
)
SOURCE_SIZE = 1824172
SOURCE_SHA256 = (
    "5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03"
)


def integer(record: dict[str, Any], key: str, default: int = -1) -> int:
    value = record.get(key)
    if value is None:
        return default
    if isinstance(value, int):
        return value
    return int(value, 16) if value.startswith("0x") else int(value)


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    base.IDENTITY = IDENTITY
    base.RETURN_ROOT = RETURN_ROOT
    base.RETURN_SIZE = RETURN_SIZE
    base.RETURN_SHA256 = RETURN_SHA256
    base.SOURCE_SIZE = SOURCE_SIZE
    base.SOURCE_SHA256 = SOURCE_SHA256
    report = base.analyze(return_zip, source_zip)

    with zipfile.ZipFile(return_zip) as archive:
        observer = archive.read(
            f"{RETURN_ROOT}/runs/return_observer.log"
        ).decode("utf-8", errors="replace")
        binding = archive.read(
            f"{RETURN_ROOT}/evidence/observer_binding.txt"
        ).decode("utf-8", errors="replace")
        argv = archive.read(
            f"{RETURN_ROOT}/evidence/actual_simulator_argv.txt"
        ).decode("utf-8", errors="replace")
        canonical = json.loads(
            archive.read(
                f"{RETURN_ROOT}/evidence/canonical_decision.json"
            )
        )
    with zipfile.ZipFile(source_zip) as archive:
        package_observer = archive.read(
            f"{IDENTITY}/tb_probe/native_return_observer.svh"
        ).decode("utf-8", errors="replace")

    queue_counts = base.base.last_record(
        observer, "BUFFER_AG_IDX_QUEUE_COUNTS_V1"
    )
    queue_state = base.base.last_record(
        observer, "BUFFER_AG_IDX_QUEUE_STATE_V1"
    )
    queue_witness = base.base.last_record(
        observer, "BUFFER_AG_IDX_QUEUE_WITNESS_V1"
    )
    queue_events = base.base.event_records(
        observer, "BUFFER_AG_IDX_QUEUE_EVENT_V1"
    )
    bp_state = base.base.last_record(observer, "BP_PRE_FACTOR_STATE_V1")
    bp_counts = base.base.last_record(observer, "BP_PRE_FACTOR_COUNTS_V1")
    source_queue = (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    )
    source_group = ROOT / "NDP_copy01/rtl/slice_with_datahub_phy_no_pin.sv"
    source_top = ROOT / "NDP_copy01/rtl/NDP_Top_phy.sv"
    queue_rtl = source_queue.read_text(encoding="utf-8")
    group_rtl = source_group.read_text(encoding="utf-8")
    top_rtl = source_top.read_text(encoding="utf-8")
    v33_sampler = package_observer[
        package_observer.index(
            "// v33 sampler: qualified input accepts and FIFO accepts only."
        ):
        package_observer.index(
            "// v31 sampler: accepted transactions only; stable levels are state."
        )
    ]
    clock_domain_error = (
        "always @(posedge u_NDP_Top_new.clk_sg)" in v33_sampler
        and ".clk                         ( clk_db" in group_rtl
        and ".clk_db                  ( clk )" in top_rtl
        and "input                                                                 clk" in queue_rtl
        and ".clk               ( clk" in queue_rtl
    )
    queue_state_repeated = observer.count(
        "BUFFER_AG_IDX_QUEUE_STATE_V1"
    ) > 100
    final_state_narrows_rd_ready = (
        integer(queue_state, "full") == 1
        and integer(queue_state, "rd_en") == 0
        and integer(queue_state, "empty") == 0
        and integer(queue_state, "out_valid") == 1
        and integer(queue_state, "all_matched") == 1
        and integer(queue_state, "mse_enable") == 1
        and integer(bp_state, "ob_full") == 0
        and integer(bp_state, "data_ready") == 0
        and integer(bp_state, "barrier") == 0
    )

    report.update(
        {
            "schema": "gap-node0071-v33-return-analysis-v1",
            "status": "ADJUDICATED_PACKAGE_DIAGNOSTIC_FIX_REQUIRED",
            "analysis_owner_thread":
                "019fa366-cb1f-7ae2-880c-f527be0680cd",
            "return_target_thread":
                "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "runtime_binding": {
                **report["runtime_binding"],
                "buffer_ag_idx_queue_enable_in_argv":
                    "+RETURN_OBS_BUFFER_AG_IDX_QUEUE" in argv,
                "buffer_ag_idx_queue_limit_in_argv":
                    "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256" in argv,
                "buffer_ag_idx_queue_time0_marker":
                    "buffer_ag_idx_queue=1" in observer
                    and "buffer_ag_idx_queue_limit=256" in observer,
                "buffer_ag_idx_queue_return_binding":
                    "buffer_ag_idx_queue_enabled=true" in binding
                    and "buffer_ag_idx_queue_records_returned=true" in binding,
            },
            "production_identity_boundary": {
                "user_confirmed_server_and_local_rtl_commit":
                    "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d",
                "local_rtl_tree_digest":
                    "70334ce5f9addcfa409d566e7f7215b9870f815a7afc813d55f020a3af3ae647",
                "return_binds_actual_compiled_commit": False,
                "claim": (
                    "The user-confirmed baseline is current provenance, but "
                    "this return does not cryptographically bind the production "
                    "compiled RTL commit and cannot upgrade E3/E4/E5."
                ),
            },
            "buffer_ag_idx_queue_evidence": {
                "counts": queue_counts,
                "state": queue_state,
                "witness": queue_witness,
                "event_record_count": len(queue_events),
                "qualified_event_counts_evaluable": False,
                "event_records_evaluable": False,
                "reason": (
                    "The v33 sampler advances on clk_sg while the observed "
                    "Buffer_AG_Idx_Queue and its FIFO are clocked by clk_db."
                ),
                "stable_state_snapshot_only": True,
                "state_record_repeated_over_long_window": queue_state_repeated,
                "final_state_narrows_rd_ready": final_state_narrows_rd_ready,
                "final_state_interpretation": (
                    "At repeated snapshots, the queue is nonempty/full with "
                    "valid output and all-matched/MSE enabled, while its direct "
                    "consumer does not dequeue. The WR_Buffer_AG conjunction "
                    "snapshot has ob_full=0, barrier=0, data_ready=0, narrowing "
                    "the held state to RD_Data_Channel readiness. Occurrence "
                    "and accepted counts remain unproven until clk_db sampling."
                ),
                "bp_factor_counts_unevaluable": bp_counts,
            },
            "clock_domain_binding_error": {
                "proven": clock_domain_error,
                "package_sampler_clock": "u_NDP_Top_new.clk_sg",
                "signal_owner_clock": "clk_db / u_NDP_Top_new.clk",
                "queue_rtl": str(source_queue.relative_to(ROOT)),
                "group_clock_binding_rtl": str(source_group.relative_to(ROOT)),
                "top_clock_binding_rtl": str(source_top.relative_to(ROOT)),
                "package_observer_member":
                    f"{IDENTITY}/tb_probe/native_return_observer.svh",
                "functional_rtl_defect_claimed": False,
            },
            "canonical_decision_adjudication": {
                "returned_decision": canonical["decision"],
                "returned_boundary": canonical["boundary"],
                "accepted_as_generic_stall_detection": True,
                "accepted_as_functional_first_divergence": False,
                "reason": (
                    "The generic canonical record remains valid for the global "
                    "stall, but the v33 feature intended to refine it sampled "
                    "qualified queue events in the wrong clock domain."
                ),
            },
            "last_proven_good": (
                "Package/source/return identity, compile, runtime feature "
                "binding and repeated state snapshots are valid. The prior v32 "
                "LPG remains the latest qualified functional evidence; v33 "
                "does not add qualified Buffer_AG queue occurrence evidence."
            ),
            "first_divergence": (
                "PACKAGE_OBSERVER_BUFFER_AG_IDX_QUEUE_QUALIFIED_SAMPLER_"
                "CLOCK_DOMAIN_MISMATCH_CLK_SG_VS_CLK_DB"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_MSE0_BUFFER_AG_BACKPRESSURE_WITH_RD_"
                "DATA_READY_LOW_STATE_ONLY_PENDING_CLK_DB_QUALIFIED_FACTORS"
            ),
            "root_cause_scope": {
                "closed_by_repeated_state_only": [
                    "queue empty at the held state",
                    "MSE0 disabled at the held state",
                    "index pair not matched at the held state",
                    "WR_Buffer_AG output buffer full at the held state",
                    "NRM read barrier asserted at the held state",
                ],
                "remaining": [
                    "RD_Data_Channel prepared-data count never reaches spatial size",
                    "memory request/return/inbuffer supply ends before demand",
                    "RD_Data_Channel output buffer/full or downstream request pairing",
                    "qualified queue enqueue/dequeue occurrence differs from clk_sg snapshots",
                ],
                "unique_functional_root": False,
                "package_diagnostic_root_unique": True,
            },
            "blocker_delta": {
                "closed": (
                    "B_GAP_NODE0071_MSE0_BUFFER_AG_INDEX_PAIRING_SUPPRESSES_"
                    "BYTE_LANE1_PENDING_INPUT_OR_MATCH_MASK_LEAF"
                ),
                "opened": (
                    "B_GAP_NODE0071_RD_DATA_READY_LOW_PENDING_PREPARED_DATA_"
                    "SUPPLY_OR_OUTPUT_FULL_CLK_DB_QUALIFIED_LEAF"
                ),
                "diagnostic_blocker": (
                    "B_GAP_NODE0071_V33_QUEUE_OBSERVER_WRONG_CLOCK_DOMAIN"
                ),
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "package_fix": (
                    "move queue and RD-ready accepted-event sampling to "
                    "u_NDP_Top_new.clk (clk_db) and add owner-clock counter"
                ),
                "information_gain_boundary": (
                    "queue direct consumer -> WR_Buffer_AG bp conjunction -> "
                    "RD_Data_Channel prepared count/data-vld/output-full -> "
                    "memory request/return/inbuffer supply"
                ),
                "config_change": False,
                "timeout_change": False,
                "functional_rtl_change": False,
            },
            "rule_confirmation": sorted(
                set(report.get("rule_confirmation", []))
                | {
                    "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
                    "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                    "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
                    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                }
            ),
            "rule_delta_proposal": "NONE",
            "numeric_sum_tail_workload_config_golden_repeated": False,
        }
    )
    report["e3_e4_e5"]["reason"] = (
        "compile=0 but INT/125 is not a natural terminal; all 48 formal D "
        "targets are missing, mismatch=0 is unevaluable, the conjunctive result "
        "gate is false, and the actual compiled production commit is unbound"
    )
    report["errors"] = list(report.get("errors", []))
    for condition, message in (
        (clock_domain_error, "v33 clock-domain binding error not proven"),
        (queue_state_repeated, "v33 queue state was not repeatedly returned"),
        (final_state_narrows_rd_ready, "v33 final state did not narrow RD readiness"),
        (len(queue_events) == 20, "v33 queue event record count differs"),
    ):
        if not condition:
            report["errors"].append(message)
    report["valid_receipt"] = not report["errors"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve(), args.source_zip.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
