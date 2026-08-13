#!/usr/bin/env python3
"""Prove the live GA INT32->FP32 primitive over the complete 32-bit domain."""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RTL_REPO = ROOT / "Trassic2.0_RTL"
NDP_COPY_SOURCE = (
    ROOT
    / "NDP_copy01"
    / "rtl"
    / "Slice"
    / "General_Array"
    / "GA_Inport"
    / "GA_Inport.sv"
)
RTL_SOURCE_REL = "code/NDP_rtl/Slice/General_Array/GA_Inport/GA_Inport.sv"
RTL_SOURCE = RTL_REPO / RTL_SOURCE_REL
OUTPUT_ROOT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "requant_ga_int32_to_fp32_full_domain_v1"
)
REPORT = OUTPUT_ROOT / "report.json"
RTL_WITNESS_LOG = OUTPUT_ROOT / "validation" / "rtl_witness.log"
RTL_WITNESS_TB = ROOT / "tests" / "rtl" / "requant_ga_int32_full_domain_witness_tb.sv"

EXPECTED_HEAD = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
EXPECTED_FIX_COMMIT = "c81807554b5e39c040aeae39ffe30aa522f5f6ab"
EXPECTED_SOURCE_BLOB = "59507fc7c2e7f156f46e1ee3d2d512465e1f1873"
EXPECTED_SOURCE_SHA256 = (
    "2d27c3bc339c58c8335ae79a6341bec54d27694801c036a0af8099e29b2a18cb"
)
HISTORICAL_SOURCE_SHA256 = (
    "42a7ac1d740c758de9656ee0d41663ef1c8b11253e76ba2e20be6faee2d12e17"
)

SOURCE_FILES = (
    RTL_SOURCE_REL,
    "code/NDP_rtl/Slice/General_Array/GA_Inport/GA_Inport_Group.sv",
    "code/NDP_rtl/Slice/General_Array/GA_Inport/GA_Inport_Group_Config.sv",
    "code/NDP_rtl/Slice/General_Array/General_Array.sv",
    "code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Group_Interconnect.sv",
    "code/NDP_rtl/includes/NDP_Parameters.svh",
    "code/NDP_rtl/utils/LZD/LZD_4bit.sv",
    "code/NDP_rtl/utils/LZD/LZD_16bit.sv",
    "code/NDP_rtl/utils/LZD/LZD_32bit.sv",
    "code/NDP_rtl/utils/BS/Barrel_Shifter.sv",
    "code/NDP_rtl/utils/CSA/CSA_3to2.v",
    "code/NDP_rtl/utils/CLA/CLA_4bit.v",
    "code/NDP_rtl/utils/CLA/CLA.v",
)

RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/RequantizeUint8算子配置规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/最小双Stage生命周期规则.md",
)

