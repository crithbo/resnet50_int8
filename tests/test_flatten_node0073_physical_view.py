from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.flatten_physical_view import (
    ACCEPTED_EVENT_ORDER,
    BINDING_SCHEMA,
    BYTE_COUNT,
    ELEMENT_COUNT,
    FlattenPhysicalViewError,
    INPUT_BYTE_STRIDES,
    OUTPUT_BYTE_STRIDES,
    SOURCE_BINDING_KEYS,
    build_node0073_view_assets,
    build_view_metadata,
    validate_binding_certificate,
    validate_view_metadata,
)
from resnet50_pipeline.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]


class FlattenNode0073PhysicalViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata = build_view_metadata(ROOT)

    def test_typed_identity_and_all_element_address_mapping_are_exact(self) -> None:
        metadata = self.metadata
        self.assertEqual(metadata["identity"]["request_id"], "r5:hwop-0073-00")
        self.assertEqual(
            metadata["logical_tensors"]["input"]["shape"], [16, 2048, 1, 1]
        )
        self.assertEqual(
            metadata["logical_tensors"]["output"]["shape"], [16, 2048]
        )
        proof = metadata["address_mapping_proof"]
        self.assertEqual(proof["enumerated_element_count"], ELEMENT_COUNT)
        self.assertTrue(proof["all_addresses_equal"])
        self.assertEqual(proof["first"]["address"], 0)
        self.assertEqual(proof["last"]["address"], BYTE_COUNT - 4)

    def test_no_arithmetic_json_or_hardware_work_is_emitted(self) -> None:
        materialization = self.metadata["materialization"]
        self.assertEqual(materialization["kind"], "execplan_metadata_zero_copy_alias")
        self.assertFalse(materialization["emit_arithmetic_json"])
        self.assertFalse(materialization["emit_mapping_or_bitstream"])
        self.assertEqual(materialization["hardware_instruction_count"], 0)
        self.assertEqual(materialization["hardware_memory_request_count"], 0)
        replay = self.metadata["input_replay_policy"]
        self.assertFalse(replay["input_or_constant_replay_enabled"])
        self.assertFalse(replay["host_precomputed_internal_tensor_enabled"])
        self.assertFalse(replay["host_precomputed_scaled_tensor_enabled"])
        self.assertFalse(replay["host_precomputed_rounded_tensor_enabled"])
        self.assertFalse(replay["host_precomputed_saturated_tensor_enabled"])
        self.assertFalse(replay["host_precomputed_final_tensor_enabled"])

    def test_target_local_e2_is_fail_closed_without_endpoint_binding(self) -> None:
        report = validate_view_metadata(self.metadata, ROOT)
        self.assertTrue(report["valid"])
        self.assertFalse(report["integrated_target_local_e2"])
        self.assertFalse(report["independent_target_local_e2"])
        self.assertFalse(report["claim_enabled"])
        self.assertEqual(report["status"], "ENDPOINT_BINDING_PENDING")
        self.assertIsNone(report["claim_label"])
        self.assertEqual(
            report["eligible_claim_label_after_binding"],
            "CONFIG_ONLY_CORRECTNESS_BASELINE",
        )
        self.assertFalse(report["input_replay_enabled"])
        self.assertFalse(report["host_precomputed_internal_tensor_used"])
        self.assertEqual(len(report["open_blockers"]), 4)

    def _positive_certificate(self, source_root: Path) -> dict:
        sources = {}
        for index, key in enumerate(SOURCE_BINDING_KEYS):
            path = source_root / f"{index}-{key}.json"
            path.write_text(
                json.dumps({"key": key}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            sources[key] = {
                "path": path.relative_to(source_root).as_posix(),
                "sha256": sha256_file(path),
            }
        base = 0x240000
        offset = 4096
        coverage_digest = __import__("hashlib").sha256()
        for address in range(base + offset, base + offset + BYTE_COUNT):
            coverage_digest.update(f"{address}\n".encode("ascii"))
        coverage = {
            "equation": (
                "required_byte_set={allocation_base+byte_offset+i | "
                "0<=i<131072}"
            ),
            "unique_byte_count": BYTE_COUNT,
            "first_address": base + offset,
            "last_address": base + offset + BYTE_COUNT - 1,
            "ordered_byte_set_sha256": coverage_digest.hexdigest(),
        }
        return {
            "schema": BINDING_SCHEMA,
            "storage_id": "activation:node0072:D",
            "allocation_owner_request_id": "r5:hwop-0072-00",
            "allocation_base": f"0x{base:X}",
            "producer_byte_offset": offset,
            "consumer_byte_offset": offset,
            "byte_span": BYTE_COUNT,
            "producer_byte_strides": list(INPUT_BYTE_STRIDES),
            "consumer_byte_strides": list(OUTPUT_BYTE_STRIDES),
            "order": "C",
            "dtype": "float32",
            "event_sequence": {
                event: index for index, event in enumerate(ACCEPTED_EVENT_ORDER)
            },
            "no_pending_or_replayed_consumer_reads_at_release": True,
            "producer_final_output_coverage": coverage,
            "consumer_final_input_coverage": coverage,
            "sources": sources,
        }

    def test_config_bound_certificate_closes_address_and_lifetime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary)
            certificate = self._positive_certificate(source_root)
            proof = validate_binding_certificate(
                self.metadata, certificate, source_root
            )
            self.assertTrue(proof["valid"])
            self.assertTrue(proof["accepted_handshake_lifetime_proven"])
            self.assertEqual(
                proof["address_mapping_proof"]["enumerated_element_count"],
                ELEMENT_COUNT,
            )
            self.assertEqual(
                proof["address_mapping_proof"]["first"]["address"],
                0x240000 + 4096,
            )

    def test_mismatched_offset_and_early_release_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source_root = Path(temporary)
            certificate = self._positive_certificate(source_root)
            bad_offset = copy.deepcopy(certificate)
            bad_offset["consumer_byte_offset"] += 4
            with self.assertRaisesRegex(
                FlattenPhysicalViewError, "byte offsets differ"
            ):
                validate_binding_certificate(
                    self.metadata, bad_offset, source_root
                )

            bad_release = copy.deepcopy(certificate)
            bad_release["event_sequence"]["allocation.release_accepted"] = 4
            with self.assertRaisesRegex(
                FlattenPhysicalViewError, "event order is not strict"
            ):
                validate_binding_certificate(
                    self.metadata, bad_release, source_root
                )

    def test_build_is_deterministic_and_stays_local_only(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            temp_root = Path(temporary)
            first = build_node0073_view_assets(
                ROOT,
                config_path=temp_root / "config.json",
                artifact_root=temp_root / "artifact",
                contract_path=temp_root / "contract.json",
            )
            first_bytes = {
                path: (temp_root / path).read_bytes()
                for path in ("config.json", "contract.json")
            }
            second = build_node0073_view_assets(
                ROOT,
                config_path=temp_root / "config.json",
                artifact_root=temp_root / "artifact",
                contract_path=temp_root / "contract.json",
            )
            self.assertEqual(first, second)
            self.assertEqual(first_bytes["config.json"], (temp_root / "config.json").read_bytes())
            self.assertEqual(first_bytes["contract.json"], (temp_root / "contract.json").read_bytes())
            self.assertFalse(first["server_package"])
            self.assertFalse(first["claim_enabled"])


if __name__ == "__main__":
    unittest.main()
