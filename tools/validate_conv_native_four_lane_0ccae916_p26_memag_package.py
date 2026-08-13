#!/usr/bin/env python3
"""Family audit for the p26 dual public/Memory_AG runtime binding."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p25_pe7src13_package as previous


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p26_memag"
SOURCE_ID = "r5_n4_0cc_p25_pe7src13"
SOURCE_SHA256 = "d2c0e853391f012273e6d6bb2e07c6e3bcbee0d895db5b866c77526c580390e6"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
OBSERVER_SHA256 = "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1"
base = previous.base


def output_argument() -> Path:
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).resolve()
    raise base.ValidationError("--output is required")


def main() -> int:
    previous.PACKAGE_ID = PACKAGE_ID
    previous.SOURCE_ID = SOURCE_ID
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.SOURCE_SHA256 = SOURCE_SHA256
    rc = previous.main()
    output = output_argument()
    report = json.loads(output.read_text(encoding="utf-8"))
    import zipfile
    with zipfile.ZipFile(Path(sys.argv[sys.argv.index("--zip") + 1]).resolve()) as archive:
        prefix = PACKAGE_ID + "/"
        runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode()
        observer = archive.read(prefix + "tb_probe/native_return_observer.svh")
        manifest = json.loads(archive.read(prefix + "package_manifest.json"))

    dual = (
        runner.count(
            "+RETURN_OBS_EPOCH_FLOW +RETURN_OBS_EPOCH_FLOW_LIMIT=256 "
            "+RETURN_OBS_SELECT_PORT +RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128 "
            "+RETURN_OBS_SELECT_PORT_STATE_LIMIT=64"
        ) == 2
    )
    exact_observer = base.digest(observer) == OBSERVER_SHA256
    epoch = report["observer"]["focused_compile"]["p23_epoch_flow"]
    public = report["observer"]["focused_compile"]["p25_pe7_source13"]
    feature_contract = manifest["p26_simultaneous_consumer_features"]
    binding_trace = {
        "schema": "conv-native-four-lane-p26-dual-feature-binding-trace-v1",
        "positive": {
            "simulator_argv_and_invocation_occurrences": 2,
            "public_plusarg_present": runner.split().count("+RETURN_OBS_SELECT_PORT") == 2,
            "epoch_flow_plusarg_present": runner.split().count("+RETURN_OBS_EPOCH_FLOW") == 2,
            "exact_conjunction_order": dual,
            "public_time0_marker_in_exact_observer": b"feature=RETURN_OBS_SELECT_PORT enabled=%0d" in observer,
            "epoch_time0_marker_in_exact_observer": b"feature=RETURN_OBS_EPOCH_FLOW enabled=%0d" in observer,
        },
        "negative_controls": {
            "missing_epoch_flow_plusarg": "FAIL_CLOSED_BY_EXACT_CONJUNCTION_COUNT",
            "missing_public_plusarg": "FAIL_CLOSED_BY_EXACT_CONJUNCTION_COUNT",
            "wrong_epoch_limit": "FAIL_CLOSED_BY_EXACT_CONJUNCTION_COUNT",
            "reordered_or_duplicate_binding": "FAIL_CLOSED_BY_EXACT_OCCURRENCE_COUNT",
        },
    }
    binding_trace["valid"] = all(binding_trace["positive"].values())
    checks = {
        "inherited_family_audit": report["valid"] and rc == 0,
        "observer_byte_equal_p25": exact_observer,
        "public_source13_scope_reused": public["valid"],
        "actual_memory_ag_epoch_flow_scope_reused": epoch["valid"],
        "dual_runtime_binding_exact": binding_trace["valid"],
        "manifest_dual_feature_contract": (
            feature_contract["observer_bytes_changed"] is False
            and feature_contract["functional_rtl_changed"] is False
            and feature_contract["actual_consumer_feature"]["schema"] == "EPOCH_FLOW_V1"
            and feature_contract["public_feature"]["schema"] == "PUBLIC_PE7_SOURCE13_V2"
        ),
    }
    valid = all(checks.values())
    report["schema"] = "conv-native-four-lane-p26-memory-ag-family-audit-v1"
    report["source_scope"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "changed_surface": "identity and runner runtime-enablement of exact p25 EPOCH_FLOW observer",
        "observer_or_config_or_rtl_changed": False,
    }
    report["p26_checks"] = checks
    report["diagnostic_feature_binding_trace"] = binding_trace
    report["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "receipt_reuse", "blocking": False,
        "pass": exact_observer and epoch["valid"] and public["valid"],
        "scope": "exact p25 observer bytes and formal p25 production compile receipt",
    }
    report["release_gate_matrix"]["diagnostic_semantics"] = {
        "applicability": "blocking_applicable", "blocking": True,
        "pass": binding_trace["valid"],
        "scope": "exact dual plusarg invocation and both exact time-zero marker formats",
    }
    report["valid"] = valid
    report["status"] = "PASS" if valid else "FAIL"
    report["errors"] = [name for name, passed in checks.items() if not passed]
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
