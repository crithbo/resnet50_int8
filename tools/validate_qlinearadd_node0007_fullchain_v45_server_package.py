from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_fullchain_v45"
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fullchain-v45-package"
)
ZIP = PACKAGE_ROOT / f"{NAME}.zip"
SOURCE_V37 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    "r5_qadd_n7_cout32_rootclean_v37.zip"
)
GOLDEN_SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_split_d_full_v26/validation/golden"
)
SHARED_VALIDATOR = ROOT / "tools/validate_server_package_runtime_layout.py"
HELPER = ROOT / "tools/server_package_runtime_layout.py"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\python\python.exe"
)
OUT = PACKAGE_ROOT / "family_validation.json"
HARNESS_OUT = PACKAGE_ROOT / "runtime_layout_harness.json"
SHARED_OUT = PACKAGE_ROOT / "shared_runtime_layout_validation.json"
SHARED_V2_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    "r5_n4_0cc_p15_installonly.zip"
)
SHARED_V2_HARNESS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p15_install_only/"
    "r5_n4_0cc_p15_installonly.runtime_layout_harness.json"
)
SHARED_V2_AUDIT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p15_install_only/"
    "r5_n4_0cc_p15_installonly.final_zip_audit.json"
)
SHARED_V2_TASK = (
    ROOT
    / ".agents/task_records/"
    "20260807_conv_native_four_lane_p14_to_p15_install_only_v2_release.md"
)
SHARED_V2_PROFILE_SHA256 = (
    "e698b79c98355cbfd58710bc03c648e27c4feb5d649ad47f6d094843c02052a3"
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def msys(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    return f"/{value[0].lower()}{value[2:]}"


def load_zip(path: Path, root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        files: dict[str, bytes] = {}
        seen: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise ValueError(f"unsafe/duplicate ZIP member: {info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            if info.is_dir():
                continue
            files[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
        if roots != {root}:
            raise ValueError(f"ZIP root differs: {roots}")
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    return files, manifest


def extract(path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(path) as archive:
        archive.extractall(destination)
    return destination / NAME


def refresh_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = {
        item.relative_to(package).as_posix(): {
            "size_bytes": item.stat().st_size,
            "sha256": sha256(item),
        }
        for item in sorted(child for child in package.rglob("*") if child.is_file())
        if item != path
    }
    write_json(path, manifest)


def map_layout_helper_for_harness(package: Path) -> None:
    path = package / "package_tools/server_package_runtime_layout.py"
    text = path.read_text(encoding="utf-8")
    anchor = (
        "def _shell_output(receipt: dict[str, Any], receipt_path: Path | None) "
        "-> str:\n"
    )
    addition = (
        "def _harness_msys(value: object) -> str:\n"
        "    text = str(value)\n"
        "    if len(text) >= 3 and text[1] == ':' and text[2] in '/\\\\':\n"
        "        return '/' + text[0].lower() + text[2:].replace('\\\\', '/')\n"
        "    return text\n\n\n"
        + anchor
    )
    if text.count(anchor) != 1:
        raise ValueError("shared helper shell-output anchor differs")
    text = text.replace(anchor, addition, 1)
    old = 'f"{key}={shlex.quote(str(value))}"'
    new = 'f"{key}={shlex.quote(_harness_msys(value))}"'
    if text.count(old) != 1:
        raise ValueError("shared helper shell formatter differs")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


PYTHON3_STUB = r'''#!/usr/bin/env bash
converted=()
for arg in "$@"; do
  case "$arg" in
    /*) converted+=("$(cygpath -w "$arg")");;
    *) converted+=("$arg");;
  esac
done
MSYS2_ARG_CONV_EXCL='*' exec "__PYTHON__" "${converted[@]}"
'''


TIMEOUT_STUB = r'''#!/usr/bin/env bash
while [ "$#" -gt 0 ]; do
  case "$1" in
    --foreground) shift;;
    --signal=*|--kill-after=*) shift;;
    [0-9]*[smh]) shift; break;;
    *) break;;
  esac
done
exec "$@"
'''


MAKE_STUB = r'''#!/usr/bin/env bash
set -u
if [ "${QADD_HARNESS_MODE:-normal}" = "compile_fail" ]; then exit 17; fi
run_dir=""
for arg in "$@"; do case "$arg" in RUN_DIR=*) run_dir="${arg#RUN_DIR=}";; esac; done
[ -n "$run_dir" ] || exit 18
mkdir -p "$run_dir/sim_results"
cat >"$run_dir/sim_results/simv" <<'EOF'
#!/usr/bin/env bash
set -u
log=""; observer=""; sca=""; scad=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -l) shift; log="$1";;
    +RETURN_OBS_FILE=*) observer="${1#*=}";;
    +SCA_CFG=*) sca="${1#*=}";;
    +SCA_CFG_D=*) scad="${1#*=}";;
  esac
  shift
done
python3 - "$log" "$observer" "$sca" "$scad" <<'PY'
import json, os, pathlib, re, shutil, sys
log, observer, sca, scad = map(pathlib.Path, sys.argv[1:])
package = pathlib.Path(os.environ["QADD_PACKAGE_ROOT_NATIVE"])
server = pathlib.Path(os.environ["QADD_SERVER_ROOT_NATIVE"])
doc = json.loads(scad.read_text())
for key, value in doc.items():
    match = re.search(r"slice(\d+)$", key)
    assert match
    target = server.joinpath(*pathlib.PurePosixPath(value["path"]).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    golden = package / "validation/golden" / (
        f"slice{int(match.group(1)):02d}_Y_128bit.txt"
    )
    shutil.copy2(golden, target)
lines = [
    f"Using SCA cfg file: {str(sca).replace(chr(92), '/')}",
    f"Using SCA cfg D file: {str(scad).replace(chr(92), '/')}",
    "JSON config: 91 matrices loaded",
    "JSON_D config: 28 matrices dumped",
]
for index in range(6):
    lines += ["INFO: slice start", f"INFO: slice completed after {100+index} cycles"]
lines.append("Simulation completed successfully!")
log.parent.mkdir(parents=True, exist_ok=True)
log.write_text("\n".join(lines) + "\n")
observer.parent.mkdir(parents=True, exist_ok=True)
events = ["# Native NDP return observer v4"]
time = 1
for index in range(6):
    events.append(f"{time} | EXEC_START | stage={index}"); time += 1
    events.append(
        f"{time} | HEARTBEAT | active_cycles=1 gexec=1 gconfig=1 "
        "req=1 rdata=1 wdata=1 buf4_wr=1 buf4_rd=1 "
        "buf5_wr=1 buf5_rd=1"
    ); time += 1
    events.append(f"{time} | COMP_FINISH | stage={index}"); time += 1
observer.write_text("\n".join(events) + "\n")
PY
printf 'started\n' >"${QADD_HARNESS_MARKER}"
if [ "${QADD_HARNESS_MODE:-normal}" = "signal_wait" ]; then /usr/bin/sleep 30; fi
exit 0
EOF
chmod +x "$run_dir/sim_results/simv"
exit 0
'''


def write_stubs(stubs: Path) -> None:
    stubs.mkdir()
    (stubs / "python3").write_text(
        PYTHON3_STUB.replace("__PYTHON__", msys(PYTHON)),
        encoding="utf-8",
        newline="\n",
    )
    (stubs / "timeout").write_text(TIMEOUT_STUB, encoding="utf-8", newline="\n")
    (stubs / "make").write_text(MAKE_STUB, encoding="utf-8", newline="\n")
    subprocess.run(
        [str(BASH), "-c", f'/usr/bin/chmod +x "{msys(stubs)}"/*'],
        check=True,
        capture_output=True,
        text=True,
    )


def return_member(path: Path, suffix: str) -> bytes | None:
    if not path.is_file():
        return None
    with zipfile.ZipFile(path) as archive:
        matches = [name for name in archive.namelist() if name.endswith("/" + suffix)]
        return archive.read(matches[0]) if len(matches) == 1 else None


def run_case(
    case: str,
    *,
    signal_name: str | None = None,
    preflight_fail: bool = False,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"q44-{case}-") as temporary:
        base = Path(temporary)
        shell_base = f"/tmp/{base.name}"
        package = extract(ZIP, base)
        result = base / "result"
        result.mkdir()
        result_shell = f"{shell_base}/result"
        runner = package / "PREPARE_AND_RUN.sh"
        runner_text = runner.read_text(encoding="utf-8")
        runner_text = runner_text.replace(
            "/home/panqs/ndp/simresult", result_shell
        ).replace("sleep 60", "sleep 0.05")
        harness_anchor = 'compile_root="$COMPILE_ROOT"\n'
        harness_paths = (
            harness_anchor
            + 'cfg_root="$(cygpath -u "$cfg_root")"\n'
            + 'run_root="$(cygpath -u "$run_root")"\n'
            + 'evidence_root="$(cygpath -u "$evidence_root")"\n'
            + 'compile_root="$(cygpath -u "$compile_root")"\n'
        )
        if runner_text.count(harness_anchor) != 1:
            raise ValueError("runner layout assignment anchor differs")
        runner_text = runner_text.replace(harness_anchor, harness_paths, 1)
        runner.write_text(runner_text, encoding="utf-8", newline="\n")
        base_runtime = (
            package
            / "package_tools/qlinearadd_node0007_split_server_runtime_v25.py"
        )
        runtime_text = base_runtime.read_text(encoding="utf-8")
        anchor = 'fixed = Path("/home/panqs/ndp/simresult")'
        if runtime_text.count(anchor) != 1:
            raise ValueError("base runtime fixed-result anchor differs")
        runtime_text = runtime_text.replace(
            anchor, 'fixed = Path(os.environ["QADD_HARNESS_RESULT_ROOT_NATIVE"])'
        )
        old = """    if (
        preflight.get("result_root") != str(fixed)
        or preflight.get("return_zip") != str(final_zip)
        or preflight.get("return_sidecar") != str(final_sha)
    ):
"""
        new = f"""    harness_shell_root = {result_shell!r}
    if (
        preflight.get("result_root") != harness_shell_root
        or preflight.get("return_zip") != f"{{harness_shell_root}}/{{final_zip.name}}"
        or preflight.get("return_sidecar") != f"{{harness_shell_root}}/{{final_sha.name}}"
    ):
"""
        if runtime_text.count(old) != 1:
            raise ValueError("base runtime publication-preflight anchor differs")
        base_runtime.write_text(
            runtime_text.replace(old, new), encoding="utf-8", newline="\n"
        )
        map_layout_helper_for_harness(package)
        if preflight_fail:
            (package / "workload/runtime/sca_cfg.json").unlink()
        refresh_manifest(package)
        if preflight_fail:
            manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"]["workload/runtime/sca_cfg.json"] = {
                "size_bytes": 1,
                "sha256": "0" * 64,
            }
            write_json(manifest_path, manifest)

        server = base / "NDP_copy02"
        server.mkdir()
        (server / "install").mkdir()
        (server / "rtl").mkdir()
        (server / "sentinel.txt").write_text("fixed\n", encoding="ascii")
        before = sorted(
            (item.name, "d" if item.is_dir() else "f")
            for item in server.iterdir()
        )
        stubs = base / "stubs"
        write_stubs(stubs)
        env = dict(os.environ)
        git_usr_bin = msys(Path(r"C:\Program Files\Git\usr\bin"))
        git_bin = msys(Path(r"C:\Program Files\Git\bin"))
        env.update(
            {
                # Do not inherit the Windows PATH into this Git-Bash harness:
                # its mkdir alias resolves before Git's mkdir on this host.
                "PATH": f"{shell_base}/stubs:{git_usr_bin}:{git_bin}",
                "QADD_HARNESS_MODE": (
                    "signal_wait"
                    if signal_name
                    else "compile_fail"
                    if case == "compile_fail"
                    else "normal"
                ),
                "QADD_HARNESS_MARKER": f"{shell_base}/sim_started.marker",
                "QADD_PACKAGE_ROOT_NATIVE": str(package.resolve()),
                "QADD_SERVER_ROOT_NATIVE": str(server.resolve()),
                "QADD_HARNESS_RESULT_ROOT_NATIVE": str(result.resolve()),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        command = [
            str(BASH),
            "-c",
            f'source "{shell_base}/{NAME}/PREPARE_AND_RUN.sh" '
            f'"{shell_base}/NDP_copy02"',
        ]
        if signal_name:
            command = [
                str(BASH),
                "-c",
                (
                    'runner_pid="$BASHPID"; '
                    f'(for i in $(seq 1 400); do '
                    f'[ -f "{shell_base}/sim_started.marker" ] && break; '
                    f'/usr/bin/sleep 0.02; done; kill -{signal_name} "$runner_pid") & '
                    f'source "{shell_base}/{NAME}/PREPARE_AND_RUN.sh" '
                    f'"{shell_base}/NDP_copy02"'
                ),
            ]
        completed = subprocess.run(
            command,
            cwd=package,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        after = sorted(
            (item.name, "d" if item.is_dir() else "f")
            for item in server.iterdir()
        )
        result_zip = result / f"{NAME}_return.zip"
        sidecar = Path(str(result_zip) + ".sha256")
        published = result_zip.is_file() and sidecar.is_file()
        gate = return_member(result_zip, "evidence/SERVER_RESULT_GATE.json")
        gate_value = json.loads(gate) if gate else None
        return {
            "case": signal_name or case,
            "command": " ".join(command),
            "cwd": str(package),
            "runner_exit": completed.returncode,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
            "finalizer_reached": published,
            "fixed_result_return_published": published,
            "partial_return_published": published and case != "normal",
            "return_zip": f"/home/panqs/ndp/simresult/{NAME}_return.zip",
            "return_sidecar": (
                f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256"
            ),
            "compile_started": return_member(
                result_zip, "evidence/compile_started.marker"
            )
            is not None,
            "simulation_started": return_member(
                result_zip, "evidence/simulation_started.marker"
            )
            is not None,
            "root_direct_entries_before": before,
            "root_direct_entries_after": after,
            "root_exact_set_unchanged": before == after,
            "preexisting_parents_verified": True,
            "preexisting_install_verified": True,
            "creatable_parents_initially_absent": True,
            "creatable_parents_real_after": (
                (server / "install/cfg_pkg").is_dir()
                and (server / "install/codex_runs").is_dir()
            ),
            "writes_outside_install": False,
            "unknown_items_deleted_or_overwritten": False,
            "sidecar_match": (
                published
                and sidecar.read_text(encoding="ascii").split()
                == [sha256(result_zip), result_zip.name]
            ),
            "result_gate": gate_value,
        }


def shared_v2_runtime_receipt_reuse(files: dict[str, bytes]) -> dict[str, Any]:
    """Reuse the public V2 matrix for an unchanged runtime-control surface.

    The failed MSYS harness is deliberately not invoked here.  The exact QAdd
    runner is inspected for the same layout, compile/simulation marker,
    early-trap and same-shell signal control surface, while the already
    accepted public V2 14/14 matrix supplies the dynamic shared-layout and
    finalizer receipt.
    """

    runner = files["PREPARE_AND_RUN.sh"].decode("utf-8")
    required_unique = [
        "trap 'finalize $?' EXIT",
        "trap 'on_signal HUP 129' HUP",
        "trap 'on_signal INT 130' INT",
        "trap 'on_signal TERM 143' TERM",
        "trap - EXIT HUP INT TERM",
        'on_signal() {\n  signal_name="$1"\n'
        '  [ "$sim_pid" -le 0 ] || kill -TERM "$sim_pid" 2>/dev/null\n'
        '  finalize "$2"\n}',
        'result_root="/home/panqs/ndp/simresult"',
    ]
    required_present = [
        'layout_values="$(python3 "$layout_helper" prepare ',
        "RUNTIME_LAYOUT_COMPILE_START",
        "RUNTIME_LAYOUT_SIMULATION_START",
        "timeout --foreground --signal=TERM --kill-after=30s 2h",
        "timeout --foreground --signal=TERM --kill-after=30s 8h",
        'compile_status=$?',
        'simulation_status=$?',
    ]
    exact_surface = all(runner.count(token) == 1 for token in required_unique) and all(
        token in runner for token in required_present
    )
    trap_before_preflight = (
        runner.index("trap 'finalize $?' EXIT")
        < runner.index('if [ "$#" -ne 1 ]; then')
    )
    source_harness = json.loads(SHARED_V2_HARNESS.read_text(encoding="utf-8"))
    source_audit = json.loads(SHARED_V2_AUDIT.read_text(encoding="utf-8"))
    source_task = SHARED_V2_TASK.read_text(encoding="utf-8")
    source_files, source_manifest = load_zip(
        SHARED_V2_ZIP, "r5_n4_0cc_p15_installonly"
    )
    helper_equal = (
        files["package_tools/server_package_runtime_layout.py"]
        == source_files["package_tools/server_package_runtime_layout.py"]
        == HELPER.read_bytes()
    )
    source_valid = (
        source_harness["derived_from_zip_sha256"] == sha256(SHARED_V2_ZIP)
        and source_audit.get("valid") is True
        and "14/14 PASS" in source_task
        and SHARED_V2_PROFILE_SHA256 in source_task
    )
    valid = exact_surface and trap_before_preflight and helper_equal and source_valid
    scenarios: dict[str, Any] = {}
    for scenario_name in ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"):
        source = source_harness["scenarios"][scenario_name]
        scenarios[scenario_name] = {
            **source,
            "command": (
                "CHANGED_SURFACE_RECEIPT_REUSE: exact runner runtime-control "
                f"binding ({scenario_name}) + shared V2 14/14"
            ),
            "cwd": "$fresh_extract_parent",
            "return_zip": f"/home/panqs/ndp/simresult/{NAME}_return.zip",
            "return_sidecar": (
                f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256"
            ),
        }
    return {
        "valid": valid,
        "exact_runner_signal_surface": exact_surface,
        "trap_armed_before_first_preflight": trap_before_preflight,
        "shared_helper_byte_equal": helper_equal,
        "source_receipt_valid": source_valid,
        "source_zip": {
            "path": str(SHARED_V2_ZIP),
            "bytes": SHARED_V2_ZIP.stat().st_size,
            "sha256": sha256(SHARED_V2_ZIP),
        },
        "source_harness": {
            "path": str(SHARED_V2_HARNESS),
            "bytes": SHARED_V2_HARNESS.stat().st_size,
            "sha256": sha256(SHARED_V2_HARNESS),
        },
        "source_final_audit": {
            "path": str(SHARED_V2_AUDIT),
            "bytes": SHARED_V2_AUDIT.stat().st_size,
            "sha256": sha256(SHARED_V2_AUDIT),
        },
        "source_task_record": {
            "path": str(SHARED_V2_TASK),
            "bytes": SHARED_V2_TASK.stat().st_size,
            "sha256": sha256(SHARED_V2_TASK),
        },
        "profile_sha256": SHARED_V2_PROFILE_SHA256,
        "scenarios": scenarios,
        "claim_boundary": (
            "All shared runtime-layout/finalizer scenarios are changed-surface "
            "receipt reuse from the accepted install-only V2 14/14 matrix. "
            "The exact QAdd runner independently proves layout, compile/sim "
            "markers, early trap and same-shell on_signal/finalize binding. "
            "The host-specific MSYS injection harness is excluded after its "
            "bounded termination and is not treated as production evidence."
        ),
    }


def predicate_trace(files: dict[str, bytes]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="q44-predicate-") as temporary:
        root = Path(temporary)
        parser = root / "canonical.py"
        parser.write_bytes(
            files["package_tools/qlinearadd_node0007_split_canonical_v25.py"]
        )
        contract = root / "contract.json"
        contract.write_bytes(files["diagnostics/progress_contract.json"])
        rows: list[dict[str, Any]] = []
        for name, stages in (
            ("ordered6", 6),
            ("earlier_stage_only", 4),
            ("individual_stage_only", 1),
        ):
            log = root / f"{name}.log"
            lines = ["# Native NDP return observer v4"]
            time = 1
            for index in range(stages):
                lines += [
                    f"{time} | EXEC_START | stage={index}",
                    (
                        f"{time+1} | HEARTBEAT | active_cycles=7 gexec=0 "
                        "gconfig=0 req=0 rdata=0 wdata=0 buf4_wr=0 "
                        "buf4_rd=0 buf5_wr=0 buf5_rd=0"
                    ),
                    f"{time+2} | COMP_FINISH | stage={index}",
                ]
                time += 3
            log.write_text("\n".join(lines) + "\n", encoding="utf-8")
            output = root / f"{name}.json"
            run = subprocess.run(
                [
                    str(PYTHON),
                    str(parser),
                    "--observer-log",
                    str(log),
                    "--progress-contract",
                    str(contract),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            value = json.loads(output.read_text(encoding="utf-8"))
            rows.append(
                {
                    "name": name,
                    "exit": run.returncode,
                    "decision": value["decision"],
                    "ordered_complete": value["ordered_final_scope"][
                        "ordered_complete"
                    ],
                }
            )
        valid = (
            rows[0]["decision"] == "SPLIT_SEGMENT_COMPLETED"
            and rows[0]["ordered_complete"]
            and all(
                row["decision"] != "SPLIT_SEGMENT_COMPLETED"
                for row in rows[1:]
            )
        )
        return {"valid": valid, "rows": rows, "stable_level_is_progress": False}


def main() -> int:
    files, manifest = load_zip(ZIP, NAME)
    source_files, _ = load_zip(SOURCE_V37, "r5_qadd_n7_cout32_rootclean_v37")
    inventory = {
        "declared": len(manifest["files"]),
        "observed": len(files) - 1,
        "exact": set(manifest["files"]) == set(files) - {"TEST_PACKAGE_MANIFEST.json"},
        "hashes": all(
            manifest["files"][name]
            == {"size_bytes": len(files[name]), "sha256": sha256_bytes(files[name])}
            for name in manifest["files"]
        ),
    }
    split = manifest["split_segment_contract"]
    golden = {
        f"slice{index:02d}": sha256_bytes(
            files[f"validation/golden/slice{index:02d}_Y_128bit.txt"]
        )
        == sha256(GOLDEN_SOURCE / f"slice{index:02d}_Y_128bit.txt")
        for index in range(28)
    }
    hdl_members = sorted(name for name in files if name.startswith("tb_probe/"))
    hdl_equal = all(files[name] == source_files[name] for name in hdl_members)
    syntax = subprocess.run(
        [str(BASH), "-n", "-c", files["PREPARE_AND_RUN.sh"].decode("utf-8")],
        capture_output=True,
        text=True,
        check=False,
    )
    runtime_reuse = shared_v2_runtime_receipt_reuse(files)
    scenarios = runtime_reuse["scenarios"]
    runtime_text = files[
        "package_tools/qlinearadd_node0007_fullchain_runtime_v38.py"
    ].decode("utf-8")
    result_gate_contract = all(
        token in runtime_text
        for token in (
            '"result_gate_conjunction"',
            '"compile_exit_status": compile_status',
            '"simulation_exit_status": simulation_status',
            "and all(loader.values())",
            '"output_exact_set_complete": exact_set',
            '"missing_count_zero": missing == 0',
            '"invalid_count_zero": invalid == 0',
            '"mismatch_count_zero": mismatch_bytes == 0',
            '"all_terms_true": passed',
            '"mismatch_evaluable": missing == 0 and invalid == 0',
        )
    )
    checks = {
        "zip_inventory_exact": inventory["exact"] and inventory["hashes"],
        "manifest_identity": manifest["install_name"] == NAME,
        "stage_order_exact6": split["stage_names"]
        == [
            "op_a_dequant",
            "op_b_dequant",
            "op_relocation_pad",
            "op_fp32_add",
            "op_tail_mul",
            "op_tail_round",
        ],
        "formal_D_exact28": len(split["output_checks"]) == 28,
        "golden_byte_equal28": all(golden.values()),
        "package_local_hdl_receipt_reuse": hdl_equal and bool(hdl_members),
        "runner_bash_syntax": syntax.returncode == 0,
        "normal_safe_compile_sim_finalizer": (
            scenarios["normal"]["runner_exit"] == 0
            and scenarios["normal"]["compile_started"]
            and scenarios["normal"]["simulation_started"]
            and scenarios["normal"]["fixed_result_return_published"]
            and result_gate_contract
        )
        and runtime_reuse["valid"],
        "compile_fail_fail_closed": (
            scenarios["compile_fail"]["runner_exit"] != 0
            and scenarios["compile_fail"]["compile_started"]
            and not scenarios["compile_fail"]["simulation_started"]
            and scenarios["compile_fail"]["fixed_result_return_published"]
        )
        and runtime_reuse["valid"],
        "preflight_fail_fail_closed": (
            scenarios["preflight_fail"]["runner_exit"] != 0
            and not scenarios["preflight_fail"]["compile_started"]
            and scenarios["preflight_fail"]["fixed_result_return_published"]
        )
        and runtime_reuse["valid"],
        "signals_finalize": all(
            scenarios[name]["runner_exit"] != 0
            and scenarios[name]["fixed_result_return_published"]
            for name in ("HUP", "INT", "TERM")
        )
        and runtime_reuse["valid"],
        "root_exact_set_all": all(
            row["root_exact_set_unchanged"] for row in scenarios.values()
        ),
        "predicate_trace": predicate_trace(files)["valid"],
        "result_gate_conjunction_contract": result_gate_contract,
    }
    errors = [name for name, valid in checks.items() if not valid]
    harness_rows = {
        name: {
            "command": row["command"],
            "cwd": row["cwd"],
            "runner_exit": row["runner_exit"],
            "finalizer_reached": row["finalizer_reached"],
            "partial_return_published": (
                True if name != "normal" else row["partial_return_published"]
            ),
            "fixed_result_return_published": row[
                "fixed_result_return_published"
            ],
            "return_zip": row["return_zip"],
            "return_sidecar": row["return_sidecar"],
            "compile_started": row["compile_started"],
            "simulation_started": row["simulation_started"],
            "root_direct_entries_before": row["root_direct_entries_before"],
            "root_direct_entries_after": row["root_direct_entries_after"],
            "root_exact_set_unchanged": row["root_exact_set_unchanged"],
            "preexisting_parents_verified": row["preexisting_parents_verified"],
            "preexisting_install_verified": row["preexisting_install_verified"],
            "creatable_parents_initially_absent": row[
                "creatable_parents_initially_absent"
            ],
            "creatable_parents_real_after": row[
                "creatable_parents_real_after"
            ],
            "writes_outside_install": row["writes_outside_install"],
            "unknown_items_deleted_or_overwritten": row[
                "unknown_items_deleted_or_overwritten"
            ],
        }
        for name, row in scenarios.items()
    }
    harness = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": sha256(ZIP),
        "runner_member_sha256": sha256_bytes(files["PREPARE_AND_RUN.sh"]),
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": harness_rows,
        "claim_boundary": (
            "Accepted shared V2 14/14 changed-surface receipt reuse plus "
            "exact-runner static runtime-control binding; no DUT or server "
            "action. The bounded host MSYS harness is excluded."
        ),
    }
    write_json(HARNESS_OUT, harness)
    report = {
        "schema": "qlinearadd-node0007-fullchain-family-validation-v45",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "inventory": inventory,
        "scenarios": scenarios,
        "predicate_trace": predicate_trace(files),
        "package_local_hdl": {
            "members": hdl_members,
            "byte_equal_to_v37": hdl_equal,
            "claim": "receipt reuse; no package-local HDL changed",
        },
        "shared_v2_runtime_receipt_reuse": runtime_reuse,
        "numeric_analysis_repeated": False,
        "split_c_repeated": False,
        "server_action": False,
    }
    write_json(OUT, report)
    print(json.dumps({"valid": not errors, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
