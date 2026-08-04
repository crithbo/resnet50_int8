from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_bp_pre_factor_diag_v18 as factor


ROOT_NAME = "r5_n71_gap_v19_bp_pre_factor_stage_scope"
TEST_ID = "r5-gap-node0071-v19-bp-pre-factor-stage-scope"
SERVER_RULE_SHA256 = (
    "1e0b40589dddee3bf2b4d081936d37d9a25f78ea2ceb98bc08f2dcf813438589"
)
CANONICAL = "package_tools/gap_node0071_canonical_decision.py"
MANIFEST_BINDING = '--manifest "$package_manifest"'
EXPECTED_STAGES = [
    "sum_s1",
    "sum_s2",
    "sum_s3",
    "sum_s4",
    "sum_s5",
    "sum_s6",
    "tail_mul",
    "tail_round",
]


def configure() -> None:
    factor.ROOT_NAME = ROOT_NAME
    factor.TEST_ID = TEST_ID


def _manifest(files: dict[str, bytes]) -> dict[str, Any]:
    return json.loads(files["TEST_PACKAGE_MANIFEST.json"])


def _refresh(
    files: dict[str, bytes], relative: str
) -> dict[str, bytes]:
    return factor._refresh_record(files, relative)


def validate_payload(
    files: dict[str, bytes], root_name: str
) -> dict[str, Any]:
    base = factor.validate_payload(files, root_name)
    errors = list(base["errors"])
    manifest = _manifest(files)
    canonical_contract = manifest.get("canonical_decision_contract", {})
    canonical = files[CANONICAL].decode("utf-8")
    runner = files[factor.RUNNER].decode("utf-8")
    if canonical_contract.get("expected_ordered_stage_list") != EXPECTED_STAGES:
        errors.append("expected ordered stage list differs")
    if canonical_contract.get("stage_identity_source") != (
        "TEST_PACKAGE_MANIFEST.json canonical_decision_contract"
    ):
        errors.append("stage identity source differs")
    if canonical_contract.get("final_stage_scope_required") is not True:
        errors.append("final stage scope requirement absent")
    if canonical_contract.get(
        "natural_terminal_requires_final_expected_stage"
    ) is not True:
        errors.append("natural terminal final-stage gate absent")
    if canonical_contract.get("final_stage_scope_error") != (
        "PACKAGE_DIAGNOSTIC_DECISION_FINAL_STAGE_SCOPE_ERROR"
    ):
        errors.append("final stage scope error classification differs")
    required_fields = set(canonical_contract.get("required_fields", []))
    if not {
        "expected_ordered_stage_list",
        "final_stage_scope",
    }.issubset(required_fields):
        errors.append("canonical stage fields absent")
    negatives = set(canonical_contract.get("negative_controls", []))
    if not {
        "early_stage_completion",
        "later_stage_started_not_finished",
        "unmatched_stage_finish",
    }.issubset(negatives):
        errors.append("canonical stage negative controls absent")
    if f"    {MANIFEST_BINDING} \\" not in runner:
        errors.append("runner canonical manifest binding absent")
    for token in (
        "FINAL_STAGE_SCOPE_ERROR",
        "expected_ordered_stage_list",
        "paired_stage_records",
        "active_unfinished_stage",
        "final_stage_completed",
        "stage start before prior finish",
        "COMP_FINISH without paired EXEC_START",
        "natural terminal lacks final-stage completion",
    ):
        if token not in canonical:
            errors.append(f"canonical stage mechanism absent: {token}")
    if any(stage in canonical for stage in EXPECTED_STAGES):
        errors.append("canonical tool hardcodes package expected stage identity")
    record = manifest.get("files", {}).get(CANONICAL, {})
    if record.get("sha256") != factor.sha256_bytes(files[CANONICAL]):
        errors.append("manifest SHA differs: canonical tool")
    if record.get("size_bytes") != len(files[CANONICAL]):
        errors.append("manifest size differs: canonical tool")
    server_receipts = [
        item
        for item in manifest.get(
            "final_zip_rule_self_audit_contract", {}
        ).get("read_receipt", [])
        if item.get("path") == ".agents/rules/服务器测试包生成规则.md"
    ]
    if len(server_receipts) != 1 or server_receipts[0].get(
        "sha256"
    ) != SERVER_RULE_SHA256:
        errors.append("current server rule receipt differs")
    drift = manifest.get("post_generation_rule_drift", {})
    if drift.get("content_neutral") is not False:
        errors.append("material rule drift not declared")
    if drift.get("current_server_rule_sha256") != SERVER_RULE_SHA256:
        errors.append("material rule drift current SHA differs")
    base.update(
        {
            "valid": not errors,
            "errors": errors,
            "canonical_sha256": factor.sha256_bytes(files[CANONICAL]),
            "expected_ordered_stage_list": EXPECTED_STAGES,
        }
    )
    return base


