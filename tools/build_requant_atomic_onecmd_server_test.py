#!/usr/bin/env python3
"""Build the one-command stock-RTL Requant atomic FIRST_DYNAMIC package."""

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
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.requantize_uint8_vertical import (  # noqa: E402
    _build_tool_copy,
    _execplan_explanations,
    _execplan_words,
)
from tools.requant_atomic_server_runtime import (  # noqa: E402
    MANIFEST_NAME,
    preflight_package,
)


SCHEMA = "requant-node0001-atomic-two-stage-stockrtl-firstdynamic-package-v2"
INSTALL_NAME = "rq_node0001_atomic2_stock_v2"
FROZEN_INSTALL_NAME = "rq_node0001_atomic2_stock_v1"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
SOURCE_ROOT = (
    ROOT
    / "configs/native_ndp_sim/node0001_requant_single_occurrence_two_stage_v2"
)
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "requant_node0001_single_occurrence_two_stage_dynamic_v2.json"
)
LOCAL_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-requant-node0001-single-occurrence-two-stage-v2/local_contract_report.json"
)
READ_RECEIPT = (
    ROOT
    / ".agents/task_records/"
    "20260726_requant_atomic2_bootstrap_v2_package_read_receipt.json"
)
FROZEN_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / FROZEN_INSTALL_NAME
)
FROZEN_PACKAGE_ZIP_SHA256 = (
    "4f732020c598ac9e00eec5dddf4a06f84e5f0caf54fb75243d6df7e38922f54b"
)
SOURCE_IDENTITIES = {
    "manifest": (
        SOURCE_ROOT / "manifest.json",
        "c6e50200d01209147851d990e824b3eead748ecfec9fb64aaaf6cd0cd97d4097",
    ),
    "generation_receipt": (
        SOURCE_ROOT / "generation_receipt.json",
        "0046cc4ad1e19e905b24b3b78524a5c80b991c5c4699bcd329c6d9c8063f7f25",
    ),
    "guard_json": (
        SOURCE_ROOT / "guard.json",
        "defeca56b0c248eb1f4915b0338227580687d4e8c92cedf548ad727f6457d5d2",
    ),
    "round_json": (
        SOURCE_ROOT / "round_saturate.json",
        "e8e3d0f2ed67f77f8228aeb142e64b038f1f0ac4cdbc2e79f297ca4ee4be08b0",
    ),
    "typed_graph": (
        SOURCE_ROOT / "typed_graph.json",
        "0dd2d0549c02a538bd69cf48309be9bd26beefe070bf707f6266420894de3742",
    ),
    "expected_mse4_writes": (
        SOURCE_ROOT / "expected_mse4_writes.json",
        "9575f48d166defa194a9523a31c4d162f053c23f081a5866bae9fac2d8f70e1c",
    ),
    "lifecycle_contract": (
        SOURCE_ROOT / "lifecycle_contract.json",
        "c36fad83a4bf508e127563575b6fa8b1e0bb281a6f74e17103975c4b07210ca2",
    ),
    "contract": (
        CONTRACT,
        "efba2a4f00764d7f9cecef8c91888255ea5f0a1d409b94df4d277d41766cbd9b",
    ),
    "local_report": (
        LOCAL_REPORT,
        "aa1acd52995cfa22dc6cbb9f8c2682fd50782dfdc80d893673237130dddeaeb3",
    ),
    "requant_rule": (
        ROOT / ".agents/rules/RequantizeUint8算子配置规则.md",
        "f0315f627a492a660c91a95aa12d46339518863b79358280e498dc2125799cf3",
    ),
    "server_rule": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "bdddfedd8d361d745298ac36db9862638a54096eac3d7da5c77e852a3e8dfeea",
    ),
    "read_receipt": (
        READ_RECEIPT,
        "fe36a17e5cc1d9b00b5298a634bd21e4fb537d6dbda8a01da3017f091cd1df50",
    ),
}
RULE_IDS = (
    "CDA-SERVER-WORKLOAD-PROVENANCE-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SERVER-SCA-PRETTY-JSON-001",
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
    "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-REQUANT-QPARAM-001",
    "CDA-REQUANT-INT32-GUARD-001",
    "CDA-REQUANT-SFU-LUT-001",
    "CDA-REQUANT-TWO-STAGE-001",
    "CDA-REQUANT-ROUND-MAGIC-001",
    "CDA-REQUANT-ATOMIC-SINGLE-OCCURRENCE-001",
    "CDA-REQUANT-ATOMIC-STOCK-TB-MASK-COMPAT-001",
)


