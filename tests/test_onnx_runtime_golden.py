from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper

from resnet50_pipeline.golden.onnx_runtime import run_all_node_outputs


class OnnxRuntimeGoldenTests(unittest.TestCase):
    def test_all_node_outputs_and_initializer_references_are_saved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_path = root / "tiny.onnx"
            scale = helper.make_tensor("scale", TensorProto.FLOAT, (), [0.5])
            zero = helper.make_tensor("zero", TensorProto.UINT8, (), [10])
            graph = helper.make_graph(
                [
                    helper.make_node("QuantizeLinear", ["x", "scale", "zero"], ["q"], name="quant"),
                    helper.make_node("DequantizeLinear", ["q", "scale", "zero"], ["y"], name="dequant"),
                ],
                "tiny",
                [helper.make_tensor_value_info("x", TensorProto.FLOAT, ["N", 2])],
                [helper.make_tensor_value_info("y", TensorProto.FLOAT, ["N", 2])],
                [scale, zero],
            )
            model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 12)])
            model.ir_version = 10
            onnx.save(model, model_path)
            output = root / "golden"
            manifest = run_all_node_outputs(
                model_path,
                np.array([[0.0, 1.0]], dtype=np.float32),
                output,
            )
            self.assertEqual(len(manifest["nodes"]), 2)
            self.assertEqual(len(manifest["initializers"]), 2)
            self.assertEqual(len(manifest["tensors"]), 3)
            saved = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["runtime"]["graph_optimization"], "ORT_DISABLE_ALL")
            for item in saved["tensors"].values():
                array = np.load(output / item["path"], allow_pickle=False)
                self.assertEqual(str(array.dtype), item["dtype"])
                self.assertEqual(list(array.shape), item["shape"])
            with self.assertRaises(FileExistsError):
                run_all_node_outputs(
                    model_path,
                    np.array([[0.0, 1.0]], dtype=np.float32),
                    output,
                )


if __name__ == "__main__":
    unittest.main()
