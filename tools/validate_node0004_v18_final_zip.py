from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v18_a_reuse_diag"
ZIP_SHA256 = "aa12edc55f10e28133e843e3ddeff832831a8d8c71cef47c5bc69e7c48f73fc1"
SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
INDEX_SHA256 = (
    "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
)
INT8_SA_SHA256 = (
    "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
)
COMMON_SHA256 = (
    "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
)
NDP_SHA256 = (
    "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
)
OBSERVER_SHA256 = (
    "db36700079225c70b2811f674791a2fd9d08aa3878f85f7bfd6e8d879c03172b"
)
REQUIRED_RULE_IDS = {
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
    "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
    "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
    "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
    "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
    "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
}
RULE_RECEIPTS = {
    ".agents/rules/生成前必读索引.md": INDEX_SHA256,
    ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
    ".agents/rules/INT8_SA点积专项规则.md": INT8_SA_SHA256,
    ".agents/rules/算子配置规则.md": COMMON_SHA256,
    ".agents/rules/NDP硬件字段语义.md": NDP_SHA256,
}
RTL_TOKEN_RECEIPTS = {
    "NDP_copy01/rtl/Slice/LSU/LSU.sv": (
        "se2buf_mem_wreq_buf_sel",
    ),
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Buffer_Manager_Cluster.sv": (
        "se2buf_mem_wreq_buf_sel",
    ),
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_Inport/"
    "SA_Inport_Connect.sv": (
        "sa_inport_src_sel",
        "sa_inport_group_bp_pre",
    ),
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
    "SA_PE_Control_Block.sv": (
        "alu_pipeline0_valid_bit",
        "sa_pe_alu_pipeline0_enable",
    ),
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
    "SA_PE_Outbuffer.sv": (
        "alu2ob_wr_handshake",
        "sa_pe_ob2alu_port_psum_bit",
    ),
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(zip_path: Path) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    entries: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            errors.append(f"CRC failure: {bad_crc}")
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        roots = {name.split("/", 1)[0] for name in names}
        if roots != {INSTALL_NAME}:
            errors.append(f"single-root mismatch: {sorted(roots)}")
        for name in names:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                errors.append(f"unsafe ZIP member: {name}")
                continue
            if "/" not in name:
                errors.append(f"member outside package root: {name}")
                continue
            relative = name.split("/", 1)[1]
            entries[relative] = archive.read(name)
    return entries, errors


