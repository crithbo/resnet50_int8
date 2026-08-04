from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools import build_decode_silu_control_onecmd_server_test as builder
from tools import decode_silu_control_server_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DecodeSiluControlPackageTests(unittest.TestCase):
    def test_frozen_contract_and_oracle(self) -> None:
        self.assertEqual(sha256(builder.CONTRACT), builder.CONTRACT_SHA256)
        self.assertEqual(sha256(builder.ORACLE), builder.ORACLE_SHA256)
        contract = json.loads(builder.CONTRACT.read_text(encoding="utf-8"))
        self.assertFalse(contract["candidate_release"])
        self.assertFalse(contract["counts_as_requant_e4"])
        self.assertFalse(contract["counts_as_requant_e5"])
        self.assertEqual(contract["execution"]["active_slices"], [0, 1])
        self.assertEqual(contract["execution"]["formal_d_lines_per_slice"], 8)

    def test_formal_data_is_nonzero_and_slice_distinct(self) -> None:
        materialized = builder.MATERIALIZED
        inputs = [
            materialized
            / f"install/op0/slice{slice_id:02d}/matrix_A_linearized_128bit.txt"
            for slice_id in (0, 1)
        ]
        golden = [
            materialized
            / f"golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
            for slice_id in (0, 1)
        ]
        for path in inputs:
            lines = runtime._validate_128(path, 4)
            self.assertTrue(any(int(line, 2) != 0 for line in lines))
        for path in golden:
            lines = runtime._validate_128(path, 8)
            self.assertTrue(any(int(line, 2) != 0 for line in lines))
        self.assertNotEqual(inputs[0].read_bytes(), inputs[1].read_bytes())
        self.assertNotEqual(golden[0].read_bytes(), golden[1].read_bytes())

    def test_capture_edge_observer_is_read_only_and_xmr_safe(self) -> None:
        text = builder._observer_tail()
        self.assertIn("+DECODE_SILU_CONTROL_PROBE", text)
        self.assertIn("boundary=SFU_PREPROCESS_INPUT_CAPTURE", text)
        self.assertIn("boundary=SFU_COEFF_CAPTURE", text)
        self.assertIn("boundary=NORMAL_OUTBUFFER_WRITE_COMMIT", text)
        self.assertIn("boundary=MSE4_WDATA", text)
        active = "\n".join(
            line.split("//", 1)[0]
            for line in text.splitlines()
            if not line.lstrip().startswith("//")
        ).lower()
        for token in ("force ", "deposit", "release ", "<="):
            self.assertNotIn(token, active)
        report = runtime.common.validate_observer_xmr_elaboration(text)
        self.assertEqual(report["status"], "pass")

    def test_tb_target_is_single_manifest_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "native_return_observer.svh"
            target.write_text("// stock\n", encoding="utf-8", newline="\n")
            resolved_root, resolved_target = runtime._resolve_tb_target(
                root, "native_return_observer.svh"
            )
            self.assertEqual(resolved_root, root)
            self.assertEqual(resolved_target, target)
            for bad in (
                "../native_return_observer.svh",
                "rtl/native_return_observer.svh",
                "other.svh",
            ):
                with self.assertRaises(Exception):
                    runtime._resolve_tb_target(root, bad)

    def test_run_script_keeps_one_command_and_explicit_target(self) -> None:
        previous = builder.base.INSTALL_NAME
        builder.base.INSTALL_NAME = builder.INSTALL_NAME
        try:
            script = (
                builder.base._run_script()
                .replace(
                    "package_tools/requant_atomic_server_runtime.py",
                    "package_tools/decode_silu_control_server_runtime.py",
                )
                .replace("+REQUANT_ATOMIC_PROBE", "+DECODE_SILU_CONTROL_PROBE")
            )
        finally:
            builder.base.INSTALL_NAME = previous
        self.assertIn(
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
            script,
        )
        self.assertNotIn("DUMP_VCD=1", script)
        self.assertNotIn("DUMP_FSDB=1", script)


if __name__ == "__main__":
    unittest.main()
