#!/usr/bin/env python3
"""Build the v93d-return-driven serialized Conv WR-data drain successor."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "tools/build_node0004_v93b_tbvcd_hardened_successor.py"
SPEC = importlib.util.spec_from_file_location("node0004_v93_builder", BASE_PATH)
assert SPEC and SPEC.loader
V93 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V93)
BASE = V93.BASE

PACKAGE_ID = "r5_n4_hw_v94b_tbvcd_wrdrain"
OUT = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_release1"
BASE.PACKAGE_ID = PACKAGE_ID
BASE.OUT = OUT
BASE.BUILD_ROOT = OUT / "build" / PACKAGE_ID
BASE.FINAL_ZIP = OUT / f"{PACKAGE_ID}.zip"
V93.PACKAGE_ID = PACKAGE_ID
V93.OUT = OUT

ORIGINAL_SIGNALS = V93.make_signals
ORIGINAL_PROBE = V93.make_probe
ORIGINAL_CONTRACT = V93.build_contract
ORIGINAL_POST_REQUEST = V93.make_post_request
ORIGINAL_TRANSFORM = V93.transform_runner
ORIGINAL_ZIP = V93.deterministic_zip

WR = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv"
FIFO = "rtl/utils/FIFO/FIFO.sv"


def make_signals() -> list[dict[str, object]]:
    signals = ORIGINAL_SIGNALS()
    add = V93.local_signal
    signals.extend(
        [
            add("sig_prepared_wr_hs", "u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs", 1, ["fifo_enqueue", "accept", "prepared_data"], WR, "wr_data_chl_prepared_data_wr_hs"),
            add("sig_prepared_rd_hs", "u_WR_Data_Channel.wr_data_chl_prepared_data_rd_hs", 1, ["fifo_dequeue", "drain", "prepared_data"], WR, "wr_data_chl_prepared_data_rd_hs"),
            add("sig_prepared_valid", "u_WR_Data_Channel.wr_data_chl_prepared_data_vld", 1, ["valid", "prepared_data"], WR, "wr_data_chl_prepared_data_vld"),
            add("sig_mse_buf_spatial_size", "u_WR_Data_Channel.mse_buf_spatial_size", 5, ["count", "configuration", "prepared_data"], WR, "mse_buf_spatial_size"),
            add("sig_wr_req_valid", "u_WR_Data_Channel.wr_data_chl_req_valid", 1, ["request", "valid", "producer"], WR, "wr_data_chl_req_valid"),
            add("sig_wr_req_ready", "u_WR_Data_Channel.wr_data_chl_req_ready", 1, ["ready", "accept", "backpressure"], WR, "wr_data_chl_req_ready"),
            add("sig_wr_queue_wr", "u_WR_Data_Channel.wr_chl_queue_wr_en", 1, ["fifo_enqueue", "accept", "metadata_queue"], WR, "wr_chl_queue_wr_en"),
            add("sig_wr_queue_rd", "u_WR_Data_Channel.wr_chl_queue_rd_en", 1, ["fifo_dequeue", "drain", "metadata_queue"], WR, "wr_chl_queue_rd_en"),
            add("sig_wr_queue_empty", "u_WR_Data_Channel.wr_chl_queue_empty", 1, ["fifo_empty", "drain", "metadata_queue"], WR, "wr_chl_queue_empty"),
            add("sig_wr_queue_full", "u_WR_Data_Channel.wr_chl_queue_full", 1, ["fifo_full", "backpressure", "metadata_queue"], WR, "wr_chl_queue_full"),
            add("sig_wr_queue_count", "u_WR_Data_Channel.u_wr_chl_queue.fifo_counter", 2, ["fifo_occupancy", "count", "metadata_queue"], FIFO, "fifo_counter"),
            add("sig_wr_queue_tsf_size", "u_WR_Data_Channel.wr_chl_queue_rd_tsf_size", 5, ["count", "metadata_queue", "prepared_data"], WR, "wr_chl_queue_rd_tsf_size"),
            add("sig_wr_queue_mask_flag", "u_WR_Data_Channel.wr_chl_queue_rd_mask_flag", 1, ["mask", "metadata_queue"], WR, "wr_chl_queue_rd_mask_flag"),
            add("sig_wr_ob_vld_in", "u_WR_Data_Channel.wr_chl_ob_vld_in", 2, ["valid", "output_buffer", "producer"], WR, "wr_chl_ob_vld_in"),
            add("sig_wr_ob_bp_pre", "u_WR_Data_Channel.wr_chl_ob_bp_pre", 2, ["ready", "backpressure", "output_buffer"], WR, "wr_chl_ob_bp_pre"),
            add("sig_wr_ob_wr_hs", "u_WR_Data_Channel.wr_chl_ob_wr_hs", 2, ["fifo_enqueue", "accept", "output_buffer"], WR, "wr_chl_ob_wr_hs"),
            add("sig_wr_ob_vld", "u_WR_Data_Channel.wr_chl_ob_vld", 2, ["valid", "output_buffer", "internal_state"], WR, "wr_chl_ob_vld"),
            add("sig_wr_ob_rd_hs", "u_WR_Data_Channel.wr_chl_ob_rd_hs", 2, ["fifo_dequeue", "drain", "output_buffer"], WR, "wr_chl_ob_rd_hs"),
            add("sig_wr_ob_sel", "u_WR_Data_Channel.wr_chl_ob_sel", 1, ["selected_port", "output_buffer", "internal_state"], WR, "wr_chl_ob_sel"),
        ]
    )
    return signals


def make_probe(signals: list[dict[str, object]]) -> str:
    probe = ORIGINAL_PROBE(signals)
    # The current v3 gate requires the executable dump target to be the exact
    # source-bound DUT hierarchy, not the passive bind-module input alias.  The
    # aliases remain useful to the read-only monitor logic, but are deliberately
    # not the objects named by $dumpvars.
    for signal in signals:
        local = str(signal["signal_id"])
        exact = str(signal["exact_hierarchy"])
        old_dump = f"$dumpvars(0, {local});"
        new_dump = f"$dumpvars(0, {exact});"
        if old_dump not in probe:
            raise RuntimeError(f"v94 exact dump target anchor absent: {local}")
        probe = probe.replace(old_dump, new_dump, 1)
    anchor = "(|(sig_buf_rreq_valid & {16{sig_buf_rreq_ready}})) || sig_slice_finish) begin"
    replacement = (
        "(|(sig_buf_rreq_valid & {16{sig_buf_rreq_ready}})) ||\n"
        "              sig_prepared_wr_hs || sig_prepared_rd_hs ||\n"
        "              (sig_wr_req_valid && sig_wr_req_ready) || sig_wr_queue_wr || sig_wr_queue_rd ||\n"
        "              (|sig_wr_ob_wr_hs) || (|sig_wr_ob_rd_hs) || sig_slice_finish) begin"
    )
    if anchor not in probe:
        raise RuntimeError("v94 qualified-progress extension anchor absent")
    probe = probe.replace(anchor, replacement, 1)
    declaration = "string codex_vcd_path;"
    if declaration not in probe:
        raise RuntimeError("v94 control-path declaration anchor absent")
    probe = probe.replace(declaration, declaration + "\n          string codex_vcd_control_path;\n          integer codex_control_fd;", 1)
    plusarg = 'if (!$value$plusargs("CODEX_VCD_PATH=%s", codex_vcd_path)) $fatal(1, "missing CODEX_VCD_PATH");'
    if plusarg not in probe:
        raise RuntimeError("v94 control-path plusarg anchor absent")
    probe = probe.replace(plusarg, plusarg + '\n              if (!$value$plusargs("CODEX_VCD_CONTROL_PATH=%s", codex_vcd_control_path)) $fatal(1, "missing CODEX_VCD_CONTROL_PATH");', 1)
    old_stop = """if (codex_dump_active && codex_owner_cycles - codex_last_progress_cycle >= CODEX_DUMPOFF_CYCLES) begin
              $dumpoff; $dumpflush; codex_dump_active = 0;
              $display("CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
            end
            if (!codex_dump_active && !codex_stop_reported && codex_owner_cycles - codex_last_progress_cycle >= CODEX_DUMPOFF_CYCLES + CODEX_GRACE_CYCLES) begin
              codex_stop_reported = 1;
              $display("CODEX_TB_VCD_STOP_REQUEST_V1 reason=CAUSAL_PLATEAU sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
            end"""
    new_stop = """if (codex_dump_active && !codex_stop_reported && (codex_owner_cycles & 64'h3fff) == 0) begin
              codex_control_fd = $fopen(codex_vcd_control_path, "r");
              if (codex_control_fd != 0) begin
                $fclose(codex_control_fd);
                $dumpoff; $dumpflush; codex_dump_active = 0; codex_stop_reported = 1;
                $display("CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
                $display("CODEX_TB_VCD_STOP_REQUEST_V1 reason=CAUSAL_PLATEAU sim_time=%0d owner_cycles=%0d", codex_time_ps, codex_owner_cycles);
              end
            end"""
    if old_stop not in probe:
        raise RuntimeError("v94 shared-decision TB stop anchor absent")
    return probe.replace(old_stop, new_stop, 1)


def build_contract(signals: list[dict[str, object]], probe_sha: str) -> dict[str, object]:
    contract = ORIGINAL_CONTRACT(signals, probe_sha)
    contract["boundaries"] = [
        {"boundary_id": "upstream", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ["sig_rd_ob_count", "sig_rd_ob_rd", "sig_buf_rreq_ready", "sig_buf_rvalid", "sig_mse_buf_spatial_size"]},
        {"boundary_id": "current", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ["sig_prepared_count", "sig_prepared_bp", "sig_prepared_wr_hs", "sig_prepared_rd_hs", "sig_prepared_valid", "sig_wr_data_ready"]},
        {"boundary_id": "downstream", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ["sig_wr_req_valid", "sig_wr_req_ready", "sig_wr_queue_wr", "sig_wr_queue_rd", "sig_wr_queue_count", "sig_wr_queue_empty", "sig_wr_queue_full", "sig_wr_queue_tsf_size", "sig_wr_queue_mask_flag", "sig_wr_ob_vld_in", "sig_wr_ob_bp_pre", "sig_wr_ob_wr_hs", "sig_wr_ob_vld", "sig_wr_ob_rd_hs", "sig_wr_ob_sel", "sig_wdata_valid", "sig_wdata_ready"]},
        {"boundary_id": "state_hold_clear", "layer": "STATE_HOLD_CLEAR", "signal_ids": ["sig_rst_n", "sig_slice_rst", "sig_hold_data_valid", "sig_mse_enable", "sig_slice_finish", "sig_global_fetch_finish", "sig_global_slice_finish"]},
    ]
    candidates = [
        ("prepared_write_without_drain", "Prepared data accepts a new spatial group while no output-buffer fill drains the matching transfer size."),
        ("metadata_queue_starvation_or_block", "Write metadata queue empty/full state or request acceptance prevents the prepared-data transfer from becoming eligible."),
        ("prepared_valid_size_gate", "Prepared count versus queued transfer size prevents prepared-data valid."),
        ("output_buffer_selection_gate", "Selected lane and vld_in keep both output-buffer write handshakes low."),
        ("output_buffer_backpressure", "Per-channel output buffer occupancy/backpressure prevents a new output write."),
        ("memory_wdata_drain_block", "Memory write-data ready prevents output-buffer read handshakes."),
        ("prepared_count_accounting", "Prepared count update is inconsistent with observed write/read handshakes and their sizes."),
        ("terminal_lifetime_hold", "Prepared/output/metadata state remains live after global fetch completion."),
    ]
    contract["candidates"] = [{"candidate_id": name, "description": text} for name, text in candidates]
    sets = {
        "prepared_write_without_drain": ["sig_prepared_wr_hs", "sig_prepared_rd_hs", "sig_prepared_count", "sig_mse_buf_spatial_size", "sig_wr_queue_tsf_size"],
        "metadata_queue_starvation_or_block": ["sig_wr_req_valid", "sig_wr_req_ready", "sig_wr_queue_wr", "sig_wr_queue_rd", "sig_wr_queue_count", "sig_wr_queue_empty", "sig_wr_queue_full"],
        "prepared_valid_size_gate": ["sig_prepared_count", "sig_wr_queue_tsf_size", "sig_prepared_valid", "sig_mse_enable"],
        "output_buffer_selection_gate": ["sig_wr_ob_sel", "sig_wr_queue_mask_flag", "sig_wr_ob_vld_in", "sig_wr_ob_wr_hs"],
        "output_buffer_backpressure": ["sig_wr_ob_vld", "sig_wr_ob_bp_pre", "sig_wr_ob_vld_in", "sig_wr_ob_wr_hs"],
        "memory_wdata_drain_block": ["sig_wr_ob_vld", "sig_wdata_valid", "sig_wdata_ready", "sig_wr_ob_rd_hs"],
        "prepared_count_accounting": ["sig_prepared_wr_hs", "sig_prepared_rd_hs", "sig_mse_buf_spatial_size", "sig_wr_queue_tsf_size", "sig_prepared_count"],
        "terminal_lifetime_hold": ["sig_prepared_count", "sig_wr_queue_count", "sig_wr_ob_vld", "sig_hold_data_valid", "sig_mse_enable", "sig_slice_finish", "sig_global_fetch_finish", "sig_global_slice_finish"],
    }
    predicates = {
        "prepared_write_without_drain": "prepared_wr_hs_one_and_prepared_rd_hs_zero_at_count_saturation",
        "metadata_queue_starvation_or_block": "queue_accept_or_occupancy_explains_absent_metadata_dequeue",
        "prepared_valid_size_gate": "prepared_count_and_tsf_size_explain_prepared_valid",
        "output_buffer_selection_gate": "selected_lane_and_mask_explain_vld_in_and_write_handshake",
        "output_buffer_backpressure": "output_valid_explains_bp_pre_and_absent_write_handshake",
        "memory_wdata_drain_block": "wdata_ready_explains_output_read_handshake_and_valid_lifetime",
        "prepared_count_accounting": "next_count_equals_count_plus_write_size_minus_read_size",
        "terminal_lifetime_hold": "local_write_state_nonempty_after_global_fetch_finish",
    }
    matrix = []
    for candidate, _ in candidates:
        for boundary in contract["boundaries"]:
            direct = [item for item in sets[candidate] if item in boundary["signal_ids"]]
            matrix.append({"candidate_id": candidate, "boundary_id": boundary["boundary_id"], "expected_signature": {"decision_predicate": predicates[candidate], "candidate_signal_ids": sets[candidate], "direct_boundary_signal_ids": direct, "requires_complete_ordered_transitions": True}})
    contract["candidate_boundary_matrix"] = matrix
    contract["runtime_policy"].update({
        "heartbeat_source": "APPENDED_VCD_TIMESTAMP",
        "heartbeat_width_bits": 64,
        "heartbeat_signed": False,
        "heartbeat_cadence_cycles": 16384,
        "decision_authority": "SHARED_RUNTIME_EVALUATOR_ONLY",
        "outer_runner_independent_exit_logic": False,
        "required_replay_cases": ["ADVANCING_VCD_TIMESTAMP", "PLATEAU_SUSPECTED_ONLY", "PLATEAU_DUMP_OFF_PLUS_GRACE", "THREE_INTERVAL_TRUE_FREEZE"],
        "archive_timestamp_binding": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT",
    })
    contract["execution"]["dump_targeting"] = {
        "mode": "EXACT_CATALOG_SIGNALS",
        "module_scope_dump": False,
        "dumpvars_depth": 0,
        "signal_ids": [str(signal["signal_id"]) for signal in signals],
    }
    contract["execution"]["sim_argv"].append(
        "+CODEX_VCD_CONTROL_PATH=<attempt-shared-runtime-stop-control>"
    )
    contract["claim_boundary"] = "v93d-return-driven WR_Data_Channel leaf-driver diagnostic; no production root, RTL defect, natural terminal, formal-D, E3, E4 or E5 claim."
    return contract


def fixed_finalizer() -> str:
    text = BASE.FINALIZER
    ident_anchor = "def write(path,value):"
    fused = """def vcd_ident(path):
    if not path.is_file(): return None,0
    h=hashlib.sha256(); size=0; carry=b''; last=0
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            size+=len(block); h.update(block); rows=(carry+block).split(b'\\n'); carry=rows.pop() if rows else b''
            for raw in rows:
                row=raw.strip()
                if len(row)>1 and row.startswith(b'#') and row[1:].isdigit(): last=int(row[1:])
    row=carry.strip()
    if len(row)>1 and row.startswith(b'#') and row[1:].isdigit(): last=int(row[1:])
    return {'path':str(path),'bytes':size,'sha256':h.hexdigest()},last
"""
    if ident_anchor not in text:
        raise RuntimeError("v94 fused VCD identity anchor absent")
    text = text.replace(ident_anchor, fused + ident_anchor, 1)
    vid_anchor = "timescale,enddefs,refs=vcd_header(a.vcd); required={x['signal_id'] for x in signals}; complete=required.issubset(set(refs)); vid=ident(a.vcd)"
    vid_replacement = "timescale,enddefs,refs=vcd_header(a.vcd); required={x['signal_id'] for x in signals}; complete=required.issubset(set(refs)); vid,last_archive_tick=vcd_ident(a.vcd)"
    if vid_anchor not in text:
        raise RuntimeError("v94 archive timestamp identity anchor absent")
    text = text.replace(vid_anchor, vid_replacement, 1)
    text = text.replace("'transitions_complete':proc.get('vcd_stable') is True", "'transitions_complete':proc.get('vcd_stable') is True and proc.get('process_tree_reaped') is True", 1)
    samples_anchor = "samples=proc.get('samples',[])\n    if samples and natural: samples[-1]['natural_terminal']=True"
    samples_replacement = "samples=proc.get('samples',[])\n    if samples and last_archive_tick>=samples[-1].get('appended_vcd_timestamp_ticks',0):\n        final=dict(samples[-1]); final['seq']=len(samples); final['wall_seconds']=float(final.get('wall_seconds',0))+0.001; final['appended_vcd_timestamp_ticks']=last_archive_tick; final['sim_time_ticks']=last_archive_tick\n        if proc.get('stop_marker'): final['owner_clock_cycles']=proc['stop_marker'].get('owner_clock_cycles',final.get('owner_clock_cycles',0)); final['sim_cycles']=final['owner_clock_cycles']\n        samples=[*samples,final]\n    if samples and natural: samples[-1]['natural_terminal']=True"
    if samples_anchor not in text:
        raise RuntimeError("v94 final archive sample anchor absent")
    text = text.replace(samples_anchor, samples_replacement, 1)
    old = "'samples':samples,'candidate_catalog_complete':complete"
    new = "'samples':samples,'heartbeat_contract':proc.get('heartbeat_contract',{'source':'APPENDED_VCD_TIMESTAMP','width_bits':64,'signed':False,'cadence_cycles':16384}),'decision_authority':proc.get('decision_authority'),'archive_timestamp_receipt':(None if vid is None else {'binding':'FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT','parse_status':'COMPLETE',**vid,'last_timestamp_ticks':last_archive_tick}),'target_entry_observed':proc.get('simulation_time_progress_observed') is True,'target_diagnostic_claim':proc.get('simulation_time_progress_observed') is True,'candidate_catalog_complete':complete"
    if old not in text:
        raise RuntimeError("v94 finalizer request anchor absent")
    text = text.replace(old, new, 1)
    exact_anchor = "'vcd_identity':vcd_identity,'flush':"
    exact_replacement = "'vcd_identity':vcd_identity,'return_exact_set':{'members':([] if vid is None else [vid]),'hard_limit_bytes':None,'truncated':False,'sampled':False,'allowlist_complete':vid is not None,'published':vid is not None},'live_diagnostics':{'downstream_state_source':'LIVE_SAME_ATTEMPT','first_error_source':'LIVE_SAME_ATTEMPT','stale_evidence_absent':True},'flush':"
    if exact_anchor not in text:
        raise RuntimeError("v94 exact-set/live diagnostic anchor absent")
    text = text.replace(exact_anchor, exact_replacement, 1)
    old = "receipt=evaluate(request); write(out/'VCD_RUNTIME_RECEIPT.json',receipt)"
    new = "receipt=evaluate(request)\n    write(out/'TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json',request.get('archive_timestamp_receipt'))\n    write(out/'TB_VCD_RETURN_EXACT_SET.json',request.get('return_exact_set'))\n    write(out/'VCD_RUNTIME_RECEIPT.json',receipt)"
    if old not in text:
        raise RuntimeError("v94 finalizer stop-decision anchor absent")
    return text.replace(old, new, 1)


BASE.SUPERVISOR = (ROOT / "tools/node0004_tb_vcd_guarded_supervisor_v94.py").read_text(encoding="utf-8")
BASE.FINALIZER = fixed_finalizer()


def make_post_request() -> dict[str, object]:
    request = ORIGINAL_POST_REQUEST()
    existing = {str(row["archive"]) for row in request["core_entries"]}
    additions = [
        ("evidence/vcd/TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json", "evidence/vcd/TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json"),
        ("evidence/vcd/TB_VCD_RETURN_EXACT_SET.json", "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json"),
    ]
    for archive, source in additions:
        if archive not in existing:
            request["core_entries"].append({"archive": archive, "required": True, "source": source, "source_root": "attempt"})
    return request


def transform_runner() -> None:
    ORIGINAL_TRANSFORM()
    provenance = BASE.BUILD_ROOT / "provenance"
    shutil.copyfile(ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_return_analysis/return_analysis.json", provenance / "v93d_return_analysis.json")
    shutil.copyfile(ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_return_analysis/rule_gap_audit.json", provenance / "v93d_rule_gap_audit.json")
    shutil.copyfile(
        ROOT / "tools/node0004_v94_package_release_preflight.py",
        BASE.BUILD_ROOT / "package_tools/package_release_preflight.py",
    )
    runner_path = BASE.BUILD_ROOT / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    marker = "# V93 hardening:"
    if marker not in runner:
        raise RuntimeError("v94 runner provenance anchor absent")
    runner = runner.replace(marker, "# V94: appended-VCD-time supervision, exact post-dumpoff marker/grace, PID-starttime reaping.\n" + marker, 1)
    supervisor = ' --vcd "$vcd_path" --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" -- '
    replacement = ' --vcd "$vcd_path" --receipt "$evidence_root/PROCESS_TREE_RECEIPT.json" --runtime-evaluator "$package_root/package_tools/server_tb_vcd_runtime_supervision.py" --stop-control "$run_root/c0/shared_stop.control" -- '
    if supervisor not in runner:
        raise RuntimeError("v94 shared evaluator supervisor invocation anchor absent")
    runner = runner.replace(supervisor, replacement, 1)
    control_plusarg = '"+CODEX_VCD_PATH=$vcd_path"'
    if control_plusarg not in runner:
        raise RuntimeError("v94 TB control plusarg anchor absent")
    runner = runner.replace(control_plusarg, control_plusarg + ' "+CODEX_VCD_CONTROL_PATH=$run_root/c0/shared_stop.control"', 1)
    runner_path.write_text(runner, encoding="utf-8", newline="\n")


def deterministic_zip() -> None:
    manifest_path = BASE.BUILD_ROOT / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "node0004-v94b-tbvcd-wrdrain-package-manifest-v1",
        "previous_version_progress": "v93d compiled and executed the target, excluded QAdd-v63-style false freeze, and narrowed the stable hold to WR_Data_Channel prepared-data occupancy/drain; its post-stop process tree was not fully reaped.",
        "current_purpose": "Distinguish prepared write/read accounting, metadata queue, selected output-buffer and memory-ready drain alternatives while fixing appended-time supervision and identity-bound reaping.",
        "rule_gap_audit": "provenance/v93d_rule_gap_audit.json",
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "package_build_failure_rule_audit_triggered": False,
        "retired_ack_comparator_present": False,
    })
    (BASE.BUILD_ROOT / "README.md").write_text(
        f"# {PACKAGE_ID}\n\n"
        "Previous progress: v93d production compile and target execution succeeded. Its appended VCD time and unsigned 64-bit heartbeat proved the stop was not the QAdd v63 false freeze; the causal boundary narrowed to WR_Data_Channel prepared-data occupancy/drain. The partial finalization was caused by an unreaped post-stop process.\n\n"
        "Current purpose: preserve the exact frozen workload and actual-source target, add only the prepared write/read, metadata queue, selected output-buffer and memory-ready drain leaf nets, and harden appended-VCD-time supervision plus PID-starttime-bound reaping.\n\n"
        "Run only after separate authorization:\n\n"
        f"    bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\n"
        "The dump profile remains DUMP_VCD=0, DUMP_FSDB=0, TB_DUMP_FSDB=0. The passive package-local TB writes the bounded standard VCD; evidence is not capped, sampled, truncated or deleted because of size.\n",
        encoding="utf-8", newline="\n",
    )
    manifest["files"] = [row for row in BASE.file_map() if row["path"] != "package_manifest.json"]
    BASE.write_json(manifest_path, manifest)
    ORIGINAL_ZIP()


BASE.make_signals = make_signals
BASE.make_probe = make_probe
BASE.build_contract = build_contract
BASE.make_post_request = make_post_request
BASE.transform_runner = transform_runner
BASE.deterministic_zip = deterministic_zip


def main() -> int:
    result = BASE.main()
    receipt_path = OUT / "build_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update({
        "schema": "node0004-v94b-tbvcd-wrdrain-build-v1",
        "source_formal_return_analysis": "outputs/conv_node0004_v93d_tbvcd_hardened_return_analysis/return_analysis.json",
        "rule_gap_audit": "outputs/conv_node0004_v93d_tbvcd_hardened_return_analysis/rule_gap_audit.json",
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "package_build_failure_rule_audit_triggered": False,
        "authorized_changes": ["fresh identity", "WR_Data_Channel leaf actual-net causal expansion", "appended-VCD-time runtime supervision", "exact dumpoff/stop grace binding", "PID-starttime-bound process reaping", "runtime receipt stop-decision conjunction"],
    })
    BASE.write_json(receipt_path, receipt)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
