from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkspaceLifecycleRuleTests(unittest.TestCase):
    def test_root_agents_is_pointer_only(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(".agents/agent.md", text)
        self.assertNotIn("CDA-", text)
        self.assertLess(len(text), 600)

    def test_entry_and_skill_require_lifecycle_sequence(self) -> None:
        entry = (ROOT / ".agents/agent.md").read_text(encoding="utf-8")
        skill = (ROOT / ".codex/skills/resnet50-server-package-flow/SKILL.md").read_text(encoding="utf-8")
        for token in ("scan", "quarantine", "verify", "purge", "WORKSPACE_OBJECT_MANIFEST.json"):
            self.assertIn(token, entry)
        self.assertIn("writer quiescence", skill)
        self.assertIn("CLEANUP_PENDING", skill)

    def test_cleanup_is_not_added_to_final_zip_gate(self) -> None:
        dispatch = json.loads((ROOT / "contracts/workspace_lifecycle_dispatch_v1.json").read_text(encoding="utf-8"))
        registry = json.loads((ROOT / "contracts/server_package_build_gate_registry_v1.json").read_text(encoding="utf-8"))
        self.assertEqual(dispatch["final_zip_gate_change"], "NONE")
        self.assertFalse(any("workspace" in item["gate_id"] or "cleanup" in item["gate_id"] for item in registry["gates"]))

    def test_manifest_schema_accepts_compacted_record_storage(self) -> None:
        schema = json.loads((ROOT / "schemas/workspace_object_manifest_v1.schema.json").read_text(encoding="utf-8"))
        value = {
            "schema": "workspace-object-manifest-v1",
            "object_id": "family.task.output",
            "root": "work/family/task",
            "owner": {"role_id": "family.f", "owner_epoch": 1, "registry_epoch": 50, "task_pointer": "outputs/f/receipt.json"},
            "kind": "BUILD_STAGING",
            "lifecycle": "ACTIVE",
            "source": ["pending/f.zip"],
            "canonical_anchor": None,
            "protected_reasons": ["active patch base"],
            "cleanup_trigger": "POST_ADMISSION_STORAGE",
            "record_storage": {"logical_record_count": 12000, "representation": "JSONL", "per_record_files_allowed": False, "actual_consumer_requirement": None},
            "claim_boundary": "local object lifecycle only"
        }
        try:
            import jsonschema
        except ImportError:
            return
        jsonschema.validate(value, schema)

    def test_gitignore_concentrates_ephemeral_roots(self) -> None:
        lines = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
        self.assertIn("/.tmp/", lines)
        self.assertIn("/work/", lines)


if __name__ == "__main__":
    unittest.main()
