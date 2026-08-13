#!/usr/bin/env python3
"""Final family audit wrapper for the p22 actual-consumer identifier fix."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import validate_conv_native_four_lane_0ccae916_p21_epoch_owner_package as previous


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p22_eoenfix"
SOURCE_ID = "r5_n4_0cc_p21_epochowner"
SOURCE_SHA256 = "cd78dd1aa2234bc12e4588b957fa900e71030486bd6eca4c315155451f631c8d"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
GOOD = "if (return_obs_eo_enabled && n4d_fd != 0) begin"
BAD = "if (return_obs_enabled && n4d_fd != 0) begin"
P21_COMPILE = previous.combined_compile


def corrected_compile(observer: str, iverilog: Path, temp_root: Path) -> dict[str, Any]:
    inherited = P21_COMPILE(observer, iverilog, temp_root)
    if observer.count(GOOD) != 2 or BAD in observer or "bit return_obs_eo_enabled;" not in observer:
        raise previous.previous.base.ValidationError("p22 corrected epoch-owner consumer surface differs")
    exact = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        "  bit return_obs_eo_enabled;\n  integer n4d_fd;\n"
        "  initial begin\n    if (return_obs_eo_enabled && n4d_fd != 0) begin\n"
        "      $display(\"EPOCH_OWNER\");\n    end\n  end\nendmodule\n"
    )
    positive = previous.previous.base.compile_case(iverilog, temp_root, "p22_actual_consumer_positive", exact)
    missing = previous.previous.base.compile_case(
        iverilog, temp_root, "p22_actual_consumer_missing_decl",
        exact.replace("  bit return_obs_eo_enabled;\n", "", 1),
    )
    mutation = previous.previous.base.compile_case(
        iverilog, temp_root, "p22_actual_consumer_p21_mutation",
        exact.replace(GOOD, BAD, 1),
    )
    actual_valid = positive["exit_code"] == 0 and missing["exit_code"] != 0 and mutation["exit_code"] != 0
    inherited["valid"] = inherited["valid"] and actual_valid
    inherited["p22_actual_consumer_scope"] = {
        "valid": actual_valid, "positive": positive,
        "negative_missing_exact_declaration": missing,
        "negative_mutation_back_to_p21_identifier": mutation,
        "corrected_consumer_occurrences": observer.count(GOOD),
        "legacy_undeclared_identifier_absent": BAD not in observer,
    }
    return inherited


def main() -> int:
    previous.PACKAGE_ID = PACKAGE_ID
    previous.SOURCE_ID = SOURCE_ID
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.SOURCE_SHA256 = SOURCE_SHA256
    previous.combined_compile = corrected_compile
    rc = previous.main()
    import sys
    output = None
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            output = Path(sys.argv[index + 1]).resolve()
    if output is None:
        raise previous.previous.base.ValidationError("--output is required")
    report = json.loads(output.read_text(encoding="utf-8"))
    actual = report["observer"]["focused_compile"]["p22_actual_consumer_scope"]["valid"]
    report["schema"] = "conv-native-four-lane-p22-eoenfix-family-audit-v1"
    report["source_scope"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "changed_surface": "one package-local epoch-owner enable identifier at the actual time-zero consumer",
        "config_or_rtl_changed": False, "predicate_changed": False,
    }
    report["release_gate_matrix"]["package_local_hdl"]["pass"] = actual and report["release_gate_matrix"]["package_local_hdl"]["pass"]
    report["valid"] = report["valid"] and actual
    report["status"] = "PASS" if report["valid"] else "FAIL"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
