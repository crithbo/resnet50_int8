from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.pool28_layout import (  # noqa: E402
    GlobalAveragePoolPhysicalLayout,
    MaxPoolPhysicalLayout,
)
from resnet50_pipeline.profile28 import (  # noqa: E402
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)


def _maxpool_reference(activation: np.ndarray) -> np.ndarray:
    padded = np.pad(activation, ((0, 0), (0, 0), (1, 1), (1, 1)))
    output = np.empty((16, activation.shape[1], 3, 3), dtype=np.uint8)
    for oh in range(3):
        for ow in range(3):
            window = padded[:, :, oh * 2 : oh * 2 + 3, ow * 2 : ow * 2 + 3]
            output[:, :, oh, ow] = window.max(axis=(2, 3))
    return output


def _gap_values() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(20260713)
    activation = rng.integers(0, 256, size=(16, 5, 2, 3), dtype=np.uint8)
    x_scale = np.array([0.025], dtype=np.float32)
    x_zero_point = np.array([111], dtype=np.uint8)
    y_scale = np.array([0.04], dtype=np.float32)
    y_zero_point = np.array([97], dtype=np.uint8)
    accumulator = np.sum(
        activation.astype(np.int32) - int(x_zero_point[0]),
        axis=(2, 3),
        keepdims=True,
        dtype=np.int64,
    ).astype(np.int32)
    multiplier = np.float32(x_scale[0]) / (
        np.float32(y_scale[0]) * np.float32(6)
    )
    output = np.clip(
        np.rint(accumulator.astype(np.float32) * multiplier).astype(np.int64)
        + int(y_zero_point[0]),
        0,
        255,
    ).astype(np.uint8)
    return {
        "activation": activation,
        "x_scale": x_scale,
        "x_zero_point": x_zero_point,
        "y_scale": y_scale,
        "y_zero_point": y_zero_point,
        "accumulator": accumulator,
        "output": output,
    }


def _plan_summary(plan: dict[str, object]) -> dict[str, object]:
    return {
        "input_shape": plan["input_shape"],
        "output_shape": plan["output_shape"],
        "channel_tile": plan["channel_tile"],
        "storage_sample_count": plan["storage_sample_count"],
        "per_slice_used_bytes": plan["per_slice_used_bytes"],
        "capacity_bytes": plan["capacity_bytes"],
        "capacity_margin_bytes": int(plan["capacity_bytes"])
        - int(plan["per_slice_used_bytes"]),
        "fits": plan["fits"],
    }


def build_report() -> dict[str, object]:
    activation = np.arange(16 * 5 * 5 * 5, dtype=np.uint16).astype(
        np.uint8
    ).reshape(16, 5, 5, 5)
    maxpool_output = _maxpool_reference(activation)
    gap_values = _gap_values()
    profiles: dict[str, object] = {}
    for profile_id in (
        GROUP4X7_BATCH_CHANNEL28_PROFILE,
        GLOBAL_RING28_PROFILE,
    ):
        maxpool = MaxPoolPhysicalLayout(profile_id=profile_id)
        maxpool_bundle = maxpool.forward(
            activation=activation,
            output=maxpool_output,
            kernel_shape=(3, 3),
            strides=(2, 2),
            pads=(1, 1, 1, 1),
            input_tail_value=101,
            output_tail_value=103,
        )
        maxpool_recovered = maxpool.inverse(maxpool_bundle)
        maxpool_plan = maxpool.plan(
            input_shape=(16, 64, 112, 112),
            kernel_shape=(3, 3),
            strides=(2, 2),
            pads=(1, 1, 1, 1),
        )

        gap = GlobalAveragePoolPhysicalLayout(profile_id=profile_id)
        gap_bundle = gap.forward(**gap_values)
        gap_recovered = gap.inverse(gap_bundle)
        gap_plan = gap.plan(input_shape=(16, 2048, 7, 7), output_rank=4)
        profiles[profile_id] = {
            "maxpool": {
                "contract": maxpool.contract,
                "micro_roundtrip_bit_exact": (
                    np.array_equal(
                        maxpool_recovered["maxpool_input"], activation
                    )
                    and np.array_equal(
                        maxpool_recovered["maxpool_output"], maxpool_output
                    )
                ),
                "a_d_owner_compatible": maxpool.prove_a_d_compatibility(
                    maxpool_bundle
                )["compatible"],
                "formal_conv0_plan": _plan_summary(maxpool_plan),
            },
            "global_average_pool": {
                "contract": gap.contract,
                "micro_roundtrip_bit_exact": all(
                    np.array_equal(
                        gap_recovered[
                            {
                                "activation": "globalavgpool_input",
                                "x_scale": "globalavgpool_x_scale",
                                "x_zero_point": "globalavgpool_x_zero_point",
                                "y_scale": "globalavgpool_y_scale",
                                "y_zero_point": "globalavgpool_y_zero_point",
                                "accumulator": "globalavgpool_centered_sum",
                                "output": "globalavgpool_output",
                            }[name]
                        ],
                        value,
                    )
                    for name, value in gap_values.items()
                ),
                "owner_local_reduction": gap.prove_owner_local_reduction(
                    gap_bundle
                )["compatible"],
                "cross_group_reduction": False,
                "formal_resnet_gap_plan": _plan_summary(gap_plan),
            },
        }
    report: dict[str, object] = {
        "schema": "w4_pool28_candidate_report_v1",
        "status": "candidate_unapproved",
        "target_family": "rtl28",
        "slice_count": 28,
        "geometry_status": "candidate_unapproved",
        "address_order_status": "candidate_unapproved",
        "hardware_approval": False,
        "g4_claim": False,
        "w5_artifact": False,
        "notes": [
            "small deterministic arrays only; no W3 tensor payload was read",
            "this report is reversible software-layout evidence, not hardware approval",
            "MaxPool UINT8 spatial boundary and tail values remain separate semantics",
            "GAP keeps A, centered INT32 sum and D on the same channel owner",
        ],
        "profiles": profiles,
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["content_sha256_without_this_field"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify deterministic candidate RTL28 MaxPool/GAP layouts"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="explicit candidate report path; omitted means stdout only",
    )
    args = parser.parse_args()
    payload = json.dumps(build_report(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
