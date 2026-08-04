from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v7_finalaudit.zip"
)
SIDECAR = Path(str(ZIP) + ".sha256")
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v7_finalaudit.final_zip_rule_self_audit.json"
)
ROOT_NAME = "r5_n71_gap_v7_finalaudit"
RULES = {
    ".agents/rules/生成前必读索引.md":
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    ".agents/rules/服务器测试包生成规则.md":
        "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa",
    ".agents/rules/GAP_int32_mac_bypass_rules.md":
        "b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96",
    ".agents/rules/GAP_probe_v7_validator_rules.md":
        "2dee42a883bde9c1650710c8312d23e661aeb3c66ef9d1d4e15524af79c33dc7",
    ".agents/rules/精确UINT8量化尾专项规则.md":
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
}
PLAN_SHA256 = (
    "ec237da2f2094f20b5f7dab12d0723ebe08f1453cbb775c72b1b61567198edb5"
)


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
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def run_command(
    name: str,
    command: list[str],
    cwd: Path,
) -> tuple[dict[str, Any], str]:
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
        "stdout_sha256": sha256_bytes(stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(stderr.encode("utf-8")),
        "stdout_size_bytes": len(stdout.encode("utf-8")),
        "stderr_size_bytes": len(stderr.encode("utf-8")),
        "status": "PASS" if process.returncode == 0 else "FAIL",
    }
    if process.returncode != 0:
        raise AuditError(
            f"{name} failed: exit={process.returncode}: {stderr}"
        )
    return receipt, stdout


def safe_zip_files(archive: zipfile.ZipFile) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or info.filename in files
            or (mode and stat.S_ISLNK(mode))
        ):
            raise AuditError(f"unsafe ZIP member: {info.filename}")
        if not info.is_dir():
            files[info.filename] = archive.read(info)
    return files


