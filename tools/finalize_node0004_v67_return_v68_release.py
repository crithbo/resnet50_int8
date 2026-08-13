from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v67_return_v68_successor"
ANALYSIS = ROOT / "outputs/conv_node0004_v67_return_analysis/report.json"
TASK = ROOT / ".agents/task_records/20260808_conv_node0004_v67_return_v68_pe7_pair_successor.md"
ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v68_pe7_pair_diag.zip"
SIDECAR = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v68_pe7_pair_diag/r5_n4_hw_v68_pe7_pair_diag.zip.sha256"
FILES = {
    "return_analyzer": ROOT / "tools/analyze_node0004_v67_pe1_pair_return.py",
    "return_report": ANALYSIS,
    "builder": ROOT / "tools/build_node0004_v67_pe7_pair_successor_v68.py",
    "build_report": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v68_pe7_pair_diag/r5_n4_hw_v68_pe7_pair_diag.build.json",
    "observer_validator": ROOT / "tools/validate_node0004_v68_pe7_pair.py",
    "observer_report": OUT / "v68_pe7_pair_validation.json",
    "family_report": OUT / "v68_family_validation.json",
    "shared_report": OUT / "v68_shared_validation.json",
    "shared_harness": OUT / "v68_shared_harness.json",
    "runner_report": OUT / "v68_runner_visibility.json",
    "return_contract": OUT / "v68_return_contract_validation.json",
    "final_auditor": ROOT / "tools/audit_node0004_v68_final_zip.py",
    "final_audit": OUT / "v68_final_zip_audit.json",
    "storage_index": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json",
    "task_record": TASK,
}

def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def rec(path: Path) -> dict[str, object]: return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}

def main() -> int:
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    audit = json.loads((OUT / "v68_final_zip_audit.json").read_text(encoding="utf-8"))
    report = {
        "schema": "node0004-v67-return-v68-release-v1", "status": "PACKAGE_READY_NOT_RUN",
        "return_analysis": {key: analysis[key] for key in ("status", "last_proven_good", "first_divergence", "hang_root_cause", "formal_result", "blocker_delta")},
        "package_audit_escape_root_cause": {
            "class": "LOGICAL_TO_PHYSICAL_MAPPER_BINDING_NOT_VALIDATED_BY_V67_OBSERVER_AUDIT",
            "exact_error": "v67 PE1_PAIR sampled IGA_PE[1] and physical LC9; mapping binds logical PE1/LC15/LC9 to physical PE7/LC17/LC18",
            "why_old_audit_passed": "The old scope check proved every written XMR leaf exists in RTL, but did not prove that the selected physical instance implements the logical mapped consumer.",
            "claim_correction": "v67 focused HDL syntax/scope and runner receipts remain valid; v67 PE1_PAIR causal coverage claim is withdrawn.",
            "v68_gate": "Final feature contract binds mapping SHA and validator asserts physical PE7/LC17/LC18 while rejecting PE1/LC9 in the changed block.",
        },
        "package_release": {
            "id": "r5_n4_hw_v68_pe7_pair_diag", "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False, "zip": rec(ZIP), "sidecar": rec(SIDECAR),
            "command": "bash r5_n4_hw_v68_pe7_pair_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x",
            "expected_return": "/home/panqs/ndp/simresult/r5_n4_hw_v68_pe7_pair_diag_r<epoch-ns>_<pid>_return.zip",
            "final_zip_rule_self_audit_pass": audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
            "errors": audit["errors"], "release_gate_matrix": audit["release_gate_matrix"],
        },
        "evidence": {key: rec(path) for key, path in FILES.items()},
        "storage": {"previous_v67": "tested", "current_pending": "r5_n4_hw_v68_pe7_pair_diag", "one_pending_per_family": True},
        "rule_confirmation": "CURRENT_RULES_SUFFICIENT; the actual-consumer/scope rule is correctly strengthened in v68 by binding mapper logical-to-physical identity, with no public-rule delta required.",
        "rule_delta_proposal": None,
        "frozen": {"numeric_analysis_repeated": False, "workload_rebuilt": False, "configuration_rebuilt": False,
                   "golden_rebuilt": False, "timeout_or_backpressure_changed": False, "functional_rtl_modified": False,
                   "server_action": False},
        "provenance": {"owner": "019fa2c1-17df-7122-bcbd-a727aaf173f5", "return_target": "019fbec2-fe93-7e03-9314-cff6f222f33d"},
    }
    target = OUT / "release_report.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"release_report": rec(target), "task_record": rec(TASK)}, indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
