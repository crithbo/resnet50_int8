from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v47_stage_transition_rootfix"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
MARKER = "    // v46: mask-wide stage-transition information-gain observer."
RTL_ROOT = ROOT / "NDP_copy01/rtl"
GLOBAL_MANAGER = RTL_ROOT / "Global/global_exec_manager.sv"
GLOBAL_CTRL = RTL_ROOT / "Global/global_ctrl.sv"
TOP = RTL_ROOT / "NDP_Top_phy.sv"
SLICE_MANAGER = RTL_ROOT / "Slice/Slice_Execution_Manager.sv"
FIFO = RTL_ROOT / "utils/FIFO/FIFO.sv"
FIFO_128TO64 = RTL_ROOT / "Global/FIFO_128to64.sv"
INCLUDES = RTL_ROOT / "includes"
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def run(argv: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_sha256": sha_bytes(completed.stdout.encode()),
        "stderr_sha256": sha_bytes(completed.stderr.encode()),
    }


def focused(text: str) -> str:
    at = text.find(MARKER)
    if at < 0:
        raise ValueError("v46 observer marker absent")
    return text[at:]


def consumer_ledger(observer: str) -> dict[str, Any]:
    body = focused(observer)
    expected_assignments = {
        "return_obs_gst_valid_mon":
            "u_NDP_Top_new.gexec2slice_valid_gc",
        "return_obs_gst_ready_mon":
            "u_NDP_Top_new.slice2gexec_ready_gc",
        "return_obs_gst_local_empty_mon":
            "u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.local_queue_empty",
        "return_obs_gst_global_data_mon":
            "u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.global_queue_data_out",
        "return_obs_gst_global_empty_mon":
            "u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.global_queue_empty",
        "return_obs_gst_global_rd_mon":
            "u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.global_queue_rd_en",
        "return_obs_gst_mask_match_mon":
            "u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.mask_match",
        "return_obs_gst_config_match_mon":
            "u_NDP_Top_new.u_global_ctrl.u_global_exec_manager.config_match",
        "return_obs_gst_gconfig_ready_mon":
            "u_NDP_Top_new.u_global_ctrl.gconfig2gexec_ready",
        "return_obs_gst_fetch_finish_mon":
            "u_NDP_Top_new.u_global_ctrl.exec_fetch_finish",
    }
    assignment_checks = {
        name: (
            f"assign {name} =" in body
            and expression in body
        )
        for name, expression in expected_assignments.items()
    }
    checks = {
        "all_direct_consumers_present": all(assignment_checks.values()),
        "owner_clock_exact":
            "always @(posedge u_NDP_Top_new.clk)" in body,
        "owner_reset_exact": "if (!u_NDP_Top_new.rst_n)" in body,
        "selected_mask_from_exact_instruction_bits":
            "[3 +: `GLB_SLICE_NUM]" in body,
        "qualified_stage_start":
            "gst_exec_rise & gst_mask" in body,
        "qualified_stage_finish":
            "gst_finish_rise & gst_mask" in body,
        "stable_level_not_progress":
            "gst_changed = gst_surface != return_obs_gst_prev_surface;"
            in body,
        "rate_limited_heartbeat":
            "return_obs_gst_edge % return_obs_gst_heartbeat_cycles"
            in body,
        "bounded_records":
            "return_obs_gst_emit_count < 128" in body,
        "critical_updates": all(
            token in body
            for token in (
                "return_obs_gst_edge++;",
                "return_obs_gst_exec_seen = gst_exec_rise & gst_mask;",
                "return_obs_gst_exec_seen |= gst_exec_rise & gst_mask;",
                "return_obs_gst_finish_seen |= gst_finish_rise & gst_mask;",
                "return_obs_gst_prev_surface = gst_surface;",
                "return_obs_gst_prev_exec = return_obs_gst_exec_level_mon;",
                "return_obs_gst_prev_finish = return_obs_gst_finish_level_mon;",
            )
        ),
        "required_record":
            "GEXEC_STAGE_TRANSITION_STATE_V1" in body,
        "read_only_no_force":
            not any(
                token in body
                for token in ("force ", "release ", "<= u_NDP_Top_new")
            ),
    }
    private = {
        name: value
        for name, value in expected_assignments.items()
        if ".u_global_exec_manager." in value
    }
    exported = {
        name: value
        for name, value in expected_assignments.items()
        if name not in private
    }
    return {
        "checks": checks,
        "assignment_checks": assignment_checks,
        "private_xmr_consumers": private,
        "exported_interconnect_consumers": exported,
        "valid": all(checks.values()) and all(assignment_checks.values()),
    }


