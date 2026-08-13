from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.dequantize_linear_complete_json_regeneration import (
    DequantCompleteJsonError,
    build_artifacts,
    build_candidate,
    build_stage_inventory,
    validate_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


class DequantizeLinearCompleteJsonRegenerationTests(unittest.TestCase):
    def test_lowering_family_is_exactly_two_stages_and_two_classes(self) -> None:
        inventory = build_stage_inventory(ROOT)
        self.assertEqual(inventory["stage_count"], 2)
        self.assertEqual(inventory["equivalence_class_count"], 2)
        self.assertEqual(
            {item["hw_op_id"] for item in inventory["stages"]},
            {"hwop-0072-00", "hwop-0077-00"},
        )

    def test_both_candidates_are_strict_and_match_target_coverage(self) -> None:
        for stage_id in ("hwop-0072-00", "hwop-0077-00"):
            report = validate_candidate(build_candidate(ROOT, stage_id), stage_id)
            self.assertTrue(report["valid"])
            self.assertEqual(report["leaf_count"], 416)

    def test_wrong_final_d_stride_fails_closed(self) -> None:
        config = copy.deepcopy(build_candidate(ROOT, "hwop-0072-00"))
        config["stream_engine"]["stream2"]["dim_stride"][1] = 256
        with self.assertRaises(DequantCompleteJsonError):
            validate_candidate(config, "hwop-0072-00")

    def test_full_bundle_has_no_server_package_outputs(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temporary:
            output = Path(temporary) / "dequantize_linear"
            products = build_artifacts(ROOT, output)
            self.assertTrue(products["report"].is_file())
            names = {path.name for path in output.rglob("*") if path.is_file()}
            self.assertFalse(any(name.lower().endswith(".zip") for name in names))
            self.assertNotIn("PREPARE_AND_RUN.sh", names)
            self.assertNotIn("TEST_PACKAGE_MANIFEST.json", names)


if __name__ == "__main__":
    unittest.main()
