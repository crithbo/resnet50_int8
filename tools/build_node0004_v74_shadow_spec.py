from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v72_return_v74_successor"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def receipt(relative: str, surface: str) -> dict:
    path = ROOT / relative
    return {"path": relative, "bytes": path.stat().st_size, "sha256": sha(path), "surface": surface}

def validator(script: str, fixture: str) -> dict:
    return {"validator_sha256": sha(ROOT / script), "fixture_sha256": sha(ROOT / fixture)}

def main() -> int:
    audit = "outputs/conv_node0004_v72_return_v74_successor/v74_final_zip_audit.json"
    family = "outputs/conv_node0004_v72_return_v74_successor/v74_family_validation.json"
    source_bound = "outputs/conv_node0004_v72_return_v74_successor/source_bound/final_zip_validation.json"
    trace = "outputs/conv_node0004_v72_return_v74_successor/source_bound/trace_validation.json"
    ret = "outputs/conv_node0004_v72_return_v74_successor/v74_return_contract.json"
    spec = {
        "schema": "server-package-build-spec-v1",
        "package_id": "r5_n4_hw_v74_sourcebound_epoch_diag",
        "family": "conv_node0004_serialized",
        "lifecycle": "NEXT_FRESH_SUCCESSOR",
        "shadow_only": True,
        "current_package_impact": False,
        "changed_surfaces": ["package_identity", "package_local_hdl", "observer", "progress", "runner", "return_collector", "storage"],
        "inputs": [
            receipt("outputs/conv_node0004_v72_return_v74_successor/build/r5_n4_hw_v74_sourcebound_epoch_diag.zip", "package_identity"),
            receipt(source_bound, "package_local_hdl"),
            receipt(trace, "observer"),
            receipt(family, "runner"),
            receipt(ret, "return_collector"),
        ],
        "validators": {
            "source_bound_observer_generation": validator("tools/generate_server_source_bound_observer.py", trace),
            "source_bound_final_zip": validator("tools/generate_server_source_bound_observer.py", source_bound),
            "core_identity_bootstrap": validator("tools/audit_node0004_v74_final_zip.py", audit),
            "runner_control_flow": validator("tools/validate_node0004_v74_install_only_runner.py", family),
            "package_local_hdl": validator("tools/generate_server_source_bound_observer.py", source_bound),
            "materialized_config": validator("tools/audit_node0004_v74_final_zip.py", audit),
            "diagnostic_semantics": validator("tools/validate_node0004_v74_source_bound_trace.py", trace),
            "return_result_contract": validator("tools/validate_node0004_v74_return_contract.py", ret),
            "final_zip_content": validator("tools/audit_node0004_v74_final_zip.py", audit),
            "runtime_layout": validator("tools/validate_node0004_v74_install_only_runner.py", family),
            "storage_rotation": validator("tools/audit_node0004_v74_final_zip.py", audit),
        },
        "receipt_reuse_candidates": [],
    }
    target = OUT / "v74_build_spec.json"
    target.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"path": str(target), "sha256": sha(target)}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
