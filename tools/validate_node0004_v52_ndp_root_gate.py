from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v51_runner_controls as v51


base = v51.base
INSTALL_NAME = "r5_n4_hw_v52_ndproot_gate"
FIXED_ROOT = "/home/panqs/ndp/simresult"


def direct_children(root: Path) -> list[dict[str, str]]:
    result = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if child.is_symlink():
            kind = "symlink"
        elif child.is_dir():
            kind = "directory"
        elif child.is_file():
            kind = "file"
        else:
            kind = "other"
        result.append({"name": child.name, "type": kind})
    return result


def write_stubs(stub_root: Path, python: Path) -> None:
    v51.write_stubs(stub_root, python)
    make = stub_root / "make"
    text = make.read_text(encoding="utf-8")
    text = text.replace(
        ': "${COMPILE_STUB_LOG:?}"\n',
        ': "${COMPILE_STUB_LOG:?}"\n'
        'case "${ROOT_MUTATION_KIND:-none}" in\n'
        '  directory) mkdir -p "$PWD/negative_root_directory"; '
        'printf "negative\\n" > '
        '"$PWD/negative_root_directory/marker";;\n'
        '  file) printf "negative\\n" > "$PWD/negative_root_file";;\n'
        '  none) :;;\n'
        '  *) exit 98;;\n'
        'esac\n'
        '[ "${COMPILE_STUB_FAIL:-0}" = 0 ] || exit 73\n',
        1,
    )
    text = text.replace(
        'if [ "$SIM_STUB_MODE" = "exit" ]; then exit 74; fi\n',
        'if [ "$SIM_STUB_MODE" = "normal" ]; then exit 0; fi\n'
        'if [ "$SIM_STUB_MODE" = "exit" ]; then exit 74; fi\n',
        1,
    )
    make.write_text(text, encoding="utf-8", newline="\n")
    sleep = stub_root / "sleep"
    sleep.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "${1:-}" = "60" ]; then exec /usr/bin/sleep 0.1; fi\n'
        'exec /usr/bin/sleep "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    sleep.chmod(0o755)


def map_harness(package: Path, result_root: Path) -> None:
    old = v51.INSTALL_NAME
    try:
        v51.INSTALL_NAME = INSTALL_NAME
        v51.map_harness(package, result_root)
    finally:
        v51.INSTALL_NAME = old
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    temp_root = Path(tempfile.gettempdir()).resolve()
    relative = result_root.resolve().relative_to(temp_root)
    bash_result_root = "/tmp/" + relative.as_posix()
    native_result_root = result_root.resolve().as_posix()
    runner = runner.replace(
        f'"result_root": "{bash_result_root}"',
        f'"result_root": "{native_result_root}"',
    ).replace(
        f'"return_zip": "{bash_result_root}/${{install_name}}_return.zip"',
        f'"return_zip": "{native_result_root}/${{install_name}}_return.zip"',
    ).replace(
        f'"return_sidecar": "{bash_result_root}/${{install_name}}_return.zip.sha256"',
        f'"return_sidecar": "{native_result_root}/${{install_name}}_return.zip.sha256"',
    )
    runner_path.write_text(runner, encoding="utf-8", newline="\n")


def returned_gate(return_zip: Path) -> dict[str, Any]:
    if not return_zip.is_file():
        return {}
    with zipfile.ZipFile(return_zip) as archive:
        roots = {Path(info.filename).parts[0] for info in archive.infolist()}
        if roots != {f"{INSTALL_NAME}_return"}:
            return {"root_error": sorted(roots)}
        prefix = f"{INSTALL_NAME}_return/"
        names = {
            info.filename[len(prefix) :]: info
            for info in archive.infolist()
            if not info.is_dir() and info.filename.startswith(prefix)
        }
        required = (
            "evidence/ndp_root_toplevel_pre.json",
            "evidence/ndp_root_toplevel_post.json",
            "evidence/ndp_root_write_contract.json",
            "evidence/ndp_root_toplevel_gate.json",
            "RETURN_MANIFEST.json",
        )
        if any(name not in names for name in required):
            return {"missing": [name for name in required if name not in names]}
        result = {
            name: json.loads(archive.read(names[name]))
            for name in required
            if name.endswith(".json")
        }
        return result


