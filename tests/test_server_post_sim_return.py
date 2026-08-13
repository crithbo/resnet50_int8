from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

from tools.server_post_sim_return import (
    ReturnCoreError,
    finalize,
    validate_final_zip,
    validate_request,
)
from tools.server_waveform_mandatory_return import collect_runtime


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/server_post_sim_return.py"
REQUEST_SCHEMA = ROOT / "schemas/server_post_sim_return_request_v1.schema.json"
CONTRACT_SCHEMA = ROOT / "schemas/server_post_sim_return_contract_v1.schema.json"
VALIDATION_SCHEMA = ROOT / "schemas/server_post_sim_return_validation_v1.schema.json"
DISPATCH = ROOT / "contracts/server_post_sim_return_next_fresh_dispatch_v1.json"
WAVE_PLAN_FIXTURE = (
    ROOT / "fixtures/server_waveform_mandatory_return_v2/positive_plan.json"
)
FSDB_PLAN_FIXTURE = (
    ROOT / "fixtures/server_waveform_mandatory_return_v3/positive_plan.json"
)
WAVE_HELPER = ROOT / "tools/server_waveform_mandatory_return.py"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PostSimReturnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.package = self.root / "package"
        self.attempt = self.root / "attempt"
        self.result = self.root / "simresult"
        for path in (self.package, self.attempt, self.result):
            path.mkdir()
        (self.attempt / "run.log").write_text("simulation evidence\n", encoding="utf-8")
        (self.attempt / "c0").mkdir()
        (self.attempt / "c0/source_bound_causal.log").write_text(
            "CODEX_PROBE_V1 kind=EVENT boundary=target instance=tb.dut.probe "
            "time=10 mask=1 payload=2 seq=0\n",
            encoding="utf-8",
        )
        (self.package / "PACKAGE_MANIFEST.json").write_text("{}\n", encoding="utf-8")
        self.plugin = self.package / "plugin.py"
        self.plugin.write_text(
            "import argparse, json\n"
            "from pathlib import Path\n"
            "p=argparse.ArgumentParser(); p.add_argument('--log', required=True); "
            "p.add_argument('--output', required=True); a=p.parse_args()\n"
            "text=Path(a.log).read_text(encoding='utf-8')\n"
            "if 'kind=EVENT' not in text: raise SystemExit(9)\n"
            "out=Path(a.output); out.parent.mkdir(parents=True, exist_ok=True); "
            "out.write_text(json.dumps({'decision':'LIVE_CAUSAL_EVENT_ACCEPTED'})+'\\n', encoding='utf-8')\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def request(self) -> dict:
        return {
            "schema": "server-post-sim-return-request-v1",
            "package_id": "synthetic_pkg",
            "result_root": "/home/panqs/ndp/simresult",
            "return_basename_template": "{package_id}_{execution_id}_return.zip",
            "core_entries": [
                {
                    "source_root": "attempt",
                    "source": "run.log",
                    "archive": "raw/run.log",
                    "required": True,
                },
                {
                    "source_root": "package",
                    "source": "PACKAGE_MANIFEST.json",
                    "archive": "identity/PACKAGE_MANIFEST.json",
                    "required": True,
                },
            ],
            "plugins": [
                {
                    "plugin_id": "decision",
                    "argv": [
                        sys.executable,
                        "{package_root}/plugin.py",
                        "--log",
                        "{attempt_root}/c0/source_bound_causal.log",
                        "--output",
                        "{attempt_root}/evidence/decision.json",
                    ],
                    "cwd_root": "attempt",
                    "timeout_seconds": 5,
                    "required_for_adjudication": True,
                }
            ],
            "max_plugin_output_bytes": 4096,
            "claim_boundary": "synthetic return-core fixture only",
        }

    def environment(self, **updates: str) -> dict[str, str]:
        values = {
            "CODEX_PACKAGE_ROOT": str(self.package),
            "CODEX_ATTEMPT_ROOT": str(self.attempt),
            "CODEX_EXECUTION_ID": "r123_456",
            "CODEX_SIM_EXIT_CODE": "0",
            "CODEX_SIM_SIGNAL": "NONE",
            "CODEX_SIM_STARTED": "true",
            "CODEX_NATURAL_TERMINAL": "true",
        }
        values.update(updates)
        return values

    def enable_waveform(self, request: dict, *, fsdb: bool = False) -> tuple[dict, Path]:
        request = copy.deepcopy(request)
        request["waveform_discovery"] = {
            "plan_member": "contracts/server_waveform_mandatory_plan.json",
            "collector_member": "package_tools/server_waveform_mandatory_return.py",
            "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
            "collect_all_matching": True,
            "required_when_simulation_started": True,
            "no_size_limit": True,
            "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json",
        }
        fixture = FSDB_PLAN_FIXTURE if fsdb else WAVE_PLAN_FIXTURE
        plan = json.loads(fixture.read_text(encoding="utf-8"))
        plan["package_id"] = request["package_id"]
        plan_path = self.package / request["waveform_discovery"]["plan_member"]
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(
            json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        helper_path = self.package / request["waveform_discovery"]["collector_member"]
        helper_path.parent.mkdir(parents=True, exist_ok=True)
        helper_path.write_bytes(WAVE_HELPER.read_bytes())
        return request, plan_path

    def write_wave_receipt(
        self, plan_path: Path, *, execution_id: str, exit_kind: str
    ) -> dict:
        receipt = collect_runtime(
            plan_path, self.attempt, execution_id, True, exit_kind
        )
        receipt_path = self.attempt / "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return receipt

    def returned_manifest(self, result: dict) -> dict:
        with zipfile.ZipFile(result["return_zip"], "r") as archive:
            name = next(
                item
                for item in archive.namelist()
                if item.endswith("/RETURN_CORE_MANIFEST.json")
            )
            self.assertIsNone(archive.testzip())
            return json.loads(archive.read(name))

    def test_schemas_and_dispatch(self) -> None:
        request = self.request()
        if jsonschema is not None:
            jsonschema.validate(
                request, json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))
            )
        self.assertEqual(validate_request(request), [])
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(dispatch["enforcement"], "required_next_fresh")
        self.assertFalse(dispatch["runtime_contract"]["plugin_failure_blocks_core_return"])
        self.assertEqual(
            dispatch["runtime_contract"]["waveform_dynamic_discovery"]["copy_mode"],
            "STREAM_ALL_MATCHING_NO_SIZE_LIMIT",
        )

    def test_natural_success_publishes_complete_return(self) -> None:
        result = finalize(
            self.request(), environment=self.environment(), result_root_override=self.result
        )
        self.assertTrue(result["published"])
        self.assertEqual(result["disposition"], "COMPLETE_RETURN")
        manifest = self.returned_manifest(result)
        self.assertEqual(manifest["disposition"], "COMPLETE_RETURN")
        self.assertTrue(Path(result["sidecar"]).is_file())

    def test_required_plugin_failure_still_publishes_core(self) -> None:
        self.plugin.write_text(
            "import sys\nprint('analysis failed', file=sys.stderr)\nraise SystemExit(9)\n",
            encoding="utf-8",
        )
        result = finalize(
            self.request(), environment=self.environment(), result_root_override=self.result
        )
        self.assertTrue(result["published"])
        self.assertEqual(result["disposition"], "EVIDENCE_INCOMPLETE")
        manifest = self.returned_manifest(result)
        self.assertEqual(manifest["required_plugin_failures"], ["decision"])

    def test_missing_required_entry_still_publishes_core(self) -> None:
        (self.attempt / "run.log").unlink()
        result = finalize(
            self.request(), environment=self.environment(), result_root_override=self.result
        )
        self.assertTrue(result["published"])
        self.assertEqual(result["disposition"], "EVIDENCE_INCOMPLETE")
        self.assertTrue(self.returned_manifest(result)["missing_required_entries"])

    def test_simulation_nonzero_still_publishes_partial_return(self) -> None:
        result = finalize(
            self.request(),
            environment=self.environment(
                CODEX_SIM_EXIT_CODE="124",
                CODEX_NATURAL_TERMINAL="false",
            ),
            result_root_override=self.result,
        )
        self.assertTrue(result["published"])
        self.assertEqual(result["disposition"], "PARTIAL_EXECUTION_RETURN")

    def test_started_return_streams_every_waveform_shard(self) -> None:
        request, plan_path = self.enable_waveform(self.request())
        wave_root = self.attempt / "run/sim_results"
        wave_root.mkdir(parents=True)
        (wave_root / "wave.vpd").write_bytes(b"primary-vpd")
        (wave_root / "wave.vpd.001").write_bytes(b"shard-vpd")
        receipt = self.write_wave_receipt(
            plan_path, execution_id="r123_456", exit_kind="NATURAL"
        )
        self.assertTrue(receipt["pass"], receipt["errors"])
        result = finalize(
            request, environment=self.environment(), result_root_override=self.result
        )
        self.assertEqual(result["disposition"], "COMPLETE_RETURN")
        manifest = self.returned_manifest(result)
        self.assertTrue(manifest["waveform_no_size_limit"])
        self.assertEqual(len(manifest["waveform_entry_receipts"]), 3)
        with zipfile.ZipFile(result["return_zip"]) as archive:
            wave_members = [
                name
                for name in archive.namelist()
                if name.endswith("wave.vpd") or "/wave.vpd." in name
            ]
        self.assertEqual(len(wave_members), 2)

    def test_started_return_streams_every_fsdb_shard(self) -> None:
        request, plan_path = self.enable_waveform(self.request(), fsdb=True)
        wave_root = self.attempt / "run/sim_results"
        wave_root.mkdir(parents=True)
        (wave_root / "wave.fsdb").write_bytes(b"primary-fsdb")
        (wave_root / "wave.fsdb.001").write_bytes(b"shard-fsdb")
        receipt = self.write_wave_receipt(
            plan_path, execution_id="r123_456", exit_kind="NATURAL"
        )
        self.assertTrue(receipt["pass"], receipt["errors"])
        result = finalize(
            request, environment=self.environment(), result_root_override=self.result
        )
        self.assertEqual(result["disposition"], "COMPLETE_RETURN")
        manifest = self.returned_manifest(result)
        kinds = {item["kind"] for item in manifest["waveform_entry_receipts"]}
        self.assertIn("waveform_fsdb", kinds)
        with zipfile.ZipFile(result["return_zip"]) as archive:
            wave_members = [
                name
                for name in archive.namelist()
                if name.endswith("wave.fsdb") or "/wave.fsdb." in name
            ]
        self.assertEqual(len(wave_members), 2)

    def test_started_missing_waveform_still_publishes_fail_closed_return(self) -> None:
        request, _ = self.enable_waveform(self.request())
        result = finalize(
            request, environment=self.environment(), result_root_override=self.result
        )
        self.assertTrue(result["published"])
        self.assertEqual(result["disposition"], "EVIDENCE_INCOMPLETE")
        manifest = self.returned_manifest(result)
        self.assertTrue(
            any("runtime receipt is absent" in item for item in manifest["waveform_errors"])
        )

    def test_compile_failure_may_omit_waveform_but_keeps_core_return(self) -> None:
        request, _ = self.enable_waveform(self.request())
        result = finalize(
            request,
            environment=self.environment(
                CODEX_SIM_STARTED="false",
                CODEX_SIM_EXIT_CODE="1",
                CODEX_NATURAL_TERMINAL="false",
            ),
            result_root_override=self.result,
        )
        self.assertTrue(result["published"])
        self.assertEqual(result["disposition"], "SIM_NOT_STARTED_RETURN")
        self.assertEqual(self.returned_manifest(result)["waveform_errors"], [])

    def test_multi_megabyte_wave_has_no_return_size_cap(self) -> None:
        request, plan_path = self.enable_waveform(self.request())
        wave_root = self.attempt / "run/sim_results"
        wave_root.mkdir(parents=True)
        payload = bytes(range(256)) * 32768
        (wave_root / "wave.vpd").write_bytes(payload)
        receipt = self.write_wave_receipt(
            plan_path, execution_id="r123_456", exit_kind="NATURAL"
        )
        self.assertTrue(receipt["pass"], receipt["errors"])
        result = finalize(
            request, environment=self.environment(), result_root_override=self.result
        )
        self.assertGreater(result["return_bytes"], len(payload))
        manifest = self.returned_manifest(result)
        vpd = next(
            item
            for item in manifest["waveform_entry_receipts"]
            if item.get("kind") == "waveform_vpd"
        )
        self.assertEqual(vpd["bytes"], len(payload))
        self.assertEqual(vpd["sha256"], hashlib.sha256(payload).hexdigest())

    def test_idempotent_reentry_reuses_exact_return(self) -> None:
        first = finalize(
            self.request(), environment=self.environment(), result_root_override=self.result
        )
        first_bytes = Path(first["return_zip"]).read_bytes()
        second = finalize(
            self.request(), environment=self.environment(), result_root_override=self.result
        )
        self.assertEqual(second["phase"], "PUBLISHED_IDEMPOTENT")
        self.assertEqual(Path(first["return_zip"]).read_bytes(), first_bytes)

    def test_publish_failure_leaves_recoverable_state(self) -> None:
        invalid_result = self.root / "result_is_file"
        invalid_result.write_text("not a directory", encoding="utf-8")
        with self.assertRaises(ReturnCoreError):
            finalize(
                self.request(),
                environment=self.environment(),
                result_root_override=invalid_result,
            )
        state = json.loads(
            (
                self.attempt
                / "evidence/return_core/RETURN_FINALIZER_STATE.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(state["phase"], "FAILED_RECOVERABLE_FROM_ATTEMPT_ROOT")
        self.assertIn("do not rerun simulation", state["recovery"])

    def test_request_aggregates_contract_errors(self) -> None:
        request = self.request()
        request["result_root"] = "/tmp/result"
        request["core_entries"][0]["source"] = "../escape"
        request["plugins"][0]["timeout_seconds"] = 0
        errors = validate_request(request)
        self.assertGreaterEqual(len(errors), 3)

    def build_package(
        self,
        *,
        helper_mutation: bytes = b"",
        omit_runner_token: str | None = None,
        wrapper: bool = False,
        final_block_only_parser: bool = False,
        omit_partial_exit_disposition: bool = False,
        waveform: bool = False,
    ) -> Path:
        package_id = "synthetic_pkg"
        top = package_id
        request = self.request()
        plan_data: bytes | None = None
        if waveform:
            request, plan_path = self.enable_waveform(request)
            plan_data = plan_path.read_bytes()
        request_data = (
            json.dumps(request, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        helper_data = HELPER.read_bytes() + helper_mutation
        runner_lines = [
            "#!/usr/bin/env bash",
            "export CODEX_PACKAGE_ROOT=...",
            "export CODEX_ATTEMPT_ROOT=...",
            "export CODEX_EXECUTION_ID=...",
            "export CODEX_SIM_EXIT_CODE=0",
            "export CODEX_SIM_SIGNAL=NONE",
            "export CODEX_SIM_STARTED=true",
            "export CODEX_NATURAL_TERMINAL=true",
            "# RETURN_FINALIZER_STATE.json",
            "python3 package_tools/server_post_sim_return.py finalize --request contracts/server_post_sim_return_request.json",
        ]
        if omit_runner_token is not None:
            runner_lines = [line.replace(omit_runner_token, "MISSING") for line in runner_lines]
        if wrapper:
            runner_lines.append("base.collect(a,b,c,d,e)")
        runner_data = ("\n".join(runner_lines) + "\n").encode("utf-8")
        contract = {
            "schema": "server-post-sim-return-contract-v1",
            "package_id": package_id,
            "runner_member": "PREPARE_AND_RUN.sh",
            "helper_member": "package_tools/server_post_sim_return.py",
            "helper_sha256": sha(HELPER.read_bytes()),
            "request_member": "contracts/server_post_sim_return_request.json",
            "request_sha256": sha(request_data),
            "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR",
            "sim_exit_persisted_before_plugins": True,
            "plugin_failure_blocks_core_return": False,
            "required_scenarios": [
                "natural_success",
                "natural_success_plugin_failure",
                "simulation_nonzero",
                "idempotent_reentry",
            ],
            "partial_exit_live_causal_record": {
                "rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
                "enforcement": "required_next_fresh",
                "required_signals": ["INT", "TERM"],
                "final_block_ring_sole_input_forbidden": True,
                "plugin_dispositions": [] if omit_partial_exit_disposition else [
                    {
                        "plugin_id": "decision",
                        "disposition": "LIVE_CAUSAL_FIXTURE",
                        "input_root": "attempt",
                        "input_path": "c0/source_bound_causal.log",
                        "fixture_member": "diagnostics/partial_exit_live/decision.log",
                        "input_kind": "QUALIFIED_LIVE_RECORD",
                        "output_root": "attempt",
                        "output_path": "evidence/decision.json",
                        "expected_exit_code": 0,
                        "timeout_seconds": 5,
                    }
                ],
            },
            "claim_boundary": "synthetic exact ZIP only",
        }
        if not omit_partial_exit_disposition and jsonschema is not None:
            jsonschema.validate(
                contract, json.loads(CONTRACT_SCHEMA.read_text(encoding="utf-8"))
            )
        plugin_data = self.plugin.read_bytes()
        if final_block_only_parser:
            plugin_data = (
                "import argparse, json\n"
                "from pathlib import Path\n"
                "p=argparse.ArgumentParser(); p.add_argument('--log', required=True); "
                "p.add_argument('--output', required=True); a=p.parse_args()\n"
                "text=Path(a.log).read_text(encoding='utf-8')\n"
                "if 'kind=RING_POST' not in text: raise SystemExit(9)\n"
                "Path(a.output).write_text(json.dumps({'decision':'RING_ONLY'})+'\\n', encoding='utf-8')\n"
            ).encode("utf-8")
        zip_path = self.root / f"package_{os.urandom(4).hex()}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(f"{top}/PREPARE_AND_RUN.sh", runner_data)
            archive.writestr(
                f"{top}/package_tools/server_post_sim_return.py", helper_data
            )
            archive.writestr(
                f"{top}/contracts/server_post_sim_return_request.json",
                request_data,
            )
            archive.writestr(
                f"{top}/contracts/server_post_sim_return_contract.json",
                json.dumps(contract, indent=2, sort_keys=True) + "\n",
            )
            archive.writestr(f"{top}/plugin.py", plugin_data)
            archive.writestr(
                f"{top}/diagnostics/partial_exit_live/decision.log",
                "CODEX_PROBE_V1 kind=EVENT boundary=target instance=tb.dut.probe "
                "time=10 mask=1 payload=2 seq=0\n",
            )
            if waveform:
                assert plan_data is not None
                archive.writestr(
                    f"{top}/contracts/server_waveform_mandatory_plan.json",
                    plan_data,
                )
                archive.writestr(
                    f"{top}/package_tools/server_waveform_mandatory_return.py",
                    WAVE_HELPER.read_bytes(),
                )
        return zip_path

    def test_exact_final_zip_passes(self) -> None:
        report = validate_final_zip(self.build_package())
        self.assertTrue(report["pass"], report)
        if jsonschema is not None:
            jsonschema.validate(
                report, json.loads(VALIDATION_SCHEMA.read_text(encoding="utf-8"))
            )

    def test_exact_final_zip_waveform_request_runs_all_scenarios(self) -> None:
        report = validate_final_zip(self.build_package(waveform=True))
        self.assertTrue(report["pass"], report)

    def test_final_zip_rejects_helper_mutation(self) -> None:
        report = validate_final_zip(self.build_package(helper_mutation=b"\n# edit\n"))
        self.assertFalse(report["pass"])
        self.assertTrue(any("helper SHA" in item for item in report["errors"]))

    def test_final_zip_rejects_missing_runner_token(self) -> None:
        report = validate_final_zip(
            self.build_package(omit_runner_token="CODEX_NATURAL_TERMINAL")
        )
        self.assertFalse(report["pass"])
        self.assertTrue(any("runner tokens" in item for item in report["errors"]))

    def test_final_zip_rejects_family_positional_wrapper(self) -> None:
        report = validate_final_zip(self.build_package(wrapper=True))
        self.assertFalse(report["pass"])
        self.assertTrue(any("positional collector" in item for item in report["errors"]))

    def test_final_zip_rejects_p33b_final_block_only_parser(self) -> None:
        report = validate_final_zip(self.build_package(final_block_only_parser=True))
        self.assertFalse(report["pass"])
        self.assertTrue(
            any("partial-exit live fixture failed" in item for item in report["errors"]),
            report,
        )
        fixture = report["details"]["partial_exit_live_causal_record"]["plugin_results"]["decision"]
        self.assertEqual(fixture["exit_code"], 9)

    def test_final_zip_rejects_missing_required_plugin_disposition(self) -> None:
        report = validate_final_zip(
            self.build_package(omit_partial_exit_disposition=True)
        )
        self.assertFalse(report["pass"])
        self.assertTrue(
            any("exactly cover required plugins" in item for item in report["errors"]),
            report,
        )


if __name__ == "__main__":
    unittest.main()
