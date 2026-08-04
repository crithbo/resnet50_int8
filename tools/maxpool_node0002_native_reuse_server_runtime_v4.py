#!/usr/bin/env python3
"""Current-rule runtime gate for the exact-native MaxPool node0002 package."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import maxpool_node0002_original_json_server_runtime as base  # noqa: E402


MANIFEST = "TEST_PACKAGE_MANIFEST.json"
CANONICAL_PREFIX = "| CANONICAL_MAXPOOL_DIAG_DECISION_V1 |"


class MaxPoolNativeReuseRuntimeError(base.MaxPoolRuntimeError):
    pass


def _manifest(package_root: Path) -> dict[str, Any]:
    return base.load_json(package_root.resolve() / MANIFEST)


def manifest_value(package_root: Path, key: str) -> str:
    value: Any = _manifest(package_root)
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise MaxPoolNativeReuseRuntimeError(f"manifest key missing: {key}")
        value = value[part]
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise MaxPoolNativeReuseRuntimeError(f"manifest value invalid: {key}")
    return value


def _parse_fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))


def parse_canonical(lines: list[str]) -> dict[str, Any]:
    candidates = [line for line in lines if CANONICAL_PREFIX in line]
    errors: list[str] = []
    record: dict[str, Any] | None = None
    required = {
        "schema",
        "version",
        "decision",
        "reason",
        "boundary",
        "slice",
        "window_cycles",
        "zero_windows",
        "qualified_progress",
        "qualified_delta",
        "req",
        "rdata",
        "wdata",
        "p0_capture",
        "ga_output",
        "finish",
        "content_digest",
    }
    if len(candidates) != 1:
        errors.append(f"canonical candidate count differs: {len(candidates)}")
    if candidates:
        fields = _parse_fields(candidates[0].split(CANONICAL_PREFIX, 1)[1])
        missing = sorted(required - set(fields))
        if missing:
            errors.append(f"canonical fields missing: {missing}")
        else:
            try:
                numeric = {
                    name: int(fields[name])
                    for name in (
                        "version",
                        "slice",
                        "window_cycles",
                        "zero_windows",
                        "qualified_progress",
                        "qualified_delta",
                        "req",
                        "rdata",
                        "wdata",
                        "p0_capture",
                        "ga_output",
                        "finish",
                    )
                }
            except ValueError:
                numeric = {}
                errors.append("canonical numeric field invalid")
            if numeric:
                total = sum(
                    numeric[name]
                    for name in (
                        "req",
                        "rdata",
                        "wdata",
                        "p0_capture",
                        "ga_output",
                        "finish",
                    )
                )
                if fields["schema"] != "maxpool_node0002_diag" or numeric["version"] != 1:
                    errors.append("canonical schema/version differs")
                if numeric["slice"] not in (0, 1):
                    errors.append("canonical slice differs")
                if numeric["window_cycles"] <= 0 or numeric["zero_windows"] < 4:
                    errors.append("canonical stall window differs")
                if total != numeric["qualified_progress"]:
                    errors.append("canonical qualified progress sum differs")
                if numeric["qualified_delta"] != 0:
                    errors.append("canonical stall delta is not zero")
                expected_decision = f"LONG_RUNNING_HANG_AT_{fields['boundary']}"
                if (
                    fields["reason"] != "STALL_WINDOW_EXCEEDED"
                    or fields["decision"] != expected_decision
                ):
                    errors.append("canonical decision/reason differs")
                expected_digest = (
                    f"MPQV1_{numeric['qualified_progress']}_"
                    f"{numeric['qualified_delta']}_{numeric['slice']}"
                )
                if fields["content_digest"] != expected_digest:
                    errors.append("canonical digest differs")
                record = {
                    "line": candidates[0],
                    "fields": fields,
                    "numeric": numeric,
                }
    return {
        "valid": len(candidates) == 1 and record is not None and not errors,
        "candidate_count": len(candidates),
        "errors": errors,
        "record": record if not errors else None,
    }


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    root = package_root.resolve()
    manifest = _manifest(root)
    if manifest.get("install_name") != install_name:
        raise MaxPoolNativeReuseRuntimeError("install identity differs")
    observed = base.file_records(root, exclude_manifest=True)
    expected = manifest.get("files")
    if expected != observed:
        expected = expected if isinstance(expected, dict) else {}
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        changed = sorted(
            name
            for name in set(expected) & set(observed)
            if expected[name] != observed[name]
        )
        raise MaxPoolNativeReuseRuntimeError(
            f"package exact-set differs: missing={missing[:3]} "
            f"extra={extra[:3]} changed={changed[:3]}"
        )
    claims = {
        "status": "PACKAGE_READY_NOT_RUN",
        "reuse_class": "EXACT_FULL_OPERATOR",
        "candidate_release": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_source_preflight_performed": False,
        "numeric_analysis_repeated": False,
    }
    for key, expected_value in claims.items():
        if manifest.get(key) != expected_value:
            raise MaxPoolNativeReuseRuntimeError(f"package claim differs: {key}")
    observer = manifest.get("observer_binding_four_way")
    if not isinstance(observer, dict):
        raise MaxPoolNativeReuseRuntimeError("observer binding contract missing")
    source = base.inside(root, str(observer.get("source_path", "")))
    if (
        not source.is_file()
        or base.sha256(source) != observer.get("source_sha256")
        or source.stat().st_size != observer.get("source_size_bytes")
        or observer.get("include_option")
        != "+incdir+$package_root/tb_probe"
        or observer.get("compile_enable")
        != "+define+NATIVE_RETURN_OBSERVER_ENABLE"
        or observer.get("runtime_enable") != "+RETURN_OBSERVER"
    ):
        raise MaxPoolNativeReuseRuntimeError("observer four-way binding differs")
    progress = manifest.get("progress_diagnostics")
    if (
        not isinstance(progress, dict)
        or progress.get("enabled_by_default") is not True
        or progress.get("read_only") is not True
        or progress.get("low_volume") is not True
        or progress.get("canonical_prefix") != CANONICAL_PREFIX.strip()
        or int(progress.get("sample_cycles", 0)) <= 0
        or int(progress.get("stall_windows", 0)) < 4
    ):
        raise MaxPoolNativeReuseRuntimeError("progress diagnostics contract differs")
    allowlist = manifest.get("return_allowlist")
    if not isinstance(allowlist, list) or not allowlist:
        raise MaxPoolNativeReuseRuntimeError("return allowlist missing")
    targets: set[str] = set()
    for item in allowlist:
        if (
            not isinstance(item, dict)
            or item.get("source_root") not in {"package", "evidence", "run", "cfg"}
            or not isinstance(item.get("required"), bool)
            or not isinstance(item.get("max_bytes"), int)
            or int(item["max_bytes"]) <= 0
        ):
            raise MaxPoolNativeReuseRuntimeError("return allowlist record differs")
        target = str(item.get("target_path", ""))
        base.safe_relative(target)
        if target in targets:
            raise MaxPoolNativeReuseRuntimeError("return target duplicated")
        targets.add(target)
    base_report = base.preflight_package(root, install_name)
    return {
        "schema": "maxpool-node0002-native-reuse-package-preflight-v4",
        "valid": True,
        "package_exact_file_set_check_performed": True,
        "package_tree_immutable": True,
        "file_count": len(observed),
        "return_allowlist_count": len(allowlist),
        "server_source_files_inspected": False,
        "base_payload": base_report,
    }


def preflight_installed(
    package_root: Path, server_root: Path, install_name: str
) -> dict[str, Any]:
    package_report = preflight_package(package_root, install_name)
    cfg_root = server_root.resolve() / "install" / "cfg_pkg" / install_name
    base_report = base.preflight_installed(package_root, server_root, install_name)
    source = base.file_records(package_root.resolve() / "workload/runtime")
    installed = base.file_records(cfg_root)
    if source != installed:
        raise MaxPoolNativeReuseRuntimeError("installed workload exact-set differs")
    return {
        "schema": "maxpool-node0002-native-reuse-installed-preflight-v4",
        "valid": True,
        "package_preflight": package_report,
        "base_payload": base_report,
        "installed_exact_file_set_check_performed": True,
        "installed_file_count": len(installed),
        "formal_readback_targets_absent": True,
        "server_source_files_inspected": False,
    }


def analyze(
    server_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    compile_status: int,
    sim_status: int,
) -> dict[str, Any]:
    root = server_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    base_report = base.analyze(
        root,
        package,
        install_name,
        evidence,
        run,
        compile_status,
        sim_status,
    )
    observer_path = run / "sim_results/return_observer.log"
    lines = (
        observer_path.read_text(encoding="utf-8", errors="replace").splitlines()
        if observer_path.is_file()
        else []
    )
    time0 = [line for line in lines if "[MAXPOOL_RETURN_OBSERVER] enabled" in line]
    windows = [line for line in lines if "| MAXPOOL_PROGRESS_WINDOW_V1 |" in line]
    stage_finishes = [line for line in lines if "| MAXPOOL_STAGE_FINISH_V1 |" in line]
    canonical = parse_canonical(lines)
    actual_compile = evidence / "actual_compile_argv.txt"
    actual_sim = run / "sim_results/simulator_argv.txt"
    compile_text = (
        actual_compile.read_text(encoding="utf-8", errors="replace")
        if actual_compile.is_file()
        else ""
    )
    sim_text = (
        actual_sim.read_text(encoding="utf-8", errors="replace")
        if actual_sim.is_file()
        else ""
    )
    binding = {
        "schema": "maxpool-node0002-observer-binding-v4",
        "valid": (
            "+incdir+" in compile_text
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_text
            and "+RETURN_OBSERVER" in sim_text
            and len(time0) == 1
            and observer_path.is_file()
        ),
        "compile_include_present": "+incdir+" in compile_text,
        "compile_enable_present": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_text,
        "runtime_enable_present": "+RETURN_OBSERVER" in sim_text,
        "time0_marker_count": len(time0),
        "observer_returned": observer_path.is_file(),
    }
    base.write_json(evidence / "observer_binding.json", binding)
    if canonical["valid"]:
        decision = canonical["record"]
    elif len(stage_finishes) == 2:
        decision = {
            "fields": {
                "decision": "MAXPOOL_TWO_STAGE_PROGRESS_COMPLETE",
                "reason": "BOTH_STAGE_FINISH_WITNESSES",
                "boundary": "NATURAL_TERMINAL_PENDING_TB_CONFIRMATION",
            }
        }
    else:
        decision = {
            "fields": {
                "decision": "EVIDENCE_INSUFFICIENT",
                "reason": "NO_CANONICAL_DECISION_BEFORE_EXIT",
                "boundary": "LAST_RETURNED_PROGRESS_WINDOW",
            }
        }
    base.write_json(evidence / "CANONICAL_PROGRESS_DECISION.json", decision)
    readback = base_report["formal_readback"]
    conjunction = {
        "compile_exit_zero": compile_status == 0,
        "simulation_exit_zero": sim_status == 0,
        "natural_completion": bool(base_report["natural_completion_marker"]),
        "observer_binding_valid": binding["valid"],
        "formal_readback_complete": bool(readback["all_readbacks_present"])
        and bool(readback["all_readbacks_format_valid"]),
        "mismatch_zero": readback["total_byte_mismatch_count"] == 0,
    }
    conjunction["all_terms_true"] = all(conjunction.values())
    if conjunction["all_terms_true"]:
        status = "MAXPOOL_NODE0002_DYNAMIC_PASS_VERSION_UNBOUND"
    elif canonical["valid"]:
        status = canonical["record"]["fields"]["decision"]
    elif compile_status != 0:
        status = "SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE"
    else:
        status = "MAXPOOL_NODE0002_DYNAMIC_FAILURE_EVIDENCE_INSUFFICIENT"
    report = {
        **base_report,
        "schema": "maxpool-node0002-native-reuse-result-v4",
        "status": status,
        "result_gate_conjunction": conjunction,
        "observer_binding": binding,
        "progress_window_count": len(windows),
        "last_progress_window": windows[-1] if windows else None,
        "stage_finish_witness_count": len(stage_finishes),
        "canonical_validation": canonical,
        "canonical_decision": decision,
        "numeric_analysis_repeated": False,
        "counts_as_e4": False,
        "counts_as_e5": False,
    }
    base.write_json(evidence / "SERVER_RESULT_GATE.json", report)
    return report


def collect(
    server_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = server_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    cfg = root / "install" / "cfg_pkg" / install_name
    destination = root / f"{install_name}_return"
    archive_path = root / f"{install_name}_return.zip"
    sidecar = Path(str(archive_path) + ".sha256")
    if destination.exists() or archive_path.exists() or sidecar.exists():
        raise MaxPoolNativeReuseRuntimeError("return namespace must be fresh")
    destination.mkdir()
    roots = {"package": package, "evidence": evidence, "run": run, "cfg": cfg}
    manifest = _manifest(package)
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in manifest["return_allowlist"]:
        source = base.inside(roots[str(item["source_root"])], str(item["source_path"]))
        target = base.inside(destination, str(item["target_path"]))
        if not source.is_file() or source.is_symlink():
            if item["required"]:
                missing.append(str(item["target_path"]))
            continue
        if source.stat().st_size > int(item["max_bytes"]):
            raise MaxPoolNativeReuseRuntimeError(f"return file exceeds budget: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records.append(
            {
                "path": str(item["target_path"]),
                "size_bytes": target.stat().st_size,
                "sha256": base.sha256(target),
            }
        )
    return_manifest = {
        "schema": "maxpool-node0002-native-reuse-return-manifest-v4",
        "status": "complete" if not missing else "incomplete",
        "install_name": install_name,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "required_missing": missing,
        "files": records,
    }
    base.write_json(destination / "RETURN_MANIFEST.json", return_manifest)
    observed = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and path.name != "RETURN_MANIFEST.json"
    }
    if observed != {str(item["path"]) for item in records}:
        raise MaxPoolNativeReuseRuntimeError("return exact-set differs")
    extracted = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
    budget = int(manifest["budgets"]["return_extracted_max_bytes"])
    if extracted > budget:
        raise MaxPoolNativeReuseRuntimeError("return extracted budget exceeded")
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in destination.rglob("*") if item.is_file()):
            relative = f"{destination.name}/{path.relative_to(destination).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    if archive_path.stat().st_size > int(manifest["budgets"]["return_zip_max_bytes"]):
        raise MaxPoolNativeReuseRuntimeError("return ZIP budget exceeded")
    digest = base.sha256(archive_path)
    sidecar.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii", newline="\n")
    return {
        "zip": str(archive_path),
        "zip_sha256": digest,
        "required_missing": missing,
        "return_manifest": return_manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    value_parser = sub.add_parser("manifest-value")
    value_parser.add_argument("--package-root", type=Path, required=True)
    value_parser.add_argument("--key", required=True)
    package_parser = sub.add_parser("preflight-package")
    package_parser.add_argument("--package-root", type=Path, required=True)
    package_parser.add_argument("--install-name", required=True)
    package_parser.add_argument("--output", type=Path, required=True)
    installed_parser = sub.add_parser("preflight-installed")
    installed_parser.add_argument("--package-root", type=Path, required=True)
    installed_parser.add_argument("--server-root", type=Path, required=True)
    installed_parser.add_argument("--install-name", required=True)
    installed_parser.add_argument("--output", type=Path, required=True)
    analysis_parser = sub.add_parser("analyze")
    analysis_parser.add_argument("--server-root", type=Path, required=True)
    analysis_parser.add_argument("--package-root", type=Path, required=True)
    analysis_parser.add_argument("--install-name", required=True)
    analysis_parser.add_argument("--evidence-root", type=Path, required=True)
    analysis_parser.add_argument("--run-dir", type=Path, required=True)
    analysis_parser.add_argument("--compile-status", type=int, required=True)
    analysis_parser.add_argument("--sim-status", type=int, required=True)
    analysis_parser.add_argument("--output", type=Path, required=True)
    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--server-root", type=Path, required=True)
    collect_parser.add_argument("--package-root", type=Path, required=True)
    collect_parser.add_argument("--install-name", required=True)
    collect_parser.add_argument("--evidence-root", type=Path, required=True)
    collect_parser.add_argument("--run-dir", type=Path, required=True)
    collect_parser.add_argument("--run-status", type=int, required=True)
    collect_parser.add_argument("--server-command", required=True)
    args = parser.parse_args()
    try:
        if args.command == "manifest-value":
            print(manifest_value(args.package_root, args.key))
            return 0
        if args.command == "preflight-package":
            value = preflight_package(args.package_root, args.install_name)
            base.write_json(args.output, value)
        elif args.command == "preflight-installed":
            value = preflight_installed(
                args.package_root, args.server_root, args.install_name
            )
            base.write_json(args.output, value)
        elif args.command == "analyze":
            value = analyze(
                args.server_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.compile_status,
                args.sim_status,
            )
        else:
            value = collect(
                args.server_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.run_status,
                args.server_command,
            )
        print(json.dumps(value, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"MaxPool native-reuse runtime failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
