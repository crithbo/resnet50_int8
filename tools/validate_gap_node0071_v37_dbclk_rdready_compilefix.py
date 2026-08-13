from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_v36_dbclk_rdready as base


ROOT_NAME = "r5_n71_gap_v37_dbclk_rdready_compilefix"
TEST_ID = "r5-gap-node0071-v37-dbclk-rdready-observer-compile-correction"
OBSERVER = "tb_probe/native_return_observer.svh"
BAD = "return_obs_rd_spatial_mon"
GOOD = "return_obs_rd_spatial_size_mon"
SOURCE_SHA256 = (
    "8835bcad4b54f6c0ec5ad225976d71631492477430e73e77f838df1d76cbf1dd"
)
TRIGGER_RETURN_SHA256 = (
    "2f8a425164bfb4dbe193e644b3a5c040a8b15b92feb62e5edc197902599852ff"
)


def configure() -> None:
    base.ROOT_NAME = ROOT_NAME
    base.TEST_ID = TEST_ID
    base.configure()


def validate_payload(
    files: dict[str, bytes],
    root_name: str,
    runner_report: dict[str, Any] | None,
) -> dict[str, Any]:
    configure()
    result = base.validate_payload(files, root_name, runner_report)
    errors = list(result["errors"])
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    observer = files[OBSERVER].decode("utf-8")
    contract = manifest.get("observer_compile_correction_contract", {})
    correction = contract.get("minimal_correction", {})
    checks = {
        "package_identity":
            manifest.get("package_name") == ROOT_NAME
            and manifest.get("install_name") == ROOT_NAME,
        "source_binding":
            manifest.get("supersedes_package_sha256") == SOURCE_SHA256
            and contract.get("source_package_sha256") == SOURCE_SHA256
            and contract.get("trigger_return_sha256")
            == TRIGGER_RETURN_SHA256,
        "exact_identifier_correction":
            BAD not in observer
            and observer.count(GOOD) == 6
            and correction.get("old_identifier") == BAD
            and correction.get("new_identifier") == GOOD
            and correction.get("old_hit_count_before") == 1
            and correction.get("old_hit_count_after") == 0,
        "actual_consumer_resolves":
            f"{GOOD}[return_obs_group_id]"
            "[return_obs_local_slice_id][dbrr_flow]" in observer,
        "declared_monitor":
            "[1:0][7:0] return_obs_rd_prep_count_mon," in observer
            and f"{GOOD};" in observer,
        "monitor_assignments":
            observer.count(f"assign {GOOD}[") == 2,
        "diagnostic_algorithm_frozen":
            contract.get("diagnostic_algorithm_changed") is False
            and contract.get("owner_clock_changed") is False
            and contract.get("runtime_feature_contract_changed") is False
            and contract.get("return_schema_changed") is False,
        "functional_boundaries_frozen":
            contract.get("config_changed") is False
            and contract.get("timeout_or_backpressure_changed") is False
            and contract.get("functional_rtl_modified") is False,
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(f"v37 observer compile correction differs: {name}")
    result.update(
        {
            "valid": not errors,
            "errors": errors,
            "observer_compile_correction_checks": checks,
            "observer_compile_correction_contract_valid":
                all(checks.values()),
        }
    )
    return result


def correction_negative_controls(
    files: dict[str, bytes],
    runner_report: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []

    def check(
        name: str,
        mutated: dict[str, bytes],
        expected_fragment: str,
    ) -> None:
        result = validate_payload(mutated, ROOT_NAME, runner_report)
        controls.append(
            {
                "name": name,
                "failed_closed": result["valid"] is False,
                "expected_error_observed": any(
                    expected_fragment in error for error in result["errors"]
                ),
                "errors": result["errors"],
            }
        )

    observer = files[OBSERVER]
    mutated = dict(files)
    mutated[OBSERVER] = observer.replace(
        GOOD.encode(), BAD.encode(), 1
    )
    check(
        "production_v36_undeclared_consumer_reintroduced",
        mutated,
        "exact_identifier_correction",
    )

    mutated = dict(files)
    mutated[OBSERVER] = observer.replace(
        f"                      {GOOD};".encode(),
        b"                      return_obs_rd_spatial_size_removed;",
        1,
    )
    check(
        "actual_monitor_declaration_removed",
        mutated,
        "declared_monitor",
    )

    consumer = (
        f"{GOOD}[return_obs_group_id]"
        "[return_obs_local_slice_id][dbrr_flow]"
    )
    mutated = dict(files)
    mutated[OBSERVER] = observer.replace(
        consumer.encode(),
        b"return_obs_rd_spatial_consumer_removed"
        b"[return_obs_group_id][return_obs_local_slice_id][dbrr_flow]",
        1,
    )
    check(
        "actual_required_consumer_removed",
        mutated,
        "actual_consumer_resolves",
    )

    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    manifest.pop("observer_compile_correction_contract", None)
    mutated = dict(files)
    mutated["TEST_PACKAGE_MANIFEST.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False).encode() + b"\n"
    )
    check(
        "correction_contract_removed",
        mutated,
        "source_binding",
    )
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--runner-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        configure()
        files = base.read_zip(args.zip_path.resolve(), ROOT_NAME)
        runner_report = (
            json.loads(args.runner_report.read_text(encoding="utf-8"))
            if args.runner_report
            else None
        )
        result = validate_payload(files, ROOT_NAME, runner_report)
        inherited = base.negative_controls(
            files, ROOT_NAME, runner_report
        )
        correction = correction_negative_controls(files, runner_report)
        controls = inherited + correction
        result["schema"] = (
            "gap-node0071-v37-observer-compilefix-validation-v1"
        )
        result["negative_controls"] = controls
        result["all_negative_controls_fail_closed"] = all(
            item["failed_closed"] and item["expected_error_observed"]
            for item in controls
        )
        result["valid"] = (
            result["valid"]
            and result["all_negative_controls_fail_closed"]
        )
        result["status"] = "PASS" if result["valid"] else "FAIL"
        exit_code = 0 if result["valid"] else 1
    except Exception as error:
        result = {
            "schema":
                "gap-node0071-v37-observer-compilefix-validation-v1",
            "status": "FAIL",
            "valid": False,
            "errors": [str(error)],
            "negative_controls": [],
            "all_negative_controls_fail_closed": False,
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
