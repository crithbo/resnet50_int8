from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


OBSERVER_RELATIVE = Path("tb_probe/native_return_observer.svh")
IDENTITY_JSON_POINTER = (
    "/files/tb_probe~1native_return_observer.svh/sha256"
)
_GENERATED_PATH = re.compile(r"\b[A-Za-z_]\w*_gen\s*\[([^\]]+)\]")
_GENVAR = re.compile(r"\bgenvar\s+([A-Za-z_]\w*)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_expected_identity(
    root: Path, manifest_path: Path
) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    resolved = manifest_path.resolve()
    if (
        not resolved.is_file()
        or resolved.is_symlink()
        or not resolved.is_relative_to(root)
    ):
        return None, ["manifest is unavailable or escapes package root"]
    try:
        manifest = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, [f"manifest is unreadable: {error}"]
    observer_contract = manifest.get("package_local_observer")
    if not isinstance(observer_contract, dict):
        return None, ["package-local observer contract is absent"]
    relative = observer_contract.get("relative_path")
    pointer = observer_contract.get("identity_json_pointer")
    if relative != OBSERVER_RELATIVE.as_posix():
        errors.append("observer relative path differs")
    if pointer != IDENTITY_JSON_POINTER:
        errors.append("observer identity JSON pointer differs")
    files = manifest.get("files")
    receipt = files.get(relative) if isinstance(files, dict) else None
    expected = receipt.get("sha256") if isinstance(receipt, dict) else None
    if not isinstance(expected, str) or re.fullmatch(
        r"[0-9a-f]{64}", expected
    ) is None:
        errors.append("manifest observer SHA receipt differs")
        expected = None
    return expected, errors


def observer_precompile_receipt(
    package_root: Path, manifest_path: Path, runner: Path
) -> dict[str, Any]:
    root = package_root.resolve()
    observer = root / OBSERVER_RELATIVE
    expected_sha256, errors = manifest_expected_identity(
        root, manifest_path
    )
    if not observer.exists():
        errors.append("package-local observer is missing")
    elif observer.is_symlink() or not observer.is_file():
        errors.append("package-local observer must be a regular non-symlink file")
    elif not observer.resolve().is_relative_to(root):
        errors.append("package-local observer escapes package root")

    observed_sha: str | None = None
    generated_reference_count = 0
    declared_genvars: list[str] = []
    runtime_indexes: list[str] = []
    if observer.is_file() and not observer.is_symlink():
        observed_sha = sha256(observer)
        if observed_sha != expected_sha256:
            errors.append("package-local observer SHA-256 differs")
        text = observer.read_text(encoding="utf-8")
        declared = set(_GENVAR.findall(text))
        references = _GENERATED_PATH.findall(text)
        runtime_indexes = sorted(
            {
                expression.strip()
                for expression in references
                if not expression.strip().isdecimal()
                and expression.strip() not in declared
            }
        )
        generated_reference_count = len(references)
        declared_genvars = sorted(declared)
        if runtime_indexes:
            errors.append(
                "observer contains runtime-indexed generated instance paths"
            )

    runner_path = runner.resolve()
    runner_terms = {
        "manifest_single_source":
            '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json"',
        "package_local_incdir": "+incdir+$package_root/tb_probe",
        "compile_enable_macro": "+define+NATIVE_RETURN_OBSERVER_ENABLE",
        "runtime_enable": "+RETURN_OBSERVER",
        "runtime_output": "+RETURN_OBS_FILE=$observer_log",
        "time0_marker_check": "[RETURN_OBSERVER] enabled",
        "actual_compile_argv": "actual_compile_argv.txt",
        "actual_simulator_argv": "actual_simulator_argv.txt",
        "progress_return": "progress_samples.log",
    }
    runner_presence = {key: False for key in runner_terms}
    if (
        not runner_path.is_file()
        or runner_path.is_symlink()
        or not runner_path.is_relative_to(root)
    ):
        errors.append("package runner is unavailable or escapes root")
    else:
        runner_text = runner_path.read_text(encoding="utf-8")
        runner_presence = {
            key: term in runner_text
            for key, term in runner_terms.items()
        }
        if not all(runner_presence.values()):
            errors.append("observer four-way runner binding differs")
        if expected_sha256 and expected_sha256 in runner_text:
            errors.append("runner duplicates manifest observer SHA")

    return {
        "schema":
            "gap-node0071-package-local-observer-precompile-manifest-v2",
        "valid": not errors,
        "errors": errors,
        "package_root": str(root),
        "manifest_path": str(manifest_path.resolve()),
        "identity_source": "final_manifest_single_source",
        "identity_json_pointer": IDENTITY_JSON_POINTER,
        "observer_relative_path": OBSERVER_RELATIVE.as_posix(),
        "observer_path": str(observer),
        "observer_readable": observer.is_file(),
        "observer_symlink": observer.is_symlink(),
        "expected_sha256": expected_sha256,
        "observed_sha256": observed_sha,
        "identity_match": observed_sha == expected_sha256,
        "compile_include_directory": str((root / "tb_probe").resolve()),
        "runner_path": str(runner_path),
        "runner_binding": runner_presence,
        "four_way_rule": "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        "xmr_static_gate": {
            "rule_id": "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "status": "pass" if not runtime_indexes else "fail",
            "checked_generated_instance_reference_count":
                generated_reference_count,
            "declared_genvars": declared_genvars,
            "runtime_indexed_generated_instance_reference_count":
                len(runtime_indexes),
        },
        "server_source_files_inspected": False,
        "server_file_written": False,
        "functional_rtl_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    args = parser.parse_args()
    receipt = observer_precompile_receipt(
        args.package_root, args.manifest, args.runner
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