class AtomicPackageError(RuntimeError):
    """Raised when the deterministic atomic package cannot be built."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_json(path: Path, value: Any) -> None:
    _write_lf(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _copy_lf(source: Path, target: Path) -> None:
    _write_lf(
        target,
        source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"),
    )


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return result


def _tree_sha256(records: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(records.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return digest.hexdigest()


def _is_frozen_semantic_payload(relative: str) -> bool:
    if relative.startswith("golden/"):
        return True
    if relative.startswith("workload/runtime/payloads/"):
        return True
    if relative.startswith("validation/native/"):
        return True
    return relative in {
        "validation/coverage_contract.json",
        "validation/derivation_provenance.json",
        "validation/expected_mse4_writes.json",
        "validation/first_divergence_routing.json",
        "validation/generation_receipt.json",
        "validation/guard.json",
        "validation/instructions_explained.txt",
        "validation/lifecycle_contract.json",
        "validation/local_contract_report.json",
        "validation/manifest.json",
        "validation/native_double_rebuild.json",
        "validation/planner_id_adapter_receipt.json",
        "validation/planner_typed_graph_v2.json",
        "validation/requant_atomic_v2_withbaseaddr.json",
        "validation/round_saturate.json",
        "validation/semantic_contract.json",
        "validation/semantic_typed_graph_v2.json",
    }


def _semantic_payload_category(relative: str) -> str:
    name = Path(*relative.split("/")).name
    if relative.startswith("golden/"):
        return "golden"
    if relative == "validation/expected_mse4_writes.json":
        return "expected_writes"
    if name == "mapping_review.json":
        return "mapping_review"
    if name == "parsed_bitstream.txt":
        return "parsed_bitstream"
    if name == "bitstream_64b.bin":
        return "bitstream_64b"
    if name == "bitstream_128b.bin" or (
        relative.startswith("workload/runtime/payloads/cfg_pkg/")
        and name.endswith("_bitstream_128b.bin")
    ):
        return "bitstream_128b"
    if relative == "workload/runtime/payloads/execplan.txt":
        return "execplan"
    if name in {
        "address_bound_config.json",
        "guard.json",
        "round_saturate.json",
        "requant_atomic_v2_withbaseaddr.json",
    }:
        return "operator_json"
    if relative.startswith("workload/runtime/payloads/inputs/"):
        return "input"
    return "semantic_evidence"


def _normalize_sca_identity(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_sca_identity(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_normalize_sca_identity(item) for item in value]
    if isinstance(value, str):
        for install_name in (FROZEN_INSTALL_NAME, INSTALL_NAME):
            value = value.replace(
                f"../install/cfg_pkg/{install_name}/",
                "../install/cfg_pkg/<INSTALL_IDENTITY>/",
            )
        return value
    return value


def _semantic_freeze_receipt(package: Path) -> dict[str, Any]:
    frozen_zip = FROZEN_PACKAGE.with_suffix(".zip")
    if (
        not FROZEN_PACKAGE.is_dir()
        or not frozen_zip.is_file()
        or _sha256(frozen_zip) != FROZEN_PACKAGE_ZIP_SHA256
    ):
        raise AtomicPackageError("frozen atomic v1 package identity differs")
    frozen_records = {
        relative: item
        for relative, item in _records(FROZEN_PACKAGE).items()
        if _is_frozen_semantic_payload(relative)
    }
    rebuilt_records = {
        relative: item
        for relative, item in _records(package).items()
        if _is_frozen_semantic_payload(relative)
    }
    if frozen_records != rebuilt_records:
        differing = sorted(set(frozen_records) ^ set(rebuilt_records))
        differing.extend(
            relative
            for relative in sorted(set(frozen_records) & set(rebuilt_records))
            if frozen_records[relative] != rebuilt_records[relative]
        )
        raise AtomicPackageError(
            f"frozen semantic payload differs from atomic v1: {differing[:8]}"
        )
    categories: dict[str, int] = {}
    files: dict[str, Any] = {}
    for relative, item in sorted(rebuilt_records.items()):
        category = _semantic_payload_category(relative)
        categories[category] = categories.get(category, 0) + 1
        files[relative] = {
            "category": category,
            "v1_sha256": frozen_records[relative]["sha256"],
            "v2_sha256": item["sha256"],
            "size_bytes": item["size_bytes"],
            "byte_identical": True,
        }
    for required in (
        "operator_json",
        "mapping_review",
        "parsed_bitstream",
        "bitstream_64b",
        "bitstream_128b",
        "execplan",
        "golden",
        "expected_writes",
    ):
        if categories.get(required, 0) == 0:
            raise AtomicPackageError(
                f"frozen semantic category is empty: {required}"
            )
    sca_receipts: dict[str, Any] = {}
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        frozen_path = FROZEN_PACKAGE / "workload/runtime" / name
        rebuilt_path = package / "workload/runtime" / name
        frozen_sca = json.loads(frozen_path.read_text(encoding="utf-8"))
        rebuilt_sca = json.loads(rebuilt_path.read_text(encoding="utf-8"))
        if _normalize_sca_identity(frozen_sca) != _normalize_sca_identity(
            rebuilt_sca
        ):
            raise AtomicPackageError(
                f"SCA differs beyond the unique install identity: {name}"
            )
        sca_receipts[name] = {
            "v1_sha256": _sha256(frozen_path),
            "v2_sha256": _sha256(rebuilt_path),
            "normalized_equal": True,
            "allowed_change": "install namespace path only",
        }
    return {
        "schema": "requant-atomic2-bootstrap-semantic-freeze-v1",
        "frozen_package": FROZEN_PACKAGE.relative_to(ROOT).as_posix(),
        "frozen_zip_sha256": FROZEN_PACKAGE_ZIP_SHA256,
        "semantic_payload_file_count": len(files),
        "semantic_payload_tree_sha256": _tree_sha256(rebuilt_records),
        "categories": categories,
        "files": files,
        "sca_identity_normalization": sca_receipts,
        "semantic_payload_byte_identical": True,
        "allowed_change_scope": (
            "runtime/bootstrap and install/SCA namespace paths only"
        ),
    }


def _verify_sources() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, (path, expected) in SOURCE_IDENTITIES.items():
        if not path.is_file() or _sha256(path) != expected:
            raise AtomicPackageError(f"source identity differs: {path}")
        result[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": expected,
        }
    source_manifest = json.loads(
        (SOURCE_ROOT / "manifest.json").read_text(encoding="utf-8")
    )
    for relative, expected in source_manifest["files"].items():
        path = SOURCE_ROOT / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["size_bytes"]
            or _sha256(path) != expected["sha256"]
        ):
            raise AtomicPackageError(f"v2 config-root exact file differs: {relative}")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if (
        contract.get("active_slices") != [0, 1]
        or contract.get("stock_tb_completion_compatible") is not True
        or contract.get("counts_as_node0001_e4") is not False
        or contract.get("counts_as_node0001_e5") is not False
    ):
        raise AtomicPackageError("v2 contract claim boundary differs")
    return result


def _planner_graph() -> tuple[dict[str, Any], dict[str, Any]]:
    source = json.loads((SOURCE_ROOT / "typed_graph.json").read_text(encoding="utf-8"))
    graph = deepcopy(source)
    if [item["id"] for item in graph["operators"]] != [
        "op_atomic_guard",
        "op_atomic_round",
    ]:
        raise AtomicPackageError("v2 graph operator IDs differ")
    graph["operators"][0]["id"] = "op_w0_s00_guard"
    graph["operators"][1]["id"] = "op_w0_s00_round"
    graph["operators"][1]["inputs"]["A"]["source"][
        "operator_id"
    ] = "op_w0_s00_guard"
    receipt = {
        "schema": "requant-atomic-planner-id-adapter-v1",
        "semantic_operator_count": 2,
        "changes": [
            {
                "path": "operators[0].id",
                "before": "op_atomic_guard",
                "after": "op_w0_s00_guard",
            },
            {
                "path": "operators[1].id",
                "before": "op_atomic_round",
                "after": "op_w0_s00_round",
            },
            {
                "path": "operators[1].inputs.A.source.operator_id",
                "before": "op_atomic_guard",
                "after": "op_w0_s00_guard",
            },
        ],
        "config_json_changed": False,
        "shapes_addresses_masks_or_tensor_ids_changed": False,
        "reason": "isolated native address planner consumes the existing op_w*_s*_role ID grammar",
    }
    return graph, receipt


def _barrierize(tool_root: Path, graph_path: Path, output_dir: Path) -> dict[str, Any]:
    execplan = output_dir / "install/execplan.txt"
    explained = output_dir / "instructions_explained.txt"
    commands = _execplan_words(execplan)
    explanations = _execplan_explanations(explained, len(commands))
    if len(commands) != 10:
        raise AtomicPackageError(f"ordinary native command count differs: {len(commands)}")
    if sum((word & 0x7) == 0b101 for word in commands) != 2:
        raise AtomicPackageError("ordinary native Start_Comp count differs")
    if any((word & 0x7) == 0b110 for word in commands):
        raise AtomicPackageError("ordinary native plan already contains a barrier")
    source_root = tool_root / "model_execplan/src"
    prefix = "execution_plan_generator"
    prior_path = list(sys.path)
    prior_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == prefix or name.startswith(f"{prefix}.")
    }
    for name in prior_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(source_root))
    try:
        from execution_plan_generator.models import ExecutionPlanArtifact  # type: ignore
        from execution_plan_generator.output_writer import (  # type: ignore
            write_instruction_outputs,
        )

        barrier_commands: list[int] = []
        barrier_explanations: list[str] = []
        stage = 0
        for command, explanation in zip(commands, explanations, strict=True):
            barrier_commands.append(int(command))
            barrier_explanations.append(str(explanation))
            if (command & 0x7) != 0b101:
                continue
            mask = (command >> 3) & ((1 << 28) - 1)
            if command >> 31 or mask != 0b11:
                raise AtomicPackageError(f"Start_Comp mask differs at stage {stage}")
            barrier_commands.append((mask << 3) | 0b110)
            barrier_explanations.append(
                "Server completion barrier after "
                f"{graph_path.stem} stage {stage}: wait for "
                "slice_mask_bin=0000000000000000000000000011"
            )
            stage += 1
        if stage != 2:
            raise AtomicPackageError("barrier stage count differs")
        write_instruction_outputs(
            ExecutionPlanArtifact(
                commands=barrier_commands,
                command_explanations=barrier_explanations,
                metadata={
                    "profile": "requant_atomic_same_mask_after_each_start_v1",
                    "barrier_count": "2",
                },
            ),
            output_dir,
        )
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(f"{prefix}."):
                sys.modules.pop(name, None)
        sys.modules.update(prior_modules)
        sys.path[:] = prior_path

    sca_path = output_dir / "sca_cfg.json"
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    words = _execplan_words(execplan)
    sca["Exec_Length"] = (len(words) + 1) // 2
    sca["Repeat_Num"] = 2
    removed = {
        name: sca.pop(name)
        for name in (
            "op_w0_s00_round_matrixA_slice0",
            "op_w0_s00_round_matrixA_slice1",
        )
        if name in sca
    }
    if len(removed) != 2 or any("round_matrixA" in name for name in sca):
        raise AtomicPackageError("round external preload removal differs")
    _write_json(sca_path, sca)
    opcodes = [word & 0x7 for word in words]
    if (
        len(words) != 12
        or opcodes.count(0b101) != 2
        or opcodes.count(0b110) != 2
        or opcodes[-1] != 0b110
    ):
        raise AtomicPackageError("barrierized execplan differs")
    return {
        "ordinary_command_count": len(commands),
        "barrierized_command_count": len(words),
        "execplan_128b_line_count": (len(words) + 1) // 2,
        "start_comp_count": 2,
        "completion_barrier_count": 2,
        "repeat_num": 2,
        "slice_mask": "0b0000000000000000000000000011",
        "consumer_external_preload_removed_count": len(removed),
        "final_opcode": "0b110",
    }


def _native_once(run_dir: Path) -> dict[str, Any]:
    graph, adapter_receipt = _planner_graph()
    guard = json.loads((SOURCE_ROOT / "guard.json").read_text(encoding="utf-8"))
    round_config = json.loads(
        (SOURCE_ROOT / "round_saturate.json").read_text(encoding="utf-8")
    )
    configs: Mapping[str, Mapping[str, Any]] = {
        graph["operators"][0]["type"]: guard,
        graph["operators"][1]["type"]: round_config,
    }
    tool_root, source_manifest = _build_tool_copy(
        ROOT,
        run_dir,
        configs,
        (SOURCE_ROOT / "RequantGuard.txt").read_text(encoding="utf-8"),
    )
    input_dir = tool_root / "input"
    input_dir.mkdir()
    graph_path = input_dir / "requant_atomic_v2.json"
    _write_json(graph_path, graph)
    seed_hook = run_dir / "seed_hook"
    seed_hook.mkdir()
    _write_lf(seed_hook / "sitecustomize.py", "import random\nrandom.seed(314159)\n")
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": os.pathsep.join(
            filter(None, (str(seed_hook.resolve()), os.environ.get("PYTHONPATH")))
        ),
    }
    process = subprocess.run(
        [
            sys.executable,
            str(tool_root / "model_execplan/main.py"),
            str(graph_path),
        ],
        cwd=tool_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        check=False,
    )
    _write_lf(run_dir / "native_stdout.log", process.stdout)
    _write_lf(run_dir / "native_stderr.log", process.stderr)
    if process.returncode != 0 or "Parsed operators: 2" not in process.stdout:
        raise AtomicPackageError(
            f"isolated native planner/mapper/encoder failed: rc={process.returncode}"
        )
    output = tool_root / "model_execplan/output/requant_atomic_v2"
    if not output.is_dir():
        raise AtomicPackageError("isolated native output is missing")
    barrier = _barrierize(tool_root, graph_path, output)
    required = [
        output / "install/execplan.txt",
        output / "instructions_explained.txt",
        output / "sca_cfg.json",
        output / "sca_cfg_D.json",
        output / "requant_atomic_v2_withbaseaddr.json",
    ]
    for op_id, op_type in (
        ("op_w0_s00_guard", graph["operators"][0]["type"]),
        ("op_w0_s00_round", graph["operators"][1]["type"]),
    ):
        required.extend(
            [
                output / f"jsons/{op_id}_{op_type}.json",
                output / f"config/{op_id}/mapping_review.json",
                output / f"config/{op_id}/parsed_bitstream.txt",
                output / f"config/{op_id}/detailed_dump.txt",
                output / f"config/{op_id}/{op_id}_{op_type}_bitstream_64b.bin",
                output / f"config/{op_id}/{op_id}_{op_type}_bitstream_128b.bin",
            ]
        )
    missing = [path.as_posix() for path in required if not path.is_file()]
    if missing:
        raise AtomicPackageError(f"native output silently omitted files: {missing[:4]}")
    return {
        "run_dir": run_dir,
        "tool_root": tool_root,
        "output": output,
        "graph": graph,
        "adapter_receipt": adapter_receipt,
        "source_manifest": source_manifest,
        "barrier": barrier,
        "stdout": run_dir / "native_stdout.log",
        "stderr": run_dir / "native_stderr.log",
    }


def _native_file_map(output: Path) -> dict[str, dict[str, Any]]:
    result = _records(output)
    return {
        relative: value
        for relative, value in result.items()
        if not relative.endswith("/placement.png")
    }


def _double_native_build(temp_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    left = _native_once(temp_root / "native_a")
    right = _native_once(temp_root / "native_b")
    files_left = _native_file_map(left["output"])
    files_right = _native_file_map(right["output"])
    if files_left != files_right:
        differing = sorted(
            key
            for key in set(files_left) | set(files_right)
            if files_left.get(key) != files_right.get(key)
        )
        raise AtomicPackageError(f"fresh native rebuilds differ: {differing[:6]}")
    source_left = left["source_manifest"]["manifest_sha256"]
    source_right = right["source_manifest"]["manifest_sha256"]
    if source_left != source_right:
        raise AtomicPackageError("isolated tool source manifests differ")
    report = {
        "schema": "requant-atomic-native-double-rebuild-v1",
        "fresh_isolated_run_count": 2,
        "mapping_seed": 314159,
        "python_hash_seed": 0,
        "deterministic_file_count": len(files_left),
        "deterministic_files_byte_identical": True,
        "excluded_visualization_suffixes": ["config/*/placement.png"],
        "isolated_tool_source_manifest_sha256": source_left,
        "barrierization": left["barrier"],
        "files": files_left,
    }
    return left, report


def _rewrite_sca(source: dict[str, Any]) -> dict[str, Any]:
    sca = deepcopy(source)
    expected_keys = {
        "Exec_Base",
        "Exec_Length",
        "Repeat_Num",
        "ExecutionPlan",
        "op_w0_s00_guard_matrixA_slice0",
        "op_w0_s00_guard_matrixA_slice1",
        "op_w0_s00_guard_config",
        "op_w0_s00_guard_sfu_config",
        "op_w0_s00_round_config",
    }
    if set(sca) != expected_keys:
        raise AtomicPackageError(f"sanitized native SCA exact set differs: {sorted(sca)}")
    prefix = f"../install/cfg_pkg/{INSTALL_NAME}/payloads"
    sca["ExecutionPlan"]["path"] = f"{prefix}/execplan.txt"
    for slice_id in (0, 1):
        key = f"op_w0_s00_guard_matrixA_slice{slice_id}"
        sca[key]["path"] = (
            f"{prefix}/inputs/op_w0_s00_guard/slice{slice_id:02d}/"
            "matrix_A_linearized_128bit.txt"
        )
    for key in (
        "op_w0_s00_guard_config",
        "op_w0_s00_guard_sfu_config",
        "op_w0_s00_round_config",
    ):
        sca[key]["path"] = f"{prefix}/cfg_pkg/{Path(sca[key]['path']).name}"
    return sca


def _rewrite_sca_d(source: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "op_w0_s00_guard_matrixD_slice0": ("0x00800000", 8),
        "op_w0_s00_guard_matrixD_slice1": ("0x02800000", 8),
        "op_w0_s00_round_matrixD_slice0": ("0x01000000", 2),
        "op_w0_s00_round_matrixD_slice1": ("0x03000000", 2),
    }
    if set(source) != set(expected):
        raise AtomicPackageError("native SCA_D exact set differs")
    result: dict[str, Any] = {}
    for name, (address, length) in expected.items():
        item = source[name]
        if item.get("base_addr") != address or item.get("length") != length:
            raise AtomicPackageError(f"native SCA_D identity differs: {name}")
        result[name] = {
            "base_addr": address,
            "path": f"sim_results/formal_readback/{name}.txt",
            "length": length,
        }
    return result


def _observer_tail() -> str:
    return r"""
