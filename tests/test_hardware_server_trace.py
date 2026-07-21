from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from resnet50_pipeline.hardware_server_trace import analyze_hardware_server_trace_zip


class HardwareServerTraceTests(unittest.TestCase):
    @staticmethod
    def _strict_gate_fixture(
        root: Path,
        *,
        required_slices: list[int],
        minimum_dump_bytes: int = 16,
    ) -> tuple[Path, Path, str, dict[str, object]]:
        package = root / "package"
        package.mkdir()
        expected = "00112233445566778899aabbccddeeff"
        required_metadata = [
            "simulator_version",
            "rtl_version",
            "firmware_version",
            "run_command",
            "exit_status",
            "wall_time_seconds",
            "freeze_id",
            "freeze_manifest_sha256",
            "package_manifest_sha256",
            "preload_readback_report",
            "completed_runtime_stage_count",
        ]
        (package / "runner_contract.json").write_text(
            json.dumps(
                {
                    "comparison_command": "compare-real-hardware-dump",
                    "preload": {
                        "sca_cfg": {
                            "immutable_tb_parser_abi": {
                                "validated_transfer_count": 1,
                            }
                        },
                        "readback_gate": {
                            "probes": [
                                {
                                    "base_addr": "0x00000000",
                                    "expected_128bit": "0x" + expected,
                                }
                            ]
                        }
                    },
                    "execution": {
                        "completion_gate": {
                            "expected_runtime_stage_count": 2,
                            "expected_start_comp_count": 2,
                            "required_markers": ["slice completed", "Total handshakes"],
                        }
                    },
                    "post_run_dump": {
                        "required_slices": required_slices,
                        "minimum_bytes_per_slice": minimum_dump_bytes,
                    },
                    "required_return_metadata": required_metadata,
                }
            ),
            encoding="utf-8",
        )
        (package / "dump_contract.json").write_text(
            json.dumps(
                {
                    "slice_count": len(required_slices),
                    "P": [{"base_addr": "0x00000100", "slice_id": 0, "size_bytes": 16}],
                    "staged_D": [
                        {
                            "base_addr": "0x00000200",
                            "slice_id": 0,
                            "local_half": 0,
                            "size_bytes": 16,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        manifest = {
            "freeze_id": "freeze-test",
            "freeze_manifest_sha256": "a" * 64,
        }
        manifest_path = package / "manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        return_metadata: dict[str, object] = {
            "simulator_version": "sim-test",
            "rtl_version": "rtl-test",
            "firmware_version": "fw-test",
            "run_command": "run-test",
            "exit_status": 0,
            "wall_time_seconds": 1,
            "freeze_id": manifest["freeze_id"],
            "freeze_manifest_sha256": manifest["freeze_manifest_sha256"],
            "package_manifest_sha256": manifest_sha,
            "preload_readback_report": {"status": "passed"},
            "completed_runtime_stage_count": 2,
        }
        tensor = {
            "dtype": "int32",
            "element_count": 1,
            "mismatch_count": 0,
            "actual_sha256": "b" * 64,
            "golden_sha256": "b" * 64,
            "first_mismatch": None,
        }
        preflight = root / "preflight.json"
        preflight.write_text(
            json.dumps(
                {
                    "ndp_target_config_comparison": {
                        "ordered_comparisons": [
                            {"name": "full_operator", "P": tensor, "D": tensor}
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        return package, preflight, expected, return_metadata

    @staticmethod
    def _write_gate_archive(
        path: Path,
        *,
        expected: str,
        terminal_text: str,
        exit_status: int,
        return_metadata: dict[str, object],
        dump_bytes: bytes,
    ) -> None:
        frame_text = (
            f"10 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x{expected} | 0x000000\n"
            + "150 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x"
            + "f" * 32
            + " | 0x000010\n"
            + "160 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x"
            + "e" * 32
            + " | 0x000020\n"
        )
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("terminal_output.txt", terminal_text)
            archive.writestr(
                "sim_results/gexec2slice/slice_all/gexec2slice.log",
                "100 | 0 | 0x000000000000000d\n200 | 0 | 0x000000000000000d\n",
            )
            archive.writestr(
                "sim_results/bank_frame/slice0/bank0_frame.log",
                frame_text,
            )
            archive.writestr(
                "sim_results/bank_frame/slice0/bank0_mc_rdata.log",
                f"20 | 0 | 0 | 0 | 0(R) | 0 | 0x{expected}\n",
            )
            archive.writestr("slice00_Bank00_data.bin", dump_bytes)
            archive.writestr("run_sim_results/v9_exit_status.txt", f"{exit_status}\n")
            archive.writestr("run_metadata.json", json.dumps(return_metadata))

    def test_trace_evidence_alone_never_claims_three_way_numeric_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, preflight, expected, return_metadata = self._strict_gate_fixture(
                root, required_slices=[0]
            )
            archive_path = root / "complete-structural-trace.zip"
            self._write_gate_archive(
                archive_path,
                expected=expected,
                terminal_text="slice completed\nTotal handshakes\n",
                exit_status=0,
                return_metadata=return_metadata,
                dump_bytes=b"\x00" * 16,
            )

            report, _ = analyze_hardware_server_trace_zip(
                archive_path, package, preflight
            )

            self.assertEqual(report["status"], "returned_uncompared")
            self.assertEqual(report["comparison_verdict"], "three_way_not_comparable")
            self.assertEqual(report["hardware_outputs"]["structural_evidence_status"], "passed")
            self.assertEqual(report["numeric_hardware_comparison"]["status"], "not_run")
            self.assertEqual(report["first_failure"]["stage"], "hardware_numeric_comparison")
            self.assertNotEqual(
                report["three_way_comparison"]["golden_vs_hardware"]["status"],
                "passed",
            )

    def test_preload_abort_without_gexec_still_produces_fail_closed_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, preflight, _expected, return_metadata = self._strict_gate_fixture(
                root, required_slices=[0]
            )
            (package / "sca_cfg.json").write_text(
                json.dumps(
                    {
                        "Exec_Base": "0x00104800",
                        "Exec_Length": 307,
                        "ExecutionPlan": {
                            "chunked_transport": {
                                "base_addr": "0x00104800",
                                "path": "install/execplan.head.txt",
                            },
                            "base_addr": "0x00105000",
                            "path": "install/execplan.tail.txt",
                            "semantic_path": "install/execplan.txt",
                        },
                    }
                ),
                encoding="utf-8",
            )
            runner_contract_path = package / "runner_contract.json"
            runner_contract = json.loads(
                runner_contract_path.read_text(encoding="utf-8")
            )
            runner_contract["preload"]["sca_cfg"]["immutable_tb_parser_abi"][
                "validated_transfer_count"
            ] = 2
            runner_contract_path.write_text(
                json.dumps(runner_contract), encoding="utf-8"
            )
            return_metadata["exit_status"] = 2
            return_metadata["completed_runtime_stage_count"] = 0
            archive_path = root / "preload-abort.zip"
            terminal = "\n".join(
                (
                    "[7794000] JSON: Loading matrix[0]: install/execplan.txt -> 0x00104800",
                    "[7794000] JSON: Exec_Base   = 0x00104800",
                    "[7794000] JSON: Exec_Length = 307",
                    "  [Write Burst 0] Addr=0x00104800, Length=256 words",
                    "Simulation exit status: 255",
                    "make: *** [sim] Error 255",
                )
            )
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("v9_return/run_sim_results/v9_console.log", terminal)
                archive.writestr("v9_return/run_sim_results/v9_exit_status.txt", "2\n")
                archive.writestr(
                    "v9_return/sim_results/local_summary/slice_all/local_summary.log",
                    "header only\n",
                )
                archive.writestr(
                    "v9_return/config/sca_cfg.json",
                    (package / "sca_cfg.json").read_text(encoding="utf-8"),
                )
                archive.writestr(
                    "v9_return/run_metadata.json",
                    json.dumps(return_metadata),
                )

            report, extracted = analyze_hardware_server_trace_zip(
                archive_path, package, preflight
            )

            self.assertEqual(report["status"], "returned_failed")
            self.assertEqual(report["comparison_verdict"], "three_way_not_comparable")
            self.assertEqual(report["archive"]["archive_prefix"], "v9_return/")
            self.assertEqual(
                report["archive"]["terminal_output_entry"],
                "run_sim_results/v9_console.log",
            )
            self.assertFalse(report["archive"]["gexec_trace_present"])
            self.assertEqual(report["runtime"]["observed_start_comp_stage_count"], 0)
            self.assertEqual(report["preload"]["terminal_started_matrix_count"], 1)
            self.assertIsNone(report["preload"]["terminal_loaded_matrix_count"])
            self.assertEqual(report["preload"]["sca_cfg_payload_count"], 2)
            self.assertEqual(
                report["preload"]["sca_cfg_payload_count_source"],
                "immutable_tb_parser_abi",
            )
            self.assertEqual(
                report["preload"]["matrix_load_completion_status"], "incomplete"
            )
            self.assertTrue(
                any(
                    "SCA preload did not complete" in reason
                    for reason in report["hardware_outputs"]["incomplete_reasons"]
                )
            )
            self.assertEqual(extracted["gexec2slice.log"], "")

    def test_failure_markers_metadata_and_full_dump_gaps_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, preflight, expected, return_metadata = self._strict_gate_fixture(
                root, required_slices=list(range(28))
            )
            archive_path = root / "old-false-positive-shape.zip"
            self._write_gate_archive(
                archive_path,
                expected=expected,
                terminal_text=(
                    "slice completed\nTotal handshakes\n"
                    "ERROR FAIL timeout; result file exists but run failed\n"
                ),
                exit_status=7,
                return_metadata={"exit_status": 7},
                dump_bytes=b"X",
            )

            report, _ = analyze_hardware_server_trace_zip(
                archive_path, package, preflight
            )

            self.assertEqual(report["status"], "returned_failed")
            self.assertEqual(report["comparison_verdict"], "three_way_not_comparable")
            self.assertEqual(report["runtime"]["status"], "failed")
            self.assertEqual(report["archive"]["simulator_exit_status"]["value"], 7)
            self.assertTrue(report["archive"]["return_metadata"]["missing_keys"])
            dump_gate = report["hardware_outputs"]["post_run_bank_dump_validation"]
            self.assertEqual(dump_gate["status"], "incomplete")
            self.assertEqual(dump_gate["missing_or_undersized_slices"], list(range(28)))
            self.assertIn("slice00_Bank00_data.bin", dump_gate["invalid_entries"])
            self.assertEqual(report["first_failure"]["stage"], "server_run")

    def test_incomplete_runtime_preserves_two_way_pass_and_blocks_hardware_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package.mkdir()
            expected = "00112233445566778899aabbccddeeff"
            (package / "runner_contract.json").write_text(
                json.dumps(
                    {
                        "preload": {
                            "readback_gate": {
                                "probes": [
                                    {
                                        "base_addr": "0x00000000",
                                        "expected_128bit": "0x" + expected,
                                        "kind": "input",
                                        "port": "A",
                                        "source_path": "input.txt",
                                    }
                                ]
                            }
                        },
                        "execution": {
                            "completion_gate": {
                                "expected_runtime_stage_count": 2,
                                "expected_start_comp_count": 2,
                                "required_markers": ["slice completed", "Total handshakes"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (package / "dump_contract.json").write_text(
                json.dumps(
                    {
                        "P": [
                            {
                                "base_addr": "0x00001000",
                                "slice_id": 0,
                                "size_bytes": 16,
                            }
                        ],
                        "staged_D": [
                            {
                                "base_addr": "0x00002000",
                                "slice_id": 0,
                                "local_half": 0,
                                "size_bytes": 16,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (package / "manifest.json").write_text(
                json.dumps(
                    {
                        "freeze_id": "freeze-test",
                        "freeze_manifest_sha256": "a" * 64,
                    }
                ),
                encoding="utf-8",
            )
            preflight = root / "preflight.json"
            tensor = {
                "dtype": "int32",
                "element_count": 1,
                "mismatch_count": 0,
                "actual_sha256": "b" * 64,
                "golden_sha256": "b" * 64,
                "first_mismatch": None,
            }
            preflight.write_text(
                json.dumps(
                    {
                        "ndp_target_config_comparison": {
                            "ordered_comparisons": [
                                {"name": "full_operator", "P": tensor, "D": tensor}
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            archive_path = root / "trace.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("v7_return/run_sim_results/v7_console.log", "loader PASS\n")
                archive.writestr(
                    "v7_return/sim_results/gexec2slice/slice_all/gexec2slice.log",
                    "100 | 0 | 0x000000000000000d\n",
                )
                archive.writestr(
                    "v7_return/sim_results/bank_frame/slice0/bank0_frame.log",
                    f"10 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x{expected} | 0x000000\n",
                )
                archive.writestr(
                    "v7_return/sim_results/bank_frame/slice0/bank0_mc_rdata.log",
                    f"20 | 0 | 0 | 0 | 0(R) | 0 | 0x{expected}\n",
                )

            report, extracted = analyze_hardware_server_trace_zip(
                archive_path,
                package,
                preflight,
            )
            self.assertEqual(report["status"], "returned_incomplete")
            self.assertEqual(report["comparison_verdict"], "three_way_not_comparable")
            self.assertEqual(report["preload"]["strict_readback_status"], "passed")
            self.assertEqual(report["runtime"]["observed_start_comp_stage_count"], 1)
            self.assertEqual(
                report["three_way_comparison"]["golden_vs_config_bound_ndp"]["status"],
                "passed",
            )
            self.assertEqual(report["identity"]["source_freeze_id"], "freeze-test")
            self.assertEqual(report["archive"]["archive_prefix"], "v7_return/")
            self.assertTrue(report["archive"]["terminal_output_present"])
            self.assertIn("terminal_output.txt", extracted)

    def test_unknown_output_rmw_is_reported_before_stage_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package.mkdir()
            (package / "Bank_data").mkdir()
            bank_lines = ["0" * 32] * (0x12 * 4)
            (package / "Bank_data" / "slice00_Bank00_data.txt").write_text(
                "\n".join(bank_lines) + "\n", encoding="ascii"
            )
            (package / "sca_cfg.json").write_text(
                json.dumps({"A": {"base_addr": "0x0", "path": "A.txt"}}),
                encoding="utf-8",
            )
            (package / "runner_contract.json").write_text(
                json.dumps(
                    {
                        "preload": {
                            "readback_gate": {
                                "probes": [
                                    {
                                        "base_addr": "0x00000000",
                                        "expected_128bit": "0x" + "0" * 32,
                                        "kind": "input",
                                        "port": "A",
                                        "source_path": "A.txt",
                                    }
                                ]
                            }
                        },
                        "execution": {
                            "completion_gate": {
                                "expected_runtime_stage_count": 2,
                                "expected_start_comp_count": 2,
                                "required_markers": ["slice completed"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (package / "dump_contract.json").write_text(
                json.dumps(
                    {
                        "slice_count": 1,
                        "P": [
                            {"base_addr": "0x00000100", "slice_id": 0, "size_bytes": 32}
                        ],
                        "staged_D": [
                            {
                                "base_addr": "0x00000200",
                                "slice_id": 0,
                                "local_half": 0,
                                "size_bytes": 16,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (package / "manifest.json").write_text(
                json.dumps({"freeze_id": "freeze-test", "freeze_manifest_sha256": "a" * 64}),
                encoding="utf-8",
            )
            preflight = root / "preflight.json"
            tensor = {
                "dtype": "int32",
                "element_count": 1,
                "mismatch_count": 0,
                "actual_sha256": "b" * 64,
                "golden_sha256": "b" * 64,
                "first_mismatch": None,
            }
            preflight.write_text(
                json.dumps(
                    {
                        "ndp_target_config_comparison": {
                            "ordered_comparisons": [
                                {"name": "full_operator", "P": tensor, "D": tensor}
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            archive_path = root / "trace.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("terminal_output.txt", "JSON config: 1 matrices loaded\n")
                archive.writestr(
                    "sim_results/gexec2slice/slice_all/gexec2slice.log",
                    "100 | 0 | 0x000000000000000d\n",
                )
                archive.writestr(
                    "sim_results/bank_frame/slice0/bank0_frame.log",
                    "10 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x00000000000000000000000000000000 | 0x000000\n"
                    "11 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x00000000000000000000000000000000 | 0x000010\n",
                )
                archive.writestr(
                    "sim_results/bank_frame/slice0/bank0_mc_rdata.log",
                    "20 | 0 | 0 | 0 | 0(R) | 0 | 0x00000000000000000000000000000000\n",
                )
                archive.writestr(
                    "sim_results/local/slice0/local_mse4_req.log",
                    "[101] INFO: slice start (cycle=0, start_idx=1)\n"
                    "110 | 0 | 0x000010 | 0 | 0 | 16 | 0 | 1\n"
                    "111 | 0 | 0x000010 | 0 | 0 | 16 | 1 | 2\n",
                )
                archive.writestr(
                    "sim_results/local/slice0/local_mse4_rdata.log",
                    "[101] INFO: slice start (cycle=0, start_idx=1)\n"
                    "120 | 0 | 0 | 110 | 0xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n",
                )
                archive.writestr(
                    "sim_results/local/slice0/local_mse4_wdata.log",
                    "[101] INFO: slice start (cycle=0, start_idx=1)\n",
                )
                archive.writestr(
                    "sim_results/local_completed_other_run/slice0/local_mse4_req.log",
                    "[10001] INFO: slice start (cycle=0, start_idx=1)\n"
                    "[10020] INFO: slice completed\n",
                )

            report, _ = analyze_hardware_server_trace_zip(archive_path, package, preflight)
            local = report["runtime"]["local_slice_execution"]
            self.assertEqual(local["namespace"], "local")
            self.assertEqual(local["start_comp_to_slice_start_ns"], 1)
            self.assertEqual(local["status"], "stalled_on_unknown_output_read_modify_write")
            self.assertEqual(local["slices_with_unknown_output_reads"], 1)
            self.assertEqual(local["output_write_request_count"], 1)
            self.assertEqual(local["output_write_data_handshake_count"], 0)
            self.assertEqual(report["first_failure"]["stage"], "slice_output_read_modify_write")
            self.assertEqual(
                local["slices"][0]["output_read_returns"][0]["expected_bank_data_128bit"],
                "0x" + "0" * 32,
            )
            self.assertEqual(report["hardware_outputs"]["P_bank_write_transactions"], 0)
            self.assertEqual(
                report["hardware_outputs"]["P_bank_write_transactions_all_phases"], 1
            )

            clean_archive_path = root / "clean-trace.zip"
            with zipfile.ZipFile(clean_archive_path, "w") as archive:
                archive.writestr("terminal_output.txt", "")
                archive.writestr(
                    "sim_results/gexec2slice/slice_all/gexec2slice.log",
                    "100 | 0 | 0x000000000000000d\n",
                )
                archive.writestr(
                    "sim_results/bank_frame/slice0/bank0_frame.log",
                    "10 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x00000000000000000000000000000000 | 0x000000\n"
                    "11 | 0 | 0 | 0 | 1(W) | 1 | 0 | 0x00000000000000000000000000000000 | 0x000010\n",
                )
                archive.writestr(
                    "sim_results/bank_frame/slice0/bank0_mc_rdata.log",
                    "20 | 0 | 0 | 0 | 0(R) | 0 | 0x00000000000000000000000000000000\n",
                )
                archive.writestr(
                    "sim_results/local/slice0/local_mse4_req.log",
                    "[101] INFO: slice start (cycle=0, start_idx=1)\n"
                    "110 | 0 | 0x000010 | 0 | 0 | 16 | 0 | 1\n"
                    "111 | 0 | 0x000010 | 0 | 0 | 16 | 1 | 2\n",
                )
                archive.writestr(
                    "sim_results/local/slice0/local_mse4_rdata.log",
                    "[101] INFO: slice start (cycle=0, start_idx=1)\n"
                    "120 | 0 | 0 | 110 | 0x00000000000000000000000000000000\n",
                )
                archive.writestr(
                    "sim_results/local/slice0/local_mse4_wdata.log",
                    "[101] INFO: slice start (cycle=0, start_idx=1)\n",
                )
                archive.writestr(
                    "sim_results/local_old/slice0/local_mse4_req.log",
                    "[10001] INFO: slice start (cycle=0, start_idx=1)\n",
                )

            clean_report, _ = analyze_hardware_server_trace_zip(
                clean_archive_path, package, preflight
            )
            self.assertEqual(
                clean_report["runtime"]["local_slice_execution"]["status"],
                "trace_ends_after_clean_output_rmw_before_write_data",
            )
            self.assertEqual(clean_report["first_failure"]["stage"], "slice_output_write_data")
            self.assertEqual(clean_report["archive"]["selected_local_trace_namespace"], "local")
            self.assertEqual(clean_report["archive"]["other_local_trace_namespaces"], ["local_old"])


if __name__ == "__main__":
    unittest.main()
