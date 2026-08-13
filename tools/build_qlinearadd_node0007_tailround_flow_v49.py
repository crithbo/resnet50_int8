"""Build the fresh QAdd v49 release with canonical rule-receipt paths."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_qlinearadd_node0007_tailround_flow_v48 as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_qadd_n7_tailround_flow_v48"
TARGET = "r5_qadd_n7_tailround_flow_v49"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v48-package/r5_qadd_n7_tailround_flow_v48.zip"
SOURCE_SHA = "e52787879f400c3d129d51a83b8672cd3569066135139084bca6c813548c5486"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v49-package"
OUT_ZIP = OUT / f"{TARGET}.zip"
RULES = {
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def extract(destination: Path) -> Path:
    if sha(SOURCE) != SOURCE_SHA:
        raise BuildError("exact v48 source differs")
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise BuildError("source CRC failed")
        roots: set[str] = set(); seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename); mode = (info.external_attr >> 16) & 0xFFFF
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or info.filename in seen or stat.S_ISLNK(mode):
                raise BuildError(f"unsafe source member: {info.filename}")
            roots.add(pure.parts[0]); seen.add(info.filename)
        if roots != {SOURCE_NAME}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    source = destination / SOURCE_NAME; target = destination / TARGET; source.rename(target)
    return target


def update(package: Path) -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.TARGET = TARGET
    base.replace_identity(package)
    readme = package / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nV49 canonicalizes package-local current rule paths; all runtime, diagnostic, functional and timeout semantics are byte-equivalent after identity normalization.\n", encoding="utf-8", newline="\n")
    base.update_path_budget(package)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET
    manifest["rule_receipts"] = {name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)} for name, path in RULES.items()}
    manifest["successor"]["unreleased_intermediate_source"] = {"install_name": SOURCE_NAME, "sha256": SOURCE_SHA, "status": "QUARANTINED_PACKAGE_RULE_PATH_ENCODING_INVALID"}
    manifest["successor"]["changed_surface"] = ["identity", "manifest canonical rule paths", "README"]
    manifest["final_zip_rule_self_audit"] = {"required": True, "status": "PENDING_EXACT_ZIP_AUDIT"}
    manifest["provenance"]["generator"] = Path(__file__).relative_to(ROOT).as_posix()
    manifest["files"] = base.records(package)
    write_json(manifest_path, manifest)


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(f"{TARGET}/{path.relative_to(package).as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.create_system = 3; info.external_attr = (0o100644 & 0xFFFF) << 16; info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> int:
    if OUT_ZIP.exists() or (OUT / "build_receipt.json").exists():
        raise BuildError(f"fresh output exists: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="q49a-") as first, tempfile.TemporaryDirectory(prefix="q49b-") as second:
        a = extract(Path(first)); b = extract(Path(second)); update(a); update(b)
        za = Path(first) / f"{TARGET}.zip"; zb = Path(second) / f"{TARGET}.zip"
        deterministic_zip(a, za); deterministic_zip(b, zb)
        if za.read_bytes() != zb.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {"schema": "qadd-tailround-flow-v49-build-v1", "status": "BUILT_PENDING_FINAL_AUDIT", "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": sha(OUT_ZIP)}, "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": sha(sidecar)}, "source_v48_sha256": SOURCE_SHA, "deterministic_double_build": True, "runtime_diagnostic_functional_timeout_frozen": True, "numeric_workload_config_golden_repeated": False, "server_action": False}
    write_json(OUT / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
