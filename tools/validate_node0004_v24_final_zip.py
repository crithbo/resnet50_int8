from __future__ import annotations

import argparse
import copy
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True
INSTALL_NAME = "r5_n4_hw_v24_final_release_diag_compilefix"
SOURCE_NAME = "r5_n4_hw_v23_final_release_diag"
ZIP_SHA256 = "3701226c52de41a6982dd0ac9a111ade26c26ed088eee53d62fcc038cd5980fc"
SOURCE_SHA256 = "9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27"
RETURN_SHA256 = "e8efef64b095f5d6cc2b5e4d734b6d1a94a14741d3b608dfc008ef6894905842"
INDEX_SHA256 = "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8"
SERVER_RULE_SHA256 = "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
INT8_SA_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
BITSTREAM_REL = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
BITSTREAM_SHA256 = "6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b"
RULE_RECEIPTS = {
    ".agents/rules/生成前必读索引.md": INDEX_SHA256,
    ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
    ".agents/rules/INT8_SA点积专项规则.md": INT8_SA_SHA256,
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
}
EDGE_COUNTER = "return_obs_fr_buffer5_write_edges"
BAD_IDENTIFIER = "return_obs_buf45_wr_edge_count"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(
    path: Path, root: str
) -> tuple[dict[str, bytes], list[str], dict[str, Any]]:
    entries: dict[str, bytes] = {}
    errors: list[str] = []
    roots: set[str] = set()
    seen: set[str] = set()
    symlinks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failed: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                errors.append(f"unsafe or duplicate ZIP member: {info.filename}")
                continue
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(info.filename)
                errors.append(f"symlink ZIP member: {info.filename}")
                continue
            if info.is_dir():
                continue
            if pure.parts[0] != root or len(pure.parts) < 2:
                errors.append(f"unexpected ZIP root: {info.filename}")
                continue
            entries[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(
                info
            )
    if roots != {root}:
        errors.append(f"ZIP root set differs: {sorted(roots)}")
    return entries, errors, {
        "roots": sorted(roots),
        "entry_count": len(entries),
        "symlinks": symlinks,
    }


def normalized_workload_equal(
    entries: dict[str, bytes], source: dict[str, bytes]
) -> bool:
    current_paths = {p for p in entries if p.startswith("workload/runtime/")}
    source_paths = {p for p in source if p.startswith("workload/runtime/")}
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
    runner: dict[str, Any],
    observer_scope: dict[str, Any],
    escape: dict[str, Any],
) -> dict[str, bool]:
    files = manifest.get("files", {})
    receipts = manifest.get("active_receipts", {})
    read_receipts = {
        item.get("path"): item.get("sha256")
        for item in receipts.get("generation_read_receipt", [])
        if isinstance(item, dict)
    }
    observer_payload = entries.get(
        "tb_probe/native_return_observer.svh", b""
    )
    observer = observer_payload.decode("utf-8", errors="replace")
    runner_text = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    collector = entries.get(
        "package_tools/node0004_hang_localization_runtime_v7.py", b""
    ).decode("utf-8", errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    return {
        "manifest_exact_set_hashes": (
            set(files) == set(entries) - {"package_manifest.json"}
            and all(
                path in entries and sha256_bytes(entries[path]) == digest
                for path, digest in files.items()
            )
        ),
        "fresh_identity_and_diagnostic_only": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema")
            == (
                "resnet50-node0004-final-release-diagnostic-compilefix-"
                "package-v24"
            )
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
        ),
        "source_v23_and_return_bound": (
            manifest.get("superseded_v23_package", {}).get("sha256")
            == SOURCE_SHA256
            and manifest.get("v23_return_analysis", {}).get(
                "return_zip_sha256"
            )
            == RETURN_SHA256
            and manifest.get("v23_return_analysis", {}).get(
                "simulation_started"
            )
            is False
        ),
        "workload_content_preserved": normalized_workload_equal(entries, source),
        "bitstream_preserved": (
            sha256_bytes(entries.get(BITSTREAM_REL, b"")) == BITSTREAM_SHA256
        ),
        "observer_identity_matches": (
            manifest.get("observer_sha256") == sha256_bytes(observer_payload)
            and manifest.get("observer_binding_four_way", {})
            .get("source", {})
            .get("sha256")
            == manifest.get("observer_sha256")
        ),
        "observer_compile_fix_present": (
            BAD_IDENTIFIER not in observer
            and observer.count(f"longint unsigned {EDGE_COUNTER};") == 1
            and observer.count(f"{EDGE_COUNTER} = 0;") == 1
            and observer.count(f"{EDGE_COUNTER}++;") == 1
            and observer.count(f"{EDGE_COUNTER},") == 1
            and "!return_obs_fr_prev_buffer5_write" in observer
        ),
        "return_manifest_writer_and_validator": (
            '"RETURN_MANIFEST.json"' in collector
            and '"evidence/returned_package_manifest.json"' in collector
            and '"node0004-return-manifest-v24"' in collector
            and '{"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}' in runtime
            and "return manifest allowlist receipt differs" in runtime
            and "returned package manifest receipt differs" in runtime
        ),
        "runner_observer_binding_and_minimal_runtime": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner_text
            and "+incdir+$package_root/tb_probe" in runner_text
            and "+RETURN_OBS_FINAL_RELEASE" in runner_text
            and "+RETURN_OBS_FINAL_RELEASE_LIMIT=256" in runner_text
            and "git rev-parse" not in runner_text
            and "README_HARDWARE_SIM_ENTRY" not in runner_text
        ),
        "current_rule_receipts": (
            receipts.get("server_package_rule_sha256") == SERVER_RULE_SHA256
            and all(
                read_receipts.get(path) == digest
                for path, digest in RULE_RECEIPTS.items()
            )
        ),
        "runner_controls_valid": (
            runner.get("valid") is True
            and runner.get("checks", {}).get("zip_identity") is True
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
        "observer_syntax_scope_gate_valid": (
            observer_scope.get("valid") is True
            and observer_scope.get("zip", {}).get("sha256") == ZIP_SHA256
            and observer_scope.get("focused_compatible_frontend", {})
            .get("positive", {})
            .get("exit_code")
            == 0
            and observer_scope.get("all_negative_controls_fail_closed") is True
            and observer_scope.get("safe_compile_stub_used_as_hdl_evidence")
            is False
        ),
        "audit_escape_claim_corrected": (
            escape.get("status")
            == "VALIDATOR_NONCOMPLIANCE_WITH_STRICT_LOCAL_AUDIT_INTENT"
            and escape.get("v23_claim_correction", {}).get("v23_disposition")
            == "QUARANTINED_PACKAGE_LOCAL_OBSERVER_COMPILE_FAILURE"
            and escape.get("rule_read_audit", {}).get("not_a_rule_read_omission")
            is True
        ),
    }


