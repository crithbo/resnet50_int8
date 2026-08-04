from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.generate_active_ndpsim_node0004_accumulate_smoke_inputs import (
    _load_w3_bundle,
)

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .int8_sa_dot_product_adjudication import stock_rtl_sa_chunk
from .operator_config_validator import OperatorConfigValidator


TEST_ID = "r5_conv_node0004_serialized_one_product_local_e2_v1"
NODE_ID = "node-0004"
REQUEST_ID = "r5:hwop-0004-00"
REQUEST_SHA256 = (
    "e27e10169168f3889df4c03bf15cb21de074abf3f3767dc4bee288425165874b"
)
SOURCE_CONFIG_REL = Path(
    "configs/native_ndp_sim/"
    "node0004_accumulate_wave0_nopp_r1_strict_v1/config.json"
)
SOURCE_CONFIG_SHA256 = (
    "2fe3fc865a6bfb8f37d0c34afe2adb730de35568d02892d9705895b0261b9ae8"
)
LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
LOWERING_SHA256 = (
    "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
)
CONFIG_ROOT_REL = Path(
    "configs/native_ndp_sim/"
    "r5_conv_node0004_serialized_one_product_local_e2_v1"
)
ARTIFACT_ROOT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5_conv_node0004_serialized_one_product_local_e2_v1"
)
GRAPH_REL = ARTIFACT_ROOT_REL / "graph.json"
PHYSICAL_REL = ARTIFACT_ROOT_REL / "physical_assets.npz"
PHYSICAL_MANIFEST_REL = ARTIFACT_ROOT_REL / "physical_assets_manifest.json"
PATCHSET_REL = Path(
    "contracts/operator_config/"
    "r5_conv_node0004_serialized_one_product_patchset_v1.json"
)
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "r5_conv_node0004_serialized_one_product_local_e2_v1.json"
)
FINAL_EXECPLAN_REL = ARTIFACT_ROOT_REL / "execplan_final"
W3_ACCUMULATOR_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0004-accumulate.npy"
)
W3_ACCUMULATOR_SHA256 = (
    "32de6ea94086ce09da37b4f3c5b12ee51275c7b0f6d7b4a9875b0b9900ca25ac"
)

WAVE_SAMPLES = (
    (0, 3, 6, 8, 10, 12, 14),
    (1, 4, 7, 9, 11, 13, 15),
    (2, 5),
)
WAVE_SLICE_COUNTS = (28, 28, 8)
SERIALIZED_WEIGHT_BYTES = 4_096
SERIALIZED_ACTIVATION_BYTES = 802_816
BIAS_BYTES = 64
ACCUMULATOR_BYTES = 200_704
OP_ALLOCATION_BYTES = (
    SERIALIZED_WEIGHT_BYTES
    + SERIALIZED_ACTIVATION_BYTES
    + BIAS_BYTES
    + ACCUMULATOR_BYTES
)


