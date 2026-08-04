from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import analyze_gap_node0071_v28_return as base


IDENTITY = "r5_n71_gap_v30_arm_ready_factor_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 355886
RETURN_SHA256 = (
    "b72a3baa7468aa6a09254c90a7d488aa949b37045b1dad83670cc8a9dc2239f6"
)
SOURCE_SIZE = 1819468
SOURCE_SHA256 = (
    "f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931"
)


def fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"(\w+)=([^\s]+)", line))


def last_record(text: str, marker: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if marker in line]
    return fields(lines[-1]) if lines else {}


def event_records(text: str, marker: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in text.splitlines():
        if marker not in line:
            continue
        item: dict[str, Any] = {
            "time_ps": int(line.split("|", 1)[0].strip())
        }
        for key, value in fields(line).items():
            try:
                item[key] = int(value, 16) if value.startswith("0x") else int(value)
            except ValueError:
                item[key] = value
        result.append(item)
    return result


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

    factor_counts = last_record(
        observer, "BUFFER0_ARM_READY_FACTOR_COUNTS_V1"
    )
    factor_state = last_record(
        observer, "BUFFER0_ARM_READY_FACTOR_STATE_V1"
    )
    factor_witness = last_record(
        observer, "BUFFER0_ARM_READY_FACTOR_WITNESS_V1"
    )
    m0_counts = last_record(
        observer, "MSE0_BUFFER_PREP_GROUP0_COUNTS_V1"
    )
    m0_state = last_record(
        observer, "MSE0_BUFFER_PREP_GROUP0_STATE_V1"
    )
    bp_counts = last_record(observer, "BP_PRE_FACTOR_COUNTS_V1")
    bp_state = last_record(observer, "BP_PRE_FACTOR_STATE_V1")
    rd_counts = last_record(observer, "RD_DATA_VLD_PATH_COUNTS_V1")
    prep_counts = last_record(observer, "PREP_COUNT_CAUSE_COUNTS_V1")
    dual_counts = last_record(observer, "DUAL_INGRESS_COUNTS")
    pair_counts = last_record(observer, "GA_MSE4_FINAL_PAIR_COUNTS_V1")
    events = event_records(
        observer, "BUFFER0_ARM_READY_FACTOR_EVENT_V1"
    )

    final_req = integer(factor_state, "req", 0)
    final_mask = integer(factor_state, "mask", 0)
    final_bank_ready = integer(factor_state, "bank_ready", 0)
    final_selected_ready = integer(factor_state, "selected_ready", 0)
    final_barrier = integer(factor_state, "barrier", -1)
    final_composite_ready = integer(factor_state, "composite_ready", -1)
    final_valid = integer(factor_state, "valid_at_addr", 0)
    lane_nibbles = [
        (final_valid >> (4 * bank)) & 0xF for bank in range(8)
    ]
    barrier_never_asserted = (
        integer(factor_counts, "barrier_edge", -1) == 0
        and all(integer(event, "barrier", -1) == 0 for event in events)
        and final_barrier == 0
    )
    all_selected_banks_not_ready = (
        final_req == final_mask == 0xFF
        and final_bank_ready == 0
        and final_selected_ready == 0
    )
    lane0_only = lane_nibbles == [1] * 8

    report.update(
        {
            "schema": "gap-node0071-v30-return-analysis-v1",
            "status": "ADJUDICATED_SUCCESSOR_REQUIRED",
            "analysis_owner_thread":
                "019fa366-cb1f-7ae2-880c-f527be0680cd",
            "return_target_thread":
                "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "runtime_binding": {
                **report["runtime_binding"],
                "arm_ready_factor_enable_in_argv":
                    "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS" in argv,
                "arm_ready_factor_limit_in_argv":
                    "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256"
                    in argv,
                "arm_ready_factor_time0_marker":
                    "buffer0_arm_ready_factors=1" in observer
                    and "buffer0_arm_ready_factors_limit=256"
                    in observer,
                "arm_ready_factor_return_binding":
                    "buffer0_arm_ready_factors_enabled=true" in binding
                    and "buffer0_arm_ready_factors_records_returned=true"
                    in binding,
            },
            "buffer0_arm_ready_factor_evidence": {
                "counts": factor_counts,
                "state": factor_state,
                "witness": factor_witness,
                "event_record_count": len(events),
                "event_records": events,
                "rtl_equation": (
                    "buf2arm_rreq_ready = "
                    "&(~buffer_mask | buf2arm_rreq_bank_ready) "
                    "& ~nrm2buf_rd_barrier"
                ),
                "nrm_read_barrier_never_asserted_in_factor_window":
                    barrier_never_asserted,
                "all_selected_banks_not_ready_at_stall":
                    all_selected_banks_not_ready,
                "valid_nibble_by_bank": lane_nibbles,
                "only_byte_lane_zero_valid_in_every_bank": lane0_only,
                "stable_levels_count_as_progress": False,
            },
            "retained_path_evidence": {
                "mse0_counts": m0_counts,
                "mse0_state": m0_state,
                "bp_pre_counts": bp_counts,
                "bp_pre_state": bp_state,
                "rd_data_counts": rd_counts,
                "prepared_count_counts": prep_counts,
                "dual_ingress_counts": dual_counts,
                "ga_mse4_pair_counts": pair_counts,
            },
            "canonical_decision_adjudication": {
                "returned_decision": canonical["decision"],
                "returned_boundary": canonical["boundary"],
                "accepted_as_generic_stall_detection": True,
                "accepted_as_first_divergence": False,
                "reason": (
                    "The generic canonical record identifies the last "
                    "global qualified checkpoint. The enabled v30 factor "
                    "observer is closer to the first divergence and proves "
                    "the Buffer0 read-ready conjunction leaf."
                ),
            },
            "last_proven_good": (
                "Within sum_s1, Buffer0 accepts two complete ARM row reads "
                "with all eight selected banks ready while the NRM read "
                "barrier is zero; retained downstream evidence remains "
                "lossless for every transaction that becomes available."
            ),
            "first_divergence": (
                "THIRD_BUFFER0_ARM_ROW_READ_HELD_WITH_ALL_SELECTED_BANK_"
                "READINESS_ZERO_AND_NRM_READ_BARRIER_ZERO"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_BUFFER0_SELECTED_BANK_READINESS_"
                "AFTER_PARTIAL_ROW_FILL_BYTE_LANE0_ONLY"
            ),
            "root_cause_scope": {
                "closed": [
                    "Buffer0 nrm2buf_rd_barrier causing the held ARM read",
                    "Buffer0 mask selecting an unintended subset of banks",
                    "a ready-high level being miscounted as progress",
                    "downstream GA or MSE4 losing a transaction that became available",
                ],
                "remaining": [
                    "IGA COL_LC0 accepted sequence fails to reach the required next byte-lane values",
                    "MSE0 Buffer-AG row/column materialization loses the accepted COL value",
                    "Buffer0 Memory_Req_Manager accepted write strobe/row does not materialize the intended byte lane",
                    "upstream memory-return/data-vld exhaustion prevents the remaining row lanes from being written",
                ],
                "unique_functional_root": False,
                "packaged_stage1_bitstream_sha256":
                    "768524002a7b5abd89f08a8fec9cf086c7cd429234bd5449c281a476db4fea7a",
                "static_config_contract": (
                    "GROUP0 COL_LC start/end/stride=0/4/1 and "
                    "buf_spatial_stride=[0,4,...,28]"
                ),
                "dynamic_static_contradiction": (
                    "The final accepted hardware state has only nibble "
                    "0001 in every selected bank, so the static 0,1,2,3 "
                    "coverage claim is not sufficient to assign the next "
                    "leaf without observing accepted COL/address/strobe."
                ),
            },
            "blocker_delta": {
                "closed": (
                    "B_GAP_NODE0071_BUFFER0_ARM_READ_READY_CONJUNCTION_"
                    "PENDING_BANK_READY_OR_NRM_BARRIER_LEAF"
                ),
                "opened": (
                    "B_GAP_NODE0071_BUFFER0_SELECTED_BANK_READINESS_"
                    "PARTIAL_ROW_FILL_PENDING_COL_AG_OR_MRM_STROBE_LEAF"
                ),
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "boundary": (
                    "MSE0 IGA COL_LC0 qualified output -> WR_Buffer_AG "
                    "accepted row/column/tag -> Memory_Req_Manager "
                    "qualified request/strobe/write -> Buffer0 per-bank "
                    "byte-valid transition at the held ARM row"
                ),
                "config_change": False,
                "timeout_change": False,
                "required_signals": [
                    "COL_LC0 tag/value and downstream acceptance",
                    "MSE0 buffer-AG accepted row/column/tag",
                    "MSE0 mse2buf request-valid/column and data write handshake",
                    "Buffer0 mrm2buf request-valid/strobe/row and accepted write",
                    "Buffer0 selected-row valid nibble transition",
                ],
            },
            "rule_confirmation": [
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001",
                "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001",
                "CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001",
            ],
            "rule_delta_proposal": "NONE",
            "numeric_sum_tail_workload_config_golden_repeated": False,
        }
    )
    report["e3_e4_e5"]["reason"] = (
        "compile=0 but INT/125 is not a natural terminal; all 48 formal D "
        "targets are missing, mismatch=0 is unevaluable, and the conjunctive "
        "SERVER_RESULT_GATE is false"
    )
    report["errors"] = list(report.get("errors", []))
    for condition, message in (
        (barrier_never_asserted, "v30 did not exclude the NRM barrier"),
        (all_selected_banks_not_ready, "v30 did not prove selected-bank blocking"),
        (lane0_only, "v30 final selected-row byte validity was not lane0-only"),
        (len(events) == 7, "v30 factor event exact count differs"),
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
