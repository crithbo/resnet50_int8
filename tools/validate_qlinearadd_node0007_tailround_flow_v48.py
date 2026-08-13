"""Validate the exact QAdd v48 diagnostic package and emit local receipts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import validate_qlinearadd_node0007_tailround_flow_v47 as v47


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_flow_v48"
SOURCE_NAME = "r5_qadd_n7_tailround_flow_v47"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v48-package"
ZIP = OUT / f"{NAME}.zip"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v47-package/r5_qadd_n7_tailround_flow_v47.zip"
REPORT = OUT / "family_validation.json"
HARNESS = OUT / "runtime_layout_harness.json"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
CHANGED = {"PREPARE_AND_RUN.sh", "README.md", "TEST_PACKAGE_MANIFEST.json", "SERVER_RUNTIME_LAYOUT_CONTRACT.json"}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("CRC failed")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or info.filename in seen:
                raise ValueError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename); roots.add(pure.parts[0])
            if not info.is_dir():
                files[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(info)
    if roots != {root}:
        raise ValueError(f"root differs: {sorted(roots)}")
    return files, json.loads(files["TEST_PACKAGE_MANIFEST.json"])


def normalize(value: bytes) -> bytes:
    try:
        return value.decode("utf-8").replace(NAME, SOURCE_NAME).encode("utf-8")
    except UnicodeDecodeError:
        return value


def runner_visibility_unit(runner: str) -> dict[str, Any]:
    helper = re.search(r"(?ms)^runner_fail\(\) \{.*?^\}", runner)
    if helper is None:
        return {"pass": False, "reason": "helper_missing"}
    program = "#!/usr/bin/env bash\nset -u\npackage_id='" + NAME + "'\n" + helper.group(0) + "\nrunner_fail 37 'isolated changed-surface failure receipt'\n"
    with tempfile.TemporaryDirectory(prefix="q48-runner-unit-") as raw:
        path = Path(raw) / "unit.sh"
        path.write_text(program, encoding="utf-8", newline="\n")
        result = subprocess.run([str(BASH), str(path)], capture_output=True, text=True, check=False)
    expected = f"RUNNER_ERROR package={NAME} code=37 message=isolated changed-surface failure receipt"
    return {"pass": result.returncode == 37 and expected in result.stderr and result.stdout == "", "exit_code": result.returncode, "stderr": result.stderr, "stdout": result.stdout, "program_sha256": sha_bytes(program.encode())}


def harness(zip_sha: str, runner_sha: str) -> dict[str, Any]:
    source_path = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fullchain-v46-returnfix-package/runtime_layout_harness.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    rows = {}
    for index, (scenario, row) in enumerate(sorted(source["scenarios"].items()), 1):
        dynamic = f"/home/panqs/ndp/simresult/{NAME}_r17861104753443430{index:02d}_37229{index:02d}_return.zip"
        rows[scenario] = {
            **row,
            "command": f"CHANGED_SURFACE_RECEIPT_REUSE scenario={scenario}; exact v48 runner visibility unit and package checks are separate",
            "cwd": "$fresh_extract_parent",
            "return_zip": dynamic,
            "return_sidecar": dynamic + ".sha256",
        }
    return {"schema": "server_package_runtime_layout_harness_v1", "derived_from_zip_sha256": zip_sha, "runner_member_sha256": runner_sha, "fixed_result_root": "/home/panqs/ndp/simresult", "scenarios": rows, "claim_boundary": "install-only V2 layout scenarios are byte-semantics receipt reuse; exact v48 changed runner_fail surface is directly executed; no DUT/server action"}


def main() -> int:
    files, manifest = read_zip(ZIP, NAME)
    source, _ = read_zip(SOURCE, SOURCE_NAME)
    records = manifest.get("files", {})
    inventory = set(records) == (set(files) - {"TEST_PACKAGE_MANIFEST.json"}) and all(row.get("size_bytes") == len(files[name]) and row.get("sha256") == sha_bytes(files[name]) for name, row in records.items())
    normalized_changed = sorted(name for name in set(files) | set(source) if name == "TEST_PACKAGE_MANIFEST.json" or name not in files or name not in source or normalize(files[name]) != source[name])
    runner = files["PREPARE_AND_RUN.sh"].decode()
    tail = files["tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    with tempfile.NamedTemporaryFile(prefix="q48-runner-", suffix=".sh", delete=False, mode="w", encoding="utf-8") as stream:
        runner_path = Path(stream.name); stream.write(runner)
    bash = subprocess.run([str(BASH), "-n", str(runner_path)], capture_output=True, text=True, check=False); runner_path.unlink()
    with tempfile.TemporaryDirectory(prefix="q48-py-") as raw:
        paths = []
        for name, payload in files.items():
            if name.startswith("package_tools/") and name.endswith(".py"):
                path = Path(raw) / Path(name).name; path.write_bytes(payload); paths.append(str(path))
        py = subprocess.run([str(PYTHON), "-m", "py_compile", *paths], capture_output=True, text=True, check=False)
    closure = v47.hdl_closure(tail); xmr = v47.xmr_gate(tail); frontend = v47.hdl_frontend(native, tail); negatives = v47.negative_controls(tail)
    visibility = runner_visibility_unit(runner)
    checks = {
        "zip_manifest_exact": inventory,
        "identity": manifest.get("install_name") == NAME,
        "changed_surface_exact": normalized_changed == sorted(CHANGED),
        "frozen_functional_diagnostic_payload": all(name in CHANGED or normalize(files[name]) == source[name] for name in files if name in source),
        "runner_bash_syntax": bash.returncode == 0,
        "package_python_syntax": py.returncode == 0,
        "runner_error_visibility_unit": visibility["pass"],
        "collector_cfg_root_return_zip_bound": '--cfg-root "$cfg_root" --return-zip "$return_zip"' in runner,
        "canonical_qualified_only": '"buf4_wr"' not in files["package_tools/qlinearadd_node0007_tailround_flow_canonical_v47.py"].decode().split("QUALIFIED =", 1)[1].split(")", 1)[0],
        "hdl_closure": closure["valid"],
        "hdl_xmr": xmr["valid"],
        "hdl_frontend": frontend["valid"],
        "hdl_negatives": negatives["all_fail_closed"],
        "timeout_frozen_8h": "--kill-after=30s 8h" in runner,
        "fixed_result": 'result_root="/home/panqs/ndp/simresult"' in runner,
        "runtime_D_absent": not any(name.startswith("readbacks/") or (name.endswith("matrix_D_linearized_128bit.txt") and not name.startswith("validation/golden/")) for name in files),
    }
    errors = [name for name, value in checks.items() if value is not True]
    write_json(HARNESS, harness(sha(ZIP), sha_bytes(files["PREPARE_AND_RUN.sh"])))
    report = {"schema": "qadd-tailround-flow-v48-family-validation-v1", "valid": not errors, "errors": errors, "checks": checks, "zip": {"bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}, "changed_members": normalized_changed, "expected_changed_members": sorted(CHANGED), "runner_visibility_unit": visibility, "hdl_scope_revalidation": {"closure": closure, "xmr": xmr, "frontend": frontend, "negative_controls": negatives}, "runner": {"bash_exit": bash.returncode, "bash_stderr": bash.stderr, "python_compile_exit": py.returncode, "python_stderr": py.stderr}, "claim_boundary": "exact v48 ZIP, runner changed surface, inherited diagnostic HDL and frozen functional assets; no DUT/server/terminal/D/E3/E4/E5", "numeric_workload_config_golden_repeated": False, "server_action": False}
    write_json(REPORT, report)
    print(json.dumps({"valid": not errors, "errors": errors, "report": str(REPORT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
