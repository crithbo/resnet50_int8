#!/usr/bin/env python3
"""Finalize the v96b compile-failure analysis and rule disposition."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_return_r1786770065727401255_2781777"
SUMMARY = ANALYSIS / "streaming_summary.json"
PROBE = ANALYSIS / "package_source/tb_vcd_bounded_causal_cone.svh"
V96_CONTRACT = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_release1/build/r5_n4_hw_v96b_tbvcd_memtuple/contracts/tb_vcd_bounded_causal_cone_contract.json"
V95_ANALYSIS = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_return_r1786734268630496410_2597866/return_analysis.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def identity(path: Path) -> dict[str, Any]:
    return {"bytes": path.stat().st_size, "path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path)}


def main() -> int:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    v95 = json.loads(V95_ANALYSIS.read_text(encoding="utf-8"))
    contract = json.loads(V96_CONTRACT.read_text(encoding="utf-8"))
    probe = PROBE.read_text(encoding="utf-8")
    duplicate = "u_Memory_AG_Idx_Queue.u_Memory_AG_Idx_Queue."
    duplicate_signals = [row["signal_id"] for row in contract["signals"] if duplicate in row["exact_hierarchy"]]
    sites = summary["compile_log"]["unique_xmre_sites"]
    expected_first_ten = [
        "sig_mem_raw_idx_all", "sig_mem_raw_tag_all", "sig_mem_i0_raw_valid", "sig_mem_i0_raw_last",
        "sig_mem_i0_raw_same", "sig_mem_i0_raw_last_index", "sig_mem_i0_gotten",
        "sig_mem_i0_same_gotten_mask", "sig_mem_i0_valid_masked", "sig_mem_i0_split_wr",
    ]
    checks = {
        "exact_zip_and_manifest": summary["pass"],
        "compile_exit_2": summary["receipts"]["compile_core"]["compile_exit"] == 2,
        "simulation_not_started": summary["receipts"]["sim_exit"]["simulation_started"] is False,
        "target_not_entered": summary["receipts"]["runtime"]["target_entry"]["observed"] is False,
        "first_error_xmre": summary["first_error"] == "Error-[XMRE] Cross-module reference resolution error",
        "ten_vcs_reported_sites": [row["observer_symbol"] for row in sites] == expected_first_ten,
        "all_reported_sites_package_probe": all(row["source"].endswith("/tb_probe/tb_vcd_bounded_causal_cone.svh") for row in sites),
        "all_reported_token_same": {row["token"] for row in sites} == {"u_Memory_AG_Idx_Queue"},
        "all_53_added_contract_paths_duplicate_anchor": len(duplicate_signals) == 53,
        "probe_duplicate_occurrences_cover_declaration_and_dump": probe.count(duplicate) == 106,
        "v95_validated_boundary_preserved": v95["root_disposition"]["VALIDATED_ROOT_CAUSE"] == "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION",
    }
    if not all(checks.values()):
        raise RuntimeError(f"v96 analysis invariant failed: {[key for key, value in checks.items() if not value]}")

    analysis = {
        "DIRECT_ACTUAL_RTL_EVIDENCE": {
            "source_identity_status": "COMPLETE_FOR_COMPILE_FAILURE",
            "actual_module_instance": "Memory_WR_Stream_Engine.sv line 87 instantiates exactly one u_Memory_AG_Idx_Queue",
            "observer_scope": "bind originates inside Memory_WR_Stream_Engine; therefore added leaves must use one relative u_Memory_AG_Idx_Queue anchor",
            "functional_rtl_defect": "REBUTTED_FOR_THIS_FAILURE",
        },
        "DIRECT_CONFIG_EVIDENCE": {
            "v95_validated_values_preserved": True,
            "v96_runtime_consumption": "NOT_REACHED",
            "config_workaround": "NOT_APPLICABLE_TO_PACKAGE_LOCAL_COMPILE_FAILURE",
        },
        "DYNAMIC_EXECUTION_EVIDENCE": {
            "v96_new_dynamic_evidence": "NONE_SIMULATION_NOT_STARTED",
            "v95_preserved_boundary": "MEMORY_AG_METADATA_TRANSACTION_SUPPLY_SHORT_BY_ONE_32_UNIT_TRANSACTION",
            "v95_leaf_state": "OPEN_UNVALIDATED_MECHANISM",
        },
        "attempt_id": "a2781777",
        "checks": checks,
        "claim_boundary": "v96 proves only a package-local TB/probe XMR compile defect. It adds no tuple, VCD, target, natural-terminal, formal-D or E3-E5 evidence and cannot change the v95 dynamic root boundary.",
        "compile": {
            "actual_cwd": summary["receipts"]["compile_argv"]["cwd"],
            "actual_argv": summary["receipts"]["compile_argv"]["argv"],
            "exit": 2,
            "first_true_error": summary["first_error"],
            "reported_error_count": 10,
            "vcs_error_limit_reached": True,
        },
        "conflicts": [],
        "execution_id": "r1786770065727401255_2781777",
        "first_divergence": {
            "classification": "PACKAGE_LOCAL_TB_PROBE_HIERARCHY_DUPLICATION",
            "first_site": "tb_probe/tb_vcd_bounded_causal_cone.svh:511 sig_mem_raw_idx_all",
            "exact_bad_anchor": duplicate,
        },
        "identity": summary["identity"],
        "last_proven_good": "native production compile launched directly with preflight noninterference and parsed actual DUT/package sources up to XMR resolution",
        "package_id": "r5_n4_hw_v96b_tbvcd_memtuple",
        "pass": True,
        "previous_version_progress": "v95 validated that Memory_AG metadata supply is short by one 32-unit transaction while prepared-data generation is exact; the precise three-input formation leaf remained open.",
        "production_partition": {
            "compile_exit": 2,
            "preflight_provider_probe_performed": False,
            "runtime_started": False,
            "simulation_started": False,
            "target_entry": False,
        },
        "root_disposition": {
            "classification": "PACKAGE_LOCAL_TB_PROBE_HIERARCHY_DUPLICATION",
            "exact_extent": "all 53 v96-added signals use a duplicated relative instance anchor in both connection and dump references; VCS reports the first 10 then stops at its default error limit",
            "repair": "fresh identity; remove exactly one duplicated u_Memory_AG_Idx_Queue segment from the 53 added contract/probe paths; preserve all signals and frozen functional surfaces",
        },
        "schema": "node0004-v96b-formal-return-analysis-v1",
        "source_return": summary["source"],
        "streaming_artifacts": {
            "analysis_state": "streaming/analysis_state.json",
            "checkpoints": "streaming/checkpoints.jsonl",
            "incremental_report": "streaming/report.md",
            "summary": "streaming_summary.json",
        },
        "successor_required": True,
        "termination_boundary": {
            "e3": "NOT_PROVEN",
            "e4": "NOT_PROVEN",
            "e5": "NOT_PROVEN",
            "formal_d": "NOT_PROVEN",
            "natural_terminal": False,
            "return_disposition": "SIM_NOT_STARTED_RETURN / DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        },
    }
    write(ANALYSIS / "return_analysis.json", analysis)

    audit = {
        "conflicts": [],
        "disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "package_build_failure_rule_audit_triggered": False,
        "package_build_failure_rule_audit_reason": "single package-local target-execution failure; v95 executed the target, so the two-consecutive-failure threshold is not met",
        "package_only_first_fresh_negative_controls": [
            "reject_repeated_memory_ag_instance_anchor",
            "require_each_added_leaf_share_the_compiled_v95_memidx_anchor_depth",
            "require_contract_probe_exact_hierarchy_multiset_equality",
            "require_all_153_signals_retained",
        ],
        "pass": True,
        "rule_gap_audit_triggered": False,
        "rule_gap_audit_reason": "v96 did not compile or enter the target; the successful-target-but-nonunique trigger does not apply",
        "schema": "node0004-v96b-rule-disposition-v1",
        "shared_rule_change_required": False,
        "why_current_rules_are_sufficient": "current source-bound exact-hierarchy rules already forbid identity drift; the defect is an isolated family builder implementation error and is closed by a fresh exact hierarchy negative control",
    }
    write(ANALYSIS / "rule_disposition.json", audit)

    report_path = ANALYSIS / "streaming/report.md"
    text = report_path.read_text(encoding="utf-8")
    if "## Family disposition" not in text:
        text += (
            "\n## Family disposition\n\n"
            "- root: `PACKAGE_LOCAL_TB_PROBE_HIERARCHY_DUPLICATION`\n"
            "- first divergence: probe line 511; duplicated `u_Memory_AG_Idx_Queue` anchor\n"
            "- affected extent: all 53 newly added leaves; VCS emitted 10 XMREs then reached its default limit\n"
            "- v96 dynamic tuple evidence: none; simulation and target did not start\n"
            "- v95 validated 32-unit metadata deficit remains the last dynamic boundary\n"
            "- rule disposition: `RULE_CONFIRMATION_NO_CHANGE`; package-build-failure audit not triggered\n"
        )
        report_path.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"pass": True, "analysis": identity(ANALYSIS / "return_analysis.json"), "rule_disposition": identity(ANALYSIS / "rule_disposition.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
