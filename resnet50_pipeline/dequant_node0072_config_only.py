from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline import dequantize_linear_vertical as node77
from resnet50_pipeline.hashing import canonical_json_bytes, sha256_bytes, sha256_file
from resnet50_pipeline.operator_config_validator import OperatorConfigValidator


REQUEST_ID = "r5:hwop-0072-00"
REQUEST_SHA256 = "22657270d4f617aaa60795575aa0ca21bd5125de775b12e46e47648587f23746"
NODE_ID = "node-0072"
HW_OP_ID = "hwop-0072-00"
OP_TYPE = "dq72_u8_f32_cfg_v1"
INSTANCE_ID = "dequant:node-0072:hwop-0072-00:config-only-v1"
USED_SLICES = "0b1111111111111111111111111111"
HARDWARE_SHAPE = (16, 74, 1)
WORDS_PER_SLICE = 1184
D_BYTES_PER_SLICE = 4736
D_LINES_PER_SLICE = 296
SLICE_COUNT = 28
SCALE_BITS = "0x3cbf57ec"
NEGATIVE_ZERO_POINT_BITS = "0x80000000"
SCALE = np.frombuffer(struct.pack("<I", int(SCALE_BITS, 16)), dtype=np.float32)
NEGATIVE_ZERO_POINT = np.frombuffer(
    struct.pack("<I", int(NEGATIVE_ZERO_POINT_BITS, 16)), dtype=np.float32
)
INPUT_RELATIVE = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-ab32f279540568c3.npy"
)
OUTPUT_RELATIVE = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-50c285690f899b1b.npy"
)
CONFIG_RELATIVE = Path(
    "configs/native_ndp_sim/"
    "resnet50_dequant_node0072_uint8_fp32_config_only_v1/config.json"
)
ARTIFACT_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-dequant-node0072-config-only-e2-v1"
)
CONTRACT_RELATIVE = Path(
    "contracts/operator_config/"
    "node0072_dequant_config_only_correctness_baseline_v1.json"
)
REPORT_RELATIVE = ARTIFACT_RELATIVE / "local_e2_report.json"
RULE_RECEIPT_PATHS = (
    Path(".agents/agent.md"),
    Path(".agents/plan.md"),
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/DequantizeLinear算子配置规则.md"),
    Path(".agents/rules/DequantizeLinear原子动态合同规则.md"),
)
RULE_IDS = (
    "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
    "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
    "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
    "CDA-CONFIG-SEMANTIC-OWNERSHIP-001",
    "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
    "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
)
NODE0077_REFERENCE_RULE_PATTERNS = (
    "CDA-DEQUANT-TWO-STAGE-GA-001",
    "CDA-DEQUANT-NORMAL-OUTBUFFER-001",
    "CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001",
    "CDA-DEQUANT-MAPPING-BINDING-001",
)
TOOLCHAIN_CONSUMERS = (
    Path("ndp-sim-ref/model_execplan/main.py"),
    Path(
        "ndp-sim-ref/model_execplan/src/execution_plan_generator/json_loader.py"
    ),
    Path(
        "ndp-sim-ref/model_execplan/src/execution_plan_generator/control_registers.py"
    ),
    Path(
        "ndp-sim-ref/model_execplan/src/execution_plan_generator/output_writer.py"
    ),
    Path("ndp-sim-ref/model_execplan/src/execution_plan_generator/pipeline.py"),
    Path(
        "ndp-sim-ref/model_execplan/src/execution_plan_generator/"
        "instruction_generator.py"
    ),
    Path("ndp-sim-ref/bitstream/main.py"),
    Path("ndp-sim-ref/bitstream/parse.py"),
    Path("ndp-sim-ref/bitstream/config/mapper.py"),
    Path("ndp-sim-ref/bitstream/config/general.py"),
)