// ============================================================================
// Requant node0001 atomic two-stage MSE4 observer.
// Read-only: no DUT/TB driver. Enabled only by +REQUANT_ATOMIC_PROBE.
// Address and data are paired at the actual accepted MSE4 write boundary.
// The interface has no byte-strobe signal; every accepted beat is 128 bits.
// ============================================================================
    bit requant_atomic_probe_enabled;
    integer requant_atomic_probe_fd [0:1];
    integer requant_atomic_probe_stage [0:1];
    logic requant_atomic_probe_exec_d [0:1];
    logic requant_atomic_probe_finish_d [0:1];
    logic [`MSE_TSA_ADDR_WIDTH-1:0]
        requant_atomic_probe_addr_q [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    longint unsigned requant_atomic_probe_cycle;
    integer requant_atomic_probe_mkdir_status;

    initial begin : requant_atomic_probe_init
        requant_atomic_probe_enabled =
            $test$plusargs("REQUANT_ATOMIC_PROBE");
        requant_atomic_probe_cycle = 0;
        for (int sid = 0; sid < 2; sid++) begin
            requant_atomic_probe_fd[sid] = 0;
            requant_atomic_probe_stage[sid] = -1;
            requant_atomic_probe_exec_d[sid] = 1'b0;
            requant_atomic_probe_finish_d[sid] = 1'b0;
            for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                requant_atomic_probe_addr_q[sid][ch].delete();
        end
        if (requant_atomic_probe_enabled) begin
            requant_atomic_probe_mkdir_status =
                $system("mkdir -p sim_results/requant_atomic_probe");
            for (int sid = 0; sid < 2; sid++) begin
                requant_atomic_probe_fd[sid] = $fopen(
                    $sformatf(
                        "sim_results/requant_atomic_probe/slice%02d.log", sid
                    ),
                    "w"
                );
                if (requant_atomic_probe_fd[sid] == 0)
                    $error("REQUANT_ATOMIC_PROBE cannot open slice%0d log", sid);
                else begin
                    $fdisplay(
                        requant_atomic_probe_fd[sid],
                        "# Requant node0001 atomic accepted MSE4 observer v1"
                    );
                    $fdisplay(
                        requant_atomic_probe_fd[sid],
                        "# accepted boundary: local_wdata_valid && local_wdata_ready"
                    );
                end
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin : requant_atomic_probe_sample
        if (!u_NDP_Top_new.rst_n_sg) begin
            requant_atomic_probe_cycle = 0;
            for (int sid = 0; sid < 2; sid++) begin
                requant_atomic_probe_stage[sid] = -1;
                requant_atomic_probe_exec_d[sid] = 1'b0;
                requant_atomic_probe_finish_d[sid] = 1'b0;
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                    requant_atomic_probe_addr_q[sid][ch].delete();
            end
        end
        else if (requant_atomic_probe_enabled) begin
            requant_atomic_probe_cycle++;
            for (int sid = 0; sid < 2; sid++) begin
                if (return_obs_sem_exec_start_mon[0][sid] &&
                    !requant_atomic_probe_exec_d[sid]) begin
                    requant_atomic_probe_stage[sid]++;
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                        if (requant_atomic_probe_addr_q[sid][ch].size() != 0)
                            $fdisplay(
                                requant_atomic_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d local_stage=%0d ch=%0d stale_addr_count=%0d",
                                $time, requant_atomic_probe_cycle, sid,
                                requant_atomic_probe_stage[sid], ch,
                                requant_atomic_probe_addr_q[sid][ch].size()
                            );
                        requant_atomic_probe_addr_q[sid][ch].delete();
                    end
                    $fdisplay(
                        requant_atomic_probe_fd[sid],
                        "%0t | STAGE_START | cycle=%0d slice=%0d local_stage=%0d",
                        $time, requant_atomic_probe_cycle, sid,
                        requant_atomic_probe_stage[sid]
                    );
                end
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                    if (local_req_hs[0][sid][4][ch])
                        requant_atomic_probe_addr_q[sid][ch].push_back(
                            return_obs_mse4_local_req_addr_mon[0][sid][ch]
                        );
                    if (local_wdata_hs[0][sid][4][ch]) begin
                        logic [`MSE_TSA_ADDR_WIDTH-1:0] paired_addr;
                        if (requant_atomic_probe_addr_q[sid][ch].size() == 0) begin
                            $fdisplay(
                                requant_atomic_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d local_stage=%0d ch=%0d accepted_wdata_without_address=1 strobe=0xffff data=0x%032h",
                                $time, requant_atomic_probe_cycle, sid,
                                requant_atomic_probe_stage[sid], ch,
                                return_obs_mse4_local_wdata_mon[0][sid][ch]
                            );
                        end
                        else begin
                            paired_addr =
                                requant_atomic_probe_addr_q[sid][ch].pop_front();
                            $fdisplay(
                                requant_atomic_probe_fd[sid],
                                "%0t | MSE4_WRITE | cycle=%0d slice=%0d local_stage=%0d role=%s ch=%0d accepted=1 valid=1 ready=1 strobe=0xffff addr=0x%0h data=0x%032h",
                                $time, requant_atomic_probe_cycle, sid,
                                requant_atomic_probe_stage[sid],
                                (requant_atomic_probe_stage[sid] == 0) ?
                                    "guard" : "round_saturate",
                                ch, paired_addr,
                                return_obs_mse4_local_wdata_mon[0][sid][ch]
                            );
                        end
                    end
                end
                if (return_obs_slice_finish_mon[0][sid] &&
                    !requant_atomic_probe_finish_d[sid]) begin
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                        if (requant_atomic_probe_addr_q[sid][ch].size() != 0)
                            $fdisplay(
                                requant_atomic_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d local_stage=%0d ch=%0d finish_outstanding_addr_count=%0d",
                                $time, requant_atomic_probe_cycle, sid,
                                requant_atomic_probe_stage[sid], ch,
                                requant_atomic_probe_addr_q[sid][ch].size()
                            );
                    $fdisplay(
                        requant_atomic_probe_fd[sid],
                        "%0t | STAGE_FINISH | cycle=%0d slice=%0d local_stage=%0d",
                        $time, requant_atomic_probe_cycle, sid,
                        requant_atomic_probe_stage[sid]
                    );
                    $fflush(requant_atomic_probe_fd[sid]);
                end
                requant_atomic_probe_exec_d[sid] =
                    return_obs_sem_exec_start_mon[0][sid];
                requant_atomic_probe_finish_d[sid] =
                    return_obs_slice_finish_mon[0][sid];
            end
        end
    end

    final begin : requant_atomic_probe_final
        for (int sid = 0; sid < 2; sid++)
            if (requant_atomic_probe_fd[sid] != 0) begin
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                    if (requant_atomic_probe_addr_q[sid][ch].size() != 0)
                        $fdisplay(
                            requant_atomic_probe_fd[sid],
                            "%0t | PROBE_ERROR | final_outstanding ch=%0d count=%0d",
                            $time, ch,
                            requant_atomic_probe_addr_q[sid][ch].size()
                        );
                $fclose(requant_atomic_probe_fd[sid]);
            end
    end
