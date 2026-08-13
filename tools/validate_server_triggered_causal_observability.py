#!/usr/bin/env python3
"""Validate always-on triggered causal observability designs.

This tool validates design contracts for *future fresh successors*.  It does
not open, rebuild, or modify current server packages and it does not execute a
simulator.  Exact final-HDL binding remains a family final-ZIP responsibility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = (
    ROOT / "contracts/server_triggered_causal_observability_registry_v1.json"
)
DEFAULT_PROFILES = (
    ROOT
    / "contracts/server_triggered_causal_observability_current_five_v1.json"
)

RULE_ID = "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001"
BUDGET_RULE_ID = (
    "CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001"
)
LOGGER_PARSER_RULE_ID = (
    "CDA-SERVER-DIAGNOSTIC-LOGGER-PARSER-EXACT-FORMAT-TRACE-001"
)
MULTICLASS_EDGE_RULE_ID = (
    "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001"
)
GAP_V50_SOURCE_SHA256 = (
    "96c23c3762b9fca323ff3d76250f8ca9482c74d536a93b843321c8be3f37252d"
)
GAP_V50_RETURN_SHA256 = (
    "af493115127b0040d8bec83815d0e00d2fc90a7a9c559b11758ddb42982adfc2"
)
GAP_V53_SOURCE_SHA256 = (
    "5a50594bae06c56040d48637f46709a32dea292d6af925c36b4a235d7a887d8a"
)
GAP_V53_RETURN_SHA256 = (
    "36c04e4e93fd2f608239c634186c895d71a0edbbd697a8294a9678650d712ff4"
)
GAP_V53_ANALYSIS_SHA256 = (
    "8725caca7993485cc38dcf4daa8fcfe5f96cddba284fa1d78a7a81196bde56be"
)
GAP_V53_LOGGER_SHA256 = (
    "aac881fc3d2fee63d5a496e575af7c85e4fa05b70ec622a341a8eece6ad98721"
)
GAP_V53_PARSER_SHA256 = (
    "dac84ee1341694b49c47f0148b9f5d1b0942b6da4796d0506aee3df2e374b94c"
)
GAP_V54_SOURCE_SHA256 = (
    "131e9de37698c8e0470db0c42120c0b2d793c84ce0c2ee62a02eb24cefbd87c9"
)
GAP_V54_RETURN_SHA256 = (
    "5bbe79edd2a8cfcec03b63207920f8c73166dd78fd57066e30360230c9ba9e5b"
)
GAP_V54_ANALYSIS_SHA256 = (
    "ce469ea17b409cae5f8e51eb18db2fd776c4077652ef0ca009fd42474d5640d9"
)
GAP_V54_OBSERVER_SHA256 = (
    "ddc50b15fecb7e2bc04fd51389284978f5d7cc83e6b33c450438aaaee5573f0d"
)
GAP_V54_PARSER_SHA256 = (
    "0434b84c1828a68be36d1734a3bf13b54a3a5e43ef9224113a49a66b313c27d9"
)
APPLICATION_SCOPE = "NEXT_FRESH_SUCCESSOR_ONLY"
DECISION_PRIORITY = "ONE_ROUND_HYPOTHESIS_DISCRIMINATION_FIRST"
OVER_PREFERRED_ACTION = (
    "REPORT_JUSTIFY_AND_OPTIMIZE_WITHOUT_DROPPING_REQUIRED_BOUNDARIES"
)
PREFERRED_SLOWDOWN_PERCENT = 50.0

MECHANISM_IDS = {
    "INFRASTRUCTURE_START_AND_BINDING",
    "SOURCE_TO_QUEUE_CONSERVATION",
    "QUEUE_TO_CONSUMER_DRAIN",
    "SHARED_BRANCH_ACCEPTANCE_SPLIT",
    "INTERNAL_MATCH_OR_COMPUTE",
    "OUTPUT_ACCEPTANCE",
    "TERMINAL_PROPAGATION",
    "FORMAL_D_COLLECTION",
    "NO_PROGRESS_TRIGGER_SNAPSHOT",
    "OBSERVER_OVERHEAD_BUDGET",
    "QUALIFIED_BUDGET_STATE_ISOLATION",
    "SOURCE_BOUND_GENERATED_OBSERVER",
    "CAUSAL_DECISION_MATRIX_UNIQUE",
    "HIGH_INFORMATION_SEPARATE_EVENT_RINGS",
}

CANONICAL_CLASSIFICATIONS = {
    "TEST_INFRASTRUCTURE_FAILURE",
    "SIM_NOT_STARTED",
    "TARGET_STAGE_NOT_REACHED",
    "DYNAMIC_FLOW_CONTROL_STALL",
    "TERMINAL_PROPAGATION_FAILURE",
    "RESULT_COLLECTION_FAILURE",
    "NUMERIC_MISMATCH",
    "NATURAL_SUCCESS",
    "EVIDENCE_INCOMPLETE",
}

REQUIRED_TRIGGERS = {
    "FIRST_QUEUE_FULL",
    "FIRST_BRANCH_DIVERGENCE",
    "NO_PROGRESS_WINDOW",
    "TERMINAL_GAP",
    "STAGE_TRANSITION",
    "EXIT_OR_SIGNAL",
}

CURRENT_FAMILIES = {
    "global_average_pool",
    "conv_int32_accumulate_serialized",
    "qlinearadd",
    "conv_int32_accumulate_native",
    "global_average_pool_to_qlinear_matmul",
}


class ContractError(ValueError):
    """The observability contract cannot be evaluated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {path}")
    return value


def _expect(
    errors: list[str],
    condition: bool,
    message: str,
) -> None:
    if not condition:
        errors.append(message)


def evaluate_calibration(
    *,
    baseline_wall_seconds: float,
    instrumented_wall_seconds: float,
    preferred_max_slowdown_percent: float = PREFERRED_SLOWDOWN_PERCENT,
) -> dict[str, Any]:
    """Return a nonblocking wall-clock calibration classification."""

    if baseline_wall_seconds <= 0:
        raise ContractError("baseline wall seconds must be positive")
    if instrumented_wall_seconds <= 0:
        raise ContractError("instrumented wall seconds must be positive")
    if preferred_max_slowdown_percent <= 0:
        raise ContractError("preferred slowdown percent must be positive")
    slowdown = (
        (instrumented_wall_seconds / baseline_wall_seconds) - 1.0
    ) * 100.0
    status = (
        "WITHIN_PREFERRED"
        if slowdown <= preferred_max_slowdown_percent
        else "ABOVE_PREFERRED_REPORTED"
    )
    return {
        "schema": "server_observer_wallclock_calibration_v1",
        "baseline_wall_seconds": baseline_wall_seconds,
        "instrumented_wall_seconds": instrumented_wall_seconds,
        "slowdown_percent": round(slowdown, 6),
        "preferred_max_slowdown_percent": preferred_max_slowdown_percent,
        "status": status,
        "blocking": false_bool(),
        "action": (
            "ACCEPT_AND_RECORD"
            if status == "WITHIN_PREFERRED"
            else OVER_PREFERRED_ACTION
        ),
        "observation_completeness_must_be_preserved": True,
        "claim_boundary": (
            "Wall-clock cost classification only. The preferred threshold is "
            "not a release hard gate and cannot justify deleting a boundary "
            "required for one-round root-cause discrimination."
        ),
    }


def false_bool() -> bool:
    """Keep the machine report spelling explicit without magic literals."""

    return False


