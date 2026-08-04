from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_prefill_stage_producer import (
    CONTRACT_PATH,
    DeepSeekPrefillStageProducerError,
    GEMM_A_LAYOUT_HINT,
    GEMM_B_LAYOUT_HINT,
    OUTPUT_PATH,
    SOFTMAX_EXP_LAYOUT_HINT,
    SOFTMAX_MASK_LAYOUT_HINT,
    build_prefill_stage_producer_contract,
    build_rule_normalized_prefill_stage,
    validate_prefill_stage_producer_contract,
)


ROOT = Path(__file__).resolve().parents[1]


class DeepSeekPrefillStageProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(
            (ROOT / CONTRACT_PATH).read_text(encoding="utf-8")
        )

    def test_normalization_is_exactly_twelve_rule_owned_leaves(self) -> None:
        graph, changes = build_rule_normalized_prefill_stage(ROOT)
        self.assertEqual(len(changes), 12)
        self.assertEqual(
            graph,
            json.loads((ROOT / OUTPUT_PATH).read_text(encoding="utf-8")),
        )
        self.assertEqual(
            {item["path"] for item in changes},
            {
                "operators.op1.used_slices",
                "operators.op1.inputs.A.shape",
                "operators.op1.inputs.A.type",
                "operators.op2.inputs.A.type",
                "operators.op33.used_slices",
                "operators.op33.inputs.A.shape",
                "operators.op33.inputs.A.type",
                "operators.op34.inputs.A.type",
                "operators.op24.inputs.C.write_reg_hint",
                "operators.op26.inputs.A.write_reg_hint",
                "operators.op37.inputs.A.write_reg_hint",
                "operators.op37.inputs.B.write_reg_hint",
            },
        )

    def test_active_stage_owns_rms_softmax_and_gemm_semantics(self) -> None:
        graph, _ = build_rule_normalized_prefill_stage(ROOT)
        operators = {item["id"]: item for item in graph["operators"]}
        for remote_id, sfu_id in (("op1", "op2"), ("op33", "op34")):
            remote = operators[remote_id]
            self.assertEqual(remote["used_slices"], "0b" + "1" * 28)
            self.assertEqual(
                remote["inputs"]["A"]["shape"],
                [1, "slice_per_head", "sequence_length"],
            )
            self.assertEqual(remote["inputs"]["A"]["type"], "slice0")
            self.assertNotIn("type", operators[sfu_id]["inputs"]["A"])
        self.assertEqual(
            operators["op24"]["inputs"]["C"]["write_reg_hint"],
            SOFTMAX_MASK_LAYOUT_HINT,
        )
        self.assertEqual(
            operators["op26"]["inputs"]["A"]["write_reg_hint"],
            SOFTMAX_EXP_LAYOUT_HINT,
        )
        self.assertEqual(
            operators["op37"]["inputs"]["A"]["write_reg_hint"],
            GEMM_A_LAYOUT_HINT,
        )
        self.assertEqual(
            operators["op37"]["inputs"]["B"]["write_reg_hint"],
            GEMM_B_LAYOUT_HINT,
        )

    def test_contract_matches_and_closes_only_registered_blockers(self) -> None:
        rebuilt = build_prefill_stage_producer_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_prefill_stage_producer_contract(self.checked, ROOT)
        self.assertEqual(
            set(self.checked["closed_blockers"]),
            {
                "B_DS_RMSNORM_STAGE_TOPOLOGY_GAP",
                "B_DS_SOFTMAX_STAGE_LAYOUT_HINT_GAP",
                "B_DS_GEMM_LAYOUT_HINT_STAGE_GAP",
            },
        )
        self.assertFalse(
            self.checked["upstream_boundary"][
                "raw_upstream_graph_modified"
            ]
        )

    def test_contract_tamper_fails_closed(self) -> None:
        tampered = deepcopy(self.checked)
        tampered["normalization_changes"][0]["after"] = "0b1"
        with self.assertRaisesRegex(
            DeepSeekPrefillStageProducerError,
            "contract differs",
        ):
            validate_prefill_stage_producer_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
