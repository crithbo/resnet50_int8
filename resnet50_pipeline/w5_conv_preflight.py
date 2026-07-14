"""Fail-closed W5 preflight for the first real ResNet-50 INT8 Conv tile.

The report produced here deliberately stops before target JSON generation.  The
locked target configuration repository has no Conv template and the workspace
has no runner that consumes the exported emulator bundle.  What can be proven
without guessing is still useful: the real model tensors and typed qparams are
bound, one approved HIGH-4 physical tile is materialized, and its four reduction
segments are checked against the W3 INT32/UINT8 goldens bit-for-bit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

from .conv28_layout import QLinearConvPhysicalLayout
from .golden.qlinear_conv import requantize_uint8
from .hardware_approval import validate_hardware_approval_file
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .profile28 import GROUP4X7_BATCH_CHANNEL28_PROFILE
from .topology28 import Direction, TOPOLOGY28
from .typed_config_parameters import validate_typed_config_parameter_contract


SCHEMA_VERSION = "0.1"
REPORT_KIND = "w5_first_real_conv_preflight"
SELECTED_NODE_ID = "node-0004"
ACCUMULATE_HW_OP_ID = "hwop-0004-00"
REQUANT_HW_OP_ID = "hwop-0004-01"
OFFICIAL_CONFIG_COMMIT = "e299b2804448242d1589b3e58ed7c5a9a5eca09f"
MODEL_SHA256 = "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"


class W5ConvPreflightError(ValueError):
    """The first real Conv preflight violates a locked invariant."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise W5ConvPreflightError(f"cannot read JSON evidence: {path}") from error
    if not isinstance(value, dict):
        raise W5ConvPreflightError(f"JSON evidence must be an object: {path}")
    return value


def _verify_source_commit(source_root: Path) -> str:
    resolved = source_root.resolve()
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={resolved.as_posix()}",
            "rev-parse",
            "HEAD",
        ],
        cwd=resolved,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    commit = completed.stdout.strip()
    if completed.returncode or commit != OFFICIAL_CONFIG_COMMIT:
        raise W5ConvPreflightError(
            "official DeepSeek configuration source does not match the locked commit"
        )
    return commit


def _record_by_hw_op(contract: dict[str, Any], hw_op_id: str) -> dict[str, Any]:
    matches = [item for item in contract["hw_ops"] if item.get("hw_op_id") == hw_op_id]
    if len(matches) != 1:
        raise W5ConvPreflightError(f"expected one typed record for {hw_op_id}")
    return matches[0]


def _port(record: dict[str, Any], direction: str, role: str) -> dict[str, Any]:
    matches = [
        item for item in record["ports"][direction] if item.get("role") == role
    ]
    if len(matches) != 1:
        raise W5ConvPreflightError(
            f"expected one {direction} port {role!r} for {record['hw_op_id']}"
        )
    return matches[0]


