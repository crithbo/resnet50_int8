from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from resnet50_pipeline.gap_int32_mac_bypass import (  # noqa: E402
    CGRA_REPORT_PATH,
    LOGICAL_WIDTHS,
    RULE_IDS,
    W3_EXPECTED_PATH,
    W3_INPUT_PATH,
    load_locked_cgra_sum,
)
from resnet50_pipeline.hashing import (  # noqa: E402
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)

SUM = load_locked_cgra_sum(ROOT)


def _explicit_tree(matrix: np.ndarray) -> tuple[np.ndarray, list[int]]:
    level = matrix.astype(np.int32, copy=True)
    widths = [int(level.shape[1])]
    while level.shape[1] > 1:
        if level.shape[1] % 2:
            level = np.pad(level, ((0, 0), (0, 1)), constant_values=0)
        level = (
            level[:, 0::2].astype(np.int64)
            + level[:, 1::2].astype(np.int64)
        ).astype(np.int32)
        widths.append(int(level.shape[1]))
    return level[:, 0], widths


def build_report(root: Path) -> dict[str, object]:
    input_path = root / W3_INPUT_PATH
    expected_path = root / W3_EXPECTED_PATH
    tensor = np.load(input_path, allow_pickle=False)
    expected = np.load(expected_path, allow_pickle=False)
    if tensor.shape != (16, 2048, 7, 7) or tensor.dtype != np.uint8:
        raise ValueError(f"unexpected W3 input: {tensor.shape} {tensor.dtype}")
    if expected.shape != (16, 2048, 1, 1) or expected.dtype != np.int32:
        raise ValueError(
            f"unexpected W3 GAP expected tensor: {expected.shape} {expected.dtype}"
        )
    matrix = tensor.reshape(16 * 2048, 49)
    operator = SUM(
        dtype="int32",
        layout="rowmajor",
        bm=16 * 2048,
        bn=49,
        axis=1,
    )
    cgra_result = operator.SUM(matrix.astype(np.int32)).astype(np.int32)
    tree_result, widths = _explicit_tree(matrix)
    expected_flat = expected.reshape(-1)
    cgra_equal_tree = bool(np.array_equal(cgra_result, tree_result))
    cgra_equal_expected = bool(np.array_equal(cgra_result, expected_flat))
    tree_equal_expected = bool(np.array_equal(tree_result, expected_flat))
    if widths != list(LOGICAL_WIDTHS):
        raise ValueError(f"explicit logical widths differ: {widths}")
    if not (cgra_equal_tree and cgra_equal_expected and tree_equal_expected):
        raise ValueError("CGRA/tree/W3 expected three-way numeric comparison failed")
    sum_source = root / "CGRA_SIM/cgra_python/op_lib/reduce_op/sum.py"
    base_source = root / "CGRA_SIM/cgra_python/op_lib/base_op.py"
    return {
        "schema": "resnet50-gap-int32-mac-cgra-semantic-reference-v1",
        "status": "pass_local_semantic_reference_only",
        "candidate_release": False,
        "server_package_allowed": False,
        "functional_rtl_modified": False,
        "rule_ids": list(RULE_IDS),
        "method": {
            "operator": "CGRA_SIM.cgra_python.op_lib.reduce_op.sum.SUM",
            "entrypoint": "SUM.SUM",
            "stream_execute_or_compute_used": False,
            "reason": (
                "the locked SUM.compute transport wrapper calls "
                "BaseOP.reshape with an incompatible argument count"
            ),
            "consumes_config_mapping_bitstream_execplan_sca": False,
        },
        "inputs": {
            "w3_input": {
                "path": W3_INPUT_PATH,
                "sha256": sha256_file(input_path),
                "shape": list(tensor.shape),
                "dtype": str(tensor.dtype),
            },
            "w3_expected": {
                "path": W3_EXPECTED_PATH,
                "sha256": sha256_file(expected_path),
                "shape": list(expected.shape),
                "dtype": str(expected.dtype),
            },
            "cgra_sum_source": {
                "path": sum_source.relative_to(root).as_posix(),
                "sha256": sha256_file(sum_source),
            },
            "cgra_base_source": {
                "path": base_source.relative_to(root).as_posix(),
                "sha256": sha256_file(base_source),
            },
        },
        "comparison": {
            "vector_count": int(matrix.shape[0]),
            "elements_per_vector": int(matrix.shape[1]),
            "logical_tree_widths": widths,
            "cgra_equal_explicit_int32_mac_tree": cgra_equal_tree,
            "cgra_equal_independent_w3_expected": cgra_equal_expected,
            "explicit_tree_equal_independent_w3_expected": tree_equal_expected,
            "cgra_output_sha256": sha256_bytes(cgra_result.tobytes()),
            "tree_output_sha256": sha256_bytes(tree_result.tobytes()),
            "expected_output_sha256": sha256_bytes(expected_flat.tobytes()),
            "minimum": int(cgra_result.min()),
            "maximum": int(cgra_result.max()),
        },
        "claim_boundary": {
            "proves_formula_and_w3_numbers": True,
            "proves_two_mse_stream_routing": False,
            "proves_intermediate_ddr_visibility": False,
            "proves_cycle_level_backpressure": False,
            "proves_server_or_rtl_execution": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local CGRA_SIM semantic reference for the stock-RTL "
            "GAP int32_mac bypass. This does not generate a server package."
        )
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = (
        args.output.resolve()
        if args.output is not None
        else (root / CGRA_REPORT_PATH).resolve()
    )
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"refusing to overwrite existing file: {output}")
    report = build_report(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_json_bytes(report) + b"\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": str(output),
                "sha256": sha256_file(output),
                "comparison": report["comparison"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
