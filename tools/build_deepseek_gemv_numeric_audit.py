from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from resnet50_pipeline.hashing import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)


WEIGHT = (
    "ndp-sim/generate_python_golden/python_golden_decode_hwverified/"
    "ffn_gate_gemv_in0_shape896x1792x1_dtype_f16.bin"
)
ACTIVATION = (
    "ndp-sim/generate_python_golden/python_golden_decode_hwverified/"
    "ffn_gate_gemv_in1_shape896x1x1_dtype_f16.bin"
)
OUTPUT = (
    "ndp-sim/generate_python_golden/python_golden_decode_hwverified/"
    "ffn_gate_gemv_out_shape1792x1x1_dtype_f16.bin"
)
AUDIT = (
    "contracts/operator_config/deepseek_gemv_numeric_audit_v1.json"
)


def _binding(root: Path, relative: str) -> dict[str, object]:
    path = root / relative
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    golden_root = root / "ndp-sim/generate_python_golden"
    sys.path.insert(0, str(golden_root))
    from decode_ops import gemv_fp32_accumulate
    from tensor_io import load_golden_tensor

    weight = load_golden_tensor(root / WEIGHT).squeeze()
    activation = load_golden_tensor(root / ACTIVATION).reshape(
        -1, order="F"
    )
    expected = load_golden_tensor(root / OUTPUT).reshape(
        -1, order="F"
    )
    actual = gemv_fp32_accumulate(weight, activation).astype(
        np.float16
    )
    mismatch_count = int(
        np.count_nonzero(
            actual.view(np.uint16) != expected.view(np.uint16)
        )
    )
    payload: dict[str, object] = {
        "schema": "deepseek-gemv-numeric-audit-v1",
        "operator": "decode_gemv_ring",
        "instance": "ffn_gate_gemv",
        "formula": (
            "fp16_output = fp16(fp32_fma_accumulate("
            "weight[896,1792].T, activation[896]))"
        ),
        "inputs": {
            "weight": _binding(root, WEIGHT),
            "activation": _binding(root, ACTIVATION),
            "expected_output": _binding(root, OUTPUT),
        },
        "shapes": {
            "weight": list(weight.shape),
            "activation": list(activation.shape),
            "output": list(expected.shape),
        },
        "comparison": {
            "element_count": int(expected.size),
            "bitwise_fp16_mismatch_count": mismatch_count,
            "bitwise_fp16_equal": mismatch_count == 0,
        },
        "identity_boundary": {
            "classification": (
                "TRUSTED_CROP_DERIVED_HWVERIFIED_NUMERIC_ORACLE"
            ),
            "original_onnx_external_data_identity": False,
        },
    }
    payload["audit_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    output = root / AUDIT
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output)
    print(payload["audit_sha256"])
    return 0 if mismatch_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
