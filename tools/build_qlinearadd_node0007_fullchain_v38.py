from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_REL = Path("artifacts/q38")
SOURCE_V18_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-column-pair-v18"
)
SOURCE_V36_REL = Path(
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36"
)
CONFIG_V36_REL = Path(
    "configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36"
)
STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
    "op_tail_mul",
    "op_tail_round",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def leaf_diffs(before: Any, after: Any, prefix: str = "") -> list[str]:
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[str] = []
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(leaf_diffs(before[key], after[key], child))
        return result
    if isinstance(before, list) and isinstance(after, list):
        result = []
        for index in range(max(len(before), len(after))):
            child = f"{prefix}[{index}]"
            if index >= len(before) or index >= len(after):
                result.append(child)
            else:
                result.extend(leaf_diffs(before[index], after[index], child))
        return result
    return [] if before == after else [prefix]


def main() -> int:
    output = ROOT / OUT_REL
    if (output / "build_receipt.json").exists():
        raise ValueError(f"completed full-chain output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)

    source_v18 = ROOT / SOURCE_V18_REL
    source_v36 = ROOT / SOURCE_V36_REL
    config_v36 = ROOT / CONFIG_V36_REL
    graph = json.loads((source_v18 / "graph.json").read_text(encoding="utf-8"))
    if [item["id"] for item in graph["operators"]] != list(STAGES):
        raise ValueError("v18 full-chain graph stage order differs")
    graph["params"]["fp32_output32_fix"] = True
    graph["params"]["fp32_rowpair_fix"] = True
    graph["params"]["full_chain_successor"] = "v38"
    graph_path = output / "graph.json"
    write_json(graph_path, graph)

    mapping_bundles = {
        stage: (
            source_v36 / "mapping/op_fp32_add"
            if stage == "op_fp32_add"
            else source_v18 / "mapping" / stage
        )
        for stage in STAGES
    }
    for stage, bundle in mapping_bundles.items():
        if not (bundle / "artifact_validation_report.json").is_file():
            raise FileNotFoundError(f"mapping bundle absent for {stage}: {bundle}")

    assembled = output / "w"
    if assembled.exists():
        raise ValueError(f"fresh assembled execplan required: {assembled}")
    source_pipeline_v18 = source_v18 / "execplan/pipeline_output"
    source_pipeline_v36 = source_v36 / "execplan/pipeline_output"
    pipeline = assembled / "pipeline_output"
    pipeline.mkdir(parents=True)
    shutil.copytree(source_pipeline_v18 / "install", pipeline / "install")
    shutil.copytree(source_pipeline_v18 / "jsons", pipeline / "jsons")
    for name in ("sca_cfg.json", "sca_cfg_D.json", "graph_withbaseaddr.json"):
        shutil.copy2(source_pipeline_v18 / name, pipeline / name)

    fp32_relatives = [
        path.relative_to(source_pipeline_v36)
        for path in source_pipeline_v36.rglob("*")
        if path.is_file()
        and "op_fp32_add" in path.as_posix()
        and (
            path.is_relative_to(source_pipeline_v36 / "install")
            or path.is_relative_to(source_pipeline_v36 / "jsons")
        )
    ]
    if len(fp32_relatives) != 3:
        raise ValueError("v36 FP32 artifact cardinality differs")
    for relative in fp32_relatives:
        target = pipeline / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_pipeline_v36 / relative, target)

    old_stage = (
        source_pipeline_v18 / "install/execplan_op_fp32_add.txt"
    ).read_bytes().splitlines(keepends=True)
    new_stage = (
        source_pipeline_v36 / "install/execplan_op_fp32_add.txt"
    ).read_bytes().splitlines(keepends=True)
    changed_lines = [
        index
        for index, (old, new) in enumerate(zip(old_stage, new_stage, strict=True))
        if old != new
    ]
    if changed_lines != [0]:
        raise ValueError(f"FP32 execplan delta differs: {changed_lines}")
    full_execplan = pipeline / "install/execplan.txt"
    full_lines = full_execplan.read_bytes().splitlines(keepends=True)
    explained = (
        source_pipeline_v18 / "instructions_explained.txt"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"<([01]{64})>\s+Load_Config for operator op_fp32_add", explained
    )
    if match is None:
        raise ValueError("full execplan FP32 Load_Config explanation absent")
    old_word = match.group(1).encode("ascii")
    anchors = [
        (line_index, half)
        for line_index, line in enumerate(full_lines)
        for half in (0, 64)
        if line[half : half + 64] == old_word
    ]
    if len(anchors) != 1:
        raise ValueError(f"full execplan FP32 Load_Config anchor differs: {anchors}")
    line_index, half = anchors[0]
    line = full_lines[line_index]
    new_length_bits = new_stage[0][:8]
    full_lines[line_index] = (
        line[:half] + new_length_bits + line[half + 8 :]
    )
    full_execplan.write_bytes(b"".join(full_lines))

    final_root = pipeline / "jsons"
    final_receipts: dict[str, dict[str, Any]] = {}
    for stage in STAGES:
        matches = sorted(final_root.glob(f"{stage}_*.json"))
        if len(matches) != 1:
            raise ValueError(f"final JSON cardinality differs for {stage}")
        final_path = matches[0]
        final_json = json.loads(final_path.read_text(encoding="utf-8"))
        expected = json.loads(
            (config_v36 / f"{stage}.json").read_text(encoding="utf-8")
        )
        diffs = [
            path
            for path in leaf_diffs(expected, final_json)
            if not path.endswith(".base_addr")
        ]
        if diffs:
            raise ValueError(f"final JSON semantic diff for {stage}: {diffs[:8]}")
        final_receipts[stage] = {
            "path": final_path.relative_to(ROOT).as_posix(),
            "bytes": final_path.stat().st_size,
            "sha256": sha256_file(final_path),
            "semantic_diffs_excluding_address_binding": 0,
        }

    sca = json.loads((pipeline / "sca_cfg.json").read_text(encoding="utf-8"))
    sca_d = json.loads((pipeline / "sca_cfg_D.json").read_text(encoding="utf-8"))
    sca_d = {
        key: value
        for key, value in sca_d.items()
        if key.startswith("op_tail_round_matrixD_slice")
    }
    write_json(pipeline / "sca_cfg_D.json", sca_d)
    if sca.get("Repeat_Num") != 6 or len(sca_d) != 28:
        raise ValueError("six-stage/28D SCA cardinality differs")
    if not all("op_tail_round" in key for key in sca_d):
        raise ValueError("formal D does not bind final tail_round stage")

    receipt = {
        "schema": "qlinearadd-node0007-fullchain-build-v38",
        "status": "LOCAL_SIX_STAGE_EXECPLAN_MATERIALIZED",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "stage_order": list(STAGES),
        "mapping_initial_state": "REUSED_VALIDATED_BYTE_EXACT_BUNDLES",
        "execplan_initial_state": (
            "BYTE_EXACT_V18_FULL_CHAIN_WITH_SINGLE_V36_FP32_LOAD_CONFIG"
        ),
        "mapping_sources": {
            stage: {
                "path": bundle.relative_to(ROOT).as_posix(),
                "artifact_validation_sha256": sha256_file(
                    bundle / "artifact_validation_report.json"
                ),
            }
            for stage, bundle in mapping_bundles.items()
        },
        "graph": {
            "path": graph_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(graph_path),
        },
        "final_jsons": final_receipts,
        "execplan_assembly": {
            "path": pipeline.relative_to(ROOT).as_posix(),
            "full_execplan_sha256": sha256_file(full_execplan),
            "command_count": len(full_lines),
            "fp32_changed_command_indices": changed_lines,
            "fp32_load_config_replacements": 1,
            "stage_specific_fp32_sha256": sha256_file(
                pipeline / "install/execplan_op_fp32_add.txt"
            ),
            "sca_cardinality_valid": True,
        },
        "sca": {
            "repeat_num": sca["Repeat_Num"],
            "exec_length": sca["Exec_Length"],
            "formal_D_count": len(sca_d),
            "final_stage_only": True,
        },
        "frozen_semantics": {
            "numeric_W3_qparams_tail": True,
            "workload_config_golden": True,
            "v37_fp32_output32": True,
            "addresses": True,
            "functional_rtl": True,
        },
        "numeric_analysis_repeated": False,
        "split_c_repeated": False,
        "server_action": False,
    }
    write_json(output / "build_receipt.json", receipt)
    print(
        json.dumps(
            {
                "valid": True,
                "output": OUT_REL.as_posix(),
                "receipt_sha256": sha256_file(output / "build_receipt.json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
