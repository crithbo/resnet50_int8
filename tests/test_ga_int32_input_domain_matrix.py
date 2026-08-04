from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.ga_int32_input_domain_matrix import (
    CONTRACT_PATH,
    build_ga_int32_input_domain_matrix,
    validate_ga_int32_input_domain_matrix,
)


ROOT = Path(__file__).resolve().parents[1]


class GAInt32InputDomainMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.value = build_ga_int32_input_domain_matrix(ROOT)

    def test_all_int32_conversion_stages_are_covered(self) -> None:
        summary = self.value["summary"]
        self.assertEqual(summary["stage_count"], 55)
        self.assertEqual(summary["requant_stage_count"], 54)
        self.assertEqual(summary["average_requant_stage_count"], 1)
        self.assertEqual(len(self.value["stages"]), 55)
        self.assertEqual(summary["rtl_compatible_stage_count"], 0)
        self.assertTrue(
            self.value["release"]["blocker_retained_for_all_55_stages"]
        )

    def test_node0004_matches_exact_representative_replay(self) -> None:
        item = next(
            record
            for record in self.value["stages"]
            if record["request_id"] == "r5:hwop-0004-01"
        )
        self.assertEqual(item["element_count"], 3_211_264)
        self.assertEqual(item["minus_one_count"], 128)
        self.assertEqual(item["int_min_count"], 0)
        self.assertTrue(item["exact_w3_hits_known_counterexample"])
        self.assertFalse(item["rtl_semantics_compatible"])

    def test_checked_contract_is_hash_bound(self) -> None:
        checked = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )
        validate_ga_int32_input_domain_matrix(checked, ROOT)


if __name__ == "__main__":
    unittest.main()
