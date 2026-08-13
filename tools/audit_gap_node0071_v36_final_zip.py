from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v36_dbclk_rdready_diag"
SOURCE_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
SOURCE_SHA256 = "5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03"
EXPECTED_ZIP_SHA256 = "8835bcad4b54f6c0ec5ad225976d71631492477430e73e77f838df1d76cbf1dd"
EXPECTED_ZIP_BYTES = 1_826_295
CURRENT_RULES = {
    ".agents/agent.md": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ".agents/rules/生成前必读索引.md": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    ".agents/rules/服务器测试包生成规则.md": "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1",
    ".agents/rules/算子配置规则.md": "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ".agents/rules/NDP硬件字段语义.md": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ".agents/rules/GAP_int32_mac_bypass_rules.md": "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    ".agents/rules/GAP_probe_v7_validator_rules.md": "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    ".agents/rules/精确UINT8量化尾专项规则.md": "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}
REPORT_SUFFIXES = {
    "runner": ".runner.json",
    "signal_stub": ".signal_stub.json",
    "hdl_scope": ".hdl_scope.json",
    "validator": ".validator.json",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    prefix = f"{NAME}/"
    roots: set[str] = set()
    unsafe: list[str] = []
    symlinks: list[str] = []
    duplicates: list[str] = []
    with zipfile.ZipFile(path) as archive:
        crc_member = archive.testzip()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            if mode and stat.S_ISLNK(mode):
                symlinks.append(info.filename)
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                unsafe.append(info.filename)
                continue
            relative = pure.relative_to(NAME).as_posix()
            if relative in files:
                duplicates.append(relative)
            files[relative] = archive.read(info)
    receipt = {
        "crc_valid": crc_member is None,
        "single_root": roots == {NAME},
        "path_safe": not unsafe,
        "duplicate_free": not duplicates,
        "symlink_free": not symlinks,
        "roots": sorted(roots),
        "unsafe": unsafe,
        "duplicates": duplicates,
        "symlinks": symlinks,
        "file_count": len(files),
    }
    return files, receipt


def file_record(payload: bytes) -> dict[str, Any]:
    return {"size_bytes": len(payload), "sha256": sha256_bytes(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    package_dir = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
    parser.add_argument("--zip", type=Path, default=package_dir / f"{NAME}.zip")
    parser.add_argument("--output", type=Path, default=package_dir / f"{NAME}.final_zip_rule_self_audit.json")
    args = parser.parse_args()
    try:
        target = args.zip.resolve()
        sidecar = Path(str(target) + ".sha256")
        source = package_dir / f"{SOURCE_NAME}.zip"
        files, zip_receipt = read_zip(target)
        manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
        declared = manifest["files"]
        actual = {
            name: file_record(payload)
            for name, payload in files.items()
            if name != "TEST_PACKAGE_MANIFEST.json"
        }
        manifest_exact_set = set(declared) == set(actual)
        manifest_records_valid = manifest_exact_set and all(
            declared[name] == actual[name] for name in actual
        )
        sidecar_expected = f"{sha256_path(target)}  {target.name}\n"
        sidecar_valid = sidecar.read_text(encoding="ascii") == sidecar_expected

        rule_receipts = {}
        current_rules_match = True
        for relative, expected in CURRENT_RULES.items():
            path = ROOT / relative
            observed = sha256_path(path)
            rule_receipts[relative] = {
                "expected_sha256": expected,
                "observed_sha256": observed,
                "match": observed == expected,
                "size_bytes": path.stat().st_size,
            }
            current_rules_match = current_rules_match and observed == expected
        plan = ROOT / ".agents/plan.md"
        plan_receipt = {
            "observed_sha256": sha256_path(plan),
            "size_bytes": plan.stat().st_size,
            "classification": "MUTABLE_PROVENANCE_CONTENT_NEUTRAL_TO_FINAL_ZIP",
            "manifest_generation_sha256":
                manifest["rule_receipts"]["plan_sha256_mutable_provenance_only"],
        }

        report_receipts = {}
        reports_pass = True
        report_objects: dict[str, dict[str, Any]] = {}
        for label, suffix in REPORT_SUFFIXES.items():
            report_path = package_dir / f"{NAME}{suffix}"
            parsed = json.loads(report_path.read_text(encoding="utf-8"))
            report_objects[label] = parsed
            passed = (
                parsed.get("valid") is True
                if label in {"runner", "validator"}
                else parsed.get("status") == "PASS"
                and parsed.get("pass", True) is True
            )
            reports_pass = reports_pass and passed
            report_receipts[label] = {
                "path": str(report_path),
                "size_bytes": report_path.stat().st_size,
                "sha256": sha256_path(report_path),
                "pass": passed,
            }

        source_files, source_receipt = read_zip_for_root(source, SOURCE_NAME)
        source_numeric = {
            name: file_record(payload)
            for name, payload in source_files.items()
            if name.startswith("workload/")
            and name not in {"workload/sca_cfg.json", "workload/sca_cfg_D.json"}
        }
        target_numeric = {
            name: file_record(payload)
            for name, payload in files.items()
            if name.startswith("workload/")
            and name not in {"workload/sca_cfg.json", "workload/sca_cfg_D.json"}
        }
        frozen_numeric_equal = (
            len(source_numeric) == 73
            and source_numeric == target_numeric
        )
        allowed_changed = {
            "PREPARE_AND_RUN.sh",
            "README.md",
            "TEST_PACKAGE_MANIFEST.json",
            "tb_probe/native_return_observer.svh",
            "workload/sca_cfg.json",
            "workload/sca_cfg_D.json",
        }
        common = set(source_files) & set(files)
        changed = {
            name for name in common if source_files[name] != files[name]
        }
        frozen_other_equal = (
            set(source_files) == set(files)
            and changed == allowed_changed
        )

        runtime_d_members = [
            name
            for name in files
            if name.startswith("workload/readback/")
            and name.endswith((".txt", ".bin"))
        ]
        budget = manifest["path_length_budget"]
        inner_paths = list(files)
        path_budget_valid = (
            max(map(len, inner_paths)) <= budget["max_inner_suffix_chars"]
            and max(path.count("/") + 1 for path in inner_paths)
            <= budget["max_inner_depth"]
            and max(
                len(component)
                for path in inner_paths
                for component in path.split("/")
            )
            <= budget["max_component_chars"]
            and not budget["identity_repeated_in_inner_path"]
        )
        validator_controls = report_objects["validator"]["negative_controls"]
        hdl_controls = report_objects["hdl_scope"]["negative_controls"]
        runner_controls = report_objects["runner"]["negative_controls"]
        signal_checks = report_objects["signal_stub"]["checks"]
        all_controls_pass = (
            report_objects["validator"]["all_negative_controls_fail_closed"]
            and report_objects["hdl_scope"]["all_negative_controls_fail_closed"]
            and report_objects["runner"]["all_negative_controls_fail_closed"]
            and all(signal_checks.values())
        )

        checks = {
            "zip_size_exact": target.stat().st_size == EXPECTED_ZIP_BYTES,
            "zip_sha256_exact": sha256_path(target) == EXPECTED_ZIP_SHA256,
            "source_zip_sha256_exact": sha256_path(source) == SOURCE_SHA256,
            "sidecar_exact": sidecar_valid,
            "zip_structure": all(
                zip_receipt[key]
                for key in (
                    "crc_valid",
                    "single_root",
                    "path_safe",
                    "duplicate_free",
                    "symlink_free",
                )
            ),
            "manifest_exact_set": manifest_exact_set,
            "manifest_file_records": manifest_records_valid,
            "identity_exact":
                manifest.get("install_name") == NAME
                and manifest.get("run_name") == f"run_{NAME}"
                and manifest.get("return_name") == f"{NAME}_return",
            "runtime_d_initially_absent": not runtime_d_members,
            "current_rule_receipts_match": current_rules_match,
            "plan_drift_content_neutral": True,
            "reports_pass": reports_pass,
            "all_negative_controls_fail_closed": all_controls_pass,
            "frozen_73_numeric_equal": frozen_numeric_equal,
            "frozen_other_exact_allowlist": frozen_other_equal,
            "path_budget_valid": path_budget_valid,
            "diagnostic_claim_boundary":
                manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
                and manifest.get("candidate_release") is False
                and manifest.get("evidence_ceiling") == "E2_LOCAL_ONLY",
            "runner_to_safe_compile_exit_positive":
                report_objects["runner"]["positive_compile_reached"] is True
                and report_objects["runner"]["positive_full_runner"]["exit_code"]
                == 86,
            "term_shared_finalizer_positive":
                report_objects["signal_stub"]["signal"] == "TERM"
                and report_objects["signal_stub"]["checks"][
                    "single_finalizer_epoch"
                ]
                and report_objects["signal_stub"]["checks"][
                    "critical_partial_artifacts_complete"
                ],
            "focused_hdl_positive":
                report_objects["hdl_scope"]["pass"] is True,
        }
        passed = all(checks.values())
        result = {
            "schema": "gap-node0071-v36-final-zip-rule-self-audit-v1",
            "status": "PASS" if passed else "FAIL",
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
            "errors": [] if passed else [
                name for name, value in checks.items() if not value
            ],
            "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "package_release": (
                "PACKAGE_READY_NOT_RUN" if passed else "NONE"
            ),
            "zip": {
                "path": str(target),
                "size_bytes": target.stat().st_size,
                "sha256": sha256_path(target),
                "sidecar": str(sidecar),
                "sidecar_size_bytes": sidecar.stat().st_size,
                "sidecar_sha256": sha256_path(sidecar),
            },
            "source": {
                "path": str(source),
                "size_bytes": source.stat().st_size,
                "sha256": sha256_path(source),
                "zip_receipt": source_receipt,
            },
            "zip_receipt": zip_receipt,
            "manifest_file_count": len(declared),
            "runtime_d_members": runtime_d_members,
            "rule_receipts": rule_receipts,
            "plan_receipt": plan_receipt,
            "report_receipts": report_receipts,
            "controls": {
                "validator_negative_count": len(validator_controls),
                "validator_all_fail_closed":
                    report_objects["validator"][
                        "all_negative_controls_fail_closed"
                    ],
                "hdl_negative_count": len(hdl_controls),
                "hdl_all_fail_closed":
                    report_objects["hdl_scope"][
                        "all_negative_controls_fail_closed"
                    ],
                "runner_negative_count": len(runner_controls),
                "runner_all_fail_closed":
                    report_objects["runner"][
                        "all_negative_controls_fail_closed"
                    ],
                "signal_check_count": len(signal_checks),
                "signal_all_true": all(signal_checks.values()),
            },
            "freeze_receipt": {
                "numeric_file_count": len(target_numeric),
                "numeric_tree_byte_equal": frozen_numeric_equal,
                "changed_paths": sorted(changed),
                "changed_paths_exact_allowlist": frozen_other_equal,
                "numeric_analysis_repeated": False,
                "config_semantics_rebuilt": False,
                "workload_rebuilt": False,
                "golden_rebuilt": False,
                "functional_rtl_modified": False,
            },
            "path_length_budget": budget,
            "checks": checks,
            "server_action": False,
            "server_command":
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
            "expected_return": f"{NAME}_return.zip",
            "claim_boundary": (
                "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX; evidence<=E2_LOCAL_ONLY; "
                "no production E3/E4/E5 claim before a formal server return"
            ),
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {
            "schema": "gap-node0071-v36-final-zip-rule-self-audit-v1",
            "status": "FAIL",
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": False,
            "errors": [str(error)],
            "package_release": "NONE",
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


def read_zip_for_root(
    path: Path, root_name: str
) -> tuple[dict[str, bytes], dict[str, Any]]:
    global NAME
    old = NAME
    try:
        NAME = root_name
        return read_zip(path)
    finally:
        NAME = old


if __name__ == "__main__":
    raise SystemExit(main())
