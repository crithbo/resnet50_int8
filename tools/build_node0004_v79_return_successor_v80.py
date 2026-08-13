from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v78_return_successor_v79 as prior


SOURCE = "r5_n4_hw_v79_buffer_ack_equation_diag"
INSTALL = "r5_n4_hw_v80_ack_phase_diag"
SOURCE_SHA = "447b5a5647b94d914093ec660134ad99ec5ab5e6fc194227bb4e7e9c21484d65"
RETURN_SHA = "b130f1b0b1bcde8ece6c20f1746f847c68566dd2d60ba210e7dc501a8ceaf571"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v79_return_analysis/report.json"
OUT = ROOT / "outputs/conv_node0004_v79_return_v80_successor"
DEFAULT_OUTPUT = OUT / "build"
EPOCH = "20260810-first-fresh-extra-audit-v1"
PRIOR_FIRST_FRESH = ROOT / "outputs/conv_node0004_v76_return_v77_successor/first_fresh_extra_audit/validation.json"
base = prior.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


PHASE_OBSERVER = r'''module codex_probe_buf_ack_phase_witness(
  input wire clk,
  input wire rst_n,
  input wire mse_enable,
  input wire [1:0] mse_buf_idx_mode,
  input wire buf_ag_idx_queue_wr_en,
  input wire buf_ag_idx_queue_full,
  input wire buf_all_idx_matched,
  input wire [1:0] buf_idx_valid_bit_masked,
  input wire [1:0] buf_idx_same_bit_masked,
  input wire [1:0] buf_idx_gotten_bit,
  input wire [1:0] buf_idx_bp_pre_keep_mask,
  input wire [1:0] buf_idx_bp_pre_mask,
  input wire [1:0] mse_buf_queue_bp_pre,
  input wire [`SE_BUF_ROW_INPORT_IDX_WIDTH-1:0] mse_buf_queue_row_idx,
  input wire [7:0] mse_buf_queue_col_idx,
  input wire [`SE_BUF_INPORT_TAG_WIDTH-1:0] mse_buf_queue_row_tag,
  input wire [`SE_BUF_INPORT_TAG_WIDTH-1:0] mse_buf_queue_col_tag
);
  integer codex_enabled;
  integer codex_limit;
  integer codex_count;
  integer codex_last_seq;
  logic codex_pending;

  task automatic codex_emit(input [47:0] phase_name, input integer seq_value);
    $display("CODEX_PROBE_V1 kind=RING_STATE boundary=buf_ack_phase_witness instance=%m time=%0t mask=0 payload=0 seq=%0d phase=%0s wr=%b full=%b all=%b valid=%h same=%h gotten=%h keep=%h bpmask=%h bp=%h mode=%h row=%h col=%h rowtag=%h coltag=%h",
      $time, seq_value, phase_name, buf_ag_idx_queue_wr_en, buf_ag_idx_queue_full,
      buf_all_idx_matched, buf_idx_valid_bit_masked, buf_idx_same_bit_masked,
      buf_idx_gotten_bit, buf_idx_bp_pre_keep_mask, buf_idx_bp_pre_mask,
      mse_buf_queue_bp_pre, mse_buf_idx_mode, mse_buf_queue_row_idx,
      mse_buf_queue_col_idx, mse_buf_queue_row_tag, mse_buf_queue_col_tag);
  endtask

  initial begin
    codex_enabled = $test$plusargs("CODEX_CAUSAL_OBSERVER");
    if (!$value$plusargs("RETURN_OBS_BUF_ACK_PHASE_LIMIT=%d", codex_limit)) codex_limit = 128;
    codex_count = 0;
    codex_last_seq = 0;
    codex_pending = 0;
    if (codex_enabled)
      $display("CODEX_PROBE_V1 kind=ENABLED boundary=buf_ack_phase_witness instance=%m feature=RETURN_OBS_BUF_ACK_PHASE limit=%0d", codex_limit);
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      codex_pending = 0;
    end else if (codex_enabled && mse_enable && codex_count < codex_limit &&
                 (buf_ag_idx_queue_wr_en === 1'b1) &&
                 (buf_ag_idx_queue_full === 1'b0) &&
                 (buf_idx_bp_pre_mask === 2'b11) &&
                 (mse_buf_queue_bp_pre !== 2'b11)) begin
      codex_last_seq = codex_count;
      codex_count = codex_count + 1;
      codex_pending = 1;
      codex_emit("ACTIVE", codex_last_seq);
      #0 codex_emit("DELTA", codex_last_seq);
    end
  end

  always @(negedge clk) begin
    if (codex_enabled && codex_pending) begin
      codex_emit("STABLE", codex_last_seq);
      codex_pending = 0;
    end
  end

  final begin
    if (codex_enabled)
      $display("CODEX_PROBE_V1 kind=SUMMARY boundary=buf_ack_phase_witness instance=%m count=%0d state=0 first=0 last=%0t maxgap=0 sticky=0 xor=0", codex_count, $time);
  end
endmodule

`ifndef CODEX_SOURCE_BOUND_FOCUS
bind Buffer_AG_Idx_Queue codex_probe_buf_ack_phase_witness codex_probe_buf_ack_phase_witness_inst (
  .clk(clk),
  .rst_n(rst_n),
  .mse_enable(mse_enable),
  .mse_buf_idx_mode(mse_buf_idx_mode),
  .buf_ag_idx_queue_wr_en(buf_ag_idx_queue_wr_en),
  .buf_ag_idx_queue_full(buf_ag_idx_queue_full),
  .buf_all_idx_matched(buf_all_idx_matched),
  .buf_idx_valid_bit_masked(buf_idx_valid_bit_masked),
  .buf_idx_same_bit_masked(buf_idx_same_bit_masked),
  .buf_idx_gotten_bit(buf_idx_gotten_bit),
  .buf_idx_bp_pre_keep_mask(buf_idx_bp_pre_keep_mask),
  .buf_idx_bp_pre_mask(buf_idx_bp_pre_mask),
  .mse_buf_queue_bp_pre(mse_buf_queue_bp_pre),
  .mse_buf_queue_row_idx(mse_buf_queue_row_idx),
  .mse_buf_queue_col_idx(mse_buf_queue_col_idx),
  .mse_buf_queue_row_tag(mse_buf_queue_row_tag),
  .mse_buf_queue_col_tag(mse_buf_queue_col_tag)
);
`endif
'''


