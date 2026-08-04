"""Frozen target-JSON schedule for the first ResNet-50 UINT8 MaxPool."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import PipelineError
from .profile28 import GROUP4X7_BATCH_CHANNEL28_PROFILE, GROUP_SAMPLE_COUNTS
from .target_config_audit import (
    MAXPOOL_TEMPLATE,
    validate_maxpool_shape_linkage,
    validate_maxpool_template,
)
from .topology28 import HIGH_RING_OWNERS


NODE_ID = "node-0002"
HWOP_ID = "hwop-0002-00"
ONNX_NAME = "resnetv17_pool0_fwd"
INPUT_TENSOR_ID = "tensor-f6c1a8fb6fd529e8"
OUTPUT_TENSOR_ID = "tensor-8d2f28c80ac24676"
INPUT_SHAPE = (16, 64, 112, 112)
OUTPUT_SHAPE = (16, 64, 56, 56)
LOCAL_CHANNELS = 16
STORAGE_SAMPLES = 3
INPUT_SAMPLE_BYTES = 112 * 112 * LOCAL_CHANNELS
OUTPUT_SAMPLE_BYTES = 56 * 56 * LOCAL_CHANNELS
INPUT_REGION_BYTES = STORAGE_SAMPLES * INPUT_SAMPLE_BYTES
OUTPUT_REGION_OFFSET = INPUT_REGION_BYTES
WAVE_ACTIVE_SLICES = (
    tuple(range(28)),
    tuple(range(28)),
    tuple(slice_id for group_id in range(2) for slice_id in HIGH_RING_OWNERS[group_id]),
)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


@dataclass(frozen=True)
class MaxPoolInstance:
    root: Path
    manifest: dict[str, Any]
    configs: tuple[dict[str, Any], ...]
    config_texts: tuple[str, ...]

    def functional_binding(self) -> dict[str, Any]:
        return {
            "template_name": self.manifest["source_template"]["name"],
            "template_sha256": self.manifest["source_template"]["sha256"],
            "configs": [
                {
                    "wave_index": wave["wave_index"],
                    "active_slices": wave["active_slices"],
                    "config_sha256": wave["config_sha256"],
                    "config_text": text,
                }
                for wave, text in zip(
                    self.manifest["waves"], self.config_texts, strict=True
                )
            ],
        }


def build_maxpool_instance(
    project_root: Path,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    project_root = project_root.resolve()
    template_path = project_root / "ndp-sim-ref" / "jsons" / MAXPOOL_TEMPLATE
    graph_path = project_root / "artifacts" / "w3" / "model_graph.json"
    if not template_path.is_file() or not graph_path.is_file():
        raise PipelineError("MaxPool source template or W3 model graph is missing")
    template = json.loads(template_path.read_text(encoding="utf-8"))
    validate_maxpool_template(template)
    validate_maxpool_shape_linkage(
        template,
        channels=LOCAL_CHANNELS,
        height=INPUT_SHAPE[2],
        width=INPUT_SHAPE[3],
        kernel=3,
        stride=2,
        padding=1,
    )
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    nodes = [item for item in graph["nodes"] if item["node_id"] == NODE_ID]
    if len(nodes) != 1:
        raise PipelineError(f"W3 graph does not contain exactly one {NODE_ID}")
    node = nodes[0]
    expected_node = {
        "op_type": "MaxPool",
        "onnx_name": ONNX_NAME,
        "input_tensor_ids": [INPUT_TENSOR_ID],
        "output_tensor_ids": [OUTPUT_TENSOR_ID],
    }
    if any(node.get(key) != value for key, value in expected_node.items()):
        raise PipelineError("W3 MaxPool node identity differs from the frozen instance")
    attrs = node["attributes"]
    if (
        attrs.get("kernel_shape") != [3, 3]
        or attrs.get("strides") != [2, 2]
        or attrs.get("pads") != [1, 1, 1, 1]
        or int(attrs.get("ceil_mode", -1)) != 0
        or int(attrs.get("storage_order", -1)) != 0
    ):
        raise PipelineError("W3 MaxPool attributes differ from the target template")

    configs: list[dict[str, Any]] = []
    waves: list[dict[str, Any]] = []
    for wave_index, active_slices in enumerate(WAVE_ACTIVE_SLICES):
        config = deepcopy(template)
        input_offset = wave_index * INPUT_SAMPLE_BYTES
        output_offset = OUTPUT_REGION_OFFSET + wave_index * OUTPUT_SAMPLE_BYTES
        config["stream_engine"]["stream0"]["base_addr"] = input_offset
        config["stream_engine"]["stream1"]["base_addr"] = output_offset
        validate_maxpool_template(config)
        validate_maxpool_shape_linkage(
            config,
            channels=LOCAL_CHANNELS,
            height=INPUT_SHAPE[2],
            width=INPUT_SHAPE[3],
            kernel=3,
            stride=2,
            padding=1,
        )
        text = _json_text(config)
        name = f"wave-{wave_index}.json"
        configs.append(config)
        waves.append(
            {
                "wave_index": wave_index,
                "path": name,
                "config_sha256": _sha256_bytes(text.encode("utf-8")),
                "input_offset": input_offset,
                "output_offset": output_offset,
                "active_slices": list(active_slices),
            }
        )
    manifest = {
        "schema_version": "0.1",
        "kind": "resnet50_uint8_maxpool_target_instance",
        "status": "candidate_config_bound_not_target_executed",
        "identity": {
            "node_id": NODE_ID,
            "hwop_id": HWOP_ID,
            "onnx_name": ONNX_NAME,
            "input_tensor_id": INPUT_TENSOR_ID,
            "output_tensor_id": OUTPUT_TENSOR_ID,
            "model_sha256": graph["model_sha256"],
        },
        "source_template": {
            "repository": "ndp-sim-ref",
            "commit": "d4ffc32c9b29a858d83e13706cd837c5549521a4",
            "name": MAXPOOL_TEMPLATE,
            "sha256": _sha256_file(template_path),
        },
        "profile_id": GROUP4X7_BATCH_CHANNEL28_PROFILE,
        "logical": {
            "input_shape": list(INPUT_SHAPE),
            "output_shape": list(OUTPUT_SHAPE),
            "dtype": "uint8",
            "kernel_shape": [3, 3],
            "strides": [2, 2],
            "pads": [1, 1, 1, 1],
            "dilations": [1, 1],
            "ceil_mode": 0,
            "storage_order": 0,
            "spatial_padding_value": 0,
        },
        "physical": {
            "slice_count": 28,
            "local_channels": LOCAL_CHANNELS,
            "storage_samples_per_slice": STORAGE_SAMPLES,
            "group_sample_counts": list(GROUP_SAMPLE_COUNTS),
            "input_physical_shape": [3, 112, 112, 16],
            "output_physical_shape": [3, 56, 56, 16],
            "input_sample_bytes": INPUT_SAMPLE_BYTES,
            "output_sample_bytes": OUTPUT_SAMPLE_BYTES,
            "input_region_bytes": INPUT_REGION_BYTES,
            "output_region_offset": OUTPUT_REGION_OFFSET,
        },
        "waves": waves,
        "limitations": [
            "The three JSONs reuse one single-sample target program at three local DRAM offsets.",
            "A target controller must load/start/wait the listed active slices for each wave.",
            "This manifest does not itself prove full target simulator or hardware execution.",
        ],
    }
    return manifest, tuple(configs)


def write_maxpool_instance(project_root: Path, output_root: Path) -> MaxPoolInstance:
    output_root = output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        raise PipelineError(f"refusing to overwrite non-empty MaxPool config directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest, configs = build_maxpool_instance(project_root)
    texts = tuple(_json_text(item) for item in configs)
    for wave, text in zip(manifest["waves"], texts, strict=True):
        (output_root / wave["path"]).write_bytes(text.encode("utf-8"))
    (output_root / "manifest.json").write_bytes(_json_text(manifest).encode("utf-8"))
    return load_maxpool_instance(project_root, output_root)


def load_maxpool_instance(project_root: Path, instance_root: Path) -> MaxPoolInstance:
    project_root = project_root.resolve()
    instance_root = instance_root.resolve()
    manifest_path = instance_root / "manifest.json"
    if not manifest_path.is_file():
        raise PipelineError(f"MaxPool manifest is missing: {manifest_path}")
    checked_manifest, checked_configs = build_maxpool_instance(project_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest != checked_manifest:
        raise PipelineError("checked-in MaxPool manifest differs from the frozen source instance")
    expected_names = {"manifest.json", *(item["path"] for item in manifest["waves"])}
    actual_names = {item.name for item in instance_root.iterdir() if item.is_file()}
    if actual_names - expected_names:
        raise PipelineError("MaxPool config directory contains unexpected files")
    texts: list[str] = []
    configs: list[dict[str, Any]] = []
    for wave, expected_config in zip(manifest["waves"], checked_configs, strict=True):
        path = instance_root / wave["path"]
        if not path.is_file():
            raise PipelineError(f"MaxPool wave config is missing: {path}")
        payload = path.read_bytes()
        if _sha256_bytes(payload) != wave["config_sha256"]:
            raise PipelineError(f"MaxPool wave config hash differs: {path.name}")
        text = payload.decode("utf-8")
        config = json.loads(text)
        if config != expected_config:
            raise PipelineError(f"MaxPool wave config semantics differ: {path.name}")
        validate_maxpool_shape_linkage(
            config,
            channels=LOCAL_CHANNELS,
            height=112,
            width=112,
            kernel=3,
            stride=2,
            padding=1,
        )
        texts.append(text)
        configs.append(config)
    return MaxPoolInstance(instance_root, manifest, tuple(configs), tuple(texts))
