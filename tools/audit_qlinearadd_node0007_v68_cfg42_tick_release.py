#!/usr/bin/env python3
"""Run the full current QAdd release audit for v68 via the gated v67 suite."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "tools/audit_qlinearadd_node0007_v67_cfg42_target_capture_release.py"
    source = path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"', 'PACKAGE = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"'),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v66_cfg42"', 'PRIOR = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"'),
        ('PRIOR_SHA = "f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc"', 'PRIOR_SHA = "dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740"'),
        ('EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-v66-return-target-capture-v1+tb-vcd-adaptive-v4+runtime-v3"', 'EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-pretarget-safety-pulse-v1+runtime-v3-pid-identity"'),
        ('OUT = ROOT / "outputs/qlinearadd_node0007_v67_cfg42_tgcap_release"', 'OUT = ROOT / "outputs/qlinearadd_node0007_v68_cfg42_tick_release"'),
        ('tools/validate_qlinearadd_node0007_v67_cfg42_target_capture.py', 'tools/validate_qlinearadd_node0007_v68_cfg42_tick.py'),
        ('tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh', 'tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v68.svh'),
        ('package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py', 'package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v68.py'),
        ('package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py', 'package_tools/qlinearadd_node0007_tb_vcd_finalize_v68.py'),
        ('codex_qadd_tb_vcd_causal_cone_v67', 'codex_qadd_tb_vcd_causal_cone_v68'),
        ('qadd-v67', 'qadd-v68'),
        ('QAdd v67', 'QAdd v68'),
        ('outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/formal_return_analysis.json', 'outputs/qlinearadd_node0007_v67_return_r1786793338560402996_2911236/formal_return_analysis.json'),
        ('outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/RULE_GAP_AUDIT.json', 'outputs/qlinearadd_node0007_v67_return_r1786793338560402996_2911236/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json'),
        ('RULE_CONFIRMATION_NO_PUBLIC_CHANGE', 'MACHINE_READABLE_PACKAGE_LOCAL_EXEMPTION_WITH_NEGATIVE_CONTROLS'),
        ('v66 proved exact 4/2 materialization and production compile while pretarget matrix preload advanced; wall ceiling arrived before target entry, so the ordered 0x33333333/0xcccccccc acceptance contract remains dynamically open.', 'v67 proved exact 4/2 materialization, production compile and fast pretarget execution, but same-time safety snapshots left appended VCD time static and caused a package-local semantic-v5 freeze before target entry.'),
        ('Preserve the validated 4/2 lineage and full 64-signal causal target while suppressing full-rate pretarget VCD, retaining periodic safety snapshots, and starting continuous unbounded causal capture before the target-entry marker.', 'Preserve exact 4/2 and the full 64-signal causal target; make each transport-only pretarget pulse span a real owner edge, retain continuous unbounded target capture, and bind process ownership to PID plus start time.'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v67 audit adapter anchor drifted: {old}")
        source = source.replace(old, new)
    injection_anchor = """        source = source.replace(old, new)
    phase_anchor = \"\"\"def import_module(path: Path, name: str) -> Any:
"""
    injection = """        source = source.replace(old, new)
    refined_negative_replacements = [
        ('(\"low_confidence_removal\", lambda value: value[\"diagnostic_round\"].update({\"round_index\": 2, \"round_kind\": \"EVIDENCE_REFINED_SUCCESSOR\"}))', '(\"low_confidence_removal\", lambda value: (value[\"diagnostic_round\"][\"evolution\"][\"removed_signal_ids\"].append(value[\"diagnostic_round\"][\"evolution\"][\"unchanged_signal_ids\"][0]), value[\"diagnostic_round\"][\"evolution\"][\"removal_evidence\"].append({\"signal_id\": value[\"diagnostic_round\"][\"evolution\"][\"unchanged_signal_ids\"][0], \"reason\": \"negative control\", \"confidence\": \"LOW\", \"affected_candidate_ids\": [], \"disposition\": \"FAMILY_ADAPTIVE_PRUNING\"})))'),
        ('(\"add_remove_diff_mismatch\", lambda value: value[\"diagnostic_round\"][\"evolution\"][\"added_signal_ids\"].pop())', '(\"add_remove_diff_mismatch\", lambda value: value[\"diagnostic_round\"][\"evolution\"][\"added_signal_ids\"].append(\"sig_not_in_catalog\"))'),
        ('(\"candidate_loss\", lambda value: value[\"diagnostic_round\"][\"evolution\"][\"candidate_preservation\"][\"new_candidate_ids\"].pop())', '(\"candidate_loss\", lambda value: value[\"diagnostic_round\"][\"evolution\"][\"candidate_preservation\"][\"preserved_candidate_ids\"].pop())'),
        ('\"breadth_v4_round1\": contract[\"diagnostic_round\"][\"round_index\"] == 1 and contract[\"diagnostic_round\"][\"round_kind\"] == \"FIRST_DIAGNOSTIC_ROUND\"', '\"breadth_v4_round1\": contract[\"diagnostic_round\"][\"round_index\"] == 2 and contract[\"diagnostic_round\"][\"round_kind\"] == \"EVIDENCE_REFINED_SUCCESSOR\" and contract[\"diagnostic_round\"][\"evolution\"][\"predecessor\"][\"package_id\"] == PRIOR'),
    ]
    for old, new in refined_negative_replacements:
        if old not in source:
            raise RuntimeError(f\"v65 refined negative-control anchor drifted: {old}\")
        source = source.replace(old, new)
    phase_anchor = \"\"\"def import_module(path: Path, name: str) -> Any:
"""
    if injection_anchor not in source:
        raise RuntimeError("v67 nested audit injection anchor drifted")
    source = source.replace(injection_anchor, injection, 1)
    namespace = {"__name__": "qadd_v68_full_release_audit", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
