from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import sha256_file


SCHEMA = "resnet50-node0075-negative-psum-reachability-v1"
TEST_ID = "r5-node0075-negative-psum-reachability-v1"
MASK32 = (1 << 32) - 1
INT32_MIN = -(1 << 31)
INT32_MIN_BITS = 1 << 31

MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
A_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-6fbd5707d5f08110.npy"
)
ACC_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0075-accumulate.npy"
)
RTL_WITNESS_REL = Path(
    "outputs/node0075_negative_psum_reachability/"
    "current_rtl_witness.json"
)
WEIGHT_NAME = "resnetv17_dense0_weight_quantized"

LOCKED_RECEIPTS = (
    Path(".agents/agent.md"),
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/INT8_SA点积专项规则.md"),
    Path(".agents/rules/精确UINT8量化尾专项规则.md"),
    Path(".agents/rules/服务器测试包生成规则.md"),
    Path(
        ".agents/task_records/"
        "20260803_node0075_materializer_mainline_authorization.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_node0075_a_repeated_read_diagnostic_bypass_authorization.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_node0075_operator_family_owner_split.md"
    ),
    Path(
        ".agents/task_records/"
        "20260803_trassic_master_8f2f318_active_rtl_sync.md"
    ),
    Path(
        "contracts/operator_config/"
        "node0071_node0075_uint8_identity_alias_integration_v1.json"
    ),
    Path("contracts/resnet50_r5_lowering_bundle.json"),
    Path("artifacts/w3/golden_batch16/manifest.json"),
    Path("artifacts/w3/subop_batch16/manifest.json"),
    MODEL_REL,
    A_REL,
    ACC_REL,
    RTL_WITNESS_REL,
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_Control.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_CSA.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Mul_Array.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_ALU.v"
    ),
)


class Node0075NegativePsumError(ValueError):
    pass


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _s32(values: np.ndarray) -> np.ndarray:
    bits = np.bitwise_and(values.astype(np.int64, copy=False), MASK32)
    return np.where(bits >= INT32_MIN_BITS, bits - (1 << 32), bits)


def _load_weight(model_path: Path) -> np.ndarray:
    import onnx
    from onnx import numpy_helper

    model = onnx.load(model_path.as_posix(), load_external_data=True)
    matches = [
        numpy_helper.to_array(item)
        for item in model.graph.initializer
        if item.name == WEIGHT_NAME
    ]
    if len(matches) != 1:
        raise Node0075NegativePsumError(
            f"expected one {WEIGHT_NAME} initializer, found {len(matches)}"
        )
    return np.ascontiguousarray(matches[0])


