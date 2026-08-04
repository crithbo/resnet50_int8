from __future__ import annotations

import argparse
import copy
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


INSTALL_NAME = "r5_n4_hw_v21_bufkeep_fix"
ZIP_SHA256 = "bd9fadb9bdd18c1678461ae055fea7e15be5d414957b76de48f761833e345131"
SOURCE_V20_SHA256 = (
    "e67775aed87d2065f51190049a9a7ba05fb98de9ba08a4362901612248f92ead"
)
RETURN_V20_SHA256 = (
    "b8a1ac0a9f7c9d705b21f332b010a3eaa59d131f85fd1eae524a2d2f26b57b55"
)
SERVER_RULE_SHA256 = (
    "88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6"
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
CONFIG_SHA256 = (
    "3f39ac9baccce2d7052420636eda69ae3c0e7d59f53f245f9c02e89e32a4c6d2"
)
BITSTREAM_SHA256 = (
    "6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b"
)
BITSTREAM_REL = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
REQUIRED_RULE_IDS = {
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
    "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
    "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
    "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
    "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
    "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
    "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
    "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
}
RULE_RECEIPTS = {
    ".agents/rules/生成前必读索引.md": INDEX_SHA256,
    ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
    ".agents/rules/INT8_SA点积专项规则.md": INT8_SA_SHA256,
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
}
EXPECTED_LEAVES = {
    "stream_engine.stream0.buf_idx_keep_last_index[0]": (4, 5),
    "stream_engine.stream1.buf_idx_keep_last_index[0]": (4, 5),
    "stream_engine.stream2.buf_idx_keep_last_index[0]": (4, 5),
    "stream_engine.stream3.buf_idx_keep_last_index[0]": (3, 4),
    "stream_engine.stream4.buf_idx_keep_last_index[0]": (4, 5),
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    entries: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failed: {bad}")
        roots: set[str] = set()
        seen: set[str] = set()
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
            if pure.parts[0] != INSTALL_NAME or len(pure.parts) < 2:
                errors.append(f"unexpected ZIP root: {info.filename}")
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            entries[relative] = archive.read(info)
    if roots != {INSTALL_NAME}:
        errors.append(f"ZIP root set mismatch: {sorted(roots)}")
    return entries, errors


def matrix_entries(entries: dict[str, bytes]) -> list[str]:
    return sorted(
        path
        for path in entries
        if path.startswith("workload/runtime/runs/c0/install/op_w0/")
        and "/matrix_" in path
    )


def source_matrix_entries(source_zip: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(source_zip) as archive:
        if archive.testzip() is not None:
            raise ValueError("source v20 ZIP CRC failed")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.is_dir() or not pure.parts:
                continue
            if pure.parts[0] != "r5_n4_hw_v20_buffer_mode_fix":
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if (
                relative.startswith("workload/runtime/runs/c0/install/op_w0/")
                and "/matrix_" in relative
            ):
                result[relative] = archive.read(info)
    return result


def semantic_checks(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    source_zip: Path,
) -> dict[str, bool]:
    files = manifest.get("files", {})
    fix = manifest.get("configuration_fix", {})
    changes = fix.get("leaf_changes", [])
    normalized = {
        item.get("path"): (item.get("old"), item.get("new"))
        for item in changes
        if isinstance(item, dict)
    }
    receipts = manifest.get("active_receipts", {})
    rules = set(receipts.get("rules", []))
    transport = manifest.get("return_transport_policy", {})
    positive_body = positive.get("positive_control", {})
    negative_body = positive.get("negative_controls", {})
    matrices = matrix_entries(entries)
    source_matrices = source_matrix_entries(source_zip)
    runner = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    checks = {
        "manifest_exact_set_and_hashes": (
            set(files) == set(entries) - {"package_manifest.json"}
            and all(
                path in entries and sha256_bytes(entries[path]) == expected
                for path, expected in files.items()
            )
        ),
        "functional_fix_identity": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema")
            == "resnet50-node0004-buffer-ag-keep-config-fix-package-v21"
            and manifest.get("classification")
            == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            and manifest.get("candidate_release") is False
            and manifest.get("formal_readback_claimed") is False
        ),
        "controlled_config_only_rebuild": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt") is True
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
        ),
        "source_and_return_bound": (
            manifest.get("superseded_v20_package", {}).get("sha256")
            == SOURCE_V20_SHA256
            and manifest.get("v20_return_adjudication", {}).get(
                "bound_return_sha256"
            )
            == RETURN_V20_SHA256
        ),
        "exact_five_keep_threshold_leaves": (
            len(changes) == 5 and normalized == EXPECTED_LEAVES
        ),
        "keep_threshold_formula": (
            fix.get("formula")
            == (
                "stream_engine.streamN.buf_idx_keep_last_index[0] = "
                "buffer_loop_configs.GROUPN.COL_LC.last_index"
            )
            and fix.get("fresh_config_sha256") == CONFIG_SHA256
        ),
        "fresh_bitstream_bound": (
            sha256_bytes(entries.get(BITSTREAM_REL, b""))
            == BITSTREAM_SHA256
        ),
        "frozen_matrix_payloads_preserved": (
            len(matrices) == 84
            and set(matrices) == set(source_matrices)
            and all(entries[path] == source_matrices[path] for path in matrices)
        ),
        "current_rule_receipt_and_ids": (
            receipts.get("server_package_rule_sha256") == SERVER_RULE_SHA256
            and REQUIRED_RULE_IDS.issubset(rules)
        ),
        "transport_policy_bound": (
            transport.get("rule_id")
            == "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
            and transport.get("runner_generates_local_sidecar") is True
            and transport.get("user_upload_sidecar_required") is False
            and transport.get("analysis_recomputes_return_zip_sha256") is True
            and transport.get(
                "internal_manifest_allowlist_and_source_binding_unchanged"
            )
            is True
        ),
        "minimal_server_runtime_preflight": (
            "package_manifest.json" in runtime
            and "package_manifest.json" in runner
            and "git rev-parse" not in runner
            and "README_HARDWARE_SIM_ENTRY" not in runner
        ),
        "runner_positive_control": (
            positive.get("valid") is True
            and positive.get("zip", {}).get("sha256") == ZIP_SHA256
            and positive_body.get("runner_exit_code") == 73
            and positive_body.get("compile_stub_invocation_count") == 1
            and positive_body.get("checks", {}).get(
                "ordered_chain_reached_compile"
            )
            is True
            and positive_body.get("checks", {}).get(
                "package_tree_unchanged"
            )
            is True
        ),
        "runner_wrong_identity_negative": (
            negative_body.get("all_failed_closed") is True
            and negative_body.get("wrong_observer_identity_sha", {}).get(
                "compile_stub_invocation_count"
            )
            == 0
        ),
    }
    return checks


def evaluate(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    source_zip: Path,
) -> tuple[bool, list[str], dict[str, bool]]:
    checks = semantic_checks(entries, manifest, positive, source_zip)
    errors = [
        f"semantic check failed: {name}"
        for name, passed in checks.items()
        if not passed
    ]
    return not errors, errors, checks


def negatives(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    source_zip: Path,
) -> dict[str, Any]:
    cases: dict[str, tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]] = {}

    missing_leaf = copy.deepcopy(manifest)
    missing_leaf["configuration_fix"]["leaf_changes"] = missing_leaf[
        "configuration_fix"
    ]["leaf_changes"][:-1]
    cases["missing_one_keep_threshold_leaf"] = (
        entries,
        missing_leaf,
        positive,
    )

    wrong_formula = copy.deepcopy(manifest)
    wrong_formula["configuration_fix"]["formula"] = "row_keep = col_last - 1"
    cases["wrong_keep_release_formula"] = (entries, wrong_formula, positive)

    not_rebuilt = copy.deepcopy(manifest)
    not_rebuilt["configuration_rebuilt"] = False
    cases["configuration_rebuild_not_declared"] = (
        entries,
        not_rebuilt,
        positive,
    )

    missing_rule = copy.deepcopy(manifest)
    missing_rule["active_receipts"]["rules"].remove(
        "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
    )
    cases["missing_current_transport_rule"] = (
        entries,
        missing_rule,
        positive,
    )

    wrong_bitstream = dict(entries)
    wrong_bitstream[BITSTREAM_REL] = b"old-v20-bitstream-negative-control"
    wrong_bitstream_manifest = copy.deepcopy(manifest)
    wrong_bitstream_manifest["files"][BITSTREAM_REL] = sha256_bytes(
        wrong_bitstream[BITSTREAM_REL]
    )
    cases["wrong_bitstream_payload"] = (
        wrong_bitstream,
        wrong_bitstream_manifest,
        positive,
    )

    no_runner_positive = copy.deepcopy(positive)
    no_runner_positive["valid"] = False
    cases["runner_positive_control_missing"] = (
        entries,
        manifest,
        no_runner_positive,
    )

    result: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest, changed_positive) in (
        cases.items()
    ):
        valid, errors, _ = evaluate(
            changed_entries,
            changed_manifest,
            changed_positive,
            source_zip,
        )
        result[name] = {
            "command": (
                "python tools/validate_node0004_v21_final_zip.py "
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


def audit(
    project_root: Path,
    zip_path: Path,
    sidecar_path: Path,
    source_zip: Path,
    positive_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    observed_zip_sha = sha256_file(zip_path)
    if observed_zip_sha != ZIP_SHA256:
        errors.append("ZIP SHA mismatch")
    sidecar_text = sidecar_path.read_text(encoding="ascii").strip()
    expected_sidecar = f"{observed_zip_sha}  {zip_path.name}"
    if sidecar_text != expected_sidecar:
        errors.append("sidecar mismatch")
    if sha256_file(source_zip) != SOURCE_V20_SHA256:
        errors.append("source v20 ZIP SHA mismatch")

    entries, zip_errors = read_zip(zip_path)
    errors.extend(zip_errors)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    positive = json.loads(positive_path.read_text(encoding="utf-8"))

    rule_receipts: dict[str, Any] = {}
    for relative, expected in RULE_RECEIPTS.items():
        path = project_root / relative
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
        entries, manifest, positive, source_zip
    )
    errors.extend(semantic_errors)
    negative_results = negatives(entries, manifest, positive, source_zip)
    if not negative_results["all_failed_closed"]:
        errors.append("negative control did not fail closed")
    passed = valid and not errors and negative_results["all_failed_closed"]
    return {
        "schema": "node0004-v21-final-zip-current-rule-audit-v1",
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
            "sha256": observed_zip_sha,
            "crc_path_root_valid": not zip_errors,
        },
        "sidecar": {
            "path": str(sidecar_path),
            "sha256": sha256_file(sidecar_path),
            "valid": sidecar_text == expected_sidecar,
            "server_return_upload_required": False,
        },
        "source_v20": {
            "path": str(source_zip),
            "sha256": sha256_file(source_zip),
        },
        "rule_receipts": rule_receipts,
        "required_rule_ids": sorted(REQUIRED_RULE_IDS),
        "semantic_checks": checks,
        "runner_positive_control": {
            "path": str(positive_path),
            "sha256": sha256_file(positive_path),
            "validator_exit_code": 0 if positive.get("valid") else 1,
            "safe_compile_stub_expected_exit_code": 73,
            "safe_compile_stub_observed_exit_code": positive.get(
                "positive_control", {}
            ).get("runner_exit_code"),
            "compile_stub_invocation_count": positive.get(
                "positive_control", {}
            ).get("compile_stub_invocation_count"),
            "actual_compile_argv": positive.get(
                "positive_control", {}
            ).get("actual_compile_argv"),
        },
        "negative_controls": negative_results,
        "all_required_negative_controls_fail_closed": negative_results[
            "all_failed_closed"
        ],
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": True,
        "functional_rtl_modified": False,
        "server_action": False,
        "claim_boundary": (
            "local config-functional-fix delivery validation only; no real "
            "VCS, simulation, natural terminal, formal D, E4, or E5 claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-v20", type=Path, required=True)
    parser.add_argument("--positive-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.source_v20.resolve(),
        args.positive_control.resolve(),
    )
    args.output.resolve().write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
