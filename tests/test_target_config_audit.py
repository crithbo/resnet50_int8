from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.target_config_audit import (
    MAXPOOL_TEMPLATE,
    TargetConfigAuditError,
    audit_register_map,
    audit_maxpool_encoder,
    inventory_templates,
    validate_maxpool_template,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ndp-sim-ref"


class TargetConfigAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template = json.loads((SOURCE / "jsons" / MAXPOOL_TEMPLATE).read_text(encoding="utf-8"))

    def test_official_inventory_is_complete_and_exposes_conv_gap(self) -> None:
        inventory = inventory_templates(SOURCE)
        self.assertEqual(inventory["json_count"], 42)
        self.assertEqual(inventory["resnet_or_shared_count"], 7)
        self.assertEqual(inventory["deepseek_transformer_count"], 35)
        self.assertEqual(inventory["named_conv_template_count"], 0)

    def test_maxpool_preflight_binds_resources_and_field_routes(self) -> None:
        result = validate_maxpool_template(self.template)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["resources"]["dram_loops"], 8)
        self.assertEqual(result["resources"]["read_streams"], 1)
        self.assertEqual(result["resources"]["write_streams"], 1)
        self.assertEqual(result["resources"]["ga_pes"], 8)
        self.assertEqual(result["field_routes"]["general_array.PE_array"]["encoder_class"], "GAPEConfig")

    def test_register_map_declared_widths_align_despite_bad_range_annotations(self) -> None:
        report = audit_register_map(SOURCE)
        self.assertEqual(report["declared_width_alignment_status"], "passed")
        self.assertGreater(report["annotation_range_mismatch_count"], 0)
        self.assertTrue(all(item["aligned"] for item in report["maxpool_module_alignment"]))
        self.assertGreater(report["maxpool_semantic_field_rows"], 0)
        self.assertEqual(report["official_consumer_probe"]["field_binding_count"], 739)
        self.assertEqual(
            report["official_consumer_probe"]["sample_binding_widths"][
                "rd_stream0.stream_engine.stream.base_addr"
            ],
            30,
        )

    def test_unknown_top_level_group_fails_closed(self) -> None:
        value = deepcopy(self.template)
        value["guessed_hardware_field"] = 1
        with self.assertRaisesRegex(TargetConfigAuditError, "unexpected"):
            validate_maxpool_template(value)

    def test_encoder_overflow_fails_before_silent_truncation(self) -> None:
        value = deepcopy(self.template)
        value["dram_loop_configs"]["LC1"]["end"] = 1 << 17
        with self.assertRaisesRegex(TargetConfigAuditError, "refusing silent truncation"):
            validate_maxpool_template(value)

    def test_maxpool_encoder_is_reproducible_and_field_sensitive(self) -> None:
        report = audit_maxpool_encoder(SOURCE)
        self.assertEqual(report["determinism"]["status"], "passed")
        self.assertEqual(report["differential_sensitivity"]["status"], "passed")
        self.assertNotEqual(
            report["differential_sensitivity"]["baseline_128b_sha256"],
            report["differential_sensitivity"]["modified_128b_sha256"],
        )
        self.assertEqual(report["fail_closed"]["status"], "passed")


if __name__ == "__main__":
    unittest.main()
