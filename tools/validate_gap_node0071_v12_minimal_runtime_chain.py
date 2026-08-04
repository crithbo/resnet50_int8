from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_runner_guard_chain as common


ROOT_NAME = "r5_n71_gap_v12_minruntime"
OBSERVER_SHA256 = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)
IDENTITY_POINTER = "/files/tb_probe~1native_return_observer.svh/sha256"
WRONG_SHA256 = "f" * 64


class ValidationError(ValueError):
    pass


def run_manifest_guard(package: Path) -> dict[str, Any]:
    command = [
        sys.executable,
        str(
            package
            / "package_tools/gap_node0071_package_observer_guard.py"
        ),
        "--package-root",
        str(package),
        "--manifest",
        str(package / "TEST_PACKAGE_MANIFEST.json"),
        "--runner",
        str(package / common.RUNNER_RELATIVE),
    ]
    process = subprocess.run(
        command,
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    parsed = None
    if process.stdout.strip():
        try:
            parsed = json.loads(process.stdout)
        except json.JSONDecodeError:
            parsed = None
    return {
        "command": command,
        "exit_code": process.returncode,
        "stdout_sha256": common.hashlib.sha256(
            process.stdout.encode("utf-8")
        ).hexdigest(),
        "stderr_sha256": common.hashlib.sha256(
            process.stderr.encode("utf-8")
        ).hexdigest(),
        "parsed": parsed,
    }


def mutate_manifest_observer_sha(package: Path, replacement: str) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    relative = manifest["package_local_observer"]["relative_path"]
    manifest["files"][relative]["sha256"] = replacement
    path.write_text(
        json.dumps(
            manifest, indent=2, ensure_ascii=False, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".g71-v12-",
        dir=Path.cwd(),
        ignore_cleanup_errors=True,
    ) as temporary:
        root = Path(temporary)
        package = common.extract(target_zip, ROOT_NAME, root / "fresh")
        observer_sha = common.sha256(
            package / common.OBSERVER_RELATIVE
        )
        runner_text = (package / common.RUNNER_RELATIVE).read_text(
            encoding="utf-8"
        )
        manifest = json.loads(
            (package / "TEST_PACKAGE_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        observer_contract = manifest["package_local_observer"]
        canonical_sha = manifest["files"][
            observer_contract["relative_path"]
        ]["sha256"]
        static_single_source = (
            observer_sha == OBSERVER_SHA256 == canonical_sha
            and observer_contract.get("identity_json_pointer")
            == IDENTITY_POINTER
            and "sha256" not in observer_contract
            and "source_sha256"
            not in manifest.get("observer_binding_contract", {})
            and OBSERVER_SHA256 not in runner_text
            and "--expected-sha256" not in runner_text
            and '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json"'
            in runner_text
        )
        if not static_single_source:
            raise ValidationError("manifest single-source binding differs")

        precompile = runner_text.split(
            "printf 'make -C %q -f Makefile.tb_NDP_Top_new_phy compile",
            1,
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
        runtime_minimal = not any(
            token in precompile for token in forbidden_runtime_source_gates
        )
        if not runtime_minimal:
            raise ValidationError("server-source runtime preflight overreach")

        positive_guard = run_manifest_guard(package)
        if (
            positive_guard["exit_code"] != 0
            or positive_guard["parsed"].get("valid") is not True
            or positive_guard["parsed"].get("identity_match") is not True
            or positive_guard["parsed"].get("identity_source")
            != "final_manifest_single_source"
        ):
            raise ValidationError("manifest-source observer guard failed")

        controls: dict[str, Any] = {}
        control_specs = {
            "source_missing": None,
            "incdir_missing": (
                "+incdir+$package_root/tb_probe",
                "+incdir+$package_root/absent_probe",
            ),
            "macro_missing": (
                "+define+NATIVE_RETURN_OBSERVER_ENABLE",
                "+define+NATIVE_RETURN_OBSERVER_DISABLED",
            ),
            "runtime_missing": (
                "+RETURN_OBSERVER",
                "+NO_RETURN_OBSERVER",
            ),
        }
        for name, mutation in control_specs.items():
            control_root = root / f"control_{name}"
            shutil.copytree(package, control_root)
            if name == "source_missing":
                (control_root / common.OBSERVER_RELATIVE).unlink()
            else:
                assert mutation is not None
                common.mutate_runner_term(
                    control_root, mutation[0], mutation[1]
                )
            receipt = run_manifest_guard(control_root)
            controls[name] = receipt
            if receipt["exit_code"] != 1:
                raise ValidationError(
                    f"negative control did not fail: {name}"
                )

        wrong_guard_root = root / "wrong_guard"
        shutil.copytree(package, wrong_guard_root)
        mutate_manifest_observer_sha(wrong_guard_root, WRONG_SHA256)
        wrong_guard = run_manifest_guard(wrong_guard_root)
        controls["wrong_manifest_identity"] = wrong_guard
        if wrong_guard["exit_code"] != 1:
            raise ValidationError("wrong manifest identity guard did not fail")

        positive_runner = common.run_runner_mock(
            package, root / "positive_runner", bash
        )
        if (
            positive_runner["exit_code"] != 86
            or not positive_runner["make_reached"]
            or positive_runner["installed_preflight"].get("valid") is not True
            or positive_runner["observer_precompile"].get("valid") is not True
            or positive_runner["observer_precompile"].get("identity_source")
            != "final_manifest_single_source"
            or not positive_runner["actual_compile_argv_exists"]
        ):
            raise ValidationError(
                "fresh-extract real runner did not reach compile stub"
            )

        wrong_runner_root = root / "wrong_runner_package"
        shutil.copytree(package, wrong_runner_root)
        mutate_manifest_observer_sha(wrong_runner_root, WRONG_SHA256)
        wrong_runner = common.run_runner_mock(
            wrong_runner_root, root / "wrong_runner", bash
        )
        if (
            wrong_runner["exit_code"] != 5
            or wrong_runner["make_reached"]
            or wrong_runner["observer_precompile"] is not None
            or wrong_runner["actual_compile_argv_exists"]
        ):
            raise ValidationError(
                "wrong manifest identity did not fail before compile"
            )

        return {
            "schema":
                "gap-node0071-minimal-runtime-runner-chain-validation-v12",
            "valid": True,
            "rule_ids": [
                "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
                "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
                "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
            ],
            "target_zip": str(target_zip),
            "target_zip_sha256": common.sha256(target_zip),
            "fresh_extract_root": ROOT_NAME,
            "manifest_single_source": static_single_source,
            "runtime_preflight_minimal": runtime_minimal,
            "server_source_files_inspected": False,
            "positive_guard": positive_guard,
            "positive_full_runner": positive_runner,
            "negative_controls": controls,
            "wrong_manifest_identity_full_runner": wrong_runner,
            "compile_stub_unique_expected_exit_code": 86,
            "positive_compile_reached": True,
            "actual_compile_argv_captured": True,
            "wrong_identity_failed_before_compile": True,
            "all_negative_controls_fail_closed": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(
            args.target_zip.resolve(), args.bash.resolve()
        )
        if args.output:
            args.output.write_text(
                json.dumps(
                    result, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
    except Exception as error:
        print(
            f"minimal-runtime runner validation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
