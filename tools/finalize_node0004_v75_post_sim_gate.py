from __future__ import annotations
import hashlib, json, shutil, sys, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'outputs/conv_node0004_v74_recovered_return_v75_successor/build_current/r5_n4_hw_v75_sourcebound_collectfix'
OUT=(Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'outputs/conv_node0004_v74_recovered_return_v75_successor/build_gate3')
PKG=OUT/'r5_n4_hw_v75_sourcebound_collectfix'
HELPER=ROOT/'tools/server_post_sim_return.py'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n',encoding='utf-8',newline='\n')
def records(root): return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and p.name!='package_manifest.json'}

def main():
  if PKG.exists(): raise SystemExit('refuse overwrite')
  shutil.copytree(SRC,PKG)
  (PKG/'package_tools/server_post_sim_return.py').write_bytes(HELPER.read_bytes())
  plugin=PKG/'package_tools/node0004_v75_post_sim_plugin.py'
  plugin.write_text('''#!/usr/bin/env python3
import argparse, importlib.util, json, pathlib, subprocess, sys
p=argparse.ArgumentParser(); p.add_argument("--package-root",type=pathlib.Path,required=True); p.add_argument("--attempt-root",type=pathlib.Path,required=True); a=p.parse_args()
runtime=a.package_root/"package_tools/node0004_hang_localization_runtime.py"
subprocess.run([sys.executable,str(runtime),"analyze","--package-root",str(a.package_root),"--evidence-root",str(a.attempt_root/"evidence"),"--run-root",str(a.attempt_root)],check=True)
tools=a.package_root/"package_tools"; sys.path.insert(0,str(tools)); spec=importlib.util.spec_from_file_location("v75rt",tools/"node0004_hang_localization_runtime_v7.py"); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
r=m._prepare_source_bound_products(a.attempt_root); (a.attempt_root/"evidence/source_bound_parser_receipt.json").write_text(json.dumps(r,indent=2,sort_keys=True)+"\\n",encoding="utf-8")
print(json.dumps(r,sort_keys=True))
''',encoding='utf-8',newline='\n')
  request={"schema":"server-post-sim-return-request-v1","package_id":PKG.name,"result_root":"/home/panqs/ndp/simresult","return_basename_template":"{package_id}_{execution_id}_return.zip","max_plugin_output_bytes":1048576,"core_entries":[
    {"source_root":"attempt","source":"evidence/compile_exit_status.txt","archive":"evidence/compile_exit_status.txt","required":True},
    {"source_root":"attempt","source":"evidence/run_exit_status.txt","archive":"evidence/run_exit_status.txt","required":True},
    {"source_root":"attempt","source":"evidence/signal_status.txt","archive":"evidence/signal_status.txt","required":True},
    {"source_root":"attempt","source":"evidence/SERVER_RESULT_GATE.json","archive":"evidence/SERVER_RESULT_GATE.json","required":False},
    {"source_root":"attempt","source":"evidence/source_bound_parser_receipt.json","archive":"evidence/source_bound_parser_receipt.json","required":False},
    {"source_root":"attempt","source":"c0/source_bound_causal_decision.json","archive":"runs/c0/source_bound_causal_decision.json","required":False},
    {"source_root":"attempt","source":"c0/source_bound_causal.log","archive":"runs/c0/source_bound_causal.log","required":False},
    {"source_root":"attempt","source":"c0/sim.log","archive":"runs/c0/sim.log","required":False},
    {"source_root":"attempt","source":"c0/return_observer.log","archive":"runs/c0/return_observer.log","required":False},
    {"source_root":"attempt","source":"c0/simulator_argv.txt","archive":"runs/c0/simulator_argv.txt","required":False},
    {"source_root":"package","source":"package_manifest.json","archive":"evidence/returned_package_manifest.json","required":True}],
    "plugins":[{"plugin_id":"node0004_source_bound_collect","argv":["python3","{package_root}/package_tools/node0004_v75_post_sim_plugin.py","--package-root","{package_root}","--attempt-root","{attempt_root}"],"cwd_root":"attempt","timeout_seconds":600,"required_for_adjudication":True}],
    "claim_boundary":"Core post-simulation return survives family parser failure; no natural-terminal, formal-D, E4 or E5 claim."}
  write(PKG/'contracts/server_post_sim_return_request.json',request)
  contract={"schema":"server-post-sim-return-contract-v1","package_id":PKG.name,"helper_member":"package_tools/server_post_sim_return.py","helper_sha256":sha(HELPER),"request_member":"contracts/server_post_sim_return_request.json","request_sha256":sha(PKG/'contracts/server_post_sim_return_request.json'),"runner_member":"PREPARE_AND_RUN.sh","invocation_mode":"JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR","sim_exit_persisted_before_plugins":True,"plugin_failure_blocks_core_return":False,"required_scenarios":["natural_success","natural_success_plugin_failure","simulation_nonzero","idempotent_reentry"]}
  write(PKG/'contracts/server_post_sim_return_contract.json',contract)
  # Disable the historical positional publication ABI; preflight/analyze/root commands remain available.
  for name in ('node0004_hang_localization_runtime.py','node0004_hang_localization_runtime_v7.py'):
    p=PKG/'package_tools'/name; t=p.read_text(encoding='utf-8'); t=t.replace('_base_collect','_legacy_return_disabled').replace('base.collect','base.legacy_return_disabled').replace('def collect(','def legacy_return_disabled(').replace('collect(','legacy_return_disabled(').replace('base.legacy_return_disabled = collect','base.legacy_return_disabled = legacy_return_disabled'); p.write_text(t,encoding='utf-8',newline='\n')
  runner=PKG/'PREPARE_AND_RUN.sh'; t=runner.read_text(encoding='utf-8')
  t=t.replace('run_status=125\n', 'run_status=125\nsim_started=false\n', 1)
  t=t.replace('echo RUNTIME_LAYOUT_SIMULATION_START > "$evidence_root/simulation_started.marker"\n', 'sim_started=true\necho RUNTIME_LAYOUT_SIMULATION_START > "$evidence_root/simulation_started.marker"\n', 1)
  a=t.index('finalize() {'); b=t.index('\non_signal() {',a)
  fn='''finalize() {
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1; trap - EXIT INT TERM HUP; set +e
  [ -z "$host_progress_pid" ] || kill "$host_progress_pid" 2>/dev/null
  [ -z "$host_progress_pid" ] || wait "$host_progress_pid" 2>/dev/null
  [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && [ -n "$run_root" ] && [ -d "$run_root" ] || { publish_minimal_return; exit "$original"; }
  printf '%s\\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
  printf '%s\\n' "$run_status" > "$evidence_root/run_exit_status.txt"
  printf '%s\\n' "$signal_status" > "$evidence_root/signal_status.txt"
  natural=false; grep -aq 'DUT_NATURAL_TERMINAL' "$run_root/c0/return_observer.log" 2>/dev/null && natural=true
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL="$natural"
  # Shared helper persists return_core/RETURN_FINALIZER_STATE.json before plugins.
  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
  core=$?
  final="$original"; [ "$final" -ne 0 ] || [ "$core" -eq 0 ] || final="$core"
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2
  exit "$final"
}
'''
  t=t[:a]+fn+t[b+1:]; runner.write_text(t,encoding='utf-8',newline='\n')
  m=json.loads((PKG/'package_manifest.json').read_text(encoding='utf-8')); m['active_receipts']['server_package_rule_sha256']='30ebf61ef5f1705df043e1d23116f4418c15e26e866d371e445fb04af85edafc'; m['active_receipts']['server_post_sim_return_helper_sha256']=sha(HELPER); m['active_receipts']['server_post_sim_return_dispatch_sha256']='f3ed31646f45e25056020401d1e64ac8ee412631ef4e83a64bf16ebf4fc1cc69'; m['active_receipts'].setdefault('rules',[]).append('CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001'); write(PKG/'package_manifest.json',m); m['files']=records(PKG); write(PKG/'package_manifest.json',m); m['files']=records(PKG); write(PKG/'package_manifest.json',m)
  z=OUT/(PKG.name+'.zip'); base=PKG.parent
  with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as q:
    for p in sorted(PKG.rglob('*')):
      if p.is_file():
        name=p.relative_to(base).as_posix(); info=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); info.compress_type=zipfile.ZIP_DEFLATED; info.external_attr=0o100644<<16; q.writestr(info,p.read_bytes())
  h=sha(z); (OUT/(z.name+'.sha256')).write_text(f'{h}  {z.name}\n',encoding='ascii',newline='\n'); print(json.dumps({'zip':str(z),'bytes':z.stat().st_size,'sha256':h}))
if __name__=='__main__': main()
