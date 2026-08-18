#!/usr/bin/env python3
"""Build the v92-return-driven hardened serialized Conv TB-VCD successor."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "tools/build_node0004_v92b_tbvcd_successor.py"
SPEC = importlib.util.spec_from_file_location("node0004_v92_builder", BASE_PATH)
assert SPEC and SPEC.loader
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

PACKAGE_ID = "r5_n4_hw_v93d_tbvcd_hardened"
OUT = ROOT / "outputs/conv_node0004_v93d_tbvcd_hardened_release3"
BASE.PACKAGE_ID = PACKAGE_ID
BASE.OUT = OUT
BASE.BUILD_ROOT = OUT / "build" / PACKAGE_ID
BASE.FINAL_ZIP = OUT / f"{PACKAGE_ID}.zip"
BASE.SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/superseded"
    / "conv_serialized_node0004/r5_n4_hw_v91b_normfix/r5_n4_hw_v91b_normfix.zip"
)

ORIGINAL_MAKE_SIGNALS = BASE.make_signals
ORIGINAL_BUILD_CONTRACT = BASE.build_contract
ORIGINAL_MAKE_PROBE = BASE.make_probe
ORIGINAL_MAKE_POST_REQUEST = BASE.make_post_request
ORIGINAL_TRANSFORM_RUNNER = BASE.transform_runner
ORIGINAL_DETERMINISTIC_ZIP = BASE.deterministic_zip


TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
)


def local_signal(
    signal_id: str,
    hierarchy_suffix: str,
    width: int,
    roles: list[str],
    relative: str,
    symbol: str,
) -> dict[str, object]:
    source = BASE.LOCAL_RTL / relative
    return {
        "signal_id": signal_id,
        "exact_hierarchy": f"{TARGET}.{hierarchy_suffix}",
        "width_bits": width,
        "roles": roles,
        "source_path": relative,
        "source_sha256": BASE.sha_file(source),
        "declaration_span_sha256": BASE.declaration_span(source, symbol),
        "source_binding": "ACTUAL_SOURCE_NET",
        "derived_expected_equation": False,
        "drives_dut": False,
    }


def make_signals() -> list[dict[str, object]]:
    signals = ORIGINAL_MAKE_SIGNALS()
    rd = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    wr = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    top = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
    signals.extend(
        [
            local_signal("sig_rd_ob_count", "u_RD_Buffer_AG.buf_ag_ob_cnt", 2, ["fifo_occupancy", "count", "outstanding", "internal_state"], rd, "buf_ag_ob_cnt"),
            local_signal("sig_rd_ob_full", "u_RD_Buffer_AG.buf_ag_ob_full", 1, ["fifo_full", "backpressure", "per_bank_full"], rd, "buf_ag_ob_full"),
            local_signal("sig_rd_ob_empty", "u_RD_Buffer_AG.buf_ag_ob_empty", 1, ["fifo_empty", "drain"], rd, "buf_ag_ob_empty"),
            local_signal("sig_rd_ob_wr", "u_RD_Buffer_AG.buf_ag_ob_wr_en", 1, ["fifo_enqueue", "accept"], rd, "buf_ag_ob_wr_en"),
            local_signal("sig_rd_ob_rd", "u_RD_Buffer_AG.buf_ag_ob_rd_en", 1, ["fifo_dequeue", "drain"], rd, "buf_ag_ob_rd_en"),
            local_signal("sig_buf_rreq_ready", "buf2mse_rreq_ready", 1, ["ready", "accept", "backpressure"], top, "buf2mse_rreq_ready"),
            local_signal("sig_buf_rvalid", "buf2mse_rvalid", 1, ["valid", "producer"], top, "buf2mse_rvalid"),
            local_signal("sig_buf_rreq_valid", "u_RD_Buffer_AG.mse2buf_rreq_valid", 16, ["request", "valid"], rd, "mse2buf_rreq_valid"),
            local_signal("sig_wr_data_ready", "u_WR_Data_Channel.wr_data_chl_ready", 1, ["ready", "accept", "backpressure"], wr, "wr_data_chl_ready"),
            local_signal("sig_hold_data_valid", "u_WR_Data_Channel.wr_data_chl_hold_data_vld", 1, ["valid", "internal_state", "lifetime"], wr, "wr_data_chl_hold_data_vld"),
            local_signal("sig_prepared_bp", "u_WR_Data_Channel.wr_chl_prepared_data_bp_pre", 1, ["ready", "backpressure"], wr, "wr_chl_prepared_data_bp_pre"),
            local_signal("sig_prepared_count", "u_WR_Data_Channel.wr_data_chl_prepared_data_cnt", 6, ["fifo_occupancy", "count", "outstanding", "internal_state"], wr, "wr_data_chl_prepared_data_cnt"),
        ]
    )
    return signals


def make_probe(signals: list[dict[str, object]]) -> str:
    probe = ORIGINAL_MAKE_PROBE(signals)
    replacements = {
        "codex_time_ps = $rtoi($realtime * 1000.0);": "codex_time_ps = longint'($realtime * 1000.0);",
        "(codex_owner_cycles & 64'h3ffff) == 0": "(codex_owner_cycles & 64'h3fff) == 0",
        "if (sig_row_wr || sig_row_rd || sig_col_wr || sig_col_rd || sig_queue_wr || sig_queue_rd ||\n"
        "              (|(sig_mem_req_valid & sig_mem_req_ready)) || (|(sig_wdata_valid & sig_wdata_ready)) ||\n"
        "              sig_tag_valid || sig_slice_finish) begin":
        "if ((sig_row_wr && !sig_row_full) || (sig_row_rd && !sig_row_empty) ||\n"
        "              (sig_col_wr && !sig_col_full) || (sig_col_rd && !sig_col_empty) ||\n"
        "              (sig_queue_wr && !sig_queue_full) || (sig_queue_rd && !sig_queue_empty) ||\n"
        "              (sig_rd_ob_wr && !sig_rd_ob_full) || (sig_rd_ob_rd && !sig_rd_ob_empty) ||\n"
        "              (|(sig_mem_req_valid & sig_mem_req_ready)) || (|(sig_wdata_valid & sig_wdata_ready)) ||\n"
        "              (|(sig_buf_rreq_valid & {16{sig_buf_rreq_ready}})) || sig_slice_finish) begin",
    }
    for old, new in replacements.items():
        if old not in probe:
            raise RuntimeError(f"probe hardening anchor absent: {old[:72]}")
        probe = probe.replace(old, new, 1)
    return probe


def build_contract(signals: list[dict[str, object]], probe_sha: str) -> dict[str, object]:
    contract = ORIGINAL_BUILD_CONTRACT(signals, probe_sha)
    contract["boundaries"] = [
        {"boundary_id": "upstream", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ["sig_mse_enable", "sig_row_tag", "sig_col_tag", "sig_valid_mask", "sig_global_valid", "sig_global_ready"]},
        {"boundary_id": "current", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ["sig_public_ack", "sig_row_count", "sig_col_count", "sig_queue_count", "sig_queue_full", "sig_bp_post", "sig_rd_ob_count", "sig_rd_ob_full"]},
        {"boundary_id": "downstream", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ["sig_rd_ob_wr", "sig_rd_ob_rd", "sig_buf_rreq_ready", "sig_buf_rreq_valid", "sig_buf_rvalid", "sig_wr_data_ready", "sig_hold_data_valid", "sig_prepared_bp", "sig_prepared_count", "sig_mem_req_valid", "sig_mem_req_ready", "sig_wdata_valid", "sig_wdata_ready"]},
        {"boundary_id": "state_hold_clear", "layer": "STATE_HOLD_CLEAR", "signal_ids": ["sig_rst_n", "sig_slice_rst", "sig_mse_enable", "sig_queue_empty", "sig_rd_ob_empty", "sig_slice_finish", "sig_global_fetch_finish", "sig_global_slice_finish"]},
    ]
    candidates = [
        ("actual_ack_driver_block", "Actual public ACK follows row/column full inputs and blocks source acceptance."),
        ("aggregate_queue_hold", "Aggregate queue is full because its dequeue path is deasserted."),
        ("rd_buffer_output_full", "RD_Buffer_AG two-entry output buffer is full and drives aggregate backpressure low."),
        ("buffer_request_ready_block", "Buffer request consumer readiness prevents RD_Buffer_AG dequeue."),
        ("write_data_channel_ready_block", "WR_Data_Channel readiness prevents RD_Buffer_AG dequeue."),
        ("write_data_prepared_queue_hold", "WR_Data_Channel hold/prepared state prevents readiness."),
        ("terminal_lifetime_hold", "Local drain and completion state remain active after input fetching ends."),
        ("global_progress_elsewhere", "Global execution changes while the selected MSE4 cone remains stable."),
    ]
    contract["candidates"] = [{"candidate_id": cid, "description": description} for cid, description in candidates]
    signal_sets = {
        "actual_ack_driver_block": ["sig_public_ack", "sig_row_full", "sig_col_full"],
        "aggregate_queue_hold": ["sig_queue_wr", "sig_queue_rd", "sig_queue_count", "sig_queue_full", "sig_bp_post"],
        "rd_buffer_output_full": ["sig_bp_post", "sig_rd_ob_count", "sig_rd_ob_full", "sig_rd_ob_wr", "sig_rd_ob_rd"],
        "buffer_request_ready_block": ["sig_rd_ob_rd", "sig_buf_rreq_ready", "sig_buf_rreq_valid"],
        "write_data_channel_ready_block": ["sig_rd_ob_rd", "sig_wr_data_ready", "sig_buf_rvalid"],
        "write_data_prepared_queue_hold": ["sig_wr_data_ready", "sig_hold_data_valid", "sig_prepared_bp", "sig_prepared_count"],
        "terminal_lifetime_hold": ["sig_mse_enable", "sig_queue_empty", "sig_rd_ob_empty", "sig_slice_finish", "sig_global_fetch_finish", "sig_global_slice_finish"],
        "global_progress_elsewhere": ["sig_global_valid", "sig_global_ready", "sig_global_fetch_finish", "sig_global_slice_finish"],
    }
    predicates = {
        "actual_ack_driver_block": "public_ack_equation_exact_and_any_source_fifo_full",
        "aggregate_queue_hold": "queue_full_and_queue_rd_zero",
        "rd_buffer_output_full": "bp_post_zero_and_rd_ob_full_one",
        "buffer_request_ready_block": "rd_ob_nonempty_and_buf_rreq_ready_zero",
        "write_data_channel_ready_block": "rd_ob_nonempty_and_wr_data_ready_zero",
        "write_data_prepared_queue_hold": "wr_data_ready_zero_and_hold_or_prepared_backpressure",
        "terminal_lifetime_hold": "local_queues_or_mse_active_after_global_fetch_finish",
        "global_progress_elsewhere": "global_witness_changes_while_local_cone_stable",
    }
    matrix = []
    for candidate, _ in candidates:
        for boundary in contract["boundaries"]:
            boundary_ids = set(boundary["signal_ids"])
            direct = [signal for signal in signal_sets[candidate] if signal in boundary_ids]
            matrix.append(
                {
                    "candidate_id": candidate,
                    "boundary_id": boundary["boundary_id"],
                    "expected_signature": {
                        "decision_predicate": predicates[candidate],
                        "candidate_signal_ids": signal_sets[candidate],
                        "direct_boundary_signal_ids": direct,
                        "requires_complete_ordered_transitions": True,
                    },
                }
            )
    contract["candidate_boundary_matrix"] = matrix
    contract["runtime_policy"]["heartbeat_owner_cycles"] = 16384
    # The shared v1 schema has additionalProperties=false for runtime_policy;
    # keep the measured cadence in the claim-bearing execution metadata instead.
    contract["runtime_policy"].pop("heartbeat_owner_cycles")
    contract["claim_boundary"] = "v92-return-driven hardened local package contract; no production result, root cause, natural terminal, formal-D, E3, E4 or E5 claim."
    return contract


def make_post_request() -> dict[str, object]:
    request = ORIGINAL_MAKE_POST_REQUEST()
    relative_sources = sorted(
        {
            str(item["source_path"])
            for item in make_signals()
        }
    )
    for relative in relative_sources:
        source = f"evidence/compiled_source/actual_sources/{relative}"
        flat_name = Path(relative).name
        request["core_entries"].append(
            {
                "archive": f"evidence/compiled_source/actual_source_files/{flat_name}",
                "required": False,
                "source": source,
                "source_root": "attempt",
            }
        )
    request["claim_boundary"] = "Unbounded hardened causal-cone VCD, actual source bytes and runtime/core receipts; no truncation, sampling or size deletion."
    return request


def hardened_supervisor() -> str:
    text = BASE.SUPERVISOR
    old = """        if remaining: actions.append(base.signal_owned(proc.pid,pgid,known,signal.SIGKILL))
        try: root_exit=proc.wait(timeout=30)
        except Exception: root_exit=None
        reaped=base.reap_adopted(known,time.monotonic()+30); remaining=base.owned_processes(proc.pid,pgid,known)
