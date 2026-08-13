from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


VERSION = 44


def accepted(valid: int, ready: int) -> int:
    return int(bool(valid) and bool(ready))


def evaluate(event: dict[str, int]) -> dict[str, int]:
    result = {
        "lc9_advance": accepted(event["lc9_valid"], event["lc9_all_ready"]),
        "pe1_in2_accept": accepted(
            event["lc9_valid"], event["pe1_in2_ready"]
        ),
        "pe1_match": int(bool(event["pe1_match"])),
        "pe1_out_accept": accepted(
            event["pe1_out_valid"], event["pe1_out_ready"]
        ),
        "mem1_accept": accepted(event["mem1_valid"], event["mem1_ready"]),
        "row4_accept": accepted(event["row4_valid"], event["row4_ready"]),
        "row4_out_accept": accepted(
            event["row4_out_valid"], event["row4_out_ready"]
        ),
        "buf_source_push": accepted(
            event["buf_source_wr_en"], int(not event["buf_source_full"])
        ),
    }
    result["qualified_progress"] = sum(result.values())
    result["lc9_last0"] = int(
        result["lc9_advance"]
        and event["lc9_last"]
        and event["lc9_last_index"] == 0
    )
    result["pe1_last0"] = int(
        result["pe1_out_accept"]
        and event["pe1_last"]
        and event["pe1_last_index"] == 0
    )
    result["mem1_last0"] = int(
        result["mem1_accept"]
        and event["mem1_last"]
        and event["mem1_last_index"] == 0
    )
    result["row4_last0"] = int(
        result["row4_out_accept"]
        and event["row4_last"]
        and event["row4_last_index"] == 0
    )
    return result


BASE: dict[str, int] = {
    "lc9_valid": 0,
    "lc9_all_ready": 0,
    "pe1_in2_ready": 0,
    "pe1_match": 0,
    "pe1_out_valid": 0,
    "pe1_out_ready": 0,
    "mem1_valid": 0,
    "mem1_ready": 0,
    "row4_valid": 0,
    "row4_ready": 0,
    "row4_out_valid": 0,
    "row4_out_ready": 0,
    "buf_source_wr_en": 0,
    "buf_source_full": 0,
    "lc9_last": 0,
    "lc9_last_index": 5,
    "pe1_last": 0,
    "pe1_last_index": 5,
    "mem1_last": 0,
    "mem1_last_index": 5,
    "row4_last": 0,
    "row4_last_index": 5,
}


