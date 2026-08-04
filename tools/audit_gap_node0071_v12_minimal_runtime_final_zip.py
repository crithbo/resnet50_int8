from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_v10_runner_guard_final_zip as common


PACKAGE_DIR = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
ZIP = PACKAGE_DIR / "r5_n71_gap_v12_minruntime.zip"
SOURCE_ZIP = PACKAGE_DIR / "r5_n71_gap_v11_runner_rule.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
OUTPUT = PACKAGE_DIR / (
    "r5_n71_gap_v12_minruntime.final_zip_rule_self_audit.json"
)
RUNNER_REPORT = PACKAGE_DIR / (
    "r5_n71_gap_v12_minruntime.runner_chain_validation.json"
)
ROOT_NAME = "r5_n71_gap_v12_minruntime"
SOURCE_ROOT_NAME = "r5_n71_gap_v11_runner_rule"
SOURCE_SHA256 = (
    "dd3453ad79c87a60bf86bb492ac250bdf30a7369d9cea5498c4971ddcc524680"
)
OBSERVER_SHA256 = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)
IDENTITY_POINTER = "/files/tb_probe~1native_return_observer.svh/sha256"
RULES = {
    ".agents/rules/生成前必读索引.md":
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    ".agents/rules/算子配置规则.md":
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ".agents/rules/NDP硬件字段语义.md":
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ".agents/rules/服务器测试包生成规则.md":
        "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a",
    ".agents/rules/GAP_int32_mac_bypass_rules.md":
        "b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96",
    ".agents/rules/GAP_probe_v7_validator_rules.md":
        "4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf",
    ".agents/rules/精确UINT8量化尾专项规则.md":
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
}
REQUIRED_RULE_IDS = {
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
    "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
    "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
    "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
    "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
    "CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001",
    "CDA-GAP-D-READBACK-COVERAGE-001",
    "CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001",
    "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
}
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "package_tools/gap_node0071_package_observer_guard.py",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


def validate_manifest(
    files: dict[str, bytes], errors: list[str]
) -> tuple[dict[str, Any], bool, bool, list[str]]:
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"].decode())
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        raise common.AuditError("manifest files map absent")
    exact_set = set(files) == set(declared) | {"TEST_PACKAGE_MANIFEST.json"}
    if not exact_set:
        errors.append("manifest exact-set differs")
    for relative, receipt in declared.items():
        payload = files.get(relative)
        if (
            payload is None
            or len(payload) != receipt.get("size_bytes")
            or common.sha256_bytes(payload) != receipt.get("sha256")
        ):
            errors.append(f"manifest receipt differs: {relative}")
    contract = manifest.get("final_zip_rule_self_audit_contract", {})
    receipt_map = {
        item.get("path"): item
        for item in contract.get("read_receipt", [])
        if isinstance(item, dict)
    }
    current_match = (
        contract.get("all_current_match") is True
        and all(
            receipt_map.get(path, {}).get("sha256") == digest
            and receipt_map.get(path, {}).get("current_match") is True
            for path, digest in RULES.items()
        )
    )
    if not current_match:
        errors.append("manifest rule current-match receipt differs")
    applicable = [
        str(item) for item in contract.get("applicable_rule_ids", [])
    ]
    if not REQUIRED_RULE_IDS <= set(applicable):
        errors.append("manifest applicable rule IDs differ")
    return manifest, exact_set, current_match, applicable


