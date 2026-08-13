#!/usr/bin/env python3
"""Emit the final machine report for p37b return to p38 release closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p38_mse4join"
PACKAGE = "r5_n4_0cc_p38_mse4join"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
OUTPUT = BASE / "p37b_return_p38_release_report.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p37b-to-p38 release report")
    p37 = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_return_analysis/report.json"
    zip_path = STORAGE / "pending" / f"{PACKAGE}.zip"
    final = STORAGE / "pending_receipts/conv_native_four_lane" / PACKAGE / f"{PACKAGE}.final_zip_audit.json"
    reports = {
        "p37b_return": p37,
        "build": BASE / "build" / f"{PACKAGE}.build.json",
        "family": BASE / "p38_family_audit.json",
        "typed_v2": BASE / "build" / f"{PACKAGE}.source_bound_final_zip.json",
        "post_sim": BASE / "build" / f"{PACKAGE}.post_sim.json",
        "runner": BASE / "build" / f"{PACKAGE}.runner_harness.json",
        "shared_layout": BASE / "build" / f"{PACKAGE}.shared_layout.json",
        "build_spec": BASE / "server_package_build_spec_v2.json",
        "build_profile": BASE / "server_package_build_profile_v2.json",
        "final_zip": final,
        "storage_audit": BASE / "storage_audit.json",
        "storage_index": STORAGE / "PACKAGE_STORAGE_INDEX.json",
    }
    if not zip_path.is_file() or not all(path.is_file() for path in reports.values()):
        raise RuntimeError("final release evidence is incomplete")
    p37_value = json.loads(p37.read_text(encoding="utf-8"))
    final_value = json.loads(final.read_text(encoding="utf-8"))
    index = json.loads(reports["storage_index"].read_text(encoding="utf-8-sig"))
    disposition = {row["package_base"]: row["disposition"] for row in index["packages"]}
    checks = {
        "p37b_return_valid": p37_value.get("valid") is True,
        "p37b_formal_status": p37_value.get("status") == "P37B_PARTIAL_RETURN_VALID_DISTINCT_SA_BEATS_PROVEN_WRITE_DESCRIPTOR_BOUNDARY_SUCCESSOR_REQUIRED",
        "p38_final_gate_pass": final_value.get("valid") is True and final_value.get("status") == "PACKAGE_READY_NOT_RUN",
        "p38_zip_exact": sha(zip_path) == "328b7ec7b7034a1a2c202fad38d628199cfbbaa2213196d94daab39c25ff4d22",
        "p37b_tested": disposition.get("r5_n4_0cc_p37b_saepoch") == "tested",
        "p38_pending": disposition.get(PACKAGE) == "pending",
        "serialized_v84b_preserved": disposition.get("r5_n4_hw_v84b_ack_inline_realtime_diag") == "pending",
        "qadd_v56_preserved": disposition.get("r5_qadd_n7_tailround_lanephase_v56") == "pending",
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-p37b-return-p38-release-report-v1",
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_HELD",
        "valid": valid,
        "mainline_target": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "return_analysis": {
            "classification": p37_value["classification"],
            "return_identity": p37_value["return_identity"],
            "source_identity": p37_value["source_identity"],
            "execution": p37_value["execution"],
            "result_conjunction": p37_value["result_conjunction"],
            "last_proven_good": p37_value["failure_localization"]["LAST_PROVEN_GOOD"],
            "first_divergence": p37_value["failure_localization"]["FIRST_DIVERGENCE"],
            "hang_root_cause": p37_value["failure_localization"]["HANG_ROOT_CAUSE"],
            "blocker_delta": p37_value["blocker_delta"],
            "round_progress": p37_value["round_progress"],
        },
        "successor": {
            "package_id": PACKAGE,
            "package_release": final_value["package_release"],
            "candidate_release": False,
            "pickup": receipt(zip_path),
            "command": "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02",
            "expected_return": "/home/panqs/ndp/simresult/r5_n4_0cc_p38_mse4join_r<epoch-ns>_<pid>_return.zip",
            "scope": "exact MSE4 Memory_AG/descriptor/Buffer5-data/wdata-output/slice-finish accepted-event join through the final two-unit skew",
            "frozen": "87 payload/config/numeric/W3/workload/mapping/bitstream/execplan/SCA/golden/timeout/functional RTL",
        },
        "checks": checks,
        "audits": {name: receipt(path) for name, path in reports.items()},
        "source_bound_receipts": {
            name: receipt(ROOT / "outputs/conv_native_four_lane_0ccae916_p38_mse4join_source_bound" / name)
            for name in (
                "source_bound_probe_catalog.json", "source_bound_probe_plan.json",
                "exact_instance_identity.json", "mse4_join_contract.json",
                "source_bound_generation_report.json", "source_bound_observer_generation.json",
            )
        },
        "storage": {
            "preimage": {"bytes": 340780, "sha256": "61e364f4d19bf892f24e5824f673230399de34f176437000a17445e4bbc2f9ad"},
            "postimage": receipt(reports["storage_index"]),
            "pending_count": sum(row["disposition"] == "pending" for row in index["packages"]),
            "tested_count": sum(row["disposition"] == "tested" for row in index["packages"]),
            "superseded_count": sum(row["disposition"] == "superseded" for row in index["packages"]),
        },
        "claims": {
            "natural_terminal": False,
            "formal_320D": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "performance": False,
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "public_rule_modified": False,
            "confirmed": [
                "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
                "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
                "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
                "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
                "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
                "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            ],
        },
        "server_action": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "output": str(OUTPUT), "sha256": sha(OUTPUT)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
