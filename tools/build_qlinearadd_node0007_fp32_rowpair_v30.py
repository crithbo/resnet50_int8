from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_evidence_bundle import (
    create_mapping_evidence_bundle,
)
from resnet50_pipeline.operator_config_execplan_evidence import (
    create_execplan_evidence_bundle,
)
from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    PATCHSET_REL,
    ROOT_REL as SOURCE_ROOT_REL,
    build_configs as build_source_configs,
    graph_spec,
)


OUT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-rowpair-v30"
)
CFG_REL = Path("configs/native_ndp_sim/qlinearadd_node0007_fp32_rowpair_v30")
SOURCE_NATIVE = Path("ndp-sim/jsons/decode_add_fp32N_fp32N_fp32N.json")
STAGES = ["op_a_dequant", "op_b_dequant", "op_relocation_pad", "op_fp32_add"]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def leaf_diffs(before: Any, after: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(before, dict) and isinstance(after, dict):
        out: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                out.append({"path": child, "old": before.get(key), "new": after.get(key)})
            else:
                out.extend(leaf_diffs(before[key], after[key], child))
        return out
    if isinstance(before, list) and isinstance(after, list):
        out = []
        for index in range(max(len(before), len(after))):
            child = f"{prefix}[{index}]"
            old = before[index] if index < len(before) else None
            new = after[index] if index < len(after) else None
            out.extend(leaf_diffs(old, new, child))
        return out
    return [{"path": prefix, "old": before, "new": after}] if before != after else []


def build_fixed_config(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    value = copy.deepcopy(source)
    for lc in ("LC1", "LC2", "LC3"):
        if value["dram_loop_configs"][lc]["end"] != 18816:
            raise ValueError(f"{lc} preimage differs")
        value["dram_loop_configs"][lc]["end"] = 9408
    for group in ("GROUP0", "GROUP1", "GROUP2"):
        col = value["buffer_loop_configs"][group]["COL_LC"]
        if (col["start"], col["end"], col["stride"]) != (0, 16, 16):
            raise ValueError(f"{group} COL preimage differs")
        col["end"] = 32
    for stream_name in ("stream0", "stream1", "stream2"):
        stream = value["stream_engine"][stream_name]
        if stream["idx_size"][:2] != [0, 15] or stream["dim_stride"][:2] != [
            16,
            301056,
        ]:
            raise ValueError(f"{stream_name} transaction preimage differs")
        stream["idx_size"][1] = 31
        stream["dim_stride"][0] = 32
    records = {}
    for stream_name, group in zip(
        ("stream0", "stream1", "stream2"), ("GROUP0", "GROUP1", "GROUP2")
    ):
        stream = value["stream_engine"][stream_name]
        cols = list(
            range(
                value["buffer_loop_configs"][group]["COL_LC"]["start"],
                value["buffer_loop_configs"][group]["COL_LC"]["end"],
                value["buffer_loop_configs"][group]["COL_LC"]["stride"],
            )
        )
        windows = [[col, col + int(stream["buf_spatial_size"])] for col in cols]
        ordered_addresses = [
            int(stream["base_addr"], 0) + outer * 301056 + inner * 32
            for outer in range(8)
            for inner in range(9408)
        ]
        packed = b"".join(address.to_bytes(8, "little") for address in ordered_addresses)
        records[stream_name] = {
            "transaction_bytes": 32,
            "inner_occurrences": 9408,
            "outer_occurrences": 8,
            "total_occurrences": len(ordered_addresses),
            "total_bytes": len(ordered_addresses) * 32,
            "column_windows": windows,
            "window_union_exact_0_32": windows == [[0, 16], [16, 32]],
            "first_address": hex(ordered_addresses[0]),
            "last_address": hex(ordered_addresses[-1]),
            "ordered_address_sha256": hashlib.sha256(packed).hexdigest(),
        }
    proof = {
        "schema": "qlinearadd-node0007-fp32-rowpair-proof-v30",
        "valid": all(
            record["total_bytes"] == 2408448
            and record["window_union_exact_0_32"]
            for record in records.values()
        ),
        "active_rtl_equation": (
            "buf2arm_rreq_ready=&(~buffer_mask|"
            "(&valid_buf[bank][row]&~arm_clear_reg[row]))"
        ),
        "buffer_physical_row_bytes": 32,
        "mse_window_bytes": 16,
        "native_oracle": {
            "path": SOURCE_NATIVE.as_posix(),
            "sha256": sha(ROOT / SOURCE_NATIVE),
            "same_transaction_and_window_structure": True,
        },
        "records": records,
        "numeric_values_recomputed": False,
        "workload_values_changed": False,
        "address_coverage_reproved": True,
    }
    if not proof["valid"]:
        raise ValueError("row-pair coverage proof failed")
    return value, proof


def subset_graph() -> dict[str, Any]:
    source = graph_spec()
    by_id = {operator["id"]: operator for operator in source["operators"]}
    return {
        "operators": [by_id[name] for name in STAGES],
        "params": {
            **source["params"],
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "fp32_rowpair_fix": True,
        },
        "used_slices": source["used_slices"],
    }


def main() -> int:
    output = ROOT / OUT_REL
    config_root = ROOT / CFG_REL
    if output.exists() or config_root.exists():
        print("fresh v30 materialization paths required", file=sys.stderr)
        return 1
    source_configs = build_source_configs(ROOT)
    fixed, proof = build_fixed_config(source_configs["op_fp32_add"])
    output.mkdir(parents=True)
    config_root.mkdir(parents=True)
    for stage, config in source_configs.items():
        write_json(config_root / f"{stage}.json", fixed if stage == "op_fp32_add" else config)
    graph_path = output / "graph.json"
    write_json(graph_path, subset_graph())

    mapping_root = output / "mapping/op_fp32_add"
    create_mapping_evidence_bundle(
        ndp_sim_root=ROOT / "ndp-sim",
        config_path=config_root / "op_fp32_add.json",
        output_dir=mapping_root,
        python_executable=Path(sys.executable),
        patchset_manifest_path=ROOT / PATCHSET_REL,
        heuristic_iterations=2_000,
        heuristic_restarts=4,
        timeout_seconds=600,
    )
    source_root = ROOT / SOURCE_ROOT_REL
    mappings = {
        stage: (
            mapping_root
            if stage == "op_fp32_add"
            else source_root / "mapping" / stage
        )
        for stage in STAGES
    }
    execplan = output / "execplan"
    create_execplan_evidence_bundle(
        ndp_sim_root=ROOT / "ndp-sim",
        graph_path=graph_path,
        mapping_bundles=mappings,
        output_dir=execplan,
        python_executable=Path(sys.executable),
        patchset_manifest_path=ROOT / PATCHSET_REL,
        timeout_seconds=900,
    )
    final_json = (
        execplan
        / "pipeline_output/jsons/"
        "op_fp32_add_resnet50_qadd_node0007_fp32_add.json"
    )
    final_value = json.loads(final_json.read_text(encoding="utf-8"))
    final_fixed, final_proof = build_fixed_config(source_configs["op_fp32_add"])
    if leaf_diffs(final_fixed, final_value):
        raise ValueError("final materialized FP32 JSON differs from approved row-pair config")
    receipt = {
        "schema": "qlinearadd-node0007-fp32-rowpair-build-v30",
        "status": "LOCAL_CONFIG_CORRECTION_MATERIALIZED",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "source_root": SOURCE_ROOT_REL.as_posix(),
        "changed_stage": "op_fp32_add",
        "unchanged_mapping_reused": STAGES[:-1],
        "changed_mapping_empty_initial_state": True,
        "execplan_empty_initial_state": True,
        "authorized_leaf_deltas": leaf_diffs(
            source_configs["op_fp32_add"], fixed
        ),
        "rowpair_proof": proof,
        "final_materialized_rowpair_proof": final_proof,
        "final_json": {
            "path": final_json.relative_to(ROOT).as_posix(),
            "bytes": final_json.stat().st_size,
            "sha256": sha(final_json),
        },
        "execplan_bundle_manifest_sha256": sha(execplan / "bundle_manifest.json"),
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "qparams_tail_golden_changed": False,
        "functional_rtl_modified": False,
    }
    write_json(output / "build_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
