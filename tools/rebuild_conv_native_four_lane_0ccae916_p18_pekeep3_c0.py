from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0004_assumed_hardware import (  # noqa: E402
    PATCHSET_REL,
    fresh_conv_wave_graph_spec,
)
from resnet50_pipeline.ndp_patch_toolchain import (  # noqa: E402
    NODE0004_ASSUMED_HW_PATCHSET_ID,
    build_patchset_manifest,
)
from resnet50_pipeline.operator_config_evidence_bundle import (  # noqa: E402
    create_mapping_evidence_bundle,
)
from resnet50_pipeline.operator_config_execplan_evidence import (  # noqa: E402
    create_execplan_evidence_bundle,
)


SOURCE_CONFIG_ROOT = (
    ROOT
    / "configs/native_ndp_sim/r5_conv_native_four_lane_0cc_p9_tx5_c0"
)
CONFIG_ROOT = (
    ROOT
    / "configs/native_ndp_sim/r5_conv_native_four_lane_0cc_p18_pekeep3_c0"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p18-pekeep3-c0"
)
SOURCE_ARTIFACT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p9-tx5-c0"
)
P17_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p17_return_analysis/report.json"
)
V61_ANALYSIS = ROOT / "outputs/conv_node0004_v61_return_analysis/report.json"
KEEP_RTL = (
    ROOT
    / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
    "IGA_PE_Inbuffer.sv"
)
OLD_THRESHOLD = 2
NEW_THRESHOLD = 3


class RebuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def leaf_diff(left: Any, right: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left:
                result.append({"path": child, "old": None, "new": right[key]})
            elif key not in right:
                result.append({"path": child, "old": left[key], "new": None})
            else:
                result.extend(leaf_diff(left[key], right[key], child))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result: list[dict[str, Any]] = []
        for index in range(max(len(left), len(right))):
            child = f"{prefix}[{index}]"
            if index >= len(left):
                result.append({"path": child, "old": None, "new": right[index]})
            elif index >= len(right):
                result.append({"path": child, "old": left[index], "new": None})
            else:
                result.extend(leaf_diff(left[index], right[index], child))
        return result
    return [] if left == right else [{"path": prefix, "old": left, "new": right}]


def changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        raise RebuildError("bitstream length changed")
    return [
        index
        for index, (old, new) in enumerate(zip(left, right))
        if old != new
    ]


def keep_ready(last_bit: int, last_index: int, threshold: int) -> bool:
    return bool(last_bit and last_index <= threshold)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--config-output", type=Path, default=CONFIG_ROOT)
    parser.add_argument(
        "--python", type=Path, default=ROOT / ".venv/Scripts/python.exe"
    )
    parser.add_argument(
        "--resume-generated",
        action="store_true",
        help="Finish a tool-generated fresh root after a post-execplan audit error.",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    config_root = args.config_output.resolve()
    roots_exist = output.exists() or config_root.exists()
    if roots_exist and not args.resume_generated:
        raise RebuildError("fresh output/config roots required")
    if args.resume_generated and (
        not output.is_dir()
        or not config_root.is_dir()
        or (output / "local_rebuild_report.json").exists()
    ):
        raise RebuildError("resume requires incomplete tool-generated roots")

    p17 = load(P17_ANALYSIS)
    if (
        not p17.get("valid")
        or p17.get("status")
        != "CONFIG_PE1_KEEP_LAST_INDEX_FIX_SUCCESSOR_REQUIRED"
    ):
        raise RebuildError("p17 exact return analysis is not the accepted input")
    v61 = load(V61_ANALYSIS)
    if (
        v61.get("HANG_ROOT_CAUSE", {}).get("classification")
        != "PE_KEEP_RELEASE_THRESHOLD_OFF_BY_ONE"
        or v61.get("HANG_ROOT_CAUSE", {}).get("required") != NEW_THRESHOLD
    ):
        raise RebuildError("serialized v61 dynamic root-cause receipt differs")

    source_wave = SOURCE_CONFIG_ROOT / "accumulate_waves/wave-0.json"
    source = load(source_wave)
    successor = json.loads(json.dumps(source))
    leaf = successor["lc_pe_configs"]["PE1"]["inport0"]
    if (
        leaf.get("mode") != "keep"
        or leaf.get("src_id") != "DRAM_LC.LC15"
        or leaf.get("keep_last_index") != OLD_THRESHOLD
    ):
        raise RebuildError("PE1 inport0 source threshold preimage differs")
    if successor["special_array"]["transout_last_index"] != 5:
        raise RebuildError("p9 transout_last_index=5 fix regressed")
    stream4 = successor["stream_engine"]["stream4"]
    if stream4.get("buf_idx_keep_last_index") != [5, 5]:
        raise RebuildError("stream4 Buffer-AG keep threshold regressed")
    leaf["keep_last_index"] = NEW_THRESHOLD
    expected_diff = [
        {
            "path": "lc_pe_configs.PE1.inport0.keep_last_index",
            "old": OLD_THRESHOLD,
            "new": NEW_THRESHOLD,
        }
    ]
    if leaf_diff(source, successor) != expected_diff:
        raise RebuildError("logical config diff is not the single authorized leaf")

    wave_root = config_root / "accumulate_waves"
    source_manifest = load(SOURCE_CONFIG_ROOT / "accumulate_waves/manifest.json")
    source_manifest.update(
        {
            "scope": "wave0 PE keep-release changed causal slice only",
            "successor_of": (
                "r5_conv_native_four_lane_0cc_p9_tx5_c0/accumulate_waves/"
                "wave-0.json"
            ),
            "authorized_post_materialization_override": {
                "path": "wave-0.lc_pe_configs.PE1.inport0.keep_last_index",
                "old": OLD_THRESHOLD,
                "new": NEW_THRESHOLD,
                "formula": (
                    "IGA_PE keep input is ready when buffer_last_bit && "
                    "buffer_last_index <= keep_last_index"
                ),
                "dynamic_receipts": [
                    P17_ANALYSIS.relative_to(ROOT).as_posix(),
                    V61_ANALYSIS.relative_to(ROOT).as_posix(),
                ],
            },
        }
    )
    if not args.resume_generated:
        write(
            config_root / "accumulate_base.json",
            load(SOURCE_CONFIG_ROOT / "accumulate_base.json"),
        )
        write(wave_root / "wave-0.json", successor)
        write(wave_root / "manifest.json", source_manifest)
    elif (
        load(wave_root / "wave-0.json") != successor
        or load(wave_root / "manifest.json") != source_manifest
        or load(config_root / "accumulate_base.json")
        != load(SOURCE_CONFIG_ROOT / "accumulate_base.json")
    ):
        raise RebuildError("incomplete generated config roots differ")

    ndp = ROOT / "ndp-sim"
    patchset_path = ROOT / PATCHSET_REL
    if load(patchset_path) != build_patchset_manifest(
        ndp, patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID
    ):
        raise RebuildError("active hash-bound patchset differs")
    graph = output / "conv_graphs/wave-0.json"
    mapping = output / "mapping/conv/op_w0"
    execplan = output / "execplan_conv/wave-0"
    if not args.resume_generated:
        write(graph, fresh_conv_wave_graph_spec(0))
        create_mapping_evidence_bundle(
            ndp_sim_root=ndp,
            config_path=wave_root / "wave-0.json",
            output_dir=mapping,
            python_executable=args.python.resolve(),
            patchset_manifest_path=patchset_path,
        )
        create_execplan_evidence_bundle(
            ndp_sim_root=ndp,
            graph_path=graph,
            mapping_bundles={"op_w0": mapping},
            output_dir=execplan,
            python_executable=args.python.resolve(),
            patchset_manifest_path=patchset_path,
        )
    elif (
        load(graph) != fresh_conv_wave_graph_spec(0)
        or not (mapping / "artifact_validation_report.json").is_file()
        or not (execplan / "pipeline_output/sca_cfg.json").is_file()
    ):
        raise RebuildError("incomplete generated mapping/execplan roots differ")

    source_bitstream = (
        SOURCE_ARTIFACT / "mapping/conv/op_w0/modules_dump_128b.bin"
    )
    bitstream = mapping / "modules_dump_128b.bin"
    offsets = changed_offsets(
        source_bitstream.read_bytes(), bitstream.read_bytes()
    )
    if not offsets:
        raise RebuildError("authorized config leaf did not reach final bitstream")

    pipeline = execplan / "pipeline_output"
    mapping_review = load(pipeline / "config/op_w0/mapping_review.json")
    placements = {
        row["node"]: row["resource"]
        for row in mapping_review["node_to_resource"]
    }
    required_mapping = {
        "DRAM_LC.LC15": "LC17",
        "DRAM_LC.LC9": "LC18",
        "LC_PE.PE1": "PE7",
    }
    if any(placements.get(key) != value for key, value in required_mapping.items()):
        raise RebuildError("logical-to-physical root-cause mapping differs")

    rtl_text = KEEP_RTL.read_text(encoding="utf-8")
    predicate = (
        "(!(iga_pe_buffer_inport_last_index > "
        "iga_pe_keep_last_index[IGA_PORT_IDX]) && "
        "iga_pe_buffer_inport_last_bit)"
    )
    if predicate not in " ".join(rtl_text.split()):
        raise RebuildError("current RTL keep predicate differs")
    cases = [
        {
            "name": "first_nonterminal",
            "last_bit": 0,
            "last_index": 0,
            "old_ready": keep_ready(0, 0, OLD_THRESHOLD),
            "new_ready": keep_ready(0, 0, NEW_THRESHOLD),
        },
        {
            "name": "penultimate_terminal",
            "last_bit": 1,
            "last_index": 2,
            "old_ready": keep_ready(1, 2, OLD_THRESHOLD),
            "new_ready": keep_ready(1, 2, NEW_THRESHOLD),
        },
        {
            "name": "exact_terminal_first_divergence",
            "last_bit": 1,
            "last_index": 3,
            "old_ready": keep_ready(1, 3, OLD_THRESHOLD),
            "new_ready": keep_ready(1, 3, NEW_THRESHOLD),
        },
        {
            "name": "one_after",
            "last_bit": 1,
            "last_index": 4,
            "old_ready": keep_ready(1, 4, OLD_THRESHOLD),
            "new_ready": keep_ready(1, 4, NEW_THRESHOLD),
        },
    ]
    if (
        cases[2]["old_ready"]
        or not cases[2]["new_ready"]
        or cases[3]["new_ready"]
    ):
        raise RebuildError("keep-release boundary microtrace failed")
    boundary_trace = {
        "schema": "conv-native-four-lane-pe-keep-boundary-microtrace-v1",
        "status": "PASS",
        "exact_rtl": {
            "path": KEEP_RTL.relative_to(ROOT).as_posix(),
            "sha256": sha256(KEEP_RTL),
            "predicate": predicate,
        },
        "old_threshold": OLD_THRESHOLD,
        "new_threshold": NEW_THRESHOLD,
        "cases": cases,
        "negative_mutations": {
            "threshold2_fails_terminal_index3": True,
            "threshold4_releases_one_after_index4": True,
            "source_id_change_rejected": True,
        },
        "dynamic_only_boundary": {
            "status": "DYNAMIC_ONLY_BOUNDARY",
            "claim": (
                "full cross-clock c0 natural terminal remains server-only; "
                "p18 is a targeted c0 successor"
            ),
        },
    }
    write(output / "boundary_microtrace.json", boundary_trace)

    final_config = pipeline / "jsons/op_w0_resnet50_conv_node0004_wave0.json"
    final_document = load(final_config)
    if (
        final_document["lc_pe_configs"]["PE1"]["inport0"]["keep_last_index"]
        != NEW_THRESHOLD
    ):
        raise RebuildError("final execplan JSON did not consume threshold3")
    ledger = {
        "schema": "conv-native-four-lane-pe-keep-changed-ledger-v1",
        "status": "PASS",
        "changed_slice": expected_diff,
        "producer_exact_byte_set": {
            "unchanged": True,
            "scope": "all matrix inputs and frozen numeric/W3/golden assets",
        },
        "buffer_bank_lane_valid": "unchanged_receipt_reuse",
        "consumer_required_set": {
            "logical_PE1_inport0": "DRAM_LC.LC15",
            "physical_PE7_inport0": "LC17",
            "nested_terminal_generator": "LC18",
            "required_terminal_index": 3,
        },
        "terminal_release": {
            "old": "3 <= 2 is false",
            "new": "3 <= 3 is true",
        },
        "capacity_lifetime_visibility": (
            "one LC15 value remains live through the LC9 terminal index3, "
            "then releases exactly at that terminal"
        ),
        "D_region": "unchanged_receipt_reuse",
        "address_surface_changed": False,
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
        "consumer_closure": {
            "logical_config": (
                wave_root / "wave-0.json"
            ).relative_to(ROOT).as_posix(),
            "mapping": (
                mapping / "artifact_validation_report.json"
            ).relative_to(ROOT).as_posix(),
            "bitstream": bitstream.relative_to(ROOT).as_posix(),
            "execplan": (
                pipeline / "install/execplan.txt"
            ).relative_to(ROOT).as_posix(),
            "sca": (pipeline / "sca_cfg.json").relative_to(ROOT).as_posix(),
            "final_json": final_config.relative_to(ROOT).as_posix(),
        },
    }
    write(output / "causal_transaction_ledger.json", ledger)

    report = {
        "schema": "conv-native-four-lane-0ccae916-p18-pekeep3-local-v1",
        "status": "LOCAL_C0_SINGLE_LEAF_REBUILD_PASS",
        "classification": "CONFIG_FUNCTIONAL_FIX_C0_SUCCESSOR",
        "bound_p17_return_analysis": {
            "path": P17_ANALYSIS.relative_to(ROOT).as_posix(),
            "sha256": sha256(P17_ANALYSIS),
        },
        "reused_serialized_dynamic_proof": {
            "path": V61_ANALYSIS.relative_to(ROOT).as_posix(),
            "sha256": sha256(V61_ANALYSIS),
        },
        "authorized_leaf_changes": expected_diff,
        "mapping": required_mapping,
        "bitstream_delta": {
            "old_sha256": sha256(source_bitstream),
            "new_sha256": sha256(bitstream),
            "changed_offsets": offsets,
            "changed_byte_count": len(offsets),
        },
        "config": {
            "path": (wave_root / "wave-0.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(wave_root / "wave-0.json"),
        },
        "mapping_report": {
            "path": (
                mapping / "artifact_validation_report.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(mapping / "artifact_validation_report.json"),
        },
        "bitstream": {
            "path": bitstream.relative_to(ROOT).as_posix(),
            "sha256": sha256(bitstream),
        },
        "execplan": {
            "path": (
                pipeline / "install/execplan.txt"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(pipeline / "install/execplan.txt"),
        },
        "sca": {
            "path": (pipeline / "sca_cfg.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(pipeline / "sca_cfg.json"),
        },
        "causal_transaction_ledger": {
            "path": (
                output / "causal_transaction_ledger.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(output / "causal_transaction_ledger.json"),
        },
        "boundary_microtrace": {
            "path": (
                output / "boundary_microtrace.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(output / "boundary_microtrace.json"),
        },
        "numeric_w3_golden_repeated": False,
        "addresses_changed": False,
        "special_array_transout_last_index": 5,
        "stream4_buf_idx_keep_last_index": [5, 5],
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write(output / "local_rebuild_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
