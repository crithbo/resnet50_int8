from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v15_abpe_syntax_fix_final_zip as prior  # noqa: E402


PLAN_SHA256 = "532d176ed70fb630dbc797263409887a2d32bafecd5f9af3a21077d56a157bfe"
SERVER_RULE_SHA256 = (
    "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
)
RULE_IDS = {
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
    "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
}
BOUND_V15_RETURN_SHA256 = (
    "592d792e9f0d647f1a3d43bdc8b3a5bbffb1956d4ff908916d0f6d78cf9a94d2"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_current_receipts() -> None:
    prior.PLAN_SHA256 = PLAN_SHA256
    base = prior.prior.common.base
    for path, digest in list(base.CURRENT_RECEIPTS.items()):
        if digest == (
            "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
        ):
            base.CURRENT_RECEIPTS[path] = SERVER_RULE_SHA256
    base.REQUIRED_RULE_IDS.update(RULE_IDS)


def validate_v16(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    zip_sha256: str,
) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    runner = entries["PREPARE_AND_RUN.sh"].decode("utf-8")
    observer = entries["tb_probe/native_return_observer.svh"].decode("utf-8")
    guard = entries[
        "package_tools/node0004_package_observer_guard.py"
    ].decode("utf-8")
    receipts = manifest.get("active_receipts", {})
    rules = set(receipts.get("rules", []))
    profile = manifest.get("runtime_preflight_profile", {})
    repair = manifest.get("observer_task_terminator_repair", {})
    task_tail = observer[
        observer.index(
            "task automatic return_obs_write_abpe_state(input string event_name);"
        ):
    ]
    checks = {
        "current_server_rule_receipt": (
            receipts.get("server_package_rule_sha256")
            == SERVER_RULE_SHA256
        ),
        "current_rule_ids": RULE_IDS.issubset(rules),
        "task_closes_with_endtask": (
            task_tail.count("endtask") == 1
            and re.search(r"\$fflush\(return_obs_fd\);.*?endtask\s*$",
                          task_tail, flags=re.DOTALL)
            is not None
        ),
        "task_repair_bound_to_v15_return": (
            repair.get("bound_return_sha256") == BOUND_V15_RETURN_SHA256
            and repair.get("new_sha256") == manifest.get("observer_sha256")
        ),
        "runner_has_no_hardcoded_sha256": (
            re.search(r"\b[0-9a-f]{64}\b", runner) is None
            and "--expected-sha256" not in runner
        ),
        "runner_guard_uses_manifest": (
            '--manifest "$package_root/package_manifest.json"' in runner
        ),
        "guard_expected_identity_manifest_sourced": (
            'parser.add_argument("--manifest"' in guard
            and "manifest[\"observer_binding_four_way\"][\"source\"][\"sha256\"]"
            in guard
            and "--expected-sha256" not in guard
        ),
        "ordinary_user_root_profile": (
            profile.get("user_supplied_root") is True
            and profile.get("server_source_identity_bound") is False
            and profile.get("runner_hardcoded_observer_sha_count") == 0
        ),
        "no_server_source_preflight_commands": all(
            token not in runner
            for token in (
                "git rev-parse",
                "sha256sum \"$server_root",
                "find \"$server_root",
                "rg \"$server_root",
                "rtl/filelists",
                "README_HARDWARE_SIM_ENTRY",
            )
        ),
        "positive_control_valid": positive.get("valid") is True,
        "positive_control_zip_bound": (
            positive.get("zip", {}).get("sha256") == zip_sha256
        ),
        "positive_control_unique_compile_exit": (
            positive.get("positive_control", {}).get(
                "runner_exit_code"
            ) == 73
            and positive.get("positive_control", {}).get(
                "expected_stub_exit_code"
            ) == 73
            and positive.get("positive_control", {}).get(
                "compile_stub_invocation_count"
            ) == 1
        ),
        "positive_control_actual_argv": (
            "Makefile.tb_NDP_Top_new_phy"
            in (
                positive.get("positive_control", {}).get(
                    "actual_compile_argv"
                )
                or ""
            )
            and "VCS_EXTRA_OPTS=" in (
                positive.get("positive_control", {}).get(
                    "actual_compile_argv"
                )
                or ""
            )
        ),
        "wrong_identity_negative_failed_closed": (
            positive.get("negative_controls", {}).get(
                "all_failed_closed"
            ) is True
            and positive.get("negative_controls", {})
            .get("wrong_observer_identity_sha", {})
            .get("compile_stub_invocation_count")
            == 0
        ),
    }
    errors.extend(
        f"v16 current-rule check failed: {name}"
        for name, valid in checks.items()
        if not valid
    )
    return not errors, errors, checks


def negative_controls(
    entries: dict[str, bytes],
    manifest: dict[str, Any],
    positive: dict[str, Any],
    zip_sha256: str,
) -> dict[str, Any]:
    cases: dict[str, tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]] = {}
    changed = dict(entries)
    changed["PREPARE_AND_RUN.sh"] = (
        entries["PREPARE_AND_RUN.sh"].decode("utf-8")
        + "\n# "
        + "0" * 64
        + "\n"
    ).encode("utf-8")
    cases["runner_hardcoded_sha"] = (changed, manifest, positive)

    bad_manifest = copy.deepcopy(manifest)
    bad_manifest["active_receipts"]["rules"].remove(
        "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001"
    )
    cases["missing_strict_runtime_rule"] = (
        entries,
        bad_manifest,
        positive,
    )

    changed = dict(entries)
    changed["package_tools/node0004_package_observer_guard.py"] = (
        entries["package_tools/node0004_package_observer_guard.py"]
        .decode("utf-8")
        .replace(
            'parser.add_argument("--manifest", type=Path, required=True)',
            'parser.add_argument("--expected-sha256", required=True)',
            1,
        )
        .encode("utf-8")
    )
    cases["guard_second_expected_sha_source"] = (
        changed,
        manifest,
        positive,
    )

    bad_positive = copy.deepcopy(positive)
    bad_positive["positive_control"]["compile_stub_invocation_count"] = 0
    cases["compile_stub_not_reached"] = (
        entries,
        manifest,
        bad_positive,
    )

    result: dict[str, Any] = {}
    for name, (changed_entries, changed_manifest, changed_positive) in (
        cases.items()
    ):
        valid, errors, _ = validate_v16(
            changed_entries,
            changed_manifest,
            changed_positive,
            zip_sha256,
        )
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
    positive_control: Path,
) -> dict[str, Any]:
    configure_current_receipts()
    raw = prior.audit(project_root, zip_path, sidecar, python, builder)
    _, entries = prior.prior._entries(zip_path)
    manifest = json.loads(entries["package_manifest.json"])
    positive = json.loads(positive_control.read_text(encoding="utf-8"))
    zip_digest = sha256_file(zip_path)
    valid, v16_errors, checks = validate_v16(
        entries, manifest, positive, zip_digest
    )
    negatives = negative_controls(
        entries, manifest, positive, zip_digest
    )
    superseded_base_error = (
        "OBSERVER_REPAIR: runner does not bind the repaired observer SHA"
    )
    errors = [
        item for item in raw["errors"] if item != superseded_base_error
    ]
    observer_validation = raw.get(
        "observer_compile_repair_validation", {}
    )
    observer_validation["errors"] = [
        item
        for item in observer_validation.get("errors", [])
        if item != "runner does not bind the repaired observer SHA"
    ]
    observer_validation["valid"] = not observer_validation["errors"]
    raw.setdefault("not_applicable", {})[
        "legacy_runner_hardcoded_observer_sha"
    ] = (
        "superseded by "
        "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001; "
        "the runner reads package-local observer identity from the final "
        "manifest single source of truth"
    )
    errors.extend(f"V16: {item}" for item in v16_errors)
    if not negatives["all_failed_closed"]:
        errors.append("v16 current-rule negative control did not fail closed")
    all_negatives = (
        raw["all_required_negative_controls_fail_closed"]
        and negatives["all_failed_closed"]
    )
    passed = valid and all_negatives and not errors
    raw.update(
        {
            "schema": "node0004-v16-final-zip-current-rule-audit-v1",
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if passed
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "errors": errors,
            "error_count": len(errors),
            "all_required_negative_controls_fail_closed": all_negatives,
            "runner_positive_control": {
                "report_path": str(positive_control),
                "report_sha256": sha256_file(positive_control),
                "valid": positive.get("valid"),
                "actual_compile_argv": positive.get(
                    "positive_control", {}
                ).get("actual_compile_argv"),
                "expected_stub_exit_code": 73,
            },
            "v16_current_rule_validation": {
                "valid": valid,
                "errors": v16_errors,
                "checks": checks,
                "negative_controls": negatives,
            },
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
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
    parser.add_argument("--positive-control", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.python.resolve(),
        args.builder.resolve(),
        args.positive_control.resolve(),
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
