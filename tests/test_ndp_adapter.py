from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.adapters import NdpFunctionalAdapter
from resnet50_pipeline.conv_layout import SmallConvPhysicalLayout
from resnet50_pipeline.golden.qlinear_conv import qlinear_conv_scalar
from resnet50_pipeline.memory import DramGeometry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class NdpFunctionalAdapterTests(unittest.TestCase):
    def test_ndp_dram_consumes_the_exact_w2_physical_bundle(self) -> None:
        activation = np.arange(12, dtype=np.uint8).reshape(1, 3, 2, 2)
        weight = np.array(
            [
                [[[1]], [[-1]], [[2]]],
                [[[2]], [[1]], [[-2]]],
                [[[-1]], [[3]], [[1]]],
                [[[1]], [[1]], [[1]]],
            ],
            dtype=np.int8,
        )
        bias = np.array([1, -2, 3, 0], dtype=np.int32)
        w_scale = np.array([0.02, 0.03, 0.04, 0.05], dtype=np.float32)
        w_zero_point = np.zeros(4, dtype=np.int8)
        x_scale = np.float32(0.025)
        x_zero_point = np.uint8(5)
        y_scale = np.float32(0.04)
        y_zero_point = np.uint8(101)
        golden = qlinear_conv_scalar(
            activation,
            weight,
            x_scale=x_scale,
            x_zero_point=x_zero_point,
            w_scale=w_scale,
            w_zero_point=w_zero_point,
            y_scale=y_scale,
            y_zero_point=y_zero_point,
            bias=bias,
        )
        geometry = DramGeometry(
            slice_count=4,
            bank_count=2,
            row_count=8,
            col_count=8,
            subword_bytes=16,
        )
        layout = SmallConvPhysicalLayout(geometry, slice_count=4)
        bundle = layout.forward(
            activation=activation,
            weight=weight,
            bias=bias,
            w_scale=w_scale,
            w_zero_point=w_zero_point,
            x_scale=x_scale,
            x_zero_point=x_zero_point,
            y_scale=y_scale,
            y_zero_point=y_zero_point,
            output=golden.output,
        )
        adapter = NdpFunctionalAdapter(
            PROJECT_ROOT / "NDPFuncModel",
            python_executable=Path(sys.executable),
        )
        result = adapter.probe_physical_bundle(bundle)
        self.assertEqual(result.per_slice, geometry.bytes_per_slice)
        self.assertEqual(result.total_bytes, geometry.total_bytes)
        self.assertEqual(len(result.regions), len(bundle.regions))
        self.assertTrue(all(region["hash_matches"] for region in result.regions))
        self.assertEqual(
            {region["start_coordinate"][0] for region in result.regions},
            {0, 1, 2, 3},
        )


if __name__ == "__main__":
    unittest.main()
