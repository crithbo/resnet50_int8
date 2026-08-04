from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the legacy CGRA_SIM MaxPool software operator")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/w5/hwop-0002-00/maxpool_v1/cgra_software_reference.json"),
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else project_root / args.output
    if output.exists():
        raise RuntimeError(f"refusing to overwrite CGRA software reference report: {output}")
    cgra_root = project_root / "CGRA_SIM"
    sys.path.insert(0, str(cgra_root))
    from cgra_python.op_lib.reduce_op.max_pool import MAXPOOLING

    tensors = project_root / "artifacts" / "w3" / "golden_batch16" / "tensors"
    activation = np.load(tensors / "tensor-f6c1a8fb6fd529e8.npy", allow_pickle=False)
    golden = np.load(tensors / "tensor-8d2f28c80ac24676.npy", allow_pickle=False)
    # CGRA_SIM's historical execution-plan generator materializes spatial
    # padding in DMA extraction and then invokes MAXPOOLING with padding=0 in
    # torch.  Reproduce that native contract instead of silently changing it.
    staged = np.pad(activation, ((0, 0), (0, 0), (1, 1), (1, 1)), constant_values=0)
    operator = MAXPOOLING(
        list(staged.shape), [1, 1], [3, 3], [2, 2], "uint8", "nchw"
    )
    actual = np.frombuffer(operator.compute(staged.tobytes(order="C")), dtype=np.uint8).reshape(
        golden.shape
    )
    mismatch_count = int(np.count_nonzero(actual != golden))
    if mismatch_count:
        first = tuple(int(item) for item in np.argwhere(actual != golden)[0])
        raise RuntimeError(
            f"CGRA_SIM MaxPool differs at {first}: actual={int(actual[first])}, golden={int(golden[first])}"
        )
    max_pool_source = cgra_root / "cgra_python" / "op_lib" / "reduce_op" / "max_pool.py"
    import_fix_source = cgra_root / "cgra_python" / "layout" / "layout_buffer.py"
    report = {
        "schema_version": "0.1",
        "kind": "legacy_cgra_sim_software_reference",
        "status": "passed_extra_software_reference_not_target_execution",
        "identity": {"node_id": "node-0002", "hwop_id": "hwop-0002-00"},
        "repository": {
            "name": "CGRA_SIM",
            "commit": "53c41e02c294bcc54379e686dc9d25bbb93919fa",
            "local_import_blocker_fix": {
                "path": "cgra_python/layout/layout_buffer.py",
                "sha256": _sha256_file(import_fix_source),
                "change": "removed stray pass token from an unrelated PEArray.execute argument list",
            },
        },
        "operator_source": {
            "path": "CGRA_SIM/cgra_python/op_lib/reduce_op/max_pool.py",
            "sha256": _sha256_file(max_pool_source),
            "class": "MAXPOOLING",
            "method": "compute",
        },
        "execution": {
            "input_shape": list(activation.shape),
            "dma_staged_shape": list(staged.shape),
            "output_shape": list(actual.shape),
            "dtype": "uint8",
            "padding_contract": "zero border materialized before MAXPOOLING, matching the historical DMA extraction plan",
            "logical_element_count": int(actual.size),
            "mismatch_count": mismatch_count,
            "output_payload_sha256": _array_sha256(actual),
        },
        "evidence_boundary": {
            "counts_as_independent_software_reference": True,
            "counts_as_current_28_slice_target_execution": False,
            "counts_as_g6_or_g8": False,
            "reason": "CGRA_SIM is an old .cu semantic simulator and does not consume the frozen target JSON/bitstream or RTL28 physical image",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "output": str(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
