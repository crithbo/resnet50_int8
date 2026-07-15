from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from .conv28_layout import GROUP4X7_BATCH_CHANNEL28_PROFILE, QLinearConvPhysicalLayout
from .typed_config_parameters import validate_typed_config_parameter_contract
from .w5_conv_preflight import (
    ACCUMULATE_HW_OP_ID,
    REQUANT_HW_OP_ID,
    SELECTED_NODE_ID,
    _initializer,
    _initializer_values,
    _load_json,
    _load_npy,
    _port,
    _record_by_hw_op,
    validate_w5_first_conv_preflight,
)


FREEZE_SCHEMA_VERSION = "0.1"
FREEZE_CONTRACT_TYPE = "conv_1x1_manual_hardware_handoff"
INPUT_PORTS = {
    "A",
    "B",
    "bias",
    "w_scale",
    "w_zero_point",
    "x_scale",
    "x_zero_point",
    "y_scale",
    "y_zero_point",
}
OUTPUT_PORTS = {"P", "D"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_bytes(path: Path, payload: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": path.as_posix(),
        "size_bytes": len(payload),
        "sha256": _sha256(payload),
    }


def _write_relative(root: Path, relative: str, payload: bytes) -> dict[str, Any]:
    record = _write_bytes(root / relative, payload)
    record["path"] = relative
    return record


def _copy_relative(root: Path, source: Path, relative: str) -> dict[str, Any]:
    if not source.is_file():
        raise FileNotFoundError(f"frozen handoff source is missing: {source}")
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return {
        "path": relative,
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination.read_bytes()),
    }


def _selected_bundle(project_root: Path):
    typed = _load_json(project_root / "contracts" / "typed_config_parameter_contract.json")
    validate_typed_config_parameter_contract(typed)
    accumulate = _record_by_hw_op(typed, ACCUMULATE_HW_OP_ID)
    requant = _record_by_hw_op(typed, REQUANT_HW_OP_ID)
    runtime_root = project_root / "artifacts" / "w3" / "golden_batch16"
    subop_root = project_root / "artifacts" / "w3" / "subop_batch16"
    runtime_manifest = _load_json(runtime_root / "manifest.json")
    subop_manifest = _load_json(subop_root / "manifest.json")
    initializers = _initializer_values(
        project_root / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"
    )
    descriptors = {
        "A": _port(accumulate, "inputs", "x"),
        "B": _port(accumulate, "inputs", "w"),
        "bias": _port(accumulate, "inputs", "bias"),
        "w_zero_point": _port(accumulate, "inputs", "w_zero_point"),
        "x_zero_point": _port(accumulate, "inputs", "x_zero_point"),
        "x_scale": _port(requant, "inputs", "x_scale"),
        "w_scale": _port(requant, "inputs", "w_scale"),
        "y_scale": _port(requant, "inputs", "y_scale"),
        "y_zero_point": _port(requant, "inputs", "y_zero_point"),
        "P": requant["ports"]["inputs"][0],
        "D": requant["ports"]["outputs"][0],
    }
    values = {
        "A": _load_npy(
            runtime_root,
            runtime_manifest,
            runtime_manifest["tensors"][descriptors["A"]["tensor_id"]],
        ),
        "P": _load_npy(
            subop_root,
            subop_manifest,
            subop_manifest["internal_tensors"][descriptors["P"]["tensor_id"]],
        ),
        "D": _load_npy(
            runtime_root,
            runtime_manifest,
            runtime_manifest["tensors"][descriptors["D"]["tensor_id"]],
        ),
    }
    for port in INPUT_PORTS - {"A"}:
        values[port] = _initializer(
            initializers,
            runtime_manifest,
            descriptors[port],
        )
    attributes = accumulate["logical_geometry"]["attributes"]
    layout = QLinearConvPhysicalLayout(
        profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE
    )
    bundle = layout.forward(
        activation=values["A"],
        weight=values["B"],
        bias=values["bias"],
        w_scale=values["w_scale"],
        w_zero_point=values["w_zero_point"],
        x_scale=values["x_scale"],
        x_zero_point=values["x_zero_point"],
        y_scale=values["y_scale"],
        y_zero_point=values["y_zero_point"],
        accumulator=values["P"],
        output=values["D"],
        strides=tuple(attributes["strides"]),
        pads=tuple(attributes["pads"]),
        dilations=tuple(attributes["dilations"]),
        group=int(attributes["group"]),
        tensor_ids={name: descriptor["tensor_id"] for name, descriptor in descriptors.items()},
    )
    layout.validate(bundle)
    return values, bundle


