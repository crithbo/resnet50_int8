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

import tools.validate_node0004_v33_final_zip as v33  # noqa: E402


prior = v33.prior
INSTALL_NAME = "r5_n4_hw_v35_rowlc4_bufag_diag"
SOURCE_NAME = "r5_n4_hw_v33_lc18_pe7_diag"
SOURCE_SHA256 = "5094fc3e01a04c1931b81c4db3a67bf2f6b82f424124d0311866d03004997c90"
RETURN_SHA256 = "82c1cc545d1df6a9e0359be6902c064af30d7e9631d50fcc4182177eb904105e"
RTL_COMMIT = "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727"
RTL_SYNC_SHA256 = "6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5"
SERVER_RULE_SHA256 = "0916c655b0581cd99836d8cc1561a3f41b15b25e861692d596a4789c039b090e"
CURRENT_RECEIPTS = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "5146225e549942c4e25780ac4fc0120d7cac1ef355879284450dad2e48df237b",
    "server": SERVER_RULE_SHA256,
    "common": "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
}
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
)
v33.FEATURES = FEATURES


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v33", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--observer-scope", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    source_path = args.source_v33.resolve()
    entries, zip_errors = prior.read_zip(zip_path, INSTALL_NAME)
    source, source_errors = prior.read_zip(source_path, SOURCE_NAME)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner = json.loads(args.runner_controls.read_text(encoding="utf-8"))
    scope = json.loads(args.observer_scope.read_text(encoding="utf-8"))
    return_report = json.loads(args.return_report.read_text(encoding="utf-8"))
    digest = prior.sha256_file(zip_path)
    errors = zip_errors + source_errors

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
    expected_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "package_manifest.json",
        "package_tools/node0004_hang_localization_runtime.py",
        "provenance/current_local_rtl_binding.json",
        "tb_probe/native_return_observer.svh",
    }
    expected_added = {"provenance/v35_diagnostic_execution_reduction.json"}
    receipt_text = json.dumps(manifest, sort_keys=True)
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    binding = json.loads(
        entries.get("provenance/current_local_rtl_binding.json", b"{}")
    )
    reduction = json.loads(
        entries.get(
            "provenance/v35_diagnostic_execution_reduction.json", b"{}"
        )
    )
    with tempfile.TemporaryDirectory(prefix="v35-final-audit-") as temp:
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
    required_mapping = {
        "DRAM_LC.LC9": "LC18",
        "GROUP4.ROW_LC": "ROW_LC4",
        "GROUP4.COL_LC": "COL_LC4",
        "LC_PE.PE1": "PE7",
        "STREAM.stream4": "WRITE_STREAM0",
    }
    kept = {
        "RETURN_HANG_DIAG",
        "RETURN_OBS_MSE4_DESCRIPTOR",
        "RETURN_OBS_MSE4_INDEX",
        "RETURN_OBS_LC18_PE7",
        "RETURN_OBS_ROWLC4_BUFAG",
    }
    dropped = {
        "RETURN_OBS_DEEP",
        "RETURN_OBS_ABPE",
        "RETURN_OBS_FINAL_RELEASE",
        "RETURN_OBS_DWRITE_PATH",
        "RETURN_OBS_DATAHUB_DRAIN",
    }
    argv_lines = [
        line
        for line in prepare.splitlines()
        if "+RETURN_OBS_ROWLC4_BUFAG" in line
    ]
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
            set(manifest_files) == set(entries) - {"package_manifest.json"}
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
            set(changed) == expected_changed and set(added) == expected_added
        ),
        "current_rule_receipts": all(
            value in receipt_text for value in CURRENT_RECEIPTS.values()
        ),
        "time_to_root_cause_rule_bound": (
            "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001"
            in manifest.get("active_receipts", {}).get("rules", [])
            and reduction.get("rule_id")
            == "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001"
        ),
        "candidate_observation_matrix": (
            len(reduction.get("candidate_observation_matrix", {})) == 5
            and set(reduction.get("kept", {}).get("observer_features", []))
            == kept
            and set(
                reduction.get("dropped", {}).get(
                    "observer_runtime_features", []
                )
            )
            == dropped
            and reduction.get("kept", {}).get("stages") == ["c0"]
            and reduction.get("dropped", {}).get("stages") == []
            and "No verified hardware checkpoint"
            in reduction.get("why_stage_payload_not_reduced", "")
        ),
        "observer_narrow_feature": (
            observer.count("ROWLC4_BUFAG_BOUNDARY_V1") == 1
            and observer.count("ROWLC4_BUFAG_EDGE_V1") == 1
            and observer.count(
                "return_obs_write_rowlc4_bufag_state(event_name);"
            )
            == 1
        ),
        "actual_runner_binding": (
            len(argv_lines) == 2
            and all(
                "+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128" in line
                and all(f"+{name}" in line for name in kept)
                and all(f"+{name}" not in line for name in dropped)
                for line in argv_lines
            )
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in prepare
            and "+incdir+$package_root/tb_probe" in prepare
        ),
        "collector_binding": (
            runtime.count('"feature": "RETURN_OBS_ROWLC4_BUFAG"') == 1
            and runtime.count(
                '"enable": "+RETURN_OBS_ROWLC4_BUFAG"'
            )
            == 1
            and runtime.count(
                '"limits": ("+RETURN_OBS_ROWLC4_BUFAG_LIMIT=128",)'
            )
            == 1
            and all(f'"feature": "{name}"' not in runtime for name in dropped)
        ),
        "physical_mapping_binding": (
            binding.get("mapping_cache", {}).get("required")
            == required_mapping
        ),
        "current_local_rtl_binding": (
            binding.get("current_local_rtl_commit") == RTL_COMMIT
            and binding.get("sync_report_sha256") == RTL_SYNC_SHA256
            and binding.get("server_run_rtl_identity_bound") is False
            and local_leaf_match
            and manifest.get("current_local_rtl_binding") == binding
        ),
        "runner_controls": runner.get("valid") is True,
        "observer_scope": (
            scope.get("valid") is True
            and scope.get("all_negative_controls_fail_closed") is True
            and scope.get("package_local_hdl_gate", {}).get("pass") is True
        ),
        "feature_binding_positive": (
            feature_controls["positive"].get("valid") is True
            and len(feature_controls["positive"].get("features", [])) == 5
        ),
        "feature_binding_negatives": (
            feature_controls["all_negative_controls_fail_closed"]
        ),
        "minimal_server_preflight": (
            "git rev-parse" not in prepare
            and "README_HARDWARE_SIM_ENTRY" not in prepare
            and "NDP_Top_phy_filelist.f" not in prepare
        ),
    }
    if not all(checks.values()):
        errors += [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "node0004-v35-final-zip-rule-self-audit-v1",
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
        "source_v33_sha256": prior.sha256_file(source_path),
        "bound_v33_return_sha256": RETURN_SHA256,
        "changed_after_identity_normalization": changed,
        "added_after_identity_normalization": added,
        "feature_binding_controls": feature_controls,
        "runner_controls_sha256": prior.sha256_file(args.runner_controls),
        "observer_scope_sha256": prior.sha256_file(args.observer_scope),
        "return_report_sha256": prior.sha256_file(args.return_report),
        "current_receipts": CURRENT_RECEIPTS,
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
