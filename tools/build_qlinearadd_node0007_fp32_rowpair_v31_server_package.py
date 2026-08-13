from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records


PKG = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_qadd_n7_split_c_rowpairfix_v30"
TARGET_NAME = "r5_qadd_n7_split_c_rowpairfix_rule_v31"
SOURCE = PKG / SOURCE_NAME
SOURCE_ZIP = PKG / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "9c791561aab98670ab42c14e9849bdc34f1849319d892b47eaa89102fbf4d194"
TARGET = PKG / TARGET_NAME
ZIP = PKG / f"{TARGET_NAME}.zip"

RULES = {
    "agent": ROOT / ".agents/agent.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common": ROOT / ".agents/rules/算子配置规则.md",
    "hardware": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}

ALIASES = {
    "agent": "agent",
    "index": "index",
    "generation_index": "index",
    "server": "server",
    "server_package": "server",
    "common": "common",
    "common_operator": "common",
    "hardware": "hardware",
    "hardware_fields": "hardware",
    "qadd": "qadd",
    "qlinearadd": "qadd",
    "tail": "tail",
    "exact_tail": "tail",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def materialize(parent: Path) -> Path:
    out = parent / TARGET_NAME
    shutil.copytree(SOURCE, out)
    for path in out.rglob("*"):
        if not path.is_file():
            continue
        if path.name == "TEST_PACKAGE_MANIFEST.json":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, TARGET_NAME),
                encoding="utf-8",
                newline="\n",
            )

    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET_NAME
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_fp32_rowpair_v31_server_package.py"
    )
    manifest["provenance"]["successor_reason"] = (
        "fresh identity for post-generation current QAdd rule receipt; "
        "v30 functional/config/observer bytes frozen"
    )
    manifest["source_assets"]["fp32_rowpair_v30_source_zip"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_SHA,
        "immutable": True,
        "runtime_identity": "QUARANTINED_UNRELEASED_STALE_RULE_ALIAS_RECEIPT",
    }

    receipts = manifest["rule_receipts"]
    for alias, canonical in ALIASES.items():
        path = RULES[canonical]
        record = dict(receipts.get(alias, {}))
        record.update(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "current_match": True,
            }
        )
        receipts[alias] = record
    qadd_ids = set(receipts["qlinearadd"].get("applicable_rule_ids", []))
    qadd_ids.add("CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001")
    receipts["qlinearadd"]["applicable_rule_ids"] = sorted(qadd_ids)
    receipts["qadd"]["applicable_rule_ids"] = sorted(qadd_ids)

    manifest["final_zip_rule_self_audit"] = {
        "required": True,
        "status": "PENDING_POST_BUILD_DIRECT_FINAL_ZIP_AUDIT",
    }
    manifest["files"] = file_records(out, exclude_manifest=True)
    write_json(manifest_path, manifest)
    return out


def main() -> int:
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise ValueError("frozen v30 source ZIP differs")
    if TARGET.exists() or ZIP.exists():
        raise ValueError("fresh v31 identity already exists")
    with tempfile.TemporaryDirectory(prefix="qadd-v31-a-") as first, tempfile.TemporaryDirectory(
        prefix="qadd-v31-b-"
    ) as second:
        package_a = materialize(Path(first))
        package_b = materialize(Path(second))
        zip_a = Path(first) / f"{TARGET_NAME}.zip"
        zip_b = Path(second) / f"{TARGET_NAME}.zip"
        deterministic_zip(package_a, zip_a)
        deterministic_zip(package_b, zip_b)
        if sha(zip_a) != sha(zip_b):
            raise ValueError("deterministic double build differs")
        shutil.copytree(package_a, TARGET)
        shutil.copy2(zip_a, ZIP)
    sidecar = Path(str(ZIP) + ".sha256")
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    print(
        json.dumps(
            {
                "zip": str(ZIP),
                "bytes": ZIP.stat().st_size,
                "sha256": sha(ZIP),
                "sidecar_sha256": sha(sidecar),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
