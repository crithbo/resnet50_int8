"""Materialize and validate the minimal native two-stage lifecycle probe.

The probe is intentionally synthetic and local-only.  It closes generic
producer-D -> consumer-A storage, config reload, barrier and termination
semantics without claiming a ResNet50 target configuration or RTL execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hardware_simulation_frontend import (
    BankedMemory,
    PhysicalAddress,
    StageInvocation,
    load_payload_bytes,
    prepare_hardware_simulation,
    run_prepared_simulation,
)
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


ASSET_VERSION = "v1"
SCHEMA = "minimal-two-stage-lifecycle-local-e2-v1"
STAGE0_ID = "op0"
STAGE1_ID = "op1"
STAGE0_TYPE = "prefill_mul_fp32MN_fp32M_fp32MN"
STAGE1_TYPE = "prefill_add_fp32MN_fp32MN_fp32MN"
SLICE_MASK = "0b0000000000000000000000000001"
SHAPE = (1, 8, 32)
STAGE0_B_SHAPE = (1, 1, 32)
BYTE_COUNT = int(np.prod(SHAPE, dtype=np.int64)) * 4
RULE_IDS = (
    "CDA-TWO-STAGE-MATERIALIZED-ROUNDTRIP-001",
    "CDA-TWO-STAGE-DATA-ALIAS-001",
    "CDA-TWO-STAGE-CONFIG-RELOAD-001",
    "CDA-TWO-STAGE-BARRIER-ORDER-001",
    "CDA-TWO-STAGE-TERMINATION-001",
    "CDA-TWO-STAGE-DUAL-GOLDEN-001",
)

_EXPECTED_SOURCE_HASHES = {
    ".agents/agent.md": (
        "367f4f4260246d40531d83cc6d24fe94946cb05bce6fbef18c428f05b634c083"
    ),
    ".agents/rules/生成前必读索引.md": (
        "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7"
    ),
    ".agents/rules/算子配置规则.md": (
        "a5fbe2f0fa2e26d8cd4ebfe8772d5a3c69516d6918cfaa5087198706a352427b"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "7f446adb1719658ce75c2614c6d619fc2c7cdcabf5e4fd34945482645539158f"
    ),
    ".agents/rules/最小双Stage生命周期规则.md": (
        "821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171"
    ),
    "ndp-sim-ref/jsons/prefill_mul_fp32MN_fp32M_fp32MN.json": (
        "db66d5e8da6146eb743fe1006a6248daf040ba937d713a99f961c591325a272f"
    ),
    "ndp-sim-ref/jsons/prefill_add_fp32MN_fp32MN_fp32MN.json": (
        "d78e184c92f3f88875f8ef6caea13d88e8e35f514226e893bb6078ed2f4e4a85"
    ),
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/json_loader.py": (
        "a3ac009d0f452c610bfb97f2562eaaf60cb0c4981ace7f337372ce5178b92dee"
    ),
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/address_planner.py": (
        "2208ffa925c509d2479e2763f323551a36e1b6c1680a112e7519f6356a312ea0"
    ),
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/control_registers.py": (
        "5fe1c5f363a0ff57c1db26281d75a0cc365a260395f2130155fb6ccdc4fcb8dd"
    ),
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/instruction_generator.py": (
        "cdc7d4dcdf41ec79571d53a909a2b2d8f1ab7897a404969b5cf49d416fc85315"
    ),
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/output_writer.py": (
        "383f39f2e61900d1e4dddcffa90faff80bc315266f77350c597b8eecc60a23aa"
    ),
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/pipeline.py": (
        "a4905e18eb3e843b58d4049096971288087bfedf2c2cc58f038bb14e2a9b28b5"
    ),
    "ndp-sim-ref/model_execplan/src/execution_plan_generator/server_profile.py": (
        "986d5173ab132dec2426094f70dce3430c644f68db956bc4e6d5772c379a7076"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
    ),
}


class MinimalTwoStageLifecycleError(ValueError):
    pass


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise MinimalTwoStageLifecycleError(f"cannot parse JSON: {path}") from error
    if not isinstance(value, dict):
        raise MinimalTwoStageLifecycleError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _tree_identity(path: Path) -> dict[str, Any]:
    entries = [
        {
            "path": item.relative_to(path).as_posix(),
            "sha256": sha256_file(item),
        }
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    ]
    return {
        "file_count": len(entries),
        "tree_sha256": sha256_bytes(canonical_json_bytes(entries)),
    }


def build_generation_receipt(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    observed: dict[str, str] = {}
    for relative, expected in _EXPECTED_SOURCE_HASHES.items():
        path = root / relative
        if not path.is_file():
            raise MinimalTwoStageLifecycleError(
                f"generation-read input is missing: {relative}"
            )
        observed_hash = sha256_file(path)
        if observed_hash != expected:
            raise MinimalTwoStageLifecycleError(
                "generation-read input identity drifted; reread and refresh receipt: "
                f"{relative}"
            )
        observed[relative] = observed_hash
    read_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    receipt: dict[str, Any] = {
        "schema": "minimal-two-stage-generation-read-receipt-v1",
        "status": "generation_gate_satisfied_before_materialization",
        "read_at": read_at,
        "rule_ids": list(RULE_IDS),
        "sources": [
            {
                "path": relative,
                "sha256": observed[relative],
                "read_at": read_at,
            }
            for relative in _EXPECTED_SOURCE_HASHES
        ],
        "triggered_hardware_sections": [
            "LC",
            "MSE",
            "Buffer",
            "GA",
            "execplan",
            "completion observer",
        ],
        "scope": {
            "candidate_release": False,
            "formal_target_config": False,
            "server_package": False,
            "rtl_modification_allowed": False,
        },
    }
    receipt["receipt_sha256"] = sha256_bytes(canonical_json_bytes(receipt))
    return receipt


def build_typed_request() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "plan_id": "minimal-two-stage-lifecycle-v1",
        "used_slices": SLICE_MASK,
        "operators": [
            {
                "id": STAGE0_ID,
                "type": STAGE0_TYPE,
                "instance_id": "lifecycle:stage0:mul",
                "stage": "producer",
                "used_slices": SLICE_MASK,
                "attributes": {
                    "stage_index": 0,
                    "formula": "D0=fp32(A0*B0)",
                    "candidate_release": False,
                },
                "inputs": {
                    "A": {
                        "shape": list(SHAPE),
                        "dtype": "fp32",
                        "tensor_id": "lifecycle.A0",
                        "source": {"type": "external"},
                    },
                    "B": {
                        "shape": list(STAGE0_B_SHAPE),
                        "dtype": "fp32",
                        "tensor_id": "lifecycle.B0",
                        "source": {"type": "external"},
                    },
                },
                "output": {
                    "shape": list(SHAPE),
                    "dtype": "fp32",
                    "tensor_id": "lifecycle.D0",
                },
            },
            {
                "id": STAGE1_ID,
                "type": STAGE1_TYPE,
                "instance_id": "lifecycle:stage1:add",
                "stage": "consumer",
                "used_slices": SLICE_MASK,
                "attributes": {
                    "stage_index": 1,
                    "formula": "D1=fp32(D0+B1)",
                    "candidate_release": False,
                },
                "inputs": {
                    "A": {
                        "shape": list(SHAPE),
                        "dtype": "fp32",
                        "tensor_id": "lifecycle.D0",
                        "source": {
                            "type": "operator",
                            "operator_id": STAGE0_ID,
                        },
                    },
                    "B": {
                        "shape": list(SHAPE),
                        "dtype": "fp32",
                        "tensor_id": "lifecycle.B1",
                        "source": {"type": "external"},
                    },
                },
                "output": {
                    "shape": list(SHAPE),
                    "dtype": "fp32",
                    "tensor_id": "lifecycle.D1",
                },
            },
        ],
    }


def _deterministic_tensors() -> dict[str, np.ndarray]:
    indices = np.arange(np.prod(SHAPE), dtype=np.int32).reshape(SHAPE)
    a0 = ((indices % 17) - 8).astype(np.float32)
    b0 = np.asarray(
        [0.5, 1.0, 2.0, 4.0] * 8,
        dtype=np.float32,
    ).reshape(STAGE0_B_SHAPE)
    b1 = ((indices % 9) - 4).astype(np.float32)
    d0 = np.multiply(a0, b0, dtype=np.float32)
    d1 = np.add(d0, b1, dtype=np.float32)
    if not all(np.isfinite(value).all() for value in (a0, b0, b1, d0, d1)):
        raise AssertionError("deterministic lifecycle tensors must be finite")
    return {"A0": a0, "B0": b0, "B1": b1, "D0": d0, "D1": d1}


def _copy_isolated_toolchain(project_root: Path, destination: Path) -> None:
    source = project_root / "ndp-sim-ref"
    destination.mkdir(parents=True)
    for relative in ("bitstream", "model_execplan", "jsons"):
        shutil.copytree(source / relative, destination / relative)

    mapper_path = destination / "bitstream/config/mapper.py"
    pipeline_path = (
        destination
        / "model_execplan/src/execution_plan_generator/pipeline.py"
    )
    if sha256_file(mapper_path) != (
        "8e2504d3262bd47ce13b9d75c8bebe58a6900bdf9af03360bf563d653dd88641"
    ):
        raise MinimalTwoStageLifecycleError("isolated mapper preimage differs")
    if sha256_file(pipeline_path) != _EXPECTED_SOURCE_HASHES[
        "ndp-sim-ref/model_execplan/src/execution_plan_generator/pipeline.py"
    ]:
        raise MinimalTwoStageLifecycleError("isolated pipeline preimage differs")

    mapper_text = mapper_path.read_text(encoding="utf-8")
    import_block = (
        "import matplotlib\n"
        "matplotlib.use(\"Agg\")\n"
        "import matplotlib.pyplot as plt\n"
        "from matplotlib.patches import FancyArrowPatch\n"
        "from matplotlib.path import Path\n"
    )
    if mapper_text.count(import_block) != 1:
        raise MinimalTwoStageLifecycleError("isolated mapper headless anchor differs")
    mapper_path.write_text(
        mapper_text.replace(
            import_block,
            "# Local E2 headless adapter; visualization imports stay inside "
            "visualize_mapping.\n",
        ),
        encoding="utf-8",
    )

    pipeline_text = pipeline_path.read_text(encoding="utf-8")
    visualize_line = '                "--visualize-placement",\n'
    seed_anchor = (
        '                "-o", str(op_config_dir),\n'
        '                "-q",\n'
    )
    if pipeline_text.count(visualize_line) != 1 or pipeline_text.count(seed_anchor) != 1:
        raise MinimalTwoStageLifecycleError("isolated pipeline patch anchor differs")
    pipeline_text = pipeline_text.replace(visualize_line, "")
    pipeline_text = pipeline_text.replace(
        seed_anchor,
        (
            '                "-o", str(op_config_dir),\n'
            '                "--seed", "77",\n'
            '                "-q",\n'
        ),
    )
    pipeline_path.write_text(pipeline_text, encoding="utf-8")

    _write_json(
        destination / "isolated_patch_manifest.json",
        {
            "schema": "minimal-two-stage-isolated-toolchain-patch-v1",
            "active_source_modified": False,
            "functional_semantics_changed": False,
            "patches": [
                {
                    "path": "bitstream/config/mapper.py",
                    "reason": "headless_import_only",
                    "post_sha256": sha256_file(mapper_path),
                },
                {
                    "path": (
                        "model_execplan/src/execution_plan_generator/pipeline.py"
                    ),
                    "reason": "headless_output_and_deterministic_mapping_seed_77",
                    "post_sha256": sha256_file(pipeline_path),
                },
            ],
        },
    )


def _run(command: list[str], *, cwd: Path, env: Mapping[str, str]) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=str(cwd),
        env=dict(env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise MinimalTwoStageLifecycleError(
            f"native lifecycle command failed ({process.returncode}):\n"
            f"{process.stdout}\n{process.stderr}"
        )
    return {
        "returncode": process.returncode,
        "native_cli_completed": True,
    }


def _execplan_words(path: Path) -> list[int]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="ascii").splitlines()
        if line.strip()
    ]
    if not lines or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise MinimalTwoStageLifecycleError("native execplan is not strict 128-bit text")
    words: list[int] = []
    for line in lines:
        words.extend((int(line[64:], 2), int(line[:64], 2)))
    if words and words[-1] == 0:
        words.pop()
    return words


def _execplan_explanations(path: Path, count: int) -> list[str]:
    pattern = re.compile(r"^\s*(\d+)\s+<([01]{64})>(?:\s{4}(.*))?$")
    records: dict[int, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw)
        if match is None:
            continue
        records[int(match.group(1))] = match.group(3) or ""
    if set(records) != set(range(count)):
        raise MinimalTwoStageLifecycleError(
            "native execplan explanation coverage differs"
        )
    return [records[index] for index in range(count)]


def _barrierize_native_outputs(
    isolated: Path, request_path: Path, lifecycle_root: Path
) -> dict[str, Any]:
    execplan_path = lifecycle_root / "install/execplan.txt"
    explanation_path = lifecycle_root / "instructions_explained.txt"
    commands = _execplan_words(execplan_path)
    explanations = _execplan_explanations(explanation_path, len(commands))
    source_root = isolated / "model_execplan/src"
    module_prefix = "execution_plan_generator"
    prior_path = list(sys.path)
    prior_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == module_prefix or name.startswith(f"{module_prefix}.")
    }
    for name in prior_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(source_root))
    try:
        from execution_plan_generator.json_loader import (  # type: ignore[import-not-found]
            load_execution_plan_json,
        )
        from execution_plan_generator.models import (  # type: ignore[import-not-found]
            ExecutionPlanArtifact,
        )
        from execution_plan_generator.output_writer import (  # type: ignore[import-not-found]
            write_instruction_outputs,
        )
        from execution_plan_generator.server_profile import (  # type: ignore[import-not-found]
            insert_server_completion_barriers,
        )

        execution_input = load_execution_plan_json(request_path)
        ordinary = ExecutionPlanArtifact(
            commands=commands,
            command_explanations=explanations,
            metadata={"profile": "ordinary_native_before_local_barriers"},
        )
        barrierized = insert_server_completion_barriers(
            ordinary, execution_input.operators
        )
        write_instruction_outputs(barrierized, lifecycle_root)
    finally:
        for name in list(sys.modules):
            if name == module_prefix or name.startswith(f"{module_prefix}."):
                sys.modules.pop(name, None)
        sys.modules.update(prior_modules)
        sys.path[:] = prior_path

    sca_path = lifecycle_root / "sca_cfg.json"
    sca = _json_object(sca_path)
    barrierized_words = _execplan_words(execplan_path)
    sca["Exec_Length"] = (len(barrierized_words) + 1) // 2
    sca["Repeat_Num"] = 2
    _write_json(sca_path, sca)
    opcodes = [word & 0x7 for word in barrierized_words]
    if (
        opcodes.count(0b101) != 2
        or opcodes.count(0b110) != 2
        or opcodes[-1] != 0b110
    ):
        raise MinimalTwoStageLifecycleError(
            "native server barrier insertion did not produce two terminal fences"
        )
    return {
        "ordinary_command_count": len(commands),
        "barrierized_command_count": len(barrierized_words),
        "start_comp_count": opcodes.count(0b101),
        "barrier_count": opcodes.count(0b110),
        "final_opcode": "0b110",
        "helper": (
            "ndp-sim-ref.model_execplan.execution_plan_generator."
            "server_profile.insert_server_completion_barriers"
        ),
    }


def _native_required_paths(lifecycle_root: Path, isolated: Path) -> dict[str, Path]:
    config_root = lifecycle_root / "config"
    return {
        "normalized_request": lifecycle_root.parent.parent / "normalized_request.json",
        "addressed_request": lifecycle_root / "two_stage_withbaseaddr.json",
        "execplan": lifecycle_root / "install/execplan.txt",
        "explanation": lifecycle_root / "instructions_explained.txt",
        "sca": lifecycle_root / "sca_cfg.json",
        "sca_d": lifecycle_root / "sca_cfg_D.json",
        "stage0_json": lifecycle_root / "jsons" / f"{STAGE0_ID}_{STAGE0_TYPE}.json",
        "stage1_json": lifecycle_root / "jsons" / f"{STAGE1_ID}_{STAGE1_TYPE}.json",
        "stage0_mapping": config_root / STAGE0_ID / "mapping_review.json",
        "stage1_mapping": config_root / STAGE1_ID / "mapping_review.json",
        "stage0_bitstream": (
            config_root
            / STAGE0_ID
            / f"{STAGE0_ID}_{STAGE0_TYPE}_bitstream_128b.bin"
        ),
        "stage1_bitstream": (
            config_root
            / STAGE1_ID
            / f"{STAGE1_ID}_{STAGE1_TYPE}_bitstream_128b.bin"
        ),
        "stage0_cfg_pkg": (
            lifecycle_root
            / "install/cfg_pkg"
            / f"{STAGE0_ID}_{STAGE0_TYPE}_bitstream_128b.bin"
        ),
        "stage1_cfg_pkg": (
            lifecycle_root
            / "install/cfg_pkg"
            / f"{STAGE1_ID}_{STAGE1_TYPE}_bitstream_128b.bin"
        ),
        "patch_manifest": isolated / "isolated_patch_manifest.json",
    }


def _run_native_once(
    project_root: Path,
    run_root: Path,
    request: Mapping[str, Any],
    *,
    python_executable: Path,
) -> tuple[dict[str, Path], dict[str, Any]]:
    isolated = run_root / "tool"
    _copy_isolated_toolchain(project_root, isolated)
    request_path = isolated / "model_execplan/two_stage.json"
    _write_json(request_path, request)
    normalized_path = run_root / "normalized_request.json"
    cache_dir = run_root / "mapping-cache"
    cache_dir.mkdir()
    run_record = _run(
        [
            str(python_executable),
            str(isolated / "model_execplan/main.py"),
            str(request_path),
            "--dump-normalized-json",
            str(normalized_path),
        ],
        cwd=isolated,
        env={
            **os.environ,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
            "NDP_MAPPING_CACHE_DIR": str(cache_dir),
        },
    )
    lifecycle_root = isolated / "model_execplan/output/two_stage"
    barrier = _barrierize_native_outputs(isolated, request_path, lifecycle_root)
    required = _native_required_paths(lifecycle_root, isolated)
    required["normalized_request"] = normalized_path
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise MinimalTwoStageLifecycleError(
            f"native lifecycle outputs are missing: {missing}"
        )
    for stage_index in (0, 1):
        if sha256_file(required[f"stage{stage_index}_bitstream"]) != sha256_file(
            required[f"stage{stage_index}_cfg_pkg"]
        ):
            raise MinimalTwoStageLifecycleError(
                f"stage{stage_index} regenerated bitstream/cfg_pkg identity differs"
            )
    return required, {
        "run": run_record,
        "barrier": barrier,
        "cache_initial_file_count": 0,
        "cache_final_file_count": len(list(cache_dir.iterdir())),
    }


def _parse_base_addr(value: object) -> int:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        raise MinimalTwoStageLifecycleError(f"base_addr is missing: {value!r}")
    text = value.replace("_", "")
    try:
        return int(text, 0)
    except ValueError as error:
        raise MinimalTwoStageLifecycleError(
            f"base_addr is malformed: {value!r}"
        ) from error


def _addressed_operator(
    addressed: Mapping[str, Any], operator_id: str
) -> Mapping[str, Any]:
    operators = addressed.get("operators")
    if not isinstance(operators, list):
        raise MinimalTwoStageLifecycleError("addressed operators are missing")
    matches = [
        value
        for value in operators
        if isinstance(value, Mapping) and value.get("id") == operator_id
    ]
    if len(matches) != 1:
        raise MinimalTwoStageLifecycleError(
            f"addressed operator cardinality differs: {operator_id}"
        )
    return matches[0]


def _materialized_roundtrip(required: Mapping[str, Path]) -> dict[str, Any]:
    addressed = _json_object(required["addressed_request"])
    native_sca = _json_object(required["sca"])
    native_sca_d = _json_object(required["sca_d"])
    config_audits: list[dict[str, Any]] = []
    for operator_id, operator_type in (
        (STAGE0_ID, STAGE0_TYPE),
        (STAGE1_ID, STAGE1_TYPE),
    ):
        operator = _addressed_operator(addressed, operator_id)
        config = _json_object(required[f"stage{operator_id[-1]}_json"])
        streams = config.get("stream_engine")
        if not isinstance(streams, Mapping):
            raise MinimalTwoStageLifecycleError(
                f"materialized stream engine is missing: {operator_id}"
            )
        by_target = {
            value.get("target"): value
            for value in streams.values()
            if isinstance(value, Mapping)
        }
        if set(by_target) != {"A", "B", "D"}:
            raise MinimalTwoStageLifecycleError(
                f"materialized stream target set differs: {operator_id}"
            )
        if (
            by_target["A"].get("mode") != "read"
            or by_target["B"].get("mode") != "read"
            or by_target["D"].get("mode") != "write"
        ):
            raise MinimalTwoStageLifecycleError(
                f"materialized stream direction differs: {operator_id}"
            )
        inputs = operator.get("inputs")
        output = operator.get("output")
        if not isinstance(inputs, Mapping) or not isinstance(output, Mapping):
            raise MinimalTwoStageLifecycleError(
                f"addressed operator ports are missing: {operator_id}"
            )
        expected_addresses = {
            "A": _parse_base_addr(inputs["A"]["base_addr"]),
            "B": _parse_base_addr(inputs["B"]["base_addr"]),
            "D": _parse_base_addr(output["base_addr"]),
        }
        observed_addresses = {
            target: _parse_base_addr(by_target[target].get("base_addr"))
            for target in ("A", "B", "D")
        }
        if observed_addresses != expected_addresses:
            raise MinimalTwoStageLifecycleError(
                f"materialized stream addresses differ: {operator_id}"
            )
        pe_array = config.get("general_array", {}).get("PE_array", {})
        if not isinstance(pe_array, Mapping) or not pe_array:
            raise MinimalTwoStageLifecycleError(
                f"materialized GA PE array is missing: {operator_id}"
            )
        expected_opcode = "mul" if operator_id == STAGE0_ID else "add"
        opcodes = {
            value.get("alu_opcode")
            for value in pe_array.values()
            if isinstance(value, Mapping)
        }
        if opcodes != {expected_opcode}:
            raise MinimalTwoStageLifecycleError(
                f"materialized GA opcode differs: {operator_id}"
            )
        sca_d_key = f"{operator_id}_matrixD_slice0"
        if _parse_base_addr(native_sca_d[sca_d_key]["base_addr"]) != expected_addresses["D"]:
            raise MinimalTwoStageLifecycleError(
                f"materialized SCA_D address differs: {operator_id}"
            )
        config_audits.append(
            {
                "operator_id": operator_id,
                "operator_type": operator_type,
                "config_sha256": sha256_file(
                    required[f"stage{operator_id[-1]}_json"]
                ),
                "mapping_sha256": sha256_file(
                    required[f"stage{operator_id[-1]}_mapping"]
                ),
                "bitstream_sha256": sha256_file(
                    required[f"stage{operator_id[-1]}_bitstream"]
                ),
                "ga_opcode": expected_opcode,
                "stream_addresses": {
                    key: f"0x{value:08X}"
                    for key, value in expected_addresses.items()
                },
            }
        )
    producer = _addressed_operator(addressed, STAGE0_ID)
    consumer = _addressed_operator(addressed, STAGE1_ID)
    producer_address = _parse_base_addr(producer["output"]["base_addr"])
    consumer_address = _parse_base_addr(consumer["inputs"]["A"]["base_addr"])
    if producer_address != consumer_address:
        raise MinimalTwoStageLifecycleError(
            "materialized producer D / consumer A address differs"
        )
    if f"{STAGE1_ID}_matrixA_slice0" not in native_sca:
        raise MinimalTwoStageLifecycleError(
            "expected native producer-backed input SCA evidence is missing"
        )
    return {
        "valid": True,
        "operators": config_audits,
        "producer_d_consumer_a_address": f"0x{producer_address:08X}",
        "producer_d_consumer_a_alias": True,
        "native_writer_emits_producer_backed_input_preload": True,
        "runtime_sca_must_filter_key": f"{STAGE1_ID}_matrixA_slice0",
    }


def _copy_native_evidence(
    required: Mapping[str, Path], destination: Path
) -> dict[str, dict[str, Any]]:
    paths = {
        "normalized_request.json": required["normalized_request"],
        "addressed_request.json": required["addressed_request"],
        "execplan.txt": required["execplan"],
        "instructions_explained.txt": required["explanation"],
        "native_sca_cfg.json": required["sca"],
        "native_sca_cfg_D.json": required["sca_d"],
        "stage0_config.json": required["stage0_json"],
        "stage1_config.json": required["stage1_json"],
        "stage0_mapping_review.json": required["stage0_mapping"],
        "stage1_mapping_review.json": required["stage1_mapping"],
        "stage0_bitstream_128b.bin": required["stage0_bitstream"],
        "stage1_bitstream_128b.bin": required["stage1_bitstream"],
        "isolated_patch_manifest.json": required["patch_manifest"],
    }
    destination.mkdir(parents=True)
    records: dict[str, dict[str, Any]] = {}
    for name, source in paths.items():
        target = destination / name
        shutil.copyfile(source, target)
        records[name] = {
            "sha256": sha256_file(target),
            "size_bytes": target.stat().st_size,
        }
    return records


def _place_payload(
    images: dict[tuple[int, int], bytearray], address: int, payload: bytes
) -> None:
    decoded = PhysicalAddress.decode(address)
    key = (decoded.slice_id, decoded.bank_id)
    image = images.setdefault(key, bytearray())
    padded = payload + b"\x00" * ((16 - len(payload) % 16) % 16)
    end = decoded.bank_offset + len(padded)
    if end > len(image):
        image.extend(b"\x00" * (end - len(image)))
    existing = bytes(image[decoded.bank_offset:end])
    if any(existing) and existing != padded:
        raise MinimalTwoStageLifecycleError(
            f"local package payload overlap differs at 0x{address:08X}"
        )
    image[decoded.bank_offset:end] = padded


def _build_local_package(
    artifact_root: Path,
    required: Mapping[str, Path],
    tensors: Mapping[str, np.ndarray],
    *,
    receipt: Mapping[str, Any],
) -> Path:
    package = artifact_root / "local_package"
    (package / "install/data").mkdir(parents=True)
    (package / "install/cfg_pkg").mkdir(parents=True)
    (package / "install").mkdir(exist_ok=True)
    (package / "golden").mkdir()
    (package / "Bank_data").mkdir()

    addressed_target = package / "addressed_request.json"
    shutil.copyfile(required["addressed_request"], addressed_target)
    addressed = _json_object(addressed_target)
    native_sca = _json_object(required["sca"])
    native_sca_d = _json_object(required["sca_d"])

    tensor_paths = {
        "A0": package / "install/data/op0_A.bin",
        "B0": package / "install/data/op0_B.bin",
        "B1": package / "install/data/op1_B.bin",
        "D0": package / "golden/op0_D.bin",
        "D1": package / "golden/op1_D.bin",
    }
    for name, path in tensor_paths.items():
        path.write_bytes(np.ascontiguousarray(tensors[name]).tobytes(order="C"))

    config_targets = {
        STAGE0_ID: (
            package
            / "install/cfg_pkg"
            / f"{STAGE0_ID}_{STAGE0_TYPE}_bitstream_128b.bin"
        ),
        STAGE1_ID: (
            package
            / "install/cfg_pkg"
            / f"{STAGE1_ID}_{STAGE1_TYPE}_bitstream_128b.bin"
        ),
    }
    shutil.copyfile(required["stage0_cfg_pkg"], config_targets[STAGE0_ID])
    shutil.copyfile(required["stage1_cfg_pkg"], config_targets[STAGE1_ID])
    exec_target = package / "install/execplan.txt"
    shutil.copyfile(required["execplan"], exec_target)

    runtime_sca: dict[str, Any] = {
        "Exec_Base": native_sca["Exec_Base"],
        "Exec_Length": native_sca["Exec_Length"],
        "Repeat_Num": 2,
        "ExecutionPlan": {
            "base_addr": native_sca["ExecutionPlan"]["base_addr"],
            "path": "install/execplan.txt",
        },
    }
    external_entries = {
        f"{STAGE0_ID}_matrixA_slice0": "install/data/op0_A.bin",
        f"{STAGE0_ID}_matrixB_slice0": "install/data/op0_B.bin",
        f"{STAGE1_ID}_matrixB_slice0": "install/data/op1_B.bin",
    }
    for key, path in external_entries.items():
        runtime_sca[key] = {
            "base_addr": native_sca[key]["base_addr"],
            "path": path,
        }
    for operator_id in (STAGE0_ID, STAGE1_ID):
        key = f"{operator_id}_config"
        runtime_sca[key] = {
            "base_addr": native_sca[key]["base_addr"],
            "path": (
                "install/cfg_pkg/"
                f"{operator_id}_{STAGE0_TYPE if operator_id == STAGE0_ID else STAGE1_TYPE}"
                "_bitstream_128b.bin"
            ),
        }
    _write_json(package / "sca_cfg.json", runtime_sca)

    runtime_sca_d: dict[str, Any] = {}
    for operator_id, golden_name in ((STAGE0_ID, "op0_D.bin"), (STAGE1_ID, "op1_D.bin")):
        key = f"{operator_id}_matrixD_slice0"
        runtime_sca_d[key] = {
            "base_addr": native_sca_d[key]["base_addr"],
            "length": BYTE_COUNT // 16,
            "path": f"golden/{golden_name}",
        }
    _write_json(package / "sca_cfg_D.json", runtime_sca_d)

    producer = _addressed_operator(addressed, STAGE0_ID)
    consumer = _addressed_operator(addressed, STAGE1_ID)
    producer_address = _parse_base_addr(producer["output"]["base_addr"])
    consumer_address = _parse_base_addr(consumer["inputs"]["A"]["base_addr"])
    output_addresses = {
        STAGE0_ID: producer_address,
        STAGE1_ID: _parse_base_addr(consumer["output"]["base_addr"]),
    }
    lifecycle: dict[str, Any] = {
        "strategy": "producer_output_alias_to_consumer_input_v1",
        "stage_count": 2,
        "rule_ids": list(RULE_IDS),
        "addressed_request": {
            "path": "addressed_request.json",
            "sha256": sha256_file(addressed_target),
        },
        "dependencies": [
            {
                "tensor_id": "lifecycle.D0",
                "producer_operator_id": STAGE0_ID,
                "producer_port": "D",
                "consumer_operator_id": STAGE1_ID,
                "consumer_port": "A",
                "dtype": "fp32",
                "shape": list(SHAPE),
                "byte_count": BYTE_COUNT,
                "producer_base_addr": f"0x{producer_address:08X}",
                "consumer_base_addr": f"0x{consumer_address:08X}",
                "producer_sca_d_key": f"{STAGE0_ID}_matrixD_slice0",
                "consumer_preload_sca_key": f"{STAGE1_ID}_matrixA_slice0",
                "visibility_fence": "post_start_same_mask_barrier",
            }
        ],
        "config_reload": {
            "required_each_stage": True,
            "distinct_main_config_address": True,
            "distinct_main_config_payload": True,
        },
        "termination": {
            "start_comp_count": 2,
            "completion_barrier_count": 2,
            "repeat_num": 2,
            "completion_operator_ids": [STAGE0_ID, STAGE1_ID],
            "final_barrier_required": True,
        },
        "outputs": [
            {
                "operator_id": operator_id,
                "dtype": "fp32",
                "shape": list(SHAPE),
                "byte_count": BYTE_COUNT,
                "base_addr": f"0x{output_addresses[operator_id]:08X}",
                "sca_d_key": f"{operator_id}_matrixD_slice0",
                "golden_path": f"golden/{operator_id}_D.bin",
                "golden_sha256": sha256_file(
                    tensor_paths["D0" if operator_id == STAGE0_ID else "D1"]
                ),
            }
            for operator_id in (STAGE0_ID, STAGE1_ID)
        ],
    }
    runner = {
        "schema_version": "minimal-two-stage-local-runner-v1",
        "execution": {
            "exec_base": runtime_sca["Exec_Base"],
            "exec_length_128bit_beats": runtime_sca["Exec_Length"],
            "execplan_path": "install/execplan.txt",
            "completion_gate": {
                "expected_runtime_stage_count": 2,
                "expected_testbench_repeat_num": 2,
                "expected_start_comp_count": 2,
                "expected_completion_barrier_count": 2,
                "completion_barrier_opcode": "0b110",
                "expected_runtime_sequence": [STAGE0_ID, STAGE1_ID],
                "final_barrier_required": True,
            },
        },
    }
    _write_json(package / "runner_contract.json", runner)

    images: dict[tuple[int, int], bytearray] = {}
    for value in runtime_sca.values():
        if not isinstance(value, Mapping) or not isinstance(value.get("path"), str):
            continue
        payload = load_payload_bytes(package / str(value["path"]))
        _place_payload(images, _parse_base_addr(value["base_addr"]), payload)
    for (slice_id, bank_id), image in sorted(images.items()):
        (package / "Bank_data" / f"slice{slice_id:02d}_Bank{bank_id:02d}_data.bin").write_bytes(
            image
        )

    tracked = sorted(
        path
        for path in package.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    manifest: dict[str, Any] = {
        "schema_version": "minimal-two-stage-local-package-v1",
        "status": "local_e2_transport_package_not_server_package",
        "candidate_release": False,
        "formal_target_config": False,
        "server_package": False,
        "generation_receipt_sha256": receipt["receipt_sha256"],
        "runtime_sequence": [STAGE0_ID, STAGE1_ID],
        "runtime_serialization": {
            "strategy": "post_start_same_mask_barrier",
            "barrier_opcode": "0b110",
            "barrier_count": 2,
        },
        "runtime_operators": [
            {
                "operator_id": STAGE0_ID,
                "operator_type": STAGE0_TYPE,
                "stage": "producer",
                "instance_id": "lifecycle:stage0:mul",
                "slice_mask": "0x0000001",
                "attributes": {"stage_index": 0},
            },
            {
                "operator_id": STAGE1_ID,
                "operator_type": STAGE1_TYPE,
                "stage": "consumer",
                "instance_id": "lifecycle:stage1:add",
                "slice_mask": "0x0000001",
                "attributes": {"stage_index": 1},
            },
        ],
        "runtime_lifecycle": lifecycle,
        "files": [
            {
                "path": path.relative_to(package).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in tracked
        ],
    }
    _write_json(package / "manifest.json", manifest)
    return package


@dataclass
class _RecordingTwoStageExecutor:
    package_root: Path
    addressed: Mapping[str, Any]
    expected: Mapping[str, np.ndarray]
    records: list[dict[str, Any]]
    name: str = "minimal-two-stage-recording-fp32"

    def _port_address(self, operator_id: str, role: str, name: str) -> int:
        operator = _addressed_operator(self.addressed, operator_id)
        if role == "output":
            return _parse_base_addr(operator["output"]["base_addr"])
        return _parse_base_addr(operator["inputs"][name]["base_addr"])

    @staticmethod
    def _read_fp32(memory: BankedMemory, address: int, shape: tuple[int, ...]) -> np.ndarray:
        byte_count = int(np.prod(shape, dtype=np.int64)) * 4
        return np.frombuffer(memory.read(address, byte_count), dtype="<f4").reshape(shape).copy()

    def _write_and_compare(
        self,
        *,
        invocation: StageInvocation,
        memory: BankedMemory,
        value: np.ndarray,
        expected_name: str,
    ) -> None:
        address = self._port_address(invocation.stage.operator_id, "output", "D")
        payload = np.ascontiguousarray(value, dtype=np.float32).tobytes(order="C")
        memory.write(address, payload)
        expected = np.ascontiguousarray(self.expected[expected_name], dtype=np.float32)
        exact = np.array_equal(value.view(np.uint32), expected.view(np.uint32))
        if not exact:
            raise MinimalTwoStageLifecycleError(
                f"local numeric golden differs for {invocation.stage.operator_id}"
            )
        self.records.append(
            {
                "operator_id": invocation.stage.operator_id,
                "output_base_addr": f"0x{address:08X}",
                "output_sha256": hashlib.sha256(payload).hexdigest(),
                "golden_bit_exact": True,
            }
        )

    def execute_stage(self, invocation: StageInvocation, memory: BankedMemory) -> None:
        if invocation.stage.operator_id == STAGE0_ID:
            a = self._read_fp32(
                memory, self._port_address(STAGE0_ID, "input", "A"), SHAPE
            )
            b = self._read_fp32(
                memory,
                self._port_address(STAGE0_ID, "input", "B"),
                STAGE0_B_SHAPE,
            )
            self._write_and_compare(
                invocation=invocation,
                memory=memory,
                value=np.multiply(a, b, dtype=np.float32),
                expected_name="D0",
            )
            return
        if invocation.stage.operator_id == STAGE1_ID:
            producer_address = self._port_address(STAGE0_ID, "output", "D")
            consumer_address = self._port_address(STAGE1_ID, "input", "A")
            if producer_address != consumer_address or len(self.records) != 1:
                raise MinimalTwoStageLifecycleError(
                    "consumer did not observe the completed producer storage"
                )
            a = self._read_fp32(memory, consumer_address, SHAPE)
            if not np.array_equal(
                a.view(np.uint32), self.expected["D0"].view(np.uint32)
            ):
                raise MinimalTwoStageLifecycleError(
                    "consumer A does not contain the stage0 golden"
                )
            b = self._read_fp32(
                memory, self._port_address(STAGE1_ID, "input", "B"), SHAPE
            )
            self._write_and_compare(
                invocation=invocation,
                memory=memory,
                value=np.add(a, b, dtype=np.float32),
                expected_name="D1",
            )
            self.records[-1]["consumer_read_stage0_output_same_address"] = True
            return
        raise MinimalTwoStageLifecycleError(
            f"unexpected lifecycle stage: {invocation.stage.operator_id}"
        )


def _file_identity(path: Path) -> dict[str, Any]:
    return {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def build_semantic_contract(
    project_root: Path, artifact_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    output = artifact_root.resolve()
    manifest_path = output / "manifest.json"
    report_path = output / "local_e2_report.json"
    manifest = _json_object(manifest_path)
    report = _json_object(report_path)
    if (
        manifest.get("status")
        != "MINIMAL_TWO_STAGE_LIFECYCLE_LOCAL_E2_COMPLETE"
        or report.get("status")
        != "MINIMAL_TWO_STAGE_LIFECYCLE_LOCAL_E2_COMPLETE"
        or report.get("candidate_release") is not False
        or report.get("formal_target_config") is not False
        or report.get("server_package") is not False
    ):
        raise MinimalTwoStageLifecycleError(
            "minimal two-stage artifact is not a closed local E2 input"
        )
    contract: dict[str, Any] = {
        "schema": "minimal-two-stage-lifecycle-contract-v1",
        "status": "local_e2_complete_dynamic_hardware_pending",
        "candidate_release": False,
        "formal_target_config": False,
        "server_package": False,
        "rule_ids": list(RULE_IDS),
        "probe": {
            "stage0": STAGE0_TYPE,
            "stage1": STAGE1_TYPE,
            "shape": list(SHAPE),
            "dtype": "fp32",
            "slice_mask": SLICE_MASK,
        },
        "closed_local_semantics": [
            "producer D and consumer A exact physical address alias",
            "producer-backed input excluded from runtime preload",
            "independent main config load/address/payload per stage",
            "same-mask immediate barrier after each Start_Comp",
            "Repeat_Num/start/barrier/completion count equals two",
            "stage0 and stage1 bit-exact independent golden",
        ],
        "artifact": {
            "path": (
                output.relative_to(root).as_posix()
                if output.is_relative_to(root)
                else str(output)
            ),
            "manifest_sha256": sha256_file(manifest_path),
            "report_sha256": sha256_file(report_path),
        },
        "remaining_scope": (
            "full-network 133-stage physical allocation/lifetime remains open; "
            "hardware E4/E5 is not claimed"
        ),
    }
    contract["contract_sha256"] = sha256_bytes(canonical_json_bytes(contract))
    return contract


def build_artifact_manifest(artifact_root: Path) -> dict[str, Any]:
    output = artifact_root.resolve()
    report = _json_object(output / "local_e2_report.json")
    tracked = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path != output / "manifest.json"
    )
    value: dict[str, Any] = {
        "schema": "minimal-two-stage-lifecycle-artifact-manifest-v1",
        "status": report["status"],
        "candidate_release": False,
        "formal_target_config": False,
        "server_package": False,
        "files": [
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in tracked
        ],
    }
    value["manifest_sha256"] = sha256_bytes(canonical_json_bytes(value))
    return value


def run_local_e2(
    project_root: Path,
    *,
    artifact_root: Path | None = None,
    python_executable: Path | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    output = (
        artifact_root.resolve()
        if artifact_root is not None
        else root
        / "artifacts/operator_config_validation/r5-minimal-two-stage-lifecycle-e2-v1"
    )
    if output.exists():
        raise MinimalTwoStageLifecycleError(
            f"refusing to overwrite lifecycle artifact root: {output}"
        )
    python = (python_executable or Path(sys.executable)).resolve()
    receipt = build_generation_receipt(root)
    request = build_typed_request()
    tensors = _deterministic_tensors()
    rtl_root = root / "NDP_copy01/rtl"
    rtl_before = _tree_identity(rtl_root)
    source_before = {
        relative: sha256_file(root / relative)
        for relative in _EXPECTED_SOURCE_HASHES
        if relative.startswith("ndp-sim-ref/")
    }

    with tempfile.TemporaryDirectory(prefix="minimal-two-stage-e2-") as temporary:
        temp = Path(temporary)
        run_paths: dict[str, dict[str, Path]] = {}
        run_records: dict[str, dict[str, Any]] = {}
        for label in ("run-a", "run-b"):
            run_paths[label], run_records[label] = _run_native_once(
                root,
                temp / label,
                request,
                python_executable=python,
            )
        deterministic: dict[str, dict[str, Any]] = {}
        for name in run_paths["run-a"]:
            left = run_paths["run-a"][name]
            right = run_paths["run-b"][name]
            if sha256_file(left) != sha256_file(right):
                raise MinimalTwoStageLifecycleError(
                    f"two isolated native lifecycles differ: {name}"
                )
            deterministic[name] = _file_identity(left)

        roundtrip_a = _materialized_roundtrip(run_paths["run-a"])
        roundtrip_b = _materialized_roundtrip(run_paths["run-b"])
        if canonical_json_bytes(roundtrip_a) != canonical_json_bytes(roundtrip_b):
            raise MinimalTwoStageLifecycleError(
                "two isolated materialized roundtrip audits differ"
            )

        work = temp / "artifact"
        work.mkdir()
        _write_json(work / "generation_receipt.json", receipt)
        _write_json(work / "typed_request.json", request)
        native_files = _copy_native_evidence(
            run_paths["run-a"], work / "native_evidence"
        )
        package = _build_local_package(
            work, run_paths["run-a"], tensors, receipt=receipt
        )
        prepared = prepare_hardware_simulation(package)
        executor = _RecordingTwoStageExecutor(
            package_root=package,
            addressed=_json_object(package / "addressed_request.json"),
            expected=tensors,
            records=[],
        )
        memory = run_prepared_simulation(prepared, executor)
        for operator_id, expected_name in ((STAGE0_ID, "D0"), (STAGE1_ID, "D1")):
            address = executor._port_address(operator_id, "output", "D")
            observed = np.frombuffer(
                memory.read(address, BYTE_COUNT), dtype="<f4"
            ).reshape(SHAPE)
            if not np.array_equal(
                observed.view(np.uint32), tensors[expected_name].view(np.uint32)
            ):
                raise MinimalTwoStageLifecycleError(
                    f"post-run output readback differs: {operator_id}"
                )

        source_after = {
            relative: sha256_file(root / relative)
            for relative in source_before
        }
        rtl_after = _tree_identity(rtl_root)
        if source_before != source_after:
            raise MinimalTwoStageLifecycleError(
                "active ndp-sim-ref source identity changed"
            )
        if rtl_before != rtl_after:
            raise MinimalTwoStageLifecycleError(
                "NDP_copy01/rtl tree identity changed"
            )

        preparation = prepared.report()
        preparation["package_root"] = "local_package"
        for bank_image in preparation["bank_images"]:
            source_path = Path(str(bank_image["source_path"]))
            bank_image["source_path"] = source_path.relative_to(package).as_posix()
        report: dict[str, Any] = {
            "schema": SCHEMA,
            "status": "MINIMAL_TWO_STAGE_LIFECYCLE_LOCAL_E2_COMPLETE",
            "candidate_release": False,
            "formal_target_config": False,
            "server_package": False,
            "rule_ids_passed": list(RULE_IDS),
            "typed_request_sha256": sha256_file(work / "typed_request.json"),
            "generation_receipt_sha256": receipt["receipt_sha256"],
            "native_double_rebuild": {
                "isolated_toolchain_count": 2,
                "empty_mapping_cache_count": 2,
                "all_products_identical": True,
                "products": deterministic,
                "run_records": run_records,
            },
            "materialized_roundtrip": roundtrip_a,
            "runtime_sca_boundary": {
                "native_producer_backed_input_key": f"{STAGE1_ID}_matrixA_slice0",
                "native_key_retained_as_evidence": True,
                "runtime_preload_key_removed": True,
                "consumer_external_preload": False,
            },
            "transport_and_state": preparation,
            "numeric_execution": {
                "executor": executor.name,
                "stage_records": executor.records,
                "stage0_golden_bit_exact": True,
                "stage1_golden_bit_exact": True,
                "consumer_read_stage0_output_same_address": True,
            },
            "source_identity": {
                "ndp_sim_ref_unchanged": True,
                "rtl_modified": False,
                "rtl_tree_identity": rtl_after,
            },
            "native_evidence_files": native_files,
            "remaining_dynamic_boundary": [
                "RTL write visibility timing is not executed at E2",
                "real completion events are not observed at E2",
                "formal server readback is not performed",
            ],
        }
        report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
        _write_json(work / "local_e2_report.json", report)

        artifact_manifest = build_artifact_manifest(work)
        _write_json(work / "manifest.json", artifact_manifest)
        shutil.copytree(work, output)

    contract = build_semantic_contract(root, output)
    contract_path = (
        root / "contracts/operator_config/minimal_two_stage_lifecycle_v1.json"
    )
    if artifact_root is None:
        _write_json(contract_path, contract)
    return {
        "status": contract["status"],
        "artifact_root": str(output),
        "contract_path": str(contract_path) if artifact_root is None else None,
        "contract_sha256": contract["contract_sha256"],
        "report_sha256": sha256_file(output / "local_e2_report.json"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the local-only minimal two-stage lifecycle E2 probe."
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--artifact-root", type=Path)
    args = parser.parse_args(argv)
    result = run_local_e2(
        args.project_root,
        artifact_root=args.artifact_root,
        python_executable=Path(sys.executable),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ASSET_VERSION",
    "MinimalTwoStageLifecycleError",
    "RULE_IDS",
    "build_artifact_manifest",
    "build_generation_receipt",
    "build_semantic_contract",
    "build_typed_request",
    "run_local_e2",
]
