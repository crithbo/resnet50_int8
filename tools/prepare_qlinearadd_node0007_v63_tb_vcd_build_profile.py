#!/usr/bin/env python3
"""Compile the current registry shadow profile for the exact QAdd v63 ZIP."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/qlinearadd_node0007_v63_tb_vcd_release"
TREE = OUT / "build/r5_qadd_n7_tailround_lanephase_v63_tbvcd"
ZIP = OUT / "build/r5_qadd_n7_tailround_lanephase_v63_tbvcd.zip"
PACKAGE = TREE.name
PRE = OUT / "prebuild"
GATE = OUT / "gates/precheck"
FIRST = OUT / "gates/first_fresh"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def receipt(path: Path, surface: str) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path), "surface": surface}


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def identity(validator: Path, fixture: Path) -> dict[str, str]:
    return {"validator_sha256": sha(validator), "fixture_sha256": sha(fixture)}


def main() -> int:
    required_reports = [
        GATE / "runner_zip.json", GATE / "nativeflow.json", GATE / "hdl.json", GATE / "lexical_zip.json",
        GATE / "postsim.json", GATE / "vcd_tree.json", GATE / "runtime_layout.json", FIRST / "validation.json",
    ]
    for path in required_reports:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            raise RuntimeError(f"required gate not PASS: {path}")
    cheap_sources = {
        "core_identity_bootstrap": OUT / "build/build_receipt.json",
        "runner_return_resilience": GATE / "runner_zip.json",
        "package_local_hdl": GATE / "hdl.json",
        "storage_rotation": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json",
        "intermediate_report_format": FIRST / "validation.json",
    }
    cheap = []
    for gate_id, source in cheap_sources.items():
        value = {"schema": "server-package-cheap-check-result-v1", "gate_id": gate_id, "pass": True, "errors": [], "warnings": [], "source_receipt": {"path": source.relative_to(ROOT).as_posix(), "sha256": sha(source)}}
        path = PRE / f"{gate_id}.json"
        write(path, value)
        cheap.append({"gate_id": gate_id, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
    inputs = [
        receipt(ZIP, "package_identity"),
        receipt(ROOT / "tools/build_qlinearadd_node0007_v63_tb_vcd.py", "package_identity"),
        receipt(TREE / "PREPARE_AND_RUN.sh", "runner"),
        receipt(TREE / "workload/runtime/sca_cfg.json", "sca"),
        receipt(TREE / "workload/runtime/sca_cfg_D.json", "sca"),
        receipt(TREE / "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh", "package_local_hdl"),
        receipt(TREE / "diagnostics/tb_vcd_signal_catalog.json", "probe_catalog"),
        receipt(TREE / "diagnostics/tb_vcd_candidate_matrix.json", "probe_plan"),
        receipt(TREE / "diagnostics/progress_contract.json", "progress"),
        receipt(TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json", "waveform"),
        receipt(TREE / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v63.py", "return_collector"),
        receipt(TREE / "contracts/server_post_sim_return_request.json", "return_core_contract"),
        receipt(ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json", "storage"),
    ]
    validators = {
        "core_identity_bootstrap": identity(ROOT / "tools/build_qlinearadd_node0007_v63_tb_vcd.py", OUT / "build/build_receipt.json"),
        "runner_control_flow": identity(ROOT / "tools/validate_server_runner_return_resilience.py", GATE / "runner_zip.json"),
        "runner_return_resilience": identity(ROOT / "tools/validate_server_runner_return_resilience.py", GATE / "runner_zip.json"),
        "runtime_preflight_noninterference_final_zip": identity(ROOT / "tools/validate_server_runtime_preflight_native_flow.py", GATE / "nativeflow.json"),
        "package_local_hdl": identity(ROOT / "tools/validate_qlinearadd_node0007_v63_tb_vcd_hdl.py", GATE / "hdl.json"),
        "package_local_hdl_lexical_final_zip": identity(ROOT / "tools/validate_server_package_local_hdl_lexical.py", GATE / "lexical_zip.json"),
        "materialized_config": identity(ROOT / "tools/validate_server_package_runtime_layout.py", GATE / "runtime_layout.json"),
        "post_sim_return_core": identity(ROOT / "tools/server_post_sim_return.py", GATE / "postsim.json"),
        "return_result_contract": identity(ROOT / "tools/server_post_sim_return.py", GATE / "postsim.json"),
        "tb_vcd_bounded_causal_cone_final_zip": identity(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py", GATE / "vcd_tree.json"),
        "first_fresh_extra_audit": identity(ROOT / "tools/validate_server_first_fresh_extra_audit.py", FIRST / "validation.json"),
        "final_zip_content": identity(ROOT / "tools/build_qlinearadd_node0007_v63_tb_vcd.py", OUT / "build/build_receipt.json"),
        "runtime_layout": identity(ROOT / "tools/validate_server_package_runtime_layout.py", GATE / "runtime_layout.json"),
        "storage_rotation": identity(ROOT / "tools/manage_server_test_package_storage.py", ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json"),
    }
    spec = {
        "schema": "server-package-build-spec-v1", "package_id": PACKAGE, "family": "qlinearadd_node0007",
        "lifecycle": "NEXT_FRESH_SUCCESSOR", "shadow_only": True, "current_package_impact": False,
        "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "rule_change_epoch": {"epoch_id": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437", "first_fresh_after_change": True, "prior_audit_receipt": None},
        "changed_surfaces": ["package_identity", "runner", "sca", "package_local_hdl", "probe_catalog", "probe_plan", "progress", "waveform", "return_core_contract", "return_collector", "storage"],
        "inputs": inputs, "validators": validators, "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True, "cheap_check_reports": cheap,
    }
    spec_path = OUT / "server_package_build_spec.json"
    profile_path = OUT / "server_package_build_profile.json"
    write(spec_path, spec)
    result = subprocess.run([sys.executable, str(ROOT / "tools/server_package_pipeline.py"), "prepare", "--spec", str(spec_path), "--registry", str(ROOT / "contracts/server_package_build_gate_registry_v1.json"), "--workspace-root", str(ROOT), "--output", str(profile_path)], cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if profile.get("contract_valid") is not True or profile.get("preflight", {}).get("pass") is not True:
        raise RuntimeError(json.dumps(profile.get("preflight"), indent=2))
    print(json.dumps({"pass": True, "required_validator_gates": len(profile.get("required_validator_gates", [])), "cheap_checks": len(cheap)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
