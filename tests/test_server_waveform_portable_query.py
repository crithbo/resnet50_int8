from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.server_waveform_portable_query import (
    QUERY_SCHEMA,
    RUNTIME_SCHEMA,
    make_runtime_receipt,
    pretty_json,
    render_dump_tcl,
    validate_profile,
    validate_runtime_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/server_waveform_portable_query_v1"
PROFILE = FIXTURE / "profile.json"
VCD = FIXTURE / "wave.vcd"
SOURCE_REPORT = FIXTURE / "source_generation_report.json"
CASES = FIXTURE / "cases.json"
PROFILE_SCHEMA = ROOT / "schemas/server_waveform_portable_profile_v1.schema.json"
QUERY_RECEIPT_SCHEMA = ROOT / "schemas/server_waveform_signal_query_receipt_v1.schema.json"
RUNTIME_RECEIPT_SCHEMA = ROOT / "schemas/server_waveform_portable_runtime_receipt_v1.schema.json"
DISPATCH = ROOT / "contracts/server_waveform_portable_query_profile_v1.json"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty_json(value))


def file_identity(path: Path, relative: str) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "path": relative,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


class PortableWaveformQueryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    def _build_attempt(
        self,
        root: Path,
        *,
        first_fresh: bool = True,
        mode: str = "DIRECT_VCD_AND_QUERY",
        include_vcd: bool = True,
        mutate_query=None,
        omit_allowlist: str | None = None,
    ) -> tuple[dict, dict, Path]:
        attempt_root = "attempts/attempt1"
        attempt = root / "attempts/attempt1"
        run = attempt / "run/sim_results"
        evidence = attempt / "evidence"
        run.mkdir(parents=True)
        evidence.mkdir()
        (run / "wave.vpd").write_bytes(b"authoritative-vpd")
        if include_vcd:
            shutil.copyfile(VCD, run / "wave.vcd")
        shutil.copyfile(SOURCE_REPORT, evidence / "source_generation_report.json")

        dump = render_dump_tcl(self.profile, attempt_root, "20ns", mode)
        (attempt / "dump.tcl").write_text(dump, encoding="utf-8", newline="\n")
        argv = [
            "make",
            "sim",
            "DUMP_VCD=1",
            "DUMP_FSDB=0",
            "TB_DUMP_FSDB=0",
            f"DUMP_PORTABLE_VCD={'1' if mode == 'DIRECT_VCD_AND_QUERY' else '0'}",
        ]
        write_json(attempt / "actual_sim_argv.json", argv)

        raw_bytes = (run / "wave.vpd").read_bytes()
        raw = {
            "schema": "server-waveform-runtime-receipt-v2",
            "package_id": "fixture-package",
            "execution_id": "exec1",
            "plan_sha256": "b" * 64,
            "simulation_started": True,
            "exit_kind": "NATURAL",
            "waveforms": [
                {
                    "source_path": "run/sim_results/wave.vpd",
                    "archive_path": "waveforms/run/sim_results/wave.vpd",
                    "bytes": len(raw_bytes),
                    "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                    "format": "VPD",
                    "completeness": "COMPLETE",
                }
            ],
            "no_size_limit": True,
            "all_matching_collected": True,
            "pass": True,
            "errors": [],
            "claim_boundary": "fixture raw VPD identity",
        }
        write_json(evidence / "WAVEFORM_RUNTIME_RECEIPT.json", raw)

        catalog = self.profile["probe_catalog"]
        query = {
            "schema": QUERY_SCHEMA,
            "package_id": "fixture-package",
            "execution_id": "exec1",
            "attempt_id": "attempt1",
            "profile_sha256": hashlib.sha256(pretty_json(self.profile)).hexdigest(),
            "probe_catalog_sha256": self.profile["probe_catalog_sha256"],
            "timescale": "1 ns",
            "completeness": "COMPLETE",
            "catalog": copy.deepcopy(catalog),
            "capture": {
                "format": "REGISTERED_EVENT_ROWS",
                "ordered": True,
                "every_transition": True,
                "no_byte_limit": True,
                "no_event_limit": True,
                "sampling": False,
                "truncation": False,
                "flush_complete": True,
                "source_generation_report": {
                    "path": f"{attempt_root}/evidence/source_generation_report.json",
                    "sha256": hashlib.sha256(SOURCE_REPORT.read_bytes()).hexdigest(),
                },
            },
            "candidate_coverage": {
                "expected": ["bp_pre", "mask"],
                "covered": ["bp_pre", "mask"],
                "missing": [],
                "unexpected": [],
            },
            "events": [
                {"sequence": 0, "time_tick": 0, "candidate_id": "bp_pre", "hierarchical_path": catalog[0]["hierarchical_path"], "width": 1, "value": "0"},
                {"sequence": 1, "time_tick": 0, "candidate_id": "mask", "hierarchical_path": catalog[1]["hierarchical_path"], "width": 2, "value": "b00"},
                {"sequence": 2, "time_tick": 5, "candidate_id": "bp_pre", "hierarchical_path": catalog[0]["hierarchical_path"], "width": 1, "value": "x"},
                {"sequence": 3, "time_tick": 5, "candidate_id": "mask", "hierarchical_path": catalog[1]["hierarchical_path"], "width": 2, "value": "b0z"},
                {"sequence": 4, "time_tick": 10, "candidate_id": "bp_pre", "hierarchical_path": catalog[0]["hierarchical_path"], "width": 1, "value": "1"},
                {"sequence": 5, "time_tick": 10, "candidate_id": "mask", "hierarchical_path": catalog[1]["hierarchical_path"], "width": 2, "value": "b1x"},
                {"sequence": 6, "time_tick": 15, "candidate_id": "bp_pre", "hierarchical_path": catalog[0]["hierarchical_path"], "width": 1, "value": "z"},
                {"sequence": 7, "time_tick": 15, "candidate_id": "mask", "hierarchical_path": catalog[1]["hierarchical_path"], "width": 2, "value": "b11"}
            ],
            "candidate_end_states": [
                {"candidate_id": "bp_pre", "hierarchical_path": catalog[0]["hierarchical_path"], "width": 1, "time_tick": 15, "value": "z"},
                {"candidate_id": "mask", "hierarchical_path": catalog[1]["hierarchical_path"], "width": 2, "time_tick": 15, "value": "b11"}
            ],
            "claim_boundary": "synthetic query evidence only",
        }
        if mutate_query is not None:
            mutate_query(query)
        write_json(evidence / "SIGNAL_QUERY_RECEIPT.json", query)

        allowlist = [
            f"{attempt_root}/run/sim_results/wave.vpd",
            f"{attempt_root}/evidence/SIGNAL_QUERY_RECEIPT.json",
            f"{attempt_root}/evidence/source_generation_report.json",
        ]
        if include_vcd:
            allowlist.append(f"{attempt_root}/run/sim_results/wave.vcd")
        if omit_allowlist is not None:
            allowlist = [item for item in allowlist if not item.endswith(omit_allowlist)]
        write_json(attempt / "return_allowlist.json", allowlist)

        request = {
            "package_id": "fixture-package",
            "execution_id": "exec1",
            "attempt_id": "attempt1",
            "attempt_root": attempt_root,
            "first_fresh_for_profile": first_fresh,
            "capture_mode": mode,
            "simulation_started": True,
            "exit_kind": "NATURAL",
            "actual_sim_argv_path": f"{attempt_root}/actual_sim_argv.json",
            "dump_tcl_path": f"{attempt_root}/dump.tcl",
            "raw_vpd_runtime_receipt_path": f"{attempt_root}/evidence/WAVEFORM_RUNTIME_RECEIPT.json",
            "portable_vcd_path": f"{attempt_root}/run/sim_results/wave.vcd" if include_vcd else None,
            "signal_query_receipt_path": f"{attempt_root}/evidence/SIGNAL_QUERY_RECEIPT.json",
            "return_allowlist_path": f"{attempt_root}/return_allowlist.json",
        }
        receipt = make_runtime_receipt(self.profile, request, root)
        return receipt, query, attempt

    def test_profile_schema_dispatch_and_case_registry(self) -> None:
        self.assertEqual(validate_profile(self.profile), [])
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(
            dispatch["rule_id"],
            "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
        )
        self.assertIn("DUMP_PORTABLE_VCD=1", dispatch["make_argument_semantics"])
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual(len(cases["positive"]), 5)
        self.assertEqual(len(cases["negative"]), 11)
        if jsonschema is not None:
            jsonschema.validate(self.profile, json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8")))
        for section, field, value in (
            ("raw_vpd", "hard_limit_bytes", 1024),
            ("raw_vpd", "sampling", True),
            ("portable_vcd", "hard_limit_bytes", 1024),
            ("portable_vcd", "truncation", True),
        ):
            bad = copy.deepcopy(self.profile)
            bad[section][field] = value
            self.assertTrue(validate_profile(bad), (section, field))

    def test_misleading_dump_vcd_semantics_is_not_reinterpreted(self) -> None:
        bad = copy.deepcopy(self.profile)
        bad["raw_vpd"]["existing_dump_vcd_semantics"] = "VCD"
        self.assertTrue(any("DUMP_VCD=1" in item for item in validate_profile(bad)))
        rendered = render_dump_tcl(self.profile, "attempts/a", "20ns", "DIRECT_VCD_AND_QUERY")
        self.assertIn("wave.vpd -type VPD", rendered)
        self.assertIn("wave.vcd -type VCD", rendered)

    def test_first_fresh_direct_vcd_and_query_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt, query, _ = self._build_attempt(Path(directory))
            self.assertEqual(receipt["schema"], RUNTIME_SCHEMA)
            report = validate_runtime_receipt(receipt, self.profile, Path(directory))
            self.assertTrue(report["pass"], report)
            self.assertTrue(report["diagnostic_complete"])
            self.assertEqual(receipt["diagnostic_status"], "COMPLETE")
            if jsonschema is not None:
                jsonschema.validate(query, json.loads(QUERY_RECEIPT_SCHEMA.read_text(encoding="utf-8")))
                jsonschema.validate(receipt, json.loads(RUNTIME_RECEIPT_SCHEMA.read_text(encoding="utf-8")))

    def test_later_query_only_exact_catalog_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt, _, _ = self._build_attempt(
                Path(directory), first_fresh=False, mode="QUERY_ONLY", include_vcd=False
            )
            report = validate_runtime_receipt(receipt, self.profile, Path(directory))
            self.assertTrue(report["pass"], report)

    def test_first_fresh_missing_vcd_fails_but_preserves_return(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt, _, _ = self._build_attempt(Path(directory), include_vcd=False)
            report = validate_runtime_receipt(receipt, self.profile, Path(directory))
            self.assertFalse(report["pass"])
            self.assertFalse(report["diagnostic_complete"])
            self.assertEqual(receipt["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")
            self.assertTrue(report["return_must_publish"])
            self.assertEqual(receipt["raw_vpd_runtime_receipt"]["bytes"], (Path(directory) / "attempts/attempt1/evidence/WAVEFORM_RUNTIME_RECEIPT.json").stat().st_size)

    def test_incomplete_query_catalog_fails_query_only(self) -> None:
        def mutate(query: dict) -> None:
            query["candidate_coverage"]["covered"] = ["bp_pre"]
            query["candidate_coverage"]["missing"] = ["mask"]

        with tempfile.TemporaryDirectory() as directory:
            receipt, _, _ = self._build_attempt(
                Path(directory), first_fresh=False, mode="QUERY_ONLY", include_vcd=False, mutate_query=mutate
            )
            report = validate_runtime_receipt(receipt, self.profile, Path(directory))
            self.assertFalse(report["pass"])
            self.assertTrue(any("coverage" in item for item in report["diagnostic_findings"]))

    def test_x_z_and_order_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt, query, _ = self._build_attempt(Path(directory))
            values = [event["value"] for event in query["events"]]
            self.assertIn("x", values)
            self.assertIn("z", values)
            self.assertIn("b0z", values)
            self.assertIn("b1x", values)
            self.assertTrue(validate_runtime_receipt(receipt, self.profile, Path(directory))["pass"])

    def test_transition_gap_and_wrong_width_fail_closed(self) -> None:
        def mutate(query: dict) -> None:
            query["events"][3]["sequence"] = 99
            query["events"][4]["width"] = 2

        with tempfile.TemporaryDirectory() as directory:
            receipt, _, _ = self._build_attempt(
                Path(directory), first_fresh=False, mode="QUERY_ONLY", include_vcd=False, mutate_query=mutate
            )
            findings = validate_runtime_receipt(receipt, self.profile, Path(directory))["diagnostic_findings"]
            self.assertTrue(any("sequence" in item for item in findings))
            self.assertTrue(any("width" in item for item in findings))

    def test_hard_cap_sampling_truncation_and_free_text_fail(self) -> None:
        def mutate(query: dict) -> None:
            query["capture"]["no_event_limit"] = False
            query["capture"]["sampling"] = True
            query["capture"]["truncation"] = True
            query["capture"]["hard_limit_events"] = 8
            query["free_form_text"] = "looks fine"

        with tempfile.TemporaryDirectory() as directory:
            receipt, _, _ = self._build_attempt(
                Path(directory), first_fresh=False, mode="QUERY_ONLY", include_vcd=False, mutate_query=mutate
            )
            report = validate_runtime_receipt(receipt, self.profile, Path(directory))
            self.assertFalse(report["pass"])
            joined = " ".join(report["diagnostic_findings"])
            self.assertIn("no_event_limit", joined)
            self.assertIn("sampling", joined)
            self.assertIn("truncation", joined)
            self.assertIn("unregistered", joined)

    def test_allowlist_omission_and_attempt_drift_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt, _, _ = self._build_attempt(root, omit_allowlist="wave.vcd")
            report = validate_runtime_receipt(receipt, self.profile, root)
            self.assertFalse(report["pass"])
            self.assertTrue(any("allowlist" in item for item in report["errors"]))
            receipt["portable_vcd"]["path"] = "attempts/attempt2/run/sim_results/wave.vcd"
            report = validate_runtime_receipt(receipt, self.profile, root)
            self.assertFalse(report["pass"])
            self.assertTrue(any("attempt" in item or "portable VCD" in item for item in report["errors"]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt, _, _ = self._build_attempt(
                root,
                first_fresh=False,
                mode="QUERY_ONLY",
                include_vcd=False,
                omit_allowlist="SIGNAL_QUERY_RECEIPT.json",
            )
            report = validate_runtime_receipt(receipt, self.profile, root)
            self.assertFalse(report["pass"])
            self.assertTrue(any("allowlist" in item for item in report["errors"]))

    def test_asset_identity_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt, _, attempt = self._build_attempt(root)
            with (attempt / "run/sim_results/wave.vcd").open("ab") as stream:
                stream.write(b"\n#20\n0!\n")
            report = validate_runtime_receipt(receipt, self.profile, root)
            self.assertFalse(report["pass"])
            self.assertTrue(any("identity mismatch" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
