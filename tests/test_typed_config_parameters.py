from __future__ import annotations

import json
import os
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from resnet50_pipeline.hashing import canonical_json_bytes, sha256_file
from resnet50_pipeline.typed_config_parameters import (
    TypedConfigParameterError,
    build_typed_config_parameter_contract,
    validate_typed_config_parameter_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class TypedConfigParameterContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = build_typed_config_parameter_contract(ROOT)

    def test_binds_all_w3_nodes_hwops_and_concrete_ports(self) -> None:
        coverage = self.report["coverage"]
        self.assertEqual(coverage["node_count"], 78)
        self.assertEqual(coverage["hw_op_count"], 133)
        self.assertEqual(coverage["internal_tensor_count"], 55)
        self.assertTrue(coverage["all_nodes_bound"])
        self.assertTrue(coverage["all_hw_ops_bound"])
        self.assertTrue(coverage["all_formal_target_instances_rejected"])
        for record in self.report["hw_ops"]:
            self.assertTrue(record["ports"]["inputs"])
            self.assertTrue(record["ports"]["outputs"])
            for port in record["ports"]["inputs"] + record["ports"]["outputs"]:
                self.assertTrue(port["shape"])
                self.assertNotEqual(port["dtype"], "unknown")
                self.assertEqual(len(port["identity_sha256"]), 64)
            self.assertFalse(record["formal_target_instance_allowed"])

    def test_w3_identity_and_report_are_reproducible_without_npy_reads(self) -> None:
        source = self.report["source"]
        for path_field, hash_field in (
            ("model_graph_path", "model_graph_sha256"),
            ("runtime_manifest_path", "runtime_manifest_sha256"),
            ("subop_manifest_path", "subop_manifest_sha256"),
            ("target_config_authority_path", "target_config_authority_sha256"),
        ):
            self.assertEqual(sha256_file(ROOT / source[path_field]), source[hash_field])
        with patch("numpy.load", side_effect=AssertionError("W3 payload read")):
            second = build_typed_config_parameter_contract(ROOT)
        self.assertEqual(canonical_json_bytes(self.report), canonical_json_bytes(second))
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                cross_path = build_typed_config_parameter_contract(ROOT)
            finally:
                os.chdir(original_cwd)
        self.assertEqual(
            canonical_json_bytes(self.report), canonical_json_bytes(cross_path)
        )
        self.assertFalse(second["scope"]["reads_w3_tensor_payloads"])

    def test_scalar_and_per_channel_qparams_are_never_implicitly_lost(self) -> None:
        parameters = [
            parameter
            for record in self.report["hw_ops"]
            for parameter in record["parameters"]
        ]
        direct = [
            parameter
            for parameter in parameters
            if parameter["provenance"]["kind"] == "onnx_initializer"
        ]
        self.assertEqual(len(direct), 491)
        self.assertEqual(
            sum(item["parameter_kind"] in {"scale", "zero_point"} for item in direct),
            438,
        )
        self.assertEqual(sum(item["parameter_kind"] == "bias" for item in direct), 53)
        per_channel = [item for item in direct if item["value"]["value_kind"] == "per_channel"]
        self.assertEqual(len(per_channel), 159)
        for parameter in direct:
            value = parameter["value"]
            self.assertEqual(value["value_sha256"], parameter["provenance"]["initializer_sha256"])
            if value["value_kind"] == "per_channel":
                self.assertEqual(value["axis"], 0)
                self.assertGreater(value["element_count"], 1)
                self.assertIn(parameter["name"], {"w_scale", "w_zero_point", "bias"})
            else:
                self.assertEqual(value["element_count"], 1)
                self.assertIn("scalar", value)
                if value["dtype"] == "float32":
                    self.assertRegex(value["float32_bits"], r"^0x[0-9a-f]{8}$")
        conv_multipliers = [
            item
            for item in parameters
            if item["name"] == "requant_multiplier"
            and item["parameter_id"].startswith("hwop-")
            and item["value"]["value_kind"] == "per_channel"
        ]
        self.assertEqual(len(conv_multipliers), 53)
        self.assertTrue(all(item["value"]["axis"] == 0 for item in conv_multipliers))

    def test_add_gap_matmul_and_view_geometry_remains_explicit(self) -> None:
        add_records = [
            record for record in self.report["hw_ops"] if record["onnx_op_type"] == "QLinearAdd"
        ]
        self.assertEqual(len(add_records), 17)
        for record in add_records:
            roles = [item["role"] for item in record["ports"]["inputs"]]
            self.assertEqual(
                roles,
                [
                    "a",
                    "a_scale",
                    "a_zero_point",
                    "b",
                    "b_scale",
                    "b_zero_point",
                    "y_scale",
                    "y_zero_point",
                ],
            )
            self.assertEqual(record["ports"]["outputs"][0]["dtype"], "uint8")
            self.assertEqual(
                record["logical_geometry"]["broadcast"]["output_shape"],
                record["ports"]["outputs"][0]["shape"],
            )
        gap_requant = next(
            record
            for record in self.report["hw_ops"]
            if record["onnx_op_type"] == "QLinearGlobalAveragePool"
            and record["stage"] == "requantize"
        )
        spatial = next(
            item for item in gap_requant["parameters"] if item["name"] == "spatial_element_count"
        )
        self.assertEqual(spatial["value"]["scalar"], 49)
        matmul = next(
            record
            for record in self.report["hw_ops"]
            if record["onnx_op_type"] == "QLinearMatMul" and record["stage"] == "accumulate"
        )
        self.assertEqual(matmul["logical_geometry"]["mnk"], {"M": 16, "N": 1000, "K": 2048})
        view = next(record for record in self.report["hw_ops"] if record["hw_op_type"] == "View")
        self.assertTrue(view["logical_geometry"]["view"]["logical_zero_copy_candidate"])

    def test_three_state_field_provenance_is_fail_closed(self) -> None:
        coverage = self.report["coverage"]
        self.assertEqual(
            coverage["field_resolution_counts"],
            {"approval_required": 135, "derived": 359, "rejected": 263},
        )
        fields = [field for record in self.report["hw_ops"] for field in record["field_bindings"]]
        self.assertEqual({field["resolution"] for field in fields}, {"derived", "approval_required", "rejected"})
        self.assertTrue(all(field["formal_target_write_allowed"] is False for field in fields))
        self.assertTrue(all(field["blockers"] for field in fields if field["resolution"] != "derived"))
        families = {field["field_family"] for field in fields}
        self.assertIn("ga_qlinearadd_uint8_output_requant", families)
        self.assertIn("sa_int8_matmul_accumulate_psum_tail", families)
        self.assertIn("ga_centered_uint8_to_int32_sum", families)
        self.assertIn("view_zero_copy_physical_identity", families)
        self.assertFalse(self.report["scope"]["w5_authorized"])
        self.assertFalse(self.report["scope"]["g4_passed"])
        self.assertTrue(self.report["scope"]["no_gate_authority"])

    def test_validator_rejects_axis_loss_target_write_and_coverage_drop(self) -> None:
        axis_loss = deepcopy(self.report)
        parameter = next(
            item
            for record in axis_loss["hw_ops"]
            for item in record["parameters"]
            if item["value"]["value_kind"] == "per_channel"
        )
        del parameter["value"]["axis"]
        with self.assertRaisesRegex(TypedConfigParameterError, "per-channel"):
            validate_typed_config_parameter_contract(axis_loss)

        target_write = deepcopy(self.report)
        target_write["hw_ops"][0]["field_bindings"][0]["formal_target_write_allowed"] = True
        with self.assertRaisesRegex(TypedConfigParameterError, "target write"):
            validate_typed_config_parameter_contract(target_write)

        coverage_drop = deepcopy(self.report)
        coverage_drop["hw_ops"].pop()
        with self.assertRaisesRegex(TypedConfigParameterError, "133 hw_ops"):
            validate_typed_config_parameter_contract(coverage_drop)

    def test_checked_in_contract_is_exact_generated_output(self) -> None:
        path = ROOT / "contracts" / "typed_config_parameter_contract.json"
        checked_in = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(canonical_json_bytes(checked_in), canonical_json_bytes(self.report))


if __name__ == "__main__":
    unittest.main()
