"""Fail-closed evidence for the first node0075 materializer blocking leaf.

This module does not emit a node0075 target, replay a tensor, or modify RTL.
It rechecks the current RTL source identity, the focused compile failure, and
the frozen W3 node0075 accumulator/tail observations recorded by the owner.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from .exact_uint8_quant_tail_capability import (
    one_round_fused_magic,
    sequential_multiplier_tail,
)
from .stage_operator_semantics_audit import ga_int32_to_fp32_rtl_result


SCHEMA = "resnet50-node0075-materializer-blocking-leaf-v1"
REPORT_SCHEMA = "resnet50-node0075-materializer-blocking-leaf-report-v1"
TEST_ID = "r5-node0075-materializer-blocking-leaf-v1"

CONTROL_PATH = Path(
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/"
    "SA_PE_Float_Control.v"
)
CONTROL_SHA256 = (
    "c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b"
)
CONTROL_LINE = 50
CONTROL_LINE_TEXT = "    output[1:0]         o_Config,"

ACCUMULATOR_PATH = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0075-accumulate.npy"
)
ACCUMULATOR_SHA256 = (
    "ee8422fe7c20f0cc40adb18abcd0b8b0f9c433a6c2283e8c87262e3a7d419ec3"
)
D_PATH = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-6cc774b369e8dea4.npy"
)
D_SHA256 = "10d974cdab69904bfd3ed7749059e26e16388ba784872f0d432cd2ba14bcbdc8"
MULTIPLIER_BITS = 0x3A510DB3
OUTPUT_ZERO_POINT = 60


class Node0075BlockingLeafError(RuntimeError):
    """Raised when the fail-closed receipt no longer matches current disk."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _f32_bits(value: np.float32) -> int:
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def _resolve_iverilog() -> str:
    candidate = shutil.which("iverilog")
    if candidate:
        return candidate
    windows_default = Path(r"C:\iverilog\bin\iverilog.exe")
    if windows_default.is_file():
        return str(windows_default)
    raise Node0075BlockingLeafError("iverilog is unavailable for focused probe")


