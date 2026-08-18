from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/validate_server_runtime_preflight_native_flow.py"
DISPATCH = ROOT / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json"
FIXTURES = ROOT / "fixtures/server_runtime_preflight_native_flow_v1"


class ServerRuntimePreflightNativeFlowTests(unittest.TestCase):
    def run_tool(self, runner: Path) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(TOOL),
                    "--runner",
                    str(runner),
                    "--dispatch",
                    str(DISPATCH),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            return completed, json.loads(output.read_text(encoding="utf-8"))

    def test_direct_production_launch_passes(self) -> None:
        completed, report = self.run_tool(FIXTURES / "positive_runner.sh")
        self.assertEqual(completed.returncode, 0, report)
        self.assertTrue(report["pass"])
        self.assertEqual(report["forbidden_prelaunch_findings"], [])
        self.assertEqual(report["production_launch_marker_count"], 1)

    def test_post_launch_collection_file_test_is_not_preflight(self) -> None:
        _, report = self.run_tool(FIXTURES / "positive_runner.sh")
        self.assertFalse(any(item["line"] > report["prelaunch_line_count"] for item in report["forbidden_prelaunch_findings"]))

    def test_all_forbidden_checks_are_aggregated(self) -> None:
        completed, report = self.run_tool(FIXTURES / "negative_runner.sh")
        self.assertEqual(completed.returncode, 1)
        mechanisms = {item["mechanism"] for item in report["forbidden_prelaunch_findings"]}
        self.assertEqual(
            mechanisms,
            {
                "shell_file_type_or_readability_test",
                "stat_find_readlink_realpath_inventory",
                "hash_or_tree_identity_of_server_owned_content",
                "git_server_source_identity",
                "command_v_or_which_tool_availability",
                "make_dry_run_or_just_print",
                "module_or_provider_lookup_probe",
                "separate_runtime_preflight_or_attestation_subcommand",
            },
        )

    def test_missing_marker_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            runner = Path(raw) / "runner.sh"
            runner.write_text("#!/bin/sh\nmake compile sim\n", encoding="utf-8")
            completed, report = self.run_tool(runner)
        self.assertEqual(completed.returncode, 1)
        self.assertIn("exactly once", "\n".join(report["errors"]))

    def test_dispatch_retires_provider_prelaunch_gate(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(
            dispatch["policy"]["server_environment_adjudicator"],
            "ACTUAL_PRODUCTION_COMMAND_ONLY",
        )
        self.assertIn(
            "CDA-SERVER-COMPILE-MODULE-PROVIDER-CLOSURE-001",
            dispatch["retired_from_current_blocking"],
        )
        self.assertIn(
            "compile_environment_attestation",
            dispatch["retired_from_current_blocking"],
        )

    def test_public_routing_no_longer_requires_provider_probe(self) -> None:
        server_rule = (ROOT / ".agents/rules/服务器测试包生成规则.md").read_text(encoding="utf-8")
        index = (ROOT / ".agents/rules/生成前必读索引.md").read_text(encoding="utf-8")
        optimizer = (ROOT / ".agents/rules/整网测试收敛优化专项规则.md").read_text(encoding="utf-8")
        self.assertIn("本地不得因服务器工具、license", server_rule)
        self.assertNotIn("必须读取`contracts/server_compile_environment_gate_dispatch_v1.json`", index)
        self.assertIn("SHA/format/style/provenance", optimizer)

    def test_native_failure_review_is_post_failure_and_unknown_safe(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        native = dispatch["native_failure_differential"]
        self.assertEqual(native["timing"], "AFTER_ACTUAL_FAILURE_BEFORE_SUCCESSOR_DESIGN")
        self.assertEqual(native["unknown_semantics"], "DO_NOT_GUESS_AND_DO_NOT_CREATE_PREFLIGHT")
        paths = {item["path"] for item in native["required_reference_paths"]}
        self.assertIn("ndp-sim/README_SERVER_PACKAGE_LOCAL.md", paths)
        self.assertIn("ndp-sim/model_execplan/main.py", paths)
        self.assertIn("NDP_copy01/Makefile.tb_NDP_Top_new_phy", paths)


if __name__ == "__main__":
    unittest.main()
