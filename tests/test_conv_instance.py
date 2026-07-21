from __future__ import annotations

import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.conv_instance import (
    FIRST_REAL_CONV_V1_BASELINE_SHA256,
    FIRST_REAL_CONV_V4_BASELINE_SHA256,
    FIRST_REAL_CONV_V5_BASELINE_SHA256,
    FIRST_REAL_CONV_V6_BASELINE_SHA256,
    FIRST_REAL_CONV_V8_BASELINE_SHA256,
    FIRST_REAL_CONV_V9_STATIC_SHA256,
    ConvInstanceError,
    audit_generated_conv_output_routes,
    build_conv_target_request,
    load_conv_instance_spec,
    validate_conv_accumulate_config_mask,
    validate_conv_accumulate_neighbor_ring,
    validate_conv_accumulate_output_route,
    validate_conv_requant_output_route,
)
from tools.generate_conv_1x1_real import build_real_1x1
from tools.generate_conv_1x1_requant_real import build_bundle


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _embedded_artifact_sha256(path: Path, role: str) -> str:
    request = json.loads(path.read_text(encoding="utf-8"))
    matches = [
        item
        for item in request["operators"][0]["config_artifacts"]
        if item.get("role") == role
    ]
    if len(matches) != 1:
        raise AssertionError(f"missing unique {role} artifact in {path}")
    return matches[0]["sha256"]


