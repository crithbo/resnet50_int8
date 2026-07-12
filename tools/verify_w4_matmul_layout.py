from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

from resnet50_pipeline.add16_layout import (
    QLinearAddBatch16PhysicalLayout,
    QLinearAddChannel16PhysicalLayout,
)
from resnet50_pipeline.hashing import sha256_file
from resnet50_pipeline.matmul16_layout import (
    QLinearMatMulBatch16PhysicalLayout,
    QLinearMatMulRing16PhysicalLayout,
)
from resnet50_pipeline.simple_layout import (
    DequantizeLinearPhysicalLayout,
    QuantizeLinearPhysicalLayout,
)
from verify_w4_add_layout import _load_case as load_add_case
from verify_w4_conv0_layout import _array_hash


PORTS = (
    "A",
    "x_scale",
    "x_zero_point",
    "B",
    "w_scale",
    "w_zero_point",
    "y_scale",
    "y_zero_point",
    "multiplier",
    "P",
    "D",
)


def _source(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
    }


def _profile(
    matmul_layout,
    add_layout,
    values: dict[str, np.ndarray],
    tensor_ids: dict[str, str],
    add_case: dict[str, Any],
    quantize_bundle,
    dequantize_bundle,
) -> dict[str, Any]:
    if matmul_layout.topology == "batch":
        input_bases = tuple(
            quantize_bundle.region("D", slice_id).base_address
            for slice_id in range(16)
        )
        bundle = matmul_layout.forward(
            **values,
            tensor_ids=tensor_ids,
            input_base_addresses=input_bases,
        )
        input_transition = matmul_layout.prove_batch_quantize_input_alias(
            quantize_bundle, bundle
        )
    else:
        bundle = matmul_layout.forward(**values, tensor_ids=tensor_ids)
        input_transition = {
            "compatible": True,
            "exact_alias": False,
            "transition": "batch_quantize_D_to_ring_K_partition_explicit_relayout",
            "logical_input_sha256": _array_hash(values["activation"]),
            "inverse_input_sha256": _array_hash(
                matmul_layout.inverse_port(bundle, "A")
            ),
            "logical_bit_exact": True,
        }

    recovered = matmul_layout.inverse(bundle)
    expected = {
        "A": values["activation"],
        "x_scale": values["x_scale"],
        "x_zero_point": values["x_zero_point"],
        "B": values["weight"],
        "w_scale": values["w_scale"],
        "w_zero_point": values["w_zero_point"],
        "y_scale": values["y_scale"],
        "y_zero_point": values["y_zero_point"],
        "multiplier": np.array([bundle.metadata["multiplier"]], dtype=np.float32),
        "P": values["accumulator"],
        "D": values["output"],
    }
    comparisons: dict[str, Any] = {}
    for port in PORTS:
        candidate = recovered[tensor_ids[port]]
        reference = expected[port]
        np.testing.assert_array_equal(candidate, reference)
        comparisons[port] = {
            "tensor_id": tensor_ids[port],
            "shape": list(reference.shape),
            "dtype": str(reference.dtype),
            "logical_sha256": _array_hash(reference),
            "inverse_sha256": _array_hash(candidate),
            "bit_exact": True,
        }

    np.testing.assert_array_equal(add_case["values"]["a"], values["output"])
    output_bases = tuple(
        bundle.region("D", slice_id).base_address for slice_id in range(16)
    )
    add_bundle = add_layout.forward(
        **add_case["values"],
        tensor_ids=add_case["tensor_ids"],
        input_base_addresses={"A": output_bases},
    )
    output_alias = add_layout.prove_input_compatibility(
        bundle, add_bundle, "A", require_same_base=True
    )
    dense_output_id = add_case["tensor_ids"]["D"]
    if dequantize_bundle.region("A", 0).tensor_id != dense_output_id:
        raise ValueError("dense Add D and Dequantize A tensor IDs differ")
    if matmul_layout.topology == "batch":
        physical_bytes_equal = True
        base_addresses_equal = True
        for slice_id in range(16):
            add_region = add_bundle.region("D", slice_id)
            dequant_region = dequantize_bundle.region("A", slice_id)
            if add_region.payload_bytes != dequant_region.payload_bytes:
                raise ValueError("dense Add D and Dequantize A payload sizes differ")
            physical_bytes_equal &= (
                add_bundle.read("D", slice_id)
                == dequantize_bundle.read("A", slice_id)
            )
            base_addresses_equal &= (
                add_region.base_address == dequant_region.base_address
            )
        if not physical_bytes_equal:
            raise ValueError("dense Add D and Dequantize A physical bytes differ")
        dequant_transition = {
            "compatible": True,
            "physical_bytes_equal": True,
            "base_addresses_equal": base_addresses_equal,
            "exact_alias": base_addresses_equal,
            "memory_plan_rebase_required": not base_addresses_equal,
            "transition": "batch_layout_compatible_rebase_in_W7",
            "shared_tensor_id": dense_output_id,
        }
    else:
        dequant_transition = {
            "compatible": True,
            "exact_alias": False,
            "transition": "channel_O_partition_to_batch_Dequantize_explicit_relayout",
            "logical_input_sha256": _array_hash(add_case["values"]["output"]),
            "shared_tensor_id": dense_output_id,
        }
    result = {
        "matmul_contract": matmul_layout.contract,
        "add_contract": add_layout.contract,
        "slice_topology": bundle.metadata["slice_topology"],
        "k_tile": bundle.metadata["k_tile"],
        "o_tile": bundle.metadata["o_tile"],
        "k_padded": bundle.metadata["k_padded"],
        "o_padded": bundle.metadata["o_padded"],
        "ring_steps": bundle.metadata["ring_steps"],
        "neighbor_transfer_count": bundle.metadata["neighbor_transfer_count"],
        "per_slice_used_bytes": bundle.metadata["per_slice_used_bytes"],
        "slice_capacity_bytes": bundle.geometry.bytes_per_slice,
        "logical_physical_bytes": sum(len(value) for value in bundle.payloads.values()),
        "layout_record_count": len(bundle.layout_records()),
        "validation": matmul_layout.validate(bundle),
        "quantize_d_to_matmul_a": input_transition,
        "matmul_d_to_dense_add_a": output_alias,
        "dense_add_d_to_dequantize_a": dequant_transition,
        "dense_bias_b": {
            "tensor_id": add_case["tensor_ids"]["B"],
            "shape": list(add_case["values"]["b"].shape),
            "placement": add_bundle.metadata["ports"]["B"]["placement"],
            "broadcast_mode": add_bundle.metadata["broadcast_mode"],
        },
        "comparisons": comparisons,
        "all_inverse_bit_exact": True,
    }
    if matmul_layout.topology == "ring":
        first = matmul_layout.explain_ring_step(
            bundle, output_feature=999, step=0
        )
        last = matmul_layout.explain_ring_step(
            bundle, output_feature=999, step=15
        )
        result["ring_probe"] = {"first": first, "last": last}
    del bundle, add_bundle, recovered
    gc.collect()
    return result


