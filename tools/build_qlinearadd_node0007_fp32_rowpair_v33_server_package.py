from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_qlinearadd_node0007_fp32_rowpair_v32_server_package as base


base.SOURCE_NAME = "r5_qadd_n7_crow32_v32"
base.TARGET_NAME = "r5_qadd_n7_crow32_v33"
base.SOURCE = base.PKG / base.SOURCE_NAME
base.SOURCE_ZIP = base.PKG / f"{base.SOURCE_NAME}.zip"
base.SOURCE_SHA = "cf95fdab90542480d6aeb2f6b084002b48f2d21b34165c23cb099a5aa8386da0"
base.TARGET = base.PKG / base.TARGET_NAME
base.ZIP = base.PKG / f"{base.TARGET_NAME}.zip"


def fix_sca_paths(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    prefix = f"install/cfg_pkg/{base.TARGET_NAME}/"
    for key, record in value.items():
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            continue
        old = record["path"].replace("\\", "/")
        suffix = old.split(f"/{base.TARGET_NAME}/", 1)[-1]
        while suffix.startswith("install/"):
            suffix = suffix.removeprefix("install/")
        if key == "ExecutionPlan":
            suffix = "execplan.txt"
        elif key.endswith("_config"):
            suffix = "cfg_pkg/" + Path(suffix).name
        record["path"] = prefix + "install/" + suffix
    base.write_json(path, value)


base.fix_sca_paths = fix_sca_paths
original_materialize = base.materialize


def materialize(parent: Path) -> Path:
    out = original_materialize(parent)
    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["source_assets"].pop("fp32_rowpair_v31_source_zip")
    manifest["source_assets"]["fp32_rowpair_v32_source_zip"] = record
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_fp32_rowpair_v33_server_package.py"
    )
    manifest["provenance"]["successor_reason"] = (
        "fix exact SCA installed-tree paths by record kind: execplan under install/, "
        "bitstreams under install/cfg_pkg/, tensors under install/<stage>/"
    )
    manifest["files"] = base.file_records(out, exclude_manifest=True)
    base.write_json(manifest_path, manifest)
    return out


base.materialize = materialize

if __name__ == "__main__":
    raise SystemExit(base.main())