def logic_projection(observer: str) -> str:
    body = focused(observer)
    state_at = body.find("    bit return_obs_gst_enabled;")
    if state_at < 0:
        raise ValueError("v46 state declaration absent")
    logic = body[state_at:]
    logic = logic.replace("u_NDP_Top_new.clk", "clk")
    logic = logic.replace("u_NDP_Top_new.rst_n", "rst_n")
    return (
        "`define GLB_SLICE_NUM 16\n"
        "`define EXEC_BIT_WIDTH 64\n"
        "module v46_stage_transition_focus;\n"
        "  logic clk, rst_n;\n"
        "  bit return_obs_enabled;\n"
        "  integer return_obs_fd;\n"
        "  integer return_obs_plusarg_status;\n"
        "  logic [`GLB_SLICE_NUM-1:0] return_obs_gst_valid_mon;\n"
        "  logic [`GLB_SLICE_NUM-1:0] return_obs_gst_ready_mon;\n"
        "  logic [`GLB_SLICE_NUM-1:0] return_obs_gst_local_empty_mon;\n"
        "  logic [`GLB_SLICE_NUM-1:0] return_obs_gst_exec_level_mon;\n"
        "  logic [`GLB_SLICE_NUM-1:0] return_obs_gst_finish_level_mon;\n"
        "  logic [`EXEC_BIT_WIDTH-1:0] return_obs_gst_global_data_mon;\n"
        "  logic return_obs_gst_global_empty_mon;\n"
        "  logic return_obs_gst_global_rd_mon;\n"
        "  logic return_obs_gst_mask_match_mon;\n"
        "  logic return_obs_gst_config_match_mon;\n"
        "  logic return_obs_gst_gconfig_ready_mon;\n"
        "  logic return_obs_gst_fetch_finish_mon;\n"
        + logic
        + "\nendmodule\n"
    )


MANAGER_FOCUS = r"""
`include "NDP_Parameters.svh"
module v46_global_manager_focus;
  logic clk, rst_n, global_sca_start, global_sca_reset;
  logic [`LD_EXEC_ADDR_WIDTH-1:0] init_exec_base_addr;
  logic [`EXEC_LEN_WIDTH-1:0] init_exec_inst_length;
  wire [`EXEC_LEN_WIDTH-1:0] exec_fetch_cnt;
  wire exec_fetch_cnt_overflow, exec_fetch_finish;
  wire [`GLB_SLICE_NUM-1:0] exec_slice_finish;
  logic [`EXEC_BIT_WIDTH*2-1:0] mem2gexec_rdata;
  logic mem2gexec_rvalid, mem2gexec_rlast, mem2gexec_arready;
  wire gexec2mem_rready;
  wire [`LD_EXEC_ADDR_WIDTH-1:0] gexec2mem_araddr;
  wire [`LD_EXEC_LEN_WIDTH-1:0] gexec2mem_arlen;
  wire gexec2mem_arvalid;
  wire [`GLB_SLICE_NUM-1:0][`EXEC_BIT_WIDTH-1:0] gexec2slice_data;
  wire [`GLB_SLICE_NUM-1:0] gexec2slice_valid;
  logic [`GLB_SLICE_NUM-1:0] slice2gexec_ready;
  wire [`LD_CFG_ADDR_WIDTH-1:0] gexec2gconfig_base_addr;
  wire [`LD_CFG_LEN_WIDTH-1:0] gexec2gconfig_len;
  wire [`GLB_SLICE_NUM-1:0] slice2gconfig_mask;
  wire gexec2gconfig_valid;
  logic gconfig2gexec_ready;

  global_exec_manager u_global_exec_manager (
    .clk(clk), .rst_n(rst_n),
    .init_exec_base_addr(init_exec_base_addr),
    .init_exec_inst_length(init_exec_inst_length),
    .global_sca_start(global_sca_start),
    .global_sca_reset(global_sca_reset),
    .exec_fetch_cnt(exec_fetch_cnt),
    .exec_fetch_cnt_overflow(exec_fetch_cnt_overflow),
    .exec_fetch_finish(exec_fetch_finish),
    .exec_slice_finish(exec_slice_finish),
    .mem2gexec_rdata(mem2gexec_rdata),
    .mem2gexec_rvalid(mem2gexec_rvalid),
    .gexec2mem_rready(gexec2mem_rready),
    .mem2gexec_rlast(mem2gexec_rlast),
    .gexec2mem_araddr(gexec2mem_araddr),
    .gexec2mem_arlen(gexec2mem_arlen),
    .gexec2mem_arvalid(gexec2mem_arvalid),
    .mem2gexec_arready(mem2gexec_arready),
    .gexec2slice_data(gexec2slice_data),
    .gexec2slice_valid(gexec2slice_valid),
    .slice2gexec_ready(slice2gexec_ready),
    .gexec2gconfig_base_addr(gexec2gconfig_base_addr),
    .gexec2gconfig_len(gexec2gconfig_len),
    .slice2gconfig_mask(slice2gconfig_mask),
    .gexec2gconfig_valid(gexec2gconfig_valid),
    .gconfig2gexec_ready(gconfig2gexec_ready)
  );
  wire [`GLB_SLICE_NUM-1:0] local_empty =
      u_global_exec_manager.local_queue_empty;
  wire [`EXEC_BIT_WIDTH-1:0] global_data =
      u_global_exec_manager.global_queue_data_out;
  wire global_empty = u_global_exec_manager.global_queue_empty;
  wire global_rd = u_global_exec_manager.global_queue_rd_en;
  wire mask_match = u_global_exec_manager.mask_match;
  wire config_match = u_global_exec_manager.config_match;
endmodule
"""