def evaluate(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    runner: dict[str, Any],
    observer_scope: dict[str, Any],
    escape: dict[str, Any],
) -> tuple[bool, list[str], dict[str, bool]]:
    checks = semantic_checks(
        entries, manifest, source, runner, observer_scope, escape
    )
    errors = [
        f"semantic check failed: {name}"
        for name, passed in checks.items()
        if not passed
    ]
    return not errors, errors, checks


def update_file(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    path: str,
    old: str,
    new: str,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    changed_entries = dict(entries)
    text = changed_entries[path].decode("utf-8")
    if old not in text:
        raise RuntimeError(f"negative anchor missing: {path}:{old}")
    changed_entries[path] = text.replace(old, new).encode("utf-8")
    changed_manifest = copy.deepcopy(manifest)
    changed_manifest["files"][path] = sha256_bytes(changed_entries[path])
    if path == "tb_probe/native_return_observer.svh":
        digest = sha256_bytes(changed_entries[path])
        changed_manifest["observer_sha256"] = digest
        changed_manifest["observer_binding_four_way"]["source"][
            "sha256"
        ] = digest
    return changed_entries, changed_manifest


def negatives(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    runner: dict[str, Any],
    observer_scope: dict[str, Any],
    escape: dict[str, Any],
) -> dict[str, Any]:
    cases = {
        "delete_edge_counter_declaration": update_file(
            entries,
            manifest,
            "tb_probe/native_return_observer.svh",
            f"    longint unsigned {EDGE_COUNTER};\n",
            "",
        ),
        "delete_compile_incdir": update_file(
            entries,
            manifest,
            "PREPARE_AND_RUN.sh",
            "+incdir+$package_root/tb_probe",
            "+incdir+deleted",
        ),
        "delete_enable_macro": update_file(
            entries,
            manifest,
            "PREPARE_AND_RUN.sh",
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            "+define+DELETED_OBSERVER_ENABLE",
        ),
        "delete_return_manifest_writer": update_file(
            entries,
            manifest,
            "package_tools/node0004_hang_localization_runtime_v7.py",
            '"RETURN_MANIFEST.json"',
            '"DELETED_RETURN_MANIFEST.json"',
        ),
        "delete_return_manifest_validator": update_file(
            entries,
            manifest,
            "package_tools/node0004_hang_localization_runtime.py",
            '{"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}',
            '{"RETURN_ALLOWLIST.json"}',
        ),
        "delete_returned_package_manifest": update_file(
            entries,
            manifest,
            "package_tools/node0004_hang_localization_runtime_v7.py",
            '"evidence/returned_package_manifest.json"',
            '"evidence/deleted_package_manifest.json"',
        ),
        "delete_final_release_runtime_enable": update_file(
            entries,
            manifest,
            "PREPARE_AND_RUN.sh",
            "+RETURN_OBS_FINAL_RELEASE",
            "+DELETED_OBS_FINAL_RELEASE",
        ),
    }
    wrong_identity = copy.deepcopy(manifest)
    wrong_identity["observer_sha256"] = "0" * 64
    cases["wrong_observer_identity"] = (dict(entries), wrong_identity)
    result: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest) in cases.items():
        valid, errors, _ = evaluate(
            changed_entries,
            changed_manifest,
            source,
            runner,
            observer_scope,
            escape,
        )
        result[name] = {
            "expected_exit_code": 1,
            "observed_exit_code": 0 if valid else 1,
            "failed_closed": not valid,
            "errors": errors,
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
    parser.add_argument("--source-v23", type=Path, required=True)
    parser.add_argument("--runner-controls", type=Path, required=True)
    parser.add_argument("--observer-scope", type=Path, required=True)
    parser.add_argument("--escape-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project = args.project_root.resolve()
    zip_path = args.zip.resolve()
    sidecar_path = args.sidecar.resolve()
    source_path = args.source_v23.resolve()
    errors: list[str] = []
    zip_sha = sha256_file(zip_path)
    if zip_sha != ZIP_SHA256:
        errors.append("final ZIP SHA mismatch")
    sidecar_text = sidecar_path.read_text(encoding="ascii").strip()
    sidecar_valid = sidecar_text == f"{zip_sha}  {zip_path.name}"
    if not sidecar_valid:
        errors.append("sidecar mismatch")
    if sha256_file(source_path) != SOURCE_SHA256:
        errors.append("source v23 ZIP SHA mismatch")
    entries, zip_errors, zip_meta = read_zip(zip_path, INSTALL_NAME)
    source, source_errors, source_meta = read_zip(source_path, SOURCE_NAME)
    errors.extend(zip_errors)
    errors.extend(source_errors)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    runner_path = args.runner_controls.resolve()
    scope_path = args.observer_scope.resolve()
    escape_path = args.escape_report.resolve()
    runner = json.loads(runner_path.read_text(encoding="utf-8"))
    observer_scope = json.loads(scope_path.read_text(encoding="utf-8"))
    escape = json.loads(escape_path.read_text(encoding="utf-8"))
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
        entries, manifest, source, runner, observer_scope, escape
    )
    errors.extend(semantic_errors)
    negative_controls = negatives(
        entries, manifest, source, runner, observer_scope, escape
    )
    if not negative_controls["all_failed_closed"]:
        errors.append("one or more final ZIP negatives did not fail closed")
    passed = valid and not errors and negative_controls["all_failed_closed"]
    report = {
        "schema": "node0004-v24-final-zip-current-rule-self-audit-v1",
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
            "sha256": zip_sha,
            "crc_path_root_duplicate_symlink_valid": not zip_errors,
            "meta": zip_meta,
        },
        "sidecar": {
            "path": str(sidecar_path),
            "bytes": sidecar_path.stat().st_size,
            "sha256": sha256_file(sidecar_path),
            "valid": sidecar_valid,
        },
        "source_v23": {
            "path": str(source_path),
            "bytes": source_path.stat().st_size,
            "sha256": sha256_file(source_path),
            "meta": source_meta,
        },
        "rule_receipts": rule_receipts,
        "semantic_checks": checks,
        "runner_controls": {
            "path": str(runner_path),
            "sha256": sha256_file(runner_path),
            "exit_code": 0 if runner.get("valid") else 1,
            "safe_compile_stub_exit": runner.get("exit_control", {}).get(
                "runner_exit_code"
            ),
            "safe_term_exit": runner.get("term_control", {}).get(
                "runner_exit_code"
            ),
            "claim_boundary": "runner reachability/finalizer only, not HDL",
        },
        "observer_scope_gate": {
            "path": str(scope_path),
            "sha256": sha256_file(scope_path),
            "exit_code": 0 if observer_scope.get("valid") else 1,
            "focused_frontend_exit": observer_scope.get(
                "focused_compatible_frontend", {}
            )
            .get("positive", {})
            .get("exit_code"),
        },
        "audit_escape_report": {
            "path": str(escape_path),
            "sha256": sha256_file(escape_path),
        },
        "negative_controls": negative_controls,
        "all_required_negative_controls_fail_closed": negative_controls[
            "all_failed_closed"
        ],
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "claim_boundary": (
            "local package syntax/scope subset, runner and return-contract "
            "validation; server VCS remains full observer/RTL elaboration "
            "evidence and E3/E4/E5 remain open"
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
