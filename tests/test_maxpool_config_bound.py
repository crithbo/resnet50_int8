from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from NDPFuncModel.component.GeneralPEA import GeneralPEA
from resnet50_pipeline.adapters.ndp_rtl28_maxpool import NdpRtl28MaxPoolAdapter
from resnet50_pipeline.errors import PipelineError
from resnet50_pipeline.maxpool_instance import (
    INPUT_SAMPLE_BYTES,
    INPUT_TENSOR_ID,
    OUTPUT_REGION_OFFSET,
    OUTPUT_SAMPLE_BYTES,
    OUTPUT_TENSOR_ID,
    WAVE_ACTIVE_SLICES,
    build_maxpool_instance,
    load_maxpool_instance,
)
from resnet50_pipeline.pool28_layout import MaxPoolPhysicalLayout
from resnet50_pipeline.profile28 import GROUP4X7_BATCH_CHANNEL28_PROFILE


ROOT = Path(__file__).resolve().parents[1]
INSTANCE_ROOT = ROOT / "configs" / "maxpool" / "hwop-0002-00"


class MaxPoolInstanceTests(unittest.TestCase):
    def test_frozen_three_wave_schedule_is_derived_and_checked_in(self) -> None:
        manifest, configs = build_maxpool_instance(ROOT)
        loaded = load_maxpool_instance(ROOT, INSTANCE_ROOT)
        self.assertEqual(loaded.manifest, manifest)
        self.assertEqual(loaded.configs, configs)
        self.assertEqual([len(item) for item in WAVE_ACTIVE_SLICES], [28, 28, 8])
        self.assertEqual(
            [item["input_offset"] for item in manifest["waves"]],
            [0, INPUT_SAMPLE_BYTES, 2 * INPUT_SAMPLE_BYTES],
        )
        self.assertEqual(
            [item["output_offset"] for item in manifest["waves"]],
            [
                OUTPUT_REGION_OFFSET,
                OUTPUT_REGION_OFFSET + OUTPUT_SAMPLE_BYTES,
                OUTPUT_REGION_OFFSET + 2 * OUTPUT_SAMPLE_BYTES,
            ],
        )
        self.assertEqual(
            [item["stream_engine"]["stream0"]["base_addr"] for item in configs],
            [0, INPUT_SAMPLE_BYTES, 2 * INPUT_SAMPLE_BYTES],
        )

    def test_checked_in_config_mutation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_text:
            temp = Path(temp_text)
            for source in INSTANCE_ROOT.iterdir():
                if source.is_file():
                    (temp / source.name).write_bytes(source.read_bytes())
            wave = temp / "wave-1.json"
            value = json.loads(wave.read_text(encoding="utf-8"))
            value["stream_engine"]["stream0"]["base_addr"] += 16
            wave.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(PipelineError, "hash differs"):
                load_maxpool_instance(ROOT, temp)


class GeneralPeaUint8MaxTests(unittest.TestCase):
    def test_unsigned_byte_max_handles_signed_boundary_values(self) -> None:
        a = np.array([0, 127, 128, 255], dtype=np.uint8)
        b = np.array([255, 128, 127, 0], dtype=np.uint8)
        np.testing.assert_array_equal(
            GeneralPEA().max_pair(a, b), np.array([255, 128, 128, 255], dtype=np.uint8)
        )

    def test_nhwc_maxpool_uses_zero_spatial_padding(self) -> None:
        value = np.array(
            [
                [[255], [2], [3]],
                [[4], [128], [6]],
                [[7], [8], [9]],
            ],
            dtype=np.uint8,
        )
        actual = GeneralPEA().maxpool2d_nhwc(
            value,
            kernel_shape=(3, 3),
            strides=(2, 2),
            pads=(1, 1, 1, 1),
            dilations=(1, 1),
            padding_value=0,
        )
        np.testing.assert_array_equal(
            actual, np.array([[[255], [128]], [[128], [128]]], dtype=np.uint8)
        )


class RealMaxPoolConfigBoundIntegrationTests(unittest.TestCase):
    def test_real_w3_tensor_is_bit_exact_logically_and_physically(self) -> None:
        tensor_root = ROOT / "artifacts" / "w3" / "golden_batch16" / "tensors"
        activation = np.load(tensor_root / f"{INPUT_TENSOR_ID}.npy", allow_pickle=False)
        golden = np.load(tensor_root / f"{OUTPUT_TENSOR_ID}.npy", allow_pickle=False)
        layout = MaxPoolPhysicalLayout(profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE)
        bundle = layout.forward(
            activation=activation,
            output=golden,
            kernel_shape=(3, 3),
            strides=(2, 2),
            pads=(1, 1, 1, 1),
            dilations=(1, 1),
            spatial_padding_value=0,
            input_tail_value=0,
            output_tail_value=0,
            tensor_ids={"A": INPUT_TENSOR_ID, "D": OUTPUT_TENSOR_ID},
        )
        result = NdpRtl28MaxPoolAdapter(
            ROOT / "NDPFuncModel",
            python_executable=ROOT / ".venv" / "Scripts" / "python.exe",
            timeout_seconds=300,
        ).run(
            layout,
            bundle,
            instance=load_maxpool_instance(ROOT, INSTANCE_ROOT),
        )
        np.testing.assert_array_equal(result.output, golden)
        self.assertEqual(
            result.physical_probe.uint8_maxpool_jobs[0]["physical_mismatch_count"], 0
        )
        self.assertEqual(len(result.physical_probe.uint8_maxpool_jobs[0]["outputs"]), 28)
        self.assertFalse(result.target_simulator_validated)
        self.assertFalse(result.g6_validated)


if __name__ == "__main__":
    unittest.main()
