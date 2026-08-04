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
    "r5-node0004-a-pingpong-fix-c0-v2"
)
DEFAULT_CONFIG = (
    ROOT / "configs/native_ndp_sim/node0004_a_pingpong_fix_c0_v2"
)
FROZEN_CONFIG = (
    ROOT
    / "artifacts/operator_config_validation/r5-node0004-assumed-hardware-v1/"
    "mapping/conv/op_w0/source_config.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _leaf_diff(left: Any, right: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left:
                result.append({"path": child, "old": None, "new": right[key]})
            elif key not in right:
                result.append({"path": child, "old": left[key], "new": None})
            else:
                result.extend(_leaf_diff(left[key], right[key], child))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        for index in range(max(len(left), len(right))):
            child = f"{prefix}[{index}]"
            if index >= len(left):
                result.append({"path": child, "old": None, "new": right[index]})
            elif index >= len(right):
                result.append({"path": child, "old": left[index], "new": None})
            else:
                result.extend(_leaf_diff(left[index], right[index], child))
        return result
    return [] if left == right else [{"path": prefix, "old": left, "new": right}]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config-output", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(
            r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
            r"\dependencies\python\python.exe"
        ),
    )
    args = parser.parse_args()
    output = args.output.resolve()
    config_root = args.config_output.resolve()
    if output.exists() or config_root.exists():
        raise SystemExit("fresh output/config roots required")

    accumulate = build_fresh_accumulate_base(ROOT)
    contract = validate_first_conv_signed_a_local_contract(accumulate)
    _write(config_root / "accumulate_base.json", accumulate)
    source_rel = (config_root / "accumulate_base.json").relative_to(ROOT)
    configs, manifest = build_strict_configs(
        ROOT,
        source_config_rel=source_rel,
        reuse_wave_addresses=True,
    )
    wave_root = config_root / "accumulate_waves"
    for wave, config in sorted(configs.items()):
        _write(wave_root / f"wave-{wave}.json", config)
    _write(wave_root / "manifest.json", manifest)

    frozen = _load(FROZEN_CONFIG)
    diff = _leaf_diff(frozen, configs[0])
    expected = {
        "stream_engine.stream0.ping_pong": (0, 1),
        "stream_engine.stream0.pingpong_last_index": (None, 4),
    }
    observed = {
        item["path"]: (item["old"], item["new"])
        for item in diff
    }
    if observed != expected:
        raise SystemExit(f"unexpected frozen-config leaf diff: {diff}")

    ndp = ROOT / "ndp-sim"
    patchset_path = ROOT / PATCHSET_REL
    patchset = build_patchset_manifest(
        ndp, patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID
    )
    if _load(patchset_path) != patchset:
        raise SystemExit("active hash-bound node0004 patchset differs")

    graph = output / "conv_graphs/wave-0.json"
    _write(graph, fresh_conv_wave_graph_spec(0))
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

    report = {
        "schema": "node0004-a-pingpong-fix-c0-local-rebuild-v1",
        "status": "LOCAL_C0_PHYSICAL_REBUILD_PASS",
        "classification": "CONFIG_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_numeric_and_matrix_payloads_reused": True,
        "first_divergence": (
            "MSE stream0 kept writing physical buffer0 while SA inport0 "
            "switched from buffer0 to unwritten buffer1 after terminal tag 4"
        ),
        "authorized_leaf_changes": [
            {
                "path": path,
                "owner": "Conv signed-A local materializer",
                "input": (
                    "SA inport0 pingpong enable and terminal tag plus RTL "
                    "buffer0/1 physical pairing"
                ),
                "formula": (
                    "stream0.ping_pong = inport0.pingpong_en; "
                    "stream0.pingpong_last_index = "
                    "inport0.pingpong_last_index"
                ),
                "old": old,
                "new": new,
            }
            for path, (old, new) in sorted(expected.items())
        ],
        "contract": contract,
        "frozen_config": {
            "path": FROZEN_CONFIG.relative_to(ROOT).as_posix(),
            "sha256": _sha256(FROZEN_CONFIG),
        },
        "fresh_config": {
            "path": (wave_root / "wave-0.json").relative_to(ROOT).as_posix(),
            "sha256": _sha256(wave_root / "wave-0.json"),
        },
        "mapping_manifest": {
            "path": (mapping / "bundle_manifest.json").relative_to(ROOT).as_posix(),
            "sha256": _sha256(mapping / "bundle_manifest.json"),
        },
        "bitstream": {
            "path": (mapping / "modules_dump_128b.bin").relative_to(ROOT).as_posix(),
            "sha256": _sha256(mapping / "modules_dump_128b.bin"),
        },
        "execplan_manifest": {
            "path": (execplan / "bundle_manifest.json").relative_to(ROOT).as_posix(),
            "sha256": _sha256(execplan / "bundle_manifest.json"),
        },
        "sca": {
            "path": (execplan / "pipeline_output/sca_cfg.json")
            .relative_to(ROOT)
            .as_posix(),
        },
    }
    sca_path = ROOT / report["sca"]["path"]
    report["sca"]["sha256"] = _sha256(sca_path)
    _write(output / "local_rebuild_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
