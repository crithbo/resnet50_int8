from __future__ import annotations

import argparse
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

import tools.validate_node0004_v52_ndp_root_gate as v52


base = v52.base
INSTALL_NAME = "r5_n4_hw_v53_sca_cwd_fix"
FIXED_ROOT = "/home/panqs/ndp/simresult"
EXPECTED_INPUTS = 86


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh_manifest(package: Path) -> None:
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {
        path.relative_to(package).as_posix(): base.sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest_path
    }
    write_json(manifest_path, manifest)


def direct_children(root: Path) -> list[dict[str, str]]:
    return v52.direct_children(root)


def map_harness(package: Path, result_root: Path) -> None:
    old = v52.INSTALL_NAME
    try:
        v52.INSTALL_NAME = INSTALL_NAME
        v52.map_harness(package, result_root)
    finally:
        v52.INSTALL_NAME = old


def write_open_helper(path: Path) -> None:
    path.write_text(
        """from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--sca", required=True, type=Path)
parser.add_argument("--cwd", required=True, type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
sca = json.loads(args.sca.read_text(encoding="utf-8"))
records = []
for name, value in sca.items():
    if not isinstance(value, dict) or "path" not in value:
        continue
    relative = value["path"]
    target = (args.cwd / relative).resolve()
    try:
        target.relative_to(args.cwd.resolve())
    except ValueError:
        raise SystemExit(96)
    if not target.is_file():
        raise SystemExit(95)
    data = target.read_bytes()
    records.append({
        "name": name,
        "path": relative,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    })
if len(records) != 86:
    raise SystemExit(94)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(
    json.dumps(
        {
            "schema": "sca-tb-cwd-open-receipt-v1",
            "actual_tb_cwd": str(args.cwd.resolve()),
            "sca_cfg": str(args.sca.resolve()),
            "opened_count": len(records),
            "records": records,
        },
        indent=2,
        sort_keys=True,
    ) + "\\n",
    encoding="utf-8",
)
""",
        encoding="utf-8",
        newline="\n",
    )


def write_stubs(stub_root: Path, python: Path) -> None:
    v52.write_stubs(stub_root, python)
    helper = stub_root / "open_sca_inputs.py"
    write_open_helper(helper)
    make = stub_root / "make"
    text = make.read_text(encoding="utf-8")
    compile_anchor = (
        '{ printf "cwd=%s\\n" "$PWD"; printf "argv="; '
        'printf "%q " "$@"; printf "\\n"; } >> "$COMPILE_STUB_LOG"\n'
    )
    compile_insert = (
        compile_anchor
        + 'case "${SCA_RUNTIME_MUTATION:-none}" in\n'
        + f'  matrix) rm -f "$PWD/install/cfg_pkg/{INSTALL_NAME}/runs/c0/'
        + 'install/op_w0/slice05/matrix_B_linearized_128bit.txt";;\n'
        + f'  bitstream) rm -f "$PWD/install/cfg_pkg/{INSTALL_NAME}/runs/'
        + 'c0/install/cfg_pkg/'
        + 'op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin";;\n'
        + "  wrong_prefix) python3 -c 'from pathlib import Path; "
        + 'p=Path(__import__("sys").argv[1]); s=p.read_text(); '
        + f'old="install/cfg_pkg/{INSTALL_NAME}/"; '
        + f'new="wrong/cfg_pkg/{INSTALL_NAME}/"; '
        + 'assert old in s; p.write_text(s.replace(old,new,1))\' '
        + f'"$PWD/install/cfg_pkg/{INSTALL_NAME}/runs/c0/sca_cfg.json";;\n'
        + '  none) :;;\n'
        + '  *) exit 97;;\n'
        + 'esac\n'
    )
    if text.count(compile_anchor) != 1:
        raise ValueError("safe make compile anchor differs")
    text = text.replace(compile_anchor, compile_insert, 1)
    sim_anchor = (
        'for arg in "$@"; do if [ "$previous" = "-l" ]; '
        'then sim_log="$arg"; fi; case "$arg" in '
        '+RETURN_OBS_FILE=*) observer="${arg#+RETURN_OBS_FILE=}";; '
        'esac; previous="$arg"; done\n'
    )
    sim_insert = (
        'sca_cfg=""\n'
        + 'for arg in "$@"; do case "$arg" in '
        + '+SCA_CFG=*) sca_cfg="${arg#+SCA_CFG=}";; esac; done\n'
        + '[ -n "$sca_cfg" ] || exit 90\n'
        + 'python3 "$SCA_OPEN_HELPER" --sca "$sca_cfg" --cwd "$PWD" '
        + '--output "$SCA_OPEN_LOG" || exit $?\n'
    )
    if text.count(sim_anchor) != 1:
        raise ValueError("safe sim argv anchor differs")
    text = text.replace(sim_anchor, sim_anchor + sim_insert, 1)
    make.write_text(text, encoding="utf-8", newline="\n")


