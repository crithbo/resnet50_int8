from __future__ import annotations

import json
import unittest
from pathlib import Path

import resnet50_pipeline.layout as public_layout
from resnet50_pipeline import conv_coverage, network_dry_run, w4_profiles


ROOT = Path(__file__).resolve().parents[1]


class Rtl28LegacyIsolationTests(unittest.TestCase):
    def test_current_layout_registry_contains_only_rtl28_records(self) -> None:
        architecture = json.loads(
            (ROOT / "contracts/architecture.json").read_text(encoding="utf-8")
        )
        for registry_name in ("planned_layouts", "candidate_layouts"):
            for layout_id, record in architecture[registry_name].items():
                self.assertNotIn("16", layout_id.lower())
                self.assertEqual(record["target_family"], "rtl28")
                self.assertEqual(record["slice_count"], 28)

    def test_current_public_layout_api_does_not_export_legacy16_classes(self) -> None:
        exported = set(public_layout.__all__)
        self.assertFalse(any("16" in name for name in exported))
        self.assertFalse(any("Batch16" in name for name in exported))

    def test_generic_historical_modules_are_explicitly_gate_ineligible(self) -> None:
        for module in (conv_coverage, network_dry_run, w4_profiles):
            self.assertEqual(module.TARGET_FAMILY, "legacy16")
            self.assertFalse(module.CURRENT_GATE_ELIGIBLE)
            self.assertIn("Legacy16", module.__doc__ or "")

    def test_current_layout_modules_do_not_import_legacy_physical_code(self) -> None:
        for relative_path in (
            "resnet50_pipeline/layout.py",
            "resnet50_pipeline/simple_layout.py",
            "resnet50_pipeline/profile28.py",
            "resnet50_pipeline/topology28.py",
        ):
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertNotIn("LEGACY_DRAM_GEOMETRY16", source, relative_path)
            self.assertNotIn("16_layout", source, relative_path)


if __name__ == "__main__":
    unittest.main()
