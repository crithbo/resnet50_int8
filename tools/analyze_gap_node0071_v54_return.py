#!/usr/bin/env python3
"""Formal GAP node0071 v54 remote-owner false-accept return analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

import analyze_gap_node0071_v51_return as base


ROOT = Path(__file__).resolve().parents[1]
INSTALL = "r5_n71_gap_v54_remote_owner_false_accept_diag"
RETURN_PATH = Path(
    r"C:\Users\15383\Downloads"
    r"\r5_n71_gap_v54_remote_owner_false_accept_diag_"
    r"r1786189099790677414_4093690_return.zip"
)
RETURN_SHA = "5bbe79edd2a8cfcec03b63207920f8c73166dd78fd57066e30360230c9ba9e5b"
SOURCE_PATH = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{INSTALL}.zip"
)
SOURCE_SHA = "131e9de37698c8e0470db0c42120c0b2d793c84ce0c2ee62a02eb24cefbd87c9"
EXECUTION = "r1786189099790677414_4093690"
ATTEMPT = "a4093690"
RTL_PATH = ROOT / "NDP_copy01/rtl/Slice/slice2hub_crossbar.sv"

PROGRESS_FIELDS = (
    "m4_req_hs0", "m4_req_hs1", "m4_w_hs0", "m4_w_hs1",
    "g_req_wr0", "g_req_wr1", "g_w_wr0", "g_w_wr1", "finish",
)
VIOLATION_FIELDS = (
    "remote_collision", "req_owner_mismatch0", "req_owner_mismatch1",
    "w_owner_mismatch0", "w_owner_mismatch1", "req_no_fifo_write0",
    "req_no_fifo_write1", "w_no_fifo_write0", "w_no_fifo_write1",
)
FACTOR_FIELDS = (
    *(f"remote{i}" for i in range(5)), *(f"owner{i}" for i in range(5)),
    *(f"mse{i}_{kind}{ch}" for i in range(5)
      for kind in ("req_v", "req_r", "w_v", "w_r") for ch in range(2)),
    *(f"g_{kind}{ch}" for kind in ("req_v", "req_r", "w_v", "w_r")
      for ch in range(2)),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def parse_exact_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line in text.splitlines():
        if "REMOTE_OWNER_FALSE_ACCEPT_V1" not in line:
            continue
        fields = dict(re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line))
        if fields:
            records.append(fields)
    return records


def sticky_replay(records: list[dict[str, str]]) -> dict[str, object]:
    def aggregate(names: tuple[str, ...]) -> dict[str, str]:
        result: dict[str, str] = {}
        for name in names:
            value = 0
            for row in records:
                if name in row and row[name].startswith("0x"):
                    value |= int(row[name], 16)
            result[name] = f"0x{value:04x}"
        return result

    counts = {
        event: sum(row.get("event") == event for row in records)
        for event in ("QUALIFIED_EDGE", "VIOLATION_EDGE", "FACTOR_EDGE", "HEARTBEAT")
    }
    return {
        "schema": "gap-node0071-v54-sticky-semantic-replay-v1",
        "record_count": len(records),
        "record_counts": counts,
        "progress_masks_from_exact_records": aggregate(PROGRESS_FIELDS),
        "violation_sticky_masks_from_exact_records": aggregate(VIOLATION_FIELDS),
        "factor_sticky_masks_from_exact_records": aggregate(FACTOR_FIELDS),
        "semantics": {
            "qualified_progress": "only QUALIFIED_EDGE changes count as progress",
            "violation_evidence": "owner-clock sticky violation state may be consumed from any exact reporter record",
            "stable_level_or_heartbeat_counts_as_progress": False,
        },
    }


def analyze(output: Path) -> dict[str, object]:
    base.INSTALL = INSTALL
    base.RETURN_ROOT = f"{INSTALL}_return"
    base.RETURN_PATH = RETURN_PATH
    base.RETURN_SHA = RETURN_SHA
    base.RETURN_BYTES = 188181
    base.SOURCE_PATH = SOURCE_PATH
    base.SOURCE_SHA = SOURCE_SHA
    base.EXECUTION = EXECUTION
    base.ATTEMPT = ATTEMPT
    report = base.analyze(output)

    with tempfile.TemporaryDirectory(prefix="gap-v54-return-") as tmp_name:
        tmp = Path(tmp_name)
        with zipfile.ZipFile(RETURN_PATH) as archive:
            archive.extractall(tmp / "return")
        with zipfile.ZipFile(SOURCE_PATH) as archive:
            archive.extractall(tmp / "source")
        returned = tmp / "return" / f"{INSTALL}_return"
        source = tmp / "source" / INSTALL
        observer_log = returned / "runs/return_observer.log"
        parser = source / "package_tools/gap_node0071_remote_owner_false_accept_decision.py"
        observer_source = source / "tb_probe/native_return_observer.svh"
        returned_decision = json.loads(
            (returned / "evidence/remote_owner_false_accept_decision.json")
            .read_text(encoding="utf-8")
        )
        replay_path = output / "formal_replay/remote_owner_false_accept_exact.json"
        replay = base.run_parser(
            [sys.executable, str(parser), "analyze", "--observer-log",
             str(observer_log), "--output", str(replay_path)], replay_path,
        )
        exact_replay_equal = replay.get("output") == returned_decision
        records = parse_exact_records(observer_log.read_text(encoding="utf-8", errors="replace"))
        sticky = sticky_replay(records)
        sticky_path = output / "formal_replay/remote_owner_false_accept_sticky_semantic_replay.json"
        write(sticky_path, sticky)

        progress = sticky["progress_masks_from_exact_records"]
        violation = sticky["violation_sticky_masks_from_exact_records"]
        factor = sticky["factor_sticky_masks_from_exact_records"]
        expected_fffe = (
            "remote_collision", "req_owner_mismatch0", "req_owner_mismatch1",
            "w_owner_mismatch0", "w_owner_mismatch1",
            "w_no_fifo_write0", "w_no_fifo_write1",
        )
        evidence_valid = all((
            replay["exit_code"] == 0,
            exact_replay_equal,
            returned_decision["feature_enabled_marker"] is True,
            sticky["record_counts"] == returned_decision["record_counts"],
            progress["m4_w_hs0"] == "0xffff",
            progress["m4_w_hs1"] == "0xffff",
            progress["g_req_wr0"] == "0xfffe",
            progress["g_req_wr1"] == "0xfffe",
            progress["g_w_wr0"] == "0x0000",
            progress["g_w_wr1"] == "0x0000",
            factor["remote0"] == factor["remote3"] == factor["remote4"] == "0xfffe",
            factor["owner0"] == "0xfffe",
            all(factor[f"owner{i}"] == "0x0000" for i in range(1, 5)),
            all(violation[name] == "0xfffe" for name in expected_fffe),
            violation["req_no_fifo_write0"] == "0x0000",
            violation["req_no_fifo_write1"] == "0x0000",
        ))
        observer_text = observer_source.read_text(encoding="utf-8", errors="replace")
        event_loss_source_proven = all(token in observer_text for token in (
            'pc?"QUALIFIED_EDGE":vc?"VIOLATION_EDGE":fc?"FACTOR_EDGE":"HEARTBEAT"',
            "return_obs_v54_prev_progress=ps;return_obs_v54_prev_violation=vs;",
        ))
        parser_event_loss = (
            returned_decision["record_counts"]["VIOLATION_EDGE"] == 0
            and all(returned_decision["violation_masks"][name] == "0x0000"
                    for name in expected_fffe)
            and all(violation[name] == "0xfffe" for name in expected_fffe)
            and event_loss_source_proven
        )
        observer_source_sha = sha(observer_source)
        parser_sha = sha(parser)
        if not evidence_valid:
            report["return_analysis"]["errors"].append(
                "v54 remote-owner sticky evidence did not satisfy exact expected masks"
            )

    rtl_text = RTL_PATH.read_text(encoding="utf-8", errors="replace")
    rtl_equations_present = all(token in rtl_text for token in (
        "slice_global_wdata_fifo_in_valid[chl_idx] = slice_remote_req_flag[0]",
        "hub2mse_wdata_ready[MSE_IDX][CHL_IDX]  = slice_remote_req_flag[MSE_IDX] ? slice_global_wdata_fifo_in_ready[CHL_IDX]",
    ))
    if not rtl_equations_present:
        report["return_analysis"]["errors"].append("bound RTL equations absent")

    report.update({
        "schema": "gap-node0071-v54-repeatable-return-analysis-v1",
        "status": "WAIT_RTL_FIX_REMOTE_WDATA_OWNER_FALSE_ACCEPT_PROVEN",
        "formal_decision_collection": {
            **report["formal_decision_collection"],
            "remote_owner_exact_parser_exit": replay["exit_code"],
            "remote_owner_returned_equals_exact_replay": exact_replay_equal,
            "family_local_parser_consumed_as_frozen_run_receipt": True,
            "shared_logger_parser_rule_not_retroactively_applied": True,
        },
        "runtime_binding": {
            **report["runtime_binding"],
            "actual_compiled_production_identity": "NOT_DYN_RECOVERED_BY_V54_RETURN",
        },
        "qualified_progress": {
            **report["qualified_progress"],
            "remote_owner_progress_masks": progress,
            "remote_owner_factor_masks": factor,
            "remote_owner_violation_sticky_masks": violation,
            "record_counts": sticky["record_counts"],
            "stable_level_factor_violation_or_heartbeat_counts_as_progress": False,
        },
        "observer_parser_adjudication": {
            "package_local_event_priority_loss_proven": parser_event_loss,
            "exact_parser_reported_violation_masks_zero": returned_decision["violation_masks"],
            "raw_exact_records_preserve_owner_clock_sticky_violation_state": violation,
            "claim_boundary": "sticky violation state is functional evidence; it is not counted as monotonic progress",
            "observer_member_sha256": observer_source_sha,
            "parser_member_sha256": parser_sha,
            "semantic_replay_path": str(sticky_path.resolve()),
            "semantic_replay_sha256": sha(sticky_path),
        },
        "last_proven_good": {
            "boundary": "SLICES1_15_MSE4_REMOTE_REQUEST_GLOBAL_FIFO_WRITE_ACCEPTED",
            "qualified_masks": {
                "m4_req_hs0": progress["m4_req_hs0"],
                "m4_req_hs1": progress["m4_req_hs1"],
                "g_req_wr0": progress["g_req_wr0"],
                "g_req_wr1": progress["g_req_wr1"],
            },
        },
        "first_divergence": {
            "boundary": "MSE4_WDATA_FALSE_ACCEPT_WHILE_PRIORITY_OWNER_MSE0_AND_GLOBAL_WDATA_FIFO_WRITE_ABSENT_SLICES1_15",
            "mse4_wdata_handshake": [progress["m4_w_hs0"], progress["m4_w_hs1"]],
            "global_wdata_fifo_write": [progress["g_w_wr0"], progress["g_w_wr1"]],
            "remote_flags": {name: factor[name] for name in ("remote0", "remote3", "remote4")},
            "priority_owner": {f"owner{i}": factor[f"owner{i}"] for i in range(5)},
            "false_accept_sticky": {name: violation[name] for name in (
                "w_owner_mismatch0", "w_owner_mismatch1",
                "w_no_fifo_write0", "w_no_fifo_write1",
            )},
        },
        "hang_root_cause": {
            "classification": "FUNCTIONAL_RTL_SLICE2HUB_REMOTE_WDATA_READY_NOT_QUALIFIED_BY_PRIORITY_OWNER",
            "unique_functional_leaf_closed": True,
            "rtl_path": str(RTL_PATH.resolve()),
            "rtl_sha256": sha(RTL_PATH),
            "request_and_wdata_mux_priority_lines": [167, 184, 193, 210],
            "independent_per_mse_ready_lines": [252, 253],
            "equation": "owner=first asserted remote flag (MSE0); global wdata valid selects owner, but hub2mse_wdata_ready[MSE4] is asserted from FIFO ready solely because remote4=1",
            "resnet_effect": "MSE4 accepts write data that was not selected into the global FIFO; slices1-15 cannot complete and no natural terminal/readback follows",
            "config_fix_authorized": False,
            "config_boundary": "serializing MSE0/MSE3 reads versus MSE4 writes would alter the proven pre-divergence schedule and has no one-leaf equivalence proof",
            "minimum_rtl_fix_proposal_only": "qualify per-MSE remote req/wdata ready with the same selected owner used by the mux, separately per channel; verify non-owner ready=0 and owner valid&&ready implies exactly one FIFO write",
        },
        "formal_d": report["formal_d"],
        "e3_e4_e5": {
            "E3": False, "E4": False, "E5": False,
            "reason": "compile passed, but INT/125/130 is not natural completion; 0/48 formal D are present and numeric result is unevaluable",
        },
        "blocker_delta": {
            "closed": [
                "B_GAP_NODE0071_REMOTE_WDATA_SHARED_PRIORITY_OWNER_CONJUNCTION_PENDING",
                "remote-owner candidate ambiguity for slices1-15",
            ],
            "opened": "B_GAP_NODE0071_SLICE2HUB_REMOTE_WDATA_OWNER_FALSE_ACCEPT_RTL_FIX",
        },
        "rule_confirmation": [
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            "CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001",
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        ],
        "rule_delta_proposal": {
            "id": "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
            "proposal": "When multiple diagnostic state classes change in one reporter sample, an event-priority arbiter must not acknowledge/update a lower-priority previous-state snapshot unless that class is emitted; alternatively, the exact parser must consume monotonic sticky class state from every exact record while keeping non-progress classes out of progress accounting.",
            "evidence": "v54 pc won over vc, prev_violation was still updated, VIOLATION_EDGE count stayed zero, while all exact later records retained 0xfffe sticky violation masks.",
        },
        "successor_required": False,
        "termination": "WAIT_RTL_FIX",
        "successor_proposal_or_none": "NONE_UNTIL_FUNCTIONAL_RTL_FIX",
        "package_release": "NONE",
        "numeric_sum_tail_workload_config_golden_repeated": False,
        "files_modified_by_analysis": [
            str((output / "report.json").resolve()),
            str(sticky_path.resolve()),
        ],
    })
    write(output / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.output.resolve())
    report_path = args.output.resolve() / "report.json"
    print(json.dumps({
        "output": str(report_path),
        "sha256": sha(report_path),
        "errors": report["return_analysis"]["errors"],
        "status": report["status"],
        "last_proven_good": report["last_proven_good"]["boundary"],
        "first_divergence": report["first_divergence"]["boundary"],
    }))
    return 0 if not report["return_analysis"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
