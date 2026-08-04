#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline import gap_complete_config_only as complete  # noqa: E402
from resnet50_pipeline import gap_sum_config_only as gap_sum  # noqa: E402
from resnet50_pipeline.hashing import sha256_file  # noqa: E402


SUM_CONFIG_ROOT = Path("configs/gap_sum_stage1_byte_slots_v2")
SUM_ARTIFACT_ROOT = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-sum-stage1-byte-slots-local-e2-v2"
)
SUM_CONTRACT = Path(
    "contracts/operator_config/gap_sum_stage1_byte_slots_local_e2_v2.json"
)
COMPLETE_CONFIG_ROOT = Path("configs/gap_complete_stage1_byte_slots_v2")
COMPLETE_ARTIFACT_ROOT = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-complete-stage1-byte-slots-local-e2-v2"
)
COMPLETE_CONTRACT = Path(
    "contracts/operator_config/"
    "gap_node0071_stage1_byte_slots_local_e2_v2.json"
)
REPORT = Path(
    "artifacts/operator_config_validation/"
    "r5-gap-node0071-stage1-byte-slots-v16/local_rebuild_report.json"
)


class RebuildError(ValueError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def leaf_diff(left: Any, right: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                result.append(
                    {
                        "path": child,
                        "old": left.get(key, "<MISSING>"),
                        "new": right.get(key, "<MISSING>"),
                    }
                )
            else:
                result.extend(leaf_diff(left[key], right[key], child))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        for index in range(max(len(left), len(right))):
            child = f"{prefix}[{index}]"
            if index >= len(left) or index >= len(right):
                result.append(
                    {
                        "path": child,
                        "old": left[index] if index < len(left) else "<MISSING>",
                        "new": right[index] if index < len(right) else "<MISSING>",
                    }
                )
            else:
                result.extend(leaf_diff(left[index], right[index], child))
        return result
    return [] if left == right else [{"path": prefix, "old": left, "new": right}]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> dict[str, Any]:
    outputs = (
        SUM_CONFIG_ROOT,
        SUM_ARTIFACT_ROOT,
        SUM_CONTRACT,
        COMPLETE_CONFIG_ROOT,
        COMPLETE_ARTIFACT_ROOT,
        COMPLETE_CONTRACT,
        REPORT,
    )
    existing = [path.as_posix() for path in outputs if (ROOT / path).exists()]
    if existing:
        raise RebuildError(f"fresh outputs required: {existing}")

    sum_result = gap_sum.build_local_e2(
        ROOT,
        config_root=ROOT / SUM_CONFIG_ROOT,
        artifact_root=ROOT / SUM_ARTIFACT_ROOT,
    )
    sum_contract = gap_sum.build_contract(ROOT, ROOT / SUM_ARTIFACT_ROOT)
    write_json(ROOT / SUM_CONTRACT, sum_contract)

    complete.SUM_CONFIG_ROOT = SUM_CONFIG_ROOT
    complete.SUM_ARTIFACT_ROOT = SUM_ARTIFACT_ROOT
    complete.SUM_CONTRACT = SUM_CONTRACT
    complete.CONFIG_ROOT = COMPLETE_CONFIG_ROOT
    complete.ARTIFACT_ROOT = COMPLETE_ARTIFACT_ROOT
    complete.CONTRACT = COMPLETE_CONTRACT
    complete_result = complete.build_local_e2(ROOT)

    old_stage1 = load_json(
        ROOT / "configs/gap_sum_config_only_v1/stage-1/config.json"
    )
    new_stage1 = load_json(ROOT / SUM_CONFIG_ROOT / "stage-1/config.json")
    stage1_diff = leaf_diff(old_stage1, new_stage1)
    expected_paths = {
        "buffer_loop_configs.GROUP0.COL_LC.end",
        "buffer_loop_configs.GROUP0.COL_LC.stride",
        "buffer_loop_configs.GROUP1.COL_LC.end",
        "buffer_loop_configs.GROUP1.COL_LC.stride",
    }
    if {item["path"] for item in stage1_diff} != expected_paths:
        raise RebuildError(f"stage1 config diff differs: {stage1_diff}")
    for stage in range(2, 7):
        if load_json(
            ROOT / f"configs/gap_sum_config_only_v1/stage-{stage}/config.json"
        ) != load_json(ROOT / SUM_CONFIG_ROOT / f"stage-{stage}/config.json"):
            raise RebuildError(f"stage{stage} config drifted")

    bitstreams = []
    for stage in range(1, 7):
        old = (
            ROOT
            / "artifacts/operator_config_validation/"
            "r5-gap-sum-config-only-local-e2-v1/install/cfg_pkg"
            / f"gap_sum_config_only_s{stage}_128b.bin"
        )
        new = (
            ROOT
            / SUM_ARTIFACT_ROOT
            / "install/cfg_pkg"
            / f"gap_sum_config_only_s{stage}_128b.bin"
        )
        bitstreams.append(
            {
                "stage": stage,
                "old_sha256": sha256_file(old),
                "new_sha256": sha256_file(new),
                "changed": sha256_file(old) != sha256_file(new),
            }
        )
    if [item["stage"] for item in bitstreams if item["changed"]] != [1]:
        raise RebuildError("only stage1 bitstream may change")

    old_complete = ROOT / (
        "artifacts/operator_config_validation/"
        "r5-gap-node0071-complete-config-only-local-e2-v1"
    )
    new_complete = ROOT / COMPLETE_ARTIFACT_ROOT
    preserved_complete = {}
    for relative in (
        "mapping/run-a/mul/modules_dump_128b.bin",
        "mapping/run-a/round/modules_dump_128b.bin",
        "install/cfg_pkg/gap_node0071_tail_mul_128b.bin",
        "install/cfg_pkg/gap_node0071_tail_round_128b.bin",
        "install/execplan.txt",
        "sca_cfg.json",
        "sca_cfg_D.json",
    ):
        old = old_complete / relative
        new = new_complete / relative
        preserved_complete[relative] = {
            "old_sha256": sha256_file(old),
            "new_sha256": sha256_file(new),
            "equal": sha256_file(old) == sha256_file(new),
        }
    if not all(item["equal"] for item in preserved_complete.values()):
        raise RebuildError("tail/execplan/SCA semantic payload drifted")

    fill = gap_sum.stage1_buffer_byte_lane_contract(new_stage1)
    report = {
        "schema": "gap-node0071-stage1-byte-slots-local-rebuild-v16",
        "status": "CONFIG_FUNCTIONAL_FIX_LOCAL_E2",
        "valid": True,
        "root_cause": "STAGE1_8B_READ_REPEATS_BUFFER_BYTE_LANE_ZERO",
        "rtl_equation": {
            "bank": "low5(col_base + buf_spatial_stride) >> 2",
            "byte": "low5(col_base + buf_spatial_stride) & 3",
            "buffer_array_ready":
                "all four byte-valid bits in every active bank",
        },
        "minimal_config_diff": stage1_diff,
        "stage1_buffer_byte_lane_contract": fill,
        "sum_result": sum_result,
        "sum_contract": SUM_CONTRACT.as_posix(),
        "sum_contract_sha256": sha256_file(ROOT / SUM_CONTRACT),
        "complete_result": complete_result,
        "complete_contract": COMPLETE_CONTRACT.as_posix(),
        "complete_contract_sha256": sha256_file(ROOT / COMPLETE_CONTRACT),
        "sum_bitstreams": bitstreams,
        "preserved_complete_payloads": preserved_complete,
        "numeric_golden_regenerated": False,
        "frozen_w3_input_and_golden_reused": True,
        "config_bound_integration_replayed": True,
        "functional_rtl_modified": False,
    }
    write_json(ROOT / REPORT, report)
    return report


def main() -> int:
    try:
        result = build()
    except Exception as error:
        print(f"GAP node0071 stage1 byte-slot rebuild failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
