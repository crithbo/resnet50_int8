#!/usr/bin/env python3
"""Aggregate current exact-ZIP, first-fresh, runtime and storage gates for p47."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p47_tbvcdcone"
OLD_ID = "r5_n4_0cc_p46_nativeflow"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release"
ZIP = OUT / f"{PACKAGE_ID}.zip"
TREE = OUT / "build" / PACKAGE_ID
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    gate_names = [
        "mode_selector_tree", "mode_selector_zip", "tb_vcd_tree", "tb_vcd_final_zip",
        "hdl_lexical_tree", "hdl_lexical_zip", "runner_tree", "runner_zip",
        "native_preflight", "post_sim_final_zip", "runtime_layout", "full_hdl_source_bound",
        "runtime_six_exit", "streaming_retention", "first_fresh_validation",
    ]
    gate_receipts = []
    errors: list[str] = []
    for name in gate_names:
        path = OUT / "gates" / f"{name}.json"
        if not path.is_file():
            errors.append(f"gate absent: {name}")
            continue
        value = load(path)
        if value.get("pass") is not True:
            errors.append(f"gate failed: {name}")
        gate_receipts.append({"gate": name, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "pass": value.get("pass")})

    profile = load(OUT / "server_package_build_profile.json")
    if profile.get("contract_valid") is not True or profile.get("preflight", {}).get("pass") is not True:
        errors.append("staging aggregate build profile failed")
    if profile.get("aggregate_prebuild", {}).get("coverage_complete") is not True:
        errors.append("staging aggregate cheap-gate coverage incomplete")

    manifest = load(TREE / "package_manifest.json")
    actual_files = {
        item.relative_to(TREE).as_posix(): {"size_bytes": item.stat().st_size, "sha256": sha(item)}
        for item in sorted(path for path in TREE.rglob("*") if path.is_file())
        if item.name != "package_manifest.json"
    }
    if manifest.get("files") != actual_files:
        errors.append("package manifest differs from staging tree")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            errors.append("final ZIP CRC failure")
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if name}
        if roots != {PACKAGE_ID} or len(names) != len(set(names)):
            errors.append("final ZIP root/member uniqueness failure")
        if any(name.lower().endswith((".vcd", ".vpd", ".fsdb", ".fst")) for name in names):
            errors.append("runtime waveform member was packaged")

    tests = [
        "tests.test_server_diagnostic_mode_selector",
        "tests.test_server_tb_vcd_bounded_causal_cone",
        "tests.test_server_tb_vcd_runtime_supervision",
        "tests.test_server_tb_vcd_retention_analysis",
        "tests.test_server_package_local_hdl_lexical",
        "tests.test_server_runner_return_resilience",
        "tests.test_server_runtime_preflight_native_flow",
        "tests.test_server_post_sim_return",
    ]
    test_results = []
    total = 0
    for module in tests:
        result = subprocess.run([str(PYTHON), "-m", "unittest", module], cwd=ROOT, text=True, capture_output=True, check=False)
        combined = result.stdout + result.stderr
        match = re.search(r"Ran (\d+) tests?", combined)
        count = int(match.group(1)) if match else 0
        total += count
        if result.returncode != 0:
            errors.append(f"shared regression failed: {module}")
        test_results.append({"module": module, "exit_code": result.returncode, "test_count": count, "output_tail": combined[-4096:]})

    storage_result = subprocess.run([str(PYTHON), str(ROOT / "tools/manage_server_test_package_storage.py"), "audit", "--root", str(STORAGE)], cwd=ROOT, text=True, capture_output=True, check=False)
    try:
        storage = json.loads(storage_result.stdout)
    except json.JSONDecodeError:
        storage = {}
    if storage_result.returncode != 0 or storage.get("pass") is not True:
        errors.append("prepublication storage audit failed")
    pending = storage.get("pending_by_family", {}).get("conv_native_four_lane", [])
    if pending != [OLD_ID]:
        errors.append(f"protected predecessor pending set differs: {pending}")

    checks = {
        "all_gate_receipts_pass": len(gate_receipts) == len(gate_names) and all(item["pass"] is True for item in gate_receipts),
        "staging_aggregate_pass": profile.get("contract_valid") is True and profile.get("preflight", {}).get("pass") is True,
        "manifest_exact": manifest.get("files") == actual_files,
        "deterministic_zip": ZIP.stat().st_size == (OUT / f"{PACKAGE_ID}.repeat.zip").stat().st_size and sha(ZIP) == sha(OUT / f"{PACKAGE_ID}.repeat.zip"),
        "shared_regressions_pass": all(item["exit_code"] == 0 for item in test_results) and total >= 75,
        "storage_clean_prepublication": storage.get("pass") is True and pending == [OLD_ID],
        "server_actions_absent": manifest.get("server_actions_performed") == [],
    }
    errors.extend(key for key, value in checks.items() if not value and key not in errors)
    report = {
        "schema": "conv-native-p47-final-release-audit-v1",
        "package_id": PACKAGE_ID,
        "activation_epoch": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437",
        "pass": not errors,
        "checks": checks,
        "gate_receipts": gate_receipts,
        "shared_regressions": {"pass": all(item["exit_code"] == 0 for item in test_results), "total_tests": total, "results": test_results},
        "storage_prepublication": {"pass": storage.get("pass"), "counts": storage.get("counts"), "pending_by_family": storage.get("pending_by_family")},
        "exact_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        "errors": errors,
        "claim_boundary": "Local construction/gates/storage readiness only; no upload, connection, production compile/simulation, root cause, natural terminal, formal-D or E3/E4/E5 claim.",
    }
    write(OUT / "gates/final_zip_release_audit.json", report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
