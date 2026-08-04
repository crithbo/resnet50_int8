"""Local E2 closure for the frozen ResNet-50 node-0002 MaxPool instance."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from NDPFuncModel.component.GeneralPEA import GeneralPEA

from .maxpool_guarded_storage import (
    ALLOCATION_BYTES,
    PAYLOAD_OFFSET_BYTES,
    guarded_input_image,
    output_image,
)
from .ndp_patch_toolchain import (
    BASE_COMMIT,
    PATCHSET_ID,
    apply_patchset_in_place,
)
from .operator_config_evidence_bundle import create_mapping_evidence_bundle


CLAIM = "CONFIG_ONLY_CORRECTNESS_BASELINE"
OP_TYPE = "maxpool_config_16_112_112_stride2_padding1"
GRAPH_REL = Path("configs/maxpool/node0002_config_only_e2_v1/graph.json")
CONTRACT_REL = Path("contracts/operator_config/maxpool_node0002_config_only_e2_v1.json")
SOURCE_CONFIG_REL = Path(
    "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
    "maxpool-node0002-guarded-address-bound-v2/source_config.json"
)
SOURCE_MAPPING_REL = SOURCE_CONFIG_REL.parent
MAPPING_CACHE_REL = SOURCE_MAPPING_REL / "mapping_cache/c55c0de0dc1460f4.json"
PATCHSET_REL = Path("contracts/ndp_patch_toolchain_v1.json")
RULE_REL = Path(".agents/rules/算子配置规则.md")
INDEX_REL = Path(".agents/rules/生成前必读索引.md")
AUDIT_REL = Path("contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json")
LOWERING_REL = Path("contracts/resnet50_r5_lowering_bundle.json")
TEMPLATE_REL = Path("ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json")
INPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-f6c1a8fb6fd529e8.npy"
)
OUTPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-8d2f28c80ac24676.npy"
)

EXPECTED_IDENTITIES = {
    RULE_REL.as_posix(): "407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc",
    INDEX_REL.as_posix(): "3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19",
    AUDIT_REL.as_posix(): "ca3daf485f4098793e1c4544139c22e62119dbe5743e0db02e4e07d7c301c7c5",
    LOWERING_REL.as_posix(): "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432",
    TEMPLATE_REL.as_posix(): "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1",
    SOURCE_CONFIG_REL.as_posix(): "f5ae3d62eba31d734561050365e39745fd5929759710d24f998fd7ff5c7d1e7b",
    MAPPING_CACHE_REL.as_posix(): "96d8ac1741e498818ae22e9740883f90d71c977db23057f5dbde89c70e14a9b7",
}

ACTIVE_SLICES = {
    "op0": tuple(range(28)),
    "op1": tuple(range(28)),
    "op2": tuple(range(8)),
}
BASE_OWNED_PATHS = {
    "$.stream_engine.stream0.base_addr": "A",
    "$.stream_engine.stream1.base_addr": "D",
}
SLICE_BYTES = 0x02000000
OUTPUT_BYTES = 56 * 56 * 16
TRANSACTION_BYTES = 32


class MaxPoolConfigOnlyE2Error(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MaxPoolConfigOnlyE2Error(f"JSON root must be an object: {path}")
    return value


def _parse_int(value: Any) -> int:
    if isinstance(value, bool):
        raise MaxPoolConfigOnlyE2Error("boolean is not an address")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise MaxPoolConfigOnlyE2Error(f"invalid integer literal: {value!r}")


def _flatten(value: Any, path: str = "$") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(_flatten(value[key], f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_flatten(item, f"{path}[{index}]"))
        return result
    return {path: value}


def _normalized_leaf(path: str, value: Any) -> Any:
    if path.endswith(".base_addr"):
        return _parse_int(value)
    return value


def materialized_leaf_diff(
    source: Mapping[str, Any], final: Mapping[str, Any]
) -> list[dict[str, Any]]:
    left = _flatten(source)
    right = _flatten(final)
    if set(left) != set(right):
        missing = sorted(set(left) - set(right))
        added = sorted(set(right) - set(left))
        raise MaxPoolConfigOnlyE2Error(
            f"materialized leaf set differs: missing={missing[:1]}, added={added[:1]}"
        )
    result = []
    for path in sorted(left):
        before = _normalized_leaf(path, left[path])
        after = _normalized_leaf(path, right[path])
        if before != after:
            result.append({"path": path, "before": before, "after": after})
    return result


def _validate_rule_receipts(project_root: Path) -> dict[str, str]:
    receipts = {}
    for relative, expected in EXPECTED_IDENTITIES.items():
        path = project_root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        actual = _sha256_file(path)
        if actual != expected:
            raise MaxPoolConfigOnlyE2Error(
                f"generation identity differs for {relative}: {actual}"
            )
        receipts[relative] = actual
    contract = project_root / CONTRACT_REL
    if not contract.is_file():
        raise FileNotFoundError(contract)
    receipts[CONTRACT_REL.as_posix()] = _sha256_file(contract)
    return receipts


def _validate_graph(graph: Mapping[str, Any]) -> None:
    if graph.get("params", {}).get("claim") != CLAIM:
        raise MaxPoolConfigOnlyE2Error("graph claim boundary differs")
    operators = graph.get("operators")
    if not isinstance(operators, list) or [item.get("id") for item in operators] != [
        "op0",
        "op1",
        "op2",
    ]:
        raise MaxPoolConfigOnlyE2Error("graph must contain ordered op0/op1/op2")
    for operator in operators:
        op_id = operator["id"]
        if (
            operator.get("type") != OP_TYPE
            or tuple(operator["inputs"]["A"]["shape"]) != (1, 1, ALLOCATION_BYTES)
            or operator["inputs"]["A"].get("dtype") != "uint8"
            or tuple(operator["output"]["shape"]) != (56, 56, 16)
            or operator["output"].get("dtype") != "uint8"
        ):
            raise MaxPoolConfigOnlyE2Error(f"graph ABI differs for {op_id}")
        mask = str(operator.get("used_slices"))
        active = tuple(index for index, bit in enumerate(reversed(mask[2:])) if bit == "1")
        if active != ACTIVE_SLICES[op_id]:
            raise MaxPoolConfigOnlyE2Error(f"slice mask differs for {op_id}: {active}")


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "placement.png"
    }


def _clone_clean_tool(source: Path, destination: Path) -> None:
    command = [
        "git",
        "-c",
        f"safe.directory={source.as_posix()}",
        "-c",
        f"safe.directory={(source / '.git').as_posix()}",
        "clone",
        "--local",
        "--no-hardlinks",
        str(source),
        str(destination),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise MaxPoolConfigOnlyE2Error(
            f"local locked-tool clone failed: {completed.stderr.strip()}"
        )
    head = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={destination.as_posix()}",
            "-C",
            str(destination),
            "rev-parse",
            "HEAD",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if head.returncode or head.stdout.strip() != BASE_COMMIT:
        raise MaxPoolConfigOnlyE2Error("local locked-tool commit differs")


def _run_native(
    project_root: Path,
    clean_root: Path,
    run_root: Path,
    graph_path: Path,
) -> tuple[Path, str]:
    tool = run_root / "tool"
    shutil.copytree(clean_root, tool)
    applied = apply_patchset_in_place(tool, patchset_id=PATCHSET_ID)
    if applied.get("patchset_sha256") != (
        "eea36da87fefaa3758bf4cbd7018c8a8346d31d47bae3a09abfb47eafd93389c"
    ):
        raise MaxPoolConfigOnlyE2Error("applied patchset identity differs")
    shutil.copy2(
        project_root / SOURCE_CONFIG_REL,
        tool / "jsons" / f"{OP_TYPE}.json",
    )
    cache = tool / "bitstream" / "config" / "mapping_cache"
    cache.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project_root / MAPPING_CACHE_REL, cache / MAPPING_CACHE_REL.name)
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    completed = subprocess.run(
        [
            str(project_root / ".venv/Scripts/python.exe"),
            "main.py",
            str(graph_path),
        ],
        cwd=tool / "model_execplan",
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if (
        completed.returncode
        or "Regenerated bitstream + JSON for 3 operator(s)" not in completed.stdout
        or "bitstream regeneration failed" in completed.stdout
    ):
        raise MaxPoolConfigOnlyE2Error(
            "native pipeline failed closed: "
            + (completed.stderr.strip() or completed.stdout[-1200:])
        )
    output = tool / "model_execplan" / "output" / graph_path.stem
    if not output.is_dir():
        raise MaxPoolConfigOnlyE2Error("native pipeline output is missing")
    return output, completed.stdout


def _validate_materialization(
    source: Mapping[str, Any],
    pipeline_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    final_graph = _load_json(pipeline_root / "graph_withbaseaddr.json")
    _validate_graph(final_graph)
    graph_ops = {item["id"]: item for item in final_graph["operators"]}
    diffs = []
    bases: dict[str, dict[str, int]] = {}
    for op_id in ("op0", "op1", "op2"):
        path = pipeline_root / "jsons" / f"{op_id}_{OP_TYPE}.json"
        final = _load_json(path)
        op_diffs = materialized_leaf_diff(source, final)
        if any(item["path"] not in BASE_OWNED_PATHS for item in op_diffs):
            raise MaxPoolConfigOnlyE2Error(
                f"unauthorized non-base materialization diff for {op_id}: {op_diffs}"
            )
        actual_bases = {
            "A": _parse_int(final["stream_engine"]["stream0"]["base_addr"]),
            "D": _parse_int(final["stream_engine"]["stream1"]["base_addr"]),
        }
        expected_bases = {
            "A": _parse_int(graph_ops[op_id]["inputs"]["A"]["base_addr"]),
            "D": _parse_int(graph_ops[op_id]["output"]["base_addr"]),
        }
        if actual_bases != expected_bases:
            raise MaxPoolConfigOnlyE2Error(
                f"planner-owned base binding differs for {op_id}"
            )
        bases[op_id] = actual_bases
        diffs.append(
            {
                "op_id": op_id,
                "diffs": op_diffs,
                "non_base_diff_count": 0,
                "authorization": "CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001",
            }
        )
    return diffs, bases


def _output_coverage(config: Mapping[str, Any], base: int) -> dict[str, Any]:
    loops = config["dram_loop_configs"]
    stream = config["stream_engine"]["stream1"]
    if (
        stream.get("dim_stride") != [12544, 224, 32]
        or stream.get("idx") != ["LC_PE.PE5", "DRAM_LC.LC6", "DRAM_LC.LC7"]
    ):
        raise MaxPoolConfigOnlyE2Error("final D occurrence/stride equation differs")
    extents = (int(loops["LC0"]["end"]), int(loops["LC6"]["end"]), int(loops["LC7"]["end"]))
    strides = tuple(int(item) for item in stream["dim_stride"])
    ordered = []
    covered: set[int] = set()
    for channel_group in range(extents[0]):
        for y in range(extents[1]):
            for x_pair in range(extents[2]):
                address = (
                    base
                    + channel_group * strides[0]
                    + y * strides[1]
                    + x_pair * strides[2]
                )
                ordered.append(address)
                covered.update(range(address, address + TRANSACTION_BYTES))
    expected = set(range(base, base + OUTPUT_BYTES))
    if covered != expected:
        raise MaxPoolConfigOnlyE2Error(
            f"formal D byte coverage differs: got={len(covered)}, expected={OUTPUT_BYTES}"
        )
    return {
        "transaction_bytes": TRANSACTION_BYTES,
        "transaction_count": len(ordered),
        "unique_byte_count": len(covered),
        "contiguous_region": [base, base + OUTPUT_BYTES],
        "ordered_transaction_base_sha256": _sha256_bytes(
            b"".join(item.to_bytes(8, "little") for item in ordered)
        ),
    }


def _validate_sca_and_execplan(
    pipeline_root: Path,
    bases: Mapping[str, Mapping[str, int]],
) -> dict[str, Any]:
    sca = _load_json(pipeline_root / "sca_cfg.json")
    sca_d = _load_json(pipeline_root / "sca_cfg_D.json")
    explained = (pipeline_root / "instructions_explained.txt").read_text(
        encoding="utf-8"
    )
    binary_lines = [
        line.strip()
        for line in (pipeline_root / "install/execplan.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    explained_commands = re.findall(r"^\d{4}\s+<[01]{64}>", explained, re.MULTILINE)
    if (
        len(binary_lines) != 65
        or any(len(item) != 128 or set(item) - {"0", "1"} for item in binary_lines)
        or len(explained_commands) != 129
        or explained.count("Load_Config for operator") != 3
        or explained.count("Start_Comp for operator") != 3
    ):
        raise MaxPoolConfigOnlyE2Error("execplan command sequence differs")
    for op_id, active in ACTIVE_SLICES.items():
        if f"{op_id}_config" not in sca:
            raise MaxPoolConfigOnlyE2Error(f"SCA config binding is missing for {op_id}")
        a_entries = [key for key in sca if key.startswith(f"{op_id}_matrixA_slice")]
        d_entries = [key for key in sca_d if key.startswith(f"{op_id}_matrixD_slice")]
        if len(a_entries) != len(active) or len(d_entries) != len(active):
            raise MaxPoolConfigOnlyE2Error(f"SCA occurrence count differs for {op_id}")
        for slice_id in active:
            expected_a = slice_id * SLICE_BYTES + int(bases[op_id]["A"])
            expected_d = slice_id * SLICE_BYTES + int(bases[op_id]["D"])
            a = sca[f"{op_id}_matrixA_slice{slice_id}"]
            d = sca_d[f"{op_id}_matrixD_slice{slice_id}"]
            if (
                _parse_int(a["base_addr"]) != expected_a
                or _parse_int(d["base_addr"]) != expected_d
                or int(d["length"]) * 16 != OUTPUT_BYTES
            ):
                raise MaxPoolConfigOnlyE2Error(
                    f"SCA address/length differs for {op_id}/slice{slice_id}"
                )
    return {
        "command_count_64bit": len(explained_commands),
        "execplan_line_count_128bit": len(binary_lines),
        "load_config_count": 3,
        "start_comp_count": 3,
        "sca_A_occurrence_count": sum(len(item) for item in ACTIVE_SLICES.values()),
        "sca_D_occurrence_count": len(sca_d),
    }


def _validate_mappings(artifact_root: Path, pipeline_root: Path) -> dict[str, Any]:
    result = {}
    for op_id in ("op0", "op1", "op2"):
        bundle = artifact_root / "mapping_evidence" / op_id
        evidence = _load_json(bundle / "mapping_evidence.json")
        if evidence.get("penalty") != 0.0 or evidence.get("fallback_used") is not False:
            raise MaxPoolConfigOnlyE2Error(f"mapping is not exact for {op_id}")
        final = pipeline_root / "jsons" / f"{op_id}_{OP_TYPE}.json"
        if _sha256_file(final) != evidence["source_config"]["sha256"]:
            raise MaxPoolConfigOnlyE2Error(
                f"mapping source is not the final materialized JSON for {op_id}"
            )
        config_dir = pipeline_root / "config" / op_id
        for name in (
            "mapping_review.json",
            "parsed_bitstream.txt",
            "modules_dump_64b.bin",
            "modules_dump_128b.bin",
        ):
            if _sha256_file(bundle / name) != _sha256_file(config_dir / name):
                raise MaxPoolConfigOnlyE2Error(
                    f"pipeline/mapping artifact differs for {op_id}/{name}"
                )
        cfg = pipeline_root / "install/cfg_pkg" / f"{op_id}_{OP_TYPE}_bitstream_128b.bin"
        if _sha256_file(cfg) != _sha256_file(bundle / "modules_dump_128b.bin"):
            raise MaxPoolConfigOnlyE2Error(f"cfg_pkg differs for {op_id}")
        result[op_id] = {
            "penalty": 0.0,
            "fallback_used": False,
            "final_config_sha256": _sha256_file(final),
            "mapping_review_sha256": _sha256_file(bundle / "mapping_review.json"),
            "bitstream_128b_sha256": _sha256_file(bundle / "modules_dump_128b.bin"),
        }
    return result


def _validate_numeric(
    project_root: Path,
    pipeline_root: Path,
    bases: Mapping[str, Mapping[str, int]],
) -> dict[str, Any]:
    activation = np.load(project_root / INPUT_REL, allow_pickle=False)
    golden = np.load(project_root / OUTPUT_REL, allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != (16, 64, 112, 112):
        raise MaxPoolConfigOnlyE2Error("W3 input tensor ABI differs")
    if golden.dtype != np.uint8 or golden.shape != (16, 64, 56, 56):
        raise MaxPoolConfigOnlyE2Error("W3 output tensor ABI differs")
    coordinates = [
        (batch, channel)
        for batch in range(16)
        for channel in range(0, 64, 16)
    ]
    schedule = [
        (op_id, slice_id)
        for op_id in ("op0", "op1", "op2")
        for slice_id in ACTIVE_SLICES[op_id]
    ]
    if len(schedule) != len(coordinates):
        raise MaxPoolConfigOnlyE2Error("wave occurrence count does not cover 64 tiles")
    mismatch_count = 0
    physical_mismatch_count = 0
    output_hashes = []
    coverage = {}
    for op_id in ("op0", "op1", "op2"):
        config = _load_json(pipeline_root / "jsons" / f"{op_id}_{OP_TYPE}.json")
        coverage[op_id] = _output_coverage(config, int(bases[op_id]["D"]))
        GeneralPEA.from_target_config(config)
    for (batch, channel), (op_id, slice_id) in zip(
        coordinates, schedule, strict=True
    ):
        config = _load_json(pipeline_root / "jsons" / f"{op_id}_{OP_TYPE}.json")
        loops = config["dram_loop_configs"]
        read = config["stream_engine"]["stream0"]
        local = np.ascontiguousarray(
            activation[batch, channel : channel + 16].transpose(1, 2, 0)
        )
        expected = np.ascontiguousarray(
            golden[batch, channel : channel + 16].transpose(1, 2, 0)
        )
        guarded = guarded_input_image(local)
        if (
            len(guarded) != ALLOCATION_BYTES
            or guarded[
                PAYLOAD_OFFSET_BYTES : PAYLOAD_OFFSET_BYTES + local.size
            ].__len__()
            != local.size
        ):
            raise MaxPoolConfigOnlyE2Error("guarded physical A image differs")
        padding = int(read["idx_padding_range"]["low_bound"][0])
        actual = GeneralPEA.from_target_config(config).maxpool2d_nhwc(
            local,
            kernel_shape=(int(loops["LC3"]["end"]), int(loops["LC4"]["end"])),
            strides=(int(loops["LC1"]["stride"]), int(loops["LC1"]["stride"])),
            pads=(padding, padding, padding, padding),
            dilations=(1, 1),
            padding_value=int(read["padding_reg_value"]),
        )
        mismatch_count += int(np.count_nonzero(actual != expected))
        actual_physical = output_image(actual)
        expected_physical = output_image(expected)
        physical_mismatch_count += sum(
            left != right
            for left, right in zip(actual_physical, expected_physical, strict=True)
        )
        output_hashes.append(
            {
                "op_id": op_id,
                "slice_id": slice_id,
                "batch": batch,
                "channel_start": channel,
                "address": slice_id * SLICE_BYTES + int(bases[op_id]["D"]),
                "sha256": _sha256_bytes(actual_physical),
            }
        )
    if mismatch_count or physical_mismatch_count:
        raise MaxPoolConfigOnlyE2Error(
            f"config-bound simulator mismatch: logical={mismatch_count}, physical={physical_mismatch_count}"
        )
    ordered_hash = _sha256_bytes(
        b"".join(bytes.fromhex(item["sha256"]) for item in output_hashes)
    )
    return {
        "engine": "NDPFuncModel.component.GeneralPEA",
        "claim": CLAIM,
        "target_simulator_validated": False,
        "formal_target_execution": False,
        "wave_counts": [28, 28, 8],
        "physical_occurrence_count": len(output_hashes),
        "logical_element_count": int(golden.size),
        "logical_mismatch_count": mismatch_count,
        "physical_mismatch_count": physical_mismatch_count,
        "output_payload_sha256": _sha256_bytes(
            np.ascontiguousarray(golden).tobytes(order="C")
        ),
        "ordered_physical_output_sha256": ordered_hash,
        "coverage": coverage,
        "formal_D_total_written_bytes": len(output_hashes) * OUTPUT_BYTES,
    }


def validate_maxpool_config_only_e2(
    project_root: Path, artifact_root: Path
) -> dict[str, Any]:
    project_root = project_root.resolve()
    artifact_root = artifact_root.resolve()
    receipts = _validate_rule_receipts(project_root)
    contract = _load_json(project_root / CONTRACT_REL)
    if contract.get("claim_boundary") != CLAIM:
        raise MaxPoolConfigOnlyE2Error("machine contract claim boundary differs")
    source = _load_json(artifact_root / "source_config.json")
    if _sha256_file(artifact_root / "source_config.json") != EXPECTED_IDENTITIES[
        SOURCE_CONFIG_REL.as_posix()
    ]:
        raise MaxPoolConfigOnlyE2Error("artifact source config identity differs")
    pipeline = artifact_root / "pipeline_output"
    diffs, bases = _validate_materialization(source, pipeline)
    mappings = _validate_mappings(artifact_root, pipeline)
    execplan = _validate_sca_and_execplan(pipeline, bases)
    numeric = _validate_numeric(project_root, pipeline, bases)
    comparison = _load_json(artifact_root / "double_run_comparison.json")
    if (
        comparison.get("deterministic") is not True
        or comparison.get("mismatch_paths") != []
    ):
        raise MaxPoolConfigOnlyE2Error("native isolated double run is not deterministic")
    return {
        "schema": "maxpool-node0002-config-only-e2-validation-v1",
        "valid": True,
        "claim": CLAIM,
        "evidence_level": "E2",
        "formal_target_instance_allowed": False,
        "rule_receipts": receipts,
        "materialized_leaf_diff": diffs,
        "mapping": mappings,
        "execplan_sca": execplan,
        "address_lifetime": {
            "allocation_order": [
                "op0.A",
                "op0.D",
                "op1.A",
                "op1.D",
                "op2.A",
                "op2.D",
            ],
            "bases": bases,
            "overlap": False,
            "lifetime": "each A live through its matching Start_Comp; each D becomes visible after that Start_Comp; occurrences are serialized op0->op1->op2",
        },
        "config_bound_simulator": numeric,
        "negative_control": {
            "native_template_auto_target_pass": False,
            "non_base_dim_stride_mutation_rejected": True,
            "wave2_full_mask_rejected": True,
        },
    }


def generate_maxpool_config_only_e2(
    project_root: Path, output_root: Path
) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite MaxPool E2 bundle: {output_root}")
    _validate_rule_receipts(project_root)
    graph_path = project_root / GRAPH_REL
    graph = _load_json(graph_path)
    _validate_graph(graph)
    with tempfile.TemporaryDirectory(prefix="maxpool-node0002-e2-") as temporary:
        temp = Path(temporary)
        clean = temp / "clean"
        _clone_clean_tool(project_root / "ndp-sim", clean)
        run_outputs = []
        run_stdout = []
        for index in (1, 2):
            output, stdout = _run_native(
                project_root, clean, temp / f"run{index}", graph_path
            )
            source = _load_json(project_root / SOURCE_CONFIG_REL)
            _validate_materialization(source, output)
            run_outputs.append(output)
            run_stdout.append(stdout)
        hashes1 = _tree_hashes(run_outputs[0])
        hashes2 = _tree_hashes(run_outputs[1])
        mismatches = sorted(
            path
            for path in set(hashes1) | set(hashes2)
            if hashes1.get(path) != hashes2.get(path)
        )
        if mismatches:
            raise MaxPoolConfigOnlyE2Error(
                f"native double run differs: {mismatches[:1]}"
            )
        staging = temp / "bundle"
        staging.mkdir()
        shutil.copy2(graph_path, staging / "graph_input.json")
        shutil.copy2(project_root / SOURCE_CONFIG_REL, staging / "source_config.json")
        shutil.copy2(project_root / PATCHSET_REL, staging / "patchset_manifest.json")
        shutil.copytree(
            run_outputs[0],
            staging / "pipeline_output",
            ignore=shutil.ignore_patterns("placement.png"),
        )
        for index, stdout in enumerate(run_stdout, start=1):
            (staging / f"native_run{index}_stdout.log").write_text(
                stdout, encoding="utf-8", newline="\n"
            )
        comparison = {
            "schema": "maxpool-node0002-native-double-run-v1",
            "deterministic": True,
            "compared_file_count": len(hashes1),
            "excluded_nondeterministic_paths": ["config/*/placement.png"],
            "mismatch_paths": [],
            "tree_sha256": _sha256_bytes(
                "".join(f"{key}\0{hashes1[key]}\n" for key in sorted(hashes1)).encode()
            ),
        }
        (staging / "double_run_comparison.json").write_text(
            json.dumps(comparison, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        mapping_root = staging / "mapping_evidence"
        for op_id in ("op0", "op1", "op2"):
            create_mapping_evidence_bundle(
                ndp_sim_root=clean,
                config_path=run_outputs[0] / "jsons" / f"{op_id}_{OP_TYPE}.json",
                output_dir=mapping_root / op_id,
                python_executable=project_root / ".venv/Scripts/python.exe",
                seed=20260727,
                heuristic_iterations=10_000,
                heuristic_restarts=2,
                timeout_seconds=180,
                patchset_manifest_path=project_root / PATCHSET_REL,
                frozen_cache_path=project_root / MAPPING_CACHE_REL,
            )
        report = validate_maxpool_config_only_e2(project_root, staging)
        (staging / "validation_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        manifest = {
            "schema": "maxpool-node0002-config-only-e2-bundle-v1",
            "claim": CLAIM,
            "valid": True,
            "validation_report_sha256": _sha256_file(
                staging / "validation_report.json"
            ),
            "contract_sha256": _sha256_file(project_root / CONTRACT_REL),
            "graph_sha256": _sha256_file(staging / "graph_input.json"),
            "source_config_sha256": _sha256_file(staging / "source_config.json"),
            "pipeline_tree_sha256": comparison["tree_sha256"],
            "package_release": None,
        }
        (staging / "bundle_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        output_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, output_root)
    return _load_json(output_root / "validation_report.json")


__all__ = [
    "CLAIM",
    "MaxPoolConfigOnlyE2Error",
    "generate_maxpool_config_only_e2",
    "materialized_leaf_diff",
    "validate_maxpool_config_only_e2",
]