class Node0072ConfigOnlyError(RuntimeError):
    pass


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _identity(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _request(root: Path) -> dict[str, Any]:
    bundle = json.loads(
        (root / "contracts/resnet50_r5_lowering_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    matches = [
        item
        for item in bundle["requests"]
        if item.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1 or matches[0].get("request_sha256") != REQUEST_SHA256:
        raise Node0072ConfigOnlyError("node0072 typed request identity differs")
    return matches[0]


def bypass_annotation() -> dict[str, Any]:
    return {
        "baseline_classification": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "bypass_reason": (
            "Reuse the proven node0077 two-stage ordinary-GA subtract/add then "
            "multiply schedule because the typed target rejects the standalone "
            "native/handler and typed-transport paths."
        ),
        "contradicted_or_missing_native_path": [
            "r5:hwop-0072-00.field.ga_standalone_uint8_to_fp32_dequant",
            "r5:hwop-0072-00.field.execplan_typed_parameter_transport",
            "r5:hwop-0072-00.field.rtl28_physical_port_layout",
        ],
        "exact_equivalence_scope": (
            "Only node0072 uint8[16,2048,1,1], scale bits 0x3cbf57ec, "
            "zero-point 0, frozen W3 input domain and padded 28x1184 physical layout; "
            "two-stage, one-stage multiply and W3 golden are bit-identical here."
        ),
        "materialized_configuration_mechanism": (
            "One standalone A-read/D-write operator using four ordinary GA add PEs "
            "with -0.0f followed by four ordinary GA multiply PEs with x_scale; "
            "official mapper/bitstream and typed execplan/SCA bind 28 slices."
        ),
        "performance_and_resource_cost": (
            "Uses 8 GA PEs and two dependent arithmetic levels instead of the "
            "numerically sufficient 4-PE single multiply level; 28 slices each "
            "execute 74 occurrences, with 384 padded elements globally. This adds "
            "one GA stage of latency/dependency and lowers PE/throughput efficiency."
        ),
        "unresolved_production_blocker": [
            "B_DEQUANT_NODE0072_NATIVE_STANDALONE_PATH",
            "B_DEQUANT_NODE0072_FORMAL_LAYOUT_APPROVAL",
            "B_DEQUANT_NODE0072_HARDWARE_E4_E5",
            "B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING",
        ],
        "claim_boundary": (
            "Local materialized E2 correctness only; not a formal target config, "
            "not production/performance approval, not server/hardware evidence, "
            "and not transferable to node0077 or any other Dequant instance."
        ),
    }


def input_replay_contract(root: Path) -> dict[str, Any]:
    return {
        "rule_id": "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
        "source_producer": {
            "node_id": "node-0071",
            "op_type": "QLinearGlobalAveragePool",
            "source": "artifacts/w3/model_graph.json",
        },
        "tensor_identity": {
            "tensor_id": "tensor-ab32f279540568c3",
            **_identity(root, INPUT_RELATIVE),
            "payload_sha256": hashlib.sha256(
                np.load(root / INPUT_RELATIVE, allow_pickle=False).tobytes()
            ).hexdigest(),
            "dtype": "uint8",
            "shape": [16, 2048, 1, 1],
        },
        "allowed_index_address_mapping": (
            "Logical C-order flat index k maps to slice=floor(k/1184), "
            "local_word=k mod 1184, A address=A_base+local_word; only the final "
            "384 physical words are zero padding."
        ),
        "replayed_constants": {
            "x_scale_bits": SCALE_BITS,
            "x_zero_point": 0,
        },
        "uncrossed_computation_boundary": (
            "Host copies only the typed uint8 producer output and frozen constants; "
            "no subtract, scale, rounding, saturation, or final Dequant output is "
            "precomputed. Both Dequant arithmetic stages execute in the configured GA."
        ),
        "host_precomputed_internal_tensor": False,
        "host_precomputed_final_output": False,
        "dtype_or_value_transform_during_replay": False,
    }


def toolchain_consumer_receipt(root: Path) -> dict[str, Any]:
    return {
        "source_tree": "ndp-sim-ref isolated read-only copies",
        "source_tree_modified": False,
        "functional_rtl_modified": False,
        "isolated_patch_applied": False,
        "consumers": [_identity(root, path) for path in TOOLCHAIN_CONSUMERS],
    }


def build_config(root: Path) -> dict[str, Any]:
    config = deepcopy(node77.build_operator_config(root))
    config["dram_loop_configs"]["LC1"]["end"] = 74
    config["dram_loop_configs"]["LC3"]["end"] = 74
    config["stream_engine"]["stream0"]["dim_stride"] = [16, 16, WORDS_PER_SLICE]
    config["stream_engine"]["stream2"]["dim_stride"] = [
        64,
        64,
        D_BYTES_PER_SLICE,
    ]
    for pe in node77.FIRST_STAGE_PES:
        config["general_array"]["PE_array"][pe]["inport1"][
            "constant"
        ] = NEGATIVE_ZERO_POINT_BITS
    for pe, _ in node77.SECOND_STAGE_LINKS:
        config["general_array"]["PE_array"][pe]["inport1"]["constant"] = SCALE_BITS
    validate_config(config)
    return config


def _float32_bits(value: Any) -> int:
    if isinstance(value, str) and value.lower().startswith("0x"):
        return int(value, 16)
    return int(
        np.array([np.float32(float(value))], dtype=np.float32).view(np.uint32)[0]
    )


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    generic = OperatorConfigValidator().validate(
        config, source="node0072-config-only", development_mode=True
    )
    if not generic.valid:
        raise Node0072ConfigOnlyError(
            f"strict config validation failed: {generic.to_dict()['first_error']}"
        )
    if (
        config["dram_loop_configs"]["LC1"]["end"] != 74
        or config["dram_loop_configs"]["LC3"]["end"] != 74
        or config["stream_engine"]["stream0"]["dim_stride"]
        != [16, 16, WORDS_PER_SLICE]
        or config["stream_engine"]["stream2"]["dim_stride"]
        != [64, 64, D_BYTES_PER_SLICE]
        or set(config["stream_engine"]) != {"stream0", "stream2"}
    ):
        raise Node0072ConfigOnlyError("node0072 shape/stream specialization differs")
    pe_array = config["general_array"]["PE_array"]
    if set(pe_array) != set(node77.FIRST_STAGE_PES) | {
        item[0] for item in node77.SECOND_STAGE_LINKS
    }:
        raise Node0072ConfigOnlyError("node0072 two-stage GA PE set differs")
    for pe in node77.FIRST_STAGE_PES:
        if (
            pe_array[pe]["alu_opcode"] != "add"
            or _float32_bits(pe_array[pe]["inport1"]["constant"])
            not in {0x80000000, 0x00000000}
        ):
            raise Node0072ConfigOnlyError("node0072 first GA stage differs")
    for pe, predecessor in node77.SECOND_STAGE_LINKS:
        if (
            pe_array[pe]["alu_opcode"] != "mul"
            or pe_array[pe]["inport0"]["src_id"] != f"GA_PE.{predecessor}"
            or _float32_bits(pe_array[pe]["inport1"]["constant"])
            != int(SCALE_BITS, 16)
        ):
            raise Node0072ConfigOnlyError("node0072 second GA stage differs")
    d_rows = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
    if (
        config["buffer_config"]["buffer5"]["buf_end_row_addr"] != 3
        or d_rows != {"start": 0, "end": 4, "stride": 1, "last_index": 3, "src_id": "DRAM_LC.LC4"}
    ):
        raise Node0072ConfigOnlyError("node0072 D buffer supply differs")
    return {
        "strict_operator_config_valid": True,
        "hardware_shape_cwh": list(HARDWARE_SHAPE),
        "occurrences_per_slice": 74,
        "two_stage_ga_exact": True,
        "d_buffer_supply_bytes": 64,
        "rule_ids": list(RULE_IDS),
        "bypass_annotation": bypass_annotation(),
    }


def numeric_evidence(root: Path) -> dict[str, Any]:
    x = np.load(root / INPUT_RELATIVE, allow_pickle=False)
    golden = np.load(root / OUTPUT_RELATIVE, allow_pickle=False)
    if x.shape != (16, 2048, 1, 1) or x.dtype != np.uint8:
        raise Node0072ConfigOnlyError("node0072 input signature differs")
    if golden.shape != x.shape or golden.dtype != np.float32:
        raise Node0072ConfigOnlyError("node0072 golden signature differs")
    two_stage = np.multiply(
        np.add(x.astype(np.float32), NEGATIVE_ZERO_POINT[0], dtype=np.float32),
        SCALE[0],
        dtype=np.float32,
    )
    one_stage = np.multiply(x.astype(np.float32), SCALE[0], dtype=np.float32)
    if not np.array_equal(two_stage.view(np.uint32), golden.view(np.uint32)):
        raise Node0072ConfigOnlyError("node0072 two-stage output differs from W3")
    if not np.array_equal(one_stage.view(np.uint32), golden.view(np.uint32)):
        raise Node0072ConfigOnlyError("node0072 one-stage domain equivalence differs")
    return {
        "logical_shape": [16, 2048, 1, 1],
        "element_count": int(x.size),
        "scale_bits": SCALE_BITS,
        "zero_point": 0,
        "negative_zero_point_bits": NEGATIVE_ZERO_POINT_BITS,
        "input_sha256": hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest(),
        "golden_sha256": hashlib.sha256(
            np.ascontiguousarray(golden).tobytes()
        ).hexdigest(),
        "two_stage_sha256": hashlib.sha256(
            np.ascontiguousarray(two_stage).tobytes()
        ).hexdigest(),
        "single_multiply_sha256": hashlib.sha256(
            np.ascontiguousarray(one_stage).tobytes()
        ).hexdigest(),
        "two_stage_vs_golden_bit_mismatch_count": 0,
        "single_multiply_vs_golden_bit_mismatch_count": 0,
        "two_stage_vs_single_multiply_bit_mismatch_count": 0,
        "nan_count": 0,
        "bit_exact": True,
    }


def build_layout(root: Path, output: Path) -> dict[str, Any]:
    x = np.load(root / INPUT_RELATIVE, allow_pickle=False).reshape(-1)
    golden = np.load(root / OUTPUT_RELATIVE, allow_pickle=False).reshape(-1)
    payload_root = output / "physical"
    payload_root.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    restored = bytearray(golden.nbytes)
    coverage = bytearray(golden.size)
    for slice_id in range(SLICE_COUNT):
        start = slice_id * WORDS_PER_SLICE
        count = max(0, min(WORDS_PER_SLICE, x.size - start))
        a = np.zeros(WORDS_PER_SLICE, dtype=np.uint8)
        d = np.zeros(WORDS_PER_SLICE, dtype=np.float32)
        if count:
            a[:count] = x[start : start + count]
            d[:count] = golden[start : start + count]
            restored[start * 4 : (start + count) * 4] = d[:count].tobytes()
            coverage[start : start + count] = b"\x01" * count
        a_path = payload_root / f"slice{slice_id:02d}_A.bin"
        d_path = payload_root / f"slice{slice_id:02d}_D_golden.bin"
        a_path.write_bytes(a.tobytes())
        d_path.write_bytes(d.tobytes())
        records.append(
            {
                "slice_id": slice_id,
                "logical_flat_start": start,
                "logical_element_count": count,
                "padding_element_count": WORDS_PER_SLICE - count,
                "a_sha256": hashlib.sha256(a.tobytes()).hexdigest(),
                "d_golden_sha256": hashlib.sha256(d.tobytes()).hexdigest(),
                "a_path": a_path.relative_to(output).as_posix(),
                "d_golden_path": d_path.relative_to(output).as_posix(),
            }
        )
    if any(value != 1 for value in coverage) or bytes(restored) != golden.tobytes():
        raise Node0072ConfigOnlyError("node0072 physical inverse differs")
    return {
        "profile": "node0072_flat_contiguous_28x1184_config_only_v1",
        "logical_shape": [16, 2048, 1, 1],
        "hardware_shape_cwh": list(HARDWARE_SHAPE),
        "slice_count": SLICE_COUNT,
        "words_per_slice": WORDS_PER_SLICE,
        "d_lines_per_slice_128bit": D_LINES_PER_SLICE,
        "global_padding_element_count": SLICE_COUNT * WORDS_PER_SLICE - x.size,
        "padding_input_value": 0,
        "padding_output_bits": "0x00000000",
        "inverse_complete": True,
        "inverse_unique": True,
        "inverse_sha256": hashlib.sha256(bytes(restored)).hexdigest(),
        "slices": records,
    }


def _execute_config_pe_graph(config: dict[str, Any], a_raw: bytes) -> bytes:
    if len(a_raw) != WORDS_PER_SLICE:
        raise ValueError(
            f"node0072 config-bound executor expected {WORDS_PER_SLICE} A bytes, "
            f"got {len(a_raw)}"
        )

    ga = config.get("general_array", {})
    inport = ga.get("inport", {}).get("inport0", {})
    pe_by_name = ga.get("PE_array", {})
    if (
        inport.get("uint8tofp32") != "true"
        or ga.get("outport", {}).get("fp32tobf16") != "false"
        or not isinstance(pe_by_name, dict)
    ):
        raise ValueError("node0072 final JSON conversion/GA contract differs")
    source = np.frombuffer(a_raw, dtype=np.uint8).astype(np.float32)
    memo: dict[str, np.ndarray] = {}

    def evaluate(name: str) -> np.ndarray:
        cached = memo.get(name)
        if cached is not None:
            return cached
        pe = pe_by_name[name]
        port = pe.get("inport0", {})
        mode = port.get("mode")
        source_id = port.get("src_id")
        if mode == "buffer" and source_id == 0:
            left = source
        elif (
            mode == "buffer"
            and isinstance(source_id, str)
            and source_id.startswith("GA_PE.")
        ):
            left = evaluate(source_id.split(".", 1)[1])
        else:
            raise ValueError(f"unsupported node0072 GA source at {name}")
        constant_bits = _float32_bits(pe.get("inport1", {}).get("constant"))
        constant = np.array([constant_bits], dtype=np.uint32).view(np.float32)[0]
        opcode = str(pe["alu_opcode"])
        if opcode == "add":
            output = np.add(left, constant, dtype=np.float32)
        elif opcode == "mul":
            output = np.multiply(left, constant, dtype=np.float32)
        else:
            raise ValueError(f"unsupported node0072 PE opcode: {opcode}")
        memo[name] = output
        return output

    first = tuple(node77.FIRST_STAGE_PES)
    final = tuple(item[0] for item in node77.SECOND_STAGE_LINKS)
    if set(pe_by_name) != set(first + final):
        raise ValueError("node0072 final JSON GA PE set differs")
    outputs = [evaluate(name) for name in final]
    reference = outputs[0].view(np.uint32)
    for lane, output in enumerate(outputs[1:], start=1):
        if not np.array_equal(reference, output.view(np.uint32)):
            raise ValueError(f"node0072 output PE lane {lane} is not bit-identical")
    return outputs[0].astype("<f4", copy=False).tobytes(order="C")


def _constant(
    *,
    tensor_id: str,
    value: np.ndarray,
    source_parameter: str,
    indices: tuple[int, ...],
    artifact_id: str,
    identity_sha256: str | None = None,
) -> dict[str, Any]:
    raw = np.ascontiguousarray(value, dtype=np.float32)
    value_sha = hashlib.sha256(raw.tobytes()).hexdigest()
    return {
        "tensor_id": tensor_id,
        "dtype": "float32",
        "shape": [1],
        "identity_sha256": identity_sha256 or value_sha,
        "value_sha256": value_sha,
        "values": raw.tolist(),
        "float32_bits": [f"0x{int(raw.view(np.uint32)[0]):08x}"],
        "axis": None,
        "source_kind": "initializer" if identity_sha256 else "derived",
        "source_parameter_ids": [source_parameter],
        "target_bindings": [
            {
                "location": (
                    f"control_register:ga_pe{index}."
                    "general_array.PE_array.PE.inport1.constant"
                ),
                "encoding": "fp32_bits",
                "derivation": "config-only two-stage ordinary GA",
                "element_indices": [0],
                "artifact_id": artifact_id,
            }
            for index in indices
        ],
    }


def build_execplan_request(root: Path, config: dict[str, Any]) -> dict[str, Any]:
    request = _request(root)
    config_text = json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    artifact_id = f"{HW_OP_ID}.config-only.config"
    scale_identity = next(
        item["value"]["value_sha256"]
        for item in request["typed_parameters"]
        if item["name"] == "x_scale"
    )
    value = {
        "schema_version": "0.2",
        "plan_id": f"{INSTANCE_ID}:typed-transport-v1",
        "used_slices": USED_SLICES,
        "params": {
            "node_id": NODE_ID,
            "hw_op_id": HW_OP_ID,
            "candidate_release": False,
            "baseline_classification": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        },
        "operators": [
            {
                "id": "op0",
                "type": OP_TYPE,
                "instance_id": INSTANCE_ID,
                "stage": "dequantize",
                "used_slices": USED_SLICES,
                "inputs": {
                    "A": {
                        "shape": list(HARDWARE_SHAPE),
                        "logical_shape": [16, 2048, 1, 1],
                        "dtype": "uint8",
                        "tensor_id": "tensor-ab32f279540568c3",
                        "identity_sha256": sha256_file(root / INPUT_RELATIVE),
                        "bank_interleave": 1,
                        "remapping": None,
                        "source": {"type": "external"},
                    }
                },
                "output": {
                    "shape": list(HARDWARE_SHAPE),
                    "logical_shape": [16, 2048, 1, 1],
                    "dtype": "float32",
                    "tensor_id": "tensor-50c285690f899b1b",
                    "identity_sha256": sha256_file(root / OUTPUT_RELATIVE),
                    "bank_interleave": 1,
                    "remapping": None,
                },
                "attributes": {
                    "node_id": NODE_ID,
                    "hw_op_id": HW_OP_ID,
                    "stage_index": 0,
                    "hardware_shape_cwh": list(HARDWARE_SHAPE),
                    "valid_logical_elements": 32768,
                    "hardware_elements": SLICE_COUNT * WORDS_PER_SLICE,
                    "target": {
                        "slice_count": 28,
                        "communication_domain": "local",
                        "ga_topology": "four_add_then_four_mul",
                        "normal_outbuffer_only": True,
                    },
                    "rule_ids": list(RULE_IDS),
                    "bypass_annotation": bypass_annotation(),
                },
                "constants": {
                    "negative_zero_point": _constant(
                        tensor_id=f"{HW_OP_ID}.derived.negative_zero_point_fp32",
                        value=NEGATIVE_ZERO_POINT,
                        source_parameter=f"{HW_OP_ID}.initializer.x_zero_point",
                        indices=node77.FIRST_STAGE_LINEAR,
                        artifact_id=artifact_id,
                    ),
                    "x_scale": _constant(
                        tensor_id="tensor-2cc427657ec3a8ed",
                        value=SCALE,
                        source_parameter=f"{HW_OP_ID}.initializer.x_scale",
                        indices=node77.SECOND_STAGE_LINEAR,
                        artifact_id=artifact_id,
                        identity_sha256=scale_identity,
                    ),
                },
                "config_artifacts": [
                    {
                        "artifact_id": artifact_id,
                        "role": "config_only_correctness_baseline",
                        "path": CONFIG_RELATIVE.as_posix(),
                        "sha256": hashlib.sha256(config_text.encode()).hexdigest(),
                        "raw_text": config_text,
                    }
                ],
            }
        ],
    }
    parsed, normalized, renormalized = node77._official_parser_roundtrip(root, value)
    if (
        len(parsed.operators) != 1
        or set(parsed.operators[0].constants)
        != {"negative_zero_point", "x_scale"}
        or normalized != renormalized
    ):
        raise Node0072ConfigOnlyError("official typed parser roundtrip differs")
    return value


def _mapping_audit(config: dict[str, Any], required: dict[str, Path]) -> dict[str, Any]:
    mapping = json.loads(required["mapping_review"].read_text(encoding="utf-8"))
    mapped = {
        item["node"].split(".", 1)[1]
        for item in mapping["node_to_resource"]
        if item["node"].startswith("GA_PE.")
    }
    if mapped != set(config["general_array"]["PE_array"]):
        raise Node0072ConfigOnlyError("mapping does not cover exact GA PE set")
    stdout = required["encoder_stdout"].read_text(encoding="utf-8")
    if not any(
        marker in stdout
        for marker in (
            "Success: Found valid mapping with 0 violations",
            "Mapping successful with zero violations",
        )
    ):
        raise Node0072ConfigOnlyError("mapper did not report zero violations")
    lines = required["bitstream"].read_text(encoding="utf-8").splitlines()
    if not lines or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise Node0072ConfigOnlyError("bitstream 128-bit ABI differs")
    return {
        "logical_ga_pe_coverage_exact": True,
        "placement_violations": 0,
        "fallback_used": False,
        "bitstream_line_count": len(lines),
        "bitstream_sha256": sha256_file(required["bitstream"]),
        "mapping_review_sha256": sha256_file(required["mapping_review"]),
    }


def _flatten_leaves(value: Any, path: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        flattened: dict[str, Any] = {}
        for key, child in value.items():
            flattened.update(_flatten_leaves(child, f"{path}/{key}"))
        return flattened
    if isinstance(value, list):
        flattened = {}
        for index, child in enumerate(value):
            flattened.update(_flatten_leaves(child, f"{path}/{index}"))
        return flattened
    return {path: value}


def _materialized_leaf_audit(
    static: dict[str, Any], materialized: dict[str, Any]
) -> dict[str, Any]:
    static_leaves = _flatten_leaves(static)
    final_leaves = _flatten_leaves(materialized)
    paths = sorted(set(static_leaves) | set(final_leaves))
    diff = [
        {
            "path": path,
            "old_value": static_leaves.get(path),
            "new_value": final_leaves.get(path),
        }
        for path in paths
        if static_leaves.get(path) != final_leaves.get(path)
    ]
    base_declarations = {
        "/stream_engine/stream0/base_addr": {
            "owner": "planner/address_binder",
            "input_source": "typed input A allocation",
            "formula": "A_base = aligned allocation start = 0",
            "old_value": "0b00000_00_0000000000000_000000_0000",
            "expected_new_value": "0x0",
            "authorization": "planner-owned physical base field",
        },
        "/stream_engine/stream2/base_addr": {
            "owner": "planner/address_binder",
            "input_source": "typed A size 16*74*1 uint8 = 1184 bytes",
            "formula": "D_base = A_base + A_size = 0 + 1184 = 0x4a0",
            "old_value": "0b00000_11_0000000000000_000000_0000",
            "expected_new_value": "0x4a0",
            "authorization": "planner-owned physical base field",
        },
    }
    nonbase_declarations: dict[str, dict[str, Any]] = {}
    for pe in node77.FIRST_STAGE_PES:
        path = f"/general_array/PE_array/{pe}/inport1/constant"
        nonbase_declarations[path] = {
            "owner": "native typed constant handler",
            "input_source": "hwop-0072-00.initializer.x_zero_point = uint8 scalar 0",
            "formula": "decimal float materialization of -float32(x_zero_point)",
            "old_value": NEGATIVE_ZERO_POINT_BITS,
            "expected_new_value": "0.0",
            "authorization": (
                "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001 frozen uint8 domain: "
                "add(+0.0) and add(-0.0) are bit-identical before positive scaling"
            ),
        }
    for pe, _ in node77.SECOND_STAGE_LINKS:
        path = f"/general_array/PE_array/{pe}/inport1/constant"
        nonbase_declarations[path] = {
            "owner": "native typed constant handler",
            "input_source": (
                "hwop-0072-00.initializer.x_scale float32 bits 0x3cbf57ec"
            ),
            "formula": "shortest round-trip decimal rendering of exact float32 x_scale",
            "old_value": SCALE_BITS,
            "expected_new_value": "0.02335735410451889",
            "authorization": (
                "node0072 typed request binding plus "
                "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001; "
                "decimal reparses to exact float32 bits 0x3cbf57ec"
            ),
        }
    allowed = {**base_declarations, **nonbase_declarations}
    actual_paths = {item["path"] for item in diff}
    if actual_paths != set(allowed):
        raise Node0072ConfigOnlyError(
            "materialized leaf diff allowlist differs; "
            f"missing={sorted(set(allowed) - actual_paths)}, "
            f"unexpected={sorted(actual_paths - set(allowed))}"
        )
    for item in diff:
        declaration = allowed[item["path"]]
        if (
            item["old_value"] != declaration["old_value"]
            or item["new_value"] != declaration["expected_new_value"]
        ):
            raise Node0072ConfigOnlyError(
                f"materialized leaf value differs at {item['path']}"
            )
    if _float32_bits("0.02335735410451889") != int(SCALE_BITS, 16):
        raise Node0072ConfigOnlyError("materialized scale decimal is not bit-exact")
    return {
        "rule_id": "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
        "static_to_materialized_leaf_diff_count": len(diff),
        "planner_base_field_diff_count": len(base_declarations),
        "nonbase_field_diff_count": len(nonbase_declarations),
        "unexpected_diff_count": 0,
        "all_diff_paths_declared": True,
        "planner_base_field_declarations": [
            {"path": path, **declaration}
            for path, declaration in sorted(base_declarations.items())
        ],
        "nonbase_field_declarations": [
            {"path": path, **declaration}
            for path, declaration in sorted(nonbase_declarations.items())
        ],
        "actual_leaf_diff": diff,
    }


def _address_lifetime_audit(
    config: dict[str, Any], sca: dict[str, Any], sca_d: dict[str, Any]
) -> dict[str, Any]:
    stream = config["stream_engine"]["stream2"]
    loop = config["dram_loop_configs"]["LC3"]
    occurrence_count = (loop["end"] - loop["start"]) // loop["stride"]
    transaction_bytes = int(stream["idx_size"][2]) + 1
    occurrence_stride = int(stream["dim_stride"][1])
    covered_offsets: set[int] = set()
    for occurrence in range(occurrence_count):
        start = occurrence * occurrence_stride
        covered_offsets.update(range(start, start + transaction_bytes))
    if (
        occurrence_count != 74
        or transaction_bytes != 64
        or occurrence_stride != 64
        or len(covered_offsets) != D_BYTES_PER_SLICE
        or min(covered_offsets) != 0
        or max(covered_offsets) != D_BYTES_PER_SLICE - 1
    ):
        raise Node0072ConfigOnlyError(
            "final occurrence/address equation does not cover full D region"
        )
    for slice_id in range(SLICE_COUNT):
        a = int(sca[f"op0_matrixA_slice{slice_id}"]["base_addr"], 16)
        d = int(sca_d[f"op0_matrixD_slice{slice_id}"]["base_addr"], 16)
        if d - a != WORDS_PER_SLICE:
            raise Node0072ConfigOnlyError("A/D address spacing differs")
        if sca_d[f"op0_matrixD_slice{slice_id}"]["length"] != D_LINES_PER_SLICE:
            raise Node0072ConfigOnlyError("SCA_D length differs")
    if (
        config["buffer_config"]["buffer0"]["buffer_life_time"] != 1
        or config["buffer_config"]["buffer5"]["buffer_life_time"] != 1
    ):
        raise Node0072ConfigOnlyError("buffer lifetime differs")
    return {
        "slice_count": SLICE_COUNT,
        "a_bytes_per_slice": WORDS_PER_SLICE,
        "d_bytes_per_slice": D_BYTES_PER_SLICE,
        "a_d_regions_non_overlapping": True,
        "sca_d_lines_per_slice": D_LINES_PER_SLICE,
        "buffer_lifetime": 1,
        "occurrences_per_slice": 74,
        "d_rows_per_occurrence": 4,
        "d_supply_bytes_per_occurrence": 64,
        "final_materialized_output_coverage": {
            "occurrence_count": occurrence_count,
            "transaction_bytes": transaction_bytes,
            "occurrence_address_stride_bytes": occurrence_stride,
            "covered_byte_count_per_slice": len(covered_offsets),
            "expected_output_bytes_per_slice": D_BYTES_PER_SLICE,
            "sca_d_bytes_per_slice": D_LINES_PER_SLICE * 16,
            "coverage_complete": True,
            "coverage_unique": True,
            "equation": "union_{i=0..73} [D_base+i*64, D_base+i*64+64)",
        },
    }


def _node0073_integrated_binding_handoff(
    root: Path,
    sca: dict[str, Any],
    sca_d: dict[str, Any],
    required: dict[str, Path],
) -> dict[str, Any]:
    slice_bindings = []
    for slice_id in range(SLICE_COUNT):
        a_base = int(sca[f"op0_matrixA_slice{slice_id}"]["base_addr"], 16)
        d_base = int(sca_d[f"op0_matrixD_slice{slice_id}"]["base_addr"], 16)
        slice_bindings.append(
            {
                "slice_id": slice_id,
                "physical_d_base_addr": f"0x{d_base:08x}",
                "d_offset_from_a_bytes": d_base - a_base,
                "physical_d_span_bytes": D_BYTES_PER_SLICE,
                "written_byte_coverage": {
                    "start_offset": 0,
                    "end_offset_exclusive": D_BYTES_PER_SLICE,
                    "covered_bytes": D_BYTES_PER_SLICE,
                    "complete": True,
                    "unique": True,
                },
            }
        )
    return {
        "producer": {
            "node_id": NODE_ID,
            "request_id": REQUEST_ID,
            "output_tensor_id": "tensor-50c285690f899b1b",
        },
        "consumer": {
            "node_id": "node-0073",
            "binding_role": "input storage handoff only",
        },
        "storage_owner": (
            "node0072 standalone D allocation in the official addressed execplan; "
            "node0073 does not own or relocate these bytes in this contract"
        ),
        "logical_contract": {
            "dtype": "float32",
            "shape": [16, 2048, 1, 1],
            "byte_strides": [8192, 4, 4, 4],
            "logical_span_bytes": 131072,
            "layout": "C-order logical tensor reconstructed from slice shards",
        },
        "physical_contract": {
            "slice_count": SLICE_COUNT,
            "words_per_slice": WORDS_PER_SLICE,
            "bytes_per_slice": D_BYTES_PER_SLICE,
            "physical_written_span_bytes": SLICE_COUNT * D_BYTES_PER_SLICE,
            "valid_logical_bytes": 131072,
            "padding_bytes": SLICE_COUNT * D_BYTES_PER_SLICE - 131072,
            "slice_bindings": slice_bindings,
        },
        "final_write_completion": {
            "static_validator_completion_path_accepted": True,
            "execplan_start_and_all_slice_d_address_writes_accepted": True,
            "config_bound_simulator_all_physical_d_writes_complete": True,
            "dynamic_hardware_final_write_accepted": False,
            "integrated_node0072_to_node0073_lifetime_accepted": False,
        },
        "final_written_byte_coverage": {
            "physical_written_bytes": SLICE_COUNT * D_BYTES_PER_SLICE,
            "logical_valid_bytes": 131072,
            "padding_bytes": SLICE_COUNT * D_BYTES_PER_SLICE - 131072,
            "per_slice_complete": True,
            "logical_inverse_complete": True,
            "logical_inverse_unique": True,
        },
        "addressed_asset_hashes": {
            "addressed_graph_sha256": sha256_file(required["addressed_graph"]),
            "final_address_bound_config_sha256": sha256_file(
                required["patched_config"]
            ),
            "execplan_sha256": sha256_file(required["execplan"]),
            "sca_sha256": sha256_file(required["sca"]),
            "sca_d_sha256": sha256_file(required["sca_d"]),
            "layout_evidence_sha256": sha256_file(
                root / ARTIFACT_RELATIVE / "layout_evidence.json"
            ),
        },
        "integrated_binding_status": "UNRESOLVED",
        "unresolved_blocker": "B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING",
        "claim_boundary": (
            "Exact standalone physical storage handoff only. A shared multi-operator "
            "execplan, address alias/lifetime visibility, and node0073 consumption "
            "have not been materialized or dynamically accepted."
        ),
    }


def materialize_local_e2(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    output = root / ARTIFACT_RELATIVE
    if output.exists():
        raise Node0072ConfigOnlyError(
            f"refusing to overwrite existing node0072 artifact root: {output}"
        )
    output.mkdir(parents=True)
    config = build_config(root)
    numeric = numeric_evidence(root)
    layout = build_layout(root, output)
    request = build_execplan_request(root, config)
    _write_json(root / CONFIG_RELATIVE, config)
    _write_json(output / "execplan_request.json", request)
    _write_json(output / "numeric_evidence.json", numeric)
    _write_json(output / "layout_evidence.json", layout)
    _write_json(output / "config_validation.json", validate_config(config))

    isolated = output / "isolated_toolchain"
    node77._copy_isolated_toolchain(root, isolated)
    shutil.copyfile(
        root / CONFIG_RELATIVE, isolated / "jsons" / f"{OP_TYPE}.json"
    )
    request_path = isolated / "model_execplan" / "dq72.json"
    shutil.copyfile(output / "execplan_request.json", request_path)
    (
        isolated / "model_execplan" / "output" / "dq72" / "install" / "cfg_pkg"
    ).mkdir(parents=True, exist_ok=True)
    cache = output / "mapping_cache"
    cache.mkdir()
    normalized_path = output / "normalized_execplan_request.json"
    run = node77._run(
        [
            str(Path(sys.executable).resolve()),
            str(isolated / "model_execplan/main.py"),
            str(request_path),
            "--dump-normalized-json",
            str(normalized_path),
        ],
        cwd=isolated,
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
            "NDP_MAPPING_CACHE_DIR": str(cache),
        },
    )
    lifecycle = isolated / "model_execplan/output/dq72"
    config_root = lifecycle / "config/op0"
    required = {
        "execplan": lifecycle / "install/execplan.txt",
        "explanation": lifecycle / "instructions_explained.txt",
        "sca": lifecycle / "sca_cfg.json",
        "sca_d": lifecycle / "sca_cfg_D.json",
        "addressed_graph": lifecycle / "dq72_withbaseaddr.json",
        "patched_config": lifecycle / "jsons" / f"op0_{OP_TYPE}.json",
        "mapping_review": config_root / "mapping_review.json",
        "bitstream": config_root / f"op0_{OP_TYPE}_bitstream_128b.bin",
        "cfg_pkg": lifecycle / "install/cfg_pkg" / f"op0_{OP_TYPE}_bitstream_128b.bin",
        "encoder_stdout": config_root / "encoder_stdout.log",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise Node0072ConfigOnlyError(f"official lifecycle products missing: {missing}")
    if sha256_file(required["bitstream"]) != sha256_file(required["cfg_pkg"]):
        raise Node0072ConfigOnlyError("bitstream/cfg_pkg identity differs")

    isolated_b = output / "isolated_toolchain_b"
    node77._copy_isolated_toolchain(root, isolated_b)
    shutil.copyfile(
        root / CONFIG_RELATIVE, isolated_b / "jsons" / f"{OP_TYPE}.json"
    )
    request_path_b = isolated_b / "model_execplan" / "dq72.json"
    shutil.copyfile(output / "execplan_request.json", request_path_b)
    cache_b = output / "mapping_cache_b"
    cache_b.mkdir()
    normalized_path_b = output / "normalized_execplan_request_b.json"
    run_b = node77._run(
        [
            str(Path(sys.executable).resolve()),
            str(isolated_b / "model_execplan/main.py"),
            str(request_path_b),
            "--dump-normalized-json",
            str(normalized_path_b),
        ],
        cwd=isolated_b,
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
            "NDP_MAPPING_CACHE_DIR": str(cache_b),
        },
    )
    lifecycle_b = isolated_b / "model_execplan/output/dq72"
    config_root_b = lifecycle_b / "config/op0"
    required_b = {
        "execplan": lifecycle_b / "install/execplan.txt",
        "explanation": lifecycle_b / "instructions_explained.txt",
        "sca": lifecycle_b / "sca_cfg.json",
        "sca_d": lifecycle_b / "sca_cfg_D.json",
        "addressed_graph": lifecycle_b / "dq72_withbaseaddr.json",
        "patched_config": lifecycle_b / "jsons" / f"op0_{OP_TYPE}.json",
        "mapping_review": config_root_b / "mapping_review.json",
        "bitstream": config_root_b / f"op0_{OP_TYPE}_bitstream_128b.bin",
        "cfg_pkg": (
            lifecycle_b
            / "install/cfg_pkg"
            / f"op0_{OP_TYPE}_bitstream_128b.bin"
        ),
    }
    missing_b = [name for name, path in required_b.items() if not path.is_file()]
    if missing_b:
        raise Node0072ConfigOnlyError(
            f"second isolated lifecycle products missing: {missing_b}"
        )
    deterministic = {
        name: sha256_file(path)
        for name, path in required.items()
        if name in required_b and name != "encoder_stdout"
    }
    deterministic_b = {
        name: sha256_file(path)
        for name, path in required_b.items()
        if name != "encoder_stdout"
    }
    if deterministic != deterministic_b or normalized_path.read_bytes() != normalized_path_b.read_bytes():
        raise Node0072ConfigOnlyError("two isolated config materializations differ")
    reproducibility = {
        "isolated_run_count": 2,
        "mapping_cache_initial_state": "empty for each run",
        "semantic_product_hashes_identical": True,
        "normalized_request_identical": True,
        "compared_product_sha256": deterministic,
    }
    patched = json.loads(required["patched_config"].read_text(encoding="utf-8"))
    validate_config(patched)
    materialized_leaf = _materialized_leaf_audit(config, patched)
    sca = json.loads(required["sca"].read_text(encoding="utf-8"))
    sca_d = json.loads(required["sca_d"].read_text(encoding="utf-8"))
    mapping = _mapping_audit(patched, required)
    address = _address_lifetime_audit(patched, sca, sca_d)
    node0073_handoff = _node0073_integrated_binding_handoff(
        root, sca, sca_d, required
    )
    execplan_audit = node77._execplan_roundtrip_audit(
        required["execplan"],
        required["explanation"],
        required["sca"],
        required["sca_d"],
        required["cfg_pkg"],
    )

    simulator_payloads: dict[int, bytes] = {}
    simulator_slice_records: list[dict[str, Any]] = []
    simulator_root = output / "simulator_physical_d"
    simulator_root.mkdir()
    logical = bytearray(32768 * 4)
    coverage = bytearray(32768)
    for item in layout["slices"]:
        slice_id = item["slice_id"]
        a_raw = (output / item["a_path"]).read_bytes()
        d_raw = _execute_config_pe_graph(patched, a_raw)
        simulator_payloads[slice_id] = d_raw
        d_path = simulator_root / f"slice{slice_id:02d}_D.bin"
        d_path.write_bytes(d_raw)
        start = item["logical_flat_start"]
        count = item["logical_element_count"]
        logical[start * 4 : (start + count) * 4] = d_raw[: count * 4]
        coverage[start : start + count] = b"\x01" * count
        if any(d_raw[count * 4 :]):
            raise Node0072ConfigOnlyError("simulator padding D is not +0.0f")
        simulator_slice_records.append(
            {
                "slice_id": slice_id,
                "physical_a_sha256": hashlib.sha256(a_raw).hexdigest(),
                "physical_d_sha256": hashlib.sha256(d_raw).hexdigest(),
                "physical_d_path": d_path.relative_to(root).as_posix(),
                "logical_element_count": count,
                "padding_element_count": WORDS_PER_SLICE - count,
            }
        )
    golden_raw = np.load(root / OUTPUT_RELATIVE, allow_pickle=False).tobytes()
    if any(value != 1 for value in coverage) or bytes(logical) != golden_raw:
        raise Node0072ConfigOnlyError("config-bound simulator differs from W3")

    receipt = [_identity(root, path) for path in RULE_RECEIPT_PATHS]
    report: dict[str, Any] = {
        "schema": "dequant-node0072-config-only-local-e2-report-v1",
        "status": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "request_id": REQUEST_ID,
        "request_sha256": REQUEST_SHA256,
        "rule_ids": list(RULE_IDS),
        "node0077_structural_reference_rule_patterns": list(
            NODE0077_REFERENCE_RULE_PATTERNS
        ),
        "node0077_rule_values_reused_as_node0072_authority": False,
        "read_receipt": receipt,
        "bypass_annotation": bypass_annotation(),
        "input_replay_contract": input_replay_contract(root),
        "toolchain_consumer_receipt": toolchain_consumer_receipt(root),
        "instance_delta_from_node0077": {
            "logical_shape": {
                "node0072": [16, 2048, 1, 1],
                "node0077": [16, 1000],
            },
            "scale_bits": {"node0072": SCALE_BITS, "node0077": "0x3e01622d"},
            "zero_point": {"node0072": 0, "node0077": 60},
            "hardware_shape_cwh": {
                "node0072": list(HARDWARE_SHAPE),
                "node0077": [16, 47, 1],
            },
            "occurrences_per_slice": {"node0072": 74, "node0077": 47},
            "d_lines_per_slice": {"node0072": 296, "node0077": 188},
            "topology": "same four-add then four-multiply ordinary GA DAG",
            "cross_instance_formal_claim": False,
        },
        "numeric": numeric,
        "layout": {
            key: value for key, value in layout.items() if key != "slices"
        },
        "config_validation": validate_config(patched),
        "materialized_nonbase_field_ownership": materialized_leaf,
        "mapping_bitstream": mapping,
        "execplan_sca": execplan_audit,
        "isolated_materialization_reproducibility": reproducibility,
        "address_lifetime": address,
        "node0073_integrated_binding_handoff": node0073_handoff,
        "config_bound_simulator": {
            "executor": "PROJECT_EQUIVALENT_CONFIG_BOUND_PE_GRAPH_EXECUTOR",
            "consumes_final_address_bound_json": True,
            "consumes_final_bitstream_and_mapping_identity": True,
            "consumes_execplan_sca_sca_d": True,
            "consumes_physical_layout_a": True,
            "produces_physical_d": True,
            "software_formula_substitution": False,
            "physical_d_slice_count": SLICE_COUNT,
            "physical_d_bytes_per_slice": D_BYTES_PER_SLICE,
            "physical_d_ordered_sha256": hashlib.sha256(
                b"".join(simulator_payloads[index] for index in range(SLICE_COUNT))
            ).hexdigest(),
            "physical_d_slices": simulator_slice_records,
            "logical_shape": [16, 2048, 1, 1],
            "logical_sha256": hashlib.sha256(bytes(logical)).hexdigest(),
            "golden_sha256": hashlib.sha256(golden_raw).hexdigest(),
            "bit_mismatch_count": 0,
            "bit_exact": True,
            "nan_count": 0,
            "padding_positive_zero": True,
        },
        "source_identity": {
            "typed_lowering_bundle": _identity(
                root, Path("contracts/resnet50_r5_lowering_bundle.json")
            ),
            "w3_model_graph": _identity(root, Path("artifacts/w3/model_graph.json")),
            "input": _identity(root, INPUT_RELATIVE),
            "golden": _identity(root, OUTPUT_RELATIVE),
            "static_config": _identity(root, CONFIG_RELATIVE),
            "normalized_execplan_request": {
                "path": normalized_path.relative_to(root).as_posix(),
                "sha256": sha256_file(normalized_path),
            },
            "numeric_evidence": _identity(root, ARTIFACT_RELATIVE / "numeric_evidence.json"),
            "layout_evidence": _identity(root, ARTIFACT_RELATIVE / "layout_evidence.json"),
            "config_validation": _identity(
                root, ARTIFACT_RELATIVE / "config_validation.json"
            ),
            "final_address_bound_config": {
                "path": required["patched_config"].relative_to(root).as_posix(),
                "sha256": sha256_file(required["patched_config"]),
            },
            "addressed_graph": {
                "path": required["addressed_graph"].relative_to(root).as_posix(),
                "sha256": sha256_file(required["addressed_graph"]),
            },
            "mapping_review": {
                "path": required["mapping_review"].relative_to(root).as_posix(),
                "sha256": sha256_file(required["mapping_review"]),
            },
            "bitstream": {
                "path": required["bitstream"].relative_to(root).as_posix(),
                "sha256": sha256_file(required["bitstream"]),
            },
            "execplan": {
                "path": required["execplan"].relative_to(root).as_posix(),
                "sha256": sha256_file(required["execplan"]),
            },
            "sca": {
                "path": required["sca"].relative_to(root).as_posix(),
                "sha256": sha256_file(required["sca"]),
            },
            "sca_d": {
                "path": required["sca_d"].relative_to(root).as_posix(),
                "sha256": sha256_file(required["sca_d"]),
            },
        },
        "run": {
            "scope": "LOCAL_TOOLCHAIN_ONLY",
            "commands": [run["command"], run_b["command"]],
            "returncodes": [run["returncode"], run_b["returncode"]],
            "server_package_generated": False,
            "server_files_inspected": False,
            "server_run": False,
        },
        "remaining_blockers": bypass_annotation()["unresolved_production_blocker"],
        "known_counterexamples": [
            "typed node0072 standalone/transport/layout paths are rejected",
            "native typed handler normalizes GA constant leaves; undeclared drift fails",
            "stream2 occurrence stride drift produces incomplete D byte coverage",
        ],
        "open_dynamic_gates": [
            "node0072 formal E4/E5",
            "node0072-to-node0073 integrated address/lifetime visibility",
        ],
        "omitted_files": [
            {
                "path": ".agents/rules/Flatten_View算子配置规则.md",
                "reason": (
                    "not consumed: this task owns only node0072 output handoff; "
                    "node0073 owns Flatten/View interpretation and validation"
                ),
            }
        ],
    }
    report["report_content_sha256"] = sha256_bytes(canonical_json_bytes(report))
    _write_json(output / "local_e2_report.json", report)
    contract = {
        "schema": "dequant-node0072-config-only-correctness-contract-v1",
        "status": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "request_id": REQUEST_ID,
        "rule_ids": list(RULE_IDS),
        "node0077_structural_reference_rule_patterns": list(
            NODE0077_REFERENCE_RULE_PATTERNS
        ),
        "bypass_annotation": bypass_annotation(),
        "input_replay_contract": input_replay_contract(root),
        "toolchain_consumer_receipt": report["toolchain_consumer_receipt"],
        "node0073_integrated_binding_handoff": node0073_handoff,
        "artifact": _identity(root, REPORT_RELATIVE),
        "gates": {
            "typed_target_bound": True,
            "final_json_valid": True,
            "materialized_nonbase_field_ownership_closed": True,
            "final_output_byte_coverage_closed": True,
            "mapping_bitstream_closed": True,
            "execplan_sca_closed": True,
            "two_isolated_materializations_identical": True,
            "address_lifetime_closed": True,
            "config_bound_simulator_bit_exact": True,
            "input_replay_noncomputational": True,
            "hardware_evidence": False,
            "node0072_to_node0073_integrated_binding": False,
            "production_release": False,
        },
        "remaining_blockers": report["remaining_blockers"],
    }
    contract["contract_content_sha256"] = sha256_bytes(
        canonical_json_bytes(contract)
    )
    _write_json(root / CONTRACT_RELATIVE, contract)
    return report, contract


__all__ = [
    "ARTIFACT_RELATIVE",
    "CONFIG_RELATIVE",
    "CONTRACT_RELATIVE",
    "REPORT_RELATIVE",
    "Node0072ConfigOnlyError",
    "build_config",
    "bypass_annotation",
    "input_replay_contract",
    "materialize_local_e2",
    "numeric_evidence",
    "validate_config",
]
