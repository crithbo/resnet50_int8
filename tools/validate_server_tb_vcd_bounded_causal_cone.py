#!/usr/bin/env python3
"""Validate a source-bound, bounded causal-cone TB VCD contract."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import importlib.util
from pathlib import Path
from typing import Any


SCHEMA = "server-tb-vcd-bounded-causal-cone-v1"
PROFILE = "TB_VCD_BOUNDED_CAUSAL_CONE"
RULE_ID = "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001"
CURRENT_GATE_SEMANTIC_VERSION = "8"
LEGACY_PREDECESSOR_GATE_SEMANTIC_VERSIONS = {"5", "6", "7"}
REQUIRED_ROLES = (
    "clock", "reset", "stage", "source", "producer", "request", "valid", "ready", "accept", "backpressure",
    "fifo_enqueue", "fifo_dequeue", "fifo_occupancy", "fifo_full", "fifo_empty", "outstanding",
    "tag", "address", "mask", "last", "count", "ping_pong_branch0", "ping_pong_branch1",
    "per_bank_ready", "per_bank_full", "per_bank_valid", "per_bank_owner",
    "barrier", "lifetime", "clear", "completion", "drain", "finish", "global_terminal",
    "selected_port", "selected_bank", "selected_lane", "internal_match", "internal_state", "output", "wdata",
)
LAYERS = (
    "FIRST_DIVERGENCE_UPSTREAM_ONE", "FIRST_DIVERGENCE_CURRENT",
    "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "STATE_HOLD_CLEAR",
)
TASKS = ("$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush")
SHA = re.compile(r"^[0-9a-f]{64}$")
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def semantic_sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def source_identity_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": item.get("signal_id"),
        "exact_hierarchy": item.get("exact_hierarchy"),
        "width_bits": item.get("width_bits"),
        "source_path": item.get("source_path"),
        "source_sha256": item.get("source_sha256"),
        "declaration_span_sha256": item.get("declaration_span_sha256"),
    }


def resolve_evidence(
    root: Path | None,
    relative: Any,
    declared_sha: Any,
    label: str,
    errors: list[str],
) -> Path | None:
    if root is None:
        errors.append(f"{label}: validation root is required for exact evidence")
        return None
    if not isinstance(relative, str) or not relative:
        errors.append(f"{label}: evidence path is absent")
        return None
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label}: evidence path escapes validation root")
        return None
    if not candidate.is_file():
        errors.append(f"{label}: evidence file is absent")
        return None
    actual_sha = sha_file(candidate)
    if declared_sha != actual_sha:
        errors.append(f"{label}: evidence SHA mismatch")
        return None
    return candidate


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("contract must be an object")
    return value


def validate_contract(contract: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    tb_text: str | None = None
    if contract.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if contract.get("profile") != PROFILE:
        errors.append(f"profile must be {PROFILE}")
    if contract.get("rule_id") != RULE_ID:
        errors.append(f"rule_id must be {RULE_ID}")

    execution = contract.get("execution") if isinstance(contract.get("execution"), dict) else {}
    dump_argv = execution.get("dump_argv") if isinstance(execution.get("dump_argv"), dict) else {}
    for key in ("DUMP_VCD", "DUMP_FSDB", "TB_DUMP_FSDB"):
        if dump_argv.get(key) != "0":
            errors.append(f"{key} must be 0; TB standard tasks are the only VCD producer")
    if execution.get("producer") != "PACKAGE_LOCAL_TB_STANDARD_SYSTEM_TASKS_ONLY":
        errors.append("VCD producer must be package-local TB standard system tasks")
    if execution.get("standard_tasks") != list(TASKS):
        errors.append("standard task list must bind dumpfile/dumpvars/dumpon/dumpoff/dumpflush")
    if execution.get("lightweight_observer_jsonl") is not False:
        errors.append("VCD mode must not generate full observer JSONL")
    joined_argv = " ".join(str(x) for x in execution.get("compile_argv", []) + execution.get("sim_argv", []))
    if re.search(r"(?:DUMP_VCD|DUMP_FSDB|TB_DUMP_FSDB)=1", joined_argv):
        errors.append("actual compile/sim argv enables a forbidden Make/vendor dump")
    if re.search(r"\b(?:UCLI|vpd2vcd|verdi|dve|waveutils)\b|dump\s+-file", joined_argv, re.I):
        errors.append("actual argv contains forbidden UCLI/vendor waveform mechanism")

    tb_path = execution.get("tb_source_path")
    if root is not None and isinstance(tb_path, str):
        source = (root / tb_path).resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError:
            errors.append("TB source escapes validation root")
        else:
            if not source.is_file():
                errors.append("TB source is absent")
            else:
                text = source.read_text(encoding="utf-8", errors="replace")
                tb_text = text
                if sha_file(source) != execution.get("tb_source_sha256"):
                    errors.append("TB source SHA mismatch")
                for task in TASKS:
                    if task not in text:
                        errors.append(f"TB source lacks required standard task {task}")
                if re.search(r"\$fsdb|\bUCLI\b|dump\s+-file|\b(?:vpd2vcd|verdi|dve)\b", text, re.I):
                    errors.append("TB source contains forbidden vendor waveform control")

    scope = contract.get("scope") if isinstance(contract.get("scope"), dict) else {}
    top = scope.get("simulation_top")
    if scope.get("full_hierarchy_dump") is not False:
        errors.append("full hierarchy dump must be false")
    dump_scopes = scope.get("dump_scopes") if isinstance(scope.get("dump_scopes"), list) else []
    if not dump_scopes:
        errors.append("at least one bounded causal-cone dump scope is required")
    for item in dump_scopes:
        hierarchy = item.get("exact_hierarchy") if isinstance(item, dict) else None
        if not hierarchy or hierarchy == top:
            errors.append("dump scope must be explicit and narrower than the simulation top")

    budget = contract.get("budget") if isinstance(contract.get("budget"), dict) else {}
    expected_budget = {
        "soft_warning_bytes": 100_000_000,
        "operational_vcd_budget_bytes": 8_000_000_000,
        "return_budget_bytes": 10_000_000_000,
        "hard_truncation": False,
        "sampling": False,
        "size_based_deletion": False,
    }
    for key, wanted in expected_budget.items():
        if budget.get(key) != wanted:
            errors.append(f"budget {key} must be {wanted}")
    wall = budget.get("wall_ceiling_seconds")
    mode = budget.get("runtime_budget_mode")
    if not isinstance(wall, int) or isinstance(wall, bool) or not 3600 <= wall <= 86400:
        errors.append("budget wall_ceiling_seconds must be bounded within [3600,86400]")
    if budget.get("absolute_maximum_wall_seconds") != 86400:
        errors.append("budget absolute maximum wall must remain 86400 seconds")
    admission_path = budget.get("runtime_budget_admission_path")
    admission_sha = budget.get("runtime_budget_admission_sha256")
    if mode == "DEFAULT_BOUNDED":
        if wall != 3600 or admission_path is not None or admission_sha is not None:
            errors.append("default bounded runtime must remain 3600 seconds with no override receipt")
    elif mode == "MEASURED_PRETARGET_AWARE":
        if not isinstance(admission_path, str) or not admission_path:
            errors.append("runtime override lacks an admission receipt path")
        else:
            candidate = (root / admission_path).resolve()
            try:
                candidate.relative_to(root.resolve())
            except ValueError:
                errors.append("runtime budget admission receipt escapes validation root")
            else:
                if not candidate.is_file():
                    errors.append("runtime budget admission receipt is absent")
                elif sha_file(candidate) != admission_sha:
                    errors.append("runtime budget admission receipt SHA mismatch")
                else:
                    spec = importlib.util.spec_from_file_location(
                        "server_runtime_budget_admission",
                        REPOSITORY_ROOT / "tools" / "server_runtime_budget_admission.py",
                    )
                    if spec is None or spec.loader is None:
                        errors.append("runtime budget admission validator cannot be loaded")
                    else:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        admission = json.loads(candidate.read_text(encoding="utf-8"))
                        report = module.validate(admission)
                        if not report["pass"]:
                            errors.extend(f"runtime budget admission: {item}" for item in report["errors"])
                        if admission.get("mode") != mode or admission.get("selected_wall_ceiling_seconds") != wall:
                            errors.append("runtime budget admission mode/wall does not match package contract")
    else:
        errors.append("runtime budget mode is invalid")

    signals = contract.get("signals") if isinstance(contract.get("signals"), list) else []
    signal_ids: set[str] = set()
    signal_identity_by_id: dict[str, dict[str, Any]] = {}
    driver_candidates_by_signal: dict[str, set[str]] = {}
    for item in signals:
        sid = item.get("signal_id") if isinstance(item, dict) else None
        if not sid or sid in signal_ids:
            errors.append(f"duplicate or absent signal_id: {sid}")
            continue
        signal_ids.add(sid)
        signal_identity_by_id[sid] = source_identity_row(item)
        if item.get("source_binding") != "ACTUAL_SOURCE_NET" or item.get("derived_expected_equation") is not False:
            errors.append(f"{sid}: derived-only expected signal is forbidden")
        if item.get("drives_dut") is not False:
            errors.append(f"{sid}: diagnostic source must not drive DUT")
        if not isinstance(item.get("width_bits"), int) or item.get("width_bits", 0) < 1:
            errors.append(f"{sid}: width must be positive")
        if not SHA.fullmatch(str(item.get("source_sha256", ""))) or not SHA.fullmatch(str(item.get("declaration_span_sha256", ""))):
            errors.append(f"{sid}: source identity is incomplete")
        driver_candidates = item.get("driver_leaf_for_candidate_ids")
        if not isinstance(driver_candidates, list) or len(driver_candidates) != len(set(driver_candidates)):
            errors.append(f"{sid}: direct-driver candidate IDs must be a unique array")
            driver_candidates = []
        driver_candidates_by_signal[sid] = set(driver_candidates)
        if driver_candidates and item.get("driver_depth_edges") != 0:
            errors.append(f"{sid}: direct-driver leaf must have driver_depth_edges=0")
        if not driver_candidates and item.get("driver_depth_edges") is not None:
            errors.append(f"{sid}: non-driver signal must have null driver depth")

    targeting = execution.get("dump_targeting") if isinstance(execution.get("dump_targeting"), dict) else {}
    target_ids = targeting.get("signal_ids") if isinstance(targeting.get("signal_ids"), list) else []
    if targeting.get("mode") != "EXACT_CATALOG_SIGNALS" or targeting.get("module_scope_dump") is not False or targeting.get("dumpvars_depth") != 0:
        errors.append("VCD dump targeting must select exact catalog signals at depth 0; module-scope dump is forbidden")
    if len(target_ids) != len(set(target_ids)) or set(target_ids) != signal_ids:
        errors.append("exact VCD dump target signal IDs must equal the complete source-bound catalog")
    if tb_text is not None:
        dumpvars_calls = re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;", tb_text)
        dumpvars_targets = [target.strip() for call in dumpvars_calls for target in call.split(",") if target.strip()]
        expected_hierarchies = [
            str(item.get("exact_hierarchy"))
            for item in signals
            if isinstance(item, dict) and item.get("signal_id") in set(target_ids)
        ]
        if len(dumpvars_targets) != len(expected_hierarchies) or sorted(dumpvars_targets) != sorted(expected_hierarchies):
            errors.append("TB $dumpvars calls must equal the exact catalog hierarchy set; module/aggregate over-dump is forbidden")

    coverage = contract.get("role_coverage") if isinstance(contract.get("role_coverage"), list) else []
    seen_roles = [item.get("role") for item in coverage if isinstance(item, dict)]
    if sorted(seen_roles) != sorted(REQUIRED_ROLES):
        errors.append("role coverage must contain every causal role exactly once")
    for item in coverage:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        ids = item.get("signal_ids") if isinstance(item.get("signal_ids"), list) else []
        if item.get("disposition") == "covered":
            if not ids or not set(ids).issubset(signal_ids):
                errors.append(f"{role}: covered role lacks valid source-bound signals")
        elif item.get("disposition") == "not_applicable":
            proof = item.get("not_applicable_proof")
            if not isinstance(proof, dict) or proof.get("machine_check_exit") != 0 or not SHA.fullmatch(str(proof.get("sha256", ""))):
                errors.append(f"{role}: not_applicable lacks exact machine proof")
        else:
            errors.append(f"{role}: invalid disposition")

    boundaries = contract.get("boundaries") if isinstance(contract.get("boundaries"), list) else []
    boundary_ids: set[str] = set()
    layers: list[str] = []
    for item in boundaries:
        bid = item.get("boundary_id") if isinstance(item, dict) else None
        if not bid or bid in boundary_ids:
            errors.append(f"duplicate or absent boundary_id: {bid}")
            continue
        boundary_ids.add(bid)
        layers.append(item.get("layer"))
        if not set(item.get("signal_ids", [])).issubset(signal_ids) or not item.get("signal_ids"):
            errors.append(f"{bid}: boundary lacks valid signal IDs")
    if set(layers) != set(LAYERS):
        errors.append("boundaries must cover upstream/current/downstream/state-hold-clear")

    candidates = contract.get("candidates") if isinstance(contract.get("candidates"), list) else []
    candidate_ids = [item.get("candidate_id") for item in candidates if isinstance(item, dict)]
    if len(candidate_ids) < 2 or len(set(candidate_ids)) != len(candidate_ids):
        errors.append("at least two unique candidates are required")
    candidate_set = set(candidate_ids)
    high_probability_candidates = {
        item.get("candidate_id")
        for item in candidates
        if isinstance(item, dict) and item.get("priority") == "HIGH"
    }
    if not high_probability_candidates:
        errors.append("at least one HIGH-priority candidate is required")
    boundary_signal_ids = {
        sid
        for item in boundaries
        if isinstance(item, dict)
        for sid in item.get("signal_ids", [])
    }
    direct_drivers_by_candidate: dict[str, set[str]] = {
        candidate_id: set() for candidate_id in candidate_set
    }
    for signal_id, referenced_candidates in driver_candidates_by_signal.items():
        unknown_candidates = referenced_candidates - candidate_set
        if unknown_candidates:
            errors.append(
                f"{signal_id}: direct-driver leaf references unknown candidates: "
                f"{sorted(unknown_candidates)}"
            )
        if referenced_candidates and signal_id not in boundary_signal_ids:
            errors.append(
                f"{signal_id}: direct-driver leaf is outside every qualified boundary"
            )
        for candidate_id in referenced_candidates & candidate_set:
            direct_drivers_by_candidate[candidate_id].add(signal_id)
    missing_high_direct_drivers = {
        candidate_id
        for candidate_id in high_probability_candidates
        if not direct_drivers_by_candidate.get(candidate_id)
    }
    coverage_gaps = (
        contract.get("diagnostic_round", {}).get("coverage_gaps", [])
        if isinstance(contract.get("diagnostic_round"), dict)
        and isinstance(contract.get("diagnostic_round", {}).get("coverage_gaps"), list)
        else []
    )
    gap_candidates = [
        item.get("candidate_id")
        for item in coverage_gaps
        if isinstance(item, dict)
    ]
    if len(gap_candidates) != len(set(gap_candidates)) or set(gap_candidates) != missing_high_direct_drivers:
        errors.append("HIGH-candidate zero-hop driver coverage gaps do not exactly match the catalog")
    for item in coverage_gaps:
        if not isinstance(item, dict):
            continue
        if (
            item.get("gap_code") != "HIGH_CANDIDATE_ZERO_HOP_DRIVER_ABSENT"
            or not isinstance(item.get("reason"), str)
            or not item.get("reason").strip()
            or item.get("matrix_still_distinguishable") is not True
        ):
            errors.append(f"{item.get('candidate_id')}: HIGH-candidate driver gap record is incomplete")
    for candidate_id in sorted(missing_high_direct_drivers):
        warnings.append(
            f"{candidate_id}: HIGH-priority candidate has no source-bound zero-hop direct driver; gap is record-only while the matrix remains distinguishable"
        )
    matrix = contract.get("candidate_boundary_matrix") if isinstance(contract.get("candidate_boundary_matrix"), list) else []
    rows: dict[tuple[str, str], str] = {}
    for item in matrix:
        if not isinstance(item, dict):
            continue
        key = (item.get("candidate_id"), item.get("boundary_id"))
        if key in rows:
            errors.append(f"duplicate candidate-boundary row: {key}")
        rows[key] = canonical(item.get("expected_signature"))
    expected_rows = set(itertools.product(candidate_ids, boundary_ids))
    actual_rows = set(rows)
    if expected_rows != actual_rows:
        errors.append("candidate-boundary matrix is incomplete or has unexpected rows")
    for left, right in itertools.combinations(candidate_ids, 2):
        if boundary_ids and all(rows.get((left, bid)) == rows.get((right, bid)) for bid in boundary_ids):
            errors.append(f"candidate pair is not distinguishable: {left} vs {right}")

    diagnostic_round = (
        contract.get("diagnostic_round")
        if isinstance(contract.get("diagnostic_round"), dict)
        else {}
    )
    round_index = diagnostic_round.get("round_index")
    round_kind = diagnostic_round.get("round_kind")
    source_identity = (
        diagnostic_round.get("source_identity")
        if isinstance(diagnostic_round.get("source_identity"), dict)
        else {}
    )
    catalog_source_identity_sha = semantic_sha(
        sorted(signal_identity_by_id.values(), key=lambda row: str(row["signal_id"]))
    )
    if source_identity.get("catalog_source_identity_sha256") != catalog_source_identity_sha:
        errors.append("catalog source identity SHA differs from exact signal declarations")
    pinned_rtl_sha = source_identity.get("pinned_rtl_tree_sha256")
    if not SHA.fullmatch(str(pinned_rtl_sha or "")):
        errors.append("pinned RTL tree identity is absent")

    baseline = (
        diagnostic_round.get("breadth_baseline")
        if isinstance(diagnostic_round.get("breadth_baseline"), dict)
        else {}
    )
    if baseline.get("mode") != "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE":
        errors.append("breadth baseline mode must bind a soft current-family round-three reference")
    reference_round_index = baseline.get("reference_round_index")
    if not isinstance(reference_round_index, int) or reference_round_index < 3:
        errors.append("breadth baseline reference round must be at least three")
    baseline_path = resolve_evidence(
        root,
        baseline.get("receipt_path"),
        baseline.get("receipt_sha256"),
        "breadth baseline",
        errors,
    )
    baseline_receipt: dict[str, Any] = {}
    if baseline_path is not None:
        try:
            baseline_receipt = load(baseline_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"breadth baseline is unreadable: {exc}")
    expected_baseline = {
        "schema": "server-tb-vcd-family-round-breadth-baseline-v1",
        "family": contract.get("family"),
        "package_id": baseline.get("reference_package_id"),
        "round_index": baseline.get("reference_round_index"),
        "signal_count": baseline.get("reference_signal_count"),
        "direct_driver_leaf_count": baseline.get("reference_direct_driver_leaf_count"),
        "candidate_count": baseline.get("reference_candidate_count"),
        "boundary_count": baseline.get("reference_boundary_count"),
        "pinned_rtl_tree_sha256": pinned_rtl_sha,
        "machine_check_exit": 0,
    }
    for field, wanted in expected_baseline.items():
        if baseline_receipt.get(field) != wanted:
            errors.append(f"breadth baseline {field} differs")
    reasonable_range = (
        baseline.get("reasonable_signal_count_range")
        if isinstance(baseline.get("reasonable_signal_count_range"), dict)
        else {}
    )
    range_minimum = reasonable_range.get("minimum")
    range_maximum = reasonable_range.get("maximum")
    if (
        not isinstance(range_minimum, int)
        or not isinstance(range_maximum, int)
        or range_minimum < 1
        or range_minimum > range_maximum
    ):
        errors.append("reasonable signal-count reference range is invalid")
        expected_relation = None
    elif len(signal_ids) < range_minimum:
        expected_relation = "BELOW_REFERENCE_RANGE"
    elif len(signal_ids) > range_maximum:
        expected_relation = "ABOVE_REFERENCE_RANGE"
    else:
        expected_relation = "WITHIN_REFERENCE_RANGE"
    deviation = baseline.get("deviation") if isinstance(baseline.get("deviation"), dict) else {}
    if expected_relation is not None and deviation.get("relation") != expected_relation:
        errors.append("signal-count deviation relation differs from the declared reasonable range")
    if expected_relation in {"BELOW_REFERENCE_RANGE", "ABOVE_REFERENCE_RANGE"}:
        if not isinstance(deviation.get("explanation"), str) or not deviation.get("explanation", "").strip():
            errors.append("soft breadth deviation requires a non-empty explanation")
        if deviation.get("acknowledged") is not True:
            errors.append("soft breadth deviation must be acknowledged")
        warnings.append(
            f"signal count is {expected_relation.lower()}; deviation is recorded but not a package blocker"
        )

    evolution = (
        diagnostic_round.get("evolution")
        if isinstance(diagnostic_round.get("evolution"), dict)
        else {}
    )
    added = set(evolution.get("added_signal_ids", []))
    removed = set(evolution.get("removed_signal_ids", []))
    unchanged = set(evolution.get("unchanged_signal_ids", []))
    if added & removed or added & unchanged or removed & unchanged:
        errors.append("signal add/remove/unchanged diff sets overlap")
    preservation = (
        evolution.get("candidate_preservation")
        if isinstance(evolution.get("candidate_preservation"), dict)
        else {}
    )
    preserved_candidates = set(preservation.get("preserved_candidate_ids", []))
    closed_candidates = set(preservation.get("closed_candidate_ids", []))
    new_candidates = set(preservation.get("new_candidate_ids", []))
    closure_evidence = (
        preservation.get("closure_evidence")
        if isinstance(preservation.get("closure_evidence"), list)
        else []
    )
    predecessor = evolution.get("predecessor")
    if round_index == 1 or round_kind == "FIRST_DIAGNOSTIC_ROUND":
        if round_index != 1 or round_kind != "FIRST_DIAGNOSTIC_ROUND":
            errors.append("first diagnostic round index/kind must agree")
        if predecessor is not None:
            errors.append("first diagnostic round must not declare a predecessor")
        if added != signal_ids or removed or unchanged:
            errors.append("first diagnostic round diff must add the complete catalog from an empty predecessor")
        if preserved_candidates or closed_candidates or new_candidates != candidate_set or closure_evidence:
            errors.append("first diagnostic round candidate preservation must declare every candidate as new")
    elif isinstance(round_index, int) and round_index >= 2 and round_kind == "EVIDENCE_REFINED_SUCCESSOR":
        if not isinstance(predecessor, dict):
            errors.append("refined successor requires an exact predecessor contract")
            predecessor = {}
        predecessor_path = resolve_evidence(
            root,
            predecessor.get("contract_path"),
            predecessor.get("contract_sha256"),
            "predecessor contract",
            errors,
        )
        prior: dict[str, Any] = {}
        if predecessor_path is not None:
            try:
                prior = load(predecessor_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"predecessor contract is unreadable: {exc}")
        prior_round = prior.get("diagnostic_round") if isinstance(prior.get("diagnostic_round"), dict) else {}
        prior_source = prior_round.get("source_identity") if isinstance(prior_round.get("source_identity"), dict) else {}
        published_semantic = predecessor.get("published_gate_semantic_version")
        published_receipt_path = resolve_evidence(
            root,
            predecessor.get("published_pass_receipt_path"),
            predecessor.get("published_pass_receipt_sha256"),
            "predecessor published PASS receipt",
            errors,
        )
        published_receipt: dict[str, Any] = {}
        if published_receipt_path is not None:
            try:
                published_receipt = load(published_receipt_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"predecessor published PASS receipt is unreadable: {exc}")
        if (
            published_receipt.get("pass") is not True
            or published_receipt.get("package_id") != predecessor.get("package_id")
            or published_receipt.get("family") != contract.get("family")
            or published_receipt.get("errors") not in ([], None)
            or "PACKAGE_READY_NOT_RUN" not in str(published_receipt.get("status", ""))
        ):
            errors.append("predecessor published PASS receipt identity/status differs")
        if prior.get("package_id") != predecessor.get("package_id") or prior.get("family") != contract.get("family"):
            errors.append("predecessor package/family identity differs")
        if prior_round.get("round_index") != predecessor.get("round_index") or predecessor.get("round_index") != round_index - 1:
            errors.append("predecessor round identity is not the immediately prior round")
        elif predecessor_path is not None:
            if published_semantic == CURRENT_GATE_SEMANTIC_VERSION:
                prior_validation = validate_contract(prior, root)
                if not prior_validation.get("pass"):
                    errors.append("same-version predecessor contract does not pass the current breadth/evolution gate")
            elif published_semantic in LEGACY_PREDECESSOR_GATE_SEMANTIC_VERSIONS:
                activation_epoch = str(published_receipt.get("activation_epoch", ""))
                if (
                    f"semantic-v{published_semantic}" not in activation_epoch
                    and f"-v{published_semantic}" not in activation_epoch
                ):
                    errors.append("legacy predecessor PASS receipt does not bind its declared semantic version")
            else:
                errors.append("predecessor gate semantic version is unsupported")
        if predecessor.get("pinned_rtl_tree_sha256") != pinned_rtl_sha or prior_source.get("pinned_rtl_tree_sha256") != pinned_rtl_sha:
            errors.append("pinned RTL source identity drifted across diagnostic rounds")
        prior_signals = prior.get("signals") if isinstance(prior.get("signals"), list) else []
        prior_identity_by_id = {
            item.get("signal_id"): source_identity_row(item)
            for item in prior_signals
            if isinstance(item, dict) and item.get("signal_id")
        }
        prior_signal_ids = set(prior_identity_by_id)
        if added != signal_ids - prior_signal_ids or removed != prior_signal_ids - signal_ids or unchanged != signal_ids & prior_signal_ids:
            errors.append("signal add/remove/unchanged diff does not match predecessor and current catalogs")
        for signal_id in sorted(unchanged):
            if prior_identity_by_id.get(signal_id) != signal_identity_by_id.get(signal_id):
                errors.append(f"{signal_id}: unchanged signal source identity drifted")
        prior_candidates = {
            item.get("candidate_id")
            for item in prior.get("candidates", [])
            if isinstance(item, dict) and item.get("candidate_id")
        }
        if preserved_candidates != prior_candidates & candidate_set or closed_candidates != prior_candidates - candidate_set or new_candidates != candidate_set - prior_candidates:
            errors.append("candidate preservation/closure/new diff is incomplete")
        removal_evidence = evolution.get("removal_evidence") if isinstance(evolution.get("removal_evidence"), list) else []
        evidence_ids = [item.get("signal_id") for item in removal_evidence if isinstance(item, dict)]
        if len(evidence_ids) != len(set(evidence_ids)) or set(evidence_ids) != removed:
            errors.append("every removed signal requires exactly one adaptive-pruning record")
        for item in removal_evidence:
            if not isinstance(item, dict):
                continue
            if item.get("disposition") != "FAMILY_ADAPTIVE_PRUNING":
                errors.append(f"{item.get('signal_id')}: removal disposition is invalid")
            if not isinstance(item.get("reason"), str) or not item.get("reason", "").strip():
                errors.append(f"{item.get('signal_id')}: adaptive pruning lacks a reason")
            if item.get("confidence") == "LOW":
                errors.append(f"{item.get('signal_id')}: low-confidence signal must be retained by default")
            elif item.get("confidence") not in {"HIGH", "MEDIUM"}:
                errors.append(f"{item.get('signal_id')}: adaptive-pruning confidence is invalid")
            affected_candidates = set(item.get("affected_candidate_ids", []))
            if not affected_candidates.issubset(prior_candidates):
                errors.append(f"{item.get('signal_id')}: affected candidates are outside the predecessor set")
        closure_ids = [item.get("candidate_id") for item in closure_evidence if isinstance(item, dict)]
        if len(closure_ids) != len(set(closure_ids)) or set(closure_ids) != closed_candidates:
            errors.append("every closed candidate requires exactly one closure receipt")
        for item in closure_evidence:
            if not isinstance(item, dict):
                continue
            evidence_path = resolve_evidence(
                root,
                item.get("path"),
                item.get("sha256"),
                f"candidate closure {item.get('candidate_id')}",
                errors,
            )
            if item.get("machine_check_exit") != 0 or item.get("result") != "CLOSED_BY_PRIOR_EVIDENCE":
                errors.append(f"{item.get('candidate_id')}: candidate closure evidence is invalid")
            if evidence_path is not None:
                try:
                    evidence_receipt = load(evidence_path)
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"{item.get('candidate_id')}: closure evidence is unreadable: {exc}")
                else:
                    expected_receipt = {
                        "schema": "server-tb-vcd-candidate-closure-v1",
                        "family": contract.get("family"),
                        "predecessor_package_id": predecessor.get("package_id"),
                        "successor_package_id": contract.get("package_id"),
                        "candidate_id": item.get("candidate_id"),
                        "result": "CLOSED_BY_PRIOR_EVIDENCE",
                        "pinned_rtl_tree_sha256": pinned_rtl_sha,
                        "machine_check_exit": 0,
                    }
                    for field, wanted in expected_receipt.items():
                        if evidence_receipt.get(field) != wanted:
                            errors.append(
                                f"{item.get('candidate_id')}: closure evidence receipt {field} differs"
                            )
    else:
        errors.append("diagnostic round index/kind is invalid")

    runtime = contract.get("runtime_policy") if isinstance(contract.get("runtime_policy"), dict) else {}
    expected_runtime = {
        "plateau_suspected_cycles": 1_048_576,
        "plateau_dump_off_cycles": 4_194_304,
        "post_dump_grace_cycles": 262_144,
        "plateau_qualification": [
            "owner_clock_advancing", "sim_time_advancing", "all_qualified_progress_counters_stable",
            "complete_source_bound_causal_state_bitwise_stable", "global_progress_witness_stable",
            "candidate_catalog_coverage_complete", "no_unresolved_xz",
        ],
        "sim_time_freeze_intervals": 3,
        "sim_time_freeze_interval_seconds": 30,
        "heartbeat_source": "APPENDED_VCD_TIMESTAMP",
        "heartbeat_width_bits": 64,
        "heartbeat_signed": False,
        "heartbeat_cadence_cycles": 16_384,
        "decision_authority": "SHARED_RUNTIME_EVALUATOR_ONLY",
        "outer_runner_independent_exit_logic": False,
        "required_replay_cases": [
            "ADVANCING_VCD_TIMESTAMP", "PLATEAU_SUSPECTED_ONLY",
            "PLATEAU_DUMP_OFF_PLUS_GRACE", "THREE_INTERVAL_TRUE_FREEZE",
        ],
        "planned_dumpoff_state_source": "EXECUTION_BOUND_TB_STICKY_EVENT",
        "post_dumpoff_progress_source": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
        "dump_off_grace_precedes_freeze": True,
        "stop_marker_policy": "ONE_SHOT_LATCHED",
        "required_dumpoff_consistency_replays": [
            "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE",
            "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU",
            "REPEATED_STOP_MARKER_FAIL_CLOSED",
        ],
        "archive_timestamp_binding": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT",
        "termination_sequence": ["TERM", "WAIT", "KILL", "REAP"],
        "disk_write_quota_fail_safe": True,
        "rolling_growth_projection": True,
    }
    for key, wanted in expected_runtime.items():
        if runtime.get(key) != wanted:
            errors.append(f"runtime policy {key} must be {wanted}")

    receipts = contract.get("return_receipts") if isinstance(contract.get("return_receipts"), dict) else {}
    required_receipts = {"catalog", "candidate_matrix", "breadth_evolution", "actual_argv", "tb_source", "elaboration", "runtime", "dump_control", "vcd", "process_tree", "return_manifest"}
    if not required_receipts.issubset(receipts) or not str(receipts.get("vcd", "")).endswith(".vcd"):
        errors.append("formal return receipt paths are incomplete")

    first_fresh = contract.get("first_fresh_controls") if isinstance(contract.get("first_fresh_controls"), dict) else {}
    negative_controls = first_fresh.get("negative_controls") if isinstance(first_fresh.get("negative_controls"), dict) else {}
    required_negative_controls = {
        "missing_soft_reference_receipt",
        "deviation_without_explanation",
        "low_confidence_removal",
        "add_remove_diff_mismatch",
        "candidate_loss",
        "source_identity_drift",
        "size_or_stop_protection_weakened",
    }
    if first_fresh.get("required_for_family_epoch") is not True or first_fresh.get("clean_exact_zip_revalidation") is not True:
        errors.append("first-fresh clean exact-ZIP breadth revalidation is required")
    if set(negative_controls) != required_negative_controls or any(value is not True for value in negative_controls.values()):
        errors.append("first-fresh breadth/evolution negative controls are incomplete")

    return {
        "schema": "server-tb-vcd-bounded-causal-cone-validation-v1",
        "pass": not errors,
        "package_id": contract.get("package_id"),
        "family": contract.get("family"),
        "signal_count": len(signal_ids),
        "role_count": len(set(seen_roles)),
        "boundary_count": len(boundary_ids),
        "candidate_count": len(candidate_ids),
        "matrix_rows": len(rows),
        "diagnostic_round_index": round_index,
        "diagnostic_round_kind": round_kind,
        "direct_driver_leaf_count": sum(1 for values in driver_candidates_by_signal.values() if values),
        "high_probability_candidate_count": len(high_probability_candidates),
        "catalog_source_identity_sha256": catalog_source_identity_sha,
        "soft_reference_signal_count_range": [range_minimum, range_maximum],
        "soft_reference_relation": expected_relation,
        "missing_high_candidate_direct_driver_ids": sorted(missing_high_direct_drivers),
        "warnings": warnings,
        "errors": errors,
        "claim_boundary": "Local source-bound VCD contract only; no production, diagnostic or correctness claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = validate_contract(load(args.contract), args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
