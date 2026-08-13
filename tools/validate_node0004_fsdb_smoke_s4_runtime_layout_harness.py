#!/usr/bin/env python3
"""Run s4 exact runner in the existing isolated harness with a local supervisor stub."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import validate_node0004_fsdb_smoke_s1_runtime_layout_harness as base


base.PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s4"
original_map_harness = base.map_harness
original_env_for = base.env_for
original_write_stubs = base.write_stubs


def map_harness(package, result_root):
    original_map_harness(package, result_root)
    helper = package / "package_tools/server_fsdb_runtime_quiescence.py"
    helper.write_text(r'''#!/usr/bin/env python3
import argparse,hashlib,json,pathlib,re,signal,subprocess,sys,time

def ident(path):
 data=path.read_bytes(); return {"path":str(path),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}

p=argparse.ArgumentParser(); s=p.add_subparsers(dest="cmd",required=True)
q=s.add_parser("supervise")
for name in ("package-id","execution-id","attempt-id","attempt-root","cwd","receipt","heartbeat-source","heartbeat-output","heartbeat-regex","timescale","heartbeat-interval","term-grace","kill-grace","runtime-timeout-seconds"):
 q.add_argument("--"+name,required=name not in ("heartbeat-interval","term-grace","kill-grace"))
q.add_argument("rest",nargs=argparse.REMAINDER)
q=s.add_parser("quiesce")
for name in ("attempt-root","process-receipt","heartbeat","plateau-seconds","settle-seconds","output"): q.add_argument("--"+name,required=name in ("attempt-root","process-receipt","heartbeat","output"))
a=p.parse_args()
if a.cmd=="supervise":
 command=a.rest[1:] if a.rest and a.rest[0]=="--" else a.rest
 stopped=[]
 def on_signal(signum,frame): stopped.append(signum)
 signal.signal(signal.SIGTERM,on_signal)
 process=subprocess.Popen([r"C:\Program Files\Git\bin\bash.exe","-c",'exec "$@"',"quiescence-harness",*command])
 deadline=time.monotonic()+2.0
 while process.poll() is None and not stopped and time.monotonic()<deadline: time.sleep(0.02)
 if process.poll() is None and not stopped: stopped.append(signal.SIGTERM)
 if stopped and process.poll() is None:
  subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
  try: process.wait(timeout=3)
  except subprocess.TimeoutExpired: process.kill(); process.wait()
 source=pathlib.Path(a.heartbeat_source); output=pathlib.Path(a.heartbeat_output); output.parent.mkdir(parents=True,exist_ok=True)
 pattern=re.compile(a.heartbeat_regex); maximum=None
 if source.is_file():
  for line in source.read_text(errors="replace").splitlines():
   m=pattern.search(line)
   if m: maximum=max(maximum or 0,int(m.group(1)))
 rows=[{"sequence":0,"host_monotonic_ns":1,"sim_time":0,"timescale":a.timescale},{"sequence":1,"host_monotonic_ns":2,"sim_time":maximum,"timescale":a.timescale}]
 output.write_text("".join(json.dumps(row,sort_keys=True)+"\n" for row in rows))
 receipt={"schema":"server-fsdb-runtime-quiescence-v1","kind":"process_tree_receipt","rule_id":"CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001","package_id":a.package_id,"execution_id":a.execution_id,"attempt_id":a.attempt_id,"attempt_root":a.attempt_root,"cwd":a.cwd,"start_new_session":True,"child_subreaper":{"enabled":True,"prctl":"PR_SET_CHILD_SUBREAPER","value":1},"root_pid":999,"pgid":999,"root_reaped":True,"remaining_owned_pids":[],"process_tree_quiescent":True,"heartbeat_source":ident(source),"heartbeat_output":ident(output),"termination_reason":"SIGTERM" if stopped else "NATURAL","root_exit_code":process.returncode,"pass":True,"errors":[],"claim_boundary":"local harness stub only"}
 pathlib.Path(a.receipt).write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
 raise SystemExit(process.returncode if process.returncode is not None else 143)
root=pathlib.Path(a.attempt_root); wave=sorted((root/"run/sim_results").glob("wave.fsdb*")); members=[ident(x)|{"path":x.relative_to(root).as_posix()} for x in wave if x.is_file() and x.stat().st_size]
process_receipt=json.loads(pathlib.Path(a.process_receipt).read_text()); rows=[json.loads(x) for x in pathlib.Path(a.heartbeat).read_text().splitlines() if x.strip()]
ok=process_receipt.get("process_tree_quiescent") is True and bool(members) and any(row.get("sim_time")==0 for row in rows) and any(isinstance(row.get("sim_time"),int) and row["sim_time"]>0 for row in rows)
report={"schema":"server-fsdb-runtime-quiescence-v1","kind":"quiescence_receipt","rule_id":"CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001","stable_exact_set":bool(members),"pre_snapshot":{"members":members,"transient_members":[]},"post_snapshot":{"members":members,"transient_members":[]},"diagnostic_status":"COMPLETE" if ok else "DIAGNOSTIC_EVIDENCE_INCOMPLETE","pass":ok,"errors":[] if ok else ["local harness quiescence failed"],"claim_boundary":"local harness stub only"}
pathlib.Path(a.output).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n"); raise SystemExit(0 if ok else 1)
''', encoding="utf-8", newline="\n")


base.map_harness = map_harness


def write_stubs(stub_root, python):
    """Keep signal cases finite on Windows/MSYS while exercising the runner trap."""
    original_write_stubs(stub_root, python)
    make = stub_root / "make"
    text = make.read_text(encoding="utf-8")
    anchor = ''': > "$SIM_STUB_STARTED"
if [ "${SIM_STUB_MODE:-normal}" = loop ]; then
'''
    replacement = ''': > "$SIM_STUB_STARTED"
if [ "${SIM_STUB_MODE:-normal}" = signal_once ]; then
  /usr/bin/sleep 1
  exit 0
fi
if [ "${SIM_STUB_MODE:-normal}" = loop ]; then
'''
    if text.count(anchor) != 1:
        raise ValueError("sim stub signal anchor differs")
    make.write_text(text.replace(anchor, replacement, 1), encoding="utf-8", newline="\n")


base.write_stubs = write_stubs


def env_for(stub, mode, started):
    env = original_env_for(stub, mode, started)
    if mode in {"HUP", "INT", "TERM"}:
        env["SIM_STUB_MODE"] = "signal_once"
    env["PATH"] = str(stub) + os.pathsep + r"C:\Program Files\Git\usr\bin" + os.pathsep + r"C:\Program Files\Git\bin" + os.pathsep + os.environ.get("PATH", "")
    return env


base.env_for = env_for


if __name__ == "__main__":
    raise SystemExit(base.main())
