#!/usr/bin/env python3
"""Build the one-command stock-RTL Dequant node0077 atomic diagnostic package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.dequantize_linear_vertical import (  # noqa: E402
    OP_TYPE,
    _copy_isolated_toolchain,
)
from tools.dequant_atomic_server_runtime import (  # noqa: E402
    MANIFEST_NAME,
    preflight_package,
)


SCHEMA = "dequant-node0077-atomic-stockrtl-firstdynamic-package-v3"
INSTALL_NAME = "dq_node0077_atomic1_stock_v3"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
SOURCE_ROOT = (
    ROOT
    / "configs/native_ndp_sim/node0077_dequant_atomic_single_stage_stocktb_v2"
)
CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "dequant_node0077_atomic_single_stage_stocktb_v2.json"
)
LOCAL_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-dequant-node0077-atomic-single-stage-stocktb-v2/local_contract_report.json"
)
FULL_V6_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/"
    "resnet50_dequant_node0077_uint8_fp32_strict_v6/config.json"
)
FULL_V6_E2_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-dequant-node0077-e2-v6/local_e2_report.json"
)
V1_ANALYSIS_RECORD = (
    ROOT / ".agents/task_records/20260726_dequant_atomic1_v1_return_analysis.md"
)
V1_ANALYSIS_REPORT = (
    ROOT
    / "server_returns/"
    "dequant_node0077_atomic1_stock_v1_return_analysis_20260726.json"
)
V1_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/"
    "node0077_dequant_atomic_single_stage_stocktb_v1/config.json"
)
READ_RECEIPT = (
    ROOT
    / ".agents/task_records/"
    "20260726_dual_xmr_safe_server_packages_read_receipt.json"
)
PREDECESSOR_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "dq_node0077_atomic1_stock_v2"
)
PREDECESSOR_PACKAGE_ZIP_SHA256 = (
    "6d3f9c52f602131a5f3b4950d8d477b13f03509900e15dc82ad40f9aa80fac71"
)
V2_ANALYSIS_REPORT = (
    ROOT
    / "server_returns/"
    "dq_node0077_atomic1_stock_v2_return_analysis_20260726.json"
)
V2_ANALYSIS_RECORD = (
    ROOT
    / ".agents/task_records/"
    "20260726_dequant_atomic_v2_predicted_xmr_return.md"
)
SOURCE_IDENTITIES = {
    "config": (
        SOURCE_ROOT / "config.json",
        "c974e9ca8bdd8635a2cf804bbb90b7c72aae2265084dd4256e4fa267da846718",
    ),
    "manifest": (
        SOURCE_ROOT / "manifest.json",
        "d2d514fd81e0cdcbd439a6b7a83365dcb5cee0891a8be98181c2220a97fac708",
    ),
    "generation_receipt": (
        SOURCE_ROOT / "generation_receipt.json",
        "e50561cec5daeb5b8bd12badeb4f9b6bf75e74ce3d9e4397993df560c56db392",
    ),
    "atomic_rule": (
        ROOT / ".agents/rules/DequantizeLinear原子动态合同规则.md",
        "0785af08353894f42aa703f06929d2c05944898698fdc819a7b8e0ae6a737199",
    ),
    "dequant_rule": (
        ROOT / ".agents/rules/DequantizeLinear算子配置规则.md",
        "b6c6586422706287625c39792e33eda6b39dc4f8a4cbd24f363b921cbc526b09",
    ),
    "server_rule": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "2ceeb45736ac4d6a887024642c71bfc1fa40cf35646e7fc93e5a751d3d4d98d0",
    ),
    "semantic_contract": (
        CONTRACT,
        "29b59e73ec729771ee09a794e0d60732e3aa80c944961320dee0f050500bc617",
    ),
    "local_contract_report": (
        LOCAL_REPORT,
        "235bf6232855914c2ac47d04697db5b4ec40ffbf1e5f1d93361a93885b8412e6",
    ),
    "full_v6_config": (
        FULL_V6_CONFIG,
        "72c871e3bb4583302961ead62cabefa8b125281be97b5df61b45a190f18998bb",
    ),
    "full_v6_e2_report": (
        FULL_V6_E2_REPORT,
        "6a024f7da99026b977a4356909c99e7ac1635733fd95173a4f6741795cb965ee",
    ),
    "v1_analysis_record": (
        V1_ANALYSIS_RECORD,
        "d7878d0e437edd4c3bc3c17a8dffdc0e4a2528f4a4e49bbd559799ca42065135",
    ),
    "v1_analysis_report": (
        V1_ANALYSIS_REPORT,
        "d05d5768232120b5286c2d0529197b2d80fb4eb5cc1d019ba4eb2ab48b13acc1",
    ),
    "v1_config": (
        V1_CONFIG,
        "1e331488ff95d10f5c9b50abde13193b495d24f0230f51b6e4f38f836a9ee290",
    ),
    "read_receipt": (
        READ_RECEIPT,
        "f8c2b72ff343af19028e3177d5b0d3aba9203639ef8e35433a7d2ae824c5e14d",
    ),
    "v2_xmr_analysis_report": (
        V2_ANALYSIS_REPORT,
        "1c802e43a58df45e84a6c16a3ec067d055238c3be039d608b4baf1742cb9e7b9",
    ),
    "v2_xmr_analysis_record": (
        V2_ANALYSIS_RECORD,
        "67e13a7f275a78a658029ed9e8c4eaa41f4d3d50ee102b772ae46527dcfd2236",
    ),
}
RULE_IDS = (
    "CDA-SERVER-WORKLOAD-PROVENANCE-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
    "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
    "CDA-DEQUANT-ONNX-ORDER-001",
    "CDA-DEQUANT-NO-AFFINE-MAC-001",
    "CDA-DEQUANT-TWO-STAGE-GA-001",
    "CDA-DEQUANT-NORMAL-OUTBUFFER-001",
    "CDA-DEQUANT-STREAM-LIFECYCLE-001",
    "CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001",
    "CDA-DEQUANT-ATOMIC-STOCK-TB-001",
    "CDA-DEQUANT-ATOMIC-V1-DYNAMIC-EVIDENCE-001",
)


class AtomicDequantPackageError(RuntimeError):
    """Raised when a deterministic atomic Dequant package cannot be built."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _verify_sources() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, (path, expected) in SOURCE_IDENTITIES.items():
        if not path.is_file() or _sha256(path) != expected:
            raise AtomicDequantPackageError(f"source identity differs: {path}")
        result[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": expected,
        }
    manifest = json.loads((SOURCE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        path = SOURCE_ROOT / relative
        if (
            not path.is_file()
            or path.stat().st_size != expected["size_bytes"]
            or _sha256(path) != expected["sha256"]
        ):
            raise AtomicDequantPackageError(f"atomic config-root file differs: {relative}")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    report = json.loads(LOCAL_REPORT.read_text(encoding="utf-8"))
    v1_config = json.loads(V1_CONFIG.read_text(encoding="utf-8"))
    v2_config = json.loads((SOURCE_ROOT / "config.json").read_text(encoding="utf-8"))
    expected_v2 = deepcopy(v1_config)
    expected_v2["buffer_loop_configs"]["GROUP2"]["ROW_LC"]["end"] = 4
    if (
        contract.get("active_slices") != [0, 1]
        or contract.get("repeat_num") != 1
        or contract.get("counts_as_node0077_e4") is not False
        or contract.get("counts_as_node0077_e5") is not False
        or report.get("dynamic_execution_status") != "NOT_RUN"
    ):
        raise AtomicDequantPackageError("atomic contract claim boundary differs")
    if v2_config != expected_v2:
        raise AtomicDequantPackageError(
            "atomic v2 config differs beyond GROUP2.ROW_LC.end 1 -> 4"
        )
    return result


def _is_frozen_dequant_semantic_payload(relative: str) -> bool:
    return (
        relative.startswith("golden/")
        or relative.startswith("validation/")
        or relative.startswith("workload/runtime/payloads/")
        or relative == "workload/runtime/sca_cfg_D.json"
    )


def _normalize_install_identity(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_install_identity(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_normalize_install_identity(item) for item in value]
    if isinstance(value, str):
        for install_name in (PREDECESSOR_PACKAGE.name, INSTALL_NAME):
            value = value.replace(install_name, "<INSTALL_IDENTITY>")
        return value
    return value


def _semantic_freeze_receipt(package: Path) -> dict[str, Any]:
    predecessor_zip = PREDECESSOR_PACKAGE.with_suffix(".zip")
    if (
        not PREDECESSOR_PACKAGE.is_dir()
        or not predecessor_zip.is_file()
        or _sha256(predecessor_zip) != PREDECESSOR_PACKAGE_ZIP_SHA256
    ):
        raise AtomicDequantPackageError("frozen Dequant atomic v2 package differs")
    predecessor_manifest = json.loads(
        (PREDECESSOR_PACKAGE / MANIFEST_NAME).read_text(encoding="utf-8")
    )
    if predecessor_manifest.get("files") != _records(
        PREDECESSOR_PACKAGE, exclude_manifest=True
    ):
        raise AtomicDequantPackageError(
            "frozen Dequant atomic v2 exact set differs"
        )
    predecessor_records = {
        relative: identity
        for relative, identity in _records(PREDECESSOR_PACKAGE).items()
        if _is_frozen_dequant_semantic_payload(relative)
    }
    successor_records = {
        relative: identity
        for relative, identity in _records(package).items()
        if _is_frozen_dequant_semantic_payload(relative)
    }
    if predecessor_records != successor_records:
        differing = sorted(set(predecessor_records) ^ set(successor_records))
        differing.extend(
            relative
            for relative in sorted(set(predecessor_records) & set(successor_records))
            if predecessor_records[relative] != successor_records[relative]
        )
        raise AtomicDequantPackageError(
            f"Dequant semantic payload differs from frozen v2: {differing[:8]}"
        )
    predecessor_sca = json.loads(
        (
            PREDECESSOR_PACKAGE / "workload/runtime/sca_cfg.json"
        ).read_text(encoding="utf-8")
    )
    successor_sca = json.loads(
        (package / "workload/runtime/sca_cfg.json").read_text(encoding="utf-8")
    )
    if _normalize_install_identity(predecessor_sca) != _normalize_install_identity(
        successor_sca
    ):
        raise AtomicDequantPackageError(
            "Dequant SCA differs beyond the unique install namespace"
        )
    return {
        "schema": "dequant-atomic-v2-to-v3-semantic-freeze-v1",
        "status": "pass",
        "predecessor": PREDECESSOR_PACKAGE.relative_to(ROOT).as_posix(),
        "predecessor_zip_sha256": PREDECESSOR_PACKAGE_ZIP_SHA256,
        "semantic_payload_file_count": len(successor_records),
        "semantic_payload_tree_sha256": _tree_sha256(successor_records),
        "semantic_payload_byte_identical": True,
        "sca_normalized_equal": True,
        "semantic_change": False,
        "allowed_changes": [
            "unique install/run/return identity",
            "observer/runtime/validator XMR elaboration infrastructure",
            "receipts and manifest"
        ],
    }


def _typed_constant(
    *,
    name: str,
    bits: int,
    pe_names: tuple[str, ...],
    artifact_id: str,
) -> dict[str, Any]:
    payload = struct.pack("<I", bits)
    value = struct.unpack("<f", payload)[0]
    value_sha = _sha256_bytes(payload)
    return {
        "tensor_id": f"hwop-0077-00.atomic.{name}",
        "dtype": "float32",
        "shape": [1],
        "identity_sha256": value_sha,
        "value_sha256": value_sha,
        "values": [value],
        "float32_bits": [f"0x{bits:08x}"],
        "axis": None,
        "source_kind": "atomic-contract",
        "source_parameter_ids": [f"hwop-0077-00.{name}"],
        "target_bindings": [
            {
                "location": (
                    f"config_json:{artifact_id}#/general_array/PE_array/"
                    f"{pe}/inport1/constant"
                ),
                "encoding": "fp32_bits",
                "derivation": "frozen atomic Dequant config constant",
                "element_indices": [0],
                "artifact_id": artifact_id,
            }
            for pe in pe_names
        ],
    }


def _planner_graph() -> tuple[dict[str, Any], dict[str, Any]]:
    source = json.loads((SOURCE_ROOT / "typed_graph.json").read_text(encoding="utf-8"))
    graph = deepcopy(source)
    operator = graph["operators"][0]
    if (
        operator.get("id") != "op0"
        or operator.get("type") != OP_TYPE
        or operator.get("used_slices")
        != "0b0000000000000000000000000011"
    ):
        raise AtomicDequantPackageError("frozen typed graph identity differs")
    raw_text = (SOURCE_ROOT / "config.json").read_text(encoding="utf-8")
    artifact_id = "hwop-0077-00.atomic.config"
    operator["instance_id"] = "r5:hwop-0077-00:atomic-single-stage"
    operator["attributes"] = {
        "diagnostic_only": True,
        "logical_occurrence_count": 1,
        "physical_slice_instances": [0, 1],
        "normal_outbuffer_only": True,
        "rule_id": "CDA-DEQUANT-ATOMIC-STOCK-TB-001",
    }
    operator["constants"] = {
        "negative_zero_point": _typed_constant(
            name="negative_zero_point",
            bits=0xC2700000,
            pe_names=("PE00", "PE02", "PE20", "PE22"),
            artifact_id=artifact_id,
        ),
        "x_scale": _typed_constant(
            name="x_scale",
            bits=0x3E01622D,
            pe_names=("PE10", "PE12", "PE30", "PE32"),
            artifact_id=artifact_id,
        ),
    }
    operator["config_artifacts"] = [
        {
            "artifact_id": artifact_id,
            "role": "atomic_dequant_config",
            "path": (
                "configs/native_ndp_sim/"
                "node0077_dequant_atomic_single_stage_stocktb_v2/config.json"
            ),
            "sha256": _sha256(SOURCE_ROOT / "config.json"),
            "raw_text": raw_text,
        }
    ]
    receipt = {
        "schema": "dequant-atomic-planner-transport-adapter-v2",
        "frozen_typed_graph_sha256": _sha256(SOURCE_ROOT / "typed_graph.json"),
        "frozen_config_sha256": _sha256(SOURCE_ROOT / "config.json"),
        "semantic_json_or_tensor_changed": False,
        "upstream_semantic_change_from_atomic_v1": {
            "field": "buffer_loop_configs.GROUP2.ROW_LC.end",
            "old": 1,
            "new": 4,
            "reason": "supply four 16-byte rows for one 64-byte D transaction",
        },
        "added_fields": [
            "operator.instance_id",
            "operator.attributes",
            "typed constant transport identity/bindings",
            "config_artifacts exact raw text",
        ],
        "reason": (
            "the frozen diagnostic graph is semantic IR; the native typed parser "
            "requires explicit lossless transport identity and target bindings"
        ),
    }
    return graph, receipt


def _native_once(run_dir: Path) -> dict[str, Any]:
    graph, adapter = _planner_graph()
    tool = run_dir / "tool"
    _copy_isolated_toolchain(ROOT, tool)
    shutil.copyfile(SOURCE_ROOT / "config.json", tool / "jsons" / f"{OP_TYPE}.json")
    input_root = tool / "input"
    input_root.mkdir()
    graph_path = input_root / "dequant_atomic_stocktb.json"
    _write_json(graph_path, graph)
    seed_hook = run_dir / "seed_hook"
    seed_hook.mkdir()
    _write_lf(seed_hook / "sitecustomize.py", "import random\nrandom.seed(77)\n")
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
        [sys.executable, str(tool / "model_execplan/main.py"), str(graph_path)],
        cwd=tool,
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
    if process.returncode != 0 or "Parsed operators: 1" not in process.stdout:
        raise AtomicDequantPackageError(
            f"isolated native planner/mapper/encoder failed: rc={process.returncode}; "
            f"stderr={process.stderr[-800:]}"
        )
    output = tool / "model_execplan/output/dequant_atomic_stocktb"
    required = {
        "execplan": output / "install/execplan.txt",
        "explanation": output / "instructions_explained.txt",
        "sca": output / "sca_cfg.json",
        "sca_d": output / "sca_cfg_D.json",
        "addressed_graph": output / "dequant_atomic_stocktb_withbaseaddr.json",
        "addressed_config": output / f"jsons/op0_{OP_TYPE}.json",
        "mapping": output / "config/op0/mapping_review.json",
        "parsed_bitstream": output / "config/op0/parsed_bitstream.txt",
        "detailed_dump": output / "config/op0/detailed_dump.txt",
        "bitstream_128b": (
            output / f"config/op0/op0_{OP_TYPE}_bitstream_128b.bin"
        ),
        "bitstream_64b": output / f"config/op0/op0_{OP_TYPE}_bitstream_64b.bin",
        "cfg_pkg": output / f"install/cfg_pkg/op0_{OP_TYPE}_bitstream_128b.bin",
    }
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        raise AtomicDequantPackageError(f"native outputs are missing: {missing}")
    if _sha256(required["bitstream_128b"]) != _sha256(required["cfg_pkg"]):
        raise AtomicDequantPackageError("native cfg_pkg differs from encoded bitstream")
    return {
        "run_dir": run_dir,
        "output": output,
        "graph": graph,
        "adapter": adapter,
        "required": required,
    }


def _native_file_map(output: Path) -> dict[str, dict[str, Any]]:
    return {
        relative: identity
        for relative, identity in _records(output).items()
        if not relative.endswith(
            ("/placement.png", "/encoder_stdout.log", "/encoder_stderr.log")
        )
    }


def _double_native(temp_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    left = _native_once(temp_root / "a")
    right = _native_once(temp_root / "b")
    files_left = _native_file_map(left["output"])
    files_right = _native_file_map(right["output"])
    if files_left != files_right:
        differing = sorted(
            name
            for name in set(files_left) | set(files_right)
            if files_left.get(name) != files_right.get(name)
        )
        raise AtomicDequantPackageError(
            f"two fresh native rebuilds differ: {differing[:8]}"
        )
    return left, {
        "schema": "dequant-atomic-native-double-rebuild-v1",
        "fresh_isolated_run_count": 2,
        "mapping_seed": 77,
        "python_hash_seed": 0,
        "deterministic_files_byte_identical": True,
        "deterministic_file_count": len(files_left),
        "excluded_nonsemantic_products": [
            "config/*/placement.png",
            "config/*/encoder_stdout.log",
            "config/*/encoder_stderr.log",
        ],
        "files": files_left,
    }


def _rewrite_sca(source: dict[str, Any]) -> dict[str, Any]:
    sca = deepcopy(source)
    expected = {
        "Exec_Base",
        "Exec_Length",
        "ExecutionPlan",
        "op0_matrixA_slice0",
        "op0_matrixA_slice1",
        "op0_config",
    }
    if set(sca) != expected:
        raise AtomicDequantPackageError(
            f"native atomic SCA exact set differs: {sorted(sca)}"
        )
    prefix = f"../install/cfg_pkg/{INSTALL_NAME}/payloads"
    sca["ExecutionPlan"]["path"] = f"{prefix}/execplan.txt"
    sca["Repeat_Num"] = 1
    for slice_id in (0, 1):
        sca[f"op0_matrixA_slice{slice_id}"]["path"] = (
            f"{prefix}/inputs/slice{slice_id:02d}/matrix_A_linearized_128bit.txt"
        )
    sca["op0_config"]["path"] = (
        f"{prefix}/cfg_pkg/{Path(sca['op0_config']['path']).name}"
    )
    return sca


def _rewrite_sca_d(source: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "op0_matrixD_slice0": "0x00000010",
        "op0_matrixD_slice1": "0x02000010",
    }
    if set(source) != set(expected):
        raise AtomicDequantPackageError("native atomic SCA_D exact set differs")
    result: dict[str, Any] = {}
    for name, address in expected.items():
        entry = source[name]
        if entry.get("base_addr") != address or entry.get("length") != 4:
            raise AtomicDequantPackageError(f"native SCA_D differs: {name}")
        result[name] = {
            "base_addr": address,
            "path": f"sim_results/formal_readback/{name}.txt",
            "length": 4,
        }
    return result


def _observer_tail() -> str:
    return r"""
// Dequant node0077 atomic accepted MSE4 observer v3.
// Read-only and plusarg-gated; no DUT/TB signal is driven.
// Both pre-remap linear and post-remap request addresses are retained.
    bit dequant_atomic_probe_enabled;
    integer dequant_atomic_probe_fd [0:1];
    logic dequant_atomic_probe_exec_d [0:1];
    logic dequant_atomic_probe_finish_d [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        dequant_atomic_transfer_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        dequant_atomic_linear_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        dequant_atomic_transfer_wdata [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        dequant_atomic_linear_wdata [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        dequant_atomic_post_wdata [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic dequant_atomic_mse4_ag_wr_hs [0:1][0:`MSE_REQ_CHL_NUM-1];
    logic dequant_atomic_mse4_ag_bp_pre_barrier [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        dequant_atomic_mse4_transfer_addr_nooff [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        dequant_atomic_mse4_stream_base_word [0:1];
    integer dequant_atomic_accepted_req_count [0:1];
    integer dequant_atomic_accepted_wdata_count [0:1];
    integer dequant_atomic_accepted_write_count [0:1];
    integer dequant_atomic_unpaired_data_count [0:1];
    longint unsigned dequant_atomic_probe_cycle;
    integer dequant_atomic_probe_mkdir_status;

    generate
        for (genvar dq_sid = 0; dq_sid < 2; dq_sid++) begin : DQ_ATOMIC_SID
            assign dequant_atomic_mse4_ag_bp_pre_barrier[dq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[dq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mem_ag_ob_bp_pre_barrier;
            assign dequant_atomic_mse4_transfer_addr_nooff[dq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[dq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.transfer_addr_nooff;
            assign dequant_atomic_mse4_stream_base_word[dq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[dq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mse_stream_base_addr[
                    `GLOBAL_DDR_ADDR_WIDTH-1:`DDR_ADDR_OFFSET_WIDTH
                ];
            for (genvar dq_ch = 0;
                 dq_ch < `MSE_REQ_CHL_NUM;
                 dq_ch++) begin : DQ_ATOMIC_MSE4_CH
                assign dequant_atomic_mse4_ag_wr_hs[dq_sid][dq_ch] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[dq_sid]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_WR_Memory_AG.mem_ag_ob_chl_wr_hs[dq_ch];
            end
        end
    endgenerate

    initial begin : dequant_atomic_probe_init
        dequant_atomic_probe_enabled = $test$plusargs("DEQUANT_ATOMIC_PROBE");
        dequant_atomic_probe_cycle = 0;
        for (int sid = 0; sid < 2; sid++) begin
            dequant_atomic_probe_fd[sid] = 0;
            dequant_atomic_probe_exec_d[sid] = 1'b0;
            dequant_atomic_probe_finish_d[sid] = 1'b0;
            dequant_atomic_accepted_req_count[sid] = 0;
            dequant_atomic_accepted_wdata_count[sid] = 0;
            dequant_atomic_accepted_write_count[sid] = 0;
            dequant_atomic_unpaired_data_count[sid] = 0;
            for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                dequant_atomic_transfer_pending[sid][ch].delete();
                dequant_atomic_linear_pending[sid][ch].delete();
                dequant_atomic_transfer_wdata[sid][ch].delete();
                dequant_atomic_linear_wdata[sid][ch].delete();
                dequant_atomic_post_wdata[sid][ch].delete();
            end
        end
        if (dequant_atomic_probe_enabled) begin
            dequant_atomic_probe_mkdir_status =
                $system("mkdir -p sim_results/dequant_atomic_probe");
            for (int sid = 0; sid < 2; sid++) begin
                dequant_atomic_probe_fd[sid] = $fopen(
                    $sformatf(
                        "sim_results/dequant_atomic_probe/slice%02d.log", sid
                    ),
                    "w"
                );
                if (dequant_atomic_probe_fd[sid] == 0)
                    $error("DEQUANT_ATOMIC_PROBE cannot open slice%0d log", sid);
                else
                    $fdisplay(
                        dequant_atomic_probe_fd[sid],
                        "# Dequant node0077 atomic accepted MSE4 observer v3"
                    );
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin : dequant_atomic_probe_sample
        if (!u_NDP_Top_new.rst_n_sg) begin
            dequant_atomic_probe_cycle = 0;
            for (int sid = 0; sid < 2; sid++) begin
                dequant_atomic_probe_exec_d[sid] = 1'b0;
                dequant_atomic_probe_finish_d[sid] = 1'b0;
                dequant_atomic_accepted_req_count[sid] = 0;
                dequant_atomic_accepted_wdata_count[sid] = 0;
                dequant_atomic_accepted_write_count[sid] = 0;
                dequant_atomic_unpaired_data_count[sid] = 0;
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                    dequant_atomic_transfer_pending[sid][ch].delete();
                    dequant_atomic_linear_pending[sid][ch].delete();
                    dequant_atomic_transfer_wdata[sid][ch].delete();
                    dequant_atomic_linear_wdata[sid][ch].delete();
                    dequant_atomic_post_wdata[sid][ch].delete();
                end
            end
        end
        else if (dequant_atomic_probe_enabled) begin
            dequant_atomic_probe_cycle++;
            for (int sid = 0; sid < 2; sid++) begin
                if (return_obs_sem_exec_start_mon[0][sid] &&
                    !dequant_atomic_probe_exec_d[sid])
                    $fdisplay(
                        dequant_atomic_probe_fd[sid],
                        "%0t | STAGE_START | cycle=%0d slice=%0d local_stage=0",
                        $time, dequant_atomic_probe_cycle, sid
                    );
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                    if (dequant_atomic_mse4_ag_wr_hs[sid][ch] &&
                        dequant_atomic_mse4_ag_bp_pre_barrier[sid]) begin
                        dequant_atomic_transfer_pending[sid][ch].push_back(
                            dequant_atomic_mse4_transfer_addr_nooff[sid]
                        );
                        dequant_atomic_linear_pending[sid][ch].push_back(
                            dequant_atomic_mse4_transfer_addr_nooff[sid] +
                            dequant_atomic_mse4_stream_base_word[sid]
                        );
                    end
                    if (local_req_hs[0][sid][4][ch]) begin
                        dequant_atomic_accepted_req_count[sid]++;
                        if (
                            dequant_atomic_transfer_pending[sid][ch].size() == 0 ||
                            dequant_atomic_linear_pending[sid][ch].size() == 0
                        ) begin
                            $fdisplay(
                                dequant_atomic_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d missing_pre_remap_address=1",
                                $time, dequant_atomic_probe_cycle, sid
                            );
                        end else begin
                            dequant_atomic_transfer_wdata[sid][ch].push_back(
                                dequant_atomic_transfer_pending[sid][ch].pop_front()
                            );
                            dequant_atomic_linear_wdata[sid][ch].push_back(
                                dequant_atomic_linear_pending[sid][ch].pop_front()
                            );
                            dequant_atomic_post_wdata[sid][ch].push_back(
                                return_obs_mse4_local_req_addr_mon[0][sid][ch]
                            );
                            $fdisplay(
                                dequant_atomic_probe_fd[sid],
                                "%0t | MSE4_REQ | cycle=%0d slice=%0d local_stage=0 ch=%0d accepted=1 transfer_addr=0x%0h linear_addr=0x%0h post_remap_addr=0x%0h",
                                $time, dequant_atomic_probe_cycle, sid, ch,
                                dequant_atomic_transfer_wdata[sid][ch][$],
                                dequant_atomic_linear_wdata[sid][ch][$],
                                dequant_atomic_post_wdata[sid][ch][$]
                            );
                        end
                    end
                    if (local_wdata_hs[0][sid][4][ch]) begin
                        dequant_atomic_accepted_wdata_count[sid]++;
                        if (
                            dequant_atomic_transfer_wdata[sid][ch].size() == 0 ||
                            dequant_atomic_linear_wdata[sid][ch].size() == 0 ||
                            dequant_atomic_post_wdata[sid][ch].size() == 0
                        ) begin
                            dequant_atomic_unpaired_data_count[sid]++;
                            $fdisplay(
                                dequant_atomic_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d accepted_wdata_without_address=1",
                                $time, dequant_atomic_probe_cycle, sid
                            );
                        end else begin
                            logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] transfer_addr;
                            logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] linear_addr;
                            logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] post_addr;
                            transfer_addr =
                                dequant_atomic_transfer_wdata[sid][ch].pop_front();
                            linear_addr =
                                dequant_atomic_linear_wdata[sid][ch].pop_front();
                            post_addr =
                                dequant_atomic_post_wdata[sid][ch].pop_front();
                            dequant_atomic_accepted_write_count[sid]++;
                            $fdisplay(
                                dequant_atomic_probe_fd[sid],
                                "%0t | MSE4_WRITE | cycle=%0d slice=%0d local_stage=0 role=dequantize ch=%0d accepted=1 valid=1 ready=1 strobe=0xffff transfer_addr=0x%0h linear_addr=0x%0h post_remap_addr=0x%0h data=0x%032h",
                                $time, dequant_atomic_probe_cycle, sid, ch,
                                transfer_addr, linear_addr, post_addr,
                                return_obs_mse4_local_wdata_mon[0][sid][ch]
                            );
                        end
                    end
                end
                if (return_obs_slice_finish_mon[0][sid] &&
                    !dequant_atomic_probe_finish_d[sid]) begin
                    integer outstanding_addr_count;
                    integer outstanding_data_count;
                    outstanding_addr_count = 0;
                    outstanding_data_count =
                        dequant_atomic_unpaired_data_count[sid];
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                        outstanding_addr_count +=
                            dequant_atomic_transfer_pending[sid][ch].size();
                        outstanding_addr_count +=
                            dequant_atomic_transfer_wdata[sid][ch].size();
                        if (
                            dequant_atomic_transfer_pending[sid][ch].size() !=
                            dequant_atomic_linear_pending[sid][ch].size()
                        )
                            $fdisplay(
                                dequant_atomic_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d pending_address_domain_queue_mismatch=1",
                                $time, dequant_atomic_probe_cycle, sid
                            );
                        if (
                            dequant_atomic_transfer_wdata[sid][ch].size() !=
                                dequant_atomic_linear_wdata[sid][ch].size() ||
                            dequant_atomic_transfer_wdata[sid][ch].size() !=
                                dequant_atomic_post_wdata[sid][ch].size()
                        )
                            $fdisplay(
                                dequant_atomic_probe_fd[sid],
                                "%0t | PROBE_ERROR | cycle=%0d slice=%0d accepted_address_domain_queue_mismatch=1",
                                $time, dequant_atomic_probe_cycle, sid
                            );
                    end
                    $fdisplay(
                        dequant_atomic_probe_fd[sid],
                        "%0t | STAGE_FINISH | cycle=%0d slice=%0d local_stage=0 accepted_req_count=%0d accepted_wdata_count=%0d accepted_write_count=%0d outstanding_addr_count=%0d outstanding_data_count=%0d",
                        $time, dequant_atomic_probe_cycle, sid,
                        dequant_atomic_accepted_req_count[sid],
                        dequant_atomic_accepted_wdata_count[sid],
                        dequant_atomic_accepted_write_count[sid],
                        outstanding_addr_count, outstanding_data_count
                    );
                    $fflush(dequant_atomic_probe_fd[sid]);
                end
                dequant_atomic_probe_exec_d[sid] =
                    return_obs_sem_exec_start_mon[0][sid];
                dequant_atomic_probe_finish_d[sid] =
                    return_obs_slice_finish_mon[0][sid];
            end
        end
    end

    final begin : dequant_atomic_probe_final
        for (int sid = 0; sid < 2; sid++)
            if (dequant_atomic_probe_fd[sid] != 0)
                $fclose(dequant_atomic_probe_fd[sid]);
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
runtime_tool="${{package_root}}/package_tools/dequant_atomic_server_runtime.py"
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
  command -v "${{command_name}}" >/dev/null 2>&1 || exit 3
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
    if [ "${{restore_status}}" -eq 0 ]; then probe_installed=0; fi
    return "${{restore_status}}"
  fi
  return 0
}}

finalize_return() {{
  original_status="$1"
  if [ "${{finalization_started}}" -eq 1 ]; then exit "${{original_status}}"; fi
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
     [ -f "${{evidence_root}}/server_identity_post_restore.json" ]; then
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
if [ "${{restore_status}}" -ne 0 ]; then run_status="${{restore_status}}"; exit "${{run_status}}"; fi
python3 "${{common_tool}}" capture-identity \
  --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" \
  --install-name "${{install_name}}" --phase post_compile \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_compile.json" >/dev/null
post_compile_status=$?
if [ "${{compile_status}}" -eq 0 ] && [ "${{post_compile_status}}" -eq 0 ]; then
  (
    cd "${{run_dir}}"
    timeout --foreground --signal=TERM --kill-after=30s 4h \
      ./sim_results/simv \
      -l sim_results/sim.log \
      +vcs+lic+wait \
      +DEQUANT_ATOMIC_PROBE \
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
    return f"""# Dequant node0077 atomic single-stage stock-RTL diagnostic v3

解压后只运行一条命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

该包在两个物理 slice（0、1）上执行一次 CWH16 Dequant stage，仅用于
FIRST_DYNAMIC 原子诊断，不计 node0077 E4/E5。v2 已把
`GROUP2.ROW_LC.end` 从 1 修正为 4，并从该配置重新生成
planner、mapping、bitstream、execplan、SCA 与 SCA_D。v3 不再改变
这些冻结语义资产，只把 observer 的深层 XMR 改为 genvar 静态代理。

包内没有 `rtl/` 文件，也不修改功能 RTL。只读 observer 仅事务式追加到
既有 `native_return_observer.svh` include hook，编译后立即逐字节恢复。

通过条件包括：两片自然 Start/Finish；每片 4/4 accepted MSE4 写入；
finish 时地址与数据 outstanding 都为 0；两片各 4 行正式 D 回读均非 x
且与 golden bit-exact。回传文件为：

`{INSTALL_NAME}_return.zip` 与 `{INSTALL_NAME}_return.zip.sha256`。
"""


def _copy_native(native: dict[str, Any], package: Path, double: dict[str, Any]) -> dict[str, Any]:
    output = native["output"]
    runtime = package / "workload/runtime"
    payloads = runtime / "payloads"
    _copy_lf(output / "install/execplan.txt", payloads / "execplan.txt")
    for source in sorted((output / "install/cfg_pkg").glob("*")):
        if source.is_file():
            _copy_lf(source, payloads / "cfg_pkg" / source.name)
    for slice_id in (0, 1):
        _copy_lf(
            SOURCE_ROOT / f"input_slice{slice_id:02d}_128b.txt",
            payloads / f"inputs/slice{slice_id:02d}/matrix_A_linearized_128bit.txt",
        )
        _copy_lf(
            SOURCE_ROOT / f"golden_slice{slice_id:02d}_128b.txt",
            package / f"golden/slice{slice_id:02d}_128b.txt",
        )
    sca = _rewrite_sca(json.loads((output / "sca_cfg.json").read_text(encoding="utf-8")))
    sca_d = _rewrite_sca_d(
        json.loads((output / "sca_cfg_D.json").read_text(encoding="utf-8"))
    )
    _write_json(runtime / "sca_cfg.json", sca)
    _write_json(runtime / "sca_cfg_D.json", sca_d)

    validation = package / "validation"
    _write_json(validation / "native_double_rebuild.json", double)
    _write_json(validation / "planner_transport_adapter_receipt.json", native["adapter"])
    _write_json(validation / "planner_typed_graph.json", native["graph"])
    for name in (
        "config.json",
        "typed_graph.json",
        "manifest.json",
        "generation_receipt.json",
        "expected_mse4_writes.json",
        "lifecycle_contract.json",
        "coverage_contract.json",
        "derivation_provenance.json",
    ):
        _copy_lf(SOURCE_ROOT / name, validation / name)
    _copy_lf(CONTRACT, validation / "semantic_contract.json")
    _copy_lf(LOCAL_REPORT, validation / "local_contract_report.json")
    _copy_lf(FULL_V6_CONFIG, validation / "upstream/full_v6_config.json")
    _copy_lf(
        FULL_V6_E2_REPORT,
        validation / "upstream/full_v6_local_e2_report.json",
    )
    _copy_lf(
        V1_ANALYSIS_REPORT,
        validation / "history/atomic_v1_return_analysis.json",
    )
    _copy_lf(
        V1_ANALYSIS_RECORD,
        validation / "history/atomic_v1_return_analysis.md",
    )
    _write_json(
        validation / "address_domain_contract.json",
        {
            "schema": "dequant-atomic-address-domain-contract-v2",
            "linear_expected_field": "word_address_128b",
            "linear_observed_field": "linear_addr",
            "linear_observed_rtl": (
                "WR_Memory_AG.transfer_addr_nooff plus "
                "mse_stream_base_addr>>DDR_ADDR_OFFSET_WIDTH"
            ),
            "transfer_offset_observed_field": "transfer_addr",
            "post_remap_observed_field": "post_remap_addr",
            "post_remap_observed_rtl": "accepted local_req_addr",
            "remap_rtl": "WR_Memory_AG.sv:302-351",
            "direct_cross_domain_comparison_forbidden": True,
        },
    )
    _write_json(
        validation / "v1_to_v2_config_fix_receipt.json",
        {
            "schema": "dequant-atomic-v1-to-v2-config-fix-v1",
            "first_divergence": (
                "DEQUANT_CONFIG_D_BUFFER_ROW_UNDERSUPPLY_EARLY_LAST"
            ),
            "owner": "CONFIG_SEMANTICS",
            "only_config_diff": {
                "path": "buffer_loop_configs.GROUP2.ROW_LC.end",
                "old": 1,
                "new": 4,
            },
            "d_transaction_bytes": 64,
            "buffer_row_bytes": 16,
            "required_row_count": 4,
            "full_rebuild_required": True,
            "functional_rtl_modified": False,
        },
    )
    for target, source in (
        ("addressed_graph.json", native["required"]["addressed_graph"]),
        ("address_bound_config.json", native["required"]["addressed_config"]),
        ("mapping_review.json", native["required"]["mapping"]),
        ("parsed_bitstream.txt", native["required"]["parsed_bitstream"]),
        ("detailed_dump.txt", native["required"]["detailed_dump"]),
        ("instructions_explained.txt", native["required"]["explanation"]),
    ):
        _copy_lf(source, validation / "native" / target)
    return {
        "execplan_128b_line_count": len(
            (payloads / "execplan.txt").read_text(encoding="ascii").splitlines()
        ),
        "sca_preload_count": 4,
        "sca_d_readback_count": 2,
        "accepted_mse4_write_count": 8,
        "native_operator_count": 1,
    }


def _write_deterministic_zip(package: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def _zip_tree(package: Path) -> tuple[Path, str]:
    zip_path = package.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    _write_deterministic_zip(package, zip_path)
    digest = _sha256(zip_path)
    zip_path.with_suffix(".zip.sha256").write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return zip_path, digest


def _audit_zip(package: Path, zip_path: Path) -> dict[str, Any]:
    expected = {
        f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}": path.read_bytes()
        for path in sorted(item for item in package.rglob("*") if item.is_file())
    }
    with zipfile.ZipFile(zip_path) as archive:
        if archive.namelist() != list(expected):
            raise AtomicDequantPackageError("ZIP exact set/order differs")
        for name, payload in expected.items():
            if archive.read(name) != payload:
                raise AtomicDequantPackageError(f"ZIP payload differs: {name}")
    return {"entry_count": len(expected), "exact_set": True, "payloads_byte_exact": True}


def _build_tree(package: Path, source_identities: dict[str, Any]) -> dict[str, Any]:
    package.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="dq-at-native-") as temporary:
        native, double = _double_native(Path(temporary))
        native_receipt = _copy_native(native, package, double)
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script())
    _write_lf(package / "README.md", _readme())
    _copy_lf(
        ROOT / "tools/dequant_atomic_server_runtime.py",
        package / "package_tools/dequant_atomic_server_runtime.py",
    )
    _copy_lf(
        ROOT / "tools/requant_node0001_server_runtime.py",
        package / "package_tools/requant_node0001_server_runtime.py",
    )
    _write_lf(
        package / "tb_probe/requant_mse4_guard_observer_tail.svh",
        _observer_tail().lstrip(),
    )
    _write_json(
        package / "validation/semantic_freeze_v2_to_v3.json",
        _semantic_freeze_receipt(package),
    )
    _write_json(
        package / "validation/xmr_observer_rebuild_provenance.json",
        {
            "schema": "dequant-atomic-xmr-observer-rebuild-v1",
            "status": "infrastructure_only",
            "predecessor_install_name": PREDECESSOR_PACKAGE.name,
            "predecessor_failure_class": (
                "SERVER_TEST_INFRASTRUCTURE_OBSERVER_"
                "XMR_ELABORATION_FAILURE"
            ),
            "predecessor_simulation_started": False,
            "predecessor_counts_as_dynamic_attempt": False,
            "semantic_change": False,
            "generated_instance_indices": "literal_or_genvar_only",
            "procedural_indices_scope": "local_proxy_signal_arrays_only",
        },
    )
    files = _records(package)
    manifest = {
        "schema": SCHEMA,
        "package_name": package.name,
        "install_name": INSTALL_NAME,
        "target": "r5:hwop-0077-00 DequantizeLinear atomic",
        "run_kind": "FIRST_DYNAMIC_DIAGNOSTIC",
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "counts_as_node0077_e4": False,
        "counts_as_node0077_e5": False,
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "evidence_level_before_run": "E2_LOCAL_CONTRACT_ONLY",
        "server_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "source_identities": source_identities,
        "native_rebuild": native_receipt,
        "execution_contract": {
            "logical_occurrence_count": 1,
            "physical_slice_instances": [0, 1],
            "slice_mask": "0b0000000000000000000000000011",
            "stage_count": 1,
            "repeat_num": 1,
            "start_comp_count": 1,
            "a_preload_count": 2,
            "formal_readback_count": 2,
            "accepted_mse4_write_count": 8,
            "accepted_mse4_write_count_per_slice": 4,
            "a_base": "0x00000000",
            "d_base": "0x00000010",
            "group2_row_lc_end": 4,
            "finish_requires": {
                "accepted_mse4_write_count_per_slice": 4,
                "accepted_request_count_per_slice": 4,
                "accepted_wdata_count_per_slice": 4,
                "outstanding_address_count": 0,
                "outstanding_data_count": 0,
                "formal_d_lines_per_slice": 4,
                "formal_d_unknown_lines": 0,
                "formal_d_bit_exact": True,
            },
        },
        "validator_repairs": {
            "observer_address_domain": {
                "expected_compared_to": "pre-remap linear address",
                "post_remap_request_address_retained_separately": True,
                "cross_domain_direct_comparison_forbidden": True,
            },
            "observer_xmr_elaboration": {
                "generated_instance_index": "literal_or_genvar_only",
                "procedural_indexing": "local_proxy_signal_arrays_only",
                "compiler_switch_workaround": False,
            },
            "stock_identity": {
                "status_string_is_a_gate": False,
                "functional_rtl_unchanged_boolean_required": True,
                "probe_restored_boolean_required": True,
                "focused_and_support_booleans_required": True,
            },
        },
        "rtl_policy": {
            "functional_rtl_modified": False,
            "rtl_directory_write_allowed": False,
            "rtl_patch_included": False,
            "tb_top_modification_allowed": False,
            "force_or_deposit_allowed": False,
            "internal_tb_timeout_changed": False,
            "read_only_observer_included": True,
            "observer_install_target": "native_return_observer.svh",
            "observer_transactional_restore_required": True,
        },
        "bootstrap_policy": {
            "shell_python_no_bytecode_export": True,
            "runtime_sets_sys_dont_write_bytecode_before_local_import": True,
            "pyc_or_pycache_ignored": False,
            "fresh_zip_extract_runtime_preflight_required": True,
        },
        "return_policy": {
            "allowlist_only": True,
            "direct_zip_and_sidecar": True,
            "waveforms": False,
            "build_tree": False,
            "nested_archives": False,
            "return_zip_limit_bytes": 2 * 1024 * 1024,
        },
        "rule_ids": list(RULE_IDS),
        "release_gate": {
            "formal_e4_or_e5_gate": False,
            "remaining_blocker": "B_DEQUANT_SERVER_E4_E5",
            "candidate_release": False,
        },
        "files": files,
        "payload_tree_sha256": _tree_sha256(files),
    }
    _write_json(package / MANIFEST_NAME, manifest)
    preflight = preflight_package(package, INSTALL_NAME)
    return {"manifest": manifest, "preflight": preflight}


def _validate_bootstrap_immutability(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="dq-at-bootstrap-") as temporary:
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
                / "package_tools/dequant_atomic_server_runtime.py"
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
            raise AtomicDequantPackageError(
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
            raise AtomicDequantPackageError(
                "fresh-extracted package tree changed during runtime bootstrap: "
                f"{differing[:8]}"
            )
        forbidden = [
            relative
            for relative in after
            if "__pycache__" in {
                part.lower() for part in relative.split("/")
            }
            or Path(*relative.split("/")).suffix.lower() in {".pyc", ".pyo"}
        ]
        if forbidden:
            raise AtomicDequantPackageError(
                f"runtime bootstrap materialized Python bytecode: {forbidden[:4]}"
            )
        runtime_report = json.loads(output.read_text(encoding="utf-8"))
        if runtime_report.get("status") != "package_preflight_passed":
            raise AtomicDequantPackageError(
                "fresh-extracted runtime did not pass package preflight"
            )
        return {
            "schema": "dequant-atomic-bootstrap-immutability-receipt-v1",
            "rule_id": "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "status": "pass",
            "entry": (
                "package_tools/dequant_atomic_server_runtime.py "
                "preflight-package"
            ),
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


def _validate_probe_transaction(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="dq-at-probe-install-") as temporary:
        root = Path(temporary)
        extract_root = root / "extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        fresh_package = extract_root / INSTALL_NAME
        package_before = _records(fresh_package)
        ndp_root = root / "NDP_copy_mock"
        evidence = root / "evidence"
        ndp_root.mkdir()
        evidence.mkdir()
        observer = ndp_root / "native_return_observer.svh"
        shutil.copyfile(ROOT / "NDP_copy01/native_return_observer.svh", observer)
        observer_preimage = observer.read_bytes()
        common_tool = (
            fresh_package
            / "package_tools/requant_node0001_server_runtime.py"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"

        def run(*arguments: str) -> subprocess.CompletedProcess[str]:
            completed = subprocess.run(
                [sys.executable, str(common_tool), *arguments],
                cwd=fresh_package,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                raise AtomicDequantPackageError(
                    "fresh-extracted probe transaction failed: "
                    f"{' '.join(arguments[:1])}: {completed.stderr.strip()}"
                )
            return completed

        run(
            "install-probe",
            "--ndp-root",
            str(ndp_root),
            "--package-root",
            str(fresh_package),
            "--evidence-root",
            str(evidence),
        )
        install_receipt = json.loads(
            (evidence / "tb_probe_install_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        installed_sha256 = _sha256(observer)
        run(
            "verify-probe-installed",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
            "--output",
            str(evidence / "tb_probe_precompile_receipt.json"),
        )
        verify_receipt = json.loads(
            (evidence / "tb_probe_precompile_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        run(
            "restore-probe",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
        )
        if observer.read_bytes() != observer_preimage:
            raise AtomicDequantPackageError(
                "probe transaction did not restore observer byte-exact"
            )
        final_receipt = json.loads(
            (evidence / "tb_probe_install_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        package_after = _records(fresh_package)
        if package_before != package_after:
            raise AtomicDequantPackageError(
                "probe transaction changed the fresh-extracted package tree"
            )
        return {
            "schema": "dequant-atomic-probe-transaction-receipt-v2",
            "status": "pass",
            "fresh_zip_extraction": True,
            "installed_probe_sha256": installed_sha256,
            "preimage_sha256": _sha256_bytes(observer_preimage),
            "install_receipt_status": install_receipt.get("status"),
            "final_receipt_status": final_receipt.get("status"),
            "verified_immediately_before_compile": True,
            "xmr_elaboration_gate": verify_receipt["xmr_elaboration_gate"],
            "restored_byte_exact": True,
            "package_tree_unchanged": True,
            "package_tree_sha256_before": _tree_sha256(package_before),
            "package_tree_sha256_after": _tree_sha256(package_after),
        }


def build_package(output: Path) -> dict[str, Any]:
    package = output.resolve()
    if package.name != INSTALL_NAME:
        raise AtomicDequantPackageError(
            f"output directory name must preserve ZIP identity: {INSTALL_NAME}"
        )
    zip_path = package.with_suffix(".zip")
    sidecar = zip_path.with_suffix(".zip.sha256")
    for target in (package, zip_path, sidecar):
        if target.exists():
            raise AtomicDequantPackageError(f"fresh output required: {target}")
    source_identities = _verify_sources()
    with tempfile.TemporaryDirectory(
        prefix="dq-at-pkg-a-"
    ) as left_parent, tempfile.TemporaryDirectory(
        prefix="dq-at-pkg-b-"
    ) as right_parent:
        left = Path(left_parent) / INSTALL_NAME
        right = Path(right_parent) / INSTALL_NAME
        left_build = _build_tree(left, source_identities)
        right_build = _build_tree(right, source_identities)
        left_zip, left_digest = _zip_tree(left)
        right_zip, right_digest = _zip_tree(right)
        if (
            left_digest != right_digest
            or left_zip.read_bytes() != right_zip.read_bytes()
            or _records(left) != _records(right)
        ):
            raise AtomicDequantPackageError(
                "two fresh package builds are not byte-identical"
            )
        shutil.copytree(right, package)
        shutil.copyfile(right_zip, zip_path)
        shutil.copyfile(right_zip.with_suffix(".zip.sha256"), sidecar)
    validation = validate_package(package)
    return {
        "schema": SCHEMA,
        "status": "built",
        "directory": package.as_posix(),
        "manifest_sha256": _sha256(package / MANIFEST_NAME),
        "payload_tree_sha256": left_build["manifest"]["payload_tree_sha256"],
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": right_digest,
        "sidecar": sidecar.as_posix(),
        "server_command": left_build["manifest"]["server_command"],
        "preflight": validation["preflight"],
        "bootstrap_immutability": validation["bootstrap_immutability"],
        "probe_transaction": validation["probe_transaction"],
        "deterministic_package_build_count": 2,
        "deterministic_zip_byte_identical": True,
        "release_gate": {
            "candidate_release": False,
            "counts_as_node0077_e4": False,
            "counts_as_node0077_e5": False,
            "remaining_blocker": "B_DEQUANT_SERVER_E4_E5",
        },
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
    }


def validate_package(output: Path) -> dict[str, Any]:
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sidecar = Path(f"{zip_path}.sha256")
    manifest = json.loads((package / MANIFEST_NAME).read_text(encoding="utf-8"))
    records = _records(package, exclude_manifest=True)
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("install_name") != INSTALL_NAME
        or manifest.get("files") != records
        or manifest.get("payload_tree_sha256") != _tree_sha256(records)
    ):
        raise AtomicDequantPackageError("manifest exact-set identity differs")
    script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    export_at = script.find("export PYTHONDONTWRITEBYTECODE=1")
    first_python = script.find("python3 ")
    if export_at < 0 or first_python < 0 or export_at > first_python:
        raise AtomicDequantPackageError("no-bytecode export does not precede Python")
    for token in (
        "+DEQUANT_ATOMIC_PROBE",
        "DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0",
        "+SCA_CFG=../install/cfg_pkg/${install_name}/sca_cfg.json",
        "+SCA_CFG_D=../install/cfg_pkg/${install_name}/sca_cfg_D.json",
    ):
        if token not in script:
            raise AtomicDequantPackageError(f"runner token missing: {token}")
    preflight = preflight_package(package, INSTALL_NAME)
    digest = _sha256(zip_path)
    if sidecar.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise AtomicDequantPackageError("ZIP sidecar differs")
    return {
        "schema": SCHEMA,
        "status": "validated",
        "manifest_sha256": _sha256(package / MANIFEST_NAME),
        "payload_tree_sha256": _tree_sha256(records),
        "zip_sha256": digest,
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_audit": _audit_zip(package, zip_path),
        "preflight": preflight,
        "bootstrap_immutability": _validate_bootstrap_immutability(package),
        "probe_transaction": _validate_probe_transaction(package),
        "server_command": manifest["server_command"],
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report = validate_package(output) if args.validate_only else build_package(output)
    except Exception as exc:
        print(f"Dequant atomic package failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
