from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
ZIP = PACKAGE_DIR / "r5_n71_gap_v10_runner_guard.zip"
SOURCE_ZIP = PACKAGE_DIR / "r5_n71_gap_v9_ingress_rule.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
OUTPUT = PACKAGE_DIR / (
    "r5_n71_gap_v10_runner_guard.final_zip_rule_self_audit.json"
)
RUNNER_REPORT = PACKAGE_DIR / (
    "r5_n71_gap_v10_runner_guard.runner_chain_validation.json"
)
ROOT_NAME = "r5_n71_gap_v10_runner_guard"
SOURCE_ROOT_NAME = "r5_n71_gap_v9_ingress_rule"
RULES = {
    ".agents/rules/生成前必读索引.md":
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    ".agents/rules/算子配置规则.md":
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ".agents/rules/NDP硬件字段语义.md":
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ".agents/rules/服务器测试包生成规则.md":
        "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa",
    ".agents/rules/GAP_int32_mac_bypass_rules.md":
        "b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96",
    ".agents/rules/GAP_probe_v7_validator_rules.md":
        "4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf",
    ".agents/rules/精确UINT8量化尾专项规则.md":
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
}
SOURCE_SHA256 = (
    "d37f40e768001d3588cd22f25040ba4e229ffc138221a42b13d7e446436e644c"
)
OBSERVER_SHA256 = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)
OLD_EXPECTED_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class AuditError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_records(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def zip_payload(path: Path, root_name: str) -> tuple[dict[str, bytes], str | None]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        crc_bad = archive.testzip()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != root_name
                or (mode and stat.S_ISLNK(mode))
            ):
                raise AuditError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in files:
                raise AuditError(f"duplicate ZIP member: {relative}")
            files[relative] = archive.read(info)
    return files, crc_bad


def run_command(name: str, command: list[str], cwd: Path) -> tuple[dict[str, Any], str]:
    process = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    stdout = process.stdout
    stderr = process.stderr
    receipt = {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "exit_code": process.returncode,
        "status": "PASS" if process.returncode == 0 else "FAIL",
        "stdout_sha256": sha256_bytes(stdout.encode()),
        "stderr_sha256": sha256_bytes(stderr.encode()),
        "stdout_size_bytes": len(stdout.encode()),
        "stderr_size_bytes": len(stderr.encode()),
    }
    if process.returncode:
        raise AuditError(
            f"{name} failed with exit {process.returncode}: {stderr}"
        )
    return receipt, stdout


