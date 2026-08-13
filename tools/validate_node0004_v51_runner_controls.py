from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v50_runner_controls as prior


base = prior.base
INSTALL_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
FIXED_ROOT = "/home/panqs/ndp/simresult"
ORIGINAL_WRITE_STUBS = prior.write_stubs


def write_stubs(stub_root: Path, python: Path) -> None:
    ORIGINAL_WRITE_STUBS(stub_root, python)
    make = stub_root / "make"
    text = make.read_text(encoding="utf-8")
    anchor = (
        "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | "
        "feature=RETURN_OBS_DTERM_OWNER enabled=1 "
        "limit_name=RETURN_OBS_DTERM_OWNER_LIMIT limit=96 "
        "schema=DTERM_OWNER\n"
    )
    addition = anchor + (
        "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | "
        "feature=RETURN_OBS_LC13_LC14 enabled=1 "
        "limit_name=RETURN_OBS_LC13_LC14_LIMIT limit=128 "
        "schema=LC13_LC14\n"
    )
    if text.count(anchor) != 1:
        raise ValueError("DTERM safe-stub marker differs")
    make.write_text(
        text.replace(anchor, addition, 1),
        encoding="utf-8",
        newline="\n",
    )


def map_harness(package: Path, result_root: Path) -> None:
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    if runner.count(FIXED_ROOT) < 4:
        raise ValueError("production fixed path not fully bound")
    temp_root = Path(tempfile.gettempdir()).resolve()
    relative = result_root.resolve().relative_to(temp_root)
    bash_result_root = "/tmp/" + relative.as_posix()
    mapped_runner = runner.replace(FIXED_ROOT, bash_result_root)
    native_result_root = result_root.resolve().as_posix()
    mapped_runner = mapped_runner.replace(
        f'"result_root": "{bash_result_root}"',
        f'"result_root": "{native_result_root}"',
        1,
    ).replace(
        f'"return_zip": "{bash_result_root}/${{install_name}}_return.zip"',
        f'"return_zip": "{native_result_root}/${{install_name}}_return.zip"',
        1,
    ).replace(
        f'"return_sidecar": "{bash_result_root}/${{install_name}}_return.zip.sha256"',
        f'"return_sidecar": "{native_result_root}/${{install_name}}_return.zip.sha256"',
        1,
    )
    runner_path.write_text(
        mapped_runner, encoding="utf-8", newline="\n"
    )
    runtime_path = (
        package
        / "package_tools/node0004_hang_localization_runtime_v7.py"
    )
    runtime = runtime_path.read_text(encoding="utf-8")
    token = 'Path("/home/panqs/ndp/simresult")'
    if runtime.count(token) != 1:
        raise ValueError("production runtime fixed path differs")
    mapped_runtime = runtime.replace(
        token, f"Path({str(result_root)!r})", 1
    ).replace(
        'publication.get("result_root") != str(fixed)',
        'Path(publication.get("result_root")) != fixed',
        1,
    ).replace(
        'publication.get("return_zip") != str(final_zip)',
        'Path(publication.get("return_zip")) != final_zip',
        1,
    ).replace(
        'publication.get("return_sidecar") != str(final_sha)',
        'Path(publication.get("return_sidecar")) != final_sha',
        1,
    )
    runtime_path.write_text(
        mapped_runtime,
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(package).as_posix(): base.sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extract(zip_path: Path, destination: Path) -> Path:
    return base.extract(zip_path, destination)


def one_control(
    source_package: Path,
    root: Path,
    python: Path,
    bash: Path,
    *,
    term: bool,
) -> dict[str, object]:
    package = root / "package"
    shutil.copytree(source_package, package)
    result_root = root / "isolated_simresult"
    result_root.mkdir()
    map_harness(package, result_root)
    stub = root / "stub"
    write_stubs(stub, python)
    compile_log = root / "compile.log"
    started = root / "started"
    server = root / "server"
    if term:
        status = root / "term.status"
        process = base.run_term(
            package,
            server,
            stub,
            compile_log,
            started,
            bash,
            status,
        )
        runner_exit = int(status.read_text(encoding="ascii").strip())
    else:
        process = base.run_exit(
            package,
            server,
            stub,
            compile_log,
            started,
            bash,
        )
        runner_exit = process.returncode
    return_zip = result_root / f"{INSTALL_NAME}_return.zip"
    return_sha = Path(str(return_zip) + ".sha256")
    sidecar = (
        return_sha.read_text(encoding="ascii").split()
        if return_sha.is_file()
        else []
    )
    compile_text = (
        compile_log.read_text(encoding="utf-8")
        if compile_log.is_file()
        else ""
    )
    members = base.returned_members(return_zip)
    return {
        "runner_exit_code": runner_exit,
        "outer_harness_exit_code": process.returncode,
        "runner_stdout": process.stdout,
        "runner_stderr": process.stderr,
        "compile_invoked": "Makefile.tb_NDP_Top_new_phy" in compile_text,
        "compile_argv": compile_text,
        "return_zip_exists": return_zip.is_file(),
        "return_sidecar_exists": return_sha.is_file(),
        "sidecar_name_hash_shape": len(sidecar) == 2
        and sidecar[1] == return_zip.name,
        "return_manifest_present": "RETURN_MANIFEST.json" in members,
        "publication_receipt_present": (
            "evidence/publication_preflight.json" in members
        ),
        "server_root_duplicate_absent": not (
            server / return_zip.name
        ).exists(),
        "package_root_duplicate_absent": not (
            package / return_zip.name
        ).exists(),
        "isolated_harness_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    digest = base.sha256(args.zip)
    with tempfile.TemporaryDirectory(prefix="v51-runner-harness-") as temp:
        root = Path(temp)
        source_package = extract(args.zip.resolve(), root / "extract")
        production_runner = (
            source_package / "PREPARE_AND_RUN.sh"
        ).read_text(encoding="utf-8")
        exit_control = one_control(
            source_package,
            root / "exit",
            args.python.resolve(),
            args.bash.resolve(),
            term=False,
        )
        term_control = one_control(
            source_package,
            root / "term",
            args.python.resolve(),
            args.bash.resolve(),
            term=True,
        )
        wrong = root / "wrong"
        shutil.copytree(source_package, wrong)
        wrong_manifest = wrong / "package_manifest.json"
        manifest = json.loads(wrong_manifest.read_text(encoding="utf-8"))
        manifest["install_name"] = "wrong_identity"
        wrong_manifest.write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        # Identity is manifest-bound and package preflight must reject this.
        runtime = (
            source_package
            / "package_tools/node0004_hang_localization_runtime.py"
        )
        import subprocess

        wrong_result = subprocess.run(
            [
                str(args.python.resolve()),
                str(runtime),
                "preflight",
                "--package-root",
                str(wrong),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
    checks = {
        "zip_identity": (
            digest == args.expected_zip_sha256
            and args.sidecar.read_text(encoding="ascii")
            == f"{digest}  {args.zip.name}\n"
        ),
        "production_fixed_path_unmodified": (
            f'result_root="{FIXED_ROOT}"' in production_runner
            and "NDP_SIMRESULT_ROOT" not in production_runner
        ),
        "safe_compile_exit_reached": (
            exit_control["compile_invoked"] is True
            and exit_control["runner_exit_code"] == 74
            and "Traceback" not in exit_control["runner_stderr"]
        ),
        "safe_compile_term_finalized": (
            term_control["compile_invoked"] is True
            and term_control["runner_exit_code"] == 143
            and "Traceback" not in term_control["runner_stderr"]
        ),
        "exit_return_complete": all(
            exit_control[name] is True
            for name in (
                "return_zip_exists",
                "return_sidecar_exists",
                "sidecar_name_hash_shape",
                "return_manifest_present",
                "publication_receipt_present",
                "server_root_duplicate_absent",
                "package_root_duplicate_absent",
            )
        ),
        "term_return_complete": all(
            term_control[name] is True
            for name in (
                "return_zip_exists",
                "return_sidecar_exists",
                "sidecar_name_hash_shape",
                "return_manifest_present",
                "publication_receipt_present",
                "server_root_duplicate_absent",
                "package_root_duplicate_absent",
            )
        ),
        "wrong_identity_fail_closed": wrong_result.returncode != 0,
        "harness_mapping_absent_from_production": (
            "isolated_simresult" not in production_runner
        ),
    }
    report = {
        "schema": "node0004-v51-runner-controls-v1",
        "valid": all(checks.values()),
        "errors": [name for name, value in checks.items() if not value],
        "checks": checks,
        "exit_control": exit_control,
        "term_control": term_control,
        "wrong_identity_exit_code": wrong_result.returncode,
        "production_target": FIXED_ROOT,
        "local_fixed_server_path_created_or_mapped": False,
        "claim_boundary": (
            "Production runner bytes are parsed first. A fresh-extract copy "
            "alone is rewritten to a disposable namespace for safe compile "
            "and EXIT/TERM finalizer controls; the mapping never enters ZIP."
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
