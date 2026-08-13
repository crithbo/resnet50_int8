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

from tools import analyze_gap_node0071_v36_return as base


IDENTITY = "r5_n71_gap_v40_lc_supply_conservation_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 231089
RETURN_SHA256 = (
    "fdec51572f3017bf5cc0af70ee66873128c784b04a5988b6b8f9ea69aadf6a48"
)
SOURCE_SIZE = 1833762
SOURCE_SHA256 = (
    "7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4"
)
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
CLOUD_AUTHORITY = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def fields(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in line.split("|")[-1].strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result


def last_line(text: str, marker: str) -> str:
    matches = [line for line in text.splitlines() if marker in line]
    if not matches:
        raise ValueError(f"missing marker: {marker}")
    return matches[-1]


def pair(value: str) -> tuple[int, int]:
    left, right = value.split("/", 1)
    return int(left, 0), int(right, 0)


def integer(value: str) -> int:
    return int(value, 0)


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    base.IDENTITY = IDENTITY
    base.RETURN_ROOT = RETURN_ROOT
    base.RETURN_SIZE = RETURN_SIZE
    base.RETURN_SHA256 = RETURN_SHA256
    base.SOURCE_SIZE = SOURCE_SIZE
    base.SOURCE_SHA256 = SOURCE_SHA256
    report = base.analyze(return_zip, source_zip)

    with zipfile.ZipFile(return_zip) as archive:
        prefix = f"{RETURN_ROOT}/"
        observer = archive.read(prefix + "runs/return_observer.log").decode(
            "utf-8", errors="replace"
        )
        binding = archive.read(
            prefix + "evidence/observer_binding.txt"
        ).decode("utf-8", errors="replace")
        simulator_argv = archive.read(
            prefix + "evidence/actual_simulator_argv.txt"
        ).decode("utf-8", errors="replace")
        compile_argv = archive.read(
            prefix + "evidence/actual_compile_argv.txt"
        ).decode("utf-8", errors="replace")
        compile_log = archive.read(prefix + "logs/compile.log").decode(
            "utf-8", errors="replace"
        )
        canonical = json.loads(
            archive.read(prefix + "evidence/canonical_decision.json")
        )
        gate = json.loads(
            archive.read(prefix + "evidence/SERVER_RESULT_GATE.json")
        )
        timing = archive.read(
            prefix + "evidence/host_timing.txt"
        ).decode("utf-8", errors="replace")

    counts = fields(last_line(observer, "LC_SUPPLY_CONSERVATION_COUNTS_V1"))
    state = fields(last_line(observer, "LC_SUPPLY_CONSERVATION_STATE_V1"))
    witness = fields(last_line(observer, "LC_SUPPLY_CONSERVATION_WITNESS_V1"))
    event_lines = [
        line for line in observer.splitlines()
        if "LC_SUPPLY_CONSERVATION_EVENT_V1" in line
    ]
    heartbeat_lines = [
        line for line in observer.splitlines()
        if "LC_SUPPLY_CONSERVATION_COUNTS_V1" in line
        and "event=HEARTBEAT" in line
    ]
    times = {
        key: int(value)
        for key, value in (
            line.split("=", 1)
            for line in timing.splitlines()
            if "=" in line
        )
    }
    wall_seconds = (
        times["final_epoch_ns"] - times["sim_start_epoch_ns"]
    ) / 1_000_000_000

    bq_wr = pair(counts["bq_wr"])
    bq_rd = pair(counts["bq_rd"])
    mq_wr = pair(counts["mq_wr"])
    mq_rd = pair(counts["mq_rd"])
    req = pair(counts["req"])
    bq_balance = tuple(bq_wr[i] - bq_rd[i] for i in range(2))
    mq_balance = tuple(mq_wr[i] - mq_rd[i] for i in range(2))
    final_state = {
        key: value
        for key, value in state.items()
        if key not in {"event"}
    }
    feature_enabled = (
        "+RETURN_OBS_LC_SUPPLY_CONSERVATION" in simulator_argv
        and "+RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512" in simulator_argv
        and "lc_supply_conservation=1" in observer
        and "lc_supply_conservation_limit=512" in observer
        and "owner_clock=clk_db" in observer
        and "lc_supply_conservation_enabled=true" in binding
        and "lc_supply_conservation_records_returned=true" in binding
    )
    conservation_closed = (
        bq_wr == (217, 217)
        and bq_rd == (185, 185)
        and bq_balance == (32, 32)
        and mq_wr == (185, 185)
        and mq_rd == (185, 185)
        and mq_balance == (0, 0)
        and req == (185, 185)
        and integer(state["bq_count"].split("/")[0]) == 32
        and integer(state["bq_count"].split("/")[1]) == 32
        and integer(state["bq_full"]) == 3
        and integer(state["mq_count"].split("/")[0]) == 0
        and integer(state["mq_count"].split("/")[1]) == 0
        and integer(state["mq_empty"]) == 3
        and integer(state["mem_out_vld"]) == 0
        and integer(state["req_vld"]) == 0
        and integer(state["buf_out_vld"]) == 3
        and integer(state["buf_out_bp"]) == 0
    )
    terminal_tag_stable = (
        integer(state["mem_tag0"]) == 0x142880
        and integer(state["mem_tag3"]) == 0x142880
        and integer(state["mem_bp0"]) == 0x3
        and integer(state["mem_bp3"]) == 0x3
    )
    compile_clean = (
        report["execution"]["compile_exit_status"] == 0
        and "Error-[" not in compile_log
    )
    result_terms = gate["result_gate_conjunction"]
    formal_expected = int(gate["readback_count"])
    formal_missing = int(gate["missing_count"])
    formal_present = formal_expected - formal_missing
    natural = bool(canonical["natural_terminal"])
    valid_receipt = (
        not report["errors"]
        and compile_clean
        and feature_enabled
        and len(event_lines) == 512
        and len(heartbeat_lines) > 1
        and conservation_closed
        and terminal_tag_stable
    )

    report.pop("compile_first_failure", None)
    report.update(
        {
            "schema": "gap-node0071-v40-return-analysis-v1",
            "status": "ADJUDICATED_CONFIG_TOPOLOGY_CORRECTION_REQUIRED",
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "runtime_binding": {
                **report["runtime_binding"],
                "simulator_argv_returned": True,
                "observer_log_returned": True,
                "lc_supply_feature_enable_in_actual_argv":
                    "+RETURN_OBS_LC_SUPPLY_CONSERVATION" in simulator_argv,
                "lc_supply_feature_limit_in_actual_argv":
                    "+RETURN_OBS_LC_SUPPLY_CONSERVATION_LIMIT=512"
                    in simulator_argv,
                "lc_supply_time0_marker": (
                    "lc_supply_conservation=1" in observer
                    and "lc_supply_conservation_limit=512" in observer
                    and "owner_clock=clk_db" in observer
                ),
                "lc_supply_return_binding": (
                    "lc_supply_conservation_enabled=true" in binding
                    and "lc_supply_conservation_records_returned=true"
                    in binding
                ),
                "owner_clock_qualified_counts_evaluable": feature_enabled,
                "zero_counts_evaluable": feature_enabled,
                "reason": (
                    "Compile succeeded and the exact clk_db LC-supply feature "
                    "is present in actual argv, time-0 output, package-local "
                    "observer receipt and return allowlist."
                ),
            },
            "execution": {
                "compile_exit_status": 0,
                "compile_clean": compile_clean,
                "simulation_exit_status": 125,
                "simulation_started": True,
                "runner_exit_status": 125,
                "signal": "INT",
                "natural_terminal": natural,
                "host_wall_seconds_from_sim_start": wall_seconds,
                "canonical_decision": canonical["decision"],
                "canonical_boundary": canonical["boundary"],
                "canonical_reason": canonical["reason"],
                "ordered_stage_scope": canonical["final_stage_scope"],
            },
            "rtl_identity_binding": {
                "current_cloud_authority_repository":
                    "xlsjdjdk/Trassic2.0_RTL",
                "current_cloud_authority_commit": CLOUD_AUTHORITY,
                "authority_source": (
                    "current plan/task-record/user-confirmed immutable commit "
                    "receipt and synchronized local object"
                ),
                "compile_root": "/home/panqs/ndp/NDP_copy01",
                "actual_compile_argv": compile_argv.strip(),
                "actual_compiled_commit_return_bound": False,
                "actual_compiled_commit": "UNBOUND_BY_RETURN",
                "actual_observer_surface_compatible": compile_clean,
                "claim_boundary": (
                    "Compile success proves the actual server tree accepted "
                    "the exact package-local observer and referenced causal "
                    "surface. The return does not contain a Git/commit receipt, "
                    "so it cannot prove the exact production commit."
                ),
            },
            "lc_supply_conservation_evidence": {
                "feature_enabled_and_return_bound": feature_enabled,
                "qualified_event_record_count": len(event_lines),
                "qualified_event_record_limit": integer(counts["limit"]),
                "heartbeat_record_count": len(heartbeat_lines),
                "final_owner_clock_edge": integer(counts["edge"]),
                "accepted_counts": {
                    "buffer_ag_enqueue": list(bq_wr),
                    "buffer_ag_dequeue": list(bq_rd),
                    "memory_ag_enqueue": list(mq_wr),
                    "memory_ag_dequeue": list(mq_rd),
                    "memory_request": list(req),
                },
                "conservation": {
                    "buffer_ag_enqueue_minus_dequeue": list(bq_balance),
                    "buffer_ag_fifo_depth": 32,
                    "buffer_ag_exactly_full": bq_balance == (32, 32),
                    "memory_ag_enqueue_minus_dequeue": list(mq_balance),
                    "memory_ag_exactly_empty": mq_balance == (0, 0),
                    "loss_or_overflow_observed": False,
                    "closed": conservation_closed,
                },
                "final_state": final_state,
                "first_last_blocking_witness": witness,
                "terminal_tag_decode": {
                    "raw_mse0": state["mem_tag0"],
                    "raw_mse3": state["mem_tag3"],
                    "port0_null": {
                        "valid": 1,
                        "backpressure_ready": 1,
                    },
                    "port1_buffer": {
                        "valid": 1,
                        "same": 1,
                        "last": 0,
                        "last_index": 1,
                        "backpressure_ready": 1,
                    },
                    "port2_keep": {
                        "valid": 1,
                        "same": 1,
                        "last": 0,
                        "last_index": 0,
                        "backpressure_ready": 0,
                    },
                    "raw_backpressure_mse0": state["mem_bp0"],
                    "raw_backpressure_mse3": state["mem_bp3"],
                    "symmetric": terminal_tag_stable,
                },
                "stable_levels_count_as_progress": False,
            },
            "qualified_path_evidence": {
                "lc_supply_feature_started": feature_enabled,
                "owner_clock_qualified_records": len(event_lines),
                "records_evaluable": feature_enabled,
                "buffer_and_memory_conservation_adjudicated":
                    conservation_closed,
                "stable_levels_count_as_progress": False,
            },
            "materialized_config_causal_binding": {
                "stage": "sum_s1",
                "mse0": {
                    "memory_index_roots": [
                        "DRAM_LC.LC0",
                        "DRAM_LC.LC1",
                    ],
                    "buffer_row_root": "DRAM_LC.LC1",
                },
                "mse3": {
                    "memory_index_roots": [
                        "DRAM_LC.LC2",
                        "DRAM_LC.LC3",
                    ],
                    "buffer_row_root": "DRAM_LC.LC3",
                },
                "shared_root_present": True,
                "rtl_ready_equation":
                    "iga_lc_connect2ob_bp_post=&iga_lc_outport_bp_post",
                "cloud_refactor_relevant": (
                    "IGA_ROW_LC_Inbuffer now buffers its branch and reports "
                    "upstream ready as !fifo_full; the memory branch taps the "
                    "DRAM LC directly."
                ),
                "causal_cycle": [
                    "Memory_AG occurrence 185 dequeues and request 185 fires",
                    "Buffer_AG continues to occurrence 217 and fills depth 32",
                    "full Buffer_AG deasserts its shared LC destination ready",
                    "shared DRAM LC AND-ready cannot advance occurrence 186 "
                    "to Memory_AG",
                    "Memory_AG remains empty and issues no new read request",
                    "without returned data WR_Buffer_AG cannot drain the full "
                    "Buffer_AG queue",
                ],
                "dynamic_rule_adjudication": {
                    "rule":
                        "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
                    "former_status": "STRUCTURAL_RISK",
                    "v40_status": "DYNAMIC_ROOT_CAUSE_PROVEN",
                    "route_selected":
                        "independent branch roots plus complete rebuild",
                },
            },
            "canonical_decision_adjudication": {
                "accepted_as_generic_global_stall": True,
                "accepted_as_natural_terminal": False,
                "accepted_as_numeric_evidence": False,
                "local_boundary_refinement": (
                    "The generic MSE4 accepted-write boundary is a downstream "
                    "symptom. The first local divergence is memory-supply "
                    "occurrence 186 absent after both streams completed 185."
                ),
            },
            "formal_d": {
                "expected_count": formal_expected,
                "present_count": formal_present,
                "missing_count": formal_missing,
                "mismatch_byte_count": gate["mismatch_byte_count"],
                "mismatch_zero_evaluable": formal_missing == 0,
                "exact_set_complete":
                    result_terms["formal_readback_exact_set_complete"],
                "server_result_gate_all_terms_true":
                    result_terms["all_terms_true"],
                "server_result_status": gate["status"],
            },
            "last_proven_good": (
                "For both MSE0 and MSE3, Memory_AG enqueue/dequeue/request "
                "occurrences 1..185 complete, while Buffer_AG preserves "
                "217 enqueues, 185 dequeues and the exact remaining FIFO "
                "depth 32. Compile, feature binding and all conservation "
                "equalities are valid; no queue loss or overflow is observed."
            ),
            "first_divergence": (
                "MEMORY_AG_SUPPLY_OCCURRENCE_186_ABSENT_WHILE_BUFFER_AG_"
                "OCCURRENCES_186_TO_217_ACCUMULATE_TO_FIFO_DEPTH_32"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_SHARED_LC_AND_READY_CYCLE_BUFFER_AG_"
                "FULL_MEMORY_AG_EMPTY"
            ),
            "root_cause_scope": {
                "unique": conservation_closed and terminal_tag_stable,
                "owner": "materialized config topology on current RTL semantics",
                "functional_rtl_modified": False,
                "minimal_legal_route": (
                    "Allocate independent DRAM-LC roots for each stream's "
                    "Buffer ROW/COL branch so Buffer_AG full cannot suppress "
                    "the paired Memory_AG source. Rebuild mapping/bitstream "
                    "and revalidate the complete eight-stage contract."
                ),
                "claim_boundary": (
                    "v40 proves the current shared-root topology deadlocks "
                    "for this exact sum_s1 execution. It does not itself prove "
                    "a corrected package reaches natural terminal or formal D."
                ),
            },
            "e3_e4_e5": {
                "E3": False,
                "E4": False,
                "E5": False,
                "reason": (
                    "compile=0 but simulation/runner=125 under INT, sum_s1 "
                    "never completes, natural terminal is false, and formal "
                    "D is 0/48. mismatch=0 is unevaluable."
                ),
            },
            "blocker_delta": {
                "closed": [
                    "B_GAP_NODE0071_BUFFER_AG_TO_MEMORY_SUPPLY_SHARED_LC_"
                    "OCCURRENCE_OR_BACKPRESSURE_PENDING_LEAF",
                ],
                "opened": [
                    "B_GAP_NODE0071_SHARED_LC_AND_READY_CONFIG_TOPOLOGY_CYCLE",
                ],
                "held": [
                    "B_GAP_NODE0071_DYNAMIC_NATURAL_TERMINAL",
                    "B_GAP_NODE0071_FORMAL_D_48",
                ],
            },
            "successor": {
                "required": True,
                "class": "CONFIG_CORRECTION_PACKAGE",
                "strategy": (
                    "Use independent Buffer branch roots in every changed "
                    "sum/tail config, fully remap, retain low-overhead v40 "
                    "checkpoints, and return full natural-terminal/48D."
                ),
                "diagnostic_only": False,
                "config_change": True,
                "timeout_change": False,
                "backpressure_change": False,
                "functional_rtl_change": False,
            },
            "rule_confirmation": [
                "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            ],
            "rule_delta_proposal": {
                "status": "NONE",
                "reason": (
                    "The existing GAP branch-isolation rule already requires "
                    "either a progress proof or independent roots. v40 is the "
                    "dynamic counterexample that selects its existing route 2."
                ),
            },
            "numeric_sum_tail_workload_config_golden_repeated": False,
            "errors": report["errors"],
            "valid_receipt": valid_receipt,
        }
    )
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
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