class SerializedConvE2Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SerializedConvE2Error(f"cannot parse JSON: {path}") from error
    if not isinstance(value, dict):
        raise SerializedConvE2Error(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _mask(count: int) -> str:
    return "0b" + "0" * (28 - count) + "1" * count


def operator_type(wave: int) -> str:
    return f"resnet50_conv_node0004_serialized_wave{wave}"


def op_id(wave: int) -> str:
    return f"serialized_w{wave}"


def _stream(config: Mapping[str, Any], target: str) -> dict[str, Any]:
    streams = config.get("stream_engine")
    if not isinstance(streams, Mapping):
        raise SerializedConvE2Error("stream_engine is missing")
    matches = [
        value
        for value in streams.values()
        if isinstance(value, dict) and value.get("target") == target
    ]
    if len(matches) != 1:
        raise SerializedConvE2Error(f"requires exactly one {target} stream")
    return matches[0]


def _typed_request(root: Path) -> dict[str, Any]:
    if sha256_file(root / LOWERING_REL) != LOWERING_SHA256:
        raise SerializedConvE2Error("typed lowering bundle identity differs")
    lowering = _load(root / LOWERING_REL)
    matches = [
        item
        for item in lowering.get("requests", [])
        if isinstance(item, dict) and item.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1:
        raise SerializedConvE2Error("node0004 typed request is not unique")
    request = matches[0]
    if (
        request.get("request_sha256") != REQUEST_SHA256
        or request.get("identity", {}).get("node_id") != NODE_ID
        or request.get("identity", {}).get("hw_op_type")
        != "ConvInt32Accumulate"
    ):
        raise SerializedConvE2Error("node0004 typed request identity differs")
    return request


def build_config(root: Path, wave: int) -> dict[str, Any]:
    source_path = root / SOURCE_CONFIG_REL
    if sha256_file(source_path) != SOURCE_CONFIG_SHA256:
        raise SerializedConvE2Error("structural seed config identity differs")
    if wave not in range(3):
        raise SerializedConvE2Error(f"invalid wave: {wave}")
    config = deepcopy(_load(source_path))

    # The seed owns topology only.  These fields are re-derived from the
    # serialized K=64 schedule: PE=outer*4+inner and 64 four-byte groups.
    for name in ("LC4", "LC6"):
        config["dram_loop_configs"][name]["end"] = 16
    _stream(config, "B")["dim_stride"] = [32, 2_048, 14_336]

    offsets = {
        "A": 0,
        "B": SERIALIZED_WEIGHT_BYTES,
        "C": SERIALIZED_WEIGHT_BYTES + SERIALIZED_ACTIVATION_BYTES,
        "D": SERIALIZED_WEIGHT_BYTES
        + SERIALIZED_ACTIVATION_BYTES
        + BIAS_BYTES,
    }
    op_base = wave * OP_ALLOCATION_BYTES
    for target, offset in offsets.items():
        _stream(config, target)["base_addr"] = f"0x{op_base + offset:08X}"

    report = OperatorConfigValidator().validate(
        config,
        source=f"{TEST_ID}#wave{wave}",
        development_mode=True,
        expected_sa_transpose=False,
    )
    if not report.valid:
        first = report.issues[0]
        raise SerializedConvE2Error(
            f"serialized config is invalid: {first.code} "
            f"at {first.path}: {first.message}"
        )
    return config


def graph_spec() -> dict[str, Any]:
    operators: list[dict[str, Any]] = []
    for wave, count in enumerate(WAVE_SLICE_COUNTS):
        operators.append(
            {
                "id": op_id(wave),
                "type": operator_type(wave),
                "used_slices": _mask(count),
                "inputs": {
                    "A": {
                        "shape": [1, 1, SERIALIZED_WEIGHT_BYTES],
                        "dtype": "int8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "B": {
                        "shape": [1, 1, SERIALIZED_ACTIVATION_BYTES],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                    "C": {
                        "shape": [1, 1, BIAS_BYTES // 4],
                        "dtype": "int32",
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    },
                },
                "output": {
                    "shape": [1, 1, ACCUMULATOR_BYTES // 4],
                    "dtype": "int32",
                    "bank_interleave": 1,
                    "remapping": None,
                },
            }
        )
    return {
        "params": {
            "test_id": TEST_ID,
            "node_id": NODE_ID,
            "request_id": REQUEST_ID,
            "wave_count": 3,
            "occurrence_encoding": (
                "one original K scalar per four-byte SA word; other lanes zero"
            ),
        },
        "used_slices": _mask(28),
        "operators": operators,
    }


def _expand_group_lane(values: np.ndarray, *, group_axis: int) -> np.ndarray:
    if values.shape[-1] != 4:
        raise SerializedConvE2Error("source lane axis must have width four")
    normalized_axis = group_axis % values.ndim
    if normalized_axis == values.ndim - 1:
        raise SerializedConvE2Error("group axis cannot be the lane axis")
    moved = np.moveaxis(values, normalized_axis, -2)
    output = np.zeros(
        (*moved.shape[:-2], moved.shape[-2] * 4, 4), dtype=values.dtype
    )
    for lane in range(4):
        output[..., lane::4, lane] = moved[..., :, lane]
    return np.moveaxis(output, -2, normalized_axis)


def _schedule(bundle: Any) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    for wave, (samples, count) in enumerate(
        zip(WAVE_SAMPLES, WAVE_SLICE_COUNTS, strict=True)
    ):
        for slice_id in range(count):
            region = bundle.region("A", slice_id)
            if region.group_id is None or region.owner_step is None:
                raise SerializedConvE2Error("Conv28 schedule owner is missing")
            result.append(
                {
                    "wave": wave,
                    "slice": slice_id,
                    "sample": samples[region.group_id],
                    "group": region.group_id,
                    "output_step": region.owner_step,
                    "output_start": bundle.region("B", slice_id).logical_start,
                    "storage_slot": wave,
                }
            )
    if len(result) != 64:
        raise SerializedConvE2Error("three-wave schedule must contain 64 slices")
    owners = {(item["sample"], item["output_step"]) for item in result}
    if owners != {(sample, step) for sample in range(16) for step in range(4)}:
        raise SerializedConvE2Error("three-wave schedule does not cover batch16 x K4")
    return result


def _physical_assets(root: Path) -> tuple[dict[str, np.ndarray], list[dict[str, int]]]:
    _, bundle, _, _ = _load_w3_bundle(root)
    schedule = _schedule(bundle)

    weight = np.zeros((4, 64, 16, 4), dtype=np.int8)
    bias = np.zeros((4, 16), dtype="<i4")
    activation = np.zeros((16, 4, 56, 7, 64, 8, 4), dtype=np.uint8)
    expected = np.zeros((16, 4, 56, 7, 8, 16), dtype="<i4")
    seen_weight: set[int] = set()
    seen_activation: set[tuple[int, int]] = set()
    seen_expected: set[tuple[int, int]] = set()

    for item in schedule:
        wave = item["wave"]
        slice_id = item["slice"]
        sample = item["sample"]
        step = item["output_step"]
        if step not in seen_weight:
            source_w = np.frombuffer(
                bundle.read("B", slice_id), dtype=np.int8
            ).reshape(16, 16, 4)
            weight[step] = _expand_group_lane(source_w, group_axis=0)
            bias[step] = np.frombuffer(
                bundle.read("bias", slice_id), dtype="<i4"
            )
            seen_weight.add(step)
        activation_key = (sample, step)
        if activation_key not in seen_activation:
            start = wave * 200_704
            source_x = np.frombuffer(
                bundle.read("A", slice_id)[start : start + 200_704],
                dtype=np.uint8,
            ).reshape(56, 7, 16, 8, 4)
            activation[sample, step] = _expand_group_lane(
                source_x, group_axis=2
            )
            seen_activation.add(activation_key)
        key = (sample, step)
        if key not in seen_expected:
            start = wave * 200_704
            expected[sample, step] = np.frombuffer(
                bundle.read("P", slice_id)[start : start + 200_704],
                dtype="<i4",
            ).reshape(56, 7, 8, 16)
            seen_expected.add(key)

    if (
        seen_weight != set(range(4))
        or seen_activation
        != {(sample, step) for sample in range(16) for step in range(4)}
        or len(seen_expected) != 64
    ):
        raise SerializedConvE2Error("physical source coverage is incomplete")
    return {
        "weight_s8": weight,
        "activation_u8": activation,
        "bias_s32": bias,
        "expected_d_s32": expected,
    }, schedule


def _write_physical_assets(
    root: Path,
    arrays: Mapping[str, np.ndarray],
    schedule: list[dict[str, int]],
) -> dict[str, Any]:
    physical_path = root / PHYSICAL_REL
    np.savez_compressed(physical_path, **arrays)
    manifest = {
        "schema": "resnet50-node0004-serialized-physical-assets-v1",
        "test_id": TEST_ID,
        "asset": {
            "path": PHYSICAL_REL.as_posix(),
            "sha256": sha256_file(physical_path),
            "size_bytes": physical_path.stat().st_size,
        },
        "arrays": {
            name: {
                "shape": list(value.shape),
                "dtype": str(value.dtype),
                "payload_sha256": hashlib.sha256(
                    np.ascontiguousarray(value).tobytes()
                ).hexdigest(),
            }
            for name, value in arrays.items()
        },
        "schedule": schedule,
        "serialization": {
            "logical_k": 64,
            "physical_group_count": 64,
            "lanes_per_occurrence": 4,
            "nonzero_product_lanes_max": 1,
            "weight_bytes_per_output_tile": SERIALIZED_WEIGHT_BYTES,
            "activation_bytes_per_sample_and_output_step": (
                SERIALIZED_ACTIVATION_BYTES
            ),
        },
        "sources": {
            "w3_accumulator": {
                "path": W3_ACCUMULATOR_REL.as_posix(),
                "sha256": sha256_file(root / W3_ACCUMULATOR_REL),
            },
            "typed_lowering": {
                "path": LOWERING_REL.as_posix(),
                "sha256": sha256_file(root / LOWERING_REL),
            },
        },
    }
    _write_json(root / PHYSICAL_MANIFEST_REL, manifest)
    return manifest


def refresh_physical_assets(project_root: Path) -> dict[str, Any]:
    """Rebuild only this test's generated physical asset and its receipt."""

    root = project_root.resolve()
    if not (root / ARTIFACT_ROOT_REL).is_dir():
        raise SerializedConvE2Error("serialized artifact root is missing")
    arrays, schedule = _physical_assets(root)
    return _write_physical_assets(root, arrays, schedule)


def materialize_inputs(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    _typed_request(root)
    config_root = root / CONFIG_ROOT_REL
    artifact_root = root / ARTIFACT_ROOT_REL
    if config_root.exists() or artifact_root.exists():
        raise SerializedConvE2Error("serialized outputs must use fresh paths")
    config_root.mkdir(parents=True)
    artifact_root.mkdir(parents=True)

    config_records = []
    for wave in range(3):
        config = build_config(root, wave)
        path = config_root / f"wave-{wave}.json"
        _write_json(path, config)
        config_records.append(
            {
                "wave": wave,
                "op_id": op_id(wave),
                "operator_type": operator_type(wave),
                "active_slice_count": WAVE_SLICE_COUNTS[wave],
                "samples": list(WAVE_SAMPLES[wave]),
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "canonical_sha256": sha256_bytes(canonical_json_bytes(config)),
            }
        )
    config_manifest = {
        "schema": "resnet50-node0004-serialized-config-set-v1",
        "test_id": TEST_ID,
        "field_ownership": {
            "typed_geometry_qparams": LOWERING_REL.as_posix(),
            "active_sa_arithmetic": ".agents/rules/INT8_SA点积专项规则.md",
            "topology_seed_structure_only": SOURCE_CONFIG_REL.as_posix(),
            "derived_fields": [
                "LC4.end=16",
                "LC6.end=16",
                "B.dim_stride=[32,2048,14336]",
                "A/B/C/D relative bases from serialized physical sizes",
            ],
        },
        "source_receipts": {
            "typed_lowering_sha256": sha256_file(root / LOWERING_REL),
            "structural_seed_sha256": sha256_file(root / SOURCE_CONFIG_REL),
        },
        "operator_allocation_bytes": OP_ALLOCATION_BYTES,
        "records": config_records,
    }
    _write_json(config_root / "manifest.json", config_manifest)

    graph_path = root / GRAPH_REL
    _write_json(graph_path, graph_spec())
    arrays, schedule = _physical_assets(root)
    physical_path = root / PHYSICAL_REL
    _write_physical_assets(root, arrays, schedule)
    return {
        "test_id": TEST_ID,
        "config_manifest": str(config_root / "manifest.json"),
        "graph": str(graph_path),
        "physical_manifest": str(root / PHYSICAL_MANIFEST_REL),
        "physical_asset": str(physical_path),
    }


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


def serialized_holdouts() -> dict[str, Any]:
    cases = [
        ("positive", [3, 5, 7, 11, 13], [2, 4, 6, 8, 10], 0, 17),
        ("negative", [-3, 5, -7, 11, -13], [2, 4, 6, 8, 10], 0, -19),
        ("k_tail_odd", [127, -128, 1], [255, 255, 1], 0, 0),
        ("nonzero_xzp", [-8, 3, 5, -2, 7], [9, 11, 13, 15, 17], 11, 23),
        ("bias_wrap", [127, 127], [255, 255], 0, 0x7FFFFFF0),
    ]
    rows = []
    for case_id, weights, activations, x_zp, bias in cases:
        initial = _s32(bias - x_zp * sum(weights))
        psum = initial
        occurrences = []
        for index, (weight, activation) in enumerate(
            zip(weights, activations, strict=True)
        ):
            lanes_w = [weight, 0, 0, 0]
            lanes_x = [activation, 0, 0, 0]
            stock = stock_rtl_sa_chunk(lanes_w, lanes_x, psum)["result"]
            independent = _s32(psum + weight * activation)
            if stock != independent:
                raise SerializedConvE2Error(
                    f"stock one-product occurrence differs in {case_id}:{index}"
                )
            occurrences.append(
                {
                    "index": index,
                    "weight_lanes": lanes_w,
                    "activation_lanes": lanes_x,
                    "nonzero_product_lane_count": int(weight * activation != 0),
                    "psum_in": psum,
                    "psum_out": stock,
                }
            )
            psum = stock
        target = _s32(
            bias
            + sum(
                w * (x - x_zp)
                for w, x in zip(weights, activations, strict=True)
            )
        )
        if psum != target:
            raise SerializedConvE2Error(f"serialized holdout differs: {case_id}")
        rows.append(
            {
                "case_id": case_id,
                "k": len(weights),
                "x_zero_point": x_zp,
                "bias": _s32(bias),
                "corrected_initial_psum": initial,
                "target": target,
                "result": psum,
                "occurrences": occurrences,
            }
        )
    return {
        "oracle": "independent s32(psum+s8*u8) recurrence",
        "stock_primitive_cross_check": "stock_rtl_sa_chunk",
        "cases": rows,
        "all_pass": True,
    }


def _leaves(value: Any, path: str = "$") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result.update(_leaves(item, f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_leaves(item, f"{path}[{index}]"))
        return result
    return {path: value}


def _config_bound_simulation(root: Path) -> dict[str, Any]:
    physical_manifest = _load(root / PHYSICAL_MANIFEST_REL)
    physical_path = root / PHYSICAL_REL
    if (
        physical_manifest.get("asset", {}).get("sha256")
        != sha256_file(physical_path)
    ):
        raise SerializedConvE2Error("physical asset receipt differs")
    with np.load(physical_path) as bundle:
        weight_lanes = bundle["weight_s8"]
        activation_lanes = bundle["activation_u8"]
        bias = bundle["bias_s32"]
        expected = bundle["expected_d_s32"]

    if (
        weight_lanes.shape != (4, 64, 16, 4)
        or activation_lanes.shape != (16, 4, 56, 7, 64, 8, 4)
        or bias.shape != (4, 16)
        or expected.shape != (16, 4, 56, 7, 8, 16)
    ):
        raise SerializedConvE2Error("physical asset shapes differ")

    zero_lane_mismatch = 0
    for group in range(64):
        active_lane = group & 3
        inactive = [lane for lane in range(4) if lane != active_lane]
        zero_lane_mismatch += int(
            np.count_nonzero(weight_lanes[:, group, :, inactive])
        )
        zero_lane_mismatch += int(
            np.count_nonzero(
                activation_lanes[:, :, :, :, group, :, inactive]
            )
        )
    if zero_lane_mismatch:
        raise SerializedConvE2Error("serialized physical asset has an active extra lane")

    weights = weight_lanes.sum(axis=-1, dtype=np.int16)
    activations = activation_lanes.sum(axis=-1, dtype=np.uint16)
    simulated = np.empty_like(expected)
    for sample in range(16):
        for step in range(4):
            wide = np.einsum(
                "hwgq,gk->hwqk",
                activations[sample, step].astype(np.int64),
                weights[step].astype(np.int64),
                optimize=True,
            )
            wide += bias[step]
            simulated[sample, step] = wide.astype(np.uint32).view(np.int32)
    physical_mismatch = int(np.count_nonzero(simulated != expected))
    if physical_mismatch:
        raise SerializedConvE2Error(
            f"config-bound physical mismatch count: {physical_mismatch}"
        )

    logical = np.empty((16, 64, 56, 56), dtype=np.int32)
    for sample in range(16):
        for step in range(4):
            logical[sample, step * 16 : (step + 1) * 16] = (
                simulated[sample, step]
                .reshape(56, 56, 16)
                .transpose(2, 0, 1)
            )
    w3 = np.load(root / W3_ACCUMULATOR_REL)
    logical_mismatch = int(np.count_nonzero(logical != w3))
    if logical_mismatch:
        raise SerializedConvE2Error(
            f"inverse logical W3 mismatch count: {logical_mismatch}"
        )

    first_negative: dict[str, Any] | None = None
    for sample in range(16):
        for step in range(4):
            for h in range(56):
                if first_negative is not None:
                    break
                for w_block in range(7):
                    if first_negative is not None:
                        break
                    for q in range(8):
                        if first_negative is not None:
                            break
                        for out_channel in range(16):
                            psum = int(bias[step, out_channel])
                            lane_w = weights[step, :, out_channel].tolist()
                            lane_x = activations[
                                sample, step, h, w_block, :, q
                            ].tolist()
                            for offset in range(0, 64, 4):
                                psum = stock_rtl_sa_chunk(
                                    lane_w[offset : offset + 4],
                                    lane_x[offset : offset + 4],
                                    psum,
                                )["result"]
                            target = int(
                                expected[
                                    sample,
                                    step,
                                    h,
                                    w_block,
                                    q,
                                    out_channel,
                                ]
                            )
                            if psum != target:
                                first_negative = {
                                    "sample": sample,
                                    "output_step": step,
                                    "h": h,
                                    "w": w_block * 8 + q,
                                    "local_output_channel": out_channel,
                                    "stock_four_lane_s32": psum,
                                    "w3_target_s32": target,
                                    "first_weight_group": lane_w[:4],
                                    "first_activation_group": lane_x[:4],
                                }
                                break
    if first_negative is None:
        raise SerializedConvE2Error("stock four-lane negative control did not fail")

    return {
        "consumer_inputs": {
            "physical_asset": {
                "path": PHYSICAL_REL.as_posix(),
                "sha256": sha256_file(physical_path),
            },
            "config_manifest": {
                "path": (CONFIG_ROOT_REL / "manifest.json").as_posix(),
                "sha256": sha256_file(root / CONFIG_ROOT_REL / "manifest.json"),
            },
            "graph": {
                "path": GRAPH_REL.as_posix(),
                "sha256": sha256_file(root / GRAPH_REL),
            },
            "mapping_bundle_manifests": {
                op_id(wave): sha256_file(
                    root
                    / ARTIFACT_ROOT_REL
                    / "mapping"
                    / op_id(wave)
                    / "bundle_manifest.json"
                )
                for wave in range(3)
            },
            "execplan_bundle": {
                "path": (FINAL_EXECPLAN_REL / "bundle_manifest.json").as_posix(),
                "sha256": sha256_file(
                    root / FINAL_EXECPLAN_REL / "bundle_manifest.json"
                ),
            },
            "sca": {
                name: sha256_file(
                    root / FINAL_EXECPLAN_REL / "pipeline_output" / name
                )
                for name in ("sca_cfg.json", "sca_cfg_D.json")
            },
        },
        "inverse": "physical [H,W/8,Q,K16] -> logical [N,C,H,W]",
        "serialized_occurrence_count": 16 * 64 * 56 * 56 * 64,
        "possible_nonzero_product_lanes_per_occurrence_max": 1,
        "inactive_lane_nonzero_value_count": zero_lane_mismatch,
        "physical_mismatch_count": physical_mismatch,
        "logical_w3_mismatch_count": logical_mismatch,
        "physical_output_payload_sha256": hashlib.sha256(
            simulated.tobytes()
        ).hexdigest(),
        "logical_output_payload_sha256": hashlib.sha256(
            logical.tobytes()
        ).hexdigest(),
        "w3_npy_file_sha256": sha256_file(root / W3_ACCUMULATOR_REL),
        "stock_four_lane_negative_control": first_negative,
    }


def _materialized_diff(root: Path) -> dict[str, Any]:
    json_root = root / FINAL_EXECPLAN_REL / "pipeline_output" / "jsons"
    records = []
    for wave in range(3):
        source_path = root / CONFIG_ROOT_REL / f"wave-{wave}.json"
        matches = list(json_root.glob(f"{op_id(wave)}_*.json"))
        if len(matches) != 1:
            raise SerializedConvE2Error("materialized operator JSON is not unique")
        final_path = matches[0]
        source = _load(source_path)
        final = _load(final_path)
        source_leaves, final_leaves = _leaves(source), _leaves(final)
        raw_differences = []
        semantic_nonbase = []
        for path in sorted(set(source_leaves) | set(final_leaves)):
            old = source_leaves.get(path, "<missing>")
            new = final_leaves.get(path, "<missing>")
            if old == new:
                continue
            raw_differences.append({"path": path, "old": old, "new": new})
            is_base = path.endswith(".base_addr")
            numerically_equal = False
            if is_base and isinstance(old, (str, int)) and isinstance(
                new, (str, int)
            ):
                numerically_equal = int(old, 0) == int(new, 0)
            if not is_base or not numerically_equal:
                semantic_nonbase.append(
                    {"path": path, "old": old, "new": new}
                )
        if semantic_nonbase:
            raise SerializedConvE2Error(
                f"unowned materialized non-base diff: {semantic_nonbase[0]}"
            )
        records.append(
            {
                "wave": wave,
                "source": {
                    "path": source_path.relative_to(root).as_posix(),
                    "sha256": sha256_file(source_path),
                },
                "materialized": {
                    "path": final_path.relative_to(root).as_posix(),
                    "sha256": sha256_file(final_path),
                },
                "raw_leaf_difference_count": len(raw_differences),
                "semantic_nonbase_leaf_difference_count": 0,
                "differences": [
                    {
                        **item,
                        "owner": "native output_writer literal normalizer",
                        "input": item["old"],
                        "formula": "int(old,0) -> minimal lowercase hexadecimal",
                        "expected_new": item["new"],
                        "authorization": (
                            "planner/output-writer base materialization; "
                            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001"
                        ),
                    }
                    for item in raw_differences
                ],
            }
        )
    return {
        "allowlist": "$.stream_engine.*.base_addr lexical normalization only",
        "nonbase_change_allowlist": [],
        "records": records,
        "all_semantic_nonbase_fields_unchanged": True,
    }


def _address_and_lifetime(root: Path) -> dict[str, Any]:
    execplan_root = root / FINAL_EXECPLAN_REL
    bundle = _load(execplan_root / "bundle_manifest.json")
    report_path = execplan_root / "request_address_validation_report.json"
    report = _load(report_path)
    if (
        bundle.get("request_address_validation_report", {}).get("sha256")
        != sha256_file(report_path)
        or report.get("valid") is not True
    ):
        raise SerializedConvE2Error("request-address report is not hash-bound valid")
    expected_counts = WAVE_SLICE_COUNTS
    d_records = []
    totals = {"A": 0, "B": 0, "C": 0, "D": 0}
    expected_offsets = {
        row * 3_584 + spatial * 64 + half * 32 + byte
        for row in range(56)
        for spatial in range(56)
        for half in range(2)
        for byte in range(32)
    }
    if (
        len(expected_offsets) != ACCUMULATOR_BYTES
        or min(expected_offsets) != 0
        or max(expected_offsets) != ACCUMULATOR_BYTES - 1
    ):
        raise AssertionError("derived D occurrence coverage is not contiguous")
    stages = report.get("facts", {}).get("stages", [])
    if len(stages) != 3:
        raise SerializedConvE2Error("address report stage count differs")
    for wave, stage in enumerate(stages):
        enabled = stage.get("enabled_slices", [])
        if len(enabled) != expected_counts[wave]:
            raise SerializedConvE2Error("address report slice count differs")
        streams = stage.get("streams", [])
        if len(streams) != expected_counts[wave] * 4:
            raise SerializedConvE2Error("address report stream count differs")
        for item in streams:
            target = item["target"]
            totals[target] += int(item["logical_payload_byte_count_with_multiplicity"])
            if target != "D":
                continue
            first = int(item["first_request"]["byte_addr_30b"], 0)
            last = int(item["last_request"]["byte_addr_30b"], 0)
            if (
                item["transaction_size_bytes"] != 32
                or item["index_tuple_count"] != 6_272
                or item["request_count_with_multiplicity"] != 12_544
                or item["unique_request_count"] != 12_544
                or item["logical_payload_byte_count_with_multiplicity"]
                != ACCUMULATOR_BYTES
                or last - first + 16 != ACCUMULATOR_BYTES
            ):
                raise SerializedConvE2Error("final D occurrence coverage differs")
            d_records.append(
                {
                    "wave": wave,
                    "slice": item["execution_slice"],
                    "base_addr": item["base_addr"],
                    "transaction_count": item["request_count_with_multiplicity"],
                    "unique_16byte_base_count": item["unique_request_count"],
                    "recomputed_written_byte_count": len(expected_offsets),
                    "region": item["first_request"]["region_hits"][0],
                    "first_byte_addr": item["first_request"]["byte_addr_30b"],
                    "last_byte_addr": item["last_request"]["byte_addr_30b"],
                }
            )
    if len(d_records) != 64:
        raise SerializedConvE2Error("D coverage record count differs")
    if totals != {
        "A": 64 * SERIALIZED_WEIGHT_BYTES,
        "B": 64 * SERIALIZED_ACTIVATION_BYTES,
        "C": 64 * 25_088,
        "D": 64 * ACCUMULATOR_BYTES,
    }:
        raise SerializedConvE2Error(f"stream payload totals differ: {totals}")
    return {
        "full_request_enumeration": {
            "path": report_path.relative_to(root).as_posix(),
            "sha256": sha256_file(report_path),
            "request_count_with_multiplicity": report["facts"][
                "request_count_with_multiplicity"
            ],
            "unique_request_address_count": report["facts"][
                "unique_request_address_count"
            ],
            "sampled_for_release": False,
        },
        "stream_payload_bytes_with_multiplicity": totals,
        "write_coverage_equation": (
            "offset=row*3584 + (lc15*8+lc9)*64 + lc13*32 + byte; "
            "row=0..55, lc15=0..6, lc9=0..7, lc13=0..1, byte=0..31"
        ),
        "per_output_region": d_records,
        "terminal_conservation": {
            "slice_schedule_count": 64,
            "unique_logical_output_tiles": 64,
            "D_regions_written_exactly_once": 64,
            "D_bytes_per_region": ACCUMULATOR_BYTES,
            "typed_output_bytes": 64 * ACCUMULATOR_BYTES,
            "all_no_pingpong": True,
            "buffer_local_geometry_unchanged": True,
            "serialized_reduction_groups_per_output": 64,
            "products_per_output": 64,
            "bias_initializations_per_output": 1,
            "terminal_writes_per_output": 1,
        },
        "lifetime_boundary": (
            "symbolic config/address/terminal conservation is closed for the "
            "local baseline; cycle-level server dynamic release remains false"
        ),
    }


def build_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    rule_path = root / ".agents/rules/算子配置规则.md"
    rule_sha = sha256_file(rule_path)
    if (
        rule_sha
        != "407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc"
    ):
        raise SerializedConvE2Error("active common config rule receipt differs")
    request = _typed_request(root)
    execplan = _load(root / FINAL_EXECPLAN_REL / "bundle_manifest.json")
    if (
        execplan.get("double_run", {}).get("equal") is not True
        or execplan.get("validation_report", {}).get("valid") is not True
        or execplan.get("request_address_validation_report", {}).get("valid")
        is not True
    ):
        raise SerializedConvE2Error("final native execplan bundle is not valid")
    mappings = {}
    for wave in range(3):
        manifest_path = (
            root
            / ARTIFACT_ROOT_REL
            / "mapping"
            / op_id(wave)
            / "bundle_manifest.json"
        )
        manifest = _load(manifest_path)
        if (
            manifest.get("summary", {}).get("valid") is not True
            or manifest.get("summary", {}).get("penalty") != 0
            or manifest.get("summary", {}).get("fallback_used") is not False
        ):
            raise SerializedConvE2Error("mapping evidence is not exact")
        mappings[op_id(wave)] = {
            "path": manifest_path.relative_to(root).as_posix(),
            "sha256": sha256_file(manifest_path),
            "penalty": 0,
            "fallback_used": False,
        }

    materialized = _materialized_diff(root)
    address = _address_and_lifetime(root)
    simulation = _config_bound_simulation(root)
    holdouts = serialized_holdouts()
    occurrence_count = simulation["serialized_occurrence_count"]
    contract: dict[str, Any] = {
        "schema": "resnet50-node0004-serialized-one-product-local-e2-v1",
        "status": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "candidate_release": False,
        "test_id": TEST_ID,
        "scope": {
            "node_id": NODE_ID,
            "request_id": REQUEST_ID,
            "request_sha256": REQUEST_SHA256,
            "hw_op_type": "ConvInt32Accumulate",
            "frozen_instance": {
                "x": ["uint8", [16, 64, 56, 56]],
                "w": ["int8", [64, 64, 1, 1]],
                "bias": ["int32", [64]],
                "output": ["int32", [16, 64, 56, 56]],
                "x_zero_point": 0,
                "weight_zero_points": "all zero",
            },
            "not_in_scope": [
                "QLinearConv requant",
                "the remaining 52 Conv nodes",
                "QLinearMatMul rank2/layout/tail",
                "server dynamic execution",
                "production/performance release",
            ],
        },
        "bypass_annotation": {
            "rule_id": "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
            "bypass_reason": (
                "stock four-lane INT8 SA shifts CSA carry a second time and "
                "also constrains the legal four-product reduction to signed17"
            ),
            "contradicted_or_missing_native_path": {
                "path": "stock four-lane s8*u8 dot4 -> psum32",
                "carry_counterexample": "four products 1 yield stock 6, target 4",
                "range_counterexample": (
                    "legal dot4 range [-130560,129540] exceeds "
                    "signed17 [-65536,65535] and cout17 is ignored"
                ),
            },
            "exact_equivalence_scope": (
                "frozen node0004 ConvInt32Accumulate x_zp=0, W3 bias and "
                "INT32 modulo accumulation; synthetic holdouts cover nonzero "
                "x_zp correction, odd K/tail and wrap but do not release other nodes"
            ),
            "materialized_configuration_mechanism": (
                "expand each original K lane into a separate four-byte SA "
                "occurrence with the original lane retained and the other "
                "three lanes zero; LC4/LC6 group count 16->64"
            ),
            "performance_and_resource_cost": {
                "compute_occurrence_multiplier": 4,
                "serialized_occurrences": occurrence_count,
                "product_lane_slots": occurrence_count * 4,
                "maximum_useful_product_lane_utilization": "25%",
                "weight_payload_multiplier": 4,
                "activation_payload_multiplier": 4,
                "extra_barrier_count": 0,
                "extra_scratch_stage_count": 0,
            },
            "unresolved_production_blocker": [
                "B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY",
                "B_SA_INT8_DUPLICATE_CARRY_SHIFT",
                "B_SA_INT8_REDUCTION_WIDTH",
                "B_CONV_SERIALIZED_BASELINE_PERFORMANCE",
                "B_CONV_SERVER_DYNAMIC_RELEASE",
            ],
            "claim_boundary": (
                "local accumulate-only CONFIG_ONLY_CORRECTNESS_BASELINE; "
                "not a target/production/performance release and does not "
                "close bias/psum/tiling/tail or requant gates beyond this instance"
            ),
        },
        "field_ownership": {
            "generator": {
                "path": "resnet50_pipeline/conv_serialized_one_product_local_e2.py",
                "sha256": sha256_file(
                    root
                    / "resnet50_pipeline/conv_serialized_one_product_local_e2.py"
                ),
            },
            "unique_owner_groups": [
                {
                    "paths": "$.dram_loop_configs, $.lc_pe_configs",
                    "owner": "serialized logical ScheduleIR",
                    "inputs": "K=64, four-byte word, PE=outer*4+inner",
                },
                {
                    "paths": "$.stream_engine",
                    "owner": "serialized physical layout and address schedule",
                    "inputs": "A=4096B, B=802816B, C=64B, D=200704B",
                },
                {
                    "paths": "$.buffer_loop_configs, $.buffer_config",
                    "owner": "unchanged 4x4 local buffer micro-topology",
                    "inputs": "one four-byte group per reduction occurrence",
                },
                {
                    "paths": "$.special_array",
                    "owner": "INT8 SA rule plus mainline serialized authorization",
                    "inputs": "gemm, s8 A, u8 B, bias/psum C",
                },
                {
                    "paths": "$.CONFIG, $.n2n",
                    "owner": "single-stage local baseline lifecycle ScheduleIR",
                    "inputs": "IGA/LSU/SA enabled+updated, GA disabled, no N2N",
                },
            ],
            "structural_seed_is_not_semantic_owner": True,
            "materialized_leaf_diff": materialized,
        },
        "input_replay": {
            "rule_id": "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "sources": [
                {
                    "role": "activation",
                    "producer": "node-0003 formal W3 output",
                    "tensor_id": "tensor-8d2f28c80ac24676",
                    "dtype": "uint8",
                    "shape": [16, 64, 56, 56],
                    "identity_sha256": (
                        "e4039c779c0083ff3cbe76845b4ba313"
                        "e9b2e095e4faa72d329cbfa04f6cae1b"
                    ),
                },
                {
                    "role": "weight",
                    "producer": "frozen ONNX initializer",
                    "tensor_id": "tensor-56b60866ff5ecb4a",
                    "dtype": "int8",
                    "shape": [64, 64, 1, 1],
                    "identity_sha256": (
                        "ff6ee89cbc889e0708d483f22b2a8f0e"
                        "09f2cde13f65dcac061eb30551f68b48"
                    ),
                },
                {
                    "role": "bias",
                    "producer": "frozen ONNX initializer",
                    "tensor_id": "tensor-d72c70cfb6839a45",
                    "dtype": "int32",
                    "shape": [64],
                    "identity_sha256": (
                        "40bc2a3acbd553ffc067ea1c7b1c31cb"
                        "59f18fca30451f55809ff76d2594bc0b"
                    ),
                },
            ],
            "allowed_index_address_mapping": (
                "value-preserving Conv28 physical permutation followed by "
                "K group g,lane l -> serialized group 4*g+l with the same "
                "byte in lane l and zeros in all other lanes"
            ),
            "uncrossed_computation_boundary": (
                "no scaled, rounded, saturated, accumulated or requantized "
                "tensor is replayed as an input"
            ),
            "golden_is_oracle_only": {
                "tensor_id": "tensor-internal-node-0004-accumulate",
                "path": W3_ACCUMULATOR_REL.as_posix(),
                "never_consumed_as_compute_input": True,
            },
        },
        "occurrence_proof": {
            "logical_products_per_output": 64,
            "serialized_occurrences_per_output": 64,
            "lanes_per_occurrence": 4,
            "nonzero_product_lanes_per_occurrence_max": 1,
            "lane_padding": "three forced-zero lanes in every K occurrence",
            "target_k_tail": "K=64 exact; no reduction tail",
            "synthetic_tail_and_xzp": holdouts,
        },
        "native_roundtrip": {
            "mapping": mappings,
            "execplan": {
                "path": (
                    FINAL_EXECPLAN_REL / "bundle_manifest.json"
                ).as_posix(),
                "sha256": sha256_file(
                    root / FINAL_EXECPLAN_REL / "bundle_manifest.json"
                ),
                "double_run_equal": True,
                "deterministic_file_count": execplan["double_run"][
                    "deterministic_file_count"
                ],
                "execplan_sha256": execplan["execplan"]["sha256"],
            },
            "json_mapping_bitstream_execplan_sca": "PASS",
        },
        "address_lifetime_terminal": address,
        "config_bound_simulator": simulation,
        "stage_gates": {
            "json_emitter_ready": True,
            "rtl_semantics_compatible": True,
            "dynamic_release_ready": False,
        },
        "blocker_delta": {
            "close": ["B_SA_SERIALIZED_FALLBACK_MATERIALIZATION"],
            "keep": [
                "B_CONV_INT8_SA",
                "B_MATMUL_INT8_SA",
                "B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY",
                "B_SA_INT8_DUPLICATE_CARRY_SHIFT",
                "B_SA_INT8_REDUCTION_WIDTH",
            ],
            "add": [
                "B_CONV_SERIALIZED_BASELINE_PERFORMANCE",
                "B_CONV_SERVER_DYNAMIC_RELEASE",
            ],
        },
        "rule_delta_proposal": [],
        "package_release": "NONE",
        "read_receipts": {
            ".agents/rules/算子配置规则.md": rule_sha,
            ".agents/rules/生成前必读索引.md": sha256_file(
                root / ".agents/rules/生成前必读索引.md"
            ),
            ".agents/rules/INT8_SA点积专项规则.md": sha256_file(
                root / ".agents/rules/INT8_SA点积专项规则.md"
            ),
            ".agents/task_records/20260727_conv_serialized_config_baseline_mainline_authorization.md": sha256_file(
                root
                / ".agents/task_records/20260727_conv_serialized_config_baseline_mainline_authorization.md"
            ),
            LOWERING_REL.as_posix(): sha256_file(root / LOWERING_REL),
            "typed_request_sha256": request["request_sha256"],
        },
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def write_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    contract = build_contract(root)
    _write_json(root / CONTRACT_REL, contract)
    return contract


__all__ = [
    "ARTIFACT_ROOT_REL",
    "CONFIG_ROOT_REL",
    "CONTRACT_REL",
    "GRAPH_REL",
    "PATCHSET_REL",
    "PHYSICAL_MANIFEST_REL",
    "PHYSICAL_REL",
    "SerializedConvE2Error",
    "TEST_ID",
    "build_config",
    "build_contract",
    "graph_spec",
    "materialize_inputs",
    "op_id",
    "operator_type",
    "refresh_physical_assets",
    "serialized_holdouts",
    "write_contract",
]
