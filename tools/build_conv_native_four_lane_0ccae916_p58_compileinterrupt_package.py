#!/usr/bin/env python3
"""Build native-Conv p58: p57's exact causal cone plus compile-signal return repair.

This is deliberately a package-local successor.  It consumes the exact managed
p57 ZIP, preserves every diagnostic/config/RTL/workload byte except identity
and return-runtime surfaces, and makes a signal during native production
compile produce a reaped process receipt and bounded compile core.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_0cc_p57_globalexec"
PACKAGE = "r5_n4_0cc_p58_compileinterrupt"
FAMILY = "conv_native_four_lane"
EPOCH = "conv-native-p58-compile-signal-finalization-v1"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
ANALYSIS = ROOT / "outputs/conv_native_p57_globalexec_return_analysis_r1787386659935327695_1258886"
OUT = ROOT / "outputs/conv_native_p58_compileinterrupt_20260822"
BUILD = OUT / "build"
TREE = BUILD / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
REPEAT = OUT / f"{PACKAGE}.repeat.zip"
GATES = OUT / "gates"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def identity(path: Path) -> dict[str, Any]:
    return {"size_bytes": path.stat().st_size, "sha256": sha(path)}


def deterministic_zip(root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root.parent).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            executable = bool(path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
            info.external_attr = ((0o100755 if executable else 0o100644) << 16)
            archive.writestr(info, path.read_bytes())


COMPILE_HELPER = r'''#!/usr/bin/env python3
"""Own the native compile process group and guarantee signal-safe reaping."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PR_SET_CHILD_SUBREAPER = 36


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def enable_subreaper() -> dict:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        rc = libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
        if rc != 0:
            return {"enabled": False, "errno": ctypes.get_errno()}
        return {"enabled": True}
    except Exception as exc:
        return {"enabled": False, "error": str(exc)}


def reap_until(deadline: float) -> list[int]:
    reaped: list[int] = []
    while time.monotonic() < deadline:
        changed = False
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return reaped
            if pid <= 0:
                break
            reaped.append(pid)
            changed = True
        if not changed:
            time.sleep(0.05)
    return reaped


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("supervise")
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--grace-seconds", type=float, default=30.0)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("compile command is required")
    attempt = args.attempt_root.resolve(strict=True)
    for candidate in (args.receipt.resolve().parent, args.result.resolve().parent):
        candidate.mkdir(parents=True, exist_ok=True)
        candidate.resolve().relative_to(attempt)
    received: list[int] = []
    old_handlers: dict[int, object] = {}
    def handler(signum: int, _frame: object) -> None:
        received.append(signum)
    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        old_handlers[signum] = signal.signal(signum, handler)
    subreaper = enable_subreaper()
    started_ns = time.monotonic_ns()
    proc = subprocess.Popen(command, cwd=args.cwd, start_new_session=True)
    pgid = os.getpgid(proc.pid)
    termination: list[dict] = []
    try:
        while proc.poll() is None and not received:
            time.sleep(0.05)
        if received and proc.poll() is None:
            os.killpg(pgid, signal.SIGTERM)
            termination.append({"signal": "TERM", "reason": signal.Signals(received[-1]).name})
            deadline = time.monotonic() + args.grace_seconds
            while proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            if proc.poll() is None:
                os.killpg(pgid, signal.SIGKILL)
                termination.append({"signal": "KILL", "reason": "TERM_GRACE_EXPIRED"})
        try:
            root_exit = proc.wait(timeout=max(args.grace_seconds, 0.1))
        except subprocess.TimeoutExpired:
            root_exit = None
        reaped = reap_until(time.monotonic() + max(args.grace_seconds, 0.1))
    finally:
        for signum, old in old_handlers.items():
            signal.signal(signum, old)
    receipt = {
        "schema": "server-native-compile-process-supervision-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "actual_cwd": str(args.cwd.resolve()),
        "actual_argv": command,
        "root_pid": proc.pid,
        "pgid": pgid,
        "child_subreaper": subreaper,
        "started_host_monotonic_ns": started_ns,
        "received_signal": signal.Signals(received[-1]).name if received else "NONE",
        "root_exit": root_exit,
        "termination": termination,
        "reaped_pids": reaped,
        "process_tree_reaped": root_exit is not None,
        "diagnostic_status": "COMPLETE" if root_exit is not None else "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
    }
    write_json(args.receipt, receipt)
    write_json(args.result, {**receipt, "result_kind": "COMPILE_STAGE_RESULT"})
    if received:
        return 128 + int(received[-1])
    return int(root_exit if root_exit is not None else 125)


