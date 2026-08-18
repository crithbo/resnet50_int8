#!/usr/bin/env python3
"""Stage exact QAdd v63 package and receipts for atomic manager rotation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/qlinearadd_node0007_v63_tb_vcd_release"
BUILD = OUT / "build"
GATE = OUT / "gates/precheck"
FIRST = OUT / "gates/first_fresh"
STAGE = OUT / "storage_release"
PACKAGE = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
PRIOR = "r5_qadd_n7_tailround_lanephase_v62_nfobs"
ZIP = BUILD / f"{PACKAGE}.zip"
SIDECAR = BUILD / f"{PACKAGE}.zip.sha256"
TASK = ROOT / ".agents/task_records/20260814_qlinearadd_node0007_v63_tbvcdcone_package_ready_not_run.md"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rec(path: Path) -> dict:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if STAGE.exists():
        raise RuntimeError("fresh storage_release directory required")
    reports = {
        "build": BUILD / "build_receipt.json", "frozen_surface": OUT / "frozen_surface_receipt.json",
        "build_spec": OUT / "server_package_build_spec.json", "build_profile": OUT / "server_package_build_profile.json",
        "staging_aggregate": OUT / "gates/staging_aggregate.json", "final_zip_audit": OUT / "gates/final_zip_release_audit.json",
        "mode_selector_tree": GATE / "selector_tree.json", "mode_selector_final_zip": GATE / "selector_zip.json",
        "tb_vcd_tree": GATE / "vcd_tree.json", "tb_vcd_final_zip": GATE / "vcd_exact_zip.json",
        "hdl_lexical_tree": GATE / "lexical_tree.json", "hdl_lexical_final_zip": GATE / "lexical_zip.json",
        "hdl_full_scope_state": GATE / "hdl.json", "source_bound": GATE / "source_bound.json",
        "native_preflight": GATE / "nativeflow.json", "runner_tree": GATE / "runner_tree.json",
        "runner_final_zip": GATE / "runner_zip.json", "post_sim_return": GATE / "postsim.json",
        "runtime_layout": GATE / "runtime_layout.json", "first_fresh_contract": FIRST / "contract.json",
        "first_fresh_validation": FIRST / "validation.json", "runtime_six_exit_streaming_retention": FIRST / "reports/source_bound_logger_collector_parser_roundtrip.json",
        "candidate_matrix": FIRST / "reports/candidate_discrimination_matrix.json", "task_record": TASK,
    }
    failed = []
    for name, path in reports.items():
        if not path.is_file():
            failed.append(f"missing:{name}")
            continue
        if path.suffix == ".json" and name not in {"build_spec", "first_fresh_contract"}:
            value = load(path)
            passed = value.get("pass") is True
            if name == "build_profile":
                passed = value.get("contract_valid") is True and value.get("preflight", {}).get("pass") is True
            if not passed:
                failed.append(f"failed:{name}")
    if failed:
        raise RuntimeError(f"release gates open: {failed}")
    if SIDECAR.read_text(encoding="ascii").split()[0].lower() != sha(ZIP):
        raise RuntimeError("sidecar mismatch")
    STAGE.mkdir(parents=True)
    shutil.copy2(ZIP, STAGE / ZIP.name)
    shutil.copy2(SIDECAR, STAGE / SIDECAR.name)
    for name, path in reports.items():
        suffix = ".md" if path.suffix == ".md" else ".json"
        shutil.copy2(path, STAGE / f"{PACKAGE}.{name}{suffix}")
    release = {
        "schema": "qadd-node0007-v63-tb-vcd-package-ready-not-run-v1", "package_id": PACKAGE,
        "family": "qlinearadd_node0007", "role_id": "family.qlinearadd", "owner_epoch": 2, "registry_epoch": 6,
        "activation_epoch": "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437", "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "status": "PACKAGE_READY_NOT_RUN", "pass": True, "errors": [], "package": rec(STAGE / ZIP.name),
        "previous_package": PRIOR,
        "previous_version_progress": "v57h localized the Buffer5 request-decode to selected-port required-lane read-accept boundary; v59 exposed the manifest/install/SCA identity defect; v60 repaired it; v62 preserved the repaired identity and native-flow contract in an unrun observer-only package.",
        "current_version_purpose": "Preserve v62 identity repair, tail-round target and both ping-pong branches while returning one bounded source-bound standard-TB VCD over the complete selected-port/lane readiness causal cone and terminal/global-progress chain.",
        "final_zip_audit": rec(OUT / "gates/final_zip_release_audit.json"), "first_fresh_validation": rec(FIRST / "validation.json"), "task_record": rec(TASK),
        "sole_future_command": f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01",
        "frozen": ["config", "numeric", "workload", "golden", "functional_rtl", "ping_pong_behavior", "tail_round_target"],
        "server_actions_performed": [],
        "claim_boundary": "Local PACKAGE_READY_NOT_RUN only; no upload, lease, connection, production compile/simulation, root cause, natural terminal, formal-D, E3, E4 or E5 claim.",
    }
    release_path = STAGE / f"{PACKAGE}.release.json"
    write(release_path, release)
    print(json.dumps({"status": release["status"], "stage": STAGE.relative_to(ROOT).as_posix(), "member_count": len(list(STAGE.iterdir()))}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
