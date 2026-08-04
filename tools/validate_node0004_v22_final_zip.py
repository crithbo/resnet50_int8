from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


INSTALL_NAME = "r5_n4_hw_v22_featurebind"
SOURCE_NAME = "r5_n4_hw_v21_bufkeep_fix"
ZIP_SHA256 = "caf96850ceb5dcf66233dd736757bb2e0b3fbb3b63b066dc9c0194022f1ac68b"
SOURCE_SHA256 = (
    "bd9fadb9bdd18c1678461ae055fea7e15be5d414957b76de48f761833e345131"
)
SERVER_RULE_SHA256 = (
    "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
)
INDEX_SHA256 = (
    "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
)
INT8_SA_SHA256 = (
    "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
)
README_SHA256 = (
    "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
)
NEW_RULE_ID = "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
BITSTREAM_REL = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
BITSTREAM_SHA256 = (
    "6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b"
)
RULE_RECEIPTS = {
    ".agents/rules/生成前必读索引.md": INDEX_SHA256,
    ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
    ".agents/rules/INT8_SA点积专项规则.md": INT8_SA_SHA256,
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
}
FEATURES = {
    "RETURN_OBS_DEEP": {
        "enable": "+RETURN_OBS_DEEP",
        "limits": ["+RETURN_OBS_DEEP_LIMIT=256"],
        "marker": "feature=RETURN_OBS_DEEP enabled=%0d limit_name=RETURN_OBS_DEEP_LIMIT limit=%0d",
        "schema": "DEEP_COUNTS",
    },
    "RETURN_OBS_ABPE": {
        "enable": "+RETURN_OBS_ABPE",
        "limits": ["+RETURN_HANG_DIAG_MAX_CYCLES=8388608"],
        "marker": "feature=RETURN_OBS_ABPE enabled=%0d budget_name=RETURN_HANG_DIAG_MAX_CYCLES budget=%0d",
        "schema": "ABPE_BOUNDARY_V1",
    },
    "RETURN_HANG_DIAG": {
        "enable": "+RETURN_HANG_DIAG",
        "limits": [
            "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
            "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
            "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        ],
        "marker": "feature=RETURN_HANG_DIAG enabled=%0d sample_cycles=%0d stall_windows=%0d max_cycles=%0d",
        "schema": "CANONICAL_DIAG_DECISION_V1",
    },
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], list[str]]:
    entries: dict[str, bytes] = {}
    errors: list[str] = []
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failed: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts:
                errors.append(f"unsafe ZIP path: {info.filename}")
                continue
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            if info.filename in seen:
                errors.append(f"duplicate ZIP member: {info.filename}")
                continue
            seen.add(info.filename)
            if pure.parts[0] != root or len(pure.parts) < 2:
                errors.append(f"unexpected ZIP root: {info.filename}")
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            entries[relative] = archive.read(info)
    if roots != {root}:
        errors.append(f"ZIP root set differs: {sorted(roots)}")
    return entries, errors


def normalized_workload_equal(
    entries: dict[str, bytes], source: dict[str, bytes]
) -> bool:
    current_paths = {
        path for path in entries if path.startswith("workload/runtime/")
    }
    source_paths = {
        path for path in source if path.startswith("workload/runtime/")
    }
    if current_paths != source_paths:
        return False
    for path in current_paths:
        current = entries[path]
        previous = source[path]
        try:
            current_text = current.decode("utf-8")
            previous_text = previous.decode("utf-8")
        except UnicodeDecodeError:
            if current != previous:
                return False
            continue
        if current_text.replace(INSTALL_NAME, SOURCE_NAME) != previous_text:
            return False
    return True


