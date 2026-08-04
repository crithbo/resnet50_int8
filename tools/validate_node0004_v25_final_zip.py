from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True

INSTALL_NAME = "r5_n4_hw_v25_terminal_match_diag"
SOURCE_NAME = "r5_n4_hw_v24_final_release_diag_compilefix"
ZIP_SHA256 = "e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab"
SOURCE_SHA256 = "3701226c52de41a6982dd0ac9a111ade26c26ed088eee53d62fcc038cd5980fc"
RETURN_SHA256 = "e403d08c5ea0b6dd252f72d4378e78b8f15c68165153d304dde7c1834fde0999"
CURRENT_RECEIPTS = {
    ".agents/agent.md": "aae402d48b82d026c5512c8a6a5d4c9ff9db4bcc6a94576cd618c168f3fd188e",
    ".agents/rules/生成前必读索引.md": "d9e66e5a1dc4ba1658aac7f851227bb162b76601cd497eeea558a88a2e900422",
    ".agents/rules/服务器测试包生成规则.md": "559ce2660cfe34d567ab45f6c2573f7d0ad2ad3f3d751337432616ce9a9690b2",
    ".agents/rules/INT8_SA点积专项规则.md": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
}
BITSTREAM_REL = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
BITSTREAM_SHA256 = "6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(
    path: Path, root: str
) -> tuple[dict[str, bytes], list[str], dict[str, Any]]:
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
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                errors.append(f"unsafe/duplicate/symlink member: {info.filename}")
                continue
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            if pure.parts[0] != root or len(pure.parts) < 2:
                errors.append(f"unexpected root: {info.filename}")
                continue
            entries[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(
                info
            )
    if roots != {root}:
        errors.append(f"root set differs: {sorted(roots)}")
    return entries, errors, {
        "roots": sorted(roots),
        "entry_count": len(entries),
    }


def normalized_workload_equal(
    entries: dict[str, bytes], source: dict[str, bytes]
) -> bool:
    paths = {p for p in entries if p.startswith("workload/runtime/")}
    source_paths = {p for p in source if p.startswith("workload/runtime/")}
    if paths != source_paths:
        return False
    for path in paths:
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


def checks(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    runner: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, bool]:
    files = manifest.get("files", {})
    observer_payload = entries.get(
        "tb_probe/native_return_observer.svh", b""
    )
    observer = observer_payload.decode("utf-8", errors="replace")
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    collector = entries.get(
        "package_tools/node0004_hang_localization_runtime_v7.py", b""
    ).decode("utf-8", errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    v24 = manifest.get("v24_return_analysis", {})
    scope_negatives = scope.get("negative_controls", {})
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
            == "resnet50-node0004-terminal-match-diagnostic-package-v25"
            and manifest.get("classification")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
        ),
        "frozen_semantics": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt_in_this_successor") is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
            and normalized_workload_equal(entries, source)
            and sha256_bytes(entries.get(BITSTREAM_REL, b""))
            == BITSTREAM_SHA256
        ),
        "source_and_return_bound": (
            manifest.get("superseded_v24_package", {}).get("sha256")
            == SOURCE_SHA256
            and v24.get("return_zip_sha256") == RETURN_SHA256
            and v24.get("compile_exit_status") == 0
            and v24.get("run_exit_status") == 0
            and v24.get("natural_terminal") is False
            and v24.get("formal_d_present") == 0
            and v24.get("formal_d_missing") == 320
        ),
        "observer_identity": (
            manifest.get("observer_sha256") == sha256_bytes(observer_payload)
            and manifest.get("observer_binding_four_way", {})
            .get("source", {})
            .get("sha256")
            == manifest.get("observer_sha256")
        ),
        "terminal_match_diagnostic_present": all(
            token in observer
            for token in (
                "TERMINAL_MATCH_EDGE_V1",
                "TERMINAL_MATCH_BOUNDARY_V1",
                "return_obs_tm_qualified_terminal_accepts",
                "sa_pe_inport_last_bit_unmasked",
                "sa_pe_all_inport_matched",
                "sa_pe_transout_last_index_diff",
                "sa_pe_transout_last_matched",
                "sa_pe_transout_last_out",
            )
        ),
        "compile_and_runtime_binding": (
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
        "runner_positive_and_finalizer": (
            runner.get("valid") is True
            and runner.get("exit_control", {}).get("runner_exit_code") == 74
            and runner.get("term_control", {}).get("runner_exit_code") == 143
            and runner.get("exit_control", {})
            .get("checks", {})
            .get("return_manifest_contract")
            is True
            and runner.get("term_control", {})
            .get("checks", {})
            .get("return_manifest_contract")
            is True
        ),
        "focused_hdl_positive": (
            scope.get("valid") is True
            and scope.get("zip", {}).get("sha256") == ZIP_SHA256
            and scope.get("focused_compatible_frontend", {})
            .get("positive", {})
            .get("exit_code")
            == 0
            and scope.get("all_negative_controls_fail_closed") is True
            and scope.get("safe_compile_stub_used_as_hdl_evidence") is False
        ),
        "focused_hdl_required_negatives": all(
            scope_negatives.get(name, {}).get("failed_closed") is True
            for name in (
                "delete_counter_declaration",
                "typo_counter_use",
                "delete_qualified_update",
            )
        ),
    }


