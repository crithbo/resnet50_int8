#!/usr/bin/env python3
"""Build the fresh serialized-Conv native-flow evidence successor.

The v88 workload and actual-source observer target stay byte-identical.  This
adapter changes only the package identity and runner/return surfaces needed by
the runtime-preflight-native-flow-v1 activation.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v90b_nativeflow"
OUT = ROOT / "outputs/conv_node0004_v90b_nativeflow_release1"
BUILD_ROOT = OUT / "build" / PACKAGE_ID
FINAL_ZIP = OUT / f"{PACKAGE_ID}.zip"


def load_base():
    source = ROOT / "tools/build_node0004_v88b_observerwide_successor_v89b.py"
    spec = importlib.util.spec_from_file_location("node0004_v89b_base", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_receipt_function() -> str:
    return r'''
write_native_flow_attempt() {
  native_path="$evidence_root/NATIVE_FLOW_ATTEMPT.json"
  sim_log="$run_root/c0/sim.log"
  python3 - "$native_path" "$package_id" "$return_tag" "$attempt" "$server_root" "$compile_status" "$sim_started" "$compile_first_error_txt" "$compile_full_log" "$sim_log" "$compile_source_identity_json" "$cfg_root/runs/c0/sca_cfg.json" "$cfg_root/runs/c0/sca_cfg_D.json" "$simv" "$observer_chunk" <<'PY'
import hashlib,json,pathlib,sys
(out,pkg,exe,att,cwd,compile_exit,sim_started,first_error,compile_log,sim_log,
 source_identity,sca_cfg,sca_cfg_d,simv,observer_chunk)=sys.argv[1:]
def log_receipt(label, raw_path):
    path=pathlib.Path(raw_path)
    if not path.is_file():
        return {"label":label,"path":raw_path,"status":"NOT_CREATED"}
    digest=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024),b""):
            digest.update(block)
    return {"label":label,"path":raw_path,"bytes":path.stat().st_size,"sha256":digest.hexdigest(),"complete":True}
compile_argv_path=pathlib.Path(compile_log).parent/"compile_argv.json"
try:
    compile_argv=json.loads(compile_argv_path.read_text(encoding="utf-8")).get("argv",[])
except Exception:
    compile_argv=[]
started=sim_started.lower()=="true"
planned_sim=[simv,"-l",sim_log,"+vcs+lic+wait",f"+SCA_CFG={sca_cfg}",f"+SCA_CFG_D={sca_cfg_d}","+CODEX_OBSERVER_ONLY_WIDE_CAUSAL",f"+CODEX_OBSERVER_CHUNK={observer_chunk}",f"+CODEX_PACKAGE_ID={pkg}",f"+CODEX_EXECUTION_ID={exe}",f"+CODEX_ATTEMPT_ID={att}"]
first=pathlib.Path(first_error).read_text(encoding="utf-8",errors="replace").strip() if pathlib.Path(first_error).is_file() else "runner failed before first-error extraction"
value={
  "schema":"server-native-flow-attempt-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,
  "actual_cwd":cwd,"actual_compile_argv":compile_argv,"actual_sim_argv":planned_sim if started else [],
  "planned_sim_argv":planned_sim,"sca_cfg":sca_cfg,"sca_cfg_d":sca_cfg_d,"repeat_num":1,
  "compile_exit":int(compile_exit),"simulation_started":started,"first_true_error":first,
  "complete_log_receipts":[log_receipt("production_compile",compile_log),log_receipt("production_simulation",sim_log)],
  "relevant_env":{"DUMP_VCD":"0","DUMP_FSDB":"0","TB_DUMP_FSDB":"0","VCS_EXTRA_OPTS":"package-local observer include and source"},
  "actual_source_identity_receipt":source_identity,
  "native_failure_differential_status":"READY_AFTER_ACTUAL_FAILURE" if int(compile_exit)!=0 else "NOT_REQUIRED_BEFORE_RESULT",
  "unknown_server_loader_start_wait_readback":"SERVER_RUNTIME_UNKNOWN",
  "provider_or_environment_preflight_performed":False,
  "claim_boundary":"Exact native command/cwd/environment/log/source inputs only; no environment readiness, compile success, simulation, terminal, formal-D, E3, E4 or E5 claim."
}
pathlib.Path(out).write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY
}

'''


def adapt_runner(text: str) -> str:
    text = text.replace("r5_n4_hw_v89b_obswide", PACKAGE_ID)
    text = text.replace("cfg_root=\n", "cfg_root=\nsimv=\nobserver_chunk=\n")
    old_traps = """trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

"""
    if text.count(old_traps) != 1:
        raise RuntimeError("unexpected v89 trap block")
    text = text.replace(old_traps, "")
    arm = """trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM

# CODEX_PRODUCTION_LAUNCH