def export_hardware_freeze(project_root: Path, output_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    preflight_path = project_root / "artifacts" / "w5" / "hwop-0004-00" / "preflight.json"
    preflight_payload = preflight_path.read_bytes()
    preflight = json.loads(preflight_payload)
    validate_w5_first_conv_preflight(preflight)
    if preflight["gate_state"].get("single_operator_manual_hardware_handoff_ready") is not True:
        raise ValueError("W5 report does not authorize the manual hardware handoff")

    values, bundle = _selected_bundle(project_root)
    files: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    for region in bundle.regions:
        relative = f"physical/{region.port}/slice-{region.slice_id:02d}.bin"
        file_record = _write_relative(
            output_root,
            relative,
            bundle.read(region.port, region.slice_id),
        )
        files.append(file_record)
        regions.append(
            {
                "port": region.port,
                "slice_id": region.slice_id,
                "role": "load_input" if region.port in INPUT_PORTS else "golden_output",
                "base_address": region.base_address,
                "base_address_hex": f"0x{region.base_address:08x}",
                "payload_bytes": region.payload_bytes,
                "size_bytes": region.size_bytes,
                "physical_shape": list(region.physical_shape),
                "dtype": bundle.plan.port(region.port).dtype,
                "sample_start": region.sample_start,
                "sample_count": region.sample_count,
                "logical_start": region.logical_start,
                "logical_count": region.logical_count,
                "file": file_record,
            }
        )

    requant_manifest = _load_json(project_root / "conv_1x1_requant_real" / "manifest.json")
    for slice_id in range(bundle.plan.geometry.slice_count):
        slice_base = bundle.plan.geometry.slice_base(slice_id)
        for local_half, offset in enumerate((904400, 979664)):
            regions.append(
                {
                    "port": f"staged_D_{local_half}",
                    "slice_id": slice_id,
                    "role": "hardware_output",
                    "base_address": slice_base + offset,
                    "base_address_hex": f"0x{slice_base + offset:08x}",
                    "payload_bytes": requant_manifest["physical_layout"]["staged_half_bytes"],
                    "size_bytes": requant_manifest["physical_layout"]["staged_half_bytes"],
                    "physical_shape": [3, 56, 56, 8],
                    "dtype": "uint8",
                }
            )

    canonical_golden: dict[str, Any] = {}
    for port in ("P", "D"):
        value = np.ascontiguousarray(values[port])
        record = _write_relative(
            output_root,
            f"golden/canonical_{port}.bin",
            value.tobytes(order="C"),
        )
        record.update({"dtype": str(value.dtype), "shape": list(value.shape)})
        canonical_golden[port] = record
        files.append(record)

    config_records = []
    for source, relative in [
        (project_root / "conv_1x1_real.json", "configs/conv_1x1_real.json"),
        (
            project_root / "conv_1x1_requant_real" / "manifest.json",
            "configs/requant/manifest.json",
        ),
        *[
            (
                project_root / "conv_1x1_requant_real" / f"shard-{index:02d}.json",
                f"configs/requant/shard-{index:02d}.json",
            )
            for index in range(8)
        ],
    ]:
        record = _copy_relative(output_root, source, relative)
        config_records.append(record)
        files.append(record)

    bitstream_records = []
    bitstream_sources = [
        (
            project_root
            / "artifacts"
            / "w5"
            / "conv_1x1_real"
            / "encode_a"
            / f"conv_1x1_real_bitstream_{width}.bin",
            f"bitstreams/accumulate/conv_1x1_real_bitstream_{width}.bin",
        )
        for width in ("128b", "64b")
    ]
    for shard_index in range(8):
        bitstream_sources.extend(
            (
                project_root
                / "artifacts"
                / "w5"
                / "conv_1x1_requant_real"
                / f"shard-{shard_index:02d}"
                / f"shard-{shard_index:02d}_bitstream_{width}.bin",
                f"bitstreams/requant/shard-{shard_index:02d}_bitstream_{width}.bin",
            )
            for width in ("128b", "64b")
        )
    for source, relative in bitstream_sources:
        record = _copy_relative(output_root, source, relative)
        bitstream_records.append(record)
        files.append(record)

    address_payload = (
        json.dumps(
            {"schema_version": "0.1", "regions": regions},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    address_table = _write_relative(output_root, "address_table.json", address_payload)
    files.append(address_table)

    comparison_tool_path = project_root / "tools" / "compare_conv_1x1_hardware_dump.py"
    comparison_tool = {
        "path": "tools/compare_conv_1x1_hardware_dump.py",
        "sha256": _sha256(comparison_tool_path.read_bytes()),
        "dump_convention": "<dump-root>/P/slice-XX.bin and <dump-root>/D/slice-XX.bin",
    }
    manifest = {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "contract_type": FREEZE_CONTRACT_TYPE,
        "status": "manual_hardware_handoff_ready",
        "identity": {
            "node_id": SELECTED_NODE_ID,
            "hw_op_ids": [ACCUMULATE_HW_OP_ID, REQUANT_HW_OP_ID],
            "preflight_sha256": _sha256(preflight_payload),
            "ndp_source_commit": preflight["ndp_conv_simulator_first_coordinate"]["source_commit"],
            "request_schema": preflight["ndp_target_config_comparison"]["request_schema"],
        },
        "layout": {
            "profile_id": bundle.plan.profile_id,
            "slice_count": bundle.plan.geometry.slice_count,
            "per_slice_used_bytes": bundle.plan.per_slice_used_bytes,
            "staged_d_offsets": [904400, 979664],
            "staged_half_bytes": 75264,
        },
        "configs": config_records,
        "bitstreams": bitstream_records,
        "address_table": address_table,
        "canonical_golden": canonical_golden,
        "comparison_tool": comparison_tool,
        "files": sorted(files, key=lambda item: item["path"]),
    }
    freeze_payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["freeze_id"] = _sha256(freeze_payload)
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_bytes(output_root / "manifest.json", manifest_payload)
    return manifest


def _inverse_port(
    manifest: dict[str, Any],
    dump_root: Path,
    port: str,
) -> np.ndarray:
    golden = manifest["canonical_golden"][port]
    dtype = np.dtype(golden["dtype"])
    shape = tuple(int(item) for item in golden["shape"])
    result = np.zeros(shape, dtype=dtype)
    filled = np.zeros(shape, dtype=np.bool_)
    address_table = json.loads(
        (Path(manifest["_freeze_root"]) / manifest["address_table"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    for region in address_table["regions"]:
        if region["port"] != port:
            continue
        path = dump_root / port / f"slice-{int(region['slice_id']):02d}.bin"
        payload = path.read_bytes()
        if len(payload) != int(region["size_bytes"]):
            raise ValueError(f"hardware dump size differs: {path}")
        local = np.frombuffer(
            payload[: int(region["payload_bytes"])], dtype=dtype
        ).reshape(tuple(int(item) for item in region["physical_shape"]))
        n_start = int(region["sample_start"])
        n_count = int(region["sample_count"])
        k_start = int(region["logical_start"])
        k_count = int(region["logical_count"])
        logical = local[:n_count, ..., :k_count].transpose(0, 3, 1, 2)
        target = np.s_[
            n_start : n_start + n_count,
            k_start : k_start + k_count,
            :,
            :,
        ]
        if np.any(filled[target]):
            raise ValueError(f"hardware dump overlaps canonical {port}")
        result[target] = logical
        filled[target] = True
    if not np.all(filled):
        raise ValueError(f"hardware dump does not cover canonical {port}")
    return result


def compare_hardware_dump(freeze_root: Path, dump_root: Path) -> dict[str, Any]:
    freeze_root = freeze_root.resolve()
    manifest = json.loads((freeze_root / "manifest.json").read_text(encoding="utf-8"))
    manifest["_freeze_root"] = str(freeze_root)
    comparisons = {}
    for port in ("P", "D"):
        actual = np.ascontiguousarray(_inverse_port(manifest, dump_root.resolve(), port))
        golden_record = manifest["canonical_golden"][port]
        golden_payload = (freeze_root / golden_record["path"]).read_bytes()
        if _sha256(golden_payload) != golden_record["sha256"]:
            raise ValueError(f"frozen canonical {port} hash differs")
        golden = np.frombuffer(golden_payload, dtype=np.dtype(golden_record["dtype"])).reshape(
            tuple(int(item) for item in golden_record["shape"])
        )
        mismatches = np.argwhere(actual != golden)
        first = None
        if mismatches.size:
            coordinate = tuple(int(item) for item in mismatches[0])
            first = {
                "coordinate": list(coordinate),
                "actual": int(actual[coordinate]),
                "golden": int(golden[coordinate]),
            }
        comparisons[port] = {
            "element_count": int(actual.size),
            "mismatch_count": int(len(mismatches)),
            "actual_sha256": _sha256(actual.tobytes(order="C")),
            "golden_sha256": golden_record["sha256"],
            "first_mismatch": first,
        }
    return {
        "status": "passed"
        if all(item["mismatch_count"] == 0 for item in comparisons.values())
        else "mismatch",
        "freeze_id": manifest["freeze_id"],
        "comparisons": comparisons,
    }


__all__ = [
    "FREEZE_CONTRACT_TYPE",
    "FREEZE_SCHEMA_VERSION",
    "compare_hardware_dump",
    "export_hardware_freeze",
]
