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

from tools import revalidate_gap_node0071_v29_signal_stub as base


ROOT_NAME = "r5_n71_gap_v30_arm_ready_factor_diag"
ZIP_SHA256 = "f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931"
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
        text, "m0_limit=false\n",
        "m0_limit=false\narmf=false\narmf_limit=false\n", "feature variables",
    )
    text = replace_once(
        text,
        "    +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512) m0_limit=true;;\n",
        "    +RETURN_OBS_MSE0_BUFFER_PREP_GROUP0_LIMIT=512) m0_limit=true;;\n"
        "    +RETURN_OBS_BUFFER0_ARM_READY_FACTORS) armf=true;;\n"
        "    +RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256) armf_limit=true;;\n",
        "feature argv",
    )
    text = replace_once(
        text,
        '[ "$m0_limit" = true ] || exit 75\n',
        '[ "$m0_limit" = true ] || exit 75\n'
        '[ "$armf" = true ] || exit 72\n'
        '[ "$armf_limit" = true ] || exit 73\n',
        "feature guards",
    )
    text = replace_once(
        text,
        "mse0_buffer_prep_group0=1 mse0_buffer_prep_group0_limit=512'",
        "mse0_buffer_prep_group0=1 mse0_buffer_prep_group0_limit=512 "
        "buffer0_arm_ready_factors=1 buffer0_arm_ready_factors_limit=256'",
        "time0 marker",
    )
    text = replace_once(
        text,
        "  '0 | MSE0_BUFFER_PREP_GROUP0_WITNESS_V1 | event=SAFE_STUB "
        "last_buf_accept=0 last_arm_accept=0 last_arm_clear=0 "
        "last_prep_wr=0 last_prep_rd=0 last_data_vld=0 "
        "last_group0_accept=0' \\\n"
        "  >\"$observer_log\"\n",
        "  '0 | MSE0_BUFFER_PREP_GROUP0_WITNESS_V1 | event=SAFE_STUB "
        "last_buf_accept=0 last_arm_accept=0 last_arm_clear=0 "
        "last_prep_wr=0 last_prep_rd=0 last_data_vld=0 "
        "last_group0_accept=0' \\\n"
        "  '0 | BUFFER0_ARM_READY_FACTOR_COUNTS_V1 | event=SAFE_STUB "
        "accept=0 bank_edge=0 barrier_edge=0 ready_edge=0 block_entry=0 "
        "records=0 limit=256' \\\n"
        "  '0 | BUFFER0_ARM_READY_FACTOR_STATE_V1 | event=SAFE_STUB "
        "req=0x0 rw=0 addr=0x0 mask=0x0 bank_ready=0x0 "
        "selected_ready=0x0 barrier=0 composite_ready=0 "
        "clear_at_addr=0 valid_at_addr=0x0' \\\n"
        "  '0 | BUFFER0_ARM_READY_FACTOR_WITNESS_V1 | event=SAFE_STUB "
        "first_block=0 last_factor_edge=0 last_accept=0' \\\n"
        "  >\"$observer_log\"\n",
        "feature records",
    )
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    return bin_dir, sim_started


def validate_return(package: Path, mock_server: Path) -> dict[str, Any]:
    result = ORIGINAL_VALIDATE_RETURN(package, mock_server)
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    root = f"{ROOT_NAME}_return"
    with zipfile.ZipFile(return_zip) as archive:
        binding = archive.read(
            f"{root}/evidence/observer_binding.txt"
        ).decode("utf-8")
        argv = archive.read(
            f"{root}/evidence/actual_simulator_argv.txt"
        ).decode("utf-8")
    result["buffer0_arm_ready_factor_binding"] = {
        "enabled": "buffer0_arm_ready_factors_enabled=true" in binding,
        "limit_256": "buffer0_arm_ready_factors_limit=256" in binding,
        "records_returned":
            "buffer0_arm_ready_factors_records_returned=true" in binding,
        "actual_argv_enable":
            "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS" in argv,
        "actual_argv_limit":
            "+RETURN_OBS_BUFFER0_ARM_READY_FACTORS_LIMIT=256" in argv,
    }
    if not all(result["buffer0_arm_ready_factor_binding"].values()):
        raise ValueError("Buffer0 ARM-ready signal-finalizer binding differs")
    return result


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    base.ROOT_NAME = ROOT_NAME
    base.ZIP_SHA256 = ZIP_SHA256
    base.write_mock_tools = write_mock_tools
    base.validate_return = validate_return
    result = base.validate(target_zip, bash)
    result["schema"] = (
        "gap-node0071-v30-buffer0-arm-ready-factor-safe-signal-stub-v1"
    )
    result["diagnostic_feature"] = "BUFFER0_ARM_READY_FACTORS"
    result["current_rule_scope"]["arm_ready_factor_all_bound"] = all(
        result["return"]["buffer0_arm_ready_factor_binding"].values()
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash", type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.bash.resolve())
        exit_code = 0
    except Exception as error:
        result = {
            "schema": "gap-node0071-v30-buffer0-arm-ready-factor-safe-signal-stub-v1",
            "status": "FAIL",
            "error": str(error),
        }
        exit_code = 1
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