"""


def _run_script() -> str:
    return f"""#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *) echo "NDP_copy path must be absolute: $1" >&2; exit 2 ;;
esac

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
runtime_tool="${{package_root}}/package_tools/requant_atomic_server_runtime.py"
common_tool="${{package_root}}/package_tools/requant_node0001_server_runtime.py"
package_manifest="${{package_root}}/{MANIFEST_NAME}"
ndp_root="$(cd "$1" && pwd)"
install_name="{INSTALL_NAME}"
cfg_root="${{ndp_root}}/install/cfg_pkg/${{install_name}}"
run_dir="${{ndp_root}}/run_${{install_name}}"
evidence_root="${{ndp_root}}/evidence_${{install_name}}"
return_dir="${{ndp_root}}/${{install_name}}_return"
return_zip="${{return_dir}}.zip"
return_sha="${{return_zip}}.sha256"
server_command="bash PREPARE_AND_RUN.sh ${{ndp_root}}"

for required in \
  "${{ndp_root}}/tb_NDP_Top_new_phy.sv" \
  "${{ndp_root}}/native_return_observer.svh" \
  "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy" \
  "${{ndp_root}}/rtl/filelists/NDP_Top_phy_filelist.f"; do
  if [ ! -f "${{required}}" ]; then
    echo "Missing required stock-RTL server input: ${{required}}" >&2
    exit 3
  fi
