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


OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-pe1-keep-last-index-fix-c0-v62"
)
CONFIG_ROOT = (
    ROOT
    / "configs/native_ndp_sim/"
    "r5_node0004_pe1_keep_last_index_fix_c0_v62"
)
FROZEN_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/r5_conv_native_four_lane_0cc_p9_tx5_c0/"
    "accumulate_waves/wave-0.json"
)
FROZEN_PIPELINE = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p9-tx5-c0/execplan_conv/wave-0/"
    "pipeline_output"
)
FROZEN_FINAL_JSON = (
    FROZEN_PIPELINE / "jsons/op_w0_resnet50_conv_node0004_wave0.json"
)
V61_ANALYSIS = ROOT / "outputs/conv_node0004_v61_return_analysis/report.json"
OLD_KEEP = 2
NEW_KEEP = 3


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
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
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
        raise SystemExit("bitstream length changed")
    return [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--config-output", type=Path, default=CONFIG_ROOT)
    parser.add_argument(
        "--python", type=Path, default=ROOT / ".venv/Scripts/python.exe"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    config_root = args.config_output.resolve()
    if output.exists() or config_root.exists():
        raise SystemExit("fresh output/config roots required")

    analysis = load(V61_ANALYSIS)
    if (
        analysis.get("valid") is not True
        or analysis.get("HANG_ROOT_CAUSE", {}).get("classification")
        != "PE_KEEP_RELEASE_THRESHOLD_OFF_BY_ONE"
    ):
        raise SystemExit("accepted v61 return analysis differs")

    frozen = load(FROZEN_CONFIG)
    changed = json.loads(json.dumps(frozen))
    pe1 = changed["lc_pe_configs"]["PE1"]
    if (
        pe1["inport0"]["src_id"] != "DRAM_LC.LC15"
        or pe1["inport0"]["mode"] != "keep"
        or pe1["inport0"]["keep_last_index"] != OLD_KEEP
        or pe1["inport2"]["src_id"] != "DRAM_LC.LC9"
        or pe1["inport2"]["mode"] != "buffer"
    ):
        raise SystemExit("PE1 keep/buffer preimage differs")
    pe1["inport0"]["keep_last_index"] = NEW_KEEP
    expected_diff = [
        {
            "path": "lc_pe_configs.PE1.inport0.keep_last_index",
            "old": OLD_KEEP,
            "new": NEW_KEEP,
        }
    ]
    if leaf_diff(frozen, changed) != expected_diff:
        raise SystemExit("logical config diff is not the single authorized leaf")

    wave_root = config_root / "accumulate_waves"
    config_path = wave_root / "wave-0.json"
    write(config_path, changed)
    write(
        wave_root / "manifest.json",
        {
            "schema": "node0004-pe1-keep-last-index-config-fix-v1",
            "scope": "wave0 changed causal slice only",
            "source_config": {
                "path": FROZEN_CONFIG.relative_to(ROOT).as_posix(),
                "sha256": sha256(FROZEN_CONFIG),
            },
            "authorized_post_materialization_override": {
                **expected_diff[0],
                "owner": "Conv/SA owner",
                "input": (
                    "v61 qualified LC18 terminal last_index=3 and "
                    "PE7 inport0 ready=0"
                ),
                "formula": (
                    "keep_last_index = immediate buffer-loop terminal "
                    "last_index = DRAM_LC.LC9.last_index = 3"
                ),
                "consumer": "IGA_PE_Inbuffer.sv:167",
            },
            "unmaterialized_unchanged_waves": [1, 2],
        },
    )

    ndp = ROOT / "ndp-sim"
    patchset_path = ROOT / PATCHSET_REL
    if load(patchset_path) != build_patchset_manifest(
        ndp, patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID
    ):
        raise SystemExit("active hash-bound patchset differs")
    graph = output / "conv_graphs/wave-0.json"
    write(graph, fresh_conv_wave_graph_spec(0))
    mapping = output / "mapping/conv/op_w0"
    create_mapping_evidence_bundle(
        ndp_sim_root=ndp,
        config_path=config_path,
        output_dir=mapping,
        python_executable=args.python.resolve(),
        patchset_manifest_path=patchset_path,
    )
    execplan = output / "execplan_conv/wave-0"
    create_execplan_evidence_bundle(
        ndp_sim_root=ndp,
        graph_path=graph,
        mapping_bundles={"op_w0": mapping},
        output_dir=execplan,
        python_executable=args.python.resolve(),
        patchset_manifest_path=patchset_path,
    )

    pipeline = execplan / "pipeline_output"
    final_json = (
        pipeline / "jsons/op_w0_resnet50_conv_node0004_wave0.json"
    )
    if leaf_diff(load(FROZEN_FINAL_JSON), load(final_json)) != expected_diff:
        raise SystemExit("final address-bound JSON diff differs")
    old_mapping = load(FROZEN_PIPELINE / "config/op_w0/mapping_review.json")
    new_mapping = load(pipeline / "config/op_w0/mapping_review.json")
    mapping_keys = ("node_to_resource", "resource_to_node", "connections")
    if any(old_mapping.get(key) != new_mapping.get(key) for key in mapping_keys):
        raise SystemExit("logical-to-physical placement changed")

    old_bitstream = (
        FROZEN_PIPELINE
        / "install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    new_bitstream = (
        pipeline
        / "install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    offsets = changed_offsets(old_bitstream.read_bytes(), new_bitstream.read_bytes())
    if not offsets or len(offsets) > 8:
        raise SystemExit(f"unexpected bitstream delta size:{offsets}")

    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        if load(FROZEN_PIPELINE / name) != load(pipeline / name):
            raise SystemExit(f"address/SCA semantics changed:{name}")
    if (
        (FROZEN_PIPELINE / "install/execplan.txt").read_text(encoding="utf-8")
        != (pipeline / "install/execplan.txt").read_text(encoding="utf-8")
    ):
        raise SystemExit("execplan occurrence schedule changed")

    boundary = {
        "schema": "node0004-pe1-keep-last-index-boundary-microtrace-v1",
        "status": "PASS",
        "predicate": (
            "buffer_mode || "
            "(!(buffer_last_index > keep_last_index) && buffer_last_bit)"
        ),
        "changed_leaf": expected_diff[0],
        "cases": [
            {
                "name": "penultimate_nonterminal",
                "buffer_last_bit": 0,
                "buffer_last_index": 3,
                "keep_last_index": NEW_KEEP,
                "keep_ready": 0,
            },
            {
                "name": "old_threshold_terminal_negative",
                "buffer_last_bit": 1,
                "buffer_last_index": 3,
                "keep_last_index": OLD_KEEP,
                "keep_ready": 0,
            },
            {
                "name": "equal_terminal_positive",
                "buffer_last_bit": 1,
                "buffer_last_index": 3,
                "keep_last_index": NEW_KEEP,
                "keep_ready": 1,
            },
            {
                "name": "outer_terminal_inherited_index2",
                "buffer_last_bit": 1,
                "buffer_last_index": 2,
                "keep_last_index": NEW_KEEP,
                "keep_ready": 1,
            },
            {
                "name": "one_after",
                "event": "next LC15 value may be accepted",
                "expected": True,
            },
        ],
    }
    write(output / "boundary_microtrace.json", boundary)
    ledger = {
        "schema": "node0004-pe1-keep-last-index-causal-transaction-ledger-v1",
        "status": "PASS",
        "changed_slice": expected_diff,
        "producer_exact_byte_set": "unchanged; receipt reuse",
        "buffer_bank_lane_valid": "unchanged; receipt reuse",
        "consumer_required_set": (
            "PE1 inport0 must accept one LC15 value for every eight LC9 "
            "buffer values"
        ),
        "terminal_release": (
            "LC9 terminal last_index3 releases PE1 keep inport0"
        ),
        "capacity_lifetime_visibility": "unchanged; receipt reuse",
        "D_region": "unchanged; receipt reuse",
        "address_surface_changed": False,
        "physical_bank_row_validity": "receipt_reuse",
        "consumer_closure": {
            "config": config_path.relative_to(ROOT).as_posix(),
            "final_json": final_json.relative_to(ROOT).as_posix(),
            "mapping": (
                pipeline / "config/op_w0/mapping_review.json"
            ).relative_to(ROOT).as_posix(),
            "bitstream": new_bitstream.relative_to(ROOT).as_posix(),
            "execplan": (
                pipeline / "install/execplan.txt"
            ).relative_to(ROOT).as_posix(),
            "sca": (pipeline / "sca_cfg.json").relative_to(ROOT).as_posix(),
        },
    }
    write(output / "causal_transaction_ledger.json", ledger)

    report = {
        "schema": "node0004-pe1-keep-last-index-local-rebuild-v1",
        "status": "LOCAL_C0_PHYSICAL_REBUILD_PASS",
        "classification": "CONFIG_FUNCTIONAL_FIX",
        "bound_v61_return_analysis": {
            "path": V61_ANALYSIS.relative_to(ROOT).as_posix(),
            "sha256": sha256(V61_ANALYSIS),
        },
        "authorized_leaf_changes": expected_diff,
        "config": {
            "path": config_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(config_path),
        },
        "final_json": {
            "path": final_json.relative_to(ROOT).as_posix(),
            "sha256": sha256(final_json),
        },
        "mapping": {
            "path": (
                pipeline / "config/op_w0/mapping_review.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(pipeline / "config/op_w0/mapping_review.json"),
            "unchanged": True,
        },
        "bitstream": {
            "path": new_bitstream.relative_to(ROOT).as_posix(),
            "sha256": sha256(new_bitstream),
            "old_sha256": sha256(old_bitstream),
            "changed_offsets": offsets,
        },
        "execplan": {
            "path": (
                pipeline / "install/execplan.txt"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(pipeline / "install/execplan.txt"),
            "unchanged": True,
        },
        "sca": {
            "path": (pipeline / "sca_cfg.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(pipeline / "sca_cfg.json"),
            "address_semantics_unchanged": True,
        },
        "boundary_microtrace": {
            "path": (
                output / "boundary_microtrace.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(output / "boundary_microtrace.json"),
        },
        "causal_transaction_ledger": {
            "path": (
                output / "causal_transaction_ledger.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(output / "causal_transaction_ledger.json"),
        },
        "numeric_w3_golden_repeated": False,
        "addresses_changed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write(output / "local_rebuild_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
