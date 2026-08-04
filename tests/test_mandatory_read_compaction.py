from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES = ROOT / ".agents" / "rules"


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


class MandatoryReadCompactionTests(unittest.TestCase):
    def test_router_owns_the_common_read_matrix(self) -> None:
        router = _text(".agents/rules/生成前必读索引.md")
        for required in (
            "算子配置规则.md",
            "服务器测试包生成规则.md",
            "NDP硬件字段语义.md",
            "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
            "NO_DYNAMIC_BASELINE",
            "FIRST_DYNAMIC_FAILURE",
        ):
            self.assertIn(required, router)

    def test_long_pre_compaction_documents_are_archived(self) -> None:
        for relative in (
            ".agents/archive/agent_pre_read_compaction_20260724.md",
            ".agents/archive/server_package_rules_pre_read_compaction_20260724.md",
            ".agents/archive/operator_config_rules_pre_read_compaction_20260724.md",
            ".agents/archive/NDP_copy01_README_HARDWARE_SIM_ENTRY_pre_read_compaction_20260724.md",
            ".agents/archive/GAP_int32_mac_bypass_rules_pre_read_compaction_20260724.md",
            ".agents/archive/GAP_repair_candidate_rules_pre_read_compaction_20260724.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_common_active_documents_contain_no_version_identity(self) -> None:
        common = "\n".join(
            _text(path)
            for path in (
                ".agents/agent.md",
                ".agents/rules/服务器测试包生成规则.md",
                ".agents/rules/算子配置规则.md",
                "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
            )
        )
        self.assertIsNone(re.search(r"onecmd_v\d+|repair_v\d+|probe_v\d+", common))
        self.assertNotIn("最新增量（优先于", common)

    def test_generic_special_rules_contain_no_candidate_identity(self) -> None:
        generic_special = "\n".join(
            _text(path)
            for path in (
                ".agents/rules/GAP_int32_mac_bypass_rules.md",
                ".agents/rules/GAP_repair_candidate_rules.md",
            )
        )
        self.assertIsNone(
            re.search(r"atomic_v\d+|onecmd_v\d+|repair_v\d+", generic_special)
        )

    def test_effective_hardware_counterexamples_remain_active(self) -> None:
        active = "\n".join(
            path.read_text(encoding="utf-8")
            for path in RULES.glob("*.md")
        )
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

    def test_repeated_headings_are_removed(self) -> None:
        for relative in (
            ".agents/rules/服务器测试包生成规则.md",
            ".agents/rules/GAP_int32_mac_bypass_rules.md",
        ):
            headings = [
                line.strip()
                for line in _text(relative).splitlines()
                if line.startswith("#")
            ]
            self.assertEqual(len(headings), len(set(headings)), relative)

    def test_router_uniquely_defines_evidence_levels(self) -> None:
        router = _text(".agents/rules/生成前必读索引.md")
        agent = _text(".agents/agent.md")
        config = _text(".agents/rules/算子配置规则.md")
        for level in range(6):
            marker = f"- E{level}："
            self.assertEqual(router.count(marker), 1, marker)
            self.assertNotIn(marker, agent)
            self.assertNotIn(marker, config)

    def test_common_files_are_bounded(self) -> None:
        limits = {
            ".agents/agent.md": 180,
            ".agents/rules/服务器测试包生成规则.md": 300,
            ".agents/rules/算子配置规则.md": 300,
            "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": 180,
        }
        for relative, limit in limits.items():
            line_count = len(_text(relative).splitlines())
            self.assertLessEqual(line_count, limit, relative)


if __name__ == "__main__":
    unittest.main()
