#!/usr/bin/env python3
"""Build the fresh QAdd v69 precompile-evidence successor from exact v68.

Only fresh identity and package-local runner/return evidence surfaces change.
The exact 4/2 lineage, workload, numeric/golden payload, functional RTL absence,
TB causal semantics, 64-signal catalog and candidate matrix remain frozen.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"
NEW = "r5_qadd_n7_tailround_lanephase_v69_pfc"
OLD_SHA = "449e07e917bca6ff406bd94804903375e24d51b74b5c20762dc53e110ff228f4"
GOOD_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
EPOCH = "tb-vcd-planned-dumpoff-consistency-v5-b175c14254f3+qadd-precompile-core-capture-v1"
SOURCE_OUT = ROOT / "outputs/qlinearadd_node0007_v68_cfg42_tick_release"
SOURCE_TREE = SOURCE_OUT / "build" / OLD
SOURCE_RELEASE_ZIP = SOURCE_OUT / f"{OLD}.zip"
SOURCE_PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
ANALYSIS_OUT = ROOT / "outputs/qlinearadd_node0007_v68_return_r1786853531805017272_3183291"
ANALYSIS = ANALYSIS_OUT / "formal_return_analysis.json"
AUDIT = ANALYSIS_OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json"
ESCALATION = ANALYSIS_OUT / "SHARED_RULE_AUDIT_ESCALATION.json"
DISPOSITION = ANALYSIS_OUT / "RULE_AUDIT_DISPOSITION.json"
OUT = ROOT / "outputs/qlinearadd_node0007_v69_pfc_release"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v68.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v69.svh"
OLD_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v68.py"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v69.py"
OLD_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v68.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v69.py"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


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
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def subtree_map(root: Path, *, ignore: set[str] | None = None) -> dict[str, str]:
    ignored = ignore or set()
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in ignored
    }


def normalized_json(path: Path, package_id: str) -> Any:
    return json.loads(json.dumps(load(path), ensure_ascii=False).replace(package_id, "<PACKAGE_ID>"))


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(f"{NEW}/{path.relative_to(TREE).as_posix()}", (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def replace_identity() -> None:
    if OUT.exists():
        raise RuntimeError(f"fresh output already exists: {OUT}")
    shutil.copytree(SOURCE_TREE, TREE)
    text_suffixes = {".json", ".py", ".sh", ".svh", ".md"}
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        relative = path.relative_to(TREE).as_posix()
        if relative.startswith("provenance/") or path.suffix.lower() not in text_suffixes:
            continue
        text = path.read_text(encoding="utf-8")
        changed = text.replace(OLD, NEW)
        changed = changed.replace("QAdd v68", "QAdd v69")
        changed = changed.replace("qlinearadd_node0007_tb_vcd_causal_cone_v68", "qlinearadd_node0007_tb_vcd_causal_cone_v69")
        changed = changed.replace("codex_qadd_tb_vcd_causal_cone_v68", "codex_qadd_tb_vcd_causal_cone_v69")
        changed = changed.replace("qlinearadd_node0007_tb_vcd_live_supervision_v68.py", "qlinearadd_node0007_tb_vcd_live_supervision_v69.py")
        changed = changed.replace("qlinearadd_node0007_tb_vcd_finalize_v68.py", "qlinearadd_node0007_tb_vcd_finalize_v69.py")
        changed = changed.replace("qadd-v68", "qadd-v69")
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    (TREE / OLD_TB).rename(TREE / NEW_TB)
    (TREE / OLD_LIVE).rename(TREE / NEW_LIVE)
    (TREE / OLD_FINALIZER).rename(TREE / NEW_FINALIZER)
    for path in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(path)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def patch_runner_capture() -> None:
    path = TREE / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    variable_anchor = """actual_argv_json=
vcd_path="""
    variable_new = """actual_argv_json=