def scan_arrays(
    activation_u8: np.ndarray,
    weight_kn_s8: np.ndarray,
    formal_acc_s32: np.ndarray | None = None,
    *,
    group_chunk: int = 64,
) -> dict[str, Any]:
    if activation_u8.dtype != np.uint8 or activation_u8.shape != (16, 2048):
        raise Node0075NegativePsumError(
            "node0075 A must be uint8[16,2048]"
        )
    if weight_kn_s8.dtype != np.int8 or weight_kn_s8.shape != (2048, 1000):
        raise Node0075NegativePsumError(
            "node0075 B must be int8[2048,1000]"
        )
    if formal_acc_s32 is not None and (
        formal_acc_s32.dtype != np.int32
        or formal_acc_s32.shape != (16, 1000)
    ):
        raise Node0075NegativePsumError(
            "node0075 formal accumulator must be int32[16,1000]"
        )
    if group_chunk <= 0:
        raise Node0075NegativePsumError("group_chunk must be positive")

    m_count, k_count = activation_u8.shape
    n_count = weight_kn_s8.shape[1]
    group_count = k_count // 4
    activation_groups = np.ascontiguousarray(
        activation_u8.reshape(m_count, group_count, 4).astype(np.int64)
    )
    weight_groups = np.ascontiguousarray(
        weight_kn_s8.T.reshape(n_count, group_count, 4).astype(np.int64)
    )

    hits: list[dict[str, Any]] = []
    first_stream_order_hit: dict[str, Any] | None = None
    dot_min = 1 << 62
    dot_max = -(1 << 62)
    psum_min = 1 << 62
    psum_max = -(1 << 62)
    negative_psum_occurrences = 0
    negative_to_zero_count = 0
    negative_to_int32_min_count = 0
    final_rows: list[np.ndarray] = []
    occurrence_count = 0

    for m_index in range(m_count):
        state = np.zeros(n_count, dtype=np.int64)
        for group_start in range(0, group_count, group_chunk):
            group_end = min(group_count, group_start + group_chunk)
            dot4 = np.einsum(
                "gk,ngk->gn",
                activation_groups[m_index, group_start:group_end],
                weight_groups[:, group_start:group_end],
                optimize=True,
            )
            prefix = np.cumsum(dot4, axis=0, dtype=np.int64)
            psum_in = state[np.newaxis, :] + prefix - dot4
            psum_next = psum_in + dot4

            dot_min = min(dot_min, int(dot4.min(initial=dot_min)))
            dot_max = max(dot_max, int(dot4.max(initial=dot_max)))
            psum_min = min(psum_min, int(psum_in.min(initial=psum_min)))
            psum_max = max(psum_max, int(psum_in.max(initial=psum_max)))
            occurrence_count += int(dot4.size)

            negative = psum_in < 0
            negative_psum_occurrences += int(np.count_nonzero(negative))
            negative_to_zero = negative & (psum_next == 0)
            negative_to_int32_min = negative & (
                np.bitwise_and(psum_next, MASK32) == INT32_MIN_BITS
            )
            negative_to_zero_count += int(
                np.count_nonzero(negative_to_zero)
            )
            negative_to_int32_min_count += int(
                np.count_nonzero(negative_to_int32_min)
            )

            for local_group, n_index in np.argwhere(
                negative_to_zero | negative_to_int32_min
            ):
                group_index = group_start + int(local_group)
                a_lanes = activation_groups[m_index, group_index].tolist()
                b_lanes = weight_groups[int(n_index), group_index].tolist()
                expected_s32 = int(psum_next[local_group, n_index])
                boundary = (
                    "NEGATIVE_PSUM_EXACT_CANCELLATION"
                    if expected_s32 == 0
                    else "NEGATIVE_PSUM_TO_INT32_MIN"
                )
                hit = {
                    "m": m_index,
                    "n": int(n_index),
                    "k_group": group_index,
                    "k_byte_start": group_index * 4,
                    "a_u8_lanes": [int(item) for item in a_lanes],
                    "b_s8_lanes": [int(item) for item in b_lanes],
                    "lane_products": [
                        int(left) * int(right)
                        for left, right in zip(a_lanes, b_lanes, strict=True)
                    ],
                    "psum_in_s32": int(psum_in[local_group, n_index]),
                    "dot4_s32": int(dot4[local_group, n_index]),
                    "expected_next_s32": expected_s32,
                    "boundary_class": boundary,
                    "current_split_rtl_result_bits": (
                        "0x80000000"
                        if expected_s32 == 0
                        else "0x00000000"
                    ),
                }
                if first_stream_order_hit is None:
                    first_stream_order_hit = hit
                hits.append(hit)

            state = _s32(state + prefix[-1])
        final_rows.append(state.astype(np.int32))

    final_acc = np.stack(final_rows)
    final_match = (
        None
        if formal_acc_s32 is None
        else bool(np.array_equal(final_acc, formal_acc_s32))
    )
    mismatch_count = (
        None
        if formal_acc_s32 is None
        else int(np.count_nonzero(final_acc != formal_acc_s32))
    )
    hits.sort(key=lambda item: (item["m"], item["n"], item["k_group"]))
    planned = m_count * n_count * group_count
    return {
        "scan_order": (
            "for each (m,n), k_group=0..511; each group consumes "
            "A[m,4g:4g+4] and B[4g:4g+4,n]"
        ),
        "planned_occurrence_count": planned,
        "enumerated_occurrence_count": occurrence_count,
        "complete_enumeration": occurrence_count == planned,
        "dot4_observed_range": [dot_min, dot_max],
        "psum_in_observed_range": [psum_min, psum_max],
        "negative_psum_occurrence_count": negative_psum_occurrences,
        "negative_to_zero_count": negative_to_zero_count,
        "negative_to_int32_min_count": negative_to_int32_min_count,
        "boundary_hit_count": len(hits),
        "boundary_hits_sha256": _sha256_bytes(
            _canonical_json_bytes(hits)
        ),
        "lexicographic_first_hit": hits[0] if hits else None,
        "first_stream_order_hit": first_stream_order_hit,
        "first_sixteen_hits": hits[:16],
        "formal_final_accumulator_match": final_match,
        "formal_final_accumulator_mismatch_count": mismatch_count,
        "computed_final_accumulator_value_sha256": _sha256_bytes(
            np.ascontiguousarray(final_acc.astype("<i4")).tobytes()
        ),
        "computed_final_accumulator_range": [
            int(final_acc.min()),
            int(final_acc.max()),
        ],
        "formal_final_zero_count": int(
            np.count_nonzero(final_acc == 0)
        ),
    }


