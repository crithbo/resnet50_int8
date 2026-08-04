from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_v13_buffer_to_ga_diag_package as v13


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v14_accum_enable"
INSTALL_NAME = "r5_n71_gap_v15_feature_enable_rule"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = "98ef0a67d09f6790c2dfa8fb7445b6535ae605fc92c9455e5513b21210f5271b"
SERVER_RULE_SHA256 = (
    "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
)
FEATURE_RULE_ID = (
    "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
)
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_source() -> None:
    v13.SOURCE_NAME = SOURCE_NAME
    v13.INSTALL_NAME = INSTALL_NAME
    v13.SOURCE_ZIP = SOURCE_ZIP
    v13.SOURCE_SHA256 = SOURCE_SHA256
    v13.SERVER_RULE_SHA256 = SERVER_RULE_SHA256


def patch_runner_receipt(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old_true = (
        "printf 'observer_enabled_and_returned=true\\n"
        "buffer_to_ga_accum_state_enabled=true\\n'"
    )
    new_true = (
        "printf 'observer_enabled_and_returned=true\\n"
        "buffer_to_ga_accum_state_enabled=true\\n"
        "buffer_to_ga_accum_limit=512\\n'"
    )
    if text.count(old_true) != 1:
        raise BuildError("feature success receipt marker differs")
    text = text.replace(old_true, new_true, 1)
    old_false = (
        "printf 'observer_enabled_and_returned=false\n"
        "'       >\"$evidence_root/observer_binding.txt\""
    )
    new_false = (
        "printf 'observer_enabled_and_returned=false\\n"
        "buffer_to_ga_accum_state_enabled=false\\n"
        "buffer_to_ga_accum_limit=UNKNOWN\\n"
        "'       >\"$evidence_root/observer_binding.txt\""
    )
    if text.count(old_false) != 1:
        raise BuildError("feature failure receipt marker differs")
    text = text.replace(old_false, new_false, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def update_manifest(
    package: Path, source_manifest: dict[str, Any]
) -> None:
    manifest = v13.replace_identity(source_manifest)
    plan_sha = sha256(ROOT / ".agents/plan.md")
    receipts = v13.current_rule_receipts()
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v15",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    contract = manifest["final_zip_rule_self_audit_contract"]
    applicable = list(contract["applicable_rule_ids"])
    if FEATURE_RULE_ID not in applicable:
        applicable.append(FEATURE_RULE_ID)
    contract.update(
        {
            "read_receipt": receipts,
            "applicable_rule_ids": applicable,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
            "final_zip_independent_validator_required": True,
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    manifest["rule_receipts"].update(
        {
            "server_rule_sha256": SERVER_RULE_SHA256,
            "current_match": True,
            "plan_sha256_mutable_provenance_only": plan_sha,
        }
    )
    manifest["diagnostic_feature_runtime_enable_contract"] = {
        "rule_id": FEATURE_RULE_ID,
        "feature_name": "buffer_to_ga_accumulator_state",
        "runtime_enable_plusarg": "+RETURN_OBS_ACCUM_STATE",
        "runtime_limit_plusarg": "+RETURN_OBS_ACCUM_LIMIT=512",
        "effective_limit": 512,
        "time0_marker": {
            "return_target": "runs/return_observer.log",
            "required_tokens": [
                "accum_state=1",
                "accum_limit=512"
            ],
            "semantic_interpretation": "feature_enabled=true; effective_limit=512"
        },
        "feature_specific_binding_receipt": {
            "return_target": "evidence/observer_binding.txt",
            "success_exact_lines": [
                "buffer_to_ga_accum_state_enabled=true",
                "buffer_to_ga_accum_limit=512"
            ],
            "failure_exact_lines": [
                "buffer_to_ga_accum_state_enabled=false",
                "buffer_to_ga_accum_limit=UNKNOWN"
            ]
        },
        "expected_record_schema": [
            "BUFFER_TO_GA_COUNTS",
            "BUFFER_TO_GA_STATE"
        ],
        "return_allowlist_targets": [
            "evidence/actual_simulator_argv.txt",
            "evidence/observer_binding.txt",
            "runs/return_observer.log"
        ],
        "disabled_zero_classification":
            "DISABLED_INSTRUMENTATION_ZERO",
        "analysis_three_way_conjunction_required": True,
        "observer_algorithm_changed": False,
        "numeric_workload_changed": False,
        "config_changed": False,
        "golden_changed": False
    }
    manifest["post_generation_rule_drift_refresh"] = {
        "source_v14_zip_sha256": SOURCE_SHA256,
        "old_server_rule_sha256":
            "88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6",
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "trigger_rule_id": FEATURE_RULE_ID,
        "source_v14_quarantined": True,
        "observer_algorithm_changed": False,
        "runner_feature_enable_behavior_changed": False,
        "runner_feature_receipt_schema_extended": True,
        "numeric_workload_changed": False,
        "config_semantics_changed": False,
        "golden_changed": False,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED)
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_v15_feature_enable_rule_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity/SCA namespace/manifest/README/current-rule "
                "receipt and feature-specific binding receipt schema"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = v13.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = {
        path: receipt
        for path, receipt in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    v13.rewrite_identity(package)
    patch_runner_receipt(package)
    (package / "README.md").write_text(
        "# GAP node0071 v15 feature-enable-rule package\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the v14 observer, runtime feature enable/limit behavior, frozen "
        "configuration semantics, golden, and all 73 numeric files. The "
        "fresh identity materializes current rule "
        "`CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001` and "
        "extends the returned feature receipt with the effective limit. No "
        "functional RTL or DUT behavior changes.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = {
        path: receipt
        for path, receipt in file_records(
            package / "workload", exclude_manifest=False
        ).items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric workload drifted")
    final_records = file_records(package, exclude_manifest=False)
    changed = {
        path
        for path in set(source_records) & set(final_records)
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    if source_records[OBSERVER_RELATIVE] != final_records[OBSERVER_RELATIVE]:
        raise BuildError("observer algorithm drifted")
    return package, {
        "source_v14_zip_sha256": SOURCE_SHA256,
        "observer_sha256": final_records[OBSERVER_RELATIVE]["sha256"],
        "numeric_workload_file_count": len(numeric_after),
        "numeric_workload_tree_equal": True,
        "observer_tree_equal": True,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = sha256(zip_path)
    first_tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v15-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        deterministic_zip(repeated, repeated_zip, archive_root=INSTALL_NAME)
        if (
            sha256(repeated_zip) != first_sha
            or file_records(repeated, exclude_manifest=False) != first_tree
        ):
            raise BuildError("repeat build differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": first_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}")
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        result = {
            "schema": "gap-node0071-feature-enable-rule-validation-v15",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v14_quarantined": True,
            **proof,
            "repeated_build": repeated,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "config_rebuilt": False,
            "server_action": False,
        }
        write_json(validation_path, result)
    except Exception as error:
        print(f"GAP v15 build failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
