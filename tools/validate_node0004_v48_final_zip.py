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


INSTALL_NAME = "r5_n4_hw_v48_lc9_actual"
SOURCE_NAME = "r5_n4_hw_v47_lc9_split_cloudrtl"
ZIP_SHA256 = "cdb13ac9039cbaac88306669b8b6e6d9bdb3d3956a4f38425610c6b4f2b7971b"
SOURCE_SHA256 = "516173e54132e2ee31cf2d4f750c46a595bb0bf31afb7f5b6661fc5a0ed6a015"
RETURN_SHA256 = "d05cca4f9d823be3c9ff0b675b2a1601ce863f5075dc29ce057eac0371d3589c"
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
CURRENT = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "bd04756ccab49e5a94843a8d9337eda35f818073ea9daa31244be1ae9903e547",
    "server": "36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457",
    "common": "30d0b20979e639d6bd9d0ec81f5e920da19733f0b2e3fe7ba751ef7e44b972d1",
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
    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
    "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
    "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
}


def normalize(data: bytes) -> bytes:
    for identity in (INSTALL_NAME, SOURCE_NAME):
        data = data.replace(identity.encode(), b"<PACKAGE_IDENTITY>")
    return data


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def feature_contract(
    prepare: str,
    runtime: str,
    observer: str,
    feature: dict[str, Any],
) -> bool:
    return common.feature_contract(prepare, runtime, observer, feature)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v47", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--actual-consumers", required=True, type=Path)
    parser.add_argument("--observer-syntax", required=True, type=Path)
    parser.add_argument("--predicate-trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    entries, zip_errors = common.read_zip(zip_path, INSTALL_NAME)
    source, source_errors = common.read_zip(
        args.source_v47.resolve(), SOURCE_NAME
    )
    structural_errors = zip_errors + source_errors
    digest = common.sha256_file(zip_path)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    files = manifest.get("files", {})
    paths = set(entries) - {"package_manifest.json"}
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode(errors="replace")
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode(errors="replace")

    reports = {
        "return": load(args.return_report),
        "build": load(args.build_report),
        "runner": load(args.runner_controls),
        "consumers": load(args.actual_consumers),
        "syntax": load(args.observer_syntax),
        "trace": load(args.predicate_trace),
    }
    current_receipts = {
        name: common.sha256_file(ROOT / path)
        for name, path in RULE_PATHS.items()
    }
    receipts = manifest.get("active_receipts", {})
    rules = set(receipts.get("rules", []))
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
    applicability_values = {
        "blocking_applicable",
        "receipt_reuse",
        "record_only",
        "not_applicable",
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
    allowed_changed = {
        "README.md",
        "package_manifest.json",
        "PREPARE_AND_RUN.sh",
        "package_tools/node0004_hang_localization_runtime.py",
        "tb_probe/native_return_observer.svh",
    }
    added = sorted(set(entries) - set(source))
    removed = sorted(set(source) - set(entries))

    feature = next(
        item
        for item in manifest["diagnostic_feature_runtime_binding"]["features"]
        if item.get("feature") == "RETURN_OBS_LC9_ACTUAL"
    )
    feature_positive = feature_contract(prepare, runtime, observer, feature)
    marker = common.feature_source_marker(feature)
    feature_negatives = {
        "delete_enable_fail_closed": not feature_contract(
            prepare.replace(feature["runtime_enable_parameter"] + " ", "", 2),
            runtime,
            observer,
            feature,
        ),
        "delete_limit_fail_closed": not feature_contract(
            prepare.replace(feature["limit_or_budget_parameters"][0], "", 2),
            runtime,
            observer,
            feature,
        ),
        "delete_time0_marker_fail_closed": not feature_contract(
            prepare, runtime, observer.replace(marker, "", 1), feature
        ),
        "wrong_return_target_fail_closed": not feature_contract(
            prepare,
            runtime,
            observer,
            {**feature, "returned_record_target": "runs/c0/wrong.log"},
        ),
    }

    return_analysis = reports["return"].get("RETURN_ANALYSIS", {})
    cloud = manifest.get("cloud_rtl_authority", {})
    config_app = manifest.get("materialized_config_rule_applicability", {})
    checks = {
        "zip_sha": digest == ZIP_SHA256,
        "sidecar_exact": args.sidecar.read_text(encoding="ascii")
        == f"{digest}  {zip_path.name}\n",
        "source_v47_sha": common.sha256_file(args.source_v47) == SOURCE_SHA256,
        "crc_root_path_duplicate_symlink": not structural_errors,
        "manifest_exact_set": set(files) == paths,
        "manifest_per_file_hashes": all(
            path in entries and common.sha256(entries[path]) == value
            for path, value in files.items()
        ),
        "manifest_identity": manifest.get("install_name") == INSTALL_NAME,
        "classification": (
            manifest.get("candidate_release") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("functional_rtl_modified") is False
        ),
        "return_report_bound": (
            reports["return"].get("valid") is True
            and return_analysis.get("return_zip", {}).get("sha256")
            == RETURN_SHA256
        ),
        "v47_dynamic_gate_fail_closed": (
            return_analysis.get("compile_exit") == 0
            and return_analysis.get("run_exit") == 0
            and return_analysis.get("natural_terminal") is False
            and return_analysis.get("formal_d_present") == 0
            and return_analysis.get("formal_d_missing") == 320
            and return_analysis.get("joint_result_gate") is False
        ),
        "build_deterministic": (
            reports["build"].get("zip_sha256") == digest
            and reports["build"].get("deterministic_rebuild_equal") is True
        ),
        "all_specialized_reports_valid": all(
            reports[name].get("valid") is True
            for name in ("runner", "consumers", "syntax", "trace")
        ),
        "current_receipts": all(
            current_receipts[name] == value for name, value in CURRENT.items()
        ),
        "manifest_current_rules": (
            receipts.get("server_package_rule_sha256") == CURRENT["server"]
            and receipts.get("common_operator_rule_sha256")
            == CURRENT["common"]
        ),
        "required_rule_ids": REQUIRED_RULES <= rules,
        "release_gate_matrix_single_complete": (
            len(matrix) == 9
            and {row.get("gate_id") for row in matrix} == required_matrix
            and all(
                {
                    "gate_id",
                    "applicability",
                    "reason",
                    "changed_surface",
                    "evidence",
                    "blocking",
                }
                <= set(row)
                and row.get("applicability") in applicability_values
                for row in matrix
            )
        ),
        "cloud_authority_exact_nonblocking": (
            cloud.get("approved_commit") == CLOUD_COMMIT
            and cloud.get("local_disk_commit") == CLOUD_COMMIT
            and cloud.get("identity_difference_blocks_compile_or_simulation")
            is False
        ),
        "actual_consumer_uncovered_zero": (
            reports["consumers"].get("actual_consumer_count") == 22
            and reports["consumers"].get("uncovered") == 0
        ),
        "feature_binding_positive": feature_positive,
        "feature_binding_negatives": all(feature_negatives.values()),
        "observer_syntax_scope": reports["syntax"].get("valid") is True,
        "predicate_trace": reports["trace"].get("valid") is True,
        "runner_safe_compile_exit_term": (
            reports["runner"].get("exit_control", {}).get("runner_exit_code")
            == 74
            and reports["runner"].get("term_control", {}).get(
                "runner_exit_code"
            )
            == 143
        ),
        "frozen_runtime_payload_byte_equal": runtime_equal,
        "semantic_changes_exact": set(semantic_changed) == allowed_changed,
        "no_source_file_removed": not removed,
        "only_expected_provenance_added": added
        == ["provenance/v47_return_v48_lc9_actual.json"],
        "config_receipt_reuse": (
            config_app.get("causal_transaction_ledger")
            == "RECEIPT_REUSE_BYTE_EQUAL"
            and config_app.get("boundary_microtrace")
            == "NOT_APPLICABLE_NO_CHANGED_CONFIG_PREDICATE"
            and config_app.get("physical_bank_row_validity")
            == "RECEIPT_REUSE_BYTE_EQUAL_ADDRESS"
        ),
        "internal_path_budget": max(map(len, entries)) <= 240,
        "no_nested_identity_repetition": all(
            path.count(INSTALL_NAME) <= 1 for path in entries
        ),
        "old_occupancy_not_reopened": (
            manifest.get("v47_return_adjudication", {}).get(
                "old_outbuffer_occupancy"
            )
            == "INVALIDATED_NOT_RTL_BUG"
        ),
    }
    valid = all(checks.values())
    report: dict[str, Any] = {
        "schema": "node0004-v48-final-zip-current-rule-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "valid": valid,
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "source_v47_sha256": SOURCE_SHA256,
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
        "feature_negative_controls": feature_negatives,
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
                "consumers": args.actual_consumers,
                "syntax": args.observer_syntax,
                "trace": args.predicate_trace,
            }.items()
        },
        "package_release": "PACKAGE_READY_NOT_RUN" if valid else "QUARANTINED",
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
