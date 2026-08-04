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
from tools import build_gap_node0071_v13_buffer_to_ga_diag_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v19_bp_pre_factor_stage_scope"
INSTALL_NAME = "r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix"
TEST_ID = "r5-gap-node0071-v20-bp-pre-factor-stage-scope-runnerfix"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "68c9bd007d8dea02a13aefc7ac9ddda3623b1afb83ad9fdb97552940579ce098"
)
SERVER_RULE_SHA256 = (
    "1e0b40589dddee3bf2b4d081936d37d9a25f78ea2ceb98bc08f2dcf813438589"
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def current_receipts(
    source_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for item in source_manifest[
        "final_zip_rule_self_audit_contract"
    ]["read_receipt"]:
        receipt = dict(item)
        receipt["sha256"] = sha256(ROOT / receipt["path"])
        receipt["current_match"] = True
        receipts.append(receipt)
    return receipts


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest = base.replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    receipt_by_path = {item["path"]: item["sha256"] for item in receipts}
    manifest.update(
        {
            "schema":
                "gap-node0071-bp-pre-factor-stage-scope-server-package-v20",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "v19 factor observer and ordered-stage canonical parser "
                "preserved; EXIT-trap finalizer now derives the manifest "
                "path from global package_root"
            ),
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
    audit_contract = manifest["final_zip_rule_self_audit_contract"]
    audit_contract.update(
        {
            "read_receipt": receipts,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only":
                sha256(ROOT / ".agents/plan.md"),
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    rules = manifest["rule_receipts"]
    for path, digest in receipt_by_path.items():
        if path.endswith("生成前必读索引.md"):
            rules["generation_index_sha256"] = digest
        elif path.endswith("算子配置规则.md"):
            rules["common_operator_rule_sha256"] = digest
        elif path.endswith("NDP硬件字段语义.md"):
            rules["ndp_field_rule_sha256"] = digest
        elif path.endswith("服务器测试包生成规则.md"):
            rules["server_rule_sha256"] = digest
        elif path.endswith("GAP_int32_mac_bypass_rules.md"):
            rules["gap_int32_rule_sha256"] = digest
        elif path.endswith("GAP_probe_v7_validator_rules.md"):
            rules["gap_probe_rule_sha256"] = digest
        elif path.endswith("精确UINT8量化尾专项规则.md"):
            rules["exact_uint8_tail_rule_sha256"] = digest
    rules["current_match"] = True
    rules["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    manifest["runner_finalizer_manifest_scope_fix"] = {
        "source_package": SOURCE_NAME,
        "source_package_sha256": SOURCE_SHA256,
        "first_divergence":
            "EXIT_TRAP_FINALIZER_PACKAGE_MANIFEST_UNBOUND_VARIABLE",
        "old_expression": "$package_manifest",
        "new_expression": "$package_root/TEST_PACKAGE_MANIFEST.json",
        "owner": "package-local PREPARE_AND_RUN.sh finalizer",
        "functional_or_config_change": False,
        "positive_control_required": (
            "safe compile stub reaches exit 86 and finalizer emits no "
            "unbound-variable diagnostic"
        ),
    }
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_bp_pre_factor_diag_v20_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus EXIT-trap-safe global package-root "
                "manifest binding"
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = file_records(
        package / "workload", exclude_manifest=False
    )
    numeric_before = {
        path: record
        for path, record in numeric_before.items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    base.rewrite_identity(package)
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    old = '    --manifest "$package_manifest" \\\n'
    new = (
        '    --manifest "$package_root/TEST_PACKAGE_MANIFEST.json" \\\n'
    )
    if text.count(old) != 1:
        raise BuildError("v19 finalizer manifest binding marker differs")
    runner.write_text(
        text.replace(old, new, 1), encoding="utf-8", newline="\n"
    )
    (package / "README.md").write_text(
        "# GAP node0071 v20 factor/stage-scope diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves "
        "the v19 factor observer, ordered-stage canonical parser, 73 numeric "
        "files and all functional/config/golden/execplan semantics. The "
        "package-only fix makes the EXIT-trap finalizer read the manifest "
        "through global `package_root`, avoiding the quarantined v19 local-"
        "scope variable failure.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = file_records(
        package / "workload", exclude_manifest=False
    )
    numeric_after = {
        path: record
        for path, record in numeric_after.items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric/workload tree drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("relative file set changed")
    changed = {
        path
        for path in source_records
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    frozen = sorted(set(source_records) - ALLOWED_CHANGED)
    return package, {
        "source_v19_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": len(numeric_after),
        "frozen_numeric_workload_tree_equal": True,
        "frozen_semantic_file_count": len(frozen),
        "frozen_semantic_tree_equal": all(
            source_records[path] == final_records[path] for path in frozen
        ),
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = sha256(zip_path)
    tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v20-repeat-"
    ) as temp:
        repeated, _ = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if sha256(repeated_zip) != digest:
            raise BuildError("repeat ZIP differs")
        if file_records(repeated, exclude_manifest=False) != tree:
            raise BuildError("repeat package tree differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
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
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        result = {
            "schema":
                "gap-node0071-bp-pre-factor-stage-scope-v20-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "test_id": TEST_ID,
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "sidecar_sha256": sha256(sidecar),
            **proof,
            "repeat_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(validation, result)
    except Exception as error:
        print(f"GAP v20 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
