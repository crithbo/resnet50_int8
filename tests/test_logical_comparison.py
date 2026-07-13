from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.cli import main as cli_main
from resnet50_pipeline.compare import (
    LogicalTensorSource,
    compare_logical_tensor,
    compare_request,
)
from resnet50_pipeline.hashing import sha256_file


class LogicalComparisonTests(unittest.TestCase):
    def test_three_way_integer_comparison_is_bit_exact(self) -> None:
        value = np.arange(24, dtype=np.uint8).reshape(2, 3, 4)
        report = compare_logical_tensor(
            tensor_id="tensor-output",
            sources={
                "golden": value,
                "simulator": value.copy(),
                "hardware": value.copy(),
            },
            onnx_node_id="node-0001",
            hw_op_id="hwop-0002",
            block_elements=5,
        )
        self.assertEqual(report["status"], "passed")
        self.assertEqual(len(report["pairs"]), 3)
        self.assertTrue(all(item["comparison_mode"] == "bit_exact" for item in report["pairs"]))
        self.assertTrue(all(item["mismatch_count"] == 0 for item in report["pairs"]))

    def test_first_value_mismatch_has_coordinate_values_and_provenance(self) -> None:
        golden = np.arange(12, dtype=np.int32).reshape(3, 4)
        simulator = golden.copy()
        simulator[1, 2] = -99
        source = LogicalTensorSource.from_array(
            "simulator",
            simulator,
            provenance={"execution_id": "sim-1"},
            coordinate_explainer=lambda coordinate: {
                "slice": coordinate[0],
                "physical_address": 0x1000 + coordinate[1] * 4,
            },
        )
        report = compare_logical_tensor(
            tensor_id="tensor-output",
            required_sources=("golden", "simulator"),
            sources={"golden": golden, "simulator": source},
            block_elements=3,
        )
        pair = report["pairs"][0]
        self.assertEqual(report["status"], "failed")
        self.assertEqual(pair["status"], "value_mismatch")
        self.assertEqual(pair["mismatch_count"], 1)
        self.assertEqual(pair["first_mismatch"]["logical_coordinate"], [1, 2])
        self.assertEqual(pair["first_mismatch"]["values"], {"golden": 6, "simulator": -99})
        provenance = pair["first_mismatch"]["provenance"]["simulator"]
        self.assertEqual(provenance["execution_id"], "sim-1")
        self.assertEqual(provenance["slice"], 1)
        self.assertEqual(provenance["physical_address"], 0x1008)

    def test_shape_and_dtype_failures_are_not_value_failures(self) -> None:
        shape_report = compare_logical_tensor(
            tensor_id="shape",
            required_sources=("golden", "simulator"),
            sources={
                "golden": np.zeros((2, 3), dtype=np.uint8),
                "simulator": np.zeros((3, 2), dtype=np.uint8),
            },
        )
        dtype_report = compare_logical_tensor(
            tensor_id="dtype",
            required_sources=("golden", "simulator"),
            sources={
                "golden": np.zeros((2, 3), dtype=np.uint8),
                "simulator": np.zeros((2, 3), dtype=np.int8),
            },
        )
        self.assertEqual(shape_report["pairs"][0]["status"], "shape_mismatch")
        self.assertEqual(dtype_report["pairs"][0]["status"], "dtype_mismatch")

    def test_missing_and_inverse_failure_make_report_incomplete(self) -> None:
        report = compare_logical_tensor(
            tensor_id="missing-hardware",
            sources={
                "golden": np.zeros((1,), dtype=np.uint8),
                "simulator": np.zeros((1,), dtype=np.uint8),
                "hardware": LogicalTensorSource(
                    name="hardware",
                    status="layout_inverse_failure",
                    error="approved inverse layout is unavailable",
                ),
            },
        )
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["pairs"][0]["status"], "passed")
        self.assertEqual(report["pairs"][1]["status"], "layout_inverse_failure")
        self.assertEqual(report["first_failure"]["category"], "layout_inverse_failure")

    def test_float_requires_tolerance_and_respects_it(self) -> None:
        golden = np.array([1.0, 2.0, np.nan], dtype=np.float32)
        close = np.array([1.0001, 2.0001, np.nan], dtype=np.float32)
        missing_policy = compare_logical_tensor(
            tensor_id="float",
            required_sources=("golden", "simulator"),
            sources={"golden": golden, "simulator": close},
        )
        passing = compare_logical_tensor(
            tensor_id="float",
            required_sources=("golden", "simulator"),
            sources={"golden": golden, "simulator": close},
            atol=0.001,
            rtol=0.0,
        )
        failing = compare_logical_tensor(
            tensor_id="float",
            required_sources=("golden", "simulator"),
            sources={"golden": golden, "simulator": close},
            atol=0.0,
            rtol=0.0,
        )
        self.assertEqual(missing_policy["pairs"][0]["status"], "tolerance_required")
        self.assertEqual(missing_policy["status"], "incomplete")
        self.assertEqual(passing["status"], "passed")
        self.assertEqual(failing["status"], "failed")

    def test_request_orders_first_failure_by_topology(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            same = np.array([1, 2], dtype=np.uint8)
            wrong = np.array([1, 9], dtype=np.uint8)
            np.save(root / "same.npy", same, allow_pickle=False)
            np.save(root / "wrong.npy", wrong, allow_pickle=False)
            request = {
                "schema_version": "0.1",
                "comparison_id": "topology-order",
                "required_sources": ["golden", "simulator"],
                "tensors": [
                    {
                        "tensor_id": "later",
                        "topology_index": 20,
                        "sources": {
                            "golden": {"path": "same.npy"},
                            "simulator": {"path": "wrong.npy"},
                        },
                    },
                    {
                        "tensor_id": "earlier",
                        "topology_index": 10,
                        "sources": {
                            "golden": {"path": "same.npy"},
                            "simulator": {"status": "missing", "error": "not produced"},
                        },
                    },
                ],
            }
            report = compare_request(request, base_dir=root, block_elements=1)
        self.assertEqual([item["tensor_id"] for item in report["tensors"]], ["earlier", "later"])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["first_failure"]["tensor_id"], "earlier")
        self.assertEqual(report["first_failure"]["category"], "missing")

    def test_cli_writes_deterministic_report_and_returns_comparison_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            array = np.array([[1, 2], [3, 4]], dtype=np.int8)
            np.save(root / "golden.npy", array, allow_pickle=False)
            np.save(root / "simulator.npy", array, allow_pickle=False)
            request = {
                "schema_version": "0.1",
                "comparison_id": "cli-pass",
                "required_sources": ["golden", "simulator"],
                "tensors": [{
                    "tensor_id": "tensor-cli",
                    "sources": {
                        "golden": {"path": "golden.npy"},
                        "simulator": {"path": "simulator.npy"},
                    },
                }],
            }
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            output = root / "report.json"
            self.assertEqual(
                cli_main(["compare-results", str(request_path), "--output", str(output)]),
                0,
            )
            first_hash = sha256_file(output)
            self.assertEqual(
                cli_main(["compare-results", str(request_path), "--output", str(output)]),
                0,
            )
            self.assertEqual(sha256_file(output), first_hash)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "passed")


if __name__ == "__main__":
    unittest.main()
