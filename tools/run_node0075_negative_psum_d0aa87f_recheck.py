from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


DEFAULT_OUTPUT = Path(
    "outputs/node0075_negative_psum_d0aa87f_revalidation/"
    "current_rtl_and_recurrence.json"
)
MODEL_REL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
A_REL = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-6fbd5707d5f08110.npy"
)
ACC_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0075-accumulate.npy"
)
WEIGHT_NAME = "resnetv17_dense0_weight_quantized"
MASK32 = (1 << 32) - 1
INT32_SIGN = 1 << 31

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
    Path("tests/rtl/node0075_negative_psum_d0aa87f_recheck_tb.sv"),
)

EXPECTED_CASES = {
    "neg20_plus19": "0xffffffff",
    "neg19_plus19": "0x00000000",
    "neg18_plus19": "0x00000001",
    "zero_plus19": "0x00000013",
    "pos7_plus19": "0x0000001a",
}


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


def to_s32(value: np.ndarray) -> np.ndarray:
    bits = np.bitwise_and(value.astype(np.int64, copy=False), MASK32)
    return np.where(bits >= INT32_SIGN, bits - (1 << 32), bits)


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
        raise RuntimeError(
            f"expected exactly one {WEIGHT_NAME}, found {len(matches)}"
        )
    weight = np.ascontiguousarray(matches[0])
    if weight.dtype != np.int8 or weight.shape != (2048, 1000):
        raise RuntimeError(
            f"unexpected node0075 weight {weight.dtype} {weight.shape}"
        )
    return weight


