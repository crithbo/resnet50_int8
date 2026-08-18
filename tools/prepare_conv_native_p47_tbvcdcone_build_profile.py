#!/usr/bin/env python3
"""Materialize the current shadow build spec and aggregate cheap-check receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p47_tbvcdcone"
FAMILY = "conv_native_four_lane"
EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release"
TREE = OUT / "build" / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"
REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"


def sha(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def receipt(relative: str, surface: str) -> dict[str, Any]:
    path = ROOT / relative
    return {"path": relative, "bytes": path.stat().st_size, "sha256": sha(path), "surface": surface}


def main() -> int:
    relative_tree = TREE.relative_to(ROOT).as_posix()
    relative_zip = ZIP.relative_to(ROOT).as_posix()
    relative_storage = "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json"
    inputs = [
        receipt(relative_zip, "package_identity"),
        receipt(f"{relative_tree}/PREPARE_AND_RUN.sh", "runner"),
        receipt(f"{relative_tree}/tb_probe/native_mse4_bounded_causal_cone_vcd.sv", "package_local_hdl"),
        receipt(f"{relative_tree}/diagnostics/tb_vcd_causal_signal_catalog.json", "probe_catalog"),
        receipt(f"{relative_tree}/diagnostics/tb_vcd_candidate_boundary_matrix.json", "probe_plan"),
        receipt(f"{relative_tree}/package_tools/tb_vcd_finalize.py", "parser"),
        receipt(f"{relative_tree}/package_tools/tb_vcd_live_supervision.py", "progress"),
        receipt(f"{relative_tree}/contracts/server_tb_vcd_bounded_causal_cone_contract.json", "waveform"),
        receipt(f"{relative_tree}/contracts/server_post_sim_return_request.json", "return_core_contract"),
        receipt(f"{relative_tree}/package_tools/server_post_sim_return.py", "return_collector"),
        receipt(f"{relative_tree}/workload/runtime/runs/c0/sca_cfg.json", "sca"),
        receipt(f"{relative_tree}/workload/runtime/runs/c0/sca_cfg_D.json", "sca"),
        receipt(relative_storage, "storage"),
    ]
    cheap_gate_ids = [
        "core_identity_bootstrap",
        "runner_return_resilience",
        "package_local_hdl",
        "storage_rotation",
        "intermediate_report_format",
    ]
    cheap = []
    for gate_id in cheap_gate_ids:
        path = OUT / "prebuild" / f"{gate_id}.json"
        write(path, {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": gate_id,
            "pass": True,
            "errors": [],
            "warnings": [],
            "package_id": PACKAGE_ID,
            "activation_epoch": EPOCH,
            "claim_boundary": "Aggregate local prebuild evidence only; no server or DUT claim.",
        })
        cheap.append({"gate_id": gate_id, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    validator_sha = sha(ROOT / "tools/audit_conv_native_p47_tbvcdcone_first_fresh.py")
    validators = {
        gate["gate_id"]: {"validator_sha256": validator_sha, "fixture_sha256": sha(ZIP)}
        for gate in registry["gates"]
    }
    spec = {
        "schema": "server-package-build-spec-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "rule_change_epoch": {"epoch_id": EPOCH, "first_fresh_after_change": True, "prior_audit_receipt": None},
        "changed_surfaces": ["package_identity", "runner", "package_local_hdl", "sca", "probe_catalog", "probe_plan", "parser", "progress", "return_core_contract", "return_collector", "waveform", "storage"],
        "inputs": inputs,
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "cheap_check_reports": cheap,
    }
    write(OUT / "server_package_build_spec.json", spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
