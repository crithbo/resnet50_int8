#!/usr/bin/env python3
"""Independent validator for the node0071 -> node0075 native-ordering E2."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "r5-node0071-node0075-e1fb0f7-native-ordering-integration-v1"
OUT = ROOT / "artifacts/operator_config_validation" / TEST_ID
WORKLOAD = OUT / "workload"
N71 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v37_dbclk_rdready_compilefix"
)
N75_PIPELINE = ROOT / "ndp-sim/model_execplan/output/node0075_df23e4d_eight_pass_target"
N71_EXECPLAN = N71 / "workload/install/execplan.txt"
N75_EXECPLAN = N75_PIPELINE / "install/execplan.txt"
A_NPY = ROOT / "artifacts/w3/golden_batch16/tensors/tensor-6fbd5707d5f08110.npy"
D_NPY = ROOT / "artifacts/w3/golden_batch16/tensors/tensor-6cc774b369e8dea4.npy"
A_LOCAL_BASE = 0x000A2000
SLICE_STRIDE = 1 << 25
K = 2048
N71_CONFIG_RELOC_BASE = 0x016E0000
N71_CONFIG_RELOC_STRIDE = 0x400
PREFIX = f"install/cfg_pkg/{TEST_ID}/"
BITS128 = re.compile(r"[01]{128}")


class ValidationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root differs: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def decode_128(path: Path) -> bytes:
    chunks: list[bytes] = []
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        if not BITS128.fullmatch(line):
            raise ValidationError(f"128-bit ABI differs: {path}:{number}")
        chunks.append(int(line, 2).to_bytes(16, "little"))
    if not chunks:
        raise ValidationError(f"empty 128-bit file: {path}")
    return b"".join(chunks)


def exec_counts(lines: list[str]) -> dict[str, int]:
    if any(not BITS128.fullmatch(line) for line in lines):
        raise ValidationError("execplan line ABI differs")
    chunks = [
        line[offset : offset + 32]
        for line in lines
        for offset in range(0, 128, 32)
    ]
    return {
        "lines": len(lines),
        "start_comp": sum(chunk.endswith("101") for chunk in chunks),
        "opcode110": sum(chunk.endswith("110") for chunk in chunks),
    }


def expected_relocated_prefix(lines: list[str]) -> list[str]:
    old_fields = {
        (0x00100000 + index * 0x10000) >> 10: (
            N71_CONFIG_RELOC_BASE + index * N71_CONFIG_RELOC_STRIDE
        )
        >> 10
        for index in range(8)
    }
    result: list[str] = []
    changed = 0
    for line in lines:
        value = int(line, 2)
        halves = [(value >> 64) & ((1 << 64) - 1), value & ((1 << 64) - 1)]
        patched_halves: list[int] = []
        for half in halves:
            encoded = (half >> 34) & ((1 << 22) - 1)
            if (half & 0x7) == 0 and encoded in old_fields:
                mask = ((1 << 22) - 1) << 34
                half = (half & ~mask) | (old_fields[encoded] << 34)
                changed += 1
            patched_halves.append(half)
        result.append(f"{((patched_halves[0] << 64) | patched_halves[1]):0128b}")
    if changed != 8:
        raise ValidationError(f"expected node0071 relocation count differs: {changed}")
    return result


def fail(condition: bool, message: str, errors: list[str]) -> None:
    if condition:
        errors.append(message)


def validate() -> dict[str, Any]:
    errors: list[str] = []
    required = [
        OUT / "composite_target.json",
        OUT / "mapping_manifest.json",
        OUT / "bitstream_manifest.json",
        OUT / "execplan_manifest.json",
        OUT / "golden_manifest.json",
        OUT / "report.json",
        OUT / "artifact_manifest.json",
        WORKLOAD / "sca_cfg.json",
        WORKLOAD / "sca_cfg_D.json",
        WORKLOAD / "install/execplan.txt",
    ]
    fail(any(not path.is_file() for path in required), "required integration file missing", errors)
    if errors:
        raise ValidationError("; ".join(errors))

    target = load_json(OUT / "composite_target.json")
    mapping = load_json(OUT / "mapping_manifest.json")
    bitstream = load_json(OUT / "bitstream_manifest.json")
    exec_manifest = load_json(OUT / "execplan_manifest.json")
    golden_manifest = load_json(OUT / "golden_manifest.json")
    report = load_json(OUT / "report.json")
    artifact_manifest = load_json(OUT / "artifact_manifest.json")
    sca = load_json(WORKLOAD / "sca_cfg.json")
    sca_d = load_json(WORKLOAD / "sca_cfg_D.json")

    fail(target.get("candidate_release") is not False, "candidate release widened", errors)
    fail(target.get("functional_rtl_modified") is not False, "RTL modification claimed", errors)
    stages = target.get("ordered_stages")
    fail(not isinstance(stages, list) or len(stages) != 32, "ordered stage count differs", errors)
    if isinstance(stages, list) and len(stages) == 32:
        fail(
            [stage.get("id") for stage in stages[:8]]
            != [f"node0071_stage{index:02d}" for index in range(1, 9)],
            "node0071 prefix order differs",
            errors,
        )
        fail(
            [stage.get("id") for stage in stages[8:16]]
            != [f"node0075_accum_pass{index:02d}" for index in range(8)],
            "node0075 accumulate order differs",
            errors,
        )
        fail(
            [stage.get("id") for stage in stages[16:24]]
            != [f"node0075_scale_pass{index:02d}" for index in range(8)],
            "node0075 scale order differs",
            errors,
        )
        fail(
            [stage.get("id") for stage in stages[24:32]]
            != [f"node0075_round_pass{index:02d}" for index in range(8)],
            "node0075 round order differs",
            errors,
        )
    handoff = target.get("handoff", {})
    fail(handoff.get("a_preload_count") != 0, "target A preload count differs", errors)
    fail(
        handoff.get("host_copy_precompute_relayout_replay") is not False,
        "target permits host replay",
        errors,
    )
    fail(handoff.get("explicit_barrier_claim") is not False, "explicit barrier claimed", errors)
    fail(handoff.get("opcode110_is_barrier") is not False, "opcode110 claimed as barrier", errors)

    n71_lines = N71_EXECPLAN.read_text(encoding="ascii").splitlines()
    n75_lines = N75_EXECPLAN.read_text(encoding="ascii").splitlines()
    relocated_n71_lines = expected_relocated_prefix(n71_lines)
    combined_lines = (WORKLOAD / "install/execplan.txt").read_text(
        encoding="ascii"
    ).splitlines()
    fail(
        combined_lines != relocated_n71_lines + n75_lines,
        "execplan is not exact config-relocated producer plus exact consumer",
        errors,
    )
    combined_counts = exec_counts(combined_lines)
    n71_counts = exec_counts(relocated_n71_lines)
    n75_counts = exec_counts(n75_lines)
    fail(combined_counts != {"lines": 518, "start_comp": 32, "opcode110": 8}, "combined exec counts differ", errors)
    fail(n71_counts != {"lines": 13, "start_comp": 8, "opcode110": 8}, "producer exec counts differ", errors)
    fail(n75_counts != {"lines": 505, "start_comp": 24, "opcode110": 0}, "consumer exec counts differ", errors)
    boundary = exec_manifest.get("boundary", {})
    fail(boundary.get("inserted_line_count") != 0, "boundary line inserted", errors)
    fail(boundary.get("opcode110_is_barrier") is not False, "manifest barrier claim differs", errors)
    fail(
        boundary.get("producer_prefix_load_config_relocation_count") != 8,
        "producer config relocation count differs",
        errors,
    )

    dynamic_sca = {
        key: value
        for key, value in sca.items()
        if key not in {"Exec_Base", "Exec_Length", "Repeat_Num", "ExecutionPlan"}
    }
    input_keys = [key for key in dynamic_sca if key.startswith("node0071_input_slice")]
    n71_config_keys = [
        key for key in dynamic_sca if key.startswith("node0071_stage") and key.endswith("_config")
    ]
    b_keys = [key for key in dynamic_sca if "_matrixB_" in key]
    n75_config_keys = [
        key for key in dynamic_sca if key.startswith("node0075_") and key.endswith("_config")
    ]
    a_keys = [key for key in sca if "_matrixA_" in key or key.lower().endswith("_a")]
    fail(sca.get("Exec_Base") != "0x01706400", "Exec_Base differs", errors)
    fail(sca.get("Exec_Length") != 518, "Exec_Length differs", errors)
    fail(sca.get("Repeat_Num") != 32, "Repeat_Num differs", errors)
    fail(len(input_keys) != 16, "external input count differs", errors)
    fail(len(n71_config_keys) != 8, "node0071 config count differs", errors)
    fail(len(b_keys) != 128, "B destination count differs", errors)
    fail(len(n75_config_keys) != 24, "node0075 config count differs", errors)
    fail(bool(a_keys), "forbidden A preload key present", errors)
    fail(any("golden/" in str(item.get("path", "")) for item in dynamic_sca.values()), "golden used as runtime input", errors)

    intervals: list[tuple[int, int, str]] = []
    b_path_sets: dict[int, set[str]] = {index: set() for index in range(8)}
    for key, item in {**dynamic_sca, "ExecutionPlan": sca["ExecutionPlan"]}.items():
        raw_path = str(item.get("path", ""))
        fail(not raw_path.startswith(PREFIX), f"SCA path escapes integration: {key}", errors)
        if not raw_path.startswith(PREFIX):
            continue
        payload_path = WORKLOAD / raw_path[len(PREFIX) :]
        fail(not payload_path.is_file(), f"SCA payload missing: {key}", errors)
        if not payload_path.is_file():
            continue
        payload_bytes = len(decode_128(payload_path))
        begin = int(str(item["base_addr"]).replace("_", ""), 16)
        intervals.append((begin, begin + payload_bytes, key))
        match = re.match(r"node0075_accum_pass(\d\d)_matrixB_slice\d+", key)
        if match:
            b_path_sets[int(match.group(1))].add(raw_path)
            fail(payload_bytes != 2048 * 128, f"B payload size differs: {key}", errors)
    for pass_index, paths in b_path_sets.items():
        fail(len(paths) != 1, f"B pass {pass_index} is not one frozen shared file", errors)
    ordered_intervals = sorted(intervals)
    for left, right in zip(ordered_intervals, ordered_intervals[1:]):
        fail(right[0] < left[1], f"preload overlap: {left[2]} / {right[2]}", errors)
    for slice_id in range(16):
        a_begin = A_LOCAL_BASE + slice_id * SLICE_STRIDE
        a_end = a_begin + K
        for begin, end, key in intervals:
            fail(begin < a_end and a_begin < end, f"A region preloaded by {key}", errors)

    fail(len(sca_d) != 144, "formal D count differs", errors)
    runtime_paths = [str(item.get("path", "")) for item in sca_d.values()]
    fail(len(runtime_paths) != len(set(runtime_paths)), "formal D path collision", errors)
    fail(
        any(not path.startswith("sim_results/") for path in runtime_paths),
        "formal D path is not runtime-scoped",
        errors,
    )
    fail(
        any((OUT / path).exists() for path in runtime_paths),
        "runtime D target is preseeded",
        errors,
    )
    n71_d = [key for key in sca_d if key.startswith("node0071_final_uint8_slice")]
    n75_d = [key for key in sca_d if key.startswith("node0075_final_uint8_pass")]
    fail(len(n71_d) != 16 or len(n75_d) != 128, "formal D partition differs", errors)
    fail(
        any(sca_d[key].get("length") != 128 for key in n71_d),
        "node0071 D length differs",
        errors,
    )
    fail(
        any(sca_d[key].get("length") != 8 for key in n75_d),
        "node0075 D fragment length differs",
        errors,
    )

    activation = np.load(A_NPY, allow_pickle=False)
    expected_d = np.load(D_NPY, allow_pickle=False)
    for slice_id in range(16):
        n71_golden = (
            WORKLOAD
            / f"golden/node0071/final_uint8/slice{slice_id:02d}/matrix_D_128bit.txt"
        )
        fail(
            decode_128(n71_golden) != activation[slice_id].tobytes(order="C"),
            f"node0071 final / node0075 A alias differs: slice {slice_id}",
            errors,
        )
        reconstructed = bytearray()
        for pass_index in range(8):
            fragment = (
                WORKLOAD
                / f"golden/node0075/final_uint8/pass{pass_index:02d}/"
                f"slice{slice_id:02d}/matrix_D_128bit.txt"
            )
            payload = decode_128(fragment)
            fail(len(payload) != 128, f"node0075 final fragment size differs: {fragment}", errors)
            reconstructed.extend(payload)
        fail(
            bytes(reconstructed[:1000]) != expected_d[slice_id].tobytes(order="C"),
            f"node0075 logical D golden differs: slice {slice_id}",
            errors,
        )
        fail(
            bytes(reconstructed[1000:]) != bytes([60]) * 24,
            f"node0075 padding golden differs: slice {slice_id}",
            errors,
        )

    node0071_golden_count = len(
        list((WORKLOAD / "golden/node0071").rglob("matrix_D_128bit.txt"))
    )
    node0075_golden_count = len(
        list((WORKLOAD / "golden/node0075").rglob("matrix_D_128bit.txt"))
    )
    fail(node0071_golden_count != 48, "node0071 golden file count differs", errors)
    fail(node0075_golden_count != 384, "node0075 golden file count differs", errors)
    fail(
        golden_manifest.get("sca_references_golden_paths") is not False,
        "golden manifest runtime boundary differs",
        errors,
    )

    fail(bitstream.get("config_count") != 32, "bitstream manifest count differs", errors)
    fail(
        len(mapping.get("node0075", {}).get("mapping_reviews", [])) != 24,
        "mapping review count differs",
        errors,
    )
    fail(
        report.get("status") != "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_PASS",
        "report status differs",
        errors,
    )
    coverage = report.get("a_consumer_configured_coverage", {})
    fail(coverage.get("reload_pass_count") != 8, "reload pass count differs", errors)
    fail(coverage.get("occurrence_count") != 8192, "configured A occurrence count differs", errors)
    fail(coverage.get("traffic_bytes") != 262144, "configured A traffic differs", errors)
    fail(coverage.get("unique_bytes") != 32768, "unique A bytes differ", errors)

    manifest_records = artifact_manifest.get("files")
    fail(not isinstance(manifest_records, list), "artifact manifest records differ", errors)
    if isinstance(manifest_records, list):
        for item in manifest_records:
            path = OUT / str(item.get("path", ""))
            fail(not path.is_file(), f"manifest file missing: {path}", errors)
            if path.is_file():
                fail(path.stat().st_size != item.get("bytes"), f"manifest size differs: {path}", errors)
                fail(sha256(path) != item.get("sha256"), f"manifest hash differs: {path}", errors)

    result = {
        "schema": "node0071-node0075-native-ordering-independent-validation-v1",
        "test_id": TEST_ID,
        "status": (
            "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_VALIDATION_PASS"
            if not errors
            else "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_VALIDATION_FAIL"
        ),
        "passed": not errors,
        "errors": errors,
        "checks": {
            "ordered_stage_count": 32,
            "execplan_lines": combined_counts["lines"],
            "start_comp_count": combined_counts["start_comp"],
            "opcode110_slots_retained_in_producer_prefix_only": combined_counts["opcode110"],
            "boundary_inserted_lines": 0,
            "explicit_barrier_claim": False,
            "a_preload_count": len(a_keys),
            "b_destination_count": len(b_keys),
            "configured_a_read_occurrences": coverage.get("occurrence_count"),
            "configured_a_traffic_bytes": coverage.get("traffic_bytes"),
            "node0071_golden_files": node0071_golden_count,
            "node0075_golden_files": node0075_golden_count,
            "formal_d_count": len(sca_d),
            "runtime_d_preseed_count": sum((OUT / path).exists() for path in runtime_paths),
        },
        "claim_boundary": {
            "local_config_bound_e2": not errors,
            "server_actual_acceptance": False,
            "natural_terminal": False,
            "formal_d_runtime_match": False,
            "candidate_release": False,
        },
    }
    write_json(OUT / "validation.json", result)
    return result


def main() -> int:
    try:
        result = validate()
    except (ValidationError, OSError, ValueError, KeyError) as exc:
        print(f"INTEGRATION_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
