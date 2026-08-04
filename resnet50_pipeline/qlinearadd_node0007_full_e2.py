from __future__ import annotations

import json
import struct
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .add28_layout import (
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    QLinearAddPhysicalLayout,
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
from .operator_config_validator import OperatorConfigValidator
from .qlinearadd_predesign import _qlinearadd_records


SCHEMA = "qlinearadd-node0007-full-local-e2-v1"
NODE_ID = "node-0007"
HW_OP_ID = "hwop-0007-00"
CLAIM = "CONFIG_ONLY_CORRECTNESS_BASELINE"
USED_SLICES = "0b1111111111111111111111111111"
LANES = 8
LOCAL_ELEMENTS = 3 * 56 * 56 * 64
SPATIAL = LOCAL_ELEMENTS // LANES
ADD_LANES = 4
ADD_SPATIAL = LOCAL_ELEMENTS // ADD_LANES
DEQUANT_OCCURRENCES = LOCAL_ELEMENTS // 16
ROUND_OCCURRENCES = SPATIAL // 4
OUTER_TILES = 4
INNER_SPATIAL = SPATIAL // OUTER_TILES
INNER_ADD_SPATIAL = ADD_SPATIAL // OUTER_TILES
INNER_ROUND_OCCURRENCES = ROUND_OCCURRENCES // OUTER_TILES
RELOCATION_PAD_ELEMENTS = 33_792
RELOCATION_PAD_SPATIAL = RELOCATION_PAD_ELEMENTS // LANES
RELOCATION_PAD_BYTES = RELOCATION_PAD_ELEMENTS * 4
RECIPROCAL_BITS = "0x428c425c"
RECIPROCAL = np.asarray(
    [struct.unpack("<f", int(RECIPROCAL_BITS, 16).to_bytes(4, "little"))[0]],
    dtype=np.float32,
)[0]
LOCAL_BASES = {
    "op_a_dequant": {"A": 0, "D": 602_112},
    "op_b_dequant": {"A": 3_010_560, "D": 3_612_672},
    "op_relocation_pad": {"A": 6_021_120, "D": 6_156_288},
    "op_fp32_add": {"A": 602_112, "B": 3_612_672, "D": 8_388_608},
    "op_tail_mul": {"A": 8_388_608, "D": 10_797_056},
    "op_tail_round": {"A": 10_797_056, "D": 13_205_504},
}

ROOT_REL = Path(
    "artifacts/operator_config_validation/r5-qlinearadd-node0007-relocated-full-e2-v2"
)
CONFIG_REL = Path(
    "configs/native_ndp_sim/qlinearadd_node0007_relocated_full_e2_v2"
)
CONTRACT_REL = Path(
    "contracts/operator_config/qlinearadd_node0007_relocated_full_e2_v2.json"
)
PATCHSET_REL = Path(
    "contracts/ndp_patch_toolchain_qlinearadd_node0007_relocated_full_e2_v2.json"
)
RUNTIME_REL = Path("artifacts/w3/golden_batch16")
DEQUANT_TEMPLATE_REL = Path(
    "ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json"
)
ADD_TEMPLATE_REL = Path("ndp-sim/jsons/prefill_add_fp32MN_fp32MN_fp32MN.json")
TAIL_TEMPLATE_REL = Path(
    "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
)


class QLinearAddNode0007Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QLinearAddNode0007Error(f"JSON root must be object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _record(root: Path) -> dict[str, Any]:
    typed = _load(root / "contracts/typed_config_parameter_contract.json")
    matches = [
        item
        for item in _qlinearadd_records(typed)
        if item["node_id"] == NODE_ID and item["hw_op_id"] == HW_OP_ID
    ]
    if len(matches) != 1:
        raise QLinearAddNode0007Error("node0007 typed QLinearAdd record differs")
    return matches[0]


def _runtime_array(root: Path, tensor_id: str) -> np.ndarray:
    runtime_root = root / RUNTIME_REL
    manifest = _load(runtime_root / "manifest.json")
    item = manifest.get("tensors", {}).get(tensor_id)
    if not isinstance(item, Mapping):
        raise QLinearAddNode0007Error(f"missing W3 tensor: {tensor_id}")
    rel = item.get("path")
    if not isinstance(rel, str):
        raise QLinearAddNode0007Error(f"missing W3 tensor path: {tensor_id}")
    path = runtime_root / rel
    if sha256_file(path) != item.get("sha256"):
        raise QLinearAddNode0007Error(f"W3 tensor identity drifted: {tensor_id}")
    return np.load(path, allow_pickle=False)


def load_w3_values(root: Path) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    record = _record(root)
    q = record["qparams"]
    values = {
        "A": _runtime_array(root, record["tensors"]["a"]),
        "B": _runtime_array(root, record["tensors"]["b"]),
        "D": _runtime_array(root, record["tensors"]["y"]),
        "a_scale": np.asarray([q["a_scale"]["value"]], dtype=np.float32),
        "a_zero_point": np.asarray(
            [q["a_zero_point"]["value"]], dtype=np.uint8
        ),
        "b_scale": np.asarray([q["b_scale"]["value"]], dtype=np.float32),
        "b_zero_point": np.asarray(
            [q["b_zero_point"]["value"]], dtype=np.uint8
        ),
        "y_scale": np.asarray([q["y_scale"]["value"]], dtype=np.float32),
        "y_zero_point": np.asarray(
            [q["y_zero_point"]["value"]], dtype=np.uint8
        ),
    }
    if (
        values["A"].shape != (16, 256, 56, 56)
        or values["B"].shape != values["A"].shape
        or values["D"].shape != values["A"].shape
    ):
        raise QLinearAddNode0007Error("node0007 W3 tensor geometry differs")
    return record, values


def load_physical_bundle(root: Path):
    record, values = load_w3_values(root)
    layout = QLinearAddPhysicalLayout(
        profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE
    )
    bundle = layout.forward(
        a=values["A"],
        a_scale=values["a_scale"],
        a_zero_point=values["a_zero_point"],
        b=values["B"],
        b_scale=values["b_scale"],
        b_zero_point=values["b_zero_point"],
        y_scale=values["y_scale"],
        y_zero_point=values["y_zero_point"],
        output=values["D"],
        tensor_ids={
            "A": record["tensors"]["a"],
            "B": record["tensors"]["b"],
            "D": record["tensors"]["y"],
            "a_scale": "node0007:a_scale",
            "a_zero_point": "node0007:a_zero_point",
            "b_scale": "node0007:b_scale",
            "b_zero_point": "node0007:b_zero_point",
            "y_scale": "node0007:y_scale",
            "y_zero_point": "node0007:y_zero_point",
        },
    )
    return record, values, layout, bundle


def _port(src_id: object, mode: str | None, constant: object = 0) -> dict[str, Any]:
    return {
        "src_id": src_id,
        "mode": mode,
        "keep_last_index": None,
        "constant": constant,
    }


def _neg_zero_bits(value: int) -> str:
    bits = np.asarray([-float(value)], dtype=np.float32).view(np.uint32)[0]
    return f"0x{int(bits):08x}"


def _validate_config(config: dict[str, Any], name: str) -> None:
    report = OperatorConfigValidator().validate(
        config, source=f"qlinearadd node0007 {name}", development_mode=True
    )
    if not report.valid:
        raise QLinearAddNode0007Error(
            f"{name} strict config rejected: {report.to_dict()['first_error']}"
        )


def _dequant_config(
    template: dict[str, Any], *, scale_bits: str, zero_point: int, name: str
) -> dict[str, Any]:
    config = deepcopy(template)
    for key, end in {
        "LC1": DEQUANT_OCCURRENCES,
        "LC2": 1,
        "LC3": DEQUANT_OCCURRENCES,
        "LC4": 1,
    }.items():
        config["dram_loop_configs"][key]["end"] = end
    del config["buffer_loop_configs"]["GROUP1"]
    config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"] = 4
    del config["stream_engine"]["stream1"]
    config["stream_engine"]["stream0"]["dim_stride"] = [
        16,
        16,
        LOCAL_ELEMENTS,
    ]
    config["stream_engine"]["stream2"]["dim_stride"] = [
        64,
        64,
        0,
    ]
    del config["buffer_config"]["buffer2"]
    config["general_array"]["inport"]["inport1"]["mask"] = [0] * 8
    config["general_array"]["inport"]["inport1"]["uint8tofp32"] = "false"
    first = ("PE00", "PE02", "PE20", "PE22")
    second = (
        ("PE10", "PE00"),
        ("PE12", "PE02"),
        ("PE30", "PE20"),
        ("PE32", "PE22"),
    )
    pes: dict[str, Any] = {}
    for pe in first:
        pes[pe] = {
            "alu_opcode": "add",
            "transout_last_index": None,
            "inport2": _port(None, None),
            "inport1": _port(None, "constant", _neg_zero_bits(zero_point)),
            "inport0": _port(0, "buffer"),
        }
    for pe, predecessor in second:
        pes[pe] = {
            "alu_opcode": "mul",
            "transout_last_index": None,
            "inport2": _port(None, None),
            "inport1": _port(None, "constant", scale_bits),
            "inport0": _port(f"GA_PE.{predecessor}", "buffer"),
        }
    config["general_array"]["PE_array"] = pes
    _validate_config(config, name)
    return config


def _add_config(template: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(template)
    config["dram_loop_configs"]["LC0"].update(
        {"start": 0, "end": OUTER_TILES, "stride": 1, "last_index": 0}
    )
    for key in ("LC1", "LC2", "LC3"):
        config["dram_loop_configs"][key].update(
            {
                "start": 0,
                "end": INNER_ADD_SPATIAL,
                "stride": 1,
                "last_index": 1,
            }
        )
    for key in ("stream0", "stream1", "stream2"):
        stream = config["stream_engine"][key]
        stream["idx_size"] = [0, 15, None]
        stream["dim_stride"] = [16, INNER_ADD_SPATIAL * 16, None]
        stream["buf_spatial_stride"] = list(range(16))
        stream["buf_spatial_size"] = 16
    for group in config["buffer_loop_configs"].values():
        group["COL_LC"]["end"] = 16
        group["COL_LC"]["stride"] = 16
    config["general_array"]["PE_array"] = {
        pe: config["general_array"]["PE_array"][pe]
        for pe in ("PE00", "PE02", "PE20", "PE22")
    }
    _validate_config(config, "fp32_add")
    return config


def _conversion_flags(port: dict[str, Any]) -> None:
    port.update(
        {
            "fp16tofp32": "false",
            "bf16tofp32": "false",
            "int32tofp32": "false",
            "uint8tofp32": "false",
            "uint8toint32": "false",
        }
    )


def _tail_geometry(config: dict[str, Any], *, packed_output: bool) -> None:
    loops = config["dram_loop_configs"]
    loops["LC0"].update(
        {"start": 0, "end": OUTER_TILES, "stride": 1, "last_index": 0}
    )
    loops["LC1"].update(
        {"start": 0, "end": INNER_SPATIAL, "stride": 1, "last_index": 1}
    )
    loops["LC2"].update(
        {
            "start": 0,
            "end": (
                INNER_ROUND_OCCURRENCES if packed_output else INNER_SPATIAL
            ),
            "stride": 1,
            "last_index": 1,
        }
    )
    read = config["stream_engine"]["stream0"]
    read["idx_size"] = [0, 31, None]
    read["dim_stride"] = [32, INNER_SPATIAL * 32, None]
    read["buf_spatial_stride"] = list(range(16))
    read["buf_spatial_size"] = 16
    write = config["stream_engine"]["stream2"]
    write["idx_size"] = [3, 7, None] if packed_output else [0, 31, None]
    write["dim_stride"] = [
        32,
        (
            INNER_ROUND_OCCURRENCES * 32
            if packed_output
            else INNER_SPATIAL * 32
        ),
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
        if packed_output
        else list(range(16))
    )
    write["buf_spatial_size"] = 16


def _tail_configs(template: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    mul = deepcopy(template)
    _tail_geometry(mul, packed_output=False)
    _conversion_flags(mul["general_array"]["inport"]["inport0"])
    mul["general_array"]["outport"].update(
        {"src_id": 0, "int32touint8": "false"}
    )
    pes: dict[str, Any] = {}
    for pe_name in EVEN_PES:
        pe = deepcopy(template["general_array"]["PE_array"][pe_name])
        pe["alu_opcode"] = "mul"
        pe["inport0"].update({"src_id": 0, "mode": "buffer"})
        pe["inport1"].update(
            {
                "src_id": None,
                "mode": "constant",
                "constant": RECIPROCAL_BITS,
            }
        )
        pe["inport2"].update({"src_id": None, "mode": None, "constant": 0})
        pes[pe_name] = pe
    mul["general_array"]["PE_array"] = pes

    rounded = deepcopy(template)
    _tail_geometry(rounded, packed_output=True)
    _conversion_flags(rounded["general_array"]["inport"]["inport0"])
    rounded["general_array"]["outport"].update(
        {"src_id": 1, "int32touint8": "true"}
    )
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
                "constant": MAGIC_BITS,
            }
        )
    _validate_config(mul, "tail_mul")
    _validate_config(rounded, "tail_round")
    return mul, rounded


def _relocation_pad_config(template: dict[str, Any]) -> dict[str, Any]:
    config = deepcopy(template)
    loops = config["dram_loop_configs"]
    loops["LC0"].update({"start": 0, "end": 1, "stride": 1, "last_index": 0})
    loops["LC1"].update(
        {
            "start": 0,
            "end": RELOCATION_PAD_SPATIAL,
            "stride": 1,
            "last_index": 1,
        }
    )
    loops["LC2"].update(
        {
            "start": 0,
            "end": RELOCATION_PAD_SPATIAL,
            "stride": 1,
            "last_index": 1,
        }
    )
    for key in ("stream0", "stream2"):
        stream = config["stream_engine"][key]
        stream["idx_size"] = [0, 31, None]
        stream["dim_stride"] = [32, RELOCATION_PAD_BYTES, None]
        stream["buf_spatial_stride"] = list(range(16))
        stream["buf_spatial_size"] = 16
    _conversion_flags(config["general_array"]["inport"]["inport0"])
    config["general_array"]["outport"].update(
        {"src_id": 0, "int32touint8": "false"}
    )
    pes: dict[str, Any] = {}
    for pe_name in EVEN_PES:
        pe = deepcopy(template["general_array"]["PE_array"][pe_name])
        pe["alu_opcode"] = "mul"
        pe["inport0"].update({"src_id": 0, "mode": "buffer"})
        pe["inport1"].update(
            {"src_id": None, "mode": "constant", "constant": 1.0}
        )
        pe["inport2"].update({"src_id": None, "mode": None, "constant": 0})
        pes[pe_name] = pe
    config["general_array"]["PE_array"] = pes
    _validate_config(config, "relocation_pad")
    return config


def build_configs(root: Path) -> dict[str, dict[str, Any]]:
    record = _record(root)
    q = record["qparams"]
    dequant_template = _load(root / DEQUANT_TEMPLATE_REL)
    add_template = _load(root / ADD_TEMPLATE_REL)
    tail_template = _load(root / TAIL_TEMPLATE_REL)
    mul, rounded = _tail_configs(tail_template)
    configs = {
        "op_a_dequant": _dequant_config(
            dequant_template,
            scale_bits=q["a_scale"]["float32_bits"],
            zero_point=int(q["a_zero_point"]["value"]),
            name="a_dequant",
        ),
        "op_b_dequant": _dequant_config(
            dequant_template,
            scale_bits=q["b_scale"]["float32_bits"],
            zero_point=int(q["b_zero_point"]["value"]),
            name="b_dequant",
        ),
        "op_relocation_pad": _relocation_pad_config(tail_template),
        "op_fp32_add": _add_config(add_template),
        "op_tail_mul": mul,
        "op_tail_round": rounded,
    }
    for op_id, config in configs.items():
        for stream in config["stream_engine"].values():
            target = stream["target"]
            if target in LOCAL_BASES[op_id]:
                stream["base_addr"] = f"0x{LOCAL_BASES[op_id][target]:08x}"
        _validate_config(config, f"{op_id}_address_bound_static")
    return configs


def graph_spec() -> dict[str, Any]:
    shape = [1, SPATIAL, LANES]
    pad_shape = [1, RELOCATION_PAD_SPATIAL, LANES]

    def tensor(
        dtype: str,
        source: dict[str, Any] | None = None,
        *,
        tensor_shape: list[int] | None = None,
    ) -> dict[str, Any]:
        value = {
            "shape": tensor_shape or shape,
            "dtype": dtype,
            "bank_interleave": 1,
            "remapping": None,
        }
        if source is not None:
            value["source"] = source
        return value

    return {
        "params": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "claim": CLAIM,
            "physical_layout": "w4_qlinearadd_group4x7_28_candidate_v1",
        },
        "used_slices": USED_SLICES,
        "operators": [
            {
                "id": "op_a_dequant",
                "type": "resnet50_qadd_node0007_a_dequant",
                "used_slices": USED_SLICES,
                "inputs": {"A": tensor("uint8", {"type": "external"})},
                "output": tensor("fp32"),
            },
            {
                "id": "op_b_dequant",
                "type": "resnet50_qadd_node0007_b_dequant",
                "used_slices": USED_SLICES,
                "inputs": {"A": tensor("uint8", {"type": "external"})},
                "output": tensor("fp32"),
            },
            {
                "id": "op_relocation_pad",
                "type": "resnet50_qadd_node0007_relocation_pad",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": tensor(
                        "fp32",
                        {"type": "external"},
                        tensor_shape=pad_shape,
                    )
                },
                "output": tensor("fp32", tensor_shape=pad_shape),
            },
            {
                "id": "op_fp32_add",
                "type": "resnet50_qadd_node0007_fp32_add",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": tensor(
                        "fp32",
                        {"type": "operator", "operator_id": "op_a_dequant"},
                    ),
                    "B": tensor(
                        "fp32",
                        {"type": "operator", "operator_id": "op_b_dequant"},
                    ),
                },
                "output": tensor("fp32"),
            },
            {
                "id": "op_tail_mul",
                "type": "resnet50_qadd_node0007_tail_mul",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": tensor(
                        "fp32",
                        {"type": "operator", "operator_id": "op_fp32_add"},
                    )
                },
                "output": tensor("fp32"),
            },
            {
                "id": "op_tail_round",
                "type": "resnet50_qadd_node0007_tail_round",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": tensor(
                        "fp32",
                        {"type": "operator", "operator_id": "op_tail_mul"},
                    )
                },
                "output": tensor("uint8"),
            },
        ],
    }