package_preflight_stdout=
package_preflight_stderr=
package_preflight_receipt=
runner_stage_receipt=
vcd_path="""
    if variable_anchor not in text:
        raise RuntimeError("runner variable anchor drifted")
    text = text.replace(variable_anchor, variable_new, 1)
    path_anchor = '''actual_argv_json="$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"
printf '# SIMULATION_NOT_STARTED\\n' >"$run_root/sim.log"
runtime="$package_root/package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
python3 "$runtime" preflight --package-root "$package_root" >"$evidence_root/package_preflight.json" || runner_fail 5 "package preflight failed"'''
    path_new = '''actual_argv_json="$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"
package_preflight_stdout="$evidence_root/PACKAGE_PREFLIGHT_STDOUT.txt"
package_preflight_stderr="$evidence_root/PACKAGE_PREFLIGHT_STDERR.txt"
package_preflight_receipt="$evidence_root/PACKAGE_PREFLIGHT_EXECUTION.json"
runner_stage_receipt="$evidence_root/RUNNER_STAGE_RECEIPT.json"
printf '# SIMULATION_NOT_STARTED\\n' >"$run_root/sim.log"
runtime="$package_root/package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
python3 - "$runner_stage_receipt" "$package_id" "$return_tag" "$attempt" <<'PY'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({'schema':'qadd-runner-stage-receipt-v1','package_id':sys.argv[2],'execution_id':sys.argv[3],'attempt_id':sys.argv[4],'stage':'PACKAGE_RUNTIME_PREFLIGHT','state':'STARTED','compile_started':False,'simulation_started':False},sort_keys=True)+'\\n')
PY
set +e
python3 "$runtime" preflight --package-root "$package_root" >"$package_preflight_stdout" 2>"$package_preflight_stderr"
package_preflight_status=$?
set +e
python3 - "$package_preflight_receipt" "$runner_stage_receipt" "$package_preflight_stdout" "$package_preflight_stderr" "$bootstrap_root" "$actual_argv_json" "$package_id" "$return_tag" "$attempt" "$server_root" "$package_preflight_status" <<'PY'
import hashlib,json,pathlib,sys
receipt,stage,stdout,stderr,bootstrap,actual=map(pathlib.Path,sys.argv[1:7]);pkg,exe,att,cwd=sys.argv[7:11];code=int(sys.argv[11])
def row(path):
 data=path.read_bytes() if path.is_file() else b''
 return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'complete':True}
stderr_text=stderr.read_text(errors='replace') if stderr.is_file() else ''
first=next((line.strip() for line in stderr_text.splitlines() if line.strip()),f'PACKAGE_RUNTIME_PREFLIGHT_EXIT_{code}')
receipt.write_text(json.dumps({'schema':'qadd-package-runtime-preflight-execution-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'stage':'PACKAGE_RUNTIME_PREFLIGHT','exit_code':code,'compile_started':False,'simulation_started':False,'stdout':row(stdout),'stderr':row(stderr),'first_true_error':None if code==0 else first[:8192]},sort_keys=True)+'\\n')
stage.write_text(json.dumps({'schema':'qadd-runner-stage-receipt-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'stage':'PACKAGE_RUNTIME_PREFLIGHT','state':'COMPLETED' if code==0 else 'FAILED','stage_exit':code,'compile_started':False,'simulation_started':False},sort_keys=True)+'\\n')
actual.write_text(json.dumps({'schema':'server-tb-vcd-actual-argv-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'cwd':cwd,'actual_cwd':cwd,'sca_cfg':None,'sca_cfg_d':None,'repeat_num':None,'relevant_env':{'DUMP_VCD':'0','DUMP_FSDB':'0','TB_DUMP_FSDB':'0'},'source_identity_status':'COMPILE_NOT_STARTED','compile_argv':[],'sim_argv':[]},sort_keys=True)+'\\n')
if code:
 bootstrap.mkdir(parents=True,exist_ok=True)
 (bootstrap/'compile_argv.json').write_text(json.dumps({'schema':'server-exact-compile-argv-v1','cwd':cwd,'argv':[],'compile_started':False,'blocked_stage':'PACKAGE_RUNTIME_PREFLIGHT'},sort_keys=True)+'\\n')
 (bootstrap/'compile_source_identity.json').write_text(json.dumps({'schema':'server-compile-source-identity-v1','status':'COMPILE_NOT_STARTED','blocked_stage':'PACKAGE_RUNTIME_PREFLIGHT'},sort_keys=True)+'\\n')
 (bootstrap/'compile_exit.txt').write_text('125\\n')
 (bootstrap/'compile_driver.log').write_text(stderr_text or first+'\\n')
 (bootstrap/'compile_first_error.txt').write_text(first[:8192]+'\\n')
 (bootstrap/'compile_log_head.txt').write_text((stderr_text or first+'\\n')[:32768])
 (bootstrap/'compile_log_tail.txt').write_text((stderr_text or first+'\\n')[-32768:])
 (bootstrap/'compile_downstream_state.json').write_text(json.dumps({'schema':'server-compile-downstream-state-v1','compile_succeeded':False,'compile_started':False,'blocked_stage':'PACKAGE_RUNTIME_PREFLIGHT','simulation_started':False,'formal_D':'not-produced-before-simulation'},sort_keys=True)+'\\n')
PY
[ "$package_preflight_status" -eq 0 ] || runner_fail 5 "package preflight failed; stdout/stderr/exit/stage/first-error captured"
cp -- "$package_preflight_stdout" "$evidence_root/package_preflight.json"'''
    if path_anchor not in text:
        raise RuntimeError("runner package-preflight anchor drifted")
    text = text.replace(path_anchor, path_new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def bind_analysis_and_contracts() -> None:
    provenance = TREE / "provenance"
    shutil.copyfile(ANALYSIS, provenance / "v68_formal_return_analysis.json")
    shutil.copyfile(AUDIT, provenance / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json")
    shutil.copyfile(ESCALATION, provenance / "SHARED_RULE_AUDIT_ESCALATION.json")
    shutil.copyfile(DISPOSITION, provenance / "v68_RULE_AUDIT_DISPOSITION.json")
    predecessor = SOURCE_TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    predecessor_copy = provenance / "v68_server_tb_vcd_bounded_causal_cone_contract.json"
    shutil.copyfile(predecessor, predecessor_copy)
    shutil.copyfile(SOURCE_TREE / OLD_TB, TREE / OLD_TB)

    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    vcd = load(vcd_path)
    signals = [row["signal_id"] for row in vcd["signals"]]
    candidates = [row["candidate_id"] for row in vcd["candidates"]]
    vcd["package_id"] = NEW
    vcd["diagnostic_round"]["round_index"] = 3
    vcd["diagnostic_round"]["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    vcd["diagnostic_round"]["evolution"] = {
        "predecessor": {
            "package_id": OLD,
            "round_index": 2,
            "contract_path": "provenance/v68_server_tb_vcd_bounded_causal_cone_contract.json",
            "contract_sha256": sha(predecessor_copy),
            "pinned_rtl_tree_sha256": vcd["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
        },
        "added_signal_ids": [],
        "removed_signal_ids": [],
        "unchanged_signal_ids": signals,
        "removal_evidence": [],
        "candidate_preservation": {
            "preserved_candidate_ids": candidates,
            "closed_candidate_ids": [],
            "new_candidate_ids": [],
            "closure_evidence": [],
        },
    }
    vcd["execution"]["tb_source_path"] = NEW_TB
    vcd["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    vcd["claim_boundary"] = "Exact v68 causal/TB semantics are frozen; v69 changes only fresh identity and precompile stdout/stderr/exit/stage/core return capture."
    write(vcd_path, vcd)

    capture = {
        "schema": "qadd-precompile-core-capture-contract-v1",
        "package_id": NEW,
        "predecessor_package_id": OLD,
        "source_return_analysis": identity(ANALYSIS),
        "source_recurring_audit": identity(AUDIT),
        "shared_rule_audit_escalation": identity(ESCALATION),
        "trigger": "THIRD_CONSECUTIVE_PRETARGET_PACKAGE_RUNTIME_ESCAPE",
        "stage": "PACKAGE_RUNTIME_PREFLIGHT",
        "required_return_members": [
            "evidence/PACKAGE_PREFLIGHT_STDOUT.txt",
            "evidence/PACKAGE_PREFLIGHT_STDERR.txt",
            "evidence/PACKAGE_PREFLIGHT_EXECUTION.json",
            "evidence/RUNNER_STAGE_RECEIPT.json",
            "evidence/compile_first_error.txt",
            "evidence/ACTUAL_COMPILE_SIM_ARGV.json",
        ],
        "compile_not_started_semantics": {"compile_exit_sentinel": 125, "actual_compile_argv": [], "actual_sim_argv": []},
        "server_prelaunch_inventory_or_probe": False,
        "functional_delta": False,
        "pass": True,
        "errors": [],
    }
    write(TREE / "diagnostics/precompile_core_capture_contract.json", capture)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    additions = [
        {"source_root": "attempt", "source": "evidence/PACKAGE_PREFLIGHT_STDOUT.txt", "archive": "evidence/PACKAGE_PREFLIGHT_STDOUT.txt", "required": True},
        {"source_root": "attempt", "source": "evidence/PACKAGE_PREFLIGHT_STDERR.txt", "archive": "evidence/PACKAGE_PREFLIGHT_STDERR.txt", "required": True},
        {"source_root": "attempt", "source": "evidence/PACKAGE_PREFLIGHT_EXECUTION.json", "archive": "evidence/PACKAGE_PREFLIGHT_EXECUTION.json", "required": True},
        {"source_root": "attempt", "source": "evidence/RUNNER_STAGE_RECEIPT.json", "archive": "evidence/RUNNER_STAGE_RECEIPT.json", "required": True},
        {"source_root": "package", "source": "diagnostics/precompile_core_capture_contract.json", "archive": "source_package/precompile_core_capture_contract.json", "required": True},
        {"source_root": "package", "source": "provenance/v68_formal_return_analysis.json", "archive": "source_package/v68_formal_return_analysis.json", "required": True},
        {"source_root": "package", "source": "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json", "archive": "source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json", "required": True},
        {"source_root": "package", "source": "provenance/SHARED_RULE_AUDIT_ESCALATION.json", "archive": "source_package/SHARED_RULE_AUDIT_ESCALATION.json", "required": True},
    ]
    archives = {row.get("archive") for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)

    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    allow["package_id"] = NEW
    required = set(allow.get("required", []))
    for relative in capture["required_return_members"]:
        required.add(relative)
        required.add(f"{NEW}_return/{relative}")
    required.update({
        f"{NEW}_return/source_package/precompile_core_capture_contract.json",
        f"{NEW}_return/source_package/v68_formal_return_analysis.json",
        f"{NEW}_return/source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json",
        f"{NEW}_return/source_package/SHARED_RULE_AUDIT_ESCALATION.json",
    })
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
    projected_absolute = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(projected)
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    if isinstance(layout.get("runner_bindings"), dict):
        layout["runner_bindings"]["runner_sha256"] = runner_sha
    write(layout_path, layout)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post["package_id"] = NEW
    post["request_sha256"] = sha(request_path)
    post["runner_sha256"] = runner_sha
    post["helper_sha256"] = sha(TREE / "package_tools/server_post_sim_return.py")
    write(post_path, post)

    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    vcd = load(vcd_path)
    vcd["execution"]["tb_source_sha256"] = sha(TREE / NEW_TB)
    write(vcd_path, vcd)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = NEW
    selector["vcd_contract_sha256"] = sha(vcd_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {
        "source_package/precompile_core_capture_contract.json",
        "source_package/v68_formal_return_analysis.json",
        "source_package/PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json",
        "source_package/SHARED_RULE_AUDIT_ESCALATION.json",
        "evidence/PACKAGE_PREFLIGHT_STDOUT.txt",
        "evidence/PACKAGE_PREFLIGHT_STDERR.txt",
        "evidence/PACKAGE_PREFLIGHT_EXECUTION.json",
        "evidence/RUNNER_STAGE_RECEIPT.json",
    })
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)

    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["package_id"] = NEW
    manifest["package_identity"] = NEW
    manifest["install_name"] = NEW
    manifest["activation_epoch"] = EPOCH
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["previous_version_progress"] = "v68 preserved exact 4/2 and the 64-signal target cone, but the third attempt stopped inside package runtime preflight before production compile; the return omitted the preflight true error."
    manifest["current_version_purpose"] = "Preserve the exact v68 functional/diagnostic package while returning package-preflight stdout, stderr, exit, stage and first-error evidence before retrying the unchanged production target."
    manifest["package_build_failure_rule_audit"] = "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT_RECURRING_ESCAPE.json"
    manifest["precompile_core_capture"] = "diagnostics/precompile_core_capture_contract.json"
    manifest["diagnostic_mode_selector_sha256"] = sha(selector_path)
    manifest["path_length_budget"]["longest_projected_relative_path"] = projected
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(projected)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = projected_absolute
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
    if not SOURCE_PENDING.is_file() or sha(SOURCE_PENDING) != OLD_SHA:
        raise RuntimeError("protected v68 pending identity drifted")
    if not SOURCE_RELEASE_ZIP.is_file() or sha(SOURCE_RELEASE_ZIP) != OLD_SHA or not SOURCE_TREE.is_dir():
        raise RuntimeError("durable v68 staging is not exact")
    analysis = load(ANALYSIS)
    audit = load(AUDIT)
    if analysis.get("successor_disposition") != "FRESH_RUNNER_RETURN_ONLY_SUCCESSOR_WARRANTED" or not analysis.get("pass"):
        raise RuntimeError("v68 analysis does not admit the runner/return successor")
    if audit.get("adjudication", {}).get("class") != "EXISTING_RULE_IMPLEMENTATION_ESCAPE" or not audit.get("pass"):
        raise RuntimeError("recurring package-build audit authority is absent")

    source_identity = identity(SOURCE_PENDING)
    source_validation = subtree_map(SOURCE_TREE / "validation")
    source_workload = subtree_map(
        SOURCE_TREE / "workload",
        ignore={"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"},
    )
    source_bitstream = sha(SOURCE_TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    source_config = sha(SOURCE_TREE / "provenance/config_lineage/op_tail_round_4_2.json")
    source_catalog = normalized_json(SOURCE_TREE / "diagnostics/tb_vcd_signal_catalog.json", OLD)
    source_matrix = normalized_json(SOURCE_TREE / "diagnostics/tb_vcd_candidate_matrix.json", OLD)
    source_tb_normalized = (SOURCE_TREE / OLD_TB).read_text(encoding="utf-8").replace(OLD, "<PACKAGE_ID>").replace("v68", "vXX")

    replace_identity()
    patch_runner_capture()
    bind_analysis_and_contracts()
    refresh_identities()

    frozen_checks = {
        "v68_pending_byte_frozen": identity(SOURCE_PENDING) == source_identity,
        "config42_bitstream_exact": sha(TREE / "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin") == source_bitstream == GOOD_BITSTREAM,
        "config_json_exact": sha(TREE / "provenance/config_lineage/op_tail_round_4_2.json") == source_config,
        "validation_payload_exact": subtree_map(TREE / "validation") == source_validation,
        "workload_payload_exact_except_identity_sca": subtree_map(TREE / "workload", ignore={"runtime/sca_cfg.json", "runtime/sca_cfg_D.json"}) == source_workload,
        "signal_catalog_exact_except_fresh_identity": normalized_json(TREE / "diagnostics/tb_vcd_signal_catalog.json", NEW) == source_catalog,
        "candidate_matrix_exact_except_fresh_identity": normalized_json(TREE / "diagnostics/tb_vcd_candidate_matrix.json", NEW) == source_matrix,
        "tb_semantics_exact_except_fresh_identity": (TREE / NEW_TB).read_text(encoding="utf-8").replace(NEW, "<PACKAGE_ID>").replace("v69", "vXX") == source_tb_normalized,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
    }
    frozen = {
        "schema": "qadd-v69-frozen-surface-v1",
        "package_id": NEW,
        "checks": frozen_checks,
        "changed_surfaces": ["fresh_identity", "package_preflight_stdout_stderr_exit_stage_capture", "compile_not_started_first_error_core", "return_provenance"],
        "frozen": ["validated_config42", "numeric", "workload_payload", "golden", "functional_rtl", "tail_round_target", "64_signal_causal_cone", "candidate_matrix", "tb_functional_observation_semantics"],
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": all(frozen_checks.values()),
        "errors": [name for name, passed in frozen_checks.items() if not passed],
    }
    write(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen-surface failure: {frozen['errors']}")

    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if sha(ZIP) != sha(REPEAT) or ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic ZIP recomputation differs")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("final ZIP CRC failed")
    receipt = {
        "schema": "qadd-v69-precompile-core-build-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": NEW,
        "activation_epoch": EPOCH,
        "source_v68": source_identity,
        "return_analysis": identity(ANALYSIS),
        "recurring_package_build_failure_rule_audit": identity(AUDIT),
        "shared_rule_audit_escalation": identity(ESCALATION),
        "package": identity(ZIP),
        "repeat_package": identity(REPEAT),
        "deterministic_recompute": True,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "pass": True,
        "errors": [],
        "claim_boundary": "Local runner/return construction only; no production compile, target, config repair, natural/Formal-D or E3-E5 claim.",
    }
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
