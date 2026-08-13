from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v77_return_successor_v78 as prior
import tools.generate_server_source_bound_observer as sourcegen


SOURCE = "r5_n4_hw_v78_buffer_input_owner_diag"
INSTALL = "r5_n4_hw_v79_buffer_ack_equation_diag"
SOURCE_SHA = "57044a3aef6208650681fe76076d20700fa267ddf415e91a3beb7d5daf065b56"
RETURN_SHA = "1e6f2f6f4c5af952c903fb0552736cab43a027cbe9eec7a3d69d46cd63ec5b77"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v78_return_analysis/report.json"
OUT = ROOT / "outputs/conv_node0004_v78_return_v79_successor"
DEFAULT_OUTPUT = OUT / "build"
EPOCH = "20260810-first-fresh-extra-audit-v1"
PRIOR_FIRST_FRESH = ROOT / "outputs/conv_node0004_v76_return_v77_successor/first_fresh_extra_audit/validation.json"
base = prior.base
v76 = prior.prior.prior


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


EQUATION_PARSER = r'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

LINE = re.compile(r"CODEX_PROBE_V1 kind=(?P<kind>RING_PROGRESS|RING_POST|EVENT|TRIGGER) boundary=buf_ack_equation_witness instance=(?P<instance>\S+) time=(?P<time>\d+) mask=(?P<mask>[0-9a-fA-F]+) payload=(?P<payload>[0-9a-fA-F]+) seq=(?P<seq>\d+)")
TARGET = "slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0]"

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--log',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args()
    events=[]
    for line in a.log.read_text(encoding='utf-8',errors='replace').splitlines():
        m=LINE.search(line)
        if m and TARGET in m.group('instance'):
            d=m.groupdict(); d['time']=int(d['time']); d['mask_int']=int(d['mask'],16); d['seq']=int(d['seq']); events.append(d)
    writes=[x for x in events if x['mask_int'] & 0x1]
    expected=0x1ff
    full=[x for x in writes if (x['mask_int'] & expected)==expected]
    bp_mask_without_output=[x for x in writes if (x['mask_int'] & 0x40) and not (x['mask_int'] & 0x80)]
    keep_not_ready=[x for x in writes if (x['mask_int'] & 0x1e) == 0x1e and not (x['mask_int'] & 0x20)]
    upstream_not_ready=[x for x in writes if not all(x['mask_int'] & bit for bit in (0x2,0x4,0x8,0x10,0x100))]
    if not writes: decision='NO_TARGET_BUFFER_WRITE_WITNESS'
    elif full: decision='FULL_ACK_EQUATION_VISIBLE_AT_WRITE'
    elif bp_mask_without_output: decision='BP_MASK_PRESENT_BUT_OUTPUT_ACK_ZERO'
    elif keep_not_ready: decision='KEEP_MASK_SUPPRESSES_OUTPUT_ACK'
    elif upstream_not_ready: decision='VALID_MATCH_GOTTEN_OR_MODE_NOT_READY_AT_WRITE'
    else: decision='WRITE_ACK_PHASE_OR_TOKEN_ALIGNMENT_UNRESOLVED'
    value={
      'schema':'node0004-buffer-input-ack-equation-decision-v1','decision':decision,
      'candidate_ids':['NO_TARGET_BUFFER_WRITE_WITNESS','FULL_ACK_EQUATION_VISIBLE_AT_WRITE','BP_MASK_PRESENT_BUT_OUTPUT_ACK_ZERO','KEEP_MASK_SUPPRESSES_OUTPUT_ACK','VALID_MATCH_GOTTEN_OR_MODE_NOT_READY_AT_WRITE','WRITE_ACK_PHASE_OR_TOKEN_ALIGNMENT_UNRESOLVED'],
      'pairwise_distinguishable':True,'class_bits':{
        '0':'queue_write_accept','1':'all_idx_matched','2':'valid_masked_eq_3','3':'same_masked_eq_3','4':'gotten_eq_0','5':'bp_keep_mask_eq_3','6':'bp_mask_eq_3','7':'output_bp_eq_3','8':'mode_eq_2'},
      'target_event_count':len(events),'target_write_witnesses':writes,'full_equation_witnesses':full,
      'claim_boundary':'Exact generated same-instance class bitmap around qualified Buffer_AG queue writes; no numeric, configuration-correction, RTL-defect, natural-terminal or formal-D claim.'
    }
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(value,sort_keys=True)); return 0 if writes else 2
if __name__=='__main__': raise SystemExit(main())
'''


PLUGIN = r'''#!/usr/bin/env python3
import argparse, hashlib, json, pathlib, subprocess, sys
p=argparse.ArgumentParser(); p.add_argument('--package-root',type=pathlib.Path,required=True); p.add_argument('--attempt-root',type=pathlib.Path,required=True); a=p.parse_args()
old=a.package_root/'package_tools/node0004_v78_post_sim_plugin.py'
done=subprocess.run([sys.executable,str(old),'--package-root',str(a.package_root),'--attempt-root',str(a.attempt_root)],text=True,capture_output=True,check=False)
if done.returncode != 0: raise RuntimeError('v78 frozen collector failed: '+done.stderr)
decision=a.attempt_root/'c0/buffer_input_ack_equation_decision.json'
parsed=subprocess.run([sys.executable,str(a.package_root/'package_tools/buffer_input_ack_equation_parser.py'),'--log',str(a.attempt_root/'c0/source_bound_causal.log'),'--output',str(decision)],text=True,capture_output=True,check=False)
if parsed.returncode != 0 or not decision.is_file(): raise RuntimeError('buffer input ack equation parser failed: '+parsed.stderr)
value=json.loads(decision.read_text(encoding='utf-8'))
receipt={'schema':'node0004-buffer-input-ack-equation-parser-receipt-v1','parser_exit_status':parsed.returncode,'decision':value['decision'],'decision_sha256':hashlib.sha256(decision.read_bytes()).hexdigest(),'pairwise_distinguishable':value['pairwise_distinguishable'],'target_write_witness_count':len(value['target_write_witnesses'])}
(a.attempt_root/'evidence/buffer_input_ack_equation_parser_receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps({'frozen_v78_collector_stdout':done.stdout.strip(),'buffer_input_ack_equation':receipt},sort_keys=True))
'''


def eq(signal: str, value: int) -> dict:
    return {"op": "EQ", "symbol_id": signal, "value": value}


def signal(symbol: str) -> dict:
    return {"op": "SIGNAL", "symbol_id": symbol}


def and_(*items: dict) -> dict:
    return {"op": "AND", "args": list(items)}


def patch_source_bound_plan(package: Path) -> dict:
    sb = v76.SB
    plan_path = package / "diagnostics/source_bound_probe_plan.json"
    catalog_path = package / "diagnostics/source_bound_probe_catalog.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    old_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    rtl_root = ROOT / "NDP_copy01/rtl"
    tree_sha = old_catalog["rtl_identity"]["rtl_tree_sha256"]
    catalog = sourcegen.build_catalog(
        rtl_root,
        [
            rtl_root / "includes/NDP_Parameters_expanded.svh",
            rtl_root / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
            rtl_root / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv",
        ],
        tree_sha,
    )
    if catalog.get("valid") is not True:
        raise BuildError("expanded-macro source catalog failed: " + repr(catalog.get("errors")))
    plan["catalog_identity"]["catalog_semantic_sha256"] = sourcegen.semantic_sha256(catalog)
    plan["package_id"] = INSTALL
    boundary_id = "buf_ack_equation_witness"
    if boundary_id not in {x["boundary_id"] for x in plan["boundaries"]}:
        wr = "sym_4762eda4da9264a4c1042286"
        full = "sym_5dd54b4c78705081c7f9bcf0"
        plan["boundaries"].append({
            "boundary_id": boundary_id,
            "target_module": "Buffer_AG_Idx_Queue",
            "role": "internal_match_compute",
            "clock_symbol_id": "sym_667019fb08a2ed0f336ee632",
            "reset": {"symbol_id": "sym_5a13c36922af56707cc4f7c6", "active_low": True},
            "stage_gate": signal("sym_9a373fbf63fbf8f91af5c08a"),
            "classes": [
                {"bit":0,"class_id":"queue_write_accept","predicate":and_(signal(wr),{"op":"NOT","arg":signal(full)}),"progress":True,"trigger":True},
                {"bit":1,"class_id":"all_idx_matched","predicate":signal("sym_91bb65b86e7853a8d1a61ec9"),"progress":False,"trigger":False},
                {"bit":2,"class_id":"valid_masked_eq_3","predicate":eq("sym_86700952bd4c171cd00fe138",3),"progress":False,"trigger":False},
                {"bit":3,"class_id":"same_masked_eq_3","predicate":eq("sym_bd38f2bd007281edf3fc6a7a",3),"progress":False,"trigger":False},
                {"bit":4,"class_id":"gotten_eq_0","predicate":eq("sym_aa214c473058a91b9bcde6c9",0),"progress":False,"trigger":False},
                {"bit":5,"class_id":"bp_keep_mask_eq_3","predicate":eq("sym_dbae1854abac2bc1e9ae3611",3),"progress":False,"trigger":False},
                {"bit":6,"class_id":"bp_mask_eq_3","predicate":eq("sym_33950dbed89cf33867bca73b",3),"progress":False,"trigger":False},
                {"bit":7,"class_id":"output_bp_eq_3","predicate":eq("sym_a75b64666abeb505b35afd73",3),"progress":False,"trigger":False},
                {"bit":8,"class_id":"mode_eq_2","predicate":eq("sym_1076fcf0bd9b4233ace2ff9d",2),"progress":False,"trigger":False},
            ],
            "payload_symbol_ids": [wr, full, "sym_bde609d25de5428db99ba2cf", "sym_91bb65b86e7853a8d1a61ec9"],
        })
        for role in plan.get("role_coverage", []):
            if role.get("role") == "internal_match_compute":
                role.setdefault("boundary_ids", []).append(boundary_id)
        plan["claim_boundary"] += " The added exact Buffer_AG equation witness binds write/full, matched/valid/same/gotten, keep-mask, bp-mask, public bp and mode in one multiclass bitmap."
    sb.mkdir(parents=True, exist_ok=True)
    write_json(sb / "probe_catalog.json", catalog)
    write_json(sb / "probe_plan.json", plan)
    report = sourcegen.materialize(sb / "probe_catalog.json", sb / "probe_plan.json", sb / "generated")
    write_json(sb / "generation_report.json", report)
    if report.get("pass") is not True:
        raise BuildError("source-bound equation regeneration failed: " + repr(report.get("errors")))
    mapping = {
        sb / "probe_catalog.json": package / "diagnostics/source_bound_probe_catalog.json",
        sb / "probe_plan.json": package / "diagnostics/source_bound_probe_plan.json",
        sb / "generated/source_bound_causal_observer.svh": package / "tb_probe/source_bound_causal_observer.svh",
        sb / "generated/source_bound_causal_parser.py": package / "package_tools/source_bound_causal_parser.py",
        sb / "generated/source_bound_probe_binding.json": package / "diagnostics/source_bound_probe_binding.json",
        sb / "generation_report.json": package / "diagnostics/source_bound_observer_generation_report.json",
    }
    for src, dst in mapping.items():
        shutil.copy2(src, dst)
    write_json(package / "diagnostics/source_bound_observer_generation.json", {
        "schema":"conv-node0004-v79-source-bound-generation-v1","status":"PASS","package_id":INSTALL,
        "generator_sha256":base.sha256(ROOT / "tools/generate_server_source_bound_observer.py"),
        "generation_report_sha256":base.sha256(sb / "generation_report.json"),
        "changed_surface":["fresh package identity","added Buffer_AG same-instance ack equation witness"],
    })
    return report


def patch_post_sim(package: Path) -> None:
    (package / "package_tools/node0004_v79_post_sim_plugin.py").write_text(PLUGIN, encoding="utf-8", newline="\n")
    (package / "package_tools/buffer_input_ack_equation_parser.py").write_text(EQUATION_PARSER, encoding="utf-8", newline="\n")
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = INSTALL
    request["plugins"][0]["argv"] = [x.replace("node0004_v78_post_sim_plugin.py", "node0004_v79_post_sim_plugin.py") for x in request["plugins"][0]["argv"]]
    extra = [
        {"archive":"evidence/buffer_input_ack_equation_parser_receipt.json","required":True,"source":"evidence/buffer_input_ack_equation_parser_receipt.json","source_root":"attempt"},
        {"archive":"runs/c0/buffer_input_ack_equation_decision.json","required":True,"source":"c0/buffer_input_ack_equation_decision.json","source_root":"attempt"},
    ]
    have = {x["archive"] for x in request["core_entries"]}
    request["core_entries"].extend(x for x in extra if x["archive"] not in have)
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8")); contract["request_sha256"] = base.sha256(request_path); write_json(contract_path, contract)


def build_directory(output: Path) -> Path:
    prior.SOURCE=SOURCE; prior.INSTALL=INSTALL; prior.SOURCE_SHA=SOURCE_SHA; prior.RETURN_SHA=RETURN_SHA
    prior.SOURCE_ZIP=SOURCE_ZIP; prior.ANALYSIS=ANALYSIS; prior.OUT=OUT; prior.DEFAULT_OUTPUT=DEFAULT_OUTPUT
    original_regen = v76.regenerate_source_bound
    try:
        v76.regenerate_source_bound = patch_source_bound_plan
        package = prior.build_directory(output)
    finally:
        v76.regenerate_source_bound = original_regen
    patch_post_sim(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT"
    manifest["first_fresh_extra_audit"] = {"epoch_id":EPOCH,"notification_acknowledged":True,"first_fresh_after_change":False,"bound_package_id":INSTALL,"prior_first_fresh_pass_receipt":{"path":str(PRIOR_FIRST_FRESH.relative_to(ROOT)).replace('\\','/'),"sha256":base.sha256(PRIOR_FIRST_FRESH)},"upload_hold_until_final_audit_pass":True}
    manifest["v78_return_adjudication"] = {"formal_return_sha256":RETURN_SHA,"return_analysis_sha256":base.sha256(ANALYSIS),"last_proven_good":"FINAL_DESCRIPTOR_EVENT_18_THEN_BUFFER_QUEUE_WRITE_AND_PAYLOAD_ADVANCE","first_divergence":"POST_FINAL_BUFFER_WRITE_INPUT_ACK_KEEP_EQUATION_PHASE","root_leaf_status":"UNRESOLVED"}
    manifest["buffer_input_ack_equation_diagnostic"] = {"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","boundary_id":"buf_ack_equation_witness","class_bitmap_bits":9,"pairwise_distinguishable":True,"natural_terminal_or_formal_d_claim":False}
    write_json(package / "provenance/v78_return_to_v79_buffer_ack_equation.json", {"schema":"conv-node0004-v78-return-to-v79-buffer-ack-equation-v1","source_package_zip_sha256":SOURCE_SHA,"formal_return_sha256":RETURN_SHA,"return_analysis_sha256":base.sha256(ANALYSIS),"epoch_ack":EPOCH,"first_fresh_after_change":False,"changed_surface":["fresh identity","source-bound Buffer_AG equation boundary","equation parser/plugin/return binding"],"frozen":["numeric/W3/qparams/tail/workload/config/golden","timeout/backpressure","functional RTL/ISA/hardware/active ndp-sim"]})
    projected = f"install/cfg_pkg/{INSTALL}/runs/c0/install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    projected_absolute = 96 + 1 + len(projected)
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    write_json(layout_path, layout)
    manifest["path_length_budget"] = {"rule_id":"CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001","declared_target_root_max_chars":96,"longest_projected_relative_path":projected,"longest_projected_relative_path_chars":len(projected),"max_projected_absolute_path_chars":projected_absolute,"absolute_path_limit_chars":240,"pass":projected_absolute <= 240}
    base.refresh_receipts(manifest)
    write_json(manifest_path, manifest); manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest); manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',type=Path,default=DEFAULT_OUTPUT); a=ap.parse_args()
    output=a.output_root.resolve(); output.mkdir(parents=True,exist_ok=True)
    package=build_directory(output); archive=output/f"{INSTALL}.zip"; base.deterministic_zip(package,archive); digest=base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix='node0004-v79-repeat-') as raw:
        repeat=build_directory(Path(raw)); repeat_zip=Path(raw)/f"{INSTALL}.zip"; base.deterministic_zip(repeat,repeat_zip)
        if base.sha256(repeat_zip) != digest: raise BuildError('deterministic rebuild differs')
    sidecar=output/f"{INSTALL}.zip.sha256"; sidecar.write_text(f"{digest}  {archive.name}\n",encoding='ascii',newline='\n')
    report={"schema":"conv-node0004-v79-build-v1","status":"PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDIT","package_id":INSTALL,"zip":str(archive),"zip_bytes":archive.stat().st_size,"zip_sha256":digest,"sidecar":str(sidecar),"deterministic_rebuild_equal":True,"epoch_id":EPOCH,"first_fresh_after_change":False,"prior_first_fresh_pass_sha256":base.sha256(PRIOR_FIRST_FRESH),"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False}
    write_json(output/f"{INSTALL}.build.json",report); print(json.dumps(report,indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())
