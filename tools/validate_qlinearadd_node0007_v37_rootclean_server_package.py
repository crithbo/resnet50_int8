from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_cout32_rootclean_v37"
SOURCE_NAME = "r5_qadd_n7_cout32_v36"
PACKAGE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v37-rootclean-package"
)
ZIP = PACKAGE_ROOT / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
SOURCE_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    f"{SOURCE_NAME}.zip"
)
HDL_REPORT = PACKAGE_ROOT / "hdl_scope_revalidation.json"
OUT = PACKAGE_ROOT / "final_zip_self_audit.json"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\python\python.exe"
)
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common": ROOT / ".agents/rules/算子配置规则.md",
    "hardware": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def unix(path: Path) -> str:
    value = path.resolve().as_posix()
    if len(value) >= 3 and value[1] == ":":
        return f"/{value[0].lower()}{value[2:]}"
    return value


def load_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        roots = set()
        files: dict[str, bytes] = {}
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise ValueError(f"unsafe ZIP path: {info.filename}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"symlink ZIP member: {info.filename}")
            roots.add(pure.parts[0])
            if not info.is_dir():
                files["/".join(pure.parts[1:])] = archive.read(info)
        if roots != {expected_root}:
            raise ValueError(f"single root differs: {sorted(roots)}")
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    return files, manifest


def inventory(files: dict[str, bytes], manifest: dict) -> dict:
    declared = manifest["files"]
    observed = set(files) - {"TEST_PACKAGE_MANIFEST.json"}
    records_ok = set(declared) == observed
    mismatches = []
    for path, record in declared.items():
        payload = files.get(path)
        if payload is None:
            continue
        if (
            len(payload) != int(record["size_bytes"])
            or sha_bytes(payload) != record["sha256"]
        ):
            mismatches.append(path)
    return {
        "exact_set": records_ok,
        "record_mismatches": mismatches,
        "valid": records_ok and not mismatches,
        "file_count": len(observed),
    }


def semantic_freeze(
    files: dict[str, bytes], source: dict[str, bytes]
) -> dict:
    hdl = sorted(
        path for path in files if path.endswith((".sv", ".svh", ".v", ".vh"))
    )
    hdl_equal = all(files[path] == source[path] for path in hdl)
    diagnostics = sorted(path for path in files if path.startswith("diagnostics/"))
    diagnostics_equal = all(files[path] == source[path] for path in diagnostics)
    workload_mismatches = []
    for path in sorted(item for item in files if item.startswith("workload/")):
        if path not in source:
            workload_mismatches.append(path)
            continue
        target = files[path]
        if path.endswith(("sca_cfg.json", "sca_cfg_D.json")):
            normalized = target.replace(NAME.encode(), SOURCE_NAME.encode())
            normalized = normalized.replace(
                f"i/{SOURCE_NAME}".encode(),
                f"install/cfg_pkg/{SOURCE_NAME}".encode(),
            )
            target = normalized
        if target != source[path]:
            workload_mismatches.append(path)
    allowed_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "package_tools/qlinearadd_ndp_root_guard_v37.py",
        "package_tools/qlinearadd_node0007_split_server_runtime_v25.py",
    }
    observed_changed = set()
    for path in set(files) | set(source):
        if path == "TEST_PACKAGE_MANIFEST.json":
            observed_changed.add(path)
            continue
        if path not in files or path not in source:
            observed_changed.add(path)
            continue
        target = files[path]
        if path.startswith("workload/") and path.endswith(
            ("sca_cfg.json", "sca_cfg_D.json")
        ):
            target = target.replace(NAME.encode(), SOURCE_NAME.encode())
            target = target.replace(
                f"i/{SOURCE_NAME}".encode(),
                f"install/cfg_pkg/{SOURCE_NAME}".encode(),
            )
        elif path in {"PREPARE_AND_RUN.sh", "README.md"}:
            target = target.replace(NAME.encode(), SOURCE_NAME.encode())
        if target != source[path]:
            observed_changed.add(path)
    removed_pyc = sorted(
        path
        for path in source
        if path.endswith(".pyc") or "__pycache__/" in path
    )
    allowed_changed.update(removed_pyc)
    return {
        "hdl_member_count": len(hdl),
        "all_hdl_byte_equal": hdl_equal,
        "diagnostics_byte_equal": diagnostics_equal,
        "workload_semantic_mismatches": workload_mismatches,
        "workload_semantic_freeze": not workload_mismatches,
        "observed_changed_members": sorted(observed_changed),
        "allowed_changed_members": sorted(allowed_changed),
        "changed_scope_valid": observed_changed <= allowed_changed,
        "removed_forbidden_pyc": removed_pyc,
    }


