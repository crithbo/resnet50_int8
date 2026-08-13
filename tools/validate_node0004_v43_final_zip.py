from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v39_final_zip as audit_base  # noqa: E402


prior = audit_base.prior
previous = audit_base.previous
INSTALL_NAME = "r5_n4_hw_v43_wrterm2_compilefix"
SOURCE_NAME = "r5_n4_hw_v41_wrterm2_diag"
SOURCE_SHA256 = "e314dfb65b1bc7b8ad0403aa559a79508073092988a45e20b8637f21917933b0"
RETURN_SHA256 = "b351089eb76255f23f8190e181a05cbe9bbac1d01c16b555b6eaa3af4424b011"
BUILDER_PLAN_RECEIPT = (
    "1185bc9aca4d033bca553df987192ee6d43cf5882a9ad4950352a67e56692211"
)
CURRENT_RECEIPTS = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server": "68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d",
    "common": "d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}
REQUIRED_RULE_IDS = {
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
    "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
}
FEATURES = audit_base.FEATURES


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v41", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--predicate-public", required=True, type=Path)
    parser.add_argument("--actual-consumers", required=True, type=Path)
    parser.add_argument("--observer-syntax", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    sidecar = args.sidecar.resolve()
    source_path = args.source_v41.resolve()
    entries, zip_errors = prior.read_zip(zip_path, INSTALL_NAME)
    source, source_errors = prior.read_zip(source_path, SOURCE_NAME)
    errors = zip_errors + source_errors
    digest = prior.sha256_file(zip_path)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner = load(args.runner_controls)
    predicate = load(args.predicate_public)
    consumers = load(args.actual_consumers)
    syntax = load(args.observer_syntax)
    return_report = load(args.return_report)
    build_report = load(args.build_report)
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    manifest_files = manifest.get("files", {})
    paths = set(entries) - {"package_manifest.json"}

    runtime_paths = {
        path for path in entries if path.startswith("workload/runtime/")
    }
    source_runtime_paths = {
        path for path in source if path.startswith("workload/runtime/")
    }
    runtime_equal = runtime_paths == source_runtime_paths and all(
        prior.normalized(entries[path], INSTALL_NAME)
        == prior.normalized(source[path], SOURCE_NAME)
        for path in runtime_paths
    )
    changed = [
        path
        for path in sorted(set(entries) & set(source))
        if prior.normalized(entries[path], INSTALL_NAME)
        != prior.normalized(source[path], SOURCE_NAME)
    ]
    added = sorted(set(entries) - set(source))
    removed = sorted(set(source) - set(entries))
    expected_changed = {
        "README.md",
        "package_manifest.json",
        "tb_probe/native_return_observer.svh",
    }
    expected_added = {"provenance/v41_xmr_compilefix_v43.json"}

    previous.INSTALL_NAME = INSTALL_NAME
    previous.FEATURES = FEATURES
    with tempfile.TemporaryDirectory(prefix="v43-final-audit-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        feature_controls = previous.feature_binding_controls(
            root / INSTALL_NAME, root / "feature-controls"
        )

    actual_receipts = {
        "agent": prior.sha256_file(ROOT / ".agents/agent.md"),
        "plan_mutable": prior.sha256_file(ROOT / ".agents/plan.md"),
        "index": prior.sha256_file(
            ROOT / ".agents/rules/生成前必读索引.md"
        ),
        "server": prior.sha256_file(
            ROOT / ".agents/rules/服务器测试包生成规则.md"
        ),
        "common": prior.sha256_file(
            ROOT / ".agents/rules/算子配置规则.md"
        ),
        "ndp": prior.sha256_file(
            ROOT / ".agents/rules/NDP硬件字段语义.md"
        ),
        "int8_sa": prior.sha256_file(
            ROOT / ".agents/rules/INT8_SA点积专项规则.md"
        ),
        "readme": prior.sha256_file(
            ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md"
        ),
    }

    manifest["_prepare_text"] = prepare
    path_positive = previous.v36.path_contract_valid(paths, manifest)
    overdeep = set(paths)
    overdeep.add("w/" + ("x" * 129))
    path_negative_overdeep = not previous.v36.path_contract_valid(
        overdeep, manifest, require_references=False
    )
    repeated = set(paths)
    repeated.add(f"workload/{INSTALL_NAME}/{INSTALL_NAME}/duplicate.bin")
    path_negative_repeated = (
        sum(path.count(INSTALL_NAME) for path in repeated) > 1
        and not previous.v36.path_contract_valid(
            repeated, manifest, require_references=False
        )
    )
    stale_manifest = dict(manifest)
    stale_manifest["_prepare_text"] = prepare.replace(
        "workload/runtime", "workload/shortened", 1
    )
    path_negative_stale = not previous.v36.path_contract_valid(
        paths, stale_manifest
    )

    matrix = manifest.get("release_gate_matrix", [])
    matrix_fields = {
        "gate_id",
        "applicable",
        "reason",
        "changed_surface",
        "evidence",
        "blocking",
    }
    matrix_map = {
        row.get("gate_id"): row for row in matrix if isinstance(row, dict)
    }
    config_gate = matrix_map.get(
        "CHANGED_MATERIALIZED_CONFIG_CONSUMER_CONTRACT", {}
    )
    rules = set(manifest.get("active_receipts", {}).get("rules", []))
    receipt_text = json.dumps(manifest, sort_keys=True)
    checks = {
        "zip_sha": digest == args.expected_zip_sha256,
        "sidecar": (
            sidecar.read_text(encoding="ascii")
            == f"{digest}  {zip_path.name}\n"
        ),
        "source_sha": prior.sha256_file(source_path) == SOURCE_SHA256,
        "bound_return_report": (
            return_report.get("valid") is True
            and return_report.get("RETURN_ANALYSIS", {})
            .get("return_zip", {})
            .get("sha256")
            == RETURN_SHA256
            and return_report.get("FIRST_DIVERGENCE")
            == (
                "VCS_SCOPE_RESOLUTION_FAILS_ON_OBSERVER_LINE_5974_"
                "TOKEN_MEM_IDX_GOTTEN"
            )
        ),
        "build_report_deterministic": (
            build_report.get("zip_sha256") == digest
            and build_report.get("deterministic_rebuild_equal") is True
            and build_report.get("current_server_rule_sha256")
            == CURRENT_RECEIPTS["server"]
        ),
        "manifest_exact_set_hashes": (
            set(manifest_files) == paths
            and all(
                path in entries
                and prior.sha256_bytes(entries[path]) == value
                for path, value in manifest_files.items()
            )
        ),
        "identity_classification": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("classification")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
        ),
        "frozen_scope": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt") is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and runtime_equal
        ),
        "only_expected_source_changes": (
            set(changed) == expected_changed
            and set(added) == expected_added
            and not removed
        ),
        "current_rule_receipts": (
            all(
                actual_receipts[key] == value
                for key, value in CURRENT_RECEIPTS.items()
            )
            and all(
                value in receipt_text for value in CURRENT_RECEIPTS.values()
            )
            and REQUIRED_RULE_IDS.issubset(rules)
            and BUILDER_PLAN_RECEIPT in receipt_text
        ),
        "post_generation_plan_drift_content_neutral": (
            isinstance(actual_receipts["plan_mutable"], str)
            and len(actual_receipts["plan_mutable"]) == 64
        ),
        "release_gate_matrix_single_complete": (
            isinstance(matrix, list)
            and len(matrix) == 9
            and len(matrix_map) == len(matrix)
            and all(matrix_fields == set(row) for row in matrix)
        ),
        "release_gate_matrix_config_rules_consumed": (
            config_gate.get("applicable") is False
            and config_gate.get("blocking") is False
            and "byte-equal" in config_gate.get("reason", "")
            and any(
                "CAUSAL-TRANSACTION-LEDGER" in evidence
                for evidence in config_gate.get("evidence", [])
            )
            and any(
                "BOUNDARY-MICROTRACE" in evidence
                for evidence in config_gate.get("evidence", [])
            )
        ),
        "v41_compile_failure_bound": (
            manifest.get("v41_return_adjudication", {}).get(
                "bound_return_sha256"
            )
            == RETURN_SHA256
            and manifest.get("v41_return_adjudication", {}).get(
                "compile_exit"
            )
            == 2
        ),
        "compilefix_exact": (
            "mem_idx_gotten[1]" not in observer
            and "mem1_gotten=" not in observer
            and "wt_desc_pop && !wt_desc_push" in observer
            and observer.count("WRTERM2_EDGE_V1") == 1
            and observer.count("WRTERM2_BOUNDARY_V1") == 1
        ),
        "predicate_trace_and_public_surface": (
            predicate.get("valid") is True
            and predicate.get("checks", {}).get(
                "predicate_trace_unique_true_final"
            )
            is True
            and predicate.get("public_surface_or_xmr", {}).get(
                "private_xmr_required_for_changed_surface"
            )
            is False
        ),
        "actual_final_hdl_consumers": (
            consumers.get("valid") is True
            and consumers.get("uncovered") == 0
            and consumers.get("classified")
            == consumers.get("actual_consumer_unique")
            and consumers.get("negative_controls", {}).get(
                "actual_leaf_deleted_fail_closed"
            )
            is True
        ),
        "focused_observer_syntax": (
            syntax.get("valid") is True
            and syntax.get("frontend_positive", {}).get("exit_code") == 0
            and syntax.get("all_negative_controls_fail_closed") is True
        ),
        "runner_controls": runner.get("valid") is True,
        "feature_binding_positive": (
            feature_controls["positive"].get("valid") is True
            and len(feature_controls["positive"].get("features", []))
            == len(FEATURES)
        ),
        "feature_binding_negatives": (
            feature_controls["all_negative_controls_fail_closed"]
        ),
        "runtime_and_argv_feature_binding": (
            runtime.count('"feature": "RETURN_OBS_WRTERM"') == 1
            and prepare.count("+RETURN_OBS_WRTERM_LIMIT=96") == 2
        ),
        "path_budget_positive": path_positive,
        "path_budget_negative_overdeep": path_negative_overdeep,
        "path_budget_negative_repeated_identity": path_negative_repeated,
        "path_budget_negative_stale_reference": path_negative_stale,
        "minimal_server_preflight": (
            "git rev-parse" not in prepare
            and "README_HARDWARE_SIM_ENTRY" not in prepare
            and "NDP_Top_phy_filelist.f" not in prepare
            and "path-budget --package-root" in prepare
        ),
        "legacy_occupancy_blocker_not_reintroduced": (
            manifest.get("return_reanalysis", {})
            .get("invalidation_receipt", {})
            .get("invalidated_blocker")
            == "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            and manifest.get("return_reanalysis", {})
            .get("invalidation_receipt", {})
            .get("invalidated_status")
            == "WAIT_RTL_FIX"
        ),
        "intermediate_v42_not_release_identity": (
            "r5_n4_hw_v42_wrterm2_compilefix" not in receipt_text
        ),
    }
    if not all(checks.values()):
        errors.extend(
            f"check failed: {name}"
            for name, passed in checks.items()
            if not passed
        )
    report = {
        "schema": "node0004-v43-final-zip-rule-self-audit-v1",
        "valid": not errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "release_gate_matrix": matrix,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "sidecar": {
            "path": str(sidecar),
            "bytes": sidecar.stat().st_size,
            "sha256": prior.sha256_file(sidecar),
        },
        "source_v41_sha256": SOURCE_SHA256,
        "bound_v41_return_sha256": RETURN_SHA256,
        "changed_after_identity_normalization": changed,
        "added_after_identity_normalization": added,
        "removed_after_identity_normalization": removed,
        "predicate_public_sha256": prior.sha256_file(args.predicate_public),
        "actual_consumers_sha256": prior.sha256_file(args.actual_consumers),
        "observer_syntax_sha256": prior.sha256_file(args.observer_syntax),
        "runner_controls_sha256": prior.sha256_file(args.runner_controls),
        "return_report_sha256": prior.sha256_file(args.return_report),
        "build_report_sha256": prior.sha256_file(args.build_report),
        "post_generation_rule_receipts": actual_receipts,
        "builder_plan_mutable_provenance_receipt": BUILDER_PLAN_RECEIPT,
        "feature_binding_controls": feature_controls,
        "path_length_budget_negatives": {
            "overdeep_fail_closed": path_negative_overdeep,
            "repeated_identity_fail_closed": path_negative_repeated,
            "stale_reference_fail_closed": path_negative_stale,
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