PHASE_PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

LINE = re.compile(
 r"CODEX_PROBE_V1 kind=RING_STATE boundary=buf_ack_phase_witness instance=(?P<instance>\S+) "
 r"time=(?P<time>\d+) mask=\S+ payload=\S+ seq=(?P<seq>\d+) phase=(?P<phase>ACTIVE|DELTA|STABLE) "
 r"wr=(?P<wr>[01xXzZ]) full=(?P<full>[01xXzZ]) all=(?P<all>[01xXzZ]) "
 r"valid=(?P<valid>[0-9a-fA-FxXzZ]+) same=(?P<same>[0-9a-fA-FxXzZ]+) gotten=(?P<gotten>[0-9a-fA-FxXzZ]+) "
 r"keep=(?P<keep>[0-9a-fA-FxXzZ]+) bpmask=(?P<bpmask>[0-9a-fA-FxXzZ]+) bp=(?P<bp>[0-9a-fA-FxXzZ]+) "
 r"mode=(?P<mode>[0-9a-fA-FxXzZ]+) row=(?P<row>[0-9a-fA-FxXzZ]+) col=(?P<col>[0-9a-fA-FxXzZ]+) "
 r"rowtag=(?P<rowtag>[0-9a-fA-FxXzZ]+) coltag=(?P<coltag>[0-9a-fA-FxXzZ]+)"
)
TARGET = "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue"

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--log',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    events=[]
    for line in a.log.read_text(encoding='utf-8',errors='replace').splitlines():
        m=LINE.search(line)
        if m and TARGET in m.group('instance'):
            d=m.groupdict(); d['time']=int(d['time']); d['seq']=int(d['seq']); events.append(d)
    grouped={}
    for event in events: grouped.setdefault(event['seq'],{})[event['phase']]=event
    complete=[value for value in grouped.values() if {'ACTIVE','DELTA','STABLE'} <= set(value)]
    active_only=[]; delta_only=[]; settled_consumed=[]; settled_not_consumed=[]; persistent=[]; operand_transition=[]
    for value in complete:
        active,delta,stable=value['ACTIVE'],value['DELTA'],value['STABLE']
        if delta['bp']=='3' and stable['bp']=='3':
            if stable['gotten']=='3': settled_consumed.append(value)
            else: settled_not_consumed.append(value)
            if active['bp']!='3': active_only.append(value)
        elif delta['bp']!='3' and stable['bp']=='3': delta_only.append(value)
        elif stable['full']=='0' and stable['bpmask']=='3' and stable['bp']!='3': persistent.append(value)
        else: operand_transition.append(value)
    if not grouped: decision='NO_TARGET_PHASE_WITNESS'
    elif len(complete) != len(grouped): decision='PHASE_WITNESS_INCOMPLETE'
    elif persistent: decision='PERSISTENT_PUBLIC_ACK_EQUATION_MISMATCH'
    elif settled_not_consumed: decision='ACK_SETTLES_BUT_INPUT_CONSUMER_DOES_NOT_ACCEPT'
    elif settled_consumed and len(settled_consumed)==len(complete): decision='ACTIVE_SAMPLE_TRANSIENT_SETTLES_AND_CONSUMER_ACCEPTS'
    elif delta_only: decision='MULTI_DELTA_SETTLES_BEFORE_HALF_CYCLE'
    elif operand_transition: decision='OPERAND_TRANSITION_EXPLAINS_ACTIVE_MISMATCH'
    else: decision='PHASE_RESULT_UNCLASSIFIED'
    out={
      'schema':'node0004-buffer-ack-phase-decision-v1','decision':decision,
      'candidate_ids':['NO_TARGET_PHASE_WITNESS','PHASE_WITNESS_INCOMPLETE','PERSISTENT_PUBLIC_ACK_EQUATION_MISMATCH','ACK_SETTLES_BUT_INPUT_CONSUMER_DOES_NOT_ACCEPT','ACTIVE_SAMPLE_TRANSIENT_SETTLES_AND_CONSUMER_ACCEPTS','MULTI_DELTA_SETTLES_BEFORE_HALF_CYCLE','OPERAND_TRANSITION_EXPLAINS_ACTIVE_MISMATCH','PHASE_RESULT_UNCLASSIFIED'],
      'pairwise_distinguishable':True,'event_count':len(events),'sequence_count':len(grouped),'complete_sequence_count':len(complete),
      'counts':{'active_only_transient':len(active_only),'delta_only_transient':len(delta_only),'settled_and_consumed':len(settled_consumed),'settled_not_consumed':len(settled_not_consumed),'persistent':len(persistent),'operand_transition':len(operand_transition)},
      'sequences':grouped,
      'claim_boundary':'Read-only active, inactive-delta and half-cycle stable snapshots of the exact target Buffer_AG acknowledgement equation and gotten state; no numeric, configuration-correction, RTL-defect, natural-terminal or formal-D claim.'}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(out,sort_keys=True)); return 0 if complete else 2
