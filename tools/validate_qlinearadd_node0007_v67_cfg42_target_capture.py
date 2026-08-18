#!/usr/bin/env python3
"""Independently validate the v67 config42 target-capture staging and final ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import types
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
PRIOR = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
PRIOR_SHA = "f9add4a1f54d922fb76fbe7d7b8a72e4965fea0c27546864fb3032bcad8862bc"
TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh"
FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def source_span(path: Path, leaf: str) -> str:
    rows = [
        row.strip()
        for row in path.read_text(encoding="utf-8", errors="strict").splitlines()
        if re.search(rf"\b{re.escape(leaf)}\b", row) and not row.lstrip().startswith("//")
    ]
    if not rows:
        raise ValueError(f"source declaration absent: {path}:{leaf}")
    return hashlib.sha256(rows[0].encode("utf-8")).hexdigest()


def load_v66_validator() -> dict[str, Any]:
    path = ROOT / "tools/validate_qlinearadd_node0007_v66_config42_release.py"
    source = path.read_text(encoding="utf-8")
    replacements = {
        'PACKAGE = "r5_qadd_n7_tailround_lanephase_v66_cfg42"': f'PACKAGE = "{PACKAGE}"',
        'PRIOR = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"': f'PRIOR = "{PRIOR}"',
    }
    for old, new in replacements.items():
        if old not in source:
            raise RuntimeError(f"v66 validator adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v67_config42_base", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


def load_module(path: Path, name: str) -> Any:
    module = types.ModuleType(name)
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def header_probe(finalizer: Any, root: Path, contract: dict[str, Any]) -> dict[str, bool]:
    root.mkdir(parents=True, exist_ok=True)
    expected = {
        finalizer.normalize(str(row["exact_hierarchy"])): int(row["width_bits"])
        for row in contract["signals"]
    }
    def emit(path: Path, wrong_width: bool) -> None:
        lines = ["$timescale 1ps $end"]
        scope_stack: list[str] = []
        for index, (hierarchy, width) in enumerate(expected.items()):
            parts = hierarchy.split(".")
            common = 0
            while common < len(scope_stack) and common < len(parts) - 1 and scope_stack[common] == parts[common]:
                common += 1
            for _ in range(len(scope_stack) - common):
                lines.append("$upscope $end")
            scope_stack = scope_stack[:common]
            for part in parts[common:-1]:
                lines.append(f"$scope module {part} $end")
                scope_stack.append(part)
            actual_width = width + 1 if wrong_width and index == 0 else width
            reference = parts[-1] + (f" [{actual_width - 1}:0]" if actual_width > 1 else "")
            lines.append(f"$var wire {actual_width} v{index} {reference} $end")
        for _ in scope_stack:
            lines.append("$upscope $end")
        lines.extend(["$enddefinitions $end", "#0", "0v0"])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    good = root / "legal_ranges.vcd"
    bad = root / "wrong_width.vcd"
    emit(good, False)
    emit(bad, True)
    good_result = finalizer.scan_vcd(good, expected)
    bad_result = finalizer.scan_vcd(bad, expected)
    return {
        "legal_terminal_ranges_exact": good_result.get("catalog_exact_set") is True,
        "wrong_width_fails_closed": bad_result.get("catalog_exact_set") is False and bool(bad_result.get("width_mismatches")),
    }


def validate_capture(package: Path, temp: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    temporal = load(package / "diagnostics/pretarget_target_capture_contract.json")
    source_receipt = load(package / "provenance/v67_current_source_identity.json")
    tb = (package / TB).read_text(encoding="utf-8")
    finalizer_path = package / FINALIZER
    finalizer_text = finalizer_path.read_text(encoding="utf-8")
    finalizer = load_module(finalizer_path, f"qadd_v67_finalize_{id(package)}")
    evaluator_path = package / "package_tools/server_tb_vcd_runtime_supervision.py"
    evaluator = load_module(evaluator_path, f"qadd_v67_evaluator_{id(package)}")
    live_text = (package / "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py").read_text(encoding="utf-8")
    source_errors: list[str] = []
    for row in contract["signals"]:
        source = ROOT / "NDP_copy01" / row["source_path"]
        leaf = row["exact_hierarchy"].rsplit(".", 1)[-1]
        if not source.is_file() or sha(source) != row["source_sha256"] or source_span(source, leaf) != row["declaration_span_sha256"]:
            source_errors.append(row["signal_id"])
    targets = re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^;]+?)\s*\)\s*;", tb)
    probes = header_probe(finalizer, temp, contract)
    p51 = load(ROOT / "fixtures/server_tb_vcd_bounded_causal_cone_v1/p51_planned_dumpoff_false_freeze.json")
    samples = p51["replay_samples"]
    authority = {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY", "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
        "helper_sha256": sha(evaluator_path), "outer_runner_consumes_only_receipt": True,
        "independent_exit_logic_absent": True,
        "replay_cases": [
            {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
        ],
    }
    phase = {
        "mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF", "helper_path": "package_tools/server_tb_vcd_runtime_supervision.py",
        "helper_sha256": sha(evaluator_path),
        "replay_cases": [
            {"case_id": "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "observed_decision": "CONTINUE"},
            {"case_id": "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "REPEATED_STOP_MARKER", "observed_decision": "FAIL_CLOSED"},
        ],
    }
    request = {
        "package_id": PACKAGE, "execution_id": "v5-probe", "attempt_id": "a0", "started": True,
        "actual_argv_sha256": "0" * 64, "catalog_sha256": "0" * 64, "candidate_matrix_sha256": "0" * 64,
        "tb_source_sha256": "0" * 64, "elaboration_sha256": "0" * 64, "samples": samples,
        "candidate_catalog_complete": True, "unresolved_xz": False, "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
        "decision_authority": authority, "dumpoff_consistency_authority": phase, "flush": {}, "process_tree": {},
    }
    p51_receipt = evaluator.evaluate(request)
    repeated_request = json.loads(json.dumps(request))
    repeated_request["samples"][-1]["stop_marker_count"] = 2
    repeated_receipt = evaluator.evaluate(repeated_request)
    snapshot = "if (!(tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active)) begin" in tb
    checks = {
        "identity_exact": contract.get("package_id") == PACKAGE and temporal.get("package_id") == PACKAGE,
        "first_round_current_source": contract["diagnostic_round"].get("round_index") == 1 and contract["diagnostic_round"].get("round_kind") == "FIRST_DIAGNOSTIC_ROUND" and contract["diagnostic_round"]["evolution"].get("predecessor") is None,
        "source_identity_recomputed": not source_errors and source_receipt.get("pass") is True and source_receipt.get("functional_rtl_modified_by_family") is False,
        "exact_64_target_set": len(targets) == 64 and set(item.strip() for item in targets) == {row["exact_hierarchy"] for row in contract["signals"]},
        "pretarget_quiet_armed": "$dumpoff;" in tb and "CODEX_TBVCD_PRETARGET_SAFETY_SNAPSHOT_V1" in tb and snapshot,
        "snapshot_cadence_exact": "(tbvcd_owner_cycles & 64'h3fff) == 0" in tb,
        "target_continuous_armed_before_marker": tb.index("$dumpon;", tb.index("if ((sig_exec_start || sig_global_exec_active)")) < tb.index("CODEX_TBVCD_TARGET_ENTRY_V2"),
        "target_marker_compatible": "CODEX_TBVCD_TARGET_ENTRY_V2" in tb and "CODEX_TBVCD_HEARTBEAT_V2" in tb,
        "no_target_sampling_or_cap": temporal["capture"].get("target_window") == "CONTINUOUS_ALL_64_SIGNALS_UNTIL_LEGAL_STOP_OR_FINAL_CLOSE" and temporal["capture"].get("byte_cap") is None and temporal["capture"].get("event_cap") is None and temporal["capture"].get("target_window_sampling") is False,
        "legal_range_normalizer_narrow": 're.sub(r"\\s+\\[[0-9]+:[0-9]+\\]$", "", normalized)' in finalizer_text,
        "width_binding_implemented": "width_mismatches" in finalizer_text and 'int(item["width_bits"])' in finalizer_text,
        "semantic_v5_contract": contract["runtime_policy"].get("planned_dumpoff_state_source") == "EXECUTION_BOUND_TB_STICKY_EVENT" and contract["runtime_policy"].get("dump_off_grace_precedes_freeze") is True and contract["runtime_policy"].get("stop_marker_policy") == "ONE_SHOT_LATCHED" and "dump_control" in contract["return_receipts"],
        "semantic_v5_tb_one_shot": "CODEX_TBVCD_PLANNED_DUMPOFF_V5" in tb and "CODEX_TBVCD_STOP_V5" in tb and "!tbvcd_stop_marker_emitted" in tb and "tbvcd_stop_marker_emitted <= 1" in tb,
        "semantic_v5_live_phase_bound": all(token in live_text for token in ("DUMPOFF_REPLAY_CASES", "planned_dumpoff_cycle", "stop_marker_count", "dumpoff_consistency_authority")),
        "canonical_evaluator_exact": evaluator_path.read_bytes() == (ROOT / "tools/server_tb_vcd_runtime_supervision.py").read_bytes(),
        "p51_false_freeze_fixed": p51_receipt.get("stop_reason") == "CAUSAL_PLATEAU" and p51_receipt.get("dump_control", {}).get("stop_marker_count") == 1,
        "repeated_stop_fails_closed": any("one-shot" in item for item in repeated_receipt.get("errors", [])),
        "dump_control_return_bound": "TB_VCD_DUMP_CONTROL_RECEIPT.json" in finalizer_text,
        **probes,
    }
    return checks, {"source_errors": source_errors, "header_probes": probes, "p51_stop_reason": p51_receipt.get("stop_reason"), "p51_dump_control": p51_receipt.get("dump_control"), "repeated_errors": repeated_receipt.get("errors", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = load_v66_validator()
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="qadd-v67-target-capture-") as raw:
        temp = Path(raw)
        package = base["safe_extract"](args.zip, temp / "package", PACKAGE)
        prior = base["safe_extract"](args.prior_zip, temp / "prior", PRIOR)
        tree_base, tree_base_errors, tree_facts = base["validate_tree"](args.tree.resolve(), prior)
        zip_base, zip_base_errors, zip_facts = base["validate_tree"](package, prior)
        tree_capture, tree_capture_facts = validate_capture(args.tree.resolve(), temp / "tree_probe")
        zip_capture, zip_capture_facts = validate_capture(package, temp / "zip_probe")
        checks = {
            "base_config42_staging": not tree_base_errors,
            "base_config42_exact_zip": not zip_base_errors,
            "target_capture_staging": all(tree_capture.values()),
            "target_capture_exact_zip": all(zip_capture.values()),
            "tree_zip_file_map_equal": base["file_map"](args.tree.resolve()) == base["file_map"](package),
            "deterministic_zip_recompute_equal": args.zip.read_bytes() == args.repeat_zip.read_bytes(),
            "v66_pending_byte_frozen": sha(args.prior_zip) == PRIOR_SHA,
        }
        errors.extend(f"tree_base:{item}" for item in tree_base_errors)
        errors.extend(f"zip_base:{item}" for item in zip_base_errors)
        errors.extend(f"tree_capture:{name}" for name, passed in tree_capture.items() if not passed)
        errors.extend(f"zip_capture:{name}" for name, passed in zip_capture.items() if not passed)
        errors.extend(name for name, passed in checks.items() if not passed)
        report = {
            "schema": "qadd-v67-config42-target-capture-exact-validation-v1",
            "package_id": PACKAGE,
            "checks": checks,
            "staging_base_checks": tree_base,
            "exact_zip_base_checks": zip_base,
            "staging_capture_checks": tree_capture,
            "exact_zip_capture_checks": zip_capture,
            "facts": {"staging_base": tree_facts, "zip_base": zip_facts, "staging_capture": tree_capture_facts, "zip_capture": zip_capture_facts},
            "package": identity(args.zip.resolve()),
            "prior_pending": identity(args.prior_zip.resolve()),
            "storage_manager_called": False,
            "server_actions_performed": [],
            "pass": not errors,
            "errors": errors,
            "claim_boundary": "Local exact package/config/source/capture validation only; no production, target-entry, root, natural/formal-D or E3-E5 claim.",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