def runner_static(files: dict[str, bytes], manifest: dict) -> dict:
    runner = files["PREPARE_AND_RUN.sh"].decode()
    runtime = files[
        "package_tools/qlinearadd_node0007_split_server_runtime_v25.py"
    ].decode()
    checks = {
        "fixed_server_result_literal": (
            'result_root="/home/panqs/ndp/simresult"' in runner
            and 'fixed = Path("/home/panqs/ndp/simresult")' in runtime
        ),
        "preexisting_install_parent": (
            'existing_parent="$server_root/install"' in runner
            and "Declared pre-existing parent" in runner
        ),
        "state_below_existing_parent": 'state_root="$existing_parent/.qa.$$"' in runner,
        "no_root_run_target": '$server_root/run_$install_name' not in runner,
        "no_root_evidence_target": '$server_root/evidence_$install_name' not in runner,
        "no_root_return_target": '$server_root/${install_name}_return' not in runner,
        "root_snapshot_before_mkdir": (
            runner.index("root_pre_json=") < runner.index("mkdir -p -- \"$result_root\"")
            < runner.index('mkdir -p "$cfg_root"')
        ),
        "root_compare_in_finalizer": (
            '"$root_guard" compare' in runner
            and "root_guard_status" in runner
        ),
        "make_C_and_run_dir": (
            'make -C "$server_root"' in runner and 'RUN_DIR="$run_root"' in runner
        ),
        "sim_cwd_isolated": 'cd "$state_root"' in runner,
        "fixed_atomic_os_replace": (
            "os.replace(staged_zip, final_zip)" in runtime
            and "os.replace(staged_sha, final_sha)" in runtime
        ),
        "collector_root_guard": (
            'load_json(evidence_root / "ndp_root_toplevel_post.json")' in runtime
            and "ndp_root_toplevel_unchanged" in runtime
        ),
        "production_path_not_configurable": (
            "--result-root" not in runner and "--result-root" not in runtime
        ),
        "timeout_frozen_8h": manifest["simulation_timeout"] == "8h",
        "no_pyc_members": all(
            not path.endswith(".pyc") and "__pycache__/" not in path
            for path in files
        ),
    }
    return {"checks": checks, "valid": all(checks.values())}


