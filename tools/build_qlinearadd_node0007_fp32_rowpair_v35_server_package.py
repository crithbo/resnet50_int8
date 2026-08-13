from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_qlinearadd_node0007_fp32_rowpair_v34_server_package as prior

base = prior.base
base.SOURCE_NAME = "r5_qadd_n7_crow32_v34"
base.TARGET_NAME = "r5_qadd_n7_crow32_v35"
base.SOURCE = base.PKG / base.SOURCE_NAME
base.SOURCE_ZIP = base.PKG / f"{base.SOURCE_NAME}.zip"
base.SOURCE_SHA = "7430f2020ffe4217b839f10446b4ad54cd2df75a4b41159342c07da133bf75b2"
base.TARGET = base.PKG / base.TARGET_NAME
base.ZIP = base.PKG / f"{base.TARGET_NAME}.zip"


def materialize(parent: Path) -> Path:
    out = prior.materialize(parent)
    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["source_assets"].pop("fp32_rowpair_v33_source_zip")
    manifest["source_assets"]["fp32_rowpair_v34_source_zip"] = record
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_fp32_rowpair_v35_server_package.py"
    )
    manifest["provenance"]["successor_reason"] = (
        "path-budget guard success is silent so safe compile/finalizer stderr remains clean; "
        "v34 config/bitstream/observer/SCA/runner control flow frozen"
    )
    manifest["files"] = base.file_records(out, exclude_manifest=True)
    base.write_json(manifest_path, manifest)
    return out


base.materialize = materialize

if __name__ == "__main__":
    raise SystemExit(base.main())
