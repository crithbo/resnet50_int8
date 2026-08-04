#!/usr/bin/env python3
"""Materialize the native Decode SiLU stock-TB control and exact formal data."""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "ndp-sim/jsons/decode_silu_fp16N_fp32N.json"
ORACLE_SHA256 = "eafb7ec7cd47006dda15c1fc60d00601563a7a9f7e8ae12da3ce45e57baec6be"
GRAPH = (
    ROOT
    / "configs/native_ndp_sim/decode_silu_fp16N_fp32N_control_stocktb_v1/graph.json"
)
NATIVE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-decode-silu-control-stocktb-v1"
)
NATIVE_RUNS = ("native-tool-d", "native-tool-e")
NATIVE_REL = Path("ndp-sim/model_execplan/output/control_graph")
OUTPUT = (
    ROOT
    / "configs/native_ndp_sim/decode_silu_fp16N_fp32N_control_stocktb_v1/materialized"
)
REPORT = (
    NATIVE_ROOT / "local_materialization_report.json"
)
CONTRACT = (
    ROOT
    / "contracts/operator_config/decode_silu_fp16N_fp32N_control_stocktb_v1.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _records(root: Path, *, exclude: set[str] | None = None) -> dict[str, str]:
    omitted = exclude or set()
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in omitted
    }


def _round_fraction(value: Fraction) -> int:
    quotient, remainder = divmod(value.numerator, value.denominator)
    doubled = remainder * 2
    if doubled > value.denominator or (
        doubled == value.denominator and quotient & 1
    ):
        quotient += 1
    return quotient


def _fraction_to_fp32_bits(value: Fraction) -> int:
    if value == 0:
        return 0
    sign = int(value < 0)
    value = abs(value)
    numerator = value.numerator
    denominator = value.denominator
    exponent = numerator.bit_length() - denominator.bit_length()
    if exponent >= 0:
        if Fraction(1 << exponent, 1) > value:
            exponent -= 1
    elif Fraction(1, 1 << (-exponent)) > value:
        exponent -= 1
    if not -126 <= exponent <= 127:
        raise ValueError(f"golden result is not a normal FP32 value: {value}")
    shift = 23 - exponent
    scaled = value * (1 << shift) if shift >= 0 else value / (1 << (-shift))
    significand = _round_fraction(scaled)
    if significand == 1 << 24:
        significand >>= 1
        exponent += 1
    if not (1 << 23) <= significand < (1 << 24):
        raise ValueError(f"invalid normal FP32 significand: {significand}")
    return (sign << 31) | ((exponent + 127) << 23) | (
        significand - (1 << 23)
    )


def _fp32_fraction(bits: int) -> Fraction:
    sign = -1 if bits >> 31 else 1
    exponent = (bits >> 23) & 0xFF
    fraction = bits & 0x7FFFFF
    if exponent in {0, 0xFF}:
        raise ValueError(f"non-normal LUT FP32 word: 0x{bits:08x}")
    significand = (1 << 23) | fraction
    shift = exponent - 127 - 23
    value = (
        Fraction(sign * significand * (1 << shift), 1)
        if shift >= 0
        else Fraction(sign * significand, 1 << (-shift))
    )
    return value


def _fp16_bits(value: float) -> int:
    return int.from_bytes(struct.pack("<e", value), "little")


def _fp16_fraction(bits: int) -> Fraction:
    sign = -1 if bits >> 15 else 1
    exponent = (bits >> 10) & 0x1F
    fraction = bits & 0x3FF
    if exponent == 0:
        if fraction == 0:
            return Fraction(0)
        raise ValueError("formal input must not use FP16 subnormals")
    if exponent == 0x1F:
        raise ValueError("formal input must be finite")
    significand = (1 << 10) | fraction
    shift = exponent - 15 - 10
    return (
        Fraction(sign * significand * (1 << shift), 1)
        if shift >= 0
        else Fraction(sign * significand, 1 << (-shift))
    )


