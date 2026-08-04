"""Audit the four unmaterialized y_zero_point=0 Requant shape holdouts.

This is a read-only LOCAL_E2 planning audit.  It does not emit operator JSON,
invoke the native toolchain, or create a server package.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


REPORT = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-family-classification-v1/report.json"
)
NODE0001 = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-two-stage-e2-v1"
)
PACKAGE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "rq_node0001_guardonly_sfu_eventedge_stock_v1.zip"
)
OUTPUT = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-zero-point-shape-holdouts-v1/analysis.json"
)
EXPECTED_SHAPES = (
    "16x64x56x56",
    "16x128x28x28",
    "16x256x14x14",
    "16x512x7x7",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binding(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def tree_identity(root: Path, relative: Path) -> dict[str, Any]:
    base = root / relative
    files = [
        {
            "path": path.relative_to(base).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in base.rglob("*") if item.is_file())
    ]
    encoded = json.dumps(
        files, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "path": relative.as_posix(),
        "file_count": len(files),
        "tree_sha256": hashlib.sha256(encoded).hexdigest(),
    }


def build(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    family = json.loads((root / REPORT).read_text(encoding="utf-8"))
    by_shape: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in family["records"]:
        if (
            record["qparams"]["y_zero_point"] == 0
            and record["request_id"] != "r5:hwop-0001-01"
        ):
            by_shape[record["shape_signature"]].append(record)
    if tuple(sorted(by_shape)) != tuple(sorted(EXPECTED_SHAPES)):
        raise ValueError(f"holdout shape set drifted: {sorted(by_shape)}")

    holdouts = []
    for shape in EXPECTED_SHAPES:
        records = by_shape[shape]
        representative = records[0]
        logical_shape = representative["logical_shape"]
        channels = int(representative["channels"])
        spatial = int(logical_shape[2]) * int(logical_shape[3])
        shard_count = channels // 8
        holdouts.append(
            {
                "shape_signature": shape,
                "representative_request_id": representative["request_id"],
                "representative_node_id": representative["identity"]["node_id"],
                "same_shape_request_count": len(records),
                "same_shape_request_ids": [item["request_id"] for item in records],
                "logical_shape": logical_shape,
                "y_zero_point": 0,
                "channels": channels,
                "channel_tail_mod8": channels % 8,
                "spatial_elements_per_channel": spatial,
                "h_to_w_product_exact": True,
                "lane_count": 8,
                "shard_count": shard_count,
                "three_wave_occurrence_forecast_not_emission_authority": (
                    3 * shard_count
                ),
                "two_stage_count_forecast_not_emission_authority": (
                    6 * shard_count
                ),
                "status": "LOCAL_E2_PARAMETERIZATION_PENDING",
                "required_next_gates": [
                    "typed request and W3 tensor identity binding",
                    "shape-derived LC/MSE/Buffer schedule and byte conservation",
                    "strict guard and round address-bound JSON materialization",
                    "empty-cache native mapping and bitstream rebuild",
                    "execplan/SCA lifecycle and stage0-D-to-stage1-A alias proof",
                    "config-bound full-W3 guard and UINT8 bit-exact replay",
                    "second isolated deterministic rebuild",
                ],
            }
        )

    result: dict[str, Any] = {
        "schema": "requant-zero-point-zero-shape-holdout-audit-v1",
        "status": "LOCAL_E2_PARAMETERIZATION_STARTED_NO_JSON_EMITTED",
        "scope": "four unmaterialized RequantizeUint8 y_zero_point=0 shapes",
        "read_receipt": [
            binding(root, Path(".agents/agent.md")),
            binding(root, Path(".agents/plan.md")),
            binding(root, Path(".agents/rules/生成前必读索引.md")),
            binding(root, Path(".agents/rules/算子配置规则.md")),
            binding(root, Path(".agents/rules/NDP硬件字段语义.md")),
            binding(root, Path(".agents/rules/服务器测试包生成规则.md")),
            binding(root, Path(".agents/rules/RequantizeUint8算子配置规则.md")),
            binding(root, Path(".agents/rules/最小双Stage生命周期规则.md")),
            binding(root, Path("NDP_copy01/README_HARDWARE_SIM_ENTRY.md")),
            binding(root, REPORT),
        ],
        "frozen_node0001_identity": tree_identity(root, NODE0001),
        "package_ready_not_run_identity": binding(root, PACKAGE),
        "holdouts": holdouts,
        "boundaries": {
            "node0001_asset_modified": False,
            "operator_json_generated": False,
            "mapping_or_bitstream_generated": False,
            "execplan_or_sca_generated": False,
            "server_package_generated": False,
            "server_uploaded_or_run": False,
            "rtl_modified": False,
            "candidate_release": False,
            "formal_target_config": False,
            "evidence_level": "LOCAL_E2_PLANNING_ONLY",
        },
        "blocker_delta": {
            "keep": [
                "B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2",
                "B_REQUANT_GUARD_DYNAMIC_DATA_PATH",
                "B_REQUANT_SERVER_E4_E5",
            ],
            "close": [],
            "add": [],
        },
        "rule_delta_proposal": [],
    }
    canonical = json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    result["analysis_sha256"] = hashlib.sha256(canonical).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build(args.project_root)
    output = args.output
    if not output.is_absolute():
        output = args.project_root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"output": str(output), "status": result["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