if __name__=='__main__': raise SystemExit(main())
'''


PLUGIN = r'''#!/usr/bin/env python3
import argparse, hashlib, json, pathlib, subprocess, sys
p=argparse.ArgumentParser(); p.add_argument('--package-root',type=pathlib.Path,required=True); p.add_argument('--attempt-root',type=pathlib.Path,required=True); a=p.parse_args()
old=a.package_root/'package_tools/node0004_v79_post_sim_plugin.py'
done=subprocess.run([sys.executable,str(old),'--package-root',str(a.package_root),'--attempt-root',str(a.attempt_root)],text=True,capture_output=True,check=False)
if done.returncode != 0: raise RuntimeError('v79 frozen collector failed: '+done.stderr)
decision=a.attempt_root/'c0/buffer_ack_phase_decision.json'
parsed=subprocess.run([sys.executable,str(a.package_root/'package_tools/buffer_ack_phase_parser.py'),'--log',str(a.attempt_root/'c0/source_bound_causal.log'),'--output',str(decision)],text=True,capture_output=True,check=False)
if parsed.returncode != 0 or not decision.is_file(): raise RuntimeError('buffer ack phase parser failed: '+parsed.stderr)
value=json.loads(decision.read_text(encoding='utf-8'))
receipt={'schema':'node0004-buffer-ack-phase-parser-receipt-v1','parser_exit_status':parsed.returncode,'decision':value['decision'],'decision_sha256':hashlib.sha256(decision.read_bytes()).hexdigest(),'pairwise_distinguishable':value['pairwise_distinguishable'],'sequence_count':value['sequence_count'],'complete_sequence_count':value['complete_sequence_count']}
(a.attempt_root/'evidence/buffer_ack_phase_parser_receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'frozen_v79_collector_stdout':done.stdout.strip(),'buffer_ack_phase':receipt},sort_keys=True))
'''


def patch_package(package: Path) -> None:
    (package / "tb_probe/buffer_ack_phase_observer.svh").write_text(PHASE_OBSERVER, encoding="utf-8", newline="\n")
    (package / "package_tools/buffer_ack_phase_parser.py").write_text(PHASE_PARSER, encoding="utf-8", newline="\n")
    (package / "package_tools/node0004_v80_post_sim_plugin.py").write_text(PLUGIN, encoding="utf-8", newline="\n")
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    old_compile = "$package_root/tb_probe/source_bound_causal_observer.svh\""
    new_compile = "$package_root/tb_probe/source_bound_causal_observer.svh $package_root/tb_probe/buffer_ack_phase_observer.svh\""
    if text.count(old_compile) != 1:
        raise BuildError("unexpected source-bound compile handoff count")
    text = text.replace(old_compile, new_compile)
    old_limit = "+CODEX_CAUSAL_OBSERVER +RETURN_OBS_SLICE=0"
    new_limit = "+CODEX_CAUSAL_OBSERVER +RETURN_OBS_BUF_ACK_PHASE_LIMIT=128 +RETURN_OBS_SLICE=0"
    if text.count(old_limit) != 1:
        raise BuildError("simulator argv receipt handoff count mismatch")
    text = text.replace(old_limit, new_limit)
    old_run = "+CODEX_CAUSAL_OBSERVER   +RETURN_OBS_SLICE=0"
    new_run = "+CODEX_CAUSAL_OBSERVER +RETURN_OBS_BUF_ACK_PHASE_LIMIT=128   +RETURN_OBS_SLICE=0"
    if text.count(old_run) != 1:
        raise BuildError("actual simulator argv handoff count mismatch")
    text = text.replace(old_run, new_run)
    runner.write_text(text, encoding="utf-8", newline="\n")

    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = INSTALL
    old_plugin = request["plugins"][0]["argv"]
    request["plugins"][0]["argv"] = [x.replace("node0004_v79_post_sim_plugin.py", "node0004_v80_post_sim_plugin.py") for x in old_plugin]
    extra = [
        {"archive":"evidence/buffer_ack_phase_parser_receipt.json","required":True,"source":"evidence/buffer_ack_phase_parser_receipt.json","source_root":"attempt"},
        {"archive":"runs/c0/buffer_ack_phase_decision.json","required":True,"source":"c0/buffer_ack_phase_decision.json","source_root":"attempt"},
    ]
    have = {x["archive"] for x in request["core_entries"]}
    request["core_entries"].extend(x for x in extra if x["archive"] not in have)
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["request_sha256"] = base.sha256(request_path)
    write_json(contract_path, contract)


def build_directory(output: Path) -> Path:
    prior.SOURCE = SOURCE
    prior.INSTALL = INSTALL
    prior.SOURCE_SHA = SOURCE_SHA
    prior.RETURN_SHA = RETURN_SHA
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.ANALYSIS = ANALYSIS
    prior.OUT = OUT
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    package = prior.build_directory(output)
    patch_package(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT"
    manifest["first_fresh_extra_audit"] = {
        "epoch_id": EPOCH,
        "notification_acknowledged": True,
        "first_fresh_after_change": False,
        "bound_package_id": INSTALL,
        "prior_first_fresh_pass_receipt": {
            "path": str(PRIOR_FIRST_FRESH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": base.sha256(PRIOR_FIRST_FRESH),
        },
        "upload_hold_until_final_audit_pass": True,
    }
    manifest["v79_return_adjudication"] = {
        "formal_return_sha256": RETURN_SHA,
        "return_analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "SAME_INSTANCE_BUFFER_WRITE_ACCEPT_WITH_NOT_FULL_AND_BP_MASK_EQ3",
        "first_divergence": "SAME_ACTIVE_EDGE_PUBLIC_BP_VECTOR_NOT_EQ3_DESPITE_NOT_FULL_AND_BP_MASK_EQ3",
        "root_leaf_status": "UNRESOLVED_ACTIVE_REGION_DELTA_SETTLING_VS_CONSUMER_VISIBLE_ACK",
    }
    manifest["buffer_ack_phase_diagnostic"] = {
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "boundary_id": "buf_ack_phase_witness",
        "sample_phases": ["ACTIVE", "DELTA", "STABLE_HALF_CYCLE"],
        "consumer_accept_state": "buf_idx_gotten_bit",
        "runtime_gate": "CODEX_CAUSAL_OBSERVER",
        "limit_parameter": "+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128",
        "pairwise_distinguishable": True,
        "natural_terminal_or_formal_d_claim": False,
    }
    manifest["observer_public_surface_or_xmr_proof"]["buffer_ack_phase_observer"] = {
        "target_module": "Buffer_AG_Idx_Queue",
        "target_file": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        "target_file_sha256": "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca",
        "binding": "module-local bind ports; no hierarchical sibling XMR",
        "clock": "clk",
        "reset": "rst_n active-low",
        "private_leaf_reason": "queue full, match masks and gotten state have no equivalent exported module interface and are required to distinguish active/delta/stable acknowledgement semantics",
    }
    write_json(
        package / "provenance/v79_return_to_v80_ack_phase.json",
        {
            "schema": "conv-node0004-v79-return-to-v80-ack-phase-v1",
            "source_package_zip_sha256": SOURCE_SHA,
            "formal_return_sha256": RETURN_SHA,
            "return_analysis_sha256": base.sha256(ANALYSIS),
            "epoch_ack": EPOCH,
            "first_fresh_after_change": False,
            "changed_surface": [
                "fresh identity",
                "package-local module-bound active/delta/stable Buffer_AG acknowledgement witness",
                "phase parser/plugin/return binding",
                "compile handoff for one additional package-local HDL file",
            ],
            "frozen": [
                "numeric/W3/qparams/tail/workload/config/golden",
                "timeout/backpressure",
                "functional RTL/ISA/hardware/active ndp-sim",
            ],
        },
    )
    base.refresh_receipts(manifest)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = build_directory(output)
    archive = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v80-repeat-") as raw:
        repeat = build_directory(Path(raw))
        repeat_zip = Path(raw) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        if base.sha256(repeat_zip) != digest:
            raise BuildError("deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-node0004-v80-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDIT",
        "package_id": INSTALL,
        "zip": str(archive),
        "zip_bytes": archive.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": True,
        "epoch_id": EPOCH,
        "first_fresh_after_change": False,
        "prior_first_fresh_pass_sha256": base.sha256(PRIOR_FIRST_FRESH),
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
