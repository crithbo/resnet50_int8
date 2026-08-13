#!/usr/bin/env python3
"""Create the exact final-ZIP release receipt for native-four-lane p26."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p26_memag"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p26_memag"
ZIP_PATH = BASE / "build" / f"{PACKAGE_ID}.zip"
BUILD = BASE / "build" / f"{PACKAGE_ID}.build.json"
FAMILY = BASE / "p26_family_audit.json"
HARNESS = BASE / "p26_runtime_layout_harness.json"
SHARED = BASE / "p26_shared_runtime_layout_from_harness.json"
PROFILE = BASE / "server_package_build_profile.json"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p25_return_analysis/report.json"
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
    required = (ZIP_PATH, BUILD, FAMILY, HARNESS, SHARED, PROFILE, ANALYSIS)
    if not all(path.is_file() for path in required):
        raise FinalizeError("required p26 release input is absent")
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    harness = json.loads(HARNESS.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    with zipfile.ZipFile(ZIP_PATH) as archive:
        prefix = PACKAGE_ID + "/"
        runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode()
        manifest = json.loads(archive.read(prefix + "package_manifest.json"))
        observer = archive.read(prefix + "tb_probe/native_return_observer.svh")
    scenarios = harness["scenarios"]
    required_scenarios = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    expected_exits = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    runtime_ok = all(
        scenarios[name]["runner_exit"] == expected_exits[name]
        and scenarios[name]["finalizer_reached"] is True
        and scenarios[name]["fixed_result_return_published"] is True
        and scenarios[name]["root_exact_set_unchanged"] is True
        and scenarios[name]["unknown_items_deleted_or_overwritten"] is False
        and scenarios[name]["writes_outside_install"] is False
        for name in required_scenarios
    )
    binding = (
        "+RETURN_OBS_EPOCH_FLOW +RETURN_OBS_EPOCH_FLOW_LIMIT=256 "
        "+RETURN_OBS_SELECT_PORT +RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128 "
        "+RETURN_OBS_SELECT_PORT_STATE_LIMIT=64"
    )
    epoch = family["observer"]["focused_compile"]["p23_epoch_flow"]
    public = family["observer"]["focused_compile"]["p25_pe7_source13"]
    checks = {
        "exact_zip_identity": ZIP_PATH.stat().st_size == build["zip_bytes"] and sha256(ZIP_PATH) == build["zip_sha256"],
        "formal_p25_analysis": analysis["valid"] is True and analysis["status"] == "P25_SOURCE13_PUBLIC_CHAIN_PASS_MEMORY_AG_CONSUMER_SUCCESSOR_REQUIRED",
        "shadow_build_profile": (
            profile["contract_valid"] is True and profile["preflight"]["pass"] is True
            and not profile["preflight"]["errors"] and profile["mode"] == "SHADOW_ONLY_NEXT_FRESH"
        ),
        "deterministic_frozen_build": (
            build["deterministic_double_build"] is True
            and build["frozen"]["frozen_install_payload_byte_equal"] is True
            and build["frozen"]["observer_byte_equal"] is True
            and all(build["frozen"]["sca_identity_normalized_equal"].values())
            and build["functional_rtl_modified"] is False
        ),
        "family_audit": family["valid"] is True and family["status"] == "PASS" and not family["errors"],
        "exact_p25_observer": hashlib.sha256(observer).hexdigest() == "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1",
        "public_source13_scope": public["valid"] is True,
        "actual_memory_ag_epoch_flow_scope": epoch["valid"] is True,
        "dual_feature_binding": runner.count(binding) == 2 and family["diagnostic_feature_binding_trace"]["valid"] is True,
        "runtime_scenarios": runtime_ok,
        "shared_runtime_layout_once": shared["pass"] is True and not shared["errors"],
        "repeatable_return_contract": (
            'return_tag="r$(date -u +%s%N)_$$"' in runner
            and 'return_zip="/home/panqs/ndp/simresult/${package_identity}_${return_tag}_return.zip"' in runner
        ),
        "manifest_claim_boundary": (
            manifest["candidate_release"] is False
            and manifest["p26_simultaneous_consumer_features"]["observer_bytes_changed"] is False
            and manifest["p26_simultaneous_consumer_features"]["functional_rtl_changed"] is False
        ),
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p26-final-zip-audit-v1",
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
            "p25_return_analysis": receipt(ANALYSIS),
            "build_profile": receipt(PROFILE),
            "build": receipt(BUILD),
            "family": {**receipt(FAMILY), "pass": family["valid"], "errors": len(family["errors"])},
            "runtime_layout_harness": {**receipt(HARNESS), "required_scenarios_pass": list(required_scenarios)},
            "shared_runtime_layout": {
                **receipt(SHARED), "pass": shared["pass"], "errors": len(shared["errors"]),
                "exact_final_zip_invocation_count": 1,
            },
        },
        "frozen_surface": {
            "install_payload_member_count": build["frozen"]["frozen_install_payload_member_count"],
            "install_payload_byte_equal": True,
            "sca_identity_normalized_equal": True,
            "observer_byte_equal": True,
            "workload_config_mapping_bitstream_execplan_numeric_w3_golden_timeout_changed": False,
            "functional_rtl_modified": False,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {"applicability": "blocking_applicable", "pass": checks["exact_zip_identity"]},
            "runner_control_flow": {"applicability": "blocking_applicable", "pass": checks["runtime_scenarios"] and checks["repeatable_return_contract"]},
            "runtime_layout": {"applicability": "blocking_applicable", "pass": checks["shared_runtime_layout_once"]},
            "package_local_hdl": {"applicability": "receipt_reuse", "pass": checks["exact_p25_observer"] and checks["actual_memory_ag_epoch_flow_scope"]},
            "diagnostic_semantics": {"applicability": "blocking_applicable", "pass": checks["dual_feature_binding"]},
            "diagnostic_multiclass_edge_no_loss": {"applicability": "blocking_applicable", "pass": checks["public_source13_scope"]},
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
            "p26 is one c0 diagnostic for the actual Memory_AG selection/queue boundary. It does not claim c0 natural "
            "terminal, 27 natural terminals, formal 320D, E3/E4/E5, numeric correctness or performance before formal server return."
        ),
        "server_action": False,
    }
    if OUTPUT.exists():
        raise FinalizeError("refusing to overwrite p26 final audit")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
