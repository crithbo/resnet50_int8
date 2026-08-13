from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "tools" / "validate_server_observer_only_wide_causal.py"
FIXTURE_PATH = ROOT / "fixtures" / "server_observer_only_wide_causal_v1" / "positive_contract.json"
SCHEMA_PATH = ROOT / "schemas" / "server_observer_only_wide_causal_contract_v1.schema.json"
POST_SIM_HELPER = ROOT / "tools" / "server_post_sim_return.py"
SPEC = importlib.util.spec_from_file_location("observer_only_gate", TOOL_PATH)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def encoded(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")


class ObserverOnlyWideCausalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        helper_identity = GATE.canonical_post_sim_helper_identity()
        exemption = self.contract["post_sim_historical_compatibility_exemption"]
        exemption["canonical_helper_bytes"] = helper_identity["bytes"]
        exemption["canonical_helper_sha256"] = helper_identity["sha256"]
        exemption["inert_literal_tokens"] = helper_identity["inert_literal_tokens"]
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_contract_fails(self, contract: dict, fragment: str) -> None:
        report = GATE.validate_contract(contract)
        self.assertFalse(report["pass"], report)
        self.assertTrue(any(fragment in item for item in report["errors"]), report)

    def test_positive_contract_and_json_schema(self) -> None:
        report = GATE.validate_contract(self.contract)
        self.assertTrue(report["pass"], report)
        self.assertEqual(report["causal_role_count"], 26)
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is unavailable")
        jsonschema.validate(self.contract, json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

    def test_decimal_soft_limit_is_warning_only(self) -> None:
        self.assertEqual(self.contract["budget"]["observer_evidence_soft_limit_bytes"], 100000000)
        budget = GATE.evaluate_soft_budget(100000001, 120000000)
        self.assertTrue(budget["soft_limit_exceeded"])
        self.assertIsNone(budget["hard_limit_bytes"])
        self.assertFalse(budget["coverage_reduced"])
        self.assertEqual(budget["formal_return_total_bytes"], 120000000)

    def test_dump_enabled_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["execution"]["sim_argv"][3] = "DUMP_FSDB=1"
        self.assert_contract_fails(item, "DUMP_FSDB=0 exactly once")

    def test_hidden_waveform_argv_control_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["execution"]["sim_argv"].append("-P=novas.tab")
        self.assert_contract_fails(item, "waveform writer/control token")

    def test_hard_limit_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["budget"]["observer_evidence_hard_limit_bytes"] = 100000000
        self.assert_contract_fails(item, "observer_evidence_hard_limit_bytes must be null")

    def test_post_sim_exemption_wrong_hash_and_path_fail(self) -> None:
        for key, value, fragment in (
            ("canonical_helper_sha256", "0" * 64, "canonical_helper_sha256"),
            ("member_path", "pkg/package_tools/renamed.py", "member_path"),
        ):
            item = copy.deepcopy(self.contract)
            item["post_sim_historical_compatibility_exemption"][key] = value
            self.assert_contract_fails(item, fragment)

    def test_renamed_post_sim_helper_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["package_members"]["post_sim_helper"] = "pkg/package_tools/renamed.py"
        item["post_sim_historical_compatibility_exemption"]["member_path"] = "pkg/package_tools/renamed.py"
        self.assert_contract_fails(item, "exact package-relative path")

    def test_sampling_and_truncation_fail(self) -> None:
        for key in ("sampling", "truncation"):
            item = copy.deepcopy(self.contract)
            item["event_recording"][key] = True
            self.assert_contract_fails(item, f"event_recording.{key} must be false")

    def test_derived_expected_signal_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["signals"][4]["derived_expected_equation"] = True
        self.assert_contract_fails(item, "derived expected equation")

    def test_observer_drive_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["signals"][4]["observer_drives_dut"] = True
        self.assert_contract_fails(item, "observer must not drive DUT")

    def test_missing_role_fails(self) -> None:
        item = copy.deepcopy(self.contract)
        item["role_coverage"] = [entry for entry in item["role_coverage"] if entry["role"] != "formal_d"]
        self.assert_contract_fails(item, "missing causal role coverage")

    def test_not_applicable_requires_machine_proof(self) -> None:
        item = copy.deepcopy(self.contract)
        item["role_coverage"][-1] = {"role": "formal_d", "disposition": "not_applicable", "signal_ids": []}
        self.assert_contract_fails(item, "not_applicable needs exact machine proof")

    def test_owner_clock_must_resolve(self) -> None:
        item = copy.deepcopy(self.contract)
        item["signals"][4]["owner_clock_signal_id"] = "missing"
        self.assert_contract_fails(item, "owner clock does not resolve")

    def test_candidate_pair_must_be_distinguishable(self) -> None:
        item = copy.deepcopy(self.contract)
        item["candidates"][1]["signature"] = copy.deepcopy(item["candidates"][0]["signature"])
        self.assert_contract_fails(item, "candidate pair is not distinguishable")

    def test_all_boundary_layers_required(self) -> None:
        item = copy.deepcopy(self.contract)
        item["boundary_observations"] = item["boundary_observations"][:-1]
        self.assert_contract_fails(item, "boundary layers must cover")

    def _package_zip(self, mutation: str | None = None) -> Path:
        target = self.root / f"package-{mutation or 'ok'}.zip"
        members = self.contract["package_members"]
        runner = "\n".join([
            "#!/usr/bin/env bash", "set -euo pipefail", "DUMP_VCD=0", "DUMP_FSDB=0",
            "TB_DUMP_FSDB=0", "python3 tools/server_observer_runtime_supervision.py supervise", "",
        ])
        exact_members: list[str] = []
        for value in self.contract["return_members"].values():
            exact_members.extend(value if isinstance(value, list) else [value])
        allow = {"exact": exact_members}
        contract_sha = hashlib.sha256(GATE.canonical_bytes(self.contract)).hexdigest()
        payloads: dict[str, bytes] = {
            members["runner"]: runner.encode(),
            members["manifest"]: encoded({
                "observer_only_profile": self.contract["profile"],
                "observer_only_contract_sha256": contract_sha,
            }),
            members["return_allowlist"]: encoded(allow),
            members["contract"]: GATE.canonical_bytes(self.contract),
            members["observer"]: b"module source_bound_observer; endmodule\n",
            members["parser"]: b"print('observer parser')\n",
            members["runtime_supervisor"]: b"print('process-tree supervision')\n",
            members["post_sim_helper"]: POST_SIM_HELPER.read_bytes(),
            members["post_sim_request"]: encoded({
                "schema": "server-post-sim-return-request-v1",
                "package_id": self.contract["package_id"],
                "result_root": "/home/panqs/ndp/simresult",
                "return_basename_template": "{package_id}_{execution_id}_return.zip",
                "core_entries": [
                    {"source_root": "attempt", "source": "run.log", "archive": "raw/run.log", "required": True}
                ],
                "plugins": [],
                "max_plugin_output_bytes": 4096,
                "claim_boundary": "synthetic post-sim observer-only fixture"
            }),
        }
        payloads[members["runner"]] = (
            runner
            + "python3 package_tools/server_post_sim_return.py finalize "
            + "--request contracts/server_post_sim_return_request.json\n"
        ).encode()
        if mutation == "waveform_member":
            payloads["pkg/forbidden.fsdb"] = b"bad"
        elif mutation == "pli_member":
            payloads["pkg/novas.tab"] = b"bad"
        elif mutation == "waveform_allowlist":
            payloads[members["return_allowlist"]] = encoded({"exact": ["forbidden.vpd"]})
        elif mutation == "writer":
            payloads[members["observer"]] = b"initial $fsdbDumpfile(\"bad\");\n"
        elif mutation == "missing_parser":
            del payloads[members["parser"]]
        elif mutation == "missing_chunk_prefix":
            allow["exact"] = [item for item in allow["exact"] if item != self.contract["return_members"]["chunk_prefix"]]
            payloads[members["return_allowlist"]] = encoded(allow)
        elif mutation == "waveform_discovery":
            request = json.loads(payloads[members["post_sim_request"]])
            request["waveform_discovery"] = {
                "plan_member": "contracts/server_waveform_mandatory_plan.json"
            }
            payloads[members["post_sim_request"]] = encoded(request)
        elif mutation == "unknown_helper_literal":
            payloads["pkg/package_tools/unknown.py"] = b"legacy = 'wave.vpd'\n"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, payload in payloads.items():
                zf.writestr(name, payload)
        return target

    def test_positive_final_zip(self) -> None:
        report = GATE.validate_final_zip(self._package_zip(), self.contract)
        self.assertTrue(report["pass"], report)

    def test_post_sim_waveform_discovery_fails(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("waveform_discovery"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("activates waveform_discovery" in item for item in report["errors"]))

    def test_unknown_helper_literal_is_not_exempt(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("unknown_helper_literal"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("unknown.py" in item and "waveform suffix" in item for item in report["errors"]))

    def test_final_zip_rejects_waveform_member(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("waveform_member"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("waveform members" in item for item in report["errors"]))

    def test_final_zip_rejects_waveform_pli_member(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("pli_member"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("waveform PLI" in item for item in report["errors"]))

    def test_final_zip_rejects_waveform_allowlist(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("waveform_allowlist"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("allowlist contains" in item for item in report["errors"]))

    def test_final_zip_rejects_writer(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("writer"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("writer/control" in item for item in report["errors"]))

    def test_final_zip_rejects_missing_required_member(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("missing_parser"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("package member missing" in item for item in report["errors"]))

    def test_final_zip_rejects_chunk_allowlist_omission(self) -> None:
        report = GATE.validate_final_zip(self._package_zip("missing_chunk_prefix"), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("chunk prefix" in item for item in report["errors"]))

    def _event_rows(self, signal_name: str | None = None) -> tuple[list[dict], dict[str, str]]:
        identity = {
            "package_id": self.contract["package_id"],
            "execution_id": "exec-1",
            "attempt_id": "attempt-1",
        }
        values = {
            "sig_clk": "0", "sig_reset": "1", "sig_stage": "0011", "sig_producer": "1",
            "sig_queue": "10XZ", "sig_flow": "1010", "sig_route": "00000001", "sig_output": "11110000",
        }
        widths = {item["signal_id"]: item["width_bits"] for item in self.contract["signals"]}
        rows: list[dict] = []
        for seq, sid in enumerate(values):
            rows.append({
                **identity, "record_type": "EVENT", "seq": seq, "sim_time": seq + 1,
                "timescale": "1ps", "signal_id": sid, "width_bits": widths[sid], "value_4state": values[sid],
            })
        rows.append({
            **identity, "record_type": "HEARTBEAT", "seq": len(rows), "sim_time": 100,
            "timescale": "1ps", "signal_id": "sig_clk", "width_bits": 1, "value_4state": "0",
        })
        if signal_name:
            rows.append({
                **identity, "record_type": "PARTIAL_EXIT", "seq": len(rows), "sim_time": 100,
                "timescale": "1ps", "signal_id": "sig_clk", "width_bits": 1, "value_4state": "0",
            })
        return rows, values

    def _return_zip(self, *, started: bool = True, signal_name: str | None = None, mutate=None) -> Path:
        identity = {"package_id": self.contract["package_id"], "execution_id": "exec-1", "attempt_id": "attempt-1"}
        rm = self.contract["return_members"]
        members: dict[str, bytes] = {
            rm["actual_argv"]: encoded({
                **identity,
                "compile_argv": self.contract["execution"]["compile_argv"],
                "sim_argv": self.contract["execution"]["sim_argv"],
            }),
            rm["sim_exit"]: encoded({**identity, "simulation_started": started, "signal": signal_name}),
        }
        if started:
            rows, end_state = self._event_rows(signal_name)
            chunk = b"".join(encoded(row) for row in rows)
            chunk_path = "observer/chunks/chunk-000000.jsonl"
            matrix_sha = hashlib.sha256(GATE.canonical_bytes({
                "boundary_observations": self.contract["boundary_observations"],
                "candidates": self.contract["candidates"],
            })).hexdigest()
            members.update({
                rm["process_tree"]: encoded({**identity, "process_tree_reaped": True, "owned_pids_remaining": []}),
                rm["sim_time_heartbeat"]: encoded({**identity, "simulation_time_progress_observed": True}),
                rm["signal_catalog"]: encoded({
                    **identity, "source_bound": True, "derived_expected_equation": False,
                    "signals": self.contract["signals"],
                }),
                chunk_path: chunk,
                rm["chunk_index"]: encoded({
                    **identity,
                    "byte_cap": None, "event_count_cap": None, "sampling": False, "truncated": False,
                    "candidate_ids": sorted(item["candidate_id"] for item in self.contract["candidates"]),
                    "candidate_boundary_matrix_sha256": matrix_sha,
                    "chunks": [{"path": chunk_path, "bytes": len(chunk), "sha256": hashlib.sha256(chunk).hexdigest(), "sampling": False, "truncated": False}],
                    "end_state": end_state,
                }),
                rm["decision"]: encoded({
                    **identity,
                    "candidate_ids_covered": sorted(item["candidate_id"] for item in self.contract["candidates"]),
                    "candidate_boundary_matrix_sha256": matrix_sha,
                    "diagnostic_evidence_complete": True,
                }),
            })
        else:
            members["COMPILE_CORE.json"] = encoded({"compile_started": True, "compile_passed": False})
            members["compile_first_error.txt"] = b"synthetic compile error\n"
        if mutate:
            mutate(members, identity)
        manifest_names = sorted(members)
        members[rm["return_manifest"]] = encoded({**identity, "members": manifest_names})
        target = self.root / f"return-{len(list(self.root.glob('return-*.zip')))}.zip"
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, payload in members.items():
                zf.writestr(name, payload)
        return target

    def test_positive_natural_return_preserves_xz(self) -> None:
        report = GATE.validate_return(self._return_zip(), self.contract)
        self.assertTrue(report["pass"], report)
        self.assertEqual(report["event_summary"]["last_values"]["sig_queue"], "10XZ")

    def test_positive_signal_returns(self) -> None:
        for signal_name in ("HUP", "INT", "TERM"):
            report = GATE.validate_return(self._return_zip(signal_name=signal_name), self.contract)
            self.assertTrue(report["pass"], (signal_name, report))

    def test_positive_timeout_and_nonzero_returns(self) -> None:
        rm = self.contract["return_members"]
        for field, value in (("timed_out", True), ("exit_code", 9)):
            def mutate(members, identity, field=field, value=value):
                item = json.loads(members[rm["sim_exit"]])
                item[field] = value
                members[rm["sim_exit"]] = encoded(item)
            report = GATE.validate_return(self._return_zip(signal_name="PARTIAL", mutate=mutate), self.contract)
            self.assertTrue(report["pass"], (field, report))

    def test_positive_compile_not_started_without_observer(self) -> None:
        report = GATE.validate_return(self._return_zip(started=False), self.contract)
        self.assertTrue(report["pass"], report)

    def test_missing_chunk_fails_closed(self) -> None:
        rm = self.contract["return_members"]
        def mutate(members, _identity):
            del members["observer/chunks/chunk-000000.jsonl"]
        report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
        self.assertFalse(report["pass"])
        self.assertEqual(report["diagnostic_status"], "DIAGNOSTIC_EVIDENCE_INCOMPLETE")

    def test_unindexed_extra_chunk_fails_closed(self) -> None:
        def mutate(members, _identity):
            members["observer/chunks/unindexed.jsonl"] = b""
        report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("exact returned chunk set" in item for item in report["errors"]))

    def test_identity_drift_fails_closed(self) -> None:
        rm = self.contract["return_members"]
        def mutate(members, _identity):
            item = json.loads(members[rm["decision"]])
            item["attempt_id"] = "other-attempt"
            members[rm["decision"]] = encoded(item)
        report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("decision receipt identity" in item for item in report["errors"]))

    def test_catalog_and_candidate_matrix_drift_fail_closed(self) -> None:
        rm = self.contract["return_members"]
        for case in ("catalog", "matrix"):
            def mutate(members, _identity, case=case):
                if case == "catalog":
                    item = json.loads(members[rm["signal_catalog"]])
                    item["signals"][4]["exact_hierarchy"] = "wrong.instance.net"
                    members[rm["signal_catalog"]] = encoded(item)
                else:
                    item = json.loads(members[rm["decision"]])
                    item["candidate_boundary_matrix_sha256"] = "0" * 64
                    members[rm["decision"]] = encoded(item)
            report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
            self.assertFalse(report["pass"], (case, report))

    def test_hard_cap_sampling_and_truncation_fail(self) -> None:
        rm = self.contract["return_members"]
        for key, value in (("byte_cap", 100000000), ("sampling", True), ("truncated", True)):
            def mutate(members, _identity, key=key, value=value):
                item = json.loads(members[rm["chunk_index"]])
                item[key] = value
                members[rm["chunk_index"]] = encoded(item)
            report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
            self.assertFalse(report["pass"], (key, report))

    def test_width_and_four_state_loss_fail(self) -> None:
        rm = self.contract["return_members"]
        for replacement in ("10X", "102Z"):
            def mutate(members, _identity, replacement=replacement):
                path = "observer/chunks/chunk-000000.jsonl"
                rows = [json.loads(line) for line in members[path].decode().splitlines()]
                rows[4]["value_4state"] = replacement
                raw = b"".join(encoded(row) for row in rows)
                members[path] = raw
                index = json.loads(members[rm["chunk_index"]])
                index["chunks"][0].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                members[rm["chunk_index"]] = encoded(index)
            report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
            self.assertFalse(report["pass"], (replacement, report))

    def test_sequence_time_and_end_state_loss_fail(self) -> None:
        rm = self.contract["return_members"]
        for case in ("seq", "time", "end"):
            def mutate(members, _identity, case=case):
                path = "observer/chunks/chunk-000000.jsonl"
                if case == "end":
                    index = json.loads(members[rm["chunk_index"]])
                    del index["end_state"]["sig_output"]
                    members[rm["chunk_index"]] = encoded(index)
                    return
                rows = [json.loads(line) for line in members[path].decode().splitlines()]
                if case == "seq":
                    rows[3]["seq"] += 1
                else:
                    rows[3]["sim_time"] = 0
                raw = b"".join(encoded(row) for row in rows)
                members[path] = raw
                index = json.loads(members[rm["chunk_index"]])
                index["chunks"][0].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                members[rm["chunk_index"]] = encoded(index)
            report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
            self.assertFalse(report["pass"], (case, report))

    def test_signal_exit_without_partial_record_fails(self) -> None:
        report = GATE.validate_return(self._return_zip(signal_name=None, mutate=lambda members, identity: members.__setitem__(
            self.contract["return_members"]["sim_exit"], encoded({**identity, "simulation_started": True, "signal": "INT"})
        )), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("partial-exit" in item for item in report["errors"]))

    def test_waveform_return_member_fails(self) -> None:
        def mutate(members, _identity):
            members["forbidden.vcd"] = b"bad"
        report = GATE.validate_return(self._return_zip(mutate=mutate), self.contract)
        self.assertFalse(report["pass"])
        self.assertTrue(any("forbidden waveform" in item for item in report["errors"]))


if __name__ == "__main__":
    unittest.main()
