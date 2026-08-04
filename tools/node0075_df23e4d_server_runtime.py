#!/usr/bin/env python3
"""Package-local preflight, result gate, and allowlist return collector for node0075."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

sys.dont_write_bytecode = True

MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
BITS128 = re.compile(rb"[01]{128}")
SUMMARY_RE = re.compile(
    r"FINAL_SUMMARY .*cfg_start=(\d+) cfg_finish=(\d+) exec=(\d+) "
    r"finish=(\d+) a_req=(\d+) a_data=(\d+) d_write=(\d+)"
)


class RuntimeErrorN75(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeErrorN75(f"cannot parse JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeErrorN75(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_relative(raw: str, label: str) -> PurePosixPath:
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        not raw
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.anchor)
        or "\\" in raw
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise RuntimeErrorN75(f"unsafe {label}: {raw!r}")
    return posix


def resolve_inside(root: Path, raw: str, label: str) -> Path:
    relative = safe_relative(raw, label)
    target = root.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeErrorN75(f"{label} escapes root: {raw}") from exc
    return target


def file_records(root: Path, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    excluded = exclude or set()
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeErrorN75(f"symlink forbidden: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        records.append(
            {"path": relative, "size_bytes": path.stat().st_size, "sha256": sha256(path)}
        )
    return records


def _record_map(records: Any, label: str) -> dict[str, tuple[int, str]]:
    if not isinstance(records, list):
        raise RuntimeErrorN75(f"{label} is not a list")
    result: dict[str, tuple[int, str]] = {}
    for item in records:
        if not isinstance(item, dict):
            raise RuntimeErrorN75(f"{label} record is not an object")
        raw = str(item.get("path", ""))
        safe_relative(raw, f"{label} path")
        size = item.get("size_bytes")
        digest = str(item.get("sha256", ""))
        if raw in result or not isinstance(size, int) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeErrorN75(f"invalid {label} record: {raw}")
        result[raw] = (size, digest)
    return result


def _validate_records(root: Path, records: Any, label: str, extra: set[str] | None = None) -> None:
    expected = _record_map(records, label)
    actual = {
        item["path"]: (item["size_bytes"], item["sha256"])
        for item in file_records(root, exclude=extra)
    }
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        differing = sorted(path for path in set(actual) & set(expected) if actual[path] != expected[path])
        raise RuntimeErrorN75(
            f"{label} exact tree differs: missing={missing[:4]} unexpected={unexpected[:4]} "
            f"differing={differing[:4]}"
        )


def _validate_128bit_text(path: Path, expected_lines: int | None = None) -> int:
    count = 0
    with path.open("rb") as stream:
        for count, raw in enumerate(stream, 1):
            if not raw.endswith(b"\n") or not BITS128.fullmatch(raw[:-1]):
                raise RuntimeErrorN75(f"invalid 128-bit text ABI: {path}:{count}")
    if count == 0 or (expected_lines is not None and count != expected_lines):
        raise RuntimeErrorN75(f"128-bit line count differs: {path}: {count}")
    return count


def preflight(package_root: Path) -> dict[str, Any]:
    package_root = package_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    if (
        manifest.get("status") != "PACKAGE_READY_NOT_RUN"
        or manifest.get("candidate_release") is not False
        or manifest.get("functional_rtl_modified") is not False
        or manifest.get("functional_rtl_file_count") != 0
    ):
        raise RuntimeErrorN75("package release boundary differs")
    _validate_records(package_root, manifest.get("files"), "package files", {MANIFEST_NAME})
    if any(path.name in {"__pycache__"} or path.suffix == ".pyc" for path in package_root.rglob("*")):
        raise RuntimeErrorN75("Python bytecode forbidden in package")
    runner = (package_root / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    required_runner_tokens = [
        "export PYTHONDONTWRITEBYTECODE=1",
        "+SCA_CFG=$cfg_rel/sca_cfg.json",
        "+SCA_CFG_D=$cfg_rel/sca_cfg_D.json",
        "+RETURN_OBSERVER",
        "+RETURN_OBS_EVENT_LIMIT=256",
        "+incdir+$package_root/tb_probe",
    ]
    if not all(token in runner for token in required_runner_tokens):
        raise RuntimeErrorN75("runner binding token missing")
    forbidden_preflight = ["rtl/filelists", "tb_NDP_Top_new_phy.sv", "git rev-parse", "README_HARDWARE"]
    if any(token in runner for token in forbidden_preflight):
        raise RuntimeErrorN75("runner performs forbidden server-source preflight")

    workload = package_root / "workload"
    _validate_records(workload, manifest.get("workload_files"), "workload files")
    sca = load_json(workload / "sca_cfg.json")
    sca_d = load_json(workload / "sca_cfg_D.json")
    if sca.get("Repeat_Num") != 24 or not isinstance(sca.get("Exec_Length"), int):
        raise RuntimeErrorN75("SCA execution counts differ")
    b_items = {key: value for key, value in sca.items() if "_matrixB_" in key}
    config_items = {key: value for key, value in sca.items() if key.endswith("_config")}
    if len(b_items) != 128 or len(config_items) != 24 or len(sca_d) != 128:
        raise RuntimeErrorN75("SCA exact transfer counts differ")
    for key, item in {**b_items, **config_items, "ExecutionPlan": sca["ExecutionPlan"]}.items():
        path = resolve_inside(package_root.parent.parent.parent, str(item["path"]), f"SCA path {key}")
        # Package preflight validates the corresponding workload-relative file,
        # while installed-path resolution is checked after fresh installation.
        relative = PurePosixPath(str(item["path"]))
        marker = ("install", "cfg_pkg", str(manifest["install_name"]))
        if tuple(relative.parts[:3]) != marker:
            raise RuntimeErrorN75(f"SCA path namespace differs: {item['path']}")
        package_file = workload.joinpath(*relative.parts[3:])
        if not package_file.is_file():
            raise RuntimeErrorN75(f"SCA package payload missing: {package_file}")
        if "_matrixB_" in key:
            _validate_128bit_text(package_file, 16384)
    for key, item in sca_d.items():
        if set(item) != {"base_addr", "length", "path"} or item["length"] != 8:
            raise RuntimeErrorN75(f"SCA_D leaf differs: {key}")
        raw = str(item["path"])
        if not raw.startswith(f"sim_results/{manifest['run_namespace']}/formal_d/"):
            raise RuntimeErrorN75(f"SCA_D runtime namespace differs: {raw}")
        if (package_root / raw).exists():
            raise RuntimeErrorN75("runtime D target is preseeded in package")
    checks = manifest.get("readback_checks")
    if not isinstance(checks, list) or len(checks) != 128:
        raise RuntimeErrorN75("formal readback contract count differs")
    for item in checks:
        golden = resolve_inside(package_root, str(item["golden_path"]), "golden path")
        if golden.stat().st_size != item["size_bytes"] or sha256(golden) != item["sha256"]:
            raise RuntimeErrorN75("golden identity differs")
        _validate_128bit_text(golden, 8)
    return {
        "status": "PACKAGE_PREFLIGHT_PASS",
        "package_root": str(package_root),
        "package_manifest_sha256": sha256(package_root / MANIFEST_NAME),
        "package_file_count": len(manifest["files"]) + 1,
        "workload_file_count": len(manifest["workload_files"]),
        "b_preload_count": 128,
        "config_preload_count": 24,
        "formal_readback_count": 128,
        "runtime_d_absent": True,
    }


def verify_install(package_root: Path, cfg_root: Path) -> dict[str, Any]:
    package_root = package_root.resolve()
    cfg_root = cfg_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    _validate_records(cfg_root, manifest.get("workload_files"), "installed workload")
    sca = load_json(cfg_root / "sca_cfg.json")
    for key, item in sca.items():
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        expected = resolve_inside(cfg_root, str(PurePosixPath(item["path"]).relative_to("install", "cfg_pkg", manifest["install_name"])), f"installed SCA {key}")
        if not expected.is_file():
            raise RuntimeErrorN75(f"installed SCA payload missing: {expected}")
    return {
        "status": "INSTALLED_WORKLOAD_PREFLIGHT_PASS",
        "cfg_root": str(cfg_root),
        "installed_file_count": len(manifest["workload_files"]),
        "installed_exact_tree": True,
    }


def prepare_run(package_root: Path, server_root: Path, run_root: Path) -> dict[str, Any]:
    package_root = package_root.resolve()
    server_root = server_root.resolve()
    run_root = run_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    targets: list[str] = []
    for item in manifest["readback_checks"]:
        target = resolve_inside(server_root, str(item["runtime_path"]), "runtime D")
        try:
            target.relative_to(run_root)
        except ValueError as exc:
            raise RuntimeErrorN75("runtime D target escapes run root") from exc
        if target.exists():
            raise RuntimeErrorN75(f"runtime D target is preseeded: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        targets.append(str(target))
    return {
        "status": "RUNTIME_D_ABSENT_PRE_SIM_PASS",
        "target_count": len(targets),
        "all_absent": True,
        "targets_sha256": hashlib.sha256(
            json.dumps(targets, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def _status(path: Path) -> int:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except Exception:
        return 125


def analyze(package_root: Path, server_root: Path, run_root: Path, evidence_root: Path) -> dict[str, Any]:
    package_root = package_root.resolve()
    server_root = server_root.resolve()
    run_root = run_root.resolve()
    evidence_root = evidence_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    compile_status = _status(evidence_root / "compile_exit_status.txt")
    run_status = _status(evidence_root / "run_exit_status.txt")
    signal = (evidence_root / "signal_status.txt").read_text(encoding="ascii").strip() if (evidence_root / "signal_status.txt").is_file() else "MISSING"
    sim_log_path = run_root / "sim.log"
    observer_path = run_root / "return_observer.log"
    sim_log = sim_log_path.read_text(encoding="utf-8", errors="replace") if sim_log_path.is_file() else ""
    observer = observer_path.read_text(encoding="utf-8", errors="replace") if observer_path.is_file() else ""
    cfg_rel = f"install/cfg_pkg/{manifest['install_name']}"
    marker_checks = {
        "sca_echo": f"Using SCA cfg file: {cfg_rel}/sca_cfg.json" in sim_log,
        "sca_d_echo": f"Using SCA cfg D file: {cfg_rel}/sca_cfg_D.json" in sim_log,
        "natural_terminal": "Simulation completed successfully!" in sim_log,
        "formal_dump_count": bool(re.search(r"JSON_D config:\s*128 matrices dumped", sim_log)),
        "no_timeout": "Simulation aborted due to timeout!" not in sim_log,
        "no_sca_open_failure": "Cannot open" not in sim_log and "skip matrix readback" not in sim_log,
        "observer_enabled": "N75_FEATURE_ENABLE_V1 feature=NODE0075_PROGRESS enabled=1" in observer,
        "observer_canonical": "N75_CANONICAL_DECISION_V1 decision=EXPECTED_24_STAGE_PREFIX_COMPLETE" in observer,
    }
    summary_matches = list(SUMMARY_RE.finditer(observer))
    summary = None
    if summary_matches:
        values = [int(value) for value in summary_matches[-1].groups()]
        summary = dict(zip(("cfg_start", "cfg_finish", "exec", "finish", "a_req", "a_data", "d_write"), values))
    observer_stage_gate = bool(summary and summary["exec"] == 24 and summary["finish"] == 24)

    missing: list[str] = []
    mismatches: list[str] = []
    actual_records: list[dict[str, Any]] = []
    for item in manifest["readback_checks"]:
        runtime_path = resolve_inside(server_root, str(item["runtime_path"]), "runtime D")
        golden = resolve_inside(package_root, str(item["golden_path"]), "golden")
        if not runtime_path.is_file():
            missing.append(str(item["runtime_path"]))
            continue
        try:
            lines = _validate_128bit_text(runtime_path, int(item["line_count_128bit"]))
        except RuntimeErrorN75:
            mismatches.append(str(item["runtime_path"]) + ":ABI")
            continue
        actual_sha = sha256(runtime_path)
        if runtime_path.read_bytes() != golden.read_bytes():
            mismatches.append(str(item["runtime_path"]))
        actual_records.append(
            {
                "runtime_path": str(item["runtime_path"]),
                "size_bytes": runtime_path.stat().st_size,
                "sha256": actual_sha,
                "line_count_128bit": lines,
            }
        )
    conjunction = (
        compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and all(marker_checks.values())
        and observer_stage_gate
        and not missing
        and not mismatches
        and len(actual_records) == 128
    )
    result = {
        "schema": "node0075-df23e4d-server-result-gate-v1",
        "status": "SERVER_DYNAMIC_PASS" if conjunction else "SERVER_DYNAMIC_FAIL_OR_INCOMPLETE",
        "passed": conjunction,
        "candidate_release": False,
        "compile_exit_status": compile_status,
        "run_exit_status": run_status,
        "signal_status": signal,
        "marker_checks": marker_checks,
        "observer_summary": summary,
        "observer_24_stage_gate": observer_stage_gate,
        "formal_readback_expected_count": 128,
        "formal_readback_actual_count": len(actual_records),
        "missing_count": len(missing),
        "mismatch_count": len(mismatches),
        "missing": missing,
        "mismatches": mismatches,
        "actual_readbacks": actual_records,
        "server_source_identity_bound": False,
        "evidence_level_if_passed": "DYNAMIC_DIAGNOSTIC_ONLY_NO_SERVER_SOURCE_IDENTITY",
        "result_gate_conjunction": conjunction,
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", result)
    return result


def _copy_limited(source: Path, target: Path, limit: int) -> bool:
    if not source.is_file():
        return False
    payload = source.read_bytes()
    if len(payload) > limit:
        half = limit // 2
        payload = payload[:half] + b"\n...TRUNCATED_HEAD_TAIL...\n" + payload[-half:]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return True


def _deterministic_zip(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = f"{root.name}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def collect(package_root: Path, server_root: Path, run_root: Path, evidence_root: Path) -> dict[str, Any]:
    package_root = package_root.resolve()
    server_root = server_root.resolve()
    run_root = run_root.resolve()
    evidence_root = evidence_root.resolve()
    manifest = load_json(package_root / MANIFEST_NAME)
    return_root = server_root / str(manifest["return_directory"])
    return_zip = server_root / str(manifest["return_zip"])
    sidecar = Path(str(return_zip) + ".sha256")
    if return_root.exists() or return_zip.exists() or sidecar.exists():
        raise RuntimeErrorN75("return namespace must be fresh")
    return_root.mkdir(parents=True)

    copied: list[str] = []
    required_sources = {
        "evidence/package_preflight.json": evidence_root / "package_preflight.json",
        "evidence/install_preflight.json": evidence_root / "install_preflight.json",
        "evidence/runtime_d_absent.json": evidence_root / "runtime_d_absent.json",
        "evidence/compile_exit_status.txt": evidence_root / "compile_exit_status.txt",
        "evidence/run_exit_status.txt": evidence_root / "run_exit_status.txt",
        "evidence/signal_status.txt": evidence_root / "signal_status.txt",
        "evidence/compile_argv.txt": evidence_root / "compile_argv.txt",
        "evidence/simulator_argv.txt": evidence_root / "simulator_argv.txt",
        "evidence/SERVER_RESULT_GATE.json": evidence_root / "SERVER_RESULT_GATE.json",
        "source_package/TEST_PACKAGE_MANIFEST.json": package_root / MANIFEST_NAME,
        "source_package/sca_cfg.json": package_root / "workload/sca_cfg.json",
        "source_package/sca_cfg_D.json": package_root / "workload/sca_cfg_D.json",
    }
    for relative, source in required_sources.items():
        if source.is_file():
            target = return_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(relative)

    limited = {
        "logs/compile_driver.head_tail.log": (run_root / "compile/sim_results/compile_driver.log", 2 * 1024 * 1024),
        "logs/sim.head_tail.log": (run_root / "sim.log", 2 * 1024 * 1024),
        "logs/return_observer.log": (run_root / "return_observer.log", 8 * 1024 * 1024),
        "logs/host_progress.log": (run_root / "host_progress.log", 1024 * 1024),
    }
    for relative, (source, limit) in limited.items():
        if _copy_limited(source, return_root / relative, limit):
            copied.append(relative)

    readback_count = 0
    for item in manifest["readback_checks"]:
        source = resolve_inside(server_root, str(item["runtime_path"]), "runtime D")
        if not source.is_file():
            continue
        relative = "readbacks/" + PurePosixPath(str(item["runtime_path"])).relative_to(
            "sim_results", manifest["run_namespace"], "formal_d"
        ).as_posix()
        target = return_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(relative)
        readback_count += 1

    allowlist = {
        "schema": "node0075-df23e4d-return-allowlist-v1",
        "copied_exact_set": sorted(copied),
        "formal_readback_count": readback_count,
        "forbidden": ["csrc", "simv", "simv.daidir", "waveform", "nested archive"],
    }
    write_json(return_root / "RETURN_ALLOWLIST.json", allowlist)
    return_manifest = {
        "schema": "node0075-df23e4d-return-manifest-v1",
        "source_package_manifest_sha256": sha256(package_root / MANIFEST_NAME),
        "files": file_records(return_root, {"RETURN_MANIFEST.json"}),
    }
    write_json(return_root / "RETURN_MANIFEST.json", return_manifest)
    _deterministic_zip(return_root, return_zip)
    digest = sha256(return_zip)
    sidecar.write_text(f"{digest}  {return_zip.name}\n", encoding="ascii", newline="\n")
    return {
        "status": "RETURN_PACKAGE_CREATED",
        "return_zip": str(return_zip),
        "return_zip_sha256": digest,
        "sidecar": str(sidecar),
        "file_count": len(return_manifest["files"]) + 1,
        "formal_readback_count": readback_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preflight")
    p.add_argument("--package-root", type=Path, required=True)
    p = sub.add_parser("verify-install")
    p.add_argument("--package-root", type=Path, required=True)
    p.add_argument("--cfg-root", type=Path, required=True)
    p = sub.add_parser("prepare-run")
    p.add_argument("--package-root", type=Path, required=True)
    p.add_argument("--server-root", type=Path, required=True)
    p.add_argument("--run-root", type=Path, required=True)
    p = sub.add_parser("analyze")
    p.add_argument("--package-root", type=Path, required=True)
    p.add_argument("--server-root", type=Path, required=True)
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--evidence-root", type=Path, required=True)
    p = sub.add_parser("collect")
    p.add_argument("--package-root", type=Path, required=True)
    p.add_argument("--server-root", type=Path, required=True)
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            result = preflight(args.package_root)
        elif args.command == "verify-install":
            result = verify_install(args.package_root, args.cfg_root)
        elif args.command == "prepare-run":
            result = prepare_run(args.package_root, args.server_root, args.run_root)
        elif args.command == "analyze":
            result = analyze(args.package_root, args.server_root, args.run_root, args.evidence_root)
        else:
            result = collect(args.package_root, args.server_root, args.run_root, args.evidence_root)
    except Exception as exc:
        print(f"NODE0075_RUNTIME_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    if args.command == "analyze" and not result.get("passed", False):
        return 20
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