def _parameter(record: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [item for item in record["parameters"] if item.get("name") == name]
    if len(matches) != 1:
        raise W5ConvPreflightError(
            f"expected one typed parameter {name!r} for {record['hw_op_id']}"
        )
    return matches[0]


def _load_npy(root: Path, manifest: dict[str, Any], record: dict[str, Any]) -> np.ndarray:
    relative = record.get("path")
    if not isinstance(relative, str) or not relative:
        raise W5ConvPreflightError("W3 tensor record has no payload path")
    path = root / relative
    if not path.is_file() or sha256_file(path) != record.get("sha256"):
        raise W5ConvPreflightError(f"W3 tensor payload/hash mismatch: {path}")
    value = np.load(path, allow_pickle=False)
    if str(value.dtype) != record.get("dtype") or list(value.shape) != record.get("shape"):
        raise W5ConvPreflightError(f"W3 tensor dtype/shape mismatch: {path}")
    return np.ascontiguousarray(value)


def _array_sha256(value: np.ndarray) -> str:
    return sha256_bytes(np.ascontiguousarray(value).tobytes(order="C"))


def _initializer_values(model_path: Path) -> dict[str, np.ndarray]:
    if sha256_file(model_path) != MODEL_SHA256:
        raise W5ConvPreflightError("formal ONNX model hash differs")
    model = onnx.load(str(model_path))
    return {
        item.name: np.ascontiguousarray(numpy_helper.to_array(item))
        for item in model.graph.initializer
    }


def _initializer(
    values: dict[str, np.ndarray],
    runtime_manifest: dict[str, Any],
    descriptor: dict[str, Any],
) -> np.ndarray:
    tensor_id = descriptor["tensor_id"]
    record = runtime_manifest["initializers"].get(tensor_id)
    if not isinstance(record, dict):
        raise W5ConvPreflightError(f"W3 initializer record missing: {tensor_id}")
    if (
        record.get("onnx_name") != descriptor.get("onnx_name")
        or record.get("sha256") != descriptor.get("identity_sha256")
        or record.get("dtype") != descriptor.get("dtype")
        or record.get("shape") != descriptor.get("shape")
    ):
        raise W5ConvPreflightError(f"typed/W3 initializer identity mismatch: {tensor_id}")
    try:
        value = values[descriptor["onnx_name"]]
    except KeyError as error:
        raise W5ConvPreflightError(f"ONNX initializer payload missing: {tensor_id}") from error
    if (
        str(value.dtype) != descriptor["dtype"]
        or list(value.shape) != descriptor["shape"]
        or _array_sha256(value) != descriptor["identity_sha256"]
    ):
        raise W5ConvPreflightError(f"ONNX initializer payload mismatch: {tensor_id}")
    return value


def _tensor_provenance(
    port_name: str,
    descriptor: dict[str, Any],
    value: np.ndarray,
    payload_source: str,
) -> dict[str, Any]:
    return {
        "port": port_name,
        "tensor_id": descriptor["tensor_id"],
        "onnx_name": descriptor.get("onnx_name"),
        "kind": descriptor["kind"],
        "dtype": str(value.dtype),
        "shape": list(value.shape),
        "identity_sha256": descriptor["identity_sha256"],
        "payload_sha256": _array_sha256(value),
        "payload_source": payload_source,
        "verified": True,
    }


def _simulator_entry_probe(
    project_root: Path,
    source_root: Path,
    authority: dict[str, Any],
    backend: dict[str, Any],
) -> dict[str, Any]:
    inventory = authority.get("inventory", {})
    target = backend.get("backends", {}).get("target_simulator", {})
    config_backend = backend.get("backends", {}).get("target_config_toolchain", {})
    main_path = source_root / "model_execplan" / "main.py"
    writer_path = (
        source_root
        / "model_execplan"
        / "src"
        / "execution_plan_generator"
        / "output_writer.py"
    )
    runner_path = source_root / "run_all_slices.py"
    main_text = main_path.read_text(encoding="utf-8")
    writer_text = writer_path.read_text(encoding="utf-8")
    runner_text = runner_path.read_text(encoding="utf-8")
    if (
        "write_emulator_bundle" not in main_text
        or "dram_data.bin" not in writer_text
        or "bitstream/main.py" not in runner_text
    ):
        raise W5ConvPreflightError("DeepSeek packaging call chain differs from the audit")
    if (
        target
        != {
            "status": "unapproved_missing_authoritative_binding",
            "approved": False,
            "implementation_available": False,
        }
        or config_backend.get("can_execute_numerical_model") is not False
        or inventory.get("named_conv_template_count") != 0
    ):
        raise W5ConvPreflightError("target simulator/Conv inventory is no longer fail-closed")
    return {
        "status": "missing_from_current_workspace",
        "source_repository": config_backend["source_repository"],
        "source_commit": config_backend["source_commit"],
        "authoritative_paths": config_backend["authoritative_paths"],
        "packager": {
            "command": (
                ".\\.venv\\Scripts\\python.exe main.py <operator_graph.json> "
                "--export-emulator"
            ),
            "working_directory": "ndp-sim-ref/model_execplan",
            "entrypoint": "model_execplan/main.py",
            "entrypoint_sha256": sha256_file(main_path),
            "function": "write_emulator_bundle",
            "function_source": (
                "model_execplan/src/execution_plan_generator/output_writer.py"
            ),
            "function_source_sha256": sha256_file(writer_path),
            "inputs": ["operator graph JSON", "per-slice matrix_*.bin payloads"],
            "outputs": ["patched operator JSON", "dram_data.bin"],
            "executes_numerical_model": False,
        },
        "bitstream_only_driver": {
            "entrypoint": "run_all_slices.py",
            "entrypoint_sha256": sha256_file(runner_path),
            "invoked_program": "bitstream/main.py",
            "executes_numerical_model": False,
        },
        "target_runner": {
            "command": None,
            "version": None,
            "input_package": None,
            "exit_code_contract": None,
            "physical_d_output_format": None,
        },
        "workspace_contract": target,
        "w6_blocker": "B_TARGET_SIMULATOR_ENTRY",
        "search_scope": [
            "locked ndp-sim-ref source call sites",
            "contracts/backend.json",
            "contracts/target_config_authority_audit.json",
        ],
        "manual_path_probe": {
            "command": "Get-Command *emulator*,*simulator* -ErrorAction SilentlyContinue",
            "observed_result": "NO_EMULATOR_OR_SIMULATOR_COMMAND_ON_PATH",
            "evidence_scope": "2026-07-14 Local workspace",
        },
        "project_root": project_root.name,
    }


def _legacy_conv_generator_probe(source_root: Path) -> dict[str, Any]:
    generator_path = source_root / "config" / "config_generator_ver2.py"
    nse_path = source_root / "config" / "config_nse.py"
    parameters_path = source_root / "config" / "utils" / "config_parameters.py"
    generator = generator_path.read_text(encoding="utf-8")
    nse = nse_path.read_text(encoding="utf-8")
    parameters = parameters_path.read_text(encoding="utf-8")
    required_generator_fragments = (
        '"sa_pe_computation_data_type":  0',
        '"sa_pe_bias_enable":            0',
        '"mse_stream_base_addr": 0x10_0000',
        '"mse_stream_base_addr": 0x20_0000',
    )
    if (
        "SLICE_NUM = 16" not in parameters
        or "SA_PE_COMP_INT8_TYPE = 0b00" not in parameters
        or any(fragment not in generator for fragment in required_generator_fragments)
        or '"sa_pe_bias_enable":            0' not in nse
    ):
        raise W5ConvPreflightError("legacy Conv generator evidence differs")
    semantic_text = (generator + "\n" + nse).lower()
    return {
        "status": "legacy16_reference_only",
        "files": [
            {
                "path": "config/config_generator_ver2.py",
                "sha256": sha256_file(generator_path),
            },
            {"path": "config/config_nse.py", "sha256": sha256_file(nse_path)},
            {
                "path": "config/utils/config_parameters.py",
                "sha256": sha256_file(parameters_path),
            },
        ],
        "observed": {
            "slice_count": 16,
            "sa_int8_selector": 0,
            "sa_bias_enable": 0,
            "hardcoded_activation_base": "0x10_0000",
            "hardcoded_weight_base": "0x20_0000",
            "typed_zero_point_reference_present": "zero_point" in semantic_text,
            "typed_scale_reference_present": "scale" in semantic_text,
            "requant_reference_present": "requant" in semantic_text,
        },
        "missing_for_w5": [
            "28-slice target JSON field mapping",
            "nonzero INT32 bias load/enable semantics",
            "first/middle/last-K persistent INT32 psum semantics",
            "typed x/w/y qparam transport",
            "per-channel nearest-even UINT8 requant and saturation",
        ],
        "can_serve_as_target_template": False,
        "interpretation": (
            "shape/stream hints may be reviewed, but old16 hardcoded fields cannot "
            "authorize a target JSON or bitstream"
        ),
    }


def _checked_int32(value: np.ndarray, label: str) -> np.ndarray:
    minimum = int(value.min())
    maximum = int(value.max())
    limits = np.iinfo(np.int32)
    if minimum < limits.min or maximum > limits.max:
        raise W5ConvPreflightError(
            f"{label} exceeds INT32: minimum={minimum}, maximum={maximum}"
        )
    return value.astype(np.int32)


def _compare_tile(
    values: dict[str, np.ndarray],
    layout: QLinearConvPhysicalLayout,
    bundle: Any,
) -> dict[str, Any]:
    ring = TOPOLOGY28.high_ring_for_group(0)
    destination = ring.owners[0]
    traversal = ring.traverse(destination, Direction.PREV)
    p_region = bundle.region("P", destination)
    d_region = bundle.region("D", destination)
    if (
        destination != 0
        or p_region.sample_start != 0
        or p_region.sample_count != 3
        or p_region.logical_start != 0
        or p_region.logical_count != 16
    ):
        raise W5ConvPreflightError("selected first physical Conv tile differs")

    activation = values["A"][:3].astype(np.int64)
    weight = values["B"][:16, :, 0, 0].astype(np.int64)
    x_zero_point = int(values["x_zero_point"].reshape(-1)[0])
    w_zero_point = values["w_zero_point"][:16].astype(np.int64)
    accumulator = np.broadcast_to(
        values["bias"][:16].astype(np.int64).reshape(1, 16, 1, 1),
        (3, 16, 56, 56),
    ).copy()
    lifecycle: list[dict[str, Any]] = []
    for index, source_slice in enumerate(traversal):
        region = bundle.region("A", source_slice)
        start = region.logical_start
        count = region.logical_count
        a = activation[:, start : start + count, :, :] - x_zero_point
        b = weight[:, start : start + count] - w_zero_point.reshape(-1, 1)
        partial = np.einsum("nchw,kc->nkhw", a, b, dtype=np.int64, optimize=True)
        accumulator += partial
        checked = _checked_int32(accumulator, f"K segment {index}")
        phase = "first" if index == 0 else "last" if index == len(traversal) - 1 else "middle"
        lifecycle.append(
            {
                "phase": phase,
                "source_slice": source_slice,
                "owner_step": region.owner_step,
                "channel_start": start,
                "channel_count": count,
                "int8_pair_count_per_output": count // 2,
                "bias_action": "initialize_before_segment" if index == 0 else "preserve",
                "psum_action": "requantize_after_segment" if phase == "last" else "persist_int32",
                "logical_psum_sha256": _array_sha256(checked),
                "minimum": int(checked.min()),
                "maximum": int(checked.max()),
            }
        )

    recomputed_p = _checked_int32(accumulator, "final tile accumulator")
    expected_p = np.ascontiguousarray(values["P"][:3, :16])
    p_mismatches = int(np.count_nonzero(recomputed_p != expected_p))
    if p_mismatches:
        raise W5ConvPreflightError(f"real tile P differs from W3 golden: {p_mismatches}")

    multiplier = np.asarray(
        np.float32(values["x_scale"][0])
        * values["w_scale"][:16].astype(np.float32)
        / np.float32(values["y_scale"][0]),
        dtype=np.float32,
    )
    recomputed_d = requantize_uint8(
        recomputed_p, multiplier, values["y_zero_point"]
    )
    expected_d = np.ascontiguousarray(values["D"][:3, :16])
    d_mismatches = int(np.count_nonzero(recomputed_d != expected_d))
    if d_mismatches:
        raise W5ConvPreflightError(f"real tile D differs from W3 golden: {d_mismatches}")

    physical_p = np.ascontiguousarray(np.moveaxis(expected_p, 1, -1)).astype(
        "<i4", copy=False
    )
    physical_d = np.ascontiguousarray(np.moveaxis(expected_d, 1, -1))
    p_payload = bundle.read("P", destination)[: p_region.payload_bytes]
    d_payload = bundle.read("D", destination)[: d_region.payload_bytes]
    if p_payload != physical_p.tobytes(order="C"):
        raise W5ConvPreflightError("physical P bytes differ from W4 layout")
    if d_payload != physical_d.tobytes(order="C"):
        raise W5ConvPreflightError("physical D bytes differ from W4 layout")

    p_first = layout.explain_coordinate(bundle, bundle.tensor_ids["P"], (0, 0, 0, 0))[0]
    d_first = layout.explain_coordinate(bundle, bundle.tensor_ids["D"], (0, 0, 0, 0))[0]
    return {
        "status": "golden_and_physical_preflight_passed",
        "target_simulator_comparison_status": "not_run_missing_runner",
        "tile_id": "node-0004-group0-k000-015-n000-002",
        "group_id": 0,
        "high_ring_owners": list(ring.owners),
        "reduction_traversal": list(traversal),
        "destination_slice": destination,
        "logical_ranges": {
            "N": [0, 3],
            "K": [0, 16],
            "H": [0, 56],
            "W": [0, 56],
            "C": [0, 64],
        },
        "logical_im2col_projection": {"M": 3 * 56 * 56, "N": 16, "K": 64},
        "physical_shape": [3, 56, 56, 16],
        "k_lifecycle": lifecycle,
        "requant": {
            "multiplier_dtype": "float32",
            "multiplier_shape": [16],
            "multiplier_sha256": _array_sha256(multiplier),
            "rounding": "nearest_even_numpy_rint_golden",
            "output_zero_point": int(values["y_zero_point"][0]),
            "saturation": "uint8_[0,255]",
            "target_encoding_status": "unresolved",
        },
        "comparisons": {
            "P": {
                "dtype": "int32",
                "element_count": int(expected_p.size),
                "mismatch_count": p_mismatches,
                "recomputed_sha256": _array_sha256(recomputed_p),
                "w3_sha256": _array_sha256(expected_p),
                "physical_sha256": sha256_bytes(p_payload),
                "physical_base_address": p_region.base_address,
                "physical_base_address_hex": f"0x{p_region.base_address:08x}",
                "first_coordinate_address": int(p_first["address"]),
            },
            "D": {
                "dtype": "uint8",
                "element_count": int(expected_d.size),
                "mismatch_count": d_mismatches,
                "recomputed_sha256": _array_sha256(recomputed_d),
                "w3_sha256": _array_sha256(expected_d),
                "physical_sha256": sha256_bytes(d_payload),
                "physical_base_address": d_region.base_address,
                "physical_base_address_hex": f"0x{d_region.base_address:08x}",
                "first_coordinate_address": int(d_first["address"]),
            },
        },
    }


def build_w5_first_conv_preflight(
    project_root: Path,
    source_root: Path | None = None,
) -> dict[str, Any]:
    """Build the deterministic, fail-closed first-real-Conv W5 report."""

    root = project_root.resolve()
    source = (source_root or root / "ndp-sim-ref").resolve()
    commit = _verify_source_commit(source)

    typed_path = root / "contracts" / "typed_config_parameter_contract.json"
    typed = _load_json(typed_path)
    validate_typed_config_parameter_contract(typed)
    accumulate = _record_by_hw_op(typed, ACCUMULATE_HW_OP_ID)
    requant = _record_by_hw_op(typed, REQUANT_HW_OP_ID)
    if (
        accumulate.get("node_id") != SELECTED_NODE_ID
        or requant.get("node_id") != SELECTED_NODE_ID
        or accumulate["logical_geometry"]["attributes"]
        != requant["logical_geometry"]["attributes"]
    ):
        raise W5ConvPreflightError("selected Conv lowering identity differs")

    approval = validate_hardware_approval_file(
        root / "contracts" / "hardware_approval.json",
        root / "contracts" / "architecture.json",
    )
    conv_binding = approval["operator_bindings"].get("conv", {})
    if (
        approval.get("gate_authority_eligible") is not True
        or conv_binding
        != {
            "layout_id": "w4_conv_group4x7_28_candidate_v1",
            "communication_domain": "high4",
        }
    ):
        raise W5ConvPreflightError("W4 Conv layout/profile approval differs")

    runtime_root = root / "artifacts" / "w3" / "golden_batch16"
    subop_root = root / "artifacts" / "w3" / "subop_batch16"
    runtime_manifest = _load_json(runtime_root / "manifest.json")
    subop_manifest = _load_json(subop_root / "manifest.json")
    initializers = _initializer_values(
        root / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"
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
    for port_name in (
        "B",
        "bias",
        "w_zero_point",
        "x_zero_point",
        "x_scale",
        "w_scale",
        "y_scale",
        "y_zero_point",
    ):
        values[port_name] = _initializer(
            initializers, runtime_manifest, descriptors[port_name]
        )

    direct_parameters = {
        item["name"]: item
        for item in (*accumulate["parameters"], *requant["parameters"])
        if item["provenance"]["kind"] == "onnx_initializer"
    }
    for name, parameter in direct_parameters.items():
        if _array_sha256(values[name]) != parameter["value"]["value_sha256"]:
            raise W5ConvPreflightError(f"typed parameter transport lost {name}")
    multiplier = np.asarray(
        np.float32(values["x_scale"][0])
        * values["w_scale"].astype(np.float32)
        / np.float32(values["y_scale"][0]),
        dtype=np.float32,
    )
    if _array_sha256(multiplier) != _parameter(
        requant, "requant_multiplier"
    )["value"]["value_sha256"]:
        raise W5ConvPreflightError("typed per-channel requant multiplier differs")

    tensor_ids = {name: descriptors[name]["tensor_id"] for name in descriptors}
    layout = QLinearConvPhysicalLayout(
        profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE
    )
    attributes = accumulate["logical_geometry"]["attributes"]
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
        tensor_ids=tensor_ids,
    )
    layout_validation = layout.validate(bundle)

    provenance = []
    for port_name in (
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
    ):
        source_name = (
            "artifacts/w3/subop_batch16"
            if port_name == "P"
            else "artifacts/w3/golden_batch16"
            if port_name in {"A", "D"}
            else "formal ONNX initializer"
        )
        provenance.append(
            _tensor_provenance(
                port_name, descriptors[port_name], values[port_name], source_name
            )
        )

    authority_path = root / "contracts" / "target_config_authority_audit.json"
    backend_path = root / "contracts" / "backend.json"
    authority = _load_json(authority_path)
    backend = _load_json(backend_path)
    simulator_probe = _simulator_entry_probe(root, source, authority, backend)
    legacy_generator_probe = _legacy_conv_generator_probe(source)
    tile = _compare_tile(values, layout, bundle)

    plan = bundle.plan
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "status": "g5_preflight_blocked_before_target_json",
        "selection": {
            "node_id": SELECTED_NODE_ID,
            "onnx_name": accumulate["onnx_name"],
            "onnx_op_type": "QLinearConv",
            "hw_op_ids": [ACCUMULATE_HW_OP_ID, REQUANT_HW_OP_ID],
            "reason": "first real 1x1 stride-1 Conv recommended by W5 handoff",
        },
        "source_identity": {
            "model_sha256": MODEL_SHA256,
            "typed_contract_path": "contracts/typed_config_parameter_contract.json",
            "typed_contract_sha256": sha256_file(typed_path),
            "hardware_approval_path": "contracts/hardware_approval.json",
            "hardware_approval_sha256": approval["sha256"],
            "target_config_authority_path": "contracts/target_config_authority_audit.json",
            "target_config_authority_sha256": sha256_file(authority_path),
            "backend_contract_path": "contracts/backend.json",
            "backend_contract_sha256": sha256_file(backend_path),
            "target_config_commit": commit,
        },
        "logical_instance": {
            "activation_shape": list(plan.activation_shape),
            "weight_shape": list(plan.weight_shape),
            "output_shape": list(plan.output_shape),
            "attributes": attributes,
            "dtype_path": ["uint8_A", "int8_B", "int32_bias_and_P", "uint8_D"],
            "per_channel_axis": 0,
            "parameter_transport": "lossless_into_preflight_only",
        },
        "field_provenance": provenance,
        "physical_preflight": {
            "status": "passed",
            "profile_id": approval["network_profile"],
            "layout_id": conv_binding["layout_id"],
            "runtime_layout_contract": plan.contract,
            "communication_domain": conv_binding["communication_domain"],
            "slice_count": plan.geometry.slice_count,
            "instruction_mask": "0b1111111111111111111111111111",
            "c_tile": plan.c_tile,
            "k_tile": plan.k_tile,
            "c_padded": plan.c_padded,
            "storage_sample_count": plan.storage_sample_count,
            "per_slice_used_bytes": plan.per_slice_used_bytes,
            "per_slice_capacity_bytes": plan.per_slice_capacity_bytes,
            "address_scope": "W4 per-operator physical placeholder; W7 address plan not assigned",
            "layout_validation": layout_validation,
        },
        "first_tile_golden_preflight": tile,
        "deepseek_target_simulator_entry": simulator_probe,
        "target_configuration": {
            "official_json_inventory_count": authority["inventory"]["json_count"],
            "official_named_conv_template_count": authority["inventory"][
                "named_conv_template_count"
            ],
            "patched_json_generated": False,
            "bitstream_generated": False,
            "mapping_review_generated": False,
            "unknown_fields_rejected": True,
            "legacy_generator_probe": legacy_generator_probe,
            "unresolved_target_bindings": [
                {
                    "blocker": "B_CONV_TEMPLATE_ABSENT",
                    "fields": ["CONFIG", "dram_loop_configs", "lc_pe_configs"],
                    "reason": "locked target source has zero named Conv templates",
                },
                {
                    "blocker": "B_CONV_INT8_SA",
                    "fields": ["special_array.mode", "special_array.data_type"],
                    "reason": "no approved UINT8xINT8-to-INT32 SA field encoding",
                },
                {
                    "blocker": "B_CONV_BIAS_PSUM",
                    "fields": ["buffer_config", "stream_engine", "special_array"],
                    "reason": "first/middle/last-K bias and persistent INT32 psum storage are unbound",
                },
                {
                    "blocker": "B_REQUANT_TARGET_NUMERICS",
                    "fields": ["general_array", "stream_engine"],
                    "reason": "per-channel multiplier encoding, nearest-even, saturation and unique flush are unbound",
                },
                {
                    "blocker": "B_EXECPLAN_TYPED_TRANSPORT",
                    "fields": ["OperatorSpec", "control_registers"],
                    "reason": "official execplan has no typed qparam/constants transport",
                },
            ],
        },
        "gate_state": {
            "w5_started": True,
            "g5_preflight": "blocked",
            "g5_passed": False,
            "g6_passed": False,
            "g8_passed": False,
            "target_simulator_numerical_status": "not_run",
            "golden_tile_status": "passed",
            "stop_expansion": True,
            "whole_network_generation_allowed": False,
            "next_required_evidence": [
                "authoritative target numerical simulator command/version/input/D format",
                "approved INT8 Conv JSON template or field-level register contract",
                "approved bias/psum/requant/qparam transport and unique-flush semantics",
            ],
        },
    }
    validate_w5_first_conv_preflight(report)
    return report


