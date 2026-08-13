from __future__ import annotations

import argparse
import json
from pathlib import Path


def evaluate(event: dict[str, int]) -> dict[str, int]:
    result = {
        "lc9_advance": int(event["lc9_valid"] and event["all_ready"]),
        "lc7_capture": int(
            event["lc7_masked_valid"] and event["lc7_ready"]
        ),
        "lc7_out_accept": int(
            event["lc7_out_valid"] and event["lc7_out_ready"]
        ),
        "mem3_in2_capture": int(
            event["mem3_masked_valid"] and event["mem3_in2_ready"]
        ),
        "mem3_push": int(event["mem3_wr_en"] and not event["mem3_full"]),
        "mem3_pop": int(event["mem3_rd_en"] and not event["mem3_empty"]),
        "bp_change": int(
            event["bp0"] != event["prev_bp0"]
            or event["bp26"] != event["prev_bp26"]
        ),
    }
    result["lc9_last0"] = int(
        result["lc9_advance"]
        and event["lc9_last"]
        and event["lc9_last_index"] == 0
    )
    result["qualified_progress"] = sum(
        result[name]
        for name in (
            "lc9_advance",
            "lc7_capture",
            "lc7_out_accept",
            "mem3_in2_capture",
            "mem3_push",
            "mem3_pop",
        )
    )
    return result


BASE = {
    "lc9_valid": 0,
    "all_ready": 0,
    "lc7_masked_valid": 0,
    "lc7_ready": 0,
    "lc7_out_valid": 0,
    "lc7_out_ready": 0,
    "mem3_masked_valid": 0,
    "mem3_in2_ready": 0,
    "mem3_wr_en": 0,
    "mem3_full": 0,
    "mem3_rd_en": 0,
    "mem3_empty": 1,
    "bp0": 1,
    "bp26": 1,
    "prev_bp0": 1,
    "prev_bp26": 1,
    "lc9_last": 0,
    "lc9_last_index": 5,
}


def case(**updates: int) -> dict[str, int]:
    return evaluate({**BASE, **updates})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cases = {
        "held_valid_no_global_ready": case(lc9_valid=1),
        "global_advance": case(lc9_valid=1, all_ready=1),
        "lc7_masked_capture": case(lc7_masked_valid=1, lc7_ready=1),
        "mse3_masked_capture": case(
            mem3_masked_valid=1, mem3_in2_ready=1
        ),
        "push_when_not_full": case(mem3_wr_en=1, mem3_full=0),
        "push_when_full": case(mem3_wr_en=1, mem3_full=1),
        "pop_when_not_empty": case(mem3_rd_en=1, mem3_empty=0),
        "pop_when_empty": case(mem3_rd_en=1, mem3_empty=1),
        "simultaneous_push_pop": case(
            mem3_wr_en=1, mem3_full=0, mem3_rd_en=1, mem3_empty=0
        ),
        "bp0_falls": case(bp0=0),
        "bp26_falls": case(bp26=0),
        "local_last5": case(
            lc9_valid=1, all_ready=1, lc9_last=1, lc9_last_index=5
        ),
        "global_last0": case(
            lc9_valid=1, all_ready=1, lc9_last=1, lc9_last_index=0
        ),
    }
    stable = [case(lc9_valid=1) for _ in range(4)]
    candidate_matrix = {
        "LC7_INPUT_BLOCKED": {"bp0": 0, "bp26": 1, "lc7_capture": 0},
        "LC7_DOWNSTREAM_BLOCKED": {
            "bp0": 0,
            "lc7_capture": 1,
            "lc7_out_accept": 0,
        },
        "MSE3_INPUT2_MATCH_BLOCKED": {
            "bp26": 0,
            "mem3_in2_capture": 0,
            "mem3_full": 0,
        },
        "MSE3_QUEUE_FULL": {
            "bp26": 0,
            "mem3_in2_capture": 1,
            "mem3_full": 1,
            "mem3_pop": 0,
        },
        "GLOBAL_LAST0_LOST": {
            "lc9_advance": 0,
            "lc9_last0": 0,
            "bp0": 0,
            "bp26": 0,
        },
    }
    signatures = {
        name: tuple(sorted(value.items()))
        for name, value in candidate_matrix.items()
    }
    checks = {
        "held_valid_not_transaction": (
            cases["held_valid_no_global_ready"]["qualified_progress"] == 0
        ),
        "global_advance_qualified": cases["global_advance"]["lc9_advance"] == 1,
        "local_masked_captures_qualified": (
            cases["lc7_masked_capture"]["lc7_capture"] == 1
            and cases["mse3_masked_capture"]["mem3_in2_capture"] == 1
        ),
        "full_and_empty_fail_closed": (
            cases["push_when_full"]["mem3_push"] == 0
            and cases["pop_when_empty"]["mem3_pop"] == 0
        ),
        "simultaneous_push_pop_preserved": (
            cases["simultaneous_push_pop"]["mem3_push"] == 1
            and cases["simultaneous_push_pop"]["mem3_pop"] == 1
        ),
        "stable_level_not_progress": all(
            item["qualified_progress"] == 0 for item in stable
        ),
        "bp_edges_are_state_witness": (
            cases["bp0_falls"]["bp_change"] == 1
            and cases["bp0_falls"]["qualified_progress"] == 0
            and cases["bp26_falls"]["bp_change"] == 1
        ),
        "local_last5_not_global": cases["local_last5"]["lc9_last0"] == 0,
        "global_last0_exact": cases["global_last0"]["lc9_last0"] == 1,
        "candidate_signatures_unique": (
            len(set(signatures.values())) == len(signatures)
        ),
    }
    report = {
        "schema": "node0004-v48-lc9-actual-predicate-trace-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "clock_owner": "u_NDP_Top_new.clk_db",
        "reset_owner": "u_NDP_Top_new.rst_n_db",
        "active_owner": "return_obs_active",
        "cases": cases,
        "stable_level_trace": stable,
        "candidate_observation_matrix": candidate_matrix,
        "claim_boundary": "metadata event trace only; no DUT/numeric execution",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