def validate_payload(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    zip_sha256: str,
    project_root: Path,
) -> tuple[bool, list[str], dict[str, bool], dict[str, str]]:
    errors: list[str] = []
    required_files = {
        "package_manifest.json",
        "PREPARE_AND_RUN.sh",
        "README.md",
        "tb_probe/native_return_observer.svh",
        "package_tools/node0004_package_observer_guard.py",
        "package_tools/node0004_hang_localization_runtime.py",
        "package_tools/node0004_hang_localization_runtime_v7.py",
    }
    missing_files = required_files - set(entries)
    if missing_files:
        errors.append(f"missing required files: {sorted(missing_files)}")

    files = manifest.get("files", {})
    observed_payload_files = set(entries) - {"package_manifest.json"}
    if set(files) != observed_payload_files:
        errors.append("manifest files exact-set mismatch")
    for relative, expected in files.items():
        payload = entries.get(relative)
        if payload is None:
            continue
        observed = sha256_bytes(payload)
        if observed != expected:
            errors.append(f"manifest hash mismatch: {relative}")

    runner = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    guard = entries.get(
        "package_tools/node0004_package_observer_guard.py", b""
    ).decode("utf-8", errors="replace")
    receipts = manifest.get("active_receipts", {})
    rules = set(receipts.get("rules", []))
    binding = manifest.get("observer_binding_four_way", {})
    source = binding.get("source", {})
    runtime_binding = binding.get("runtime_return", {})
    positive_body = positive.get("positive_control", {})
    negative_body = positive.get("negative_controls", {})
    actual_argv = positive_body.get("actual_compile_argv") or ""
    xmr_gate = positive_body.get("observer_precompile", {}).get(
        "xmr_static_gate", {}
    )

    checks = {
        "install_identity": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema")
            == "resnet50-node0004-a-reuse-diagnostic-package-v18"
        ),
        "diagnostic_only_classification": (
            manifest.get("classification")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
            and manifest.get("formal_readback_claimed") is False
        ),
        "no_functional_or_workload_rebuild": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt") is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
        ),
        "current_server_rule": (
            receipts.get("server_package_rule_sha256")
            == SERVER_RULE_SHA256
        ),
        "required_rule_ids": REQUIRED_RULE_IDS.issubset(rules),
        "observer_identity": (
            source.get("sha256") == OBSERVER_SHA256
            and manifest.get("observer_sha256") == OBSERVER_SHA256
            and sha256_bytes(
                entries.get("tb_probe/native_return_observer.svh", b"")
            )
            == OBSERVER_SHA256
        ),
        "observer_source_bound": (
            source.get("path") == "tb_probe/native_return_observer.svh"
            and source.get("size_bytes")
            == len(entries.get("tb_probe/native_return_observer.svh", b""))
        ),
        "compile_incdir_bound": (
            "+incdir+$package_root/tb_probe" in runner
            and "+incdir+" in actual_argv
            and "/tb_probe" in actual_argv
        ),
        "compile_macro_bound": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in actual_argv
        ),
        "runtime_binding": all(
            token in runner
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_HANG_DIAG",
                "+RETURN_OBS_ABPE",
                "+RETURN_OBS_FILE=",
                "host_progress.log",
                "return_observer.log",
            )
        ),
        "return_allowlist_binding": all(
            path in runtime_binding.get("return_allowlist_paths", [])
            for path in (
                "runs/c0/simulator_argv.txt",
                "runs/c0/sim.log",
                "runs/c0/return_observer.log",
                "runs/c0/host_progress.log",
            )
        ),
        "manifest_single_identity_source": (
            '--manifest "$package_root/package_manifest.json"' in runner
            and 'parser.add_argument("--manifest"' in guard
            and "observer_binding_four_way" in guard
            and "--expected-sha256" not in guard
            and re.search(r"\b[0-9a-f]{64}\b", runner) is None
        ),
        "runtime_classification_manifest_bound": (
            '["classification"]' in runtime
            and "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            not in runtime
        ),
        "a_reuse_record_unique": (
            observer.count("A_REUSE_BOUNDARY_V1") == 1
            and observer.count(
                'return_obs_write_a_reuse_state("DIAG_DECISION")'
            )
            == 1
            and observer.count(
                "task automatic return_obs_write_a_reuse_state"
            )
            == 1
        ),
        "a_reuse_boundary_tokens": all(
            token in observer
            for token in (
                "se2buf_mem_wreq_buf_sel",
                "sa_inport_src_sel",
                "alu_pipeline0_valid_bit",
                "alu2ob_wr_handshake",
                "return_obs_ar_mem_clear_count",
                "return_obs_ar_array_clear_count",
                "return_obs_ar_buf_read_accept",
                "return_obs_ar_sa_src_accept",
            )
        ),
        "qualified_counts_separate_from_snapshots": (
            manifest.get("narrow_diagnostic", {}).get("not_functional_fix")
            is True
            and manifest.get("progress_contract", {}).get(
                "buffer_level_samples_count_as_progress"
            )
            is False
        ),
        "positive_control_valid": (
            positive.get("valid") is True
            and positive.get("zip", {}).get("sha256") == zip_sha256
            and positive_body.get("runner_exit_code") == 73
            and positive_body.get("expected_stub_exit_code") == 73
            and positive_body.get("compile_stub_invocation_count") == 1
        ),
        "positive_control_ordered_guards": all(
            positive_body.get("checks", {}).get(name) is True
            for name in (
                "package_preflight_valid",
                "installed_preflight_valid",
                "observer_guard_valid_and_identity_match",
                "actual_compile_argv_is_compile_target",
                "ordered_chain_reached_compile",
                "package_tree_unchanged",
            )
        ),
        "positive_control_runtime_classification": (
            "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            in (positive_body.get("runner_stdout") or "")
        ),
        "positive_control_wrong_identity_fail_closed": (
            negative_body.get("all_failed_closed") is True
            and negative_body.get("wrong_observer_identity_sha", {}).get(
                "compile_stub_invocation_count"
            )
            == 0
        ),
        "xmr_elaboration_constant_guard": (
            xmr_gate.get("status") == "pass"
            and xmr_gate.get("checked_generated_instance_reference_count", 0)
            > 0
            and not xmr_gate.get("runtime_indexed_generated_references")
        ),
    }
    errors.extend(
        f"semantic check failed: {name}"
        for name, passed in checks.items()
        if not passed
    )

    rtl_receipts: dict[str, str] = {}
    for relative, tokens in RTL_TOKEN_RECEIPTS.items():
        path = project_root / relative
        if not path.is_file():
            errors.append(f"active RTL evidence file missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rtl_receipts[relative] = sha256_file(path)
        for token in tokens:
            if token not in text:
                errors.append(
                    f"active RTL evidence token missing: {relative}:{token}"
                )

    return not errors, errors, checks, rtl_receipts


def negative_controls(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    zip_sha256: str,
    project_root: Path,
) -> dict[str, Any]:
    cases: dict[
        str, tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]
    ] = {}

    missing_source = dict(entries)
    missing_source.pop("tb_probe/native_return_observer.svh", None)
    missing_source_manifest = copy.deepcopy(manifest)
    missing_source_manifest.get("files", {}).pop(
        "tb_probe/native_return_observer.svh", None
    )
    cases["four_way_missing_source"] = (
        missing_source,
        missing_source_manifest,
        positive,
    )

    for name, old, new in (
        (
            "four_way_missing_incdir",
            "+incdir+$package_root/tb_probe",
            "+incdir+$package_root/not_tb_probe",
        ),
        (
            "four_way_missing_enable_macro",
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            "+define+OBSERVER_DISABLED_NEGATIVE",
        ),
        (
            "four_way_missing_runtime_binding",
            "+RETURN_OBSERVER",
            "+OBSERVER_DISABLED_NEGATIVE",
        ),
    ):
        changed_entries = dict(entries)
        changed_manifest = copy.deepcopy(manifest)
        changed_runner = entries["PREPARE_AND_RUN.sh"].decode(
            "utf-8"
        ).replace(old, new)
        changed_entries["PREPARE_AND_RUN.sh"] = changed_runner.encode("utf-8")
        changed_manifest["files"]["PREPARE_AND_RUN.sh"] = sha256_bytes(
            changed_entries["PREPARE_AND_RUN.sh"]
        )
        cases[name] = (changed_entries, changed_manifest, positive)

    missing_rule = copy.deepcopy(manifest)
    missing_rule["active_receipts"]["rules"].remove(
        "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001"
    )
    cases["missing_current_rule_id"] = (entries, missing_rule, positive)

    wrong_class = copy.deepcopy(manifest)
    wrong_class["classification"] = (
        "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
    )
    cases["diagnostic_mislabeled_functional_fix"] = (
        entries,
        wrong_class,
        positive,
    )

    bad_positive = copy.deepcopy(positive)
    bad_positive["positive_control"]["compile_stub_invocation_count"] = 0
    cases["compile_stub_not_reached"] = (entries, manifest, bad_positive)

    missing_boundary_entries = dict(entries)
    missing_boundary_manifest = copy.deepcopy(manifest)
    changed_observer = entries[
        "tb_probe/native_return_observer.svh"
    ].replace(b"A_REUSE_BOUNDARY_V1", b"A_REUSE_BOUNDARY_DISABLED", 1)
    missing_boundary_entries[
        "tb_probe/native_return_observer.svh"
    ] = changed_observer
    changed_observer_sha = sha256_bytes(changed_observer)
    missing_boundary_manifest["files"][
        "tb_probe/native_return_observer.svh"
    ] = changed_observer_sha
    missing_boundary_manifest["observer_sha256"] = changed_observer_sha
    missing_boundary_manifest["observer_binding_four_way"]["source"][
        "sha256"
    ] = changed_observer_sha
    cases["missing_unique_a_reuse_boundary"] = (
        missing_boundary_entries,
        missing_boundary_manifest,
        positive,
    )

    results: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest, changed_positive) in cases.items():
        valid, errors, _, _ = validate_payload(
            changed_entries,
            changed_manifest,
            changed_positive,
            zip_sha256,
            project_root,
        )
        results[name] = {
            "command": (
                "python tools/validate_node0004_v18_final_zip.py "
                f"--negative-control {name}"
            ),
            "expected_exit_code": 1,
            "observed_exit_code": 1 if not valid else 0,
            "failed_closed": not valid,
            "errors": errors,
        }
    results["all_failed_closed"] = all(
        value.get("failed_closed") is True
        for key, value in results.items()
        if key != "all_failed_closed"
    )
    return results


