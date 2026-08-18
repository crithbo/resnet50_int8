from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.validate_server_release_consistency import validate_contract


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/server_release_consistency_v1.schema.json"
HISTORICAL = (
    ROOT
    / "fixtures/server_release_consistency_v1/recent_independent_audit_failures.json"
)
DISPATCH = ROOT / "contracts/server_release_consistency_dispatch_v1.json"
BUILD_GATES = ROOT / "contracts/server_package_build_gate_registry_v1.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


class ServerReleaseConsistencyTests(unittest.TestCase):
    package_id = "synthetic_release_consistency_pkg"
    root_member = "synthetic_release_consistency_pkg"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.zip_path = self.workspace / "final" / f"{self.package_id}.zip"
        self.runner = (
            "#!/usr/bin/env bash\n"
            "phase_FINALIZATION_GUARD_COMPLETE=1\n"
            "phase_RETURN_PUBLISH=1\n"
            "phase_DURABLE_RETURN_RECEIPT=1\n"
            "phase_POST_DURABLE_CLEANUP_RECEIPT=1\n"
        ).encode("utf-8")
        self.producer = (
            "# package producer\n"
            "write evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json\n"
            "write evidence/core.json\n"
        ).encode("utf-8")
        self.progress_source = (
            "always @(posedge owner_clk) begin\n"
            "  if (target_valid && target_ready) progress_count <= progress_count + 1;\n"
            "end\n"
        ).encode("utf-8")
        span_start = self.progress_source.index(b"if (")
        span_end = self.progress_source.index(b"\n", span_start)
        span = self.progress_source[span_start:span_end]
        self.members: dict[str, bytes] = {
            "TEST_PACKAGE_MANIFEST.json": json_bytes({
                "test_id": self.package_id,
                "status": "PACKAGE_READY_NOT_RUN",
                "final_zip_rule_self_audit": {
                    "status": "FINAL_EXACT_ZIP_AND_FIRST_FRESH_AUDIT_PASS",
                    "pass": True,
                },
            }),
            "diagnostics/runtime_budget_admission.json": json_bytes({
                "selected_wall_ceiling_seconds": 15000,
                "absolute_maximum_wall_seconds": 86400,
            }),
            "contracts/server_tb_vcd_bounded_causal_cone_contract.json": json_bytes({
                "budget": {
                    "wall_ceiling_seconds": 15000,
                    "absolute_maximum_wall_seconds": 86400,
                }
            }),
            "contracts/server_post_sim_return_request.json": json_bytes({
                "core_entries": [
                    {
                        "source_root": "attempt",
                        "source": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
                        "archive": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
                        "required": True,
                    },
                    {
                        "source_root": "attempt",
                        "source": "evidence/core.json",
                        "archive": "evidence/core.json",
                        "required": True,
                    },
                ]
            }),
            "RETURN_ALLOWLIST.json": json_bytes({
                "required_members": [
                    "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
                    "evidence/core.json",
                ]
            }),
            "package_tools/producer.py": self.producer,
            "PREPARE_AND_RUN.sh": self.runner,
            "tb_probe/progress.svh": self.progress_source,
        }
        self.contract = {
            "schema": "server-release-consistency-v1",
            "package": {
                "package_id": self.package_id,
                "final_zip": {
                    "path": f"final/{self.package_id}.zip",
                    "bytes": 1,
                    "sha256": "0" * 64,
                },
                "zip_root_member": self.root_member,
            },
            "manifest": {
                "member": "TEST_PACKAGE_MANIFEST.json",
                "top_status_pointer": "/status",
                "top_ready_status": "PACKAGE_READY_NOT_RUN",
                "release_critical_statuses": [
                    {
                        "pointer": "/final_zip_rule_self_audit/status",
                        "expected_terminal_status": "FINAL_EXACT_ZIP_AND_FIRST_FRESH_AUDIT_PASS",
                    }
                ],
            },
            "cross_member_identities": [
                {
                    "identity_id": "selected_wall_seconds",
                    "endpoints": [
                        {
                            "member": "diagnostics/runtime_budget_admission.json",
                            "pointer": "/selected_wall_ceiling_seconds",
                        },
                        {
                            "member": "contracts/server_tb_vcd_bounded_causal_cone_contract.json",
                            "pointer": "/budget/wall_ceiling_seconds",
                        },
                    ],
                    "expected_value": 15000,
                },
                {
                    "identity_id": "absolute_maximum_wall_seconds",
                    "endpoints": [
                        {
                            "member": "diagnostics/runtime_budget_admission.json",
                            "pointer": "/absolute_maximum_wall_seconds",
                        },
                        {
                            "member": "contracts/server_tb_vcd_bounded_causal_cone_contract.json",
                            "pointer": "/budget/absolute_maximum_wall_seconds",
                        },
                    ],
                    "expected_value": 86400,
                },
            ],
            "return_phase": {
                "request_member": "contracts/server_post_sim_return_request.json",
                "allowlist_member": "RETURN_ALLOWLIST.json",
                "allowlist_required_pointer": "/required_members",
                "prepublication_producers": [
                    {
                        "source_root": "attempt",
                        "source": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
                        "archive": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
                        "producer_member": "package_tools/producer.py",
                        "producer_sha256": sha(self.producer),
                        "producer_output_literal": "write evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
                    },
                    {
                        "source_root": "attempt",
                        "source": "evidence/core.json",
                        "archive": "evidence/core.json",
                        "producer_member": "package_tools/producer.py",
                        "producer_sha256": sha(self.producer),
                        "producer_output_literal": "write evidence/core.json",
                    },
                ],
                "finalization_guard_archive": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
                "postpublication_receipts": [
                    {
                        "path": "evidence/DURABLE_RETURN_RECEIPT.json",
                        "location": "EXTERNAL_IMMUTABLE_SIDECAR",
                    },
                    {
                        "path": "evidence/POST_DURABLE_CLEANUP_RECEIPT.json",
                        "location": "EXTERNAL_IMMUTABLE_SIDECAR",
                    },
                ],
                "runner_member": "PREPARE_AND_RUN.sh",
                "runner_sha256": sha(self.runner),
                "ordered_runner_markers": [
                    {"phase": "FINALIZATION_GUARD_COMPLETE", "literal": "phase_FINALIZATION_GUARD_COMPLETE=1"},
                    {"phase": "RETURN_PUBLISH", "literal": "phase_RETURN_PUBLISH=1"},
                    {"phase": "DURABLE_RETURN_RECEIPT", "literal": "phase_DURABLE_RETURN_RECEIPT=1"},
                    {"phase": "POST_DURABLE_CLEANUP_RECEIPT", "literal": "phase_POST_DURABLE_CLEANUP_RECEIPT=1"},
                ],
            },
            "progress_qualification": {
                "source_member": "tb_probe/progress.svh",
                "source_sha256": sha(self.progress_source),
                "events": [
                    {
                        "event_id": "target_accept",
                        "counter_symbol": "progress_count",
                        "event_kind": "QUALIFIED_HANDSHAKE",
                        "source_span_start_byte": span_start,
                        "source_span_end_byte": span_end,
                        "source_span_sha256": sha(span),
                        "source_signal_tokens": ["target_valid"],
                        "qualifier_signal_tokens": ["target_ready"],
                        "state_memory_tokens": [],
                    }
                ],
                "held_level_replay_required": True,
                "held_level_replays": [
                    {
                        "event_id": "target_accept",
                        "source_samples": [0, 1, 1, 1, 0],
                        "qualifier_samples": [0, 1, 0, 0, 0],
                        "expected_counter_deltas": [0, 1, 0, 0, 0],
                    }
                ],
            },
            "claim_boundary": "Synthetic local final-ZIP consistency control only.",
        }
        self.refresh_zip()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def refresh_zip(self) -> None:
        self.zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(self.members.items()):
                archive.writestr(f"{self.root_member}/{name}", data)
        self.contract["package"]["final_zip"].update({
            "bytes": self.zip_path.stat().st_size,
            "sha256": hashlib.sha256(self.zip_path.read_bytes()).hexdigest(),
        })

    def report(self, contract: dict | None = None) -> dict:
        return validate_contract(contract or self.contract, self.workspace)

    def mutate_json(self, member: str, callback) -> None:
        value = json.loads(self.members[member])
        callback(value)
        self.members[member] = json_bytes(value)
        self.refresh_zip()

    def test_positive_cross_member_temporal_and_progress_closure(self) -> None:
        report = self.report()
        self.assertTrue(report["pass"], report)
        self.assertTrue(all(report["checks"].values()), report)
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(
            self.contract,
            json.loads(SCHEMA.read_text(encoding="utf-8")),
        )

    def test_nested_final_audit_pending_fails_closed(self) -> None:
        self.mutate_json(
            "TEST_PACKAGE_MANIFEST.json",
            lambda value: value["final_zip_rule_self_audit"].update({
                "status": "PENDING_EXACT_ZIP_AND_FIRST_FRESH_AUDIT"
            }),
        )
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("release-critical manifest status", "\n".join(report["errors"]))

    def test_selected_and_absolute_wall_conflation_fails_closed(self) -> None:
        self.mutate_json(
            "diagnostics/runtime_budget_admission.json",
            lambda value: value.update({"absolute_maximum_wall_seconds": 15000}),
        )
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("absolute_maximum_wall_seconds", "\n".join(report["errors"]))

    def test_required_member_without_exact_producer_fails_closed(self) -> None:
        item = copy.deepcopy(self.contract)
        item["return_phase"]["prepublication_producers"][0]["source"] = (
            "evidence/OPERATIONAL_STOP_RECEIPT.json"
        )
        report = self.report(item)
        self.assertFalse(report["pass"])
        self.assertIn("lacks exactly one producer closure", "\n".join(report["errors"]))

    def test_postpublication_receipt_cannot_be_required_inside_first_return(self) -> None:
        def mutate(request: dict) -> None:
            request["core_entries"].append({
                "source_root": "attempt",
                "source": "evidence/DURABLE_RETURN_RECEIPT.json",
                "archive": "evidence/DURABLE_RETURN_RECEIPT.json",
                "required": True,
            })

        self.mutate_json("contracts/server_post_sim_return_request.json", mutate)
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("postpublication receipt is impossible", "\n".join(report["errors"]))

    def test_return_publication_before_guard_completion_fails_closed(self) -> None:
        self.runner = (
            "#!/usr/bin/env bash\n"
            "phase_RETURN_PUBLISH=1\n"
            "phase_FINALIZATION_GUARD_COMPLETE=1\n"
            "phase_DURABLE_RETURN_RECEIPT=1\n"
            "phase_POST_DURABLE_CLEANUP_RECEIPT=1\n"
        ).encode("utf-8")
        self.members["PREPARE_AND_RUN.sh"] = self.runner
        self.contract["return_phase"]["runner_sha256"] = sha(self.runner)
        self.refresh_zip()
        report = self.report()
        self.assertFalse(report["pass"])
        self.assertIn("guard->publish->durable->cleanup", "\n".join(report["errors"]))

    def test_raw_held_level_cannot_count_as_progress(self) -> None:
        item = copy.deepcopy(self.contract)
        event = item["progress_qualification"]["events"][0]
        event["event_kind"] = "RAW_LEVEL_PER_OWNER_CLOCK"
        event["qualifier_signal_tokens"] = []
        report = self.report(item)
        self.assertFalse(report["pass"])
        self.assertIn("raw/unknown level event", "\n".join(report["errors"]))

    def test_handshake_without_ready_qualifier_fails_closed(self) -> None:
        item = copy.deepcopy(self.contract)
        item["progress_qualification"]["events"][0]["qualifier_signal_tokens"] = []
        report = self.report(item)
        self.assertFalse(report["pass"])
        self.assertIn("lacks ready/accept qualifier", "\n".join(report["errors"]))

    def test_held_level_replay_that_counts_each_cycle_fails_closed(self) -> None:
        item = copy.deepcopy(self.contract)
        replay = item["progress_qualification"]["held_level_replays"][0]
        replay["expected_counter_deltas"] = [0, 1, 1, 1, 0]
        report = self.report(item)
        self.assertFalse(report["pass"])
        self.assertIn("counter deltas differ", "\n".join(report["errors"]))

    def test_historical_recent_failures_are_registered(self) -> None:
        value = json.loads(HISTORICAL.read_text(encoding="utf-8"))
        by_id = {item["package_id"]: item for item in value["cases"]}
        self.assertIn("FINALIZATION_GUARD_RECEIPT_PUBLISHED_AFTER_RETURN", by_id["r5_n4_hw_v103b_lcdup_obsfix"]["defects"])
        self.assertIn("HELD_LEVEL_FALSE_PROGRESS", by_id["r5_qadd_n7_tr_v78_w15kpfs"]["defects"])
        self.assertTrue(all(item["required_result"] == "FAIL_CLOSED" for item in value["cases"]))

    def test_local_unpublished_candidate_patch_policy_is_strict_and_non_retroactive(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        policy = dispatch["local_unpublished_candidate_patch_policy"]
        eligibility = policy["same_package_identity_allowed_only_when"]
        self.assertTrue(eligibility["local_only"])
        self.assertFalse(eligibility["ever_managed_or_published"])
        self.assertFalse(eligibility["ever_server_run"])
        self.assertFalse(eligibility["ever_authoritative_release_handoff"])
        self.assertFalse(eligibility["formal_return_bound"])
        exclusions = "\n".join(policy["immutable_exclusions"])
        for token in ("managed", "server-run", "authoritative release", "formal return", "tested"):
            self.assertIn(token, exclusions)
        required = "\n".join(policy["required_prepatch_evidence"])
        self.assertIn("prepatch tree bytes and SHA-256", required)
        self.assertIn("exact added/removed/modified/unchanged", required)
        self.assertIn("functional RTL", required)

    def test_local_patch_never_reuses_final_release_driver_receipt(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        semantics = dispatch["local_unpublished_candidate_patch_policy"]["receipt_semantics"]
        self.assertIn("all prepatch final-ZIP receipts", semantics["invalidate"])
        self.assertIn("receipt_reuse_allowed is false", semantics["rerun_when"])
        registry = json.loads(BUILD_GATES.read_text(encoding="utf-8"))
        gates = {item["gate_id"]: item for item in registry["gates"]}
        gate = gates["release_cross_member_temporal_consistency_final_zip"]
        self.assertFalse(gate["receipt_reuse_allowed"])
        self.assertEqual(gate["execution_group"], "final_zip_release_driver")


if __name__ == "__main__":
    unittest.main()
