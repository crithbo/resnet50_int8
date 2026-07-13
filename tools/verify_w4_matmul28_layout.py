from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.matmul28_layout import (
    PORT_ORDER,
    QLinearMatMulPhysicalLayout,
)
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)


def _micro_case() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(20260713)
    activation = rng.integers(0, 256, size=(16, 9), dtype=np.uint8)
    weight = rng.integers(-15, 16, size=(9, 11), dtype=np.int16).astype(np.int8)
    a_scale = np.array([0.025], dtype=np.float32)
    a_zero_point = np.array([113], dtype=np.uint8)
    b_scale = np.array([0.0125], dtype=np.float32)
    b_zero_point = np.array([-2], dtype=np.int8)
    y_scale = np.array([0.04], dtype=np.float32)
    y_zero_point = np.array([97], dtype=np.uint8)
    left = activation.astype(np.int32) - int(a_zero_point[0])
    right = weight.astype(np.int32) - int(b_zero_point[0])
    wide = left.astype(np.int64) @ right.astype(np.int64)
    limits = np.iinfo(np.int32)
    if np.any(wide < limits.min) or np.any(wide > limits.max):
        raise OverflowError("micro MatMul accumulator is outside int32")
    accumulator = wide.astype(np.int32)
    multiplier = np.float32(a_scale[0] * b_scale[0] / y_scale[0])
    output = np.clip(
        np.rint(accumulator.astype(np.float32) * multiplier).astype(np.int64)
        + int(y_zero_point[0]),
        0,
        255,
    ).astype(np.uint8)
    return {
        "activation": activation,
        "weight": weight,
        "a_scale": a_scale,
        "a_zero_point": a_zero_point,
        "b_scale": b_scale,
        "b_zero_point": b_zero_point,
        "y_scale": y_scale,
        "y_zero_point": y_zero_point,
        "accumulator": accumulator,
        "output": output,
    }


def _payload_sha256(bundle: Any) -> str:
    digest = hashlib.sha256()
    for port in PORT_ORDER:
        for slice_id in range(bundle.geometry.slice_count):
            digest.update(port.encode("ascii"))
            digest.update(slice_id.to_bytes(2, "little"))
            digest.update(bundle.read(port, slice_id))
    return digest.hexdigest()


def build_report() -> dict[str, Any]:
    values = _micro_case()
    profiles: dict[str, Any] = {}
    for profile_id in (
        GROUP4X7_BATCH_CHANNEL28_PROFILE,
        GLOBAL_RING28_PROFILE,
    ):
        layout = QLinearMatMulPhysicalLayout(profile_id)
        first = layout.forward(**values)
        second = layout.forward(**values)
        validation = layout.validate(first)
        recovered = layout.inverse(first)
        expected = {
            "matmul_input": values["activation"],
            "matmul_weight": values["weight"],
            "matmul_accumulator": values["accumulator"],
            "matmul_output": values["output"],
        }
        bit_exact = all(
            np.array_equal(recovered[tensor_id], logical)
            for tensor_id, logical in expected.items()
        )
        first_hash = _payload_sha256(first)
        second_hash = _payload_sha256(second)
        profiles[profile_id] = {
            "layout_id": layout.contract,
            "status": layout.status,
            "geometry_status": layout.geometry_status,
            "address_order_status": layout.address_order_status,
            "slice_count": validation["slice_count"],
            "region_count": validation["region_count"],
            "micro_bit_exact_roundtrip": bit_exact,
            "deterministic_payload": first_hash == second_hash,
            "payload_sha256": first_hash,
            "formal_head_capacity": layout.capacity_report(
                activation_shape=(16, 2048),
                weight_shape=(2048, 1000),
                weight_dtype="int8",
            ),
        }
    return {
        "schema": "w4_matmul28_candidate_report_v1",
        "operator": "QLinearMatMul",
        "target_family": "rtl28",
        "status": "candidate_unapproved",
        "hardware_approval": False,
        "g4_passed": False,
        "w5_authorized": False,
        "formal_onnx_contract": {
            "A": "uint8 [16,2048]",
            "B": "int8 [2048,1000]",
            "a_qparams": "scalar float32 scale + scalar uint8 zero_point",
            "b_qparams": "scalar float32 scale + scalar int8 zero_point",
            "y_qparams": "scalar float32 scale + scalar uint8 zero_point",
            "P": "lowering-only final int32 [16,1000]",
            "D": "uint8 [16,1000]",
        },
        "profiles": profiles,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic, small W4 RTL28 MatMul candidate evidence."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Explicit JSON destination. Without this option no file is written.",
    )
    args = parser.parse_args()
    encoded = json.dumps(build_report(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