def verify(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    graph_path = root / "artifacts/w3/model_graph.json"
    subop_manifest_path = root / "artifacts/w3/subop_batch16/manifest.json"
    model_path = root / "artifacts/reference_model/resnet50-v1-12-int8.onnx"
    golden_root = root / "artifacts/w3/golden_batch16/tensors"
    subop_root = root / "artifacts/w3/subop_batch16/tensors"
    catalog = json.loads(graph_path.read_text(encoding="utf-8"))
    subop_manifest = json.loads(subop_manifest_path.read_text(encoding="utf-8"))
    nodes = {item["node_id"]: item for item in catalog["nodes"]}
    tensors = {item["tensor_id"]: item for item in catalog["tensors"]}
    node = nodes["node-0075"]
    quantize_node = nodes[tensors[node["input_tensor_ids"][0]]["producer_node_id"]]
    add_node = nodes[tensors[node["output_tensor_ids"][0]]["consumer_node_ids"][0]]
    if quantize_node["node_id"] != "node-0074" or quantize_node["op_type"] != "QuantizeLinear":
        raise ValueError("formal MatMul input producer is not node-0074 QuantizeLinear")
    if add_node["node_id"] != "node-0076" or add_node["op_type"] != "QLinearAdd":
        raise ValueError("formal MatMul output consumer is not node-0076 QLinearAdd")
    replay = subop_manifest["node_replays"][node["node_id"]]
    internal_id = "tensor-internal-node-0075-accumulate"
    internal = subop_manifest["internal_tensors"][internal_id]
    if replay["formula"] != "int32_internal_then_requant" or not replay["matches_ort"]:
        raise ValueError("W3 MatMul replay evidence is not valid")
    if not internal["requant_matches_ort"]:
        raise ValueError("W3 MatMul requant evidence is not valid")

    model = onnx.load(model_path, load_external_data=True)
    initializers = {
        item.name: np.ascontiguousarray(
            numpy_helper.to_array(item, base_dir=str(model_path.parent))
        )
        for item in model.graph.initializer
    }
    node_proto = model.graph.node[int(node["graph_index"])]
    ids = node["input_tensor_ids"]
    output_id = node["output_tensor_ids"][0]
    activation_path = golden_root / f"{ids[0]}.npy"
    accumulator_path = subop_root / f"{internal_id}.npy"
    output_path = golden_root / f"{output_id}.npy"
    activation = np.load(activation_path, allow_pickle=False, mmap_mode="r")
    accumulator = np.load(accumulator_path, allow_pickle=False, mmap_mode="r")
    output = np.load(output_path, allow_pickle=False, mmap_mode="r")

    def initializer(index: int) -> np.ndarray:
        return initializers[node_proto.input[index]]

    values = {
        "activation": activation,
        "x_scale": initializer(1),
        "x_zero_point": initializer(2),
        "weight": initializer(3),
        "w_scale": initializer(4),
        "w_zero_point": initializer(5),
        "y_scale": initializer(6),
        "y_zero_point": initializer(7),
        "accumulator": accumulator,
        "output": output,
    }
    tensor_ids = {
        "A": ids[0],
        "x_scale": ids[1],
        "x_zero_point": ids[2],
        "B": ids[3],
        "w_scale": ids[4],
        "w_zero_point": ids[5],
        "y_scale": ids[6],
        "y_zero_point": ids[7],
        "multiplier": "tensor-internal-node-0075-multiplier",
        "P": internal_id,
        "D": output_id,
    }
    quant_proto = model.graph.node[int(quantize_node["graph_index"])]
    quant_input_id = quantize_node["input_tensor_ids"][0]
    quant_input_path = golden_root / f"{quant_input_id}.npy"
    quant_input = np.load(quant_input_path, allow_pickle=False, mmap_mode="r")
    quantize_bundle = QuantizeLinearPhysicalLayout().forward(
        input_tensor=quant_input,
        scale=initializers[quant_proto.input[1]],
        zero_point=initializers[quant_proto.input[2]],
        output_tensor=activation,
        tensor_ids={
            "A": quant_input_id,
            "scale": quantize_node["input_tensor_ids"][1],
            "zero_point": quantize_node["input_tensor_ids"][2],
            "D": ids[0],
        },
    )
    add_case = load_add_case(root, add_node, tensors, model, initializers)
    if ids[7] != add_node["input_tensor_ids"][2]:
        raise ValueError("MatMul output qparams do not match dense Add A qparams")
    dequant_node = nodes["node-0077"]
    if dequant_node["input_tensor_ids"][0] != add_node["output_tensor_ids"][0]:
        raise ValueError("formal Dequantize does not consume dense Add output")
    dequant_proto = model.graph.node[int(dequant_node["graph_index"])]
    final_output_id = dequant_node["output_tensor_ids"][0]
    final_output_path = golden_root / f"{final_output_id}.npy"
    final_output = np.load(final_output_path, allow_pickle=False, mmap_mode="r")
    dequantize_layout = DequantizeLinearPhysicalLayout()
    dequantize_bundle = dequantize_layout.forward(
        input_tensor=add_case["values"]["output"],
        scale=initializers[dequant_proto.input[1]],
        zero_point=initializers[dequant_proto.input[2]],
        output_tensor=final_output,
        tensor_ids={
            "A": dequant_node["input_tensor_ids"][0],
            "scale": dequant_node["input_tensor_ids"][1],
            "zero_point": dequant_node["input_tensor_ids"][2],
            "D": final_output_id,
        },
    )
    dequant_recovered = dequantize_layout.inverse(dequantize_bundle)
    np.testing.assert_array_equal(
        dequant_recovered[dequant_node["input_tensor_ids"][0]],
        add_case["values"]["output"],
    )
    np.testing.assert_array_equal(dequant_recovered[final_output_id], final_output)

    batch = _profile(
        QLinearMatMulBatch16PhysicalLayout(),
        QLinearAddBatch16PhysicalLayout(),
        values,
        tensor_ids,
        add_case,
        quantize_bundle,
        dequantize_bundle,
    )
    ring = _profile(
        QLinearMatMulRing16PhysicalLayout(),
        QLinearAddChannel16PhysicalLayout(),
        values,
        tensor_ids,
        add_case,
        quantize_bundle,
        dequantize_bundle,
    )
    for port in PORTS:
        if (
            batch["comparisons"][port]["inverse_sha256"]
            != ring["comparisons"][port]["inverse_sha256"]
        ):
            raise ValueError(f"MatMul profiles recover different {port}")
    return {
        "schema_version": "0.1",
        "model_sha256": catalog["model_sha256"],
        "node_id": node["node_id"],
        "onnx_name": node["onnx_name"],
        "activation_shape": list(activation.shape),
        "weight_shape": list(values["weight"].shape),
        "accumulator_shape": list(accumulator.shape),
        "output_shape": list(output.shape),
        "input_producer_node_id": quantize_node["node_id"],
        "output_consumer_node_id": add_node["node_id"],
        "output_qparam_chain_exact": True,
        "w3_replay": replay,
        "w3_internal_accumulator": internal,
        "source_files": {
            "model_graph": _source(graph_path, root),
            "subop_manifest": _source(subop_manifest_path, root),
            "quantize_input": _source(quant_input_path, root),
            "activation": _source(activation_path, root),
            "accumulator": _source(accumulator_path, root),
            "output": _source(output_path, root),
            "final_dequantized_output": _source(final_output_path, root),
        },
        "profiles": {"batch": batch, "ring": ring},
        "all_profiles_inverse_bit_exact": True,
        "all_profiles_logical_bit_exact": True,
        "batch_quantize_d_to_matmul_a_exact_alias": True,
        "ring_quantize_d_to_matmul_a_explicit_relayout": True,
        "all_matmul_d_to_dense_add_a_exact_alias": True,
        "dense_bias_broadcast_validated": True,
        "final_dequantize_inverse_bit_exact": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify W4 QLinearMatMul layouts from existing W3 evidence"
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
