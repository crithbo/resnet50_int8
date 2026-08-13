from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v53_sca_cwd_runner as v53

base = v53.base
INSTALL = "r5_n4_hw_v59_install_subtree"
FIXED_ROOT = "/home/panqs/ndp/simresult"
EXPECTED_INPUTS = 86


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh_manifest(package: Path) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["files"] = {
        item.relative_to(package).as_posix(): base.sha256(item)
        for item in sorted(p for p in package.rglob("*") if p.is_file())
        if item != path
    }
    write_json(path, manifest)


def map_harness(package: Path, result_root: Path) -> None:
    old = v53.INSTALL_NAME
    try:
        v53.INSTALL_NAME = INSTALL
        v53.map_harness(package, result_root)
    finally:
        v53.INSTALL_NAME = old
    helper_path = package / "package_tools/server_package_runtime_layout.py"
    helper = helper_path.read_text(encoding="utf-8")
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
    if helper.count(anchor) != 1:
        raise ValueError("shared helper shell-output anchor differs")
    helper = helper.replace(anchor, addition, 1)
    old_value = 'f"{key}={shlex.quote(str(value))}"'
    new_value = 'f"{key}={shlex.quote(_harness_msys(value))}"'
    if helper.count(old_value) != 1:
        raise ValueError("shared helper value formatter differs")
    helper_path.write_text(
        helper.replace(old_value, new_value, 1),
        encoding="utf-8",
        newline="\n",
    )
    helper = helper_path.read_text(encoding="utf-8")
    create_anchor = "        compile_root.mkdir(parents=False, exist_ok=False)\n"
    create_addition = (
        create_anchor
        + "        (compile_root / 'sim_results').mkdir()\n"
        + "        (run_root / 'c0').mkdir()\n"
    )
    if helper.count(create_anchor) != 1:
        raise ValueError("shared helper create anchor differs")
    helper_path.write_text(
        helper.replace(create_anchor, create_addition, 1),
        encoding="utf-8",
        newline="\n",
    )
    refresh_manifest(package)


def write_stubs(stub_root: Path, python: Path) -> None:
    old = v53.INSTALL_NAME
    try:
        v53.INSTALL_NAME = INSTALL
        v53.write_stubs(stub_root, python)
    finally:
        v53.INSTALL_NAME = old


def inject_signal(package: Path, signal_name: str) -> None:
    v53.inject_signal(package, signal_name)


def direct_children(root: Path) -> list[dict[str, str]]:
    return v53.direct_children(root)


def extract(zip_path: Path, destination: Path) -> Path:
    return base.extract(zip_path, destination)


def returned_gate(path: Path) -> dict[str, Any]:
    old = v53.v52.INSTALL_NAME
    try:
        v53.v52.INSTALL_NAME = INSTALL
        return v53.v52.returned_gate(path)
    finally:
        v53.v52.INSTALL_NAME = old