def validate_w5_first_conv_preflight(value: dict[str, Any]) -> None:
    """Reject any report that overstates the currently available evidence."""

    if value.get("schema_version") != SCHEMA_VERSION or value.get("report_kind") != REPORT_KIND:
        raise W5ConvPreflightError("W5 Conv preflight identity differs")
    if value.get("status") != "g5_preflight_blocked_before_target_json":
        raise W5ConvPreflightError("W5 Conv preflight must remain blocked")
    selection = value.get("selection", {})
    if selection.get("node_id") != SELECTED_NODE_ID or selection.get("hw_op_ids") != [
        ACCUMULATE_HW_OP_ID,
        REQUANT_HW_OP_ID,
    ]:
        raise W5ConvPreflightError("W5 Conv selection differs")
    target = value.get("target_configuration", {})
    if (
        target.get("official_named_conv_template_count") != 0
        or target.get("patched_json_generated") is not False
        or target.get("bitstream_generated") is not False
        or target.get("mapping_review_generated") is not False
        or target.get("unknown_fields_rejected") is not True
    ):
        raise W5ConvPreflightError("W5 Conv target configuration exceeded evidence")
    blocker_ids = {
        item.get("blocker") for item in target.get("unresolved_target_bindings", [])
    }
    required = {
        "B_CONV_TEMPLATE_ABSENT",
        "B_CONV_INT8_SA",
        "B_CONV_BIAS_PSUM",
        "B_REQUANT_TARGET_NUMERICS",
        "B_EXECPLAN_TYPED_TRANSPORT",
    }
    if blocker_ids != required:
        raise W5ConvPreflightError("W5 Conv blocker set differs")
    tile = value.get("first_tile_golden_preflight", {})
    comparisons = tile.get("comparisons", {})
    if (
        tile.get("status") != "golden_and_physical_preflight_passed"
        or tile.get("target_simulator_comparison_status")
        != "not_run_missing_runner"
        or comparisons.get("P", {}).get("mismatch_count") != 0
        or comparisons.get("D", {}).get("mismatch_count") != 0
        or len(tile.get("k_lifecycle", [])) != 4
    ):
        raise W5ConvPreflightError("W5 Conv golden tile evidence differs")
    simulator = value.get("deepseek_target_simulator_entry", {})
    if (
        simulator.get("status") != "missing_from_current_workspace"
        or simulator.get("target_runner", {}).get("command") is not None
        or simulator.get("packager", {}).get("executes_numerical_model") is not False
    ):
        raise W5ConvPreflightError("target simulator absence is not preserved")
    gate = value.get("gate_state", {})
    if (
        gate.get("w5_started") is not True
        or gate.get("g5_passed") is not False
        or gate.get("g6_passed") is not False
        or gate.get("stop_expansion") is not True
        or gate.get("whole_network_generation_allowed") is not False
    ):
        raise W5ConvPreflightError("W5 Conv gate state overclaims completion")
    # Ensure the public report remains deterministic JSON data.
    canonical_json_bytes(value)


__all__ = [
    "ACCUMULATE_HW_OP_ID",
    "REQUANT_HW_OP_ID",
    "SELECTED_NODE_ID",
    "W5ConvPreflightError",
    "build_w5_first_conv_preflight",
    "validate_w5_first_conv_preflight",
]
