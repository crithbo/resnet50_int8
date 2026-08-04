from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_senior_conv_operator import (
    MODEL_GRAPH,
    ORIGINAL_JSON,
    REPAIRED_JSON,
    current_contract_audit,
    known_issues,
    matching_resnet_nodes,
    semantic_leaf_differences,
    summarize_bitstream,
)


class SeniorConvOperatorAuditTests(unittest.TestCase):
    def test_structural_repair_is_an_exact_reviewed_delta(self) -> None:
        original = json.loads(ORIGINAL_JSON.read_text(encoding="utf-8"))
        repaired = json.loads(REPAIRED_JSON.read_text(encoding="utf-8"))
        differences = semantic_leaf_differences(original, repaired)
        self.assertEqual(len(differences), 13)
        self.assertEqual(
            {item["path"] for item in differences},
            {
                "$.buffer_config.buffer5.dst_port",
                "$.buffer_loop_configs.GROUP2.COL_LC.src_id",
                "$.buffer_loop_configs.GROUP3.COL_LC.src_id",
                "$.dram_loop_configs.LC13",
                "$.dram_loop_configs.LC14",
                "$.dram_loop_configs.LC15",
                "$.dram_loop_configs.LC9.src_id",
                "$.lc_pe_configs.PE1.inport2.src_id",
                "$.lc_pe_configs.PE4.inport0.src_id",
                "$.lc_pe_configs.PE6.inport0.src_id",
                "$.special_array.outport.mode",
                "$.stream_engine.stream2.idx[2]",
                "$.stream_engine.stream3.idx[0]",
            },
        )

    def test_geometry_matches_three_formal_resnet_nodes(self) -> None:
        graph = json.loads(MODEL_GRAPH.read_text(encoding="utf-8"))
        matches = matching_resnet_nodes(graph)
        self.assertEqual(
            [item["node_id"] for item in matches],
            ["node-0005", "node-0009", "node-0013"],
        )
        self.assertTrue(all(item["weight_shape"] == [64, 64, 3, 3] for item in matches))
        self.assertTrue(all(item["attributes"]["pads"] == [1, 1, 1, 1] for item in matches))

    def test_current_hardware_contract_rejects_original_and_structural_repair(self) -> None:
        original = json.loads(ORIGINAL_JSON.read_text(encoding="utf-8"))
        repaired = json.loads(REPAIRED_JSON.read_text(encoding="utf-8"))
        original_results = current_contract_audit(original)
        repaired_results = current_contract_audit(repaired)
        self.assertEqual([item["status"] for item in original_results], ["failed"] * 4)
        self.assertEqual(repaired_results[0]["status"], "passed")
        self.assertEqual([item["status"] for item in repaired_results[1:]], ["failed"] * 3)

    def test_issue_inventory_keeps_server_package_fail_closed(self) -> None:
        issues = known_issues()
        self.assertGreaterEqual(len(issues), 10)
        self.assertTrue(all(item["severity"] == "blocking" for item in issues))
        self.assertIn("E_INCOMPLETE_QLINEARCONV", {item["code"] for item in issues})
        self.assertIn("E_BIAS_TILE_HANDSHAKE", {item["code"] for item in issues})

    def test_bitstream_summary_normalizes_line_endings(self) -> None:
        line_a = "0" * 128
        line_b = "1" * 128
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bits.bin"
            path.write_bytes(f"{line_a}\r\n{line_b}\r\n".encode("ascii"))
            report = summarize_bitstream(path, 128)
        self.assertEqual(report["line_count"], 2)
        self.assertEqual(report["line_width_bits"], 128)
        self.assertEqual(report["normalized_lf_size_bytes"], 258)


if __name__ == "__main__":
    unittest.main()
