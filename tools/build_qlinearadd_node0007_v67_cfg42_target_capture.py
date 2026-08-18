#!/usr/bin/env python3
"""Build the fresh QAdd v67 pretarget-quiet/target-continuous VCD successor."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
NEW = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
FAMILY = "qlinearadd_node0007"
EPOCH = "qadd-v66-return-target-capture-v1+tb-vcd-adaptive-v4+runtime-v3"
OUT = ROOT / "outputs/qlinearadd_node0007_v67_cfg42_tgcap_release"
SOURCE_OUT = ROOT / "outputs/qlinearadd_node0007_v66_cfg42_release"
SOURCE_TREE = SOURCE_OUT / "build" / OLD
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
SOURCE_RELEASE_ZIP = SOURCE_OUT / f"{OLD}.zip"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v66.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh"
OLD_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v66.py"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py"
OLD_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v66.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py"
ANALYSIS = ROOT / f"outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/formal_return_analysis.json"
AUDIT = ROOT / f"outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/RULE_GAP_AUDIT.json"
VCD_SUMMARY = ROOT / f"outputs/qlinearadd_node0007_v66_return_r1786770100877714671_2785121/streaming_analysis/chunks/003_dynamic_acceptance.json"
EXPECTED_SOURCE_SHA = "f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc"
GOOD_BITSTREAM_SHA = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def source_span(path: Path, leaf: str) -> str:
    matches = [
        row.strip()
        for row in path.read_text(encoding="utf-8", errors="strict").splitlines()
        if re.search(rf"\b{re.escape(leaf)}\b", row) and not row.lstrip().startswith("//")
    ]
    if not matches:
        raise RuntimeError(f"declaration span absent: {path}:{leaf}")
    return hashlib.sha256(matches[0].encode("utf-8")).hexdigest()


def refresh_current_source_bindings() -> None:
    """Reset the breadth round after canonical RTL source identity changed."""
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    catalog_path = TREE / "diagnostics/tb_vcd_signal_catalog.json"
    contract = load(contract_path)
    catalog = load(catalog_path)
    by_id = {row["signal_id"]: row for row in catalog["signals"]}
    source_records: dict[str, dict[str, Any]] = {}
    for row in contract["signals"]:
        source = ROOT / "NDP_copy01" / row["source_path"]
        leaf = row["exact_hierarchy"].rsplit(".", 1)[-1]
        row["source_sha256"] = sha(source)
        row["declaration_span_sha256"] = source_span(source, leaf)
        catalog_row = by_id[row["signal_id"]]
        catalog_row["source_sha256"] = row["source_sha256"]
        catalog_row["declaration_span_sha256"] = row["declaration_span_sha256"]
        source_records[row["source_path"]] = identity(source)
    source_rows = sorted(
        [
            {
                "signal_id": row["signal_id"], "exact_hierarchy": row["exact_hierarchy"],
                "width_bits": row["width_bits"], "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "declaration_span_sha256": row["declaration_span_sha256"],
            }
            for row in contract["signals"]
        ],
        key=lambda row: row["signal_id"],
    )
    semantic = hashlib.sha256(
        json.dumps(source_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    pinned = hashlib.sha256(
        json.dumps(
            sorted({(row["source_path"], row["source_sha256"]) for row in contract["signals"]}),
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    signal_ids = [row["signal_id"] for row in contract["signals"]]
    candidate_ids = [row["candidate_id"] for row in contract["candidates"]]
    baseline_path = TREE / "provenance/qadd_v64_round3_breadth_baseline.json"
    baseline = load(baseline_path)
    baseline["pinned_rtl_tree_sha256"] = pinned
    baseline["claim_boundary"] = "Count/boundary-only v64 round-three soft reference rebased to the current canonical source identity; no v64 revalidation or DUT claim."
    write(baseline_path, baseline)
    contract["diagnostic_round"] = {
        "round_index": 1,
        "round_kind": "FIRST_DIAGNOSTIC_ROUND",
        "breadth_baseline": {
            "mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE",
            "reference_round_index": 3, "reference_package_id": baseline["package_id"],
            "receipt_path": "provenance/qadd_v64_round3_breadth_baseline.json",
            "receipt_sha256": sha(baseline_path), "reference_signal_count": 64,
            "reference_direct_driver_leaf_count": 0, "reference_candidate_count": 7,
            "reference_boundary_count": 4,
            "reasonable_signal_count_range": {"minimum": 48, "maximum": 96},
            "deviation": {"relation": "WITHIN_REFERENCE_RANGE", "explanation": None, "acknowledged": False},
        },
        "source_identity": {"pinned_rtl_tree_sha256": pinned, "catalog_source_identity_sha256": semantic},
        "coverage_gaps": [],
        "evolution": {
            "predecessor": None, "added_signal_ids": signal_ids, "removed_signal_ids": [],
            "unchanged_signal_ids": [], "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": [], "closed_candidate_ids": [],
                "new_candidate_ids": candidate_ids, "closure_evidence": [],
            },
        },
    }
    write(catalog_path, catalog)
    write(contract_path, contract)
    write(
        TREE / "provenance/v67_current_source_identity.json",
        {
            "schema": "qadd-v67-current-source-identity-v1", "package_id": NEW,
            "reason": "Canonical source bytes changed after the v66 build; adaptive-v4 therefore resets to a first diagnostic round instead of falsely declaring unchanged source identity.",
            "pinned_rtl_tree_sha256": pinned, "catalog_source_identity_sha256": semantic,
            "sources": [source_records[key] for key in sorted(source_records)],
            "functional_rtl_modified_by_family": False, "pass": True, "errors": [],
        },
    )


def replace_tree_identity() -> None:
    if OUT.exists():
        raise RuntimeError(f"fresh output already exists: {OUT}")
    shutil.copytree(SOURCE_TREE, TREE)
    replacements = (
        (OLD, NEW),
        ("QAdd v66", "QAdd v67"),
        ("qlinearadd_node0007_tb_vcd_causal_cone_v66", "qlinearadd_node0007_tb_vcd_causal_cone_v67"),
        ("codex_qadd_tb_vcd_causal_cone_v66", "codex_qadd_tb_vcd_causal_cone_v67"),
        ("qlinearadd_node0007_tb_vcd_live_supervision_v66.py", "qlinearadd_node0007_tb_vcd_live_supervision_v67.py"),
        ("qlinearadd_node0007_tb_vcd_finalize_v66.py", "qlinearadd_node0007_tb_vcd_finalize_v67.py"),
        ("qadd-v66", "qadd-v67"),
    )
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        if path.suffix.lower() in {".bin", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        changed = text
        for old, new in replacements:
            changed = changed.replace(old, new)
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    (TREE / OLD_TB).rename(TREE / NEW_TB)
    (TREE / OLD_LIVE).rename(TREE / NEW_LIVE)
    (TREE / OLD_FINALIZER).rename(TREE / NEW_FINALIZER)
    for path in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(path)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def patch_tb_capture() -> None:
    path = TREE / NEW_TB
    text = path.read_text(encoding="utf-8")
    old = """      $dumpon;
      $display(\"CODEX_TB_VCD_STARTED path=%0s\", tbvcd_path);"""
    new = """      // v66 proved the entire pre-target cone static while native preload advanced.
      // Keep only a sparse runtime-safety snapshot until the actual target enters.
      $dumpoff;
      $dumpflush;
      $display(\"CODEX_TB_VCD_PRETARGET_QUIET_V1 path=%0s cadence_cycles=16384\", tbvcd_path);"""
    if old not in text:
        raise RuntimeError("TB initial dump anchor drifted")
    text = text.replace(old, new, 1)
    old = """      if ((sig_exec_start || sig_global_exec_active) && !tbvcd_target_entry_seen) begin
        tbvcd_target_entry_seen <= 1;
        $display(\"CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=%0t owner_cycles=%0d\", $time, tbvcd_owner_cycles);
      end"""
    new = """      if ((sig_exec_start || sig_global_exec_active) && !tbvcd_target_entry_seen) begin
        // Full 64-signal causal-cone capture is continuous from this boundary.
        $dumpon;
        $dumpflush;
        tbvcd_target_entry_seen <= 1;
        $display(\"CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=%0t owner_cycles=%0d full_continuous_capture=1\", $time, tbvcd_owner_cycles);
      end"""
    if old not in text:
        raise RuntimeError("TB target entry anchor drifted")
    text = text.replace(old, new, 1)
    old = """        $display(\"CODEX_TBVCD_HEARTBEAT_V2 sim_time=%0d owner_cycles=%0d progress=%0d state=%0h global=%0d unresolved_xz=%0d target_entry=%0d\", tbvcd_sim_time_ps, tbvcd_owner_cycles, tbvcd_progress_count, tbvcd_state_current, sig_global_cycle, $isunknown(tbvcd_state_current), tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active);
        $dumpflush;"""
    new = """        $display(\"CODEX_TBVCD_HEARTBEAT_V2 sim_time=%0d owner_cycles=%0d progress=%0d state=%0h global=%0d unresolved_xz=%0d target_entry=%0d\", tbvcd_sim_time_ps, tbvcd_owner_cycles, tbvcd_progress_count, tbvcd_state_current, sig_global_cycle, $isunknown(tbvcd_state_current), tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active);
        if (!(tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active)) begin
          // Zero-duration safety snapshot only. It is excluded from functional evidence.
          $dumpon;
          $dumpflush;
          $dumpoff;
          $display(\"CODEX_TBVCD_PRETARGET_SAFETY_SNAPSHOT_V1 sim_time=%0t owner_cycles=%0d\", $time, tbvcd_owner_cycles);
        end else begin
          $dumpflush;
        end"""
    if old not in text:
        raise RuntimeError("TB heartbeat anchor drifted")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_finalizer_normalization() -> None:
    path = TREE / NEW_FINALIZER
    text = path.read_text(encoding="utf-8")
    old = """def normalize(path: str) -> str:
    return \".\".join(part.lstrip(\"\\\\\").strip() for part in path.split(\".\"))"""
    new = """def normalize(path: str) -> str:
    normalized = \".\".join(part.lstrip(\"\\\\\").strip() for part in path.split(\".\"))
    # VCS appends a terminal packed range to vector references. The source-bound
    # catalog already binds width separately, so only that legal suffix is removed.
    return re.sub(r\"\\s+\\[[0-9]+:[0-9]+\\]$\", \"\", normalized)"""
    if old not in text:
        raise RuntimeError("finalizer normalization anchor drifted")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def patch_finalizer_width_binding() -> None:
    path = TREE / NEW_FINALIZER
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "def scan_vcd(path: Path, expected: set[str]) -> dict[str, Any]:",
        "def scan_vcd(path: Path, expected: dict[str, int]) -> dict[str, Any]:",
        1,
    )
    text = text.replace(
        "    names: list[str] = []\n",
        "    names: list[str] = []\n    widths: list[int] = []\n",
        1,
    )
    text = text.replace(
        "                        names.append(normalize(\".\".join([*scopes, reference])))\n",
        "                        names.append(normalize(\".\".join([*scopes, reference])))\n                        widths.append(int(fields[2]))\n",
        1,
    )
    old = """    actual = set(names)
    return {
        \"exists\": True,
        \"header_valid\": bool(enddefinitions and timescale and names),
        \"timescale\": timescale,
        \"catalog_complete\": expected.issubset(actual),
        \"catalog_exact_set\": actual == expected and len(names) == len(expected),
        \"expected_signal_count\": len(expected),
        \"header_var_count\": len(names),
        \"missing_expected_hierarchies\": sorted(expected - actual),
        \"unexpected_hierarchies\": sorted(actual - expected),"""
    new = """    actual = set(names)
    expected_names = set(expected)
    actual_widths = {name: width for name, width in zip(names, widths)}
    width_mismatches = [
        {\"exact_hierarchy\": name, \"expected_width\": expected[name], \"actual_width\": actual_widths.get(name)}
        for name in sorted(expected_names & actual)
        if actual_widths.get(name) != expected[name]
    ]
    return {
        \"exists\": True,
        \"header_valid\": bool(enddefinitions and timescale and names),
        \"timescale\": timescale,
        \"catalog_complete\": expected_names.issubset(actual) and not width_mismatches,
        \"catalog_exact_set\": actual == expected_names and len(names) == len(expected_names) and not width_mismatches,
        \"expected_signal_count\": len(expected_names),
        \"header_var_count\": len(names),
        \"missing_expected_hierarchies\": sorted(expected_names - actual),
        \"unexpected_hierarchies\": sorted(actual - expected_names),
        \"width_mismatches\": width_mismatches,"""
    if old not in text:
        raise RuntimeError("finalizer width-binding anchor drifted")
    text = text.replace(old, new, 1)
    old = """    expected = {normalize(str(item[\"exact_hierarchy\"])) for item in contract[\"signals\"]}
    scan = scan_vcd(args.vcd, expected)"""
    new = """    expected = {
        normalize(str(item[\"exact_hierarchy\"])): int(item[\"width_bits\"])
        for item in contract[\"signals\"]
    }
    scan = scan_vcd(args.vcd, expected)"""
    if old not in text:
        raise RuntimeError("finalizer expected-width anchor drifted")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def bind_provenance_and_contracts() -> None:
    provenance = TREE / "provenance"
    shutil.copyfile(ANALYSIS, provenance / "v66_formal_return_analysis.json")
    shutil.copyfile(AUDIT, provenance / "v66_rule_gap_audit.json")
    shutil.copyfile(VCD_SUMMARY, provenance / "v66_pretarget_dynamic_summary.json")

    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    predecessor_bytes = vcd_path.read_bytes()
    predecessor_sha = hashlib.sha256(predecessor_bytes).hexdigest()
    (provenance / "v66_server_tb_vcd_bounded_causal_cone_contract.json").write_bytes(predecessor_bytes)
    vcd = load(vcd_path)
    signals = [row["signal_id"] for row in vcd["signals"]]
    candidates = [row["candidate_id"] for row in vcd["candidates"]]
    vcd["package_id"] = NEW
    vcd["diagnostic_round"]["round_index"] = 2
    vcd["diagnostic_round"]["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    vcd["diagnostic_round"]["evolution"] = {
        "predecessor": {
            "package_id": OLD,
            "round_index": 1,
            "contract_path": "provenance/v66_server_tb_vcd_bounded_causal_cone_contract.json",
            "contract_sha256": predecessor_sha,
            "pinned_rtl_tree_sha256": vcd["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
        },
        "added_signal_ids": [], "removed_signal_ids": [], "unchanged_signal_ids": signals,
        "removal_evidence": [],
        "candidate_preservation": {
            "preserved_candidate_ids": candidates, "closed_candidate_ids": [],
            "new_candidate_ids": [], "closure_evidence": [],
        },
    }
    vcd["execution"]["tb_source_path"] = NEW_TB
    vcd["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    vcd["claim_boundary"] = "Exact 4/2 target validation with pretarget safety-only snapshots and continuous untruncated 64-signal capture from target entry; local gates make no production or E3-E5 claim."
    write(vcd_path, vcd)

    temporal = {
        "schema": "qadd-pretarget-quiet-target-continuous-capture-v1",
        "package_id": NEW, "predecessor_package_id": OLD,
        "source_return_analysis": identity(ANALYSIS), "source_rule_gap_audit": identity(AUDIT),
        "evidence_basis": {
            "streamed_vcd_bytes": 583_852_780, "catalog_signals": 64,
            "target_entry_observed": False, "target_signal_set_static": True,
            "pretarget_matrix_completions": 24, "next_matrix_read_burst": 237,
        },
        "capture": {
            "pretarget": "SAFETY_SNAPSHOT_EVERY_16384_OWNER_CYCLES_NOT_FUNCTIONAL_EVIDENCE",
            "target_entry": "DUMPON_AND_FLUSH_BEFORE_ENTRY_MARKER",
            "target_window": "CONTINUOUS_ALL_64_SIGNALS_UNTIL_LEGAL_STOP_OR_FINAL_CLOSE",
            "byte_cap": None, "event_cap": None, "target_window_sampling": False,
            "size_based_deletion": False,
        },
        "negative_controls": [
            "missing_target_entry_dumpon_fails", "pretarget_snapshot_used_as_functional_evidence_fails",
            "target_window_dumpoff_before_legal_plateau_fails", "vector_range_width_mismatch_fails",
            "legal_terminal_vector_range_suffix_normalizes_without_signal_loss",
        ],
        "functional_rtl_or_config_changed": False, "pass": True, "errors": [],
    }
    write(TREE / "diagnostics/pretarget_target_capture_contract.json", temporal)
    dynamic_path = TREE / "diagnostics/qadd_config42_dynamic_acceptance.json"
    dynamic = load(dynamic_path)
    dynamic["package_id"] = NEW
    dynamic["capture_window"] = {
        "start": "LIVE_TARGET_ENTRY_DUMPON_BEFORE_MARKER", "continuous": True,
        "pretarget_snapshots_are_functional_evidence": False,
    }
    write(dynamic_path, dynamic)
    transition = {
        "schema": "qadd-v66-to-v67-target-capture-v1", "source_package": OLD,
        "package_id": NEW,
        "previous_version_progress": "v66 materialized and production-compiled the exact 4/2 lineage, but the six-hour attempt remained in advancing matrix preload and never entered the DUT target.",
        "current_version_purpose": "Remove eager pretarget full-rate clock tracing while preserving safety timestamps, then capture the unchanged 64-signal causal cone continuously from target entry to adjudicate ordered complementary requests and terminal evidence.",
        "changed_surfaces": ["fresh_identity", "package_local_tb_capture_control", "package_local_vcd_hierarchy_normalization", "runtime_return_provenance"],
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_target_cone", "candidate_matrix"],
        "server_actions_performed": [],
    }
    write(provenance / "v66_to_v67_target_capture.json", transition)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    additions = [
        {"source_root": "package", "source": "diagnostics/pretarget_target_capture_contract.json", "archive": "source_package/pretarget_target_capture_contract.json", "required": True},
        {"source_root": "package", "source": "provenance/v66_formal_return_analysis.json", "archive": "source_package/v66_formal_return_analysis.json", "required": True},
        {"source_root": "package", "source": "provenance/v66_rule_gap_audit.json", "archive": "source_package/v66_rule_gap_audit.json", "required": True},
    ]
    archives = {row.get("archive") for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)


def refresh_identity_contracts_and_manifest() -> None:
    runner = TREE / "PREPARE_AND_RUN.sh"
    runner_sha = sha(runner)
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path)
    resilience["package_id"] = NEW
    resilience["runner_sha256"] = runner_sha
    write(resilience_path, resilience)

    projected = f"install/cfg_pkg/{NEW}/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    layout["package_id"] = NEW
    layout["install_name"] = NEW
    projected_absolute = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(projected)
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    if isinstance(layout.get("runner_bindings"), dict):
        layout["runner_bindings"]["runner_sha256"] = runner_sha
    write(layout_path, layout)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post["package_id"] = NEW
    post["request_sha256"] = sha(request_path)
    post["runner_sha256"] = runner_sha
    post["helper_sha256"] = sha(TREE / "package_tools/server_post_sim_return.py")
    write(post_path, post)

    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    vcd = load(vcd_path)
    vcd["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    write(vcd_path, vcd)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = NEW
    selector["vcd_contract_sha256"] = sha(vcd_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {
        "source_package/pretarget_target_capture_contract.json",
        "source_package/v66_formal_return_analysis.json",
        "source_package/v66_rule_gap_audit.json",
    })
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)

    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["package_id"] = NEW
    manifest["package_identity"] = NEW
    manifest["install_name"] = NEW
    manifest["activation_epoch"] = EPOCH
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["previous_version_progress"] = "v66 selected and compiled the exact 4/2 lineage but remained in advancing pre-target preload until wall ceiling; no dynamic request/accept/clear was exercised."
    manifest["current_version_purpose"] = "Preserve the exact 4/2 lineage and 64-signal cone while using safety-only pretarget snapshots and continuous full capture from target entry."
    manifest["pretarget_target_capture"] = "diagnostics/pretarget_target_capture_contract.json"
    manifest["diagnostic_mode_selector_sha256"] = sha(selector_path)
    manifest["path_length_budget"]["longest_projected_relative_path"] = projected
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(projected)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)
    selector = load(selector_path)
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest = load(manifest_path)
    manifest["diagnostic_mode_selector_sha256"] = sha(selector_path)
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            member = f"{NEW}/{path.relative_to(TREE).as_posix()}"
            info = zipfile.ZipInfo(member, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def main() -> int:
    if not SOURCE_ZIP.is_file() or sha(SOURCE_ZIP) != EXPECTED_SOURCE_SHA:
        raise RuntimeError("protected v66 pending package identity drifted")
    if sha(SOURCE_RELEASE_ZIP) != EXPECTED_SOURCE_SHA or not SOURCE_TREE.is_dir():
        raise RuntimeError("durable v66 release staging is not the exact pending source")
    source_before = identity(SOURCE_ZIP)
    if load(ANALYSIS).get("pass") is not True or load(AUDIT).get("disposition") != "RULE_CONFIRMATION_NO_PUBLIC_CHANGE":
        raise RuntimeError("v66 analysis/audit authority is not complete")
    replace_tree_identity()
    patch_tb_capture()
    patch_finalizer_normalization()
    patch_finalizer_width_binding()
    bind_provenance_and_contracts()
    refresh_current_source_bindings()
    refresh_identity_contracts_and_manifest()

    bitstream = TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
    if sha(bitstream) != GOOD_BITSTREAM_SHA:
        raise RuntimeError("validated 4/2 bitstream drifted")
    frozen = {
        "schema": "qadd-v67-frozen-surface-v1", "package_id": NEW,
        "source_v66_preserved": identity(SOURCE_ZIP) == source_before,
        "config42_bitstream_preserved": sha(bitstream) == GOOD_BITSTREAM_SHA,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
        "changed_surfaces": ["identity", "tb_capture_control", "vcd_catalog_normalization", "return_provenance"],
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_target_cone", "candidate_matrix"],
        "storage_manager_called": False, "server_actions_performed": [],
        "pass": identity(SOURCE_ZIP) == source_before and sha(bitstream) == GOOD_BITSTREAM_SHA and not (TREE / "rtl").exists(),
        "errors": [],
    }
    write(OUT / "frozen_surface_receipt.json", frozen)
    if frozen["pass"] is not True:
        raise RuntimeError("frozen surface check failed")
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic ZIP recomputation differs")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("final ZIP CRC failed")
    receipt = {
        "schema": "qadd-v67-target-capture-build-v1", "role_id": "family.qlinearadd",
        "owner_epoch": 2, "registry_epoch": 6, "package_id": NEW, "family": FAMILY,
        "activation_epoch": EPOCH, "source_v66": source_before,
        "return_analysis": identity(ANALYSIS), "rule_gap_audit": identity(AUDIT),
        "package": identity(ZIP), "repeat_package": identity(REPEAT),
        "deterministic_recompute": True, "storage_manager_called": False,
        "server_actions_performed": [], "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "pass": True, "errors": [],
        "claim_boundary": "Local package construction only; no production compile/simulation or natural/formal-D/E3-E5 claim.",
    }
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--refresh-existing"]:
        refresh_current_source_bindings()
        refresh_identity_contracts_and_manifest()
        deterministic_zip(ZIP)
        deterministic_zip(REPEAT)
        if ZIP.read_bytes() != REPEAT.read_bytes():
            raise RuntimeError("refreshed deterministic ZIP recomputation differs")
        receipt = load(OUT / "build_receipt.json")
        receipt["package"] = identity(ZIP)
        receipt["repeat_package"] = identity(REPEAT)
        write(OUT / "build_receipt.json", receipt)
        print(json.dumps({"package_id": NEW, "refreshed": True, "pass": True}, sort_keys=True))
        raise SystemExit(0)
    raise SystemExit(main())
