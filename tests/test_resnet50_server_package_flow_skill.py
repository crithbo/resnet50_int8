from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".codex/skills/resnet50-server-package-flow/SKILL.md"
AGENT = ROOT / ".agents/agent.md"


class Resnet50ServerPackageFlowSkillTests(unittest.TestCase):
    def test_skill_is_thin_and_has_formal_entry(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 120)
        self.assertIn("server_package_pipeline.py prepare", text)
        self.assertIn("server_package_pipeline.py admit", text)
        self.assertIn("PACKAGE_READY_NOT_RUN", text)
        self.assertIn("validate_project_takeover_readiness.py", text)

    def test_registered_family_is_not_replaced_by_temporary_subagent(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        agent = AGENT.read_text(encoding="utf-8")
        self.assertIn("Never spawn a subagent or temporary child task", skill)
        self.assertIn("临时子代理替代", agent)

    def test_future_default_is_bounded_tb_vcd(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("future new dynamic successor", text)
        self.assertIn("TB causal-cone VCD", text)
        self.assertIn("Never change the mode of a current ready package", text)

    def test_skill_does_not_authorize_external_actions(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("Do not upload, lease, or run a server unless the user explicitly authorizes it", text)


if __name__ == "__main__":
    unittest.main()
