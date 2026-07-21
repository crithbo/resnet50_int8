from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools.build_ndp_server_overlay import (
    OBSERVATION_COMPLETION_NO_WAVE,
    _audit_overlay_zip,
    _completion_stage_records,
    _sca_payload_references,
    _sca_runtime_transfers,
    build_overlay,
)


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v6"
ZIP = OVERLAY.with_suffix(".zip")
OVERLAY_V7 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v7"
ZIP_V7 = OVERLAY_V7.with_suffix(".zip")
OVERLAY_V7R1 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v7r1"
ZIP_V7R1 = OVERLAY_V7R1.with_suffix(".zip")
OVERLAY_V7R2 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v7r2"
ZIP_V7R2 = OVERLAY_V7R2.with_suffix(".zip")
OVERLAY_V9 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v9"
ZIP_V9 = OVERLAY_V9.with_suffix(".zip")
OVERLAY_V10 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10"
ZIP_V10 = OVERLAY_V10.with_suffix(".zip")
OVERLAY_V10R1 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r1"
ZIP_V10R1 = OVERLAY_V10R1.with_suffix(".zip")
OVERLAY_V10R2 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r2"
ZIP_V10R2 = OVERLAY_V10R2.with_suffix(".zip")
OVERLAY_V10R3 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r3"
ZIP_V10R3 = OVERLAY_V10R3.with_suffix(".zip")
OVERLAY_V10R4 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r4"
ZIP_V10R4 = OVERLAY_V10R4.with_suffix(".zip")
OVERLAY_V10R5 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r5"
ZIP_V10R5 = OVERLAY_V10R5.with_suffix(".zip")
OVERLAY_V10R6 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r6"
ZIP_V10R6 = OVERLAY_V10R6.with_suffix(".zip")
OVERLAY_V10R7 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r7"
ZIP_V10R7 = OVERLAY_V10R7.with_suffix(".zip")
OVERLAY_V10R8 = ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v10r8"
ZIP_V10R8 = OVERLAY_V10R8.with_suffix(".zip")
OVERLAY_V14 = ROOT / "artifacts/w5/hwop-0004-00/v14/server_overlay"
ZIP_V14 = ROOT / "artifacts/w5/hwop-0004-00/v14/server_overlay.zip"
OVERLAY_V19 = ROOT / "artifacts/w5/hwop-0004-00/v19/server_overlay"
ZIP_V19 = ROOT / "artifacts/w5/hwop-0004-00/v19/server_overlay.zip"
APPROVED_TB_SHA256 = (
    "52fb1c9e132b8a4b3bf3ff2700cdb8ce5021d4971118276ff5a02bfe2ec351d3"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _make_minimal_completion_package(package: Path) -> None:
    (package / "install").mkdir(parents=True)
    (package / "install/input.txt").write_text(
        "0" * 128 + "\n", encoding="utf-8", newline="\n"
    )
    _write_json(
        package / "manifest.json",
        {
            "freeze_id": "unit-test-freeze",
            "freeze_manifest_sha256": "f" * 64,
            "runtime_operators": [
                {"operator_id": "op0", "slice_mask": "0x1"}
            ],
        },
    )
    _write_json(
        package / "runner_contract.json",
        {
            "execution": {
                "completion_gate": {
                    "expected_runtime_stage_count": 1,
                    "expected_runtime_sequence": ["op0"],
                }
            },
            "preload": {
                "sca_cfg": {
                    "immutable_tb_parser_abi": {"validated_transfer_count": 1}
                }
            },
        },
    )
    _write_json(package / "dump_contract.json", {})
    _write_json(
        package / "sca_cfg.json",
        {
            "Repeat_Num": 1,
            "Payload": {"base_addr": "0x00000000", "path": "install/input.txt"},
        },
    )
    _write_json(
        package / "sca_cfg_D.json",
        {
            "Output": {
                "base_addr": "0x00001000",
                "length": 1,
                "path": "install/hwop-test/output.txt",
            }
        },
    )


class NdpServerOverlayTests(unittest.TestCase):
    def test_builder_rejects_existing_zip_companions_before_package_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "server_overlay"
            for companion in (output.with_suffix(".zip"), Path(f"{output}.zip.sha256")):
                companion.write_bytes(b"existing\n")
                with mock.patch(
                    "tools.build_ndp_server_overlay.validate_conv_hardware_execplan_package"
                ) as validator:
                    with self.assertRaisesRegex(FileExistsError, "overlay companion"):
                        build_overlay(
                            root / "package",
                            output,
                            "hwop-0004-00-vnext",
                            observation=OBSERVATION_COMPLETION_NO_WAVE,
                        )
                    validator.assert_not_called()
                companion.unlink()

    def test_fixed_completion_runner_has_clock_phase_and_return_guards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp_root = Path(temp_text)
            package = temp_root / "package"
            output = temp_root / "overlay"
            _make_minimal_completion_package(package)
            runner_contract = json.loads(
                (package / "runner_contract.json").read_text(encoding="utf-8")
            )
            completion_gate = runner_contract["execution"]["completion_gate"]
            completion_gate.update(
                {
                    "expected_testbench_repeat_num": 1,
                    "testbench_observer_mode": (
                        "fixed_slice0_start_slice1_finish"
                    ),
                    "testbench_observer": {
                        "mode": "fixed_slice0_start_slice1_finish",
                        "repeat_num": 1,
                        "runtime_stage_count": 1,
                    },
                }
            )
            _write_json(package / "runner_contract.json", runner_contract)
            with mock.patch(
                "tools.build_ndp_server_overlay."
                "validate_conv_hardware_execplan_package",
                return_value={
                    "status": "hardware_execplan_package_validated",
                    "checked_file_count": 6,
                },
            ):
                manifest = build_overlay(
                    package,
                    output,
                    "hwop-test-fixed-vnext",
                    observation=OBSERVATION_COMPLETION_NO_WAVE,
                )

            runner_path = output / "NDP_copy01/RUN_SERVER_VNEXT.sh"
            runner = runner_path.read_text(encoding="utf-8")
            command_gate_start = runner.index("missing_server_commands=()")
            command_gate_end = runner.index(
                "# A run ID owns exactly one canonical return directory/archive"
            )
            command_gate = runner[command_gate_start:command_gate_end]
            self.assertIn("exit 20", command_gate)
            self.assertNotIn("emit_preflight_failure", command_gate)
            for required in (
                "server_entrypoint_missing",
                "record_server_entrypoint_provenance()",
                "phase_watchdog()",
                "validate_ordered_progress()",
                'phase_timeout_status="not_timed_out"',
                'archive_timeout="1h"',
                "diagnostic_allowlist.tsv",
                '"return_archive_policy": "bounded_exact_set_allowlist_v2"',
                "runtime_log_sink_count",
                "return_file_contract.tsv",
                "run_command_contract_sha256",
                "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING",
                "RESERVED_AXI_CLOCK_FORCE_FAILED",
            ):
                self.assertIn(required, runner)
            command_contracts = list(output.rglob("*_run_argv.tsv"))
            self.assertEqual(len(command_contracts), 1)
            command_arguments = command_contracts[0].read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertIn("DUMP_VCD=0", command_arguments)
            self.assertIn(
                "VCS_EXTRA_OPTS=-debug_access+all +define+BANK_FRAME_LOG_SLICE_START_ONLY",
                command_arguments,
            )
            self.assertNotIn("sim", command_arguments)
            self.assertTrue(any(value.endswith("_sim_no_archive") for value in command_arguments))
            self.assertNotIn(
                'cp -a sim_results "${return_root}/"',
                runner,
            )
            self.assertIn(
                'copy_runtime_diagnostic_bounded "gexec2slice/slice_all/gexec2slice.log"',
                runner,
            )
            self.assertEqual(
                manifest["bank_frame_logging_policy"],
                "slice_start_only_plus_runtime_devnull_sinks",
            )
            self.assertEqual(
                manifest["reserved_clock_validation"],
                "force_and_low_high_toggle_proof",
            )
            self.assertEqual(
                manifest["return_archive_policy"],
                "bounded_exact_set_allowlist_v2",
            )
            self.assertEqual(manifest["phase_stall_watchdog"]["poll_seconds"], 30)
            self.assertEqual(
                manifest["phase_stall_watchdog"]["progress_policy"],
                "complete_line_snapshot_final_revalidation_v2",
            )

            tcl_paths = list(output.rglob("*_reserved_axi_clock.tcl"))
            self.assertEqual(len(tcl_paths), 1)
            tcl = tcl_paths[0].read_text(encoding="utf-8")
            for required in (
                "catch {force $reserved_clock_path",
                "set reserved_clock_low [get $reserved_clock_path]",
                "set reserved_clock_high [get $reserved_clock_path]",
                "RESERVED_AXI_CLOCK_FORCE_FAILED no_toggle",
                "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING",
            ):
                self.assertIn(required, tcl)
            self.assertNotIn('echo "RESERVED_AXI_CLOCK_FORCE_APPLIED"', tcl)

            bash_path = shutil.which("bash")
            if bash_path is None:
                for candidate in (
                    Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
                    Path(r"C:\Program Files\Git\bin\bash.exe"),
                ):
                    if candidate.is_file():
                        bash_path = str(candidate)
                        break
            if bash_path is not None:
                syntax = subprocess.run(
                    [
                        bash_path,
                        "-lc",
                        'bash -n "$1"',
                        "runner-syntax",
                        runner_path.as_posix(),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(syntax.returncode, 0, syntax.stderr)
                function_start = runner.index("capture_complete_console_snapshot() {")
                function_end = runner.index(
                    '\nrunner_phase="runtime"', function_start
                )
                function_text = runner[function_start:function_end]
                probe_root = temp_root / "phase-probe"
                (probe_root / "install").mkdir(parents=True)
                probe_script = temp_root / "probe_phase_watchdog.sh"
                probe_script.write_text(
                    "#!/usr/bin/env bash\n"
                    "set -uo pipefail\n"
                    f'install_root="{probe_root.as_posix()}"\n'
                    f'console_log="{(temp_root / "console.log").as_posix()}"\n'
                    f'complete_console_snapshot="{(temp_root / "console-complete.log").as_posix()}"\n'
                    f'readback_contract="{(temp_root / "readback.tsv").as_posix()}"\n'
                    f'phase_progress_log="{(temp_root / "phase_progress.tsv").as_posix()}"\n'
                    f'phase_timeout_record="{(temp_root / "phase_timeout.tsv").as_posix()}"\n'
                    f'phase_watchdog_done_record="{(temp_root / "phase_done.tsv").as_posix()}"\n'
                    "testbench_observer_mode=fixed_slice0_start_slice1_finish\n"
                    "expected_preload_count=1\n"
                    "expected_repeat_num=1\n"
                    "expected_stage_count=1\n"
                    "expected_region_count=1\n"
                    "preload_stall_timeout_seconds=1\n"
                    "first_start_stall_timeout_seconds=1\n"
                    "compute_stall_timeout_seconds=1\n"
                    "readback_stall_timeout_seconds=1\n"
                    "completion_exit_stall_timeout_seconds=1\n"
                    "phase_poll_seconds=1\n"
                    "inspect_runtime_log_budget() { printf '0\\n'; }\n"
                    f'readback_live_validation_state="{(temp_root / "readback-live.tsv").as_posix()}"\n'
                    ": > \"${console_log}\"\n"
                    ": > \"${readback_contract}\"\n"
                    ": > \"${phase_progress_log}\"\n"
                    ": > \"${readback_live_validation_state}\"\n"
                    f"{function_text}"
                    "sleep 10 &\n"
                    "probe_pid=$!\n"
                    "set +e\n"
                    "phase_watchdog \"${probe_pid}\"\n"
                    "probe_status=$?\n"
                    "wait \"${probe_pid}\" 2>/dev/null\n"
                    "exit \"${probe_status}\"\n",
                    encoding="utf-8",
                    newline="\n",
                )
                stalled = subprocess.run(
                    [
                        bash_path,
                        "-lc",
                        'bash "$1"',
                        "phase-watchdog",
                        probe_script.as_posix(),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(stalled.returncode, 70, stalled.stderr)
                timeout_fields = (temp_root / "phase_timeout.tsv").read_text(
                    encoding="utf-8"
                ).split("\t")
                self.assertEqual(timeout_fields[:2], ["preload", "passes=0 loads=0"])

    def test_generated_runner_lf_gate_counts_raw_cr_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp_root = Path(temp_text)
            package = temp_root / "package"
            output = temp_root / "overlay"
            _make_minimal_completion_package(package)
            with mock.patch(
                "tools.build_ndp_server_overlay."
                "validate_conv_hardware_execplan_package",
                return_value={
                    "status": "hardware_execplan_package_validated",
                    "checked_file_count": 6,
                },
            ):
                build_overlay(
                    package,
                    output,
                    "hwop-test-lf-gate",
                    observation=OBSERVATION_COMPLETION_NO_WAVE,
                )

            runner_paths = list((output / "NDP_copy01").glob("RUN_SERVER_*.sh"))
            self.assertEqual(len(runner_paths), 1)
            runner_path = runner_paths[0]
            runner_text = runner_path.read_text(encoding="utf-8")
            self.assertIn("od -An -v -t x1", runner_text)
            self.assertIn('$field_idx == "0d"', runner_text)
            self.assertNotIn(b"\r", runner_path.read_bytes())
            function_start = runner_text.index("check_lf_text_file() {")
            function_end = runner_text.index("\n}\n", function_start) + 3
            function_text = runner_text[function_start:function_end]

            bash_path = shutil.which("bash")
            if bash_path is None:
                for candidate in (
                    Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
                    Path(r"C:\Program Files\Git\bin\bash.exe"),
                ):
                    if candidate.is_file():
                        bash_path = str(candidate)
                        break
            if bash_path is None:
                self.skipTest("bash is unavailable for the runner byte-gate test")
            syntax = subprocess.run(
                [bash_path, "-n", runner_path.as_posix()],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(syntax.returncode, 0, syntax.stderr)

            probe_script = temp_root / "probe_runner_lf_gate.sh"
            probe_script.write_bytes(
                (
                    "#!/usr/bin/env bash\n"
                    "set -uo pipefail\n"
                    "emit_preflight_failure() {\n"
                    "  printf 'reason=%s detail=%s\\n' \"$1\" \"$2\" >&2\n"
                    "  return 23\n"
                    "}\n"
                    f"{function_text}"
                    "check_lf_text_file \"$1\"\n"
                ).encode("utf-8")
            )
            lf_sample = temp_root / "lf.txt"
            cr_sample = temp_root / "cr.txt"
            lf_sample.write_bytes(b"a\nb\n")
            cr_sample.write_bytes(b"a\r\nb\n")
            clean = subprocess.run(
                [
                    bash_path,
                    "-lc",
                    'bash "$1" "$2"',
                    "runner-lf-gate",
                    probe_script.as_posix(),
                    lf_sample.as_posix(),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            rejected = subprocess.run(
                [
                    bash_path,
                    "-lc",
                    'bash "$1" "$2"',
                    "runner-lf-gate",
                    probe_script.as_posix(),
                    cr_sample.as_posix(),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(clean.returncode, 0, clean.stderr)
            self.assertEqual(rejected.returncode, 23, rejected.stderr)
            self.assertIn("cr_byte_count=1", rejected.stderr)

    def test_zip_text_audit_rejects_crlf_with_precise_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            archive_path = Path(temp_text) / "overlay.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("NDP_copy01/launch.sh", b"#!/bin/bash\r\n")
            with self.assertRaisesRegex(
                ValueError,
                r"NDP_copy01/launch\.sh, cr_byte_count=1",
            ):
                _audit_overlay_zip(
                    archive_path,
                    expected_paths={"NDP_copy01/launch.sh"},
                    text_paths={"NDP_copy01/launch.sh"},
                )

    def test_completion_stage_contract_is_ordered_and_mask_exact(self) -> None:
        sequence = ["op.accumulate", "op.requant"]
        runner = {
            "execution": {
                "completion_gate": {
                    "expected_runtime_stage_count": 2,
                    "expected_runtime_sequence": sequence,
                }
            }
        }
        manifest = {
            "runtime_operators": [
                {"operator_id": sequence[0], "slice_mask": "0xff"},
                {"operator_id": sequence[1], "slice_mask": "0x1000000"},
            ]
        }
        self.assertEqual(
            _completion_stage_records(manifest, runner),
            [
                (0, "op.accumulate", "0x00000FF"),
                (1, "op.requant", "0x1000000"),
            ],
        )

        reordered = dict(manifest)
        reordered["runtime_operators"] = list(
            reversed(manifest["runtime_operators"])
        )
        with self.assertRaisesRegex(ValueError, "operator order"):
            _completion_stage_records(reordered, runner)

        bad_mask = {
            "runtime_operators": [
                manifest["runtime_operators"][0],
                {"operator_id": sequence[1], "slice_mask": "0x10000000"},
            ]
        }
        with self.assertRaisesRegex(ValueError, "mask is invalid"):
            _completion_stage_records(bad_mask, runner)

    def test_nested_sca_head_is_a_runtime_transfer_and_all_payloads_are_bound(self) -> None:
        sca = {
            "Repeat_Num": 2,
            "ExecutionPlan": {
                "base_addr": "0x00000FF0",
                "path": "install/full.txt",
                "chunked_transport": {
                    "base_addr": "0x00000FF0",
                    "path": "install/head.txt",
                    "semantic_path": "install/full.txt",
                },
            },
            "ExecutionPlan__axi4_tail": {
                "base_addr": "0x00001000",
                "path": "install/tail.txt",
                "semantic_path": "install/full.txt",
            },
        }
        self.assertEqual(
            _sca_runtime_transfers(sca),
            [
                ("ExecutionPlan", "install/head.txt"),
                ("ExecutionPlan__axi4_tail", "install/tail.txt"),
            ],
        )
        references = _sca_payload_references(sca)
        self.assertIn(("ExecutionPlan.path", "install/full.txt"), references)
        self.assertIn(
            ("ExecutionPlan.chunked_transport.path", "install/head.txt"),
            references,
        )
        self.assertIn(
            ("ExecutionPlan__axi4_tail.path", "install/tail.txt"), references
        )
        self.assertEqual(
            sum(path == "install/full.txt" for _, path in references), 3
        )

    def test_completion_overlay_records_only_readable_server_entrypoints_without_packaging_rtl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp_root = Path(temp_text)
            package = temp_root / "package"
            output = temp_root / "overlay"
            _make_minimal_completion_package(package)
            preflight = {
                "status": "hardware_execplan_package_validated",
                "checked_file_count": 6,
            }
            with mock.patch(
                "tools.build_ndp_server_overlay."
                "validate_conv_hardware_execplan_package",
                return_value=preflight,
            ) as validate:
                report = build_overlay(
                    package,
                    output,
                    "hwop-test-vnext",
                    observation=OBSERVATION_COMPLETION_NO_WAVE,
                    expected_rtl_revision="1" * 40,
                    expected_server_testbench_sha256=APPROVED_TB_SHA256.upper(),
                )

            validate.assert_called_once_with(package.resolve())
            self.assertTrue(report["formal_acceptance_ready"])
            self.assertEqual(report["rtl_files_included"], 0)
            self.assertFalse(report["versioned_testbench_included"])
            attestation = report["immutable_testbench_capability_attestation"]
            self.assertEqual(
                attestation["identity_policy"],
                "logical_entrypoints_unpinned_source_provenance",
            )
            self.assertFalse(attestation["prestart_source_hash_required"])

            runtime_root = (
                output
                / "NDP_copy01/install/cfg_pkg/hwop-test-vnext"
            )
            identity = json.loads(
                (runtime_root / "metadata/runtime_identity.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(identity["formal_acceptance_ready"])
            self.assertEqual(
                identity["immutable_testbench_capability_attestation"], attestation
            )
            self.assertEqual(
                identity["testbench"],
                {
                    "path": "tb_NDP_Top_new_phy.sv",
                    "source": "existing_server_file_not_in_overlay",
                    "identity_policy": (
                        "record_actual_hash_without_prestart_comparison"
                    ),
                },
            )
            self.assertEqual(
                identity["server_source_policy"]["mode"],
                "readable_logical_entrypoints_with_nonblocking_provenance",
            )
            self.assertFalse(
                identity["server_source_policy"]["content_hash_required"]
            )
            self.assertEqual(
                identity["server_source_policy"]["actual_hash_inventory_required"],
                "entrypoints_and_DIR_HOME",
            )
            self.assertEqual(
                identity["server_source_policy"][
                    "include_directory_validation_required"
                ],
                False,
            )
            self.assertFalse(
                identity["server_source_policy"][
                    "external_vendor_include_tree_equivalence_required"
                ]
            )
            self.assertFalse(
                identity["server_source_policy"][
                    "physical_source_path_inside_server_root_required"
                ]
            )

            launch_manifests = list(
                (runtime_root / "metadata").glob("launch_manifest.*.tsv")
            )
            launch_identities = list(
                (runtime_root / "metadata").glob("launch_identity.*.json")
            )
            self.assertEqual(len(launch_manifests), 1)
            self.assertEqual(len(launch_identities), 1)
            for content_addressed in (*launch_manifests, *launch_identities):
                self.assertEqual(content_addressed.name.split(".")[1], _sha256(content_addressed))
            manifest_rows = launch_manifests[0].read_text(encoding="utf-8").splitlines()
            self.assertTrue(manifest_rows)
            self.assertTrue(all(len(row.split("\t")) == 5 for row in manifest_rows))
            self.assertFalse(any("tb_NDP_Top_new_phy.sv" in row for row in manifest_rows))

            runner = (output / "NDP_copy01/RUN_SERVER_VNEXT.sh").read_text(
                encoding="utf-8"
            )
            for required in (
                'wall_timeout="24h"',
                "server_entrypoint_missing",
                "Makefile.tb_NDP_Top_new_phy",
                "tb_NDP_Top_new_phy.sv",
                "rtl/filelists/NDP_Top_phy_filelist.f",
                "record_server_entrypoint_provenance",
                "server_source_inventory",
                "physical:",
                "missing_server_commands=()",
                'command -v "${required_command}"',
                "effective_failure_reason",
                "testbench_sha256=$(sha256sum tb_NDP_Top_new_phy.sv",
                "launch_manifest.",
                "PASS: Continuous transfer completed successfully",
                "Repeat_Num",
                "readback-region",
                "timeout --signal=TERM --kill-after=5m",
            ):
                self.assertIn(required, runner)
            for removed_scan in (
                "git diff",
                "git ls-files",
                "--others",
                "skip-worktree",
                "assume-unchanged",
                "git rev-parse",
                "sha256sum --check",
                "server_rtl_identity_mismatch",
                "immutable_testbench_hash_mismatch",
                "validate_active_filelist_recursive",
                "validated_external_include_count",
                "server_make_effective_command_mismatch",
                "testbench_continuous_transfer_burst_capability_mismatch",
            ):
                self.assertNotIn(removed_scan, runner)
            self.assertNotIn("git ", runner)

            generated_files = [path for path in output.rglob("*") if path.is_file()]
            self.assertFalse(
                any(path.suffix.lower() in {".v", ".sv"} for path in generated_files)
            )
            with zipfile.ZipFile(output.with_suffix(".zip")) as archive:
                infos = archive.infolist()
                self.assertFalse(
                    any(name.lower().endswith((".v", ".sv")) for name in archive.namelist())
                )
                self.assertTrue(
                    all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos)
                )
                self.assertTrue(all(info.create_system == 3 for info in infos))
                self.assertTrue(
                    all((info.external_attr >> 16) & 0o777 == 0o644 for info in infos)
                )

    def test_completion_overlay_rejects_packaged_testbench_before_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp_root = Path(temp_text)
            with mock.patch(
                "tools.build_ndp_server_overlay."
                "validate_conv_hardware_execplan_package"
            ) as validate:
                with self.assertRaisesRegex(ValueError, "must not include or replace"):
                    build_overlay(
                        temp_root / "missing-package",
                        temp_root / "packaged-overlay",
                        "hwop-test-vnext",
                        observation=OBSERVATION_COMPLETION_NO_WAVE,
                        testbench=ROOT / "NDP_copy01/tb_NDP_Top_new_phy.sv",
                        expected_rtl_revision="1" * 40,
                        expected_server_testbench_sha256=APPROVED_TB_SHA256,
                    )
            validate.assert_not_called()

    @unittest.skipUnless(OVERLAY_V9.is_dir() and ZIP_V9.is_file(), "historical v9 artifact was intentionally removed")
    def test_v9_is_one_command_natural_completion_without_rtl_or_waveform(self) -> None:
        manifest = json.loads(
            (OVERLAY_V9 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["observation_mode"], "natural_completion_no_waveform")
        self.assertTrue(manifest["natural_completion_required"])
        self.assertEqual(manifest["expected_runtime_stage_count"], 11)
        self.assertIsNone(manifest["waveform"])
        self.assertIsNone(manifest["signal_path_list"])
        self.assertEqual(manifest["rtl_files_included"], 0)
        files = [item["path"] for item in manifest["files"]]
        self.assertFalse(any(path.endswith((".v", ".sv", ".tcl")) for path in files))
        self.assertIn("NDP_copy01/RUN_SERVER_V9.sh", files)

        runner_path = OVERLAY_V9 / "NDP_copy01/RUN_SERVER_V9.sh"
        runner = runner_path.read_text(encoding="utf-8")
        readme = (OVERLAY_V9 / "README_SERVER_V9.txt").read_text(encoding="utf-8")
        self.assertIn("bash RUN_SERVER_V9.sh", readme)
        self.assertIn("DUMP_FSDB=0 TB_DUMP_FSDB=0", runner)
        self.assertIn("sim_results_${revision}.zip", runner)
        self.assertNotIn("SIM_TIME=", runner)
        self.assertNotIn("-ucli", runner)
        self.assertNotIn("VCS_EXTRA_OPTS", runner)
        self.assertNotIn(b"\r\n", runner_path.read_bytes())
        with zipfile.ZipFile(ZIP_V9) as archive:
            names = archive.namelist()
        self.assertTrue(names)
        self.assertTrue(all("\\" not in name for name in names))
        self.assertFalse(any(name.endswith((".v", ".sv", ".tcl")) for name in names))

    @unittest.skipUnless(OVERLAY_V10.is_dir() and ZIP_V10.is_file(), "historical v10 artifact was intentionally removed")
    def test_v10_is_formal_completion_overlay_bound_to_server_entrypoints(self) -> None:
        manifest = json.loads(
            (OVERLAY_V10 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["status"],
            "runtime_only_ndp_server_overlay_ready_formal_acceptance_ready",
        )
        self.assertTrue(manifest["formal_acceptance_ready"])
        self.assertEqual(manifest["expected_runtime_stage_count"], 11)
        self.assertIsNone(manifest["rtl_source_provenance"])
        self.assertEqual(
            manifest["server_source_policy"]["mode"],
            "entrypoint_only_unpinned_server_sources",
        )
        self.assertFalse(manifest["server_source_policy"]["content_hash_required"])
        self.assertIsNone(manifest["testbench_source_provenance_sha256"])
        self.assertEqual(manifest["rtl_files_included"], 0)
        self.assertEqual(manifest["design_rtl_files_included"], 0)
        self.assertFalse(manifest["versioned_testbench_included"])
        files = [item["path"] for item in manifest["files"]]
        self.assertFalse(any(path.endswith((".v", ".sv", ".tcl")) for path in files))
        with zipfile.ZipFile(ZIP_V10) as archive:
            names = archive.namelist()
        self.assertTrue(names)
        self.assertTrue(all("\\" not in name for name in names))
        self.assertFalse(any(name.endswith((".v", ".sv", ".tcl")) for name in names))
        sidecar = Path(f"{ZIP_V10}.sha256")
        expected_sha, expected_name = sidecar.read_text(encoding="utf-8").split()
        self.assertEqual(expected_name, ZIP_V10.name)
        self.assertEqual(_sha256(ZIP_V10), expected_sha)

    @unittest.skipUnless(OVERLAY_V10R1.is_dir() and ZIP_V10R1.is_file(), "historical v10r1 artifact was intentionally removed")
    def test_v10r1_drives_reserved_clock_and_fences_the_legacy_observer(self) -> None:
        manifest = json.loads(
            (OVERLAY_V10R1 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["observation_mode"],
            "legacy_fixed_pair_completion_ucli_reserved_clock_no_waveform",
        )
        self.assertEqual(manifest["expected_runtime_stage_count"], 11)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(
            manifest["testbench_observer_mode"],
            "fixed_slice0_start_slice1_finish",
        )
        self.assertEqual(manifest["rtl_files_included"], 0)
        files = [item["path"] for item in manifest["files"]]
        self.assertFalse(any(path.endswith((".v", ".sv")) for path in files))
        self.assertTrue(any(path.endswith("_reserved_axi_clock.tcl") for path in files))

        runner_path = OVERLAY_V10R1 / "NDP_copy01/RUN_SERVER_V10R1.sh"
        runner = runner_path.read_text(encoding="utf-8")
        self.assertIn("rm -rf sim_results run/sim_results run/csrc", runner)
        self.assertIn('vcs_extra_opts="-debug_access+all"', runner)
        self.assertIn('sim_extra_opts="-ucli -i ${reserved_clock_tcl}"', runner)
        self.assertIn('expected_repeat_num=5', runner)
        self.assertNotIn(b"\r\n", runner_path.read_bytes())

        tcl_paths = list(OVERLAY_V10R1.rglob("*_reserved_axi_clock.tcl"))
        self.assertEqual(len(tcl_paths), 1)
        tcl = tcl_paths[0].read_text(encoding="utf-8")
        self.assertIn(
            "force tb_NDP_Top_new_phy.u_NDP_Top_new.m_axi_reserved_clk "
            "0 0ns, 1 1.25ns -repeat 2.5ns",
            tcl,
        )
        self.assertEqual(tcl.splitlines()[-1], "run")
        self.assertNotIn(b"\r\n", tcl_paths[0].read_bytes())

        with zipfile.ZipFile(ZIP_V10R1) as archive:
            names = archive.namelist()
        self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))
        sidecar = Path(f"{ZIP_V10R1}.sha256")
        expected_sha, expected_name = sidecar.read_text(encoding="utf-8").split()
        self.assertEqual(expected_name, ZIP_V10R1.name)
        self.assertEqual(_sha256(ZIP_V10R1), expected_sha)

    @unittest.skipUnless(OVERLAY_V10R2.is_dir() and ZIP_V10R2.is_file(), "historical v10r2 artifact was intentionally removed")
    def test_v10r2_is_lf_only_in_directory_and_zip(self) -> None:
        manifest = json.loads(
            (OVERLAY_V10R2 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["expected_runtime_stage_count"], 11)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(manifest["rtl_files_included"], 0)
        self.assertEqual(manifest["design_rtl_files_included"], 0)
        self.assertFalse(manifest["versioned_testbench_included"])
        text_contract = manifest["text_file_contract"]
        self.assertEqual(text_contract["line_ending"], "lf")
        self.assertFalse(text_contract["carriage_return_byte_allowed"])
        self.assertEqual(text_contract["paths"], sorted(text_contract["paths"]))
        for relative in text_contract["paths"]:
            self.assertNotIn(
                b"\r", (OVERLAY_V10R2 / relative).read_bytes(), relative
            )

        runner_path = OVERLAY_V10R2 / "NDP_copy01/RUN_SERVER_V10R2.sh"
        runner = runner_path.read_text(encoding="utf-8")
        self.assertIn("invalid_launch_text_line_endings", runner)
        self.assertIn("cr_byte_count=", runner)
        self.assertNotIn("invalid_reserved_clock_ucli", runner)

        with zipfile.ZipFile(ZIP_V10R2) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            for relative in text_contract["paths"]:
                self.assertNotIn(b"\r", archive.read(relative), relative)
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))
        sidecar = Path(f"{ZIP_V10R2}.sha256")
        expected_sha, expected_name = sidecar.read_text(encoding="utf-8").split()
        self.assertEqual(expected_name, ZIP_V10R2.name)
        self.assertEqual(_sha256(ZIP_V10R2), expected_sha)

    @unittest.skipUnless(OVERLAY_V10R3.is_dir() and ZIP_V10R3.is_file(), "historical v10r3 artifact was intentionally removed")
    def test_v10r3_is_the_lf_only_release_with_a_byte_exact_runner_gate(self) -> None:
        manifest_path = OVERLAY_V10R3 / "OVERLAY_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["expected_runtime_stage_count"], 11)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(manifest["rtl_files_included"], 0)
        self.assertEqual(manifest["design_rtl_files_included"], 0)
        self.assertFalse(manifest["versioned_testbench_included"])
        text_contract = manifest["text_file_contract"]
        self.assertEqual(text_contract["line_ending"], "lf")
        self.assertFalse(text_contract["carriage_return_byte_allowed"])
        self.assertEqual(text_contract["paths"], sorted(text_contract["paths"]))
        for relative in text_contract["paths"]:
            self.assertNotIn(b"\r", (OVERLAY_V10R3 / relative).read_bytes(), relative)

        runner_path = OVERLAY_V10R3 / "NDP_copy01/RUN_SERVER_V10R3.sh"
        runner = runner_path.read_text(encoding="utf-8")
        self.assertIn("invalid_launch_text_line_endings", runner)
        self.assertIn("od -An -v -t x1", runner)
        self.assertIn('$field_idx == "0d"', runner)
        self.assertNotIn("invalid_reserved_clock_ucli", runner)
        self.assertNotIn(b"\r", runner_path.read_bytes())

        with zipfile.ZipFile(ZIP_V10R3) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(
                set(names),
                {
                    path.relative_to(OVERLAY_V10R3).as_posix()
                    for path in OVERLAY_V10R3.rglob("*")
                    if path.is_file()
                },
            )
            for relative in text_contract["paths"]:
                self.assertNotIn(b"\r", archive.read(relative), relative)
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))
        sidecar = Path(f"{ZIP_V10R3}.sha256")
        expected_sha, expected_name = sidecar.read_text(encoding="utf-8").split()
        self.assertEqual(expected_name, ZIP_V10R3.name)
        self.assertEqual(_sha256(ZIP_V10R3), expected_sha)

    @unittest.skipUnless(OVERLAY_V10R4.is_dir() and ZIP_V10R4.is_file(), "historical v10r4 artifact was intentionally removed")
    def test_v10r4_is_the_rebuild_v9_bound_release(self) -> None:
        manifest_path = OVERLAY_V10R4 / "OVERLAY_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["expected_runtime_stage_count"], 11)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(manifest["rtl_files_included"], 0)
        self.assertEqual(manifest["design_rtl_files_included"], 0)
        self.assertFalse(manifest["versioned_testbench_included"])

        install_root = (
            OVERLAY_V10R4
            / "NDP_copy01/install/cfg_pkg/hwop-0004-00-v10r4/install/cfg_pkg"
        )
        accumulate = install_root / "conv_1x1_real_bitstream_128b.bin"
        lines = accumulate.read_text(encoding="ascii").splitlines()
        self.assertEqual(len(lines), 28)
        self.assertTrue(all(len(line) == 128 and set(line) <= {"0", "1"} for line in lines))
        self.assertEqual(
            _sha256(accumulate),
            "44fb091f0013dbccfc376154ea53d074d08bc945e3d276810579766e8c45fa8f",
        )

        runner_path = OVERLAY_V10R4 / "NDP_copy01/RUN_SERVER_V10R4.sh"
        runner = runner_path.read_text(encoding="utf-8")
        self.assertIn("invalid_launch_text_line_endings", runner)
        self.assertIn("od -An -v -t x1", runner)
        self.assertNotIn("git ", runner)
        self.assertNotIn(b"\r", runner_path.read_bytes())

        with zipfile.ZipFile(ZIP_V10R4) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(
                set(names),
                {
                    path.relative_to(OVERLAY_V10R4).as_posix()
                    for path in OVERLAY_V10R4.rglob("*")
                    if path.is_file()
                },
            )
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))
            self.assertEqual(archive.read(accumulate.relative_to(OVERLAY_V10R4).as_posix()), accumulate.read_bytes())
        sidecar = Path(f"{ZIP_V10R4}.sha256")
        expected_sha, expected_name = sidecar.read_text(encoding="utf-8").split()
        self.assertEqual(expected_name, ZIP_V10R4.name)
        self.assertEqual(_sha256(ZIP_V10R4), expected_sha)

    @unittest.skipUnless(OVERLAY_V10R5.is_dir() and ZIP_V10R5.is_file(), "historical v10r5 artifact was intentionally removed")
    def test_v10r5_closes_final_stage_binding_and_cleanup_gaps(self) -> None:
        manifest_path = OVERLAY_V10R5 / "OVERLAY_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["expected_runtime_stage_count"], 12)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(manifest["expected_return_archive"], "run/sim_results_v10r5.zip")
        observer = manifest["testbench_observer"]
        self.assertEqual(observer["final_stage_slice_mask"], "0x0000002")
        self.assertTrue(observer["final_stage_is_finish_slice_only"])
        self.assertTrue(
            observer[
                "all_other_final_shard_slices_barrier_completed_before_final_stage"
            ]
        )
        self.assertTrue(observer["readback_after_final_finish_is_full_mask_completion_safe"])
        self.assertEqual(manifest["runtime_stage_contract"]["stage_count"], 12)
        self.assertEqual(manifest["readback_region_contract"]["region_count"], 168)
        for key in (
            "freeze_id",
            "freeze_manifest_sha256",
            "package_manifest_sha256",
        ):
            self.assertIsInstance(manifest[key], str)
            self.assertEqual(len(manifest[key]), 64)
        for key in (
            "runner",
            "runtime_stage_contract",
            "readback_region_contract",
            "launch_file_contract",
            "launch_identity",
            "runtime_identity",
        ):
            self.assertEqual(len(manifest[key]["sha256"]), 64)

        runner_path = OVERLAY_V10R5 / "NDP_copy01/RUN_SERVER_V10R5.sh"
        runner = runner_path.read_text(encoding="utf-8")
        self.assertNotIn("rm -rf sim_results run/sim_results", runner)
        self.assertIn('archive_root="run/archive/preexisting-${revision}-${archive_epoch}"', runner)
        self.assertIn('mv -- sim_results "${archive_root}/sim_results"', runner)
        self.assertIn(
            "rm -rf run/csrc run/${revision}_return run/sim_results_${revision}.zip",
            runner,
        )
        self.assertNotIn(b"\r", runner_path.read_bytes())
        self.assertFalse(
            any(
                path.suffix.lower() in {".v", ".sv"}
                for path in OVERLAY_V10R5.rglob("*")
                if path.is_file()
            )
        )
        with zipfile.ZipFile(ZIP_V10R5) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(
                set(names),
                {
                    path.relative_to(OVERLAY_V10R5).as_posix()
                    for path in OVERLAY_V10R5.rglob("*")
                    if path.is_file()
                },
            )
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))
        sidecar = Path(f"{ZIP_V10R5}.sha256")
        expected_sha, expected_name = sidecar.read_text(encoding="utf-8").split()
        self.assertEqual(expected_name, ZIP_V10R5.name)
        self.assertEqual(_sha256(ZIP_V10R5), expected_sha)

    @unittest.skipUnless(OVERLAY_V10R6.is_dir() and ZIP_V10R6.is_file(), "historical v10r6 artifact was intentionally removed")
    def test_v10r6_is_the_guarded_minimal_return_release(self) -> None:
        manifest_path = OVERLAY_V10R6 / "OVERLAY_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["expected_runtime_stage_count"], 12)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(
            manifest["expected_return_archive"], "run/sim_results_v10r6.zip"
        )
        self.assertEqual(
            manifest["bank_frame_logging_policy"],
            "slice_start_only_compile_define",
        )
        self.assertEqual(
            manifest["reserved_clock_validation"],
            "force_and_low_high_toggle_proof",
        )
        self.assertEqual(
            manifest["return_archive_policy"],
            "minimal_diagnostic_allowlist_v1",
        )
        self.assertEqual(manifest["phase_stall_watchdog"]["poll_seconds"], 60)
        self.assertEqual(manifest["rtl_files_included"], 0)

        runner_path = OVERLAY_V10R6 / "NDP_copy01/RUN_SERVER_V10R6.sh"
        runner = runner_path.read_text(encoding="utf-8")
        for required in (
            "+define+BANK_FRAME_LOG_SLICE_START_ONLY",
            "phase_watchdog()",
            "phase_stall_timeout",
            "diagnostic_allowlist.tsv",
            'archive_timeout="1h"',
            "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING",
        ):
            self.assertIn(required, runner)
        self.assertNotIn('cp -a sim_results "${return_root}/"', runner)
        self.assertNotIn("DUMP_FSDB=1", runner)
        self.assertNotIn(b"\r", runner_path.read_bytes())

        tcl_paths = list(OVERLAY_V10R6.rglob("*_reserved_axi_clock.tcl"))
        self.assertEqual(len(tcl_paths), 1)
        tcl = tcl_paths[0].read_text(encoding="utf-8")
        self.assertIn("catch {force $reserved_clock_path", tcl)
        self.assertIn("set reserved_clock_low [get $reserved_clock_path]", tcl)
        self.assertIn("set reserved_clock_high [get $reserved_clock_path]", tcl)
        self.assertIn("RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING", tcl)

        try:
            import tkinter
        except ImportError:
            tkinter = None
        if tkinter is not None:
            try:
                tkinter.Tcl()
            except tkinter.TclError:
                tkinter = None
        if tkinter is not None:
            def evaluate_clock_tcl(samples: list[str], *, fail_force: bool = False) -> list[str]:
                interpreter = tkinter.Tcl()
                messages: list[str] = []
                remaining = list(samples)

                def echo(*values: str) -> str:
                    messages.append(" ".join(values))
                    return ""

                def force(*_values: str) -> str:
                    if fail_force:
                        raise tkinter.TclError("forced unit-test failure")
                    return ""

                def get_signal(*_values: str) -> str:
                    if not remaining:
                        raise tkinter.TclError("missing unit-test sample")
                    return remaining.pop(0)

                interpreter.createcommand("echo", echo)
                interpreter.createcommand("force", force)
                interpreter.createcommand("get", get_signal)
                interpreter.createcommand("run", lambda *_values: "")
                interpreter.createcommand("quit", lambda *_values: "")
                interpreter.eval(tcl)
                return messages

            toggling = evaluate_clock_tcl(["0", "1"])
            self.assertEqual(
                toggling.count("RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING"),
                1,
            )
            self.assertFalse(
                any(message.startswith("RESERVED_AXI_CLOCK_FORCE_FAILED") for message in toggling)
            )
            static = evaluate_clock_tcl(["0", "0"])
            self.assertIn("RESERVED_AXI_CLOCK_FORCE_FAILED no_toggle", static)
            self.assertNotIn("RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING", static)
            force_failed = evaluate_clock_tcl([], fail_force=True)
            self.assertIn("RESERVED_AXI_CLOCK_FORCE_FAILED force", force_failed)
            self.assertNotIn(
                "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING", force_failed
            )

        accumulate = next(
            OVERLAY_V10R6.rglob("conv_1x1_real_bitstream_128b.bin")
        )
        lines = accumulate.read_text(encoding="ascii").splitlines()
        self.assertEqual(len(lines), 28)
        self.assertEqual(
            _sha256(accumulate),
            "44fb091f0013dbccfc376154ea53d074d08bc945e3d276810579766e8c45fa8f",
        )
        self.assertFalse(
            any(
                path.suffix.lower() in {".v", ".sv"}
                for path in OVERLAY_V10R6.rglob("*")
                if path.is_file()
            )
        )
        with zipfile.ZipFile(ZIP_V10R6) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(
                set(names),
                {
                    path.relative_to(OVERLAY_V10R6).as_posix()
                    for path in OVERLAY_V10R6.rglob("*")
                    if path.is_file()
                },
            )
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))
        sidecar = Path(f"{ZIP_V10R6}.sha256")
        expected_sha, expected_name = sidecar.read_text(encoding="utf-8").split()
        self.assertEqual(expected_name, ZIP_V10R6.name)
        self.assertEqual(_sha256(ZIP_V10R6), expected_sha)

    @unittest.skipUnless(OVERLAY_V10R7.is_dir() and ZIP_V10R7.is_file(), "historical v10r7 artifact was intentionally removed")
    def test_v10r7_closes_non_hdl_runtime_chain_gaps(self) -> None:
        manifest = json.loads(
            (OVERLAY_V10R7 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["expected_runtime_stage_count"], 12)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(
            manifest["expected_return_archive"], "run/sim_results_v10r7.zip"
        )
        self.assertEqual(
            manifest["bank_frame_logging_policy"],
            "slice_start_only_plus_runtime_devnull_sinks",
        )
        self.assertEqual(
            manifest["return_archive_policy"],
            "bounded_exact_set_allowlist_v2",
        )
        self.assertEqual(
            manifest["make_archive_policy"], "runner_no_archive_target_v1"
        )
        self.assertEqual(
            manifest["phase_stall_watchdog"]["progress_policy"],
            "ordered_marker_state_machine_v1",
        )
        self.assertEqual(manifest["phase_stall_watchdog"]["poll_seconds"], 30)
        self.assertEqual(manifest["rtl_files_included"], 0)

        runner_path = OVERLAY_V10R7 / "NDP_copy01/RUN_SERVER_V10R7.sh"
        runner = runner_path.read_text(encoding="utf-8")
        for required in (
            "validate_ordered_progress()",
            "expected_diagnostic_sink_count=1037",
            "audited_high_frequency_paths_to_devnull_v1",
            "copy_runtime_diagnostic_bounded",
            "return_file_contract.tsv",
            "required_runtime_log_patterns=(",
            "testbench_log_path_capability_missing",
            "sim_results/bank_frame/slice%0d/bank%0d_mc_rdata.log",
            'phase_watchdog_exit_status="${raw_phase_watchdog_exit_status}"',
            "watchdog_abnormal_exit_or_missing_done_sentinel",
        ):
            self.assertIn(required, runner)
        self.assertNotIn("make -f Makefile.tb_NDP_Top_new_phy compile sim", runner)
        self.assertNotIn('cp -a sim_results "${return_root}/"', runner)
        self.assertNotIn('copy_runtime_diagnostic "', runner)
        self.assertNotIn('kill -TERM "${phase_watchdog_pid}"', runner)
        self.assertLess(
            runner.index("server_entrypoint_missing"),
            runner.index("server_make_no_archive_capability_missing"),
        )

        readme = (OVERLAY_V10R7 / "README_SERVER_V10R7.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("15 runtime-log path patterns", readme)
        self.assertIn("1037 temporary", readme)
        self.assertIn("separate no-archive simulation target", readme)
        self.assertIn("exact-set/size/SHA contract", readme)

        command_contract = next(OVERLAY_V10R7.rglob("v10r7_run_argv.tsv"))
        command_arguments = command_contract.read_text(encoding="utf-8").splitlines()
        self.assertEqual(command_arguments[:4], ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "-f"])
        self.assertEqual(command_arguments[5:7], ["compile", "v10r7_sim_no_archive"])
        self.assertNotIn("sim", command_arguments)
        self.assertNotIn("archive_sim_results", command_arguments)

        make_override = next(OVERLAY_V10R7.rglob("v10r7_runtime_no_archive.mk"))
        make_text = make_override.read_text(encoding="utf-8")
        self.assertIn("v10r7_sim_no_archive: $(SIMV)", make_text)
        self.assertIn("$(SIMV) $(SIM_OPTS) $(SIM_EXTRA_OPTS)", make_text)
        self.assertNotIn("archive_sim_results:", make_text)
        self.assertNotRegex(make_text, r"(?m)^(?:compile|sim):")
        continuation_lines = [line for line in make_text.splitlines() if line.endswith("\\")]
        self.assertEqual(len(continuation_lines), 3)
        self.assertTrue(all(not line.endswith("\\\\") for line in continuation_lines))

        launch_identity = json.loads(next(OVERLAY_V10R7.rglob("launch_identity.*.json")).read_text(encoding="utf-8"))
        self.assertEqual(
            launch_identity["immutable_testbench_capability_attestation"]["schema_version"],
            "resnet50-server-entrypoint-capability-policy-0.4",
        )
        self.assertEqual(launch_identity["runtime_log_sink_policy"]["expected_sink_count"], 1037)

        accumulate = next(OVERLAY_V10R7.rglob("conv_1x1_real_bitstream_128b.bin"))
        self.assertEqual(len(accumulate.read_text(encoding="ascii").splitlines()), 28)
        self.assertEqual(
            _sha256(accumulate),
            "44fb091f0013dbccfc376154ea53d074d08bc945e3d276810579766e8c45fa8f",
        )
        self.assertFalse(any(path.is_symlink() for path in OVERLAY_V10R7.rglob("*")))
        self.assertFalse(
            any(
                path.suffix.lower() in {".v", ".sv"}
                for path in OVERLAY_V10R7.rglob("*")
                if path.is_file()
            )
        )
        with zipfile.ZipFile(ZIP_V10R7) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(
                set(names),
                {
                    path.relative_to(OVERLAY_V10R7).as_posix()
                    for path in OVERLAY_V10R7.rglob("*")
                    if path.is_file()
                },
            )
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))

    @unittest.skipUnless(OVERLAY_V10R7.is_dir(), "historical v10r7 artifact was intentionally removed")
    def test_v10r7_ordered_progress_rejects_malformed_marker_sequences(self) -> None:
        bash_path = shutil.which("bash")
        if bash_path is None:
            for candidate in (
                Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
                Path(r"C:\Program Files\Git\bin\bash.exe"),
            ):
                if candidate.is_file():
                    bash_path = str(candidate)
                    break
        if bash_path is None:
            self.skipTest("bash is unavailable for ordered-progress behavior tests")

        runner = (OVERLAY_V10R7 / "NDP_copy01/RUN_SERVER_V10R7.sh").read_text(
            encoding="utf-8"
        )
        function_start = runner.index("validate_ordered_progress() {")
        function_end = runner.index("\n}\n\nphase_watchdog()", function_start) + 3
        function_text = runner[function_start:function_end]
        probe = (
            "PATH=/usr/bin:$PATH\n"
            + function_text
            + "\nconsole_log=\"$1\"\n"
            + "expected_preload_count=2\n"
            + "expected_repeat_num=2\n"
            + "expected_stage_count=12\n"
            + "testbench_observer_mode=fixed_slice0_start_slice1_finish\n"
            + "validate_ordered_progress\n"
        )
        valid_prefix = [
            "[1] JSON: Loading matrix[0]: a -> 0x0",
            "[2] *** PASS: Continuous transfer completed successfully!",
            "[3] JSON: Loading matrix[1]: b -> 0x10",
            "[4] *** PASS: Continuous transfer completed successfully!",
        ]
        cases = {
            "valid": (
                valid_prefix
                + [
                    "[5] INFO: slice start",
                    "[6] INFO: slice completed after 10 cycles",
                    "[7] INFO: slice start",
                    "[8] INFO: slice completed after 10 cycles",
                    "Simulation completed successfully!",
                ],
                0,
                "valid",
            ),
            "preload_skip": (
                ["[1] JSON: Loading matrix[1]: b -> 0x10"],
                1,
                "preload_index_or_order_violation",
            ),
            "duplicate_pass": (
                valid_prefix[:2] + [valid_prefix[1]],
                1,
                "preload_pass_pair_violation",
            ),
            "duplicate_start": (
                valid_prefix
                + ["[5] INFO: slice start", "[6] INFO: slice start"],
                1,
                "observer_start_order_or_limit_violation",
            ),
            "finish_first": (
                valid_prefix + ["[5] INFO: slice completed after 10 cycles"],
                1,
                "observer_finish_order_or_limit_violation",
            ),
            "early_completion": (
                valid_prefix + ["Simulation completed successfully!"],
                1,
                "natural_completion_before_runtime_contract",
            ),
        }
        with tempfile.TemporaryDirectory() as temp_text:
            temp_root = Path(temp_text)
            for name, (lines, expected_status, expected_output) in cases.items():
                console_path = temp_root / f"{name}.log"
                console_path.write_text(
                    "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
                )
                completed = subprocess.run(
                    [bash_path, "-c", probe, "ordered-progress", console_path.as_posix()],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, expected_status, name)
                self.assertIn(expected_output, completed.stdout, name)

    @unittest.skipUnless(
        OVERLAY_V19.is_dir() and ZIP_V19.is_file(),
        "current v19 artifact has not been generated yet",
    )
    def test_current_v19_artifact_binds_identity_before_cleanup_and_runtime_guards(
        self,
    ) -> None:
        manifest = json.loads(
            (OVERLAY_V19 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["expected_return_archive"],
            "run/sim_results_v19_<SERVER_RUN_ID>.zip",
        )
        self.assertEqual(manifest["expected_runtime_stage_count"], 12)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(
            manifest["runtime_log_sink_policy"]["policy"],
            "audited_sinks_unknown_log_guard_v2",
        )
        self.assertEqual(
            manifest["runtime_log_sink_policy"]["runtime_total_size_limit_bytes"],
            1073741824,
        )
        runner_path = OVERLAY_V19 / "NDP_copy01/RUN_SERVER_V19.sh"
        runner = runner_path.read_text(encoding="utf-8")
        run_id_index = runner.index('requested_server_run_id="${SERVER_RUN_ID:-run1}"')
        identity_index = runner.index("actual_runner_hash_line=$(sha256sum")
        cleanup_index = runner.index(
            "# A run ID owns exactly one canonical return directory/archive"
        )
        trap_index = runner.index("trap unexpected_runner_error ERR")
        command_gate_index = runner.index("missing_server_commands=()")
        self.assertLess(run_id_index, identity_index)
        self.assertLess(identity_index, cleanup_index)
        self.assertLess(identity_index, trap_index)
        self.assertLess(trap_index, command_gate_index)
        self.assertLess(command_gate_index, cleanup_index)
        self.assertNotIn("mkdir ", runner[:identity_index])
        self.assertNotIn("rm ", runner[:identity_index])
        for required in (
            "inspect_runtime_log_budget()",
            "unknown_runtime_log_file",
            "runtime_log_total_size_exceeded",
            "readback_live_validation_state",
            "inspect_readback_progress final",
            "static_install_path_is_expected()",
            "static_install_unexpected_file",
            "unset MAKEFLAGS MAKEFILES GNUMAKEFLAGS MFLAGS MAKELEVEL",
        ):
            self.assertIn(required, runner)
        self.assertNotIn("git ", runner.lower())

        runtime_identity = json.loads(
            next(OVERLAY_V19.rglob("runtime_identity.json")).read_text(
                encoding="utf-8"
            )
        )
        runner_identity_path = OVERLAY_V19 / runtime_identity["runner_identity"]["path"]
        self.assertEqual(
            runner_identity_path.read_text(encoding="ascii"),
            f"{_sha256(runner_path)}  {runner_path.name}\n",
        )
        self.assertEqual(
            runtime_identity["make_environment_policy"],
            "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch",
        )
        self.assertEqual(
            runtime_identity["static_install_exact_set_policy"],
            "launch_manifest_plus_four_content_addressed_identity_files",
        )
        with zipfile.ZipFile(ZIP_V19) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(
                set(names),
                {
                    path.relative_to(OVERLAY_V19).as_posix()
                    for path in OVERLAY_V19.rglob("*")
                    if path.is_file()
                },
            )
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))

    @unittest.skipUnless(
        OVERLAY_V14.is_dir() and ZIP_V14.is_file(),
        "revoked v14 generated overlay has been retired",
    )
    def test_v14_remains_an_immutable_revoked_diagnostic_artifact(self) -> None:
        manifest = json.loads(
            (OVERLAY_V14 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["expected_runtime_stage_count"], 12)
        self.assertEqual(manifest["expected_testbench_repeat_num"], 5)
        self.assertEqual(
            manifest["expected_return_archive"],
            "run/sim_results_v14_<SERVER_RUN_ID>.zip",
        )
        self.assertEqual(
            manifest["required_formal_return_archives"],
            ["run/sim_results_v14_run1.zip", "run/sim_results_v14_run2.zip"],
        )
        self.assertEqual(
            manifest["phase_stall_watchdog"]["progress_policy"],
            "complete_line_snapshot_final_revalidation_v2",
        )
        self.assertEqual(
            manifest["phase_stall_watchdog"]["readback_progress_policy"],
            "exact_regular_file_exact_size_v1",
        )
        runner_path = OVERLAY_V14 / "NDP_copy01/RUN_SERVER_V14.sh"
        runner = runner_path.read_text(encoding="utf-8")
        for required in (
            "capture_complete_console_snapshot()",
            "inspect_readback_progress()",
            'validate_ordered_progress "${console_log}"',
            "unterminated_final_console_record",
            "readback_file_oversize",
            "unexpected_readback_file",
            "runner_self_identity_mismatch",
            "server_make_effective_command_mismatch",
            "server_topology_capability_mismatch",
            "unexpected_runner_error",
            "invalid_server_run_id",
            "validate_active_filelist_recursive",
            "server_source_inventory",
            "validated_external_include_count",
            "testbench_continuous_transfer_burst_capability_mismatch",
            "emit_runtime_failure 14",
            "emit_runtime_failure 15",
            "emit_runtime_failure 11",
        ):
            self.assertIn(required, runner)
        self.assertNotIn(
            'cp -a "${install_root}/metadata" "${return_root}/config/"', runner
        )
        self.assertIn("for approved_metadata_file in", runner)

        command_contract = next(OVERLAY_V14.rglob("v14_run_argv.tsv"))
        command_arguments = command_contract.read_text(encoding="utf-8").splitlines()
        for argument in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"):
            self.assertEqual(command_arguments.count(argument), 1)
        self.assertEqual(command_arguments[5:7], ["compile", "v14_sim_no_archive"])

        runtime_identity = json.loads(
            next(OVERLAY_V14.rglob("runtime_identity.json")).read_text(
                encoding="utf-8"
            )
        )
        runner_identity_path = OVERLAY_V14 / runtime_identity["runner_identity"]["path"]
        self.assertEqual(
            _sha256(runner_identity_path), runtime_identity["runner_identity"]["sha256"]
        )
        self.assertEqual(
            runner_identity_path.read_text(encoding="ascii"),
            f"{_sha256(runner_path)}  {runner_path.name}\n",
        )
        capability = runtime_identity["immutable_testbench_capability_attestation"]
        self.assertEqual(
            capability["schema_version"],
            "resnet50-server-entrypoint-capability-policy-0.6",
        )
        self.assertTrue(capability["runner_self_identity_required"])
        self.assertTrue(capability["return_config_exact_set_required"])
        self.assertEqual(capability["required_topology_capability"]["SLICE_NUM"], 28)
        self.assertTrue(capability["recursive_filelist_validation_required"])
        self.assertTrue(capability["include_directory_validation_required"])
        self.assertTrue(
            capability["external_vendor_include_tree_equivalence_required"]
        )
        self.assertEqual(
            capability["continuous_transfer_burst_contract"]["max_burst_beats"],
            256,
        )

        readme = (OVERLAY_V14 / "README_SERVER_V14.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("sha256sum -c server_overlay.zip.sha256", readme)
        self.assertIn("Git is neither required nor used on the server", readme)
        self.assertIn("Do not run git commands", readme)
        self.assertIn("${DIR_HOME}/Hardware/IP/bus/nic_cgra_0310", readme)
        self.assertIn("byte-identical", readme)
        self.assertIn("SERVER_RUN_ID=run1 bash RUN_SERVER_V14.sh", readme)
        self.assertIn("SERVER_RUN_ID=run2 bash RUN_SERVER_V14.sh", readme)
        accumulate = next(OVERLAY_V14.rglob("conv_1x1_real_bitstream_128b.bin"))
        self.assertEqual(len(accumulate.read_text(encoding="ascii").splitlines()), 28)
        self.assertEqual(
            _sha256(accumulate),
            "44fb091f0013dbccfc376154ea53d074d08bc945e3d276810579766e8c45fa8f",
        )
        with zipfile.ZipFile(ZIP_V14) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            self.assertEqual(
                set(names),
                {
                    path.relative_to(OVERLAY_V14).as_posix()
                    for path in OVERLAY_V14.rglob("*")
                    if path.is_file()
                },
            )
            self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))

    def test_current_v19_live_snapshot_ignores_partial_line_and_readback_requires_full_size(self) -> None:
        bash_path = shutil.which("bash")
        if bash_path is None:
            for candidate in (
                Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
                Path(r"C:\Program Files\Git\bin\bash.exe"),
            ):
                if candidate.is_file():
                    bash_path = str(candidate)
                    break
        if bash_path is None:
            self.skipTest("bash is unavailable for current v19 runner behavior tests")

        runner = (OVERLAY_V19 / "NDP_copy01/RUN_SERVER_V19.sh").read_text(
            encoding="utf-8"
        )
        snapshot_start = runner.index("capture_complete_console_snapshot() {")
        snapshot_end = runner.index("\ninspect_readback_progress() {", snapshot_start)
        snapshot_functions = runner[snapshot_start:snapshot_end]
        readback_start = runner.index("readback_path_is_expected() {")
        readback_end = runner.index("\nphase_watchdog() {", readback_start)
        readback_function = runner[readback_start:readback_end]

        with tempfile.TemporaryDirectory() as temp_text:
            temp_root = Path(temp_text)
            console = temp_root / "console.log"
            snapshot = temp_root / "snapshot.log"
            console.write_bytes(
                b"[1] JSON: Loading matrix[0]: a\n"
                b"[2] PASS: Continuous transfer completed successfully\n"
                b"JSON: Loading matrix["
            )
            snapshot_probe = temp_root / "snapshot_probe.sh"
            snapshot_probe.write_text(
                "#!/usr/bin/env bash\nset -uo pipefail\n"
                f'console_log="{console.as_posix()}"\n'
                f'complete_console_snapshot="{snapshot.as_posix()}"\n'
                "expected_preload_count=1\nexpected_repeat_num=1\n"
                "expected_stage_count=1\n"
                "testbench_observer_mode=fixed_slice0_start_slice1_finish\n"
                + snapshot_functions
                + "\ncapture_complete_console_snapshot\n"
                + "validate_ordered_progress \"${complete_console_snapshot}\"\n",
                encoding="utf-8",
                newline="\n",
            )
            clean = subprocess.run(
                [bash_path, "-lc", 'bash "$1"', "snapshot-probe", snapshot_probe.as_posix()],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(clean.returncode, 0, clean.stderr)
            with console.open("ab") as stream:
                stream.write(b"1]\n")
            rejected = subprocess.run(
                [bash_path, "-lc", 'bash "$1"', "snapshot-probe", snapshot_probe.as_posix()],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("preload_index_or_order_violation", rejected.stdout)

            install_root = temp_root / "runtime"
            expected_file = install_root / "install/hwop-test/output.txt"
            expected_file.parent.mkdir(parents=True)
            readback_contract = temp_root / "readback.tsv"
            readback_contract.write_text(
                f"{expected_file.as_posix()}\t2\n", encoding="utf-8", newline="\n"
            )
            readback_live_state = temp_root / "readback_live_validated.tsv"
            readback_probe = temp_root / "readback_probe.sh"
            readback_probe.write_text(
                "#!/usr/bin/env bash\nset -uo pipefail\n"
                f'install_root="{install_root.as_posix()}"\n'
                f'readback_contract="{readback_contract.as_posix()}"\n'
                f'readback_live_validation_state="{readback_live_state.as_posix()}"\n'
                ': > "${readback_live_validation_state}"\n'
                + readback_function
                + "\ninspect_readback_progress\n",
                encoding="utf-8",
                newline="\n",
            )
            one_line = b"0" * 128 + b"\n"
            expected_file.write_bytes(one_line)
            partial = subprocess.run(
                [bash_path, "-lc", 'bash "$1"', "readback-probe", readback_probe.as_posix()],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(partial.returncode, 0, partial.stderr)
            self.assertEqual(partial.stdout.strip(), "0")
            expected_file.write_bytes(one_line * 2)
            complete = subprocess.run(
                [bash_path, "-lc", 'bash "$1"', "readback-probe", readback_probe.as_posix()],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(complete.returncode, 0, complete.stderr)
            self.assertEqual(complete.stdout.strip(), "1")
            (expected_file.parent / "extra.txt").write_bytes(b"")
            unexpected = subprocess.run(
                [bash_path, "-lc", 'bash "$1"', "readback-probe", readback_probe.as_posix()],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(unexpected.returncode, 0)
            self.assertIn("unexpected_readback_file", unexpected.stdout)

    @unittest.skipUnless(OVERLAY.is_dir() and ZIP.is_file(), "historical v6 artifact was intentionally removed")
    def test_overlay_is_merge_only_and_contains_no_rtl(self) -> None:
        manifest = json.loads(
            (OVERLAY / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "runtime_only_ndp_server_overlay_ready")
        self.assertEqual(
            manifest["overlay_semantics"],
            "merge_only_do_not_replace_server_ndp_root",
        )
        files = [item["path"] for item in manifest["files"]]
        rtl = [path for path in files if path.endswith((".v", ".sv"))]
        self.assertEqual(rtl, [])
        self.assertEqual(manifest["rtl_files_included"], 0)
        self.assertEqual(
            manifest["observation_mode"],
            "existing_makefile_full_hierarchy_fsdb",
        )
        signal_text = (OVERLAY / "V6_FSDB_SIGNAL_PATHS.txt").read_text(
            encoding="utf-8"
        )
        for token in (
            "buf_src_id[5]",
            "sa_inport_group_in_tag",
            "sa_outport_group_out_tag",
            "array2arm_wtag[5]",
            "wr_data_chl_prepared_data_vld",
            "mse2mem_wdata_valid[4]",
        ):
            self.assertIn(token, signal_text)
        self.assertFalse(any("Bank_data/" in path for path in files))
        self.assertFalse(any("/source/" in path for path in files))
        self.assertEqual(manifest["sca_reference_count"], 348)
        for record in manifest["files"]:
            path = OVERLAY / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(path.stat().st_size, record["size_bytes"])
            self.assertEqual(_sha256(path), record["sha256"])

    @unittest.skipUnless(OVERLAY.is_dir() and ZIP.is_file(), "historical v6 artifact was intentionally removed")
    def test_relocated_sca_paths_exist_and_zip_uses_posix_merge_paths(self) -> None:
        sca = json.loads(
            (
                OVERLAY
                / "NDP_copy01/install/cfg_pkg/hwop-0004-00-v6/sca_cfg.json"
            ).read_text(encoding="utf-8")
        )
        paths = [
            value["path"]
            for value in sca.values()
            if isinstance(value, dict) and "path" in value
        ]
        self.assertTrue(paths)
        self.assertTrue(
            all(path.startswith("install/cfg_pkg/hwop-0004-00-v6/install/") for path in paths)
        )
        self.assertTrue(all((OVERLAY / "NDP_copy01" / path).is_file() for path in paths))
        with zipfile.ZipFile(ZIP) as archive:
            names = archive.namelist()
        self.assertTrue(names)
        self.assertTrue(all("\\" not in name for name in names))
        self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))

    @unittest.skipUnless(OVERLAY_V7R2.is_dir() and ZIP_V7R2.is_file(), "historical v7r2 artifact was intentionally removed")
    def test_v7r2_targeted_vpd_is_server_preflighted_and_contains_no_rtl(self) -> None:
        manifest = json.loads(
            (OVERLAY_V7R2 / "OVERLAY_MANIFEST.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["observation_mode"],
            "ucli_slice0_targeted_vpd_no_rtl_changes",
        )
        self.assertEqual(manifest["diagnostic_run_time"], "12ms")
        self.assertEqual(manifest["rtl_files_included"], 0)
        self.assertEqual(manifest["targeted_signal_count"], 19)
        self.assertEqual(manifest["server_text_encoding"], "utf-8_lf")
        self.assertEqual(manifest["ucli_stdin_mode"], "noninteractive_dev_null")
        files = [item["path"] for item in manifest["files"]]
        self.assertFalse(any(path.endswith((".v", ".sv")) for path in files))
        self.assertIn("NDP_copy01/RUN_SERVER_V7R2.sh", files)
        self.assertIn(
            "NDP_copy01/install/cfg_pkg/hwop-0004-00-v7r2/v7r2_diag.tcl",
            files,
        )
        for record in manifest["files"]:
            path = OVERLAY_V7R2 / record["path"]
            self.assertTrue(path.is_file(), record["path"])
            self.assertEqual(path.stat().st_size, record["size_bytes"])
            self.assertEqual(_sha256(path), record["sha256"])

        source_v7 = ROOT / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v7"
        installed_v7r2 = (
            OVERLAY_V7R2
            / "NDP_copy01/install/cfg_pkg/hwop-0004-00-v7r2/install"
        )
        for relative in (
            "cfg_pkg/conv_1x1_real_bitstream_128b.bin",
            "execplan.txt",
            "data/A/slice-00.txt",
        ):
            self.assertEqual(
                _sha256(source_v7 / "install" / relative),
                _sha256(installed_v7r2 / relative),
            )

        tcl = (
            OVERLAY_V7R2
            / "NDP_copy01/install/cfg_pkg/hwop-0004-00-v7r2/v7r2_diag.tcl"
        ).read_text(encoding="utf-8")
        self.assertEqual(tcl.count("dump -add "), 19)
        self.assertEqual(tcl.count("-fid VPD0"), 19)
        self.assertFalse(
            any(
                line.startswith("dump -add ") and "-fid VPD0" not in line
                for line in tcl.splitlines()
            )
        )
        self.assertIn("run 12ms", tcl)
        self.assertIn("run/sim_results/v7r2_diag.vpd", tcl)
        self.assertNotIn("fsdbDumpvars", tcl)
        self.assertNotIn("mse2mem_wdata[4]", tcl)
        self.assertIn("mse2mem_wdata_valid[4]", tcl)
        self.assertIn("mem2mse_wdata_ready[4]", tcl)

        runner_path = OVERLAY_V7R2 / "NDP_copy01/RUN_SERVER_V7R2.sh"
        runner = runner_path.read_text(encoding="utf-8")
        readme = (OVERLAY_V7R2 / "README_SERVER_V7R2.txt").read_text(
            encoding="utf-8"
        )
        self.assertIn("bash RUN_SERVER_V7R2.sh", readme)
        self.assertNotIn("chmod", readme)
        for token in (
            "DUMP_FSDB=0",
            "TB_DUMP_FSDB=0",
            "-debug_access+all -kdb",
            "-ucli -i ${diagnostic_tcl}",
            "expected_dump_count=19",
            "grep -c '^dump -add .* -fid VPD0$'",
            "</dev/null",
            "rm -rf sim_results run/sim_results",
            "sim_results_${revision}.zip",
        ):
            self.assertIn(token, runner)
        tcl_path = (
            OVERLAY_V7R2
            / "NDP_copy01/install/cfg_pkg/hwop-0004-00-v7r2/v7r2_diag.tcl"
        )
        self.assertNotIn(b"\r\n", runner_path.read_bytes())
        self.assertNotIn(b"\r\n", tcl_path.read_bytes())

        with zipfile.ZipFile(ZIP_V7R2) as archive:
            names = archive.namelist()
        self.assertTrue(names)
        self.assertTrue(all("\\" not in name for name in names))
        self.assertFalse(any(name.endswith((".v", ".sv")) for name in names))

    @unittest.skipUnless(
        (ROOT / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v6").is_dir()
        and (ROOT / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v7").is_dir(),
        "historical v6/v7 packages were intentionally removed",
    )
    def test_v7_keeps_v6_numeric_runtime_bytes(self) -> None:
        package_v6 = ROOT / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v6"
        package_v7 = ROOT / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v7"
        for relative in (
            "install/cfg_pkg/conv_1x1_real_bitstream_128b.bin",
            "install/execplan.txt",
            "Bank_data/slice00_Bank00_data.txt",
        ):
            self.assertEqual(_sha256(package_v6 / relative), _sha256(package_v7 / relative))
        freeze_v6 = json.loads(
            (
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze_v6/manifest.json"
            ).read_text(encoding="utf-8")
        )
        freeze_v7 = json.loads(
            (
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze_v7/manifest.json"
            ).read_text(encoding="utf-8")
        )
        self.assertNotEqual(freeze_v6["freeze_id"], freeze_v7["freeze_id"])
        self.assertEqual(freeze_v6["configs"], freeze_v7["configs"])
        self.assertEqual(freeze_v6["bitstreams"], freeze_v7["bitstreams"])


if __name__ == "__main__":
    unittest.main()