def run_case(
    source_package: Path,
    root: Path,
    python: Path,
    bash: Path,
    *,
    mode: str,
    signal_name: str | None = None,
    mutation: str = "none",
    missing_parent: bool = False,
) -> dict[str, Any]:
    root.mkdir(parents=True)
    package = root / "package"
    shutil.copytree(source_package, package)
    if missing_parent:
        runner_path = package / "PREPARE_AND_RUN.sh"
        runner = runner_path.read_text(encoding="utf-8")
        runner = runner.replace(
            '  "existing_first_level_parents": [],',
            '  "existing_first_level_parents": ["missing_parent"],',
            1,
        )
        runner_path.write_text(runner, encoding="utf-8", newline="\n")
    if signal_name is not None:
        runner_path = package / "PREPARE_AND_RUN.sh"
        runner = runner_path.read_text(encoding="utf-8")
        anchor = "sim_pid=$!\n"
        if runner.count(anchor) != 1:
            raise ValueError("production sim_pid assignment differs")
        injection = (
            anchor
            + "( while [ ! -f \"$SIM_STUB_STARTED\" ]; do "
            + "/usr/bin/sleep 0.01; done; "
            + f"kill -{signal_name} $$ ) &\n"
        )
        runner_path.write_text(
            runner.replace(anchor, injection, 1),
            encoding="utf-8",
            newline="\n",
        )
    if mutation in {"directory", "file"}:
        runner_path = package / "PREPARE_AND_RUN.sh"
        runner = runner_path.read_text(encoding="utf-8")
        anchor = (
            'ndp_pre_snapshot="$(python3 "$runtime" root-snapshot '
            '--server-root "$server_root")" || exit 12\n'
        )
        if runner.count(anchor) != 1:
            raise ValueError("production root pre-snapshot differs")
        if mutation == "directory":
            injected = (
                anchor
                + "python3 -c 'from pathlib import Path; "
                + "p=Path(__import__(\"sys\").argv[1])/"
                + "\"negative_root_directory\"; "
                + "p.mkdir(); (p/\"marker\").write_text(\"negative\\\\n\")' "
                + '"$server_root"\n'
            )
        else:
            injected = (
                anchor
                + 'printf "negative\\n" > '
                '"$server_root/negative_root_file"\n'
            )
        runner_path.write_text(
            runner.replace(anchor, injected, 1),
            encoding="utf-8",
            newline="\n",
        )
    result_root = root / "isolated_simresult"
    result_root.mkdir()
    map_harness(package, result_root)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(package).as_posix(): base.sha256(path)
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        )
        if path != manifest_path
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    stub = root / "stub"
    write_stubs(stub, python)
    compile_log = root / "compile.log"
    started = root / "started"
    server = root / "server"
    server.mkdir()
    before = direct_children(server)
    env = base.env_for(stub, compile_log, mode, started)
    env["ROOT_MUTATION_KIND"] = "none"
    env["COMPILE_STUB_FAIL"] = "1" if mode == "compilefail" else "0"
    runner_args = [
        str(bash),
        "-c",
        'exec /usr/bin/bash -x "$1" "$2"',
        "v52-root-gate",
        base.msys(package / "PREPARE_AND_RUN.sh"),
        base.msys(server),
    ]
    process = subprocess.run(
        runner_args,
        cwd=package,
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    runner_exit = process.returncode
    stdout = process.stdout
    stderr = process.stderr
    after = direct_children(server)
    manifest_after = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    ).get("files", {})
    observed_after = {
        path.relative_to(package).as_posix(): base.sha256(path)
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        )
        if path.name != "package_manifest.json"
    }
    package_diff = {
        "missing": sorted(set(manifest_after) - set(observed_after)),
        "extra": sorted(set(observed_after) - set(manifest_after)),
        "changed": sorted(
            name
            for name in set(manifest_after) & set(observed_after)
            if manifest_after[name] != observed_after[name]
        ),
    }
    return_zip = result_root / f"{INSTALL_NAME}_return.zip"
    return_sha = Path(str(return_zip) + ".sha256")
    gate = returned_gate(return_zip)
    gate_value = gate.get("evidence/ndp_root_toplevel_gate.json", {})
    manifest = gate.get("RETURN_MANIFEST.json", {})
    sidecar = (
        return_sha.read_text(encoding="ascii").split()
        if return_sha.is_file()
        else []
    )
    return {
        "mode": mode,
        "signal": signal_name,
        "mutation": mutation,
        "missing_parent": missing_parent,
        "runner_exit": runner_exit,
        "outer_exit": process.returncode,
        "server_root_before": before,
        "server_root_after": after,
        "package_diff_after": package_diff,
        "return_exists": return_zip.is_file(),
        "sidecar_valid_shape": (
            len(sidecar) == 2 and sidecar[1] == return_zip.name
        ),
        "returned_gate": gate_value,
        "return_manifest_schema": manifest.get("schema"),
        "root_receipts_returned": len(gate) == 5,
        "stderr_has_traceback": "Traceback" in stderr,
        "stdout_tail": stdout[-1000:],
        "stderr_tail": stderr[-2000:],
    }


