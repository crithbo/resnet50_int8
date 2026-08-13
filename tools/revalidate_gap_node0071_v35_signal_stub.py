from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v33_signal_stub as prior


ROOT_NAME = "r5_n71_gap_v36_dbclk_rdready_diag"
TARGET = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{ROOT_NAME}.zip"
)
if not TARGET.is_file():
    TARGET = (
        ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages/tested"
        / "gap_node0071"
        / ROOT_NAME
        / f"{ROOT_NAME}.zip"
    )
ZIP_SHA256 = hashlib.sha256(TARGET.read_bytes()).hexdigest()
PRIOR_WRITE = prior.write_mock_tools
PRIOR_VALIDATE_RETURN = prior.validate_return


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"{label}: marker count {text.count(old)}")
    return text.replace(old, new, 1)


def write_mock_tools(root: Path):
    bin_dir, sim_started = PRIOR_WRITE(root)
    wrapper = bin_dir / "make"
    text = wrapper.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "bq=false\nbq_limit=false\n",
        "bq=false\nbq_limit=false\ndbrr=false\ndbrr_limit=false\n",
        "v35 variables",
    )
    text = replace_once(
        text,
        "    +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256) bq_limit=true;;\n",
        "    +RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256) bq_limit=true;;\n"
        "    +RETURN_OBS_DBCLK_RD_READY) dbrr=true;;\n"
        "    +RETURN_OBS_DBCLK_RD_READY_LIMIT=256) dbrr_limit=true;;\n",
        "v35 argv",
    )
    text = replace_once(
        text,
        '[ "$bq_limit" = true ] || exit 69\n',
        '[ "$bq_limit" = true ] || exit 69\n'
        '[ "$dbrr" = true ] || exit 66\n'
        '[ "$dbrr_limit" = true ] || exit 67\n',
        "v35 guards",
    )
    text = replace_once(
        text,
        "buffer_ag_idx_queue=1 buffer_ag_idx_queue_limit=256'",
        "buffer_ag_idx_queue=1 buffer_ag_idx_queue_limit=256 "
        "dbclk_rd_ready=1 dbclk_rd_ready_limit=256'",
        "v35 time0",
    )
    text = replace_once(
        text,
        "  '0 | BUFFER_AG_IDX_QUEUE_WITNESS_V1 | event=SAFE_STUB "
        "first_col=0 last_col=0 last_row=0 last_enqueue=0 last_dequeue=0' \\\n"
        "  >\"$observer_log\"\n",
        "  '0 | BUFFER_AG_IDX_QUEUE_WITNESS_V1 | event=SAFE_STUB "
        "first_col=0 last_col=0 last_row=0 last_enqueue=0 last_dequeue=0' \\\n"
        "  '0 | DBCLK_RD_READY_COUNTS_V1 | event=SAFE_STUB edge=0 "
        "req=0/0 q_enq=0/0 q_deq=0/0 ib_wr=0/0 ib_rd=0/0 "
        "prep_wr=0/0 prep_rd=0/0 wr_accept=0/0 records=0 limit=256' \\\n"
        "  '0 | DBCLK_RD_READY_STATE_V1 | event=SAFE_STUB bq_wr=0 "
        "bq_full=0 bq_rd=0 bq_empty=1 bq_count=0 bq_out_valid=0 "
        "bp_pre=0 wr_ob_full=0 data_ready=0 data_vld=0 prep_count=0 "
        "rd_ob_full=0 barrier=0 req_vld=0 req_ready=0 rd_q_full=0 "
        "rd_q_empty=3 ib_vld=0 ib_sel=0' \\\n"
        "  '0 | DBCLK_RD_READY_WITNESS_V1 | event=SAFE_STUB "
        "ready_low=0:0/0:0 data_vld_low=0:0/0:0 rd_ob_full=0:0/0:0 "
        "wr_ob_full=0:0/0:0 barrier=0:0/0:0' \\\n"
        "  >\"$observer_log\"\n",
        "v35 records",
    )
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    return bin_dir, sim_started


def validate_return(package: Path, mock_server: Path):
    result = PRIOR_VALIDATE_RETURN(package, mock_server)
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    root = f"{ROOT_NAME}_return"
    with zipfile.ZipFile(return_zip) as archive:
        binding = archive.read(f"{root}/evidence/observer_binding.txt").decode()
        argv = archive.read(f"{root}/evidence/actual_simulator_argv.txt").decode()
    path_budget = json.loads(
        (
            mock_server
            / f"evidence_{ROOT_NAME}"
            / "path_budget_preflight.json"
        ).read_text(encoding="utf-8")
    )
    result["dbclk_rd_ready_binding"] = {
        "enabled": "dbclk_rd_ready_enabled=true" in binding,
        "limit_256": "dbclk_rd_ready_limit=256" in binding,
        "records_returned": "dbclk_rd_ready_records_returned=true" in binding,
        "actual_argv_enable": "+RETURN_OBS_DBCLK_RD_READY" in argv,
        "actual_argv_limit": "+RETURN_OBS_DBCLK_RD_READY_LIMIT=256" in argv,
        "path_budget_runtime_valid": path_budget.get("valid") is True,
    }
    if not all(result["dbclk_rd_ready_binding"].values()):
        raise ValueError("v35 feature/signal-finalizer binding differs")
    return result


def validate(target_zip: Path, bash: Path):
    prior.base.ROOT_NAME = ROOT_NAME
    prior.base.ZIP_SHA256 = ZIP_SHA256
    prior.base.write_mock_tools = write_mock_tools
    prior.base.validate_return = validate_return
    result = prior.ORIGINAL_VALIDATE(target_zip, bash)
    result["schema"] = "gap-node0071-v35-dbclk-rdready-safe-signal-stub-v1"
    checks = result.setdefault("checks", {})
    checks["dbclk_rd_ready_feature_bound"] = all(
        result["return"]["dbclk_rd_ready_binding"].values()
    )
    result["status"] = "PASS" if all(checks.values()) else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash", type=Path, default=Path(r"C:\Program Files\Git\bin\bash.exe")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.bash.resolve())
        exit_code = 0 if result["status"] == "PASS" else 1
    except Exception as error:
        result = {
            "schema": "gap-node0071-v35-dbclk-rdready-safe-signal-stub-v1",
            "status": "FAIL",
            "error": str(error),
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
