from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v28_signal_stub as base


ROOT_NAME = "r5_n71_gap_v29_mse0_buffer_prep_group0_diag"
ZIP_SHA256 = "15833d826872e118a9be834b082351ae2b31862da0b138a2a4f271269108e164"
ORIGINAL_WRITE_MOCK_TOOLS = base.write_mock_tools
ORIGINAL_VALIDATE_RETURN = base.validate_return


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"safe stub marker differs: {label}")
    return text.replace(old, new, 1)


def write_mock_tools(root: Path) -> tuple[Path, Path]:
    bin_dir, sim_started = ORIGINAL_WRITE_MOCK_TOOLS(root)
    wrapper = bin_dir / "make"
    text = wrapper.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "pair_limit=false\n",
        "pair_limit=false\nm0_path=false\nm0_limit=false\n",
        "feature variables",
    )
    text = replace_once(
        text,
        "    +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512) pair_limit=true;;\n",
        "    +RETURN_OBS_GA_MSE4_FINAL_PAIR_LIMIT=512) pair_limit=true;;\n"
        "    +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0) m0_path=true;;\n"
        "    +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512) m0_limit=true;;\n",
        "feature argv",
    )
    text = replace_once(
        text,
        '[ "$pair_limit" = true ] || exit 77\n',
        '[ "$pair_limit" = true ] || exit 77\n'
        '[ "$m0_path" = true ] || exit 74\n'
        '[ "$m0_limit" = true ] || exit 75\n',
        "feature guards",
    )
    text = replace_once(
        text,
        "ga_mse4_final_pair=1 ga_mse4_final_pair_limit=512'",
        "ga_mse4_final_pair=1 ga_mse4_final_pair_limit=512 "
        "mse0_buffer_prep_group0=1 mse0_buffer_prep_group0_limit=512'",
        "time0 marker",
    )
    text = replace_once(
        text,
        "  '0 | GA_MSE4_FINAL_PAIR_WITNESS_V1 | event=SAFE_STUB "
        "last_ga_accept=0 last_ga_retire=0 last_ga_wr=0 last_m4_req=0 "
        "last_m4_buf=0 last_m4_ob_wr=0 last_m4_ob_rd=0' \\\n"
        "  >\"$observer_log\"\n",
        "  '0 | GA_MSE4_FINAL_PAIR_WITNESS_V1 | event=SAFE_STUB "
        "last_ga_accept=0 last_ga_retire=0 last_ga_wr=0 last_m4_req=0 "
        "last_m4_buf=0 last_m4_ob_wr=0 last_m4_ob_rd=0' \\\n"
        "  '0 | MSE0_BUFFER_PREP_GROUP0_COUNTS_V1 | event=SAFE_STUB "
        "buf_accept=0 arm_accept=0 arm_clear=0 prep_wr=0 prep_rd=0 "
        "data_vld=0 group0_accept=0 records=0 limit=512' \\\n"
        "  '0 | MSE0_BUFFER_PREP_GROUP0_STATE_V1 | event=SAFE_STUB "
        "buf_vld=0x0 arm_req=0x0 arm_ready=0 arm_rw=0 arm_clear=0x0 "
        "arm_addr=0x0 arm_count=0/0 rd_q_empty=1 ib_vld=0x0 ib_sel=0 "
        "prep_wr=0 prep_rd=0 prep_count=0 data_vld=0 buf_rtag=0x0 "
        "buf_bp=0 group0_tag=0x0 group0_bp=0' \\\n"
        "  '0 | MSE0_BUFFER_PREP_GROUP0_WITNESS_V1 | event=SAFE_STUB "
        "last_buf_accept=0 last_arm_accept=0 last_arm_clear=0 "
        "last_prep_wr=0 last_prep_rd=0 last_data_vld=0 "
        "last_group0_accept=0' \\\n"
        "  >\"$observer_log\"\n",
        "feature records",
    )
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    return bin_dir, sim_started


def validate_return(package: Path, mock_server: Path) -> dict[str, Any]:
    result = ORIGINAL_VALIDATE_RETURN(package, mock_server)
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    files, _ = base.base.base.base.read_return_zip(return_zip)
    binding = files["evidence/observer_binding.txt"].decode("utf-8")
    argv = files["evidence/actual_simulator_argv.txt"].decode("utf-8")
    result["mse0_buffer_prep_group0_binding"] = {
        "enabled": "mse0_buffer_prep_group0_enabled=true" in binding,
        "limit_512": "mse0_buffer_prep_group0_limit=512" in binding,
        "records_returned":
            "mse0_buffer_prep_group0_records_returned=true" in binding,
        "actual_argv_enable":
            "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0" in argv,
        "actual_argv_limit":
            "+RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512" in argv,
    }
    if not all(result["mse0_buffer_prep_group0_binding"].values()):
        raise base.base.base.base.RevalidationError(
            "MSE0 Buffer/prepared/group0 signal-finalizer binding differs"
        )
    return result


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    base.ROOT_NAME = ROOT_NAME
    base.ZIP_SHA256 = ZIP_SHA256
    base.base.ROOT_NAME = ROOT_NAME
    base.base.ZIP_SHA256 = ZIP_SHA256
    base.base.base.ROOT_NAME = ROOT_NAME
    base.base.base.ZIP_SHA256 = ZIP_SHA256
    base.write_mock_tools = write_mock_tools
    base.validate_return = validate_return
    result = base.validate(target_zip, bash)
    result["schema"] = (
        "gap-node0071-v29-mse0-buffer-prep-group0-safe-signal-stub-"
        "revalidation-v1"
    )
    result["diagnostic_feature"] = "MSE0_BUFFER_PREP_GROUP0"
    result["current_rule_scope"]["mse0_feature_all_bound"] = all(
        result["return"]["mse0_buffer_prep_group0_binding"].values()
    )
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
                "gap-node0071-v29-mse0-buffer-prep-group0-safe-signal-"
                "stub-revalidation-v1"
            ),
            "status": "FAIL",
            "error": str(error),
        }
        exit_code = 1
    else:
        exit_code = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
