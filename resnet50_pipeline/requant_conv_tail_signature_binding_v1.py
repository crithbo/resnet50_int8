from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_REL = Path(
    "contracts/operator_config/requant_conv53_tail_signature_binding_v1.json"
)
ARTIFACT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-conv53-tail-signature-binding-v1"
)

SOURCE_SHA256 = {
    ".agents/rules/生成前必读索引.md":
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    ".agents/rules/算子配置规则.md":
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ".agents/rules/精确UINT8量化尾专项规则.md":
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ".agents/rules/RequantizeUint8算子配置规则.md":
        "5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555",
    "contracts/resnet50_r5_lowering_bundle.json":
        "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432",
    "contracts/operator_config/requant_conv53_exact_tail_binding_v1.json":
        "075df2abdab13f7c94679b411a9822213f3975bc7341c7415a2c3577d5cdf113",
    ".agents/task_records/20260729_node0004_assumed_hardware_package_ready.md":
        "5495d06377b6feb6527de110c11e0f5194a3bf5e47d97e713435fb19a12ed77f",
    "artifacts/operator_config_validation/r5-node0004-assumed-hardware-v1/"
    "tail_graph.json":
        "e51eb6ab66088a5474b1067e94f921db57043407f5d992e4b2a5bda24de0bd6a",
    "artifacts/operator_config_validation/r5-node0004-assumed-hardware-v1/"
    "local_numeric_report.json":
        "cf653e51d388c5194aea8ee66db9594dcbb90dd35a1f1a75244757a1d28fbc42",
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1/package_manifest.json":
        "1cfd9175e913c0eb13bf747b6781c4bacc477407810f56d68674fe503ab78866",
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1.validation.json":
        "d7085699109f0b00740d93e73ee19ad7ea847f8cb1f895bf97eb9cdc2e230207",
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1.zip.sha256":
        "72b00e6d13d0dde099594ae410197d1ea6f2a1dd281696e3d46d4cb32ce32451",
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1.zip":
        "335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989",
}

LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
PRIOR_BINDING_REL = Path(
    "contracts/operator_config/requant_conv53_exact_tail_binding_v1.json"
)
TAIL_GRAPH_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-node0004-assumed-hardware-v1/tail_graph.json"
)
NUMERIC_REPORT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-node0004-assumed-hardware-v1/local_numeric_report.json"
)
PACKAGE_VALIDATION_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1.validation.json"
)
PACKAGE_ZIP_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_node0004_hw_v1.zip"
)

NODE0004_REQUEST_ID = "r5:hwop-0004-01"
NODE0004_SHAPE = [16, 64, 56, 56]
NODE0004_MULTIPLIER_SHA256 = (
    "e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2"
)
DISPATCH_PLAN_SHA256 = (
    "f9a3ce73baa73346c144f14bf005262f0b0caaf66d981da157a5a11c0a703183"
)


