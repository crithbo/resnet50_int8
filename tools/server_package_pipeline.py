#!/usr/bin/env python3
"""Compile next-fresh server-package rules into a shadow build profile.

This v1 tool is intentionally non-mutating: it does not invoke a family
builder, create a ZIP, rotate storage, run a validator, or change release
state.  It makes the eventual single build entry enforceable by compiling
rule identities, changed surfaces, validator identities and reusable receipts
before expensive materialization begins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
HEX64 = set("0123456789abcdef")


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def semantic_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode(
            "utf-8"
        )
        + b"\n"
    )


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in HEX64 for character in value)
    )


def _file_receipt(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _surface_hashes(
    inputs: list[dict[str, Any]], vocabulary: set[str]
) -> dict[str, str]:
    by_surface: dict[str, list[dict[str, Any]]] = {
        surface: [] for surface in sorted(vocabulary)
    }
    for item in inputs:
        surface = item.get("surface")
        if surface in by_surface:
            by_surface[surface].append(
                {
                    "path": item.get("path"),
                    "bytes": item.get("bytes"),
                    "sha256": item.get("sha256"),
                }
            )
    return {
        surface: semantic_sha256(sorted(items, key=lambda item: str(item["path"])))
        for surface, items in by_surface.items()
    }


def _combined_surface_hash(
    gate: dict[str, Any], surface_hashes: dict[str, str]
) -> str:
    return semantic_sha256(
        {
            surface: surface_hashes[surface]
            for surface in sorted(gate["surfaces"])
        }
    )


def _validator_identity(
    validators: dict[str, Any], gate_id: str
) -> dict[str, Any] | None:
    value = validators.get(gate_id)
    return value if isinstance(value, dict) else None


def _matching_receipt(
    candidates: list[dict[str, Any]],
    gate: dict[str, Any],
    surface_sha256: str,
    validator: dict[str, Any] | None,
) -> dict[str, Any] | None:
    for candidate in candidates:
        if candidate.get("gate_id") != gate["gate_id"]:
            continue
        if candidate.get("result") != "PASS":
            continue
        if candidate.get("exact_bytes_equal") is not True:
            continue
        if candidate.get("direct_consumers_equal") is not True:
            continue
        if candidate.get("surface_sha256") != surface_sha256:
            continue
        if candidate.get("semantic_version") != gate["semantic_version"]:
            continue
        if gate["validator_identity_required"]:
            if validator is None:
                continue
            if candidate.get("validator_sha256") != validator.get(
                "validator_sha256"
            ):
                continue
            if candidate.get("fixture_sha256") != validator.get("fixture_sha256"):
                continue
        return candidate
    return None


def compile_profile(
    spec: dict[str, Any],
    registry: dict[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    """Collect every cheap contract error and compile all gate dispositions."""

    errors: list[str] = []
    warnings: list[str] = []
    supported_diagnostic_modes = {
        "OBSERVER_ONLY_WIDE_CAUSAL",
        "TB_VCD_BOUNDED_CAUSAL_CONE",
    }
    diagnostic_mode = spec.get(
        "diagnostic_mode", "OBSERVER_ONLY_WIDE_CAUSAL"
    )
    if diagnostic_mode not in supported_diagnostic_modes:
        errors.append(f"unsupported diagnostic_mode: {diagnostic_mode}")
    vocabulary = set(registry.get("surface_vocabulary", []))
    causal_vocabulary = set(registry.get("causal_blocking_classes", []))
    gates = registry.get("gates", [])
    gate_ids = [gate.get("gate_id") for gate in gates if isinstance(gate, dict)]
    if registry.get("schema") != "server-package-build-gate-registry-v1":
        errors.append("registry schema mismatch")
    if registry.get("mode") != "SHADOW_ONLY_NEXT_FRESH":
        errors.append("registry mode must be SHADOW_ONLY_NEXT_FRESH")
    if causal_vocabulary != {
        "server_start",
        "actual_input",
        "state_safety",
        "return",
    }:
        errors.append("registry causal blocking classes mismatch")
    duplicates = [
        gate_id
        for gate_id, count in Counter(gate_ids).items()
        if gate_id is not None and count > 1
    ]
    if duplicates:
        errors.append(f"duplicate gate ids: {sorted(duplicates)}")
    for gate in gates:
        if not isinstance(gate, dict):
            errors.append("registry gate must be an object")
            continue
        gate_id = gate.get("gate_id")
        classes = gate.get("causal_blocking_classes")
        if not isinstance(classes, list):
            errors.append(f"{gate_id}: causal_blocking_classes must be an array")
            classes = []
        unknown_classes = sorted(set(classes) - causal_vocabulary)
        if unknown_classes:
            errors.append(f"{gate_id}: unknown causal classes: {unknown_classes}")
        activation = gate.get("activation")
        if activation not in {
            "always",
            "changed_surface",
            "record_only",
            "first_fresh_after_rule_change",
            "required_next_fresh_after_activation",
        }:
            errors.append(f"{gate_id}: invalid activation")
        selected_modes = gate.get("selected_modes")
        if selected_modes is not None:
            if (
                not isinstance(selected_modes, list)
                or not selected_modes
                or any(
                    mode not in supported_diagnostic_modes
                    for mode in selected_modes
                )
                or len(selected_modes) != len(set(selected_modes))
            ):
                errors.append(f"{gate_id}: invalid selected_modes")
        if activation == "record_only":
            if classes:
                errors.append(f"{gate_id}: record-only gate cannot have causal classes")
        elif not classes:
            errors.append(f"{gate_id}: blocking gate lacks causal mapping")
        if not isinstance(gate.get("blocking_effect"), str) or not gate.get(
            "blocking_effect"
        ):
            errors.append(f"{gate_id}: blocking_effect is required")
        if gate.get("execution_group") not in {
            "prebuild_aggregate",
            "staging_tree_aggregate",
            "final_zip_release_driver",
            "storage_rotation",
        }:
            errors.append(f"{gate_id}: invalid execution_group")
        if not isinstance(gate.get("cheap_prebuild_eligible"), bool):
            errors.append(f"{gate_id}: cheap_prebuild_eligible must be boolean")
        enforcement = gate.get("enforcement", "shadow_only")
        if enforcement not in {"shadow_only", "required_next_fresh"}:
            errors.append(f"{gate_id}: invalid enforcement")
        if (
            gate_id == "source_bound_observer_generation"
            and enforcement != "required_next_fresh"
        ):
            errors.append(
                "source_bound_observer_generation must be required_next_fresh"
            )
        if (
            gate_id == "post_sim_return_core"
            and enforcement != "required_next_fresh"
        ):
            errors.append("post_sim_return_core must be required_next_fresh")
        if (
            gate_id == "first_fresh_extra_audit"
            and enforcement != "required_next_fresh"
        ):
            errors.append("first_fresh_extra_audit must be required_next_fresh")

    if spec.get("schema") != "server-package-build-spec-v1":
        errors.append("spec schema mismatch")
    if spec.get("lifecycle") != "NEXT_FRESH_SUCCESSOR":
        errors.append("only NEXT_FRESH_SUCCESSOR is accepted")
    if spec.get("shadow_only") is not True:
        errors.append("v1 is shadow-only")
    if spec.get("current_package_impact") is not False:
        errors.append("current package impact must be false")
    for field in ("package_id", "family"):
        if not isinstance(spec.get(field), str) or not spec[field]:
            errors.append(f"{field} must be a non-empty string")

    rule_change_epoch = spec.get("rule_change_epoch")
    if not isinstance(rule_change_epoch, dict):
        errors.append("rule_change_epoch must be an object")
        rule_change_epoch = {}
    epoch_id = rule_change_epoch.get("epoch_id")
    if not isinstance(epoch_id, str) or not epoch_id:
        errors.append("rule_change_epoch.epoch_id must be non-empty")
        epoch_id = ""
    first_fresh_after_change = rule_change_epoch.get(
        "first_fresh_after_change"
    )
    if not isinstance(first_fresh_after_change, bool):
        errors.append(
            "rule_change_epoch.first_fresh_after_change must be boolean"
        )
        first_fresh_after_change = False
    prior_audit_receipt = rule_change_epoch.get("prior_audit_receipt")
    normalized_prior_audit: dict[str, Any] | None = None
    if first_fresh_after_change:
        if prior_audit_receipt is not None:
            errors.append(
                "first fresh package cannot declare a prior audit receipt"
            )
    elif not isinstance(prior_audit_receipt, dict):
        errors.append("non-first package requires prior_audit_receipt")
    else:
        relative = prior_audit_receipt.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append("prior_audit_receipt.path is invalid")
        else:
            receipt_path = (workspace_root / relative).resolve()
            try:
                receipt_path.relative_to(workspace_root.resolve())
            except ValueError:
                errors.append(
                    f"prior audit receipt escapes workspace: {relative}"
                )
            else:
                if not receipt_path.is_file():
                    errors.append(f"prior audit receipt missing: {relative}")
                else:
                    actual_sha = sha256_file(receipt_path)
                    if prior_audit_receipt.get("sha256") != actual_sha:
                        errors.append("prior audit receipt sha256 mismatch")
                    try:
                        prior_report = load_json(receipt_path)
                    except (OSError, json.JSONDecodeError) as exc:
                        errors.append(f"prior audit receipt unreadable: {exc}")
                    else:
                        if (
                            prior_report.get("schema")
                            != "server-first-fresh-extra-audit-validation-v1"
                            or prior_report.get("pass") is not True
                            or prior_report.get("family") != spec.get("family")
                            or prior_report.get("rule_change_epoch_id") != epoch_id
                        ):
                            errors.append(
                                "prior audit receipt identity/pass mismatch"
                            )
                        else:
                            normalized_prior_audit = {
                                "path": relative,
                                "sha256": actual_sha,
                                "package_id": prior_report.get("package_id", ""),
                            }

    changed = spec.get("changed_surfaces", [])
    if not isinstance(changed, list):
        errors.append("changed_surfaces must be an array")
        changed = []
    unknown_changed = sorted(
        {surface for surface in changed if surface not in vocabulary}
    )
    if unknown_changed:
        errors.append(f"unknown changed surfaces: {unknown_changed}")
    if len(changed) != len(set(changed)):
        errors.append("changed_surfaces contains duplicates")
    changed_set = set(changed) & vocabulary

    inputs = spec.get("inputs", [])
    if not isinstance(inputs, list) or not inputs:
        errors.append("inputs must contain at least one file receipt")
        inputs = []
    normalized_inputs: list[dict[str, Any]] = []
    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            errors.append(f"inputs[{index}] must be an object")
            continue
        relative = item.get("path")
        surface = item.get("surface")
        if not isinstance(relative, str) or not relative:
            errors.append(f"inputs[{index}].path is invalid")
            continue
        if surface not in vocabulary:
            errors.append(f"inputs[{index}].surface is unknown: {surface}")
        path = (workspace_root / relative).resolve()
        try:
            path.relative_to(workspace_root.resolve())
        except ValueError:
            errors.append(f"inputs[{index}] escapes workspace: {relative}")
            continue
        if not path.is_file():
            errors.append(f"input file missing: {relative}")
            continue
        actual = _file_receipt(path, workspace_root)
        if item.get("bytes") != actual["bytes"]:
            errors.append(f"input bytes mismatch: {relative}")
        if item.get("sha256") != actual["sha256"]:
            errors.append(f"input sha256 mismatch: {relative}")
        normalized_inputs.append(
            {
                **actual,
                "surface": surface,
            }
        )

    rule_receipts: list[dict[str, Any]] = []
    for relative in registry.get("required_rule_paths", []):
        path = (workspace_root / relative).resolve()
        if not path.is_file():
            errors.append(f"required rule missing: {relative}")
            continue
        rule_receipts.append(_file_receipt(path, workspace_root))

    validators = spec.get("validators", {})
    if not isinstance(validators, dict):
        errors.append("validators must be an object")
        validators = {}
    for gate_id, identity in validators.items():
        if gate_id not in gate_ids:
            errors.append(f"validator references unknown gate: {gate_id}")
            continue
        if not isinstance(identity, dict):
            errors.append(f"validator identity is not an object: {gate_id}")
            continue
        for field in ("validator_sha256", "fixture_sha256"):
            if not is_sha256(identity.get(field)):
                errors.append(f"{gate_id}.{field} is not sha256")

    candidates = spec.get("receipt_reuse_candidates", [])
    if not isinstance(candidates, list):
        errors.append("receipt_reuse_candidates must be an array")
        candidates = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            errors.append(f"receipt_reuse_candidates[{index}] must be an object")
        elif candidate.get("gate_id") not in gate_ids:
            errors.append(
                f"receipt candidate references unknown gate: "
                f"{candidate.get('gate_id')}"
            )

    require_all_cheap = spec.get("require_all_cheap_checks", False)
    if not isinstance(require_all_cheap, bool):
        errors.append("require_all_cheap_checks must be boolean")
        require_all_cheap = False
    if require_all_cheap:
        supplied_surfaces = {
            item.get("surface")
            for item in normalized_inputs
            if isinstance(item, dict)
        }
        if diagnostic_mode == "OBSERVER_ONLY_WIDE_CAUSAL":
            required_source_bound_surfaces = {
                "probe_catalog",
                "probe_plan",
                "package_local_hdl",
                "parser",
            }
            incomplete_label = "source-bound observer generation inputs"
        else:
            required_source_bound_surfaces = {
                "probe_catalog",
                "probe_plan",
                "package_local_hdl",
                "waveform",
            }
            incomplete_label = "source-bound TB VCD causal-cone inputs"
        missing_source_bound_surfaces = sorted(
            required_source_bound_surfaces - supplied_surfaces
        )
        if missing_source_bound_surfaces:
            errors.append(
                f"{incomplete_label} are incomplete: "
                f"{missing_source_bound_surfaces}"
            )
    cheap_reports = spec.get("cheap_check_reports", [])
    if not isinstance(cheap_reports, list):
        errors.append("cheap_check_reports must be an array")
        cheap_reports = []
    cheap_by_gate: dict[str, dict[str, Any]] = {}
    cheap_results: list[dict[str, Any]] = []
    for index, item in enumerate(cheap_reports):
        if not isinstance(item, dict):
            errors.append(f"cheap_check_reports[{index}] must be an object")
            continue
        gate_id = item.get("gate_id")
        if gate_id not in gate_ids:
            errors.append(f"cheap check references unknown gate: {gate_id}")
            continue
        if gate_id in cheap_by_gate:
            errors.append(f"duplicate cheap check report: {gate_id}")
            continue
        gate = next(gate for gate in gates if gate.get("gate_id") == gate_id)
        if gate.get("cheap_prebuild_eligible") is not True:
            errors.append(f"gate is not cheap-prebuild eligible: {gate_id}")
        relative = item.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append(f"cheap_check_reports[{index}].path is invalid")
            continue
        path = (workspace_root / relative).resolve()
        try:
            path.relative_to(workspace_root.resolve())
        except ValueError:
            errors.append(f"cheap check escapes workspace: {relative}")
            continue
        if not path.is_file():
            errors.append(f"cheap check report missing: {relative}")
            continue
        actual_sha = sha256_file(path)
        if item.get("sha256") != actual_sha:
            errors.append(f"cheap check report sha256 mismatch: {relative}")
            continue
        try:
            report = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"cheap check report unreadable: {relative}: {exc}")
            continue
        report_errors = report.get("errors", [])
        report_warnings = report.get("warnings", [])
        if (
            report.get("schema") != "server-package-cheap-check-result-v1"
            or report.get("gate_id") != gate_id
            or not isinstance(report.get("pass"), bool)
            or not isinstance(report_errors, list)
            or not all(isinstance(value, str) for value in report_errors)
            or not isinstance(report_warnings, list)
            or not all(isinstance(value, str) for value in report_warnings)
        ):
            errors.append(f"cheap check report contract invalid: {relative}")
            continue
        cheap_by_gate[gate_id] = report
        if report["pass"] is not True:
            if gate.get("activation") == "record_only":
                warnings.extend(
                    f"{gate_id}: {message}" for message in report_errors
                )
            else:
                errors.extend(
                    f"{gate_id}: {message}" for message in report_errors
                )
        warnings.extend(f"{gate_id}: {message}" for message in report_warnings)
        cheap_results.append(
            {
                "gate_id": gate_id,
                "path": relative,
                "sha256": actual_sha,
                "pass": report["pass"],
                "error_count": len(report_errors),
                "warning_count": len(report_warnings),
            }
        )
    eligible_cheap = sorted(
        gate["gate_id"]
        for gate in gates
        if gate.get("cheap_prebuild_eligible") is True
        and diagnostic_mode in gate.get(
            "selected_modes", sorted(supported_diagnostic_modes)
        )
    )
    missing_cheap = sorted(set(eligible_cheap) - set(cheap_by_gate))
    if require_all_cheap and missing_cheap:
        errors.append(f"missing required cheap check reports: {missing_cheap}")

    surface_hashes = _surface_hashes(normalized_inputs, vocabulary)
    dispositions: list[dict[str, Any]] = []
    required_validator_gates: list[str] = []
    for gate in gates:
        gate_id = gate["gate_id"]
        activation = gate["activation"]
        selected_modes = gate.get(
            "selected_modes", sorted(supported_diagnostic_modes)
        )
        relevant_changed = changed_set & set(gate["surfaces"])
        validator = _validator_identity(validators, gate_id)
        surface_sha = _combined_surface_hash(gate, surface_hashes)
        cache_key = semantic_sha256(
            {
                "gate_id": gate_id,
                "semantic_version": gate["semantic_version"],
                "surface_sha256": surface_sha,
                "validator_sha256": (
                    validator.get("validator_sha256") if validator else None
                ),
                "fixture_sha256": (
                    validator.get("fixture_sha256") if validator else None
                ),
            }
        )
        receipt = None
        if diagnostic_mode not in selected_modes:
            disposition = "not_applicable"
            reason = (
                f"gate applies only to diagnostic modes {selected_modes}; "
                f"selected mode is {diagnostic_mode}"
            )
        elif activation == "record_only":
            disposition = "record_only"
            reason = "registry classifies this check as nonblocking metadata"
        elif (
            activation == "first_fresh_after_rule_change"
            and not first_fresh_after_change
        ):
            disposition = "not_applicable"
            reason = (
                "the first fresh package for this family/rule epoch already "
                "has a bound PASS receipt"
            )
        elif activation == "changed_surface" and not relevant_changed:
            disposition = "not_applicable"
            reason = "no affected surface changed"
        else:
            if (
                gate["receipt_reuse_allowed"]
                and not relevant_changed
                and normalized_inputs
            ):
                receipt = _matching_receipt(
                    candidates, gate, surface_sha, validator
                )
            if receipt is not None:
                disposition = "receipt_reuse"
                reason = (
                    "exact bytes, direct consumers, rule semantics, validator "
                    "and fixture identities match"
                )
            else:
                disposition = "blocking_applicable"
                reason = (
                    "affected or always-on gate requires fresh evidence before "
                    "release"
                )
                if gate["validator_identity_required"]:
                    required_validator_gates.append(gate_id)
                    if validator is None:
                        errors.append(
                            f"applicable gate lacks validator identity: {gate_id}"
                        )
        if (
            gate["receipt_reuse_allowed"]
            and candidates
            and receipt is None
            and activation != "record_only"
            and not relevant_changed
        ):
            related = [
                item
                for item in candidates
                if isinstance(item, dict) and item.get("gate_id") == gate_id
            ]
            if related:
                warnings.append(
                    f"stale or incomplete receipt rejected for gate: {gate_id}"
                )
        dispositions.append(
            {
                "gate_id": gate_id,
                "phase": gate["phase"],
                "disposition": disposition,
                "reason": reason,
                "causal_blocking_classes": gate[
                    "causal_blocking_classes"
                ],
                "blocking_effect": gate["blocking_effect"],
                "execution_group": gate["execution_group"],
                "enforcement": gate.get("enforcement", "shadow_only"),
                "cache_key": cache_key,
                "receipt": receipt,
            }
        )

    counts = Counter(item["disposition"] for item in dispositions)
    preflight = {
        "pass": not errors,
        "errors": errors,
        "warnings": warnings,
        "all_errors_collected": True,
    }
    return {
        "schema": "server-package-build-profile-v1",
        "mode": "SHADOW_ONLY_NEXT_FRESH",
        "package_id": spec.get("package_id", ""),
        "family": spec.get("family", ""),
        "lifecycle": spec.get("lifecycle", ""),
        "current_package_impact": spec.get("current_package_impact"),
        "rule_change_epoch": {
            "epoch_id": epoch_id,
            "first_fresh_after_change": first_fresh_after_change,
            "prior_audit_receipt": normalized_prior_audit,
        },
        "contract_valid": not errors,
        "preflight": preflight,
        "aggregate_prebuild": {
            "top_level_invocations": 1,
            "require_all_cheap_checks": require_all_cheap,
            "eligible_gate_ids": eligible_cheap,
            "supplied_results": cheap_results,
            "missing_gate_ids": missing_cheap,
            "coverage_complete": not missing_cheap,
            "all_errors_collected": True,
        },
        "rule_receipts": rule_receipts,
        "registry_identity": {
            "schema": registry.get("schema"),
            "semantic_sha256": semantic_sha256(registry),
        },
        "validator_identities": {
            gate_id: {
                "validator_sha256": identity.get("validator_sha256"),
                "fixture_sha256": identity.get("fixture_sha256"),
            }
            for gate_id, identity in sorted(validators.items())
            if gate_id in gate_ids and isinstance(identity, dict)
        },
        "changed_surfaces": sorted(changed_set),
        "surface_hashes": surface_hashes,
        "gate_dispositions": dispositions,
        "required_validator_gates": sorted(set(required_validator_gates)),
        "cache_plan": {
            "reused_gate_count": counts["receipt_reuse"],
            "blocking_gate_count": counts["blocking_applicable"],
            "record_only_gate_count": counts["record_only"],
            "not_applicable_gate_count": counts["not_applicable"],
        },
        "execution_contract": {
            "prebuild_aggregate_top_level_invocations": 1,
            "staging_tree_aggregate_top_level_invocations": 1,
            "final_zip_release_driver_top_level_invocations": 1,
            "final_zip_subgates": sorted(
                gate["gate_id"]
                for gate in gates
                if gate.get("execution_group") == "final_zip_release_driver"
            ),
            "rebuild_per_single_error_forbidden": True,
            "final_zip_same_sha_reuses_exact_content_receipt": True,
            "final_zip_changed_sha_requires_one_fresh_release_driver": True,
        },
        "claim_boundary": {
            "changes_current_package": False,
            "builds_zip": False,
            "runs_family_validator": False,
            "changes_family_release": False,
            "blocking_promotion_authorized": False,
            "source_bound_gate_required_next_fresh": True,
            "post_sim_return_gate_required_next_fresh": True,
            "first_fresh_extra_audit_required": first_fresh_after_change,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile a next-fresh shadow build profile; no package is built."
        )
    )
    parser.add_argument("command", choices=["prepare"])
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    workspace = args.workspace_root.resolve()
    spec = load_json(args.spec.resolve())
    registry = load_json(args.registry.resolve())
    profile = compile_profile(spec, registry, workspace)
    write_json(args.output.resolve(), profile)
    print(
        json.dumps(
            {
                "schema": profile["schema"],
                "mode": profile["mode"],
                "contract_valid": profile["contract_valid"],
                "error_count": len(profile["preflight"]["errors"]),
                "warning_count": len(profile["preflight"]["warnings"]),
                "cache_plan": profile["cache_plan"],
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if profile["contract_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
