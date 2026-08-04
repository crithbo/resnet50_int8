from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_gap_node0071_v10_runner_guard_package as base


SOURCE_NAME = "r5_n71_gap_v10_runner_guard"
INSTALL_NAME = "r5_n71_gap_v11_runner_rule"
PACKAGE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "1293d2f3868974edefad562bc28d9128a23bf3ff609df096bd68c11fd6a3a2b8"
)
SERVER_RULE_SHA256 = (
    "bcf62cc301f721a48641ecd9a7a1c6ad38a16cc831fb7a695da9229782f35f38"
)
NEW_RULE_ID = "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001"
OBSERVER_SHA256 = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class BuildError(ValueError):
    pass


def configure_base() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.OUTPUT_ROOT = PACKAGE_ROOT
    receipts = [dict(item) for item in base.RULE_RECEIPTS]
    receipts[3]["sha256"] = SERVER_RULE_SHA256
    receipts[3]["reason"] = (
        "current server-package rules including runner positive control"
    )
    base.RULE_RECEIPTS = receipts


def rewrite_runner_identity_only(package: Path, observer_sha: str) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(SOURCE_NAME) < 1:
        raise BuildError("source v10 identity absent from runner")
    if text.count(observer_sha) != 1:
        raise BuildError("observer SHA binding is not unique")
    runner.write_text(
        text.replace(SOURCE_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )
    final = runner.read_text(encoding="utf-8")
    if (
        SOURCE_NAME in final
        or final.count(observer_sha) != 1
        or f'install_name="{INSTALL_NAME}"' not in final
    ):
        raise BuildError("runner identity-only rebinding differs")


def update_receipts(manifest: dict[str, Any]) -> None:
    plan_sha = base.sha256(ROOT / ".agents/plan.md")
    contract = manifest["final_zip_rule_self_audit_contract"]
    applicable = list(contract["applicable_rule_ids"])
    if NEW_RULE_ID not in applicable:
        applicable.append(NEW_RULE_ID)
    contract.update(
        {
            "read_receipt": base.RULE_RECEIPTS,
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


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    original_rewrite = base.rewrite_runner
    base.rewrite_runner = rewrite_runner_identity_only
    try:
        package, proof = base.build_directory(destination)
    finally:
        base.rewrite_runner = original_rewrite

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v11",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "post-generation current-rule identity refresh only; runner "
                "algorithm, observer, frozen GAP sum/tail/config/golden and "
                "73-file numeric workload unchanged; no E3/E4/E5"
            ),
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
        }
    )
    update_receipts(manifest)
    manifest.pop("runner_observer_sha_repair", None)
    manifest["runner_positive_control_rule_refresh"] = {
        "source_v10_zip_sha256": SOURCE_SHA256,
        "trigger": "POST_GENERATION_CURRENT_RULE_DRIFT",
        "new_server_rule_sha256": SERVER_RULE_SHA256,
        "new_rule_id": NEW_RULE_ID,
        "runner_algorithm_changed": False,
        "observer_algorithm_changed": False,
        "numeric_workload_changed": False,
        "required_positive_control": (
            "fresh extract real PREPARE_AND_RUN.sh reaches safe compile stub "
            "after package/install/precompile guards"
        ),
        "required_negative_control": (
            "wrong observer identity/SHA fails before compile"
        ),
        "allowed_changed_paths": sorted(ALLOWED_CHANGED),
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_v11_runner_rule_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "package_side_change": (
                "fresh identity/SCA namespace/manifest/README/rule receipt "
                "only; runner algorithm unchanged"
            ),
        }
    )
    (package / "README.md").write_text(
        "# GAP node0071 v11 runner-rule receipt refresh\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It reuses "
        "the frozen v10 runner algorithm, package-local observer, numeric "
        "workload, configs, goldens, exact sum and exact UINT8 tail. The "
        "fresh identity binds server rule SHA `" + SERVER_RULE_SHA256 + "` "
        "and `" + NEW_RULE_ID + "`. Final self-audit invokes the real "
        "runner from a fresh extract, reaches a safe compile stub, records "
        "actual compile argv, and proves wrong identity/SHA fails before "
        "compile.\n\nRun once with:\n\n```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest["files"] = base.file_records(package)
    base.write_json(manifest_path, manifest)
    preflight = base.package_preflight(package)
    guard = base.observer_guard(package, OBSERVER_SHA256)
    return package, {
        **proof,
        "package_preflight_after_receipt_refresh": preflight,
        "observer_guard_after_receipt_refresh": guard,
        "new_rule_id": NEW_RULE_ID,
        "new_server_rule_sha256": SERVER_RULE_SHA256,
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    base.deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = base.sha256(zip_path)
    first_tree = base.file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v11-repeat-"
    ) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeated_zip = Path(temporary) / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if (
            base.sha256(repeated_zip) != first_sha
            or base.file_records(repeated, exclude_manifest=False)
            != first_tree
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
    package_path = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation_path = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation_path):
        if path.exists():
            print(f"refusing to overwrite: {path}")
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = base.sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        validation = {
            "schema": "gap-node0071-runner-rule-refresh-validation-v11",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v10_quarantined": True,
            **proof,
            "repeated_build": repeated,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_action": False,
        }
        base.write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v11 build failed: {error}")
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
