from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v43_lc9_split_diag_package_v44 as builder


builder.INSTALL_NAME = "r5_n4_hw_v45_lc9_split_cloudrtl"
builder.VERSION = 45
builder.RTL_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
builder.PLAN_MUTABLE_SHA256 = (
    "0d1c5577f71d565c7ee4fa6a43054db458de53b41f45813ed2bb3b98be30e126"
)
builder.SERVER_RULE_SHA256 = (
    "61753f6866f49aca142545394451cd73c4e634a5aa160b066e020b7c9067cedd"
)
builder.COMMON_RULE_SHA256 = (
    "d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0"
)
builder.OBSERVER_BLOCK = builder.OBSERVER_BLOCK.replace(
    "v44 LC9_SPLIT", "v45 LC9_SPLIT"
)
cloud_rule = "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001"
if cloud_rule not in builder.RULE_IDS:
    builder.RULE_IDS.append(cloud_rule)

_matrix = builder.release_gate_matrix


def cloud_matrix():
    rows = _matrix()
    for row in rows:
        if row["gate_id"] == "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL":
            row["reason"] = (
                "LC9 split observer is rebound to approved cloud RTL 0ccae91"
            )
            row["evidence"].extend(
                [
                    "cloud changed-file causal-cone classification",
                    "cloud exact-leaf and width/depth receipt",
                    "identity mismatch remains nonblocking after compile",
                ]
            )
    return rows


builder.release_gate_matrix = cloud_matrix
_build_directory = builder.build_directory


def build_directory(output: Path) -> Path:
    package = _build_directory(output)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cloud_rtl_causal_cone_expected"] = {
        "base_commit": "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d",
        "approved_commit": builder.RTL_COMMIT,
        "changed_files": 11,
        "insertions": 497,
        "deletions": 30,
        "direct_serialized_conv_hits": [
            "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC.sv",
            "code/NDP_rtl/Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC_Inbuffer.sv",
            "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
            "code/NDP_rtl/Slice/Specialized_Array/SA_Inport/SA_Inport_Connect.sv",
            "code/NDP_rtl/includes/NDP_Parameters.svh",
        ],
        "observer_xmr_rebind_required": True,
        "server_compile_identity_difference_is_nonblocking": True,
    }
    manifest["release_gate_matrix"] = cloud_matrix()
    manifest["files"] = builder.base.package_records(package)
    builder.base.write_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = builder.base.package_records(package)
    builder.base.write_json(manifest_path, manifest)
    return package


builder.build_directory = build_directory


if __name__ == "__main__":
    raise SystemExit(builder.main())
