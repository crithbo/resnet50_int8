from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v34_final_zip as old  # noqa: E402


v33 = old.v33
prior = old.prior
INSTALL_NAME = "r5_n4_hw_v36_b5rd_diag"
SOURCE_NAME = "r5_n4_hw_v35_rowlc4_bufag_diag"
SOURCE_SHA256 = "af9f94d12275e9b5e9b138101354811bf5fdc4c7a5f4b3ef32cf7d94dd5f90cd"
RETURN_SHA256 = "e8c6496c95ae618d6f85c8c89f6ca3a0f17659cbe925857d71c545d5187a84ba"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
RTL_SYNC_SHA256 = "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"
CURRENT_RECEIPTS = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "plan_mutable": "d9d63138769fea2cb26e70da9350bbcd2ea16dd4fcb15d74d21c5e194e56ca2e",
    "index": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server": "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1",
    "common": "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}
BUILDER_PLAN_MUTABLE_RECEIPT = (
    "d9d63138769fea2cb26e70da9350bbcd2ea16dd4fcb15d74d21c5e194e56ca2e"
)
FEATURES = (
    (
        "RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
    ),
    (
        "RETURN_OBS_MSE4_DESCRIPTOR",
        "+RETURN_OBS_MSE4_DESCRIPTOR",
        "+RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96",
    ),
    (
        "RETURN_OBS_MSE4_INDEX",
        "+RETURN_OBS_MSE4_INDEX",
        "+RETURN_OBS_MSE4_INDEX_LIMIT=96",
    ),
    (
        "RETURN_OBS_LC18_PE7",
        "+RETURN_OBS_LC18_PE7",
        "+RETURN_OBS_LC18_PE7_LIMIT=96",
    ),
    (
        "RETURN_OBS_ROWLC4_BUFAG",
        "+RETURN_OBS_ROWLC4_BUFAG",
        "+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128",
    ),
    (
        "RETURN_OBS_B5RD",
        "+RETURN_OBS_B5RD",
        "+RETURN_OBS_B5RD_LIMIT=96",
    ),
)
v33.FEATURES = FEATURES


def path_metrics(paths: set[str], install_name: str) -> dict[str, object]:
    inner = [path for path in paths if path]
    longest = max(inner, key=len)
    projected = [
        f"install/cfg_pkg/{install_name}/{path}" for path in inner
    ] + [
        f"run_{install_name}/compile/sim_results/compile_driver.log",
        f"evidence_{install_name}/SERVER_RESULT_GATE.json",
        f"{install_name}_return/runs/c0/return_observer.log",
    ]
    longest_projected = max(projected, key=len)
    return {
        "max_inner_suffix_chars": len(longest),
        "max_inner_depth": max(path.count("/") + 1 for path in inner),
        "max_inner_component_chars": max(
            len(part) for path in inner for part in path.split("/")
        ),
        "longest_inner_member": longest,
        "longest_projected_relative_path": longest_projected,
        "declared_worst_projected_absolute_chars": 96 + 1 + len(longest_projected),
    }


