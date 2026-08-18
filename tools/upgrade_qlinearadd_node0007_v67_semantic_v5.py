#!/usr/bin/env python3
"""Upgrade the staged v67 package to canonical TB-VCD semantic-v5."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD_PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tgcap"
PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
OUT = ROOT / "outputs/qlinearadd_node0007_v67_cfg42_tgcap_release"
TREE = OUT / "build" / PACKAGE
TB = TREE / "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh"
LIVE = TREE / "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py"
FINALIZER = TREE / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-v66-return-target-capture-v1+tb-vcd-adaptive-v4+runtime-v3"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"semantic-v5 {label} anchor drifted")
    return text.replace(old, new, 1)


def patch_tb() -> None:
    text = TB.read_text(encoding="utf-8")
    if "CODEX_TBVCD_PLANNED_DUMPOFF_V5" in text:
        return
    text = replace_once(
        text,
        "  logic tbvcd_target_entry_seen;\n",
        "  logic tbvcd_target_entry_seen;\n  logic tbvcd_stop_marker_emitted;\n",
        "TB declaration",
    )
    text = replace_once(
        text,
        "    tbvcd_target_entry_seen = 0;\n",
        "    tbvcd_target_entry_seen = 0;\n    tbvcd_stop_marker_emitted = 0;\n",
        "TB initialization",
    )
    text = text.replace("      tbvcd_dump_off <= 0;\n", "", 1)
    old = """      if (!tbvcd_dump_off && tbvcd_plateau_cycles == TBVCD_DUMPOFF_CYCLES) begin
        $dumpoff;
        $dumpflush;
        tbvcd_dump_off <= 1;
        $display(\"CODEX_TBVCD_DUMPOFF_V2 sim_time=%0t owner_cycles=%0d strict_intersection=1\", $time, tbvcd_owner_cycles);
      end
      if (tbvcd_dump_off && tbvcd_plateau_cycles >= TBVCD_DUMPOFF_CYCLES + TBVCD_GRACE_CYCLES)
        $display(\"CODEX_TBVCD_STOP_V2 reason=CAUSAL_PLATEAU sim_time=%0t owner_cycles=%0d\", $time, tbvcd_owner_cycles); // shared evaluator remains sole outer stop authority"""
    new = """      if (!tbvcd_dump_off && tbvcd_plateau_cycles == TBVCD_DUMPOFF_CYCLES) begin
        $dumpoff;
        $dumpflush;
        tbvcd_dump_off <= 1;
        $display(\"CODEX_TBVCD_PLANNED_DUMPOFF_V5 sim_time=%0t owner_cycles=%0d vcd_timestamp_ticks=%0t sticky=1 strict_intersection=1\", $time, tbvcd_owner_cycles, $time);
      end
      if (tbvcd_dump_off && !tbvcd_stop_marker_emitted && tbvcd_plateau_cycles >= TBVCD_DUMPOFF_CYCLES + TBVCD_GRACE_CYCLES) begin
        tbvcd_stop_marker_emitted <= 1;
        $display(\"CODEX_TBVCD_STOP_V5 reason=CAUSAL_PLATEAU sim_time=%0t owner_cycles=%0d one_shot=1\", $time, tbvcd_owner_cycles); // shared evaluator remains sole outer stop authority
      end"""
    text = replace_once(text, old, new, "TB planned-dumpoff/STOP")
    TB.write_text(text, encoding="utf-8", newline="\n")


def patch_live() -> None:
    text = LIVE.read_text(encoding="utf-8")
    if "planned_dumpoff_execution_tick: int | None = None" in text and "DUMPOFF_REPLAY_CASES" in text:
        return
    if "DUMPOFF_REPLAY_CASES" not in text:
        anchor = """REPLAY_CASES = [
    {\"case_id\": \"ADVANCING_VCD_TIMESTAMP\", \"observed_decision\": \"CONTINUE\"},
    {\"case_id\": \"PLATEAU_SUSPECTED_ONLY\", \"observed_decision\": \"CONTINUE\"},
    {\"case_id\": \"PLATEAU_DUMP_OFF_PLUS_GRACE\", \"observed_decision\": \"CAUSAL_PLATEAU\"},
    {\"case_id\": \"THREE_INTERVAL_TRUE_FREEZE\", \"observed_decision\": \"SIM_TIME_FREEZE\"},
]"""
        replacement = anchor + """
DUMPOFF_REPLAY_CASES = [
    {\"case_id\": \"PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE\", \"observed_decision\": \"CONTINUE\"},
    {\"case_id\": \"PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU\", \"observed_decision\": \"CAUSAL_PLATEAU\"},
    {\"case_id\": \"REPEATED_STOP_MARKER\", \"observed_decision\": \"FAIL_CLOSED\"},
]
PLANNED_DUMPOFF = re.compile(r\"CODEX_TBVCD_PLANNED_DUMPOFF_V5\\s+sim_time=(?P<time>\\d+)\\s+owner_cycles=(?P<cycles>\\d+)\\s+vcd_timestamp_ticks=(?P<vcd>\\d+)\\s+sticky=1\")
STOP_MARKER = re.compile(r\"CODEX_TBVCD_STOP_V5\\s+reason=CAUSAL_PLATEAU\\s+sim_time=(?P<time>\\d+)\\s+owner_cycles=(?P<cycles>\\d+)\\s+one_shot=1\")"""
        text = replace_once(text, anchor, replacement, "live constants")

    scan_start = text.index("def scan_log(")
    scan_end = text.index("\ndef scan_vcd_timestamp(", scan_start)
    scan = '''def scan_log(
    path: Path, offset: int
) -> tuple[int, dict[str, Any] | None, bool, bool, int, dict[str, int] | None, list[dict[str, int]]]:
    if not path.is_file():
        return offset, None, False, False, 0, None, []
    if path.stat().st_size < offset:
        return 0, None, True, False, 0, None, []
    latest: dict[str, Any] | None = None
    target_entry = False
    pretarget_matrix_completions = 0
    planned: dict[str, int] | None = None
    stops: list[dict[str, int]] = []
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        stream.seek(offset)
        for line in stream:
            if "Matrix transfer completed" in line:
                pretarget_matrix_completions += 1
            match = HEARTBEAT.search(line)
            if match:
                latest = {
                    "display_sim_time_ticks": int(match.group("time")),
                    "owner_clock_cycles": int(match.group("cycles")),
                    "causal_progress_events": int(match.group("progress")),
                    "qualified_progress_counters": {"total": int(match.group("progress"))},
                    "causal_state_digest": match.group("state").lower(),
                    "global_progress_witness": {"count": int(match.group("global"))},
                    "unresolved_xz": match.group("xz") == "1",
                    "target_entry_observed": match.group("entry") == "1",
                }
            match = PLANNED_DUMPOFF.search(line)
            if match:
                planned = {"sim_time_ticks": int(match.group("time")), "owner_clock_cycles": int(match.group("cycles")), "vcd_timestamp_ticks": int(match.group("vcd"))}
            match = STOP_MARKER.search(line)
            if match:
                stops.append({"sim_time_ticks": int(match.group("time")), "owner_clock_cycles": int(match.group("cycles"))})
            if "CODEX_TBVCD_TARGET_ENTRY_V2" in line:
                target_entry = True
        return stream.tell(), latest, False, target_entry, pretarget_matrix_completions, planned, stops

'''
    text = text[:scan_start] + scan + text[scan_end + 1:]

    if "def phase_authority(" not in text:
        anchor = """    return module, authority


def shared_decision("""
        replacement = """    return module, authority


def phase_authority(path: Path) -> dict[str, Any]:
    return {
        \"mode\": \"SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF\",
        \"helper_path\": \"package_tools/server_tb_vcd_runtime_supervision.py\",
        \"helper_sha256\": sha256(path.resolve(strict=True)),
        \"replay_cases\": DUMPOFF_REPLAY_CASES,
    }


def shared_decision("""
        text = replace_once(text, anchor, replacement, "live phase authority")
    text = replace_once(
        text,
        "    authority: dict[str, Any],\n    args: argparse.Namespace,",
        "    authority: dict[str, Any],\n    dumpoff_authority: dict[str, Any],\n    args: argparse.Namespace,",
        "live shared_decision signature",
    )
    text = replace_once(
        text,
        '        "decision_authority": authority,\n        "archive_timestamp_receipt": None,',
        '        "decision_authority": authority,\n        "dumpoff_consistency_authority": dumpoff_authority,\n        "archive_timestamp_receipt": None,',
        "live shared request authority",
    )
    text = replace_once(
        text,
        "    evaluator, decision_authority = load_evaluator(args.runtime_evaluator)\n",
        "    evaluator, decision_authority = load_evaluator(args.runtime_evaluator)\n    dumpoff_consistency_authority = phase_authority(args.runtime_evaluator)\n",
        "live authority load",
    )
    old = """                log_offset, heartbeat, log_rotated, target_marker, preload_delta = scan_log(
                    sim_log, log_offset
                )"""
    new = """                log_offset, heartbeat, log_rotated, target_marker, preload_delta, planned_event, stop_events = scan_log(
                    sim_log, log_offset
                )"""
    text = replace_once(text, old, new, "live scan assignment")
    text = replace_once(
        text,
        "    root_exit: int | None = None\n    try:",
        "    root_exit: int | None = None\n    planned_dumpoff_cycle: int | None = None\n    planned_dumpoff_vcd_tick: int | None = None\n    planned_dumpoff_execution_tick: int | None = None\n    stop_marker_count = 0\n    try:",
        "live sticky state",
    )
    old = """                row = {
                    \"seq\": seq,
                    \"host_monotonic_ns\": time.monotonic_ns(),
                    \"wall_seconds\": wall,
                    \"sim_time_ticks\": last_vcd_tick,
                    \"appended_vcd_timestamp_ticks\": last_vcd_tick,
                    **last_heartbeat,
                    \"vcd_bytes\": size,
                    \"vcd_operational_projection_bytes\": vcd_projection,
                    \"return_projection_bytes\": return_projection,
                    \"disk_free_bytes\": free,
                    \"disk_space_ok\": disk_ok,
                    \"write_ok\": write_ok,
                    \"quota_ok\": True,
                    \"soft_warning_exceeded\": size > SOFT_WARNING,
                    \"timescale\": \"1ps\",
                }
                append_row(samples_path, row)
                append_row(heartbeat_path, row)
                samples.append(row)
                seq += 1"""
    new = """                row = {
                    \"seq\": seq,
                    \"host_monotonic_ns\": time.monotonic_ns(),
                    \"wall_seconds\": wall,
                    \"sim_time_ticks\": int(last_heartbeat.get(\"display_sim_time_ticks\", last_vcd_tick)),
                    \"appended_vcd_timestamp_ticks\": last_vcd_tick,
                    **last_heartbeat,
                    \"sim_cycles\": int(last_heartbeat.get(\"owner_clock_cycles\", 0)),
                    \"vcd_bytes\": size,
                    \"vcd_operational_projection_bytes\": vcd_projection,
                    \"return_projection_bytes\": return_projection,
                    \"disk_free_bytes\": free,
                    \"disk_space_ok\": disk_ok,
                    \"write_ok\": write_ok,
                    \"quota_ok\": True,
                    \"soft_warning_exceeded\": size > SOFT_WARNING,
                    \"timescale\": \"1ps\",
                }
                event_rows: list[dict[str, Any]] = []
                if planned_event is not None:
                    planned_dumpoff_cycle = planned_event[\"owner_clock_cycles\"]
                    planned_dumpoff_vcd_tick = planned_event[\"vcd_timestamp_ticks\"]
                    planned_dumpoff_execution_tick = planned_event[\"sim_time_ticks\"]
                    planned_row = dict(row)
                    planned_row.update({\"owner_clock_cycles\": planned_dumpoff_cycle, \"sim_cycles\": planned_dumpoff_cycle, \"sim_time_ticks\": planned_dumpoff_execution_tick, \"appended_vcd_timestamp_ticks\": planned_dumpoff_vcd_tick})
                    event_rows.append(planned_row)
                for stop_event in stop_events:
                    stop_marker_count += 1
                    stop_row = dict(row)
                    stop_row.update({\"owner_clock_cycles\": stop_event[\"owner_clock_cycles\"], \"sim_cycles\": stop_event[\"owner_clock_cycles\"], \"sim_time_ticks\": stop_event[\"sim_time_ticks\"], \"appended_vcd_timestamp_ticks\": planned_dumpoff_vcd_tick if planned_dumpoff_vcd_tick is not None else last_vcd_tick, \"stop_marker_count\": stop_marker_count})
                    event_rows.append(stop_row)
                if not event_rows:
                    event_rows = [row]
                for event_row in event_rows:
                    event_row[\"seq\"] = seq
                    if planned_dumpoff_cycle is not None:
                        event_row.update({\"planned_dumpoff\": True, \"planned_dumpoff_cycle\": planned_dumpoff_cycle, \"planned_dumpoff_vcd_timestamp_ticks\": planned_dumpoff_vcd_tick})
                    event_row.setdefault(\"stop_marker_count\", stop_marker_count)
                    append_row(samples_path, event_row)
                    append_row(heartbeat_path, event_row)
                    samples.append(event_row)
                    seq += 1"""
    text = replace_once(text, old, new, "live event rows")
    text = text.replace(
        "                    evaluator, decision_authority, args, samples\n",
        "                    evaluator, decision_authority, dumpoff_consistency_authority, args, samples\n",
    )
    text = replace_once(
        text,
        '        "decision_authority": decision_authority,\n        "outer_runner_consumed_shared_receipt_only": True,',
        '        "decision_authority": decision_authority,\n        "dumpoff_consistency_authority": dumpoff_consistency_authority,\n        "dump_control": {"planned_dumpoff": planned_dumpoff_cycle is not None, "planned_dumpoff_cycle": planned_dumpoff_cycle, "planned_dumpoff_vcd_timestamp_ticks": planned_dumpoff_vcd_tick, "planned_dumpoff_execution_sim_time_ticks": planned_dumpoff_execution_tick, "stop_marker_count": stop_marker_count, "sticky": True},\n        "outer_runner_consumed_shared_receipt_only": True,',
        "live process receipt",
    )
    text = replace_once(
        text,
        '            "target_entry_observed": last_heartbeat["target_entry_observed"],\n            "thresholds": {',
        '            "target_entry_observed": last_heartbeat["target_entry_observed"],\n            "dumpoff_consistency_authority": dumpoff_consistency_authority,\n            "dump_control": {"planned_dumpoff": planned_dumpoff_cycle is not None, "planned_dumpoff_cycle": planned_dumpoff_cycle, "planned_dumpoff_vcd_timestamp_ticks": planned_dumpoff_vcd_tick, "planned_dumpoff_execution_sim_time_ticks": planned_dumpoff_execution_tick, "stop_marker_count": stop_marker_count, "sticky": True},\n            "thresholds": {',
        "live safety receipt",
    )
    LIVE.write_text(text, encoding="utf-8", newline="\n")


def patch_finalizer() -> None:
    text = FINALIZER.read_text(encoding="utf-8")
    text = text.replace('stop = re.compile(r"CODEX_TBVCD_STOP_V[12] reason=([A-Z_]+)")', 'stop = re.compile(r"CODEX_TBVCD_STOP_V(?:1|2|5) reason=([A-Z_]+)")')
    if '"dumpoff_consistency_authority": {' not in text:
        anchor = """        \"decision_authority\": {
            \"mode\": \"SHARED_RUNTIME_EVALUATOR_ONLY\","""
        replacement = """        \"dumpoff_consistency_authority\": {
            \"mode\": \"SHARED_RUNTIME_EVALUATOR_PHASE_AWARE_DUMPOFF\",
            \"helper_path\": \"package_tools/server_tb_vcd_runtime_supervision.py\",
            \"helper_sha256\": sha_file(package / \"package_tools/server_tb_vcd_runtime_supervision.py\")[1],
            \"replay_cases\": [
                {\"case_id\": \"PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE\", \"observed_decision\": \"CONTINUE\"},
                {\"case_id\": \"PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU\", \"observed_decision\": \"CAUSAL_PLATEAU\"},
                {\"case_id\": \"REPEATED_STOP_MARKER\", \"observed_decision\": \"FAIL_CLOSED\"},
            ],
        },
        \"decision_authority\": {
            \"mode\": \"SHARED_RUNTIME_EVALUATOR_ONLY\","""
        text = replace_once(text, anchor, replacement, "finalizer phase authority")
    old = '    atomic_json(evidence / "TB_VCD_RUNTIME_RECEIPT.json", receipt)\n'
    new = '    atomic_json(evidence / "TB_VCD_RUNTIME_RECEIPT.json", receipt)\n    atomic_json(evidence / "TB_VCD_DUMP_CONTROL_RECEIPT.json", {"schema": "server-tb-vcd-dump-control-receipt-v1", "package_id": args.package_id, "execution_id": args.execution_id, "attempt_id": args.attempt_id, **receipt.get("dump_control", {})})\n'
    if "TB_VCD_DUMP_CONTROL_RECEIPT.json" not in text:
        text = replace_once(text, old, new, "finalizer dump receipt")
    if "live/final phase-aware dumpoff authority identity differs" not in text:
        anchor = """    if live_decision.get(\"decision_authority\") != request[\"decision_authority\"]:
        conjunction_errors.append(\"live/final shared decision authority identity differs\")"""
        replacement = anchor + """
    if live_decision.get(\"dumpoff_consistency_authority\") != request[\"dumpoff_consistency_authority\"]:
        conjunction_errors.append(\"live/final phase-aware dumpoff authority identity differs\")"""
        text = replace_once(text, anchor, replacement, "finalizer authority conjunction")
    FINALIZER.write_text(text, encoding="utf-8", newline="\n")


def update_contracts() -> None:
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    contract = load(contract_path)
    runtime = contract["runtime_policy"]
    runtime.update({
        "planned_dumpoff_state_source": "EXECUTION_BOUND_TB_STICKY_EVENT",
        "post_dumpoff_progress_source": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
        "dump_off_grace_precedes_freeze": True,
        "stop_marker_policy": "ONE_SHOT_LATCHED",
        "required_dumpoff_consistency_replays": [
            "PLANNED_DUMPOFF_FROZEN_VCD_GRACE_CONTINUE",
            "PLANNED_DUMPOFF_PLUS_GRACE_CAUSAL_PLATEAU",
            "REPEATED_STOP_MARKER_FAIL_CLOSED",
        ],
    })
    contract["return_receipts"]["dump_control"] = "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json"
    contract["claim_boundary"] = "Semantic-v5 two-phase planned-dumpoff/freeze and one-shot STOP plus exact 4/2 target capture; local gates make no production or E3-E5 claim."
    write(contract_path, contract)
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    member = {"archive": "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json", "required": True, "source": "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json", "source_root": "attempt"}
    if member not in request["core_entries"]:
        request["core_entries"].append(member)
    write(request_path, request)
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    root_member = f"{PACKAGE}_return/evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json"
    for item in ("evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json", root_member):
        if item not in allow["required"]:
            allow["required"].append(item)
    allow["required"] = sorted(allow["required"])
    write(allow_path, allow)
    temporal_path = TREE / "diagnostics/pretarget_target_capture_contract.json"
    temporal = load(temporal_path)
    temporal["semantic_v5"] = {
        "activation_epoch": "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3",
        "pre_dumpoff_freeze_witness": "APPENDED_VCD_TIMESTAMP",
        "post_dumpoff_progress_witness": "EXECUTION_BOUND_OWNER_CLOCK_AND_TB_TIME",
        "dump_off_grace_precedes_freeze": True,
        "stop_marker": "ONE_SHOT_LATCHED",
    }
    temporal["negative_controls"].extend([
        "planned_dumpoff_frozen_vcd_grace_continues",
        "planned_dumpoff_plus_grace_stops_once",
        "repeated_stop_marker_fails_closed",
    ])
    temporal["negative_controls"] = list(dict.fromkeys(temporal["negative_controls"]))
    write(temporal_path, temporal)


def main() -> int:
    old_tree = OUT / "build" / OLD_PACKAGE
    if not TREE.is_dir() and old_tree.is_dir():
        old_tree.rename(TREE)
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if OLD_PACKAGE in text:
                path.write_text(text.replace(OLD_PACKAGE, PACKAGE), encoding="utf-8", newline="\n")
    patch_tb()
    patch_live()
    patch_finalizer()
    shutil.copyfile(ROOT / "tools/server_tb_vcd_runtime_supervision.py", TREE / "package_tools/server_tb_vcd_runtime_supervision.py")
    shutil.copyfile(ROOT / "contracts/server_tb_vcd_planned_dumpoff_consistency_delta_v5.json", TREE / "provenance/server_tb_vcd_planned_dumpoff_consistency_delta_v5.json")
    shutil.copyfile(ROOT / "outputs/tb_vcd_planned_dumpoff_consistency_v5/canonical_activation_receipt.json", TREE / "provenance/tb_vcd_semantic_v5_activation_receipt.json")
    update_contracts()
    build_path = ROOT / "tools/build_qlinearadd_node0007_v67_cfg42_target_capture.py"
    spec = importlib.util.spec_from_file_location("qadd_v67_builder", build_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("builder cannot be loaded")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.refresh_current_source_bindings()
    builder.refresh_identity_contracts_and_manifest()
    builder.deterministic_zip(builder.ZIP)
    builder.deterministic_zip(builder.REPEAT)
    if builder.ZIP.read_bytes() != builder.REPEAT.read_bytes():
        raise RuntimeError("semantic-v5 deterministic ZIP recomputation differs")
    receipt = load(OUT / "build_receipt.json")
    receipt.update({
        "activation_epoch": EPOCH,
        "semantic_v5": True,
        "package": builder.identity(builder.ZIP),
        "repeat_package": builder.identity(builder.REPEAT),
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "pass": True,
        "errors": [],
    })
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": PACKAGE, "semantic_v5": True, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
