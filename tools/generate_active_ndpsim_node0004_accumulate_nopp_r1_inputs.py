"""Generate the node-0004 wave-0 zero-ping-pong smoke revision.

The failed ``node0004_accumulate_wave0`` package remains immutable evidence.
This revision derives a new static JSON from the same frozen source config,
removes the unconsumed B' branch, disables every ping-pong selector, and
regenerates W3-backed A/B/C/D files without reading the failed package.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import numpy as np

from generate_active_ndpsim_node0004_accumulate_smoke_inputs import (
    AccumulateSmokeInputError,
    SEMANTIC_CONTRACT_REL,
    SOURCE_CONFIG_REL,
    SOURCE_CONFIG_SHA256,
    _assert_fresh_directory,
    _assert_fresh_path,
    _load_w3_bundle,
    _read_json,
    _sha256_file,
    _write_json,
    _write_matrix,
)


REVISION = "nopp_r1"
OP_TYPE = f"node0004_accumulate_wave0_{REVISION}"
ACTIVE_CONFIG_REL = Path(f"ndp-sim/jsons/{OP_TYPE}.json")
GRAPH_REL = Path(
    "ndp-sim/generate_python_golden/model_execplan/op_json/"
    f"{OP_TYPE}_graph.json"
)
DATA_ROOT_REL = Path(
    "ndp-sim/generate_python_golden/single_op_data/"
    f"install_{OP_TYPE}"
)
SLICE_COUNT = 28
WAVE_INDEX = 0


def _derive_zero_pingpong_config(source: dict[str, Any]) -> dict[str, Any]:
    config = copy.deepcopy(source)

    streams = config.get("stream_engine")
    if not isinstance(streams, dict):
        raise AccumulateSmokeInputError("source config has no stream_engine object")
    expected_streams = {
        "stream0": ("A", "read"),
        "stream1": ("B", "read"),
        "stream2": ("B'", "read"),
        "stream3": ("C", "read"),
        "stream4": ("D", "write"),
    }
    observed_streams = {
        key: (value.get("target"), value.get("mode"))
        for key, value in streams.items()
    }
    if observed_streams != expected_streams:
        raise AccumulateSmokeInputError(
            f"source stream topology differs: {observed_streams}"
        )

    # READ_STREAM2 only filled buffer3 for SA inport1 ping-pong.  Once the SA
    # consumes only source 0, keeping this branch would fill an unused buffer
    # and eventually backpressure the shared loop graph.
    del streams["stream2"]
    for stream in streams.values():
        stream["ping_pong"] = 0
        stream["pingpong_last_index"] = None

    groups = config.get("buffer_loop_configs")
    if not isinstance(groups, dict) or groups.get("GROUP2", {}).get("target") != "B'":
        raise AccumulateSmokeInputError("source GROUP2 is not the B' branch")
    del groups["GROUP2"]

    special = config.get("special_array")
    if not isinstance(special, dict) or special.get("mode") != "gemm":
        raise AccumulateSmokeInputError("source special_array is not GEMM")
    for name in ("inport0", "inport1", "inport2"):
        inport = special.get(name)
        if not isinstance(inport, dict) or inport.get("enable") != 1:
            raise AccumulateSmokeInputError(f"source {name} is not enabled")
        inport["pingpong_en"] = 0
        inport["pingpong_last_index"] = None
        inport["nbr_enable"] = 0

    # The native encoder maps JSON row->1, while the active RTL defines bit 1
    # as col-major.  Native GEMM examples use JSON col (encoded 0 / row-major).
    outport = special.get("outport")
    if not isinstance(outport, dict):
        raise AccumulateSmokeInputError("source special_array has no outport")
    outport["mode"] = "col"

    buffers = config.get("buffer_config")
    if not isinstance(buffers, dict):
        raise AccumulateSmokeInputError("source config has no buffer_config")
    for name in ("buffer0", "buffer1", "buffer2", "buffer3", "buffer4", "buffer5"):
        buffer = buffers.get(name)
        if not isinstance(buffer, dict):
            raise AccumulateSmokeInputError(f"missing {name}")
        buffer["nbr_enable"] = 0
        buffer["buffer_nbr_cnt"] = 0

    if any(stream.get("ping_pong") for stream in streams.values()):
        raise AssertionError("derived stream ping-pong is still enabled")
    if any(
        special[name].get("pingpong_en")
        for name in ("inport0", "inport1", "inport2")
    ):
        raise AssertionError("derived SA ping-pong is still enabled")
    if {value.get("target") for value in streams.values()} != {"A", "B", "C", "D"}:
        raise AssertionError("derived stream topology is not A/B/C/D")
    if {value.get("target") for value in groups.values()} != {"A", "B", "C", "D"}:
        raise AssertionError("derived buffer-loop topology is not A/B/C/D")
    return config


def generate(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    forbidden = (root / "ndp-sim-ref").resolve()
    old_w5 = (root / "artifacts" / "w5").resolve()
    failed_package = (
        root / "ndp-sim/model_execplan/output/node0004_accumulate_wave0_graph"
    ).resolve()
    source_config = (root / SOURCE_CONFIG_REL).resolve()
    active_config = (root / ACTIVE_CONFIG_REL).resolve()
    graph_path = (root / GRAPH_REL).resolve()
    data_root = (root / DATA_ROOT_REL).resolve()

    for path in (source_config, root / SEMANTIC_CONTRACT_REL):
        resolved = path.resolve()
        if resolved == forbidden or forbidden in resolved.parents:
            raise AccumulateSmokeInputError(f"forbidden ndp-sim-ref source: {resolved}")
        if resolved == old_w5 or old_w5 in resolved.parents:
            raise AccumulateSmokeInputError(f"forbidden previous W5 source: {resolved}")
        if resolved == failed_package or failed_package in resolved.parents:
            raise AccumulateSmokeInputError(f"forbidden failed-package source: {resolved}")
        if not resolved.is_file():
            raise AccumulateSmokeInputError(f"missing source: {resolved}")
    if _sha256_file(source_config) != SOURCE_CONFIG_SHA256:
        raise AccumulateSmokeInputError("frozen node-0004 source config identity differs")

    _assert_fresh_path(active_config)
    _assert_fresh_path(graph_path)
    _assert_fresh_directory(data_root)

    derived_config = _derive_zero_pingpong_config(_read_json(source_config))
    _write_json(active_config, derived_config)

    spec, bundle, runtime_manifest, subop_manifest = _load_w3_bundle(root)
    if bundle.plan.storage_sample_count != 3:
        raise AccumulateSmokeInputError("expected three local storage sample slots")

    activation_slot_bytes = bundle.plan.port("A").payload_bytes // 3
    accumulator_slot_bytes = bundle.plan.port("P").payload_bytes // 3
    weight_bytes = bundle.plan.port("B").payload_bytes
    bias_bytes = bundle.plan.port("bias").payload_bytes
    if (activation_slot_bytes, accumulator_slot_bytes, weight_bytes, bias_bytes) != (
        200704,
        200704,
        1024,
        64,
    ):
        raise AccumulateSmokeInputError("node-0004 physical tensor sizes differ")

    graph = {
        "params": {
            "used_slices": SLICE_COUNT,
            "node_id": spec.node_id,
            "wave_index": WAVE_INDEX,
            "revision": REVISION,
            "source": "W3 golden_batch16 + subop_batch16 through signed-A Conv28 layout",
            "logical_samples": [0, 3, 6, 8, 10, 12, 14],
            "execution_scope": "single-stage zero-ping-pong smoke",
        },
        "used_slices": SLICE_COUNT,
        "operators": [
            {
                "id": "op0",
                "type": OP_TYPE,
                "used_slices": "0b" + "1" * SLICE_COUNT,
                "inputs": {
                    "A": {
                        "shape": [1, 1, weight_bytes],
                        "dtype": "int8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "B": {
                        "shape": [1, 1, activation_slot_bytes],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "C": {
                        "shape": [1, 1, bias_bytes // 4],
                        "dtype": "int32",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                },
                "output": {
                    "shape": [1, 1, accumulator_slot_bytes // 4],
                    "dtype": "int32",
                    "bank_interleave": 1,
                    "remapping": None,
                },
            }
        ],
    }
    _write_json(graph_path, graph)

    records: list[dict[str, Any]] = []
    logical_samples = (0, 3, 6, 8, 10, 12, 14)
    for slice_id in range(SLICE_COUNT):
        region = bundle.region("A", slice_id)
        if region.group_id is None or not 0 <= region.group_id < len(logical_samples):
            raise AccumulateSmokeInputError(f"slice {slice_id} has no wave-0 group")
        slice_root = data_root / "op0" / f"slice{slice_id:02d}"
        slice_root.mkdir(parents=True, exist_ok=True)
        matrices = {
            "A": _write_matrix(
                slice_root, "A", bundle.read("B", slice_id), np.dtype("int8")
            ),
            "B": _write_matrix(
                slice_root,
                "B",
                bundle.read("A", slice_id)[:activation_slot_bytes],
                np.dtype("uint8"),
            ),
            "C": _write_matrix(
                slice_root, "C", bundle.read("bias", slice_id), np.dtype("<i4")
            ),
            "D": _write_matrix(
                slice_root,
                "D",
                bundle.read("P", slice_id)[:accumulator_slot_bytes],
                np.dtype("<i4"),
            ),
        }
        records.append(
            {
                "slice_id": slice_id,
                "group_id": region.group_id,
                "owner_step": region.owner_step,
                "logical_sample": logical_samples[region.group_id],
                "local_sample_slot": 0,
                "matrices": matrices,
            }
        )

    generated_tensor_files = sorted(path for path in data_root.rglob("*") if path.is_file())
    if len(generated_tensor_files) != SLICE_COUNT * 4 * 3:
        raise AccumulateSmokeInputError(
            f"expected {SLICE_COUNT * 12} tensor files, found {len(generated_tensor_files)}"
        )

    source_paths = {
        "frozen_failed_revision_config_baseline": source_config,
        "derived_zero_pingpong_config": active_config,
        "semantic_contract": root / SEMANTIC_CONTRACT_REL,
        "runtime_manifest": root / "artifacts/w3/golden_batch16/manifest.json",
        "subop_manifest": root / "artifacts/w3/subop_batch16/manifest.json",
        "reference_model": root / "artifacts/reference_model/resnet50-v1-12-int8.onnx",
    }
    manifest = {
        "format_version": 1,
        "kind": "active_ndpsim_node0004_accumulate_wave0_zero_pingpong_inputs",
        "status": "generated_from_W3_for_zero_pingpong_single_stage_smoke",
        "revision": REVISION,
        "prohibited_sources": [
            "ndp-sim-ref",
            "artifacts/w5 previous packages",
            "node0004_accumulate_wave0_graph failed package",
        ],
        "configuration_policy": (
            "derive a new revision from the frozen config; remove B-prime; "
            "disable all ping-pong and neighbor inputs; use native GEMM col label"
        ),
        "node_id": spec.node_id,
        "operator_type": OP_TYPE,
        "wave_index": WAVE_INDEX,
        "used_slices": SLICE_COUNT,
        "logical_samples": list(logical_samples),
        "physical_sizes_per_slice": {
            "config_A_weight_int8": weight_bytes,
            "config_B_activation_uint8": activation_slot_bytes,
            "config_C_bias_int32": bias_bytes,
            "config_D_accumulator_int32": accumulator_slot_bytes,
        },
        "graph": {
            "path": graph_path.relative_to(root).as_posix(),
            "bytes": graph_path.stat().st_size,
            "sha256": _sha256_file(graph_path),
        },
        "sources": {
            label: {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for label, path in source_paths.items()
        },
        "w3_manifest_identities": {
            "runtime_manifest_schema": runtime_manifest.get("schema_version"),
            "subop_manifest_schema": subop_manifest.get("schema_version"),
        },
        "records": records,
        "generated_tensor_file_count": len(generated_tensor_files),
        "generated_tensor_bytes": sum(path.stat().st_size for path in generated_tensor_files),
    }
    manifest_path = data_root / f"{OP_TYPE}_input_manifest.json"
    _write_json(manifest_path, manifest)
    return {
        "active_config": str(active_config),
        "active_config_sha256": _sha256_file(active_config),
        "graph": str(graph_path),
        "data_root": str(data_root),
        "manifest": str(manifest_path),
        "slice_count": SLICE_COUNT,
        "tensor_files": len(generated_tensor_files),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    return parser.parse_args()


def main() -> int:
    result = generate(parse_args().project_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
