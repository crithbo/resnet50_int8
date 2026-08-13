"""Canonical parser for the isolated QAdd v52 tail-round queue-flow probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
from collections import Counter
from pathlib import Path


QUALIFIED = (
    "mse0_addr", "mse0_req", "mse0_meta", "mse0_consume", "mse0_buf",
    "ga_in", "ga_out", "buf5_wr", "buf5_rd", "bag_enq", "bag_deq",
    "rdag_enq", "rdag_deq", "rdag_rreq", "wr_req", "wr_prepared",
    "wr_ob_enq0", "wr_ob_enq1", "wr_ob_deq0", "wr_ob_deq1",
    "mse4_req0", "mse4_req1", "mse4_wdata0", "mse4_wdata1",
)
CANDIDATES = (
    "C_BAG_PAIR_DEQUEUE",
    "C_RDAG_ELIGIBILITY_READ_REQUEST",
    "C_WR_PREPARED_SECOND_BEAT",
    "C_CHANNEL1_OUTPUT_DELIVERY",
)


def fields(body: str) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for key, value in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+|[A-Z][A-Z0-9_]*)", body):
        if value.lower().startswith("0x"):
            result[key] = int(value, 16)
        elif value.isdecimal():
            result[key] = int(value, 10)
        else:
            result[key] = value
    return result


def parse(text: str) -> dict:
    marker = "# QADD_TAILROUND_QUEUEFLOW_V52" in text
    starts: list[dict] = []
    finishes: list[dict] = []
    flow: list[dict] = []
    states: list[dict] = []
    detail: list[dict] = []
    pattern = re.compile(r"^(\d+)\s+\|\s+([A-Z0-9_]+)\s+\|\s*(.*)$")
    for line_no, line in enumerate(text.splitlines(), 1):
        match = pattern.match(line)
        if not match:
            continue
        row = {"line": line_no, "time_ps": int(match.group(1)), **fields(match.group(3))}
        instance = re.search(r"\binst=([^\s]+)", match.group(3))
        if instance:
            row["inst"] = instance.group(1)
        event = match.group(2)
        if event == "EXEC_START": starts.append(row)
        elif event == "COMP_FINISH": finishes.append(row)
        elif event == "TAILROUND_FLOW": flow.append(row)
        elif event == "Q52_STATE": states.append(row)
        elif event == "Q52_EVENT": detail.append(row)

    monotonic = all(
        all(int(right.get(key, 0)) >= int(left.get(key, 0)) for key in QUALIFIED)
        for left, right in zip(flow, flow[1:])
    )
    frozen = sum(
        all(int(right.get(key, 0)) == int(left.get(key, 0)) for key in QUALIFIED)
        for left, right in zip(flow, flow[1:])
    )
    counts = Counter(str(row.get("kind", "")) for row in detail)
    instances = sorted({str(row.get("inst", "")) for row in detail})
    by_channel = Counter(
        (str(row.get("kind", "")), int(row.get("channel", -1))) for row in detail
    )
    observations = {
        "bag_enq": counts["BAG_ENQ"],
        "bag_deq": counts["BAG_DEQ"],
        "rdag_enq": counts["RDAG_ENQ"],
        "rdag_deq": counts["RDAG_DEQ"],
        "rdag_rreq": counts["RDAG_RREQ"],
        "wr_req": counts["WR_REQ"],
        "wr_prepared": counts["WR_PREPARED"],
        "wr_ob_enq0": by_channel[("WR_OB_ENQ", 0)],
        "wr_ob_enq1": by_channel[("WR_OB_ENQ", 1)],
        "mse4_req0": by_channel[("MSE4_REQ", 0)],
        "mse4_req1": by_channel[("MSE4_REQ", 1)],
        "mse4_wdata0": by_channel[("MSE4_WDATA", 0)],
        "mse4_wdata1": by_channel[("MSE4_WDATA", 1)],
    }
    candidate_matrix = {
        "C_BAG_PAIR_DEQUEUE": {
            "positive": "BAG_ENQ and BAG_DEQ payload/tag events",
            "negative": "BAG_ENQ without BAG_DEQ while queue state is nonempty/full",
            "observed": observations["bag_enq"] > 0 and observations["bag_deq"] > 0,
        },
        "C_RDAG_ELIGIBILITY_READ_REQUEST": {
            "positive": "RDAG_ENQ then RDAG_DEQ and RDAG_RREQ",
            "negative": "RDAG_ENQ without RDAG_DEQ/RREQ plus buf_ready/wr_ready state",
            "observed": observations["rdag_enq"] > 0 and observations["rdag_deq"] > 0 and observations["rdag_rreq"] > 0,
        },
        "C_WR_PREPARED_SECOND_BEAT": {
            "positive": "two WR_REQ and two WR_PREPARED events",
            "negative": "WR_REQ exceeds WR_PREPARED with prepared/data/hold state",
            "observed": observations["wr_req"] >= 2 and observations["wr_prepared"] >= 2,
        },
        "C_CHANNEL1_OUTPUT_DELIVERY": {
            "positive": "channel1 request, output enqueue, and accepted wdata",
            "negative": "channel1 request without channel1 output/wdata",
            "observed": observations["mse4_req1"] > 0 and observations["wr_ob_enq1"] > 0 and observations["mse4_wdata1"] > 0,
        },
    }
    if (not marker or len(starts) != 1 or int(starts[0].get("stage", -1)) != 1
            or not flow or not states or len(detail) > 96 or len(instances) != 1
            or instances == [""]):
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "TAILROUND_QUEUEFLOW_BINDING_OR_SCOPE"
        reason = "marker/scope/snapshots absent, event budget exceeded, or instance ownership is not unique"
    elif len(finishes) == 1 and int(finishes[0].get("stage", -1)) == 1:
        decision = "TAILROUND_SPLIT_NATURAL_TERMINAL_OBSERVED"
        boundary = "OP_TAIL_ROUND_COMP_FINISH"
        reason = "isolated tail_round reached COMP_FINISH"
    elif not monotonic:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "TAILROUND_QUALIFIED_COUNTER_REGRESSION"
        reason = "a qualified counter regressed"
    elif frozen >= 3:
        decision = "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_QUEUEFLOW"
        boundary = "AFTER_LAST_TAILROUND_QUALIFIED_ADVANCE"
        reason = "three or more complete stall windows had no qualified advance"
    elif len(flow) >= 2:
        decision = "STILL_PROGRESSING_NOT_FINISHED"
        boundary = "AFTER_LAST_TAILROUND_QUALIFIED_ADVANCE"
        reason = "qualified tail_round events advanced but terminal is absent"
    else:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "TAILROUND_QUALIFIED_PROGRESS_ABSENT"
        reason = "insufficient qualified snapshots"
    record = {
        "schema": "qlinearadd-node0007-tailround-queueflow-canonical-v52",
        "decision": decision,
        "reason": reason,
        "boundary": boundary,
        "stage_scope": "op_tail_round",
        "qualified_clock": "clk_sg",
        "snapshot_clock": "clk_db",
        "stable_level_is_progress": False,
        "marker_present": marker,
        "ordered_start_count": len(starts),
        "ordered_finish_count": len(finishes),
        "flow_samples": len(flow),
        "state_samples": len(states),
        "detail_event_count": len(detail),
        "detail_event_budget": 96,
        "detail_instances": instances,
        "qualified_frozen_windows": frozen,
        "qualified_monotonic": monotonic,
        "last_flow": {key: int(flow[-1].get(key, 0)) for key in QUALIFIED} if flow else {},
        "last_state": states[-1] if states else {},
        "candidate_ids": list(CANDIDATES),
        "candidate_observations": observations,
        "candidate_matrix": candidate_matrix,
    }
    record["content_digest"] = {
        "algorithm": "sha256",
        "scope": "canonical_record_without_content_digest",
        "value": hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    return record


def selftest() -> bool:
    base = "stage=1 active_cycles=1 " + " ".join(f"{key}=0" for key in QUALIFIED)
    start = "1 | EXEC_START | stage=1"
    detail = "\n".join([
        "3 | Q52_EVENT | inst=tb.dut kind=BAG_ENQ row=0x0 col=0x10",
        "4 | Q52_EVENT | inst=tb.dut kind=BAG_DEQ",
        "5 | Q52_EVENT | inst=tb.dut kind=RDAG_ENQ",
        "6 | Q52_EVENT | inst=tb.dut kind=RDAG_DEQ",
        "7 | Q52_EVENT | inst=tb.dut kind=RDAG_RREQ",
        "8 | Q52_EVENT | inst=tb.dut kind=WR_REQ",
        "9 | Q52_EVENT | inst=tb.dut kind=WR_PREPARED",
        "9 | Q52_EVENT | inst=tb.dut kind=WR_REQ",
        "9 | Q52_EVENT | inst=tb.dut kind=WR_PREPARED",
        "10 | Q52_EVENT | inst=tb.dut kind=MSE4_REQ channel=1",
        "11 | Q52_EVENT | inst=tb.dut kind=WR_OB_ENQ channel=1",
        "12 | Q52_EVENT | inst=tb.dut kind=MSE4_WDATA channel=1",
    ])
    prefix = "# QADD_TAILROUND_QUEUEFLOW_V52 enabled=1\n" + start + "\n2 | Q52_STATE | stage=1"
    cases = {
        "stable_level": prefix + "\n" + detail + "\n20 | TAILROUND_FLOW | " + base + "\n21 | TAILROUND_FLOW | " + base + "\n22 | TAILROUND_FLOW | " + base + "\n23 | TAILROUND_FLOW | " + base,
        "simultaneous": prefix + "\n3 | Q52_EVENT | inst=tb.dut kind=RDAG_RREQ\n20 | TAILROUND_FLOW | " + base + "\n21 | TAILROUND_FLOW | " + base.replace("rdag_rreq=0", "rdag_rreq=1").replace("wr_prepared=0", "wr_prepared=1"),
        "terminal": prefix + "\n3 | Q52_EVENT | inst=tb.dut kind=WR_PREPARED\n20 | TAILROUND_FLOW | " + base + "\n30 | COMP_FINISH | stage=1",
        "missing_marker": start + "\n2 | Q52_STATE | stage=1\n20 | TAILROUND_FLOW | " + base,
        "multi_instance": prefix + "\n" + detail + "\n13 | Q52_EVENT | inst=tb.other kind=BAG_ENQ\n20 | TAILROUND_FLOW | " + base,
        "over_budget": prefix + "\n" + "\n".join(
            f"{100+i} | Q52_EVENT | inst=tb.dut kind=BAG_ENQ" for i in range(97)
        ) + "\n20 | TAILROUND_FLOW | " + base,
    }
    expected = {
        "stable_level": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_QUEUEFLOW",
        "simultaneous": "STILL_PROGRESSING_NOT_FINISHED",
        "terminal": "TAILROUND_SPLIT_NATURAL_TERMINAL_OBSERVED",
        "missing_marker": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "multi_instance": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "over_budget": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
    }
    results = {name: parse(value)["decision"] for name, value in cases.items()}
    matrix = parse(cases["stable_level"])["candidate_matrix"]
    return results == expected and all(row["observed"] for row in matrix.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observer-log", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        passed = selftest()
        print(json.dumps({"pass": passed}))
        return 0 if passed else 1
    if args.observer_log is None or args.output is None:
        parser.error("--observer-log and --output are required")
    record = parse(args.observer_log.read_text(encoding="utf-8", errors="replace"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": record["decision"], "output": str(args.output)}))
    return 0 if record["decision"] != "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