def semantic_checks(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    compile_positive: dict[str, Any],
    feature_positive: dict[str, Any],
) -> dict[str, bool]:
    files = manifest.get("files", {})
    receipts = manifest.get("active_receipts", {})
    rules = set(receipts.get("rules", []))
    feature_contract = manifest.get("diagnostic_feature_runtime_binding", {})
    declared = {
        item.get("feature"): item
        for item in feature_contract.get("features", [])
        if isinstance(item, dict)
    }
    runner = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    collector = entries.get(
        "package_tools/node0004_hang_localization_runtime_v7.py", b""
    ).decode("utf-8", errors="replace")
    per_feature: list[bool] = []
    for name, expected in FEATURES.items():
        item = declared.get(name, {})
        per_feature.append(
            item.get("runtime_enable_parameter") == expected["enable"]
            and item.get("limit_or_budget_parameters") == expected["limits"]
            and item.get("expected_record_schema") == expected["schema"]
            and expected["enable"] in runner
            and all(limit in runner for limit in expected["limits"])
            and expected["marker"] in observer
            and f'"feature": "{name}"' in runtime
        )
    return {
        "manifest_exact_set_and_hashes": (
            set(files) == set(entries) - {"package_manifest.json"}
            and all(
                path in entries and sha256_bytes(entries[path]) == expected
                for path, expected in files.items()
            )
        ),
        "identity_and_classification": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema")
            == "resnet50-node0004-feature-runtime-binding-package-v22"
            and manifest.get("classification")
            == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            and manifest.get("candidate_release") is False
        ),
        "no_numeric_config_workload_rebuild": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt_in_this_successor")
            is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
        ),
        "source_v21_bound_and_quarantined": (
            manifest.get("superseded_v21_package", {}).get("sha256")
            == SOURCE_SHA256
            and manifest.get("superseded_v21_package", {}).get("status")
            == "QUARANTINED_RULE_DRIFT_FEATURE_BINDING_INCOMPLETE"
        ),
        "workload_content_neutral_after_root_normalization": (
            normalized_workload_equal(entries, source)
        ),
        "bitstream_preserved": (
            sha256_bytes(entries.get(BITSTREAM_REL, b""))
            == BITSTREAM_SHA256
        ),
        "current_server_rule_and_id": (
            receipts.get("server_package_rule_sha256") == SERVER_RULE_SHA256
            and NEW_RULE_ID in rules
        ),
        "three_feature_manifest_runner_marker_closure": (
            set(declared) == set(FEATURES) and all(per_feature)
        ),
        "feature_receipt_generated_and_returned": (
            "node0004-diagnostic-feature-runtime-binding-v1" in runtime
            and "diagnostic_feature_binding.json" in runtime
            and '"evidence/diagnostic_feature_binding.json"' in collector
            and feature_contract.get("receipt_return_target")
            == "evidence/diagnostic_feature_binding.json"
            and feature_contract.get("feature_record_return_target")
            == "runs/c0/return_observer.log"
            and feature_contract.get("simulator_argv_return_target")
            == "runs/c0/simulator_argv.txt"
        ),
        "compile_positive_control": (
            compile_positive.get("valid") is True
            and compile_positive.get("zip", {}).get("sha256") == ZIP_SHA256
            and compile_positive.get("positive_control", {}).get(
                "runner_exit_code"
            )
            == 73
        ),
        "feature_simulator_positive_control": (
            feature_positive.get("valid") is True
            and feature_positive.get("zip", {}).get("sha256") == ZIP_SHA256
            and feature_positive.get("runner_exit_code") == 74
            and feature_positive.get("feature_binding_receipt", {}).get(
                "valid"
            )
            is True
            and all(feature_positive.get("checks", {}).values())
        ),
    }


def evaluate(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    compile_positive: dict[str, Any],
    feature_positive: dict[str, Any],
) -> tuple[bool, list[str], dict[str, bool]]:
    checks = semantic_checks(
        entries, manifest, source, compile_positive, feature_positive
    )
    errors = [
        f"semantic check failed: {name}"
        for name, passed in checks.items()
        if not passed
    ]
    return not errors, errors, checks


