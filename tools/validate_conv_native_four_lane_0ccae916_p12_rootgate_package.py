#!/usr/bin/env python3
"""Final ZIP and exact-runner harness audit for native Conv p12."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p11f_pubord"
PACKAGE_ID = "r5_n4_0cc_p12_rootgate"
SOURCE_SHA256 = (
    "3198b62bf609f213f9355f8ddaa45df90dd05ea61443fe859247d0b9f3cd0acf"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "pending"
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p11f_rootgate_replacement"
)
ZIP_PATH = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
SIDECAR = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_audit.json"
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\python\python.exe"
)
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PRODUCTION_RESULT_ROOT = "/home/panqs/ndp/simresult"


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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
    value = path.resolve().as_posix()
    if len(value) >= 3 and value[1:3] == ":/":
        return f"/{value[0].lower()}{value[2:]}"
    return value


def direct_set(root: Path) -> list[dict[str, str]]:
    records = []
    for child in root.iterdir():
        mode = child.lstat().st_mode
        if stat.S_ISLNK(mode):
            kind = "symlink"
        elif stat.S_ISDIR(mode):
            kind = "directory"
        elif stat.S_ISREG(mode):
            kind = "file"
        else:
            kind = "other"
        records.append({"name": child.name, "type": kind})
    return sorted(records, key=lambda item: os.fsencode(item["name"]))


def safe_extract(zip_path: Path, target: Path) -> Path:
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
                or pure.parts[0] != PACKAGE_ID
            ):
                raise AuditError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:])
            output = target.joinpath(PACKAGE_ID, *relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(info))
    return target / PACKAGE_ID


def zip_payloads(
    zip_path: Path, expected_root: str
) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if info.is_dir():
                continue
            if not pure.parts or pure.parts[0] != expected_root:
                raise AuditError(f"unexpected ZIP root: {info.filename}")
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            result[relative] = archive.read(info)
    return result


def validate_frozen_surfaces() -> dict[str, Any]:
    source = zip_payloads(SOURCE_ZIP, SOURCE_ID)
    successor = zip_payloads(ZIP_PATH, PACKAGE_ID)
    frozen_prefixes = (
        "workload/runtime/",
        "diagnostics/",
        "tb_probe/",
    )
    frozen_paths = sorted(
        path for path in source if path.startswith(frozen_prefixes)
    )
    frozen_mismatch = [
        path
        for path in frozen_paths
        if successor.get(path) != source.get(path)
    ]
    unchanged_nonmetadata = sorted(
        path
        for path in source
        if path
        not in {
            "PREPARE_AND_RUN.sh",
            "README.md",
            "TEST_PACKAGE_MANIFEST.json",
            "package_manifest.json",
            "package_tools/fixed_simresult_publisher.py",
        }
    )
    nonmetadata_mismatch = [
        path
        for path in unchanged_nonmetadata
        if successor.get(path) != source.get(path)
    ]
    additions = sorted(set(successor) - set(source))
    removals = sorted(set(source) - set(successor))
    p11_runner = source["PREPARE_AND_RUN.sh"].decode("utf-8")
    p12_runner = successor["PREPARE_AND_RUN.sh"].decode("utf-8")
    timeout_tokens = [
        "2h make",
        "12h \"$simv\"",
        "+RETURN_OBS_STALL_CYCLES=1048576",
        "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
        "+N4T_NO_PROGRESS_CYCLES=1048576",
        "+N4P_EVENT_LIMIT=64",
    ]
    timeout_equal = all(
        p11_runner.count(token) == p12_runner.count(token)
        and p11_runner.count(token) > 0
        for token in timeout_tokens
    )
    return {
        "source_zip_sha256": sha256(SOURCE_ZIP),
        "source_identity_valid": sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "frozen_path_count": len(frozen_paths),
        "frozen_mismatch": frozen_mismatch,
        "unchanged_nonmetadata_mismatch": nonmetadata_mismatch,
        "additions": additions,
        "removals": removals,
        "timeout_tokens_equal": timeout_equal,
        "valid": (
            sha256(SOURCE_ZIP) == SOURCE_SHA256
            and not frozen_mismatch
            and not nonmetadata_mismatch
            and additions
            == ["package_tools/ndp_root_toplevel_exact_set_gate.py"]
            and not removals
            and timeout_equal
        ),
    }


STUB_RUNTIME = r'''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def option(name):
    index = sys.argv.index(name)
    return Path(sys.argv[index + 1])

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")

command = sys.argv[1]
if command in {"path-budget", "preflight", "verify-install"}:
    print(json.dumps({"valid": True, "command": command}))
elif command == "compile-identity":
    write(option("--output"), {"valid": True, "stub": True})
elif command in {"feature-binding", "qualify-run"}:
    write(option("--output"), {"valid": True, "command": command})
elif command == "analyze":
    package = option("--package-root")
    evidence = option("--evidence-root")
    run = option("--run-root")
    write(evidence / "SERVER_RESULT_GATE.json", {
        "status": "LOCAL_RUNNER_STUB_ONLY",
        "valid": False,
        "claim_boundary": "no DUT",
    })
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    roots = {"package": package, "evidence": evidence, "run": run}
    for item in manifest["return_allowlist"]:
        if not item["required"]:
            continue
        path = roots[item["source_root"]] / item["source_path"]
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            path.write_text("{}\n", encoding="utf-8")
        else:
            path.write_text("stub\n", encoding="utf-8")
    print(json.dumps({"valid": True, "command": command}))
else:
    raise SystemExit(2)
'''


STUB_FINALIZER = r'''#!/usr/bin/env python3
import json
import sys
from pathlib import Path
output = Path(sys.argv[sys.argv.index("--output") + 1])
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps({"valid": False, "stub": True}) + "\n")
'''


STUB_GUARD = r'''#!/usr/bin/env python3
print('{"valid": true, "stub": true}')
'''


STUB_MAKE = r'''#!/usr/bin/env bash
set -u
run_dir=
for arg in "$@"; do
  case "$arg" in RUN_DIR=*) run_dir="${arg#RUN_DIR=}";; esac
done
[ -n "$run_dir" ] || exit 90
case "${STUB_MODE:-normal}" in
  compile_fail) exit 42 ;;
  root_dir) mkdir -p -- runner_leak_dir ;;
  root_file) printf 'leak\n' > runner_leak_file ;;
esac
mkdir -p -- "$run_dir/sim_results"
cat > "$run_dir/sim_results/simv" <<'EOF'
#!/usr/bin/env bash
set -u
case "${STUB_MODE:-normal}" in
  hup|int|term)
    : > "${STUB_MARKER:?}"
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


def prepare_harness(
    package: Path, scenario_root: Path
) -> tuple[Path, Path, Path, dict[str, str]]:
    local_package = scenario_root / PACKAGE_ID
    shutil.copytree(package, local_package)
    result_root = scenario_root / "simresult"
    runner = local_package / "PREPARE_AND_RUN.sh"
    publisher = (
        local_package / "package_tools/fixed_simresult_publisher.py"
    )
    runner_text = runner.read_text(encoding="utf-8").replace(
        PRODUCTION_RESULT_ROOT, "../simresult"
    )
    runner_text = runner_text.replace(
        '[ "$resolved_result_root" = "../simresult" ] || exit 9',
        '[ -n "$resolved_result_root" ] || exit 9',
    )
    runner.write_text(runner_text, encoding="utf-8", newline="\n")
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
    runtime = (
        local_package
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    runtime.write_text(STUB_RUNTIME, encoding="utf-8", newline="\n")
    guard = (
        local_package
        / "package_tools/node0004_package_observer_guard.py"
    )
    guard.write_text(STUB_GUARD, encoding="utf-8", newline="\n")
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
    server_root.mkdir()
    (server_root / "existing_dir").mkdir()
    (server_root / "existing_file.txt").write_text(
        "stable\n", encoding="utf-8"
    )
    (server_root / "Makefile.tb_NDP_Top_new_phy").write_text(
        "stub\n", encoding="utf-8"
    )
    marker = scenario_root / "sim_started.marker"
    env = dict(os.environ)
    env["PATH"] = f"{posix_path(stub_bin)}:/usr/bin:/bin"
    env["STUB_MARKER"] = posix_path(marker)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return local_package, server_root, result_root, env


def read_return_gate(return_zip: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(return_zip) as archive:
        gate_names = [
            name
            for name in archive.namelist()
            if name.endswith("/evidence/ndp_root_toplevel_gate.json")
        ]
        manifest_names = [
            name
            for name in archive.namelist()
            if name.endswith("/RETURN_MANIFEST.json")
        ]
        if len(gate_names) != 1 or len(manifest_names) != 1:
            raise AuditError("return root-gate evidence exact-set differs")
        gate = json.loads(archive.read(gate_names[0]).decode("utf-8"))
        manifest = json.loads(
            archive.read(manifest_names[0]).decode("utf-8")
        )
    return gate, manifest


def run_scenario(
    package: Path, harness_root: Path, mode: str
) -> dict[str, Any]:
    scenario_root = harness_root / mode
    scenario_root.mkdir(parents=True)
    local_package, server_root, result_root, env = prepare_harness(
        package, scenario_root
    )
    env["STUB_MODE"] = mode
    before = direct_set(server_root)
    runner = local_package / "PREPARE_AND_RUN.sh"
    runner_posix = posix_path(runner)
    server_posix = posix_path(server_root)
    if mode in {"hup", "int", "term"}:
        signal_name = {"hup": "HUP", "int": "INT", "term": "TERM"}[mode]
        signal_anchor = "sim_pid=$!\n(\n  while kill -0"
        signal_injection = (
            "sim_pid=$!\n"
            f"( sleep 0.2; kill -{signal_name} \"$$\" ) &\n"
            "(\n  while kill -0"
        )
        runner_text = runner.read_text(encoding="utf-8")
        if runner_text.count(signal_anchor) != 1:
            raise AuditError("signal injection anchor differs")
        runner.write_text(
            runner_text.replace(signal_anchor, signal_injection),
            encoding="utf-8",
            newline="\n",
        )
        completed = subprocess.run(
            [str(BASH), runner_posix, server_posix],
            cwd=local_package,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
        )
    else:
        completed = subprocess.run(
            [str(BASH), runner_posix, server_posix],
            cwd=local_package,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=60,
            check=False,
        )
    after = direct_set(server_root)
    return_zip = result_root / f"{PACKAGE_ID}_return.zip"
    sidecar = Path(f"{return_zip}.sha256")
    if not return_zip.is_file() or not sidecar.is_file():
        preflight_debug = []
        if result_root.is_dir():
            for candidate in result_root.glob(
                f".{PACKAGE_ID}.run.*/evidence/publication_preflight.json"
            ):
                preflight_debug.append(
                    candidate.read_text(
                        encoding="utf-8", errors="replace"
                    )
                )
        raise AuditError(
            f"{mode} did not publish fixed return: code={completed.returncode} "
            f"stdout={(completed.stdout or '')[-500:]} "
            f"stderr={(completed.stderr or '')[-500:]} "
            f"publication_preflight={preflight_debug}"
        )
    tokens = sidecar.read_text(encoding="ascii").split()
    sidecar_valid = tokens == [sha256(return_zip), return_zip.name]
    gate, return_manifest = read_return_gate(return_zip)
    expected_unchanged = mode not in {"root_dir", "root_file"}
    return {
        "mode": mode,
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-1000:],
        "stderr_tail": completed.stderr[-1000:],
        "root_before": before,
        "root_after": after,
        "python_root_unchanged": before == after,
        "gate": gate,
        "return_manifest_root_gate": return_manifest.get(
            "ndp_root_toplevel_gate"
        ),
        "fixed_return_zip": str(return_zip),
        "fixed_return_sha256": sha256(return_zip),
        "sidecar_valid": sidecar_valid,
        "duplicate_under_server_root": (
            server_root / f"{PACKAGE_ID}_return.zip"
        ).exists(),
        "valid": (
            sidecar_valid
            and gate.get("ndp_root_toplevel_unchanged")
            is expected_unchanged
            and gate.get("valid") is expected_unchanged
            and (before == after) is expected_unchanged
            and return_manifest.get("ndp_root_toplevel_gate", {}).get(
                "ndp_root_toplevel_unchanged"
            )
            is expected_unchanged
            and not (
                server_root / f"{PACKAGE_ID}_return.zip"
            ).exists()
            and (
                completed.returncode == 0
                if mode == "normal"
                else completed.returncode != 0
            )
        ),
    }


def helper_negatives(package: Path, target: Path) -> dict[str, Any]:
    target.mkdir(parents=True)
    helper = (
        package / "package_tools/ndp_root_toplevel_exact_set_gate.py"
    )
    root = target / "helper_root"
    root.mkdir()
    (root / "stable").mkdir()
    pre = target / "pre.json"
    post = target / "post.json"
    manifest = target / "manifest.json"
    base_manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    write_json(manifest, base_manifest)

    def capture(path: Path) -> None:
        completed = subprocess.run(
            [
                str(PYTHON),
                str(helper),
                "snapshot",
                "--server-root",
                str(root),
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        path.write_text(completed.stdout, encoding="utf-8", newline="\n")

    capture(pre)
    capture(post)
    unchanged_output = target / "unchanged.json"
    unchanged = subprocess.run(
        [
            str(PYTHON),
            str(helper),
            "compare",
            "--pre",
            str(pre),
            "--post",
            str(post),
            "--manifest",
            str(manifest),
            "--output",
            str(unchanged_output),
        ],
        check=False,
    )
    missing_manifest = dict(base_manifest)
    missing_contract = dict(
        missing_manifest["ndp_root_toplevel_contract"]
    )
    missing_contract["root_internal_preexisting_parents"] = [
        "declared_but_missing"
    ]
    missing_manifest["ndp_root_toplevel_contract"] = missing_contract
    missing_manifest_path = target / "missing_parent_manifest.json"
    write_json(missing_manifest_path, missing_manifest)
    missing = subprocess.run(
        [
            str(PYTHON),
            str(helper),
            "validate-parents",
            "--server-root",
            str(root),
            "--manifest",
            str(missing_manifest_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    tampered = json.loads(pre.read_text(encoding="utf-8"))
    tampered["entries"].append(
        {"name": "forged", "type": "directory"}
    )
    tampered_path = target / "tampered_pre.json"
    write_json(tampered_path, tampered)
    tampered_output = target / "tampered_output.json"
    tampered_run = subprocess.run(
        [
            str(PYTHON),
            str(helper),
            "compare",
            "--pre",
            str(tampered_path),
            "--post",
            str(post),
            "--manifest",
            str(manifest),
            "--output",
            str(tampered_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    conjunction = (
        '[ "$final" -ne 0 ] || [ "$root_gate_status" -eq 0 ] '
        '|| final="$root_gate_status"'
    )
    mutation = runner.replace(conjunction, "# removed gate conjunction")
    return {
        "unchanged_compare_exit": unchanged.returncode,
        "missing_declared_parent_exit": missing.returncode,
        "tampered_pre_receipt_exit": tampered_run.returncode,
        "exact_runner_has_drift_exit_conjunction": conjunction in runner,
        "ignored_drift_mutation_rejected": conjunction not in mutation,
        "valid": (
            unchanged.returncode == 0
            and missing.returncode != 0
            and tampered_run.returncode != 0
            and conjunction in runner
            and conjunction not in mutation
        ),
    }


def static_zip_audit(package: Path) -> dict[str, Any]:
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    observed = {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }
    sidecar_tokens = SIDECAR.read_text(encoding="ascii").split()
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    pre_index = runner.index('pre_snapshot_json="$(python3 "$root_gate"')
    first_mkdir_index = runner.index('mkdir -p -- "$result_root"')
    post_index = runner.index(
        'post_snapshot_json="$(python3 "$root_gate"'
    )
    publication_index = runner.index(
        'publication_json="$(python3 "$publisher"'
    )
    production_fixed_literals = (
        runner.count(PRODUCTION_RESULT_ROOT),
        (
            package / "package_tools/fixed_simresult_publisher.py"
        )
        .read_text(encoding="utf-8")
        .count(PRODUCTION_RESULT_ROOT),
    )
    return {
        "zip_sha256": sha256(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "sidecar_valid": sidecar_tokens
        == [sha256(ZIP_PATH), ZIP_PATH.name],
        "manifest_exact_set_valid": manifest.get("files") == observed,
        "package_identity_valid": (
            manifest.get("package_identity") == PACKAGE_ID
            and manifest.get("install_name") == SOURCE_ID
        ),
        "pre_snapshot_before_first_write": pre_index < first_mkdir_index,
        "post_snapshot_before_publication": post_index < publication_index,
        "production_result_path_literal_counts": production_fixed_literals,
        "production_result_path_nonconfigurable": production_fixed_literals[
            0
        ]
        > 0
        and production_fixed_literals[1] > 0,
        "valid": (
            sidecar_tokens == [sha256(ZIP_PATH), ZIP_PATH.name]
            and manifest.get("files") == observed
            and manifest.get("package_identity") == PACKAGE_ID
            and manifest.get("install_name") == SOURCE_ID
            and pre_index < first_mkdir_index
            and post_index < publication_index
            and production_fixed_literals[0] > 0
            and production_fixed_literals[1] > 0
        ),
    }


def main() -> int:
    if REPORT.exists():
        raise AuditError("refusing to overwrite p12 final ZIP audit")
    if (
        not ZIP_PATH.is_file()
        or not SIDECAR.is_file()
        or not SOURCE_ZIP.is_file()
    ):
        raise AuditError("p12/source ZIP inputs are missing")
    with tempfile.TemporaryDirectory(
        prefix=".p12_", dir=ROOT
    ) as temp:
        temp_root = Path(temp)
        package = safe_extract(ZIP_PATH, temp_root / "extract")
        static = static_zip_audit(package)
        frozen = validate_frozen_surfaces()
        helper = helper_negatives(package, temp_root / "helper")
        scenarios = [
            run_scenario(package, temp_root / "runner", mode)
            for mode in (
                "normal",
                "compile_fail",
                "hup",
                "int",
                "term",
                "root_dir",
                "root_file",
            )
        ]
    valid = (
        static["valid"]
        and frozen["valid"]
        and helper["valid"]
        and all(item["valid"] for item in scenarios)
    )
    result = {
        "schema": "conv-native-four-lane-p12-rootgate-final-zip-audit-v1",
        "status": (
            "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_AUDIT_FAILED"
        ),
        "valid": valid,
        "package_identity": PACKAGE_ID,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "source_p11f_zip_sha256": sha256(SOURCE_ZIP),
        "static_zip_audit": static,
        "frozen_surface_audit": frozen,
        "root_gate_helper_negatives": helper,
        "exact_runner_harness": scenarios,
        "release_gate_matrix": {
            "core_always": "PASS",
            "runner": "PASS" if all(item["valid"] for item in scenarios) else "FAIL",
            "package_local_hdl": "RECEIPT_REUSE",
            "materialized_config": "RECEIPT_REUSE",
            "diagnostic_semantics": "RECEIPT_REUSE",
            "return_result": "PASS",
        },
        "server_action": False,
        "claim_boundary": (
            "isolated exact-runner control-flow and package audit only; "
            "no DUT execution, natural terminal, formal 320D, E3/E4/E5, "
            "numeric correctness, or performance claim"
        ),
    }
    write_json(REPORT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
