from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


OBSERVER_RELATIVE = Path("tb_probe/native_return_observer.svh")
_GENERATED_PATH = re.compile(r"\b[A-Za-z_]\w*_gen\s*\[([^\]]+)\]")
_GENVAR = re.compile(r"\bgenvar\s+([A-Za-z_]\w*)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def observer_precompile_receipt(
    package_root: Path, expected_sha256: str
) -> dict[str, Any]:
    root = package_root.resolve()
    observer = root / OBSERVER_RELATIVE
    errors: list[str] = []
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
    if not errors:
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

    return {
        "schema": "gap-node0071-package-local-observer-precompile-v1",
        "valid": not errors,
        "errors": errors,
        "package_root": str(root),
        "observer_relative_path": OBSERVER_RELATIVE.as_posix(),
        "observer_path": str(observer),
        "observer_readable": observer.is_file(),
        "observer_symlink": observer.is_symlink(),
        "expected_sha256": expected_sha256,
        "observed_sha256": observed_sha,
        "identity_match": observed_sha == expected_sha256,
        "compile_include_directory": str((root / "tb_probe").resolve()),
        "xmr_static_gate": {
            "rule_id": "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "status": "pass" if not runtime_indexes else "fail",
            "checked_generated_instance_reference_count":
                generated_reference_count,
            "declared_genvars": declared_genvars,
            "runtime_indexed_generated_instance_reference_count":
                len(runtime_indexes),
        },
        "server_file_written": False,
        "functional_rtl_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    receipt = observer_precompile_receipt(
        args.package_root, args.expected_sha256
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0 if receipt["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
