#!/usr/bin/env python3
"""Build the fresh v97b package-only XMR hierarchy repair successor."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix"
PREVIOUS = "r5_n4_hw_v96b_tbvcd_memtuple"
OUT = ROOT / "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
SOURCE_TREE = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_release1/build" / PREVIOUS
ANALYSIS = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_return_r1786770065727401255_2781777"
V96_BUILDER = ROOT / "tools/build_node0004_v96b_tbvcd_memtuple_successor.py"
DUPLICATE = "u_Memory_AG_Idx_Queue.u_Memory_AG_Idx_Queue."
CORRECT = "u_Memory_AG_Idx_Queue."


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load_v96() -> Any:
    spec = importlib.util.spec_from_file_location("node0004_v96_builder_for_v97", V96_BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replace_text_identities() -> None:
    for path in TREE.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".sh", ".json", ".md", ".txt", ".svh"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        updated = text.replace(PREVIOUS, PACKAGE).replace(DUPLICATE, CORRECT)
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")


def file_rows() -> list[dict[str, Any]]:
    return [
        {"bytes": path.stat().st_size, "path": path.relative_to(TREE).as_posix(), "sha256": sha256(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def replace_signal_ids(value: Any, mapping: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: replace_signal_ids(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_signal_ids(item, mapping) for item in value]
    if isinstance(value, str):
        if value in mapping:
            return mapping[value]
        # Replace embedded signal identifiers in one pass.  Sequential str.replace
        # is unsafe here because identifiers such as sig_mem_i0_raw_last and
        # sig_mem_i0_raw_last_index overlap; a later replacement could rewrite an
        # identifier that was already renamed by an earlier replacement.
        pattern = re.compile(
            r"(?<![A-Za-z0-9_])(?:"
            + "|".join(re.escape(old) for old in sorted(mapping, key=len, reverse=True))
            + r")(?![A-Za-z0-9_])"
        )
        return pattern.sub(lambda match: mapping[match.group(0)], value)
    return value


V5_EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3"
V5_RUNTIME_FIELDS = {
    "planned_dumpoff_state_source": "EXECUTION_BOUND_TB_STICKY_EVENT",
    "post_dumpoff_progress_source": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
    "dump_off_grace_precedes_freeze": True,
    "stop_marker_policy": "ONE_SHOT_LATCHED",
    "required_dumpoff_consistency_replays": [
        "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE",
        "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU",
        "REPEATED_STOP_MARKER_FAIL_CLOSED",
    ],
}


def upgrade_contract_runtime_v5(contract: dict[str, Any]) -> None:
    contract.setdefault("runtime_policy", {}).update(V5_RUNTIME_FIELDS)
    contract.setdefault("return_receipts", {})["dump_control"] = "evidence/vcd/TB_VCD_DUMP_CONTROL_RECEIPT.json"


def normalize_predecessor_chain_v5() -> None:
    ordered = [
        TREE / "provenance/v94b_current_schema_round1_contract.json",
        TREE / "provenance/v95b_predecessor_contract.json",
        TREE / "provenance/v96b_predecessor_contract.json",
    ]
    historical: list[dict[str, Any]] = []
    for index, path in enumerate(ordered):
        before = sha256(path)
        historical_copy = TREE / "provenance" / f"{path.stem}_historical_exact.json"
        shutil.copyfile(path, historical_copy)
        contract = json.loads(path.read_text(encoding="utf-8"))
        upgrade_contract_runtime_v5(contract)
        if index:
            predecessor = contract["diagnostic_round"]["evolution"]["predecessor"]
            predecessor["contract_sha256"] = sha256(ordered[index - 1])
        write(path, contract)
        historical.append(
            {
                "historical_exact_path": historical_copy.relative_to(TREE).as_posix(),
                "historical_exact_sha256": before,
                "normalized_path": path.relative_to(TREE).as_posix(),
                "normalized_sha256": sha256(path),
                "package_id": contract["package_id"],
                "round_index": contract["diagnostic_round"]["round_index"],
            }
        )
    write(
        TREE / "provenance/predecessor_runtime_v5_compatibility_receipt.json",
        {
            "schema": "node0004-predecessor-runtime-v5-compatibility-receipt-v1",
            "activation_epoch": V5_EPOCH,
            "catalog_candidate_and_source_identity_changed": False,
            "normalization_scope": ["runtime_policy v5 phase semantics", "dump_control return receipt path"],
            "contracts": historical,
            "pass": True,
            "claim_boundary": "Current-gate compatibility copy only; historical exact contracts remain byte-preserved beside each normalized lineage contract.",
        },
    )


def patch_probe_runtime_v5(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = [
        ("        reg codex_stop_reported;\n", "        reg codex_stop_reported;\n        reg codex_planned_dumpoff;\n"),
        ("          codex_suspect_reported = 0; codex_stop_reported = 0;\n", "          codex_suspect_reported = 0; codex_stop_reported = 0; codex_planned_dumpoff = 0;\n"),
        (
            "            if (codex_dump_active && !codex_stop_reported && (codex_owner_cycles & 64'h3fff) == 0) begin\n",
            "            if (codex_dump_active && !codex_planned_dumpoff &&\n"
            "                codex_owner_cycles - codex_last_progress_cycle >= CODEX_DUMPOFF_CYCLES) begin\n"
            "              $dumpoff; $dumpflush; codex_dump_active = 0; codex_planned_dumpoff = 1;\n"
            "              $display(\"CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=%0d owner_cycles=%0d\", codex_time_ps, codex_owner_cycles);\n"
            "            end\n"
            "            if (codex_planned_dumpoff && !codex_stop_reported && (codex_owner_cycles & 64'h3fff) == 0) begin\n",
        ),
        (
            "                  $dumpoff; $dumpflush; codex_dump_active = 0; codex_stop_reported = 1;\n"
            "                  $display(\"CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=%0d owner_cycles=%0d\", codex_time_ps, codex_owner_cycles);\n",
            "                  codex_stop_reported = 1;\n",
        ),
    ]
    for old, new in replacements:
        if text.count(old) != 1:
            raise RuntimeError(f"v5 probe rewrite anchor count differs: {old[:72]!r}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_supervisor_runtime_v5(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old_scan = text[text.index("def scan_log("):text.index("def scan_vcd(")]
    new_scan = '''def scan_log(path: Path, offset: int, heartbeat: dict[str, Any] | None, dump: dict[str, int] | None, stop_marker_count: int) -> tuple[int, dict[str, Any] | None, dict[str, int] | None, dict[str, Any] | None, int, bool]:
    if not path.is_file():
        return offset, heartbeat, dump, None, stop_marker_count, False
    if path.stat().st_size < offset:
        return 0, heartbeat, dump, None, stop_marker_count, True
    stop = None
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            match = HB.search(line)
            if match:
                heartbeat = {
                    "reported_sim_time_ticks": int(match.group(1)),
                    "owner_clock_cycles": int(match.group(2)),
                    "sim_cycles": int(match.group(2)),
                    "causal_progress_events": int(match.group(3)),
                    "qualified_progress_counters": {"events": int(match.group(3))},
                    "causal_state_digest": hashlib.sha256(match.group(4).encode()).hexdigest(),
                    "global_progress_witness": {"digest": hashlib.sha256(match.group(5).encode()).hexdigest()},
                    "unresolved_xz_absent": match.group(6) == "0",
                }
            match = DUMPOFF.search(line)
            if match and dump is None:
                dump = {"sim_time_ticks": int(match.group(1)), "owner_clock_cycles": int(match.group(2))}
            match = STOP.search(line)
            if match:
                stop_marker_count += 1
                stop = {"reason": match.group(1), "sim_time_ticks": int(match.group(2)), "owner_clock_cycles": int(match.group(3))}
        return stream.tell(), heartbeat, dump, stop, stop_marker_count, False


'''
    text = text.replace(old_scan, new_scan)
    start = text.index("def evaluator_request(")
    end = text.index("def select_evaluation_samples(")
    new_evaluator = '''def evaluator_request(samples: list[dict[str, Any]], authority: dict[str, Any], dumpoff_authority: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_id": "live", "execution_id": "live", "attempt_id": "live", "started": True,
        "actual_argv_sha256": "1" * 64, "catalog_sha256": "2" * 64,
        "candidate_matrix_sha256": "3" * 64, "tb_source_sha256": "4" * 64,
        "elaboration_sha256": "5" * 64, "samples": samples,
        "candidate_catalog_complete": True,
        "unresolved_xz": not bool(samples and samples[-1].get("unresolved_xz_absent") is True),
        "heartbeat_contract": {"source": "APPENDED_VCD_TIMESTAMP", "width_bits": 64, "signed": False, "cadence_cycles": 16384},
        "decision_authority": authority, "dumpoff_consistency_authority": dumpoff_authority,
        "target_entry_observed": True, "target_diagnostic_claim": False,
        "flush": {"dumpoff": False, "dumpflush": False, "closed": False},
        "process_tree": {"term_sent": False, "wait_completed": False, "kill_sent_if_needed": False, "all_reaped": False},
        "vcd_identity": None, "return_exact_set": None, "archive_timestamp_receipt": None,
        "live_diagnostics": {"downstream_state_source": "LIVE_SAME_ATTEMPT", "first_error_source": "LIVE_SAME_ATTEMPT", "stale_evidence_absent": True},
    }


def _replay_row(seq: int, cycles: int, vcd_tick: int, execution_tick: int, wall: int, **extra: Any) -> dict[str, Any]:
    row = {
        "seq": seq, "owner_clock_cycles": cycles, "sim_cycles": cycles,
        "sim_time_ticks": execution_tick, "appended_vcd_timestamp_ticks": vcd_tick,
        "wall_seconds": wall, "vcd_bytes": 1000 + cycles,
        "causal_progress_events": 1, "qualified_progress_counters": {"accept": 1},
        "causal_state_digest": "a" * 64, "global_progress_witness": {"accept": 1},
        "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True, "quota_ok": True,
    }
    row.update(extra)
    return row


def replay_cases(evaluate: Any) -> list[dict[str, str]]:
    placeholder = {
        "mode": "SHARED_RUNTIME_EVALUATOR_ONLY", "helper_path": "pending", "helper_sha256": "7" * 64,
        "outer_runner_consumes_only_receipt": True, "independent_exit_logic_absent": True,
        "replay_cases": [
            {"case_id": "ADVANCING_VCD_TIMESTAMP", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_SUSPECTED_ONLY", "observed_decision": "CONTINUE"},
            {"case_id": "PLATEAU_DUMP_OFF_PLUS_GRACE", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "THREE_INTERVAL_TRUE_FREEZE", "observed_decision": "SIM_TIME_FREEZE"},
        ],
    }
    dumpoff = {
        "mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF", "helper_path": "pending", "helper_sha256": "7" * 64,
        "replay_cases": [
            {"case_id": "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "observed_decision": "CONTINUE"},
            {"case_id": "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "REPEATED_STOP_MARKER", "observed_decision": "FAIL_CLOSED"},
        ],
    }
    vectors = {
        "ADVANCING_VCD_TIMESTAMP": [_replay_row(0, 0, 0, 0, 0), _replay_row(1, 100, 100, 100, 1)],
        "PLATEAU_SUSPECTED_ONLY": [_replay_row(0, 0, 0, 0, 0), _replay_row(1, 1048576, 1048576, 1048576, 10)],
        "PLATEAU_DUMP_OFF_PLUS_GRACE": [
            _replay_row(0, 0, 0, 0, 0),
            _replay_row(1, 4194304, 4194304, 4194304, 20, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=4194304),
            _replay_row(2, 4456448, 4194304, 4456448, 30, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=4194304, stop_marker_count=1),
        ],
        "THREE_INTERVAL_TRUE_FREEZE": [_replay_row(index, index * 100, 7, 7, index * 30) for index in range(4)],
    }
    result = []
    for case, samples in vectors.items():
        receipt = evaluate(evaluator_request(samples, placeholder, dumpoff))
        reason = receipt.get("stop_reason")
        result.append({"case_id": case, "observed_decision": "CONTINUE" if reason == "NONZERO_EXIT" else str(reason)})
    expected = {item["case_id"]: item["observed_decision"] for item in placeholder["replay_cases"]}
    if {item["case_id"]: item["observed_decision"] for item in result} != expected:
        raise RuntimeError(f"shared evaluator exact replay differs: {result}")
    return result


def dumpoff_replay_cases(evaluate: Any, authority: dict[str, Any]) -> list[dict[str, str]]:
    placeholder = {
        "mode": "SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF", "helper_path": "pending", "helper_sha256": "7" * 64,
        "replay_cases": [
            {"case_id": "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "observed_decision": "CONTINUE"},
            {"case_id": "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "observed_decision": "CAUSAL_PLATEAU"},
            {"case_id": "REPEATED_STOP_MARKER", "observed_decision": "FAIL_CLOSED"},
        ],
    }
    base = [
        _replay_row(0, 0, 0, 0, 0),
        _replay_row(1, 4194304, 7000, 7000, 10, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000),
    ]
    vectors = {
        "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE": base + [_replay_row(2, 4325376, 7000, 8000, 40, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000)],
        "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU": base + [_replay_row(2, 4456448, 7000, 9000, 70, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000, stop_marker_count=1)],
        "REPEATED_STOP_MARKER": base + [_replay_row(2, 4456448, 7000, 9000, 70, planned_dumpoff=True, planned_dumpoff_cycle=4194304, planned_dumpoff_vcd_timestamp_ticks=7000, stop_marker_count=2)],
    }
    result = []
    for case, samples in vectors.items():
        receipt = evaluate(evaluator_request(samples, authority, placeholder))
        if case == "REPEATED_STOP_MARKER":
            decision = "FAIL_CLOSED" if any("one-shot" in error for error in receipt.get("errors", [])) else str(receipt.get("stop_reason"))
        else:
            reason = receipt.get("stop_reason")
            decision = "CONTINUE" if reason == "NONZERO_EXIT" else str(reason)
        result.append({"case_id": case, "observed_decision": decision})
    expected = {item["case_id"]: item["observed_decision"] for item in placeholder["replay_cases"]}
    if {item["case_id"]: item["observed_decision"] for item in result} != expected:
        raise RuntimeError(f"phase-aware dumpoff replay differs: {result}")
    return result


def shared_decision(evaluate: Any, samples: list[dict[str, Any]], authority: dict[str, Any], dumpoff_authority: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    receipt = evaluate(evaluator_request(samples, authority, dumpoff_authority))
    reason = str(receipt.get("stop_reason"))
    if reason == "NONZERO_EXIT" and "sample stream ended without a terminal supervisor decision" in receipt.get("errors", []):
        return "CONTINUE", receipt
    return reason, receipt


'''
    text = text[:start] + new_evaluator + text[end:]
    old_select = text[text.index("def select_evaluation_samples("):text.index("def main()")]
    new_select = '''def select_evaluation_samples(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retain owner-heartbeat updates and phase-aware 30-second freeze samples."""
    selected: list[dict[str, Any]] = []
    for raw in samples:
        row = dict(raw)
        if not selected:
            selected.append(row)
            continue
        previous = selected[-1]
        cycles = int(row.get("owner_clock_cycles", row.get("sim_cycles", 0)))
        old_cycles = int(previous.get("owner_clock_cycles", previous.get("sim_cycles", 0)))
        planned = row.get("planned_dumpoff") is True or previous.get("planned_dumpoff") is True
        tick_key = "sim_time_ticks" if planned else "appended_vcd_timestamp_ticks"
        tick = int(row.get(tick_key, 0))
        old_tick = int(previous.get(tick_key, 0))
        terminal = row.get("signal") in {"HUP", "INT", "TERM"} or row.get("natural_terminal") is True or row.get("exit_code") not in (None, 0) or row.get("write_ok") is False or row.get("disk_space_ok") is False or row.get("quota_ok") is False
        freeze_sample = tick == old_tick and float(row.get("wall_seconds", 0)) - float(previous.get("wall_seconds", 0)) >= 30.0
        phase_transition = row.get("planned_dumpoff") is True and previous.get("planned_dumpoff") is not True
        stop_transition = int(row.get("stop_marker_count", 0)) != int(previous.get("stop_marker_count", 0))
        if cycles > old_cycles or freeze_sample or terminal or phase_transition or stop_transition:
            row["seq"] = len(selected)
            selected.append(row)
    return selected


