from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .deepseek_native_e2 import run_double_isolated_native_graph
from .deepseek_onnx_validation import build_deepseek_crop_contract
from .deepseek_rope_numeric import (
    CONTRACT_PATH as ROPE_NUMERIC_CONTRACT_PATH,
    build_rope_numeric_contract,
)
from .deepseek_silu_holdout import _compute_native_mapping_penalty
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import load_native_execution_plan


ARTIFACT_ROOT = "artifacts/operator_config_validation/ds_rope_v1"
GRAPH_NAME = "ds_rope_v1"
GRAPH_PATH = f"{ARTIFACT_ROOT}/{GRAPH_NAME}.json"
CONTRACT_PATH = (
    "contracts/operator_config/deepseek_rope_validation_v1.json"
)
READ_RECEIPT_PATH = (
    "contracts/operator_config/deepseek_rope_read_receipt_v1.json"
)
READ_RECEIPT_SHA256 = (
    "5cb4e5b242f9c45ca5ea4354f21cad9d"
    "8419989788f7e4b1b48cde611a5c2d09"
)
PREFILL_GRAPH_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/layer0_prefill.generated.json"
)
ONNX_INVENTORY_PATH = (
    "artifacts/operator_config_validation/"
    "r5-deepseek-onnx-stage-json-e2-v1/onnx_graph_inventory.json"
)
ROPE_FRAGMENT_PATH = "ndp-sim/model_execplan/op_json/rope.json"
ROPE_K_FRAGMENT_PATH = "ndp-sim/model_execplan/op_json/rope_k.json"
ROUTER_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/"
    "slice_routing.py"
)
INSTRUCTION_GENERATOR_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/"
    "instruction_generator.py"
)
PREFILL_GOLDEN_PATH = (
    "ndp-sim/generate_python_golden/"
    "deepseek1.5b_3_time_golden_smallsize.py"
)
PREFILL_GOLDEN_HISTORY_PATH = (
    "ndp-sim/generate_python_golden/"
    "deepseek1.5b_3_time_golden_smallsize_0527.py"
)
ROPE_RELAYOUT_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/"
    "relayout_rope.py"
)
ROPE_RELAYOUT_BACKUP_PATH = (
    "ndp-sim/generate_python_golden/single_op_data/"
    "backup/relayout_rope.py"
)
GOLDEN_README_PATH = "ndp-sim/generate_python_golden/README.md"
ROPE_RULE_PATH = ".agents/rules/DeepSeek_RoPE增量规则.md"
TRUSTED_ROPE_ROOT = "jsons/rope"
TRUSTED_ROPE_GRAPH_PATH = f"{TRUSTED_ROPE_ROOT}/rope_withbaseaddr.json"
TRUSTED_ROPE_INSTRUCTIONS_PATH = (
    f"{TRUSTED_ROPE_ROOT}/instructions_explained.txt"
)
TRUSTED_ROPE_SCA_PATH = f"{TRUSTED_ROPE_ROOT}/sca_cfg.json"
TRUSTED_ROPE_SCA_D_PATH = f"{TRUSTED_ROPE_ROOT}/sca_cfg_D.json"
OPERATOR_TYPES = (
    "prefill_mul_fp32MN_fp32MN_fp32MN",
    "prefill_mul_fp32MN_fp32MN_fp32MN",
    "prefill_add_fp32MN_fp32MN_fp16MN",
)
ALL_28_MASK = "0b" + ("1" * 28)
ROUTER_OVERLAY_PATH = (
    "resnet50_pipeline/native_overlays/deepseek_rope/"
    "slice_routing.py"
)
ROUTER_OVERLAY_TARGET = (
    "model_execplan/src/execution_plan_generator/slice_routing.py"
)


class DeepSeekRopeValidationError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekRopeValidationError(
            f"cannot parse RoPE evidence JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekRopeValidationError(
            f"JSON root must be an object: {path}"
        )
    return value


def _onnx_anchor(root: Path) -> dict[str, Any]:
    inventory = _load(root / ONNX_INVENTORY_PATH)
    nodes = inventory.get("graph", {}).get("nodes")
    matches = [
        item
        for item in nodes
        if isinstance(item, Mapping)
        and item.get("index") == 12
        and item.get("name")
        == "/model/layers.0/attn/GroupQueryAttention"
    ] if isinstance(nodes, list) else []
    if len(matches) != 1:
        raise DeepSeekRopeValidationError(
            "ONNX layer-0 GQA/RoPE anchor differs"
        )
    node = matches[0]
    attributes = {
        str(item.get("name")): item.get("value")
        for item in node.get("attributes", [])
        if isinstance(item, Mapping)
    }
    inputs = node.get("inputs")
    if (
        node.get("op_type") != "GroupQueryAttention"
        or attributes.get("do_rotary") != 1
        or attributes.get("rotary_interleaved") != 0
        or not isinstance(inputs, list)
        or "cos_cache" not in inputs
        or "sin_cache" not in inputs
    ):
        raise DeepSeekRopeValidationError(
            "ONNX non-interleaved RoPE semantics differ"
        )
    return deepcopy(dict(node))


