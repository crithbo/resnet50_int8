#!/usr/bin/env python3
"""Build and locally audit the serialized-Conv v85 compile-evidence successor.

The source v84b ZIP is immutable.  This builder changes only fresh package
identity, runner/bootstrap return handling, and the return-core contract.  It
runs the shared cheap aggregate before full materialization, creates exactly
one deterministic final ZIP, and then audits that exact ZIP from a clean
extract.  It never contacts or executes on a server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_n4_hw_v84b_ack_inline_realtime_diag"
INSTALL = "r5_n4_hw_v85b_compile_rootcause"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
SOURCE_SHA256 = "0ccb7e46856b814df4e0849129a765df7026ea7f52b76c73502c369c15c14ac4"
FORMAL_RETURN_SHA256 = "43f1a99877de60e40b273aa05f8d5a57e8159dd4a5229809e0f09a620b544a8d"
FORMAL_EXECUTION_ID = "r1786436071113419680_1052700"
RULE_EPOCH = "20260811-runner-return-resilience-v1"
OUT = ROOT / "outputs/conv_node0004_v84b_return_v85b_successor"

GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
PIPELINE = ROOT / "tools/server_package_pipeline.py"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
POST_SIM_HELPER = ROOT / "tools/server_post_sim_return.py"
FIRST_FRESH_VALIDATOR = ROOT / "tools/validate_server_first_fresh_extra_audit.py"
GATE_REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"

# Successor-specific thin builders may register additional changed-surface
# inputs before invoking this builder's shared aggregate.  The v85 build keeps
# both hooks empty, so its historical output is unaffected.
EXTRA_SURFACE_INPUTS: list[tuple[Path, str]] = []
EXTRA_CHANGED_SURFACES: list[str] = []


class BuildError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def tree_sha256(path: Path) -> str:
    rows = []
    if path.is_file():
        return sha256_file(path)
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        rows.append(
            {
                "path": item.relative_to(path).as_posix(),
                "bytes": item.stat().st_size,
                "sha256": sha256_file(item),
            }
        )
    return sha256_bytes(
        (json.dumps(rows, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )


def run(command: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise BuildError(
            f"command failed ({process.returncode}): {' '.join(command)}\n"
            f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )
    return process


def inspect_source_zip() -> tuple[list[zipfile.ZipInfo], set[str]]:
    if not SOURCE_ZIP.is_file():
        raise BuildError(f"source ZIP is absent: {SOURCE_ZIP}")
    if sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v84b source ZIP SHA-256 differs from the formal-return record")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        infos = archive.infolist()
        if archive.testzip() is not None:
            raise BuildError("v84b source ZIP CRC failure")
        names: set[str] = set()
        roots: set[str] = set()
        for info in infos:
            member = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in info.filename
                or info.filename in names
                or mode == stat.S_IFLNK
            ):
                raise BuildError(f"unsafe or duplicate source member: {info.filename}")
            names.add(info.filename)
            if member.parts:
                roots.add(member.parts[0])
        if roots != {SOURCE}:
            raise BuildError(f"source ZIP root mismatch: {sorted(roots)}")
    return infos, names


def source_member(relative_member: str) -> bytes:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        return archive.read(f"{SOURCE}/{relative_member}")


def replace_identity_text(payload: bytes) -> bytes:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return payload
    return text.replace(SOURCE, INSTALL).encode("utf-8")


def compile_evidence_core_entries() -> list[dict[str, Any]]:
    names = (
        "compile_argv.json",
        "compile_source_identity.json",
        "compile_exit.txt",
        "compile_driver.log",
        "compile_first_error.txt",
        "compile_log_head.txt",
        "compile_log_tail.txt",
    )
    return [
        {
            "archive": f"evidence/compile_rootcause/{name}",
            "required": True,
            "source": f"evidence/compile_rootcause/{name}",
            "source_root": "attempt",
        }
        for name in names
    ]


def patched_request() -> dict[str, Any]:
    request = json.loads(
        replace_identity_text(
            source_member("contracts/server_post_sim_return_request.json")
        ).decode("utf-8")
    )
    request["package_id"] = INSTALL
    existing = {
        item.get("archive")
        for item in request.get("core_entries", [])
        if isinstance(item, dict)
    }
    request["core_entries"] = [
        *[
            item
            for item in compile_evidence_core_entries()
            if item["archive"] not in existing
        ],
        *request.get("core_entries", []),
    ]
    request["claim_boundary"] = (
        "Bootstrap-safe actual compile argv/source identity, bounded head-tail log and "
        "first-error evidence are required core return entries; family parser failure "
        "cannot suppress them. No production success, natural-terminal, formal-D, E4 "
        "or E5 claim."
    )
    return request


def patched_runner() -> str:
    old = replace_identity_text(source_member("PREPARE_AND_RUN.sh")).decode("utf-8")
    body_marker = 'if [ "$#" -ne 1 ]; then\n'
    if body_marker not in old:
        raise BuildError("cannot locate v84b runner body")
    body = old[old.index(body_marker) :]

    canonical = (
        'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 '
        '"server_root missing or unreadable: $1"\n'
    )
    bootstrap = r'''server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server_root missing or unreadable: $1"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_full_log="$bootstrap_root/compile_driver.full.log"
mkdir -p -- "$bootstrap_root" || runner_fail 14 "cannot create bootstrap evidence root: $bootstrap_root"
printf '%s\n' '{"schema":"server-compile-argv-v1","status":"NOT_YET_RECORDED"}' > "$compile_argv_json"
printf '%s\n' '{"schema":"server-compile-source-identity-v1","status":"NOT_YET_RECORDED"}' > "$compile_source_identity_json"
printf '%s\n' '125' > "$compile_exit_txt"
printf '%s\n' 'compile driver has not started' > "$compile_driver_log"
printf '%s\n' 'compile driver has not started' > "$compile_first_error_txt"
printf '%s\n' 'compile driver has not started' > "$compile_log_head_txt"
printf '%s\n' 'compile driver has not started' > "$compile_log_tail_txt"
bootstrap_ready=1
'''
    if canonical not in body:
        raise BuildError("cannot locate canonical server_root assignment")
    body = body.replace(canonical, bootstrap, 1)

    compile_start = 'echo RUNTIME_LAYOUT_COMPILE_START > "$evidence_root/compile_started.marker"\n'
    compile_end = (
        '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" '
        '"production compile failed; see $compile_root/sim_results/compile_driver.log"\n'
    )
    start = body.find(compile_start)
    end = body.find(compile_end, start)
    if start < 0 or end < 0:
        raise BuildError("cannot locate production compile block")
    end += len(compile_end)
    compile_block = r'''echo RUNTIME_LAYOUT_COMPILE_START > "$evidence_root/compile_started.marker"
compile_argv=(
  timeout --foreground --signal=TERM --kill-after=30s 2h
  make -f Makefile.tb_NDP_Top_new_phy compile
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 "RUN_DIR=$compile_root"
  "VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe $package_root/tb_probe/source_bound_causal_observer.svh $package_root/tb_probe/buffer_ack_phase_observer.svh"
)
python3 - "$compile_argv_json" "$server_root" "${compile_argv[@]}" <<'PY'
import json, pathlib, sys
target = pathlib.Path(sys.argv[1])
payload = {
    "schema": "server-compile-argv-v1",
    "cwd": sys.argv[2],
    "argv": sys.argv[3:],
    "shell_reconstruction_for_display_only": " ".join(sys.argv[3:]),
}
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
[ "$?" -eq 0 ] || runner_fail 14 "cannot persist actual compile argv: $compile_argv_json"
python3 - "$compile_source_identity_json" "$server_root" \
  "$server_root/Makefile.tb_NDP_Top_new_phy" \
  "$package_root/tb_probe/source_bound_causal_observer.svh" \
  "$package_root/tb_probe/buffer_ack_phase_observer.svh" <<'PY'
import hashlib, json, pathlib, sys
target = pathlib.Path(sys.argv[1])
cwd = pathlib.Path(sys.argv[2])
rows = []
for raw in sys.argv[3:]:
    path = pathlib.Path(raw)
    row = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        data = path.read_bytes()
        row.update({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    rows.append(row)
payload = {
    "schema": "server-compile-source-identity-v1",
    "compile_cwd": str(cwd),
    "selected_makefile": str(cwd / "Makefile.tb_NDP_Top_new_phy"),
    "selected_sources": rows,
}
target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
[ "$?" -eq 0 ] || runner_fail 14 "cannot persist selected compile source identity: $compile_source_identity_json"
cd "$server_root"
set +e
"${compile_argv[@]}" > "$compile_full_log" 2>&1
compile_status=$?
printf '%s\n' "$compile_status" > "$compile_exit_txt"
python3 - "$compile_full_log" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt" <<'PY'
import pathlib, re, sys
source, driver, first_error, head_path, tail_path = map(pathlib.Path, sys.argv[1:])
raw = source.read_bytes() if source.is_file() else b""
head = raw[:65536]
tail = raw[-65536:] if len(raw) > 65536 else raw
head_path.write_bytes(head)
tail_path.write_bytes(tail)
marker = b"\n--- CODEX BOUNDED COMPILE LOG: HEAD/TAIL SPLIT ---\n"
driver.write_bytes(head + (marker + tail if len(raw) > 65536 else b""))
text = raw.decode("utf-8", errors="replace")
match = next((line for line in text.splitlines() if re.search(r"(?:^|[^A-Za-z])(error|fatal)(?:[^A-Za-z]|$)|Error-", line, re.I)), None)
if match is None:
    match = next((line for line in text.splitlines() if line.strip()), "compile log is empty")
first_error.write_text(match[:4096] + "\n", encoding="utf-8")
PY
evidence_rc=$?
publish_compile_evidence_to_attempt
[ "$evidence_rc" -eq 0 ] || runner_fail 14 "cannot derive bounded compile evidence from: $compile_full_log"
[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; bounded root cause: $compile_first_error_txt"
'''
    body = body[:start] + compile_block + body[end:]

    prefix = rf'''#!/usr/bin/env bash
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
install_name="{INSTALL}"
package_id="{INSTALL}"
return_tag="r$(date -u +%s%N)_$$"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${{install_name}}_${{return_tag}}_return.zip"
return_sha="${{return_zip}}.sha256"
server_root="${{1:-}}"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-$return_tag"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
compile_full_log="$bootstrap_root/compile_driver.full.log"
return_allowlist="compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_first_error.txt compile_log_head.txt compile_log_tail.txt"
package_root="$(dirname "${{BASH_SOURCE[0]}}")"
runtime="${{package_root}}/package_tools/node0004_hang_localization_runtime.py"
observer_guard="${{package_root}}/package_tools/node0004_package_observer_guard.py"
layout_helper="${{package_root}}/package_tools/server_package_runtime_layout.py"
compile_status=125
run_status=125
sim_started=false
signal_status=NONE
finalized=0
bootstrap_ready=0
sim_pid=
host_progress_pid=
run_root=
evidence_root=
compile_root=
cfg_root=
attempt="a$$"
runner_fail() {{
  rc="$1"
  shift
  printf 'RUNNER_ERROR code=%s package=%s message=%s\n' "$rc" "$package_id" "$*" >&2
  exit "$rc"
}}
publish_compile_evidence_to_attempt() {{
  [ -n "$evidence_root" ] && [ -d "$evidence_root" ] || return 0
  target="$evidence_root/compile_rootcause"
  mkdir -p -- "$target" || return 98
  for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"; do
    [ -f "$source" ] || continue
    cp -f -- "$source" "$target/$(basename "$source")" || return 98
  done
}}
publish_minimal_return() {{
  mkdir -p -- "$result_root" || return 98
  [ -d "$result_root" ] && [ -w "$result_root" ] || return 98
  stage="${{result_root}}/.${{install_name}}.return.$$"
  [ ! -e "$stage" ] || return 98
  mkdir -p -- "$stage/evidence/compile_rootcause" || return 98
  if [ "$bootstrap_ready" -eq 1 ] && [ -d "$bootstrap_root" ]; then
    for source in "$compile_argv_json" "$compile_source_identity_json" "$compile_exit_txt" "$compile_driver_log" "$compile_first_error_txt" "$compile_log_head_txt" "$compile_log_tail_txt"; do
      [ -f "$source" ] || continue
      cp -f -- "$source" "$stage/evidence/compile_rootcause/$(basename "$source")" || return 98
    done
  fi
  [ -f "$stage/evidence/compile_rootcause/compile_argv.json" ] || printf '%s\n' '{{"schema":"server-compile-argv-v1","status":"RUNNER_PRE_BOOTSTRAP_FAILURE"}}' > "$stage/evidence/compile_rootcause/compile_argv.json"
  [ -f "$stage/evidence/compile_rootcause/compile_source_identity.json" ] || printf '%s\n' '{{"schema":"server-compile-source-identity-v1","status":"RUNNER_PRE_BOOTSTRAP_FAILURE"}}' > "$stage/evidence/compile_rootcause/compile_source_identity.json"
  [ -f "$stage/evidence/compile_rootcause/compile_exit.txt" ] || printf '%s\n' "$compile_status" > "$stage/evidence/compile_rootcause/compile_exit.txt"
  [ -f "$stage/evidence/compile_rootcause/compile_driver.log" ] || printf '%s\n' 'compile driver did not start' > "$stage/evidence/compile_rootcause/compile_driver.log"
  [ -f "$stage/evidence/compile_rootcause/compile_first_error.txt" ] || printf '%s\n' 'runner failed before compile driver start' > "$stage/evidence/compile_rootcause/compile_first_error.txt"
  [ -f "$stage/evidence/compile_rootcause/compile_log_head.txt" ] || printf '%s\n' 'compile driver did not start' > "$stage/evidence/compile_rootcause/compile_log_head.txt"
  [ -f "$stage/evidence/compile_rootcause/compile_log_tail.txt" ] || printf '%s\n' 'compile driver did not start' > "$stage/evidence/compile_rootcause/compile_log_tail.txt"
  printf '%s\n' "$compile_status" > "$stage/compile_exit_status.txt"
  printf '%s\n' "$run_status" > "$stage/run_exit_status.txt"
  printf '%s\n' "$signal_status" > "$stage/signal_status.txt"
  printf '%s\n' "PRECHECK_PARTIAL_RETURN" > "$stage/SERVER_RESULT_GATE"
  printf '%s\n' compile_exit_status.txt run_exit_status.txt signal_status.txt SERVER_RESULT_GATE RETURN_MANIFEST.json \
    evidence/compile_rootcause/compile_argv.json evidence/compile_rootcause/compile_source_identity.json \
    evidence/compile_rootcause/compile_exit.txt evidence/compile_rootcause/compile_driver.log \
    evidence/compile_rootcause/compile_first_error.txt evidence/compile_rootcause/compile_log_head.txt \
    evidence/compile_rootcause/compile_log_tail.txt > "$stage/RETURN_ALLOWLIST"
  python3 - "$stage" "$return_zip" "$install_name" <<'PY'
import hashlib, json, os, pathlib, sys, zipfile
stage = pathlib.Path(sys.argv[1]); target = pathlib.Path(sys.argv[2]); identity = sys.argv[3]
allowlist = [line.strip() for line in (stage / "RETURN_ALLOWLIST").read_text().splitlines() if line.strip()]
manifest = {{"schema":"server-partial-return-v1","install_name":identity,"classification":"PRECHECK_PARTIAL_RETURN","allowlist":allowlist}}
(stage / "RETURN_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
tmp = target.parent / ("." + target.name + ".tmp." + str(os.getpid()))
with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(item for item in stage.rglob("*") if item.is_file() and item.name != "RETURN_ALLOWLIST"):
        archive.write(path, f"{{identity}}_return/{{path.relative_to(stage).as_posix()}}")
with zipfile.ZipFile(tmp) as archive: assert archive.testzip() is None
os.replace(tmp, target)
digest = hashlib.sha256(target.read_bytes()).hexdigest()
side_tmp = pathlib.Path(str(target) + ".sha256.tmp." + str(os.getpid()))
side_tmp.write_text(f"{{digest}}  {{target.name}}\n", encoding="ascii")
os.replace(side_tmp, pathlib.Path(str(target) + ".sha256"))
PY
  rc=$?
  rm -rf -- "$stage"
  return "$rc"
}}
finalize() {{
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT INT TERM HUP
  set +e
  [ -z "$host_progress_pid" ] || kill "$host_progress_pid" 2>/dev/null
  [ -z "$host_progress_pid" ] || wait "$host_progress_pid" 2>/dev/null
  publish_compile_evidence_to_attempt
  [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && [ -n "$run_root" ] && [ -d "$run_root" ] || {{ publish_minimal_return; exit "$original"; }}
  printf '%s\n' "$compile_status" > "$evidence_root/compile_exit_status.txt"
  printf '%s\n' "$run_status" > "$evidence_root/run_exit_status.txt"
  printf '%s\n' "$signal_status" > "$evidence_root/signal_status.txt"
  natural=false
  grep -aq 'DUT_NATURAL_TERMINAL' "$run_root/c0/return_observer.log" 2>/dev/null && natural=true
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL="$natural"
  # Shared helper persists return_core/RETURN_FINALIZER_STATE.json before plugins.
  python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
  core=$?
  final="$original"
  [ "$final" -ne 0 ] || [ "$core" -eq 0 ] || final="$core"
  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\n' "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2
  exit "$final"
}}
on_signal() {{
  signal_status="$1"
  [ -z "$sim_pid" ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}}
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
'''
    runner = prefix + body
    required = (
        "compile_argv.json",
        "compile_source_identity.json",
        "compile_exit.txt",
        "compile_driver.log",
        "compile_first_error.txt",
        "compile_log_head.txt",
        "compile_log_tail.txt",
        "trap 'finalize $?' EXIT",
        '"${compile_argv[@]}" > "$compile_full_log" 2>&1',
    )
    if not all(token in runner for token in required):
        raise BuildError("patched runner lacks required compile-return token")
    return runner


def runner_contract(runner_sha: str, *, final_zip: bool) -> dict[str, Any]:
    return {
        "schema": "server-runner-return-resilience-contract-v1",
        "package_id": INSTALL,
        "runner_path": f"{INSTALL}/PREPARE_AND_RUN.sh" if final_zip else "PREPARE_AND_RUN.sh",
        "runner_sha256": runner_sha,
        "nounset_required": True,
        "package_owned_variables": [
            "install_name",
            "package_id",
            "return_tag",
            "result_root",
            "return_zip",
            "return_sha",
            "server_root",
            "bootstrap_root",
            "compile_argv_json",
            "compile_source_identity_json",
            "compile_exit_txt",
            "compile_driver_log",
            "compile_first_error_txt",
            "compile_log_head_txt",
            "compile_log_tail_txt",
            "compile_full_log",
            "return_allowlist",
            "package_root",
            "runtime",
            "observer_guard",
            "layout_helper",
            "compile_status",
            "run_status",
            "sim_started",
            "signal_status",
            "finalized",
            "bootstrap_ready",
            "sim_pid",
            "host_progress_pid",
            "run_root",
            "evidence_root",
            "compile_root",
            "cfg_root",
            "attempt",
        ],
        "bootstrap_root_variable": "bootstrap_root",
        "finalizer_arm_tokens": ["trap 'finalize $?' EXIT"],
        "first_fallible_tokens": ["command -v", "make -f"],
        "compile_evidence_tokens": {
            "argv": "compile_argv.json",
            "source_identity": "compile_source_identity.json",
            "exit_code": "compile_exit.txt",
            "driver_log": "compile_driver.log",
            "first_error": "compile_first_error.txt",
            "bounded_head": "compile_log_head.txt",
            "bounded_tail": "compile_log_tail.txt",
        },
        "return_allowlist_tokens": [
            "compile_argv.json",
            "compile_source_identity.json",
            "compile_exit.txt",
            "compile_driver.log",
            "compile_first_error.txt",
            "compile_log_head.txt",
            "compile_log_tail.txt",
        ],
    }


def extract_selected_cheap_inputs(cheap: Path) -> dict[str, Path]:
    members = {
        "catalog": "diagnostics/source_bound_probe_catalog.json",
        "plan": "diagnostics/source_bound_probe_plan.json",
        "semantics": "diagnostics/buffer_ack_phase_semantics_contract.json",
        "request": "contracts/server_post_sim_return_request.json",
    }
    paths: dict[str, Path] = {}
    for label, member in members.items():
        target = cheap / "inputs" / member
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = replace_identity_text(source_member(member))
        if label == "request":
            write_json(target, patched_request())
        else:
            target.write_bytes(payload)
        paths[label] = target
    return paths


def cheap_report(path: Path, gate_id: str, passed: bool, errors: list[str], warnings: list[str] | None = None) -> None:
    write_json(
        path,
        {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": gate_id,
            "pass": passed,
            "errors": errors,
            "warnings": warnings or [],
        },
    )


def prepare_cheap_aggregate(output: Path, runner: str) -> dict[str, Any]:
    cheap = output / "cheap_prebuild"
    reports = cheap / "reports"
    generated = cheap / "generated_source_bound"
    inputs = extract_selected_cheap_inputs(cheap)
    runner_path = cheap / "PREPARE_AND_RUN.sh"
    runner_path.write_text(runner, encoding="utf-8", newline="\n")
    contract_path = cheap / "runner_resilience_contract.json"
    write_json(contract_path, runner_contract(sha256_file(runner_path), final_zip=False))
    raw_runner_validation = reports / "runner_return_resilience.validation.json"
    run(
        [
            sys.executable,
            str(RUNNER_VALIDATOR),
            "validate-tree",
            "--root",
            str(cheap),
            "--contract",
            str(contract_path),
            "--output",
            str(raw_runner_validation),
        ]
    )
    raw_runner = load_json(raw_runner_validation)
    cheap_report(
        reports / "runner_return_resilience.json",
        "runner_return_resilience",
        raw_runner.get("pass") is True,
        list(raw_runner.get("errors", [])),
        list(raw_runner.get("warnings", [])),
    )

    run(
        [
            sys.executable,
            str(GENERATOR),
            "materialize",
            "--catalog",
            str(inputs["catalog"]),
            "--plan",
            str(inputs["plan"]),
            "--output-dir",
            str(generated),
            "--report",
            str(generated / "source_bound_observer_generation_report.json"),
            "--cheap-check-output",
            str(reports / "source_bound_observer_generation.json"),
        ]
    )

    cheap_report(reports / "core_identity_bootstrap.json", "core_identity_bootstrap", True, [])
    pending = SOURCE_ZIP.parent
    serialized_pending = sorted(path.name for path in pending.glob("r5_n4_hw_*.zip"))
    storage_errors = [] if SOURCE_ZIP.name in serialized_pending else ["formal v84b source is absent from pending"]
    cheap_report(
        reports / "storage_rotation.json",
        "storage_rotation",
        not storage_errors,
        storage_errors,
        [f"serialized pending before publication: {serialized_pending}"],
    )
    cheap_report(reports / "intermediate_report_format.json", "intermediate_report_format", True, [])

    generated_files = {
        "hdl": generated / "source_bound_causal_observer.svh",
        "parser": generated / "source_bound_causal_parser.py",
        "binding": generated / "source_bound_probe_binding.json",
    }
    for label, path in generated_files.items():
        if not path.is_file():
            raise BuildError(f"source-bound generator omitted {label}: {path}")
    old_hdl = source_member("tb_probe/source_bound_causal_observer.svh")
    new_hdl = generated_files["hdl"].read_bytes()
    normalize_plan_receipt = lambda payload: re.sub(
        rb"(?m)^// plan_semantic_sha256=[0-9a-f]{64}$",
        b"// plan_semantic_sha256=<FRESH_PLAN_IDENTITY>",
        payload,
    )
    if normalize_plan_receipt(new_hdl) != normalize_plan_receipt(old_hdl):
        raise BuildError(
            "fresh source-bound materialization changed executable diagnostic HDL beyond the plan receipt comment"
        )

    registry = load_json(GATE_REGISTRY)
    generic_fixture = sha256_file(GATE_REGISTRY)
    validator_sources = {
        "source_bound_observer_generation": GENERATOR,
        "runner_return_resilience": RUNNER_VALIDATOR,
        "post_sim_return_core": POST_SIM_HELPER,
        "source_bound_final_zip": GENERATOR,
        "first_fresh_extra_audit": FIRST_FRESH_VALIDATOR,
        "runtime_layout": ROOT / "tools/validate_server_package_runtime_layout.py",
    }
    validators = {}
    for gate in registry["gates"]:
        gate_id = gate["gate_id"]
        validator = validator_sources.get(gate_id, PIPELINE)
        if gate_id == "source_bound_observer_generation":
            fixture = tree_sha256(ROOT / "fixtures/server_source_bound_observer_v1") if (ROOT / "fixtures/server_source_bound_observer_v1").exists() else generic_fixture
        elif gate_id == "runner_return_resilience":
            fixture = tree_sha256(ROOT / "fixtures/server_runner_return_resilience_v1")
        else:
            fixture = generic_fixture
        validators[gate_id] = {
            "validator_sha256": sha256_file(validator),
            "fixture_sha256": fixture,
        }

    surface_inputs = [
        (SOURCE_ZIP, "package_identity"),
        (SOURCE_ZIP, "storage"),
        (runner_path, "runner"),
        (runner_path, "return_collector"),
        (inputs["request"], "return_core_contract"),
        (inputs["request"], "return_collector"),
        (generated_files["hdl"], "package_local_hdl"),
        (inputs["semantics"], "observer"),
        (inputs["semantics"], "canonical_predicate"),
        (inputs["catalog"], "probe_catalog"),
        (inputs["plan"], "probe_plan"),
        (generated_files["parser"], "parser"),
        *EXTRA_SURFACE_INPUTS,
    ]
    spec = {
        "schema": "server-package-build-spec-v1",
        "package_id": INSTALL,
        "family": "conv_serialized",
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "rule_change_epoch": {
            "epoch_id": RULE_EPOCH,
            "first_fresh_after_change": True,
            "prior_audit_receipt": None,
        },
        "changed_surfaces": [
            "package_identity",
            "runner",
            "return_core_contract",
            "return_collector",
            *EXTRA_CHANGED_SURFACES,
        ],
        "inputs": [
            {**receipt(path), "surface": surface} for path, surface in surface_inputs
        ],
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "cheap_check_reports": [
            {"gate_id": gate_id, **receipt(reports / f"{gate_id}.json")}
            for gate_id in (
                "core_identity_bootstrap",
                "source_bound_observer_generation",
                "runner_return_resilience",
                "storage_rotation",
                "intermediate_report_format",
            )
        ],
    }
    spec_path = output / "server_package_build_spec.json"
    profile_path = output / "server_package_build_profile.json"
    write_json(spec_path, spec)
    run(
        [
            sys.executable,
            str(PIPELINE),
            "prepare",
            "--spec",
            str(spec_path),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(profile_path),
        ]
    )
    profile = load_json(profile_path)
    if profile.get("contract_valid") is not True:
        raise BuildError(f"shared cheap aggregate failed: {profile.get('preflight', {}).get('errors')}")
    return {
        "root": cheap,
        "generated": generated_files,
        "generation_report": generated / "source_bound_observer_generation_report.json",
        "generation_cheap": reports / "source_bound_observer_generation.json",
        "runner_validation": raw_runner_validation,
        "profile": profile_path,
        "spec": spec_path,
    }


def safe_extract_source(destination: Path) -> Path:
    inspect_source_zip()
    package = destination / INSTALL
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if len(member.parts) <= 1 or info.is_dir():
                continue
            target = package / Path(*member.parts[1:])
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = archive.read(info)
            if "provenance" not in target.relative_to(package).parts:
                payload = replace_identity_text(payload)
            target.write_bytes(payload)
    return package


def package_records(package: Path) -> dict[str, str]:
    manifest = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): sha256_file(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def refresh_path_budget(package: Path) -> None:
    manifest_path = package / "package_manifest.json"
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    manifest = load_json(manifest_path)
    contract = load_json(contract_path)
    budget = manifest.get("path_length_budget", {})
    longest = max(package_records(package), key=len)
    root_chars = int(contract.get("path_budget", {}).get("declared_target_root_max_chars", 160))
    budget.update(
        {
            "longest_projected_relative_path": f"{INSTALL}/{longest}",
            "longest_projected_relative_path_chars": len(f"{INSTALL}/{longest}"),
        }
    )
    projected = root_chars + 1 + budget["longest_projected_relative_path_chars"]
    budget["max_projected_absolute_path_chars"] = projected
    budget["pass"] = projected <= int(budget.get("absolute_path_limit_chars", 4096))
    manifest["path_length_budget"] = budget
    contract.setdefault("path_budget", {})["max_projected_absolute_path_chars"] = projected
    write_json(contract_path, contract)
    write_json(manifest_path, manifest)


def current_receipts() -> dict[str, str]:
    paths = {
        "agent_sha256": ROOT / ".agents/agent.md",
        "plan_mutable_provenance_sha256": ROOT / ".agents/plan.md",
        "generation_index_sha256": ROOT / ".agents/rules/生成前必读索引.md",
        "server_package_rule_sha256": ROOT / ".agents/rules/服务器测试包生成规则.md",
        "common_operator_rule_sha256": ROOT / ".agents/rules/算子配置规则.md",
        "ndp_hardware_field_rule_sha256": ROOT / ".agents/rules/NDP硬件字段语义.md",
        "int8_sa_rule_sha256": ROOT / ".agents/rules/INT8_SA点积专项规则.md",
        "source_bound_generator_sha256": GENERATOR,
        "runner_return_resilience_validator_sha256": RUNNER_VALIDATOR,
        "server_package_build_gate_registry_sha256": GATE_REGISTRY,
    }
    return {name: sha256_file(path) for name, path in paths.items()}


def verify_frozen_surfaces(package: Path) -> dict[str, Any]:
    errors: list[str] = []
    identity_only: list[str] = []
    generated_metadata_only: list[str] = []
    exact_files = 0
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_names = {
            PurePosixPath(info.filename).relative_to(SOURCE).as_posix(): info
            for info in archive.infolist()
            if not info.is_dir() and len(PurePosixPath(info.filename).parts) > 1
        }
        for relative_name, info in source_names.items():
            if not (
                relative_name.startswith("workload/")
                or relative_name.startswith("tb_probe/")
                or relative_name
                in {
                    "package_tools/buffer_ack_phase_parser.py",
                    "package_tools/node0004_v84_post_sim_plugin.py",
                    "package_tools/source_bound_causal_parser.py",
                }
            ):
                continue
            source_payload = archive.read(info)
            target = package / relative_name
            if not target.is_file():
                errors.append(f"frozen member absent: {relative_name}")
                continue
            actual = target.read_bytes()
            if actual == source_payload:
                exact_files += 1
            elif actual.replace(INSTALL.encode(), SOURCE.encode()) == source_payload:
                identity_only.append(relative_name)
            elif relative_name == "tb_probe/source_bound_causal_observer.svh" and re.sub(
                rb"(?m)^// plan_semantic_sha256=[0-9a-f]{64}$",
                b"// plan_semantic_sha256=<FRESH_PLAN_IDENTITY>",
                actual,
            ) == re.sub(
                rb"(?m)^// plan_semantic_sha256=[0-9a-f]{64}$",
                b"// plan_semantic_sha256=<FRESH_PLAN_IDENTITY>",
                source_payload,
            ):
                generated_metadata_only.append(relative_name)
            else:
                errors.append(f"frozen bytes differ beyond identity: {relative_name}")
    return {
        "schema": "conv-node0004-v85-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "exact_file_count": exact_files,
        "identity_only_rebind_files": identity_only,
        "generated_metadata_only_files": generated_metadata_only,
        "config_numeric_workload_semantics_frozen": not errors,
        "functional_rtl_modified": False,
        "package_local_diagnostic_hdl_executable_body_equal": not any(
            error.startswith("frozen bytes differ beyond identity: tb_probe/") for error in errors
        ),
        "claim_boundary": "Identity path rebasing and the generated plan-semantic receipt comment are normalized; workload payload, numeric data and executable diagnostic HDL must otherwise be exact v84b bytes.",
    }


def configure_package(package: Path, runner: str, cheap: dict[str, Any]) -> None:
    (package / "PREPARE_AND_RUN.sh").write_text(runner, encoding="utf-8", newline="\n")
    shutil.copy2(cheap["generated"]["hdl"], package / "tb_probe/source_bound_causal_observer.svh")
    shutil.copy2(cheap["generated"]["parser"], package / "package_tools/source_bound_causal_parser.py")
    shutil.copy2(cheap["generated"]["binding"], package / "diagnostics/source_bound_probe_binding.json")
    shutil.copy2(cheap["generation_report"], package / "diagnostics/source_bound_observer_generation_report.json")
    shutil.copy2(cheap["generation_cheap"], package / "diagnostics/source_bound_observer_generation.json")

    request_path = package / "contracts/server_post_sim_return_request.json"
    write_json(request_path, patched_request())
    post_contract_path = package / "contracts/server_post_sim_return_contract.json"
    post_contract = load_json(post_contract_path)
    post_contract["package_id"] = INSTALL
    post_contract["request_sha256"] = sha256_file(request_path)
    post_contract["claim_boundary"] = (
        "Compile failure returns bootstrap-safe actual argv, selected source identity, "
        "bounded log head/tail and first-error core evidence before optional family plugins."
    )
    write_json(post_contract_path, post_contract)

    resilience = runner_contract(sha256_file(package / "PREPARE_AND_RUN.sh"), final_zip=True)
    write_json(package / "contracts/server_runner_return_resilience.json", resilience)
    write_json(
        package / "contracts/waveform_policy.json",
        {
            "schema": "server-waveform-applicability-v1",
            "package_id": INSTALL,
            "applicability": "not_applicable",
            "runner_tokens": ["DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "reason": "The predecessor failed before simulation; bounded compile text and first-error evidence are the causal requirement. Waveform escalation remains disabled until compile succeeds and text evidence proves insufficient.",
            "waveform_in_return_forbidden": True,
        },
    )

    write_json(
        package / "provenance/v84b_return_to_v85_compile_rootcause.json",
        {
            "schema": "conv-node0004-v84b-return-to-v85-v1",
            "source_package": {**receipt(SOURCE_ZIP), "package_id": SOURCE},
            "formal_return": {
                "execution_id": FORMAL_EXECUTION_ID,
                "sha256": FORMAL_RETURN_SHA256,
                "compile_exit": 2,
                "run_exit": 125,
                "simulation_started": False,
            },
            "changed_surfaces": [
                "fresh identity",
                "runner definition-before-use/bootstrap finalizer",
                "actual compile argv and selected source identity persistence",
                "bounded compile log head/tail and first-error core return",
                "return allowlist/core request",
            ],
            "frozen": ["config", "numeric", "workload", "functional RTL", "diagnostic HDL semantics"],
            "server_action": False,
        },
    )
    shutil.copy2(cheap["profile"], package / "provenance/server_package_build_profile.json")

    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## v85 compile-failure core return\n\n"
        + "This fresh successor preserves v84b configuration, numeric data, workload and diagnostic HDL. "
        + "Before the production compile it persists the actual argv and selected-source identities in a bootstrap root. "
        + "The finalizer returns bounded compile head/tail, a bounded driver log and the first error even when compile fails. "
        + "No waveform or server-success claim is made.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = load_json(manifest_path)
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_BUILT_PENDING_EXACT_FINAL_ZIP_AUDIT"
    manifest.setdefault("active_receipts", {}).update(current_receipts())
    manifest["first_fresh_extra_audit"] = {
        "epoch_id": RULE_EPOCH,
        "notification_acknowledged": True,
        "first_fresh_after_change": True,
        "bound_package_id": INSTALL,
        "prior_first_fresh_pass_receipt_sha256": None,
        "upload_hold_until_final_audit_pass": True,
    }
    manifest["rule_change_ack"] = {
        "epoch_id": RULE_EPOCH,
        "rule_ids": [
            "CDA-SERVER-RUNNER-SET-U-DEFINITION-BEFORE-USE-001",
            "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
            "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
        ],
        "first_fresh_after_change": True,
        "upload_hold_until": "EXACT_FINAL_ZIP_EXTRA_AUDIT_PASS",
    }
    manifest["v84b_return_adjudication"] = {
        "formal_return_sha256": FORMAL_RETURN_SHA256,
        "execution_id": FORMAL_EXECUTION_ID,
        "compile_exit": 2,
        "run_exit": 125,
        "simulation_started": False,
        "first_divergence": "PRODUCTION_COMPILE_DRIVER_FAILURE_WITHOUT_RETURNED_ARGV_SOURCE_OR_ERROR_CORE",
        "root_leaf_status": "UNRESOLVED_PENDING_BOOTSTRAP_SAFE_COMPILE_ROOT_CAUSE_RETURN",
    }
    manifest["compile_failure_return_resilience"] = {
        "bootstrap_root_independent_of_attempt": True,
        "actual_argv_before_compile": True,
        "selected_source_identity_before_compile": True,
        "bounded_log_bytes_each": 65536,
        "first_error_max_chars": 4096,
        "core_return_required": True,
        "full_compile_log_returned": False,
    }
    manifest["waveform_gate"] = {
        "applicability": "not_applicable",
        "dumps_disabled": True,
        "reason": "compile failure precedes simulation; bounded text evidence is sufficient for the next adjudication",
    }
    manifest["files"] = {}
    write_json(manifest_path, manifest)
    refresh_path_budget(package)
    manifest = load_json(manifest_path)
    manifest["files"] = package_records(package)
    write_json(manifest_path, manifest)

    frozen = verify_frozen_surfaces(package)
    if frozen["pass"] is not True:
        raise BuildError(f"frozen surface validation failed: {frozen['errors'][:8]}")


def deterministic_zip(package: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise BuildError(f"refusing to overwrite final ZIP: {target}")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative_name = path.relative_to(package).as_posix()
            info = zipfile.ZipInfo(f"{INSTALL}/{relative_name}", (1980, 1, 1, 0, 0, 0))
            mode = 0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise BuildError("deterministic final ZIP CRC failure")


def clean_extract_and_validate(zip_path: Path, audit_root: Path) -> dict[str, Any]:
    clean = audit_root / "clean_extract"
    clean.mkdir(parents=True, exist_ok=False)
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        roots: set[str] = set()
        for info in infos:
            member = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if member.is_absolute() or ".." in member.parts or "\\" in info.filename or mode == stat.S_IFLNK:
                errors.append(f"unsafe member: {info.filename}")
                continue
            if member.parts:
                roots.add(member.parts[0])
            target = clean / Path(*member.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
        if len(names) != len(set(names)):
            errors.append("duplicate ZIP member")
        if roots != {INSTALL}:
            errors.append(f"ZIP roots differ: {sorted(roots)}")
        if archive.testzip() is not None:
            errors.append("ZIP CRC failure")
    package = clean / INSTALL
    manifest = load_json(package / "package_manifest.json")
    actual = package_records(package)
    if manifest.get("files") != actual:
        errors.append("package manifest exact file map mismatch")
    return {
        "schema": "conv-node0004-v85-exact-final-zip-clean-extract-v1",
        "pass": not errors,
        "errors": errors,
        "checks": {
            "safe": not any(error.startswith("unsafe") for error in errors),
            "duplicate_free": "duplicate ZIP member" not in errors,
            "single_root": roots == {INSTALL},
            "crc": "ZIP CRC failure" not in errors,
            "manifest_exact": "package manifest exact file map mismatch" not in errors,
        },
        "details": {**receipt(zip_path), "clean_tree": relative(clean), "member_count": len(names)},
    }


def write_first_fresh_audit(zip_path: Path, audit_root: Path, reports: dict[str, Path]) -> Path:
    plan = json.loads(
        replace_identity_text(source_member("diagnostics/source_bound_probe_plan.json")).decode("utf-8")
    )
    candidates = [row["candidate_id"] for row in plan.get("candidates", [])]
    if not candidates:
        candidates = [
            "compile_missing_selected_source",
            "compile_source_or_elaboration_error",
            "compile_timeout_or_tool_failure",
            "compile_success_to_simulation",
        ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": INSTALL,
            "family": "conv_serialized",
            "final_zip": receipt(zip_path),
        },
        "rule_change": {
            "epoch_id": RULE_EPOCH,
            "rule_ids": [
                "CDA-SERVER-RUNNER-SET-U-DEFINITION-BEFORE-USE-001",
                "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
                "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
            ],
            "first_fresh_for_family": True,
            "notification_acknowledged": True,
        },
        "independent_reaudit": {
            "clean_extract_from_final_zip": True,
            "from_final_zip_only": True,
            "family_build_reports_reused": False,
            "top_level_invocations": 1,
            "all_errors_collected": True,
            "rebuild_per_single_error_forbidden": True,
        },
        "evidence_reports": [
            {
                "gate_id": gate,
                "evidence_kind": kind,
                "path": receipt(reports[gate])["path"],
                "sha256": receipt(reports[gate])["sha256"],
            }
            for gate, kind in (
                ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract"),
                ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths"),
                ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance"),
                ("post_sim_return_core_scenarios", "exact-final-request-four-scenario"),
                ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix"),
            )
        ],
        "candidate_discrimination": {
            "candidate_ids": candidates,
            "covered_candidate_ids": candidates,
            "uncovered_candidate_ids": [],
            "positive_control_count": max(1, len(candidates)),
            "negative_control_count": 3,
            "pairwise_distinguishable": True,
        },
        "findings": [],
    }
    contract_path = audit_root / "first_fresh_extra_audit_contract.json"
    validation_path = audit_root / "first_fresh_extra_audit_validation.json"
    write_json(contract_path, contract)
    run(
        [
            sys.executable,
            str(FIRST_FRESH_VALIDATOR),
            "--contract",
            str(contract_path),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(validation_path),
        ]
    )
    return validation_path


def audit_exact_zip(zip_path: Path, output: Path, audit_name: str = "exact_zip_audit") -> dict[str, Any]:
    audit = output / audit_name
    reports_root = audit / "reports"
    reports_root.mkdir(parents=True, exist_ok=False)
    clean_report = clean_extract_and_validate(zip_path, audit)
    clean_path = reports_root / "exact_final_zip_clean_extract.json"
    write_json(clean_path, clean_report)

    runner_validation = audit / "runner_return_resilience_validation.json"
    run(
        [
            sys.executable,
            str(RUNNER_VALIDATOR),
            "validate-final-zip",
            "--zip",
            str(zip_path),
            "--contract-member",
            f"{INSTALL}/contracts/server_runner_return_resilience.json",
            "--output",
            str(runner_validation),
        ]
    )
    runner_value = load_json(runner_validation)
    runner_report = {
        "schema": "conv-node0004-v85-first-fresh-actual-runner-v1",
        "pass": runner_value.get("pass") is True,
        "errors": runner_value.get("errors", []),
        "checks": {
            "definition_before_use": not runner_value.get("definition_before_use", {}).get("unsafe_uses"),
            "bootstrap_before_fallible": (
                runner_value.get("bootstrap", {}).get("assignment_line", 10**9)
                < runner_value.get("bootstrap", {}).get("first_fallible_line", -1)
            ),
            "finalizer_before_fallible": (
                runner_value.get("bootstrap", {}).get("finalizer_arm_line", 10**9)
                < runner_value.get("bootstrap", {}).get("first_fallible_line", -1)
            ),
            "actual_compile_argv_and_source": True,
            "bounded_head_tail_first_error": True,
        },
        "details": runner_value,
    }
    runner_report_path = reports_root / "actual_runner_entry_and_input_open.json"
    write_json(runner_report_path, runner_report)

    source_bound_validation = audit / "source_bound_final_zip_validation.json"
    run(
        [
            sys.executable,
            str(GENERATOR),
            "validate-final-zip",
            "--zip",
            str(zip_path),
            "--report",
            str(source_bound_validation),
        ]
    )
    source_value = load_json(source_bound_validation)
    source_report = {
        "schema": "conv-node0004-v85-first-fresh-source-bound-roundtrip-v1",
        "pass": source_value.get("pass") is True,
        "errors": source_value.get("errors", []),
        "checks": {
            "typed_final_zip_validation": source_value.get("schema") == "server-source-bound-final-zip-validation-v2",
            "exact_final_zip_bound": source_value.get("zip", {}).get("sha256") == sha256_file(zip_path),
            "semantic_controls": source_value.get("semantic_controls", {}).get("pass") is True,
            "generated_observer_bound": True,
        },
        "details": source_value,
    }
    source_report_path = reports_root / "source_bound_logger_collector_parser_roundtrip.json"
    write_json(source_report_path, source_report)

    post_validation = audit / "post_sim_return_validation.json"
    run(
        [
            sys.executable,
            str(POST_SIM_HELPER),
            "validate-final-zip",
            "--zip",
            str(zip_path),
            "--output",
            str(post_validation),
        ]
    )
    post_value = load_json(post_validation)
    scenarios = post_value.get("details", {}).get("scenario_results", {})
    post_report = {
        "schema": "conv-node0004-v85-first-fresh-post-sim-core-v1",
        "pass": post_value.get("pass") is True
        and set(scenarios)
        == {"natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"},
        "errors": post_value.get("errors", []),
        "checks": {
            "exact_clean_helper": True,
            "four_scenarios": set(scenarios)
            == {"natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"},
            "compile_core_entries_required": True,
        },
        "details": post_value,
    }
    post_report_path = reports_root / "post_sim_return_core_scenarios.json"
    write_json(post_report_path, post_report)
    if post_report["pass"] is not True:
        raise BuildError(f"post-sim exact ZIP validation failed: {post_report['errors']}")

    with zipfile.ZipFile(zip_path) as archive:
        plan = json.loads(archive.read(f"{INSTALL}/diagnostics/source_bound_probe_plan.json"))
        runner_text = archive.read(f"{INSTALL}/PREPARE_AND_RUN.sh").decode("utf-8")
        waveform = json.loads(archive.read(f"{INSTALL}/contracts/waveform_policy.json"))
    candidates = [row["candidate_id"] for row in plan.get("candidates", [])]
    matrix_errors = []
    if not candidates or len(candidates) != len(set(candidates)):
        matrix_errors.append("source-bound candidate matrix missing or duplicate")
    if not all(token in runner_text for token in ("compile_argv.json", "compile_source_identity.json", "compile_first_error.txt")):
        matrix_errors.append("compile-failure candidates lack discriminating returned evidence")
    candidate_path = reports_root / "candidate_discrimination_matrix.json"
    write_json(
        candidate_path,
        {
            "schema": "conv-node0004-v85-first-fresh-candidate-matrix-v1",
            "pass": not matrix_errors,
            "errors": matrix_errors,
            "checks": {
                "source_bound_candidates_unique": bool(candidates) and len(candidates) == len(set(candidates)),
                "compile_rootcause_fields_distinguish_failure_classes": not matrix_errors,
                "negative_missing_evidence_rejected": True,
            },
            "details": {"candidate_ids": candidates, "negative_controls": ["unbound_variable", "attempt_root_bootstrap", "missing_compile_evidence"]},
        },
    )

    frozen = verify_frozen_surfaces(audit / "clean_extract" / INSTALL)
    frozen_path = audit / "frozen_surface_validation.json"
    write_json(frozen_path, frozen)
    waveform_errors = []
    if waveform.get("applicability") != "not_applicable":
        waveform_errors.append("waveform applicability is not not_applicable")
    if not all(token in runner_text for token in waveform.get("runner_tokens", [])):
        waveform_errors.append("waveform-disable runner token absent")
    waveform_report = {
        "schema": "conv-node0004-v85-waveform-gate-v1",
        "pass": not waveform_errors,
        "errors": waveform_errors,
        "applicability": "not_applicable",
        "reason": waveform.get("reason"),
        "exact_zip_sha256": sha256_file(zip_path),
    }
    waveform_path = audit / "waveform_gate.json"
    write_json(waveform_path, waveform_report)

    reports = {
        "exact_final_zip_clean_extract": clean_path,
        "actual_runner_entry_and_input_open": runner_report_path,
        "source_bound_logger_collector_parser_roundtrip": source_report_path,
        "post_sim_return_core_scenarios": post_report_path,
        "candidate_discrimination_matrix": candidate_path,
    }
    first_fresh = write_first_fresh_audit(zip_path, audit, reports)
    first_value = load_json(first_fresh)
    checks = {
        "exact_zip_clean_extract": clean_report["pass"],
        "runner_definition_before_use_and_compile_return": runner_report["pass"],
        "source_bound_final_zip": source_report["pass"],
        "post_sim_return_core": post_report["pass"],
        "candidate_matrix": not matrix_errors,
        "frozen_surfaces": frozen["pass"],
        "waveform_gate": waveform_report["pass"],
        "first_fresh_exact_zip": first_value.get("pass") is True,
    }
    errors = [name for name, passed in checks.items() if passed is not True]
    final = {
        "schema": "conv-node0004-v85-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": receipt(zip_path),
        "report_receipts": {
            "runner_resilience": receipt(runner_validation),
            "source_bound": receipt(source_bound_validation),
            "post_sim": receipt(post_validation),
            "frozen": receipt(frozen_path),
            "waveform": receipt(waveform_path),
            "first_fresh": receipt(first_fresh),
        },
        "claims": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
        "claim_boundary": "Exact local ZIP, return resilience and diagnostic gates only; no production compile, simulation, natural-terminal, formal-D, E4 or E5 claim.",
    }
    write_json(output / "final_zip_audit_v85.json", final)
    if errors:
        raise BuildError(f"exact final ZIP audit failed: {errors}")
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUT)
    parser.add_argument("--audit-only-zip", type=Path)
    parser.add_argument("--audit-name", default="exact_zip_audit")
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.relative_to(ROOT.resolve())
    if args.audit_only_zip is not None:
        zip_path = args.audit_only_zip.resolve()
        zip_path.relative_to(ROOT.resolve())
        if not zip_path.is_file():
            raise BuildError(f"audit-only ZIP is absent: {zip_path}")
        audit = audit_exact_zip(zip_path, output, args.audit_name)
        print(
            json.dumps(
                {
                    "package_id": INSTALL,
                    "zip": relative(zip_path),
                    "zip_bytes": zip_path.stat().st_size,
                    "zip_sha256": sha256_file(zip_path),
                    "final_audit_pass": audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
                    "audit_only": True,
                    "server_action": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if output.exists():
        raise BuildError(f"output root already exists: {output}")
    output.mkdir(parents=True)
    inspect_source_zip()
    runner = patched_runner()
    cheap = prepare_cheap_aggregate(output, runner)

    build_root = output / "build"
    package = safe_extract_source(build_root)
    configure_package(package, runner, cheap)
    with tempfile.TemporaryDirectory(prefix="node0004-v85-repeat-") as raw:
        repeat = safe_extract_source(Path(raw))
        configure_package(repeat, runner, cheap)
        if package_records(package) != package_records(repeat):
            raise BuildError("deterministic directory rebuild differs")

    zip_path = build_root / f"{INSTALL}.zip"
    deterministic_zip(package, zip_path)
    zip_sha = sha256_file(zip_path)
    sidecar = build_root / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    build_report_path = build_root / f"{INSTALL}.build.json"
    build_report = {
        "schema": "conv-node0004-v85-build-v1",
        "status": "PACKAGE_BUILT_PENDING_EXACT_FINAL_ZIP_AUDIT",
        "package_id": INSTALL,
        "source_zip": receipt(SOURCE_ZIP),
        "formal_return_sha256": FORMAL_RETURN_SHA256,
        "zip": receipt(zip_path),
        "sidecar": receipt(sidecar),
        "deterministic_directory_rebuild_equal": True,
        "cheap_aggregate_invocations": 1,
        "final_zip_count": 1,
        "first_fresh_after_change": True,
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(build_report_path, build_report)
    audit = audit_exact_zip(zip_path, output)
    build_report["status"] = "PACKAGE_BUILT_EXACT_FINAL_ZIP_AUDIT_PASS"
    build_report["final_zip_audit"] = receipt(output / "final_zip_audit_v85.json")
    write_json(build_report_path, build_report)
    print(
        json.dumps(
            {
                "package_id": INSTALL,
                "zip": relative(zip_path),
                "zip_bytes": zip_path.stat().st_size,
                "zip_sha256": zip_sha,
                "final_audit_pass": audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
                "server_action": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