if __name__ == "__main__":
    raise SystemExit(main())
'''


def replace_identity(tree: Path) -> None:
    suffixes = {".json", ".md", ".sh", ".py", ".sv", ".txt"}
    for path in sorted(item for item in tree.rglob("*") if item.is_file() and item.suffix.lower() in suffixes):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if OLD in text:
            path.write_text(text.replace(OLD, PACKAGE), encoding="utf-8", newline="\n")


def patch_runner(tree: Path) -> None:
    path = tree / "PREPARE_AND_RUN.sh"
    runner = path.read_text(encoding="utf-8")
    old_vars = 'simv=""\n'
    new_vars = '''simv=""
compile_supervisor_pid=""
compile_finalize_done=false
compile_process_receipt="$bootstrap_root/COMPILE_PROCESS_TREE_RECEIPT.json"
compile_stage_result="$bootstrap_root/COMPILE_STAGE_RESULT.json"
'''
    if old_vars not in runner:
        raise RuntimeError("runner variable anchor absent")
    runner = runner.replace(old_vars, new_vars, 1)
    old_begin = 'finalize() {\n'
    helper = '''compile_core_finalize() {
  [ "$compile_finalize_done" = true ] && return 0
  [ -f "$compile_driver_log" ] || return 0
  python3 "$package_root/package_tools/compile_core_evidence.py" finalize --output-root "$bootstrap_root" --exit-code "$compile_status" || return $?
  python3 "$package_root/package_tools/capture_actual_compiled_sources.py" --server-root "$server_root" --compile-log "$compile_driver_log" --output-root "$bootstrap_root/actual_compiled_sources" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" || printf 'CODEX_WARNING actual compiled source capture incomplete; core return preserved\\n' >&2
  [ ! -f "$compile_process_receipt" ] || cp -f "$compile_process_receipt" "$evidence_root/compile_rootcause/COMPILE_PROCESS_TREE_RECEIPT.json"
  [ ! -f "$compile_process_receipt" ] || cp -f "$compile_process_receipt" "$evidence_root/PROCESS_TREE_RECEIPT.json"
  [ ! -f "$compile_stage_result" ] || cp -f "$compile_stage_result" "$evidence_root/compile_rootcause/COMPILE_STAGE_RESULT.json"
  compile_finalize_done=true
  return 0
}

