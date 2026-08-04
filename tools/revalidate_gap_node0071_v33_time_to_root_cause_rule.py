from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v33_buffer_ag_idx_pair_diag.zip"
)
SIDECAR = Path(str(ZIP) + ".sha256")
CLOSURE = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-gap-node0071-v32-return-v33-successor/report.json"
)
FINAL_AUDIT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v33_buffer_ag_idx_pair_diag.final_zip_rule_self_audit.json"
)
RULE_UPDATE = (
    ROOT
    / ".agents/task_records/20260804_diagnostic_time_to_root_cause_rule_update.md"
)
ROOT_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
ZIP_BYTES = 1_824_172
ZIP_SHA256 = "5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03"
SIDECAR_SHA256 = "9bdb2cdb465d225d5dcd37746ba0e8e782cf3d2076a9b53625fe00b46cb46f1b"
CLOSURE_SHA256 = "0c37f937316dfc09215f632a2d700b8607de665028d9b75d2057b88dc43d7676"
RULE_UPDATE_SHA256 = "7501510ca6e4bbd4aad8c96d331508728b225f877029edf8be922a857688ea75"
CURRENT = {
    ".agents/agent.md":
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ".agents/rules/生成前必读索引.md":
        "5146225e549942c4e25780ac4fc0120d7cac1ef355879284450dad2e48df237b",
    ".agents/rules/服务器测试包生成规则.md":
        "0916c655b0581cd99836d8cc1561a3f41b15b25e861692d596a4789c039b090e",
}
RULE_ID = "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def semantic_checks(
    closure: dict[str, Any],
    manifest: dict[str, Any],
    final_audit: dict[str, Any],
) -> dict[str, bool]:
    successor = closure.get("successor", {})
    matrix = successor.get("candidate_discrimination_matrix", {})
    reduction = closure.get("causal_slice", {})
    feature = manifest.get("buffer_ag_index_pair_diagnostic_contract", {})
    return {
        "diagnostic_only":
            successor.get("classification") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and successor.get("candidate_release") is False,
        "candidate_matrix_complete": set(matrix) == {
            "producer_not_presented_or_accepted",
            "same_or_gotten_mask_suppression",
            "pair_not_reached",
            "mse_disabled",
            "queue_full_reject",
            "direct_consumer_not_dequeuing",
        },
        "one_run_low_cost_observations":
            len(successor.get("information_gain_scope", [])) >= 6,
        "qualified_event_limit_256":
            feature.get("runtime_limit") == "+RETURN_OBS_BUFFER_AG_IDX_QUEUE_LIMIT=256"
            and "256 qualified" in successor.get("event_budget", ""),
        "stable_level_not_progress":
            feature.get("stable_level_counts_as_progress") is False,
        "no_legal_checkpoint": reduction.get("legal_checkpoint_available") is False,
        "keep_exact_set_declared":
            reduction.get("keep_exact_set")
            == "all 73 frozen workload/numeric files and complete ordered-stage/return contract",
        "drop_exact_set_empty": reduction.get("drop_exact_set") == [],
        "nonprunable_reason_complete":
            "sum_s1 is the first stage" in reduction.get("reason", "")
            and "Later stages never start" in reduction.get("reason", "")
            and "cannot reduce" in reduction.get("reason", ""),
        "pre_divergence_semantics_unchanged":
            reduction.get("fd_precondition_changed") is False
            and successor.get("timeout_changed") is False
            and successor.get("backpressure_changed") is False,
        "host_internal_replay_absent":
            reduction.get("host_internal_tensor_replay_used") is False,
        "full_chain_claim_not_promoted":
            closure.get("return_analysis", {}).get("E3") is False
            and closure.get("return_analysis", {}).get("E4") is False
            and closure.get("return_analysis", {}).get("E5") is False,
        "final_zip_prior_audit_pass":
            final_audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is True
            and final_audit.get("error_count") == 0,
    }


