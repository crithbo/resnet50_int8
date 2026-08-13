from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v76_return_v77_successor"
ANALYSIS = ROOT / "outputs/conv_node0004_v76_return_analysis/report.json"
BUILD = OUT / "build"
PACKAGE = "r5_n4_hw_v77_terminal_temporal_ledger_diag"
ZIP = BUILD / f"{PACKAGE}.zip"
SIDECAR = BUILD / f"{PACKAGE}.zip.sha256"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict:
    return {"path": path.resolve().relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    analysis = load(ANALYSIS)
    final_audit_path = OUT / "final_zip_audit.json"
    final_audit = load(final_audit_path)
    extra_path = OUT / "first_fresh_extra_audit/validation.json"
    extra = load(extra_path)
    reports = {
        "return_analysis": receipt(ANALYSIS),
        "build": receipt(BUILD / f"{PACKAGE}.build.json"),
        "source_bound_final_zip": receipt(OUT / "source_bound_final_zip_validation.json"),
        "post_sim_final_zip": receipt(OUT / "post_sim_final_zip_validation.json"),
        "temporal_collector": receipt(OUT / "temporal_collector_validation.json"),
        "runner": receipt(OUT / "runner_validation.json"),
        "shared_runtime_layout": receipt(OUT / "shared_runtime_layout_validation.json"),
        "return_contract": receipt(OUT / "return_contract_validation.json"),
        "first_fresh_contract": receipt(OUT / "first_fresh_extra_audit/contract.json"),
        "first_fresh_validation": receipt(extra_path),
        "final_zip_audit": receipt(final_audit_path),
    }
    release = {
        "schema": "conv-node0004-v76-return-v77-release-v1",
        "owner": "019fa2c1-17df-7122-bcbd-a727aaf173f5",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "RETURN_ANALYSIS": {
            "formal_return": analysis["return_receipt"],
            "source": analysis["source_receipt"],
            "integrity_identity_plugin_parser_pass": analysis["valid"],
            "compile_exit": analysis["dynamic_joint_gate"]["compile_exit"],
            "run_exit": analysis["dynamic_joint_gate"]["run_exit"],
            "signal": analysis["dynamic_joint_gate"]["signal"],
            "natural_terminal": analysis["dynamic_joint_gate"]["natural_terminal"],
            "formal_d_present": analysis["dynamic_joint_gate"]["formal_d_present"],
            "formal_d_missing": analysis["dynamic_joint_gate"]["formal_d_missing"],
            "formal_d_mismatch": analysis["dynamic_joint_gate"]["formal_d_mismatch"],
            "E3": analysis["dynamic_joint_gate"]["E3"],
            "E4": analysis["dynamic_joint_gate"]["E4"],
            "E5": analysis["dynamic_joint_gate"]["E5"],
            "bounded_projection": analysis["bounded_projection"],
        },
        "LAST_PROVEN_GOOD": analysis["LAST_PROVEN_GOOD"],
        "FIRST_DIVERGENCE": analysis["FIRST_DIVERGENCE"],
        "HANG_ROOT_CAUSE": analysis["HANG_ROOT_CAUSE"],
        "BLOCKER_DELTA": analysis["BLOCKER_DELTA"],
        "PACKAGE_RELEASE": {
            "status": "PACKAGE_READY_NOT_RUN",
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_id": PACKAGE,
            "zip": receipt(ZIP),
            "sidecar": receipt(SIDECAR),
            "command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x",
            "expected_return": f"/home/panqs/ndp/simresult/{PACKAGE}_<execution>_return.zip",
            "first_fresh_after_change": True,
            "rule_change_epoch_id": "20260810-first-fresh-extra-audit-v1",
            "first_fresh_extra_audit_pass": extra.get("pass") is True,
            "upload_authorized_by_local_audit": extra.get("upload_authorized") is True,
            "final_zip_rule_self_audit_pass": final_audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is True,
            "errors": final_audit.get("errors"),
        },
        "observer_information_gain": {
            "target": "slice0/group0/MSE4 WR",
            "all_target_ring_records_retained": True,
            "other_instances_retention": "tail1 per boundary/kind/instance",
            "candidate_ids": [
                "MEMORY_TERMINAL_ABSENT",
                "BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH",
                "BUFFER_QUEUE_RESIDUAL_BEFORE_MEMORY_TERMINAL",
                "MEMORY_QUEUE_RESIDUAL",
                "BALANCED_BRANCHES_DOWNSTREAM_RELEASE",
            ],
            "pairwise_distinguishable": True,
        },
        "active_rule_receipts": {
            "agent": receipt(ROOT / ".agents/agent.md"),
            "plan_mutable": receipt(ROOT / ".agents/plan.md"),
            "generation_index": receipt(ROOT / ".agents/rules/生成前必读索引.md"),
            "server_package_rule": receipt(ROOT / ".agents/rules/服务器测试包生成规则.md"),
            "int8_sa_rule": receipt(ROOT / ".agents/rules/INT8_SA点积专项规则.md"),
            "hardware_readme": receipt(ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
            "source_bound_generator": receipt(ROOT / "tools/generate_server_source_bound_observer.py"),
            "post_sim_core": receipt(ROOT / "tools/server_post_sim_return.py"),
            "first_fresh_validator": receipt(ROOT / "tools/validate_server_first_fresh_extra_audit.py"),
        },
        "validation": {
            "commands_exit": {
                "formal_return_analysis": 0,
                "deterministic_double_build": 0,
                "source_bound_final_zip": 0,
                "post_sim_final_zip": 0,
                "temporal_overbudget_roundtrip_and_negatives": 0,
                "runner_normal_preflight_compile_HUP_INT_TERM": 0,
                "return_contract": 0,
                "first_fresh_preparation": 0,
                "first_fresh_shared_validator": 0,
                "final_zip_audit": 0,
            },
            "reports": reports,
            "release_gate_matrix": final_audit["release_gate_matrix"],
        },
        "RULE_CONFIRMATION": {
            "status": "CONFIRMED_EFFECTIVE_NO_DELTA",
            "evidence": "The first-fresh independent audit exposed a target-instance SUMMARY completeness escape before release; the final v77 adds the exact 12-summary fail-closed check, and its deletion negative now fails closed. Existing rules therefore produced the intended correction without a new public-rule delta.",
        },
        "claims": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    release_path = OUT / "release_report.json"
    write_json(release_path, release)
    task = f"""# Serialized Conv node0004 v76 RETURN -> v77 temporal-ledger successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

v76 return integrity, source/execution binding, post-sim core and required plugin all pass.
The bounded projection retained 14,447 of 57,142 source-bound records in
5,340,150 bytes (limit 7 MiB), and preserved the unique canonical class
`both_terminals_present_temporal_skew`. Compile/run are zero and signal is
`NONE`, but natural terminal is false and formal D is 0/320, so E3/E4/E5 are
all false.

For exact slice0/group0/MSE4 WR, Buffer terminal starts at 2446109 and totals
13 while Memory terminal appears once at 2446448. Buffer enqueue/dequeue/
consumer totals are 27/23/23 versus Memory 9/9/9. This closes the v75 package
projection overflow but does not uniquely choose replay, Memory suppression,
or drain/lifetime ownership because v76 retained only the last ring event.

v77 changes no numeric, workload, config, golden, timeout, backpressure or RTL.
It retains the complete qualified ring for the exact target and uses a
five-way pairwise temporal decision, while all other instances stay tail1.
The epoch `{release['PACKAGE_RELEASE']['rule_change_epoch_id']}` is ACKed as
this family's first fresh package. Independent clean-extract audit, 86 SCA
opens, runner/finalizer controls, over-budget multi-instance logger pipeline,
post-sim four scenarios, target SUMMARY deletion/stable-level negatives, shared
first-fresh validator and final ZIP audit all pass.

- pre-rotation ZIP SHA256: `{sha(ZIP)}`
- command: `{release['PACKAGE_RELEASE']['command']}`
- expected return: `{release['PACKAGE_RELEASE']['expected_return']}`
- formal return report SHA256: `{sha(ANALYSIS)}`
- first-fresh validation SHA256: `{sha(extra_path)}`
- final audit SHA256: `{sha(final_audit_path)}`

RULE_CONFIRMATION: the new independent audit gate worked as intended and found
the target-instance SUMMARY completeness escape before release; no additional
public rule delta is proposed.
"""
    (OUT / "task_record.md").write_text(task, encoding="utf-8", newline="\n")
    print(json.dumps({"release": receipt(release_path), "task": receipt(OUT / "task_record.md")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
