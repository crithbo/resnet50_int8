from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n71_gap_v31_col_ag_mrm_lane_diag"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
EXPECTED_ZIP_SHA256 = "d37405bf47e2a572f52de47580faec3375ba387fffeb0168bad1cf42b7671650"
EXPECTED_ZIP_BYTES = 1_821_349
ANCHOR = "    // v31: COL-LC -> MSE0 WR_Buffer_AG -> Buffer0 MRM byte-lane diagnostic."
DECL_END = "    // v30: Buffer0 ARM read-ready conjunction factor diagnostic."
SAMPLER_ANCHOR = "    // v31 sampler: accepted transactions only; stable levels are state."
SAMPLER_END = "    // v30 factor sampler: only qualified accepts and factor edges advance."
CRITICAL_UPDATE = "return_obs_lane_mrm_write_accept_count++;"
REQUIRED_RECORDS = {
    "COL_AG_MRM_LANE_EVENT_V1",
    "COL_AG_MRM_LANE_COUNTS_V1",
    "COL_AG_MRM_LANE_STATE_V1",
    "COL_AG_MRM_LANE_WITNESS_V1",
}
REQUIRED_LEAVES = {
    ".iga_col_lc_outport[0];",
    ".iga_col_lc_outport_bp_post[0];",
    ".buf_ag_ob_wr_en;",
    ".buf_ag_bp_pre;",
    ".u_WR_Buffer_AG.mse_buf_ag_idx;",
    ".u_Memory_RD_Stream_Engine.mse2buf_wreq_col_addr;",
    ".u_Buffer_Manager.mrm2buf_req_strb;",
    ".u_Buffer_Manager.buf2mrm_req_ready;",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], cwd: Path | None = None) -> dict[str, Any]:
    process = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "argv": argv,
        "cwd": str(cwd) if cwd else None,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "stdout_sha256": sha256_bytes(process.stdout.encode()),
        "stderr_sha256": sha256_bytes(process.stderr.encode()),
    }


def section(text: str, start: str, end: str) -> str:
    left = text.find(start)
    right = text.find(end, left)
    if left < 0 or right <= left:
        raise ValueError(f"focused observer section absent: {start}")
    return text[left:right]


def read_exact(path: Path) -> tuple[str, dict[str, Any]]:
    if path.stat().st_size != EXPECTED_ZIP_BYTES:
        raise ValueError("final ZIP byte size differs")
    if sha256_path(path) != EXPECTED_ZIP_SHA256:
        raise ValueError("final ZIP SHA256 differs")
    member = f"{INSTALL_NAME}/{OBSERVER_RELATIVE}"
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC differs")
        payload = archive.read(member)
    return payload.decode("utf-8"), {
        "zip": str(path),
        "zip_size_bytes": path.stat().st_size,
        "zip_sha256": sha256_path(path),
        "observer_member": member,
        "observer_size_bytes": len(payload),
        "observer_sha256": sha256_bytes(payload),
    }


