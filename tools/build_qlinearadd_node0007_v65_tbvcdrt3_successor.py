#!/usr/bin/env python3
"""Build the v64-return-driven QAdd runtime-v3 TB-VCD successor locally."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"
NEW = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"
FAMILY = "qlinearadd_node0007"
EPOCH = "tb-vcd-exit-mechanism-consistency-v3+package-python-schema-runtime-v2"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE = STORAGE / "pending" / f"{OLD}.zip"
ANALYSIS = ROOT / "outputs/qlinearadd_node0007_v64_return_r1786704798234127277_2300842"
OUT = ROOT / "outputs/qlinearadd_node0007_v65_tbvcdrt3_release"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v65.svh"
LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v65.py"
FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v65.py"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def file_map(root: Path, manifest_name: str = "TEST_PACKAGE_MANIFEST.json") -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != manifest_name
    }


def safe_extract() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    TREE.parent.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v64 source ZIP CRC failure")
        roots = {PurePosixPath(row.filename).parts[0] for row in archive.infolist() if row.filename}
        if roots != {OLD}:
            raise RuntimeError(f"unexpected v64 root: {roots}")
        old_tree = TREE.parent / OLD
        for row in archive.infolist():
            pure = PurePosixPath(row.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in row.filename:
                raise RuntimeError(f"unsafe source member: {row.filename}")
            if stat.S_ISLNK(row.external_attr >> 16):
                raise RuntimeError(f"source symlink forbidden: {row.filename}")
            target = TREE.parent.joinpath(*pure.parts)
            if row.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(row))
        old_tree.rename(TREE)


def replace_identity() -> None:
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        if path.suffix.lower() in {".bin", ".pyc"}:
            continue
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        changed = text.replace(OLD, NEW).replace("QAdd v64", "QAdd v65")
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    old_tb = TREE / OLD_TB
    old_tb.rename(TREE / NEW_TB)
    for path in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(path)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def patch_tb() -> None:
    path = TREE / NEW_TB
    source = path.read_text(encoding="utf-8")
    source = source.replace(
        "codex_qadd_tb_vcd_causal_cone_v64",
        "codex_qadd_tb_vcd_causal_cone_v65",
    )
    source = source.replace(
        "  logic tbvcd_dump_off;",
        "  logic tbvcd_dump_off;\n  logic tbvcd_target_entry_seen;",
        1,
    )
    source = source.replace(
        "    tbvcd_dump_off = 0;",
        "    tbvcd_dump_off = 0;\n    tbvcd_target_entry_seen = 0;",
        1,
    )
    reset_anchor = "      tbvcd_dump_off <= 0;\n    end else if ($test$plusargs(\"CODEX_TB_VCD_ENABLE\")) begin"
    if reset_anchor not in source:
        raise RuntimeError("QAdd TB reset anchor drifted")
    source = source.replace(
        reset_anchor,
        "      tbvcd_dump_off <= 0;\n      tbvcd_target_entry_seen <= 0;\n    end else if ($test$plusargs(\"CODEX_TB_VCD_ENABLE\")) begin",
        1,
    )
    anchor = "    end else if ($test$plusargs(\"CODEX_TB_VCD_ENABLE\")) begin\n      tbvcd_owner_cycles <= tbvcd_owner_cycles + 1;"
    replacement = (
        anchor
        + "\n      if ((sig_exec_start || sig_global_exec_active) && !tbvcd_target_entry_seen) begin\n"
        + "        tbvcd_target_entry_seen <= 1;\n"
        + "        $display(\"CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=%0t owner_cycles=%0d\", $time, tbvcd_owner_cycles);\n"
        + "      end"
    )
    if anchor not in source:
        raise RuntimeError("QAdd TB owner-clock anchor drifted")
    source = source.replace(anchor, replacement, 1)
    old_heartbeat = '$display("CODEX_TB_VCD_HEARTBEAT sim_time=%0d cycles=%0d progress=%0d global=%0d state=%0h", tbvcd_sim_time_ps, tbvcd_owner_cycles, tbvcd_progress_count, sig_global_cycle, tbvcd_state_current);'
    new_heartbeat = '$display("CODEX_TBVCD_HEARTBEAT_V2 sim_time=%0d owner_cycles=%0d progress=%0d state=%0h global=%0d unresolved_xz=%0d target_entry=%0d", tbvcd_sim_time_ps, tbvcd_owner_cycles, tbvcd_progress_count, tbvcd_state_current, sig_global_cycle, $isunknown(tbvcd_state_current), tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active);'
    if old_heartbeat not in source:
        raise RuntimeError("QAdd TB heartbeat anchor drifted")
    source = source.replace(old_heartbeat, new_heartbeat, 1)
    source = source.replace(
        '$display("CODEX_TB_VCD_PLATEAU_SUSPECT cycles=%0d", tbvcd_owner_cycles);',
        '$display("CODEX_TBVCD_PLATEAU_SUSPECT_V2 sim_time=%0t owner_cycles=%0d", $time, tbvcd_owner_cycles);',
        1,
    )
    source = source.replace(
        '$display("CODEX_TB_VCD_DUMPOFF cycles=%0d strict_intersection=1", tbvcd_owner_cycles);',
        '$display("CODEX_TBVCD_DUMPOFF_V2 sim_time=%0t owner_cycles=%0d strict_intersection=1", $time, tbvcd_owner_cycles);',
        1,
    )
    fatal = '$fatal(1, "CODEX_TB_VCD_CAUSAL_PLATEAU_PARTIAL");'
    if fatal not in source:
        raise RuntimeError("QAdd TB package-local plateau fatal anchor drifted")
    source = source.replace(
        fatal,
        '$display("CODEX_TBVCD_STOP_V2 reason=CAUSAL_PLATEAU sim_time=%0t owner_cycles=%0d", $time, tbvcd_owner_cycles); // shared evaluator remains sole outer stop authority',
        1,
    )
    source = source.replace(
        '$display("CODEX_TB_VCD_NATURAL_TERMINAL cycles=%0d", tbvcd_owner_cycles);',
        '$display("CODEX_TBVCD_TERMINAL_WITNESS_V2 sim_time=%0t owner_cycles=%0d", $time, tbvcd_owner_cycles);',
        1,
    )
    source = source.replace(
        '$display("CODEX_TB_VCD_CLOSED cycles=%0d", tbvcd_owner_cycles);',
        '$display("CODEX_TBVCD_FLUSH_V2 dumpoff=1 dumpflush=1 closed=1 owner_cycles=%0d", tbvcd_owner_cycles);',
        1,
    )
    path.write_text(source, encoding="utf-8", newline="\n")


def package_live_supervisor() -> None:
    source = (ROOT / "tools/conv_native_p49_tb_vcd_live_supervision.py").read_text(encoding="utf-8")
    source = source.replace(
        ") -> tuple[int, dict[str, Any] | None, bool, bool]:",
        ") -> tuple[int, dict[str, Any] | None, bool, bool, int]:",
        1,
    )
    source = source.replace("return offset, None, False, False", "return offset, None, False, False, 0", 1)
    source = source.replace("return 0, None, True, False", "return 0, None, True, False, 0", 1)
    source = source.replace(
        "    target_entry = False\n    with path.open",
        "    target_entry = False\n    pretarget_matrix_completions = 0\n    with path.open",
        1,
    )
    source = source.replace(
        "        for line in stream:\n            match = HEARTBEAT.search(line)",
        "        for line in stream:\n            if \"Matrix transfer completed\" in line:\n                pretarget_matrix_completions += 1\n            match = HEARTBEAT.search(line)",
        1,
    )
    source = source.replace(
        "        return stream.tell(), latest, False, target_entry",
        "        return stream.tell(), latest, False, target_entry, pretarget_matrix_completions",
        1,
    )
    source = source.replace(
        "    last_vcd_tick = 0",
        "    pretarget_matrix_completions = 0\n    last_vcd_tick = 0",
        1,
    )
    source = source.replace(
        "                log_offset, heartbeat, log_rotated, target_marker = scan_log(\n                    sim_log, log_offset\n                )",
        "                log_offset, heartbeat, log_rotated, target_marker, preload_delta = scan_log(\n                    sim_log, log_offset\n                )\n                pretarget_matrix_completions += preload_delta",
        1,
    )
    source = source.replace(
        "                if target_marker:\n                    last_heartbeat[\"target_entry_observed\"] = True",
        "                if target_marker:\n                    last_heartbeat[\"target_entry_observed\"] = True\n"
        "                target_global = int(last_heartbeat.get(\"global_progress_witness\", {}).get(\"count\", 0))\n"
        "                last_heartbeat[\"global_progress_witness\"] = {\"target_count\": target_global, \"pretarget_matrix_completions\": pretarget_matrix_completions}\n"
        "                counters = dict(last_heartbeat.get(\"qualified_progress_counters\", {}))\n"
        "                counters[\"pretarget_matrix_completions\"] = pretarget_matrix_completions\n"
        "                last_heartbeat[\"qualified_progress_counters\"] = counters",
        1,
    )
    source = source.replace("conv-native-tb-vcd-direct-process-supervision-v2", "qadd-tb-vcd-direct-process-supervision-v3")
    source = source.replace(
        '"target_entry_observed": last_heartbeat["target_entry_observed"],',
        '"target_entry_observed": last_heartbeat["target_entry_observed"],\n        "pretarget_matrix_completions": pretarget_matrix_completions,',
        1,
    )
    (TREE / LIVE).write_text(source, encoding="utf-8", newline="\n")


def package_finalizer() -> None:
    source = (ROOT / "tools/conv_native_p49_tb_vcd_finalize.py").read_text(encoding="utf-8")
    source = source.replace("diagnostics/tb_vcd_causal_signal_catalog.json", "diagnostics/tb_vcd_signal_catalog.json")
    source = source.replace("diagnostics/tb_vcd_candidate_boundary_matrix.json", "diagnostics/tb_vcd_candidate_matrix.json")
    source = source.replace("conv-native", "qadd-node0007")
    source = source.replace(
        '    shutil.copyfile(matrix_path, evidence / "TB_VCD_CANDIDATE_BOUNDARY_MATRIX.json")',
        '    shutil.copyfile(matrix_path, evidence / "TB_VCD_CANDIDATE_BOUNDARY_MATRIX.json")\n'
        '    atomic_json(evidence / "TB_VCD_BREADTH_EVOLUTION.json", {"schema": "server-tb-vcd-breadth-evolution-return-v1", "package_id": args.package_id, "execution_id": args.execution_id, "attempt_id": args.attempt_id, "diagnostic_round": contract["diagnostic_round"], "source": "PACKAGE_CONTRACT_SAME_ATTEMPT"})',
        1,
    )
    (TREE / FINALIZER).write_text(source, encoding="utf-8", newline="\n")


def release_preflight_source() -> str:
    return '''#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1048576),b""): h.update(block)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument("command");parser.add_argument("--package-root",type=pathlib.Path,required=True);args=parser.parse_args()
    if args.command!="preflight": return 2
    root=args.package_root.resolve();manifest_path=root/"TEST_PACKAGE_MANIFEST.json";manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("package_id")!="''' + NEW + '''" and manifest.get("package_identity")!="''' + NEW + '''":
        print("package claim boundary differs: embedded package identity differs",file=sys.stderr);return 19
    if manifest.get("status")!="PACKAGE_READY_NOT_RUN":
        print("package claim boundary differs: embedded status is not PACKAGE_READY_NOT_RUN",file=sys.stderr);return 19
    declared=manifest.get("files",{});actual={p.relative_to(root).as_posix():{"size_bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(root.rglob("*")) if p.is_file() and p.name!="TEST_PACKAGE_MANIFEST.json"}
    if declared!=actual:
        print("package claim boundary differs: manifest exact set differs",file=sys.stderr);return 19
    print(json.dumps({"package_id":"''' + NEW + '''","status":"PACKAGE_READY_NOT_RUN","pass":True},sort_keys=True));return 0

if __name__=="__main__": raise SystemExit(main())
'''


def patch_runner() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    runner = path.read_text(encoding="utf-8")
    runner = runner.replace(OLD_TB, NEW_TB)
    runner = runner.replace(
        "supervisor_heartbeat=\nactual_argv_json=",
        "supervisor_heartbeat=\nsafety_receipt=\ndecision_receipt=\nactual_argv_json=",
        1,
    )
    runner = runner.replace(
        'supervisor_heartbeat="$evidence_root/vcd/supervisor_samples.jsonl"',
        'supervisor_heartbeat="$evidence_root/vcd/supervisor_samples.jsonl"\n'
        'safety_receipt="$evidence_root/TB_VCD_LIVE_SAFETY_RECEIPT.json"\n'
        'decision_receipt="$evidence_root/TB_VCD_LIVE_DECISION_RECEIPT.json"\n'
        '# Exact returned target-entry member: TB_VCD_TARGET_ENTRY_RECEIPT.json',
        1,
    )
    start = runner.index('    python3 "$package_root/package_tools/qlinearadd_node0007_tb_vcd_finalize_v63.py"')
    end = runner.index("    diagnostic_status=$?", start)
    final_call = (
        f'    python3 "$package_root/{FINALIZER}" \\\n'
        '      --package-root "$package_root" --attempt-root "$run_root" --evidence-root "$evidence_root" \\\n'
        '      --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" \\\n'
        '      --actual-root "$server_root" --published-root "$server_root" --compile-exit "$compile_status" \\\n'
        '      --sim-exit "$simulation_status" --signal "$signal_name" --vcd "$vcd_path" --sim-log "$run_root/sim.log" \\\n'
        '      --samples "$supervisor_heartbeat" --process-receipt "$process_receipt" --safety-receipt "$safety_receipt"\n'
    )
    runner = runner[:start] + final_call + runner[end:]
    old_live_start = runner.index('DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/qlinearadd_node0007_tb_vcd_guarded_supervisor_v63.py"')
    old_live_end = runner.index(" &\nsim_pid=$!", old_live_start)
    live_call = (
        f'DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/{LIVE}" '
        '--package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" '
        '--attempt-root "$run_root" --cwd "$server_root" '
        '--runtime-evaluator "$package_root/package_tools/server_tb_vcd_runtime_supervision.py" '
        '--decision-receipt "$decision_receipt" --sim-log "$run_root/sim.log" --vcd "$vcd_path" '
        '--samples "$supervisor_heartbeat" --heartbeat-output "$evidence_root/SIM_TIME_HEARTBEAT.jsonl" '
        '--process-receipt "$process_receipt" --safety-receipt "$safety_receipt" '
        '-- "$simv" "${sim_args[@]}"'
    )
    runner = runner[:old_live_start] + live_call + runner[old_live_end:]
    runner = runner.replace("CODEX_TB_VCD_NATURAL_TERMINAL", "CODEX_TBVCD_TERMINAL_WITNESS_V2")
    runner = runner.replace(
        "re.search(r'(?i)error|fatal|no rule to make target|not found|syntax error',r)",
        "re.search(r'(?i)(?:Error-\\[|^Error:|^Fatal:|no rule to make target|command not found|syntax error)',r)",
        1,
    )
    path.write_text(runner, encoding="utf-8", newline="\n")


def update_contracts() -> None:
    tb_path = TREE / NEW_TB
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    contract["package_id"] = NEW
    contract["execution"]["tb_source_path"] = NEW_TB
    contract["execution"]["tb_source_sha256"] = sha(tb_path)
    signal_ids = [item["signal_id"] for item in contract["signals"]]
    contract["execution"]["dump_targeting"] = {
        "mode": "EXACT_CATALOG_SIGNALS",
        "module_scope_dump": False,
        "dumpvars_depth": 0,
        "signal_ids": signal_ids,
    }
    candidates = contract["candidates"]
    for index, candidate in enumerate(candidates):
        candidate["priority"] = "HIGH" if index == 0 else "MEDIUM"
    driver_map = {
        "sig_valid_buf": [candidates[0]["candidate_id"]],
        "sig_arm_r_bank_ready": [candidates[0]["candidate_id"]],
        "sig_mrm_r_bank_ready": [candidates[0]["candidate_id"]],
    }
    for signal in contract["signals"]:
        bound = driver_map.get(signal["signal_id"], [])
        signal["driver_leaf_for_candidate_ids"] = bound
        signal["driver_depth_edges"] = 0 if bound else None
    source_rows = [
        {
            "signal_id": item["signal_id"],
            "exact_hierarchy": item["exact_hierarchy"],
            "width_bits": item["width_bits"],
            "source_path": item["source_path"],
            "source_sha256": item["source_sha256"],
            "declaration_span_sha256": item["declaration_span_sha256"],
        }
        for item in contract["signals"]
    ]
    source_rows.sort(key=lambda item: item["signal_id"])
    catalog_semantic_sha = hashlib.sha256(
        json.dumps(source_rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    pinned_rtl_sha = hashlib.sha256(
        json.dumps(
            sorted({(item["source_path"], item["source_sha256"]) for item in contract["signals"]}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    baseline_path = TREE / "provenance/qadd_v64_round3_breadth_baseline.json"
    baseline = {
        "schema": "server-tb-vcd-family-round-breadth-baseline-v1",
        "family": FAMILY,
        "package_id": OLD,
        "round_index": 3,
        "signal_count": 64,
        "direct_driver_leaf_count": 0,
        "candidate_count": 7,
        "boundary_count": 4,
        "pinned_rtl_tree_sha256": pinned_rtl_sha,
        "machine_check_exit": 0,
        "claim_boundary": "Exact current-family pre-v4 QAdd round-three breadth reference only; no retroactive v64 revalidation or DUT claim.",
    }
    write(baseline_path, baseline)
    contract["diagnostic_round"] = {
        "round_index": 1,
        "round_kind": "FIRST_DIAGNOSTIC_ROUND",
        "breadth_baseline": {
            "mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE",
            "reference_round_index": 3,
            "reference_package_id": OLD,
            "receipt_path": baseline_path.relative_to(TREE).as_posix(),
            "receipt_sha256": sha(baseline_path),
            "reference_signal_count": 64,
            "reference_direct_driver_leaf_count": 0,
            "reference_candidate_count": 7,
            "reference_boundary_count": 4,
            "reasonable_signal_count_range": {"minimum": 48, "maximum": 96},
            "deviation": {"relation": "WITHIN_REFERENCE_RANGE", "explanation": None, "acknowledged": False},
        },
        "source_identity": {
            "pinned_rtl_tree_sha256": pinned_rtl_sha,
            "catalog_source_identity_sha256": catalog_semantic_sha,
        },
        "coverage_gaps": [],
        "evolution": {
            "predecessor": None,
            "added_signal_ids": signal_ids,
            "removed_signal_ids": [],
            "unchanged_signal_ids": [],
            "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": [],
                "closed_candidate_ids": [],
                "new_candidate_ids": [item["candidate_id"] for item in candidates],
                "closure_evidence": [],
            },
        },
    }
    contract["return_receipts"]["breadth_evolution"] = "evidence/TB_VCD_BREADTH_EVOLUTION.json"
    contract["first_fresh_controls"] = {
        "required_for_family_epoch": True,
        "clean_exact_zip_revalidation": True,
        "negative_controls": {
            "missing_soft_reference_receipt": True,
            "deviation_without_explanation": True,
            "low_confidence_removal": True,
            "add_remove_diff_mismatch": True,
            "candidate_loss": True,
            "source_identity_drift": True,
            "size_or_stop_protection_weakened": True,
        },
    }
    contract["runtime_policy"].update(
        {
            "heartbeat_source": "APPENDED_VCD_TIMESTAMP",
            "heartbeat_width_bits": 64,
            "heartbeat_signed": False,
            "heartbeat_cadence_cycles": 16384,
            "decision_authority": "SHARED_RUNTIME_EVALUATOR_ONLY",
            "outer_runner_independent_exit_logic": False,
            "required_replay_cases": [
                "ADVANCING_VCD_TIMESTAMP",
                "PLATEAU_SUSPECTED_ONLY",
                "PLATEAU_DUMP_OFF_PLUS_GRACE",
                "THREE_INTERVAL_TRUE_FREEZE",
            ],
            "archive_timestamp_binding": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT",
        }
    )
    contract["claim_boundary"] = "v64-return-driven runtime-v3 exact-signal TB-VCD transport only; local gates do not prove production v65 execution or a DUT outcome."
    write(contract_path, contract)

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner_sha = sha(runner_path)
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path)
    resilience["package_id"] = NEW
    resilience["runner_sha256"] = runner_sha
    resilience.pop("claim_boundary", None)
    resilience["package_owned_variables"] = sorted(
        set(resilience.get("package_owned_variables", []))
        | {"safety_receipt", "decision_receipt"}
    )
    resilience["return_allowlist_tokens"] = sorted(
        set(resilience.get("return_allowlist_tokens", []))
        | {"TB_VCD_LIVE_DECISION_RECEIPT.json", "TB_VCD_LIVE_SAFETY_RECEIPT.json", "TB_VCD_TARGET_ENTRY_RECEIPT.json"}
    )
    write(resilience_path, resilience)

    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    layout["package_id"] = NEW
    layout["install_name"] = NEW
    if "runner_bindings" in layout and isinstance(layout["runner_bindings"], dict):
        layout["runner_bindings"]["runner_sha256"] = runner_sha
    write(layout_path, layout)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    additions = [
        "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json",
        "evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json",
        "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json",
        "evidence/TB_VCD_IDENTITY.json",
        "evidence/TB_VCD_STOP_RECEIPT.json",
        "evidence/TB_VCD_BREADTH_EVOLUTION.json",
    ]
    existing = {row.get("archive") for row in request["core_entries"]}
    for member in additions:
        if member not in existing:
            request["core_entries"].append({"source_root": "attempt", "source": member, "archive": member, "required": True})
    write(request_path, request)
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post["package_id"] = NEW
    post["request_sha256"] = sha(request_path)
    post["runner_sha256"] = runner_sha
    post["helper_sha256"] = sha(TREE / "package_tools/server_post_sim_return.py")
    write(post_path, post)

    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = NEW
    selector["vcd_contract_sha256"] = sha(contract_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | set(additions))
    write(selector_path, selector)

    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    allow["package_id"] = NEW
    root = f"{NEW}_return/"
    allow["required"] = sorted(
        set(allow.get("required", []))
        | {root + row["archive"] for row in request["core_entries"] if row.get("required") is True}
    )
    write(allow_path, allow)


def update_provenance_and_manifest() -> None:
    provenance = TREE / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ANALYSIS / "formal_return_analysis.json", provenance / "v64_formal_return_analysis.json")
    shutil.copyfile(
        ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json",
        provenance / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json",
    )
    write(
        provenance / "v64_to_v65_runtime_v3.json",
        {
            "schema": "qadd-v64-to-v65-runtime-v3-v1",
            "source_package": OLD,
            "package_id": NEW,
            "classification": "PACKAGE_LOCAL_RUNTIME_SUPERVISOR_FINALIZER_RETURN_GATE_DEFECT",
            "previous_version_progress": "v64 production compile passed and 24 pre-target matrix transfers completed, but slice04 preload hit the wall ceiling before target entry; split stale finalization and incomplete reap made the return partial.",
            "current_version_purpose": "Preserve the v64 identity repair, 41-role/64-signal Buffer5/ping-pong causal cone and tail-round target while applying current shared-evaluator-only exit-v3, pre-target progress binding, quiescent archive identity and package Python/schema runtime-v2.",
            "changed_surfaces": ["fresh identity", "package-local TB runtime markers", "runtime supervisor", "return finalizer", "release preflight"],
            "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional RTL", "tail-round target", "64 source-bound signals", "candidate matrix"],
            "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "server_actions_performed": [],
        },
    )
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["package_id"] = NEW
    manifest["package_identity"] = NEW
    manifest["install_name"] = NEW
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["activation_epoch"] = EPOCH
    manifest["previous_version_progress"] = "v64 compile passed and pre-target preload advanced through slice04 read burst 227, but target entry was not reached before a package-local exit/finalization escape."
    manifest["current_version_purpose"] = "Preserve the v64 Buffer5 selected-port required-lane target under current runtime-v3 and package Python/schema runtime-v2."
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest = load(manifest_path)
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)


def deterministic_zip(target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            name = f"{NEW}/{path.relative_to(TREE).as_posix()}"
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def frozen_receipt() -> dict[str, Any]:
    with zipfile.ZipFile(SOURCE) as archive:
        old_members = {
            PurePosixPath(row.filename).relative_to(OLD).as_posix(): hashlib.sha256(archive.read(row)).hexdigest()
            for row in archive.infolist()
            if not row.is_dir()
            and PurePosixPath(row.filename).relative_to(OLD).as_posix().startswith(("workload/runtime/install/op_tail_round/", "validation/golden/"))
        }
    new_members = {
        path.relative_to(TREE).as_posix(): sha(path)
        for path in TREE.rglob("*")
        if path.is_file() and path.relative_to(TREE).as_posix().startswith(("workload/runtime/install/op_tail_round/", "validation/golden/"))
    }
    return {
        "schema": "qadd-v65-frozen-surface-receipt-v1",
        "package_id": NEW,
        "exact_matrix_and_golden_equal": old_members == new_members,
        "old_member_count": len(old_members),
        "new_member_count": len(new_members),
        "functional_rtl_absent": not (TREE / "rtl").exists(),
        "pass": old_members == new_members and not (TREE / "rtl").exists(),
        "errors": [] if old_members == new_members else ["matrix/golden payload drift"],
    }


def main() -> int:
    if not SOURCE.is_file():
        raise RuntimeError("protected v64 pending package is absent")
    analysis = load(ANALYSIS / "formal_return_analysis.json")
    audit = load(ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json")
    if analysis.get("successor_justified") is not True or audit.get("disposition") != "RULE_CONFIRMATION_NO_CHANGE":
        raise RuntimeError("formal analysis/audit does not authorize v65")
    safe_extract()
    replace_identity()
    (TREE / "package_tools/qlinearadd_node0007_tb_vcd_guarded_supervisor_v63.py").unlink(missing_ok=True)
    (TREE / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v63.py").unlink(missing_ok=True)
    shutil.copyfile(ROOT / "tools/server_tb_vcd_runtime_supervision.py", TREE / "package_tools/server_tb_vcd_runtime_supervision.py")
    shutil.copyfile(ROOT / "tools/server_post_sim_return.py", TREE / "package_tools/server_post_sim_return.py")
    shutil.copyfile(ROOT / "tools/server_package_runtime_layout.py", TREE / "package_tools/server_package_runtime_layout.py")
    (TREE / "package_tools/package_release_preflight.py").write_text(release_preflight_source(), encoding="utf-8", newline="\n")
    package_live_supervisor()
    package_finalizer()
    patch_tb()
    patch_runner()
    for path in (TREE / "PREPARE_AND_RUN.sh", TREE / LIVE, TREE / FINALIZER, TREE / "package_tools/package_release_preflight.py"):
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    update_contracts()
    update_provenance_and_manifest()
    frozen = frozen_receipt()
    write(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface differs: {frozen['errors']}")
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic exact ZIP recomputation differs")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("final ZIP CRC failed")
    receipt = {
        "schema": "qadd-v65-tbvcd-runtime-v3-build-v1",
        "package_id": NEW,
        "family": FAMILY,
        "activation_epoch": EPOCH,
        "source_v64_pending": identity(SOURCE),
        "formal_return_analysis": identity(ANALYSIS / "formal_return_analysis.json"),
        "package_build_failure_rule_audit": identity(ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json"),
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "zip": identity(ZIP),
        "repeat_zip": identity(REPEAT),
        "deterministic_recompute": True,
        "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone"],
        "server_actions_performed": [],
        "pass": True,
        "errors": [],
    }
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "zip": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