def scalar_tail_proof(root: Path) -> dict[str, Any]:
    record = _record(root)
    q = record["qparams"]
    a = np.arange(256, dtype=np.float32)[:, None]
    b = np.arange(256, dtype=np.float32)[None, :]
    a_scaled = np.float32(
        np.float32(a + np.float32(-q["a_zero_point"]["value"]))
        * np.float32(q["a_scale"]["value"])
    )
    b_scaled = np.float32(
        np.float32(b + np.float32(-q["b_zero_point"]["value"]))
        * np.float32(q["b_scale"]["value"])
    )
    summed = np.float32(a_scaled + b_scaled)
    divided = np.float32(summed / np.float32(q["y_scale"]["value"]))
    multiplied = np.float32(summed * RECIPROCAL)
    rne_div = np.rint(divided).astype(np.int32)
    rne_mul = np.rint(multiplied).astype(np.int32)
    magic = (
        np.float32(multiplied + np.float32(MAGIC_FLOAT))
        .view(np.int32)
        .astype(np.int64)
        - MAGIC_BITS
    )
    y0 = np.clip(rne_div + int(q["y_zero_point"]["value"]), 0, 255).astype(
        np.uint8
    )
    y1 = np.clip(rne_mul + int(q["y_zero_point"]["value"]), 0, 255).astype(
        np.uint8
    )
    y2 = np.clip(magic + int(q["y_zero_point"]["value"]), 0, 255).astype(
        np.uint8
    )
    return {
        "domain": "all 65536 scalar uint8 A/B pairs",
        "numeric_analysis_scope": "tail-only; reused stage0 analysis was not repeated",
        "reciprocal_bits": RECIPROCAL_BITS,
        "division_vs_reciprocal_fp32_bit_mismatch_count": int(
            np.count_nonzero(divided.view(np.uint32) != multiplied.view(np.uint32))
        ),
        "division_rne_vs_reciprocal_rne_uint8_mismatch_count": int(
            np.count_nonzero(y0 != y1)
        ),
        "reciprocal_rne_vs_magic_uint8_mismatch_count": int(
            np.count_nonzero(y1 != y2)
        ),
        "scaled_min": float(multiplied.min()),
        "scaled_max": float(multiplied.max()),
        "finite": bool(np.isfinite(multiplied).all()),
    }


