from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_prep_count_cause_v24 as base


ROOT_NAME = "r5_n71_gap_v25_hdl_scope_rulefix"
TEST_ID = "r5-gap-node0071-v25-hdl-scope-rulefix"
SERVER_RULE_SHA256 = (
    "c230db601433cd3f8f4344e7e43b3be4d069d8dd8a28057f07b56910dba555cd"
)
HDL_RULE_ID = (
    "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
)


def configure() -> None:
    base.ROOT_NAME = ROOT_NAME
    base.TEST_ID = TEST_ID
    base.CURRENT_SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    base.configure()


def main() -> int:
    configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--root-name", default=ROOT_NAME)
    parser.add_argument("--runner-report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        files = base.base.base.stage.factor.read_zip(
            args.zip_path, args.root_name
        )
        runner_report = (
            json.loads(args.runner_report.read_text(encoding="utf-8"))
            if args.runner_report
            else None
        )
        result = base.validate_payload(files, args.root_name, runner_report)
        manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
        contract = manifest.get("package_local_hdl_syntax_scope_contract", {})
        hdl_checks = {
            "rule_id": contract.get("rule_id") == HDL_RULE_ID,
            "exact_member":
                contract.get("members", [{}])[0].get("relative_path")
                == base.OBSERVER,
            "include_order":
                contract.get("include_order")
                == [
                    "package-local +incdir tb_probe",
                    (
                        "tb_NDP_Top_new_phy.sv protected include "
                        "native_return_observer.svh"
                    ),
                ],
            "compile_profile":
                "+define+NATIVE_RETURN_OBSERVER_ENABLE"
                in contract.get("compile_macro_profile", ""),
            "state_leaves":
                len(contract.get("features", [{}])[0].get("state_leaves", []))
                == 23,
            "negative_contract":
                set(contract.get("required_negative_controls", []))
                == {
                    "delete_declaration",
                    "misspell_consumer_use",
                    "delete_qualified_update",
                },
        }
        refresh = manifest.get("post_generation_rule_drift_refresh", {})
        legacy_drift_superseded = (
            refresh.get("classification") == "FRESH_SUCCESSOR_REQUIRED"
            and refresh.get("current_server_rule_sha256")
            == SERVER_RULE_SHA256
        )
        errors = [
            error
            for error in result["errors"]
            if not (
                error == "material rule drift current SHA differs"
                and legacy_drift_superseded
            )
        ]
        if not all(hdl_checks.values()):
            errors.append("package-local HDL manifest contract differs")
        controls = base.negative_controls(
            files, args.root_name, runner_report
        )
        result.update(
            {
                "schema":
                    "gap-node0071-hdl-scope-rulefix-v25-validation-v1",
                "errors": errors,
                "package_local_hdl_manifest_checks": hdl_checks,
                "legacy_rule_drift_record_superseded_by_v25_refresh":
                    legacy_drift_superseded,
                "negative_controls": controls,
                "all_negative_controls_fail_closed": all(
                    item["failed_closed"]
                    and item["expected_error_observed"]
                    for item in controls
                ),
            }
        )
        result["valid"] = (
            not errors and result["all_negative_controls_fail_closed"]
        )
        result["status"] = "PASS" if result["valid"] else "FAIL"
    except Exception as error:
        result = {
            "schema": "gap-node0071-hdl-scope-rulefix-v25-validation-v1",
            "valid": False,
            "status": "FAIL",
            "errors": [str(error)],
            "negative_controls": [],
            "all_negative_controls_fail_closed": False,
        }
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
