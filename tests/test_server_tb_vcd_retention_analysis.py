from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.server_tb_vcd_retention_analysis import (
    analyze_chunk,
    apply_retention,
    retention_plan,
)


ROOT = Path(__file__).resolve().parents[1]
VCD = ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/small_causal.vcd"
MULTILINE_VCD = ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/multiline_timescale.vcd"
SCHEMA = ROOT / "schemas/server_tb_vcd_retention_analysis_v1.schema.json"


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


class TbVcdRetentionAnalysisTests(unittest.TestCase):
    def test_vcd_streaming_resume_and_xz_summary(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            first = analyze_chunk(VCD, state_dir, "vcd", max_bytes=120)
            self.assertEqual(first["status"], "IN_PROGRESS")
            while json.loads((state_dir / "analysis_state.json").read_text())["status"] == "IN_PROGRESS":
                analyze_chunk(VCD, state_dir, "vcd", max_bytes=120)
            state = json.loads((state_dir / "analysis_state.json").read_text())
            checkpoints = (state_dir / "checkpoints.jsonl").read_text().splitlines()
            self.assertGreater(len(checkpoints), 1)
            self.assertEqual(state["byte_offset"], state["source"]["bytes"])
            self.assertGreater(sum(item["xz_transitions"] for item in state["signal_summaries"].values()), 0)
            self.assertTrue((state_dir / "report.md").is_file())
            try:
                import jsonschema
            except ImportError:
                return
            jsonschema.validate(state, json.loads(SCHEMA.read_text(encoding="utf-8")))

    def test_root_cause_unique_stops_further_scan(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            analyze_chunk(VCD, state_dir, "vcd", max_bytes=100, root_cause_unique=True)
            with self.assertRaisesRegex(ValueError, "further scan is forbidden"):
                analyze_chunk(VCD, state_dir, "vcd", max_bytes=100)

    def test_legal_multiline_timescale_is_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state_dir = Path(raw) / "state"
            analyze_chunk(MULTILINE_VCD, state_dir, "vcd", max_bytes=10000)
            state = json.loads((state_dir / "analysis_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "EOF_REACHED")
            self.assertEqual(state["timescale"], "1 ns")

    def test_zip_member_and_jsonl_are_streamed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            archive = base / "return.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(VCD, "root/evidence/wave.vcd")
            checkpoint = analyze_chunk(archive, base / "zip_state", "vcd", "root/evidence/wave.vcd", 80)
            self.assertGreater(checkpoint["end_offset"], 0)
            events = base / "events.jsonl"
            events.write_text(
                json.dumps({"sim_time": 1, "signal_id": "s", "value_4state": "x"}) + "\n" +
                json.dumps({"sim_time": 2, "signal_id": "s", "value_4state": "1"}) + "\n",
                encoding="utf-8",
            )
            analyze_chunk(events, base / "jsonl_state", "jsonl", max_bytes=1000)
            state = json.loads((base / "jsonl_state/analysis_state.json").read_text())
            self.assertEqual(state["signal_summaries"]["s"]["xz_transitions"], 1)

    def _index(self, root: Path, unsafe_group: str | None = None) -> dict:
        groups = []
        metrics = ([0, 1], [0, 2], [9, 0], [0, 4], [0, 5])
        for number, metric in enumerate(metrics, start=1):
            group_dir = root / f"g{number}"
            group_dir.mkdir()
            records = []
            for name in ("source.zip", "return.zip", "sidecar.json", "wave.vcd"):
                path = group_dir / name
                path.write_text(f"g{number}:{name}", encoding="utf-8")
                records.append(identity(path))
            group = {
                "group_id": f"g{number}", "sequence": number, "progress_metric": metric,
                "source_package": records[0], "return_zip": records[1], "sidecar": records[2], "raw_evidence": [records[3]],
                "analysis_complete": True, "family_consumed": True, "mainline_consumed": True,
                "deterministic_core_evidence": True, "protected_set_audit_pass": True,
            }
            groups.append(group)
        if unsafe_group:
            groups[0][unsafe_group] = False
        return {"schema": "server-tb-vcd-retention-analysis-v1", "kind": "retention_index", "family": "f", "track": "t", "storage_root": root.as_posix(), "max_raw_groups": 3, "groups": groups}

    def test_retention_slots_are_max_progress_plus_latest_two(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            index = self._index(Path(raw))
            plan = retention_plan(index)
            self.assertTrue(plan["pass"], plan)
            self.assertEqual(plan["slots"], {"MAX_PROGRESS": "g3", "LATEST_1": "g5", "LATEST_2": "g4"})
            self.assertEqual(plan["delete_group_ids"], ["g2", "g1"])

    def test_unanalyzed_or_unconsumed_return_is_protected(self) -> None:
        for field in ("analysis_complete", "family_consumed", "mainline_consumed", "deterministic_core_evidence", "protected_set_audit_pass"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                index = self._index(Path(raw), field)
                plan = retention_plan(index)
                self.assertFalse(plan["pass"])
                self.assertIn(field, "\n".join(plan["errors"]))

    def test_apply_deletes_only_exact_raw_group_and_preserves_reports(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            index = self._index(root)
            for name in ("task_record.md", "report.md", "core_evidence.zip"):
                (root / name).write_text(name, encoding="utf-8")
            plan = retention_plan(index)
            receipt = apply_retention(index, plan)
            self.assertTrue(receipt["pass"])
            self.assertFalse((root / "g1/return.zip").exists())
            self.assertFalse((root / "g2/return.zip").exists())
            self.assertTrue((root / "g3/return.zip").exists())
            self.assertTrue((root / "task_record.md").exists())
            self.assertTrue((root / "report.md").exists())
            self.assertTrue((root / "core_evidence.zip").exists())


if __name__ == "__main__":
    unittest.main()