def _fp16_to_fp32_bits(bits: int) -> int:
    value = _fp16_fraction(bits)
    return 0 if value == 0 else _fraction_to_fp32_bits(value)


def _read_lut_words(path: Path) -> list[int]:
    file_words: list[int] = []
    hardware_words: list[int] = []
    for line in path.read_text(encoding="ascii").splitlines():
        if len(line) != 128 or set(line) - {"0", "1"}:
            raise ValueError("SiLU.txt is not canonical 128-bit text")
        # Slice_Config_Manager consumes the MSB-side 32-bit SFU table word
        # first within each 64-bit beat.  Global FIFO_128to64 emits the
        # low 64-bit half before the high half, so one textual 128-bit line
        # reaches the SFU table as lanes [2, 3, 0, 1].
        lanes = [
            int(line[offset : offset + 32], 2)
            for offset in range(0, 128, 32)
        ]
        file_words.extend(lanes)
        hardware_words.extend((lanes[2], lanes[3], lanes[0], lanes[1]))
    if len(file_words) != 200 or file_words[-3:] != [0, 0, 0]:
        raise ValueError("SiLU LUT exact shape/padding differs")
    return hardware_words


def _coefficient_index(x_bits: int, breakpoints: list[int]) -> int:
    x = _fp32_fraction(x_bits) if x_bits & 0x7FFFFFFF else Fraction(0)

    def ge(word: int) -> bool:
        threshold = (
            _fp32_fraction(word) if word & 0x7FFFFFFF else Fraction(0)
        )
        return x >= threshold

    address = int(ge(breakpoints[0]))
    for stage in range(1, 5):
        offset = (1 << stage) - 1
        address = (address << 1) | int(ge(breakpoints[offset + address]))
    address5 = address
    gt5 = ge(breakpoints[31 + address5])
    # RTL captures bst_search_addr_4[3], which is the MSB of the final
    # five-bit address after stage 4.
    boundary_select = (address5 >> 4) & 1
    ge_boundary = ge(breakpoints[63 + boundary_select])
    if not ge_boundary and boundary_select == 0:
        return 0
    if ge_boundary and boundary_select == 1:
        return 65
    return (address5 << 1) + (2 if gt5 else 1)


def _encode_128(words: list[int], width: int) -> str:
    return "".join(f"{word:0{width}b}" for word in reversed(words))


def _write_input(path: Path, fp16_values: list[int]) -> None:
    if len(fp16_values) != 32:
        raise ValueError("control input must contain exactly 32 FP16 values")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _encode_128(fp16_values[offset : offset + 8], 16)
        for offset in range(0, 32, 8)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def _write_golden(path: Path, fp32_values: list[int]) -> None:
    if len(fp32_values) != 32:
        raise ValueError("control golden must contain exactly 32 FP32 values")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        _encode_128(fp32_values[offset : offset + 4], 32)
        for offset in range(0, 32, 4)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def _golden_for_input(
    fp16_values: list[int], words: list[int]
) -> tuple[list[int], list[dict[str, Any]]]:
    breakpoints = words[:65]
    intercepts = words[65:131]
    slopes = words[131:197]
    outputs: list[int] = []
    evidence: list[dict[str, Any]] = []
    for input_bits in fp16_values:
        x_bits = _fp16_to_fp32_bits(input_bits)
        coefficient = _coefficient_index(x_bits, breakpoints)
        x = _fp16_fraction(input_bits)
        slope = _fp32_fraction(slopes[coefficient])
        intercept = _fp32_fraction(intercepts[coefficient])
        output_bits = _fraction_to_fp32_bits(x * slope + intercept)
        outputs.append(output_bits)
        evidence.append(
            {
                "input_fp16_bits": f"0x{input_bits:04x}",
                "converted_fp32_bits": f"0x{x_bits:08x}",
                "coefficient_index": coefficient,
                "slope_bits": f"0x{slopes[coefficient]:08x}",
                "intercept_bits": f"0x{intercepts[coefficient]:08x}",
                "output_fp32_bits": f"0x{output_bits:08x}",
            }
        )
    return outputs, evidence