def negative_controls(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    compile_positive: dict[str, Any],
    feature_positive: dict[str, Any],
) -> dict[str, Any]:
    cases: dict[str, tuple[dict[str, bytes], dict[str, Any]]] = {}

    delete_enable_entries = dict(entries)
    runner = delete_enable_entries["PREPARE_AND_RUN.sh"].decode("utf-8")
    delete_enable_entries["PREPARE_AND_RUN.sh"] = runner.replace(
        "+RETURN_OBS_DEEP", ""
    ).encode("utf-8")
    delete_enable_manifest = copy.deepcopy(manifest)
    delete_enable_manifest["files"]["PREPARE_AND_RUN.sh"] = sha256_bytes(
        delete_enable_entries["PREPARE_AND_RUN.sh"]
    )
    cases["delete_feature_enable"] = (
        delete_enable_entries,
        delete_enable_manifest,
    )

    tamper_limit_entries = dict(entries)
    runner = tamper_limit_entries["PREPARE_AND_RUN.sh"].decode("utf-8")
    tamper_limit_entries["PREPARE_AND_RUN.sh"] = runner.replace(
        "+RETURN_OBS_DEEP_LIMIT=256",
        "+RETURN_OBS_DEEP_LIMIT=255",
    ).encode("utf-8")
    tamper_limit_manifest = copy.deepcopy(manifest)
    tamper_limit_manifest["files"]["PREPARE_AND_RUN.sh"] = sha256_bytes(
        tamper_limit_entries["PREPARE_AND_RUN.sh"]
    )
    cases["tamper_feature_limit"] = (
        tamper_limit_entries,
        tamper_limit_manifest,
    )

    delete_marker_entries = dict(entries)
    observer = delete_marker_entries[
        "tb_probe/native_return_observer.svh"
    ].decode("utf-8")
    delete_marker_entries[
        "tb_probe/native_return_observer.svh"
    ] = observer.replace(
        FEATURES["RETURN_OBS_DEEP"]["marker"], "deleted-marker-contract"
    ).encode("utf-8")
    delete_marker_manifest = copy.deepcopy(manifest)
    delete_marker_manifest["files"][
        "tb_probe/native_return_observer.svh"
    ] = sha256_bytes(
        delete_marker_entries["tb_probe/native_return_observer.svh"]
    )
    cases["delete_time_zero_marker_contract"] = (
        delete_marker_entries,
        delete_marker_manifest,
    )

    delete_return_entries = dict(entries)
    collector = delete_return_entries[
        "package_tools/node0004_hang_localization_runtime_v7.py"
    ].decode("utf-8")
    delete_return_entries[
        "package_tools/node0004_hang_localization_runtime_v7.py"
    ] = collector.replace(
        '"evidence/diagnostic_feature_binding.json"',
        '"evidence/deleted_feature_binding.json"',
    ).encode("utf-8")
    delete_return_manifest = copy.deepcopy(manifest)
    delete_return_manifest["files"][
        "package_tools/node0004_hang_localization_runtime_v7.py"
    ] = sha256_bytes(
        delete_return_entries[
            "package_tools/node0004_hang_localization_runtime_v7.py"
        ]
    )
    cases["delete_feature_return_target"] = (
        delete_return_entries,
        delete_return_manifest,
    )

    result: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest) in cases.items():
        valid, errors, _ = evaluate(
            changed_entries,
            changed_manifest,
            source,
            compile_positive,
            feature_positive,
        )
        result[name] = {
            "command": (
                "python tools/validate_node0004_v22_final_zip.py "
                f"--internal-negative {name}"
            ),
            "expected_exit_code": 1,
            "observed_exit_code": 0 if valid else 1,
            "failed_closed": not valid,
            "errors": errors,
        }
    result["all_failed_closed"] = all(
        item.get("failed_closed") is True for item in result.values()
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-v21", type=Path, required=True)
    parser.add_argument("--compile-positive", type=Path, required=True)
    parser.add_argument("--feature-positive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    zip_path = args.zip.resolve()
    sidecar_path = args.sidecar.resolve()
    source_path = args.source_v21.resolve()
    errors: list[str] = []
    observed_sha = sha256_file(zip_path)
    if observed_sha != ZIP_SHA256:
        errors.append("ZIP SHA mismatch")
    sidecar_text = sidecar_path.read_text(encoding="ascii").strip()
    if sidecar_text != f"{observed_sha}  {zip_path.name}":
        errors.append("sidecar mismatch")
    if sha256_file(source_path) != SOURCE_SHA256:
        errors.append("source v21 SHA mismatch")
    entries, zip_errors = read_zip(zip_path, INSTALL_NAME)
    source, source_errors = read_zip(source_path, SOURCE_NAME)
    errors.extend(zip_errors)
    errors.extend(source_errors)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    compile_positive = json.loads(
        args.compile_positive.resolve().read_text(encoding="utf-8")
    )
    feature_positive = json.loads(
        args.feature_positive.resolve().read_text(encoding="utf-8")
    )
    rule_receipts: dict[str, Any] = {}
    for relative, expected in RULE_RECEIPTS.items():
        path = project / relative
        observed = sha256_file(path) if path.is_file() else None
        match = observed == expected
        rule_receipts[relative] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "current_match": match,
        }
        if not match:
            errors.append(f"active rule drift: {relative}")
    valid, semantic_errors, checks = evaluate(
        entries,
        manifest,
        source,
        compile_positive,
        feature_positive,
    )
    errors.extend(semantic_errors)
    negatives = negative_controls(
        entries,
        manifest,
        source,
        compile_positive,
        feature_positive,
    )
    if not negatives["all_failed_closed"]:
        errors.append("feature negative control did not fail closed")
    passed = valid and not errors and negatives["all_failed_closed"]
    report = {
        "schema": "node0004-v22-final-zip-current-rule-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if passed
            else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "errors": errors,
        "error_count": len(errors),
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": observed_sha,
            "crc_path_root_valid": not zip_errors,
        },
        "sidecar": {
            "path": str(sidecar_path),
            "sha256": sha256_file(sidecar_path),
            "valid": sidecar_text == f"{observed_sha}  {zip_path.name}",
            "server_return_upload_required": False,
        },
        "source_v21": {
            "path": str(source_path),
            "sha256": sha256_file(source_path),
        },
        "rule_receipts": rule_receipts,
        "new_rule_id": NEW_RULE_ID,
        "semantic_checks": checks,
        "compile_positive_control": {
            "path": str(args.compile_positive.resolve()),
            "sha256": sha256_file(args.compile_positive.resolve()),
            "exit_code": 0 if compile_positive.get("valid") else 1,
            "stub_exit": compile_positive.get("positive_control", {}).get(
                "runner_exit_code"
            ),
        },
        "feature_simulator_positive_control": {
            "path": str(args.feature_positive.resolve()),
            "sha256": sha256_file(args.feature_positive.resolve()),
            "exit_code": 0 if feature_positive.get("valid") else 1,
            "stub_exit": feature_positive.get("runner_exit_code"),
        },
        "negative_controls": negatives,
        "all_required_negative_controls_fail_closed": negatives[
            "all_failed_closed"
        ],
        "v21_status": "QUARANTINED_RULE_DRIFT_FEATURE_BINDING_INCOMPLETE",
        "numeric_analysis_repeated": False,
        "configuration_rebuilt_in_this_successor": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "claim_boundary": (
            "package-local feature delivery validation only; no VCS, DUT "
            "simulation, natural terminal, formal D, E3, E4, or E5"
        ),
    }
    args.output.resolve().write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
