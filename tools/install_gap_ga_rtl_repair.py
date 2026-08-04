#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any


def _canonical_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _atomic_copy(source: Path, destination: Path) -> None:
    mode = stat.S_IMODE(destination.stat().st_mode) if destination.exists() else 0o644
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        shutil.copyfile(source, temporary)
        os.chmod(temporary, mode | stat.S_IWUSR)
        if destination.exists():
            os.chmod(destination, mode | stat.S_IWUSR)
        os.replace(temporary, destination)
        os.chmod(destination, mode)
    finally:
        if temporary.exists():
            os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
            temporary.unlink()


def _write_report(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def install(
    *,
    ndp_root: Path,
    patch_root: Path,
    backup_root: Path,
    report_path: Path,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    patch = patch_root.resolve()
    backup = backup_root.resolve()
    manifest = _load(patch / "RTL_PATCH_MANIFEST.json")
    if backup.exists():
        raise ValueError(f"backup root must be fresh: {backup}")
    backup.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    try:
        for relative_text, identity in sorted(manifest["files"].items()):
            relative = Path(relative_text)
            target = (root / relative).resolve()
            expected_parent = (root / "rtl").resolve()
            target.relative_to(expected_parent)
            source = patch / relative
            if not target.is_file() or not source.is_file():
                raise FileNotFoundError(target if not target.is_file() else source)
            actual_preimage = _canonical_sha256(target)
            if actual_preimage != identity["source_canonical_text_sha256"]:
                raise ValueError(
                    f"server RTL preimage differs for {relative_text}: "
                    f"{actual_preimage}"
                )
            backup_path = backup / relative
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup_path)
            _atomic_copy(source, target)
            actual_patched = _canonical_sha256(target)
            if actual_patched != identity["patched_canonical_text_sha256"]:
                raise ValueError(f"server RTL patched hash differs: {relative_text}")
            records.append(
                {
                    "path": relative.as_posix(),
                    "resolved_target": target.as_posix(),
                    "preimage_sha256": _sha256(backup_path),
                    "preimage_canonical_text_sha256": actual_preimage,
                    "patched_sha256": _sha256(target),
                    "patched_canonical_text_sha256": actual_patched,
                }
            )
    except Exception:
        for record in reversed(records):
            relative = Path(record["path"])
            target = (root / relative).resolve()
            backup_path = backup / relative
            if backup_path.is_file():
                _atomic_copy(backup_path, target)
        raise
    report = {
        "schema": "resnet50-gap-ga-rtl-repair-install-v1",
        "action": "install",
        "status": "installed",
        "repair_id": manifest["repair_id"],
        "ndp_root": root.as_posix(),
        "patch_root": patch.as_posix(),
        "backup_root": backup.as_posix(),
        "files": records,
    }
    _write_report(report_path, report)
    return report


def restore(
    *,
    ndp_root: Path,
    patch_root: Path,
    backup_root: Path,
    report_path: Path,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    patch = patch_root.resolve()
    backup = backup_root.resolve()
    manifest = _load(patch / "RTL_PATCH_MANIFEST.json")
    records: list[dict[str, Any]] = []
    for relative_text, identity in sorted(manifest["files"].items()):
        relative = Path(relative_text)
        target = (root / relative).resolve()
        target.relative_to((root / "rtl").resolve())
        backup_path = backup / relative
        if not target.is_file() or not backup_path.is_file():
            raise FileNotFoundError(target if not target.is_file() else backup_path)
        current = _canonical_sha256(target)
        if current != identity["patched_canonical_text_sha256"]:
            raise ValueError(
                f"refusing restore over unexpected server RTL: {relative_text}: {current}"
            )
        _atomic_copy(backup_path, target)
        restored = _canonical_sha256(target)
        if restored != identity["source_canonical_text_sha256"]:
            raise ValueError(f"restored RTL hash differs: {relative_text}")
        records.append(
            {
                "path": relative.as_posix(),
                "resolved_target": target.as_posix(),
                "restored_sha256": _sha256(target),
                "restored_canonical_text_sha256": restored,
            }
        )
    report = {
        "schema": "resnet50-gap-ga-rtl-repair-install-v1",
        "action": "restore",
        "status": "restored",
        "repair_id": manifest["repair_id"],
        "ndp_root": root.as_posix(),
        "patch_root": patch.as_posix(),
        "backup_root": backup.as_posix(),
        "files": records,
    }
    _write_report(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install or restore a hash-gated GAP GA RTL repair."
    )
    parser.add_argument("--action", choices=("install", "restore"), required=True)
    parser.add_argument("--ndp-root", type=Path, required=True)
    parser.add_argument("--patch-root", type=Path, required=True)
    parser.add_argument("--backup-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        action = install if args.action == "install" else restore
        report = action(
            ndp_root=args.ndp_root,
            patch_root=args.patch_root,
            backup_root=args.backup_root,
            report_path=args.report,
        )
    except Exception as error:
        print(f"GAP GA RTL repair {args.action} failed: {error}")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
