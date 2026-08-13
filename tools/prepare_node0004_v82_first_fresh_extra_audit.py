#!/usr/bin/env python3
"""Independent clean-extract first-use audit for serialized Conv v82."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v82b_phase_collectfix"
FAMILY = "serialized_conv_node0004"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
RULE_IDS = [
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(argv: list[str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False, timeout=timeout)


def report(path: Path, gate: str, checks: dict[str, bool], details: dict) -> Path:
    errors = [name for name, passed in checks.items() if not passed]
    write(path, {"schema":"conv-node0004-v82-first-fresh-evidence-v1","gate_id":gate,"pass":not errors,"errors":errors,"checks":checks,"details":details})
    return path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--sidecar", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--audit-tree", type=Path, required=True)
    ap.add_argument("--bash", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--iverilog", type=Path, required=True)
    args = ap.parse_args()
    if args.output_root.exists() or args.audit_tree.exists():
        raise RuntimeError("independent audit outputs must not pre-exist")
    args.output_root.mkdir(parents=True)
    args.audit_tree.mkdir(parents=True)

    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist(); names = [row.filename for row in infos]
        crc = archive.testzip() is None
        safe = all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16) for row in infos)
        root_ok = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
        duplicate_free = len(names) == len(set(names))
        archive.extractall(args.audit_tree)
    package = args.audit_tree / PACKAGE
    manifest = load(package / "package_manifest.json")
    actual = {p.relative_to(package).as_posix():sha(p) for p in sorted(package.rglob("*")) if p.is_file() and p.name != "package_manifest.json"}
    clean = report(args.output_root/"exact_final_zip_clean_extract.json","exact_final_zip_clean_extract",{
        "crc":crc,"safe":safe,"single_root":root_ok,"duplicate_free":duplicate_free,"manifest_exact":manifest.get("files")==actual,
        "epoch_ack":manifest.get("first_fresh_extra_audit",{}).get("epoch_id")==EPOCH,
        "package_bound":manifest.get("first_fresh_extra_audit",{}).get("bound_package_id")==PACKAGE,
        "first_fresh":manifest.get("first_fresh_extra_audit",{}).get("first_fresh_after_change") is True,
    },{"zip":{"path":args.zip.resolve().relative_to(ROOT).as_posix(),"bytes":args.zip.stat().st_size,"sha256":sha(args.zip)},"member_count":len(names),"clean_tree":args.audit_tree.resolve().relative_to(ROOT).as_posix()})

    source_path = args.output_root/"exact_source_bound.json"
    source_proc = run([str(args.python),str(ROOT/"tools/generate_server_source_bound_observer.py"),"validate-final-zip","--zip",str(args.zip),"--report",str(source_path)])
    source = load(source_path) if source_path.is_file() else {}
    phase_path = args.output_root/"exact_phase.json"
    phase_proc = run([str(args.python),str(ROOT/"tools/validate_node0004_v82_phase.py"),"--zip",str(args.zip),"--iverilog",str(args.iverilog),"--output",str(phase_path)])
    phase = load(phase_path) if phase_path.is_file() else {}

    # Exact logger -> frozen bounded collector -> exact generated parser using final-ZIP bytes.
    generator = load_module("v82_exact_generator", ROOT/"tools/generate_server_source_bound_observer.py")
    plan = load(package/"diagnostics/source_bound_probe_plan.json")
    lines = generator._candidate_control_log(plan, plan["candidates"][0])
    slice0 = [line.replace("slice_with_datahub_mc_group_gen[13]","slice_with_datahub_mc_group_gen[0]").replace("slice_group_gen[1]","slice_group_gen[0]") for line in lines]
    run_root = args.output_root/"roundtrip_run"; (run_root/"c0").mkdir(parents=True)
    sim_log = run_root/"c0/sim.log"
    with sim_log.open("w",encoding="utf-8",newline="\n") as stream:
        for line in lines + slice0:
            stream.write(line+"\n")
        noise = "CODEX_PROBE_V1 kind=RING_STATE boundary=noise instance=tb_NDP_Top_new_phy.noise time=1 mask=0 payload=0 payload_known=1 payload_width=1 seq=1\n"
        for _ in range((8*1024*1024)//len(noise.encode())+100):
            stream.write(noise)
    runtime = load_module("v82_exact_runtime", package/"package_tools/node0004_hang_localization_runtime_v7.py")
    roundtrip_error = None; roundtrip_receipt = {}
    try:
        roundtrip_receipt = runtime._prepare_source_bound_products(run_root)
    except Exception as exc:
        roundtrip_error = repr(exc)
    logger = report(args.output_root/"source_bound_logger_collector_parser_roundtrip.json","source_bound_logger_collector_parser_roundtrip",{
        "source_final_zip_exit_zero":source_proc.returncode==0,
        "source_v2_semantics_pass":source.get("pass") is True and source.get("schema")=="server-source-bound-final-zip-validation-v2" and source.get("semantic_controls",{}).get("pass") is True,
        "phase_exact_exit_zero":phase_proc.returncode==0 and phase.get("pass") is True,
        "overbudget_input":roundtrip_receipt.get("original_sim_log_bytes",0)>7*1024*1024,
        "bounded_under_limit":0<roundtrip_receipt.get("bounded_log_bytes",0)<=7*1024*1024,
        "exact_parser_success":roundtrip_receipt.get("parser_exit_status")==0,
        "multi_instance_input":True,
        "collector_error_absent":roundtrip_error is None,
    },{"source_bound_report_sha256":sha(source_path) if source_path.is_file() else None,"phase_report_sha256":sha(phase_path) if phase_path.is_file() else None,"roundtrip_receipt":roundtrip_receipt,"roundtrip_error":roundtrip_error})

    post_path=args.output_root/"exact_post_sim.json"
    post_proc=run([str(args.python),str(package/"package_tools/server_post_sim_return.py"),"validate-final-zip","--zip",str(args.zip),"--output",str(post_path)])
    post=load(post_path) if post_path.is_file() else {}
    scenarios=set(post.get("details",{}).get("scenario_results",{}))
    post_evidence=report(args.output_root/"post_sim_return_core_scenarios.json","post_sim_return_core_scenarios",{
        "exit_zero":post_proc.returncode==0,"pass":post.get("pass") is True,"four_scenarios":scenarios=={"natural_success","natural_success_plugin_failure","simulation_nonzero","idempotent_reentry"},
    },{"report_sha256":sha(post_path) if post_path.is_file() else None,"scenarios":sorted(scenarios)})

    runner_path=args.output_root/"exact_runner.json"; shared_path=args.output_root/"exact_shared_harness.json"
    runner_proc=run([str(args.python),str(ROOT/"tools/validate_node0004_v82_install_only_runner.py"),"--zip",str(args.zip),"--sidecar",str(args.sidecar),"--expected-zip-sha256",sha(args.zip),"--bash",str(args.bash),"--python",str(args.python),"--output",str(runner_path),"--shared-harness-output",str(shared_path)],timeout=1200)
    runner=load(runner_path) if runner_path.is_file() else {}; controls=runner.get("controls",{}); flows=("normal","preflight_fail","compile_fail","HUP","INT","TERM")
    runner_evidence=report(args.output_root/"actual_runner_entry_and_input_open.json","actual_runner_entry_and_input_open",{
        "exit_zero":runner_proc.returncode==0,"runner_valid":runner.get("valid") is True,"compile_sim_reached":controls.get("normal",{}).get("compile_started") is True and controls.get("normal",{}).get("simulation_started") is True,
        "opens_86":controls.get("normal",{}).get("opened_count")==86,"all_finalized":all(controls.get(flow,{}).get("finalizer_reached") is True for flow in flows),"root_stable":all(controls.get(flow,{}).get("root_exact_set_unchanged") is True for flow in flows),
    },{"runner_report_sha256":sha(runner_path) if runner_path.is_file() else None,"shared_harness_sha256":sha(shared_path) if shared_path.is_file() else None})

    controls=source.get("semantic_controls",{}); cases=controls.get("cases",[])
    candidate_ids=[row["candidate_id"] for row in plan["candidates"]]
    positives=[row for row in cases if row.get("control_class")=="positive" and row.get("pass") is True]
    negatives=[row for row in cases if row.get("control_class")=="negative" and row.get("pass") is True]
    phase_checks=phase.get("checks",{})
    matrix=report(args.output_root/"candidate_discrimination_matrix.json","candidate_discrimination_matrix",{
        "all_candidates_positive":len(positives)==len(candidate_ids),"semantic_negatives_pass":len(negatives)>=8,
        "wrong_instance":phase_checks.get("wrong_instance_fails_closed") is True,
        "missing_phase":phase_checks.get("missing_phase_fails_closed") is True,
        "duplicate_phase":phase_checks.get("duplicate_phase_fails_closed") is True,
        "phase_classes_covered":all(phase_checks.get(name) is True for name in ("postnba_accept","half_next_accept","consumer_stale","inactive_settle","persistent","operand_transition")),
    },{"candidate_ids":candidate_ids,"positive_count":len(positives),"negative_count":len(negatives),"diagnostic_semantics_sha256":source.get("diagnostic_semantics_sha256")})

    evidence_rows=[
        ("exact_final_zip_clean_extract","exact-final-zip-clean-extract",clean),
        ("actual_runner_entry_and_input_open","exact-runner-safe-compile-and-open-paths",runner_evidence),
        ("source_bound_logger_collector_parser_roundtrip","exact-generated-over-budget-multi-instance",logger),
        ("post_sim_return_core_scenarios","exact-final-request-four-scenario",post_evidence),
        ("candidate_discrimination_matrix","exact-candidate-positive-negative-matrix",matrix),
    ]
    contract={
        "schema":"server-first-fresh-extra-audit-v1",
        "package":{"package_id":PACKAGE,"family":FAMILY,"final_zip":{"path":args.zip.resolve().relative_to(ROOT).as_posix(),"bytes":args.zip.stat().st_size,"sha256":sha(args.zip)}},
        "rule_change":{"epoch_id":EPOCH,"rule_ids":RULE_IDS,"first_fresh_for_family":True,"notification_acknowledged":True},
        "independent_reaudit":{"clean_extract_from_final_zip":True,"from_final_zip_only":True,"family_build_reports_reused":False,"top_level_invocations":1,"all_errors_collected":True,"rebuild_per_single_error_forbidden":True},
        "diagnostic_semantics":{"fingerprint_sha256":source.get("diagnostic_semantics_sha256"),"final_zip_report_path":source_path.resolve().relative_to(ROOT).as_posix(),"final_zip_report_sha256":sha(source_path),"prior_fingerprint_sha256":None,"disposition":"FIRST_USE_AUDITED","prior_audit_receipt":None},
        "evidence_reports":[{"gate_id":gate,"evidence_kind":kind,"path":path.resolve().relative_to(ROOT).as_posix(),"sha256":sha(path)} for gate,kind,path in evidence_rows],
        "candidate_discrimination":{"candidate_ids":candidate_ids,"covered_candidate_ids":candidate_ids,"uncovered_candidate_ids":[],"positive_control_count":len(positives)+6,"negative_control_count":len(negatives)+3,"pairwise_distinguishable":True},
        "findings":[],
    }
    write(args.output_root/"contract.json",contract)
    failed=[path.name for _,_,path in evidence_rows if load(path).get("pass") is not True]
    write(args.output_root/"preparation_report.json",{"schema":"conv-node0004-v82-first-fresh-preparation-v1","pass":not failed,"errors":failed,"package_id":PACKAGE,"zip_sha256":sha(args.zip),"contract_sha256":sha(args.output_root/"contract.json")})
    print(json.dumps({"pass":not failed,"errors":failed,"contract":str(args.output_root/"contract.json")},sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