"""
    needle = "runner_fail() {"
    if text.count(needle) != 1:
        raise RuntimeError("unexpected runner function anchor")
    text = text.replace(needle, arm + needle)
    text = text.replace(
        'for tool in python3 make; do command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "missing tool: $tool"; done\n',
        "",
    )
    text = text.replace(
        '[ -f "$server_root/Makefile.tb_NDP_Top_new_phy" ] || runner_fail 4 "wrong server root"\n',
        "",
    )
    text = text.replace(
        'cp "$compile_driver_log" "$compile_first_error_txt"; cp "$compile_driver_log" "$compile_log_head_txt"; cp "$compile_driver_log" "$compile_log_tail_txt"',
        'cp "$compile_driver_log" "$compile_first_error_txt"; cp "$compile_driver_log" "$compile_log_head_txt"; cp "$compile_driver_log" "$compile_log_tail_txt"; cp "$compile_driver_log" "$compile_full_log"',
    )
    old_sources = '"$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"'
    text = text.replace(old_sources, old_sources + ' "$compile_full_log"')
    text = text.replace(
        "    observer_rc=0\n  fi\n  export CODEX_PACKAGE_ROOT=",
        "    observer_rc=0\n  fi\n  write_native_flow_attempt\n  export CODEX_PACKAGE_ROOT=",
    )
    text = text.replace("\nfinalize() {", "\n" + native_receipt_function() + "finalize() {")
    text = text.replace(
        'mkdir -p "$run_root/c0" "$evidence_root/compile_rootcause" "$evidence_root/compiled_source" "$evidence_root/observer/chunks" "$compile_root/sim_results" || runner_fail 14 "attempt layout create failed"\n',
        'mkdir -p "$run_root/c0" "$evidence_root/compile_rootcause" "$evidence_root/compiled_source" "$evidence_root/observer/chunks" "$compile_root/sim_results" || runner_fail 14 "attempt layout create failed"\n'
        'cp -a "$package_root/workload/runtime/." "$cfg_root/" || runner_fail 16 "package-owned workload install failed"\n',
    )
    old_first = 'pats=[re.compile(x,re.I) for x in (r"^\\s*(Error|Fatal)-\\[",r"^\\s*(error|fatal)\\s*[:[]",r"^make: \\*\\*\\*")]; hit=next((line for pat in pats for line in lines if pat.search(line)),next((line for line in lines if line.strip()),"compile log is empty")); f.write_text(hit[:4096]+"\\n")'
    new_first = 'pats=[re.compile(x,re.I) for x in (r"^\\s*(Error|Fatal)-\\[",r"^\\s*(error|fatal)\\s*[:[]",r"^make: \\*\\*\\*")]; hit=next((line for line in lines if any(pat.search(line) for pat in pats)),next((line for line in lines if line.strip()),"compile log is empty")); f.write_text(hit[:4096]+"\\n")'
    if old_first not in text:
        raise RuntimeError("first-error extractor anchor changed")
    text = text.replace(old_first, new_first)
    minimal_anchor = '(stage/"evidence/SIM_EXIT_RECEIPT.json").write_text(json.dumps(sim,indent=2,sort_keys=True)+"\\n")\nmembers='
    minimal_insert = '''(stage/"evidence/SIM_EXIT_RECEIPT.json").write_text(json.dumps(sim,indent=2,sort_keys=True)+"\\n")
native={"schema":"server-native-flow-attempt-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"actual_cwd":"UNRESOLVED_BEFORE_NATIVE_CD","actual_compile_argv":[],"actual_sim_argv":[],"planned_sim_argv":[],"sca_cfg":"UNRESOLVED","sca_cfg_d":"UNRESOLVED","repeat_num":1,"compile_exit":int(code),"simulation_started":False,"first_true_error":"runner failed before native attempt initialization","complete_log_receipts":[],"relevant_env":{"DUMP_VCD":"0","DUMP_FSDB":"0","TB_DUMP_FSDB":"0"},"provider_or_environment_preflight_performed":False,"unknown_server_loader_start_wait_readback":"SERVER_RUNTIME_UNKNOWN"}
(stage/"evidence/NATIVE_FLOW_ATTEMPT.json").write_text(json.dumps(native,indent=2,sort_keys=True)+"\\n")
members='''
    if minimal_anchor not in text:
        raise RuntimeError("minimal return anchor changed")
    text = text.replace(minimal_anchor, minimal_insert)
    if text.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        raise RuntimeError("production launch marker is not unique")
    return text


def main() -> int:
    base = load_base()
    base.PACKAGE_ID = PACKAGE_ID
    base.OUT = OUT
    base.BUILD_ROOT = BUILD_ROOT
    base.FINAL_ZIP = FINAL_ZIP
    base.RUNNER = adapt_runner(base.RUNNER)

    base_contract = base.contract
    base_request = base.post_request

    def contract():
        value = base_contract()
        root = f"{PACKAGE_ID}_return/"
        value["runtime_preflight_native_flow"] = {
            "activation_epoch": "runtime-preflight-native-flow-v1",
            "rule_id": "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
            "production_launch_marker": "# CODEX_PRODUCTION_LAUNCH",
            "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
            "provider_probe": False,
            "unknown_server_loader_start_wait_readback": "SERVER_RUNTIME_UNKNOWN",
        }
        value["return_members"]["native_flow_attempt"] = root + "evidence/NATIVE_FLOW_ATTEMPT.json"
        value["return_members"]["compile_full_log"] = root + "evidence/compile_rootcause/compile_driver.full.log"
        value["return_members"]["compile_core_when_not_started"].extend([
            root + "evidence/NATIVE_FLOW_ATTEMPT.json",
            root + "evidence/compile_rootcause/compile_driver.full.log",
        ])
        return value

    def post_request():
        value = base_request()
        value["core_entries"].extend([
            {"source_root": "attempt", "source": "evidence/NATIVE_FLOW_ATTEMPT.json", "archive": "evidence/NATIVE_FLOW_ATTEMPT.json", "required": True},
            {"source_root": "attempt", "source": "evidence/compile_rootcause/compile_driver.full.log", "archive": "evidence/compile_rootcause/compile_driver.full.log", "required": True},
        ])
        return value

    base.contract = contract
    base.post_request = post_request
    result = base.main()

    package = BUILD_ROOT
    # The v89 builder writes this receipt after its first ZIP.  It is a local
    # build artifact, not a package input, so keep it outside the final ZIP.
    (package / "build_receipt.json").unlink()
    (package / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json").write_bytes(
        (ROOT / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json").read_bytes()
    )
    (package / "provenance/v89b_formal_return_analysis.json").write_bytes(
        (ROOT / "outputs/conv_node0004_v89b_formal_return_analysis1/formal_return_analysis.json").read_bytes()
    )
    runner_contract_path = package / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["first_fallible_tokens"] = ["make -f"]
    runner_contract["return_allowlist_tokens"].append("NATIVE_FLOW_ATTEMPT.json")
    runner_contract["package_owned_variables"].extend(["simv", "observer_chunk"])
    runner_contract_path.write_text(json.dumps(runner_contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "status": "PACKAGE_BUILT_AWAITING_CURRENT_GATES",
        "runtime_preflight_native_flow_activation_epoch": "runtime-preflight-native-flow-v1",
        "diagnostic_predecessor": "r5_n4_hw_v89b_obswide",
        "workload_and_actual_source_baseline": "r5_n4_hw_v88b_portvcd",
        "source_package": "r5_n4_hw_v89b_obswide",
        "previous_version_progress": "v88b passed production compile/elaboration and invalidated the retired ACK comparator as an observer/source-identity semantic false positive. v89b used the corrected actual-source wide observer but production compile failed on unresolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf and simulation did not start; the v88/v89 compile difference remains unresolved.",
        "current_purpose": "Run the native production path directly with the corrected actual-source observer and return exact cwd/compile/sim argv/relevant env/source identity/full logs/first true error for a post-failure native-flow differential without any provider probe.",
        "server_prelaunch_provider_or_environment_probe": False,
    })
    manifest["files"] = [row for row in base.file_map() if row["path"] != "package_manifest.json"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    manifest["files"] = [row for row in base.file_map() if row["path"] != "package_manifest.json"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    readme = f"""# {PACKAGE_ID}

