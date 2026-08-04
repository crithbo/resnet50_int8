import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_col_ag_mrm_lane_v31_final_zip as base


ROOT_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
SOURCE_ROOT = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
SOURCE_SHA256 = "c974125f0b3e913f733ad4c2341b922ea3551a62144b1062c6dd433d82e369a1"
base.ROOT_NAME = ROOT_NAME
base.SOURCE_ROOT = SOURCE_ROOT
base.SOURCE_SHA256 = SOURCE_SHA256
base.RUNNER_REPORT = base.PACKAGE_DIR / f"{ROOT_NAME}.runner.json"
base.SIGNAL_REPORT = base.PACKAGE_DIR / f"{ROOT_NAME}.signal_stub.json"
base.HDL_REPORT = base.PACKAGE_DIR / f"{ROOT_NAME}.hdl_scope.json"
base.OUTPUT = base.PACKAGE_DIR / f"{ROOT_NAME}.final_zip_rule_self_audit.json"
ORIGINAL_CONFIGURE = base.configure


def configure() -> None:
    ORIGINAL_CONFIGURE()
    base.audit.EXTRA_VALIDATORS = [
        (
            "buffer_ag_idx_queue_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_buffer_ag_idx_queue_v33.py",
            [
                str(base.audit.ZIP),
                "--root-name",
                ROOT_NAME,
                "--runner-report",
                str(base.RUNNER_REPORT),
            ],
        ),
    ]


base.configure = configure

if __name__ == "__main__":
    exit_code = base.main()
    result = json.loads(base.OUTPUT.read_text(encoding="utf-8"))
    result["schema"] = "gap-node0071-v33-buffer-ag-index-final-audit-v1"
    result["source_v32"] = result.pop("source_v30")
    result["diagnostic_contract"].update(
        {
            "test_id": "r5-gap-node0071-v33-buffer-ag-index-pairing-diagnostic",
            "last_proven_good": (
                "COL-LC0 accepted lane1 value exists and all eight downstream "
                "MSE writes are preserved by Buffer0 MRM"
            ),
            "first_divergence": (
                "COL_LC0_ACCEPTED_BYTE_LANE1_VALUE_PRESENT_ONLY_BEFORE_MSE0_"
                "BUFFER_AG_ACTIVITY_AND_NO_BUFFER0_MRM_BYTE_LANE1_WRITE"
            ),
            "information_gain_scope": [
                "COL-LC0 accepted value retained from v32 observer",
                "MSE0 queue column and row direct accepted inputs",
                "raw tag/index and decoded valid/same/gotten/keep masks",
                "all-matched and MSE enable",
                "accepted enqueue versus full rejection and FIFO count",
                "accepted dequeue and direct output tag/index consumer",
            ],
            "causal_slice": {
                "checkpoint_available": False,
                "kept_exact_set": (
                    "all 73 frozen workload/numeric files and the full ordered "
                    "stage contract; sum_s1 is the first stage and reproduces "
                    "the LPG-to-FD boundary"
                ),
                "dropped_exact_set": [],
                "reason": (
                    "No legal typed hardware checkpoint exists before the "
                    "sum_s1 internal queue boundary. Later stages never start "
                    "while sum_s1 is stalled, so deleting them would not reduce "
                    "observed runtime and would weaken the formal return contract."
                ),
                "fd_precondition_changed": False,
            },
            "candidate_discrimination_matrix": {
                "source_not_presented_or_accepted":
                    "col/row direct accept counts and tag/index witnesses",
                "same_or_gotten_mask_suppression":
                    "raw valid/same, gotten, keep, same-gotten and valid-masked",
                "pairing_not_reached":
                    "valid-masked vector and all-matched",
                "mse_disabled":
                    "all-matched with mse_enable and wr_en",
                "queue_full_reject":
                    "wr_en, full, accepted enqueue and FIFO count",
                "direct_consumer_not_dequeuing":
                    "rd_en, empty, accepted dequeue and output tag/index",
            },
            "estimated_runtime_delta": (
                "no stage/runtime extension; at most 256 event records plus "
                "rate-limited heartbeat/final summaries"
            ),
        }
    )
    result["package_release"]["server_command"] = (
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
    )
    result["package_release"]["expected_return"] = [
        f"{ROOT_NAME}_return.zip"
    ]
    base.OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    raise SystemExit(exit_code)
