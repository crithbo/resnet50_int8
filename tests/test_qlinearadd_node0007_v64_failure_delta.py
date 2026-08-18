from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.qlinearadd_node0007_tb_vcd_guarded_supervisor_v63 import scan_vcd_time
from tools.validate_qlinearadd_node0007_v64_tbvcd_failure_delta import exact_dump_check


class QAddV64FailureDeltaTests(unittest.TestCase):
    def test_appended_vcd_timestamp_is_the_freeze_clock(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "wave.vcd"
            path.write_bytes(b"$timescale\n1ps\n$end\n#0\n0!\n")
            offset, carry, first, rotated = scan_vcd_time(path, 0, b"")
            self.assertEqual(first, 0)
            self.assertFalse(rotated)
            with path.open("ab") as stream:
                stream.write(b"#125\n1!\n")
            offset, carry, second, rotated = scan_vcd_time(path, offset, carry)
            self.assertEqual(second, 125)
            self.assertFalse(rotated)
            self.assertGreater(offset, 0)

    def test_whole_module_dump_cannot_satisfy_exact_signal_set(self) -> None:
        expected = {"top.u.req", "top.u.ready"}
        positive = "$dumpvars(0, top.u.req);\n$dumpvars(0, top.u.ready);\n"
        negative = "$dumpvars(0, top.u);\n"
        self.assertTrue(exact_dump_check(positive, expected)["pass"])
        self.assertFalse(exact_dump_check(negative, expected)["pass"])

    def test_duplicate_signal_dump_is_rejected(self) -> None:
        expected = {"top.u.req"}
        duplicate = "$dumpvars(0, top.u.req);\n$dumpvars(0, top.u.req);\n"
        result = exact_dump_check(duplicate, expected)
        self.assertFalse(result["pass"])
        self.assertTrue(result["duplicates"])


if __name__ == "__main__":
    unittest.main()
