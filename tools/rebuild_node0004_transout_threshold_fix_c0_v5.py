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


DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-transout-threshold-fix-c0-v5"
)
DEFAULT_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/"
    "node0004_transout_threshold_fix_c0_v5"
)
V21_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_bufkeep_fix_c0_v4/"
    "accumulate_waves/wave-0.json"
)
BOUND_V25_RETURN_SHA256 = (
    "e6b35bc2f311b9cdf184c65bdd6f8ad834ededf6888ffb390943b83d87d1ac5f"
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


def classify_terminal(index: int, threshold: int) -> dict[str, Any]:
    width = 5
    mask = (1 << width) - 1
    diff = (index - threshold) & mask
    return {
        "index": index,
        "threshold": threshold,
        "diff": diff,
        "ignore": bool((diff >> 4) == 0 and (diff & 0xF) != 0),
        "matched": diff == 0,
        "out": bool(diff >> 4),
        "release": bool(diff == 0 or (diff >> 4)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config-output", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--python", type=Path, default=ROOT / ".venv/Scripts/python.exe"
    )
    args = parser.parse_args()
    output = args.output.resolve()
    config_root = args.config_output.resolve()
    if output.exists() or config_root.exists():
        raise SystemExit("fresh output/config roots required")

    accumulate = build_fresh_accumulate_base(ROOT)
    contract = validate_first_conv_signed_a_local_contract(accumulate)
    write(config_root / "accumulate_base.json", accumulate)
    source_rel = (config_root / "accumulate_base.json").relative_to(ROOT)
    configs, config_manifest = build_strict_configs(
        ROOT,
        source_config_rel=source_rel,
        reuse_wave_addresses=True,
    )
    if configs[0]["special_array"]["transout_last_index"] != OLD_THRESHOLD:
        raise SystemExit("fresh typed materializer preimage threshold differs")
    configs[0]["special_array"]["transout_last_index"] = NEW_THRESHOLD

    wave_root = config_root / "accumulate_waves"
    for wave, config in sorted(configs.items()):
        write(wave_root / f"wave-{wave}.json", config)
    config_manifest["authorized_post_materialization_override"] = {
        "owner": "Conv/SA integration owner",
        "path": "wave-0.special_array.transout_last_index",
        "old": OLD_THRESHOLD,
        "new": NEW_THRESHOLD,
        "input": (
            "v25 TERMINAL_MATCH_EDGE_V1 and TERMINAL_MATCH_BOUNDARY_V1"
        ),
        "formula": (
            "max accepted A/B terminal last_index; RTL releases when "
            "accepted_index <= transout_last_index"
        ),
    }
    write(wave_root / "manifest.json", config_manifest)

    old = load(V21_CONFIG)
    diff = leaf_diff(old, configs[0])
    expected = [
        {
            "path": "special_array.transout_last_index",
            "old": OLD_THRESHOLD,
            "new": NEW_THRESHOLD,
        }
    ]
    if diff != expected:
        raise SystemExit(f"unexpected logical leaf diff: {diff}")

    terminal_histogram = {4: 64, 5: 192}
    proof = {
        str(index): {
            "occurrences": occurrences,
            "old": classify_terminal(index, OLD_THRESHOLD),
            "new": classify_terminal(index, NEW_THRESHOLD),
        }
        for index, occurrences in terminal_histogram.items()
    }
    if any(
        row["old"]["release"] or not row["new"]["release"]
        for row in proof.values()
    ):
        raise SystemExit(f"terminal release proof failed: {proof}")

    ndp = ROOT / "ndp-sim"
    patchset_path = ROOT / PATCHSET_REL
    patchset = build_patchset_manifest(
        ndp, patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID
    )
    if load(patchset_path) != patchset:
        raise SystemExit("active hash-bound node0004 patchset differs")

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
    execplan_path = execplan / "pipeline_output/install/execplan.txt"
    sca = execplan / "pipeline_output/sca_cfg.json"
    report = {
        "schema": "node0004-transout-threshold-config-fix-local-rebuild-v1",
        "status": "LOCAL_C0_PHYSICAL_REBUILD_PASS",
        "classification": "CONFIG_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_numeric_and_matrix_payloads_reused": True,
        "bound_v25_return_sha256": BOUND_V25_RETURN_SHA256,
        "last_proven_good": (
            "QUALIFIED_A_B_TERMINAL_ACCEPT_WITH_ALL_OPERANDS_MATCHED"
        ),
        "first_divergence": (
            "ACCEPTED_TERMINAL_INDEX_TO_TRANSOUT_THRESHOLD_CLASSIFICATION"
        ),
        "rtl_equations": {
            "diff": "accepted_last_index - transout_last_index (5-bit modulo)",
            "ignore": "last && !diff[4] && |diff[3:0]",
            "matched": "last && !|diff",
            "out": "last && diff[4]",
            "release": "matched || out",
        },
        "authorized_leaf_changes": [
            {
                "path": "special_array.transout_last_index",
                "owner": "Conv/SA integration owner",
                "input": (
                    "256 v25 qualified terminal accepts: index5 x192, "
                    "index4 x64; configured threshold2 ignored all 256"
                ),
                "formula": "max accepted terminal last_index",
                "old": OLD_THRESHOLD,
                "new": NEW_THRESHOLD,
            }
        ],
        "terminal_release_proof": proof,
        "old_ignored_occurrences": 256,
        "new_released_occurrences": 256,
        "contract": contract,
        "v21_config": {
            "path": V21_CONFIG.relative_to(ROOT).as_posix(),
            "sha256": sha256(V21_CONFIG),
        },
        "fresh_config": {
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
            "path": execplan_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(execplan_path),
        },
        "sca": {
            "path": sca.relative_to(ROOT).as_posix(),
            "sha256": sha256(sca),
        },
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write(output / "local_rebuild_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
