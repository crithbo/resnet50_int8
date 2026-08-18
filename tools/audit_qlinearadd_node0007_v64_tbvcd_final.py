#!/usr/bin/env python3
"""Aggregate staging/current-epoch/exact-final-ZIP gates for QAdd v64."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/qlinearadd_node0007_v64_tb_vcd_fix_release"
PACKAGE = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"
PRIOR = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / "build" / f"{PACKAGE}.zip"
GATE = OUT / "gates/precheck"
FIRST = OUT / "gates/first_fresh"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rec(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def import_base() -> Any:
    path = ROOT / "tools/build_qlinearadd_node0007_v63_tb_vcd.py"
    spec = importlib.util.spec_from_file_location("qadd_v63_zip_helpers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import deterministic ZIP helper")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    reports = {
        "failure_delta_tree": OUT / "gates/failure_delta_tree.json",
        "failure_delta_exact_zip": OUT / "gates/failure_delta_zip.json",
        "mode_selector_tree": GATE / "selector_tree.json",
        "mode_selector_exact_zip": GATE / "selector_zip.json",
        "hdl_lexical_tree": GATE / "lexical_tree.json",
        "hdl_lexical_exact_zip": GATE / "lexical_zip.json",
        "runner_tree": GATE / "runner_tree.json",
        "runner_exact_zip": GATE / "runner_zip.json",
        "native_preflight": GATE / "nativeflow.json",
        "post_sim_return": GATE / "postsim.json",
        "runtime_layout_six_exit": GATE / "runtime_layout.json",
        "shared_tb_vcd_contract": GATE / "vcd_tree.json",
        "full_frontend_scope_state": GATE / "hdl.json",
        "source_bound": GATE / "source_bound.json",
        "first_fresh": FIRST / "validation.json",
    }
    errors: list[str] = []
    for name, path in reports.items():
        if not path.is_file():
            errors.append(f"missing_report:{name}")
        elif load(path).get("pass") is not True:
            errors.append(f"failed_report:{name}")
    profile = load(OUT / "server_package_build_profile.json")
    if profile.get("contract_valid") is not True or profile.get("preflight", {}).get("pass") is not True:
        errors.append("current_build_gate_registry_profile")
    build = load(OUT / "build/build_receipt.json")
    frozen = load(OUT / "frozen_surface_receipt.json")
    if build.get("pass") is not True or build.get("zip", {}).get("sha256") != sha(ZIP):
        errors.append("build_receipt_zip_binding")
    if frozen.get("pass") is not True:
        errors.append("frozen_surface")

    safe_zip = manifest_exact = deterministic = False
    with tempfile.TemporaryDirectory(prefix="qadd-v64-final-") as raw:
        temp = Path(raw)
        with zipfile.ZipFile(ZIP) as archive:
            names = archive.namelist()
            roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
            unsafe = [name for name in names if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts]
            safe_zip = roots == {PACKAGE} and not unsafe and archive.testzip() is None and len(names) == len(set(names))
            archive.extractall(temp / "extract")
        package = temp / "extract" / PACKAGE
        manifest = load(package / "TEST_PACKAGE_MANIFEST.json")
        declared = {name: (row["size_bytes"], row["sha256"]) for name, row in manifest.get("files", {}).items()}
        actual = {
            path.relative_to(package).as_posix(): (path.stat().st_size, sha(path))
            for path in sorted(package.rglob("*"))
            if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
        }
        manifest_exact = declared == actual
        rebuilt = temp / "rebuilt.zip"
        import_base().deterministic_zip(package, rebuilt)
        deterministic = rebuilt.read_bytes() == ZIP.read_bytes()
    if not safe_zip:
        errors.append("safe_exact_zip")
    if not manifest_exact:
        errors.append("manifest_exact_set")
    if not deterministic:
        errors.append("deterministic_final_zip_recompute")

    index = load(STORAGE / "PACKAGE_STORAGE_INDEX.json")
    pending = [row for row in index.get("packages", []) if row.get("family") == "qlinearadd_node0007" and row.get("disposition") == "pending"]
    prior_zip = STORAGE / "pending" / f"{PRIOR}.zip"
    prior_receipt = build.get("source_v63_pending", {})
    prior_ok = (
        index.get("pass") is True
        and len(pending) == 1
        and pending[0].get("package_base") == PRIOR
        and prior_zip.is_file()
        and prior_zip.stat().st_size == prior_receipt.get("bytes")
        and sha(prior_zip) == prior_receipt.get("sha256")
    )
    if not prior_ok:
        errors.append("prior_v63_not_unique_byte_frozen_pending")

    modules = [
        "tests.test_qlinearadd_node0007_v64_failure_delta",
        "tests.test_server_diagnostic_mode_selector",
        "tests.test_server_tb_vcd_bounded_causal_cone",
        "tests.test_server_tb_vcd_runtime_supervision",
        "tests.test_server_tb_vcd_retention_analysis",
        "tests.test_server_package_local_hdl_lexical",
        "tests.test_server_runner_return_resilience",
        "tests.test_server_runtime_preflight_native_flow",
        "tests.test_server_post_sim_return",
    ]
    regressions = []
    test_total = 0
    for module in modules:
        result = subprocess.run([sys.executable, "-m", "unittest", module], cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
        output = result.stdout + result.stderr
        match = re.search(r"Ran (\d+) tests?", output)
        count = int(match.group(1)) if match else 0
        test_total += count
        regressions.append({"module": module, "exit_code": result.returncode, "test_count": count, "output_tail": output[-1024:]})
        if result.returncode:
            errors.append(f"regression:{module}")
    missing_jsonschema = subprocess.run(
        [sys.executable, "-c", "import jsonschema"], cwd=ROOT, capture_output=True, text=True, timeout=30, check=False
    ).returncode != 0
    environment_skip = {
        "module": "tests.test_server_package_runtime_layout",
        "skipped": missing_jsonschema,
        "reason": "bundled Python lacks jsonschema; exact runtime-layout validator and six-exit harness independently passed" if missing_jsonschema else None,
    }
    if not missing_jsonschema:
        result = subprocess.run([sys.executable, "-m", "unittest", environment_skip["module"]], cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
        environment_skip["skipped"] = False
        environment_skip["exit_code"] = result.returncode
        if result.returncode:
            errors.append(f"regression:{environment_skip['module']}")

    staging = {
        "schema": "qadd-node0007-v64-staging-tree-aggregate-v1",
        "package_id": PACKAGE,
        "pass": not any(item.startswith(("missing_report", "failed_report")) for item in errors),
        "errors": [item for item in errors if item.startswith(("missing_report", "failed_report"))],
        "reports": {name: rec(path) for name, path in reports.items() if path.is_file()},
        "claim_boundary": "Local staging and exact-package gates only; no server or DUT claim.",
    }
    staging_path = OUT / "gates/staging_aggregate.json"
    write(staging_path, staging)
    report = {
        "schema": "qadd-node0007-v64-tb-vcd-final-release-audit-v1",
        "package_id": PACKAGE,
        "activation_epoch": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437+qadd-failure-delta-v1",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "pass": not errors,
        "errors": errors,
        "checks": {
            "staging_aggregate": staging["pass"],
            "safe_exact_zip": safe_zip,
            "manifest_exact": manifest_exact,
            "deterministic_final_zip": deterministic,
            "first_fresh_current_epoch": load(FIRST / "validation.json").get("pass") is True,
            "prior_v63_byte_frozen": prior_ok,
            "server_actions_absent": True,
        },
        "exact_zip": rec(ZIP),
        "gate_receipts": [{"gate": name, **rec(path)} for name, path in reports.items() if path.is_file()],
        "regressions": {"pass": all(row["exit_code"] == 0 for row in regressions), "tests_run": test_total, "results": regressions, "environment_skip": environment_skip},
        "storage_prepublication": {"pass": prior_ok, "pending_by_family": index.get("pending_by_family", {}), "counts": index.get("counts", {})},
        "claim_boundary": "PACKAGE_READY_NOT_RUN gate only; no upload, lease, connection, production compile/simulation, DUT root, natural terminal, formal D, E3, E4 or E5 claim.",
    }
    write(OUT / "gates/final_zip_release_audit.json", report)
    print(json.dumps({"pass": report["pass"], "errors": report["errors"], "tests_run": test_total, "environment_skip": missing_jsonschema}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
