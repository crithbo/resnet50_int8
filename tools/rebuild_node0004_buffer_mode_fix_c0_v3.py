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
    "r5-node0004-buffer-mode-fix-c0-v3"
)
DEFAULT_CONFIG = (
    ROOT / "configs/native_ndp_sim/node0004_buffer_mode_fix_c0_v3"
)
V19_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_a_pingpong_fix_c0_v2/"
    "accumulate_waves/wave-0.json"
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
        result = []
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


def arm_sequence(mode: int, lifetime: int, end_row: int) -> list[dict[str, int]]:
    """Mirror Array_Request_Manager lines 207-258 for accepted reads."""
    encoded_lifetime = lifetime - 1
    counter0 = 0
    counter1 = 0
    result: list[dict[str, int]] = []
    for accepted_index in range(1, lifetime + 2):
        address = counter1 if mode else counter0
        life = counter0 if mode else counter1
        clear = int(life == encoded_lifetime)
        result.append(
            {
                "accepted_index": accepted_index,
                "address_before": address,
                "life_before": life,
                "clear": clear,
            }
        )
        counter0_end = encoded_lifetime if mode else end_row
        end0 = counter0 == counter0_end
        counter0 = 0 if end0 else counter0 + 1
        if end0:
            counter1_end = end_row if mode else encoded_lifetime
            counter1 = 0 if counter1 == counter1_end else counter1 + 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config-output", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--python",
        type=Path,
        default=ROOT / ".venv/Scripts/python.exe",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    config_root = args.config_output.resolve()
    if output.exists() or config_root.exists():
        raise SystemExit("fresh output/config roots required")

    accumulate = build_fresh_accumulate_base(ROOT)
    contract = validate_first_conv_signed_a_local_contract(accumulate)
    modes = {
        name: int(accumulate["buffer_config"][name]["mode"])
        for name in ("buffer0", "buffer1", "buffer2", "buffer3")
    }
    if modes != {name: 1 for name in modes}:
        raise SystemExit(f"SA input buffers are not row-stationary: {modes}")
    write(config_root / "accumulate_base.json", accumulate)
    source_rel = (config_root / "accumulate_base.json").relative_to(ROOT)
    configs, manifest = build_strict_configs(
        ROOT,
        source_config_rel=source_rel,
        reuse_wave_addresses=True,
    )
    wave_root = config_root / "accumulate_waves"
    for wave, config in sorted(configs.items()):
        write(wave_root / f"wave-{wave}.json", config)
    write(wave_root / "manifest.json", manifest)

    old = load(V19_CONFIG)
    diff = leaf_diff(old, configs[0])
    expected = {
        "buffer_config.buffer0.mode": (0, 1),
        "buffer_config.buffer1.mode": (0, 1),
    }
    observed = {item["path"]: (item["old"], item["new"]) for item in diff}
    if observed != expected:
        raise SystemExit(f"unexpected v19-to-v20 logical leaf diff: {diff}")

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

    fixed = configs[0]["buffer_config"]["buffer0"]
    old_sequence = arm_sequence(
        0, int(fixed["buffer_life_time"]), int(fixed["buf_end_row_addr"])
    )
    fixed_sequence = arm_sequence(
        1, int(fixed["buffer_life_time"]), int(fixed["buf_end_row_addr"])
    )
    if [item["address_before"] for item in old_sequence[:2]] != [0, 1]:
        raise SystemExit("mode0 counterexample changed")
    if [item["address_before"] for item in fixed_sequence[:4]] != [0, 0, 0, 0]:
        raise SystemExit("mode1 four-use row retention changed")
    if fixed_sequence[3]["clear"] != 1 or fixed_sequence[4]["address_before"] != 1:
        raise SystemExit("mode1 clear/next-row boundary changed")

    bitstream = mapping / "modules_dump_128b.bin"
    sca = execplan / "pipeline_output/sca_cfg.json"
    report = {
        "schema": "node0004-buffer-mode-fix-c0-local-rebuild-v1",
        "status": "LOCAL_C0_PHYSICAL_REBUILD_PASS",
        "classification": "CONFIG_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_numeric_and_matrix_payloads_reused": True,
        "bound_v19_return_sha256": (
            "aba139e405f894564ec105e5929a3b02e6d44c6aae1d004d898d6f6106e27205"
        ),
        "first_divergence": (
            "Buffer0 completed its first ARM read, then mode0 advanced "
            "array_req_addr from row0 to unwritten row1 while row0 remained "
            "valid and its configured four-use lifetime remained unconsumed"
        ),
        "authorized_leaf_changes": [
            {
                "path": path,
                "owner": "Conv signed-A typed materializer",
                "input": (
                    "v19 BUFFER0_FLOW_BOUNDARY_V1 plus active "
                    "Array_Request_Manager counter equations"
                ),
                "formula": (
                    "mode=1: array_req_addr=array_counter_1 and "
                    "array_life_cnt=array_counter_0, so lifetime is the "
                    "inner counter before row advance"
                ),
                "old": old_value,
                "new": new_value,
            }
            for path, (old_value, new_value) in sorted(expected.items())
        ],
        "rtl_counterexample": {
            "mode0_first_two_addresses": [
                item["address_before"] for item in old_sequence[:2]
            ],
            "mode1_first_four_addresses": [
                item["address_before"] for item in fixed_sequence[:4]
            ],
            "mode1_fourth_accept_clear": fixed_sequence[3]["clear"],
            "mode1_fifth_accept_address": fixed_sequence[4]["address_before"],
        },
        "contract": contract,
        "v19_config": {
            "path": V19_CONFIG.relative_to(ROOT).as_posix(),
            "sha256": sha256(V19_CONFIG),
        },
        "fresh_config": {
            "path": (wave_root / "wave-0.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(wave_root / "wave-0.json"),
        },
        "mapping_manifest": {
            "path": (mapping / "bundle_manifest.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(mapping / "bundle_manifest.json"),
        },
        "bitstream": {
            "path": bitstream.relative_to(ROOT).as_posix(),
            "sha256": sha256(bitstream),
        },
        "execplan_manifest": {
            "path": (execplan / "bundle_manifest.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(execplan / "bundle_manifest.json"),
        },
        "sca": {
            "path": sca.relative_to(ROOT).as_posix(),
            "sha256": sha256(sca),
        },
    }
    write(output / "local_rebuild_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
