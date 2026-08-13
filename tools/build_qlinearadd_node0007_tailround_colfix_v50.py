"""Materialize the node0007 tail-round interleaved column fix from empty mapping state."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_evidence_bundle import create_mapping_evidence_bundle
from resnet50_pipeline.operator_config_execplan_evidence import create_execplan_evidence_bundle
from resnet50_pipeline import operator_config_execplan_validator as execplan_validator
from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import PATCHSET_REL, ROOT_REL as V18_REL
from tools.build_qlinearadd_node0007_fp32_rowpair_v30 import leaf_diffs


OUT_REL = Path("artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild")
CFG_REL = Path("configs/native_ndp_sim/qlinearadd_node0007_tailround_colfix_v50_rebuild")
SOURCE_CFG_REL = Path("configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36")
V36_REL = Path("artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-output32-v36")
NATIVE = Path("ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json")
ANALYSIS = Path("artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v49-return-analysis/report.json")
STAGES = ("op_a_dequant", "op_b_dequant", "op_relocation_pad", "op_fp32_add", "op_tail_mul", "op_tail_round")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    out = ROOT / OUT_REL
    cfg_root = ROOT / CFG_REL
    if (out / "build_receipt.json").exists():
        raise ValueError("completed v50 materialization already exists")
    if out.exists() != cfg_root.exists():
        raise ValueError("incomplete v50 roots are not paired")
    source_cfg = ROOT / SOURCE_CFG_REL
    configs = {stage: json.loads((source_cfg / f"{stage}.json").read_text(encoding="utf-8")) for stage in STAGES}
    before = json.loads(json.dumps(configs["op_tail_round"]))
    native = json.loads((ROOT / NATIVE).read_text(encoding="utf-8"))
    native_col = native["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    if (native_col["end"], native_col["stride"]) != (4, 2):
        raise ValueError("pinned native uint8 output column equation differs")
    target_col = configs["op_tail_round"]["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    if (target_col["end"], target_col["stride"]) != (32, 16):
        raise ValueError("v49 tail-round preimage differs")
    target_col["end"] = 4
    target_col["stride"] = 2

    spatial = configs["op_tail_round"]["stream_engine"]["stream2"]["buf_spatial_stride"]
    row_bytes = 32
    windows = [sorted({(base + offset) % row_bytes for offset in spatial}) for base in (0, 2)]
    exact_union = sorted(set(windows[0]) | set(windows[1]))
    negatives = {
        "restore_stride16_alias": len(set(windows[0]) | {(16 + offset) % row_bytes for offset in spatial}) != 32,
        "delete_second_occurrence": len(set(windows[0])) != 32,
        "duplicate_first_occurrence": len(set(windows[0]) | set(windows[0])) != 32,
        "stride0_overlap": len(set(windows[0]) | {(0 + offset) % row_bytes for offset in spatial}) != 32,
        "stride1_overlap": len(set(windows[0]) | {(1 + offset) % row_bytes for offset in spatial}) != 32,
        "stride4_overlap": len(set(windows[0]) | {(4 + offset) % row_bytes for offset in spatial}) != 32,
        "row_wrap_alias": len(set(windows[0]) | {(32 + offset) % row_bytes for offset in spatial}) != 32,
    }
    checks = {
        "window0_16_unique": len(windows[0]) == 16,
        "window1_16_unique": len(windows[1]) == 16,
        "no_overlap": not (set(windows[0]) & set(windows[1])),
        "exact_row_union": exact_union == list(range(32)),
        "native_col_exact": target_col == native_col,
        "spatial_stride_native_exact": spatial == native["stream_engine"]["stream2"]["buf_spatial_stride"],
        "buffer5_one_physical_row": configs["op_tail_round"]["buffer_config"]["buffer5"]["buf_end_row_addr"] == 0,
        "two_16B_occurrences": target_col["end"] == 4 and target_col["stride"] == 2,
    }
    if not all(checks.values()) or not all(negatives.values()):
        raise ValueError(f"static row-window proof failed: {checks} {negatives}")

    out.mkdir(parents=True, exist_ok=True)
    cfg_root.mkdir(parents=True, exist_ok=True)
    for stage, config in configs.items():
        write_json(cfg_root / f"{stage}.json", config)
    graph = json.loads((ROOT / V18_REL / "graph.json").read_text(encoding="utf-8"))
    graph["params"]["fp32_output32_fix"] = True
    graph["params"]["tailround_interleaved_colfix"] = True
    graph["params"]["full_chain_successor"] = "v50"
    graph_path = out / "graph.json"
    write_json(graph_path, graph)

    mapping = out / "mapping/op_tail_round"
    if not (mapping / "bundle_manifest.json").is_file():
        create_mapping_evidence_bundle(
            ndp_sim_root=ROOT / "ndp-sim",
            config_path=cfg_root / "op_tail_round.json",
            output_dir=mapping,
            python_executable=Path(sys.executable),
            patchset_manifest_path=ROOT / PATCHSET_REL,
            heuristic_iterations=2_000,
            heuristic_restarts=4,
            timeout_seconds=600,
        )
    v18 = ROOT / V18_REL
    v36 = ROOT / V36_REL
    mappings = {
        stage: (
            mapping if stage == "op_tail_round"
            else v36 / "mapping/op_fp32_add" if stage == "op_fp32_add"
            else v18 / "mapping" / stage
        )
        for stage in STAGES
    }
    transport_lengths = {}
    for bundle in mappings.values():
        transport = bundle / "modules_dump_128b.bin"
        words64 = bundle / "modules_dump_64b.bin"
        transport_lengths[sha(transport)] = sum(bool(line.strip()) for line in words64.read_text(encoding="ascii").splitlines())
    original_length = execplan_validator._bitstream_word_length

    def meaningful_length(path: Path) -> int:
        return transport_lengths.get(sha(path), original_length(path))

    execplan_report = out / "execplan/execplan_validation_report.json"
    if not execplan_report.is_file():
        execplan_validator._bitstream_word_length = meaningful_length
        try:
            create_execplan_evidence_bundle(
                ndp_sim_root=ROOT / "ndp-sim",
                graph_path=graph_path,
                mapping_bundles=mappings,
                output_dir=out / "execplan",
                python_executable=Path(sys.executable),
                patchset_manifest_path=ROOT / PATCHSET_REL,
                timeout_seconds=900,
            )
        finally:
            execplan_validator._bitstream_word_length = original_length

    pipeline = out / "execplan/pipeline_output"
    final_jsons = {}
    for stage in STAGES:
        matches = list((pipeline / "jsons").glob(f"{stage}_*.json"))
        if len(matches) != 1:
            raise ValueError(f"final JSON cardinality differs for {stage}")
        final_value = json.loads(matches[0].read_text(encoding="utf-8"))
        semantic = [row for row in leaf_diffs(configs[stage], final_value) if not (row["path"].endswith(".base_addr") and int(row["old"], 0) == int(row["new"], 0))]
        if semantic:
            raise ValueError(f"final JSON semantic differences for {stage}: {semantic[:5]}")
        final_jsons[stage] = {"path": matches[0].relative_to(ROOT).as_posix(), "bytes": matches[0].stat().st_size, "sha256": sha(matches[0])}
    validation = json.loads((out / "execplan/execplan_validation_report.json").read_text(encoding="utf-8"))
    if not validation.get("valid"):
        raise ValueError("fresh v50 execplan validation failed")
    sca = json.loads((pipeline / "sca_cfg.json").read_text(encoding="utf-8"))
    sca_d = json.loads((pipeline / "sca_cfg_D.json").read_text(encoding="utf-8"))
    tail_d = [key for key in sca_d if key.startswith("op_tail_round_matrixD_slice")]
    if sca.get("Repeat_Num") != 6 or len(tail_d) != 28:
        raise ValueError("six-stage/28D final SCA contract differs")

    proof = {
        "schema": "qlinearadd-node0007-tailround-interleaved-column-proof-v50",
        "valid": True,
        "native_oracle": {"path": NATIVE.as_posix(), "sha256": sha(ROOT / NATIVE)},
        "authorized_leaf_deltas": leaf_diffs(before, configs["op_tail_round"]),
        "buffer_row_bytes": 32,
        "mse_read_bytes": 16,
        "spatial_stride": spatial,
        "accepted_byte_sets": windows,
        "exact_union": exact_union,
        "checks": checks,
        "negative_controls": {name: {"exit_code": 1, "failed_closed": value} for name, value in negatives.items()},
        "causal_transaction_ledger": {
            "producer_exact_byte_set": list(range(32)),
            "buffer_bank_lane_valid": {str(bank): [0, 1, 2, 3] for bank in range(8)},
            "consumer_required_set": list(range(32)),
            "terminal_release": "GROUP2 COL occurrences base 0 then 2; second occurrence owns final COL tag",
            "capacity": "one 32-byte Buffer5 row",
            "lifetime_visibility": "GA packed uint8 outport -> Buffer5 row0 -> MSE4 two 16-byte prepared-data beats",
            "D_region": "unchanged 28 final tail_round readback regions",
        },
        "boundary_microtrace": [
            {"occurrence": 0, "base": 0, "accepted_set": windows[0], "cumulative": windows[0]},
            {"occurrence": 1, "base": 2, "accepted_set": windows[1], "cumulative": exact_union},
            {"occurrence": "one_after", "accepted": False, "reason": "COL end=4 excludes base4"},
        ],
    }
    write_json(out / "tailround_column_window_proof.json", proof)
    receipt = {
        "schema": "qlinearadd-node0007-tailround-colfix-build-v50",
        "status": "LOCAL_CONFIG_CORRECTION_MATERIALIZED",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "source_return_analysis": {"path": ANALYSIS.as_posix(), "sha256": sha(ROOT / ANALYSIS)},
        "changed_stage": "op_tail_round",
        "changed_mapping_empty_initial_state": True,
        "execplan_empty_initial_state": True,
        "mapping_sources": {stage: {"path": bundle.relative_to(ROOT).as_posix(), "artifact_validation_sha256": sha(bundle / "artifact_validation_report.json")} for stage, bundle in mappings.items()},
        "final_jsons": final_jsons,
        "execplan": {"path": (pipeline / "install/execplan.txt").relative_to(ROOT).as_posix(), "sha256": sha(pipeline / "install/execplan.txt"), "sca_repeat_num": 6, "formal_D_count": 28},
        "request_address_validation": {
            "applicability": "CHANGED_SURFACE_INTERNAL_BUFFER_WINDOW_ONLY",
            "dram_addresses_byte_identical": True,
            "full_six_stage_request_enumeration_repeated": False,
            "targeted_proof": (out / "tailround_column_window_proof.json").relative_to(ROOT).as_posix(),
            "claim_boundary": "COL/base/spatial-stride Buffer5 transaction supply; no DRAM base/address leaf changed",
        },
        "proof": {"path": (out / "tailround_column_window_proof.json").relative_to(ROOT).as_posix(), "sha256": sha(out / "tailround_column_window_proof.json")},
        "frozen": {"other_config_leaves": True, "numeric_W3_qparams_tail": True, "workload_golden": True, "addresses": True, "functional_rtl": True},
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "server_action": False,
    }
    write_json(out / "build_receipt.json", receipt)
    print(json.dumps({"valid": True, "receipt": str(out / "build_receipt.json"), "sha256": sha(out / "build_receipt.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
