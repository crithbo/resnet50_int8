from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.ndp_patch_toolchain import (
    apply_patchset_in_place,
    validate_patchset_manifest,
)
from resnet50_pipeline.operator_config_execplan_evidence import (
    _copy_native_tool,
    _install_patchset_base_files,
    _install_validated_configs,
    _merge_mapping_caches,
    _validate_run,
)


SOURCE = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-column-pair-v18"
)
GRAPH = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-split-workloads-v25/segment_A/graph.json"
)
OUTPUT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-split-workloads-v25-debug-a"
)
PATCHSET_PATH = ROOT / (
    "contracts/ndp_patch_toolchain_"
    "qlinearadd_node0007_d_buffer_column_pair_v18.json"
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if OUTPUT.exists():
        print(f"refusing existing debug output: {OUTPUT}", file=sys.stderr)
        return 1
    tool = OUTPUT / "tool"
    _copy_native_tool(ROOT / "ndp-sim", tool)
    patchset = load(PATCHSET_PATH)
    validate_patchset_manifest(patchset, ROOT / "ndp-sim")
    _install_patchset_base_files(
        source_root=ROOT / "ndp-sim",
        tool_root=tool,
        patchset=patchset,
    )
    apply_patchset_in_place(tool, patchset_id=patchset["patchset_id"])
    operators = [
        {"id": item["id"], "type": item["type"]}
        for item in load(GRAPH)["operators"]
    ]
    validated = {}
    for item in operators:
        bundle = SOURCE / "mapping" / item["id"]
        validated[item["id"]] = {
            "bundle": bundle,
            "config": bundle / "source_config.json",
            "evidence": load(bundle / "mapping_evidence.json"),
            "cache_files": sorted((bundle / "mapping_cache").glob("*")),
        }
    _install_validated_configs(tool, operators, validated)
    cache = tool / "bitstream/config/mapping_cache"
    cache.mkdir(parents=True, exist_ok=True)
    _merge_mapping_caches(validated, cache)
    env = dict(os.environ)
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
            "PYTHONHASHSEED": "0",
            "MPLBACKEND": "Agg",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(tool / "model_execplan/main.py"),
            str(GRAPH),
        ],
        cwd=tool,
        env=env,
        capture_output=True,
        timeout=900,
        check=False,
    )
    (OUTPUT / "planner.stdout.log").write_bytes(completed.stdout)
    (OUTPUT / "planner.stderr.log").write_bytes(completed.stderr)
    graph_root = tool / "model_execplan/output/graph"
    report = _validate_run(
        graph_root=graph_root,
        graph_withbaseaddr=graph_root / "graph_withbaseaddr.json",
        validated=validated,
    )
    (OUTPUT / "validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
