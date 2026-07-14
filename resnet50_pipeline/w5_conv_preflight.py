"""Fail-closed W5 preflight for the first real ResNet-50 INT8 Conv tile.

The report deliberately stops before real 1x1 target JSON generation.  The
official repository has no named Conv template, but an operator-provided Conv
pseudocode config and the operator-confirmed NDPFuncModel Conv simulator are now
available.  The report keeps their remaining boundary explicit: the config can
be encoded and the simulator can execute real physical coordinates, while no
adapter yet makes the simulator consume that target JSON/bitstream.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper

from .adapters.ndp_rtl28_functional import NdpRtl28FunctionalAdapter
from .conv28_layout import QLinearConvPhysicalLayout
from .golden.qlinear_conv import requantize_uint8
from .hardware_approval import validate_hardware_approval_file
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .profile28 import GROUP4X7_BATCH_CHANNEL28_PROFILE
from .topology28 import Direction, TOPOLOGY28
from .typed_config_parameters import validate_typed_config_parameter_contract


SCHEMA_VERSION = "0.2"
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
    ndp = backend.get("backends", {}).get("ndp_conv_functional", {})
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
    simulator_path = (
        project_root / "NDPFuncModel" / "tools" / "physical_image_probe.py"
    )
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
        target.get("status")
        != "operator_confirmed_conv_backend_adapter_pending"
        or target.get("approved") is not False
        or target.get("identity_confirmed") is not True
        or target.get("implementation_available") is not True
        or target.get("backend") != "ndp_conv_functional"
        or target.get("config_adapter_available") is not False
        or ndp.get("status") != "operator_confirmed_conv_simulator_component"
        or ndp.get("entrypoint") != "tools/physical_image_probe.py"
        or not simulator_path.is_file()
        or config_backend.get("can_execute_numerical_model") is not False
        or inventory.get("named_conv_template_count") != 0
    ):
        raise W5ConvPreflightError("Conv simulator identity/config-adapter boundary differs")
    return {
        "status": "operator_confirmed_conv_backend_adapter_pending",
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
            "command": target["command"],
            "working_directory": "NDPFuncModel",
            "entrypoint": target["entrypoint"],
            "entrypoint_sha256": sha256_file(simulator_path),
            "version": ndp["source_commit"],
            "input_package": "physical_image_request schema 0.1",
            "exit_code_contract": "0 with one JSON object on stdout",
            "physical_d_output_format": "uint8 DRAM byte plus output_after in JSON",
            "supported_ops": target["supported_ops"],
            "can_dump_physical_output": target["can_dump_physical_output"],
            "consumes_target_json_or_bitstream": False,
            "config_adapter_available": False,
        },
        "workspace_contract": target,
        "w6_blocker": "B_CONV_SIMULATOR_CONFIG_ADAPTER",
        "search_scope": [
            "locked ndp-sim-ref source call sites",
            "contracts/backend.json",
            "contracts/target_config_authority_audit.json",
        ],
        "identity_basis": {
            "operator_confirmation": "NDPFuncModel conv_func is the Conv simulator",
            "local_entrypoint_verified": True,
            "target_json_binding_verified": False,
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


def _operator_conv_candidate_probe(project_root: Path) -> dict[str, Any]:
    evidence_path = project_root / "contracts" / "conv_full_encoder_evidence.json"
    evidence = _load_json(evidence_path)
    config_path = project_root / evidence["source"]["json_path"]
    pseudocode_path = project_root / evidence["source"]["pseudocode_path"]
    if (
        evidence.get("status")
        != "official_encoder_passed_candidate_semantics_unvalidated"
        or sha256_file(config_path) != evidence["source"]["json_sha256"]
        or sha256_file(pseudocode_path) != evidence["source"]["pseudocode_sha256"]
        or evidence["placement_repair"].get("constraint_cost") != 0
        or evidence["placement_repair"].get("connection_count") != 46
        or evidence["encoder"].get("exit_code") != 0
        or evidence["encoder"].get("mapping_status") != "zero_violations"
    ):
        raise W5ConvPreflightError("operator Conv candidate evidence differs")
    config = _load_json(config_path)
    if (
        config.get("special_array", {}).get("data_type") != "int8"
        or config.get("special_array", {}).get("bias_enable") != 1
        or config.get("special_array", {}).get("mode") != "gemm"
        or len(config.get("dram_loop_configs", {})) != 16
        or len(config.get("lc_pe_configs", {})) != 7
    ):
        raise W5ConvPreflightError("operator Conv candidate fields differ")
    output_root = project_root / "artifacts" / "w5" / "conv_full_audit" / "accepted"
    output_paths = {
        name: output_root / name for name in evidence["encoder"]["outputs"]
    }
    if any(path.is_file() for path in output_paths.values()):
        if not all(path.is_file() for path in output_paths.values()):
            raise W5ConvPreflightError("official Conv encoder artifacts are partial")
        for name, path in output_paths.items():
            record = evidence["encoder"]["outputs"][name]
            if (
                path.stat().st_size != record["size_bytes"]
                or sha256_file(path) != record["sha256"]
            ):
                raise W5ConvPreflightError(
                    f"official Conv encoder artifact differs: {name}"
                )
        review = _load_json(output_root / "mapping_review.json")
        if (
            review.get("summary", {}).get("connections") != 46
            or len(review.get("connection_mapping", [])) != 46
        ):
            raise W5ConvPreflightError("official Conv mapping review differs")
    return {
        "status": evidence["status"],
        "evidence_path": "contracts/conv_full_encoder_evidence.json",
        "evidence_sha256": sha256_file(evidence_path),
        "source": evidence["source"],
        "deterministic_repairs": evidence["deterministic_repairs"],
        "placement": {
            key: evidence["placement_repair"][key]
            for key in (
                "method",
                "mapping_cache_key",
                "connection_count",
                "logical_lc_count",
                "physical_lc_capacity",
                "logical_lc_pe_count",
                "physical_lc_pe_capacity",
                "constraint_cost",
            )
        },
        "encoder": {
            "repository": evidence["encoder"]["repository"],
            "commit": evidence["encoder"]["commit"],
            "entrypoint": evidence["encoder"]["entrypoint"],
            "command": evidence["encoder"]["command"],
            "exit_code": evidence["encoder"]["exit_code"],
            "mapping_status": evidence["encoder"]["mapping_status"],
            "outputs": evidence["encoder"]["outputs"],
        },
        "proven_fields": evidence["proven_fields"],
        "not_proven": evidence["not_proven"],
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
        "target_simulator_comparison_status": "not_run_missing_config_adapter",
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


def _compare_ndp_first_coordinate(
    project_root: Path,
    values: dict[str, np.ndarray],
    layout: QLinearConvPhysicalLayout,
    bundle: Any,
) -> dict[str, Any]:
    coordinate = (0, 0, 0, 0)
    adapter = NdpRtl28FunctionalAdapter(
        project_root / "NDPFuncModel",
        timeout_seconds=60,
    )
    result = adapter.run_qlinear_conv_coordinates(layout, bundle, (coordinate,))
    expected_p = int(values["P"][coordinate])
    expected_d = int(values["D"][coordinate])
    observed_p = result.accumulators[0]
    observed_d = result.outputs[0]
    inverse_d = int(layout.inverse_port(result.updated_bundle, "D")[coordinate])
    if observed_p != expected_p or observed_d != expected_d or inverse_d != expected_d:
        raise W5ConvPreflightError("NDPFuncModel first real 1x1 coordinate differs")
    plan = result.probe_plans[0]
    probe = result.physical_probe.int8_dot_probes[0]
    if (
        plan.source_owners != (0, 1, 3, 2)
        or plan.destination_owner != 0
        or len(probe.get("partial_accumulators", [])) != 4
        or probe.get("execution_path")
        != [
            "DRAM",
            "input_buffer",
            "SpecialPEA",
            "ActivationUnit",
            "output_buffer",
            "DRAM",
        ]
    ):
        raise W5ConvPreflightError("NDPFuncModel first-coordinate execution path differs")
    return {
        "status": "passed",
        "scope": "one_real_hwop-0004-00_output_coordinate",
        "coordinate": list(coordinate),
        "logical_shape": list(bundle.plan.output_shape),
        "kernel_shape": list(bundle.plan.weight_shape[2:]),
        "pads": list(bundle.plan.pads),
        "strides": list(bundle.plan.strides),
        "dilations": list(bundle.plan.dilations),
        "simulator": "NDPFuncModel conv_func",
        "simulator_status": adapter.status,
        "source_commit": "35eab40e5314bf603481dd6268bc96ab2ca514a6",
        "destination_slice": plan.destination_owner,
        "source_owners": list(plan.source_owners),
        "channel_ranges": [list(value) for value in plan.channel_ranges],
        "ring_segment_ends": list(plan.probe.ring_segment_ends),
        "partial_accumulators": list(probe["partial_accumulators"]),
        "accumulator": {
            "observed": observed_p,
            "golden": expected_p,
            "mismatch_count": 0,
        },
        "output": {
            "observed": observed_d,
            "golden": expected_d,
            "inverse_physical_d": inverse_d,
            "mismatch_count": 0,
        },
        "execution_path": probe["execution_path"],
        "config_link_status": "not_run_target_json_adapter_missing",
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
    operator_candidate = _operator_conv_candidate_probe(root)
    tile = _compare_tile(values, layout, bundle)
    ndp_coordinate = _compare_ndp_first_coordinate(root, values, layout, bundle)

    plan = bundle.plan
    report = {
        "schema_version": SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "status": "g5_candidate_encoded_real_1x1_config_adapter_blocked",
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
            "operator_conv_candidate_evidence_path": operator_candidate[
                "evidence_path"
            ],
            "operator_conv_candidate_evidence_sha256": operator_candidate[
                "evidence_sha256"
            ],
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
        "ndp_conv_simulator_first_coordinate": ndp_coordinate,
        "deepseek_target_simulator_entry": simulator_probe,
        "target_configuration": {
            "official_json_inventory_count": authority["inventory"]["json_count"],
            "official_named_conv_template_count": authority["inventory"][
                "named_conv_template_count"
            ],
            "candidate_named_conv_template_count": 1,
            "operator_candidate": operator_candidate,
            "candidate_json_encoded": True,
            "candidate_bitstream_generated": True,
            "candidate_mapping_review_generated": True,
            "real_1x1_patched_json_generated": False,
            "real_1x1_bitstream_generated": False,
            "unknown_fields_rejected": True,
            "legacy_generator_probe": legacy_generator_probe,
            "unresolved_target_bindings": [
                {
                    "blocker": "B_CONV_CANDIDATE_SHAPE_LOWERING",
                    "fields": ["dram_loop_configs", "lc_pe_configs", "stream_engine"],
                    "reason": "encoded candidate declares 3x3 B1 while hwop-0004-00 is 1x1 B16, and pseudocode/JSON loop and PE formulas conflict",
                },
                {
                    "blocker": "B_CONV_SIMULATOR_CONFIG_ADAPTER",
                    "fields": ["conv_full.json", "physical_image_request"],
                    "reason": "NDPFuncModel executes real Conv physical coordinates but does not consume ndp-sim target JSON or bitstream",
                },
                {
                    "blocker": "B_CONV_SA_PSUM_BINDING",
                    "fields": ["buffer_config", "stream_engine", "special_array"],
                    "reason": "INT8 and bias bits encode and NDPFuncModel proves four-segment INT32 accumulation, but exact target-config ports, signedness and unique final flush are not bound to that execution",
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
            "conv_simulator_component_status": "first_real_coordinate_passed",
            "golden_tile_status": "passed",
            "stop_expansion": True,
            "whole_network_generation_allowed": False,
            "next_required_evidence": [
                "derive and encode a semantically consistent hwop-0004-00 1x1 JSON",
                "bind ndp-sim target JSON/bitstream fields to the NDPFuncModel request",
                "bind target bias/psum/requant/qparam transport and unique-flush semantics",
            ],
        },
    }
    validate_w5_first_conv_preflight(report)
    return report


def validate_w5_first_conv_preflight(value: dict[str, Any]) -> None:
    """Reject any report that overstates the currently available evidence."""

    if value.get("schema_version") != SCHEMA_VERSION or value.get("report_kind") != REPORT_KIND:
        raise W5ConvPreflightError("W5 Conv preflight identity differs")
    if value.get("status") != "g5_candidate_encoded_real_1x1_config_adapter_blocked":
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
        or target.get("candidate_named_conv_template_count") != 1
        or target.get("candidate_json_encoded") is not True
        or target.get("candidate_bitstream_generated") is not True
        or target.get("candidate_mapping_review_generated") is not True
        or target.get("real_1x1_patched_json_generated") is not False
        or target.get("real_1x1_bitstream_generated") is not False
        or target.get("unknown_fields_rejected") is not True
    ):
        raise W5ConvPreflightError("W5 Conv target configuration exceeded evidence")
    blocker_ids = {
        item.get("blocker") for item in target.get("unresolved_target_bindings", [])
    }
    required = {
        "B_CONV_CANDIDATE_SHAPE_LOWERING",
        "B_CONV_SIMULATOR_CONFIG_ADAPTER",
        "B_CONV_SA_PSUM_BINDING",
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
        != "not_run_missing_config_adapter"
        or comparisons.get("P", {}).get("mismatch_count") != 0
        or comparisons.get("D", {}).get("mismatch_count") != 0
        or len(tile.get("k_lifecycle", [])) != 4
    ):
        raise W5ConvPreflightError("W5 Conv golden tile evidence differs")
    simulator = value.get("deepseek_target_simulator_entry", {})
    if (
        simulator.get("status")
        != "operator_confirmed_conv_backend_adapter_pending"
        or not simulator.get("target_runner", {}).get("command")
        or simulator.get("target_runner", {}).get("config_adapter_available")
        is not False
        or simulator.get("packager", {}).get("executes_numerical_model") is not False
    ):
        raise W5ConvPreflightError("target simulator identity/adapter boundary differs")
    ndp_coordinate = value.get("ndp_conv_simulator_first_coordinate", {})
    if (
        ndp_coordinate.get("status") != "passed"
        or ndp_coordinate.get("coordinate") != [0, 0, 0, 0]
        or ndp_coordinate.get("accumulator", {}).get("mismatch_count") != 0
        or ndp_coordinate.get("output", {}).get("mismatch_count") != 0
        or ndp_coordinate.get("config_link_status")
        != "not_run_target_json_adapter_missing"
    ):
        raise W5ConvPreflightError("NDP Conv first-coordinate evidence differs")
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
