from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import torch

from .conv_sa_remaining52_expansion import (
    LOWERING_REL,
    MODEL_REL,
    RUNTIME_REL,
    _load,
    _port,
    _typed_parameter,
)
from .hashing import sha256_file
from .w5_conv_preflight import _initializer_values, _load_npy


SCHEMA = "resnet50-conv-native-four-lane-negative-psum-reachability-v1"
TEST_ID = "r5_conv_native_four_lane_negative_psum_reachability_v1"
NODE0004_HW_OP_ID = "hwop-0004-00"
INT32_MIN = -(1 << 31)
UINT32_MASK = (1 << 32) - 1
KNOWN_COUNTEREXAMPLES = (
    {"counterexample_id": "NEG5_PLUS5", "psum_in": -5, "dot4": 5},
    {
        "counterexample_id": "INT32_MIN_PLUS0",
        "psum_in": INT32_MIN,
        "dot4": 0,
    },
)

RULE_PATHS = (
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/服务器测试包生成规则.md"),
    Path(".agents/rules/INT8_SA点积专项规则.md"),
    Path(".agents/rules/精确UINT8量化尾专项规则.md"),
)
AUTHORITY_PATHS = (
    Path(
        ".agents/task_records/"
        "20260727_int8_sa_dot_product_common_cause_adjudication.md"
    ),
    Path(
        ".agents/task_records/"
        "20260727_int8_sa_rtl_repair_acceptance.md"
    ),
    Path(
        ".agents/task_records/"
        "20260729_trassic2_github_master_sync_and_interface_adjudication.md"
    ),
    Path("outputs/conv_sa_rtl_compile_audit_b7acbe5/report.json"),
    Path(
        ".agents/task_records/"
        "20260803_conv_node0004_v26_return_v28_dwrite_path_successor.md"
    ),
    Path(
        "contracts/operator_config/"
        "conv_sa_remaining52_expansion_v1.json"
    ),
)


class ConvNativeFourLaneError(ValueError):
    pass


def _s32_tensor(value: torch.Tensor) -> torch.Tensor:
    bits = torch.bitwise_and(value, UINT32_MASK)
    return torch.where(bits >= (1 << 31), bits - (1 << 32), bits)


def _position_witness(
    *,
    flat_nhw: int,
    output_shape: tuple[int, int, int, int],
) -> dict[str, int]:
    n_count, _, h_count, w_count = output_shape
    if not 0 <= flat_nhw < n_count * h_count * w_count:
        raise ConvNativeFourLaneError("flat output position is out of range")
    sample, spatial = divmod(flat_nhw, h_count * w_count)
    output_h, output_w = divmod(spatial, w_count)
    return {
        "flat_nhw": flat_nhw,
        "sample": sample,
        "output_h": output_h,
        "output_w": output_w,
    }


def _absolute_partial_sum_bound(
    *,
    packed_weight: np.ndarray,
    corrected_bias: np.ndarray,
) -> dict[str, Any]:
    per_channel = np.abs(corrected_bias.astype(np.int64)) + np.sum(
        np.abs(packed_weight.astype(np.int64)) * 255,
        axis=1,
        dtype=np.int64,
    )
    maximum = int(per_channel.max(initial=0))
    return {
        "formula": (
            "abs(corrected_bias[oc]) + "
            "sum_k(abs(weight[oc,k]) * 255)"
        ),
        "maximum": maximum,
        "int32_min_reachable_under_bound": maximum >= (1 << 31),
        "per_channel_sha256": hashlib.sha256(
            np.ascontiguousarray(per_channel.astype("<i8")).tobytes()
        ).hexdigest(),
    }


