from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.matmul_config_audit import (
    PRIMARY_GEMV_TEMPLATE,
    SA_TEMPLATES,
    MatmulConfigAuditError,
    audit_matmul_encoder,
    build_matmul_candidate_report,
    extract_matmul_crosswalk,
    inventory_sa_templates,
    validate_matmul_template,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ndp-sim-ref"


class MatmulConfigAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.configs = {
            name: json.loads((SOURCE / "jsons" / name).read_text(encoding="utf-8"))
            for name in SA_TEMPLATES
        }

    def test_inventory_and_all_six_locked_candidates_preflight(self) -> None:
        inventory = inventory_sa_templates(SOURCE)
        self.assertEqual(inventory["candidate_count"], 6)
        self.assertEqual(inventory["gemm_count"], 3)
        self.assertEqual(inventory["gemv_count"], 3)
        self.assertEqual(inventory["named_int8_template_count"], 0)
        for name, config in self.configs.items():
            result = validate_matmul_template(config, name)
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["sa"]["input_dtype"], "fp16")
            self.assertFalse(result["sa"]["bias_enable"])
            self.assertFalse(result["sa"]["requant_to_uint8"])
            self.assertEqual(result["numerical_status"], "not_validated")
            self.assertTrue(result["no_gate_authority"])

    def test_primary_gemv_shape_lc_stream_buffer_sa_crosswalk(self) -> None:
        crosswalk = extract_matmul_crosswalk(SOURCE)
        primary = crosswalk["templates"][PRIMARY_GEMV_TEMPLATE]
        chain = primary["observed_chain"]
        self.assertEqual(chain["shape_metadata"], {"M": 1, "N": 128, "K": 32})
        self.assertEqual(chain["lc_end"]["LC1"], 16)
        self.assertEqual(chain["stream"]["stream3"]["target"], "D")
        self.assertEqual(chain["stream"]["stream3"]["idx_size"], [127, None, None])
        self.assertEqual(chain["sa"]["mode"], "gemv")
        self.assertEqual(chain["ga_boundary"], "direct_SA_to_D")

    def test_decode_gemv_explicitly_bridges_sa_through_ga_sum(self) -> None:
        crosswalk = extract_matmul_crosswalk(SOURCE)
        for name in ("decode_gemv_local.json", "decode_gemv_ring.json"):
            candidate = crosswalk["templates"][name]
            self.assertTrue(candidate["preflight"]["resources"]["ga_bridge"])
            self.assertEqual(
                candidate["observed_chain"]["ga_boundary"],
                "SA_fp32_to_buffer5_to_GA_sum_to_fp16_D",
            )
            self.assertEqual(candidate["observed_chain"]["buffer"]["buffer5"]["dst_port"], 1)

    def test_handlers_are_present_but_placeholder_and_qparam_free(self) -> None:
        binding = extract_matmul_crosswalk(SOURCE)["handler_binding"]
        self.assertEqual(binding["handler_count"], 5)
        self.assertEqual(binding["status"], "partial_binding_only")
        self.assertTrue(all(item["declared_placeholder"] for item in binding["handlers"].values()))
        self.assertTrue(all(not item["typed_qparams_consumed"] for item in binding["handlers"].values()))
        self.assertFalse(binding["operator_spec_has_typed_qparams"])
        self.assertEqual(
            binding["operator_base_info_registered_types"],
            ["prefill_gemm_local", "prefill_gemm_ring_4slice"],
        )
        self.assertIn(PRIMARY_GEMV_TEMPLATE, binding["templates_without_registered_operator_type"])

    def test_resnet_shape_dtype_bias_psum_requant_gaps_are_fail_closed_evidence(self) -> None:
        gap = extract_matmul_crosswalk(SOURCE)["resnet_qlinearmatmul_gap"]
        self.assertEqual(gap["resnet_shape_MNK"], [16, 1000, 2048])
        self.assertEqual(gap["local_gemm_floor_projection"]["M_div_32"], 0)
        self.assertEqual(gap["local_gemm_floor_projection"]["N_remainder_32"], 8)
        self.assertFalse(gap["bias"]["qlinearmatmul_has_bias_input"])
        self.assertEqual(gap["bias"]["resnet_dense_bias_location"], "following QLinearAdd")
        self.assertFalse(gap["complete_compatible_template_exists"])
        missing = " ".join(gap["missing"])
        for token in ("INT8", "tail", "zero-point", "qparam", "psum", "requant"):
            self.assertIn(token, missing)

    def test_unknown_field_int8_relabel_and_overflow_fail_closed(self) -> None:
        unknown = deepcopy(self.configs[PRIMARY_GEMV_TEMPLATE])
        unknown["guessed_requant"] = True
        with self.assertRaisesRegex(MatmulConfigAuditError, "unexpected"):
            validate_matmul_template(unknown, PRIMARY_GEMV_TEMPLATE)

        int8 = deepcopy(self.configs[PRIMARY_GEMV_TEMPLATE])
        int8["special_array"]["data_type"] = "int8"
        with self.assertRaisesRegex(MatmulConfigAuditError, "INT8 is not validated"):
            validate_matmul_template(int8, PRIMARY_GEMV_TEMPLATE)

        overflow = deepcopy(self.configs[PRIMARY_GEMV_TEMPLATE])
        overflow["dram_loop_configs"]["LC1"]["end"] = 1 << 17
        with self.assertRaisesRegex(MatmulConfigAuditError, "refusing silent truncation"):
            validate_matmul_template(overflow, PRIMARY_GEMV_TEMPLATE)

    def test_report_is_json_serializable_deterministic_and_has_no_gate_authority(self) -> None:
        first = build_matmul_candidate_report(SOURCE)
        second = build_matmul_candidate_report(SOURCE)
        first_bytes = json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        second_bytes = json.dumps(second, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual(first_bytes, second_bytes)
        self.assertEqual(first["status"], "candidate_preflight_only")
        self.assertEqual(first["numerical_status"], "not_validated")
        self.assertFalse(first["w5_instance_generated"])
        self.assertFalse(first["g4_authorized"])
        self.assertTrue(first["no_gate_authority"])

    def test_primary_official_encoder_is_deterministic_sensitive_but_not_numerical(self) -> None:
        report = audit_matmul_encoder(SOURCE)
        self.assertEqual(report["determinism"]["status"], "passed")
        self.assertEqual(report["differential_sensitivity"]["status"], "passed")
        self.assertNotEqual(
            report["differential_sensitivity"]["baseline_128b_sha256"],
            report["differential_sensitivity"]["modified_128b_sha256"],
        )
        self.assertEqual(report["fail_closed"]["status"], "passed")
        self.assertEqual(report["numerical_status"], "not_validated")
        self.assertTrue(report["no_gate_authority"])


if __name__ == "__main__":
    unittest.main()
