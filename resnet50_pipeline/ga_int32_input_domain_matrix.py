from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .r5_lowering_bundle import validate_r5_lowering_bundle
from .stage_operator_semantics_audit import (
    ga_int32_to_fp32_rtl_trace,
)
from .w5_conv_preflight import _load_npy


SCHEMA = "resnet50-ga-int32-input-domain-matrix-v1"
CONTRACT_PATH = (
    "contracts/operator_config/ga_int32_input_domain_matrix_v1.json"
)
LOWERING_PATH = "contracts/resnet50_r5_lowering_bundle.json"
SUBOP_PATH = "artifacts/w3/subop_batch16/manifest.json"
AUDIT_PATH = (
    "contracts/operator_config/stage_operator_semantics_audit_v1.json"
)
REQUANT_EVIDENCE_PATH = (
    "contracts/operator_config/node0004_requant_semantics_evidence_v1.json"
)
INT32_GA_FAMILIES = {"RequantizeUint8", "AverageRequantizeUint8"}
DOMAIN_BLOCKER = "B_GA_INT32TOFP32_INPUT_DOMAIN"


class GAInt32InputDomainMatrixError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GAInt32InputDomainMatrixError(
            f"cannot load GA input-domain JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise GAInt32InputDomainMatrixError(
            f"GA input-domain JSON root must be an object: {path}"
        )
    return value


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise GAInt32InputDomainMatrixError(
            f"required GA input-domain input is missing: {relative}"
        )
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def build_ga_int32_input_domain_matrix(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    lowering = _load(root / LOWERING_PATH)
    subop = _load(root / SUBOP_PATH)
    audit = _load(root / AUDIT_PATH)
    requant = _load(root / REQUANT_EVIDENCE_PATH)
    validate_r5_lowering_bundle(lowering, root)

    findings = {
        str(item.get("issue_id")): item
        for item in audit.get("findings", [])
        if isinstance(item, Mapping)
    }
    conversion_finding = findings.get("CDA-GA-INPORT-CONVERT-001")
    if (
        not isinstance(conversion_finding, Mapping)
        or conversion_finding.get("classification") != "CONTRADICTED"
        or len(conversion_finding.get("counterexamples", [])) != 2
    ):
        raise GAInt32InputDomainMatrixError(
            "GA INT32 conversion audit finding differs"
        )

    resolutions = {
        str(item["request_id"]): item
        for item in lowering.get("effective_resolutions", [])
        if isinstance(item, Mapping)
    }
    requests = [
        item
        for item in lowering.get("requests", [])
        if isinstance(item, Mapping)
        and item.get("identity", {}).get("hw_op_type")
        in INT32_GA_FAMILIES
    ]
    if (
        len(requests) != 55
        or sum(
            item["identity"]["hw_op_type"] == "RequantizeUint8"
            for item in requests
        )
        != 54
        or sum(
            item["identity"]["hw_op_type"] == "AverageRequantizeUint8"
            for item in requests
        )
        != 1
    ):
        raise GAInt32InputDomainMatrixError(
            "GA INT32 conversion stage inventory differs"
        )

    tensors = subop.get("internal_tensors")
    if not isinstance(tensors, Mapping):
        raise GAInt32InputDomainMatrixError(
            "W3 internal tensor manifest is missing"
        )
    records: list[dict[str, Any]] = []
    for request in requests:
        request_id = str(request["request_id"])
        resolution = resolutions.get(request_id)
        if (
            not isinstance(resolution, Mapping)
            or DOMAIN_BLOCKER
            not in resolution.get("effective_blockers", [])
        ):
            raise GAInt32InputDomainMatrixError(
                f"GA input-domain blocker missing: {request_id}"
            )
        ports = request.get("ports", {}).get("inputs", [])
        if not isinstance(ports, list) or not ports:
            raise GAInt32InputDomainMatrixError(
                f"GA INT32 input port missing: {request_id}"
            )
        port = ports[0]
        tensor_id = str(port.get("tensor_id"))
        tensor_record = tensors.get(tensor_id)
        if (
            not isinstance(tensor_record, dict)
            or port.get("dtype") != "int32"
            or tensor_record.get("dtype") != "int32"
            or port.get("shape") != tensor_record.get("shape")
            or port.get("identity_sha256") != tensor_record.get("sha256")
        ):
            raise GAInt32InputDomainMatrixError(
                f"typed/W3 GA INT32 tensor identity differs: {request_id}"
            )
        value = _load_npy(
            root / "artifacts/w3/subop_batch16",
            subop,
            tensor_record,
        )
        minus_one_count = int(np.count_nonzero(value == -1))
        int_min_count = int(
            np.count_nonzero(value == np.iinfo(np.int32).min)
        )
        counterexample_count = minus_one_count + int_min_count
        records.append(
            {
                "ordinal": request["ordinal"],
                "request_id": request_id,
                "node_id": request["identity"]["node_id"],
                "hw_op_type": request["identity"]["hw_op_type"],
                "request_sha256": request["request_sha256"],
                "tensor_id": tensor_id,
                "tensor_sha256": tensor_record["sha256"],
                "shape": tensor_record["shape"],
                "element_count": int(value.size),
                "minimum": int(value.min()),
                "maximum": int(value.max()),
                "negative_count": int(np.count_nonzero(value < 0)),
                "zero_count": int(np.count_nonzero(value == 0)),
                "minus_one_count": minus_one_count,
                "int_min_count": int_min_count,
                "known_counterexample_element_count": counterexample_count,
                "exact_w3_hits_known_counterexample": (
                    counterexample_count > 0
                ),
                "exact_w3_conversion_disposition": (
                    "incompatible_known_counterexample_observed"
                    if counterexample_count
                    else "two_known_counterexamples_absent_not_general_proof"
                ),
                "rtl_semantics_compatible": False,
                "retained_blocker": DOMAIN_BLOCKER,
            }
        )

    node0004 = next(
        item for item in records if item["request_id"] == "r5:hwop-0004-01"
    )
    representative_domain = requant.get("bit_accurate_rtl_replay", {}).get(
        "accumulator_domain", {}
    )
    if (
        node0004["element_count"] != representative_domain.get(
            "element_count"
        )
        or node0004["minimum"] != representative_domain.get("minimum")
        or node0004["maximum"] != representative_domain.get("maximum")
        or node0004["minus_one_count"]
        != representative_domain.get("minus_one_count")
        or node0004["int_min_count"]
        != representative_domain.get("int_min_count")
    ):
        raise GAInt32InputDomainMatrixError(
            "node-0004 representative replay and all-stage matrix differ"
        )

    hit_records = [
        item for item in records if item["exact_w3_hits_known_counterexample"]
    ]
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": (
            "all_int32_ga_stage_inputs_inventoried_"
            "known_counterexamples_block_release"
        ),
        "inputs": {
            "lowering_bundle": _binding(root, LOWERING_PATH),
            "subop_golden": _binding(root, SUBOP_PATH),
            "stage_operator_semantics_audit": _binding(root, AUDIT_PATH),
            "node0004_requant_replay": _binding(
                root, REQUANT_EVIDENCE_PATH
            ),
        },
        "rtl_conversion": {
            "finding_id": "CDA-GA-INPORT-CONVERT-001",
            "classification": "CONTRADICTED",
            "known_counterexamples": [
                {
                    "value": -1,
                    "input_bits": "0xffffffff",
                    "rtl_trace": ga_int32_to_fp32_rtl_trace(-1),
                    "expected_fp32_bits": "0xbf800000",
                },
                {
                    "value": -2_147_483_648,
                    "input_bits": "0x80000000",
                    "rtl_trace": ga_int32_to_fp32_rtl_trace(
                        -2_147_483_648
                    ),
                    "expected_fp32_bits": "0xcf000000",
                },
            ],
            "release_policy": (
                "an observed counterexample is an exact incompatibility; "
                "absence of the two known counterexamples in one W3 tensor "
                "is not a proof over the stage input domain"
            ),
        },
        "summary": {
            "stage_count": len(records),
            "requant_stage_count": sum(
                item["hw_op_type"] == "RequantizeUint8"
                for item in records
            ),
            "average_requant_stage_count": sum(
                item["hw_op_type"] == "AverageRequantizeUint8"
                for item in records
            ),
            "total_element_count": sum(
                item["element_count"] for item in records
            ),
            "known_counterexample_hit_stage_count": len(hit_records),
            "known_counterexample_avoiding_stage_count": (
                len(records) - len(hit_records)
            ),
            "minus_one_element_count": sum(
                item["minus_one_count"] for item in records
            ),
            "int_min_element_count": sum(
                item["int_min_count"] for item in records
            ),
            "rtl_compatible_stage_count": 0,
            "retained_blocker": DOMAIN_BLOCKER,
        },
        "stages": records,
        "release": {
            "candidate_stage_count": 0,
            "blocker_retained_for_all_55_stages": True,
            "reason": (
                "some exact W3 inputs hit the proven RTL defect, and W3 "
                "avoidance alone cannot establish a general signed int32 "
                "conversion domain for the remaining stages"
            ),
        },
    }
    payload["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(payload)
    )
    return payload


def validate_ga_int32_input_domain_matrix(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_ga_int32_input_domain_matrix(project_root)
    if value != expected:
        raise GAInt32InputDomainMatrixError(
            "GA INT32 input-domain matrix differs from hash-bound inputs"
        )


def write_ga_int32_input_domain_matrix(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CONTRACT_PATH",
    "GAInt32InputDomainMatrixError",
    "SCHEMA",
    "build_ga_int32_input_domain_matrix",
    "validate_ga_int32_input_domain_matrix",
    "write_ga_int32_input_domain_matrix",
]
