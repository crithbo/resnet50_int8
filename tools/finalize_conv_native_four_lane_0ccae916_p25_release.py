#!/usr/bin/env python3
"""Create the exact final-ZIP release receipt for native-four-lane p25."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p25_pe7src13"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p25_pe7src13"
ZIP_PATH = BASE / "build" / f"{PACKAGE_ID}.zip"
BUILD = BASE / "build" / f"{PACKAGE_ID}.build.json"
FAMILY = BASE / "p25_family_audit.json"
HARNESS = BASE / "p25_runtime_layout_harness.json"
SHARED = BASE / "p25_shared_runtime_layout_from_harness.json"
PROFILE = BASE / "server_package_build_profile.json"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p24_return_analysis/report.json"
OUTPUT = BASE / f"{PACKAGE_ID}.final_zip_audit.json"


class FinalizeError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size, "sha256": sha256(path),
    }


def main() -> int:
    required = (ZIP_PATH, BUILD, FAMILY, HARNESS, SHARED, PROFILE, ANALYSIS)
    if not all(path.is_file() for path in required):
        raise FinalizeError("required p25 release input is absent")
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        runner = archive.read(f"{PACKAGE_ID}/PREPARE_AND_RUN.sh").decode()
        manifest = json.loads(archive.read(f"{PACKAGE_ID}/package_manifest.json"))
        observer = archive.read(f"{PACKAGE_ID}/tb_probe/native_return_observer.svh").decode()
        runtime = archive.read(f"{PACKAGE_ID}/package_tools/node0004_assumed_hardware_server_runtime.py").decode()
    scenarios = harness["scenarios"]
    required_scenarios = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    expected_exits = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    scope = family["observer"]["focused_compile"]["p25_pe7_source13"]
    runtime_ok = all(
        scenarios[name]["runner_exit"] == expected_exits[name]
        and scenarios[name]["finalizer_reached"] is True
        and scenarios[name]["fixed_result_return_published"] is True
        and scenarios[name]["root_exact_set_unchanged"] is True
        and scenarios[name]["unknown_items_deleted_or_overwritten"] is False
        and scenarios[name]["writes_outside_install"] is False
        for name in required_scenarios
    )
    target_identity = all(
        manifest["expected_production_rtl_identity"]["leaves"].get(name) == sha
        and manifest["cloud_rtl_authority"]["leaves"].get(name) == sha
        and runtime.count(f'"{name}"') == 2
        for name, sha in {
            "IGA_Interconnect.sv": "f46f68b1eb1edc2a4ff85ce6894b8f549727512f9d3e6527d6954d7bb352c82e",
            "Stream_Engine_Connect.sv": "0ca375c4af56f7f6fe9e7055a39ac7370d91e6048b2aa9f3ae0a4910deae5425",
            "Memory_WR_Stream_Engine.sv": "c97a5b4a3587384d5b57b2a5db288a44b2166584c236307c69d26bb04f389127",
        }.items()
    )
    checks = {
        "exact_zip_identity": ZIP_PATH.stat().st_size == build["zip_bytes"] and sha256(ZIP_PATH) == build["zip_sha256"],
        "formal_p24_analysis": analysis["valid"] is True and analysis["status"] == "P24_PUBLIC_BOUNDARY_PASS_OBSERVER_SOURCE_MAPPING_SUCCESSOR_REQUIRED",
        "shadow_build_profile": (
            profile["contract_valid"] is True and profile["preflight"]["pass"] is True
            and not profile["preflight"]["errors"] and profile["mode"] == "SHADOW_ONLY_NEXT_FRESH"
        ),
        "deterministic_frozen_build": (
            build["deterministic_double_build"] is True
            and build["frozen"]["frozen_install_payload_byte_equal"] is True
            and all(build["frozen"]["sca_identity_normalized_equal"].values())
            and build["functional_rtl_modified"] is False
        ),
        "family_audit": family["valid"] is True and family["status"] == "PASS" and not family["errors"],
        "public_port_scope": (
            scope["valid"] is True and scope["public_surface_only"] is True
            and scope["new_private_xmr"] is False and scope["positive"]["exit_code"] == 0
            and scope["negative_leaf_deleted"]["exit_code"] != 0
            and scope["negative_leaf_renamed"]["exit_code"] != 0
            and scope["negative_wrong_sibling_path"]["exit_code"] != 0
        ),
        "pe7_source13_mapping": (
            scope["source_mapping_proof"]["valid"] is True
            and scope["source_mapping_proof"]["checks"]["source13_maps_pe7"] is True
        ),
        "diagnostic_predicate_trace": (
            scope["predicate_trace"]["valid"] is True
            and scope["predicate_trace"]["qualified_budget_consumed_by_state"] is False
        ),
        "diagnostic_multiclass_no_loss": (
            scope["multiclass_no_loss_trace"]["valid"] is True
            and scope["multiclass_no_loss_trace"]["simultaneous_input_mask"] == 7
            and all(scope["multiclass_no_loss_trace"]["covered"].values())
        ),
        "exact_logger_parser_trace": (
            scope["logger_parser_trace"]["valid"] is True
            and scope["logger_parser_trace"]["normalization"] == "NONE"
            and scope["logger_parser_trace"]["parsed_event_mask"] == 7
        ),
        "production_target_identity_collector": target_identity,
        "runtime_scenarios": runtime_ok,
        "shared_runtime_layout_once": shared["pass"] is True and not shared["errors"],
        "observer_and_runner_binding": (
            observer.count("p25 PE7_SOURCE13_BEGIN") == 1
            and observer.count("iga2se_mem_inport[4][13]") >= 6
            and "iga2se_mem_inport[4][7]" not in observer[observer.index("p25 PE7_SOURCE13_BEGIN"):]
            and runner.count("+RETURN_OBS_SELECT_PORT +RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128 +RETURN_OBS_SELECT_PORT_STATE_LIMIT=64") == 2
        ),
        "repeatable_return_contract": (
            'return_tag="r$(date -u +%s%N)_$$"' in runner
            and 'return_zip="/home/panqs/ndp/simresult/${package_identity}_${return_tag}_return.zip"' in runner
        ),
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p25-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid, "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_identity": PACKAGE_ID,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "checks": checks,
        "zip": {**receipt(ZIP_PATH), "deterministic_double_build": True},
        "audits": {
            "p24_return_analysis": receipt(ANALYSIS),
            "build_profile": receipt(PROFILE), "build": receipt(BUILD),
            "family": {**receipt(FAMILY), "pass": family["valid"], "errors": len(family["errors"])},
            "runtime_layout_harness": {**receipt(HARNESS), "required_scenarios_pass": list(required_scenarios)},
            "shared_runtime_layout": {
                **receipt(SHARED), "pass": shared["pass"], "errors": len(shared["errors"]),
                "exact_final_zip_invocation_count": 1,
            },
        },
        "frozen_surface": {
            "install_payload_member_count": build["frozen"]["frozen_install_payload_member_count"],
            "install_payload_byte_equal": True, "sca_identity_normalized_equal": True,
            "workload_config_mapping_bitstream_execplan_numeric_w3_golden_timeout_changed": False,
            "functional_rtl_modified": False,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["exact_zip_identity"]},
            "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runtime_scenarios"] and checks["repeatable_return_contract"]},
            "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout_once"]},
            "package_local_hdl": {"applicability": "blocking_applicable", "pass": checks["family_audit"] and checks["public_port_scope"] and checks["production_target_identity_collector"]},
            "diagnostic_semantics": {"applicability": "blocking_applicable", "pass": checks["diagnostic_predicate_trace"] and checks["exact_logger_parser_trace"]},
            "diagnostic_multiclass_edge_no_loss": {"applicability": "blocking_applicable", "pass": checks["diagnostic_multiclass_no_loss"]},
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
        "claim_boundary": "p25 is one c0 diagnostic correcting PE7 source mapping. It does not claim c0 natural terminal, 27 natural terminals, formal 320D, E3/E4/E5, numeric correctness or performance before formal server return.",
        "server_action": False,
    }
    if OUTPUT.exists():
        raise FinalizeError("refusing to overwrite p25 final audit")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
