from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_rowpair_v31_server_package as base


NAME = "r5_qadd_n7_crow32_v33"
SOURCE = "r5_qadd_n7_crow32_v32"
base.NAME = NAME
base.SOURCE = SOURCE
base.ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}.zip"
base.SOURCE_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE}.zip"
base.HDL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v33-server-package/hdl_scope_revalidation.json"
base.OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v33-server-package/final_zip_self_audit.json"


def workload_with_exact_installed_tree(
    files: dict[str, bytes], source: dict[str, bytes]
) -> dict:
    paths = {item for item in files if item.startswith("workload/")}
    source_paths = {item for item in source if item.startswith("workload/")}
    mismatches = []
    sca_targets = []
    for path in sorted(paths & source_paths):
        target_bytes = files[path]
        source_bytes = source[path]
        if path in {"workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"}:
            target = json.loads(target_bytes)
            prior = json.loads(source_bytes)
            target_without_paths = json.loads(json.dumps(target))
            prior_without_paths = json.loads(json.dumps(prior))
            for value in target_without_paths.values():
                if isinstance(value, dict):
                    value.pop("path", None)
            for value in prior_without_paths.values():
                if isinstance(value, dict):
                    value.pop("path", None)
            if target_without_paths != prior_without_paths:
                mismatches.append(path + ":non_path")
                continue
            prefix = f"install/cfg_pkg/{NAME}/"
            for key, value in target.items():
                if not isinstance(value, dict) or not isinstance(value.get("path"), str):
                    continue
                declared = value["path"].replace("\\", "/")
                if not declared.startswith(prefix):
                    mismatches.append(path + ":" + key + ":prefix")
                    continue
                relative = declared[len(prefix) :]
                member = "workload/runtime/" + relative
                exists = member in files
                sca_targets.append({"key": key, "declared": declared, "member": member, "exists": exists})
                if not exists:
                    mismatches.append(path + ":" + key + ":absent")
            continue
        target_bytes = target_bytes.replace(NAME.encode(), SOURCE.encode())
        if target_bytes != source_bytes:
            mismatches.append(path)
    return {
        "exact_set": paths == source_paths,
        "sca_targets": sca_targets,
        "all_sca_targets_exist": bool(sca_targets) and all(x["exists"] for x in sca_targets),
        "mismatches_after_identity_and_authorized_path_normalization": mismatches,
        "valid": paths == source_paths
        and not mismatches
        and bool(sca_targets)
        and all(x["exists"] for x in sca_targets),
    }


base.v29.workload_frozen = workload_with_exact_installed_tree
original_main = base.main


def main() -> int:
    # The base validator's source binding key names the original v30 provenance.
    # v33 additionally binds its immediate v32 source below through the manifest.
    original_contract = base.rowpair_contract

    immediate_source_zip = base.SOURCE_ZIP

    def contract(files: dict[str, bytes], manifest: dict) -> dict:
        result = original_contract(files, manifest)
        immediate = manifest["source_assets"].get("fp32_rowpair_v32_source_zip", {})
        result["checks"]["immediate_v32_source_bound"] = (
            immediate.get("sha256") == base.sha(immediate_source_zip)
        )
        result["valid"] = all(result["checks"].values())
        return result

    base.rowpair_contract = contract
    # Make the legacy source-v30 check resolve to the frozen v30 source record.
    frozen_v30 = ROOT / (
        "artifacts/operator_config_validation/r5-server-test-packages/"
        "r5_qadd_n7_split_c_rowpairfix_v30.zip"
    )
    prior_source = base.SOURCE_ZIP
    base.SOURCE_ZIP = frozen_v30
    try:
        # Workload comparison must still use the immediate v32 package.
        immediate_files, _ = base.v28.load(prior_source, SOURCE)
        original_load = base.v28.load

        def routed_load(path: Path, name: str):
            if path == frozen_v30 and name == SOURCE:
                return immediate_files, {}
            return original_load(path, name)

        base.v28.load = routed_load
        return original_main()
    finally:
        base.SOURCE_ZIP = prior_source


if __name__ == "__main__":
    raise SystemExit(main())
