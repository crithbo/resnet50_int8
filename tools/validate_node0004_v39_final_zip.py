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

import tools.validate_node0004_v37_final_zip as previous  # noqa: E402


prior = previous.prior
INSTALL_NAME = "r5_n4_hw_v40_wrterm_diag"
SOURCE_NAME = "r5_n4_hw_v37_wrdrain_diag"
SOURCE_SHA256 = "cd37675c41c3920c292bdb7ff342443222f96a412fe66d7d4d1319540549dbe0"
RETURN_SHA256 = "6a2cc106f6124f3640340531d5f1e62bac245e3c8674bd3fdb0e3307714a2d37"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
BUILDER_PLAN_RECEIPT = (
    "5767a496a0aaa33d2a1b55d5cfc237e9cc5a9192da59a25079a97d0e602779a9"
)
CURRENT_RECEIPTS = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server": "5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9",
    "common": "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}
FEATURES = previous.FEATURES + (
    (
        "RETURN_OBS_WRTERM",
        "+RETURN_OBS_WRTERM",
        ("+RETURN_OBS_WRTERM_LIMIT=96",),
        ("feature=RETURN_OBS_WRTERM", "enabled=1", "limit=96"),
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v37", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--observer-scope", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    sidecar = args.sidecar.resolve()
    source_path = args.source_v37.resolve()
    entries, zip_errors = prior.read_zip(zip_path, INSTALL_NAME)
    source, source_errors = prior.read_zip(source_path, SOURCE_NAME)
    errors = zip_errors + source_errors
    digest = prior.sha256_file(zip_path)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner = json.loads(args.runner_controls.read_text(encoding="utf-8"))
    scope = json.loads(args.observer_scope.read_text(encoding="utf-8"))
    return_report = json.loads(
        args.return_report.read_text(encoding="utf-8")
    )
    build_report = json.loads(args.build_report.read_text(encoding="utf-8"))
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    receipt_text = json.dumps(manifest, sort_keys=True)
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
        "PREPARE_AND_RUN.sh",
        "README.md",
        "package_manifest.json",
        "package_tools/node0004_hang_localization_runtime.py",
        "tb_probe/native_return_observer.svh",
    }
    expected_added = {"provenance/diag_reduction_v38.json"}

    previous.INSTALL_NAME = INSTALL_NAME
    previous.FEATURES = FEATURES
    with tempfile.TemporaryDirectory(prefix="v39-final-audit-") as temp:
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
    reduction = json.loads(
        entries.get("provenance/diag_reduction_v38.json", b"{}")
    )
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

    scope_coverage = scope.get("actual_consumer_coverage", {})
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
        ),
        "build_report_deterministic": (
            build_report.get("zip_sha256") == digest
            and build_report.get("deterministic_rebuild_equal") is True
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
            and all(value in receipt_text for value in CURRENT_RECEIPTS.values())
            and BUILDER_PLAN_RECEIPT in receipt_text
        ),
        "plan_drift_content_neutral": (
            actual_receipts["plan_mutable"] != BUILDER_PLAN_RECEIPT
        ),
        "v37_adjudication": (
            manifest.get("v37_return_adjudication", {}).get(
                "bound_return_sha256"
            )
            == RETURN_SHA256
            and manifest.get("v37_return_adjudication", {}).get(
                "regression"
            )
            is False
        ),
        "candidate_matrix": (
            reduction.get("rule_id")
            == "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001"
            and len(reduction.get("candidate_observation_matrix", {})) == 4
        ),
        "observer_hooks_and_feature": (
            observer.count("WRTERM_EDGE_V1") == 1
            and observer.count("WRTERM_BOUNDARY_V1") == 1
            and observer.count(
                'return_obs_write_wrterm_state("DIAG_DECISION");'
            )
            == 1
            and "return_hang_diag_current_progress"
            not in observer[observer.index("// v38 WRTERM") :]
        ),
        "runtime_and_argv_feature_binding": (
            runtime.count('"feature": "RETURN_OBS_WRTERM"') == 1
            and prepare.count("+RETURN_OBS_WRTERM_LIMIT=96") == 2
        ),
        "runner_controls": runner.get("valid") is True,
        "actual_consumer_scope": (
            scope.get("valid") is True
            and scope.get("all_negative_controls_fail_closed") is True
            and scope.get("rule_id")
            == (
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-"
                "ACTUAL-CONSUMER-001"
            )
            and scope_coverage.get("unique_count", 0) > 0
            and scope_coverage.get("uncovered_count") == 0
        ),
        "feature_binding_positive": (
            feature_controls["positive"].get("valid") is True
            and len(feature_controls["positive"].get("features", []))
            == len(FEATURES)
        ),
        "feature_binding_negatives": (
            feature_controls["all_negative_controls_fail_closed"]
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
            "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            not in json.dumps(
                manifest.get("v37_return_adjudication", {}), sort_keys=True
            )
        ),
    }
    if not all(checks.values()):
        errors += [name for name, value in checks.items() if not value]
    report: dict[str, Any] = {
        "schema": "node0004-v39-final-zip-rule-self-audit-v1",
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
            "path": str(sidecar),
            "bytes": sidecar.stat().st_size,
            "sha256": prior.sha256_file(sidecar),
        },
        "source_v37_sha256": prior.sha256_file(source_path),
        "bound_v37_return_sha256": RETURN_SHA256,
        "changed_after_identity_normalization": changed,
        "added_after_identity_normalization": added,
        "removed_after_identity_normalization": removed,
        "feature_binding_controls": feature_controls,
        "path_length_budget_negatives": {
            "overdeep_fail_closed": path_negative_overdeep,
            "repeated_identity_fail_closed": path_negative_repeated,
            "stale_reference_fail_closed": path_negative_stale,
        },
        "runner_controls_sha256": prior.sha256_file(args.runner_controls),
        "observer_scope_sha256": prior.sha256_file(args.observer_scope),
        "return_report_sha256": prior.sha256_file(args.return_report),
        "build_report_sha256": prior.sha256_file(args.build_report),
        "current_receipts": actual_receipts,
        "builder_plan_mutable_provenance_receipt": BUILDER_PLAN_RECEIPT,
        "plan_drift_content_neutral": (
            actual_receipts["plan_mutable"] != BUILDER_PLAN_RECEIPT
        ),
        "current_local_rtl_commit": RTL_COMMIT,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
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