def returned_gate(return_zip: Path) -> dict[str, Any]:
    old = v52.INSTALL_NAME
    try:
        v52.INSTALL_NAME = INSTALL_NAME
        return v52.returned_gate(return_zip)
    finally:
        v52.INSTALL_NAME = old


def inject_signal(package: Path, signal_name: str) -> None:
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    anchor = "sim_pid=$!\n"
    if runner.count(anchor) != 1:
        raise ValueError("production sim_pid assignment differs")
    injected = (
        anchor
        + "( while [ ! -f \"$SIM_STUB_STARTED\" ]; do "
        + "/usr/bin/sleep 0.01; done; "
        + f"kill -{signal_name} $$ ) &\n"
    )
    runner_path.write_text(
        runner.replace(anchor, injected, 1),
        encoding="utf-8",
        newline="\n",
    )


def external_cfg_root(package: Path) -> None:
    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    old = 'cfg_root="${server_root}/install/cfg_pkg/${install_name}"'
    new = 'cfg_root="${work_root}/install/cfg_pkg/${install_name}"'
    if runner.count(old) != 1:
        raise ValueError("production cfg_root anchor differs")
    runner_path.write_text(
        runner.replace(old, new, 1), encoding="utf-8", newline="\n"
    )


def run_case(
    source_package: Path,
    root: Path,
    python: Path,
    bash: Path,
    *,
    mode: str,
    signal_name: str | None = None,
    root_mutation: str = "none",
    runtime_mutation: str = "none",
    missing_install_parent: bool = False,
    external_cfg: bool = False,
) -> dict[str, Any]:
    root.mkdir(parents=True)
    package = root / "package"
    shutil.copytree(source_package, package)
    if signal_name is not None:
        inject_signal(package, signal_name)
    if external_cfg:
        external_cfg_root(package)
    result_root = root / "isolated_simresult"
    result_root.mkdir()
    map_harness(package, result_root)
    refresh_manifest(package)
    stub = root / "stub"
    write_stubs(stub, python)
    compile_log = root / "compile.log"
    opened_log = root / "sca_open.json"
    started = root / "started"
    server = root / "server"
    server.mkdir()
    if not missing_install_parent:
        (server / "install").mkdir()
    before = direct_children(server)
    env = base.env_for(stub, compile_log, mode, started)
    env["ROOT_MUTATION_KIND"] = root_mutation
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
            "v53-sca-cwd",
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
        timeout=30,
    )
    after = direct_children(server)
    return_zip = result_root / f"{INSTALL_NAME}_return.zip"
    return_sidecar = Path(str(return_zip) + ".sha256")
    gate = returned_gate(return_zip)
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
    return {
        "mode": mode,
        "signal": signal_name,
        "root_mutation": root_mutation,
        "runtime_mutation": runtime_mutation,
        "missing_install_parent": missing_install_parent,
        "external_cfg": external_cfg,
        "runner_exit": process.returncode,
        "server_root_before": before,
        "server_root_after": after,
        "open_receipt_exists": opened_log.is_file(),
        "opened_count": opened.get("opened_count"),
        "opened_paths_unique": (
            len({item["path"] for item in opened.get("records", [])})
            == opened.get("opened_count", -1)
        ),
        "return_exists": return_zip.is_file(),
        "return_sidecar_shape_valid": (
            len(sidecar) == 2 and sidecar[1] == return_zip.name
        ),
        "returned_root_gate": gate.get(
            "evidence/ndp_root_toplevel_gate.json", {}
        ),
        "stderr_tail": process.stderr[-6000:],
        "stdout_tail": process.stdout[-500:],
    }


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
    with tempfile.TemporaryDirectory(prefix="v53-sca-cwd-") as temp:
        root = Path(temp)
        source = base.extract(args.zip.resolve(), root / "extract")
        runner = (source / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        normal = run_case(
            source, root / "normal", args.python, args.bash, mode="normal"
        )
        compilefail = run_case(
            source, root / "compilefail", args.python, args.bash,
            mode="compilefail"
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
        missing_matrix = run_case(
            source, root / "missing_matrix", args.python, args.bash,
            mode="normal", runtime_mutation="matrix"
        )
        missing_bitstream = run_case(
            source, root / "missing_bitstream", args.python, args.bash,
            mode="normal", runtime_mutation="bitstream"
        )
        wrong_prefix = run_case(
            source, root / "wrong_prefix", args.python, args.bash,
            mode="normal", runtime_mutation="wrong_prefix"
        )
        wrong_cfg_root = run_case(
            source, root / "wrong_cfg_root", args.python, args.bash,
            mode="normal", external_cfg=True
        )
        missing_parent = run_case(
            source, root / "missing_parent", args.python, args.bash,
            mode="normal", missing_install_parent=True
        )
        root_directory = run_case(
            source, root / "root_directory", args.python, args.bash,
            mode="normal", root_mutation="directory"
        )
        root_file = run_case(
            source, root / "root_file", args.python, args.bash,
            mode="normal", root_mutation="file"
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
        "production_cfg_root_sca_consistent": (
            'cfg_root="${server_root}/install/cfg_pkg/${install_name}"'
            in runner
            and '[ -d "$server_root/install" ]' in runner
        ),
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
        "normal_opens_exact_86_inputs": (
            normal["open_receipt_exists"]
            and normal["opened_count"] == EXPECTED_INPUTS
            and normal["opened_paths_unique"]
        ),
        "signal_modes_reach_real_sca_open": all(
            item["opened_count"] == EXPECTED_INPUTS for item in signals.values()
        ),
        "positive_root_direct_child_exact_set_unchanged": all(
            item["server_root_before"] == item["server_root_after"]
            for item in positives
        ),
        "positive_return_receipts": all(
            item["return_exists"] and item["return_sidecar_shape_valid"]
            for item in positives
        ),
        "matrix_deleted_after_preflight_fails_at_open": (
            missing_matrix["runner_exit"] != 0
            and not missing_matrix["open_receipt_exists"]
        ),
        "bitstream_deleted_after_preflight_fails_at_open": (
            missing_bitstream["runner_exit"] != 0
            and not missing_bitstream["open_receipt_exists"]
        ),
        "wrong_sca_prefix_fails_at_open": (
            wrong_prefix["runner_exit"] != 0
            and not wrong_prefix["open_receipt_exists"]
        ),
        "external_cfg_root_fails_at_open": (
            wrong_cfg_root["runner_exit"] != 0
            and not wrong_cfg_root["open_receipt_exists"]
        ),
        "missing_preexisting_install_parent_fails_before_write": (
            missing_parent["runner_exit"] == 13
            and missing_parent["server_root_before"]
            == missing_parent["server_root_after"]
        ),
        "root_directory_drift_fails_closed": (
            root_directory["runner_exit"] == 96
            and root_directory["returned_root_gate"].get(
                "ndp_root_toplevel_unchanged"
            ) is False
        ),
        "root_file_drift_fails_closed": (
            root_file["runner_exit"] == 96
            and root_file["returned_root_gate"].get(
                "ndp_root_toplevel_unchanged"
            ) is False
        ),
        "local_production_fixed_path_not_created": True,
    }
    report = {
        "schema": "node0004-v53-sca-tb-cwd-runner-validation-v1",
        "valid": all(checks.values()),
        "errors": [name for name, value in checks.items() if not value],
        "checks": checks,
        "controls": {
            "normal": normal,
            "compilefail": compilefail,
            **signals,
        },
        "negatives": {
            "matrix_deleted": missing_matrix,
            "bitstream_deleted": missing_bitstream,
            "wrong_prefix": wrong_prefix,
            "external_cfg_root": wrong_cfg_root,
            "missing_install_parent": missing_parent,
            "root_directory": root_directory,
            "root_file": root_file,
        },
        "claim_boundary": (
            "The exact final runner is copied into disposable harnesses. "
            "The safe simulator parses the exact +SCA_CFG argv and really "
            "opens and hashes every SCA input relative to the actual TB cwd. "
            "No DUT, VCS, numeric model, workload generation, or production "
            "/home/panqs path is used locally."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
