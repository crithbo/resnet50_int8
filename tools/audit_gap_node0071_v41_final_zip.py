#!/usr/bin/env python3
"""Independent final-ZIP release audit for GAP node0071 v41."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/operator_config_validation/r5-gap-node0071-v41-branch-isolated-config-fix"
NAME = "r5_n71_gap_v41_branch_isolated_config_fix"
SOURCE_NAME = "r5_n71_gap_v40_lc_supply_conservation_diag"
TARGET = OUT / f"{NAME}.zip"
SIDECAR = OUT / f"{NAME}.zip.sha256"
SOURCE = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
REPORT = OUT / "final_zip_rule_self_audit.json"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "gap_mac": ROOT / ".agents/rules/GAP_int32_mac_bypass_rules.md",
    "gap_probe": ROOT / ".agents/rules/GAP_probe_v7_validator_rules.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}
SUPPORT = {
    "runner": OUT / "runner_chain.json",
    "signal": OUT / "signal_stub.json",
    "hdl": OUT / "hdl_scope.json",
    "config": OUT / "configs/manifest.json",
    "mapping": OUT / "mapping_report.json",
}
EXPECTED = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "2697fec8192f5008a0b5f288a4c38c36e9f493ff85db264479e4c5a88b03b706",
    "server": "5540e9c724e9c313e9a874a8251ad291328d4df80f01382ca091520893e757a1",
    "config": "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "gap_mac": "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    "gap_probe": "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    "tail": "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
}
CLOUD = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def archive_payloads(path: Path) -> tuple[zipfile.ZipFile, dict[str, bytes]]:
    archive = zipfile.ZipFile(path)
    return archive, {
        info.filename: archive.read(info)
        for info in archive.infolist()
        if not info.is_dir()
    }


def config_contract(candidate: dict, source: dict) -> bool:
    frozen = ("CONFIG", "buffer_config", "general_array", "lc_pe_configs", "stream_engine")
    if any(candidate.get(key) != source.get(key) for key in frozen):
        return False
    loops = candidate["dram_loop_configs"]
    for group in candidate["buffer_loop_configs"].values():
        row = group["ROW_LC"]["src_id"].split(".")[-1]
        if row not in loops:
            return False
        outer = loops[row]["src_id"]
        if not outer or outer.split(".")[-1] not in loops:
            return False
    return True


def main() -> int:
    errors: list[str] = []
    target_sha = digest(TARGET)
    sidecar_ok = target_sha in SIDECAR.read_text(encoding="utf-8") and TARGET.name in SIDECAR.read_text(encoding="utf-8")
    if not sidecar_ok:
        errors.append("sidecar")

    rule_receipts = {}
    for key, path in RULES.items():
        actual = digest(path)
        ok = actual == EXPECTED[key]
        rule_receipts[key] = {"sha256": actual, "current_match": ok}
        if not ok:
            errors.append(f"rule:{key}")

    target_zip, target_files = archive_payloads(TARGET)
    source_zip, source_files = archive_payloads(SOURCE)
    infos = target_zip.infolist()
    names = [info.filename for info in infos]
    roots = {PurePosixPath(name).parts[0] for name in names if name}
    zip_checks = {
        "crc": target_zip.testzip() is None,
        "single_root": roots == {NAME},
        "path_safe": all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name for name in names
        ),
        "duplicates_absent": len(names) == len(set(names)),
        "symlinks_absent": all(
            ((info.external_attr >> 16) & 0o170000) != 0o120000 for info in infos
        ),
        "stale_partial_provenance_absent": not any(
            "/provenance/v41_branch_isolation/" in name for name in names
        ),
    }
    for key, ok in zip_checks.items():
        if not ok:
            errors.append(f"zip:{key}")

    manifest_member = f"{NAME}/TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(target_files[manifest_member])
    relative_files = {
        name.split("/", 1)[1]: data for name, data in target_files.items()
        if name != manifest_member
    }
    manifest_files = manifest.get("files", {})
    exact_set = set(relative_files) == set(manifest_files)
    per_file = exact_set and all(
        len(relative_files[name]) == rec["size_bytes"]
        and digest_bytes(relative_files[name]) == rec["sha256"]
        for name, rec in manifest_files.items()
    )
    identity = {
        "package": manifest.get("package_name") == NAME,
        "install": manifest.get("install_name") == NAME,
        "run": manifest.get("run_name") == f"run_{NAME}",
        "return": manifest.get("return_name") == f"{NAME}_return",
        "claim": manifest.get("package_class") == "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "candidate_release_false": manifest.get("candidate_release") is False,
        "cloud_authority": manifest.get("active_rtl_identity", {}).get("commit") == CLOUD,
        "actual_compile_return_required": manifest.get("active_rtl_identity", {}).get(
            "actual_compiled_commit_must_be_returned"
        ) is True,
    }
    if not exact_set:
        errors.append("manifest:exact_set")
    if not per_file:
        errors.append("manifest:per_file")
    for key, ok in identity.items():
        if not ok:
            errors.append(f"identity:{key}")

    frozen_relatives = sorted(
        rel for rel in (
            name.split("/", 1)[1] for name in source_files
            if name != f"{SOURCE_NAME}/TEST_PACKAGE_MANIFEST.json"
        )
        if rel.startswith("workload/input/") or rel.startswith("workload/golden/")
    )
    frozen_equal = (
        len(frozen_relatives) == 64
        and all(
            source_files[f"{SOURCE_NAME}/{rel}"] == target_files[f"{NAME}/{rel}"]
            for rel in frozen_relatives
        )
    )
    observer_equal = (
        source_files[f"{SOURCE_NAME}/tb_probe/native_return_observer.svh"]
        == target_files[f"{NAME}/tb_probe/native_return_observer.svh"]
    )
    if not frozen_equal:
        errors.append("frozen_numeric")
    if not observer_equal:
        errors.append("observer_changed")

    config_report = read_json(SUPPORT["config"])
    mapping_report = read_json(SUPPORT["mapping"])
    stage_checks = []
    for record in config_report.get("records", []):
        candidate = read_json(ROOT / record["candidate"])
        source = read_json(ROOT / record["source"])
        roots_disjoint = not set(record["buffer_roots"]) & set(record["memory_roots"])
        embedded = json.loads(target_files[f"{NAME}/p/v41/configs/{record['stage']}/config.json"])
        ok = (
            record["strict_validator_error_count"] == 0
            and roots_disjoint
            and config_contract(candidate, source)
            and embedded == candidate
        )
        stage_checks.append({"stage": record["stage"], "pass": ok})
    config_pass = (
        config_report.get("status") == "CONFIG_ONLY_CORRECTNESS_BASELINE"
        and config_report.get("stage_count") == 8
        and len(stage_checks) == 8
        and all(item["pass"] for item in stage_checks)
    )
    mapping_pass = (
        mapping_report.get("status") == "PASS"
        and len(mapping_report.get("records", [])) == 8
        and all(
            item.get("exact") is True
            and item.get("fallback_used") is False
            and item.get("penalty") == 0
            and item.get("double_build_products_equal") is True
            and digest_bytes(target_files[
                f"{NAME}/workload/install/cfg_pkg/gap_node0071_{item['stage']}_128b.bin"
            ]) == item["products"]["modules_dump_128b.bin"]
            for item in mapping_report.get("records", [])
        )
    )
    if not config_pass:
        errors.append("config")
    if not mapping_pass:
        errors.append("mapping")

    microtrace = json.loads(target_files[f"{NAME}/p/v41/boundary_microtrace.json"])
    ledger = json.loads(target_files[f"{NAME}/p/v41/changed_causal_transaction_ledger.json"])
    materialized_config = (
        microtrace.get("pass") is True
        and ledger.get("status") == "PASS"
        and manifest.get("config_correction_contract", {}).get("memory_roots_changed") is False
        and manifest.get("config_correction_contract", {}).get("addresses_changed") is False
    )
    if not materialized_config:
        errors.append("materialized_config")

    reports = {key: read_json(path) for key, path in SUPPORT.items() if key in ("runner", "signal", "hdl")}
    support_pass = {
        "runner": reports["runner"].get("valid") is True
        and reports["runner"].get("all_negative_controls_fail_closed") is True,
        "signal": reports["signal"].get("status") == "PASS"
        and all(reports["signal"].get("checks", {}).values()),
        "hdl": reports["hdl"].get("pass") is True and reports["hdl"].get("errors") == [],
    }
    for key, ok in support_pass.items():
        if not ok:
            errors.append(f"support:{key}")

    # Changed-config fail-closed controls exercise the same contract checker.
    first = config_report["records"][0]
    base_candidate = read_json(ROOT / first["candidate"])
    base_source = read_json(ROOT / first["source"])
    shared = copy.deepcopy(base_candidate)
    shared["buffer_loop_configs"]["GROUP0"]["ROW_LC"]["src_id"] = "DRAM_LC.LC1"
    missing = copy.deepcopy(base_candidate)
    del missing["dram_loop_configs"]["LC9"]
    address = copy.deepcopy(base_candidate)
    address["stream_engine"]["stream0"]["base_addr"] = "0x10"
    negative_controls = {
        "shared_root_rejected": (
            shared["buffer_loop_configs"]["GROUP0"]["ROW_LC"]["src_id"]
            in set(first["memory_roots"])
        ),
        "missing_clone_rejected": not config_contract(missing, base_source),
        "changed_address_rejected": not config_contract(address, base_source),
        "missing_mapping_receipt_rejected": not (
            len(mapping_report.get("records", [])) - 1 == 8
        ),
        "stale_provenance_rejected": zip_checks["stale_partial_provenance_absent"],
    }
    negatives_pass = all(negative_controls.values())
    if not negatives_pass:
        errors.append("negative_controls")

    release_gate_matrix = {
        "package_bootstrap_path_runtime_D": {
            "applicability": "applicable", "pass": exact_set and per_file and all(identity.values())
        },
        "runner_compile_finalizer": {
            "applicability": "applicable", "pass": support_pass["runner"] and support_pass["signal"]
        },
        "package_local_hdl": {
            "applicability": "receipt_reuse_exact_observer", "pass": observer_equal and support_pass["hdl"]
        },
        "materialized_config": {
            "applicability": "applicable_changed_causal_slice", "pass": config_pass and mapping_pass and materialized_config
        },
        "diagnostic_semantics": {
            "applicability": "receipt_reuse_exact_observer_canonical", "pass": observer_equal
        },
        "return_result_conjunction": {
            "applicability": "applicable", "pass": support_pass["runner"] and support_pass["signal"]
        },
        "frozen_numeric_golden": {
            "applicability": "record_only_byte_equality", "pass": frozen_equal
        },
    }
    blocking = [key for key, value in release_gate_matrix.items() if value["pass"] is not True]
    if blocking:
        errors.append("release_gate:" + ",".join(blocking))

    receipts = {
        key: {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for key, path in SUPPORT.items()
    }
    output = {
        "schema": "gap-node0071-v41-final-zip-rule-self-audit-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "package_release": "PACKAGE_READY_NOT_RUN" if not errors else "NONE",
        "target_zip": str(TARGET.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": TARGET.stat().st_size,
        "target_zip_sha256": target_sha,
        "sidecar_valid": sidecar_ok,
        "source_zip_sha256": digest(SOURCE),
        "rule_receipts": rule_receipts,
        "zip_checks": zip_checks,
        "manifest_exact_set": exact_set,
        "manifest_per_file_receipts": per_file,
        "identity": identity,
        "frozen_numeric_and_golden_count": len(frozen_relatives),
        "frozen_numeric_and_golden_byte_equal": frozen_equal,
        "observer_byte_equal": observer_equal,
        "config_stage_checks": stage_checks,
        "config_pass": config_pass,
        "mapping_pass": mapping_pass,
        "materialized_config_pass": materialized_config,
        "negative_controls": negative_controls,
        "all_negative_controls_fail_closed": negatives_pass,
        "supporting_reports": receipts,
        "supporting_pass": support_pass,
        "release_gate_matrix": release_gate_matrix,
        "blocking_failures": blocking,
        "errors": errors,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "run_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": f"{NAME}_return.zip",
        "claim_boundary": (
            "CONFIG_ONLY_CORRECTNESS_BASELINE / E2_LOCAL_ONLY. The exact observer "
            "and frozen 64 numeric/golden files are reused. Natural terminal, 48 "
            "formal D targets, actual compiled commit, E3, E4 and E5 require return."
        ),
    }
    REPORT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "report": str(REPORT.relative_to(ROOT)).replace("\\", "/"),
        "sha256": digest(REPORT),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
    }, ensure_ascii=False))
    target_zip.close()
    source_zip.close()
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
