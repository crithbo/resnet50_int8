from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_gap_node0071_v10_runner_guard_package as base


SOURCE_NAME = "r5_n71_gap_v11_runner_rule"
INSTALL_NAME = "r5_n71_gap_v12_minruntime"
PACKAGE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "dd3453ad79c87a60bf86bb492ac250bdf30a7369d9cea5498c4971ddcc524680"
)
SERVER_RULE_SHA256 = (
    "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
)
OBSERVER_SHA256 = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)
IDENTITY_POINTER = "/files/tb_probe~1native_return_observer.svh/sha256"
STRICT_RULE_ID = (
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001"
)
POSITIVE_RULE_ID = (
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001"
)
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    "package_tools/gap_node0071_package_observer_guard.py",
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
        "current server-package rules: strict local audit and minimal runtime"
    )
    base.RULE_RECEIPTS = receipts


def rewrite_runner_identity_only(package: Path, observer_sha: str) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if text.count(SOURCE_NAME) < 1 or text.count(observer_sha) != 1:
        raise BuildError("source v11 runner identity/SHA shape differs")
    runner.write_text(
        text.replace(SOURCE_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )


def rewrite_runner_manifest_identity(package: Path) -> None:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    old = (
        'python3 "$observer_guard" --package-root "$package_root"   '
        '--expected-sha256   "' + OBSERVER_SHA256 + '"   '
        '--runner "$package_root/PREPARE_AND_RUN.sh" \\\n'
        '  >"$evidence_root/observer_precompile.json" || exit 7'
    )
    new = (
        'python3 "$observer_guard" --package-root "$package_root"   '
        '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json"   '
        '--runner "$package_root/PREPARE_AND_RUN.sh" \\\n'
        '  >"$evidence_root/observer_precompile.json" || exit 7'
    )
    if text.count(old) != 1:
        raise BuildError("hardcoded observer guard call is not unique")
    text = text.replace(old, new)
    runner.write_text(text, encoding="utf-8", newline="\n")
    final = runner.read_text(encoding="utf-8")
    if (
        OBSERVER_SHA256 in final
        or final.count("--manifest") != 1
        or "--expected-sha256" in final
        or f'install_name="{INSTALL_NAME}"' not in final
    ):
        raise BuildError("manifest-single-source runner rewrite differs")


def manifest_guard(package: Path) -> dict[str, Any]:
    receipt = base.run_package_tool(
        [
            sys.executable,
            str(
                package
                / "package_tools/gap_node0071_package_observer_guard.py"
            ),
            "--package-root",
            str(package),
            "--manifest",
            str(package / "TEST_PACKAGE_MANIFEST.json"),
            "--runner",
            str(package / "PREPARE_AND_RUN.sh"),
        ],
        package,
    )
    if receipt["exit_code"] != 0:
        raise BuildError(
            f"manifest observer guard failed: "
            f"{receipt['stdout']} {receipt['stderr']}"
        )
    result = json.loads(receipt["stdout"])
    if (
        result.get("valid") is not True
        or result.get("identity_source") != "final_manifest_single_source"
        or result.get("identity_match") is not True
    ):
        raise BuildError("manifest observer guard receipt differs")
    return result


def update_manifest(package: Path) -> None:
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plan_sha = base.sha256(ROOT / ".agents/plan.md")
    manifest.update(
        {
            "schema": "gap-node0071-progress-server-package-v12",
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "package-only minimal-runtime preflight and manifest single "
                "identity source; frozen GAP sum/tail/config/golden, 73-file "
                "numeric workload and observer algorithm unchanged; "
                "no E3/E4/E5"
            ),
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "server_source_preflight_performed": False,
        }
    )
    contract = manifest["final_zip_rule_self_audit_contract"]
    applicable = list(contract["applicable_rule_ids"])
    for rule_id in (STRICT_RULE_ID, POSITIVE_RULE_ID):
        if rule_id not in applicable:
            applicable.append(rule_id)
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
    observer = manifest["package_local_observer"]
    observer.pop("sha256", None)
    observer.update(
        {
            "identity_json_pointer": IDENTITY_POINTER,
            "identity_single_source": True,
            "runtime_guard_expected_sha_hardcoded": False,
        }
    )
    observer_binding = manifest["observer_binding_contract"]
    observer_binding.pop("source_sha256", None)
    observer_binding.update(
        {
            "source_identity_json_pointer": IDENTITY_POINTER,
            "runner_expected_sha_hardcoded": False,
        }
    )
    manifest.pop("runner_positive_control_rule_refresh", None)
    manifest["strict_local_audit_minimal_runtime_refresh"] = {
        "source_v11_zip_sha256": SOURCE_SHA256,
        "trigger": "POST_GENERATION_CURRENT_RULE_DRIFT",
        "server_rule_sha256": SERVER_RULE_SHA256,
        "rule_ids": [STRICT_RULE_ID, POSITIVE_RULE_ID],
        "local_final_zip_audit": "STRICT",
        "runtime_preflight_profile":
            "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
        "server_source_files_inspected": False,
        "server_source_files_required_before_compile": False,
        "package_observer_identity_json_pointer": IDENTITY_POINTER,
        "runner_expected_sha_hardcoded": False,
        "runner_algorithm_changed": True,
        "runner_change": (
            "observer expected identity now loaded from final manifest; no "
            "secondary SHA literal"
        ),
        "observer_algorithm_changed": False,
        "numeric_workload_changed": False,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED),
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_v12_minimal_runtime_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "package_side_change": (
                "fresh identity/SCA namespace/manifest/README plus runner "
                "manifest-single-source guard and package-local guard tool"
            ),
        }
    )
    manifest["files"] = base.file_records(package)
    base.write_json(manifest_path, manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    original_rewrite = base.rewrite_runner
    base.rewrite_runner = rewrite_runner_identity_only
    try:
        package, proof = base.build_directory(destination)
    finally:
        base.rewrite_runner = original_rewrite
    shutil.copy2(
        ROOT / "tools/gap_node0071_manifest_observer_guard.py",
        package
        / "package_tools/gap_node0071_package_observer_guard.py",
    )
    rewrite_runner_manifest_identity(package)
    (package / "README.md").write_text(
        "# GAP node0071 v12 minimal-runtime package\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. Local final-ZIP "
        "audit is strict; server runtime uses the user-supplied-root "
        "no-source-preflight profile and proceeds to real compile without "
        "requiring existing server RTL/TB/Makefile/filelist/Git/README/"
        "observer identities. The package-local observer identity has one "
        "authoritative source: `" + IDENTITY_POINTER + "` in the final "
        "manifest; the runner contains no duplicate expected SHA. Frozen "
        "numeric workload, configs, goldens, sum/tail and observer algorithm "
        "are unchanged.\n\nRun once with:\n\n```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package)
    preflight = base.package_preflight(package)
    guard = manifest_guard(package)
    return package, {
        **proof,
        "package_preflight_after_minimal_runtime_refresh": preflight,
        "manifest_observer_guard": guard,
        "server_rule_sha256": SERVER_RULE_SHA256,
        "new_rule_ids": [STRICT_RULE_ID, POSITIVE_RULE_ID],
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    base.deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    first_sha = base.sha256(zip_path)
    first_tree = base.file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v12-repeat-"
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
            print(f"refusing to overwrite: {path}", file=sys.stderr)
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
            "schema": "gap-node0071-minimal-runtime-validation-v12",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_sha256": digest,
            "zip_size_bytes": zip_path.stat().st_size,
            "sidecar": str(sidecar),
            "bound_source_zip": str(SOURCE_ZIP),
            "bound_source_zip_sha256": SOURCE_SHA256,
            "source_v11_quarantined": True,
            **proof,
            "repeated_build": repeated,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "server_action": False,
        }
        base.write_json(validation_path, validation)
    except Exception as error:
        print(f"GAP v12 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
