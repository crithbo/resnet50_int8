from __future__ import annotations

import sys
import importlib.util
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.adapters import NdpFunctionalAdapter, NdpInt8DotProbe
from resnet50_pipeline.conv_layout import SmallConvPhysicalLayout
from resnet50_pipeline.golden.qlinear_conv import qlinear_conv_scalar
from resnet50_pipeline.memory import DramGeometry


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_cgra_qnn_round():
    path = PROJECT_ROOT / "CGRA_SIM" / "cgra_python" / "op_lib" / "qnn" / "qnn_round.py"
    spec = importlib.util.spec_from_file_location("cgra_qnn_round_for_w2", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load CGRA QNN round reference: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NdpFunctionalAdapterTests(unittest.TestCase):
    def _adapter(self) -> NdpFunctionalAdapter:
        return NdpFunctionalAdapter(
            PROJECT_ROOT / "NDPFuncModel",
            python_executable=Path(sys.executable),
        )

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
        adapter = self._adapter()
        c_tile = int(bundle.metadata["c_tile"])
        c_padded = int(bundle.metadata["c_padded"])
        k_tile = int(bundle.metadata["k_tile"])
        activation_addresses = []
        for channel in range(c_padded):
            slice_id = channel // c_tile
            local_c = channel % c_tile
            region = bundle.region("activation", slice_id)
            activation_addresses.append(region.base_address + local_c)
        output_channel = 0
        owner_slice = output_channel // k_tile
        local_k = output_channel % k_tile
        weight_region = bundle.region("weight", owner_slice)
        weight_addresses = tuple(
            weight_region.base_address + local_k * c_padded + channel
            for channel in range(c_padded)
        )
        corrected_bias = int(bias[output_channel]) - int(x_zero_point) * int(
            np.sum(weight[output_channel, :, 0, 0].astype(np.int32), dtype=np.int64)
        )
        result = adapter.probe_physical_bundle(
            bundle,
            int8_dot_probes=(
                NdpInt8DotProbe(
                    name="output_n0_k0_h0_w0",
                    activation_addresses=tuple(activation_addresses),
                    weight_addresses=weight_addresses,
                    bias=corrected_bias,
                ),
            ),
        )
        self.assertEqual(result.per_slice, geometry.bytes_per_slice)
        self.assertEqual(result.total_bytes, geometry.total_bytes)
        self.assertEqual(len(result.regions), len(bundle.regions))
        self.assertTrue(all(region["hash_matches"] for region in result.regions))
        self.assertEqual(
            {region["start_coordinate"][0] for region in result.regions},
            {0, 1, 2, 3},
        )
        self.assertEqual(len(result.int8_dot_probes), 1)
        self.assertEqual(
            result.int8_dot_probes[0]["accumulator"],
            int(golden.accumulator[0, output_channel, 0, 0]),
        )

    def test_all_conv_coordinates_match_independent_golden_accumulators(self) -> None:
        activation = (np.arange(36, dtype=np.uint8) + 3).reshape(1, 3, 3, 4)
        weight = ((np.arange(189, dtype=np.int16) % 9) - 4).astype(np.int8).reshape(
            7, 3, 3, 3
        )
        bias = np.array([17, -9, 3, 21, -16, 5, 11], dtype=np.int32)
        w_scale = np.linspace(0.02, 0.05, 7, dtype=np.float32)
        w_zero_point = np.zeros(7, dtype=np.int8)
        x_scale = np.float32(0.025)
        x_zero_point = np.uint8(7)
        y_scale = np.float32(0.04)
        y_zero_point = np.uint8(101)
        pads = (1, 1, 1, 1)
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
            pads=pads,
        )
        qnn_round = _load_cgra_qnn_round()
        multiplier = (x_scale * w_scale / y_scale).astype(np.float32)
        qnn_output = qnn_round.quantize(
            golden.accumulator,
            multiplier,
            np.array(y_zero_point, dtype=np.uint8),
        )
        np.testing.assert_array_equal(qnn_output, golden.output)
        adapter = self._adapter()
        for slice_count in (1, 4):
            with self.subTest(slice_count=slice_count):
                geometry = DramGeometry(
                    slice_count=slice_count,
                    bank_count=2,
                    row_count=8,
                    col_count=8,
                    subword_bytes=16,
                )
                layout = SmallConvPhysicalLayout(geometry, slice_count=slice_count)
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
                    output=np.full_like(golden.output, y_zero_point),
                )
                probes = adapter.build_qlinear_conv_accumulator_probes(bundle, pads=pads)
                self.assertEqual(len(probes), golden.accumulator.size)
                self.assertTrue(
                    all(len(probe.ring_segment_ends) == slice_count for probe in probes)
                )
                self.assertTrue(any(any(probe.branch_mask) for probe in probes))
                result = adapter.run_qlinear_conv_accumulators(bundle, pads=pads)
                np.testing.assert_array_equal(result.accumulator, golden.accumulator)
                np.testing.assert_array_equal(result.output, golden.output)
                np.testing.assert_array_equal(layout.inverse_output(bundle), golden.output)
                self.assertEqual(layout.validate(bundle)["slice_count"], slice_count)
                for region in bundle.regions:
                    for address in range(
                        region.base_address, region.base_address + region.size_bytes
                    ):
                        coordinate, provenance = bundle.explain_address(address)
                        self.assertEqual(coordinate.slice_id, region.slice_id)
                        self.assertIn(
                            provenance.semantic,
                            {"data", "tensor_padding", "alignment"},
                        )
                self.assertEqual(
                    len(result.physical_probe.int8_dot_probes), golden.accumulator.size
                )
                expected_last = [0] * (slice_count - 1) + [1]
                self.assertTrue(
                    all(
                        len(dot["partial_accumulators"]) == slice_count
                        and [state["last"] for state in dot["ring_loop_states"]]
                        == expected_last
                        and dot["output_before"] == int(y_zero_point)
                        and dot["output_after"] == dot["requantized_output"]
                        for dot in result.physical_probe.int8_dot_probes
                    )
                )


if __name__ == "__main__":
    unittest.main()