def scan_frozen_recurrence(root: Path) -> dict[str, Any]:
    activation = np.load(root / A_REL, allow_pickle=False)
    formal = np.load(root / ACC_REL, allow_pickle=False)
    weight = load_weight(root / MODEL_REL)
    if activation.dtype != np.uint8 or activation.shape != (16, 2048):
        raise RuntimeError(
            f"unexpected node0075 activation {activation.dtype} "
            f"{activation.shape}"
        )
    if formal.dtype != np.int32 or formal.shape != (16, 1000):
        raise RuntimeError(
            f"unexpected node0075 accumulator {formal.dtype} {formal.shape}"
        )

    hits: list[dict[str, Any]] = []
    final_rows: list[np.ndarray] = []
    negative_count = 0
    negative_to_zero = 0
    dot_min = 1 << 62
    dot_max = -(1 << 62)
    psum_min = 1 << 62
    psum_max = -(1 << 62)
    occurrence_count = 0

    for m_index in range(16):
        psum = np.zeros(1000, dtype=np.int64)
        for group_index in range(512):
            k_start = group_index * 4
            a_lanes = activation[m_index, k_start : k_start + 4].astype(
                np.int64
            )
            b_lanes = weight[k_start : k_start + 4, :].astype(
                np.int64
            )
            dot4 = np.sum(a_lanes[:, None] * b_lanes, axis=0)
            next_psum = psum + dot4
            negative = psum < 0
            exact_zero = negative & (next_psum == 0)

            occurrence_count += dot4.size
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
                            for left, right in zip(
                                a_lanes, b_values, strict=True
                            )
                        ],
                        "psum_in_s32": int(psum[n_index]),
                        "dot4_s32": int(dot4[n_index]),
                        "expected_next_s32": 0,
                    }
                )
            psum = to_s32(next_psum)
        final_rows.append(psum.astype(np.int32))

    computed = np.stack(final_rows)
    ordered_hits = sorted(
        hits, key=lambda item: (item["m"], item["n"], item["k_group"])
    )
    stream_hits = sorted(
        hits, key=lambda item: (item["m"], item["k_group"], item["n"])
    )
    return {
        "implementation": (
            "fresh direct m->k_group recurrence; does not import the prior "
            "node0075 reachability module or report"
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
        "formal_accumulator_mismatch_count": int(
            np.count_nonzero(computed != formal)
        ),
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


def run_rtl(root: Path) -> dict[str, Any]:
    missing = [item.as_posix() for item in SOURCES if not (root / item).is_file()]
    if missing:
        raise RuntimeError(f"missing RTL inputs: {missing}")
    iverilog = Path(r"C:\iverilog\bin\iverilog.exe")
    vvp = Path(r"C:\iverilog\bin\vvp.exe")
    if not iverilog.is_file() or not vvp.is_file():
        raise RuntimeError("Icarus executable pair unavailable")

    with tempfile.TemporaryDirectory(prefix="node0075-d0aa87f-") as tmp:
        binary = Path(tmp) / "node0075_d0aa87f.vvp"
        compile_argv = [
            str(iverilog),
            "-g2012",
            "-s",
            "node0075_negative_psum_d0aa87f_recheck_tb",
            "-o",
            str(binary),
            *[str(root / item) for item in SOURCES],
        ]
        compile_run = subprocess.run(
            compile_argv,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        sim_run = None
        if compile_run.returncode == 0:
            sim_run = subprocess.run(
                [str(vvp), str(binary)],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )

    stdout = "" if sim_run is None else sim_run.stdout
    pattern = re.compile(
        r"NODE0075_D0AA_CASE label=(\S+) "
        r"psum=([0-9a-fA-F]{8}) magnitude=([0-9a-fA-F]{8}) "
        r"csa_raw=([0-9a-fA-F]{8}) sign=([01xXzZ]) "
        r"result=([0-9a-fA-F]{8}) expected=([0-9a-fA-F]{8})"
    )
    cases: dict[str, dict[str, Any]] = {}
    for match in pattern.finditer(stdout):
        label = match.group(1)
        observed = f"0x{match.group(6).lower()}"
        expected = f"0x{match.group(7).lower()}"
        cases[label] = {
            "psum_bits": f"0x{match.group(2).lower()}",
            "magnitude_bits": f"0x{match.group(3).lower()}",
            "csa_raw_bits": f"0x{match.group(4).lower()}",
            "int_result_sign": match.group(5).lower(),
            "observed_bits": observed,
            "expected_bits": expected,
            "pass": observed == expected,
        }
    return {
        "compile_exit": compile_run.returncode,
        "simulation_exit": None if sim_run is None else sim_run.returncode,
        "cases": cases,
        "all_expected_cases_observed": set(cases) == set(EXPECTED_CASES),
        "source_receipts": {
            item.as_posix(): sha256_file(root / item) for item in SOURCES
        },
        "tool": {
            "iverilog": str(iverilog),
            "vvp": str(vvp),
            "top": "node0075_negative_psum_d0aa87f_recheck_tb",
            "flags": ["-g2012"],
        },
        "compile_argv": [
            "<temporary-vvp>" if item == str(binary) else item
            for item in compile_argv
        ],
        "compile_stdout": compile_run.stdout,
        "compile_stderr": compile_run.stderr,
        "simulation_stdout": stdout,
        "simulation_stderr": "" if sim_run is None else sim_run.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    root = args.project_root.resolve()

    rtl = run_rtl(root)
    scan = scan_frozen_recurrence(root)
    exact_case = rtl["cases"].get("neg19_plus19", {})
    adjacent_labels = (
        "neg20_plus19",
        "neg18_plus19",
        "zero_plus19",
        "pos7_plus19",
    )
    exact_failure = (
        rtl["compile_exit"] == 0
        and rtl["simulation_exit"] == 0
        and rtl["all_expected_cases_observed"]
        and exact_case.get("observed_bits") == "0x80000000"
        and exact_case.get("expected_bits") == "0x00000000"
    )
    adjacent_pass = all(
        rtl["cases"].get(label, {}).get("pass") is True
        for label in adjacent_labels
    )
    blocker_retained = (
        exact_failure
        and adjacent_pass
        and scan["complete"]
        and scan["formal_accumulator_match"]
        and scan["negative_to_exact_zero"] > 0
    )

    receipt = {
        "schema": "resnet50-node0075-d0aa87f-revalidation-run-v1",
        "status": (
            "BLOCKER_RETAINED_CURRENT_RTL"
            if blocker_retained
            else "REVALIDATION_INCONCLUSIVE_OR_BLOCKER_CLOSED"
        ),
        "blocker": (
            "B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE"
        ),
        "current_rtl_identity": {
            "trassic_commit": (
                "d0aa87f682880a260fb792aaac88f70a23aba414"
            ),
            "functional_fix_commit": (
                "cb11353d4196b4af26aac18b4dcc39ba0027e8bc"
            ),
            "SA_PE_Float_CSA.v": (
                "429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a"
            ),
            "SA_PE_Float_Control.v": (
                "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
            ),
        },
        "directed_rtl": rtl,
        "frozen_recurrence": scan,
        "decision_inputs": {
            "exact_failure_reproduced": exact_failure,
            "adjacent_controls_pass": adjacent_pass,
            "complete_recurrence": scan["complete"],
            "formal_final_match": scan["formal_accumulator_match"],
            "reachable_exact_cancellations": scan["negative_to_exact_zero"],
        },
        "claim_boundary": (
            "Fresh owner-side Icarus/VVP directed cases plus a fresh full "
            "frozen node0075 natural-order recurrence under the exact d0aa87f "
            "active RTL identity; no functional RTL, materializer, E2, or "
            "server claim."
        ),
    }
    output = args.output
    if not output.is_absolute():
        output = root / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(output)
    print(sha256_file(output))
    print(receipt["status"])
    return 0 if blocker_retained else 1


if __name__ == "__main__":
    raise SystemExit(main())