def path_contract_valid(
    paths: set[str], manifest: dict, *, require_references: bool = True
) -> bool:
    budget = manifest.get("path_length_budget", {})
    metrics = path_metrics(paths, manifest.get("install_name", ""))
    refs_ok = True
    if require_references:
        prepare = manifest["_prepare_text"]
        refs_ok = all(
            token in prepare
            for token in (
                "package_tools/node0004_hang_localization_runtime.py",
                "tb_probe",
                "workload/runtime",
                "path-budget --package-root",
            )
        )
    return (
        budget.get("pass") is True
        and budget.get("declared_target_root_max_chars") == 96
        and budget.get("max_projected_absolute_path_chars") == 240
        and budget.get("max_inner_suffix_chars")
        == metrics["max_inner_suffix_chars"]
        and budget.get("max_inner_depth") == metrics["max_inner_depth"]
        and budget.get("longest_inner_member") == metrics["longest_inner_member"]
        and budget.get("longest_projected_relative_path")
        == metrics["longest_projected_relative_path"]
        and metrics["max_inner_suffix_chars"] <= 128
        and metrics["max_inner_depth"] <= 8
        and metrics["declared_worst_projected_absolute_chars"] <= 240
        and all(
            manifest.get("install_name", "") not in path for path in paths
        )
        and refs_ok
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v35", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--observer-scope", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    source_path = args.source_v35.resolve()
    entries, zip_errors = prior.read_zip(zip_path, INSTALL_NAME)
    source, source_errors = prior.read_zip(source_path, SOURCE_NAME)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner = json.loads(args.runner_controls.read_text(encoding="utf-8"))
    scope = json.loads(args.observer_scope.read_text(encoding="utf-8"))
    return_report = json.loads(args.return_report.read_text(encoding="utf-8"))
    digest = prior.sha256_file(zip_path)
    errors = zip_errors + source_errors
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    manifest["_prepare_text"] = prepare

    manifest_files = manifest.get("files", {})
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
        "PREPARE_AND_RUN.sh",
        "README.md",
        "package_manifest.json",
        "package_tools/node0004_hang_localization_runtime.py",
        "tb_probe/native_return_observer.svh",
    }
    expected_added = {
        "provenance/rtl_e1fb.json",
        "provenance/diag_reduction_v36.json",
    }
    expected_removed = {
        "provenance/current_local_rtl_binding.json",
        "provenance/v35_diagnostic_execution_reduction.json",
    }
    binding = json.loads(entries.get("provenance/rtl_e1fb.json", b"{}"))
    reduction = json.loads(
        entries.get("provenance/diag_reduction_v36.json", b"{}")
    )
    receipt_text = json.dumps(manifest, sort_keys=True)
    with tempfile.TemporaryDirectory(prefix="v36-final-audit-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        feature_controls = v33.feature_binding_controls(
            root / INSTALL_NAME, root / "feature-controls"
        )

    local_leaf_match = all(
        (ROOT / leaf["path"]).is_file()
        and prior.sha256_file(ROOT / leaf["path"]) == leaf["sha256"]
        for leaf in binding.get("focused_direct_consumers", [])
    )
    paths = set(entries) - {"package_manifest.json"}
    positive_path = path_contract_valid(paths, manifest)
    # Three required path negatives: over-budget deep member, repeated long
    # identity, and a shortened/member-reference divergence.
    overbudget_paths = set(paths)
    overbudget_paths.add("w/" + ("x" * 129))
    overbudget_negative = not path_contract_valid(
        overbudget_paths, manifest, require_references=False
    )
    repeated_paths = set(paths)
    repeated_paths.add(
        f"workload/{INSTALL_NAME}/{INSTALL_NAME}/duplicate.bin"
    )
    repeated_negative = (
        sum(path.count(INSTALL_NAME) for path in repeated_paths) > 1
        and not path_contract_valid(
            repeated_paths, manifest, require_references=False
        )
    )
    stale_reference_manifest = dict(manifest)
    stale_reference_manifest["_prepare_text"] = prepare.replace(
        "workload/runtime", "workload/shortened", 1
    )
    stale_reference_negative = not path_contract_valid(
        paths, stale_reference_manifest
    )

    actual_rule_hashes = {
        "agent": prior.sha256_file(ROOT / ".agents/agent.md"),
        "plan_mutable": prior.sha256_file(ROOT / ".agents/plan.md"),
        "index": prior.sha256_file(ROOT / ".agents/rules/生成前必读索引.md"),
        "server": prior.sha256_file(ROOT / ".agents/rules/服务器测试包生成规则.md"),
        "common": prior.sha256_file(ROOT / ".agents/rules/算子配置规则.md"),
        "ndp": prior.sha256_file(ROOT / ".agents/rules/NDP硬件字段语义.md"),
        "int8_sa": prior.sha256_file(ROOT / ".agents/rules/INT8_SA点积专项规则.md"),
        "readme": prior.sha256_file(ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
    }
    checks = {
        "zip_sha": digest == args.expected_zip_sha256,
        "sidecar": (
            args.sidecar.read_text(encoding="ascii")
            == f"{digest}  {zip_path.name}\n"
        ),
        "source_sha": prior.sha256_file(source_path) == SOURCE_SHA256,
        "bound_return_report": (
            return_report.get("valid") is True
            and return_report.get("RETURN_ANALYSIS", {})
            .get("return_zip", {})
            .get("sha256")
            == RETURN_SHA256
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
            and manifest.get("configuration_rebuilt_in_this_successor")
            is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and runtime_equal
        ),
        "only_expected_source_changes": (
            set(changed) == expected_changed
            and set(added) == expected_added
            and set(removed) == expected_removed
        ),
        "current_rule_receipts": (
            actual_rule_hashes == CURRENT_RECEIPTS
            and all(
                value in receipt_text
                for key, value in CURRENT_RECEIPTS.items()
                if key != "plan_mutable"
            )
            and BUILDER_PLAN_MUTABLE_RECEIPT in receipt_text
        ),
        "path_budget_positive": positive_path,
        "path_budget_negative_overdeep": overbudget_negative,
        "path_budget_negative_repeated_identity": repeated_negative,
        "path_budget_negative_stale_reference": stale_reference_negative,
        "time_to_root_cause_matrix": (
            reduction.get("rule_id")
            == "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001"
            and len(reduction.get("candidate_observation_matrix", {})) == 5
            and reduction.get("kept", {}).get("stages") == ["c0"]
            and reduction.get("dropped", {}).get("stages") == []
        ),
        "observer_corrections": (
            "!return_obs_rb_buf_match_prev" in observer
            and observer.count(
                'return_obs_write_rowlc4_bufag_state("DIAG_DECISION");'
            )
            == 1
            and observer.count(
                'return_obs_write_b5rd_state("DIAG_DECISION");'
            )
            == 1
        ),
        "b5rd_feature": (
            observer.count("B5RD_EDGE_V1") == 1
            and observer.count("B5RD_BOUNDARY_V1") == 1
            and runtime.count('"feature": "RETURN_OBS_B5RD"') == 1
            and prepare.count("+RETURN_OBS_B5RD_LIMIT=96") == 2
        ),
        "current_local_rtl_binding": (
            binding.get("current_local_rtl_commit") == RTL_COMMIT
            and binding.get("sync_report_sha256") == RTL_SYNC_SHA256
            and local_leaf_match
            and manifest.get("current_local_rtl_binding") == binding
        ),
        "no_stale_current_rtl_provenance": (
            "provenance/current_local_rtl_binding.json" not in entries
            and binding.get("current_local_rtl_commit") == RTL_COMMIT
        ),
        "runner_controls": runner.get("valid") is True,
        "observer_scope": (
            scope.get("valid") is True
            and scope.get("all_negative_controls_fail_closed") is True
            and scope.get("package_local_hdl_gate", {}).get("pass") is True
        ),
        "feature_binding_positive": (
            feature_controls["positive"].get("valid") is True
            and len(feature_controls["positive"].get("features", [])) == 6
        ),
        "feature_binding_negatives": (
            feature_controls["all_negative_controls_fail_closed"]
        ),
        "minimal_server_preflight": (
            "git rev-parse" not in prepare
            and "README_HARDWARE_SIM_ENTRY" not in prepare
            and "NDP_Top_phy_filelist.f" not in prepare
            and "path-budget --package-root" in prepare
        ),
    }
    if not all(checks.values()):
        errors += [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "node0004-v36-final-zip-rule-self-audit-v1",
        "valid": not errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "sidecar": {
            "path": str(args.sidecar.resolve()),
            "bytes": args.sidecar.stat().st_size,
            "sha256": prior.sha256_file(args.sidecar),
        },
        "source_v35_sha256": prior.sha256_file(source_path),
        "bound_v35_return_sha256": RETURN_SHA256,
        "changed_after_identity_normalization": changed,
        "added_after_identity_normalization": added,
        "removed_after_identity_normalization": removed,
        "path_length_budget": {
            "positive": path_metrics(paths, INSTALL_NAME),
            "negative_controls": {
                "overdeep_member_fail_closed": overbudget_negative,
                "repeated_identity_fail_closed": repeated_negative,
                "stale_reference_fail_closed": stale_reference_negative,
            },
        },
        "feature_binding_controls": feature_controls,
        "runner_controls_sha256": prior.sha256_file(args.runner_controls),
        "observer_scope_sha256": prior.sha256_file(args.observer_scope),
        "return_report_sha256": prior.sha256_file(args.return_report),
        "current_receipts": actual_rule_hashes,
        "builder_plan_mutable_provenance_receipt": (
            BUILDER_PLAN_MUTABLE_RECEIPT
        ),
        "plan_drift_content_neutral": (
            actual_rule_hashes["plan_mutable"]
            != BUILDER_PLAN_MUTABLE_RECEIPT
        ),
        "current_local_rtl_commit": RTL_COMMIT,
        "rtl_sync_report_sha256": RTL_SYNC_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
