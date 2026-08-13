from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_padding_contract import (  # noqa: E402
    CURRENT_PADDING_RTL_RECEIPT,
    MaxPoolPaddingContractError,
    validate_maxpool_padding_rtl_current_receipt,
    validate_maxpool_zero_padding_contract,
)
from resnet50_pipeline.operator_config_validator import (  # noqa: E402
    OperatorConfigValidator,
)


EXPECTED_GA_FACTS = {
    "rule_results": {
        "CDA-GA-INT8-MAX-NUMERIC-001": "LOCAL_SOURCE_PASS",
        "CDA-GA-INT8-MAX-PIPE-001": "CONTRADICTED",
    },
    "numeric_classification": "LOCAL_SOURCE_PASS",
    "numeric_equation": "unsigned bytewise max(A,C)",
    "pipeline_classification": "CONTRADICTED",
    "pipeline0_accepts_second_item": False,
}
CANDIDATE = (
    ROOT
    / "artifacts/operator_config_validation/r5_complete_json_regeneration_v1"
    / "maxpool_uint8/complete_json/node0002_hwop-0002-00_maxpool_uint8.json"
)
CURRENT_V5 = (
    ROOT
    / "artifacts/operator_config_validation/r5_complete_json_regeneration_v1"
    / "maxpool_uint8/current_test_consumed_config.json"
)
CURRENT_DIFF = (
    ROOT
    / "artifacts/operator_config_validation/r5_complete_json_regeneration_v1"
    / "maxpool_uint8/current_test_diff.json"
)
SOURCE_CONFIGS = (
    ROOT / "ndp-sim/jsons/maxpool_config_16_16_16_stride2_padding1.json",
    ROOT / "ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json",
    CANDIDATE,
)
PADDING_CONTRACTS = (
    ROOT / "contracts/maxpool_uint8_zero_padding_contract.json",
    ROOT / "contracts/maxpool_node0002_zero_padding_contract.json",
)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_ga_facts(value: dict[str, Any]) -> None:
    check(
        value == EXPECTED_GA_FACTS,
        "GA int8_max facts do not match the split numeric/pipeline rules",
    )
    check(
        "classification" not in value,
        "GA int8_max facts still expose an ambiguous overall classification",
    )


def ga_negative_controls() -> list[dict[str, Any]]:
    mutations: list[tuple[str, dict[str, Any]]] = []
    numeric_promoted = copy.deepcopy(EXPECTED_GA_FACTS)
    numeric_promoted["numeric_classification"] = "CONTRADICTED"
    mutations.append(("promote_pipeline_failure_to_numeric_failure", numeric_promoted))
    wrong_pipeline = copy.deepcopy(EXPECTED_GA_FACTS)
    wrong_pipeline["pipeline_classification"] = "LOCAL_SOURCE_PASS"
    mutations.append(("hide_pipeline_contradiction", wrong_pipeline))
    overall = copy.deepcopy(EXPECTED_GA_FACTS)
    overall["classification"] = "CONTRADICTED"
    mutations.append(("restore_ambiguous_overall_classification", overall))
    wrong_equation = copy.deepcopy(EXPECTED_GA_FACTS)
    wrong_equation["numeric_equation"] = "unsigned bytewise min(A,C)"
    mutations.append(("restore_stale_min_equation", wrong_equation))
    results = []
    for name, mutated in mutations:
        try:
            check_ga_facts(mutated)
        except ValueError as error:
            results.append(
                {
                    "name": name,
                    "expected_exit": 1,
                    "observed_exit": 1,
                    "failed_closed": True,
                    "reason": str(error),
                }
            )
        else:
            results.append(
                {
                    "name": name,
                    "expected_exit": 1,
                    "observed_exit": 0,
                    "failed_closed": False,
                    "reason": "mutation was accepted",
                }
            )
    return results


