from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from resnet50_pipeline.r5_lowering_bundle import (
    R5LoweringBundleError,
    build_r5_lowering_bundle,
    validate_r5_lowering_bundle,
)


ROOT = Path(__file__).resolve().parents[1]


class R5LoweringBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_r5_lowering_bundle(ROOT)

    def test_exact_stage_node_and_type_coverage(self) -> None:
        coverage = self.bundle["coverage"]
        self.assertEqual(coverage["node_count"], 78)
        self.assertEqual(coverage["stage_count"], 133)
        self.assertEqual(coverage["request_count"], 133)
        self.assertEqual(len(self.bundle["node_stage_dags"]), 78)
        self.assertEqual(len(self.bundle["requests"]), 133)
        self.assertEqual(
            sum(coverage["hw_op_type_counts"].values()), 133
        )

    def test_requests_preserve_typed_values_dags_and_patch_identity(self) -> None:
        patch_sha = self.bundle["patchset"]["patchset_sha256"]
        seen: set[str] = set()
        for ordinal, request in enumerate(self.bundle["requests"]):
            self.assertEqual(request["ordinal"], ordinal)
            self.assertEqual(request["patchset"]["patchset_sha256"], patch_sha)
            self.assertTrue(
                all(value in seen for value in request["predecessor_hw_op_ids"])
            )
            seen.add(request["identity"]["hw_op_id"])
            for parameter in request["typed_parameters"]:
                value = parameter["value"]
                self.assertIn("dtype", value)
                self.assertIn("shape", value)
                self.assertIn("value_sha256", value)
        self.assertEqual(len(seen), 133)

    def test_local_resolution_and_formal_release_are_separate(self) -> None:
        coverage = self.bundle["coverage"]
        self.assertEqual(coverage["formal_target_config_ready_count"], 0)
        self.assertEqual(coverage["blocked_request_count"], 133)
        self.assertEqual(coverage["local_lowering_resolved_count"], 5)
        self.assertEqual(coverage["local_lowering_unresolved_count"], 128)
        self.assertEqual(coverage["candidate_config_emission_allowed_count"], 2)
        self.assertEqual(coverage["candidate_zero_copy_binding_allowed_count"], 1)
        self.assertEqual(coverage["json_emitter_ready_count"], 4)
        self.assertEqual(coverage["rtl_semantics_compatible_count"], 3)
        self.assertEqual(coverage["dynamic_release_ready_count"], 0)
        effective = {item["hw_op_id"]: item for item in self.bundle["effective_resolutions"]}
        self.assertEqual(
            effective["hwop-0002-00"]["disposition"],
            "draft_json_emitter_ready_rtl_semantics_blocked",
        )
        self.assertEqual(
            effective["hwop-0073-00"]["disposition"],
            "candidate_zero_copy_binding_allowed",
        )
        self.assertEqual(
            effective["hwop-0071-00"]["disposition"],
            "draft_json_emitter_ready_rtl_semantics_blocked",
        )
        self.assertEqual(
            effective["hwop-0077-00"]["disposition"],
            "candidate_config_emission_allowed",
        )
        self.assertEqual(
            effective["hwop-0001-01"]["disposition"],
            "candidate_config_emission_allowed",
        )
        self.assertEqual(
            set(effective["hwop-0001-01"]["resolved_blockers"]),
            {
                "B_EXECPLAN_TYPED_TRANSPORT",
                "B_LAYOUT_APPROVAL",
                "B_REQUANT_TARGET_NUMERICS",
            },
        )
        self.assertEqual(
            effective["hwop-0001-01"]["effective_blockers"], []
        )
        self.assertEqual(
            set(effective["hwop-0077-00"]["resolved_blockers"]),
            {
                "B_DEQUANT_STANDALONE",
                "B_EXECPLAN_TYPED_TRANSPORT",
                "B_LAYOUT_APPROVAL",
            },
        )
        self.assertEqual(
            set(effective["hwop-0071-00"]["resolved_blockers"]),
            {
                "B_EXECPLAN_TYPED_TRANSPORT",
                "B_GAP_CENTERED_SUM",
                "B_LAYOUT_APPROVAL",
                "B_SUM_COMPLETION",
                "B_SUM_CROSS_SLICE",
            },
        )
        self.assertEqual(
            effective["hwop-0002-00"]["rtl_semantic_blockers"],
            ["B_GA_INT8_MAX_FLOW", "B_GA_INT8_MAX_NUMERIC"],
        )
        self.assertEqual(
            effective["hwop-0071-00"]["rtl_semantic_blockers"],
            ["B_GAP_D_INDEX_CARRIER_SEMANTICS", "B_GAP_GA_ACCUM_STATE"],
        )
        self.assertTrue(
            all(not item["formal_target_instance_allowed"] for item in effective.values())
        )

    def test_historical_request_hashes_remain_self_consistent(self) -> None:
        from resnet50_pipeline.hashing import canonical_json_bytes, sha256_bytes

        for request in self.bundle["requests"]:
            payload = {key: value for key, value in request.items() if key != "request_sha256"}
            self.assertEqual(
                request["request_sha256"], sha256_bytes(canonical_json_bytes(payload))
            )

    def test_tamper_and_checked_in_drift_fail_closed(self) -> None:
        checked = json.loads(
            (ROOT / "contracts/resnet50_r5_lowering_bundle.json").read_text(
                encoding="utf-8"
            )
        )
        validate_r5_lowering_bundle(checked, ROOT)
        tampered = copy.deepcopy(checked)
        tampered["requests"][0]["typed_parameters"][0]["value"]["scalar"] = 0
        with self.assertRaises(R5LoweringBundleError):
            validate_r5_lowering_bundle(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