def compile_source(
    source: str,
    tool: Path,
    temp: Path,
    stem: str,
    actual_manager: bool = False,
) -> dict[str, Any]:
    path = temp / f"{stem}.sv"
    path.write_text(source, encoding="utf-8", newline="\n")
    argv = [str(tool), "-g2012", "-tnull"]
    if actual_manager:
        argv.extend(
            [
                "-I",
                str(INCLUDES),
                str(FIFO),
                str(FIFO_128TO64),
                str(GLOBAL_MANAGER),
                str(path),
            ]
        )
    else:
        argv.extend(["-s", "v46_stage_transition_focus", str(path)])
    result = run(argv, temp)
    result["source_sha256"] = sha_bytes(source.encode())
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--iverilog",
        type=Path,
        default=Path(r"C:\iverilog\bin\iverilog.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    target = args.target_zip.resolve()
    tool = args.iverilog.resolve()
    errors: list[str] = []
    try:
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC differs")
            observer_payload = archive.read(
                f"{NAME}/{OBSERVER_RELATIVE}"
            )
            manifest = json.loads(
                archive.read(
                    f"{NAME}/TEST_PACKAGE_MANIFEST.json"
                ).decode("utf-8")
            )
        observer = observer_payload.decode("utf-8")
        ledger = consumer_ledger(observer)
        version = run([str(tool), "-V"], ROOT)
        target_receipts = {
            path.relative_to(ROOT).as_posix(): {
                "size_bytes": path.stat().st_size,
                "sha256": sha_path(path),
            }
            for path in (TOP, GLOBAL_CTRL, GLOBAL_MANAGER, SLICE_MANAGER)
        }
        with tempfile.TemporaryDirectory(
            prefix=".gap-v46-hdl-", dir=ROOT
        ) as raw:
            temp = Path(raw)
            projection = logic_projection(observer)
            logic_positive = compile_source(
                projection, tool, temp, "logic_positive"
            )
            manager_positive = compile_source(
                MANAGER_FOCUS,
                tool,
                temp,
                "manager_positive",
                actual_manager=True,
            )
            compile_controls = []
            for name, source, manager in (
                (
                    "declaration_removed",
                    projection.replace(
                        "  logic return_obs_gst_mask_match_mon;\n",
                        "",
                        1,
                    ),
                    False,
                ),
                (
                    "actual_use_misspelled",
                    projection.replace(
                        "return_obs_gst_gconfig_ready_mon",
                        "return_obs_gst_gconfig_ready_typo",
                        1,
                    ),
                    False,
                ),
                (
                    "private_leaf_renamed",
                    MANAGER_FOCUS.replace(
                        "u_global_exec_manager.mask_match",
                        "u_global_exec_manager.mask_match_typo",
                        1,
                    ),
                    True,
                ),
                (
                    "wrong_sibling_path",
                    MANAGER_FOCUS.replace(
                        "u_global_exec_manager.config_match",
                        "u_global_exec_manager_wrong.config_match",
                        1,
                    ),
                    True,
                ),
            ):
                receipt = compile_source(
                    source, tool, temp, name, actual_manager=manager
                )
                compile_controls.append(
                    {
                        "name": name,
                        "exit_code": receipt["exit_code"],
                        "failed_closed": receipt["exit_code"] != 0,
                        "stderr_sha256": receipt["stderr_sha256"],
                    }
                )
        semantic_controls = []
        for name, mutated in (
            (
                "critical_update_removed",
                observer.replace(
                    "return_obs_gst_finish_seen |= "
                    "gst_finish_rise & gst_mask;",
                    "/* critical finish-seen update removed */",
                    1,
                ),
            ),
            (
                "owner_clock_changed",
                observer.replace(
                    focused(observer),
                    focused(observer).replace(
                        "always @(posedge u_NDP_Top_new.clk)",
                        "always @(posedge u_NDP_Top_new.clk_sg)",
                        1,
                    ),
                    1,
                ),
            ),
            (
                "actual_consumer_misspelled",
                observer.replace(
                    "u_global_exec_manager.global_queue_rd_en",
                    "u_global_exec_manager.global_queue_rd_typo",
                    1,
                ),
            ),
        ):
            control = consumer_ledger(mutated)
            semantic_controls.append(
                {
                    "name": name,
                    "failed_closed": not control["valid"],
                    "failed_checks": [
                        key
                        for key, value in control["checks"].items()
                        if not value
                    ]
                    + [
                        key
                        for key, value in control[
                            "assignment_checks"
                        ].items()
                        if not value
                    ],
                }
            )
        checks = {
            "frontend_available": version["exit_code"] == 0,
            "exact_changed_consumer_ledger": ledger["valid"],
            "package_logic_projection_compiles":
                logic_positive["exit_code"] == 0,
            "actual_global_manager_private_xmr_compiles":
                manager_positive["exit_code"] == 0,
            "compile_negatives_fail_closed": all(
                item["failed_closed"] for item in compile_controls
            ),
            "semantic_negatives_fail_closed": all(
                item["failed_closed"] for item in semantic_controls
            ),
            "cloud_authority_current":
                manifest.get("rtl_authority", {}).get("cloud_commit")
                == CLOUD_COMMIT,
        }
        passed = all(checks.values())
        errors.extend(key for key, value in checks.items() if not value)
        result = {
            "schema":
                "gap-node0071-v47-stage-transition-focused-hdl-scope-v1",
            "status": "PASS" if passed else "FAIL",
            "pass": passed,
            "target_zip": str(target),
            "target_zip_size_bytes": target.stat().st_size,
            "target_zip_sha256": sha_path(target),
            "observer_member": f"{NAME}/{OBSERVER_RELATIVE}",
            "observer_sha256": sha_bytes(observer_payload),
            "frontend": {
                "name": "Icarus Verilog",
                "path": str(tool),
                "version": version,
            },
            "checks": checks,
            "consumer_ledger": ledger,
            "actual_target_module_receipts": target_receipts,
            "package_logic_positive": logic_positive,
            "actual_global_manager_private_xmr_positive":
                manager_positive,
            "compile_negative_controls": compile_controls,
            "semantic_negative_controls": semantic_controls,
            "full_design_elaboration_claimed": False,
            "claim_boundary": (
                "Exact final v46 changed logic, actual private leaves of "
                "cloud-current global_exec_manager, exported interconnect "
                "paths bound to exact top/global_ctrl/slice-manager bytes, "
                "and focused name resolution only. Production hierarchy and "
                "VCS elaboration remain formal server-return evidence."
            ),
            "errors": errors,
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {
            "schema":
                "gap-node0071-v47-stage-transition-focused-hdl-scope-v1",
            "status": "FAIL",
            "pass": False,
            "error": str(error),
        }
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
