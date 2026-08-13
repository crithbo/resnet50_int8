#!/usr/bin/env python3
"""Independent final-ZIP audit for the p6 ARM-interface diagnostic successor."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_conv_native_four_lane_e1fb0f7_p6_armif_package as build
from tools import validate_conv_native_four_lane_e1fb0f7_c0_diag_package as base


INSTALL_NAME = build.INSTALL_NAME
PACKAGE_ROOT = build.OUTPUT_ROOT / INSTALL_NAME
PACKAGE_ZIP = build.OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT = build.OUTPUT_ROOT / f"{INSTALL_NAME}.final_zip_audit.json"
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
EXPECTED_CHANGED = sorted(
    [
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "package_tools/node0004_assumed_hardware_server_runtime.py",
        "tb_probe/native_return_observer.svh",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    ]
)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_shared_audit() -> None:
    """Point the proven p5 generic audit helpers at the fresh p6 identity."""
    base.INSTALL_NAME = INSTALL_NAME
    base.PACKAGE_ROOT = PACKAGE_ROOT
    base.PACKAGE_ZIP = PACKAGE_ZIP
    base.OUTPUT = OUTPUT
    base.runtime.INSTALL_NAME = INSTALL_NAME
    tokens = list(base.SCOPE_TOKENS["Array_Request_Manager.sv"])
    tokens.remove("buf2arm_valid_hold")
    base.SCOPE_TOKENS["Array_Request_Manager.sv"] = tuple(tokens)


def p5_relation(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(build.SOURCE_ZIP) as archive:
        source_manifest = json.loads(
            archive.read(f"{build.SOURCE_NAME}/package_manifest.json")
        )
        source_payloads = {
            info.filename[len(build.SOURCE_NAME) + 1 :]: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
            and info.filename != f"{build.SOURCE_NAME}/package_manifest.json"
        }
    target_payloads = {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    }
    changed = sorted(
        path
        for path in set(source_payloads) & set(target_payloads)
        if source_payloads[path] != target_payloads[path]
    )
    identity_normalized = [
        path
        for path in changed
        if path
        not in {"README.md", "tb_probe/native_return_observer.svh"}
        and source_payloads[path].replace(
            build.SOURCE_NAME.encode(), INSTALL_NAME.encode()
        )
        == target_payloads[path]
    ]
    observer = target_payloads[
        "tb_probe/native_return_observer.svh"
    ].decode()
    observer_checks = {
        "private_xmr_absent": "buf2arm_valid_hold" not in observer,
        "public_rvalid_present": ".buf2arm_rvalid &" in observer,
        "public_backpressure_present": ".array2arm_bp_post;" in observer,
        "derived_negation_present": "!u_NDP_Top_new" in observer,
        "armhold_assignment_single": observer.count(
            "assign n4d_arm_hold_mon"
        )
        == 1,
    }
    readme = target_payloads["README.md"].decode()
    readme_checks = {
        "fresh_p6_identity": "diagnostic p6" in readme,
        "observer_only_scope": "observer-only successor" in readme,
        "private_xmr_replacement": "buf2arm_valid_hold" in readme,
        "interface_witness": (
            "buf2arm_rvalid & !array2arm_bp_post" in readme
        ),
        "no_formal_claim": "no formal 320D payload" in readme,
    }
    return {
        "valid": (
            not (set(source_payloads) - set(target_payloads))
            and not (set(target_payloads) - set(source_payloads))
            and changed == EXPECTED_CHANGED
            and sorted(identity_normalized)
            == sorted(
                set(EXPECTED_CHANGED)
                - {"README.md", "tb_probe/native_return_observer.svh"}
            )
            and all(observer_checks.values())
            and all(readme_checks.values())
            and source_manifest["files"]
            == {
                path: {
                    "size_bytes": len(payload),
                    "sha256": base.digest(payload),
                }
                for path, payload in source_payloads.items()
            }
        ),
        "source_file_count": len(source_payloads),
        "target_file_count": len(target_payloads),
        "missing": sorted(set(source_payloads) - set(target_payloads)),
        "extra": sorted(set(target_payloads) - set(source_payloads)),
        "changed": changed,
        "expected_changed": EXPECTED_CHANGED,
        "identity_normalized": sorted(identity_normalized),
        "observer_checks": observer_checks,
        "readme_checks": readme_checks,
    }


def main() -> int:
    configure_shared_audit()
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--zip", type=Path, default=PACKAGE_ZIP)
    parser.add_argument("--iverilog", type=Path, default=IVERILOG)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    package = args.package_root.resolve()
    package_zip = args.zip.resolve()

    zip_audit = base.safe_zip_records(package_zip, INSTALL_NAME)
    directory_records = base.numeric_base.package_records(
        package, exclude_manifest=False
    )
    with tempfile.TemporaryDirectory(prefix="n4-p6-final-") as name:
        extracted = Path(name)
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(extracted)
        audited = extracted / INSTALL_NAME
        audited_records = base.numeric_base.package_records(
            audited, exclude_manifest=False
        )
        manifest = json.loads(
            (audited / "package_manifest.json").read_text(encoding="utf-8")
        )
        manifest_files_exact = (
            manifest.get("files")
            == base.numeric_base.package_records(audited)
        )
        relation = p5_relation(audited)
        closure = base.consumer_closure(audited)
        git_identity = base.immutable_git_identity()
        observer = (
            audited / "tb_probe/native_return_observer.svh"
        ).read_text(encoding="utf-8")
        observer_hdl = base.compile_observer_cases(
            observer, args.iverilog.resolve()
        )
        runtime_gate = base.runtime_controls(audited)
        runner_gate = base.runner_controls(audited)
        binding_feature = base.observer_binding_and_feature_controls(audited)
        canonical = base.canonical_decision_controls(audited)
        allowlist = base.return_allowlist_controls(audited)
        runner_end_to_end = base.runner_end_to_end_controls(package_zip)

    manifest_checks = {
        "ready_not_run": manifest.get("status") == "PACKAGE_READY_NOT_RUN",
        "diagnostic_only": (
            manifest.get("candidate_class")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        ),
        "candidate_release_false": manifest.get("candidate_release") is False,
        "c0_only": (
            manifest.get("conv_run_ids") == ["c0"]
            and manifest.get("simulation_run_count") == 1
            and manifest.get("tail_run_ids") == []
        ),
        "formal_d_absent_by_design": (
            manifest.get("formal_readback_count") == 0
            and manifest.get("readback_checks") == []
        ),
        "no_functional_rtl": (
            manifest.get("functional_rtl_modified") is False
            and manifest.get("functional_rtl_file_count") == 0
            and manifest.get("server_rtl_entries") == 0
        ),
        "p5_return_analysis_exact": (
            manifest.get("source_return_analysis", {}).get("sha256")
            == build.sha256(build.RETURN_ANALYSIS)
            and manifest.get("source_return_analysis", {}).get(
                "formal_return_sha256"
            )
            == (
                "bcebec2837fdf3398d2786bf7c75dc6bf5b4c6012d136911e9"
                "d998844232aeb0"
            )
        ),
        "p5_source_exact": (
            manifest.get("delivery_and_workload_provenance", {}).get(
                "source_p5_zip_sha256"
            )
            == build.SOURCE_ZIP_SHA256
        ),
        "observer_sha_exact": (
            manifest.get("observer_binding", {}).get("source_sha256")
            == base.sha256(
                package / "tb_probe/native_return_observer.svh"
            )
        ),
        "observer_semantics_declared": (
            manifest.get("observer_binding", {}).get("private_state_xmr")
            is False
            and "buf2arm_rvalid & !array2arm_bp_post"
            in manifest.get("observer_binding", {}).get(
                "armhold_semantics", ""
            )
        ),
        "rule_receipts_current": manifest.get("rule_receipts")
        == {
            relative: build.sha256(ROOT / relative)
            for relative in build.RULE_PATHS
        },
        "rule_confirmation_only": (
            manifest.get("rule_feedback", {}).get("type")
            == "RULE_CONFIRMATION"
            and manifest.get("rule_feedback", {}).get(
                "rule_delta_proposal"
            )
            == []
        ),
        "manifest_files_exact": manifest_files_exact,
        "path_budget_exact": (
            manifest.get("path_length_budget")
            == build.path_budget(package)
            and manifest["path_length_budget"][
                "max_projected_absolute_path_chars"
            ]
            <= manifest["path_length_budget"][
                "max_projected_absolute_path_limit_chars"
            ]
        ),
    }
    replay = base.deterministic_zip_replay(package, package_zip)
    sidecar = Path(str(package_zip) + ".sha256")
    sidecar_expected = (
        f"{base.sha256(package_zip)}  {package_zip.name}\n"
    )
    checks = {
        "source_p5_exact": base.sha256(build.SOURCE_ZIP)
        == build.SOURCE_ZIP_SHA256,
        "safe_final_zip": zip_audit["valid"],
        "zip_matches_persisted_directory": (
            zip_audit["records"] == directory_records == audited_records
        ),
        "manifest_gate": all(manifest_checks.values()),
        "p5_content_relation": relation["valid"],
        "consumer_closure": closure["valid"],
        "immutable_e1fb0f7_git_leaf_identity": git_identity["valid"],
        "focused_observer_hdl_syntax_scope": observer_hdl["valid"],
        "runtime_positive_and_negative_controls": runtime_gate["valid"],
        "runner_controls": runner_gate["valid"],
        "observer_binding_and_feature_controls": binding_feature["valid"],
        "canonical_decision_controls": canonical["valid"],
        "manifest_bound_return_allowlist": allowlist["valid"],
        "runner_end_to_end_safe_stub_controls":
            runner_end_to_end["valid"],
        "deterministic_zip_replay": replay["valid"],
        "sidecar_exact": (
            sidecar.is_file()
            and sidecar.read_text(encoding="ascii") == sidecar_expected
        ),
    }
    errors = [key for key, value in checks.items() if not value]
    result = {
        "schema": "conv-native-four-lane-p6-armif-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "FAIL",
        "valid": not errors,
        "errors": errors,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package": str(package),
        "zip": str(package_zip),
        "zip_bytes": package_zip.stat().st_size,
        "zip_sha256": base.sha256(package_zip),
        "sidecar": str(sidecar),
        "sidecar_sha256": base.sha256(sidecar),
        "checks": checks,
        "manifest_checks": manifest_checks,
        "zip_audit": {
            key: value for key, value in zip_audit.items()
            if key != "records"
        },
        "source_p5_relation": relation,
        "consumer_closure": closure,
        "immutable_git_identity": git_identity,
        "observer_hdl": observer_hdl,
        "runtime_controls": runtime_gate,
        "runner_controls": runner_gate,
        "observer_binding_and_feature_controls": binding_feature,
        "canonical_decision_controls": canonical,
        "return_allowlist_controls": allowlist,
        "runner_end_to_end_controls": runner_end_to_end,
        "reproducibility": replay,
        "final_zip_rule_self_audit": {
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "current_match": manifest_checks["rule_receipts_current"],
            "current_server_package_rule_sha256": build.sha256(
                ROOT / ".agents/rules/服务器测试包生成规则.md"
            ),
            "current_plan_mutable_provenance_sha256": build.sha256(
                ROOT / ".agents/plan.md"
            ),
            "independent_validator": str(Path(__file__).resolve()),
            "independent_validator_sha256": build.sha256(Path(__file__)),
        },
        "claim_boundary": {
            "server_action": False,
            "production_vcs_or_dut_simulation": False,
            "formal_320d_in_package": False,
            "E3_E4_E5_claimed": False,
            "purpose": (
                "re-enter production compilation and collect c0 boundary "
                "diagnostics without the p5 private-state XMR"
            ),
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "rule_delta_proposal": [],
        },
    }
    write_json(args.output.resolve(), result)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
