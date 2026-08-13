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

import tools.validate_node0004_v36_final_zip as v36  # noqa: E402


prior = v36.prior
INSTALL_NAME = "r5_n4_hw_v37_wrdrain_diag"
SOURCE_NAME = "r5_n4_hw_v36_b5rd_diag"
SOURCE_SHA256 = "08a7d79c50896c18665d551c32522fc39f0f90f4802a8797caa024f4ac474bc2"
RETURN_SHA256 = "f98d448113aafb78c80cbab6cd002e8b783325082a79ae98cf265ffebc38bca5"
RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
RTL_SYNC_SHA256 = "c2e57de1d1d05cc1fee3356cce772fbb3c76943cf04bb5366cbc0a4db6e3539c"
BUILDER_PLAN_RECEIPT = (
    "ae72cd46d134c51eba8455da120d07e9a82dfe1aa29f1bd438e592d556de042e"
)
CURRENT_RECEIPTS = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "plan_mutable": "e5a3d81804f6b23a19f36953e71fd5752e47ba6851dda16f2001b46c7e58af9c",
    "index": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server": "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1",
    "common": "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}
FEATURES = (
    (
        "RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG",
        (
            "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
            "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
            "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        ),
        (
            "feature=RETURN_HANG_DIAG",
            "enabled=1",
            "sample_cycles=262144",
            "stall_windows=4",
            "max_cycles=8388608",
        ),
    ),
    (
        "RETURN_OBS_MSE4_DESCRIPTOR",
        "+RETURN_OBS_MSE4_DESCRIPTOR",
        ("+RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96",),
        ("feature=RETURN_OBS_MSE4_DESCRIPTOR", "enabled=1", "limit=96"),
    ),
    (
        "RETURN_OBS_MSE4_INDEX",
        "+RETURN_OBS_MSE4_INDEX",
        ("+RETURN_OBS_MSE4_INDEX_LIMIT=96",),
        ("feature=RETURN_OBS_MSE4_INDEX", "enabled=1", "limit=96"),
    ),
    (
        "RETURN_OBS_LC18_PE7",
        "+RETURN_OBS_LC18_PE7",
        ("+RETURN_OBS_LC18_PE7_LIMIT=96",),
        ("feature=RETURN_OBS_LC18_PE7", "enabled=1", "limit=96"),
    ),
    (
        "RETURN_OBS_ROWLC4_BUFAG",
        "+RETURN_OBS_ROWLC4_BUFAG",
        ("+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128",),
        ("feature=RETURN_OBS_ROWLC4_BUFAG", "enabled=1", "limit=128"),
    ),
    (
        "RETURN_OBS_B5RD",
        "+RETURN_OBS_B5RD",
        ("+RETURN_OBS_B5RD_LIMIT=96",),
        ("feature=RETURN_OBS_B5RD", "enabled=1", "limit=96"),
    ),
    (
        "RETURN_OBS_DWRITE_PATH",
        "+RETURN_OBS_DWRITE_PATH",
        ("+RETURN_OBS_DWRITE_PATH_LIMIT=64",),
        ("feature=RETURN_OBS_DWRITE_PATH", "enabled=1", "limit=64"),
    ),
    (
        "RETURN_OBS_DATAHUB_DRAIN",
        "+RETURN_OBS_DATAHUB_DRAIN",
        ("+RETURN_OBS_DATAHUB_DRAIN_LIMIT=64",),
        ("feature=RETURN_OBS_DATAHUB_DRAIN", "enabled=1", "limit=64"),
    ),
    (
        "RETURN_OBS_WRDRAIN",
        "+RETURN_OBS_WRDRAIN",
        ("+RETURN_OBS_WRDRAIN_LIMIT=1",),
        ("feature=RETURN_OBS_WRDRAIN", "enabled=1", "limit=1"),
    ),
)


def feature_binding_controls(package: Path, root: Path) -> dict[str, Any]:
    runtime = prior.import_runtime(package)
    evidence = root / "evidence"
    run = root / "run"
    (run / "c0").mkdir(parents=True)
    evidence.mkdir()
    (evidence / "compile_exit_status.txt").write_text("0\n", encoding="ascii")
    argv_tokens = ["simv"]
    for _, enable, limits, _ in FEATURES:
        argv_tokens.append(enable)
        argv_tokens.extend(limits)
    markers = [
        "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | " + " ".join(tokens)
        for _, _, _, tokens in FEATURES
    ]

    def run_case(argv: list[str], rows: list[str]) -> dict[str, Any]:
        (run / "c0/simulator_argv.txt").write_text(
            " ".join(argv) + "\n", encoding="utf-8"
        )
        observer = run / "c0/return_observer.log"
        if rows:
            observer.write_text(
                "\n".join(rows) + "\n", encoding="utf-8"
            )
        elif observer.exists():
            observer.unlink()
        return runtime.diagnostic_feature_binding(evidence, run)

    positive = run_case(argv_tokens, markers)
    per_new_feature: dict[str, Any] = {}
    for name, enable, limits, marker_tokens in FEATURES[-3:]:
        delete_enable = run_case(
            [token for token in argv_tokens if token != enable], markers
        )
        delete_limit = run_case(
            [token for token in argv_tokens if token != limits[0]], markers
        )
        delete_marker = run_case(
            argv_tokens,
            [
                row
                for row in markers
                if marker_tokens[0] not in row
            ],
        )
        delete_return = run_case(argv_tokens, [])
        controls = {
            "delete_enable_fail_closed": delete_enable.get("valid") is False,
            "delete_limit_fail_closed": delete_limit.get("valid") is False,
            "delete_time0_marker_fail_closed": (
                delete_marker.get("valid") is False
            ),
            "delete_return_target_fail_closed": (
                delete_return.get("valid") is False
            ),
        }
        per_new_feature[name] = {
            "controls": controls,
            "valid": all(controls.values()),
        }
    return {
        "positive": positive,
        "per_new_feature_negative_controls": per_new_feature,
        "all_negative_controls_fail_closed": all(
            item["valid"] for item in per_new_feature.values()
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v36", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--observer-scope", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    sidecar = args.sidecar.resolve()
    source_path = args.source_v36.resolve()
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
    expected_added = {"provenance/diag_reduction_v37.json"}
    expected_removed = {"provenance/diag_reduction_v36.json"}

    with tempfile.TemporaryDirectory(prefix="v37-final-audit-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        feature_controls = feature_binding_controls(
            root / INSTALL_NAME, root / "feature-controls"
        )

    actual_rule_hashes = {
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
    binding = json.loads(entries.get("provenance/rtl_e1fb.json", b"{}"))
    local_leaf_match = all(
        (ROOT / leaf["path"]).is_file()
        and prior.sha256_file(ROOT / leaf["path"]) == leaf["sha256"]
        for leaf in binding.get("focused_direct_consumers", [])
    )
    reduction = json.loads(
        entries.get("provenance/diag_reduction_v37.json", b"{}")
    )
    paths = set(entries) - {"package_manifest.json"}
    manifest["_prepare_text"] = prepare
    path_positive = v36.path_contract_valid(paths, manifest)
    overdeep = set(paths)
    overdeep.add("w/" + ("x" * 129))
    path_negative_overdeep = not v36.path_contract_valid(
        overdeep, manifest, require_references=False
    )
    repeated = set(paths)
    repeated.add(f"workload/{INSTALL_NAME}/{INSTALL_NAME}/duplicate.bin")
    path_negative_repeated = (
        sum(path.count(INSTALL_NAME) for path in repeated) > 1
        and not v36.path_contract_valid(
            repeated, manifest, require_references=False
        )
    )
    stale_manifest = dict(manifest)
    stale_manifest["_prepare_text"] = prepare.replace(
        "workload/runtime", "workload/shortened", 1
    )
    path_negative_stale = not v36.path_contract_valid(
        paths, stale_manifest
    )

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
            all(
                actual_rule_hashes[key] == value
                for key, value in CURRENT_RECEIPTS.items()
                if key != "plan_mutable"
            )
            and all(
                value in receipt_text
                for key, value in CURRENT_RECEIPTS.items()
                if key != "plan_mutable"
            )
            and BUILDER_PLAN_RECEIPT in receipt_text
        ),
        "plan_drift_content_neutral": (
            actual_rule_hashes["plan_mutable"] != BUILDER_PLAN_RECEIPT
        ),
        "v36_adjudication": (
            manifest.get("v36_return_adjudication", {}).get(
                "bound_return_sha256"
            )
            == RETURN_SHA256
            and manifest.get("v36_return_adjudication", {}).get(
                "v35_observer_defects_closed"
            )
            is True
        ),
        "candidate_matrix": (
            reduction.get("rule_id")
            == "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001"
            and len(reduction.get("candidate_observation_matrix", {})) == 5
            and reduction.get("kept", {}).get("stages") == ["c0"]
            and reduction.get("dropped", {}).get("stages") == []
        ),
        "observer_hooks_and_feature": (
            observer.count("WRDRAIN_BOUNDARY_V1") == 1
            and observer.count(
                'return_obs_write_wrdrain_state("DIAG_DECISION");'
            )
            == 1
            and all(
                observer.count(
                    f'return_obs_write_{task}("DIAG_DECISION");'
                )
                == 1
                for task in (
                    "mse4_descriptor_state",
                    "mse4_index_state",
                    "dwrite_path_state",
                    "datahub_drain_state",
                )
            )
            and "return_hang_diag_current_progress"
            not in observer[observer.index("// v37:") :]
        ),
        "runtime_and_argv_feature_binding": (
            runtime.count('"feature": "RETURN_OBS_WRDRAIN"') == 1
            and prepare.count("+RETURN_OBS_WRDRAIN_LIMIT=1") == 2
            and prepare.count("+RETURN_OBS_DWRITE_PATH_LIMIT=64") == 2
            and prepare.count("+RETURN_OBS_DATAHUB_DRAIN_LIMIT=64") == 2
        ),
        "current_local_rtl_binding": (
            binding.get("current_local_rtl_commit") == RTL_COMMIT
            and binding.get("sync_report_sha256") == RTL_SYNC_SHA256
            and local_leaf_match
        ),
        "legacy_occupancy_blocker_remains_invalidated": (
            manifest.get("return_reanalysis", {})
            .get("invalidation_receipt", {})
            .get("invalidated_blocker")
            == "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
        ),
        "runner_controls": runner.get("valid") is True,
        "observer_scope": (
            scope.get("valid") is True
            and scope.get("all_negative_controls_fail_closed") is True
            and scope.get("package_local_hdl_gate", {}).get("pass") is True
        ),
        "feature_binding_positive": (
            feature_controls["positive"].get("valid") is True
            and len(
                feature_controls["positive"].get("features", [])
            )
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
    }
    if not all(checks.values()):
        errors += [name for name, value in checks.items() if not value]
    report = {
        "schema": "node0004-v37-final-zip-rule-self-audit-v1",
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
        "source_v36_sha256": prior.sha256_file(source_path),
        "bound_v36_return_sha256": RETURN_SHA256,
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
        "current_receipts": actual_rule_hashes,
        "builder_plan_mutable_provenance_receipt": BUILDER_PLAN_RECEIPT,
        "plan_drift_content_neutral": (
            actual_rule_hashes["plan_mutable"] != BUILDER_PLAN_RECEIPT
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
