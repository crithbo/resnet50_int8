from __future__ import annotations

import argparse
from pathlib import Path

from resnet50_pipeline.deepseek_onnx_validation import (
    build_deepseek_crop_contract,
    build_deepseek_onnx_stage_mapping,
    build_deepseek_prefill_stage_audit,
    write_deepseek_crop_contract,
    write_deepseek_onnx_stage_mapping,
    write_deepseek_prefill_stage_audit,
)


DEFAULT_OUTPUT = (
    "contracts/operator_config/deepseek_ndpsim_crop_contract_v1.json"
)
DEFAULT_STAGE_MAPPING_OUTPUT = (
    "contracts/operator_config/"
    "deepseek_onnx_stage_mapping_v1.json"
)
DEFAULT_PREFILL_AUDIT_OUTPUT = (
    "contracts/operator_config/"
    "deepseek_onnx_prefill_stage_audit_v1.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the explicit DeepSeek source-to-NDP crop contract."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument(
        "--stage-mapping-output",
        type=Path,
        default=Path(DEFAULT_STAGE_MAPPING_OUTPUT),
    )
    parser.add_argument(
        "--prefill-audit-output",
        type=Path,
        default=Path(DEFAULT_PREFILL_AUDIT_OUTPUT),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.project_root.resolve()
    output = args.output
    if not output.is_absolute():
        output = root / output
    value = build_deepseek_crop_contract(root)
    write_deepseek_crop_contract(output, value)
    print(output)
    print(value["contract_sha256"])
    stage_output = args.stage_mapping_output
    if not stage_output.is_absolute():
        stage_output = root / stage_output
    stage_value = build_deepseek_onnx_stage_mapping(root)
    write_deepseek_onnx_stage_mapping(stage_output, stage_value)
    print(stage_output)
    print(stage_value["mapping_sha256"])
    prefill_output = args.prefill_audit_output
    if not prefill_output.is_absolute():
        prefill_output = root / prefill_output
    prefill_value = build_deepseek_prefill_stage_audit(root)
    write_deepseek_prefill_stage_audit(prefill_output, prefill_value)
    print(prefill_output)
    print(prefill_value["audit_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