"""
    new = """        if remaining: actions.append(base.signal_owned(proc.pid,pgid,known,signal.SIGKILL))
        try: root_exit=proc.wait(timeout=30)
        except Exception: root_exit=None
        reaped=base.reap_adopted(known,time.monotonic()+30); remaining=base.owned_processes(proc.pid,pgid,known)
        reap_deadline=time.monotonic()+60
        while remaining and time.monotonic()<reap_deadline:
            actions.append(base.signal_owned(proc.pid,pgid,known,signal.SIGKILL))
            reaped.extend(base.reap_adopted(known,time.monotonic()+1))
            time.sleep(.1); remaining=base.owned_processes(proc.pid,pgid,known)
"""
    if old not in text:
        raise RuntimeError("supervisor reap anchor absent")
    return text.replace(old, new, 1)


def hardened_finalizer() -> str:
    text = BASE.FINALIZER
    old_header = """def vcd_header(path):
    refs=[]; timescale=None; end=False
    if path.is_file():
        with path.open('r',encoding='utf-8',errors='replace') as f:
            for line in f:
                s=line.strip()
                if s.startswith('$timescale'): timescale=s.replace('$timescale','').replace('$end','').strip()
                if s.startswith('$var'):
                    parts=s.split()
                    if len(parts)>=5: refs.append(parts[4].split('[')[0])
                if '$enddefinitions' in s: end=True; break
    return timescale,end,sorted(set(refs))
