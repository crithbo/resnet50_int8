from __future__ import annotations

import copy
import unittest

from tools.analyze_node0004_lc_branch_duplication_ab import (
    make_candidate,
    math_rows,
    microtrace,
)


class Node0004LcBranchDuplicationAbTest(unittest.TestCase):
    def baseline(self):
        return {
            "dram_loop_configs": {
                "LC3": {
                    "src_id": None,
                    "outmost_loop": 0,
                    "start": 0,
                    "end": 0,
                    "stride": 0,
                    "last_index": 0,
                },
                "LC9": {
                    "src_id": "DRAM_LC.LC15",
                    "outmost_loop": 0,
                    "start": 0,
                    "end": 8,
                    "stride": 1,
                    "last_index": 3,
                },
                "LC13": {"start": 0, "end": 2, "stride": 1},
                "LC14": {"start": 0, "end": 56, "stride": 1},
                "LC15": {"start": 0, "end": 7, "stride": 1},
            },
            "lc_pe_configs": {
                "PE1": {
                    "inport2": {
                        "src_id": "DRAM_LC.LC9",
                        "mode": "buffer",
                        "keep_last_index": None,
                        "constant": 0,
                    }
                }
            },
        }

    def test_candidate_copies_lc_and_changes_only_pe_source(self):
        baseline = self.baseline()
        candidate = make_candidate(copy.deepcopy(baseline))
        self.assertEqual(candidate["dram_loop_configs"]["LC3"], baseline["dram_loop_configs"]["LC9"])
        self.assertEqual(candidate["lc_pe_configs"]["PE1"]["inport2"]["src_id"], "DRAM_LC.LC3")
        self.assertEqual(baseline["lc_pe_configs"]["PE1"]["inport2"]["src_id"], "DRAM_LC.LC9")

    def test_math_sequence_is_equal(self):
        baseline = self.baseline()
        candidate = make_candidate(copy.deepcopy(baseline))
        self.assertEqual(math_rows(baseline), math_rows(candidate))
        self.assertEqual(len(math_rows(candidate)), 6272)

    def test_boundary_negative_and_positive_controls(self):
        v68 = {
            "physical_pe7_tenth_pair_adjudication": {"input0_accept": 2, "input2_accept": 9},
            "lc18_fanout_backpressure_adjudication": {
                "only_low_destination_bit": [10],
                "PE7_input2_is_ready": True,
            },
        }
        v97 = {
            "dynamic_execution_evidence": {
                "input1_last_marked_tuple_ps": 10,
                "input1_post_last_nonlast_tuple_ps": 20,
            }
        }
        result = microtrace(v68, v97)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["negative_control_shared_lc"]["tuple10_possible"])
        self.assertTrue(result["duplicated_branch_candidate"]["tuple10_possible"])
        self.assertFalse(result["duplicated_branch_candidate"]["parent_advance_required_for_tuple10"])


if __name__ == "__main__":
    unittest.main()