def load_json(relative: Path | str) -> dict[str, Any]:
    value = json.loads((ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object JSON required: {relative}")
    return value


def file_sha256(relative: Path | str) -> str:
    digest = hashlib.sha256()
    with (ROOT / relative).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_receipt(relative: Path | str, role: str) -> dict[str, Any]:
    path = ROOT / relative
    return {
        "path": Path(relative).as_posix(),
        "role": role,
        "size_bytes": path.stat().st_size,
        "sha256": file_sha256(relative),
    }


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def semantic_sha256(value: dict[str, Any], field: str) -> str:
    copy = deepcopy(value)
    copy.pop(field, None)
    return hashlib.sha256(canonical_bytes(copy)).hexdigest()


def write_json(relative: Path | str, value: dict[str, Any]) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def assert_source_identities() -> None:
    for relative, expected in SOURCE_SHA256.items():
        actual = file_sha256(relative)
        if actual != expected:
            raise ValueError(
                f"source identity drifted: {relative}: {actual} != {expected}"
            )


def parameter_map(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in request["typed_parameters"]}


def compact_request(request: dict[str, Any]) -> dict[str, Any]:
    identity = request["identity"]
    return {
        "request_id": request["request_id"],
        "request_sha256": request["request_sha256"],
        "ordinal": request["ordinal"],
        "hw_op_id": identity["hw_op_id"],
        "node_id": identity["node_id"],
        "onnx_name": identity["onnx_name"],
        "onnx_op_type": identity["onnx_op_type"],
        "hw_op_type": identity["hw_op_type"],
        "stage": identity["stage"],
    }


def schedule_profile_id(shape: list[int]) -> str:
    n, c, h, w = shape
    return f"TAIL_N{n}_C{c}_H{h}_W{w}_HWC8"


def rounding_profile_id(zero_point: int) -> str:
    if zero_point == 0:
        return "RS_ZP0_NODE0004_EXACT_TWO_STAGE"
    if zero_point % 2 == 0:
        return "RS_EVEN_NONZERO_ZP_AFTER_RNE"
    return "RS_ODD_NONZERO_ZP_AFTER_RNE_TIE_PARITY"


def reuse_decision(
    request_id: str,
    shape: list[int],
    zero_point: int,
) -> dict[str, Any]:
    if request_id == NODE0004_REQUEST_ID:
        return {
            "reuse_class": "FROZEN_NODE0004_ANCHOR_NO_REBUILD",
            "node0004_exact_two_stage_recipe_reusable": True,
            "node0004_physical_schedule_shape_reusable": True,
            "independent_materialization_required": False,
            "reason": (
                "fresh complete-node local config-bound anchor already exists; "
                "its package identity is immutable"
            ),
        }
    if zero_point == 0 and shape == NODE0004_SHAPE:
        return {
            "reuse_class": (
                "REUSE_NODE0004_EXACT_RECIPE_AND_SCHEDULE_SHAPE_TEMPLATE"
            ),
            "node0004_exact_two_stage_recipe_reusable": True,
            "node0004_physical_schedule_shape_reusable": True,
            "independent_materialization_required": True,
            "reason": (
                "same logical shape and zp0 arithmetic; multiplier bits, tensor "
                "identity, addresses, lifetime and final materialized JSON remain "
                "instance-specific"
            ),
        }
    if zero_point == 0:
        return {
            "reuse_class": (
                "REUSE_NODE0004_EXACT_TWO_STAGE_ARITHMETIC_RECIPE_ONLY"
            ),
            "node0004_exact_two_stage_recipe_reusable": True,
            "node0004_physical_schedule_shape_reusable": False,
            "independent_materialization_required": True,
            "reason": (
                "zp0 arithmetic order matches node0004, but shape/channel/spatial "
                "schedule, multiplier payload, addresses and lifetime differ"
            ),
        }
    if zero_point % 2 == 0:
        return {
            "reuse_class": (
                "NODE0004_STAGE0_SCRATCH_SATURATION_PRIMITIVES_ONLY__"
                "EVEN_NONZERO_ZP_INDEPENDENT"
            ),
            "node0004_exact_two_stage_recipe_reusable": False,
            "node0004_physical_schedule_shape_reusable": False,
            "independent_materialization_required": True,
            "reason": (
                "node0004 stage1 is zp0-only; target must add nonzero zero-point "
                "after RNE and freshly materialize constants, topology and lifetime"
            ),
        }
    return {
        "reuse_class": (
            "NODE0004_STAGE0_SCRATCH_SATURATION_PRIMITIVES_ONLY__"
            "ODD_NONZERO_ZP_TIE_PARITY_INDEPENDENT"
        ),
        "node0004_exact_two_stage_recipe_reusable": False,
        "node0004_physical_schedule_shape_reusable": False,
        "independent_materialization_required": True,
        "reason": (
            "node0004 stage1 is zp0-only; odd zero-point additionally retains "
            "post-RNE tie-parity proof and fresh physical materialization"
        ),
    }


def node0004_schedule_anchor(
    tail_graph: dict[str, Any],
) -> dict[str, Any]:
    operators = tail_graph["operators"]
    mul = [item for item in operators if item["id"].startswith("op_mul_")]
    round_ops = [
        item for item in operators if item["id"].startswith("op_round_")
    ]
    if len(mul) != 24 or len(round_ops) != 24:
        raise ValueError("node0004 tail graph must contain 24 two-stage pairs")
    pattern = re.compile(r"^op_mul_w(\d+)_s(\d+)$")
    wave_shards: dict[int, set[int]] = defaultdict(set)
    wave_masks: dict[int, list[str]] = defaultdict(list)
    for item in mul:
        match = pattern.match(item["id"])
        if not match:
            raise ValueError(f"unexpected node0004 mul id: {item['id']}")
        wave = int(match.group(1))
        shard = int(match.group(2))
        wave_shards[wave].add(shard)
        wave_masks[wave].append(item["used_slices"])
        if item["inputs"]["A"]["shape"] != [1, 3136, 8]:
            raise ValueError("node0004 occurrence shape differs")
        if item["inputs"]["A"]["dtype"] != "int32":
            raise ValueError("node0004 stage0 ingress dtype differs")
        if item["output"]["dtype"] != "fp32":
            raise ValueError("node0004 stage0 output dtype differs")
    for item in round_ops:
        if item["inputs"]["A"]["shape"] != [1, 3136, 8]:
            raise ValueError("node0004 stage1 occurrence shape differs")
        if item["inputs"]["A"]["dtype"] != "fp32":
            raise ValueError("node0004 stage1 ingress dtype differs")
        if item["output"]["dtype"] != "uint8":
            raise ValueError("node0004 stage1 output dtype differs")
    if sorted(wave_shards) != [0, 1, 2]:
        raise ValueError("node0004 must use three sample waves")
    if any(shards != set(range(8)) for shards in wave_shards.values()):
        raise ValueError("node0004 must use eight channel shards per wave")
    sample_counts = []
    for wave in (0, 1, 2):
        unique_masks = sorted(set(wave_masks[wave]))
        popcounts = {
            mask[2:].count("1")
            for mask in unique_masks
        }
        if len(popcounts) != 1:
            raise ValueError("node0004 wave mask popcount differs")
        sample_counts.append(next(iter(popcounts)))
    if sample_counts != [7, 7, 2]:
        raise ValueError(f"node0004 wave sample counts differ: {sample_counts}")
    return {
        "logical_shape": NODE0004_SHAPE,
        "physical_layout": "HWC8",
        "occurrence_shape": [1, 3136, 8],
        "lane_count": 8,
        "channel_shards": 8,
        "sample_waves": 3,
        "samples_per_wave": sample_counts,
        "two_stage_pair_count": 24,
        "stage_count": 48,
        "stage_order": [
            "signed_int32_to_fp32_then_explicit_fp32_mul",
            "fp32_scratch_completion_barrier",
            "raw_fp32_magic_rne_then_int32_sub_then_uint8_saturation",
        ],
        "stage0_input_bytes_per_occurrence": 3136 * 8 * 4,
        "scratch_bytes_per_occurrence": 3136 * 8 * 4,
        "stage1_output_bytes_per_occurrence": 3136 * 8,
        "slice_mask_policy": (
            "fresh node0004 exact masks; same-shape reuse is topology-only and "
            "must receive fresh address/lifetime binding"
        ),
    }


def build_manifest() -> dict[str, Any]:
    assert_source_identities()
    lowering = load_json(LOWERING_REL)
    prior = load_json(PRIOR_BINDING_REL)
    tail_graph = load_json(TAIL_GRAPH_REL)
    numeric_report = load_json(NUMERIC_REPORT_REL)
    package_validation = load_json(PACKAGE_VALIDATION_REL)

    requests = {
        item["request_id"]: item
        for item in lowering["requests"]
        if item["identity"]["onnx_op_type"] == "QLinearConv"
        and item["identity"]["hw_op_type"] == "RequantizeUint8"
    }
    if len(requests) != 53:
        raise ValueError("typed lowering must contain exactly 53 Conv tails")
    prior_rows = {
        item["typed_request"]["request_id"]: item
        for item in prior["conv53_stage_bindings"]
    }
    if set(prior_rows) != set(requests):
        raise ValueError("prior Conv53 binding request set differs")

    anchor_schedule = node0004_schedule_anchor(tail_graph)
    if (
        numeric_report["tail_mismatch_count"] != 0
        or numeric_report["typed_identity"]["output_zero_point"] != 0
        or numeric_report["typed_identity"]["multiplier_sha256"]
        != NODE0004_MULTIPLIER_SHA256
        or package_validation["status"] != "PACKAGE_READY_NOT_RUN"
        or package_validation["zip_sha256"]
        != SOURCE_SHA256[PACKAGE_ZIP_REL.as_posix()]
    ):
        raise ValueError("node0004 fresh anchor receipt differs")

    stage_bindings: list[dict[str, Any]] = []
    profile_members: dict[str, list[str]] = defaultdict(list)
    for request in sorted(requests.values(), key=lambda item: item["ordinal"]):
        request_id = request["request_id"]
        params = parameter_map(request)
        shape = request["logical_geometry"]["output_shapes"][0]
        if len(shape) != 4 or shape[0] != 16:
            raise ValueError(f"unexpected Conv tail shape: {request_id}: {shape}")
        n, channels, height, width = shape
        if channels % 8:
            raise ValueError(f"non-HWC8-aligned channels: {request_id}")
        zero_point = params["y_zero_point"]["value"]["scalar"]
        multiplier = params["requant_multiplier"]["value"]
        if (
            multiplier["dtype"] != "float32"
            or multiplier["shape"] != [channels]
            or multiplier["element_count"] != channels
            or multiplier.get("axis") != 0
        ):
            raise ValueError(f"multiplier descriptor differs: {request_id}")
        schedule_id = schedule_profile_id(shape)
        rounding_id = rounding_profile_id(zero_point)
        profile_members[schedule_id].append(request_id)
        prior_row = prior_rows[request_id]
        if request_id == NODE0004_REQUEST_ID:
            evidence = {
                "source": (
                    ".agents/task_records/"
                    "20260729_node0004_assumed_hardware_package_ready.md"
                ),
                "classification": (
                    "FRESH_LOCAL_CONFIG_BOUND_E2_PACKAGE_READY_NOT_RUN"
                ),
                "w3_classification_rerun": False,
                "reused_prior_54_stage_row": False,
            }
            transaction_forecast = {
                "source": "fresh node0004 tail_graph.json",
                "forecast_only": False,
                "channel_shards": 8,
                "two_stage_pairs": 24,
                "stage_count": 48,
            }
        else:
            old = prior_row["existing_evidence_binding"]
            transaction = old["transaction"]
            expected_pairs = 3 * (channels // 8)
            if (
                transaction["channel_tail_mod8"] != 0
                or transaction["shard_count"] != channels // 8
                or transaction[
                    "three_wave_occurrence_forecast_not_emission_authority"
                ]
                != expected_pairs
                or transaction[
                    "two_stage_count_forecast_not_emission_authority"
                ]
                != 2 * expected_pairs
            ):
                raise ValueError(
                    f"existing transaction classification differs: {request_id}"
                )
            evidence = {
                "source": PRIOR_BINDING_REL.as_posix(),
                "classification": old["numeric_classification"],
                "physical_materialization_classification": old[
                    "physical_materialization_classification"
                ],
                "source_evidence_ordinal": old["source_evidence_ordinal"],
                "w3_exact_recipe_proven": old["w3_exact_recipe_proven"],
                "w3_classification_rerun": False,
                "reused_prior_54_stage_row": True,
            }
            transaction_forecast = {
                "source": "accepted other52 classification",
                "forecast_only": True,
                "not_emission_authority": True,
                "channel_shards": transaction["shard_count"],
                "two_stage_pairs": transaction[
                    "three_wave_occurrence_forecast_not_emission_authority"
                ],
                "stage_count": transaction[
                    "two_stage_count_forecast_not_emission_authority"
                ],
            }
        reuse = reuse_decision(request_id, shape, zero_point)
        signature_dimensions = {
            "logical_shape_nchw": shape,
            "y_zero_point_uint8": zero_point,
            "multiplier_fp32_bits_sha256": multiplier["value_sha256"],
            "rounding_saturation_profile_id": rounding_id,
            "physical_schedule_profile_id": schedule_id,
        }
        signature = hashlib.sha256(
            canonical_bytes(signature_dimensions)
        ).hexdigest()
        subtract_constant = 0x4B400000 - zero_point
        stage_bindings.append(
            {
                "signature_sha256": signature,
                "signature_dimensions": signature_dimensions,
                "typed_request": compact_request(request),
                "typed_qparams": {
                    "x_scale": deepcopy(params["x_scale"]),
                    "w_scale": deepcopy(params["w_scale"]),
                    "y_scale": deepcopy(params["y_scale"]),
                    "y_zero_point": deepcopy(params["y_zero_point"]),
                    "requant_multiplier": deepcopy(
                        params["requant_multiplier"]
                    ),
                },
                "multiplier_bits_binding": {
                    "dtype": "float32",
                    "axis": 0,
                    "element_count": channels,
                    "shape": [channels],
                    "bits_sha256": multiplier["value_sha256"],
                    "exact_payload_reused_from_node0004": (
                        request_id == NODE0004_REQUEST_ID
                    ),
                    "fresh_payload_binding_required": (
                        request_id != NODE0004_REQUEST_ID
                    ),
                },
                "rounding_saturation_binding": {
                    "profile_id": rounding_id,
                    "target_order": (
                        "explicit_fp32_multiply -> fp32_scratch/barrier -> "
                        "round_to_nearest_even -> integer_add_zero_point -> "
                        "saturate_uint8"
                    ),
                    "magic_bias_fp32_bits": "0x4b400000",
                    "post_magic_subtract_constant_uint32": (
                        f"0x{subtract_constant:08x}"
                    ),
                    "zero_point_added_after_rne": True,
                    "odd_zero_point_tie_parity_gate": zero_point % 2 == 1,
                },
                "physical_tail_schedule_dependencies": {
                    "profile_id": schedule_id,
                    "logical_shape_nchw": shape,
                    "physical_layout": "HWC8",
                    "lane_count": 8,
                    "channel_tail_mod8": channels % 8,
                    "spatial_elements_per_sample": height * width,
                    "occurrence_shape": [1, height * width, 8],
                    "sample_wave_capacity_from_node0004_anchor": 7,
                    "sample_waves_forecast": math.ceil(n / 7),
                    "channel_shards": channels // 8,
                    "two_stage_pairs_forecast": (
                        math.ceil(n / 7) * (channels // 8)
                    ),
                    "stage_count_forecast": (
                        2 * math.ceil(n / 7) * (channels // 8)
                    ),
                    "stage0_input_bytes_per_occurrence": (
                        height * width * 8 * 4
                    ),
                    "scratch_bytes_per_occurrence": (
                        height * width * 8 * 4
                    ),
                    "stage1_output_bytes_per_occurrence": (
                        height * width * 8
                    ),
                    "fresh_slice_mask_address_lifetime_binding_required": (
                        request_id != NODE0004_REQUEST_ID
                    ),
                    "existing_transaction_classification": (
                        transaction_forecast
                    ),
                },
                "existing_w3_classification": evidence,
                "node0004_reuse_decision": reuse,
            }
        )

    multiplier_hashes = [
        item["multiplier_bits_binding"]["bits_sha256"]
        for item in stage_bindings
    ]
    if len(set(multiplier_hashes)) != 53:
        raise ValueError("each Conv tail must have a unique multiplier payload")

    schedule_profiles: list[dict[str, Any]] = []
    rows_by_id = {
        item["typed_request"]["request_id"]: item
        for item in stage_bindings
    }
    for profile_id, member_ids in sorted(profile_members.items()):
        first = rows_by_id[member_ids[0]]
        deps = first["physical_tail_schedule_dependencies"]
        schedule_profiles.append(
            {
                "profile_id": profile_id,
                "logical_shape_nchw": deps["logical_shape_nchw"],
                "physical_layout": "HWC8",
                "member_count": len(member_ids),
                "member_request_ids": member_ids,
                "spatial_elements_per_sample": deps[
                    "spatial_elements_per_sample"
                ],
                "channel_shards": deps["channel_shards"],
                "sample_waves_forecast": deps["sample_waves_forecast"],
                "two_stage_pairs_forecast": deps[
                    "two_stage_pairs_forecast"
                ],
                "stage_count_forecast": deps["stage_count_forecast"],
                "node0004_materialized_anchor_profile": (
                    deps["logical_shape_nchw"] == NODE0004_SHAPE
                ),
                "claim_boundary": (
                    "node0004 profile has one materialized anchor; every other "
                    "member still requires fresh multiplier/address/lifetime "
                    "binding. Other profiles are dependency forecasts only."
                ),
            }
        )

    reuse_counts = Counter(
        item["node0004_reuse_decision"]["reuse_class"]
        for item in stage_bindings
    )
    rounding_counts = Counter(
        item["rounding_saturation_binding"]["profile_id"]
        for item in stage_bindings
    )
    old_class_counts = Counter(
        item["existing_w3_classification"]["classification"]
        for item in stage_bindings
        if item["typed_request"]["request_id"] != NODE0004_REQUEST_ID
    )
    shape_zp_groups: dict[str, list[str]] = defaultdict(list)
    for item in stage_bindings:
        dimensions = item["signature_dimensions"]
        shape = "x".join(str(v) for v in dimensions["logical_shape_nchw"])
        key = f"{shape}|zp={dimensions['y_zero_point_uint8']}"
        shape_zp_groups[key].append(item["typed_request"]["request_id"])

    value: dict[str, Any] = {
        "schema": "requant-conv53-tail-signature-binding-v1",
        "status": "LOCAL_CONTRACT_ONLY_SIGNATURE_BINDING_READY",
        "owner_family": "RequantizeUint8",
        "mainline_thread_id": "019fa2ca-72bc-7753-8d58-81e59bc76c88",
        "mode": {
            "dispatch_plan_sha256": DISPATCH_PLAN_SHA256,
            "plan_receipt_is_mutable_provenance": True,
            "numeric_analysis_repeated": False,
            "w3_classification_repeated": False,
            "reuse_assets_consumed": True,
            "node0004_recomputed": False,
            "node0004_repackaged": False,
            "server_package_generated": False,
            "server_inspected_uploaded_or_run": False,
        },
        "read_receipts": [
            file_receipt(path, "active_plan_or_rule")
            for path in (
                ".agents/plan.md",
                ".agents/rules/生成前必读索引.md",
                ".agents/rules/算子配置规则.md",
                ".agents/rules/精确UINT8量化尾专项规则.md",
                ".agents/rules/RequantizeUint8算子配置规则.md",
            )
        ],
        "source_receipts": [
            file_receipt(
                LOWERING_REL, "typed Conv tail request and qparam identity"
            ),
            file_receipt(
                PRIOR_BINDING_REL,
                "accepted other52 W3 classification only",
            ),
            file_receipt(
                TAIL_GRAPH_REL,
                "fresh node0004 materialized two-stage schedule anchor",
            ),
            file_receipt(
                NUMERIC_REPORT_REL,
                "fresh node0004 local config-bound numeric receipt",
            ),
            file_receipt(
                ".agents/task_records/"
                "20260729_node0004_assumed_hardware_package_ready.md",
                "fresh node0004 mainline evidence receipt",
            ),
            file_receipt(
                PACKAGE_VALIDATION_REL,
                "frozen node0004 package status receipt",
            ),
            file_receipt(
                PACKAGE_ZIP_REL,
                "frozen node0004 package identity; read-only anchor",
            ),
        ],
        "frozen_node0004_anchor": {
            "request_id": NODE0004_REQUEST_ID,
            "logical_shape_nchw": NODE0004_SHAPE,
            "y_zero_point": 0,
            "multiplier_fp32_bits_sha256": NODE0004_MULTIPLIER_SHA256,
            "tail_graph_sha256": SOURCE_SHA256[TAIL_GRAPH_REL.as_posix()],
            "local_numeric_report_sha256": SOURCE_SHA256[
                NUMERIC_REPORT_REL.as_posix()
            ],
            "package_zip": PACKAGE_ZIP_REL.as_posix(),
            "package_zip_sha256": SOURCE_SHA256[
                PACKAGE_ZIP_REL.as_posix()
            ],
            "package_status": "PACKAGE_READY_NOT_RUN",
            "schedule": anchor_schedule,
            "local_config_bound_tail_mismatch_count": 0,
            "magic_domain": deepcopy(numeric_report["magic_domain"]),
            "immutable_no_rebuild": True,
            "counts_as_e4": False,
            "counts_as_e5": False,
        },
        "signature_definition": {
            "dimensions": [
                "logical_shape_nchw",
                "y_zero_point_uint8",
                "multiplier_fp32_bits_sha256",
                "rounding_saturation_profile_id",
                "physical_schedule_profile_id",
            ],
            "signature_hash": (
                "sha256(canonical JSON of the five dimensions)"
            ),
            "multiplier_payload_identity": (
                "exact FP32 per-channel bit payload SHA; decimal min/max is "
                "not a replacement"
            ),
        },
        "rounding_saturation_profiles": {
            "RS_ZP0_NODE0004_EXACT_TWO_STAGE": {
                "stage0": (
                    "signed_int32_to_fp32 -> explicit_fp32_mul -> fp32_scratch"
                ),
                "barrier": "required_completion_barrier",
                "stage1": (
                    "raw_fp32 + magic(0x4b400000) -> bitcast_int32 -> "
                    "sub(0x4b400000) -> saturate_uint8"
                ),
                "node0004_exact_recipe_reuse_scope": (
                    "all other zp0 Conv tails, with fresh multiplier/domain/"
                    "address/lifetime materialization"
                ),
            },
            "RS_EVEN_NONZERO_ZP_AFTER_RNE": {
                "target_order": (
                    "sequential_fp32_mul -> RNE -> add even zp -> saturate"
                ),
                "node0004_exact_recipe_reusable": False,
                "reusable_primitives": [
                    "direct signed stage0",
                    "fp32 scratch/barrier",
                    "fixed magic RNE primitive",
                    "uint8 saturation",
                ],
                "independent_requirement": (
                    "post-RNE nonzero-zp constant/topology and full physical "
                    "materialization"
                ),
            },
            "RS_ODD_NONZERO_ZP_AFTER_RNE_TIE_PARITY": {
                "target_order": (
                    "sequential_fp32_mul -> RNE -> add odd zp -> saturate"
                ),
                "node0004_exact_recipe_reusable": False,
                "reusable_primitives": [
                    "direct signed stage0",
                    "fp32 scratch/barrier",
                    "fixed magic RNE primitive",
                    "uint8 saturation",
                ],
                "independent_requirement": (
                    "post-RNE odd-zp constant/topology, tie-parity proof and "
                    "full physical materialization"
                ),
            },
        },
        "physical_schedule_profiles": schedule_profiles,
        "stage_bindings": stage_bindings,
        "group_summary": {
            "stage_count": len(stage_bindings),
            "other52_reused_classification_count": 52,
            "unique_exact_signature_count": len(
                {item["signature_sha256"] for item in stage_bindings}
            ),
            "unique_multiplier_bits_payload_count": len(
                set(multiplier_hashes)
            ),
            "physical_schedule_profile_count": len(schedule_profiles),
            "shape_zero_point_group_count": len(shape_zp_groups),
            "shape_zero_point_groups": {
                key: {
                    "count": len(ids),
                    "request_ids": ids,
                }
                for key, ids in sorted(shape_zp_groups.items())
            },
            "rounding_saturation_profile_counts": dict(
                sorted(rounding_counts.items())
            ),
            "node0004_reuse_class_counts": dict(
                sorted(reuse_counts.items())
            ),
            "other52_existing_w3_classification_counts": dict(
                sorted(old_class_counts.items())
            ),
            "node0004_exact_recipe_reuse_eligible_other_stages": sum(
                1
                for item in stage_bindings
                if item["typed_request"]["request_id"]
                != NODE0004_REQUEST_ID
                and item["node0004_reuse_decision"][
                    "node0004_exact_two_stage_recipe_reusable"
                ]
            ),
            "node0004_schedule_shape_template_reuse_eligible_other_stages": sum(
                1
                for item in stage_bindings
                if item["typed_request"]["request_id"]
                != NODE0004_REQUEST_ID
                and item["node0004_reuse_decision"][
                    "node0004_physical_schedule_shape_reusable"
                ]
            ),
            "independent_materialization_required_other_stages": sum(
                1
                for item in stage_bindings
                if item["typed_request"]["request_id"]
                != NODE0004_REQUEST_ID
                and item["node0004_reuse_decision"][
                    "independent_materialization_required"
                ]
            ),
        },
        "blocker_delta": {
            "add": [],
            "close": [],
            "carry_forward": [
                "remaining 52 Conv tails require fresh instance materialization",
                "each non-node0004 multiplier payload requires fresh exact-bit binding",
                "each non-node0004 address/lifetime/slice-mask schedule remains unmaterialized",
                "20 nonzero-zp Conv tails require independent post-RNE zp materialization",
                "5 odd nonzero-zp Conv tails retain tie-parity validation",
                "final Trassic2.0_RTL commit identity remains unbound",
                "real server compile/run/readback and E4/E5 remain open",
            ],
            "reason": (
                "this task classifies integration signatures only; it does not "
                "materialize or dynamically execute any new Conv tail"
            ),
        },
        "rule_delta_proposal": [],
        "package_release": {
            "new_package": "NONE",
            "frozen_node0004_package_consumed_as_read_only_anchor": True,
            "frozen_zip_sha256": SOURCE_SHA256[
                PACKAGE_ZIP_REL.as_posix()
            ],
        },
        "claim_boundary": {
            "local_machine_contract_only": True,
            "new_operator_target_json_generated": False,
            "new_mapping_bitstream_execplan_sca_generated": False,
            "new_server_package_generated": False,
            "candidate_release": False,
            "counts_as_e2_for_other52": False,
            "counts_as_e4": False,
            "counts_as_e5": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    value["manifest_sha256"] = semantic_sha256(value, "manifest_sha256")
    return value


def validate_manifest(
    value: dict[str, Any],
    *,
    verify_sources: bool = True,
) -> dict[str, Any]:
    if verify_sources:
        assert_source_identities()
    rows = value["stage_bindings"]
    node_rows = [
        item
        for item in rows
        if item["typed_request"]["request_id"] == NODE0004_REQUEST_ID
    ]
    other = [
        item
        for item in rows
        if item["typed_request"]["request_id"] != NODE0004_REQUEST_ID
    ]
    reuse_counts = Counter(
        item["node0004_reuse_decision"]["reuse_class"]
        for item in rows
    )
    rounding_counts = Counter(
        item["rounding_saturation_binding"]["profile_id"]
        for item in rows
    )
    checks = {
        "schema": (
            value["schema"]
            == "requant-conv53-tail-signature-binding-v1"
        ),
        "local_contract_only": value["claim_boundary"][
            "local_machine_contract_only"
        ],
        "stage_count_53": len(rows) == 53,
        "unique_request_count_53": len(
            {item["typed_request"]["request_id"] for item in rows}
        )
        == 53,
        "unique_signature_count_53": len(
            {item["signature_sha256"] for item in rows}
        )
        == 53,
        "unique_multiplier_payload_count_53": len(
            {
                item["multiplier_bits_binding"]["bits_sha256"]
                for item in rows
            }
        )
        == 53,
        "node0004_anchor_single": len(node_rows) == 1,
        "other52_count": len(other) == 52,
        "other52_classification_reused": all(
            item["existing_w3_classification"][
                "reused_prior_54_stage_row"
            ]
            for item in other
        ),
        "numeric_analysis_not_repeated": (
            value["mode"]["numeric_analysis_repeated"] is False
            and value["mode"]["w3_classification_repeated"] is False
        ),
        "reuse_assets_consumed": value["mode"]["reuse_assets_consumed"],
        "physical_schedule_profiles_9": len(
            value["physical_schedule_profiles"]
        )
        == 9,
        "shape_zp_groups_24": value["group_summary"][
            "shape_zero_point_group_count"
        ]
        == 24,
        "rounding_counts_33_15_5": rounding_counts
        == {
            "RS_ZP0_NODE0004_EXACT_TWO_STAGE": 33,
            "RS_EVEN_NONZERO_ZP_AFTER_RNE": 15,
            "RS_ODD_NONZERO_ZP_AFTER_RNE_TIE_PARITY": 5,
        },
        "reuse_class_counts_1_5_27_15_5": reuse_counts
        == {
            "FROZEN_NODE0004_ANCHOR_NO_REBUILD": 1,
            "REUSE_NODE0004_EXACT_RECIPE_AND_SCHEDULE_SHAPE_TEMPLATE": 5,
            "REUSE_NODE0004_EXACT_TWO_STAGE_ARITHMETIC_RECIPE_ONLY": 27,
            (
                "NODE0004_STAGE0_SCRATCH_SATURATION_PRIMITIVES_ONLY__"
                "EVEN_NONZERO_ZP_INDEPENDENT"
            ): 15,
            (
                "NODE0004_STAGE0_SCRATCH_SATURATION_PRIMITIVES_ONLY__"
                "ODD_NONZERO_ZP_TIE_PARITY_INDEPENDENT"
            ): 5,
        },
        "node0004_exact_recipe_reuse_other32": value["group_summary"][
            "node0004_exact_recipe_reuse_eligible_other_stages"
        ]
        == 32,
        "node0004_schedule_shape_reuse_other5": value["group_summary"][
            "node0004_schedule_shape_template_reuse_eligible_other_stages"
        ]
        == 5,
        "other52_all_require_fresh_materialization": value[
            "group_summary"
        ]["independent_materialization_required_other_stages"]
        == 52,
        "node0004_not_recomputed_or_repackaged": (
            value["mode"]["node0004_recomputed"] is False
            and value["mode"]["node0004_repackaged"] is False
        ),
        "frozen_package_identity": value["frozen_node0004_anchor"][
            "package_zip_sha256"
        ]
        == SOURCE_SHA256[PACKAGE_ZIP_REL.as_posix()],
        "package_release_none": value["package_release"]["new_package"]
        == "NONE",
        "blockers_not_closed": value["blocker_delta"]["close"] == [],
        "no_target_or_server_artifacts": (
            value["claim_boundary"][
                "new_operator_target_json_generated"
            ]
            is False
            and value["claim_boundary"][
                "new_mapping_bitstream_execplan_sca_generated"
            ]
            is False
            and value["claim_boundary"]["new_server_package_generated"]
            is False
            and value["claim_boundary"]["server_action"] is False
        ),
        "manifest_semantic_hash": value["manifest_sha256"]
        == semantic_sha256(value, "manifest_sha256"),
    }
    failures = [key for key, passed in checks.items() if not passed]
    return {
        "schema": "requant-conv53-tail-signature-binding-validation-v1",
        "valid": not failures,
        "manifest_sha256": value["manifest_sha256"],
        "checks": checks,
        "failure_keys": failures,
        "summary": {
            "stage_count": len(rows),
            "other52_count": len(other),
            "physical_schedule_profile_count": len(
                value["physical_schedule_profiles"]
            ),
            "exact_recipe_reuse_other_count": value["group_summary"][
                "node0004_exact_recipe_reuse_eligible_other_stages"
            ],
            "schedule_shape_reuse_other_count": value["group_summary"][
                "node0004_schedule_shape_template_reuse_eligible_other_stages"
            ],
            "fresh_materialization_other_count": value["group_summary"][
                "independent_materialization_required_other_stages"
            ],
        },
    }


def build_and_write() -> tuple[dict[str, Any], dict[str, Any]]:
    value = build_manifest()
    validation = validate_manifest(value)
    if not validation["valid"]:
        raise ValueError(
            f"manifest validation failed: {validation['failure_keys']}"
        )
    write_json(CONTRACT_REL, value)
    write_json(ARTIFACT_REL / "validation_report.json", validation)
    receipt: dict[str, Any] = {
        "schema": (
            "requant-conv53-tail-signature-binding-generation-receipt-v1"
        ),
        "contract": file_receipt(
            CONTRACT_REL, "Conv53 tail signature machine manifest"
        ),
        "validation_report": file_receipt(
            ARTIFACT_REL / "validation_report.json",
            "binding-only validator report",
        ),
        "plan_is_mutable_provenance": True,
        "numeric_analysis_repeated": False,
        "w3_classification_repeated": False,
        "reuse_assets_consumed": True,
        "node0004_recomputed_or_repackaged": False,
        "server_actions": "NONE",
        "new_package": "NONE",
    }
    receipt["receipt_sha256"] = semantic_sha256(
        receipt, "receipt_sha256"
    )
    write_json(ARTIFACT_REL / "generation_receipt.json", receipt)
    return value, validation
