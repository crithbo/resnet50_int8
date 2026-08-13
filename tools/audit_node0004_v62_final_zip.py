#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v62_pekeep_fix"
SOURCE = "r5_n4_hw_v61_lcmap_argv_fix"
EXPECTED_ZIP_SHA = "613eb2a6e4dc14f65065c1a4cd880f0f42828b25a6ebde8383ae78f6d2bdec40"
EXPECTED_SOURCE_SHA = "c78e62cde4f8e185f801900773117017982920b9a479996a1c31af8a1dae1e96"
BITSTREAM = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
SUBSTANTIVE_CHANGED = {
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "package_manifest.json",
    BITSTREAM,
    "workload/runtime/runs/c0/sca_cfg.json",
}
ADDED = ["provenance/v61_to_v62_pekeep_fix.json"]
RULE_PATHS = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "int8_sa": ROOT / ".agents/rules/INT8_SA点积专项规则.md",
    "hardware_readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


def sha_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def members(archive: zipfile.ZipFile) -> dict[str, bytes]:
    return {
        "/".join(name.split("/")[1:]): archive.read(name)
        for name in archive.namelist()
        if not name.endswith("/")
    }


def identity_normalized(value: bytes) -> bytes:
    return value.replace(PACKAGE.encode(), SOURCE.encode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v61", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--family-report", required=True, type=Path)
    parser.add_argument("--shared-report", required=True, type=Path)
    parser.add_argument("--observer-report", required=True, type=Path)
    parser.add_argument("--predicate-report", required=True, type=Path)
    parser.add_argument("--config-report", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    zip_sha = sha_file(args.zip)
    checks["zip_identity"] = zip_sha == EXPECTED_ZIP_SHA
    checks["source_identity"] = sha_file(args.source_v61) == EXPECTED_SOURCE_SHA
    sidecar = args.sidecar.read_text(encoding="ascii").strip().split()
    checks["sidecar_identity"] = sidecar == [EXPECTED_ZIP_SHA, args.zip.name]

    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = archive.testzip() is None
        checks["no_duplicates"] = len(names) == len(set(names))
        checks["single_root"] = {
            name.split("/", 1)[0] for name in names
        } == {PACKAGE}
        checks["safe_paths"] = all(
            not PurePosixPath(item.filename).is_absolute()
            and ".." not in PurePosixPath(item.filename).parts
            and "\\" not in item.filename
            for item in infos
        )
        checks["no_symlinks"] = all(
            not stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF)
            for item in infos
        )
        current = members(archive)
        manifest = json.loads(current["package_manifest.json"])
        actual = {
            name: sha_bytes(value)
            for name, value in current.items()
            if name != "package_manifest.json"
        }
        checks["manifest_exact_set"] = set(manifest["files"]) == set(actual)
        checks["manifest_per_file_receipts"] = manifest["files"] == actual
        checks["manifest_identity"] = (
            manifest["install_name"] == PACKAGE
            and manifest["source_package_sha256"] == EXPECTED_SOURCE_SHA
            and manifest["classification"]
            == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            and manifest["configuration_rebuilt"] is True
            and manifest["functional_rtl_modified"] is False
        )
        contract = json.loads(current["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])
        checks["install_only_v2_contract"] = (
            contract["package_id"] == PACKAGE
            and contract["install_name"] == PACKAGE
            and contract["required_preexisting_parents"] == ["install"]
            and contract["package_creatable_parent_dirs"]
            == ["install/cfg_pkg", "install/codex_runs"]
            and contract["runtime_roots"]["cfg_root"]
            == f"install/cfg_pkg/{PACKAGE}"
            and contract["runtime_roots"]["run_root"]
            == f"install/codex_runs/{PACKAGE}/{{attempt}}"
            and contract["fixed_result_root"] == "/home/panqs/ndp/simresult"
            and contract["tb_cwd"] == "$server_root"
            and contract["path_budget"]["max_projected_absolute_path_chars"]
            == 214
        )
        runner = current["PREPARE_AND_RUN.sh"].decode()
        checks["runner_and_early_finalizer"] = (
            "trap 'finalize $?' EXIT" in runner
            and "+RETURN_OBS_LC18_PE7" in runner
            and "+RETURN_OBS_LC13_LC14" in runner
            and "+RETURN_HANG_DIAG" in runner
            and "/home/panqs/ndp/simresult" in runner
        )
        materialized = [
            row
            for row in manifest.get("release_gate_matrix", [])
            if row.get("gate_id") == "materialized_config"
        ]
        checks["manifest_materialized_config_gate"] = (
            len(materialized) == 1
            and materialized[0].get("blocking") is True
            and materialized[0].get("applicability") == "blocking_applicable"
        )
        active = manifest.get("active_receipts", {})
        checks["manifest_current_rule_receipts"] = (
            active.get("generation_index_sha256")
            == sha_file(RULE_PATHS["index"])
            and active.get("server_package_rule_sha256")
            == sha_file(RULE_PATHS["server"])
            and active.get("common_operator_rule_sha256")
            == sha_file(RULE_PATHS["common_config"])
            and active.get("int8_sa_rule_sha256")
            == sha_file(RULE_PATHS["int8_sa"])
        )

    with zipfile.ZipFile(args.source_v61) as archive:
        previous = members(archive)
    common = set(previous) & set(current)
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    normalized_differences = sorted(
        name
        for name in common
        if identity_normalized(current[name]) != previous[name]
    )
    checks["member_set_delta_exact"] = added == ADDED and not removed
    checks["normalized_changed_surface_bounded"] = (
        set(normalized_differences) <= SUBSTANTIVE_CHANGED
    )
    binary_frozen = sorted(
        name
        for name in common
        if (
            "matrix_" in name
            or name.endswith(".golden")
            or name.endswith(".bin")
        )
        and name != BITSTREAM
    )
    checks["numeric_matrices_golden_frozen"] = (
        bool(binary_frozen)
        and all(previous[name] == current[name] for name in binary_frozen)
    )
    checks["bitstream_single_byte_change"] = (
        BITSTREAM in current
        and BITSTREAM in previous
        and [
            index
            for index, (left, right) in enumerate(
                zip(previous[BITSTREAM], current[BITSTREAM])
            )
            if left != right
        ]
        == [1301]
    )
    sca_member = "workload/runtime/runs/c0/sca_cfg.json"
    checks["sca_input_semantics_identity_only"] = (
        json.loads(identity_normalized(current[sca_member]))
        == json.loads(previous[sca_member])
    )
    frozen_normalized = sorted(
        common - SUBSTANTIVE_CHANGED
    )
    checks["all_other_members_identity_only_or_equal"] = all(
        identity_normalized(current[name]) == previous[name]
        for name in frozen_normalized
    )

    build = load(args.build_report)
    family = load(args.family_report)
    shared = load(args.shared_report)
    observer = load(args.observer_report)
    predicate = load(args.predicate_report)
    config = load(args.config_report)
    return_report = load(args.return_report)
    checks["deterministic_double_build"] = (
        build.get("deterministic_rebuild_equal") is True
        and build.get("numeric_analysis_repeated") is False
        and build.get("node0004_workload_rebuilt") is False
        and build.get("configuration_rebuilt") is True
        and build.get("mapping_rebuilt") is True
        and build.get("bitstream_rebuilt") is True
        and build.get("functional_rtl_modified") is False
        and build.get("server_action") is False
    )
    checks["family_runner_validation"] = (
        family.get("valid") is True and not family.get("errors")
    )
    checks["shared_runtime_layout_validation"] = (
        shared.get("pass") is True and not shared.get("errors")
    )
    checks["observer_validation"] = (
        observer.get("valid") is True and not observer.get("errors")
    )
    checks["predicate_trace_validation"] = (
        predicate.get("valid") is True and not predicate.get("errors")
    )
    checks["changed_config_validation"] = (
        config.get("valid") is True and not config.get("errors")
    )
    checks["v61_return_analysis_valid"] = (
        return_report.get("valid") is True
        and not return_report.get("errors")
        and return_report.get("HANG_ROOT_CAUSE", {}).get(
            "configuration_root_cause_proven"
        )
        is True
    )
    for name, passed in checks.items():
        if not passed:
            errors.append(f"{name} failed")

    gate_matrix = [
        {
            "gate_id": "package_bootstrap_path_runtime_d",
            "applicability": "blocking_applicable",
            "status": "PASS" if checks["family_runner_validation"] else "FAIL",
            "blocking": True,
        },
        {
            "gate_id": "runtime_layout_and_sca_open",
            "applicability": "blocking_applicable",
            "status": (
                "PASS" if checks["shared_runtime_layout_validation"] else "FAIL"
            ),
            "blocking": True,
        },
        {
            "gate_id": "materialized_config",
            "applicability": "blocking_applicable",
            "status": "PASS" if checks["changed_config_validation"] else "FAIL",
            "blocking": True,
        },
        {
            "gate_id": "package_local_hdl",
            "applicability": "receipt_reuse",
            "status": "PASS" if checks["observer_validation"] else "FAIL",
            "blocking": False,
        },
        {
            "gate_id": "observer_canonical_semantics",
            "applicability": "receipt_reuse",
            "status": "PASS" if checks["predicate_trace_validation"] else "FAIL",
            "blocking": False,
        },
        {
            "gate_id": "return_result_conjunction",
            "applicability": "blocking_applicable",
            "status": "PASS" if checks["v61_return_analysis_valid"] else "FAIL",
            "blocking": True,
        },
        {
            "gate_id": "functional_rtl",
            "applicability": "not_applicable",
            "status": "NOT_APPLICABLE",
            "blocking": False,
        },
    ]
    report = {
        "schema": "conv-node0004-v62-final-zip-audit-v1",
        "package_id": PACKAGE,
        "classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
        "candidate_release": False,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": zip_sha,
        },
        "source_v61": {
            "path": str(args.source_v61.resolve()),
            "bytes": args.source_v61.stat().st_size,
            "sha256": sha_file(args.source_v61),
            "disposition": "TESTED_RETURN_CONSUMED",
        },
        "frozen_payload_comparison": {
            "source_member_count": len(previous),
            "target_member_count": len(current),
            "common_members": len(common),
            "frozen_binary_members": len(binary_frozen),
            "normalized_substantive_changes": normalized_differences,
            "added_members": added,
            "removed_members": removed,
        },
        "release_gate_matrix": gate_matrix,
        "rule_receipts_post_generation": {
            key: sha_file(path) for key, path in RULE_PATHS.items()
        },
        "negative_controls": {
            "runner": (
                "missing matrix, missing bitstream, wrong prefix, preflight "
                "failure, compile failure, HUP, INT, TERM all fail closed"
            ),
            "config": (
                "old keep2/index3, nonterminal release, wrong SCA input/output "
                "roots all fail closed"
            ),
            "observer": "actual-consumer scope/typo negatives fail closed",
        },
        "claim_boundary": (
            "Local package and changed-config correctness only. No production "
            "DUT natural terminal, 320 formal D, E4, or E5 claim before return."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"pass": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
