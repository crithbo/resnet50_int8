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


INSTALL_NAME = "r5_n71_gap_v33_buffer_ag_idx_pair_diag"
EXPECTED_ZIP_SHA256 = "5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03"
EXPECTED_ZIP_BYTES = 1_824_172
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
ANCHOR = "    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic."
DECL_END = "    // v31: COL-LC -> MSE0 WR_Buffer_AG -> Buffer0 MRM byte-lane diagnostic."
SAMPLER_ANCHOR = "    // v33 sampler: qualified input accepts and FIFO accepts only."
SAMPLER_END = "    // v31 sampler: accepted transactions only; stable levels are state."
CRITICAL_UPDATE = "return_obs_bq_enqueue_count++;"
REQUIRED_RECORDS = {
    "BUFFER_AG_IDX_QUEUE_EVENT_V1",
    "BUFFER_AG_IDX_QUEUE_COUNTS_V1",
    "BUFFER_AG_IDX_QUEUE_STATE_V1",
    "BUFFER_AG_IDX_QUEUE_WITNESS_V1",
}
REQUIRED_LEAVES = {
    ".mse_buf_queue_row_idx;",
    ".mse_buf_queue_col_idx;",
    ".mse_buf_queue_row_tag;",
    ".mse_buf_queue_col_tag;",
    ".buf_idx_valid_bit_unmasked;",
    ".buf_idx_same_bit_unmasked;",
    ".buf_idx_gotten_bit;",
    ".buf_idx_same_bit_keep_mask;",
    ".buf_idx_same_bit_masked;",
    ".buf_idx_same_gotten_mask;",
    ".buf_idx_valid_bit_masked;",
    ".buf_idx_bp_pre_keep_mask;",
    ".buf_idx_bp_pre_mask;",
    ".buf_all_idx_matched;",
    ".buf_ag_idx_queue_wr_en;",
    ".buf_ag_idx_queue_full;",
    ".buf_ag_idx_queue_rd_en;",
    ".buf_ag_idx_queue_empty;",
    ".u_buf_ag_idx_queue.fifo_counter;",
    ".mse_buf_ag_tag_valid;",
    ".mse_buf_ag_idx;",
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
    identifiers = set(
        re.findall(r"\breturn_obs_bq_[A-Za-z0-9_]+\b", decl + sampler)
    )
    declared = set(
        re.findall(
            r"\b(?:bit|int|longint unsigned)\s+(return_obs_bq_[A-Za-z0-9_]+)",
            decl,
        )
    )
    declared.update(
        re.findall(r"\btask\s+automatic\s+(return_obs_bq_[A-Za-z0-9_]+)", decl)
    )
    declared.update(
        re.findall(
            r"\b(return_obs_bq_[A-Za-z0-9_]+)(?:\s*,|\s*;)",
            section(decl, ANCHOR, "    generate"),
        )
    )
    undeclared = sorted(
        identifiers - declared - {"return_obs_bq_group", "return_obs_bq_slice"}
    )
    leaves = {leaf: decl.count(leaf) == 1 for leaf in REQUIRED_LEAVES}
    records = {record: record in observer for record in REQUIRED_RECORDS}
    updates = {
        token: token in sampler
        for token in (
            "return_obs_bq_col_accept_count++;",
            "return_obs_bq_row_accept_count++;",
            CRITICAL_UPDATE,
            "return_obs_bq_dequeue_count++;",
        )
    }
    qualified = {
        "col_valid_and_bp":
            "return_obs_bq_valid_raw_mon" in sampler
            and "return_obs_bq_bp_pre_mon" in sampler,
        "enqueue_wr_and_not_full":
            "return_obs_bq_wr_en_mon" in sampler
            and "!return_obs_bq_full_mon" in sampler,
        "dequeue_rd_and_not_empty":
            "return_obs_bq_rd_en_mon" in sampler
            and "!return_obs_bq_empty_mon" in sampler,
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
module v33_fifo; logic [4:0] fifo_counter; endmodule
module v33_bq;
  logic [`SE_BUF_ROW_INPORT_IDX_WIDTH-1:0] mse_buf_queue_row_idx;
  logic [`SE_BUF_COL_INPORT_IDX_WIDTH-1:0] mse_buf_queue_col_idx;
  logic [`SE_BUF_INPORT_TAG_WIDTH-1:0] mse_buf_queue_row_tag, mse_buf_queue_col_tag;
  logic [1:0] mse_buf_queue_bp_pre, buf_idx_valid_bit_unmasked;
  logic [1:0] buf_idx_same_bit_unmasked, buf_idx_gotten_bit;
  logic [1:0] buf_idx_same_bit_keep_mask, buf_idx_same_bit_masked;
  logic [1:0] buf_idx_same_gotten_mask, buf_idx_valid_bit_masked;
  logic [1:0] buf_idx_bp_pre_keep_mask, buf_idx_bp_pre_mask;
  logic buf_all_idx_matched, mse_enable, buf_ag_idx_queue_wr_en;
  logic buf_ag_idx_queue_full, buf_ag_idx_queue_rd_en, buf_ag_idx_queue_empty;
  logic mse_buf_ag_tag_valid;
  logic [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0] mse_buf_ag_tag;
  logic [`MSE_BUF_AG_INPORT_IDX_WIDTH-1:0] mse_buf_ag_idx;
  v33_fifo u_buf_ag_idx_queue();
endmodule
module v33_mrd; v33_bq u_Buffer_AG_Idx_Queue(); endmodule
module v33_rd; v33_mrd u_Memory_RD_Stream_Engine(); endmodule
module v33_stream;
  generate for(genvar i=0;i<1;i++) begin: MSE_INST v33_rd RD_MSE(); end endgenerate
endmodule
module v33_lsu; v33_stream u_Stream_Engine(); endmodule
module v33_slice; v33_lsu u_LSU(); endmodule
module v33_wrapper; v33_slice u_Slice(); endmodule
module v33_group;
  generate for(genvar i=0;i<1;i++) begin: slice_group_gen v33_wrapper u_slice_wrapper(); end endgenerate
endmodule
module v33_ndp;
  logic clk_sg, rst_n_sg;
  generate for(genvar i=0;i<1;i++) begin: slice_with_datahub_mc_group_gen v33_group u_slice_with_datahub_mc_group(); end endgenerate
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
        "`define SE_BUF_ROW_INPORT_IDX_WIDTH 8\n"
        "`define SE_BUF_COL_INPORT_IDX_WIDTH 8\n"
        "`define SE_BUF_INPORT_TAG_WIDTH 8\n"
        "`define MSE_BUF_AG_INPORT_TAG_WIDTH 8\n"
        "`define MSE_BUF_AG_INPORT_IDX_WIDTH 16\n"
        + MOCKS
        + "\nmodule v33_buffer_ag_idx_focus;\n"
        "  v33_ndp u_NDP_Top_new();\n"
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
            [
                str(iverilog), "-g2012", "-tnull",
                "-s", "v33_buffer_ag_idx_focus", str(source_path),
            ],
            temp,
        )
        return {
            "valid": closure["valid"] and compile_result["exit_code"] == 0,
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


def replace_in_sampler(observer: str, old: str, new: str) -> str:
    left, right = observer.split(SAMPLER_ANCHOR, 1)
    return left + SAMPLER_ANCHOR + right.replace(old, new, 1)


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
        with tempfile.TemporaryDirectory(prefix="gap-v33-hdl-") as temp_name:
            temp = Path(temp_name)
            positive = evaluate(observer, args.iverilog.resolve(), temp, "positive")
            mutations = [
                (
                    "declaration_removed",
                    observer.replace(
                        "    longint unsigned return_obs_bq_enqueue_count;\n",
                        "",
                        1,
                    ),
                ),
                (
                    "sampler_use_misspelled",
                    replace_in_sampler(
                        observer,
                        "return_obs_bq_full_mon[return_obs_group_id]",
                        "return_obs_bq_full_typo[return_obs_group_id]",
                    ),
                ),
                (
                    "critical_update_removed",
                    observer.replace(CRITICAL_UPDATE, "/* update removed */", 1),
                ),
                (
                    "xmr_leaf_misspelled",
                    observer.replace(
                        ".buf_idx_same_gotten_mask;",
                        ".buf_idx_same_gotten_typo;",
                        1,
                    ),
                ),
            ]
            controls = []
            for name, mutated in mutations:
                check = evaluate(mutated, args.iverilog.resolve(), temp, name)
                controls.append(
                    {
                        "name": name,
                        "failed_closed": not check["valid"],
                        "compile_exit_code":
                            check["focused_xmr_sampler_compile"].get("exit_code"),
                        "ledger_valid":
                            check["scoped_identifier_closure"].get("valid"),
                    }
                )
        all_negative = all(item["failed_closed"] for item in controls)
        passed = positive["valid"] and all_negative and version["exit_code"] == 0
        result = {
            "schema": "gap-node0071-v33-buffer-ag-index-focused-hdl-v1",
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
                "exact v33 package-local added Buffer_AG_Idx_Queue XMR "
                "declarations, focused mock name-resolution and qualified sampler"
            ),
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {
            "schema": "gap-node0071-v33-buffer-ag-index-focused-hdl-v1",
            "status": "FAIL",
            "pass": False,
            "error": str(error),
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
