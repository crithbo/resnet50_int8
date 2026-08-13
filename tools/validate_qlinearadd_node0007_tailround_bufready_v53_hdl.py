"""Focused package-local HDL/parser closure gate for QAdd v53."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_IDENTIFIERS = {
    "q53_enabled", "q53_marker_emitted", "q53_event_budget",
    "q53_pingpong_sel_mon", "q53_ready0_mon", "q53_ready1_mon",
    "q53_selected_ready_mon", "q53_mrm_ready5_mon", "q53_req_valid_mon",
    "q53_req_rw_mon", "q53_req_addr_mon", "q53_req_strb_mon",
    "q53_rd_en_mon", "q53_bank_ready_mon", "q53_valid_at_req_mon",
    "q53_rreq_ready_mon", "q53_buffer_mask_mon", "q53_nrm_barrier_mon",
    "q53_valid_wr_en_mon", "q53_buf_wready_mon", "q53_buf_wr_addr_mon",
    "q53_valid_clear_mon", "q53_valid_clr_addr_mon", "q53_valid_clr_mask_mon",
}
XMR_LEAVES = {
    "mse_wreq_pingpong_sel": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine.sv",
    "buf2se_mem_rreq_ready": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine.sv",
    "buf2mse_rreq_ready": "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine.sv",
    "mrm2se_req_ready": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster.sv",
    "mrm2buf_req_valid": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "mrm2buf_req_rw": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "mrm2buf_req_addr": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "mrm2buf_req_strb": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "mrm2buf_rd_en": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "buf2mrm_rreq_bank_ready": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "buf2mrm_rreq_ready": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "valid_buf": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "valid_buf_wr_en": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "valid_buf_clear": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "valid_buf_clr_addr": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "valid_buf_clr_mask": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "buf_wreq_ready": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "buf_wr_addr": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "buffer_mask": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "nrm2buf_rd_barrier": "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
}
EVENT_KINDS = {"BUF5_WRITE_ACCEPT", "BUF5_VALID_CLEAR", "BUF5_READ_ACCEPT"}
CANDIDATES = {
    "C_PINGPONG_PORT_SELECTION", "C_BUFFER5_MRM_REQUEST_DECODE",
    "C_BUFFER5_ROW_BANK_LANE_VALIDITY", "C_BUFFER5_WRITE_CLEAR_ORDER",
    "C_BUFFER5_READ_ACCEPT",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(native: Path, addon: Path, parser: Path, rtl_root: Path) -> dict:
    errors: list[str] = []
    native_text = native.read_text(encoding="utf-8")
    addon_text = addon.read_text(encoding="utf-8")
    parser_text = parser.read_text(encoding="utf-8")
    include = '`include "qlinearadd_node0007_tailround_bufready_v53.svh"'
    if native_text.count(include) != 1:
        errors.append("native include count differs")
    functional_addon = re.sub(r"//.*", "", addon_text)
    functional_addon = re.sub(r"/\*.*?\*/", "", functional_addon, flags=re.S)
    if "%m" in functional_addon:
        errors.append("procedural-scope %m is forbidden in v53")
    declared = {
        name for name in REQUIRED_IDENTIFIERS
        if re.search(rf"\b(?:bit|integer|logic)[^;]*\b{re.escape(name)}\b", addon_text, re.S)
    }
    unresolved = sorted(REQUIRED_IDENTIFIERS - declared)
    if unresolved:
        errors.append("undeclared q53 identifiers: " + ",".join(unresolved))
    low_use = sorted(name for name in REQUIRED_IDENTIFIERS if len(re.findall(rf"\b{re.escape(name)}\b", addon_text)) < 2)
    if low_use:
        errors.append("q53 declarations lack consumer/update use: " + ",".join(low_use))
    if addon_text.count("always @(posedge u_NDP_Top_new.clk_sg)") != 1:
        errors.append("qualified source-clock block differs")
    if addon_text.count("always @(posedge u_NDP_Top_new.clk_db)") != 1:
        errors.append("snapshot-clock block differs")
    if "Q53_STATE" not in addon_text or "QADD_TAILROUND_BUFREADY_V53" not in addon_text:
        errors.append("time0/state markers absent")
    for kind in EVENT_KINDS:
        if addon_text.count(f"kind={kind}") != 1:
            errors.append(f"qualified event update differs: {kind}")
    if addon_text.count("q53_event_budget--") != len(EVENT_KINDS):
        errors.append("event budget decrement count differs")
    xmr_records = []
    for leaf, relative in XMR_LEAVES.items():
        rtl = rtl_root / relative
        rtl_text = rtl.read_text(encoding="utf-8") if rtl.is_file() else ""
        addon_count = len(re.findall(rf"\.{re.escape(leaf)}\b", addon_text))
        rtl_count = len(re.findall(rf"\b{re.escape(leaf)}\b", rtl_text))
        if addon_count < 1 or rtl_count < 1:
            errors.append(f"XMR leaf/source closure differs: {leaf}")
        xmr_records.append({
            "leaf": leaf, "addon_use_count": addon_count,
            "rtl_path": relative, "rtl_sha256": digest(rtl) if rtl.is_file() else None,
            "rtl_token_count": rtl_count,
        })
    missing_candidates = sorted(value for value in CANDIDATES if value not in parser_text)
    if missing_candidates:
        errors.append("canonical candidate missing: " + ",".join(missing_candidates))
    selftest = subprocess.run(
        [sys.executable, str(parser), "--selftest"], capture_output=True, text=True, check=False
    )
    if selftest.returncode != 0:
        errors.append("canonical selftest failed")
    return {
        "schema": "qlinearadd-node0007-tailround-bufready-v53-hdl-gate-v1",
        "pass": not errors,
        "errors": errors,
        "members": {
            "native": {"path": str(native), "sha256": digest(native)},
            "addon": {"path": str(addon), "sha256": digest(addon)},
            "parser": {"path": str(parser), "sha256": digest(parser)},
        },
        "declaration_use_update_closure": {
            "required": len(REQUIRED_IDENTIFIERS), "declared": len(declared),
            "unresolved": unresolved, "low_use": low_use,
        },
        "actual_consumer_xmr_closure": {"count": len(xmr_records), "uncovered": [row["leaf"] for row in xmr_records if row["addon_use_count"] < 1 or row["rtl_token_count"] < 1], "records": xmr_records},
        "event_updates": sorted(EVENT_KINDS),
        "canonical_candidates": sorted(CANDIDATES),
        "canonical_selftest": {"exit_code": selftest.returncode, "stdout": selftest.stdout.strip(), "stderr": selftest.stderr.strip()},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--addon", type=Path, required=True)
    parser.add_argument("--parser", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate(args.native, args.addon, args.parser, args.workspace_root)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": report["pass"], "errors": report["errors"]}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
