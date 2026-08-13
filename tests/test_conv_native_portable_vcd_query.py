from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.conv_native_portable_vcd_query import argv_json, canonical, parse_vcd


def profile() -> dict:
    catalog = [
        {
            "candidate_id": "valid",
            "hierarchical_path": "tb_NDP_Top_new_phy.dut.mse2mem_wdata_valid [1:0]",
            "width": 2,
        },
        {
            "candidate_id": "finish",
            "hierarchical_path": "tb_NDP_Top_new_phy.dut.slice_cmpt_finish",
            "width": 1,
        },
    ]
    return {
        "probe_catalog": catalog,
        "probe_catalog_sha256": hashlib.sha256(canonical(catalog)).hexdigest(),
    }


class NativePortableQueryTests(unittest.TestCase):
    def test_streams_ordered_vector_and_xz_rows(self) -> None:
        data = """$timescale 1 ns $end
$scope module tb_NDP_Top_new_phy $end
$scope module dut $end
$var wire 2 ! mse2mem_wdata_valid [1:0] $end
$var wire 1 \" slice_cmpt_finish $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b0 !
x\"
#5
b1z !
1\"
#10
bxx !
z\"
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wave.vcd"
            path.write_text(data, encoding="utf-8")
            result = parse_vcd(path, profile())
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["covered"], ["valid", "finish"])
        self.assertEqual([row["sequence"] for row in result["events"]], list(range(6)))
        self.assertEqual(
            [row["value"] for row in result["events"]],
            ["b00", "x", "b1z", "1", "bxx", "z"],
        )

    def test_missing_candidate_fails_closed(self) -> None:
        data = """$timescale 1 ns $end
$scope module tb_NDP_Top_new_phy $end
$scope module dut $end
$var wire 1 ! slice_cmpt_finish $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
0!
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wave.vcd"
            path.write_text(data, encoding="utf-8")
            result = parse_vcd(path, profile())
        self.assertIn("valid", result["missing"])
        self.assertTrue(any("exact-set" in item for item in result["errors"]))

    def test_actual_argv_json_is_tokenized_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "simulator_argv.txt"
            output = root / "actual_sim_argv.json"
            text.write_text(
                "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 "
                "DUMP_PORTABLE_VCD=1 timeout 12h /tmp/simv +ARG=x\n",
                encoding="utf-8",
            )
            self.assertEqual(argv_json(text, output), 0)
            value = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(value.count("DUMP_VCD=1"), 1)
        self.assertEqual(value.count("DUMP_PORTABLE_VCD=1"), 1)
        self.assertEqual(value[-1], "+ARG=x")


if __name__ == "__main__":
    unittest.main()
