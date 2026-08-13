#!/usr/bin/env python3
"""Formal analysis for the p38 early bootstrap partial return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p38_mse4join"
EXECUTION = "r1786436059412189518_1051036"
RETURN = Path(r"C:\Users\15383\Downloads\r5_n4_0cc_p38_mse4join_r1786436059412189518_1051036_return.zip")
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p38_mse4join.zip"
FINAL_AUDIT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p38_mse4join/r5_n4_0cc_p38_mse4join.final_zip_audit.json"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p38_return_analysis/report.json"
RETURN_SHA = "be026648659b6468a6b0121686eb7f55b655b8342c809e05cc767cbde846231c"
SOURCE_SHA = "328b7ec7b7034a1a2c202fad38d628199cfbbaa2213196d94daab39c25ff4d22"
SOURCE_MANIFEST_SHA = "e871d4e2aef2364a696802f90d2e6cbace644133c33d3f6ec5ad2d4e05b647dd"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def receipt(path: Path) -> dict[str, object]:
    try:
        label = path.relative_to(ROOT).as_posix()
    except ValueError:
        label = str(path)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def path_safe(name: str, root: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not path.is_absolute()
        and ".." not in path.parts
        and path.parts[0] == root
    )


def zip_identity(path: Path, expected_root: str) -> tuple[dict[str, object], zipfile.ZipFile]:
    archive = zipfile.ZipFile(path)
    names = archive.namelist()
    roots = sorted({PurePosixPath(name).parts[0] for name in names if name})
    bad_crc = archive.testzip()
    unsafe = [name for name in names if not path_safe(name, expected_root)]
    duplicate = sorted({name for name in names if names.count(name) > 1})
    special = []
    for info in archive.infolist():
        mode = (info.external_attr >> 16) & 0o170000
        if mode not in (0, 0o040000, 0o100000):
            special.append(info.filename)
    return ({
        "bytes": path.stat().st_size,
        "sha256": sha(path),
        "member_count": len(names),
        "roots": roots,
        "crc_bad_member": bad_crc,
        "unsafe_paths": unsafe,
        "duplicate_members": duplicate,
        "special_members": special,
        "single_expected_root": roots == [expected_root],
    }, archive)


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p38 return analysis")
    return_root = f"{PACKAGE}_return"
    source_identity, source_zip = zip_identity(SOURCE, PACKAGE)
    return_identity, return_zip = zip_identity(RETURN, return_root)
    try:
        source_manifest_bytes = source_zip.read(f"{PACKAGE}/package_manifest.json")
        source_manifest = json.loads(source_manifest_bytes)
        source_names = set(source_zip.namelist())
        declared_source = source_manifest["files"]
        source_expected = {f"{PACKAGE}/package_manifest.json"} | {
            f"{PACKAGE}/{name}" for name in declared_source
        }
        source_mismatches: dict[str, object] = {}
        for relative, row in declared_source.items():
            member = f"{PACKAGE}/{relative}"
            if member not in source_names:
                source_mismatches[relative] = "missing"
                continue
            data = source_zip.read(member)
            actual = {"size_bytes": len(data), "sha256": sha_bytes(data)}
            expected = {"size_bytes": row["size_bytes"], "sha256": row["sha256"]}
            if actual != expected:
                source_mismatches[relative] = {"expected": expected, "actual": actual}

        allowlist_member = f"{return_root}/RETURN_ALLOWLIST.json"
        manifest_member = f"{return_root}/RETURN_MANIFEST.json"
        status_member = f"{return_root}/evidence/package_local_preflight_status.json"
        allowlist = json.loads(return_zip.read(allowlist_member))
        return_manifest = json.loads(return_zip.read(manifest_member))
        status = json.loads(return_zip.read(status_member))
        records = allowlist["records"]
        manifest_records = return_manifest["records_excluding_this_manifest"]
        expected_return_names = {allowlist_member, manifest_member} | {
            f"{return_root}/{row['path']}" for row in records
        }
        return_names = set(return_zip.namelist())
        return_mismatches: dict[str, object] = {}
        for row in records:
            member = f"{return_root}/{row['path']}"
            if member not in return_names:
                return_mismatches[row["path"]] = "missing"
                continue
            data = return_zip.read(member)
            actual = {"size_bytes": len(data), "sha256": sha_bytes(data)}
            expected = {"size_bytes": row["size_bytes"], "sha256": row["sha256"]}
            if actual != expected:
                return_mismatches[row["path"]] = {"expected": expected, "actual": actual}

        publication = return_manifest["fixed_result_publication"]
        expected_return_path = f"/home/panqs/ndp/simresult/{PACKAGE}_{EXECUTION}_return.zip"
        checks = {
            "transport_identity_exact": receipt(RETURN)["sha256"] == RETURN_SHA and receipt(RETURN)["bytes"] == 2323,
            "return_crc_single_root_path_safe": return_identity["crc_bad_member"] is None and return_identity["single_expected_root"] and not return_identity["unsafe_paths"] and not return_identity["duplicate_members"] and not return_identity["special_members"],
            "return_exact_set_allowlist": return_names == expected_return_names and not return_mismatches,
            "return_manifest_allowlist_same_records": records == manifest_records,
            "return_partial_identity_exact": allowlist.get("package_identity") == PACKAGE and allowlist.get("partial") is True and return_manifest.get("package_identity") == PACKAGE and return_manifest.get("partial") is True,
            "source_transport_identity_exact": source_identity["sha256"] == SOURCE_SHA and source_identity["bytes"] == 5970142,
            "source_crc_single_root_path_safe": source_identity["crc_bad_member"] is None and source_identity["single_expected_root"] and not source_identity["unsafe_paths"] and not source_identity["duplicate_members"] and not source_identity["special_members"],
            "source_manifest_exact_set_and_per_file": source_names == source_expected and not source_mismatches,
            "source_manifest_binding_exact": sha_bytes(source_manifest_bytes) == SOURCE_MANIFEST_SHA and return_manifest.get("source_package_manifest_sha256") == SOURCE_MANIFEST_SHA,
            "execution_binding_exact": publication.get("return_zip") == expected_return_path and publication.get("return_sidecar") == expected_return_path + ".sha256" and re.fullmatch(r"r\d+_\d+", EXECUTION) is not None,
            "fixed_result_root_and_duplicate_contract": publication.get("result_root") == "/home/panqs/ndp/simresult" and publication.get("duplicate_absent") is True,
            "bootstrap_partial_schema_exact": allowlist.get("schema") == "conv-native-four-lane-install-layout-partial-return-allowlist-v1" and return_manifest.get("schema") == "conv-native-four-lane-install-layout-partial-return-manifest-v1" and status.get("schema") == "conv-native-four-lane-package-local-preflight-status-v1",
            "compile_stage_exit2_exact": return_manifest.get("preflight_stage") == "PRODUCTION_COMPILE" and status.get("preflight_stage") == "PRODUCTION_COMPILE" and status.get("runner_exit_status") == 2 and status.get("signal_status") == "NONE",
            "simulation_not_started_exact": status.get("dut_simulation_started") is False,
            "source_release_audit_frozen_pass": json.loads(FINAL_AUDIT.read_text(encoding="utf-8")).get("valid") is True,
        }
        valid = all(checks.values())
        result = {
            "schema": "conv-native-four-lane-0ccae916-p38-return-analysis-v1",
            "status": "P38_BOOTSTRAP_PARTIAL_VALID_COMPILE_STAGE_EXIT2_EVIDENCE_LOSS_ANALYSIS_ONLY",
            "valid": valid,
            "classification": "PACKAGE_LOCAL_PRODUCTION_COMPILE_STAGE_FAILURE_OR_LAUNCH_ERROR_WITH_ATTEMPT_EVIDENCE_UNAVAILABLE",
            "return_identity": {
                **receipt(RETURN),
                "execution_id": EXECUTION,
                "adjacent_sidecar_present": Path(str(RETURN) + ".sha256").is_file(),
                "zip": return_identity,
            },
            "source_identity": {
                **receipt(SOURCE),
                "package_manifest_sha256": sha_bytes(source_manifest_bytes),
                "zip": source_identity,
            },
            "internal_receipt": {
                "checks": checks,
                "return_errors": [] if return_names == expected_return_names and not return_mismatches else ["return exact-set or per-file mismatch"],
                "source_errors": [] if source_names == source_expected and not source_mismatches else ["source exact-set or per-file mismatch"],
                "return_member_count": len(return_names),
                "source_member_count": len(source_names),
                "publication_state": publication.get("publication_state"),
                "claim_boundary": "Bootstrap partial exact-set only; no attempt-root compile log, core result or plugin payload is present.",
            },
            "execution": {
                "preflight_stage": status["preflight_stage"],
                "runner_exit_status": status["runner_exit_status"],
                "signal_status": status["signal_status"],
                "runtime_layout_created": status["runtime_layout_created"],
                "production_compile_started_claim": status["production_compile_started"],
                "compile_succeeded": False,
                "actual_compile_identity_collected": False,
                "dut_simulation_started": False,
                "c0_slice_finish": False,
                "natural_terminal": False,
                "natural_terminal_27_of_27": False,
                "formal_D_payload_present": False,
            },
            "publication_and_plugins": {
                "bootstrap_partial_published": True,
                "fixed_target_exact": checks["execution_binding_exact"] and checks["fixed_result_root_and_duplicate_contract"],
                "atomic_published_verified_inside_return": False,
                "post_sim_core_invoked": False,
                "required_plugin_payload_present": False,
                "plugin_adjudication": "NOT_REACHED_BECAUSE_DUT_SIMULATION_DID_NOT_START",
            },
            "result_conjunction": {
                "compile": False,
                "simulator_started": False,
                "c0_slice_finish": False,
                "natural_terminal_27_of_27": False,
                "formal_D_320_of_320": False,
                "mismatch_zero_claim": False,
                "E3": False,
                "E4": False,
                "E5": False,
                "performance_claimed": False,
                "passed": False,
            },
            "failure_localization": {
                "LAST_PROVEN_GOOD": "exact p38 source/execution binding and bootstrap finalizer publication; runner records stage PRODUCTION_COMPILE after earlier control-flow stages",
                "FIRST_DIVERGENCE": "before the first persisted production compile receipt: runner exit=2, runtime_layout_created=false, no compile argv/log/status/identity, no simulator invocation",
                "HANG_ROOT_CAUSE": {
                    "status": "PACKAGE_LOCAL_COMPILE_STAGE_EXIT2_WITH_ATTEMPT_EVIDENCE_NOT_AVAILABLE",
                    "dut_or_rtl_root_cause_proven": False,
                    "config_or_numeric_root_cause_proven": False,
                    "remaining_observational_equivalents": [
                        "production make/compile launch returned exit 2 before a persistent receipt was captured",
                        "attempt runtime/evidence root was absent or became unavailable when the EXIT finalizer ran",
                        "bootstrap fallback discarded the underlying compiler stderr/log needed to distinguish the first two cases",
                    ],
                    "frozen_future_repair_surface": "package runner/layout/finalizer/bootstrap publisher compile-failure evidence retention only",
                },
            },
            "blocker_delta": {
                "added": {
                    "B_CONV_NATIVE_P38_COMPILE_STAGE_EXIT2_NO_COMPILE_RECEIPT": "No compile log, argv, exit-status receipt or actual production identity was returned.",
                    "B_CONV_NATIVE_P38_BOOTSTRAP_FALLBACK_ATTEMPT_EVIDENCE_UNAVAILABLE": "The finalizer published only the three-member bootstrap partial even though its stage was PRODUCTION_COMPILE.",
                },
                "preserved": [
                    "B_CONV_NATIVE_MSE4_DESCRIPTOR_18_VS_PREPARED_20_UNIT_SEMANTICS_UNRESOLVED",
                    "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                    "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                    "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                    "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
                ],
                "closed": [],
            },
            "round_progress": {
                "compared_to_p37b_functional_progress": "ZERO",
                "compared_to_p37b_causal_progress": "ZERO",
                "package_pipeline_progress": "NONZERO_ERROR_LOCALIZATION_TO_PRODUCTION_COMPILE_STAGE_AND_BOOTSTRAP_EVIDENCE_GAP",
                "reason": "p38 MSE4 join observer never compiled or ran, so it produced no new DUT evidence.",
                "newly_proven": [
                    "the exact p38 runner reached its PRODUCTION_COMPILE stage and exited 2 without a signal",
                    "the bootstrap fixed-result publisher produced a source/execution-bound allowlisted partial return",
                    "the returned payload is insufficient to recover the compile error because attempt-root evidence is absent",
                ],
            },
            "package_local_defect": {
                "identified": True,
                "status": "REPORT_ONLY_REPAIR_FROZEN_BY_USER",
                "description": "Compile-stage exit 2 collapses to a bootstrap-only return without compile driver log or attempt-root receipts, preventing formal root-cause localization.",
                "successor_built": False,
                "storage_rotated": False,
            },
            "rule_feedback": {
                "type": "RULE_CONFIRMATION_WITH_PACKAGE_LOCAL_DEFECT_REPORT",
                "public_rule_modified": False,
                "rule_delta_proposal": None,
                "evidence": "The early finalizer preserved a consumable fixed-result partial, but the package implementation did not preserve the compile-stage causal payload required for diagnosis.",
            },
            "current_rule_receipts": {
                path: receipt(ROOT / path)
                for path in (
                    ".agents/agent.md", ".agents/plan.md", ".agents/rules/生成前必读索引.md",
                    ".agents/rules/服务器测试包生成规则.md", ".agents/rules/算子配置规则.md",
                    ".agents/rules/NDP硬件字段语义.md", ".agents/rules/INT8_SA点积专项规则.md",
                    ".agents/rules/精确UINT8量化尾专项规则.md", ".agents/rules/整网测试收敛优化专项规则.md",
                    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
                )
            },
            "constraints": {
                "analysis_only": True,
                "successor_construction": False,
                "storage_rotation": False,
                "functional_asset_change": False,
                "server_action": False,
            },
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"valid": valid, "status": result["status"], "output": str(OUTPUT), "sha256": sha(OUTPUT)}))
        return 0 if valid else 1
    finally:
        source_zip.close()
        return_zip.close()


if __name__ == "__main__":
    raise SystemExit(main())
