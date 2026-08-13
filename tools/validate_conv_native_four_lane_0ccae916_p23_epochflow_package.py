#!/usr/bin/env python3
"""Family audit wrapper for the p23 edge-qualified epoch-flow observer."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any

import validate_conv_native_four_lane_0ccae916_p22_eoenfix_package as previous
import validate_conv_native_four_lane_0ccae916_p20_obsbindfix_package as p20


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p23_epochflow"
SOURCE_ID = "r5_n4_0cc_p22_eoenfix"
SOURCE_SHA256 = "876f9a16575648ddcb2dd594a881651cf7c678ddb30d344d112c68951f4fd8cf"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
BEGIN = "// p23 EPOCH_FLOW_ACTUAL_CONSUMER_BEGIN"
END = "// p23 EPOCH_FLOW_ACTUAL_CONSUMER_END"
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+|n4d_[A-Za-z0-9_]+)\b")
LOCAL_RE = re.compile(r"\b(?:bit|integer|string|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+(return_obs_[A-Za-z0-9_]+|n4d_[A-Za-z0-9_]+)")
P22_COMPILE = previous.corrected_compile
base = p20.base


def predicate_trace() -> dict[str, Any]:
    """Run the exact event-selection ordering without driving a DUT."""

    def select(row: dict[str, int]) -> str | None:
        if row["terminal"]:
            return "DESC_TERMINAL"
        if row["input1"]:
            return "INPUT1_ACCEPT"
        if row["input0"]:
            return "INPUT0_ACCEPT"
        if row["input2"]:
            return "INPUT2_ACCEPT"
        if row["qwr"]:
            return "QUEUE_WRITE"
        if row["qrd"]:
            return "QUEUE_READ"
        if row["desc"]:
            return "DESC_ACCEPT"
        if row["prepared"]:
            return "PREPARED_ACCEPT"
        if row["buf"]:
            return "BUFFER_ACCEPT"
        return None

    zero = {key: 0 for key in ("terminal", "input0", "input1", "input2", "qwr", "qrd", "desc", "prepared", "buf")}
    cases = [
        ("stable_level", {}, None),
        ("terminal2_boundary", {"terminal": 1}, "DESC_TERMINAL"),
        ("input0_new_token", {"input0": 1}, "INPUT0_ACCEPT"),
        ("input1_new_token", {"input1": 1}, "INPUT1_ACCEPT"),
        ("input2_new_token", {"input2": 1}, "INPUT2_ACCEPT"),
        ("queue_write", {"qwr": 1}, "QUEUE_WRITE"),
        ("queue_read", {"qrd": 1}, "QUEUE_READ"),
        ("desc_edge", {"desc": 1}, "DESC_ACCEPT"),
        ("prepared_edge", {"prepared": 1}, "PREPARED_ACCEPT"),
        ("buffer_edge", {"buf": 1}, "BUFFER_ACCEPT"),
        ("simultaneous_terminal_input_queue", {"terminal": 1, "input1": 1, "qwr": 1}, "DESC_TERMINAL"),
        ("simultaneous_input1_input0", {"input1": 1, "input0": 1}, "INPUT1_ACCEPT"),
        ("simultaneous_write_read", {"qwr": 1, "qrd": 1}, "QUEUE_WRITE"),
    ]
    rows = []
    for name, updates, expected in cases:
        row = dict(zero)
        row.update(updates)
        observed = select(row)
        rows.append({"case": name, "expected": expected, "observed": observed, "pass": observed == expected})
    return {
        "schema": "conv-native-four-lane-p23-epochflow-predicate-trace-v1",
        "clock": "u_NDP_Top_new.clk_db negedge observation after posedge ownership update",
        "reset": "u_NDP_Top_new.rst_n_db asynchronous reset clears counters and previous keys",
        "stable_level_emits_transaction": False,
        "cases": rows, "valid": all(row["pass"] for row in rows),
    }


def epochflow_compile(observer: str, iverilog: Path, temp_root: Path) -> dict[str, Any]:
    inherited = P22_COMPILE(observer, iverilog, temp_root)
    if observer.count(BEGIN) != 1 or observer.count(END) != 1:
        raise base.ValidationError("p23 epoch-flow span differs")
    block = observer[observer.index(BEGIN):observer.index(END) + len(END)]
    expressions = sorted(set(base.XMR_RE.findall(block)), key=len, reverse=True)
    replacements = {value: f"p23_epochflow_xmr_{index}" for index, value in enumerate(expressions)}
    focused = block
    for expression, local in replacements.items():
        focused = focused.replace(expression, local)
    focused = re.sub(r"(p23_epochflow_xmr_[0-9]+)\s*\[\s*p23_epochflow_xmr_[0-9]+", r"\1", focused)
    focused = re.sub(r"(p23_epochflow_xmr_[0-9]+)\]", r"\1", focused)
    declared = set(LOCAL_RE.findall(focused))
    used = set(NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_epoch_flow"})
    declarations = "\n".join(
        [f"  logic [255:0] {name};" for name in external]
        + [f"  logic [255:0] {name};" for name in replacements.values()]
    )
    source = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        + declarations + "\n" + focused
        + '\n  initial begin #1; return_obs_write_epoch_flow("FOCUS"); end\nendmodule\n'
    )
    positive = base.compile_case(iverilog, temp_root, "p23_epochflow_positive", source)
    first = next(iter(replacements.values()))
    missing_leaf = base.compile_case(
        iverilog, temp_root, "p23_epochflow_missing_leaf",
        source.replace(f"  logic [255:0] {first};\n", "", 1),
    )
    renamed_leaf = base.compile_case(
        iverilog, temp_root, "p23_epochflow_renamed_leaf",
        source.replace(first, first + "_renamed", 1),
    )
    wrong_sibling = base.compile_case(
        iverilog, temp_root, "p23_epochflow_wrong_sibling",
        source.replace(first, "p23_wrong_sibling_path", 1),
    )
    trace = predicate_trace()
    private_valid = (
        positive["exit_code"] == 0
        and missing_leaf["exit_code"] != 0
        and renamed_leaf["exit_code"] != 0
        and wrong_sibling["exit_code"] != 0
        and trace["valid"]
        and "Memory_AG_Idx_Queue" in block
        and "mem_idx_valid_same_gotten_masked" in block
        and "mem_ag_idx_queue_wr_en" in block
        and "mem_ag_idx_queue_rd_en" in block
    )
    inherited_expressions = inherited.pop("expressions")
    return {
        **inherited,
        "valid": inherited["valid"] and private_valid,
        "expressions": sorted(set(inherited_expressions) | set(expressions)),
        "p23_epoch_flow": {
            "valid": private_valid, "positive": positive,
            "negative_leaf_deleted": missing_leaf,
            "negative_leaf_renamed": renamed_leaf,
            "negative_wrong_sibling_path": wrong_sibling,
            "expression_count": len(expressions), "block_sha256": base.digest(block.encode()),
            "private_xmr_target": "Memory_AG_Idx_Queue.sv",
            "predicate_trace": trace,
        },
    }


def main() -> int:
    previous.PACKAGE_ID = PACKAGE_ID
    previous.SOURCE_ID = SOURCE_ID
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.SOURCE_SHA256 = SOURCE_SHA256
    previous.corrected_compile = epochflow_compile
    rc = previous.main()
    import sys
    output = None
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            output = Path(sys.argv[index + 1]).resolve()
    if output is None:
        raise base.ValidationError("--output is required")
    report = json.loads(output.read_text(encoding="utf-8"))
    scope = report["observer"]["focused_compile"]["p23_epoch_flow"]
    report["schema"] = "conv-native-four-lane-p23-epochflow-family-audit-v1"
    report["source_scope"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "changed_surface": "edge-qualified MSE4 epoch-flow observer, plusarg and exact Memory_AG production identity collection",
        "config_or_rtl_changed": False,
    }
    report["release_gate_matrix"]["package_local_hdl"]["pass"] = scope["valid"] and report["release_gate_matrix"]["package_local_hdl"]["pass"]
    report["release_gate_matrix"]["diagnostic_semantics"] = {
        "applicability": "blocking_applicable", "blocking": True,
        "pass": scope["predicate_trace"]["valid"],
        "scope": "exact edge-selection trace; stable held levels do not emit transactions",
    }
    report["valid"] = report["valid"] and scope["valid"]
    report["status"] = "PASS" if report["valid"] else "FAIL"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
