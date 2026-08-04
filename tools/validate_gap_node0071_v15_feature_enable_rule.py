from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT_NAME = "r5_n71_gap_v15_feature_enable_rule"
RULE_ID = "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def validate_payload(
    runner: str, manifest: dict[str, Any]
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    feature = manifest.get("diagnostic_feature_runtime_enable_contract", {})
    allowlist = {
        item.get("target_path"): item
        for item in manifest.get("return_allowlist", [])
        if isinstance(item, dict)
    }
    sim_block = runner.split("sim_args=(", 1)[-1].split("\n)", 1)[0]
    if sim_block.count("+RETURN_OBS_ACCUM_STATE") != 1:
        errors.append("real sim_args feature enable differs")
    if sim_block.count("+RETURN_OBS_ACCUM_LIMIT=512") != 1:
        errors.append("real sim_args feature limit differs")
    if "grep -Fq 'accum_state=1' \"$observer_log\"" not in runner:
        errors.append("time0 feature marker guard differs")
    if "buffer_to_ga_accum_state_enabled=true" not in runner:
        errors.append("feature-specific enable receipt differs")
    if "buffer_to_ga_accum_limit=512" not in runner:
        errors.append("feature-specific limit receipt differs")
    if (
        feature.get("rule_id") != RULE_ID
        or feature.get("feature_name")
        != "buffer_to_ga_accumulator_state"
        or feature.get("runtime_enable_plusarg")
        != "+RETURN_OBS_ACCUM_STATE"
        or feature.get("runtime_limit_plusarg")
        != "+RETURN_OBS_ACCUM_LIMIT=512"
        or feature.get("effective_limit") != 512
    ):
        errors.append("manifest feature identity/argv contract differs")
    marker = feature.get("time0_marker", {})
    if (
        marker.get("return_target") != "runs/return_observer.log"
        or marker.get("required_tokens")
        != ["accum_state=1", "accum_limit=512"]
    ):
        errors.append("manifest time0 marker contract differs")
    binding = feature.get("feature_specific_binding_receipt", {})
    if (
        binding.get("return_target")
        != "evidence/observer_binding.txt"
        or binding.get("success_exact_lines")
        != [
            "buffer_to_ga_accum_state_enabled=true",
            "buffer_to_ga_accum_limit=512",
        ]
    ):
        errors.append("manifest feature return receipt differs")
    if feature.get("expected_record_schema") != [
        "BUFFER_TO_GA_COUNTS",
        "BUFFER_TO_GA_STATE",
    ]:
        errors.append("manifest feature record schema differs")
    required_targets = {
        "evidence/actual_simulator_argv.txt",
        "evidence/observer_binding.txt",
        "runs/return_observer.log",
    }
    if set(feature.get("return_allowlist_targets", [])) != required_targets:
        errors.append("manifest feature allowlist declaration differs")
    for target in required_targets:
        if target not in allowlist or allowlist[target].get("required") is not True:
            errors.append(f"feature return target absent/optional: {target}")
    if RULE_ID not in manifest.get(
        "final_zip_rule_self_audit_contract", {}
    ).get("applicable_rule_ids", []):
        errors.append("formal rule ID absent from applicable rules")
    return not errors, errors


def read_zip(
    target: Path, root_name: str = ROOT_NAME
) -> tuple[str, dict[str, Any]]:
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValidationError("ZIP CRC differs")
        runner_payload = archive.read(f"{root_name}/PREPARE_AND_RUN.sh")
        manifest_payload = archive.read(
            f"{root_name}/TEST_PACKAGE_MANIFEST.json"
        )
    manifest = json.loads(manifest_payload.decode("utf-8"))
    receipt = manifest["files"]["PREPARE_AND_RUN.sh"]
    if (
        receipt["sha256"] != sha256_bytes(runner_payload)
        or receipt["size_bytes"] != len(runner_payload)
    ):
        raise ValidationError("runner manifest receipt differs")
    return runner_payload.decode("utf-8"), manifest


def validate(
    target: Path, root_name: str = ROOT_NAME
) -> dict[str, Any]:
    runner, manifest = read_zip(target, root_name)
    valid, errors = validate_payload(runner, manifest)
    if not valid:
        raise ValidationError("; ".join(errors))
    controls: dict[str, Any] = {}

    def run_control(
        name: str, mutated_runner: str, mutated_manifest: dict[str, Any]
    ) -> None:
        control_valid, control_errors = validate_payload(
            mutated_runner, mutated_manifest
        )
        controls[name] = {
            "failed_closed": not control_valid,
            "errors": control_errors,
        }
        if control_valid:
            raise ValidationError(f"negative control did not fail: {name}")

    run_control(
        "enable_removed",
        runner.replace("  +RETURN_OBS_ACCUM_STATE\n", "", 1),
        json.loads(json.dumps(manifest)),
    )
    run_control(
        "limit_tampered",
        runner.replace("+RETURN_OBS_ACCUM_LIMIT=512", "+RETURN_OBS_ACCUM_LIMIT=511"),
        json.loads(json.dumps(manifest)),
    )
    marker_missing = json.loads(json.dumps(manifest))
    marker_missing["diagnostic_feature_runtime_enable_contract"].pop(
        "time0_marker"
    )
    run_control("time0_marker_contract_removed", runner, marker_missing)
    target_missing = json.loads(json.dumps(manifest))
    target_missing["return_allowlist"] = [
        item
        for item in target_missing["return_allowlist"]
        if item.get("target_path") != "evidence/observer_binding.txt"
    ]
    run_control("feature_return_target_removed", runner, target_missing)
    return {
        "schema": "gap-node0071-feature-enable-rule-validation-v15",
        "status": "PASS",
        "target_zip": str(target),
        "target_zip_sha256": sha256_bytes(target.read_bytes()),
        "rule_id": RULE_ID,
        "feature_name": "buffer_to_ga_accumulator_state",
        "three_way_binding": {
            "actual_argv": True,
            "time0_marker": True,
            "feature_specific_return_receipt": True,
            "feature_records": True,
        },
        "negative_controls": controls,
        "all_negative_controls_fail_closed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_zip", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.root_name)
    except Exception as error:
        print(f"v15 feature-enable rule validation failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