def negative_controls(
    files: dict[str, bytes], root_name: str
) -> list[dict[str, Any]]:
    controls = factor.negative_controls(files, root_name)

    def run(
        name: str,
        mutated: dict[str, bytes],
        expected_fragment: str,
    ) -> None:
        result = validate_payload(mutated, root_name)
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
    manifest = _manifest(mutated)
    manifest["canonical_decision_contract"].pop(
        "expected_ordered_stage_list"
    )
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    run(
        "missing_expected_ordered_stage_list",
        mutated,
        "expected ordered stage list differs",
    )

    mutated = dict(files)
    manifest = _manifest(mutated)
    manifest["canonical_decision_contract"][
        "expected_ordered_stage_list"
    ][0:2] = ["sum_s2", "sum_s1"]
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    run(
        "reordered_expected_stage_list",
        mutated,
        "expected ordered stage list differs",
    )

    mutated = dict(files)
    mutated[factor.RUNNER] = files[factor.RUNNER].replace(
        f"    {MANIFEST_BINDING} \\\n".encode("utf-8"), b"", 1
    )
    mutated = _refresh(mutated, factor.RUNNER)
    run(
        "missing_runner_manifest_stage_binding",
        mutated,
        "runner canonical manifest binding absent",
    )

    mutated = dict(files)
    mutated[CANONICAL] = files[CANONICAL].replace(
        b"natural terminal lacks final-stage completion",
        b"natural terminal stage gate removed",
        1,
    )
    mutated = _refresh(mutated, CANONICAL)
    run(
        "missing_final_stage_parser_gate",
        mutated,
        (
            "canonical stage mechanism absent: "
            "natural terminal lacks final-stage completion"
        ),
    )

    mutated = dict(files)
    manifest = _manifest(mutated)
    manifest["final_zip_rule_self_audit_contract"]["read_receipt"] = [
        item
        for item in manifest[
            "final_zip_rule_self_audit_contract"
        ]["read_receipt"]
        if item.get("path") != ".agents/rules/服务器测试包生成规则.md"
    ]
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    run(
        "missing_current_server_rule_receipt",
        mutated,
        "current server rule receipt differs",
    )
    return controls


def canonical_self_test(files: dict[str, bytes]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix="gap-v19-canonical-self-test-"
    ) as temp:
        tool = Path(temp) / "canonical.py"
        tool.write_bytes(files[CANONICAL])
        completed = subprocess.run(
            [sys.executable, str(tool), "self-test"],
            check=False,
            capture_output=True,
            text=True,
        )
    result = json.loads(completed.stdout) if completed.stdout else {}
    controls = result.get("negative_controls", {})
    required = {
        "ordered_final_stage_positive",
        "early_stage_completion",
        "later_stage_started_not_finished",
        "unmatched_stage_finish",
    }
    return {
        "exit_code": completed.returncode,
        "status": result.get("status"),
        "required_controls_present": required.issubset(controls),
        "stderr": completed.stderr,
        "valid": (
            completed.returncode == 0
            and result.get("status") == "PASS"
            and required.issubset(controls)
        ),
        "result": result,
    }


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        files = factor.read_zip(args.zip_path, args.root_name)
        result = validate_payload(files, args.root_name)
        controls = negative_controls(files, args.root_name)
        self_test = canonical_self_test(files)
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
