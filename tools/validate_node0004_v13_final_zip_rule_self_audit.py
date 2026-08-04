from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_final_zip_rule_self_audit_v11 as base  # noqa: E402


PLAN_SHA256 = (
    "e4beaa39dfd5bd3c247d546dc2fc431758e1038cbef806e7b5a8f5b49e09ac6a"
)


def _payloads(zip_path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        result: dict[str, bytes] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            pure = PurePosixPath(info.filename)
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            result[relative] = archive.read(info)
        return result


def _progress_expression(observer: str) -> str | None:
    matched = re.search(
        r"return_hang_diag_current_progress\s*=\s*(.*?);",
        observer,
        flags=re.DOTALL,
    )
    return matched.group(1) if matched else None


def _validate_abpe_texts(
    manifest_text: str, runner: str, observer: str
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_text)
    except json.JSONDecodeError as error:
        return False, [f"manifest parse failed: {error}"]
    contract = manifest.get("narrow_diagnostic_contract", {})
    if contract.get("record") != "ABPE_BOUNDARY_V1":
        errors.append("ABPE record contract missing")
    if contract.get("existing_monotonic_progress_unchanged") is not True:
        errors.append("qualified-progress noninterference contract missing")
    if contract.get("deep_mse0_enabled") is not True:
        errors.append("finite MSE0 deep trace contract missing")
    if observer.count("ABPE_BOUNDARY_V1") != 1:
        errors.append("ABPE boundary record must have one format definition")
    if observer.count('return_obs_write_abpe_state("DIAG_DECISION");') != 1:
        errors.append("ABPE record must be emitted once at canonical decision")
    for token in (
        "sa_pe_inport_valid_bit_masked[1:0]",
        ".sa_pe_cb2ob_alu_bp_pre",
        ".sa_pe_outbuffer_port",
        ".sa_pe_outport_bp_post",
    ):
        if token not in observer:
            errors.append(f"missing ABPE XMR boundary: {token}")
    if runner.count("+RETURN_OBS_ABPE") != 2:
        errors.append("ABPE plusarg must exist in receipt and actual simulator argv")
    if len(re.findall(r"\+RETURN_OBS_DEEP(?=\s)", runner)) != 2:
        errors.append("deep plusarg must exist in receipt and actual simulator argv")
    if runner.count("+RETURN_OBS_DEEP_LIMIT=256") != 2:
        errors.append("finite deep-event limit must exist in both argv forms")
    expression = _progress_expression(observer)
    if expression is None:
        errors.append("canonical qualified-progress expression missing")
    elif "abpe" in expression.lower():
        errors.append("ABPE diagnostic levels/counters entered monotonic progress")
    return not errors, errors


def _negative_controls(
    manifest_text: str, runner: str, observer: str
) -> dict[str, Any]:
    cases = {
        "missing_abpe_record": (
            manifest_text,
            runner,
            observer.replace("ABPE_BOUNDARY_V1", "ABPE_BOUNDARY_REMOVED"),
        ),
        "missing_abpe_runtime_binding": (
            manifest_text,
            runner.replace("+RETURN_OBS_ABPE", ""),
            observer,
        ),
        "missing_deep_runtime_binding": (
            manifest_text,
            runner.replace("+RETURN_OBS_DEEP ", ""),
            observer,
        ),
        "abpe_level_injected_into_progress": (
            manifest_text,
            runner,
            observer.replace(
                "return_hang_diag_current_progress =",
                "return_hang_diag_current_progress = "
                "return_obs_abpe_alu_accept_count +",
                1,
            ),
        ),
    }
    result: dict[str, Any] = {}
    for name, texts in cases.items():
        valid, errors = _validate_abpe_texts(*texts)
        result[name] = {"failed_closed": not valid, "errors": errors}
    result["all_failed_closed"] = all(
        item["failed_closed"]
        for name, item in result.items()
        if name != "all_failed_closed"
    )
    return result


def audit(
    project_root: Path,
    zip_path: Path,
    sidecar: Path,
    python: Path,
    builder: Path,
) -> dict[str, Any]:
    base.PLAN_SHA256 = PLAN_SHA256
    report = base.audit(
        project_root, zip_path, sidecar, python, builder
    )
    payloads = _payloads(zip_path)
    manifest_text = payloads["package_manifest.json"].decode("utf-8")
    runner = payloads["PREPARE_AND_RUN.sh"].decode("utf-8")
    observer = payloads["tb_probe/native_return_observer.svh"].decode("utf-8")
    valid, errors = _validate_abpe_texts(manifest_text, runner, observer)
    negatives = _negative_controls(manifest_text, runner, observer)
    report["schema"] = "node0004-v13-final-zip-rule-self-audit-v1"
    report["abpe_boundary"] = {
        "valid": valid,
        "errors": errors,
        "negative_controls": negatives,
    }
    if not valid:
        report["errors"].extend(f"ABPE: {item}" for item in errors)
    if not negatives["all_failed_closed"]:
        report["errors"].append("ABPE negative control did not fail closed")
    report["error_count"] = len(report["errors"])
    report["all_required_negative_controls_fail_closed"] = (
        report["all_required_negative_controls_fail_closed"]
        and negatives["all_failed_closed"]
    )
    report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = (
        report["error_count"] == 0
        and report["all_required_negative_controls_fail_closed"]
    )
    report["status"] = (
        "PACKAGE_READY_NOT_RUN"
        if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]
        else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.python.resolve(),
        args.builder.resolve(),
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
