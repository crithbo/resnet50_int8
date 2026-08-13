from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v76_return_successor_v77 as prior


SOURCE = "r5_n4_hw_v77_terminal_temporal_ledger_diag"
INSTALL = "r5_n4_hw_v78_buffer_input_owner_diag"
SOURCE_SHA = "316d5d2a50ae3378cd7809963e5a9bb54a38e5f07763d512864e02945dcd4d91"
RETURN_SHA = "39d25e0fb99f790e019749d0d463c36a4be0d78ab5089c7ab9445efdb2b935bf"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v77_return_analysis/report.json"
OUT = ROOT / "outputs/conv_node0004_v77_return_v78_successor"
DEFAULT_OUTPUT = OUT / "build"
EPOCH = "20260810-first-fresh-extra-audit-v1"
PRIOR_FIRST_FRESH = ROOT / "outputs/conv_node0004_v76_return_v77_successor/first_fresh_extra_audit/validation.json"
base = prior.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


OWNER_PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

TOKEN = re.compile(
    r"^(?P<time>\d+) \| TOKEN_ORIGIN_ACCEPT_EDGE_V2 .*?buf_wr_ev=(?P<wr>[01]).*?"
    r"buf_pop_ev=(?P<pop>[01]).*?desc_ev=(?P<desc_ev>[01]).*?desc=(?P<desc>\d+).*?buf_row_tag=(?P<row>[0-9a-fx]+) "
    r"buf_col_tag=(?P<col>[0-9a-fx]+) buf_bp=(?P<bp>[0-9a-fx]+) buf_qwr=(?P<qwr>[0-9a-fx]+)"
)
ROW = re.compile(
    r"^(?P<time>\d+) \| ROWLC4_BUFAG_EDGE_V1 .*?buf_valid=0x(?P<valid>[0-9a-fx]+) "
    r"buf_same=0x(?P<same>[0-9a-fx]+) buf_gotten=0x(?P<gotten>[0-9a-fx]+) "
    r"buf_bp=0x(?P<bp>[0-9a-fx]+).*?bufq_full=(?P<full>[01])"
)
DTERM = re.compile(r"DTERM_OWNER_BOUNDARY_V1 .*?buf_mode=(?P<mode>[0-9a-fx]+) buf_keep=(?P<keep>[0-9a-fx]+)")

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--log',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    tokens=[]; rows={}; mode=None; keep=None
    for line in a.log.read_text(encoding='utf-8',errors='replace').splitlines():
        m=TOKEN.search(line)
        if m:
            x=m.groupdict(); x.update({k:int(x[k]) for k in ('time','wr','pop','desc_ev','desc')}); tokens.append(x)
        m=ROW.search(line)
        if m: rows[int(m.group('time'))]=m.groupdict()
        m=DTERM.search(line)
        if m: mode=m.group('mode'); keep=m.group('keep')
    final=next((x for x in tokens if x['desc_ev'] and x['desc']==18),None)
    post=[x for x in tokens if final and x['time']>=final['time'] and x['wr']]
    enriched=[]
    for x in post:
        y=dict(x); y['row_state']=rows.get(x['time']); enriched.append(y)
    noack=[x for x in enriched if x['bp']=='0']
    follow_ack=False; payload_changed=False
    for left,right in zip(enriched,enriched[1:]):
        if left['bp']=='0' and right['bp']!='0' and left['row']==right['row'] and left['col']==right['col']:
            follow_ack=True; payload_changed=left['qwr']!=right['qwr']
    if final is None:
        decision='FINAL_DESCRIPTOR_NOT_OBSERVED'
    elif noack and follow_ack and payload_changed:
        decision='BUFFER_WRITE_PRECEDES_INPUT_ACK_THEN_NEXT_PAYLOAD_ACCEPTS'
    elif noack:
        decision='BUFFER_WRITE_WITHOUT_INPUT_ACK'
    elif post:
        decision='POST_FINAL_BUFFER_WRITES_ALL_INPUT_ACKED'
    else:
        decision='FINAL_DESCRIPTOR_WITH_RESIDUAL_DRAIN_ONLY'
    value={
      'schema':'node0004-post-final-buffer-input-owner-decision-v1',
      'decision':decision,
      'candidate_ids':['FINAL_DESCRIPTOR_NOT_OBSERVED','BUFFER_WRITE_PRECEDES_INPUT_ACK_THEN_NEXT_PAYLOAD_ACCEPTS','BUFFER_WRITE_WITHOUT_INPUT_ACK','POST_FINAL_BUFFER_WRITES_ALL_INPUT_ACKED','FINAL_DESCRIPTOR_WITH_RESIDUAL_DRAIN_ONLY'],
      'pairwise_distinguishable':True,
      'expected_final_descriptor_count':18,
      'buffer_mode_hex':mode,'buffer_keep_threshold_hex':keep,
      'final_descriptor_event':final,'post_final_buffer_write_events':enriched,
      'claim_boundary':'Qualified existing observer edges plus exact cumulative descriptor count; no configuration correctness, RTL defect, natural-terminal or formal-D claim.'
    }
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(value,sort_keys=True)); return 0 if final is not None and mode is not None and keep is not None else 2
if __name__=='__main__': raise SystemExit(main())
'''


PLUGIN = r'''#!/usr/bin/env python3
import argparse, hashlib, importlib.util, json, pathlib, subprocess, sys
p=argparse.ArgumentParser(); p.add_argument('--package-root',type=pathlib.Path,required=True); p.add_argument('--attempt-root',type=pathlib.Path,required=True); a=p.parse_args()
runtime=a.package_root/'package_tools/node0004_hang_localization_runtime.py'
subprocess.run([sys.executable,str(runtime),'analyze','--package-root',str(a.package_root),'--evidence-root',str(a.attempt_root/'evidence'),'--run-root',str(a.attempt_root)],check=True)
tools=a.package_root/'package_tools'; sys.path.insert(0,str(tools)); spec=importlib.util.spec_from_file_location('v78rt',tools/'node0004_hang_localization_runtime_v7.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
r=m._prepare_source_bound_products(a.attempt_root); (a.attempt_root/'evidence/source_bound_parser_receipt.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf-8')
decision=a.attempt_root/'c0/post_final_buffer_input_owner_decision.json'
done=subprocess.run([sys.executable,str(tools/'post_final_buffer_input_owner_parser.py'),'--log',str(a.attempt_root/'c0/return_observer.log'),'--output',str(decision)],text=True,capture_output=True,check=False)
if done.returncode != 0 or not decision.is_file(): raise RuntimeError('post-final input-owner parser failed: '+done.stderr)
value=json.loads(decision.read_text(encoding='utf-8'))
receipt={'schema':'node0004-post-final-buffer-input-owner-parser-receipt-v1','parser_exit_status':done.returncode,'decision':value['decision'],'decision_sha256':hashlib.sha256(decision.read_bytes()).hexdigest(),'pairwise_distinguishable':value['pairwise_distinguishable']}
(a.attempt_root/'evidence/post_final_buffer_input_owner_parser_receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
r['post_final_buffer_input_owner_decision']=value['decision']; print(json.dumps(r,sort_keys=True))
'''


def patch_runtime(package: Path) -> None:
    # v77 already contains the accepted bounded target-complete collector.
    return None


def patch_plugin(package: Path) -> None:
    old = package / "package_tools/node0004_v77_post_sim_plugin.py"
    if old.exists():
        old.unlink()
    new = package / "package_tools/node0004_v78_post_sim_plugin.py"
    new.write_text(PLUGIN, encoding="utf-8", newline="\n")
    parser_path = package / "package_tools/post_final_buffer_input_owner_parser.py"
    parser_path.write_text(OWNER_PARSER, encoding="utf-8", newline="\n")
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = INSTALL
    request["plugins"][0]["argv"] = [
        item.replace("node0004_v77_post_sim_plugin.py", "node0004_v78_post_sim_plugin.py")
        for item in request["plugins"][0]["argv"]
    ]
    for item in (
        {"archive":"evidence/post_final_buffer_input_owner_parser_receipt.json","required":False,"source":"evidence/post_final_buffer_input_owner_parser_receipt.json","source_root":"attempt"},
        {"archive":"runs/c0/post_final_buffer_input_owner_decision.json","required":False,"source":"c0/post_final_buffer_input_owner_decision.json","source_root":"attempt"},
    ):
        if item["archive"] not in {entry["archive"] for entry in request["core_entries"]}:
            request["core_entries"].append(item)
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["request_sha256"] = base.sha256(request_path)
    write_json(contract_path, contract)


def build_directory(output: Path) -> Path:
    prior.SOURCE = SOURCE; prior.INSTALL = INSTALL; prior.SOURCE_ZIP_SHA = SOURCE_SHA
    prior.RETURN_SHA = RETURN_SHA; prior.SOURCE_ZIP = SOURCE_ZIP; prior.ANALYSIS = ANALYSIS
    prior.OUT = OUT; prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    old_runtime, old_plugin = prior.patch_runtime, prior.patch_plugin
    try:
        prior.patch_runtime, prior.patch_plugin = patch_runtime, patch_plugin
        package = prior.build_directory(output)
    finally:
        prior.patch_runtime, prior.patch_plugin = old_runtime, old_plugin
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    projected_longest = (
        f"install/cfg_pkg/{INSTALL}/runs/c0/install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    projected_absolute = 96 + 1 + len(projected_longest)
    if projected_absolute > 240:
        raise BuildError("v78 projected runtime path exceeds 240 characters")
    layout_contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout_contract = json.loads(layout_contract_path.read_text(encoding="utf-8"))
    layout_contract["path_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    write_json(layout_contract_path, layout_contract)
    manifest["path_length_budget"] = {
        "rule_id": "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
        "declared_target_root_max_chars": 96,
        "longest_projected_relative_path": projected_longest,
        "longest_projected_relative_path_chars": len(projected_longest),
        "max_projected_absolute_path_chars": projected_absolute,
        "absolute_path_limit_chars": 240,
        "pass": True,
    }
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT"
    manifest["first_fresh_extra_audit"] = {
        "epoch_id": EPOCH,
        "notification_acknowledged": True,
        "first_fresh_after_change": False,
        "bound_package_id": INSTALL,
        "prior_first_fresh_pass_receipt": {"path": str(PRIOR_FIRST_FRESH.relative_to(ROOT)).replace('\\','/'), "sha256": base.sha256(PRIOR_FIRST_FRESH)},
        "upload_hold_until_final_audit_pass": True,
    }
    manifest["v77_return_adjudication"] = {
        "formal_return_sha256": RETURN_SHA,
        "return_analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "MEMORY_BRANCH_LOCAL_TERMINAL_AND_QUEUE_DRAIN_9_OF_9_WHILE_BUFFER_BRANCH_CONTINUES_QUALIFIED_PROGRESS",
        "first_divergence": "AFTER_MEMORY_LOCAL_TERMINAL_BUFFER_QUEUE_ACCEPTS_EIGHT_MORE_ENTRIES_AND_RETAINS_FOUR_WITH_NO_NATURAL_D_RELEASE",
        "unique_observed_class": "BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH",
        "root_leaf_status": "UNRESOLVED",
    }
    manifest["post_final_buffer_input_owner_diagnostic"] = {
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "expected_final_descriptor_count": 18,
        "inputs": ["TOKEN_ORIGIN_ACCEPT_EDGE_V2", "ROWLC4_BUFAG_EDGE_V1", "DTERM_OWNER_BOUNDARY_V1"],
        "candidate_ids": ["FINAL_DESCRIPTOR_NOT_OBSERVED","BUFFER_WRITE_PRECEDES_INPUT_ACK_THEN_NEXT_PAYLOAD_ACCEPTS","BUFFER_WRITE_WITHOUT_INPUT_ACK","POST_FINAL_BUFFER_WRITES_ALL_INPUT_ACKED","FINAL_DESCRIPTOR_WITH_RESIDUAL_DRAIN_ONLY"],
        "pairwise_distinguishable": True,
        "natural_terminal_or_formal_d_claim": False,
    }
    write_json(package / "provenance/v77_return_to_v78_buffer_input_owner.json", {
        "schema":"conv-node0004-v77-return-to-v78-buffer-input-owner-v1",
        "source_package_zip_sha256":SOURCE_SHA,"formal_return_sha256":RETURN_SHA,
        "return_analysis_sha256":base.sha256(ANALYSIS),"epoch_ack":EPOCH,"first_fresh_after_change":False,
        "changed_surface":["fresh identity","post-final input-owner parser/plugin/return binding"],
        "frozen":["numeric/W3/qparams/tail/workload/config/golden","timeout/backpressure","functional RTL/ISA/hardware/active ndp-sim"]
    })
    base.refresh_receipts(manifest)
    write_json(manifest_path, manifest); manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest); manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',type=Path,default=DEFAULT_OUTPUT); a=ap.parse_args()
    output=a.output_root.resolve(); output.mkdir(parents=True,exist_ok=True)
    package=build_directory(output); archive=output/f"{INSTALL}.zip"; base.deterministic_zip(package,archive); sha=base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix='node0004-v78-repeat-') as temp:
        repeat=build_directory(Path(temp)); repeat_zip=Path(temp)/f"{INSTALL}.zip"; base.deterministic_zip(repeat,repeat_zip)
        if base.sha256(repeat_zip)!=sha: raise BuildError('deterministic rebuild differs')
    sidecar=output/f"{INSTALL}.zip.sha256"; sidecar.write_text(f"{sha}  {archive.name}\n",encoding='ascii',newline='\n')
    report={'schema':'conv-node0004-v78-build-v1','status':'PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDIT','package_id':INSTALL,'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':sha,'sidecar':str(sidecar),'deterministic_rebuild_equal':True,'epoch_id':EPOCH,'first_fresh_after_change':False,'prior_first_fresh_pass_sha256':base.sha256(PRIOR_FIRST_FRESH),'numeric_analysis_repeated':False,'workload_rebuilt':False,'configuration_rebuilt':False,'functional_rtl_modified':False,'server_action':False}
    write_json(output/f"{INSTALL}.build.json",report); print(json.dumps(report,indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())