done
for command_name in python3 timeout make; do
  if ! command -v "${{command_name}}" >/dev/null 2>&1; then
    echo "Missing command: ${{command_name}}" >&2
    exit 3
  fi
done
for fresh in \
  "${{cfg_root}}" "${{run_dir}}" "${{evidence_root}}" \
  "${{return_dir}}" "${{return_zip}}" "${{return_sha}}"; do
  if [ -e "${{fresh}}" ]; then
    echo "Fresh identity required; target already exists: ${{fresh}}" >&2
    exit 4
  fi
done

mkdir -p "${{evidence_root}}"
printf '%s\\n' "${{server_command}}" > "${{evidence_root}}/server_command.txt"
run_status=125
compile_status=125
sim_status=125
probe_installed=0
finalization_started=0
termination_signal=""

restore_if_needed() {{
  if [ "${{probe_installed}}" -eq 1 ]; then
    python3 "${{common_tool}}" restore-probe \
      --ndp-root "${{ndp_root}}" --evidence-root "${{evidence_root}}" >/dev/null
    restore_status=$?
    if [ "${{restore_status}}" -eq 0 ]; then
      probe_installed=0
    else
      return "${{restore_status}}"
    fi
  fi
  return 0
}}

finalize_return() {{
  original_status="$1"
  if [ "${{finalization_started}}" -eq 1 ]; then
    exit "${{original_status}}"
  fi
  finalization_started=1
  trap - EXIT HUP INT TERM
  set +e
  restore_if_needed
  restore_status=$?
  if [ "${{restore_status}}" -ne 0 ]; then original_status="${{restore_status}}"; fi
  if [ -n "${{termination_signal}}" ]; then
    printf '%s\\n' "${{termination_signal}}" > "${{evidence_root}}/termination_signal.txt"
  fi
  printf '%s\\n' "${{compile_status}}" > "${{evidence_root}}/compile_exit_status.txt"
  printf '%s\\n' "${{sim_status}}" > "${{evidence_root}}/sim_exit_status.txt"
  printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"
  python3 "${{common_tool}}" capture-identity \
    --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
    --install-name "${{install_name}}" --phase post_run \
    --server-command "${{server_command}}" --exit-status "${{run_status}}" \
    --output "${{evidence_root}}/server_identity_post_run.json" >/dev/null
  post_run_status=$?
  restore_if_needed
  final_restore_status=$?
  python3 "${{common_tool}}" capture-identity \
    --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
    --install-name "${{install_name}}" --phase post_restore \
    --server-command "${{server_command}}" --exit-status "${{run_status}}" \
    --output "${{evidence_root}}/server_identity_post_restore.json" >/dev/null
  post_restore_status=$?
  identity_status=1
  if [ -f "${{evidence_root}}/server_identity_pre_install.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_probe_install.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_compile.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_run.json" ] &&
     [ -f "${{evidence_root}}/server_identity_post_restore.json" ] &&
     [ -f "${{evidence_root}}/tb_probe_install_receipt.json" ] &&
     [ -f "${{evidence_root}}/tb_probe_precompile_receipt.json" ]; then
    python3 "${{common_tool}}" verify-identity \
      --pre-install "${{evidence_root}}/server_identity_pre_install.json" \
      --post-probe-install "${{evidence_root}}/server_identity_post_probe_install.json" \
      --post-compile "${{evidence_root}}/server_identity_post_compile.json" \
      --post-run "${{evidence_root}}/server_identity_post_run.json" \
      --post-restore "${{evidence_root}}/server_identity_post_restore.json" \
      --probe-receipt "${{evidence_root}}/tb_probe_install_receipt.json" \
      --precompile-receipt "${{evidence_root}}/tb_probe_precompile_receipt.json" \
      --output "${{evidence_root}}/stock_rtl_identity_receipt.json" >/dev/null
    identity_status=$?
  fi
  python3 "${{runtime_tool}}" analyze \
    --package-root "${{package_root}}" --install-name "${{install_name}}" \
    --evidence-root "${{evidence_root}}" --run-dir "${{run_dir}}" \
    --run-status "${{run_status}}" \
    --output "${{evidence_root}}/SERVER_RESULT_GATE.json" >/dev/null
  analysis_status=$?
  python3 "${{runtime_tool}}" collect \
    --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" \
    --install-name "${{install_name}}" --evidence-root "${{evidence_root}}" \
    --run-dir "${{run_dir}}" --run-status "${{run_status}}" \
    --server-command "${{server_command}}" >/dev/null
  collection_status=$?
  if [ -f "${{return_zip}}" ] && [ -f "${{return_sha}}" ]; then
    echo "Return ZIP: ${{return_zip}}"
    echo "Return SHA256: ${{return_sha}}"
  else
    echo "Return collection did not produce ZIP + sidecar." >&2
  fi
  final_status="${{original_status}}"
  for status in \
    "${{post_run_status}}" "${{final_restore_status}}" \
    "${{post_restore_status}}" "${{identity_status}}" \
    "${{analysis_status}}" "${{collection_status}}"; do
    if [ "${{final_status}}" -eq 0 ] && [ "${{status}}" -ne 0 ]; then
      final_status="${{status}}"
    fi
  done
  exit "${{final_status}}"
}}
trap 'finalize_return $?' EXIT
trap 'termination_signal=HUP; exit 129' HUP
trap 'termination_signal=INT; exit 130' INT
trap 'termination_signal=TERM; exit 143' TERM

