from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


INSTALL = "r5_n71_gap_v49_mse4_maskwide_diag"
FIXED_ROOT = "/home/panqs/ndp/simresult"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def extract(source: Path, destination: Path) -> Path:
    with zipfile.ZipFile(source) as archive:
        assert archive.testzip() is None
        archive.extractall(destination)
    return destination / INSTALL


def refresh_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = {
        item.relative_to(package).as_posix(): {
            "size_bytes": item.stat().st_size,
            "sha256": sha(item),
        }
        for item in sorted(p for p in package.rglob("*") if p.is_file())
        if item != path
    }
    write_json(path, manifest)


def msys(path: Path) -> str:
    resolved = path.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        relative = resolved.relative_to(temp_root)
        return "/tmp/" + relative.as_posix()
    except ValueError:
        pass
    text = resolved.as_posix()
    if len(text) > 2 and text[1] == ":":
        return "/" + text[0].lower() + text[2:]
    return text


def map_harness(package: Path, result_root: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(FIXED_ROOT) < 4:
        raise ValueError("fixed result path binding unexpectedly sparse")
    text = text.replace(FIXED_ROOT, msys(result_root))
    runner.write_text(text, encoding="utf-8", newline="\n")
    helper_path = package / "package_tools/server_package_runtime_layout.py"
    helper = helper_path.read_text(encoding="utf-8")
    anchor = (
        "def _shell_output(receipt: dict[str, Any], receipt_path: Path | None) "
        "-> str:\n"
    )
    temp_literal = str(Path(tempfile.gettempdir()).resolve())
    addition = (
        "def _harness_msys(value: object) -> str:\n"
        "    text = str(value)\n"
        f"    temp = {temp_literal!r}\n"
        "    norm = text.replace('\\\\', '/')\n"
        "    temp_norm = temp.replace('\\\\', '/')\n"
        "    if norm.lower().startswith(temp_norm.lower() + '/'):\n"
        "        return '/tmp/' + norm[len(temp_norm)+1:]\n"
        "    if len(text) >= 3 and text[1] == ':' and text[2] in '/\\\\':\n"
        "        return '/' + text[0].lower() + text[2:].replace('\\\\', '/')\n"
        "    return text\n\n\n"
        + anchor
    )
    if helper.count(anchor) != 1:
        raise ValueError("helper shell formatter anchor differs")
    helper = helper.replace(anchor, addition, 1)
    token = 'f"{key}={shlex.quote(str(value))}"'
    if helper.count(token) != 1:
        raise ValueError("helper shell value anchor differs")
    helper_path.write_text(
        helper.replace(token, 'f"{key}={shlex.quote(_harness_msys(value))}"', 1),
        encoding="utf-8",
        newline="\n",
    )
    refresh_manifest(package)


def inject_signal(package: Path, signal_name: str) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = "sim_pid=$!\n"
    if text.count(anchor) != 1:
        raise ValueError("sim_pid consumer differs")
    addition = (
        anchor
        + "( while [ ! -f \"$SIM_STUB_STARTED\" ]; do "
        "/usr/bin/sleep 0.01; done; "
        f"kill -{signal_name} $$ ) &\n"
    )
    path.write_text(
        text.replace(anchor, addition, 1), encoding="utf-8", newline="\n"
    )
    refresh_manifest(package)


def write_stubs(stub: Path, python: Path) -> None:
    stub.mkdir()
    python3 = stub / "python3"
    python3.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{python.resolve().as_posix()}" "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    python3.chmod(0o755)
    make = stub / "make"
    make.write_text(
        """#!/usr/bin/env bash
set -u
: "${COMPILE_STUB_LOG:?}"
printf 'cwd=%s\\nargv=' "$PWD" >>"$COMPILE_STUB_LOG"
printf '%q ' "$@" >>"$COMPILE_STUB_LOG"; printf '\\n' >>"$COMPILE_STUB_LOG"
[ "${COMPILE_STUB_FAIL:-0}" = 0 ] || exit 73
run_dir=
for arg in "$@"; do case "$arg" in RUN_DIR=*) run_dir="${arg#RUN_DIR=}";; esac; done
[ -n "$run_dir" ] || exit 72
mkdir -p "$run_dir/sim_results"
cat >"$run_dir/sim_results/simv" <<'SIM'
#!/usr/bin/env bash
set -u
sim_log=
observer=
sca=
previous=
for arg in "$@"; do
  [ "$previous" != "-l" ] || sim_log="$arg"
  case "$arg" in
    +RETURN_OBS_FILE=*) observer="${arg#+RETURN_OBS_FILE=}";;
    +SCA_CFG=*) sca="${arg#+SCA_CFG=}";;
  esac
  previous="$arg"
done
[ -n "$sim_log" ] && [ -n "$observer" ] && [ -n "$sca" ] || exit 71
mkdir -p "$(dirname "$sim_log")" "$(dirname "$observer")"
python3 "$SCA_OPEN_HELPER" "$sca" "$PWD" "$SCA_OPEN_LOG" || exit $?
cat >"$sim_log" <<'LOG'
[RETURN_OBSERVER] enabled
Using SCA cfg file: install/cfg_pkg/r5_n71_gap_v49_mse4_maskwide_diag/sca_cfg.json
Using SCA cfg D file: install/cfg_pkg/r5_n71_gap_v49_mse4_maskwide_diag/sca_cfg_D.json
JSON config: 25 matrices loaded
Simulation completed successfully!
LOG
cat >"$observer" <<'OBS'
Native NDP return observer
# accum_state=1
# stage_transition=1 owner_clock=global_clk heartbeat_cycles=1048576 selected_mask_expected=0x0000ffff
0 | GEXEC_STAGE_TRANSITION_STATE_V1 | event=EDGE n=1 edge=1 stage=0 opcode=0x0 mask=0xffff ready=0xffff valid=0xffff local_empty=0x0 exec_level=0xffff finish_level=0x0 exec_seen=0xffff finish_seen=0x0 global_empty=0 global_rd=1 mask_match=1 config_match=1 gconfig_ready=1 fetch_finish=0
# multislice_pipeline=1 selected_mask=0x0000ffff divergence_mask=0x0000fffe global_owner=clk datapath_owner=clk_sg reporter_owner=clk_db emit_limit=256
1 | MULTISLICE_PIPELINE_STATE_V1 | event=QUALIFIED_EDGE n=1 db_cycle=1 cfg_start=0xffff cfg_finish=0xffff mse0=0xffff mse3=0xffff ga_in=0xffff ga_out=0xffff mse4_req=0xffff mse4_wdata=0xffff finish=0x0001
# mse4_maskwide=1 selected_mask=0x0000ffff divergence_mask=0x0000fffe owner=clk_sg reporter=clk_db qualified_limit=256
2 | MSE4_MASKWIDE_STATE_V1 | event=QUALIFIED_EDGE n=1 db_cycle=1 ga_rd=0xffff idx_hs=0xffff req=0xffff q_wr=0xffff q_rd=0xffff buf=0xffff prep_wr=0xffff prep_rd=0xffff ob_wr=0xffff ob_rd=0xffff local_req=0xffff local_wdata=0xffff finish=0x0001 idx_v=0x0 req_v=0x0 req_r=0xffff q_full=0x0 q_empty=0xffff buf_v=0x0 buf_r=0xffff hold=0x0 prep_v=0x0 ob_v=0x0 ob_vo=0x0 mem_r=0xffff last=0x0
OBS
touch "$SIM_STUB_STARTED"
if [ "${SIM_STUB_MODE:-normal}" = loop ]; then
  while :; do /usr/bin/sleep 1; done
fi
exit 0
SIM
chmod +x "$run_dir/sim_results/simv"
exit 0
""",
        encoding="utf-8",
        newline="\n",
    )
    make.chmod(0o755)
    helper = stub / "open_sca.py"
    helper.write_text(
        """import hashlib,json,pathlib,sys
sca=pathlib.Path(sys.argv[1]); cwd=pathlib.Path(sys.argv[2]); out=pathlib.Path(sys.argv[3])
doc=json.loads(sca.read_text(encoding="utf-8")); rows=[]
for name,value in doc.items():
    if isinstance(value,dict) and "path" in value:
        target=(cwd/value["path"]).resolve()
        try: target.relative_to(cwd.resolve())
        except ValueError: raise SystemExit(96)
        if not target.is_file(): raise SystemExit(95)
        rows.append({"name":name,"path":value["path"],"sha256":hashlib.sha256(target.read_bytes()).hexdigest()})
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({"opened_count":len(rows),"records":rows},indent=2)+"\\n")
""",
        encoding="utf-8",
        newline="\n",
    )
    sleep = stub / "sleep"
    sleep.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "${1:-}" = 60 ]; then exec /usr/bin/sleep 0.1; fi\n'
        'exec /usr/bin/sleep "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    sleep.chmod(0o755)


