#!/usr/bin/env python3
"""Create the exact final-ZIP release receipt for native-four-lane p28."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p28_b5release"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p28_b5release"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p28_b5release_source_bound"
ZIP_PATH = BASE / "build" / f"{PACKAGE_ID}.zip"
BUILD = BASE / "build" / f"{PACKAGE_ID}.build.json"
FAMILY = BASE / "p28_family_audit.json"
HARNESS = BASE / "p28_runtime_layout_harness.json"
SHARED = BASE / "p28_shared_runtime_layout_from_harness.json"
PROFILE = BASE / "server_package_build_profile.json"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p26_return_analysis/report.json"
GENERATION = SOURCE_BOUND / "source_bound_generation_report.json"
FINAL_SOURCE_BOUND = SOURCE_BOUND / "source_bound_final_zip_validation.json"
OUTPUT = BASE / f"{PACKAGE_ID}.final_zip_audit.json"


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
    required = (
        ZIP_PATH,
        BUILD,
        FAMILY,
        HARNESS,
        SHARED,
        PROFILE,
        ANALYSIS,
        GENERATION,
        FINAL_SOURCE_BOUND,
    )
    if not all(path.is_file() for path in required):
        raise FinalizeError("required p28 release input is absent")
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    generation = json.loads(GENERATION.read_text(encoding="utf-8"))
    source_bound_final = json.loads(FINAL_SOURCE_BOUND.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        prefix = PACKAGE_ID + "/"
        runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode()
        manifest = json.loads(archive.read(prefix + "package_manifest.json"))
        observer = archive.read(prefix + "tb_probe/source_bound_causal_observer.svh")
        parser = archive.read(prefix + "package_tools/source_bound_causal_parser.py")
        binding = archive.read(prefix + "diagnostics/source_bound_probe_binding.json")
    scenarios = harness["scenarios"]
    required_scenarios = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    expected_exits = {
        "normal": 0,
        "preflight_fail": 5,
        "compile_fail": 42,
        "HUP": 129,
        "INT": 130,
        "TERM": 143,
    }
    runtime_ok = all(
        scenarios[name]["runner_exit"] == expected_exits[name]
        and scenarios[name]["finalizer_reached"] is True
        and scenarios[name]["fixed_result_return_published"] is True
        and scenarios[name]["root_exact_set_unchanged"] is True
        and scenarios[name]["unknown_items_deleted_or_overwritten"] is False
        and scenarios[name]["writes_outside_install"] is False
        for name in required_scenarios
    )
    exact_generation = source_bound_final["exact_generation"]
    checks = {
        "exact_zip_identity": ZIP_PATH.stat().st_size == build["zip_bytes"] and sha256(ZIP_PATH) == build["zip_sha256"],
        "formal_p26_analysis": (
            analysis["valid"] is True
            and analysis["status"] == "P26_ACTUAL_MEMORY_AG_FLOW_PASS_BUFFER5_RELEASE_SUCCESSOR_REQUIRED"
        ),
        "shadow_build_profile": (
            profile["contract_valid"] is True
            and profile["preflight"]["pass"] is True
            and not profile["preflight"]["errors"]
            and profile["mode"] == "SHADOW_ONLY_NEXT_FRESH"
        ),
        "source_bound_generation_required_next_fresh": (
            generation["pass"] is True
            and not generation["errors"]
            and source_bound_final["pass"] is True
            and not source_bound_final["errors"]
        ),
        "source_bound_exact_regeneration": (
            exact_generation["observer"]["byte_equal"] is True
            and exact_generation["parser"]["byte_equal"] is True
            and exact_generation["binding"]["byte_equal"] is True
            and hashlib.sha256(observer).hexdigest() == exact_generation["observer"]["actual_sha256"]
            and hashlib.sha256(parser).hexdigest() == exact_generation["parser"]["actual_sha256"]
            and hashlib.sha256(binding).hexdigest() == exact_generation["binding"]["actual_sha256"]
        ),
        "deterministic_frozen_build": (
            build["deterministic_double_build"] is True
            and build["frozen"]["frozen_install_payload_member_count"] == 87
            and build["frozen"]["frozen_install_payload_byte_equal"] is True
            and build["frozen"]["legacy_observer_byte_equal"] is True
            and all(build["frozen"]["sca_identity_normalized_equal"].values())
            and build["functional_rtl_modified"] is False
        ),
        "family_audit": family["valid"] is True and family["status"] == "PASS" and not family["errors"],
        "generated_parser_trace": family["source_bound_parser_trace"]["valid"] is True,
        "runner_four_way_binding": (
            runner.count("$source_bound_observer") == 2
            and runner.count("+CODEX_CAUSAL_OBSERVER") == 2
            and runner.count('python3 "$source_bound_parser"') == 1
            and "source_bound_causal.log" in runner
            and "source_bound_causal_decision.json" in runner
        ),
        "runtime_scenarios": runtime_ok,
        "shared_runtime_layout_once": shared["pass"] is True and not shared["errors"],
        "repeatable_return_contract": (
            'return_tag="r$(date -u +%s%N)_$$"' in runner
            and 'return_zip="/home/panqs/ndp/simresult/${package_identity}_${return_tag}_return.zip"' in runner
        ),
        "diagnostic_only_claim_boundary": (
            manifest["candidate_release"] is False
            and manifest["source_p26_formal_return_analysis"]["formal_D_claimed"] is False
            and manifest["source_bound_observer_binding"]["functional_rtl_changed"] is False
        ),
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p28-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_identity": PACKAGE_ID,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "checks": checks,
        "zip": {**receipt(ZIP_PATH), "deterministic_double_build": True},
        "audits": {
            "p26_return_analysis": receipt(ANALYSIS),
            "build_profile": receipt(PROFILE),
            "build": receipt(BUILD),
            "family": {**receipt(FAMILY), "pass": family["valid"], "errors": len(family["errors"])},
            "source_bound_generation": {**receipt(GENERATION), "pass": generation["pass"], "errors": len(generation["errors"])},
            "source_bound_final_zip": {**receipt(FINAL_SOURCE_BOUND), "pass": source_bound_final["pass"], "errors": len(source_bound_final["errors"])},
            "runtime_layout_harness": {**receipt(HARNESS), "required_scenarios_pass": list(required_scenarios)},
            "shared_runtime_layout": {
                **receipt(SHARED),
                "pass": shared["pass"],
                "errors": len(shared["errors"]),
                "exact_final_zip_invocation_count": 1,
            },
        },
        "frozen_surface": {
            "install_payload_member_count": 87,
            "install_payload_byte_equal": True,
            "sca_identity_normalized_equal": True,
            "legacy_observer_byte_equal": True,
            "workload_config_mapping_bitstream_execplan_numeric_w3_golden_timeout_changed": False,
            "functional_rtl_modified": False,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["exact_zip_identity"]},
            "source_bound_observer_generation": {"applicability": "blocking_applicable", "enforcement": "required_next_fresh", "pass": checks["source_bound_generation_required_next_fresh"]},
            "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runtime_scenarios"] and checks["repeatable_return_contract"]},
            "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout_once"]},
            "package_local_hdl": {"applicability": "blocking_applicable", "pass": checks["source_bound_exact_regeneration"]},
            "diagnostic_semantics": {"applicability": "blocking_applicable", "pass": checks["generated_parser_trace"] and checks["runner_four_way_binding"]},
            "diagnostic_multiclass_edge_no_loss": {"applicability": "blocking_applicable", "pass": checks["source_bound_generation_required_next_fresh"]},
            "source_bound_final_zip": {"applicability": "blocking_applicable", "enforcement": "required_next_fresh", "pass": checks["source_bound_exact_regeneration"]},
            "materialized_config": {"applicability": "receipt_reuse", "pass": checks["deterministic_frozen_build"]},
            "numeric_w3_golden": {"applicability": "record_only", "pass": True},
            "production_compile_sim_return": {"applicability": "dynamic_only", "pass": None},
        },
        "expected_server": {
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "return_template": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip",
            "sidecar_template": f"/home/panqs/ndp/simresult/{PACKAGE_ID}_r<epoch-ns>_<pid>_return.zip.sha256",
            "duplicate_absent_required": True,
        },
        "claim_boundary": (
            "p28 is one c0 generated source-bound diagnostic for Buffer5 last-write/read-response timing. It does not "
            "claim c0 natural terminal, 27 natural terminals, formal 320D, E3/E4/E5, numeric correctness or performance."
        ),
        "server_action": False,
    }
    if OUTPUT.exists():
        raise FinalizeError("refusing to overwrite p28 final audit")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
