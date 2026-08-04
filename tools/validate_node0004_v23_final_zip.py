from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True

INSTALL_NAME = "r5_n4_hw_v23_final_release_diag"
SOURCE_NAME = "r5_n4_hw_v22_featurebind"
ZIP_SHA256 = "9ec61dda9d1d1729b1896b94e86c92747fbec4b2077a7d779a75d186329e2a27"
SOURCE_SHA256 = "caf96850ceb5dcf66233dd736757bb2e0b3fbb3b63b066dc9c0194022f1ac68b"
INDEX_SHA256 = "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8"
SERVER_RULE_SHA256 = "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
INT8_SA_SHA256 = "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
README_SHA256 = "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
CORRECTION_TASK_SHA256 = "0eaa10c0e7f97daf3c0765fdea83489733f9061a2749b548654bd65b3a781cb2"
CORRECTION_REPORT_SHA256 = "2369d9eb4976b67d54a34b5eacfb1e24877b3a2a7000d29967ab082a3d960b8c"
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

REQUIRED_RULE_IDS = {
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001",
    "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
    "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
    "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
    "CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001",
    "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
    "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
    "CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001",
    "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
    "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
    "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
    "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
    "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
    "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
    "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
    "CDA-SERVER-WORKLOAD-PROVENANCE-001",
    "CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001",
}

