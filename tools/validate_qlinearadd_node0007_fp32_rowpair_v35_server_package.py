from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_rowpair_v31_server_package as base


NAME = "r5_qadd_n7_crow32_v35"
SOURCE = "r5_qadd_n7_crow32_v34"
IMMEDIATE_SOURCE_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    f"{SOURCE}.zip"
)
FROZEN_V30_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_split_c_rowpairfix_v30.zip"
)
base.NAME = NAME
base.SOURCE = SOURCE
base.ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}.zip"
base.SOURCE_ZIP = IMMEDIATE_SOURCE_ZIP
base.HDL = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/"
    "hdl_scope_revalidation.json"
)
base.OUT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/"
    "final_zip_self_audit.json"
)


def workload_frozen(files: dict[str, bytes], source: dict[str, bytes]) -> dict:
    paths = {item for item in files if item.startswith("workload/")}
    source_paths = {item for item in source if item.startswith("workload/")}
    mismatches = []
    input_targets = []
    output_targets = []
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
                member = "workload/runtime/" + declared[len(prefix) :]
                exists = member in files
                record = {
                    "key": key,
                    "declared": declared,
                    "member": member,
                    "exists_before_run": exists,
                }
                if path.endswith("sca_cfg_D.json"):
                    output_targets.append(record)
                    if exists:
                        mismatches.append(path + ":" + key + ":runtime_D_preseeded")
                else:
                    input_targets.append(record)
                    if not exists:
                        mismatches.append(path + ":" + key + ":input_absent")
            continue
        target_bytes = target_bytes.replace(NAME.encode(), SOURCE.encode())
        if target_bytes != source_bytes:
            mismatches.append(path)
    return {
        "exact_set": paths == source_paths,
        "input_targets": input_targets,
        "output_targets": output_targets,
        "all_input_targets_exist": bool(input_targets)
        and all(x["exists_before_run"] for x in input_targets),
        "all_28_runtime_D_targets_absent": len(output_targets) == 28
        and all(not x["exists_before_run"] for x in output_targets),
        "mismatches": mismatches,
        "valid": paths == source_paths
        and not mismatches
        and bool(input_targets)
        and all(x["exists_before_run"] for x in input_targets)
        and len(output_targets) == 28
        and all(not x["exists_before_run"] for x in output_targets),
    }


def expected_projected_paths(files: dict[str, bytes]) -> set[str]:
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    result = {f"{NAME}/{path}" for path in manifest["files"]}
    for sca_name in (
        "workload/runtime/sca_cfg.json",
        "workload/runtime/sca_cfg_D.json",
    ):
        for record in json.loads(files[sca_name]).values():
            if isinstance(record, dict) and isinstance(record.get("path"), str):
                result.add(record["path"])
    result.update(
        {
            f"run_{NAME}/sim_results/return_observer/return_observer.log",
            f"evidence_{NAME}/CANONICAL_PROGRESS_DECISION.json",
            f"evidence_{NAME}/actual_simulator_argv.txt",
            f"{NAME}_return/RETURN_MANIFEST.json",
            f"{NAME}_return.zip.sha256",
        }
    )
    return result


def budget_contract(files: dict[str, bytes], manifest: dict) -> bool:
    budget = manifest.get("path_length_budget", {})
    expected = expected_projected_paths(files)
    declared = set(budget.get("projected_relative_paths", []))
    inner = list(manifest["files"])
    components = sorted(
        {
            component
            for path in inner
            for component in path.replace("\\", "/").split("/")
            if len(component) > 48
        }
    )
    exceptions = sorted(
        item.get("component") for item in budget.get("long_component_exceptions", [])
    )
    return (
        budget.get("rule_id")
        == "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001"
        and declared == expected
        and budget.get("max_projected_relative_path_chars") == max(map(len, expected))
        and budget.get("max_projected_absolute_path_chars")
        == budget.get("declared_target_root_max_chars") + 1 + max(map(len, expected))
        and budget.get("max_zip_member_chars")
        == max(len(NAME + "/" + path) for path in [*inner, "TEST_PACKAGE_MANIFEST.json"])
        and budget.get("max_inner_suffix_chars") == max(map(len, inner))
        and budget.get("max_inner_depth")
        == max(path.count("/") + 1 for path in inner)
        and exceptions == components
        and budget.get("max_projected_absolute_path_chars")
        <= budget.get("absolute_path_limit_chars")
        and b"package_path_budget_guard_v34.py" in files["PREPARE_AND_RUN.sh"]
    )


