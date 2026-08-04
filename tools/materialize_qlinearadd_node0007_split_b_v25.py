from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.address_bound_config import bind_config_addresses
from resnet50_pipeline.hashing import sha256_file
from resnet50_pipeline.operator_config_evidence_bundle import (
    create_mapping_evidence_bundle,
)
from resnet50_pipeline.operator_config_execplan_evidence import (
    create_execplan_evidence_bundle,
)


SOURCE = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-column-pair-v18"
)
OUTPUT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-split-workloads-v25-native-b"
)
PATCHSET = ROOT / (
    "contracts/ndp_patch_toolchain_"
    "qlinearadd_node0007_d_buffer_column_pair_v18.json"
)
CONTRACT = ROOT / (
    "contracts/operator_config/"
    "qlinearadd_node0007_split_workload_v25.json"
)
CONTRACT_SHA = (
    "37dc6c2a0b0f4176a8e9372a29f10db8f3b6e2c630203487b3ea6041c521c9e1"
)


class SegmentBError(ValueError):
    pass


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SegmentBError(f"JSON root differs: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def graph() -> dict[str, Any]:
    source = load(
        SOURCE / "execplan/pipeline_output/graph_withbaseaddr.json"
    )
    operator = next(
        item for item in source["operators"]
        if item["id"] == "op_relocation_pad"
    )
    operator["inputs"]["A"]["base_addr"] = "0x00000000"
    operator["output"]["base_addr"] = "0x00021000"
    return {
        "operators": [operator],
        "params": {
            **source["params"],
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "split_workload_contract": CONTRACT.relative_to(ROOT).as_posix(),
            "split_workload_contract_sha256": CONTRACT_SHA,
            "address_policy": "FRESH_SINGLE_STAGE_NONALIAS_ALLOCATION",
        },
        "used_slices": source["used_slices"],
    }


def main() -> int:
    if OUTPUT.exists():
        print(f"refusing existing output: {OUTPUT}", file=sys.stderr)
        return 1
    if sha256_file(CONTRACT) != CONTRACT_SHA:
        print("split contract receipt drift", file=sys.stderr)
        return 1
    graph_path = OUTPUT / "graph.json"
    stage_graph = graph()
    write(graph_path, stage_graph)
    source_config = SOURCE / "mapping/op_relocation_pad/source_config.json"
    bound, changes = bind_config_addresses(load(source_config), stage_graph)
    expected_paths = {
        "$.stream_engine.stream0.base_addr",
        "$.stream_engine.stream2.base_addr",
    }
    actual_paths = {item["path"] for item in changes}
    if actual_paths != expected_paths:
        raise SegmentBError(
            f"address-only change set differs: {sorted(actual_paths)}"
        )
    config_path = OUTPUT / "config/op_relocation_pad.json"
    write(config_path, bound)
    mapping = OUTPUT / "mapping/op_relocation_pad"
    create_mapping_evidence_bundle(
        ndp_sim_root=ROOT / "ndp-sim",
        config_path=config_path,
        output_dir=mapping,
        python_executable=Path(sys.executable),
        patchset_manifest_path=PATCHSET,
        heuristic_iterations=2_000,
        heuristic_restarts=4,
        timeout_seconds=600,
    )
    execplan = OUTPUT / "execplan"
    create_execplan_evidence_bundle(
        ndp_sim_root=ROOT / "ndp-sim",
        graph_path=graph_path,
        mapping_bundles={"op_relocation_pad": mapping},
        output_dir=execplan,
        python_executable=Path(sys.executable),
        patchset_manifest_path=PATCHSET,
        timeout_seconds=900,
    )
    sca = load(execplan / "pipeline_output/sca_cfg.json")
    receipt = {
        "schema": "qlinearadd-node0007-split-b-materialization-v25",
        "status": "NATIVE_SPLIT_B_MATERIALIZED",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "split_contract_sha256": CONTRACT_SHA,
        "boundary_mode": "FROZEN_NONCOMPUTATIONAL_CONSTANT",
        "host_precomputed_internal_tensor": False,
        "address_changes": changes,
        "address_changes_only": True,
        "mapping_initial_state": "EMPTY",
        "execplan_initial_state": "EMPTY",
        "graph_sha256": sha256_file(graph_path),
        "config_sha256": sha256_file(config_path),
        "mapping_bundle_manifest_sha256": sha256_file(
            mapping / "bundle_manifest.json"
        ),
        "execplan_bundle_manifest_sha256": sha256_file(
            execplan / "bundle_manifest.json"
        ),
        "execplan_sha256": sha256_file(
            execplan / "pipeline_output/install/execplan.txt"
        ),
        "repeat_num": sca["Repeat_Num"],
        "exec_length": sca["Exec_Length"],
        "numeric_analysis_repeated": False,
        "functional_rtl_modified": False,
    }
    write(OUTPUT / "materialization_receipt.json", receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