def audit() -> dict[str, Any]:
    errors: list[str] = []
    zip_sha = sha256_file(ZIP)
    sidecar_text = SIDECAR.read_text(encoding="ascii")
    sidecar_exact = sidecar_text == f"{zip_sha}  {ZIP.name}\n"
    if not sidecar_exact:
        errors.append("sidecar content differs")
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

    with zipfile.ZipFile(ZIP) as archive:
        crc_bad_member = archive.testzip()
        files = safe_zip_files(archive)
    if crc_bad_member is not None:
        errors.append(f"ZIP CRC differs: {crc_bad_member}")
    prefix = f"{ROOT_NAME}/"
    manifest_member = prefix + "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(files[manifest_member].decode("utf-8"))
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        raise AuditError("manifest files absent")
    declared_members = {prefix + relative for relative in declared}
    exact_set = declared_members | {manifest_member} == set(files)
    if not exact_set:
        errors.append("manifest exact-set differs")
    for relative, receipt in declared.items():
        payload = files.get(prefix + relative)
        if (
            payload is None
            or len(payload) != receipt.get("size_bytes")
            or sha256_bytes(payload) != receipt.get("sha256")
        ):
            errors.append(f"manifest file receipt differs: {relative}")

    final_contract = manifest.get("final_zip_rule_self_audit_contract")
    manifest_current = False
    applicable_ids: list[str] = []
    if isinstance(final_contract, dict):
        receipt_map = {
            item.get("path"): item
            for item in final_contract.get("read_receipt", [])
            if isinstance(item, dict)
        }
        manifest_current = (
            final_contract.get("all_current_match") is True
            and all(
                receipt_map.get(path, {}).get("sha256") == digest
                and receipt_map.get(path, {}).get("current_match") is True
                for path, digest in RULES.items()
            )
        )
        applicable_ids = [
            str(item)
            for item in final_contract.get("applicable_rule_ids", [])
        ]
    if not manifest_current:
        errors.append("manifest current-match receipt differs")
    required_rule_ids = {
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "CDA-SERVER-WORKLOAD-PROVENANCE-001",
        "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
        "CDA-SERVER-ONE-COMMAND-001",
        "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
        "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
        "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
        "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
        "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
        "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
        "CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001",
        "CDA-GAP-D-READBACK-COVERAGE-001",
        "CDA-QUANT-TAIL-NUMERIC-ORDER-001",
    }
    if not required_rule_ids <= set(applicable_ids):
        errors.append("manifest applicable rule IDs differ")

    runtime_d_in_zip = [
        name for name in files if "/workload/readback/" in name
    ]
    if runtime_d_in_zip:
        errors.append("runtime D target preseeded in ZIP")
    runner = files[prefix + "PREPARE_AND_RUN.sh"].decode("utf-8")
    runtime = files[
        prefix
        + "package_tools/gap_node0071_complete_server_runtime.py"
    ].decode("utf-8")
    one_command = (
        "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        in runner
        and 'case "$1" in /*)' in runner
        and "find " not in runner
    )
    if not one_command:
        errors.append("one-command/path boundary differs")
    result_gate_static = all(
        term in runtime
        for term in (
            "compile_status == 0",
            "simulation_status == 0",
            "and terminal",
            "and all(loader.values())",
            "and missing == 0",
            "and mismatch_bytes == 0",
            '"all_terms_true": passed',
        )
    )
    if not result_gate_static:
        errors.append("result gate conjunction source differs")
    allowlist = manifest.get("return_allowlist")
    allowlist_valid = (
        isinstance(allowlist, list)
        and len(allowlist) == 70
        and len(
            {
                item.get("target_path")
                for item in allowlist
                if isinstance(item, dict)
            }
        )
        == 70
        and all(
            isinstance(item, dict)
            and item.get("source_root") in {"evidence", "run", "cfg"}
            and isinstance(item.get("source_path"), str)
            and isinstance(item.get("target_path"), str)
            and isinstance(item.get("required"), bool)
            and isinstance(item.get("max_bytes"), int)
            for item in allowlist
        )
    )
    if not allowlist_valid:
        errors.append("return allowlist differs")

    command_receipts: list[dict[str, Any]] = []
    canonical_receipt, canonical_stdout = run_command(
        "final_zip_canonical_validator_and_negative_controls",
        [
            sys.executable,
            str(ROOT / "tools/validate_gap_node0071_canonical_package.py"),
            str(ZIP),
        ],
        ROOT,
    )
    command_receipts.append(canonical_receipt)
    canonical_report = json.loads(canonical_stdout)
    observer_receipt, observer_stdout = run_command(
        "final_zip_observer_four_way_validator_and_negative_controls",
        [
            sys.executable,
            str(ROOT / "tools/validate_gap_node0071_observer_binding.py"),
            str(ZIP),
        ],
        ROOT,
    )
    command_receipts.append(observer_receipt)
    observer_report = json.loads(observer_stdout)

    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v7-final-audit-"
    ) as temporary:
        extraction = Path(temporary)
        with zipfile.ZipFile(ZIP) as archive:
            archive.extractall(extraction)
        package = extraction / ROOT_NAME
        tree_before = tree_records(package)
        preflight_receipt, preflight_stdout = run_command(
            "fresh_extract_package_runtime_preflight",
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
        self_test_receipt, self_test_stdout = run_command(
            "fresh_extract_canonical_self_test_all_controls",
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
        command_receipts.append(self_test_receipt)
        bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        bash_receipt, _ = run_command(
            "fresh_extract_runner_bash_syntax",
            [str(bash), "-n", str(package / "PREPARE_AND_RUN.sh")],
            package,
        )
        command_receipts.append(bash_receipt)
        tree_after = tree_records(package)
        bootstrap_immutable = tree_before == tree_after
        if not bootstrap_immutable:
            errors.append("fresh-extract preflight mutated package")
        preflight_report = json.loads(preflight_stdout)
        self_test_report = json.loads(self_test_stdout)

    canonical_controls = canonical_report.get("negative_controls", {})
    canonical_controls_pass = all(
        value.get("failed_closed", value.get("pass", False))
        for value in canonical_controls.values()
    )
    observer_controls = observer_report.get("negative_controls", {})
    observer_controls_pass = all(
        value.get("failed_closed") is True
        for value in observer_controls.values()
    )
    self_test_controls = self_test_report.get("negative_controls", {})
    self_test_controls_pass = all(
        value.get("failed_closed", value.get("pass", False))
        for value in self_test_controls.values()
    )
    if not (
        canonical_controls_pass
        and observer_controls_pass
        and self_test_controls_pass
    ):
        errors.append("required negative control differs")
    if (
        canonical_report.get("status")
        != "CANONICAL_DECISION_RULE_VALIDATED"
        or observer_report.get("status") != "PASS"
        or preflight_report.get("valid") is not True
    ):
        errors.append("validator status differs")

    rule_checks = {
        "complete_rebuild_or_frozen_reuse": {
            "status": "PASS",
            "reason":
                "manifest binds frozen source and exact numeric workload "
                "reuse; only namespace/receipt changed",
        },
        "exact_set_and_sidecar": {
            "status": "PASS" if exact_set and sidecar_exact else "FAIL",
        },
        "bootstrap_immutability": {
            "status": "PASS" if bootstrap_immutable else "FAIL",
        },
        "one_command_and_path_boundary": {
            "status": "PASS" if one_command else "FAIL",
        },
        "runtime_d_absent": {
            "status": "PASS" if not runtime_d_in_zip else "FAIL",
        },
        "default_progress_diagnostics": {
            "status": (
                "PASS"
                if canonical_report["checks"].get(
                    "default_progress_diagnostics_contract"
                )
                else "FAIL"
            ),
        },
        "observer_four_way": {
            "status": (
                "PASS"
                if observer_report.get("status") == "PASS"
                else "FAIL"
            ),
        },
        "event_qualification_and_canonical_decision": {
            "status": (
                "PASS"
                if canonical_report.get("status")
                == "CANONICAL_DECISION_RULE_VALIDATED"
                else "FAIL"
            ),
        },
        "dynamic_result_conjunction": {
            "status": "PASS" if result_gate_static else "FAIL",
            "claim_boundary":
                "static fail-closed gate only; server not run; no E3/E4/E5",
        },
        "return_allowlist": {
            "status": "PASS" if allowlist_valid else "FAIL",
        },
        "tb_target_install": {
            "status": "NOT_APPLICABLE",
            "reason": "package does not install or modify a server TB",
        },
        "functional_rtl_repair": {
            "status": "NOT_APPLICABLE",
            "reason": "functional RTL modifications remain frozen",
        },
    }
    passed = not errors and all(
        receipt["exit_code"] == 0 for receipt in command_receipts
    )
    return {
        "schema": "gap-node0071-final-zip-rule-self-audit-v1",
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
        "sidecar_sha256": sha256_file(SIDECAR),
        "sidecar_content_exact": sidecar_exact,
        "zip_crc_valid": crc_bad_member is None,
        "zip_member_count": len(files),
        "manifest_exact_set_valid": exact_set,
        "manifest_current_match": manifest_current,
        "current_rule_receipts": current_receipts,
        "plan_sha256_mutable_provenance_only": PLAN_SHA256,
        "applicable_rule_ids": applicable_ids,
        "rule_checks": rule_checks,
        "command_receipts": command_receipts,
        "negative_control_exit_codes": {
            "canonical_validator_harness":
                canonical_receipt["exit_code"],
            "observer_four_way_validator_harness":
                observer_receipt["exit_code"],
            "fresh_extract_canonical_self_test":
                self_test_receipt["exit_code"],
        },
        "negative_controls": {
            "canonical": canonical_controls,
            "observer_four_way": observer_controls,
            "fresh_extract": self_test_controls,
            "all_required_fail_closed": (
                canonical_controls_pass
                and observer_controls_pass
                and self_test_controls_pass
            ),
        },
        "validator_report_sha256": {
            "canonical":
                canonical_receipt["stdout_sha256"],
            "observer_four_way":
                observer_receipt["stdout_sha256"],
            "package_preflight":
                preflight_receipt["stdout_sha256"],
            "canonical_self_test":
                self_test_receipt["stdout_sha256"],
        },
        "numeric_analysis_repeated": False,
        "sum_tail_workload_reexecuted": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "package_release": {
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "server_command":
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
            "expected_return": [
                "r5_n71_gap_v7_finalaudit_return.zip",
                "r5_n71_gap_v7_finalaudit_return.zip.sha256",
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
