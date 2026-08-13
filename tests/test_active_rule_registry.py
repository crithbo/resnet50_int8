from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "audit_active_rule_registry.py"
REGISTRY = ROOT / "contracts" / "active_rule_registry_v1.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ActiveRuleRegistryTests(unittest.TestCase):
    def make_fixture(self) -> Path:
        root = Path(tempfile.mkdtemp(prefix="active-rule-registry-"))
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for relative in (
            registry["entrypoints"]["stable_entry"],
            registry["entrypoints"]["current_state"],
            registry["entrypoints"]["history_entry"],
        ):
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        for item in registry["exact_active_rules"]:
            source = ROOT / item["path"]
            target = root / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        history_root = root / registry["history"]["root"]
        history_root.mkdir(parents=True, exist_ok=True)
        for name in registry["history"]["archived_active_basenames"]:
            (history_root / name).write_text("historical fixture\n", encoding="utf-8")
        target_registry = root / "contracts" / "active_rule_registry_v1.json"
        target_registry.parent.mkdir(parents=True, exist_ok=True)
        target_registry.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def run_audit(self, root: Path) -> tuple[int, dict]:
        result = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "--repo-root",
                str(root),
                "--registry",
                "contracts/active_rule_registry_v1.json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return result.returncode, json.loads(result.stdout)

    def refresh_receipt(self, root: Path, relative: str) -> None:
        registry_path = root / "contracts" / "active_rule_registry_v1.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        target = root / relative
        for item in registry["exact_active_rules"]:
            if item["path"] == relative:
                item["bytes"] = target.stat().st_size
                item["sha256"] = digest(target)
        registry_path.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def test_current_repository_contract_passes(self) -> None:
        code, report = self.run_audit(self.make_fixture())
        self.assertEqual(code, 0, report)
        self.assertTrue(report["pass"])
        self.assertEqual(report["active_rule_count"], 14)
        self.assertEqual(report["duplicate_definition_count"], 0)

    def test_unregistered_active_rule_fails_closed(self) -> None:
        root = self.make_fixture()
        (root / ".agents/rules/old.md").write_text("# old\n", encoding="utf-8")
        code, report = self.run_audit(root)
        self.assertEqual(code, 1)
        self.assertTrue(any("exact-set mismatch" in item for item in report["errors"]))

    def test_receipt_drift_fails_closed(self) -> None:
        root = self.make_fixture()
        target = root / ".agents/rules/Flatten_View算子配置规则.md"
        target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        code, report = self.run_audit(root)
        self.assertEqual(code, 1)
        self.assertTrue(any("SHA mismatch" in item for item in report["errors"]))

    def test_duplicate_rule_definition_fails_closed(self) -> None:
        root = self.make_fixture()
        relative = ".agents/rules/QLinearAdd算子配置规则.md"
        target = root / relative
        target.write_text(
            target.read_text(encoding="utf-8")
            + "\n规则 ID：`CDA-DEQUANT-E2-001`\n",
            encoding="utf-8",
        )
        self.refresh_receipt(root, relative)
        code, report = self.run_audit(root)
        self.assertEqual(code, 1)
        self.assertTrue(any("owner is not unique" in item for item in report["errors"]))

    def test_archived_filename_reference_fails_closed(self) -> None:
        root = self.make_fixture()
        relative = ".agents/rules/Flatten_View算子配置规则.md"
        target = root / relative
        target.write_text(
            target.read_text(encoding="utf-8") + "\nGAP_probe_v7_validator_rules.md\n",
            encoding="utf-8",
        )
        self.refresh_receipt(root, relative)
        code, report = self.run_audit(root)
        self.assertEqual(code, 1)
        self.assertTrue(any("references archived filename" in item for item in report["errors"]))

    def test_version_result_in_family_rule_fails_closed(self) -> None:
        root = self.make_fixture()
        relative = ".agents/rules/Flatten_View算子配置规则.md"
        target = root / relative
        target.write_text(
            target.read_text(encoding="utf-8") + "\n当前状态：PASSED\n",
            encoding="utf-8",
        )
        self.refresh_receipt(root, relative)
        code, report = self.run_audit(root)
        self.assertEqual(code, 1)
        self.assertTrue(any("result leaked" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()

