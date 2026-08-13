from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/qlinearadd_node0007_source_bound_stage_filter_v57.py"


class StageFilterTests(unittest.TestCase):
    def run_filter(self, source: str, observer: str) -> tuple[str, dict]:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            src = root / "source.log"
            obs = root / "observer.log"
            out = root / "filtered.log"
            receipt = root / "receipt.json"
            src.write_text(source, encoding="utf-8")
            obs.write_text(observer, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(TOOL), "--source-log", str(src), "--observer-log", str(obs), "--output", str(out), "--receipt", str(receipt)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return out.read_text(encoding="utf-8"), json.loads(receipt.read_text(encoding="utf-8"))

    def test_keeps_only_enabled_and_timed_records_at_or_after_exec_start(self) -> None:
        source = (
            "CODEX_PROBE_V1 kind=ENABLED boundary=b instance=i\n"
            "CODEX_PROBE_V1 kind=EVENT boundary=b instance=i time=99 mask=1 payload=0 payload_known=1 payload_width=1 seq=0\n"
            "CODEX_PROBE_V1 kind=EVENT boundary=b instance=i time=100 mask=1 payload=1 payload_known=1 payload_width=1 seq=1\n"
            "CODEX_PROBE_V1 kind=SUMMARY boundary=b instance=i count=2 state=0 first=99 last=100 maxgap=1 sticky=1 xor=1\n"
        )
        output, receipt = self.run_filter(source, "100 | EXEC_START | stage=1\n")
        self.assertIn("kind=ENABLED", output)
        self.assertNotIn("time=99", output)
        self.assertIn("time=100", output)
        self.assertNotIn("kind=SUMMARY", output)
        self.assertTrue(receipt["stage_start_found"])
        self.assertEqual(receipt["pre_stage_records_dropped"], 1)
        self.assertEqual(receipt["aggregate_records_dropped"], 1)

    def test_no_exec_start_retains_no_transaction_record(self) -> None:
        source = (
            "CODEX_PROBE_V1 kind=ENABLED boundary=b instance=i\n"
            "CODEX_PROBE_V1 kind=EVENT boundary=b instance=i time=10 mask=1 payload=1 payload_known=1 payload_width=1 seq=0\n"
        )
        output, receipt = self.run_filter(source, "# feature marker only\n")
        self.assertEqual(output, "CODEX_PROBE_V1 kind=ENABLED boundary=b instance=i\n")
        self.assertFalse(receipt["stage_start_found"])
        self.assertEqual(receipt["pre_stage_records_dropped"], 1)

    def test_combined_single_input_keeps_only_post_start_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "combined.log"
            output = root / "out.log"
            receipt_path = root / "receipt.json"
            source.write_text(
                "CODEX_PROBE_V1 kind=ENABLED time=1 boundary=x\n"
                "CODEX_PROBE_V1 kind=EVENT time=99 boundary=x\n"
                "100 | EXEC_START | stage=1\n"
                "CODEX_PROBE_V1 kind=EVENT time=100 boundary=x\n",
                encoding="utf-8",
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--source-log",
                    str(source),
                    "--output",
                    str(output),
                    "--receipt",
                    str(receipt_path),
                ],
                check=False,
            )
            self.assertEqual(process.returncode, 0)
            text = output.read_text(encoding="utf-8")
            self.assertNotIn("time=99", text)
            self.assertIn("time=100", text)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertTrue(receipt["stage_start_found"])
            self.assertEqual(receipt["ordered_start_source"], "source_log")


if __name__ == "__main__":
    unittest.main()