class ConvInstanceSpecTests(unittest.TestCase):
    def test_sa_accumulate_generator_forces_buffer5_to_special_array(self) -> None:
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        self.assertEqual(source["buffer_config"]["buffer5"]["dst_port"], 0)
        self.assertEqual(source["special_array"]["outport"]["mode"], "col")
        generated = build_real_1x1(source)
        self.assertEqual(generated["CONFIG"], "11101110")
        self.assertEqual(generated["buffer_config"]["buffer5"]["dst_port"], 0)
        self.assertEqual(generated["special_array"]["outport"]["mode"], "col")
        self.assertEqual(generated["buffer_config"]["buffer0"]["nbr_enable"], 1)
        self.assertEqual(generated["buffer_config"]["buffer1"]["nbr_enable"], 1)
        self.assertEqual(generated["buffer_config"]["buffer2"]["nbr_enable"], 0)
        self.assertEqual(generated["buffer_config"]["buffer3"]["nbr_enable"], 0)
        self.assertEqual(
            {item["buffer_nbr_cnt"] for item in generated["buffer_config"].values()},
            {3},
        )
        validate_conv_accumulate_config_mask(generated)
        validate_conv_accumulate_neighbor_ring(generated, expected_group_size=4)
        validate_conv_accumulate_output_route(generated)

    def test_first_request_rejects_kblock_only_bias_schedule(self) -> None:
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        generated = build_real_1x1(source)
        generated["stream_engine"]["stream3"].update(
            idx=["DRAM_LC.LC13", None, None],
            dim_stride=[32, None, None],
            mem_idx_mode=["buffer", None, None],
            mem_idx_keep_last_index=[0, None, None],
            buf_idx_keep_last_index=[1, 2],
            buf_full_last_index=0,
        )
        generated["buffer_loop_configs"]["GROUP2"]["ROW_LC"].update(
            src_id="DRAM_LC.LC13", last_index=1
        )
        generated["buffer_loop_configs"]["GROUP2"]["COL_LC"]["last_index"] = 2
        generated["buffer_config"]["buffer4"].update(
            buf_full_last_index=0, buffer_life_time=1
        )
        from resnet50_pipeline.conv_sa_contract import validate_first_conv_sa_contract

        with self.assertRaisesRegex(ValueError, "Kblock/H/Qblock bias tile branch"):
            validate_first_conv_sa_contract(generated)

    def test_sa_accumulate_neighbor_ring_rejects_missing_odd_buffer(self) -> None:
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        generated = build_real_1x1(source)
        generated["buffer_config"]["buffer1"]["nbr_enable"] = 0
        with self.assertRaisesRegex(ConvInstanceError, "buffer1.nbr_enable"):
            validate_conv_accumulate_neighbor_ring(generated, expected_group_size=4)

    def test_sa_accumulate_neighbor_ring_rejects_encoder_default_count(self) -> None:
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        generated = build_real_1x1(source)
        generated["buffer_config"]["buffer0"]["buffer_nbr_cnt"] = 27
        with self.assertRaisesRegex(ConvInstanceError, "buffer0.buffer_nbr_cnt"):
            validate_conv_accumulate_neighbor_ring(generated, expected_group_size=4)

    def test_sa_accumulate_rejects_broad_sa_ga_presence_mask(self) -> None:
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        generated = build_real_1x1(source)
        generated["CONFIG"] = "11111111"
        with self.assertRaisesRegex(ConvInstanceError, "11101110"):
            validate_conv_accumulate_config_mask(generated)

    def test_sa_accumulate_route_invariant_rejects_gene_array_producer(self) -> None:
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        generated = build_real_1x1(source)
        broken = deepcopy(generated)
        broken["buffer_config"]["buffer5"]["dst_port"] = 1
        with self.assertRaisesRegex(ConvInstanceError, "SpecArray producer"):
            validate_conv_accumulate_output_route(broken)
        broken["buffer_config"]["buffer5"]["dst_port"] = True
        with self.assertRaisesRegex(ConvInstanceError, "integer 0 or 1"):
            validate_conv_accumulate_output_route(broken)

    def test_sa_accumulate_rejects_encoder_label_for_rtl_col_major(self) -> None:
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        broken = build_real_1x1(source)
        broken["special_array"]["outport"]["mode"] = "row"
        with self.assertRaisesRegex(ConvInstanceError, "sa_outport_major=0"):
            validate_conv_accumulate_output_route(broken)

    def test_ga_requant_route_invariant_rejects_special_array_producer(self) -> None:
        requant = json.loads(
            (ROOT / "conv_1x1_requant_real/shard-00.json").read_text(encoding="utf-8")
        )
        validate_conv_requant_output_route(requant)
        broken = deepcopy(requant)
        broken["buffer_config"]["buffer5"]["dst_port"] = 0
        with self.assertRaisesRegex(ConvInstanceError, "GeneArray producer"):
            validate_conv_requant_output_route(broken)

    def test_all_mutable_generated_conv_routes_are_audited(self) -> None:
        report = audit_generated_conv_output_routes(ROOT)
        self.assertEqual(report["status"], "generated_conv_output_routes_passed")
        self.assertEqual(report["accumulate_config_count"], 6)
        self.assertEqual(report["requant_config_count"], 128)
        self.assertEqual(report["config_count"], 134)
        self.assertTrue(report["historical_freezes_excluded"])

    def test_first_real_instance_is_one_typed_source_for_all_consumers(self) -> None:
        request = build_conv_target_request(ROOT)
        spec = request.spec
        self.assertEqual(spec.node_id, "node-0004")
        self.assertEqual(
            (spec.accumulate_hw_op_id, spec.requant_hw_op_id),
            ("hwop-0004-00", "hwop-0004-01"),
        )
        self.assertEqual(spec.activation_shape, (16, 64, 56, 56))
        self.assertEqual(spec.weight_shape, (64, 64, 1, 1))
        self.assertEqual(spec.output_shape, (16, 64, 56, 56))
        self.assertEqual((spec.c_tile, spec.k_tile), (16, 16))
        self.assertEqual(spec.requant_shard_count, 8)
        self.assertEqual(
            (spec.n2n_mem_loop, spec.n2n_src_slice_sel, spec.n2n_dst_slice_sel),
            (4, 1, 1),
        )
        self.assertEqual(len(spec.tensor_bindings), 11)
        request.validate_checked_in_bindings()

    def test_parameterized_generators_preserve_first_instance_bytes(self) -> None:
        request = build_conv_target_request(ROOT)
        source = json.loads((ROOT / "conv_full.json").read_text(encoding="utf-8"))
        generated_config = (
            json.dumps(
                build_real_1x1(source, request.spec),
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        ).encode("utf-8")
        self.assertEqual(generated_config, request.accumulate_config_path.read_bytes())
        _manifest, generated_requant = build_bundle(request.spec)
        for name, payload in generated_requant.items():
            self.assertEqual(payload, (request.requant_root / name).read_bytes())

    @unittest.skip("historical v4-v9 package artifacts were intentionally removed")
    def test_frozen_first_instance_hashes_do_not_drift(self) -> None:
        observed_v1 = {
            "accumulate_config": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze/configs/conv_1x1_real.json"
            ),
            "requant_manifest": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze/configs/requant/manifest.json"
            ),
            "preflight": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/preflight.json"
            ),
            "hardware_freeze_manifest": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/hardware_freeze/manifest.json"
            ),
        }
        self.assertEqual(observed_v1, FIRST_REAL_CONV_V1_BASELINE_SHA256)

        observed_v4 = {
            "accumulate_config": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze_v4/configs/conv_1x1_real.json"
            ),
            "semantic_contract": json.loads(
                (ROOT / "artifacts/w5/hwop-0004-00/v4/execplan_request.json").read_text(
                    encoding="utf-8"
                )
            )["operators"][0]["config_artifacts"][1]["sha256"],
            "execplan_request": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v4/execplan_request.json"
            ),
            "preflight": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v4/preflight.json"
            ),
            "hardware_freeze_manifest": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/hardware_freeze_v4/manifest.json"
            ),
            "hardware_execplan_manifest": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v4/manifest.json"
            ),
        }
        self.assertEqual(observed_v4, FIRST_REAL_CONV_V4_BASELINE_SHA256)

        observed_v5 = {
            "accumulate_config": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze_v5/configs/conv_1x1_real.json"
            ),
            "semantic_contract": json.loads(
                (ROOT / "artifacts/w5/hwop-0004-00/v5/execplan_request.json").read_text(
                    encoding="utf-8"
                )
            )["operators"][0]["config_artifacts"][1]["sha256"],
            "execplan_request": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v5/execplan_request.json"
            ),
            "preflight": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v5/preflight.json"
            ),
            "hardware_freeze_manifest": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/hardware_freeze_v5/manifest.json"
            ),
            "hardware_execplan_manifest": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v5/manifest.json"
            ),
        }
        self.assertEqual(observed_v5, FIRST_REAL_CONV_V5_BASELINE_SHA256)

        observed_v6 = {
            "accumulate_config": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze_v6/configs/conv_1x1_real.json"
            ),
            "semantic_contract": json.loads(
                (ROOT / "artifacts/w5/hwop-0004-00/v6/execplan_request.json").read_text(
                    encoding="utf-8"
                )
            )["operators"][0]["config_artifacts"][1]["sha256"],
            "execplan_request": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v6/execplan_request.json"
            ),
            "preflight": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v6/preflight.json"
            ),
            "hardware_freeze_manifest": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/hardware_freeze_v6/manifest.json"
            ),
            "hardware_execplan_manifest": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v6/manifest.json"
            ),
        }
        self.assertEqual(observed_v6, FIRST_REAL_CONV_V6_BASELINE_SHA256)

        observed_v8 = {
            "accumulate_config": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_freeze_v8/configs/conv_1x1_real.json"
            ),
            "semantic_contract": _embedded_artifact_sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v8/execplan_request.json",
                "semantic_contract",
            ),
            "execplan_request": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v8/execplan_request.json"
            ),
            "preflight": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v8/preflight.json"
            ),
            "hardware_freeze_manifest": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/hardware_freeze_v8/manifest.json"
            ),
            "hardware_execplan_manifest": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v8/manifest.json"
            ),
        }
        self.assertEqual(observed_v8, FIRST_REAL_CONV_V8_BASELINE_SHA256)

        observed_v9 = {
            "accumulate_config": _sha256(ROOT / "conv_1x1_real.json"),
            "semantic_contract": _embedded_artifact_sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v9/execplan_request.json",
                "semantic_contract",
            ),
            "execplan_request": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v9/execplan_request.json"
            ),
            "preflight": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/v9/preflight.json"
            ),
            "hardware_freeze_manifest": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/hardware_freeze_v9/manifest.json"
            ),
            "hardware_execplan_manifest": _sha256(
                ROOT
                / "artifacts/w5/hwop-0004-00/hardware_execplan_server_v9/manifest.json"
            ),
            "server_overlay_zip": _sha256(
                ROOT / "artifacts/w5/hwop-0004-00/server_overlay_v9.zip"
            ),
        }
        self.assertEqual(observed_v9, FIRST_REAL_CONV_V9_STATIC_SHA256)

    def test_second_and_third_instances_are_bound_without_freezing_the_next(self) -> None:
        second_request = build_conv_target_request(ROOT, "node-0008")
        second = second_request.spec
        wide_output_request = build_conv_target_request(ROOT, "node-0003")
        wide_output = wide_output_request.spec
        self.assertEqual(second.activation_shape, (16, 256, 56, 56))
        self.assertEqual(second.output_shape, (16, 64, 56, 56))
        self.assertEqual((second.c_tile, second.k_tile), (64, 16))
        self.assertEqual(wide_output.activation_shape, (16, 64, 56, 56))
        self.assertEqual(wide_output.output_shape, (16, 256, 56, 56))
        self.assertEqual((wide_output.c_tile, wide_output.k_tile), (16, 64))
        self.assertEqual(wide_output.requant_shard_count, 32)
        second_request.validate_checked_in_bindings()
        wide_output_request.validate_checked_in_bindings()
        with self.assertRaisesRegex(ConvInstanceError, "files are missing"):
            build_conv_target_request(ROOT, "node-0005")

    def test_non_conv_or_unknown_node_fails_closed(self) -> None:
        with self.assertRaises(ConvInstanceError):
            load_conv_instance_spec(ROOT, "node-0002")
        with self.assertRaises(ConvInstanceError):
            load_conv_instance_spec(ROOT, "node-does-not-exist")


if __name__ == "__main__":
    unittest.main()
