from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_col_ag_mrm_lane_v31 as base


base.ROOT_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
base.TEST_ID = "r5-gap-node0071-v33-buffer-ag-index-pairing-diagnostic"
RUNNER = "PREPARE_AND_RUN.sh"
OBSERVER = "tb_probe/native_return_observer.svh"
RECORDS = [
    "BUFFER_AG_IDX_QUEUE_EVENT_V1",
    "BUFFER_AG_IDX_QUEUE_COUNTS_V1",
    "BUFFER_AG_IDX_QUEUE_STATE_V1",
    "BUFFER_AG_IDX_QUEUE_WITNESS_V1",
]
ORIGINAL_VALIDATE = base.validate_payload
ORIGINAL_NEGATIVES = base.negative_controls


def validate_payload(
    files: dict[str, bytes], root_name: str, runner_report: dict[str, Any] | None
) -> dict[str, Any]:
    result = ORIGINAL_VALIDATE(files, root_name, runner_report)
    errors = list(result["errors"])
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    runner = files[RUNNER].decode("utf-8")
    observer = files[OBSERVER].decode("utf-8")
    contract = manifest.get("buffer_ag_index_pair_diagnostic_contract", {})
    checks = {
        "test_id": manifest.get("test_id") == base.TEST_ID,
        "runtime_enable":
            contract.get("runtime_enable") == "+RETURN_OBS_BUFFER_AG_IDX_QUEUE",
        "runtime_limit":
            contract.get("runtime_limit")
            == "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256",
        "stable_excluded": contract.get("stable_level_counts_as_progress") is False,
        "read_only":
            contract.get("read_only") is True and contract.get("drives_dut") is False,
        "runner_enable":
            "\n  +RETURN_OBS_BUFFER_AG_IDX_QUEUE\n" in runner
            and " +RETURN_OBS_BUFFER_AG_IDX_QUEUE " in runner,
        "runner_limit":
            "\n  +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256\n" in runner
            and " +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256 " in runner,
        "runner_receipt":
            "buffer_ag_idx_queue_enabled=true" in runner
            and "buffer_ag_idx_queue_records_returned=true" in runner,
        "observer_enable": "RETURN_OBS_BUFFER_AG_IDX_QUEUE" in observer,
        "observer_limit": "RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=%d" in observer,
        "time0":
            "buffer_ag_idx_queue=%0d buffer_ag_idx_queue_limit=%0d" in observer,
        "records": all(token in observer for token in RECORDS),
        "qualified_updates": all(
            token in observer
            for token in (
                "return_obs_bq_col_accept_count++;",
                "return_obs_bq_row_accept_count++;",
                "return_obs_bq_enqueue_count++;",
                "return_obs_bq_dequeue_count++;",
                "return_obs_bq_wr_en_mon",
                "!return_obs_bq_full_mon",
                "return_obs_bq_rd_en_mon",
                "!return_obs_bq_empty_mon",
            )
        ),
        "factor_leaves": all(
            token in observer
            for token in (
                ".buf_idx_valid_bit_unmasked;",
                ".buf_idx_same_bit_unmasked;",
                ".buf_idx_gotten_bit;",
                ".buf_idx_same_bit_keep_mask;",
                ".buf_idx_same_bit_masked;",
                ".buf_idx_same_gotten_mask;",
                ".buf_idx_valid_bit_masked;",
                ".buf_idx_bp_pre_keep_mask;",
                ".buf_idx_bp_pre_mask;",
                ".buf_all_idx_matched;",
                ".u_buf_ag_idx_queue.fifo_counter;",
            )
        ),
        "not_canonical_progress":
            "BUFFER_AG_IDX_QUEUE_" not in files[
                "package_tools/gap_node0071_canonical_decision.py"
            ].decode("utf-8"),
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(f"v33 Buffer-AG index queue contract differs: {name}")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "buffer_ag_idx_queue_checks": checks,
            "buffer_ag_idx_queue_contract_valid": all(checks.values()),
        }
    )
    return result


def negative_controls(
    files: dict[str, bytes], root_name: str, runner_report: dict[str, Any] | None
) -> list[dict[str, Any]]:
    controls = ORIGINAL_NEGATIVES(files, root_name, runner_report)

    def check(name: str, mutated: dict[str, bytes], changed: str, expected: str) -> None:
        mutated = base.base.base.base.refresh(mutated, changed)
        result = validate_payload(mutated, root_name, runner_report)
        controls.append(
            {
                "name": name,
                "failed_closed": not result["valid"],
                "expected_error_observed": any(
                    expected in error for error in result["errors"]
                ),
                "errors": result["errors"],
            }
        )

    mutated = dict(files)
    mutated[RUNNER] = files[RUNNER].replace(
        b"  +RETURN_OBS_BUFFER_AG_IDX_QUEUE\n", b"", 1
    ).replace(b"+RETURN_OBS_BUFFER_AG_IDX_QUEUE ", b"", 1)
    check("bq_runtime_enable_removed", mutated, RUNNER, "runner_enable")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"buffer_ag_idx_queue=%0d buffer_ag_idx_queue_limit=%0d",
        b"bq_time0_removed",
        1,
    )
    check("bq_time0_removed", mutated, OBSERVER, "time0")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b"return_obs_bq_enqueue_count++;",
        b"return_obs_bq_enqueue_update_removed++;",
        1,
    )
    check("bq_critical_update_removed", mutated, OBSERVER, "qualified_updates")

    mutated = dict(files)
    mutated[OBSERVER] = files[OBSERVER].replace(
        b".buf_idx_same_gotten_mask;",
        b".buf_idx_same_gotten_typo;",
        1,
    )
    check("bq_factor_leaf_misspelled", mutated, OBSERVER, "factor_leaves")
    return controls


base.validate_payload = validate_payload
base.negative_controls = negative_controls

if __name__ == "__main__":
    raise SystemExit(base.main())
