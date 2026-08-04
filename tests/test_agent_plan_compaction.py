from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _sha256(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


class AgentPlanCompactionTests(unittest.TestCase):
    def test_active_files_are_bounded(self) -> None:
        # agent.md is the stable governance entry; it grew when package-owner
        # completion notification and time-to-root-cause routing became mandatory.
        self.assertLessEqual(len(_text(".agents/agent.md").splitlines()), 240)
        self.assertLessEqual(len(_text(".agents/plan.md").splitlines()), 180)

    def test_plan_contains_only_current_dispatch_state(self) -> None:
        plan = _text(".agents/plan.md")
        for required in (
            "正式 E4/E5 闭环：`1/78`",
            "r5_n71_gap_v33_buffer_ag_idx_pair_diag.zip",
            "r5_n4_hw_v35_rowlc4_bufag_diag.zip",
            "r5_qadd_n7_split_c_pairmatrix_v29.zip",
            "r5_n4_df23e4d_p4.zip",
            "B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED",
        ):
            self.assertIn(required, plan)
        for stale in (
            "r5_n71_gap_v32_col_ag_mrm_lane_rulebind.zip",
            "r5_n4_hw_v33_lc18_pe7_diag.zip",
            "r5_qadd_n7_split_c_ingress_v28.zip",
            "r5_conv_native_four_lane_df23e4d_perf_v1.zip",
            "r5_n4_hw_v20_buffer_mode_fix.zip",
            "r5_n4_hw_v21_bufkeep_fix.zip",
            "r5_qadd_n7_cfgpreload_v14.zip",
            "r5_qadd_n7_dbuf_v15.zip",
            "r5_qadd_n7_dbuf_rule_v16.zip",
            "r5_n71_gap_v13_buffer_to_ga_diag.zip",
            "r5_n71_gap_v14_accum_enable.zip",
            "r5_n71_gap_v15_feature_enable_rule.zip",
        ):
            self.assertNotIn(stale, plan)

    def test_active_plan_has_no_version_history_or_old_commands(self) -> None:
        plan = _text(".agents/plan.md")
        self.assertIsNone(
            re.search(
                r"onecmd_v\d+|probe_v\d+|repair_v\d+|"
                r"服务器唯一命令|已完成步骤|#### 0\.3",
                plan,
            )
        )

    def test_agent_routes_without_redefining_common_rules(self) -> None:
        agent = _text(".agents/agent.md")
        self.assertIn("生成前必读索引.md", agent)
        self.assertIn("文档唯一归属", agent)
        for level in range(6):
            self.assertNotIn(f"- E{level}：", agent)
        self.assertNotIn("typed request\n→", agent)

    def test_historical_snapshots_are_exact(self) -> None:
        expected = {
            ".agents/history/agent_pre_active_compaction_20260724.md":
                "27f2e3a567d39e01abe176289bcffb3bc28fd6a4c39ffb0dd17c79784154b966",
            ".agents/history/plan_pre_active_compaction_20260724.md":
                "d4bc08ec44017a1d438961391577fdb74584b6b203daa66978706b07d95d515b",
        }
        for relative, digest in expected.items():
            self.assertEqual(_sha256(relative), digest, relative)

    def test_history_indexes_the_migration(self) -> None:
        history = _text(".agents/history.md")
        self.assertIn("2026-07-24 活动 agent/plan 精简", history)
        self.assertIn("plan_pre_active_compaction_20260724.md", history)
        self.assertIn("2026-08-01 活动 plan 再精简", history)
        self.assertIn("plan_pre_active_20260801.md", history)

    def test_transition_stubs_do_not_duplicate_active_content(self) -> None:
        for relative, active in (
            (".agents/agent.compacted.md", ".agents/agent.md"),
            (".agents/plan.compacted.md", ".agents/plan.md"),
        ):
            stub = _text(relative)
            self.assertLessEqual(len(stub.splitlines()), 3)
            self.assertIn(active, stub)


if __name__ == "__main__":
    unittest.main()