def _focused_compile_probe(root: Path) -> dict[str, Any]:
    source = root / CONTROL_PATH
    with tempfile.TemporaryDirectory(prefix="node0075-control-probe-") as temp_dir:
        output = Path(temp_dir) / "control.vvp"
        process = subprocess.run(
            [
                _resolve_iverilog(),
                "-g2012",
                "-s",
                "SA_PE_Float_Control",
                "-o",
                str(output),
                str(source),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    combined = "\n".join(
        value.strip() for value in (process.stdout, process.stderr) if value.strip()
    )
    expected_fragment = "Superfluous comma in port declaration list"
    return {
        "tool": "iverilog",
        "language": "SystemVerilog-2012",
        "top": "SA_PE_Float_Control",
        "exit_code": process.returncode,
        "expected_error_fragment": expected_fragment,
        "expected_error_observed": expected_fragment in combined,
    }


def _frozen_instance_observation(root: Path) -> dict[str, Any]:
    accumulator_path = root / ACCUMULATOR_PATH
    d_path = root / D_PATH
    if _sha256(accumulator_path) != ACCUMULATOR_SHA256:
        raise Node0075BlockingLeafError("node0075 accumulator identity changed")
    if _sha256(d_path) != D_SHA256:
        raise Node0075BlockingLeafError("node0075 D identity changed")

    accumulator = np.load(accumulator_path, allow_pickle=False)
    expected_d = np.load(d_path, allow_pickle=False)
    if accumulator.shape != (16, 1000) or accumulator.dtype != np.int32:
        raise Node0075BlockingLeafError("node0075 accumulator type/shape changed")
    if expected_d.shape != (16, 1000) or expected_d.dtype != np.uint8:
        raise Node0075BlockingLeafError("node0075 D type/shape changed")

    values = accumulator.reshape(-1)
    golden = expected_d.reshape(-1)
    multiplier = np.asarray(MULTIPLIER_BITS, dtype=np.uint32).view(np.float32)

    ingress_mismatches = 0
    sequential = np.empty(values.size, dtype=np.uint8)
    fused = np.empty(values.size, dtype=np.uint8)
    for index, raw in enumerate(values):
        value = int(raw)
        expected_fp32_bits = _f32_bits(np.float32(value))
        if ga_int32_to_fp32_rtl_result(value) != expected_fp32_bits:
            ingress_mismatches += 1
        sequential[index] = sequential_multiplier_tail(
            np.float32(value), multiplier, OUTPUT_ZERO_POINT
        )
        fused[index] = one_round_fused_magic(
            np.float32(value), multiplier, OUTPUT_ZERO_POINT
        )

    return {
        "accumulator": {
            "path": ACCUMULATOR_PATH.as_posix(),
            "sha256": ACCUMULATOR_SHA256,
            "shape": [16, 1000],
            "dtype": "int32",
            "element_count": int(values.size),
            "unique_value_count": int(np.unique(values).size),
            "minimum": int(values.min()),
            "maximum": int(values.max()),
            "negative_count": int(np.count_nonzero(values < 0)),
            "zero_count": int(np.count_nonzero(values == 0)),
            "positive_count": int(np.count_nonzero(values > 0)),
            "rows_with_negative": int(np.count_nonzero(np.any(accumulator < 0, axis=1))),
        },
        "current_ga_int32tofp32_model": {
            "source_scope": "frozen W3 node0075 values only",
            "element_mismatch_count": ingress_mismatches,
            "general_signed_domain_closed": False,
        },
        "requant_tail": {
            "multiplier_bits": f"0x{MULTIPLIER_BITS:08x}",
            "output_zero_point": OUTPUT_ZERO_POINT,
            "sequential_vs_frozen_d_mismatch_count": int(
                np.count_nonzero(sequential != golden)
            ),
            "one_round_fused_vs_frozen_d_mismatch_count": int(
                np.count_nonzero(fused != golden)
            ),
            "one_round_fused_vs_sequential_mismatch_count": int(
                np.count_nonzero(fused != sequential)
            ),
            "frozen_d": {
                "path": D_PATH.as_posix(),
                "sha256": D_SHA256,
                "shape": [16, 1000],
                "dtype": "uint8",
                "minimum": int(golden.min()),
                "maximum": int(golden.max()),
            },
            "general_exact_uint8_tail_closed": False,
        },
    }


def build_dynamic_evidence(root: Path) -> dict[str, Any]:
    root = root.resolve()
    control = root / CONTROL_PATH
    actual_control_sha = _sha256(control)
    if actual_control_sha != CONTROL_SHA256:
        raise Node0075BlockingLeafError(
            "SA_PE_Float_Control identity changed: "
            f"expected={CONTROL_SHA256} actual={actual_control_sha}"
        )
    source_lines = control.read_text(encoding="utf-8").splitlines()
    if source_lines[CONTROL_LINE - 1].rstrip() != CONTROL_LINE_TEXT:
        raise Node0075BlockingLeafError("focused compile leaf source line changed")

    compile_probe = _focused_compile_probe(root)
    if compile_probe["exit_code"] != 1 or not compile_probe["expected_error_observed"]:
        raise Node0075BlockingLeafError("focused compile leaf no longer reproduces")

    return {
        "first_blocking_leaf": {
            "id": "SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA",
            "classification": "CURRENT_ACTIVE_RTL_COMPILE_STOP",
            "config_expressibility": "NOT_EXPRESSIBLE_BY_NODE0075_NON_RTL_ASSETS",
            "path": CONTROL_PATH.as_posix(),
            "sha256": CONTROL_SHA256,
            "line": CONTROL_LINE,
            "source_text_trimmed": CONTROL_LINE_TEXT.strip(),
            "focused_compile_probe": compile_probe,
            "required_next_authority": "RTL owner",
            "minimum_fix_direction": "remove only the comma after final o_Config port",
        },
        "frozen_instance_observation": _frozen_instance_observation(root),
        "reload_accounting": {
            "capacity_formula": "ceil(1000/(16*8))",
            "authorized_minimum_passes": 8,
            "actual_materialized_passes": 0,
            "actual_accepted_32byte_read_occurrences": 0,
            "actual_accepted_traffic_bytes": 0,
            "actual_unique_consumer_accepted_bytes": 0,
            "frozen_producer_owned_unique_storage_bytes": 32768,
            "if_unblocked_exactly_8_passes": {
                "accepted_32byte_reads_per_slice": 512,
                "accepted_32byte_read_occurrences": 8192,
                "accepted_traffic_bytes": 262144,
                "unique_storage_bytes": 32768,
            },
            "reason_actual_is_zero": (
                "fail-closed stop precedes target/handler/materializer emission; "
                "producer bases are not consumer acceptance evidence"
            ),
        },
        "decision": {
            "status": "TERMINATED_AT_FIRST_NONEXPRESSIBLE_HARDWARE_LEAF",
            "target_json_generated": False,
            "handler_or_registry_modified": False,
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_or_sca_generated": False,
            "config_bound_e2": "NOT_RUN",
            "package_release": "NONE",
            "server_accessed": False,
            "functional_rtl_modified": False,
        },
    }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def validate_report(root: Path, report: dict[str, Any]) -> dict[str, Any]:
    if report.get("schema") != REPORT_SCHEMA or report.get("test_id") != TEST_ID:
        raise Node0075BlockingLeafError("report schema/test id changed")
    current = build_dynamic_evidence(root)
    if report.get("dynamic_evidence") != current:
        raise Node0075BlockingLeafError("recorded dynamic evidence changed")
    if report.get("package_release") != "NONE":
        raise Node0075BlockingLeafError("blocked report must not release a package")
    return {
        "schema": REPORT_SCHEMA,
        "test_id": TEST_ID,
        "status": "PASS_FAIL_CLOSED",
        "first_blocking_leaf": current["first_blocking_leaf"]["id"],
        "actual_materialized_passes": current["reload_accounting"][
            "actual_materialized_passes"
        ],
        "actual_accepted_traffic_bytes": current["reload_accounting"][
            "actual_accepted_traffic_bytes"
        ],
        "package_release": "NONE",
    }

