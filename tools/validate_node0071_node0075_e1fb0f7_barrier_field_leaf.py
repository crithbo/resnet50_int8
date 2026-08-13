#!/usr/bin/env python3
"""Independently validate the e1fb0f7 producer-barrier field leaf."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from build_node0071_node0075_e1fb0f7_barrier_field_leaf import (
    CONTRACT,
    REPORT,
    ROOT,
    BarrierAuditError,
    audit_barrier_field,
    build_report,
    canonical_json,
)

VALIDATION = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-barrier-field-leaf-v1/validation.json"
)


class ValidationError(RuntimeError):
    """Fail-closed validation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_candidate(candidate: dict[str, Any]) -> None:
    require(
        candidate["status"] == "HARDWARE_FIELD_LEAF_UNEXPRESSIBLE",
        "status differs",
    )
    require(candidate["package_release"] == "NONE", "package release differs")
    require(candidate["candidate_release"] is False, "candidate release differs")
    require(
        candidate["hardware_field_audit"][
            "declared_but_live_semantics_absent"
        ]
        is True,
        "live barrier semantics cannot be claimed",
    )
    require(
        all(
            candidate["hardware_field_audit"]["absence_checks"].values()
        ),
        "barrier absence closure differs",
    )
    decision = candidate["generation_decision"]
    require(
        not any(
            value
            for key, value in decision.items()
            if key.endswith("_generated")
        ),
        "downstream generation must stop",
    )
    require(
        candidate["node0075_existing_local_e2"]["configured_reload_passes"]
        == 8,
        "configured reload count differs",
    )
    require(
        candidate["node0075_existing_local_e2"][
            "configured_32byte_read_occurrences"
        ]
        == 8192,
        "configured read occurrences differ",
    )
    require(
        candidate["node0075_existing_local_e2"][
            "configured_a_traffic_bytes"
        ]
        == 262144,
        "configured A traffic differs",
    )
    require(
        candidate["node0075_existing_local_e2"]["runtime_accepted_reads"]
        is None,
        "unrun acceptance cannot be invented",
    )
    require(
        candidate["current_node0071_read_only_inputs"]["execplan"][
            "barrier_command_count"
        ]
        == 8,
        "node0071 barrier command count differs",
    )
    require(
        candidate["current_node0071_read_only_inputs"]["dynamic_current_return"][
            "natural_terminal"
        ]
        is False,
        "current node0071 return cannot be promoted",
    )
    require(
        candidate["rule_feedback"]["type"] == "RULE_DELTA_PROPOSAL",
        "rule feedback differs",
    )


def expect_rejected(candidate: dict[str, Any], mutation: str) -> None:
    try:
        validate_candidate(candidate)
    except (KeyError, TypeError, ValidationError):
        return
    raise ValidationError(f"negative control escaped: {mutation}")


def main() -> None:
    expected = build_report()
    expected_payload = canonical_json(expected)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    require(CONTRACT.read_bytes() == expected_payload, "contract is not current")
    require(REPORT.read_bytes() == expected_payload, "report is not current")
    require(CONTRACT.read_bytes() == REPORT.read_bytes(), "twins differ")
    validate_candidate(contract)
    audit_barrier_field()

    mutations: list[tuple[str, dict[str, Any]]] = []

    candidate = copy.deepcopy(contract)
    candidate["package_release"] = "PACKAGE_READY_NOT_RUN"
    mutations.append(("package promotion", candidate))

    candidate = copy.deepcopy(contract)
    candidate["hardware_field_audit"][
        "declared_but_live_semantics_absent"
    ] = False
    mutations.append(("barrier live-semantics promotion", candidate))

    candidate = copy.deepcopy(contract)
    candidate["hardware_field_audit"]["absence_checks"][
        "barrier_valid_decode_absent"
    ] = False
    mutations.append(("undecoded opcode accepted", candidate))

    candidate = copy.deepcopy(contract)
    candidate["generation_decision"]["integration_target_generated"] = True
    mutations.append(("generation beyond first leaf", candidate))

    candidate = copy.deepcopy(contract)
    candidate["node0075_existing_local_e2"]["runtime_accepted_reads"] = 8192
    mutations.append(("configured traffic promoted to runtime acceptance", candidate))

    candidate = copy.deepcopy(contract)
    candidate["current_node0071_read_only_inputs"]["dynamic_current_return"][
        "natural_terminal"
    ] = True
    mutations.append(("failed node0071 return promoted", candidate))

    candidate = copy.deepcopy(contract)
    candidate["rule_feedback"]["type"] = "RULE_CONFIRMATION"
    mutations.append(("non-synonymous rule gap suppressed", candidate))

    for name, candidate in mutations:
        expect_rejected(candidate, name)

    result = {
        "schema": "node0071-node0075-e1fb0f7-barrier-field-validation-v1",
        "status": "INDEPENDENT_BARRIER_FIELD_LEAF_VALIDATION_PASS",
        "errors": 0,
        "negative_controls": len(mutations),
        "contract": str(CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "contract_sha256": sha256_file(CONTRACT),
        "report": str(REPORT.relative_to(ROOT)).replace("\\", "/"),
        "report_sha256": sha256_file(REPORT),
        "package_release": "NONE",
    }
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION.write_bytes(canonical_json(result))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (BarrierAuditError, ValidationError) as exc:
        raise SystemExit(str(exc)) from exc
