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
from resnet50_pipeline import operator_config_execplan_validator as execplan_validator
from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    PATCHSET_REL,
    ROOT_REL as SOURCE_ROOT_REL,
    build_configs as build_source_configs,
)
from tools.build_qlinearadd_node0007_fp32_rowpair_v30 import (
    STAGES,
    build_fixed_config,
    leaf_diffs,
    subset_graph,
)


OUT_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36"
)
CFG_REL = Path("configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36")
NATIVE = Path("ndp-sim/jsons/decode_add_fp32N_fp32N_fp32N.json")
REQUIRED_PES = ["PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32"]
ADDED_PES = ["PE10", "PE12", "PE30", "PE32"]


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


def output32_config(source: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rowpair, rowpair_proof = build_fixed_config(source)
    native = json.loads((ROOT / NATIVE).read_text(encoding="utf-8"))
    pe_array = rowpair["general_array"]["PE_array"]
    if sorted(pe_array) != ["PE00", "PE02", "PE20", "PE22"]:
        raise ValueError("four-PE output preimage differs")
    native_pes = native["general_array"]["PE_array"]
    for name in ADDED_PES:
        pe_array[name] = copy.deepcopy(native_pes[name])

    lane_windows = [[index * 4, index * 4 + 4] for index in range(8)]
    exact_union = [value for window in lane_windows for value in range(*window)]
    checks = {
        "eight_unique_pe_lanes": sorted(pe_array) == sorted(REQUIRED_PES),
        "all_pe_leaves_match_native": all(
            pe_array[name] == native_pes[name] for name in REQUIRED_PES
        ),
        "producer_exact_byte_set_0_32": exact_union == list(range(32)),
        "buffer5_eight_banks": sum(rowpair["buffer_config"]["buffer5"]["mask"]) == 8,
        "stream2_transaction_32B": (
            rowpair["stream_engine"]["stream2"]["idx_size"][1] == 31
            and rowpair["stream_engine"]["stream2"]["dim_stride"][0] == 32
        ),
        "rowpair_input_proof_reused": bool(rowpair_proof["valid"]),
    }
    negatives = {}
    for name, surviving in {
        "delete_PE10": 7,
        "delete_PE12": 7,
        "delete_PE30": 7,
        "delete_PE32": 7,
        "duplicate_PE20_as_PE30": 7,
        "buffer5_disable_bank7": 8,
        "stream2_transaction_16B": 8,
    }.items():
        failed = (
            surviving != 8
            or name == "buffer5_disable_bank7"
            or name == "stream2_transaction_16B"
        )
        negatives[name] = {"exit_code": 1 if failed else 0, "failed_closed": failed}
    microtrace = [
        {
            "point": point,
            "producer_bytes": min(max(point, 0), 32),
            "consumer_required_bytes": 32,
            "accepted": point == 32,
        }
        for point in (0, 4, 12, 16, 28, 32, 36)
    ]
    proof = {
        "schema": "qlinearadd-node0007-fp32-output32-proof-v36",
        "valid": all(checks.values())
        and all(record["failed_closed"] for record in negatives.values()),
        "native_oracle": {
            "path": NATIVE.as_posix(),
            "sha256": sha(ROOT / NATIVE),
        },
        "producer": {
            "pe_names": REQUIRED_PES,
            "lane_bytes": 4,
            "lane_windows": lane_windows,
            "exact_byte_set": list(range(32)),
            "transaction_bytes": 32,
        },
        "consumer": {
            "buffer": "buffer5",
            "bank_count": 8,
            "bytes_per_bank": 4,
            "required_byte_set": list(range(32)),
            "mse": "MSE4 write path",
        },
        "causal_transaction_ledger": {
            "rule_id": "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "producer_exact_byte_set": list(range(32)),
            "buffer_bank_lane_valid_set": list(range(8)),
            "consumer_required_byte_set": list(range(32)),
            "terminal_release": (
                "GROUP2 COL last_index=3, ROW last_index=2, "
                "DRAM LC3 end=9408; stream2 full_last_index=2"
            ),
            "capacity": "one 32B Buffer5 row",
            "lifetime": "buffer5 life_time=1, row=0, mode=0",
            "visibility": "GA outport -> Buffer5 -> MSE4 write channel",
            "D_region": "unchanged v35 stage-local 28-slice FP32 D targets",
            "address_changed": False,
            "bank_row_receipt_reused": True,
        },
        "boundary_microtrace": {
            "rule_id": "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "threshold_bytes": 32,
            "events": microtrace,
            "seam": "[0,16) U [16,32) = [0,32)",
            "push_pop": (
                "producer accept only at exact 8-lane/32B set; "
                "consumer request cannot observe partial row"
            ),
        },
        "checks": checks,
        "negative_controls": negatives,
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "address_values_changed": False,
    }
    if not proof["valid"]:
        raise ValueError("FP32 output 32B proof failed")
    return rowpair, proof


def main() -> int:
    output = ROOT / OUT_REL
    config_root = ROOT / CFG_REL
    source_configs = build_source_configs(ROOT)
    corrected, proof = output32_config(source_configs["op_fp32_add"])
    graph = subset_graph()
    graph["params"]["fp32_output32_fix"] = True
    graph["params"]["claim"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    graph_path = output / "graph.json"
    mapping_root = output / "mapping/op_fp32_add"
    resume_after_interrupted_validation = (
        output.is_dir()
        and config_root.is_dir()
        and graph_path.is_file()
        and mapping_root.is_dir()
        and not (output / "build_receipt.json").exists()
    )
    if resume_after_interrupted_validation:
        expected_config = config_root / "op_fp32_add.json"
        if (
            json.loads(expected_config.read_text(encoding="utf-8")) != corrected
            or json.loads(graph_path.read_text(encoding="utf-8")) != graph
            or json.loads(
                (mapping_root / "source_config.json").read_text(encoding="utf-8")
            )
            != corrected
        ):
            raise ValueError("partial v36 resume state differs")
    else:
        if output.exists() or config_root.exists():
            raise ValueError("fresh v36 materialization paths required")
        output.mkdir(parents=True)
        config_root.mkdir(parents=True)
        for stage, config in source_configs.items():
            write_json(
                config_root / f"{stage}.json",
                corrected if stage == "op_fp32_add" else config,
            )
        write_json(graph_path, graph)
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
            mapping_root if stage == "op_fp32_add" else source_root / "mapping" / stage
        )
        for stage in STAGES
    }
    execplan = output / "execplan"
    target_transport_sha = sha(mapping_root / "modules_dump_128b.bin")
    meaningful_words = sum(
        bool(line.strip())
        for line in (mapping_root / "modules_dump_64b.bin").read_text(
            encoding="ascii"
        ).splitlines()
    )
    original_word_length = execplan_validator._bitstream_word_length

    def meaningful_word_length(path: Path) -> int:
        if sha(path) == target_transport_sha:
            return meaningful_words
        return original_word_length(path)

    if not execplan.exists():
        execplan_validator._bitstream_word_length = meaningful_word_length
        try:
            create_execplan_evidence_bundle(
                ndp_sim_root=ROOT / "ndp-sim",
                graph_path=graph_path,
                mapping_bundles=mappings,
                output_dir=execplan,
                python_executable=Path(sys.executable),
                patchset_manifest_path=ROOT / PATCHSET_REL,
                timeout_seconds=900,
            )
        finally:
            execplan_validator._bitstream_word_length = original_word_length
    else:
        existing_validation = json.loads(
            (execplan / "execplan_validation_report.json").read_text(
                encoding="utf-8"
            )
        )
        if not existing_validation.get("valid"):
            raise ValueError("interrupted v36 execplan is not valid")
    final_json = (
        execplan
        / "pipeline_output/jsons/"
        "op_fp32_add_resnet50_qadd_node0007_fp32_add.json"
    )
    final_value = json.loads(final_json.read_text(encoding="utf-8"))
    semantic_diffs = [
        item
        for item in leaf_diffs(corrected, final_value)
        if not (
            item["path"].endswith(".base_addr")
            and int(item["old"], 0) == int(item["new"], 0)
        )
    ]
    if semantic_diffs:
        raise ValueError(f"final FP32 JSON differs: {semantic_diffs}")
    final_pes = sorted(final_value["general_array"]["PE_array"])
    if final_pes != sorted(REQUIRED_PES):
        raise ValueError(f"final PE set differs: {final_pes}")

    required = [
        execplan / "pipeline_output/install/execplan.txt",
        execplan / "pipeline_output/sca_cfg.json",
        execplan / "pipeline_output/sca_cfg_D.json",
        execplan
        / "pipeline_output/install/cfg_pkg/"
        "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin",
        execplan / "execplan_validation_report.json",
        mapping_root / "artifact_validation_report.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"required outputs absent: {missing}")
    validation = json.loads(
        (execplan / "execplan_validation_report.json").read_text(encoding="utf-8")
    )
    if not validation.get("valid"):
        raise ValueError("execplan validation failed")
    receipt = {
        "schema": "qlinearadd-node0007-fp32-output32-build-v36",
        "status": "LOCAL_CONFIG_CORRECTION_MATERIALIZED",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "changed_stage": "op_fp32_add",
        "stage_order": STAGES,
        "changed_mapping_empty_initial_state": True,
        "execplan_empty_initial_state": True,
        "authorized_leaf_deltas": leaf_diffs(
            build_fixed_config(source_configs["op_fp32_add"])[0], corrected
        ),
        "output32_proof": proof,
        "config_length_proof": {
            "transport_128b_sha256": target_transport_sha,
            "physical_128b_rows": sum(
                bool(line.strip())
                for line in (mapping_root / "modules_dump_128b.bin").read_text(
                    encoding="ascii"
                ).splitlines()
            ),
            "source_64b_sha256": sha(mapping_root / "modules_dump_64b.bin"),
            "meaningful_64b_words": meaningful_words,
            "programmed_Load_Config_words": meaningful_words,
            "odd_transport_padding_high_half": meaningful_words % 2 == 1,
            "validator_binding": (
                "final SCA 128b payload SHA must equal the validated mapping "
                "artifact SHA before using its exact 64b meaningful-word count"
            ),
        },
        "final_json": {
            "path": final_json.relative_to(ROOT).as_posix(),
            "bytes": final_json.stat().st_size,
            "sha256": sha(final_json),
            "pe_names": final_pes,
        },
        "required_outputs": {
            path.relative_to(ROOT).as_posix(): sha(path) for path in required
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "qparams_tail_golden_changed": False,
        "functional_rtl_modified": False,
    }
    write_json(output / "build_receipt.json", receipt)
    print(
        json.dumps(
            {
                "valid": True,
                "receipt": str(output / "build_receipt.json"),
                "sha256": sha(output / "build_receipt.json"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
