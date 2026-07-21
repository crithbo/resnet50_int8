from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.hardware_simulation_frontend import (
    HardwareSimulationPreparationError,
    build_execution_stages,
    decode_command,
    load_payload_bytes,
    prepare_hardware_simulation,
    run_prepared_simulation,
    verify_server_preload_readback,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pack_execplan(commands: list[int]) -> str:
    if len(commands) % 2:
        commands.append(0)
    lines = []
    for index in range(0, len(commands), 2):
        low = commands[index]
        high = commands[index + 1]
        lines.append(f"{high:064b}{low:064b}")
    return "\n".join(lines) + "\n"


def _decoded_fixture_commands(*, barrier_mask: int = 1) -> list[object]:
    slice_mask = 1
    raw_commands = [
        (0b1111 << 31) | (slice_mask << 3) | 0b001,
        (2 << 56) | ((0x400 >> 10) << 34) | (slice_mask << 3) | 0b000,
        (0xDEADBEEF << 32) | (0x123 << 18) | 0b100,
        (slice_mask << 3) | 0b101,
        (barrier_mask << 3) | 0b110,
    ]
    return [
        decode_command(
            raw,
            index=index,
            beat_index=index // 2,
            lane="low" if index % 2 == 0 else "high",
        )
        for index, raw in enumerate(raw_commands)
    ]


def _serialization_manifest(**overrides: object) -> dict[str, object]:
    serialization: dict[str, object] = {
        "strategy": "post_start_same_mask_barrier",
        "barrier_opcode": "0b110",
        "barrier_count": 1,
    }
    serialization.update(overrides)
    return {
        "runtime_sequence": ["fixture-op"],
        "runtime_serialization": serialization,
    }


def _build_fixture(root: Path) -> Path:
    package = root / "package"
    install = package / "install"
    bank_root = package / "Bank_data"
    install.mkdir(parents=True)
    bank_root.mkdir(parents=True)

    input_path = install / "input.bin"
    input_path.write_bytes(bytes(range(16)))
    config_path = install / "config.bin"
    config_path.write_text(f"{0x0123456789ABCDEFFEDCBA9876543210:0128b}\n", encoding="ascii")

    slice_mask = 1
    clock_enable = (0b1111 << 31) | (slice_mask << 3) | 0b001
    load_config = (2 << 56) | ((0x400 >> 10) << 34) | (slice_mask << 3) | 0b000
    write_reg = (0xDEADBEEF << 32) | (0x123 << 18) | (0 << 3) | 0b100
    start_comp = (slice_mask << 3) | 0b101
    completion_barrier = (slice_mask << 3) | 0b110
    exec_path = install / "execplan.txt"
    exec_path.write_text(
        _pack_execplan(
            [clock_enable, load_config, write_reg, start_comp, completion_barrier]
        ),
        encoding="ascii",
    )

    sca = {
        "Exec_Base": "0x00000800",
        "Exec_Length": 3,
        "ExecutionPlan": {"base_addr": "0x00000800", "path": "install/execplan.txt"},
        "fixture_input_slice0": {"base_addr": "0x00000000", "path": "install/input.bin"},
        "fixture_config": {"base_addr": "0x00000400", "path": "install/config.bin"},
    }
    (package / "sca_cfg.json").write_text(
        json.dumps(sca, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    runner_contract = {
        "preload": {
            "readback_gate": {
                "required": True,
                "probe_count": 2,
                "probes": [
                    {
                        "kind": "input",
                        "base_addr": "0x00000000",
                        "expected_128bit": (
                            f"0x{int.from_bytes(input_path.read_bytes(), byteorder='little'):032X}"
                        ),
                    },
                    {
                        "kind": "config",
                        "base_addr": "0x00000400",
                        "expected_128bit": (
                            f"0x{int.from_bytes(load_payload_bytes(config_path), byteorder='little'):032X}"
                        ),
                    },
                ],
            }
        }
    }
    (package / "runner_contract.json").write_text(
        json.dumps(runner_contract, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    exec_payload = load_payload_bytes(exec_path)
    bank = bytearray(0x800 + len(exec_payload))
    bank[0:16] = input_path.read_bytes()
    bank[0x400:0x410] = load_payload_bytes(config_path)
    bank[0x800 : 0x800 + len(exec_payload)] = exec_payload
    (bank_root / "slice00_Bank00_data.bin").write_bytes(bank)

    tracked = [
        package / "sca_cfg.json",
        package / "runner_contract.json",
        input_path,
        config_path,
        exec_path,
    ]
    manifest = {
        "schema_version": "fixture-hardware-package-0.1",
        "status": "hardware_execplan_package_validated",
        "node_id": "fixture-node",
        "runtime_sequence": ["fixture-op"],
        "runtime_serialization": {
            "strategy": "post_start_same_mask_barrier",
            "barrier_opcode": "0b110",
            "barrier_count": 1,
        },
        "runtime_operators": [
            {
                "operator_id": "fixture-op",
                "operator_type": "fixture_identity",
                "stage": "identity",
                "instance_id": "fixture-instance",
                "slice_mask": "0x0000001",
                "attributes": {"family": "test"},
            }
        ],
        "files": [
            {
                "path": path.relative_to(package).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in tracked
        ],
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return package


class HardwareSimulationFrontendTest(unittest.TestCase):
    def test_generic_package_becomes_stage_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = _build_fixture(Path(temp_dir))
            prepared = prepare_hardware_simulation(package)
            report = prepared.report()

            self.assertEqual(report["status"], "hardware_simulation_input_prepared")
            self.assertEqual(report["command_count"], 5)
            self.assertEqual(
                [command.kind for command in prepared.commands],
                [
                    "clock_enable",
                    "load_config",
                    "write_reg",
                    "start_comp",
                    "barrier",
                ],
            )
            self.assertEqual(len(prepared.invocations), 1)
            invocation = prepared.invocations[0]
            self.assertEqual(invocation.stage.operator_id, "fixture-op")
            self.assertEqual(invocation.stage.operator_type, "fixture_identity")
            self.assertIsNotNone(invocation.stage.completion_barrier)
            self.assertEqual(invocation.register_values[(0, 0x123)], 0xDEADBEEF)
            self.assertEqual(
                invocation.loaded_configs[(0, False)].payload,
                load_payload_bytes(package / "install/config.bin"),
            )
            self.assertEqual(report["numeric_executor"]["status"], "not_run")

    def test_sca_payload_must_match_preloaded_bank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = _build_fixture(Path(temp_dir))
            bank_path = package / "Bank_data/slice00_Bank00_data.bin"
            bank = bytearray(bank_path.read_bytes())
            bank[0] ^= 0xFF
            bank_path.write_bytes(bank)
            with self.assertRaisesRegex(
                HardwareSimulationPreparationError,
                "does not contain SCA payload fixture_input_slice0",
            ):
                prepare_hardware_simulation(package)

    def test_unknown_opcode_fails_closed(self) -> None:
        with self.assertRaisesRegex(HardwareSimulationPreparationError, "unsupported opcode"):
            decode_command(0b010, index=0, beat_index=0, lane="low")

    def test_runtime_serialization_requires_immediate_same_mask_barrier(self) -> None:
        commands = _decoded_fixture_commands()
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "contract differs"
        ):
            build_execution_stages(commands[:-1], _serialization_manifest())

        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "slice masks differ"
        ):
            build_execution_stages(
                _decoded_fixture_commands(barrier_mask=2), _serialization_manifest()
            )

        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "before its completion barrier"
        ):
            build_execution_stages(
                commands[:-1] + [commands[1], commands[-1]],
                _serialization_manifest(),
            )

    def test_runtime_serialization_schema_fails_closed(self) -> None:
        commands = _decoded_fixture_commands()
        invalid_manifests = [
            {"runtime_sequence": ["fixture-op"], "runtime_serialization": "barrier"},
            _serialization_manifest(strategy="unknown"),
            _serialization_manifest(barrier_count=True),
            _serialization_manifest(barrier_count=2),
            _serialization_manifest(barrier_opcode="0b111"),
        ]
        for manifest in invalid_manifests:
            with self.subTest(manifest=manifest):
                with self.assertRaises(HardwareSimulationPreparationError):
                    build_execution_stages(commands, manifest)

        legacy_global, legacy_stages = build_execution_stages(
            commands[:-1], {"runtime_sequence": ["fixture-op"]}
        )
        self.assertEqual(len(legacy_global), 1)
        self.assertIsNone(legacy_stages[0].completion_barrier)
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError,
            "without a runtime_serialization contract",
        ):
            build_execution_stages(commands, {"runtime_sequence": ["fixture-op"]})

    def test_server_preload_readback_blocks_execution_on_first_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temporary = Path(temp_dir)
            package = _build_fixture(temporary)
            readback = temporary / "readback"
            readback.mkdir()
            source_bank = package / "Bank_data/slice00_Bank00_data.bin"
            observed_bank = readback / source_bank.name
            observed_bank.write_bytes(source_bank.read_bytes())

            passed = verify_server_preload_readback(package, readback)
            self.assertEqual(passed["status"], "passed")
            self.assertTrue(passed["execution_authorized"])
            self.assertEqual(passed["passed_probe_count"], 2)

            corrupted = bytearray(observed_bank.read_bytes())
            corrupted[0] ^= 0xFF
            observed_bank.write_bytes(corrupted)
            failed = verify_server_preload_readback(package, readback)
            self.assertEqual(failed["status"], "failed")
            self.assertFalse(failed["execution_authorized"])
            self.assertEqual(failed["failed_probe_count"], 1)
            self.assertEqual(failed["first_failure"]["kind"], "input")

    def test_numeric_executor_protocol_is_ready_without_builtin_kernel(self) -> None:
        class RecordingExecutor:
            name = "recording-fixture"

            def __init__(self) -> None:
                self.operator_ids: list[str] = []

            def execute_stage(self, invocation, memory) -> None:  # type: ignore[no-untyped-def]
                self.operator_ids.append(invocation.stage.operator_id)
                memory.write(0x10, b"DONE")

        with tempfile.TemporaryDirectory() as temp_dir:
            package = _build_fixture(Path(temp_dir))
            prepared = prepare_hardware_simulation(package)
            executor = RecordingExecutor()
            memory = run_prepared_simulation(prepared, executor)
            self.assertEqual(executor.operator_ids, ["fixture-op"])
            self.assertEqual(memory.read(0x10, 4), b"DONE")


if __name__ == "__main__":
    unittest.main()
