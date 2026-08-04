from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v29_datahub_drain_diag"
MARKER = "    // v29: qualified MSE4 local write queue -> arbiter -> bank crossbar drain."
ACTIVE_FILES = {
    "local_wr_req_queue": (
        "NDP_copy01/rtl/Datahub/Request_Queue/local_wr_req_queue.sv"
    ),
    "local_req_full_channel": (
        "NDP_copy01/rtl/Datahub/Request_Queue/local_req_full_channel.sv"
    ),
    "datahub_req_crossbar": (
        "NDP_copy01/rtl/Datahub/Datahub_Req_Crossbar/"
        "datahub_req_crossbar.sv"
    ),
    "datahub_top": "NDP_copy01/rtl/Datahub/datahub_top.sv",
}
LEAVES = {
    "local_wr_req_queue": (
        "req_fifo_wr_en",
        "data_fifo_wr_en",
        "hub_wr_req_valid",
        "hub_wr_req_ready",
        "hub_wr_req_addr",
        "req_fifo_full",
    ),
    "local_req_full_channel": ("arb_req_ready",),
    "datahub_req_crossbar": (
        "total_req_addr_bank",
        "total_req_match",
        "total_req_ready",
        "req_cb_ready",
    ),
    "datahub_top": (
        "local_req_full_channels",
        "u_datahub_req_crossbar",
    ),
}


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compile_case(
    iverilog: Path, root: Path, name: str, source: str
) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    result = subprocess.run(
        [
            str(iverilog),
            "-g2012",
            "-s",
            "datahub_focus_top",
            "-o",
            str(output_path),
            str(source_path),
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def prefix() -> str:
    return r"""
`timescale 1ns/1ps
module local_wr_req_queue_stub;
  logic req_fifo_wr_en, data_fifo_wr_en;
  logic hub_wr_req_valid, hub_wr_req_ready, req_fifo_full;
  logic [20:0] hub_wr_req_addr;
endmodule
module local_req_full_channel_stub;
  logic [1:0] arb_req_ready;
  local_wr_req_queue_stub u_local_wr_req_queue();
endmodule
module datahub_req_crossbar_stub;
  logic [10:0][1:0] total_req_addr_bank;
  logic [3:0][10:0] total_req_match;
  logic [3:0][10:0] total_req_ready;
  logic [3:0] req_cb_ready;
endmodule
module datahub_top_stub;
  generate
    for (genvar c = 0; c < 10; c++) begin : local_req_full_channels
      if (1) begin : wr_en
        local_req_full_channel_stub u_local_req_full_channel();
      end
    end
  endgenerate
  datahub_req_crossbar_stub u_datahub_req_crossbar();
endmodule
module datahub_wrapper_stub;
  datahub_top_stub u_datahub_top();
endmodule
module group_stub;
  generate
    for (genvar s = 0; s < 1; s++) begin : slice_group_gen
      datahub_wrapper_stub u_datahub_top_wrapper();
    end
  endgenerate
endmodule
module ndp_stub;
  logic clk_sg, rst_n_sg;
  generate
    for (genvar g = 0; g < 1; g++) begin : slice_with_datahub_mc_group_gen
      group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module datahub_focus_top;
  ndp_stub u_NDP_Top_new();
  bit return_obs_enabled;
  bit return_obs_active;
  integer return_obs_fd;
"""


def semantic_closure(source: str) -> dict[str, Any]:
    declaration = "longint unsigned return_obs_dh_addr_in_8;"
    reset_or_initial = "return_obs_dh_addr_in_8 = 0;"
    qualified_update = (
        "if (dh_addr_in_8) return_obs_dh_addr_in_8++;"
    )
    consumer = "return_obs_dh_addr_in_8,"
    checks = {
        "declaration": source.count(declaration) == 1,
        "reset_or_initialization": source.count(reset_or_initial) >= 2,
        "qualified_update": source.count(qualified_update) == 1,
        "consumer_use": source.count(consumer) >= 1,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "declared": int(checks["declaration"]),
        "used": int(checks["consumer_use"]),
        "unresolved": 0 if all(checks.values()) else 1,
        "ownerless_state": 0 if all(checks.values()) else 1,
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
        observer = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        ).decode("utf-8")
    if observer.count(MARKER) != 1:
        errors.append("v29 marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER) :]
    active: dict[str, Any] = {}
    for module, relative in ACTIVE_FILES.items():
        path = project / relative
        text = path.read_text(encoding="utf-8")
        checks = {leaf: leaf in text for leaf in LEAVES[module]}
        active[module] = {
            "path": relative,
            "sha256": digest(path.read_bytes()),
            "leaf_checks": checks,
        }
        if not all(checks.values()):
            errors.append(f"{module} active leaf closure failed")
    focused = prefix() + block + "\nendmodule\n"
    positive_closure = semantic_closure(focused)
    with tempfile.TemporaryDirectory(prefix="v29-datahub-scope-") as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog.resolve(), root, "positive", focused)
        typo = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_typo_leaf",
            focused.replace(".hub_wr_req_addr", ".hub_wr_req_adrx", 1),
        )
        deleted = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_deleted_declaration",
            focused.replace(
                "logic hub_wr_req_valid, hub_wr_req_ready, req_fifo_full;",
                "logic hub_wr_req_valid, req_fifo_full;",
                1,
            ),
        )
        missing_task = compile_case(
            args.iverilog.resolve(),
            root,
            "negative_missing_task_end",
            focused.replace("    endtask", "    end", 1),
        )
        update_mutant_source = focused.replace(
            "if (dh_addr_in_8) return_obs_dh_addr_in_8++;",
            "",
            1,
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
    syntax_negatives = (typo, deleted, missing_task)
    if any(case["exit_code"] == 0 for case in syntax_negatives):
        errors.append("one or more focused negatives did not fail")
    if update_mutant_closure["valid"]:
        errors.append("deleted qualified update did not fail semantic closure")
    frontend_version = subprocess.run(
        [str(args.iverilog.resolve()), "-V"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    package_local_gate = {
        "applicable": True,
        "rule_id": (
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-"
            "SYNTAX-SCOPE-POSITIVE-001"
        ),
        "exact_members": [
            {
                "path": (
                    f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
                ),
                "bytes": len(observer.encode()),
                "sha256": digest(observer.encode()),
                "role": "package-local read-only observer",
            }
        ],
        "frontend": {
            "name": "iverilog",
            "version_exit": frontend_version.returncode,
            "version": (
                frontend_version.stdout + frontend_version.stderr
            ).strip(),
            "command": (
                f"{args.iverilog.resolve()} -g2012 -s datahub_focus_top "
                "-o <output> <focused-source>"
            ),
            "cwd": str(project),
            "exit": positive["exit_code"],
            "coverage": "focused",
        },
        "focused_harness_sha256": digest(focused.encode()),
        "specializations": [
            (
                "external DUT hierarchy and packed signal types are modeled; "
                "the exact v29 observer block is not rewritten"
            )
        ],
        "closure": {
            "scope": (
                "v29 declarations/reset/qualified updates/consumer uses plus "
                "direct external XMR name closure"
            ),
            **positive_closure,
        },
        "negative_controls": {
            "delete_declaration_fail_closed": deleted["exit_code"] != 0,
            "misspell_consumer_use_fail_closed": typo["exit_code"] != 0,
            "delete_reset_or_update_fail_closed": (
                update_mutant_closure["valid"] is False
            ),
        },
        "claim_boundary": (
            "v29-added DataHub drain observer HDL only; server VCS remains "
            "the full-design compile/elaboration authority"
        ),
        "pass": (
            positive["exit_code"] == 0
            and positive_closure["valid"]
            and all(case["exit_code"] != 0 for case in syntax_negatives)
            and update_mutant_closure["valid"] is False
        ),
    }
    report = {
        "schema": "node0004-v29-datahub-observer-scope-v1",
        "valid": not errors,
        "errors": errors,
        "zip": {
            "path": str(args.zip.resolve()),
            "sha256": digest(args.zip.resolve().read_bytes()),
        },
        "observer_sha256": digest(observer.encode()),
        "active_rtl": active,
        "focused_compatible_frontend": {
            "tool": str(args.iverilog.resolve()),
            "positive": positive,
            "negative_typo_leaf": typo,
            "negative_deleted_declaration": deleted,
            "negative_missing_task_end": missing_task,
            "negative_deleted_qualified_update": {
                **update_mutant,
                "semantic_closure": update_mutant_closure,
                "validator_fail_closed": (
                    update_mutant_closure["valid"] is False
                ),
            },
        },
        "semantic_closure": positive_closure,
        "package_local_hdl_gate": package_local_gate,
        "all_negative_controls_fail_closed": (
            all(case["exit_code"] != 0 for case in syntax_negatives)
            and update_mutant_closure["valid"] is False
        ),
        "scope": (
            "only the v29-added DataHub drain observer HDL and directly "
            "referenced active RTL leaves"
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
