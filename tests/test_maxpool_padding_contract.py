from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.maxpool_padding_contract import (
    CURRENT_PADDING_RTL_RECEIPT,
    MaxPoolPaddingContractError,
    validate_maxpool_padding_rtl_current_receipt,
    validate_maxpool_zero_padding_contract,
)
from resnet50_pipeline.strict_config_materialization import (
    validate_materialized_strict_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts/maxpool_uint8_zero_padding_contract.json"
STRICT = ROOT / "configs/native_ndp_sim/maxpool_config_16_16_16_stride2_padding1_strict_v1"
NODE0002_CONTRACT = ROOT / "contracts/maxpool_node0002_zero_padding_contract.json"
NODE0002_STRICT = ROOT / "configs/native_ndp_sim/maxpool_config_16_112_112_stride2_padding1_strict_v1"
CURRENT_RTL_RECEIPT = ROOT / CURRENT_PADDING_RTL_RECEIPT


class MaxPoolPaddingContractTests(unittest.TestCase):
    def test_contract_binds_uint8_rtl_and_exact_legacy_source(self) -> None:
        value = validate_maxpool_zero_padding_contract(ROOT, CONTRACT)
        self.assertEqual(value["operator_semantics"]["logical_dtype"], "uint8")
        self.assertEqual(value["operator_semantics"]["max_identity"], 0)
        self.assertEqual(
            value["evidence"]["rtl_semantics_record"]["byte_lane_checks"],
            262_144,
        )
        self.assertFalse(value["authorization"]["formal_target_config"])

    def test_checked_strict_materialization_requires_the_contract(self) -> None:
        manifest = validate_materialized_strict_config(STRICT)
        self.assertEqual(
            manifest["adjudication"]["normalization_decision"],
            "approved-explicit-zero-padding-operator-contract",
        )
        self.assertEqual(
            manifest["operator_padding_contract"]["contract_sha256"],
            validate_maxpool_zero_padding_contract(ROOT, CONTRACT)["contract_sha256"],
        )

    def test_resnet_node0002_contract_binds_exact_active_shape(self) -> None:
        value = validate_maxpool_zero_padding_contract(ROOT, NODE0002_CONTRACT)
        self.assertEqual(
            value["authorization"]["source_path"],
            "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json",
        )
        self.assertEqual(
            value["operator_semantics"]["shape_scope"],
            "resnet50_node_0002_local_tile",
        )
        self.assertEqual(
            value["operator_semantics"]["sample_shape"], [1, 112, 112, 16]
        )
        manifest = validate_materialized_strict_config(NODE0002_STRICT)
        self.assertEqual(
            manifest["operator_padding_contract"]["contract_sha256"],
            value["contract_sha256"],
        )

    def test_current_padding_rtl_receipt_binds_cloud_checkout_and_mirror(
        self,
    ) -> None:
        value = validate_maxpool_padding_rtl_current_receipt(
            ROOT, CURRENT_RTL_RECEIPT
        )
        authority = value["cloud_authority_checkout"]
        mirror = value["local_runtime_mirror"]
        self.assertEqual(
            authority["commit"],
            "0ccae916ef61904a64d6cf8ec1d1931b45e428d8",
        )
        self.assertEqual(
            authority["sha256"],
            "08b35e80c234c6567099c4da5e18ff0a18955e259b7c12bedff72325f744038c",
        )
        self.assertEqual(mirror["sha256"], authority["sha256"])
        self.assertTrue(mirror["byte_equal_to_cloud_authority_checkout"])
        self.assertEqual(
            value["padding_substitution"]["equation"],
            "padding_mask ? padding_value : "
            "branch_or_tail_mask ? zero : ddr_data",
        )

    def test_current_padding_rtl_receipt_hash_and_equation_tamper_fail_closed(
        self,
    ) -> None:
        value = json.loads(CURRENT_RTL_RECEIPT.read_text(encoding="utf-8"))
        mutations = []
        wrong_hash = copy.deepcopy(value)
        wrong_hash["cloud_authority_checkout"]["sha256"] = "0" * 64
        mutations.append(wrong_hash)
        wrong_equation = copy.deepcopy(value)
        wrong_equation["padding_substitution"]["equation"] = (
            "padding_mask ? ddr_data : padding_value"
        )
        mutations.append(wrong_equation)
        for index, tampered in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as temp_text:
                path = Path(temp_text) / "receipt.json"
                path.write_text(json.dumps(tampered), encoding="utf-8")
                with self.assertRaisesRegex(
                    MaxPoolPaddingContractError,
                    "current padding RTL receipt differs",
                ):
                    validate_maxpool_padding_rtl_current_receipt(ROOT, path)

    def test_contract_tamper_fails_closed(self) -> None:
        value = json.loads(CONTRACT.read_text(encoding="utf-8"))
        tampered = copy.deepcopy(value)
        tampered["operator_semantics"]["max_identity"] = 255
        with tempfile.TemporaryDirectory() as temp_text:
            path = Path(temp_text) / "contract.json"
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(
                MaxPoolPaddingContractError, "differs from current hash-bound evidence"
            ):
                validate_maxpool_zero_padding_contract(ROOT, path)


if __name__ == "__main__":
    unittest.main()
