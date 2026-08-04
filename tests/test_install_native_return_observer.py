from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.install_native_return_observer import (
    INCLUDE_LINE,
    RUN_TIME_SIZED,
    install_observer,
)


ROOT = Path(__file__).resolve().parents[1]


class InstallNativeReturnObserverTests(unittest.TestCase):
    def test_installs_only_before_tb_endmodule_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tb = root / "tb_NDP_Top_new_phy.sv"
            tb.write_text(
                "module tb_NDP_Top_new_phy;\n  initial $display(\"tb\");\nendmodule\n",
                encoding="utf-8",
                newline="\n",
            )
            observer = root / "native_return_observer.svh"
            observer.write_text("// observer\n", encoding="utf-8", newline="\n")

            first = install_observer(tb, observer)
            second = install_observer(tb, observer)

            self.assertEqual(first["status"], "installed")
            self.assertEqual(second["status"], "already_installed")
            self.assertFalse(first["functional_rtl_modified"])
            self.assertEqual(tb.read_text(encoding="utf-8").count(INCLUDE_LINE), 1)
            self.assertIn(f"{INCLUDE_LINE}\n\nendmodule", tb.read_text())
            self.assertEqual(
                (root / "native_return_observer.svh").read_text(encoding="utf-8"),
                "// observer\n",
            )

    def test_copies_packaged_observer_next_to_tb(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package.mkdir()
            tb_root = root / "NDP_copy01"
            tb_root.mkdir()
            tb = tb_root / "tb_NDP_Top_new_phy.sv"
            tb.write_text("module tb_NDP_Top_new_phy;\nendmodule\n", encoding="utf-8")
            observer = package / "native_return_observer.svh"
            observer.write_text("// packaged observer\n", encoding="utf-8")

            report = install_observer(tb, observer)

            installed = tb_root / "native_return_observer.svh"
            self.assertEqual(installed.read_bytes(), observer.read_bytes())
            self.assertEqual(
                report["observer_installed"], installed.resolve().as_posix()
            )

    def test_rejects_functional_rtl_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rtl = root / "rtl"
            rtl.mkdir()
            tb = rtl / "tb_NDP_Top_new_phy.sv"
            tb.write_text("module tb; endmodule\n", encoding="utf-8")
            observer = root / "native_return_observer.svh"
            observer.write_text("// observer\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "rtl"):
                install_observer(tb, observer)

    def test_sizes_known_run_time_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tb = root / "tb_NDP_Top_new_phy.sv"
            tb.write_text(
                "module tb_NDP_Top_new_phy;\n"
                "  longint RUN_TIME = 100000000000000;\n"
                "endmodule\n",
                encoding="utf-8",
            )
            observer = root / "native_return_observer.svh"
            observer.write_text("// observer\n", encoding="utf-8")

            first = install_observer(tb, observer, fix_run_time=True)
            second = install_observer(tb, observer, fix_run_time=True)

            self.assertEqual(first["run_time_status"], "sized")
            self.assertEqual(second["run_time_status"], "already_sized")
            self.assertIn(RUN_TIME_SIZED, tb.read_text(encoding="utf-8"))
            self.assertNotIn(
                "longint RUN_TIME = 100000000000000;",
                tb.read_text(encoding="utf-8"),
            )

    def test_rejects_unknown_run_time_when_fix_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tb = root / "tb_NDP_Top_new_phy.sv"
            tb.write_text(
                "module tb_NDP_Top_new_phy;\nendmodule\n",
                encoding="utf-8",
            )
            observer = root / "native_return_observer.svh"
            observer.write_text("// observer\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "RUN_TIME"):
                install_observer(tb, observer, fix_run_time=True)

    def test_repository_observer_is_available_for_fresh_clone(self) -> None:
        observer = ROOT / "NDP_copy01" / "native_return_observer.svh"
        self.assertTrue(observer.is_file())
        self.assertIn(
            '$test$plusargs("RETURN_OBS_DEEP")',
            observer.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