def case(**updates: int) -> dict[str, int]:
    return evaluate({**BASE, **updates})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    cases: dict[str, dict[str, int]] = {
        "valid_without_ready": case(lc9_valid=1),
        "ready_without_valid": case(lc9_all_ready=1),
        "lc9_handshake": case(lc9_valid=1, lc9_all_ready=1),
        "simultaneous_branches": case(
            lc9_valid=1,
            lc9_all_ready=1,
            pe1_in2_ready=1,
            row4_valid=1,
            row4_ready=1,
        ),
        "pe1_output_to_memory": case(
            pe1_out_valid=1,
            pe1_out_ready=1,
            mem1_valid=1,
            mem1_ready=1,
        ),
        "buffer_full_blocks_push": case(
            buf_source_wr_en=1, buf_source_full=1
        ),
        "buffer_push": case(buf_source_wr_en=1, buf_source_full=0),
        "local_last5_not_global": case(
            lc9_valid=1,
            lc9_all_ready=1,
            lc9_last=1,
            lc9_last_index=5,
        ),
        "global_last0": case(
            lc9_valid=1,
            lc9_all_ready=1,
            lc9_last=1,
            lc9_last_index=0,
        ),
    }
    stable_level = [
        case(lc9_valid=1, lc9_all_ready=0),
        case(lc9_valid=1, lc9_all_ready=0),
        case(lc9_valid=1, lc9_all_ready=0),
    ]
    reset_trace = [
        {"reset_n": 0, "qualified_progress": 0},
        {"reset_n": 1, "active": 0, "qualified_progress": 0},
        {"reset_n": 1, "active": 1, **case(lc9_valid=1, lc9_all_ready=1)},
    ]
    boundary_trace = {
        "first": case(lc9_valid=1, lc9_all_ready=1),
        "penultimate": case(
            pe1_out_valid=1, pe1_out_ready=1, mem1_valid=1, mem1_ready=1
        ),
        "final_local_last5": case(
            lc9_valid=1,
            lc9_all_ready=1,
            lc9_last=1,
            lc9_last_index=5,
        ),
        "one_after": case(lc9_valid=1, pe1_in2_ready=1),
    }
    candidate_matrix: dict[str, dict[str, int]] = {
        "SHARED_LC9_PE1_BLOCKED": {
            "lc9_valid": 1,
            "pe1_in2_ready": 0,
            "row4_ready": 1,
        },
        "SHARED_LC9_ROW4_BLOCKED": {
            "lc9_valid": 1,
            "pe1_in2_ready": 1,
            "row4_ready": 0,
        },
        "PE1_INTERNAL_MATCH_BLOCKED": {
            "pe1_in2_accept": 1,
            "pe1_match": 0,
            "pe1_out_accept": 0,
        },
        "MEMORY_PORT1_BLOCKED": {
            "pe1_out_accept": 1,
            "mem1_accept": 0,
        },
        "BUFFER_ROW_PIPELINE_BLOCKED": {
            "row4_accept": 1,
            "row4_out_accept": 0,
            "buf_source_push": 0,
        },
        "GLOBAL_LAST0_LOST": {
            "lc9_last0": 1,
            "pe1_last0": 0,
            "mem1_last0": 0,
            "row4_last0": 0,
        },
    }
    signatures = {
        name: tuple(sorted(values.items()))
        for name, values in candidate_matrix.items()
    }
    checks = {
        "conjunct_valid_without_ready_zero": (
            cases["valid_without_ready"]["qualified_progress"] == 0
        ),
        "conjunct_ready_without_valid_zero": (
            cases["ready_without_valid"]["qualified_progress"] == 0
        ),
        "qualified_handshake_counts": (
            cases["lc9_handshake"]["lc9_advance"] == 1
        ),
        "simultaneous_events_all_preserved": (
            cases["simultaneous_branches"]["lc9_advance"] == 1
            and cases["simultaneous_branches"]["pe1_in2_accept"] == 1
            and cases["simultaneous_branches"]["row4_accept"] == 1
        ),
        "stable_level_not_progress": all(
            item["qualified_progress"] == 0 for item in stable_level
        ),
        "full_blocks_buffer_push": (
            cases["buffer_full_blocks_push"]["buf_source_push"] == 0
        ),
        "local_last5_not_global": (
            cases["local_last5_not_global"]["lc9_last0"] == 0
        ),
        "global_last0_exact": cases["global_last0"]["lc9_last0"] == 1,
        "reset_stage_ownership": (
            reset_trace[0]["qualified_progress"] == 0
            and reset_trace[1]["qualified_progress"] == 0
            and reset_trace[2]["qualified_progress"] > 0
        ),
        "first_penultimate_final_one_after_present": (
            set(boundary_trace) == {"first", "penultimate", "final_local_last5", "one_after"}
        ),
        "candidate_signatures_unique": (
            len(set(signatures.values())) == len(signatures)
        ),
    }
    report: dict[str, Any] = {
        "schema": f"node0004-v{VERSION}-lc9-split-predicate-trace-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "clock_owner": "u_NDP_Top_new.clk_db",
        "reset_owner": "u_NDP_Top_new.rst_n_db",
        "active_owner": "return_obs_active",
        "progress_definition": "qualified valid-and-ready handshake only",
        "cases": cases,
        "stable_level_trace": stable_level,
        "reset_stage_trace": reset_trace,
        "boundary_trace": boundary_trace,
        "candidate_observation_matrix": candidate_matrix,
        "claim_boundary": "metadata event trace only; no DUT or numeric execution",
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
