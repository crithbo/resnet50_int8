from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import deterministic_zip, write_json
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_col_ag_mrm_lane_v31_package as base


INSTALL_NAME = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
TEST_ID = "r5-gap-node0071-v32-col-ag-mrm-byte-lane-rulebind-diagnostic"
ORIGINAL_UPDATE_MANIFEST = base.update_manifest


def configure() -> None:
    base.INSTALL_NAME = INSTALL_NAME
    base.TEST_ID = TEST_ID


def update_manifest(package: Path, source_manifest: dict) -> None:
    ORIGINAL_UPDATE_MANIFEST(package, source_manifest)
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["schema"] = (
        "gap-node0071-col-ag-mrm-byte-lane-rulebind-diagnostic-package-v32"
    )
    ids = manifest["final_zip_rule_self_audit_contract"]["applicable_rule_ids"]
    rule_id = "CDA-GAP-8B-RD-BUFFER-BYTE-LANE-COVERAGE-001"
    if rule_id not in ids:
        ids.append(rule_id)
    manifest["generation_provenance"]["tool"] = (
        "tools/build_gap_node0071_col_ag_mrm_lane_v32_rulebind_package.py"
    )
    manifest["generation_provenance"]["v31_quarantined_sha256"] = (
        "d37405bf47e2a572f52de47580faec3375ba387fffeb0168bad1cf42b7671650"
    )
    manifest["generation_provenance"]["v31_quarantine_reason"] = (
        "applicable rule ID absent from final manifest"
    )
    manifest["post_generation_rule_drift"]["resolution"] = (
        "fresh v32 binds current rules including GAP 8B byte-lane coverage"
    )
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=base.PACKAGE_ROOT)
    args = parser.parse_args()
    configure()
    base.update_manifest = update_manifest
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, proof = base.build_directory(output_root)
        repeated = base.repeat_build(package, zip_path)
        digest = base.sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
        )
        result = {
            "schema": "gap-node0071-col-ag-mrm-byte-lane-v32-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "test_id": TEST_ID,
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "sidecar_sha256": base.sha256(sidecar),
            **proof,
            "repeat_build": repeated,
            "v31_quarantined": True,
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(validation, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
