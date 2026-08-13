#!/usr/bin/env python3
"""Final family audit wrapper for native-four-lane p21 epoch ownership."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import validate_conv_native_four_lane_0ccae916_p20_obsbindfix_package as previous


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p21_epochowner"
SOURCE_ID = "r5_n4_0cc_p20_obsbindfix"
SOURCE_SHA256 = "68e2fc8f98fa1c6c95fa8eb56a7d5a46e9ac132719cf252be5748b3da2dca208"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
BEGIN = "// v66 EPOCH_OWNER_ACTUAL_CONSUMER_BEGIN"
END = "// v66 EPOCH_OWNER_ACTUAL_CONSUMER_END"
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+)\b")
LOCAL_RE = re.compile(r"\b(?:bit|integer|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+(return_obs_[A-Za-z0-9_]+)")
P20_COMPILE = previous.focused_combined_scope_compile


def combined_compile(observer: str, iverilog: Path, temp_root: Path) -> dict[str, Any]:
    p20 = P20_COMPILE(observer, iverilog, temp_root)
    if observer.count(BEGIN) != 1 or observer.count(END) != 1:
        raise previous.base.ValidationError("p21 epoch-owner span differs")
    block = observer[observer.index(BEGIN):observer.index(END) + len(END)]
    expressions = sorted(set(previous.base.XMR_RE.findall(block)), key=len, reverse=True)
    replacements = {value: f"p21_epoch_xmr_{index}" for index, value in enumerate(expressions)}
    focused = block
    for expression, local in replacements.items():
        focused = focused.replace(expression, local)
    focused = re.sub(r"(p21_epoch_xmr_[0-9]+)\s*\[\s*p21_epoch_xmr_[0-9]+", r"\1", focused)
    focused = re.sub(r"(p21_epoch_xmr_[0-9]+)\]", r"\1", focused)
    declared = set(LOCAL_RE.findall(focused))
    used = set(NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_epoch_owner"})
    declarations = "\n".join([f"  logic [255:0] {name};" for name in external] + [f"  logic [255:0] {name};" for name in replacements.values()] + ["  bit n4d_active;", "  integer n4d_fd;"])
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + '\n  initial begin #1; return_obs_write_epoch_owner("FOCUS"); end\nendmodule\n'
    positive = previous.base.compile_case(iverilog, temp_root, "p21_epoch_positive", source)
    missing = previous.base.compile_case(iverilog, temp_root, "p21_epoch_missing_decl", source.replace("  bit return_obs_eo_enabled;", "", 1))
    first = next(iter(replacements.values()))
    typo = previous.base.compile_case(iverilog, temp_root, "p21_epoch_consumer_typo", source.replace(first, first + "_wrong", 1))
    epoch_valid = positive["exit_code"] == 0 and missing["exit_code"] != 0 and typo["exit_code"] != 0
    p20_expressions = p20.pop("expressions")
    return {
        **p20,
        "valid": p20["valid"] and epoch_valid,
        "expressions": sorted(set(p20_expressions) | set(expressions)),
        "epoch_owner": {
            "valid": epoch_valid, "positive": positive,
            "negative_missing_declaration": missing,
            "negative_actual_consumer_typo": typo,
            "expression_count": len(expressions),
            "block_sha256": previous.base.digest(block.encode()),
        },
    }


def main() -> int:
    previous.PACKAGE_ID = PACKAGE_ID
    previous.SOURCE_ID = SOURCE_ID
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.SOURCE_SHA256 = SOURCE_SHA256
    previous.focused_combined_scope_compile = combined_compile
    rc = previous.main()
    output = None
    import sys
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            output = Path(sys.argv[index + 1]).resolve()
    if output is None:
        raise previous.base.ValidationError("--output is required")
    report = json.loads(output.read_text(encoding="utf-8"))
    manifest_feature = report["observer"]["focused_compile"]["epoch_owner"]["valid"]
    report["schema"] = "conv-native-four-lane-p21-epochowner-family-audit-v1"
    report["source_scope"] = {"source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256, "changed_surface": "epoch-owner observer plus signal-safe partial receipt runner", "config_or_rtl_changed": False}
    report["release_gate_matrix"]["package_local_hdl"]["pass"] = manifest_feature and report["release_gate_matrix"]["package_local_hdl"]["pass"]
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