def validate_manifest(
    files: dict[str, bytes],
    errors: list[str],
) -> tuple[dict[str, Any], bool, bool, list[str]]:
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"].decode())
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        raise AuditError("manifest files map absent")
    exact_set = set(files) == set(declared) | {"TEST_PACKAGE_MANIFEST.json"}
    if not exact_set:
        errors.append("manifest exact-set differs")
    for relative, receipt in declared.items():
        payload = files.get(relative)
        if (
            payload is None
            or len(payload) != receipt.get("size_bytes")
            or sha256_bytes(payload) != receipt.get("sha256")
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
    required = {
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
    applicable_valid = required <= set(applicable)
    if not applicable_valid:
        errors.append("manifest applicable rule IDs differ")
    return manifest, exact_set, current_match, applicable


def audit() -> dict[str, Any]:
    errors: list[str] = []
    command_receipts: list[dict[str, Any]] = []
    current_receipts = []
    for relative, expected in RULES.items():
        observed = sha256_file(ROOT / relative)
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

    zip_sha = sha256_file(ZIP)
    sidecar_exact = (
        SIDECAR.read_text(encoding="ascii") == f"{zip_sha}  {ZIP.name}\n"
    )
    if not sidecar_exact:
        errors.append("sidecar differs")
    target, target_crc_bad = zip_payload(ZIP, ROOT_NAME)
    source, source_crc_bad = zip_payload(SOURCE_ZIP, SOURCE_ROOT_NAME)
    if target_crc_bad is not None:
        errors.append(f"target ZIP CRC differs: {target_crc_bad}")
    if source_crc_bad is not None or sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        errors.append("source v9 identity differs")
    manifest, exact_set, manifest_current, applicable = validate_manifest(
        target, errors
    )

    changed = {
        path for path in set(source) & set(target)
        if source[path] != target[path]
    }
    relative_set_equal = set(source) == set(target)
    numeric_paths = sorted(
        path for path in target
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
        len(immutable_paths) == 120
        and all(source[path] == target[path] for path in immutable_paths)
    )
    observer_equal = (
        source["tb_probe/native_return_observer.svh"]
        == target["tb_probe/native_return_observer.svh"]
        and sha256_bytes(target["tb_probe/native_return_observer.svh"])
        == OBSERVER_SHA256
    )
    if not (
        relative_set_equal
        and changed == ALLOWED_CHANGED
        and numeric_equal
        and immutable_equal
        and observer_equal
    ):
        errors.append("v9-to-v10 frozen-payload boundary differs")

    runner = target["PREPARE_AND_RUN.sh"].decode()
    runner_binding = (
        runner.count(OBSERVER_SHA256) == 1
        and OLD_EXPECTED_SHA256 not in runner
        and "|| exit 7" in runner
        and "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        in runner
    )
    if not runner_binding:
        errors.append("runner observer guard binding differs")
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
        ),
        (
            "observer_four_way_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_observer_binding.py",
        ),
        (
            "dual_ingress_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_v8_dual_ingress.py",
        ),
    ]
    validator_reports: dict[str, Any] = {}
    for name, script in validators:
        receipt, stdout = run_command(
            name, [sys.executable, str(script), str(ZIP)], ROOT
        )
        command_receipts.append(receipt)
        validator_reports[name] = json.loads(stdout)

    runner_receipt, runner_stdout = run_command(
        "runner_preflight_to_compile_positive_and_negative_controls",
        [
            sys.executable,
            str(ROOT / "tools/validate_gap_node0071_runner_guard_chain.py"),
            "--source-zip", str(SOURCE_ZIP),
            "--target-zip", str(ZIP),
            "--output", str(RUNNER_REPORT),
        ],
        ROOT,
    )
    command_receipts.append(runner_receipt)
    runner_report = json.loads(RUNNER_REPORT.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(
        prefix=".g71-audit-", dir=ROOT, ignore_cleanup_errors=True
    ) as temporary:
        extraction = Path(temporary)
        with zipfile.ZipFile(ZIP) as archive:
            archive.extractall(extraction)
        package = extraction / ROOT_NAME
        before = tree_records(package)
        preflight_receipt, preflight_stdout = run_command(
            "fresh_extract_package_preflight",
            [
                sys.executable,
                str(
                    package
                    / "package_tools/gap_node0071_complete_server_runtime.py"
                ),
                "preflight", "--package-root", str(package),
            ],
            package,
        )
        command_receipts.append(preflight_receipt)
        self_receipt, self_stdout = run_command(
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
        syntax_receipt, _ = run_command(
            "fresh_extract_runner_bash_syntax",
            [
                r"C:\Program Files\Git\bin\bash.exe",
                "-n", str(package / "PREPARE_AND_RUN.sh"),
            ],
            package,
        )
        command_receipts.append(syntax_receipt)
        bootstrap_immutable = before == tree_records(package)
        if not bootstrap_immutable:
            errors.append("fresh extract preflight mutated package")
        preflight_report = json.loads(preflight_stdout)
        self_report = json.loads(self_stdout)

    canonical = validator_reports["canonical_validator_and_controls"]
    observer = validator_reports[
        "observer_four_way_validator_and_controls"
    ]
    dual = validator_reports["dual_ingress_validator_and_controls"]
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
        and runner_report["source_v9"]["full_runner_mock"]["exit_code"] == 7
        and not runner_report["source_v9"]["full_runner_mock"]["make_reached"]
        and runner_report["target_v10"]["full_runner_mock"]["exit_code"] == 86
        and runner_report["target_v10"]["full_runner_mock"]["make_reached"]
        and runner_report["target_v10"]["full_runner_mock"][
            "actual_compile_argv_exists"
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
        "schema": "gap-node0071-v10-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if passed else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "errors": errors,
        "error_count": len(errors),
        "zip": str(ZIP),
        "zip_size_bytes": ZIP.stat().st_size,
        "zip_sha256": zip_sha,
        "sidecar": str(SIDECAR),
        "sidecar_sha256": sha256_file(SIDECAR),
        "sidecar_content_exact": sidecar_exact,
        "zip_crc_valid": target_crc_bad is None,
        "manifest_exact_set_valid": exact_set,
        "manifest_current_match": manifest_current,
        "current_rule_receipts": current_receipts,
        "plan_sha256_mutable_provenance_only": (
            sha256_file(ROOT / ".agents/plan.md")
        ),
        "applicable_rule_ids": applicable,
        "source_v9": {
            "zip": str(SOURCE_ZIP),
            "sha256": sha256_file(SOURCE_ZIP),
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
        "runner_guard": {
            "expected_sha256": OBSERVER_SHA256,
            "actual_observer_sha256": sha256_bytes(
                target["tb_probe/native_return_observer.svh"]
            ),
            "static_binding_valid": runner_binding,
            "v9_mock_exit_code": runner_report[
                "source_v9"
            ]["full_runner_mock"]["exit_code"],
            "v9_mock_compile_reached": runner_report[
                "source_v9"
            ]["full_runner_mock"]["make_reached"],
            "v10_mock_exit_code": runner_report[
                "target_v10"
            ]["full_runner_mock"]["exit_code"],
            "v10_mock_compile_reached": runner_report[
                "target_v10"
            ]["full_runner_mock"]["make_reached"],
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
            name: receipt["stdout_sha256"]
            for name, receipt in (
                (item["name"], item) for item in command_receipts
            )
        },
        "runner_chain_report": str(RUNNER_REPORT),
        "runner_chain_report_sha256": sha256_file(RUNNER_REPORT),
        "numeric_analysis_repeated": False,
        "sum_tail_workload_reexecuted": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "package_release": {
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "server_command":
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
            "expected_return": [
                "r5_n71_gap_v10_runner_guard_return.zip",
                "r5_n71_gap_v10_runner_guard_return.zip.sha256",
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
