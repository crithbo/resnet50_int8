from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


INSTALL_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
BEGIN = "// v51 LC13_LC14_ACTUAL_CONSUMER_BEGIN"
END = "// v51 LC13_LC14_ACTUAL_CONSUMER_END"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def step(
    state: dict[str, int],
    event: dict[str, int],
    *,
    active: bool = True,
    reset: bool = False,
) -> dict[str, int]:
    if reset:
        for key in state:
            state[key] = 0
        return {"qualified": 0, "trigger": 0}
    if not active:
        return {"qualified": 0, "trigger": 0}
    q13 = int(event.get("lc13_valid", 0) and event.get("lc13_all_ready", 0))
    q14_capture = int(
        event.get("lc14_input_valid", 0)
        and event.get("lc14_same_mask", 0)
        and event.get("lc14_input_ready", 0)
    )
    q14_write = int(event.get("lc14_wr_en", 0) and not event.get("lc14_full", 0))
    q14_out = int(event.get("lc14_valid", 0) and event.get("lc14_all_ready", 0))
    q15_capture = int(
        event.get("lc15_input_valid", 0)
        and event.get("lc15_same_mask", 0)
        and event.get("lc15_input_ready", 0)
    )
    q15_out = int(event.get("lc15_valid", 0) and event.get("lc15_all_ready", 0))
    same_suppress = int(
        event.get("lc14_input_valid", 0)
        and event.get("lc14_gotten", 0)
        and not event.get("lc14_same_mask", 1)
    )
    qualified = {
        "q13": q13,
        "q14_capture": q14_capture,
        "q14_write": q14_write,
        "q14_out": q14_out,
        "q15_capture": q15_capture,
        "q15_out": q15_out,
    }
    trigger = int(
        any(value and state[key] == 0 for key, value in qualified.items())
        or (same_suppress and state["same_suppress"] == 0)
        or (
            event.get("lc13_valid", 0)
            and not event.get("lc13_all_ready", 0)
            and state["hold13"] == 0
        )
    )
    for key, value in qualified.items():
        state[key] += value
    state["same_suppress"] += same_suppress
    if event.get("lc13_valid", 0) and not event.get("lc13_all_ready", 0):
        state["hold13"] = 1
    return {"qualified": sum(qualified.values()), "trigger": trigger}


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
        "q13": 0,
        "q14_capture": 0,
        "q14_write": 0,
        "q14_out": 0,
        "q15_capture": 0,
        "q15_out": 0,
        "same_suppress": 0,
        "hold13": 0,
    }
    trace = {
        "reset": step(state, {}, reset=True),
        "inactive": step(
            state,
            {"lc13_valid": 1, "lc13_all_ready": 1},
            active=False,
        ),
        "held_lc13": step(
            state, {"lc13_valid": 1, "lc13_all_ready": 0}
        ),
        "accepted_lc13": step(
            state, {"lc13_valid": 1, "lc13_all_ready": 1}
        ),
        "lc14_valid_without_ready": step(
            state,
            {
                "lc14_input_valid": 1,
                "lc14_same_mask": 1,
                "lc14_input_ready": 0,
            },
        ),
        "lc14_same_suppressed": step(
            state,
            {
                "lc14_input_valid": 1,
                "lc14_gotten": 1,
                "lc14_same_mask": 0,
                "lc14_input_ready": 1,
            },
        ),
        "lc14_capture": step(
            state,
            {
                "lc14_input_valid": 1,
                "lc14_same_mask": 1,
                "lc14_input_ready": 1,
            },
        ),
        "lc14_full_write_attempt": step(
            state, {"lc14_wr_en": 1, "lc14_full": 1}
        ),
        "lc14_write_and_out": step(
            state,
            {
                "lc14_wr_en": 1,
                "lc14_full": 0,
                "lc14_valid": 1,
                "lc14_all_ready": 1,
            },
        ),
        "lc15_capture_and_out": step(
            state,
            {
                "lc15_input_valid": 1,
                "lc15_same_mask": 1,
                "lc15_input_ready": 1,
                "lc15_valid": 1,
                "lc15_all_ready": 1,
            },
        ),
    }
    checks = {
        "reset_inactive_no_progress": (
            trace["reset"]["qualified"] == 0
            and trace["inactive"]["qualified"] == 0
        ),
        "held_lc13_not_transaction": trace["held_lc13"]["qualified"] == 0,
        "held_lc13_first_edge_snapshots": trace["held_lc13"]["trigger"] == 1,
        "accepted_lc13_transaction": trace["accepted_lc13"]["qualified"] == 1,
        "lc14_requires_ready_and_mask": (
            trace["lc14_valid_without_ready"]["qualified"] == 0
        ),
        "same_gotten_is_state_not_accept": (
            trace["lc14_same_suppressed"]["qualified"] == 0
            and state["q14_capture"] == 1
        ),
        "full_counter_write_not_accept": (
            trace["lc14_full_write_attempt"]["qualified"] == 0
        ),
        "simultaneous_write_output_counted_once_each": (
            trace["lc14_write_and_out"]["qualified"] == 2
        ),
        "lc15_capture_output_counted_once_each": (
            trace["lc15_capture_and_out"]["qualified"] == 2
        ),
        "exact_owner_clock_reset": (
            "posedge u_NDP_Top_new.clk_db" in block
            and "negedge u_NDP_Top_new.rst_n_db" in block
        ),
        "exact_predicates_present": all(
            token in block
            for token in (
                "lx_13_port[22] &&",
                "iga_lc_same_gotten_mask",
                "iga_lc_inbuffer_bp_pre",
                "iga_lc_outbuf_wr_en",
                "iga_lc_outbuf_full",
                "lx_14_port[22] &&",
                "lx_15_port[22] &&",
            )
        ),
    }
    required_counts = {
        token: block.count(token)
        for token in (
            "lx_13_port[22] &&",
            "iga_lc_same_gotten_mask",
            "iga_lc_inbuffer_bp_pre",
            "iga_lc_outbuf_full",
        )
    }

    def accepts(candidate: str) -> bool:
        return all(
            candidate.count(token) == count
            for token, count in required_counts.items()
        )

    negatives = {
        "drop_lc13_ready_fail_closed": not accepts(
            block.replace("lx_13_port[22] &&", "", 1)
        ),
        "drop_same_mask_fail_closed": not accepts(
            block.replace("iga_lc_same_gotten_mask", "", 1)
        ),
        "drop_lc14_ready_fail_closed": not accepts(
            block.replace("iga_lc_inbuffer_bp_pre", "", 1)
        ),
        "drop_counter_full_fail_closed": not accepts(
            block.replace("iga_lc_outbuf_full", "", 1)
        ),
    }
    checks["negative_controls"] = all(negatives.values())
    report = {
        "schema": "node0004-v51-lc13-lc14-predicate-trace-v1",
        "valid": all(checks.values()),
        "errors": [name for name, value in checks.items() if not value],
        "checks": checks,
        "trace": trace,
        "negative_controls": negatives,
        "observer": {
            "bytes": len(payload),
            "sha256": digest(payload),
            "span_sha256": digest(block.encode()),
        },
        "claim_boundary": (
            "Metadata-only event trace for the exact v51 predicates; "
            "no DUT execution and no terminal/formal-D claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
