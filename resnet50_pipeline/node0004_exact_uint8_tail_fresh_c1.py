"""Fresh, fail-closed C1 dependency audit for node0004's exact UINT8 tail.

This module intentionally consumes only the sources authorized by the
2026-07-28 mainline override: typed lowering, the formal model/W3 artifacts,
current rules, and the hash-bound native ndp-sim sources.  It never reads an
older node0004 config, candidate, mapping, report, simulator output, or package.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx


SCHEMA = "node0004-exact-uint8-tail-fresh-c1-dependency-v1"
REPORT_SCHEMA = "node0004-exact-uint8-tail-fresh-c1-dependency-report-v1"
REQUEST_ID = "r5:hwop-0004-01"

CONTRACT_PATH = (
    "contracts/operator_config/node0004_exact_uint8_tail_fresh_c1_dependency_v1.json"
)
REPORT_PATH = (
    "artifacts/operator_config_validation/"
    "node0004-exact-uint8-tail-fresh-c1-dependency-v1/report.json"
)

PLAN_PATH = ".agents/plan.md"
OVERRIDE_PATH = (
    ".agents/task_records/"
    "20260728_node0004_untrusted_fresh_rebuild_mainline_override.md"
)
INDEX_RULE_PATH = ".agents/rules/生成前必读索引.md"
COMMON_RULE_PATH = ".agents/rules/算子配置规则.md"
NDP_RULE_PATH = ".agents/rules/NDP硬件字段语义.md"
TAIL_RULE_PATH = ".agents/rules/精确UINT8量化尾专项规则.md"
REQUANT_RULE_PATH = ".agents/rules/RequantizeUint8算子配置规则.md"

LOWERING_PATH = "contracts/resnet50_r5_lowering_bundle.json"
MODEL_PATH = "artifacts/reference_model/resnet50-v1-12-int8.onnx"
MODEL_GRAPH_PATH = "artifacts/w3/model_graph.json"
GOLDEN_MANIFEST_PATH = "artifacts/w3/golden_batch16/manifest.json"
SUBOP_MANIFEST_PATH = "artifacts/w3/subop_batch16/manifest.json"
ACCUMULATOR_PATH = (
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0004-accumulate.npy"
)
GOLDEN_PATH = (
    "artifacts/w3/golden_batch16/tensors/tensor-78b29737ada5ce7a.npy"
)

REPOS_LOCK_PATH = "repos.lock.json"
NATIVE_TEMPLATE_PATH = (
    "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
)
NATIVE_BASE_INFO_PATH = "ndp-sim/model_execplan/config/operator_base_info.json"
NATIVE_MODELS_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/models.py"
)
NATIVE_TEMPLATE_MANAGER_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/template_manager.py"
)
NATIVE_CONTROL_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py"
)
NATIVE_PIPELINE_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/pipeline.py"
)
NATIVE_INSTRUCTION_PATH = (
    "ndp-sim/model_execplan/src/execution_plan_generator/"
    "instruction_generator.py"
)
NATIVE_MAPPER_PATH = "ndp-sim/bitstream/config/mapper.py"
NATIVE_GENERAL_ENCODER_PATH = "ndp-sim/bitstream/config/general.py"

PARAMETER_NAMES = {
    "x_scale": "resnetv17_relu0_fwd_scale",
    "w_scale": "ConvBnFusion_W_resnetv17_stage1_conv0_weight_scale",
    "y_scale": "resnetv17_stage1_relu0_fwd_scale",
    "y_zero_point": "resnetv17_stage1_relu0_fwd_zero_point",
}

CURRENT_MATCH_SOURCES = [
    (OVERRIDE_PATH, "mainline fresh-rebuild override"),
    (INDEX_RULE_PATH, "generation routing"),
    (COMMON_RULE_PATH, "common config and reuse gates"),
    (NDP_RULE_PATH, "GA/MSE/Buffer hardware semantics"),
    (TAIL_RULE_PATH, "shared exact UINT8-tail gates"),
    (REQUANT_RULE_PATH, "INT32-to-UINT8 family gates"),
    (LOWERING_PATH, "typed request and qparam binding"),
    (MODEL_PATH, "formal ONNX model"),
    (MODEL_GRAPH_PATH, "formal model graph identity"),
    (GOLDEN_MANIFEST_PATH, "formal W3 output manifest"),
    (SUBOP_MANIFEST_PATH, "formal W3 accumulator manifest"),
    (ACCUMULATOR_PATH, "formal W3 INT32 accumulator"),
    (GOLDEN_PATH, "formal W3 UINT8 golden"),
    (REPOS_LOCK_PATH, "authorized native repository identity"),
    (NATIVE_TEMPLATE_PATH, "authorized structural primitive"),
    (NATIVE_BASE_INFO_PATH, "native template registry"),
    (NATIVE_MODELS_PATH, "native typed execplan model"),
    (NATIVE_TEMPLATE_MANAGER_PATH, "native template binding"),
    (NATIVE_CONTROL_PATH, "native control handler"),
    (NATIVE_PIPELINE_PATH, "native execplan pipeline"),
    (NATIVE_INSTRUCTION_PATH, "native control-write consumer"),
    (NATIVE_MAPPER_PATH, "native mapper"),
    (NATIVE_GENERAL_ENCODER_PATH, "GA conversion encoder"),
]

FORBIDDEN_SOURCE_FRAGMENTS = (
    "node0004_requant_semantics_evidence",
    "node0004_requant_full_semantic_contract",
    "node0004_server",
    "node0004_accumulate_wave",
    "node0004_conv_three_wave",
    "node0004-nopp",
    "requant_quant_tail_evidence_input",
    "requant_family_classification",
    "server_returns/",
    "outputs/",
)


class Node0004FreshTailError(ValueError):
    """Raised when the fresh C1 dependency evidence no longer holds."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Node0004FreshTailError(f"JSON root must be an object: {path}")
    return value


