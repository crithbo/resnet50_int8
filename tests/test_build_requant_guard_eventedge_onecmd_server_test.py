from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import build_requant_guard_eventedge_onecmd_server_test as builder
from tools import requant_guard_eventedge_server_runtime as event_runtime
from tools import requant_node0001_server_runtime as common_runtime


class RequantGuardEventEdgePackageTests(unittest.TestCase):
    def test_observer_is_event_qualified_xmr_safe_and_read_only(self) -> None:
        tail = builder._eventedge_observer_tail()
        gate = common_runtime.validate_observer_xmr_elaboration(tail)
        self.assertEqual(gate["status"], "pass")
        self.assertEqual(
            gate["runtime_indexed_generated_instance_reference_count"], 0
        )
        self.assertIn("ga_pe_sfu_coeff_addr_o", tail)
        self.assertNotIn("ga_pe_sfu_coeffs_addr", tail)
        self.assertNotIn("force ", tail)
        self.assertNotIn("deposit(", tail)
        for boundary in event_runtime.EVENT_BOUNDARIES:
            self.assertEqual(tail.count(f"boundary={boundary}"), 1)
        self.assertEqual(tail.count("event=qualified"), 8)

    def test_run_script_binds_one_explicit_tb_target(self) -> None:
        script = builder._run_script()
        self.assertEqual(
            script.count('tb_relative_path="native_return_observer.svh"'), 1
        )
        self.assertEqual(script.count("--tb-relative-path"), 3)
        self.assertNotIn("find ", script)
        self.assertNotIn("rglob", script)
        self.assertNotIn("basename", script)

    def test_event_receipt_uses_real_transactions_not_level_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            log_root = run_dir / "sim_results" / "event_logs"
            log_root.mkdir(parents=True)
            per_slice: dict[int, list[str]] = {0: [], 1: []}
            for slice_id in (0, 1):
                for row in range(4):
                    for slot in range(2):
                        pe = f"{row}{2 * slot + 1}"
                        for txn_id in range(4):
                            common = (
                                f"event=qualified cycle={100 + txn_id} "
                                f"slice={slice_id} pe={pe} txn_id={txn_id}"
                            )
                            per_slice[slice_id].extend(
                                [
                                    (
                                        "GUARD_PATH "
                                        "boundary=SFU_COEFF_SRAM_AT_ALU_CAPTURE "
                                        f"{common} coeff_addr=0x41 "
                                        "slope=0x3f800000 intercept=0x00000000 "
                                        "data=0x3f800000"
                                    ),
                                    (
                                        "GUARD_PATH "
                                        "boundary=SFU_ALU_PIPELINE0_ACCEPT "
                                        f"{common} tag=0x1 data0=0x3f800000 "
                                        "data1=0x3f800000 data2=0x00000000 "
                                        "data=0x3f800000"
                                    ),
                                    (
                                        "GUARD_PATH "
                                        "boundary=SFU_ALU_RESULT_PRODUCED "
                                        f"{common} tag=0x1 data=0x3f800000"
                                    ),
                                    (
                                        "GUARD_PATH "
                                        "boundary=SFU_POSTPROCESS_RESULT_AT_OUTBUFFER_ACCEPT "
                                        f"{common} tag=0x1 alu_data=0x3f800000 "
                                        "data=0x3f800000"
                                    ),
                                    (
                                        "GUARD_PATH "
                                        "boundary=NORMAL_OUTBUFFER_WRITE_COMMIT "
                                        f"{common} tag=0x1 data=0x3f800000"
                                    ),
                                    (
                                        "GUARD_PATH "
                                        "boundary=NORMAL_OUTPORT_ACCEPTED "
                                        f"{common} tag=0x1 data=0x3f800000"
                                    ),
                                ]
                            )
                for txn_id in range(8):
                    channel = txn_id % 4
                    per_slice[slice_id].extend(
                        [
                            (
                                "GUARD_PATH boundary=MSE4_REQ event=qualified "
                                f"cycle={300 + txn_id} slice={slice_id} "
                                f"ch={channel} txn_id={txn_id} "
                                f"transfer_addr=0x{txn_id:x} "
                                f"linear_addr=0x{txn_id:x} "
                                f"post_remap_addr=0x{txn_id:x}"
                            ),
                            (
                                "GUARD_PATH boundary=MSE4_WDATA event=qualified "
                                f"cycle={400 + txn_id} slice={slice_id} "
                                f"ch={channel} txn_id={txn_id} "
                                "data=0x0000000000000000000000003f800000"
                            ),
                        ]
                    )
                (log_root / f"slice{slice_id:02d}.log").write_text(
                    "\n".join(per_slice[slice_id]) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            profile = builder._diagnostic_profile()
            profile["observer_log_dir"] = "event_logs"
            receipt = event_runtime.event_checkpoint_gate(run_dir, profile)
            self.assertEqual(receipt["status"], "pass", receipt)
            self.assertFalse(receipt["level_qualifier_count_used_as_transaction_count"])
            for boundary, count in profile["checkpoint_expected_counts"].items():
                metric = receipt["count_checks"][boundary]
                self.assertEqual(metric["qualified_event_count"], count)
                self.assertEqual(metric["parseable_count"], count)
                self.assertEqual(metric["duplicate_sample_count"], 0)
            semantic = receipt["semantic_checks"]
            for key, value in semantic.items():
                if key.endswith("_mismatch_count"):
                    self.assertEqual(value, 0, key)

    def test_route_absorbs_positive_native_silu_control_evidence(self) -> None:
        checkpoints = {
            "status": "pass",
            "count_checks": {},
            "semantic_checks": {
                "coefficient_address_mismatch_count": 0,
                "coefficient_payload_mismatch_count": 1,
                "alu_pipeline0_input_mismatch_count": 0,
                "alu_result_mismatch_count": 0,
                "postprocess_mismatch_count": 0,
                "normal_outbuffer_mismatch_count": 0,
                "normal_outport_mismatch_count": 0,
            },
        }
        route = event_runtime.event_first_divergence(
            {"status": "pass"},
            {"status": "pass"},
            checkpoints,
            {"status": "pass"},
            {"status": "pass"},
        )
        self.assertEqual(
            route["classification"],
            "SFU_LUT_SELECTED_COEFFICIENT_PAYLOAD_DIVERGENCE",
        )
        self.assertIn(
            "REQUANT_SPECIFIC_CONFIG_CONSUMPTION_OR_SELECTION",
            route["responsibility_unresolved"],
        )
        control = route["shared_native_silu_control_evidence"]
        self.assertTrue(control["common_sfu_normal_outbuffer_path_operational"])
        self.assertTrue(
            control["excludes_universal_common_sfu_or_normal_outbuffer_failure"]
        )

    def test_explicit_tb_target_install_verify_restore_is_byte_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ndp_root = root / "NDP_copy_target"
            package_root = root / "package"
            evidence_root = root / "evidence"
            ndp_root.mkdir()
            (package_root / "tb_probe").mkdir(parents=True)
            evidence_root.mkdir()
            observer = ndp_root / "native_return_observer.svh"
            observer.write_text("// preimage\n", encoding="utf-8", newline="\n")
            tail = package_root / "tb_probe/requant_mse4_guard_observer_tail.svh"
            tail.write_text("// read-only tail\n", encoding="utf-8", newline="\n")
            preimage = observer.read_bytes()
            install = common_runtime.install_probe(
                ndp_root,
                package_root,
                evidence_root,
                "native_return_observer.svh",
            )
            verify = common_runtime.verify_probe_installed(
                ndp_root,
                evidence_root,
                "native_return_observer.svh",
            )
            restore = common_runtime.restore_probe(
                ndp_root,
                evidence_root,
                "native_return_observer.svh",
            )
            isolation = install["target_directory_isolation"]
            self.assertTrue(isolation["command_argument_was_explicit"])
            self.assertEqual(isolation["candidate_write_path_count"], 1)
            self.assertFalse(isolation["basename_find_glob_rglob_used"])
            self.assertEqual(verify["xmr_elaboration_gate"]["status"], "pass")
            self.assertTrue(restore["restored"])
            self.assertEqual(observer.read_bytes(), preimage)
            persisted = json.loads(
                (evidence_root / "tb_probe_install_receipt.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(persisted["status"], "restored_byte_exact")


if __name__ == "__main__":
    unittest.main()
