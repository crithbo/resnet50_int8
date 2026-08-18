#!/usr/bin/env python3
"""Aggregate p49 exact-final-ZIP v3 gates without performing storage/server actions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p49_tbvcdrt2"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_release"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
GATES = OUT / "gates"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_return_analysis_r1786704774390782459_2297616"
ACTIVATION = ROOT / "outputs/tb_vcd_cross_family_exit_audit_v1/canonical_activation_receipt.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"object required: {path}")
    return value


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }


def main() -> int:
    gate_names = [
        "tb_vcd_tree_v3",
        "mode_selector_tree_v3",
        "mode_selector_zip_v3",
        "hdl_lexical_tree_v3",
        "hdl_lexical_zip_v3",
        "runtime_preflight_v3",
        "runner_tree_v3",
        "runner_zip_v3",
        "post_sim_final_zip_v3",
        "package_release_admission",
        "first_fresh_validation",
    ]
    receipts: dict[str, dict[str, Any]] = {}
    gate_checks: dict[str, bool] = {}
    for name in gate_names:
        path = GATES / f"{name}.json"
        receipts[name] = identity(path)
        value = load(path)
        gate_checks[name] = value.get("pass") is True or value.get("valid") is True

    manifest = load(TREE / "package_manifest.json")
    pointer = load(TREE / "TEST_PACKAGE_MANIFEST.json")
    build = load(OUT / "build_receipt.json")
    contract = load(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    layout = load(TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json")
    retention = load(TREE / "contracts/server_tb_vcd_streaming_retention_contract.json")
    activation = load(ACTIVATION)
    formal = load(ANALYSIS / "formal_return_analysis.json")
    rule_audit = load(ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")
    runner_sha = sha(TREE / "PREPARE_AND_RUN.sh")
    helper_sha = sha(TREE / "package_tools/server_tb_vcd_runtime_supervision.py")
    archive_report = load(
        OUT / "first_fresh_audit/reports/source_bound_logger_collector_parser_roundtrip.json"
    )

    checks = {
        **{f"gate_{name}": value for name, value in gate_checks.items()},
        "deterministic_exact_zip_recompute": ZIP.read_bytes() == REPEAT.read_bytes(),
        "build_receipt_exact_zip": build.get("zip", {}).get("sha256") == sha(ZIP)
        and build.get("repeat_zip", {}).get("sha256") == sha(REPEAT),
        "manifest_exact": manifest.get("files") == file_map(TREE),
        "manifest_ready": manifest.get("status") == "PACKAGE_READY_NOT_RUN"
        and pointer.get("status") == "PACKAGE_READY_NOT_RUN",
        "runtime_v3_epoch": build.get("activation_epoch") == "tb-vcd-exit-mechanism-consistency-v3"
        and activation.get("status") == "CURRENT_DISK_TB_VCD_EXIT_MECHANISM_CONSISTENCY_V3_ACTIVATED",
        "shared_helper_byte_equal": helper_sha == sha(ROOT / "tools/server_tb_vcd_runtime_supervision.py"),
        "runner_identity_conjunction": layout.get("runner_sha256") == runner_sha
        and load(TREE / "server_runner_return_resilience_contract.json").get("runner_sha256") == runner_sha
        and load(TREE / "contracts/server_post_sim_return_contract.json").get("runner_sha256") == runner_sha,
        "sole_shared_decision_authority": contract.get("runtime_policy", {}).get("decision_authority")
        == "SHARED_RUNTIME_EVALUATOR_ONLY"
        and contract.get("runtime_policy", {}).get("outer_runner_independent_exit_logic") is False,
        "exact_four_case_replay": archive_report.get("replay", {}).get("checks", {}).get("exact_four_case_replay") is True,
        "archive_identity_timestamp_bound": archive_report.get("roundtrip", {}).get("checks", {}).get("archive_timestamp_exact") is True,
        "partial_flush_reap_fail_closed": archive_report.get("roundtrip", {}).get("checks", {}).get("natural_complete") is True
        and load(GATES / "post_sim_final_zip_v3.json").get("pass") is True,
        "retention_streaming_resume": retention.get("analysis_artifacts")
        == ["analysis_state.json", "checkpoints.jsonl", "report.md"]
        and retention.get("analysis_mode") == "STREAMING_RESUMABLE_NO_WHOLE_FILE_CONTEXT_LOAD"
        and retention.get("size_based_deletion") is False,
        "p48_formal_analysis_complete": formal.get("pass") is True,
        "mandatory_build_failure_audit": rule_audit.get("pass") is True
        and isinstance(rule_audit.get("trigger"), str)
        and bool(rule_audit.get("trigger"))
        and rule_audit.get("rule_disposition") == "RULE_CONFIRMATION_NO_CHANGE",
        "frozen_surfaces_declared": build.get("frozen_surfaces")
        == ["config", "numeric", "workload", "golden", "functional_rtl", "p42_vector_predicate", "MSE4_target"],
        "functional_rtl_absent": not (TREE / "rtl").exists(),
        "no_runtime_wave_packaged": not any(
            path.suffix.lower() in {".vcd", ".vpd", ".fsdb", ".fst"}
            for path in TREE.rglob("*") if path.is_file()
        ),
        "no_server_action": build.get("server_actions_performed") == [],
    }
    errors = [name for name, passed in checks.items() if not passed]
    final = {
        "schema": "conv-native-p49-tb-vcd-runtime-v3-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "LOCAL_GATE_FAILED",
        "package_id": PACKAGE,
        "family": "conv_native_four_lane",
        "activation_epoch": "tb-vcd-exit-mechanism-consistency-v3",
        "package": identity(ZIP),
        "repeat_zip": identity(REPEAT),
        "checks": checks,
        "gate_receipts": receipts,
        "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json"),
        "package_build_failure_rule_audit": identity(ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"),
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "previous_version_progress": (
            "p41 passed production compile beyond Datahub; p42 fixed the two-bit vector predicate; p46 proved "
            "descriptor/buffer/MemAG/wdata accepts; p48 compiled and advanced through preload but a stale "
            "display-heartbeat false freeze stopped before MSE4 target entry."
        ),
        "current_version_purpose": (
            "Preserve the p42/MSE4 FIFO-outstanding-last-FSM-drain-finish target while making the current v3 "
            "shared evaluator the sole stop authority and binding the quiescent VCD identity/timestamp."
        ),
        "unique_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_<execution>_return.zip",
        "pass": not errors,
        "errors": errors,
        "claim_boundary": (
            "Local exact-ZIP/package/runtime/return gates only. No production p49 compile/simulation, target "
            "entry, root cause, natural terminal, formal-D, E3, E4 or E5 claim; no server action performed."
        ),
    }
    path = GATES / "final_zip_release_audit.json"
    path.write_text(json.dumps(final, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    evidence = {
        "schema": "conv-native-p49-release-evidence-v1",
        "status": final["status"],
        "package_id": PACKAGE,
        "final_zip": identity(ZIP),
        "final_zip_audit": identity(path),
        "first_fresh": receipts["first_fresh_validation"],
        "release_admission": receipts["package_release_admission"],
        "formal_return_analysis": final["formal_return_analysis"],
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "server_actions_performed": [],
        "claim_boundary": final["claim_boundary"],
    }
    evidence_path = OUT / f"{PACKAGE}.release_evidence.json"
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": not errors, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
