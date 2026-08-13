from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v36_b5rd_diag"
MARKER = "    // v36: qualified Buffer5 read-request and return-path discriminator."
COUNTERS = (
    "rd_req_accept",
    "cluster_accept",
    "buffer_accept",
    "rvalid_rise",
    "rd_pop",
)
ACTIVE_FILES = (
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Connect.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compile_case(
    iverilog: Path, root: Path, name: str, source: str
) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    command = [
        str(iverilog),
        "-g2012",
        "-s",
        "b5rd_focus_top",
        "-o",
        str(output_path),
        str(source_path),
    ]
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": command,
        "cwd": str(root),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def prefix() -> str:
    return r'''
`timescale 1ns/1ps
module rd_ag_stub;
  logic buf_ag_ob_rd_en, buf_ag_ob_empty, buf_ag_ob_full;
  logic [3:0] buf_ag_ob_cnt;
endmodule
module memory_wr_stream_engine_stub;
  rd_ag_stub u_RD_Buffer_AG();
endmodule
module wr_mse_stub;
  memory_wr_stream_engine_stub u_Memory_WR_Stream_Engine();
endmodule
module stream_engine_stub;
  logic [0:0][31:0] mse2buf_rreq_valid;
  logic [0:0] mse_wreq_pingpong_sel, buf2mse_rreq_ready;
  generate
    for (genvar i=0;i<5;i++) begin : MSE_INST
      wr_mse_stub WR_MSE();
    end
  endgenerate
endmodule
module buffer_stub;
  logic [7:0] buf2mrm_rreq_bank_ready, mrm2buf_rd_en;
  logic buf2mrm_rreq_ready;
endmodule
module buffer_manager_stub;
  logic [7:0] mrm2buf_req_valid;
  logic [7:0][15:0] mrm2buf_req_strb;
  logic [11:0] mrm2buf_req_addr;
  buffer_stub u_Buffer();
endmodule
module cluster_stub;
  logic [5:0][31:0] se2mrm_req_valid;
  logic [5:0] mrm2se_req_ready, mrm2se_rvalid;
  generate
    for (genvar j=0;j<6;j++) begin : BUFFER_MANAGER
      buffer_manager_stub u_Buffer_Manager();
    end
  endgenerate
endmodule
module lsu_stub;
  stream_engine_stub u_Stream_Engine();
  cluster_stub u_Buffer_Manager_Cluster();
endmodule
module slice_stub; lsu_stub u_LSU(); endmodule
module slice_wrapper_stub; slice_stub u_Slice(); endmodule
module group_stub;
  generate
    for (genvar s=0;s<1;s++) begin : slice_group_gen
      slice_wrapper_stub u_slice_wrapper();
    end
  endgenerate
endmodule
module ndp_stub;
  logic clk_db, rst_n_db;
  generate
    for (genvar g=0;g<1;g++) begin : slice_with_datahub_mc_group_gen
      group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module b5rd_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled, return_obs_active;
  integer return_obs_fd;
'''


def semantic_closure(block: str, full: str) -> dict[str, Any]:
    per_counter: dict[str, dict[str, bool]] = {}
    for name in COUNTERS:
        identifier = f"return_obs_b5_{name}"
        local = f"b5_{name}_now"
        per_counter[name] = {
            "declared_once": block.count(f"longint unsigned {identifier};") == 1,
            "initialized_and_reset": block.count(f"{identifier} = 0;") == 2,
            "qualified_update_once": block.count(
                f"if ({local}) {identifier}++;"
            )
            == 1,
            "consumer_use": block.count(identifier) >= 4,
        }
    checks = {
        "all_counter_roles_closed": all(
            all(row.values()) for row in per_counter.values()
        ),
        "edge_record_present": block.count("B5RD_EDGE_V1") == 1,
        "boundary_record_present": block.count("B5RD_BOUNDARY_V1") == 1,
        "decision_hook_direct": full.count(
            'return_obs_write_b5rd_state("DIAG_DECISION");'
        )
        == 1,
        "row_snapshot_hook_direct": full.count(
            'return_obs_write_rowlc4_bufag_state("DIAG_DECISION");'
        )
        == 1,
        "v35_match_rising_qualified": (
            "!return_obs_rb_buf_match_prev" in full
            and "return_obs_rb_buf_match_prev =" in full
        ),
        "state_change_not_progress": (
            "b5_state != return_obs_b5_prev_state" in block
            and "if (b5_state)" not in block
        ),
        "qualified_handshakes": all(
            token in block
            for token in (
                "b5_rd_req_valid && b5_selected_ready",
                "b5_cluster_valid && b5_cluster_ready",
                "mrm2buf_rd_en",
                "b5_buffer_ready",
                "b5_rvalid && !return_obs_b5_prev_state[8]",
            )
        ),
        "physical_chain_exact": all(
            token in block
            for token in (
                ".u_Stream_Engine.mse2buf_rreq_valid[0]",
                ".u_Stream_Engine.mse_wreq_pingpong_sel[0]",
                ".u_Stream_Engine.buf2mse_rreq_ready[0]",
                ".u_Buffer_Manager_Cluster.se2mrm_req_valid[5]",
                ".BUFFER_MANAGER[5].u_Buffer_Manager",
                ".u_Buffer.buf2mrm_rreq_bank_ready",
                ".MSE_INST[4].WR_MSE",
            )
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "per_counter": per_counter,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    project = args.project_root.resolve()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip.resolve()) as archive:
        if archive.testzip() is not None:
            errors.append("ZIP CRC failed")
        payload = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = payload.decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v36 marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER) :]

    active: list[dict[str, Any]] = []
    for relative in ACTIVE_FILES:
        path = project / relative
        if not path.is_file():
            errors.append(f"missing active RTL leaf: {relative}")
            continue
        active.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": digest(path.read_bytes()),
            }
        )

    focused = prefix() + block + "\nendmodule\n"
    closure = semantic_closure(block, observer)
    with tempfile.TemporaryDirectory(prefix="v36-b5rd-scope-") as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog.resolve(), root, "positive", focused)
        typo = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_typo_consumer",
            focused.replace(".BUFFER_MANAGER[5]", ".BUFFER_MANAGEX[5]", 1),
        )
        deleted = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_declaration",
            focused.replace(
                "longint unsigned return_obs_b5_rd_req_accept;\n", "", 1
            ),
        )
        syntax = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_task_end",
            focused.replace("    endtask", "    end", 1),
        )
        update_block = block.replace(
            "if (b5_cluster_accept_now) return_obs_b5_cluster_accept++;",
            "",
            1,
        )
        update_case = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_qualified_update",
            prefix() + update_block + "\nendmodule\n",
        )
        update_closure = semantic_closure(update_block, observer)

    if positive["exit_code"] != 0:
        errors.append("focused positive compile failed")
    if not closure["valid"]:
        errors.append("positive semantic closure failed")
    if any(case["exit_code"] == 0 for case in (typo, deleted, syntax)):
        errors.append("syntax/scope negative did not fail closed")
    if update_closure["valid"]:
        errors.append("deleted qualified update did not fail semantic closure")
    report = {
        "schema": "node0004-v36-b5rd-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "package_local_hdl_gate": {
            "applicable": True,
            "rule_id": (
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-"
                "SYNTAX-SCOPE-POSITIVE-001"
            ),
            "exact_member": {
                "path": f"{INSTALL_NAME}/tb_probe/native_return_observer.svh",
                "bytes": len(payload),
                "sha256": digest(payload),
            },
            "frontend": {
                "name": "Icarus Verilog",
                "command": positive["command"],
                "cwd": positive["cwd"],
                "exit": positive["exit_code"],
                "coverage": "focused",
            },
            "focused_harness_sha256": digest(focused.encode()),
            "closure": {
                "scope": "v36 B5RD state plus v35 match/snapshot corrections",
                "declared": len(COUNTERS) + 2,
                "used": len(COUNTERS) + 2,
                "unresolved": 0 if closure["valid"] else 1,
                "ownerless_state": 0 if closure["valid"] else 1,
            },
            "claim_boundary": (
                "v36-added/modified package-local diagnostic leaves and exact "
                "e1fb direct-consumer hashes; not full-design VCS elaboration"
            ),
            "pass": not errors,
        },
        "active_local_rtl": active,
        "positive": positive,
        "positive_semantic_closure": closure,
        "negative_typo_consumer": typo,
        "negative_deleted_declaration": deleted,
        "negative_missing_task_end": syntax,
        "negative_deleted_qualified_update": update_case,
        "negative_deleted_qualified_update_semantic_closure": update_closure,
        "all_negative_controls_fail_closed": (
            all(case["exit_code"] != 0 for case in (typo, deleted, syntax))
            and not update_closure["valid"]
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
