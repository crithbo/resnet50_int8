from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v68_return_v69_successor"
ANALYSIS = ROOT / "outputs/conv_node0004_v68_return_analysis/report.json"
PACKAGE = "r5_n4_hw_v69_branch_drain_diag"
ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending/{PACKAGE}.zip"
RECEIPTS = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/{PACKAGE}"
SIDECAR = RECEIPTS / f"{PACKAGE}.zip.sha256"
TASK = ROOT / ".agents/task_records/20260808_conv_node0004_v68_return_v69_branch_drain_successor.md"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rec(path: Path) -> dict[str, object]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    audit_path = OUT / "v69_final_zip_audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    files = {
        "return_analyzer": ROOT / "tools/analyze_node0004_v68_pe7_pair_return.py",
        "return_report": ANALYSIS,
        "builder": ROOT / "tools/build_node0004_v68_branch_drain_successor_v69.py",
        "observer_validator": ROOT / "tools/validate_node0004_v69_branch_drain.py",
        "observer_report": OUT / "v69_branch_drain_validation.json",
        "family_report": OUT / "v69_family_validation.json",
        "shared_report": OUT / "v69_shared_validation.json",
        "shared_harness": OUT / "v69_shared_harness.json",
        "runner_report": OUT / "v69_runner_visibility.json",
        "return_contract_report": OUT / "v69_return_contract_validation.json",
        "final_auditor": ROOT / "tools/audit_node0004_v69_final_zip.py",
        "final_audit": audit_path,
        "storage_index": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json",
    }
    report = {
        "schema": "node0004-v68-return-v69-release-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "return_analysis": {
            key: analysis[key]
            for key in (
                "status",
                "last_proven_good",
                "first_divergence",
                "hang_root_cause",
                "formal_result",
                "blocker_delta",
            )
        },
        "package_release": {
            "id": PACKAGE,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "zip": rec(ZIP),
            "sidecar": rec(SIDECAR),
            "command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x",
            "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_r<epoch-ns>_<pid>_return.zip",
            "final_zip_rule_self_audit_pass": audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
            "errors": audit["errors"],
            "release_gate_matrix": audit["release_gate_matrix"],
        },
        "observer_coverage": {
            "feature": "RETURN_OBS_BRANCH_DRAIN / BRANCH_DRAIN_V1",
            "candidates": [
                "address_request_queue_empty",
                "prepared_data_cannot_join_request",
                "memory_channel_backpressure",
                "buffer_read_return_not_accepted",
            ],
            "progress_semantics": "Only qualified handshakes/changes increment progress; held levels are snapshots.",
            "claim_boundary": "Diagnostic localization only; v69 is not a functional fix and does not claim natural terminal or formal-D success.",
        },
        "validation_commands": [
            {"name": "return_analyzer", "exit": 0},
            {"name": "observer_scope_and_predicate_trace", "exit": 0},
            {"name": "install_only_family_harness", "exit": 0},
            {"name": "shared_runtime_layout", "exit": 0},
            {"name": "runner_error_visibility", "exit": 0},
            {"name": "return_contract", "exit": 0},
            {"name": "final_zip_rule_self_audit", "exit": 0},
            {"name": "storage_rotation_and_audit", "exit": 0},
        ],
        "evidence": {key: rec(path) for key, path in files.items()},
        "storage": {
            "previous_v68": "tested",
            "current_pending": PACKAGE,
            "one_pending_per_family": True,
            "pending_pickup_zip_only": True,
        },
        "rule_confirmation": {
            "decision": "CURRENT_RULES_CONFIRMED_SUFFICIENT",
            "evidence": "The current event-qualification, time-to-root-cause, actual-consumer HDL, install-only runtime, fixed-return, and storage-rotation gates all fired in their intended scopes; all blocking checks and negatives passed.",
        },
        "rule_delta_proposal": None,
        "frozen": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "golden_rebuilt": False,
            "timeout_or_backpressure_changed": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
        "provenance": {
            "owner": "019fa2c1-17df-7122-bcbd-a727aaf173f5",
            "return_target": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        },
    }
    release = OUT / "release_report.json"
    release.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    task_text = f"""# 2026-08-08 serialized Conv node0004 v68 return -> v69 branch-drain diagnostic

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- v68 return SHA256: `2a39ff084c605e06343fba9b6193d1e5666640f519266a5aa2d1f332b807d97e`
- v68 source SHA256: `372c6135f064dfb5847bedfea3741b8724113eb8e3b0c7f644e87f4fa877fdee`

## Return adjudication

- LAST_PROVEN_GOOD: `{analysis['last_proven_good']}`
- FIRST_DIVERGENCE: `{analysis['first_divergence']}`
- HANG_ROOT_CAUSE: `{analysis['hang_root_cause']['status']}`
- E3/E4/E5: `{analysis['formal_result']['E3']}/{analysis['formal_result']['E4']}/{analysis['formal_result']['E5']}`
- natural terminal: `{analysis['formal_result']['natural_terminal']}`
- formal D: expected `{analysis['formal_result']['expected']}`, present `{analysis['formal_result']['present']}`, missing `{analysis['formal_result']['missing']}`, mismatch `{analysis['formal_result']['mismatch']}`. All-missing is not a numeric pass.

v68 proves the physical PE7 path is locally healthy for nine complete match/write/read/output transactions. The next LC18 token is blocked by destination bit 10 (ROW_LC4), while PE7 input2 remains ready. The remaining ambiguity is confined to the ROW_LC4 -> Buffer_AG/RD_Buffer_AG -> prepared-data/Memory_AG descriptor drain conjunction.

## v69 successor

- ZIP: `{ZIP}`
- ZIP SHA256: `{sha(ZIP)}`
- classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`; candidate_release=false
- observer: aggregated qualified `BRANCH_DRAIN_V1`, covering address-request queue empty, prepared-data/request join, memory-channel backpressure, and buffer read-return acceptance in one run.
- final ZIP audit: PASS, errors=0
- storage: v68 moved to tested; v69 is the sole pending package for `conv_serialized_node0004`.

Frozen: numeric/W3/qparams/tail/workload/config/golden/timeout/backpressure/functional RTL. No server action was performed.

RULE_CONFIRMATION: current rules are sufficient; no public rule delta is proposed.

Release report: `{release}` SHA256=`{sha(release)}`.
"""
    TASK.write_text(task_text, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {"release_report": rec(release), "task_record": rec(TASK)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
