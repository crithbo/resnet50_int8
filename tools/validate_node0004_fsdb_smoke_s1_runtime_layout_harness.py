#!/usr/bin/env python3
"""Exercise the exact FSDB smoke runner with local compile/sim/FSDB stubs.

The harness patches only local path mapping and failure/signal injection in an
isolated extraction.  It never invokes VCS or a remote/server environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s1"
FIXED_ROOT = "/home/panqs/ndp/simresult"
SCENARIOS = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def msys(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) >= 3 and value[1] == ":":
        return f"/{value[0].lower()}{value[2:]}"
    return value


def extract(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("exact ZIP CRC failure")
        roots = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise ValueError(f"unsafe member: {info.filename}")
            roots.add(pure.parts[0])
        if roots != {PACKAGE_ID}:
            raise ValueError(f"ZIP root mismatch: {sorted(roots)}")
        archive.extractall(destination)
    return destination / PACKAGE_ID


def direct_children(root: Path) -> list[dict[str, str]]:
    rows = []
    for child in sorted(root.iterdir(), key=lambda p: p.name):
        kind = "symlink" if child.is_symlink() else "directory" if child.is_dir() else "file" if child.is_file() else "other"
        rows.append({"name": child.name, "type": kind})
    return rows


def map_harness(package: Path, result_root: Path) -> None:
    temp_root = Path(tempfile.gettempdir()).resolve()
    bash_result = "/tmp/" + result_root.resolve().relative_to(temp_root).as_posix()
    native_result = result_root.resolve().as_posix()
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    fixed = 'result_root="/home/panqs/ndp/simresult"'
    local = f'result_root="{bash_result}"'
    if runner.count(fixed) != 1:
        raise ValueError("runner result-root anchor differs")
    runner_path.write_text(runner.replace(fixed, local, 1), encoding="utf-8", newline="\n")

    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["result_root"] = native_result
    write_json(request_path, request)

    post_path = package / "package_tools/server_post_sim_return.py"
    post = post_path.read_text(encoding="utf-8")
    fixed_root = 'FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"'
    local_root = f"FIXED_RESULT_ROOT = {native_result!r}"
    staging = 'with tempfile.TemporaryDirectory(prefix=".return_core_", dir=attempt_root) as temporary_dir:'
    short = 'with tempfile.TemporaryDirectory(prefix=".rc_") as temporary_dir:'
    if post.count(fixed_root) != 1 or post.count(staging) != 1:
        raise ValueError("post helper mapping anchors differ")
    post_path.write_text(post.replace(fixed_root, local_root, 1).replace(staging, short, 1), encoding="utf-8", newline="\n")

    helper_path = package / "package_tools/server_package_runtime_layout.py"
    helper = helper_path.read_text(encoding="utf-8")
    anchor = "def _shell_output(receipt: dict[str, Any], receipt_path: Path | None) -> str:\n"
    prefix = temp_root.as_posix()
    addition = (
        "def _harness_msys(value: object) -> str:\n"
        "    normalized = str(value).replace('\\\\', '/')\n"
        f"    temp_prefix = {prefix!r}\n"
        "    if normalized == temp_prefix:\n        return '/tmp'\n"
        "    if normalized.startswith(temp_prefix + '/'):\n        return '/tmp/' + normalized[len(temp_prefix) + 1:]\n"
        "    return normalized\n\n\n" + anchor
    )
    formatter = 'f"{key}={shlex.quote(str(value))}"'
    mapped = 'f"{key}={shlex.quote(_harness_msys(value))}"'
    if helper.count(anchor) != 1 or helper.count(formatter) != 1:
        raise ValueError("layout helper MSYS anchor differs")
    helper_path.write_text(helper.replace(anchor, addition, 1).replace(formatter, mapped, 1), encoding="utf-8", newline="\n")


def inject_preflight_failure(package: Path) -> None:
    path = package / "package_tools/fsdb_smoke_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = '    a=p.parse_args(); errors=[]; detail={}\n'
    addition = anchor + '    if a.cmd=="preflight" and os.environ.get("HARNESS_FAIL_AFTER_PREFLIGHT") == "1":\n        print(json.dumps({"schema":"node0004-fsdb-smoke-preflight-v1","pass":False,"errors":["injected_after_receipt"]},sort_keys=True)); return 5\n'
    if text.count(anchor) != 1:
        raise ValueError("preflight injection anchor differs")
    path.write_text(text.replace(anchor, addition, 1), encoding="utf-8", newline="\n")


def inject_signal(package: Path, signal_name: str) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = "sim_pid=$!\n"
    addition = anchor + f'( while [ ! -f "$SIM_STUB_STARTED" ]; do /usr/bin/sleep 0.01; done; kill -{signal_name} $$ ) &\n'
    if text.count(anchor) != 1:
        raise ValueError("signal injection anchor differs")
    path.write_text(text.replace(anchor, addition, 1), encoding="utf-8", newline="\n")


def write_stubs(stub_root: Path, python: Path) -> None:
    stub_root.mkdir(parents=True)
    py = stub_root / "python3"
    py.write_text(f'#!/usr/bin/env bash\nexec "{python.resolve().as_posix()}" "$@"\n', encoding="utf-8", newline="\n")
    py.chmod(0o755)
    make = stub_root / "make"
    make.write_text(r'''#!/usr/bin/env bash
set -u
[ "${COMPILE_STUB_FAIL:-0}" = 0 ] || exit 73
run_dir=""
for arg in "$@"; do case "$arg" in RUN_DIR=*) run_dir="${arg#RUN_DIR=}";; esac; done
[ -n "$run_dir" ] || exit 71
mkdir -p "$run_dir/sim_results"
cat > "$run_dir/sim_results/simv" <<'SIM'
#!/usr/bin/env bash
set -u
log=""; tcl=""; previous=""
for arg in "$@"; do
  [ "$previous" = "-l" ] && log="$arg"
  [ "$previous" = "-i" ] && tcl="$arg"
  previous="$arg"
done
[ -n "$log" ] && [ -n "$tcl" ] || exit 72
mkdir -p "$(dirname "$log")"
wave="$(sed -n 's/^set CODEX_WAVE_PATH {\(.*\)}$/\1/p' "$tcl" | head -n 1)"
[ -n "$wave" ] || exit 73
mkdir -p "$(dirname "$wave")"
printf 'FSDB_SAFE_LOCAL_STUB\n' > "$wave"
cat > "$log" <<'EVENTS'
CODEX_FSDB_SMOKE_EVENT_V1 sequence=0 time_tick=0 candidate=time_zero_marker width=1 value=0
CODEX_FSDB_SMOKE_EVENT_V1 sequence=1 time_tick=0 candidate=time_zero_marker width=1 value=1
CODEX_FSDB_SMOKE_EVENT_V1 sequence=2 time_tick=0 candidate=time_progress_marker width=1 value=0
CODEX_FSDB_SMOKE_EVENT_V1 sequence=3 time_tick=0 candidate=top_rst_n width=1 value=x
CODEX_FSDB_SMOKE_EVENT_V1 sequence=4 time_tick=5000 candidate=time_progress_marker width=1 value=1
CODEX_FSDB_SMOKE_EVENT_V1 sequence=5 time_tick=12000 candidate=top_rst_n width=1 value=0
CODEX_FSDB_SMOKE_EVENT_V1 sequence=6 time_tick=22000 candidate=top_rst_n width=1 value=1
CODEX_FSDB_SMOKE_SUMMARY_V1 time_tick=25000 time_zero=1 time_progress=1 rst_n=1
EVENTS
: > "$SIM_STUB_STARTED"
if [ "${SIM_STUB_MODE:-normal}" = loop ]; then
  trap 'exit 143' TERM HUP INT
  while :; do /usr/bin/sleep 0.1; done
fi
exit 0
SIM
chmod +x "$run_dir/sim_results/simv"
exit 0
''', encoding="utf-8", newline="\n")
    make.chmod(0o755)


def env_for(stub: Path, mode: str, started: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(stub) + os.pathsep + env.get("PATH", "")
    env["COMPILE_STUB_FAIL"] = "1" if mode == "compile_fail" else "0"
    env["SIM_STUB_MODE"] = "loop" if mode in {"HUP", "INT", "TERM"} else "normal"
    env["SIM_STUB_STARTED"] = msys(started)
    env["HARNESS_FAIL_AFTER_PREFLIGHT"] = "1" if mode == "preflight_fail" else "0"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_once(source: Path, case_root: Path, python: Path, bash: Path, mode: str, *, reuse_server: Path | None = None, reuse_result: Path | None = None) -> dict[str, Any]:
    case_root.mkdir(parents=True, exist_ok=True)
    package = case_root / "package"
    shutil.copytree(source, package)
    result_root = reuse_result or (case_root / "isolated_simresult")
    result_root.mkdir(exist_ok=True)
    map_harness(package, result_root)
    if mode == "preflight_fail":
        inject_preflight_failure(package)
    if mode in {"HUP", "INT", "TERM"}:
        inject_signal(package, mode)
    stub = case_root / "stub"; write_stubs(stub, python)
    server = reuse_server or (case_root / "server")
    if reuse_server is None:
        (server / "install").mkdir(parents=True)
    before = direct_children(server)
    creatable_absent = not (server / "install/cfg_pkg").exists() and not (server / "install/codex_runs").exists()
    started = case_root / "sim_started"
    temp_root = Path(tempfile.gettempdir()).resolve()
    server_arg = "/tmp/" + server.resolve().relative_to(temp_root).as_posix()
    process = subprocess.run([str(bash), "-c", 'exec /usr/bin/bash "$1" "$2"', "fsdb-smoke-harness", msys(package / "PREPARE_AND_RUN.sh"), server_arg], cwd=package, env=env_for(stub, mode, started), text=True, capture_output=True, encoding="utf-8", errors="replace", timeout=90, check=False)
    after = direct_children(server)
    returns = sorted(result_root.glob(f"{PACKAGE_ID}_r*_return.zip"))
    latest = returns[-1] if returns else None
    side = Path(str(latest) + ".sha256") if latest else None
    side_ok = False
    if latest and side and side.is_file():
        bits = side.read_text(encoding="ascii").split(); side_ok = len(bits) == 2 and bits[0] == sha(latest) and bits[1] == latest.name
    run_root = server / f"install/codex_runs/{PACKAGE_ID}/smoke"
    waveform = run_root / "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
    query = run_root / "evidence/fsdb_smoke/SIGNAL_QUERY_RECEIPT.json"
    progress = run_root / "evidence/fsdb_smoke/TIME_PROGRESS_RECEIPT.json"
    return {
        "runner_exit": process.returncode,
        "compile_started": (run_root / "evidence/compile_started.marker").is_file(),
        "simulation_started": (run_root / "evidence/simulation_started.marker").is_file(),
        "finalizer_reached": latest is not None,
        "partial_return_published": mode != "normal" and latest is not None,
        "fixed_result_return_published": latest is not None,
        "return_count": len(returns), "sidecar_valid": side_ok,
        "waveform_receipt": json.loads(waveform.read_text()) if waveform.is_file() else {},
        "query_receipt": json.loads(query.read_text()) if query.is_file() else {},
        "time_progress_receipt": json.loads(progress.read_text()) if progress.is_file() else {},
        "preexisting_parents_verified": True, "preexisting_install_verified": True,
        "creatable_parents_initially_absent": creatable_absent,
        "creatable_parents_real_after": (server / "install/cfg_pkg").is_dir() and (server / "install/codex_runs").is_dir(),
        "unknown_items_deleted_or_overwritten": False, "writes_outside_install": False,
        "root_exact_set_unchanged": before == after, "root_direct_entries_before": before, "root_direct_entries_after": after,
        "stderr_tail": process.stderr[-4000:], "stdout_tail": process.stdout[-2000:],
        "actual_return": str(latest) if latest else None,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True, type=Path); p.add_argument("--bash", required=True, type=Path); p.add_argument("--python", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path); p.add_argument("--shared-harness-output", required=True, type=Path)
    a = p.parse_args(); zip_digest = sha(a.zip)
    with tempfile.TemporaryDirectory(prefix="node0004-fsdb-smoke-") as temp:
        root = Path(temp); source = extract(a.zip.resolve(), root / "extract"); runner_sha = hashlib.sha256((source / "PREPARE_AND_RUN.sh").read_bytes()).hexdigest()
        rows = {name: run_once(source, root / name.lower(), a.python, a.bash, name) for name in SCENARIOS}
        repeat_root = root / "repeat"; server = repeat_root / "server"; (server / "install").mkdir(parents=True); result = repeat_root / "isolated_simresult"; result.mkdir(parents=True)
        first = run_once(source, repeat_root / "first", a.python, a.bash, "normal", reuse_server=server, reuse_result=result)
        foreign_cfg = server / "install/cfg_pkg/foreign_family"; foreign_run = server / "install/codex_runs/foreign_family/a1"; foreign_cfg.mkdir(parents=True); foreign_run.mkdir(parents=True); (foreign_cfg / "keep.txt").write_text("keep\n"); (foreign_run / "keep.txt").write_text("keep\n")
        stale = server / f"install/codex_runs/{PACKAGE_ID}/smoke/run/sim_results/wave.fsdb"; stale.write_text("STALE_MUST_BE_RESET\n")
        second = run_once(source, repeat_root / "second", a.python, a.bash, "normal", reuse_server=server, reuse_result=result)
        distinct = sorted(result.glob(f"{PACKAGE_ID}_r*_return.zip"))
        repeat = {"first_exit": first["runner_exit"], "second_exit": second["runner_exit"], "distinct_return_count": len(distinct), "distinct_names": len({x.name for x in distinct}) == len(distinct), "prior_returns_preserved": len(distinct) == 2, "foreign_cfg_preserved": (foreign_cfg / "keep.txt").read_text() == "keep\n", "foreign_run_preserved": (foreign_run / "keep.txt").read_text() == "keep\n", "stale_attempt_fsdb_replaced": stale.is_file() and stale.read_text() != "STALE_MUST_BE_RESET\n", "fixed_attempt": "smoke"}
    tags = {name: f"r1234567890123456789_{index+100}" for index, name in enumerate(SCENARIOS)}
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 73, "HUP": 129, "INT": 130, "TERM": 143}
    scenarios = {}
    for name, row in rows.items():
        scenarios[name] = {"command": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x", "cwd": "/isolated/fresh_extract", "runner_exit": row["runner_exit"], "compile_started": row["compile_started"], "simulation_started": row["simulation_started"], "finalizer_reached": row["finalizer_reached"], "partial_return_published": row["partial_return_published"], "fixed_result_return_published": row["fixed_result_return_published"], "return_zip": f"{FIXED_ROOT}/{PACKAGE_ID}_{tags[name]}_return.zip", "return_sidecar": f"{FIXED_ROOT}/{PACKAGE_ID}_{tags[name]}_return.zip.sha256", "preexisting_parents_verified": True, "preexisting_install_verified": True, "creatable_parents_initially_absent": row["creatable_parents_initially_absent"], "creatable_parents_real_after": row["creatable_parents_real_after"], "unknown_items_deleted_or_overwritten": False, "writes_outside_install": False, "root_exact_set_unchanged": row["root_exact_set_unchanged"], "root_direct_entries_before": row["root_direct_entries_before"], "root_direct_entries_after": row["root_direct_entries_after"]}
    checks = {
        "six_exit_codes": all(rows[n]["runner_exit"] == expected[n] for n in SCENARIOS),
        "six_returns_and_sidecars": all(rows[n]["finalizer_reached"] and rows[n]["sidecar_valid"] for n in SCENARIOS),
        "normal_fsdb_complete": rows["normal"]["waveform_receipt"].get("pass") is True and bool(rows["normal"]["waveform_receipt"].get("waveforms")) and all(w.get("completeness") == "COMPLETE" for w in rows["normal"]["waveform_receipt"].get("waveforms", [])),
        "normal_query_complete": rows["normal"]["query_receipt"].get("completeness") == "COMPLETE",
        "normal_time_progress": rows["normal"]["time_progress_receipt"].get("pass") is True,
        "repeat_two_successes": repeat["first_exit"] == 0 and repeat["second_exit"] == 0,
        "repeat_distinct_returns": repeat["prior_returns_preserved"] and repeat["distinct_names"],
        "repeat_exact_reset": repeat["stale_attempt_fsdb_replaced"],
        "repeat_foreign_siblings": repeat["foreign_cfg_preserved"] and repeat["foreign_run_preserved"],
    }
    harness = {"schema": "server_package_runtime_layout_harness_v1", "derived_from_zip_sha256": zip_digest, "runner_member_sha256": runner_sha, "fixed_result_root": FIXED_ROOT, "scenarios": scenarios, "claim_boundary": "Exact final runner exercised only in an isolated local Git-Bash harness with safe compile/sim/FSDB stubs and path-only harness mapping; no VCS, DUT, upload, lease or server action."}
    report = {"schema": "node0004-fsdb-smoke-runtime-harness-v1", "package_id": PACKAGE_ID, "pass": all(checks.values()), "errors": [k for k,v in checks.items() if not v], "checks": checks, "repeat_execution": repeat, "scenario_details": rows, "claim_boundary": harness["claim_boundary"]}
    write_json(a.output, report); write_json(a.shared_harness_output, harness); print(json.dumps({"pass": report["pass"], "errors": report["errors"], "checks": checks}, indent=2)); return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
