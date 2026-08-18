#!/usr/bin/env python3
"""Promote the fully gated v94b staging tree and recreate its exact ZIP."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v94b_tbvcd_wrdrain"
OUT = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def main() -> int:
    first = json.loads((OUT / "first_fresh_extra_audit/validation.json").read_text(encoding="utf-8"))
    required = [
        "tb_vcd_contract", "mode_selector", "hdl_lexical", "runtime_preflight",
        "normalizer_arity", "runner_resilience", "post_sim_return", "active_rule_registry",
    ]
    gates = [json.loads((OUT / f"gates/{name}.json").read_text(encoding="utf-8")) for name in required]
    if first.get("pass") is not True or any(item.get("pass") is not True and item.get("valid") is not True for item in gates):
        raise SystemExit("v94b promotion refused: prerequisite gate failed")
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("package_id") != PACKAGE:
        raise SystemExit("v94b promotion refused: package identity differs")
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["activation_epoch"] = "tb-vcd-exit-mechanism-consistency-v3"
    manifest["first_fresh_validation"] = "external: first_fresh_extra_audit/validation.json"
    manifest["release_admission_required"] = True
    write_json(manifest_path, manifest)

    temporary = ZIP.with_name(f".{ZIP.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(TREE.parent).as_posix(), (2026, 8, 14, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise SystemExit("v94b promoted ZIP CRC failure")
    os.replace(temporary, ZIP)
    build_path = OUT / "build_receipt.json"
    build = json.loads(build_path.read_text(encoding="utf-8"))
    build.update({"status": "PACKAGE_READY_NOT_RUN", "zip_bytes": ZIP.stat().st_size, "zip_sha256": sha(ZIP), "promotion_epoch": "tb-vcd-exit-mechanism-consistency-v3"})
    write_json(build_path, build)
    (OUT / f"{PACKAGE}.zip.sha256").write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    print(ZIP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
