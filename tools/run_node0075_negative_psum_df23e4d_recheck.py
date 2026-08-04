from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import struct
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_OUTPUT = Path(
    "outputs/node0075_negative_psum_df23e4d_revalidation/"
    "current_rtl_and_recurrence.json"
)
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
A_REL = Path("artifacts/w3/golden_batch16/tensors/tensor-6fbd5707d5f08110.npy")
ACC_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0075-accumulate.npy"
)
WEIGHT_NAME = "resnetv17_dense0_weight_quantized"
MASK32 = (1 << 32) - 1
INT32_SIGN = 1 << 31
INT32_MIN = -(1 << 31)
INT32_MAX = (1 << 31) - 1

EXPECTED_IDENTITY = {
    "trassic_commit": "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727",
    "SA_PE_Float_CSA.v": (
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
    ),
    "SA_PE_Float_Control.v": (
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
    ),
    "sync_report": (
        "6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5"
    ),
}

SOURCES = (
    Path("NDP_copy01/rtl/utils/DW02_mult/DW02_mult.v"),
    Path("NDP_copy01/rtl/utils/DW01_add/DW01_add.v"),
    Path("NDP_copy01/rtl/utils/CSA/CSA_4to2.v"),
    Path("NDP_copy01/rtl/utils/CSA/CSA_3to2.v"),
    Path("NDP_copy01/rtl/utils/CLA/CLA_4bit.v"),
    Path("NDP_copy01/rtl/utils/CLA/CLA.v"),
    Path("NDP_copy01/rtl/utils/FCTLZ/f_ctlz.v"),
    Path("NDP_copy01/rtl/utils/FADDONE/f_addone.v"),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_Control.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_Expdiff.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Mul_Array.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_CSA.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_LZA.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_SHT.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_Expadj.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_PE_Float_Last.v"
    ),
    Path(
        "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
        "SA_PE_ALU/SA_ALU.v"
    ),
    Path("tests/rtl/node0075_negative_psum_df23e4d_recheck_tb.sv"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def to_s32_scalar(value: int) -> int:
    bits = int(value) & MASK32
    return bits - (1 << 32) if bits >= INT32_SIGN else bits


def to_s32_array(value: np.ndarray) -> np.ndarray:
    bits = np.bitwise_and(value.astype(np.int64, copy=False), MASK32)
    return np.where(bits >= INT32_SIGN, bits - (1 << 32), bits)


def pack_word(values: list[int]) -> int:
    padded = values + [0] * (4 - len(values))
    if len(padded) != 4:
        raise ValueError("one SA occurrence requires one to four lanes")
    word = 0
    for value in padded:
        word = (word << 8) | (int(value) & 0xFF)
    return word


def load_weight(model_path: Path) -> np.ndarray:
    import onnx
    from onnx import numpy_helper

    model = onnx.load(model_path.as_posix(), load_external_data=True)
    matches = [
        numpy_helper.to_array(item)
        for item in model.graph.initializer
        if item.name == WEIGHT_NAME
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {WEIGHT_NAME}, found {len(matches)}")
    weight = np.ascontiguousarray(matches[0])
    if weight.dtype != np.int8 or weight.shape != (2048, 1000):
        raise RuntimeError(f"unexpected node0075 weight {weight.dtype} {weight.shape}")
    return weight


def scan_frozen_recurrence(root: Path) -> dict[str, Any]:
    activation = np.load(root / A_REL, allow_pickle=False)
    formal = np.load(root / ACC_REL, allow_pickle=False)
    weight = load_weight(root / MODEL_REL)
    if activation.dtype != np.uint8 or activation.shape != (16, 2048):
        raise RuntimeError(
            f"unexpected node0075 activation {activation.dtype} {activation.shape}"
        )
    if formal.dtype != np.int32 or formal.shape != (16, 1000):
        raise RuntimeError(f"unexpected accumulator {formal.dtype} {formal.shape}")

    hits: list[dict[str, Any]] = []
    final_rows: list[np.ndarray] = []
    negative_count = 0
    negative_to_zero = 0
    occurrence_count = 0
    dot_min = 1 << 62
    dot_max = -(1 << 62)
    psum_min = 1 << 62
    psum_max = -(1 << 62)

    for m_index in range(16):
        psum = np.zeros(1000, dtype=np.int64)
        for group_index in range(512):
            k_start = group_index * 4
            a_lanes = activation[m_index, k_start : k_start + 4].astype(np.int64)
            b_lanes = weight[k_start : k_start + 4, :].astype(np.int64)
            dot4 = np.sum(a_lanes[:, None] * b_lanes, axis=0)
            next_psum = psum + dot4
            negative = psum < 0
            exact_zero = negative & (next_psum == 0)

            occurrence_count += int(dot4.size)
            negative_count += int(np.count_nonzero(negative))
            negative_to_zero += int(np.count_nonzero(exact_zero))
            dot_min = min(dot_min, int(dot4.min()))
            dot_max = max(dot_max, int(dot4.max()))
            psum_min = min(psum_min, int(psum.min()))
            psum_max = max(psum_max, int(psum.max()))

            for n_index in np.flatnonzero(exact_zero):
                b_values = b_lanes[:, n_index]
                hits.append(
                    {
                        "m": m_index,
                        "n": int(n_index),
                        "k_group": group_index,
                        "a_u8_lanes": [int(item) for item in a_lanes],
                        "b_s8_lanes": [int(item) for item in b_values],
                        "lane_products": [
                            int(left) * int(right)
                            for left, right in zip(a_lanes, b_values, strict=True)
                        ],
                        "psum_in_s32": int(psum[n_index]),
                        "dot4_s32": int(dot4[n_index]),
                        "expected_next_s32": 0,
                    }
                )
            psum = to_s32_array(next_psum)
        final_rows.append(psum.astype(np.int32))

    computed = np.stack(final_rows)
    ordered_hits = sorted(hits, key=lambda item: (item["m"], item["n"], item["k_group"]))
    stream_hits = sorted(hits, key=lambda item: (item["m"], item["k_group"], item["n"]))
    return {
        "implementation": (
            "fresh direct m->k_group recurrence under frozen node0075 inputs; "
            "no prior reachability report imported"
        ),
        "planned_occurrences": 16 * 512 * 1000,
        "enumerated_occurrences": occurrence_count,
        "complete": occurrence_count == 16 * 512 * 1000,
        "negative_psum_occurrences": negative_count,
        "negative_to_exact_zero": negative_to_zero,
        "dot4_range": [dot_min, dot_max],
        "psum_in_range": [psum_min, psum_max],
        "boundary_hit_digest": canonical_sha256(ordered_hits),
        "first_stream_order_hit": stream_hits[0] if stream_hits else None,
        "first_lexicographic_hit": ordered_hits[0] if ordered_hits else None,
        "exact_zero_hits": ordered_hits,
        "formal_accumulator_mismatch_count": int(np.count_nonzero(computed != formal)),
        "formal_accumulator_match": bool(np.array_equal(computed, formal)),
        "computed_accumulator_sha256": hashlib.sha256(
            np.ascontiguousarray(computed.astype("<i4")).tobytes()
        ).hexdigest(),
        "input_receipts": {
            A_REL.as_posix(): sha256_file(root / A_REL),
            ACC_REL.as_posix(): sha256_file(root / ACC_REL),
            MODEL_REL.as_posix(): sha256_file(root / MODEL_REL),
            "weight_initializer_value_sha256": hashlib.sha256(
                np.ascontiguousarray(weight).tobytes()
            ).hexdigest(),
        },
    }


def make_case(
    category: str,
    weights: list[int],
    activations: list[int],
    psum: int,
    expected: int,
    label: str | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "label": label,
        "data_a": pack_word(weights),
        "data_b": pack_word(activations),
        "data_c": int(psum) & MASK32,
        "expected": int(expected) & MASK32,
    }


def build_rtl_cases(scan: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    first = scan["first_stream_order_hit"]
    for label, psum, expected in (
        ("neg20_plus19", -20, -1),
        ("neg19_plus19", -19, 0),
        ("neg18_plus19", -18, 1),
        ("zero_plus19", 0, 19),
        ("pos7_plus19", 7, 26),
    ):
        cases.append(
            make_case(
                "directed_adjacent",
                first["b_s8_lanes"],
                first["a_u8_lanes"],
                psum,
                expected,
                label,
            )
        )

    for hit_index, hit in enumerate(scan["exact_zero_hits"]):
        cases.append(
            make_case(
                "frozen_exact_cancellation",
                hit["b_s8_lanes"],
                hit["a_u8_lanes"],
                hit["psum_in_s32"],
                0,
                f"hit-{hit_index:03d}",
            )
        )

    acceptance_vectors = (
        ("carry_duplicate_positive", [1, 1, 1, 1], [1, 1, 1, 1], 0, 0),
        ("carry_duplicate_negative", [-1, -1, -1, -1], [1, 1, 1, 1], 0, 0),
        ("signed18_positive_extreme", [127] * 4, [255] * 4, 0, 0),
        ("signed18_negative_extreme", [-128] * 4, [255] * 4, 0, 0),
        ("psum_positive_wrap", [1], [1], 0, INT32_MAX),
        ("psum_negative_wrap", [-1], [1], 0, INT32_MIN),
        ("tail_k3_bias_on", [1, -2, 3], [4, 5, 6], 0, 7),
        ("tail_k5", [1, -2, 3, -4, 5], [6, 7, 8, 9, 10], 0, 0),
        ("tail_k6", [1, -2, 3, -4, 5, -6], [6, 7, 8, 9, 10, 11], 0, 0),
        ("tail_k7", [1, -2, 3, -4, 5, -6, 7], [6, 7, 8, 9, 10, 11, 12], 0, 0),
        (
            "nonzero_xzp_bias_on",
            [3, -2, 1, 5, -7],
            [120, 114, 130, 90, 200],
            114,
            -123456,
        ),
    )
    acceptance_occurrences = 0
    for label, weights, activations, x_zero_point, bias in acceptance_vectors:
        psum = to_s32_scalar(bias - x_zero_point * sum(weights))
        for offset in range(0, len(weights), 4):
            w_chunk = weights[offset : offset + 4]
            a_chunk = activations[offset : offset + 4]
            expected = to_s32_scalar(psum + sum(w * a for w, a in zip(w_chunk, a_chunk)))
            cases.append(
                make_case(
                    "acceptance_vectors",
                    w_chunk,
                    a_chunk,
                    psum,
                    expected,
                    f"{label}/occurrence-{offset // 4}",
                )
            )
            psum = expected
            acceptance_occurrences += 1

    pair_domain = tuple(itertools.product((-3, 0, 3), (0, 1, 7)))
    small_domain_count = 0
    small_domain_digest = hashlib.sha256()
    for length in (1, 2, 3, 4):
        for pairs in itertools.product(pair_domain, repeat=length):
            weights = [pair[0] for pair in pairs]
            activations = [pair[1] for pair in pairs]
            for x_zero_point in (0, 2):
                for bias in (0, -11, INT32_MAX):
                    psum = to_s32_scalar(bias - x_zero_point * sum(weights))
                    expected = to_s32_scalar(
                        psum + sum(w * a for w, a in zip(weights, activations))
                    )
                    case = make_case(
                        "small_domain_exhaustive", weights, activations, psum, expected
                    )
                    cases.append(case)
                    small_domain_digest.update(
                        struct.pack(
                            "<4I",
                            case["data_a"],
                            case["data_b"],
                            case["data_c"],
                            case["expected"],
                        )
                    )
                    small_domain_count += 1

    single_product_count = 0
    for weight in range(-128, 128):
        for activation in range(256):
            expected = to_s32_scalar(INT32_MAX + weight * activation)
            cases.append(
                make_case(
                    "single_product_full_domain",
                    [weight],
                    [activation],
                    INT32_MAX,
                    expected,
                )
            )
            single_product_count += 1

    corner_count = 0
    for pairs in itertools.product(
        tuple(itertools.product((-128, 127), (0, 255))), repeat=4
    ):
        weights = [pair[0] for pair in pairs]
        activations = [pair[1] for pair in pairs]
        expected = to_s32_scalar(sum(w * a for w, a in zip(weights, activations)))
        cases.append(
            make_case("four_lane_corner_cross_product", weights, activations, 0, expected)
        )
        corner_count += 1

    coverage = {
        "directed_adjacent": 5,
        "frozen_exact_cancellation": len(scan["exact_zero_hits"]),
        "acceptance_vector_occurrences": acceptance_occurrences,
        "small_domain_exhaustive": {
            "case_count": small_domain_count,
            "stimulus_sha256": small_domain_digest.hexdigest(),
        },
        "single_product_full_domain": single_product_count,
        "four_lane_corner_cross_product": corner_count,
        "total_rtl_occurrences": len(cases),
    }
    return cases, coverage


def write_hex(path: Path, values: list[int]) -> None:
    path.write_text(
        "".join(f"{value & MASK32:08x}\n" for value in values),
        encoding="ascii",
        newline="\n",
    )


def verify_identity(root: Path) -> dict[str, Any]:
    paths = {
        "SA_PE_Float_CSA.v": SOURCES[11],
        "SA_PE_Float_Control.v": SOURCES[8],
        "sync_report": Path("artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json"),
    }
    observed = {label: sha256_file(root / path) for label, path in paths.items()}
    mismatches = {
        label: {"expected": EXPECTED_IDENTITY[label], "observed": observed[label]}
        for label in paths
        if observed[label] != EXPECTED_IDENTITY[label]
    }
    if mismatches:
        raise RuntimeError(f"df23e4d identity mismatch: {mismatches}")
    return {**EXPECTED_IDENTITY, "observed_sha256": observed}


def run_rtl(
    root: Path,
    cases: list[dict[str, Any]],
    output_dir: Path,
) -> dict[str, Any]:
    missing = [item.as_posix() for item in SOURCES if not (root / item).is_file()]
    if missing:
        raise RuntimeError(f"missing RTL inputs: {missing}")
    iverilog = Path(r"C:\iverilog\bin\iverilog.exe")
    vvp = Path(r"C:\iverilog\bin\vvp.exe")
    if not iverilog.is_file() or not vvp.is_file():
        raise RuntimeError("Icarus executable pair unavailable")

    output_dir.mkdir(parents=True, exist_ok=True)
    memory_paths = {
        "data_a": output_dir / "data_a.hex",
        "data_b": output_dir / "data_b.hex",
        "data_c": output_dir / "data_c.hex",
        "expected": output_dir / "expected.hex",
    }
    for field, path in memory_paths.items():
        write_hex(path, [case[field] for case in cases])

    with tempfile.TemporaryDirectory(prefix="node0075-df23e4d-") as tmp:
        binary = Path(tmp) / "node0075_df23e4d.vvp"
        compile_argv = [
            str(iverilog),
            "-g2012",
            "-s",
            "node0075_negative_psum_df23e4d_recheck_tb",
            "-o",
            str(binary),
            *[str(root / item) for item in SOURCES],
        ]
        compile_run = subprocess.run(
            compile_argv, cwd=root, text=True, capture_output=True, check=False
        )
        sim_argv = [
            str(vvp),
            str(binary),
            f"+DATA_A={memory_paths['data_a'].as_posix()}",
            f"+DATA_B={memory_paths['data_b'].as_posix()}",
            f"+DATA_C={memory_paths['data_c'].as_posix()}",
            f"+EXPECTED={memory_paths['expected'].as_posix()}",
            f"+COUNT={len(cases)}",
        ]
        sim_run = None
        if compile_run.returncode == 0:
            sim_run = subprocess.run(
                sim_argv, cwd=root, text=True, capture_output=True, check=False
            )

    stdout = "" if sim_run is None else sim_run.stdout
    stderr = "" if sim_run is None else sim_run.stderr
    stdout_path = output_dir / "rtl_simulation.log"
    stderr_path = output_dir / "rtl_simulation.stderr.log"
    stdout_path.write_text(stdout, encoding="utf-8", newline="\n")
    stderr_path.write_text(stderr, encoding="utf-8", newline="\n")

    case_pattern = re.compile(
        r"NODE0075_DF23_CASE index=(\d+) data_a=([0-9a-fA-F]{8}) "
        r"data_b=([0-9a-fA-F]{8}) psum=([0-9a-fA-F]{8}) "
        r"raw=([0-9a-fA-F]{8}) result=([0-9a-fA-F]{8}) "
        r"expected=([0-9a-fA-F]{8}) match=([01])"
    )
    parsed: dict[int, dict[str, Any]] = {}
    ordered_digest = hashlib.sha256()
    category_counts: Counter[str] = Counter()
    category_mismatches: Counter[str] = Counter()
    mismatch_examples: list[dict[str, Any]] = []
    for match in case_pattern.finditer(stdout):
        index = int(match.group(1))
        observed = int(match.group(6), 16)
        expected = int(match.group(7), 16)
        matches = match.group(8) == "1" and observed == expected
        if index >= len(cases):
            continue
        case = cases[index]
        category = case["category"]
        category_counts[category] += 1
        if not matches:
            category_mismatches[category] += 1
            if len(mismatch_examples) < 16:
                mismatch_examples.append(
                    {
                        "index": index,
                        "category": category,
                        "label": case.get("label"),
                        "observed": f"0x{observed:08x}",
                        "expected": f"0x{expected:08x}",
                    }
                )
        parsed[index] = {
            "observed": observed,
            "expected": expected,
            "matches": matches,
            "raw": int(match.group(5), 16),
        }
        ordered_digest.update(
            struct.pack(
                "<6I",
                index,
                int(match.group(2), 16),
                int(match.group(3), 16),
                int(match.group(4), 16),
                observed,
                expected,
            )
        )

    summary_match = re.search(
        r"NODE0075_DF23_SUMMARY count=(\d+) mismatches=(\d+) "
        r"marker=(\S+)",
        stdout,
    )
    directed = {}
    for index, case in enumerate(cases[:5]):
        result = parsed.get(index)
        directed[case["label"]] = None if result is None else {
            "observed_bits": f"0x{result['observed']:08x}",
            "expected_bits": f"0x{result['expected']:08x}",
            "csa_raw_bits": f"0x{result['raw']:08x}",
            "pass": result["matches"],
        }

    return {
        "compile_exit": compile_run.returncode,
        "simulation_exit": None if sim_run is None else sim_run.returncode,
        "requested_case_count": len(cases),
        "parsed_case_count": len(parsed),
        "all_cases_observed": len(parsed) == len(cases),
        "mismatch_count": sum(category_mismatches.values()),
        "category_case_count": dict(sorted(category_counts.items())),
        "category_mismatch_count": dict(sorted(category_mismatches.items())),
        "mismatch_examples": mismatch_examples,
        "directed_cases": directed,
        "summary": None if summary_match is None else {
            "count": int(summary_match.group(1)),
            "mismatches": int(summary_match.group(2)),
            "marker": summary_match.group(3),
        },
        "ordered_rtl_observation_sha256": ordered_digest.hexdigest(),
        "memory_receipts": {
            path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in memory_paths.values()
        },
        "stdout_receipt": {
            "path": stdout_path.relative_to(root).as_posix(),
            "sha256": sha256_file(stdout_path),
            "bytes": stdout_path.stat().st_size,
        },
        "stderr_receipt": {
            "path": stderr_path.relative_to(root).as_posix(),
            "sha256": sha256_file(stderr_path),
            "bytes": stderr_path.stat().st_size,
        },
        "source_receipts": {item.as_posix(): sha256_file(root / item) for item in SOURCES},
        "tool": {
            "iverilog": str(iverilog),
            "vvp": str(vvp),
            "top": "node0075_negative_psum_df23e4d_recheck_tb",
            "flags": ["-g2012"],
        },
        "compile_stdout": compile_run.stdout,
        "compile_stderr": compile_run.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output

    identity = verify_identity(root)
    scan = scan_frozen_recurrence(root)
    cases, coverage = build_rtl_cases(scan)
    rtl = run_rtl(root, cases, output.parent)
    blocker_closed = (
        scan["complete"]
        and scan["enumerated_occurrences"] == 8_192_000
        and scan["negative_to_exact_zero"] == 272
        and scan["formal_accumulator_match"]
        and rtl["compile_exit"] == 0
        and rtl["simulation_exit"] == 0
        and rtl["all_cases_observed"]
        and rtl["mismatch_count"] == 0
        and rtl["category_case_count"].get("frozen_exact_cancellation") == 272
        and rtl["summary"] == {
            "count": len(cases),
            "mismatches": 0,
            "marker": "RTL_REPAIR_FULL_REACHABLE_PASS",
        }
    )

    receipt = {
        "schema": "resnet50-node0075-df23e4d-revalidation-run-v1",
        "status": (
            "BLOCKER_CLOSED_CURRENT_RTL_FULL_REACHABLE_PASS"
            if blocker_closed
            else "FAIL_CLOSED_REVALIDATION_INCONCLUSIVE"
        ),
        "blocker": "B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE",
        "blocker_closed": blocker_closed,
        "current_rtl_identity": identity,
        "frozen_recurrence": scan,
        "current_source_rtl_gate": rtl,
        "domain_coverage": coverage,
        "decision_inputs": {
            "full_recurrence_enumerated": scan["enumerated_occurrences"],
            "formal_final_match": scan["formal_accumulator_match"],
            "reachable_exact_cancellations": scan["negative_to_exact_zero"],
            "reachable_exact_cancellations_rtl_tested": rtl[
                "category_case_count"
            ].get("frozen_exact_cancellation", 0),
            "rtl_occurrences_tested": rtl["parsed_case_count"],
            "rtl_mismatches": rtl["mismatch_count"],
        },
        "claim_boundary": (
            "Fresh owner-side full frozen 8,192,000-occurrence natural-order "
            "recurrence, all 272 reachable negative-psum exact cancellations "
            "driven through df23e4d current-source SA_ALU, adjacent controls, "
            "44,280 small-domain cases, full single-product legal domain, and "
            "four-lane legal corners. No functional RTL modification and no "
            "materializer, E2, package, or generic exact-divider claim."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    print(sha256_file(output))
    print(receipt["status"])
    return 0 if blocker_closed else 1


if __name__ == "__main__":
    raise SystemExit(main())
