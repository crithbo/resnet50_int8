from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from resnet50_pipeline.node0004_assumed_hardware import (
    build_fresh_accumulate_base,
    build_tail_configs,
    fresh_conv_graph_spec,
    fresh_conv_wave_graph_spec,
    local_numeric_report,
    tail_graph_spec,
    tail_pair_graph_spec,
)
from resnet50_pipeline.operator_config_validator import OperatorConfigValidator
from tools.node0004_assumed_hardware_server_runtime import preflight


ROOT = Path(__file__).resolve().parents[1]


class Node0004AssumedHardwareTest(unittest.TestCase):
    def test_fresh_accumulate_is_strict(self) -> None:
        report = OperatorConfigValidator().validate(
            build_fresh_accumulate_base(ROOT), source="test"
        )
        self.assertTrue(report.valid, report.to_dict().get("first_error"))

    def test_conv_waves_reuse_one_local_allocation(self) -> None:
        from resnet50_pipeline.conv_native_package import build_strict_configs

        source = ROOT / "configs/native_ndp_sim/node0004_assumed_hardware_v1"
        if not (source / "accumulate_base.json").is_file():
            self.skipTest("fresh local materialization is not present")
        configs, manifest = build_strict_configs(
            ROOT,
            source_config_rel=source.relative_to(ROOT) / "accumulate_base.json",
            reuse_wave_addresses=True,
        )
        self.assertEqual(
            manifest["wave_address_policy"], "reuse_same_local_allocation"
        )
        addresses = []
        for config in configs.values():
            addresses.append(
                {
                    stream["target"]: int(stream["base_addr"], 0)
                    for stream in config["stream_engine"].values()
                }
            )
        self.assertEqual(addresses[0], addresses[1])
        self.assertEqual(addresses[1], addresses[2])

    def test_two_stage_tail_is_strict_and_complete(self) -> None:
        configs, manifest = build_tail_configs(ROOT)
        self.assertEqual(len(configs), 48)
        self.assertEqual(manifest["stage_count"], 48)
        for config in configs.values():
            report = OperatorConfigValidator().validate(config, source="test")
            self.assertTrue(report.valid, report.to_dict().get("first_error"))

    def test_conv_graph_declares_shared_activation_ports(self) -> None:
        for operator in fresh_conv_graph_spec()["operators"]:
            self.assertEqual(
                operator["inputs"]["B"]["shape"], [1, 1, 200704]
            )
            self.assertEqual(
                operator["inputs"]["B'"]["shape"], [1, 1, 200704]
            )
        for wave in range(3):
            selected = fresh_conv_wave_graph_spec(wave)
            self.assertEqual(len(selected["operators"]), 1)
            self.assertEqual(selected["operators"][0]["id"], f"op_w{wave}")

    def test_tail_pair_graphs_are_two_stage(self) -> None:
        for wave in range(3):
            for shard in range(8):
                selected = tail_pair_graph_spec(wave, shard)
                self.assertEqual(len(selected["operators"]), 2)
                mul, rounded = selected["operators"]
                self.assertEqual(
                    rounded["inputs"]["A"]["source"]["operator_id"],
                    mul["id"],
                )

    def test_tail_graph_pairs_producer_and_consumer(self) -> None:
        operators = tail_graph_spec()["operators"]
        self.assertEqual(len(operators), 48)
        for index in range(0, len(operators), 2):
            mul, rounded = operators[index : index + 2]
            self.assertEqual(
                rounded["inputs"]["A"]["source"]["operator_id"], mul["id"]
            )
            self.assertEqual(mul["output"]["dtype"], "fp32")
            self.assertEqual(rounded["output"]["dtype"], "uint8")

    def test_fresh_full_w3_replay(self) -> None:
        report = local_numeric_report(ROOT)
        self.assertEqual(report["element_count"], 3_211_264)
        self.assertEqual(report["dot4_group_count"], 51_380_224)
        self.assertEqual(report["accumulate_mismatch_count"], 0)
        self.assertEqual(report["tail_mismatch_count"], 0)
        self.assertTrue(report["magic_domain"]["finite"])

    def test_server_package_is_exact_and_ready_not_run(self) -> None:
        package_root = (
            ROOT
            / "artifacts/operator_config_validation/r5-server-test-packages"
            / "r5_node0004_hw_v1"
        )
        if not package_root.is_dir():
            self.skipTest("server package is not present")
        checked = preflight(package_root)
        self.assertTrue(checked["valid"])
        manifest = json.loads(
            (package_root / "package_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "PACKAGE_READY_NOT_RUN")
        self.assertEqual(manifest["compile_count"], 1)
        self.assertEqual(manifest["simulation_run_count"], 27)
        self.assertEqual(len(manifest["conv_run_ids"]), 3)
        self.assertEqual(len(manifest["tail_run_ids"]), 24)
        self.assertEqual(len(manifest["tail_materialization"]), 128)
        self.assertEqual(len(manifest["readback_checks"]), 320)
        self.assertFalse(manifest["server_source_preflight_performed"])
        zip_path = package_root.with_suffix(".zip")
        sidecar = Path(str(zip_path) + ".sha256")
        expected = sidecar.read_text(encoding="ascii").split()[0]
        self.assertEqual(
            hashlib.sha256(zip_path.read_bytes()).hexdigest(), expected
        )


if __name__ == "__main__":
    unittest.main()
