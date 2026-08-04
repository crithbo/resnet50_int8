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

import tools.validate_node0004_v18_final_zip as prior  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v19_buffer0_flow_diag"
ZIP_SHA256 = "0420907934a5a603ea40a127128664affe0182b7d6bc986107e0b0b04303adf3"
OBSERVER_SHA256 = (
    "0e91f541b5ffb5f67a8ec198243dbb5fe7ba7b6a962ba73555eabe5a985ec828"
)
SERVER_RULE_SHA256 = prior.SERVER_RULE_SHA256
REQUIRED_RULE_IDS = prior.REQUIRED_RULE_IDS
RULE_RECEIPTS = prior.RULE_RECEIPTS
SOURCE_TOKEN_RECEIPTS = {
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine.sv": (
        "MSE_INST",
        "mse2buf_wreq_valid",
        "mse2buf_wreq_row_addr",
    ),
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_RD_Stream_Engine/Memory_RD_Stream_Engine.sv": (
        "u_WR_Buffer_AG",
        "buf2mse_wreq_ready",
    ),
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_RD_Stream_Engine/WR_Buffer_AG.sv": (
        "buf_ag_ob_cnt",
        "buf_ag_ob_full",
        "buf_ag_ob_empty",
        "buf_ag_req_pingpong",
    ),
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv": (
        "valid_buf",
        "buf2mrm_req_ready",
        "buf2arm_req_ready",
        "buf2arm_rreq_bank_ready",
    ),
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
    "Array_Request_Manager.sv": (
        "array_counter_0",
        "array_counter_1",
        "array_req_addr",
        "array_life_cnt",
        "arm_addr_update",
        "buf2arm_valid_bit",
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


def validate_payload(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    zip_sha256: str,
    project_root: Path,
) -> tuple[bool, list[str], dict[str, bool], dict[str, str]]:
    errors: list[str] = []
    files = manifest.get("files", {})
    observed_files = set(entries) - {"package_manifest.json"}
    if set(files) != observed_files:
        errors.append("manifest files exact-set mismatch")
    for relative, expected in files.items():
        payload = entries.get(relative)
        if payload is None or sha256_bytes(payload) != expected:
            errors.append(f"manifest payload mismatch: {relative}")

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
    source = manifest.get("observer_binding_four_way", {}).get("source", {})
    positive_body = positive.get("positive_control", {})
    negative_body = positive.get("negative_controls", {})
    actual_argv = positive_body.get("actual_compile_argv") or ""
    xmr_gate = positive_body.get("observer_precompile", {}).get(
        "xmr_static_gate", {}
    )
    flow = manifest.get("buffer0_flow_diagnostic", {})

    checks = {
        "install_identity": (
            manifest.get("install_name") == INSTALL_NAME
            and manifest.get("schema")
            == "resnet50-node0004-buffer0-flow-diagnostic-package-v19"
        ),
        "diagnostic_only": (
            manifest.get("classification")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
            and manifest.get("formal_readback_claimed") is False
        ),
        "no_semantic_rebuild": (
            manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
            and manifest.get("configuration_rebuilt") is False
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("server_action") is False
        ),
        "current_rule": (
            receipts.get("server_package_rule_sha256")
            == SERVER_RULE_SHA256
            and REQUIRED_RULE_IDS.issubset(rules)
        ),
        "observer_identity": (
            source.get("sha256") == OBSERVER_SHA256
            and manifest.get("observer_sha256") == OBSERVER_SHA256
            and sha256_bytes(
                entries.get("tb_probe/native_return_observer.svh", b"")
            )
            == OBSERVER_SHA256
        ),
        "four_way_compile": (
            "+incdir+$package_root/tb_probe" in runner
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner
            and "+incdir+" in actual_argv
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in actual_argv
        ),
        "four_way_runtime_return": all(
            token in runner
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_HANG_DIAG",
                "+RETURN_OBS_ABPE",
                "return_observer.log",
                "host_progress.log",
            )
        ),
        "manifest_single_identity_source": (
            '--manifest "$package_root/package_manifest.json"' in runner
            and "observer_binding_four_way" in guard
            and "--expected-sha256" not in guard
            and re.search(r"\b[0-9a-f]{64}\b", runner) is None
        ),
        "runtime_classification_manifest_bound": (
            '["classification"]' in runtime
            and "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            not in runtime
        ),
        "a_reuse_preserved": (
            observer.count("A_REUSE_BOUNDARY_V1") == 1
            and observer.count(
                'return_obs_write_a_reuse_state("DIAG_DECISION")'
            )
            == 1
        ),
        "flow_record_unique": (
            observer.count("BUFFER0_FLOW_BOUNDARY_V1") == 1
            and observer.count(
                "task automatic return_obs_write_buffer0_flow_state"
            )
            == 1
            and observer.count(
                'return_obs_write_buffer0_flow_state("DIAG_DECISION")'
            )
            == 1
            and flow.get("canonical_record_count") == 1
            and flow.get("not_functional_fix") is True
        ),
        "flow_required_tokens": all(
            token in observer
            for token in (
                "buf_ag_ob_cnt",
                "buf_ag_ob_full",
                "buf_ag_ob_empty",
                "mse2buf_wreq_row_addr",
                "buf2mse_wreq_ready",
                "valid_buf",
                "buf2mrm_req_ready",
                "buf2arm_req_ready",
                "array_counter_0",
                "array_counter_1",
                "array_req_addr",
                "array_life_cnt",
                "return_obs_b0_ag_enqueue_count",
                "return_obs_b0_arm_req_accept_count",
            )
        ),
        "qualified_vs_snapshot_contract": (
            len(flow.get("qualified_counters", [])) == 4
            and len(flow.get("state_only_snapshots", [])) == 3
            and manifest.get("progress_contract", {}).get(
                "buffer_level_samples_count_as_progress"
            )
            is False
        ),
        "positive_control": (
            positive.get("valid") is True
            and positive.get("zip", {}).get("sha256") == zip_sha256
            and positive_body.get("runner_exit_code") == 73
            and positive_body.get("expected_stub_exit_code") == 73
            and positive_body.get("compile_stub_invocation_count") == 1
            and all(
                positive_body.get("checks", {}).get(name) is True
                for name in (
                    "package_preflight_valid",
                    "installed_preflight_valid",
                    "observer_guard_valid_and_identity_match",
                    "ordered_chain_reached_compile",
                    "package_tree_unchanged",
                )
            )
        ),
        "wrong_identity_negative": (
            negative_body.get("all_failed_closed") is True
            and negative_body.get("wrong_observer_identity_sha", {}).get(
                "runner_exit_code"
            )
            == 5
            and negative_body.get("wrong_observer_identity_sha", {}).get(
                "compile_stub_invocation_count"
            )
            == 0
        ),
        "xmr_static_gate": (
            xmr_gate.get("status") == "pass"
            and xmr_gate.get("checked_generated_instance_reference_count", 0)
            > 234
            and xmr_gate.get(
                "runtime_indexed_generated_instance_reference_count"
            )
            == 0
        ),
    }
    errors.extend(
        f"semantic check failed: {name}"
        for name, valid in checks.items()
        if not valid
    )

    source_receipts: dict[str, str] = {}
    for relative, tokens in SOURCE_TOKEN_RECEIPTS.items():
        path = project_root / relative
        if not path.is_file():
            errors.append(f"active source missing: {relative}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        source_receipts[relative] = sha256_file(path)
        for token in tokens:
            if token not in text:
                errors.append(f"active source token missing: {relative}:{token}")
    return not errors, errors, checks, source_receipts


def negatives(
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
    missing_source_manifest["files"].pop(
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
            "+incdir+$package_root/disabled_probe",
        ),
        (
            "four_way_missing_macro",
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
            "+define+OBSERVER_DISABLED_NEGATIVE",
        ),
        (
            "four_way_missing_runtime",
            "+RETURN_OBSERVER",
            "+OBSERVER_DISABLED_NEGATIVE",
        ),
    ):
        changed_entries = dict(entries)
        changed_manifest = copy.deepcopy(manifest)
        changed = entries["PREPARE_AND_RUN.sh"].decode().replace(old, new)
        changed_entries["PREPARE_AND_RUN.sh"] = changed.encode()
        changed_manifest["files"]["PREPARE_AND_RUN.sh"] = sha256_bytes(
            changed_entries["PREPARE_AND_RUN.sh"]
        )
        cases[name] = (changed_entries, changed_manifest, positive)

    changed_entries = dict(entries)
    changed_manifest = copy.deepcopy(manifest)
    changed = entries["tb_probe/native_return_observer.svh"].replace(
        b"BUFFER0_FLOW_BOUNDARY_V1", b"BUFFER0_FLOW_DISABLED_V1", 1
    )
    changed_entries["tb_probe/native_return_observer.svh"] = changed
    changed_sha = sha256_bytes(changed)
    changed_manifest["files"]["tb_probe/native_return_observer.svh"] = (
        changed_sha
    )
    changed_manifest["observer_sha256"] = changed_sha
    changed_manifest["observer_binding_four_way"]["source"]["sha256"] = (
        changed_sha
    )
    cases["missing_flow_record"] = (
        changed_entries,
        changed_manifest,
        positive,
    )

    wrong_class = copy.deepcopy(manifest)
    wrong_class["classification"] = "CONFIG_FUNCTIONAL_FIX"
    cases["diagnostic_mislabeled_fix"] = (entries, wrong_class, positive)

    bad_positive = copy.deepcopy(positive)
    bad_positive["positive_control"]["compile_stub_invocation_count"] = 0
    cases["compile_stub_not_reached"] = (entries, manifest, bad_positive)

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
    prior.INSTALL_NAME = INSTALL_NAME
    entries, zip_errors = prior.read_zip(zip_path)
    errors = list(zip_errors)
    zip_sha256 = sha256_file(zip_path)
    if zip_sha256 != ZIP_SHA256:
        errors.append("ZIP SHA mismatch")
    sidecar_text = sidecar_path.read_text(encoding="ascii").strip()
    expected_sidecar = f"{zip_sha256}  {zip_path.name}"
    if sidecar_text != expected_sidecar:
        errors.append("sidecar mismatch")
    manifest = json.loads(entries["package_manifest.json"])
    positive = json.loads(positive_path.read_text(encoding="utf-8"))

    rule_receipts: dict[str, Any] = {}
    for relative, expected in RULE_RECEIPTS.items():
        path = project_root / relative
        observed = sha256_file(path) if path.is_file() else None
        current = observed == expected
        rule_receipts[relative] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "current_match": current,
        }
        if not current:
            errors.append(f"active rule drift: {relative}")

    valid, semantic_errors, checks, source_receipts = validate_payload(
        entries, manifest, positive, zip_sha256, project_root
    )
    errors.extend(semantic_errors)
    negative_results = negatives(
        entries, manifest, positive, zip_sha256, project_root
    )
    if not negative_results["all_failed_closed"]:
        errors.append("negative control did not fail closed")
    passed = valid and not errors and negative_results["all_failed_closed"]
    return {
        "schema": "node0004-v19-final-zip-current-rule-audit-v1",
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
            "valid": sidecar_text == expected_sidecar,
        },
        "classification": manifest.get("classification"),
        "rule_receipts": rule_receipts,
        "required_rule_ids": sorted(REQUIRED_RULE_IDS),
        "semantic_checks": checks,
        "active_source_read_only_receipts": source_receipts,
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
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "claim_boundary": (
            "diagnostic-only local delivery validation; no server compile, "
            "simulation, natural terminal, formal D, E4, or E5 claim"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--positive-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
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
