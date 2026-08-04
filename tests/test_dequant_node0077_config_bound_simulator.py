from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.dequant_node0077_config_bound_simulator import (
    CONTRACT_RELATIVE,
    REPORT_RELATIVE,
    build_three_party_report,
)
from resnet50_pipeline.hashing import canonical_json_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[1]


class DequantNode0077ConfigBoundSimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_three_party_report(ROOT)

    def test_executor_is_bound_to_all_final_assets(self) -> None:
        executor = self.report["executor"]
        self.assertEqual(
            executor["kind"], "PROJECT_EQUIVALENT_CONFIG_BOUND_PE_GRAPH_EXECUTOR"
        )
        self.assertTrue(executor["consumes_final_strict_json"])
        self.assertTrue(executor["consumes_final_bitstream_and_mapping"])
        self.assertTrue(executor["consumes_execplan_sca_sca_d"])
        self.assertTrue(executor["consumes_physical_a"])
        self.assertTrue(executor["produces_physical_d"])
        self.assertFalse(executor["software_formula_substitution"])

    def test_all_three_parties_are_bit_exact(self) -> None:
        self.assertEqual(
            self.report["status"], "THREE_PARTY_CONFIG_BOUND_CLOSURE_PASS"
        )
        for comparison in self.report["comparisons"].values():
            self.assertEqual(comparison["status"], "PASS")
            self.assertEqual(comparison["bit_mismatch_count"], 0)
            self.assertTrue(comparison["bit_exact"])
            self.assertEqual(comparison["nan_count_left"], 0)
            self.assertEqual(comparison["nan_count_right"], 0)
        self.assertEqual(
            self.report["physical_layout"]["simulator_inverse_sha256"],
            "d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d",
        )

    def test_physical_d_tail_and_coverage(self) -> None:
        records = self.report["physical_d"]
        self.assertEqual(len(records), 28)
        self.assertEqual({item["slice_id"] for item in records}, set(range(28)))
        self.assertTrue(
            all(
                item["tail_words_hex"] == ["0x00000000", "0x00000000"]
                for item in records
            )
        )

    def test_ledger_is_releasable(self) -> None:
        self.assertTrue(self.report["counts_as_formal_resnet_three_party_node"])
        self.assertEqual(
            self.report["project_ledger_delta"], {"before": "0/78", "after": "1/78"}
        )
        self.assertEqual(self.report["remaining_blockers"], [])

    def test_hardware_evidence_chain_preserves_all_boundaries(self) -> None:
        chain = self.report["hardware_evidence_chain"]
        atomic = chain["atomic_v3"]
        self.assertEqual(
            atomic["classification"],
            "ATOMIC_FUNCTIONAL_PASS_OBSERVER_TEMPORAL_EVIDENCE_INCOMPLETE",
        )
        self.assertTrue(atomic["formal_d_bit_exact"])
        self.assertTrue(atomic["observer_does_not_override_formal_d"])
        self.assertFalse(atomic["counts_as_e4"])
        self.assertFalse(atomic["counts_as_e5"])
        self.assertEqual(
            chain["full_v6_e4"]["classification"], "FIRST_DYNAMIC_PASS"
        )
        self.assertEqual(
            chain["full_v6_e5"]["classification"], "REPEATED_DYNAMIC_PASS"
        )
        self.assertFalse(chain["full_v6_e4"]["counts_as_simulator"])
        self.assertFalse(chain["full_v6_e5"]["counts_as_simulator"])

    def test_checked_in_artifacts_are_current(self) -> None:
        checked = json.loads((ROOT / REPORT_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(checked, self.report)
        report_hash = checked.pop("report_content_sha256")
        self.assertEqual(
            report_hash,
            __import__("hashlib").sha256(canonical_json_bytes(checked)).hexdigest(),
        )
        contract = json.loads((ROOT / CONTRACT_RELATIVE).read_text(encoding="utf-8"))
        self.assertEqual(contract["artifact"]["sha256"], sha256_file(ROOT / REPORT_RELATIVE))
        contract_hash = contract.pop("contract_content_sha256")
        self.assertEqual(
            contract_hash,
            __import__("hashlib").sha256(canonical_json_bytes(contract)).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
