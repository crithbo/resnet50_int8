from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v37_wrdrain_diag"
MARKER = "    // v37: state-only discriminator after qualified descriptor/data counters."
RTL_LEAF = (
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
)
XMR_LEAVES = (
    "wr_chl_queue_empty",
    "wr_chl_queue_full",
    "u_wr_chl_queue.fifo_counter",
    "wr_chl_queue_rd_tsf_size",
    "wr_chl_queue_rd_mask_flag",
    "wr_chl_mask_buf_vld",
    "wr_chl_mask_buf_bp_post",
    "raw_col_data_valid",
    "wr_data_chl_hold_data_vld",
    "wr_data_chl_prepared_data_cnt",
    "wr_data_chl_prepared_data_vld",
    "wr_chl_prepared_data_bp_pre",
    "wr_chl_ob_sel",
    "wr_chl_ob_vld_in",
    "wr_chl_ob_vld",
    "wr_chl_ob_bp_pre",
    "wr_chl_ob_wr_hs",
    "wr_chl_ob_rd_hs",
    "mem2mse_wdata_ready",
    "mse2mem_wdata_valid",
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
        "wrdrain_focus_top",
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
module fifo_stub;
  logic [5:0] fifo_counter;
endmodule
module wr_data_channel_stub;
  logic wr_chl_queue_empty, wr_chl_queue_full;
  fifo_stub u_wr_chl_queue();
  logic [4:0] wr_chl_queue_rd_tsf_size;
  logic wr_chl_queue_rd_mask_flag;
  logic [1:0] wr_chl_mask_buf_vld, wr_chl_mask_buf_bp_post;
  logic raw_col_data_valid, wr_data_chl_hold_data_vld;
  logic [5:0] wr_data_chl_prepared_data_cnt;
  logic wr_data_chl_prepared_data_vld, wr_chl_prepared_data_bp_pre;
  logic wr_chl_ob_sel;
  logic [1:0] wr_chl_ob_vld_in, wr_chl_ob_vld, wr_chl_ob_bp_pre;
  logic [1:0] wr_chl_ob_wr_hs, wr_chl_ob_rd_hs;
  logic [1:0] mem2mse_wdata_ready, mse2mem_wdata_valid;
endmodule
module memory_wr_stream_engine_stub;
  wr_data_channel_stub u_WR_Data_Channel();
endmodule
module wr_mse_stub;
  memory_wr_stream_engine_stub u_Memory_WR_Stream_Engine();
endmodule
module stream_engine_stub;
  generate
    for (genvar i=0;i<5;i++) begin : MSE_INST
      wr_mse_stub WR_MSE();
    end
  endgenerate
endmodule
module lsu_stub; stream_engine_stub u_Stream_Engine(); endmodule
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
  generate
    for (genvar g=0;g<1;g++) begin : slice_with_datahub_mc_group_gen
      group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module wrdrain_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled;
  integer return_obs_fd;
'''


def suffix() -> str:
    return r'''
  initial begin
    #1;
    return_obs_write_wrdrain_state("FOCUS");
  end
endmodule
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    project = args.project_root.resolve()
    errors: list[str] = []
    member = f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
    with zipfile.ZipFile(args.zip.resolve()) as archive:
        if archive.testzip() is not None:
            errors.append("ZIP CRC failed")
        payload = archive.read(member)
    observer = payload.decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v37 WR drain marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER) :]

    rtl_path = project / RTL_LEAF
    rtl_text = rtl_path.read_text(encoding="utf-8")
    rtl_leaf_checks = {
        leaf: (
            leaf.split(".")[-1] in rtl_text
            or leaf == "u_wr_chl_queue.fifo_counter"
            and "u_wr_chl_queue" in rtl_text
        )
        for leaf in XMR_LEAVES
    }
    closure = {
        "single_feature_declaration": (
            block.count("bit return_obs_wrd_enabled;") == 1
        ),
        "single_task_declaration": (
            block.count(
                "task automatic return_obs_write_wrdrain_state"
            )
            == 1
        ),
        "single_boundary_schema": block.count("WRDRAIN_BOUNDARY_V1") == 1,
        "direct_canonical_hook": observer.count(
            'return_obs_write_wrdrain_state("DIAG_DECISION");'
        )
        == 1,
        "qualified_upstream_hooks": all(
            observer.count(token) >= 1
            for token in (
                'return_obs_write_mse4_descriptor_state("DIAG_DECISION");',
                'return_obs_write_dwrite_path_state("DIAG_DECISION");',
                'return_obs_write_datahub_drain_state("DIAG_DECISION");',
            )
        ),
        "state_not_canonical_progress": (
            "return_hang_diag_current_progress" not in block
            and "++" not in block
        ),
        "all_xmr_leaf_tokens_present": all(
            leaf in block for leaf in XMR_LEAVES
        ),
        "all_xmr_leaf_owners_in_current_rtl": all(
            rtl_leaf_checks.values()
        ),
    }
    if not all(closure.values()):
        errors += [name for name, value in closure.items() if not value]

    full_source = prefix() + block + suffix()
    with tempfile.TemporaryDirectory(prefix="v37-wrdrain-scope-") as temp:
        root = Path(temp)
        positive = compile_case(
            args.iverilog.resolve(), root, "positive", full_source
        )
        missing_gate = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_gate",
            full_source.replace(
                "bit return_obs_wrd_enabled;",
                "// declaration removed by negative control",
                1,
            ),
        )
        typo_leaf = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_typo_leaf",
            full_source.replace(
                ".wr_chl_queue_empty",
                ".wr_chl_queue_empty_typo",
                1,
            ),
        )
        missing_task = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_task",
            full_source.replace(
                "task automatic return_obs_write_wrdrain_state",
                "task automatic return_obs_write_wrdrain_state_typo",
                1,
            ),
        )
    negative_controls = {
        "missing_feature_declaration_fail_closed": (
            missing_gate["exit_code"] != 0
        ),
        "typo_xmr_leaf_fail_closed": typo_leaf["exit_code"] != 0,
        "missing_task_owner_fail_closed": missing_task["exit_code"] != 0,
    }
    if positive["exit_code"] != 0:
        errors.append("focused positive compile failed")
    if not all(negative_controls.values()):
        errors += [
            name for name, value in negative_controls.items() if not value
        ]

    report = {
        "schema": "node0004-v37-wrdrain-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "package_local_hdl_gate": {
            "applicable": True,
            "rule_id": (
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-"
                "POSITIVE-001"
            ),
            "exact_member": {
                "path": member,
                "bytes": len(payload),
                "sha256": digest(payload),
            },
            "frontend": {
                "name": "Icarus Verilog",
                "command": positive["command"],
                "cwd": positive["cwd"],
                "exit": positive["exit_code"],
                "coverage": "focused v37-added WRDRAIN snapshot and direct task owner",
            },
            "focused_harness_sha256": digest(
                full_source.encode("utf-8")
            ),
            "closure": closure,
            "claim_boundary": (
                "v37-added WRDRAIN state snapshot and direct leaf scope only; "
                "v36 server return already proved the unchanged observer compiles"
            ),
            "pass": not errors,
        },
        "active_local_rtl_leaf": {
            "path": RTL_LEAF,
            "bytes": rtl_path.stat().st_size,
            "sha256": digest(rtl_path.read_bytes()),
            "leaf_checks": rtl_leaf_checks,
        },
        "positive_control": positive,
        "negative_controls": {
            **negative_controls,
            "details": {
                "missing_feature_declaration": missing_gate,
                "typo_xmr_leaf": typo_leaf,
                "missing_task_owner": missing_task,
            },
        },
        "all_negative_controls_fail_closed": all(
            negative_controls.values()
        ),
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt_in_this_successor": False,
        "functional_rtl_modified": False,
        "server_action": False,
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
