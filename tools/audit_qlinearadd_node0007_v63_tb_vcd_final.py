#!/usr/bin/env python3
"""Single aggregate staging/final-ZIP release audit for exact QAdd v63."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/qlinearadd_node0007_v63_tb_vcd_release"
TREE = OUT / "build/r5_qadd_n7_tailround_lanephase_v63_tbvcd"
ZIP = OUT / "build/r5_qadd_n7_tailround_lanephase_v63_tbvcd.zip"
PACKAGE = TREE.name
GATE = OUT / "gates/precheck"
FIRST = OUT / "gates/first_fresh"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
PRIOR = "r5_qadd_n7_tailround_lanephase_v62_nfobs"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root is not object: {path}")
    return value


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rec(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    errors: list[str] = []
    staging_reports = {
        "mode_selector_tree": GATE / "selector_tree.json", "tb_vcd_tree": GATE / "vcd_tree.json",
        "hdl_lexical_tree": GATE / "lexical_tree.json", "runner_tree": GATE / "runner_tree.json",
        "build_profile": OUT / "server_package_build_profile.json",
    }
    final_reports = {
        "mode_selector_zip": GATE / "selector_zip.json", "hdl_lexical_zip": GATE / "lexical_zip.json",
        "runner_zip": GATE / "runner_zip.json", "native_preflight": GATE / "nativeflow.json",
        "post_sim": GATE / "postsim.json", "full_hdl": GATE / "hdl.json",
        "source_bound": GATE / "source_bound.json", "runtime_layout": GATE / "runtime_layout.json",
        "first_fresh": FIRST / "validation.json",
    }
    for name, path in {**staging_reports, **final_reports}.items():
        if not path.is_file():
            errors.append(f"missing_report:{name}")
            continue
        value = load(path)
        passed = value.get("pass") is True
        if name == "build_profile":
            passed = value.get("contract_valid") is True and value.get("preflight", {}).get("pass") is True
        if not passed:
            errors.append(f"failed_report:{name}")
    staging = {
        "schema": "qadd-node0007-v63-staging-tree-aggregate-v1", "package_id": PACKAGE,
        "pass": not any(error.startswith(("missing_report", "failed_report")) for error in errors),
        "errors": list(errors), "top_level_invocations": 1,
        "reports": {name: rec(path) for name, path in staging_reports.items() if path.is_file()},
        "claim_boundary": "Local staging tree and registry profile only; no server action or dynamic DUT claim.",
    }
    staging_path = OUT / "gates/staging_aggregate.json"
    write(staging_path, staging)

    exact_vcd: dict = {}
    manifest_exact = deterministic = safe_zip = False
    with tempfile.TemporaryDirectory(prefix="qadd-v63-final-") as raw:
        temp = Path(raw)
        with zipfile.ZipFile(ZIP) as archive:
            names = archive.namelist()
            roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
            unsafe = [name for name in names if PurePosixPath(name.replace("\\", "/")).is_absolute() or ".." in PurePosixPath(name.replace("\\", "/")).parts]
            safe_zip = roots == {PACKAGE} and not unsafe and archive.testzip() is None and len(names) == len(set(names))
            archive.extractall(temp / "extract")
        package = temp / "extract" / PACKAGE
        manifest = load(package / "TEST_PACKAGE_MANIFEST.json")
        declared = {name: (row["size_bytes"], row["sha256"]) for name, row in manifest.get("files", {}).items()}
        actual = {path.relative_to(package).as_posix(): (path.stat().st_size, sha(path)) for path in sorted(package.rglob("*")) if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"}
        manifest_exact = declared == actual
        sys.path.insert(0, str(ROOT / "tools"))
        import build_qlinearadd_node0007_v63_tb_vcd as builder
        rebuilt = temp / "rebuilt.zip"
        builder.deterministic_zip(package, rebuilt)
        deterministic = rebuilt.read_bytes() == ZIP.read_bytes()
        vcd_output = temp / "vcd_exact.json"
        result = subprocess.run([sys.executable, str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"), "--contract", str(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"), "--root", str(package), "--output", str(vcd_output)], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
        exact_vcd = load(vcd_output)
        exact_vcd["exact_final_zip_sha256"] = sha(ZIP)
        exact_vcd["from_clean_extract"] = True
        exact_vcd["pass"] = result.returncode == 0 and exact_vcd.get("pass") is True
    exact_vcd_path = GATE / "vcd_exact_zip.json"
    write(exact_vcd_path, exact_vcd)
    if not safe_zip: errors.append("exact_zip_safety")
    if not manifest_exact: errors.append("manifest_exact_set")
    if not deterministic: errors.append("deterministic_zip_byte_recompute")
    if exact_vcd.get("pass") is not True: errors.append("exact_zip_tb_vcd")
    first = load(FIRST / "contract.json")
    if first.get("package", {}).get("final_zip", {}).get("sha256") != sha(ZIP):
        errors.append("first_fresh_zip_binding")
    build = load(OUT / "build/build_receipt.json")
    if build.get("zip", {}).get("sha256") != sha(ZIP) or build.get("exact_final_zip_recheck", {}).get("pass") is not True:
        errors.append("build_zip_binding")
    index = load(STORAGE / "PACKAGE_STORAGE_INDEX.json")
    prior_rows = [row for row in index.get("packages", []) if row.get("family") == "qlinearadd_node0007" and row.get("disposition") == "pending"]
    prior_ok = index.get("pass") is True and len(prior_rows) == 1 and prior_rows[0].get("package_base") == PRIOR
    prior_zip = STORAGE / "pending" / f"{PRIOR}.zip"
    prior_ok = prior_ok and prior_zip.is_file() and prior_zip.stat().st_size == build.get("source_v62_pending", {}).get("bytes") and sha(prior_zip) == build.get("source_v62_pending", {}).get("sha256")
    if not prior_ok: errors.append("prior_v62_not_unique_byte_frozen_pending")

    modules = [
        "tests.test_server_diagnostic_mode_selector", "tests.test_server_tb_vcd_bounded_causal_cone",
        "tests.test_server_tb_vcd_runtime_supervision", "tests.test_server_tb_vcd_retention_analysis",
        "tests.test_server_package_local_hdl_lexical", "tests.test_server_runner_return_resilience",
        "tests.test_server_runtime_preflight_native_flow", "tests.test_server_post_sim_return",
    ]
    regressions = []
    total = 0
    for module in modules:
        result = subprocess.run([sys.executable, "-m", "unittest", module], cwd=ROOT, capture_output=True, text=True, timeout=120, check=False)
        output = result.stdout + result.stderr
        match = re.search(r"Ran (\d+) tests?", output)
        count = int(match.group(1)) if match else 0
        total += count
        regressions.append({"module": module, "exit_code": result.returncode, "test_count": count, "output_tail": output[-1024:]})
        if result.returncode != 0: errors.append(f"regression:{module}")
    all_reports = {**staging_reports, **final_reports, "staging_aggregate": staging_path, "tb_vcd_exact_zip": exact_vcd_path}
    report = {
        "schema": "qadd-node0007-v63-tb-vcd-final-release-audit-v1", "package_id": PACKAGE,
        "activation_epoch": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "pass": not errors, "errors": errors,
        "checks": {"staging_aggregate_pass": staging["pass"], "safe_exact_zip": safe_zip, "manifest_exact": manifest_exact, "deterministic_zip": deterministic, "exact_zip_tb_vcd": exact_vcd.get("pass") is True, "first_fresh_bound": "first_fresh_zip_binding" not in errors, "prior_v62_byte_frozen": prior_ok, "all_gate_receipts_pass": not any(error.startswith(("missing_report", "failed_report")) for error in errors), "server_actions_absent": True},
        "exact_zip": rec(ZIP), "gate_receipts": [{"gate": name, **rec(path), "pass": True} for name, path in all_reports.items() if path.is_file()],
        "shared_regressions": {"pass": all(row["exit_code"] == 0 for row in regressions), "total_tests": total, "results": regressions},
        "storage_prepublication": {"pass": prior_ok, "pending_by_family": index.get("pending_by_family", {}), "counts": index.get("counts", {})},
        "claim_boundary": "Local construction/gates/storage readiness only; no upload, connection, production compile/simulation, root cause, natural terminal, formal-D, E3, E4 or E5 claim.",
    }
    final_path = OUT / "gates/final_zip_release_audit.json"
    write(final_path, report)
    print(json.dumps({"pass": report["pass"], "errors": len(errors), "regression_tests": total}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
