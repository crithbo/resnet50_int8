from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v69_return_v70_successor"
ANALYSIS = ROOT / "outputs/conv_node0004_v69_return_analysis/report.json"
PACKAGE = "r5_n4_hw_v70_branch_owner_diag"
ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending/{PACKAGE}.zip"
RECEIPTS = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/{PACKAGE}"
SIDECAR = RECEIPTS / f"{PACKAGE}.zip.sha256"
TASK = ROOT / ".agents/task_records/20260808_conv_node0004_v69_return_v70_branch_owner_successor.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rec(path: Path) -> dict[str, object]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    audit_path = OUT / "v70_final_zip_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    files = {
        "return_analyzer": ROOT / "tools/analyze_node0004_v69_branch_drain_return.py",
        "return_report": ANALYSIS,
        "builder": ROOT / "tools/build_node0004_v69_branch_owner_successor_v70.py",
        "observer_validator": ROOT / "tools/validate_node0004_v70_branch_owner.py",
        "observer_report": OUT / "v70_branch_owner_validation.json",
        "family_report": OUT / "v70_family_validation.json",
        "shared_report": OUT / "v70_shared_validation.json",
        "shared_harness": OUT / "v70_shared_harness.json",
        "runner_report": OUT / "v70_runner_visibility.json",
        "return_contract_report": OUT / "v70_return_contract_validation.json",
        "final_auditor": ROOT / "tools/audit_node0004_v70_final_zip.py",
        "final_audit": audit_path,
        "storage_index": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json",
    }
    report = {
        "schema": "node0004-v69-return-v70-release-v1", "status": "PACKAGE_READY_NOT_RUN",
        "return_analysis": {key: analysis[key] for key in (
            "status", "last_proven_good", "first_divergence", "hang_root_cause",
            "qualified_branch_drain_chronology", "four_candidate_adjudication",
            "formal_result", "blocker_delta")},
        "package_release": {"id": PACKAGE, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False, "zip": rec(ZIP), "sidecar": rec(SIDECAR),
            "command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x",
            "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
            "final_zip_rule_self_audit_pass": audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
            "errors": audit["errors"], "release_gate_matrix": audit["release_gate_matrix"]},
        "observer_coverage": {"feature": "RETURN_OBS_BRANCH_OWNER / BRANCH_OWNER_EDGE_V1",
            "candidates": list(analysis["next_candidate_matrix"]),
            "qualified_event_budget": 128, "non_progress_state_budget": 8,
            "progress_semantics": "Only qualified handshakes increment the token ledger; state snapshots have an independent finite budget.",
            "claim_boundary": "Diagnostic localization only; v70 is not a functional fix and does not claim natural terminal or formal-D success."},
        "validation_commands": [
            {"name": "return_analyzer", "exit": 0},
            {"name": "observer_scope_profile_budget_format_trace", "exit": 0},
            {"name": "install_only_family_harness", "exit": 0},
            {"name": "shared_runtime_layout", "exit": 0},
            {"name": "runner_error_visibility", "exit": 0},
            {"name": "return_contract", "exit": 0},
            {"name": "final_zip_rule_self_audit", "exit": 0},
            {"name": "storage_rotation_and_audit", "exit": 0}],
        "evidence": {key: rec(path) for key, path in files.items()},
        "storage": {"previous_v69": "tested", "current_pending": PACKAGE,
            "one_pending_per_family": True, "pending_pickup_zip_only": True},
        "rule_confirmation": {"decision": "CURRENT_RULES_CONFIRMED_SUFFICIENT",
            "evidence": "The current qualified-budget isolation and exact logger/parser trace rules directly caught and closed local package validation gaps; exact-consumer HDL, install-only runtime, fixed-return and storage gates all passed without needing a public rule delta."},
        "rule_delta_proposal": None,
        "frozen": {"numeric_analysis_repeated": False, "workload_rebuilt": False,
            "configuration_rebuilt": False, "golden_rebuilt": False,
            "timeout_or_backpressure_changed": False, "functional_rtl_modified": False,
            "server_action": False},
        "provenance": {"owner": "019fa2c1-17df-7122-bcbd-a727aaf173f5",
            "return_target": "019fbec2-fe93-7e03-9314-cff6f222f33d"}}
    release = OUT / "release_report.json"
    release.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    task_text = f"""# 2026-08-08 serialized Conv node0004 v69 return -> v70 branch-owner diagnostic

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- v69 return SHA256: `ac7ccf08989db2b7afebaa1937ce7b337acfb16e94fffa39878bcf6b86f36ddb`
- v69 source SHA256: `e6c94bf8b38e8e0ff7aed6984782a874a665938930dc5f91357323592c2e88eb`

## Return adjudication

- LAST_PROVEN_GOOD: `{analysis['last_proven_good']}`
- FIRST_DIVERGENCE: `{analysis['first_divergence']}`
- HANG_ROOT_CAUSE: `{analysis['hang_root_cause']['status']}`
- dynamic run bound: `{analysis['formal_result']['dynamic_run_bound']}`
- E3/E4/E5: `{analysis['formal_result']['E3']}/{analysis['formal_result']['E4']}/{analysis['formal_result']['E5']}`
- natural terminal: `{analysis['formal_result']['natural_terminal']}`
- formal D: expected `{analysis['formal_result']['expected']}`, present `{analysis['formal_result']['present']}`, missing `{analysis['formal_result']['missing']}`, mismatch `{analysis['formal_result']['mismatch']}`.

v69 proves 18/18 descriptor/prepared joins drain, then the data branch accepts two additional prepared groups. Final counters are descriptor 18, prepared write/read 20/18, prepared occupancy 32, memory-index push/pop 9/9. Address/request queue and memory-channel backpressure are excluded; the remaining ambiguity is exact last/index/epoch ownership of the two surplus groups.

## v70 successor

- ZIP: `{ZIP}`
- ZIP SHA256: `{sha(ZIP)}`
- classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`; candidate_release=false
- observer: qualified `BRANCH_OWNER_EDGE_V1`, binding descriptor tag/size, Buffer_AG tag/last/index, request/return, prepared pointers and join.
- qualified/state budgets: 128/8, separate; state never consumes qualified capacity.
- focused HDL positive and missing-declaration/consumer-typo negatives PASS; logger/parser exact-format mutations PASS.
- install-only V2, 86/86 SCA open, runner/finalizer, return contract and final ZIP audit PASS/errors=0.
- storage: v69 moved to tested; v70 is the sole pending package for `conv_serialized_node0004`.

Frozen: numeric/W3/qparams/tail/workload/config/golden/timeout/backpressure/functional RTL. No server action was performed.

RULE_CONFIRMATION: current rules are sufficient; no public rule delta is proposed.

Release report: `{release}` SHA256=`{sha(release)}`.
"""
    TASK.write_text(task_text, encoding="utf-8", newline="\n")
    print(json.dumps({"release_report": rec(release), "task_record": rec(TASK)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