Formal serialized Conv observer-only native-flow successor.

Previous progress: v88b passed production compile/elaboration and proved the retired ACK comparator was an observer/source-identity semantic false positive. v89b preserved the corrected actual-source wide observer, but production compile failed at unresolved DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf and simulation never started. The reason v88 compiled while v89 did not remains unresolved.

Current purpose: execute the native production cd/install/compile/sim path directly, with no provider or environment probe, while returning exact cwd, compile/sim argv, relevant environment, SCA_CFG/SCA_CFG_D, Repeat_Num, actual source identity, complete logs, first true error, exits and simulation-started state for a registered post-failure differential.

Run only when separately authorized:

    bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01

The frozen v88 workload/config/numeric/golden/functional RTL and the v89 actual-source causal target are unchanged. The retired comparator is absent. Observer evidence has a decimal 100000000-byte warning threshold and no hard cap, sampling, truncation or size deletion.
"""
    (package / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = [row for row in base.file_map() if row["path"] != "package_manifest.json"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    base.deterministic_zip()
    build_receipt = {
        "schema": "node0004-nativeflow-build-v1",
        "package_id": PACKAGE_ID,
        "zip": {"path": FINAL_ZIP.relative_to(ROOT).as_posix(), "bytes": FINAL_ZIP.stat().st_size, "sha256": base.sha(FINAL_ZIP.read_bytes())},
        "member_count": len(base.file_map()),
        "pass": True,
    }
    (OUT / "build_receipt.json").write_text(
        json.dumps(build_receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