def materialize() -> dict[str, Any]:
    if _sha256(ORACLE) != ORACLE_SHA256:
        raise RuntimeError("native Decode SiLU oracle identity differs")
    native = [NATIVE_ROOT / name / NATIVE_REL for name in NATIVE_RUNS]
    for path in native:
        if not path.is_dir():
            raise RuntimeError(f"missing isolated native run: {path}")
    excluded = {"config/op0/placement.png"}
    run_records = [_records(path, exclude=excluded) for path in native]
    if run_records[0] != run_records[1]:
        raise RuntimeError("fixed-seed empty-cache native outputs differ")
    bound_json = native[0] / "jsons/op0_decode_silu_fp16N_fp32N.json"
    bitstream = (
        native[0]
        / "config/op0/op0_decode_silu_fp16N_fp32N_bitstream_128b.bin"
    )
    if _sha256(bitstream) != (
        "7327afb213a7e6017bfb9150c92ed8adca6a430f62225a3f7625e896863ed083"
    ):
        raise RuntimeError("native fixed-seed bitstream identity differs")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    for relative in (
        "control_graph_withbaseaddr.json",
        "instructions_explained.txt",
        "sca_cfg.json",
        "sca_cfg_D.json",
        "jsons/op0_decode_silu_fp16N_fp32N.json",
        "config/op0/detailed_dump.txt",
        "config/op0/mapping_review.json",
        "config/op0/modules_dump_128b.bin",
        "config/op0/modules_dump_64b.bin",
        "config/op0/op0_decode_silu_fp16N_fp32N_bitstream_128b.bin",
        "config/op0/op0_decode_silu_fp16N_fp32N_bitstream_64b.bin",
        "config/op0/parsed_bitstream.txt",
        "install/execplan.txt",
        "install/execplan_op0.txt",
        "install/cfg_pkg/op0_decode_silu_fp16N_fp32N_bitstream_128b.bin",
        "install/cfg_pkg/SiLU.txt",
    ):
        _copy(native[0] / relative, OUTPUT / relative)

    lut_path = OUTPUT / "install/cfg_pkg/SiLU.txt"
    lut_words = _read_lut_words(lut_path)
    # Each 32-byte hardware transaction uses one value. This deliberately
    # removes any unproven lane-permutation assumption from the formal D gate.
    slice_values = {
        0: [-1.0] * 16 + [0.0] * 16,
        1: [-4.0] * 16 + [4.0] * 16,
    }
    golden_evidence: dict[str, Any] = {}
    for slice_id, values in slice_values.items():
        fp16_values = [_fp16_bits(value) for value in values]
        outputs, evidence = _golden_for_input(fp16_values, lut_words)
        input_path = (
            OUTPUT
            / f"install/op0/slice{slice_id:02d}/matrix_A_linearized_128bit.txt"
        )
        golden_path = (
            OUTPUT
            / f"golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        )
        _write_input(input_path, fp16_values)
        _write_golden(golden_path, outputs)
        golden_evidence[f"slice{slice_id:02d}"] = {
            "transaction_values": [values[0], values[16]],
            "input_sha256": _sha256(input_path),
            "golden_sha256": _sha256(golden_path),
            "unique_cases": [evidence[0], evidence[16]],
        }

    install_name = "decode_silu_fp16N_fp32N_control_stock_v1"
    prefix = f"../install/cfg_pkg/{install_name}"
    sca = {
        "Exec_Base": "0x0000_0C00",
        "Exec_Length": 3,
        "Repeat_Num": 1,
        "ExecutionPlan": {
            "base_addr": "0x00000C00",
            "path": f"{prefix}/install/execplan.txt",
        },
        "op0_matrixA_slice0": {
            "base_addr": "0x00000000",
            "path": f"{prefix}/install/op0/slice00/matrix_A_linearized_128bit.txt",
        },
        "op0_matrixA_slice1": {
            "base_addr": "0x02000000",
            "path": f"{prefix}/install/op0/slice01/matrix_A_linearized_128bit.txt",
        },
        "op0_config": {
            "base_addr": "0x00000400",
            "path": (
                f"{prefix}/install/cfg_pkg/"
                "op0_decode_silu_fp16N_fp32N_bitstream_128b.bin"
            ),
        },
        "op0_sfu_config": {
            "base_addr": "0x00000800",
            "path": f"{prefix}/install/cfg_pkg/SiLU.txt",
        },
    }
    sca_d = {
        f"op0_matrixD_slice{slice_id}": {
            "base_addr": f"0x{(slice_id << 25) + 0x40:08X}",
            "path": (
                "sim_results/formal_readback/"
                f"op0_matrixD_slice{slice_id}.txt"
            ),
            "length": 8,
        }
        for slice_id in (0, 1)
    }
    _write_json(OUTPUT / "runtime/sca_cfg.json", sca)
    _write_json(OUTPUT / "runtime/sca_cfg_D.json", sca_d)
    contract = {
        "schema": "decode-silu-fp16n-fp32n-stocktb-control-v1",
        "candidate_release": False,
        "counts_as_requant_e4": False,
        "counts_as_requant_e5": False,
        "claim": (
            "shared native SFU SiLU/fp16-to-fp32/normal-outbuffer path only"
        ),
        "claim_excludes": [
            "Requant guard semantics",
            "Requant round stage",
            "Requant alias lifetime",
            "Requant E4/E5",
        ],
        "oracle": {
            "path": ORACLE.relative_to(ROOT).as_posix(),
            "sha256": ORACLE_SHA256,
            "byte_identity_preserved": True,
        },
        "derived_address_bound_config": {
            "path": bound_json.relative_to(ROOT).as_posix(),
            "sha256": _sha256(bound_json),
            "is_oracle_byte_identity": False,
        },
        "native_rebuild": {
            "fixed_seed": 42,
            "independent_empty_cache_run_count": 2,
            "outputs_identical_excluding_visualization": True,
            "mapping_sha256": (
                "2b1c7bbe409a349c0ec668dc4030515dc1e99219a74c789b6a1677f25bbd2ff1"
            ),
            "bitstream_sha256": _sha256(bitstream),
        },
        "execution": {
            "active_slices": [0, 1],
            "slice_mask": "0x0000003",
            "repeat_num": 1,
            "start_comp_count": 1,
            "exec_lines_128bit": 3,
            "preload_count": 5,
            "formal_readback_count": 2,
            "formal_d_lines_per_slice": 8,
        },
        "golden": {
            "method": (
                "FP16 exact conversion, FIFO_128to64 low-half-before-high "
                "SFU load order, RTL BST coefficient selection, SiLU.txt "
                "FP32 slope/intercept, exact-rational fused multiply-add "
                "rounded once to FP32 RNE"
            ),
            "sfu_128b_to_32b_order": "text lanes [2,3,0,1] per 128-bit line",
            "sfu_consumed_word_count": 197,
            "not_high_precision_silu": True,
            "lane_layout_assumption_removed_by_uniform_32byte_transactions": True,
            "slices": golden_evidence,
        },
    }
    _write_json(CONTRACT, contract)
    report = {
        "schema": "decode-silu-control-local-materialization-report-v1",
        "status": "LOCAL_E2_MATERIALIZED_NOT_DYNAMIC",
        "candidate_release": False,
        "oracle_sha256": ORACLE_SHA256,
        "derived_graph_sha256": _sha256(GRAPH),
        "native_run_records_equal": True,
        "canonical_tree": _records(OUTPUT),
        "contract_path": CONTRACT.relative_to(ROOT).as_posix(),
        "contract_sha256": _sha256(CONTRACT),
    }
    _write_json(REPORT, report)
    return report


def main() -> int:
    try:
        result = materialize()
    except Exception as exc:
        print(f"decode SiLU control materialization failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
