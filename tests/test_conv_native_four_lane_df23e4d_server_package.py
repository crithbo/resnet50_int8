from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import conv_native_four_lane_df23e4d_server_runtime as runtime
from tools import validate_conv_native_four_lane_df23e4d_server_package as validator


ROOT = Path(__file__).resolve().parents[1]
OBSERVER = (
    ROOT
    / "tests/rtl_audit"
    / "conv_native_four_lane_df23e4d_progress_observer.svh"
)


class NativeFourLaneServerPackageTests(unittest.TestCase):
    def test_exact_observer_focused_frontend_and_semantic_closure(self) -> None:
        iverilog_name = shutil.which("iverilog")
        self.assertIsNotNone(iverilog_name)
        text = OBSERVER.read_text(encoding="utf-8")
        specialized = text
        for selector in (
            "[n4_obs_group_id]",
            "[n4_obs_local_slice_id]",
            "[n4_obs_mse]",
            "[n4_obs_req]",
            "[n4_obs_bank]",
        ):
            specialized = specialized.replace(selector, "[0]")
        focused = validator._focus_prefix() + specialized + "\nendmodule\n"
        with tempfile.TemporaryDirectory(prefix="native4-observer-test-") as name:
            result = validator._compile_focus(
                Path(str(iverilog_name)), Path(name), "positive", focused
            )
        self.assertEqual(result["exit_code"], 0, result["stderr"])
        self.assertTrue(validator._observer_semantic_closure(text)["valid"])

    def test_deleted_qualified_update_fails_semantic_closure(self) -> None:
        text = OBSERVER.read_text(encoding="utf-8")
        mutant = text.replace("n4_obs_req_accept_count++;\n", "", 1)
        self.assertFalse(
            validator._observer_semantic_closure(mutant)["valid"]
        )

    def test_natural_terminal_and_feature_binding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="native4-runtime-test-") as name:
            root = Path(name)
            sim = root / "sim.log"
            observer = root / "observer.log"
            output = root / "receipt.json"
            sim.write_text(
                "[RETURN_OBSERVER] enabled "
                "N4PERF_FEATURE_ENABLE_V1 "
                "feature=NATIVE4_PROGRESS enabled=1 "
                "heartbeat_cycles=262144 "
                "stall_window_cycles=1048576 expected_stages=1\n"
                "$finish at simulation time 123\n",
                encoding="utf-8",
                newline="\n",
            )
            observer.write_text(
                "# Conv native four-lane progress observer v1\n"
                "N4PERF_FEATURE_ENABLE_V1 "
                "feature=NATIVE4_PROGRESS enabled=1 "
                "heartbeat_cycles=262144 "
                "stall_window_cycles=1048576 expected_stages=1\n"
                "N4PERF_CANONICAL_DECISION_V1 "
                "decision=EXPECTED_STAGE_PREFIX_COMPLETE "
                "reason=control boundary=slice_finish\n",
                encoding="utf-8",
                newline="\n",
            )
            result = runtime.qualify_run(
                "control", sim, observer, output
            )
            self.assertTrue(result["valid"])
            sim.write_text(
                sim.read_text(encoding="utf-8").replace(
                    "$finish at simulation time 123\n", ""
                ),
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaises(runtime.RuntimeErrorContract):
                runtime.qualify_run(
                    "negative", sim, observer, root / "negative.json"
                )

    def test_guard_identity_comes_from_manifest(self) -> None:
        from tools import conv_native_four_lane_package_observer_guard as guard

        with tempfile.TemporaryDirectory(prefix="native4-guard-test-") as name:
            package = Path(name)
            target = package / validator.OBSERVER_REL
            target.parent.mkdir(parents=True)
            shutil.copy2(OBSERVER, target)
            (package / "package_manifest.json").write_text(
                json.dumps(
                    {
                        "observer_binding": {
                            "source": validator.OBSERVER_REL.as_posix(),
                            "source_sha256": validator.sha256(target),
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertTrue(guard.receipt(package)["valid"])
            target.write_bytes(target.read_bytes() + b"\n")
            self.assertFalse(guard.receipt(package)["valid"])


if __name__ == "__main__":
    unittest.main()