'''
    text = text.replace(old_select, new_select)
    text = text.replace(
        "    subreaper = enable_subreaper()\n",
        "    dumpoff_authority = {\n"
        "        \"mode\": \"SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF\",\n"
        "        \"helper_path\": \"package_tools/server_tb_vcd_runtime_supervision.py\",\n"
        "        \"helper_sha256\": evaluator_sha,\n"
        "        \"replay_cases\": dumpoff_replay_cases(evaluator.evaluate, authority),\n"
        "    }\n\n"
        "    subreaper = enable_subreaper()\n",
    )
    text = text.replace("    dump = None\n", "    dump = None\n    stop_marker_count = 0\n", 1)
    text = text.replace(
        "log_offset, heartbeat, dump, marker, rotated = scan_log(log, log_offset, heartbeat, dump)",
        "log_offset, heartbeat, dump, marker, stop_marker_count, rotated = scan_log(log, log_offset, heartbeat, dump, stop_marker_count)",
    )
    text = text.replace(
        '                    "sim_time_ticks": 0 if last_vcd_tick is None else last_vcd_tick,\n',
        '                    "sim_time_ticks": int((heartbeat or {}).get("reported_sim_time_ticks", 0 if last_vcd_tick is None else last_vcd_tick)),\n',
    )
    text = text.replace(
        '                    "dumpoff_seen": dump is not None,\n',
        '                    "dumpoff_seen": dump is not None, "planned_dumpoff": dump is not None,\n'
        '                    "planned_dumpoff_cycle": None if dump is None else dump["owner_clock_cycles"],\n'
        '                    "planned_dumpoff_vcd_timestamp_ticks": None if dump is None else (0 if last_vcd_tick is None else last_vcd_tick),\n'
        '                    "stop_marker_count": stop_marker_count,\n',
    )
    text = text.replace(
        "decision, shared_receipt = shared_decision(evaluator.evaluate, evaluation_samples, authority)",
        "decision, shared_receipt = shared_decision(evaluator.evaluate, evaluation_samples, authority, dumpoff_authority)",
    )
    text = text.replace(
        "    if new_tick is not None:\n        last_vcd_tick = new_tick\n",
        "    if new_tick is not None:\n        last_vcd_tick = new_tick\n    if samples:\n        samples[-1][\"stop_marker_count\"] = stop_marker_count\n",
    )
    text = text.replace(
        '        "decision_authority": authority,\n        "shared_evaluator_receipt": shared_receipt,\n        "dumpoff_marker": dump, "stop_marker": marker,\n',
        '        "decision_authority": authority, "dumpoff_consistency_authority": dumpoff_authority,\n        "shared_evaluator_receipt": shared_receipt,\n        "dumpoff_marker": dump, "stop_marker": marker, "stop_marker_count": stop_marker_count,\n',
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_finalize_runtime_v5(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    anchor = "'decision_authority':proc.get('decision_authority'),'archive_timestamp_receipt'"
    if text.count(anchor) != 1:
        raise RuntimeError("v5 finalizer authority anchor differs")
    text = text.replace(anchor, "'decision_authority':proc.get('decision_authority'),'dumpoff_consistency_authority':proc.get('dumpoff_consistency_authority'),'archive_timestamp_receipt'")
    anchor = "    write(out/'VCD_RUNTIME_RECEIPT.json',receipt)\n"
    if text.count(anchor) != 1:
        raise RuntimeError("v5 finalizer receipt anchor differs")
    text = text.replace(
        anchor,
        anchor
        + "    write(out/'TB_VCD_DUMP_CONTROL_RECEIPT.json',{'schema':'node0004-tb-vcd-dump-control-receipt-v1','package_id':a.package_id,'execution_id':a.execution_id,'attempt_id':a.attempt_id,'activation_epoch':'"
        + V5_EPOCH
        + "','dump_control':receipt.get('dump_control'),'dumpoff_consistency_authority':request.get('dumpoff_consistency_authority'),'pass':not any('dumpoff' in item.lower() or 'stop marker' in item.lower() for item in receipt.get('errors',[]))})\n",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_preflight_runtime_v5(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    anchor = '        and runtime.get("archive_timestamp_binding") == "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT"\n'
    if text.count(anchor) != 1:
        raise RuntimeError("v5 preflight runtime anchor differs")
    text = text.replace(
        anchor,
        '        and runtime.get("planned_dumpoff_state_source") == "EXECUTION_BOUND_TB_STICKY_EVENT"\n'
        '        and runtime.get("post_dumpoff_progress_source") == "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME"\n'
        '        and runtime.get("dump_off_grace_precedes_freeze") is True\n'
        '        and runtime.get("stop_marker_policy") == "ONE_SHOT_LATCHED"\n'
        '        and runtime.get("required_dumpoff_consistency_replays") == ["PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE", "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU", "REPEATED_STOP_MARKER_FAIL_CLOSED"]\n'
        + anchor,
    )
    text = text.replace(
        '        "evidence/vcd/VCD_RUNTIME_RECEIPT.json",\n',
        '        "evidence/vcd/VCD_RUNTIME_RECEIPT.json",\n        "evidence/vcd/TB_VCD_DUMP_CONTROL_RECEIPT.json",\n',
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def apply_runtime_v5() -> None:
    shutil.copyfile(ROOT / "tools/server_tb_vcd_runtime_supervision.py", TREE / "package_tools/server_tb_vcd_runtime_supervision.py")
    patch_probe_runtime_v5(TREE / "tb_probe/tb_vcd_bounded_causal_cone.svh")
    patch_supervisor_runtime_v5(TREE / "package_tools/node0004_tb_vcd_process_supervisor.py")
    patch_finalize_runtime_v5(TREE / "package_tools/node0004_tb_vcd_finalize.py")
    patch_preflight_runtime_v5(TREE / "package_tools/package_release_preflight.py")


def deterministic_zip() -> None:
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as archive:
        for path in sorted(TREE.rglob("*"), key=lambda item: item.relative_to(TREE).as_posix()):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{PACKAGE}/{path.relative_to(TREE).as_posix()}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix in {".sh", ".py"} else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    if not SOURCE_TREE.is_dir() or not (ANALYSIS / "return_analysis.json").is_file():
        raise RuntimeError("v96 source tree or formal analysis absent")
    OUT.mkdir(parents=True, exist_ok=True)
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(SOURCE_TREE, TREE)
    for cache in sorted(TREE.rglob("__pycache__"), reverse=True):
        if cache.is_dir():
            shutil.rmtree(cache)
    for bytecode in TREE.rglob("*.pyc"):
        bytecode.unlink()

    predecessor_contract = json.loads((SOURCE_TREE / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
    predecessor_contract_path = TREE / "provenance/v96b_predecessor_contract.json"
    replace_text_identities()
    # Preserve the predecessor as exact v96 bytes/semantics after the fresh
    # identity rewrite; it must never be rewritten to the successor identity.
    predecessor_probe_path = TREE / "provenance/v96b_predecessor_tb_vcd_bounded_causal_cone.svh"
    shutil.copyfile(SOURCE_TREE / "tb_probe/tb_vcd_bounded_causal_cone.svh", predecessor_probe_path)
    predecessor_contract["execution"]["tb_source_path"] = "provenance/v96b_predecessor_tb_vcd_bounded_causal_cone.svh"
    predecessor_contract["execution"]["tb_source_sha256"] = sha256(predecessor_probe_path)
    write(predecessor_contract_path, predecessor_contract)

    provenance = TREE / "provenance"
    shutil.copyfile(ANALYSIS / "return_analysis.json", provenance / "v96b_return_analysis.json")
    shutil.copyfile(ANALYSIS / "rule_disposition.json", provenance / "v96b_rule_disposition.json")
    shutil.copyfile(ANALYSIS / "streaming_summary.json", provenance / "v96b_streaming_summary.json")
    shutil.copyfile(
        ANALYSIS / "package_build_failure_rule_audit_applicability.json",
        provenance / "v96b_v97_package_build_failure_rule_audit.json",
    )

    probe_path = TREE / "tb_probe/tb_vcd_bounded_causal_cone.svh"
    probe = probe_path.read_text(encoding="utf-8")
    if DUPLICATE in probe or probe.count(CORRECT) < 106:
        raise RuntimeError("v97 probe hierarchy correction is incomplete")

    contract_path = TREE / "contracts/tb_vcd_bounded_causal_cone_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    signals = contract["signals"]
    corrected = [row for row in signals if row["signal_id"].startswith("sig_mem_i") or row["signal_id"] in {"sig_mem_raw_idx_all", "sig_mem_raw_tag_all"}]
    if len(corrected) != 53 or any(DUPLICATE in row["exact_hierarchy"] for row in signals):
        raise RuntimeError("v97 contract hierarchy correction is incomplete")
    renamed = {row["signal_id"]: row["signal_id"] + "_xmrfix" for row in corrected}
    contract = replace_signal_ids(contract, renamed)
    signals = contract["signals"]
    probe = probe_path.read_text(encoding="utf-8")
    for old, new in sorted(renamed.items(), key=lambda item: len(item[0]), reverse=True):
        probe = re.sub(r"\b" + re.escape(old) + r"\b", new, probe)
    probe_path.write_text(probe, encoding="utf-8", newline="\n")
    if len({row["signal_id"] for row in signals}) != 153 or len({row["exact_hierarchy"] for row in signals}) != 153:
        raise RuntimeError("v97 signal identity is not one-to-one")

    apply_runtime_v5()
    normalize_predecessor_chain_v5()

    v96 = load_v96()
    v96.PACKAGE = PACKAGE
    v96.PREVIOUS = PREVIOUS
    v96.OUT = OUT
    v96.TREE = TREE
    v96.SOURCE_TREE = SOURCE_TREE
    v96.FINAL_ZIP = ZIP
    contract["package_id"] = PACKAGE
    upgrade_contract_runtime_v5(contract)
    contract["execution"]["tb_source_sha256"] = sha256(probe_path)
    contract["diagnostic_round"]["round_index"] = 4
    contract["diagnostic_round"]["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    contract["diagnostic_round"]["source_identity"]["catalog_source_identity_sha256"] = v96.source_identity_sha(signals)
    candidate_ids = sorted(row["candidate_id"] for row in contract["candidates"])
    signal_ids = sorted(row["signal_id"] for row in signals)
    prior_signal_by_id = {row["signal_id"]: row for row in predecessor_contract["signals"]}
    removed_ids = sorted(renamed)
    added_ids = sorted(renamed.values())
    unchanged_ids = sorted(set(prior_signal_by_id) - set(removed_ids))
    contract["diagnostic_round"]["evolution"] = {
        "added_signal_ids": added_ids,
        "candidate_preservation": {
            "closed_candidate_ids": [],
            "closure_evidence": [],
            "new_candidate_ids": [],
            "preserved_candidate_ids": candidate_ids,
        },
        "predecessor": {
            "contract_path": "provenance/v96b_predecessor_contract.json",
            "contract_sha256": sha256(predecessor_contract_path),
            "package_id": PREVIOUS,
            "pinned_rtl_tree_sha256": predecessor_contract["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
            "round_index": predecessor_contract["diagnostic_round"]["round_index"],
        },
        "removed_signal_ids": removed_ids,
        "removal_evidence": [
            {
                "affected_candidate_ids": sorted(
                    prior_signal_by_id[signal_id].get("driver_leaf_for_candidate_ids", [])
                    or [
                        "memory_input0_keep_token_or_epoch_ends_early",
                        "memory_input1_buffer_token_or_last_ends_early",
                        "memory_input2_keep_token_or_epoch_ends_early",
                        "memory_same_gotten_mask_suppresses_tenth_tuple",
                        "memory_split_fifo_or_keep_release_suppresses_tenth_tuple",
                    ]
                ),
                "confidence": "HIGH",
                "disposition": "FAMILY_ADAPTIVE_PRUNING",
                "reason": "Invalid v96 catalog identity duplicated the relative u_Memory_AG_Idx_Queue anchor and could not compile; replaced one-for-one by the _xmrfix identity with the correct actual hierarchy.",
                "signal_id": signal_id,
            }
            for signal_id in removed_ids
        ],
        "unchanged_signal_ids": unchanged_ids,
    }
    contract["package_local_xmre_controls"] = {
        "contract_probe_hierarchy_multiset_mismatch": True,
        "memory_ag_anchor_depth_mismatch": True,
        "repeated_memory_ag_instance_anchor": True,
    }
    contract["claim_boundary"] = "Fresh package-only correction of the v96 duplicated Memory_AG instance anchor. All 153 signals, candidates, config, workload, numeric, golden and functional RTL are frozen; no production or dynamic claim."
    write(contract_path, contract)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    dump_control_entry = {
        "archive": "evidence/vcd/TB_VCD_DUMP_CONTROL_RECEIPT.json",
        "required": False,
        "source": "evidence/vcd/TB_VCD_DUMP_CONTROL_RECEIPT.json",
        "source_root": "attempt",
    }
    request["core_entries"] = [
        row for row in request["core_entries"]
        if row.get("archive") != dump_control_entry["archive"]
    ] + [dump_control_entry]
    write(request_path, request)

    readme = (
        f"# {PACKAGE}\n\n"
        "Previous progress: v95 validated a one-transaction/32-unit Memory_AG metadata supply deficit. v96 attempted to distinguish the three tuple inputs but production compile stopped before simulation because all 53 new probe leaves repeated the relative u_Memory_AG_Idx_Queue anchor.\n\n"
        "Current purpose: execute the identical 153-signal tuple-leaf diagnostic after removing exactly one duplicated package-local hierarchy segment. Config, numeric, workload, golden, functional RTL, candidate matrix and target are unchanged.\n\n"
        "Run only after separate authorization:\n\n"
        f"    bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\n"
        "This package is locally built and validated only; it is not published to managed storage and has not been run.\n"
    )
    (TREE / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    v96.update_post_and_bound_contracts()
    v96.update_allowlist_and_selector()
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "current_purpose": "Run the unchanged 153-signal Memory_AG three-input tuple discriminator after correcting the duplicated package-local hierarchy anchor.",
            "activation_epoch": V5_EPOCH,
            "files": file_rows(),
            "package_id": PACKAGE,
            "package_build_failure_rule_audit": "provenance/v96b_v97_package_build_failure_rule_audit.json",
            "package_build_failure_rule_audit_triggered": True,
            "previous_version_progress": "v96 production compile reached VCS XMR resolution but simulation did not start because all 53 added leaves repeated u_Memory_AG_Idx_Queue in the package-local probe.",
            "added_signal_count": 53,
            "removed_signal_count": 53,
            "retained_predecessor_signal_count": 100,
            "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
            "schema": "node0004-v97b-tbvcd-memtuple-xmrefix-package-manifest-v1",
            "signal_count": 153,
            "source_return_analysis": "provenance/v96b_return_analysis.json",
            "status": "PACKAGE_READY_NOT_RUN",
            "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        }
    )
    write(manifest_path, manifest)
    deterministic_zip()
    write(
        OUT / "build_receipt.json",
        {
            "added_signal_count": 53,
            "corrected_hierarchy_count": 53,
            "errors": [],
            "package_id": PACKAGE,
            "pass": True,
            "removed_signal_count": 53,
            "retained_predecessor_signal_count": 100,
            "schema": "node0004-v97b-tbvcd-memtuple-xmrefix-build-v1",
            "source_return_analysis": (ANALYSIS / "return_analysis.json").relative_to(ROOT).as_posix(),
            "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
            "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            "zip": {"bytes": ZIP.stat().st_size, "path": ZIP.relative_to(ROOT).as_posix(), "sha256": sha256(ZIP)},
            "activation_epoch": V5_EPOCH,
        },
    )
    print(json.dumps({"package": PACKAGE, "signals": 153, "corrected": 53, "zip": str(ZIP)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
