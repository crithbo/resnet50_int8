from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.strict_config_materialization import (
    StrictConfigMaterializationError,
    validate_materialized_strict_config,
)


ROOT = Path(__file__).resolve().parents[1]
CHECKED = (
    ROOT
    / "configs/native_ndp_sim/node0004_accumulate_wave0_nopp_r1_strict_v1"
)


class StrictConfigMaterializationTests(unittest.TestCase):
    def test_checked_node0004_cleanup_is_strict_and_bit_equivalent(self) -> None:
        manifest = validate_materialized_strict_config(CHECKED)
        self.assertEqual(
            manifest["adjudication"]["normalization_decision"],
            "approved-remove-native-ignored-write-fields",
        )
        self.assertEqual(
            {item["path"] for item in manifest["changes"]},
            {
                "$.stream_engine.stream4.padding_enable",
                "$.stream_engine.stream4.idx_padding_range",
            },
        )
        self.assertTrue(manifest["native_field_probe"]["all_equivalent"])

    def test_three_typed_null_gemm_cleanups_are_strict_and_approved(self) -> None:
        for name in (
            "prefill_gemm_local",
            "prefill_gemm_local_qkt",
            "prefill_gemm_ring_4slice",
        ):
            with self.subTest(name=name):
                manifest = validate_materialized_strict_config(
                    ROOT / f"configs/native_ndp_sim/{name}_strict_v1"
                )
                self.assertEqual(
                    manifest["adjudication"]["normalization_decision"],
                    "approved-typed-null-native-field-equivalent",
                )
                self.assertEqual(
                    [item["path"] for item in manifest["changes"]],
                    ["$.stream_engine.stream2.mem_idx_mode[2]"],
                )
                self.assertTrue(manifest["native_field_probe"]["all_equivalent"])

    def test_config_or_manifest_tamper_fails_closed(self) -> None:
        manifest = json.loads((CHECKED / "manifest.json").read_text(encoding="utf-8"))
        config = json.loads((CHECKED / "config.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config["CONFIG"] = "00000000"
            (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(
                StrictConfigMaterializationError, "normalized config identity"
            ):
                validate_materialized_strict_config(root)

            config = json.loads((CHECKED / "config.json").read_text(encoding="utf-8"))
            tampered = copy.deepcopy(manifest)
            tampered["native_field_probe"]["all_equivalent"] = False
            (root / "config.json").write_text(json.dumps(config), encoding="utf-8")
            tampered["normalized"]["sha256"] = __import__("hashlib").sha256(
                (root / "config.json").read_bytes()
            ).hexdigest()
            (root / "manifest.json").write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(
                StrictConfigMaterializationError, "equivalence/adjudication"
            ):
                validate_materialized_strict_config(root)


if __name__ == "__main__":
    unittest.main()