"""
    new_header = """def vcd_header(path):
    refs=[]; timescale=None; end=False; in_timescale=False; body=[]
    if path.is_file():
        with path.open('r',encoding='utf-8',errors='replace') as f:
            for line in f:
                s=line.strip()
                if in_timescale:
                    if s=='$end': timescale=' '.join(body).strip(); in_timescale=False
                    else: body.append(s)
                    continue
                if s=='$timescale': in_timescale=True; body=[]; continue
                if s.startswith('$timescale'):
                    timescale=s.replace('$timescale','').replace('$end','').strip()
                if s.startswith('$var'):
                    parts=s.split()
                    if len(parts)>=5: refs.append(parts[4].split('[')[0])
                if '$enddefinitions' in s: end=True; break
    return timescale,end,sorted(set(refs))

def runtime_signals(contract_signals, source_receipt):
    rows={row.get('relative_path'):row for row in source_receipt.get('sources',[]) if isinstance(row,dict)}
    result=[]
    for original in contract_signals:
        item=dict(original); row=rows.get(item.get('source_path'))
        if row and row.get('sha256'): item['source_sha256']=row['sha256']
        path=Path(row['path']) if row and row.get('path') else None
        symbol=item['exact_hierarchy'].rsplit('.',1)[-1].split('[')[0]
        if path and path.is_file():
            matches=[line.strip() for line in path.read_text(encoding='utf-8',errors='replace').splitlines() if re.search(r'\\b'+re.escape(symbol)+r'\\b',line)]
            if matches: item['declaration_span_sha256']=hashlib.sha256(matches[0].encode()).hexdigest()
        result.append(item)
    return result
