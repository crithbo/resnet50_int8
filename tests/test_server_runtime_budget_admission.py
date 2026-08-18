from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.server_runtime_budget_admission import calculate, validate


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas/server_runtime_budget_admission_v1.schema.json"


def v70_request() -> dict:
    return {
        "package_id": "r5_qadd_next",
        "execution_id": "exec-next",
        "mode": "MEASURED_PRETARGET_AWARE",
        "source_measurement": {
            "source_package_id": "r5_qadd_n7_tailround_lanephase_v70_pmapfix",
            "source_return_path": "tested/qadd/v70_return.zip",
            "source_return_sha256": "ae317f36edd28ecf0b9c3bf7d5c7734612d18755932f9fedb371a1203addb369",
            "qualified_progress_source": "PRETARGET_MATRIX_TRANSFER_COMPLETE",
            "qualified_units_completed": 19,
            "total_pretarget_units": 30,
            "elapsed_seconds": 3608.29,
            "target_entry_observed": False,
            "progress_was_advancing": True,
        },
        "safety_factor": 1.25,
        "target_diagnostic_margin_seconds": 900,
        "selected_wall_ceiling_seconds": 8400,
        "absolute_maximum_wall_seconds": 8400,
        "independent_operational_guards": {
            "vcd_operational_budget_bytes": 8000000000,
            "return_budget_bytes": 10000000000,
            "disk_space_guard_enabled": True,
            "growth_projection_enabled": True,
            "write_failure_guard_enabled": True,
            "quota_guard_enabled": True,
        },
    }


def v73_request() -> dict:
    return {
        "package_id": "r5_qadd_next_after_v73",
        "execution_id": "exec-next-v73",
        "mode": "MEASURED_PRETARGET_AWARE",
        "user_authorization": {
            "source_thread_id": "019ff027-e7db-72a3-b282-cfad8708da05",
            "exact_text": "qadd预算允许到15000秒确定跑完",
            "utf8_sha256": "60602079640071373a013309304df0d0e9099a2481a93dfe7953298ac3eb8d58",
            "family": "qlinearadd_node0007",
            "source_package_id": "r5_qadd_n7_tailround_lanephase_v73_w8400v7",
            "source_return_sha256": "a65425c43962ee172bf4583b4a114b0a5123d0a19eb20a80860c19ac52e2f23c",
            "selected_wall_ceiling_seconds": 15000,
            "authorization_scope": "EXACT_V73_MEASURED_RETURN_TO_ONE_NEXT_FRESH_QADD_SUCCESSOR",
        },
        "source_measurement": {
            "authorization_profile_id": "qadd-v73-target-progress-15000",
            "source_package_id": "r5_qadd_n7_tailround_lanephase_v73_w8400v7",
            "source_return_path": "C:/Users/15383/Downloads/r5_qadd_n7_tailround_lanephase_v73_w8400v7_r1786958027042931325_3775010_return.zip",
            "source_return_sha256": "a65425c43962ee172bf4583b4a114b0a5123d0a19eb20a80860c19ac52e2f23c",
            "source_formal_analysis_path": "outputs/qlinearadd_node0007_v73_return_r1786958027042931325_3775010/formal_return_analysis.json",
            "source_formal_analysis_sha256": "f0e7d0298d80c233041be6dd26fda8c6aaaabcca6353586f31cd94cc063bc432",
            "qualified_progress_source": "TARGET_COMPLEMENTARY_PAIR_ACCEPT_CLEAR_OUTPUT",
            "measurement_phase": "TARGET",
            "qualified_units_completed": 12440,
            "total_pretarget_units": 18816,
            "elapsed_seconds": 2855.939969378058,
            "fixed_overhead_seconds": 5562.327059702948,
            "target_entry_observed": True,
            "progress_was_advancing": True,
        },
        "safety_factor": 1.25,
        "target_diagnostic_margin_seconds": 900,
        "selected_wall_ceiling_seconds": 15000,
        "absolute_maximum_wall_seconds": 86400,
        "independent_operational_guards": {
            "vcd_operational_budget_bytes": 8000000000,
            "return_budget_bytes": 10000000000,
            "disk_space_guard_enabled": True,
            "growth_projection_enabled": True,
            "write_failure_guard_enabled": True,
            "quota_guard_enabled": True,
            "signal_guard_enabled": True,
            "plateau_protection_unchanged": True,
            "return_integrity_fail_closed": True,
        },
    }


