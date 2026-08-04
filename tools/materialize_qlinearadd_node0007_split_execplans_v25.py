from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.hashing import sha256_file
from resnet50_pipeline.operator_config_execplan_evidence import (
    create_execplan_evidence_bundle,
)


SOURCE = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-column-pair-v18"
)
OUTPUT = ROOT / (
    "artifacts/operator_config_validation/"
    "qn7v25cd"
)
PATCHSET = ROOT / (
    "contracts/ndp_patch_toolchain_"
    "qlinearadd_node0007_d_buffer_column_pair_v18.json"
)
CONTRACT = ROOT / (
    "contracts/operator_config/"
    "qlinearadd_node0007_split_workload_v25.json"
)
SOURCE_GRAPH = SOURCE / (
    "execplan/pipeline_output/graph_withbaseaddr.json"
)
SOURCE_GRAPH_SHA = (
    "2d2cc67efefb66270ca6d106d4145d812755bbf0c3d255f2840e4bde9f67468e"
)
CONTRACT_SHA = (
    "37dc6c2a0b0f4176a8e9372a29f10db8f3b6e2c630203487b3ea6041c521c9e1"
)

SEGMENTS = {
    "C": [
        "op_a_dequant",
        "op_b_dequant",
        "op_relocation_pad",
        "op_fp32_add",
    ],
    "D": [
        "op_a_dequant",
        "op_b_dequant",
        "op_relocation_pad",
        "op_fp32_add",
        "op_tail_mul",
        "op_tail_round",
    ],
}


class SplitExecplanError(ValueError):
    pass


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def subset_graph(source: dict[str, Any], ids: list[str]) -> dict[str, Any]:
    by_id = {op["id"]: op for op in source["operators"]}
    missing = [op_id for op_id in ids if op_id not in by_id]
    if missing:
        raise SplitExecplanError(f"source graph operators absent: {missing}")
    operators = [by_id[op_id] for op_id in ids]
    selected = set(ids)
    for op in operators:
        for edge in op.get("inputs", {}).values():
            source_edge = edge.get("source", {})
            if source_edge.get("type") != "operator":
                continue
            producer = source_edge.get("operator_id")
            if producer not in selected:
                raise SplitExecplanError(
                    f"{op['id']} depends on omitted producer {producer}"
                )
    graph = {
        "operators": operators,
        "params": {
            **source["params"],
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "split_workload_contract": CONTRACT.relative_to(ROOT).as_posix(),
            "split_workload_contract_sha256": CONTRACT_SHA,
        },
        "used_slices": source["used_slices"],
    }
    return graph


def main() -> int:
    graph_path = SOURCE_GRAPH
    if (
        not graph_path.is_file()
        or sha256_file(graph_path) != SOURCE_GRAPH_SHA
        or not CONTRACT.is_file()
        or sha256_file(CONTRACT) != CONTRACT_SHA
    ):
        print("immutable source/contract receipt drift", file=sys.stderr)
        return 1
    if OUTPUT.exists():
        print(f"refusing non-empty output identity: {OUTPUT}", file=sys.stderr)
        return 1
    source_graph = load_json(graph_path)
    receipts: dict[str, Any] = {}
    for name, ids in SEGMENTS.items():
        segment_root = OUTPUT / name.lower()
        segment_graph = subset_graph(source_graph, ids)
        segment_graph_path = segment_root / "graph.json"
        write_json(segment_graph_path, segment_graph)
        mappings = {
            op_id: SOURCE / "mapping" / op_id
            for op_id in ids
        }
        absent = [
            op_id for op_id, path in mappings.items() if not path.is_dir()
        ]
        if absent:
            raise SplitExecplanError(f"mapping bundles absent: {absent}")
        execplan = segment_root / "execplan"
        create_execplan_evidence_bundle(
            ndp_sim_root=ROOT / "ndp-sim",
            graph_path=segment_graph_path,
            mapping_bundles=mappings,
            output_dir=execplan,
            python_executable=Path(sys.executable),
            patchset_manifest_path=PATCHSET,
            timeout_seconds=900,
        )
        pipeline = execplan / "pipeline_output"
        sca = load_json(pipeline / "sca_cfg.json")
        receipts[name] = {
            "operators": ids,
            "operator_count": len(ids),
            "graph": segment_graph_path.relative_to(ROOT).as_posix(),
            "graph_sha256": sha256_file(segment_graph_path),
            "execplan_bundle": execplan.relative_to(ROOT).as_posix(),
            "execplan_bundle_manifest_sha256": sha256_file(
                execplan / "bundle_manifest.json"
            ),
            "execplan": (
                pipeline / "install/execplan.txt"
            ).relative_to(ROOT).as_posix(),
            "execplan_sha256": sha256_file(
                pipeline / "install/execplan.txt"
            ),
            "exec_length": sca["Exec_Length"],
            "repeat_num": sca["Repeat_Num"],
            "mapping_reused_without_remap": True,
            "empty_execplan_initial_state": True,
        }
    receipt = {
        "schema": "qlinearadd-node0007-split-execplans-v25",
        "status": "NATIVE_SPLIT_EXECPLANS_MATERIALIZED",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "source_graph_sha256": SOURCE_GRAPH_SHA,
        "split_contract_sha256": CONTRACT_SHA,
        "numeric_analysis_repeated": False,
        "workload_numeric_analysis_repeated": False,
        "functional_rtl_modified": False,
        "segments": receipts,
    }
    write_json(OUTPUT / "materialization_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