def audit() -> dict[str, Any]:
    errors: list[str] = []
    command_receipts: list[dict[str, Any]] = []
    current_receipts = []
    for relative, expected in RULES.items():
        observed = common.sha256_file(ROOT / relative)
        current_receipts.append(
            {
                "path": relative,
                "expected_sha256": expected,
                "observed_sha256": observed,
                "current_match": observed == expected,
            }
        )
        if observed != expected:
            errors.append(f"current rule SHA differs: {relative}")

    zip_sha = common.sha256_file(ZIP)
    sidecar_exact = (
        SIDECAR.read_text(encoding="ascii") == f"{zip_sha}  {ZIP.name}\n"
    )
    if not sidecar_exact:
        errors.append("sidecar differs")
    target, target_crc_bad = common.zip_payload(ZIP, ROOT_NAME)
    source, source_crc_bad = common.zip_payload(
        SOURCE_ZIP, SOURCE_ROOT_NAME
    )
    if target_crc_bad is not None:
        errors.append(f"target ZIP CRC differs: {target_crc_bad}")
    if (
        source_crc_bad is not None
        or common.sha256_file(SOURCE_ZIP) != SOURCE_SHA256
    ):
        errors.append("source v11 identity differs")
    manifest, exact_set, manifest_current, applicable = validate_manifest(
        target, errors
    )

    changed = {
        path
        for path in set(source) & set(target)
        if source[path] != target[path]
    }
    relative_set_equal = set(source) == set(target)
    numeric_paths = sorted(
        path
        for path in target
        if path.startswith("workload/")
        and path not in {
            "workload/sca_cfg.json", "workload/sca_cfg_D.json"
        }
    )
    immutable_paths = sorted(set(target) - ALLOWED_CHANGED)
    numeric_equal = (
        len(numeric_paths) == 73
        and all(source[path] == target[path] for path in numeric_paths)
    )
    immutable_equal = (
        len(immutable_paths) == 119
        and all(source[path] == target[path] for path in immutable_paths)
    )
    observer_equal = (
        source["tb_probe/native_return_observer.svh"]
        == target["tb_probe/native_return_observer.svh"]
        and common.sha256_bytes(
            target["tb_probe/native_return_observer.svh"]
        )
        == OBSERVER_SHA256
    )
    if not (
        relative_set_equal
        and changed == ALLOWED_CHANGED
        and numeric_equal
        and immutable_equal
        and observer_equal
    ):
        errors.append("v11-to-v12 frozen-payload boundary differs")

    runner = target["PREPARE_AND_RUN.sh"].decode()
    observer_contract = manifest.get("package_local_observer", {})
    binding_contract = manifest.get("observer_binding_contract", {})
    manifest_single_source = (
        manifest["files"]["tb_probe/native_return_observer.svh"]["sha256"]
        == OBSERVER_SHA256
        and observer_contract.get("identity_json_pointer")
        == IDENTITY_POINTER
        and "sha256" not in observer_contract
        and binding_contract.get("source_identity_json_pointer")
        == IDENTITY_POINTER
        and "source_sha256" not in binding_contract
        and OBSERVER_SHA256 not in runner
        and "--expected-sha256" not in runner
        and '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json"'
        in runner
    )
    if not manifest_single_source:
        errors.append("manifest observer single-source differs")

    precompile = runner.split(
        "printf 'make -C %q -f Makefile.tb_NDP_Top_new_phy compile", 1
    )[0]
    forbidden_runtime_source_gates = [
        "git rev-parse",
        "sha256sum \"$server_root",
        "[ -f \"$server_root/",
        "[ -r \"$server_root/",
        "find \"$server_root",
        "README_HARDWARE_SIM_ENTRY",
        "rtl/filelists/",
    ]
    runtime_preflight_minimal = not any(
        token in precompile for token in forbidden_runtime_source_gates
    )
    if not runtime_preflight_minimal:
        errors.append("runtime preflight inspects server source")

    runtime_d_absent = not any(
        path.startswith("workload/readback/") for path in target
    )
    if not runtime_d_absent:
        errors.append("runtime readback target preseeded")
    allowlist = manifest.get("return_allowlist", [])
    allowlist_valid = (
        isinstance(allowlist, list)
        and len(allowlist) == 70
        and len({item.get("target_path") for item in allowlist}) == 70
    )
    if not allowlist_valid:
        errors.append("return allowlist differs")

    validators = [
        (
            "canonical_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_canonical_package.py",
            [str(ZIP)],
        ),
        (
            "observer_four_way_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_observer_binding.py",
            [str(ZIP)],
        ),
        (
            "dual_ingress_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_v8_dual_ingress.py",
            [str(ZIP)],
        ),
        (
            "runner_positive_and_negative_controls",
            ROOT
            / "tools/validate_gap_node0071_v12_minimal_runtime_chain.py",
            [
                "--target-zip", str(ZIP),
                "--output", str(RUNNER_REPORT),
            ],
        ),
    ]
    reports: dict[str, Any] = {}
    for name, script, arguments in validators:
        receipt, stdout = common.run_command(
            name, [sys.executable, str(script), *arguments], ROOT
        )
        command_receipts.append(receipt)
        reports[name] = (
            json.loads(RUNNER_REPORT.read_text(encoding="utf-8"))
            if name == "runner_positive_and_negative_controls"
            else json.loads(stdout)
        )

    with tempfile.TemporaryDirectory(
        prefix=".g71-v12-audit-",
        dir=ROOT,
        ignore_cleanup_errors=True,
    ) as temporary:
        extraction = Path(temporary)
        with zipfile.ZipFile(ZIP) as archive:
            archive.extractall(extraction)
        package = extraction / ROOT_NAME
        before = common.tree_records(package)
        preflight_receipt, preflight_stdout = common.run_command(
            "fresh_extract_package_preflight",
            [
                sys.executable,
                str(
                    package
                    / "package_tools/gap_node0071_complete_server_runtime.py"
                ),
                "preflight",
                "--package-root",
                str(package),
            ],
            package,
        )
        command_receipts.append(preflight_receipt)
        self_receipt, self_stdout = common.run_command(
            "fresh_extract_canonical_self_test",
            [
                sys.executable,
                str(
                    package
                    / "package_tools/gap_node0071_canonical_decision.py"
                ),
                "self-test",
            ],
            package,
        )
        command_receipts.append(self_receipt)
        syntax_receipt, _ = common.run_command(
            "fresh_extract_runner_bash_syntax",
            [
                r"C:\Program Files\Git\bin\bash.exe",
                "-n",
                str(package / "PREPARE_AND_RUN.sh"),
            ],
            package,
        )
        command_receipts.append(syntax_receipt)
        bootstrap_immutable = before == common.tree_records(package)
        if not bootstrap_immutable:
            errors.append("fresh extract preflight mutated package")
        preflight_report = json.loads(preflight_stdout)
        self_report = json.loads(self_stdout)

    canonical = reports["canonical_validator_and_controls"]
    observer = reports["observer_four_way_validator_and_controls"]
    dual = reports["dual_ingress_validator_and_controls"]
    runner_report = reports["runner_positive_and_negative_controls"]
    controls_valid = (
        canonical.get("all_negative_controls_fail_closed") is True
        and observer.get("all_negative_controls_fail_closed") is True
        and dual.get("all_negative_controls_fail_closed") is True
        and runner_report.get("all_negative_controls_fail_closed") is True
        and all(
            item.get("failed_closed", item.get("pass", False))
            for item in self_report.get("negative_controls", {}).values()
        )
    )
    statuses_valid = (
        canonical.get("status") == "CANONICAL_DECISION_RULE_VALIDATED"
        and observer.get("status") == "PASS"
        and dual.get("status") == "PASS"
        and runner_report.get("valid") is True
        and runner_report.get("manifest_single_source") is True
        and runner_report.get("runtime_preflight_minimal") is True
        and runner_report["positive_full_runner"]["exit_code"] == 86
        and runner_report["positive_full_runner"]["make_reached"]
        and runner_report["positive_full_runner"][
            "actual_compile_argv_exists"
        ]
        and runner_report["wrong_manifest_identity_full_runner"][
            "exit_code"
        ]
        == 5
        and not runner_report["wrong_manifest_identity_full_runner"][
            "make_reached"
        ]
        and preflight_report.get("valid") is True
    )
    if not controls_valid:
        errors.append("required negative control differs")
    if not statuses_valid:
        errors.append("validator positive status differs")

    passed = (
        not errors
        and all(item["exit_code"] == 0 for item in command_receipts)
    )
    return {
        "schema":
            "gap-node0071-v12-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if passed
            else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "errors": errors,
        "error_count": len(errors),
        "zip": str(ZIP),
        "zip_size_bytes": ZIP.stat().st_size,
        "zip_sha256": zip_sha,
        "sidecar": str(SIDECAR),
        "sidecar_sha256": common.sha256_file(SIDECAR),
        "sidecar_content_exact": sidecar_exact,
        "zip_crc_valid": target_crc_bad is None,
        "manifest_exact_set_valid": exact_set,
        "manifest_current_match": manifest_current,
        "current_rule_receipts": current_receipts,
        "plan_sha256_mutable_provenance_only": common.sha256_file(
            ROOT / ".agents/plan.md"
        ),
        "applicable_rule_ids": applicable,
        "source_v11": {
            "zip": str(SOURCE_ZIP),
            "sha256": common.sha256_file(SOURCE_ZIP),
            "quarantined": True,
        },
        "frozen_reuse_boundary": {
            "relative_file_set_equal": relative_set_equal,
            "changed_paths": sorted(changed),
            "changed_paths_exact_allowlist": changed == ALLOWED_CHANGED,
            "numeric_workload_file_count": len(numeric_paths),
            "numeric_workload_tree_equal": numeric_equal,
            "immutable_file_count": len(immutable_paths),
            "immutable_tree_equal": immutable_equal,
            "observer_algorithm_unchanged": observer_equal,
        },
        "minimal_runtime_contract": {
            "manifest_single_source": manifest_single_source,
            "identity_json_pointer": IDENTITY_POINTER,
            "runner_expected_sha_hardcoded": False,
            "runtime_preflight_minimal": runtime_preflight_minimal,
            "server_source_files_inspected": False,
            "positive_compile_stub_exit_code":
                runner_report["positive_full_runner"]["exit_code"],
            "positive_compile_reached":
                runner_report["positive_full_runner"]["make_reached"],
            "wrong_identity_exit_code":
                runner_report["wrong_manifest_identity_full_runner"][
                    "exit_code"
                ],
            "wrong_identity_compile_reached":
                runner_report["wrong_manifest_identity_full_runner"][
                    "make_reached"
                ],
        },
        "rule_checks": {
            "runtime_d_absent": runtime_d_absent,
            "return_allowlist_valid": allowlist_valid,
            "bootstrap_immutable": bootstrap_immutable,
            "all_required_controls_fail_closed": controls_valid,
            "positive_statuses_valid": statuses_valid,
        },
        "command_receipts": command_receipts,
        "validator_report_sha256": {
            item["name"]: item["stdout_sha256"]
            for item in command_receipts
        },
        "runner_chain_report": str(RUNNER_REPORT),
        "runner_chain_report_sha256": common.sha256_file(RUNNER_REPORT),
        "numeric_analysis_repeated": False,
        "sum_tail_workload_reexecuted": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "package_release": {
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "server_command":
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
            "expected_return": [
                "r5_n71_gap_v12_minruntime_return.zip",
                "r5_n71_gap_v12_minruntime_return.zip.sha256",
            ],
        },
    }


def main() -> int:
    result = audit()
    OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
