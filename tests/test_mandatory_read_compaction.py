from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".agents" / "rules"
REGISTRY = ROOT / "contracts" / "active_rule_registry_v1.json"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class MandatoryReadCompactionTests(unittest.TestCase):
    def test_agent_plan_router_history_are_distinct_entries(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["entrypoints"]["stable_entry"], ".agents/agent.md")
        self.assertEqual(registry["entrypoints"]["current_state"], ".agents/plan.md")
        self.assertEqual(
            registry["entrypoints"]["router"], ".agents/rules/生成前必读索引.md"
        )
        self.assertEqual(
            registry["entrypoints"]["history_entry"], ".agents/history/rules/README.md"
        )

    def test_router_owns_the_common_read_matrix(self) -> None:
        router = _text(".agents/rules/生成前必读索引.md")
        for required in (
            "算子配置规则.md",
            "服务器测试包生成规则.md",
            "NDP硬件字段语义.md",
            "会话转接与所有权规则.md",
            "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
            "NO_DYNAMIC_BASELINE",
            "FIRST_DYNAMIC_FAILURE",
        ):
            self.assertIn(required, router)

    def test_archived_rules_have_one_non_active_entry(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        history = ROOT / registry["history"]["root"]
        self.assertFalse(registry["history"]["default_read"])
        self.assertTrue((history / "README.md").is_file())
        for basename in registry["history"]["archived_active_basenames"]:
            self.assertFalse((RULES / basename).exists(), basename)
            self.assertTrue(any(history.rglob(basename)), basename)

    def test_active_rule_count_is_small_and_exact(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        expected = {item["path"] for item in registry["exact_active_rules"]}
        actual = {path.relative_to(ROOT).as_posix() for path in RULES.glob("*.md")}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 14)

    def test_router_contains_no_semantic_definition_or_version_result(self) -> None:
        router = _text(".agents/rules/生成前必读索引.md")
        self.assertNotRegex(router, r"^规则 ID：", msg="router must only reference rules")
        self.assertIsNone(re.search(r"onecmd_v\d+|repair_v\d+|probe_v\d+", router))
        self.assertLessEqual(len(router.splitlines()), 180)

    def test_family_and_primitive_rules_do_not_embed_current_status(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for item in registry["exact_active_rules"]:
            if item["layer"] not in {"family", "primitive"}:
                continue
            text = _text(item["path"])
            self.assertNotIn("当前裁决：", text, item["path"])
            self.assertNotIn("当前状态：", text, item["path"])
            self.assertIsNone(
                re.search(r"CDA-[A-Z0-9_-]*(?:V\d+|DYNAMIC-PASS)", text),
                item["path"],
            )

    def test_effective_hardware_counterexamples_remain_active(self) -> None:
        active = "\n".join(path.read_text(encoding="utf-8") for path in RULES.glob("*.md"))
        for rule_id in (
            "CDA-SA-INT8-CSA-001",
            "CDA-SA-FP-CONVERT-001",
            "CDA-GA-INPORT-CONVERT-001",
            "CDA-GA-INT8-MAX-PIPE-001",
            "CDA-GAP-GA-ACCUM-STATE-001",
            "CDA-N2N-ROUTE-TRANSFER-001",
            "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
            "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
        ):
            self.assertIn(rule_id, active, rule_id)

    def test_router_uniquely_defines_evidence_levels(self) -> None:
        router = _text(".agents/rules/生成前必读索引.md")
        other = "\n".join(
            _text(path)
            for path in (
                ".agents/agent.md",
                ".agents/rules/算子配置规则.md",
            )
        )
        for level in range(6):
            marker = f"- E{level}："
            self.assertEqual(router.count(marker), 1, marker)
            self.assertNotIn(marker, other)


if __name__ == "__main__":
    unittest.main()
