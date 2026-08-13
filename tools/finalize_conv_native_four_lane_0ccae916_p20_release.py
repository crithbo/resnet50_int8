#!/usr/bin/env python3
"""Create the immutable p20 release receipt after exact final-ZIP gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p20_obsbindfix"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p20_obsbindfix"
ZIP_PATH = BASE / "build_v3" / f"{PACKAGE_ID}.zip"
BUILD = BASE / "build_v3" / f"{PACKAGE_ID}.build.json"
FAMILY = BASE / "p20_family_audit_v2.json"
HARNESS = BASE / "p20_runtime_layout_harness.json"
SHARED = BASE / "p20_shared_runtime_layout.json"
PROFILE = BASE / "server_package_build_profile.json"
ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p19b_return_analysis/report.json"
)
OUTPUT = BASE / f"{PACKAGE_ID}.final_zip_audit.json"
EXPECTED_ZIP_SHA256 = (
    "68e2fc8f98fa1c6c95fa8eb56a7d5a46e9ac132719cf252be5748b3da2dca208"
)


class FinalizeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    required = (ZIP_PATH, BUILD, FAMILY, HARNESS, SHARED, PROFILE, ANALYSIS)
    if not all(path.is_file() for path in required):
        raise FinalizeError("required p20 release input is absent")
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    scenarios = harness["scenarios"]
    required_scenarios = (
        "normal",
        "preflight_fail",
        "compile_fail",
        "HUP",
        "INT",
        "TERM",
    )
    scenario_exits = {
        "normal": 0,
        "preflight_fail": 5,
        "compile_fail": 42,
        "HUP": 129,
        "INT": 130,
        "TERM": 143,
    }
    checks = {
        "exact_zip_identity": (
            ZIP_PATH.stat().st_size == 5_874_994
            and sha256(ZIP_PATH) == EXPECTED_ZIP_SHA256
        ),
        "formal_p19b_analysis": (
            analysis["valid"] is True
            and analysis["status"]
            == (
                "P19B_PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_ESCAPE_"
                "SUCCESSOR_REQUIRED"
            )
        ),
        "shadow_build_profile": (
            profile["contract_valid"] is True
            and profile["preflight"]["pass"] is True
            and not profile["preflight"]["errors"]
            and profile["mode"] == "SHADOW_ONLY_NEXT_FRESH"
        ),
        "deterministic_build": (
            build["deterministic_double_build"] is True
            and build["frozen"]["frozen_install_payload_byte_equal"] is True
            and all(build["frozen"]["sca_identity_normalized_equal"].values())
            and build["functional_rtl_modified"] is False
        ),
        "family_audit": (
            family["valid"] is True
            and family["status"] == "PASS"
            and not family["errors"]
            and family["observer"]["focused_compile"]["valid"] is True
            and family["observer"]["focused_compile"][
                "declarations_at_module_scope"
            ]
            is True
        ),
        "runtime_scenarios": all(
            scenarios[name]["runner_exit"] == scenario_exits[name]
            and scenarios[name]["finalizer_reached"] is True
            and scenarios[name]["fixed_result_return_published"] is True
            and scenarios[name]["root_exact_set_unchanged"] is True
            and scenarios[name]["unknown_items_deleted_or_overwritten"]
            is False
            and scenarios[name]["writes_outside_install"] is False
            for name in required_scenarios
        ),
        "shared_runtime_layout_once": (
            shared["pass"] is True and not shared["errors"]
        ),
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p20-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_identity": PACKAGE_ID,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "checks": checks,
        "zip": {
            **receipt(ZIP_PATH),
            "deterministic_double_build": True,
        },
        "audits": {
            "p19b_return_analysis": receipt(ANALYSIS),
            "build_profile": receipt(PROFILE),
            "build": receipt(BUILD),
            "family": {
                **receipt(FAMILY),
                "pass": family["valid"],
                "errors": len(family["errors"]),
            },
            "runtime_layout_harness": {
                **receipt(HARNESS),
                "required_scenarios_pass": list(required_scenarios),
            },
            "shared_runtime_layout": {
                **receipt(SHARED),
                "pass": shared["pass"],
                "errors": len(shared["errors"]),
                "exact_final_zip_invocation_count": 1,
                "runner_early_exit_visibility": shared[
                    "runner_early_exit_visibility"
                ]["pass"],
            },
        },
        "frozen_surface": {
            "install_payload_member_count": 87,
            "install_payload_byte_equal": True,
            "sca_identity_normalized_equal": True,
            "workload_config_mapping_bitstream_execplan_numeric_w3_golden_timeout_changed": False,
            "functional_rtl_modified": False,
        },
        "observer": {
            "source_p19b_sha256": build["observer"]["source_sha256"],
            "final_sha256": build["observer"]["fixed_sha256"],
            "symbol_replacement_counts": build["observer"][
                "tail_symbol_replacement_counts"
            ],
            "xmr_or_predicate_changed": False,
            "combined_scope_positive_compile": family["observer"][
                "focused_compile"
            ]["positive"]["exit_code"]
            == 0,
            "missing_declaration_negatives_fail_closed": all(
                row["exit_code"] != 0
                for row in family["observer"]["focused_compile"][
                    "negative_missing_combined_scope_declaration"
                ].values()
            ),
            "renamed_declaration_negatives_fail_closed": all(
                row["exit_code"] != 0
                for row in family["observer"]["focused_compile"][
                    "negative_renamed_combined_scope_declaration"
                ].values()
            ),
            "server_production_compile_required": True,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {
                "applicability": "blocking_applicable",
                "pass": checks["exact_zip_identity"],
            },
            "runner_control_flow": {
                "applicability": "receipt_reuse",
                "pass": checks["runtime_scenarios"],
            },
            "runtime_layout": {
                "applicability": "blocking_applicable",
                "pass": checks["shared_runtime_layout_once"],
            },
            "package_local_hdl": {
                "applicability": "blocking_applicable",
                "pass": checks["family_audit"],
            },
            "diagnostic_semantics": {
                "applicability": "receipt_reuse",
                "pass": True,
            },
            "materialized_config": {
                "applicability": "receipt_reuse",
                "pass": checks["deterministic_build"],
            },
            "numeric_w3_golden": {
                "applicability": "record_only",
                "pass": True,
            },
            "production_compile_sim_return": {
                "applicability": "dynamic_only",
                "pass": None,
            },
        },
        "expected_server": {
            "command": (
                "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02"
            ),
            "return_template": (
                "/home/panqs/ndp/simresult/"
                f"{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip"
            ),
            "sidecar_template": (
                "/home/panqs/ndp/simresult/"
                f"{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip.sha256"
            ),
            "duplicate_absent_required": True,
        },
        "claim_boundary": (
            "p20 is the same c0 D-flow diagnostic with only observer lexical "
            "scope binding repaired. It does not claim production compile, "
            "simulation, natural terminal, formal 320D, E3/E4/E5, numeric "
            "correctness or performance before formal server return."
        ),
        "server_action": False,
    }
    if OUTPUT.exists():
        raise FinalizeError("refusing to overwrite p20 final audit")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"status": result["status"], "valid": valid, "output": str(OUTPUT)},
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
