"""Canonical parser for the isolated QAdd v53 Buffer5 read-ready probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
    "C_PINGPONG_PORT_SELECTION",
    "C_BUFFER5_MRM_REQUEST_DECODE",
    "C_BUFFER5_ROW_BANK_LANE_VALIDITY",
    "C_BUFFER5_WRITE_CLEAR_ORDER",
    "C_BUFFER5_READ_ACCEPT",
)


def fields(body: str) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    for key, value in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+|[A-Z][A-Z0-9_]*)", body):
        if value.lower().startswith("0x"):
            result[key] = int(value, 16)
        elif value.isdecimal():
            result[key] = int(value)
        else:
            result[key] = value
    return result


def parse(text: str) -> dict:
    marker = "# QADD_TAILROUND_BUFREADY_V53" in text
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
        event = match.group(2)
        if event == "EXEC_START": starts.append(row)
        elif event == "COMP_FINISH": finishes.append(row)
        elif event == "TAILROUND_FLOW": flow.append(row)
        elif event == "Q53_STATE": states.append(row)
        elif event == "Q53_EVENT": detail.append(row)

    monotonic = all(
        all(int(right.get(key, 0)) >= int(left.get(key, 0)) for key in QUALIFIED)
        for left, right in zip(flow, flow[1:])
    )
    frozen = sum(
        all(int(right.get(key, 0)) == int(left.get(key, 0)) for key in QUALIFIED)
        for left, right in zip(flow, flow[1:])
    )
    owners = sorted({(int(row.get("group", -1)), int(row.get("local_slice", -1))) for row in states})
    counts = Counter(str(row.get("kind", "")) for row in detail)
    last = states[-1] if states else {}
    req_valid = int(last.get("req_valid", 0))
    rd_en = int(last.get("rd_en", 0))
    bank_ready = int(last.get("bank_ready", 0))
    req_strb = int(last.get("req_strb", 0))
    valid_at_req = int(last.get("valid_at_req", 0))
    failed_banks = rd_en & ~bank_ready
    missing_lanes = req_strb & ~valid_at_req
    selector_consistent = (
        bool(states)
        and int(last.get("selected_ready", -1))
        == int(last.get("ready1" if int(last.get("pingpong", 0)) else "ready0", -2))
    )
    matrix = {
        "C_PINGPONG_PORT_SELECTION": {
            "positive": "selected_ready equals ready[pingpong] and both physical port readiness levels are present",
            "observed": selector_consistent,
            "snapshot": {key: last.get(key) for key in ("pingpong", "ready0", "ready1", "selected_ready")},
        },
        "C_BUFFER5_MRM_REQUEST_DECODE": {
            "positive": "a read request is decoded into req_valid/rd_en with row and lane strobes",
            "observed": req_valid != 0 and int(last.get("req_rw", 1)) == 0 and rd_en != 0,
            "snapshot": {key: last.get(key) for key in ("req_valid", "req_rw", "req_addr", "req_strb", "rd_en")},
        },
        "C_BUFFER5_ROW_BANK_LANE_VALIDITY": {
            "positive": "per-bank ready and valid-at-request identify every required missing bank/lane",
            "observed": rd_en != 0 and failed_banks != 0 and missing_lanes != 0,
            "failed_banks": failed_banks,
            "missing_lanes": missing_lanes,
            "snapshot": {key: last.get(key) for key in ("bank_ready", "valid_at_req", "req_strb", "req_addr")},
        },
        "C_BUFFER5_WRITE_CLEAR_ORDER": {
            "positive": "accepted write and clear transactions are separately counted and timestamped",
            "observed": counts["BUF5_WRITE_ACCEPT"] > 0,
            "write_accepts": counts["BUF5_WRITE_ACCEPT"],
            "valid_clears": counts["BUF5_VALID_CLEAR"],
        },
        "C_BUFFER5_READ_ACCEPT": {
            "positive": "an enabled Buffer5 read and bank-ready conjunction are accepted",
            "observed": counts["BUF5_READ_ACCEPT"] > 0,
            "read_accepts": counts["BUF5_READ_ACCEPT"],
        },
    }
    binding_ok = (
        marker
        and len(starts) == 1
        and int(starts[0].get("stage", -1)) == 1
        and bool(flow)
        and bool(states)
        and all(int(row.get("stage", -1)) == 1 for row in states)
        and owners == [(0, 0)]
        and len(detail) <= 96
    )
    if not binding_ok:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "TAILROUND_BUFREADY_BINDING_OR_SCOPE"
        reason = "marker/scope/state absent, selected owner not unique, or event budget exceeded"
    elif len(finishes) == 1 and int(finishes[0].get("stage", -1)) == 1:
        decision = "TAILROUND_SPLIT_NATURAL_TERMINAL_OBSERVED"
        boundary = "OP_TAIL_ROUND_COMP_FINISH"
        reason = "isolated tail_round reached COMP_FINISH"
    elif not monotonic:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "TAILROUND_QUALIFIED_COUNTER_REGRESSION"
        reason = "a qualified counter regressed"
    elif frozen >= 3:
        decision = "LONG_RUNNING_HANG_AT_BUFFER5_SELECTED_READ_READY"
        boundary = "BUF2MSE_RREQ_READY_OR_BUFFER5_BANK_LANE_VALIDITY"
        reason = "three complete stall windows froze after RDAG fill; selected Buffer5 readiness state localizes the cause"
    elif len(flow) >= 2:
        decision = "STILL_PROGRESSING_NOT_FINISHED"
        boundary = "AFTER_LAST_TAILROUND_QUALIFIED_ADVANCE"
        reason = "qualified tail_round events advanced but terminal is absent"
    else:
        decision = "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        boundary = "TAILROUND_QUALIFIED_PROGRESS_ABSENT"
        reason = "insufficient qualified snapshots"
    record = {
        "schema": "qlinearadd-node0007-tailround-bufready-canonical-v53",
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
        "selected_owners": [{"group": group, "local_slice": local_slice} for group, local_slice in owners],
        "qualified_frozen_windows": frozen,
        "qualified_monotonic": monotonic,
        "last_flow": {key: int(flow[-1].get(key, 0)) for key in QUALIFIED} if flow else {},
        "last_state": last,
        "candidate_ids": list(CANDIDATES),
        "candidate_matrix": matrix,
    }
    record["content_digest"] = {
        "algorithm": "sha256",
        "scope": "canonical_record_without_content_digest",
        "value": hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    return record


def selftest() -> bool:
    base = "stage=1 active_cycles=1 " + " ".join(f"{key}=0" for key in QUALIFIED)
    prefix = (
        "# QADD_TAILROUND_BUFREADY_V53 enabled=1\n"
        "1 | EXEC_START | stage=1\n"
        "2 | Q53_STATE | stage=1 group=0 local_slice=0 pingpong=0 ready0=0 ready1=1 selected_ready=0 "
        "mrm_ready5=0 req_valid=0x1 req_rw=0 req_addr=0 req_strb=0xf rd_en=0x1 "
        "bank_ready=0xfe valid_at_req=0x7 rreq_ready=0 buffer_mask=0xff nrm_barrier=0\n"
        "3 | Q53_EVENT | kind=BUF5_WRITE_ACCEPT wr_en=0xff row=0 req_valid=0xff req_strb=0xffffffff\n"
    )
    stable = prefix + "\n".join(f"{20+i} | TAILROUND_FLOW | {base}" for i in range(4))
    terminal = prefix + f"20 | TAILROUND_FLOW | {base}\n30 | COMP_FINISH | stage=1"
    moving = prefix + f"20 | TAILROUND_FLOW | {base}\n21 | TAILROUND_FLOW | {base.replace('rdag_rreq=0', 'rdag_rreq=1')}"
    wrong_owner = prefix.replace("group=0 local_slice=0", "group=1 local_slice=0") + f"20 | TAILROUND_FLOW | {base}"
    wrong_stage = stable.replace("1 | EXEC_START | stage=1", "1 | EXEC_START | stage=2", 1)
    cases = {
        "stable": stable,
        "terminal": terminal,
        "moving": moving,
        "missing_marker": stable.replace("# QADD_TAILROUND_BUFREADY_V53 enabled=1\n", ""),
        "wrong_owner": wrong_owner,
        "wrong_stage": wrong_stage,
    }
    expected = {
        "stable": "LONG_RUNNING_HANG_AT_BUFFER5_SELECTED_READ_READY",
        "terminal": "TAILROUND_SPLIT_NATURAL_TERMINAL_OBSERVED",
        "moving": "STILL_PROGRESSING_NOT_FINISHED",
        "missing_marker": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "wrong_owner": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "wrong_stage": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
    }
    results = {name: parse(value)["decision"] for name, value in cases.items()}
    matrix = parse(stable)["candidate_matrix"]
    return (
        results == expected
        and matrix["C_PINGPONG_PORT_SELECTION"]["observed"] is True
        and matrix["C_BUFFER5_MRM_REQUEST_DECODE"]["observed"] is True
        and matrix["C_BUFFER5_ROW_BANK_LANE_VALIDITY"]["observed"] is True
        and matrix["C_BUFFER5_WRITE_CLEAR_ORDER"]["observed"] is True
        and matrix["C_BUFFER5_READ_ACCEPT"]["observed"] is False
    )


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
