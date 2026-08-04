#!/usr/bin/env python3
"""Event-qualified runtime overlay for the Requant guard-only SFU diagnostic."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

try:
    import requant_atomic_server_runtime_base as base  # noqa: E402
except ModuleNotFoundError:  # Local tests; packaged runtime uses the alias above.
    from tools import requant_atomic_server_runtime as base  # type: ignore[no-redef]  # noqa: E402


EVENT_SUBMODE = "sfu_eventedge_coeff_to_outbuffer"
CONTROL_REPORT_SHA256 = (
    "894b01355a888316a9f9475e38cfb2a565689895ba842955e31cc187dd3f8f6a"
)
SHARED_CONTROL_EVIDENCE = {
    "rule_id": "CDA-REQUANT-NATIVE-SILU-CONTROL-V1-DYNAMIC-EVIDENCE-001",
    "report_sha256": CONTROL_REPORT_SHA256,
    "classification": (
        "SHARED_SFU_NUMERIC_NORMAL_OUTBUFFER_MSE4_PAYLOAD_PASS__"
        "D_OCCURRENCE_ADDRESS_COVERAGE_FAIL"
    ),
    "common_sfu_normal_outbuffer_path_operational": True,
    "excludes_universal_common_sfu_or_normal_outbuffer_failure": True,
    "does_not_prove_requant_specific_configuration_consumption": True,
}
EVENT_BOUNDARIES = (
    "SFU_COEFF_SRAM_AT_ALU_CAPTURE",
    "SFU_ALU_PIPELINE0_ACCEPT",
    "SFU_ALU_RESULT_PRODUCED",
    "SFU_POSTPROCESS_RESULT_AT_OUTBUFFER_ACCEPT",
    "NORMAL_OUTBUFFER_WRITE_COMMIT",
    "NORMAL_OUTPORT_ACCEPTED",
    "MSE4_REQ",
    "MSE4_WDATA",
)
PAYLOAD_FIELDS = {
    "SFU_COEFF_SRAM_AT_ALU_CAPTURE": (
        "coeff_addr",
        "slope",
        "intercept",
        "data",
    ),
    "SFU_ALU_PIPELINE0_ACCEPT": (
        "tag",
        "data0",
        "data1",
        "data2",
        "data",
    ),
    "SFU_ALU_RESULT_PRODUCED": ("tag", "data"),
    "SFU_POSTPROCESS_RESULT_AT_OUTBUFFER_ACCEPT": (
        "tag",
        "alu_data",
        "data",
    ),
    "NORMAL_OUTBUFFER_WRITE_COMMIT": ("tag", "data"),
    "NORMAL_OUTPORT_ACCEPTED": ("tag", "data"),
    "MSE4_REQ": ("transfer_addr", "linear_addr", "post_remap_addr"),
    "MSE4_WDATA": ("data",),
}
HEX_VALUE = re.compile(r"0x[0-9a-fA-F]+$")
DECIMAL_VALUE = re.compile(r"-?[0-9]+$")
XZ_VALUE = re.compile(r"[xXzZ]")


def _fields(line: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for token in line.split():
        if "=" in token:
            key, value = token.split("=", 1)
            parsed[key] = value
    return parsed


def _integer(value: str) -> int:
    return int(value, 16) if value.lower().startswith("0x") else int(value, 10)


def _contains_x_or_z(value: str) -> bool:
    payload = value[2:] if value.lower().startswith("0x") else value
    return XZ_VALUE.search(payload) is not None


def _transaction_key(
    boundary: str, fields: dict[str, str]
) -> tuple[int, str, int]:
    slice_id = int(fields["slice"])
    if boundary in {"MSE4_REQ", "MSE4_WDATA"}:
        identity = f"ch{fields['ch']}"
    else:
        identity = f"pe{fields['pe']}"
    return slice_id, identity, int(fields["txn_id"])


def _empty_metric(expected: int) -> dict[str, Any]:
    return {
        "expected_qualified_event_count": expected,
        "raw_total": 0,
        "qualified_event_count": 0,
        "parseable_count": 0,
        "x_or_z_or_pre_valid_count": 0,
        "duplicate_sample_count": 0,
        "raw_unqualified_count": 0,
        "zero_payload_count": 0,
        "nonzero_payload_count": 0,
        "exact_qualified_coverage": False,
        "first_samples": [],
    }


def _semantic_checks(
    records: dict[str, dict[tuple[int, str, int], dict[str, str]]]
) -> dict[str, Any]:
    coeff = records["SFU_COEFF_SRAM_AT_ALU_CAPTURE"]
    alu_input = records["SFU_ALU_PIPELINE0_ACCEPT"]
    alu_result = records["SFU_ALU_RESULT_PRODUCED"]
    postprocess = records["SFU_POSTPROCESS_RESULT_AT_OUTBUFFER_ACCEPT"]
    outbuffer = records["NORMAL_OUTBUFFER_WRITE_COMMIT"]
    outport = records["NORMAL_OUTPORT_ACCEPTED"]

    coefficient_address_mismatch = 0
    coefficient_payload_mismatch = 0
    alu_input_mismatch = 0
    alu_result_mismatch = 0
    postprocess_mismatch = 0
    outbuffer_mismatch = 0
    outport_mismatch = 0
    checked = set(coeff) | set(alu_input) | set(alu_result) | set(postprocess) | set(
        outbuffer
    )
    checked |= set(outport)
    first_mismatches: list[dict[str, Any]] = []

    def mismatch(kind: str, key: tuple[int, str, int], **values: Any) -> None:
        if len(first_mismatches) < 16:
            first_mismatches.append(
                {
                    "kind": kind,
                    "slice": key[0],
                    "consumer": key[1],
                    "transaction_id": key[2],
                    **values,
                }
            )

    for key in sorted(checked):
        coeff_item = coeff.get(key)
        input_item = alu_input.get(key)
        result_item = alu_result.get(key)
        post_item = postprocess.get(key)
        outbuffer_item = outbuffer.get(key)
        outport_item = outport.get(key)
        expected_alu: int | None = None

        if coeff_item is not None:
            address = _integer(coeff_item["coeff_addr"])
            slope = _integer(coeff_item["slope"])
            intercept = _integer(coeff_item["intercept"])
            if address not in {0x00, 0x41}:
                coefficient_address_mismatch += 1
                mismatch(
                    "coefficient_address",
                    key,
                    actual=f"0x{address:02x}",
                    expected="0x00_or_0x41",
                )
            expected_slope = 0x3F800000 if address == 0x41 else 0
            if slope != expected_slope or intercept != 0:
                coefficient_payload_mismatch += 1
                mismatch(
                    "coefficient_payload",
                    key,
                    address=f"0x{address:02x}",
                    actual_slope=f"0x{slope:08x}",
                    expected_slope=f"0x{expected_slope:08x}",
                    actual_intercept=f"0x{intercept:08x}",
                    expected_intercept="0x00000000",
                )

        if coeff_item is not None and input_item is not None:
            expected_inputs = (
                _integer(coeff_item["data"]),
                _integer(coeff_item["slope"]),
                _integer(coeff_item["intercept"]),
            )
            actual_inputs = (
                _integer(input_item["data0"]),
                _integer(input_item["data1"]),
                _integer(input_item["data2"]),
            )
            if actual_inputs != expected_inputs:
                alu_input_mismatch += 1
                mismatch(
                    "alu_pipeline0_input",
                    key,
                    actual=[f"0x{value:08x}" for value in actual_inputs],
                    expected=[f"0x{value:08x}" for value in expected_inputs],
                )
            slope = expected_inputs[1]
            intercept = expected_inputs[2]
            if slope == 0 and intercept == 0:
                expected_alu = 0
            elif slope == 0x3F800000 and intercept == 0:
                expected_alu = expected_inputs[0]

        if result_item is not None and expected_alu is not None:
            actual = _integer(result_item["data"])
            if actual != expected_alu:
                alu_result_mismatch += 1
                mismatch(
                    "alu_result",
                    key,
                    actual=f"0x{actual:08x}",
                    expected=f"0x{expected_alu:08x}",
                )

        if post_item is not None and result_item is not None:
            actual = _integer(post_item["data"])
            expected = _integer(result_item["data"])
            if actual != expected or _integer(post_item["alu_data"]) != expected:
                postprocess_mismatch += 1
                mismatch(
                    "postprocess",
                    key,
                    actual=f"0x{actual:08x}",
                    expected=f"0x{expected:08x}",
                )

        if outbuffer_item is not None and post_item is not None:
            actual = _integer(outbuffer_item["data"])
            expected = _integer(post_item["data"])
            if actual != expected:
                outbuffer_mismatch += 1
                mismatch(
                    "normal_outbuffer_write",
                    key,
                    actual=f"0x{actual:08x}",
                    expected=f"0x{expected:08x}",
                )

        if outport_item is not None and outbuffer_item is not None:
            actual = _integer(outport_item["data"])
            expected = _integer(outbuffer_item["data"])
            if actual != expected:
                outport_mismatch += 1
                mismatch(
                    "normal_outport",
                    key,
                    actual=f"0x{actual:08x}",
                    expected=f"0x{expected:08x}",
                )

    complete_key_coverage = {
        boundary: len(records[boundary]) for boundary in EVENT_BOUNDARIES
    }
    return {
        "transaction_key": "slice+physical_PE_or_channel+per_boundary_transaction_id",
        "guard_coefficient_contract": {
            "address_0": {
                "slope": "0x00000000",
                "intercept": "0x00000000",
            },
            "address_0x41": {
                "slope": "0x3f800000",
                "intercept": "0x00000000",
            },
        },
        "complete_key_coverage": complete_key_coverage,
        "coefficient_address_mismatch_count": coefficient_address_mismatch,
        "coefficient_payload_mismatch_count": coefficient_payload_mismatch,
        "alu_pipeline0_input_mismatch_count": alu_input_mismatch,
        "alu_result_mismatch_count": alu_result_mismatch,
        "postprocess_mismatch_count": postprocess_mismatch,
        "normal_outbuffer_mismatch_count": outbuffer_mismatch,
        "normal_outport_mismatch_count": outport_mismatch,
        "first_mismatches": first_mismatches,
    }


def event_checkpoint_gate(
    run_dir: Path, profile: dict[str, Any]
) -> dict[str, Any]:
    expected = {
        str(name): int(count)
        for name, count in profile["checkpoint_expected_counts"].items()
    }
    metrics = {name: _empty_metric(expected[name]) for name in EVENT_BOUNDARIES}
    records: dict[str, dict[tuple[int, str, int], dict[str, str]]] = {
        name: {} for name in EVENT_BOUNDARIES
    }
    errors: list[str] = []

    for slice_id in base.ACTIVE_SLICES:
        path = (
            run_dir.resolve()
            / "sim_results"
            / str(profile["observer_log_dir"])
            / f"slice{slice_id:02d}.log"
        )
        if not path.is_file():
            errors.append(f"missing event-qualified observer log slice{slice_id}")
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "GUARD_PATH" not in line:
                continue
            fields = _fields(line)
            boundary = fields.get("boundary")
            if boundary not in metrics:
                continue
            metric = metrics[boundary]
            metric["raw_total"] += 1
            if fields.get("event") != "qualified":
                metric["raw_unqualified_count"] += 1
                if fields.get("pre_valid") == "1" or any(
                    _contains_x_or_z(value) for value in fields.values()
                ):
                    metric["x_or_z_or_pre_valid_count"] += 1
                continue
            metric["qualified_event_count"] += 1
            required = {"slice", "txn_id", *PAYLOAD_FIELDS[boundary]}
            required.add("ch" if boundary in {"MSE4_REQ", "MSE4_WDATA"} else "pe")
            missing = sorted(required - fields.keys())
            if missing:
                errors.append(f"{boundary} missing fields {missing}: {line[-320:]}")
                continue
            if fields["slice"] != str(slice_id):
                errors.append(f"{boundary} slice identity differs: {line[-320:]}")
                continue
            values = [fields[name] for name in PAYLOAD_FIELDS[boundary]]
            if any(_contains_x_or_z(value) for value in values):
                metric["x_or_z_or_pre_valid_count"] += 1
                continue
            malformed = [
                name
                for name in PAYLOAD_FIELDS[boundary]
                if HEX_VALUE.fullmatch(fields[name]) is None
            ]
            if (
                malformed
                or DECIMAL_VALUE.fullmatch(fields["txn_id"]) is None
                or (
                    boundary in {"MSE4_REQ", "MSE4_WDATA"}
                    and DECIMAL_VALUE.fullmatch(fields["ch"]) is None
                )
            ):
                errors.append(
                    f"{boundary} malformed event fields {malformed}: {line[-320:]}"
                )
                continue
            key = _transaction_key(boundary, fields)
            if key in records[boundary]:
                metric["duplicate_sample_count"] += 1
                continue
            records[boundary][key] = fields
            metric["parseable_count"] += 1
            data = fields.get("data")
            if data is not None:
                if _integer(data) == 0:
                    metric["zero_payload_count"] += 1
                else:
                    metric["nonzero_payload_count"] += 1
            if len(metric["first_samples"]) < 8:
                metric["first_samples"].append(fields)

    for boundary, metric in metrics.items():
        metric["exact_qualified_coverage"] = (
            metric["qualified_event_count"]
            == metric["expected_qualified_event_count"]
            and metric["parseable_count"] == metric["qualified_event_count"]
            and metric["x_or_z_or_pre_valid_count"] == 0
            and metric["duplicate_sample_count"] == 0
        )
    passed = not errors and all(
        metric["exact_qualified_coverage"] for metric in metrics.values()
    )
    semantic = _semantic_checks(records)
    return {
        "status": "pass" if passed else "fail",
        "schema": "requant-guard-event-qualified-checkpoint-receipt-v1",
        "rule_ids": [
            "CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
            "CDA-REQUANT-GUARD-CHECKPOINT-ROUTING-001",
            "CDA-REQUANT-NATIVE-SILU-CONTROL-V1-DYNAMIC-EVIDENCE-001",
        ],
        "evidence_kind": "qualified_consumer_capture_and_handshake_payload_events",
        "level_qualifier_count_used_as_transaction_count": False,
        "only_qualified_events_affect_first_divergence": True,
        "count_checks": metrics,
        "semantic_checks": semantic,
        "shared_native_silu_control_evidence": SHARED_CONTROL_EVIDENCE,
        "errors": errors[:32],
    }


def event_first_divergence(
    simulation: dict[str, Any],
    lifecycle: dict[str, Any],
    checkpoints: dict[str, Any],
    observer: dict[str, Any],
    formal: dict[str, Any],
) -> dict[str, Any]:
    unresolved = [
        "REQUANT_SPECIFIC_CONFIG_CONSUMPTION_OR_SELECTION",
        "REQUANT_MODE_SPECIFIC_RTL_CONTROL",
        "OBSERVER_EVIDENCE",
    ]

    def route(
        classification: str,
        first_divergence: str | None,
        level: int | None,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "classification": classification,
            "first_divergence": first_divergence,
            "four_level_route": level,
            "enable_only": None if first_divergence is None else "guard-only",
            "responsibility_unresolved": [] if first_divergence is None else unresolved,
            "shared_native_silu_control_evidence": SHARED_CONTROL_EVIDENCE,
            **extra,
        }

    if simulation["status"] != "pass" or lifecycle["status"] != "pass":
        return route(
            "SERVER_INFRASTRUCTURE_OR_GUARD_LIFECYCLE_FAILURE",
            "guard-only simulation/lifecycle did not complete naturally",
            None,
        )
    if checkpoints["status"] != "pass":
        return route(
            "OBSERVER_EVENT_QUALIFICATION_INCOMPLETE",
            "qualified-event count, parseability, X/Z, or duplicate gate failed",
            None,
            event_count_receipt=checkpoints["count_checks"],
        )
    semantic = checkpoints["semantic_checks"]
    if semantic["coefficient_address_mismatch_count"]:
        return route(
            "SFU_COEFFICIENT_ADDRESS_EVENT_DIVERGENCE",
            "event-qualified coefficient address differs from the proven 0x00/0x41 contract",
            1,
        )
    if semantic["coefficient_payload_mismatch_count"]:
        return route(
            "SFU_LUT_SELECTED_COEFFICIENT_PAYLOAD_DIVERGENCE",
            "coefficient address is valid but selected slope/intercept payload differs",
            1,
        )
    if semantic["alu_pipeline0_input_mismatch_count"]:
        return route(
            "SFU_COEFFICIENT_TO_ALU_CAPTURE_DIVERGENCE",
            "selected coefficient and preprocess payload do not reach ALU pipeline0 unchanged",
            2,
        )
    if semantic["alu_result_mismatch_count"]:
        return route(
            "SFU_ALU_RESULT_DIVERGENCE_AFTER_CORRECT_CAPTURE",
            "coefficient and ALU inputs are correct but the accepted ALU result differs",
            2,
        )
    if semantic["postprocess_mismatch_count"] or semantic[
        "normal_outbuffer_mismatch_count"
    ]:
        return route(
            "SFU_POSTPROCESS_OR_NORMAL_OUTBUFFER_DIVERGENCE",
            "ALU result is correct but postprocess/outbuffer accepted payload differs",
            3,
        )
    if semantic["normal_outport_mismatch_count"]:
        return route(
            "NORMAL_OUTBUFFER_TO_OUTPORT_DIVERGENCE",
            "normal outbuffer write is correct but accepted normal outport payload differs",
            4,
        )
    if observer["status"] != "pass" or formal["status"] != "pass":
        return route(
            "NORMAL_OUTBUFFER_TO_MSE4_OR_FORMAL_D_DIVERGENCE",
            "event-qualified outbuffer path is correct but MSE4/formal D gate differs",
            4,
        )
    return route("GUARD_ONLY_DIAGNOSTIC_PASS", None, None)


_original_checkpoint_gate = base._guard_checkpoint_gate
_original_first_divergence = base._guard_only_first_divergence
_original_analyze = base.analyze


def _checkpoint_dispatch(
    run_dir: Path, profile: dict[str, Any]
) -> dict[str, Any]:
    if profile.get("diagnostic_submode") == EVENT_SUBMODE:
        return event_checkpoint_gate(run_dir, profile)
    return _original_checkpoint_gate(run_dir, profile)


def _divergence_dispatch(
    simulation: dict[str, Any],
    lifecycle: dict[str, Any],
    checkpoints: dict[str, Any],
    observer: dict[str, Any],
    formal: dict[str, Any],
    checkpoint_order: list[str] | tuple[str, ...] | None = None,
    diagnostic_submode: str | None = None,
) -> dict[str, Any]:
    if diagnostic_submode == EVENT_SUBMODE:
        return event_first_divergence(
            simulation, lifecycle, checkpoints, observer, formal
        )
    return _original_first_divergence(
        simulation,
        lifecycle,
        checkpoints,
        observer,
        formal,
        checkpoint_order,
        diagnostic_submode,
    )


def _analyze_dispatch(*args: Any, **kwargs: Any) -> dict[str, Any]:
    report = _original_analyze(*args, **kwargs)
    package_root = Path(args[0] if args else kwargs["package_root"])
    profile = base._runtime_profile(package_root.resolve())
    if profile.get("diagnostic_submode") == EVENT_SUBMODE:
        routing = report["first_divergence_routing"]
        if routing.get("classification") != "GUARD_ONLY_DIAGNOSTIC_PASS":
            report["status"] = "GUARD_ONLY_DIAGNOSTIC_FAIL_OR_INCOMPLETE"
            report["classification"] = "FIRST_DYNAMIC_FAILURE"
            report["release_gate_passed"] = False
    return report


base._guard_checkpoint_gate = _checkpoint_dispatch
base._guard_only_first_divergence = _divergence_dispatch
base.analyze = _analyze_dispatch


if __name__ == "__main__":
    raise SystemExit(base.main())
