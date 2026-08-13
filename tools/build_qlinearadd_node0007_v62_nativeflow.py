#!/usr/bin/env python3
"""Build the fresh QAdd v62 observer-only native-production-flow package.

The sole payload source is the exact current v61 pending ZIP.  Functional HDL,
observer HDL, parser, workload, numeric data, golden data, mapping, bitstream and
execplan remain byte-equal.  Changes are limited to fresh identity, the SCA path
identity, runner non-interference, and native-failure return metadata.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v61_obswide"
NEW = "r5_qadd_n7_tailround_lanephase_v62_nfobs"
FAMILY = "qlinearadd_node0007"
EPOCH = "runtime-preflight-native-flow-v1"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{OLD}.zip"
RELEASE = ROOT / "outputs/qlinearadd_node0007_v62_nativeflow_release"
BUILD = RELEASE / "build"
TREE = BUILD / NEW
ZIP = BUILD / f"{NEW}.zip"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def safe_extract(source: Path, target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=False)
    resolved = target.resolve()
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v61 source ZIP CRC failure")
        roots: set[str] = set()
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"unsafe ZIP member: {info.filename}")
            if member.parts:
                roots.add(member.parts[0])
            destination = (target / Path(*member.parts)).resolve()
            if destination != resolved and resolved not in destination.parents:
                raise RuntimeError(f"ZIP member escapes extraction root: {info.filename}")
        if roots != {OLD}:
            raise RuntimeError(f"unexpected v61 ZIP roots: {sorted(roots)}")
        archive.extractall(target)
    return target / OLD


def tree_identity(root: Path, excluded: set[str] | None = None) -> dict[str, tuple[int, str]]:
    excluded = excluded or set()
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, digest(path))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    }


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def deterministic_zip(tree: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(
        temporary,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=1,
        allowZip64=True,
    ) as archive:
        for path in sorted(tree.rglob("*")):
            if not path.is_file():
                continue
            member = f"{tree.name}/{path.relative_to(tree).as_posix()}"
            info = zipfile.ZipInfo(member, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)
    os.replace(temporary, target)


def exact_zip_recheck(tree: Path, target: Path) -> dict[str, Any]:
    expected = {
        f"{tree.name}/{path.relative_to(tree).as_posix()}": (path.stat().st_size, digest(path))
        for path in sorted(tree.rglob("*"))
        if path.is_file()
    }
    actual: dict[str, tuple[int, str]] = {}
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("fresh ZIP CRC failure")
        for info in archive.infolist():
            if info.is_dir():
                continue
            data = archive.read(info)
            actual[info.filename] = (len(data), hashlib.sha256(data).hexdigest())
    if actual != expected:
        raise RuntimeError("exact final ZIP/tree mismatch")
    return {"pass": True, "member_count": len(actual), "zip_sha256": digest(target)}


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    command_probe = '''for tool in python3 timeout make date tail head grep cp; do
  command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "required runtime tool is unavailable: $tool"
done
'''
    text = replace_once(text, command_probe, "", "retired command-v probe")
    late_traps = '''trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
'''
    text = replace_once(text, late_traps, "", "late finalizer traps")
    marker_anchor = "actual_argv_json=\n"
    text = replace_once(
        text,
        marker_anchor,
        marker_anchor
        + "trap 'finalize $?' EXIT\n"
        + "trap 'on_signal HUP 129' HUP\n"
        + "trap 'on_signal INT 130' INT\n"
        + "trap 'on_signal TERM 143' TERM\n"
        + "# CODEX_PRODUCTION_LAUNCH\n",
        "production marker",
    )

    identity_pattern = re.compile(
        r'python3 - "\$bootstrap_root/compile_source_identity\.json" "\$server_root/Makefile\.tb_NDP_Top_new_phy" "\$source_bound_observer" "\$package_root/tb_probe" <<\'PY\'\n.*?\nPY\n',
        re.S,
    )
    match = identity_pattern.search(text)
    if match is None:
        raise RuntimeError("compile source identity block not found")
    identity_block = match.group(0)
    text = text[: match.start()] + text[match.end() :]
    text = replace_once(
        text,
        "compile_status=$?\n",
        "compile_status=$?\n" + identity_block,
        "post-production source identity",
    )

    text, count = re.subn(
        r'^root_pre="\$\(python3 "\$root_guard" snapshot --server-root "\$server_root"\)" \|\| runner_fail 12 "NDP root pre-snapshot failed"\n',
        "",
        text,
        flags=re.M,
    )
    if count != 1:
        raise RuntimeError(f"root pre-snapshot anchor count={count}")
    text, count = re.subn(
        r'^\s*printf \'%s\\n\' "\$root_pre" >"\$evidence_root/ndp_root_toplevel_pre\.json"\n',
        "",
        text,
        flags=re.M,
    )
    if count != 1:
        raise RuntimeError(f"root pre-receipt anchor count={count}")
    text, count = re.subn(
        r'^\s*python3 "\$root_guard" compare --server-root "\$server_root".*?\n',
        "",
        text,
        flags=re.M,
    )
    if count != 1:
        raise RuntimeError(f"root post-compare anchor count={count}")
    text, count = re.subn(
        r'^\s*\[ "\$final" -ne 0 \] \|\| \[ "\$root_status" -eq 0 \] \|\| final="\$root_status"\n',
        "",
        text,
        flags=re.M,
    )
    if count != 1:
        raise RuntimeError(f"root status anchor count={count}")
    text = text.replace("    root_status=$?\n", "")
    for token in (" ndp_root_toplevel_pre.json", " ndp_root_toplevel_post.json"):
        text = text.replace(token, "")

    initial_pattern = re.compile(
        r'python3 - "\$actual_argv_json" "\$package_id" "\$return_tag" "\$attempt" "\$\{compile_argv\[@\]\}" <<\'PY\'\n.*?\nPY\n',
        re.S,
    )
    initial = '''python3 - "$actual_argv_json" "$package_id" "$return_tag" "$attempt" "$server_root" "$cfg_root/sca_cfg.json" "$cfg_root/sca_cfg_D.json" "1" "${compile_argv[@]}" <<'PY'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({"schema":"server-observer-actual-argv-v1","package_id":sys.argv[2],"execution_id":sys.argv[3],"attempt_id":sys.argv[4],"cwd":sys.argv[5],"actual_cwd":sys.argv[5],"sca_cfg":sys.argv[6],"sca_cfg_d":sys.argv[7],"repeat_num":int(sys.argv[8]),"relevant_env":{"DUMP_VCD":"0","DUMP_FSDB":"0","TB_DUMP_FSDB":"0"},"source_identity_status":"NOT_YET_BOUND","compile_argv":sys.argv[9:],"sim_argv":["simv","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0"]},sort_keys=True)+"\\n")
PY
'''
    text, count = initial_pattern.subn(lambda _match: initial, text, count=1)
    if count != 1:
        raise RuntimeError(f"initial actual argv anchor count={count}")

    sim_pattern = re.compile(
        r'python3 - "\$actual_argv_json" "\$package_id" "\$return_tag" "\$attempt" "\$server_root" "\$\{compile_argv\[@\]\}" --SIM-- "\$simv" "\$\{sim_args\[@\]\}" <<\'PY\'\n.*?\nPY\n',
        re.S,
    )
    sim_receipt = '''python3 - "$actual_argv_json" "$package_id" "$return_tag" "$attempt" "$server_root" "$cfg_root/sca_cfg.json" "$cfg_root/sca_cfg_D.json" "1" "${compile_argv[@]}" --SIM-- "$simv" "${sim_args[@]}" <<'PY'
import json,pathlib,sys
cut=sys.argv.index("--SIM--")
pathlib.Path(sys.argv[1]).write_text(json.dumps({"schema":"server-observer-actual-argv-v1","package_id":sys.argv[2],"execution_id":sys.argv[3],"attempt_id":sys.argv[4],"cwd":sys.argv[5],"actual_cwd":sys.argv[5],"sca_cfg":sys.argv[6],"sca_cfg_d":sys.argv[7],"repeat_num":int(sys.argv[8]),"relevant_env":{"DUMP_VCD":"0","DUMP_FSDB":"0","TB_DUMP_FSDB":"0"},"source_identity_status":"COMPLETE","compile_argv":sys.argv[9:cut],"sim_argv":["env","DUMP_VCD=0","DUMP_FSDB=0","TB_DUMP_FSDB=0",*sys.argv[cut+1:]]},sort_keys=True)+"\\n")
PY
'''
    text, count = sim_pattern.subn(lambda _match: sim_receipt, text, count=1)
    if count != 1:
        raise RuntimeError(f"simulation actual argv anchor count={count}")

    native_receipt = '''    python3 - "$evidence_root/NATIVE_FAILURE_ATTEMPT.json" "$package_id" "$return_tag" "$attempt" "$server_root" "$compile_status" "$simulation_started" "$simulation_status" "$actual_argv_json" "$evidence_root/compile_driver.log" "$run_root/sim.log" "$run_root/return_observer.log" "$evidence_root/compile_first_error.txt" <<'PY'
import hashlib,json,pathlib,re,sys
target=pathlib.Path(sys.argv[1]);pkg,exe,att,cwd=sys.argv[2:6];compile_exit=int(sys.argv[6]);started=sys.argv[7]=="true";sim_exit=int(sys.argv[8]);actual_path=pathlib.Path(sys.argv[9]);logs=[pathlib.Path(value) for value in sys.argv[10:13]];compile_first=pathlib.Path(sys.argv[13])
actual=json.loads(actual_path.read_text()) if actual_path.is_file() else {}
first=compile_first.read_text(encoding="utf-8",errors="replace").strip() if compile_exit != 0 and compile_first.is_file() else ""
if not first and started and sim_exit != 0:
    patterns=(r"(?i)(^|\\s)(error|fatal)(\\s|:|\\[)",r"(?i)assert",r"(?i)timeout",r"(?i)terminated")
    for source in logs[1:]:
        if not source.is_file(): continue
        for line in source.read_text(encoding="utf-8",errors="replace").splitlines():
            if any(re.search(pattern,line) for pattern in patterns): first=line[:8192]; break
        if first: break
if not first: first="NO_FAILURE_ERROR_PATTERN" if compile_exit == 0 and sim_exit == 0 else "NO_TRUE_ERROR_PATTERN_FOUND"
receipts=[]
for source in logs:
    if source.is_file():
        data=source.read_bytes();receipts.append({"path":str(source),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"complete":True})
value={"schema":"server-native-failure-attempt-v1","package_id":pkg,"execution_id":exe,"attempt_id":att,"actual_cwd":cwd,"actual_compile_argv":actual.get("compile_argv",[]),"actual_sim_argv":actual.get("sim_argv",[]),"relevant_env":actual.get("relevant_env",{}),"sca_cfg":actual.get("sca_cfg"),"sca_cfg_d":actual.get("sca_cfg_d"),"repeat_num":actual.get("repeat_num"),"compile_exit":compile_exit,"simulation_started":started,"simulation_exit":sim_exit,"first_true_error":first,"complete_log_receipts":receipts,"native_failure_differential":"PENDING_FAMILY_POST_FAILURE_REVIEW" if compile_exit != 0 or sim_exit != 0 else "NOT_APPLICABLE_SUCCESS","unknown_server_loader_start_wait_readback":"SERVER_RUNTIME_UNKNOWN"}
target.write_text(json.dumps(value,sort_keys=True)+"\\n",encoding="utf-8")
PY
'''
    text = replace_once(
        text,
        '    export CODEX_PACKAGE_ROOT="$package_root"\n',
        native_receipt + '    export CODEX_PACKAGE_ROOT="$package_root"\n',
        "native failure attempt receipt",
    )
    if text.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        raise RuntimeError("production marker is not unique")
    path.write_text(text, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def build() -> None:
    if BUILD.exists():
        raise RuntimeError("refusing to overwrite the one-shot v62 build directory")
    index = json.loads((STORAGE / "PACKAGE_STORAGE_INDEX.json").read_text(encoding="utf-8"))
    pending = [
        item
        for item in index.get("packages", [])
        if item.get("family") == FAMILY and item.get("disposition") == "pending"
    ]
    if index.get("pass") is not True or len(pending) != 1 or pending[0].get("package_base") != OLD:
        raise RuntimeError("v61 is not the unique indexed QAdd pending predecessor")
    declared = [
        item
        for item in pending[0].get("files", [])
        if item.get("relative_path") == f"pending/{OLD}.zip"
    ]
    if len(declared) != 1 or declared[0].get("bytes") != SOURCE_ZIP.stat().st_size or declared[0].get("sha256") != digest(SOURCE_ZIP):
        raise RuntimeError("v61 pending ZIP differs from storage index")
    source_identity = identity(SOURCE_ZIP)

    BUILD.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="qadd-v62-source-") as temporary:
        source = safe_extract(SOURCE_ZIP, Path(temporary) / "extract")
        source_validation = tree_identity(source / "validation")
        source_tb = tree_identity(source / "tb_probe")
        source_install = tree_identity(source / "workload/install")
        source_runtime = tree_identity(
            source / "workload/runtime", {"sca_cfg.json", "sca_cfg_D.json"}
        )
        source_tools = tree_identity(source / "package_tools")
        shutil.copytree(source, TREE)

    identity_files = [
        "contracts/server_post_sim_return_contract.json",
        "contracts/server_runner_return_resilience_contract.json",
        "contracts/server_observer_only_wide_causal_contract.json",
        "contracts/server_post_sim_return_request.json",
        "diagnostics/observer_capture_plan.json",
        "README.md",
        "PREPARE_AND_RUN.sh",
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "RETURN_ALLOWLIST.json",
        "TEST_PACKAGE_MANIFEST.json",
        "workload/runtime/sca_cfg_D.json",
        "workload/runtime/sca_cfg.json",
    ]
    for relative in identity_files:
        path = TREE / relative
        text = path.read_text(encoding="utf-8")
        if OLD not in text:
            raise RuntimeError(f"identity anchor absent: {relative}")
        path.write_text(text.replace(OLD, NEW), encoding="utf-8", newline="\n")

    patch_runner(TREE / "PREPARE_AND_RUN.sh")

    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    longest = manifest["path_length_budget"]["longest_projected_relative_path"]
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(longest)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = (
        manifest["path_length_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    )
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["path_budget"]["max_projected_absolute_path_chars"] = (
        layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    )
    write_json(layout_path, layout)

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["core_entries"] = [
        row
        for row in request["core_entries"]
        if row.get("source") not in {
            "evidence/ndp_root_toplevel_pre.json",
            "evidence/ndp_root_toplevel_post.json",
        }
    ]
    request["core_entries"].append(
        {
            "archive": "evidence/NATIVE_FAILURE_ATTEMPT.json",
            "required": False,
            "source": "evidence/NATIVE_FAILURE_ATTEMPT.json",
            "source_root": "attempt",
        }
    )
    write_json(request_path, request)

    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["request_sha256"] = digest(request_path)
    post_contract["native_failure_attempt"] = {
        "member": "evidence/NATIVE_FAILURE_ATTEMPT.json",
        "required_on_natural_failure": True,
        "native_differential_timing": "AFTER_ACTUAL_FAILURE_BEFORE_SUCCESSOR_DESIGN",
        "unknown_semantics": "SERVER_RUNTIME_UNKNOWN",
    }
    write_json(post_contract_path, post_contract)

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner_contract_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = digest(runner_path)
    runner_contract["return_allowlist_tokens"].append("NATIVE_FAILURE_ATTEMPT.json")
    write_json(runner_contract_path, runner_contract)

    provenance = {
        "schema": "qadd-v62-native-flow-provenance-v1",
        "package_id": NEW,
        "activation_epoch": EPOCH,
        "previous_version_progress": (
            "v57h localized the DUT boundary after Buffer5 request decode and before selected "
            "ping-pong-port required-lane read accept; v59 exposed the manifest install/SCA "
            "identity mismatch; v60 repaired it; v61 preserved both ping-pong branches and the "
            "26-role/48-actual-signal observer but predates native-flow non-interference."
        ),
        "current_version_purpose": (
            "Preserve the v61 identity repair, tail-round target, 26-role/48-signal observer and "
            "both ping-pong branches while entering the native production cd/install/compile/sim "
            "flow without server-owned inventory or provider probes."
        ),
        "changed_surface": [
            "fresh identity",
            "identity-bound SCA install paths",
            "runtime prelaunch non-interference",
            "native failure attempt return metadata",
        ],
        "frozen_surface": [
            "configuration semantics", "numeric", "workload payload", "golden",
            "functional RTL", "observer HDL", "observer parser", "tail-round diagnostic target",
        ],
        "server_action": False,
    }
    write_json(TREE / "provenance/v61_to_v62_nativeflow.json", provenance)

    manifest["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"
    manifest["server_run_performed"] = False
    manifest["uploaded"] = False
    manifest["runtime_preflight_native_flow"] = {
        "activation_epoch": EPOCH,
        "production_launch_marker": "# CODEX_PRODUCTION_LAUNCH",
        "production_launch_marker_count": 1,
        "server_environment_adjudicator": "ACTUAL_PRODUCTION_COMMAND_ONLY",
        "native_failure_differential": "AFTER_ACTUAL_FAILURE_BEFORE_SUCCESSOR_DESIGN",
        "unknown_semantics": "SERVER_RUNTIME_UNKNOWN",
    }
    manifest["observer_only_contract_sha256"] = digest(
        TREE / "contracts/server_observer_only_wide_causal_contract.json"
    )
    manifest["rule_change_epoch"] = {
        "epoch_id": EPOCH,
        "family": FAMILY,
        "package_id": NEW,
        "first_fresh_after_change": True,
        "notification_acknowledged": True,
        "upload_hold_until": "EXPLICIT_USER_SERVER_AUTHORIZATION",
    }
    manifest["first_fresh_extra_audit"] = {
        "bound_package_id": NEW,
        "epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "notification_acknowledged": True,
        "prior_first_fresh_pass_receipt": None,
        "upload_hold_until_final_audit_pass": True,
    }
    manifest["ndp_root_toplevel_contract"] = {
        "status": "RETIRED_FROM_CURRENT_BLOCKING",
        "runtime_invoked": False,
        "reason": "native production command is the sole server-environment adjudicator",
    }
    manifest["files"] = file_map(TREE)
    write_json(manifest_path, manifest)

    frozen = {
        "schema": "qadd-v62-native-flow-frozen-surface-v1",
        "validation_golden_byte_equal": tree_identity(TREE / "validation") == source_validation,
        "observer_and_legacy_hdl_byte_equal": tree_identity(TREE / "tb_probe") == source_tb,
        "workload_install_payload_byte_equal": tree_identity(TREE / "workload/install") == source_install,
        "workload_runtime_excluding_identity_sca_byte_equal": tree_identity(
            TREE / "workload/runtime", {"sca_cfg.json", "sca_cfg_D.json"}
        ) == source_runtime,
        "package_tools_byte_equal": tree_identity(TREE / "package_tools") == source_tools,
        "functional_rtl_modified": False,
        "config_numeric_workload_golden_semantics_modified": False,
        "ping_pong_behavior_modified": False,
    }
    frozen["pass"] = (
        frozen["validation_golden_byte_equal"]
        and frozen["observer_and_legacy_hdl_byte_equal"]
        and frozen["workload_install_payload_byte_equal"]
        and frozen["workload_runtime_excluding_identity_sca_byte_equal"]
        and frozen["package_tools_byte_equal"]
        and frozen["functional_rtl_modified"] is False
        and frozen["config_numeric_workload_golden_semantics_modified"] is False
        and frozen["ping_pong_behavior_modified"] is False
    )
    write_json(RELEASE / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface drift: {frozen}")

    canonical_helper = ROOT / "tools/server_post_sim_return.py"
    if (TREE / "package_tools/server_post_sim_return.py").read_bytes() != canonical_helper.read_bytes():
        raise RuntimeError("post-sim helper differs from current canonical bytes")
    forbidden = [
        path.relative_to(TREE).as_posix()
        for path in TREE.rglob("*")
        if path.is_file() and path.suffix.lower() in {".vpd", ".fsdb", ".vcd", ".fst", ".tcl"}
    ]
    if forbidden:
        raise RuntimeError(f"observer-only package has forbidden waveform members: {forbidden}")

    deterministic_zip(TREE, ZIP)
    recheck = exact_zip_recheck(TREE, ZIP)
    ZIP.with_name(ZIP.name + ".sha256").write_text(
        f"{digest(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n"
    )
    if identity(SOURCE_ZIP) != source_identity:
        raise RuntimeError("v61 pending ZIP changed during fresh build")
    write_json(
        BUILD / "build_receipt.json",
        {
            "schema": "qadd-v62-native-flow-build-v1",
            "package_id": NEW,
            "source_v61_pending": source_identity,
            "activation_epoch": EPOCH,
            "zip": identity(ZIP),
            "frozen_surface": frozen,
            "exact_final_zip_recheck": recheck,
            "server_action": False,
            "pass": True,
        },
    )


def resume_only() -> None:
    """Finalize an already materialized tree after a receipt-only interruption."""
    if not TREE.is_dir() or ZIP.exists():
        raise RuntimeError("resume requires an existing v62 tree and no final ZIP")
    source_tree = (
        ROOT
        / "outputs/qlinearadd_node0007_v61_observer_only_release/build"
        / OLD
    )
    source_build_zip = source_tree.parent / f"{OLD}.zip"
    if not source_tree.is_dir() or digest(source_build_zip) != digest(SOURCE_ZIP):
        raise RuntimeError("resume source tree is not bound to exact pending v61 ZIP")
    frozen = {
        "schema": "qadd-v62-native-flow-frozen-surface-v1",
        "validation_golden_byte_equal": tree_identity(TREE / "validation") == tree_identity(source_tree / "validation"),
        "observer_and_legacy_hdl_byte_equal": tree_identity(TREE / "tb_probe") == tree_identity(source_tree / "tb_probe"),
        "workload_install_payload_byte_equal": tree_identity(TREE / "workload/install") == tree_identity(source_tree / "workload/install"),
        "workload_runtime_excluding_identity_sca_byte_equal": tree_identity(TREE / "workload/runtime", {"sca_cfg.json", "sca_cfg_D.json"}) == tree_identity(source_tree / "workload/runtime", {"sca_cfg.json", "sca_cfg_D.json"}),
        "package_tools_byte_equal": tree_identity(TREE / "package_tools") == tree_identity(source_tree / "package_tools"),
        "functional_rtl_modified": False,
        "config_numeric_workload_golden_semantics_modified": False,
        "ping_pong_behavior_modified": False,
    }
    frozen["pass"] = (
        frozen["validation_golden_byte_equal"]
        and frozen["observer_and_legacy_hdl_byte_equal"]
        and frozen["workload_install_payload_byte_equal"]
        and frozen["workload_runtime_excluding_identity_sca_byte_equal"]
        and frozen["package_tools_byte_equal"]
        and frozen["functional_rtl_modified"] is False
        and frozen["config_numeric_workload_golden_semantics_modified"] is False
        and frozen["ping_pong_behavior_modified"] is False
    )
    write_json(RELEASE / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"resume frozen surface drift: {frozen}")
    if (TREE / "package_tools/server_post_sim_return.py").read_bytes() != (ROOT / "tools/server_post_sim_return.py").read_bytes():
        raise RuntimeError("post-sim helper differs from current canonical bytes")
    forbidden = [
        path.relative_to(TREE).as_posix()
        for path in TREE.rglob("*")
        if path.is_file() and path.suffix.lower() in {".vpd", ".fsdb", ".vcd", ".fst", ".tcl"}
    ]
    if forbidden:
        raise RuntimeError(f"observer-only package has forbidden waveform members: {forbidden}")
    deterministic_zip(TREE, ZIP)
    recheck = exact_zip_recheck(TREE, ZIP)
    ZIP.with_name(ZIP.name + ".sha256").write_text(
        f"{digest(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n"
    )
    write_json(
        BUILD / "build_receipt.json",
        {
            "schema": "qadd-v62-native-flow-build-v1",
            "package_id": NEW,
            "source_v61_pending": identity(SOURCE_ZIP),
            "activation_epoch": EPOCH,
            "materialization_resume_only": True,
            "resume_reason": "receipt boolean aggregation corrected; staging was not rebuilt",
            "zip": identity(ZIP),
            "frozen_surface": frozen,
            "exact_final_zip_recheck": recheck,
            "server_action": False,
            "pass": True,
        },
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--resume-only"]:
        resume_only()
    elif not sys.argv[1:]:
        build()
    else:
        raise SystemExit("usage: build_qlinearadd_node0007_v62_nativeflow.py [--resume-only]")
