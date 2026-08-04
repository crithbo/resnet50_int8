from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v33_lc18_pe7_diag"
MARKER = (
    "    // v33: mapped physical LC17/LC18/PE7 -> "
    "WRITE_STREAM0 input1 boundary."
)
ACTIVE_FILES = {
    "Index_Generation_Array": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/"
        "Index_Generation_Array.sv"
    ),
    "IGA_Interconnect": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_Interconnect.sv"
    ),
    "IGA_LC_Counter": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/"
        "IGA_LC_Counter.sv"
    ),
    "IGA_PE_Inbuffer": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_Inbuffer.sv"
    ),
    "IGA_PE_Outbuffer": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_Outbuffer.sv"
    ),
    "Memory_AG_Idx_Queue": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_AG_Idx_Queue.sv"
    ),
}
ACTIVE_TOKENS = {
    "Index_Generation_Array": ("IGA_LC", "IGA_PE", "iga_lc_outport_bp_post"),
    "IGA_Interconnect": (
        "iga_lc_outport_bp_post",
        "iga_pe_outport_bp_post",
        "iga2se_mem_inport",
    ),
    "IGA_LC_Counter": (
        "iga_lc_cnt_outport_valid_bit",
        "iga_lc_cnt_outport",
        "iga_lc_cnt_bp_post",
    ),
    "IGA_PE_Inbuffer": (
        "iga_pe_inbuffer_enbale",
        "iga_pe_inbuffer_matched",
        "iga_pe_inport_valid_bit",
        "iga_pe_inport_last_index",
    ),
    "IGA_PE_Outbuffer": (
        "normal_mode_wr_handshake",
        "normal_mode_rd_handshake",
        "iga_pe_outbuffer_count",
    ),
    "Memory_AG_Idx_Queue": (
        "mse_mem_queue_bp_pre",
        "mem_idx_valid_same_gotten_masked",
        "mem_idx_gotten_bit",
    ),
}
COUNTERS = (
    "lc17_out",
    "lc18_parent",
    "lc18_out",
    "pe7_in0",
    "pe7_in2",
    "pe7_write",
    "pe7_read",
    "mse_input1",
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
        "lc18_pe7_focus_top",
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
module lc_counter_stub;
  logic iga_lc_cnt_outport_valid_bit;
endmodule
module lc_stub;
  logic iga_lc_cnt_bp_post, iga_lc_inbuffer_valid_bit, iga_lc_cnt_bp_pre;
  logic [31:0] iga_lc_outport;
  lc_counter_stub u_IGA_LC_Counter();
endmodule
module pe_inbuffer_stub;
  logic [2:0] iga_pe_inbuffer_enbale;
  logic [2:0] iga_pe_inport_valid_bit, iga_pe_inport_last_bit;
  logic [2:0][3:0] iga_pe_inport_last_index;
  logic iga_pe_inbuffer_matched;
endmodule
module pe_outbuffer_stub;
  logic normal_mode_wr_handshake, normal_mode_rd_handshake;
  logic [2:0] iga_pe_outbuffer_count;
endmodule
module pe_stub;
  logic [2:0] iga_pe_inbuffer_bp_pre;
  logic [5:0] iga_pe_alu_result_tag;
  logic [31:0] iga_pe_outport;
  pe_inbuffer_stub u_IGA_PE_Inbuffer();
  pe_outbuffer_stub u_IGA_PE_Outbuffer();
endmodule
module index_generation_array_stub;
  logic [19:0][7:0] iga_lc_outport_bp_post;
  generate
    for (genvar i=0;i<20;i++) begin : IGA_LC
      lc_stub u_IGA_LC();
    end
    for (genvar j=0;j<12;j++) begin : IGA_PE
      pe_stub u_IGA_PE();
    end
  endgenerate
endmodule
module memory_idx_queue_stub;
  logic [2:0] mse_mem_queue_bp_pre;
  logic [2:0] mem_idx_valid_same_gotten_masked;
  logic [2:0] mem_idx_valid_bit_unmasked;
  logic [2:0] mem_idx_same_bit_unmasked;
  logic [2:0] mem_idx_gotten_bit;
endmodule
module memory_wr_stream_engine_stub;
  memory_idx_queue_stub u_Memory_AG_Idx_Queue();
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
module slice_stub;
  index_generation_array_stub u_Index_Generation_Array();
  lsu_stub u_LSU();
endmodule
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
module lc18_pe7_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled, return_obs_active;
  integer return_obs_fd;
'''


def semantic_closure(source: str) -> dict[str, Any]:
    per_counter: dict[str, dict[str, bool]] = {}
    for name in COUNTERS:
        identifier = f"return_obs_lp_{name}"
        local = f"lp_{name}"
        per_counter[name] = {
            "declared_once": (
                source.count(f"longint unsigned {identifier};") == 1
            ),
            "initialized": source.count(f"{identifier} = 0;") >= 2,
            "qualified_update_once": (
                source.count(f"if ({local}) {identifier}++;") == 1
            ),
            "consumer_use": source.count(identifier) >= 5,
        }
    checks = {
        "all_counter_roles_closed": all(
            all(row.values()) for row in per_counter.values()
        ),
        "edge_record_present": source.count("LC18_PE7_EDGE_V1") == 1,
        "boundary_record_present": source.count("LC18_PE7_BOUNDARY_V1") == 1,
        "state_not_progress": (
            "Only qualified captures/writes/reads are progress" in source
        ),
        "physical_mapping_exact": all(
            token in source
            for token in (
                ".IGA_LC[17].u_IGA_LC",
                ".IGA_LC[18].u_IGA_LC",
                ".IGA_PE[7].u_IGA_PE",
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
        observer_payload = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = observer_payload.decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v33 marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER) :]

    active: dict[str, Any] = {}
    for module, relative in ACTIVE_FILES.items():
        path = project / relative
        text = path.read_text(encoding="utf-8")
        checks = {
            token: token in text for token in ACTIVE_TOKENS[module]
        }
        active[module] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": digest(path.read_bytes()),
            "leaf_checks": checks,
        }
        if not all(checks.values()):
            errors.append(f"{module} active leaf closure failed")

    focused = prefix() + block + "\nendmodule\n"
    focused_sha = digest(focused.encode())
    positive_closure = semantic_closure(focused)
    with tempfile.TemporaryDirectory(prefix="v33-lc18-pe7-scope-") as temp:
        root = Path(temp)
        positive = compile_case(
            args.iverilog.resolve(), root, "positive", focused
        )
        typo = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_typo_consumer",
            focused.replace(
                ".IGA_PE[7].u_IGA_PE",
                ".IGA_PE[7].u_IGA_PX",
                1,
            ),
        )
        deleted = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_declaration",
            focused.replace(
                "longint unsigned return_obs_lp_pe7_write;\n", "", 1
            ),
        )
        syntax = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_task_end",
            focused.replace("    endtask", "    end", 1),
        )
        update_mutant_source = focused.replace(
            "if (lp_pe7_read) return_obs_lp_pe7_read++;", "", 1
        )
        update_mutant = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_qualified_update",
            update_mutant_source,
        )
        update_mutant_closure = semantic_closure(update_mutant_source)

    if positive["exit_code"] != 0:
        errors.append("focused positive compile failed")
    if not positive_closure["valid"]:
        errors.append("positive semantic closure failed")
    if any(
        case["exit_code"] == 0 for case in (typo, deleted, syntax)
    ):
        errors.append("one or more syntax/scope negatives did not fail")
    if update_mutant_closure["valid"]:
        errors.append("deleted qualified update did not fail semantic closure")
    frontend = subprocess.run(
        [str(args.iverilog.resolve()), "-V"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    report = {
        "schema": "node0004-v33-lc18-pe7-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "package_local_hdl_gate": {
            "applicable": True,
            "rule_id": (
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-"
                "HDL-SYNTAX-SCOPE-POSITIVE-001"
            ),
            "exact_members": [
                {
                    "path": (
                        f"{INSTALL_NAME}/tb_probe/"
                        "native_return_observer.svh"
                    ),
                    "bytes": len(observer_payload),
                    "sha256": digest(observer_payload),
                    "role": "package-local read-only observer",
                }
            ],
            "focused_harness_sha256": focused_sha,
            "closure": {
                "scope": (
                    "v33 changed physical LC17/LC18/PE7 to "
                    "WRITE_STREAM0 input1 counters and boundary records"
                ),
                "declared": len(COUNTERS),
                "used": len(COUNTERS),
                "unresolved": 0 if positive_closure["valid"] else 1,
                "ownerless_state": 0 if positive_closure["valid"] else 1,
            },
            "negative_controls": {
                "delete_declaration_fail_closed": (
                    deleted["exit_code"] != 0
                ),
                "misspell_consumer_use_fail_closed": typo["exit_code"] != 0,
                "delete_reset_or_update_fail_closed": (
                    not update_mutant_closure["valid"]
                ),
            },
            "claim_boundary": (
                "focused exact v33 added observer syntax/scope/state "
                "ownership and direct active-leaf existence; not full-design "
                "VCS elaboration or server RTL identity"
            ),
            "pass": not errors,
        },
        "active_local_rtl": active,
        "frontend": {
            "path": str(args.iverilog.resolve()),
            "version_exit": frontend.returncode,
            "version_stdout": frontend.stdout,
            "version_stderr": frontend.stderr,
        },
        "positive": positive,
        "positive_semantic_closure": positive_closure,
        "negative_typo_consumer": typo,
        "negative_deleted_declaration": deleted,
        "negative_missing_task_end": syntax,
        "negative_deleted_qualified_update": update_mutant,
        "negative_deleted_qualified_update_semantic_closure": (
            update_mutant_closure
        ),
        "all_negative_controls_fail_closed": (
            all(case["exit_code"] != 0 for case in (typo, deleted, syntax))
            and not update_mutant_closure["valid"]
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
