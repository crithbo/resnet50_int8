from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from resnet50_pipeline.artifacts import ArtifactManager
from resnet50_pipeline.backends import MockBackend
from resnet50_pipeline.errors import ManifestVersionError
from resnet50_pipeline.manifest import RunManifest
from resnet50_pipeline.layout import IdentityLayout
from resnet50_pipeline.records import ObjectManifest, TensorRecord
from resnet50_pipeline.pipeline import STAGES, execute_mock_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class W0PipelineTests(unittest.TestCase):
    def test_successful_mock_run_has_all_stages_and_valid_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            manifest = execute_mock_run(PROJECT_ROOT, output, MockBackend())
            self.assertEqual(manifest.status, "succeeded")
            self.assertEqual([stage.name for stage in manifest.stages], list(STAGES))
            self.assertTrue(all(stage.status == "succeeded" for stage in manifest.stages))
            manager = ArtifactManager(output / manifest.run_id)
            self.assertTrue(all(manager.verify(item) for stage in manifest.stages for item in stage.artifacts))
            loaded = RunManifest.load(output / manifest.run_id / "manifest.json")
            self.assertEqual(loaded.cache_key, manifest.cache_key)
            self.assertEqual(len(loaded.environment["integration_code_sha256"]), 64)
            self.assertEqual(len(loaded.environment["digest"]), 64)
            self.assertEqual(loaded.objects.nodes[0].node_id, "node-0000")
            self.assertEqual(loaded.objects.hw_ops[0].node_id, "node-0000")

    def test_backend_failure_blocks_downstream_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = execute_mock_run(
                PROJECT_ROOT,
                Path(directory),
                MockBackend(fail_stage="simulate"),
            )
            statuses = {stage.name: stage.status for stage in manifest.stages}
            self.assertEqual(manifest.status, "failed")
            self.assertEqual(statuses["simulate"], "failed")
            self.assertEqual(statuses["execplan"], "blocked")
            self.assertEqual(statuses["hardware"], "blocked")
            self.assertEqual(statuses["compare"], "blocked")

    def test_unsupported_capability_fails_before_other_stages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = execute_mock_run(
                PROJECT_ROOT,
                Path(directory),
                MockBackend(),
                op="QLinearConv",
            )
            self.assertEqual(manifest.status, "failed")
            self.assertEqual(manifest.stages[0].status, "failed")
            self.assertIn("does not support", manifest.stages[0].error or "")
            self.assertTrue(all(stage.status == "blocked" for stage in manifest.stages[1:]))

    def test_missing_input_raises_before_creating_a_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(Exception, "input does not exist"):
                execute_mock_run(
                    PROJECT_ROOT,
                    Path(directory),
                    MockBackend(),
                    input_path=Path(directory) / "missing.bin",
                )

    def test_contract_change_changes_cache_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            for name in ("fixtures", "contracts"):
                (root / name).mkdir()
            (root / "fixtures" / "mock_graph.json").write_text(
                (PROJECT_ROOT / "fixtures" / "mock_graph.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (root / "repos.lock.json").write_text(
                (PROJECT_ROOT / "repos.lock.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            for name in ("architecture", "quantization", "backend"):
                (root / "contracts" / f"{name}.json").write_text(
                    (PROJECT_ROOT / "contracts" / f"{name}.json").read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            (root / "contracts" / "rtl28_candidate_audit.json").write_bytes(
                (PROJECT_ROOT / "contracts" / "rtl28_candidate_audit.json").read_bytes()
            )
            (root / "contracts" / "target_config_authority_audit.json").write_bytes(
                (PROJECT_ROOT / "contracts" / "target_config_authority_audit.json").read_bytes()
            )
            (root / "contracts" / "typed_config_parameter_contract.json").write_bytes(
                (PROJECT_ROOT / "contracts" / "typed_config_parameter_contract.json").read_bytes()
            )
            (root / "contracts" / "hardware_approval.json").write_bytes(
                (PROJECT_ROOT / "contracts" / "hardware_approval.json").read_bytes()
            )
            legacy_index = json.loads(
                (PROJECT_ROOT / "artifacts/w4/legacy16_index.json").read_text(
                    encoding="utf-8"
                )
            )
            for relative_path in (
                "artifacts/w4/legacy16_index.json",
                *(record["path"] for record in legacy_index["reports"].values()),
            ):
                source = PROJECT_ROOT / relative_path
                destination = root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            architecture = json.loads(
                (root / "contracts/architecture.json").read_text(encoding="utf-8")
            )
            for record in architecture["candidate_evidence"].values():
                if record.get("current_gate_eligible") is not True:
                    continue
                source = PROJECT_ROOT / record["path"]
                destination = root / record["path"]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(source.read_bytes())
            first = execute_mock_run(root, Path(directory) / "out", MockBackend())
            path = root / "contracts" / "quantization.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            value["hardware_unresolved"].append(
                "cache-key regression fixture revision"
            )
            path.write_text(json.dumps(value), encoding="utf-8")
            second = execute_mock_run(root, Path(directory) / "out", MockBackend())
            self.assertNotEqual(first.cache_key, second.cache_key)

    def test_unknown_manifest_version_is_rejected(self) -> None:
        with self.assertRaises(ManifestVersionError):
            RunManifest.from_dict({"schema_version": "9.9"})

    def test_resume_reuses_only_a_valid_matching_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            first = execute_mock_run(PROJECT_ROOT, output, MockBackend())
            resumed = execute_mock_run(PROJECT_ROOT, output, MockBackend(), resume=True)
            changed = execute_mock_run(
                PROJECT_ROOT,
                output,
                MockBackend(),
                resume=True,
                slice_count=4,
            )
            self.assertEqual(first.run_id, resumed.run_id)
            self.assertNotEqual(first.run_id, changed.run_id)
            artifact = output / first.run_id / first.stages[0].artifacts[0].path
            artifact.write_bytes(b"corrupted")
            rerun = execute_mock_run(PROJECT_ROOT, output, MockBackend(), resume=True)
            self.assertNotEqual(first.run_id, rerun.run_id)

    def test_object_manifest_rejects_broken_references(self) -> None:
        objects = ObjectManifest(tensors=[TensorRecord("tensor-a", "uint8", (1,))])
        objects.validate()
        with self.assertRaisesRegex(ValueError, "unknown tensor"):
            ObjectManifest.from_dict({
                "tensors": [{"tensor_id": "tensor-a", "dtype": "uint8", "shape": [1]}],
                "nodes": [],
                "hw_ops": [],
                "layouts": [{
                    "layout_id": "layout-bad",
                    "tensor_id": "missing",
                    "transform": "identity",
                    "contract_status": "candidate"
                }],
                "configs": [],
                "executions": [],
                "results": []
            })

    def test_identity_layout_round_trip_and_coordinate_explanation(self) -> None:
        layout = IdentityLayout()
        logical = bytes([0, 1, 127, 255])
        physical = layout.forward(logical, {"size_bytes": 4})
        self.assertEqual(layout.inverse(physical, {"size_bytes": 4}), logical)
        self.assertEqual(layout.explain_coordinate((0, 0))["mapping"], "identity")

    def test_resume_skips_an_unsupported_old_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            old = output / "w0-zzzz-old"
            old.mkdir(parents=True)
            (old / "manifest.json").write_text(
                json.dumps({"schema_version": "0.0"}), encoding="utf-8"
            )
            manifest = execute_mock_run(
                PROJECT_ROOT,
                output,
                MockBackend(),
                resume=True,
            )
            self.assertEqual(manifest.status, "succeeded")

    def test_artifact_path_cannot_escape_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = ArtifactManager(Path(directory))
            with self.assertRaises(ValueError):
                manager.write_bytes("../escape.bin", b"bad")


if __name__ == "__main__":
    unittest.main()
