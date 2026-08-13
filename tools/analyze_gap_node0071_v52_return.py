#!/usr/bin/env python3
"""Formal GAP node0071 v52 return analysis layered on the v51 receipt audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import analyze_gap_node0071_v51_return as base


ROOT = Path(__file__).resolve().parents[1]
INSTALL = "r5_n71_gap_v52_ga_read_mse4_direct_diag"
RETURN_PATH = Path(r"C:\Users\15383\Downloads\r5_n71_gap_v52_ga_read_mse4_direct_diag_r1786164375511644113_3976438_return.zip")
RETURN_SHA = "8cc238e12154f0ef8a671ea7be4c2df60b68d42c27a2c10d62517dd864ae987d"
SOURCE_PATH = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{INSTALL}.zip"
SOURCE_SHA = "1dfa3f28687f2725ea22579a05871b0353d2302914062225ecd13ac5784938ef"
EXECUTION = "r1786164375511644113_3976438"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def analyze(output: Path) -> dict[str, object]:
    base.INSTALL = INSTALL
    base.RETURN_ROOT = f"{INSTALL}_return"
    base.RETURN_PATH = RETURN_PATH
    base.RETURN_SHA = RETURN_SHA
    base.RETURN_BYTES = 175161
    base.SOURCE_PATH = SOURCE_PATH
    base.SOURCE_SHA = SOURCE_SHA
    base.EXECUTION = EXECUTION
    base.ATTEMPT = "a3976438"
    report = base.analyze(output)

    with tempfile.TemporaryDirectory(prefix="gap-v52-return-extra-") as tmp_name:
        tmp = Path(tmp_name)
        with zipfile.ZipFile(RETURN_PATH) as archive:
            archive.extractall(tmp / "return")
        with zipfile.ZipFile(SOURCE_PATH) as archive:
            archive.extractall(tmp / "source")
        returned = tmp / "return" / f"{INSTALL}_return"
        source = tmp / "source" / INSTALL
        observer = returned / "runs/return_observer.log"
        parser = source / "package_tools/gap_node0071_ga_read_mse4_direct_decision.py"
        replay_path = output / "formal_replay/ga_read_mse4_direct.json"
        replay = base.run_parser([
            sys.executable, str(parser), "analyze", "--observer-log", str(observer), "--output", str(replay_path)
        ], replay_path)
        returned_decision = json.loads((returned / "evidence/ga_read_mse4_direct_decision.json").read_text(encoding="utf-8"))
        decision_equal = replay.get("output") == returned_decision
        masks = returned_decision["qualified_masks"]
        full_through_ob_read = all(masks[name] == "0xffff" for name in (
            "mode_normal", "selected_wr", "nonempty", "selected_rd", "m4_idx", "m4_req",
            "m4_q_wr", "m4_q_rd", "m4_buf", "m4_prep_wr", "m4_prep_rd", "m4_ob_wr", "m4_ob_rd",
        ))
        only_slice0_after_ob_read = all(masks[name] == "0x0001" for name in (
            "m4_local_req", "m4_local_wdata", "finish",
        ))
        observer_text = observer.read_text(encoding="utf-8", errors="replace")
        records = [line for line in observer_text.splitlines() if "GA_READ_MSE4_DIRECT_V1" in line]
        qualified_records = [line for line in records if "event=QUALIFIED_EDGE" in line]
        heartbeat_records = [line for line in records if "event=HEARTBEAT" in line]
        marker = "# ga_read_mse4_direct=1" in observer_text
        qualified_count = returned_decision["qualified_record_count"]
        coverage_unexhausted = qualified_count < 320 and len(qualified_records) == qualified_count
        evidence_valid = all((
            replay["exit_code"] == 0, decision_equal, marker, full_through_ob_read,
            only_slice0_after_ob_read, returned_decision["stable_level_is_progress"] is False,
            not heartbeat_records, coverage_unexhausted,
        ))
        if not evidence_valid:
            report["return_analysis"]["errors"].append("v52 direct-chain evidence invalid")

    report.update({
        "schema": "gap-node0071-v52-repeatable-return-analysis-v1",
        "status": "PARTIAL_INTERRUPTED_DIAGNOSTIC_LOCAL_REQUEST_BOUNDARY_IDENTIFIED",
        "runtime_binding": {
            **report["runtime_binding"],
            "actual_compiled_production_identity": "NOT_DYN_RECOVERED_BY_V52_RETURN",
        },
        "formal_decision_collection": {
            **report["formal_decision_collection"],
            "ga_read_mse4_direct_replay_exit": replay["exit_code"],
            "ga_read_mse4_direct_returned_equals_replay": decision_equal,
        },
        "local_exact_parser_replay": {**report["local_exact_parser_replay"], "direct": replay},
        "qualified_progress": {
            **report["qualified_progress"],
            "ga_read_mse4_direct_masks": masks,
            "qualified_record_count": qualified_count,
            "qualified_limit": 320,
            "coverage_unexhausted": coverage_unexhausted,
            "heartbeat_record_count": len(heartbeat_records),
            "state_or_heartbeat_counts_as_progress": False,
            "full_chain_through_mse4_output_buffer_read_all_slices": full_through_ob_read,
            "local_request_write_data_finish_slice0_only": only_slice0_after_ob_read,
        },
        "last_proven_good": {
            "boundary": "ALL_16_SLICES_MSE4_OUTPUT_BUFFER_READ_ACCEPTED",
            "qualified_masks": {name: masks[name] for name in (
                "mode_normal", "selected_wr", "nonempty", "selected_rd", "m4_idx", "m4_req",
                "m4_q_wr", "m4_q_rd", "m4_buf", "m4_prep_wr", "m4_prep_rd", "m4_ob_wr", "m4_ob_rd",
            )},
        },
        "first_divergence": {
            "boundary": "MSE4_OUTPUT_BUFFER_READ_TO_LOCAL_REQUEST_ACCEPTANCE_SLICES1_15",
            "last_good_mask": masks["m4_ob_rd"],
            "first_bad_mask": masks["m4_local_req"],
            "local_wdata_mask": masks["m4_local_wdata"],
            "finish_mask": masks["finish"],
            "qualified_coverage_evaluable": coverage_unexhausted,
            "functional_interpretation": "slices1-15 reach MSE4 output-buffer read but do not produce an accepted local request; slice0 completes the same chain",
        },
        "hang_root_cause": {
            "classification": "LONG_RUNNING_HANG_AT_MSE4_OUTPUT_BUFFER_READ_TO_LOCAL_REQUEST_ACCEPTANCE_PENDING_FACTOR",
            "unique_functional_leaf_closed": False,
            "observer_budget_issue_closed": True,
            "remaining_candidates": [
                "local request valid is not asserted after MSE4 output-buffer read on slices1-15",
                "local request valid is asserted but local request ready/arbitration blocks slices1-15",
                "channel/select ownership maps only slice0 into the accepted local request",
                "local request acceptance occurs outside the reused reduction surface and needs direct factor confirmation",
            ],
        },
        "blocker_delta": {
            "closed": [
                "v51 direct-consumer evidence budget saturation",
                "all 16 slices reach MSE4 index/request/queue/buffer/prepared/output-buffer write and read",
                "slice0 reaches local request, local write-data and finish",
            ],
            "remaining": "B_GAP_NODE0071_MSE4_OB_READ_TO_LOCAL_REQUEST_ACCEPTANCE_SLICES1_15_PENDING_FACTOR",
        },
        "formal_d": report["formal_d"],
        "e3_e4_e5": {
            "E3": False, "E4": False, "E5": False,
            "reason": "INT, no natural terminal, actual compiled identity not recovered, and 0/48 formal D",
        },
        "rule_confirmation": [
            "CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001",
            "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
            "CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
        ],
        "rule_delta_proposal": None,
        "successor_required": True,
        "successor_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "successor_scope": "all-slice local request/wdata valid-ready-channel-arbitration factors plus direct accepted/finish consumer",
    })
    write_json(output / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.output.resolve())
    print(json.dumps({
        "output": str((args.output / "report.json").resolve()),
        "sha256": sha(args.output / "report.json"),
        "errors": report["return_analysis"]["errors"],
        "last_proven_good": report["last_proven_good"]["boundary"],
        "first_divergence": report["first_divergence"]["boundary"],
    }, ensure_ascii=False))
    return 0 if not report["return_analysis"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
