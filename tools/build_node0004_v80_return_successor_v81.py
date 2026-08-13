from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v79_return_successor_v80 as prior

SOURCE = "r5_n4_hw_v80_ack_phase_diag"
INSTALL = "r5_n4_hw_v81_ack_phase_targetfix"
SOURCE_SHA = "cd3dd4f78f1ed75c0fc94b3113f6afb447c507e61fe9d289a20d90854e117a8a"
RETURN_SHA = "292f5a4019f5fe76352a0ab0269c2fd87df0d2b0ef1c1c67a0c95983605f8505"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v80_return_analysis/report.json"
OUT = ROOT / "outputs/conv_node0004_v80_return_v81_successor"
DEFAULT_OUTPUT = OUT / "build"
EPOCH = "20260811-partial-exit-live-causal-record-v1"
base = prior.base

TARGET_INSTANCE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue"
)


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def extract_source(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA:
        raise BuildError("v80 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v80 source CRC differs")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or info.filename in seen or mode == 0o120000:
                raise BuildError(f"unsafe/duplicate source member:{info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"v80 source root differs:{sorted(roots)}")
    target = destination / INSTALL
    target.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if len(pure.parts) <= 1:
                continue
            relative = Path(*pure.parts[1:])
            out = target / relative
            if info.is_dir():
                out.mkdir(parents=True, exist_ok=True)
            else:
                out.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, out.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
    return target


def rebase_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or "provenance" in path.relative_to(package).parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(text.replace(SOURCE, INSTALL), encoding="utf-8", newline="\n")


PHASE_OBSERVER = r'''module codex_probe_buf_ack_phase_target(
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
  integer codex_enabled, codex_limit, codex_count, codex_seq;
  integer codex_half_pending, codex_next_pending, codex_pending_seq;
  localparam string CODEX_TARGET = "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue";

  task automatic codex_emit(input [63:0] phase_name, input integer seq_value);
    $display("CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance=%0s time=%0t mask=1 payload=1 seq=%0d phase=%0s wr=%b full=%b all=%b valid=%h same=%h gotten=%h keep=%h bpmask=%h bp=%h mode=%h row=%h col=%h rowtag=%h coltag=%h",
      CODEX_TARGET, $time, seq_value, phase_name, buf_ag_idx_queue_wr_en,
      buf_ag_idx_queue_full, buf_all_idx_matched, buf_idx_valid_bit_masked,
      buf_idx_same_bit_masked, buf_idx_gotten_bit, buf_idx_bp_pre_keep_mask,
      buf_idx_bp_pre_mask, mse_buf_queue_bp_pre, mse_buf_idx_mode,
      mse_buf_queue_row_idx, mse_buf_queue_col_idx, mse_buf_queue_row_tag,
      mse_buf_queue_col_tag);
  endtask

  initial begin
    codex_enabled = $test$plusargs("CODEX_CAUSAL_OBSERVER");
    if (!$value$plusargs("RETURN_OBS_BUF_ACK_PHASE_LIMIT=%d", codex_limit)) codex_limit = 128;
    codex_count = 0; codex_seq = 0; codex_half_pending = 0; codex_next_pending = 0; codex_pending_seq = 0;
    if (codex_enabled)
      $display("CODEX_PROBE_V1 kind=ENABLED boundary=buf_ack_phase_target instance=%0s feature=RETURN_OBS_BUF_ACK_PHASE limit=%0d", CODEX_TARGET, codex_limit);
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      codex_half_pending = 0; codex_next_pending = 0;
    end else if (codex_enabled) begin
      if (codex_next_pending) begin
        codex_emit("NEXT", codex_pending_seq);
        codex_next_pending = 0;
      end
      if (mse_enable && codex_count < codex_limit &&
          (buf_ag_idx_queue_wr_en === 1'b1) &&
          (buf_ag_idx_queue_full === 1'b0) &&
          (buf_idx_bp_pre_mask === 2'b11) &&
          (mse_buf_queue_bp_pre !== 2'b11)) begin
        codex_pending_seq = codex_seq; codex_seq = codex_seq + 1; codex_count = codex_count + 1;
        codex_half_pending = 1; codex_next_pending = 1;
        codex_emit("ACTIVE", codex_pending_seq);
        #0 codex_emit("INACTIVE", codex_pending_seq);
        #1 codex_emit("POSTNBA", codex_pending_seq);
      end
    end
  end

  always @(negedge clk) begin
    if (codex_enabled && codex_half_pending) begin
      codex_emit("HALF", codex_pending_seq);
      codex_half_pending = 0;
    end
  end

  final begin
    if (codex_enabled)
      $display("CODEX_PROBE_V1 kind=SUMMARY boundary=buf_ack_phase_target instance=%0s count=%0d state=0 first=0 last=%0t maxgap=0 sticky=0 xor=0", CODEX_TARGET, codex_count, $time);
  end
endmodule

`ifndef CODEX_SOURCE_BOUND_FOCUS
bind tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue codex_probe_buf_ack_phase_target codex_probe_buf_ack_phase_target_inst (
  .clk(clk), .rst_n(rst_n), .mse_enable(mse_enable), .mse_buf_idx_mode(mse_buf_idx_mode),
  .buf_ag_idx_queue_wr_en(buf_ag_idx_queue_wr_en), .buf_ag_idx_queue_full(buf_ag_idx_queue_full),
  .buf_all_idx_matched(buf_all_idx_matched), .buf_idx_valid_bit_masked(buf_idx_valid_bit_masked),
  .buf_idx_same_bit_masked(buf_idx_same_bit_masked), .buf_idx_gotten_bit(buf_idx_gotten_bit),
  .buf_idx_bp_pre_keep_mask(buf_idx_bp_pre_keep_mask), .buf_idx_bp_pre_mask(buf_idx_bp_pre_mask),
  .mse_buf_queue_bp_pre(mse_buf_queue_bp_pre), .mse_buf_queue_row_idx(mse_buf_queue_row_idx),
  .mse_buf_queue_col_idx(mse_buf_queue_col_idx), .mse_buf_queue_row_tag(mse_buf_queue_row_tag),
  .mse_buf_queue_col_tag(mse_buf_queue_col_tag)
);
`endif
'''


PHASE_PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
TARGET="tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue"
PHASES=("ACTIVE","INACTIVE","POSTNBA","HALF","NEXT")
LINE=re.compile(r"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance=(?P<instance>\S+) time=(?P<time>\d+) mask=1 payload=1 seq=(?P<seq>\d+) phase=(?P<phase>ACTIVE|INACTIVE|POSTNBA|HALF|NEXT) wr=(?P<wr>[01xXzZ]) full=(?P<full>[01xXzZ]) all=(?P<all>[01xXzZ]) valid=(?P<valid>[0-9a-fA-FxXzZ]+) same=(?P<same>[0-9a-fA-FxXzZ]+) gotten=(?P<gotten>[0-9a-fA-FxXzZ]+) keep=(?P<keep>[0-9a-fA-FxXzZ]+) bpmask=(?P<bpmask>[0-9a-fA-FxXzZ]+) bp=(?P<bp>[0-9a-fA-FxXzZ]+) mode=(?P<mode>[0-9a-fA-FxXzZ]+) row=(?P<row>[0-9a-fA-FxXzZ]+) col=(?P<col>[0-9a-fA-FxXzZ]+) rowtag=(?P<rowtag>[0-9a-fA-FxXzZ]+) coltag=(?P<coltag>[0-9a-fA-FxXzZ]+)")

def main():
  p=argparse.ArgumentParser(); p.add_argument('--log',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
  events=[]; foreign=0
  for line in a.log.read_text(encoding='utf-8',errors='replace').splitlines():
    m=LINE.search(line)
    if not m: continue
    d=m.groupdict()
    if d['instance'] != TARGET: foreign += 1; continue
    d['time']=int(d['time']); d['seq']=int(d['seq']); events.append(d)
  grouped={}; duplicate=False
  for e in events:
    key=(e['instance'],e['seq']); duplicate |= e['phase'] in grouped.setdefault(key,{}); grouped[key][e['phase']]=e
  complete=[v for v in grouped.values() if set(PHASES)<=set(v)]
  classes=[]
  for v in complete:
    active,ina,post,half,nxt=(v[x] for x in PHASES)
    stable_fields=('full','all','valid','same','keep','bpmask','mode','row','col','rowtag','coltag')
    stable=all(active[x]==ina[x]==post[x]==half[x] for x in stable_fields)
    expected=(half['full']=='0' and half['bpmask']=='3')
    if not stable: cls='OPERAND_OR_EPOCH_TRANSITION'
    elif expected and post['bp']=='3' and (post['gotten']=='3' or half['gotten']=='3'): cls='POSTNBA_SETTLE_WITH_SAME_CYCLE_CONSUMER_ACCEPT'
    elif expected and half['bp']=='3' and half['gotten']!='3' and nxt['gotten']=='3': cls='HALF_SETTLE_THEN_NEXT_EDGE_CONSUMER_ACCEPT'
    elif expected and half['bp']=='3' and half['gotten']!='3' and nxt['gotten']!='3': cls='SETTLED_PUBLIC_ACK_BUT_CONSUMER_STALE'
    elif expected and active['bp']!='3' and ina['bp']=='3': cls='INACTIVE_DELTA_SETTLE'
    elif expected and all(v[x]['bp']!='3' for x in PHASES): cls='PERSISTENT_EQUATION_OR_COMPILED_SOURCE_MISMATCH'
    else: cls='UNCLASSIFIED_TARGET_PHASE_SEQUENCE'
    classes.append(cls)
  if duplicate: decision='DUPLICATE_PHASE_FAIL_CLOSED'
  elif not grouped: decision='NO_EXACT_TARGET_LIVE_EVENT'
  elif len(complete)!=len(grouped): decision='INCOMPLETE_EXACT_TARGET_PHASE_SEQUENCE'
  elif len(set(classes))!=1: decision='MULTIPLE_TARGET_PHASE_CLASSES'
  else: decision=classes[0]
  out={'schema':'node0004-buffer-ack-phase-decision-v2','decision':decision,'target_instance':TARGET,'live_event_count':len(events),'foreign_event_count':foreign,'sequence_count':len(grouped),'complete_sequence_count':len(complete),'classes':classes,'sequences':{str(k[1]):v for k,v in grouped.items()},'claim_boundary':'Exact slice13/group1/MSE4 qualified live EVENT phase sequence only; no config, RTL, numeric, natural-terminal or formal-D claim.'}
  a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n',encoding='utf-8')
  print(json.dumps(out,sort_keys=True)); return 0 if complete and not duplicate and decision not in ('MULTIPLE_TARGET_PHASE_CLASSES','UNCLASSIFIED_TARGET_PHASE_SEQUENCE') else 2
if __name__=='__main__': raise SystemExit(main())
'''


PLUGIN = r'''#!/usr/bin/env python3
import argparse, hashlib, json, pathlib, subprocess, sys
p=argparse.ArgumentParser(); p.add_argument('--package-root',type=pathlib.Path,required=True); p.add_argument('--attempt-root',type=pathlib.Path,required=True); p.add_argument('--phase-live-log',type=pathlib.Path,required=True); p.add_argument('--phase-output',type=pathlib.Path,required=True); a=p.parse_args()
full=(a.attempt_root/'evidence/compile_exit_status.txt').is_file()
frozen=None
if full:
  old=a.package_root/'package_tools/node0004_v79_post_sim_plugin.py'
  frozen=subprocess.run([sys.executable,str(old),'--package-root',str(a.package_root),'--attempt-root',str(a.attempt_root)],text=True,capture_output=True,check=False)
  if frozen.returncode: raise RuntimeError('v79 frozen collector failed: '+frozen.stderr)
parsed=subprocess.run([sys.executable,str(a.package_root/'package_tools/buffer_ack_phase_parser.py'),'--log',str(a.phase_live_log),'--output',str(a.phase_output)],text=True,capture_output=True,check=False)
if parsed.returncode or not a.phase_output.is_file(): raise RuntimeError('exact target live phase parser failed: '+parsed.stderr)
value=json.loads(a.phase_output.read_text(encoding='utf-8'))
receipt={'schema':'node0004-buffer-ack-phase-parser-receipt-v2','parser_exit_status':parsed.returncode,'decision':value['decision'],'decision_sha256':hashlib.sha256(a.phase_output.read_bytes()).hexdigest(),'target_instance':value['target_instance'],'live_event_count':value['live_event_count'],'sequence_count':value['sequence_count'],'complete_sequence_count':value['complete_sequence_count']}
(a.attempt_root/'evidence').mkdir(parents=True,exist_ok=True); (a.attempt_root/'evidence/buffer_ack_phase_parser_receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'frozen_v79_collector':None if frozen is None else frozen.stdout.strip(),'buffer_ack_phase':receipt},sort_keys=True))
'''


def fixture() -> str:
    prefix = "wr=1 full=0 all=1 valid=3 same=3"
    suffix = "keep=3 bpmask=3 mode=2 row=1 col=75 rowtag=73 coltag=73"
    rows = []
    values = {
        "ACTIVE": "gotten=0 bp=0", "INACTIVE": "gotten=0 bp=0",
        "POSTNBA": "gotten=3 bp=3", "HALF": "gotten=3 bp=3", "NEXT": "gotten=3 bp=3",
    }
    for i, phase in enumerate(("ACTIVE", "INACTIVE", "POSTNBA", "HALF", "NEXT")):
        gotten, bp = values[phase].split()
        rows.append(f"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target instance={TARGET_INSTANCE} time={100+i} mask=1 payload=1 seq=0 phase={phase} {prefix} {gotten} {suffix.replace(' mode=', ' bp='+bp.split('=')[1]+' mode=')}")
    return "\n".join(rows) + "\n"


def patch_package(package: Path) -> None:
    (package / "tb_probe/buffer_ack_phase_observer.svh").write_text(PHASE_OBSERVER, encoding="utf-8", newline="\n")
    (package / "package_tools/buffer_ack_phase_parser.py").write_text(PHASE_PARSER, encoding="utf-8", newline="\n")
    (package / "package_tools/node0004_v81_post_sim_plugin.py").write_text(PLUGIN, encoding="utf-8", newline="\n")
    shutil.copy2(ROOT / "tools/server_post_sim_return.py", package / "package_tools/server_post_sim_return.py")
    fixture_path = package / "diagnostics/partial_exit_live/buffer_ack_phase_live.log"
    fixture_path.parent.mkdir(parents=True, exist_ok=True); fixture_path.write_text(fixture(), encoding="utf-8", newline="\n")

    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8")); request["package_id"] = INSTALL
    request["plugins"][0]["argv"] = [
        "python3", "{package_root}/package_tools/node0004_v81_post_sim_plugin.py",
        "--package-root", "{package_root}", "--attempt-root", "{attempt_root}",
        "--phase-live-log", "{attempt_root}/c0/sim.log",
        "--phase-output", "{attempt_root}/c0/buffer_ack_phase_decision.json",
    ]
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update({
        "package_id": INSTALL,
        "helper_sha256": base.sha256(package / "package_tools/server_post_sim_return.py"),
        "request_sha256": base.sha256(request_path),
        "partial_exit_live_causal_record": {
            "rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
            "enforcement": "required_next_fresh", "required_signals": ["INT", "TERM"],
            "final_block_ring_sole_input_forbidden": True,
            "plugin_dispositions": [{
                "plugin_id": "node0004_source_bound_collect", "disposition": "LIVE_CAUSAL_FIXTURE",
                "input_root": "attempt", "input_path": "c0/sim.log",
                "fixture_member": "diagnostics/partial_exit_live/buffer_ack_phase_live.log",
                "input_kind": "QUALIFIED_LIVE_RECORD", "output_root": "attempt",
                "output_path": "c0/buffer_ack_phase_decision.json", "expected_exit_code": 0,
                "timeout_seconds": 5,
            }],
        },
        "claim_boundary": "Exact target live causal phase parser is available on INT/TERM; core return remains independent and no natural-terminal, formal-D, E4 or E5 claim is made.",
    })
    write_json(contract_path, contract)


def regenerate_source_bound(package: Path) -> None:
    generator = ROOT / "tools/generate_server_source_bound_observer.py"
    py = Path(sys.executable)
    with tempfile.TemporaryDirectory(prefix="n4v81-source-bound-") as raw:
        temp = Path(raw); generated = temp / "generated"; report_path = temp / "report.json"; cheap = temp / "cheap.json"
        done = subprocess.run([
            str(py), str(generator), "materialize",
            "--catalog", str(package / "diagnostics/source_bound_probe_catalog.json"),
            "--plan", str(package / "diagnostics/source_bound_probe_plan.json"),
            "--output-dir", str(generated), "--report", str(report_path),
            "--cheap-check-output", str(cheap),
        ], text=True, capture_output=True, check=False)
        if done.returncode:
            raise BuildError("current source-bound regeneration failed: " + done.stderr)
        shutil.copy2(generated / "source_bound_causal_observer.svh", package / "tb_probe/source_bound_causal_observer.svh")
        shutil.copy2(generated / "source_bound_causal_parser.py", package / "package_tools/source_bound_causal_parser.py")
        shutil.copy2(generated / "source_bound_probe_binding.json", package / "diagnostics/source_bound_probe_binding.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["catalog"]["path"] = "diagnostics/source_bound_probe_catalog.json"
        report["plan"]["path"] = "diagnostics/source_bound_probe_plan.json"
        write_json(package / "diagnostics/source_bound_observer_generation_report.json", report)
    receipt_path = package / "diagnostics/source_bound_observer_generation.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update({
        "schema": "conv-node0004-v81-source-bound-current-regeneration-v1",
        "package_id": INSTALL,
        "generator_sha256": base.sha256(generator),
        "generation_report_sha256": base.sha256(package / "diagnostics/source_bound_observer_generation_report.json"),
        "changed_surface": ["current generator exact regeneration only; causal plan/catalog unchanged"],
        "status": "PASS",
    })
    write_json(receipt_path, receipt)


def build_directory(output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    package = extract_source(output)
    rebase_identity(package)
    patch_package(package)
    regenerate_source_bound(package)
    base.update_path_budget(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT"
    manifest["first_fresh_extra_audit"] = {
        "epoch_id": EPOCH, "notification_acknowledged": True,
        "first_fresh_after_change": True, "bound_package_id": INSTALL,
        "upload_hold_until_final_audit_pass": True,
    }
    manifest["v80_return_adjudication"] = {
        "formal_return_sha256": RETURN_SHA, "return_analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "V79_SAME_INSTANCE_ACTIVE_EDGE_ACK_EQUATION_CONTRADICTION_REPRODUCED_GLOBALLY_BUT_V80_PHASE_ROWS_NOT_BOUND_TO_THAT_INSTANCE",
        "first_divergence": "V80_PHASE_PARSER_TARGET_SUBSTRING_ACCEPTS_SLICE0_WHILE_REQUIRED_TARGET_IS_SLICE13_GROUP1",
        "root_leaf_status": "PACKAGE_LOCAL_PHASE_OBSERVER_INSTANCE_SCOPE_AND_PAIRING_DEFECT",
    }
    manifest["buffer_ack_phase_diagnostic"] = {
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "target_instance": TARGET_INSTANCE,
        "sample_phases": ["ACTIVE", "INACTIVE_DELTA", "POSTNBA", "HALF_CYCLE", "NEXT_POSEDGE"],
        "record_kind": "QUALIFIED_LIVE_EVENT", "consumer_accept_state": "buf_idx_gotten_bit",
        "runtime_gate": "CODEX_CAUSAL_OBSERVER", "limit_parameter": "+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128",
        "natural_terminal_or_formal_d_claim": False,
    }
    proof = manifest.setdefault("observer_public_surface_or_xmr_proof", {})
    proof["buffer_ack_phase_observer"] = {
        "target_instance": TARGET_INSTANCE, "target_module": "Buffer_AG_Idx_Queue",
        "target_file": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
        "target_file_sha256": "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca",
        "binding": "exact hierarchical instance bind; no sibling wildcard", "clock": "clk", "reset": "rst_n active-low",
    }
    rules = manifest.setdefault("active_receipts", {}).setdefault("rules", [])
    if "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001" not in rules:
        rules.append("CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001")
    manifest.setdefault("active_receipts", {})["source_bound_generator_sha256"] = base.sha256(ROOT / "tools/generate_server_source_bound_observer.py")
    write_json(package / "provenance/v80_return_to_v81_exact_target_phase.json", {
        "schema": "conv-node0004-v80-return-to-v81-exact-target-phase-v1",
        "source_package_zip_sha256": SOURCE_SHA, "formal_return_sha256": RETURN_SHA,
        "return_analysis_sha256": base.sha256(ANALYSIS), "epoch_ack": EPOCH,
        "first_fresh_after_change": True,
        "changed_surface": ["fresh identity", "exact slice13/group1/MSE4 phase observer", "live EVENT phase parser/plugin", "partial-exit live fixture contract", "current shared post-sim helper"],
        "frozen": ["numeric/W3/qparams/tail/workload/config/golden", "timeout/backpressure", "functional RTL/ISA/hardware/active ndp-sim"],
    })
    base.refresh_receipts(manifest)
    # refresh_receipts can replace the rule list; re-assert the new required gate.
    rules = manifest.setdefault("active_receipts", {}).setdefault("rules", [])
    if "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001" not in rules:
        rules.append("CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001")
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package); write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package); write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',type=Path,default=DEFAULT_OUTPUT); a=ap.parse_args()
    out=a.output_root.resolve(); out.mkdir(parents=True,exist_ok=True)
    package=build_directory(out); archive=out/f"{INSTALL}.zip"; base.deterministic_zip(package,archive); digest=base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix='node0004-v81-repeat-') as raw:
        repeat=build_directory(Path(raw)); rz=Path(raw)/f"{INSTALL}.zip"; base.deterministic_zip(repeat,rz)
        if base.sha256(rz)!=digest: raise BuildError('deterministic rebuild differs')
    sidecar=out/f"{INSTALL}.zip.sha256"; sidecar.write_text(f"{digest}  {archive.name}\n",encoding='ascii',newline='\n')
    report={'schema':'conv-node0004-v81-build-v1','status':'PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDIT','package_id':INSTALL,'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':digest,'sidecar':str(sidecar),'deterministic_rebuild_equal':True,'epoch_id':EPOCH,'first_fresh_after_change':True,'numeric_analysis_repeated':False,'workload_rebuilt':False,'configuration_rebuilt':False,'functional_rtl_modified':False,'server_action':False}
    write_json(out/f'{INSTALL}.build.json',report); print(json.dumps(report,indent=2)); return 0

if __name__=='__main__': raise SystemExit(main())