def audit(
    project_root: Path,
    zip_path: Path,
    sidecar_path: Path,
    positive_path: Path,
) -> dict[str, Any]:
    entries, zip_errors = read_zip(zip_path)
    errors = list(zip_errors)
    zip_sha256 = sha256_file(zip_path)
    if zip_sha256 != ZIP_SHA256:
        errors.append(f"ZIP SHA mismatch: {zip_sha256}")
    sidecar_text = sidecar_path.read_text(encoding="utf-8").strip()
    expected_sidecar = f"{zip_sha256}  {zip_path.name}"
    if sidecar_text != expected_sidecar:
        errors.append("sidecar content mismatch")
    try:
        manifest = json.loads(entries["package_manifest.json"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid package manifest: {exc}") from exc
    positive = json.loads(positive_path.read_text(encoding="utf-8"))

    receipt_results: dict[str, Any] = {}
    for relative, expected in RULE_RECEIPTS.items():
        path = project_root / relative
        observed = sha256_file(path) if path.is_file() else None
        valid = observed == expected
        receipt_results[relative] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "current_match": valid,
        }
        if not valid:
            errors.append(f"active rule receipt drift: {relative}")

    valid, semantic_errors, checks, rtl_receipts = validate_payload(
        entries, manifest, positive, zip_sha256, project_root
    )
    errors.extend(semantic_errors)
    negatives = negative_controls(
        entries, manifest, positive, zip_sha256, project_root
    )
    if not negatives["all_failed_closed"]:
        errors.append("one or more required negative controls did not fail closed")
    passed = valid and not errors and negatives["all_failed_closed"]
    return {
        "schema": "node0004-v18-final-zip-current-rule-audit-v1",
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
            "sha256": zip_sha256,
            "crc_and_single_root_valid": not zip_errors,
        },
        "sidecar": {
            "path": str(sidecar_path),
            "sha256": sha256_file(sidecar_path),
            "content": sidecar_text,
            "valid": sidecar_text == expected_sidecar,
        },
        "classification": manifest.get("classification"),
        "rule_receipts": receipt_results,
        "required_rule_ids": sorted(REQUIRED_RULE_IDS),
        "semantic_checks": checks,
        "active_rtl_read_only_token_receipts": rtl_receipts,
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
            "diagnostic package local delivery validation only; no server "
            "compile, simulation, formal D, E4, or E5 claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--positive-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--negative-control")
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.positive_control.resolve(),
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