def evaluate_diagnostic_budget_trace(
    fixture: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate whether state churn can consume qualified-event coverage.

    The compact fixture uses event runs rather than materializing thousands of
    repeated state transitions.  Only ``qualified_event`` runs can consume the
    qualified budget.  Heartbeat/state/level runs use the independent
    non-progress budget and may be coalesced after that budget is full.
    """

    errors: list[str] = []
    _expect(
        errors,
        fixture.get("schema") == "server_diagnostic_budget_trace_v1",
        "budget trace schema mismatch",
    )
    accounting_mode = fixture.get("accounting_mode")
    _expect(
        errors,
        accounting_mode == "SEPARATE_QUALIFIED_AND_NON_PROGRESS",
        "budget trace accounting must separate qualified and state records",
    )
    qualified_budget = fixture.get("qualified_event_budget")
    state_budget = fixture.get("non_progress_state_budget")
    _expect(
        errors,
        isinstance(qualified_budget, int) and qualified_budget > 0,
        "qualified_event_budget must be positive",
    )
    _expect(
        errors,
        isinstance(state_budget, int) and state_budget > 0,
        "non_progress_state_budget must be positive",
    )
    event_runs = fixture.get("event_runs")
    _expect(
        errors,
        isinstance(event_runs, list) and bool(event_runs),
        "budget trace event_runs are missing",
    )
    required_late_event = fixture.get("required_late_qualified_event_id")
    _expect(
        errors,
        isinstance(required_late_event, str) and bool(required_late_event),
        "required late qualified event is missing",
    )
    historical = fixture.get("historical_binding")
    if not isinstance(historical, dict):
        errors.append("historical_binding is missing")
        historical = {}
    _expect(
        errors,
        historical.get("family") == "global_average_pool",
        "historical family mismatch",
    )
    _expect(
        errors,
        historical.get("source_package_sha256") == GAP_V50_SOURCE_SHA256,
        "historical GAP v50 source identity mismatch",
    )
    _expect(
        errors,
        historical.get("return_sha256") == GAP_V50_RETURN_SHA256,
        "historical GAP v50 return identity mismatch",
    )
    _expect(
        errors,
        historical.get("observed_v50_limit") == 256,
        "historical GAP v50 diagnostic limit mismatch",
    )
    _expect(
        errors,
        historical.get(
            "first_later_slice_output_after_budget_exhaustion"
        )
        is True,
        "historical later-slice witness is missing",
    )

    qualified_seen = 0
    qualified_retained = 0
    state_seen = 0
    state_retained = 0
    qualified_capacity = (
        qualified_budget
        if isinstance(qualified_budget, int) and qualified_budget > 0
        else 0
    )
    state_capacity = (
        state_budget
        if isinstance(state_budget, int) and state_budget > 0
        else 0
    )
    shared_legacy_capacity = state_capacity
    shared_legacy_retained = 0
    shared_accounting = accounting_mode == "SHARED_LEGACY_COUNTER"
    retained_ids: list[str] = []
    state_budget_exhausted_before_late = False
    if not isinstance(event_runs, list):
        event_runs = []
    for index, run in enumerate(event_runs):
        prefix = f"event_runs[{index}]"
        if not isinstance(run, dict):
            errors.append(f"{prefix} must be an object")
            continue
        kind = run.get("kind")
        repeat = run.get("repeat")
        event_id = run.get("event_id")
        if kind not in {
            "qualified_event",
            "state_transition",
            "heartbeat",
            "level_snapshot",
        }:
            errors.append(f"{prefix}.kind is invalid")
            continue
        if not isinstance(repeat, int) or repeat < 1:
            errors.append(f"{prefix}.repeat must be positive")
            continue
        if not isinstance(event_id, str) or not event_id:
            errors.append(f"{prefix}.event_id is missing")
            continue
        if kind == "qualified_event":
            if state_seen > state_capacity:
                state_budget_exhausted_before_late = True
            qualified_seen += repeat
            available = max(
                (
                    shared_legacy_capacity - shared_legacy_retained
                    if shared_accounting
                    else qualified_capacity - qualified_retained
                ),
                0,
            )
            retained = min(repeat, available)
            qualified_retained += retained
            if shared_accounting:
                shared_legacy_retained += retained
            if retained:
                retained_ids.extend([event_id] * retained)
        else:
            state_seen += repeat
            available = max(
                (
                    shared_legacy_capacity - shared_legacy_retained
                    if shared_accounting
                    else state_capacity - state_retained
                ),
                0,
            )
            retained = min(repeat, available)
            state_retained += retained
            if shared_accounting:
                shared_legacy_retained += retained

    late_event_retained = required_late_event in retained_ids
    _expect(
        errors,
        state_budget_exhausted_before_late,
        "fixture must exhaust the state budget before the late event",
    )
    _expect(
        errors,
        late_event_retained,
        "later qualified target coverage was consumed by state activity",
    )
    return {
        "schema": "server_diagnostic_budget_trace_validation_v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "rule_id": BUDGET_RULE_ID,
        "accounting_mode": accounting_mode,
        "qualified_event_budget": qualified_budget,
        "non_progress_state_budget": state_budget,
        "qualified_seen": qualified_seen,
        "qualified_retained": qualified_retained,
        "state_seen": state_seen,
        "state_retained": state_retained,
        "state_records_coalesced_or_dropped": max(
            state_seen - state_retained, 0
        ),
        "state_budget_exhausted_before_late_event": (
            state_budget_exhausted_before_late
        ),
        "required_late_qualified_event_id": required_late_event,
        "late_qualified_event_retained": late_event_retained,
        "state_activity_consumed_qualified_budget": (
            shared_accounting and not late_event_retained
        ),
        "claim_boundary": (
            "Synthetic diagnostic budget accounting only. It proves that "
            "state/heartbeat churn cannot consume qualified-event retention; "
            "it does not validate exact final HDL or DUT behavior."
        ),
    }


def _render_logger_record(
    *,
    marker: str,
    event: str,
    render_mode: str,
    width: int,
    padding_char: str,
    field_names: list[str],
) -> tuple[str, str]:
    if render_mode == "RIGHT_JUSTIFIED_FIXED_WIDTH":
        event_field = event.rjust(width, padding_char)
    elif render_mode == "UNPADDED":
        event_field = event
    else:
        raise ContractError(f"unknown logger event render mode: {render_mode}")
    fields = " ".join(f"{name}=0x1" for name in field_names)
    return (
        f"0 | {marker} | event={event_field} qn=1 fn=1 "
        f"db_cycle=1 {fields}",
        event_field,
    )


def _prepare_exact_logger_record(
    *,
    raw_record: str,
    exact_event_field: str,
    parser_contract: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Validate the declared logger field and apply only declared padding.

    This deliberately does not call ``strip``.  The producer bytes are first
    compared with the exact logger rendering, then a narrowly declared ASCII
    padding normalization may be applied before the production parser regex.
    """

    prefix = "event="
    suffix = " qn="
    start = raw_record.find(prefix)
    if start < 0:
        return None, "event prefix is absent"
    start += len(prefix)
    end = raw_record.find(suffix, start)
    if end < 0:
        return None, "event suffix is absent"
    actual_event_field = raw_record[start:end]
    if actual_event_field != exact_event_field:
        return None, "event field differs from exact logger rendering"

    mode = parser_contract.get("normalization_mode")
    if mode == "NONE":
        return raw_record, None
    if mode != "STRIP_DECLARED_LEADING_PADDING_AFTER_EVENT_EQUALS":
        return None, "unknown parser normalization mode"
    pad = parser_contract.get("normalization_padding_char")
    maximum = parser_contract.get("normalization_max_padding_chars")
    if not isinstance(pad, str) or len(pad) != 1:
        return None, "normalization padding char must be one character"
    if not isinstance(maximum, int) or maximum < 0:
        return None, "normalization max padding must be nonnegative"
    count = 0
    while count < len(actual_event_field) and actual_event_field[count] == pad:
        count += 1
    if count > maximum:
        return None, "declared normalization padding budget exceeded"
    normalized_field = actual_event_field[count:]
    return raw_record[:start] + normalized_field + raw_record[end:], None


def evaluate_logger_parser_format_trace(
    fixture: dict[str, Any],
) -> dict[str, Any]:
    """Bind exact logger rendering to parser consumption.

    The gate rejects a hand-written unpadded trace as the sole positive.  Each
    required token is rendered through the declared logger width/alignment,
    checked byte-for-byte, optionally normalized by an explicit narrow
    contract, and then consumed by the declared parser expression.
    """

    errors: list[str] = []
    _expect(
        errors,
        fixture.get("schema") == "server_logger_parser_format_trace_v1",
        "logger/parser trace schema mismatch",
    )
    _expect(
        errors,
        fixture.get("rule_id") == LOGGER_PARSER_RULE_ID,
        "logger/parser trace rule mismatch",
    )
    historical = fixture.get("historical_binding")
    if not isinstance(historical, dict):
        historical = {}
        errors.append("historical binding is missing")
    _expect(
        errors,
        historical.get("family") == "global_average_pool",
        "historical family mismatch",
    )
    _expect(
        errors,
        historical.get("source_package_sha256") == GAP_V53_SOURCE_SHA256,
        "historical GAP v53 source identity mismatch",
    )
    _expect(
        errors,
        historical.get("return_sha256") == GAP_V53_RETURN_SHA256,
        "historical GAP v53 return identity mismatch",
    )
    _expect(
        errors,
        historical.get("analysis_sha256") == GAP_V53_ANALYSIS_SHA256,
        "historical GAP v53 analysis identity mismatch",
    )
    source_bindings = fixture.get("source_bindings")
    if not isinstance(source_bindings, dict):
        source_bindings = {}
        errors.append("source bindings are missing")
    logger_source = source_bindings.get("logger")
    parser_source = source_bindings.get("parser")
    if not isinstance(logger_source, dict):
        logger_source = {}
        errors.append("logger source binding is missing")
    if not isinstance(parser_source, dict):
        parser_source = {}
        errors.append("parser source binding is missing")
    _expect(
        errors,
        logger_source.get("member_path") == "tb_probe/native_return_observer.svh"
        and logger_source.get("sha256") == GAP_V53_LOGGER_SHA256
        and logger_source.get("source_span") == "6550-6552",
        "historical GAP v53 logger source binding mismatch",
    )
    _expect(
        errors,
        parser_source.get("member_path")
        == "package_tools/gap_node0071_mse4_route_factor_decision.py"
        and parser_source.get("sha256") == GAP_V53_PARSER_SHA256
        and parser_source.get("source_span") == "5-12",
        "historical GAP v53 parser source binding mismatch",
    )

    logger = fixture.get("logger_contract")
    parser = fixture.get("parser_contract")
    if not isinstance(logger, dict):
        logger = {}
        errors.append("logger contract is missing")
    if not isinstance(parser, dict):
        parser = {}
        errors.append("parser contract is missing")
    marker = logger.get("record_marker")
    tokens = logger.get("event_tokens")
    render_mode = logger.get("event_render_mode")
    format_string = logger.get("event_format_string")
    width = logger.get("event_container_width")
    pad = logger.get("padding_char")
    field_names = logger.get("field_names")
    _expect(errors, isinstance(marker, str) and bool(marker), "record marker missing")
    _expect(
        errors,
        isinstance(tokens, list)
        and tokens == ["QUALIFIED_EDGE", "FACTOR_EDGE", "HEARTBEAT"],
        "event token order/set mismatch",
    )
    _expect(
        errors,
        render_mode in {"RIGHT_JUSTIFIED_FIXED_WIDTH", "UNPADDED"},
        "logger render mode is invalid",
    )
    _expect(
        errors,
        (
            render_mode == "RIGHT_JUSTIFIED_FIXED_WIDTH"
            and format_string == "%s"
        )
        or (render_mode == "UNPADDED" and format_string == "%0s"),
        "logger format string/render mode mismatch",
    )
    _expect(errors, isinstance(width, int) and width >= 0, "logger width invalid")
    _expect(
        errors,
        isinstance(pad, str) and len(pad) == 1,
        "logger padding char must be one character",
    )
    _expect(
        errors,
        isinstance(field_names, list)
        and bool(field_names)
        and all(isinstance(item, str) and item for item in field_names),
        "logger field names are invalid",
    )
    if isinstance(tokens, list) and isinstance(width, int):
        _expect(
            errors,
            render_mode != "RIGHT_JUSTIFIED_FIXED_WIDTH"
            or width >= max(len(item) for item in tokens),
            "logger width truncates an event token",
        )
        if parser.get("normalization_mode") == (
            "STRIP_DECLARED_LEADING_PADDING_AFTER_EVENT_EQUALS"
        ):
            maximum_padding = max(width - len(item) for item in tokens)
            _expect(
                errors,
                parser.get("normalization_padding_char") == pad,
                "normalization padding char differs from logger padding",
            )
            _expect(
                errors,
                parser.get("normalization_max_padding_chars")
                == maximum_padding,
                "normalization padding bound differs from exact logger maximum",
            )

    parser_prefix = parser.get("event_prefix_regex")
    parser_event = parser.get("event_capture_regex")
    if not isinstance(parser_prefix, str) or not parser_prefix:
        errors.append("parser event prefix regex is missing")
    if not isinstance(parser_event, str) or not parser_event:
        errors.append("parser event capture regex is missing")
    pattern: re.Pattern[str] | None = None
    if (
        isinstance(parser_prefix, str)
        and parser_prefix
        and isinstance(parser_event, str)
        and parser_event
        and isinstance(field_names, list)
        and all(isinstance(item, str) and item for item in field_names)
    ):
        try:
            field_pattern = r"\s+".join(
                fr"{re.escape(name)}=0x([0-9a-fA-F]+)"
                for name in field_names
            )
            pattern = re.compile(
                parser_prefix + parser_event + r".*?" + field_pattern
            )
        except re.error as error:
            errors.append(f"parser regex is invalid: {error}")

    rendered: list[dict[str, Any]] = []
    parsed_counts = {name: 0 for name in (tokens or []) if isinstance(name, str)}
    if (
        pattern is not None
        and isinstance(marker, str)
        and isinstance(tokens, list)
        and isinstance(render_mode, str)
        and isinstance(width, int)
        and isinstance(pad, str)
        and len(pad) == 1
        and isinstance(field_names, list)
    ):
        for token in tokens:
            raw, event_field = _render_logger_record(
                marker=marker,
                event=token,
                render_mode=render_mode,
                width=width,
                padding_char=pad,
                field_names=field_names,
            )
            prepared, preparation_error = _prepare_exact_logger_record(
                raw_record=raw,
                exact_event_field=event_field,
                parser_contract=parser,
            )
            match = pattern.search(prepared) if prepared is not None else None
            parsed_event = match.group(1) if match is not None else None
            passed = preparation_error is None and parsed_event == token
            if passed:
                parsed_counts[token] += 1
            else:
                errors.append(f"exact logger record was not parsed: {token}")
            rendered.append(
                {
                    "event": token,
                    "event_field": event_field,
                    "event_field_length": len(event_field),
                    "raw_record_sha256": hashlib.sha256(
                        raw.encode("utf-8")
                    ).hexdigest(),
                    "normalization_applied": prepared != raw,
                    "parsed_event": parsed_event,
                    "pass": passed,
                }
            )

    mutation_results: dict[str, bool] = {}
    if (
        isinstance(marker, str)
        and isinstance(render_mode, str)
        and isinstance(width, int)
        and isinstance(pad, str)
        and len(pad) == 1
        and isinstance(field_names, list)
        and pattern is not None
    ):
        token = "FACTOR_EDGE"
        raw, exact_field = _render_logger_record(
            marker=marker,
            event=token,
            render_mode=render_mode,
            width=width,
            padding_char=pad,
            field_names=field_names,
        )
        prefix = "event="
        start = raw.index(prefix) + len(prefix)
        end = raw.index(" qn=", start)
        padding_count = max(1, len(exact_field) - len(token))
        mutations = {
            "synthetic_unpadded_not_exact_logger": token,
            "tab_padding_not_declared": "\t" * padding_count + token,
            "nonbreaking_space_padding_not_declared": (
                "\u00a0" * padding_count + token
            ),
            "left_justified_not_declared": token + pad * padding_count,
            "overwidth_padding_not_declared": (
                pad * (padding_count + 1) + token
            ),
            "embedded_token_whitespace_not_declared": "FACTOR _EDGE",
        }
        for name, mutated_field in mutations.items():
            mutated = raw[:start] + mutated_field + raw[end:]
            prepared, preparation_error = _prepare_exact_logger_record(
                raw_record=mutated,
                exact_event_field=exact_field,
                parser_contract=parser,
            )
            match = pattern.search(prepared) if prepared is not None else None
            rejected = preparation_error is not None or match is None
            mutation_results[name] = rejected
            if not rejected:
                errors.append(f"undeclared logger format mutation accepted: {name}")

    all_exact_parsed = bool(rendered) and all(item["pass"] for item in rendered)
    all_mutations_rejected = bool(mutation_results) and all(
        mutation_results.values()
    )
    if not all_mutations_rejected:
        errors.append("one or more undeclared format mutations were accepted")
    return {
        "schema": "server_logger_parser_format_trace_validation_v1",
        "rule_id": LOGGER_PARSER_RULE_ID,
        "valid": not errors,
        "status": (
            "EXACT_LOGGER_TO_PARSER_FORMAT_CLOSED"
            if not errors
            else "LOGGER_PARSER_FORMAT_FAIL_CLOSED"
        ),
        "classification": "PACKAGE_LOCAL_RETURN_EVIDENCE_FORMAT_COVERAGE_ESCAPE",
        "errors": sorted(set(errors)),
        "exact_logger_rendered_records_tested": bool(rendered),
        "synthetic_unpadded_is_not_sole_positive": bool(rendered),
        "all_exact_logger_records_parsed": all_exact_parsed,
        "parsed_record_counts": parsed_counts,
        "rendered_records": rendered,
        "undeclared_mutation_controls": mutation_results,
        "all_undeclared_mutations_rejected": all_mutations_rejected,
        "historical_binding": historical,
        "source_bindings": source_bindings,
        "claim_boundary": (
            "Package-local logger byte rendering, declared normalization, and "
            "parser consumption only. No DUT, config, numeric, RTL, natural "
            "terminal, formal D, E4/E5, package rebuild, or server claim."
        ),
    }


def evaluate_multiclass_edge_trace(
    fixture: dict[str, Any],
) -> dict[str, Any]:
    """Prove that simultaneous diagnostic edge classes are not lost."""

    errors: list[str] = []
    _expect(
        errors,
        fixture.get("schema") == "server_diagnostic_multiclass_edge_trace_v1",
        "multiclass trace schema mismatch",
    )
    _expect(
        errors,
        fixture.get("rule_id") == MULTICLASS_EDGE_RULE_ID,
        "multiclass trace rule mismatch",
    )
    historical = fixture.get("historical_binding")
    if not isinstance(historical, dict):
        historical = {}
        errors.append("historical binding is missing")
    _expect(
        errors,
        historical.get("family") == "global_average_pool",
        "historical family mismatch",
    )
    _expect(
        errors,
        historical.get("source_package_sha256") == GAP_V54_SOURCE_SHA256,
        "historical GAP v54 source identity mismatch",
    )
    _expect(
        errors,
        historical.get("return_sha256") == GAP_V54_RETURN_SHA256,
        "historical GAP v54 return identity mismatch",
    )
    _expect(
        errors,
        historical.get("analysis_sha256") == GAP_V54_ANALYSIS_SHA256,
        "historical GAP v54 analysis identity mismatch",
    )
    source_bindings = fixture.get("source_bindings")
    if not isinstance(source_bindings, dict):
        source_bindings = {}
        errors.append("source bindings are missing")
    observer_source = source_bindings.get("observer")
    parser_source = source_bindings.get("parser")
    if not isinstance(observer_source, dict):
        observer_source = {}
        errors.append("observer source binding is missing")
    if not isinstance(parser_source, dict):
        parser_source = {}
        errors.append("parser source binding is missing")
    _expect(
        errors,
        observer_source.get("member_path") == "tb_probe/native_return_observer.svh"
        and observer_source.get("sha256") == GAP_V54_OBSERVER_SHA256
        and observer_source.get("source_span") == "6886-6980",
        "historical GAP v54 observer source binding mismatch",
    )
    _expect(
        errors,
        parser_source.get("member_path")
        == "package_tools/gap_node0071_remote_owner_false_accept_decision.py"
        and parser_source.get("sha256") == GAP_V54_PARSER_SHA256
        and parser_source.get("source_span") == "5-12",
        "historical GAP v54 parser source binding mismatch",
    )

    classes = fixture.get("classes")
    expected_ids = ["QUALIFIED_EDGE", "VIOLATION_EDGE", "FACTOR_EDGE"]
    if not isinstance(classes, list):
        classes = []
        errors.append("multiclass class list is missing")
    class_ids = [item.get("id") for item in classes if isinstance(item, dict)]
    _expect(errors, class_ids == expected_ids, "multiclass class order/set mismatch")
    priorities: dict[str, int] = {}
    progress_classes: set[str] = set()
    monotonic_classes: set[str] = set()
    for item in classes:
        if not isinstance(item, dict):
            errors.append("multiclass class entry is invalid")
            continue
        class_id = item.get("id")
        priority = item.get("priority")
        if not isinstance(class_id, str):
            continue
        _expect(errors, isinstance(priority, int) and priority >= 0, f"invalid priority: {class_id}")
        if isinstance(priority, int):
            priorities[class_id] = priority
        _expect(errors, item.get("required") is True, f"class is not required: {class_id}")
        if item.get("counts_as_progress") is True:
            progress_classes.add(class_id)
        if item.get("sticky_monotonic") is True:
            monotonic_classes.add(class_id)
    _expect(
        errors,
        progress_classes == {"QUALIFIED_EDGE"},
        "only QUALIFIED_EDGE may count as progress",
    )
    _expect(
        errors,
        len(priorities) == len(set(priorities.values())) == len(expected_ids),
        "multiclass priorities must be unique",
    )

    emitter = fixture.get("emitter_contract")
    parser = fixture.get("parser_contract")
    if not isinstance(emitter, dict):
        emitter = {}
        errors.append("emitter contract is missing")
    if not isinstance(parser, dict):
        parser = {}
        errors.append("parser contract is missing")
    _expect(
        errors,
        emitter.get("selection_mode") == "HIGHEST_PRIORITY_SINGLE_RECORD",
        "emitter selection mode mismatch",
    )
    snapshot_mode = emitter.get("snapshot_advance_mode")
    _expect(
        errors,
        snapshot_mode in {"EMITTED_CLASS_ONLY", "ALL_CLASSES_UNCONDITIONAL"},
        "snapshot advance mode is invalid",
    )
    budgets = emitter.get("class_emit_budgets")
    if not isinstance(budgets, dict):
        budgets = {}
        errors.append("class emit budgets are missing")
    _expect(
        errors,
        set(budgets) == set(expected_ids)
        and all(isinstance(budgets.get(item), int) and budgets[item] > 0 for item in expected_ids),
        "class emit budgets must be positive and exact",
    )
    consumption_mode = parser.get("class_consumption_mode")
    _expect(
        errors,
        consumption_mode in {
            "EVENT_CLASS_GATED",
            "MONOTONIC_STICKY_ALL_REQUIRED_CLASSES_EVERY_RECORD",
        },
        "parser class consumption mode is invalid",
    )
    _expect(
        errors,
        parser.get("non_progress_classes_count_as_progress") is False,
        "non-progress class state must not count as progress",
    )
    if consumption_mode == "MONOTONIC_STICKY_ALL_REQUIRED_CLASSES_EVERY_RECORD":
        _expect(
            errors,
            monotonic_classes == set(expected_ids),
            "sticky-all parser requires every class state to be monotonic",
        )

    samples = fixture.get("samples")
    if not isinstance(samples, list) or not samples:
        samples = []
        errors.append("multiclass samples are missing")
    snapshots = {class_id: 0 for class_id in expected_ids}
    previous_state = {class_id: 0 for class_id in expected_ids}
    evidence = {class_id: 0 for class_id in expected_ids}
    emitted_counts = {class_id: 0 for class_id in expected_ids}
    emitted_sequence: list[dict[str, Any]] = []
    sample_trace: list[dict[str, Any]] = []
    budget_blocked_counts = {class_id: 0 for class_id in expected_ids}
    progress_record_count = 0
    simultaneous_samples = 0
    for ordinal, sample in enumerate(samples, 1):
        if not isinstance(sample, dict):
            errors.append(f"sample {ordinal} is invalid")
            continue
        state = sample.get("class_state")
        if not isinstance(state, dict) or set(state) != set(expected_ids):
            errors.append(f"sample {ordinal} class state mismatch")
            continue
        valid_state = True
        for class_id in expected_ids:
            value = state.get(class_id)
            if not isinstance(value, int) or value < 0:
                errors.append(f"sample {ordinal} invalid state: {class_id}")
                valid_state = False
                continue
            if class_id in monotonic_classes and (value | previous_state[class_id]) != value:
                errors.append(f"sample {ordinal} sticky state regressed: {class_id}")
            previous_state[class_id] = value
        if not valid_state:
            continue
        snapshot_before = dict(snapshots)
        changed = [class_id for class_id in expected_ids if state[class_id] != snapshots[class_id]]
        if len(changed) > 1:
            simultaneous_samples += 1
        eligible = [
            class_id
            for class_id in changed
            if isinstance(budgets.get(class_id), int)
            and emitted_counts[class_id] < budgets[class_id]
        ]
        for class_id in changed:
            if class_id not in eligible:
                budget_blocked_counts[class_id] += 1
        emitted = min(eligible, key=lambda item: priorities[item]) if eligible else None
        consumed_classes: list[str] = []
        progress_delta = 0
        if emitted is not None:
            emitted_counts[emitted] += 1
            if emitted in progress_classes:
                progress_record_count += 1
                progress_delta = 1
            if consumption_mode == "EVENT_CLASS_GATED":
                evidence[emitted] |= state[emitted]
                consumed_classes = [emitted]
            elif consumption_mode == "MONOTONIC_STICKY_ALL_REQUIRED_CLASSES_EVERY_RECORD":
                for class_id in expected_ids:
                    evidence[class_id] |= state[class_id]
                consumed_classes = list(expected_ids)
            emitted_sequence.append(
                {
                    "sample_id": sample.get("sample_id", str(ordinal)),
                    "changed_classes": changed,
                    "budget_eligible_classes": eligible,
                    "emitted_class": emitted,
                    "state": dict(state),
                }
            )
        if snapshot_mode == "ALL_CLASSES_UNCONDITIONAL":
            snapshots = dict(state)
        elif emitted is not None:
            snapshots[emitted] = state[emitted]
        sample_trace.append(
            {
                "sample_id": sample.get("sample_id", str(ordinal)),
                "class_state": dict(state),
                "changed_classes": changed,
                "budget_eligible_classes": eligible,
                "emitted_class": emitted,
                "parser_consumed_classes": consumed_classes,
                "progress_delta": progress_delta,
                "snapshot_before": snapshot_before,
                "snapshot_after": dict(snapshots),
            }
        )

    closure_strategy_valid = (
        snapshot_mode == "EMITTED_CLASS_ONLY"
        or consumption_mode == "MONOTONIC_STICKY_ALL_REQUIRED_CLASSES_EVERY_RECORD"
    )
    _expect(
        errors,
        closure_strategy_valid,
        "priority emitter advances un-emitted snapshots without sticky-all parser recovery",
    )
    missing_classes = [class_id for class_id in expected_ids if evidence[class_id] == 0]
    _expect(errors, not missing_classes, "required multiclass evidence is missing")
    _expect(
        errors,
        simultaneous_samples > 0,
        "trace lacks a simultaneous multiclass change sample",
    )
    non_progress_counted = sum(
        emitted_counts[class_id]
        for class_id in expected_ids
        if class_id not in progress_classes
    ) if parser.get("non_progress_classes_count_as_progress") is True else 0
    return {
        "schema": "server_diagnostic_multiclass_edge_trace_validation_v1",
        "rule_id": MULTICLASS_EDGE_RULE_ID,
        "valid": not errors,
        "status": (
            "MULTICLASS_EDGE_EVIDENCE_CLOSED"
            if not errors
            else "MULTICLASS_EDGE_LOSS_FAIL_CLOSED"
        ),
        "classification": "PACKAGE_LOCAL_DIAGNOSTIC_MULTICLASS_EDGE_LOSS",
        "errors": sorted(set(errors)),
        "closure_strategy": {
            "snapshot_advance_mode": snapshot_mode,
            "parser_class_consumption_mode": consumption_mode,
            "valid": closure_strategy_valid,
        },
        "simultaneous_multiclass_sample_count": simultaneous_samples,
        "emitted_sequence": emitted_sequence,
        "sample_trace": sample_trace,
        "emitted_record_counts": emitted_counts,
        "class_emit_budgets": budgets,
        "budget_blocked_counts": budget_blocked_counts,
        "class_evidence_masks": evidence,
        "required_class_count": len(expected_ids),
        "covered_required_class_count": len(expected_ids) - len(missing_classes),
        "missing_required_classes": missing_classes,
        "progress_record_count": progress_record_count,
        "non_progress_state_counted_as_progress": non_progress_counted > 0,
        "historical_binding": historical,
        "source_bindings": source_bindings,
        "claim_boundary": (
            "Package-local diagnostic multiclass emission/snapshot/parser "
            "coverage only. Sticky non-progress state remains separate from "
            "qualified progress. No DUT, config, numeric, RTL, package, server, "
            "natural terminal, formal D, E4, or E5 claim."
        ),
    }


def validate_registry(registry: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    _expect(
        errors,
        registry.get("schema")
        == "server_triggered_causal_observability_registry_v1",
        "registry schema mismatch",
    )
    _expect(errors, registry.get("version") == 1, "registry version mismatch")
    _expect(errors, registry.get("rule_id") == RULE_ID, "registry rule mismatch")
    mechanisms = registry.get("mechanisms")
    _expect(
        errors,
        isinstance(mechanisms, list) and bool(mechanisms),
        "registry mechanisms are missing",
    )
    indexed: dict[str, dict[str, Any]] = {}
    if isinstance(mechanisms, list):
        for index, mechanism in enumerate(mechanisms):
            prefix = f"registry.mechanisms[{index}]"
            if not isinstance(mechanism, dict):
                errors.append(f"{prefix} must be an object")
                continue
            mechanism_id = mechanism.get("mechanism_id")
            if not isinstance(mechanism_id, str) or not mechanism_id:
                errors.append(f"{prefix}.mechanism_id is missing")
                continue
            if mechanism_id in indexed:
                errors.append(f"duplicate mechanism_id: {mechanism_id}")
            indexed[mechanism_id] = mechanism
            _expect(
                errors,
                isinstance(mechanism.get("historical_sources"), list)
                and bool(mechanism["historical_sources"]),
                f"{prefix}.historical_sources are missing",
            )
            _expect(
                errors,
                isinstance(mechanism.get("claim_boundary"), str)
                and bool(mechanism["claim_boundary"]),
                f"{prefix}.claim_boundary is missing",
            )
    _expect(
        errors,
        set(indexed) == MECHANISM_IDS,
        "registry mechanism set mismatch",
    )
    canonical = registry.get("canonical_classifications")
    _expect(
        errors,
        isinstance(canonical, list)
        and set(canonical) == CANONICAL_CLASSIFICATIONS
        and len(canonical) == len(CANONICAL_CLASSIFICATIONS),
        "registry canonical classification set mismatch",
    )
    overhead = indexed.get("OBSERVER_OVERHEAD_BUDGET", {}).get(
        "required_policy", {}
    )
    _expect(
        errors,
        overhead.get("decision_priority") == DECISION_PRIORITY,
        "registry overhead decision priority mismatch",
    )
    _expect(
        errors,
        overhead.get("preferred_max_slowdown_percent")
        == PREFERRED_SLOWDOWN_PERCENT,
        "registry preferred slowdown must be 50 percent",
    )
    _expect(
        errors,
        overhead.get("slowdown_limit_hard") is False,
        "registry slowdown limit must be advisory",
    )
    return errors, {
        "mechanism_count": len(indexed),
        "mechanism_ids": sorted(indexed),
        "historical_source_count": sum(
            len(item.get("historical_sources", []))
            for item in indexed.values()
        ),
    }


def _validate_policy(policy: Any, errors: list[str]) -> None:
    if not isinstance(policy, dict):
        errors.append("profiles policy is missing")
        return
    expected = {
        "application_scope": APPLICATION_SCOPE,
        "decision_priority": DECISION_PRIORITY,
        "preferred_max_slowdown_percent": PREFERRED_SLOWDOWN_PERCENT,
        "slowdown_limit_hard": False,
        "over_preferred_action": OVER_PREFERRED_ACTION,
        "no_per_event_text_io": True,
        "full_wave_dump": False,
        "first_version_auto_terminate": False,
    }
    for key, value in expected.items():
        _expect(
            errors,
            policy.get(key) == value,
            f"policy.{key} mismatch",
        )
    for key in (
        "default_log_budget_bytes",
        "default_active_boundary_budget",
        "default_ring_event_budget",
    ):
        _expect(
            errors,
            isinstance(policy.get(key), int) and policy[key] > 0,
            f"policy.{key} must be a positive declared budget",
        )


def _validate_profile(
    profile: Any,
    *,
    index: int,
    canonical_registry: set[str],
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    prefix = f"profiles[{index}]"
    if not isinstance(profile, dict):
        return [f"{prefix} must be an object"], {}
    profile_id = profile.get("profile_id")
    family = profile.get("family")
    _expect(
        errors,
        isinstance(profile_id, str) and bool(profile_id),
        f"{prefix}.profile_id is missing",
    )
    _expect(
        errors,
        isinstance(family, str) and bool(family),
        f"{prefix}.family is missing",
    )
    current_package = profile.get("current_package")
    if not isinstance(current_package, dict):
        errors.append(f"{prefix}.current_package is missing")
    else:
        _expect(
            errors,
            current_package.get("disposition") == "READ_ONLY_NOT_MODIFIED",
            f"{prefix}.current_package must remain read-only",
        )
        sha = current_package.get("sha256")
        _expect(
            errors,
            isinstance(sha, str)
            and len(sha) == 64
            and all(char in "0123456789abcdef" for char in sha),
            f"{prefix}.current_package SHA is invalid",
        )
    runtime = profile.get("runtime_behavior")
    if not isinstance(runtime, dict):
        errors.append(f"{prefix}.runtime_behavior is missing")
    else:
        required_runtime = {
            "read_only": True,
            "drives_dut": False,
            "changes_input": False,
            "changes_ready_backpressure": False,
            "changes_timing": False,
            "changes_timeout": False,
            "host_internal_tensor_replay": False,
            "stage_gating": True,
        }
        for key, value in required_runtime.items():
            _expect(
                errors,
                runtime.get(key) == value,
                f"{prefix}.runtime_behavior.{key} must be {value!r}",
            )
    budget = profile.get("performance_budget")
    if not isinstance(budget, dict):
        errors.append(f"{prefix}.performance_budget is missing")
        budget = {}
    _expect(
        errors,
        budget.get("decision_priority") == DECISION_PRIORITY,
        f"{prefix}.performance_budget must prioritize one-round discrimination",
    )
    _expect(
        errors,
        budget.get("preferred_max_slowdown_percent")
        == PREFERRED_SLOWDOWN_PERCENT,
        f"{prefix}.preferred slowdown must be 50 percent",
    )
    _expect(
        errors,
        budget.get("slowdown_limit_hard") is False,
        f"{prefix}.slowdown limit must not be hard",
    )
    _expect(
        errors,
        budget.get("calibration_method") == "SAME_EVENT_TRACE_AB_WALLCLOCK",
        f"{prefix}.calibration method mismatch",
    )
    calibration_status = budget.get("calibration_status")
    baseline = budget.get("baseline_wall_seconds")
    instrumented = budget.get("instrumented_wall_seconds")
    calibration: dict[str, Any]
    if calibration_status == "PENDING_FRESH_BOUND_PROFILE":
        _expect(
            errors,
            baseline is None and instrumented is None,
            f"{prefix}.pending calibration cannot contain wall times",
        )
        calibration = {
            "status": calibration_status,
            "blocking": False,
            "release_eligible": False,
        }
    elif calibration_status in {
        "WITHIN_PREFERRED",
        "ABOVE_PREFERRED_REPORTED",
    }:
        try:
            calibration = evaluate_calibration(
                baseline_wall_seconds=float(baseline),
                instrumented_wall_seconds=float(instrumented),
            )
        except (TypeError, ValueError, ContractError) as error:
            errors.append(f"{prefix}.calibration is invalid: {error}")
            calibration = {"status": "INVALID"}
        else:
            _expect(
                errors,
                calibration["status"] == calibration_status,
                f"{prefix}.calibration status does not match measured wall time",
            )
    else:
        errors.append(f"{prefix}.calibration status is invalid")
        calibration = {"status": "INVALID"}
    maturity = profile.get("maturity")
    release_eligible = profile.get("release_eligible")
    if maturity == "BOUND_AND_CALIBRATED":
        _expect(
            errors,
            calibration_status
            in {"WITHIN_PREFERRED", "ABOVE_PREFERRED_REPORTED"},
            f"{prefix}.bound profile must contain calibration",
        )
    else:
        _expect(
            errors,
            release_eligible is False,
            f"{prefix}.unbound or uncalibrated profile cannot be release eligible",
        )
    storage = profile.get("storage")
    if not isinstance(storage, dict):
        errors.append(f"{prefix}.storage is missing")
        storage = {}
    _expect(
        errors,
        storage.get("per_event_text_io") is False,
        f"{prefix}.per-event text I/O is forbidden",
    )
    _expect(
        errors,
        storage.get("full_wave_dump") is False,
        f"{prefix}.full-wave dump is forbidden",
    )
    _expect(
        errors,
        isinstance(storage.get("max_log_bytes"), int)
        and storage["max_log_bytes"] > 0,
        f"{prefix}.max_log_bytes must be a positive declared budget",
    )
    _expect(
        errors,
        isinstance(storage.get("ring_events"), int)
        and storage["ring_events"] > 0,
        f"{prefix}.ring_events must be a positive bound",
    )
    _expect(
        errors,
        storage.get("flush_policy")
        == "TIME0_TRIGGER_STAGE_TRANSITION_EXIT_FINAL_ONLY",
        f"{prefix}.flush policy mismatch",
    )
    budget_separation = storage.get("diagnostic_budget_separation")
    expected_budget_separation = {
        "accounting_mode": "SEPARATE_QUALIFIED_AND_NON_PROGRESS",
        "state_activity_consumes_qualified_budget": False,
        "state_overflow_policy": "COALESCE_OR_DROP_STATE_ONLY",
        "late_qualified_event_policy": (
            "REMAINS_ELIGIBLE_AFTER_STATE_BUDGET_EXHAUSTION"
        ),
    }
    if not isinstance(budget_separation, dict):
        errors.append(
            f"{prefix}.storage.diagnostic_budget_separation is missing"
        )
        budget_separation = {}
    for key, value in expected_budget_separation.items():
        _expect(
            errors,
            budget_separation.get(key) == value,
            f"{prefix}.storage.diagnostic_budget_separation.{key} "
            f"must be {value!r}",
        )
    for key in ("qualified_event_budget", "non_progress_state_budget"):
        _expect(
            errors,
            isinstance(budget_separation.get(key), int)
            and budget_separation[key] > 0,
            f"{prefix}.storage.diagnostic_budget_separation.{key} "
            "must be positive",
        )
    no_progress = profile.get("no_progress")
    expected_no_progress = {
        "qualified_progress_only": True,
        "qualified_measured_rate_required": True,
        "auto_terminate": False,
        "on_trigger": "SNAPSHOT_AND_CONTINUE_EXISTING_TIMEOUT",
    }
    if not isinstance(no_progress, dict):
        errors.append(f"{prefix}.no_progress is missing")
    else:
        for key, value in expected_no_progress.items():
            _expect(
                errors,
                no_progress.get(key) == value,
                f"{prefix}.no_progress.{key} must be {value!r}",
            )
    boundaries = profile.get("boundaries")
    boundary_ids: set[str] = set()
    roles: dict[str, int] = {}
    if not isinstance(boundaries, list) or len(boundaries) < 2:
        errors.append(f"{prefix}.boundaries must contain at least two entries")
        boundaries = []
    for boundary_index, boundary in enumerate(boundaries):
        item_prefix = f"{prefix}.boundaries[{boundary_index}]"
        if not isinstance(boundary, dict):
            errors.append(f"{item_prefix} must be an object")
            continue
        boundary_id = boundary.get("boundary_id")
        if not isinstance(boundary_id, str) or not boundary_id:
            errors.append(f"{item_prefix}.boundary_id is missing")
            continue
        if boundary_id in boundary_ids:
            errors.append(f"{prefix} duplicate boundary_id: {boundary_id}")
        boundary_ids.add(boundary_id)
        role = boundary.get("role")
        if not isinstance(role, str) or not role:
            errors.append(f"{item_prefix}.role is missing")
        else:
            roles[role] = roles.get(role, 0) + 1
        _expect(
            errors,
            isinstance(boundary.get("stage_gate"), str)
            and bool(boundary["stage_gate"]),
            f"{item_prefix}.stage_gate is missing",
        )
        _expect(
            errors,
            boundary.get("owner_clock_binding")
            in {
                "EXACT_FINAL_SOURCE_REQUIRED",
                "HOST_MONOTONIC",
                "NOT_APPLICABLE",
            },
            f"{item_prefix}.owner clock binding is invalid",
        )
        _expect(
            errors,
            isinstance(boundary.get("qualification"), str)
            and bool(boundary["qualification"]),
            f"{item_prefix}.qualification is missing",
        )
        records = boundary.get("records")
        _expect(
            errors,
            isinstance(records, list)
            and {"count", "first_time", "last_time"}.issubset(records),
            f"{item_prefix}.records must include count/first_time/last_time",
        )
    for required_role in (
        "infrastructure",
        "source_produce",
        "consumer_accept",
        "terminal_propagation",
        "formal_d_collection",
    ):
        _expect(
            errors,
            roles.get(required_role, 0) >= 1,
            f"{prefix} lacks required role: {required_role}",
        )
    hypotheses = profile.get("hypotheses")
    hypothesis_ids: set[str] = set()
    signatures: set[tuple[str, ...]] = set()
    if not isinstance(hypotheses, list) or len(hypotheses) < 2:
        errors.append(f"{prefix}.hypotheses must contain at least two entries")
        hypotheses = []
    for hypothesis_index, hypothesis in enumerate(hypotheses):
        item_prefix = f"{prefix}.hypotheses[{hypothesis_index}]"
        if not isinstance(hypothesis, dict):
            errors.append(f"{item_prefix} must be an object")
            continue
        hypothesis_id = hypothesis.get("hypothesis_id")
        if not isinstance(hypothesis_id, str) or not hypothesis_id:
            errors.append(f"{item_prefix}.hypothesis_id is missing")
        elif hypothesis_id in hypothesis_ids:
            errors.append(f"{prefix} duplicate hypothesis_id: {hypothesis_id}")
        else:
            hypothesis_ids.add(hypothesis_id)
        _expect(
            errors,
            hypothesis.get("classification") in canonical_registry,
            f"{item_prefix}.classification is not canonical",
        )
        refs = hypothesis.get("distinguished_by")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{item_prefix}.distinguished_by is missing")
            continue
        unknown = sorted(set(refs) - boundary_ids)
        if unknown:
            errors.append(
                f"{item_prefix} references unknown boundaries: {unknown}"
            )
        signature = tuple(sorted(set(refs)))
        if signature in signatures:
            errors.append(
                f"{prefix} hypotheses reuse the same observation signature: "
                f"{signature}"
            )
        signatures.add(signature)
        _expect(
            errors,
            isinstance(hypothesis.get("decision"), str)
            and bool(hypothesis["decision"]),
            f"{item_prefix}.decision is missing",
        )
    triggers = profile.get("triggers")
    trigger_ids: set[str] = set()
    if not isinstance(triggers, list):
        errors.append(f"{prefix}.triggers are missing")
        triggers = []
    for trigger_index, trigger in enumerate(triggers):
        item_prefix = f"{prefix}.triggers[{trigger_index}]"
        if not isinstance(trigger, dict):
            errors.append(f"{item_prefix} must be an object")
            continue
        trigger_id = trigger.get("trigger_id")
        if trigger_id in trigger_ids:
            errors.append(f"{prefix} duplicate trigger: {trigger_id}")
        if isinstance(trigger_id, str):
            trigger_ids.add(trigger_id)
        refs = trigger.get("snapshot_boundaries")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{item_prefix}.snapshot_boundaries are missing")
        else:
            unknown = sorted(set(refs) - boundary_ids)
            if unknown:
                errors.append(
                    f"{item_prefix} references unknown boundaries: {unknown}"
                )
        _expect(
            errors,
            isinstance(trigger.get("one_shot"), bool),
            f"{item_prefix}.one_shot must be boolean",
        )
    _expect(
        errors,
        trigger_ids == REQUIRED_TRIGGERS,
        f"{prefix} trigger set mismatch",
    )
    canonical = profile.get("canonical_classifications")
    _expect(
        errors,
        isinstance(canonical, list)
        and set(canonical) == canonical_registry
        and len(canonical) == len(canonical_registry),
        f"{prefix} canonical classification set mismatch",
    )
    return errors, {
        "profile_id": profile_id,
        "family": family,
        "maturity": maturity,
        "release_eligible": release_eligible,
        "boundary_count": len(boundary_ids),
        "hypothesis_count": len(hypothesis_ids),
        "trigger_count": len(trigger_ids),
        "role_counts": dict(sorted(roles.items())),
        "calibration": calibration,
        "declared_log_budget_bytes": storage.get("max_log_bytes"),
        "declared_ring_events": storage.get("ring_events"),
        "diagnostic_budget_separation": {
            "accounting_mode": budget_separation.get("accounting_mode"),
            "qualified_event_budget": budget_separation.get(
                "qualified_event_budget"
            ),
            "non_progress_state_budget": budget_separation.get(
                "non_progress_state_budget"
            ),
            "state_activity_consumes_qualified_budget": (
                budget_separation.get(
                    "state_activity_consumes_qualified_budget"
                )
            ),
            "late_qualified_event_policy": budget_separation.get(
                "late_qualified_event_policy"
            ),
        },
        "preferred_max_slowdown_percent": PREFERRED_SLOWDOWN_PERCENT,
        "slowdown_is_hard_gate": False,
    }


def validate_bundle(
    registry: dict[str, Any],
    profiles: dict[str, Any],
) -> dict[str, Any]:
    errors, registry_summary = validate_registry(registry)
    _expect(
        errors,
        profiles.get("schema")
        == "server_triggered_causal_observability_profiles_v1",
        "profiles schema mismatch",
    )
    _expect(errors, profiles.get("version") == 1, "profiles version mismatch")
    bundle_scope = profiles.get("bundle_scope")
    _expect(
        errors,
        bundle_scope
        in {
            "CURRENT_FIVE_DESIGN_BASELINE",
            "FRESH_SUCCESSOR_BOUND_PROFILE",
        },
        "profiles bundle_scope mismatch",
    )
    _validate_policy(profiles.get("policy"), errors)
    profile_values = profiles.get("profiles")
    if not isinstance(profile_values, list) or not profile_values:
        errors.append("profiles list is missing")
        profile_values = []
    summaries: list[dict[str, Any]] = []
    profile_ids: set[str] = set()
    families: set[str] = set()
    for index, profile in enumerate(profile_values):
        profile_errors, summary = _validate_profile(
            profile,
            index=index,
            canonical_registry=CANONICAL_CLASSIFICATIONS,
        )
        errors.extend(profile_errors)
        if summary:
            profile_id = summary.get("profile_id")
            family = summary.get("family")
            if profile_id in profile_ids:
                errors.append(f"duplicate profile_id: {profile_id}")
            elif isinstance(profile_id, str):
                profile_ids.add(profile_id)
            if isinstance(family, str):
                families.add(family)
            summaries.append(summary)
    if bundle_scope == "CURRENT_FIVE_DESIGN_BASELINE":
        _expect(
            errors,
            families == CURRENT_FAMILIES,
            "current-five family set mismatch",
        )
        _expect(
            errors,
            all(
                summary.get("release_eligible") is False
                for summary in summaries
            ),
            "design profiles must not become release eligible",
        )
    return {
        "schema": "server_triggered_causal_observability_validation_v1",
        "valid": not errors,
        "status": (
            (
                "DESIGN_VALID_BINDING_AND_CALIBRATION_PENDING"
                if bundle_scope == "CURRENT_FIVE_DESIGN_BASELINE"
                else "FRESH_SUCCESSOR_PROFILE_VALID"
            )
            if not errors
            else "DESIGN_INVALID"
        ),
        "errors": sorted(set(errors)),
        "registry": registry_summary,
        "profile_count": len(summaries),
        "families": sorted(families),
        "bundle_scope": bundle_scope,
        "profiles": summaries,
        "policy": {
            "application_scope": APPLICATION_SCOPE,
            "decision_priority": DECISION_PRIORITY,
            "preferred_max_slowdown_percent": PREFERRED_SLOWDOWN_PERCENT,
            "slowdown_is_hard_gate": False,
            "over_preferred_action": OVER_PREFERRED_ACTION,
            "observation_completeness_must_be_preserved": True,
            "current_packages_modified": False,
            "server_package_generated": False,
            "server_action_performed": False,
        },
        "claim_boundary": (
            "Static design-contract validation only. Exact final-ZIP HDL "
            "binding, same-event-trace A/B calibration, production compile, "
            "simulation, natural terminal, formal D, E4 and E5 remain open."
        ),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate triggered causal observability contracts"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    validate.add_argument("--profiles", type=Path, default=DEFAULT_PROFILES)
    validate.add_argument("--output", type=Path)
    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument(
        "--baseline-wall-seconds", type=float, required=True
    )
    calibrate.add_argument(
        "--instrumented-wall-seconds", type=float, required=True
    )
    calibrate.add_argument(
        "--preferred-max-slowdown-percent",
        type=float,
        default=PREFERRED_SLOWDOWN_PERCENT,
    )
    calibrate.add_argument("--output", type=Path)
    budget_trace = subparsers.add_parser("validate-budget-trace")
    budget_trace.add_argument("--fixture", type=Path, required=True)
    budget_trace.add_argument("--output", type=Path)
    format_trace = subparsers.add_parser("validate-logger-parser-format")
    format_trace.add_argument("--fixture", type=Path, required=True)
    format_trace.add_argument("--output", type=Path)
    multiclass_trace = subparsers.add_parser("validate-multiclass-edge-trace")
    multiclass_trace.add_argument("--fixture", type=Path, required=True)
    multiclass_trace.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            registry = load_json(args.registry)
            profiles = load_json(args.profiles)
            report = validate_bundle(registry, profiles)
            implementation_paths = {
                "schema": (
                    ROOT
                    / "schemas/server_triggered_causal_observability_v1.schema.json"
                ),
                "validator": Path(__file__).resolve(),
                "server_rule": (
                    ROOT / ".agents/rules/服务器测试包生成规则.md"
                ),
                "optimizer_rule": (
                    ROOT / ".agents/rules/整网测试收敛优化专项规则.md"
                ),
                "generation_index": (
                    ROOT / ".agents/rules/生成前必读索引.md"
                ),
            }
            report["inputs"] = {
                "registry": {
                    "path": str(args.registry),
                    "sha256": sha256_file(args.registry),
                },
                "profiles": {
                    "path": str(args.profiles),
                    "sha256": sha256_file(args.profiles),
                },
            }
            report["implementation_receipts"] = {
                name: {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(path),
                }
                for name, path in implementation_paths.items()
            }
            exit_code = 0 if report["valid"] else 1
        elif args.command == "calibrate":
            report = evaluate_calibration(
                baseline_wall_seconds=args.baseline_wall_seconds,
                instrumented_wall_seconds=args.instrumented_wall_seconds,
                preferred_max_slowdown_percent=(
                    args.preferred_max_slowdown_percent
                ),
            )
            exit_code = 0
        elif args.command == "validate-budget-trace":
            report = evaluate_diagnostic_budget_trace(
                load_json(args.fixture)
            )
            report["inputs"] = {
                "fixture": {
                    "path": str(args.fixture),
                    "sha256": sha256_file(args.fixture),
                },
                "fixture_schema": {
                    "path": str(
                        ROOT
                        / "schemas/server_diagnostic_budget_trace_v1.schema.json"
                    ),
                    "sha256": sha256_file(
                        ROOT
                        / "schemas/server_diagnostic_budget_trace_v1.schema.json"
                    ),
                },
                "validator": {
                    "path": str(Path(__file__).resolve()),
                    "sha256": sha256_file(Path(__file__).resolve()),
                },
            }
            exit_code = 0 if report["valid"] else 1
        elif args.command == "validate-logger-parser-format":
            report = evaluate_logger_parser_format_trace(
                load_json(args.fixture)
            )
            report["inputs"] = {
                "fixture": {
                    "path": str(args.fixture),
                    "sha256": sha256_file(args.fixture),
                },
                "fixture_schema": {
                    "path": str(
                        ROOT
                        / "schemas/server_logger_parser_format_trace_v1.schema.json"
                    ),
                    "sha256": sha256_file(
                        ROOT
                        / "schemas/server_logger_parser_format_trace_v1.schema.json"
                    ),
                },
                "validator": {
                    "path": str(Path(__file__).resolve()),
                    "sha256": sha256_file(Path(__file__).resolve()),
                },
            }
            exit_code = 0 if report["valid"] else 1
        else:
            report = evaluate_multiclass_edge_trace(load_json(args.fixture))
            report["inputs"] = {
                "fixture": {
                    "path": str(args.fixture),
                    "sha256": sha256_file(args.fixture),
                },
                "fixture_schema": {
                    "path": str(
                        ROOT
                        / "schemas/server_diagnostic_multiclass_edge_trace_v1.schema.json"
                    ),
                    "sha256": sha256_file(
                        ROOT
                        / "schemas/server_diagnostic_multiclass_edge_trace_v1.schema.json"
                    ),
                },
                "validator": {
                    "path": str(Path(__file__).resolve()),
                    "sha256": sha256_file(Path(__file__).resolve()),
                },
            }
            exit_code = 0 if report["valid"] else 1
    except ContractError as error:
        report = {
            "valid": False,
            "status": "INPUT_ERROR",
            "errors": [str(error)],
        }
        exit_code = 2
    if args.output:
        write_json(args.output, report)
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