def ledger(observer: str) -> dict[str, Any]:
    decl = section(observer, ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    code = decl + sampler
    identifiers = set(re.findall(r"\breturn_obs_lane_[A-Za-z0-9_]+\b", code))
    declared = set(
        re.findall(
            r"\b(?:bit|int|longint unsigned)\s+(return_obs_lane_[A-Za-z0-9_]+)",
            decl,
        )
    )
    declared.update(
        re.findall(r"\btask\s+automatic\s+(return_obs_lane_[A-Za-z0-9_]+)", decl)
    )
    declared.update(
        re.findall(
            r"\b(return_obs_lane_[A-Za-z0-9_]+)(?:\s*,|\s*;)",
            section(decl, ANCHOR, "    generate"),
        )
    )
    undeclared = sorted(
        identifiers - declared - {"return_obs_lane_group", "return_obs_lane_slice"}
    )
    leaves = {leaf: decl.count(leaf) == 1 for leaf in REQUIRED_LEAVES}
    records = {record: record in observer for record in REQUIRED_RECORDS}
    updates = {
        token: token in sampler
        for token in (
            "return_obs_lane_col_accept_count++;",
            "return_obs_lane_bag_accept_count++;",
            "return_obs_lane_mse_write_accept_count++;",
            CRITICAL_UPDATE,
        )
    }
    qualified = {
        "col_valid_and_all_bp":
            "[`IGA_COL_LC_PORT_WIDTH-1] &&" in sampler
            and "(&return_obs_lane_col_bp_mon" in sampler,
        "bag_write_and_bp":
            "return_obs_lane_bag_wr_mon" in sampler
            and "return_obs_lane_bag_bp_mon" in sampler,
        "mse_request_data_ready":
            "return_obs_lane_mse_wvalid_mon" in sampler
            and "return_obs_lane_mse_ready_mon" in sampler,
        "mrm_request_data_ready":
            "return_obs_lane_mrm_wvalid_mon" in sampler
            and "return_obs_lane_mrm_ready_mon" in sampler,
    }
    valid = (
        not undeclared
        and all(leaves.values())
        and all(records.values())
        and all(updates.values())
        and all(qualified.values())
    )
    return {
        "identifiers": sorted(identifiers),
        "declared": sorted(declared),
        "undeclared_identifiers": undeclared,
        "xmr_leaf_exact_set": leaves,
        "required_records": records,
        "qualified_updates": updates,
        "qualified_conjunctions": qualified,
        "stable_level_counts_as_progress": False,
        "valid": valid,
    }


MOCKS = r'''
module v31_iga;
  logic [`IGA_COL_LC_PORT_WIDTH-1:0] iga_col_lc_outport [0:0];
  logic [`IGA_COL_LC_DST_NUM-1:0] iga_col_lc_outport_bp_post [0:0];
endmodule
module v31_bag;
  logic buf_ag_ob_wr_en, buf_ag_bp_pre, buf_ag_ob_rd_en, buf_ag_ob_empty;
  logic [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0] mse_buf_ag_tag;
  logic [`MSE_BUF_AG_INPORT_IDX_WIDTH-1:0] mse_buf_ag_idx;
endmodule
module v31_mrd;
  v31_bag u_WR_Buffer_AG();
  logic [`MSE_BUF_REQ_NUM-1:0] mse2buf_wreq_valid;
  logic [`BUFFER_ROW_ADDR_WIDTH-1:0] mse2buf_wreq_row_addr;
  logic [`MSE_BUF_REQ_NUM-1:0][`BUFFER_COL_ADDR_WIDTH-1:0] mse2buf_wreq_col_addr;
  logic mse2buf_wvalid, buf2mse_wreq_ready;
endmodule
module v31_rd; v31_mrd u_Memory_RD_Stream_Engine(); endmodule
module v31_stream;
  generate for(genvar i=0;i<1;i++) begin: MSE_INST v31_rd RD_MSE(); end endgenerate
endmodule
module v31_bm;
  logic [`MSE_BUF_REQ_NUM-1:0] mrm2buf_req_valid;
  logic [`BUFFER_BANK_ADDR_WIDTH-1:0] mrm2buf_req_addr;
  logic [`BUFFER_BANK_NUM-1:0][`BUFFER_STRB_WIDTH-1:0] mrm2buf_req_strb;
  logic mrm2buf_wvalid, buf2mrm_req_ready;
endmodule
module v31_bmc;
  generate for(genvar i=0;i<1;i++) begin: BUFFER_MANAGER v31_bm u_Buffer_Manager(); end endgenerate
endmodule
module v31_lsu; v31_stream u_Stream_Engine(); v31_bmc u_Buffer_Manager_Cluster(); endmodule
module v31_slice; v31_iga u_Index_Generation_Array(); v31_lsu u_LSU(); endmodule
module v31_wrapper; v31_slice u_Slice(); endmodule
module v31_group;
  generate for(genvar i=0;i<1;i++) begin: slice_group_gen v31_wrapper u_slice_wrapper(); end endgenerate
endmodule
module v31_ndp;
  logic clk_sg, rst_n_sg;
  generate for(genvar i=0;i<1;i++) begin: slice_with_datahub_mc_group_gen v31_group u_slice_with_datahub_mc_group(); end endgenerate
endmodule
'''


def projection(observer: str) -> str:
    decl = section(observer, ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    sampler = sampler.replace("return_obs_group_id", "0")
    sampler = sampler.replace("return_obs_local_slice_id", "0")
    return (
        "`define SLICE_GROUP_SIZE 1\n"
        "`define SLICE_GROUP_NUM 1\n"
        "`define IGA_COL_LC_PORT_WIDTH 16\n"
        "`define IGA_COL_LC_DST_NUM 1\n"
        "`define MSE_BUF_AG_INPORT_TAG_WIDTH 4\n"
        "`define MSE_BUF_AG_INPORT_IDX_WIDTH 8\n"
        "`define MSE_BUF_REQ_NUM 8\n"
        "`define BUFFER_ROW_ADDR_WIDTH 4\n"
        "`define BUFFER_COL_ADDR_WIDTH 5\n"
        "`define BUFFER_BANK_ADDR_WIDTH 4\n"
        "`define BUFFER_BANK_NUM 8\n"
        "`define BUFFER_STRB_WIDTH 4\n"
        + MOCKS
        + "\nmodule v31_col_ag_mrm_focus;\n"
        "  v31_ndp u_NDP_Top_new();\n"
        "  bit return_obs_enabled, return_obs_active;\n"
        "  integer return_obs_fd, return_obs_group_id, return_obs_local_slice_id;\n"
        "  longint unsigned return_obs_sg_clock_edge_count;\n"
        + decl
        + sampler
        + "\nendmodule\n"
    )


def evaluate(observer: str, iverilog: Path, temp: Path, stem: str) -> dict[str, Any]:
    try:
        closure = ledger(observer)
        source = projection(observer)
        source_path = temp / f"{stem}.sv"
        source_path.write_text(source, encoding="utf-8", newline="\n")
        compile_result = run(
            [str(iverilog), "-g2012", "-tnull", "-s", "v31_col_ag_mrm_focus", str(source_path)],
            temp,
        )
        valid = closure["valid"] and compile_result["exit_code"] == 0
        return {
            "valid": valid,
            "scoped_identifier_closure": closure,
            "focused_xmr_sampler_compile": compile_result,
            "projection_sha256": sha256_bytes(source.encode()),
        }
    except Exception as error:
        return {
            "valid": False,
            "scoped_identifier_closure": {"valid": False, "error": str(error)},
            "focused_xmr_sampler_compile": {"exit_code": 1, "stderr": str(error)},
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--iverilog", type=Path, default=Path(r"C:\iverilog\bin\iverilog.exe")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        observer, receipt = read_exact(args.target_zip.resolve())
        version = run([str(args.iverilog.resolve()), "-V"])
        with tempfile.TemporaryDirectory(prefix="gap-v31-hdl-") as temp_name:
            temp = Path(temp_name)
            positive = evaluate(observer, args.iverilog.resolve(), temp, "positive")
            controls = []
            mutations = [
                (
                    "declaration_removed",
                    observer.replace(
                        "    longint unsigned return_obs_lane_mrm_write_accept_count;\n",
                        "",
                        1,
                    ),
                ),
                (
                    "sampler_use_misspelled",
                    observer.replace(
                        "return_obs_lane_mrm_ready_mon"
                        "[return_obs_group_id][return_obs_local_slice_id];\n"
                        "            lane_any_event",
                        "return_obs_lane_mrm_ready_typo"
                        "[return_obs_group_id][return_obs_local_slice_id];\n"
                        "            lane_any_event",
                        1,
                    ),
                ),
                (
                    "critical_update_removed",
                    observer.replace(CRITICAL_UPDATE, "/* critical update removed */", 1),
                ),
                (
                    "xmr_leaf_misspelled",
                    observer.replace(
                        ".u_Buffer_Manager.mrm2buf_req_strb;",
                        ".u_Buffer_Manager.mrm2buf_req_strobe_typo;",
                        1,
                    ),
                ),
            ]
            for name, mutated in mutations:
                check = evaluate(mutated, args.iverilog.resolve(), temp, name)
                controls.append(
                    {
                        "name": name,
                        "failed_closed": not check["valid"],
                        "compile_exit_code": check["focused_xmr_sampler_compile"].get(
                            "exit_code"
                        ),
                        "ledger_valid": check["scoped_identifier_closure"].get("valid"),
                    }
                )
        all_negative = all(item["failed_closed"] for item in controls)
        passed = positive["valid"] and all_negative and version["exit_code"] == 0
        result = {
            "schema": "gap-node0071-v31-col-ag-mrm-focused-hdl-revalidation-v1",
            "status": "PASS" if passed else "FAIL",
            "pass": passed,
            "target_receipt": receipt,
            "tool": {
                "path": str(args.iverilog.resolve()),
                "version_exit_code": version["exit_code"],
                "version_stdout": version["stdout"],
                "version_stderr": version["stderr"],
            },
            "positive": positive,
            "negative_controls": controls,
            "all_negative_controls_fail_closed": all_negative,
            "full_design_elaboration_claimed": False,
            "claim_boundary": (
                "exact v31 package-local added XMR declarations, focused mock "
                "name-resolution, accepted-event sampler syntax/use/update closure"
            ),
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {"schema": "gap-node0071-v31-col-ag-mrm-focused-hdl-revalidation-v1",
                  "status": "FAIL", "pass": False, "error": str(error)}
        exit_code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
