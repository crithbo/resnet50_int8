#!/usr/bin/env python3
"""Build QAdd v68 with a real pretarget VCD tick and bounded PID ownership.

This is the audited third package attempt.  It preserves the exact v67
functional/config payload and changes only fresh identity plus package-local
TB/runtime/return surfaces admitted by qadd-pretarget-safety-pulse-v1.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
NEW = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"
OLD_SHA = "dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740"
GOOD_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-pretarget-safety-pulse-v1+runtime-v3-pid-identity"
SOURCE_OUT = ROOT / "outputs/qlinearadd_node0007_v67_cfg42_tgcap_release"
SOURCE_TREE = SOURCE_OUT / "build" / OLD
SOURCE_RELEASE_ZIP = SOURCE_OUT / f"{OLD}.zip"
SOURCE_PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
OUT = ROOT / "outputs/qlinearadd_node0007_v68_cfg42_tick_release"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v67.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v68.svh"
OLD_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v67.py"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v68.py"
OLD_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v67.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v68.py"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v67_return_r1786793338560402996_2911236"
ANALYSIS = ANALYSIS_OUT / "formal_return_analysis.json"
AUDIT = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
APPLICABILITY = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json"


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


def subtree_map(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {path.relative_to(root).as_posix(): sha(path) for path in sorted(root.rglob("*")) if path.is_file()}


def identity_normalized_json(path: Path, package_id: str) -> Any:
    """Compare frozen semantics while allowing only the mandatory fresh identity."""
    return json.loads(json.dumps(load(path), ensure_ascii=False).replace(package_id, "<PACKAGE_ID>"))


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            member = f"{NEW}/{path.relative_to(TREE).as_posix()}"
            info = zipfile.ZipInfo(member, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def replace_active_identity() -> None:
    if OUT.exists():
        raise RuntimeError(f"fresh output already exists: {OUT}")
    shutil.copytree(SOURCE_TREE, TREE)
    preserved = {
        "provenance/v66_formal_return_analysis.json",
        "provenance/v66_rule_gap_audit.json",
        "provenance/v66_pretarget_dynamic_summary.json",
        "provenance/v66_to_v67_target_capture.json",
        "provenance/v66_server_tb_vcd_bounded_causal_cone_contract.json",
    }
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        relative = path.relative_to(TREE).as_posix()
        if relative in preserved or path.suffix.lower() in {".bin", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        changed = text.replace(OLD, NEW)
        changed = changed.replace("QAdd v67", "QAdd v68")
        changed = changed.replace("qlinearadd_node0007_tb_vcd_causal_cone_v67", "qlinearadd_node0007_tb_vcd_causal_cone_v68")
        changed = changed.replace("codex_qadd_tb_vcd_causal_cone_v67", "codex_qadd_tb_vcd_causal_cone_v68")
        changed = changed.replace("qlinearadd_node0007_tb_vcd_live_supervision_v67.py", "qlinearadd_node0007_tb_vcd_live_supervision_v68.py")
        changed = changed.replace("qlinearadd_node0007_tb_vcd_finalize_v67.py", "qlinearadd_node0007_tb_vcd_finalize_v68.py")
        changed = changed.replace("qadd-v67", "qadd-v68")
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    (TREE / OLD_TB).rename(TREE / NEW_TB)
    (TREE / OLD_LIVE).rename(TREE / NEW_LIVE)
    (TREE / OLD_FINALIZER).rename(TREE / NEW_FINALIZER)
    source_receipt = TREE / "provenance/v67_current_source_identity.json"
    if source_receipt.is_file():
        source_receipt.rename(TREE / "provenance/v68_current_source_identity.json")
    for path in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(path)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def patch_tb() -> None:
    path = TREE / NEW_TB
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "  logic tbvcd_dump_off;\n  logic tbvcd_target_entry_seen;",
        "  logic tbvcd_dump_off;\n  logic tbvcd_pretarget_pulse_open;\n  logic tbvcd_target_entry_seen;",
        1,
    )
    text = text.replace(
        "    tbvcd_dump_off = 0;\n    tbvcd_target_entry_seen = 0;",
        "    tbvcd_dump_off = 0;\n    tbvcd_pretarget_pulse_open = 0;\n    tbvcd_target_entry_seen = 0;",
        1,
    )
    text = text.replace(
        "      tbvcd_output_count <= 0;\n      tbvcd_target_entry_seen <= 0;",
        "      tbvcd_output_count <= 0;\n      tbvcd_pretarget_pulse_open <= 0;\n      tbvcd_target_entry_seen <= 0;",
        1,
    )
    target_old = """      if ((sig_exec_start || sig_global_exec_active) && !tbvcd_target_entry_seen) begin
        // Full 64-signal causal-cone capture is continuous from this boundary.
        $dumpon;
        $dumpflush;
        tbvcd_target_entry_seen <= 1;
        $display("CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=%0t owner_cycles=%0d full_continuous_capture=1", $time, tbvcd_owner_cycles);
      end"""
    target_new = """      if (tbvcd_pretarget_pulse_open && !(sig_exec_start || sig_global_exec_active || tbvcd_target_entry_seen)) begin
        // Close only on a later owner-clock edge: the pulse must advance VCD time.
        $dumpflush;
        $dumpoff;
        tbvcd_pretarget_pulse_open <= 0;
        $display("CODEX_TBVCD_PRETARGET_SAFETY_PULSE_CLOSE_V1 sim_time=%0t owner_cycles=%0d spanned_owner_tick=1", $time, tbvcd_owner_cycles);
      end
      if ((sig_exec_start || sig_global_exec_active) && !tbvcd_target_entry_seen) begin
        // Full 64-signal causal-cone capture is continuous from this boundary.
        $dumpon;
        $dumpflush;
        tbvcd_pretarget_pulse_open <= 0;
        tbvcd_target_entry_seen <= 1;
        $display("CODEX_TBVCD_TARGET_ENTRY_V2 sim_time=%0t owner_cycles=%0d full_continuous_capture=1", $time, tbvcd_owner_cycles);
      end"""
    if target_old not in text:
        raise RuntimeError("target-entry TB anchor drifted")
    text = text.replace(target_old, target_new, 1)
    snapshot_old = """        if (!(tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active)) begin
          // Zero-duration safety snapshot only. It is excluded from functional evidence.
          $dumpon;
          $dumpflush;
          $dumpoff;
          $display("CODEX_TBVCD_PRETARGET_SAFETY_SNAPSHOT_V1 sim_time=%0t owner_cycles=%0d", $time, tbvcd_owner_cycles);
        end else begin
          $dumpflush;
        end"""
    snapshot_new = """        if (!(tbvcd_target_entry_seen || sig_exec_start || sig_global_exec_active) && !tbvcd_pretarget_pulse_open) begin
          // Transport-only safety pulse. It remains open until the next owner edge.
          $dumpon;
          $dumpflush;
          tbvcd_pretarget_pulse_open <= 1;
          $display("CODEX_TBVCD_PRETARGET_SAFETY_PULSE_OPEN_V1 sim_time=%0t owner_cycles=%0d close=NEXT_OWNER_EDGE", $time, tbvcd_owner_cycles);
        end else begin
          $dumpflush;
        end"""
    if snapshot_old not in text:
        raise RuntimeError("pretarget snapshot TB anchor drifted")
    text = text.replace(snapshot_old, snapshot_new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_live_supervisor() -> None:
    path = TREE / NEW_LIVE
    text = path.read_text(encoding="utf-8")
    process_old = """        rows.append(
            {
                "pid": pid,
                "ppid": ppid,
                "pgid": pgid,
                "sid": sid,
                "stat": fields[4],
                "comm": fields[5],
            }
        )"""
    process_new = """        start_time = None
        try:
            tail = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
            start_time = int(tail[19])
        except (OSError, ValueError, IndexError):
            pass
        rows.append(
            {
                "pid": pid,
                "ppid": ppid,
                "pgid": pgid,
                "sid": sid,
                "stat": fields[4],
                "comm": fields[5],
                "start_time_ticks": start_time,
            }
        )"""
    if process_old not in text:
        raise RuntimeError("process row anchor drifted")
    text = text.replace(process_old, process_new, 1)
    owned_old = """def owned(root_pid: int, pgid: int, known: set[int]) -> list[dict[str, Any]]:
    rows = process_rows()
    by_pid = {row["pid"]: row for row in rows}
    children: dict[int, list[int]] = {}
    for row in rows:
        children.setdefault(row["ppid"], []).append(row["pid"])
    closure = set(known)
    pending = list(closure)
    while pending:
        parent = pending.pop()
        for child in children.get(parent, []):
            if child not in closure:
                closure.add(child)
                pending.append(child)
    group_still_owned = any(by_pid[pid]["pgid"] == pgid for pid in known if pid in by_pid)
    if group_still_owned:
        closure.update(row["pid"] for row in rows if row["pgid"] == pgid)
    closure.update(row["pid"] for row in rows if row["ppid"] == os.getpid())
    return [by_pid[pid] for pid in sorted(closure) if pid in by_pid and pid != os.getpid()]"""
    owned_new = """def remember(known: dict[int, int | None], row: dict[str, Any]) -> None:
    known[row["pid"]] = row.get("start_time_ticks")


