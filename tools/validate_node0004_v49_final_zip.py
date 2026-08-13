from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v46_final_zip as common


INSTALL_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
SOURCE_NAME = "r5_n4_hw_v48_lc9_actual"
ZIP_SHA256 = "2b7faeb4b838133f041432ff707792047d113bf65871aa8936e3f2f4c502e27c"
SOURCE_SHA256 = "cdb13ac9039cbaac88306669b8b6e6d9bdb3d3956a4f38425610c6b4f2b7971b"
RETURN_SHA256 = "91cb18d7e0a1d687597503026ed0155af0c8cf2f491a1712318897122148a27a"
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
CURRENT = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc",
    "server": "4ff581d2add191c6345948489b90d3ccaa43fcae9c31eab8b75bcc99fae2de0b",
    "common": "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
}
RULE_PATHS = {
    "agent": ".agents/agent.md",
    "plan_mutable": ".agents/plan.md",
    "index": ".agents/rules/生成前必读索引.md",
    "server": ".agents/rules/服务器测试包生成规则.md",
    "common": ".agents/rules/算子配置规则.md",
    "ndp": ".agents/rules/NDP硬件字段语义.md",
    "int8_sa": ".agents/rules/INT8_SA点积专项规则.md",
    "readme": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}
REQUIRED_RULES = {
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
    "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
    "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(data: bytes) -> bytes:
    for identity in (INSTALL_NAME, SOURCE_NAME):
        data = data.replace(identity.encode(), b"<PACKAGE_IDENTITY>")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v48", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--branch-scope", required=True, type=Path)
    parser.add_argument("--observer-syntax", required=True, type=Path)
    parser.add_argument("--predicate-trace", required=True, type=Path)
    parser.add_argument("--trigger-profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    entries, zip_errors = common.read_zip(zip_path, INSTALL_NAME)
    source, source_errors = common.read_zip(
        args.source_v48.resolve(), SOURCE_NAME
    )
    digest = common.sha256_file(zip_path)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    files = manifest.get("files", {})
    paths = set(entries) - {"package_manifest.json"}
    reports = {
        "return": load(args.return_report),
        "build": load(args.build_report),
        "runner": load(args.runner_controls),
        "branch": load(args.branch_scope),
        "syntax": load(args.observer_syntax),
        "trace": load(args.predicate_trace),
        "profile": load(args.trigger_profile),
    }
    receipts = manifest.get("active_receipts", {})
    current_receipts = {
        name: common.sha256_file(ROOT / path)
        for name, path in RULE_PATHS.items()
    }

    runtime_paths = {
        path for path in entries if path.startswith("workload/runtime/")
    }
    source_runtime_paths = {
        path for path in source if path.startswith("workload/runtime/")
    }
    runtime_equal = runtime_paths == source_runtime_paths and all(
        normalize(entries[path]) == normalize(source[path])
        for path in runtime_paths
    )
    common_paths = set(entries) & set(source)
    semantic_changed = sorted(
        path
        for path in common_paths
        if normalize(entries[path]) != normalize(source[path])
    )
    added = sorted(set(entries) - set(source))
    removed = sorted(set(source) - set(entries))

    observer_path = "tb_probe/native_return_observer.svh"
    observer = entries.get(observer_path, b"")
    profile_path = "provenance/triggered_causal_observability_v1.json"
    profile = entries.get(profile_path, b"")
    matrix = manifest.get("release_gate_matrix", [])
    required_matrix = {
        "PACKAGE_BOOTSTRAP_PATH_RUNTIME_D",
        "RUNNER_TO_COMPILE_AND_FINALIZER",
        "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL",
        "CHANGED_MATERIALIZED_CONFIG_CONSUMER_CONTRACT",
        "CHANGED_OBSERVER_OR_CANONICAL_SEMANTICS",
        "RETURN_RESULT_JOINT_GATE",
        "FROZEN_NUMERIC_W3_GOLDEN",
        "UNRELATED_FUNCTIONAL_RTL",
        "REPORT_STYLE_OR_SYNONYMOUS_NEGATIVES",
    }
    applicability = {
        "blocking_applicable",
        "receipt_reuse",
        "record_only",
        "not_applicable",
    }
    return_analysis = reports["return"].get("RETURN_ANALYSIS", {})
    branch = reports["branch"]
    cloud = manifest.get("cloud_rtl_authority", {})
    config_app = manifest.get("materialized_config_rule_applicability", {})
    trigger_binding = manifest.get(
        "server_triggered_causal_observability", {}
    )

    checks = {
        "zip_sha": digest == ZIP_SHA256,
        "sidecar_exact": args.sidecar.read_text(encoding="ascii")
        == f"{digest}  {zip_path.name}\n",
        "source_v48_sha": common.sha256_file(args.source_v48) == SOURCE_SHA256,
        "crc_root_path_duplicate_symlink": not (zip_errors + source_errors),
        "manifest_exact_set": set(files) == paths,
        "manifest_per_file_hashes": all(
            path in entries and common.sha256(entries[path]) == value
            for path, value in files.items()
        ),
        "manifest_identity": manifest.get("install_name") == INSTALL_NAME,
        "classification": (
            manifest.get("classification")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("functional_rtl_modified") is False
        ),
        "return_report_bound": (
            reports["return"].get("valid") is True
            and return_analysis.get("return_zip", {}).get("sha256")
            == RETURN_SHA256
        ),
        "v48_compile_escape_fail_closed": (
            return_analysis.get("compile_exit") == 2
            and return_analysis.get("run_exit") == 125
            and return_analysis.get("natural_terminal") is False
            and return_analysis.get("formal_d_present") == 0
            and return_analysis.get("formal_d_missing") == 320
            and return_analysis.get("joint_result_gate") is False
        ),
        "build_deterministic": (
            reports["build"].get("zip_sha256") == digest
            and reports["build"].get("deterministic_rebuild_equal") is True
        ),
        "specialized_reports_valid": all(
            reports[name].get("valid") is True
            for name in ("runner", "branch", "syntax", "trace", "profile")
        ),
        "current_receipts": all(
            current_receipts[name] == value for name, value in CURRENT.items()
        ),
        "manifest_current_rules": (
            receipts.get("server_package_rule_sha256") == CURRENT["server"]
            and receipts.get("common_operator_rule_sha256")
            == CURRENT["common"]
        ),
        "required_rule_ids": REQUIRED_RULES
        <= set(receipts.get("rules", [])),
        "release_gate_matrix_single_complete": (
            len(matrix) == 9
            and {row.get("gate_id") for row in matrix} == required_matrix
            and all(
                row.get("applicability") in applicability
                and {
                    "gate_id",
                    "applicability",
                    "reason",
                    "changed_surface",
                    "evidence",
                    "blocking",
                }
                <= set(row)
                for row in matrix
            )
        ),
        "cloud_authority_exact_nonblocking": (
            cloud.get("approved_commit") == CLOUD_COMMIT
            and cloud.get("local_disk_commit") == CLOUD_COMMIT
            and cloud.get("identity_difference_blocks_compile_or_simulation")
            is False
        ),
        "mse3_actual_generate_branch_positive": (
            branch.get("positive", {}).get("expected_branch") == "RD_MSE"
            and branch.get("positive", {}).get("rd_path_occurrences") == 15
            and branch.get("positive", {}).get("wr_path_occurrences") == 0
            and branch.get("positive", {}).get(
                "current_rtl_generate_rd_found"
            )
            is True
        ),
        "mse3_actual_generate_branch_negatives": all(
            branch.get("negative_controls", {}).values()
        ),
        "observer_sha_bound": (
            common.sha256(observer)
            == branch.get("observer", {}).get("sha256")
            == reports["syntax"].get("final_observer", {}).get("sha256")
            == reports["trace"].get("observer", {}).get("sha256")
        ),
        "trigger_profile_bound": (
            common.sha256(profile)
            == trigger_binding.get("contract_sha256")
            and trigger_binding.get("exact_final_hdl_binding") is True
            and trigger_binding.get("owner_clock")
            == "u_NDP_Top_new.clk_db"
            and trigger_binding.get("owner_reset")
            == "u_NDP_Top_new.rst_n_db"
            and trigger_binding.get("per_event_text_io") is False
        ),
        "runner_safe_compile_exit_term": (
            reports["runner"].get("exit_control", {}).get("runner_exit_code")
            == 74
            and reports["runner"].get("term_control", {}).get(
                "runner_exit_code"
            )
            == 143
        ),
        "runner_feature_and_canonical_negatives": (
            reports["runner"].get("checks", {}).get("package_immutable")
            is True
            and all(
                reports["runner"]
                .get("canonical_negative_controls", {})
                .values()
            )
        ),
        "frozen_runtime_payload_byte_equal": runtime_equal,
        "semantic_changes_exact": set(semantic_changed)
        == {
            "README.md",
            "package_manifest.json",
            "tb_probe/native_return_observer.svh",
        },
        "only_expected_added": added
        == [
            "provenance/triggered_causal_observability_v1.json",
            "provenance/v48_return_v49_mse3_branch_fix.json",
        ],
        "no_source_file_removed": not removed,
        "config_receipt_reuse": (
            config_app.get("causal_transaction_ledger")
            == "RECEIPT_REUSE_BYTE_EQUAL"
            and config_app.get("boundary_microtrace")
            == "NOT_APPLICABLE_NO_CHANGED_CONFIG_PREDICATE"
            and config_app.get("physical_bank_row_validity")
            == "RECEIPT_REUSE_BYTE_EQUAL_ADDRESS"
        ),
        "internal_path_budget": max(map(len, entries)) <= 240,
        "old_occupancy_not_reopened": (
            manifest.get("v48_return_adjudication", {}).get(
                "old_outbuffer_occupancy"
            )
            == "INVALIDATED_NOT_RTL_BUG"
        ),
    }
    valid = all(checks.values())
    report = {
        "schema": "node0004-v49-final-zip-current-rule-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "valid": valid,
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "source_v48_sha256": SOURCE_SHA256,
        "bound_return_sha256": RETURN_SHA256,
        "current_rule_receipts": current_receipts,
        "plan_mutable_provenance": {
            "builder_receipt": receipts.get(
                "plan_mutable_provenance_sha256"
            ),
            "current": current_receipts["plan_mutable"],
            "blocking": False,
        },
        "release_gate_matrix": matrix,
        "semantic_changed_files": semantic_changed,
        "added_files": added,
        "removed_files": removed,
        "report_receipts": {
            name: {
                "path": str(path),
                "sha256": common.sha256_file(path),
                "valid": reports[name].get("valid", True),
            }
            for name, path in {
                "return": args.return_report,
                "build": args.build_report,
                "runner": args.runner_controls,
                "branch": args.branch_scope,
                "syntax": args.observer_syntax,
                "trace": args.predicate_trace,
                "profile": args.trigger_profile,
            }.items()
        },
        "control_results": {
            "runner_safe_compile_stub": 74,
            "runner_term_finalizer": 143,
            "scope_wrong_branch_fail_closed": branch.get(
                "negative_controls", {}
            ).get("wrong_branch_WR_MSE"),
            "scope_missing_branch_fail_closed": branch.get(
                "negative_controls", {}
            ).get("missing_RD_MSE"),
            "scope_wrong_sibling_fail_closed": branch.get(
                "negative_controls", {}
            ).get("wrong_sibling_MSE4"),
            "scope_generate_name_drift_fail_closed": branch.get(
                "negative_controls", {}
            ).get("rtl_generate_name_drift"),
            "syntax_missing_declaration": reports["syntax"]
            .get("negative_controls", {})
            .get("missing_declaration", {})
            .get("exit_code"),
            "syntax_task_typo": reports["syntax"]
            .get("negative_controls", {})
            .get("task_typo", {})
            .get("exit_code"),
            "syntax_consumer_typo": reports["syntax"]
            .get("negative_controls", {})
            .get("actual_consumer_typo", {})
            .get("exit_code"),
        },
        "package_release": "PACKAGE_READY_NOT_RUN" if valid else "QUARANTINED",
        "expected_return": f"{INSTALL_NAME}_return.zip",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