python3 "${{runtime_tool}}" preflight-package \
  --package-root "${{package_root}}" --install-name "${{install_name}}" \
  --output "${{evidence_root}}/package_preflight.json" >/dev/null || exit 5
python3 "${{common_tool}}" capture-identity \
  --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
  --install-name "${{install_name}}" --phase pre_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_pre_install.json" >/dev/null || exit 5

mkdir -p "${{cfg_root}}" "${{run_dir}}/sim_results"
cp -a "${{package_root}}/workload/runtime/." "${{cfg_root}}/"
python3 "${{runtime_tool}}" preflight-installed \
  --package-root "${{package_root}}" --ndp-root "${{ndp_root}}" \
  --install-name "${{install_name}}" \
  --output "${{evidence_root}}/installed_preflight.json" >/dev/null || exit 5
python3 "${{common_tool}}" install-probe \
  --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" \
  --evidence-root "${{evidence_root}}" >/dev/null || exit 5
probe_installed=1
python3 "${{common_tool}}" capture-identity \
  --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
  --install-name "${{install_name}}" --phase post_probe_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_probe_install.json" >/dev/null || exit 5
python3 "${{common_tool}}" verify-probe-installed \
  --ndp-root "${{ndp_root}}" --evidence-root "${{evidence_root}}" \
  --output "${{evidence_root}}/tb_probe_precompile_receipt.json" >/dev/null || exit 5

cd "${{ndp_root}}"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 \
  RUN_DIR="${{run_dir}}" VCS_EXTRA_OPTS="+incdir+${{ndp_root}}" \
  > "${{run_dir}}/sim_results/compile_driver.log" 2>&1
compile_status=$?
restore_if_needed
restore_status=$?
if [ "${{restore_status}}" -ne 0 ]; then
  run_status="${{restore_status}}"
  exit "${{run_status}}"
fi
python3 "${{common_tool}}" capture-identity \
  --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
  --install-name "${{install_name}}" --phase post_compile \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_compile.json" >/dev/null
post_compile_status=$?
if [ "${{compile_status}}" -eq 0 ] && [ "${{post_compile_status}}" -eq 0 ]; then
  (
    cd "${{run_dir}}"
    timeout --foreground --signal=TERM --kill-after=30s 12h \
      ./sim_results/simv \
      -l sim_results/sim.log \
      +vcs+lic+wait \
      +REQUANT_ATOMIC_PROBE \
      "+SCA_CFG=../install/cfg_pkg/${{install_name}}/sca_cfg.json" \
      "+SCA_CFG_D=../install/cfg_pkg/${{install_name}}/sca_cfg_D.json"
  )
  sim_status=$?
else
  sim_status=125
fi
if [ "${{compile_status}}" -ne 0 ]; then
  run_status="${{compile_status}}"
elif [ "${{post_compile_status}}" -ne 0 ]; then
  run_status="${{post_compile_status}}"
else
  run_status="${{sim_status}}"
fi
set -e
exit "${{run_status}}"
"""


def _readme() -> str:
    return f"""# Requant node0001 atomic two-stage stock-RTL diagnostic

解压后只运行一条命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

这是 `single-occurrence-two-stage` v2 的首次动态诊断包，不是 node0001
正式 E4/E5，也不解除 `B_REQUANT_SERVER_E4_E5`。它只运行一个逻辑
occurrence：两个物理 slice（0、1）共同执行 guard 与 round_saturate，
`Repeat_Num=2` 仍表示两个 stage。

脚本不修改 `tb_NDP_Top_new_phy.sv` 或任何 `rtl/**` 文件。只读 observer
仅事务式追加到根目录 `native_return_observer.svh` 以参与编译，并在编译后
立即逐字节恢复；恢复失败时结果 fail-closed。波形全部关闭。

预期证据：两个 stage 自然完成；20 个 accepted MSE4 写 beat 按 slice、
stage、地址、顺序和数据逐条匹配；四份正式 D 回读（slice0/1 的 guard 与
final）逐行匹配。失败回传会给出首分歧，并且最多只允许路由到一个对应的
附加原子项。回传 ZIP 为：

