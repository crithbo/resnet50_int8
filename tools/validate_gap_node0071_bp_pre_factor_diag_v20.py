from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_bp_pre_factor_diag_v19 as stage


ROOT_NAME = "r5_n71_gap_v20_bp_pre_factor_stage_scope_runnerfix"
TEST_ID = "r5-gap-node0071-v20-bp-pre-factor-stage-scope-runnerfix"
MANIFEST_BINDING = '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json"'


def configure() -> None:
    stage.ROOT_NAME = ROOT_NAME
    stage.TEST_ID = TEST_ID
    stage.MANIFEST_BINDING = MANIFEST_BINDING
    stage.factor.ROOT_NAME = ROOT_NAME
    stage.factor.TEST_ID = TEST_ID


def validate_payload(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> dict[str, Any]:
    base = stage.validate_payload(files, root_name)
    errors = list(base["errors"])
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    runner = files[stage.factor.RUNNER].decode("utf-8")
    fix = manifest.get("runner_finalizer_manifest_scope_fix", {})
    if fix.get("first_divergence") != (
        "EXIT_TRAP_FINALIZER_PACKAGE_MANIFEST_UNBOUND_VARIABLE"
    ):
        errors.append("runner finalizer root-cause receipt differs")
    if fix.get("new_expression") != (
        "$package_root/TEST_PACKAGE_MANIFEST.json"
    ):
        errors.append("runner finalizer fixed expression differs")
    if runner.count(f"    {MANIFEST_BINDING} \\") != 1:
        errors.append("global package-root manifest binding count differs")
    if "$package_manifest" in runner:
        errors.append("function-local package_manifest remains in runner")
    if runner_report is not None:
        positive = runner_report.get("positive_full_runner", {})
        stderr = str(positive.get("stderr", ""))
        if positive.get("exit_code") != 86:
            errors.append("safe compile-stub expected exit differs")
        if positive.get("make_reached") is not True:
            errors.append("safe compile stub was not reached")
        if "unbound variable" in stderr:
            errors.append("runner positive control hit unbound variable")
        if runner_report.get("positive_compile_reached") is not True:
            errors.append("runner positive compile receipt differs")
    base.update({"valid": not errors, "errors": errors})
    return base


def negative_controls(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    controls = stage.negative_controls(files, root_name)

    def run(
        name: str,
        mutated: dict[str, bytes],
        expected_fragment: str,
    ) -> None:
        result = validate_payload(mutated, root_name, runner_report)
        controls.append(
            {
                "name": name,
                "failed_closed": not result["valid"],
                "expected_error_observed": any(
                    expected_fragment in error for error in result["errors"]
                ),
                "errors": result["errors"],
            }
        )

    mutated = dict(files)
    mutated[stage.factor.RUNNER] = files[stage.factor.RUNNER].replace(
        f"    {MANIFEST_BINDING} \\\n".encode("utf-8"),
        b'    --manifest "$package_manifest" \\\n',
        1,
    )
    mutated = stage.factor._refresh_record(
        mutated, stage.factor.RUNNER
    )
    run(
        "function_local_manifest_binding_regression",
        mutated,
        "function-local package_manifest remains in runner",
    )

    if runner_report is not None:
        mutated_report = json.loads(json.dumps(runner_report))
        mutated_report["positive_full_runner"]["stderr"] = (
            "package_manifest: unbound variable"
        )
        result = validate_payload(files, root_name, mutated_report)
        controls.append(
            {
                "name": "positive_control_unbound_variable_masked",
                "failed_closed": not result["valid"],
                "expected_error_observed": (
                    "runner positive control hit unbound variable"
                    in result["errors"]
                ),
                "errors": result["errors"],
            }
        )
    return controls


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument("--runner-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        files = stage.factor.read_zip(args.zip_path, args.root_name)
        runner_report = (
            json.loads(args.runner_report.read_text(encoding="utf-8"))
            if args.runner_report
            else None
        )
        result = validate_payload(
            files, args.root_name, runner_report
        )
        controls = negative_controls(
            files, args.root_name, runner_report
        )
        self_test = stage.canonical_self_test(files)
        result["negative_controls"] = controls
        result["canonical_self_test"] = self_test
        result["all_negative_controls_fail_closed"] = all(
            item["failed_closed"] and item["expected_error_observed"]
            for item in controls
        )
        result["valid"] = (
            result["valid"]
            and result["all_negative_controls_fail_closed"]
            and self_test["valid"]
        )
        result["status"] = "PASS" if result["valid"] else "FAIL"
    except Exception as error:
        result = {
            "valid": False,
            "errors": [str(error)],
            "negative_controls": [],
            "all_negative_controls_fail_closed": False,
            "status": "FAIL",
        }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
