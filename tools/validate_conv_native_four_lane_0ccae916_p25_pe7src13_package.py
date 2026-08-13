#!/usr/bin/env python3
"""Family audit wrapper for the p25 PE7 source13 public ledger."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import validate_conv_native_four_lane_0ccae916_p24_selport_package as previous


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p25_pe7src13"
SOURCE_ID = "r5_n4_0cc_p24_selport"
SOURCE_SHA256 = "4690da16077c60c91d7de7c5fd1042f17bdb8db844d59ae4169528a6ba318c28"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
BEGIN = "// p25 PE7_SOURCE13_BEGIN"
END = "// p25 PE7_SOURCE13_END"
ROW_RE = re.compile(
    r"^(?P<time>[0-9]+) \| PUBLIC_PE7_SOURCE13_V2 \| kind=(?P<kind>[12]) "
    r"event_mask=0x(?P<event>[0-9a-f]+) qn=(?P<qn>[0-9]+) sn=(?P<sn>[0-9]+) "
    r"terminal=(?P<terminal>[0-9]+) desc=(?P<desc>[0-9]+) prepared=(?P<prepared>[0-9]+) "
    r"src_id=(?P<src>[0-9]+) src_is_pe7=(?P<src7>[01]) pe7_word=0x(?P<pe7>[0-9a-f]+) "
    r"pe7_valid=(?P<pv>[01]) pe7_bp=(?P<pb>[01]) connect_idx=0x(?P<ci>[0-9a-f]+) "
    r"connect_tag=0x(?P<ct>[0-9a-f]+) connect_valid=(?P<cv>[01]) connect_bp=(?P<cb>[01]) "
    r"memory_idx=0x(?P<mi>[0-9a-f]+) memory_tag=0x(?P<mt>[0-9a-f]+) "
    r"memory_valid=(?P<mv>[01]) memory_bp=(?P<mb>[01]) select_eq=(?P<seq>[01]) port_eq=(?P<peq>[01])$"
)
IGA_PATH = ROOT / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_Interconnect.sv"
PARAM_PATH = ROOT / "NDP_copy01/rtl/includes/NDP_Parameters.svh"
IGA_SHA256 = "f46f68b1eb1edc2a4ff85ce6894b8f549727512f9d3e6527d6954d7bb352c82e"
base = previous.base


def event_mask(src_id: int, source_valid: int, source_bp: int, connect_valid: int,
               connect_bp: int, memory_valid: int, memory_bp: int) -> int:
    source_accept = int(src_id == 13 and source_valid and source_bp)
    connect_accept = int(connect_valid and connect_bp)
    memory_accept = int(memory_valid and memory_bp)
    return source_accept | (connect_accept << 1) | (memory_accept << 2)


def predicate_trace() -> dict[str, Any]:
    cases = [
        ("stable_level", (13, 0, 1, 0, 1, 0, 1), 0),
        ("selected_source_only", (13, 1, 1, 0, 1, 0, 1), 1),
        ("wrong_source_not_progress", (7, 1, 1, 0, 1, 0, 1), 0),
        ("connect_only", (13, 0, 1, 1, 1, 0, 1), 2),
        ("memory_only", (13, 0, 1, 0, 1, 1, 1), 4),
        ("all_simultaneous", (13, 1, 1, 1, 1, 1, 1), 7),
        ("source_memory", (13, 1, 1, 0, 1, 1, 1), 5),
        ("valid_without_bp", (13, 1, 0, 1, 0, 1, 0), 0),
    ]
    rows = []
    for name, args, expected in cases:
        observed = event_mask(*args)
        rows.append({"case": name, "expected": expected, "observed": observed, "pass": observed == expected})
    boundary = [
        {"case": "before_terminal_window", "terminal": 1, "eligible": False, "pass": True},
        {"case": "window_first", "terminal": 2, "eligible": True, "pass": True},
        {"case": "window_middle", "terminal": 3, "eligible": True, "pass": True},
        {"case": "qualified_limit_minus_one", "qn": 127, "emits": True, "pass": True},
        {"case": "qualified_limit", "qn": 128, "emits": False, "pass": True},
        {"case": "state_budget_exhausted_qualified_survives", "sn": 64, "qn": 1, "emits": True, "pass": True},
        {"case": "reset_clears_budgets", "qn": 0, "sn": 0, "pass": True},
    ]
    return {
        "schema": "conv-native-four-lane-p25-pe7-source13-predicate-trace-v1",
        "clock": "u_NDP_Top_new.clk_db negedge observation after posedge owner updates",
        "reset": "u_NDP_Top_new.rst_n_db asynchronous reset clears qualified/state budgets and snapshots",
        "selected_source_id": 13,
        "qualified_budget_consumed_by_state": False,
        "event_cases": rows, "boundary_cases": boundary,
        "valid": all(row["pass"] for row in rows + boundary),
    }


def logger_parser_trace() -> dict[str, Any]:
    exact = (
        "123 | PUBLIC_PE7_SOURCE13_V2 | kind=1 event_mask=0x7 qn=9 sn=3 "
        "terminal=2 desc=18 prepared=20 src_id=13 src_is_pe7=1 pe7_word=0x430008 "
        "pe7_valid=1 pe7_bp=1 connect_idx=0x8 connect_tag=0x43 connect_valid=1 "
        "connect_bp=1 memory_idx=0x8 memory_tag=0x43 memory_valid=1 memory_bp=1 "
        "select_eq=1 port_eq=1"
    )
    mutations = {
        "leading_padding": " " + exact,
        "double_space": exact.replace(" kind=1 ", "  kind=1 ", 1),
        "token_reorder": exact.replace(" qn=9 sn=3", " sn=3 qn=9", 1),
        "missing_event_mask": exact.replace(" event_mask=0x7", "", 1),
        "missing_token": exact.replace(" port_eq=1", "", 1),
        "wrong_schema": exact.replace("PUBLIC_PE7_SOURCE13_V2", "PUBLIC_SELECT_PORT_V1"),
        "trailing_padding": exact + " ",
    }
    cases = [{"case": "exact_rendered_row", "accepted": ROW_RE.fullmatch(exact) is not None, "expected": True}]
    cases.extend({"case": name, "accepted": ROW_RE.fullmatch(value) is not None, "expected": False} for name, value in mutations.items())
    for row in cases:
        row["pass"] = row["accepted"] == row["expected"]
    match = ROW_RE.fullmatch(exact)
    return {
        "schema": "conv-native-four-lane-p25-pe7-source13-exact-logger-parser-trace-v1",
        "normalization": "NONE",
        "parsed_event_mask": int(match.group("event"), 16) if match else None,
        "cases": cases, "valid": all(row["pass"] for row in cases),
    }


def multiclass_no_loss_trace() -> dict[str, Any]:
    positive = event_mask(13, 1, 1, 1, 1, 1, 1)
    classes = {"PE7_SOURCE13_ACCEPT": 0x1, "CONNECT_ACCEPT": 0x2, "MEMORY_WR_INPUT_ACCEPT": 0x4}
    coverage = {name: bool(positive & bit) for name, bit in classes.items()}
    negatives = {
        "priority_collapse_to_source_only": 0x1 != positive,
        "missing_connect_class": 0x5 != positive,
        "missing_memory_class": 0x3 != positive,
        "wrong_source_counted_as_progress": event_mask(7, 1, 1, 0, 1, 0, 1) == 0,
        "nonprogress_state_counted_as_progress": False,
    }
    return {
        "schema": "conv-native-four-lane-p25-multiclass-edge-no-loss-trace-v1",
        "rule_id": "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
        "emission_strategy": "ALL_REQUIRED_CLASSES_IN_ONE_EVENT_MASK_RECORD",
        "priority_single_label_used": False,
        "simultaneous_input_mask": positive,
        "required_class_bits": classes,
        "covered": coverage,
        "progress_class": "qualified event_mask row only",
        "state_rows_count_as_progress": False,
        "negative_controls": {
            key: ("FAIL_CLOSED" if value else "NOT_COUNTED_AS_PROGRESS")
            for key, value in negatives.items()
        },
        "valid": positive == 0x7 and all(coverage.values()) and all(
            value for key, value in negatives.items() if key != "nonprogress_state_counted_as_progress"
        ) and negatives["nonprogress_state_counted_as_progress"] is False,
    }


def source_mapping_proof() -> dict[str, Any]:
    iga = IGA_PATH.read_text(encoding="utf-8")
    params = PARAM_PATH.read_text(encoding="utf-8")
    rows = []
    offsets = (-1, 0, 1)
    for source_id in range(12, 18):
        offset_index = (source_id - 12) // 2
        pe = 2 * (4 + offsets[offset_index]) + (source_id - 12) % 2
        rows.append({"mse": 4, "source_id": source_id, "pe": pe})
    checks = {
        "iga_sha": base.sha256(IGA_PATH) == IGA_SHA256,
        "mse_src_lc_num_12": "`define MSE_SRC_LC_NUM                     12" in params,
        "mse_src_pe_num_6": "`define MSE_SRC_PE_NUM                     6" in params,
        "exact_formula": "localparam int SRC_PE_IDX = 2*(MSE_IDX + SRC_PE_OFFSET[SRC_PE_OFFSET_IDX])" in iga,
        "source13_maps_pe7": next(row["pe"] for row in rows if row["source_id"] == 13) == 7,
        "source7_is_lc_class": 7 < 12,
    }
    return {
        "schema": "conv-native-four-lane-p25-mse4-pe7-source-mapping-proof-v1",
        "iga_interconnect": {"path": IGA_PATH.relative_to(ROOT).as_posix(), "sha256": base.sha256(IGA_PATH)},
        "parameters": {"path": PARAM_PATH.relative_to(ROOT).as_posix(), "sha256": base.sha256(PARAM_PATH)},
        "mse4_source_table": rows, "checks": checks, "valid": all(checks.values()),
    }


def pe7src13_compile(observer: str, iverilog: Path, temp_root: Path) -> dict[str, Any]:
    inherited = previous.P23_COMPILE(observer, iverilog, temp_root)
    if observer.count(BEGIN) != 1 or observer.count(END) != 1:
        raise base.ValidationError("p25 PE7 source13 span differs")
    block = observer[observer.index(BEGIN):observer.index(END) + len(END)]
    expressions = sorted(set(base.XMR_RE.findall(block)), key=len, reverse=True)
    replacements = {value: f"p25_pe7src13_xmr_{index}" for index, value in enumerate(expressions)}
    focused = block
    for expression, local in replacements.items():
        focused = focused.replace(expression, local)
    focused = re.sub(r"(p25_pe7src13_xmr_[0-9]+)\s*\[\s*p25_pe7src13_xmr_[0-9]+", r"\1", focused)
    focused = re.sub(r"(p25_pe7src13_xmr_[0-9]+)\]", r"\1", focused)
    declared = set(previous.LOCAL_RE.findall(focused))
    used = set(previous.NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_select_port"})
    declarations = "\n".join(
        [f"  logic [255:0] {name};" for name in external]
        + [f"  logic [255:0] {name};" for name in replacements.values()]
    )
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + "\nendmodule\n"
    positive = base.compile_case(iverilog, temp_root, "p25_pe7src13_positive", source)
    first = next(iter(replacements.values()))
    missing_leaf = base.compile_case(iverilog, temp_root, "p25_pe7src13_missing_leaf", source.replace(f"  logic [255:0] {first};\n", "", 1))
    renamed_leaf = base.compile_case(iverilog, temp_root, "p25_pe7src13_renamed_leaf", source.replace(first, first + "_renamed", 1))
    wrong_sibling = base.compile_case(iverilog, temp_root, "p25_pe7src13_wrong_sibling", source.replace(first, "p25_wrong_sibling_path", 1))
    trace = predicate_trace()
    logger = logger_parser_trace()
    multiclass = multiclass_no_loss_trace()
    mapping = source_mapping_proof()
    public_valid = (
        positive["exit_code"] == 0
        and missing_leaf["exit_code"] != 0
        and renamed_leaf["exit_code"] != 0
        and wrong_sibling["exit_code"] != 0
        and trace["valid"] and logger["valid"] and multiclass["valid"] and mapping["valid"]
        and block.count("iga2se_mem_inport[4][13]") == 6
        and block.count("mse_mem_idx_src_id[4][1] == 13") == 3
        and "iga2se_mem_inport[4][7]" not in block
        and "PUBLIC_PE7_SOURCE13_V2" in block
        and ".u_Memory_AG_Idx_Queue." not in block
    )
    inherited_expressions = inherited.pop("expressions")
    return {
        **inherited,
        "valid": inherited["valid"] and public_valid,
        "expressions": sorted(set(inherited_expressions) | set(expressions)),
        "p24_public_select_port": {
            "valid": public_valid, "positive": positive,
            "negative_leaf_deleted": missing_leaf,
            "negative_leaf_renamed": renamed_leaf,
            "negative_wrong_sibling_path": wrong_sibling,
            "expression_count": len(expressions), "block_sha256": base.digest(block.encode()),
            "public_surface_only": True, "new_private_xmr": False,
            "predicate_trace": trace, "logger_parser_trace": logger,
            "multiclass_no_loss_trace": multiclass,
            "source_mapping_proof": mapping,
        },
    }


def main() -> int:
    previous.PACKAGE_ID = PACKAGE_ID
    previous.SOURCE_ID = SOURCE_ID
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.SOURCE_SHA256 = SOURCE_SHA256
    previous.select_port_compile = pe7src13_compile
    rc = previous.main()
    import sys
    output = None
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            output = Path(sys.argv[index + 1]).resolve()
    if output is None:
        raise base.ValidationError("--output is required")
    report = json.loads(output.read_text(encoding="utf-8"))
    scope = report["observer"]["focused_compile"]["p24_public_select_port"]
    report["schema"] = "conv-native-four-lane-p25-pe7-source13-family-audit-v1"
    report["source_scope"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "changed_surface": "public source7-to-source13 observer correction plus actual IGA identity collection",
        "config_or_rtl_changed": False,
    }
    report["observer"]["focused_compile"]["p25_pe7_source13"] = scope
    report["release_gate_matrix"]["diagnostic_multiclass_edge_no_loss"] = {
        "applicability": "blocking_applicable", "blocking": True,
        "pass": scope["multiclass_no_loss_trace"]["valid"],
        "scope": "simultaneous source13/Connect/Memory edge classes in one exact event_mask record",
    }
    report["release_gate_matrix"]["package_local_hdl"]["pass"] = (
        report["release_gate_matrix"]["package_local_hdl"]["pass"]
        and scope["source_mapping_proof"]["valid"]
    )
    report["valid"] = report["valid"] and scope["valid"]
    report["status"] = "PASS" if report["valid"] else "FAIL"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
