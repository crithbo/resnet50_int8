from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .r5_lowering_bundle import validate_r5_lowering_bundle
from .stage_operator_semantics_audit import (
    ga_int32_to_fp32_rtl_result,
    ga_int32_to_fp32_rtl_trace,
)
from .w5_conv_preflight import (
    _initializer,
    _initializer_values,
    _load_npy,
    _port,
    _record_by_hw_op,
)


SCHEMA = "resnet50-requant-stage-semantics-evidence-v1"
REQUEST_ID = "r5:hwop-0004-01"
HW_OP_ID = "hwop-0004-01"
GA_MAC_KEYS = ("PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32")
GA_SUB_KEYS = ("PE01", "PE03", "PE11", "PE13", "PE21", "PE23", "PE31", "PE33")
ROUND_MAGIC_BITS = 0x4B400000


class RequantStageSemanticsEvidenceError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RequantStageSemanticsEvidenceError(
            f"cannot parse JSON evidence: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RequantStageSemanticsEvidenceError(
            f"JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise RequantStageSemanticsEvidenceError(
            f"missing requant evidence: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _only(items: list[Any], *, label: str) -> Mapping[str, Any]:
    matches = [item for item in items if isinstance(item, Mapping)]
    if len(matches) != 1:
        raise RequantStageSemanticsEvidenceError(
            f"expected exactly one {label}"
        )
    return matches[0]


def _float32_bits(value: np.float32) -> str:
    return f"0x{struct.unpack('<I', struct.pack('<f', float(value)))[0]:08x}"


def _typed_parameter(
    request: Mapping[str, Any], name: str
) -> Mapping[str, Any]:
    values = [
        item
        for item in request.get("typed_parameters", [])
        if isinstance(item, Mapping) and item.get("name") == name
    ]
    return _only(values, label=f"{REQUEST_ID} parameter {name}")


def _validate_ga_template(template: Mapping[str, Any]) -> dict[str, Any]:
    ga = template.get("general_array")
    if not isinstance(ga, Mapping):
        raise RequantStageSemanticsEvidenceError(
            "quant template general_array is missing"
        )
    inport0 = ga.get("inport", {}).get("inport0")
    outport = ga.get("outport")
    if (
        not isinstance(inport0, Mapping)
        or inport0.get("int32tofp32") != "true"
        or not isinstance(outport, Mapping)
        or outport.get("int32touint8") != "true"
    ):
        raise RequantStageSemanticsEvidenceError(
            "quant template conversion topology differs"
        )
    pe_array = ga.get("PE_array")
    if not isinstance(pe_array, Mapping):
        raise RequantStageSemanticsEvidenceError(
            "quant template PE array is missing"
        )
    lanes = []
    for lane, (mac_key, sub_key) in enumerate(
        zip(GA_MAC_KEYS, GA_SUB_KEYS, strict=True)
    ):
        mac = pe_array.get(mac_key)
        sub = pe_array.get(sub_key)
        if (
            not isinstance(mac, Mapping)
            or mac.get("alu_opcode") != "mac"
            or mac.get("inport0", {}).get("src_id") != 0
            or mac.get("inport0", {}).get("mode") != "buffer"
            or not isinstance(sub, Mapping)
            or sub.get("alu_opcode") != "int32_sub"
            or sub.get("inport0", {}).get("src_id") != f"GA_PE.{mac_key}"
            or sub.get("inport0", {}).get("mode") != "buffer"
            or sub.get("inport1", {}).get("constant") != ROUND_MAGIC_BITS
        ):
            raise RequantStageSemanticsEvidenceError(
                f"quant template GA lane {lane} differs"
            )
        lanes.append(
            {
                "lane": lane,
                "multiply_add_pe": mac_key,
                "integer_subtract_pe": sub_key,
                "multiplier_field": f"general_array.PE_array.{mac_key}.inport1.constant",
                "round_magic_field": f"general_array.PE_array.{mac_key}.inport2.constant",
                "subtract_magic_field": f"general_array.PE_array.{sub_key}.inport1.constant",
            }
        )
    streams = template.get("stream_engine")
    if (
        not isinstance(streams, Mapping)
        or streams.get("stream0", {}).get("target") != "A"
        or streams.get("stream0", {}).get("mode") != "read"
        or streams.get("stream2", {}).get("target") != "D"
        or streams.get("stream2", {}).get("mode") != "write"
    ):
        raise RequantStageSemanticsEvidenceError(
            "quant template A/D stream topology differs"
        )
    return {
        "input_conversion": "int32_to_fp32",
        "output_conversion": "int32_to_uint8_saturating",
        "lane_count": len(lanes),
        "lanes": lanes,
        "input_stream": "stream0:A:read",
        "output_stream": "stream2:D:write",
    }


def build_requant_stage_semantics_evidence(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    lowering_rel = "contracts/resnet50_r5_lowering_bundle.json"
    typed_rel = "contracts/typed_config_parameter_contract.json"
    template_rel = "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
    model_rel = "artifacts/reference_model/resnet50-v1-12-int8.onnx"
    runtime_rel = "artifacts/w3/golden_batch16/manifest.json"
    subop_rel = "artifacts/w3/subop_batch16/manifest.json"
    hardware_rel = "contracts/operator_config/ndpsim_json_hardware_evidence_v1.json"
    conv_schedule_rel = (
        "contracts/operator_config/node0004_conv_schedule_evidence_v1.json"
    )

    lowering = _load(root / lowering_rel)
    validate_r5_lowering_bundle(lowering, root)
    requests = [
        item
        for item in lowering.get("requests", [])
        if isinstance(item, Mapping) and item.get("request_id") == REQUEST_ID
    ]
    request = _only(requests, label=REQUEST_ID)
    resolutions = [
        item
        for item in lowering.get("effective_resolutions", [])
        if isinstance(item, Mapping) and item.get("request_id") == REQUEST_ID
    ]
    resolution = _only(resolutions, label=f"{REQUEST_ID} effective resolution")
    if (
        request.get("identity", {}).get("hw_op_type") != "RequantizeUint8"
        or request.get("identity", {}).get("node_id") != "node-0004"
        or request.get("predecessor_hw_op_ids") != ["hwop-0004-00"]
    ):
        raise RequantStageSemanticsEvidenceError(
            "node-0004 requant request identity differs"
        )

    template = _load(root / template_rel)
    ga_topology = _validate_ga_template(template)
    typed = _load(root / typed_rel)
    typed_record = _record_by_hw_op(typed, HW_OP_ID)
    runtime_manifest = _load(root / runtime_rel)
    subop_manifest = _load(root / subop_rel)
    initializers = _initializer_values(root / model_rel)
    values = {
        name: _initializer(
            initializers,
            runtime_manifest,
            _port(typed_record, "inputs", name),
        )
        for name in ("x_scale", "w_scale", "y_scale", "y_zero_point")
    }
    multiplier = np.asarray(
        np.float32(values["x_scale"][0])
        * values["w_scale"].astype(np.float32)
        / np.float32(values["y_scale"][0]),
        dtype=np.float32,
    )
    multiplier_sha256 = sha256_bytes(
        np.ascontiguousarray(multiplier).tobytes()
    )
    multiplier_parameter = _typed_parameter(request, "requant_multiplier")
    if (
        multiplier.shape != (64,)
        or multiplier_parameter.get("formula")
        != "float32(x_scale * w_scale / y_scale)"
        or multiplier_parameter.get("value", {}).get("value_sha256")
        != multiplier_sha256
    ):
        raise RequantStageSemanticsEvidenceError(
            "requant multiplier identity differs"
        )
    output_zero_point = int(values["y_zero_point"][0])
    if (
        values["y_zero_point"].shape != (1,)
        or output_zero_point != 0
        or _typed_parameter(request, "y_zero_point").get("value", {}).get(
            "scalar"
        )
        != output_zero_point
    ):
        raise RequantStageSemanticsEvidenceError(
            "requant output zero point differs"
        )

    accumulator_desc = typed_record["ports"]["inputs"][0]
    output_desc = typed_record["ports"]["outputs"][0]
    accumulator = _load_npy(
        root / "artifacts/w3/subop_batch16",
        subop_manifest,
        subop_manifest["internal_tensors"][accumulator_desc["tensor_id"]],
    )
    golden = _load_npy(
        root / "artifacts/w3/golden_batch16",
        runtime_manifest,
        runtime_manifest["tensors"][output_desc["tensor_id"]],
    )
    if (
        accumulator.shape != (16, 64, 56, 56)
        or accumulator.dtype != np.dtype("int32")
        or golden.shape != accumulator.shape
        or golden.dtype != np.dtype("uint8")
    ):
        raise RequantStageSemanticsEvidenceError(
            "requant W3 tensor signature differs"
        )
    scaled = accumulator.astype(np.float32) * multiplier.reshape(1, 64, 1, 1)
    round_magic = np.float32(12_582_912.0 + output_zero_point)
    rounded = (
        (scaled + round_magic).view(np.int32).astype(np.int64)
        - ROUND_MAGIC_BITS
    )
    actual = np.clip(rounded, 0, 255).astype(np.uint8)
    mismatch_count = int(np.count_nonzero(actual != golden))
    if mismatch_count != 0:
        raise RequantStageSemanticsEvidenceError(
            f"requant W3 replay differs: {mismatch_count} mismatches"
        )

    unique_accumulator, inverse, occurrence_counts = np.unique(
        accumulator, return_inverse=True, return_counts=True
    )
    rtl_unique_bits = np.asarray(
        [
            ga_int32_to_fp32_rtl_result(int(value))
            for value in unique_accumulator
        ],
        dtype=np.uint32,
    )
    ieee_unique_bits = unique_accumulator.astype(np.float32).view(np.uint32)
    unique_conversion_mismatch = rtl_unique_bits != ieee_unique_bits
    conversion_mismatch_unique_count = int(
        np.count_nonzero(unique_conversion_mismatch)
    )
    conversion_mismatch_element_count = int(
        occurrence_counts[unique_conversion_mismatch].sum()
    )
    rtl_fp32 = rtl_unique_bits.view(np.float32)[inverse].reshape(
        accumulator.shape
    )
    rtl_scaled = np.multiply(
        rtl_fp32,
        multiplier.reshape(1, 64, 1, 1),
        dtype=np.float32,
    )
    rtl_added_magic = np.add(
        rtl_scaled,
        round_magic,
        dtype=np.float32,
    )
    rtl_rounded = (
        rtl_added_magic.view(np.int32).astype(np.int64)
        - ROUND_MAGIC_BITS
    )
    rtl_output = np.clip(rtl_rounded, 0, 255).astype(np.uint8)
    rtl_output_mismatch_count = int(
        np.count_nonzero(rtl_output != golden)
    )
    mismatch_values = unique_accumulator[
        unique_conversion_mismatch
    ].tolist()
    if (
        accumulator.size != 3_211_264
        or int(accumulator.min()) != -1_148_879
        or int(accumulator.max()) != 57_876
        or int(np.count_nonzero(accumulator == -1)) != 128
        or int(np.count_nonzero(accumulator == np.iinfo(np.int32).min)) != 0
        or len(unique_accumulator) != 49_010
        or conversion_mismatch_unique_count != 1
        or conversion_mismatch_element_count != 128
        or mismatch_values != [-1]
        or rtl_output_mismatch_count != 0
    ):
        raise RequantStageSemanticsEvidenceError(
            "exact W3 RTL conversion/requant replay signature differs"
        )

    hardware = _load(root / hardware_rel)
    hardware_records = [
        item
        for item in hardware.get("records", [])
        if isinstance(item, Mapping) and item.get("path") == template_rel
    ]
    hardware_record = _only(
        hardware_records, label="quant template hardware audit"
    )
    exact = hardware_record.get("exact_config_evidence")
    reference_correctness = hardware_record.get(
        "reference_configuration_correctness"
    )
    if (
        not isinstance(exact, Mapping)
        or exact.get("evidence_level") != "unproven-per-template"
        or hardware_record.get("positive_hardware_test_proven") is not False
        or hardware_record.get("numeric_hardware_test_proven") is not False
        or not isinstance(reference_correctness, Mapping)
        or reference_correctness.get("accepted_as_correct_reference") is not True
    ):
        raise RequantStageSemanticsEvidenceError(
            "quant template hardware evidence boundary differs"
        )

    channel_groups = [
        {
            "shard_index": shard,
            "channels": list(range(shard * 8, shard * 8 + 8)),
            "ga_lane_count": 8,
            "multiplier_float32": [
                float(value) for value in multiplier[shard * 8 : shard * 8 + 8]
            ],
            "multiplier_float32_bits": [
                _float32_bits(value)
                for value in multiplier[shard * 8 : shard * 8 + 8]
            ],
        }
        for shard in range(8)
    ]
    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "authorized_correct_template_formula_and_ga_placement_closed_"
            "derived_instance_blocked"
        ),
        "request": {
            "request_id": REQUEST_ID,
            "request_sha256": request["request_sha256"],
            "identity": request["identity"],
            "predecessor_hw_op_ids": request["predecessor_hw_op_ids"],
            "logical_geometry": request["logical_geometry"],
        },
        "evidence": {
            "lowering_bundle": _binding(root, lowering_rel),
            "typed_parameter_contract": _binding(root, typed_rel),
            "active_ndpsim_template": _binding(root, template_rel),
            "reference_model": _binding(root, model_rel),
            "runtime_golden": _binding(root, runtime_rel),
            "subop_golden": _binding(root, subop_rel),
            "conv_predecessor_schedule": _binding(root, conv_schedule_rel),
            "hardware_evidence_audit": _binding(root, hardware_rel),
        },
        "operator_formula": {
            "multiplier": "float32(x_scale * w_scale / y_scale)",
            "multiplier_dtype": "float32",
            "multiplier_axis": 0,
            "multiplier_count": 64,
            "multiplier_sha256": multiplier_sha256,
            "output_zero_point": output_zero_point,
            "rounding_replay": (
                "reinterpret_int32(float32(accumulator * multiplier + "
                "12582912.0 + output_zero_point)) - 0x4b400000"
            ),
            "saturation": "clip integer result to [0,255] then cast uint8",
            "round_magic_float32": float(round_magic),
            "round_magic_float32_bits": _float32_bits(round_magic),
            "subtract_magic_int32": ROUND_MAGIC_BITS,
        },
        "ga_template_topology": ga_topology,
        "parameter_placement": {
            "policy": "eight channels per GA invocation",
            "shard_count": len(channel_groups),
            "channel_coverage": list(range(64)),
            "channel_groups": channel_groups,
        },
        "independent_local_numeric_replay": {
            "source": "W3 INT32 subop accumulator and independent uint8 runtime golden",
            "element_count": int(actual.size),
            "mismatch_count": mismatch_count,
            "actual_sha256": sha256_bytes(np.ascontiguousarray(actual).tobytes()),
            "golden_sha256": sha256_bytes(np.ascontiguousarray(golden).tobytes()),
            "scope": "this exact node-0004 tensor only; not an all-input proof",
        },
        "bit_accurate_rtl_replay": {
            "accumulator_domain": {
                "element_count": int(accumulator.size),
                "minimum": int(accumulator.min()),
                "maximum": int(accumulator.max()),
                "negative_count": int(np.count_nonzero(accumulator < 0)),
                "zero_count": int(np.count_nonzero(accumulator == 0)),
                "minus_one_count": int(np.count_nonzero(accumulator == -1)),
                "int_min_count": int(
                    np.count_nonzero(
                        accumulator == np.iinfo(np.int32).min
                    )
                ),
                "unique_value_count": len(unique_accumulator),
            },
            "int32_to_fp32": {
                "model": "ga_int32_to_fp32_rtl_trace",
                "rtl_bits_sha256": sha256_bytes(
                    np.ascontiguousarray(
                        rtl_unique_bits[inverse].reshape(accumulator.shape)
                    ).tobytes()
                ),
                "unique_conversion_mismatch_count": (
                    conversion_mismatch_unique_count
                ),
                "element_conversion_mismatch_count": (
                    conversion_mismatch_element_count
                ),
                "mismatch_values": mismatch_values,
                "minus_one_trace": ga_int32_to_fp32_rtl_trace(-1),
                "minus_one_ieee_bits": "0xbf800000",
                "minus_one_rtl_bits": "0xcf000000",
                "classification": "CONTRADICTED",
            },
            "post_conversion_pipeline": {
                "steps": [
                    "float32 multiply by per-channel multiplier",
                    "float32 add round magic",
                    "reinterpret result bits as int32",
                    "subtract 0x4b400000",
                    "clip to uint8 [0,255]",
                ],
                "forced_float32_multiply_and_add": True,
                "final_uint8_mismatch_count": rtl_output_mismatch_count,
                "final_uint8_sha256": sha256_bytes(
                    np.ascontiguousarray(rtl_output).tobytes()
                ),
                "golden_uint8_sha256": sha256_bytes(
                    np.ascontiguousarray(golden).tobytes()
                ),
                "observed_masking": (
                    "all 128 conversion counterexamples are accumulator=-1; "
                    "both IEEE -1.0 and RTL -2147483648.0 remain negative after "
                    "positive scaling and therefore saturate to uint8 zero"
                ),
            },
            "verdict": {
                "exact_input_hits_known_rtl_counterexample": True,
                "intermediate_conversion_equivalent": False,
                "final_uint8_output_equivalent_for_exact_w3_tensor": True,
                "rtl_semantics_compatible": False,
                "reason": (
                    "the approved P3 gate treats any exact-input hit of the "
                    "known INT32-to-FP32 counterexample as incompatible; final "
                    "saturation masking is recorded but does not generalize"
                ),
            },
        },
        "emission_gate": {
            "candidate_config_emission_allowed": False,
            "reference_template_configuration_correctness_authorized": True,
            "reference_configuration_evidence_class": reference_correctness[
                "evidence_class"
            ],
            "authority_resolves_reference_template_semantics": [
                "B_REQUANT_TARGET_NUMERICS"
            ],
            "lowering_overlay_update_pending": True,
            "effective_unresolved_blockers": list(
                resolution.get("unresolved_blockers", [])
            ),
            "additional_backend_blockers": [
                "B_REQUANT_PREDECESSOR_FULL_SCHEDULE",
                "B_REQUANT_DERIVED_INSTANCE_VALIDATION",
                "B_GA_INT32TOFP32_INPUT_DOMAIN",
            ],
            "template_hardware_evidence_level": exact["evidence_level"],
            "positive_hardware_test_proven": False,
            "numeric_hardware_test_proven": False,
            "legacy_ndp_sim_ref_outputs_used": False,
            "claim_boundary": (
                "The active quant template is accepted as a correct reference "
                "configuration. Formula, channel placement and exact W3 replay "
                "are closed for node-0004. Bit-accurate conversion replay hits "
                "128 instances of accumulator=-1 and therefore retains the "
                "RTL input-domain blocker even though uint8 saturation masks "
                "the difference in this exact final tensor."
            ),
        },
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def validate_requant_stage_semantics_evidence(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_requant_stage_semantics_evidence(project_root):
        raise RequantStageSemanticsEvidenceError(
            "requant stage semantics evidence differs from current inputs"
        )


def write_requant_stage_semantics_evidence(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "RequantStageSemanticsEvidenceError",
    "SCHEMA",
    "build_requant_stage_semantics_evidence",
    "validate_requant_stage_semantics_evidence",
    "write_requant_stage_semantics_evidence",
]
