#!/usr/bin/env python3
"""Build the node0071 -> node0075 native-ordering diagnostic integration.

This builder composes the current node0071 v37 producer workload with the
existing node0075 eight-pass materialization without preloading the aliased A
region.  It deliberately makes no generic visibility-barrier claim: the two
execplans are concatenated byte-for-byte and no opcode is inserted at their
boundary.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "r5-node0071-node0075-e1fb0f7-native-ordering-integration-v1"
OUT = ROOT / "artifacts/operator_config_validation" / TEST_ID
WORKLOAD = OUT / "workload"
CURRENT_RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
RUN_NAMESPACE = "r5_node0071_node0075_e1fb0f7_native_ordering_v1"

N71 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v37_dbclk_rdready_compilefix"
)
N71_WORKLOAD = N71 / "workload"
N71_SCA = N71_WORKLOAD / "sca_cfg.json"
N71_SCA_D = N71_WORKLOAD / "sca_cfg_D.json"
N71_EXECPLAN = N71_WORKLOAD / "install/execplan.txt"
N71_MANIFEST = N71 / "TEST_PACKAGE_MANIFEST.json"

N75_MATERIALIZER = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-df23e4d-eight-pass-materializer-v1"
)
N75_TARGET = N75_MATERIALIZER / "node0075_df23e4d_eight_pass_target.json"
N75_REPORT = N75_MATERIALIZER / "materializer_report.json"
N75_VALIDATION = N75_MATERIALIZER / "determinism_and_config_binding_validation.json"
N75_PIPELINE = ROOT / "ndp-sim/model_execplan/output/node0075_df23e4d_eight_pass_target"
N75_SCA = N75_PIPELINE / "sca_cfg.json"
N75_SCA_D = N75_PIPELINE / "sca_cfg_D.json"
N75_EXECPLAN = N75_PIPELINE / "install/execplan.txt"

ALIAS_CONTRACT = (
    ROOT
    / "contracts/operator_config/"
    "node0071_node0075_uint8_identity_alias_integration_v1.json"
)
AUTHORIZATION = (
    ROOT
    / ".agents/task_records/"
    "20260805_node0075_no_explicit_barrier_native_ordering_authorization.md"
)
PLAN = ROOT / ".agents/plan.md"
RTL_SYNC_REPORT = ROOT / "artifacts/rtl_sync/trassic_master_e1fb0f7_20260804/report.json"

A_NPY = ROOT / "artifacts/w3/golden_batch16/tensors/tensor-6fbd5707d5f08110.npy"
ACC_NPY = (
    ROOT
    / "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0075-accumulate.npy"
)
D_NPY = ROOT / "artifacts/w3/golden_batch16/tensors/tensor-6cc774b369e8dea4.npy"

ACTIVE_SLICES = tuple(range(16))
PASS_COUNT = 8
K = 2048
N = 1000
PHYSICAL_PASS_N = 128
SLICE_STRIDE = 1 << 25
A_LOCAL_BASE = 0x000A2000
FINAL_D_LOCAL_BASE = 0x01700000
EXEC_BASE = 0x01706400
N71_CONFIG_RELOC_BASE = 0x016E0000
N71_CONFIG_RELOC_STRIDE = 0x400
MULTIPLIER_BITS = 0x3A510DB3
MULTIPLIER = np.array([MULTIPLIER_BITS], dtype=np.uint32).view(np.float32)[0]
Y_ZERO_POINT = 60


class IntegrationError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise IntegrationError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def copy_exact(source: Path, destination: Path) -> dict[str, Any]:
    if not source.is_file():
        raise IntegrationError(f"source file missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if source.stat().st_size != destination.stat().st_size or sha256(source) != sha256(
        destination
    ):
        raise IntegrationError(f"copy identity mismatch: {source} -> {destination}")
    return identity(destination)


def read_128_text(path: Path) -> bytes:
    chunks: list[bytes] = []
    for line_number, raw in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        if len(raw) != 128 or set(raw) - {"0", "1"}:
            raise IntegrationError(f"invalid 128-bit text: {path}:{line_number}")
        chunks.append(int(raw, 2).to_bytes(16, byteorder="little"))
    if not chunks:
        raise IntegrationError(f"empty 128-bit text: {path}")
    return b"".join(chunks)


def write_128_text(path: Path, payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) % 16:
        raise IntegrationError(f"payload is not a non-empty multiple of 16: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{int.from_bytes(payload[offset:offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(payload), 16)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {
        "path": path.relative_to(OUT).as_posix(),
        "payload_bytes": len(payload),
        "line_count_128bit": len(lines),
        "payload_sha256": sha256_bytes(payload),
        "text_sha256": sha256(path),
    }


def installed_path(relative: str) -> str:
    return f"install/cfg_pkg/{TEST_ID}/{relative}"


def runtime_path(relative: str) -> str:
    return f"sim_results/{RUN_NAMESPACE}/formal_d/{relative}"


def file_records(root: Path, excluded: Iterable[Path] = ()) -> list[dict[str, Any]]:
    excluded_resolved = {item.resolve() for item in excluded}
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise IntegrationError(f"symlink forbidden in integration: {path}")
        if path.is_file() and path.resolve() not in excluded_resolved:
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    return records


def count_execplan(lines: list[str]) -> dict[str, Any]:
    if any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise IntegrationError("execplan has a non-128-bit line")
    chunks = [
        line[offset : offset + 32]
        for line in lines
        for offset in range(0, 128, 32)
    ]
    return {
        "line_count_128bit": len(lines),
        "command_slot_count_32bit": len(chunks),
        "start_comp_count": sum(chunk.endswith("101") for chunk in chunks),
        "opcode110_slot_count": sum(chunk.endswith("110") for chunk in chunks),
        "text_sha256": sha256_bytes(("\n".join(lines) + "\n").encode("ascii")),
    }


def relocate_node0071_load_config(
    lines: list[str],
    old_bases: list[int],
    new_bases: list[int],
) -> tuple[list[str], list[dict[str, Any]]]:
    if len(old_bases) != 8 or len(new_bases) != 8:
        raise IntegrationError("node0071 config relocation cardinality differs")
    old_to_new = {
        old_base >> 10: new_base >> 10
        for old_base, new_base in zip(old_bases, new_bases)
    }
    if any(base & 0x3FF for base in old_bases + new_bases):
        raise IntegrationError("node0071 config relocation is not 1KiB aligned")
    patched_lines: list[str] = []
    records: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines):
        value = int(line, 2)
        halves = [(value >> 64) & ((1 << 64) - 1), value & ((1 << 64) - 1)]
        patched_halves: list[int] = []
        for half_index, half in enumerate(halves):
            opcode = half & 0x7
            encoded_address = (half >> 34) & ((1 << 22) - 1)
            if opcode == 0 and encoded_address in old_to_new:
                new_encoded_address = old_to_new[encoded_address]
                mask = ((1 << 22) - 1) << 34
                patched = (half & ~mask) | (new_encoded_address << 34)
                records.append(
                    {
                        "stage_index": len(records) + 1,
                        "line_index": line_index,
                        "half_index_msb_first": half_index,
                        "old_base_addr": f"0x{encoded_address << 10:08x}",
                        "new_base_addr": f"0x{new_encoded_address << 10:08x}",
                        "changed_field": "Load_Config.ddr_config_addr[22b]",
                        "other_bits_unchanged": (patched ^ half) & ~mask == 0,
                    }
                )
                half = patched
            patched_halves.append(half)
        patched_value = (patched_halves[0] << 64) | patched_halves[1]
        patched_lines.append(f"{patched_value:0128b}")
    if len(records) != 8:
        raise IntegrationError(f"node0071 Load_Config relocation count differs: {len(records)}")
    return patched_lines, records


def _check_rtl() -> dict[str, Any]:
    checkout = ROOT / "Trassic2.0_RTL"
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={checkout.as_posix()}",
            "-C",
            str(checkout),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    head = result.stdout.strip()
    if head != CURRENT_RTL_COMMIT:
        raise IntegrationError(
            f"current RTL commit differs: expected {CURRENT_RTL_COMMIT}, got {head}"
        )
    return {
        "commit": head,
        "sync_report": identity(RTL_SYNC_REPORT),
        "functional_rtl_modified_by_integration": False,
    }


def _copy_node0071(
    source_sca: dict[str, Any],
    composite_sca: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    input_records: list[dict[str, Any]] = []
    config_records: list[dict[str, Any]] = []
    for slice_id in ACTIVE_SLICES:
        key = f"node0071_input_slice{slice_id}"
        item = source_sca[key]
        source = N71_WORKLOAD / f"input/slice{slice_id:02d}/matrix_A_128bit.txt"
        relative = f"input/node0071/slice{slice_id:02d}/matrix_A_128bit.txt"
        destination = WORKLOAD / relative
        copied = copy_exact(source, destination)
        raw = read_128_text(destination)
        if len(raw) != 2048 * 7 * 7:
            raise IntegrationError(f"node0071 typed input size differs for slice {slice_id}")
        composite_sca[key] = {
            "base_addr": item["base_addr"],
            "path": installed_path(relative),
        }
        input_records.append(
            {
                "slice_id": slice_id,
                "dtype": "uint8",
                "logical_shape": [2048, 7, 7],
                "memory_bytes": len(raw),
                **copied,
            }
        )

    for stage_index in range(1, 9):
        source_key = f"stage{stage_index}_config"
        source_item = source_sca[source_key]
        source = N71_WORKLOAD / "install/cfg_pkg" / Path(source_item["path"]).name
        relative = f"install/cfg_pkg/node0071/{source.name}"
        destination = WORKLOAD / relative
        copied = copy_exact(source, destination)
        composite_key = f"node0071_stage{stage_index:02d}_config"
        relocated_base = N71_CONFIG_RELOC_BASE + (
            stage_index - 1
        ) * N71_CONFIG_RELOC_STRIDE
        composite_sca[composite_key] = {
            "base_addr": f"0x{relocated_base:08X}",
            "path": installed_path(relative),
        }
        config_records.append(
            {
                "stage_index": stage_index,
                "sca_key": composite_key,
                "source_base_addr": source_item["base_addr"],
                "integration_base_addr": f"0x{relocated_base:08X}",
                "relocation_kind": "config_storage_only",
                "source": identity(source),
                "materialized": copied,
            }
        )
    return input_records, config_records


def _copy_node0075(
    source_sca: dict[str, Any],
    composite_sca: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    weight_records: list[dict[str, Any]] = []
    config_records: list[dict[str, Any]] = []
    for pass_index in range(PASS_COUNT):
        source_paths = [
            N75_PIPELINE
            / source_sca[
                f"node0075_accum_pass{pass_index:02d}_matrixB_slice{slice_id}"
            ]["path"]
            for slice_id in ACTIVE_SLICES
        ]
        hashes = {sha256(path) for path in source_paths}
        if len(hashes) != 1:
            raise IntegrationError(f"node0075 B differs across slices for pass {pass_index}")
        relative = (
            f"weights/node0075/pass{pass_index:02d}/"
            "matrix_B_linearized_128bit.txt"
        )
        destination = WORKLOAD / relative
        copied = copy_exact(source_paths[0], destination)
        raw = read_128_text(destination)
        if len(raw) != K * PHYSICAL_PASS_N:
            raise IntegrationError(f"node0075 B payload size differs for pass {pass_index}")
        for slice_id in ACTIVE_SLICES:
            key = f"node0075_accum_pass{pass_index:02d}_matrixB_slice{slice_id}"
            source_item = source_sca[key]
            composite_sca[key] = {
                "base_addr": source_item["base_addr"],
                "path": installed_path(relative),
            }
        weight_records.append(
            {
                "pass_index": pass_index,
                "shared_frozen_constant_path_for_16_distinct_destinations": relative,
                "source_slice_hash_count": len(hashes),
                "memory_bytes_per_destination": len(raw),
                "destination_count": 16,
                **copied,
            }
        )

    config_keys = [
        key
        for key in source_sca
        if key.startswith("node0075_") and key.endswith("_config")
    ]
    if len(config_keys) != 24:
        raise IntegrationError("node0075 config key count differs")
    for key in config_keys:
        source_item = source_sca[key]
        source = N75_PIPELINE / source_item["path"]
        relative = f"install/cfg_pkg/node0075/{source.name}"
        destination = WORKLOAD / relative
        copied = copy_exact(source, destination)
        composite_sca[key] = {
            "base_addr": source_item["base_addr"],
            "path": installed_path(relative),
        }
        config_records.append(
            {
                "sca_key": key,
                "base_addr": source_item["base_addr"],
                "source": identity(source),
                "materialized": copied,
            }
        )
    return weight_records, config_records


def _materialize_goldens() -> dict[str, Any]:
    node0071_records: list[dict[str, Any]] = []
    for category in ("sum_int32", "scaled_fp32", "final_uint8"):
        for slice_id in ACTIVE_SLICES:
            source = (
                N71_WORKLOAD
                / f"golden/{category}/slice{slice_id:02d}/matrix_D_128bit.txt"
            )
            destination = (
                WORKLOAD
                / f"golden/node0071/{category}/slice{slice_id:02d}/"
                "matrix_D_128bit.txt"
            )
            copied = copy_exact(source, destination)
            node0071_records.append(
                {"category": category, "slice_id": slice_id, **copied}
            )

    activation = np.load(A_NPY, allow_pickle=False)
    accumulator = np.load(ACC_NPY, allow_pickle=False)
    expected_d = np.load(D_NPY, allow_pickle=False)
    if activation.dtype != np.uint8 or activation.shape != (16, K):
        raise IntegrationError("node0075 A tensor identity/shape differs")
    if accumulator.dtype != np.int32 or accumulator.shape != (16, N):
        raise IntegrationError("node0075 accumulator tensor identity/shape differs")
    if expected_d.dtype != np.uint8 or expected_d.shape != (16, N):
        raise IntegrationError("node0075 D tensor identity/shape differs")

    for slice_id in ACTIVE_SLICES:
        producer_payload = read_128_text(
            WORKLOAD
            / f"golden/node0071/final_uint8/slice{slice_id:02d}/matrix_D_128bit.txt"
        )
        if producer_payload != activation[slice_id].tobytes(order="C"):
            raise IntegrationError(
                f"node0071 final golden does not equal node0075 A for slice {slice_id}"
            )

    padded_acc = np.zeros((16, PASS_COUNT * PHYSICAL_PASS_N), dtype=np.int32)
    padded_acc[:, :N] = accumulator
    scaled = np.multiply(
        padded_acc.astype(np.float32), np.float32(MULTIPLIER), dtype=np.float32
    )
    padded_d = np.full(
        (16, PASS_COUNT * PHYSICAL_PASS_N), Y_ZERO_POINT, dtype=np.uint8
    )
    padded_d[:, :N] = expected_d

    node0075_records: list[dict[str, Any]] = []
    for pass_index in range(PASS_COUNT):
        begin = pass_index * PHYSICAL_PASS_N
        end = begin + PHYSICAL_PASS_N
        for slice_id in ACTIVE_SLICES:
            for category, array in (
                ("accum_int32", padded_acc),
                ("scaled_fp32", scaled),
                ("final_uint8", padded_d),
            ):
                path = (
                    WORKLOAD
                    / f"golden/node0075/{category}/pass{pass_index:02d}/"
                    f"slice{slice_id:02d}/matrix_D_128bit.txt"
                )
                receipt = write_128_text(
                    path, np.ascontiguousarray(array[slice_id, begin:end]).tobytes()
                )
                node0075_records.append(
                    {
                        "category": category,
                        "pass_index": pass_index,
                        "slice_id": slice_id,
                        **receipt,
                    }
                )
    return {
        "node0071": {
            "categories": ["sum_int32", "scaled_fp32", "final_uint8"],
            "file_count": len(node0071_records),
            "records": node0071_records,
        },
        "node0075": {
            "categories": ["accum_int32", "scaled_fp32", "final_uint8"],
            "file_count": len(node0075_records),
            "records": node0075_records,
        },
        "frozen_tensor_identities": [
            identity(A_NPY),
            identity(ACC_NPY),
            identity(D_NPY),
        ],
    }


def _build_sca_d(source_d75: dict[str, Any]) -> dict[str, Any]:
    sca_d: dict[str, Any] = {}
    for slice_id in ACTIVE_SLICES:
        key = f"node0071_final_uint8_slice{slice_id}"
        sca_d[key] = {
            "base_addr": f"0x{A_LOCAL_BASE + slice_id * SLICE_STRIDE:08X}",
            "length": 128,
            "path": runtime_path(
                f"node0071/final_uint8/slice{slice_id:02d}/matrix_D_128bit.txt"
            ),
        }
    for pass_index in range(PASS_COUNT):
        for slice_id in ACTIVE_SLICES:
            source_key = (
                f"node0075_round_pass{pass_index:02d}_matrixD_slice{slice_id}"
            )
            source_item = source_d75[source_key]
            key = f"node0075_final_uint8_pass{pass_index:02d}_slice{slice_id}"
            sca_d[key] = {
                "base_addr": source_item["base_addr"],
                "length": 8,
                "path": runtime_path(
                    f"node0075/final_uint8/pass{pass_index:02d}/"
                    f"slice{slice_id:02d}/matrix_D_128bit.txt"
                ),
            }
    if len(sca_d) != 144:
        raise IntegrationError("composite formal D count differs")
    return sca_d


def _preload_intervals(sca: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = f"install/cfg_pkg/{TEST_ID}/"
    intervals: list[dict[str, Any]] = []
    for key, item in sca.items():
        if key in {"Exec_Base", "Exec_Length", "Repeat_Num"}:
            continue
        if not isinstance(item, dict) or not str(item.get("path", "")).startswith(prefix):
            raise IntegrationError(f"SCA path is not integration-scoped: {key}")
        relative = str(item["path"])[len(prefix) :]
        payload_path = WORKLOAD / relative
        payload_bytes = len(read_128_text(payload_path))
        begin = int(str(item["base_addr"]).replace("_", ""), 16)
        intervals.append(
            {
                "key": key,
                "begin": begin,
                "end": begin + payload_bytes,
                "bytes": payload_bytes,
                "path": str(item["path"]),
            }
        )
    ordered = sorted(intervals, key=lambda item: (item["begin"], item["end"], item["key"]))
    for left, right in zip(ordered, ordered[1:]):
        if right["begin"] < left["end"]:
            raise IntegrationError(
                f"SCA preload overlap: {left['key']} and {right['key']}"
            )
    for slice_id in ACTIVE_SLICES:
        a_begin = A_LOCAL_BASE + slice_id * SLICE_STRIDE
        a_end = a_begin + K
        for item in ordered:
            if item["begin"] < a_end and a_begin < item["end"]:
                raise IntegrationError(
                    f"forbidden A-region preload: {item['key']} slice={slice_id}"
                )
    return [
        {
            **item,
            "begin": f"0x{item['begin']:08x}",
            "end_exclusive": f"0x{item.pop('end'):08x}",
        }
        for item in ordered
    ]


def build() -> dict[str, Any]:
    if OUT.exists():
        raise IntegrationError(
            f"refusing to overwrite existing integration-scoped output: {OUT}"
        )
    required = [
        N71_SCA,
        N71_SCA_D,
        N71_EXECPLAN,
        N71_MANIFEST,
        N75_TARGET,
        N75_REPORT,
        N75_VALIDATION,
        N75_SCA,
        N75_SCA_D,
        N75_EXECPLAN,
        ALIAS_CONTRACT,
        AUTHORIZATION,
        PLAN,
        RTL_SYNC_REPORT,
        A_NPY,
        ACC_NPY,
        D_NPY,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise IntegrationError(f"required current inputs missing: {missing}")

    rtl = _check_rtl()
    n71_sca = load_json(N71_SCA)
    n75_sca = load_json(N75_SCA)
    n75_sca_d = load_json(N75_SCA_D)
    n75_target = load_json(N75_TARGET)
    n75_report = load_json(N75_REPORT)
    n75_validation = load_json(N75_VALIDATION)
    if n75_report.get("status") != "CONFIG_BOUND_LOCAL_E2_PASS":
        raise IntegrationError("node0075 materializer is not config-bound E2 pass")
    if n75_validation.get("status") != "DETERMINISTIC_CONFIG_BOUND_LOCAL_E2_PASS":
        raise IntegrationError("node0075 deterministic validation is not pass")
    if n71_sca.get("Repeat_Num") != 8 or n75_sca.get("Repeat_Num") != 24:
        raise IntegrationError("source stage counts differ")

    WORKLOAD.mkdir(parents=True)
    composite_sca: dict[str, Any] = {
        "Exec_Base": f"0x{EXEC_BASE:08X}",
        "Exec_Length": 518,
        "ExecutionPlan": {
            "base_addr": f"0x{EXEC_BASE:08X}",
            "path": installed_path("install/execplan.txt"),
        },
        "Repeat_Num": 32,
    }
    input_records, n71_configs = _copy_node0071(n71_sca, composite_sca)
    weight_records, n75_configs = _copy_node0075(n75_sca, composite_sca)

    n71_source_lines = N71_EXECPLAN.read_text(encoding="ascii").splitlines()
    n75_lines = N75_EXECPLAN.read_text(encoding="ascii").splitlines()
    n71_old_config_bases = [
        int(str(n71_sca[f"stage{stage_index}_config"]["base_addr"]), 16)
        for stage_index in range(1, 9)
    ]
    n71_new_config_bases = [
        N71_CONFIG_RELOC_BASE + stage_index * N71_CONFIG_RELOC_STRIDE
        for stage_index in range(8)
    ]
    n71_lines, n71_relocations = relocate_node0071_load_config(
        n71_source_lines,
        n71_old_config_bases,
        n71_new_config_bases,
    )
    combined_lines = n71_lines + n75_lines
    execplan_path = WORKLOAD / "install/execplan.txt"
    execplan_path.parent.mkdir(parents=True, exist_ok=True)
    execplan_path.write_text(
        "\n".join(combined_lines) + "\n", encoding="ascii", newline="\n"
    )
    execplan_counts = {
        "node0071_prefix": count_execplan(n71_lines),
        "node0071_source_prefix": count_execplan(n71_source_lines),
        "node0075_suffix": count_execplan(n75_lines),
        "combined": count_execplan(combined_lines),
        "node0071_config_storage_relocations": n71_relocations,
        "boundary": {
            "producer_last_line_index": len(n71_lines) - 1,
            "consumer_first_line_index": len(n71_lines),
            "inserted_line_count": 0,
            "producer_prefix_config_storage_relocated": True,
            "producer_prefix_load_config_relocation_count": len(n71_relocations),
            "producer_prefix_other_command_bits_unchanged": all(
                item["other_bits_unchanged"] for item in n71_relocations
            ),
            "consumer_suffix_byte_exact": (
                execplan_path.read_text(encoding="ascii").splitlines()[len(n71_lines) :]
                == n75_lines
            ),
            "opcode110_is_barrier": False,
            "explicit_barrier_claim": False,
            "transition": "normal next-command/config transition only",
        },
    }
    if (
        len(combined_lines) != 518
        or execplan_counts["combined"]["start_comp_count"] != 32
        or execplan_counts["node0071_prefix"]["start_comp_count"] != 8
        or execplan_counts["node0075_suffix"]["start_comp_count"] != 24
        or execplan_counts["combined"]["opcode110_slot_count"]
        != execplan_counts["node0071_prefix"]["opcode110_slot_count"]
    ):
        raise IntegrationError("combined execplan structure differs")

    goldens = _materialize_goldens()
    sca_d = _build_sca_d(n75_sca_d)
    write_json(WORKLOAD / "sca_cfg.json", composite_sca)
    write_json(WORKLOAD / "sca_cfg_D.json", sca_d)
    intervals = _preload_intervals(composite_sca)

    operators = n75_target.get("operators")
    if not isinstance(operators, list) or len(operators) != 24:
        raise IntegrationError("node0075 target operator list differs")
    producer_stages = [
        {
            "id": f"node0071_stage{stage_index:02d}",
            "type": (
                "GapInt32Reduction"
                if stage_index <= 6
                else "GapRequantScaleInt32ToFp32"
                if stage_index == 7
                else "GapRequantRoundFp32ToUint8"
            ),
            "owner": "GAP/node0071",
            "existing_config_key": f"node0071_stage{stage_index:02d}_config",
            "source_contract": identity(
                N71 / "provenance/config_bound_simulator_report.json"
            ),
        }
        for stage_index in range(1, 9)
    ]
    composite_target = {
        "schema": "node0071-node0075-native-ordering-diagnostic-target-v1",
        "test_id": TEST_ID,
        "status": "DIAGNOSTIC_INTEGRATION_BUILDING",
        "candidate_release": False,
        "functional_rtl_modified": False,
        "rtl": rtl,
        "graph_external_typed_inputs": input_records,
        "ordered_stages": producer_stages + operators,
        "stage_counts": {
            "node0071": 8,
            "node0075": 24,
            "total": 32,
            "node0075_accumulate_passes": 8,
            "node0075_scale_passes": 8,
            "node0075_round_passes": 8,
        },
        "handoff": {
            "producer": "node0071 stage08 final UINT8 D",
            "consumer": "node0075 accum pass00 UINT8 A",
            "allocation": {
                "per_slice_local_base": f"0x{A_LOCAL_BASE:08x}",
                "bytes_per_slice": K,
                "slice_stride": SLICE_STRIDE,
                "dtype": "uint8",
                "logical_shape": [16, K],
            },
            "identity_alias": True,
            "a_preload_count": 0,
            "host_copy_precompute_relayout_replay": False,
            "explicit_barrier_claim": False,
            "opcode110_is_barrier": False,
            "ordering_hypothesis": (
                "user-authorized frozen-instance native ordering in one simulator; "
                "dynamic observer must adjudicate producer downstream acceptance "
                "before node0075 pass00 first accepted read"
            ),
        },
        "reload": {
            "minimum_necessary_pass_count": 8,
            "derivation": "ceil(1000/(16*8))=8",
            "configured_read_occurrences_per_slice": 512,
            "configured_read_occurrences_total": 8192,
            "configured_accepted_traffic_bytes": 262144,
            "unique_a_bytes": 32768,
            "dynamic_actual_acceptance_observed": False,
        },
    }
    write_json(OUT / "composite_target.json", composite_target)

    mapping_manifest = {
        "schema": "node0071-node0075-native-ordering-mapping-manifest-v1",
        "test_id": TEST_ID,
        "node0071": {
            "ownership": "read-only current v37 producer consumption",
            "config_records": n71_configs,
            "provenance": [
                identity(N71 / "provenance/config_bound_simulator_report.json"),
                identity(N71 / "provenance/materialized_roundtrip_report.json"),
                identity(N71 / "provenance/validation_report.json"),
            ],
        },
        "node0075": {
            "ownership": "node0075 existing config-bound materialization",
            "config_records": n75_configs,
            "mapping_reviews": [
                identity(path)
                for path in sorted((N75_PIPELINE / "config").glob("*/mapping_review.json"))
            ],
        },
    }
    if len(mapping_manifest["node0075"]["mapping_reviews"]) != 24:
        raise IntegrationError("node0075 mapping review count differs")
    write_json(OUT / "mapping_manifest.json", mapping_manifest)

    bitstream_manifest = {
        "schema": "node0071-node0075-native-ordering-bitstream-manifest-v1",
        "test_id": TEST_ID,
        "config_count": len(n71_configs) + len(n75_configs),
        "node0071_configs": n71_configs,
        "node0075_configs": n75_configs,
    }
    if bitstream_manifest["config_count"] != 32:
        raise IntegrationError("composite bitstream count differs")
    write_json(OUT / "bitstream_manifest.json", bitstream_manifest)
    write_json(OUT / "execplan_manifest.json", execplan_counts)
    write_json(
        OUT / "golden_manifest.json",
        {
            "schema": "node0071-node0075-native-ordering-stage-goldens-v1",
            "runtime_input_use": False,
            "sca_references_golden_paths": False,
            **goldens,
        },
    )

    a_coverage = n75_report["a_consumer_coverage"]
    report = {
        "schema": "node0071-node0075-e1fb0f7-native-ordering-integration-report-v1",
        "test_id": TEST_ID,
        "status": "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_PASS",
        "evidence_level": "LOCAL_CONFIG_BOUND_E2",
        "candidate_release": False,
        "package_generated": False,
        "package_release": "NONE_PENDING_FRESH_DIAGNOSTIC_PACKAGE",
        "rtl": rtl,
        "composition": {
            "single_simulator_required": True,
            "single_execplan": True,
            "ordered_stage_count": 32,
            "execplan_line_count": 518,
            "start_comp_count": 32,
            "node0071_stage_count": 8,
            "node0075_stage_count": 24,
            "normal_transition_only": True,
            "explicit_barrier_claim": False,
            "opcode110_is_barrier": False,
            "dump_reload_between_operators": False,
            "a_preload_count": 0,
            "host_copy_precompute_relayout_replay": False,
            "node0071_config_storage_relocation_count": len(n71_relocations),
            "node0071_data_address_relocation_count": 0,
        },
        "a_consumer_configured_coverage": {
            "reload_pass_count": a_coverage["reload_pass_count"],
            "occurrence_count": a_coverage["accepted_occurrence_count"],
            "traffic_bytes": a_coverage["accepted_traffic_bytes"],
            "unique_bytes": a_coverage["unique_consumer_byte_count"],
            "occurrence_sha256": a_coverage["occurrence_sha256"],
            "count_semantics": (
                "configured qualified E2 occurrences only; server actual acceptance "
                "remains a dynamic observer gate"
            ),
        },
        "formal_d": {
            "node0071_final_uint8_readbacks": 16,
            "node0075_final_uint8_fragment_readbacks": 128,
            "total_readbacks": len(sca_d),
            "runtime_targets_preseeded": False,
            "golden_paths_separate_from_runtime_paths": True,
        },
        "stage_goldens": {
            "node0071_file_count": goldens["node0071"]["file_count"],
            "node0075_file_count": goldens["node0075"]["file_count"],
            "total_file_count": (
                goldens["node0071"]["file_count"]
                + goldens["node0075"]["file_count"]
            ),
            "node0071_final_equals_node0075_a_all_16_slices": True,
        },
        "preload_interval_count": len(intervals),
        "preload_intervals_sha256": canonical_sha256(intervals),
        "source_receipts": [
            identity(path)
            for path in (
                PLAN,
                AUTHORIZATION,
                RTL_SYNC_REPORT,
                N71_MANIFEST,
                N71_SCA,
                N71_SCA_D,
                N71_EXECPLAN,
                N75_TARGET,
                N75_REPORT,
                N75_VALIDATION,
                N75_SCA,
                N75_SCA_D,
                N75_EXECPLAN,
                ALIAS_CONTRACT,
            )
        ],
        "dynamic_gates": {
            "producer_final_downstream_hub_acceptance": False,
            "node0075_pass00_first_read_after_producer_acceptance": False,
            "node0075_actual_8192_reads": False,
            "natural_terminal": False,
            "formal_d_match": False,
            "failure_classification_if_observed": (
                "instance scheduling/ordering first; not automatic RTL attribution"
            ),
        },
        "next_step": (
            "independent local validator, then fresh DIAGNOSTIC_ONLY server package "
            "with one read-only 32-stage observer"
        ),
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed_rule_ids": [
                "CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001",
                "CDA-SERVER-WORKLOAD-PROVENANCE-001",
                "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
            ],
            "rule_delta_proposal": [],
        },
    }
    write_json(OUT / "report.json", report)
    manifest_path = OUT / "artifact_manifest.json"
    write_json(
        manifest_path,
        {
            "schema": "node0071-node0075-native-ordering-artifact-manifest-v1",
            "test_id": TEST_ID,
            "files": file_records(OUT, excluded=(manifest_path,)),
        },
    )
    return report


def main() -> int:
    try:
        report = build()
    except (IntegrationError, OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"INTEGRATION_BUILD_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