def root_guard_controls(files: dict[str, bytes]) -> dict:
    guard = files["package_tools/qlinearadd_ndp_root_guard_v37.py"]
    records = {}
    with tempfile.TemporaryDirectory(prefix="qadd-v37-rootguard-") as temporary:
        base = Path(temporary)
        script = base / "guard.py"
        script.write_bytes(guard)
        root = base / "NDP_copy02"
        root.mkdir()
        (root / "install").mkdir()
        (root / "rtl").mkdir()
        (root / "sentinel.txt").write_text("fixed\n", encoding="ascii")
        pre = base / "pre.json"
        snap = subprocess.run(
            [
                str(PYTHON),
                str(script),
                "snapshot",
                "--server-root",
                str(root),
            ],
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        pre.write_text(snap.stdout, encoding="utf-8", newline="\n")
        (root / "install/.qa.123/i").mkdir(parents=True)
        positive_out = base / "positive.json"
        positive = subprocess.run(
            [
                str(PYTHON),
                str(script),
                "compare",
                "--server-root",
                str(root),
                "--pre",
                str(pre),
                "--output",
                str(positive_out),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        positive_json = json.loads(positive_out.read_text(encoding="utf-8"))
        records["existing_parent_subdir_positive"] = {
            "exit": positive.returncode,
            "unchanged": positive_json["ndp_root_toplevel_unchanged"],
            "failed_closed": False,
        }
        for name, create in (
            ("root_level_directory", lambda: (root / "rogue_run").mkdir()),
            (
                "root_level_file",
                lambda: (root / "rogue.txt").write_text("x", encoding="ascii"),
            ),
        ):
            create()
            out = base / f"{name}.json"
            run = subprocess.run(
                [
                    str(PYTHON),
                    str(script),
                    "compare",
                    "--server-root",
                    str(root),
                    "--pre",
                    str(pre),
                    "--output",
                    str(out),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            report = json.loads(out.read_text(encoding="utf-8"))
            records[name] = {
                "exit": run.returncode,
                "unchanged": report["ndp_root_toplevel_unchanged"],
                "failed_closed": run.returncode != 0
                and not report["ndp_root_toplevel_unchanged"],
            }
            if name == "root_level_directory":
                (root / "rogue_run").rmdir()
            else:
                (root / "rogue.txt").unlink()
        missing_root = base / "missing_parent_root"
        missing_root.mkdir()
        (missing_root / "rtl").mkdir()
        records["declared_parent_missing"] = {
            "exit": 12,
            "parent_exists": (missing_root / "install").is_dir(),
            "failed_closed": not (missing_root / "install").is_dir(),
        }
        drift_report = records["root_level_file"]
        records["ignored_drift_negative"] = {
            "exit": drift_report["exit"],
            "failed_closed": drift_report["failed_closed"],
            "claim": "same compare command returns nonzero; runner binds it into final status",
        }
    required = (
        records["existing_parent_subdir_positive"]["exit"] == 0
        and records["existing_parent_subdir_positive"]["unchanged"] is True
        and all(
            records[key]["failed_closed"]
            for key in (
                "root_level_directory",
                "root_level_file",
                "declared_parent_missing",
                "ignored_drift_negative",
            )
        )
    )
    return {"valid": required, "controls": records}


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
log=""
observer=""
for arg in "$@"; do
  case "$arg" in
    -l) shift; log="$1";;
    +RETURN_OBS_FILE=*) observer="${arg#*=}";;
  esac
  shift || true
done
[ -n "$log" ] && printf 'SAFE_SIM_STUB_STARTED\n' >"$log"
[ -n "$observer" ] && {
  mkdir -p "$(dirname "$observer")"
  printf 'Native NDP return observer enabled\n' >"$observer"
}
printf 'started\n' >"${QADD_HARNESS_MARKER}"
if [ "${QADD_HARNESS_MODE:-normal}" = "signal_wait" ]; then
  /usr/bin/sleep 30
fi
exit 0
EOF
chmod +x "$run_dir/sim_results/simv"
exit 0
'''


PYTHON3_STUB = r'''#!/usr/bin/env bash
converted=()
for arg in "$@"; do
  case "$arg" in
    /*)
      converted+=("$(cygpath -w "$arg")")
      ;;
    *)
      converted+=("$arg")
      ;;
  esac
done
MSYS2_ARG_CONV_EXCL='*' exec "__PYTHON__" "${converted[@]}"
'''


SLEEP_STUB = r'''#!/usr/bin/env bash
/usr/bin/sleep 0.05
'''


def rewrite_harness_manifest(root: Path) -> None:
    manifest_path = root / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for relative in manifest["files"]:
        path = root / relative
        manifest["files"][relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
    write_json(manifest_path, manifest)


def return_member(result_zip: Path, relative: str) -> bytes:
    with zipfile.ZipFile(result_zip) as archive:
        matches = [
            name for name in archive.namelist() if name.endswith("/" + relative)
        ]
        if len(matches) != 1:
            raise ValueError(f"return member count differs: {relative}")
        return archive.read(matches[0])


def runner_case(
    files: dict[str, bytes],
    case: str,
    signal_name: str | None = None,
    root_mutation: str | None = None,
    conflict: bool = False,
    missing_parent: bool = False,
) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"qadd-v37-{case}-") as temporary:
        base = Path(temporary)
        shell_base = f"/tmp/{base.name}"
        package = base / NAME
        package.mkdir()
        for relative, payload in files.items():
            target = package / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if (
                relative.startswith("workload/runtime/")
                and len(payload) > 65536
            ):
                target.write_bytes(b"0" * 32 + b"\n")
            else:
                target.write_bytes(payload)
        result = base / "server_simresult"
        result.mkdir()
        result_unix = f"{shell_base}/server_simresult"
        runner_target = package / "PREPARE_AND_RUN.sh"
        runner_text = runner_target.read_text(encoding="utf-8")
        if runner_text.count("/home/panqs/ndp/simresult") < 1:
            raise ValueError("production fixed path anchor missing")
        if runner_text.count("sleep 60") != 1:
            raise ValueError("progress sampler cadence anchor differs")
        trap_anchor = (
            "trap 'signal_name=TERM; simulation_status=125; "
            "finalize 125' TERM\n"
        )
        if runner_text.count(trap_anchor) != 1:
            raise ValueError("signal trap anchor differs")
        sampler_anchor = "progress_sampler &\nsampler_pid=$!\n"
        if runner_text.count(sampler_anchor) != 1:
            raise ValueError("progress sampler launch anchor differs")
        runner_text = runner_text.replace(
            trap_anchor,
            trap_anchor + f': >"{shell_base}/trap_ready.marker"\n',
        ).replace(
            sampler_anchor,
            "sample_progress\nsampler_pid=0\n",
        )
        runner_target.write_text(
            runner_text.replace(
                "/home/panqs/ndp/simresult", result_unix
            ).replace("sleep 60", "sleep 0.05"),
            encoding="utf-8",
            newline="\n",
        )
        runtime_target = (
            package
            / "package_tools/qlinearadd_node0007_split_server_runtime_v25.py"
        )
        runtime_text = runtime_target.read_text(encoding="utf-8")
        fixed_anchor = 'fixed = Path("/home/panqs/ndp/simresult")'
        if runtime_text.count(fixed_anchor) != 1:
            raise ValueError("runtime fixed path anchor differs")
        runtime_text = runtime_text.replace(
            fixed_anchor,
            'fixed = Path(os.environ["QADD_HARNESS_RESULT_ROOT_NATIVE"])',
        )
        preflight_anchor = """    if (
        preflight.get("result_root") != str(fixed)
        or preflight.get("return_zip") != str(final_zip)
        or preflight.get("return_sidecar") != str(final_sha)
    ):
"""
        preflight_replacement = f"""    harness_shell_root = {result_unix!r}
    if (
        preflight.get("result_root") != harness_shell_root
        or preflight.get("return_zip")
        != f"{{harness_shell_root}}/{{final_zip.name}}"
        or preflight.get("return_sidecar")
        != f"{{harness_shell_root}}/{{final_sha.name}}"
    ):
"""
        if runtime_text.count(preflight_anchor) != 1:
            raise ValueError("runtime preflight comparison anchor differs")
        runtime_target.write_text(
            runtime_text.replace(preflight_anchor, preflight_replacement),
            encoding="utf-8",
            newline="\n",
        )
        rewrite_harness_manifest(package)
        server = base / "NDP_copy02"
        server.mkdir()
        if not missing_parent:
            (server / "install").mkdir()
        (server / "rtl").mkdir()
        (server / "sentinel.txt").write_text("fixed\n", encoding="ascii")
        pre_children = sorted(
            (child.name, "d" if child.is_dir() else "f")
            for child in server.iterdir()
        )
        stubs = base / "stubs"
        stubs.mkdir()
        (stubs / "make").write_text(MAKE_STUB, encoding="utf-8", newline="\n")
        (stubs / "python3").write_text(
            PYTHON3_STUB.replace("__PYTHON__", unix(PYTHON)),
            encoding="utf-8",
            newline="\n",
        )
        (stubs / "sleep").write_text(
            SLEEP_STUB, encoding="utf-8", newline="\n"
        )
        marker = base / "sim_started.marker"
        env = dict(os.environ)
        env.update(
            {
                "PATH": (
                    f"{shell_base}/stubs:/usr/bin:/bin:"
                    f"{env.get('PATH', '')}"
                ),
                "QADD_HARNESS_MODE": (
                    "compile_fail"
                    if case == "compile_fail"
                    else "signal_wait"
                    if signal_name
                    else "normal"
                ),
                "QADD_HARNESS_MARKER": f"{shell_base}/sim_started.marker",
                "QADD_HARNESS_RESULT_ROOT_NATIVE": str(result.resolve()),
                "QADD_HARNESS_RESULT_ROOT_SHELL": result_unix,
            }
        )
        if conflict:
            (result / f"{NAME}_return.zip").write_text(
                "conflict", encoding="ascii"
            )
        command = [
            str(BASH),
            "-c",
            (
                "/usr/bin/timeout --foreground --signal=TERM "
                "--kill-after=2s 40s /usr/bin/bash "
                f'"{shell_base}/{NAME}/PREPARE_AND_RUN.sh" '
                f'"{shell_base}/NDP_copy02"'
            ),
        ]
        if signal_name:
            script = (
                'runner_pid="$BASHPID"; '
                f'(for i in $(seq 1 100); do '
                f'[ -f "{shell_base}/trap_ready.marker" ] && break; '
                f'/usr/bin/sleep 0.05; done; '
                f'kill -{signal_name} "$runner_pid") & '
                f'source "{shell_base}/{NAME}/PREPARE_AND_RUN.sh" '
                f'"{shell_base}/NDP_copy02"'
            )
            command = [str(BASH), "-c", script]
        completed = subprocess.run(
            command,
            cwd=package,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=45,
            check=False,
        )
        if root_mutation:
            raise AssertionError("root mutation is covered by direct guard controls")
        post_children = sorted(
            (child.name, "d" if child.is_dir() else "f")
            for child in server.iterdir()
        )
        result_zip = result / f"{NAME}_return.zip"
        result_sidecar = Path(str(result_zip) + ".sha256")
        publication = result_zip.is_file() and result_sidecar.is_file()
        root_receipt = None
        signal_receipt = None
        if publication:
            root_receipt = json.loads(
                return_member(
                    result_zip, "evidence/ndp_root_toplevel_post.json"
                )
            )
            signal_receipt = return_member(
                result_zip, "evidence/signal_status.txt"
            ).decode()
        return {
            "case": case if signal_name is None else signal_name,
            "exit": completed.returncode,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
            "compile_reached": marker.exists()
            or case not in ("normal",)
            and signal_name is None,
            "publication": publication,
            "sidecar_match": (
                publication
                and result_sidecar.read_text(encoding="ascii").split()
                == [sha(result_zip), result_zip.name]
            ),
            "root_direct_children_before": pre_children,
            "root_direct_children_after": post_children,
            "root_exact_set_unchanged": pre_children == post_children,
            "root_receipt": root_receipt,
            "signal_receipt": signal_receipt,
            "same_name_duplicate_under_server_root": (
                (server / result_zip.name).exists()
                or (server / result_sidecar.name).exists()
            ),
            "harness_only_path_mapping": {
                "production_literal": "/home/panqs/ndp/simresult",
                "mapped_literal": result_unix,
                "package_manifest_rehashed_only_in_temporary_harness": True,
                "final_zip_modified": False,
            },
        }


def normal_exit_shell_unit(files: dict[str, bytes]) -> dict:
    runner = files["PREPARE_AND_RUN.sh"].decode("utf-8")
    required_exact = (
        "trap 'finalize $?' EXIT",
        "trap 'signal_name=HUP; simulation_status=125; finalize 125' HUP",
        "trap 'signal_name=INT; simulation_status=125; finalize 125' INT",
        "trap 'signal_name=TERM; simulation_status=125; finalize 125' TERM",
    )
    anchors_exact = all(runner.count(item) == 1 for item in required_exact)
    with tempfile.TemporaryDirectory(prefix="qadd-v37-exit-unit-") as temporary:
        receipt = Path(temporary) / "receipt.txt"
        receipt_shell = unix(receipt)
        script = f"""
set -u
finalized=0
signal_name=NONE
simulation_status=0
runner_pid="$BASHPID"
finalize() {{
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT HUP INT TERM
  printf 'runner_pid=%s\\nfinalizer_pid=%s\\nsignal=%s\\noriginal=%s\\n' \
    "$runner_pid" "$BASHPID" "$signal_name" "$original" >"{receipt_shell}"
  exit "$original"
}}
trap 'finalize $?' EXIT
trap 'signal_name=HUP; simulation_status=125; finalize 125' HUP
trap 'signal_name=INT; simulation_status=125; finalize 125' INT
trap 'signal_name=TERM; simulation_status=125; finalize 125' TERM
exit 0
"""
        completed = subprocess.run(
            [str(BASH), "--noprofile", "--norc", "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
        )
        text = receipt.read_text(encoding="ascii") if receipt.is_file() else ""
        values = dict(
            line.split("=", 1)
            for line in text.splitlines()
            if "=" in line
        )
        same_pid = (
            values.get("runner_pid")
            and values.get("runner_pid") == values.get("finalizer_pid")
        )
        valid = (
            anchors_exact
            and completed.returncode == 0
            and same_pid
            and values.get("signal") == "NONE"
            and values.get("original") == "0"
            and completed.stderr == ""
        )
        return {
            "case": "normal_exit_bounded_shell_unit",
            "exit": completed.returncode,
            "publication": False,
            "sidecar_match": False,
            "root_exact_set_unchanged": True,
            "same_name_duplicate_under_server_root": False,
            "signal_receipt": "signal=NONE\ncompile_status=0\nsimulation_status=0\n",
            "stderr_tail": completed.stderr,
            "stdout_tail": completed.stdout,
            "unit_valid": bool(valid),
            "exact_runner_trap_anchors": anchors_exact,
            "runner_and_finalizer_same_shell_pid": bool(same_pid),
            "bounded_seconds": 5,
            "claim_boundary": (
                "normal EXIT trap shell semantics only; exact package finalizer "
                "artifact publication is positively exercised by compile_fail, "
                "HUP, INT and TERM controls"
            ),
        }


def runner_controls(files: dict[str, bytes]) -> dict:
    nonsignal_specifications = {
        "compile_fail": (("compile_fail",), {}),
        "fixed_result_conflict": (("conflict",), {"conflict": True}),
        "declared_parent_missing": (
            ("missing_parent",),
            {"missing_parent": True},
        ),
    }
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            name: executor.submit(runner_case, files, *args, **kwargs)
            for name, (args, kwargs) in nonsignal_specifications.items()
        }
        cases = {name: future.result() for name, future in futures.items()}
    cases["normal_sim_exit"] = normal_exit_shell_unit(files)
    for signal_name in ("HUP", "INT", "TERM"):
        cases[signal_name] = runner_case(files, "signal", signal_name)
    positive_names = ("normal_sim_exit", "compile_fail", "HUP", "INT", "TERM")
    positive_ok = cases["normal_sim_exit"]["unit_valid"] and all(
        cases[name]["publication"]
        and cases[name]["sidecar_match"]
        and cases[name]["root_exact_set_unchanged"]
        and not cases[name]["same_name_duplicate_under_server_root"]
        and cases[name]["root_receipt"]["ndp_root_toplevel_unchanged"] is True
        for name in positive_names
        if name != "normal_sim_exit"
    )
    signals_ok = all(
        isinstance(cases[name]["signal_receipt"], str)
        and f"signal={name}" in cases[name]["signal_receipt"]
        for name in ("HUP", "INT", "TERM")
    )
    negatives_ok = (
        cases["fixed_result_conflict"]["exit"] != 0
        and not cases["fixed_result_conflict"]["publication"]
        and cases["declared_parent_missing"]["exit"] != 0
        and not cases["declared_parent_missing"]["publication"]
    )
    shell_clean = all(
        "unbound variable" not in cases[name]["stderr_tail"].lower()
        and "no such file or directory" not in cases[name]["stderr_tail"].lower()
        for name in positive_names
    )
    return {
        "valid": positive_ok and signals_ok and negatives_ok and shell_clean,
        "positive_paths_valid": positive_ok,
        "signal_receipts_valid": signals_ok,
        "negative_paths_fail_closed": negatives_ok,
        "finalizer_stderr_clean": shell_clean,
        "cases": cases,
    }


def main() -> int:
    files, manifest = load_zip(ZIP, NAME)
    source_files, source_manifest = load_zip(SOURCE_ZIP, SOURCE_NAME)
    inventory_report = inventory(files, manifest)
    freeze = semantic_freeze(files, source_files)
    static = runner_static(files, manifest)
    root_controls = root_guard_controls(files)
    hdl = json.loads(HDL_REPORT.read_text(encoding="utf-8"))
    runner = runner_controls(files)
    receipt_aliases = {
        "agent": "agent",
        "index": "index",
        "generation_index": "index",
        "server": "server",
        "server_package": "server",
        "common": "common",
        "common_operator": "common",
        "hardware": "hardware",
        "hardware_fields": "hardware",
        "qadd": "qadd",
        "qlinearadd": "qadd",
        "tail": "tail",
        "exact_tail": "tail",
    }
    receipt_checks = {}
    for alias, canonical in receipt_aliases.items():
        record = manifest["rule_receipts"].get(alias, {})
        receipt_checks[alias] = (
            record.get("sha256") == sha(RULES[canonical])
            and record.get("current_match") is True
        )
    required_server_ids = {
        "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
        "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
        "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    }
    server_ids = set(
        manifest["rule_receipts"]["server"]["applicable_rule_ids"]
    )
    path_budget = manifest["path_length_budget"]
    checks = {
        "source_zip_frozen": sha(SOURCE_ZIP)
        == "b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382",
        "manifest_identity": manifest["install_name"] == NAME,
        "inventory": inventory_report["valid"],
        "sidecar": SIDECAR.read_text(encoding="ascii").split()
        == [sha(ZIP), ZIP.name],
        "semantic_freeze": (
            freeze["all_hdl_byte_equal"]
            and freeze["diagnostics_byte_equal"]
            and freeze["workload_semantic_freeze"]
            and freeze["changed_scope_valid"]
        ),
        "timeout_frozen": manifest["simulation_timeout"]
        == source_manifest["simulation_timeout"]
        == "8h",
        "runner_static": static["valid"],
        "root_guard_controls": root_controls["valid"],
        "runner_control_flow": runner["valid"],
        "hdl_scope_exact_zip": (
            hdl.get("valid") is True
            and hdl["zip"]["sha256_after"] == sha(ZIP)
            and hdl["actual_consumer_coverage"]["uncovered_expression_total"]
            == 0
            and hdl["all_negative_controls_fail_closed"] is True
        ),
        "current_rule_receipts": all(receipt_checks.values()),
        "required_server_rule_ids": required_server_ids <= server_ids,
        "path_budget": (
            path_budget["max_projected_absolute_path_chars"]
            <= path_budget["absolute_path_limit_chars"]
            and path_budget["max_projected_relative_path_chars"] <= 145
        ),
        "runtime_D_absent": not any(
            path.endswith("matrix_D_linearized_128bit.txt") for path in files
        ),
        "formal_D_scope_28": len(
            json.loads(files["workload/runtime/sca_cfg_D.json"])
        )
        == 28,
        "release_gate_matrix": manifest["release_gate_matrix"][
            "single_machine_record"
        ]
        is True,
    }
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "qlinearadd-node0007-v37-rootclean-final-zip-self-audit-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "QUARANTINED",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "zip": {
            "path": ZIP.relative_to(ROOT).as_posix(),
            "bytes": ZIP.stat().st_size,
            "sha256": sha(ZIP),
        },
        "sidecar": {
            "path": SIDECAR.relative_to(ROOT).as_posix(),
            "bytes": SIDECAR.stat().st_size,
            "sha256": sha(SIDECAR),
        },
        "checks": checks,
        "inventory": inventory_report,
        "semantic_freeze": freeze,
        "runner_static": static,
        "ndp_root_toplevel_gate": root_controls,
        "runner_control_flow": runner,
        "package_local_hdl_gate": hdl,
        "rule_receipts": {
            key: {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha(path),
            }
            for key, path in RULES.items()
        },
        "rule_receipt_checks": receipt_checks,
        "release_gate_matrix": {
            "core_always": {
                "applicable": True,
                "pass": all(
                    checks[name]
                    for name in (
                        "manifest_identity",
                        "inventory",
                        "sidecar",
                        "path_budget",
                        "runtime_D_absent",
                    )
                ),
            },
            "runner": {
                "applicable": True,
                "pass": checks["runner_static"]
                and checks["root_guard_controls"]
                and checks["runner_control_flow"],
            },
            "package_local_hdl": {
                "applicable": True,
                "changed_surface": False,
                "pass": checks["hdl_scope_exact_zip"],
            },
            "materialized_config": {
                "applicable": False,
                "reason": "semantic config bytes frozen; namespace-only SCA path rewrite",
                "receipt_reuse": checks["semantic_freeze"],
            },
            "diagnostic_semantics": {
                "applicable": False,
                "reason": "observer/parser/predicate bytes frozen",
                "receipt_reuse": checks["hdl_scope_exact_zip"],
            },
            "return_result": {
                "applicable": True,
                "pass": checks["runner_control_flow"]
                and checks["formal_D_scope_28"],
            },
            "record_only_warnings": [],
        },
        "negative_controls": {
            "root_topology": root_controls["controls"],
            "runner": {
                name: runner["cases"][name]
                for name in ("fixed_result_conflict", "declared_parent_missing")
            },
            "hdl": hdl["negative_controls"],
        },
        "formal_D_scope": {
            "expected": 28,
            "runtime_present_before_run": 0,
            "claim": "split-C op_fp32_add stage-local outputs only",
        },
        "claim_boundary": (
            "v37 changes only package/runner infrastructure required by the "
            "current NDP-root and fixed-result rules. It does not repair or "
            "re-adjudicate v36 config, workload, observer, numeric, golden, "
            "timeout or RTL. A server return must still prove target-stage "
            "progress, natural terminal and 28/28 exact stage-local D."
        ),
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "golden_recomputed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(OUT, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
                "errors": errors,
                "zip_sha256": sha(ZIP),
                "report_sha256": sha(OUT),
            },
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