def config_bound_simulator(root: Path) -> dict[str, Any]:
    record, values, layout, bundle = load_physical_bundle(root)
    q = record["qparams"]
    actual_payloads: dict[tuple[str, int], bytes] = {}
    mismatch = 0
    padding_mismatch = 0
    ordered = bytearray()
    for slice_id in range(28):
        a = np.frombuffer(
            bundle.read("A", slice_id)[:LOCAL_ELEMENTS], dtype=np.uint8
        )
        b = np.frombuffer(
            bundle.read("B", slice_id)[:LOCAL_ELEMENTS], dtype=np.uint8
        )
        af = a.astype(np.float32)
        bf = b.astype(np.float32)
        a_scaled = np.float32(
            np.float32(af + np.float32(-q["a_zero_point"]["value"]))
            * np.float32(q["a_scale"]["value"])
        )
        b_scaled = np.float32(
            np.float32(bf + np.float32(-q["b_zero_point"]["value"]))
            * np.float32(q["b_scale"]["value"])
        )
        summed = np.float32(a_scaled + b_scaled)
        multiplied = np.float32(summed * RECIPROCAL)
        rounded = (
            np.float32(multiplied + np.float32(MAGIC_FLOAT))
            .view(np.int32)
            .astype(np.int64)
            - MAGIC_BITS
            + int(q["y_zero_point"]["value"])
        )
        output = np.clip(rounded, 0, 255).astype(np.uint8)
        raw = output.tobytes()
        expected = bundle.read("D", slice_id)[:LOCAL_ELEMENTS]
        mismatch += sum(x != y for x, y in zip(raw, expected, strict=True))
        region = bundle.region("D", slice_id)
        padding = bytes(region.size_bytes - region.payload_bytes)
        actual_payloads[("D", slice_id)] = raw + padding
        padding_mismatch += sum(
            byte != int(q["y_zero_point"]["value"])
            for byte in output[region.payload_bytes :]
        )
        ordered.extend(raw)

    simulated_bundle = bundle.__class__(
        **{
            **bundle.__dict__,
            "payloads": {
                **bundle.payloads,
                **actual_payloads,
            },
        }
    )
    inverse = layout.inverse_port(simulated_bundle, record["tensors"]["y"])
    logical_mismatch = int(np.count_nonzero(inverse != values["D"]))
    if mismatch or logical_mismatch or padding_mismatch:
        raise QLinearAddNode0007Error(
            "config-bound output mismatch: "
            f"physical={mismatch}, logical={logical_mismatch}, "
            f"padding={padding_mismatch}"
        )
    return {
        "simulator": "final-config constants and five-stage W3 operation order",
        "host_precomputed_internal_tensor": False,
        "preloaded_tensors": ["A", "B", "FROZEN_ZERO_RELOCATION_PAD"],
        "relocation_pad": {
            "input_kind": "frozen FP32 zero constant",
            "input_bytes_per_slice": RELOCATION_PAD_BYTES,
            "hardware_output_bytes_per_slice": RELOCATION_PAD_BYTES,
            "hardware_operation": "FP32 multiply by 1.0",
            "qlinearadd_internal_tensor": False,
            "output_consumed_by_qlinearadd": False,
        },
        "logical_elements": int(values["D"].size),
        "per_slice_physical_elements": LOCAL_ELEMENTS,
        "active_slices": 28,
        "physical_output_bytes": LOCAL_ELEMENTS * 28,
        "physical_mismatch_count": mismatch,
        "logical_mismatch_count": logical_mismatch,
        "padding_mismatch_count": padding_mismatch,
        "output_sha256": sha256_bytes(bytes(ordered)),
        "golden_logical_sha256": sha256_bytes(
            np.ascontiguousarray(values["D"]).tobytes()
        ),
    }