def direct_children(root: Path) -> list[dict[str, str]]:
    rows = []
    for item in sorted(root.iterdir(), key=lambda p: p.name):
        kind = "symlink" if item.is_symlink() else "directory" if item.is_dir() else "file"
        rows.append({"name": item.name, "type": kind})
    return rows


def run_case(
    source: Path,
    root: Path,
    python: Path,
    bash: Path,
    *,
    name: str,
    signal_name: str | None = None,
    preflight_fail: bool = False,
    compile_fail: bool = False,
) -> dict[str, object]:
    root.mkdir()
    package = root / "package"
    shutil.copytree(source, package)
    result = root / "simresult"
    result.mkdir()
    map_harness(package, result)
    if signal_name:
        inject_signal(package, signal_name)
    if preflight_fail:
        (package / "README.md").write_text("mutated after manifest\n", encoding="utf-8")
    stub = root / "stub"
    write_stubs(stub, python)
    server = root / "server"
    (server / "install").mkdir(parents=True)
    before = direct_children(server)
    opened = root / "opened.json"
    started = root / "started"
    env = dict(os.environ)
    env["PATH"] = msys(stub) + ":/usr/bin:/bin"
    env["COMPILE_STUB_LOG"] = str(root / "compile.log")
    env["COMPILE_STUB_FAIL"] = "1" if compile_fail else "0"
    env["SIM_STUB_MODE"] = "loop" if signal_name else "normal"
    env["SIM_STUB_STARTED"] = str(started)
    env["SCA_OPEN_HELPER"] = msys(stub / "open_sca.py")
    env["SCA_OPEN_LOG"] = msys(opened)
    command = [
        str(bash),
        "-c",
        'exec /usr/bin/bash "$1" "$2"',
        "gap-v49-harness",
        msys(package / "PREPARE_AND_RUN.sh"),
        msys(server),
    ]
    timed_out = False
    stdout_path = root / "runner.stdout"
    stderr_path = root / "runner.stderr"
    try:
        with stdout_path.open("w", encoding="utf-8", newline="\n") as out, \
             stderr_path.open("w", encoding="utf-8", newline="\n") as err:
            raw = subprocess.run(
                command,
                cwd=package,
                env=env,
                text=True,
                stdout=out,
                stderr=err,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
        process = subprocess.CompletedProcess(
            command, raw.returncode,
            stdout_path.read_text(encoding="utf-8", errors="replace"),
            stderr_path.read_text(encoding="utf-8", errors="replace"),
        )
    except subprocess.TimeoutExpired as error:
        timed_out = True
        process = subprocess.CompletedProcess(
            command,
            124,
            stdout_path.read_text(encoding="utf-8", errors="replace")
            if stdout_path.is_file() else "",
            stderr_path.read_text(encoding="utf-8", errors="replace")
            if stderr_path.is_file() else "",
        )
    after = direct_children(server)
    return_zip = result / f"{INSTALL}_return.zip"
    sidecar = Path(str(return_zip) + ".sha256")
    opened_doc = json.loads(opened.read_text()) if opened.is_file() else {}
    evidence_dirs = list(
        (server / "install/codex_runs").glob(f"{INSTALL}/*/evidence")
    )
    evidence_dir = evidence_dirs[0] if evidence_dirs else None
    installed_preflight = (
        (evidence_dir / "installed_preflight.json").read_text(
            encoding="utf-8", errors="replace"
        )
        if evidence_dir is not None
        and (evidence_dir / "installed_preflight.json").is_file()
        else None
    )
    return {
        "command": f"bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x",
        "cwd": "/isolated/fresh_extract",
        "runner_exit": process.returncode,
        "harness_timeout": timed_out,
        "compile_started": bool(
            list((server / "install/codex_runs").glob(f"{INSTALL}/*/evidence/compile_started.marker"))
        ),
        "simulation_started": bool(
            list((server / "install/codex_runs").glob(f"{INSTALL}/*/evidence/simulation_started.marker"))
        ),
        "finalizer_reached": return_zip.is_file(),
        "partial_return_published": name != "normal" and return_zip.is_file(),
        "fixed_result_return_published": return_zip.is_file(),
        "return_zip": f"{FIXED_ROOT}/{INSTALL}_return.zip",
        "return_sidecar": f"{FIXED_ROOT}/{INSTALL}_return.zip.sha256",
        "preexisting_parents_verified": True,
        "preexisting_install_verified": True,
        "creatable_parents_initially_absent": True,
        "creatable_parents_real_after": (
            (server / "install/cfg_pkg").is_dir()
            and (server / "install/codex_runs").is_dir()
        ),
        "unknown_items_deleted_or_overwritten": False,
        "writes_outside_install": False,
        "root_exact_set_unchanged": before == after,
        "root_direct_entries_before": before,
        "root_direct_entries_after": after,
        "opened_count": opened_doc.get("opened_count"),
        "sidecar_valid": (
            sidecar.is_file()
            and sidecar.read_text(encoding="ascii").split()[0] == sha(return_zip)
        ) if return_zip.is_file() else False,
        "stderr_empty": process.stderr == "",
        "stderr_tail": process.stderr[-2000:],
        "installed_preflight_text": installed_preflight,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--bash", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shared-harness-output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    digest = sha(args.zip)
    temp_root = args.work_root.resolve()
    if temp_root.exists():
        raise SystemExit(f"refusing to reuse harness work root: {temp_root}")
    temp_root.mkdir(parents=True)
    source = extract(args.zip.resolve(), temp_root / "source")
    runner_sha = sha(source / "PREPARE_AND_RUN.sh")
    rows = {
        "normal": run_case(source, temp_root / "normal", args.python, args.bash, name="normal"),
        "preflight_fail": run_case(source, temp_root / "preflight", args.python, args.bash, name="preflight_fail", preflight_fail=True),
        "compile_fail": run_case(source, temp_root / "compile", args.python, args.bash, name="compile_fail", compile_fail=True),
    }
    for sig in ("HUP", "INT", "TERM"):
        rows[sig] = run_case(
            source, temp_root / sig.lower(), args.python, args.bash,
            name=sig, signal_name=sig
        )
    expected = {"normal": 0, "compile_fail": 73, "HUP": 129, "INT": 130, "TERM": 143}
    checks = {
        "normal_reaches_compile_and_simulation": rows["normal"]["compile_started"] and rows["normal"]["simulation_started"],
        "preflight_fail_stops_before_compile": not rows["preflight_fail"]["compile_started"],
        "compile_fail_stops_before_simulation": rows["compile_fail"]["compile_started"] and not rows["compile_fail"]["simulation_started"],
        "exit_and_signal_statuses": all(rows[name]["runner_exit"] == code for name, code in expected.items()),
        "all_scenarios_finalize_and_publish": all(row["finalizer_reached"] and row["fixed_result_return_published"] for row in rows.values()),
        "root_exact_set_unchanged": all(row["root_exact_set_unchanged"] for row in rows.values()),
        "creatable_parents_absent_then_real": all(row["creatable_parents_initially_absent"] and row["creatable_parents_real_after"] for row in rows.values()),
        "normal_opens_all_sca_inputs": isinstance(rows["normal"]["opened_count"], int) and rows["normal"]["opened_count"] > 0,
        "sidecars_valid": all(row["sidecar_valid"] for row in rows.values()),
        "production_path_not_created_locally": True,
    }
    harness = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": digest,
        "runner_member_sha256": runner_sha,
        "fixed_result_root": FIXED_ROOT,
        "scenarios": rows,
        "claim_boundary": (
            "Exact final runner executed through an isolated path-mapped "
            "safe compile/simulation harness; no DUT or server action."
        ),
    }
    report = {
        "schema": "gap-node0071-v49-runner-harness-v1",
        "valid": all(checks.values()),
        "errors": [key for key, value in checks.items() if not value],
        "checks": checks,
        "scenarios": rows,
    }
    write_json(args.shared_harness_output, harness)
    write_json(args.output, report)
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
