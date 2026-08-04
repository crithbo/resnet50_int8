from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v30_signal_stub as base


ROOT_NAME = "r5_n71_gap_v31_col_ag_mrm_lane_diag"
ZIP_SHA256 = "d37405bf47e2a572f52de47580faec3375ba387fffeb0168bad1cf42b7671650"
ORIGINAL_WRITE_MOCK_TOOLS = base.write_mock_tools
ORIGINAL_VALIDATE_RETURN = base.validate_return


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"safe stub marker differs: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def write_mock_tools(root: Path) -> tuple[Path, Path]:
    bin_dir, sim_started = ORIGINAL_WRITE_MOCK_TOOLS(root)
    wrapper = bin_dir / "make"
    text = wrapper.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "armf=false\narmf_limit=false\n",
        "armf=false\narmf_limit=false\nlane=false\nlane_limit=false\n",
        "v31 variables",
    )
    text = replace_once(
        text,
        "    +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256) armf_limit=true;;\n",
        "    +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256) armf_limit=true;;\n"
        "    +RETURN_OBS_COL_AG_MRM_LANE) lane=true;;\n"
        "    +RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256) lane_limit=true;;\n",
        "v31 argv",
    )
    text = replace_once(
        text,
        '[ "$armf_limit" = true ] || exit 73\n',
        '[ "$armf_limit" = true ] || exit 73\n'
        '[ "$lane" = true ] || exit 70\n'
        '[ "$lane_limit" = true ] || exit 71\n',
        "v31 guards",
    )
    text = replace_once(
        text,
        "buffer0_arm_ready_factors=1 buffer0_arm_ready_factors_limit=256'",
        "buffer0_arm_ready_factors=1 buffer0_arm_ready_factors_limit=256 "
        "col_ag_mrm_lane=1 col_ag_mrm_lane_limit=256'",
        "v31 time0",
    )
    text = replace_once(
        text,
        "  '0 | BUFFER0_ARM_READY_FACTOR_WITNESS_V1 | event=SAFE_STUB "
        "first_block=0 last_factor_edge=0 last_accept=0' \\\n"
        "  >\"$observer_log\"\n",
        "  '0 | BUFFER0_ARM_READY_FACTOR_WITNESS_V1 | event=SAFE_STUB "
        "first_block=0 last_factor_edge=0 last_accept=0' \\\n"
        "  '0 | COL_AG_MRM_LANE_COUNTS_V1 | event=SAFE_STUB "
        "col_accept=0 bag_accept=0 mse_write_accept=0 mrm_write_accept=0 "
        "records=0 limit=256' \\\n"
        "  '0 | COL_AG_MRM_LANE_STATE_V1 | event=SAFE_STUB "
        "col_out=0 col_bp=0 bag_wr=0 bag_bp=0 bag_rd=0 bag_empty=1 "
        "bag_tag=0 bag_idx=0 mse_req=0 mse_row=0 mse_col=0 mse_wvalid=0 "
        "mse_ready=0 mrm_req=0 mrm_row=0 mrm_strb=0 mrm_wvalid=0 "
        "mrm_ready=0 valid_at_arm_addr=0' \\\n"
        "  '0 | COL_AG_MRM_LANE_WITNESS_V1 | event=SAFE_STUB "
        "first_col=0 last_col=0 last_bag=0 last_mse_write=0 last_mrm_write=0' \\\n"
        "  >\"$observer_log\"\n",
        "v31 records",
    )
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    return bin_dir, sim_started


def validate_return(package: Path, mock_server: Path) -> dict[str, Any]:
    result = ORIGINAL_VALIDATE_RETURN(package, mock_server)
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    root = f"{ROOT_NAME}_return"
    with zipfile.ZipFile(return_zip) as archive:
        binding = archive.read(f"{root}/evidence/observer_binding.txt").decode("utf-8")
        argv = archive.read(f"{root}/evidence/actual_simulator_argv.txt").decode("utf-8")
    result["col_ag_mrm_lane_binding"] = {
        "enabled": "col_ag_mrm_lane_enabled=true" in binding,
        "limit_256": "col_ag_mrm_lane_limit=256" in binding,
        "records_returned": "col_ag_mrm_lane_records_returned=true" in binding,
        "actual_argv_enable": "+RETURN_OBS_COL_AG_MRM_LANE" in argv,
        "actual_argv_limit": "+RETURN_OBS_COL_AG_MRM_LANE_LIMIT=256" in argv,
    }
    if not all(result["col_ag_mrm_lane_binding"].values()):
        raise ValueError("COL/AG/MRM lane signal-finalizer binding differs")
    return result


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    base.ROOT_NAME = ROOT_NAME
    base.ZIP_SHA256 = ZIP_SHA256
    base.write_mock_tools = write_mock_tools
    base.validate_return = validate_return
    result = base.validate(target_zip, bash)
    result["schema"] = "gap-node0071-v31-col-ag-mrm-safe-signal-stub-v1"
    result["diagnostic_feature"] = "COL_AG_MRM_LANE"
    result["current_rule_scope"]["col_ag_mrm_lane_all_bound"] = all(
        result["return"]["col_ag_mrm_lane_binding"].values()
    )
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
        exit_code = 0
    except Exception as error:
        result = {
            "schema": "gap-node0071-v31-col-ag-mrm-safe-signal-stub-v1",
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
