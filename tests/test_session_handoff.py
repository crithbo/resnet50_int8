from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.session_handoff import (
    HandoffError,
    audit_campaign,
    build_acceptance,
    build_capsule,
    activate,
    mainline_thread,
    publish_activation,
    receipt,
    validate_registry,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = [
    ROOT / "schemas/session_owner_registry_v1.schema.json",
    ROOT / "schemas/session_handoff_capsule_v1.schema.json",
    ROOT / "schemas/session_handoff_acceptance_v1.schema.json",
    ROOT / "schemas/session_handoff_activation_v1.schema.json",
    ROOT / "schemas/session_handoff_publication_v1.schema.json",
]
OPTIMIZER = "019fd276-14c5-7800-94db-87ebfb9ce632"


class SessionHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        source_map = {
            ".agents/agent.md": ROOT / ".agents/agent.md",
            ".agents/plan.md": ROOT / ".agents/plan.md",
            ".agents/rules/生成前必读索引.md": ROOT / ".agents/rules/生成前必读索引.md",
            ".agents/rules/会话转接与所有权规则.md": ROOT / ".agents/rules/会话转接与所有权规则.md",
        }
        for relative, source in source_map.items():
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        task = self.root / ".agents/task_records/current.md"
        task.parent.mkdir(parents=True, exist_ok=True)
        task.write_text("current task evidence\n", encoding="utf-8")
        self.rule_paths = list(source_map)
        self.task_path = ".agents/task_records/current.md"
        self.registry_path = self.root / "contracts/current_session_owner_registry_v1.json"
        self.registry_path.parent.mkdir(parents=True)
        write_json(self.registry_path, self.registry())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def role(self, role_id: str, kind: str, thread_id: str, scope: str) -> dict:
        return {
            "role_id": role_id,
            "role_kind": kind,
            "scope": scope,
            "thread_id": thread_id,
            "owner_epoch": 1,
            "status": "ACTIVE",
            "write_scope": [f"artifacts/{role_id}/"],
            "forbidden_scope": [".agents/plan.md"],
            "current_task": {
                "status": "ACTIVE",
                "objective": f"continue {role_id}",
                "next_action": "consume the next exact receipt",
                "pointer": receipt(self.root, self.task_path),
            },
            "latest_task_record": receipt(self.root, self.task_path),
            "in_flight": {
                "state": "NONE",
                "server_root": None,
                "lease_id": None,
                "package": None,
                "return_zip": None,
            },
        }

    def registry(self) -> dict:
        return {
            "schema": "session-owner-registry-v1",
            "registry_epoch": 1,
            "mainline_role_id": "mainline",
            "roles": [
                self.role(
                    "mainline",
                    "MAINLINE",
                    "11111111-1111-1111-1111-111111111111",
                    "project control plane",
                ),
                self.role(
                    "conv_owner",
                    "FAMILY_OWNER",
                    "22222222-2222-2222-2222-222222222222",
                    "Conv family",
                ),
                self.role(
                    "whole_network_optimizer",
                    "SPECIALIST_OWNER",
                    OPTIMIZER,
                    "whole-network convergence rules",
                ),
            ],
            "active_rule_receipts": [receipt(self.root, path) for path in self.rule_paths],
            "claim_boundary": "synthetic session ownership fixture only",
        }

    def request(self, role_id: str, new_thread_id: str) -> dict:
        return {
            "schema": "session-handoff-request-v1",
            "role_id": role_id,
            "new_thread_id": new_thread_id,
            "reason": "planned context refresh",
            "required_read_paths": self.rule_paths,
            "active_artifact_paths": [self.task_path],
            "pending_messages": ["no unconsumed user decision"],
            "first_action": "re-read current registry before any write",
        }

    def materialize_handoff(
        self,
        registry_path: Path,
        role_id: str,
        new_thread_id: str,
        order: int,
        stem: str,
    ) -> tuple[Path, Path, Path, Path]:
        request_path = self.root / f"{stem}_request.json"
        capsule_path = self.root / f"{stem}_capsule.json"
        acceptance_path = self.root / f"{stem}_acceptance.json"
        successor_path = self.root / f"{stem}_registry.json"
        activation_path = self.root / f"{stem}_activation.json"
        write_json(request_path, self.request(role_id, new_thread_id))
        write_json(
            capsule_path,
            build_capsule(registry_path, request_path, self.root),
        )
        write_json(
            acceptance_path,
            build_acceptance(capsule_path, registry_path, new_thread_id, self.root),
        )
        _, activation_receipt = activate(
            registry_path,
            capsule_path,
            acceptance_path,
            successor_path,
            order,
            self.root,
        )
        write_json(activation_path, activation_receipt)
        return capsule_path, acceptance_path, successor_path, activation_path

    def test_registry_schema_and_unique_owner_positive(self) -> None:
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self.assertEqual(validate_registry(registry, self.root), [])
        if jsonschema is not None:
            jsonschema.validate(
                registry, json.loads(SCHEMAS[0].read_text(encoding="utf-8"))
            )

    def test_duplicate_active_thread_fails_closed(self) -> None:
        bad = self.registry()
        bad["roles"][1]["thread_id"] = bad["roles"][0]["thread_id"]
        self.assertIn("one thread owns multiple ACTIVE roles", validate_registry(bad, self.root))

    def test_server_running_requires_exact_root_lease_and_package(self) -> None:
        bad = self.registry()
        bad["roles"][1]["in_flight"]["state"] = "SERVER_RUNNING"
        errors = validate_registry(bad, self.root)
        self.assertTrue(any("package receipt is absent" in item for item in errors))
        self.assertTrue(any("root/lease is absent" in item for item in errors))

    def test_new_thread_must_be_fresh(self) -> None:
        request_path = self.root / "same_request.json"
        write_json(
            request_path,
            self.request("mainline", "11111111-1111-1111-1111-111111111111"),
        )
        with self.assertRaises(HandoffError):
            build_capsule(self.registry_path, request_path, self.root)

    def test_receipt_drift_invalidates_acceptance(self) -> None:
        request_path = self.root / "drift_request.json"
        capsule_path = self.root / "drift_capsule.json"
        write_json(
            request_path,
            self.request("mainline", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        )
        write_json(
            capsule_path,
            build_capsule(self.registry_path, request_path, self.root),
        )
        (self.root / self.task_path).write_text("drifted task\n", encoding="utf-8")
        with self.assertRaises(HandoffError):
            build_acceptance(
                capsule_path,
                self.registry_path,
                "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                self.root,
            )

    def test_mainline_first_full_campaign_and_dynamic_route(self) -> None:
        _, _, registry1, activation1 = self.materialize_handoff(
            self.registry_path,
            "mainline",
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            1,
            "mainline",
        )
        self.assertEqual(
            mainline_thread(json.loads(registry1.read_text(encoding="utf-8"))),
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )
        _, _, registry2, activation2 = self.materialize_handoff(
            registry1,
            "conv_owner",
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            2,
            "conv",
        )
        before = json.loads(self.registry_path.read_text(encoding="utf-8"))
        after = json.loads(registry2.read_text(encoding="utf-8"))
        activations = [
            json.loads(activation1.read_text(encoding="utf-8")),
            json.loads(activation2.read_text(encoding="utf-8")),
        ]
        self.assertEqual(audit_campaign(before, after, activations, {OPTIMIZER}), [])
        optimizer_before = next(
            role for role in before["roles"] if role["thread_id"] == OPTIMIZER
        )
        optimizer_after = next(
            role for role in after["roles"] if role["thread_id"] == OPTIMIZER
        )
        self.assertEqual(optimizer_before, optimizer_after)
        self.assertEqual(after["registry_epoch"], 3)

    def test_atomic_publish_and_stale_pointer_fail_closed(self) -> None:
        _, _, successor, activation = self.materialize_handoff(
            self.registry_path,
            "mainline",
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            1,
            "publish_mainline",
        )
        publication = publish_activation(
            self.registry_path,
            successor,
            activation,
            self.root,
        )
        self.assertEqual(publication["status"], "REGISTRY_ACTIVATED")
        self.assertEqual(
            mainline_thread(json.loads(self.registry_path.read_text(encoding="utf-8"))),
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        )
        with self.assertRaises(HandoffError):
            publish_activation(self.registry_path, successor, activation, self.root)

    def test_campaign_rejects_family_before_mainline(self) -> None:
        _, _, registry1, family_activation = self.materialize_handoff(
            self.registry_path,
            "conv_owner",
            "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            1,
            "bad_family_first",
        )
        before = json.loads(self.registry_path.read_text(encoding="utf-8"))
        after = json.loads(registry1.read_text(encoding="utf-8"))
        activation = json.loads(family_activation.read_text(encoding="utf-8"))
        errors = audit_campaign(before, after, [activation], {OPTIMIZER})
        self.assertTrue(any("changed role set mismatch" in item for item in errors))
        self.assertTrue(any("mainline must be activated first" in item for item in errors))

    def test_schema_files_parse(self) -> None:
        for path in SCHEMAS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(schema["$id"].endswith("_v1.schema.json"))


if __name__ == "__main__":
    unittest.main()

