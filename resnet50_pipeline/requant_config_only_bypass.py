"""Fail-closed config-only bypass adjudication for the Requant family.

This module consumes the already accepted 54-stage evidence.  It deliberately
does not emit operator JSON, mapping, bitstream, execplan, SCA, or a server
package.  A group is allowed to use the
``CONFIG_ONLY_CORRECTNESS_BASELINE`` label only after every materialization
gate is closed; no group currently satisfies that condition.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "requant-config-only-bypass-adjudication-v1"
STATUS = "NO_GROUP_MATERIALIZED_FIRST_BREAK_ADJUDICATED"
MAINLINE_THREAD_ID = "019fa2ca-72bc-7753-8d58-81e59bc76c88"

EVIDENCE_REL = Path(
    "contracts/operator_config/requant_quant_tail_evidence_input_v1.json"
)
CAPABILITY_REL = Path(
    "contracts/operator_config/exact_uint8_quant_tail_capability_v1.json"
)
ROUNDING_DISCRIMINATOR_REL = Path(
    "contracts/operator_config/"
    "exact_uint8_quant_tail_rounding_discriminator_v1.json"
)
ROUNDING_MAINLINE_RECORD_REL = Path(
    ".agents/task_records/"
    "20260727_exact_uint8_quant_tail_rounding_mainline_adjudication.md"
)
CONTRACT_REL = Path(
    "contracts/operator_config/requant_config_only_bypass_adjudication_v1.json"
)
ARTIFACT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-config-only-bypass-adjudication-v1"
)

ACTIVE_RULE_SHA256 = {
    ".agents/rules/生成前必读索引.md": (
        "3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19"
    ),
    ".agents/rules/算子配置规则.md": (
        "407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc"
    ),
    ".agents/rules/精确UINT8量化尾专项规则.md": (
        "5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0"
    ),
    ".agents/rules/RequantizeUint8算子配置规则.md": (
        "d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59"
    ),
    ".agents/rules/最小双Stage生命周期规则.md": (
        "821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171"
    ),
}

BYPASS_FIELDS = (
    "bypass_reason",
    "contradicted_or_missing_native_path",
    "exact_equivalence_scope",
    "materialized_configuration_mechanism",
    "performance_and_resource_cost",
    "unresolved_production_blocker",
    "claim_boundary",
)


class RequantConfigOnlyBypassError(ValueError):
    """Raised when the fail-closed adjudication inputs or output drift."""


def _canonical_bytes(value: Any) -> bytes:
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


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RequantConfigOnlyBypassError(f"JSON root must be an object: {path}")
    return value


def _file_receipt(root: Path, relative: Path, role: str) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative.as_posix(),
        "role": role,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
    }


def _rule_receipts(root: Path) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for relative, expected in ACTIVE_RULE_SHA256.items():
        path = root / relative
        actual = _sha256_file(path)
        if actual != expected:
            raise RequantConfigOnlyBypassError(
                f"active rule receipt drifted: {relative}: {actual} != {expected}"
            )
        receipts.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": actual,
            }
        )
    return receipts


def _partition(
    stages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    zp0: list[dict[str, Any]] = []
    even: list[dict[str, Any]] = []
    odd: list[dict[str, Any]] = []
    for stage in stages:
        qparams = stage.get("qparams")
        if not isinstance(qparams, dict):
            raise RequantConfigOnlyBypassError("stage qparams missing")
        zero_point = qparams.get("y_zero_point")
        if not isinstance(zero_point, int):
            raise RequantConfigOnlyBypassError("stage zero-point is not int")
        if zero_point == 0:
            zp0.append(stage)
        elif zero_point % 2 == 0:
            even.append(stage)
        else:
            odd.append(stage)
    if (len(zp0), len(even), len(odd)) != (33, 16, 5):
        raise RequantConfigOnlyBypassError(
            "requant partition drifted from 33/16/5"
        )
    return zp0, even, odd


def _member(stage: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_id": stage["request_id"],
        "node_id": stage["node_id"],
        "onnx_op_type": stage["onnx_op_type"],
        "logical_shape": stage["logical_shape"],
        "y_zero_point": stage["qparams"]["y_zero_point"],
        "w3_exact": stage["w3"]["exact_recipe_proven"],
        "negative_w3_count": stage["w3"]["negative_count"],
        "physical_materialization_classification": stage[
            "physical_materialization_classification"
        ],
    }


def _gate_state(first_break: str, secondary: list[str]) -> dict[str, Any]:
    return {
        "materialization_status": "BLOCKED_BEFORE_NEW_OPERATOR_JSON",
        "first_non_bypassable_capability_break": first_break,
        "secondary_gates_not_reached_or_not_closed": secondary,
        "static_logical_to_materialized_leaf_diff": {
            "status": "NOT_REACHED_NO_MATERIALIZED_JSON",
            "nonbase_field_change_allowlist": [],
            "required_declaration_fields_if_reached": [
                "owner",
                "input_source",
                "transformation_formula",
                "old_value",
                "expected_new_value",
                "authorization_reason",
            ],
        },
        "formal_output_byte_coverage_from_final_occurrence_address_equations": {
            "status": "NOT_REACHED_NO_FINAL_OCCURRENCE_OR_ADDRESS_EQUATIONS",
            "covered_byte_set": None,
            "required_output_byte_count": None,
        },
        "final_materialized_json_roundtrip": False,
        "mapping_exact_penalty_zero": False,
        "bitstream_roundtrip": False,
        "execplan_sca_address_lifetime_terminal": False,
        "config_bound_simulator": False,
        "independent_double_rebuild": False,
        "config_only_correctness_baseline": False,
    }


def _annotations() -> dict[str, dict[str, Any]]:
    return {
        "zp0_33": {
            "bypass_reason": (
                "The stock two-PE MAC+INT32_SUB recipe contracts the required "
                "FP32 multiply rounding point with magic addition."
            ),
            "contradicted_or_missing_native_path": [
                "one-round FMA differs from sequential multiply then RNE for "
                "int32=400,multiplier_bits=0x3d828f5c",
                "a two-stage scratch singleton now distinguishes 26 from 25, "
                "but full-domain ordered rounding and registered typed "
                "transport/mapper/terminal closure are missing",
            ],
            "exact_equivalence_scope": (
                "All 33 frozen W3 zp0 stages remain numerical evidence only; "
                "the representative is r5:hwop-0001-01, and its older fused "
                "node0001 local E2 is explicitly not extrapolated."
            ),
            "materialized_configuration_mechanism": (
                "Proposed guard followed by explicit FP32 MUL, separately "
                "rounded ADD of fixed magic, raw INT32_SUB, and UINT8 "
                "saturation. The shared Quant line materialized this separation "
                "only for a 32-identical-positive-lane singleton; this family "
                "emitted no new operator JSON because full-domain topology/"
                "mapper/terminal gates remain open."
            ),
            "performance_and_resource_cost": {
                "proposed_lane_utilization": "4_of_8_output_lanes",
                "additional_stage_or_pe_depth": "three_PE_tail_after_guard",
                "scratch": "explicit_guard_FP32_lifetime",
                "barriers": "at_least_one_extra_ordering_boundary",
                "traffic": "extra_FP32_scratch_read_write",
            },
            "unresolved_production_blocker": [
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                "B_QUANT_TAIL_TYPED_BINDING",
                "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
                "B_REQUANT_SERVER_E4_E5",
            ],
            "claim_boundary": (
                "FIRST_BREAK_ADJUDICATION_ONLY; not "
                "CONFIG_ONLY_CORRECTNESS_BASELINE, target config, E4, or E5."
            ),
        },
        "even_nonzero_zp_16": {
            "bypass_reason": (
                "Nonzero zero-point requires negative accumulator magnitudes "
                "near zero; the zp0 max(acc,0) guard is not equivalent."
            ),
            "contradicted_or_missing_native_path": [
                "stock GA int32tofp32 maps -1 to 0xcf000000 instead of "
                "0xbf800000 and destroys signed magnitude",
                "no pure-config route from the original typed INT32 input "
                "preserves all negative magnitudes",
            ],
            "exact_equivalence_scope": (
                "All 16 frozen W3 even nonzero-zp stages, represented by "
                "r5:hwop-0003-01 (zp=150); original typed INT32 inputs and "
                "qparams only, excluding host-precomputed internal scaled or "
                "final values."
            ),
            "materialized_configuration_mechanism": (
                "No legal mechanism materialized. Replaying original INT32 "
                "input/constants does not repair signed conversion; replaying "
                "a host-computed scaled/output tensor would replace the "
                "operator computation and is excluded."
            ),
            "performance_and_resource_cost": {
                "materialized": False,
                "hypothetical_only": (
                    "a future signed ingress plus the zp0 explicit-rounding "
                    "tail would add scratch, traffic, barriers, and low lanes"
                ),
            },
            "unresolved_production_blocker": [
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN",
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                "B_QUANT_TAIL_TYPED_BINDING",
                "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "B_REQUANT_SERVER_E4_E5",
            ],
            "claim_boundary": (
                "SIGNED_INGRESS_FIRST_BREAK_ONLY; not "
                "CONFIG_ONLY_CORRECTNESS_BASELINE, target config, E4, or E5."
            ),
        },
        "odd_nonzero_zp_5": {
            "bypass_reason": (
                "Odd nonzero zero-point needs both signed magnitude retention "
                "and zero-point addition after nearest-even rounding."
            ),
            "contradicted_or_missing_native_path": [
                "the same signed INT32 ingress counterexample occurs before "
                "rounding",
                "putting odd zp inside FP32 magic bias reverses half-tie "
                "parity; r5:hwop-0014-01 has 32 W3 counterexamples",
            ],
            "exact_equivalence_scope": (
                "All 5 frozen W3 odd nonzero-zp stages, represented by "
                "r5:hwop-0014-01 (zp=123); original typed INT32 inputs and "
                "qparams only, excluding host-precomputed internal scaled or "
                "final values."
            ),
            "materialized_configuration_mechanism": (
                "No legal mechanism materialized. If signed ingress is later "
                "closed, fixed magic plus raw INT32_SUB constant "
                "0x4b400000-zp remains a proposal that must still close the "
                "three-PE and tie-parity materialized gates."
            ),
            "performance_and_resource_cost": {
                "materialized": False,
                "hypothetical_only": (
                    "signed ingress plus explicit multiply rounding, fixed "
                    "magic, post-RNE zp constant, scratch, and barriers"
                ),
            },
            "unresolved_production_blocker": [
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN",
                "B_REQUANT_MAGIC_ZP_TIE_PARITY",
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                "B_QUANT_TAIL_TYPED_BINDING",
                "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "B_REQUANT_SERVER_E4_E5",
            ],
            "claim_boundary": (
                "SIGNED_INGRESS_FIRST_BREAK_WITH_TIE_PARITY_SECONDARY; not "
                "CONFIG_ONLY_CORRECTNESS_BASELINE, target config, E4, or E5."
            ),
        },
    }


def build_adjudication(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    evidence = _load(root / EVIDENCE_REL)
    capability = _load(root / CAPABILITY_REL)
    discriminator = _load(root / ROUNDING_DISCRIMINATOR_REL)
    stages = evidence.get("stage_evidence")
    if not isinstance(stages, list) or len(stages) != 54:
        raise RequantConfigOnlyBypassError("accepted 54-stage evidence missing")
    if any(not isinstance(stage, dict) for stage in stages):
        raise RequantConfigOnlyBypassError("stage evidence item is not object")
    if any(stage["w3"]["exact_recipe_proven"] is not True for stage in stages):
        raise RequantConfigOnlyBypassError("54/54 W3 exact invariant failed")
    zp0, even, odd = _partition(stages)
    annotations = _annotations()
    groups = {
        "zp0_33": {
            "count": len(zp0),
            "representative_request_id": "r5:hwop-0001-01",
            "members": [_member(stage) for stage in zp0],
            "bypass_annotation": annotations["zp0_33"],
            "gate_state": _gate_state(
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                [
                    "B_QUANT_TAIL_TYPED_BINDING",
                    "B_QUANT_TAIL_MAPPER_REGISTRATION",
                    "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
                ],
            ),
        },
        "even_nonzero_zp_16": {
            "count": len(even),
            "representative_request_id": "r5:hwop-0003-01",
            "members": [_member(stage) for stage in even],
            "bypass_annotation": annotations["even_nonzero_zp_16"],
            "gate_state": _gate_state(
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                [
                    "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                    "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
                ],
            ),
        },
        "odd_nonzero_zp_5": {
            "count": len(odd),
            "representative_request_id": "r5:hwop-0014-01",
            "members": [_member(stage) for stage in odd],
            "bypass_annotation": annotations["odd_nonzero_zp_5"],
            "gate_state": _gate_state(
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                [
                    "B_REQUANT_MAGIC_ZP_TIE_PARITY",
                    "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                    "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
                ],
            ),
        },
    }
    for name, group in groups.items():
        fields = set(group["bypass_annotation"])
        if fields != set(BYPASS_FIELDS):
            raise RequantConfigOnlyBypassError(
                f"{name} seven-field annotation differs: {sorted(fields)}"
            )
        if group["representative_request_id"] not in {
            item["request_id"] for item in group["members"]
        }:
            raise RequantConfigOnlyBypassError(
                f"{name} representative is outside its partition"
            )
    matrix = capability.get("capability_matrix")
    if not isinstance(matrix, list):
        raise RequantConfigOnlyBypassError("capability matrix missing")
    capability_status = {
        item["capability"]: item["status"]
        for item in matrix
        if isinstance(item, dict)
        and isinstance(item.get("capability"), str)
        and isinstance(item.get("status"), str)
    }
    required_status = {
        "signed INT32 ingress": "CONTRADICTED",
        "nearest-even rounding": "HARDWARE_ORDER_UNKNOWN",
        "GA topology": "TWO_PE_ORACLE_REUSABLE_THREE_PE_RECIPE_UNPROVEN",
        "typed handler": "PLACEHOLDER_BLOCKED",
        "mapper": "REGISTRY_MISSING",
    }
    for name, expected in required_status.items():
        if capability_status.get(name) != expected:
            raise RequantConfigOnlyBypassError(
                f"capability status drifted: {name}"
            )
    discriminator_expected = {
        "claim": "LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE",
        "input_int32": 400,
        "multiplier_bits": "0x3d828f5c",
        "zero_point": 0,
        "expected_stage0_scratch_bits": "0x41cc0000",
        "expected_sequential_uint8": 26,
        "expected_fused_uint8": 25,
    }
    if discriminator.get("claim") != discriminator_expected["claim"]:
        raise RequantConfigOnlyBypassError(
            "shared rounding discriminator claim boundary drifted"
        )
    discriminator_values = discriminator.get("discriminator")
    if not isinstance(discriminator_values, dict):
        raise RequantConfigOnlyBypassError(
            "shared rounding discriminator values missing"
        )
    for key, expected in discriminator_expected.items():
        if key == "claim":
            continue
        if discriminator_values.get(key) != expected:
            raise RequantConfigOnlyBypassError(
                f"shared rounding discriminator drifted: {key}"
            )
    forbidden = discriminator.get("forbidden_outputs")
    if not isinstance(forbidden, dict) or any(forbidden.values()):
        raise RequantConfigOnlyBypassError(
            "shared rounding discriminator emitted a forbidden target artifact"
        )
    value: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "owner_family": "RequantizeUint8/AverageRequantizeUint8",
        "mainline_thread_id": MAINLINE_THREAD_ID,
        "rule_ids": [
            "CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001",
            "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
            "CDA-QUANT-TAIL-ZP-AFTER-ROUND-001",
            "CDA-QUANT-TAIL-MAGIC-DOMAIN-001",
            "CDA-QUANT-TAIL-CAPABILITY-MATRIX-001",
            "CDA-REQUANT-FAMILY-QPARAM-CLASSIFICATION-001",
            "CDA-REQUANT-NONZERO-ZP-GUARD-001",
            "CDA-REQUANT-ZP-TIE-PARITY-001",
        ],
        "semantic_rule_receipts": _rule_receipts(root),
        "evidence_inputs": [
            _file_receipt(root, EVIDENCE_REL, "accepted_54_stage_evidence"),
            _file_receipt(root, CAPABILITY_REL, "shared_capability_matrix"),
            _file_receipt(
                root,
                ROUNDING_DISCRIMINATOR_REL,
                "shared_two_stage_rounding_singleton_diagnostic",
            ),
            _file_receipt(
                root,
                ROUNDING_MAINLINE_RECORD_REL,
                "mainline_accepted_singleton_claim_boundary",
            ),
        ],
        "accepted_evidence_invariants": {
            "stage_count": 54,
            "w3_exact_count": 54,
            "partition": {
                "zp0": 33,
                "even_nonzero_zp": 16,
                "odd_nonzero_zp": 5,
            },
            "existing_physical_local_e2_request_ids": ["r5:hwop-0001-01"],
            "existing_node0001_e2_extrapolated": False,
        },
        "shared_rounding_singleton_dependency": {
            "status": "CONSUMED_AS_DIAGNOSTIC_DEPENDENCY_ONLY",
            "claim": "LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE",
            "scope": {
                "element_count": 32,
                "all_lanes_identical_positive_int32": 400,
                "multiplier_bits": "0x3d828f5c",
                "zero_point": 0,
            },
            "stage0_scratch_bits": "0x41cc0000",
            "sequential_uint8": 26,
            "fused_negative_control_uint8": 25,
            "meaning_for_requant": (
                "Explicit scratch separation is no longer proposal-only for "
                "the singleton, but it does not prove any of the 33 zp0 or "
                "AverageRequant complete frozen domains."
            ),
            "does_not_close": [
                "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                "B_QUANT_TAIL_TYPED_BINDING",
                "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
                "B_REQUANT_SERVER_E4_E5",
            ],
            "missing_for_requant": [
                "complete frozen representative domain equivalence",
                "native typed transport",
                "mapping and bitstream",
                "execplan/SCA",
                "lifetime and terminal",
                "config-bound complete-domain simulator",
            ],
            "requant_group_classification_changed": False,
            "requant_blocker_closed": False,
        },
        "groups": groups,
        "average_requant": {
            "scope": deepcopy(evidence["average_requant_input"]),
            "status": "CONFIG_ONLY_MATERIALIZATION_NOT_STARTED",
            "first_non_bypassable_capability_break": (
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY"
            ),
            "reason": (
                "The 49-term sum is nonnegative and zp0-compatible, so signed "
                "ingress is not the first break; explicit multiply rounding "
                "and the sum-to-tail typed/address/lifetime binding remain open."
            ),
            "new_operator_json_generated": False,
        },
        "negative_controls": {
            "fma_rounding": {
                "int32": 400,
                "multiplier_bits": "0x3d828f5c",
                "sequential": 26,
                "fused_magic": 25,
            },
            "signed_ingress": {
                "int32": -1,
                "expected_fp32_bits": "0xbf800000",
                "observed_static_bits": "0xcf000000",
            },
            "odd_zp_tie": {
                "request_id": "r5:hwop-0014-01",
                "scaled": 4.5,
                "zero_point": 123,
                "expected": 127,
                "zp_in_magic": 128,
                "w3_counterexample_count": 32,
            },
            "magic_domain": {
                "scaled": -12582913.0,
                "zero_point": 0,
                "expected": 0,
                "magic_decode_then_saturate": 255,
            },
        },
        "materialization_boundary": {
            "claim_label_emitted": "FIRST_BREAK_ADJUDICATION_ONLY",
            "config_only_correctness_baseline_count": 0,
            "new_operator_json_generated": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_sca_generated": False,
            "server_package_generated": False,
            "server_inspected_uploaded_or_run": False,
            "event_edge_packages_modified": False,
            "functional_rtl_modified": False,
            "counts_as_e2": False,
            "counts_as_e4": False,
            "counts_as_e5": False,
            "candidate_release": False,
            "formal_target_instance_allowed": False,
        },
        "rule_delta_proposal": [],
        "rule_delta_resolution": {
            "proposal_id": "CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001",
            "status": "ACCEPTED_IN_PUBLIC_RULE",
            "public_rule_sha256": ACTIVE_RULE_SHA256[
                ".agents/rules/算子配置规则.md"
            ],
            "additional_rule_change_requested": False,
        },
        "blocker_delta": {
            "add": [],
            "close": [],
            "keep": [
                "B_QUANT_TAIL_FMA_ROUNDING_POINT",
                "B_QUANT_TAIL_MAGIC_DOMAIN_BOUND",
                "B_QUANT_TAIL_SIGNED_INT32_INGRESS",
                "B_QUANT_TAIL_THREE_PE_TOPOLOGY",
                "B_QUANT_TAIL_TYPED_BINDING",
                "B_QUANT_TAIL_MAPPER_REGISTRATION",
                "B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN",
                "B_REQUANT_MAGIC_ZP_TIE_PARITY",
                "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
                "B_REQUANT_SERVER_E4_E5",
            ],
        },
        "package_release": {
            "release": False,
            "package": None,
            "reason": (
                "No group passed the config-only materialized E2 gates, and "
                "server package generation/action is outside this dispatch."
            ),
        },
    }
    value["adjudication_sha256"] = _sha256_bytes(_canonical_bytes(value))
    return value


def validate_adjudication(
    project_root: Path, value: Mapping[str, Any]
) -> dict[str, Any]:
    root = project_root.resolve()
    expected = build_adjudication(root)
    actual = deepcopy(dict(value))
    if actual != expected:
        raise RequantConfigOnlyBypassError(
            "adjudication differs from accepted evidence/rule-derived value"
        )
    return {
        "schema": "requant-config-only-bypass-validation-v1",
        "valid": True,
        "status": actual["status"],
        "adjudication_sha256": actual["adjudication_sha256"],
        "group_count": len(actual["groups"]),
        "config_only_correctness_baseline_count": actual[
            "materialization_boundary"
        ]["config_only_correctness_baseline_count"],
    }


def write_adjudication(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    value = build_adjudication(root)
    contract_path = root / CONTRACT_REL
    artifact_root = root / ARTIFACT_REL
    artifact_root.mkdir(parents=True, exist_ok=True)
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    contract_path.write_text(payload, encoding="utf-8", newline="\n")
    validation = validate_adjudication(root, _load(contract_path))
    validation_path = artifact_root / "validation_report.json"
    validation_path.write_text(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    receipt: dict[str, Any] = {
        "schema": "requant-config-only-bypass-generation-receipt-v1",
        "contract": _file_receipt(root, CONTRACT_REL, "adjudication_contract"),
        "validation_report": _file_receipt(
            root,
            validation_path.relative_to(root),
            "adjudication_validation",
        ),
        "plan_provenance": _file_receipt(
            root, Path(".agents/plan.md"), "mutable_provenance_only"
        ),
        "plan_current_match_is_not_a_semantic_gate": True,
        "server_actions": "NONE",
    }
    receipt["receipt_sha256"] = _sha256_bytes(_canonical_bytes(receipt))
    receipt_path = artifact_root / "generation_receipt.json"
    receipt_path.write_text(
        json.dumps(
            receipt,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "status": value["status"],
        "contract_path": str(contract_path),
        "contract_file_sha256": _sha256_file(contract_path),
        "adjudication_sha256": value["adjudication_sha256"],
        "validation_report_path": str(validation_path),
        "generation_receipt_path": str(receipt_path),
        "generation_receipt_file_sha256": _sha256_file(receipt_path),
        "config_only_correctness_baseline_count": 0,
        "package_release": False,
    }


__all__ = [
    "ACTIVE_RULE_SHA256",
    "ARTIFACT_REL",
    "BYPASS_FIELDS",
    "CAPABILITY_REL",
    "CONTRACT_REL",
    "EVIDENCE_REL",
    "ROUNDING_DISCRIMINATOR_REL",
    "ROUNDING_MAINLINE_RECORD_REL",
    "RequantConfigOnlyBypassError",
    "build_adjudication",
    "validate_adjudication",
    "write_adjudication",
]
