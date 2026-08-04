from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from resnet50_pipeline.deepseek_silu_holdout import (
    ARTIFACT_ROOT,
    CONTRACT_PATH,
    DeepSeekSiluHoldoutError,
    build_silu_graph,
    build_silu_holdout_contract,
    validate_bound_bitstream,
    validate_silu_graph_payload,
    validate_silu_holdout_contract,
    validate_silu_materialized_json_payload,
)
from resnet50_pipeline.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / CONTRACT_PATH
ARTIFACTS = ROOT / ARTIFACT_ROOT
OUTPUT_A = (
    ARTIFACTS / "a/t/model_execplan/output/ds_silu_v6"
)
MATERIALIZED_JSON = (
    OUTPUT_A / "jsons/op0_prefill_silu_fp16MN_fp32MN.json"
)
BITSTREAM = (
    OUTPUT_A
    / "config/op0/op0_prefill_silu_fp16MN_fp32MN_bitstream_128b.bin"
)


class DeepSeekSiluHoldoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checked = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_contract_matches_current_local_evidence(self) -> None:
        rebuilt = build_silu_holdout_contract(ROOT)
        self.assertEqual(self.checked, rebuilt)
        validate_silu_holdout_contract(self.checked, ROOT)

    def test_identity_and_release_boundaries_remain_fail_closed(self) -> None:
        self.assertEqual(
            self.checked["status"], "LOCAL_E2_REFERENCE_CONFORMANT"
        )
        self.assertFalse(self.checked["candidate_release"])
        self.assertFalse(self.checked["formal_target_config"])
        self.assertFalse(self.checked["server_package_generated"])
        self.assertEqual(
            self.checked["identity_boundary"][
                "onnx_repository_classification"
            ],
            "SEMANTIC_MODEL_MATCH",
        )
        self.assertFalse(
            self.checked["identity_boundary"]["original_source_identity"]
        )
        self.assertFalse(
            self.checked["identity_boundary"][
                "direct_onnx_shape_equals_stage"
            ]
        )
        self.assertTrue(
            self.checked["identity_boundary"]["crop_contract_required"]
        )

    def test_onnx_to_stage_and_stage_to_json_roundtrip(self) -> None:
        stage = self.checked["onnx_to_stage"]
        self.assertEqual(stage["source_shape"], [1, 32, 8])
        self.assertEqual(stage["crop_derived_shape"], [1, 32, 64])
        self.assertEqual(
            stage["fused_semantic_operator"], "SiLU(x)=x*Sigmoid(x)"
        )
        audit = self.checked["stage_to_json"]["materialized_audit"]
        self.assertEqual(audit["read_transaction_bytes"], 32)
        self.assertEqual(audit["read_occurrences_per_slice"], 128)
        self.assertEqual(audit["read_supply_bytes_per_slice"], 4096)
        self.assertEqual(audit["write_transaction_bytes"], 32)
        self.assertEqual(audit["write_occurrences_per_slice"], 256)
        self.assertEqual(audit["write_coverage_bytes_per_slice"], 8192)
        self.assertEqual(audit["ga_active_pe_count"], 8)
        self.assertEqual(
            audit["ga_output_path"], "normal_outbuffer_non_transout"
        )

    def test_bitstream_execplan_and_sca_are_bound(self) -> None:
        roundtrip = self.checked["json_to_bitstream_roundtrip"]
        decoded = roundtrip["decoded_selected_fields"]
        self.assertEqual(decoded["DRAM_LC.LC0.end"], 4)
        self.assertEqual(decoded["DRAM_LC.LC1.end"], 32)
        self.assertEqual(decoded["DRAM_LC.LC2.end"], 64)
        self.assertEqual(decoded["read.base_addr"], 0)
        self.assertEqual(decoded["write.base_addr"], 4096)
        lifecycle = roundtrip["lifecycle"]
        self.assertEqual(lifecycle["command_count"], 58)
        self.assertEqual(lifecycle["clock_enable_count"], 1)
        self.assertEqual(lifecycle["load_config_count"], 1)
        self.assertEqual(lifecycle["load_sfu_config_count"], 1)
        self.assertEqual(lifecycle["start_comp_count"], 1)
        self.assertEqual(
            lifecycle["ordered_command_classes"][0], "Clock_Enable"
        )
        self.assertEqual(
            lifecycle["ordered_command_classes"][-1], "Start_Comp"
        )
        sca = roundtrip["sca"]
        self.assertEqual(sca["input_a_slice_entries"], 28)
        self.assertEqual(sca["output_d_slice_entries"], 28)
        self.assertEqual(sca["output_d_128bit_lines_per_slice"], 512)

    def test_double_isolated_rebuild_is_exact_and_seed_bound(self) -> None:
        isolated = self.checked["isolated_rebuilds"]
        self.assertEqual(isolated["mapping_seed"], 42)
        self.assertEqual(isolated["python_hash_seed"], 0)
        self.assertTrue(
            isolated["comparison"]["deterministic_files_byte_identical"]
        )
        self.assertTrue(
            isolated["comparison"]["same_relative_file_set"]
        )
        for run_name in ("a", "b"):
            receipt = json.loads(
                (ARTIFACTS / run_name / "native_run_receipt.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(receipt["mapping_exact_penalty"], 0)
            self.assertEqual(
                receipt["initial_mapping_cache_file_count"], 0
            )
            self.assertEqual(
                receipt["mapping_determinism"]["seed"], 42
            )
            self.assertEqual(
                receipt["mapping_determinism"]["python_hash_seed"], 0
            )
            self.assertFalse(
                receipt["mapping_determinism"]["native_source_modified"]
            )

    def test_graph_tampering_fails_before_json_generation(self) -> None:
        graph = build_silu_graph(ROOT)
        mutations = (
            ("shape", [1, 32, 63]),
            ("dtype", "fp32"),
            ("type", "prefill_add_fp32MN_fp32MN_fp32MN"),
        )
        for field, value in mutations:
            with self.subTest(field=field):
                tampered = deepcopy(graph)
                if field == "shape":
                    tampered["operators"][0]["inputs"]["A"]["shape"] = value
                elif field == "dtype":
                    tampered["operators"][0]["inputs"]["A"]["dtype"] = value
                else:
                    tampered["operators"][0]["type"] = value
                with self.assertRaisesRegex(
                    DeepSeekSiluHoldoutError,
                    "differs from ONNX/crop/Stage evidence",
                ):
                    validate_silu_graph_payload(tampered, ROOT)

    def test_materialized_json_leaf_tamper_fails_closed(self) -> None:
        materialized = json.loads(
            MATERIALIZED_JSON.read_text(encoding="utf-8")
        )
        tampered = deepcopy(materialized)
        tampered["dram_loop_configs"]["LC1"]["end"] = 31
        with self.assertRaisesRegex(
            DeepSeekSiluHoldoutError,
            "LC domains differ",
        ):
            validate_silu_materialized_json_payload(tampered, ROOT)

    def test_bitstream_identity_tamper_fails_closed(self) -> None:
        expected_sha256 = sha256_file(BITSTREAM)
        with tempfile.TemporaryDirectory() as temporary:
            tampered_path = Path(temporary) / BITSTREAM.name
            shutil.copy2(BITSTREAM, tampered_path)
            payload = bytearray(tampered_path.read_bytes())
            payload[0] ^= 0x01
            tampered_path.write_bytes(payload)
            with self.assertRaisesRegex(
                DeepSeekSiluHoldoutError,
                "bitstream identity differs",
            ):
                validate_bound_bitstream(
                    tampered_path, expected_sha256
                )

    def test_contract_identity_tamper_fails_closed(self) -> None:
        tampered = deepcopy(self.checked)
        tampered["identity_boundary"][
            "onnx_repository_classification"
        ] = "ORIGINAL_SOURCE_IDENTITY"
        with self.assertRaisesRegex(
            DeepSeekSiluHoldoutError,
            "differs from current evidence",
        ):
            validate_silu_holdout_contract(tampered, ROOT)


if __name__ == "__main__":
    unittest.main()