def _request(lowering: dict[str, Any]) -> dict[str, Any]:
    matches = [
        item
        for item in lowering.get("requests", [])
        if isinstance(item, dict) and item.get("request_id") == REQUEST_ID
    ]
    if len(matches) != 1:
        raise Node0004FreshTailError(
            f"expected one typed request {REQUEST_ID}, got {len(matches)}"
        )
    return matches[0]


def _u32_bits(value: np.ndarray | np.float32) -> list[str]:
    array = np.asarray(value, dtype=np.float32).reshape(-1)
    return [f"0x{int(item):08x}" for item in array.view(np.uint32)]


def _model_initializers(model_path: Path) -> dict[str, np.ndarray]:
    model = onnx.load(str(model_path), load_external_data=True)
    wanted = set(PARAMETER_NAMES.values())
    result = {
        tensor.name: onnx.numpy_helper.to_array(tensor)
        for tensor in model.graph.initializer
        if tensor.name in wanted
    }
    if set(result) != wanted:
        missing = sorted(wanted - set(result))
        raise Node0004FreshTailError(
            f"formal model is missing node0004 qparams: {missing}"
        )
    return result


def _typed_parameter_map(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {
        str(item["name"]): item
        for item in request.get("typed_parameters", [])
        if isinstance(item, dict) and item.get("name") in {*PARAMETER_NAMES, "requant_multiplier"}
    }
    expected = {*PARAMETER_NAMES, "requant_multiplier"}
    if set(result) != expected:
        raise Node0004FreshTailError(
            f"typed parameter set differs: {sorted(result)}"
        )
    return result


def _shape_dtype_identity(request: dict[str, Any]) -> dict[str, Any]:
    geometry = request["logical_geometry"]
    expected_shape = [16, 64, 56, 56]
    if geometry["input_shapes"][0] != expected_shape:
        raise Node0004FreshTailError("node0004 accumulator shape changed")
    if geometry["output_shapes"] != [expected_shape]:
        raise Node0004FreshTailError("node0004 output shape changed")
    if geometry["input_dtypes"][0] != "int32":
        raise Node0004FreshTailError("node0004 accumulator dtype changed")
    if geometry["output_dtypes"] != ["uint8"]:
        raise Node0004FreshTailError("node0004 output dtype changed")
    element_count = int(np.prod(expected_shape, dtype=np.int64))
    return {
        "logical_layout": "NCHW",
        "logical_shape": expected_shape,
        "input_dtype": "int32",
        "output_dtype": "uint8",
        "element_count": element_count,
        "input_bytes": element_count * 4,
        "output_bytes": element_count,
        "channels": 64,
        "channel_mod8": 0,
        "conditional_hwc8_lane_tail": 0,
        "physical_layout": None,
        "physical_layout_status": "B_LAYOUT_APPROVAL",
        "occurrence_count": None,
        "transaction_bytes": None,
        "address_binding": None,
        "lifetime_binding": None,
        "terminal_binding": None,
        "readback_binding": None,
        "claim_boundary": (
            "Only logical NCHW bytes and the absence of a channel-mod-8 tail "
            "are closed. No physical HWC8 schedule, transaction, occurrence, "
            "address, lifetime, terminal, or readback endpoint is approved."
        ),
    }


def _qparam_identity(
    request: dict[str, Any], initializers: dict[str, np.ndarray]
) -> tuple[dict[str, Any], np.ndarray, int]:
    typed = _typed_parameter_map(request)
    arrays = {
        role: np.asarray(initializers[name])
        for role, name in PARAMETER_NAMES.items()
    }
    x_scale = np.asarray(arrays["x_scale"], dtype=np.float32).reshape(())
    w_scale = np.asarray(arrays["w_scale"], dtype=np.float32).reshape(64)
    y_scale = np.asarray(arrays["y_scale"], dtype=np.float32).reshape(())
    y_zero_point = int(
        np.asarray(arrays["y_zero_point"], dtype=np.uint8).reshape(())
    )
    multiplier = np.asarray(
        np.asarray(x_scale * w_scale, dtype=np.float32) / y_scale,
        dtype=np.float32,
    )

    expected_hashes = {
        role: typed[role]["value"]["value_sha256"]
        for role in PARAMETER_NAMES
    }
    for role, value in arrays.items():
        actual = hashlib.sha256(value.tobytes(order="C")).hexdigest()
        if actual != expected_hashes[role]:
            raise Node0004FreshTailError(
                f"model/typed qparam hash differs for {role}: "
                f"expected={expected_hashes[role]} actual={actual}"
            )
    multiplier_hash = hashlib.sha256(multiplier.tobytes(order="C")).hexdigest()
    typed_multiplier_hash = typed["requant_multiplier"]["value"]["value_sha256"]
    if multiplier_hash != typed_multiplier_hash:
        raise Node0004FreshTailError(
            "fresh model-derived multiplier differs from typed lowering"
        )
    if y_zero_point != 0:
        raise Node0004FreshTailError("node0004 output zero-point is no longer zero")
    if not np.all(np.isfinite(multiplier)) or not np.all(multiplier > 0):
        raise Node0004FreshTailError(
            "node0004 multiplier is not finite and strictly positive"
        )

    qparams = {
        "source": "formal ONNX initializers cross-checked against typed lowering",
        "scalar_shape_note": (
            "The ONNX model stores scalar qparams with canonical shape []; "
            "the typed lowering transports them as [1]."
        ),
        "x_scale": {
            "onnx_name": PARAMETER_NAMES["x_scale"],
            "dtype": "float32",
            "model_shape": list(arrays["x_scale"].shape),
            "typed_shape": typed["x_scale"]["value"]["shape"],
            "float32_bits": _u32_bits(x_scale)[0],
            "value": float(x_scale),
            "sha256": expected_hashes["x_scale"],
        },
        "w_scale": {
            "onnx_name": PARAMETER_NAMES["w_scale"],
            "dtype": "float32",
            "model_shape": list(arrays["w_scale"].shape),
            "typed_shape": typed["w_scale"]["value"]["shape"],
            "axis": 0,
            "element_count": 64,
            "minimum": float(w_scale.min()),
            "maximum": float(w_scale.max()),
            "float32_bits": _u32_bits(w_scale),
            "sha256": expected_hashes["w_scale"],
        },
        "y_scale": {
            "onnx_name": PARAMETER_NAMES["y_scale"],
            "dtype": "float32",
            "model_shape": list(arrays["y_scale"].shape),
            "typed_shape": typed["y_scale"]["value"]["shape"],
            "float32_bits": _u32_bits(y_scale)[0],
            "value": float(y_scale),
            "sha256": expected_hashes["y_scale"],
        },
        "y_zero_point": {
            "onnx_name": PARAMETER_NAMES["y_zero_point"],
            "dtype": "uint8",
            "model_shape": list(arrays["y_zero_point"].shape),
            "typed_shape": typed["y_zero_point"]["value"]["shape"],
            "value": y_zero_point,
            "sha256": expected_hashes["y_zero_point"],
        },
        "requant_multiplier": {
            "formula": "float32(float32(x_scale * w_scale[c]) / y_scale)",
            "dtype": "float32",
            "shape": [64],
            "axis": 0,
            "element_count": 64,
            "minimum": float(multiplier.min()),
            "maximum": float(multiplier.max()),
            "all_finite_positive": True,
            "float32_bits": _u32_bits(multiplier),
            "sha256": multiplier_hash,
        },
    }
    return qparams, multiplier, y_zero_point


def _w3_replay(
    root: Path, multiplier: np.ndarray, y_zero_point: int
) -> dict[str, Any]:
    subop_manifest = _load_json(root / SUBOP_MANIFEST_PATH)
    golden_manifest = _load_json(root / GOLDEN_MANIFEST_PATH)
    accumulator_record = subop_manifest["internal_tensors"][
        "tensor-internal-node-0004-accumulate"
    ]
    golden_record = golden_manifest["tensors"]["tensor-78b29737ada5ce7a"]
    if accumulator_record["path"] != "tensors/tensor-internal-node-0004-accumulate.npy":
        raise Node0004FreshTailError("formal accumulator path changed")
    if golden_record["path"] != "tensors/tensor-78b29737ada5ce7a.npy":
        raise Node0004FreshTailError("formal golden path changed")
    if sha256_file(root / ACCUMULATOR_PATH) != accumulator_record["sha256"]:
        raise Node0004FreshTailError("formal accumulator file identity differs")
    if sha256_file(root / GOLDEN_PATH) != golden_record["sha256"]:
        raise Node0004FreshTailError("formal golden file identity differs")

    accumulator = np.load(root / ACCUMULATOR_PATH, allow_pickle=False)
    golden = np.load(root / GOLDEN_PATH, allow_pickle=False)
    if accumulator.dtype != np.int32 or golden.dtype != np.uint8:
        raise Node0004FreshTailError("formal W3 dtype differs")
    if list(accumulator.shape) != [16, 64, 56, 56]:
        raise Node0004FreshTailError("formal accumulator shape differs")
    if accumulator.shape != golden.shape:
        raise Node0004FreshTailError("formal accumulator/golden shape differs")

    scaled = np.asarray(
        accumulator.astype(np.float32)
        * multiplier.reshape(1, 64, 1, 1),
        dtype=np.float32,
    )
    rounded_shifted = np.rint(scaled).astype(np.int64) + y_zero_point
    replay = np.clip(rounded_shifted, 0, 255).astype(np.uint8)
    mismatch_count = int(np.count_nonzero(replay != golden))
    if mismatch_count:
        raise Node0004FreshTailError(
            f"fresh ONNX/W3 requant replay mismatch_count={mismatch_count}"
        )
    minus_one_count = int(np.count_nonzero(accumulator == -1))
    if minus_one_count <= 0:
        raise Node0004FreshTailError(
            "formal node0004 W3 input no longer hits the -1 counterexample"
        )
    fractional = np.abs(scaled - np.trunc(scaled))
    return {
        "formula": (
            "scaled=float32(accumulator*multiplier[c]); "
            "rounded=round_to_nearest_even(scaled); "
            "shifted=rounded+y_zero_point; output=clip(shifted,0,255)"
        ),
        "element_count": int(accumulator.size),
        "accumulator": {
            "dtype": "int32",
            "shape": list(accumulator.shape),
            "file_sha256": sha256_file(root / ACCUMULATOR_PATH),
            "payload_sha256": hashlib.sha256(
                accumulator.tobytes(order="C")
            ).hexdigest(),
            "minimum": int(accumulator.min()),
            "maximum": int(accumulator.max()),
            "negative_count": int(np.count_nonzero(accumulator < 0)),
            "minus_one_count": minus_one_count,
            "zero_count": int(np.count_nonzero(accumulator == 0)),
        },
        "golden": {
            "dtype": "uint8",
            "shape": list(golden.shape),
            "file_sha256": sha256_file(root / GOLDEN_PATH),
            "payload_sha256": hashlib.sha256(
                golden.tobytes(order="C")
            ).hexdigest(),
        },
        "replay_payload_sha256": hashlib.sha256(
            replay.tobytes(order="C")
        ).hexdigest(),
        "mismatch_count": mismatch_count,
        "below_zero_before_clip_count": int(
            np.count_nonzero(rounded_shifted < 0)
        ),
        "above_255_before_clip_count": int(
            np.count_nonzero(rounded_shifted > 255)
        ),
        "exact_halfway_count": int(
            np.count_nonzero(fractional == np.float32(0.5))
        ),
        "evidence_level": "FORMULA_AND_FORMAL_W3_ONLY_NOT_HARDWARE_E2",
    }


def _native_repo_commit(root: Path) -> str:
    head = (root / "ndp-sim/.git/HEAD").read_text(encoding="ascii").strip()
    if not head.startswith("ref: "):
        return head
    ref = head[5:]
    loose = root / "ndp-sim/.git" / ref
    if loose.is_file():
        return loose.read_text(encoding="ascii").strip()
    packed = root / "ndp-sim/.git/packed-refs"
    for line in packed.read_text(encoding="ascii").splitlines():
        if line.endswith(f" {ref}"):
            return line.split(" ", 1)[0]
    raise Node0004FreshTailError(f"cannot resolve ndp-sim HEAD ref {ref}")


def _function_return_keys(source: str, function_name: str) -> list[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                    keys = []
                    for key in child.value.keys:
                        if not isinstance(key, ast.Constant) or not isinstance(
                            key.value, str
                        ):
                            raise Node0004FreshTailError(
                                "native handler return keys are no longer static strings"
                            )
                        keys.append(key.value)
                    return keys
    raise Node0004FreshTailError(
        f"native handler {function_name} was not found"
    )


def _operator_spec_fields(source: str) -> list[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "OperatorSpec":
            return [
                child.target.id
                for child in node.body
                if isinstance(child, ast.AnnAssign)
                and isinstance(child.target, ast.Name)
            ]
    raise Node0004FreshTailError("native OperatorSpec class was not found")


def _native_audit(root: Path) -> dict[str, Any]:
    repos_lock = _load_json(root / REPOS_LOCK_PATH)
    repo_record = next(
        (
            item
            for item in repos_lock["repositories"]
            if item.get("name") == "ndp-sim"
        ),
        None,
    )
    if not isinstance(repo_record, dict):
        raise Node0004FreshTailError("repos.lock has no ndp-sim record")
    head_commit = _native_repo_commit(root)
    if head_commit != repo_record["commit"]:
        raise Node0004FreshTailError(
            "ndp-sim HEAD differs from the authorized repos.lock commit"
        )

    template = _load_json(root / NATIVE_TEMPLATE_PATH)
    base_info = _load_json(root / NATIVE_BASE_INFO_PATH)["operators"][
        "quant_from_buffer_int32MN_uint8MN"
    ]
    pe_array = template["general_array"]["PE_array"]
    mac_pes = sorted(
        name for name, value in pe_array.items() if value["alu_opcode"] == "mac"
    )
    sub_pes = sorted(
        name
        for name, value in pe_array.items()
        if value["alu_opcode"] == "int32_sub"
    )
    if len(mac_pes) != 8 or len(sub_pes) != 8:
        raise Node0004FreshTailError(
            "authorized native template no longer has eight mac/sub lanes"
        )
    if (
        template["general_array"]["inport"]["inport0"]["int32tofp32"]
        != "true"
    ):
        raise Node0004FreshTailError(
            "authorized native template no longer uses INT32-to-FP32 ingress"
        )
    if template["general_array"]["outport"]["int32touint8"] != "true":
        raise Node0004FreshTailError(
            "authorized native template no longer uses UINT8 saturation"
        )

    model_source = (root / NATIVE_MODELS_PATH).read_text(encoding="utf-8")
    control_source = (root / NATIVE_CONTROL_PATH).read_text(encoding="utf-8")
    mapper_source = (root / NATIVE_MAPPER_PATH).read_text(encoding="utf-8")
    handler_name = (
        "_compute_quant_from_buffer_int32MN_uint8MN_control_register_updates"
    )
    handler_keys = _function_return_keys(control_source, handler_name)
    operator_fields = _operator_spec_fields(model_source)
    if "qparams" in operator_fields or "parameters" in operator_fields:
        raise Node0004FreshTailError(
            "native OperatorSpec gained qparam transport; capability must be re-audited"
        )
    if "Placeholder for quant_from_buffer_int32MN_uint8MN" not in control_source:
        raise Node0004FreshTailError(
            "native quant handler is no longer the audited placeholder"
        )
    if any(
        token in key.lower()
        for key in handler_keys
        for token in ("constant", "multiplier", "magic", "zero_point")
    ):
        raise Node0004FreshTailError(
            "native handler gained numeric constant transport; re-audit required"
        )
    if 'if "GA_PE" in node:' not in mapper_source:
        raise Node0004FreshTailError(
            "native mapper GA-PE handling changed; re-audit required"
        )

    mac_constants = {
        "multiplier": sorted(
            {
                float(pe_array[name]["inport1"]["constant"])
                for name in mac_pes
            }
        ),
        "magic_bias": sorted(
            {
                float(pe_array[name]["inport2"]["constant"])
                for name in mac_pes
            }
        ),
        "subtract": sorted(
            {
                int(pe_array[name]["inport1"]["constant"])
                for name in sub_pes
            }
        ),
    }
    return {
        "repository": {
            "commit": head_commit,
            "branch": repo_record["branch"],
            "dirty_claim_from_lock": repo_record["dirty"],
        },
        "template": {
            "path": NATIVE_TEMPLATE_PATH,
            "reuse_class": "STRUCTURE_OR_PRIMITIVE_ONLY",
            "initial_size": base_info["initial_size"],
            "input_conversion": "int32tofp32",
            "output_conversion": "int32touint8",
            "mac_pe_count": len(mac_pes),
            "int32_sub_pe_count": len(sub_pes),
            "static_constants": mac_constants,
            "target_qparams_equal_static_constants": False,
            "claim_boundary": (
                "Only LC/MSE/Buffer, eight fixed GA lane pairs, and UINT8 "
                "saturation structure are reusable. Shape and numeric constants "
                "are not node0004 bindings."
            ),
        },
        "typed_transport": {
            "operator_spec_fields": operator_fields,
            "qparam_fields_present": False,
            "quant_handler_docstring_classification": "PLACEHOLDER",
            "quant_handler_return_keys": handler_keys,
            "numeric_constant_update_count": 0,
            "status": "PLACEHOLDER_BLOCKED",
        },
        "mapper": {
            "ga_pe_resource_mapping": "fixed_physical_not_logical_mapper_owned",
            "target_exact_tail_registration": "MISSING_OR_UNPROVEN",
            "status": "B_QUANT_TAIL_MAPPER_REGISTRATION",
        },
        "execplan_transport": {
            "static_template_constants_only": True,
            "per_channel_multiplier_transport": False,
            "zero_point_transport": False,
            "status": "B_EXECPLAN_TYPED_TRANSPORT",
        },
    }


def _semantic_analysis(root: Path) -> dict[str, Any]:
    lowering = _load_json(root / LOWERING_PATH)
    request = _request(lowering)
    identity = request["identity"]
    if identity != {
        "hw_op_id": "hwop-0004-01",
        "node_id": "node-0004",
        "onnx_name": "fused resnetv17_stage1_conv0_fwd_quant",
        "onnx_op_type": "QLinearConv",
        "hw_op_type": "RequantizeUint8",
        "stage": "requantize",
    }:
        raise Node0004FreshTailError("node0004 typed identity changed")

    initializers = _model_initializers(root / MODEL_PATH)
    qparams, multiplier, y_zero_point = _qparam_identity(
        request, initializers
    )
    w3 = _w3_replay(root, multiplier, y_zero_point)
    native = _native_audit(root)
    shape_layout = _shape_dtype_identity(request)

    ndp_rule = (root / NDP_RULE_PATH).read_text(encoding="utf-8")
    if "`-1→0xcf000000`" not in ndp_rule:
        raise Node0004FreshTailError(
            "current NDP rule no longer carries the signed-ingress counterexample"
        )
    expected_minus_one_bits = _u32_bits(np.float32(-1.0))[0]
    counterexample = {
        "id": "CE_NODE0004_SIGNED_INT32_MINUS_ONE",
        "input_int32": -1,
        "input_bits": "0xffffffff",
        "expected_ieee_fp32_bits": expected_minus_one_bits,
        "native_int32tofp32_bits_from_current_rule": "0xcf000000",
        "formal_w3_occurrence_count": w3["accumulator"]["minus_one_count"],
        "intermediate_equivalent": False,
        "final_uint8_masking_for_this_value": (
            "Both negative paths saturate to zero for positive multiplier and "
            "y_zero_point=0; this does not prove signed ingress."
        ),
        "blocker": "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
    }

    capability_matrix = [
        {
            "capability": "signed_int32_ingress",
            "status": "CONTRADICTED",
            "first_unavoidable_capability": True,
            "evidence": counterexample["id"],
        },
        {
            "capability": "per_channel_float32_multiplier",
            "status": "SOFTWARE_AND_TYPED_IDENTITY_CLOSED_HARDWARE_TRANSPORT_BLOCKED",
            "evidence": qparams["requant_multiplier"]["sha256"],
        },
        {
            "capability": "arbitrary_uint8_zero_point",
            "status": "INSTANCE_ZP0_ONLY",
            "evidence": 0,
        },
        {
            "capability": "nearest_even_after_sequential_fp32_multiply",
            "status": "HARDWARE_ORDER_UNKNOWN",
            "evidence": "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
        },
        {
            "capability": "uint8_saturation",
            "status": "STRUCTURE_OR_PRIMITIVE_ONLY",
            "evidence": NATIVE_TEMPLATE_PATH,
        },
        {
            "capability": "ga_topology",
            "status": "ONE_STAGE_FUSED_STRUCTURE_ONLY",
            "evidence": NATIVE_TEMPLATE_PATH,
        },
        {
            "capability": "logical_shape_and_layout",
            "status": "CLOSED_NCHW",
            "evidence": request["request_sha256"],
        },
        {
            "capability": "physical_layout_transaction_tail",
            "status": "B_LAYOUT_APPROVAL",
            "evidence": None,
        },
        {
            "capability": "buffer_supply_demand_and_lifetime",
            "status": "NOT_MATERIALIZED",
            "evidence": None,
        },
        {
            "capability": "typed_handler",
            "status": "PLACEHOLDER_BLOCKED",
            "evidence": NATIVE_CONTROL_PATH,
        },
        {
            "capability": "mapper_registration",
            "status": "MISSING_OR_UNPROVEN",
            "evidence": NATIVE_MAPPER_PATH,
        },
        {
            "capability": "execplan_and_materialized_roundtrip",
            "status": "B_EXECPLAN_TYPED_TRANSPORT",
            "evidence": NATIVE_MODELS_PATH,
        },
    ]

    blockers = [
        {
            "id": "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
            "status": "OPEN_CONTRADICTED",
            "priority": 1,
            "minimum_counterexample": counterexample["id"],
        },
        {
            "id": "B_QUANT_TAIL_FMA_ROUNDING_POINT",
            "status": "OPEN_INHERITED_CURRENT_RULE",
            "priority": 2,
            "minimum_counterexample": "400 * bits(0x3d828f5c): sequential=26 fused=25",
        },
        {
            "id": "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
            "status": "OPEN",
            "priority": 3,
        },
        {
            "id": "B_LAYOUT_APPROVAL",
            "status": "OPEN_TYPED_REQUEST",
            "priority": 4,
        },
        {
            "id": "B_QUANT_TAIL_TYPED_BINDING",
            "status": "OPEN_PLACEHOLDER",
            "priority": 5,
        },
        {
            "id": "B_QUANT_TAIL_MAPPER_REGISTRATION",
            "status": "OPEN_MISSING_OR_UNPROVEN",
            "priority": 6,
        },
        {
            "id": "B_EXECPLAN_TYPED_TRANSPORT",
            "status": "OPEN",
            "priority": 7,
        },
        {
            "id": "B_NODE0004_C0_DEPENDENCY",
            "status": "OPEN_C0_PENDING",
            "priority": 8,
        },
    ]
    return {
        "request": {
            "request_id": request["request_id"],
            "request_sha256": request["request_sha256"],
            "identity": identity,
            "predecessor_hw_op_ids": request["predecessor_hw_op_ids"],
            "emission_policy": request["emission_policy"],
        },
        "tail_class": {
            "name": "REQUANT_INT32_PER_CHANNEL_FP32_MULTIPLIER_TO_UINT8_ZP0",
            "ingress": "signed_int32",
            "scale_kind": "per_channel_float32_multiplier_axis0",
            "output_qdomain": "uint8",
            "zero_point_class": "scalar_zero",
            "rounding": "nearest_even_after_sequential_fp32_multiply",
            "saturation": "[0,255]",
            "exact_division_required": False,
        },
        "qparam_identity": qparams,
        "shape_layout": shape_layout,
        "formal_w3_replay": w3,
        "native_source_audit": native,
        "minimum_counterexample": counterexample,
        "capability_matrix": capability_matrix,
        "pure_configuration_decision": {
            "exact_path_exists": False,
            "decision": "NO_EXACT_PURE_CONFIGURATION_PATH_CURRENTLY_PROVEN",
            "first_unavoidable_capability": (
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS"
            ),
            "reason": (
                "The authorized one-stage primitive uses contradicted signed "
                "INT32 conversion, while the only current guard route is not a "
                "released exact signed-ingress capability. Sequential RNE order, "
                "physical layout, qparam handler, mapper, and execplan transport "
                "also remain open."
            ),
        },
        "blockers": blockers,
        "bypass_annotation": {
            "classification": "NOT_ACTIVATED_DEPENDENCY_ONLY",
            "config_only_correctness_baseline": False,
            "bypass_reason": (
                "native signed ingress and sequential rounding are not exact"
            ),
            "contradicted_or_missing_native_path": [
                "direct signed INT32-to-FP32 conversion",
                "sequential multiply then RNE",
                "typed per-channel qparam transport",
                "approved node0004 physical layout",
            ],
            "exact_equivalence_scope": (
                "A future path must cover the legal signed INT32 domain and the "
                "full frozen node0004 W3 tensor."
            ),
            "materialized_configuration_mechanism": None,
            "performance_and_resource_cost": (
                "not estimated before C0 and before an exact route exists"
            ),
            "unresolved_production_blocker": [
                item["id"] for item in blockers
            ],
            "claim_boundary": (
                "Fresh dependency analysis only; no config-only baseline, target "
                "JSON, full Conv assembly, or release claim."
            ),
        },
        "dependency_for_node0004_c1": {
            "consumer": "node0004 complete Conv C1 after C0",
            "provided": [
                "fresh qparam identity",
                "fresh formula/W3 replay",
                "tail class",
                "logical shape and byte counts",
                "first arithmetic counterexample",
                "native handler/transport gap",
            ],
            "c0_status": "PENDING",
            "full_conv_assembly_allowed": False,
            "tail_target_generation_allowed": False,
            "required_next_authority": (
                "C0 path selection plus a proven exact signed-ingress and "
                "sequential-rounding route"
            ),
            "physical_endpoint_binding": {
                "same_storage": None,
                "base": None,
                "offset": None,
                "read_coverage": None,
                "accepted_lifetime": None,
                "terminal": None,
            },
        },
        "scope": {
            "old_node0004_assets_consumed": False,
            "target_json_generated": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_or_sca_generated": False,
            "full_conv_assembled": False,
            "server_files_inspected": False,
            "server_package_generated": False,
            "server_run_performed": False,
            "candidate_release": False,
            "package_release": "NONE",
        },
    }


def _source_identities(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "sha256": sha256_file(root / path),
            "reason": reason,
            "gate": "current_match_fail_closed",
        }
        for path, reason in CURRENT_MATCH_SOURCES
    ]


def build_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    analysis = _semantic_analysis(root)
    return {
        "schema": SCHEMA,
        "status": "FRESH_C1_DEPENDENCY_BLOCKED_NO_EXACT_CONFIG_PATH",
        "mainline_thread_id": "019fa2ca-72bc-7753-8d58-81e59bc76c88",
        "plan_read_receipt": {
            "path": PLAN_PATH,
            "sha256": sha256_file(root / PLAN_PATH),
            "gate": "mutable_provenance_only",
            "current_match_required": False,
        },
        "source_policy": {
            "allowed_classes": [
                "typed lowering/request",
                "formal ONNX model and W3 tensors/manifests",
                "current rules and mainline override",
                "hash-bound authorized native ndp-sim source",
            ],
            "forbidden_source_fragments": list(FORBIDDEN_SOURCE_FRAGMENTS),
            "old_node0004_assets_are_negative_history_only": True,
        },
        "source_identities": _source_identities(root),
        **analysis,
    }


def validate_contract(
    contract_path: Path, project_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise Node0004FreshTailError(
            f"unexpected contract schema: {contract.get('schema')}"
        )
    if contract.get("status") != (
        "FRESH_C1_DEPENDENCY_BLOCKED_NO_EXACT_CONFIG_PATH"
    ):
        raise Node0004FreshTailError("fresh C1 contract status changed")

    source_paths = [item["path"] for item in contract["source_identities"]]
    for path in source_paths:
        normalized = path.replace("\\", "/").lower()
        if any(fragment.lower() in normalized for fragment in FORBIDDEN_SOURCE_FRAGMENTS):
            raise Node0004FreshTailError(
                f"forbidden historical node0004 source consumed: {path}"
            )
    expected_paths = [path for path, _ in CURRENT_MATCH_SOURCES]
    if source_paths != expected_paths:
        raise Node0004FreshTailError(
            "fresh source allowlist changed or is incomplete"
        )
    source_receipts = []
    for item in contract["source_identities"]:
        path = root / item["path"]
        if not path.is_file():
            raise Node0004FreshTailError(
                f"fresh source is missing: {item['path']}"
            )
        actual = sha256_file(path)
        if actual != item["sha256"]:
            raise Node0004FreshTailError(
                f"fresh source identity changed: {item['path']} "
                f"expected={item['sha256']} actual={actual}"
            )
        source_receipts.append(
            {
                "path": item["path"],
                "sha256": actual,
                "matched": True,
                "gate": "current_match_fail_closed",
            }
        )

    fresh = _semantic_analysis(root)
    for field, expected in fresh.items():
        if contract.get(field) != expected:
            raise Node0004FreshTailError(
                f"contract field differs from fresh sources: {field}"
            )
    scope = contract["scope"]
    if any(
        scope[key]
        for key in (
            "old_node0004_assets_consumed",
            "target_json_generated",
            "mapping_generated",
            "bitstream_generated",
            "execplan_or_sca_generated",
            "full_conv_assembled",
            "server_files_inspected",
            "server_package_generated",
            "server_run_performed",
            "candidate_release",
        )
    ):
        raise Node0004FreshTailError("forbidden generation/release scope widened")
    if scope["package_release"] != "NONE":
        raise Node0004FreshTailError("package release must remain NONE")

    plan_receipt = contract["plan_read_receipt"]
    current_plan_sha = sha256_file(root / PLAN_PATH)
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS_FRESH_C1_DEPENDENCY_BLOCKED_NO_EXACT_CONFIG_PATH",
        "contract": {
            "path": contract_path.relative_to(root).as_posix(),
            "sha256": sha256_file(contract_path),
        },
        "source_identity_count": len(source_receipts),
        "source_identities": source_receipts,
        "plan_read_receipt": {
            "recorded_sha256": plan_receipt["sha256"],
            "current_sha256": current_plan_sha,
            "current_match": plan_receipt["sha256"] == current_plan_sha,
            "gate": "mutable_provenance_only",
        },
        "request_id": REQUEST_ID,
        "tail_class": contract["tail_class"]["name"],
        "qparam_identity": {
            "multiplier_sha256": contract["qparam_identity"][
                "requant_multiplier"
            ]["sha256"],
            "y_zero_point": contract["qparam_identity"]["y_zero_point"][
                "value"
            ],
        },
        "formal_w3_mismatch_count": contract["formal_w3_replay"][
            "mismatch_count"
        ],
        "formal_w3_minus_one_count": contract["formal_w3_replay"][
            "accumulator"
        ]["minus_one_count"],
        "pure_configuration_decision": contract[
            "pure_configuration_decision"
        ],
        "first_unavoidable_capability": contract[
            "pure_configuration_decision"
        ]["first_unavoidable_capability"],
        "physical_layout_status": contract["shape_layout"][
            "physical_layout_status"
        ],
        "typed_transport_status": contract["native_source_audit"][
            "typed_transport"
        ]["status"],
        "c0_status": contract["dependency_for_node0004_c1"]["c0_status"],
        "target_json_generated": False,
        "full_conv_assembled": False,
        "server_package_generated": False,
        "package_release": "NONE",
    }


def write_contract(project_root: Path, output_path: Path) -> dict[str, Any]:
    contract = build_contract(project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return contract


def write_report(
    contract_path: Path, project_root: Path, output_path: Path
) -> dict[str, Any]:
    report = validate_contract(contract_path, project_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
