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

from tools import analyze_gap_node0071_v23_return as base


IDENTITY = "r5_n71_gap_v28_ga_mse4_final_pair_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 129696
RETURN_SHA256 = (
    "875a9ec0ade4f1957025e0b7cefb0e843830f6dca57db8c078d462c5df40b0ff"
)
SOURCE_SIZE = 1815690
SOURCE_SHA256 = (
    "7b34ef0b592ebfd86d3e75a0983a91c8d87271454139e609174cdce8afc7d422"
)


def fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"(\w+)=([^\s]+)", line))


def last_record(text: str, marker: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if marker in line]
    if not lines:
        return {}
    return fields(lines[-1])


def pair_events(text: str, marker: str) -> list[dict[str, Any]]:
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


def split_pair(value: str) -> list[int]:
    return [int(item) for item in value.split("/")]


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    base.RETURN_SHA256 = RETURN_SHA256
    base.RETURN_SIZE = RETURN_SIZE
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.SOURCE_SIZE = SOURCE_SIZE
    base.IDENTITY = IDENTITY
    base.RETURN_ROOT = RETURN_ROOT
    report = base.analyze(return_zip, source_zip)

    with zipfile.ZipFile(return_zip) as archive:
        observer = archive.read(
            f"{RETURN_ROOT}/runs/return_observer.log"
        ).decode("utf-8", errors="replace")
        binding = archive.read(
            f"{RETURN_ROOT}/evidence/observer_binding.txt"
        ).decode("utf-8", errors="replace")
        canonical = json.loads(
            archive.read(
                f"{RETURN_ROOT}/evidence/canonical_decision.json"
            )
        )

    pair_counts = last_record(observer, "GA_MSE4_FINAL_PAIR_COUNTS_V1")
    pair_state = last_record(observer, "GA_MSE4_FINAL_PAIR_STATE_V1")
    pair_witness = last_record(observer, "GA_MSE4_FINAL_PAIR_WITNESS_V1")
    dual = last_record(observer, "DUAL_INGRESS_COUNTS")
    buffer_to_ga = last_record(observer, "BUFFER_TO_GA_COUNTS")
    rd_path = last_record(observer, "RD_DATA_VLD_PATH_COUNTS_V1")
    prep = last_record(observer, "PREP_COUNT_CAUSE_COUNTS_V1")
    sg = last_record(observer, "SG_COUNTS")
    ga_events = pair_events(observer, "GA_MSE4_FINAL_PAIR_GA_EVENT_V1")
    m4_events = pair_events(observer, "GA_MSE4_FINAL_PAIR_M4_EVENT_V1")

    ga_complete = all(
        int(pair_counts.get(key, "-1")) == 48
        for key in (
            "ga_accept",
            "ga_p0_retire",
            "ga_wr_req",
            "ga_wr_hs",
            "ga_rd_hs",
        )
    )
    producer_symmetric = (
        int(dual.get("mse0_buf_accept", "-1"))
        == int(dual.get("mse3_buf_accept", "-2"))
        == 13
    )
    operand_capture = [
        int(dual.get("ga_operand0_capture", "-1")),
        int(dual.get("ga_operand2_capture", "-1")),
    ]
    group_accept = [
        int(buffer_to_ga.get("ga_group0_accept", "-1")),
        int(buffer_to_ga.get("ga_group2_accept", "-1")),
    ]
    prep_write = split_pair(rd_path.get("prep_wr", "-1/-1"))
    prep_read = split_pair(rd_path.get("prep_rd", "-1/-1"))

    report.update(
        {
            "schema": "gap-node0071-v28-return-analysis-v1",
            "status": "ADJUDICATED_SUCCESSOR_REQUIRED",
            "runtime_binding": {
                **report["runtime_binding"],
                "ga_mse4_feature_enable_in_argv":
                    "+RETURN_OBS_GA_MSE4_FINAL_PAIR"
                    in report["runtime_binding"]["simulator_argv"],
                "ga_mse4_feature_limit_in_argv":
                    "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512"
                    in report["runtime_binding"]["simulator_argv"],
                "ga_mse4_time0_marker":
                    "ga_mse4_final_pair=1 ga_mse4_final_pair_limit=512"
                    in observer,
                "ga_mse4_return_binding":
                    "ga_mse4_final_pair_enabled=true" in binding
                    and "ga_mse4_final_pair_records_returned=true" in binding,
            },
            "ga_mse4_final_pair_evidence": {
                "counts": pair_counts,
                "state": pair_state,
                "witness": pair_witness,
                "ga_event_records": len(ga_events),
                "mse4_event_records": len(m4_events),
                "ga_pipeline_and_outbuffer_complete_for_observed_inputs":
                    ga_complete,
                "mse4_request_accept": int(
                    pair_counts.get("m4_req_accept", "-1")
                ),
                "mse4_queue_dequeue": int(
                    pair_counts.get("m4_q_rd", "-1")
                ),
                "mse4_buffer_accept": int(
                    pair_counts.get("m4_buf_accept", "-1")
                ),
                "mse4_prepared_write": int(
                    pair_counts.get("m4_prep_wr", "-1")
                ),
                "mse4_prepared_read": int(
                    pair_counts.get("m4_prep_rd", "-1")
                ),
                "mse4_output_write_by_channel":
                    split_pair(pair_counts.get("m4_ob_wr", "-1/-1")),
                "mse4_output_read_by_channel":
                    split_pair(pair_counts.get("m4_ob_rd", "-1/-1")),
                "raw_m4_q_wr_excluded_from_progress": True,
                "raw_m4_q_wr_reason":
                    "q_wr remains level-high while q_full=1 and req_ready=0",
            },
            "evidence_dominance_reanalysis": {
                "producer_to_buffer_accept": [
                    int(dual.get("mse0_buf_accept", "-1")),
                    int(dual.get("mse3_buf_accept", "-1")),
                ],
                "producer_to_buffer_symmetric": producer_symmetric,
                "ga_operand_capture": operand_capture,
                "ga_group_accept_batches": group_accept,
                "rd_prepared_write": prep_write,
                "rd_prepared_read": prep_read,
                "prep_count_write": split_pair(
                    prep.get("wr", "-1/-1")
                ),
                "prep_count_read": split_pair(
                    prep.get("rd", "-1/-1")
                ),
                "prep_count_change": split_pair(
                    prep.get("count_change", "-1/-1")
                ),
                "prep_count_no_effect": split_pair(
                    prep.get("no_effect", "-1/-1")
                ),
                "sg_final": sg,
                "stable_levels_count_as_progress": False,
                "conclusion": (
                    "Both producers reach their buffers 13 times, but MSE0 "
                    "reaches only 8 prepared writes, 6 group0 batches and 48 "
                    "operand0 captures while MSE3 reaches 13, 8 and 64. "
                    "All 48 observed GA accepts retire and traverse the GA "
                    "outbuffer, so the first functional divergence precedes "
                    "the GA final pipeline and MSE4."
                ),
            },
            "canonical_decision_adjudication": {
                "returned_decision": canonical["decision"],
                "returned_boundary": canonical["boundary"],
                "accepted_as_stall_detection": True,
                "accepted_as_first_divergence": False,
                "reason": (
                    "The generic canonical boundary uses qualified global "
                    "progress, but downstream-complete v28 evidence and "
                    "retained dual-ingress evidence place the first unequal "
                    "producer-consumer count earlier."
                ),
            },
            "last_proven_good": (
                "MSE0 and MSE3 each have 13 qualified producer-to-buffer "
                "accepts; all 48 observed GA accepts retire through pipeline0 "
                "and the normal GA outbuffer, and MSE4 consumes 12 paired "
                "write-data transactions"
            ),
            "first_divergence": (
                "MSE0_BUFFER_ACCEPT_13_TO_PREPARED_WRITE_8_TO_GA_GROUP0_"
                "CAPTURE_6_VERSUS_MSE3_13_TO_13_TO_8"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_MSE0_BUFFER_TO_RD_PREPARED_TO_"
                "GA_GROUP0_CAPTURE_PENDING_LEAF"
            ),
            "root_cause_scope": {
                "closed": [
                    "GA accepted input not retiring through pipeline0",
                    "GA normal outbuffer losing an observed retired result",
                    "MSE4 losing one of the 12 available GA write-data beats",
                    "MSE0 or MSE3 producer failing before buffer acceptance",
                ],
                "remaining": [
                    "MSE0 Buffer0 ARM row read acceptance/clear",
                    "MSE0 RD inbuffer selected capture and prepared write",
                    "MSE0 prepared-data dequeue/data_vld to GA group0 capture",
                ],
                "unique_functional_root": False,
            },
            "blocker_delta": {
                "closed": (
                    "B_GAP_NODE0071_GA_FINAL_PIPELINE_TO_MSE4_"
                    "REQUEST_WDATA_PAIRING_PENDING_LEAF"
                ),
                "opened": (
                    "B_GAP_NODE0071_MSE0_BUFFER_TO_RD_PREPARED_TO_"
                    "GA_GROUP0_CAPTURE_PENDING_LEAF"
                ),
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "boundary": (
                    "MSE0 Buffer0 accepted row -> ARM read accept/clear -> "
                    "RD inbuffer selected capture -> prepared write/read -> "
                    "data_vld/ready -> GA group0 qualified capture"
                ),
                "config_change": False,
                "timeout_change": False,
            },
        }
    )
    report["e3_e4_e5"]["reason"] = (
        "compile=0 but INT/125 is not natural completion; all 48 formal D "
        "targets are missing, mismatch=0 is unevaluable, and the conjunction "
        "gate is false"
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
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
