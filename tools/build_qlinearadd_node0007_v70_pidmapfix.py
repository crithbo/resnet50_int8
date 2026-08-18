#!/usr/bin/env python3
"""Build the fresh QAdd v70 runner/supervisor-only repair from exact v69."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v69_pfc"
NEW = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"
OLD_SHA = "2f4196597f12e424df97a94af2e614e413dea8032a04752c0c97fc57ec1d8597"
GOOD_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-supervisor-pidmap-v1"
SOURCE_OUT = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release"
SOURCE_TREE = SOURCE_OUT / "build" / OLD
SOURCE_ZIP = SOURCE_OUT / f"{OLD}.zip"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v69_return_r1786886207604661595_3464688"
ANALYSIS = ANALYSIS_OUT / "formal_return_analysis.json"
AUDIT = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
DISPOSITION = ANALYSIS_OUT / "RULE_AUDIT_DISPOSITION.json"
OUT = ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v69.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v70.svh"
OLD_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v69.py"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v70.py"
OLD_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v69.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v70.py"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(root.rglob("*")) if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def normalized(path: Path, package: str, version: str) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(text.replace(package, "<PACKAGE_ID>").replace(version, "vXX"))


def subtree(root: Path, ignore: set[str] | None = None) -> dict[str, str]:
    ignored = ignore or set()
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file() and p.relative_to(root).as_posix() not in ignored}


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(TREE.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def copy_fresh_identity() -> None:
    if OUT.exists():
        raise RuntimeError(f"fresh output exists: {OUT}")
    shutil.copytree(SOURCE_TREE, TREE)
    suffixes = {".json", ".py", ".sh", ".svh", ".md"}
    for path in sorted(TREE.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in suffixes or path.relative_to(TREE).as_posix().startswith("provenance/"):
            continue
        text = path.read_text(encoding="utf-8")
        changed = text.replace(OLD, NEW).replace("v69", "v70").replace("V69", "V70").replace("QAdd v69", "QAdd v70")
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    (TREE / OLD_TB).rename(TREE / NEW_TB)
    (TREE / OLD_LIVE).rename(TREE / NEW_LIVE)
    (TREE / OLD_FINALIZER).rename(TREE / NEW_FINALIZER)
    for cache in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(cache)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def patch_supervisor_and_runner() -> None:
    supervisor = TREE / NEW_LIVE
    text = supervisor.read_text(encoding="utf-8")
    old = """    known: dict[int, int | None] = {process.pid}\n"""
    new = """    root_row = next((row for row in process_rows() if row[\"pid\"] == process.pid), None)\n    if root_row is None:\n        process.terminate()\n        process.wait(timeout=30)\n        raise RuntimeError(\"simulator root identity unavailable immediately after Popen\")\n    known: dict[int, int | None] = {}\n    remember(known, root_row)\n"""
    if text.count(old) != 1:
        raise RuntimeError("supervisor PID-map anchor drifted")
    supervisor.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")

    runner = TREE / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    text = text.replace(
        "actual_argv_json=\npackage_preflight_stdout=",
        "actual_argv_json=\nsupervisor_stdout=\nsupervisor_stderr=\nsupervisor_execution=\npackage_preflight_stdout=",
        1,
    )
    text = text.replace(
        'actual_argv_json="$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"\npackage_preflight_stdout=',
        'actual_argv_json="$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"\nsupervisor_stdout="$evidence_root/SUPERVISOR_STDOUT.txt"\nsupervisor_stderr="$evidence_root/SUPERVISOR_STDERR.txt"\nsupervisor_execution="$evidence_root/SUPERVISOR_EXECUTION.json"\npackage_preflight_stdout=',
        1,
    )
    launch = f'''DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/{NEW_LIVE}" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --runtime-evaluator "$package_root/package_tools/server_tb_vcd_runtime_supervision.py" --decision-receipt "$decision_receipt" --sim-log "$run_root/sim.log" --vcd "$vcd_path" --samples "$supervisor_heartbeat" --heartbeat-output "$evidence_root/SIM_TIME_HEARTBEAT.jsonl" --process-receipt "$process_receipt" --safety-receipt "$safety_receipt" -- "$simv" "${{sim_args[@]}}" &'''
    redirected = launch.removesuffix(" &") + ' >"$supervisor_stdout" 2>"$supervisor_stderr" &'
    if text.count(launch) != 1:
        raise RuntimeError("runner supervisor launch anchor drifted")
    text = text.replace(launch, redirected, 1)
    wait_old = '''wait "$sim_pid"\nsimulation_status=$?\nsim_pid=0'''
    wait_new = '''wait "$sim_pid"\nsimulation_status=$?\nsim_pid=0\npython3 - "$supervisor_execution" "$supervisor_stdout" "$supervisor_stderr" "$package_id" "$return_tag" "$attempt" "$simulation_status" <<'PY'\nimport hashlib,json,pathlib,sys\ntarget,stdout,stderr=map(pathlib.Path,sys.argv[1:4]);pkg,exe,att=sys.argv[4:7];code=int(sys.argv[7])\ndef row(path):\n data=path.read_bytes() if path.is_file() else b''\n return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'complete':True}\nfirst=next((line.strip() for line in stderr.read_text(errors='replace').splitlines() if line.strip()),None) if stderr.is_file() else None\ntarget.write_text(json.dumps({'schema':'qadd-supervisor-execution-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'exit_code':code,'stdout':row(stdout),'stderr':row(stderr),'first_true_error':first},sort_keys=True)+'\\n')\nPY'''
    if text.count(wait_old) != 1:
        raise RuntimeError("runner wait anchor drifted")
    text = text.replace(wait_old, wait_new, 1)
    native_old = '"$evidence_root/compile_driver.log" "$run_root/sim.log" "$evidence_root/compile_first_error.txt" "$process_receipt" <<\'PY\''
    native_new = '"$evidence_root/compile_driver.log" "$run_root/sim.log" "$supervisor_stderr" "$evidence_root/compile_first_error.txt" "$process_receipt" <<\'PY\''
    if text.count(native_old) != 1:
        raise RuntimeError("native-failure argv anchor drifted")
    text = text.replace(native_old, native_new, 1)
    code_old = "logs=[pathlib.Path(x) for x in sys.argv[10:12]];first=pathlib.Path(sys.argv[12])"
    code_new = "logs=[pathlib.Path(x) for x in sys.argv[10:13]];first=pathlib.Path(sys.argv[13])"
    proc_old = "proc=pathlib.Path(sys.argv[13]);p=json.loads(proc.read_text()) if proc.is_file() else {}"
    proc_new = "proc=pathlib.Path(sys.argv[14]);p=json.loads(proc.read_text()) if proc.is_file() else {}"
    if text.count(code_old) != 1 or text.count(proc_old) != 1:
        raise RuntimeError("native-failure parser anchor drifted")
    text = text.replace(code_old, code_new, 1).replace(proc_old, proc_new, 1)
    runner.write_text(text, encoding="utf-8", newline="\n")


def bind_contracts() -> None:
    provenance = TREE / "provenance"
    shutil.copyfile(ANALYSIS, provenance / "v69_formal_return_analysis.json")
    shutil.copyfile(AUDIT, provenance / "v69_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")
    shutil.copyfile(DISPOSITION, provenance / "v69_RULE_AUDIT_DISPOSITION.json")
    predecessor = SOURCE_TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    predecessor_copy = provenance / "v69_server_tb_vcd_bounded_causal_cone_contract.json"
    shutil.copyfile(predecessor, predecessor_copy)
    shutil.copyfile(SOURCE_TREE / OLD_TB, TREE / OLD_TB)
    shutil.copyfile(SOURCE_TREE / OLD_LIVE, TREE / OLD_LIVE)

    fix = {
        "schema": "qadd-supervisor-pid-map-fix-contract-v1",
        "package_id": NEW, "predecessor_package_id": OLD,
        "source_return_analysis": identity(ANALYSIS), "source_failure_audit": identity(AUDIT),
        "validated_root_cause": "QADD_V69_SUPERVISOR_TRACKED_PID_MAP_INITIALIZED_AS_SET_CAUSES_POST_POPEN_PRETARGET_ESCAPE",
        "required_delta": ["dict PID/start-time state", "root start-time binding immediately after Popen", "supervisor stdout/stderr/exit formal return", "historical set-initializer negative control"],
        "functional_delta": False,
        "frozen": ["validated 4/2 config lineage", "numeric", "workload", "golden", "functional RTL", "tail-round target", "64-signal cone", "candidate matrix", "TB observation semantics"],
        "pass": True, "errors": [],
    }
    write(TREE / "diagnostics/supervisor_pid_map_fix_contract.json", fix)

    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    vcd = load(vcd_path)
    signals = [row["signal_id"] for row in vcd["signals"]]
    candidates = [row["candidate_id"] for row in vcd["candidates"]]
    vcd["package_id"] = NEW
    vcd["diagnostic_round"]["round_index"] = 4
    vcd["diagnostic_round"]["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    vcd["diagnostic_round"]["evolution"] = {
        "predecessor": {"package_id": OLD, "round_index": 3, "contract_path": "provenance/v69_server_tb_vcd_bounded_causal_cone_contract.json", "contract_sha256": sha(predecessor_copy), "pinned_rtl_tree_sha256": vcd["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"]},
        "added_signal_ids": [], "removed_signal_ids": [], "unchanged_signal_ids": signals, "removal_evidence": [],
        "candidate_preservation": {"preserved_candidate_ids": candidates, "closed_candidate_ids": [], "new_candidate_ids": [], "closure_evidence": []},
    }
    vcd["execution"]["tb_source_path"] = NEW_TB
    vcd["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    vcd["claim_boundary"] = "v70 changes only fresh identity and package-local supervisor/return evidence; v69 causal/config/TB functional semantics remain frozen."
    write(vcd_path, vcd)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    additions = [
        {"source_root": "attempt", "source": "evidence/SUPERVISOR_STDOUT.txt", "archive": "evidence/SUPERVISOR_STDOUT.txt", "required": True},
        {"source_root": "attempt", "source": "evidence/SUPERVISOR_STDERR.txt", "archive": "evidence/SUPERVISOR_STDERR.txt", "required": True},
        {"source_root": "attempt", "source": "evidence/SUPERVISOR_EXECUTION.json", "archive": "evidence/SUPERVISOR_EXECUTION.json", "required": True},
        {"source_root": "package", "source": "diagnostics/supervisor_pid_map_fix_contract.json", "archive": "source_package/supervisor_pid_map_fix_contract.json", "required": True},
        {"source_root": "package", "source": "provenance/v69_formal_return_analysis.json", "archive": "source_package/v69_formal_return_analysis.json", "required": True},
        {"source_root": "package", "source": "provenance/v69_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "archive": "source_package/v69_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", "required": True},
    ]
    archives = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)

    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    allow["package_id"] = NEW
    required = set(allow.get("required", []))
    for rel in ["evidence/SUPERVISOR_STDOUT.txt", "evidence/SUPERVISOR_STDERR.txt", "evidence/SUPERVISOR_EXECUTION.json", "source_package/supervisor_pid_map_fix_contract.json", "source_package/v69_formal_return_analysis.json", "source_package/v69_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"]:
        required.add(rel)
        required.add(f"{NEW}_return/{rel}")
    allow["required"] = sorted(required)
    write(allow_path, allow)


def refresh_identities() -> None:
    runner = TREE / "PREPARE_AND_RUN.sh"
    runner_sha = sha(runner)
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path)
    resilience["package_id"] = NEW
    resilience["runner_sha256"] = runner_sha
    write(resilience_path, resilience)

    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    layout["package_id"] = NEW
    layout["install_name"] = NEW
    projected = f"install/cfg_pkg/{NEW}/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
    projected_abs = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(projected)
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_abs
    if isinstance(layout.get("runner_bindings"), dict):
        layout["runner_bindings"]["runner_sha256"] = runner_sha
    write(layout_path, layout)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post.update({"package_id": NEW, "request_sha256": sha(request_path), "runner_sha256": runner_sha, "helper_sha256": sha(TREE / "package_tools/server_post_sim_return.py")})
    write(post_path, post)
    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    vcd = load(vcd_path)
    vcd["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    write(vcd_path, vcd)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = NEW
    selector["vcd_contract_sha256"] = sha(vcd_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {"evidence/SUPERVISOR_STDOUT.txt", "evidence/SUPERVISOR_STDERR.txt", "evidence/SUPERVISOR_EXECUTION.json", "source_package/supervisor_pid_map_fix_contract.json", "source_package/v69_formal_return_analysis.json", "source_package/v69_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"})
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)

    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest.update({
        "package_id": NEW, "package_identity": NEW, "install_name": NEW,
        "activation_epoch": EPOCH, "status": "PACKAGE_READY_NOT_RUN",
        "previous_version_progress": "v69 passed package preflight and production compile, then uniquely failed in the package-local supervisor immediately after simv Popen because its PID/start-time map was initialized as a set; target/VCD/4-2 dynamics were not reached.",
        "current_version_purpose": "Preserve exact v69 4/2/config/workload/TB causal semantics while repairing the PID/start-time map and returning supervisor stdout/stderr/exit so the unchanged target can execute with closed process ownership.",
        "package_build_failure_rule_audit": "provenance/v69_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        "supervisor_pid_map_fix": "diagnostics/supervisor_pid_map_fix_contract.json",
        "diagnostic_mode_selector_sha256": sha(selector_path),
    })
    manifest["path_length_budget"]["longest_projected_relative_path"] = projected
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(projected)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = projected_abs
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)
    selector = load(selector_path)
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest = load(manifest_path)
    manifest["diagnostic_mode_selector_sha256"] = sha(selector_path)
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)


def main() -> int:
    if not SOURCE_ZIP.is_file() or sha(SOURCE_ZIP) != OLD_SHA or not SOURCE_TREE.is_dir():
        raise RuntimeError("exact v69 durable source is absent or drifted")
    analysis = load(ANALYSIS)
    audit = load(AUDIT)
    if analysis.get("successor_disposition") != "FRESH_RUNNER_SUPERVISOR_RETURN_ONLY_FIX_WARRANTED" or not analysis.get("pass"):
        raise RuntimeError("v69 analysis does not authorize fresh fix")
    if audit.get("adjudication", {}).get("rule_disposition") != "RULE_CONFIRMATION_NO_CHANGE" or not audit.get("pass"):
        raise RuntimeError("v69 package-build audit is absent")
    source_identity = identity(SOURCE_ZIP)
    source_workload = subtree(SOURCE_TREE / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"})
    source_validation = subtree(SOURCE_TREE / "validation")
    source_bitstream = sha(SOURCE_TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    source_config = sha(SOURCE_TREE / "provenance/config_lineage/op_tail_round_4_2.json")
    source_catalog = normalized(SOURCE_TREE / "diagnostics/tb_vcd_signal_catalog.json", OLD, "v69")
    source_matrix = normalized(SOURCE_TREE / "diagnostics/tb_vcd_candidate_matrix.json", OLD, "v69")
    source_tb = (SOURCE_TREE / OLD_TB).read_text(encoding="utf-8").replace(OLD, "<PACKAGE_ID>").replace("v69", "vXX")

    copy_fresh_identity()
    patch_supervisor_and_runner()
    bind_contracts()
    refresh_identities()

    frozen_checks = {
        "v69_source_byte_frozen": identity(SOURCE_ZIP) == source_identity,
        "config42_bitstream_exact": sha(TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin") == source_bitstream == GOOD_BITSTREAM,
        "config_json_exact": sha(TREE / "provenance/config_lineage/op_tail_round_4_2.json") == source_config,
        "validation_payload_exact": subtree(TREE / "validation") == source_validation,
        "workload_payload_exact_except_identity_sca": subtree(TREE / "workload", {"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"}) == source_workload,
        "catalog_exact_except_identity": normalized(TREE / "diagnostics/tb_vcd_signal_catalog.json", NEW, "v70") == source_catalog,
        "matrix_exact_except_identity": normalized(TREE / "diagnostics/tb_vcd_candidate_matrix.json", NEW, "v70") == source_matrix,
        "tb_exact_except_identity": (TREE / NEW_TB).read_text(encoding="utf-8").replace(NEW, "<PACKAGE_ID>").replace("v70", "vXX") == source_tb,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
    }
    frozen = {"schema": "qadd-v70-frozen-surface-v1", "package_id": NEW, "checks": frozen_checks, "changed_surfaces": ["fresh_identity", "supervisor_pid_start_map", "supervisor_stdout_stderr_exit_return", "audit_provenance"], "frozen": ["validated_config42", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_cone", "candidate_matrix", "TB_observation_semantics"], "storage_manager_called": False, "server_actions_performed": [], "pass": all(frozen_checks.values()), "errors": [k for k, v in frozen_checks.items() if not v]}
    write(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface drift: {frozen['errors']}")
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if sha(ZIP) != sha(REPEAT) or ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic ZIP mismatch")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
    receipt = {"schema": "qadd-v70-pidmapfix-build-v1", "role_id": "family.qlinearadd", "owner_epoch": 2, "registry_epoch": 6, "package_id": NEW, "activation_epoch": EPOCH, "source_v69": source_identity, "return_analysis": identity(ANALYSIS), "package_build_failure_rule_audit": identity(AUDIT), "package": identity(ZIP), "repeat_package": identity(REPEAT), "deterministic_recompute": True, "storage_manager_called": False, "server_actions_performed": [], "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES", "pass": True, "errors": [], "claim_boundary": "Local runner/supervisor/return construction only; no server, dynamic 4/2 repair, natural terminal, Formal-D or E3-E5 claim."}
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
