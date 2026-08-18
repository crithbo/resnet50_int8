from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from argparse import Namespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "tools" / "server_observer_operational_attempt_boundary.py"
VALIDATOR_PATH = ROOT / "tools" / "validate_server_observer_operational_attempt_boundary.py"
FIXTURE = ROOT / "fixtures" / "server_observer_operational_attempt_boundary_v1" / "positive_contract.json"
SCHEMA = ROOT / "schemas" / "server_observer_operational_attempt_boundary_v1.schema.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNTIME = load_module("observer_operational_runtime_test", RUNTIME_PATH)
VALIDATOR = load_module("observer_operational_validator_test", VALIDATOR_PATH)


class ObserverOperationalAttemptBoundaryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_contract_fails(self, contract: dict, fragment: str) -> None:
        report = RUNTIME.validate_contract(contract)
        self.assertFalse(report["pass"], report)
        self.assertTrue(any(fragment in error for error in report["errors"]), report)

    def test_positive_contract_and_schema(self) -> None:
        report = RUNTIME.validate_contract(self.contract)
        self.assertTrue(report["pass"], report)
        self.assertEqual(report["component_sum_bytes"], 5100)
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(self.contract, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_unknown_amplification_and_missing_phase_fail(self) -> None:
        item = copy.deepcopy(self.contract)
        item["pre_run_peak_projection"]["unknown_or_unbounded_amplification"] = True
        self.assert_contract_fails(item, "unbounded amplification")
        item = copy.deepcopy(self.contract)
        item["phase_watches"].pop()
        self.assert_contract_fails(item, "compile, simulation and finalization")

    def test_evidence_cap_or_truncation_stays_forbidden(self) -> None:
        for key, value in (("byte_cap", 100000000), ("event_cap", 10), ("truncation", True), ("sampling", True)):
            item = copy.deepcopy(self.contract)
            item["operational_stop"][key] = value
            self.assert_contract_fails(item, f"operational_stop.{key}")

    def test_projection_arithmetic_and_shared_constant_fail(self) -> None:
        item = copy.deepcopy(self.contract)
        item["pre_run_peak_projection"]["peak_transient_bytes"] += 1
        self.assert_contract_fails(item, "exact component sum")
        item = copy.deepcopy(self.contract)
        item["pre_run_peak_projection"]["minimum_free_reserve_bytes"] = 0
        item["pre_run_peak_projection"]["start_required_free_bytes"] -= 1000
        self.assert_contract_fails(item, "package-specific")

    def test_soft_warning_is_not_operational_stop(self) -> None:
        sample = RUNTIME.evaluate_sample(self.contract, "simulation", 0, 100000001, 10**12, 0)
        self.assertTrue(sample["should_stop"])  # phase-specific 2000-byte budget, not 100MB preference
        self.assertEqual(sample["growth_limit_bytes"], 2000)
        self.assertEqual(sample["trigger_reasons"], ["PHASE_GROWTH_LIMIT"])
        relaxed = copy.deepcopy(self.contract)
        relaxed["phase_watches"][1]["growth_limit_bytes"] = 200000000
        relaxed["phase_watches"][1]["remaining_projection_bytes"] = 1
        sample = RUNTIME.evaluate_sample(relaxed, "simulation", 0, 100000001, 10**12, 0)
        self.assertFalse(sample["should_stop"], sample)

    def test_growth_reserve_and_repeated_stop(self) -> None:
        growth = RUNTIME.evaluate_sample(self.contract, "compile", 0, 1001, 10**9, 0)
        self.assertIn("PHASE_GROWTH_LIMIT", growth["trigger_reasons"])
        reserve = RUNTIME.evaluate_sample(self.contract, "compile", 0, 0, 999, 0)
        self.assertIn("FILESYSTEM_RESERVE_FLOOR", reserve["trigger_reasons"])
        repeated = RUNTIME.evaluate_sample(self.contract, "compile", 0, 1001, 10**9, 1)
        self.assertFalse(repeated["valid_one_shot"])
        self.assertIn("REPEATED_OPERATIONAL_STOP", repeated["trigger_reasons"])

    def _package_zip(self, mutation: str | None = None) -> Path:
        source = b'{"basis":"synthetic"}\n'
        contract = copy.deepcopy(self.contract)
        package_id = "synthetic_observer_next_fresh"
        contract["threshold_source"]["sha256"] = hashlib.sha256(source).hexdigest()
        runner = """#!/usr/bin/env bash
python3 package_tools/server_observer_operational_attempt_boundary.py preflight
python3 package_tools/server_observer_operational_attempt_boundary.py supervise-phase --phase compile --execution-id e1 --attempt-id a1 --guard-log guard.log
python3 package_tools/server_observer_operational_attempt_boundary.py supervise-phase --phase simulation --execution-id e1 --attempt-id a1 --guard-log guard.log
python3 package_tools/server_observer_operational_attempt_boundary.py supervise-phase --phase finalization --execution-id e1 --attempt-id a1 --guard-log guard.log
echo DURABLE_RETURN_RECEIPT.json
python3 package_tools/server_observer_operational_attempt_boundary.py cleanup-after-durable-return
"""
        allow = {"exact": list(VALIDATOR.REQUIRED_RETURN_MEMBERS)}
        members = {
            f"{package_id}/contracts/observer_operational_attempt_boundary.json": RUNTIME.json_bytes(contract),
            f"{package_id}/package_tools/server_observer_operational_attempt_boundary.py": RUNTIME_PATH.read_bytes(),
            f"{package_id}/package_tools/server_observer_operational_guard_v2.py": (ROOT / "tools" / "server_observer_operational_guard_v2.py").read_bytes(),
            f"{package_id}/schemas/server_observer_operational_guard_receipt_v2.schema.json": (ROOT / "schemas" / "server_observer_operational_guard_receipt_v2.schema.json").read_bytes(),
            f"{package_id}/schemas/server_observer_operational_live_tree_policy_v2.schema.json": (ROOT / "schemas" / "server_observer_operational_live_tree_policy_v2.schema.json").read_bytes(),
            f"{package_id}/contracts/observer_operational_live_tree_policy_v2.json": (ROOT / "fixtures" / "server_observer_operational_guard_live_tree_v2" / "positive_live_tree_policy.json").read_bytes(),
            f"{package_id}/PREPARE_AND_RUN.sh": runner.encode(),
            f"{package_id}/RETURN_ALLOWLIST.json": RUNTIME.json_bytes(allow),
            f"{package_id}/receipts/operational_budget_source.json": source,
        }
        if mutation == "truncate":
            members[f"{package_id}/PREPARE_AND_RUN.sh"] += b"truncate -s 1 observer/chunks/events.jsonl\n"
        elif mutation == "helper":
            members[f"{package_id}/package_tools/server_observer_operational_attempt_boundary.py"] += b"# drift\n"
        elif mutation == "source":
            members[f"{package_id}/receipts/operational_budget_source.json"] = b"drift"
        target = self.root / f"package-{mutation or 'ok'}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        return target

    def test_positive_final_zip_and_negative_controls(self) -> None:
        report = VALIDATOR.validate_final_zip(self._package_zip())
        self.assertTrue(report["pass"], report)
        for mutation, fragment in (("truncate", "truncation/deletion"), ("helper", "byte-exact"), ("source", "threshold source")):
            report = VALIDATOR.validate_final_zip(self._package_zip(mutation))
            self.assertFalse(report["pass"], (mutation, report))
            self.assertTrue(any(fragment in error for error in report["errors"]), report)

    def _stopped_receipt(self) -> dict:
        return {
            "schema": RUNTIME.GUARD_V2.SCHEMA,
            "package_id": self.contract["package_id"],
            "execution_id": "e1",
            "attempt_id": "a1",
            "phase": "simulation",
            "command_started": True,
            "child_pid": 1001,
            "child_process_identity": {"pid": 1001, "start_time_ticks": 123456},
            "process_identity_model": {
                "snapshot_backend": "PROCFS_NO_CHILD_ENUMERATOR",
                "identity_fields": ["pid", "start_time_ticks"],
                "pid_reuse_protection": True,
                "self_enumerator_child_process": False,
            },
            "one_shot_stop": True,
            "samples": [{"seq": 0}],
            "stop_count": 1,
            "failure_classification": "OPERATIONAL_BOUNDARY_STOP",
            "production_compile_error_claim_allowed": False,
            "trigger": {"trigger_reasons": ["PHASE_GROWTH_LIMIT"]},
            "termination": {
                "actions": [],
                "owned_pids_remaining": [],
                "owned_process_identities_remaining": [],
                "process_tree_reaped": True,
            },
            "process_fully_reaped": True,
            "stderr_receipt": {"path": "guard.log", "bytes": 0, "sha256": "0" * 64},
            "completed_rows_preserved": True,
            "flushable_rows_flushed": True,
            "process_tree_reaped": True,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "forbidden_claims_asserted": False,
            "errors": [],
            "pass": True,
        }

    def test_operational_return_is_partial_only(self) -> None:
        members = {
            "OPERATIONAL_STOP_RECEIPT.json": RUNTIME.json_bytes(self._stopped_receipt()),
            "DURABLE_RETURN_RECEIPT.json": RUNTIME.json_bytes({
                "zip_crc_verified": True, "exact_member_set_verified": True,
                "sidecar_bytes_sha256_verified": True, "atomic_unique_publication": True,
            }),
            "PARTIAL_EXIT.json": b"{}\n",
        }
        target = self.root / "return.zip"
        with zipfile.ZipFile(target, "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        report = VALIDATOR.validate_return(target, self.contract)
        self.assertTrue(report["pass"], report)
        item = json.loads(members["OPERATIONAL_STOP_RECEIPT.json"])
        item["diagnostic_status"] = "COMPLETE"
        members["OPERATIONAL_STOP_RECEIPT.json"] = RUNTIME.json_bytes(item)
        with zipfile.ZipFile(target, "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        report = VALIDATOR.validate_return(target, self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("cannot claim COMPLETE" in error or "upgraded" in error for error in report["errors"]))

    def _cleanup_args(self, attempt: Path, target: Path, sidecar: Path, receipt: Path, execute: bool) -> Namespace:
        return Namespace(
            attempt_root=attempt, return_zip=target, sidecar=sidecar,
            owned_leaf=["owned"], receipt=receipt, execute=execute,
        )

    def test_cleanup_only_after_durable_identity_and_preserves_foreign(self) -> None:
        attempt = self.root / "attempt"
        (attempt / "owned").mkdir(parents=True)
        (attempt / "owned" / "events.jsonl").write_text("row\n", encoding="utf-8")
        (attempt / "foreign").mkdir()
        foreign = attempt / "foreign" / "keep.bin"
        foreign.write_bytes(b"foreign")
        target = self.root / "published.zip"
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("core.json", b"{}\n")
        size, sha = RUNTIME.sha256_file(target)
        sidecar = self.root / "published.zip.json"
        sidecar.write_bytes(RUNTIME.json_bytes({"bytes": size, "sha256": sha, "members": ["core.json"]}))
        receipt = self.root / "cleanup.json"
        report = RUNTIME.durable_cleanup(self._cleanup_args(attempt, target, sidecar, receipt, True), self.contract)
        self.assertTrue(report["pass"], report)
        self.assertFalse((attempt / "owned").exists())
        self.assertEqual(foreign.read_bytes(), b"foreign")

    def test_failed_durability_leaves_attempt_recoverable(self) -> None:
        attempt = self.root / "attempt-fail"
        (attempt / "owned").mkdir(parents=True)
        evidence = attempt / "owned" / "events.jsonl"
        evidence.write_text("row\n", encoding="utf-8")
        target = self.root / "bad.zip"
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("core.json", b"{}\n")
        sidecar = self.root / "bad.zip.json"
        sidecar.write_bytes(RUNTIME.json_bytes({"bytes": 1, "sha256": "0" * 64, "members": []}))
        report = RUNTIME.durable_cleanup(self._cleanup_args(attempt, target, sidecar, self.root / "bad-cleanup.json", True), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(evidence.exists())
        self.assertTrue(report["failed_publication_uncleaned"])


if __name__ == "__main__":
    unittest.main()