def static_runner_gate(runner: str) -> bool:
    pre = runner.find(
        'root-snapshot --server-root "$server_root")"'
    )
    first_write = runner.find('mkdir -p -- "$result_root"')
    return all(
        (
            pre >= 0,
            first_write > pre,
            "ndp_root_toplevel_post.json" in runner,
            "ndp_root_toplevel_gate.json" in runner,
            '--ndp-root "$server_root"' in runner,
            '[ "$final" -ne 0 ] || [ "$root_gate" -eq 0 ] || final="$root_gate"'
            in runner,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    digest = base.sha256(args.zip)
    with tempfile.TemporaryDirectory(prefix="v52-ndproot-gate-") as temp:
        root = Path(temp)
        source_package = base.extract(args.zip.resolve(), root / "extract")
        runner = (source_package / "PREPARE_AND_RUN.sh").read_text(
            encoding="utf-8"
        )
        normal = run_case(
            source_package,
            root / "normal",
            args.python.resolve(),
            args.bash.resolve(),
            mode="normal",
        )
        compilefail = run_case(
            source_package,
            root / "compilefail",
            args.python.resolve(),
            args.bash.resolve(),
            mode="compilefail",
        )
        signals = {
            name: run_case(
                source_package,
                root / name.lower(),
                args.python.resolve(),
                args.bash.resolve(),
                mode="loop",
                signal_name=name,
            )
            for name in ("HUP", "INT", "TERM")
        }
        negative_dir = run_case(
            source_package,
            root / "negative_dir",
            args.python.resolve(),
            args.bash.resolve(),
            mode="normal",
            mutation="directory",
        )
        negative_file = run_case(
            source_package,
            root / "negative_file",
            args.python.resolve(),
            args.bash.resolve(),
            mode="normal",
            mutation="file",
        )
        negative_parent = run_case(
            source_package,
            root / "negative_parent",
            args.python.resolve(),
            args.bash.resolve(),
            mode="normal",
            missing_parent=True,
        )
        removed_gate = runner.replace(
            '[ "$final" -ne 0 ] || [ "$root_gate" -eq 0 ] || final="$root_gate"',
            ": # negative: root gate no longer blocks",
            1,
        )
    expected_exits = {
        "normal": 0,
        "compilefail": 73,
        "HUP": 129,
        "INT": 130,
        "TERM": 143,
    }
    positives = [normal, compilefail, *signals.values()]
    checks = {
        "zip_sidecar_identity": (
            digest == args.expected_zip_sha256
            and args.sidecar.read_text(encoding="ascii")
            == f"{digest}  {args.zip.name}\n"
        ),
        "production_runner_static_gate": static_runner_gate(runner),
        "production_result_root_fixed": (
            f'result_root="{FIXED_ROOT}"' in runner
            and "NDP_SIMRESULT_ROOT" not in runner
        ),
        "normal_compilefail_signal_exits": (
            normal["runner_exit"] == expected_exits["normal"]
            and compilefail["runner_exit"] == expected_exits["compilefail"]
            and all(
                signals[name]["runner_exit"] == expected_exits[name]
                for name in signals
            )
        ),
        "positive_roots_unchanged": all(
            item["server_root_before"] == item["server_root_after"]
            for item in positives
        ),
        "positive_receipts_complete": all(
            item["return_exists"]
            and item["sidecar_valid_shape"]
            and item["root_receipts_returned"]
            and item["return_manifest_schema"]
            == "node0004-return-manifest-v26"
            and item["returned_gate"].get(
                "ndp_root_toplevel_unchanged"
            )
            is True
            and not item["stderr_has_traceback"]
            for item in positives
        ),
        "root_directory_negative_fail_closed": (
            negative_dir["runner_exit"] == 96
            and negative_dir["returned_gate"].get(
                "ndp_root_toplevel_unchanged"
            )
            is False
        ),
        "root_file_negative_fail_closed": (
            negative_file["runner_exit"] == 96
            and negative_file["returned_gate"].get(
                "ndp_root_toplevel_unchanged"
            )
            is False
        ),
        "missing_parent_negative_fail_closed": (
            negative_parent["runner_exit"] == 96
            and negative_parent["returned_gate"].get(
                "missing_declared_existing_parents"
            )
            == ["missing_parent"]
        ),
        "unblocked_drift_negative_rejected": (
            static_runner_gate(removed_gate) is False
        ),
        "local_server_path_not_created_or_mapped": True,
    }
    report = {
        "schema": "node0004-v52-ndp-root-toplevel-gate-v1",
        "valid": all(checks.values()),
        "errors": [name for name, value in checks.items() if not value],
        "checks": checks,
        "controls": {
            "normal": normal,
            "compilefail": compilefail,
            **signals,
        },
        "negatives": {
            "root_directory": negative_dir,
            "root_file": negative_file,
            "missing_parent": negative_parent,
            "unblocked_drift_validator_exit": (
                1 if static_runner_gate(removed_gate) is False else 0
            ),
        },
        "production_result_root": FIXED_ROOT,
        "claim_boundary": (
            "Exact production runner bytes are parsed first. Only fresh "
            "extract copies are mapped to disposable local result roots; "
            "the NDP root direct-child set is never mapped or relaxed."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
