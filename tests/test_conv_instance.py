from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from resnet50_pipeline.conv_instance import (
    FIRST_REAL_CONV_BASELINE_SHA256,
    ConvInstanceError,
    build_conv_target_request,
    load_conv_instance_spec,
)
from tools.generate_conv_1x1_real import build_real_1x1
from tools.generate_conv_1x1_requant_real import build_bundle


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ConvInstanceSpecTests(unittest.TestCase):
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

    def test_frozen_first_instance_hashes_do_not_drift(self) -> None:
        request = build_conv_target_request(ROOT)
        observed = {
            "accumulate_config": _sha256(request.accumulate_config_path),
            "requant_manifest": _sha256(request.requant_manifest_path),
            "preflight": _sha256(request.preflight_path),
        }
        self.assertEqual(
            observed,
            {
                key: FIRST_REAL_CONV_BASELINE_SHA256[key]
                for key in observed
            },
        )
        if request.hardware_freeze_manifest_path.is_file():
            self.assertEqual(
                _sha256(request.hardware_freeze_manifest_path),
                FIRST_REAL_CONV_BASELINE_SHA256["hardware_freeze_manifest"],
            )

    def test_second_real_instance_is_bound_and_third_is_not_prematurely_frozen(self) -> None:
        second_request = build_conv_target_request(ROOT, "node-0008")
        second = second_request.spec
        wide_output = load_conv_instance_spec(ROOT, "node-0003")
        self.assertEqual(second.activation_shape, (16, 256, 56, 56))
        self.assertEqual(second.output_shape, (16, 64, 56, 56))
        self.assertEqual((second.c_tile, second.k_tile), (64, 16))
        self.assertEqual(wide_output.activation_shape, (16, 64, 56, 56))
        self.assertEqual(wide_output.output_shape, (16, 256, 56, 56))
        self.assertEqual((wide_output.c_tile, wide_output.k_tile), (16, 64))
        self.assertEqual(wide_output.requant_shard_count, 32)
        second_request.validate_checked_in_bindings()
        with self.assertRaisesRegex(ConvInstanceError, "files are missing"):
            build_conv_target_request(ROOT, "node-0003")

    def test_non_conv_or_unknown_node_fails_closed(self) -> None:
        with self.assertRaises(ConvInstanceError):
            load_conv_instance_spec(ROOT, "node-0002")
        with self.assertRaises(ConvInstanceError):
            load_conv_instance_spec(ROOT, "node-does-not-exist")


if __name__ == "__main__":
    unittest.main()
