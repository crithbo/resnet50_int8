from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.validate_server_diagnostic_mode_selector import validate_selector, validate_zip


ROOT = Path(__file__).resolve().parents[1]
DISPATCH = ROOT / "contracts/server_diagnostic_mode_selector_dispatch_v1.json"


def selector(mode: str) -> dict:
    observer = mode == "OBSERVER_ONLY_WIDE_CAUSAL"
    return {
        "schema": "server-diagnostic-mode-selector-v1",
        "package_id": "p", "family": "f", "selected_mode": mode,
        "bulk_evidence": {
            "observer_jsonl": observer, "tb_standard_vcd": not observer,
            "vpd": False, "fsdb": False, "ucli_direct_vcd": False, "vendor_signal_query": False,
        },
        "actual_dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
        "lightweight_progress_supervisor": {"enabled": True, "bulk_signal_events": False, "sim_time_heartbeat": True, "process_tree_reap": True},
        "package_members": ["runner.sh", "probe.sv"],
        "return_members": ["observer/chunks/chunk-0.jsonl"] if observer else ["evidence/vcd/wave.vcd"],
        "observer_contract_sha256": "1" * 64 if observer else None,
        "vcd_contract_sha256": None if observer else "2" * 64,
        "claim_boundary": "test",
    }


class DiagnosticModeSelectorTests(unittest.TestCase):
    def test_positive_selectors_conform_to_schema(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema unavailable")
        schema = json.loads((ROOT / "schemas/server_diagnostic_mode_selector_v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(selector("OBSERVER_ONLY_WIDE_CAUSAL"), schema)
        jsonschema.validate(selector("TB_VCD_BOUNDED_CAUSAL_CONE"), schema)

    def test_observer_mode_unchanged_identity(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        for item in dispatch["observer_frozen_assets"]:
            path = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        self.assertTrue(validate_selector(selector("OBSERVER_ONLY_WIDE_CAUSAL"))["pass"])

    def test_vcd_mode_is_explicit_and_exclusive(self) -> None:
        report = validate_selector(selector("TB_VCD_BOUNDED_CAUSAL_CONE"))
        self.assertTrue(report["pass"], report)
        self.assertEqual(report["active_bulk_modes"], ["tb_standard_vcd"])

    def test_bulk_modes_cannot_both_be_enabled(self) -> None:
        item = selector("TB_VCD_BOUNDED_CAUSAL_CONE")
        item["bulk_evidence"]["observer_jsonl"] = True
        self.assertIn("exactly one", "\n".join(validate_selector(item)["errors"]))

    def test_vendor_modes_and_make_dump_fail(self) -> None:
        item = selector("TB_VCD_BOUNDED_CAUSAL_CONE")
        item["bulk_evidence"]["fsdb"] = True
        item["actual_dump_argv"]["DUMP_VCD"] = "1"
        errors = "\n".join(validate_selector(item)["errors"])
        self.assertIn("fsdb", errors)
        self.assertIn("DUMP_VCD", errors)

    def test_vpd_and_ucli_direct_vcd_each_fail(self) -> None:
        for forbidden in ("vpd", "ucli_direct_vcd"):
            item = selector("TB_VCD_BOUNDED_CAUSAL_CONE")
            item["bulk_evidence"][forbidden] = True
            self.assertIn(forbidden, "\n".join(validate_selector(item)["errors"]))

    def test_final_zip_rejects_vendor_and_observer_bulk(self) -> None:
        item = selector("TB_VCD_BOUNDED_CAUSAL_CONE")
        with tempfile.TemporaryDirectory() as raw:
            archive = Path(raw) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("root/runner.sh", "DUMP_VCD=1\n")
                zf.writestr("root/old.fsdb", b"bad")
            report = validate_zip(archive, item)
        self.assertFalse(report["pass"])
        self.assertIn("forbidden waveform member", "\n".join(report["errors"]))

    def test_vcd_mode_rejects_prebuilt_vcd_and_observer_chunk(self) -> None:
        item = selector("TB_VCD_BOUNDED_CAUSAL_CONE")
        item["package_members"].append("stale.vcd")
        self.assertIn("self-include", "\n".join(validate_selector(item)["errors"]))
        item = selector("TB_VCD_BOUNDED_CAUSAL_CONE")
        with tempfile.TemporaryDirectory() as raw:
            archive = Path(raw) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("root/stale.vcd", b"stale")
                zf.writestr("root/observer/chunks/chunk-0.jsonl", "{}\n")
            report = validate_zip(archive, item)
        self.assertFalse(report["pass"])
        errors = "\n".join(report["errors"])
        self.assertIn("self-include", errors)
        self.assertIn("observer JSONL", errors)


if __name__ == "__main__":
    unittest.main()
