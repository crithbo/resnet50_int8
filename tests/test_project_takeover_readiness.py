from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_project_takeover_readiness import (
    REQUIRED_CONTROL_PATHS,
    STORAGE_INDEX,
    validate_takeover,
)


class ProjectTakeoverReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for relative in REQUIRED_CONTROL_PATHS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder\n", encoding="utf-8")
        (self.root / ".agents/plan.md").parent.mkdir(parents=True, exist_ok=True)
        self.package = "artifacts/operator_config_validation/r5-server-test-packages/pending/pkg-a.zip"
        package_path = self.root / self.package
        package_path.parent.mkdir(parents=True, exist_ok=True)
        package_path.write_bytes(b"PK fixture")
        record = self.root / ".agents/task_records/current.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text("current\n", encoding="utf-8")
        registry = {
            "schema": "session-owner-registry-v1",
            "registry_epoch": 3,
            "mainline_role_id": "mainline.control",
            "roles": [
                self.role("mainline.control", "MAINLINE", "11111111-1111-1111-1111-111111111111", False),
                self.role("family.a", "FAMILY_OWNER", "22222222-2222-2222-2222-222222222222", True),
            ],
            "claim_boundary": "fixture",
        }
        (self.root / "contracts/current_session_owner_registry_v1.json").write_text(json.dumps(registry), encoding="utf-8")
        build = {"mode": "ACTIVE_PATCH_FIRST_CHANGED_SURFACE", "release_admission_required": True}
        (self.root / "contracts/server_package_build_gate_registry_v1.json").write_text(json.dumps(build), encoding="utf-8")
        plan = "registry_epoch: 3\nmainline.control\n11111111-1111-1111-1111-111111111111\nfamily.a\npkg-a\n"
        (self.root / ".agents/plan.md").write_text(plan, encoding="utf-8")
        storage = self.root / STORAGE_INDEX
        storage.parent.mkdir(parents=True, exist_ok=True)
        storage.write_text(json.dumps({"pending_by_family": {"a": ["pkg-a"]}}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def role(self, role_id: str, kind: str, thread: str, pending: bool) -> dict:
        return {
            "role_id": role_id,
            "role_kind": kind,
            "scope": role_id,
            "thread_id": thread,
            "owner_epoch": 1,
            "status": "ACTIVE",
            "write_scope": [],
            "forbidden_scope": [],
            "current_task": {"status": "PACKAGE_READY_NOT_RUN" if pending else "ACTIVE", "objective": "continue", "next_action": "next", "pointer": {"path": ".agents/task_records/current.md"}},
            "latest_task_record": {"path": ".agents/task_records/current.md"},
            "in_flight": {"state": "PACKAGE_READY_NOT_RUN" if pending else "NONE", "server_root": None, "lease_id": None, "package": {"path": self.package} if pending else None, "return_zip": None},
        }

    def test_current_disk_positive(self) -> None:
        self.assertTrue(validate_takeover(self.root, self.root)["pass"])

    def test_missing_registry_fails(self) -> None:
        (self.root / "contracts/current_session_owner_registry_v1.json").unlink()
        report = validate_takeover(self.root, self.root)
        self.assertFalse(report["pass"])

    def test_stale_plan_fails(self) -> None:
        (self.root / ".agents/plan.md").write_text("registry_epoch: 2\nmainline.control\n", encoding="utf-8")
        report = validate_takeover(self.root, self.root)
        self.assertTrue(any("plan omits" in item for item in report["errors"]))

    def test_pending_mismatch_fails(self) -> None:
        storage = self.root / STORAGE_INDEX
        storage.write_text(json.dumps({"pending_by_family": {"a": ["other"]}}), encoding="utf-8")
        report = validate_takeover(self.root, self.root)
        self.assertTrue(any("pending mismatch" in item for item in report["errors"]))

    def test_shadow_build_registry_fails(self) -> None:
        path = self.root / "contracts/server_package_build_gate_registry_v1.json"
        path.write_text(json.dumps({"mode": "SHADOW_ONLY_NEXT_FRESH", "release_admission_required": False}), encoding="utf-8")
        report = validate_takeover(self.root, self.root)
        self.assertTrue(any("not in ACTIVE" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
