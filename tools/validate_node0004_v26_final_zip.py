from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v25_final_zip as base  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v26_transout_threshold_fix"
SOURCE_NAME = "r5_n4_hw_v25_terminal_match_diag"
ZIP_SHA256 = "94beb61460e033fbf8ec7afd4cd64e38cd23681fb894df9960bd3cb4be962ddb"
SOURCE_SHA256 = "e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab"
RETURN_SHA256 = "e6b35bc2f311b9cdf184c65bdd6f8ad834ededf6888ffb390943b83d87d1ac5f"
BITSTREAM_REL = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
OLD_BITSTREAM_SHA256 = (
    "6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b"
)
NEW_BITSTREAM_SHA256 = (
    "cb12f3345c42d89d17188102bd80cbeef224ddff26fd5726ed1a16af49d14e73"
)
CURRENT_RECEIPTS = {
    ".agents/agent.md": "d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721",
    ".agents/rules/生成前必读索引.md": "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5",
    ".agents/rules/服务器测试包生成规则.md": "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48",
    ".agents/rules/INT8_SA点积专项规则.md": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_identity(payload: bytes) -> bytes:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return text.replace(INSTALL_NAME, SOURCE_NAME).encode("utf-8")


def runtime_preservation(
    entries: dict[str, bytes], source: dict[str, bytes]
) -> dict[str, Any]:
    paths = {p for p in entries if p.startswith("workload/runtime/")}
    source_paths = {p for p in source if p.startswith("workload/runtime/")}
    changed: list[str] = []
    for path in sorted(paths & source_paths):
        if normalize_identity(entries[path]) != source[path]:
            changed.append(path)
    matrices = [
        path
        for path in paths
        if "/matrix_" in path and path.endswith(".txt")
    ]
    return {
        "path_set_equal": paths == source_paths,
        "matrix_count": len(matrices),
        "all_matrices_byte_identical": all(
            entries[path] == source[path] for path in matrices
        ),
        "changed_after_identity_normalization": changed,
        "changed_exactly_bitstream": changed == [BITSTREAM_REL],
    }


def semantic_checks(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    runner: dict[str, Any],
    scope: dict[str, Any],
    local: dict[str, Any],
) -> dict[str, bool]:
    files = manifest.get("files", {})
    observer_payload = entries.get(
        "tb_probe/native_return_observer.svh", b""
    )
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    collector = entries.get(
        "package_tools/node0004_hang_localization_runtime_v7.py", b""
    ).decode("utf-8", errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    preservation = runtime_preservation(entries, source)
    old_bs = source.get(BITSTREAM_REL, b"")
    new_bs = entries.get(BITSTREAM_REL, b"")
    byte_diff = [
        (index, left, right)
        for index, (left, right) in enumerate(zip(old_bs, new_bs))
        if left != right
    ]
    leaf = manifest.get("configuration_fix", {}).get("leaf_changes", [])
    v25 = manifest.get("v25_return_adjudication", {})
    return {
        "manifest_exact_set_hashes": (
            set(files) == set(entries) - {"package_manifest.json"}
            and all(
                path in entries and sha256_bytes(entries[path]) == digest
                for path, digest in files.items()
            )
        ),
        "identity_and_classification": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema")
            == "resnet50-node0004-transout-threshold-config-fix-package-v26"
            and manifest.get("classification")
            == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            and manifest.get("candidate_release") is False
        ),
        "scope_freeze": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt_in_this_successor") is True
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
            and preservation["path_set_equal"]
            and preservation["all_matrices_byte_identical"]
            and preservation["changed_exactly_bitstream"]
        ),
        "source_and_return_binding": (
            manifest.get("superseded_v25_diagnostic", {}).get("sha256")
            == SOURCE_SHA256
            and v25.get("bound_return_sha256") == RETURN_SHA256
            and v25.get("root_cause")
            == (
                "all 256 accepted terminal indices 4/5 exceeded configured "
                "transout_last_index 2 and were classified ignore"
            )
        ),
        "single_authorized_leaf": (
            leaf
            == [
                {
                    "path": "special_array.transout_last_index",
                    "old": 2,
                    "new": 5,
                }
            ]
            and manifest.get("configuration_fix", {})
            .get("old_counterexample", {})
            .get("old_ignored_occurrences")
            == 256
            and manifest.get("configuration_fix", {})
            .get("old_counterexample", {})
            .get("new_released_occurrences")
            == 256
        ),
        "fresh_local_rebuild": (
            local.get("status") == "LOCAL_C0_PHYSICAL_REBUILD_PASS"
            and local.get("old_ignored_occurrences") == 256
            and local.get("new_released_occurrences") == 256
            and local.get("authorized_leaf_changes", [{}])[0].get("old") == 2
            and local.get("authorized_leaf_changes", [{}])[0].get("new") == 5
        ),
        "bitstream_exact_delta": (
            sha256_bytes(old_bs) == OLD_BITSTREAM_SHA256
            and sha256_bytes(new_bs) == NEW_BITSTREAM_SHA256
            and byte_diff
            == [(4459, 48, 49), (4460, 49, 48), (4461, 48, 49)]
        ),
        "observer_identity": (
            manifest.get("observer_sha256") == sha256_bytes(observer_payload)
            and manifest.get("observer_binding_four_way", {})
            .get("source", {})
            .get("sha256")
            == manifest.get("observer_sha256")
        ),
        "compile_runtime_binding": (
            "+incdir+$package_root/tb_probe" in prepare
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in prepare
            and len(
                re.findall(
                    r"\+RETURN_OBS_FINAL_RELEASE(?:\s|$)", prepare
                )
            )
            == 2
            and prepare.count("+RETURN_OBS_FINAL_RELEASE_LIMIT=256") == 2
        ),
        "minimal_server_runtime": (
            "git rev-parse" not in prepare
            and "README_HARDWARE_SIM_ENTRY" not in prepare
        ),
        "return_contract": (
            '"RETURN_MANIFEST.json"' in collector
            and '"evidence/returned_package_manifest.json"' in collector
            and '{"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}' in runtime
        ),
        "runner_controls": (
            runner.get("valid") is True
            and runner.get("exit_control", {}).get("runner_exit_code") == 74
            and runner.get("term_control", {}).get("runner_exit_code") == 143
        ),
        "focused_hdl_gate": (
            scope.get("valid") is True
            and scope.get("zip", {}).get("sha256") == ZIP_SHA256
            and scope.get("focused_compatible_frontend", {})
            .get("positive", {})
            .get("exit_code")
            == 0
            and scope.get("all_negative_controls_fail_closed") is True
        ),
    }


