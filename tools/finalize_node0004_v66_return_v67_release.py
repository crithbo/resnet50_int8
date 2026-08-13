from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/conv_node0004_v66_return_v67_successor'
BUILD=OUT/'build_retry'
ZIP=BUILD/'r5_n4_hw_v67_pe1_pair_diag.zip'
SIDECAR=BUILD/'r5_n4_hw_v67_pe1_pair_diag.zip.sha256'
FILES={
 'return_analysis':ROOT/'outputs/conv_node0004_v66_return_analysis/report.json',
 'return_analyzer':ROOT/'tools/analyze_node0004_v66_epoch_owner_return.py',
 'builder':ROOT/'tools/build_node0004_v66_pe1_pair_successor_v67.py',
 'build_report':BUILD/'r5_n4_hw_v67_pe1_pair_diag.build.json',
 'observer_validator':ROOT/'tools/validate_node0004_v67_pe1_pair.py',
 'observer_report':OUT/'v67_pe1_pair_validation.json',
 'family_report':OUT/'v67_family_validation.json',
 'shared_report':OUT/'v67_shared_validation.json',
 'shared_harness':OUT/'v67_shared_harness.json',
 'runner_report':OUT/'v67_runner_visibility.json',
 'return_contract':OUT/'v67_return_contract_validation.json',
 'final_auditor':ROOT/'tools/audit_node0004_v67_final_zip.py',
 'final_audit':OUT/'v67_final_zip_audit.json'}
def sha(p:Path):return hashlib.sha256(p.read_bytes()).hexdigest()
def rec(p:Path):return {'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
analysis=json.loads(FILES['return_analysis'].read_text(encoding='utf-8')); audit=json.loads(FILES['final_audit'].read_text(encoding='utf-8'))
report={'schema':'node0004-v66-return-v67-release-v1','status':'PACKAGE_READY_NOT_RUN','return_analysis':{'status':analysis['status'],'last_proven_good':analysis['last_proven_good'],'first_divergence':analysis['first_divergence'],'hang_root_cause':analysis['hang_root_cause'],'formal_result':analysis['formal_result'],'blocker_delta':analysis['blocker_delta']},'package_release':{'id':'r5_n4_hw_v67_pe1_pair_diag','classification':'DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX','candidate_release':False,'zip':rec(ZIP),'sidecar':rec(SIDECAR),'command':'bash r5_n4_hw_v67_pe1_pair_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x','expected_return':'/home/panqs/ndp/simresult/r5_n4_hw_v67_pe1_pair_diag_r<epoch-ns>_<pid>_return.zip','final_zip_rule_self_audit_pass':audit['FINAL_ZIP_RULE_SELF_AUDIT_PASS'],'errors':audit['errors'],'release_gate_matrix':audit['release_gate_matrix']},'evidence':{k:rec(v) for k,v in FILES.items()},'rule_confirmation':'CURRENT_RULES_SUFFICIENT','rule_delta_proposal':None,'frozen':{'numeric_analysis_repeated':False,'workload_rebuilt':False,'configuration_rebuilt':False,'golden_rebuilt':False,'timeout_or_backpressure_changed':False,'functional_rtl_modified':False,'server_action':False},'provenance':{'owner':'019fa2c1-17df-7122-bcbd-a727aaf173f5','return_target':'019fbec2-fe93-7e03-9314-cff6f222f33d'}}
rp=OUT/'release_report.json'; rp.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
task=ROOT/'.agents/task_records/20260808_conv_node0004_v66_return_v67_pe1_pair_successor.md'
task.write_text(f'''# Conv node0004 v66 return -> v67 PE1 pair successor

- Formal return SHA: `{analysis['identity']['return_sha256']}`; source v66 SHA: `{analysis['identity']['source_sha256']}`; execution `{analysis['identity']['execution_id']}`.
- Receipt/CRC/exact-set/source/preflight: PASS; compile/run/signal `0/0/NONE`.
- Natural terminal: false; formal D expected/present/missing/mismatch `320/0/320/0`; E3/E4/E5 `true/false/false`.
- LPG: `{analysis['last_proven_good']}`.
- FD: `{analysis['first_divergence']}`.
- Root status: `{analysis['hang_root_cause']['status']}`.
- v66 observer escape: 128 records contained only 14 distinct printed tuples because 23-bit LC values were compared through 21-bit shadows. v67 corrects shadow widths and observes the complete LC15/LC9 -> PE1 match -> ALU/outbuffer -> MSE4 input1 chain.
- v67 ZIP `{ZIP.stat().st_size}` bytes, SHA `{sha(ZIP)}`; deterministic double build PASS.
- Focused HDL/scope positive, missing declaration and actual-consumer typo negatives, predicate trace, install-only family harness, shared runtime layout, runner visibility, return conjunction, and final ZIP audit: PASS/errors0.
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`; no numeric/workload/config/golden/RTL/server action.
- Command: `bash r5_n4_hw_v67_pe1_pair_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v67_pe1_pair_diag_r<epoch-ns>_<pid>_return.zip`.
- RULE_CONFIRMATION: current rules sufficient; no non-synonymous delta.
''',encoding='utf-8',newline='\n')
print(json.dumps({'release_report':rec(rp),'task_record':rec(task),'zip':rec(ZIP)},indent=2))
