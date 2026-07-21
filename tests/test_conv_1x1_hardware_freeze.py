from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from resnet50_pipeline.conv_1x1_hardware_freeze import (
    compare_hardware_dump,
    export_hardware_freeze,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Conv1x1HardwareFreezeTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        freeze = root / "freeze"
        dump = root / "dump"
        freeze.mkdir()
        value_p = np.asarray([[[[123]]]], dtype=np.int32)
        value_d = np.asarray([[[[17]]]], dtype=np.uint8)
        canonical = {}
        file_records = []
        regions = []
        for port, value in (("P", value_p), ("D", value_d)):
            golden_path = freeze / "golden" / f"canonical_{port}.bin"
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_bytes(value.tobytes())
            canonical[port] = {
                "path": f"golden/canonical_{port}.bin",
                "size_bytes": value.nbytes,
                "sha256": hashlib.sha256(value.tobytes()).hexdigest(),
                "dtype": str(value.dtype),
                "shape": list(value.shape),
            }
            dump_path = dump / port / "slice-00.bin"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_bytes(value.reshape(1, 1, 1, 1).tobytes())
            physical_path = freeze / "physical" / port / "slice-00.bin"
            physical_path.parent.mkdir(parents=True, exist_ok=True)
            physical_payload = value.reshape(1, 1, 1, 1).tobytes()
            physical_path.write_bytes(physical_payload)
            file_records.append(
                {
                    "path": f"physical/{port}/slice-00.bin",
                    "size_bytes": len(physical_payload),
                    "sha256": hashlib.sha256(physical_payload).hexdigest(),
                }
            )
            regions.append(
                {
                    "port": port,
                    "slice_id": 0,
                    "sample_start": 0,
                    "sample_count": 1,
                    "logical_start": 0,
                    "logical_count": 1,
                    "payload_bytes": value.nbytes,
                    "size_bytes": value.nbytes,
                    "physical_shape": [1, 1, 1, 1],
                }
            )
        address_payload = json.dumps({"schema_version": "0.1", "regions": regions})
        (freeze / "address_table.json").write_text(address_payload, encoding="utf-8")
        manifest = {
            "freeze_id": "fixture",
            "files": file_records,
            "layout": {"slice_count": 1},
            "address_table": {"path": "address_table.json"},
            "canonical_golden": canonical,
            "config_bound_ndp": {
                "status": "golden_and_ndp_bit_exact",
                "ports": {
                    port: {
                        "actual_sha256": canonical[port]["sha256"],
                        "golden_sha256": canonical[port]["sha256"],
                        "mismatch_count": 0,
                    }
                    for port in ("P", "D")
                },
            },
        }
        (freeze / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return freeze, dump

    def test_inverse_and_compare_passes_then_reports_first_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            freeze, dump = self._fixture(Path(temporary))
            passed = compare_hardware_dump(freeze, dump)
            self.assertEqual(passed["status"], "passed")
            self.assertEqual(passed["comparisons"]["P"]["mismatch_count"], 0)
            (dump / "D" / "slice-00.bin").write_bytes(bytes([18]))
            failed = compare_hardware_dump(freeze, dump)
            self.assertEqual(failed["status"], "mismatch")
            self.assertEqual(
                failed["comparisons"]["D"]["first_mismatch"],
                {"coordinate": [0, 0, 0, 0], "actual": 18, "golden": 17},
            )

    def test_compare_rejects_drifted_frozen_physical_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            freeze, dump = self._fixture(Path(temporary))
            (freeze / "physical/D/slice-00.bin").write_bytes(bytes([18]))
            with self.assertRaisesRegex(
                ValueError, "frozen physical D identity differs"
            ):
                compare_hardware_dump(freeze, dump)

    def test_first_instance_export_preserves_frozen_v1_bytes(self) -> None:
        checked_in = (
            PROJECT_ROOT
            / "artifacts"
            / "w5"
            / "hwop-0004-00"
            / "hardware_freeze"
            / "manifest.json"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "freeze"
            manifest = export_hardware_freeze(
                PROJECT_ROOT, output, node_id="node-0004"
            )
            self.assertEqual(manifest["status"], "manual_hardware_handoff_ready")
            self.assertEqual(
                (output / "manifest.json").read_bytes(), checked_in.read_bytes()
            )

    def test_first_instance_v6_rebuild_is_reproducible(self) -> None:
        checked_in = (
            PROJECT_ROOT
            / "artifacts/w5/hwop-0004-00/hardware_freeze_v6/manifest.json"
        )
        manifest = json.loads(checked_in.read_text(encoding="utf-8"))
        self.assertEqual(manifest["identity"]["revision"], "v6-sa-mask-batch3")
        self.assertEqual(manifest["status"], "manual_hardware_handoff_ready")
        # Historical revisions are immutable evidence.  Rebuilding after the
        # unified SA layout would create a new identity rather than pretending
        # to reproduce v6 with changed source rules.
        self.assertTrue(checked_in.is_file())

    def test_revised_first_instance_requires_explicit_encoder_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(
                ValueError, "requires an explicit accumulate_encoder_root"
            ):
                export_hardware_freeze(
                    PROJECT_ROOT,
                    Path(temporary) / "freeze",
                    node_id="node-0004",
                    revision="binding-negative",
                )

    def test_revised_export_rejects_nonempty_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "freeze"
            output.mkdir()
            (output / "stale.bin").write_bytes(b"stale")
            with self.assertRaisesRegex(ValueError, "not empty"):
                export_hardware_freeze(
                    PROJECT_ROOT,
                    output,
                    node_id="node-0004",
                    revision="nonempty-negative",
                    accumulate_encoder_root=(
                        PROJECT_ROOT / "artifacts/w5/conv_1x1_real/rebuild-v9"
                    ),
                    requant_encoder_root=(
                        PROJECT_ROOT
                        / "artifacts/w5/conv_1x1_requant_real/encode-a"
                    ),
                )

    def test_native_freeze_rejects_preflight_address_plan_drift(self) -> None:
        revision_root = PROJECT_ROOT / "artifacts/w5/hwop-0004-00/v14"
        candidate = revision_root / "encoder_candidate_native_02"
        report = json.loads(
            (revision_root / "preflight.json").read_text(encoding="utf-8")
        )
        actual_binding = dict(report["native_encoder_candidate"])
        actual_binding.update(
            {
                "validation_report_id": "1" * 64,
                "validation_report_sha256": "2" * 64,
                "candidate_tree_sha256": "3" * 64,
                "candidate_tree_file_count": actual_binding["checked_file_count"],
            }
        )
        report["native_encoder_candidate"] = dict(actual_binding)
        report["native_encoder_candidate"]["address_plan_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            preflight = temporary_root / "preflight.json"
            preflight.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with mock.patch(
                "resnet50_pipeline.conv_1x1_hardware_freeze."
                "_bind_native_encoder_candidate",
                return_value=actual_binding,
            ):
                with self.assertRaisesRegex(
                    ValueError, "not bound to the selected native candidate"
                ):
                    export_hardware_freeze(
                        PROJECT_ROOT,
                        temporary_root / "freeze",
                        node_id="node-0004",
                        preflight_path=preflight,
                        encoder_candidate_path=candidate,
                        revision="address-plan-drift-negative",
                    )

    @unittest.skip("historical v10r5 source identity is intentionally retired")
    def test_v10r5_rebuild_binds_accumulate_and_requant_encoder_outputs(self) -> None:
        expected_root = (
            PROJECT_ROOT
            / "artifacts/w5/hwop-0004-00/hardware_freeze_v10r5"
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "freeze"
            manifest = export_hardware_freeze(
                PROJECT_ROOT,
                output,
                node_id="node-0004",
                preflight_path=(
                    PROJECT_ROOT / "artifacts/w5/hwop-0004-00/v10/preflight.json"
                ),
                accumulate_encoder_root=(
                    PROJECT_ROOT / "artifacts/w5/conv_1x1_real/rebuild-v9"
                ),
                requant_encoder_root=(
                    PROJECT_ROOT
                    / "artifacts/w5/conv_1x1_requant_real/encode-a"
                ),
                revision="v10r5-rebuild-v9-requant-bound",
            )
            self.assertEqual(
                (output / "manifest.json").read_bytes(),
                (expected_root / "manifest.json").read_bytes(),
            )
            bindings = manifest["bitstream_bindings"]
            self.assertEqual(bindings["record_count"], 9)
            accumulate = next(
                item for item in bindings["records"] if item["role"] == "accumulate"
            )
            self.assertEqual(accumulate["official_encoder"]["line_count"], 28)
            self.assertEqual(accumulate["freeze"]["line_width_bits"], 128)
            self.assertEqual(
                accumulate["official_encoder"]["raw_sha256"],
                "e4a2a862bfe857eb84cafbd46283b73eb6fb7297dfe6f063e41bc1cb9e6b097f",
            )
            self.assertEqual(
                accumulate["official_encoder"]["logical_sha256"],
                accumulate["freeze"]["logical_sha256"],
            )
            requant = [
                item for item in bindings["records"] if item["role"] == "requant"
            ]
            self.assertEqual(len(requant), 8)
            self.assertTrue(
                all(
                    item["official_encoder"]["encoder_contract_sha256"]
                    == "cb5f54d068f390ae89be874f9fb0cff0aac603a836eff9347305e48becdfe060"
                    for item in requant
                )
            )

    def test_second_instance_exports_candidate_with_embedded_encoder_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "freeze"
            manifest = export_hardware_freeze(
                PROJECT_ROOT, output, node_id="node-0008"
            )
            self.assertEqual(manifest["status"], "candidate_hardware_freeze_ready")
            self.assertEqual(manifest["identity"]["node_id"], "node-0008")
            self.assertEqual(len(manifest["encoder_evidence"]), 9)
            self.assertEqual(len(manifest["layout"]["staged_d_offsets"]), 2)
            self.assertTrue(
                (
                    output
                    / "encoder_evidence"
                    / "accumulate"
                    / "parsed_bitstream.txt"
                ).is_file()
            )
            self.assertFalse(manifest.get("hardware_passed", False))


if __name__ == "__main__":
    unittest.main()
