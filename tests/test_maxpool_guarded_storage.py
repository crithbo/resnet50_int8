from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.maxpool_guarded_storage import (
    ALLOCATION_BYTES,
    PAYLOAD_BYTES,
    PAYLOAD_OFFSET_BYTES,
    SUFFIX_GUARD_BYTES,
    c4hwc4_pack,
    c4hwc4_unpack,
    address_seed_graph_spec,
    graph_spec,
    guarded_input_image,
    validate_guarded_wave0,
    write_guarded_wave0,
)


ROOT = Path(__file__).resolve().parents[1]


class MaxPoolGuardedStorageTests(unittest.TestCase):
    def test_guard_geometry_closes_reference_json_request_envelope(self) -> None:
        self.assertEqual(PAYLOAD_OFFSET_BYTES, 452)
        self.assertEqual(PAYLOAD_BYTES, 200704)
        self.assertEqual(ALLOCATION_BYTES, 201168)
        self.assertEqual(SUFFIX_GUARD_BYTES, 12)
        graph = graph_spec()
        tensor = graph["operators"][0]["inputs"]["A"]
        self.assertEqual(tensor["shape"], [1, 1, 201168])
        self.assertEqual(tensor["logical_storage"]["layout"], "C4HWC4")
        seed = address_seed_graph_spec()
        self.assertEqual(seed["operators"][0]["inputs"]["A"]["base_addr"], "0x00000000")
        self.assertEqual(seed["operators"][0]["output"]["base_addr"], "0x000311D0")

    def test_c4hwc4_round_trip_and_guarded_offsets(self) -> None:
        value = np.arange(112 * 112 * 16, dtype=np.uint32).astype(np.uint8).reshape(112, 112, 16)
        packed = c4hwc4_pack(value)
        self.assertEqual(packed.shape, (4, 112, 112, 4))
        np.testing.assert_array_equal(c4hwc4_unpack(packed), value)
        image = guarded_input_image(value)
        self.assertEqual(len(image), ALLOCATION_BYTES)
        self.assertEqual(image[:PAYLOAD_OFFSET_BYTES], bytes(PAYLOAD_OFFSET_BYTES))
        self.assertEqual(image[-SUFFIX_GUARD_BYTES:], bytes(SUFFIX_GUARD_BYTES))
        self.assertEqual(
            image[PAYLOAD_OFFSET_BYTES : PAYLOAD_OFFSET_BYTES + PAYLOAD_BYTES],
            packed.tobytes(order="C"),
        )

    def test_full_wave_generation_is_hash_bound_and_repeatable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="maxpool-guarded-") as temp_text:
            output = Path(temp_text) / "wave0"
            manifest = write_guarded_wave0(ROOT, output)
            checked = validate_guarded_wave0(ROOT, output)
            self.assertEqual(checked, manifest)
            self.assertEqual(manifest["summary"]["slice_count"], 28)
            self.assertEqual(manifest["summary"]["independent_mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
