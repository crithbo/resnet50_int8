#!/usr/bin/env python3
"""Add the current generated source-bound final-ZIP conjunction to v98."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v98b_lcdup_tuple10"
OUT = ROOT / "outputs/conv_node0004_v98b_lcdup_tuple10_release1"
TREE = OUT / "build" / PACKAGE
DIAG = TREE / "diagnostics"
CATALOG = DIAG / "source_bound_probe_catalog.json"
PLAN = DIAG / "source_bound_probe_plan.json"
IDENTITY = DIAG / "source_bound_exact_instance_identity.json"
GEN_REPORT = DIAG / "source_bound_observer_generation_report.json"
MEM_SOURCE = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv"
INSTANCE = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.codex_probe_mem_tuple_accept_inst"
NEAR = INSTANCE.replace("slice_with_datahub_mc_group_gen[13]", "slice_with_datahub_mc_group_gen[12]", 1)


def load_generator():
    source = ROOT / "tools/generate_server_source_bound_observer.py"
    spec = importlib.util.spec_from_file_location("source_bound_generator", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{label} anchor count={text.count(old)}")
    return text.replace(old, new, 1)


def main() -> int:
    generator = load_generator()
    catalog = generator.build_catalog(
        ROOT / "NDP_copy01/rtl",
        [MEM_SOURCE],
        sha(MEM_SOURCE),
    )
    if not catalog.get("valid"):
        raise RuntimeError(f"catalog failed: {catalog.get('errors')}")
    write(CATALOG, catalog)
    symbols = {item["name"]: item["symbol_id"] for item in catalog["symbols"]}
    required = {
        "clk", "rst_n", "mse_enable", "mem_all_idx_matched",
        "mem_ag_idx_queue_wr_en", "mse_mem_ag_tag_valid",
        "mem_ag_idx_queue_rd_en", "mem_ag_idx_queue_empty",
    }
    if not required.issubset(symbols):
        raise RuntimeError(f"catalog missing symbols: {sorted(required - set(symbols))}")
    identity = {
        "schema": "node0004-v98b-source-bound-exact-instance-v1",
        "package_id": PACKAGE,
        "boundaries": {"mem_tuple_accept": {"expected_instances": [INSTANCE], "near_miss_instances": [NEAR]}},
        "claim_boundary": "Exact instance identity for package-local generated observer parsing only.",
    }
    write(IDENTITY, identity)
    boundary = {
        "boundary_id": "mem_tuple_accept",
        "target_module": "Memory_AG_Idx_Queue",
        "role": "consumer_accept",
        "clock_symbol_id": symbols["clk"],
        "reset": {"symbol_id": symbols["rst_n"], "active_low": True},
        "stage_gate": {"op": "SIGNAL", "symbol_id": symbols["mse_enable"]},
        "classes": [
            {"bit": 0, "class_id": "mem_tuple_matched", "predicate": {"op": "SIGNAL", "symbol_id": symbols["mem_all_idx_matched"]}, "progress": False, "trigger": False},
            {"bit": 1, "class_id": "mem_tuple_enqueue", "predicate": {"op": "SIGNAL", "symbol_id": symbols["mem_ag_idx_queue_wr_en"]}, "progress": True, "trigger": False},
            {"bit": 2, "class_id": "mem_tuple_tag_visible", "predicate": {"op": "SIGNAL", "symbol_id": symbols["mse_mem_ag_tag_valid"]}, "progress": True, "trigger": False},
            {"bit": 3, "class_id": "mem_tuple_queue_empty", "predicate": {"op": "SIGNAL", "symbol_id": symbols["mem_ag_idx_queue_empty"]}, "progress": False, "trigger": True},
        ],
        "payload_symbol_ids": [
            symbols["mem_all_idx_matched"], symbols["mem_ag_idx_queue_wr_en"],
            symbols["mse_mem_ag_tag_valid"], symbols["mem_ag_idx_queue_rd_en"],
            symbols["mem_ag_idx_queue_empty"],
        ],
        "payload_contract": {"width_bits": 5, "required_binary_known": True, "unknown_disposition": "EVIDENCE_INCOMPLETE"},
        "instance_scope": {
            "mode": "EXACT_CANONICAL_INSTANCE",
            "expected_instances": [INSTANCE],
            "near_miss_instances": [NEAR],
            "identity_provenance": {"path": "diagnostics/source_bound_exact_instance_identity.json", "sha256": sha(IDENTITY), "selector": "boundaries.mem_tuple_accept"},
        },
    }
    observations = [
        {"observation_id": "mem_event_nonzero", "boundary_id": "mem_tuple_accept", "metric": "count_nonzero"},
        {"observation_id": "mem_enqueue_seen", "boundary_id": "mem_tuple_accept", "metric": "class_seen", "class_id": "mem_tuple_enqueue"},
        {"observation_id": "mem_tag_seen", "boundary_id": "mem_tuple_accept", "metric": "class_seen", "class_id": "mem_tuple_tag_visible"},
    ]
    candidates = [
        ("compat_success", "MEMORY_TUPLE_ACTIVITY_PRESENT", [True, True, True]),
        ("compat_no_activity", "MEMORY_TUPLE_ACTIVITY_ABSENT", [False, False, False]),
        ("compat_event_no_enqueue", "MEMORY_EVENT_WITHOUT_ENQUEUE", [True, False, False]),
        ("compat_enqueue_no_tag", "MEMORY_ENQUEUE_WITHOUT_TAG", [True, True, False]),
        ("compat_tag_no_enqueue", "MEMORY_TAG_WITHOUT_ENQUEUE", [True, False, True]),
    ]
    obs_ids = [item["observation_id"] for item in observations]
    roles = [
        "source_produce", "queue_enqueue", "queue_dequeue", "consumer_accept",
        "internal_match_compute", "output_accept", "terminal_propagation", "formal_d_collection",
    ]
    plan = {
        "schema": "server-source-bound-probe-plan-v2",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "package_id": PACKAGE,
        "family": "conv_serialized_node0004",
        "profile": "HIGH_INFORMATION_CAUSAL_V1",
        "catalog_identity": {"rtl_tree_sha256": catalog["rtl_identity"]["rtl_tree_sha256"], "catalog_semantic_sha256": generator.semantic_sha256(catalog)},
        "boundaries": [boundary],
        "role_coverage": [
            {"role": role, "disposition": "covered", "boundary_ids": ["mem_tuple_accept"], "reason": "Exact Memory_AG tuple accept boundary."}
            if role == "consumer_accept" else
            {"role": role, "disposition": "not_applicable", "boundary_ids": [], "reason": "The 52-signal exact-hierarchy observer owns this role in the conjunction; this generated compatibility observer is restricted to Memory_AG tuple accept."}
            for role in roles
        ],
        "decision_observations": observations,
        "candidates": [{"candidate_id": name, "root_cause_class": root, "signature": dict(zip(obs_ids, signature))} for name, root, signature in candidates],
        "diagnostic_semantics": {"instance_match": "EXACT_CANONICAL_EQUALITY", "record_grouping_key": ["boundary_id", "canonical_instance", "seq"], "unknown_payload": "EVIDENCE_INCOMPLETE", "numeric_parse_failure": "EVIDENCE_INCOMPLETE", "candidate_match_cardinality": "EXACTLY_ONE"},
        "runtime_budget": {"qualified_ring_depth": 32, "non_progress_ring_depth": 16, "first_payload_samples": 8, "post_trigger_samples": 16, "no_progress_cycles": 4096, "max_log_bytes": 8388608, "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES", "state_activity_consumes_qualified_budget": False, "text_io_policy": "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY", "slowdown_limit_hard": False},
        "claim_boundary": "Minimal generated source-bound compatibility observer for Memory_AG tuple accept; the 52-signal exact-hierarchy observer retains family diagnostic authority.",
    }
    validation = generator.validate_contract(catalog, plan)
    if not validation.get("valid"):
        raise RuntimeError(f"plan validation failed: {validation.get('errors')}")
    write(PLAN, plan)
    os.environ["PATH"] = str(Path(r"C:\iverilog\bin")) + os.pathsep + os.environ.get("PATH", "")
    report = generator.materialize(CATALOG, PLAN, DIAG)
    write(GEN_REPORT, report)
    if not report.get("pass"):
        raise RuntimeError(f"source-bound materialization failed: {report.get('errors')}")
    write(DIAG / "source_bound_final_zip_contract.json", {
        "schema": "server-source-bound-final-zip-contract-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "enforcement": "required_next_fresh",
        "members": {
            "catalog": "diagnostics/source_bound_probe_catalog.json",
            "plan": "diagnostics/source_bound_probe_plan.json",
            "observer": "tb_probe/source_bound_causal_observer.svh",
            "parser": "package_tools/source_bound_causal_parser.py",
            "binding": "diagnostics/source_bound_probe_binding.json",
            "generation_report": "diagnostics/source_bound_observer_generation_report.json",
            "runner": "PREPARE_AND_RUN.sh",
        },
        "compile_observer_token": "source_bound_causal_observer.svh",
        "runtime_plusarg": "+CODEX_CAUSAL_OBSERVER",
        "return_log_token": "source_bound_causal.log",
        "return_decision_token": "source_bound_causal_decision.json",
    })
    (TREE / "tb_probe/source_bound_causal_observer.svh").write_bytes((DIAG / "source_bound_causal_observer.svh").read_bytes())
    (TREE / "package_tools/source_bound_causal_parser.py").write_bytes((DIAG / "source_bound_causal_parser.py").read_bytes())

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    runner = replace_once(
        runner,
        '"VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe $package_root/tb_probe/observer_only_wide_causal.svh")',
        '"VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe $package_root/tb_probe/source_bound_causal_observer.svh $package_root/tb_probe/observer_only_wide_causal.svh")',
        "compile observer conjunction",
    )
    runner = runner.replace('"+CODEX_OBSERVER_ONLY_WIDE_CAUSAL"]}', '"+CODEX_CAUSAL_OBSERVER","+CODEX_OBSERVER_ONLY_WIDE_CAUSAL"]}', 1)
    runner = runner.replace('"+CODEX_OBSERVER_ONLY_WIDE_CAUSAL",f"+CODEX_OBSERVER_CHUNK=', '"+CODEX_CAUSAL_OBSERVER","+CODEX_OBSERVER_ONLY_WIDE_CAUSAL",f"+CODEX_OBSERVER_CHUNK=', 1)
    runner = replace_once(
        runner,
        '+CODEX_OBSERVER_ONLY_WIDE_CAUSAL +CODEX_OBSERVER_CHUNK=$observer_chunk" > "$run_root/c0/simulator_argv.txt"',
        '+CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL +CODEX_OBSERVER_CHUNK=$observer_chunk" > "$run_root/c0/simulator_argv.txt"',
        "simulator argv source-bound plusarg",
    )
    runner = replace_once(
        runner,
        '+CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk"',
        '+CODEX_CAUSAL_OBSERVER +CODEX_OBSERVER_ONLY_WIDE_CAUSAL "+CODEX_OBSERVER_CHUNK=$observer_chunk"',
        "runtime source-bound plusarg",
    )
    runner = replace_once(
        runner,
        "    observer_rc=$?\n  else\n",
        "    observer_rc=$?\n    source_bound_log=\"$evidence_root/source_bound_causal.log\"\n    cp -f \"$run_root/c0/sim.log\" \"$source_bound_log\"\n    python3 \"$package_root/package_tools/source_bound_causal_parser.py\" --log \"$source_bound_log\" --output \"$evidence_root/source_bound_causal_decision.json\"\n    source_bound_rc=$?\n  else\n",
        "source-bound parser handoff",
    )
    runner = replace_once(runner, "    observer_rc=0\n  fi\n", "    observer_rc=0\n    source_bound_rc=0\n  fi\n", "compile-only source-bound status")
    runner = replace_once(
        runner,
        '[ "$observer_rc" -eq 0 ] || final=97; [ "$manifest_rc" -eq 0 ] || final=98',
        '[ "$observer_rc" -eq 0 ] || final=97; [ "$source_bound_rc" -eq 0 ] || final=97; [ "$manifest_rc" -eq 0 ] || final=98',
        "source-bound fail closed",
    )
    runner_path.write_text(runner, encoding="utf-8", newline="\n")

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    additions = [
        {"source_root": "attempt", "source": "evidence/source_bound_causal.log", "archive": "evidence/source_bound_causal.log", "required": False},
        {"source_root": "attempt", "source": "evidence/source_bound_causal_decision.json", "archive": "evidence/source_bound_causal_decision.json", "required": False},
        {"source_root": "package", "source": "diagnostics/source_bound_probe_catalog.json", "archive": "evidence/source_bound_probe_catalog.json", "required": True},
        {"source_root": "package", "source": "diagnostics/source_bound_probe_plan.json", "archive": "evidence/source_bound_probe_plan.json", "required": True},
        {"source_root": "package", "source": "diagnostics/source_bound_probe_binding.json", "archive": "evidence/source_bound_probe_binding.json", "required": True},
        {"source_root": "package", "source": "diagnostics/source_bound_observer_generation_report.json", "archive": "evidence/source_bound_observer_generation_report.json", "required": True},
    ]
    archives = {item.get("archive") for item in request["core_entries"]}
    request["core_entries"].extend(item for item in additions if item["archive"] not in archives)
    write(request_path, request)

    runner_contract_path = TREE / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = sha(runner_path)
    runner_contract["return_allowlist_tokens"] = list(dict.fromkeys(runner_contract["return_allowlist_tokens"] + ["source_bound_causal.log", "source_bound_causal_decision.json", "+CODEX_CAUSAL_OBSERVER"]))
    write(runner_contract_path, runner_contract)
    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["request_sha256"] = sha(request_path)
    write(post_contract_path, post_contract)
    print(json.dumps({"source_bound": "integrated", "boundary_count": 1, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
