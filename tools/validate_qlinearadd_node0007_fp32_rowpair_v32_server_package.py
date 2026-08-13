from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_rowpair_v31_server_package as base


NAME = "r5_qadd_n7_crow32_v32"
SOURCE = "r5_qadd_n7_split_c_rowpairfix_rule_v31"
base.NAME = NAME
base.SOURCE = SOURCE
base.ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}.zip"
base.SOURCE_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE}.zip"
base.HDL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v32-server-package/hdl_scope_revalidation.json"
base.OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v32-server-package/final_zip_self_audit.json"


def workload_with_authorized_sca_path_fix(
    files: dict[str, bytes], source: dict[str, bytes]
) -> dict:
    paths = {item for item in files if item.startswith("workload/")}
    source_paths = {item for item in source if item.startswith("workload/")}
    mismatches = []
    authorized = []
    for path in sorted(paths & source_paths):
        target_bytes = files[path]
        source_bytes = source[path]
        if path in {"workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"}:
            target = json.loads(target_bytes)
            prior = json.loads(source_bytes)
            target_paths = {
                key: value.get("path")
                for key, value in target.items()
                if isinstance(value, dict) and isinstance(value.get("path"), str)
            }
            prior_paths = {
                key: value.get("path")
                for key, value in prior.items()
                if isinstance(value, dict) and isinstance(value.get("path"), str)
            }
            normalized = {
                key: value.replace(NAME, SOURCE).replace(
                    f"install/cfg_pkg/{SOURCE}/install/",
                    f"install/cfg_pkg/{SOURCE}/",
                )
                for key, value in target_paths.items()
            }
            if normalized == prior_paths:
                authorized.append(path)
                continue
        else:
            target_bytes = target_bytes.replace(NAME.encode(), SOURCE.encode())
        if target_bytes != source_bytes:
            mismatches.append(path)
    return {
        "exact_set": paths == source_paths,
        "authorized_package_local_sca_path_fix": authorized,
        "mismatches_after_identity_and_authorized_path_normalization": mismatches,
        "valid": paths == source_paths
        and not mismatches
        and set(authorized)
        == {"workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"},
    }


base.v29.workload_frozen = workload_with_authorized_sca_path_fix

if __name__ == "__main__":
    raise SystemExit(base.main())
