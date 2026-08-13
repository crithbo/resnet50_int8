from __future__ import annotations

import hashlib
import json
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.server_waveform_local_analysis import (
    convert_vcd_to_fst,
    convert_vpd,
    extract_vcd,
    inspect_toolchain,
    prepare_conversion_request,
    validate_vcd,
)


ROOT = Path(__file__).resolve().parents[1]
VCD = ROOT / "fixtures/server_waveform_local_analysis_v1/small.vcd"
SCHEMA = ROOT / "schemas/server_waveform_local_analysis_v1.schema.json"
DISPATCH = ROOT / "contracts/server_waveform_local_analysis_dispatch_v1.json"


class WaveformLocalAnalysisTests(unittest.TestCase):
    def test_contract_and_local_toolchain(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema"]["const"], "server-waveform-local-analysis-v1")
        self.assertEqual(
            dispatch["rule_delta_proposal"],
            "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
        )
        report = inspect_toolchain()
        self.assertIn("gtkwave", report["tools"])
        self.assertIn("vpd2vcd", report["tools"])

    def _return_zip(self, root: Path, *, corrupt: bool = False) -> Path:
        wave = b"synthetic-vpd-payload"
        digest = hashlib.sha256(wave).hexdigest()
        receipt = {
            "schema": "server-waveform-runtime-receipt-v2",
            "pass": True,
            "errors": [],
            "waveforms": [
                {
                    "archive_path": "waveforms/run/wave.vpd",
                    "bytes": len(wave),
                    "sha256": digest,
                    "completeness": "PARTIAL",
                }
            ],
        }
        target = root / "return.zip"
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("pkg/waveforms/WAVEFORM_RUNTIME_RECEIPT.json", json.dumps(receipt))
            archive.writestr("pkg/waveforms/run/wave.vpd", wave + (b"bad" if corrupt else b""))
        return target

    def test_prepare_conversion_request_binds_return_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = prepare_conversion_request(self._return_zip(Path(directory)))
            self.assertTrue(report["pass"], report["errors"])
            self.assertEqual(len(report["jobs"]), 1)
            self.assertFalse(report["rerun_simulation_required"])
            self.assertEqual(report["jobs"][0]["required_server_tool"], "vpd2vcd")

    def test_prepare_conversion_request_rejects_corrupt_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = prepare_conversion_request(self._return_zip(Path(directory), corrupt=True))
            self.assertFalse(report["pass"])
            self.assertTrue(any("identity mismatch" in item for item in report["errors"]))

    def test_vcd_catalog_and_selected_trace(self) -> None:
        catalog = validate_vcd(VCD)
        self.assertTrue(catalog["pass"], catalog["errors"])
        self.assertEqual(catalog["signal_count"], 3)
        self.assertEqual(catalog["timescale"], "1ns")
        self.assertEqual(catalog["last_time"], 15)
        trace = extract_vcd(VCD, [r"dut\.(valid|ready)$"])
        self.assertTrue(trace["pass"], trace["errors"])
        self.assertEqual(len(trace["selected_signals"]), 2)
        self.assertEqual(trace["event_count"], 6)
        self.assertTrue(trace["no_event_limit"])

    def test_invalid_vcd_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "bad.vcd"
            bad.write_text("not a vcd\n", encoding="utf-8")
            report = validate_vcd(bad)
            self.assertFalse(report["pass"])
            self.assertTrue(any("enddefinitions" in item for item in report["errors"]))

    def test_fake_converter_proves_streamed_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vpd = root / "wave.vpd"
            vpd.write_bytes(bytes(range(256)) * 8192)
            converter = root / "fake_vpd2vcd.py"
            converter.write_text(
                "from pathlib import Path\n"
                "import shutil,sys\n"
                f"shutil.copyfile({str(VCD)!r}, sys.argv[2])\n",
                encoding="utf-8",
            )
            converter.chmod(converter.stat().st_mode | stat.S_IXUSR)
            report = convert_vpd(vpd, root / "converted", converter)
            self.assertTrue(report["pass"], report["errors"])
            self.assertEqual(report["input_vpd"]["bytes"], 2 * 1024 * 1024)
            self.assertEqual(report["vcd_catalog"]["signal_count"], 3)
            self.assertIn("available", report["converter_version_probe"])

    def test_fake_fst_converter_binds_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            converter = root / "fake_vcd2fst.py"
            converter.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "Path(sys.argv[2]).write_bytes(b'FST' + Path(sys.argv[1]).read_bytes())\n",
                encoding="utf-8",
            )
            converter.chmod(converter.stat().st_mode | stat.S_IXUSR)
            report = convert_vcd_to_fst(VCD, root / "converted", converter)
            self.assertTrue(report["pass"], report["errors"])
            self.assertGreater(report["output_fst"]["bytes"], 3)

    def test_missing_converter_fails_without_mutating_vpd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vpd = root / "wave.vpd"
            vpd.write_bytes(b"raw")
            before = hashlib.sha256(vpd.read_bytes()).hexdigest()
            report = convert_vpd(vpd, root / "converted", root / "missing")
            self.assertFalse(report["pass"])
            self.assertEqual(hashlib.sha256(vpd.read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
