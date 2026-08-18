#!/usr/bin/env python3
"""Calculate and validate a bounded, source-bound diagnostic wall budget."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


SCHEMA = "server-runtime-budget-admission-v1"
DEFAULT_WALL = 3600
SHARED_ABSOLUTE_MAXIMUM_WALL = 86400
AUTHORIZATION_PROFILES = {
    "qadd-v70-pretarget-8400": {
        "source_package_id": "r5_qadd_n7_tailround_lanephase_v70_pmapfix",
        "source_return_sha256": "ae317f36edd28ecf0b9c3bf7d5c7734612d18755932f9fedb371a1203addb369",
        "qualified_progress_source": "PRETARGET_MATRIX_TRANSFER_COMPLETE",
        "measurement_phase": "PRETARGET",
        "target_entry_observed": False,
        "qualified_units_completed": 19,
        "total_units": 30,
        "elapsed_seconds": 3608.29,
        "fixed_overhead_seconds": 0.0,
        "selected_wall_ceiling_seconds": 8400,
        "absolute_maximum_wall_seconds": 8400,
        "require_formal_analysis_identity": False,
        "require_extended_guards": False,
    },
    "qadd-v73-target-progress-15000": {
        "source_package_id": "r5_qadd_n7_tailround_lanephase_v73_w8400v7",
        "source_return_path": "C:/Users/15383/Downloads/r5_qadd_n7_tailround_lanephase_v73_w8400v7_r1786958027042931325_3775010_return.zip",
        "source_return_sha256": "a65425c43962ee172bf4583b4a114b0a5123d0a19eb20a80860c19ac52e2f23c",
        "source_formal_analysis_path": "outputs/qlinearadd_node0007_v73_return_r1786958027042931325_3775010/formal_return_analysis.json",
        "source_formal_analysis_sha256": "f0e7d0298d80c233041be6dd26fda8c6aaaabcca6353586f31cd94cc063bc432",
        "qualified_progress_source": "TARGET_COMPLEMENTARY_PAIR_ACCEPT_CLEAR_OUTPUT",
        "measurement_phase": "TARGET",
        "target_entry_observed": True,
        "qualified_units_completed": 12440,
        "total_units": 18816,
        "elapsed_seconds": 2855.939969378058,
        "fixed_overhead_seconds": 5562.327059702948,
        "selected_wall_ceiling_seconds": 15000,
        "absolute_maximum_wall_seconds": SHARED_ABSOLUTE_MAXIMUM_WALL,
        "user_authorization_exact_text": "qadd预算允许到15000秒确定跑完",
        "user_authorization_utf8_sha256": "60602079640071373a013309304df0d0e9099a2481a93dfe7953298ac3eb8d58",
        "user_authorization_source_thread_id": "019ff027-e7db-72a3-b282-cfad8708da05",
        "require_formal_analysis_identity": True,
        "require_extended_guards": True,
    },
}


def _profile(source: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    requested = source.get("authorization_profile_id")
    if isinstance(requested, str):
        return requested, AUTHORIZATION_PROFILES.get(requested)
    for profile_id, profile in AUTHORIZATION_PROFILES.items():
        if (
            source.get("source_package_id") == profile["source_package_id"]
            and source.get("source_return_sha256") == profile["source_return_sha256"]
        ):
            return profile_id, profile
    return None, None


def _same_number(actual: Any, expected: float) -> bool:
    return (
        isinstance(actual, (int, float))
        and not isinstance(actual, bool)
        and math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-9)
    )


def calculate(request: dict[str, Any]) -> dict[str, Any]:
    source = request.get("source_measurement") if isinstance(request.get("source_measurement"), dict) else {}
    completed = source.get("qualified_units_completed")
    total = source.get("total_pretarget_units")
    elapsed = source.get("elapsed_seconds")
    factor = request.get("safety_factor", 1.25)
    margin = request.get("target_diagnostic_margin_seconds", 900)
    mode = request.get("mode", "MEASURED_PRETARGET_AWARE")
    errors: list[str] = []
    profile_id, profile = _profile(source)
    user_authorization = request.get("user_authorization")
    if not isinstance(completed, int) or isinstance(completed, bool) or completed < 3:
        errors.append("at least three qualified completed pretarget units are required")
    if not isinstance(total, int) or isinstance(total, bool) or total < 1:
        errors.append("total pretarget units must be positive")
    if isinstance(completed, int) and isinstance(total, int) and completed > total:
        errors.append("completed units exceed total pretarget units")
    if not isinstance(elapsed, (int, float)) or isinstance(elapsed, bool) or elapsed <= 0:
        errors.append("elapsed seconds must be positive")
    if not isinstance(factor, (int, float)) or isinstance(factor, bool) or not 1.1 <= float(factor) <= 4.0:
        errors.append("safety factor must be within [1.1,4.0]")
    if not isinstance(margin, int) or isinstance(margin, bool) or not 300 <= margin <= 21600:
        errors.append("target diagnostic margin must be an integer within [300,21600]")
    if profile is None:
        errors.append("measured override does not match an exact authorized source profile")
    else:
        if source.get("source_package_id") != profile["source_package_id"]:
            errors.append("measured override source package differs from the authorized profile")
        if source.get("source_return_sha256") != profile["source_return_sha256"]:
            errors.append("measured override source return identity differs from the authorized profile")
        if source.get("qualified_progress_source") != profile["qualified_progress_source"]:
            errors.append("qualified progress source differs from the authorized measurement")
        if source.get("qualified_units_completed") != profile["qualified_units_completed"]:
            errors.append("qualified completed units differ from the authorized measurement")
        if source.get("total_pretarget_units") != profile["total_units"]:
            errors.append("total units differ from the authorized measurement")
        if not _same_number(source.get("elapsed_seconds"), profile["elapsed_seconds"]):
            errors.append("elapsed seconds differ from the authorized measurement")
        if source.get("target_entry_observed") is not profile["target_entry_observed"]:
            errors.append("target-entry state differs from the authorized measurement")
        if source.get("progress_was_advancing") is not True:
            errors.append("source must prove advancing qualified progress")
        if profile["measurement_phase"] == "TARGET":
            if source.get("source_return_path") != profile["source_return_path"]:
                errors.append("v73 source return path differs from the authorized receipt")
            if source.get("measurement_phase") != "TARGET":
                errors.append("v73 authorization requires target-phase measurement")
            if not _same_number(source.get("fixed_overhead_seconds"), profile["fixed_overhead_seconds"]):
                errors.append("target-entry fixed overhead differs from the authorized measurement")
        if profile["require_formal_analysis_identity"]:
            if source.get("source_formal_analysis_path") != profile["source_formal_analysis_path"]:
                errors.append("v73 formal analysis path differs from the authorized receipt")
            if source.get("source_formal_analysis_sha256") != profile["source_formal_analysis_sha256"]:
                errors.append("v73 formal analysis identity differs from the authorized receipt")
        if profile_id == "qadd-v73-target-progress-15000":
            expected_authorization = {
                "source_thread_id": profile["user_authorization_source_thread_id"],
                "exact_text": profile["user_authorization_exact_text"],
                "utf8_sha256": profile["user_authorization_utf8_sha256"],
                "family": "qlinearadd_node0007",
                "source_package_id": profile["source_package_id"],
                "source_return_sha256": profile["source_return_sha256"],
                "selected_wall_ceiling_seconds": profile["selected_wall_ceiling_seconds"],
                "authorization_scope": "EXACT_V73_MEASURED_RETURN_TO_ONE_NEXT_FRESH_QADD_SUCCESSOR",
            }
            if user_authorization != expected_authorization:
                errors.append("v73 15000-second user authorization binding is missing or differs")
    if mode != "MEASURED_PRETARGET_AWARE":
        errors.append("runtime budget mode is invalid")

    seconds_per_unit = float(elapsed) / int(completed) if not errors else 0.0
    fixed_overhead = float(profile["fixed_overhead_seconds"]) if profile is not None else 0.0
    projected = seconds_per_unit * int(total) if not errors else 0.0
    unmargined_total = fixed_overhead + projected if not errors else 0.0
    recommended = max(
        DEFAULT_WALL,
        math.ceil(fixed_overhead + projected * float(factor) + int(margin)),
    ) if not errors else DEFAULT_WALL
    selected = request.get("selected_wall_ceiling_seconds", recommended)
    absolute_maximum = request.get("absolute_maximum_wall_seconds")
    if not isinstance(selected, int) or isinstance(selected, bool):
        errors.append("selected wall ceiling must be an integer")
        selected = 0
    elif selected < recommended:
        errors.append("selected wall ceiling is below the measured recommendation")
    elif profile is not None and selected > profile["selected_wall_ceiling_seconds"]:
        errors.append("selected wall ceiling exceeds the exact bounded authorized profile maximum")
    elif profile is not None and selected != profile["selected_wall_ceiling_seconds"]:
        errors.append("selected wall ceiling must equal the exact user-authorized profile value")
    if not isinstance(absolute_maximum, int) or isinstance(absolute_maximum, bool):
        errors.append("absolute maximum wall must be an integer")
        absolute_maximum = 0
    else:
        if absolute_maximum > SHARED_ABSOLUTE_MAXIMUM_WALL:
            errors.append("absolute maximum wall exceeds the shared hard maximum")
        if isinstance(selected, int) and not isinstance(selected, bool) and absolute_maximum < selected:
            errors.append("absolute maximum wall is below the selected wall ceiling")
        if profile is not None and absolute_maximum != profile["absolute_maximum_wall_seconds"]:
            errors.append("absolute maximum wall must equal the exact profile-bound value")

    guards = request.get("independent_operational_guards")
    expected_guards = {
        "vcd_operational_budget_bytes": 8_000_000_000,
        "return_budget_bytes": 10_000_000_000,
        "disk_space_guard_enabled": True,
        "growth_projection_enabled": True,
        "write_failure_guard_enabled": True,
        "quota_guard_enabled": True,
    }
    if profile is not None and profile["require_extended_guards"]:
        expected_guards.update({
            "signal_guard_enabled": True,
            "plateau_protection_unchanged": True,
            "return_integrity_fail_closed": True,
        })
    if guards != expected_guards:
        errors.append("independent size/disk/growth/write/quota guards must remain exact")
    projection = {
        "seconds_per_unit": seconds_per_unit,
        "projected_pretarget_seconds": projected,
        "safety_factor": float(factor) if isinstance(factor, (int, float)) else 0.0,
        "target_diagnostic_margin_seconds": margin,
        "recommended_wall_ceiling_seconds": recommended,
        "formula": "CEIL(elapsed/completed*total*safety_factor+target_margin)",
    }
    if profile is not None and profile["measurement_phase"] == "TARGET":
        projection.update({
            "fixed_overhead_seconds": fixed_overhead,
            "unmargined_projected_total_seconds": unmargined_total,
            "projection_basis": "FIXED_PRETARGET_PLUS_MEASURED_TARGET_RATE",
            "formula": "CEIL(fixed_overhead+elapsed/completed*total*safety_factor+target_margin)",
        })
    output = {
        "schema": SCHEMA,
        "package_id": request.get("package_id"),
        "execution_id": request.get("execution_id"),
        "mode": mode,
        "source_measurement": source,
        "projection": projection,
        "selected_wall_ceiling_seconds": selected,
        "absolute_maximum_wall_seconds": absolute_maximum,
        "independent_operational_guards": guards,
        "errors": errors,
        "pass": not errors,
        "claim_boundary": "Wall-budget admission only; disk/growth/write/quota guards remain independent and no DUT result is claimed.",
    }
    if profile_id == "qadd-v73-target-progress-15000":
        output["authorization_profile_id"] = profile_id
        output["user_authorization"] = user_authorization
    return output


def validate(receipt: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(receipt, dict) or receipt.get("schema") != SCHEMA:
        return {"pass": False, "errors": ["invalid runtime budget admission schema"]}
    request = {
        "package_id": receipt.get("package_id"),
        "execution_id": receipt.get("execution_id"),
        "mode": receipt.get("mode"),
        "source_measurement": receipt.get("source_measurement"),
        "user_authorization": receipt.get("user_authorization"),
        "safety_factor": receipt.get("projection", {}).get("safety_factor"),
        "target_diagnostic_margin_seconds": receipt.get("projection", {}).get("target_diagnostic_margin_seconds"),
        "selected_wall_ceiling_seconds": receipt.get("selected_wall_ceiling_seconds"),
        "absolute_maximum_wall_seconds": receipt.get("absolute_maximum_wall_seconds"),
        "independent_operational_guards": receipt.get("independent_operational_guards"),
    }
    expected = calculate(request)
    for key in ("authorization_profile_id", "user_authorization", "projection", "selected_wall_ceiling_seconds", "absolute_maximum_wall_seconds", "independent_operational_guards"):
        if receipt.get(key) != expected.get(key):
            errors.append(f"{key} does not match deterministic recomputation")
    if receipt.get("pass") is not True or expected.get("pass") is not True:
        errors.extend(expected.get("errors", []))
    return {"schema": SCHEMA, "pass": not errors, "errors": sorted(set(errors))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.request is None) == (args.receipt is None):
        parser.error("exactly one of --request or --receipt is required")
    document = json.loads((args.request or args.receipt).read_text(encoding="utf-8"))
    output = calculate(document) if args.request else validate(document)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if output["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
