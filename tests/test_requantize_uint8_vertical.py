from __future__ import annotations

import json
import unittest
from pathlib import Path

from resnet50_pipeline.requantize_uint8_vertical import (
    ARTIFACT_REL,
    CONFIG_REL,
    CONTRACT_REL,
    RULE_IDS,
    build_generation_receipt,
    build_graph,
    build_guard_sfu_words,
    build_numeric_evidence,
    build_static_configs,
    validate_guard_sfu_payload,
    guard_sfu_text,
)


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class RequantizeUint8VerticalTests(unittest.TestCase):
    def test_node0001_generation_receipt_and_numeric_replay(self) -> None:
        receipt = build_generation_receipt(ROOT)
        numeric = build_numeric_evidence(ROOT)

        self.assertEqual(
            receipt["status"],
            "generation_gate_satisfied_before_json_materialization",
        )
        self.assertEqual(receipt["rule_ids"], list(RULE_IDS))
        self.assertEqual(
            receipt["generation_boundary"],
            {
                "candidate_release": False,
                "formal_target_instance_allowed": False,
                "server_package": False,
                "rtl_modification_allowed": False,
            },
        )
        self.assertEqual(numeric["element_count"], 12_845_056)
        self.assertEqual(numeric["negative_element_count"], 3_246_544)
        self.assertEqual(numeric["minus_one_element_count"], 80)
        self.assertEqual(numeric["guard_bitwise_mismatch_count"], 0)
        self.assertEqual(numeric["final_uint8_mismatch_count"], 0)
        self.assertEqual(
            numeric["replay_sha256"], numeric["golden_sha256"]
        )

    def test_node0001_guard_payload_static_configs_and_graph(self) -> None:
        payload = validate_guard_sfu_payload(guard_sfu_text())
        configs, manifest = build_static_configs(ROOT)
        graph = build_graph()

        self.assertEqual(len(build_guard_sfu_words()), 200)
        self.assertEqual(payload["line_count_128b"], 50)
        self.assertEqual(payload["meaningful_word_count_32b"], 197)
        self.assertEqual(payload["padding_word_count_32b"], 3)
        self.assertEqual(payload["execplan_length_64b"], 100)
        self.assertEqual(len(configs), 9)
        self.assertEqual(len(manifest["operator_types"]), 9)
        self.assertEqual(len(graph["operators"]), 48)
        self.assertEqual(
            sum(op["stage"] == "guard" for op in graph["operators"]), 24
        )
        self.assertEqual(
            sum(
                op["stage"] == "round_saturate"
                for op in graph["operators"]
            ),
            24,
        )

    def test_materialized_node0001_local_e2_contract(self) -> None:
        report = _load(ROOT / ARTIFACT_REL / "local_e2_report.json")
        contract = _load(ROOT / CONTRACT_REL)
        config_manifest = _load(ROOT / CONFIG_REL / "manifest.json")

        self.assertEqual(
            report["status"],
            "NODE0001_REQUANT_TWO_STAGE_LOCAL_E2_COMPLETE",
        )
        self.assertFalse(report["candidate_release"])
        self.assertFalse(report["formal_target_instance_allowed"])
        self.assertFalse(report["server_package"])
        self.assertEqual(
            report["remaining_blocker"], "B_REQUANT_SERVER_E4_E5"
        )
        self.assertEqual(
            report["materialized_roundtrip"]["occurrence_count"], 24
        )
        self.assertEqual(report["materialized_roundtrip"]["stage_count"], 48)
        self.assertEqual(
            report["materialized_roundtrip"][
                "bitstream_decoded_stage_count"
            ],
            48,
        )
        self.assertEqual(
            report["materialized_roundtrip"][
                "consumer_intermediate_external_preload_count"
            ],
            0,
        )
        self.assertEqual(
            report["materialized_roundtrip"]["guard_sfu_load_count"], 1
        )
        self.assertEqual(report["lifecycle"]["start_comp_count"], 48)
        self.assertEqual(report["lifecycle"]["barrier_count"], 48)
        self.assertEqual(report["lifecycle"]["repeat_num"], 48)
        self.assertTrue(
            report["native_double_rebuild"][
                "deterministic_files_byte_identical"
            ]
        )
        self.assertEqual(
            contract["remaining_blockers"], ["B_REQUANT_SERVER_E4_E5"]
        )
        self.assertFalse(config_manifest["candidate_release"])
        self.assertFalse(config_manifest["formal_target_config"])


if __name__ == "__main__":
    unittest.main()
