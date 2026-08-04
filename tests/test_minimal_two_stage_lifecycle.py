from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from resnet50_pipeline.hardware_simulation_frontend import (
    HardwareSimulationPreparationError,
    StageInvocation,
    prepare_hardware_simulation,
    validate_runtime_lifecycle,
)
from resnet50_pipeline.minimal_two_stage_lifecycle import (
    BYTE_COUNT,
    RULE_IDS,
    SHAPE,
    STAGE0_ID,
    STAGE1_ID,
    build_generation_receipt,
    build_typed_request,
    run_local_e2,
)


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(__import__("sys").executable)


class MinimalTwoStageLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.artifact = Path(cls.temporary.name) / "lifecycle"
        cls.result = run_local_e2(
            ROOT,
            artifact_root=cls.artifact,
            python_executable=PYTHON,
        )
        cls.package = cls.artifact / "local_package"
        cls.prepared = prepare_hardware_simulation(cls.package)
        cls.report = json.loads(
            (cls.artifact / "local_e2_report.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_generation_receipt_and_typed_edge_are_exact(self) -> None:
        receipt = build_generation_receipt(ROOT)
        request = build_typed_request()
        self.assertEqual(receipt["rule_ids"], list(RULE_IDS))
        self.assertFalse(receipt["scope"]["candidate_release"])
        self.assertFalse(receipt["scope"]["server_package"])
        self.assertEqual(len(request["operators"]), 2)
        consumer = request["operators"][1]
        self.assertEqual(
            consumer["inputs"]["A"]["source"],
            {"type": "operator", "operator_id": STAGE0_ID},
        )
        self.assertEqual(consumer["inputs"]["A"]["shape"], list(SHAPE))

    def test_full_native_lifecycle_and_dual_golden_pass(self) -> None:
        self.assertEqual(
            self.report["status"],
            "MINIMAL_TWO_STAGE_LIFECYCLE_LOCAL_E2_COMPLETE",
        )
        self.assertTrue(
            self.report["native_double_rebuild"]["all_products_identical"]
        )
        lifecycle = self.report["transport_and_state"]["runtime_lifecycle"]
        self.assertTrue(lifecycle["validated"])
        self.assertEqual(lifecycle["runtime_sequence"], [STAGE0_ID, STAGE1_ID])
        self.assertEqual(lifecycle["repeat_num"], 2)
        self.assertEqual(lifecycle["start_comp_count"], 2)
        self.assertEqual(lifecycle["completion_barrier_count"], 2)
        self.assertEqual(lifecycle["dependency"]["byte_count"], BYTE_COUNT)
        self.assertFalse(lifecycle["dependency"]["consumer_external_preload"])
        self.assertEqual(
            len({item["address"] for item in lifecycle["config_reload"]}), 2
        )
        self.assertEqual(
            len({item["sha256"] for item in lifecycle["config_reload"]}), 2
        )
        numeric = self.report["numeric_execution"]
        self.assertTrue(numeric["stage0_golden_bit_exact"])
        self.assertTrue(numeric["stage1_golden_bit_exact"])
        self.assertTrue(numeric["consumer_read_stage0_output_same_address"])

    def test_runtime_sca_does_not_preload_producer_backed_input(self) -> None:
        native_sca = json.loads(
            (
                self.artifact / "native_evidence/native_sca_cfg.json"
            ).read_text(encoding="utf-8")
        )
        runtime_sca = self.prepared.sca
        key = f"{STAGE1_ID}_matrixA_slice0"
        self.assertIn(key, native_sca)
        self.assertNotIn(key, runtime_sca)
        self.assertEqual(
            self.prepared.runtime_lifecycle["dependency"]["base_addr"],
            "0x00000480",
        )

    def test_artifact_manifest_enumerates_nested_package_manifest(self) -> None:
        manifest = json.loads(
            (self.artifact / "manifest.json").read_text(encoding="utf-8")
        )
        recorded = {item["path"] for item in manifest["files"]}
        actual = {
            path.relative_to(self.artifact).as_posix()
            for path in self.artifact.rglob("*")
            if path.is_file() and path != self.artifact / "manifest.json"
        }
        self.assertEqual(recorded, actual)
        self.assertIn("local_package/manifest.json", recorded)

    def _validate(
        self,
        *,
        manifest: dict | None = None,
        sca: dict | None = None,
        runner: dict | None = None,
        stages=None,  # type: ignore[no-untyped-def]
        invocations=None,  # type: ignore[no-untyped-def]
    ) -> dict:
        return validate_runtime_lifecycle(
            package_root=self.package,
            manifest=manifest or copy.deepcopy(self.prepared.manifest),
            sca=sca or copy.deepcopy(self.prepared.sca),
            sca_d=copy.deepcopy(self.prepared.sca_d),
            runner=runner or copy.deepcopy(self.prepared.runner_contract),
            stages=stages or list(self.prepared.stages),
            invocations=invocations or list(self.prepared.invocations),
        )

    def test_dependency_address_and_preload_tamper_fail_closed(self) -> None:
        manifest = copy.deepcopy(self.prepared.manifest)
        dependency = manifest["runtime_lifecycle"]["dependencies"][0]
        dependency["consumer_base_addr"] = "0x00000490"
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "dtype/shape/bytes/address"
        ):
            self._validate(manifest=manifest)

        sca = copy.deepcopy(self.prepared.sca)
        sca[f"{STAGE1_ID}_matrixA_slice0"] = {
            "base_addr": "0x00000480",
            "path": "install/data/op0_A.bin",
        }
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "must not be externally preloaded"
        ):
            self._validate(sca=sca)

    def test_repeat_runner_and_final_barrier_tamper_fail_closed(self) -> None:
        sca = copy.deepcopy(self.prepared.sca)
        sca["Repeat_Num"] = 1
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "Repeat_Num differs"
        ):
            self._validate(sca=sca)

        runner = copy.deepcopy(self.prepared.runner_contract)
        runner["execution"]["completion_gate"]["expected_start_comp_count"] = 1
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError,
            "expected_start_comp_count differs",
        ):
            self._validate(runner=runner)

        stages = list(self.prepared.stages)
        stages[-1] = replace(stages[-1], completion_barrier=None)
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError, "barrier differs"
        ):
            self._validate(stages=stages)

    def test_second_stage_stale_config_reuse_fails_closed(self) -> None:
        invocations = list(self.prepared.invocations)
        first = next(
            value
            for value in invocations[0].loaded_configs.values()
            if not value.config_sfu
        )
        second = next(
            value
            for value in invocations[1].loaded_configs.values()
            if not value.config_sfu
        )
        stale = replace(
            second,
            address=first.address,
            payload=first.payload,
            sha256=first.sha256,
        )
        stale_map = {
            key: (stale if not value.config_sfu else value)
            for key, value in invocations[1].loaded_configs.items()
        }
        invocations[1] = StageInvocation(
            stage=invocations[1].stage,
            loaded_configs=stale_map,
            register_values=invocations[1].register_values,
        )
        with self.assertRaisesRegex(
            HardwareSimulationPreparationError,
            "not independently addressed and identified",
        ):
            self._validate(invocations=invocations)


if __name__ == "__main__":
    unittest.main()
