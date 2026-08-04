from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def receipt(package_root: Path) -> dict[str, Any]:
    root = package_root.resolve()
    manifest = load_json(root / "package_manifest.json")
    binding = manifest.get("observer_binding", {})
    relative = str(binding.get("source", ""))
    pure = PurePosixPath(relative)
    errors: list[str] = []
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        errors.append("manifest observer path is unsafe")
        observer = root / "__unsafe_observer__"
    else:
        observer = (root / Path(*pure.parts)).resolve()
    expected = binding.get("source_sha256")
    observed: str | None = None
    if not observer.is_relative_to(root):
        errors.append("observer escapes package root")
    elif not observer.is_file() or observer.is_symlink():
        errors.append("observer is not a regular package-local file")
    else:
        observed = sha256(observer)
        if observed != expected:
            errors.append("observer SHA differs from final manifest")
    result = {
        "schema": "conv-native-four-lane-observer-guard-v1",
        "valid": not errors,
        "errors": errors,
        "identity_source": "final package_manifest.json observer_binding",
        "observer_relative_path": relative,
        "observer_path": str(observer),
        "expected_sha256": expected,
        "observed_sha256": observed,
        "identity_match": observed == expected,
        "package_tree_written": False,
        "server_source_inspected": False,
        "functional_rtl_modified": False,
    }
    return result


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    value = receipt(args.package_root)
    print(json.dumps(value, ensure_ascii=False))
    return 0 if value["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