FEATURES = {
    "RETURN_OBS_DEEP": {
        "enable": "+RETURN_OBS_DEEP",
        "limits": ["+RETURN_OBS_DEEP_LIMIT=256"],
        "marker": "feature=RETURN_OBS_DEEP enabled=%0d",
        "schema": "DEEP_COUNTS",
    },
    "RETURN_OBS_ABPE": {
        "enable": "+RETURN_OBS_ABPE",
        "limits": ["+RETURN_HANG_DIAG_MAX_CYCLES=8388608"],
        "marker": "feature=RETURN_OBS_ABPE enabled=%0d",
        "schema": "ABPE_BOUNDARY_V1",
    },
    "RETURN_HANG_DIAG": {
        "enable": "+RETURN_HANG_DIAG",
        "limits": [
            "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
            "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
            "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        ],
        "marker": "feature=RETURN_HANG_DIAG enabled=%0d",
        "schema": "CANONICAL_DIAG_DECISION_V1",
    },
    "RETURN_OBS_FINAL_RELEASE": {
        "enable": "+RETURN_OBS_FINAL_RELEASE",
        "limits": ["+RETURN_OBS_FINAL_RELEASE_LIMIT=256"],
        "marker": "feature=RETURN_OBS_FINAL_RELEASE enabled=%0d",
        "schema": "FINAL_RELEASE_BOUNDARY_V1",
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


def read_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], list[str]]:
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
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                errors.append(f"unsafe or duplicate member: {info.filename}")
                continue
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            if pure.parts[0] != expected_root or len(pure.parts) < 2:
                errors.append(f"unexpected ZIP root: {info.filename}")
                continue
            entries[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
    if roots != {expected_root}:
        errors.append(f"ZIP root set differs: {sorted(roots)}")
    return entries, errors


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
    controls: dict[str, Any],
) -> dict[str, bool]:
    files = manifest.get("files", {})
    receipts = manifest.get("active_receipts", {})
    read_receipts = {
        item.get("path"): item.get("sha256")
        for item in receipts.get("generation_read_receipt", [])
        if isinstance(item, dict)
    }
    rules = set(receipts.get("rules", []))
    reanalysis = manifest.get("return_reanalysis", {})
    correction = reanalysis.get("invalidation_receipt", {})
    binding = manifest.get("diagnostic_feature_runtime_binding", {})
    declared = {
        item.get("feature"): item
        for item in binding.get("features", [])
        if isinstance(item, dict)
    }
    runner = entries.get("PREPARE_AND_RUN.sh", b"").decode(
        "utf-8", errors="replace"
    )
    observer = entries.get("tb_probe/native_return_observer.svh", b"").decode(
        "utf-8", errors="replace"
    )
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode("utf-8", errors="replace")
    collector = entries.get(
        "package_tools/node0004_hang_localization_runtime_v7.py", b""
    ).decode("utf-8", errors="replace")
    observer_guard = entries.get(
        "package_tools/node0004_package_observer_guard.py", b""
    ).decode("utf-8", errors="replace")

    feature_closure: list[bool] = []
    for name, expected in FEATURES.items():
        item = declared.get(name, {})
        feature_closure.append(
            item.get("runtime_enable_parameter") == expected["enable"]
            and item.get("limit_or_budget_parameters") == expected["limits"]
            and item.get("expected_record_schema") == expected["schema"]
            and expected["enable"] in runner
            and all(limit in runner for limit in expected["limits"])
            and expected["marker"] in observer
            and f'"feature": "{name}"' in runtime
        )

    required_observer_tokens = (
        "input_last_index",
        "sa_pe_inport_last_matched",
        "sa_pe_inport_last_out",
        "alu_result_last_bit",
        "sa_pe_alu_result_last_matched",
        "alu2ob_wr_handshake",
        "ob_out_rd_ready",
        "initial_port_pingpong_buffer_select",
        "ob2alu_pingpong_buffer_select",
        "alu2ob_pingpong_buffer_select",
        "ob_outport_pingpong_buffer_select",
        "initial_port_wr_ptr",
        "ob2alu_rd_ptr",
        "alu2ob_wr_ptr",
        "ob_out_rd_ptr",
        "sa_pe_outbuffer_port_valid_bit",
        "FINAL_RELEASE_EDGE_V1",
        "FINAL_RELEASE_BOUNDARY_V1",
        "return_obs_abpe_group_out_accept_count",
        "return_obs_buf45_wr_edge_count[1]",
    )
    minimal_runtime_forbidden = (
        "git rev-parse",
        "README_HARDWARE_SIM_ENTRY",
        "NDP_Top_phy_filelist.f",
        "expected_server_rtl_sha",
    )
    return {
        "manifest_exact_set_and_hashes": (
            set(files) == set(entries) - {"package_manifest.json"}
            and all(
                path in entries and sha256_bytes(entries[path]) == digest
                for path, digest in files.items()
            )
        ),
        "identity_and_diagnostic_only_class": (
            manifest.get("schema")
            == "resnet50-node0004-final-release-diagnostic-package-v23"
            and manifest.get("install_name") == INSTALL_NAME
            and manifest.get("classification")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
            and manifest.get("status") == "PACKAGE_READY_NOT_RUN"
        ),
        "frozen_semantics_and_no_server_action": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt_in_this_successor") is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
        ),
        "source_v22_identity_bound": (
            reanalysis.get("bound_source_package", {}).get("sha256")
            == SOURCE_SHA256
            and manifest.get("superseded_v22_package", {}).get("sha256")
            == SOURCE_SHA256
        ),
        "workload_byte_semantics_preserved": normalized_workload_equal(
            entries, source
        ),
        "bitstream_preserved": (
            sha256_bytes(entries.get(BITSTREAM_REL, b"")) == BITSTREAM_SHA256
        ),
        "correction_receipt_and_invalidation": (
            correction.get("task_record_sha256") == CORRECTION_TASK_SHA256
            and correction.get("machine_report_sha256")
            == CORRECTION_REPORT_SHA256
            and correction.get("invalidated_blocker")
            == "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            and correction.get("invalidated_status") == "WAIT_RTL_FIX"
            and reanalysis.get("last_proven_good")
            == "SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE"
            and reanalysis.get("first_divergence")
            == "SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID"
            and reanalysis.get("rtl_defect_classification") == "NOT_YET_PROVEN"
        ),
        "current_rule_receipts_embedded": (
            receipts.get("server_package_rule_sha256") == SERVER_RULE_SHA256
            and all(read_receipts.get(path) == digest for path, digest in RULE_RECEIPTS.items())
            and REQUIRED_RULE_IDS.issubset(rules)
        ),
        "four_feature_end_to_end_binding": (
            set(declared) == set(FEATURES) and all(feature_closure)
            and "diagnostic_feature_binding.json" in runtime
            and '"evidence/diagnostic_feature_binding.json"' in collector
        ),
        "observer_final_release_leaf_coverage": all(
            token in observer for token in required_observer_tokens
        ),
        "observer_identity_single_source_match": (
            manifest.get("observer_sha256")
            == sha256_bytes(
                entries.get("tb_probe/native_return_observer.svh", b"")
            )
            and manifest.get("observer_binding_four_way", {})
            .get("source", {})
            .get("sha256")
            == manifest.get("observer_sha256")
        ),
        "observer_qualified_not_level_progress": (
            "return_obs_fr_pe_accepts++" in observer
            and "return_obs_fr_alu_terminal_writes++" in observer
            and "count_state" in observer
            and "corroborating_state_only" in json.dumps(manifest)
        ),
        "runner_four_way_binding": (
            "+incdir+$package_root/tb_probe" in runner
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner
            and "node0004_package_observer_guard.py" in runner
            and "+RETURN_OBS_FINAL_RELEASE" in runner
            and "+RETURN_OBS_FINAL_RELEASE_LIMIT=256" in runner
        ),
        "minimal_runtime_preflight_and_manifest_truth": (
            all(token not in runner for token in minimal_runtime_forbidden)
            and '--manifest "$package_root/package_manifest.json"' in runner
            and "manifest[\"observer_binding_four_way\"][\"source\"][\"sha256\"]"
            in observer_guard
            and "package_manifest.json" in runtime
        ),
        "signal_safe_and_result_fail_closed": (
            "trap 'on_signal HUP 129' HUP" in runner
            and "trap 'on_signal INT 130' INT" in runner
            and "trap 'on_signal TERM 143' TERM" in runner
            and "SERVER_RESULT_GATE.json" in runtime
            and "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS" in runtime
        ),
        "runner_control_report_valid": (
            controls.get("valid") is True
            and controls.get("checks", {}).get("zip_identity") is True
            and controls.get("exit_control", {}).get("runner_exit_code") == 74
            and controls.get("term_control", {}).get("runner_exit_code") == 143
            and all(
                controls.get("canonical_negative_controls", {}).get(name) is True
                for name in (
                    "summary_only_append",
                    "conflicting_double_decision",
                    "missing_reason",
                    "missing_boundary",
                    "level_only_pseudo_progress",
                )
            )
        ),
    }


