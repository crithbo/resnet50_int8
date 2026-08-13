from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import jsonschema

from tools.validate_server_first_fresh_extra_audit import (
    REQUIRED_REPORTS,
    STRICT_DIAGNOSTIC_RULE_IDS,
    validate_contract,
)


CONTRACT_SCHEMA = Path("schemas/server_first_fresh_extra_audit_v1.schema.json")
DISPATCH_SCHEMA = Path(
    "schemas/server_first_fresh_extra_audit_dispatch_v1.schema.json"
)
DISPATCH = Path("contracts/server_first_fresh_extra_audit_dispatch_v1.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ServerFirstFreshExtraAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package_dir = self.root / "payload"
        self.package_dir.mkdir()
        self.zip_path = self.root / "first_fresh.zip"
        with zipfile.ZipFile(self.zip_path, "w") as archive:
            archive.writestr("first_fresh/PREPARE_AND_RUN.sh", "exit 0\n")
            archive.writestr("first_fresh/package_tools/parser.py", "pass\n")
        self.reports = self.root / "reports"
        self.reports.mkdir()
        self.report_items: list[dict] = []
        for gate_id, evidence_kind in REQUIRED_REPORTS.items():
            path = self.reports / f"{gate_id}.json"
            path.write_text(
                json.dumps({"pass": True, "errors": [], "gate_id": gate_id}),
                encoding="utf-8",
            )
            self.report_items.append(
                {
                    "gate_id": gate_id,
                    "evidence_kind": evidence_kind,
                    "path": path.relative_to(self.root).as_posix(),
                    "sha256": sha(path),
                }
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def contract(self) -> dict:
        return {
            "schema": "server-first-fresh-extra-audit-v1",
            "package": {
                "package_id": "first_fresh_v1",
                "family": "synthetic",
                "final_zip": {
                    "path": self.zip_path.relative_to(self.root).as_posix(),
                    "bytes": self.zip_path.stat().st_size,
                    "sha256": sha(self.zip_path),
                },
            },
            "rule_change": {
                "epoch_id": "epoch-v1",
                "rule_ids": ["RULE-A", "RULE-B"],
                "first_fresh_for_family": True,
                "notification_acknowledged": True,
            },
            "independent_reaudit": {
                "clean_extract_from_final_zip": True,
                "from_final_zip_only": True,
                "family_build_reports_reused": False,
                "top_level_invocations": 1,
                "all_errors_collected": True,
                "rebuild_per_single_error_forbidden": True,
            },
            "evidence_reports": copy.deepcopy(self.report_items),
            "candidate_discrimination": {
                "candidate_ids": ["memory_owner", "buffer_owner"],
                "covered_candidate_ids": ["memory_owner", "buffer_owner"],
                "uncovered_candidate_ids": [],
                "positive_control_count": 2,
                "negative_control_count": 3,
                "pairwise_distinguishable": True,
            },
            "findings": [],
        }

    def attach_diagnostic_semantics(
        self, contract: dict, *, prior: str | None = None, disposition: str = "FIRST_USE_AUDITED"
    ) -> str:
        fingerprint = "d" * 64
        report_path = self.reports / "source_bound_final_zip_v2.json"
        report_path.write_text(
            json.dumps(
                {
                    "schema": "server-source-bound-final-zip-validation-v2",
                    "pass": True,
                    "errors": [],
                    "zip": {"sha256": sha(self.zip_path)},
                    "diagnostic_semantics_sha256": fingerprint,
                    "semantic_controls": {
                        "pass": True,
                        "diagnostic_semantics_sha256": fingerprint,
                        "case_count": 10,
                    },
                }
            ),
            encoding="utf-8",
        )
        contract["rule_change"]["rule_ids"] = sorted(STRICT_DIAGNOSTIC_RULE_IDS)
        contract["diagnostic_semantics"] = {
            "fingerprint_sha256": fingerprint,
            "final_zip_report_path": report_path.relative_to(self.root).as_posix(),
            "final_zip_report_sha256": sha(report_path),
            "prior_fingerprint_sha256": prior,
            "disposition": disposition,
            "prior_audit_receipt": None,
        }
        return fingerprint

    def test_positive_contract_and_dispatch_schema(self) -> None:
        contract = self.contract()
        jsonschema.validate(
            contract, json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
        )
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        jsonschema.validate(
            dispatch, json.loads(DISPATCH_SCHEMA.read_text(encoding="utf-8"))
        )
        self.assertEqual(
            dispatch["rule_change_epoch_id"],
            "20260811-exact-instance-payload-semantic-fingerprint-v2",
        )
        self.assertIn(
            "diagnostic_semantics_fingerprint_and_disposition",
            dispatch["required_return_fields"],
        )
        result = validate_contract(contract, self.root)
        self.assertTrue(result["pass"])
        self.assertTrue(result["upload_authorized"])
        self.assertEqual(result["candidate_coverage"]["covered"], 2)

    def test_aggregates_all_cheap_and_final_zip_errors(self) -> None:
        contract = self.contract()
        contract["package"]["final_zip"]["bytes"] = 1
        contract["package"]["final_zip"]["sha256"] = "0" * 64
        contract["independent_reaudit"]["family_build_reports_reused"] = True
        contract["evidence_reports"] = contract["evidence_reports"][:-1]
        contract["candidate_discrimination"]["covered_candidate_ids"] = [
            "memory_owner"
        ]
        contract["candidate_discrimination"]["uncovered_candidate_ids"] = [
            "buffer_owner"
        ]
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertFalse(result["upload_authorized"])
        self.assertGreaterEqual(len(result["errors"]), 5)
        self.assertTrue(result["all_errors_collected"])

    def test_changed_diagnostic_semantics_gets_real_first_use_audit(self) -> None:
        contract = self.contract()
        fingerprint = self.attach_diagnostic_semantics(contract)
        jsonschema.validate(
            contract, json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
        )
        result = validate_contract(contract, self.root)
        self.assertTrue(result["pass"], result["errors"])
        self.assertEqual(
            result["diagnostic_semantics"]["fingerprint_sha256"], fingerprint
        )
        self.assertTrue(result["diagnostic_semantics"]["semantics_changed"])

    def test_v80_style_old_receipt_reuse_after_semantic_change_fails(self) -> None:
        contract = self.contract()
        self.attach_diagnostic_semantics(
            contract, prior="c" * 64, disposition="BYTE_EQUAL_RECEIPT_REUSE"
        )
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertTrue(
            any("changed diagnostic semantics" in item for item in result["errors"])
        )

    def test_typed_report_must_bind_exact_zip_and_fingerprint(self) -> None:
        contract = self.contract()
        self.attach_diagnostic_semantics(contract)
        report_path = self.root / contract["diagnostic_semantics"]["final_zip_report_path"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["zip"]["sha256"] = "e" * 64
        report["diagnostic_semantics_sha256"] = "f" * 64
        report_path.write_text(json.dumps(report), encoding="utf-8")
        contract["diagnostic_semantics"]["final_zip_report_sha256"] = sha(report_path)
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertTrue(any("another ZIP" in item for item in result["errors"]))
        self.assertTrue(any("fingerprint/report" in item for item in result["errors"]))

    def test_exact_logger_roundtrip_kind_is_required(self) -> None:
        contract = self.contract()
        item = next(
            value
            for value in contract["evidence_reports"]
            if value["gate_id"]
            == "source_bound_logger_collector_parser_roundtrip"
        )
        item["evidence_kind"] = "synthetic-unpadded-lines-only"
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertTrue(
            any("evidence_kind" in message for message in result["errors"])
        )

    def test_failed_report_is_blocking_but_all_reports_are_consumed(self) -> None:
        contract = self.contract()
        failed = self.reports / "post_sim_return_core_scenarios.json"
        failed.write_text(
            json.dumps({"pass": False, "errors": ["late finalizer"]}),
            encoding="utf-8",
        )
        item = next(
            value
            for value in contract["evidence_reports"]
            if value["gate_id"] == "post_sim_return_core_scenarios"
        )
        item["sha256"] = sha(failed)
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertEqual(len(result["report_receipts"]), len(REQUIRED_REPORTS))
        self.assertTrue(any("late finalizer" in value for value in result["errors"]))

    def test_record_only_finding_does_not_block(self) -> None:
        contract = self.contract()
        contract["findings"] = [
            {
                "finding_id": "NOTE-1",
                "disposition": "record_only",
                "causal_class": None,
                "message": "formatting preference",
            }
        ]
        result = validate_contract(contract, self.root)
        self.assertTrue(result["pass"])
        self.assertEqual(result["finding_counts"]["record_only"], 1)

    def test_blocking_finding_requires_causal_mapping_and_fails(self) -> None:
        contract = self.contract()
        contract["findings"] = [
            {
                "finding_id": "START-1",
                "disposition": "blocking_applicable",
                "causal_class": "server_start",
                "message": "runner cannot reach compile",
            }
        ]
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertEqual(result["finding_counts"]["blocking_applicable"], 1)

    def test_noncausal_blocking_finding_is_rejected(self) -> None:
        contract = self.contract()
        contract["findings"] = [
            {
                "finding_id": "STYLE-1",
                "disposition": "blocking_applicable",
                "causal_class": None,
                "message": "report prose style",
            }
        ]
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertTrue(
            any("lacks valid causal class" in value for value in result["errors"])
        )

    def test_unknown_contract_field_is_rejected(self) -> None:
        contract = self.contract()
        contract["family_builder_pass"] = True
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertTrue(
            any("unknown fields" in value for value in result["errors"])
        )

    def test_bad_zip_and_path_escape_fail_closed(self) -> None:
        contract = self.contract()
        bad = self.root / "bad.zip"
        bad.write_text("not a zip", encoding="utf-8")
        contract["package"]["final_zip"] = {
            "path": "bad.zip",
            "bytes": bad.stat().st_size,
            "sha256": sha(bad),
        }
        contract["evidence_reports"][0]["path"] = "../outside.json"
        result = validate_contract(contract, self.root)
        self.assertFalse(result["pass"])
        self.assertTrue(any("unreadable ZIP" in value for value in result["errors"]))
        self.assertTrue(any("escapes workspace" in value for value in result["errors"]))


if __name__ == "__main__":
    unittest.main()