`{INSTALL_NAME}_return.zip` 与同名 `.sha256`。
"""


def _copy_native_evidence(
    native: dict[str, Any], package: Path, double_report: dict[str, Any]
) -> dict[str, Any]:
    output = native["output"]
    runtime = package / "workload/runtime"
    payloads = runtime / "payloads"
    _copy_lf(output / "install/execplan.txt", payloads / "execplan.txt")
    for source in sorted((output / "install/cfg_pkg").glob("*")):
        if source.is_file():
            _copy_lf(source, payloads / "cfg_pkg" / source.name)
    for slice_id in (0, 1):
        _copy_lf(
            SOURCE_ROOT / f"input_int32_slice{slice_id:02d}_128b.txt",
            payloads
            / f"inputs/op_w0_s00_guard/slice{slice_id:02d}/"
            "matrix_A_linearized_128bit.txt",
        )
        _copy_lf(
            SOURCE_ROOT / f"guard_golden_slice{slice_id:02d}_128b.txt",
            package / f"golden/guard_slice{slice_id:02d}_128b.txt",
        )
        _copy_lf(
            SOURCE_ROOT / f"final_golden_slice{slice_id:02d}_128b.txt",
            package / f"golden/final_slice{slice_id:02d}_128b.txt",
        )
    source_sca = json.loads((output / "sca_cfg.json").read_text(encoding="utf-8"))
    source_sca_d = json.loads(
        (output / "sca_cfg_D.json").read_text(encoding="utf-8")
    )
    _write_json(runtime / "sca_cfg.json", _rewrite_sca(source_sca))
    _write_json(runtime / "sca_cfg_D.json", _rewrite_sca_d(source_sca_d))

    validation = package / "validation"
    _write_json(validation / "native_double_rebuild.json", double_report)
    _write_json(validation / "planner_id_adapter_receipt.json", native["adapter_receipt"])
    _copy_lf(
        SOURCE_ROOT / "typed_graph.json",
        validation / "semantic_typed_graph_v2.json",
    )
    _write_json(validation / "planner_typed_graph_v2.json", native["graph"])
    for name in (
        "manifest.json",
        "generation_receipt.json",
        "expected_mse4_writes.json",
        "lifecycle_contract.json",
        "first_divergence_routing.json",
        "coverage_contract.json",
        "derivation_provenance.json",
        "guard.json",
        "round_saturate.json",
    ):
        _copy_lf(SOURCE_ROOT / name, validation / name)
    _copy_lf(CONTRACT, validation / "semantic_contract.json")
    _copy_lf(LOCAL_REPORT, validation / "local_contract_report.json")
    _copy_lf(READ_RECEIPT, validation / "generation_read_receipt.json")
    _copy_lf(
        output / "requant_atomic_v2_withbaseaddr.json",
        validation / "requant_atomic_v2_withbaseaddr.json",
    )
    _copy_lf(
        output / "instructions_explained.txt",
        validation / "instructions_explained.txt",
    )
    native_records: dict[str, Any] = {}
    for op_id, op_type in (
        ("op_w0_s00_guard", native["graph"]["operators"][0]["type"]),
        ("op_w0_s00_round", native["graph"]["operators"][1]["type"]),
    ):
        op_root = validation / "native" / op_id
        sources = {
            "address_bound_config.json": output / f"jsons/{op_id}_{op_type}.json",
            "mapping_review.json": output / f"config/{op_id}/mapping_review.json",
            "parsed_bitstream.txt": output / f"config/{op_id}/parsed_bitstream.txt",
            "detailed_dump.txt": output / f"config/{op_id}/detailed_dump.txt",
            "bitstream_64b.bin": (
                output / f"config/{op_id}/{op_id}_{op_type}_bitstream_64b.bin"
            ),
            "bitstream_128b.bin": (
                output / f"config/{op_id}/{op_id}_{op_type}_bitstream_128b.bin"
            ),
        }
        for target_name, source in sources.items():
            _copy_lf(source, op_root / target_name)
        review = json.loads(
            (output / f"config/{op_id}/mapping_review.json").read_text(
                encoding="utf-8"
            )
        )
        if (
            review.get("summary", {}).get("mapped_nodes", 0)
            < review.get("summary", {}).get("total_nodes", 1)
            or not review.get("node_to_resource")
            or not review.get("connection_mapping")
        ):
            raise AtomicPackageError(f"mapping review is incomplete: {op_id}")
        native_records[op_id] = {
            "operator_type": op_type,
            "mapping_summary": review["summary"],
            "files": _records(op_root),
        }
    return {
        "native_operator_count": 2,
        "native_operators": native_records,
        "execplan_128b_line_count": 6,
        "sca_preload_count": 6,
        "sca_d_readback_count": 4,
    }


def _build_tree(package: Path, source_identities: dict[str, Any]) -> dict[str, Any]:
    package.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="rq-at-native-") as temporary:
        native, double_report = _double_native_build(Path(temporary))
        native_receipt = _copy_native_evidence(
            native, package, double_report
        )
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script())
    _write_lf(package / "README.md", _readme())
    _copy_lf(
        ROOT / "tools/requant_atomic_server_runtime.py",
        package / "package_tools/requant_atomic_server_runtime.py",
    )
    _copy_lf(
        ROOT / "tools/requant_node0001_server_runtime.py",
        package / "package_tools/requant_node0001_server_runtime.py",
    )
    _write_lf(
        package / "tb_probe/requant_mse4_guard_observer_tail.svh",
        _observer_tail().lstrip(),
    )
    semantic_freeze = _semantic_freeze_receipt(package)
    files = _records(package)
    manifest = {
        "schema": SCHEMA,
        "package_name": package.name,
        "install_name": INSTALL_NAME,
        "target": "r5:hwop-0001-01 RequantizeUint8",
        "run_kind": "FIRST_DYNAMIC_DIAGNOSTIC",
        "default_dynamic_contract": "single-occurrence-two-stage",
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "evidence_level_before_run": "E2_LOCAL_CONTRACT_ONLY",
        "server_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "source_identities": source_identities,
        "semantic_freeze_against_atomic_v1": semantic_freeze,
        "native_rebuild": native_receipt,
        "execution_contract": {
            "logical_occurrence_count": 1,
            "physical_slice_instances": [0, 1],
            "slice_mask": "0b0000000000000000000000000011",
            "stage_count": 2,
            "repeat_num": 2,
            "start_comp_count": 2,
            "same_mask_completion_fence_count": 2,
            "guard_sfu_load_count": 1,
            "stage1_external_preload_count": 0,
            "guard_accepted_mse4_write_count": 16,
            "round_accepted_mse4_write_count": 4,
            "total_accepted_mse4_write_count": 20,
            "formal_readback_count": 4,
        },
        "first_divergence_policy": {
            "guard-only": "disabled_until_guard_write_or_completion_divergence",
            "alias-lifetime": "disabled_until_barrier_or_same-address_visibility_divergence",
            "round-only": "disabled_until_round_write_or_data_divergence",
            "combined_pass": "keep_all_additional_atomic_contracts_disabled",
        },
        "rtl_policy": {
            "functional_rtl_modified": False,
            "rtl_directory_write_allowed": False,
            "rtl_patch_included": False,
            "tb_file_modification_allowed": False,
            "force_or_deposit_allowed": False,
            "internal_tb_timeout_changed": False,
            "read_only_observer_included": True,
            "observer_transactional_restore_required": True,
        },
        "return_policy": {
            "allowlist_only": True,
            "small_raw_observer_and_readback_allowed": True,
            "waveforms": False,
            "build_tree": False,
            "nested_archives": False,
            "return_zip_limit_bytes": 2 * 1024 * 1024,
        },
        "bootstrap_immutability_policy": {
            "rule_id": "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "shell_exports_python_dont_write_bytecode_before_python": True,
            "python_sets_sys_dont_write_bytecode_before_package_import": True,
            "pycache_or_pyc_allowlisted": False,
            "fresh_extracted_runtime_entry_required": True,
            "exact_path_size_sha_before_after_required": True,
        },
        "rule_ids": list(RULE_IDS),
        "release_gate": {
            "formal_e4_or_e5_gate": False,
            "remaining_blocker": "B_REQUANT_SERVER_E4_E5",
            "candidate_release": False,
        },
        "files": files,
        "payload_tree_sha256": _tree_sha256(files),
    }
    _write_json(package / MANIFEST_NAME, manifest)
    preflight = preflight_package(package, INSTALL_NAME)
    return {
        "manifest": manifest,
        "preflight": preflight,
    }


def _zip_tree(package: Path) -> tuple[Path, str]:
    zip_path = package.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    digest = _sha256(zip_path)
    zip_path.with_suffix(".zip.sha256").write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return zip_path, digest


def _validate_zip(package: Path) -> dict[str, Any]:
    report = preflight_package(package, INSTALL_NAME)
    zip_path = package.with_suffix(".zip")
    sidecar = zip_path.with_suffix(".zip.sha256")
    if not zip_path.is_file() or not sidecar.is_file():
        raise AtomicPackageError("ZIP or sidecar is missing")
    digest = _sha256(zip_path)
    if sidecar.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise AtomicPackageError("ZIP sidecar differs")
    with zipfile.ZipFile(zip_path) as archive:
        expected = [
            f"{package.name}/{path.relative_to(package).as_posix()}"
            for path in sorted(item for item in package.rglob("*") if item.is_file())
        ]
        if archive.namelist() != expected:
            raise AtomicPackageError("ZIP exact file set or order differs")
        for name in expected:
            relative = PurePathCompat(name[len(package.name) + 1 :]).value
            if archive.read(name) != (package / relative).read_bytes():
                raise AtomicPackageError(f"ZIP payload differs: {name}")
    if any(
        "rtl" in {part.lower() for part in Path(name).parts}
        for name in zipfile.ZipFile(zip_path).namelist()
    ):
        raise AtomicPackageError("ZIP contains an rtl/ entry")
    return {
        **report,
        "zip_exact_set": True,
        "zip_sha256": digest,
        "zip_size_bytes": zip_path.stat().st_size,
        "sidecar": sidecar.as_posix(),
    }


class PurePathCompat:
    """Convert deterministic POSIX ZIP paths into local relative Path values."""

    def __init__(self, value: str) -> None:
        if value.startswith("/") or ".." in value.split("/"):
            raise AtomicPackageError(f"unsafe ZIP path: {value}")
        self.value = Path(*value.split("/"))


def _validate_bootstrap_immutability(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="rq-at-bootstrap-") as temporary:
        extract_root = Path(temporary) / "fresh_extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        fresh_package = extract_root / package.name
        before = _records(fresh_package)
        before_size = sum(item["size_bytes"] for item in before.values())
        output = Path(temporary) / "package_preflight.json"
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [
            sys.executable,
            str(
                fresh_package
                / "package_tools/requant_atomic_server_runtime.py"
            ),
            "preflight-package",
            "--package-root",
            str(fresh_package),
            "--install-name",
            INSTALL_NAME,
            "--output",
            str(output),
        ]
        completed = subprocess.run(
            command,
            cwd=fresh_package,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        after = _records(fresh_package)
        after_size = sum(item["size_bytes"] for item in after.values())
        if completed.returncode != 0:
            raise AtomicPackageError(
                "fresh-extracted packaged runtime preflight failed: "
                + completed.stderr.strip()
            )
        if before != after or before_size != after_size:
            differing = sorted(set(before) ^ set(after))
            differing.extend(
                relative
                for relative in sorted(set(before) & set(after))
                if before[relative] != after[relative]
            )
            raise AtomicPackageError(
                "fresh-extracted package tree changed during runtime bootstrap: "
                f"{differing[:8]}"
            )
        forbidden = [
            relative
            for relative in after
            if "__pycache__" in {part.lower() for part in relative.split("/")}
            or Path(*relative.split("/")).suffix.lower() in {".pyc", ".pyo"}
        ]
        if forbidden:
            raise AtomicPackageError(
                f"runtime bootstrap materialized Python bytecode: {forbidden[:4]}"
            )
        runtime_report = json.loads(output.read_text(encoding="utf-8"))
        if runtime_report.get("status") != "package_preflight_passed":
            raise AtomicPackageError(
                "fresh-extracted runtime did not pass package preflight"
            )
        return {
            "schema": "requant-atomic2-bootstrap-immutability-receipt-v1",
            "rule_id": "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "status": "pass",
            "entry": "package_tools/requant_atomic_server_runtime.py preflight-package",
            "fresh_zip_extraction": True,
            "preflight_output_outside_package": True,
            "python_dont_write_bytecode_environment": True,
            "python_dont_write_bytecode_runtime": True,
            "pycache_or_pyc_allowlisted": False,
            "package_file_count_before": len(before),
            "package_file_count_after": len(after),
            "package_size_bytes_before": before_size,
            "package_size_bytes_after": after_size,
            "package_tree_sha256_before": _tree_sha256(before),
            "package_tree_sha256_after": _tree_sha256(after),
            "exact_path_size_sha_unchanged": True,
        }


def _fresh_final_targets(output: Path) -> None:
    for path in (
        output,
        output.with_suffix(".zip"),
        output.with_suffix(".zip.sha256"),
    ):
        if path.exists():
            raise AtomicPackageError(f"fresh package identity required: {path}")


def build_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = output.resolve()
    if output.name != INSTALL_NAME:
        raise AtomicPackageError(
            f"output directory name must preserve ZIP identity: {INSTALL_NAME}"
        )
    _fresh_final_targets(output)
    source_identities = _verify_sources()
    with tempfile.TemporaryDirectory(prefix="rq-at-pkg-a-") as left_parent, tempfile.TemporaryDirectory(
        prefix="rq-at-pkg-b-"
    ) as right_parent:
        left = Path(left_parent) / INSTALL_NAME
        right = Path(right_parent) / INSTALL_NAME
        left_report = _build_tree(left, source_identities)
        right_report = _build_tree(right, source_identities)
        left_zip, left_sha = _zip_tree(left)
        right_zip, right_sha = _zip_tree(right)
        if (
            left_sha != right_sha
            or left_zip.read_bytes() != right_zip.read_bytes()
            or _records(left) != _records(right)
        ):
            raise AtomicPackageError("two fresh package builds are not byte-identical")
        shutil.copytree(right, output)
        shutil.copyfile(right_zip, output.with_suffix(".zip"))
        shutil.copyfile(
            right_zip.with_suffix(".zip.sha256"),
            output.with_suffix(".zip.sha256"),
        )
    validation = _validate_zip(output)
    bootstrap_immutability = _validate_bootstrap_immutability(output)
    return {
        "package": output.as_posix(),
        "manifest": (output / MANIFEST_NAME).as_posix(),
        "zip": output.with_suffix(".zip").as_posix(),
        "zip_size_bytes": output.with_suffix(".zip").stat().st_size,
        "zip_sha256": validation["zip_sha256"],
        "sidecar": output.with_suffix(".zip.sha256").as_posix(),
        "payload_tree_sha256": left_report["manifest"]["payload_tree_sha256"],
        "preflight": validation,
        "bootstrap_immutability": bootstrap_immutability,
        "deterministic_package_build_count": 2,
        "deterministic_zip_byte_identical": True,
        "release_gate": {
            "candidate_release": False,
            "counts_as_node0001_e4": False,
            "counts_as_node0001_e5": False,
            "remaining_blocker": "B_REQUANT_SERVER_E4_E5",
        },
        "server_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": f"{INSTALL_NAME}_return.zip",
    }


def validate_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    package = output.resolve()
    report = _validate_zip(package)
    report["bootstrap_immutability"] = _validate_bootstrap_immutability(
        package
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        report = (
            validate_package(args.output)
            if args.validate_only
            else build_package(args.output)
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Requant atomic package build failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