def validate_model(
    closure: dict[str, Any],
    manifest: dict[str, Any],
    final_audit: dict[str, Any],
) -> tuple[bool, dict[str, bool]]:
    checks = semantic_checks(closure, manifest, final_audit)
    return all(checks.values()), checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    zip_before = sha256(ZIP)
    current_receipts = {
        path: {
            "expected_sha256": expected,
            "observed_sha256": sha256(ROOT / path),
            "current_match": sha256(ROOT / path) == expected,
        }
        for path, expected in CURRENT.items()
    }
    if not all(item["current_match"] for item in current_receipts.values()):
        errors.append("current control SHA differs")
    if (
        ZIP.stat().st_size != ZIP_BYTES
        or zip_before != ZIP_SHA256
        or sha256(SIDECAR) != SIDECAR_SHA256
        or SIDECAR.read_text(encoding="ascii")
        != f"{ZIP_SHA256}  {ZIP.name}\n"
    ):
        errors.append("frozen v33 ZIP/sidecar identity differs")
    if sha256(CLOSURE) != CLOSURE_SHA256:
        errors.append("v33 closure report identity differs")
    if sha256(RULE_UPDATE) != RULE_UPDATE_SHA256:
        errors.append("rule publication task record identity differs")

    with zipfile.ZipFile(ZIP) as archive:
        crc_bad = archive.testzip()
        names = archive.namelist()
        manifest = json.loads(
            archive.read(f"{ROOT_NAME}/TEST_PACKAGE_MANIFEST.json")
        )
    if crc_bad is not None:
        errors.append(f"ZIP CRC differs: {crc_bad}")
    if not names or any(
        not name.startswith(f"{ROOT_NAME}/") or ".." in Path(name).parts
        for name in names
    ):
        errors.append("ZIP root/path safety differs")

    closure = json.loads(CLOSURE.read_text(encoding="utf-8"))
    final_audit = json.loads(FINAL_AUDIT.read_text(encoding="utf-8"))
    positive, checks = validate_model(closure, manifest, final_audit)
    if not positive:
        errors.append("time-to-root-cause semantic positive differs")

    mutations: list[tuple[str, dict[str, Any], str]] = []
    mutated = copy.deepcopy(closure)
    mutated["causal_slice"]["keep_exact_set"] = "sum_s1 prefix removed"
    mutations.append(("required_prefix_deleted", mutated, "keep_exact_set_declared"))
    mutated = copy.deepcopy(closure)
    mutated["causal_slice"]["fd_precondition_changed"] = True
    mutations.append(
        ("boundary_provenance_mutated", mutated, "pre_divergence_semantics_unchanged")
    )
    mutated = copy.deepcopy(closure)
    del mutated["successor"]["candidate_discrimination_matrix"][
        "direct_consumer_not_dequeuing"
    ]
    mutations.append(
        ("candidate_observation_deleted", mutated, "candidate_matrix_complete")
    )
    mutated = copy.deepcopy(closure)
    mutated["causal_slice"]["drop_exact_set"] = ["workload/bitstream/stage1.bin"]
    mutations.append(("unsupported_drop_added", mutated, "drop_exact_set_empty"))
    mutated = copy.deepcopy(closure)
    mutated["successor"]["event_budget"] = "unbounded per-cycle records"
    mutations.append(("event_budget_unbounded", mutated, "qualified_event_limit_256"))
    mutated = copy.deepcopy(closure)
    mutated["return_analysis"]["E4"] = True
    mutations.append(("diagnostic_promoted_to_e4", mutated, "full_chain_claim_not_promoted"))

    negative_controls = []
    for name, candidate, expected_check in mutations:
        valid, observed_checks = validate_model(candidate, manifest, final_audit)
        negative_controls.append(
            {
                "name": name,
                "failed_closed": not valid,
                "expected_check": expected_check,
                "expected_check_false": observed_checks.get(expected_check) is False,
            }
        )
    all_negatives = all(
        item["failed_closed"] and item["expected_check_false"]
        for item in negative_controls
    )
    if not all_negatives:
        errors.append("time-to-root-cause negative control differs")

    zip_after = sha256(ZIP)
    package_bytes_unchanged = zip_before == zip_after == ZIP_SHA256
    if not package_bytes_unchanged:
        errors.append("frozen v33 ZIP changed during revalidation")

    old_server_sha = manifest.get("rule_receipts", {}).get("server_rule_sha256")
    embedded_new_id = RULE_ID in manifest.get(
        "final_zip_rule_self_audit_contract", {}
    ).get("applicable_rule_ids", [])
    result = {
        "schema": "gap-node0071-v33-time-to-root-cause-rule-revalidation-v1",
        "status": (
            "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"
            if not errors else "RULE_DRIFT_REVALIDATION_FAIL"
        ),
        "pass": not errors,
        "rule_id": RULE_ID,
        "old_server_rule_sha256": old_server_sha,
        "current_server_rule_sha256": CURRENT[
            ".agents/rules/服务器测试包生成规则.md"
        ],
        "embedded_manifest_has_new_rule_id": embedded_new_id,
        "embedded_manifest_current_match_after_drift": False,
        "external_current_match_closed": not errors,
        "content_neutral_basis": {
            "publication_record_explicitly_adjudicates_v33_compliant":
                sha256(RULE_UPDATE) == RULE_UPDATE_SHA256,
            "runner_change_required": False,
            "observer_change_required": False,
            "manifest_machine_contract_change_required": False,
            "return_schema_change_required": False,
            "validation_asset_change_required": False,
            "reason": (
                "The frozen release machine report already carries the complete "
                "candidate matrix, bounded information-gain observer evidence, "
                "causal keep/drop audit and non-prunable explanation. The new "
                "rule publication record explicitly adjudicates this exact v33 "
                "strategy compliant; this external validator only binds the "
                "new rule identity and exercises its fail-closed semantics."
            ),
        },
        "diagnostic_execution_reduction": {
            "kept_exact_set":
                closure["causal_slice"]["keep_exact_set"],
            "dropped_exact_set":
                closure["causal_slice"]["drop_exact_set"],
            "checkpoint_provenance": "no legal typed checkpoint before FD",
            "expected_stage_reduction": 0,
            "expected_payload_reduction_bytes": 0,
            "expected_wall_clock_reduction": "0 for the observed sum_s1 hang",
            "nonprunable_reason": closure["causal_slice"]["reason"],
            "full_chain_e4_e5_still_required_after_diagnostic_fix": True,
        },
        "positive_checks": checks,
        "negative_controls": negative_controls,
        "all_negative_controls_fail_closed": all_negatives,
        "frozen_package": {
            "zip": str(ZIP),
            "bytes": ZIP.stat().st_size,
            "sha256_before": zip_before,
            "sha256_after": zip_after,
            "bytes_unchanged": package_bytes_unchanged,
            "sidecar": str(SIDECAR),
            "sidecar_sha256": sha256(SIDECAR),
            "identity_unchanged": True,
        },
        "current_receipts": current_receipts,
        "plan_sha256_mutable_provenance_only":
            sha256(ROOT / ".agents/plan.md"),
        "rule_update_task_record": {
            "path": str(RULE_UPDATE),
            "sha256": sha256(RULE_UPDATE),
        },
        "closure_report": {
            "path": str(CLOSURE),
            "sha256": sha256(CLOSURE),
        },
        "prior_final_zip_audit": {
            "path": str(FINAL_AUDIT),
            "sha256": sha256(FINAL_AUDIT),
            "pass": final_audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS"),
            "error_count": final_audit.get("error_count"),
        },
        "package_release": (
            "PACKAGE_READY_NOT_RUN" if not errors else "PACKAGE_RELEASE_NONE"
        ),
        "errors": errors,
        "error_count": len(errors),
        "package_modified": False,
        "server_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
