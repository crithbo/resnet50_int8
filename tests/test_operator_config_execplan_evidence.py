from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.operator_config_execplan_evidence import (
    create_execplan_evidence_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
NDP_SIM = ROOT / "ndp-sim"
GRAPH = (
    NDP_SIM
    / "generate_python_golden/model_execplan/op_json_hwverified"
    / "decode_summac_fp32N_fp32N_graph.json"
)
MAPPING = (
    ROOT
    / "artifacts/operator_config_validation/r3-mapping-evidence"
    / "decode_summac-seed42-v1"
)
PYTHON = ROOT / ".venv/Scripts/python.exe"
CONTRACT = ROOT / "contracts/operator_config/decode_summac_r3_semantic_contract.json"


class OperatorConfigExecPlanEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="execplan-evidence-tests-")
        cls.output = Path(cls.temp.name) / "bundle"
        active_cache = NDP_SIM / "bitstream/config/mapping_cache"
        cls.cache_before = {
            path.relative_to(active_cache).as_posix(): path.read_bytes()
            for path in active_cache.glob("*.json")
        }
        cls.result = create_execplan_evidence_bundle(
            ndp_sim_root=NDP_SIM,
            graph_path=GRAPH,
            mapping_bundles={"op0": MAPPING},
            output_dir=cls.output,
            python_executable=PYTHON,
            semantic_contract_path=CONTRACT,
        )
        cls.cache_after = {
            path.relative_to(active_cache).as_posix(): path.read_bytes()
            for path in active_cache.glob("*.json")
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_native_double_run_is_bound_and_deterministic(self) -> None:
        self.assertTrue(self.result.valid)
        self.assertEqual(self.result.deterministic_file_count, 15)
        self.assertEqual(self.cache_before, self.cache_after)
        comparison = json.loads(
            (self.output / "double_run_comparison.json").read_text(encoding="utf-8")
        )
        self.assertTrue(comparison["equal"])
        self.assertEqual(len(comparison["files"]), 15)
        report = json.loads(
            (self.output / "execplan_validation_report.json").read_text(encoding="utf-8")
        )
        self.assertTrue(report["valid"])
        stage = report["facts"]["stages"][0]
        self.assertEqual(stage["pipeline_json_sha256"], stage["source_config_sha256"])
        self.assertEqual(
            stage["pipeline_artifact_sha256"]["modules_dump_128b.bin"],
            stage["config_sha256"],
        )
        package = json.loads(
            (self.output / "package_validation_report.json").read_text(encoding="utf-8")
        )
        self.assertTrue(package["valid"])
        self.assertFalse(package["facts"]["matrix_files_required"])
        requests = json.loads(
            (self.output / "request_address_validation_report.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(requests["valid"])
        self.assertEqual(requests["facts"]["request_count_with_multiplicity"], 924)
        self.assertEqual(requests["facts"]["unique_request_address_count"], 252)
        self.assertTrue(
            all(
                stream["request_rows_included"] is False and "requests" not in stream
                for stage in requests["facts"]["stages"]
                for stream in stage["streams"]
            )
        )

    def test_refuses_overwrite_or_missing_operator_binding(self) -> None:
        with self.assertRaises(FileExistsError):
            create_execplan_evidence_bundle(
                ndp_sim_root=NDP_SIM,
                graph_path=GRAPH,
                mapping_bundles={"op0": MAPPING},
                output_dir=self.output,
                python_executable=PYTHON,
            )
        with self.assertRaises(ValueError):
            create_execplan_evidence_bundle(
                ndp_sim_root=NDP_SIM,
                graph_path=GRAPH,
                mapping_bundles={},
                output_dir=Path(self.temp.name) / "missing",
                python_executable=PYTHON,
            )


class PatchedExecPlanEvidenceTests(unittest.TestCase):
    def test_checked_in_patched_double_run_binds_6144_toolchain(self) -> None:
        bundle = (
            ROOT
            / "artifacts/operator_config_validation/r5-patched-execplan-evidence"
            / "decode_summac-double-run-v1"
        )
        manifest = json.loads(
            (bundle / "bundle_manifest.json").read_text(encoding="utf-8")
        )
        comparison = json.loads(
            (bundle / "double_run_comparison.json").read_text(encoding="utf-8")
        )
        requests = json.loads(
            (bundle / "request_address_validation_report.json").read_text(
                encoding="utf-8"
            )
        )
        patchset = manifest["native_repository"]["patchset"]
        self.assertEqual(patchset["patchset_id"], "resnet50-ndp-toolchain-6144-v1")
        self.assertTrue(comparison["equal"])
        self.assertEqual(len(comparison["files"]), 15)
        self.assertTrue(requests["valid"])
        self.assertEqual(requests["facts"]["target_profile"]["ddr_rows"], 6144)

    def test_checked_node0004_candidate_is_address_bound_and_compact(self) -> None:
        bundle = (
            ROOT
            / "artifacts/operator_config_validation/r5-patched-execplan-evidence"
            / "node0004-nopp-r1-v1"
        )
        manifest = json.loads(
            (bundle / "bundle_manifest.json").read_text(encoding="utf-8")
        )
        comparison = json.loads(
            (bundle / "double_run_comparison.json").read_text(encoding="utf-8")
        )
        package = json.loads(
            (bundle / "package_validation_report.json").read_text(encoding="utf-8")
        )
        requests = json.loads(
            (bundle / "request_address_validation_report.json").read_text(
                encoding="utf-8"
            )
        )
        stage = json.loads(
            (bundle / "execplan_validation_report.json").read_text(encoding="utf-8")
        )["facts"]["stages"][0]
        self.assertEqual(
            manifest["execplan"]["sha256"],
            "a5d9edf2fbd51f2107b9fe7845f4716786a61797be7c9e38aca3ede9009a0711",
        )
        self.assertTrue(comparison["equal"])
        self.assertEqual(len(comparison["files"]), 15)
        self.assertTrue(package["valid"])
        self.assertTrue(requests["valid"])
        self.assertEqual(requests["facts"]["request_count_with_multiplicity"], 748160)
        self.assertEqual(requests["facts"]["unique_request_address_count"], 704368)
        self.assertTrue(
            all(
                stream["request_rows_included"] is False and "requests" not in stream
                for item in requests["facts"]["stages"]
                for stream in item["streams"]
            )
        )
        self.assertEqual(stage["pipeline_json_sha256"], stage["source_config_sha256"])
        self.assertEqual(
            package["facts"]["semantic_contract"]["graph_sha256"],
            requests["facts"]["graph_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
