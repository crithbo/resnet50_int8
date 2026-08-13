from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.materialize_qlinearadd_slow_composite_strict_json_v1 import (
    DEFAULT_OUTPUT,
    materialize,
)
from tools.validate_qlinearadd_slow_composite_strict_json_v1 import (
    INVENTORY,
    ROOT,
    validate,
    validate_candidate,
)


class QLinearAddSlowCompositeStrictJsonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        parent = ROOT / "artifacts/operator_config_validation"
        cls._temp = tempfile.TemporaryDirectory(
            prefix="qadd_strict_test_", dir=parent
        )
        cls.artifact_root = Path(cls._temp.name) / "out"
        proof_root = DEFAULT_OUTPUT / "inputs/qadd_slow_composite_proof"
        materialize(cls.artifact_root, proof_root)
        cls.inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        cls.dp = json.loads(
            (
                cls.artifact_root
                / "inputs/qadd_slow_composite_proof/"
                "reachable_domain_sfu_segment_dp.json"
            ).read_text(encoding="utf-8")
        )
        cls.dp_by_id = {row["stage_id"]: row for row in cls.dp["rows"]}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp.cleanup()

    def candidate_and_stage(self, stage_index: int = 0):
        stage = self.inventory["targets"][stage_index]
        stage_id = stage["identity"]["hw_op_id"]
        candidate = json.loads(
            (
                self.artifact_root
                / "candidates"
                / stage_id
                / "complete_json.json"
            ).read_text(encoding="utf-8")
        )
        return candidate, stage, self.dp_by_id[stage_id]

    def test_full_family_local_strict_validation_passes(self) -> None:
        report = validate(self.artifact_root)
        self.assertTrue(report["pass"], report["errors"])
        self.assertEqual(report["stage_count"], 17)
        self.assertEqual(report["strict_json_count"], 17)
        self.assertEqual(report["same_shape_stage_count"], 16)
        self.assertEqual(report["broadcast_stage_count"], 1)
        self.assertEqual(report["forbidden_output_count"], 0)

    def test_qparam_bit_tamper_fails_closed(self) -> None:
        candidate, stage, dp = self.candidate_and_stage()
        bad = copy.deepcopy(candidate)
        bad["qparams"]["a_scale"]["float32_bits"] = "0x00000000"
        self.assertTrue(
            any("qparam a_scale" in item for item in validate_candidate(bad, stage, dp))
        )

    def test_sfu_table_tamper_fails_closed(self) -> None:
        candidate, stage, dp = self.candidate_and_stage()
        bad = copy.deepcopy(candidate)
        bad["numeric_graph"]["reachable_domain_sfu"]["breakpoint_bits"][0] = "0x00000000"
        self.assertTrue(
            any("SFU breakpoint table" in item for item in validate_candidate(bad, stage, dp))
        )

    def test_selector_tamper_fails_closed(self) -> None:
        candidate, stage, dp = self.candidate_and_stage()
        bad = copy.deepcopy(candidate)
        bad["numeric_graph"]["selector_edges"][4]["consumer_src_id"] = 0
        self.assertTrue(
            any("selector chain" in item for item in validate_candidate(bad, stage, dp))
        )

    def test_node0076_host_replay_fails_closed(self) -> None:
        candidate, stage, dp = self.candidate_and_stage(16)
        self.assertEqual(stage["identity"]["hw_op_id"], "hwop-0076-00")
        bad = copy.deepcopy(candidate)
        bad["physical_schedule"]["broadcast_replay"]["materialized_by_host"] = True
        self.assertTrue(
            any("host replay forbidden" in item for item in validate_candidate(bad, stage, dp))
        )

    def test_node0076_address_or_lifetime_tamper_fails_closed(self) -> None:
        candidate, stage, dp = self.candidate_and_stage(16)
        bad = copy.deepcopy(candidate)
        bad["physical_schedule"]["broadcast_replay"]["B_address_equation"] = (
            "B_base + 4*group_index"
        )
        self.assertTrue(
            any("broadcast B address" in item for item in validate_candidate(bad, stage, dp))
        )
        bad = copy.deepcopy(candidate)
        bad["physical_schedule"]["lifetime"]["B"] = "release after invocation 0"
        self.assertTrue(
            any("broadcast B lifetime" in item for item in validate_candidate(bad, stage, dp))
        )

    def test_terminal_and_active_window_tamper_fail_closed(self) -> None:
        candidate, stage, dp = self.candidate_and_stage()
        bad = copy.deepcopy(candidate)
        bad["physical_schedule"]["loops"]["terminal_equation"] = "final tile only"
        self.assertTrue(
            any("accepted terminal" in item for item in validate_candidate(bad, stage, dp))
        )
        bad = copy.deepcopy(candidate)
        bad["physical_schedule"]["coverage"]["producer_windows"] = ["[0,2)"]
        self.assertTrue(
            any("active bank window conservation" in item for item in validate_candidate(bad, stage, dp))
        )


if __name__ == "__main__":
    unittest.main()