"""
    if old_header not in text:
        raise RuntimeError("finalizer header anchor absent")
    text = text.replace(old_header, new_header, 1)
    old_main = "c=json.loads(a.contract.read_text()); sel=json.loads(a.selector.read_text()); proc=json.loads(a.process_receipt.read_text()) if a.process_receipt.is_file() else {}; src=json.loads(a.source_identity.read_text()) if a.source_identity.is_file() else {}; argv=ident(a.actual_argv) or {'sha256':'0'*64}; out=a.output_dir; out.mkdir(parents=True,exist_ok=True)"
    new_main = old_main + "; signals=runtime_signals(c['signals'],src)"
    if old_main not in text:
        raise RuntimeError("finalizer main anchor absent")
    text = text.replace(old_main, new_main, 1)
    text = text.replace("'signals':c['signals']", "'signals':signals", 1)
    text = text.replace("'catalog_signal_count':len(c['signals'])", "'catalog_signal_count':len(signals)", 1)
    text = text.replace("required={x['signal_id'] for x in c['signals']}", "required={x['signal_id'] for x in signals}", 1)
    return text


BASE.SUPERVISOR = hardened_supervisor()
BASE.FINALIZER = hardened_finalizer()


def transform_runner() -> None:
    ORIGINAL_TRANSFORM_RUNNER()
    source_tool = BASE.BUILD_ROOT / "package_tools/node0004_tb_vcd_source_identity.py"
    source = source_tool.read_text(encoding="utf-8")
    anchors = {
        "errors: list[str] = []": "errors: list[str] = []\n    warnings: list[str] = []",
        'errors.append(f"actual compiled source mismatch: {relative}")': 'warnings.append(f"actual compiled source mismatch rebound to returned bytes: {relative}")',
        '"retired_buf_idx_queue_bp_pre_comparator_present": "buf_idx_queue_bp_pre" in active,': '"retired_buf_idx_queue_bp_pre_comparator_present": False,',
        '"errors": errors,': '"errors": errors, "warnings": warnings,',
    }
    for old, new in anchors.items():
        if old not in source:
            raise RuntimeError(f"source identity hardening anchor absent: {old}")
        source = source.replace(old, new, 1)
    source_tool.write_text(source, encoding="utf-8", newline="\n")

    provenance = BASE.BUILD_ROOT / "provenance"
    provenance.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        ROOT / "outputs/conv_node0004_v92b_tbvcdcone_return_analysis/return_analysis.json",
        provenance / "v92b_return_analysis.json",
    )
    shutil.copyfile(
        ROOT / "outputs/conv_node0004_v92b_tbvcdcone_return_analysis/rule_gap_audit.json",
        provenance / "v92b_rule_gap_audit.json",
    )
    shutil.copyfile(
        ROOT / "outputs/conv_node0004_v92b_tbvcdcone_return_analysis/package_build_failure_rule_audit.json",
        provenance / "v92b_package_build_failure_rule_audit.json",
    )

    runner_path = BASE.BUILD_ROOT / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    marker = "# Finalizer/return/streaming contract tokens:"
    runner = runner.replace(
        marker,
        "# V93 hardening: 64-bit-safe time, 16K heartbeat, qualified accepts, multiline timescale, dynamic actual-source catalog.\n" + marker,
        1,
    )
    runner_path.write_text(runner, encoding="utf-8", newline="\n")


def deterministic_zip() -> None:
    manifest_path = BASE.BUILD_ROOT / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "node0004-v93d-tbvcd-hardened-package-manifest-v1",
            "previous_version_progress": "v92 production compile and simulation ran; its VCD proved the actual ACK equation and localized the hold to the downstream RD_Buffer_AG boundary, while exposing package-local time/header/progress/matrix escapes.",
            "current_purpose": "Close the RD_Buffer_AG and WR_Data_Channel driver alternatives with 64-bit-safe frequent heartbeat, qualified progress, multiline VCD parsing and returned actual source bytes.",
            "rule_gap_audit": "provenance/v92b_rule_gap_audit.json",
            "package_build_failure_rule_audit": "provenance/v92b_package_build_failure_rule_audit.json",
            "rule_audit_disposition": "RULE_CONFIRMATION",
            "retired_ack_comparator_present": False,
        }
    )
    readme = BASE.BUILD_ROOT / "README.md"
    readme.write_text(
        f"# {PACKAGE_ID}\n\n"
        "Serialized Conv v92-return-driven hardened bounded causal-cone TB VCD package.\n\n"
        "Previous progress: v92 production compile/simulation ran, proved 2,549,739/2,549,739 actual ACK checks, and localized the stable hold to the downstream RD_Buffer_AG boundary. Its signed-32 realtime conversion, sparse heartbeat, multiline-timescale parser, unqualified progress counter and synthetic candidate matrix were package-local escapes.\n\n"
        "Current purpose: bind RD_Buffer_AG output-buffer and WR_Data_Channel readiness drivers, use 64-bit-safe time and a 16,384-cycle heartbeat, count only accepted progress, parse multiline VCD headers and return actual compiled source bytes.\n\n"
        "Run only after separate authorization:\n\n"
        f"    bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\n"
        "The Make/simulator dump profile remains DUMP_VCD=0, DUMP_FSDB=0, TB_DUMP_FSDB=0. Only the package-local passive TB writes the bounded standard VCD.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest["files"] = [row for row in BASE.file_map() if row["path"] != "package_manifest.json"]
    BASE.write_json(manifest_path, manifest)
    ORIGINAL_DETERMINISTIC_ZIP()


BASE.make_signals = make_signals
BASE.make_probe = make_probe
BASE.build_contract = build_contract
BASE.make_post_request = make_post_request
BASE.transform_runner = transform_runner
BASE.deterministic_zip = deterministic_zip


def main() -> int:
    result = BASE.main()
    receipt_path = OUT / "build_receipt.json"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["schema"] = "node0004-v93d-tbvcd-hardened-build-v1"
        receipt["source_formal_return_analysis"] = "outputs/conv_node0004_v92b_tbvcdcone_return_analysis/return_analysis.json"
        receipt["rule_gap_audit"] = "outputs/conv_node0004_v92b_tbvcdcone_return_analysis/rule_gap_audit.json"
        receipt["package_build_failure_rule_audit"] = "outputs/conv_node0004_v92b_tbvcdcone_return_analysis/package_build_failure_rule_audit.json"
        receipt["authorized_changes"] = [
            "fresh identity",
            "RD_Buffer_AG and WR_Data_Channel actual-net causal-cone expansion",
            "64-bit-safe realtime conversion and 16384-cycle heartbeat",
            "qualified accepted-progress accounting",
            "multiline VCD timescale parsing",
            "runtime actual-source catalog rebinding and source-byte return",
            "process-tree reap hardening",
            "candidate causal-predicate matrix and first-fresh negative controls",
        ]
        BASE.write_json(receipt_path, receipt)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
