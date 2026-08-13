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

from resnet50_pipeline.conv_native_package import build_strict_configs  # noqa: E402
from resnet50_pipeline.conv_sa_contract import (  # noqa: E402
    validate_first_conv_signed_a_local_contract,
)
from resnet50_pipeline.node0004_assumed_hardware import (  # noqa: E402
    PATCHSET_REL,
    build_fresh_accumulate_base,
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
    "r5-conv-native-four-lane-0cc-p9-tx5-c0"
)
CONFIG_ROOT = (
    ROOT
    / "configs/native_ndp_sim/"
    "r5_conv_native_four_lane_0cc_p9_tx5_c0"
)
FROZEN_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/r5_conv_native_four_lane_df23e4d_v1/"
    "accumulate_waves/wave-0.json"
)
P7_BITSTREAM = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_0cc_p7/workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
P8F_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p8f_return_analysis/"
    "report.json"
)
OLD_THRESHOLD = 2
NEW_THRESHOLD = 5


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


def classify(index: int, threshold: int) -> dict[str, Any]:
    diff = (index - threshold) & 0x1F
    ignore = not bool(diff & 0x10) and bool(diff & 0x0F)
    return {
        "index": index,
        "threshold": threshold,
        "diff_u5": diff,
        "ignore": ignore,
        "matched": diff == 0,
        "out": bool(diff & 0x10),
        "release": diff == 0 or bool(diff & 0x10),
    }


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

    p8f = load(P8F_ANALYSIS)
    if (
        not p8f.get("valid")
        or p8f.get("status")
        != "LONG_RUNNING_HANG_CONFIG_FIX_SUCCESSOR_REQUIRED"
    ):
        raise SystemExit("bound p8f return analysis is not the accepted successor input")

    accumulate = build_fresh_accumulate_base(ROOT)
    contract = validate_first_conv_signed_a_local_contract(accumulate)
    write(config_root / "accumulate_base.json", accumulate)
    source_rel = (config_root / "accumulate_base.json").relative_to(ROOT)
    configs, manifest = build_strict_configs(
        ROOT,
        source_config_rel=source_rel,
        reuse_wave_addresses=True,
    )
    preimage = configs[0]
    frozen = load(FROZEN_CONFIG)
    if leaf_diff(frozen, preimage):
        raise SystemExit("typed materializer no longer reproduces frozen native wave0")
    if preimage["special_array"]["transout_last_index"] != OLD_THRESHOLD:
        raise SystemExit("typed materializer threshold preimage differs")
    configs[0]["special_array"]["transout_last_index"] = NEW_THRESHOLD

    wave_root = config_root / "accumulate_waves"
    write(wave_root / "wave-0.json", configs[0])
    manifest["scope"] = "wave0 changed causal slice only"
    manifest["unmaterialized_unchanged_waves"] = [1, 2]
    manifest["authorized_post_materialization_override"] = {
        "path": "wave-0.special_array.transout_last_index",
        "old": OLD_THRESHOLD,
        "new": NEW_THRESHOLD,
        "formula": "max accepted terminal last_index",
        "source": (
            "historical 256/256 accepted-terminal trace: "
            "last_index=4 x64, last_index=5 x192"
        ),
    }
    write(wave_root / "manifest.json", manifest)
    expected_diff = [
        {
            "path": "special_array.transout_last_index",
            "old": OLD_THRESHOLD,
            "new": NEW_THRESHOLD,
        }
    ]
    if leaf_diff(frozen, configs[0]) != expected_diff:
        raise SystemExit("logical config diff is not the single authorized leaf")

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
        config_path=wave_root / "wave-0.json",
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

    bitstream = mapping / "modules_dump_128b.bin"
    offsets = changed_offsets(P7_BITSTREAM.read_bytes(), bitstream.read_bytes())
    if offsets != [4459, 4460, 4461]:
        raise SystemExit(f"unexpected bitstream delta offsets: {offsets}")

    histogram = {4: 64, 5: 192}
    cases = {
        str(index): {
            "occurrences": count,
            "threshold2": classify(index, 2),
            "threshold5": classify(index, 5),
        }
        for index, count in histogram.items()
    }
    if any(
        row["threshold2"]["release"] or not row["threshold5"]["release"]
        for row in cases.values()
    ):
        raise SystemExit("terminal release proof failed")
    boundary_trace = {
        "schema": "conv-native-four-lane-terminal-boundary-microtrace-v1",
        "status": "PASS",
        "logic": "final exact RTL 5-bit subtract/classifier predicate",
        "threshold": NEW_THRESHOLD,
        "conjunct_neighbors": {
            "less_than": classify(4, NEW_THRESHOLD),
            "equal": classify(5, NEW_THRESHOLD),
            "greater_than": classify(6, NEW_THRESHOLD),
        },
        "occurrence_boundaries": [
            {"ordinal": 0, "last_index": 5},
            {"ordinal": 254, "last_index": 4},
            {"ordinal": 255, "last_index": 5},
            {"ordinal": 256, "event": "one-after", "terminal_accept": False},
        ],
        "negative_threshold2": {
            "released": 0,
            "ignored": 256,
        },
        "negative_threshold4": {
            "released": 64,
            "ignored": 192,
        },
        "threshold5": {
            "released": 256,
            "ignored": 0,
        },
    }
    write(output / "boundary_microtrace.json", boundary_trace)

    pipeline = execplan / "pipeline_output"
    ledger = {
        "schema": "conv-native-four-lane-changed-causal-transaction-ledger-v1",
        "status": "PASS",
        "changed_slice": "wave0 special_array.transout_last_index only",
        "producer_exact_byte_set": "unchanged; frozen c0 matrices and addresses",
        "buffer_bank_lane_valid": "unchanged; receipt reuse",
        "consumer_required_set": {
            "accepted_terminal_indices": histogram,
            "required_release_count": 256,
            "observed_release_under_threshold2": 0,
            "predicted_release_under_threshold5": 256,
        },
        "terminal_release": "threshold5 releases both accepted indices 4 and 5",
        "capacity_lifetime_visibility": "unchanged; receipt reuse",
        "D_region": "unchanged; receipt reuse",
        "address_surface_changed": False,
        "physical_bank_row_validity": "receipt_reuse",
        "consumer_closure": {
            "config": (wave_root / "wave-0.json").relative_to(ROOT).as_posix(),
            "mapping": (
                mapping / "artifact_validation_report.json"
            ).relative_to(ROOT).as_posix(),
            "bitstream": bitstream.relative_to(ROOT).as_posix(),
            "execplan": (
                pipeline / "install/execplan.txt"
            ).relative_to(ROOT).as_posix(),
            "sca": (pipeline / "sca_cfg.json").relative_to(ROOT).as_posix(),
        },
    }
    write(output / "causal_transaction_ledger.json", ledger)

    report = {
        "schema": "conv-native-four-lane-0ccae916-p9-tx5-local-rebuild-v1",
        "status": "LOCAL_C0_PHYSICAL_REBUILD_PASS",
        "classification": "CONFIG_FUNCTIONAL_FIX",
        "bound_p8f_return_analysis": {
            "path": P8F_ANALYSIS.relative_to(ROOT).as_posix(),
            "sha256": sha256(P8F_ANALYSIS),
        },
        "authorized_leaf_changes": expected_diff,
        "terminal_release_proof": cases,
        "old_ignored_occurrences": 256,
        "new_released_occurrences": 256,
        "bitstream_delta": {
            "old_sha256": sha256(P7_BITSTREAM),
            "new_sha256": sha256(bitstream),
            "changed_offsets": offsets,
        },
        "config": {
            "path": (wave_root / "wave-0.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(wave_root / "wave-0.json"),
        },
        "mapping": {
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
        "functional_rtl_modified": False,
        "server_action": False,
        "contract": contract,
    }
    write(output / "local_rebuild_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
