from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.conv16_layout import ConvBatch16PhysicalLayout
from resnet50_pipeline.conv16_ring_layout import ConvRing16PhysicalLayout
from resnet50_pipeline.hashing import sha256_file
from resnet50_pipeline.maxpool16_layout import (
    MaxPoolBatch16PhysicalLayout,
    MaxPoolChannel16PhysicalLayout,
)
from verify_w4_conv0_layout import _array_hash, load_formal_conv0_case


def _profile(
    conv_layout,
    pool_layout,
    conv_values: dict[str, Any],
    pool_input: np.ndarray,
    pool_output: np.ndarray,
    pool_attributes: dict[str, Any],
    tensor_ids: dict[str, str],
) -> dict[str, Any]:
    conv_bundle = conv_layout.forward(**conv_values)
    pool_bundle = pool_layout.forward(
        activation=pool_input,
        output=pool_output,
        kernel_shape=tuple(pool_attributes["kernel_shape"]),
        strides=tuple(pool_attributes.get("strides", (1, 1))),
        pads=tuple(pool_attributes.get("pads", (0, 0, 0, 0))),
        ceil_mode=int(pool_attributes.get("ceil_mode", 0)),
        storage_order=int(pool_attributes.get("storage_order", 0)),
        spatial_padding_value=0,
        input_tail_value=int(conv_values["y_zero_point"].reshape(-1)[0]),
        tensor_ids=tensor_ids,
        input_base_addresses=tuple(
            conv_bundle.region("D", slice_id).base_address for slice_id in range(16)
        ),
    )
    alias = pool_layout.prove_conv_input_alias(conv_bundle, pool_bundle)
    recovered_input = pool_layout.inverse_port(pool_bundle, "A")
    recovered_output = pool_layout.inverse_port(pool_bundle, "D")
    np.testing.assert_array_equal(recovered_input, pool_input)
    np.testing.assert_array_equal(recovered_output, pool_output)
    validation = pool_layout.validate(pool_bundle)
    result = {
        "conv_contract": conv_layout.contract,
        "pool_contract": pool_layout.contract,
        "per_slice_used_bytes": pool_bundle.metadata["per_slice_used_bytes"],
        "logical_physical_bytes": sum(len(value) for value in pool_bundle.payloads.values()),
        "input_inverse_sha256": _array_hash(recovered_input),
        "output_inverse_sha256": _array_hash(recovered_output),
        "layout_record_count": len(pool_bundle.layout_records()),
        "validation": validation,
        "zero_copy_alias": alias,
        "all_inverse_bit_exact": True,
    }
    del conv_bundle, pool_bundle, recovered_input, recovered_output
    gc.collect()
    return result


def verify(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    conv_case = load_formal_conv0_case(root)
    graph_path = root / "artifacts/w3/model_graph.json"
    catalog = json.loads(graph_path.read_text(encoding="utf-8"))
    pool_node = next(
        item for item in catalog["nodes"] if item["op_type"] == "MaxPool"
    )
    input_id = pool_node["input_tensor_ids"][0]
    output_id = pool_node["output_tensor_ids"][0]
    if input_id != conv_case["node_record"]["output_tensor_ids"][0]:
        raise ValueError("formal MaxPool input is not Conv0 output")
    golden_root = root / "artifacts/w3/golden_batch16/tensors"
    input_path = golden_root / f"{input_id}.npy"
    output_path = golden_root / f"{output_id}.npy"
    pool_input = np.load(input_path, allow_pickle=False)
    pool_output = np.load(output_path, allow_pickle=False)
    np.testing.assert_array_equal(pool_input, conv_case["values"]["output"])
    tensor_ids = {"A": input_id, "D": output_id}
    batch = _profile(
        ConvBatch16PhysicalLayout(),
        MaxPoolBatch16PhysicalLayout(),
        conv_case["values"],
        pool_input,
        pool_output,
        pool_node["attributes"],
        tensor_ids,
    )
    channel = _profile(
        ConvRing16PhysicalLayout(),
        MaxPoolChannel16PhysicalLayout(),
        conv_case["values"],
        pool_input,
        pool_output,
        pool_node["attributes"],
        tensor_ids,
    )
    if batch["input_inverse_sha256"] != channel["input_inverse_sha256"]:
        raise ValueError("MaxPool profiles recover different logical inputs")
    if batch["output_inverse_sha256"] != channel["output_inverse_sha256"]:
        raise ValueError("MaxPool profiles recover different logical outputs")
    return {
        "schema_version": "0.1",
        "model_sha256": catalog["model_sha256"],
        "node_id": pool_node["node_id"],
        "onnx_name": pool_node["onnx_name"],
        "attributes": pool_node["attributes"],
        "spatial_padding_value": 0,
        "source_files": {
            "input": {
                "path": input_path.relative_to(root).as_posix(),
                "sha256": sha256_file(input_path),
            },
            "output": {
                "path": output_path.relative_to(root).as_posix(),
                "sha256": sha256_file(output_path),
            },
        },
        "logical_input_sha256": _array_hash(pool_input),
        "logical_output_sha256": _array_hash(pool_output),
        "profiles": {"batch": batch, "channel": channel},
        "all_profiles_inverse_bit_exact": True,
        "all_profiles_logical_bit_exact": True,
        "all_conv_d_maxpool_a_zero_copy": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify W4 formal MaxPool batch/channel layouts and Conv aliases"
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
