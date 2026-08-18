from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_server_tb_vcd_bounded_causal_cone import validate_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/positive_contract.json"
SCHEMA = ROOT / "schemas/server_tb_vcd_bounded_causal_cone_v1.schema.json"
BASELINE = ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/third_round_breadth_baseline.json"


def canonical_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def catalog_source_identity_sha(signals: list[dict]) -> str:
    rows = [
        {
            "signal_id": item["signal_id"],
            "exact_hierarchy": item["exact_hierarchy"],
            "width_bits": item["width_bits"],
            "source_path": item["source_path"],
            "source_sha256": item["source_sha256"],
            "declaration_span_sha256": item["declaration_span_sha256"],
        }
        for item in signals
    ]
    return canonical_sha(sorted(rows, key=lambda row: row["signal_id"]))


class TbVcdBoundedCausalConeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def assert_fails(self, item: dict, text: str) -> None:
        report = validate_contract(item, ROOT)
        self.assertFalse(report["pass"])
        self.assertIn(text, "\n".join(report["errors"]))

    def make_refined_successor(self, root: Path) -> tuple[dict, dict]:
        source = ROOT / self.contract["execution"]["tb_source_path"]
        current_tb = root / "current_tb.sv"
        current_tb.write_bytes(source.read_bytes())
        baseline = root / "baseline.json"
        baseline.write_bytes(BASELINE.read_bytes())

        prior = copy.deepcopy(self.contract)
        prior["package_id"] = "synthetic-vcd-round1-with-extra"
        extra = {
            "signal_id": "sig_prior_extra",
            "exact_hierarchy": "tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13.prior_only_debug",
            "width_bits": 1,
            "roles": ["internal_state"],
            "source_path": "slice13.sv",
            "source_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "declaration_span_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "source_binding": "ACTUAL_SOURCE_NET",
            "derived_expected_equation": False,
            "driver_leaf_for_candidate_ids": [],
            "driver_depth_edges": None,
            "drives_dut": False,
        }
        prior["signals"].append(extra)
        prior["execution"]["dump_targeting"]["signal_ids"].append(extra["signal_id"])
        prior["scope"]["dump_scopes"][0]["source_bound_signal_ids"].append(extra["signal_id"])
        prior["boundaries"][-1]["signal_ids"].append(extra["signal_id"])
        prior_text = source.read_text(encoding="utf-8")
        anchor = "      $dumpon;"
        prior_text = prior_text.replace(
            anchor,
            f"      $dumpvars(0, {extra['exact_hierarchy']});\n{anchor}",
            1,
        )
        prior_tb = root / "prior_tb.sv"
        prior_tb.write_text(prior_text, encoding="utf-8")
        prior["execution"]["tb_source_path"] = "prior_tb.sv"
        prior["execution"]["tb_source_sha256"] = hashlib.sha256(prior_tb.read_bytes()).hexdigest()
        prior["diagnostic_round"]["breadth_baseline"]["receipt_path"] = "baseline.json"
        prior["diagnostic_round"]["breadth_baseline"]["receipt_sha256"] = hashlib.sha256(baseline.read_bytes()).hexdigest()
        prior["diagnostic_round"]["source_identity"]["catalog_source_identity_sha256"] = catalog_source_identity_sha(prior["signals"])
        prior["diagnostic_round"]["evolution"]["added_signal_ids"].append(extra["signal_id"])
        self.assertTrue(validate_contract(prior, root)["pass"], validate_contract(prior, root))
        prior_path = root / "prior.json"
        prior_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
        prior_receipt = root / "prior_release_receipt.json"
        prior_receipt.write_text(
            json.dumps({
                "activation_epoch": "synthetic-semantic-v7",
                "errors": [],
                "family": prior["family"],
                "package_id": prior["package_id"],
                "pass": True,
                "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
            }, indent=2),
            encoding="utf-8",
        )

        current = copy.deepcopy(self.contract)
        current["package_id"] = "synthetic-vcd-round2-refined"
        current["execution"]["tb_source_path"] = "current_tb.sv"
        current["execution"]["tb_source_sha256"] = hashlib.sha256(current_tb.read_bytes()).hexdigest()
        round_contract = current["diagnostic_round"]
        round_contract["round_index"] = 2
        round_contract["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
        round_contract["breadth_baseline"]["receipt_path"] = "baseline.json"
        round_contract["breadth_baseline"]["receipt_sha256"] = hashlib.sha256(baseline.read_bytes()).hexdigest()
        round_contract["evolution"] = {
            "predecessor": {
                "package_id": prior["package_id"],
                "round_index": 1,
                "contract_path": "prior.json",
                "contract_sha256": hashlib.sha256(prior_path.read_bytes()).hexdigest(),
                "pinned_rtl_tree_sha256": round_contract["source_identity"]["pinned_rtl_tree_sha256"],
                "published_gate_semantic_version": "7",
                "published_pass_receipt_path": "prior_release_receipt.json",
                "published_pass_receipt_sha256": hashlib.sha256(prior_receipt.read_bytes()).hexdigest(),
            },
            "added_signal_ids": [],
            "removed_signal_ids": [extra["signal_id"]],
            "unchanged_signal_ids": [item["signal_id"] for item in current["signals"]],
            "removal_evidence": [
                {
                    "signal_id": extra["signal_id"],
                    "reason": "Prior evidence makes this debug-only state unlikely to affect the ready-blocked candidate.",
                    "confidence": "MEDIUM",
                    "affected_candidate_ids": ["c_ready_blocked"],
                    "disposition": "FAMILY_ADAPTIVE_PRUNING",
                }
            ],
            "candidate_preservation": {
                "preserved_candidate_ids": [item["candidate_id"] for item in current["candidates"]],
                "closed_candidate_ids": [],
                "new_candidate_ids": [],
                "closure_evidence": [],
            },
        }
        return current, prior

    def test_legacy_v5_predecessor_uses_exact_published_pass_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, prior = self.make_refined_successor(root)
            prior["budget"] = {
                "soft_warning_bytes": 100000000,
                "operational_vcd_budget_bytes": 8000000000,
                "return_budget_bytes": 10000000000,
                "wall_ceiling_seconds": 3600,
                "hard_truncation": False,
                "sampling": False,
                "size_based_deletion": False,
            }
            prior["execution"]["tb_source_path"] = "historical_v5_source_not_copied.svh"
            prior_path = root / "prior.json"
            prior_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
            receipt = root / "prior_release_receipt.json"
            receipt.write_text(json.dumps({
                "activation_epoch": "tb-vcd-planned-dumpoff-consistency-v5-test",
                "errors": [],
                "family": prior["family"],
                "package_id": prior["package_id"],
                "pass": True,
                "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE",
            }, indent=2), encoding="utf-8")
            predecessor = item["diagnostic_round"]["evolution"]["predecessor"]
            predecessor["contract_sha256"] = hashlib.sha256(prior_path.read_bytes()).hexdigest()
            predecessor["published_gate_semantic_version"] = "5"
            predecessor["published_pass_receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
            report = validate_contract(item, root)
        self.assertTrue(report["pass"], report)

    def test_exact_qadd_v73_semantic_v7_predecessor_passes_current_v8(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, prior = self.make_refined_successor(root)
            prior["package_id"] = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
            prior_path = root / "prior.json"
            prior_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
            receipt = root / "prior_release_receipt.json"
            receipt.write_text(json.dumps({
                "activation_epoch": "qadd-source-bound-wall-8400-v1+tb-vcd-predecessor-semantic-compatibility-v7",
                "errors": [],
                "family": prior["family"],
                "package_id": prior["package_id"],
                "pass": True,
                "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            }, indent=2), encoding="utf-8")
            predecessor = item["diagnostic_round"]["evolution"]["predecessor"]
            predecessor["package_id"] = prior["package_id"]
            predecessor["contract_sha256"] = hashlib.sha256(prior_path.read_bytes()).hexdigest()
            predecessor["published_gate_semantic_version"] = "7"
            predecessor["published_pass_receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
            report = validate_contract(item, root)
        self.assertTrue(report["pass"], report)

    def test_exact_qadd_v73_semantic_v7_source_identity_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, prior = self.make_refined_successor(root)
            prior["package_id"] = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
            prior["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"] = "f" * 64
            prior_path = root / "prior.json"
            prior_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
            receipt = root / "prior_release_receipt.json"
            receipt.write_text(json.dumps({
                "activation_epoch": "qadd-source-bound-wall-8400-v1+tb-vcd-predecessor-semantic-compatibility-v7",
                "errors": [],
                "family": prior["family"],
                "package_id": prior["package_id"],
                "pass": True,
                "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            }, indent=2), encoding="utf-8")
            predecessor = item["diagnostic_round"]["evolution"]["predecessor"]
            predecessor["package_id"] = prior["package_id"]
            predecessor["contract_sha256"] = hashlib.sha256(prior_path.read_bytes()).hexdigest()
            predecessor["published_gate_semantic_version"] = "7"
            predecessor["published_pass_receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("pinned RTL source identity drifted", "\n".join(report["errors"]))

    def test_exact_qadd_v73_semantic_v7_invalid_receipt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, prior = self.make_refined_successor(root)
            prior["package_id"] = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
            prior_path = root / "prior.json"
            prior_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
            receipt = root / "prior_release_receipt.json"
            receipt.write_text(json.dumps({
                "activation_epoch": "qadd-source-bound-wall-8400-v1",
                "errors": [],
                "family": prior["family"],
                "package_id": prior["package_id"],
                "pass": True,
                "status": "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE_STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            }, indent=2), encoding="utf-8")
            predecessor = item["diagnostic_round"]["evolution"]["predecessor"]
            predecessor["package_id"] = prior["package_id"]
            predecessor["contract_sha256"] = hashlib.sha256(prior_path.read_bytes()).hexdigest()
            predecessor["published_gate_semantic_version"] = "7"
            predecessor["published_pass_receipt_sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("legacy predecessor PASS receipt does not bind its declared semantic version", "\n".join(report["errors"]))

    def test_exact_qadd_v73_semantic_v7_receipt_sha_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, prior = self.make_refined_successor(root)
            predecessor = item["diagnostic_round"]["evolution"]["predecessor"]
            predecessor["package_id"] = "r5_qadd_n7_tailround_lanephase_v73_w8400v7"
            predecessor["published_gate_semantic_version"] = "7"
            predecessor["published_pass_receipt_sha256"] = "f" * 64
            prior["package_id"] = predecessor["package_id"]
            (root / "prior.json").write_text(json.dumps(prior, indent=2), encoding="utf-8")
            predecessor["contract_sha256"] = hashlib.sha256((root / "prior.json").read_bytes()).hexdigest()
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("published PASS receipt: evidence SHA mismatch", "\n".join(report["errors"]))

    def test_legacy_predecessor_published_receipt_sha_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, _prior = self.make_refined_successor(root)
            predecessor = item["diagnostic_round"]["evolution"]["predecessor"]
            predecessor["published_gate_semantic_version"] = "5"
            predecessor["published_pass_receipt_sha256"] = "f" * 64
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("published PASS receipt: evidence SHA mismatch", "\n".join(report["errors"]))

    def test_positive_contract_and_schema(self) -> None:
        report = validate_contract(self.contract, ROOT)
        self.assertTrue(report["pass"], report)
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(self.contract, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_full_hierarchy_scope_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["scope"]["full_hierarchy_dump"] = True
        item["scope"]["dump_scopes"][0]["exact_hierarchy"] = item["scope"]["simulation_top"]
        self.assert_fails(item, "full hierarchy")

    def test_missing_causal_role_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["role_coverage"] = item["role_coverage"][:-1]
        self.assert_fails(item, "every causal role")

    def test_incomplete_candidate_matrix_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["candidate_boundary_matrix"].pop()
        self.assert_fails(item, "matrix is incomplete")

    def test_indistinguishable_candidates_fail(self) -> None:
        item = copy.deepcopy(self.contract)
        first = {row["boundary_id"]: row["expected_signature"] for row in item["candidate_boundary_matrix"] if row["candidate_id"] == "c_ready_blocked"}
        for row in item["candidate_boundary_matrix"]:
            if row["candidate_id"] == "c_owner_mismatch":
                row["expected_signature"] = first[row["boundary_id"]]
        self.assert_fails(item, "not distinguishable")

    def test_derived_expected_signal_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["signals"][2]["source_binding"] = "DERIVED_EXPECTED"
        item["signals"][2]["derived_expected_equation"] = True
        self.assert_fails(item, "derived-only expected")

    def test_vendor_or_make_dump_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["execution"]["sim_argv"].append("DUMP_VCD=1")
        self.assert_fails(item, "forbidden Make/vendor dump")

    def test_hard_truncation_and_sampling_fail(self) -> None:
        item = copy.deepcopy(self.contract)
        item["budget"]["hard_truncation"] = True
        item["budget"]["sampling"] = True
        report = validate_contract(item, ROOT)
        self.assertGreaterEqual(len(report["errors"]), 2)

    def test_wall_extension_without_bound_admission_fails_closed(self) -> None:
        item = copy.deepcopy(self.contract)
        item["budget"]["wall_ceiling_seconds"] = 8400
        item["budget"]["runtime_budget_mode"] = "MEASURED_PRETARGET_AWARE"
        self.assert_fails(item, "admission receipt path")

    def test_wall_extension_with_exact_measured_admission_passes(self) -> None:
        item = copy.deepcopy(self.contract)
        path = ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/qadd_v70_runtime_budget_admission.json"
        item["budget"].update({
            "wall_ceiling_seconds": 8400,
            "runtime_budget_mode": "MEASURED_PRETARGET_AWARE",
            "runtime_budget_admission_path": path.relative_to(ROOT).as_posix(),
            "runtime_budget_admission_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
        report = validate_contract(item, ROOT)
        self.assertTrue(report["pass"], report)

    def test_first_round_below_reference_range_passes_with_explanation_warning(self) -> None:
        item = copy.deepcopy(self.contract)
        baseline = item["diagnostic_round"]["breadth_baseline"]
        baseline["reasonable_signal_count_range"] = {"minimum": 9, "maximum": 12}
        baseline["deviation"] = {
            "relation": "BELOW_REFERENCE_RANGE",
            "explanation": "The exact candidate matrix remains distinguishable with a narrower catalog.",
            "acknowledged": True,
        }
        report = validate_contract(item, ROOT)
        self.assertTrue(report["pass"], report)
        self.assertIn("not a package blocker", "\n".join(report["warnings"]))

    def test_soft_reference_deviation_without_explanation_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        baseline = item["diagnostic_round"]["breadth_baseline"]
        baseline["reasonable_signal_count_range"] = {"minimum": 9, "maximum": 12}
        baseline["deviation"] = {
            "relation": "BELOW_REFERENCE_RANGE",
            "explanation": None,
            "acknowledged": True,
        }
        self.assert_fails(item, "deviation requires a non-empty explanation")

    def test_first_round_baseline_must_reference_round_three_or_later(self) -> None:
        item = copy.deepcopy(self.contract)
        item["diagnostic_round"]["breadth_baseline"]["reference_round_index"] = 2
        self.assert_fails(item, "reference round must be at least three")

    def test_high_probability_candidate_without_direct_driver_is_record_only_gap(self) -> None:
        item = copy.deepcopy(self.contract)
        for signal in item["signals"]:
            if "c_ready_blocked" in signal["driver_leaf_for_candidate_ids"]:
                signal["driver_leaf_for_candidate_ids"].remove("c_ready_blocked")
                if not signal["driver_leaf_for_candidate_ids"]:
                    signal["driver_depth_edges"] = None
        item["diagnostic_round"]["coverage_gaps"] = [
            {
                "candidate_id": "c_ready_blocked",
                "gap_code": "HIGH_CANDIDATE_ZERO_HOP_DRIVER_ABSENT",
                "reason": "The exact source leaf is not elaborated in this package, but the matrix remains distinguishable.",
                "matrix_still_distinguishable": True,
            }
        ]
        report = validate_contract(item, ROOT)
        self.assertTrue(report["pass"], report)
        self.assertEqual(report["missing_high_candidate_direct_driver_ids"], ["c_ready_blocked"])

    def test_high_candidate_driver_gap_must_be_recorded_exactly(self) -> None:
        item = copy.deepcopy(self.contract)
        for signal in item["signals"]:
            if "c_ready_blocked" in signal["driver_leaf_for_candidate_ids"]:
                signal["driver_leaf_for_candidate_ids"].remove("c_ready_blocked")
                if not signal["driver_leaf_for_candidate_ids"]:
                    signal["driver_depth_edges"] = None
        self.assert_fails(item, "coverage gaps do not exactly match")

    def test_direct_driver_must_be_zero_hop(self) -> None:
        item = copy.deepcopy(self.contract)
        item["signals"][2]["driver_depth_edges"] = 1
        self.assert_fails(item, "driver_depth_edges=0")

    def test_catalog_source_identity_drift_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["diagnostic_round"]["source_identity"]["catalog_source_identity_sha256"] = "f" * 64
        self.assert_fails(item, "catalog source identity SHA differs")

    def test_first_fresh_negative_control_set_is_exact(self) -> None:
        item = copy.deepcopy(self.contract)
        del item["first_fresh_controls"]["negative_controls"]["candidate_loss"]
        self.assert_fails(item, "negative controls are incomplete")

    def test_evidence_refined_successor_with_adaptive_pruning_record_passes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, _prior = self.make_refined_successor(root)
            report = validate_contract(item, root)
        self.assertTrue(report["pass"], report)

    def test_refined_successor_removal_without_evidence_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, _prior = self.make_refined_successor(root)
            item["diagnostic_round"]["evolution"]["removal_evidence"] = []
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("every removed signal requires exactly one adaptive-pruning record", "\n".join(report["errors"]))

    def test_refined_successor_low_confidence_signal_is_retained_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, _prior = self.make_refined_successor(root)
            item["diagnostic_round"]["evolution"]["removal_evidence"][0]["confidence"] = "LOW"
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("low-confidence signal must be retained by default", "\n".join(report["errors"]))

    def test_refined_successor_add_remove_diff_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, _prior = self.make_refined_successor(root)
            item["diagnostic_round"]["evolution"]["added_signal_ids"] = ["sig_clk"]
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("diff does not match predecessor", "\n".join(report["errors"]))

    def test_refined_successor_candidate_loss_without_closure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, _prior = self.make_refined_successor(root)
            item["diagnostic_round"]["evolution"]["candidate_preservation"]["preserved_candidate_ids"].pop()
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("candidate preservation/closure/new diff is incomplete", "\n".join(report["errors"]))

    def test_refined_successor_source_identity_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            item, _prior = self.make_refined_successor(root)
            item["diagnostic_round"]["evolution"]["predecessor"]["pinned_rtl_tree_sha256"] = "f" * 64
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("pinned RTL source identity drifted", "\n".join(report["errors"]))

    def test_exact_dump_target_set_must_equal_catalog(self) -> None:
        item = copy.deepcopy(self.contract)
        item["execution"]["dump_targeting"]["signal_ids"].pop()
        self.assert_fails(item, "must equal the complete source-bound catalog")

    def test_module_scope_over_dump_fails_even_with_exact_catalog_contract(self) -> None:
        item = copy.deepcopy(self.contract)
        source = ROOT / item["execution"]["tb_source_path"]
        text = source.read_text(encoding="utf-8")
        first = text.index("      $dumpvars")
        last = text.index("      $dumpon", first)
        bad = text[:first] + "      $dumpvars(0, tb_NDP_Top_new_phy.NDP_Top_phy_INST.slice13);\n" + text[last:]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            target = root / "tb.sv"
            target.write_text(bad, encoding="utf-8")
            item["execution"]["tb_source_path"] = "tb.sv"
            item["execution"]["tb_source_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
            report = validate_contract(item, root)
        self.assertFalse(report["pass"])
        self.assertIn("module/aggregate over-dump", "\n".join(report["errors"]))

    def test_outer_runner_cannot_duplicate_exit_logic(self) -> None:
        item = copy.deepcopy(self.contract)
        item["runtime_policy"]["outer_runner_independent_exit_logic"] = True
        self.assert_fails(item, "outer_runner_independent_exit_logic")

    def test_all_exit_decision_replays_are_required(self) -> None:
        item = copy.deepcopy(self.contract)
        item["runtime_policy"]["required_replay_cases"].remove("PLATEAU_SUSPECTED_ONLY")
        self.assert_fails(item, "required_replay_cases")

    def test_planned_dumpoff_consistency_policy_is_required(self) -> None:
        mutations = (
            ("planned_dumpoff_state_source", "INFERRED_FROM_VCD_STALL"),
            ("post_dumpoff_progress_source", "APPENDED_VCD_TIMESTAMP"),
            ("dump_off_grace_precedes_freeze", False),
            ("stop_marker_policy", "REPEATED_LEVEL"),
        )
        for key, value in mutations:
            item = copy.deepcopy(self.contract)
            item["runtime_policy"][key] = value
            self.assert_fails(item, key)

        item = copy.deepcopy(self.contract)
        item["runtime_policy"]["required_dumpoff_consistency_replays"].pop()
        self.assert_fails(item, "required_dumpoff_consistency_replays")

    def test_dump_control_return_receipt_is_required(self) -> None:
        item = copy.deepcopy(self.contract)
        del item["return_receipts"]["dump_control"]
        self.assert_fails(item, "formal return receipt paths are incomplete")


if __name__ == "__main__":
    unittest.main()
