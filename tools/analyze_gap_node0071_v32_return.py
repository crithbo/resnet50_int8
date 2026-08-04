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

from tools import analyze_gap_node0071_v30_return as base


IDENTITY = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 133195
RETURN_SHA256 = (
    "6bf8f931104739d3f658959958d378fa97081ce7457b0098acff3b1ac3a07a6b"
)
SOURCE_SIZE = 1822477
SOURCE_SHA256 = (
    "c974125f0b3e913f733ad4c2341b922ea3551a62144b1062c6dd433d82e369a1"
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

    counts = base.last_record(observer, "COL_AG_MRM_LANE_COUNTS_V1")
    state = base.last_record(observer, "COL_AG_MRM_LANE_STATE_V1")
    witness = base.last_record(observer, "COL_AG_MRM_LANE_WITNESS_V1")
    events = base.event_records(observer, "COL_AG_MRM_LANE_EVENT_V1")

    col_values = [
        integer(event, "col_out") & 0x1F
        for event in events
        if integer(event, "col_accept", 0) == 1
    ]
    bag_values = [
        integer(event, "bag_idx") & 0x1F
        for event in events
        if integer(event, "bag_accept", 0) == 1
    ]
    strobes = [
        integer(event, "mrm_strb")
        for event in events
        if integer(event, "mrm_write_accept", 0) == 1
    ]
    lane_presence = {
        f"lane{lane}": any(
            strobe
            & sum(1 << (4 * bank + lane) for bank in range(8))
            for strobe in strobes
        )
        for lane in range(4)
    }
    col_has_1_and_3 = 1 in col_values and 3 in col_values
    mrm_missing_lane1 = not lane_presence["lane1"]
    matched_mse_mrm = integer(counts, "mse_write_accept") == integer(
        counts, "mrm_write_accept"
    )

    report.update(
        {
            "schema": "gap-node0071-v32-return-analysis-v1",
            "status": "ADJUDICATED_SUCCESSOR_REQUIRED",
            "analysis_owner_thread":
                "019fa366-cb1f-7ae2-880c-f527be0680cd",
            "return_target_thread":
                "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "runtime_binding": {
                **report["runtime_binding"],
                "col_ag_mrm_enable_in_argv":
                    "+RETURN_OBS_COL_AG_MRM_LANE" in argv,
                "col_ag_mrm_limit_in_argv":
                    "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256" in argv,
                "col_ag_mrm_time0_marker":
                    "col_ag_mrm_lane=1" in observer
                    and "col_ag_mrm_lane_limit=256" in observer,
                "col_ag_mrm_return_binding":
                    "col_ag_mrm_lane_enabled=true" in binding
                    and "col_ag_mrm_lane_records_returned=true" in binding,
            },
            "col_ag_mrm_lane_evidence": {
                "counts": counts,
                "state": state,
                "witness": witness,
                "event_record_count": len(events),
                "event_records": events,
                "accepted_col_lc0_values": col_values,
                "accepted_buffer_ag_indices": bag_values,
                "accepted_mrm_strobes": [f"0x{x:x}" for x in strobes],
                "accepted_mrm_lane_presence": lane_presence,
                "col_lc0_proves_values_1_and_3": col_has_1_and_3,
                "buffer_ag_accept_values": bag_values,
                "mrm_accept_missing_byte_lane_1": mrm_missing_lane1,
                "mse_mrm_accept_counts_equal": matched_mse_mrm,
                "stable_levels_count_as_progress": False,
                "claim_boundary": (
                    "COL-LC0 is a shared producer observation. It proves that "
                    "values 1/3 existed and were globally accepted, but does "
                    "not itself prove that the MSE0 queue input accepted those "
                    "values in the matching row/tag context."
                ),
            },
            "canonical_decision_adjudication": {
                "returned_decision": canonical["decision"],
                "returned_boundary": canonical["boundary"],
                "accepted_as_generic_stall_detection": True,
                "accepted_as_first_divergence": False,
                "reason": (
                    "The canonical record is a generic last-global-checkpoint "
                    "decision. The enabled v32 accepted-event chain is closer "
                    "and separates producer values from MSE0 Buffer-AG output."
                ),
            },
            "last_proven_good": (
                "COL-LC0 globally accepts values 1 and 3; every one of the "
                "eight writes that reaches the MSE write interface is also "
                "accepted by Buffer0 MRM with matching lane strobes, including "
                "lane3. Retained sum_s1 GA input/output remains 48/48 and "
                "MSE4 request/write-data remains 13/12 before the stall."
            ),
            "first_divergence": (
                "COL_LC0_ACCEPTED_BYTE_LANE1_VALUE_PRESENT_ONLY_BEFORE_"
                "MSE0_BUFFER_AG_ACTIVITY_AND_NO_BUFFER0_MRM_BYTE_LANE1_WRITE"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_MSE0_BUFFER_AG_INDEX_PAIRING_BEFORE_"
                "BYTE_LANE1_ENQUEUE_PENDING_INPUT_OR_MATCH_MASK_LEAF"
            ),
            "root_cause_scope": {
                "closed": [
                    "COL-LC0 never producing or accepting byte-lane values 1/3",
                    "MSE-to-MRM loss for a write that reaches the MSE interface",
                    "MRM strobe transformation losing every high lane",
                    "NRM read barrier causing the held Buffer0 ARM request",
                    "downstream GA/MSE4 losing every accepted upstream item",
                ],
                "remaining": [
                    "COL-LC0 value1 is not presented/accepted at MSE0 Buffer_AG_Idx_Queue input",
                    "row/column tag validity, same-index keep mask, or gotten mask suppresses the MSE0 match",
                    "MSE0 queue full/backpressure prevents the matched enqueue",
                    "a matched enqueue occurs but its queue output is not consumed",
                ],
                "unique_functional_root": False,
            },
            "blocker_delta": {
                "closed": (
                    "B_GAP_NODE0071_BUFFER0_SELECTED_BANK_READINESS_PARTIAL_"
                    "ROW_FILL_PENDING_COL_AG_OR_MRM_STROBE_LEAF"
                ),
                "opened": (
                    "B_GAP_NODE0071_MSE0_BUFFER_AG_INDEX_PAIRING_SUPPRESSES_"
                    "BYTE_LANE1_PENDING_INPUT_OR_MATCH_MASK_LEAF"
                ),
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "boundary": (
                    "MSE0 Buffer_AG_Idx_Queue direct row/column input accepts "
                    "and decoded validity/same/gotten masks -> matched enqueue "
                    "and FIFO full/count -> qualified dequeue/output"
                ),
                "config_change": False,
                "timeout_change": False,
            },
            "rule_confirmation": sorted(
                set(report.get("rule_confirmation", []))
                | {
                    "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
                    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                    "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                    "CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001",
                    "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                    "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001",
                    "CDA-GAP-8B-RD-BUFFER-BYTE-LANE-COVERAGE-001",
                }
            ),
            "rule_delta_proposal": "NONE",
            "numeric_sum_tail_workload_config_golden_repeated": False,
        }
    )
    report["e3_e4_e5"]["reason"] = (
        "compile=0 but INT/125 is not a natural terminal; all 48 formal D "
        "targets are missing, mismatch=0 is unevaluable, and the conjunctive "
        "SERVER_RESULT_GATE is false"
    )
    checks = (
        (len(events) == 20, "v32 event count differs"),
        (integer(counts, "col_accept") == 20, "v32 COL count differs"),
        (integer(counts, "bag_accept") == 5, "v32 Buffer-AG count differs"),
        (integer(counts, "mse_write_accept") == 8, "v32 MSE count differs"),
        (integer(counts, "mrm_write_accept") == 8, "v32 MRM count differs"),
        (col_has_1_and_3, "v32 did not prove COL values 1 and 3"),
        (mrm_missing_lane1, "v32 MRM unexpectedly accepted lane1"),
        (matched_mse_mrm, "v32 MSE/MRM accepted counts differ"),
    )
    report["errors"] = list(report.get("errors", []))
    for condition, message in checks:
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
