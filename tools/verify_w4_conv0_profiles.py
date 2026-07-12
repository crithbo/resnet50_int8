from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.hashing import sha256_file
from verify_w4_conv0_layout import _array_hash, load_formal_conv0_case


def verify_profiles(project_root: Path) -> dict[str, Any]:
    case = load_formal_conv0_case(project_root)
    values = case["values"]
    tensor_ids = case["tensor_ids"]
    expected = dict(case["expected"])
    multiplier = (
        np.float32(values["x_scale"].reshape(-1)[0])
        * values["w_scale"].astype(np.float32).reshape(-1)
        / np.float32(values["y_scale"].reshape(-1)[0])
    ).astype(np.float32)
    expected[tensor_ids["multiplier"]] = multiplier

    batch_layout = ConvBatch16PhysicalLayout()
    ring_layout = ConvRing16PhysicalLayout()
    batch_bundle = batch_layout.forward(**values)
    ring_bundle = ring_layout.forward(**values)
    batch_inverse = batch_layout.inverse(batch_bundle)
    ring_inverse = ring_layout.inverse(ring_bundle)
    comparisons: dict[str, Any] = {}
    for tensor_id, reference in expected.items():
        batch_value = batch_inverse[tensor_id]
        ring_value = ring_inverse[tensor_id]
        np.testing.assert_array_equal(batch_value, reference)
        np.testing.assert_array_equal(ring_value, reference)
        np.testing.assert_array_equal(batch_value, ring_value)
        comparisons[tensor_id] = {
            "shape": list(reference.shape),
            "dtype": str(reference.dtype),
            "logical_sha256": _array_hash(reference),
            "batch_inverse_sha256": _array_hash(batch_value),
            "ring_inverse_sha256": _array_hash(ring_value),
            "batch_ring_bit_exact": True,
        }
    batch_validation = batch_layout.validate(batch_bundle)
    ring_validation = ring_layout.validate(ring_bundle)
    ring_steps = [
        ring_layout.explain_ring_step(
            ring_bundle, output_channel=0, step=step
        )
        for step in range(16)
    ]
    root = case["root"]
    return {
        "schema_version": "0.1",
        "node_id": case["node_record"]["node_id"],
        "onnx_name": case["node_record"]["onnx_name"],
        "model_sha256": sha256_file(case["model_path"]),
        "source_files": {
            "activation": {
                "path": case["activation_path"].relative_to(root).as_posix(),
                "sha256": sha256_file(case["activation_path"]),
            },
            "accumulator": {
                "path": case["accumulator_path"].relative_to(root).as_posix(),
                "sha256": sha256_file(case["accumulator_path"]),
            },
            "output": {
                "path": case["output_path"].relative_to(root).as_posix(),
                "sha256": sha256_file(case["output_path"]),
            },
        },
        "profiles": {
            batch_layout.contract: {
                "status": batch_layout.status,
                "slice_topology": batch_bundle.metadata["slice_topology"],
                "per_slice_used_bytes": batch_bundle.metadata["per_slice_used_bytes"],
                "logical_physical_bytes": sum(
                    len(value) for value in batch_bundle.payloads.values()
                ),
                "layout_record_count": len(batch_bundle.layout_records()),
                "validation": batch_validation,
            },
            ring_layout.contract: {
                "status": ring_layout.status,
                "slice_topology": ring_bundle.metadata["slice_topology"],
                "c_tile": ring_bundle.metadata["c_tile"],
                "k_tile": ring_bundle.metadata["k_tile"],
                "c_padded": ring_bundle.metadata["c_padded"],
                "k_padded": ring_bundle.metadata["k_padded"],
                "per_slice_used_bytes": ring_bundle.metadata["per_slice_used_bytes"],
                "logical_physical_bytes": sum(
                    len(value) for value in ring_bundle.payloads.values()
                ),
                "layout_record_count": len(ring_bundle.layout_records()),
                "validation": ring_validation,
                "output_channel_0_ring_steps": ring_steps,
            },
        },
        "slice_capacity_bytes": batch_bundle.geometry.bytes_per_slice,
        "comparisons": comparisons,
        "all_batch_inverse_bit_exact": True,
        "all_ring_inverse_bit_exact": True,
        "all_batch_ring_logical_bit_exact": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify W4 Conv0 batch16 and ring16 relayout profiles"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify_profiles(args.project_root)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output
        if not output.is_absolute():
            output = args.project_root / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
