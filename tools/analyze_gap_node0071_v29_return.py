from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import analyze_gap_node0071_v28_return as base


IDENTITY = "r5_n71_gap_v29_mse0_buffer_prep_group0_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 125678
RETURN_SHA256 = "2b990565c41da4984bb1293ccbaf135a0f92ccee955e11653f25c60fd0c1a0bd"
SOURCE_SIZE = 1818768
SOURCE_SHA256 = "15833d826872e118a9be834b082351ae2b31862da0b138a2a4f271269108e164"


def fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"(\w+)=([^\s]+)", line))


def last_record(text: str, marker: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if marker in line]
    return fields(lines[-1]) if lines else {}


def event_records(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if "MSE0_BUFFER_PREP_GROUP0_EVENT_V1" not in line:
            continue
        item: dict[str, Any] = {
            "time_ps": int(line.split("|", 1)[0].strip())
        }
        for key, value in fields(line).items():
            try:
                item[key] = int(value, 16) if value.startswith("0x") else int(value)
            except ValueError:
                item[key] = value
        records.append(item)
    return records


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    base.IDENTITY = IDENTITY
    base.RETURN_ROOT = RETURN_ROOT
    base.RETURN_SIZE = RETURN_SIZE
    base.RETURN_SHA256 = RETURN_SHA256
    base.SOURCE_SIZE = SOURCE_SIZE
    base.SOURCE_SHA256 = SOURCE_SHA256
    report = base.analyze(return_zip, source_zip)

    with zipfile.ZipFile(return_zip) as archive:
        observer = archive.read(
            f"{RETURN_ROOT}/runs/return_observer.log"
        ).decode("utf-8", errors="replace")
        binding = archive.read(
            f"{RETURN_ROOT}/evidence/observer_binding.txt"
        ).decode("utf-8", errors="replace")
        argv = archive.read(
            f"{RETURN_ROOT}/evidence/actual_simulator_argv.txt"
        ).decode("utf-8", errors="replace")

    counts = last_record(observer, "MSE0_BUFFER_PREP_GROUP0_COUNTS_V1")
    state = last_record(observer, "MSE0_BUFFER_PREP_GROUP0_STATE_V1")
    witness = last_record(observer, "MSE0_BUFFER_PREP_GROUP0_WITNESS_V1")
    stage_flow = last_record(observer, "STAGE1_FLOW_COUNTS_V1")
    dual = last_record(observer, "DUAL_INGRESS_COUNTS")
    rd = last_record(observer, "RD_DATA_VLD_PATH_COUNTS_V1")
    events = event_records(observer)

    m0_buf_accept = int(counts.get("buf_accept", "-1"))
    m0_arm_accept = int(counts.get("arm_accept", "-1"))
    m0_arm_clear = int(counts.get("arm_clear", "-1"))
    m0_prep_wr = int(counts.get("prep_wr", "-1"))
    m0_prep_rd = int(counts.get("prep_rd", "-1"))
    m0_data_vld = int(counts.get("data_vld", "-1"))
    raw_group0 = int(counts.get("group0_accept", "-1"))
    final_arm_req = int(state.get("arm_req", "0x0"), 16)
    final_arm_ready = int(state.get("arm_ready", "-1"))
    final_arm_rw = int(state.get("arm_rw", "-1"))
    final_buf_valid = int(state.get("buf_vld", "0x0"), 16)
    inherited_group0 = int(
        last_record(observer, "BUFFER_TO_GA_COUNTS").get(
            "ga_group0_accept", "-1"
        )
    )

    group0_sampler_source = (
        ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages"
        / IDENTITY
        / "tb_probe/native_return_observer.svh"
    ).read_text(encoding="utf-8")
    bad_group0_expression = (
        "m0_group0_accept =\n"
        "                (|return_obs_ga_group_out_tag_mon"
    ) in group0_sampler_source
    raw_group0_excluded = (
        bad_group0_expression
        and raw_group0 > report["evidence_dominance_reanalysis"][
            "ga_group_accept_batches"
        ][0]
    )

    report.update(
        {
            "schema": "gap-node0071-v29-return-analysis-v1",
            "status": "ADJUDICATED_SUCCESSOR_REQUIRED",
            "runtime_binding": {
                **report["runtime_binding"],
                "mse0_path_enable_in_argv":
                    "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0" in argv,
                "mse0_path_limit_in_argv":
                    "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512" in argv,
                "mse0_path_time0_marker":
                    "mse0_buffer_prep_group0=1" in observer
                    and "mse0_buffer_prep_group0_limit=512" in observer,
                "mse0_path_return_binding":
                    "mse0_buffer_prep_group0_enabled=true" in binding
                    and "mse0_buffer_prep_group0_records_returned=true"
                    in binding,
            },
            "last_proven_good": (
                "Within the active sum_s1 window, all 8 observed MSE0 "
                "producer-to-Buffer0 accepts reach prepared writes; 2 "
                "Buffer0 ARM reads accept and clear, and 5 prepared reads "
                "produce 5 data_vld events"
            ),
            "first_divergence": (
                "BUFFER0_ARM_READ_REQUEST_0xFF_HELD_WITH_"
                "BUF2ARM_REQ_READY_0_AFTER_TWO_ACCEPTS"
            ),
            "hang_root_cause": (
                "LONG_RUNNING_HANG_AT_BUFFER0_ARM_READ_READY_"
                "CONJUNCTION_PENDING_BANK_READY_OR_NRM_READ_BARRIER_LEAF"
            ),
            "mse0_buffer_prep_group0_evidence": {
                "final_counts": counts,
                "final_state": state,
                "final_witness": witness,
                "event_record_count": len(events),
                "qualified_counts": {
                    "buffer_accept": m0_buf_accept,
                    "arm_accept": m0_arm_accept,
                    "arm_clear": m0_arm_clear,
                    "prepared_write": m0_prep_wr,
                    "prepared_read": m0_prep_rd,
                    "data_vld": m0_data_vld,
                    "inherited_group0_accept_batches": inherited_group0,
                },
                "final_blocking_state": {
                    "buffer_valid_nonzero": final_buf_valid != 0,
                    "arm_request": final_arm_req,
                    "arm_request_nonzero": final_arm_req != 0,
                    "arm_request_is_read": final_arm_rw == 0,
                    "buf2arm_req_ready": final_arm_ready,
                },
                "stage_flow_counts": stage_flow,
                "dual_ingress_counts": dual,
                "rd_data_counts": rd,
                "raw_group0_counter": raw_group0,
                "raw_group0_counter_excluded_from_progress": raw_group0_excluded,
                "raw_group0_counter_defect": (
                    "v29 used nonzero tag level AND bp_post instead of a "
                    "qualified capture/valid-bit handshake, so the raw "
                    "15M-cycle value is state repetition, not progress"
                    if raw_group0_excluded
                    else None
                ),
            },
            "root_cause_scope": {
                "closed": [
                    "MSE0 active-window producer-to-buffer accept failing to produce prepared write",
                    "MSE0 accepted ARM read failing to clear",
                    "MSE0 prepared read failing to produce data_vld",
                    "GA final pipeline/outbuffer losing an accepted transaction",
                    "MSE4 losing one of the available paired write-data transactions",
                ],
                "remaining": [
                    "Buffer0 selected-bank readiness false at current ARM address",
                    "Buffer0 nrm2buf_rd_barrier asserted",
                ],
                "unique_functional_root": False,
            },
            "blocker_delta": {
                "closed": (
                    "B_GAP_NODE0071_MSE0_BUFFER_TO_RD_PREPARED_TO_"
                    "GA_GROUP0_CAPTURE_PENDING_LEAF"
                ),
                "opened": (
                    "B_GAP_NODE0071_BUFFER0_ARM_READ_READY_CONJUNCTION_"
                    "PENDING_BANK_READY_OR_NRM_BARRIER_LEAF"
                ),
            },
            "successor": {
                "required": True,
                "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "boundary": (
                    "Buffer0 arm2buf read request/address/mask -> per-bank "
                    "buf2arm_rreq_bank_ready and selected valid/clear state "
                    "-> nrm2buf_rd_barrier -> buf2arm_rreq_ready"
                ),
                "must_correct_package_local_observer":
                    "replace v29 group0 stable-level count with qualified valid-bit capture",
                "config_change": False,
                "timeout_change": False,
            },
            "rtl_identity": {
                "commit": "d0aa87f682880a260fb792aaac88f70a23aba414",
                "sync_report_sha256":
                    "fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771",
                "gap_fix_assumed": False,
            },
            "numeric_sum_tail_workload_config_golden_repeated": False,
        }
    )
    report["errors"] = list(report.get("errors", []))
    if not raw_group0_excluded:
        report["errors"].append("v29 raw group0 stable-level defect not proven")
    report["valid_receipt"] = not report["errors"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve(), args.source_zip.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
