#!/usr/bin/env python3
"""Independently audit a senior Conv encoder diagnostic bundle ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


EXPECTED_ROOT = "senior_conv_3x3_encoder_test_v1"


class BundleAuditError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_path(raw: str) -> PurePosixPath:
    posix = PurePosixPath(raw)
    windows = PureWindowsPath(raw)
    if (
        not raw
        or posix.is_absolute()
        or windows.is_absolute()
        or windows.anchor
        or "\\" in raw
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise BundleAuditError(f"unsafe ZIP member: {raw!r}")
    return posix


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BundleAuditError(f"JSON root is not an object: {path}")
    return value


def _bitstream_identity(path: Path, width: int) -> dict[str, Any]:
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or any(len(line) != width or set(line) - {"0", "1"} for line in lines):
        raise BundleAuditError(f"invalid {width}-bit stream: {path}")
    normalized = ("\n".join(lines) + "\n").encode("ascii")
    return {
        "line_count": len(lines),
        "line_width_bits": width,
        "logical_sha256": hashlib.sha256(normalized).hexdigest(),
    }


def audit(zip_path: Path, sidecar_path: Path) -> dict[str, Any]:
    zip_path = zip_path.resolve()
    sidecar_path = sidecar_path.resolve()
    if not zip_path.is_file() or not sidecar_path.is_file():
        raise BundleAuditError("ZIP or sidecar is missing")
    zip_sha256 = _sha256(zip_path)
    if sidecar_path.read_text(encoding="ascii") != f"{zip_sha256}  {zip_path.name}\n":
        raise BundleAuditError("ZIP sidecar differs")

    with tempfile.TemporaryDirectory(prefix="senior_conv_bundle_audit_") as temporary:
        root = Path(temporary)
        names: set[str] = set()
        with zipfile.ZipFile(zip_path, "r") as archive:
            for info in archive.infolist():
                if info.filename in names:
                    raise BundleAuditError(f"duplicate ZIP member: {info.filename}")
                names.add(info.filename)
                relative = _safe_path(info.filename)
                mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise BundleAuditError(f"ZIP contains symlink: {info.filename}")
                if info.is_dir():
                    continue
                target = root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
        files = {
            path.relative_to(root).as_posix(): path
            for path in root.rglob("*")
            if path.is_file()
        }
        if any(Path(name).suffix.lower() in {".v", ".sv"} for name in files):
            raise BundleAuditError("diagnostic bundle contains HDL")
        prefix = f"{EXPECTED_ROOT}/"
        if not files or any(not name.startswith(prefix) for name in files):
            raise BundleAuditError("ZIP does not have one expected bundle root")
        bundle = root / EXPECTED_ROOT
        manifest = _load(bundle / "MANIFEST.json")
        if (
            manifest.get("bundle_name") != EXPECTED_ROOT
            or manifest.get("server_runnable") is not False
            or manifest.get("hdl_file_count") != 0
        ):
            raise BundleAuditError("bundle safety/status identity differs")
        expected: dict[str, tuple[int, str]] = {}
        for record in manifest.get("files", []):
            if not isinstance(record, dict):
                raise BundleAuditError("invalid manifest record")
            relative = str(record.get("path", ""))
            if relative in expected:
                raise BundleAuditError(f"duplicate manifest path: {relative}")
            expected[relative] = (int(record["size_bytes"]), str(record["sha256"]))
        actual = {
            path.relative_to(bundle).as_posix(): path
            for path in bundle.rglob("*")
            if path.is_file() and path.name != "MANIFEST.json"
        }
        if set(expected) != set(actual):
            raise BundleAuditError("manifest exact set differs")
        for relative, (size, digest) in expected.items():
            path = actual[relative]
            if path.stat().st_size != size or _sha256(path) != digest:
                raise BundleAuditError(f"manifest file identity differs: {relative}")

        report = _load(bundle / "evidence" / "audit_report.json")
        if (
            report.get("status")
            != "encoder_candidate_passed_formal_server_package_blocked"
            or report.get("formal_server_package", {}).get("status")
            != "not_generated_fail_closed"
            or report.get("numeric_probe", {}).get("status") != "passed"
        ):
            raise BundleAuditError("audit evidence boundary differs")
        a128 = _bitstream_identity(
            bundle / "encoder" / "repaired_a" / "modules_dump_128b.bin", 128
        )
        b128 = _bitstream_identity(
            bundle / "encoder" / "repaired_b" / "modules_dump_128b.bin", 128
        )
        a64 = _bitstream_identity(
            bundle / "encoder" / "repaired_a" / "modules_dump_64b.bin", 64
        )
        b64 = _bitstream_identity(
            bundle / "encoder" / "repaired_b" / "modules_dump_64b.bin", 64
        )
        if a128 != b128 or a64 != b64:
            raise BundleAuditError("A/B logical bitstream identity differs")
        return {
            "status": "passed",
            "audit": "fresh_zip_independent_exact_set_and_identity",
            "zip": str(zip_path),
            "zip_sha256": zip_sha256,
            "zip_size_bytes": zip_path.stat().st_size,
            "file_count": len(files),
            "hdl_file_count": 0,
            "server_runnable": False,
            "bitstream_128b": a128,
            "bitstream_64b": a64,
            "resnet50_match_node_ids": [
                item["node_id"] for item in report["resnet50_matches"]
            ],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--sidecar", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sidecar = args.sidecar or Path(str(args.zip) + ".sha256")
    try:
        if args.report is not None and args.report.exists():
            raise FileExistsError(f"refusing to replace report: {args.report}")
        report = audit(args.zip, sidecar)
        payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.report is not None:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(payload, encoding="utf-8", newline="\n")
        print(payload, end="")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(
            json.dumps(
                {"status": "failed", "reason": str(error)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