def owned(root_pid: int, pgid: int, known: dict[int, int | None]) -> list[dict[str, Any]]:
    rows = process_rows()
    by_pid = {row["pid"]: row for row in rows}
    for pid, start_time in list(known.items()):
        row = by_pid.get(pid)
        if row is None or row.get("start_time_ticks") != start_time:
            known.pop(pid, None)
    children: dict[int, list[int]] = {}
    for row in rows:
        children.setdefault(row["ppid"], []).append(row["pid"])
    closure = {root_pid, *known}
    pending = list(closure)
    while pending:
        parent = pending.pop()
        for child in children.get(parent, []):
            if child not in closure:
                closure.add(child)
                pending.append(child)
    closure.update(row["pid"] for row in rows if row["pgid"] == pgid)
    closure.update(row["pid"] for row in rows if row["ppid"] == os.getpid())
    result = []
    for pid in sorted(closure):
        row = by_pid.get(pid)
        if row is None or pid == os.getpid():
            continue
        if str(row.get("stat", "")).startswith("Z") and row.get("ppid") != os.getpid():
            continue
        result.append(row)
    return result"""
    if owned_old not in text:
        raise RuntimeError("owned-process anchor drifted")
    text = text.replace(owned_old, owned_new, 1)
    text = text.replace("known: set[int]", "known: dict[int, int | None]")
    text = text.replace("        known.add(row[\"pid\"])", "        remember(known, row)")
    text = text.replace("            known.discard(pid)", "            known.pop(pid, None)")
    text = text.replace("    known: set[int] = {process.pid}", "    known: dict[int, int | None] = {}\n    for row in process_rows():\n        if row[\"pid\"] == process.pid:\n            remember(known, row)")
    text = text.replace("                known.add(row[\"pid\"])", "                remember(known, row)")
    loop_old = """        remaining = owned(process.pid, pgid, known)
        while remaining and time.monotonic() < reap_deadline:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
            reaped.extend(reap(min(reap_deadline, time.monotonic() + 1.0), known))
            remaining = owned(process.pid, pgid, known)"""
    loop_new = """        remaining = owned(process.pid, pgid, known)
        if remaining:
            actions.append(signal_owned(process.pid, pgid, known, signal.SIGKILL))
        while remaining and time.monotonic() < reap_deadline:
            reaped.extend(reap(min(reap_deadline, time.monotonic() + 1.0), known))
            time.sleep(0.1)
            remaining = owned(process.pid, pgid, known)"""
    if loop_old not in text:
        raise RuntimeError("bounded final reap anchor drifted")
    text = text.replace(loop_old, loop_new, 1)
    text = text.replace(
        '        "owned_pids_remaining": [row["pid"] for row in remaining],',
        '        "owned_pids_remaining": [row["pid"] for row in remaining],\n        "owned_process_identity": "PID_PLUS_PROC_START_TIME_TICKS",',
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def bind_analysis_and_contracts() -> None:
    provenance = TREE / "provenance"
    shutil.copyfile(ANALYSIS, provenance / "v67_formal_return_analysis.json")
    shutil.copyfile(AUDIT, provenance / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")
    shutil.copyfile(APPLICABILITY, provenance / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json")

    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    predecessor = (SOURCE_TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json").read_bytes()
    predecessor_path = provenance / "v67_server_tb_vcd_bounded_causal_cone_contract.json"
    predecessor_path.write_bytes(predecessor)
    shutil.copyfile(SOURCE_TREE / OLD_TB, TREE / OLD_TB)
    vcd = load(vcd_path)
    signal_ids = [row["signal_id"] for row in vcd["signals"]]
    candidate_ids = [row["candidate_id"] for row in vcd["candidates"]]
    vcd["package_id"] = NEW
    vcd["diagnostic_round"]["round_index"] = 2
    vcd["diagnostic_round"]["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    vcd["diagnostic_round"]["evolution"] = {
        "predecessor": {
            "package_id": OLD,
            "round_index": 1,
            "contract_path": "provenance/v67_server_tb_vcd_bounded_causal_cone_contract.json",
            "contract_sha256": hashlib.sha256(predecessor).hexdigest(),
            "pinned_rtl_tree_sha256": vcd["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
        },
        "added_signal_ids": [],
        "removed_signal_ids": [],
        "unchanged_signal_ids": signal_ids,
        "removal_evidence": [],
        "candidate_preservation": {
            "preserved_candidate_ids": candidate_ids,
            "closed_candidate_ids": [],
            "new_candidate_ids": [],
            "closure_evidence": [],
        },
    }
    vcd["execution"]["tb_source_path"] = NEW_TB
    vcd["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    vcd["claim_boundary"] = "Pretarget safety pulses are transport-only and each spans an owner-clock edge; full 64-signal capture is continuous from target entry. Local gates make no production or terminal claim."
    write(vcd_path, vcd)

    pulse = {
        "schema": "qadd-pretarget-safety-pulse-contract-v1",
        "package_id": NEW,
        "predecessor_package_id": OLD,
        "exemption_id": "qadd-pretarget-safety-pulse-v1",
        "audit": identity(AUDIT),
        "pulse": {
            "cadence_owner_cycles": 16384,
            "open_marker": "CODEX_TBVCD_PRETARGET_SAFETY_PULSE_OPEN_V1",
            "close_marker": "CODEX_TBVCD_PRETARGET_SAFETY_PULSE_CLOSE_V1",
            "minimum_span": "ONE_SUBSEQUENT_OWNER_CLOCK_EDGE",
            "required_result": "APPENDED_VCD_TIMESTAMP_STRICTLY_ADVANCES",
            "functional_evidence": False,
        },
        "target_capture": {
            "armed_before_entry_marker": True,
            "continuous": True,
            "signals": 64,
            "byte_cap": None,
            "event_cap": None,
            "sampling": False,
            "size_deletion": False,
        },
        "runner": {
            "process_identity": "PID_PLUS_PROC_START_TIME_TICKS",
            "pid_reuse_fails_safe": True,
            "nonchild_zombie_excluded": True,
            "term_kill_actions_bounded": True,
        },
        "frozen": ["validated_config42", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone", "candidate_matrix"],
        "pass": True,
        "errors": [],
    }
    write(TREE / "diagnostics/pretarget_safety_pulse_contract.json", pulse)
    temporal_path = TREE / "diagnostics/pretarget_target_capture_contract.json"
    temporal = load(temporal_path)
    temporal["schema"] = "qadd-pretarget-owner-tick-target-continuous-capture-v2"
    temporal["package_id"] = NEW
    temporal["predecessor_package_id"] = OLD
    temporal["source_return_analysis"] = identity(ANALYSIS)
    temporal["source_package_build_failure_audit"] = identity(AUDIT)
    temporal["capture"]["pretarget"] = "TRANSPORT_ONLY_PULSE_EVERY_16384_OWNER_CYCLES_SPANNING_NEXT_OWNER_EDGE"
    temporal["capture"]["pretarget_snapshot_minimum_owner_edges"] = 1
    temporal["capture"]["pretarget_appended_vcd_timestamp_must_advance"] = True
    temporal["negative_controls"] = sorted(set(temporal.get("negative_controls", [])) | {
        "same_time_dumpon_dumpoff_fails",
        "static_appended_timestamp_trace_yields_freeze",
        "owner_tick_pulse_trace_yields_continue",
        "pid_reuse_identity_mismatch_excluded",
        "nonchild_zombie_excluded",
        "termination_action_count_bounded",
    })
    write(temporal_path, temporal)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    additions = [
        {"source_root": "package", "source": "diagnostics/pretarget_safety_pulse_contract.json", "archive": "source_package/pretarget_safety_pulse_contract.json", "required": True},
        {"source_root": "package", "source": "provenance/v67_formal_return_analysis.json", "archive": "source_package/v67_formal_return_analysis.json", "required": True},
        {"source_root": "package", "source": "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "archive": "source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "required": True},
    ]
    archives = {row.get("archive") for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)


def repair_exact_predecessor_snapshot() -> None:
    """Keep the exact round-1 contract and TB available for recursive v4 validation."""
    predecessor_path = TREE / "provenance/v67_server_tb_vcd_bounded_causal_cone_contract.json"
    predecessor_path.write_bytes((SOURCE_TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json").read_bytes())
    shutil.copyfile(SOURCE_TREE / OLD_TB, TREE / OLD_TB)
    active_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    active = load(active_path)
    active["diagnostic_round"]["evolution"]["predecessor"]["contract_sha256"] = sha(predecessor_path)
    write(active_path, active)


def refresh_active_identities() -> None:
    runner = TREE / "PREPARE_AND_RUN.sh"
    runner_sha = sha(runner)
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path)
    resilience["package_id"] = NEW
    resilience["runner_sha256"] = runner_sha
    write(resilience_path, resilience)

    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    layout["package_id"] = NEW
    layout["install_name"] = NEW
    projected = f"install/cfg_pkg/{NEW}/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
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
        "source_package/pretarget_safety_pulse_contract.json",
        "source_package/v67_formal_return_analysis.json",
        "source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
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
    manifest["previous_version_progress"] = "v67 selected and compiled exact 4/2 and advanced pretarget execution, but zero-duration safety snapshots kept appended VCD time at zero and caused a package-local false freeze before target entry."
    manifest["current_version_purpose"] = "Preserve exact 4/2 and the unchanged 64-signal target cone while making each pretarget safety pulse span a real owner edge and binding process ownership to PID plus start time."
    manifest["package_build_failure_rule_audit"] = "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
    manifest["pretarget_safety_pulse"] = "diagnostics/pretarget_safety_pulse_contract.json"
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


def main() -> int:
    if not SOURCE_PENDING.is_file() or sha(SOURCE_PENDING) != OLD_SHA:
        raise RuntimeError("protected v67 pending identity drifted")
    if not SOURCE_RELEASE_ZIP.is_file() or sha(SOURCE_RELEASE_ZIP) != OLD_SHA or not SOURCE_TREE.is_dir():
        raise RuntimeError("durable v67 staging is not the exact pending package")
    if load(ANALYSIS).get("pass") is not True:
        raise RuntimeError("v67 analysis is not complete")
    audit = load(AUDIT)
    if audit.get("disposition") != "MACHINE_READABLE_PACKAGE_LOCAL_EXEMPTION_WITH_NEGATIVE_CONTROLS" or audit.get("pass") is not True:
        raise RuntimeError("third-attempt audit authority is absent")
    source_identity = identity(SOURCE_PENDING)
    source_validation = subtree_map(SOURCE_TREE / "validation")
    source_bitstream = sha(SOURCE_TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    source_config = sha(SOURCE_TREE / "provenance/config_lineage/op_tail_round_4_2.json")
    source_catalog = identity_normalized_json(SOURCE_TREE / "diagnostics/tb_vcd_signal_catalog.json", OLD)
    source_matrix = identity_normalized_json(SOURCE_TREE / "diagnostics/tb_vcd_candidate_matrix.json", OLD)

    replace_active_identity()
    patch_tb()
    patch_live_supervisor()
    bind_analysis_and_contracts()
    refresh_active_identities()
    bitstream = TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
    frozen_checks = {
        "v67_pending_byte_frozen": identity(SOURCE_PENDING) == source_identity,
        "config42_bitstream_exact": sha(bitstream) == source_bitstream == GOOD_BITSTREAM,
        "config_json_exact": sha(TREE / "provenance/config_lineage/op_tail_round_4_2.json") == source_config,
        "validation_payload_exact": subtree_map(TREE / "validation") == source_validation,
        "signal_catalog_exact_except_fresh_identity": identity_normalized_json(TREE / "diagnostics/tb_vcd_signal_catalog.json", NEW) == source_catalog,
        "candidate_matrix_exact_except_fresh_identity": identity_normalized_json(TREE / "diagnostics/tb_vcd_candidate_matrix.json", NEW) == source_matrix,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
    }
    frozen = {
        "schema": "qadd-v68-frozen-surface-v1",
        "package_id": NEW,
        "checks": frozen_checks,
        "changed_surfaces": ["fresh_identity", "pretarget_vcd_safety_pulse", "process_identity_and_reap", "return_provenance"],
        "frozen": ["validated_config42", "numeric", "workload_payload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone", "candidate_matrix"],
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": all(frozen_checks.values()),
        "errors": [name for name, passed in frozen_checks.items() if not passed],
    }
    write(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface failure: {frozen['errors']}")
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic ZIP recomputation differs")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("final ZIP CRC failed")
    receipt = {
        "schema": "qadd-v68-config42-owner-tick-build-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": NEW,
        "activation_epoch": EPOCH,
        "source_v67": source_identity,
        "return_analysis": identity(ANALYSIS),
        "package_build_failure_rule_audit": identity(AUDIT),
        "package": identity(ZIP),
        "repeat_package": identity(REPEAT),
        "deterministic_recompute": True,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "pass": True,
        "errors": [],
        "claim_boundary": "Local construction only; no production target, functional repair, natural/formal-D or E3-E5 claim.",
    }
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--refresh-existing"]:
        if not TREE.is_dir():
            raise RuntimeError("v68 staging is absent")
        repair_exact_predecessor_snapshot()
        refresh_active_identities()
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
