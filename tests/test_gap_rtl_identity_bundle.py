from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_gap_rtl_identity_bundle import build_bundle
from tools.capture_gap_probe_server_identity import FOCUS_RTL_RELS
from tools.capture_gap_rtl_three_way_identity import capture_three_way_identity


ROOT = Path(__file__).resolve().parents[1]


class GapRtlIdentityBundleTests(unittest.TestCase):
    def test_capture_is_read_only_and_classifies_matching_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            ndp = temp / "NDP_copy02"
            focus_rel = FOCUS_RTL_RELS[0]
            focus_path = ndp / focus_rel
            focus_path.parent.mkdir(parents=True)
            focus_path.write_text(
                "module focused; endmodule\n", encoding="utf-8"
            )
            manifest = temp / "IDENTITY_BUNDLE_MANIFEST.json"
            from tools.capture_gap_probe_server_identity import (
                text_file_identity,
            )

            canonical = text_file_identity(focus_path)[
                "canonical_text_sha256"
            ]
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "identity-test",
                        "reference_server_identity": {
                            "rtl_tree": {},
                            "focus_rtl_files": {
                                focus_rel.as_posix(): {
                                    "canonical_text_sha256": canonical
                                }
                            },
                        },
                        "github_reference_identity": {
                            "files": {
                                focus_rel.as_posix(): {
                                    "github_canonical_text_sha256": canonical
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = capture_three_way_identity(
                ndp_root=ndp,
                identity_manifest_path=manifest,
            )

            self.assertTrue(report["operation"]["read_only"])
            self.assertFalse(report["operation"]["testbench_modified"])
            self.assertFalse(report["operation"]["compile_started"])
            self.assertFalse(report["operation"]["simulation_started"])
            self.assertEqual(
                report["reference_comparison"][
                    "focus_rtl_three_way_classification"
                ][focus_rel.as_posix()],
                "all_three_match",
            )

    def test_bundle_contains_no_test_or_hdl_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "gap_rtl_identity"
            report = build_bundle(ROOT, output)

            self.assertFalse(
                report["operation_policy"]["contains_workload"]
            )
            self.assertFalse(
                report["operation_policy"]["contains_observer"]
            )
            self.assertFalse(
                report["operation_policy"]["starts_compile_or_simulation"]
            )
            with zipfile.ZipFile(report["zip"]) as archive:
                names = archive.namelist()
            lowered = [name.lower() for name in names]
            self.assertFalse(any("/workload/" in name for name in lowered))
            self.assertFalse(any("observer" in name for name in lowered))
            self.assertFalse(
                any(
                    name.endswith((".v", ".sv", ".svh"))
                    for name in lowered
                )
            )


if __name__ == "__main__":
    unittest.main()
