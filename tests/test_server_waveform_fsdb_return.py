from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.server_waveform_mandatory_return import (
    PLAN_MEMBER,
    collect_runtime,
    inspect_fsdb,
    inspect_return_zip,
    render_dump_control,
    validate_final_zip,
    validate_plan,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/server_waveform_mandatory_return_v3"
PLAN = FIXTURE / "positive_plan.json"
PLAN_SCHEMA = ROOT / "schemas/server_waveform_mandatory_plan_v3.schema.json"
RECEIPT_SCHEMA = ROOT / "schemas/server_waveform_runtime_receipt_v3.schema.json"
TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
DISPATCH = ROOT / "contracts/server_waveform_mandatory_return_dispatch_v3.json"


class FsdbWaveformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_current_plan_schema_and_dispatch(self) -> None:
        self.assertEqual(validate_plan(self.plan), [])
        if jsonschema is not None:
            jsonschema.validate(self.plan, json.loads(PLAN_SCHEMA.read_text(encoding="utf-8")))
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(dispatch["default_capture"]["make_arguments"], {
            "DUMP_VCD": "0", "DUMP_FSDB": "1", "TB_DUMP_FSDB": "0"
        })
        self.assertTrue(dispatch["return_contract"]["same_zip_as_formal_return"])
        self.assertEqual(dispatch["repeat_execution"]["foreign_siblings"], "PRESERVE")

    def test_vpd_or_second_writer_arguments_fail_closed(self) -> None:
        for args in (
            {"DUMP_VCD": "1", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            {"DUMP_VCD": "0", "DUMP_FSDB": "1", "TB_DUMP_FSDB": "1"},
        ):
            bad = copy.deepcopy(self.plan)
            bad["dump"]["make_arguments"] = args
            self.assertTrue(any("make arguments" in item for item in validate_plan(bad)))

    def _make_package(self, directory: Path, *, wrong_args: bool = False) -> Path:
        plan = copy.deepcopy(self.plan)
        top = plan["package_id"]
        tree = directory / top
        (tree / "contracts").mkdir(parents=True)
        (tree / "package_tools").mkdir()
        (tree / PLAN_MEMBER).write_text(json.dumps(plan), encoding="utf-8")
        (tree / plan["integration"]["tool_member"]).write_bytes(TOOL.read_bytes())
        (tree / plan["integration"]["dump_control_member"]).write_text(
            render_dump_control(plan), encoding="utf-8", newline="\n"
        )
        args = "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0" if wrong_args else "DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0"
        (tree / plan["integration"]["runner_member"]).write_text(
            f"make compile {args}\nmake sim {args}\n"
            "python3 package_tools/server_waveform_mandatory_return.py collect-runtime "
            "--plan contracts/server_waveform_mandatory_plan.json --attempt-root . "
            "--execution-id e --simulation-started true --exit-kind NATURAL "
            "--output evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json\n",
            encoding="utf-8",
        )
        request = {
            "waveform_discovery": {
                "plan_member": PLAN_MEMBER,
                "collector_member": plan["integration"]["tool_member"],
                "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
                "collect_all_matching": True,
                "required_when_simulation_started": True,
                "no_size_limit": True,
                "manifest_archive_path": plan["return_policy"]["manifest_archive_path"],
            }
        }
        (tree / plan["integration"]["return_request_member"]).write_text(json.dumps(request), encoding="utf-8")
        target = directory / "package.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(tree.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(directory).as_posix())
        return target

    def test_exact_final_zip_accepts_fsdb_and_rejects_vpd_runner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = validate_final_zip(self._make_package(Path(directory)))
            self.assertTrue(report["pass"], report["errors"])
        with tempfile.TemporaryDirectory() as directory:
            report = validate_final_zip(self._make_package(Path(directory), wrong_args=True))
            self.assertFalse(report["pass"])
            self.assertTrue(any("mandatory token" in item for item in report["errors"]))

    def _attempt(self, root: Path, *, with_fsdb: bool) -> Path:
        attempt = root / "install/codex_runs/pkg/attempt"
        wave_root = attempt / "run/sim_results"
        wave_root.mkdir(parents=True)
        if with_fsdb:
            (wave_root / "wave.fsdb").write_bytes(b"fsdb-primary")
            (wave_root / "wave.fsdb.001").write_bytes(b"fsdb-shard")
        return attempt

    def test_started_requires_attempt_local_fsdb_and_collects_every_shard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_fsdb=False)
            missing = collect_runtime(PLAN, attempt, "first", True, "TIMEOUT")
            self.assertFalse(missing["pass"])
            self.assertTrue(any("wave.fsdb" in item for item in missing["errors"]))
            (attempt.parent.parent.parent / "inter.fsdb").write_bytes(b"stale-root")
            still_missing = collect_runtime(PLAN, attempt, "second", True, "TIMEOUT")
            self.assertFalse(still_missing["pass"])
            (attempt / "run/sim_results/wave.fsdb").write_bytes(b"current")
            receipt = collect_runtime(PLAN, attempt, "third", True, "NATURAL")
            self.assertTrue(receipt["pass"], receipt["errors"])
            self.assertEqual(receipt["schema"], "server-waveform-runtime-receipt-v3")
            self.assertEqual({item["format"] for item in receipt["waveforms"]}, {"FSDB"})

    def test_compile_failure_may_omit_fsdb_but_stale_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_fsdb=False)
            self.assertTrue(collect_runtime(PLAN, attempt, "compile", False, "COMPILE_FAILURE")["pass"])
            (attempt / "run/sim_results/wave.fsdb").write_bytes(b"stale")
            self.assertFalse(collect_runtime(PLAN, attempt, "compile2", False, "COMPILE_FAILURE")["pass"])

    def test_no_cap_sampling_or_deletion_and_identity_tool(self) -> None:
        for field, value in (
            ("hard_limit_bytes", 1), ("truncation_allowed", True),
            ("sampling_allowed", True), ("size_based_deletion_allowed", True),
        ):
            bad = copy.deepcopy(self.plan)
            bad["return_policy"][field] = value
            self.assertTrue(any(field in item for item in validate_plan(bad)))
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_fsdb=True)
            report = inspect_fsdb(attempt / "run/sim_results/wave.fsdb")
            self.assertTrue(report["pass"])
            self.assertEqual(report["identity"]["format"], "FSDB")
            self.assertIn("verdi -ssf", report["open_commands"]["verdi"])

    def test_return_zip_contains_exact_declared_fsdb_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attempt = self._attempt(root, with_fsdb=True)
            receipt = collect_runtime(PLAN, attempt, "return1", True, "TIMEOUT")
            if jsonschema is not None:
                jsonschema.validate(receipt, json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8")))
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            returned = root / "return-unique-1.zip"
            top = "synthetic_fsdb_v3_return"
            with zipfile.ZipFile(returned, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.write(receipt_path, f"{top}/{self.plan['return_policy']['manifest_archive_path']}")
                for item in receipt["waveforms"]:
                    archive.write(attempt / item["source_path"], f"{top}/{item['archive_path']}")
            report = inspect_return_zip(returned, PLAN)
            self.assertTrue(report["pass"], report["errors"])
            self.assertEqual(report["details"]["waveform_count"], 2)

    def test_large_fsdb_is_hashed_without_hidden_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_fsdb=False)
            payload = bytes(range(256)) * 32768
            wave = attempt / "run/sim_results/wave.fsdb"
            wave.write_bytes(payload)
            receipt = collect_runtime(PLAN, attempt, "large", True, "NATURAL")
            self.assertTrue(receipt["pass"], receipt["errors"])
            self.assertEqual(receipt["waveforms"][0]["bytes"], len(payload))
            self.assertEqual(receipt["waveforms"][0]["sha256"], hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
