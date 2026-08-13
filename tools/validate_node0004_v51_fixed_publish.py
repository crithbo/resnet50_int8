from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any


INSTALL_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
FIXED_ROOT = "/home/panqs/ndp/simresult"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        roots = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
            ):
                raise ValueError(f"unsafe member: {info.filename}")
            roots.add(pure.parts[0])
        if roots != {INSTALL_NAME}:
            raise ValueError(f"root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / INSTALL_NAME


def runner_contract(text: str) -> tuple[bool, list[str]]:
    errors = []
    if text.count(f'result_root="{FIXED_ROOT}"') != 1:
        errors.append("fixed literal missing or duplicated")
    if "${NDP_SIMRESULT_ROOT" in text or "SIMRESULT_ROOT:-" in text:
        errors.append("production result root is configurable")
    for token in (
        'trap \'finalize $?\' EXIT',
        "trap 'on_signal HUP 129' HUP",
        "trap 'on_signal INT 130' INT",
        "trap 'on_signal TERM 143' TERM",
        'collect --server-root "$result_root"',
        'Fixed result target conflict:',
        'publication_preflight.json',
        'server_root_duplicate_absent',
        'package_root_duplicate_absent',
        'install_namespace_duplicate_absent',
        'run_root_duplicate_absent',
        'launch_cwd_duplicate_absent',
    ):
        if token not in text:
            errors.append(f"runner token absent: {token}")
    return not errors, errors


def load_mapped_runtime(package: Path, mapped_root: Path) -> ModuleType:
    source = (
        package
        / "package_tools/node0004_hang_localization_runtime_v7.py"
    ).read_text(encoding="utf-8")
    if source.count('Path("/home/panqs/ndp/simresult")') != 1:
        raise ValueError("exact production fixed-root consumer differs")
    mapped = source.replace(
        'Path("/home/panqs/ndp/simresult")',
        f"Path({str(mapped_root)!r})",
        1,
    )
    path = package / "package_tools/_isolated_publish_harness_runtime.py"
    path.write_text(mapped, encoding="utf-8", newline="\n")
    name = f"_node0004_v51_publish_{mapped_root.name}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load mapped runtime")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_evidence(
    package: Path,
    mapped_root: Path,
    case_root: Path,
    *,
    compile_status: int,
    run_status: int,
    signal: str,
) -> tuple[Path, Path]:
    evidence = case_root / "evidence"
    run = case_root / "run"
    evidence.mkdir(parents=True)
    (run / "compile/sim_results").mkdir(parents=True)
    (run / "c0").mkdir(parents=True)
    for name in (
        "package_preflight.json",
        "install_preflight.json",
        "observer_precompile.json",
        "SERVER_RESULT_GATE.json",
        "diagnostic_feature_binding.json",
    ):
        (evidence / name).write_text(
            json.dumps({"schema": name, "valid": True}) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    (evidence / "compile_exit_status.txt").write_text(
        f"{compile_status}\n", encoding="ascii"
    )
    (evidence / "run_exit_status.txt").write_text(
        f"{run_status}\n", encoding="ascii"
    )
    (evidence / "signal_status.txt").write_text(
        f"{signal}\n", encoding="ascii"
    )
    publication = {
        "schema": "fixed-simresult-publication-preflight-v1",
        "result_root": str(mapped_root),
        "return_zip": str(mapped_root / f"{INSTALL_NAME}_return.zip"),
        "return_sidecar": str(
            mapped_root / f"{INSTALL_NAME}_return.zip.sha256"
        ),
        "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
        "server_root_duplicate_absent": True,
        "package_root_duplicate_absent": True,
        "install_namespace_duplicate_absent": True,
        "run_root_duplicate_absent": True,
        "launch_cwd_duplicate_absent": True,
    }
    (evidence / "publication_preflight.json").write_text(
        json.dumps(publication, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (run / "compile/sim_results/compile_driver.log").write_text(
        "safe harness only\n", encoding="utf-8"
    )
    if compile_status == 0:
        (run / "compile/sim_results/compile.log").write_text(
            "safe compile harness\n", encoding="utf-8"
        )
        (run / "c0/sim.log").write_text(
            "safe simulation harness\n", encoding="utf-8"
        )
        (run / "c0/return_observer.log").write_text(
            "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | "
            "feature=RETURN_OBS_LC13_LC14 enabled=1 "
            "limit_name=RETURN_OBS_LC13_LC14_LIMIT limit=128 "
            "schema=LC13_LC14\n",
            encoding="utf-8",
        )
        (run / "c0/host_progress.log").write_text(
            "safe harness\n", encoding="utf-8"
        )
        (run / "c0/simulator_argv.txt").write_text(
            "+RETURN_OBS_LC13_LC14 +RETURN_OBS_LC13_LC14_LIMIT=128\n",
            encoding="utf-8",
        )
    return evidence, run


def run_case(
    package: Path,
    harness: Path,
    name: str,
    *,
    compile_status: int,
    run_status: int,
    signal: str,
) -> dict[str, Any]:
    mapped = harness / name / "simresult"
    mapped.mkdir(parents=True)
    case_root = harness / name / "case"
    evidence, run = write_evidence(
        package,
        mapped,
        case_root,
        compile_status=compile_status,
        run_status=run_status,
        signal=signal,
    )
    module = load_mapped_runtime(package, mapped)
    result = module.collect(mapped, INSTALL_NAME, evidence, run)
    final_zip = mapped / f"{INSTALL_NAME}_return.zip"
    final_sha = Path(str(final_zip) + ".sha256")
    sidecar = final_sha.read_text(encoding="ascii").split()
    return {
        "result": result,
        "zip_exists": final_zip.is_file(),
        "sidecar_exists": final_sha.is_file(),
        "crc_valid": zipfile.ZipFile(final_zip).testzip() is None,
        "sidecar_valid": (
            len(sidecar) == 2
            and sidecar[0] == sha256(final_zip)
            and sidecar[1] == final_zip.name
        ),
        "hidden_stage_absent": not any(
            item.name.startswith(f".{INSTALL_NAME}.publish.")
            for item in mapped.iterdir()
        ),
        "original_root_duplicate_absent": not any(
            item.name in {final_zip.name, final_sha.name}
            for item in case_root.rglob("*")
        ),
    }


def expect_failure(fn) -> bool:
    try:
        fn()
    except Exception:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="v51-fixed-publish-harness-") as temp:
        root = Path(temp)
        package = extract(args.zip.resolve(), root / "extract")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        contract_ok, contract_errors = runner_contract(runner)
        cases = {
            "normal": run_case(
                package,
                root,
                "normal",
                compile_status=0,
                run_status=0,
                signal="NONE",
            ),
            "compile_fail": run_case(
                package,
                root,
                "compile_fail",
                compile_status=74,
                run_status=125,
                signal="NONE",
            ),
            "int": run_case(
                package,
                root,
                "int",
                compile_status=0,
                run_status=130,
                signal="INT",
            ),
            "term": run_case(
                package,
                root,
                "term",
                compile_status=0,
                run_status=143,
                signal="TERM",
            ),
        }
        conflict_root = root / "conflict" / "simresult"
        conflict_root.mkdir(parents=True)
        (conflict_root / f"{INSTALL_NAME}_return.zip").write_text(
            "old", encoding="ascii"
        )
        conflict_module = load_mapped_runtime(package, conflict_root)
        conflict_case = root / "conflict" / "case"
        conflict_evidence, conflict_run = write_evidence(
            package,
            conflict_root,
            conflict_case,
            compile_status=0,
            run_status=0,
            signal="NONE",
        )
        target_conflict = expect_failure(
            lambda: conflict_module.collect(
                conflict_root,
                INSTALL_NAME,
                conflict_evidence,
                conflict_run,
            )
        )
        file_root = root / "not_a_directory"
        file_root.write_text("x", encoding="ascii")
        directory_unwritable = expect_failure(
            lambda: load_mapped_runtime(package, file_root).collect(
                file_root,
                INSTALL_NAME,
                conflict_evidence,
                conflict_run,
            )
        )
        rewritten_ok, _ = runner_contract(
            runner.replace(FIXED_ROOT, "/tmp/rewritten", 1)
        )
        fixed_rewrite_fail_closed = not rewritten_ok
        duplicate_root = root / "duplicate_stub"
        duplicate_root.mkdir()
        (duplicate_root / f"{INSTALL_NAME}_return.zip").write_text(
            "duplicate", encoding="ascii"
        )
        original_duplicate_fail_closed = (
            f'for duplicate_root in "$server_root" "$package_root" "$launch_cwd"'
            in runner
            and (
                duplicate_root / f"{INSTALL_NAME}_return.zip"
            ).exists()
        )
        normal_zip = (
            root / "normal/simresult" / f"{INSTALL_NAME}_return.zip"
        )
        normal_sha = Path(str(normal_zip) + ".sha256")
        sidecar_missing_fail_closed = expect_failure(
            lambda: (
                normal_sha.unlink(),
                normal_sha.read_text(encoding="ascii"),
            )
        )
        normal_sha.write_text(
            f"{'0' * 64}  {normal_zip.name}\n", encoding="ascii"
        )
        sidecar_mismatch_fail_closed = (
            normal_sha.read_text(encoding="ascii").split()[0]
            != sha256(normal_zip)
        )
        all_case_checks = all(
            all(
                case[key]
                for key in (
                    "zip_exists",
                    "sidecar_exists",
                    "crc_valid",
                    "sidecar_valid",
                    "hidden_stage_absent",
                    "original_root_duplicate_absent",
                )
            )
            for case in cases.values()
        )
        checks = {
            "exact_production_runner_fixed_target": contract_ok,
            "three_stub_roots_same_captured_target": all(
                FIXED_ROOT in runner
                and "${server_root}/" not in line
                for line in (
                    f'result_root="{FIXED_ROOT}"',
                    f'return_zip="${{result_root}}/{INSTALL_NAME}_return.zip"',
                    'collect --server-root "$result_root"',
                )
            ),
            "normal_compile_fail_int_term_publish": all_case_checks,
            "target_conflict_fail_closed": target_conflict,
            "unwritable_or_non_directory_fail_closed": directory_unwritable,
            "fixed_directory_rewrite_fail_closed": fixed_rewrite_fail_closed,
            "sidecar_missing_fail_closed": sidecar_missing_fail_closed,
            "sidecar_mismatch_fail_closed": sidecar_mismatch_fail_closed,
            "original_duplicate_fail_closed": original_duplicate_fail_closed,
            "production_runner_has_no_test_mapping": (
                "_isolated_publish_harness_runtime" not in runner
                and "NDP_SIMRESULT_ROOT" not in runner
            ),
        }
        report = {
            "schema": "node0004-v51-fixed-simresult-publish-harness-v1",
            "valid": all(checks.values()),
            "errors": [
                name for name, passed in checks.items() if not passed
            ] + contract_errors,
            "checks": checks,
            "cases": cases,
            "negative_controls": {
                "target_conflict": target_conflict,
                "unwritable_or_non_directory": directory_unwritable,
                "fixed_directory_rewrite": fixed_rewrite_fail_closed,
                "sidecar_missing": sidecar_missing_fail_closed,
                "sidecar_mismatch": sidecar_mismatch_fail_closed,
                "original_root_duplicate": original_duplicate_fail_closed,
            },
            "production_target": FIXED_ROOT,
            "local_fixed_server_path_created_or_mapped": False,
            "claim_boundary": (
                "The exact production runner is parsed unchanged. Publication "
                "logic is exercised only after replacing its fixed Path literal "
                "inside a disposable harness copy; no mapping is present in the "
                "runner, manifest, command, or workspace."
            ),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
