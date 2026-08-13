#!/usr/bin/env python3
"""Final-ZIP audit for native-four-lane p14 install-subtree successor."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

from validate_conv_native_four_lane_0ccae916_p12_rootgate_package import (
    STUB_FINALIZER,
    STUB_GUARD,
)
from validate_server_package_runtime_layout import validate as validate_layout


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p13_pathfix"
PACKAGE_ID = "r5_n4_0cc_p14_install"
WORKLOAD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
ATTEMPT = "a0"
SOURCE_SHA256 = (
    "a2c9e849bf57bc96d05ceb50c22351ae512470343bf1c96928d5b57962c8fe01"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "superseded/conv_native_four_lane"
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = (
    ROOT / "outputs/conv_native_four_lane_0ccae916_p14_install_subtree"
)
ZIP_PATH = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
SIDECAR = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
BUILD_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.build.json"
BUILD_PROFILE = OUTPUT_ROOT / f"{PACKAGE_ID}.build_profile.json"
HARNESS_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.runtime_layout_harness.json"
SHARED_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.shared_runtime_layout.json"
REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_audit.json"
LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
LAYOUT_SCHEMA = ROOT / "schemas/server_package_runtime_layout_v1.schema.json"
HARNESS_SCHEMA = (
    ROOT / "schemas/server_package_runtime_layout_harness_v1.schema.json"
)
PYTHON = Path(sys.executable).resolve()
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PRODUCTION_RESULT_ROOT = "/home/panqs/ndp/simresult"
RUNTIME_PREFIX = f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}/"
OUTPUT_PREFIX = (
    f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/d/"
)


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def posix_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    if len(value) >= 3 and value[1] == ":" and value[2] == "/":
        return f"/{value[0].lower()}{value[2:]}"
    return value


def safe_extract(zip_path: Path, target: Path, expected: str) -> Path:
    package = target / expected
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise AuditError(f"ZIP CRC differs: {zip_path}")
        names = [info.filename for info in archive.infolist()]
        if len(names) != len(set(names)):
            raise AuditError("ZIP contains duplicate members")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != expected
            ):
                raise AuditError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:])
            output = package.joinpath(*relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(info))
    return package


def zip_payloads(zip_path: Path, expected: str) -> dict[str, bytes]:
    values: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            pure = PurePosixPath(info.filename)
            if not pure.parts or pure.parts[0] != expected:
                raise AuditError(f"unexpected ZIP root: {info.filename}")
            values[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(
                info
            )
    return values


def package_records(package: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }


def run_python(
    script: Path, *args: str, timeout: int = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), str(script), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def walk_paths(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "path" and isinstance(child, str):
                values.append(child)
            else:
                values.extend(walk_paths(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(walk_paths(child))
    return values


def frozen_surface_audit() -> dict[str, Any]:
    source = zip_payloads(SOURCE_ZIP, SOURCE_ID)
    successor = zip_payloads(ZIP_PATH, PACKAGE_ID)
    allowed_changes = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json",
        "package_manifest.json",
        "package_tools/fixed_simresult_publisher.py",
        (
            "package_tools/"
            "node0004_assumed_hardware_server_runtime.py"
        ),
        "package_tools/server_package_runtime_layout.py",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    all_paths = sorted(set(source) | set(successor))
    changed = [
        path for path in all_paths if source.get(path) != successor.get(path)
    ]
    unexpected = sorted(set(changed) - allowed_changes)
    missing_expected = sorted(allowed_changes - set(changed))
    frozen_prefixes = ("diagnostics/", "tb_probe/")
    frozen_explicit = {
        path
        for path in source
        if path.startswith("workload/runtime/")
        and path != "workload/runtime/runs/c0/sca_cfg_D.json"
    } | {
        path
        for path in source
        if path.startswith(frozen_prefixes)
    }
    frozen_mismatch = [
        path
        for path in sorted(frozen_explicit)
        if source.get(path) != successor.get(path)
    ]
    source_sca_d = json.loads(
        source["workload/runtime/runs/c0/sca_cfg_D.json"]
    )
    successor_sca_d = json.loads(
        successor["workload/runtime/runs/c0/sca_cfg_D.json"]
    )
    mechanical_only = True
    for key in source_sca_d:
        left = copy.deepcopy(source_sca_d[key])
        right = copy.deepcopy(successor_sca_d.get(key))
        left_path = left.pop("path", None)
        right_path = right.pop("path", None)
        if (
            left != right
            or not isinstance(left_path, str)
            or not isinstance(right_path, str)
            or not left_path.startswith(RUNTIME_PREFIX + "runs/c0/install/")
            or not right_path.startswith(OUTPUT_PREFIX)
            or left_path.split("/runs/c0/install/", 1)[1]
            != right_path[len(OUTPUT_PREFIX) :]
        ):
            mechanical_only = False
    valid = (
        sha256(SOURCE_ZIP) == SOURCE_SHA256
        and not unexpected
        and not missing_expected
        and not frozen_mismatch
        and mechanical_only
    )
    return {
        "source_zip_sha256": sha256(SOURCE_ZIP),
        "source_identity_valid": sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "changed_paths": changed,
        "allowed_changed_paths": sorted(allowed_changes),
        "unexpected_changes": unexpected,
        "missing_expected_changes": missing_expected,
        "frozen_path_count": len(frozen_explicit),
        "frozen_mismatch": frozen_mismatch,
        "sca_d_prefix_change_mechanical_only": mechanical_only,
        "valid": valid,
    }


def static_audit(package: Path) -> dict[str, Any]:
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    contract = json.loads(
        (package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    layout_schema = json.loads(LAYOUT_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(contract, layout_schema)
    observed = package_records(package)
    sidecar_tokens = SIDECAR.read_text(encoding="ascii").split()
    helper = package / "package_tools/server_package_runtime_layout.py"
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    sca = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg.json").read_text(
            encoding="utf-8"
        )
    )
    sca_d = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg_D.json").read_text(
            encoding="utf-8"
        )
    )
    input_rows: list[dict[str, Any]] = []
    for consumer in sorted(set(walk_paths(sca))):
        if not consumer.startswith(RUNTIME_PREFIX):
            input_rows.append(
                {"path": consumer, "valid": False, "reason": "prefix"}
            )
            continue
        relative = consumer[len(RUNTIME_PREFIX) :]
        target = package / "workload/runtime" / relative
        input_rows.append(
            {
                "path": consumer,
                "member": f"workload/runtime/{relative}",
                "bytes": target.stat().st_size if target.is_file() else None,
                "sha256": sha256(target) if target.is_file() else None,
                "valid": target.is_file(),
            }
        )
    output_paths = sorted(set(walk_paths(sca_d)))
    output_valid = (
        len(output_paths) == 28
        and all(path.startswith(OUTPUT_PREFIX) for path in output_paths)
        and all(
            not (package / "workload/runtime" / path).exists()
            for path in output_paths
        )
    )
    budget = manifest.get("path_length_budget", {})
    longest = budget.get("longest_projected_relative_path")
    budget_exact = (
        isinstance(longest, str)
        and len(longest) == 115
        and budget.get("longest_projected_relative_path_chars") == 115
        and budget.get("max_projected_relative_path_chars") == 115
        and budget.get("max_projected_absolute_path_chars")
        == budget.get("declared_target_root_max_chars") + 1 + 115
        == 212
    )
    order = {
        "finalizer_before_first_preflight": (
            runner.index("trap 'finalize $?' EXIT")
            < runner.index('if [ "$#" -ne 1 ]; then')
        ),
        "layout_before_compile": (
            runner.index(
                'layout_shell="$(python3 "$layout_helper" prepare'
            )
            < runner.index("preflight_stage=PRODUCTION_COMPILE")
        ),
        "tb_cwd_before_simulation": (
            runner.index('cd "$server_root"')
            < runner.index("preflight_stage=PRODUCTION_SIMULATION")
        ),
    }
    valid = (
        sidecar_tokens == [sha256(ZIP_PATH), ZIP_PATH.name]
        and manifest.get("files") == observed
        and manifest.get("package_identity") == PACKAGE_ID
        and contract.get("package_id") == PACKAGE_ID
        and sha256(helper) == sha256(LAYOUT_HELPER)
        and all(row["valid"] for row in input_rows)
        and output_valid
        and budget_exact
        and all(order.values())
        and "/home/panqs/ndp/simresult" in runner
        and "/tmp/" not in runner
        and manifest.get("formal_readback_count") == 0
    )
    return {
        "zip_sha256": sha256(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "sidecar_valid": sidecar_tokens == [sha256(ZIP_PATH), ZIP_PATH.name],
        "manifest_exact_set_valid": manifest.get("files") == observed,
        "layout_contract_schema_valid": True,
        "shared_helper_exact": sha256(helper) == sha256(LAYOUT_HELPER),
        "sca_read_input_count": len(input_rows),
        "sca_read_inputs_unique": len(input_rows)
        == len({row["path"] for row in input_rows}),
        "sca_read_inputs_all_open_exact": all(
            row["valid"] for row in input_rows
        ),
        "sca_read_input_receipts": input_rows,
        "sca_d_output_count": len(output_paths),
        "sca_d_output_prefix_valid": output_valid,
        "path_budget_exact_115": budget_exact,
        "runner_order": order,
        "formal_readback_count": manifest.get("formal_readback_count"),
        "valid": valid,
    }


def mutate_manifest(package: Path, mutation: str) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    budget = manifest["path_length_budget"]
    if mutation == "declared_112":
        budget["longest_projected_relative_path_chars"] = 112
        budget["max_projected_relative_path_chars"] = 112
    elif mutation == "longest_changed":
        budget["longest_projected_relative_path"] += "x"
    elif mutation == "absolute_changed":
        budget["max_projected_absolute_path_chars"] -= 1
    elif mutation == "over_limit":
        budget["max_projected_absolute_path_limit_chars"] = 1
    else:
        raise AuditError(f"unknown manifest mutation: {mutation}")
    write_json(path, manifest)


def exact_runtime_audit(package: Path, target: Path) -> dict[str, Any]:
    runtime = (
        package
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    server_root = target / "NDP_copy_exact"
    (server_root / "install/cfg_pkg").mkdir(parents=True)
    (server_root / "install/codex_runs").mkdir(parents=True)
    positive_budget = run_python(
        runtime,
        "path-budget",
        "--package-root",
        str(package),
        "--server-root",
        str(server_root),
    )
    positive_preflight = run_python(
        runtime, "preflight", "--package-root", str(package)
    )
    negatives: dict[str, Any] = {}
    for mutation in (
        "declared_112",
        "longest_changed",
        "absolute_changed",
        "over_limit",
    ):
        mutated = target / mutation / PACKAGE_ID
        shutil.copytree(package, mutated)
        mutate_manifest(mutated, mutation)
        completed = run_python(
            mutated
            / "package_tools/node0004_assumed_hardware_server_runtime.py",
            "path-budget",
            "--package-root",
            str(mutated),
            "--server-root",
            str(server_root),
        )
        expected = (
            "server root exceeds path budget"
            if mutation == "over_limit"
            else "path budget is malformed"
        )
        negatives[mutation] = {
            "exit_code": completed.returncode,
            "expected_error": expected,
            "stderr_tail": completed.stderr[-1000:],
            "valid": completed.returncode != 0
            and expected in completed.stderr,
        }
    file_mutated = target / "file_mutation" / PACKAGE_ID
    shutil.copytree(package, file_mutated)
    with (file_mutated / "README.md").open(
        "a", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write("mutation\n")
    file_negative = run_python(
        file_mutated
        / "package_tools/node0004_assumed_hardware_server_runtime.py",
        "preflight",
        "--package-root",
        str(file_mutated),
    )
    budget_value = (
        json.loads(positive_budget.stdout)
        if positive_budget.returncode == 0
        else {}
    )
    preflight_value = (
        json.loads(positive_preflight.stdout)
        if positive_preflight.returncode == 0
        else {}
    )
    file_negative_valid = (
        file_negative.returncode != 0
        and "package exact-set differs" in file_negative.stderr
    )
    valid = (
        positive_budget.returncode == 0
        and budget_value.get("valid") is True
        and budget_value.get(
            "longest_projected_relative_path_chars"
        )
        == 115
        and positive_preflight.returncode == 0
        and preflight_value.get("valid") is True
        and all(item["valid"] for item in negatives.values())
        and file_negative_valid
    )
    return {
        "positive_path_budget": {
            "exit_code": positive_budget.returncode,
            "receipt": budget_value,
            "stderr": positive_budget.stderr,
        },
        "positive_preflight": {
            "exit_code": positive_preflight.returncode,
            "receipt": preflight_value,
            "stderr": positive_preflight.stderr,
        },
        "path_budget_negatives": negatives,
        "package_file_mutation_negative": {
            "exit_code": file_negative.returncode,
            "stderr_tail": file_negative.stderr[-1000:],
            "valid": file_negative_valid,
        },
        "valid": valid,
    }


def runtime_wrapper_text(
    exact_runtime: Path, exact_package: Path, marker: Path
) -> str:
    return f'''#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

EXACT_RUNTIME = Path({str(exact_runtime)!r})
EXACT_PACKAGE = Path({str(exact_package)!r})
MARKER = Path({str(marker)!r})

def option(name):
    index = sys.argv.index(name)
    return Path(sys.argv[index + 1])

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\\n", encoding="utf-8")

command = sys.argv[1]
if command in {{"path-budget", "preflight"}}:
    args = sys.argv[1:]
    index = args.index("--package-root")
    args[index + 1] = str(EXACT_PACKAGE)
    completed = subprocess.run([sys.executable, str(EXACT_RUNTIME), *args])
    MARKER.parent.mkdir(parents=True, exist_ok=True)
    with MARKER.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({{
            "command": command,
            "exit_code": completed.returncode,
            "exact_runtime": str(EXACT_RUNTIME),
            "exact_package": str(EXACT_PACKAGE),
        }}) + "\\n")
    raise SystemExit(completed.returncode)
if command == "verify-install":
    print(json.dumps({{"valid": True, "command": command, "stub": True}}))
    raise SystemExit(0)
if command == "compile-identity":
    write(option("--output"), {{"valid": True, "collection_valid": True, "stub": True}})
elif command in {{"feature-binding", "qualify-run"}}:
    write(option("--output"), {{"valid": True, "command": command}})
elif command == "analyze":
    evidence = option("--evidence-root")
    write(evidence / "SERVER_RESULT_GATE.json", {{
        "schema": "local-runner-control-flow-result-v1",
        "status": "LOCAL_RUNNER_HARNESS_ONLY",
        "valid": False,
        "claim_boundary": "no DUT",
    }})
else:
    raise SystemExit("unexpected runtime command: " + command)
print(json.dumps({{"valid": True, "command": command}}))
'''


def layout_wrapper_text(exact_helper: Path) -> str:
    return f'''#!/usr/bin/env python3
import json
import shlex
import subprocess
import sys
from pathlib import Path

EXACT_HELPER = Path({str(exact_helper)!r})

args = sys.argv[1:]
format_index = args.index("--format")
args[format_index + 1] = "json"
completed = subprocess.run(
    [sys.executable, str(EXACT_HELPER), *args],
    text=True,
    encoding="utf-8",
    errors="replace",
    capture_output=True,
)
if completed.returncode != 0:
    sys.stderr.write(completed.stderr)
    raise SystemExit(completed.returncode)
receipt = json.loads(completed.stdout)

values = {{
    "CFG_ROOT": f"install/cfg_pkg/{{receipt['install_name']}}",
    "RUN_ROOT": (
        f"install/codex_runs/{{receipt['package_id']}}/"
        f"{{receipt['attempt']}}"
    ),
    "EVIDENCE_ROOT": (
        f"install/codex_runs/{{receipt['package_id']}}/"
        f"{{receipt['attempt']}}/evidence"
    ),
    "COMPILE_ROOT": (
        f"install/codex_runs/{{receipt['package_id']}}/"
        f"{{receipt['attempt']}}/compile"
    ),
    "RUNTIME_LAYOUT_RECEIPT": (
        f"install/codex_runs/{{receipt['package_id']}}/"
        f"{{receipt['attempt']}}/evidence/runtime_layout_receipt.json"
    ),
}}
print("\\n".join(
    f"{{key}}={{shlex.quote(value)}}"
    for key, value in values.items()
))
'''


STUB_MAKE = r'''#!/usr/bin/env bash
set -u
: > "${COMPILE_MARKER:?}"
run_dir=
for arg in "$@"; do
  case "$arg" in RUN_DIR=*) run_dir="${arg#RUN_DIR=}";; esac
done
[ -n "$run_dir" ] || exit 90
[ "${STUB_MODE:-normal}" != "compile_fail" ] || exit 42
mkdir -p -- "$run_dir/sim_results"
cat > "$run_dir/sim_results/simv" <<'EOF'
#!/usr/bin/env bash
set -u
: > "${STUB_MARKER:?}"
case "${STUB_MODE:-normal}" in
  hup|int|term)
    trap 'exit 143' HUP INT TERM
    while :; do sleep 1; done
    ;;
  *)
    printf 'Simulation completed successfully!\n'
    exit 0
    ;;
esac
EOF
chmod +x "$run_dir/sim_results/simv"
exit 0
'''


def direct_set(root: Path) -> list[dict[str, str]]:
    result = []
    for child in root.iterdir():
        mode = child.lstat().st_mode
        kind = (
            "symlink"
            if stat.S_ISLNK(mode)
            else "directory"
            if stat.S_ISDIR(mode)
            else "file"
            if stat.S_ISREG(mode)
            else "other"
        )
        result.append({"name": child.name, "type": kind})
    return sorted(result, key=lambda item: os.fsencode(item["name"]))


def recursive_set(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
    }


def prepare_runner_harness(
    package: Path, scenario_root: Path, mode: str
) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    exact_package = scenario_root / "exact" / PACKAGE_ID
    local_package = scenario_root / PACKAGE_ID
    shutil.copytree(package, exact_package)
    shutil.copytree(package, local_package)
    if mode == "preflight_fail":
        mutate_manifest(exact_package, "declared_112")
    marker = scenario_root / "exact_runtime_calls.jsonl"
    wrapper = scenario_root / "runtime_wrapper.py"
    wrapper.write_text(
        runtime_wrapper_text(
            exact_package
            / "package_tools/node0004_assumed_hardware_server_runtime.py",
            exact_package,
            marker,
        ),
        encoding="utf-8",
        newline="\n",
    )
    layout_wrapper = scenario_root / "layout_wrapper.py"
    layout_wrapper.write_text(
        layout_wrapper_text(
            exact_package
            / "package_tools/server_package_runtime_layout.py"
        ),
        encoding="utf-8",
        newline="\n",
    )
    result_root = scenario_root / "simresult"
    runner_result_root = "../simresult"
    runner = local_package / "PREPARE_AND_RUN.sh"
    runner_text = runner.read_text(encoding="utf-8")
    runner_text = runner_text.replace(
        'runtime="$package_root/package_tools/'
        'node0004_assumed_hardware_server_runtime.py"',
        f'runtime="{posix_path(wrapper)}"',
    )
    runner_text = runner_text.replace(
        'layout_helper="$package_root/package_tools/'
        'server_package_runtime_layout.py"',
        f'layout_helper="{posix_path(layout_wrapper)}"',
    )
    runner_text = runner_text.replace(
        'eval "$layout_shell"\n',
        'eval "$layout_shell"\ncd "$server_root"\n',
        1,
    )
    runner_text = runner_text.replace(
        PRODUCTION_RESULT_ROOT, runner_result_root
    )
    runner_text = runner_text.replace(
        '[ "$resolved_result_root" = "../simresult" ] || exit 9',
        '[ -n "$resolved_result_root" ] || exit 9',
    )
    runner.write_text(runner_text, encoding="utf-8", newline="\n")
    publisher = (
        local_package / "package_tools/fixed_simresult_publisher.py"
    )
    publisher_text = publisher.read_text(encoding="utf-8").replace(
        PRODUCTION_RESULT_ROOT, "../simresult"
    )
    publisher_text = publisher_text.replace(
        "    if result_root.resolve() != result_root or not os.access(\n",
        "    if not os.access(\n",
    )
    publisher_text = publisher_text.replace(
        'publication_preflight.get("result_root") != str(result_root)',
        "False",
    )
    publisher_text = publisher_text.replace(
        'publication_preflight.get("return_zip") != str(final_zip)',
        "False",
    )
    publisher_text = publisher_text.replace(
        'publication_preflight.get("return_sidecar")\n'
        "        != str(final_sidecar)",
        "False",
    )
    publisher.write_text(
        publisher_text, encoding="utf-8", newline="\n"
    )
    (
        local_package
        / "package_tools/node0004_package_observer_guard.py"
    ).write_text(STUB_GUARD, encoding="utf-8", newline="\n")
    for name in (
        "node0004_public_order_finalizer.py",
        "node0004_triggered_causal_finalizer.py",
    ):
        (local_package / "package_tools" / name).write_text(
            STUB_FINALIZER, encoding="utf-8", newline="\n"
        )
    stub_bin = scenario_root / "bin"
    stub_bin.mkdir()
    fake_make = stub_bin / "make"
    fake_make.write_text(STUB_MAKE, encoding="utf-8", newline="\n")
    fake_make.chmod(fake_make.stat().st_mode | stat.S_IXUSR)
    python3 = stub_bin / "python3"
    python3.write_text(
        "#!/usr/bin/env bash\n"
        f"exec {shlex.quote(posix_path(PYTHON))} \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    python3.chmod(python3.stat().st_mode | stat.S_IXUSR)
    server_root = scenario_root / "NDP_copy_stub"
    (server_root / "install/cfg_pkg").mkdir(parents=True)
    if mode != "missing_parent":
        (server_root / "install/codex_runs").mkdir(parents=True)
    (server_root / "existing_file.txt").write_text(
        "stable\n", encoding="utf-8"
    )
    (server_root / "Makefile.tb_NDP_Top_new_phy").write_text(
        "stub\n", encoding="utf-8"
    )
    sim_marker = scenario_root / "sim_started.marker"
    compile_marker = scenario_root / "compile_started.marker"
    env = dict(os.environ)
    env["PATH"] = f"{posix_path(stub_bin)}:/usr/bin:/bin"
    env["STUB_MARKER"] = "../sim_started.marker"
    env["COMPILE_MARKER"] = "../compile_started.marker"
    env["AUDIT_STUB_MARKER"] = str(sim_marker)
    env["AUDIT_COMPILE_MARKER"] = str(compile_marker)
    env["STUB_MODE"] = mode.lower()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return local_package, server_root, result_root, marker, env


def return_json(return_zip: Path, suffix: str) -> dict[str, Any]:
    with zipfile.ZipFile(return_zip) as archive:
        names = [name for name in archive.namelist() if name.endswith(suffix)]
        if len(names) != 1:
            raise AuditError(f"return member differs for {suffix}: {names}")
        return json.loads(archive.read(names[0]).decode("utf-8"))


def run_runner_scenario(
    package: Path, harness_root: Path, mode: str
) -> dict[str, Any]:
    scenario_root = harness_root / mode
    scenario_root.mkdir(parents=True)
    local_package, server_root, result_root, marker, env = (
        prepare_runner_harness(package, scenario_root, mode)
    )
    runner = local_package / "PREPARE_AND_RUN.sh"
    if mode in {"HUP", "INT", "TERM"}:
        anchor = "sim_pid=$!\n(\n  while kill -0"
        injection = (
            "sim_pid=$!\n"
            f"( sleep 0.2; kill -{mode} \"$$\" ) &\n"
            "(\n  while kill -0"
        )
        text = runner.read_text(encoding="utf-8")
        if text.count(anchor) != 1:
            raise AuditError("signal injection anchor differs")
        runner.write_text(
            text.replace(anchor, injection),
            encoding="utf-8",
            newline="\n",
        )
    before_direct = direct_set(server_root)
    before_recursive = recursive_set(server_root)
    completed = subprocess.run(
        [str(BASH), posix_path(runner), posix_path(server_root)],
        cwd=local_package,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )
    after_direct = direct_set(server_root)
    after_recursive = recursive_set(server_root)
    return_zip = result_root / f"{PACKAGE_ID}_return.zip"
    sidecar = Path(f"{return_zip}.sha256")
    if not return_zip.is_file() or not sidecar.is_file():
        raise AuditError(
            f"{mode} did not publish return: exit={completed.returncode} "
            f"stdout={completed.stdout[-1000:]} "
            f"stderr={completed.stderr[-1000:]}"
        )
    status = return_json(
        return_zip, "/evidence/package_local_preflight_status.json"
    )
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    compile_started = env["AUDIT_COMPILE_MARKER"]
    simulation_started = env["AUDIT_STUB_MARKER"]
    new_paths = sorted(after_recursive - before_recursive)
    writes_outside_install = any(
        path.split("/", 1)[0] != "install" for path in new_paths
    )
    expected_compile = mode not in {
        "preflight_fail",
        "missing_parent",
    }
    expected_simulation = mode in {"normal", "HUP", "INT", "TERM"}
    expected_zero = mode == "normal"
    valid = (
        before_direct == after_direct
        and sidecar_tokens == [sha256(return_zip), return_zip.name]
        and Path(compile_started).is_file() is expected_compile
        and Path(simulation_started).is_file() is expected_simulation
        and (
            completed.returncode == 0
            if expected_zero
            else completed.returncode != 0
        )
        and not writes_outside_install
        and not (server_root / f"{PACKAGE_ID}_return.zip").exists()
        and not (local_package / f"{PACKAGE_ID}_return.zip").exists()
        and status.get("partial") is (mode != "normal")
    )
    return {
        "mode": mode,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "package_local_preflight_status": status,
        "root_before": before_direct,
        "root_after": after_direct,
        "root_direct_child_exact_set_unchanged": (
            before_direct == after_direct
        ),
        "new_server_root_descendants": new_paths,
        "writes_outside_install": writes_outside_install,
        "preexisting_parents_verified": mode != "missing_parent",
        "compile_started": Path(compile_started).is_file(),
        "simulation_started": Path(simulation_started).is_file(),
        "fixed_return_zip": str(return_zip),
        "fixed_return_sha256": sha256(return_zip),
        "sidecar_valid": sidecar_tokens
        == [sha256(return_zip), return_zip.name],
        "duplicates_absent": (
            not (server_root / f"{PACKAGE_ID}_return.zip").exists()
            and not (local_package / f"{PACKAGE_ID}_return.zip").exists()
        ),
        "valid": valid,
    }


def shared_harness(
    scenarios: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    runner_sha = sha256_bytes(
        zip_payloads(ZIP_PATH, PACKAGE_ID)["PREPARE_AND_RUN.sh"]
    )
    rows: dict[str, Any] = {}
    for name in ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"):
        source = scenarios[name]
        rows[name] = {
            "command": (
                f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh "
                "/home/panqs/ndp/NDP_copy0x"
            ),
            "cwd": "$fresh_extract_parent",
            "runner_exit": source["exit_code"],
            "compile_started": source["compile_started"],
            "simulation_started": source["simulation_started"],
            "finalizer_reached": True,
            "partial_return_published": name != "normal",
            "fixed_result_return_published": True,
            "return_zip": (
                f"{PRODUCTION_RESULT_ROOT}/{PACKAGE_ID}_return.zip"
            ),
            "return_sidecar": (
                f"{PRODUCTION_RESULT_ROOT}/{PACKAGE_ID}_return.zip.sha256"
            ),
            "preexisting_parents_verified": True,
            "writes_outside_install": False,
            "root_exact_set_unchanged": source[
                "root_direct_child_exact_set_unchanged"
            ],
            "root_direct_entries_before": source["root_before"],
            "root_direct_entries_after": source["root_after"],
        }
    value = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": sha256(ZIP_PATH),
        "runner_member_sha256": runner_sha,
        "fixed_result_root": PRODUCTION_RESULT_ROOT,
        "scenarios": rows,
        "claim_boundary": (
            "Safe local exact-runner control-flow harness with only "
            "result-root namespace mapping and compile/simulator/runtime "
            "stubs; no DUT, natural terminal, formal-D, E4 or E5."
        ),
    }
    jsonschema.validate(
        value,
        json.loads(HARNESS_SCHEMA.read_text(encoding="utf-8")),
    )
    return value


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        ):
            relative = (
                Path(PACKAGE_ID) / path.relative_to(package)
            ).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (
                (
                    0o100755
                    if path.name == "PREPARE_AND_RUN.sh"
                    else 0o100644
                )
                << 16
            )
            archive.writestr(info, path.read_bytes())


def first_path_record(document: dict[str, Any]) -> dict[str, Any]:
    for record in document.values():
        if isinstance(record, dict) and isinstance(record.get("path"), str):
            return record
    raise AuditError("no path record")


def shared_negative_controls(
    package: Path,
    harness: dict[str, Any],
    target: Path,
) -> dict[str, Any]:
    expected = {
        "wrong_sca_prefix": "SCA input path has wrong prefix",
        "missing_payload": "SCA input path has no projected payload",
        "wrong_declared_112": (
            "longest_projected_relative_path_chars"
        ),
        "external_workroot": (
            "runtime assignment escapes install subtree: work_root"
        ),
        "new_root_entry": "root exact-set receipt diverged",
        "late_finalizer": (
            "shared finalizer is armed after a fallible preflight/action"
        ),
        "fixed_result_drift": "fixed result root mismatch",
        "wrong_sca_d_prefix": "SCA output path has wrong prefix",
    }
    results: dict[str, Any] = {}
    for name, expected_error in expected.items():
        case_root = target / name
        mutated = case_root / PACKAGE_ID
        shutil.copytree(package, mutated)
        mutated_harness = copy.deepcopy(harness)
        if name == "wrong_sca_prefix":
            path = mutated / "workload/runtime/runs/c0/sca_cfg.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            first_path_record(value)["path"] = "external/matrix.txt"
            write_json(path, value)
        elif name == "missing_payload":
            sca = json.loads(
                (
                    mutated / "workload/runtime/runs/c0/sca_cfg.json"
                ).read_text(encoding="utf-8")
            )
            consumer = first_path_record(sca)["path"]
            relative = consumer[len(RUNTIME_PREFIX) :]
            (mutated / "workload/runtime" / relative).unlink()
        elif name == "wrong_declared_112":
            manifest_path = mutated / "package_manifest.json"
            value = json.loads(manifest_path.read_text(encoding="utf-8"))
            value["path_length_budget"][
                "longest_projected_relative_path_chars"
            ] = 112
            write_json(manifest_path, value)
        elif name == "external_workroot":
            runner_path = mutated / "PREPARE_AND_RUN.sh"
            text = runner_path.read_text(encoding="utf-8")
            text = text.replace(
                'work_root=""',
                'work_root=""\nwork_root="/tmp/external_pkg_state"',
                1,
            )
            runner_path.write_text(text, encoding="utf-8", newline="\n")
        elif name == "new_root_entry":
            mutated_harness["scenarios"]["normal"][
                "root_direct_entries_after"
            ].append({"name": "work_root", "type": "directory"})
            mutated_harness["scenarios"]["normal"][
                "root_exact_set_unchanged"
            ] = False
        elif name == "late_finalizer":
            runner_path = mutated / "PREPARE_AND_RUN.sh"
            text = runner_path.read_text(encoding="utf-8")
            arm = "trap 'finalize $?' EXIT\n"
            text = text.replace(arm, "", 1)
            anchor = 'if [ "$#" -ne 1 ]; then\n'
            text = text.replace(anchor, anchor + arm, 1)
            runner_path.write_text(text, encoding="utf-8", newline="\n")
        elif name == "fixed_result_drift":
            contract_path = (
                mutated / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
            )
            value = json.loads(contract_path.read_text(encoding="utf-8"))
            value["fixed_result_root"] = "/tmp/result"
            write_json(contract_path, value)
        elif name == "wrong_sca_d_prefix":
            path = mutated / "workload/runtime/runs/c0/sca_cfg_D.json"
            value = json.loads(path.read_text(encoding="utf-8"))
            first_path_record(value)["path"] = (
                f"{RUNTIME_PREFIX}runs/c0/install/bad_D.txt"
            )
            write_json(path, value)
        mutated_zip = case_root / f"{PACKAGE_ID}.zip"
        deterministic_zip(mutated, mutated_zip)
        mutated_harness["derived_from_zip_sha256"] = sha256(mutated_zip)
        mutated_harness["runner_member_sha256"] = sha256(
            mutated / "PREPARE_AND_RUN.sh"
        )
        harness_path = case_root / "harness.json"
        write_json(harness_path, mutated_harness)
        report = validate_layout(
            mutated_zip, harness_path, LAYOUT_HELPER
        )
        results[name] = {
            "pass": report["pass"],
            "errors": report["errors"],
            "expected_error": expected_error,
            "valid": (
                not report["pass"]
                and any(
                    expected_error in error for error in report["errors"]
                )
            ),
        }
    return {
        "cases": results,
        "valid": all(item["valid"] for item in results.values()),
    }


def profile_compare() -> dict[str, Any]:
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    expected = {
        "core_identity_bootstrap": "blocking_applicable",
        "runner_control_flow": "blocking_applicable",
        "package_local_hdl": "not_applicable",
        "materialized_config": "blocking_applicable",
        "diagnostic_semantics": "not_applicable",
        "return_result_contract": "blocking_applicable",
        "final_zip_content": "blocking_applicable",
        "runtime_layout": "blocking_applicable",
        "storage_rotation": "blocking_applicable",
        "intermediate_report_format": "record_only",
    }
    observed = {
        row["gate_id"]: row["disposition"]
        for row in profile.get("gate_dispositions", [])
    }
    return {
        "profile_path": str(BUILD_PROFILE),
        "profile_sha256": sha256(BUILD_PROFILE),
        "profile_contract_valid": profile.get("contract_valid"),
        "expected_dispositions": expected,
        "observed_dispositions": observed,
        "match": observed == expected,
        "shadow_only": profile.get("mode") == "SHADOW_ONLY_NEXT_FRESH",
        "family_validator_remains_authoritative": True,
    }


def main() -> int:
    for path in (HARNESS_REPORT, SHARED_REPORT, REPORT):
        if path.exists():
            raise AuditError(f"refusing to overwrite audit output: {path}")
    if not all(
        path.is_file()
        for path in (
            ZIP_PATH,
            SIDECAR,
            SOURCE_ZIP,
            BUILD_REPORT,
            BUILD_PROFILE,
            BASH,
        )
    ):
        raise AuditError("p14 audit inputs are missing")
    with tempfile.TemporaryDirectory(prefix=".p14_", dir=ROOT) as temporary:
        temp_root = Path(temporary)
        package = safe_extract(
            ZIP_PATH, temp_root / "extract", PACKAGE_ID
        )
        static = static_audit(package)
        frozen = frozen_surface_audit()
        runtime = exact_runtime_audit(
            package, temp_root / "exact_runtime"
        )
        scenario_values = {
            name: run_runner_scenario(
                package, temp_root / "runner", name
            )
            for name in (
                "normal",
                "preflight_fail",
                "compile_fail",
                "HUP",
                "INT",
                "TERM",
                "missing_parent",
            )
        }
        harness = shared_harness(scenario_values)
        write_json(HARNESS_REPORT, harness)
        shared = validate_layout(
            ZIP_PATH, HARNESS_REPORT, LAYOUT_HELPER
        )
        write_json(SHARED_REPORT, shared)
        negatives = shared_negative_controls(
            package, harness, temp_root / "shared_negatives"
        )
    profile = profile_compare()
    valid = (
        static["valid"]
        and frozen["valid"]
        and runtime["valid"]
        and all(item["valid"] for item in scenario_values.values())
        and shared["pass"]
        and not shared["errors"]
        and negatives["valid"]
        and profile["profile_contract_valid"] is True
        and profile["match"]
    )
    result = {
        "schema": (
            "conv-native-four-lane-p14-install-final-zip-audit-v1"
        ),
        "status": (
            "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_AUDIT_FAILED"
        ),
        "valid": valid,
        "package_identity": PACKAGE_ID,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "source_p13_zip_sha256": sha256(SOURCE_ZIP),
        "static_zip_audit": static,
        "frozen_surface_audit": frozen,
        "exact_runtime_path_budget_and_preflight": runtime,
        "exact_runner_harness": scenario_values,
        "runtime_layout_harness": {
            "path": str(HARNESS_REPORT),
            "bytes": HARNESS_REPORT.stat().st_size,
            "sha256": sha256(HARNESS_REPORT),
            "schema_valid": True,
        },
        "shared_runtime_layout": {
            "path": str(SHARED_REPORT),
            "bytes": SHARED_REPORT.stat().st_size,
            "sha256": sha256(SHARED_REPORT),
            "pass": shared["pass"],
            "errors": len(shared["errors"]),
        },
        "shared_negative_controls": negatives,
        "shadow_profile_compare": profile,
        "release_gate_matrix": {
            "core_identity_bootstrap": {
                "disposition": "blocking_applicable",
                "pass": static["valid"] and frozen["valid"],
            },
            "runner_control_flow": {
                "disposition": "blocking_applicable",
                "pass": runtime["valid"]
                and all(item["valid"] for item in scenario_values.values()),
            },
            "package_local_hdl": {
                "disposition": "not_applicable",
                "pass": True,
                "reason": "all package-local HDL/TB bytes are frozen",
            },
            "materialized_config": {
                "disposition": "blocking_applicable",
                "pass": static["sca_read_inputs_all_open_exact"]
                and static["sca_d_output_prefix_valid"],
                "scope": "mechanical SCA_D output-path prefix only",
            },
            "diagnostic_semantics": {
                "disposition": "not_applicable",
                "pass": True,
                "reason": "observer/parser/predicate bytes are frozen",
            },
            "return_result_contract": {
                "disposition": "blocking_applicable",
                "pass": all(
                    item["valid"] for item in scenario_values.values()
                ),
            },
            "final_zip_content": {
                "disposition": "blocking_applicable",
                "pass": valid,
            },
            "runtime_layout": {
                "disposition": "blocking_applicable",
                "pass": shared["pass"] and negatives["valid"],
                "rule_id": (
                    "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001"
                ),
            },
            "storage_rotation": {
                "disposition": "blocking_applicable",
                "pass": None,
                "reason": "performed atomically after final-ZIP audit",
            },
            "intermediate_report_format": {
                "disposition": "record_only",
                "pass": True,
            },
        },
        "server_action": False,
        "claim_boundary": (
            "Exact local final-ZIP, install-subtree layout, SCA open paths, "
            "path-budget arithmetic, early/shared finalizer, fixed-result "
            "publisher and safe compile/simulator stubs only. No production "
            "compile, DUT simulation, natural terminal, formal 320D, "
            "numeric correctness, performance, E3, E4 or E5 claim."
        ),
    }
    write_json(REPORT, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "valid": valid,
                "zip_sha256": result["zip_sha256"],
                "shared_pass": shared["pass"],
                "shared_errors": len(shared["errors"]),
                "negative_controls_pass": negatives["valid"],
                "profile_match": profile["match"],
                "report": str(REPORT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