finalize() {
'''
    if old_begin not in runner:
        raise RuntimeError("runner finalizer anchor absent")
    runner = runner.replace(old_begin, helper, 1)
    old_core = '  python3 "$package_root/package_tools/compile_core_evidence.py" return-core --output-root "$bootstrap_root"'
    new_core = '  compile_core_finalize\n  compile_finalize_rc=$?\n  [ "$original" -ne 0 ] || [ "$compile_finalize_rc" -eq 0 ] || original="$compile_finalize_rc"\n  python3 "$package_root/package_tools/compile_core_evidence.py" return-core --output-root "$bootstrap_root"'
    if old_core not in runner:
        raise RuntimeError("runner core-return anchor absent")
    runner = runner.replace(old_core, new_core, 1)
    old_signal = 'on_signal() { signal_status="$1"; finalize "$2"; }\n'
    new_signal = '''on_signal() {
  signal_status="$1"
  if [ -n "$compile_supervisor_pid" ]; then
    kill -s "$1" "$compile_supervisor_pid" 2>/dev/null || true
    wait "$compile_supervisor_pid"
    compile_status=$?
    compile_supervisor_pid=""
  fi
  finalize "$2"
}
'''
    if old_signal not in runner:
        raise RuntimeError("runner signal anchor absent")
    runner = runner.replace(old_signal, new_signal, 1)
    old_compile = '''set +e
timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="$tb_source" > "$compile_driver_log" 2>&1
compile_status=$?
set -e
python3 "$package_root/package_tools/compile_core_evidence.py" finalize --output-root "$bootstrap_root" --exit-code "$compile_status" || runner_fail 8 "compile-core post-actual-command finalize failed"
python3 "$package_root/package_tools/capture_actual_compiled_sources.py" --server-root "$server_root" --compile-log "$compile_driver_log" --output-root "$bootstrap_root/actual_compiled_sources" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" || printf 'CODEX_WARNING actual compiled source capture incomplete; core return preserved\\n' >&2
'''
    new_compile = '''set +e
python3 "$package_root/package_tools/compile_stage_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --grace-seconds 30 --receipt "$compile_process_receipt" --result "$compile_stage_result" -- timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR="$compile_root" VCS_EXTRA_OPTS="$tb_source" > "$compile_driver_log" 2>&1 &
compile_supervisor_pid=$!
wait "$compile_supervisor_pid"
compile_status=$?
compile_supervisor_pid=""
set -e
compile_core_finalize || runner_fail 8 "compile-core post-actual-command finalize failed"
[ "$compile_status" -eq 0 ] && rm -f "$evidence_root/PROCESS_TREE_RECEIPT.json"
'''
    if old_compile not in runner:
        raise RuntimeError("runner compile block absent")
    runner = runner.replace(old_compile, new_compile, 1)
    path.write_text(runner, encoding="utf-8", newline="\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def patch_compile_core(tree: Path) -> None:
    path = tree / "package_tools/compile_core_evidence.py"
    text = path.read_text(encoding="utf-8")
    old = 'r"(?i)(^|\\s)(fatal|failed|failure|undefined|unresolved|not found|"\n        r"no rule to make target|syntax error|xmre|undeclared identifier|"\n        r"cannot open|permission denied)(\\s|:|$)"'
    new = 'r"(?i)(^|\\s)(fatal|failed|failure|undefined|unresolved|not found|"\n        r"no rule to make target|syntax error|xmre|undeclared identifier|"\n        r"cannot open|permission denied|cannot connect to the license server)(\\s|:|$)"'
    if old not in text:
        raise RuntimeError("compile first-error regex anchor absent")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


def patch_preflight(tree: Path) -> None:
    path = tree / "package_tools/package_release_preflight.py"
    text = path.read_text(encoding="utf-8")
    anchor = '''    if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        errors.append("production launch marker count differs")
'''
    replacement = '''    if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        errors.append("production launch marker count differs")
    runner_sha = sha(root / "PREPARE_AND_RUN.sh")
    if manifest.get("runner_sha256") != runner_sha:
        errors.append("package manifest runner SHA differs")
    for path_name in (
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "contracts/server_post_sim_return_contract.json",
        "server_runner_return_resilience_contract.json",
    ):
        linked = load(root / path_name)
        if linked.get("runner_sha256") != runner_sha:
            errors.append(f"runner SHA cross-binding differs: {path_name}")
    if "compile_stage_supervision.py" not in runner or "COMPILE_PROCESS_TREE_RECEIPT.json" not in runner:
        errors.append("compile signal supervision handoff is absent")
'''
    if anchor not in text:
        raise RuntimeError("preflight runner anchor absent")
    text = text.replace(anchor, replacement, 1)
    archive_anchor = '        "evidence/PROCESS_TREE_RECEIPT.json",\n'
    archive_new = '        "evidence/PROCESS_TREE_RECEIPT.json",\n        "evidence/compile_rootcause/COMPILE_PROCESS_TREE_RECEIPT.json",\n        "evidence/compile_rootcause/COMPILE_STAGE_RESULT.json",\n'
    if archive_anchor not in text:
        raise RuntimeError("preflight archive anchor absent")
    text = text.replace(archive_anchor, archive_new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def repair_inherited_dump_union(tree: Path) -> None:
    """Replace the inherited duplicate dump target with its omitted leaf target.

    p57's catalog contains both the complete exec_slice_finish vector and the
    lane-13 leaf.  Its TB listed one WR-Data flag twice instead of the leaf,
    making the source-bound exact-union check internally inconsistent.
    """
    contract = load(tree / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    tb = tree / str(contract["execution"]["tb_source_path"])
    text = tb.read_text(encoding="utf-8")
    import re
    pattern = re.compile(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;")
    targets = [match.group(1).strip() for match in pattern.finditer(text)]
    expected = [str(row["exact_hierarchy"]) for row in contract["signals"] if isinstance(row, dict)]
    duplicates = sorted(target for target in set(targets) if targets.count(target) > 1)
    missing = sorted(set(expected) - set(targets))
    if len(targets) != len(expected) or len(duplicates) != 1 or len(missing) != 1:
        raise RuntimeError("inherited TB dump union does not have the expected one-duplicate/one-missing repair shape")
    needle = f"$dumpvars(0, {duplicates[0]});"
    position = text.rfind(needle)
    if position < 0:
        raise RuntimeError("duplicate TB dump target source text is absent")
    replacement = f"$dumpvars(0, {missing[0]});"
    tb.write_text(text[:position] + replacement + text[position + len(needle):], encoding="utf-8", newline="\n")


def update_contracts_and_manifest(tree: Path) -> None:
    runner = tree / "PREPARE_AND_RUN.sh"
    helper = tree / "package_tools/compile_stage_supervision.py"
    request_path = tree / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    entries = [row for row in request["core_entries"] if isinstance(row, dict)]
    additions = [
        {"source_root": "attempt", "source": "evidence/compile_rootcause/COMPILE_PROCESS_TREE_RECEIPT.json", "archive": "evidence/compile_rootcause/COMPILE_PROCESS_TREE_RECEIPT.json", "required": True},
        {"source_root": "attempt", "source": "evidence/compile_rootcause/COMPILE_STAGE_RESULT.json", "archive": "evidence/compile_rootcause/COMPILE_STAGE_RESULT.json", "required": True},
    ]
    existing = {row.get("archive") for row in entries}
    entries.extend(row for row in additions if row["archive"] not in existing)
    request["core_entries"] = entries
    request["package_id"] = PACKAGE
    request["claim_boundary"] = "Signal-safe native compile core plus unchanged p57 TB-VCD causal cone; no functional change or production result claim."
    write(request_path, request)

    selector_path = tree / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = PACKAGE
    vcd_contract_path = tree / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    vcd_contract = load(vcd_contract_path)
    vcd_contract["package_id"] = PACKAGE
    vcd_contract["execution"]["tb_source_sha256"] = sha(tree / str(vcd_contract["execution"]["tb_source_path"]))
    vcd_contract["execution"]["dump_targeting"]["signal_ids"] = [
        str(row["signal_id"]) for row in vcd_contract["signals"] if isinstance(row, dict)
    ]
    write(vcd_contract_path, vcd_contract)
    selector["vcd_contract_sha256"] = sha(vcd_contract_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {
        "evidence/compile_rootcause/COMPILE_PROCESS_TREE_RECEIPT.json",
        "evidence/compile_rootcause/COMPILE_STAGE_RESULT.json",
    })
    write(selector_path, selector)

    post_path = tree / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post.update({"package_id": PACKAGE, "helper_sha256": sha(tree / "package_tools/server_post_sim_return.py"), "request_sha256": sha(request_path), "runner_sha256": sha(runner)})
    write(post_path, post)
    layout_path = tree / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path); layout.update({"package_id": PACKAGE, "runner_sha256": sha(runner)}); write(layout_path, layout)
    resilience_path = tree / "server_runner_return_resilience_contract.json"
    resilience = load(resilience_path)
    resilience.update({"package_id": PACKAGE, "runner_path": f"{PACKAGE}/PREPARE_AND_RUN.sh", "runner_sha256": sha(runner)})
    resilience["package_owned_variables"] = sorted(set(resilience.get("package_owned_variables", [])) | {"compile_supervisor_pid", "compile_finalize_done", "compile_process_receipt", "compile_stage_result"})
    resilience["return_allowlist_tokens"] = sorted(set(resilience.get("return_allowlist_tokens", [])) | {"COMPILE_PROCESS_TREE_RECEIPT.json", "COMPILE_STAGE_RESULT.json", "compile_stage_supervision.py"})
    write(resilience_path, resilience)

    allowlist_path = tree / "RETURN_ALLOWLIST.json"
    allowlist = load(allowlist_path)
    root = f"{PACKAGE}_return/"
    allowlist["package_id"] = PACKAGE
    required = [root + str(row["archive"]) for row in entries if row.get("required") is True]
    required.extend([root + "RETURN_CORE_MANIFEST.json", root + "RETURN_DIGESTS.json", root + "return_core/RETURN_CORE_STATUS.json", root + "return_core/SIM_EXIT_RECEIPT.json"])
    allowlist["required"] = sorted(set(required))
    allowlist["vcd_member"] = root + "runs/c0/native_mse4_causal.vcd"
    write(allowlist_path, allowlist)

    audit = load(ANALYSIS / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json")
    write(tree / "provenance/P57_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", audit)
    write(tree / "provenance/P57_FORMAL_RETURN_ANALYSIS.json", load(ANALYSIS / "formal_return_analysis.json"))
    write(tree / "provenance/p57_to_p58_compile_signal_return_fix.json", {
        "schema": "conv-native-p57-to-p58-compile-signal-return-fix-v1",
        "predecessor": OLD,
        "package_id": PACKAGE,
        "preserved": ["config", "numeric", "workload", "golden", "functional RTL", "TB VCD causal catalog", "p57 global execution probes"],
        "changed": ["runner", "compile core first-error recognizer", "compile process supervision helper", "return allowlist", "cross-member runner identity"],
        "reason": "The p57 license failure was followed by INT before its foreground compile command returned; the old trap bypassed compile-core finalization.",
        "server_actions_performed": [],
    })

    manifest_path = tree / "package_manifest.json"
    manifest = load(manifest_path)
    manifest.update({
        "schema": "conv-native-four-lane-p58-compile-interrupt-return-v1",
        "package_identity": PACKAGE,
        "install_name": PACKAGE,
        "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN",
        "activation_epoch": EPOCH,
        "source_package": OLD,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "previous_version_progress": "p56 narrowed the global fetch-finish boundary; p57 formed the native production compile command but stopped at a server license-connect failure followed by INT before target entry.",
        "current_version_purpose": "Re-run the exact p57 init_exec_inst_length/exec_fetch_cnt causal cone with a signal-safe native compile core that always preserves the actual log, first error, exit provenance and reaped process receipt.",
        "runner_sha256": sha(runner),
        "mode_selector_sha256": sha(selector_path),
        "vcd_contract_sha256": sha(tree / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"),
        "package_build_failure_rule_audit": "provenance/P57_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        "formal_return_analysis": "provenance/P57_FORMAL_RETURN_ANALYSIS.json",
        "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True},
        "server_actions_performed": [],
        "claim_boundary": "Local package admission only. No license/environment remediation, server run, functional change, target execution, root closure, natural terminal, Formal-D, E3, E4 or E5 claim.",
    })

    files = {
        item.relative_to(tree).as_posix(): identity(item)
        for item in sorted(entry for entry in tree.rglob("*") if entry.is_file())
        if item.name != "package_manifest.json"
    }
    if "package_tools/compile_stage_supervision.py" not in files or sha(helper) != files["package_tools/compile_stage_supervision.py"]["sha256"]:
        raise RuntimeError("compile supervision helper identity not materialized")
    manifest["files"] = files
    write(manifest_path, manifest)


def update_pointer_and_readme(tree: Path) -> None:
    pointer = load(tree / "TEST_PACKAGE_MANIFEST.json")
    pointer.update({"schema": "conv-native-four-lane-p58-compile-interrupt-pointer-v1", "package_identity": PACKAGE, "family": FAMILY, "activation_epoch": EPOCH, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "status": "PACKAGE_READY_NOT_RUN", "server_actions_performed": []})
    write(tree / "TEST_PACKAGE_MANIFEST.json", pointer)
    readme = f'''# {PACKAGE}

Previous progress: p56 narrowed the hold to premature global fetch finish; p57 formed the exact global-exec probe but VCS could not connect to its license server and the run was interrupted before target entry.

Current purpose: retain the p57 `init_exec_inst_length` / `exec_fetch_cnt` TB-VCD causal cone while making a compile-stage HUP/INT/TERM produce an actual bounded log, first-error core, and TERM-wait-KILL-reap receipt.  Config, numeric, workload, golden input, functional RTL and diagnostic signals are frozen.

Run only after separate authorization:

    bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01

No server action was performed during this local build.
'''
    (tree / "README.md").write_text(readme, encoding="utf-8", newline="\n")


def release_contract(zip_sha: str) -> dict[str, Any]:
    claim = "Local p58 signal-safe compile-return package admission only; no production or DUT claim."
    receipt = GATES / "package_release_receipt.json"
    failure = GATES / "precompile_failure_core.json"
    write(receipt, {"schema": "conv-native-p58-release-receipt-v1", "package_id": PACKAGE, "status": "PACKAGE_READY_NOT_RUN", "pass": True, "package": {"sha256": zip_sha}, "claim_boundary": claim})
    write(failure, {"schema": "server-precompile-preflight-failure-core-v1", "package_id": PACKAGE, "final_zip_sha256": zip_sha, "runner_member_sha256": sha(TREE / "PREPARE_AND_RUN.sh"), "preflight": {"exit_code": 19, "stdout": "package claim boundary differs\n", "stderr": ""}, "compile_started": False, "simulation_started": False, "core_return": {"published": True, "classification": "COMPILE_NOT_STARTED", "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]}, "claim_boundary": "Precompile failure visibility only; no compile or simulation claim."})
    return {
        "schema": "server-package-release-admission-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "staging_root": TREE.relative_to(ROOT).as_posix(), "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": zip_sha}, "zip_root_member": PACKAGE, "runner_member": "PREPARE_AND_RUN.sh"},
        "manifest": {"member": "TEST_PACKAGE_MANIFEST.json", "package_id_pointer": "/package_identity", "status_pointer": "/status", "ready_status": "PACKAGE_READY_NOT_RUN", "nonfinal_status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"},
        "runtime_preflight": {"runtime_member": "package_tools/package_release_preflight.py", "command_template": ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"], "expected_exit": 0, "nonfinal_rejection_marker": "package claim boundary differs", "timeout_seconds": 60, "non_mutating": True},
        "release_receipt": {"path": receipt.relative_to(ROOT).as_posix(), "sha256": sha(receipt), "package_id_pointer": "/package_id", "status_pointer": "/status", "pass_pointer": "/pass", "final_zip_sha256_pointer": "/package/sha256", "claim_boundary_pointer": "/claim_boundary", "expected_claim_boundary": claim},
        "precompile_failure_core": {"path": failure.relative_to(ROOT).as_posix(), "sha256": sha(failure)},
        "python_schema_runtime": {"schema_validation_enabled": True, "schema_dependency": "jsonschema", "missing_dependency_disposition": "FAIL_CLOSED", "skip_allowed": False, "exact_set_compile": True, "compile_staging_and_clean_exact_zip": True, "package_python_source_suffixes": [".py"], "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY"},
        "build_receipt_semantics": {"aggregate_mode": "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH", "positive_assertions": [{"fact_id": "deterministic_exact_zip", "observed": True, "required": True}, {"fact_id": "frozen_payload_equal", "observed": True, "required": True}], "negative_observations": [{"fact_id": "functional_rtl_modified", "observed": False, "required": False}, {"fact_id": "server_action", "observed": False, "required": False}], "informational_facts": [{"fact_id": "activation_epoch", "value": EPOCH}]},
        "claim_boundary": "Local exact staging/ZIP admission only.",
    }


def main() -> None:
    if not SOURCE_ZIP.is_file():
        raise RuntimeError(f"exact source ZIP absent: {SOURCE_ZIP}")
    if not (ANALYSIS / "formal_return_analysis.json").is_file():
        raise RuntimeError("p57 formal return analysis is absent")
    if OUT.exists():
        allowed_existing = {"gates"}
        actual_existing = {item.name for item in OUT.iterdir()}
        if actual_existing != allowed_existing:
            raise RuntimeError(f"fresh output contains non-gate artifacts; refuse to overwrite: {OUT}")
    else:
        OUT.mkdir(parents=True)
    BUILD.mkdir(parents=True)
    TREE.mkdir()
    with zipfile.ZipFile(SOURCE_ZIP) as source:
        for info in source.infolist():
            member = PurePosixPath(info.filename)
            if not member.parts or member.parts[0] != OLD or member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"source ZIP member is not beneath the expected source root: {info.filename}")
            relative = PurePosixPath(*member.parts[1:])
            if not relative.parts:
                continue
            destination = TREE / Path(*relative.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read(info))
            mode = (info.external_attr >> 16) & 0o777
            if mode:
                destination.chmod(mode)
    replace_identity(TREE)
    (TREE / "package_tools/compile_stage_supervision.py").write_text(COMPILE_HELPER, encoding="utf-8", newline="\n")
    (TREE / "package_tools/compile_stage_supervision.py").chmod(0o755)
    patch_runner(TREE)
    patch_compile_core(TREE)
    patch_preflight(TREE)
    repair_inherited_dump_union(TREE)
    update_pointer_and_readme(TREE)
    update_contracts_and_manifest(TREE)
    deterministic_zip(TREE, ZIP)
    deterministic_zip(TREE, REPEAT)
    if sha(ZIP) != sha(REPEAT):
        raise RuntimeError("deterministic repeat ZIP identity differs")
    contract = release_contract(sha(ZIP))
    write(GATES / "package_release_admission_contract.json", contract)
    write(OUT / "build_receipt.json", {
        "schema": "conv-native-p58-local-build-v1", "package_id": PACKAGE, "source_zip": {"path": str(SOURCE_ZIP.relative_to(ROOT)), "sha256": sha(SOURCE_ZIP)}, "final_zip": {"path": str(ZIP.relative_to(ROOT)), "size_bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}, "repeat_zip_sha256": sha(REPEAT), "changed_surfaces": ["package_identity", "runner", "return_core_contract", "return_collector"], "frozen_surfaces": ["config", "numeric", "workload", "golden", "functional_rtl", "TB_VCD causal cone"], "server_actions_performed": []})


if __name__ == "__main__":
    main()