def _scan_exact_pairs(
    *,
    patches_u8: np.ndarray,
    packed_weight_s8: np.ndarray,
    corrected_bias_s32: np.ndarray,
    logical_k: int,
    output_shape: tuple[int, int, int, int],
    position_chunk: int = 256,
    output_value_budget: int = 4_000_000,
    stop_on_first_hit: bool = True,
) -> dict[str, Any]:
    if patches_u8.dtype != np.uint8:
        raise ConvNativeFourLaneError("patches must be uint8")
    if packed_weight_s8.dtype != np.int8:
        raise ConvNativeFourLaneError("weights must be int8")
    if patches_u8.ndim != 2 or packed_weight_s8.ndim != 2:
        raise ConvNativeFourLaneError("packed patches/weights must be rank two")
    outputs, weight_k = packed_weight_s8.shape
    if patches_u8.shape[1] != weight_k or corrected_bias_s32.shape != (outputs,):
        raise ConvNativeFourLaneError("packed Conv dimensions differ")
    if weight_k % 4:
        raise ConvNativeFourLaneError("packed K must be a multiple of four")
    groups = weight_k // 4
    patches = torch.from_numpy(
        np.ascontiguousarray(patches_u8.reshape(-1, groups, 4)).astype(
            np.int64
        )
    )
    weights = torch.from_numpy(
        np.ascontiguousarray(
            packed_weight_s8.reshape(outputs, groups, 4)
        ).astype(np.int64)
    )
    initial = torch.from_numpy(
        np.ascontiguousarray(corrected_bias_s32.astype(np.int64))
    )

    target_pairs = {
        (item["psum_in"], item["dot4"]): item["counterexample_id"]
        for item in KNOWN_COUNTEREXAMPLES
    }
    hit_counts = {item["counterexample_id"]: 0 for item in KNOWN_COUNTEREXAMPLES}
    first_hits: dict[str, dict[str, Any] | None] = {
        item["counterexample_id"]: None for item in KNOWN_COUNTEREXAMPLES
    }
    dot4_min = 1 << 62
    dot4_max = -(1 << 62)
    enumerated = 0
    chunk_receipts: list[dict[str, Any]] = []

    for p_start in range(0, patches.shape[0], position_chunk):
        xp = patches[p_start : p_start + position_chunk]
        state = initial.expand(xp.shape[0], outputs).clone()
        group_chunk = max(
            1, output_value_budget // max(1, xp.shape[0] * outputs)
        )
        for g_start in range(0, groups, group_chunk):
            g_end = min(groups, g_start + group_chunk)
            dot4 = torch.einsum(
                "pgk,ogk->pgo",
                xp[:, g_start:g_end, :],
                weights[:, g_start:g_end, :],
            )
            prefix = torch.cumsum(dot4, dim=1)
            psum_in = _s32_tensor(
                state[:, None, :] + prefix - dot4
            )
            local_min, local_max = torch.aminmax(dot4)
            dot4_min = min(dot4_min, int(local_min))
            dot4_max = max(dot4_max, int(local_max))
            enumerated += int(dot4.numel())

            digest = hashlib.sha256()
            digest.update(
                np.ascontiguousarray(
                    dot4[:, 0, :].numpy().astype("<i4")
                ).tobytes()
            )
            digest.update(
                np.ascontiguousarray(
                    dot4[:, -1, :].numpy().astype("<i4")
                ).tobytes()
            )
            digest.update(
                np.ascontiguousarray(
                    psum_in[:, 0, :].numpy().astype("<i4")
                ).tobytes()
            )
            digest.update(
                np.ascontiguousarray(
                    psum_in[:, -1, :].numpy().astype("<i4")
                ).tobytes()
            )
            chunk_receipts.append(
                {
                    "position_start": p_start,
                    "position_end_exclusive": p_start + xp.shape[0],
                    "group_start": g_start,
                    "group_end_exclusive": g_end,
                    "occurrence_count": int(dot4.numel()),
                    "boundary_payload_sha256": digest.hexdigest(),
                }
            )

            hit_found = False
            for (target_psum, target_dot4), counterexample_id in target_pairs.items():
                mask = (psum_in == target_psum) & (dot4 == target_dot4)
                count = int(torch.count_nonzero(mask))
                hit_counts[counterexample_id] += count
                if count and first_hits[counterexample_id] is None:
                    local_p, local_g, output_channel = (
                        int(item)
                        for item in torch.nonzero(mask, as_tuple=False)[0]
                    )
                    flat_nhw = p_start + local_p
                    group_index = g_start + local_g
                    lanes_x = patches[flat_nhw, group_index].tolist()
                    lanes_w = weights[output_channel, group_index].tolist()
                    first_hits[counterexample_id] = {
                        **_position_witness(
                            flat_nhw=flat_nhw,
                            output_shape=output_shape,
                        ),
                        "output_channel": output_channel,
                        "k_group": group_index,
                        "logical_k": logical_k,
                        "activation_u8_lanes": lanes_x,
                        "weight_s8_lanes": lanes_w,
                        "lane_products": [
                            int(left) * int(right)
                            for left, right in zip(
                                lanes_x, lanes_w, strict=True
                            )
                        ],
                        "psum_in": int(psum_in[local_p, local_g, output_channel]),
                        "dot4": int(dot4[local_p, local_g, output_channel]),
                        "result_s32": int(
                            _s32_tensor(
                                psum_in[local_p, local_g, output_channel]
                                + dot4[local_p, local_g, output_channel]
                            )
                        ),
                    }
                    hit_found = True
            state = _s32_tensor(state + prefix[:, -1, :])
            if hit_found and stop_on_first_hit:
                break
        if any(hit_counts.values()) and stop_on_first_hit:
            break

    return {
        "logical_k": logical_k,
        "packed_k": weight_k,
        "dot4_group_count_per_output": groups,
        "planned_occurrence_count": int(patches.shape[0]) * groups * outputs,
        "enumerated_occurrence_count": enumerated,
        "complete_enumeration": enumerated
        == int(patches.shape[0]) * groups * outputs,
        "dot4_observed_range": [dot4_min, dot4_max],
        "counterexample_hit_counts": hit_counts,
        "first_hits": first_hits,
        "chunk_count": len(chunk_receipts),
        "chunk_receipts_sha256": hashlib.sha256(
            json.dumps(
                chunk_receipts,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        "stop_on_first_hit": stop_on_first_hit,
    }


def _request_values(
    *,
    root: Path,
    request: dict[str, Any],
    runtime: dict[str, Any],
    initializers: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    geometry = request["logical_geometry"]
    attributes = geometry["attributes"]
    x_port = _port(request, "x")
    w_port = _port(request, "w")
    wzp_port = _port(request, "w_zero_point")
    bias_port = _port(request, "bias")
    activation = _load_npy(
        root / RUNTIME_REL,
        runtime,
        runtime["tensors"][x_port["tensor_id"]],
    )
    weight = initializers[w_port["onnx_name"]]
    weight_zero_point = initializers[wzp_port["onnx_name"]]
    bias = initializers[bias_port["onnx_name"]]
    x_zero_point = int(
        _typed_parameter(request, "x_zero_point")["value"]["scalar"]
    )
    if activation.dtype != np.uint8 or weight.dtype != np.int8:
        raise ConvNativeFourLaneError("Conv signedness differs")
    if np.any(weight_zero_point != 0):
        raise ConvNativeFourLaneError("nonzero weight zero-point is unsupported")
    n_count, channels, _, _ = activation.shape
    outputs, weight_channels, kernel_h, kernel_w = weight.shape
    if channels != weight_channels or attributes["group"] != 1:
        raise ConvNativeFourLaneError("grouped Conv is unsupported")
    pad_top, pad_left, pad_bottom, pad_right = attributes["pads"]
    padded = np.pad(
        activation,
        (
            (0, 0),
            (0, 0),
            (pad_top, pad_bottom),
            (pad_left, pad_right),
        ),
        mode="constant",
        constant_values=x_zero_point,
    )
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, (kernel_h, kernel_w), axis=(2, 3)
    )
    stride_h, stride_w = attributes["strides"]
    windows = windows[:, :, ::stride_h, ::stride_w, :, :]
    output_shape = tuple(geometry["output_shapes"][0])
    observed_shape = (
        n_count,
        outputs,
        windows.shape[2],
        windows.shape[3],
    )
    if observed_shape != output_shape:
        raise ConvNativeFourLaneError(
            f"output geometry differs: {observed_shape} != {output_shape}"
        )
    patches = np.ascontiguousarray(
        windows.transpose(0, 2, 3, 1, 4, 5)
    ).reshape(-1, channels * kernel_h * kernel_w)
    packed_weight = np.ascontiguousarray(weight.reshape(outputs, -1))
    logical_k = patches.shape[1]
    packed_k = math.ceil(logical_k / 4) * 4
    if packed_k != logical_k:
        patches = np.concatenate(
            (
                patches,
                np.full(
                    (patches.shape[0], packed_k - logical_k),
                    x_zero_point,
                    dtype=np.uint8,
                ),
            ),
            axis=1,
        )
        packed_weight = np.concatenate(
            (
                packed_weight,
                np.zeros(
                    (outputs, packed_k - logical_k), dtype=np.int8
                ),
            ),
            axis=1,
        )
    corrected_bias = (
        bias.astype(np.int64).reshape(outputs)
        - x_zero_point
        * np.sum(
            packed_weight[:, :logical_k].astype(np.int64),
            axis=1,
            dtype=np.int64,
        )
    )
    corrected_bias_s32 = (
        corrected_bias.astype(np.uint32).view(np.int32)
    )
    return {
        "activation": activation,
        "weight": weight,
        "bias": bias,
        "weight_zero_point": weight_zero_point,
        "patches": patches,
        "packed_weight": packed_weight,
        "corrected_bias_s32": corrected_bias_s32,
        "logical_k": logical_k,
        "output_shape": output_shape,
        "x_zero_point": x_zero_point,
        "ports": {
            "activation": x_port,
            "weight": w_port,
            "weight_zero_point": wzp_port,
            "bias": bias_port,
        },
    }


def _ordered_requests(
    requests: Iterable[dict[str, Any]],
    selected_hw_op_ids: set[str] | None,
) -> list[dict[str, Any]]:
    conv = [
        request
        for request in requests
        if request["identity"]["hw_op_type"] == "ConvInt32Accumulate"
    ]
    if len(conv) != 53:
        raise ConvNativeFourLaneError("typed Conv census differs from 53")
    by_id = {item["identity"]["hw_op_id"]: item for item in conv}
    if selected_hw_op_ids is not None:
        missing = selected_hw_op_ids - set(by_id)
        if missing:
            raise ConvNativeFourLaneError(
                f"unknown Conv hw_op ids: {sorted(missing)}"
            )
    ordered = [by_id[NODE0004_HW_OP_ID]]
    ordered.extend(
        item
        for item in conv
        if item["identity"]["hw_op_id"] != NODE0004_HW_OP_ID
    )
    if selected_hw_op_ids is not None:
        ordered = [
            item
            for item in ordered
            if item["identity"]["hw_op_id"] in selected_hw_op_ids
        ]
    return ordered


def build_negative_psum_reachability(
    project_root: Path,
    *,
    selected_hw_op_ids: set[str] | None = None,
    stop_on_first_hit: bool = True,
    position_chunk: int = 256,
    output_value_budget: int = 4_000_000,
) -> dict[str, Any]:
    root = project_root.resolve()
    lowering = _load(root / LOWERING_REL)
    runtime_path = root / RUNTIME_REL / "manifest.json"
    runtime = _load(runtime_path)
    initializers = _initializer_values(root / MODEL_REL)
    ordered = _ordered_requests(
        lowering["requests"], selected_hw_op_ids
    )

    records: list[dict[str, Any]] = []
    first_global_hit: dict[str, Any] | None = None
    for ordinal, request in enumerate(ordered, start=1):
        values = _request_values(
            root=root,
            request=request,
            runtime=runtime,
            initializers=initializers,
        )
        bound = _absolute_partial_sum_bound(
            packed_weight=values["packed_weight"][
                :, : values["logical_k"]
            ],
            corrected_bias=values["corrected_bias_s32"],
        )
        scan = _scan_exact_pairs(
            patches_u8=values["patches"],
            packed_weight_s8=values["packed_weight"],
            corrected_bias_s32=values["corrected_bias_s32"],
            logical_k=values["logical_k"],
            output_shape=values["output_shape"],
            position_chunk=position_chunk,
            output_value_budget=output_value_budget,
            stop_on_first_hit=stop_on_first_hit,
        )
        hit_count = sum(scan["counterexample_hit_counts"].values())
        record = {
            "scan_ordinal": ordinal,
            "identity": {
                **request["identity"],
                "request_id": request["request_id"],
                "request_sha256": request["request_sha256"],
            },
            "geometry": {
                "input_shape": request["logical_geometry"]["input_shapes"][0],
                "weight_shape": request["logical_geometry"]["input_shapes"][2],
                "output_shape": request["logical_geometry"]["output_shapes"][0],
                "attributes": request["logical_geometry"]["attributes"],
                "logical_k": values["logical_k"],
                "x_zero_point": values["x_zero_point"],
            },
            "source_ownership": {
                role: {
                    key: port[key]
                    for key in (
                        "tensor_id",
                        "onnx_name",
                        "identity_sha256",
                        "identity_source",
                    )
                    if key in port
                }
                for role, port in values["ports"].items()
            },
            "absolute_partial_sum_bound": bound,
            "exact_occurrence_scan": scan,
            "counterexample_reachable": hit_count > 0,
        }
        records.append(record)
        if hit_count:
            first_global_hit = {
                "hw_op_id": request["identity"]["hw_op_id"],
                "node_id": request["identity"]["node_id"],
                "request_id": request["request_id"],
                "first_hits": scan["first_hits"],
            }
            if stop_on_first_hit:
                break

    all_selected_scanned = len(records) == len(ordered)
    any_hit = first_global_hit is not None
    report = {
        "schema": SCHEMA,
        "test_id": TEST_ID,
        "status": (
            "HARDWARE_CAPABILITY_BLOCKED"
            if any_hit
            else (
                "EXACT_REACHABILITY_PASS"
                if all_selected_scanned
                else "INCOMPLETE"
            )
        ),
        "candidate_release": False,
        "package_release": "NONE",
        "scope": {
            "typed_conv_count": 53,
            "selected_hw_op_ids": (
                sorted(selected_hw_op_ids)
                if selected_hw_op_ids is not None
                else "ALL_53"
            ),
            "selected_count": len(ordered),
            "scanned_count": len(records),
            "all_selected_scanned": all_selected_scanned,
            "node0004_scanned_first": bool(records)
            and records[0]["identity"]["hw_op_id"]
            == NODE0004_HW_OP_ID,
        },
        "rtl_counterexamples": list(KNOWN_COUNTEREXAMPLES),
        "source_receipts": {
            LOWERING_REL.as_posix(): sha256_file(root / LOWERING_REL),
            (RUNTIME_REL / "manifest.json").as_posix(): sha256_file(
                runtime_path
            ),
            MODEL_REL.as_posix(): sha256_file(root / MODEL_REL),
            **{
                path.as_posix(): sha256_file(root / path)
                for path in (*RULE_PATHS, *AUTHORITY_PATHS)
            },
        },
        "algorithm": {
            "packing": (
                "OIHW-flatten K grouped in original consecutive groups of four; "
                "tail activation=x_zp and tail weight=0"
            ),
            "initial_psum": (
                "s32(bias - x_zero_point * sum(logical signed weights))"
            ),
            "recurrence": "psum_next=s32(psum_in+dot4)",
            "exact_pairs": list(KNOWN_COUNTEREXAMPLES),
            "position_chunk": position_chunk,
            "output_value_budget": output_value_budget,
            "stop_on_first_hit": stop_on_first_hit,
            "torch_thread_count": torch.get_num_threads(),
        },
        "result": {
            "any_counterexample_reachable": any_hit,
            "first_global_hit": first_global_hit,
            "enumerated_occurrence_count": sum(
                item["exact_occurrence_scan"][
                    "enumerated_occurrence_count"
                ]
                for item in records
            ),
            "planned_occurrence_count_scanned_records": sum(
                item["exact_occurrence_scan"]["planned_occurrence_count"]
                for item in records
            ),
        },
        "claim_boundary": (
            "Exact frozen W3 reachability of the two named "
            "SA_PE_Float_CSA counterexamples only.  A hit blocks the native "
            "four-lane package without authorizing RTL edits.  A no-hit result "
            "is model/instance-limited and does not establish full INT32-domain "
            "RTL correctness."
        ),
        "blocker_delta": {
            "close": (
                ["B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABILITY"]
                if all_selected_scanned and not any_hit
                else []
            ),
            "open": (
                ["B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE"]
                if any_hit
                else []
            ),
            "keep": [
                "B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING"
            ],
        },
        "records": records,
    }
    return report


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


__all__ = [
    "ConvNativeFourLaneError",
    "INT32_MIN",
    "KNOWN_COUNTEREXAMPLES",
    "NODE0004_HW_OP_ID",
    "SCHEMA",
    "TEST_ID",
    "_scan_exact_pairs",
    "build_negative_psum_reachability",
    "write_report",
]