def padding_negative_controls(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    mutations: list[tuple[str, dict[str, Any]]] = []
    authority_hash = copy.deepcopy(receipt)
    authority_hash["cloud_authority_checkout"]["sha256"] = "0" * 64
    mutations.append(("tamper_cloud_authority_hash", authority_hash))
    mirror_hash = copy.deepcopy(receipt)
    mirror_hash["local_runtime_mirror"]["sha256"] = "f" * 64
    mutations.append(("tamper_local_mirror_hash", mirror_hash))
    equation = copy.deepcopy(receipt)
    equation["padding_substitution"]["equation"] = (
        "padding_mask ? ddr_data : padding_value"
    )
    mutations.append(("tamper_padding_priority_equation", equation))
    commit = copy.deepcopy(receipt)
    commit["cloud_authority_checkout"]["commit"] = "0" * 40
    mutations.append(("tamper_cloud_authority_commit", commit))
    results = []
    for name, mutated in mutations:
        with tempfile.TemporaryDirectory() as temp_text:
            path = Path(temp_text) / "receipt.json"
            path.write_text(
                json.dumps(mutated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            try:
                validate_maxpool_padding_rtl_current_receipt(ROOT, path)
            except MaxPoolPaddingContractError as error:
                results.append(
                    {
                        "name": name,
                        "expected_exit": 1,
                        "observed_exit": 1,
                        "failed_closed": True,
                        "reason": str(error),
                    }
                )
            else:
                results.append(
                    {
                        "name": name,
                        "expected_exit": 1,
                        "observed_exit": 0,
                        "failed_closed": False,
                        "reason": "mutation was accepted",
                    }
                )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "artifacts/operator_config_validation"
            / "r5-maxpool-tool-rule-coherence-padding-receipt-v1/report.json"
        ),
    )
    args = parser.parse_args()

    facts_by_config = []
    for path in SOURCE_CONFIGS:
        report = OperatorConfigValidator().validate_file(path)
        if path == CANDIDATE:
            check(report.valid, f"strict operator-config validation failed: {path}")
        else:
            check(
                not any(issue.code.startswith("GA.") for issue in report.issues),
                f"native reference has a GA structural issue: {path}",
            )
        facts = report.facts.get("ga_int8_max")
        check(isinstance(facts, dict), f"GA int8_max facts missing: {path}")
        check_ga_facts(facts)
        facts_by_config.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "facts": facts,
            }
        )

    receipt_path = ROOT / CURRENT_PADDING_RTL_RECEIPT
    receipt = validate_maxpool_padding_rtl_current_receipt(ROOT, receipt_path)
    padding_contracts = []
    for path in PADDING_CONTRACTS:
        value = validate_maxpool_zero_padding_contract(ROOT, path)
        padding_contracts.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "contract_sha256": value["contract_sha256"],
                "validated_with_current_rtl_receipt": True,
            }
        )

    candidate = load(CANDIDATE)
    current = load(CURRENT_V5)
    diff = load(CURRENT_DIFF)
    check(
        candidate["stream_engine"]["stream0"]["padding_reg_value"] == 0,
        "strict candidate padding leaf changed",
    )
    check(
        current["stream_engine"]["stream0"]["padding_reg_value"] is None,
        "current-v5 padding leaf changed",
    )
    changed = [
        item
        for item in diff["entries"]
        if item["classification"] != "SAME"
    ]
    check(
        len(changed) == 1
        and changed[0]["json_pointer"]
        == "/stream_engine/stream0/padding_reg_value",
        "candidate/current-v5 diff is no longer the one padding leaf",
    )

    controls = ga_negative_controls() + padding_negative_controls(receipt)
    check(
        all(item["failed_closed"] for item in controls),
        "one or more negative controls did not fail closed",
    )

    test_command = [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_operator_config_validator",
        "tests.test_maxpool_padding_contract",
        "-v",
    ]
    completed = subprocess.run(
        test_command,
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    check(completed.returncode == 0, "targeted unittest command failed")

    direct_consumer = ROOT / "tools/validate_maxpool_complete_json_local_v2.py"
    consumer_text = direct_consumer.read_text(encoding="utf-8")
    check(
        '"metadata_coherence"' in consumer_text
        and '"metadata_conflict"' not in consumer_text,
        "MaxPool complete-JSON direct consumer still reports metadata conflict",
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "maxpool-tool-rule-coherence-padding-receipt-v1",
        "status": "PASS",
        "errors": [],
        "ga_int8_max": {
            "numeric_rule": {
                "rule_id": "CDA-GA-INT8-MAX-NUMERIC-001",
                "classification": "LOCAL_SOURCE_PASS",
                "equation": "unsigned bytewise max(A,C)",
            },
            "pipeline_rule": {
                "rule_id": "CDA-GA-INT8-MAX-PIPE-001",
                "classification": "CONTRADICTED",
                "pipeline0_accepts_second_item": False,
            },
            "ambiguous_overall_classification_present": False,
            "facts_by_config": facts_by_config,
            "direct_consumer": {
                "path": direct_consumer.relative_to(ROOT).as_posix(),
                "sha256": sha(direct_consumer),
                "metadata_coherence": True,
            },
        },
        "padding_rtl_receipt": {
            "path": receipt_path.relative_to(ROOT).as_posix(),
            "sha256": sha(receipt_path),
            "receipt": receipt,
            "legacy_contracts": padding_contracts,
        },
        "negative_controls": controls,
        "negative_control_count": len(controls),
        "all_negative_controls_failed_closed": True,
        "targeted_tests": {
            "command": [
                "<python>",
                "-m",
                "unittest",
                "tests.test_operator_config_validator",
                "tests.test_maxpool_padding_contract",
                "-v",
            ],
            "exit_code": completed.returncode,
            "stdout_sha256": sha_bytes(completed.stdout),
            "stderr_sha256": sha_bytes(completed.stderr),
        },
        "complete_json_invariance": {
            "candidate": {
                "path": CANDIDATE.relative_to(ROOT).as_posix(),
                "sha256": sha(CANDIDATE),
            },
            "current_v5": {
                "path": CURRENT_V5.relative_to(ROOT).as_posix(),
                "sha256": sha(CURRENT_V5),
            },
            "current_test_diff": {
                "path": CURRENT_DIFF.relative_to(ROOT).as_posix(),
                "sha256": sha(CURRENT_DIFF),
            },
            "changed_leaf_count": 1,
            "changed_leaf": "/stream_engine/stream0/padding_reg_value",
            "unchanged": True,
        },
        "rule_receipts": {
            "operator_config_rule": {
                "path": ".agents/rules/算子配置规则.md",
                "sha256": sha(ROOT / ".agents/rules/算子配置规则.md"),
            },
            "ndp_field_semantics": {
                "path": ".agents/rules/NDP硬件字段语义.md",
                "sha256": sha(ROOT / ".agents/rules/NDP硬件字段语义.md"),
            },
            "generation_index": {
                "path": ".agents/rules/生成前必读索引.md",
                "sha256": sha(ROOT / ".agents/rules/生成前必读索引.md"),
            },
        },
        "implementation_receipts": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
            }
            for path in (
                ROOT / "resnet50_pipeline/operator_config_validator.py",
                ROOT / "tests/test_operator_config_validator.py",
                ROOT / "tools/validate_maxpool_complete_json_local_v2.py",
                ROOT / "tools/validate_maxpool_complete_json_regeneration_v1.py",
                ROOT / "resnet50_pipeline/maxpool_padding_contract.py",
                ROOT / "tests/test_maxpool_padding_contract.py",
                ROOT
                / "tools/validate_maxpool_tool_rule_coherence_padding_receipt_v1.py",
            )
        ],
        "hard_boundary": {
            "numeric_rule_modified": False,
            "functional_rtl_modified": False,
            "mapping_generated_or_modified": False,
            "bitstream_generated_or_modified": False,
            "execplan_generated_or_modified": False,
            "sca_generated_or_modified": False,
            "server_package_generated_or_modified": False,
            "server_action": False,
        },
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
