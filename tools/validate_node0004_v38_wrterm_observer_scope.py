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


INSTALL_NAME = "r5_n4_hw_v40_wrterm_diag"
BEGIN = "    // v38 WRTERM_ACTUAL_CONSUMER_BEGIN"
END = "    // v38 WRTERM_ACTUAL_CONSUMER_END"
RTL_OWNERS = {
    "u_NDP_Top_new": "NDP_copy01/rtl/NDP_Top.sv",
    "u_wr_chl_queue": "NDP_copy01/rtl/utils/FIFO/FIFO.sv",
    "u_WR_Data_Channel": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    ),
    "u_RD_Buffer_AG": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    ),
    "u_Memory_AG_Idx_Queue": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_AG_Idx_Queue.sv"
    ),
}
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[0-9]+\])?)+"
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
        "wrterm_focus_top",
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
module fifo_stub; logic [63:0] fifo_counter; endmodule
module wr_data_channel_stub;
  logic wr_chl_queue_wr_en, wr_chl_queue_full;
  logic wr_chl_queue_rd_en, wr_chl_queue_empty;
  logic wr_data_chl_prepared_data_wr_hs;
  logic wr_data_chl_hold_data_vld;
  logic [63:0] wr_data_chl_prepared_data_cnt;
  fifo_stub u_wr_chl_queue();
endmodule
module rd_buffer_ag_stub;
  logic buf_ag_ob_wr_en, buf_ag_ob_full;
  logic buf_ag_ob_rd_en, buf_ag_ob_empty;
  logic buf_ag_idx_last_bit;
  logic [63:0] buf_ag_idx_last_index;
  logic mse2buf_last;
  logic [63:0] mse2buf_last_index;
  logic [63:0] buf_ag_ob_cnt;
endmodule
module memory_ag_idx_queue_stub;
  logic [63:0] mse_mem_queue_bp_pre;
  logic [63:0] mem_idx_valid_same_gotten_masked;
endmodule
module memory_wr_stream_engine_stub;
  wr_data_channel_stub u_WR_Data_Channel();
  rd_buffer_ag_stub u_RD_Buffer_AG();
  memory_ag_idx_queue_stub u_Memory_AG_Idx_Queue();
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
  logic clk_db, rst_n_db;
  generate
    for (genvar g=0;g<1;g++) begin : slice_with_datahub_mc_group_gen
      group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module wrterm_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled;
  bit return_obs_active;
  integer return_obs_fd;
'''


def suffix() -> str:
    return r'''
  initial begin
    #1;
    return_obs_write_wrterm_state("FOCUS");
  end