def mutate_text(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    path: str,
    old: str,
    new: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    changed = dict(entries)
    text = changed[path].decode("utf-8")
    if text.count(old) < 1:
        raise RuntimeError(f"negative anchor absent: {path}:{old}")
    changed[path] = text.replace(old, new, 1).encode("utf-8")
    changed_manifest = copy.deepcopy(manifest)
    changed_manifest["files"][path] = sha256_bytes(changed[path])
    if path == "tb_probe/native_return_observer.svh":
        digest = sha256_bytes(changed[path])
        changed_manifest["observer_sha256"] = digest
        changed_manifest["observer_binding_four_way"]["source"][
            "sha256"
        ] = digest
    return changed, changed_manifest


def package_negatives(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    runner: dict[str, Any],
    scope: dict[str, Any],
) -> dict[str, Any]:
    cases = {
        "delete_compile_incdir": mutate_text(
            entries,
            manifest,
            "PREPARE_AND_RUN.sh",
            "+incdir+$package_root/tb_probe",
            "+incdir+deleted",
        ),
        "delete_enable_macro": mutate_text(
            entries,
            manifest,
            "PREPARE_AND_RUN.sh",
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            "+define+DELETED_NATIVE_RETURN_OBSERVER_ENABLE",
        ),
        "delete_runtime_feature": mutate_text(
            entries,
            manifest,
            "PREPARE_AND_RUN.sh",
            "+RETURN_OBS_FINAL_RELEASE",
            "+DELETED_RETURN_OBS_FINAL_RELEASE",
        ),
        "delete_return_manifest_writer": mutate_text(
            entries,
            manifest,
            "package_tools/node0004_hang_localization_runtime_v7.py",
            '"RETURN_MANIFEST.json"',
            '"DELETED_RETURN_MANIFEST.json"',
        ),
    }
    wrong_identity = copy.deepcopy(manifest)
    wrong_identity["observer_sha256"] = "0" * 64
    cases["wrong_observer_identity"] = (dict(entries), wrong_identity)
    result: dict[str, Any] = {}
    for name, (changed, changed_manifest) in cases.items():
        failed = [
            key
            for key, passed in checks(
                changed, changed_manifest, source, runner, scope
            ).items()
            if not passed
        ]
        result[name] = {
            "expected_exit_code": 1,
            "observed_exit_code": 1 if failed else 0,
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
    parser.add_argument("--source-v24", type=Path, required=True)
    parser.add_argument("--runner-controls", type=Path, required=True)
    parser.add_argument("--observer-scope", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project = args.project_root.resolve()
    zip_path = args.zip.resolve()
    source_path = args.source_v24.resolve()
    sidecar_path = args.sidecar.resolve()
    runner_path = args.runner_controls.resolve()
    scope_path = args.observer_scope.resolve()
    errors: list[str] = []

    observed_sha = sha256_file(zip_path)
    if observed_sha != ZIP_SHA256:
        errors.append("final ZIP SHA differs")
    sidecar_valid = (
        sidecar_path.read_text(encoding="ascii").strip()
        == f"{observed_sha}  {zip_path.name}"
    )
    if not sidecar_valid:
        errors.append("sidecar differs")
    if sha256_file(source_path) != SOURCE_SHA256:
        errors.append("source v24 SHA differs")

    entries, zip_errors, zip_meta = read_zip(zip_path, INSTALL_NAME)
    source, source_errors, source_meta = read_zip(source_path, SOURCE_NAME)
    errors.extend(zip_errors)
    errors.extend(source_errors)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner = json.loads(runner_path.read_text(encoding="utf-8"))
    scope = json.loads(scope_path.read_text(encoding="utf-8"))

    current_receipts: dict[str, Any] = {}
    for relative, expected in CURRENT_RECEIPTS.items():
        observed = sha256_file(project / relative)
        match = observed == expected
        current_receipts[relative] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "current_match": match,
        }
        if not match:
            errors.append(f"current receipt drift: {relative}")

    semantic = checks(entries, manifest, source, runner, scope)
    errors.extend(
        f"semantic check failed: {name}"
        for name, passed in semantic.items()
        if not passed
    )
    negatives = package_negatives(
        entries, manifest, source, runner, scope
    )
    if not negatives["all_failed_closed"]:
        errors.append("one or more package negatives did not fail closed")
    passed = not errors
    report = {
        "schema": "node0004-v25-final-zip-current-rule-self-audit-v1",
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
            "sha256": sha256_file(sidecar_path),
            "valid": sidecar_valid,
        },
        "source_v24": {
            "path": str(source_path),
            "bytes": source_path.stat().st_size,
            "sha256": sha256_file(source_path),
            "meta": source_meta,
        },
        "current_rule_receipts": current_receipts,
        "rule_drift": {
            "generation_server_rule_sha256": manifest.get(
                "active_receipts", {}
            ).get("server_package_rule_sha256"),
            "current_server_rule_sha256": CURRENT_RECEIPTS[
                ".agents/rules/服务器测试包生成规则.md"
            ],
            "adjudication": "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS",
            "package_bytes_changed": False,
            "reason": (
                "current rule narrows the HDL closure to changed or required "
                "diagnostic leaves; the exact v25 ZIP passes that focused gate"
            ),
        },
        "semantic_checks": semantic,
        "runner_controls": {
            "path": str(runner_path),
            "bytes": runner_path.stat().st_size,
            "sha256": sha256_file(runner_path),
            "validator_exit_code": 0 if runner.get("valid") else 1,
            "safe_compile_stub_runner_exit": runner.get(
                "exit_control", {}
            ).get("runner_exit_code"),
            "safe_term_finalizer_runner_exit": runner.get(
                "term_control", {}
            ).get("runner_exit_code"),
            "claim_boundary": "runner reachability and finalizer only",
        },
        "package_local_hdl_gate": {
            "path": str(scope_path),
            "bytes": scope_path.stat().st_size,
            "sha256": sha256_file(scope_path),
            "validator_exit_code": 0 if scope.get("valid") else 1,
            "frontend_exit_code": scope.get(
                "focused_compatible_frontend", {}
            ).get("positive", {}).get("exit_code"),
            "scope": "v25 new terminal-match declarations, updates, uses, and required XMR leaves",
            "full_observer_inventory_required": False,
            "full_design_elaboration_claimed": False,
        },
        "negative_controls": negatives,
        "all_required_negative_controls_fail_closed": negatives[
            "all_failed_closed"
        ],
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "claim_boundary": (
            "exact package structure, current-rule focused package-local HDL, "
            "runner reachability/finalizers and diagnostic binding only; "
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