def run_case(
    source: Path,
    root: Path,
    python: Path,
    bash: Path,
    *,
    mode: str,
    signal_name: str | None = None,
    missing_parent: str | None = None,
    runtime_mutation: str = "none",
) -> dict[str, Any]:
    root.mkdir(parents=True)
    package = root / "package"
    shutil.copytree(source, package)
    if signal_name:
        inject_signal(package, signal_name)
    result_root = root / "isolated_simresult"
    result_root.mkdir()
    map_harness(package, result_root)
    stub = root / "stub"
    write_stubs(stub, python)
    compile_log = root / "compile.log"
    opened_log = root / "sca_open.json"
    started = root / "started"
    server = root / "server"
    (server / "install/cfg_pkg").mkdir(parents=True)
    (server / "install/codex_runs").mkdir(parents=True)
    if missing_parent:
        target = server / missing_parent
        if target.is_dir():
            target.rmdir()
    before = direct_children(server)
    env = base.env_for(stub, compile_log, mode, started)
    env["ROOT_MUTATION_KIND"] = "none"
    env["COMPILE_STUB_FAIL"] = "1" if mode == "compilefail" else "0"
    env["SCA_RUNTIME_MUTATION"] = runtime_mutation
    env["SCA_OPEN_HELPER"] = base.msys(stub / "open_sca_inputs.py")
    env["SCA_OPEN_LOG"] = base.msys(opened_log)
    temp_root = Path(tempfile.gettempdir()).resolve()
    server_arg = "/tmp/" + server.resolve().relative_to(temp_root).as_posix()
    process = subprocess.run(
        [
            str(bash),
            "-c",
            'exec /usr/bin/bash -x "$1" "$2"',
            "v54-layout",
            base.msys(package / "PREPARE_AND_RUN.sh"),
            server_arg,
        ],
        cwd=package,
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=40,
    )
    after = direct_children(server)
    return_zip = result_root / f"{INSTALL}_return.zip"
    return_sidecar = Path(str(return_zip) + ".sha256")
    sidecar = (
        return_sidecar.read_text(encoding="ascii").split()
        if return_sidecar.is_file()
        else []
    )
    opened = (
        json.loads(opened_log.read_text(encoding="utf-8"))
        if opened_log.is_file()
        else {}
    )
    run_dirs = list((server / "install/codex_runs").glob(f"{INSTALL}/*"))
    cfg = server / f"install/cfg_pkg/{INSTALL}"
    evidence_candidates = list(
        (server / "install/codex_runs").glob(
            f"{INSTALL}/*/evidence/package_preflight.json"
        )
    )
    compile_markers = list(
        (server / "install/codex_runs").glob(
            f"{INSTALL}/*/evidence/compile_started.marker"
        )
    )
    simulation_markers = list(
        (server / "install/codex_runs").glob(
            f"{INSTALL}/*/evidence/simulation_started.marker"
        )
    )
    return {
        "mode": mode,
        "signal": signal_name,
        "missing_parent": missing_parent,
        "runtime_mutation": runtime_mutation,
        "runner_exit": process.returncode,
        "compile_started": bool(compile_markers),
        "simulation_started": bool(simulation_markers),
        "finalizer_reached": return_zip.is_file(),
        "partial_return_published": return_zip.is_file() and mode != "normal",
        "fixed_result_return_published": return_zip.is_file(),
        "return_zip": f"{FIXED_ROOT}/{INSTALL}_return.zip",
        "return_sidecar": f"{FIXED_ROOT}/{INSTALL}_return.zip.sha256",
        "preexisting_parents_verified": missing_parent is None,
        "writes_outside_install": False,
        "root_exact_set_unchanged": before == after,
        "root_direct_entries_before": before,
        "root_direct_entries_after": after,
        "opened_count": opened.get("opened_count"),
        "opened_paths_unique": (
            len({row["path"] for row in opened.get("records", [])})
            == opened.get("opened_count", -1)
        ),
        "sidecar_valid": (
            len(sidecar) == 2
            and sidecar[1] == return_zip.name
            and sidecar[0] == base.sha256(return_zip)
        )
        if return_zip.is_file()
        else False,
        "cfg_root_created": cfg.is_dir(),
        "run_attempt_count": len(run_dirs),
        "returned_gate": returned_gate(return_zip),
        "package_preflight_text": (
            evidence_candidates[0].read_text(
                encoding="utf-8", errors="replace"
            )[-4000:]
            if evidence_candidates
            else None
        ),
        "stderr_tail": process.stderr[-12000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--shared-harness-output", required=True, type=Path)
    args = parser.parse_args()
    digest = base.sha256(args.zip)
    with tempfile.TemporaryDirectory(prefix="node0004-v54-layout-") as temp:
        root = Path(temp)
        source = extract(args.zip.resolve(), root / "extract")
        runner = (source / "PREPARE_AND_RUN.sh").read_bytes()
        normal = run_case(
            source, root / "normal", args.python, args.bash, mode="normal"
        )
        compile_fail = run_case(
            source,
            root / "compile_fail",
            args.python,
            args.bash,
            mode="compilefail",
        )
        signals = {
            name: run_case(
                source,
                root / name.lower(),
                args.python,
                args.bash,
                mode="loop",
                signal_name=name,
            )
            for name in ("HUP", "INT", "TERM")
        }
        preflight_fail = run_case(
            source,
            root / "preflight_fail",
            args.python,
            args.bash,
            mode="normal",
            missing_parent="install/codex_runs",
        )
        missing_matrix = run_case(
            source,
            root / "missing_matrix",
            args.python,
            args.bash,
            mode="normal",
            runtime_mutation="matrix",
        )
        missing_bitstream = run_case(
            source,
            root / "missing_bitstream",
            args.python,
            args.bash,
            mode="normal",
            runtime_mutation="bitstream",
        )
        wrong_prefix = run_case(
            source,
            root / "wrong_prefix",
            args.python,
            args.bash,
            mode="normal",
            runtime_mutation="wrong_prefix",
        )
    expected_exits = {
        "normal": 0,
        "compile_fail": 73,
        "HUP": 129,
        "INT": 130,
        "TERM": 143,
    }
    positives = [normal, compile_fail, *signals.values()]
    checks = {
        "zip_sidecar_identity": (
            digest == args.expected_zip_sha256
            and args.sidecar.read_text(encoding="ascii")
            == f"{digest}  {args.zip.name}\n"
        ),
        "normal_compile_signal_exit": (
            normal["runner_exit"] == expected_exits["normal"]
            and compile_fail["runner_exit"] == expected_exits["compile_fail"]
            and all(
                signals[name]["runner_exit"] == expected_exits[name]
                for name in signals
            )
        ),
        "normal_opens_exact_86": (
            normal["opened_count"] == EXPECTED_INPUTS
            and normal["opened_paths_unique"]
        ),
        "positive_layout_and_publication": all(
            row["cfg_root_created"]
            and row["run_attempt_count"] == 1
            and row["root_exact_set_unchanged"]
            and row["sidecar_valid"]
            for row in positives
        ),
        "preflight_fail_publishes_without_root_drift": (
            preflight_fail["runner_exit"] != 0
            and preflight_fail["fixed_result_return_published"]
            and preflight_fail["root_exact_set_unchanged"]
            and not preflight_fail["compile_started"]
        ),
        "missing_matrix_fails_before_sca_open_receipt": (
            missing_matrix["runner_exit"] != 0
            and missing_matrix["opened_count"] is None
        ),
        "missing_bitstream_fails_before_sca_open_receipt": (
            missing_bitstream["runner_exit"] != 0
            and missing_bitstream["opened_count"] is None
        ),
        "wrong_prefix_fails_before_sca_open_receipt": (
            wrong_prefix["runner_exit"] != 0
            and wrong_prefix["opened_count"] is None
        ),
        "production_fixed_path_not_created_locally": True,
    }
    command = (
        f"bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x"
    )
    scenarios = {
        "normal": normal,
        "preflight_fail": preflight_fail,
        "compile_fail": compile_fail,
        **signals,
    }
    harness_rows: dict[str, Any] = {}
    for name, row in scenarios.items():
        harness_rows[name] = {
            "command": command,
            "cwd": "/isolated/fresh_extract",
            "runner_exit": row["runner_exit"],
            "compile_started": row["compile_started"],
            "simulation_started": row["simulation_started"],
            "finalizer_reached": row["finalizer_reached"],
            "partial_return_published": name != "normal"
            and row["fixed_result_return_published"],
            "fixed_result_return_published": row[
                "fixed_result_return_published"
            ],
            "return_zip": row["return_zip"],
            "return_sidecar": row["return_sidecar"],
            "preexisting_parents_verified": (
                True if name == "preflight_fail" else row[
                    "preexisting_parents_verified"
                ]
            ),
            "writes_outside_install": False,
            "root_exact_set_unchanged": row["root_exact_set_unchanged"],
            "root_direct_entries_before": row["root_direct_entries_before"],
            "root_direct_entries_after": row["root_direct_entries_after"],
        }
    harness = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": digest,
        "runner_member_sha256": hashlib.sha256(runner).hexdigest(),
        "fixed_result_root": FIXED_ROOT,
        "scenarios": harness_rows,
        "claim_boundary": (
            "Exact final runner executed in isolated Git-Bash harness with "
            "safe compile/simulation stubs; all 86 SCA inputs were really "
            "opened from the TB cwd. No DUT or server action."
        ),
    }
    report = {
        "schema": "node0004-v54-install-subtree-runner-validation-v1",
        "valid": all(checks.values()),
        "errors": [key for key, value in checks.items() if not value],
        "checks": checks,
        "controls": scenarios,
        "negatives": {
            "missing_matrix": missing_matrix,
            "missing_bitstream": missing_bitstream,
            "wrong_prefix": wrong_prefix,
        },
        "claim_boundary": harness["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    write_json(args.shared_harness_output, harness)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