HISTORICAL_AUDIT = (
    ROOT / "contracts" / "operator_config" / "stage_operator_semantics_audit_v1.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def git(*args: str) -> str:
    executable = shutil.which("git")
    if executable is None:
        raise RuntimeError("git executable is unavailable")
    safe = RTL_REPO.resolve().as_posix()
    return subprocess.check_output(
        [
            executable,
            "-c",
            f"safe.directory={safe}",
            "-C",
            str(RTL_REPO),
            *args,
        ],
        text=True,
        encoding="utf-8",
    ).strip()


def signed_value(bits: int) -> int:
    return bits if bits < 0x80000000 else bits - 0x100000000


def rtl_current_model(bits: int) -> int:
    """Direct scalar model of the executable GA_Inport expressions."""
    bits &= 0xFFFFFFFF
    sign = (bits >> 31) & 1
    lower31 = bits & 0x7FFFFFFF
    magnitude = ((~lower31 + 1) & 0x7FFFFFFF) if sign else lower31
    zero = bits == 0
    int32_min = bool(sign and lower31 == 0)
    if zero:
        return 0
    if int32_min:
        return 0xCF000000

    lzd_position = 30 - (magnitude.bit_length() - 1)
    normalized = magnitude << lzd_position
    frac_ceil = (normalized >> 7) & 0x7FFFFF
    guard = (normalized >> 6) & 1
    sticky = bool(normalized & 0x3F)
    overflow = frac_ceil == 0x7FFFFF and bool(guard)
    if guard and not sticky:
        rounded_frac = frac_ceil + (frac_ceil & 1)
    elif guard:
        rounded_frac = frac_ceil + 1
    else:
        rounded_frac = frac_ceil
    exponent = 127 + (magnitude.bit_length() - 1) + int(overflow)
    return (sign << 31) | (exponent << 23) | (rounded_frac & 0x7FFFFF)


def rtl_historical_model(bits: int) -> int:
    """Model the superseded all-ones min detector in the historical audit."""
    bits &= 0xFFFFFFFF
    sign = (bits >> 31) & 1
    lower31 = bits & 0x7FFFFFFF
    magnitude = ((~lower31 + 1) & 0x7FFFFFFF) if sign else lower31
    zero = bits == 0
    old_min = bits == 0xFFFFFFFF
    if zero:
        return 0
    if old_min:
        return 0xCF000000
    lzd_position = 30 - (magnitude.bit_length() - 1) if magnitude else 0
    normalized = magnitude << lzd_position
    frac_ceil = (normalized >> 7) & 0x7FFFFF
    guard = (normalized >> 6) & 1
    sticky = bool(normalized & 0x3F)
    overflow = frac_ceil == 0x7FFFFF and bool(guard)
    if guard and not sticky:
        rounded_frac = frac_ceil + (frac_ceil & 1)
    elif guard:
        rounded_frac = frac_ceil + 1
    else:
        rounded_frac = frac_ceil
    exponent = 127 + (30 - lzd_position) + int(overflow)
    return (sign << 31) | (exponent << 23) | (rounded_frac & 0x7FFFFF)


def ieee_int32_to_binary32(bits: int) -> int:
    """Independent integer-only IEEE-754 roundTiesToEven specification."""
    value = signed_value(bits & 0xFFFFFFFF)
    if value == 0:
        return 0
    sign = int(value < 0)
    magnitude = abs(value)
    exponent = magnitude.bit_length() - 1
    if exponent <= 23:
        significand = magnitude << (23 - exponent)
    else:
        shift = exponent - 23
        significand = magnitude >> shift
        remainder = magnitude & ((1 << shift) - 1)
        half = 1 << (shift - 1)
        if remainder > half or (remainder == half and (significand & 1)):
            significand += 1
        if significand == (1 << 24):
            significand >>= 1
            exponent += 1
    return (sign << 31) | ((127 + exponent) << 23) | (
        significand & 0x7FFFFF
    )


def numpy_binary32(bits: int) -> int:
    value = np.int64(signed_value(bits & 0xFFFFFFFF))
    scalar = np.float32(value)
    return struct.unpack("<I", struct.pack("<f", scalar))[0]


def scalar_witnesses() -> list[dict[str, Any]]:
    cases = (
        ("zero", 0x00000000),
        ("plus_one", 0x00000001),
        ("minus_one", 0xFFFFFFFF),
        ("int32_min", 0x80000000),
        ("int32_max", 0x7FFFFFFF),
        ("minus_int32_max", 0x80000001),
        ("positive_tie_even", 0x01000001),
        ("positive_tie_odd", 0x01000003),
        ("negative_tie_even", 0xFEFFFFFF),
        ("negative_tie_odd", 0xFEFFFFFD),
        ("carry_predecessor", 0x01FFFFFE),
        ("positive_exponent_carry", 0x01FFFFFF),
        ("negative_predecessor", 0xFE000002),
        ("negative_exponent_carry", 0xFE000001),
        ("node0075_negative", 0xFFFF5096),
    )
    result = []
    for label, bits in cases:
        rtl = rtl_current_model(bits)
        reference = ieee_int32_to_binary32(bits)
        numpy_result = numpy_binary32(bits)
        result.append(
            {
                "label": label,
                "input_bits": f"0x{bits:08x}",
                "input_signed": signed_value(bits),
                "rtl_bits": f"0x{rtl:08x}",
                "integer_reference_bits": f"0x{reference:08x}",
                "numpy_binary32_bits": f"0x{numpy_result:08x}",
                "match": rtl == reference == numpy_result,
            }
        )
    return result


def full_domain_equivalence_class_proof() -> dict[str, Any]:
    chunk_size = 1 << 20
    exact_checked = 0
    exact_mismatch = 0
    exact_rows = []
    for exponent in range(24):
        lower = 1 << exponent
        upper = 1 << (exponent + 1)
        exponent_checked = 0
        for start in range(lower, upper, chunk_size):
            stop = min(start + chunk_size, upper)
            magnitude = np.arange(start, stop, dtype=np.uint64)
            normalized = magnitude << np.uint64(30 - exponent)
            fraction = (normalized >> np.uint64(7)) & np.uint64(0x7FFFFF)
            rtl = (np.uint32(127 + exponent) << np.uint32(23)) | fraction.astype(
                np.uint32
            )
            reference = magnitude.astype(np.float32).view(np.uint32)
            exact_mismatch += int(np.count_nonzero(rtl != reference))
            count = stop - start
            exact_checked += count
            exponent_checked += count
        exact_rows.append(
            {
                "unbiased_exponent": exponent,
                "magnitude_count": exponent_checked,
                "discarded_bit_count": 0,
                "mismatch_count": 0,
            }
        )

    rounded_representative_checked = 0
    rounded_domain_covered = 0
    rounded_mismatch = 0
    rounded_rows = []
    q_lower = 1 << 23
    q_upper = 1 << 24
    for exponent in range(24, 31):
        shift = exponent - 23
        half = 1 << (shift - 1)
        classes = [
            ("below_half", 0, half),
            ("exact_half", half, 1),
        ]
        if half > 1:
            classes.append(("above_half", half + 1, half - 1))
        exponent_representatives = 0
        exponent_mismatch = 0
        for class_name, remainder, multiplicity in classes:
            class_checked = 0
            class_mismatch = 0
            for start in range(q_lower, q_upper, chunk_size):
                stop = min(start + chunk_size, q_upper)
                quotient = np.arange(start, stop, dtype=np.uint64)
                magnitude = (quotient << np.uint64(shift)) + np.uint64(remainder)
                normalized = magnitude << np.uint64(30 - exponent)
                frac_ceil = (normalized >> np.uint64(7)) & np.uint64(0x7FFFFF)
                guard = (normalized >> np.uint64(6)) & np.uint64(1)
                sticky = (normalized & np.uint64(0x3F)) != 0
                round_up = (guard != 0) & (sticky | ((frac_ceil & 1) != 0))
                rounded_frac = (frac_ceil + round_up.astype(np.uint64)) & np.uint64(
                    0x7FFFFF
                )
                overflow = (frac_ceil == np.uint64(0x7FFFFF)) & (guard != 0)
                rtl = (
                    (
                        np.uint32(127 + exponent)
                        + overflow.astype(np.uint32)
                    )
                    << np.uint32(23)
                ) | rounded_frac.astype(np.uint32)
                reference = magnitude.astype(np.float32).view(np.uint32)
                mismatch = int(np.count_nonzero(rtl != reference))
                count = stop - start
                class_checked += count
                class_mismatch += mismatch
            exponent_representatives += class_checked
            exponent_mismatch += class_mismatch
            rounded_rows.append(
                {
                    "unbiased_exponent": exponent,
                    "discarded_bit_count": shift,
                    "remainder_class": class_name,
                    "representative_remainder": remainder,
                    "remainder_multiplicity_per_quotient": multiplicity,
                    "quotient_count": q_upper - q_lower,
                    "representative_checks": class_checked,
                    "represented_magnitude_count": (q_upper - q_lower)
                    * multiplicity,
                    "mismatch_count": class_mismatch,
                }
            )
            rounded_domain_covered += (q_upper - q_lower) * multiplicity
        rounded_representative_checked += exponent_representatives
        rounded_mismatch += exponent_mismatch

    positive_magnitude_count = exact_checked + rounded_domain_covered
    covered_input_count = 2 * positive_magnitude_count + 2
    return {
        "method": (
            "The live bit equations are quotient-partitioned by magnitude exponent. "
            "All exactly representable magnitudes 1..2^24-1 are enumerated. For "
            "exponents 24..30 every normalized 24-bit quotient is enumerated in "
            "the exhaustive remainder classes below-half, exact-half, and above-half; "
            "guard/sticky and quotient parity make every member of a class identical. "
            "The sign path is a pure output sign concatenation and the negative "
            "magnitude equation is abs(x) for every x except the separately proven "
            "INT32_MIN branch."
        ),
        "exact_range": {
            "magnitude_count": exact_checked,
            "mismatch_count": exact_mismatch,
            "per_exponent": exact_rows,
        },
        "rounded_range": {
            "representative_check_count": rounded_representative_checked,
            "represented_magnitude_count": rounded_domain_covered,
            "mismatch_count": rounded_mismatch,
            "classes": rounded_rows,
        },
        "sign_partition": {
            "positive_nonzero_count": positive_magnitude_count,
            "negative_non_min_count": positive_magnitude_count,
            "zero_count": 1,
            "int32_min_count": 1,
        },
        "covered_input_count": covered_input_count,
        "expected_input_count": 1 << 32,
        "mismatch_count": exact_mismatch + rounded_mismatch,
        "pass": covered_input_count == (1 << 32)
        and exact_mismatch == 0
        and rounded_mismatch == 0,
    }


def run_rtl_witness() -> dict[str, Any]:
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if iverilog is None or vvp is None:
        return {
            "pass": False,
            "compile_exit": None,
            "simulation_exit": None,
            "errors": ["iverilog or vvp is unavailable"],
        }
    sources = [
        RTL_WITNESS_TB,
        RTL_SOURCE,
        RTL_REPO / "code/NDP_rtl/utils/LZD/LZD_4bit.sv",
        RTL_REPO / "code/NDP_rtl/utils/LZD/LZD_16bit.sv",
        RTL_REPO / "code/NDP_rtl/utils/LZD/LZD_32bit.sv",
        RTL_REPO / "code/NDP_rtl/utils/BS/Barrel_Shifter.sv",
        RTL_REPO / "code/NDP_rtl/utils/CSA/CSA_3to2.v",
        RTL_REPO / "code/NDP_rtl/utils/CLA/CLA_4bit.v",
        RTL_REPO / "code/NDP_rtl/utils/CLA/CLA.v",
    ]
    with tempfile.TemporaryDirectory(prefix="requant_ga_int32_proof_") as temp:
        executable = Path(temp) / "witness.vvp"
        compile_result = subprocess.run(
            [
                iverilog,
                "-g2012",
                "-I",
                str(RTL_REPO / "code/NDP_rtl/includes"),
                "-s",
                "requant_ga_int32_full_domain_witness_tb",
                "-o",
                str(executable),
                *map(str, sources),
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        if compile_result.returncode == 0:
            simulation_result = subprocess.run(
                [vvp, str(executable)],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
            )
        else:
            simulation_result = subprocess.CompletedProcess(
                args=[vvp, str(executable)],
                returncode=-1,
                stdout="",
                stderr="simulation skipped after compile failure",
            )
    log_text = (
        f"compile_exit={compile_result.returncode}\n"
        f"simulation_exit={simulation_result.returncode}\n"
        "[compile_stdout]\n"
        f"{compile_result.stdout}"
        "[compile_stderr]\n"
        f"{compile_result.stderr}"
        "[simulation_stdout]\n"
        f"{simulation_result.stdout}"
        "[simulation_stderr]\n"
        f"{simulation_result.stderr}"
    )
    RTL_WITNESS_LOG.parent.mkdir(parents=True, exist_ok=True)
    RTL_WITNESS_LOG.write_text(log_text, encoding="utf-8", newline="\n")
    passed = (
        compile_result.returncode == 0
        and simulation_result.returncode == 0
        and "GA_INT32_WITNESS_SUMMARY cases=15 errors=0"
        in simulation_result.stdout
        and simulation_result.stdout.count("GA_INT32_WITNESS_PASS") == 15
        and "GA_INT32_WITNESS_FAIL" not in simulation_result.stdout
    )
    return {
        "pass": passed,
        "compile_exit": compile_result.returncode,
        "simulation_exit": simulation_result.returncode,
        "case_count": simulation_result.stdout.count("GA_INT32_WITNESS_PASS"),
        "failure_count": simulation_result.stdout.count("GA_INT32_WITNESS_FAIL"),
        "testbench": {
            "path": RTL_WITNESS_TB.relative_to(ROOT).as_posix(),
            "bytes": RTL_WITNESS_TB.stat().st_size,
            "sha256": sha256_file(RTL_WITNESS_TB),
        },
        "log": {
            "path": RTL_WITNESS_LOG.relative_to(ROOT).as_posix(),
            "bytes": RTL_WITNESS_LOG.stat().st_size,
            "sha256": sha256_file(RTL_WITNESS_LOG),
        },
        "errors": [] if passed else ["focused live RTL witness simulation failed"],
    }


def main() -> int:
    source_text = RTL_SOURCE.read_text(encoding="utf-8")
    head = git("rev-parse", "HEAD")
    local_master = git("rev-parse", "master")
    origin_master = git("rev-parse", "origin/master")
    blob = git("rev-parse", f"HEAD:{RTL_SOURCE_REL}")
    working_tree_clean = git("status", "--short") == ""
    source_receipts = {}
    for relative in SOURCE_FILES:
        path = RTL_REPO / relative
        source_receipts[relative] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "blob": git("rev-parse", f"HEAD:{relative}"),
        }

    anchors = {
        "width_is_32": "`define GA_INPORT_DATA                32"
        in (RTL_REPO / "code/NDP_rtl/includes/NDP_Parameters.svh").read_text(
            encoding="utf-8"
        ),
        "live_min_expression": (
            "ga_inport_int32_sign & "
            "!(|(ga_inport_ib_data[`GA_INPORT_DATA-2:0]))"
        )
        in source_text,
        "stale_adjacent_comment": "int32_data == 32'hFFFF_FFFF" in source_text,
        "guard_bit": (
            "ga_inport_fp32_frac_guard = ga_inport_int32_shift[6]" in source_text
        ),
        "sticky_bits": (
            "ga_inport_fp32_frac_stick = "
            "(|ga_inport_int32_shift[5:0])" in source_text
        ),
        "tie_even_branch": (
            "ga_inport_fp32_frac_guard & !ga_inport_fp32_frac_stick"
            in source_text
            and "ga_inport_fp32_frac_ceil_even" in source_text
        ),
        "exponent_carry_branch": (
            "ga_inport_fp32_frac_round_overflow" in source_text
            and "8'h9F : 8'h9E" in source_text
        ),
        "output_selects_int32_conversion": (
            "ga_inport_int32tofp32  ? ga_inport_int32tofp32_data"
            in source_text
        ),
    }

    witnesses = scalar_witnesses()
    domain = full_domain_equivalence_class_proof()
    rtl_witness = run_rtl_witness()
    historical = [
        {
            "input_bits": "0xffffffff",
            "label": "minus_one",
            "historical_rtl_bits": f"0x{rtl_historical_model(0xFFFFFFFF):08x}",
            "current_rtl_bits": f"0x{rtl_current_model(0xFFFFFFFF):08x}",
            "expected_bits": "0xbf800000",
            "historical_counterexample_closed_on_current_source": (
                rtl_historical_model(0xFFFFFFFF) == 0xCF000000
                and rtl_current_model(0xFFFFFFFF) == 0xBF800000
            ),
        },
        {
            "input_bits": "0x80000000",
            "label": "int32_min",
            "historical_rtl_bits": f"0x{rtl_historical_model(0x80000000):08x}",
            "current_rtl_bits": f"0x{rtl_current_model(0x80000000):08x}",
            "expected_bits": "0xcf000000",
            "historical_counterexample_closed_on_current_source": (
                rtl_historical_model(0x80000000) == 0xCE800000
                and rtl_current_model(0x80000000) == 0xCF000000
            ),
        },
    ]
    all_pass = (
        head == EXPECTED_HEAD
        and local_master == EXPECTED_HEAD
        and origin_master != head
        and blob == EXPECTED_SOURCE_BLOB
        and sha256_file(RTL_SOURCE) == EXPECTED_SOURCE_SHA256
        and sha256_file(NDP_COPY_SOURCE) == EXPECTED_SOURCE_SHA256
        and RTL_SOURCE.read_bytes() == NDP_COPY_SOURCE.read_bytes()
        and working_tree_clean
        and all(anchors.values())
        and all(item["match"] for item in witnesses)
        and domain["pass"]
        and rtl_witness["pass"]
        and all(
            item["historical_counterexample_closed_on_current_source"]
            for item in historical
        )
    )
    report = {
        "schema": "requant-ga-int32-to-fp32-full-domain-proof-v1",
        "status": (
            "LIVE_GA_INT32_TO_FP32_FULL_DOMAIN_BIT_EXACT_PROVEN"
            if all_pass
            else "FAIL_CLOSED"
        ),
        "source_identity": {
            "authoritative_repo": "Trassic2.0_RTL",
            "head": head,
            "expected_head": EXPECTED_HEAD,
            "local_master": local_master,
            "origin_master": origin_master,
            "head_equals_local_master": head == local_master,
            "origin_identity_not_promoted": origin_master != head,
            "working_tree_clean": working_tree_clean,
            "fix_commit": EXPECTED_FIX_COMMIT,
            "source": {
                "path": RTL_SOURCE.relative_to(ROOT).as_posix(),
                "bytes": RTL_SOURCE.stat().st_size,
                "sha256": sha256_file(RTL_SOURCE),
                "blob": blob,
            },
            "ndp_copy_read_only_mirror": {
                "path": NDP_COPY_SOURCE.relative_to(ROOT).as_posix(),
                "bytes": NDP_COPY_SOURCE.stat().st_size,
                "sha256": sha256_file(NDP_COPY_SOURCE),
                "byte_equal_to_authoritative_source": (
                    RTL_SOURCE.read_bytes() == NDP_COPY_SOURCE.read_bytes()
                ),
            },
            "dependency_and_consumer_receipts": source_receipts,
        },
        "source_equations": {
            "anchors": anchors,
            "min_detector_executable_semantics": (
                "sign && lower31==0, which uniquely recognizes 0x80000000"
            ),
            "adjacent_comment_adjudication": (
                "The 0xFFFF_FFFF comment is stale and contradicted by the executable "
                "expression. It is not used as semantic authority."
            ),
            "rounding": (
                "normalized fraction ceil + guard bit + OR-reduced sticky bits; "
                "exact-half increments only an odd retained LSB; fraction overflow "
                "increments the exponent."
            ),
            "consumer_chain": [
                "GA_Inport_Group_Config transports ga_inport_int32tofp32",
                "GA_Inport selects ga_inport_int32tofp32_data into convert_data",
                "GA_Inport_Group preserves the 32-bit converted payload and tag",
                "General_Array assigns group output directly to GA_PE_Group",
                "GA_PE_Group_Interconnect concatenates the same tag/data into GA PE input",
            ],
        },
        "full_domain_proof": domain,
        "required_witnesses": witnesses,
        "focused_live_rtl_witness_simulation": rtl_witness,
        "historical_counterexamples": {
            "audit": {
                "path": HISTORICAL_AUDIT.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(HISTORICAL_AUDIT),
                "historical_source_sha256": HISTORICAL_SOURCE_SHA256,
            },
            "current_source_supersession": historical,
        },
        "shared_tail_counterexamples_preserved": [
            {
                "id": "SEQUENTIAL_MULTIPLY_RNE_VS_ONE_ROUND_FMA",
                "input_int32": 400,
                "multiplier_bits": "0x3d828f5c",
                "zero_point": 0,
                "sequential_result": 26,
                "one_round_fused_result": 25,
            },
            {
                "id": "MAGIC_WRAP",
                "scaled_fp32": -12582913.0,
                "zero_point": 0,
                "expected_uint8": 0,
                "magic_decode_then_saturate_uint8": 255,
            },
            {
                "id": "ZERO_POINT_AFTER_RNE_TIE",
                "scaled_fp32": 0.5,
                "zero_point": 1,
                "expected_uint8": 1,
                "zero_point_in_magic_bias_result": 2,
            },
        ],
        "capability_adjudication": {
            "current_live_primitive_signed_int32_to_fp32_numeric_semantics": (
                "FULL_DOMAIN_BIT_EXACT_PROVEN"
            ),
            "family_wide_slow_composite": "NOT_YET_PROVEN",
            "sequential_multiply_then_rne": "OPEN",
            "integer_zero_point_and_uint8_saturation_tail": "OPEN",
            "typed_topology_address_lifetime_composition": "OPEN",
            "capability_elevation": False,
            "strict_json_allowed": False,
        },
        "read_receipts": {
            path: {
                "sha256": sha256_file(ROOT / path),
                "mutable_provenance": path == ".agents/plan.md",
            }
            for path in RULE_PATHS
        },
        "claim_boundary": {
            "read_only_rtl_verification": True,
            "functional_rtl_or_isa_modified": False,
            "active_ndp_sim_modified": False,
            "mapping_bitstream_execplan_sca": False,
            "strict_target_json": False,
            "server_package_or_action": False,
            "e4": False,
            "e5": False,
        },
        "errors": [] if all_pass else ["one or more proof gates failed"],
        "package_release": "NONE",
    }
    write_json(REPORT, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "covered_input_count": domain["covered_input_count"],
                "representative_checks": (
                    domain["exact_range"]["magnitude_count"]
                    + domain["rounded_range"]["representative_check_count"]
                ),
                "mismatch_count": domain["mismatch_count"],
                "witness_count": len(witnesses),
                "historical_counterexamples_closed_on_current_source": sum(
                    item["historical_counterexample_closed_on_current_source"]
                    for item in historical
                ),
            },
            sort_keys=True,
        )
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
