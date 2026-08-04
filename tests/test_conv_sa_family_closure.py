from __future__ import annotations

import unittest
from pathlib import Path

from resnet50_pipeline.conv_sa_family_closure import (
    build_conv_sa_family_closure,
    rtl_int8_csa_from_reduced_words,
)


class ConvSaFamilyClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        cls.report = build_conv_sa_family_closure(cls.root)

    def test_stage_census_and_real_representative_are_frozen(self) -> None:
        self.assertEqual(
            self.report["stage_census"],
            {
                "typed_stage_count": 133,
                "conv_stage_count": 53,
                "matmul_stage_count": 1,
            },
        )
        representative = self.report["representative"]
        self.assertEqual(representative["hw_op_id"], "hwop-0004-00")
        self.assertEqual(representative["attributes"]["kernel_shape"], [1, 1])

    def test_stock_rtl_counterexample_is_not_conventional_dot(self) -> None:
        self.assertEqual(rtl_int8_csa_from_reduced_words(2, 2), 6)
        witness = self.report["arithmetic_boundary"]["counterexample"]
        self.assertEqual(witness["onnx_and_ndpfuncmodel"], 4)
        self.assertEqual(witness["stock_rtl"], 6)

    def test_release_fails_closed_before_package_generation(self) -> None:
        self.assertFalse(self.report["candidate_release"])
        self.assertFalse(self.report["formal_target_instance_allowed"])
        self.assertEqual(self.report["blocker_delta"]["close"], [])
        self.assertIn(
            "B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH",
            self.report["blocker_delta"]["add"],
        )


if __name__ == "__main__":
    unittest.main()
