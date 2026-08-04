from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import analyze_gap_node0071_v23_return as base


IDENTITY = "r5_n71_gap_v24_prep_count_cause_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 92726
RETURN_SHA256 = (
    "1ef3b3d7d091004784e46eb72c405fb25d010632d80a423ca99028089fcd43f4"
)
SOURCE_SIZE = 1812177
SOURCE_SHA256 = (
    "ad71f6d6ab75f0992505d9d4656c058aa4011776bfc9b7c1c14bd78ec9b428ab"
)


def values(line: str) -> dict[str, str]:
    return {
        key: value
        for key, value in re.findall(r"(\w+)=([^\s]+)", line)
    }


def parse_pc_events(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line in text.splitlines():
        if "PREP_COUNT_CAUSE_EVENT_V1" not in line:
            continue
        fields = values(line)
        result.append(
            {
                "time_ps": int(line.split("|", 1)[0].strip()),
                **{
                    key: int(fields[key])
                    for key in (
                        "n",
                        "mse",
                        "sg_edge",
                        "prev_rst_n",
                        "prev_slice_rst",
                        "prev_wr",
                        "prev_rd",
                        "prev_count",
                        "rst_n",
                        "slice_rst",
                        "wr",
                        "rd",
                        "count",
                        "no_effect",
                        "lt_req",
                        "bp_pre",
                        "ob_bp_pre",
                        "data_vld",
                    )
                },
                "prev_tsf": fields["prev_tsf"],
                "prev_spatial": fields["prev_spatial"],
                "tsf": fields["tsf"],
                "spatial": fields["spatial"],
            }
        )
    return result


def parse_ga(text: str, kind: str) -> list[dict[str, Any]]:
    marker = f"SG_GA_{kind}"
    result: list[dict[str, Any]] = []
    for line in text.splitlines():
        if marker not in line:
            continue
        fields = values(line)
        result.append(
            {
                "time_ps": int(line.split("|", 1)[0].strip()),
                "n": int(fields["n"]),
                "pe": fields["pe"],
                "tag": int(fields["tag"], 16),
            }
        )
    return result


def parse_mse4(text: str, kind: str) -> list[dict[str, Any]]:
    marker = f"SG_MSE4_{kind}"
    result: list[dict[str, Any]] = []
    for line in text.splitlines():
        if marker not in line:
            continue
        fields = values(line)
        result.append(
            {
                "time_ps": int(line.split("|", 1)[0].strip()),
                "n": int(fields["n"]),
                "channel": int(fields["ch"]),
                "req_channel_count": int(fields["req_ch"]),
                "wdata_channel_count": int(fields["wdata_ch"]),
                "outstanding": int(fields["outstanding"]),
                "address": fields.get("addr"),
            }
        )
    return result


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

    pc_events = parse_pc_events(observer)
    pc_by_mse = {
        mse: [item for item in pc_events if item["mse"] == mse]
        for mse in (0, 3)
    }
    ga_input = parse_ga(observer, "INPUT")
    ga_output = parse_ga(observer, "OUTPUT")
    mse4_req = parse_mse4(observer, "REQ")
    mse4_wdata = parse_mse4(observer, "WDATA")
    pc_counts = base.last_line(observer, "PREP_COUNT_CAUSE_COUNTS_V1")
    pc_state = base.last_line(observer, "PREP_COUNT_CAUSE_STATE_V1")
    pc_witness = base.last_line(observer, "PREP_COUNT_CAUSE_WITNESS_V1")
    sg_counts = base.last_line(observer, "SG_COUNTS")

    def count_sequence(mse: int) -> list[int]:
        return [item["count"] for item in pc_by_mse[mse]]

    pc_symmetric = (
        len(pc_by_mse[0]) == len(pc_by_mse[3]) == 12
        and count_sequence(0) == count_sequence(3)
        and all(item["rst_n"] == 1 for item in pc_events)
        and all(item["slice_rst"] == 0 for item in pc_events)
    )
    input_tags = {
        f"0x{tag:x}": count
        for tag, count in sorted(Counter(
            item["tag"] for item in ga_input
        ).items())
    }
    output_tags = {
        f"0x{tag:x}": count
        for tag, count in sorted(Counter(
            item["tag"] for item in ga_output
        ).items())
    }
    req_by_channel = Counter(item["channel"] for item in mse4_req)
    wdata_by_channel = Counter(item["channel"] for item in mse4_wdata)

    report.update(
        {
            "schema": "gap-node0071-v24-return-analysis-v1",
            "status": "ADJUDICATED_SUCCESSOR_REQUIRED",
            "runtime_binding": {
                **report["runtime_binding"],
                "prep_count_enable_in_argv":
                    "+RETURN_OBS_PREP_COUNT_CAUSE"
                    in report["runtime_binding"]["simulator_argv"],
                "prep_count_limit_in_argv":
                    "+RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512"
                    in report["runtime_binding"]["simulator_argv"],
                "prep_count_time0_marker":
                    "prep_count_cause=1 prep_count_cause_limit=512"
                    in observer,
                "prep_count_returned_binding":
                    "prep_count_cause_enabled=true" in binding
                    and "prep_count_cause_records_returned=true" in binding,
            },
            "prepared_count_cause_evidence": {
                "final_counts_record": pc_counts,
                "final_state_record": pc_state,
                "final_witness_record": pc_witness,
                "event_count": len(pc_events),
                "mse0_event_count": len(pc_by_mse[0]),
                "mse3_event_count": len(pc_by_mse[3]),
                "mse0_count_sequence": count_sequence(0),
                "mse3_count_sequence": count_sequence(3),
                "all_rst_n_asserted": all(
                    item["rst_n"] == 1 for item in pc_events
                ),
                "all_slice_rst_deasserted": all(
                    item["slice_rst"] == 0 for item in pc_events
                ),
                "mse0_mse3_update_sequence_symmetric": pc_symmetric,
                "qualified_write_count": {
                    "mse0": sum(item["wr"] for item in pc_by_mse[0]),
                    "mse3": sum(item["wr"] for item in pc_by_mse[3]),
                },
                "qualified_read_count": {
                    "mse0": sum(item["rd"] for item in pc_by_mse[0]),
                    "mse3": sum(item["rd"] for item in pc_by_mse[3]),
                },
                "count_change_count": {
                    "mse0": sum(
                        item["count"] != item["prev_count"]
                        for item in pc_by_mse[0]
                    ),
                    "mse3": sum(
                        item["count"] != item["prev_count"]
                        for item in pc_by_mse[3]
                    ),
                },
                "prior_mse3_count_blocker_closed": pc_symmetric,
                "stable_level_counts_as_progress": False,
            },
            "new_boundary_evidence": {
                "final_sg_counts_record": sg_counts,
                "ga_input_count": len(ga_input),
                "ga_output_count": len(ga_output),
                "ga_input_tag_histogram": input_tags,
                "ga_output_tag_histogram": output_tags,
                "ga_input_without_same-run_output_count":
                    len(ga_input) - len(ga_output),
                "mse4_request_by_channel": {
                    str(ch): req_by_channel[ch] for ch in (0, 1)
                },
                "mse4_write_data_by_channel": {
                    str(ch): wdata_by_channel[ch] for ch in (0, 1)
                },
                "mse4_final_outstanding_by_channel": {
                    str(ch): req_by_channel[ch] - wdata_by_channel[ch]
                    for ch in (0, 1)
                },
                "last_mse4_request": mse4_req[-1] if mse4_req else None,
                "last_mse4_write_data":
                    mse4_wdata[-1] if mse4_wdata else None,
                "qualified_stall_window_cycles": 1048576,
                "stable_after_last_qualified_progress": True,
            },
            "last_proven_good": (
                "MSE0/MSE3 prepared-count paths are symmetric: each has "
                "7 qualified writes, 3 reads, count 0->8->0 twice, "
                "rst_n=1 and slice_rst=0; GA produced 32 outputs and MSE4 "
                "accepted 8 write-data beats on each channel"
            ),
            "first_divergence": (
                "FINAL_GA_INPUT_BATCH_TO_GA_OUTPUT_AND_MSE4_WRITE_DATA_"
                "ABSENT_WITH_MSE4_REQUEST_OUTSTANDING_1_PER_CHANNEL"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_GA_FINAL_PIPELINE_TO_MSE4_"
                "REQUEST_WRITE_DATA_PAIRING_PENDING_LEAF"
            ),
            "root_cause_scope": {
                "closed": [
                    "MSE3 prepared-data counter never updates",
                    "MSE3 local rst_n/slice_rst clears the counter",
                    "MSE3 prepared write/read path asymmetry",
                    "observer XMR misses the MSE3 count transition",
                ],
                "remaining": [
                    (
                        "final accepted GA int32 input batch is not "
                        "retired into eight GA outbuffer writes"
                    ),
                    (
                        "MSE4 issues a ninth request per channel while only "
                        "eight corresponding write-data beats retire"
                    ),
                    (
                        "GA final-result tag/valid/backpressure versus MSE4 "
                        "request/write-data occurrence/last ownership"
                    ),
                ],
                "unique_functional_root": False,
            },
            "blocker_delta": {
                "closed": (
                    "B_GAP_NODE0071_MSE3_PREPARED_COUNT_UPDATE_"
                    "PENDING_LOCAL_RESET_OR_UPDATE_CAUSE"
                ),
                "opened": (
                    "B_GAP_NODE0071_GA_FINAL_PIPELINE_TO_MSE4_"
                    "REQUEST_WDATA_PAIRING_PENDING_LEAF"
                ),
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "boundary": (
                    "GA final pipeline valid/tag/enable/outbuffer write -> "
                    "MSE4 request/write-data accepted occurrence/last and "
                    "per-channel outstanding"
                ),
                "config_change": False,
                "timeout_change": False,
                "package_release_deferred_until_current_rule_sha": True,
            },
        }
    )
    report["e3_e4_e5"]["reason"] = (
        "compile=0 but INT/125 is not natural completion; all 48 formal D "
        "targets are missing, so mismatch=0 is unevaluable and the joint "
        "server result gate is false"
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
