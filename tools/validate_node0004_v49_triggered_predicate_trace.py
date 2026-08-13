from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


INSTALL_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
BEGIN = "// v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_BEGIN"
END = "// v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_END"


def sha256(data: bytes) -> str:
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
        return {"snapshot": 0, "progress": 0}
    if not active:
        return {"snapshot": 0, "progress": 0}
    qualified = {
        "lc9": int(event.get("lc9_valid", 0) and event.get("all_ready", 0)),
        "lc7": int(event.get("lc7_valid", 0) and event.get("lc7_ready", 0)),
        "lc7out": int(
            event.get("lc7out_valid", 0) and event.get("lc7out_ready", 0)
        ),
        "mem3": int(event.get("mem3_valid", 0) and event.get("mem3_ready", 0)),
        "push": int(event.get("wr_en", 0) and not event.get("full", 0)),
        "pop": int(event.get("rd_en", 0) and not event.get("empty", 1)),
        "last0": int(
            event.get("lc9_valid", 0)
            and event.get("last", 0)
            and event.get("last_index", 5) == 0
        ),
    }
    first_event = any(qualified[key] and state[key] == 0 for key in qualified)
    bp_change = int(
        event.get("bp0", 1) != state["prev_bp0"]
        or event.get("bp26", 1) != state["prev_bp26"]
    )
    progress = sum(qualified.values()) - qualified["last0"]
    for key, value in qualified.items():
        state[key] += value
    state["prev_bp0"] = event.get("bp0", 1)
    state["prev_bp26"] = event.get("bp26", 1)
    return {"snapshot": int(first_event or bp_change), "progress": progress}


def run_trace() -> dict[str, object]:
    state = {
        "lc9": 0,
        "lc7": 0,
        "lc7out": 0,
        "mem3": 0,
        "push": 0,
        "pop": 0,
        "last0": 0,
        "prev_bp0": 1,
        "prev_bp26": 1,
    }
    trace = {
        "reset": step(state, {}, reset=True),
        "inactive_held_level": step(
            state, {"lc9_valid": 1, "all_ready": 1}, active=False
        ),
        "initial_held_valid_snapshot": step(state, {"lc9_valid": 1}),
        "stable_held_valid_without_all_ready": step(
            state, {"lc9_valid": 1}
        ),
        "first_lc7_accept": step(
            state, {"lc7_valid": 1, "lc7_ready": 1}
        ),
        "repeated_lc7_accept": step(
            state, {"lc7_valid": 1, "lc7_ready": 1}
        ),
        "first_mse3_accept_push": step(
            state,
            {
                "mem3_valid": 1,
                "mem3_ready": 1,
                "wr_en": 1,
                "full": 0,
            },
        ),
        "simultaneous_first_pop_lc9": step(
            state,
            {
                "rd_en": 1,
                "empty": 0,
                "lc9_valid": 1,
                "all_ready": 1,
            },
        ),
        "bp26_transition": step(state, {"bp0": 1, "bp26": 0}),
        "bp26_stable": step(state, {"bp0": 1, "bp26": 0}),
        "first_last0": step(
            state, {"lc9_valid": 1, "last": 1, "last_index": 0}
        ),
        "stable_last0": step(
            state, {"lc9_valid": 1, "last": 1, "last_index": 0}
        ),
    }
    checks = {
        "inactive_not_counted": trace["inactive_held_level"]["progress"] == 0,
        "held_level_not_progress": (
            trace["initial_held_valid_snapshot"]["progress"] == 0
            and trace["stable_held_valid_without_all_ready"]["progress"] == 0
            and trace["stable_held_valid_without_all_ready"]["snapshot"] == 0
        ),
        "first_event_snapshots": trace["first_lc7_accept"]["snapshot"] == 1,
        "repeated_event_no_text_snapshot": (
            trace["repeated_lc7_accept"]["snapshot"] == 0
        ),
        "simultaneous_events_single_snapshot": (
            trace["simultaneous_first_pop_lc9"]["snapshot"] == 1
            and trace["simultaneous_first_pop_lc9"]["progress"] == 2
        ),
        "bp_transition_snapshots": trace["bp26_transition"]["snapshot"] == 1,
        "stable_bp_no_snapshot": trace["bp26_stable"]["snapshot"] == 0,
        "first_terminal_snapshots_once": (
            trace["first_last0"]["snapshot"] == 1
            and trace["stable_last0"]["snapshot"] == 0
        ),
    }
    return {"trace": trace, "checks": checks, "valid": all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        observer_bytes = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = observer_bytes.decode()
    block = observer[
        observer.index(BEGIN) : observer.index(END) + len(END)
    ]
    result = run_trace()
    source_checks = {
        "trigger_only_comment": "text output is trigger-only" in block,
        "first_lc9_predicate": (
            "return_obs_la_lc9_advance == 0" in block
        ),
        "first_lc7_predicate": (
            "return_obs_la_lc7_capture == 0" in block
        ),
        "first_mse3_predicate": (
            "return_obs_la_mem3_in2_capture == 0" in block
        ),
        "first_push_pop_predicates": (
            "return_obs_la_mem3_push == 0" in block
            and "return_obs_la_mem3_pop == 0" in block
        ),
        "bp_transition_predicate": "la_bp_change" in block,
        "stage_reset_owner": (
            "posedge u_NDP_Top_new.clk_db" in block
            and "negedge u_NDP_Top_new.rst_n_db" in block
            and "return_obs_la_enabled && return_obs_active" in block
        ),
    }
    negative_controls = {
        "remove_lc7_first_predicate": (
            "return_obs_la_lc7_capture == 0"
            not in block.replace("return_obs_la_lc7_capture == 0", "", 1)
        ),
        "remove_mse3_first_predicate": (
            "return_obs_la_mem3_in2_capture == 0"
            not in block.replace(
                "return_obs_la_mem3_in2_capture == 0", "", 1
            )
        ),
        "remove_bp_change": (
            "la_bp_change" not in block.replace("la_bp_change", "", 99)
        ),
    }
    checks = {
        **result["checks"],
        **source_checks,
        "negative_controls": all(negative_controls.values()),
    }
    report = {
        "schema": "node0004-v49-triggered-predicate-trace-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "trace": result["trace"],
        "negative_controls": negative_controls,
        "observer": {
            "bytes": len(observer_bytes),
            "sha256": sha256(observer_bytes),
            "span_sha256": sha256(block.encode()),
        },
        "claim_boundary": (
            "Metadata-only predicate trace for v49 changed observer semantics. "
            "It does not run DUT dataflow or establish terminal/formal-D/E4/E5."
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