def mutate(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    path: str,
    old: str,
    new: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    changed = dict(entries)
    text = changed[path].decode("utf-8")
    if old not in text:
        raise RuntimeError(f"negative anchor absent: {path}:{old}")
    changed[path] = text.replace(old, new, 1).encode("utf-8")
    changed_manifest = copy.deepcopy(manifest)
    changed_manifest["files"][path] = sha256_bytes(changed[path])
    return changed, changed_manifest


def negatives(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    runner: dict[str, Any],
    scope: dict[str, Any],
    local: dict[str, Any],
) -> dict[str, Any]:
    cases: dict[str, tuple[dict[str, bytes], dict[str, Any]]] = {}
    wrong_leaf = copy.deepcopy(manifest)
    wrong_leaf["configuration_fix"]["leaf_changes"][0]["new"] = 2
    cases["wrong_config_leaf_receipt"] = (dict(entries), wrong_leaf)
    reverted = dict(entries)
    reverted[BITSTREAM_REL] = source[BITSTREAM_REL]
    reverted_manifest = copy.deepcopy(manifest)
    reverted_manifest["files"][BITSTREAM_REL] = sha256_bytes(
        reverted[BITSTREAM_REL]
    )
    cases["revert_bitstream"] = (reverted, reverted_manifest)
    cases["delete_compile_incdir"] = mutate(
        entries,
        manifest,
        "PREPARE_AND_RUN.sh",
        "+incdir+$package_root/tb_probe",
        "+incdir+deleted",
    )
    cases["delete_enable_macro"] = mutate(
        entries,
        manifest,
        "PREPARE_AND_RUN.sh",
        "+define+NATIVE_RETURN_OBSERVER_ENABLE",
        "+define+DELETED_NATIVE_RETURN_OBSERVER_ENABLE",
    )
    cases["delete_runtime_feature"] = mutate(
        entries,
        manifest,
        "PREPARE_AND_RUN.sh",
        "+RETURN_OBS_FINAL_RELEASE",
        "+DELETED_RETURN_OBS_FINAL_RELEASE",
    )
    wrong_observer = copy.deepcopy(manifest)
    wrong_observer["observer_sha256"] = "0" * 64
    cases["wrong_observer_identity"] = (dict(entries), wrong_observer)
    cases["delete_return_manifest_writer"] = mutate(
        entries,
        manifest,
        "package_tools/node0004_hang_localization_runtime_v7.py",
        '"RETURN_MANIFEST.json"',
        '"DELETED_RETURN_MANIFEST.json"',
    )
    result: dict[str, Any] = {}
    for name, (changed, changed_manifest) in cases.items():
        failed = [
            key
            for key, passed in semantic_checks(
                changed, changed_manifest, source, runner, scope, local
            ).items()
            if not passed
        ]
        result[name] = {
            "expected_exit": 1,
            "observed_exit": 1 if failed else 0,
            "failed_closed": bool(failed),
            "failed_checks": failed,
        }
    result["all_failed_closed"] = all(
        row["failed_closed"]
        for name, row in result.items()
        if name != "all_failed_closed"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-v25", type=Path, required=True)
    parser.add_argument("--runner-controls", type=Path, required=True)
    parser.add_argument("--observer-scope", type=Path, required=True)
    parser.add_argument("--local-rebuild", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    zip_path = args.zip.resolve()
    source_path = args.source_v25.resolve()
    sidecar_path = args.sidecar.resolve()
    errors: list[str] = []

    observed_sha = base.sha256_file(zip_path)
    if observed_sha != ZIP_SHA256:
        errors.append("final ZIP SHA differs")
    sidecar_valid = (
        sidecar_path.read_text(encoding="ascii").strip()
        == f"{observed_sha}  {zip_path.name}"
    )
    if not sidecar_valid:
        errors.append("sidecar differs")
    if base.sha256_file(source_path) != SOURCE_SHA256:
        errors.append("source v25 SHA differs")

    entries, zip_errors, zip_meta = base.read_zip(zip_path, INSTALL_NAME)
    source, source_errors, source_meta = base.read_zip(
        source_path, SOURCE_NAME
    )
    errors.extend(zip_errors)
    errors.extend(source_errors)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner_path = args.runner_controls.resolve()
    scope_path = args.observer_scope.resolve()
    local_path = args.local_rebuild.resolve()
    runner = json.loads(runner_path.read_text(encoding="utf-8"))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))
    local = json.loads(local_path.read_text(encoding="utf-8"))

    receipts: dict[str, Any] = {}
    for relative, expected in CURRENT_RECEIPTS.items():
        observed = base.sha256_file(project / relative)
        match = observed == expected
        receipts[relative] = {
            "expected": expected,
            "observed": observed,
            "current_match": match,
        }
        if not match:
            errors.append(f"current receipt drift: {relative}")

    semantic = semantic_checks(
        entries, manifest, source, runner, scope, local
    )
    errors.extend(
        f"semantic check failed: {name}"
        for name, passed in semantic.items()
        if not passed
    )
    negative = negatives(
        entries, manifest, source, runner, scope, local
    )
    if not negative["all_failed_closed"]:
        errors.append("one or more negatives did not fail closed")
    passed = not errors
    report = {
        "schema": "node0004-v26-final-zip-current-rule-self-audit-v1",
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
            "crc_path_root_duplicate_symlink_valid": not zip_errors,
            "meta": zip_meta,
        },
        "sidecar": {
            "path": str(sidecar_path),
            "bytes": sidecar_path.stat().st_size,
            "sha256": base.sha256_file(sidecar_path),
            "valid": sidecar_valid,
        },
        "source_v25": {
            "path": str(source_path),
            "bytes": source_path.stat().st_size,
            "sha256": base.sha256_file(source_path),
            "meta": source_meta,
        },
        "current_receipts": receipts,
        "semantic_checks": semantic,
        "runtime_preservation": runtime_preservation(entries, source),
        "runner_controls": {
            "path": str(runner_path),
            "sha256": base.sha256_file(runner_path),
            "validator_exit": 0 if runner.get("valid") else 1,
            "safe_compile_runner_exit": runner.get(
                "exit_control", {}
            ).get("runner_exit_code"),
            "safe_term_runner_exit": runner.get(
                "term_control", {}
            ).get("runner_exit_code"),
        },
        "focused_hdl_gate": {
            "path": str(scope_path),
            "sha256": base.sha256_file(scope_path),
            "validator_exit": 0 if scope.get("valid") else 1,
            "frontend_exit": scope.get(
                "focused_compatible_frontend", {}
            ).get("positive", {}).get("exit_code"),
        },
        "local_rebuild": {
            "path": str(local_path),
            "sha256": base.sha256_file(local_path),
            "status": local.get("status"),
        },
        "negative_controls": negative,
        "all_required_negative_controls_fail_closed": negative[
            "all_failed_closed"
        ],
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": True,
        "functional_rtl_modified": False,
        "server_action": False,
        "claim_boundary": (
            "exact v26 package, single transout threshold config delta, "
            "focused package-local observer HDL and runner/return contracts; "
            "server VCS and E3/E4/E5 remain open"
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
