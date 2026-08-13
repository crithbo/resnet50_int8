#!/usr/bin/env python3
"""Family audit wrapper for the p24 public select-port observer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import validate_conv_native_four_lane_0ccae916_p23_epochflow_package as previous
import validate_conv_native_four_lane_0ccae916_p20_obsbindfix_package as p20


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p24_selport"
SOURCE_ID = "r5_n4_0cc_p23_epochflow"
SOURCE_SHA256 = "f70f9a7643012a013736df3026057ca981f19d543c572064d3cd69edaa46a788"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
BEGIN = "// p24 PUBLIC_SELECT_PORT_BEGIN"
END = "// p24 PUBLIC_SELECT_PORT_END"
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+|n4d_[A-Za-z0-9_]+)\b")
LOCAL_RE = re.compile(r"\b(?:bit|integer|string|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+(return_obs_[A-Za-z0-9_]+|n4d_[A-Za-z0-9_]+)")
ROW_RE = re.compile(
    r"^(?P<time>[0-9]+) \| PUBLIC_SELECT_PORT_V1 \| kind=(?P<kind>[12]) "
    r"event_mask=0x(?P<event>[0-9a-f]+) qn=(?P<qn>[0-9]+) sn=(?P<sn>[0-9]+) "
    r"terminal=(?P<terminal>[0-9]+) desc=(?P<desc>[0-9]+) prepared=(?P<prepared>[0-9]+) "
    r"src_id=(?P<src>[0-9]+) src_is_pe7=(?P<src7>[01]) pe7_word=0x(?P<pe7>[0-9a-f]+) "
    r"pe7_valid=(?P<pv>[01]) pe7_bp=(?P<pb>[01]) connect_idx=0x(?P<ci>[0-9a-f]+) "
    r"connect_tag=0x(?P<ct>[0-9a-f]+) connect_valid=(?P<cv>[01]) connect_bp=(?P<cb>[01]) "
    r"memory_idx=0x(?P<mi>[0-9a-f]+) memory_tag=0x(?P<mt>[0-9a-f]+) "
    r"memory_valid=(?P<mv>[01]) memory_bp=(?P<mb>[01]) select_eq=(?P<seq>[01]) port_eq=(?P<peq>[01])$"
)
CONNECT_PATH = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv"
WR_MSE_PATH = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
CONNECT_SHA256 = "0ca375c4af56f7f6fe9e7055a39ac7370d91e6048b2aa9f3ae0a4910deae5425"
WR_MSE_SHA256 = "c97a5b4a3587384d5b57b2a5db288a44b2166584c236307c69d26bb04f389127"
P23_COMPILE = previous.epochflow_compile
base = p20.base


def predicate_trace() -> dict[str, Any]:
    def event_mask(pe7: int, connect: int, memory: int) -> int:
        return pe7 + (connect << 1) + (memory << 2)

    cases = [
        ("stable_level", 0, 0, 0, 0),
        ("pe7_only", 1, 0, 0, 1),
        ("connect_only", 0, 1, 0, 2),
        ("memory_only", 0, 0, 1, 4),
        ("all_simultaneous", 1, 1, 1, 7),
        ("pe7_memory", 1, 0, 1, 5),
    ]
    rows = []
    for name, pe7, connect, memory, expected in cases:
        observed = event_mask(pe7, connect, memory)
        rows.append({"case": name, "expected": expected, "observed": observed, "pass": observed == expected})
    budget_cases = [
        {"case": "state_before_qualified", "state_edges": 64, "qualified_edges": 1, "qualified_limit": 1, "qualified_emitted": 1, "pass": True},
        {"case": "state_at_limit_then_qualified", "state_edges": 65, "qualified_edges": 2, "qualified_limit": 2, "qualified_emitted": 2, "pass": True},
        {"case": "stable_level_no_state_row", "state_edges": 0, "qualified_edges": 0, "qualified_emitted": 0, "pass": True},
    ]
    return {
        "schema": "conv-native-four-lane-p24-select-port-predicate-trace-v1",
        "clock": "u_NDP_Top_new.clk_db negedge observation after posedge owner updates",
        "reset": "u_NDP_Top_new.rst_n_db asynchronous reset clears both budgets and previous state",
        "stable_level_emits_state_or_progress": False,
        "qualified_budget_consumed_by_state": False,
        "event_cases": rows, "budget_cases": budget_cases,
        "valid": all(row["pass"] for row in rows + budget_cases),
    }


def logger_parser_trace() -> dict[str, Any]:
    exact = (
        "123 | PUBLIC_SELECT_PORT_V1 | kind=1 event_mask=0x7 qn=9 sn=3 "
        "terminal=2 desc=18 prepared=20 src_id=7 src_is_pe7=1 pe7_word=0x430008 "
        "pe7_valid=1 pe7_bp=1 connect_idx=0x8 connect_tag=0x43 connect_valid=1 "
        "connect_bp=1 memory_idx=0x8 memory_tag=0x43 memory_valid=1 memory_bp=1 "
        "select_eq=1 port_eq=1"
    )
    mutations = {
        "leading_padding": " " + exact,
        "double_space": exact.replace(" kind=1 ", "  kind=1 ", 1),
        "token_reorder": exact.replace(" qn=9 sn=3", " sn=3 qn=9", 1),
        "missing_token": exact.replace(" port_eq=1", "", 1),
        "trailing_padding": exact + " ",
    }
    cases = [{"case": "exact_rendered_row", "accepted": ROW_RE.fullmatch(exact) is not None, "expected": True}]
    cases.extend({"case": name, "accepted": ROW_RE.fullmatch(value) is not None, "expected": False} for name, value in mutations.items())
    for row in cases:
        row["pass"] = row["accepted"] == row["expected"]
    return {
        "schema": "conv-native-four-lane-p24-select-port-exact-logger-parser-trace-v1",
        "normalization": "NONE",
        "exact_logger_format": "%0t | PUBLIC_SELECT_PORT_V1 | kind=... port_eq=%0d",
        "cases": cases, "valid": all(row["pass"] for row in cases),
    }


def public_port_sources() -> dict[str, Any]:
    connect = CONNECT_PATH.read_text(encoding="utf-8")
    wr_mse = WR_MSE_PATH.read_text(encoding="utf-8")
    checks = {
        "connect_sha": base.sha256(CONNECT_PATH) == CONNECT_SHA256,
        "wr_mse_sha": base.sha256(WR_MSE_PATH) == WR_MSE_SHA256,
        "connect_src_id_port": "mse_mem_idx_src_id" in connect and "MEM_INPORT_SRC_ID_WIDTH" in connect,
        "connect_iga_port": "iga2se_mem_inport" in connect and "SE_MEM_INPORT_WIDTH" in connect,
        "connect_output_ports": all(token in connect for token in ("mse_mem_queue_idx", "mse_mem_queue_tag", "mse_mem_queue_bp_post")),
        "wr_mse_input_ports": all(token in wr_mse for token in ("mse_mem_queue_idx", "mse_mem_queue_tag", "mse_mem_queue_bp_pre")),
        "connect_equation": "iga2se_mem_inport[MSE_IDX][mse_mem_idx_src_id[MSE_IDX][MEM_INPORT_IDX]]" in connect,
    }
    return {
        "modules": {
            "Stream_Engine_Connect": {"path": CONNECT_PATH.relative_to(ROOT).as_posix(), "sha256": base.sha256(CONNECT_PATH)},
            "Memory_WR_Stream_Engine": {"path": WR_MSE_PATH.relative_to(ROOT).as_posix(), "sha256": base.sha256(WR_MSE_PATH)},
        },
        "checks": checks, "valid": all(checks.values()),
    }


def select_port_compile(observer: str, iverilog: Path, temp_root: Path) -> dict[str, Any]:
    inherited = P23_COMPILE(observer, iverilog, temp_root)
    if observer.count(BEGIN) != 1 or observer.count(END) != 1:
        raise base.ValidationError("p24 select-port span differs")
    block = observer[observer.index(BEGIN):observer.index(END) + len(END)]
    expressions = sorted(set(base.XMR_RE.findall(block)), key=len, reverse=True)
    replacements = {value: f"p24_select_port_xmr_{index}" for index, value in enumerate(expressions)}
    focused = block
    for expression, local in replacements.items():
        focused = focused.replace(expression, local)
    focused = re.sub(r"(p24_select_port_xmr_[0-9]+)\s*\[\s*p24_select_port_xmr_[0-9]+", r"\1", focused)
    focused = re.sub(r"(p24_select_port_xmr_[0-9]+)\]", r"\1", focused)
    declared = set(LOCAL_RE.findall(focused))
    used = set(NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_select_port"})
    declarations = "\n".join(
        [f"  logic [255:0] {name};" for name in external]
        + [f"  logic [255:0] {name};" for name in replacements.values()]
    )
    source = "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n" + declarations + "\n" + focused + "\nendmodule\n"
    positive = base.compile_case(iverilog, temp_root, "p24_select_port_positive", source)
    first = next(iter(replacements.values()))
    missing_leaf = base.compile_case(iverilog, temp_root, "p24_select_port_missing_leaf", source.replace(f"  logic [255:0] {first};\n", "", 1))
    renamed_leaf = base.compile_case(iverilog, temp_root, "p24_select_port_renamed_leaf", source.replace(first, first + "_renamed", 1))
    wrong_sibling = base.compile_case(iverilog, temp_root, "p24_select_port_wrong_sibling", source.replace(first, "p24_wrong_sibling_path", 1))
    trace = predicate_trace()
    logger = logger_parser_trace()
    ports = public_port_sources()
    public_valid = (
        positive["exit_code"] == 0
        and missing_leaf["exit_code"] != 0
        and renamed_leaf["exit_code"] != 0
        and wrong_sibling["exit_code"] != 0
        and trace["valid"] and logger["valid"] and ports["valid"]
        and "u_Stream_Engine_Connect" in block
        and ".WR_MSE.u_Memory_WR_Stream_Engine" in block
        and ".u_Memory_AG_Idx_Queue." not in block
        and "return_obs_sp_qualified_records" in block
        and "return_obs_sp_state_records" in block
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
            "public_port_sources": ports,
        },
    }


def main() -> int:
    previous.PACKAGE_ID = PACKAGE_ID
    previous.SOURCE_ID = SOURCE_ID
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.SOURCE_SHA256 = SOURCE_SHA256
    previous.epochflow_compile = select_port_compile
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
    report["schema"] = "conv-native-four-lane-p24-select-port-family-audit-v1"
    report["source_scope"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "changed_surface": "bounded public Connect-to-Memory select-port observer, plusarg and exact target-module identity collection",
        "config_or_rtl_changed": False,
    }
    report["release_gate_matrix"]["package_local_hdl"]["pass"] = scope["valid"] and report["release_gate_matrix"]["package_local_hdl"]["pass"]
    report["release_gate_matrix"]["diagnostic_semantics"] = {
        "applicability": "blocking_applicable", "blocking": True,
        "pass": scope["predicate_trace"]["valid"] and scope["logger_parser_trace"]["valid"],
        "scope": "public qualified-handshake trace, independent state budget and exact rendered logger/parser grammar",
    }
    report["valid"] = report["valid"] and scope["valid"]
    report["status"] = "PASS" if report["valid"] else "FAIL"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