def materialize_local_inputs(
    root: Path, output_root: Path, config_root: Path
) -> dict[str, Any]:
    root = root.resolve()
    output = output_root.resolve()
    configs_root = config_root.resolve()
    if output.exists() or configs_root.exists():
        raise QLinearAddNode0007Error("fresh output/config roots required")
    output.mkdir(parents=True)
    configs_root.mkdir(parents=True)
    configs = build_configs(root)
    for op_id, config in configs.items():
        _write_json(configs_root / f"{op_id}.json", config)
    graph = graph_spec()
    graph_path = output / "graph.json"
    _write_json(graph_path, graph)
    patchset_path = root / PATCHSET_REL
    _write_json(
        patchset_path,
        build_patchset_manifest(
            root / "ndp-sim",
            patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID,
        ),
    )
    proof = scalar_tail_proof(root)
    sim = config_bound_simulator(root)
    _write_json(output / "scalar_tail_proof.json", proof)
    _write_json(output / "config_bound_simulator.json", sim)
    receipt = {
        "schema": SCHEMA,
        "status": "LOCAL_INPUTS_MATERIALIZED",
        "node_id": NODE_ID,
        "hw_op_id": HW_OP_ID,
        "numeric_analysis_repeated": False,
        "reuse_assets_consumed": {
            "stage0_17_instance_contract": {
                "path": "contracts/operator_config/qlinearadd_stage0_config_only_contract_v1.json",
                "sha256": sha256_file(
                    root
                    / "contracts/operator_config/qlinearadd_stage0_config_only_contract_v1.json"
                ),
                "scope": "node0007 SUM_F32 stage ordering, qparams, readiness and lifetime",
            },
            "node0004_shared_tail": {
                "path": "resnet50_pipeline/node0004_assumed_hardware.py",
                "sha256": sha256_file(
                    root / "resnet50_pipeline/node0004_assumed_hardware.py"
                ),
                "scope": "two-stage exact UINT8 tail structure and primitive semantics",
            },
        },
        "configs": {
            op_id: {
                "path": (CONFIG_REL / f"{op_id}.json").as_posix(),
                "sha256": sha256_file(configs_root / f"{op_id}.json"),
            }
            for op_id in configs
        },
        "graph": {
            "path": (ROOT_REL / "graph.json").as_posix(),
            "sha256": sha256_file(graph_path),
        },
        "scalar_tail_proof": proof,
        "config_bound_simulator": sim,
    }
    _write_json(output / "local_input_receipt.json", receipt)
    return receipt


