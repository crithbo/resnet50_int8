#!/usr/bin/env python3
"""Write the one-shot QAdd v62 native-flow shadow build specification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v61_obswide"
NEW = "r5_qadd_n7_tailround_lanephase_v62_nfobs"
BASE = ROOT / "outputs/qlinearadd_node0007_v62_nativeflow_release"
SPEC = BASE / "server_package_build_spec.json"
PROFILE = BASE / "server_package_build_profile.json"
REGISTRY = ROOT / "contracts/server_package_build_gate_registry_v1.json"
SOURCE_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending/{OLD}.zip"
SOURCE_TREE = ROOT / f"outputs/qlinearadd_node0007_v61_observer_only_release/build/{OLD}"
SOURCE_GATES = ROOT / "outputs/qlinearadd_node0007_v61_observer_only_release/gates_v2"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def record(path: Path, surface: str) -> dict[str, Any]:
    return {
        "path": relative(path),
        "surface": surface,
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def validator(tool: str, fixture: Path) -> dict[str, str]:
    return {
        "validator_sha256": digest(ROOT / tool),
        "fixture_sha256": digest(fixture),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def cheap_report(gate_id: str, passed: bool, evidence: list[str]) -> Path:
    path = BASE / "prebuild" / f"{gate_id}.json"
    write_json(
        path,
        {
            "schema": "server-package-cheap-check-result-v1",
            "gate_id": gate_id,
            "pass": passed,
            "errors": [] if passed else ["predecessor evidence did not pass"],
            "warnings": [],
            "evidence": evidence,
        },
    )
    return path


def load_pass(path: Path) -> bool:
    return path.is_file() and json.loads(path.read_text(encoding="utf-8")).get("pass") is True


def main() -> int:
    # The initial aggregate must precede materialization.  Re-running this
    # writer after a ZIP exists is identity-refresh only: it never edits the
    # package tree or archive and keeps validator receipts current.
    storage = json.loads(
        (ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json").read_text(
            encoding="utf-8"
        )
    )
    pending = [
        item
        for item in storage.get("packages", [])
        if item.get("family") == "qlinearadd_node0007" and item.get("disposition") == "pending"
    ]
    source_ok = (
        storage.get("pass") is True
        and len(pending) == 1
        and pending[0].get("package_base") == OLD
        and SOURCE_ZIP.is_file()
        and SOURCE_TREE.is_dir()
        and digest(SOURCE_ZIP)
        == digest(ROOT / f"outputs/qlinearadd_node0007_v61_observer_only_release/build/{OLD}.zip")
    )
    gate_sources = {
        "source_bound_observer_generation": SOURCE_GATES / "source_bound_final_zip.json",
        "runner_return_resilience": SOURCE_GATES / "runner_final_zip.json",
        "package_local_hdl": SOURCE_GATES / "hdl_full_scope_state.json",
    }
    cheap = {
        "core_identity_bootstrap": cheap_report(
            "core_identity_bootstrap", source_ok, [relative(SOURCE_ZIP)]
        ),
        "source_bound_observer_generation": cheap_report(
            "source_bound_observer_generation",
            load_pass(gate_sources["source_bound_observer_generation"]),
            [relative(gate_sources["source_bound_observer_generation"])],
        ),
        "runner_return_resilience": cheap_report(
            "runner_return_resilience",
            load_pass(gate_sources["runner_return_resilience"]),
            [relative(gate_sources["runner_return_resilience"])],
        ),
        "package_local_hdl": cheap_report(
            "package_local_hdl",
            load_pass(gate_sources["package_local_hdl"]),
            [relative(gate_sources["package_local_hdl"])],
        ),
        "storage_rotation": cheap_report(
            "storage_rotation", source_ok, [relative(ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json")]
        ),
        "intermediate_report_format": cheap_report(
            "intermediate_report_format", True, ["one aggregate report set"]
        ),
    }

    builder = ROOT / "tools/build_qlinearadd_node0007_v62_nativeflow.py"
    fixture = ROOT / "fixtures/server_package_pipeline_v1/cheap/core_identity_bootstrap.json"
    native_fixture = ROOT / "fixtures/server_runtime_preflight_native_flow_v1/positive_runner.sh"
    observer_fixture = SOURCE_GATES / "observer_final_zip.json"
    validators = {
        "core_identity_bootstrap": validator("tools/build_qlinearadd_node0007_v62_nativeflow.py", SOURCE_ZIP),
        "source_bound_observer_generation": validator("tools/generate_server_source_bound_observer.py", gate_sources["source_bound_observer_generation"]),
        "runner_control_flow": validator("tools/validate_server_runner_return_resilience.py", gate_sources["runner_return_resilience"]),
        "runner_return_resilience": validator("tools/validate_server_runner_return_resilience.py", gate_sources["runner_return_resilience"]),
        "runtime_preflight_noninterference_final_zip": validator("tools/validate_server_runtime_preflight_native_flow.py", native_fixture),
        "package_local_hdl": validator("tools/validate_qlinearadd_node0007_v62_nativeflow_hdl.py", gate_sources["package_local_hdl"]),
        "package_local_hdl_lexical_final_zip": validator("tools/validate_server_package_local_hdl_lexical.py", SOURCE_GATES / "hdl_lexical_zip.json"),
        "materialized_config": validator("tools/validate_server_package_runtime_layout.py", SOURCE_GATES / "runtime_layout.json"),
        "diagnostic_semantics": validator("tools/validate_server_observer_only_wide_causal.py", observer_fixture),
        "post_sim_return_core": validator("tools/server_post_sim_return.py", SOURCE_GATES / "post_sim_return.json"),
        "return_result_contract": validator("tools/validate_qlinearadd_node0007_v62_nativeflow_return.py", SOURCE_GATES / "observer_return_fixture.json"),
        "source_bound_final_zip": validator("tools/generate_server_source_bound_observer.py", gate_sources["source_bound_observer_generation"]),
        "observer_only_wide_causal_final_zip": validator("tools/validate_server_observer_only_wide_causal.py", observer_fixture),
        "first_fresh_extra_audit": validator("tools/audit_qlinearadd_node0007_v62_nativeflow_first_fresh.py", SOURCE_GATES / "first_fresh_validation.json"),
        "final_zip_content": validator("tools/build_qlinearadd_node0007_v62_nativeflow.py", SOURCE_ZIP),
        "runtime_layout": validator("tools/validate_server_package_runtime_layout.py", SOURCE_GATES / "runtime_layout.json"),
        "storage_rotation": validator("tools/manage_server_test_package_storage.py", cheap["storage_rotation"]),
    }
    inputs = [
        record(SOURCE_ZIP, "package_identity"),
        record(builder, "package_identity"),
        record(SOURCE_TREE / "PREPARE_AND_RUN.sh", "runner"),
        record(ROOT / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json", "runner"),
        record(SOURCE_TREE / "tb_probe/qadd_observer_wide_impl.svh", "package_local_hdl"),
        record(SOURCE_TREE / "diagnostics/observer_signal_catalog.json", "probe_catalog"),
        record(SOURCE_TREE / "diagnostics/observer_capture_plan.json", "probe_plan"),
        record(SOURCE_TREE / "package_tools/qadd_observer_event_parser.py", "parser"),
        record(SOURCE_TREE / "diagnostics/progress_contract.json", "progress"),
        record(SOURCE_TREE / "contracts/server_observer_only_wide_causal_contract.json", "observer"),
        record(SOURCE_TREE / "package_tools/server_post_sim_return.py", "return_collector"),
        record(SOURCE_TREE / "contracts/server_post_sim_return_request.json", "return_core_contract"),
        record(SOURCE_TREE / "workload/runtime/sca_cfg.json", "sca"),
        record(SOURCE_TREE / "workload/runtime/sca_cfg_D.json", "sca"),
        record(ROOT / "artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json", "storage"),
    ]
    value = {
        "schema": "server-package-build-spec-v1",
        "package_id": NEW,
        "family": "qlinearadd_node0007",
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "rule_change_epoch": {
            "epoch_id": "runtime-preflight-native-flow-v1",
            "first_fresh_after_change": True,
            "prior_audit_receipt": None,
        },
        "changed_surfaces": [
            "package_identity", "runner", "sca", "observer", "probe_plan",
            "return_core_contract", "return_collector", "storage",
        ],
        "inputs": inputs,
        "validators": validators,
        "receipt_reuse_candidates": [],
        "require_all_cheap_checks": True,
        "cheap_check_reports": [
            {"gate_id": gate_id, "path": relative(path), "sha256": digest(path)}
            for gate_id, path in cheap.items()
        ],
    }
    write_json(SPEC, value)
    print(json.dumps({"spec": relative(SPEC), "source_ok": source_ok, "cheap": len(cheap)}, sort_keys=True))
    return 0 if source_ok and all(load_pass(path) for path in cheap.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