endmodule
'''


def owner_for(expression: str) -> str | None:
    if ".u_wr_chl_queue." in expression:
        return "u_wr_chl_queue"
    for owner in RTL_OWNERS:
        if f".{owner}." in expression:
            return owner
    if expression in ("u_NDP_Top_new.clk_db", "u_NDP_Top_new.rst_n_db"):
        return "u_NDP_Top_new"
    return None


def leaf_for(expression: str) -> str:
    match = re.search(r"\.([A-Za-z_][A-Za-z0-9_]*)"
                      r"(?:\[[0-9]+\])?$", expression)
    return match.group(1) if match else ""


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
    if observer.count(BEGIN) != 1 or observer.count(END) != 1:
        errors.append("actual-consumer markers differ")
        block = ""
        start_line = 0
    else:
        begin = observer.index(BEGIN)
        end = observer.index(END) + len(END)
        block = observer[begin:end]
        start_line = observer[:begin].count("\n") + 1

    occurrences: list[dict[str, Any]] = []
    for match in XMR_RE.finditer(block):
        expression = match.group(0)
        owner = owner_for(expression)
        leaf = leaf_for(expression)
        line = start_line + block[:match.start()].count("\n")
        occurrences.append(
            {
                "expression": expression,
                "expression_sha256": digest(expression.encode("utf-8")),
                "source_line": line,
                "owner_role": owner,
                "leaf": leaf,
                "classification": "external_xmr",
            }
        )
    unique: dict[str, dict[str, Any]] = {}
    for item in occurrences:
        unique.setdefault(item["expression"], item)
    unresolved = [
        item for item in unique.values() if item["owner_role"] is None
    ]
    if unresolved:
        errors.append("unclassified actual consumers")

    owner_receipts: dict[str, Any] = {}
    missing_owner_leaves: list[dict[str, str]] = []
    for owner, relative in RTL_OWNERS.items():
        path = project / relative
        text = path.read_text(encoding="utf-8")
        owned = [
            item for item in unique.values() if item["owner_role"] == owner
        ]
        missing = [item["leaf"] for item in owned if item["leaf"] not in text]
        owner_receipts[owner] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": digest(path.read_bytes()),
            "consumers": len(owned),
            "missing_leaf_tokens": missing,
        }
        missing_owner_leaves += [
            {"owner": owner, "leaf": leaf} for leaf in missing
        ]
    if missing_owner_leaves:
        errors.append("actual consumer leaf absent from current RTL owner")

    closure = {
        "actual_consumer_count_nonzero": bool(unique),
        "actual_consumer_occurrences": len(occurrences),
        "actual_consumer_unique": len(unique),
        "actual_consumer_classified": len(unique) - len(unresolved),
        "actual_consumer_uncovered": len(unresolved),
        "package_local_declarations_present": all(
            token in block
            for token in (
                "bit return_obs_wt_enabled;",
                "bit return_obs_wt_after_desc_terminal;",
                "task automatic return_obs_write_wrterm_state",
            )
        ),
        "direct_canonical_hook": observer.count(
            'return_obs_write_wrterm_state("DIAG_DECISION");'
        )
        == 1,
        "state_not_canonical_progress": (
            "return_hang_diag_current_progress" not in block
        ),
    }
    if not all(
        value if isinstance(value, bool) else True
        for value in closure.values()
    ):
        errors.append("package-local closure differs")
    if closure["actual_consumer_uncovered"] != 0:
        errors.append("actual consumer coverage incomplete")

    full_source = prefix() + block + suffix()
    selected = next(
        (
            item
            for item in unique.values()
            if item["leaf"] == "wr_chl_queue_empty"
        ),
        None,
    )
    if selected is None:
        errors.append("negative-control consumer not found")
        typo_source = full_source
    else:
        typo_source = full_source.replace(
            selected["expression"],
            selected["expression"] + "_actual_consumer_typo",
            1,
        )
    with tempfile.TemporaryDirectory(prefix="v38-wrterm-scope-") as temp:
        root = Path(temp)
        positive = compile_case(
            args.iverilog.resolve(), root, "positive", full_source
        )
        typo_consumer = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_actual_consumer_typo",
            typo_source,
        )
        missing_state = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_state_owner",
            full_source.replace(
                "bit return_obs_wt_after_desc_terminal;",
                "// deleted actual state owner",
                1,
            ),
        )
        missing_gate = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_enable_owner",
            full_source.replace(
                "bit return_obs_wt_enabled;",
                "// deleted actual enable owner",
                1,
            ),
        )
        missing_task = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_task_consumer_typo",
            full_source.replace(
                "return_obs_write_wrterm_state(\"FOCUS\")",
                "return_obs_write_wrterm_state_actual_typo(\"FOCUS\")",
                1,
            ),
        )
    negatives = {
        "actual_consumer_typo_fail_closed": typo_consumer["exit_code"] != 0,
        "missing_state_owner_fail_closed": missing_state["exit_code"] != 0,
        "missing_enable_owner_fail_closed": missing_gate["exit_code"] != 0,
        "task_consumer_typo_fail_closed": missing_task["exit_code"] != 0,
    }
    if positive["exit_code"] != 0:
        errors.append("focused actual-consumer positive compile failed")
    if not all(negatives.values()):
        errors.append("actual-consumer negative did not fail closed")

    report = {
        "schema": "node0004-v38-wrterm-actual-consumer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "rule_id": (
            "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-"
            "ACTUAL-CONSUMER-001"
        ),
        "exact_final_compiled_hdl": {
            "path": member,
            "bytes": len(payload),
            "sha256": digest(payload),
            "consumer_span": {
                "begin_marker": BEGIN.strip(),
                "end_marker": END.strip(),
                "start_line": start_line,
                "end_line": start_line + block.count("\n"),
                "sha256": digest(block.encode("utf-8")),
            },
        },
        "actual_consumer_coverage": {
            "occurrence_count": len(occurrences),
            "unique_count": len(unique),
            "classified_count": len(unique) - len(unresolved),
            "uncovered_count": len(unresolved),
            "consumers": list(unique.values()),
        },
        "owner_receipts": owner_receipts,
        "closure": closure,
        "frontend_positive": positive,
        "negative_controls": {
            **negatives,
            "mutated_actual_consumer": selected,
            "details": {
                "actual_consumer_typo": typo_consumer,
                "missing_state_owner": missing_state,
                "missing_enable_owner": missing_gate,
                "task_consumer_typo": missing_task,
            },
        },
        "all_negative_controls_fail_closed": all(negatives.values()),
        "claim_boundary": (
            "The focused wrapper models only external XMR owners. It does not "
            "supply package-local observer declarations, state, update logic or "
            "task consumers. Coverage inventory is parsed from the exact final "
            "compiled HDL span, not from an expected list or mock."
        ),
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
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
