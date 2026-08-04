from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.ndp_patch_toolchain import (
    BASE_COMMIT,
    CONV_PATCHSET_ID,
    CONV_STEM_SERIALIZED_PATCHSET_ID,
    GAP_PATCHSET_ID,
    PATCHSET_ID,
    REQUANT_PATCHSET_ID,
    PatchsetError,
    build_patchset_manifest,
    materialize_patched_toolchain,
    validate_patchset_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


class NdpPatchToolchainTests(unittest.TestCase):
    def test_manifest_binds_clean_source_and_four_fail_closed_repairs(self) -> None:
        manifest = build_patchset_manifest(ROOT / "ndp-sim")
        self.assertEqual(manifest["patchset_id"], PATCHSET_ID)
        self.assertEqual(manifest["base_commit"], BASE_COMMIT)
        self.assertEqual(manifest["target_profile"]["rows_per_bank"], 6144)
        replacements = {
            replacement
            for item in manifest["files"]
            for replacement in item["replacement_ids"]
        }
        self.assertEqual(
            replacements,
            {
                "target-profile-row-count-6144",
                "direct-dram-lc-unmatched-name",
                "zero-penalty-search-return",
                "preserve-explicit-nonconnected-bindings",
            },
        )
        validate_patchset_manifest(manifest, ROOT / "ndp-sim")

    def test_materialization_is_isolated_and_executable_python(self) -> None:
        source_mapper = ROOT / "ndp-sim" / "bitstream" / "config" / "mapper.py"
        before = source_mapper.read_bytes()
        with tempfile.TemporaryDirectory() as temp_text:
            output = Path(temp_text) / "patched"
            manifest = materialize_patched_toolchain(ROOT / "ndp-sim", output)
            checked = json.loads(
                (output / "PATCHSET_MANIFEST.json").read_text(encoding="utf-8")
            )
            self.assertEqual(checked, manifest)
            planner = (
                output
                / "model_execplan"
                / "src"
                / "execution_plan_generator"
                / "address_planner.py"
            ).read_text(encoding="utf-8")
            mapper = (output / "bitstream" / "config" / "mapper.py").read_text(
                encoding="utf-8"
            )
            self.assertIn("MAX_ROWS = 6144", planner)
            self.assertNotIn("MAX_ROWS = 8192", planner)
            self.assertIn("return self.node_to_resource\n        else:", mapper)
            self.assertIn("self.node_to_resource.update(best_mapping)", mapper)
            self.assertIn("match = re.search(r'\\.LC(\\d+)$', node)", mapper)
        self.assertEqual(source_mapper.read_bytes(), before)

    def test_manifest_tamper_is_rejected(self) -> None:
        manifest = build_patchset_manifest(ROOT / "ndp-sim")
        manifest["target_profile"]["rows_per_bank"] = 8192
        with self.assertRaises(PatchsetError):
            validate_patchset_manifest(manifest, ROOT / "ndp-sim")

    def test_checked_in_manifest_is_exact(self) -> None:
        checked = json.loads(
            (ROOT / "contracts" / "ndp_patch_toolchain_v1.json").read_text(
                encoding="utf-8"
            )
        )
        validate_patchset_manifest(checked, ROOT / "ndp-sim")

    def test_gap_patchset_adds_only_exact_fail_closed_handler(self) -> None:
        manifest = build_patchset_manifest(
            ROOT / "ndp-sim",
            patchset_id=GAP_PATCHSET_ID,
        )
        self.assertEqual(manifest["patchset_id"], GAP_PATCHSET_ID)
        replacements = {
            replacement
            for item in manifest["files"]
            for replacement in item["replacement_ids"]
        }
        self.assertEqual(
            replacements,
            {
                "target-profile-row-count-6144",
                "direct-dram-lc-unmatched-name",
                "zero-penalty-search-return",
                "preserve-explicit-nonconnected-bindings",
                "register-exact-resnet50-gap-sum-handler",
            },
        )
        with tempfile.TemporaryDirectory() as temp_text:
            output = Path(temp_text) / "patched"
            materialize_patched_toolchain(
                ROOT / "ndp-sim",
                output,
                patchset_id=GAP_PATCHSET_ID,
            )
            control = (
                output
                / "model_execplan/src/execution_plan_generator/control_registers.py"
            ).read_text(encoding="utf-8")
            self.assertIn(
                '"resnet50_gap_sum_uint8_int32": '
                "_compute_resnet50_gap_sum_uint8_int32_control_register_updates",
                control,
            )

    def test_requant_patchset_registers_24_exact_wave_shard_types(self) -> None:
        manifest = build_patchset_manifest(
            ROOT / "ndp-sim",
            patchset_id=REQUANT_PATCHSET_ID,
        )
        replacements = {
            replacement
            for item in manifest["files"]
            for replacement in item["replacement_ids"]
        }
        self.assertIn(
            "register-exact-resnet50-node0004-requant-handlers",
            replacements,
        )
        with tempfile.TemporaryDirectory() as temp_text:
            output = Path(temp_text) / "patched"
            materialize_patched_toolchain(
                ROOT / "ndp-sim",
                output,
                patchset_id=REQUANT_PATCHSET_ID,
            )
            control = (
                output
                / "model_execplan/src/execution_plan_generator/control_registers.py"
            ).read_text(encoding="utf-8")
            for wave in range(3):
                for index in range(8):
                    self.assertIn(
                        f'"resnet50_requant_node0004_w{wave}_s{index:02d}": '
                        "_compute_resnet50_node0004_requant_control_register_updates",
                        control,
                    )

    def test_conv_patchset_registers_three_exact_wave_types(self) -> None:
        manifest = build_patchset_manifest(
            ROOT / "ndp-sim",
            patchset_id=CONV_PATCHSET_ID,
        )
        replacements = {
            replacement
            for item in manifest["files"]
            for replacement in item["replacement_ids"]
        }
        self.assertIn(
            "register-exact-resnet50-node0004-conv-wave-handlers",
            replacements,
        )
        with tempfile.TemporaryDirectory() as temp_text:
            output = Path(temp_text) / "patched"
            materialize_patched_toolchain(
                ROOT / "ndp-sim",
                output,
                patchset_id=CONV_PATCHSET_ID,
            )
            control = (
                output
                / "model_execplan/src/execution_plan_generator/control_registers.py"
            ).read_text(encoding="utf-8")
            for wave in range(3):
                self.assertIn(
                    f'"resnet50_conv_node0004_wave{wave}": '
                    "_compute_resnet50_node0004_conv_control_register_updates",
                    control,
                )

    def test_conv_stem_patchset_registers_exact_fresh_identity(self) -> None:
        manifest = build_patchset_manifest(
            ROOT / "ndp-sim",
            patchset_id=CONV_STEM_SERIALIZED_PATCHSET_ID,
        )
        self.assertEqual(
            manifest["patchset_sha256"],
            "216359f140740c149a28cb8c34a087ae50518cf851e831b457804c1fca6c381a",
        )
        replacements = {
            replacement
            for item in manifest["files"]
            for replacement in item["replacement_ids"]
        }
        self.assertIn(
            "register-exact-resnet50-stem-serialized-conv-handlers",
            replacements,
        )
        with tempfile.TemporaryDirectory() as temp_text:
            output = Path(temp_text) / "patched"
            materialize_patched_toolchain(
                ROOT / "ndp-sim",
                output,
                patchset_id=CONV_STEM_SERIALIZED_PATCHSET_ID,
            )
            control = (
                output
                / "model_execplan/src/execution_plan_generator/control_registers.py"
            ).read_text(encoding="utf-8")
            for wave in range(3):
                self.assertIn(
                    f'"resnet50_conv_stem_hwop0001_serialized_wave{wave}": '
                    "_compute_resnet50_stem_serialized_conv_control_register_updates",
                    control,
                )
            self.assertIn(
                '"A": ((1, 1, 9472), "int8")',
                control,
            )
            self.assertIn(
                '"B": ((1, 1, 7426048), "uint8")',
                control,
            )
            self.assertIn(
                "serialized stem Conv D must be int32 [1,1,200704]",
                control,
            )


if __name__ == "__main__":
    unittest.main()
