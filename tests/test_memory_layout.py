from __future__ import annotations

import unittest

import numpy as np

from resnet50_pipeline.conv_layout import SmallConvPhysicalLayout
from resnet50_pipeline.golden.qlinear_conv import qlinear_conv_scalar
from resnet50_pipeline.memory import (
    ByteProvenance,
    DramCoordinate,
    DramGeometry,
    SparsePhysicalImage,
)


class DramGeometryTests(unittest.TestCase):
    def test_ndp_address_mapping_and_inverse(self) -> None:
        geometry = DramGeometry(slice_count=4, bank_count=4, row_count=8, col_count=4)
        self.assertEqual(geometry.decode(0), DramCoordinate(0, 0, 0, 3, 15))
        self.assertEqual(geometry.decode(15), DramCoordinate(0, 0, 0, 3, 0))
        self.assertEqual(geometry.decode(16), DramCoordinate(0, 0, 0, 2, 15))
        self.assertEqual(
            geometry.decode(geometry.bytes_per_bank), DramCoordinate(0, 1, 0, 3, 15)
        )
        self.assertEqual(
            geometry.decode(geometry.bytes_per_slice), DramCoordinate(1, 0, 0, 3, 15)
        )
        self.assertEqual(
            geometry.bytes_per_slice,
            geometry.bank_count * geometry.row_count * geometry.col_count * geometry.subword_bytes,
        )
        for address in (0, 1, 15, 16, 63, 64, geometry.bytes_per_bank, geometry.total_bytes - 1):
            self.assertEqual(geometry.encode(geometry.decode(address)), address)

    def test_alignment_and_explicit_byte_stride(self) -> None:
        geometry = DramGeometry(slice_count=1, bank_count=1, row_count=8, col_count=8)
        transfers = geometry.split_aligned(13, 40)
        self.assertEqual(
            [(item.address, item.size_bytes) for item in transfers],
            [(13, 3), (16, 16), (32, 16), (48, 5)],
        )
        strided = geometry.strided_transactions(100, 3, 8, 32)
        self.assertEqual([item.address for item in strided], [100, 132, 164])

    def test_sparse_image_rejects_overlap_and_keeps_provenance(self) -> None:
        geometry = DramGeometry(slice_count=1, bank_count=1, row_count=1, col_count=2)
        image = SparsePhysicalImage(geometry)
        provenance = tuple(
            ByteProvenance("x", (index,), 0, "data") for index in range(4)
        )
        image.write(3, bytes([1, 2, 3, 4]), provenance)
        self.assertEqual(image.read(3, 4), bytes([1, 2, 3, 4]))
        coordinate, source = image.explain(4)
        self.assertEqual(geometry.encode(coordinate), 4)
        self.assertEqual(source.logical_coordinate, (1,))
        with self.assertRaisesRegex(ValueError, "overlaps"):
            image.write(4, b"x", (ByteProvenance("y", (0,), 0, "data"),))


class SmallConvPhysicalLayoutTests(unittest.TestCase):
    def _case(self, slice_count: int) -> None:
        rng = np.random.default_rng(20260711 + slice_count)
        activation = rng.integers(0, 256, size=(1, 5, 4, 5), dtype=np.uint8)
        weight = rng.integers(-30, 31, size=(7, 5, 2, 3), dtype=np.int16).astype(np.int8)
        bias = np.array([-50, -20, 0, 20, 50, 80, -100], dtype=np.int32)
        w_scale = np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07], dtype=np.float32)
        w_zero_point = np.array([-3, -2, -1, 0, 1, 2, 3], dtype=np.int8)
        x_scale = np.float32(0.025)
        x_zero_point = np.uint8(111)
        y_scale = np.float32(0.04)
        y_zero_point = np.uint8(99)
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
            pads=(1, 1, 0, 1),
            reduction_tile=7,
        )
        geometry = DramGeometry(
            slice_count=slice_count, bank_count=4, row_count=32, col_count=16
        )
        layout = SmallConvPhysicalLayout(geometry, slice_count)
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

        self.assertEqual(bundle.metadata["status"], "candidate")
        self.assertEqual(bundle.metadata["contract"], "w2_ndp_ring_candidate_v1")
        np.testing.assert_array_equal(layout.inverse_activation(bundle), activation)
        np.testing.assert_array_equal(layout.inverse_weight(bundle), weight)
        np.testing.assert_array_equal(
            layout.inverse_channel_vector(bundle, "bias", np.dtype("<i4")), bias
        )
        np.testing.assert_array_equal(
            layout.inverse_channel_vector(bundle, "w_scale", np.dtype("<f4")), w_scale
        )
        np.testing.assert_array_equal(
            layout.inverse_channel_vector(bundle, "w_zero_point", np.dtype("i1")),
            w_zero_point,
        )
        np.testing.assert_array_equal(layout.inverse_output(bundle), golden.output)
        recovered = layout.inverse(bundle)
        np.testing.assert_array_equal(recovered["activation"], activation)
        np.testing.assert_array_equal(recovered["output"], golden.output)
        scalar_qparams = layout.inverse_scalar_qparams(bundle)
        self.assertEqual(scalar_qparams[0], x_scale)
        self.assertEqual(scalar_qparams[1], x_zero_point)
        self.assertEqual(scalar_qparams[2], y_scale)
        self.assertEqual(scalar_qparams[3], y_zero_point)

        for region in bundle.regions:
            self.assertEqual(region.base_address % 16, 0)
            coordinate = geometry.decode(region.base_address)
            self.assertEqual(coordinate.slice_id, region.slice_id)
            self.assertLess(
                region.base_address + region.size_bytes,
                geometry.slice_base(region.slice_id) + geometry.bytes_per_slice + 1,
            )

        addresses = bundle.addresses_for("activation", (0, 4, 2, 3))
        self.assertEqual(len(addresses), 1)
        coordinate, provenance = bundle.explain_address(addresses[0])
        self.assertEqual(coordinate.slice_id, min(4 // int(bundle.metadata["c_tile"]), slice_count - 1))
        self.assertEqual(provenance.logical_coordinate, (0, 4, 2, 3))
        explanation = layout.explain_coordinate(bundle, "activation", (0, 4, 2, 3))
        self.assertEqual(len(explanation), 1)
        self.assertEqual(explanation[0]["address"], addresses[0])
        validation = layout.validate(bundle)
        self.assertEqual(validation["slice_count"], slice_count)
        self.assertEqual(validation["written_byte_count"], bundle.image.written_byte_count)

    def test_one_slice_round_trip(self) -> None:
        self._case(1)

    def test_four_slice_round_trip_with_c_and_k_tails(self) -> None:
        self._case(4)


if __name__ == "__main__":
    unittest.main()
