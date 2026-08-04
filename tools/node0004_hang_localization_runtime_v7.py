from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


MAX_TEXT_BYTES = 8 * 1024 * 1024


class DiagnosticRuntimeError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise DiagnosticRuntimeError(f"unsafe relative path: {relative}")
    result = (root / Path(*pure.parts)).resolve()
    if not result.is_relative_to(root.resolve()):
        raise DiagnosticRuntimeError(f"path escapes root: {relative}")
    return result


def package_records(root: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "package_manifest.json":
            continue
        records[relative] = sha256(path)
    return records


def _path_leaves(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            result.extend(_path_leaves(item))
    elif isinstance(value, list):
        for item in value:
            result.extend(_path_leaves(item))
    elif isinstance(value, str) and value.startswith("install/cfg_pkg/"):
        result.append(value)
    return result


def preflight(package_root: Path) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    expected = manifest.get("files")
    observed = package_records(package_root)
    if expected != observed:
        raise DiagnosticRuntimeError("package file hash set differs")
    if manifest.get("classification") != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":
        raise DiagnosticRuntimeError("diagnostic classification differs")
    if manifest.get("candidate_release") is not False:
        raise DiagnosticRuntimeError("diagnostic package cannot be candidate")
    if manifest.get("server_rtl_entries") != 0:
        raise DiagnosticRuntimeError("diagnostic package contains RTL")
    if manifest.get("run_ids") != ["c0"]:
        raise DiagnosticRuntimeError("diagnostic run set is not c0-only")
    observer = package_root / "tb_probe/native_return_observer.svh"
    runner = (package_root / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    for token in (
        "+define+NATIVE_RETURN_OBSERVER_ENABLE",
        "+RETURN_OBSERVER",
        "+RETURN_HANG_DIAG",
        "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
        "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
        "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        "host_progress.log",
        "simulator_argv.txt",
    ):
        if token not in runner:
            raise DiagnosticRuntimeError(f"runtime binding missing: {token}")
    if "DIAG_DECISION" not in observer.read_text(encoding="utf-8"):
        raise DiagnosticRuntimeError("observer decision record missing")

    runtime = package_root / "workload/runtime"
    input_count = 0
    output_count = 0
    for path in sorted((runtime / "runs/c0").glob("sca_cfg*.json")):
        for leaf in _path_leaves(load_json(path)):
            prefix = f"install/cfg_pkg/{manifest['install_name']}/"
            if not leaf.startswith(prefix):
                raise DiagnosticRuntimeError(f"stale SCA root: {leaf}")
            target = safe_child(runtime, leaf[len(prefix) :])
            if path.name == "sca_cfg_D.json":
                if target.exists():
                    raise DiagnosticRuntimeError(f"preloaded D: {target}")
                output_count += 1
            else:
                if not target.is_file():
                    raise DiagnosticRuntimeError(f"missing input: {target}")
                input_count += 1
    if (input_count, output_count) != (86, 28):
        raise DiagnosticRuntimeError(
            f"c0 SCA leaf count differs: {input_count}/{output_count}"
        )
    return {
        "schema": "node0004-hang-localization-preflight-v7",
        "valid": True,
        "install_name": manifest["install_name"],
        "package_file_count": len(observed),
        "c0_input_leaf_count": input_count,
        "c0_absent_d_leaf_count": output_count,
        "observer_sha256": sha256(observer),
        "observer_runtime_enabled": True,
        "progress_log_return_bound": True,
        "host_monotonic_log_return_bound": True,
    }


def verify_install(package_root: Path, cfg_root: Path) -> dict[str, Any]:
    source = package_root / "workload/runtime"
    source_records = {
        path.relative_to(source).as_posix(): sha256(path)
        for path in sorted(item for item in source.rglob("*") if item.is_file())
    }
    installed_records = {
        path.relative_to(cfg_root).as_posix(): sha256(path)
        for path in sorted(item for item in cfg_root.rglob("*") if item.is_file())
    }
    if source_records != installed_records:
        raise DiagnosticRuntimeError("installed c0 workload differs")
    return {
        "schema": "node0004-hang-localization-install-v7",
        "valid": True,
        "file_count": len(source_records),
        "runtime_d_initially_absent": True,
    }


def _status(path: Path) -> int:
    if not path.is_file():
        return 125
    try:
        return int(path.read_text(encoding="ascii").strip())
    except ValueError:
        return 125


def analyze(
    package_root: Path, evidence_root: Path, run_root: Path
) -> dict[str, Any]:
    compile_status = _status(evidence_root / "compile_exit_status.txt")
    run_status = _status(evidence_root / "run_exit_status.txt")
    observer = run_root / "c0/return_observer.log"
    decision_lines: list[str] = []
    progress_lines: list[str] = []
    finish_lines: list[str] = []
    if observer.is_file():
        for line in observer.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if "| DIAG_DECISION |" in line:
                decision_lines.append(line)
            if "| PROGRESS_WINDOW |" in line:
                progress_lines.append(line)
            if "| COMP_FINISH |" in line:
                finish_lines.append(line)
    decision = decision_lines[-1] if decision_lines else None
    if finish_lines:
        status = "C0_NATURAL_TERMINAL_OBSERVED_DIAGNOSTIC_ONLY"
    elif decision and "MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING" in decision:
        status = "C0_STILL_PROGRESSING_NOT_FINISHED_AT_BUDGET"
    elif decision_lines:
        status = "C0_HANG_BOUNDARY_LOCALIZED"
    elif progress_lines:
        status = "C0_EXTERNAL_INTERRUPT_WITH_PROGRESS_HISTORY"
    else:
        status = "C0_DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    value = {
        "schema": "node0004-hang-localization-result-v7",
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "status": status,
        "compile_exit_status": compile_status,
        "run_exit_status": run_status,
        "compile_succeeded": compile_status == 0,
        "natural_terminal_observed": bool(finish_lines),
        "progress_window_count": len(progress_lines),
        "last_progress_window": progress_lines[-1] if progress_lines else None,
        "diagnostic_decision": decision,
        "formal_readback_claimed": False,
        "e4_claimed": False,
        "e5_claimed": False,
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", value)
    return value


def _copy_limited(
    source: Path,
    target: Path,
    relative: str,
    records: list[dict[str, Any]],
    required: bool,
) -> None:
    if not source.is_file():
        if required:
            raise DiagnosticRuntimeError(f"required return file missing: {source}")
        return
    if source.stat().st_size > MAX_TEXT_BYTES:
        raise DiagnosticRuntimeError(f"return text exceeds budget: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    records.append(
        {
            "path": relative,
            "required": required,
            "size_bytes": target.stat().st_size,
            "sha256": sha256(target),
        }
    )


def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    return_dir = server_root / f"{install_name}_return"
    return_zip = return_dir.with_suffix(".zip")
    return_sha = Path(str(return_zip) + ".sha256")
    return_dir.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    items = (
        (
            evidence_root / "package_preflight.json",
            "evidence/package_preflight.json",
            True,
        ),
        (
            evidence_root / "install_preflight.json",
            "evidence/install_preflight.json",
            True,
        ),
        (
            evidence_root / "observer_precompile.json",
            "evidence/observer_precompile.json",
            True,
        ),
        (
            evidence_root / "compile_exit_status.txt",
            "evidence/compile_exit_status.txt",
            True,
        ),
        (
            evidence_root / "run_exit_status.txt",
            "evidence/run_exit_status.txt",
            True,
        ),
        (
            evidence_root / "SERVER_RESULT_GATE.json",
            "evidence/SERVER_RESULT_GATE.json",
            True,
        ),
        (
            evidence_root / "signal_status.txt",
            "evidence/signal_status.txt",
            False,
        ),
        (
            run_root / "compile/sim_results/compile_driver.log",
            "runs/compile/sim_results/compile_driver.log",
            False,
        ),
        (
            run_root / "compile/sim_results/compile.log",
            "runs/compile/sim_results/compile.log",
            False,
        ),
        (run_root / "c0/sim.log", "runs/c0/sim.log", False),
        (
            run_root / "c0/return_observer.log",
            "runs/c0/return_observer.log",
            False,
        ),
        (
            run_root / "c0/host_progress.log",
            "runs/c0/host_progress.log",
            False,
        ),
        (
            run_root / "c0/simulator_argv.txt",
            "runs/c0/simulator_argv.txt",
            False,
        ),
    )
    for source, relative, required in items:
        _copy_limited(
            source,
            return_dir / Path(*PurePosixPath(relative).parts),
            relative,
            records,
            required,
        )
    records.sort(key=lambda item: item["path"])
    allowlist = {
        "schema": "node0004-hang-localization-return-allowlist-v7",
        "install_name": install_name,
        "records": records,
    }
    write_json(return_dir / "RETURN_ALLOWLIST.json", allowlist)
    with zipfile.ZipFile(
        return_zip, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(item for item in return_dir.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(return_dir.parent).as_posix())
    digest = sha256(return_zip)
    return_sha.write_text(
        f"{digest}  {return_zip.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return {
        "zip": str(return_zip),
        "sha256": digest,
        "allowlisted_file_count": len(records) + 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
    ins = sub.add_parser("verify-install")
    ins.add_argument("--package-root", type=Path, required=True)
    ins.add_argument("--cfg-root", type=Path, required=True)
    ana = sub.add_parser("analyze")
    ana.add_argument("--package-root", type=Path, required=True)
    ana.add_argument("--evidence-root", type=Path, required=True)
    ana.add_argument("--run-root", type=Path, required=True)
    col = sub.add_parser("collect")
    col.add_argument("--server-root", type=Path, required=True)
    col.add_argument("--install-name", required=True)
    col.add_argument("--evidence-root", type=Path, required=True)
    col.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        value = preflight(args.package_root)
    elif args.command == "verify-install":
        value = verify_install(args.package_root, args.cfg_root)
    elif args.command == "analyze":
        value = analyze(args.package_root, args.evidence_root, args.run_root)
    else:
        value = collect(
            args.server_root,
            args.install_name,
            args.evidence_root,
            args.run_root,
        )
    print(json.dumps(value, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