def evaluate(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    controls: dict[str, Any],
) -> tuple[bool, list[str], dict[str, bool]]:
    checks = semantic_checks(entries, manifest, source, controls)
    errors = [
        f"semantic check failed: {name}"
        for name, passed in checks.items()
        if not passed
    ]
    return not errors, errors, checks


def updated_manifest(
    manifest: dict[str, Any], path: str, payload: bytes | None
) -> dict[str, Any]:
    changed = copy.deepcopy(manifest)
    if payload is None:
        changed["files"].pop(path, None)
    else:
        changed["files"][path] = sha256_bytes(payload)
    return changed


def negative_controls(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    source: dict[str, bytes],
    controls: dict[str, Any],
) -> dict[str, Any]:
    cases: dict[str, tuple[dict[str, bytes], dict[str, Any]]] = {}

    no_source = dict(entries)
    no_source.pop("tb_probe/native_return_observer.svh")
    cases["delete_observer_source"] = (
        no_source,
        updated_manifest(manifest, "tb_probe/native_return_observer.svh", None),
    )

    replacements = {
        "delete_compile_incdir": (
            "PREPARE_AND_RUN.sh",
            "+incdir+$package_root/tb_probe",
            "+incdir+deleted",
        ),
        "delete_enable_macro": (
            "PREPARE_AND_RUN.sh",
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            "+define+DELETED_OBSERVER_ENABLE",
        ),
        "delete_final_release_runtime_enable": (
            "PREPARE_AND_RUN.sh",
            "+RETURN_OBS_FINAL_RELEASE",
            "+DELETED_OBS_FINAL_RELEASE",
        ),
        "delete_final_release_limit": (
            "PREPARE_AND_RUN.sh",
            "+RETURN_OBS_FINAL_RELEASE_LIMIT=256",
            "+RETURN_OBS_FINAL_RELEASE_LIMIT=0",
        ),
        "delete_time0_marker_contract": (
            "tb_probe/native_return_observer.svh",
            FEATURES["RETURN_OBS_FINAL_RELEASE"]["marker"],
            "feature=DELETED_FINAL_RELEASE enabled=%0d",
        ),
        "delete_feature_return_target": (
            "package_tools/node0004_hang_localization_runtime_v7.py",
            '"evidence/diagnostic_feature_binding.json"',
            '"evidence/deleted_feature_binding.json"',
        ),
        "wrong_observer_identity": (
            "package_manifest.json",
            "not-used",
            "not-used",
        ),
    }
    for name, (path, old, new) in replacements.items():
        changed_entries = dict(entries)
        changed_manifest = copy.deepcopy(manifest)
        if name == "wrong_observer_identity":
            changed_manifest["observer_sha256"] = "0" * 64
        else:
            text = changed_entries[path].decode("utf-8")
            if old not in text:
                raise RuntimeError(f"negative control anchor missing: {name}")
            changed_entries[path] = text.replace(old, new).encode("utf-8")
            changed_manifest = updated_manifest(
                changed_manifest, path, changed_entries[path]
            )
            if path == "tb_probe/native_return_observer.svh":
                changed_observer_sha = sha256_bytes(changed_entries[path])
                changed_manifest["observer_sha256"] = changed_observer_sha
                changed_manifest["observer_binding_four_way"]["source"][
                    "sha256"
                ] = changed_observer_sha
        cases[name] = changed_entries, changed_manifest

    result: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest) in cases.items():
        valid, errors, _ = evaluate(
            changed_entries, changed_manifest, source, controls
        )
        result[name] = {
            "command": (
                "python tools/validate_node0004_v23_final_zip.py "
                f"--internal-negative {name}"
            ),
            "expected_exit_code": 1,
            "observed_exit_code": 0 if valid else 1,
            "failed_closed": not valid,
            "errors": errors,
        }
    result["all_failed_closed"] = all(
        item.get("failed_closed") is True
        for name, item in result.items()
        if name != "all_failed_closed"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-v22", type=Path, required=True)
    parser.add_argument("--runner-controls", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    project = args.project_root.resolve()
    zip_path = args.zip.resolve()
    sidecar_path = args.sidecar.resolve()
    source_path = args.source_v22.resolve()
    controls_path = args.runner_controls.resolve()
    errors: list[str] = []

    observed_sha = sha256_file(zip_path)
    if observed_sha != ZIP_SHA256:
        errors.append("ZIP SHA mismatch")
    sidecar_text = sidecar_path.read_text(encoding="ascii").strip()
    sidecar_valid = sidecar_text == f"{observed_sha}  {zip_path.name}"
    if not sidecar_valid:
        errors.append("sidecar mismatch")
    source_sha = sha256_file(source_path)
    if source_sha != SOURCE_SHA256:
        errors.append("source v22 SHA mismatch")

    entries, zip_errors = read_zip(zip_path, INSTALL_NAME)
    source, source_errors = read_zip(source_path, SOURCE_NAME)
    errors.extend(zip_errors)
    errors.extend(source_errors)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    controls = json.loads(controls_path.read_text(encoding="utf-8"))

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
        entries, manifest, source, controls
    )
    errors.extend(semantic_errors)
    negatives = negative_controls(entries, manifest, source, controls)
    if not negatives["all_failed_closed"]:
        errors.append("one or more negative controls did not fail closed")
    passed = valid and not errors and negatives["all_failed_closed"]

    report = {
        "schema": "node0004-v23-final-zip-current-rule-self-audit-v1",
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
            "bytes": sidecar_path.stat().st_size,
            "sha256": sha256_file(sidecar_path),
            "valid": sidecar_valid,
            "server_return_upload_required": False,
        },
        "source_v22": {
            "path": str(source_path),
            "bytes": source_path.stat().st_size,
            "sha256": source_sha,
            "crc_path_root_valid": not source_errors,
        },
        "rule_receipts": rule_receipts,
        "required_rule_ids": sorted(REQUIRED_RULE_IDS),
        "semantic_checks": checks,
        "runner_feature_controls": {
            "path": str(controls_path),
            "bytes": controls_path.stat().st_size,
            "sha256": sha256_file(controls_path),
            "validator_exit_code": 0 if controls.get("valid") else 1,
            "safe_compile_stub_exit": controls.get("exit_control", {}).get(
                "runner_exit_code"
            ),
            "safe_term_runner_exit": controls.get("term_control", {}).get(
                "runner_exit_code"
            ),
        },
        "negative_controls": negatives,
        "all_required_negative_controls_fail_closed": negatives[
            "all_failed_closed"
        ],
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "claim_boundary": (
            "local package, runner and observer delivery validation only; "
            "no VCS, DUT simulation, natural terminal, formal D, E3, E4 or E5"
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
