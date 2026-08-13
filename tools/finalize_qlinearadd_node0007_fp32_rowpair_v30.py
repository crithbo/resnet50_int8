from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_BOOTSTRAP = Path(__file__).resolve().parents[1]
if str(ROOT_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(ROOT_BOOTSTRAP))

from tools.build_qlinearadd_node0007_fp32_rowpair_v30 import (
    CFG_REL,
    OUT_REL,
    ROOT,
    STAGES,
    build_fixed_config,
    leaf_diffs,
    sha,
)
from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    build_configs as build_source_configs,
)


def main() -> int:
    output = ROOT / OUT_REL
    pipeline = output / "execplan/pipeline_output"
    source = build_source_configs(ROOT)
    approved, proof = build_fixed_config(source["op_fp32_add"])
    final_path = (
        pipeline
        / "jsons/op_fp32_add_resnet50_qadd_node0007_fp32_add.json"
    )
    final_value = json.loads(final_path.read_text(encoding="utf-8"))
    materialized_diffs = leaf_diffs(approved, final_value)
    semantic_diffs = [
        item
        for item in materialized_diffs
        if not (
            item["path"].endswith(".base_addr")
            and int(item["old"], 0) == int(item["new"], 0)
        )
    ]
    if semantic_diffs:
        raise ValueError(
            f"final JSON differs from approved config: {semantic_diffs}"
        )
    required = [
        pipeline / "install/execplan.txt",
        pipeline / "sca_cfg.json",
        pipeline / "sca_cfg_D.json",
        pipeline
        / "install/cfg_pkg/"
        "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin",
        output / "execplan/execplan_validation_report.json",
        output / "mapping/op_fp32_add/artifact_validation_report.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"required targeted outputs absent: {missing}")
    validation = json.loads(
        (output / "execplan/execplan_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    if not validation.get("valid"):
        raise ValueError("targeted execplan validation failed")
    receipt = {
        "schema": "qlinearadd-node0007-fp32-rowpair-build-v30",
        "status": "LOCAL_TARGETED_CONFIG_CORRECTION_MATERIALIZED",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "changed_stage": "op_fp32_add",
        "stage_order": STAGES,
        "authorized_leaf_deltas": leaf_diffs(source["op_fp32_add"], approved),
        "rowpair_proof": proof,
        "final_json": {
            "path": final_path.relative_to(ROOT).as_posix(),
            "bytes": final_path.stat().st_size,
            "sha256": sha(final_path),
        },
        "planner_base_format_only_diffs": materialized_diffs,
        "execplan_validation": {
            "path": (
                output / "execplan/execplan_validation_report.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha(
                output / "execplan/execplan_validation_report.json"
            ),
            "valid": True,
        },
        "targeted_outputs": {
            path.relative_to(ROOT).as_posix(): sha(path) for path in required
        },
        "full_address_enumeration_repeated": False,
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "qparams_tail_golden_changed": False,
        "functional_rtl_modified": False,
    }
    path = output / "build_receipt.json"
    path.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"valid": True, "receipt": str(path), "sha256": sha(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
