from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.capture_gap_probe_server_identity import (
    FOCUS_RTL_RELS,
    canonical_text_sha256,
    capture_identity,
    text_file_identity,
    tree_identity,
)


class GapProbeServerIdentityTests(unittest.TestCase):
    def test_captures_artifacts_and_compares_frozen_rtl_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ndp = root / "NDP_copy02"
            (ndp / "rtl" / "filelists").mkdir(parents=True)
            (ndp / "rtl" / "unit.sv").write_text(
                "module unit; endmodule\n", encoding="utf-8"
            )
            focus_rel = FOCUS_RTL_RELS[0]
            focus_path = ndp / focus_rel
            focus_path.parent.mkdir(parents=True)
            focus_path.write_text(
                "module focused; endmodule\n", encoding="utf-8"
            )
            (ndp / "rtl" / "filelists" / "NDP_Top_phy_filelist.f").write_text(
                "../unit.sv\n", encoding="utf-8"
            )
            (ndp / "tb_NDP_Top_new_phy.sv").write_text(
                "module tb_NDP_Top_new_phy; endmodule\n", encoding="utf-8"
            )
            (ndp / "Makefile.tb_NDP_Top_new_phy").write_text(
                "sim:\n\t@true\n", encoding="utf-8"
            )
            install = ndp / "install"
            cfg = install / "cfg_pkg" / "gap_hwop0071_sum_probe_v2"
            cfg.mkdir(parents=True)
            (install / "bitstream.txt").write_text("bits\n", encoding="utf-8")
            (install / "execplan.txt").write_text("plan\n", encoding="utf-8")
            (cfg / "sca_cfg.json").write_text("{}\n", encoding="utf-8")
            (cfg / "sca_cfg_D.json").write_text("{}\n", encoding="utf-8")

            package_manifest = root / "TEST_PACKAGE_MANIFEST.json"
            reference_tree = tree_identity(ndp / "rtl")
            focus_identity = text_file_identity(focus_path)
            package_manifest.write_text(
                json.dumps(
                    {
                        "schema": "resnet50-gap-probe-test-package-v2",
                        "install_name": "gap_hwop0071_sum_probe_v2",
                        "payload_tree_sha256": "payload",
                        "source_workload": {"tree_sha256": "workload"},
                        "reference_server_identity": {
                            "rtl_tree": reference_tree,
                            "focus_rtl_files": {
                                focus_rel.as_posix(): focus_identity
                            },
                        },
                        "github_reference_identity": {
                            "files": {
                                focus_rel.as_posix(): {
                                    "github_canonical_text_sha256": (
                                        focus_identity[
                                            "canonical_text_sha256"
                                        ]
                                    )
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = capture_identity(
                ndp_root=ndp,
                package_manifest_path=package_manifest,
                install_name="gap_hwop0071_sum_probe_v2",
                phase="pre_install",
                server_command="make compile sim",
            )

            self.assertEqual(report["ndp_root"], ndp.resolve().as_posix())
            self.assertTrue(report["artifacts"]["testbench"]["exists"])
            self.assertTrue(report["artifacts"]["active_filelist"]["exists"])
            self.assertTrue(
                report["reference_comparison"]["rtl_tree_matches_reference"]
            )
            self.assertIsNone(report["exit_status"])
            self.assertEqual(
                report["reference_comparison"][
                    "focus_rtl_three_way_classification"
                ][focus_rel.as_posix()],
                "all_three_match",
            )

            (ndp / "rtl" / "unit.sv").write_text(
                "module unit; wire changed; endmodule\n", encoding="utf-8"
            )
            focus_path.write_text(
                "module focused; wire changed; endmodule\n", encoding="utf-8"
            )
            changed = capture_identity(
                ndp_root=ndp,
                package_manifest_path=package_manifest,
                install_name="gap_hwop0071_sum_probe_v2",
                phase="post_run",
                server_command="make compile sim",
                exit_status=7,
            )
            self.assertFalse(
                changed["reference_comparison"]["rtl_tree_matches_reference"]
            )
            self.assertEqual(
                changed["reference_comparison"][
                    "focus_rtl_three_way_classification"
                ][focus_rel.as_posix()],
                "server_differs_from_matching_references",
            )
            self.assertEqual(changed["exit_status"], 7)

    def test_canonical_text_hash_ignores_line_endings_and_trailing_lf(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / "left.sv"
            right = root / "right.sv"
            left.write_bytes(b"module unit;\r\nendmodule\r\n\r\n")
            right.write_bytes(b"module unit;\nendmodule")

            self.assertEqual(
                canonical_text_sha256(left),
                canonical_text_sha256(right),
            )


if __name__ == "__main__":
    unittest.main()
