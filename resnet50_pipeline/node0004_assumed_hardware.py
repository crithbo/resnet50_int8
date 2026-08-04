from __future__ import annotations

import json
import shutil
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from tools.generate_conv_1x1_real import build_real_1x1

from .conv28_layout import (
    CONV28_SIGNED_A_LOCAL_LAYOUT_ABI,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    QLinearConvPhysicalLayout,
)
from .conv_instance import FIRST_REAL_CONV_NODE_ID, load_conv_instance_spec
from .conv_sa_contract import validate_first_conv_signed_a_local_contract
from .conv_native_package import (
    WAVE_SAMPLES,
    WAVE_SLICE_COUNTS,
    graph_spec as conv_graph_spec,
    write_conv_native_inputs,
)
from .exact_uint8_quant_tail_rounding_discriminator import (
    EVEN_PES,
    MAGIC_BITS,
    MAGIC_FLOAT,
    ODD_PES,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndp_patch_toolchain import (
    NODE0004_ASSUMED_HW_PATCHSET_ID,
    build_patchset_manifest,
)
from .operator_config_evidence_bundle import create_mapping_evidence_bundle
from .operator_config_execplan_evidence import create_execplan_evidence_bundle
from .operator_config_adjudication import normalize_known_legacy_expressions
from .operator_config_validator import OperatorConfigValidator
from .requant_native_package import (
    HIGH_RING_OWNERS,
    LANES,
    SHARD_COUNT,
    SPATIAL,
    requant_parameters,
)
from .w5_conv_preflight import (
    _initializer,
    _initializer_values,
    _load_npy,
    validate_conv_hardware_quantization_preconditions,
)


SCHEMA = "resnet50-node0004-assumed-hardware-local-e2-v1"
NODE_ID = "node-0004"
ACCUMULATE_HW_OP = "hwop-0004-00"
REQUANT_HW_OP = "hwop-0004-01"
ROUND_MAGIC_BITS = MAGIC_BITS

ROOT_REL = Path(
    "artifacts/operator_config_validation/r5-node0004-assumed-hardware-v1"
)
CONFIG_REL = Path("configs/native_ndp_sim/node0004_assumed_hardware_v1")
PATCHSET_REL = Path("contracts/ndp_patch_toolchain_node0004_assumed_hw_v1.json")
CONTRACT_REL = Path(
    "contracts/operator_config/node0004_assumed_hardware_local_e2_v1.json"
)

RUNTIME_REL = Path("artifacts/w3/golden_batch16")
SUBOP_REL = Path("artifacts/w3/subop_batch16")
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
TEMPLATE_REL = Path("ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json")
CONV_ORACLE_REL = Path("conv_full.json")


class Node0004AssumedHardwareError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Node0004AssumedHardwareError(f"JSON root must be object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _mask(slice_ids: list[int]) -> str:
    bits = ["0"] * 28
    for slice_id in slice_ids:
        bits[27 - slice_id] = "1"
    return "0b" + "".join(bits)


def _typed_descriptors(root: Path) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    spec = load_conv_instance_spec(root, FIRST_REAL_CONV_NODE_ID)
    runtime = _load(root / RUNTIME_REL / "manifest.json")
    subop = _load(root / SUBOP_REL / "manifest.json")
    descriptors = {
        name: spec.tensor(name).descriptor()
        for name in (
            "A",
            "B",
            "bias",
            "w_scale",
            "w_zero_point",
            "x_scale",
            "x_zero_point",
            "y_scale",
            "y_zero_point",
            "P",
            "D",
        )
    }
    return spec, runtime, subop, descriptors


def load_fresh_w3_values(root: Path) -> dict[str, np.ndarray]:
    spec, runtime, subop, descriptors = _typed_descriptors(root)
    initializers = _initializer_values(root / MODEL_REL)
    values: dict[str, np.ndarray] = {
        "A": _load_npy(
            root / RUNTIME_REL,
            runtime,
            runtime["tensors"][descriptors["A"]["tensor_id"]],
        ),
        "P": _load_npy(
            root / SUBOP_REL,
            subop,
            subop["internal_tensors"][descriptors["P"]["tensor_id"]],
        ),
        "D": _load_npy(
            root / RUNTIME_REL,
            runtime,
            runtime["tensors"][descriptors["D"]["tensor_id"]],
        ),
    }
    for name in (
        "B",
        "bias",
        "w_scale",
        "w_zero_point",
        "x_scale",
        "x_zero_point",
        "y_scale",
        "y_zero_point",
    ):
        values[name] = _initializer(initializers, runtime, descriptors[name])
    validate_conv_hardware_quantization_preconditions(values)
    if (
        values["A"].shape != (16, 64, 56, 56)
        or values["B"].shape != (64, 64, 1, 1)
        or values["P"].shape != (16, 64, 56, 56)
        or values["D"].shape != values["P"].shape
    ):
        raise Node0004AssumedHardwareError("fresh node0004 W3 geometry differs")
    return values


def load_fresh_physical_bundle(root: Path):
    spec, runtime, subop, descriptors = _typed_descriptors(root)
    values = load_fresh_w3_values(root)
    layout = QLinearConvPhysicalLayout(
        profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE,
        layout_abi=CONV28_SIGNED_A_LOCAL_LAYOUT_ABI,
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
        strides=spec.strides,
        pads=spec.pads,
        dilations=spec.dilations,
        group=spec.group,
        tensor_ids={
            name: descriptor["tensor_id"] for name, descriptor in descriptors.items()
        },
    )
    layout.validate(bundle)
    return spec, bundle, runtime, subop


def build_fresh_accumulate_base(root: Path) -> dict[str, Any]:
    source = _load(root / CONV_ORACLE_REL)
    spec = load_conv_instance_spec(root, NODE_ID)
    generated = build_real_1x1(source, spec)
    config, changes = normalize_known_legacy_expressions(generated)
    if not changes or any(
        change.kind != "remove_write_read_only_field" for change in changes
    ):
        raise Node0004AssumedHardwareError(
            "fresh accumulate strict cleanup exceeds write-stream read-only fields"
        )
    # The two unsigned activation producers feed the SA ping-pong buffers from
    # the same local activation slot.  The generic conv_full oracle carries an
    # unrelated stream2 offset; the signed-A local ABI requires address-
    # identical B/B' producers.
    config["stream_engine"]["stream2"]["base_addr"] = config[
        "stream_engine"
    ]["stream1"]["base_addr"]
    validate_first_conv_signed_a_local_contract(config)
    report = OperatorConfigValidator().validate(
        config, source="fresh typed/model-derived node0004 accumulate"
    )
    if not report.valid:
        raise Node0004AssumedHardwareError(
            f"fresh accumulate config invalid: {report.to_dict()['first_error']}"
        )
    return config


def _set_conversion_flags(port: dict[str, Any], *, int32_to_fp32: bool) -> None:
    port.update(
        {
            "fp16tofp32": "false",
            "bf16tofp32": "false",
            "int32tofp32": "true" if int32_to_fp32 else "false",
            "uint8tofp32": "false",
            "uint8toint32": "false",
        }
    )


def _set_tail_geometry(
    config: dict[str, Any], *, packed_uint8_output: bool
) -> None:
    loops = config["dram_loop_configs"]
    loops["LC0"].update({"start": 0, "end": 1, "stride": 1, "last_index": 0})
    loops["LC1"].update(
        {"start": 0, "end": SPATIAL, "stride": 1, "last_index": 1}
    )
    loops["LC2"].update(
        {
            "start": 0,
            "end": SPATIAL // 4 if packed_uint8_output else SPATIAL,
            "stride": 1,
            "last_index": 1,
        }
    )
    read = config["stream_engine"]["stream0"]
    read["idx_size"] = [0, 31, None]
    read["dim_stride"] = [LANES * 4, SPATIAL * LANES * 4, None]
    read["buf_spatial_stride"] = list(range(16))
    read["buf_spatial_size"] = 16
    write = config["stream_engine"]["stream2"]
    write["idx_size"] = (
        [3, 7, None] if packed_uint8_output else [0, 31, None]
    )
    write["dim_stride"] = [
        32,
        SPATIAL * LANES if packed_uint8_output else SPATIAL * LANES * 4,
        None,
    ]
    write["buf_spatial_stride"] = (
        [
            0,
            4,
            8,
            12,
            16,
            20,
            24,
            28,
            1,
            5,
            9,
            13,
            17,
            21,
            25,
            29,
        ]
        if packed_uint8_output
        else list(range(16))
    )
    write["buf_spatial_size"] = 16


def build_tail_configs(
    root: Path,
) -> tuple[dict[tuple[str, int, int], dict[str, Any]], dict[str, Any]]:
    template_path = root / TEMPLATE_REL
    template = _load(template_path)
    multiplier, zero_point, typed_identity = requant_parameters(root)
    if zero_point != 0:
        raise Node0004AssumedHardwareError("node0004 assumed tail requires zp0")
    configs: dict[tuple[str, int, int], dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    for wave in range(3):
        for shard in range(SHARD_COUNT):
            channels = list(range(shard * LANES, (shard + 1) * LANES))
            mul = deepcopy(template)
            _set_tail_geometry(mul, packed_uint8_output=False)
            _set_conversion_flags(
                mul["general_array"]["inport"]["inport0"],
                int32_to_fp32=True,
            )
            mul["general_array"]["outport"].update(
                {"src_id": 0, "int32touint8": "false"}
            )
            mul["stream_engine"]["stream0"]["base_addr"] = "0x00000000"
            mul["stream_engine"]["stream2"]["base_addr"] = "0x00018800"
            mul_pes: dict[str, Any] = {}
            for pe_name, channel in zip(EVEN_PES, channels, strict=True):
                pe = deepcopy(template["general_array"]["PE_array"][pe_name])
                pe["alu_opcode"] = "mul"
                pe["inport0"].update({"src_id": 0, "mode": "buffer"})
                pe["inport1"].update(
                    {
                        "src_id": None,
                        "mode": "constant",
                        "constant": float(multiplier[channel]),
                    }
                )
                pe["inport2"].update(
                    {"src_id": None, "mode": None, "constant": 0}
                )
                mul_pes[pe_name] = pe
            mul["general_array"]["PE_array"] = mul_pes

            rounded = deepcopy(template)
            _set_tail_geometry(rounded, packed_uint8_output=True)
            _set_conversion_flags(
                rounded["general_array"]["inport"]["inport0"],
                int32_to_fp32=False,
            )
            rounded["general_array"]["outport"].update(
                {"src_id": 1, "int32touint8": "true"}
            )
            rounded["stream_engine"]["stream0"]["base_addr"] = "0x00018800"
            rounded["stream_engine"]["stream2"]["base_addr"] = "0x00031000"
            for pe_name in EVEN_PES:
                pe = rounded["general_array"]["PE_array"][pe_name]
                pe["alu_opcode"] = "mac"
                pe["inport0"].update({"src_id": 0, "mode": "buffer"})
                pe["inport1"].update(
                    {"src_id": None, "mode": "constant", "constant": 1.0}
                )
                pe["inport2"].update(
                    {
                        "src_id": None,
                        "mode": "constant",
                        "constant": float(MAGIC_FLOAT),
                    }
                )
            for pe_name in ODD_PES:
                pe = rounded["general_array"]["PE_array"][pe_name]
                pe["alu_opcode"] = "int32_sub"
                pe["inport1"].update(
                    {
                        "src_id": None,
                        "mode": "constant",
                        "constant": ROUND_MAGIC_BITS,
                    }
                )
            for kind, config in (("mul", mul), ("round", rounded)):
                report = OperatorConfigValidator().validate(
                    config,
                    source=f"node0004 assumed tail {kind} w{wave}s{shard:02d}",
                )
                if not report.valid:
                    raise Node0004AssumedHardwareError(
                        f"tail {kind} config invalid: "
                        f"{report.to_dict()['first_error']}"
                    )
                configs[(kind, wave, shard)] = config
                records.append(
                    {
                        "kind": kind,
                        "wave": wave,
                        "shard": shard,
                        "channels": channels,
                        "config_sha256": sha256_bytes(
                            canonical_json_bytes(config)
                        ),
                    }
                )
    return configs, {
        "schema": "node0004-direct-signed-two-stage-tail-config-set-v1",
        "template": {
            "path": TEMPLATE_REL.as_posix(),
            "sha256": sha256_file(template_path),
            "reuse_scope": "structure and primitive only",
        },
        "typed_identity": typed_identity,
        "pair_local_address_policy": {
            "mul_A": "0x00000000",
            "mul_D_round_A": "0x00018800",
            "round_D": "0x00031000",
            "reuse_across_wave_shard_pairs": True,
        },
        "stage_count": len(configs),
        "records": records,
    }


def _tail_op_id(kind: str, wave: int, shard: int) -> str:
    return f"op_{kind}_w{wave}_s{shard:02d}"


def _tail_op_type(kind: str, wave: int, shard: int) -> str:
    return f"resnet50_requant_node0004_{kind}_w{wave}_s{shard:02d}"


def _wave_active_slices(wave: int, shard: int) -> list[int]:
    owner_step = shard // 2
    return [
        HIGH_RING_OWNERS[group_id][owner_step]
        for group_id in range(len(WAVE_SAMPLES[wave]))
    ]


def tail_graph_spec() -> dict[str, Any]:
    operators: list[dict[str, Any]] = []
    for wave in range(3):
        for shard in range(SHARD_COUNT):
            slices = _wave_active_slices(wave, shard)
            mul_id = _tail_op_id("mul", wave, shard)
            operators.append(
                {
                    "id": mul_id,
                    "type": _tail_op_type("mul", wave, shard),
                    "used_slices": _mask(slices),
                    "inputs": {
                        "A": {
                            "shape": [1, SPATIAL, LANES],
                            "dtype": "int32",
                            "bank_interleave": 1,
                            "remapping": None,
                            "source": {"type": "external"},
                        }
                    },
                    "output": {
                        "shape": [1, SPATIAL, LANES],
                        "dtype": "fp32",
                        "bank_interleave": 1,
                        "remapping": None,
                    },
                }
            )
            operators.append(
                {
                    "id": _tail_op_id("round", wave, shard),
                    "type": _tail_op_type("round", wave, shard),
                    "used_slices": _mask(slices),
                    "inputs": {
                        "A": {
                            "shape": [1, SPATIAL, LANES],
                            "dtype": "fp32",
                            "bank_interleave": 1,
                            "remapping": None,
                            "source": {
                                "type": "operator",
                                "operator_id": mul_id,
                            },
                        }
                    },
                    "output": {
                        "shape": [1, SPATIAL, LANES],
                        "dtype": "uint8",
                        "bank_interleave": 1,
                        "remapping": None,
                    },
                }
            )
    return {
        "params": {
            "node_id": NODE_ID,
            "hw_op_id": REQUANT_HW_OP,
            "execution": "phase-B hardware-produced-accumulator replay",
        },
        "used_slices": _mask(list(range(28))),
        "operators": operators,
    }


def local_numeric_report(root: Path) -> dict[str, Any]:
    values = load_fresh_w3_values(root)
    multiplier, zero_point, typed_identity = requant_parameters(root)
    activation = values["A"].transpose(0, 2, 3, 1).reshape(-1, 64)
    weight = values["B"][:, :, 0, 0]
    x_zero = int(values["x_zero_point"].reshape(-1)[0])
    w_zero = values["w_zero_point"].astype(np.int64).reshape(64)
    if np.any(w_zero != 0):
        raise Node0004AssumedHardwareError("node0004 fresh W3 w_zp differs")
    centered = activation.astype(np.int64) - x_zero
    computed = centered @ weight.astype(np.int64).T
    computed += values["bias"].astype(np.int64).reshape(1, 64)
    computed_nchw = (
        computed.reshape(16, 56, 56, 64)
        .transpose(0, 3, 1, 2)
        .astype(np.int32)
    )
    accumulate_mismatch = int(np.count_nonzero(computed_nchw != values["P"]))

    scaled = values["P"].astype(np.float32) * multiplier.reshape(1, 64, 1, 1)
    rounded = (
        (scaled + np.float32(MAGIC_FLOAT)).view(np.int32).astype(np.int64)
        - ROUND_MAGIC_BITS
        + zero_point
    )
    final = np.clip(rounded, 0, 255).astype(np.uint8)
    final_mismatch = int(np.count_nonzero(final != values["D"]))
    if accumulate_mismatch or final_mismatch:
        raise Node0004AssumedHardwareError(
            f"fresh W3 mismatch: accumulate={accumulate_mismatch}, "
            f"tail={final_mismatch}"
        )

    grouped_weight = weight.reshape(64, 16, 4).astype(np.int64)
    max_dot4 = -2**63
    min_dot4 = 2**63 - 1
    dot4_count = 0
    chunk_rows = 2048
    for start in range(0, centered.shape[0], chunk_rows):
        rows = centered[start : start + chunk_rows]
        groups = rows.reshape(-1, 16, 4)
        dot4 = np.einsum("rig,oig->roi", groups, grouped_weight)
        min_dot4 = min(min_dot4, int(dot4.min()))
        max_dot4 = max(max_dot4, int(dot4.max()))
        dot4_count += int(dot4.size)

    return {
        "element_count": int(values["P"].size),
        "dot4_group_count": dot4_count,
        "dot4_observed_range": [min_dot4, max_dot4],
        "accumulate_mismatch_count": accumulate_mismatch,
        "tail_mismatch_count": final_mismatch,
        "accumulator_sha256": sha256_bytes(
            np.ascontiguousarray(values["P"]).tobytes()
        ),
        "output_sha256": sha256_bytes(
            np.ascontiguousarray(values["D"]).tobytes()
        ),
        "scaled_fp32_sha256": sha256_bytes(
            np.ascontiguousarray(scaled).tobytes()
        ),
        "magic_domain": {
            "scaled_min": float(scaled.min()),
            "scaled_max": float(scaled.max()),
            "finite": bool(np.isfinite(scaled).all()),
        },
        "typed_identity": typed_identity,
    }


def fresh_conv_graph_spec() -> dict[str, Any]:
    """Return the fresh Conv graph with both physical activation read ports.

    The stock Conv configuration reads the same activation allocation through
    targets ``B`` and ``B'``.  ``B'`` is therefore declared explicitly here so
    request-address validation can prove both physical streams while the
    package validator continues to alias their storage for this operator type.
    """

    graph = conv_graph_spec()
    for operator in graph["operators"]:
        # Both physical ports address the same complete activation slot.  They
        # are two producers for the SA ping-pong input buffers, not two
        # independent allocations.
        activation_tail = deepcopy(operator["inputs"]["B"])
        activation_tail["source"] = {"type": "external"}
        operator["inputs"]["B'"] = activation_tail
    return graph


def fresh_conv_wave_graph_spec(wave: int) -> dict[str, Any]:
    graph = fresh_conv_graph_spec()
    operators = [
        operator
        for operator in graph["operators"]
        if operator["id"] == f"op_w{wave}"
    ]
    if len(operators) != 1:
        raise Node0004AssumedHardwareError(f"invalid Conv wave: {wave}")
    graph["operators"] = operators
    graph["params"] = {**graph["params"], "selected_wave": wave}
    graph["used_slices"] = operators[0]["used_slices"]
    return graph


def tail_pair_graph_spec(wave: int, shard: int) -> dict[str, Any]:
    graph = tail_graph_spec()
    selected = {
        _tail_op_id("mul", wave, shard),
        _tail_op_id("round", wave, shard),
    }
    operators = [
        operator for operator in graph["operators"] if operator["id"] in selected
    ]
    if len(operators) != 2:
        raise Node0004AssumedHardwareError(
            f"invalid tail pair: wave={wave}, shard={shard}"
        )
    graph["operators"] = operators
    graph["params"] = {
        **graph["params"],
        "selected_wave": wave,
        "selected_shard": shard,
    }
    graph["used_slices"] = operators[0]["used_slices"]
    return graph


def materialize_local_inputs(
    project_root: Path,
    output_root: Path,
    config_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    configs = config_root.resolve()
    if output.exists() or configs.exists():
        raise Node0004AssumedHardwareError("fresh output/config roots required")
    configs.mkdir(parents=True)

    accumulate_base = build_fresh_accumulate_base(root)
    accumulate_base_path = configs / "accumulate_base.json"
    _write_json(accumulate_base_path, accumulate_base)
    source_rel = accumulate_base_path.relative_to(root)
    conv_transport = output / "conv_transport"
    conv_configs = configs / "accumulate_waves"
    write_conv_native_inputs(
        root,
        conv_transport,
        conv_configs,
        source_config_rel=source_rel,
        w3_bundle_loader=load_fresh_physical_bundle,
        reuse_wave_addresses=True,
    )

    tail_configs, tail_manifest = build_tail_configs(root)
    tail_root = configs / "tail"
    tail_root.mkdir()
    for (kind, wave, shard), config in sorted(tail_configs.items()):
        _write_json(
            tail_root / f"{kind}_w{wave}_s{shard:02d}.json",
            config,
        )
    _write_json(tail_root / "manifest.json", tail_manifest)
    _write_json(output / "conv_graph.json", fresh_conv_graph_spec())
    _write_json(output / "tail_graph.json", tail_graph_spec())
    for wave in range(3):
        _write_json(
            output / "conv_graphs" / f"wave-{wave}.json",
            fresh_conv_wave_graph_spec(wave),
        )
        for shard in range(SHARD_COUNT):
            _write_json(
                output
                / "tail_graphs"
                / f"wave-{wave}-shard-{shard:02d}.json",
                tail_pair_graph_spec(wave, shard),
            )
    numeric = local_numeric_report(root)
    _write_json(output / "local_numeric_report.json", numeric)
    return {
        "accumulate_base": accumulate_base_path,
        "conv_transport": conv_transport,
        "conv_config_root": conv_configs,
        "tail_config_root": tail_root,
        "numeric": numeric,
    }


def materialize_mappings_and_execplans(
    project_root: Path,
    output_root: Path,
    config_root: Path,
    *,
    python_executable: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    configs = config_root.resolve()
    ndp = root / "ndp-sim"
    patchset_path = root / PATCHSET_REL
    patchset = build_patchset_manifest(
        ndp, patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID
    )
    if patchset_path.exists():
        if _load(patchset_path) != patchset:
            raise Node0004AssumedHardwareError(
                f"existing patchset differs: {patchset_path}"
            )
    else:
        _write_json(patchset_path, patchset)

    # Graph declarations are cheap deterministic control artifacts.  Refresh
    # them on every resume so a corrected interface declaration cannot leave a
    # stale graph paired with otherwise reusable mapping evidence.
    _write_json(output / "conv_graph.json", fresh_conv_graph_spec())
    _write_json(output / "tail_graph.json", tail_graph_spec())
    tail_configs, tail_manifest = build_tail_configs(root)
    for (kind, wave, shard), config in sorted(tail_configs.items()):
        _write_json(
            configs / "tail" / f"{kind}_w{wave}_s{shard:02d}.json",
            config,
        )
    _write_json(configs / "tail" / "manifest.json", tail_manifest)
    for wave in range(3):
        _write_json(
            output / "conv_graphs" / f"wave-{wave}.json",
            fresh_conv_wave_graph_spec(wave),
        )
        for shard in range(SHARD_COUNT):
            _write_json(
                output
                / "tail_graphs"
                / f"wave-{wave}-shard-{shard:02d}.json",
                tail_pair_graph_spec(wave, shard),
            )

    mapping_root = output / "mapping"
    mapping_root.mkdir(parents=True, exist_ok=True)
    conv_bindings: dict[str, Path] = {}
    for wave in range(3):
        op_id = f"op_w{wave}"
        bundle = mapping_root / "conv" / op_id
        if not (bundle / "bundle_manifest.json").is_file():
            create_mapping_evidence_bundle(
                ndp_sim_root=ndp,
                config_path=configs / "accumulate_waves" / f"wave-{wave}.json",
                output_dir=bundle,
                python_executable=python_executable,
                patchset_manifest_path=patchset_path,
            )
        conv_bindings[op_id] = bundle
    conv_exec = output / "execplan_conv"
    conv_exec.mkdir(parents=True, exist_ok=True)
    for wave in range(3):
        bundle = conv_exec / f"wave-{wave}"
        if not (bundle / "bundle_manifest.json").is_file():
            create_execplan_evidence_bundle(
                ndp_sim_root=ndp,
                graph_path=output / "conv_graphs" / f"wave-{wave}.json",
                mapping_bundles={f"op_w{wave}": conv_bindings[f"op_w{wave}"]},
                output_dir=bundle,
                python_executable=python_executable,
                patchset_manifest_path=patchset_path,
            )

    tail_bindings: dict[str, Path] = {}
    for wave in range(3):
        for shard in range(SHARD_COUNT):
            for kind in ("mul", "round"):
                op_id = _tail_op_id(kind, wave, shard)
                bundle = mapping_root / "tail" / op_id
                if not (bundle / "bundle_manifest.json").is_file():
                    create_mapping_evidence_bundle(
                        ndp_sim_root=ndp,
                        config_path=(
                            configs
                            / "tail"
                            / f"{kind}_w{wave}_s{shard:02d}.json"
                        ),
                        output_dir=bundle,
                        python_executable=python_executable,
                        patchset_manifest_path=patchset_path,
                        heuristic_iterations=2_000,
                        heuristic_restarts=4,
                    )
                tail_bindings[op_id] = bundle
    tail_exec = output / "execplan_tail"
    tail_exec.mkdir(parents=True, exist_ok=True)
    for wave in range(3):
        for shard in range(SHARD_COUNT):
            pair_id = f"wave-{wave}-shard-{shard:02d}"
            bundle = tail_exec / pair_id
            mul_id = _tail_op_id("mul", wave, shard)
            round_id = _tail_op_id("round", wave, shard)
            if not (bundle / "bundle_manifest.json").is_file():
                create_execplan_evidence_bundle(
                    ndp_sim_root=ndp,
                    graph_path=output / "tail_graphs" / f"{pair_id}.json",
                    mapping_bundles={
                        mul_id: tail_bindings[mul_id],
                        round_id: tail_bindings[round_id],
                    },
                    output_dir=bundle,
                    python_executable=python_executable,
                    patchset_manifest_path=patchset_path,
                    timeout_seconds=900,
                )
    return {
        "patchset": patchset_path,
        "conv_execplan": conv_exec,
        "tail_execplan": tail_exec,
        "mapping_count": len(conv_bindings) + len(tail_bindings),
    }


__all__ = [
    "CONFIG_REL",
    "CONTRACT_REL",
    "PATCHSET_REL",
    "ROOT_REL",
    "Node0004AssumedHardwareError",
    "build_fresh_accumulate_base",
    "build_tail_configs",
    "fresh_conv_graph_spec",
    "fresh_conv_wave_graph_spec",
    "load_fresh_physical_bundle",
    "load_fresh_w3_values",
    "local_numeric_report",
    "materialize_local_inputs",
    "materialize_mappings_and_execplans",
    "tail_graph_spec",
    "tail_pair_graph_spec",
]
