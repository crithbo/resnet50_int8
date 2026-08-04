from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.gap_ga_rtl_repair import (
    FILE_RELS,
    build_gap_ga_rtl_repair,
    int32_feedback_allowed,
    repaired_outbuffer_count,
    validate_gap_ga_rtl_repair,
)
from tools.install_gap_ga_rtl_repair import install, restore


ROOT = Path(__file__).resolve().parents[1]


class GapGaRtlRepairTests(unittest.TestCase):
    def test_repair_is_exact_syntax_checked_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "repair"
            manifest = build_gap_ga_rtl_repair(ROOT, output)
            checked = validate_gap_ga_rtl_repair(ROOT, output)
            self.assertEqual(checked["repair_id"], manifest["repair_id"])
            self.assertTrue(manifest["local_syntax_check"]["passed"])
            self.assertEqual(set(manifest["files"]), {item.as_posix() for item in FILE_RELS})

    def test_compaction_and_result_last_never_underflow(self) -> None:
        for count in range(3):
            for write in (False, True):
                for read in (False, True):
                    self.assertEqual(
                        repaired_outbuffer_count(
                            count,
                            compaction=True,
                            result_last=False,
                            write=write,
                            read=read,
                        ),
                        0,
                    )
                    self.assertEqual(
                        repaired_outbuffer_count(
                            count,
                            compaction=False,
                            result_last=True,
                            write=write,
                            read=read,
                        ),
                        0,
                    )

    def test_int32_feedback_requires_a_valid_slot(self) -> None:
        self.assertFalse(
            int32_feedback_allowed(
                transout=True,
                int32_mode=True,
                calculating=False,
                initialization_done=True,
                outbuffer_valid=False,
            )
        )
        self.assertTrue(
            int32_feedback_allowed(
                transout=True,
                int32_mode=True,
                calculating=False,
                initialization_done=True,
                outbuffer_valid=True,
            )
        )
        self.assertTrue(
            int32_feedback_allowed(
                transout=True,
                int32_mode=True,
                calculating=True,
                initialization_done=True,
                outbuffer_valid=False,
            )
        )

    def test_installer_is_hash_gated_and_restores_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            patch = temp / "patch"
            build_gap_ga_rtl_repair(ROOT, patch)
            ndp = temp / "NDP"
            originals: dict[Path, bytes] = {}
            for relative in FILE_RELS:
                source = ROOT / "NDP_copy01" / relative
                target = ndp / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                originals[relative] = target.read_bytes()
            backup = temp / "backup"
            install(
                ndp_root=ndp,
                patch_root=patch,
                backup_root=backup,
                report_path=temp / "install.json",
            )
            for relative in FILE_RELS:
                self.assertEqual(
                    (ndp / relative).read_bytes(),
                    (patch / relative).read_bytes(),
                )
            restore(
                ndp_root=ndp,
                patch_root=patch,
                backup_root=backup,
                report_path=temp / "restore.json",
            )
            for relative, payload in originals.items():
                self.assertEqual((ndp / relative).read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