def materialize_mapping_and_execplan(
    root: Path,
    output_root: Path,
    config_root: Path,
    python_executable: Path,
) -> dict[str, Any]:
    root = root.resolve()
    output = output_root.resolve()
    configs_root = config_root.resolve()
    patchset_path = root / PATCHSET_REL
    mapping: dict[str, Path] = {}
    for op in graph_spec()["operators"]:
        op_id = op["id"]
        bundle = output / "mapping" / op_id
        if not (bundle / "bundle_manifest.json").is_file():
            create_mapping_evidence_bundle(
                ndp_sim_root=root / "ndp-sim",
                config_path=configs_root / f"{op_id}.json",
                output_dir=bundle,
                python_executable=python_executable,
                patchset_manifest_path=patchset_path,
                heuristic_iterations=2_000,
                heuristic_restarts=4,
                timeout_seconds=600,
            )
        mapping[op_id] = bundle
    execplan = output / "execplan"
    if not (execplan / "bundle_manifest.json").is_file():
        create_execplan_evidence_bundle(
            ndp_sim_root=root / "ndp-sim",
            graph_path=output / "graph.json",
            mapping_bundles=mapping,
            output_dir=execplan,
            python_executable=python_executable,
            patchset_manifest_path=patchset_path,
            timeout_seconds=900,
        )
    result = {
        "mapping_count": len(mapping),
        "execplan_bundle": execplan.relative_to(root).as_posix(),
        "execplan_bundle_manifest_sha256": sha256_file(
            execplan / "bundle_manifest.json"
        ),
    }
    _write_json(output / "native_chain_receipt.json", result)
    return result


__all__ = [
    "CONFIG_REL",
    "CONTRACT_REL",
    "PATCHSET_REL",
    "ROOT_REL",
    "QLinearAddNode0007Error",
    "build_configs",
    "config_bound_simulator",
    "graph_spec",
    "load_physical_bundle",
    "load_w3_values",
    "materialize_local_inputs",
    "materialize_mapping_and_execplan",
    "scalar_tail_proof",
]
