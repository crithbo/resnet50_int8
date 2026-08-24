from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.validate_server_family_dispatch_mode_binding import (
    validate_binding,
    validate_final_zip,
    validate_package_tree,
)


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FamilyDispatchModeBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.registry_path = self.repo / "contracts/current_session_owner_registry_v1.json"
        self.dispatch_path = self.repo / "contracts/server_diagnostic_mode_selector_dispatch_v1.json"
        self.authority_path = self.repo / "dispatch/current_task.json"
        self.authority_source_path = self.repo / "dispatch/current_task.md"
        self.registry = {
            "schema": "session-owner-registry-v1", "registry_epoch": 9,
            "roles": [
                {"role_id": "mainline.control", "status": "ACTIVE", "thread_id": "main-thread", "owner_epoch": 3},
                {"role_id": "family.conv.serialized", "status": "ACTIVE", "thread_id": "serialized-thread", "owner_epoch": 4},
            ],
        }
        write_json(self.registry_path, self.registry)
        write_json(self.dispatch_path, {"schema": "selector-dispatch", "default_mode": "TB_VCD_BOUNDED_CAUSAL_CONE"})
        self.authority_source_path.parent.mkdir(parents=True, exist_ok=True)
        self.authority_source_path.write_text("next fresh mode: TB_VCD_BOUNDED_CAUSAL_CONE\n", encoding="utf-8")
        write_json(self.authority_path, {
            "schema": "server-family-diagnostic-mode-authority-v1",
            "effective_scope": "NEXT_FRESH_AFTER_ACTIVATION",
            "package_id": "p-vcd-next",
            "family_role_id": "family.conv.serialized",
            "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
            "source": {
                "kind": "MAINLINE_TASK_RECORD", "path": "dispatch/current_task.md",
                "sha256": digest(self.authority_source_path),
            },
        })
        self.binding = {
            "schema": "server-family-dispatch-mode-binding-v1",
            "activation_epoch": "family-dispatch-mode-binding-v1",
            "effective_scope": "NEXT_FRESH_AFTER_ACTIVATION",
            "package_id": "p-vcd-next",
            "family_role_id": "family.conv.serialized",
            "owner_binding": {
                "owner_thread_id": "serialized-thread", "owner_epoch": 4, "registry_epoch": 9,
                "registry_path": "contracts/current_session_owner_registry_v1.json",
                "registry_sha256": digest(self.registry_path),
                "dispatch_mechanism": "PERSISTENT_REGISTERED_THREAD",
                "temporary_subagent_role_substitution": False,
            },
            "issued_by": {"role_id": "mainline.control", "thread_id": "main-thread"},
            "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
            "mode_authority": {
                "kind": "MAINLINE_TASK_RECORD", "path": "dispatch/current_task.json",
                "sha256": digest(self.authority_path),
                "source_path": "dispatch/current_task.md",
                "source_sha256": digest(self.authority_source_path),
                "selector_dispatch_path": "contracts/server_diagnostic_mode_selector_dispatch_v1.json",
                "selector_dispatch_sha256": digest(self.dispatch_path),
            },
            "package_contract": {
                "binding_member": "contracts/server_family_dispatch_mode_binding.json",
                "selector_member": "contracts/server_diagnostic_mode_selector.json",
                "manifest_member": "TEST_PACKAGE_MANIFEST.json",
            },
            "current_package_disposition": "NOT_RETROACTIVE_NO_REBUILD",
            "server_action_authorized": False,
            "claim_boundary": "test",
        }
        self.binding_path = self.repo / "dispatch/binding.json"
        write_json(self.binding_path, self.binding)
        self.package = self.repo / "package"
        self._write_package()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _selector(self, mode: str | None = None) -> dict:
        selected = mode or self.binding["diagnostic_mode"]
        observer = selected == "OBSERVER_ONLY_WIDE_CAUSAL"
        return {
            "schema": "server-diagnostic-mode-selector-v1",
            "package_id": self.binding["package_id"], "family": "conv.serialized", "selected_mode": selected,
            "bulk_evidence": {
                "observer_jsonl": observer, "tb_standard_vcd": not observer,
                "vpd": False, "fsdb": False, "ucli_direct_vcd": False, "vendor_signal_query": False,
            },
            "actual_dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            "lightweight_progress_supervisor": {
                "enabled": True, "bulk_signal_events": False,
                "sim_time_heartbeat": True, "process_tree_reap": True,
            },
            "package_members": ["TEST_PACKAGE_MANIFEST.json"],
            "return_members": ["evidence/vcd/wave.vcd"] if not observer else ["observer/chunks/chunk-0.jsonl"],
            "observer_contract_sha256": "1" * 64 if observer else None,
            "vcd_contract_sha256": None if observer else "2" * 64,
            "claim_boundary": "test",
        }

    def _write_package(self, mode: str | None = None) -> None:
        write_json(self.package / "contracts/server_family_dispatch_mode_binding.json", self.binding)
        write_json(self.package / "contracts/server_diagnostic_mode_selector.json", self._selector(mode))
        write_json(self.package / "TEST_PACKAGE_MANIFEST.json", {
            "package_id": self.binding["package_id"],
            "diagnostic_mode": mode or self.binding["diagnostic_mode"],
        })

    def _zip(self) -> Path:
        target = self.repo / "package.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.package.rglob("*")):
                if path.is_file():
                    archive.write(path, f"root/{path.relative_to(self.package).as_posix()}")
        return target

    def test_positive_persistent_vcd_tree_and_zip(self) -> None:
        self.assertTrue(validate_binding(self.binding, self.repo)["pass"])
        self.assertTrue(validate_package_tree(self.binding_path, self.repo, self.package)["pass"])
        self.assertTrue(validate_final_zip(self.binding_path, self.repo, self._zip())["pass"])

    def test_observer_default_cannot_override_vcd_dispatch(self) -> None:
        self._write_package("OBSERVER_ONLY_WIDE_CAUSAL")
        report = validate_package_tree(self.binding_path, self.repo, self.package)
        self.assertFalse(report["pass"])
        self.assertIn("differs from dispatched mode", "\n".join(report["errors"]))

    def test_missing_selector_or_binding_fails_closed(self) -> None:
        (self.package / "contracts/server_diagnostic_mode_selector.json").unlink()
        self.assertIn("selector member is absent", "\n".join(validate_package_tree(self.binding_path, self.repo, self.package)["errors"]))
        self._write_package()
        (self.package / "contracts/server_family_dispatch_mode_binding.json").unlink()
        self.assertIn("binding member is absent", "\n".join(validate_package_tree(self.binding_path, self.repo, self.package)["errors"]))

    def test_subagent_role_substitution_fails_closed(self) -> None:
        item = copy.deepcopy(self.binding)
        item["owner_binding"]["dispatch_mechanism"] = "SUBAGENT"
        item["owner_binding"]["temporary_subagent_role_substitution"] = True
        report = validate_binding(item, self.repo)
        self.assertFalse(report["pass"])
        self.assertIn("PERSISTENT_REGISTERED_THREAD", "\n".join(report["errors"]))

    def test_owner_thread_and_issuer_mismatch_fail(self) -> None:
        item = copy.deepcopy(self.binding)
        item["owner_binding"]["owner_thread_id"] = "temporary-child"
        item["issued_by"]["thread_id"] = "old-mainline"
        errors = "\n".join(validate_binding(item, self.repo)["errors"])
        self.assertIn("family owner thread differs", errors)
        self.assertIn("issuing mainline thread differs", errors)

    def test_registry_and_authority_drift_fail(self) -> None:
        self.registry["registry_epoch"] = 10
        write_json(self.registry_path, self.registry)
        errors = "\n".join(validate_binding(self.binding, self.repo)["errors"])
        self.assertIn("owner registry SHA256 differs", errors)
        self.assertIn("owner registry epoch differs", errors)
        write_json(self.registry_path, {**self.registry, "registry_epoch": 9})
        self.binding["owner_binding"]["registry_sha256"] = digest(self.registry_path)
        write_json(self.authority_path, {"diagnostic_mode": "OBSERVER_ONLY_WIDE_CAUSAL"})
        self.assertIn("mode authority SHA256 differs", "\n".join(validate_binding(self.binding, self.repo)["errors"]))

    def test_authority_receipt_cannot_claim_a_different_mode(self) -> None:
        authority = json.loads(self.authority_path.read_text(encoding="utf-8"))
        authority["diagnostic_mode"] = "OBSERVER_ONLY_WIDE_CAUSAL"
        write_json(self.authority_path, authority)
        item = copy.deepcopy(self.binding)
        item["mode_authority"]["sha256"] = digest(self.authority_path)
        errors = "\n".join(validate_binding(item, self.repo)["errors"])
        self.assertIn("diagnostic_mode differs", errors)

    def test_packaged_binding_drift_and_renamed_member_fail(self) -> None:
        item = copy.deepcopy(self.binding)
        item["claim_boundary"] = "drift"
        write_json(self.package / "contracts/server_family_dispatch_mode_binding.json", item)
        self.assertIn("not byte-equal", "\n".join(validate_package_tree(self.binding_path, self.repo, self.package)["errors"]))
        self._write_package()
        renamed = self.package / "contracts/renamed_dispatch.json"
        (self.package / "contracts/server_family_dispatch_mode_binding.json").replace(renamed)
        self.assertIn("binding member is absent", "\n".join(validate_package_tree(self.binding_path, self.repo, self.package)["errors"]))

    def test_current_package_boundary_is_nonretroactive(self) -> None:
        item = copy.deepcopy(self.binding)
        item["current_package_disposition"] = "REBUILD_CURRENT"
        report = validate_binding(item, self.repo)
        self.assertFalse(report["pass"])
        self.assertIn("NOT_RETROACTIVE_NO_REBUILD", "\n".join(report["errors"]))

    def test_skill_requires_persistent_owner_and_bound_mode(self) -> None:
        text = (ROOT / ".codex/skills/resnet50-server-package-flow/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Never spawn a subagent", text)
        self.assertIn("PERSISTENT_REGISTERED_THREAD", text)
        self.assertIn("default can never override a bound campaign/package decision", text)


if __name__ == "__main__":
    unittest.main()
