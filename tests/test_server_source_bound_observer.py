from __future__ import annotations

import copy
import json
import py_compile
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import jsonschema

from tools.generate_server_source_bound_observer import (
    _boundary_symbols,
    build_catalog,
    materialize,
    pretty_json_bytes,
    semantic_sha256,
    diagnostic_semantics_sha256,
    generate_observer,
    generate_parser,
    run_diagnostic_semantic_controls,
    validate_contract,
    validate_final_zip,
)


RTL_SOURCE = Path("fixtures/server_source_bound_observer_v1/rtl/demo_pipeline.sv")
CATALOG_SCHEMA = Path("schemas/server_source_bound_probe_catalog_v1.schema.json")
PLAN_SCHEMA = Path("schemas/server_source_bound_probe_plan_v1.schema.json")
PLAN_V2_SCHEMA = Path("schemas/server_source_bound_probe_plan_v2.schema.json")
REPORT_SCHEMA = Path(
    "schemas/server_source_bound_observer_generation_report_v1.schema.json"
)
FINAL_ZIP_CONTRACT_SCHEMA = Path(
    "schemas/server_source_bound_final_zip_contract_v1.schema.json"
)
FINAL_ZIP_REPORT_SCHEMA = Path(
    "schemas/server_source_bound_final_zip_validation_v1.schema.json"
)
GENERATION_V2_SCHEMA = Path(
    "schemas/server_source_bound_observer_generation_report_v2.schema.json"
)
FINAL_ZIP_REPORT_V2_SCHEMA = Path(
    "schemas/server_source_bound_final_zip_validation_v2.schema.json"
)
DECISION_V2_SCHEMA = Path(
    "schemas/server_source_bound_probe_decision_v2.schema.json"
)
REGISTRY = Path(
    "contracts/server_source_bound_observer_mechanism_registry_v1.json"
)
DISPATCH = Path(
    "contracts/server_source_bound_observer_next_fresh_dispatch_v1.json"
)
BUILD_GATE_REGISTRY = Path(
    "contracts/server_package_build_gate_registry_v1.json"
)


class SourceBoundObserverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.catalog = build_catalog(
            RTL_SOURCE.parent,
            [RTL_SOURCE],
            "a" * 64,
        )
        self.by_name = {
            (item["module"], item["name"]): item["symbol_id"]
            for item in self.catalog["symbols"]
        }
        self.catalog_path = self.root / "catalog.json"
        self.catalog_path.write_text(
            json.dumps(self.catalog, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_catalog_resolves_literal_include_macros_and_clog2_widths(self) -> None:
        header = self.root / "widths.svh"
        source = self.root / "macro_stage.sv"
        header.write_text(
            "`define BUFFER_BANK_NUM 8\n"
            "`define BUFFER_DEPTH `BUFFER_BANK_NUM\n"
            "`define BUFFER_BANK_ADDR_WIDTH $clog2(`BUFFER_DEPTH)\n",
            encoding="utf-8",
        )
        source.write_text(
            "module macro_stage(\n"
            "  input [`BUFFER_BANK_NUM-1:0] mask,\n"
            "  input [`BUFFER_BANK_ADDR_WIDTH-1:0] addr\n"
            "); endmodule\n",
            encoding="utf-8",
        )
        catalog = build_catalog(self.root, [header, source], "b" * 64)
        self.assertTrue(catalog["valid"], catalog["errors"])
        by_name = {
            (item["module"], item["name"]): item for item in catalog["symbols"]
        }
        self.assertEqual(by_name[("macro_stage", "mask")]["width_bits"], 8)
        self.assertEqual(by_name[("macro_stage", "addr")]["width_bits"], 3)
        self.assertEqual(
            [item["path"] for item in catalog["rtl_identity"]["sources"]],
            ["macro_stage.sv", "widths.svh"],
        )

    def sid(self, name: str, module: str = "demo_stage") -> str:
        return self.by_name[(module, name)]

    def predicate(self, *signals: str) -> dict:
        args = [{"op": "SIGNAL", "symbol_id": self.sid(name)} for name in signals]
        return args[0] if len(args) == 1 else {"op": "AND", "args": args}

    def boundary(self, boundary_id: str, role: str, valid: str, ready: str) -> dict:
        return {
            "boundary_id": boundary_id,
            "role": role,
            "target_module": "demo_stage",
            "clock_symbol_id": self.sid("clk_db"),
            "reset": {"symbol_id": self.sid("rst_n"), "active_low": True},
            "stage_gate": self.predicate("stage_active"),
            "classes": [
                {
                    "class_id": "QUALIFIED",
                    "bit": 0,
                    "progress": True,
                    "trigger": False,
                    "predicate": self.predicate(valid, ready),
                },
                {
                    "class_id": "VISIBLE_STATE",
                    "bit": 1,
                    "progress": False,
                    "trigger": True,
                    "predicate": self.predicate(valid),
                },
            ],
            "payload_symbol_ids": [self.sid("payload")],
        }

    def plan(self) -> dict:
        boundaries = [
            self.boundary("source_accept", "source_produce", "src_valid", "src_ready"),
            self.boundary("consumer_accept", "consumer_accept", "dst_valid", "dst_ready"),
        ]
        role_coverage = []
        for role in sorted(
            {
                "source_produce",
                "queue_enqueue",
                "queue_dequeue",
                "consumer_accept",
                "internal_match_compute",
                "output_accept",
                "terminal_propagation",
                "formal_d_collection",
            }
        ):
            matches = [item["boundary_id"] for item in boundaries if item["role"] == role]
            role_coverage.append(
                {
                    "role": role,
                    "disposition": "covered" if matches else "not_applicable",
                    "boundary_ids": matches,
                    "reason": "bound in synthetic cone" if matches else "outside synthetic cone",
                }
            )
        observations = [
            {
                "observation_id": "source_progress",
                "boundary_id": "source_accept",
                "metric": "count_nonzero",
            },
            {
                "observation_id": "consumer_progress",
                "boundary_id": "consumer_accept",
                "metric": "count_nonzero",
            },
            {
                "observation_id": "source_visible",
                "boundary_id": "source_accept",
                "metric": "class_seen",
                "class_id": "VISIBLE_STATE",
            },
        ]
        return {
            "schema": "server-source-bound-probe-plan-v1",
            "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
            "profile": "HIGH_INFORMATION_CAUSAL_V1",
            "package_id": "synthetic_next_fresh_diag",
            "family": "synthetic",
            "catalog_identity": {
                "rtl_tree_sha256": "a" * 64,
                "catalog_semantic_sha256": semantic_sha256(self.catalog),
            },
            "boundaries": boundaries,
            "role_coverage": role_coverage,
            "decision_observations": observations,
            "candidates": [
                {
                    "candidate_id": "target_not_reached",
                    "root_cause_class": "TARGET_STAGE_NOT_REACHED",
                    "signature": {
                        "source_progress": False,
                        "consumer_progress": False,
                        "source_visible": False,
                    },
                },
                {
                    "candidate_id": "consumer_stall",
                    "root_cause_class": "DYNAMIC_FLOW_CONTROL_STALL",
                    "signature": {
                        "source_progress": True,
                        "consumer_progress": False,
                        "source_visible": True,
                    },
                },
                {
                    "candidate_id": "natural_candidate",
                    "root_cause_class": "CAUSAL_BOUNDARIES_PROGRESS",
                    "signature": {
                        "source_progress": True,
                        "consumer_progress": True,
                        "source_visible": True,
                    },
                },
            ],
            "runtime_budget": {
                "qualified_ring_depth": 128,
                "non_progress_ring_depth": 64,
                "first_payload_samples": 4,
                "post_trigger_samples": 64,
                "no_progress_cycles": 1024,
                "max_log_bytes": 16777216,
                "state_activity_consumes_qualified_budget": False,
                "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES",
                "text_io_policy": "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY",
                "slowdown_limit_hard": False,
            },
            "claim_boundary": "Synthetic generated-observer contract only.",
        }

    def write_plan(self, plan: dict) -> Path:
        path = self.root / "plan.json"
        path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def plan_v2(self) -> dict:
        plan = self.plan()
        plan["schema"] = "server-source-bound-probe-plan-v2"
        plan["diagnostic_semantics"] = {
            "instance_match": "EXACT_CANONICAL_EQUALITY",
            "record_grouping_key": ["boundary_id", "canonical_instance", "seq"],
            "unknown_payload": "EVIDENCE_INCOMPLETE",
            "numeric_parse_failure": "EVIDENCE_INCOMPLETE",
            "candidate_match_cardinality": "EXACTLY_ONE",
        }
        for boundary in plan["boundaries"]:
            expected = f"tb.dut.{boundary['boundary_id']}"
            boundary["instance_scope"] = {
                "mode": "EXACT_CANONICAL_INSTANCE",
                "expected_instances": [expected],
                "near_miss_instances": [expected + "_near"],
                "identity_provenance": {
                    "path": "diagnostics/elaboration_identity.json",
                    "sha256": "b" * 64,
                    "selector": f"boundary={boundary['boundary_id']}",
                },
            }
            width = sum(
                next(
                    item["width_bits"]
                    for item in self.catalog["symbols"]
                    if item["symbol_id"] == symbol_id
                )
                for symbol_id in boundary["payload_symbol_ids"]
            )
            boundary["payload_contract"] = {
                "width_bits": width,
                "required_binary_known": True,
                "unknown_disposition": "EVIDENCE_INCOMPLETE",
            }
        return plan

    def build_final_zip(
        self,
        *,
        strict: bool = False,
        observer_mutation: bytes = b"",
        parser_mutation: bytes = b"",
        omit_runner_token: str | None = None,
    ) -> Path:
        plan_path = self.write_plan(self.plan_v2() if strict else self.plan())
        output = self.root / "generated_zip"
        generation = materialize(self.catalog_path, plan_path, output)
        self.assertTrue(generation["pass"], generation["errors"])
        contract = {
            "schema": "server-source-bound-final-zip-contract-v1",
            "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
            "enforcement": "required_next_fresh",
            "members": {
                "catalog": "diagnostics/catalog.json",
                "plan": "diagnostics/plan.json",
                "observer": "tb_probe/source_bound_causal_observer.svh",
                "parser": "package_tools/source_bound_causal_parser.py",
                "binding": "diagnostics/source_bound_probe_binding.json",
                "generation_report": "diagnostics/generation_report.json",
                "runner": "PREPARE_AND_RUN.sh",
            },
            "compile_observer_token": "source_bound_causal_observer.svh",
            "runtime_plusarg": "+CODEX_CAUSAL_OBSERVER",
            "return_log_token": "source_bound_causal.log",
            "return_decision_token": "source_bound_causal_decision.json",
            "claim_boundary": "Synthetic final ZIP binding fixture only.",
        }
        jsonschema.validate(
            contract,
            json.loads(FINAL_ZIP_CONTRACT_SCHEMA.read_text(encoding="utf-8")),
        )
        runner_tokens = [
            "source_bound_causal_observer.svh",
            "+CODEX_CAUSAL_OBSERVER",
            "source_bound_causal.log",
            "source_bound_causal_decision.json",
        ]
        if omit_runner_token:
            runner_tokens.remove(omit_runner_token)
        runner = "#!/usr/bin/env bash\n# " + " ".join(runner_tokens) + "\n"
        members = {
            "pkg/diagnostics/source_bound_final_zip_contract.json": pretty_json_bytes(contract),
            "pkg/diagnostics/catalog.json": self.catalog_path.read_bytes(),
            "pkg/diagnostics/plan.json": plan_path.read_bytes(),
            "pkg/tb_probe/source_bound_causal_observer.svh": (
                output / "source_bound_causal_observer.svh"
            ).read_bytes()
            + observer_mutation,
            "pkg/package_tools/source_bound_causal_parser.py": (
                output / "source_bound_causal_parser.py"
            ).read_bytes()
            + parser_mutation,
            "pkg/diagnostics/source_bound_probe_binding.json": (
                output / "source_bound_probe_binding.json"
            ).read_bytes(),
            "pkg/diagnostics/generation_report.json": pretty_json_bytes(generation),
            "pkg/PREPARE_AND_RUN.sh": runner.encode("utf-8"),
        }
        path = self.root / (
            "negative.zip"
            if observer_mutation or parser_mutation or omit_runner_token
            else "positive.zip"
        )
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        return path

    def test_catalog_and_plan_schemas(self) -> None:
        self.assertTrue(self.catalog["valid"], self.catalog["errors"])
        jsonschema.validate(
            self.catalog,
            json.loads(CATALOG_SCHEMA.read_text(encoding="utf-8")),
        )
        jsonschema.validate(
            self.plan(),
            json.loads(PLAN_SCHEMA.read_text(encoding="utf-8")),
        )
        jsonschema.validate(
            self.plan_v2(),
            json.loads(PLAN_V2_SCHEMA.read_text(encoding="utf-8")),
        )

    def test_v2_materializes_exact_semantic_fingerprint(self) -> None:
        plan = self.plan_v2()
        report = materialize(
            self.catalog_path, self.write_plan(plan), self.root / "generated_v2"
        )
        self.assertTrue(report["pass"], report["errors"])
        self.assertEqual(
            report["diagnostic_semantics_sha256"],
            diagnostic_semantics_sha256(self.catalog, plan),
        )
        jsonschema.validate(
            report,
            json.loads(GENERATION_V2_SCHEMA.read_text(encoding="utf-8")),
        )

    def test_v2_final_zip_executes_v80_and_p34b_regressions(self) -> None:
        report = validate_final_zip(self.build_final_zip(strict=True))
        self.assertTrue(report["pass"], report["errors"])
        controls = report["semantic_controls"]
        self.assertTrue(controls["pass"], controls["errors"])
        by_id = {item["case_id"]: item for item in controls["cases"]}
        for case_id in (
            "v80_near_miss_instance_only",
            "v80_mixed_target_near_miss",
            "p34b_payload_x",
            "p34b_payload_z",
            "payload_known_zero",
            "payload_width_wrong",
            "payload_missing",
            "duplicate_boundary_instance_seq",
        ):
            self.assertTrue(by_id[case_id]["pass"], by_id[case_id])
            self.assertEqual(by_id[case_id]["decision"], "EVIDENCE_INCOMPLETE")
            jsonschema.validate(
                by_id[case_id]["decision_report"],
                json.loads(DECISION_V2_SCHEMA.read_text(encoding="utf-8")),
            )
        jsonschema.validate(
            report,
            json.loads(FINAL_ZIP_REPORT_V2_SCHEMA.read_text(encoding="utf-8")),
        )

    def test_v2_wrong_instance_mutates_the_payload_bearing_later_boundary(self) -> None:
        plan = self.plan_v2()
        plan["decision_observations"] = [
            {
                "observation_id": "consumer_progress",
                "boundary_id": "consumer_accept",
                "metric": "count_nonzero",
            }
        ]
        plan["candidates"] = [
            {
                "candidate_id": "consumer_absent",
                "root_cause_class": "CONSUMER_NOT_REACHED",
                "signature": {"consumer_progress": False},
            },
            {
                "candidate_id": "consumer_present",
                "root_cause_class": "CONSUMER_REACHED",
                "signature": {"consumer_progress": True},
            },
        ]
        contract = validate_contract(self.catalog, plan)
        self.assertTrue(contract["valid"], contract["errors"])
        controls = run_diagnostic_semantic_controls(
            self.catalog,
            plan,
            generate_parser(plan).encode("utf-8"),
        )
        self.assertTrue(controls["pass"], controls["errors"])
        by_id = {item["case_id"]: item for item in controls["cases"]}
        self.assertTrue(by_id["v80_mixed_target_near_miss"]["pass"])
        self.assertEqual(
            by_id["v80_mixed_target_near_miss"]["decision"],
            "EVIDENCE_INCOMPLETE",
        )

    def test_v2_rejects_unpinned_decision_scope_and_payload_width_drift(self) -> None:
        plan = self.plan_v2()
        plan["boundaries"][0]["instance_scope"]["mode"] = "ALL_INSTANCES_KEYED"
        plan["boundaries"][0]["payload_contract"]["width_bits"] += 1
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        self.assertTrue(any("pinned exact instance" in item for item in report["errors"]))
        self.assertTrue(any("width_bits must equal" in item for item in report["errors"]))

    def test_materializes_one_source_bound_generation(self) -> None:
        plan_path = self.write_plan(self.plan())
        output = self.root / "generated"
        report = materialize(self.catalog_path, plan_path, output)
        self.assertTrue(report["pass"], report["errors"])
        jsonschema.validate(
            report,
            json.loads(REPORT_SCHEMA.read_text(encoding="utf-8")),
        )
        observer = (output / "source_bound_causal_observer.svh").read_text(encoding="utf-8")
        self.assertIn("bind demo_stage", observer)
        self.assertIn("BITMAP", "multiclass BITMAP")
        self.assertIn("codex_q_time", observer)
        self.assertIn("codex_s_time", observer)
        self.assertIn("codex_sticky_mask | class_mask_now", observer)
        self.assertNotIn("u_top.", observer)
        binding = json.loads((output / "source_bound_probe_binding.json").read_text(encoding="utf-8"))
        self.assertFalse(binding["free_form_hdl_identifiers_accepted"])
        self.assertFalse(binding["private_hierarchical_xmr_generated"])
        self.assertTrue(report["focused_syntax"]["pass"], report["focused_syntax"])
        py_compile.compile(str(output / "source_bound_causal_parser.py"), doraise=True)

    def test_generated_parser_uniquely_adjudicates_and_preserves_multiclass(self) -> None:
        plan_path = self.write_plan(self.plan())
        output = self.root / "generated"
        report = materialize(self.catalog_path, plan_path, output)
        self.assertTrue(report["pass"])
        log = self.root / "observer.log"
        log.write_text(
            "\n".join(
                [
                    "CODEX_PROBE_V1 kind=ENABLED boundary=source_accept instance=tb.dut.probe",
                    "CODEX_PROBE_V1 kind=ENABLED boundary=consumer_accept instance=tb.dut.probe",
                    "CODEX_PROBE_V1 kind=EVENT boundary=source_accept instance=tb.dut.probe time=10 mask=3 payload=1234 seq=0",
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=source_accept instance=tb.dut.probe count=1 state=1 first=10 last=10 maxgap=0 sticky=3 xor=1234",
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=consumer_accept instance=tb.dut.probe count=1 state=0 first=12 last=12 maxgap=0 sticky=1 xor=1234",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        decision_path = self.root / "decision.json"
        result = subprocess.run(
            [
                sys.executable,
                str(output / "source_bound_causal_parser.py"),
                "--log",
                str(log),
                "--output",
                str(decision_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        self.assertEqual(decision["decision"], "CAUSAL_BOUNDARIES_PROGRESS")
        self.assertTrue(decision["observations"]["source_visible"])
        self.assertEqual(decision["matching_candidate_ids"], ["natural_candidate"])

    def test_generated_parser_adjudicates_from_live_events_without_final_block(self) -> None:
        plan_path = self.write_plan(self.plan())
        output = self.root / "generated_live_only"
        self.assertTrue(materialize(self.catalog_path, plan_path, output)["pass"])
        log = self.root / "live_only.log"
        log.write_text(
            "\n".join(
                [
                    "CODEX_PROBE_V1 kind=ENABLED boundary=source_accept instance=tb.dut.source.probe",
                    "CODEX_PROBE_V1 kind=ENABLED boundary=consumer_accept instance=tb.dut.consumer.probe",
                    "CODEX_PROBE_V1 kind=EVENT boundary=source_accept instance=tb.dut.source.probe time=10 mask=3 payload=1234 seq=0",
                    "CODEX_PROBE_V1 kind=EVENT boundary=consumer_accept instance=tb.dut.consumer.probe time=12 mask=1 payload=1234 seq=0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        decision_path = self.root / "live_only_decision.json"
        result = subprocess.run(
            [
                sys.executable,
                str(output / "source_bound_causal_parser.py"),
                "--log",
                str(log),
                "--output",
                str(decision_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        self.assertEqual(decision["decision"], "CAUSAL_BOUNDARIES_PROGRESS")
        self.assertEqual(
            decision["live_event_count"],
            {"consumer_accept": 1, "source_accept": 1},
        )
        self.assertEqual(decision["missing_required_summaries"], [])

    def test_rejects_zero_live_payload_samples(self) -> None:
        plan = self.plan()
        plan["runtime_budget"]["first_payload_samples"] = 0
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        self.assertTrue(
            any("first_payload_samples" in item for item in report["errors"]),
            report,
        )

    def test_aggregates_multiple_unresolved_symbols(self) -> None:
        plan = self.plan()
        plan["boundaries"][0]["clock_symbol_id"] = "sym_" + "1" * 24
        plan["boundaries"][0]["reset"]["symbol_id"] = "sym_" + "2" * 24
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        unresolved = [item for item in report["errors"] if "unresolved symbol_id" in item]
        self.assertEqual(len(unresolved), 2)

    def test_rejects_cross_module_symbol(self) -> None:
        plan = self.plan()
        plan["boundaries"][0]["classes"][0]["predicate"] = {
            "op": "SIGNAL",
            "symbol_id": self.sid("foreign_signal", "unrelated_stage"),
        }
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        self.assertTrue(any("belongs to unrelated_stage" in item for item in report["errors"]))

    def test_vector_handshake_uses_bitwise_overlap_not_scalar_equality(self) -> None:
        plan = self.plan()
        boundary = plan["boundaries"][0]
        valid_id = self.sid("payload")
        ready_id = self.sid("payload")
        boundary["classes"][0]["predicate"] = {
            "op": "BIT_AND_NONZERO",
            "symbol_ids": [valid_id, ready_id],
        }
        boundary["payload_symbol_ids"] = [valid_id]
        report = validate_contract(self.catalog, plan)
        self.assertTrue(report["valid"], report["errors"])
        observer = generate_observer(self.catalog, plan)
        alias = next(
            f"p_{index}"
            for index, symbol_id in enumerate(_boundary_symbols(boundary))
            if symbol_id == valid_id
        )
        self.assertIn(f"((|({alias} & {alias})) === 1'b1)", observer)
        self.assertNotIn(f"({alias} === 1'b1) && ({alias} === 1'b1)", observer)

    def test_vector_handshake_rejects_invalid_arity(self) -> None:
        plan = self.plan()
        plan["boundaries"][0]["classes"][0]["predicate"] = {
            "op": "BIT_AND_NONZERO",
            "symbol_ids": [self.sid("payload")],
        }
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        self.assertTrue(any("BIT_AND_NONZERO" in item for item in report["errors"]))

    def test_rejects_duplicate_candidate_signatures(self) -> None:
        plan = self.plan()
        plan["candidates"][1]["signature"] = copy.deepcopy(plan["candidates"][0]["signature"])
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        self.assertTrue(report["indistinguishable_candidate_pairs"])

    def test_rejects_budget_and_multiclass_regressions_together(self) -> None:
        plan = self.plan()
        plan["runtime_budget"]["state_activity_consumes_qualified_budget"] = True
        plan["runtime_budget"]["multiclass_encoding"] = "PRIORITY_SINGLE_LABEL"
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        self.assertTrue(any("state activity" in item for item in report["errors"]))
        self.assertTrue(any("multiclass encoding" in item for item in report["errors"]))

    def test_rejects_catalog_identity_drift(self) -> None:
        plan = self.plan()
        plan["catalog_identity"]["rtl_tree_sha256"] = "b" * 64
        plan["catalog_identity"]["catalog_semantic_sha256"] = "c" * 64
        report = validate_contract(self.catalog, plan)
        self.assertFalse(report["valid"])
        self.assertIn("plan/catalog RTL tree SHA mismatch", report["errors"])
        self.assertIn("plan/catalog semantic SHA mismatch", report["errors"])

    def test_exact_parser_fails_closed_on_malformed_record(self) -> None:
        plan_path = self.write_plan(self.plan())
        output = self.root / "generated"
        self.assertTrue(materialize(self.catalog_path, plan_path, output)["pass"])
        log = self.root / "bad.log"
        log.write_text(
            "CODEX_PROBE_V1 kind=ENABLED boundary=source_accept instance=tb probe\n",
            encoding="utf-8",
        )
        decision_path = self.root / "bad_decision.json"
        result = subprocess.run(
            [sys.executable, str(output / "source_bound_causal_parser.py"), "--log", str(log), "--output", str(decision_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        self.assertEqual(decision["decision"], "EVIDENCE_INCOMPLETE")

    def test_historical_mechanism_registry_covers_known_escapes(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        text = json.dumps(registry, ensure_ascii=False)
        for token in (
            "QLinearAdd v19",
            "serialized Conv v23",
            "GAP v36",
            "serialized Conv v41",
            "native Conv p5",
            "node0071-to-node0075 v3",
            "GAP v50",
            "GAP v53",
            "GAP v54",
            "native Conv p33b",
            "serialized Conv v80",
            "native Conv p34b",
            "EXACT_CANONICAL_INSTANCE_AND_GROUPING",
            "BINARY_KNOWN_PAYLOAD_FAIL_CLOSED",
            "SEMANTIC_FINGERPRINT_FIRST_USE",
        ):
            self.assertIn(token, text)

    def test_next_fresh_dispatch_requires_v2_and_current_gate_epoch(self) -> None:
        dispatch = json.loads(DISPATCH.read_text(encoding="utf-8"))
        self.assertEqual(dispatch["version"], 2)
        text = json.dumps(dispatch, ensure_ascii=False)
        self.assertIn("server-source-bound-probe-plan-v2", text)
        self.assertIn("server-source-bound-final-zip-validation-v2", text)
        self.assertIn("diagnostic_semantics_sha256", text)
        registry = json.loads(BUILD_GATE_REGISTRY.read_text(encoding="utf-8"))
        versions = {
            item["gate_id"]: item["semantic_version"]
            for item in registry["gates"]
        }
        for gate_id in (
            "source_bound_observer_generation",
            "diagnostic_semantics",
            "source_bound_final_zip",
        ):
            self.assertEqual(versions[gate_id], "2")
        self.assertEqual(versions["first_fresh_extra_audit"], "6")

    def test_exact_final_zip_regenerates_all_generated_bytes(self) -> None:
        report = validate_final_zip(self.build_final_zip())
        self.assertTrue(report["pass"], report["errors"])
        jsonschema.validate(
            report,
            json.loads(FINAL_ZIP_REPORT_SCHEMA.read_text(encoding="utf-8")),
        )
        self.assertTrue(report["exact_generation"]["observer"]["byte_equal"])
        self.assertTrue(report["exact_generation"]["parser"]["byte_equal"])
        self.assertTrue(report["exact_generation"]["binding"]["byte_equal"])
        self.assertTrue(all(report["runner_checks"].values()))

    def test_exact_final_zip_rejects_post_generation_observer_and_parser_edits(self) -> None:
        observer = validate_final_zip(
            self.build_final_zip(observer_mutation=b"// hand edit\n")
        )
        parser = validate_final_zip(
            self.build_final_zip(parser_mutation=b"# hand edit\n")
        )
        self.assertFalse(observer["pass"])
        self.assertFalse(parser["pass"])
        self.assertTrue(any("observer differs" in item for item in observer["errors"]))
        self.assertTrue(any("parser differs" in item for item in parser["errors"]))

    def test_exact_final_zip_rejects_missing_runtime_or_return_tokens(self) -> None:
        for token in (
            "+CODEX_CAUSAL_OBSERVER",
            "source_bound_causal.log",
            "source_bound_causal_decision.json",
            "source_bound_causal_observer.svh",
        ):
            report = validate_final_zip(self.build_final_zip(omit_runner_token=token))
            self.assertFalse(report["pass"], token)
            self.assertTrue(any(token in item for item in report["errors"]), token)


if __name__ == "__main__":
    unittest.main()
