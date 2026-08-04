#!/usr/bin/env python3
"""Independently validate and reproduce the node0075 df23e4d E2 materialization."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NDP = ROOT / "ndp-sim"
TEST_ID = "r5-node0075-df23e4d-eight-pass-materializer-v1"
REPORT_ROOT = ROOT / "artifacts/operator_config_validation" / TEST_ID
REPORT = REPORT_ROOT / "materializer_report.json"
TARGET = REPORT_ROOT / "node0075_df23e4d_eight_pass_target.json"
OUTPUT = NDP / "model_execplan/output/node0075_df23e4d_eight_pass_target"
VALIDATION = REPORT_ROOT / "determinism_and_config_binding_validation.json"
ACTIVE_CSA = (
    NDP.parent
    / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_CSA.v"
)
ARITHMETIC_REPORT = (
    ROOT
    / "outputs/node0075_negative_psum_df23e4d_revalidation/"
    "current_rtl_and_recurrence.json"
)
EXPECTED_CSA_SHA256 = "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
EXPECTED_SLICE0_ORDERED_SHA256 = (
    "4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d"
)
EXPECTED_SLICE0_BYTE_SET_SHA256 = (
    "3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06"
)


class ValidationError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _fail_unless(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _inventory_paths() -> list[Path]:
    report = _json(REPORT)
    sca = _json(OUTPUT / "sca_cfg.json")
    paths = [
        REPORT,
        TARGET,
        REPORT_ROOT / "normalized_target.json",
        REPORT_ROOT / "pipeline.stdout.log",
        REPORT_ROOT / "pipeline.stderr.log",
        OUTPUT / "install/execplan.txt",
        OUTPUT / "instructions_explained.txt",
        OUTPUT / "sca_cfg.json",
        OUTPUT / "sca_cfg_D.json",
        OUTPUT / "node0075_df23e4d_eight_pass_target_withbaseaddr.json",
    ]
    paths.extend(ROOT / item["path"] for item in report["templates"])
    paths.extend(sorted((OUTPUT / "jsons").glob("*.json")))
    paths.extend(sorted((OUTPUT / "config").glob("*/mapping_review.json")))
    paths.extend(sorted((OUTPUT / "config").glob("*/*bitstream_128b.bin")))
    paths.extend(sorted((OUTPUT / "config").glob("*/*bitstream_64b.bin")))
    for value in sca.values():
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            candidate = OUTPUT / value["path"]
            if candidate.is_file():
                paths.append(candidate)
    unique = sorted(set(paths), key=lambda path: path.as_posix())
    _fail_unless(all(path.is_file() for path in unique), "inventory contains a missing file")
    return unique


def _inventory() -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(ROOT).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in _inventory_paths()
    }


def _validate_static_binding() -> dict[str, Any]:
    report = _json(REPORT)
    target = _json(TARGET)
    arithmetic = _json(ARITHMETIC_REPORT)
    _fail_unless(_sha256(ACTIVE_CSA) == EXPECTED_CSA_SHA256, "active CSA identity drift")
    _fail_unless(
        arithmetic.get("status") == "BLOCKER_CLOSED_CURRENT_RTL_FULL_REACHABLE_PASS",
        "full recurrence closure is absent",
    )
    _fail_unless(report.get("status") == "CONFIG_BOUND_LOCAL_E2_PASS", "E2 report failed")
    e2 = report["local_e2"]
    _fail_unless(e2.get("passed") is True, "local E2 did not pass")
    _fail_unless(e2.get("accumulator_mismatch_count") == 0, "accumulator mismatch")
    _fail_unless(e2.get("uint8_d_mismatch_count") == 0, "uint8 D mismatch")
    _fail_unless(e2.get("padding_mismatch_count") == 0, "padding mismatch")
    _fail_unless(e2.get("mapping_review_count") == 24, "mapping count mismatch")
    _fail_unless(e2.get("bitstream_128b_count") == 24, "128-bit bitstream count mismatch")
    _fail_unless(e2.get("bitstream_64b_count") == 24, "64-bit bitstream count mismatch")

    operators = target.get("operators")
    _fail_unless(isinstance(operators, list) and len(operators) == 24, "target operator count")
    accum = operators[:8]
    scale = operators[8:16]
    round_ops = operators[16:24]
    _fail_unless(
        all(op.get("type") == "MatMulInt32Accumulate" for op in accum),
        "accumulate operator ordering/type mismatch",
    )
    _fail_unless(
        all(op.get("type") == "Node0075RequantScaleInt32ToFp32" for op in scale),
        "scale operator ordering/type mismatch",
    )
    _fail_unless(
        all(op.get("type") == "Node0075RequantRoundFp32ToUint8" for op in round_ops),
        "round operator ordering/type mismatch",
    )

    coverage = report["a_consumer_coverage"]
    expected_counts = {
        "reload_pass_count": 8,
        "accepted_occurrence_count": 8192,
        "accepted_traffic_bytes": 262144,
        "unique_consumer_byte_count": 32768,
    }
    for key, expected in expected_counts.items():
        _fail_unless(coverage.get(key) == expected, f"A coverage differs: {key}")
    _fail_unless(len(coverage.get("passes", [])) == 8, "A pass count differs")

    for pass_index, op in enumerate(accum):
        attrs = op["attributes"]
        binding = attrs["physical_bindings"]["inputs"]["A"]
        _fail_unless(binding.get("kind") == "existing_storage_alias", "A is not alias-bound")
        _fail_unless(binding.get("host_materialized") is False, "A is host materialized")
        for slice_id in range(16):
            expected = 0x000A2000 + (slice_id << 25)
            actual = int(binding["per_slice_base_addresses"][str(slice_id)], 16)
            _fail_unless(actual == expected, "A per-slice base differs")

        pass_receipt = coverage["passes"][pass_index]
        _fail_unless(pass_receipt["accepted_occurrence_count"] == 1024, "pass reads differ")
        _fail_unless(pass_receipt["accepted_traffic_bytes"] == 32768, "pass traffic differs")
        slice0 = pass_receipt["slice_records"][0]
        _fail_unless(
            slice0["ordered_address_sha256"] == EXPECTED_SLICE0_ORDERED_SHA256,
            "approved slice0 ordered address hash differs",
        )
        _fail_unless(
            slice0["read_byte_set_sha256"] == EXPECTED_SLICE0_BYTE_SET_SHA256,
            "approved slice0 byte-set hash differs",
        )

        patched = _json(
            OUTPUT / "jsons" / f"node0075_accum_pass{pass_index:02d}_MatMulInt32Accumulate.json"
        )
        streams = patched["stream_engine"]
        _fail_unless(int(str(streams["stream1"]["base_addr"]), 0) == 0x000A2000, "A stream base")
        _fail_unless(streams["stream1"]["dim_stride"][2] == 32, "A transaction stride")
        _fail_unless(
            streams["stream1"]["buf_spatial_stride"] == [0, 1] * 8,
            "A duplicate-spatial schedule differs",
        )
        _fail_unless(patched["buffer_config"]["buffer1"]["buffer_life_time"] == 16, "A lifetime")
        _fail_unless(streams["stream0"]["base_addr"] == streams["stream3"]["base_addr"], "B/Bp alias")
        _fail_unless(patched["special_array"]["data_type"] == "int8", "SA data type")
        _fail_unless(patched["special_array"]["bias_enable"] == 0, "SA bias must be zero")

        mapping = _json(OUTPUT / "config" / f"node0075_accum_pass{pass_index:02d}/mapping_review.json")
        stream_mapping = {
            item["node"]: item["resource"]
            for item in mapping["node_to_resource"]
            if str(item["node"]).startswith("STREAM.")
        }
        _fail_unless(stream_mapping.get("STREAM.stream1") == "READ_STREAM1", "A physical stream")
        _fail_unless(stream_mapping.get("STREAM.stream0") == "READ_STREAM0", "B physical stream")
        _fail_unless(stream_mapping.get("STREAM.stream3") == "READ_STREAM2", "Bp physical stream")

    sca = _json(OUTPUT / "sca_cfg.json")
    sca_d = _json(OUTPUT / "sca_cfg_D.json")
    _fail_unless(sca.get("Repeat_Num") == 24, "Repeat_Num differs")
    _fail_unless(sca.get("Exec_Length") == 505, "Exec_Length differs")
    _fail_unless(not [key for key in sca if "_matrixA_" in key], "intermediate/A host replay")
    _fail_unless(len([key for key in sca if "_matrixB_" in key]) == 128, "B preload count")
    _fail_unless(len(sca_d) == 128, "formal D fragment count")
    _fail_unless(
        all(key.startswith("node0075_round_pass") for key in sca_d),
        "non-final output leaked into formal readback",
    )
    instructions = (OUTPUT / "instructions_explained.txt").read_text(encoding="utf-8")
    _fail_unless(instructions.count("Start_Comp for operator") == 24, "Start_Comp count")
    _fail_unless("bitstream regeneration failed" not in (REPORT_ROOT / "pipeline.stdout.log").read_text(encoding="utf-8"), "pipeline tolerated mapping failure")

    return {
        "active_csa": _identity(ACTIVE_CSA),
        "arithmetic_report": _identity(ARITHMETIC_REPORT),
        "reload_pass_count": 8,
        "configured_qualified_read_occurrence_count": 8192,
        "configured_qualified_read_traffic_bytes": 262144,
        "unique_consumer_bytes": 32768,
        "start_comp_count": 24,
        "exec_128bit_line_count": 505,
        "b_preload_count": 128,
        "formal_d_fragment_count": 128,
        "host_a_or_intermediate_replay_count": 0,
    }


def validate() -> dict[str, Any]:
    first = subprocess.run(
        [sys.executable, str(ROOT / "tools/build_node0075_df23e4d_materializer.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    _fail_unless(first.returncode == 0, f"first deterministic rebuild failed: {first.stderr[-2000:]}")
    static = _validate_static_binding()
    before = _inventory()
    second = subprocess.run(
        [sys.executable, str(ROOT / "tools/build_node0075_df23e4d_materializer.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    _fail_unless(second.returncode == 0, f"second deterministic rebuild failed: {second.stderr[-2000:]}")
    _validate_static_binding()
    after = _inventory()
    if before != after:
        differing = sorted(
            path
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        )
        raise ValidationError(
            "two-run deterministic inventory differs: " + ", ".join(differing[:32])
        )
    result = {
        "schema": "node0075-df23e4d-materializer-independent-validation-v1",
        "test_id": TEST_ID,
        "status": "DETERMINISTIC_CONFIG_BOUND_LOCAL_E2_PASS",
        "passed": True,
        "claim_boundary": (
            "independent static/compositional config-bound validation and deterministic "
            "rebuild under an approved producer visibility precondition; no cross-operator "
            "execplan barrier, server upload/run/lease, or dynamic hardware acceptance claim"
        ),
        "static_binding": static,
        "determinism": {
            "fresh_rebuild_count": 2,
            "comparison_build_count": 2,
            "inventory_file_count": len(after),
            "exact_inventory_equal": True,
            "inventory": after,
        },
        "release": {
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_release": "NONE",
            "blocking_leaf": (
                "B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED"
            ),
        },
    }
    _write_json(VALIDATION, result)
    result["validation_report"] = _identity(VALIDATION)
    return result


def main() -> int:
    try:
        result = validate()
    except Exception as exc:
        print(f"NODE0075_MATERIALIZER_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
