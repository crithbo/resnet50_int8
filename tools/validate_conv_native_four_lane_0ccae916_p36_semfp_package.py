#!/usr/bin/env python3
"""Run the p35c family audit and tighten its two p36 semantic checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p35c_armknown_package as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p36_semfp"
SOURCE = "r5_n4_0cc_p35c_armknown"
SOURCE_SHA = "b755592dbd01f05a63f0471ed76ede7673ab987b57a2cf579a8566a3d26f59fc"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
RULE_IDS = [
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
]


def main() -> int:
    cli = argparse.ArgumentParser(add_help=False)
    cli.add_argument("--zip", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args, _ = cli.parse_known_args()
    prior.PACKAGE = PACKAGE
    prior.SOURCE = SOURCE
    prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
    prior.SOURCE_SHA = SOURCE_SHA
    prior.EPOCH = EPOCH
    prior.main()
    report = json.loads(args.output.read_text(encoding="utf-8"))
    import zipfile
    with zipfile.ZipFile(args.zip) as archive:
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
        observer = archive.read(f"{PACKAGE}/tb_probe/source_bound_causal_observer.svh").decode()
        plan = json.loads(archive.read(f"{PACKAGE}/diagnostics/source_bound_probe_plan.json"))
    epoch = manifest.get("rule_change_epoch", {})
    report["checks"]["new_rule_epoch_ack"] = (
        epoch.get("epoch_id") == EPOCH
        and epoch.get("package_id") == PACKAGE
        and epoch.get("first_fresh_after_change") is True
        and epoch.get("notification_acknowledged") is True
        and epoch.get("rule_ids") == RULE_IDS
    )
    report["checks"]["undriven_leaf_excluded"] = (
        "add_array_req_addr" not in observer
        and "add_array_life_cnt" not in observer
        and "wire [44:0] payload_now" in observer
    )
    report["checks"]["exact_instance_payload_semantics"] = (
        plan.get("schema") == "server-source-bound-probe-plan-v2"
        and all(row.get("instance_scope", {}).get("mode") == "EXACT_CANONICAL_INSTANCE" for row in plan.get("boundaries", []))
        and all(row.get("payload_contract", {}).get("required_binary_known") is True for row in plan.get("boundaries", []))
    )
    report["schema"] = "conv-native-four-lane-p36-semfp-family-audit-v1"
    report["errors"] = [name for name, passed in report["checks"].items() if not passed]
    report["valid"] = report["pass"] = not report["errors"]
    report["claim_boundary"] = "Static/package-local exact-instance binary-known declared-width target audit only; no production natural terminal, formal D or E3-E5 claim."
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": report["valid"], "errors": report["errors"], "output": str(args.output)}))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