def budget_controls(files: dict[str, bytes], manifest: dict) -> dict:
    controls = {}
    for name, mutate in {
        "over_budget_deep_member": lambda value: value["path_length_budget"][
            "projected_relative_paths"
        ].append("x/" + "d" * 241),
        "repeated_full_identity": lambda value: value["path_length_budget"][
            "projected_relative_paths"
        ].append(f"{NAME}/{NAME}/payload"),
        "deleted_direct_consumer_reference": lambda value: value[
            "path_length_budget"
        ]["projected_relative_paths"].pop(),
    }.items():
        candidate = json.loads(json.dumps(manifest))
        mutate(candidate)
        failed = not budget_contract(files, candidate)
        controls[name] = {"exit_code": 1 if failed else 0, "failed_closed": failed}

    with tempfile.TemporaryDirectory(prefix="qadd-v35-path-") as raw:
        temp = Path(raw)
        with zipfile.ZipFile(base.ZIP) as archive:
            archive.extractall(temp)
        package = temp / NAME
        guard = package / "package_tools/package_path_budget_guard_v34.py"
        result = subprocess.run(
            [
                sys.executable,
                str(guard),
                "--manifest",
                str(package / "TEST_PACKAGE_MANIFEST.json"),
                "--server-root",
                "/" + "r" * 240,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        controls["actual_root_over_budget"] = {
            "exit_code": result.returncode,
            "failed_closed": result.returncode == 5
            and "server root/path budget exceeded" in result.stderr,
        }
    return controls


def main() -> int:
    immediate_files, _ = base.v28.load(IMMEDIATE_SOURCE_ZIP, SOURCE)
    base.v29.workload_frozen = workload_frozen
    original_contract = base.rowpair_contract

    def rowpair(files: dict[str, bytes], manifest: dict) -> dict:
        result = original_contract(files, manifest)
        immediate = manifest["source_assets"].get("fp32_rowpair_v34_source_zip", {})
        result["checks"]["immediate_v34_source_bound"] = (
            immediate.get("sha256") == base.sha(IMMEDIATE_SOURCE_ZIP)
        )
        result["valid"] = all(result["checks"].values())
        return result

    base.rowpair_contract = rowpair
    original_load = base.v28.load

    def routed_load(path: Path, name: str):
        if path == FROZEN_V30_ZIP and name == SOURCE:
            return immediate_files, {}
        return original_load(path, name)

    base.v28.load = routed_load
    base.SOURCE_ZIP = FROZEN_V30_ZIP
    try:
        base_exit = base.main()
    finally:
        base.SOURCE_ZIP = IMMEDIATE_SOURCE_ZIP
        base.v28.load = original_load

    report = json.loads(base.OUT.read_text(encoding="utf-8"))
    files, manifest = original_load(base.ZIP, NAME)
    budget_valid = budget_contract(files, manifest)
    negatives = budget_controls(files, manifest)
    report["checks"]["path_length_budget"] = budget_valid
    report["checks"]["path_length_negatives"] = all(
        value["failed_closed"] for value in negatives.values()
    )
    report["path_length_budget"] = manifest["path_length_budget"]
    report["path_length_negative_controls"] = negatives
    report["errors"] = [
        key for key, value in report["checks"].items() if not value
    ]
    report["error_count"] = len(report["errors"])
    report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = not report["errors"]
    report["status"] = (
        "PACKAGE_READY_NOT_RUN" if not report["errors"] else "QUARANTINED"
    )
    base.OUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "errors": report["errors"],
                "zip_sha256": report["zip_sha256"],
                "report_sha256": base.sha(base.OUT),
                "base_exit_before_path_gate": base_exit,
            },
            indent=2,
        )
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
