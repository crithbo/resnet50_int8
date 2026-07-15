from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from resnet50_pipeline.conv_1x1_hardware_freeze import compare_hardware_dump


class Conv1x1HardwareFreezeTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        freeze = root / "freeze"
        dump = root / "dump"
        freeze.mkdir()
        value_p = np.asarray([[[[123]]]], dtype=np.int32)
        value_d = np.asarray([[[[17]]]], dtype=np.uint8)
        canonical = {}
        regions = []
        for port, value in (("P", value_p), ("D", value_d)):
            golden_path = freeze / "golden" / f"canonical_{port}.bin"
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_bytes(value.tobytes())
            canonical[port] = {
                "path": f"golden/canonical_{port}.bin",
                "size_bytes": value.nbytes,
                "sha256": hashlib.sha256(value.tobytes()).hexdigest(),
                "dtype": str(value.dtype),
                "shape": list(value.shape),
            }
            dump_path = dump / port / "slice-00.bin"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_bytes(value.reshape(1, 1, 1, 1).tobytes())
            regions.append(
                {
                    "port": port,
                    "slice_id": 0,
                    "sample_start": 0,
                    "sample_count": 1,
                    "logical_start": 0,
                    "logical_count": 1,
                    "payload_bytes": value.nbytes,
                    "size_bytes": value.nbytes,
                    "physical_shape": [1, 1, 1, 1],
                }
            )
        address_payload = json.dumps({"schema_version": "0.1", "regions": regions})
        (freeze / "address_table.json").write_text(address_payload, encoding="utf-8")
        manifest = {
            "freeze_id": "fixture",
            "address_table": {"path": "address_table.json"},
            "canonical_golden": canonical,
        }
        (freeze / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return freeze, dump

    def test_inverse_and_compare_passes_then_reports_first_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            freeze, dump = self._fixture(Path(temporary))
            passed = compare_hardware_dump(freeze, dump)
            self.assertEqual(passed["status"], "passed")
            self.assertEqual(passed["comparisons"]["P"]["mismatch_count"], 0)
            (dump / "D" / "slice-00.bin").write_bytes(bytes([18]))
            failed = compare_hardware_dump(freeze, dump)
            self.assertEqual(failed["status"], "mismatch")
            self.assertEqual(
                failed["comparisons"]["D"]["first_mismatch"],
                {"coordinate": [0, 0, 0, 0], "actual": 18, "golden": 17},
            )


if __name__ == "__main__":
    unittest.main()
