from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.sum_config_audit import (
    SUM_TEMPLATE_NAMES,
    SumConfigAuditError,
    audit_sum_encoder,
    build_sum_config_audit,
    validate_sum_template,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "ndp-sim-ref"


class SumConfigAuditTests(unittest.TestCase):
    def _load(self, name: str) -> dict:
        return json.loads((SOURCE_ROOT / "jsons" / name).read_text(encoding="utf-8"))

    def test_all_sum_templates_pass_strict_candidate_preflight(self) -> None:
        for name in SUM_TEMPLATE_NAMES:
            with self.subTest(name=name):
                result = validate_sum_template(self._load(name), name)
                self.assertEqual(result["status"], "candidate_preflight_valid")
                self.assertEqual(result["numerical_status"], "not_validated")
                self.assertTrue(result["no_gate_authority"])

    def test_report_is_deterministic_json_and_has_no_gate_authority(self) -> None:
        first = build_sum_config_audit(SOURCE_ROOT)
        second = build_sum_config_audit(SOURCE_ROOT)
        first_json = json.dumps(first, ensure_ascii=False, sort_keys=True, allow_nan=False)
        second_json = json.dumps(second, ensure_ascii=False, sort_keys=True, allow_nan=False)
        self.assertEqual(first_json, second_json)
        self.assertEqual(first["scope"]["template_count"], 11)
        self.assertTrue(first["authority"]["no_gate_authority"])
        self.assertFalse(first["authority"]["w5_authorized"])
        self.assertEqual(first["encoder_probe"]["status"], "not_run")

    def test_remote_names_do_not_claim_neighbor_transport(self) -> None:
        report = build_sum_config_audit(SOURCE_ROOT)
        remote = [
            record for record in report["templates"]
            if record["preflight"]["family"] == "remote_sum"
        ]
        self.assertEqual(len(remote), 4)
        self.assertTrue(all(record["cross_slice"]["remote_named"] for record in remote))
        self.assertTrue(
            all(not record["cross_slice"]["neighbor_or_n2n_config_present"] for record in remote)
        )
        self.assertTrue(
            all(not record["completion_events"]["hardware_completion_protocol_validated"] for record in remote)
        )

    def test_resnet_gap_candidate_is_partial_only(self) -> None:
        report = build_sum_config_audit(SOURCE_ROOT)
        candidates = [
            record for record in report["templates"]
            if record["resnet_gap_relevance"]["candidate_part"]
        ]
        self.assertEqual([Path(record["template"]).name for record in candidates], ["sum_config_32_32.json"])
        self.assertFalse(candidates[0]["resnet_gap_relevance"]["direct_gap_template"])
        self.assertFalse(candidates[0]["dtype"]["requant_present"])
        self.assertFalse(candidates[0]["handler"]["handler_exists"])

    def test_handler_and_base_info_gaps_are_exposed(self) -> None:
        report = build_sum_config_audit(SOURCE_ROOT)
        by_name = {Path(record["template"]).name: record for record in report["templates"]}
        decode = by_name["decode_summac_fp32N_fp32N.json"]
        self.assertTrue(decode["handler"]["handler_exists"])
        self.assertFalse(decode["base_info"]["registered"])
        fp16_remote = by_name["prefill_remote_sum_4slice_fp16MN_fp32MN.json"]
        self.assertTrue(fp16_remote["base_info"]["conflicts"])
        for record in report["templates"]:
            self.assertFalse(record["handler"]["uses_output_dimensions_in_updates"])
            self.assertFalse(record["handler"]["updates_ga_or_requant_fields"])

    def test_preflight_rejects_overflow_wrong_opcode_and_output_requant(self) -> None:
        config = self._load("sum_config_32_32.json")
        bad_values = []
        overflow = deepcopy(config)
        overflow["dram_loop_configs"]["LC1"]["end"] = 1 << 17
        bad_values.append(overflow)
        opcode = deepcopy(config)
        opcode["general_array"]["PE_array"]["PE00"]["alu_opcode"] = "max"
        bad_values.append(opcode)
        requant = deepcopy(config)
        requant["general_array"]["outport"]["int32touint8"] = "true"
        bad_values.append(requant)
        for value in bad_values:
            with self.assertRaises(SumConfigAuditError):
                validate_sum_template(value, "sum_config_32_32.json")

    def test_official_encoder_probe_is_temporary_and_not_numerical_validation(self) -> None:
        result = audit_sum_encoder(SOURCE_ROOT, ("sum_config_32_32.json",))
        record = result["sum_config_32_32.json"]
        self.assertEqual(record["status"], "encoding_deterministic")
        self.assertEqual(record["run_count"], 2)
        self.assertEqual(record["numerical_status"], "not_validated")
        self.assertTrue(record["no_gate_authority"])


if __name__ == "__main__":
    unittest.main()
