from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v24_signal_stub as base


ROOT_NAME = "r5_n71_gap_v28_ga_mse4_final_pair_diag"
ZIP_SHA256 = (
    "7b34ef0b592ebfd86d3e75a0983a91c8d87271454139e609174cdce8afc7d422"
)


def write_mock_tools(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=False)
    bin_dir, _ = base.base.base.common.mock_tools(root)
    sim_started = root / "safe_sim_stub_started.txt"
    make_wrapper = bin_dir / "make"
    make_wrapper.write_text(
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "run_dir=''\n"
        "for argument in \"$@\"; do\n"
        "  case \"$argument\" in RUN_DIR=*) run_dir=\"${argument#RUN_DIR=}\";; esac\n"
        "done\n"
        "[ -n \"$run_dir\" ] || exit 84\n"
        "simv=\"$run_dir/sim_results/simv\"\n"
        "cat >\"$simv\" <<'SAFE_SIM_STUB'\n"
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "sim_log=''\n"
        "observer_log=''\n"
        "rd_path=false\n"
        "rd_limit=false\n"
        "pc_cause=false\n"
        "pc_limit=false\n"
        "pair_feature=false\n"
        "pair_limit=false\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -l) shift; sim_log=\"$1\";;\n"
        "    +RETURN_OBS_FILE=*) observer_log=\"${1#*=}\";;\n"
        "    +RETURN_OBS_RD_DATA_PATH) rd_path=true;;\n"
        "    +RETURN_OBS_RD_DATA_PATH_LIMIT=512) rd_limit=true;;\n"
        "    +RETURN_OBS_PREP_COUNT_CAUSE) pc_cause=true;;\n"
        "    +RETURN_OBS_PREP_COUNT_CAUSE_LIMIT=512) pc_limit=true;;\n"
        "    +RETURN_OBS_GA_MSE4_FINAL_PAIR) pair_feature=true;;\n"
        "    +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512) pair_limit=true;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "[ -n \"$sim_log\" ] || exit 82\n"
        "[ -n \"$observer_log\" ] || exit 83\n"
        "[ \"$rd_path\" = true ] || exit 80\n"
        "[ \"$rd_limit\" = true ] || exit 81\n"
        "[ \"$pc_cause\" = true ] || exit 78\n"
        "[ \"$pc_limit\" = true ] || exit 79\n"
        "[ \"$pair_feature\" = true ] || exit 76\n"
        "[ \"$pair_limit\" = true ] || exit 77\n"
        "printf '%s\\n' '[RETURN_OBSERVER] enabled for slice 0' >\"$sim_log\"\n"
        "printf '%s\\n' \\\n"
        "  'Native NDP return observer accum_state=1 accum_limit=512 bp_factor=1 bp_factor_limit=512 rd_data_path=1 rd_data_path_limit=512 prep_count_cause=1 prep_count_cause_limit=512 ga_mse4_final_pair=1 ga_mse4_final_pair_limit=512' \\\n"
        "  '0 | BP_PRE_FACTOR_COUNTS_V1 | flow=MSE0 q_rd=0 ob_wr=0 occupancy=0' \\\n"
        "  '0 | BP_PRE_FACTOR_STATE_V1 | flow=MSE0 factors=0' \\\n"
        "  '0 | BP_PRE_FACTOR_WITNESS_V1 | flow=MSE0 first=0 last=0' \\\n"
        "  '0 | RD_DATA_VLD_PATH_COUNTS_V1 | event=SAFE_STUB req_hs=0/0 rdata_hs=0,0/0,0 ib_wr=0,0/0,0 ib_rd=0,0/0,0 prep_wr=0/0 prep_rd=0/0 records=0 limit=512' \\\n"
        "  '0 | RD_DATA_VLD_PATH_STATE_V1 | event=SAFE_STUB req_vld=0x0 req_ready=0x0 q_wr=0x0 q_rd=0x0 q_full=0x0 q_empty=0x0 mem_vld=0x0 mem_ready=0x0 ib_vld=0x0 ib_sel=0x0 prep_count=0x0 queue_tsf=0x0 spatial=0x0 prep_wr=0x0 prep_rd=0x0 data_vld=0x0' \\\n"
        "  '0 | RD_DATA_VLD_PATH_WITNESS_V1 | event=SAFE_STUB mse0_no_rdata=0:0 mse3_no_rdata=0:0 mse0_no_prep=0:0 mse3_no_prep=0:0 seen_rdata=0x0 seen_prep=0x0' \\\n"
        "  '0 | PREP_COUNT_CAUSE_COUNTS_V1 | event=SAFE_STUB wr=0/0 rd=0/0 count_change=0/0 slice_rst_edge=0/0 rst_n_edge=0/0 no_effect=0/0 records=0 limit=512' \\\n"
        "  '0 | PREP_COUNT_CAUSE_STATE_V1 | event=SAFE_STUB rst_n=0x3 slice_rst=0x0 wr=0x0 rd=0x0 count=0x0 tsf=0x0 spatial=0x0 lt_req=0x0 bp_pre=0x0 ob_bp_pre=0x0 data_vld=0x0' \\\n"
        "  '0 | PREP_COUNT_CAUSE_WITNESS_V1 | event=SAFE_STUB mse0_no_effect=0:0 mse3_no_effect=0:0 mse0_local_reset=0:0 mse3_local_reset=0:0 seen_no_effect=0x0 seen_local_reset=0x0' \\\n"
        "  '0 | GA_MSE4_FINAL_PAIR_COUNTS_V1 | event=SAFE_STUB ga_accept=0 ga_p0_retire=0 ga_wr_req=0 ga_wr_hs=0 ga_rd_hs=0 m4_req_accept=0 m4_q_wr=0 m4_q_rd=0 m4_buf_accept=0 m4_prep_wr=0 m4_prep_rd=0 m4_ob_wr=0/0 m4_ob_rd=0/0 records=0 limit=512' \\\n"
        "  '0 | GA_MSE4_FINAL_PAIR_STATE_V1 | event=SAFE_STUB ga_p0_valid=0x0 ga_p0_bp=0x0 ga_result_tag=0x0 ga_ob_full=0x0 ga_ob_count=0x0 m4_req_vld=0 m4_req_ready=0 m4_q_full=0 m4_q_empty=1 m4_buf_vld=0 m4_buf_ready=1 m4_buf_last=0 m4_hold=0 m4_prep_vld=0 m4_prep_count=0 m4_ob_vld=0x0 m4_ob_vld_o=0x0 m4_mem_ready=0x0 m4_last=0x0 finish=0' \\\n"
        "  '0 | GA_MSE4_FINAL_PAIR_WITNESS_V1 | event=SAFE_STUB last_ga_accept=0 last_ga_retire=0 last_ga_wr=0 last_m4_req=0 last_m4_buf=0 last_m4_ob_wr=0 last_m4_ob_rd=0' \\\n"
        "  >\"$observer_log\"\n"
        "printf 'SAFE_SIM_STUB_STARTED\\n' >\"$MOCK_SIM_STARTED\"\n"
        "trap 'exit 143' TERM INT\n"
        "while :; do sleep 1; done\n"
        "SAFE_SIM_STUB\n"
        "chmod +x \"$simv\"\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    make_wrapper.chmod(0o755)
    return bin_dir, sim_started


original_validate_return = base.base.base.validate_return


def validate_return(package: Path, mock_server: Path) -> dict[str, Any]:
    result = original_validate_return(package, mock_server)
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    files, _ = base.base.base.read_return_zip(return_zip)
    binding = files["evidence/observer_binding.txt"].decode("utf-8")
    argv = files["evidence/actual_simulator_argv.txt"].decode("utf-8")
    result["ga_mse4_final_pair_binding"] = {
        "enabled": "ga_mse4_final_pair_enabled=true" in binding,
        "limit_512": "ga_mse4_final_pair_limit=512" in binding,
        "records_returned":
            "ga_mse4_final_pair_records_returned=true" in binding,
        "actual_argv_enable": "+RETURN_OBS_GA_MSE4_FINAL_PAIR" in argv,
        "actual_argv_limit":
            "+RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512" in argv,
    }
    if not all(result["ga_mse4_final_pair_binding"].values()):
        raise base.base.base.RevalidationError(
            "GA/MSE4-final-pair signal-finalizer binding differs"
        )
    return result


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    base.ROOT_NAME = ROOT_NAME
    base.ZIP_SHA256 = ZIP_SHA256
    base.base.ROOT_NAME = ROOT_NAME
    base.base.ZIP_SHA256 = ZIP_SHA256
    base.base.base.ROOT_NAME = ROOT_NAME
    base.base.base.ZIP_SHA256 = ZIP_SHA256
    base.base.base.write_mock_tools = write_mock_tools
    base.base.base.validate_return = validate_return
    result = base.base.base.validate(target_zip, bash)
    result["schema"] = (
        "gap-node0071-v28-ga-mse4-final-pair-safe-signal-stub-"
        "revalidation-v1"
    )
    result["diagnostic_feature"] = "GA_MSE4_FINAL_PAIR"
    result["current_rule_scope"] = {
        "exit_and_signal_share_finalize": True,
        "signal_path_dynamically_exercised": "TERM",
        "stderr_shell_diagnostic_absent":
            result["runner"]["runner_stderr"] == "",
        "declared_partial_return_complete": result["return"][
            "critical_partial_artifacts_complete"
        ],
        "nonnatural_not_misreported": (
            result["return"]["canonical_natural_terminal"] is False
            and result["return"]["result_gate_natural_completion"] is False
        ),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.bash.resolve())
    except Exception as error:
        result = {
            "schema": (
                "gap-node0071-v28-ga-mse4-final-pair-safe-signal-stub-"
                "revalidation-v1"
            ),
            "status": "FAIL",
            "error": str(error),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
