from __future__ import annotations

import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v72_sourcebound_successor_v73 as builder

builder.INSTALL = "r5_n4_hw_v74_sourcebound_epoch_diag"
builder.SOURCE_ZIP = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_serialized_node0004/"
    "r5_n4_hw_v72_token_origin_accept_diag/r5_n4_hw_v72_token_origin_accept_diag.zip"
)
builder.SB = ROOT / "outputs/conv_node0004_v72_return_v74_successor/source_bound"
builder.DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v72_return_v74_successor/build"

if __name__ == "__main__":
    catalog = builder.SB / "probe_catalog.json"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "outputs/conv_node0004_v72_return_v73_successor/source_bound/probe_catalog.json",
        catalog,
    )
    raise SystemExit(builder.main())
