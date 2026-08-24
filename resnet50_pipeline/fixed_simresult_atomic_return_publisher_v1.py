#!/usr/bin/env python3
"""Allowlist-only atomic return publisher for the fixed server result root."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


RESULT_ROOT = Path("/home/panqs/ndp/simresult")


class PublishError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublishError(f"JSON object required: {path}")
    return value


def safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise PublishError(f"unsafe allowlist path: {relative}")
    candidate = root.joinpath(*pure.parts)
    resolved_root = root.resolve()
    try:
        candidate.resolve().relative_to(resolved_root)
    except ValueError as exc:
        raise PublishError(f"allowlist path escapes root: {relative}") from exc
    return candidate


def copy_declared(
    *,
    source: Path,
    return_dir: Path,
    target_relative: str,
    required: bool,
    maximum: int,
    source_root_name: str,
    source_relative: str,
    missing_semantics: str,
    records: list[dict[str, Any]],
) -> None:
    if not source.exists():
        if required:
            raise PublishError(
                f"required return member absent: {source_root_name}/"
                f"{source_relative}: {missing_semantics}"
            )
        return
    if not source.is_file() or source.is_symlink():
        raise PublishError(f"return source is not a regular file: {source}")
    mode = source.stat().st_mode
    if not stat.S_ISREG(mode) or source.stat().st_size > maximum:
        raise PublishError(f"return source type/size invalid: {source}")
    target = safe_child(return_dir, target_relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    records.append(
        {
            "path": target_relative,
            "source_root": source_root_name,
            "source_path": source_relative,
            "size_bytes": target.stat().st_size,
            "sha256": sha256(target),
            "required": required,
            "max_bytes": maximum,
            "missing_semantics": missing_semantics,
        }
    )


def deterministic_zip(return_dir: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(
            item for item in return_dir.rglob("*") if item.is_file()
        ):
            relative = (
                Path(return_dir.name) / path.relative_to(return_dir)
            ).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def write_return_digests(return_dir: Path, install_name: str) -> None:
    """Write an internal digest manifest into the single return ZIP."""
    members: list[dict[str, Any]] = []
    for path in sorted(item for item in return_dir.rglob("*") if item.is_file()):
        members.append({
            "path": path.relative_to(return_dir).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    write_json(return_dir / "RETURN_DIGESTS.json", {
        "schema": "server-return-single-zip-digest-v1",
        "package_id": install_name,
        "return_basename": f"{install_name}_return.zip",
        "members": members,
        "adjacent_sidecar_forbidden": True,
        "claim_boundary": "Digests are internal to the single return ZIP; no adjacent sidecar is published.",
    })


def collect(
    *, package_root: Path, evidence_root: Path, run_root: Path
) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    install_name = manifest.get("install_name")
    if not isinstance(install_name, str) or not install_name:
        raise PublishError("manifest install_name is missing")
    result_root = RESULT_ROOT
    result_root.mkdir(parents=True, exist_ok=True)
    if result_root.resolve() != result_root or not os.access(
        result_root, os.W_OK | os.X_OK
    ):
        raise PublishError("fixed result root is not exact/writable")
    final_zip = result_root / f"{install_name}_return.zip"
    if final_zip.exists():
        raise PublishError("fixed result target conflict")
    stage_root = result_root / f".{install_name}.publish.{os.getpid()}"
    if stage_root.exists():
        raise PublishError("fixed result staging conflict")
    return_dir = stage_root / f"{install_name}_return"
    staged_zip = stage_root / final_zip.name
    return_dir.mkdir(parents=True, exist_ok=False)
    roots = {
        "evidence": evidence_root,
        "run": run_root,
        "package": package_root,
    }
    declarations = manifest.get("return_allowlist")
    if not isinstance(declarations, list) or not declarations:
        raise PublishError("manifest return_allowlist is missing")
    records: list[dict[str, Any]] = []
    for declaration in declarations:
        if not isinstance(declaration, dict):
            raise PublishError("return allowlist entry is malformed")
        source_root_name = declaration.get("source_root")
        source_relative = declaration.get("source_path")
        target_relative = declaration.get("target_path")
        required = declaration.get("required")
        maximum = declaration.get("max_bytes")
        missing_semantics = declaration.get("missing_semantics")
        if (
            source_root_name not in roots
            or not isinstance(source_relative, str)
            or not isinstance(target_relative, str)
            or not isinstance(required, bool)
            or not isinstance(maximum, int)
            or maximum <= 0
            or not isinstance(missing_semantics, str)
            or not missing_semantics
        ):
            raise PublishError("return allowlist entry contract differs")
        copy_declared(
            source=safe_child(roots[source_root_name], source_relative),
            return_dir=return_dir,
            target_relative=target_relative,
            required=required,
            maximum=maximum,
            source_root_name=source_root_name,
            source_relative=source_relative,
            missing_semantics=missing_semantics,
            records=records,
        )
    result = load_json(evidence_root / "SERVER_RESULT_GATE.json")
    publication_preflight = load_json(
        evidence_root / "publication_preflight.json"
    )
    duplicate_keys = (
        "server_root_duplicate_absent",
        "package_root_duplicate_absent",
        "install_namespace_duplicate_absent",
        "run_root_duplicate_absent",
        "launch_cwd_duplicate_absent",
    )
    if (
        publication_preflight.get("result_root") != str(result_root)
        or publication_preflight.get("return_zip") != str(final_zip)
        or not all(
            publication_preflight.get(key) is True
            for key in duplicate_keys
        )
    ):
        raise PublishError("fixed publication preflight differs")
    publication = {
        "result_root": str(result_root),
        "return_zip": str(final_zip),
        "return_digest_member": f"{return_dir.name}/RETURN_DIGESTS.json",
        "publication_state": "STAGING_VALIDATED_BEFORE_ATOMIC_RENAME",
        **{key: True for key in duplicate_keys},
    }
    return_manifest = {
        "schema": (
            "conv-native-four-lane-public-order-return-manifest-v1"
        ),
        "install_name": install_name,
        "source_package_manifest_sha256": sha256(
            package_root / "package_manifest.json"
        ),
        "server_result_status": result.get("status"),
        "fixed_result_publication": publication,
        "records_excluding_this_manifest": sorted(
            records, key=lambda item: str(item["path"])
        ),
        "return_exact_set_policy": (
            "records plus RETURN_MANIFEST.json, RETURN_ALLOWLIST.json and "
            "RETURN_DIGESTS.json only"
        ),
        "declared_allowlist": declarations,
    }
    manifest_path = return_dir / "RETURN_MANIFEST.json"
    write_json(manifest_path, return_manifest)
    records.append(
        {
            "path": "RETURN_MANIFEST.json",
            "size_bytes": manifest_path.stat().st_size,
            "sha256": sha256(manifest_path),
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
        }
    )
    write_json(
        return_dir / "RETURN_ALLOWLIST.json",
        {
            "schema": (
                "conv-native-four-lane-public-order-return-allowlist-v1"
            ),
            "install_name": install_name,
            "fixed_result_publication": publication,
            "declared_allowlist": declarations,
            "records": sorted(records, key=lambda item: str(item["path"])),
        },
    )
    write_return_digests(return_dir, install_name)
    unpacked = sum(
        path.stat().st_size
        for path in return_dir.rglob("*")
        if path.is_file()
    )
    budget = manifest.get("return_budget", {})
    maximum_unpacked = int(budget.get("uncompressed_max_bytes", 0))
    maximum_zip = int(budget.get("zip_max_bytes", 0))
    if maximum_unpacked <= 0 or unpacked > maximum_unpacked:
        raise PublishError("return uncompressed budget exceeded")
    deterministic_zip(return_dir, staged_zip)
    if maximum_zip <= 0 or staged_zip.stat().st_size > maximum_zip:
        raise PublishError("return ZIP budget exceeded")
    with zipfile.ZipFile(staged_zip) as archive:
        names = [item.filename for item in archive.infolist()]
        expected = sorted(
            f"{return_dir.name}/{path.relative_to(return_dir).as_posix()}"
            for path in return_dir.rglob("*")
            if path.is_file()
        )
        if (
            archive.testzip() is not None
            or sorted(names) != expected
            or len(names) != len(set(names))
        ):
            raise PublishError("staged return ZIP exact-set differs")
    value = sha256(staged_zip)
    if final_zip.exists():
        raise PublishError("fixed result target conflict before publish")
    os.replace(staged_zip, final_zip)
    if sha256(final_zip) != value:
        raise PublishError("published return SHA differs")
    shutil.rmtree(return_dir)
    stage_root.rmdir()
    return {
        "schema": "fixed-simresult-atomic-publication-v1",
        "return_zip": str(final_zip),
        "return_digest_member": f"{return_dir.name}/RETURN_DIGESTS.json",
        "return_zip_bytes": final_zip.stat().st_size,
        "return_zip_sha256": value,
        "publication_state": "ATOMIC_PUBLISHED_VERIFIED",
        "duplicate_absent": True,
        "record_count": len(records) + 1,
        "uncompressed_bytes": unpacked,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    result = collect(
        package_root=args.package_root.resolve(),
        evidence_root=args.evidence_root.resolve(),
        run_root=args.run_root.resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
