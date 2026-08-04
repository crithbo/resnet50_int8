from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import numpy as np

from resnet50_pipeline.bitstream_binding import bitstream_text_identity
from resnet50_pipeline.conv_execplan_hardware import (
    ConvHardwareExecplanError,
    _verify_freeze,
    _insert_runtime_completion_barriers,
    _legacy_fixed_pair_observer_contract,
    _legacy_fixed_pair_requant_order,
    _parse_runtime_completion_console,
    _validate_package_text_contract,
    _validate_runtime_completion_barrier_contract,
    _validate_returned_config_file_set,
    _validate_immutable_tb_sca_parser_abi,
    assemble_conv_hardware_region_dump,
    compare_conv_hardware_bank_dump,
    generate_conv_hardware_execplan,
    validate_conv_hardware_execplan_package,
    validate_conv_hardware_repeated_region_returns,
    validate_conv_hardware_region_return,
)
from resnet50_pipeline.conv_execplan_transport import ConvExecplanTransportError
from resnet50_pipeline.conv_1x1_hardware_freeze import export_hardware_freeze
from resnet50_pipeline.hardware_simulation_frontend import prepare_hardware_simulation
from resnet50_pipeline.w5_conv_preflight import (
    W5ConvPreflightError,
    validate_conv_hardware_quantization_preconditions,
)
from tools.build_ndp_server_overlay import (
    OBSERVATION_COMPLETION_NO_WAVE,
    build_overlay,
)
from tools.generate_conv_hardware_execplan import _write_package_invariance_report


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ConvHardwareExecplanTest(unittest.TestCase):
    def test_numeric_invariance_revalidates_reference_and_candidate_bytes(self) -> None:
        source = (
            PROJECT_ROOT
            / "artifacts/w5/hwop-0004-00/v18/hardware_execplan_package"
        )
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            reference = temporary_root / "reference"
            candidate = temporary_root / "candidate"
            shutil.copytree(source, reference)
            shutil.copytree(source, candidate)
            report = _write_package_invariance_report(
                reference, candidate, temporary_root / "invariance.json"
            )
            self.assertEqual(
                report["schema_version"],
                "resnet50-package-numeric-invariance-0.3",
            )
            self.assertEqual(
                report["reference_validation_status"],
                "hardware_execplan_package_validated",
            )

            candidate_manifest_path = candidate / "manifest.json"
            original_candidate_manifest = candidate_manifest_path.read_bytes()
            candidate_manifest_object = json.loads(
                original_candidate_manifest.decode("utf-8")
            )
            candidate_manifest_path.write_text(
                json.dumps(
                    candidate_manifest_object,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            reformatted = _write_package_invariance_report(
                reference, candidate, temporary_root / "reformatted.json"
            )
            self.assertNotEqual(
                reformatted["reference_manifest_sha256"],
                reformatted["candidate_manifest_sha256"],
            )
            candidate_manifest_path.write_bytes(original_candidate_manifest)

            declared_path = json.loads(
                (reference / "manifest.json").read_text(encoding="utf-8")
            )["files"][0]["path"]
            damaged = reference / declared_path
            damaged.write_bytes(damaged.read_bytes() + b"damage")
            with self.assertRaises(ConvHardwareExecplanError):
                _write_package_invariance_report(
                    reference, candidate, temporary_root / "must-not-exist.json"
                )

    def test_revised_freeze_rejects_extra_files_and_tampered_id(self) -> None:
        source = PROJECT_ROOT / "artifacts/w5/hwop-0004-00/v14/hardware_freeze"
        with tempfile.TemporaryDirectory() as temporary:
            freeze = Path(temporary) / "freeze"
            shutil.copytree(source, freeze)
            (freeze / "stale-extra.bin").write_bytes(b"stale")
            with self.assertRaisesRegex(ConvHardwareExecplanError, "exact-set"):
                _verify_freeze(freeze, expected_node_id="node-0004")

            (freeze / "stale-extra.bin").unlink()
            manifest_path = freeze / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["freeze_id"] = "0" * 64
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(ConvHardwareExecplanError, "canonical manifest body"):
                _verify_freeze(freeze, expected_node_id="node-0004")

    def test_returned_config_file_set_rejects_unapproved_metadata(self) -> None:
        metadata_names = {
            "launch_file_contract": "launch_files.tsv",
            "launch_identity": "launch_identity.json",
            "runtime_make_override": "runtime.mk",
            "run_command_contract": "run_command.json",
            "runner_identity": "runner.sha256",
        }
        approved_identity = {
            key: {"path": f"install/hwop/metadata/{name}"}
            for key, name in metadata_names.items()
        }
        expected = {
            PurePosixPath("config/sca_cfg.json"),
            PurePosixPath("config/sca_cfg_D.json"),
            PurePosixPath("config/server_source_inventory.tsv"),
            PurePosixPath("config/metadata/manifest.json"),
            PurePosixPath("config/metadata/runner_contract.json"),
            PurePosixPath("config/metadata/dump_contract.json"),
            PurePosixPath("config/metadata/readback_regions.tsv"),
            PurePosixPath("config/metadata/expected_runtime_stages.tsv"),
            PurePosixPath("config/metadata/runtime_identity.json"),
            *(PurePosixPath("config/metadata") / name for name in metadata_names.values()),
        }
        actual = {relative: Path(relative.as_posix()) for relative in expected}
        _validate_returned_config_file_set(actual, approved_identity)

        extra = PurePosixPath("config/metadata/stale_extra_metadata.json")
        actual[extra] = Path(extra.as_posix())
        with self.assertRaisesRegex(
            ConvHardwareExecplanError,
            "returned config/metadata exact set differs",
        ):
            _validate_returned_config_file_set(actual, approved_identity)

    def test_package_text_contract_rejects_crlf_with_precise_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "manifest.json").write_bytes(b"{}\n")
            (root / "payload.txt").write_bytes(b"payload\r\n")
            contract = {
                "encoding": "utf-8_or_ascii",
                "line_ending": "lf",
                "carriage_return_byte_allowed": False,
                "paths": ["manifest.json", "payload.txt"],
            }
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                r"payload\.txt, cr_byte_count=1",
            ):
                _validate_package_text_contract(root, contract)

    def test_legacy_fixed_pair_schedule_ends_on_the_final_runtime_stage(self) -> None:
        shards = [
            {
                "shard_index": index,
                "local_half": index % 2,
                "selected_slices": selected,
            }
            for index, selected in enumerate(
                (
                    [0, 4, 8],
                    [0, 4, 8],
                    [2, 6, 10],
                    [2, 6, 10],
                    [3, 7, 11],
                    [3, 7, 11],
                    [1, 5, 9],
                    [1, 5, 9],
                )
            )
        ]
        ordered = _legacy_fixed_pair_requant_order(shards)
        self.assertEqual(
            [int(shard["shard_index"]) for shard in ordered],
            [0, 2, 3, 4, 5, 6, 1, 7, 7],
        )
        masks = [0x0FFFFFFF, 0x0FFFFFFF, 0x00000FF]
        masks.extend(
            sum(1 << int(value) for value in shard["selected_slices"])
            for shard in ordered
        )
        contract = _legacy_fixed_pair_observer_contract(
            [
                SimpleNamespace(
                    used_slices=mask,
                    attributes=(
                        dict(ordered[index - 3]) if index >= 3 else {}
                    ),
                )
                for index, mask in enumerate(masks)
            ]
        )
        self.assertEqual(contract["repeat_num"], 5)
        self.assertEqual(contract["final_pair_finishes_at_stage"], 11)
        self.assertEqual(contract["final_stage_slice_mask"], "0x0000002")
        self.assertTrue(contract["readback_after_final_finish_is_full_mask_completion_safe"])
        self.assertEqual(
            [
                (pair["slice0_start_stage"], pair["slice1_finish_stage"])
                for pair in contract["pairs"]
            ],
            [(0, 0), (1, 1), (2, 2), (3, 8), (9, 11)],
        )

    def test_fixed_observer_console_is_parsed_without_runtime_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            console = Path(temp_dir) / "console.log"
            valid = "\n".join(
                [
                    "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING",
                    "[1] JSON: Loading matrix[0]: install/a.txt -> 0x00000000",
                    "[2] *** PASS: Continuous transfer completed successfully!",
                    "[3] JSON: Loading matrix[1]: install/b.txt -> 0x00000010",
                    "[4] *** PASS: Continuous transfer completed successfully!",
                    "[10] INFO: slice start",
                    "[20] INFO: slice completed after 10 cycles",
                    "[30] INFO: slice start",
                    "[40] INFO: slice completed after 10 cycles",
                    "Simulation completed successfully!",
                    "Simulation exit status: 0",
                    "",
                ]
            )
            console.write_text(valid, encoding="utf-8", newline="\n")
            report = _parse_runtime_completion_console(
                console,
                expected_preload_transfer_count=2,
                expected_slice_masks=["0x1", "0x2", "0x2"],
                expected_simulator_exit_status=0,
                observer_contract={
                    "mode": "fixed_slice0_start_slice1_finish",
                    "repeat_num": 2,
                    "runtime_stage_count": 3,
                },
            )
            self.assertEqual(report["completed_runtime_stage_count"], 3)
            self.assertEqual(report["fixed_observer_pair_count"], 2)
            self.assertEqual(report["reserved_clock_force_marker_count"], 1)
            console.write_text(
                valid.replace("Loading matrix[1]", "Loading matrix[0]", 1),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError, "malformed/non-contiguous"
            ):
                _parse_runtime_completion_console(
                    console,
                    expected_preload_transfer_count=2,
                    expected_slice_masks=["0x1", "0x2", "0x2"],
                    expected_simulator_exit_status=0,
                    observer_contract={
                        "mode": "fixed_slice0_start_slice1_finish",
                        "repeat_num": 2,
                        "runtime_stage_count": 3,
                    },
                )
            console.write_text(
                valid.replace(
                    "Simulation completed successfully!\n",
                    "Simulation completed successfully!\nSimulation completed successfully!\n",
                ),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError, "exactly one natural-completion"
            ):
                _parse_runtime_completion_console(
                    console,
                    expected_preload_transfer_count=2,
                    expected_slice_masks=["0x1", "0x2", "0x2"],
                    expected_simulator_exit_status=0,
                    observer_contract={
                        "mode": "fixed_slice0_start_slice1_finish",
                        "repeat_num": 2,
                        "runtime_stage_count": 3,
                    },
                )

    def test_barrier_insertion_rejects_an_upstream_barrier(self) -> None:
        artifact = SimpleNamespace(
            commands=[(1 << 3) | 0b110],
            command_explanations=["unexpected upstream barrier"],
            metadata={},
        )
        operator = SimpleNamespace(op_id="fixture-op", used_slices=1)

        def artifact_factory(**values: object) -> SimpleNamespace:
            return SimpleNamespace(**values)

        with self.assertRaisesRegex(
            ConvHardwareExecplanError,
            "already contains a completion barrier",
        ):
            _insert_runtime_completion_barriers(
                {"ExecutionPlanArtifact": artifact_factory},
                artifact,
                [operator],
            )

    def test_hardware_quantization_precheck_is_fail_closed(self) -> None:
        valid = {
            "x_zero_point": np.asarray([0], dtype=np.uint8),
            "w_zero_point": np.zeros(64, dtype=np.int8),
        }
        validate_conv_hardware_quantization_preconditions(valid)

        invalid_x = dict(valid)
        invalid_x["x_zero_point"] = np.asarray([114], dtype=np.uint8)
        with self.assertRaisesRegex(W5ConvPreflightError, "x_zero_point=0"):
            validate_conv_hardware_quantization_preconditions(invalid_x)

        invalid_w = dict(valid)
        invalid_w["w_zero_point"] = np.asarray([0, -3], dtype=np.int8)
        with self.assertRaisesRegex(W5ConvPreflightError, "every w_zero_point=0"):
            validate_conv_hardware_quantization_preconditions(invalid_w)

    def test_frozen_node0004_generates_closed_hardware_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "hardware_execplan"
            report = generate_conv_hardware_execplan(
                PROJECT_ROOT,
                output,
                node_id="node-0004",
                freeze_root=(
                    PROJECT_ROOT / "artifacts/w5/hwop-0004-00/v20/hardware_freeze"
                ),
                execplan_request_path=(
                    PROJECT_ROOT
                    / "artifacts/w5/hwop-0004-00/v20/execplan_request.json"
                ),
                legacy_fixed_pair_observer=True,
            )
            checked = validate_conv_hardware_execplan_package(output)

            self.assertEqual(report["runtime_operator_count"], 12)
            self.assertEqual(report["bitstream_bindings"]["record_count"], 9)
            accumulate_binding = next(
                item
                for item in report["bitstream_bindings"]["records"]
                if item["binding_id"].endswith(".accumulate")
            )
            self.assertEqual(accumulate_binding["install"]["line_count"], 35)
            self.assertEqual(accumulate_binding["install"]["line_width_bits"], 128)
            self.assertEqual(
                accumulate_binding["install"]["logical_sha256"],
                "2d22ec7f94867752a3bd6abe70842402ab943dd6142492f1d1c183556aba405a",
            )
            self.assertEqual(report["instruction_metadata"]["load_config_count"], "12")
            self.assertEqual(report["instruction_metadata"]["start_comp_count"], "12")
            self.assertEqual(report["instruction_metadata"]["barrier_count"], "12")
            self.assertEqual(
                report["runtime_serialization"]["strategy"],
                "post_start_same_mask_barrier",
            )
            self.assertEqual(report["preloaded_input_count"], 252)
            self.assertEqual(report["preloaded_runtime_scratch_count"], 84)
            self.assertEqual(report["preloaded_golden_or_output_count"], 0)
            self.assertEqual(report["preload_transfer_segment_count"], 433)
            self.assertEqual(report["semantic_dump_region_count"], 84)
            self.assertEqual(report["sca_d_transfer_segment_count"], 168)
            self.assertEqual(report["bank_data_file_count"], 28)
            text_contract = report["text_file_contract"]
            self.assertEqual(text_contract["line_ending"], "lf")
            self.assertFalse(text_contract["carriage_return_byte_allowed"])
            self.assertEqual(
                checked["lf_text_file_count"], len(text_contract["paths"])
            )
            for relative in text_contract["paths"]:
                self.assertNotIn(b"\r", (output / relative).read_bytes(), relative)
            self.assertTrue((output / "runner_contract.json").is_file())
            self.assertTrue(report["address_translation"]["local_offsets_preserved"])
            self.assertEqual(
                report["runtime_io_bindings"][
                    "hwop-0004-00.accumulate-wave-0.input.A"
                ],
                "freeze/B (signed weight -> READ_STREAM0)",
            )
            self.assertEqual(
                report["runtime_io_bindings"][
                    "hwop-0004-00.accumulate-wave-0.input.B"
                ],
                "freeze/A local sample slot (unsigned activation -> READ_STREAM1)",
            )
            self.assertEqual(
                report["runtime_io_bindings"][
                    "hwop-0004-00.accumulate-wave-0.input.B'"
                ],
                "freeze/A same local sample slot (unsigned activation B-prime -> READ_STREAM2)",
            )
            waves = report["runtime_accumulate_waves"]
            self.assertEqual(
                [wave["slice_mask"] for wave in waves],
                ["0xFFFFFFF", "0xFFFFFFF", "0x00000FF"],
            )
            self.assertEqual(
                [wave["logical_samples"] for wave in waves],
                [
                    [0, 3, 6, 8, 10, 12, 14],
                    [1, 4, 7, 9, 11, 13, 15],
                    [2, 5],
                ],
            )
            self.assertEqual(
                [wave["activation_local_offset"] for wave in waves],
                [0, 200704, 401408],
            )
            self.assertEqual(
                [wave["p_local_offset"] for wave in waves],
                [603344, 804048, 1004752],
            )
            self.assertEqual(checked["status"], "hardware_execplan_package_validated")

            prepared = prepare_hardware_simulation(output)
            preparation = prepared.report()
            self.assertEqual(preparation["status"], "hardware_simulation_input_prepared")
            self.assertEqual(preparation["scope"], "transport_and_state_only_no_numeric_execution")
            self.assertEqual(preparation["command_count"], 767)
            self.assertEqual(preparation["runtime_stage_count"], 12)
            self.assertEqual(preparation["command_counts"]["clock_enable"], 1)
            self.assertEqual(preparation["command_counts"]["load_config"], 12)
            self.assertEqual(preparation["command_counts"]["write_reg"], 730)
            self.assertEqual(preparation["command_counts"]["start_comp"], 12)
            self.assertEqual(preparation["command_counts"]["barrier"], 12)
            start_and_barrier = [
                command
                for command in prepared.commands
                if command.kind in {"start_comp", "barrier"}
            ]
            self.assertEqual(
                [command.kind for command in start_and_barrier],
                [kind for _ in range(12) for kind in ("start_comp", "barrier")],
            )
            self.assertEqual(
                [
                    int(start_and_barrier[index].fields["slice_mask"])
                    for index in range(0, len(start_and_barrier), 2)
                ],
                [
                    int(start_and_barrier[index].fields["slice_mask"])
                    for index in range(1, len(start_and_barrier), 2)
                ],
            )
            self.assertEqual(
                preparation["runtime_stages"][0]["operator_type"],
                "resnet_qlinearconv_int32_accumulate",
            )
            self.assertEqual(
                preparation["runtime_stages"][3]["operator_type"],
                "resnet_qlinearconv_uint8_requant",
            )
            self.assertEqual(preparation["numeric_executor"]["status"], "not_run")

            freeze = PROJECT_ROOT / "artifacts/w5/hwop-0004-00/v20/hardware_freeze"
            accumulate = json.loads(
                (freeze / "configs/conv_1x1_real.json").read_text(encoding="utf-8")
            )
            self.assertEqual(accumulate["buffer_config"]["buffer5"]["dst_port"], 0)
            sca = json.loads((output / "sca_cfg.json").read_text(encoding="utf-8"))
            runner = json.loads(
                (output / "runner_contract.json").read_text(encoding="utf-8")
            )
            self.assertEqual(sca["Repeat_Num"], 5)
            self.assertEqual(
                sca["Repeat_Num"],
                runner["execution"]["completion_gate"]["expected_testbench_repeat_num"],
            )
            self.assertEqual(
                runner["execution"]["completion_gate"]["expected_runtime_stage_count"],
                12,
            )
            self.assertEqual(sca["Exec_Length"], 384)
            self.assertEqual(report["exec_128bit_line_count"], 384)
            self.assertEqual(
                runner["execution"]["exec_length_128bit_beats"],
                384,
            )
            self.assertEqual(
                runner["execution"]["completion_gate"][
                    "expected_completion_barrier_count"
                ],
                12,
            )
            self.assertEqual(
                runner["execution"]["completion_gate"]["completion_barrier_opcode"],
                "0b110",
            )

            execution = sca["ExecutionPlan"]
            self.assertNotIn("chunked_transport", execution)
            self.assertNotIn("ExecutionPlan__axi4_tail", sca)
            tampered_paths = [output / execution["path"]]
            original_barrier_package_bytes = {
                path: path.read_bytes() for path in tampered_paths
            }
            try:
                commands_without_barriers = [
                    (
                        command.raw
                        if command.kind != "barrier"
                        else (command.raw & ~0x7) | 0b111
                    )
                    for command in prepared.commands
                ]
                self.assertEqual(len(commands_without_barriers), 767)
                padded_commands = commands_without_barriers + (
                    [0] if len(commands_without_barriers) % 2 else []
                )
                barrierless_lines = [
                    f"{padded_commands[index + 1]:064b}"
                    f"{padded_commands[index]:064b}"
                    for index in range(0, len(padded_commands), 2)
                ]
                self.assertEqual(len(barrierless_lines), 384)

                def write_execplan_lines(path: Path, lines: list[str]) -> None:
                    path.write_text(
                        "\n".join(lines) + "\n",
                        encoding="ascii",
                        newline="\n",
                    )

                write_execplan_lines(output / execution["path"], barrierless_lines)
                with self.assertRaisesRegex(
                    ConvHardwareExecplanError,
                    "runtime completion barrier execplan is invalid",
                ):
                    _validate_runtime_completion_barrier_contract(
                        output, report, sca, runner
                    )
            finally:
                for path, payload in original_barrier_package_bytes.items():
                    path.write_bytes(payload)

            expected_rtl_revision = "1" * 40
            expected_server_testbench_sha256 = (
                "52fb1c9e132b8a4b3bf3ff2700cdb8ce5021d4971118276ff5a02bfe2ec351d3"
            )
            overlay = Path(temp_dir) / "server_overlay_vnext"
            overlay_report = build_overlay(
                output,
                overlay,
                "hwop-0004-00-vnext",
                observation=OBSERVATION_COMPLETION_NO_WAVE,
                expected_rtl_revision=expected_rtl_revision,
                expected_server_testbench_sha256=expected_server_testbench_sha256,
            )
            original_sca_text = (output / "sca_cfg.json").read_text(encoding="utf-8")
            tampered_sca = json.loads(original_sca_text)
            tampered_sca["Repeat_Num"] = 12
            (output / "sca_cfg.json").write_text(
                json.dumps(tampered_sca), encoding="utf-8", newline="\n"
            )
            with self.assertRaisesRegex(ValueError, "package file differs"):
                build_overlay(
                    output,
                    Path(temp_dir) / "tampered_overlay",
                    "hwop-0004-00-tampered",
                    observation=OBSERVATION_COMPLETION_NO_WAVE,
                    expected_rtl_revision=expected_rtl_revision,
                    expected_server_testbench_sha256=expected_server_testbench_sha256,
                )
            (output / "sca_cfg.json").write_text(
                original_sca_text, encoding="utf-8", newline="\n"
            )
            self.assertFalse(overlay_report["versioned_testbench_included"])
            self.assertEqual(overlay_report["design_rtl_files_included"], 0)
            self.assertEqual(overlay_report["expected_runtime_stage_count"], 12)
            self.assertFalse((overlay / "NDP_copy01/tb_NDP_Top_new_phy.sv").exists())
            self.assertFalse(
                any(
                    path.suffix.lower() in {".v", ".sv"}
                    for path in overlay.rglob("*")
                    if path.is_file()
                )
            )
            relocated_sca = json.loads(
                (
                    overlay
                    / "NDP_copy01/install/cfg_pkg/hwop-0004-00-vnext/sca_cfg.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(relocated_sca["Repeat_Num"], 5)
            self.assertEqual(
                _validate_immutable_tb_sca_parser_abi(
                    overlay
                    / "NDP_copy01/install/cfg_pkg/hwop-0004-00-vnext/sca_cfg.json",
                    relocated_sca,
                ),
                report["preload_transfer_segment_count"],
            )
            overlay_runner = (
                overlay / "NDP_copy01/RUN_SERVER_VNEXT.sh"
            ).read_text(encoding="utf-8")
            for runner_token in (
                'wall_timeout="24h"',
                "timeout --signal=TERM --kill-after=5m",
                "RUNTIME_STAGE_COMPLETE",
                "preload_readback_report.json",
                "run_metadata.json",
                "readback_regions",
                "required server commands are unavailable",
                "static_install_unexpected_file",
                "unset MAKEFLAGS MAKEFILES GNUMAKEFLAGS MFLAGS MAKELEVEL",
                'for stale_output in "${install_root}/install"/hwop-*',
            ):
                self.assertIn(runner_token, overlay_runner)
            bash = shutil.which("bash")
            if bash is not None:
                subprocess.run(
                    [bash, "-n", str(overlay / "NDP_copy01/RUN_SERVER_VNEXT.sh")],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            sca_paths = [
                item["path"]
                for item in sca.values()
                if isinstance(item, dict) and "path" in item
            ]
            self.assertEqual(
                len([path for path in sca_paths if path.startswith("install/data/")]),
                252,
            )
            self.assertEqual(
                len(
                    [
                        path
                        for path in sca_paths
                        if path.startswith("install/runtime_scratch/")
                    ]
                ),
                168,
            )
            scratch_semantic_keys = {
                str(item.get("semantic_key", key))
                for key, item in sca.items()
                if key.startswith("runtime_scratch_") and isinstance(item, dict)
            }
            self.assertEqual(len(scratch_semantic_keys), 84)
            self.assertTrue(
                all(
                    path.endswith(".txt")
                    for path in sca_paths
                    if path.startswith("install/data/")
                )
            )
            self.assertFalse(
                any(
                    token in path
                    for path in sca_paths
                    for token in ("golden/", "physical/P/", "physical/D/", "staged_D")
                )
            )

            self.assertEqual(execution["base_addr"], "0x00173000")
            def decode_128bit_payload(path: Path) -> bytes:
                return b"".join(
                    int(line, 2).to_bytes(16, byteorder="little")
                    for line in path.read_text(encoding="ascii").splitlines()
                    if line
                )

            self.assertEqual(
                len(decode_128bit_payload(output / execution["path"])),
                384 * 16,
            )

            tb_transfers: list[dict[str, object]] = []
            for key, item in sca.items():
                if not isinstance(item, dict):
                    continue
                if key == "ExecutionPlan" and isinstance(
                    item.get("chunked_transport"), dict
                ):
                    tb_transfers.append(item["chunked_transport"])
                elif isinstance(item.get("base_addr"), str) and isinstance(
                    item.get("path"), str
                ):
                    tb_transfers.append(item)
            self.assertEqual(len(tb_transfers), report["preload_transfer_segment_count"])
            parser_abi = runner["preload"]["sca_cfg"]["immutable_tb_parser_abi"]
            self.assertEqual(
                parser_abi["name"], "line-oriented-json-close-resets-entry-v1"
            )
            self.assertTrue(parser_abi["serialized_order_is_authoritative"])
            self.assertTrue(
                parser_abi["execution_plan_outer_close_loads_semantic_path"]
            )
            self.assertEqual(
                parser_abi["validated_transfer_count"], len(tb_transfers)
            )
            for transfer in tb_transfers:
                address = int(str(transfer["base_addr"]).replace("_", ""), 16)
                lines = [
                    line
                    for line in (output / str(transfer["path"]))
                    .read_text(encoding="ascii")
                    .splitlines()
                    if line
                ]
                remaining = len(lines)
                while remaining:
                    burst_beats = min(remaining, 256)
                    self.assertEqual(
                        address // 4096,
                        (address + burst_beats * 16 - 1) // 4096,
                    )
                    address += burst_beats * 16
                    remaining -= burst_beats
            for slice_id in range(28):
                self.assertEqual(
                    sca[f"freeze_A_slice{slice_id}"]["base_addr"],
                    f"0x{slice_id << 25:08X}",
                )
                self.assertTrue(
                    (output / "Bank_data" / f"slice{slice_id:02d}_Bank00_data.txt").is_file()
                )

            for port in ("A", "B", "bias"):
                transported = output / sca[f"freeze_{port}_slice0"]["path"]
                transported_lines = transported.read_text(encoding="ascii").splitlines()
                self.assertTrue(transported_lines)
                self.assertTrue(
                    all(len(line) == 128 and set(line) <= {"0", "1"} for line in transported_lines)
                )
                decoded = b"".join(
                    int(line, 2).to_bytes(16, byteorder="little")
                    for line in transported_lines
                )
                self.assertEqual(
                    decoded,
                    (freeze / "physical" / port / "slice-00.bin").read_bytes(),
                )

            preload = runner["preload"]
            self.assertEqual(preload["preferred_source"], "sca_cfg.json")
            self.assertEqual(preload["bank_data"]["format"], "binary")
            self.assertTrue(preload["readback_gate"]["required"])
            self.assertFalse(
                preload["readback_gate"]["pre_start_abort_required"]
            )
            self.assertFalse(
                runner["server_preload_verification"][
                    "required_for_completion_readiness"
                ]
            )
            self.assertEqual(preload["readback_gate"]["probe_count"], 170)
            self.assertEqual(len(preload["readback_gate"]["probes"]), 170)
            a_probe = next(
                probe
                for probe in preload["readback_gate"]["probes"]
                if probe.get("port") == "A" and probe.get("slice_id") == 0
            )
            self.assertEqual(
                a_probe["expected_128bit"],
                "0x"
                + (freeze / "physical/A/slice-00.bin")
                .read_bytes()[:16][::-1]
                .hex()
                .upper(),
            )

            bank_lines = (
                output / "Bank_data/slice00_Bank00_data.txt"
            ).read_text(encoding="ascii").splitlines()
            self.assertTrue(bank_lines)
            self.assertTrue(
                all(len(line) == 32 and set(line) <= {"0", "1"} for line in bank_lines)
            )
            self.assertEqual(
                b"".join(
                    int(line, 2).to_bytes(4, byteorder="little")
                    for line in bank_lines[:4]
                ),
                (freeze / "physical/A/slice-00.bin").read_bytes()[:16],
            )

            sim_banks = Path(temp_dir) / "post_run_banks"
            sim_banks.mkdir()
            dump_contract = json.loads(
                (output / "dump_contract.json").read_text(encoding="utf-8")
            )
            dump_regions = dump_contract["P"] + dump_contract["staged_D"]
            required_bank_bytes = max(
                int(region["local_offset"]) + int(region["size_bytes"])
                for region in dump_regions
            )
            for slice_id in range(28):
                image = bytearray(required_bank_bytes)
                p = (freeze / "physical/P" / f"slice-{slice_id:02d}.bin").read_bytes()
                d = np.frombuffer(
                    (freeze / "physical/D" / f"slice-{slice_id:02d}.bin").read_bytes(),
                    dtype=np.uint8,
                ).reshape(3, 56, 56, 16)
                p_region = next(
                    region
                    for region in dump_contract["P"]
                    if int(region["slice_id"]) == slice_id
                )
                p_offset = int(p_region["local_offset"])
                image[p_offset : p_offset + len(p)] = p
                for local_half, payload in enumerate(
                    (
                        np.ascontiguousarray(d[..., :8]).tobytes(),
                        np.ascontiguousarray(d[..., 8:]).tobytes(),
                    )
                ):
                    staged_region = next(
                        region
                        for region in dump_contract["staged_D"]
                        if int(region["slice_id"]) == slice_id
                        and int(region["local_half"]) == local_half
                    )
                    staged_offset = int(staged_region["local_offset"])
                    image[staged_offset : staged_offset + len(payload)] = payload
                (sim_banks / f"slice{slice_id:02d}_Bank00_data.bin").write_bytes(image)

            comparison = compare_conv_hardware_bank_dump(
                PROJECT_ROOT,
                output,
                sim_banks,
                Path(temp_dir) / "comparison_evidence",
            )
            self.assertEqual(comparison["status"], "passed")
            self.assertEqual(
                comparison["comparison"]["comparisons"]["P"]["mismatch_count"], 0
            )
            self.assertEqual(
                comparison["comparison"]["comparisons"]["D"]["mismatch_count"], 0
            )

            returned_root = Path(temp_dir) / "server_return"
            region_root = returned_root / "readback_regions"
            sca_d = json.loads((output / "sca_cfg_D.json").read_text(encoding="utf-8"))
            self.assertEqual(len(sca_d), 168)
            self.assertEqual(
                runner["post_run_dump"]["expected_region_count"],
                len(sca_d),
            )
            self.assertEqual(runner["post_run_dump"]["semantic_region_count"], 84)
            self.assertEqual(
                runner["post_run_dump"]["transfer_segment_count"], len(sca_d)
            )
            self.assertEqual(
                runner["post_run_dump"]["return_mode"],
                "sca_d_regions",
            )
            self.assertEqual(
                len(
                    {
                        str(entry.get("semantic_key", key))
                        for key, entry in sca_d.items()
                    }
                ),
                84,
            )
            bank_images = {
                slice_id: (sim_banks / f"slice{slice_id:02d}_Bank00_data.bin").read_bytes()
                for slice_id in range(28)
            }
            for entry in sca_d.values():
                address = int(entry["base_addr"].replace("_", ""), 16)
                remaining = int(entry["length"])
                burst_address = address
                while remaining:
                    burst_beats = min(remaining, 256)
                    self.assertEqual(
                        burst_address // 4096,
                        (burst_address + burst_beats * 16 - 1) // 4096,
                    )
                    burst_address += burst_beats * 16
                    remaining -= burst_beats
                slice_id = (address >> 25) & 0x1F
                offset = address & ((1 << 23) - 1)
                size_bytes = int(entry["length"]) * 16
                payload = bank_images[slice_id][offset : offset + size_bytes]
                region_path = region_root / Path(entry["path"]).relative_to("install")
                region_path.parent.mkdir(parents=True, exist_ok=True)
                region_path.write_text(
                    "".join(
                        f"{int.from_bytes(payload[index:index + 16], 'little'):0128b}\n"
                        for index in range(0, len(payload), 16)
                    ),
                    encoding="ascii",
                    newline="\n",
                )

            returned_config = returned_root / "config"
            returned_metadata = returned_config / "metadata"
            returned_metadata.mkdir(parents=True)
            relocated_root = (
                overlay / "NDP_copy01/install/cfg_pkg/hwop-0004-00-vnext"
            )
            shutil.copy2(relocated_root / "sca_cfg.json", returned_config / "sca_cfg.json")
            shutil.copy2(
                relocated_root / "sca_cfg_D.json",
                returned_config / "sca_cfg_D.json",
            )
            for metadata_path in (relocated_root / "metadata").iterdir():
                if metadata_path.is_file():
                    shutil.copy2(metadata_path, returned_metadata / metadata_path.name)
            expected_transfer_count = len(sca_paths)
            (returned_root / "preload_readback_report.json").write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "expected_transfer_count": expected_transfer_count,
                        "passed_transfer_count": expected_transfer_count,
                    }
                ),
                encoding="utf-8",
            )
            returned_run_results = returned_root / "run_sim_results"
            returned_run_results.mkdir()
            (returned_run_results / "vnext_exit_status.txt").write_text(
                "0\n", encoding="ascii"
            )
            (returned_run_results / "vnext_phase_progress.tsv").write_text(
                "100\tpreload\tpasses=1 loads=1\n", encoding="ascii"
            )
            watchdog_done_path = (
                returned_run_results / "vnext_phase_watchdog_done.tsv"
            )
            watchdog_done_path.write_text(
                "normal_process_exit\t0\n", encoding="ascii"
            )

            def sha256(path: Path) -> str:
                return hashlib.sha256(path.read_bytes()).hexdigest()

            package_manifest = json.loads(
                (output / "manifest.json").read_text(encoding="utf-8")
            )
            observer_contract = package_manifest["testbench_observer"]
            console_path = returned_run_results / "vnext_console.log"
            console_lines = ["RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING"]
            for transfer_index in range(expected_transfer_count):
                console_lines.extend(
                    [
                        (
                            f"[{100 + transfer_index * 2}] JSON: Loading matrix"
                            f"[{transfer_index}]: install/unit-{transfer_index}.txt "
                            "-> 0x00000000"
                        ),
                        (
                            f"[{101 + transfer_index * 2}] *** PASS: Continuous transfer "
                            "completed successfully!"
                        ),
                    ]
                )
            for pair_index in range(observer_contract["repeat_num"]):
                console_lines.extend(
                    [
                        f"[{1_000 + pair_index * 2}] INFO: slice start",
                        (
                            f"[{1_001 + pair_index * 2}] INFO: slice completed after "
                            f"{10_000 + pair_index} cycles"
                        ),
                    ]
                )
            console_lines.extend(
                [
                    "Simulation completed successfully!",
                    "Simulation exit status: 0",
                ]
            )
            console_path.write_text("\n".join(console_lines) + "\n", encoding="utf-8")
            valid_console = console_path.read_text(encoding="utf-8")
            runner_path = overlay / "NDP_copy01/RUN_SERVER_VNEXT.sh"
            runtime_identity_path = returned_metadata / "runtime_identity.json"
            approved_runtime_identity_path = (
                relocated_root / "metadata/runtime_identity.json"
            )
            valid_approved_runtime_identity_text = (
                approved_runtime_identity_path.read_text(encoding="utf-8")
            )
            approved_runtime_identity = json.loads(
                valid_approved_runtime_identity_text
            )
            returned_run_command_contract = returned_metadata / Path(
                approved_runtime_identity["run_command_contract"]["path"]
            ).name
            returned_run_argv = returned_run_command_contract.read_text(
                encoding="utf-8"
            ).splitlines()
            server_run_id = "run1"
            top_filelist_hash = "a" * 64
            dir_home_value = "/srv/vendor"
            dir_home_value_sha256 = hashlib.sha256(
                dir_home_value.encode("utf-8")
            ).hexdigest()
            source_inventory_path = returned_config / "server_source_inventory.tsv"
            source_inventory_path.write_text(
                "entrypoint\tMakefile.tb_NDP_Top_new_phy\tphysical:/srv/Makefile.tb_NDP_Top_new_phy\t1\t"
                + "c" * 64
                + "\nentrypoint\trtl/filelists/NDP_Top_phy_filelist.f\tphysical:/srv/rtl/filelists/NDP_Top_phy_filelist.f\t1\t"
                + top_filelist_hash
                + "\nentrypoint\ttb_NDP_Top_new_phy.sv\tphysical:/srv/tb_NDP_Top_new_phy.sv\t1\t"
                + expected_server_testbench_sha256
                + "\nenvironment\tDIR_HOME\tset\tvalue:"
                + dir_home_value
                + "\tvendor_physical:/srv/vendor/Hardware/IP/bus/nic_cgra_0310\t"
                + dir_home_value_sha256
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            (returned_root / "server_source_provenance.json").write_text(
                json.dumps(
                    {
                        "schema_version": "resnet50-server-source-provenance-0.4",
                        "server_run_id": server_run_id,
                        "identity_policy": "logical_entrypoints_and_dir_home_recorded_nonblocking",
                        "preflight_source_policy": "readable_logical_entrypoints_only",
                        "makefile_sha256": "c" * 64,
                        "testbench_sha256": expected_server_testbench_sha256,
                        "top_filelist_sha256": top_filelist_hash,
                        "source_inventory_sha256": sha256(source_inventory_path),
                        "entrypoint_record_count": 3,
                        "environment_record_count": 1,
                        "dir_home_value_sha256": dir_home_value_sha256,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (returned_root / "run_metadata.json").write_text(
                json.dumps(
                    {
                        "server_run_id": server_run_id,
                        "execution_environment": "rtl_simulation",
                        "board_version": "not_applicable_rtl_simulation",
                        "simulator_version": "vcs-test",
                        "rtl_version": "server_entrypoint_unpinned",
                        "firmware_version": "not_applicable_rtl_simulation",
                        "isa_contract": (
                            "model_execplan_package_manifest_and_execplan_128bit_v1"
                        ),
                        "run_command": " | ".join(returned_run_argv),
                        "run_command_contract_sha256": approved_runtime_identity[
                            "run_command_contract"
                        ]["sha256"],
                        "runtime_make_override_sha256": approved_runtime_identity[
                            "runtime_make_override"
                        ]["sha256"],
                        "make_archive_policy": "runner_no_archive_target_v1",
                        "exit_status": 0,
                        "process_exit_status": 0,
                        "make_exit_status": 0,
                        "tee_exit_status": 0,
                        "phase_watchdog_exit_status": 0,
                        "raw_phase_watchdog_exit_status": 0,
                        "phase_watchdog_done": True,
                        "simulator_exit_status": 0,
                        "simulator_exit_status_observed": True,
                        "timeout_status": "not_timed_out",
                        "phase_timeout_status": "not_timed_out",
                        "phase_timeout_phase": "none",
                        "phase_last_progress": "complete",
                        "phase_stall_seconds": 0,
                        "phase_failure_reason": "none",
                        "termination_kind": "natural_process_exit",
                        "preflight_status": "passed",
                        "wall_time_seconds": 1,
                        "freeze_id": package_manifest["freeze_id"],
                        "freeze_manifest_sha256": package_manifest[
                            "freeze_manifest_sha256"
                        ],
                        "package_manifest_sha256": sha256(output / "manifest.json"),
                        "server_source_provenance": "server_source_provenance.json",
                        "preload_readback_report": "preload_readback_report.json",
                        "completed_runtime_stage_count": package_manifest[
                            "runtime_operator_count"
                        ],
                        "expected_runtime_stage_count": package_manifest[
                            "runtime_operator_count"
                        ],
                        "testbench_observer_mode": observer_contract["mode"],
                        "expected_testbench_repeat_num": observer_contract["repeat_num"],
                        "observed_slice0_start_count": observer_contract["repeat_num"],
                        "observed_slice1_finish_count": observer_contract["repeat_num"],
                        "reserved_clock_force_marker_count": 1,
                        "reserved_clock_failure_marker_count": 0,
                        "stage_marker_status": "passed",
                        "all_stages_marker_status": "passed",
                        "returned_region_count": len(sca_d),
                        "expected_region_count": len(sca_d),
                        "readback_region_contract_status": "passed",
                        "sca_cfg_sha256": sha256(returned_config / "sca_cfg.json"),
                        "sca_cfg_D_sha256": sha256(
                            returned_config / "sca_cfg_D.json"
                        ),
                        "runner_sha256": sha256(runner_path),
                        "runner_identity_sha256": approved_runtime_identity[
                            "runner_identity"
                        ]["sha256"],
                        "testbench_sha256": expected_server_testbench_sha256,
                        "readback_contract_sha256": approved_runtime_identity[
                            "readback_region_contract"
                        ]["sha256"],
                        "stage_contract_sha256": approved_runtime_identity[
                            "runtime_stage_contract"
                        ]["sha256"],
                        "launch_files_contract_sha256": approved_runtime_identity[
                            "launch_file_contract"
                        ]["sha256"],
                        "launch_identity_sha256": approved_runtime_identity[
                            "launch_identity"
                        ]["sha256"],
                        "runtime_identity_sha256": sha256(runtime_identity_path),
                        "wall_timeout": "24h",
                        "bank_frame_logging_policy": (
                            "slice_start_only_plus_runtime_devnull_sinks"
                        ),
                        "reserved_clock_validation": "force_and_low_high_toggle_proof",
                        "runtime_log_sink_policy": (
                            "audited_sinks_unknown_log_guard_v2"
                        ),
                        "runtime_log_total_size_limit_bytes": 1073741824,
                        "diagnostic_sink_count": 1037,
                        "diagnostic_return_file_count": 0,
                        "diagnostic_return_total_bytes": 0,
                        "diagnostic_file_size_limit_bytes": 1048576,
                        "diagnostic_total_size_limit_bytes": 1048576,
                        "return_file_contract": "return_file_contract.tsv",
                        "return_archive_policy": "bounded_exact_set_allowlist_v2",
                    }
                ),
                encoding="utf-8",
            )
            (returned_root / "diagnostic_allowlist.tsv").write_text(
                "", encoding="utf-8"
            )
            (returned_root / "return_archive_policy.json").write_text(
                json.dumps(
                    {
                        "schema_version": "resnet50-server-return-archive-policy-0.4",
                        "server_run_id": server_run_id,
                        "policy": "bounded_exact_set_allowlist_v2",
                        "diagnostic_allowlist": "diagnostic_allowlist.tsv",
                        "diagnostic_file_size_limit_bytes": 1048576,
                        "diagnostic_total_size_limit_bytes": 1048576,
                        "diagnostic_truncation_policy": "head_bytes_v1",
                        "diagnostic_return_file_count": 0,
                        "diagnostic_return_total_bytes": 0,
                        "runtime_log_sink_policy": (
                            "audited_sinks_unknown_log_guard_v2"
                        ),
                        "runtime_log_total_size_limit_bytes": 1073741824,
                        "runtime_log_sink_count": 1037,
                        "make_archive_policy": "runner_no_archive_target_v1",
                        "run_command_contract_sha256": approved_runtime_identity[
                            "run_command_contract"
                        ]["sha256"],
                        "return_file_contract": "return_file_contract.tsv",
                        "full_sim_results_copied": False,
                        "waveform_included": False,
                        "archive_timeout": "1h",
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            def refresh_return_file_contract() -> None:
                contract_path = returned_root / "return_file_contract.tsv"
                records = []
                for path in sorted(
                    item
                    for item in returned_root.rglob("*")
                    if item.is_file() and item != contract_path
                ):
                    records.append(
                        "\t".join(
                            (
                                path.relative_to(returned_root).as_posix(),
                                str(path.stat().st_size),
                                sha256(path),
                            )
                        )
                    )
                contract_path.write_text(
                    "\n".join(records) + "\n", encoding="utf-8", newline="\n"
                )

            refresh_return_file_contract()
            return_gate = validate_conv_hardware_region_return(
                output,
                returned_root,
                approved_runtime_identity_path,
            )
            self.assertEqual(
                return_gate["status"],
                "hardware_region_return_validated",
            )
            self.assertTrue(return_gate["formal_acceptance_ready"])
            self.assertEqual(return_gate["formal_blockers"], [])
            capability_attestation = approved_runtime_identity[
                "immutable_testbench_capability_attestation"
            ]
            self.assertEqual(
                capability_attestation["identity_policy"],
                "logical_entrypoints_unpinned_source_provenance",
            )
            self.assertFalse(capability_attestation["prestart_source_hash_required"])
            self.assertEqual(return_gate["console"]["path"], "run_sim_results/vnext_console.log")
            self.assertEqual(return_gate["console"]["sha256"], sha256(console_path))
            self.assertEqual(
                return_gate["console"]["completed_runtime_stage_count"], 12
            )
            self.assertEqual(
                return_gate["console"]["preload_readback_pass_count"],
                expected_transfer_count,
            )
            self.assertEqual(return_gate["console"]["fixed_observer_pair_count"], 5)
            self.assertEqual(
                return_gate["console"]["reserved_clock_force_marker_count"], 1
            )
            returned_root_run2 = Path(temp_dir) / "server_return_run2"
            shutil.copytree(returned_root, returned_root_run2)
            run2_metadata_path = returned_root_run2 / "run_metadata.json"
            run2_metadata = json.loads(run2_metadata_path.read_text(encoding="utf-8"))
            run2_metadata["server_run_id"] = "run2"
            run2_metadata_path.write_text(
                json.dumps(run2_metadata), encoding="utf-8"
            )
            run2_provenance_path = (
                returned_root_run2 / "server_source_provenance.json"
            )
            run2_provenance = json.loads(
                run2_provenance_path.read_text(encoding="utf-8")
            )
            run2_provenance["server_run_id"] = "run2"
            run2_provenance_path.write_text(
                json.dumps(run2_provenance, sort_keys=True), encoding="utf-8"
            )
            run2_archive_policy_path = (
                returned_root_run2 / "return_archive_policy.json"
            )
            run2_archive_policy = json.loads(
                run2_archive_policy_path.read_text(encoding="utf-8")
            )
            run2_archive_policy["server_run_id"] = "run2"
            run2_archive_policy_path.write_text(
                json.dumps(run2_archive_policy, sort_keys=True), encoding="utf-8"
            )

            def refresh_run2_return_file_contract() -> None:
                contract_path = returned_root_run2 / "return_file_contract.tsv"
                records = []
                for path in sorted(
                    item
                    for item in returned_root_run2.rglob("*")
                    if item.is_file() and item != contract_path
                ):
                    records.append(
                        "\t".join(
                            (
                                path.relative_to(returned_root_run2).as_posix(),
                                str(path.stat().st_size),
                                sha256(path),
                            )
                        )
                    )
                contract_path.write_text(
                    "\n".join(records) + "\n", encoding="utf-8", newline="\n"
                )

            refresh_run2_return_file_contract()
            repeated_gate = validate_conv_hardware_repeated_region_returns(
                output,
                {"run1": returned_root, "run2": returned_root_run2},
                approved_runtime_identity_path,
            )
            self.assertEqual(
                repeated_gate["status"],
                "formal_run1_run2_environment_provenance_and_regions_stable",
            )
            self.assertEqual(repeated_gate["region_count"], len(sca_d))
            self.assertRegex(repeated_gate["region_receipt_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(
                repeated_gate["server_source_provenance_sha256"], r"^[0-9a-f]{64}$"
            )
            self.assertRegex(
                repeated_gate["execution_environment_sha256"], r"^[0-9a-f]{64}$"
            )

            run2_source_inventory_path = (
                returned_root_run2 / "config/server_source_inventory.tsv"
            )
            valid_run2_source_inventory = run2_source_inventory_path.read_text(
                encoding="utf-8"
            )
            run2_source_inventory_path.write_text(
                valid_run2_source_inventory.replace(
                    "physical:/srv/tb_NDP_Top_new_phy.sv",
                    "physical:/srv-alternate/tb_NDP_Top_new_phy.sv",
                ),
                encoding="utf-8",
                newline="\n",
            )
            changed_run2_provenance = dict(run2_provenance)
            changed_run2_provenance["source_inventory_sha256"] = sha256(
                run2_source_inventory_path
            )
            run2_provenance_path.write_text(
                json.dumps(changed_run2_provenance, sort_keys=True), encoding="utf-8"
            )
            refresh_run2_return_file_contract()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "run1/run2 server entrypoint provenance differs",
            ):
                validate_conv_hardware_repeated_region_returns(
                    output,
                    {"run1": returned_root, "run2": returned_root_run2},
                    approved_runtime_identity_path,
                )
            run2_source_inventory_path.write_text(
                valid_run2_source_inventory, encoding="utf-8", newline="\n"
            )
            run2_provenance_path.write_text(
                json.dumps(run2_provenance, sort_keys=True), encoding="utf-8"
            )
            refresh_run2_return_file_contract()

            run2_metadata["simulator_version"] = "vcs-test-alternate"
            run2_metadata_path.write_text(
                json.dumps(run2_metadata), encoding="utf-8"
            )
            refresh_run2_return_file_contract()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "run1/run2 execution environment differs",
            ):
                validate_conv_hardware_repeated_region_returns(
                    output,
                    {"run1": returned_root, "run2": returned_root_run2},
                    approved_runtime_identity_path,
                )
            run2_metadata["simulator_version"] = "vcs-test"
            run2_metadata_path.write_text(
                json.dumps(run2_metadata), encoding="utf-8"
            )
            refresh_run2_return_file_contract()

            repeat_first_region_entry = next(iter(sca_d.values()))
            run2_first_region_path = (
                returned_root_run2
                / "readback_regions"
                / Path(repeat_first_region_entry["path"]).relative_to("install")
            )
            run2_first_region_payload = run2_first_region_path.read_bytes()
            run2_first_region_path.write_bytes(
                (b"1" if run2_first_region_payload[:1] == b"0" else b"0")
                + run2_first_region_payload[1:]
            )
            refresh_run2_return_file_contract()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "run1/run2 physical readback regions differ",
            ):
                validate_conv_hardware_repeated_region_returns(
                    output,
                    {"run1": returned_root, "run2": returned_root_run2},
                    approved_runtime_identity_path,
                )
            run2_first_region_path.write_bytes(run2_first_region_payload)
            refresh_run2_return_file_contract()
            provenance_path = returned_root / "server_source_provenance.json"
            valid_provenance = json.loads(
                provenance_path.read_text(encoding="utf-8")
            )
            tampered_provenance = dict(valid_provenance)
            tampered_provenance["entrypoint_record_count"] = 2
            provenance_path.write_text(
                json.dumps(tampered_provenance, sort_keys=True), encoding="utf-8"
            )
            refresh_return_file_contract()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "entrypoint provenance exact set differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            provenance_path.write_text(
                json.dumps(valid_provenance, sort_keys=True), encoding="utf-8"
            )
            refresh_return_file_contract()
            region_receipt = return_gate["validated_region_receipt"]
            json.dumps(return_gate)
            self.assertEqual(region_receipt["region_count"], len(sca_d))
            self.assertEqual(len(region_receipt["files"]), len(sca_d))
            self.assertTrue(
                all(len(record["sha256"]) == 64 for record in region_receipt["files"])
            )

            extra_metadata_path = returned_metadata / "stale_extra_metadata.json"
            extra_metadata_path.write_text("{}\n", encoding="utf-8", newline="\n")
            refresh_return_file_contract()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "config/metadata exact set differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            extra_metadata_path.unlink()
            refresh_return_file_contract()

            phase_timeout_path = returned_run_results / "vnext_phase_timeout.tsv"
            phase_timeout_path.write_text(
                "compute_observer\t0/5\t3600\t3600\tstall_timeout\n",
                encoding="ascii",
            )
            refresh_return_file_contract()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "successful server run-results exact set differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            phase_timeout_path.unlink()
            watchdog_done_path.write_text(
                "abnormal_process_exit\t70\n", encoding="ascii"
            )
            refresh_return_file_contract()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "phase-watchdog completion sentinel content differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            watchdog_done_path.write_text(
                "normal_process_exit\t0\n", encoding="ascii"
            )
            refresh_return_file_contract()

            console_path.unlink()
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree exact set differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            console_path.write_text(valid_console, encoding="utf-8")

            console_path.write_text(
                valid_console.replace(
                    "[101] *** PASS: Continuous transfer completed successfully!\n",
                    "",
                    1,
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            console_path.write_text(valid_console, encoding="utf-8")

            console_path.write_text(
                valid_console.replace("INFO: slice start", "INFO: slice stop", 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            console_path.write_text(valid_console, encoding="utf-8")

            console_path.write_text(
                valid_console.replace(
                    "Simulation completed successfully!\n",
                    "Simulation completed successfully!\n"
                    "Simulation completed successfully!\n",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            console_path.write_text(valid_console, encoding="utf-8")

            unexpected_region = region_root / "hwop-unexpected/extra.txt"
            unexpected_region.parent.mkdir(parents=True)
            unexpected_region.write_text("0" * 128 + "\n", encoding="ascii")
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree exact set differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            unexpected_region.unlink()
            unexpected_region.parent.rmdir()

            first_region_entry = next(iter(sca_d.values()))
            first_region_path = (
                region_root / Path(first_region_entry["path"]).relative_to("install")
            )
            valid_first_region = first_region_path.read_text(encoding="ascii")
            first_region_path.write_text("2" * 128 + "\n", encoding="ascii")
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            first_region_path.write_text(valid_first_region, encoding="ascii")
            run_metadata_path = returned_root / "run_metadata.json"
            valid_run_metadata = json.loads(
                run_metadata_path.read_text(encoding="utf-8")
            )
            tampered_run_metadata = dict(valid_run_metadata)
            tampered_run_metadata["returned_region_count"] = len(sca_d) - 1
            run_metadata_path.write_text(
                json.dumps(tampered_run_metadata), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            run_metadata_path.write_text(
                json.dumps(valid_run_metadata), encoding="utf-8"
            )
            tampered_run_metadata = dict(valid_run_metadata)
            tampered_run_metadata["timeout_status"] = "wall_timeout"
            tampered_run_metadata["termination_kind"] = "wall_timeout"
            run_metadata_path.write_text(
                json.dumps(tampered_run_metadata), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            run_metadata_path.write_text(
                json.dumps(valid_run_metadata), encoding="utf-8"
            )
            tampered_run_metadata = dict(valid_run_metadata)
            tampered_run_metadata["runner_sha256"] = "0" * 64
            run_metadata_path.write_text(
                json.dumps(tampered_run_metadata), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            run_metadata_path.write_text(
                json.dumps(valid_run_metadata), encoding="utf-8"
            )

            tampered_run_metadata = dict(valid_run_metadata)
            tampered_run_metadata["run_command"] = "   "
            run_metadata_path.write_text(
                json.dumps(tampered_run_metadata), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            run_metadata_path.write_text(
                json.dumps(valid_run_metadata), encoding="utf-8"
            )

            tampered_runtime_identity = json.loads(
                valid_approved_runtime_identity_text
            )
            tampered_runtime_identity[
                "immutable_testbench_capability_attestation"
            ]["identity_policy"] = "content_hash_pinned"
            tampered_identity_text = json.dumps(
                tampered_runtime_identity,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
            runtime_identity_path.write_text(tampered_identity_text, encoding="utf-8")
            approved_runtime_identity_path.write_text(
                tampered_identity_text, encoding="utf-8"
            )
            tampered_run_metadata = dict(valid_run_metadata)
            tampered_run_metadata["runtime_identity_sha256"] = sha256(
                runtime_identity_path
            )
            run_metadata_path.write_text(
                json.dumps(tampered_run_metadata), encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "whole-tree file identity differs",
            ):
                validate_conv_hardware_region_return(
                    output,
                    returned_root,
                    approved_runtime_identity_path,
                )
            runtime_identity_path.write_text(
                valid_approved_runtime_identity_text, encoding="utf-8"
            )
            approved_runtime_identity_path.write_text(
                valid_approved_runtime_identity_text, encoding="utf-8"
            )
            run_metadata_path.write_text(
                json.dumps(valid_run_metadata), encoding="utf-8"
            )

            assembled_banks = Path(temp_dir) / "assembled_region_banks"
            adapter = assemble_conv_hardware_region_dump(
                output,
                returned_root,
                assembled_banks,
                validated_region_receipt=region_receipt,
            )
            self.assertEqual(adapter["status"], "hardware_region_dump_assembled")
            self.assertEqual(adapter["consumed_region_count"], 168)
            self.assertTrue(adapter["validated_region_receipt_reused"])
            region_comparison = compare_conv_hardware_bank_dump(
                PROJECT_ROOT,
                output,
                assembled_banks,
                Path(temp_dir) / "region_comparison_evidence",
            )
            self.assertEqual(region_comparison["status"], "passed")

    def test_package_binding_rejects_old_e0_bitstream_even_if_raw_manifest_is_updated(self) -> None:
        source = (
            PROJECT_ROOT
            / "artifacts/w5/hwop-0004-00/v18/hardware_execplan_package"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir) / "package"
            shutil.copytree(source, package)
            install_relative = "install/cfg_pkg/conv_1x1_real_bitstream_128b.bin"
            install = package / install_relative
            stale = (
                PROJECT_ROOT
                / "artifacts/w5/conv_1x1_real/e0-rebuild/modules_dump_128b.bin"
            )
            install.write_text(
                "\n".join(stale.read_text(encoding="ascii").splitlines()) + "\n",
                encoding="ascii",
                newline="\n",
            )
            manifest_path = package / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            observed = bitstream_text_identity(install, line_width_bits=128)
            binding = next(
                item
                for item in manifest["bitstream_bindings"]["records"]
                if item["binding_id"].endswith(".accumulate")
            )
            binding["install"] = {"path": install_relative, **observed}
            file_record = next(
                item for item in manifest["files"] if item["path"] == install_relative
            )
            payload = install.read_bytes()
            file_record["size_bytes"] = len(payload)
            file_record["sha256"] = hashlib.sha256(payload).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(
                ConvHardwareExecplanError,
                "package binding .* logical bitstream differs",
            ):
                validate_conv_hardware_execplan_package(package)

    def test_parameterized_instances_use_the_explicit_legacy_transport_abi(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temporary = Path(temp_dir)
            for node_id in ("node-0008", "node-0003"):
                with self.subTest(node_id=node_id):
                    freeze = temporary / node_id / "freeze"
                    package = temporary / node_id / "package"
                    freeze_manifest = export_hardware_freeze(
                        PROJECT_ROOT, freeze, node_id=node_id
                    )
                    self.assertEqual(
                        freeze_manifest["status"], "candidate_hardware_freeze_ready"
                    )
                    request_path = (
                        PROJECT_ROOT
                        / "artifacts"
                        / "w5"
                        / freeze_manifest["identity"]["hw_op_ids"][0]
                        / "execplan_request.json"
                    )
                    report = generate_conv_hardware_execplan(
                        PROJECT_ROOT,
                        package,
                        node_id=node_id,
                        freeze_root=freeze,
                        execplan_request_path=request_path,
                    )
                    self.assertEqual(
                        report["status"], "hardware_execplan_package_validated"
                    )
                    request = json.loads(request_path.read_text(encoding="utf-8"))
                    self.assertTrue(
                        all(
                            operator["attributes"]["target"]["transport_abi"]
                            == "conv_sa_legacy_v1"
                            for operator in request["operators"]
                        )
                    )


if __name__ == "__main__":
    unittest.main()
