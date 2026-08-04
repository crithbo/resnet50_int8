from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v20_signal_stub as base


ROOT_NAME = "r5_n71_gap_v23_rd_data_vld_path_rulefix"
ZIP_SHA256 = (
    "07ea69a9b647542751c3e47b192d5d1ddb497dad97801e75c9fe002331244c19"
)


def write_mock_tools(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=False)
    bin_dir, _ = base.common.mock_tools(root)
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
        "rd_data_path=false\n"
        "rd_data_limit=false\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -l) shift; sim_log=\"$1\";;\n"
        "    +RETURN_OBS_FILE=*) observer_log=\"${1#*=}\";;\n"
        "    +RETURN_OBS_RD_DATA_PATH) rd_data_path=true;;\n"
        "    +RETURN_OBS_RD_DATA_PATH_LIMIT=512) rd_data_limit=true;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "[ -n \"$sim_log\" ] || exit 82\n"
        "[ -n \"$observer_log\" ] || exit 83\n"
        "[ \"$rd_data_path\" = true ] || exit 80\n"
        "[ \"$rd_data_limit\" = true ] || exit 81\n"
        "printf '%s\\n' '[RETURN_OBSERVER] enabled for slice 0' >\"$sim_log\"\n"
        "printf '%s\\n' \\\n"
        "  'Native NDP return observer accum_state=1 accum_limit=512 bp_factor=1 bp_factor_limit=512 rd_data_path=1 rd_data_path_limit=512' \\\n"
        "  '0 | BP_PRE_FACTOR_COUNTS_V1 | flow=MSE0 q_rd=0 ob_wr=0 occupancy=0' \\\n"
        "  '0 | BP_PRE_FACTOR_STATE_V1 | flow=MSE0 factors=0' \\\n"
        "  '0 | BP_PRE_FACTOR_WITNESS_V1 | flow=MSE0 first=0 last=0' \\\n"
        "  '0 | RD_DATA_VLD_PATH_COUNTS_V1 | event=SAFE_STUB req_hs=0/0 rdata_hs=0,0/0,0 ib_wr=0,0/0,0 ib_rd=0,0/0,0 prep_wr=0/0 prep_rd=0/0 records=0 limit=512' \\\n"
        "  '0 | RD_DATA_VLD_PATH_STATE_V1 | event=SAFE_STUB req_vld=0x0 req_ready=0x0 q_wr=0x0 q_rd=0x0 q_full=0x0 q_empty=0x0 mem_vld=0x0 mem_ready=0x0 ib_vld=0x0 ib_sel=0x0 prep_count=0x0 queue_tsf=0x0 spatial=0x0 prep_wr=0x0 prep_rd=0x0 data_vld=0x0' \\\n"
        "  '0 | RD_DATA_VLD_PATH_WITNESS_V1 | event=SAFE_STUB mse0_no_rdata=0:0 mse3_no_rdata=0:0 mse0_no_prep=0:0 mse3_no_prep=0:0 seen_rdata=0x0 seen_prep=0x0' \\\n"
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


original_validate_return = base.validate_return


def validate_return(package: Path, mock_server: Path) -> dict[str, Any]:
    result = original_validate_return(package, mock_server)
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    files, _ = base.read_return_zip(return_zip)
    binding = files["evidence/observer_binding.txt"].decode("utf-8")
    argv = files["evidence/actual_simulator_argv.txt"].decode("utf-8")
    result["rd_data_vld_path_binding"] = {
        "enabled": "rd_data_vld_path_enabled=true" in binding,
        "limit_512": "rd_data_vld_path_limit=512" in binding,
        "records_returned": "rd_data_vld_path_records_returned=true" in binding,
        "actual_argv_enable": "+RETURN_OBS_RD_DATA_PATH" in argv,
        "actual_argv_limit": "+RETURN_OBS_RD_DATA_PATH_LIMIT=512" in argv,
    }
    if not all(result["rd_data_vld_path_binding"].values()):
        raise base.RevalidationError(
            "rd-data-vld-path signal-finalizer binding differs"
        )
    return result


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    base.ROOT_NAME = ROOT_NAME
    base.ZIP_SHA256 = ZIP_SHA256
    base.write_mock_tools = write_mock_tools
    base.validate_return = validate_return
    result = base.validate(target_zip, bash)
    result["schema"] = (
        "gap-node0071-v23-rd-data-vld-path-safe-signal-stub-"
        "revalidation-v1"
    )
    result["diagnostic_feature"] = "RD_DATA_VLD_PATH"
    result["current_rule_scope"] = {
        "exit_and_signal_share_finalize": True,
        "signal_path_dynamically_exercised": "TERM",
        "stderr_shell_diagnostic_absent": (
            result["runner"]["runner_stderr"] == ""
        ),
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
                "gap-node0071-v23-rd-data-vld-path-safe-signal-stub-"
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
