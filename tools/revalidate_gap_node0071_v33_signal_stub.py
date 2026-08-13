import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v31_signal_stub as base


base.ROOT_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
target = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{base.ROOT_NAME}.zip"
)
if not target.is_file():
    target = (
        ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages/tested"
        / "gap_node0071"
        / base.ROOT_NAME
        / f"{base.ROOT_NAME}.zip"
    )
digest = hashlib.sha256(target.read_bytes()).hexdigest()
base.ZIP_SHA256 = base.base.ZIP_SHA256 = base.base.base.ZIP_SHA256 = digest
ORIGINAL_VALIDATE = base.validate
ORIGINAL_WRITE_MOCK_TOOLS = base.write_mock_tools
ORIGINAL_VALIDATE_RETURN = base.validate_return


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"safe stub marker differs: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def write_mock_tools(root: Path):
    bin_dir, sim_started = ORIGINAL_WRITE_MOCK_TOOLS(root)
    wrapper = bin_dir / "make"
    text = wrapper.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "lane=false\nlane_limit=false\n",
        "lane=false\nlane_limit=false\nbq=false\nbq_limit=false\n",
        "v33 variables",
    )
    text = replace_once(
        text,
        "    +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256) lane_limit=true;;\n",
        "    +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256) lane_limit=true;;\n"
        "    +RETURN_OBS_BUFFER_AG_IDX_QUEUE) bq=true;;\n"
        "    +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256) bq_limit=true;;\n",
        "v33 argv",
    )
    text = replace_once(
        text,
        '[ "$lane_limit" = true ] || exit 71\n',
        '[ "$lane_limit" = true ] || exit 71\n'
        '[ "$bq" = true ] || exit 68\n'
        '[ "$bq_limit" = true ] || exit 69\n',
        "v33 guards",
    )
    text = replace_once(
        text,
        "col_ag_mrm_lane=1 col_ag_mrm_lane_limit=256'",
        "col_ag_mrm_lane=1 col_ag_mrm_lane_limit=256 "
        "buffer_ag_idx_queue=1 buffer_ag_idx_queue_limit=256'",
        "v33 time0",
    )
    text = replace_once(
        text,
        "  '0 | COL_AG_MRM_LANE_WITNESS_V1 | event=SAFE_STUB "
        "first_col=0 last_col=0 last_bag=0 last_mse_write=0 last_mrm_write=0' \\\n"
        "  >\"$observer_log\"\n",
        "  '0 | COL_AG_MRM_LANE_WITNESS_V1 | event=SAFE_STUB "
        "first_col=0 last_col=0 last_bag=0 last_mse_write=0 last_mrm_write=0' \\\n"
        "  '0 | BUFFER_AG_IDX_QUEUE_COUNTS_V1 | event=SAFE_STUB "
        "col_accept=0 row_accept=0 enqueue=0 dequeue=0 records=0 limit=256' \\\n"
        "  '0 | BUFFER_AG_IDX_QUEUE_STATE_V1 | event=SAFE_STUB "
        "col_idx=0 col_tag=0 row_idx=0 row_tag=0 bp_pre=0 valid_raw=0 "
        "same_raw=0 gotten=0 same_keep=0 same_masked=0 same_gotten=0 "
        "valid_masked=0 bp_keep=0 bp_mask=0 all_matched=0 mse_enable=0 "
        "wr_en=0 full=0 rd_en=0 empty=1 count=0 out_valid=0 out_tag=0 out_idx=0' \\\n"
        "  '0 | BUFFER_AG_IDX_QUEUE_WITNESS_V1 | event=SAFE_STUB "
        "first_col=0 last_col=0 last_row=0 last_enqueue=0 last_dequeue=0' \\\n"
        "  >\"$observer_log\"\n",
        "v33 records",
    )
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    return bin_dir, sim_started


def validate_return(package: Path, mock_server: Path):
    result = ORIGINAL_VALIDATE_RETURN(package, mock_server)
    return_zip = mock_server / f"{base.ROOT_NAME}_return.zip"
    root = f"{base.ROOT_NAME}_return"
    with zipfile.ZipFile(return_zip) as archive:
        binding = archive.read(
            f"{root}/evidence/observer_binding.txt"
        ).decode("utf-8")
        argv = archive.read(
            f"{root}/evidence/actual_simulator_argv.txt"
        ).decode("utf-8")
    result["buffer_ag_idx_queue_binding"] = {
        "enabled": "buffer_ag_idx_queue_enabled=true" in binding,
        "limit_256": "buffer_ag_idx_queue_limit=256" in binding,
        "records_returned":
            "buffer_ag_idx_queue_records_returned=true" in binding,
        "actual_argv_enable": "+RETURN_OBS_BUFFER_AG_IDX_QUEUE" in argv,
        "actual_argv_limit":
            "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256" in argv,
    }
    if not all(result["buffer_ag_idx_queue_binding"].values()):
        raise ValueError("Buffer-AG index queue signal-finalizer binding differs")
    return result


def validate(target_zip: Path, bash: Path):
    base.write_mock_tools = write_mock_tools
    base.validate_return = validate_return
    result = ORIGINAL_VALIDATE(target_zip, bash)
    result["schema"] = "gap-node0071-v33-buffer-ag-index-safe-signal-stub-v1"
    checks = result.setdefault("checks", {})
    checks["buffer_ag_idx_queue_feature_bound"] = all(
        result["return"]["buffer_ag_idx_queue_binding"].values()
    )
    result["status"] = "PASS" if all(checks.values()) else "FAIL"
    return result


base.validate = validate

if __name__ == "__main__":
    raise SystemExit(base.main())
