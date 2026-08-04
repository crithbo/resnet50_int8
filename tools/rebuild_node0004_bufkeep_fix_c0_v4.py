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
    ROOT / "artifacts/operator_config_validation/r5-node0004-bufkeep-fix-c0-v4"
)
DEFAULT_CONFIG = ROOT / "configs/native_ndp_sim/node0004_bufkeep_fix_c0_v4"
V20_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_buffer_mode_fix_c0_v3/"
    "accumulate_waves/wave-0.json"
)
BOUND_V20_RETURN_SHA256 = (
    "b8a1ac0a9f7c9d705b21f332b010a3eaa59d131f85fd1eae524a2d2f26b57b55"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
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


def expected_keep_thresholds(config: dict[str, Any]) -> dict[str, int]:
    return {
        f"stream{index}": int(
            config["buffer_loop_configs"][f"GROUP{index}"]["COL_LC"]["last_index"]
        )
        for index in range(5)
    }


def buffer_ag_release(
    *, buffered_last_index: int, row_keep_threshold: int
) -> bool:
    """Mirror Buffer_AG_Idx_Queue.sv lines 149-150 for the ROW keep input."""
    return buffered_last_index <= row_keep_threshold


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
    wave_root = config_root / "accumulate_waves"
    for wave, config in sorted(configs.items()):
        write(wave_root / f"wave-{wave}.json", config)
    write(wave_root / "manifest.json", config_manifest)

    old = load(V20_CONFIG)
    diff = leaf_diff(old, configs[0])
    expected_diff = {
        "stream_engine.stream0.buf_idx_keep_last_index[0]": (4, 5),
        "stream_engine.stream1.buf_idx_keep_last_index[0]": (4, 5),
        "stream_engine.stream2.buf_idx_keep_last_index[0]": (4, 5),
        "stream_engine.stream3.buf_idx_keep_last_index[0]": (3, 4),
        "stream_engine.stream4.buf_idx_keep_last_index[0]": (4, 5),
    }
    observed_diff = {
        item["path"]: (item["old"], item["new"]) for item in diff
    }
    if observed_diff != expected_diff:
        raise SystemExit(f"unexpected v20-to-v21 logical leaf diff: {diff}")

    thresholds = expected_keep_thresholds(configs[0])
    release_proof: dict[str, dict[str, Any]] = {}
    for index in range(5):
        stream = f"stream{index}"
        terminal = thresholds[stream]
        old_threshold = int(
            old["stream_engine"][stream]["buf_idx_keep_last_index"][0]
        )
        new_threshold = int(
            configs[0]["stream_engine"][stream]["buf_idx_keep_last_index"][0]
        )
        proof = {
            "buffered_col_terminal": terminal,
            "old_row_keep_threshold": old_threshold,
            "old_releases_row": buffer_ag_release(
                buffered_last_index=terminal,
                row_keep_threshold=old_threshold,
            ),
            "new_row_keep_threshold": new_threshold,
            "new_releases_row": buffer_ag_release(
                buffered_last_index=terminal,
                row_keep_threshold=new_threshold,
            ),
        }
        if proof["old_releases_row"] or not proof["new_releases_row"]:
            raise SystemExit(f"Buffer-AG release proof failed for {stream}: {proof}")
        release_proof[stream] = proof

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
        "schema": "node0004-buffer-ag-row-keep-threshold-fix-local-rebuild-v1",
        "status": "LOCAL_C0_PHYSICAL_REBUILD_PASS",
        "classification": "CONFIG_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_numeric_and_matrix_payloads_reused": True,
        "bound_v20_return_sha256": BOUND_V20_RETURN_SHA256,
        "first_divergence": (
            "each WR_Buffer_AG enqueued/dequeued only the first row's two "
            "column entries; its ROW keep threshold was smaller than the "
            "buffered COL terminal, so Buffer_AG_Idx_Queue could not release "
            "ROW and generate the next row"
        ),
        "rtl_equation": (
            "row_release = "
            "(buffered_col_last_index <= row_keep_last_index)"
        ),
        "authorized_leaf_changes": [
            {
                "path": path,
                "owner": "Conv signed-A typed materializer",
                "input": (
                    "v20 BUFFER0_FLOW_BOUNDARY_V1 plus active "
                    "Buffer_AG_Idx_Queue keep-release equation"
                ),
                "formula": (
                    "buf_idx_keep_last_index[0] = "
                    "buffer_loop_configs.GROUPn.COL_LC.last_index"
                ),
                "old": old_value,
                "new": new_value,
            }
            for path, (old_value, new_value) in sorted(expected_diff.items())
        ],
        "release_proof": release_proof,
        "contract": contract,
        "v20_config": {
            "path": V20_CONFIG.relative_to(ROOT).as_posix(),
            "sha256": sha256(V20_CONFIG),
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
