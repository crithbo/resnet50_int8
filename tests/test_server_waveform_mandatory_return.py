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
    extract_return,
    inspect_return_zip,
    inspect_vpd,
    render_dump_control,
    validate_final_zip,
    validate_plan,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/server_waveform_mandatory_return_v2"
PLAN = FIXTURE / "positive_plan.json"
CASES = FIXTURE / "cases.json"
PLAN_SCHEMA = ROOT / "schemas/server_waveform_mandatory_plan_v2.schema.json"
RECEIPT_SCHEMA = ROOT / "schemas/server_waveform_runtime_receipt_v2.schema.json"
TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
DISPATCH = ROOT / "contracts/server_waveform_mandatory_return_dispatch_v2.json"
REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"


class MandatoryWaveformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_plan_schema_dispatch_and_registry(self) -> None:
        self.assertEqual(validate_plan(self.plan), [])
        if jsonschema is not None:
            jsonschema.validate(
                self.plan, json.loads(PLAN_SCHEMA.read_text(encoding="utf-8"))
            )
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(
            dispatch["rule_id"],
            "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
        )
        self.assertIsNone(dispatch["return_contract"]["hard_size_limit"])
        self.assertEqual(
            dispatch["shared_assets"]["post_sim_helper"],
            "tools/server_post_sim_return.py",
        )
        self.assertEqual(len(dispatch["runtime_sequence"]), 2)
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(len(cases["positive"]), 6)
        self.assertEqual(len(cases["negative"]), 7)
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        gate = next(
            item
            for item in registry["gates"]
            if item["gate_id"] == "observer_only_wide_causal_final_zip"
        )
        self.assertEqual(gate["activation"], "always")
        # This suite remains a frozen compatibility control for historical
        # waveform returns. Current next-fresh packages use observer-only v1.
        self.assertEqual(gate["semantic_version"], "2")
        retired = {
            "waveform_observation_final_zip",
            "waveform_portable_local_decodability",
            "fsdb_process_tree_writer_quiescence",
        }
        self.assertTrue(retired.isdisjoint(item["gate_id"] for item in registry["gates"]))

    def test_full_hierarchy_and_unproven_exclusion_fail_closed(self) -> None:
        bad = copy.deepcopy(self.plan)
        bad["dump"]["included_scopes"] = ["tb_NDP_Top_new_phy.u_NDP_Top_new"]
        self.assertTrue(any("FULL_HIERARCHY" in item for item in validate_plan(bad)))
        bad = copy.deepcopy(self.plan)
        bad["dump"]["scope_mode"] = "PROVEN_IRRELEVANT_PRUNED"
        bad["dump"]["excluded_scopes"] = [
            {
                "hierarchical_path": "tb_NDP_Top_new_phy.host",
                "reason": "guess",
                "evidence": {"path": "evidence/guess.json", "sha256": None},
            }
        ]
        self.assertTrue(any("sha256" in item for item in validate_plan(bad)))

    def test_no_hard_cap_or_size_deletion_can_be_declared(self) -> None:
        for field, value in (
            ("hard_limit_bytes", 1024),
            ("truncation_allowed", True),
            ("sampling_allowed", True),
            ("size_based_deletion_allowed", True),
        ):
            bad = copy.deepcopy(self.plan)
            bad["return_policy"][field] = value
            self.assertTrue(
                any(field in item for item in validate_plan(bad)), (field, validate_plan(bad))
            )

    def _make_package(
        self,
        directory: Path,
        *,
        plan: dict | None = None,
        dump_zero: bool = False,
        missing_allowlist: bool = False,
    ) -> Path:
        plan = copy.deepcopy(plan or self.plan)
        top = plan["package_id"]
        tree = directory / top
        (tree / "contracts").mkdir(parents=True)
        (tree / "package_tools").mkdir()
        (tree / PLAN_MEMBER).write_text(json.dumps(plan), encoding="utf-8")
        (tree / plan["integration"]["tool_member"]).write_bytes(TOOL.read_bytes())
        (tree / plan["integration"]["dump_control_member"]).write_text(
            render_dump_control(plan), encoding="utf-8", newline="\n"
        )
        vcd = "0" if dump_zero else "1"
        (tree / plan["integration"]["runner_member"]).write_text(
            f"make compile DUMP_VCD={vcd} DUMP_FSDB=0 TB_DUMP_FSDB=0\n"
            f"make sim DUMP_VCD={vcd} DUMP_FSDB=0 TB_DUMP_FSDB=0\n"
            "python3 package_tools/server_waveform_mandatory_return.py collect-runtime "
            "--plan contracts/server_waveform_mandatory_plan.json --attempt-root . "
            "--execution-id e --simulation-started true --exit-kind NATURAL "
            "--output evidence/wave.json\n",
            encoding="utf-8",
        )
        discovery = {
            "plan_member": PLAN_MEMBER,
            "collector_member": plan["integration"]["tool_member"],
            "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
            "collect_all_matching": True,
            "required_when_simulation_started": True,
            "no_size_limit": True,
            "manifest_archive_path": plan["return_policy"]["manifest_archive_path"],
        }
        request = {"core_entries": []}
        if not missing_allowlist:
            request["waveform_discovery"] = discovery
        (tree / plan["integration"]["return_request_member"]).write_text(
            json.dumps(request), encoding="utf-8"
        )
        target = directory / "package.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(tree.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(directory).as_posix())
        return target

    def test_exact_final_zip_positive_and_dump_zero_negative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = validate_final_zip(self._make_package(Path(directory)))
            self.assertTrue(report["pass"], report["errors"])
        with tempfile.TemporaryDirectory() as directory:
            report = validate_final_zip(
                self._make_package(Path(directory), dump_zero=True)
            )
            self.assertFalse(report["pass"])
            self.assertTrue(any("DUMP_VCD" in item for item in report["errors"]))

    def test_missing_waveform_return_allowlist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = validate_final_zip(
                self._make_package(Path(directory), missing_allowlist=True)
            )
            self.assertFalse(report["pass"])
            self.assertTrue(any("discovery contract" in item for item in report["errors"]))

    def test_self_inclusion_and_path_escape_fail(self) -> None:
        bad = copy.deepcopy(self.plan)
        bad["return_policy"]["archive_prefix"] = "returns/return.zip"
        self.assertTrue(any("cannot name a ZIP" in item for item in validate_plan(bad)))
        bad = copy.deepcopy(self.plan)
        bad["dump"]["runtime_search_roots"] = ["../outside"]
        self.assertTrue(any("unsafe" in item for item in validate_plan(bad)))

    def _attempt(self, root: Path, *, with_wave: bool) -> Path:
        attempt = root / "attempt"
        (attempt / "run/sim_results").mkdir(parents=True)
        if with_wave:
            (attempt / "run/sim_results/wave.vpd").write_bytes(b"vpd-primary")
            (attempt / "run/sim_results/wave.vpd.001").write_bytes(b"vpd-shard")
        return attempt

    def test_compilefail_no_wave_and_started_missing_wave(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_wave=False)
            receipt = collect_runtime(
                PLAN, attempt, "compilefail", False, "COMPILE_FAILURE"
            )
            self.assertTrue(receipt["pass"], receipt["errors"])
            self.assertEqual(receipt["waveforms"], [])
            missing = collect_runtime(PLAN, attempt, "dynamic", True, "TIMEOUT")
            self.assertFalse(missing["pass"])
            self.assertTrue(any("no wave.vpd" in item for item in missing["errors"]))

    def test_natural_timeout_and_signals_collect_every_shard(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_wave=True)
            for exit_kind in ("NATURAL", "TIMEOUT", "HUP", "INT", "TERM"):
                receipt = collect_runtime(PLAN, attempt, exit_kind.lower(), True, exit_kind)
                self.assertTrue(receipt["pass"], (exit_kind, receipt["errors"]))
                self.assertEqual(len(receipt["waveforms"]), 2)
                expected = "COMPLETE" if exit_kind == "NATURAL" else "PARTIAL"
                self.assertEqual(
                    {item["completeness"] for item in receipt["waveforms"]},
                    {expected},
                )
                self.assertTrue(receipt["no_size_limit"])

    def test_multi_megabyte_wave_is_streamed_without_a_hidden_cap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_wave=False)
            wave = attempt / "run/sim_results/wave.vpd"
            payload = bytes(range(256)) * 32768
            wave.write_bytes(payload)
            receipt = collect_runtime(PLAN, attempt, "large", True, "NATURAL")
            self.assertTrue(receipt["pass"], receipt["errors"])
            self.assertTrue(receipt["no_size_limit"])
            self.assertEqual(len(receipt["waveforms"]), 1)
            self.assertEqual(receipt["waveforms"][0]["bytes"], len(payload))
            self.assertEqual(
                receipt["waveforms"][0]["sha256"], hashlib.sha256(payload).hexdigest()
            )

    def _return_zip(
        self, directory: Path, *, omit_wave: bool = False
    ) -> tuple[Path, Path]:
        attempt = self._attempt(directory, with_wave=True)
        receipt = collect_runtime(PLAN, attempt, "exec1", True, "TIMEOUT")
        self.assertTrue(receipt["pass"])
        receipt_path = directory / "receipt.json"
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        top = "synthetic_wave_v2_return"
        target = directory / "return.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.write(
                receipt_path,
                f"{top}/{self.plan['return_policy']['manifest_archive_path']}",
            )
            if not omit_wave:
                for item in receipt["waveforms"]:
                    archive.write(attempt / item["source_path"], f"{top}/{item['archive_path']}")
        return target, attempt

    def test_return_integrity_vpd_identity_and_safe_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            returned, attempt = self._return_zip(root)
            report = inspect_return_zip(returned, PLAN)
            self.assertTrue(report["pass"], report["errors"])
            self.assertEqual(report["details"]["waveform_count"], 2)
            identity = inspect_vpd(attempt / "run/sim_results/wave.vpd")
            self.assertTrue(identity["pass"])
            self.assertIn("verdi -vpd", identity["open_commands"]["verdi"])
            extracted = extract_return(returned, root / "extracted", PLAN)
            self.assertTrue(extracted["pass"], extracted["errors"])
            self.assertEqual(len(extracted["extracted"]), 2)

    def test_formal_return_missing_declared_wave_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            returned, _ = self._return_zip(Path(directory), omit_wave=True)
            report = inspect_return_zip(returned, PLAN)
            self.assertFalse(report["pass"])
            self.assertTrue(any("absent" in item for item in report["errors"]))

    def test_receipt_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            attempt = self._attempt(Path(directory), with_wave=True)
            receipt = collect_runtime(PLAN, attempt, "schema", True, "NATURAL")
            if jsonschema is not None:
                jsonschema.validate(
                    receipt, json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
                )
            self.assertEqual(receipt["errors"], [])


if __name__ == "__main__":
    unittest.main()