class RuntimeBudgetAdmissionTests(unittest.TestCase):
    def test_qadd_v70_measurement_admits_bounded_wall(self) -> None:
        receipt = calculate(v70_request())
        self.assertTrue(receipt["pass"], receipt)
        self.assertLessEqual(receipt["projection"]["recommended_wall_ceiling_seconds"], 8400)
        self.assertTrue(validate(receipt)["pass"])
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(receipt, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_exact_qadd_v73_target_progress_admits_15000(self) -> None:
        receipt = calculate(v73_request())
        self.assertTrue(receipt["pass"], receipt)
        self.assertEqual(receipt["authorization_profile_id"], "qadd-v73-target-progress-15000")
        self.assertAlmostEqual(receipt["projection"]["unmargined_projected_total_seconds"], 9882.051051971239)
        self.assertEqual(receipt["projection"]["recommended_wall_ceiling_seconds"], 11862)
        self.assertEqual(receipt["selected_wall_ceiling_seconds"], 15000)
        self.assertEqual(receipt["absolute_maximum_wall_seconds"], 86400)
        self.assertTrue(validate(receipt)["pass"])
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(receipt, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_insufficient_measurement_fails_closed(self) -> None:
        item = v70_request()
        item["source_measurement"]["qualified_units_completed"] = 2
        self.assertFalse(calculate(item)["pass"])

    def test_selected_wall_below_projection_fails_closed(self) -> None:
        item = v70_request()
        item["selected_wall_ceiling_seconds"] = 3600
        self.assertFalse(calculate(item)["pass"])

    def test_other_qadd_source_or_wall_value_requires_new_authorization(self) -> None:
        wrong_source = v70_request()
        wrong_source["source_measurement"]["source_package_id"] = "r5_qadd_other"
        self.assertFalse(calculate(wrong_source)["pass"])
        wrong_wall = v70_request()
        wrong_wall["selected_wall_ceiling_seconds"] = 8399
        self.assertFalse(calculate(wrong_wall)["pass"])

    def test_unbounded_wall_and_weakened_disk_guard_fail_closed(self) -> None:
        item = v70_request()
        item["selected_wall_ceiling_seconds"] = 100000
        item["independent_operational_guards"]["disk_space_guard_enabled"] = False
        receipt = calculate(item)
        self.assertFalse(receipt["pass"])
        self.assertIn("bounded", "\n".join(receipt["errors"]))
        self.assertIn("disk", "\n".join(receipt["errors"]))

    def test_receipt_tampering_is_recomputed(self) -> None:
        receipt = calculate(v70_request())
        tampered = copy.deepcopy(receipt)
        tampered["projection"]["recommended_wall_ceiling_seconds"] -= 1
        self.assertFalse(validate(tampered)["pass"])

    def test_v73_over_authorized_wall_and_identity_drift_fail_closed(self) -> None:
        over = v73_request()
        over["selected_wall_ceiling_seconds"] = 15001
        self.assertFalse(calculate(over)["pass"])
        return_drift = v73_request()
        return_drift["source_measurement"]["source_return_sha256"] = "0" * 64
        self.assertFalse(calculate(return_drift)["pass"])
        analysis_drift = v73_request()
        analysis_drift["source_measurement"]["source_formal_analysis_sha256"] = "1" * 64
        self.assertFalse(calculate(analysis_drift)["pass"])

    def test_v73_selected_and_absolute_maximum_are_distinct_and_fail_closed(self) -> None:
        above_shared_maximum = v73_request()
        above_shared_maximum["absolute_maximum_wall_seconds"] = 86401
        self.assertFalse(calculate(above_shared_maximum)["pass"])
        below_selected = v73_request()
        below_selected["absolute_maximum_wall_seconds"] = 14999
        self.assertFalse(calculate(below_selected)["pass"])
        swapped = v73_request()
        swapped["selected_wall_ceiling_seconds"] = 86400
        swapped["absolute_maximum_wall_seconds"] = 15000
        self.assertFalse(calculate(swapped)["pass"])
        tampered_receipt = calculate(v73_request())
        tampered_receipt["absolute_maximum_wall_seconds"] = 15000
        self.assertFalse(validate(tampered_receipt)["pass"])

    def test_v73_missing_measured_receipt_fails_closed(self) -> None:
        item = v73_request()
        del item["source_measurement"]["source_formal_analysis_path"]
        del item["source_measurement"]["source_formal_analysis_sha256"]
        self.assertFalse(calculate(item)["pass"])

    def test_v73_user_authorization_binding_is_exact(self) -> None:
        missing = v73_request()
        del missing["user_authorization"]
        self.assertFalse(calculate(missing)["pass"])
        drift = v73_request()
        drift["user_authorization"]["exact_text"] += "。"
        self.assertFalse(calculate(drift)["pass"])
        wrong_scope = v73_request()
        wrong_scope["user_authorization"]["source_return_sha256"] = "0" * 64
        self.assertFalse(calculate(wrong_scope)["pass"])

    def test_v73_guard_weakening_fails_closed(self) -> None:
        for field in (
            "disk_space_guard_enabled",
            "growth_projection_enabled",
            "write_failure_guard_enabled",
            "quota_guard_enabled",
            "signal_guard_enabled",
            "plateau_protection_unchanged",
            "return_integrity_fail_closed",
        ):
            with self.subTest(field=field):
                item = v73_request()
                item["independent_operational_guards"][field] = False
                self.assertFalse(calculate(item)["pass"])

    def test_historical_8400_fixture_remains_valid(self) -> None:
        historical = json.loads(
            (ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/qadd_v70_runtime_budget_admission.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(validate(historical)["pass"])
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        jsonschema.validate(historical, json.loads(SCHEMA.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
