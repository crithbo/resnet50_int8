from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


INSTALL_NAME = "r5_n4_hw_v50_dterm_owner_diag"
BEGIN = "// v50 DTERM_OWNER_ACTUAL_CONSUMER_BEGIN"
END = "// v50 DTERM_OWNER_ACTUAL_CONSUMER_END"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def step(state: dict[str, int], event: dict[str, int], *, active=True, reset=False):
    if reset:
        for key in state:
            state[key] = 0
        return {"progress": 0, "snapshot": 0}
    if not active:
        return {"progress": 0, "snapshot": 0}
    qualified = {
        "lc": int(event.get("lc_valid", 0) and event.get("all_ready", 0)),
        "row": int(event.get("row_valid", 0) and event.get("row_ready", 0)),
        "buf_push": int(event.get("buf_wr", 0) and not event.get("buf_full", 0)),
        "buf_pop": int(event.get("buf_rd", 0) and not event.get("buf_empty", 1)),
        "desc_push": int(event.get("desc_wr", 0) and not event.get("desc_full", 0)),
        "desc_pop": int(event.get("desc_rd", 0) and not event.get("desc_empty", 1)),
    }
    last0 = int(
        qualified["lc"]
        and event.get("last", 0)
        and event.get("last_index", 5) == 0
    )
    desc_terminal = int(
        qualified["desc_pop"]
        and not qualified["desc_push"]
        and event.get("desc_pre_count", 0) == 1
    )
    post = int(state["after_desc"] and qualified["buf_push"])
    first = any(value and state[key] == 0 for key, value in qualified.items())
    first = first or (last0 and state["last0"] == 0) or desc_terminal or (
        post and state["post"] == 0
    )
    for key, value in qualified.items():
        state[key] += value
    state["last0"] += last0
    state["post"] += post
    if desc_terminal:
        state["after_desc"] = 1
    return {"progress": sum(qualified.values()), "snapshot": int(first)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        payload = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = payload.decode()
    block = observer[
        observer.index(BEGIN) : observer.index(END) + len(END)
    ]
    state = {
        "lc": 0, "row": 0, "buf_push": 0, "buf_pop": 0,
        "desc_push": 0, "desc_pop": 0, "last0": 0, "post": 0,
        "after_desc": 0,
    }
    trace = {
        "reset": step(state, {}, reset=True),
        "inactive": step(state, {"lc_valid": 1, "all_ready": 1}, active=False),
        "held_lc": step(state, {"lc_valid": 1, "all_ready": 0}),
        "first_lc_accept": step(state, {"lc_valid": 1, "all_ready": 1}),
        "stable_last_without_accept": step(
            state, {"lc_valid": 1, "all_ready": 0, "last": 1, "last_index": 0}
        ),
        "accepted_last_wrong_index": step(
            state, {"lc_valid": 1, "all_ready": 1, "last": 1, "last_index": 5}
        ),
        "accepted_last0": step(
            state, {"lc_valid": 1, "all_ready": 1, "last": 1, "last_index": 0}
        ),
        "simultaneous_push_pop": step(
            state,
            {"desc_wr": 1, "desc_rd": 1, "desc_full": 0,
             "desc_empty": 0, "desc_pre_count": 1},
        ),
        "true_descriptor_terminal": step(
            state,
            {"desc_wr": 0, "desc_rd": 1, "desc_empty": 0,
             "desc_pre_count": 1},
        ),
        "first_post_terminal_buffer_push": step(
            state, {"buf_wr": 1, "buf_full": 0}
        ),
        "held_full_buffer_request": step(
            state, {"buf_wr": 1, "buf_full": 1}
        ),
    }
    checks = {
        "reset_and_inactive_not_progress": (
            trace["reset"]["progress"] == 0 and trace["inactive"]["progress"] == 0
        ),
        "held_level_not_progress": trace["held_lc"]["progress"] == 0,
        "qualified_accept_progress": trace["first_lc_accept"]["progress"] == 1,
        "stable_last_not_terminal": (
            trace["stable_last_without_accept"]["progress"] == 0
        ),
        "wrong_index_not_terminal": state["last0"] == 1,
        "simultaneous_push_pop_not_terminal": (
            trace["simultaneous_push_pop"]["progress"] == 2
            and state["after_desc"] == 1
        ),
        "true_terminal_arms_post_boundary": (
            trace["true_descriptor_terminal"]["snapshot"] == 1
        ),
        "post_terminal_push_snapshots": (
            trace["first_post_terminal_buffer_push"]["snapshot"] == 1
        ),
        "full_request_not_progress": (
            trace["held_full_buffer_request"]["progress"] == 0
        ),
        "exact_owner_clock_reset": (
            "posedge u_NDP_Top_new.clk_db" in block
            and "negedge u_NDP_Top_new.rst_n_db" in block
        ),
        "qualified_predicates_present": all(
            token in block
            for token in (
                "dt_port[0][22] && (&",
                "buf_ag_idx_queue_wr_en",
                "!u_NDP_Top_new",
                "dt_desc_terminal = dt_desc_pop && !dt_desc_push",
                "fifo_counter",
            )
        ),
    }
    negatives = {
        "drop_ready_conjunct_fail_closed": (
            "dt_port[0][22] && (&"
            not in block.replace("dt_port[0][22] && (&", "", 1)
        ),
        "drop_last_index_equality_fail_closed": (
            "dt_port[dt_i][19:16] == 0"
            not in block.replace("dt_port[dt_i][19:16] == 0", "", 1)
        ),
        "drop_no_push_terminal_conjunct_fail_closed": (
            "dt_desc_pop && !dt_desc_push"
            not in block.replace("dt_desc_pop && !dt_desc_push", "", 1)
        ),
    }
    checks["negative_controls"] = all(negatives.values())
    report = {
        "schema": "node0004-v50-dterm-predicate-trace-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "trace": trace,
        "negative_controls": negatives,
        "observer": {
            "bytes": len(payload),
            "sha256": digest(payload),
            "span_sha256": digest(block.encode()),
        },
        "claim_boundary": (
            "Metadata-only event trace for the exact v50 predicates; no DUT "
            "execution and no terminal/formal-D claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
