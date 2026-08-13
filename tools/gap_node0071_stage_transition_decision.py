#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


MARKER = "GEXEC_STAGE_TRANSITION_STATE_V1"


def fields(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in line.split("|")[-1].strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result


def classify(item: dict[str, str]) -> dict[str, Any]:
    selected = int(item["mask"], 0)
    ready = int(item["ready"], 0)
    valid = int(item["valid"], 0)
    exec_level = int(item["exec_level"], 0)
    finish_level = int(item["finish_level"], 0)
    opcode = int(item["opcode"], 0)
    local_empty = int(item["local_empty"], 0)
    blocked = selected & ~ready
    selected_valid = selected & valid
    selected_not_empty = selected & ~local_empty
    compute_active_blocked = blocked & exec_level
    noncompute_blocked = blocked & ~exec_level

    if blocked and compute_active_blocked == blocked:
        decision = "SELECTED_SLICE_COMPUTE_UNFINISHED"
        boundary = "selected_slice_ready"
    elif blocked:
        decision = "SELECTED_SLICE_NONCOMPUTE_READY_LOW"
        boundary = "selected_slice_ready"
    elif selected_valid or selected_not_empty:
        decision = "LOCAL_QUEUE_CONSUMER_PENDING"
        boundary = "local_queue_empty_and_slice_ready"
    elif opcode == 0 and int(item["gconfig_ready"], 0) == 0:
        decision = "GLOBAL_CONFIG_READY_BLOCK"
        boundary = "gconfig2gexec_ready"
    elif int(item["mask_match"], 0) == 0:
        decision = "GLOBAL_MASK_MATCH_PENDING_OTHER_FACTOR"
        boundary = "mask_match"
    else:
        decision = "GLOBAL_DISPATCH_READY_OR_ADVANCED"
        boundary = "global_queue_rd_en"

    return {
        "schema": "gap-node0071-stage-transition-decision-v1",
        "decision": decision,
        "boundary": boundary,
        "stage": item.get("stage", "UNKNOWN"),
        "time_ps": int(item["time_ps"], 0),
        "global_edge": int(item["edge"], 0),
        "opcode": opcode,
        "selected_mask": f"0x{selected:07x}",
        "ready_mask": f"0x{ready:07x}",
        "valid_mask": f"0x{valid:07x}",
        "local_empty_mask": f"0x{local_empty:07x}",
        "blocked_ready_mask": f"0x{blocked:07x}",
        "compute_active_blocked_mask": f"0x{compute_active_blocked:07x}",
        "noncompute_blocked_mask": f"0x{noncompute_blocked:07x}",
        "finish_level_mask": f"0x{finish_level:07x}",
        "mask_match": bool(int(item["mask_match"], 0)),
        "config_match": bool(int(item["config_match"], 0)),
        "gconfig_ready": bool(int(item["gconfig_ready"], 0)),
        "global_queue_empty": bool(int(item["global_empty"], 0)),
        "global_queue_rd_en": bool(int(item["global_rd"], 0)),
        "qualified_progress": False,
        "stable_level_counts_as_progress": False,
        "claim_boundary": (
            "Read-only global-owner-clock stage-transition localization. "
            "It does not prove numeric correctness, natural terminal, or formal D."
        ),
    }


def analyze(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    states = [line for line in lines if MARKER in line]
    if not states:
        return {
            "schema": "gap-node0071-stage-transition-decision-v1",
            "decision": "FEATURE_EVIDENCE_MISSING",
            "boundary": "observer_binding",
            "qualified_progress": False,
            "stable_level_counts_as_progress": False,
        }
    item = fields(states[-1])
    item["time_ps"] = states[-1].split("|", 1)[0].strip()
    return classify(item)


def self_test() -> dict[str, Any]:
    base = {
        "time_ps": "100",
        "edge": "10",
        "stage": "POST_SUM_S1",
        "opcode": "0x6",
        "mask": "0xffff",
        "ready": "0xffff",
        "valid": "0x0",
        "exec_level": "0x0",
        "finish_level": "0x0",
        "global_empty": "0",
        "local_empty": "0xfffffff",
        "mask_match": "1",
        "config_match": "1",
        "gconfig_ready": "1",
        "global_rd": "1",
    }
    cases = []

    def check(name: str, changes: dict[str, str], expected: str) -> None:
        item = {**base, **changes}
        observed = classify(item)["decision"]
        cases.append(
            {
                "name": name,
                "expected": expected,
                "observed": observed,
                "pass": observed == expected,
            }
        )

    check(
        "one_selected_slice_compute_active",
        {"ready": "0xfffd", "exec_level": "0x2"},
        "SELECTED_SLICE_COMPUTE_UNFINISHED",
    )
    check(
        "one_selected_slice_ready_low_noncompute",
        {"ready": "0xfffb", "exec_level": "0x0"},
        "SELECTED_SLICE_NONCOMPUTE_READY_LOW",
    )
    check(
        "local_queue_pending",
        {"valid": "0x8", "local_empty": "0xffffff7"},
        "LOCAL_QUEUE_CONSUMER_PENDING",
    )
    check(
        "load_config_wait",
        {"opcode": "0x0", "gconfig_ready": "0", "mask_match": "0"},
        "GLOBAL_CONFIG_READY_BLOCK",
    )
    check(
        "other_mask_factor",
        {"mask_match": "0"},
        "GLOBAL_MASK_MATCH_PENDING_OTHER_FACTOR",
    )
    check(
        "dispatch_advanced",
        {},
        "GLOBAL_DISPATCH_READY_OR_ADVANCED",
    )
    stable_a = classify(base)
    stable_b = classify(base)
    stable_ok = (
        stable_a["decision"] == stable_b["decision"]
        and stable_a["qualified_progress"] is False
        and stable_b["qualified_progress"] is False
    )
    cases.append(
        {
            "name": "stable_level_not_progress",
            "expected": True,
            "observed": stable_ok,
            "pass": stable_ok,
        }
    )
    return {
        "schema": "gap-node0071-stage-transition-predicate-trace-v1",
        "cases": cases,
        "pass": all(case["pass"] for case in cases),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--observer-log", type=Path, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    self_parser = sub.add_parser("self-test")
    self_parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = (
        analyze(args.observer_log)
        if args.command == "analyze"
        else self_test()
    )
    if getattr(args, "output", None):
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(result, sort_keys=True))
    if args.command == "self-test":
        return 0 if result["pass"] else 1
    return 0 if result["decision"] != "FEATURE_EVIDENCE_MISSING" else 2


if __name__ == "__main__":
    raise SystemExit(main())
