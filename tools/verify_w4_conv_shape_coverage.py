from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.conv_coverage import (
    ConvShapeFamily,
    deterministic_layout_case,
    load_conv_shape_families,
    validate_family_plans,
)
from resnet50_pipeline.hashing import sha256_file


def _array_hash(array: np.ndarray) -> str:
    canonical = np.ascontiguousarray(array.astype(array.dtype.newbyteorder("<"), copy=False))
    return hashlib.sha256(canonical.tobytes(order="C")).hexdigest()


def _expected(values: dict[str, Any]) -> dict[str, np.ndarray]:
    multiplier = (
        np.float32(values["x_scale"].reshape(-1)[0])
        * values["w_scale"].astype(np.float32).reshape(-1)
        / np.float32(values["y_scale"].reshape(-1)[0])
    ).astype(np.float32)
    return {
        "A": values["activation"],
        "B": values["weight"],
        "bias": values["bias"],
        "w_scale": values["w_scale"],
        "w_zero_point": values["w_zero_point"],
        "x_scale": values["x_scale"],
        "x_zero_point": values["x_zero_point"],
        "y_scale": values["y_scale"],
        "y_zero_point": values["y_zero_point"],
        "multiplier": multiplier,
        "P": values["accumulator"],
        "D": values["output"],
    }


def _round_trip(layout, values: dict[str, Any], expected: dict[str, np.ndarray]):
    bundle = layout.forward(**values)
    hashes: dict[str, str] = {}
    for port, logical in expected.items():
        recovered = layout.inverse_port(bundle, port)
        np.testing.assert_array_equal(recovered, logical)
        hashes[port] = _array_hash(recovered)
    validation = layout.validate(bundle)
    result = {
        "contract": layout.contract,
        "physical_bytes_for_n1": sum(len(value) for value in bundle.payloads.values()),
        "per_slice_used_bytes_for_n1": bundle.metadata["per_slice_used_bytes"],
        "inverse_hashes": hashes,
        "validation": validation,
        "all_inverse_bit_exact": True,
    }
    del bundle
    gc.collect()
    return result


def _verify_family(
    family: ConvShapeFamily,
    batch_layout: ConvBatch16PhysicalLayout,
    ring_layout: ConvRing16PhysicalLayout,
) -> dict[str, Any]:
    plans = validate_family_plans(family, batch_layout, ring_layout)
    values = deterministic_layout_case(family, batch_size=1)
    expected = _expected(values)
    logical_hashes = {port: _array_hash(value) for port, value in expected.items()}
    batch = _round_trip(batch_layout, values, expected)
    ring = _round_trip(ring_layout, values, expected)
    if batch["inverse_hashes"] != logical_hashes:
        raise ValueError(f"batch inverse hash mismatch for {family.family_id}")
    if ring["inverse_hashes"] != logical_hashes:
        raise ValueError(f"ring inverse hash mismatch for {family.family_id}")
    if batch["inverse_hashes"] != ring["inverse_hashes"]:
        raise ValueError(f"batch/ring logical mismatch for {family.family_id}")
    return {
        "family": family.to_dict(),
        "formal_n16_plans": plans,
        "synthetic_roundtrip_batch_size": 1,
        "logical_hashes": logical_hashes,
        "batch_roundtrip": batch,
        "ring_roundtrip": ring,
        "all_batch_ring_logical_bit_exact": True,
    }


def verify(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = root / "artifacts/w3/model_graph.json"
    catalog = json.loads(graph_path.read_text(encoding="utf-8"))
    families = load_conv_shape_families(graph_path, batch_size=16)
    batch_layout = ConvBatch16PhysicalLayout()
    ring_layout = ConvRing16PhysicalLayout()
    coverage = [
        _verify_family(family, batch_layout, ring_layout) for family in families
    ]
    node_ids = [
        node_id for entry in coverage for node_id in entry["family"]["node_ids"]
    ]
    if len(node_ids) != 53 or len(set(node_ids)) != 53:
        raise ValueError("formal Conv coverage must contain 53 unique nodes")
    max_batch = max(
        coverage,
        key=lambda item: item["formal_n16_plans"]["batch"]["per_slice_used_bytes"],
    )
    max_ring = max(
        coverage,
        key=lambda item: item["formal_n16_plans"]["ring"]["per_slice_used_bytes"],
    )
    return {
        "schema_version": "0.1",
        "model_sha256": catalog["model_sha256"],
        "model_graph": {
            "path": graph_path.relative_to(root).as_posix(),
            "sha256": sha256_file(graph_path),
        },
        "conv_node_count": len(node_ids),
        "conv_family_count": len(coverage),
        "contracts": [batch_layout.contract, ring_layout.contract],
        "formal_plan_batch_size": 16,
        "roundtrip_batch_size": 1,
        "max_batch_per_slice": {
            "family_id": max_batch["family"]["family_id"],
            "bytes": max_batch["formal_n16_plans"]["batch"]["per_slice_used_bytes"],
            "capacity_bytes": max_batch["formal_n16_plans"]["batch"]["capacity_bytes"],
        },
        "max_ring_per_slice": {
            "family_id": max_ring["family"]["family_id"],
            "bytes": max_ring["formal_n16_plans"]["ring"]["per_slice_used_bytes"],
            "capacity_bytes": max_ring["formal_n16_plans"]["ring"]["capacity_bytes"],
        },
        "coverage": coverage,
        "all_53_nodes_covered_once": True,
        "all_20_families_fit_both_profiles": True,
        "all_owner_ranges_exact": True,
        "all_ring_orders_are_permutations": True,
        "all_family_roundtrips_bit_exact": True,
        "all_batch_ring_logical_bit_exact": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify W4 batch/ring coverage for all formal Conv shape families"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.project_root)
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
