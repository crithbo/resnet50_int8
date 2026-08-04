from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v14_a_pingpong_fix_final_zip as prior  # noqa: E402


PLAN_SHA256 = "558dce2c256f91bcf537750262b717db00c97ea415849d544cc13d365049a47e"
SOURCE_V14_SHA256 = (
    "4bf890b5ad57d8952226125de4979e96e0c00a1d347d2fb59aec7cabb1cf44b2"
)
BOUND_V14_RETURN_SHA256 = (
    "5a075ae69e0f89aa2da356c9968ea79de099ec7b38e1ba20b19c8a6757d2525d"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _observer_checks(
    entries: dict[str, bytes], manifest: dict[str, Any]
) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    observer_key = "tb_probe/native_return_observer.svh"
    observer = entries.get(observer_key, b"").decode("utf-8")
    old_a = """return_obs_abpe_masked_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][0]"""
    old_b = """return_obs_abpe_masked_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][1]"""
    requirements = {
        "old_vcs_failing_a_absent": old_a not in observer,
        "old_vcs_failing_b_absent": old_b not in observer,
        "a_unpacked_outer_aggregate_declared": observer.count(
            "return_obs_abpe_masked_a_mon\n"
            "          [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];"
        ) == 1,
        "b_unpacked_outer_aggregate_declared": observer.count(
            "return_obs_abpe_masked_b_mon\n"
            "          [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];"
        ) == 1,
        "a_aggregate_assigned": observer.count(
            "assign return_obs_abpe_masked_a_mon"
        ) == 1,
        "b_aggregate_assigned": observer.count(
            "assign return_obs_abpe_masked_b_mon"
        ) == 1,
        "a_snapshot_uses_aggregate": observer.count(
            "return_obs_abpe_masked_a_mon\n"
            "                        [return_obs_group_id]"
            "[return_obs_local_slice_id],"
        ) == 1,
        "b_snapshot_uses_aggregate": observer.count(
            "return_obs_abpe_masked_b_mon\n"
            "                        [return_obs_group_id]"
            "[return_obs_local_slice_id],"
        ) == 1,
    }
    errors.extend(
        f"observer syntax repair check failed: {name}"
        for name, valid in requirements.items()
        if not valid
    )
    repair = manifest.get("observer_compile_repair", {})
    identity = {
        "classification": (
            repair.get("classification")
            == "PACKAGE_LOCAL_READ_ONLY_OBSERVER_SYNTAX_FIX"
        ),
        "bound_return": (
            repair.get("bound_return_sha256") == BOUND_V14_RETURN_SHA256
        ),
        "source_v14": (
            repair.get("source_package", {}).get("sha256")
            == SOURCE_V14_SHA256
        ),
        "qualified_progress_unchanged": (
            repair.get("qualified_progress_changed") is False
        ),
        "functional_semantics_unchanged": (
            repair.get("functional_semantics_changed") is False
        ),
        "observer_identity": (
            _sha256(entries[observer_key])
            == manifest.get("observer_sha256")
            == repair.get("new_sha256")
        ),
    }
    errors.extend(
        f"observer repair identity failed: {name}"
        for name, valid in identity.items()
        if not valid
    )
    runner = entries.get("PREPARE_AND_RUN.sh", b"").decode("utf-8")
    if manifest.get("observer_sha256") not in runner:
        errors.append("runner does not bind the repaired observer SHA")
    return not errors, errors, {
        "requirements": requirements,
        "identity": identity,
        "observer_sha256": _sha256(entries[observer_key]),
    }


def _negative_controls(
    entries: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    observer_key = "tb_probe/native_return_observer.svh"
    original = entries[observer_key].decode("utf-8")
    cases: dict[str, tuple[dict[str, bytes], dict[str, Any]]] = {}

    old_expression = original.replace(
        """return_obs_abpe_masked_a_mon
                        [return_obs_group_id][return_obs_local_slice_id],""",
        """return_obs_abpe_masked_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][0],""",
        1,
    )
    bad_entries = dict(entries)
    bad_entries[observer_key] = old_expression.encode("utf-8")
    cases["vcs_failing_post_index_slice_reintroduced"] = (
        bad_entries,
        manifest,
    )

    missing_a = original.replace(
        "assign return_obs_abpe_masked_a_mon",
        "assign return_obs_abpe_masked_a_mon_REMOVED",
        1,
    )
    bad_entries = dict(entries)
    bad_entries[observer_key] = missing_a.encode("utf-8")
    cases["a_aggregate_assignment_missing"] = (bad_entries, manifest)

    missing_b = original.replace(
        "assign return_obs_abpe_masked_b_mon",
        "assign return_obs_abpe_masked_b_mon_REMOVED",
        1,
    )
    bad_entries = dict(entries)
    bad_entries[observer_key] = missing_b.encode("utf-8")
    cases["b_aggregate_assignment_missing"] = (bad_entries, manifest)

    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["observer_compile_repair"]["bound_return_sha256"] = "0" * 64
    cases["bound_return_identity_changed"] = (entries, bad_manifest)

    result: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest) in cases.items():
        valid, errors, _ = _observer_checks(changed_entries, changed_manifest)
        result[name] = {
            "failed_closed": not valid,
            "errors": errors,
        }
    result["all_failed_closed"] = all(
        item["failed_closed"] for item in result.values()
    )
    return result


def audit(
    project_root: Path,
    zip_path: Path,
    sidecar: Path,
    python: Path,
    builder: Path,
) -> dict[str, Any]:
    prior.PLAN_SHA256 = PLAN_SHA256
    raw = prior.audit(project_root, zip_path, sidecar, python, builder)
    _, entries = prior._entries(zip_path)
    manifest = json.loads(entries["package_manifest.json"])
    valid, syntax_errors, detail = _observer_checks(entries, manifest)
    negatives = _negative_controls(entries, manifest)
    errors = list(raw["errors"])
    errors.extend(f"OBSERVER_REPAIR: {item}" for item in syntax_errors)
    if not negatives["all_failed_closed"]:
        errors.append("observer syntax-repair negative control did not fail closed")
    all_negatives = (
        raw["all_required_negative_controls_fail_closed"]
        and negatives["all_failed_closed"]
    )
    passed = (
        raw["FINAL_ZIP_RULE_SELF_AUDIT_PASS"]
        and valid
        and all_negatives
        and not errors
    )
    raw.update(
        {
            "schema": "node0004-v15-abpe-syntax-fix-final-zip-audit-v1",
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if passed
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "errors": errors,
            "error_count": len(errors),
            "all_required_negative_controls_fail_closed": all_negatives,
            "observer_compile_repair_validation": {
                "valid": valid,
                "errors": syntax_errors,
                "detail": detail,
                "negative_controls": negatives,
            },
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
        }
    )
    return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.python.resolve(),
        args.builder.resolve(),
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
