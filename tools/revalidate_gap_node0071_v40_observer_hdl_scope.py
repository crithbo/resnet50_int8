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


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v40_lc_supply_conservation_diag"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
DECL_ANCHOR = (
    "    // v38: owner-clock LC/memory/buffer conservation "
    "information-gain slice."
)
DECL_END = (
    "    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic."
)
SAMPLER_ANCHOR = (
    "    // v38 sampler: exact owner-clock qualified FIFO accepts "
    "and surface edges."
)
SAMPLER_END = (
    "    // v33 sampler: qualified input accepts and FIFO accepts only."
)
SUMMARY_ANCHOR = "                    if (return_obs_lcsc_enabled) begin"
SUMMARY_END = "                    if (return_obs_bq_enabled) begin"
FIFO = ROOT / "NDP_copy01/rtl/utils/FIFO/FIFO.sv"
FIFO_SHA256 = (
    "7c1efe3e911caeb304a8b30a6f657b2ff92ec163e797f320573422ca3f9b5722"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
CLOUD_BUFFER_TEXT_SHA256 = (
    "e47c77d8aec2eb350d81ef2a43b72923869dd4b39a41ebc91e23a508e7ab58aa"
)
CLOUD_RD_TEXT_SHA256 = (
    "20cafa837ad80f8f01a33b4ae2323b3c515a13b0a2e66b5f2104c4065547824c"
)


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def run(argv: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        argv, cwd=cwd, text=True, capture_output=True, check=False
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stdout_sha256": sha_bytes(completed.stdout.encode()),
        "stderr_sha256": sha_bytes(completed.stderr.encode()),
    }


def section(text: str, start: str, end: str) -> str:
    left = text.find(start)
    right = text.find(end, left + len(start))
    if left < 0 or right <= left:
        raise ValueError(f"section absent: {start}")
    return text[left:right]


def replace_in_section(
    text: str, start: str, end: str, old: str, new: str
) -> str:
    focused = section(text, start, end)
    if focused.count(old) < 1:
        raise ValueError(f"focused replacement count differs: {old}")
    return text.replace(focused, focused.replace(old, new, 1), 1)


def consumer_ledger(observer: str) -> dict[str, Any]:
    declarations = section(observer, DECL_ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    summary = section(observer, SUMMARY_ANCHOR, SUMMARY_END)
    assign_lines = [
        line.strip()
        for line in declarations.splitlines()
        if line.lstrip().startswith("assign return_obs_lcsc_")
    ]
    expression_records = []
    for line in assign_lines:
        lhs, rhs = line.rstrip(";").split("=", 1)
        expression_records.append(
            {
                "lhs": lhs.replace("assign", "", 1).strip(),
                "rhs": rhs.strip(),
                "expression_sha256": sha_bytes(line.encode()),
            }
        )
    private = [
        item for item in expression_records
        if ".u_buf_ag_idx_queue." in item["rhs"]
        or ".u_mem_ag_idx_queue." in item["rhs"]
    ]
    surface = [
        item for item in expression_records if item not in private
    ]
    checks = {
        "consumer_count_36": len(expression_records) == 36,
        "private_fifo_consumer_count_20": len(private) == 20,
        "surface_consumer_count_16": len(surface) == 16,
        "surface_exact_paths": all(
            sum(token in item["rhs"] for item in surface) == 2
            for token in (
                "u_Memory_AG_Idx_Queue.mse_mem_queue_tag",
                "u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre",
                "u_Memory_AG_Idx_Queue.mse_mem_ag_tag_valid",
                "u_Memory_AG_Idx_Queue.mse_mem_ag_bp_post",
                "u_RD_Memory_AG.rd_data_chl_req_valid",
                "u_RD_Memory_AG.rd_data_chl_req_ready",
                "u_Buffer_AG_Idx_Queue.mse_buf_ag_tag_valid",
                "u_Buffer_AG_Idx_Queue.mse_buf_ag_bp_post",
            )
        ),
        "owner_clock":
            "always @(posedge u_NDP_Top_new.clk)" in sampler
            and "clk_sg" not in sampler,
        "owner_reset": "if (!u_NDP_Top_new.rst_n)" in sampler,
        "bounded":
            "return_obs_lcsc_emit_count < return_obs_lcsc_limit"
            in sampler,
        "qualified_conjunction":
            "return_obs_lcsc_req_valid_mon[lcsc_flow] &&"
            in sampler
            and "return_obs_lcsc_req_ready_mon[lcsc_flow];"
            in sampler,
        "critical_updates": all(
            token in sampler
            for token in (
                "return_obs_lcsc_bq_wr[lcsc_flow]++;",
                "return_obs_lcsc_bq_rd[lcsc_flow]++;",
                "return_obs_lcsc_mq_wr[lcsc_flow]++;",
                "return_obs_lcsc_mq_rd[lcsc_flow]++;",
                "return_obs_lcsc_req[lcsc_flow]++;",
            )
        ),
        "summary_required_records": all(
            token in summary
            for token in (
                "LC_SUPPLY_CONSERVATION_COUNTS_V1",
                "LC_SUPPLY_CONSERVATION_STATE_V1",
                "LC_SUPPLY_CONSERVATION_WITNESS_V1",
            )
        ),
        "buffer_counter_width_6":
            "logic [1:0][5:0] return_obs_lcsc_bq_count_mon;"
            in declarations,
    }
    return {
        "checks": checks,
        "valid": all(checks.values()),
        "consumer_count": len(expression_records),
        "private_fifo_consumers": private,
        "surface_consumers": surface,
    }


def package_projection(observer: str) -> str:
    declarations = section(observer, DECL_ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    summary = section(observer, SUMMARY_ANCHOR, SUMMARY_END)
    declaration_lines = []
    for line in declarations.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("`define RETURN_OBS_LCSC_")
            or stripped.startswith("`undef RETURN_OBS_LCSC_")
            or stripped.startswith("assign return_obs_lcsc_")
        ):
            continue
        declaration_lines.append(line)
    declarations = "\n".join(declaration_lines) + "\n"
    return (
        "`define MSE_MQ_INPORT_NUM 4\n"
        "`define SE_MEM_INPORT_TAG_WIDTH 32\n"
        "module v40_ndp; logic clk, rst_n; endmodule\n"
        "module v40_lcsc_focus;\n"
        "  v40_ndp u_NDP_Top_new();\n"
        "  bit return_obs_enabled, return_obs_active;\n"
        "  integer return_obs_fd;\n"
        + declarations
        + "  task automatic emit_summary(input string event_name);\n"
        + summary
        + "  endtask\n"
        + sampler
        + "\nendmodule\n"
    )


FIFO_FOCUS = r"""
module v40_fifo_focus;
  logic clk, rst_n, wr, rd;
  logic [7:0] din;
  wire [7:0] dout32, dout8;
  wire empty32, full32, empty8, full8;
  FIFO #(.FIFO_DEPTH(32), .FIFO_DATA_WIDTH(8)) u_buf_ag_idx_queue (
    .clk(clk), .rst_n(rst_n), .fifo_wr_en(wr), .fifo_wr_data(din),
    .fifo_rd_en(rd), .fifo_rd_data(dout32), .fifo_empty(empty32),
    .fifo_almost_empty(), .fifo_almost_full(), .fifo_full(full32)
  );
  FIFO #(.FIFO_DEPTH(8), .FIFO_DATA_WIDTH(8)) u_mem_ag_idx_queue (
    .clk(clk), .rst_n(rst_n), .fifo_wr_en(wr), .fifo_wr_data(din),
    .fifo_rd_en(rd), .fifo_rd_data(dout8), .fifo_empty(empty8),
    .fifo_almost_empty(), .fifo_almost_full(), .fifo_full(full8)
  );
  wire buf_add_wr = u_buf_ag_idx_queue.add_wr_ptr;
  wire buf_add_rd = u_buf_ag_idx_queue.add_rd_ptr;
  wire [5:0] buf_count = u_buf_ag_idx_queue.fifo_counter;
  wire buf_full = u_buf_ag_idx_queue.fifo_full;
  wire buf_empty = u_buf_ag_idx_queue.fifo_empty;
  wire mem_add_wr = u_mem_ag_idx_queue.add_wr_ptr;
  wire mem_add_rd = u_mem_ag_idx_queue.add_rd_ptr;
  wire [3:0] mem_count = u_mem_ag_idx_queue.fifo_counter;
  wire mem_full = u_mem_ag_idx_queue.fifo_full;
  wire mem_empty = u_mem_ag_idx_queue.fifo_empty;
endmodule
"""


def compile_projection(
    source: str, tool: Path, temp: Path, stem: str, fifo: bool = False
) -> dict[str, Any]:
    path = temp / f"{stem}.sv"
    path.write_text(source, encoding="utf-8", newline="\n")
    argv = [str(tool), "-g2012", "-tnull"]
    if fifo:
        argv.extend([str(FIFO), str(path)])
    else:
        argv.extend(["-s", "v40_lcsc_focus", str(path)])
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
    errors: list[str] = []
    target = args.target_zip.resolve()
    tool = args.iverilog.resolve()
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
                ).decode()
            )
        observer = observer_payload.decode()
        ledger = consumer_ledger(observer)
        cloud = manifest[
            "lc_supply_conservation_information_gain_contract"
        ]["cloud_rtl_authority_contract"]
        cloud_checks = {
            "approved_commit":
                cloud.get("approved_commit") == CLOUD_COMMIT,
            "buffer_cloud_text":
                cloud["gap_causal_cone_receipts"][
                    "Buffer_AG_Idx_Queue.sv"
                ]["github_dom_lf_text_sha256"]
                == CLOUD_BUFFER_TEXT_SHA256,
            "rd_cloud_text":
                cloud["gap_causal_cone_receipts"][
                    "RD_Data_Channel.sv"
                ]["github_dom_lf_text_sha256"]
                == CLOUD_RD_TEXT_SHA256,
            "fifo_exact_inherited":
                sha_path(FIFO) == FIFO_SHA256
                and cloud["gap_causal_cone_receipts"]["FIFO.sv"][
                    "changed_in_cloud_compare"
                ] is False,
        }
        version = run([str(tool), "-V"], Path.cwd())
        with tempfile.TemporaryDirectory(prefix="gap-v40-hdl-") as raw:
            temp = Path(raw)
            projection = package_projection(observer)
            package_positive = compile_projection(
                projection, tool, temp, "package_positive"
            )
            fifo_positive = compile_projection(
                FIFO_FOCUS, tool, temp, "fifo_positive", fifo=True
            )
            mutations: list[tuple[str, str, bool]] = [
                (
                    "package_declaration_removed",
                    package_projection(
                        observer.replace(
                            "    longint unsigned "
                            "return_obs_lcsc_mq_wr [0:1];\n",
                            "",
                            1,
                        )
                    ),
                    False,
                ),
                (
                    "actual_sampler_use_misspelled",
                    package_projection(
                        observer.replace(
                            "return_obs_lcsc_req_ready_mon[lcsc_flow]",
                            "return_obs_lcsc_req_ready_typo[lcsc_flow]",
                            1,
                        )
                    ),
                    False,
                ),
                (
                    "fifo_private_leaf_renamed",
                    FIFO_FOCUS.replace(
                        "u_buf_ag_idx_queue.add_wr_ptr",
                        "u_buf_ag_idx_queue.add_wr_typo",
                        1,
                    ),
                    True,
                ),
                (
                    "fifo_wrong_sibling_path",
                    FIFO_FOCUS.replace(
                        "u_buf_ag_idx_queue.add_rd_ptr",
                        "u_buf_ag_idx_queue_wrong.add_rd_ptr",
                        1,
                    ),
                    True,
                ),
            ]
            compile_controls = []
            for name, source, fifo_mode in mutations:
                compiled = compile_projection(
                    source, tool, temp, name, fifo=fifo_mode
                )
                compile_controls.append(
                    {
                        "name": name,
                        "exit_code": compiled["exit_code"],
                        "failed_closed": compiled["exit_code"] != 0,
                        "stderr_sha256": compiled["stderr_sha256"],
                    }
                )
            semantic_controls = []
            for name, mutated in (
                (
                    "critical_update_removed",
                    observer.replace(
                        "return_obs_lcsc_mq_wr[lcsc_flow]++;",
                        "/* required update removed */",
                        1,
                    ),
                ),
                (
                    "owner_clock_changed",
                    replace_in_section(
                        observer,
                        SAMPLER_ANCHOR,
                        SAMPLER_END,
                        "always @(posedge u_NDP_Top_new.clk)",
                        "always @(posedge u_NDP_Top_new.clk_sg)",
                    ),
                ),
                (
                    "actual_surface_consumer_misspelled",
                    replace_in_section(
                        observer,
                        DECL_ANCHOR,
                        DECL_END,
                        "u_RD_Memory_AG.rd_data_chl_req_ready",
                        "u_RD_Memory_AG.rd_data_chl_req_typo",
                    ),
                ),
            ):
                checked = consumer_ledger(mutated)
                semantic_controls.append(
                    {
                        "name": name,
                        "failed_closed": not checked["valid"],
                        "failed_checks": [
                            key for key, value in checked["checks"].items()
                            if not value
                        ],
                    }
                )
        checks = {
            "frontend_available": version["exit_code"] == 0,
            "exact_final_consumer_ledger": ledger["valid"],
            "cloud_causal_cone_receipts": all(cloud_checks.values()),
            "package_local_projection_compiles":
                package_positive["exit_code"] == 0,
            "actual_fifo_private_xmr_compiles":
                fifo_positive["exit_code"] == 0,
            "compile_negatives_fail_closed": all(
                item["failed_closed"] for item in compile_controls
            ),
            "semantic_negatives_fail_closed": all(
                item["failed_closed"] for item in semantic_controls
            ),
        }
        passed = all(checks.values())
        if not passed:
            errors.extend(
                key for key, value in checks.items() if not value
            )
        result = {
            "schema":
                "gap-node0071-v40-focused-observer-hdl-scope-v1",
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
            "cloud_causal_cone_checks": cloud_checks,
            "package_local_positive": package_positive,
            "actual_fifo_private_xmr_positive": fifo_positive,
            "compile_negative_controls": compile_controls,
            "semantic_negative_controls": semantic_controls,
            "full_design_elaboration_claimed": False,
            "claim_boundary": (
                "Exact final v40 changed declarations/sampler/summary, all "
                "36 actual consumer expressions, exact unchanged FIFO module "
                "private leaves, cloud-current Buffer_AG/RD width receipts, "
                "and focused name resolution only. Production hierarchy and "
                "VCS elaboration remain formal server-return evidence."
            ),
            "errors": errors,
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {
            "schema":
                "gap-node0071-v40-focused-observer-hdl-scope-v1",
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