def _validate_rtl_witness(receipt: Mapping[str, Any]) -> None:
    required = {
        "status": "CURRENT_RTL_NODE0075_BOUNDARY_REPRODUCED",
        "compile_exit": 0,
        "simulation_exit": 0,
        "observed_result_bits": "0x80000000",
        "expected_math_bits": "0x00000000",
        "current_rtl_mismatch_reproduced": True,
    }
    for key, expected in required.items():
        if receipt.get(key) != expected:
            raise Node0075NegativePsumError(
                f"RTL witness {key} differs: {receipt.get(key)!r}"
            )
    witness = receipt.get("witness", {})
    if (
        witness.get("psum_in_s32") != -19
        or witness.get("dot4_s32") != 19
        or witness.get("a_u8_lanes") != [28, 13, 1, 0]
        or witness.get("b_s8_lanes") != [1, -2, 17, -2]
    ):
        raise Node0075NegativePsumError("RTL witness payload differs")


def build_report(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    missing = [path.as_posix() for path in LOCKED_RECEIPTS if not (root / path).is_file()]
    if missing:
        raise Node0075NegativePsumError(
            f"required receipts are missing: {missing}"
        )

    activation = np.load(root / A_REL, allow_pickle=False)
    formal_acc = np.load(root / ACC_REL, allow_pickle=False)
    weight = _load_weight(root / MODEL_REL)
    weight_value_sha256 = _sha256_bytes(
        np.ascontiguousarray(weight).tobytes()
    )
    if weight_value_sha256 != (
        "0a04b48f313e071330869b5638d696e008a35801c74db1778f9376a8c6008688"
    ):
        raise Node0075NegativePsumError(
            "node0075 weight initializer identity differs"
        )

    scan = scan_arrays(activation, weight, formal_acc)
    rtl_witness = json.loads(
        (root / RTL_WITNESS_REL).read_text(encoding="utf-8")
    )
    _validate_rtl_witness(rtl_witness)
    blocked = (
        scan["complete_enumeration"]
        and scan["formal_final_accumulator_match"] is True
        and scan["boundary_hit_count"] > 0
        and rtl_witness["current_rtl_mismatch_reproduced"] is True
    )
    if not blocked:
        raise Node0075NegativePsumError(
            "frozen node0075 hardware blocker did not close mechanically"
        )

    plan_path = root / ".agents/plan.md"
    return {
        "schema": SCHEMA,
        "test_id": TEST_ID,
        "status": "HARDWARE_CAPABILITY_BLOCKED",
        "candidate_release": False,
        "package_release": "NONE",
        "owner": {
            "operator_family": "QLinearMatMul/node0075",
            "owner_thread": "019fc775-8de0-7f10-bc4a-026a4673776f",
            "mainline_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        },
        "frozen_instance": {
            "request_id": "r5:hwop-0075-00",
            "request_sha256": (
                "67453b2893d8dcee976f871f21e35313d08949a45779c2a8aecc4e31d6c24553"
            ),
            "shape": {"M": 16, "K": 2048, "N": 1000},
            "a_dtype": "uint8",
            "b_dtype": "int8",
            "accumulator_dtype": "int32",
            "a_zero_point": 0,
            "b_zero_point": 0,
            "initial_psum": 0,
            "weight_initializer_value_sha256": weight_value_sha256,
            "formal_accumulator_file_sha256": sha256_file(root / ACC_REL),
        },
        "frozen_recurrence_order": {
            "a_alias_storage_owner": "r5:hwop-0071-01:D",
            "a_slice_base_formula": (
                "0x000a2000+(slice_id<<25), 0<=slice_id<16"
            ),
            "a_transaction_equation": (
                "addr(slice,t)=0x000a2000+(slice_id<<25)+32*t, "
                "0<=t<64"
            ),
            "a_element_order": (
                "C-order A[m,k], byte offset k; transaction t carries "
                "k=32t..32t+31; dot4 group g carries k=4g..4g+3"
            ),
            "required_per_pass_ordered_address_sha256": (
                "4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d"
            ),
            "required_unique_byte_set_sha256": (
                "3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06"
            ),
            "k_reorder_or_a_relayout_used": False,
        },
        "exact_occurrence_scan": scan,
        "current_rtl_witness": rtl_witness,
        "first_divergence": {
            "id": (
                "B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE"
            ),
            "stage": "r5:hwop-0075-00 INT8-SA accumulator recurrence",
            "before": (
                "frozen A/B lanes and psum_in=-19 produce exact dot4=+19"
            ),
            "after": (
                "mathematical next psum is 0x00000000, but current "
                "SA_PE_Float_CSA produces 0x80000000"
            ),
            "hardware_leaf": (
                "SA_PE_Float_CSA live split assignments reconstruct "
                "o_IntResult[30:0] and o_IntResult[31] separately"
            ),
            "config_expressible_fix": False,
            "functional_rtl_repair_authorized": False,
        },
        "materializer_and_reload_accounting": {
            "minimum_authorized_reload_passes": 8,
            "minimum_formula": "ceil(1000/(16*8))=8",
            "planned_if_reached": {
                "accepted_32byte_reads_per_slice": 512,
                "accepted_read_occurrences_total": 8192,
                "accepted_a_traffic_bytes": 262144,
                "unique_a_storage_bytes": 32768,
            },
            "actual_materialized_reload_passes": 0,
            "actual_materialized_accepted_a_traffic_bytes": 0,
            "reason_not_materialized": (
                "fail-fast at the earlier frozen-instance hardware "
                "capability leaf; no target JSON/config/execplan/SCA was emitted"
            ),
        },
        "outputs": {
            "op_json_schema_or_template": False,
            "handler_or_registry": False,
            "consumer_materializer": False,
            "target_json": False,
            "mapping": False,
            "bitstream": False,
            "execplan": False,
            "sca": False,
            "config_bound_e2": False,
            "server_package": False,
        },
        "blocker_delta": {
            "closed": ["SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA"],
            "opened_exact": [
                "B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE"
            ],
            "kept_open_downstream_not_reached": [
                "B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING",
                "B_MATMUL_TAIL",
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
            ],
        },
        "source_receipts": {
            path.as_posix(): sha256_file(root / path)
            for path in LOCKED_RECEIPTS
        },
        "mutable_provenance": {
            ".agents/plan.md": sha256_file(plan_path),
            "binding_policy": "startup/current observation only",
        },
        "rule_confirmation": {
            "rule_ids": [
                "CDA-SA-INT8-RTL-COMPATIBILITY-001",
                "CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001",
                "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            ],
            "evidence": (
                "8,192,000/8,192,000 frozen node0075 occurrences scanned; "
                "272 exact negative-psum cancellations; first W3 witness "
                "reproduced against current exact RTL as 0x80000000 != 0"
            ),
            "claim_boundary": (
                "frozen node0075 natural C-order K recurrence and current "
                "8f2f318-synchronized RTL only; no family-wide repair claim"
            ),
        },
        "rule_delta_proposal": {
            "required": False,
            "reason": (
                "current rules already require exact current-RTL capability "
                "and fail-closed termination before target/package emission"
            ),
        },
        "claim_boundary": (
            "Exact frozen node0075 natural-order recurrence reachability and "
            "current RTL witness only. No handler/materializer/config/E2 or "
            "server package was generated, and no functional RTL was changed."
        ),
    }


def write_report(path: Path, report: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


__all__ = [
    "INT32_MIN",
    "Node0075NegativePsumError",
    "SCHEMA",
    "TEST_ID",
    "build_report",
    "scan_arrays",
    "write_report",
]