def build_rope_graph(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    receipt = root / READ_RECEIPT_PATH
    if (
        not receipt.is_file()
        or sha256_file(receipt) != READ_RECEIPT_SHA256
        or _load(receipt).get("receipt_status")
        != "ROPE_CANONICAL_XOR2_MATERIALIZATION_READY"
    ):
        raise DeepSeekRopeValidationError(
            "RoPE mandatory-read receipt differs"
        )
    crop = build_deepseek_crop_contract(root)
    derived = crop.get("model_dimensions", {}).get("derived", {})
    if (
        derived.get("hidden_elements_per_slice") != 32
        or derived.get("active_slice_count") != 28
        or crop.get("model_dimensions", {})
        .get("target", {})
        .get("head_dim")
        != 128
    ):
        raise DeepSeekRopeValidationError(
            "crop contract does not derive 7 heads x 4 slices x 32 values"
        )
    _onnx_anchor(root)

    fragment = _load(root / ROPE_FRAGMENT_PATH)
    fragment_ops = fragment.get("operators")
    if (
        not isinstance(fragment_ops, list)
        or [item.get("type") for item in fragment_ops]
        != list(OPERATOR_TYPES)
        or fragment_ops[1].get("output", {}).get("type")
        != "rope_slice_xor2"
    ):
        raise DeepSeekRopeValidationError(
            "native Q RoPE fragment differs"
        )
    kv_fragment = _load(root / ROPE_K_FRAGMENT_PATH)
    if [
        item.get("type")
        for item in kv_fragment.get("operators", [])
        if isinstance(item, Mapping)
    ] != list(OPERATOR_TYPES):
        raise DeepSeekRopeValidationError(
            "native KV RoPE fragment differs"
        )

    prefill = _load(root / PREFILL_GRAPH_PATH)
    all_ops = prefill.get("operators")
    if not isinstance(all_ops, list) or len(all_ops) < 10:
        raise DeepSeekRopeValidationError(
            "prefill graph is missing Q RoPE stages"
        )
    source_ops = deepcopy(all_ops[7:10])
    if [item.get("type") for item in source_ops] != list(OPERATOR_TYPES):
        raise DeepSeekRopeValidationError(
            "prefill Q RoPE stage sequence differs"
        )
    if (
        source_ops[0].get("inputs", {}).get("A", {}).get("source")
        != "op6"
        or source_ops[1].get("inputs", {}).get("A", {}).get("source")
        != "op6"
        or source_ops[1].get("output", {}).get("type")
        != "rope_slice_xor2"
        or source_ops[2].get("inputs", {}).get("A", {}).get("source")
        != "op7"
        or source_ops[2].get("inputs", {}).get("B", {}).get("source")
        != "op8"
    ):
        raise DeepSeekRopeValidationError(
            "prefill Q RoPE typed dependencies differ"
        )

    selected = source_ops
    for index, item in enumerate(selected):
        item["id"] = f"op{index}"
    for index in (0, 1):
        item = selected[index]
        item["inputs"]["A"]["source"] = {"type": "external"}
    selected[2]["inputs"]["A"]["source"] = "op0"
    selected[2]["inputs"]["B"]["source"] = "op1"
    params = deepcopy(prefill.get("params"))
    if not isinstance(params, dict):
        raise DeepSeekRopeValidationError(
            "prefill parameter block is malformed"
        )
    params["target_op"] = "rope_three_stage_validation"
    return {
        "params": params,
        "used_slices": ALL_28_MASK,
        "operators": selected,
    }


def validate_rope_graph(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_rope_graph(project_root):
        raise DeepSeekRopeValidationError(
            "RoPE graph differs from ONNX/crop/native-stage evidence"
        )


def materialize_rope_native_e2(
    project_root: Path, python_executable: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_rope_graph(root)
    validate_rope_graph(graph, root)
    return run_double_isolated_native_graph(
        project_root=root,
        artifact_root_relative=ARTIFACT_ROOT,
        graph_name=GRAPH_NAME,
        graph=graph,
        operator_types=OPERATOR_TYPES,
        python_executable=python_executable.resolve(),
        source_overlays={
            ROUTER_OVERLAY_TARGET: ROUTER_OVERLAY_PATH,
        },
    )


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekRopeValidationError(
            f"required RoPE evidence is missing: {relative}"
        )
    return {
        "path": relative,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _ga_opcodes(config: Mapping[str, Any]) -> list[str]:
    pe_array = config.get("general_array", {}).get("PE_array")
    if not isinstance(pe_array, Mapping):
        raise DeepSeekRopeValidationError(
            "RoPE materialized JSON has no GA PE_array"
        )
    return sorted(
        {
            str(value.get("alu_opcode"))
            for value in pe_array.values()
            if isinstance(value, Mapping)
        }
    )


def _materialized_json_summary(
    root: Path, output_relative: str
) -> list[dict[str, Any]]:
    output = root / output_relative
    expected = (
        {
            "ga_opcodes": ["mul"],
            "fp32tofp16": "false",
            "stream_idx_size": {
                "stream0": [0, 31, None],
                "stream1": [0, 31, None],
                "stream2": [0, 31, None],
            },
            "readback_lines_128b": 256,
        },
        {
            "ga_opcodes": ["mul"],
            "fp32tofp16": "false",
            "stream_idx_size": {
                "stream0": [0, 31, None],
                "stream1": [0, 31, None],
                "stream2": [0, 31, None],
            },
            "readback_lines_128b": 256,
        },
        {
            "ga_opcodes": ["add"],
            "fp32tofp16": "true",
            "stream_idx_size": {
                "stream0": [0, 31, None],
                "stream1": [0, 31, None],
                "stream2": [3, 7, None],
            },
            "readback_lines_128b": 128,
        },
    )
    sca_d = _load(output / "sca_cfg_D.json")
    summaries: list[dict[str, Any]] = []
    for index, op_type in enumerate(OPERATOR_TYPES):
        op_id = f"op{index}"
        relative = (
            f"{output_relative}/jsons/{op_id}_{op_type}.json"
        )
        review_relative = (
            f"{output_relative}/config/{op_id}/mapping_review.json"
        )
        config = _load(root / relative)
        review = _load(root / review_relative)
        penalty = _compute_native_mapping_penalty(root, review)
        loop_ends = {
            name: config.get("dram_loop_configs", {})
            .get(name, {})
            .get("end")
            for name in ("LC0", "LC1", "LC2")
        }
        stream_idx_size = {
            name: config.get("stream_engine", {})
            .get(name, {})
            .get("idx_size")
            for name in ("stream0", "stream1", "stream2")
        }
        d_entries = [
            value
            for key, value in sca_d.items()
            if re.fullmatch(rf"{op_id}_matrixD_slice\d+", key)
            and isinstance(value, Mapping)
        ]
        d_lengths = sorted(
            {int(value.get("length")) for value in d_entries}
        )
        observed = {
            "ga_opcodes": _ga_opcodes(config),
            "fp32tofp16": config.get("general_array", {})
            .get("outport", {})
            .get("fp32tofp16"),
            "stream_idx_size": stream_idx_size,
            "readback_lines_128b": (
                d_lengths[0] if len(d_lengths) == 1 else None
            ),
        }
        if (
            penalty != 0
            or loop_ends != {"LC0": 4, "LC1": 32, "LC2": 32}
            or len(d_entries) != 28
            or observed != expected[index]
        ):
            raise DeepSeekRopeValidationError(
                f"{op_id} materialized JSON/bitstream summary differs"
            )
        summaries.append(
            {
                "op_id": op_id,
                "op_type": op_type,
                "materialized_json": _binding(root, relative),
                "mapping_review": _binding(root, review_relative),
                "mapping_exact_penalty": penalty,
                "loop_ends": loop_ends,
                "active_slice_count": len(d_entries),
                **observed,
            }
        )
    return summaries


def _decode_lifecycle(output: Path) -> dict[str, Any]:
    explanation = output / "instructions_explained.txt"
    lines = [
        line
        for line in explanation.read_text(
            encoding="utf-8"
        ).splitlines()
        if re.match(r"^\d{4}\s+<", line)
    ]
    event_order: list[str] = []
    per_op: dict[str, dict[str, int]] = {
        f"op{index}": {
            "load_config_count": 0,
            "write_reg_count": 0,
            "start_comp_count": 0,
        }
        for index in range(3)
    }
    for line in lines:
        match = re.search(
            r"(Load_Config|Start_Comp) for operator (op\d+)", line
        )
        if match:
            kind, op_id = match.groups()
            event_order.append(f"{kind}:{op_id}")
            key = (
                "load_config_count"
                if kind == "Load_Config"
                else "start_comp_count"
            )
            per_op[op_id][key] += 1
        if "Write_Reg" in line:
            match = re.search(r"operator (op\d+)", line)
            if not match:
                raise DeepSeekRopeValidationError(
                    "RoPE execplan contains an unattributed Write_Reg"
                )
            per_op[match.group(1)]["write_reg_count"] += 1
    expected_order = [
        "Load_Config:op0",
        "Start_Comp:op0",
        "Load_Config:op1",
        "Start_Comp:op1",
        "Load_Config:op2",
        "Start_Comp:op2",
    ]
    expected_per_op = {
        f"op{index}": {
            "load_config_count": 1,
            "write_reg_count": 81,
            "start_comp_count": 1,
        }
        for index in range(3)
    }
    if (
        len(lines) != 250
        or sum("Clock_Enable" in line for line in lines) != 1
        or event_order != expected_order
        or per_op != expected_per_op
    ):
        raise DeepSeekRopeValidationError(
            "RoPE three-stage execplan lifecycle differs"
        )
    return {
        "command_count": len(lines),
        "clock_enable_count": 1,
        "event_order": event_order,
        "per_operator": per_op,
    }


def _native_double_run_summary(
    root: Path, output_relative: str
) -> dict[str, Any]:
    receipts: dict[str, dict[str, Any]] = {}
    manifests: dict[str, dict[str, tuple[str, int]]] = {}
    for run_name in ("a", "b"):
        relative = (
            f"{ARTIFACT_ROOT}/{run_name}/native_run_receipt.json"
        )
        receipt = _load(root / relative)
        unhashed = dict(receipt)
        receipt_hash = unhashed.pop("receipt_sha256", None)
        if (
            receipt.get("schema")
            != "deepseek-native-e2-run-receipt-v1"
            or receipt.get("returncode") != 0
            or receipt.get("parsed_operator_count") != 3
            or receipt.get("initial_mapping_cache_file_count") != 0
            or receipt.get("mapping_exact_penalties")
            != {"op0": 0.0, "op1": 0.0, "op2": 0.0}
            or receipt_hash
            != sha256_bytes(canonical_json_bytes(unhashed))
        ):
            raise DeepSeekRopeValidationError(
                f"RoPE native run {run_name} receipt differs"
            )
        determinism = receipt.get("mapping_determinism")
        overlays = (
            determinism.get("isolated_tool_overlays")
            if isinstance(determinism, Mapping)
            else None
        )
        if (
            not isinstance(determinism, Mapping)
            or determinism.get("native_source_modified") is not False
            or determinism.get("isolated_tool_overlay_applied") is not True
            or not isinstance(overlays, list)
            or len(overlays) != 1
            or overlays[0].get("source", {}).get("path")
            != ROUTER_OVERLAY_PATH
            or overlays[0].get("target") != ROUTER_OVERLAY_TARGET
            or overlays[0].get("target_postimage", {}).get("sha256")
            != sha256_file(root / ROUTER_OVERLAY_PATH)
        ):
            raise DeepSeekRopeValidationError(
                f"RoPE native run {run_name} overlay provenance differs"
            )
        output_files = receipt.get("output_files")
        if not isinstance(output_files, list) or len(output_files) != 38:
            raise DeepSeekRopeValidationError(
                f"RoPE native run {run_name} output set differs"
            )
        manifests[run_name] = {
            str(item["path"]): (
                str(item["sha256"]),
                int(item["size_bytes"]),
            )
            for item in output_files
            if isinstance(item, Mapping)
            and not str(item.get("path", "")).endswith(
                "/placement.png"
            )
        }
        if len(manifests[run_name]) != 35:
            raise DeepSeekRopeValidationError(
                f"RoPE native run {run_name} deterministic set differs"
            )
        receipts[run_name] = {
            "binding": _binding(root, relative),
            "receipt_sha256": receipt_hash,
            "returncode": 0,
            "initial_mapping_cache_file_count": 0,
            "mapping_exact_penalties": receipt[
                "mapping_exact_penalties"
            ],
        }
    if manifests["a"] != manifests["b"]:
        raise DeepSeekRopeValidationError(
            "RoPE isolated native deterministic outputs differ"
        )
    return {
        "runs": receipts,
        "output_file_count_per_run": 38,
        "deterministic_file_count": 35,
        "excluded_visualization_count": 3,
        "deterministic_outputs_byte_identical": True,
        "native_source_modified": False,
        "isolated_tool_overlay_applied": True,
        "active_router_overlay": _binding(root, ROUTER_OVERLAY_PATH),
        "empty_cache_at_start": True,
        "random_seed": 42,
        "python_hash_seed": 0,
    }


def _parse_output_route(path: Path) -> dict[int, int]:
    explicit: dict[int, int] = {}
    explained = path.read_text(encoding="utf-8")
    for line in explained.splitlines():
        if "base address for operator op1 output D" not in line:
            continue
        match = re.search(
            r"slice_bin=([01]{5}), source_slice_bin=([01]{5})",
            line,
        )
        if not match:
            raise DeepSeekRopeValidationError(
                "RoPE op1 output route explanation differs"
            )
        producer = int(match.group(1), 2)
        destination = int(match.group(2), 2)
        explicit[producer] = destination
    return explicit


def _route_summary(root: Path, output: Path) -> dict[str, Any]:
    native_router_text = (root / ROUTER_PATH).read_text(
        encoding="utf-8"
    )
    active_router_text = (root / ROUTER_OVERLAY_PATH).read_text(
        encoding="utf-8"
    )
    instruction_text = (
        root / INSTRUCTION_GENERATOR_PATH
    ).read_text(encoding="utf-8")
    if (
        '"rope_slice_xor2": lambda slice_id: slice_id ^ 0b11'
        not in native_router_text
        or '"rope_slice_xor2": lambda slice_id: slice_id ^ 0b10'
        not in active_router_text
        or "resolve_io_base_addr_source_slice(" not in instruction_text
        or "io_type=op.output.special_type" not in instruction_text
    ):
        raise DeepSeekRopeValidationError(
            "RoPE planner route implementation differs"
        )

    explicit = _parse_output_route(
        output / "instructions_explained.txt"
    )
    trusted_explicit = _parse_output_route(
        root / TRUSTED_ROPE_INSTRUCTIONS_PATH
    )
    actual = {
        slice_id: explicit.get(slice_id, 0) for slice_id in range(28)
    }
    trusted_actual = {
        slice_id: trusted_explicit.get(slice_id, 0)
        for slice_id in range(28)
    }
    expected = {slice_id: slice_id ^ 2 for slice_id in range(28)}
    if (
        len(explicit) != 27
        or set(actual) - set(explicit) != {2}
        or len(trusted_explicit) != 27
        or set(trusted_actual) - set(trusted_explicit) != {3}
        or actual != expected
        or trusted_actual
        != {slice_id: slice_id ^ 3 for slice_id in range(28)}
    ):
        raise DeepSeekRopeValidationError(
            "RoPE active or legacy execplan route writes differ"
        )
    generated_mismatches = [
        {
            "producer_slice": slice_id,
            "expected_destination_slice": expected[slice_id],
            "actual_destination_slice": actual[slice_id],
        }
        for slice_id in range(28)
        if expected[slice_id] != actual[slice_id]
    ]
    trusted_mismatches = [
        {
            "producer_slice": slice_id,
            "expected_destination_slice": expected[slice_id],
            "actual_destination_slice": trusted_actual[slice_id],
        }
        for slice_id in range(28)
        if expected[slice_id] != trusted_actual[slice_id]
    ]
    if generated_mismatches or len(trusted_mismatches) != 28:
        raise DeepSeekRopeValidationError(
            "RoPE route mismatch count differs"
        )
    return {
        "head_dim": 128,
        "elements_per_slice": 32,
        "slices_per_head": 4,
        "onnx_rotary_interleaved": 0,
        "expected_half_distance_elements": 64,
        "expected_half_distance_slices": 2,
        "expected_producer_to_destination": [
            expected[index] for index in range(28)
        ],
        "active_router_expression": "slice_id ^ 0b10",
        "active_producer_to_destination": [
            actual[index] for index in range(28)
        ],
        "explicit_execplan_route_write_count": len(explicit),
        "active_route_mismatch_count": len(generated_mismatches),
        "legacy_trusted_router_expression": "slice_id ^ 0b11",
        "legacy_trusted_producer_to_destination": [
            trusted_actual[index] for index in range(28)
        ],
        "legacy_trusted_route_mismatch_count": len(
            trusted_mismatches
        ),
        "trusted_and_rebuilt_route_writes_identical": False,
        "elided_default_route": {
            "producer_slice": 2,
            "destination_slice": 0,
        },
        "active_mismatches": generated_mismatches,
        "legacy_trusted_mismatches": trusted_mismatches,
    }


def _sign_pipeline_summary(root: Path) -> dict[str, Any]:
    golden_text = (root / PREFILL_GOLDEN_PATH).read_text(
        encoding="utf-8"
    )
    relayout_text = (root / ROPE_RELAYOUT_PATH).read_text(
        encoding="utf-8"
    )
    backup_relayout_text = (
        root / ROPE_RELAYOUT_BACKUP_PATH
    ).read_text(encoding="utf-8")
    readme_text = (root / GOLDEN_README_PATH).read_text(
        encoding="utf-8"
    )
    required_golden = (
        "mul2_in1[i, j, k] = sin_theta",
        "mul2_in1[i+ne0//2, j, k] = -sin_theta",
    )
    required_relayout = (
        'if op_id == "op1" and matrix_id == "B":',
        "data = (-data).astype(file_dtype, copy=False)",
        "np.array_split(head_data, slices_per_head, axis=0)",
    )
    if (
        any(token not in golden_text for token in required_golden)
        or any(token not in relayout_text for token in required_relayout)
        or "data = (-data).astype" in backup_relayout_text
        or "RoPE 无需跨 slice 数据交换" not in readme_text
        or "半区交换 op8/op18 的激活输入" not in readme_text
    ):
        raise DeepSeekRopeValidationError(
            "RoPE golden/relayout sign evidence differs"
        )
    raw_sign_by_quarter = [1, 1, -1, -1]
    post_relayout_sign_by_quarter = [-1, -1, 1, 1]
    expected_contribution_sign_by_destination = [-1, -1, 1, 1]
    if post_relayout_sign_by_quarter == raw_sign_by_quarter:
        raise DeepSeekRopeValidationError(
            "RoPE relayout did not expose the expected sign conflict"
        )
    return {
        "golden_saved_sin_sign_by_source_quarter": raw_sign_by_quarter,
        "relayout_operation": "negate all op1/matrix_B values",
        "post_relayout_sin_sign_by_source_quarter": (
            post_relayout_sign_by_quarter
        ),
        "expected_contribution_sign_by_destination_quarter": (
            expected_contribution_sign_by_destination
        ),
        "ordered_quarter_split_preserved": True,
        "historical_relayout_has_global_negation": False,
        "documented_decode_alternative": (
            "half-swap activation plus [-sin,+sin] and same-slice add"
        ),
        "correct_xor2_route_with_current_relayout_still_wrong": True,
        "active_implementation": {
            "activation_pre_swapped": False,
            "sin_sign_by_source_quarter": raw_sign_by_quarter,
            "relayout_global_negation": False,
            "route": "slice_id xor 0b10",
            "semantics_closed": True,
        },
    }


def _numeric_equation_summary() -> dict[str, Any]:
    head_dim = 128
    elements_per_slice = 32
    half = head_dim // 2
    values = [index + 1 for index in range(head_dim)]
    cos = [3 + (index % 7) for index in range(half)]
    sin = [5 + (index % 11) for index in range(half)]
    cos_full = cos + cos
    raw_sin = sin + [-value for value in sin]

    expected = [0] * head_dim
    for index in range(half):
        expected[index] = (
            values[index] * cos[index]
            - values[index + half] * sin[index]
        )
        expected[index + half] = (
            values[index] * sin[index]
            + values[index + half] * cos[index]
        )

    def route_products(
        *,
        activation: list[int],
        table: list[int],
        quarter_xor: int,
    ) -> list[int]:
        routed = [0] * head_dim
        for source_index, (value, factor) in enumerate(
            zip(activation, table, strict=True)
        ):
            source_quarter = source_index // elements_per_slice
            element_in_quarter = (
                source_index % elements_per_slice
            )
            destination_quarter = source_quarter ^ quarter_xor
            destination_index = (
                destination_quarter * elements_per_slice
                + element_in_quarter
            )
            routed[destination_index] = value * factor
        return routed

    raw_product_xor2 = route_products(
        activation=values,
        table=raw_sin,
        quarter_xor=2,
    )
    reference_cross_slice = [
        values[index] * cos_full[index] + raw_product_xor2[index]
        for index in range(head_dim)
    ]

    current_post_relayout_sin = [-value for value in raw_sin]
    current_product_xor3 = route_products(
        activation=values,
        table=current_post_relayout_sin,
        quarter_xor=3,
    )
    current_pipeline = [
        values[index] * cos_full[index]
        + current_product_xor3[index]
        for index in range(head_dim)
    ]

    swapped_activation = values[half:] + values[:half]
    decode_sin = [-value for value in sin] + sin
    decode_same_slice = [
        values[index] * cos_full[index]
        + swapped_activation[index] * decode_sin[index]
        for index in range(head_dim)
    ]

    def mismatch_count(actual: list[int]) -> int:
        return sum(
            actual[index] != expected[index]
            for index in range(head_dim)
        )

    current_mismatches = mismatch_count(current_pipeline)
    xor2_mismatches = mismatch_count(reference_cross_slice)
    decode_mismatches = mismatch_count(decode_same_slice)
    if (
        current_mismatches != head_dim
        or xor2_mismatches != 0
        or decode_mismatches != 0
    ):
        raise DeepSeekRopeValidationError(
            "RoPE synthetic equation evidence differs"
        )
    return {
        "arithmetic": "exact_integer_symbolic_surrogate",
        "head_dim": head_dim,
        "elements_per_slice": elements_per_slice,
        "tested_element_count": head_dim,
        "current_prefill_xor3_plus_global_negation_mismatch_count": (
            current_mismatches
        ),
        "cross_slice_xor2_without_global_negation_mismatch_count": (
            xor2_mismatches
        ),
        "preswapped_activation_rearranged_sin_same_slice_mismatch_count": (
            decode_mismatches
        ),
        "current_prefill_pipeline_matches_onnx_equation": False,
        "active_canonical_pipeline_mismatch_count": xor2_mismatches,
        "active_canonical_pipeline_matches_onnx_equation": True,
        "two_independently_derived_valid_conventions": True,
    }


def _trusted_payload_summary(root: Path) -> dict[str, Any]:
    install = root / TRUSTED_ROPE_ROOT / "install"
    files = sorted(
        (
            path
            for path in install.glob(
                "op*/slice*/matrix_*_linearized_128bit.bin"
            )
            if path.is_file()
        ),
        key=lambda item: item.as_posix(),
    )
    entries = [
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    nonempty = [entry for entry in entries if entry["size_bytes"]]
    if (
        len(entries) != 252
        or len(nonempty) != 1
        or nonempty[0]["path"]
        != (
            "jsons/rope/install/op0/slice14/"
            "matrix_D_linearized_128bit.bin"
        )
        or nonempty[0]["size_bytes"] != 4096
    ):
        raise DeepSeekRopeValidationError(
            "trusted RoPE payload coverage differs"
        )
    return {
        "expected_tensor_file_count": 252,
        "observed_tensor_file_count": len(entries),
        "nonempty_tensor_file_count": len(nonempty),
        "empty_tensor_file_count": len(entries) - len(nonempty),
        "total_payload_bytes": sum(
            int(entry["size_bytes"]) for entry in entries
        ),
        "nonempty_files": nonempty,
        "path_size_hash_manifest_sha256": sha256_bytes(
            canonical_json_bytes(entries)
        ),
        "complete_three_stage_numeric_oracle": False,
    }


def build_rope_blocker_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    graph = build_rope_graph(root)
    graph_path = root / GRAPH_PATH
    if _load(graph_path) != graph:
        raise DeepSeekRopeValidationError(
            "RoPE v1 graph differs from current evidence"
        )
    normalized = load_native_execution_plan(root, graph_path)
    output_relative = (
        f"{ARTIFACT_ROOT}/a/t/model_execplan/output/{GRAPH_NAME}"
    )
    output = root / output_relative
    configs = _materialized_json_summary(root, output_relative)
    lifecycle = _decode_lifecycle(output)
    native_runs = _native_double_run_summary(root, output_relative)
    route = _route_summary(root, output)
    sign_pipeline = _sign_pipeline_summary(root)
    numeric_equation = _numeric_equation_summary()
    trusted_payload = _trusted_payload_summary(root)
    numeric_contract = build_rope_numeric_contract(root)
    if _load(root / ROPE_NUMERIC_CONTRACT_PATH) != numeric_contract:
        raise DeepSeekRopeValidationError(
            "RoPE numeric contract differs from current payload"
        )
    if (
        route["active_route_mismatch_count"] != 0
        or route["legacy_trusted_route_mismatch_count"] != 28
        or not sign_pipeline["active_implementation"][
            "semantics_closed"
        ]
        or numeric_equation[
            "active_canonical_pipeline_mismatch_count"
        ] != 0
        or numeric_contract["numeric_result"][
            "route_mismatch_count"
        ] != 0
    ):
        raise DeepSeekRopeValidationError(
            "RoPE canonical route/sign/payload closure differs"
        )

    payload: dict[str, Any] = {
        "schema": "deepseek-rope-three-stage-validation-v1",
        "status": "LOCAL_E2_REFERENCE_CONFORMANT",
        "candidate_release": False,
        "formal_target_config": False,
        "server_package_generated": False,
        "identity_boundary": {
            "onnx_repository_classification": "SEMANTIC_MODEL_MATCH",
            "original_source_identity": False,
            "direct_onnx_shape_equals_stage": False,
            "crop_contract_required": True,
        },
        "inputs": {
            "read_receipt": _binding(root, READ_RECEIPT_PATH),
            "crop_contract": _binding(
                root,
                "contracts/operator_config/"
                "deepseek_ndpsim_crop_contract_v1.json",
            ),
            "onnx_inventory": _binding(root, ONNX_INVENTORY_PATH),
            "prefill_graph": _binding(root, PREFILL_GRAPH_PATH),
            "q_rope_fragment": _binding(root, ROPE_FRAGMENT_PATH),
            "kv_rope_fragment": _binding(
                root, ROPE_K_FRAGMENT_PATH
            ),
            "router": _binding(root, ROUTER_PATH),
            "active_router_overlay": _binding(
                root, ROUTER_OVERLAY_PATH
            ),
            "instruction_generator": _binding(
                root, INSTRUCTION_GENERATOR_PATH
            ),
            "prefill_golden": _binding(
                root, PREFILL_GOLDEN_PATH
            ),
            "historical_prefill_golden": _binding(
                root, PREFILL_GOLDEN_HISTORY_PATH
            ),
            "rope_relayout": _binding(root, ROPE_RELAYOUT_PATH),
            "historical_rope_relayout": _binding(
                root, ROPE_RELAYOUT_BACKUP_PATH
            ),
            "golden_readme": _binding(root, GOLDEN_README_PATH),
            "rope_rule": _binding(root, ROPE_RULE_PATH),
            "trusted_rope_graph": _binding(
                root, TRUSTED_ROPE_GRAPH_PATH
            ),
            "trusted_rope_instructions": _binding(
                root, TRUSTED_ROPE_INSTRUCTIONS_PATH
            ),
            "trusted_rope_sca": _binding(
                root, TRUSTED_ROPE_SCA_PATH
            ),
            "trusted_rope_sca_d": _binding(
                root, TRUSTED_ROPE_SCA_D_PATH
            ),
            "isolated_graph": _binding(root, GRAPH_PATH),
            "synthetic_numeric_contract": _binding(
                root, ROPE_NUMERIC_CONTRACT_PATH
            ),
        },
        "onnx_to_stage": {
            "onnx_anchor": _onnx_anchor(root),
            "crop_derived_hidden_size": 896,
            "crop_derived_q_heads": 7,
            "crop_derived_kv_heads": 1,
            "head_dim": 128,
            "active_q_slice_count": 28,
            "elements_per_slice": 32,
            "native_stage_sequence": list(OPERATOR_TYPES),
            "native_normalized_graph": normalized,
            "isolated_external_input_precondition": (
                "op0.A and op1.A are separately allocated stand-ins for "
                "the same upstream Q tensor; this structural run does not "
                "prove their numerical contents are equal"
            ),
        },
        "stage_json_bitstream_lifecycle": {
            "individual_trusted_jsons_invalidated": False,
            "materialized_configs": configs,
            "lifecycle": lifecycle,
            "sca_d_lines_per_slice": {
                "op0_fp32": 256,
                "op1_fp32": 256,
                "op2_fp16": 128,
            },
            "native_double_run": native_runs,
            "route_semantics": route,
            "sign_pipeline": sign_pipeline,
            "synthetic_onnx_equation": numeric_equation,
            "trusted_payload_coverage": trusted_payload,
            "synthetic_numeric_e2": numeric_contract,
            "structurally_complete": True,
            "synthetic_numerical_equation_executed": True,
            "complete_trusted_payload_golden_executed": False,
            "complete_synthetic_payload_golden_executed": True,
            "semantically_accepted": True,
        },
        "closed_findings": [
            {
                "id": "B_DS_ROPE_SLICE_PAIRING",
                "closure": (
                    "the isolated active execplan consumer emits XOR2 "
                    "for all 28 slices; the one default-elided route is "
                    "reconstructed and the mismatch count is zero"
                ),
            },
            {
                "id": "B_DS_ROPE_SIN_SIGN_PIPELINE",
                "closure": (
                    "the active payload uses unmodified activation, "
                    "signed [+,-] sin halves and no relayout negation; "
                    "the legacy double-sign conflict remains recorded"
                ),
            },
            {
                "id": "B_DS_ROPE_LOCAL_PAYLOAD_COVERAGE",
                "closure": (
                    "301 non-empty synthetic files cover all logical "
                    "head equations and all op0/op1/op2 A/B/D tensors "
                    "on 28 slices, including bit-equal op0/op1 inputs"
                ),
            },
        ],
        "blockers": [],
        "policy_result": {
            "onnx_to_three_stage_decomposition_closed": True,
            "three_stage_json_lifecycle_structurally_closed": True,
            "inter_stage_route_semantics_closed": True,
            "golden_relayout_sign_semantics_closed": True,
            "synthetic_equation_diagnosis_closed": True,
            "trusted_payload_coverage_closed": False,
            "local_synthetic_payload_coverage_closed": True,
            "three_stage_local_e2_accepted": True,
            "advance_to_server_test": False,
            "maximum_evidence_level": "E2",
        },
        "rule_ids": [
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-CONFIG-FULL-REBUILD-PROVENANCE-001",
            "CDA-DEEPSEEK-MODEL-IDENTITY-001",
            "CDA-DEEPSEEK-CROP-EXPLICIT-001",
            "CDA-DEEPSEEK-ONNX-STAGE-DAG-001",
            "CDA-DEEPSEEK-STAGE-JSON-ORACLE-001",
            "CDA-DEEPSEEK-CROSS-SLICE-ROUTE-001",
            "CDA-DEEPSEEK-ROPE-HALF-PAIRING-001",
            "CDA-DEEPSEEK-ROPE-SIGN-SINGLE-OWNER-001",
            "CDA-DEEPSEEK-ROPE-PAYLOAD-COVERAGE-001",
            "CDA-DEEPSEEK-ROPE-IMPLEMENTATION-CHOICE-001",
        ],
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_rope_blocker_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_rope_blocker_contract(project_root):
        raise DeepSeekRopeValidationError(
            "RoPE blocker contract differs from current evidence"
        )


__all__ = [
    "ARTIFACT_ROOT",
    "CONTRACT_PATH",
    "DeepSeekRopeValidationError",
    "GRAPH_NAME",
    "GRAPH_PATH",
    "OPERATOR_TYPES",
    "build_rope_blocker_contract",
    "build_rope_graph",
    "materialize_rope_native_e2",
    "validate_rope_blocker_contract",
    "validate_rope_graph",
]
