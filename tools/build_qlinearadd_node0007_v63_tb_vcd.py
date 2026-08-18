#!/usr/bin/env python3
"""Build the fresh QAdd v63 package-local bounded causal-cone TB VCD package."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_qadd_n7_tailround_lanephase_v62_nfobs"
NEW = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
FAMILY = "qlinearadd_node0007"
EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437"
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{OLD}.zip"
OUT = ROOT / "outputs/qlinearadd_node0007_v63_tb_vcd_release"
BUILD = OUT / "build"
TREE = BUILD / NEW
ZIP = BUILD / f"{NEW}.zip"
BUFFER_SOURCE = ROOT / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv"
SLICE_SOURCE = ROOT / "NDP_copy01/rtl/Slice/Slice_cdc.sv"
TB_SOURCE = ROOT / "NDP_copy01/tb_NDP_Top_new_phy.sv"


ROLES = [
    "clock", "reset", "stage", "source", "producer", "request", "valid", "ready", "accept", "backpressure",
    "fifo_enqueue", "fifo_dequeue", "fifo_occupancy", "fifo_full", "fifo_empty", "outstanding", "tag", "address",
    "mask", "last", "count", "ping_pong_branch0", "ping_pong_branch1", "per_bank_ready", "per_bank_full",
    "per_bank_valid", "per_bank_owner", "barrier", "lifetime", "clear", "completion", "drain", "finish",
    "global_terminal", "selected_port", "selected_bank", "selected_lane", "internal_match", "internal_state", "output", "wdata",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": digest(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(source: Path, target: Path) -> Path:
    target.mkdir(parents=True, exist_ok=False)
    resolved = target.resolve()
    roots: set[str] = set()
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v62 source ZIP CRC failure")
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts:
                raise RuntimeError(f"unsafe member: {info.filename}")
            if member.parts:
                roots.add(member.parts[0])
            destination = (target / Path(*member.parts)).resolve()
            if destination != resolved and resolved not in destination.parents:
                raise RuntimeError(f"escaping member: {info.filename}")
        if roots != {OLD}:
            raise RuntimeError(f"unexpected ZIP roots: {sorted(roots)}")
        archive.extractall(target)
    return target / OLD


def tree_identity(root: Path, excluded: set[str] | None = None) -> dict[str, tuple[int, str]]:
    excluded = excluded or set()
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, digest(path))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    }


def files_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def deterministic_zip(tree: Path, target: Path) -> None:
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(tree.rglob("*")):
            if not path.is_file():
                continue
            member = f"{tree.name}/{path.relative_to(tree).as_posix()}"
            info = zipfile.ZipInfo(member, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)
    os.replace(temporary, target)


def zip_recheck(tree: Path, target: Path) -> dict[str, Any]:
    expected = {
        f"{tree.name}/{path.relative_to(tree).as_posix()}": (path.stat().st_size, digest(path))
        for path in sorted(tree.rglob("*")) if path.is_file()
    }
    actual: dict[str, tuple[int, str]] = {}
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("fresh ZIP CRC failure")
        for info in archive.infolist():
            if not info.is_dir():
                payload = archive.read(info)
                actual[info.filename] = (len(payload), hashlib.sha256(payload).hexdigest())
    if actual != expected:
        raise RuntimeError("exact ZIP/tree mismatch")
    return {"pass": True, "member_count": len(actual), "zip_sha256": digest(target)}


def recursive_identity_replace(root: Path) -> None:
    text_suffixes = {".json", ".md", ".txt", ".sh", ".py", ".sv", ".svh", ".v", ".vh"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in text_suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if OLD in text:
            path.write_text(text.replace(OLD, NEW), encoding="utf-8", newline="\n")


def source_span(path: Path, name: str) -> str:
    rows = path.read_text(encoding="utf-8", errors="strict").splitlines()
    matches = [row.strip() for row in rows if re.search(rf"\b{re.escape(name)}\b", row) and not row.lstrip().startswith("//")]
    if not matches:
        raise RuntimeError(f"declaration span absent: {path}:{name}")
    return hashlib.sha256(matches[0].encode("utf-8")).hexdigest()


def make_signal(
    signal_id: str,
    hierarchy: str,
    width: int,
    roles: list[str],
    source: Path,
    source_relative: str,
    declaration: str,
) -> dict[str, Any]:
    return {
        "signal_id": signal_id,
        "exact_hierarchy": hierarchy,
        "width_bits": width,
        "roles": roles,
        "source_path": source_relative,
        "source_sha256": digest(source),
        "declaration_span_sha256": source_span(source, declaration),
        "source_binding": "ACTUAL_SOURCE_NET",
        "derived_expected_equation": False,
        "drives_dut": False,
    }


def signal_contract(source_tree: Path) -> list[dict[str, Any]]:
    old = json.loads((source_tree / "contracts/server_observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
    role_map: dict[str, list[str]] = {
        "clock": ["sig_clk"], "reset": ["sig_rst_n", "sig_slice_rst"], "stage": ["sig_exec_start"],
        "source": ["sig_arm_req_valid", "sig_mrm_req_valid"], "producer": ["sig_arm_wvalid", "sig_mrm_wvalid"],
        "request": ["sig_arm_req_valid", "sig_mrm_req_valid"], "valid": ["sig_valid_buf", "sig_mrm_rvalid", "sig_arm_rvalid"],
        "ready": ["sig_mrm_r_bank_ready", "sig_arm_r_bank_ready", "sig_mrm_rreq_ready", "sig_arm_rreq_ready"],
        "accept": ["sig_arm_rd_en", "sig_mrm_rd_en", "sig_mrm_rvalid", "sig_arm_rvalid"],
        "backpressure": ["sig_mrm_req_ready", "sig_arm_req_ready", "sig_buf_rreq_ready"],
        "fifo_enqueue": ["sig_buf_wr_en", "sig_valid_wr_en"], "fifo_dequeue": ["sig_buf_rd_en"],
        "fifo_occupancy": ["sig_valid_buf"], "fifo_full": ["sig_arm_w_bank_ready", "sig_mrm_w_bank_ready"],
        "fifo_empty": ["sig_arm_r_bank_ready", "sig_mrm_r_bank_ready"], "outstanding": ["sig_valid_buf"],
        "tag": ["sig_tag_last_buf", "sig_tag_last_index_buf"], "address": ["sig_arm_req_addr", "sig_mrm_req_addr", "sig_buf_rd_addr"],
        "mask": ["sig_mrm_req_strb", "sig_buffer_mask"], "last": ["sig_mrm_last_bit", "sig_arm_last_bit", "sig_mrm_last_out"],
        "count": ["sig_global_cycle", "sig_global_start_count"], "ping_pong_branch0": ["sig_buf_rd_addr", "sig_valid_buf"],
        "ping_pong_branch1": ["sig_buf_rd_addr", "sig_valid_buf"], "per_bank_ready": ["sig_mrm_r_bank_ready", "sig_arm_r_bank_ready"],
        "per_bank_full": ["sig_mrm_w_bank_ready", "sig_arm_w_bank_ready"], "per_bank_valid": ["sig_valid_buf", "sig_valid_in"],
        "per_bank_owner": ["sig_arm_clear_reg", "sig_nrm_clear_reg"], "barrier": ["sig_nrm_rd_barrier", "sig_nrm_wr_barrier"],
        "lifetime": ["sig_global_exec_active", "sig_exec_start"], "clear": ["sig_valid_clear", "sig_arm_clear", "sig_mrm_clear"],
        "completion": ["sig_slice_finish", "sig_global_done_pulse"], "drain": ["sig_valid_buf", "sig_mrm_rvalid", "sig_arm_rvalid"],
        "finish": ["sig_slice_finish"], "global_terminal": ["sig_global_done_pulse", "sig_slice_finish"],
        "selected_port": ["sig_buf_rd_addr", "sig_arm_req_addr", "sig_mrm_req_addr"],
        "selected_bank": ["sig_arm_req_valid", "sig_mrm_req_valid"], "selected_lane": ["sig_mrm_req_strb", "sig_valid_in_strb"],
        "internal_match": ["sig_mrm_r_bank_ready", "sig_arm_r_bank_ready"], "internal_state": ["sig_valid_buf", "sig_arm_clear_reg", "sig_nrm_clear_reg"],
        "output": ["sig_mrm_rvalid", "sig_arm_rvalid", "sig_mrm_rdata", "sig_data_out"],
        "wdata": ["sig_arm_wdata", "sig_mrm_wdata", "sig_mrm_rdata"],
    }
    roles_by_signal: dict[str, set[str]] = {}
    for role, ids in role_map.items():
        for signal_id in ids:
            roles_by_signal.setdefault(signal_id, set()).add(role)
    signals: list[dict[str, Any]] = []
    for item in old["signals"]:
        signal_id = item["signal_id"]
        signals.append(
            {
                "signal_id": signal_id,
                "exact_hierarchy": item["exact_hierarchy"],
                "width_bits": item["width_bits"],
                "roles": sorted(roles_by_signal.get(signal_id, {"internal_state"})),
                "source_path": item["source_path"],
                "source_sha256": item["source_sha256"],
                "declaration_span_sha256": item["declaration_span_sha256"],
                "source_binding": "ACTUAL_SOURCE_NET",
                "derived_expected_equation": False,
                "drives_dut": False,
            }
        )
    base = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
        "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
        "u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
    )
    additions = [
        ("sig_buffer_mask", "buffer_mask", 8, ["mask", "per_bank_owner"]),
        ("sig_nrm_rd_barrier", "nrm2buf_rd_barrier", 1, ["barrier", "backpressure"]),
        ("sig_nrm_wr_barrier", "nrm2buf_wr_barrier", 1, ["barrier", "backpressure"]),
        ("sig_mrm_last_bit", "mrm2buf_last_bit", 1, ["last", "tag"]),
        ("sig_arm_last_bit", "arm2buf_last_bit", 1, ["last", "tag"]),
        ("sig_mrm_last_out", "buf2mrm_last_bit", 1, ["last", "output"]),
        ("sig_mrm_last_index_out", "buf2mrm_last_index", 4, ["tag", "output"]),
        ("sig_arm_clear_reg", "arm_clear_reg", 4, ["per_bank_owner", "lifetime", "clear", "internal_state"]),
        ("sig_nrm_clear_reg", "nrm_clear_reg", 4, ["per_bank_owner", "lifetime", "clear", "internal_state"]),
        ("sig_tag_last_buf", "tag_last_buf", 4, ["tag", "last", "internal_state"]),
        ("sig_tag_last_index_buf", "tag_last_index_buf", 16, ["tag", "internal_state"]),
        ("sig_tag_row_empty", "tag_buf_row_empty", 4, ["fifo_empty", "drain", "internal_state"]),
    ]
    for signal_id, name, width, signal_roles in additions:
        signals.append(make_signal(signal_id, f"{base}.{name}", width, signal_roles, BUFFER_SOURCE, "rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv", name))
    tb_additions = [
        ("sig_global_cycle", "slice0_cycle_since_start", 64, ["count", "lifetime"]),
        ("sig_global_start_count", "slice0_start_count", 64, ["count", "stage"]),
        ("sig_global_exec_active", "slice0_exec_active", 1, ["lifetime", "stage"]),
        ("sig_global_done_pulse", "slice0_done_pulse", 1, ["completion", "finish", "global_terminal"]),
    ]
    for signal_id, name, width, signal_roles in tb_additions:
        signals.append(make_signal(signal_id, f"tb_NDP_Top_new_phy.{name}", width, signal_roles, TB_SOURCE, "tb_NDP_Top_new_phy.sv", name))
    return signals


def make_tb_source(signals: list[dict[str, Any]]) -> str:
    selected_ids = [
        "sig_clk", "sig_rst_n", "sig_slice_rst", "sig_exec_start", "sig_slice_finish",
        "sig_arm_req_valid", "sig_arm_req_rw", "sig_arm_req_addr", "sig_arm_clear", "sig_arm_force_clear",
        "sig_arm_wvalid", "sig_mrm_req_valid", "sig_mrm_req_rw", "sig_mrm_req_addr", "sig_mrm_req_strb",
        "sig_mrm_clear", "sig_mrm_wvalid", "sig_arm_rd_en", "sig_mrm_rd_en", "sig_buf_wr_en", "sig_buf_rd_en",
        "sig_buf_rd_addr", "sig_valid_buf", "sig_valid_wr_en", "sig_valid_in", "sig_valid_in_strb", "sig_valid_clear",
        "sig_valid_clr_mask", "sig_mrm_r_bank_ready", "sig_arm_r_bank_ready", "sig_mrm_w_bank_ready", "sig_arm_w_bank_ready",
        "sig_mrm_rreq_ready", "sig_arm_rreq_ready", "sig_buf_rreq_ready", "sig_mrm_rvalid", "sig_arm_rvalid",
        "sig_mrm_rdata", "sig_data_out", "sig_buffer_mask", "sig_nrm_rd_barrier", "sig_nrm_wr_barrier",
        "sig_arm_clear_reg", "sig_nrm_clear_reg", "sig_tag_last_buf", "sig_tag_last_index_buf", "sig_tag_row_empty",
        "sig_global_cycle", "sig_global_start_count", "sig_global_exec_active", "sig_global_done_pulse",
    ]
    by_id = {item["signal_id"]: item for item in signals}
    ports = []
    bindings = []
    for signal_id in selected_ids:
        item = by_id[signal_id]
        width = "" if item["width_bits"] == 1 else f"[{item['width_bits'] - 1}:0] "
        ports.append(f"    input wire {width}{signal_id}")
        relative = item["exact_hierarchy"].removeprefix("tb_NDP_Top_new_phy.")
        bindings.append(f"    .{signal_id}({relative})")
    causal = ", ".join(selected_ids)
    buffer_scope = by_id["sig_valid_buf"]["exact_hierarchy"].rsplit(".", 1)[0]
    return f'''`timescale 1ns/1ps
// QAdd v63 package-local standard-task VCD. Read-only diagnostics; never drives DUT.
module codex_qadd_tb_vcd_causal_cone_v63(
{',\n'.join(ports)}
);
  localparam longint unsigned TBVCD_SUSPECT_CYCLES = 64'd1048576;
  localparam longint unsigned TBVCD_DUMPOFF_CYCLES = 64'd4194304;
  localparam longint unsigned TBVCD_GRACE_CYCLES = 64'd262144;
  localparam integer TBVCD_CATALOG_MATRIX_COMPLETE = 1;
  string tbvcd_path;
  longint unsigned tbvcd_owner_cycles;
  longint unsigned tbvcd_plateau_cycles;
  longint unsigned tbvcd_progress_count;
  longint unsigned tbvcd_accept_count;
  longint unsigned tbvcd_clear_count;
  longint unsigned tbvcd_output_count;
  longint unsigned tbvcd_sim_time_ps;
  time tbvcd_last_sim_time;
  logic tbvcd_dump_off;
  logic [2047:0] tbvcd_state_previous;
  logic [255:0] tbvcd_counter_previous;
  logic [63:0] tbvcd_global_cycle_previous;
  logic [63:0] tbvcd_global_start_count_previous;
  wire [2047:0] tbvcd_state_current = {{{causal}}};
  wire [255:0] tbvcd_counter_current = {{tbvcd_progress_count, tbvcd_accept_count, tbvcd_clear_count, tbvcd_output_count}};
  wire tbvcd_progress_event = (|sig_buf_wr_en) || (|sig_buf_rd_en) || sig_mrm_rvalid || sig_arm_rvalid || sig_slice_finish;
  wire tbvcd_accept_event = (|sig_arm_rd_en && sig_arm_rreq_ready) || (|sig_mrm_rd_en && sig_mrm_rreq_ready);
  wire tbvcd_clear_event = (|sig_arm_clear) || (|sig_arm_force_clear) || (|sig_mrm_clear) || (|sig_valid_clear);
  wire tbvcd_output_event = sig_mrm_rvalid || sig_arm_rvalid;
  wire tbvcd_strict_plateau =
      (TBVCD_CATALOG_MATRIX_COMPLETE == 1) &&
      ($time > tbvcd_last_sim_time) &&
      !$isunknown(tbvcd_state_current) &&
      (tbvcd_state_current === tbvcd_state_previous) &&
      (tbvcd_counter_current === tbvcd_counter_previous) &&
      (sig_global_cycle === tbvcd_global_cycle_previous) &&
      (sig_global_start_count === tbvcd_global_start_count_previous);

  initial begin : tbvcd_init
    tbvcd_owner_cycles = 0;
    tbvcd_plateau_cycles = 0;
    tbvcd_progress_count = 0;
    tbvcd_accept_count = 0;
    tbvcd_clear_count = 0;
    tbvcd_output_count = 0;
    tbvcd_dump_off = 0;
    tbvcd_state_previous = 'x;
    tbvcd_counter_previous = 'x;
    tbvcd_global_cycle_previous = 'x;
    tbvcd_global_start_count_previous = 'x;
    tbvcd_last_sim_time = 0;
    if ($test$plusargs("CODEX_TB_VCD_ENABLE")) begin
      if (!$value$plusargs("CODEX_TB_VCD_PATH=%s", tbvcd_path))
        $fatal(1, "CODEX_TB_VCD_PATH is required");
      $dumpfile(tbvcd_path);
      $dumpvars(0, {buffer_scope});
      $dumpvars(0, tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.sem2iga_exec_start);
      $dumpvars(0, tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.slice_cmpt_finish);
      $dumpvars(0, tb_NDP_Top_new_phy.slice0_exec_active);
      $dumpvars(0, tb_NDP_Top_new_phy.slice0_cycle_since_start);
      $dumpvars(0, tb_NDP_Top_new_phy.slice0_start_count);
      $dumpvars(0, tb_NDP_Top_new_phy.slice0_done_pulse);
      $dumpon;
      $display("CODEX_TB_VCD_STARTED path=%0s", tbvcd_path);
    end
  end

  always @(posedge sig_clk) begin : tbvcd_runtime
    if (!sig_rst_n || sig_slice_rst) begin
      tbvcd_owner_cycles <= 0;
      tbvcd_plateau_cycles <= 0;
      tbvcd_progress_count <= 0;
      tbvcd_accept_count <= 0;
      tbvcd_clear_count <= 0;
      tbvcd_output_count <= 0;
      tbvcd_dump_off <= 0;
    end else if ($test$plusargs("CODEX_TB_VCD_ENABLE")) begin
      tbvcd_owner_cycles <= tbvcd_owner_cycles + 1;
      if (tbvcd_progress_event) tbvcd_progress_count <= tbvcd_progress_count + 1;
      if (tbvcd_accept_event) tbvcd_accept_count <= tbvcd_accept_count + 1;
      if (tbvcd_clear_event) tbvcd_clear_count <= tbvcd_clear_count + 1;
      if (tbvcd_output_event) tbvcd_output_count <= tbvcd_output_count + 1;
      if (tbvcd_strict_plateau) tbvcd_plateau_cycles <= tbvcd_plateau_cycles + 1;
      else tbvcd_plateau_cycles <= 0;
      tbvcd_state_previous <= tbvcd_state_current;
      tbvcd_counter_previous <= tbvcd_counter_current;
      tbvcd_global_cycle_previous <= sig_global_cycle;
      tbvcd_global_start_count_previous <= sig_global_start_count;
      tbvcd_last_sim_time <= $time;
      if ((tbvcd_owner_cycles & 64'h3ffff) == 0) begin
        tbvcd_sim_time_ps = $rtoi($realtime * 1000.0);
        $display("CODEX_TB_VCD_HEARTBEAT sim_time=%0d cycles=%0d progress=%0d global=%0d state=%0h", tbvcd_sim_time_ps, tbvcd_owner_cycles, tbvcd_progress_count, sig_global_cycle, tbvcd_state_current);
        $dumpflush;
      end
      if (tbvcd_plateau_cycles == TBVCD_SUSPECT_CYCLES)
        $display("CODEX_TB_VCD_PLATEAU_SUSPECT cycles=%0d", tbvcd_owner_cycles);
      if (!tbvcd_dump_off && tbvcd_plateau_cycles == TBVCD_DUMPOFF_CYCLES) begin
        $dumpoff;
        $dumpflush;
        tbvcd_dump_off <= 1;
        $display("CODEX_TB_VCD_DUMPOFF cycles=%0d strict_intersection=1", tbvcd_owner_cycles);
      end
      if (tbvcd_dump_off && tbvcd_plateau_cycles >= TBVCD_DUMPOFF_CYCLES + TBVCD_GRACE_CYCLES)
        $fatal(1, "CODEX_TB_VCD_CAUSAL_PLATEAU_PARTIAL");
      if (sig_slice_finish || sig_global_done_pulse)
        $display("CODEX_TB_VCD_NATURAL_TERMINAL cycles=%0d", tbvcd_owner_cycles);
    end
  end

  final begin : tbvcd_close
    if ($test$plusargs("CODEX_TB_VCD_ENABLE")) begin
      $dumpoff;
      $dumpflush;
      $display("CODEX_TB_VCD_CLOSED cycles=%0d", tbvcd_owner_cycles);
    end
  end
endmodule

bind tb_NDP_Top_new_phy codex_qadd_tb_vcd_causal_cone_v63 codex_qadd_tb_vcd_causal_cone_v63_inst(
{',\n'.join(bindings)}
);
'''


RUNNER = r'''#!/usr/bin/env bash
# Exact TB-VCD/core-return runner. Compile evidence is always bootstrap-rooted.
# Streaming return members: analysis_state.json checkpoints.jsonl report.md wave.vcd.
set -u
set -o pipefail
export PYTHONDONTWRITEBYTECODE=1
install_name="__NEW__"
package_id="__NEW__"
return_tag="r$(date -u +%s%N)_$$"
result_root="/home/panqs/ndp/simresult"
return_zip="$result_root/${install_name}_${return_tag}_return.zip"
return_sha="${return_zip}.sha256"
package_root="$(dirname "${BASH_SOURCE[0]}")"
bootstrap_root=
# $bootstrap_root/compile_argv.json $bootstrap_root/compile_source_identity.json $bootstrap_root/compile_exit.txt
# $bootstrap_root/compile_driver.log $bootstrap_root/compile_first_error.txt $bootstrap_root/compile_log_head.txt $bootstrap_root/compile_log_tail.txt
compile_status=125
simulation_status=125
simulation_started=false
signal_name=NONE
finalized=0
sim_pid=0
run_root=
evidence_root=
compile_root=
process_receipt=
supervisor_heartbeat=
actual_argv_json=
vcd_path=
return_finalizer_state_name="RETURN_FINALIZER_STATE.json"
attempt="a$$"
server_root=
cfg_root=
trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
# CODEX_PRODUCTION_LAUNCH

runner_fail() {
  code="$1"; shift
  printf 'RUNNER_ERROR package=%s code=%s message=%s\n' "$package_id" "$code" "$*" >&2
  exit "$code"
}

publish_minimal_return() {
  mkdir -p -- "$result_root" || return 98
  stage="$result_root/.${install_name}.return.$$"
  [ ! -e "$stage" ] || return 98
  mkdir -- "$stage" || return 98
  mkdir -p -- "$stage/evidence/compile_rootcause"
  printf '%s\n' "$compile_status" >"$stage/compile_exit_status.txt"
  printf '%s\n' "$simulation_status" >"$stage/simulation_exit_status.txt"
  printf '%s\n' "$signal_name" >"$stage/signal_status.txt"
  for name in compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_first_error.txt compile_log_head.txt compile_log_tail.txt compile_downstream_state.json; do
    [ -z "$bootstrap_root" ] || [ ! -f "$bootstrap_root/$name" ] || cp -- "$bootstrap_root/$name" "$stage/evidence/$name"
  done
  python3 - "$stage" "$return_zip" "$return_sha" "$package_id" "$return_tag" "$attempt" "$compile_status" <<'PY'
import hashlib,json,os,pathlib,sys,zipfile
stage,target,side=map(pathlib.Path,sys.argv[1:4]);pkg,exe,att=sys.argv[4:7];code=int(sys.argv[7])
core=stage/'evidence/compile_rootcause';core.mkdir(parents=True,exist_ok=True)
(core/'COMPILE_CORE.json').write_text(json.dumps({'schema':'server-compile-core-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'compile_exit':code},sort_keys=True)+'\n')
(core/'compile_first_error.txt').write_text('runner failed before complete attempt layout\n')
(stage/'evidence/SIM_EXIT_RECEIPT.json').write_text(json.dumps({'schema':'server-tb-vcd-sim-exit-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'simulation_started':False,'exit_code':125,'natural_terminal':False,'diagnostic_status':'DIAGNOSTIC_EVIDENCE_INCOMPLETE'},sort_keys=True)+'\n')
(stage/'RETURN_CORE_MANIFEST.json').write_text(json.dumps({'schema':'server-post-sim-return-core-manifest-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'selected_mode':'TB_VCD_BOUNDED_CAUSAL_CONE','completeness':'PARTIAL'},sort_keys=True)+'\n')
tmp=target.with_name('.'+target.name+'.tmp.'+str(os.getpid()))
with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as zf:
    for p in sorted(x for x in stage.rglob('*') if x.is_file()): zf.write(p,f'{pkg}_return/{p.relative_to(stage).as_posix()}')
os.replace(tmp,target);h=hashlib.sha256(target.read_bytes()).hexdigest();t=side.with_name('.'+side.name+'.tmp.'+str(os.getpid()));t.write_text(f'{h}  {target.name}\n');os.replace(t,side)
PY
  rc=$?
  rm -rf -- "$stage"
  return "$rc"
}

finalize() {
  original="$1"
  [ "$finalized" -eq 0 ] || exit "$original"
  finalized=1
  trap - EXIT HUP INT TERM
  set +e
  if [ "$sim_pid" -gt 0 ] && kill -0 "$sim_pid" 2>/dev/null; then kill -TERM "$sim_pid" 2>/dev/null; wait "$sim_pid" 2>/dev/null; fi
  if [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && [ -n "$run_root" ] && [ -d "$run_root" ]; then
    for name in compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_first_error.txt compile_log_head.txt compile_log_tail.txt compile_downstream_state.json package_preflight.json installed_preflight.json runtime_layout_receipt.json fixed_result_preflight.json; do
      [ -z "$bootstrap_root" ] || [ ! -f "$bootstrap_root/$name" ] || cp -- "$bootstrap_root/$name" "$evidence_root/$name"
    done
    printf '%s\n' "$compile_status" >"$evidence_root/compile_exit_status.txt"
    printf '%s\n' "$simulation_status" >"$evidence_root/simulation_exit_status.txt"
    printf '%s\n' "$signal_name" >"$evidence_root/signal_status.txt"
    natural=false
    [ "$simulation_status" -eq 0 ] && grep -aq 'CODEX_TB_VCD_NATURAL_TERMINAL' "$run_root/sim.log" 2>/dev/null && natural=true
    python3 "$package_root/package_tools/qlinearadd_node0007_tb_vcd_finalize_v63.py" \
      --package-root "$package_root" --attempt-root "$run_root" --evidence-root "$evidence_root" \
      --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" \
      --vcd "$vcd_path" --actual-argv "$actual_argv_json" --process-receipt "$process_receipt" \
      --compile-source-identity "$evidence_root/compile_source_identity.json" \
      --simulation-started "$simulation_started" --simulation-exit "$simulation_status" \
      --signal "$signal_name" --natural-terminal "$natural"
    diagnostic_status=$?
    python3 - "$evidence_root/NATIVE_FAILURE_ATTEMPT.json" "$package_id" "$return_tag" "$attempt" "$server_root" "$compile_status" "$simulation_started" "$simulation_status" "$actual_argv_json" "$evidence_root/compile_driver.log" "$run_root/sim.log" "$evidence_root/compile_first_error.txt" <<'PY'
import hashlib,json,pathlib,re,sys
target=pathlib.Path(sys.argv[1]);pkg,exe,att,cwd=sys.argv[2:6];ce=int(sys.argv[6]);started=sys.argv[7]=='true';se=int(sys.argv[8]);actual=pathlib.Path(sys.argv[9]);logs=[pathlib.Path(x) for x in sys.argv[10:12]];first=pathlib.Path(sys.argv[12])
a=json.loads(actual.read_text()) if actual.is_file() else {};error=first.read_text(errors='replace').strip() if ce and first.is_file() else ''
if not error and se:
    for source in logs:
        if source.is_file():
            error=next((line for line in source.read_text(errors='replace').splitlines() if re.search(r'(?i)error|fatal|timeout|terminated',line)),'')
        if error: break
receipts=[]
for source in logs:
    if source.is_file():
        data=source.read_bytes();receipts.append({'path':str(source),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'complete':True})
target.write_text(json.dumps({'schema':'server-native-failure-attempt-v1','package_id':pkg,'execution_id':exe,'attempt_id':att,'actual_cwd':cwd,'actual_compile_argv':a.get('compile_argv',[]),'actual_sim_argv':a.get('sim_argv',[]),'relevant_env':a.get('relevant_env',{}),'sca_cfg':a.get('sca_cfg'),'sca_cfg_d':a.get('sca_cfg_d'),'repeat_num':a.get('repeat_num'),'compile_exit':ce,'simulation_started':started,'simulation_exit':se,'first_true_error':error or ('NO_FAILURE_ERROR_PATTERN' if ce==0 and se==0 else 'NO_TRUE_ERROR_PATTERN_FOUND'),'complete_log_receipts':receipts,'native_failure_differential':'PENDING_FAMILY_POST_FAILURE_REVIEW' if ce or se else 'NOT_APPLICABLE_SUCCESS','unknown_server_loader_start_wait_readback':'SERVER_RUNTIME_UNKNOWN'},sort_keys=True)+'\n')
PY
    export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag"
    export CODEX_SIM_EXIT_CODE="$simulation_status" CODEX_SIM_SIGNAL="$signal_name" CODEX_SIM_STARTED="$simulation_started"
    export CODEX_NATURAL_TERMINAL="$natural" CODEX_COMPILE_STATUS="$compile_status" CODEX_SIMULATION_STATUS="$simulation_status"
    python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"
    collect_status=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$collect_status" -eq 0 ] || final="$collect_status"
    [ "$diagnostic_status" -eq 0 ] || [ "$final" -ne 0 ] || final="$diagnostic_status"
  else
    publish_minimal_return
    publish_status=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$publish_status" -eq 0 ] || final="$publish_status"
  fi
  printf 'RUNNER_FINAL_STATUS package=%s exit=%s\n' "$package_id" "$final" >&2
  exit "$final"
}

on_signal() {
  signal_name="$1"
  [ "$simulation_status" -ne 125 ] || simulation_status="$2"
  [ "$sim_pid" -le 0 ] || kill -TERM "$sim_pid" 2>/dev/null
  finalize "$2"
}

[ "$#" -eq 1 ] || runner_fail 2 "usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x"
case "$1" in /*) ;; *) runner_fail 2 "server root must be absolute";; esac
package_root="$(cd "$package_root" && pwd -P)" || runner_fail 2 "package root unresolved"
server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server root unresolved"
mkdir -p -- "$result_root" || runner_fail 9 "result root unavailable"
layout_helper="$package_root/package_tools/server_package_runtime_layout.py"
layout_values="$(python3 "$layout_helper" prepare --server-root "$server_root" --package-id "$package_id" --install-name "$install_name" --attempt "$attempt" --format shell)" || runner_fail 13 "layout preparation failed"
eval "$layout_values"
cfg_root="$CFG_ROOT"
run_root="$RUN_ROOT"
evidence_root="$EVIDENCE_ROOT"
compile_root="$COMPILE_ROOT"
bootstrap_root="$server_root/install/codex_runs/$package_id/.compile-return-$return_tag"
mkdir -p -- "$bootstrap_root" "$compile_root/sim_results" "$evidence_root/vcd" || runner_fail 14 "attempt roots unavailable"
vcd_path="$evidence_root/vcd/wave.vcd"
process_receipt="$evidence_root/PROCESS_TREE_RECEIPT.json"
supervisor_heartbeat="$evidence_root/vcd/supervisor_samples.jsonl"
actual_argv_json="$evidence_root/ACTUAL_COMPILE_SIM_ARGV.json"
printf '# SIMULATION_NOT_STARTED\n' >"$run_root/sim.log"
runtime="$package_root/package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
python3 "$runtime" preflight --package-root "$package_root" >"$evidence_root/package_preflight.json" || runner_fail 5 "package preflight failed"
cp "$package_root/TEST_PACKAGE_MANIFEST.json" "$evidence_root/PACKAGE_MANIFEST.json"
cp -a "$package_root/workload/runtime/." "$cfg_root/"
python3 - "$cfg_root/sca_cfg_D.json" "$attempt" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]);d=json.loads(p.read_text())
for value in d.values(): value['path']=value['path'].replace('{attempt}',sys.argv[2])
p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
PY
for slice_id in $(seq -w 0 27); do mkdir -p -- "$run_root/op_tail_round/slice${slice_id}"; done
python3 "$runtime" preflight-installed --package-root "$package_root" --cfg-root "$cfg_root" --run-root "$run_root" >"$evidence_root/installed_preflight.json" || runner_fail 6 "installed payload preflight failed"
compile_argv=(timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 "RUN_DIR=$compile_root" "VCS_EXTRA_OPTS=+incdir+$package_root/tb_probe +define+CODEX_QADD_TB_VCD_BOUNDED $package_root/tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh")
printf 'RUNTIME_LAYOUT_COMPILE_START\n' >"$evidence_root/compile_started.marker"
python3 - "$bootstrap_root/compile_argv.json" "$server_root" "${compile_argv[@]}" <<'PY'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({'schema':'server-exact-compile-argv-v1','cwd':sys.argv[2],'argv':sys.argv[3:],'makefile':'Makefile.tb_NDP_Top_new_phy','target':'compile'},sort_keys=True)+'\n')
PY
cat >"$bootstrap_root/compile_downstream_state.json" <<'EOF'
{"schema":"server-compile-downstream-state-v1","compile_succeeded":false,"simulation_started":false,"sim_log":"placeholder-only-until-compile-success","formal_D":"not-produced-before-simulation"}
EOF
python3 - "$actual_argv_json" "$package_id" "$return_tag" "$attempt" "$server_root" "$cfg_root/sca_cfg.json" "$cfg_root/sca_cfg_D.json" "${compile_argv[@]}" <<'PY'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({'schema':'server-tb-vcd-actual-argv-v1','package_id':sys.argv[2],'execution_id':sys.argv[3],'attempt_id':sys.argv[4],'cwd':sys.argv[5],'actual_cwd':sys.argv[5],'sca_cfg':sys.argv[6],'sca_cfg_d':sys.argv[7],'repeat_num':1,'relevant_env':{'DUMP_VCD':'0','DUMP_FSDB':'0','TB_DUMP_FSDB':'0'},'source_identity_status':'NOT_YET_BOUND','compile_argv':sys.argv[8:],'sim_argv':['simv','DUMP_VCD=0','DUMP_FSDB=0','TB_DUMP_FSDB=0']},sort_keys=True)+'\n')
PY
cd "$server_root"
set +e
"${compile_argv[@]}" >"$bootstrap_root/compile_driver.log" 2>&1
compile_status=$?
python3 - "$bootstrap_root/compile_source_identity.json" "$server_root/Makefile.tb_NDP_Top_new_phy" "$package_root/tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh" "$package_root/tb_probe" <<'PY'
import hashlib,json,pathlib,sys
def record(value):
 p=pathlib.Path(value);row={'path':str(p),'exists':p.is_file()}
 if p.is_file():
  data=p.read_bytes();row.update({'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 return row
tree=pathlib.Path(sys.argv[4]);files=[record(p) for p in sorted(tree.rglob('*')) if p.is_file()]
pathlib.Path(sys.argv[1]).write_text(json.dumps({'schema':'server-compile-source-identity-v1','makefile':record(sys.argv[2]),'explicit_package_source':record(sys.argv[3]),'package_include_tree':{'path':str(tree),'files':files}},sort_keys=True)+'\n')
PY
printf '%s\n' "$compile_status" >"$bootstrap_root/compile_exit.txt"
head -n 200 "$bootstrap_root/compile_driver.log" >"$bootstrap_root/compile_log_head.txt"
tail -n 200 "$bootstrap_root/compile_driver.log" >"$bootstrap_root/compile_log_tail.txt"
python3 - "$bootstrap_root/compile_driver.log" "$bootstrap_root/compile_first_error.txt" <<'PY'
import pathlib,re,sys
rows=pathlib.Path(sys.argv[1]).read_text(errors='replace').splitlines();first=next((r for r in rows if re.search(r'(?i)error|fatal|no rule to make target|not found|syntax error',r)),'NO_COMPILER_ERROR_PATTERN_FOUND');pathlib.Path(sys.argv[2]).write_text(first[:8192]+'\n')
PY
for name in compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_first_error.txt compile_log_head.txt compile_log_tail.txt compile_downstream_state.json; do cp -- "$bootstrap_root/$name" "$evidence_root/$name"; done
[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; core evidence will return"
simv="$compile_root/sim_results/simv"
sim_args=(-l "$run_root/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/sca_cfg.json" "+SCA_CFG_D=$cfg_root/sca_cfg_D.json" +CODEX_TB_VCD_ENABLE "+CODEX_TB_VCD_PATH=$vcd_path" "+CODEX_PACKAGE_ID=$package_id" "+CODEX_EXECUTION_ID=$return_tag" "+CODEX_ATTEMPT_ID=$attempt")
python3 - "$actual_argv_json" "$package_id" "$return_tag" "$attempt" "$server_root" "$cfg_root/sca_cfg.json" "$cfg_root/sca_cfg_D.json" "${compile_argv[@]}" --SIM-- "$simv" "${sim_args[@]}" <<'PY'
import json,pathlib,sys
cut=sys.argv.index('--SIM--');pathlib.Path(sys.argv[1]).write_text(json.dumps({'schema':'server-tb-vcd-actual-argv-v1','package_id':sys.argv[2],'execution_id':sys.argv[3],'attempt_id':sys.argv[4],'cwd':sys.argv[5],'actual_cwd':sys.argv[5],'sca_cfg':sys.argv[6],'sca_cfg_d':sys.argv[7],'repeat_num':1,'relevant_env':{'DUMP_VCD':'0','DUMP_FSDB':'0','TB_DUMP_FSDB':'0'},'source_identity_status':'COMPLETE','compile_argv':sys.argv[8:cut],'sim_argv':['env','DUMP_VCD=0','DUMP_FSDB=0','TB_DUMP_FSDB=0',*sys.argv[cut+1:]]},sort_keys=True)+'\n')
PY
simulation_started=true
printf 'RUNTIME_LAYOUT_SIMULATION_START\n' >"$evidence_root/simulation_started.marker"
DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/qlinearadd_node0007_tb_vcd_guarded_supervisor_v63.py" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --sim-log "$run_root/sim.log" --vcd "$vcd_path" --heartbeat "$supervisor_heartbeat" --receipt "$process_receipt" --interval 30 --grace 30 -- "$simv" "${sim_args[@]}" &
sim_pid=$!
wait "$sim_pid"
simulation_status=$?
sim_pid=0
[ "$simulation_status" -eq 0 ] || runner_fail "$simulation_status" "production simulation ended non-naturally; partial evidence will return"
exit 0
'''


def build_contract(signals: list[dict[str, Any]], tb_path: Path) -> dict[str, Any]:
    role_coverage = []
    for role in ROLES:
        ids = [item["signal_id"] for item in signals if role in item["roles"]]
        if not ids:
            raise RuntimeError(f"role has no source-bound signal: {role}")
        role_coverage.append({"role": role, "disposition": "covered", "signal_ids": ids})
    boundaries = [
        {"boundary_id": "buffer5_request_decode", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ["sig_arm_req_valid", "sig_mrm_req_valid", "sig_arm_req_rw", "sig_mrm_req_rw", "sig_arm_req_addr", "sig_mrm_req_addr", "sig_mrm_req_strb", "sig_arm_wvalid", "sig_mrm_wvalid"]},
        {"boundary_id": "selected_port_lane_ready_accept", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ["sig_buf_rd_addr", "sig_valid_buf", "sig_arm_r_bank_ready", "sig_mrm_r_bank_ready", "sig_arm_rreq_ready", "sig_mrm_rreq_ready", "sig_arm_rd_en", "sig_mrm_rd_en", "sig_nrm_rd_barrier", "sig_buffer_mask"]},
        {"boundary_id": "read_data_output_terminal", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ["sig_mrm_rvalid", "sig_arm_rvalid", "sig_mrm_rdata", "sig_data_out", "sig_mrm_last_out", "sig_slice_finish", "sig_global_done_pulse"]},
        {"boundary_id": "producer_owner_clear_hold", "layer": "STATE_HOLD_CLEAR", "signal_ids": ["sig_valid_buf", "sig_valid_wr_en", "sig_valid_clear", "sig_valid_clr_mask", "sig_arm_clear", "sig_arm_force_clear", "sig_mrm_clear", "sig_arm_clear_reg", "sig_nrm_clear_reg", "sig_tag_last_buf", "sig_tag_last_index_buf", "sig_global_cycle"]},
    ]
    candidates = [
        ("selected_required_lanes_not_ready", "Selected ping-pong address has one or more required bank/lane valid bits absent."),
        ("nonselected_or_switch_hazard", "Non-selected port state or ping-pong switch timing controls the selected readiness."),
        ("bank_owner_or_full", "Per-bank owner, full or mask state blocks the selected request."),
        ("producer_or_clear", "Producer publication or clear/force-clear timing removes required valid state."),
        ("read_barrier_or_accept", "Read barrier or aggregate accept equation blocks an otherwise-ready request."),
        ("downstream_output_or_terminal", "Read accept occurs but read-valid/data/output/completion does not advance."),
        ("tag_mask_or_outstanding", "Tag, last, mask or outstanding lifetime retains/drains the operation incorrectly."),
    ]
    matrix = []
    boundary_ids = [item["boundary_id"] for item in boundaries]
    for index, (candidate_id, _) in enumerate(candidates):
        for boundary_index, boundary_id in enumerate(boundary_ids):
            matrix.append(
                {
                    "candidate_id": candidate_id,
                    "boundary_id": boundary_id,
                    "expected_signature": {
                        "candidate_ordinal": index,
                        "boundary_ordinal": boundary_index,
                        "request_decode": "present" if boundary_index == 0 else "bound_from_upstream",
                        "selected_ready": "blocked" if index in {0, 1, 2, 3, 4, 6} and boundary_index == 1 else "distinguishable",
                        "downstream_progress": "absent_after_accept" if index == 5 and boundary_index == 2 else "causally_classified",
                    },
                }
            )
    scope_signal_ids = [item["signal_id"] for item in signals]
    return {
        "schema": "server-tb-vcd-bounded-causal-cone-v1",
        "profile": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "rule_id": "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001",
        "package_id": NEW,
        "family": FAMILY,
        "execution": {
            "compile_argv": ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0", "VCS_EXTRA_OPTS=<package-local-tb-vcd-source>"],
            "sim_argv": ["simv", "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0", "+CODEX_TB_VCD_ENABLE", "+CODEX_TB_VCD_PATH=<attempt>/evidence/vcd/wave.vcd"],
            "dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            "tb_source_path": "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh",
            "tb_source_sha256": digest(tb_path),
            "standard_tasks": ["$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush"],
            "producer": "PACKAGE_LOCAL_TB_STANDARD_SYSTEM_TASKS_ONLY",
            "lightweight_observer_jsonl": False,
        },
        "scope": {
            "simulation_top": "tb_NDP_Top_new_phy",
            "full_hierarchy_dump": False,
            "dump_scopes": [
                {
                    "scope_id": "qadd_slice0_buffer5_depth0",
                    "exact_hierarchy": "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer",
                    "depth": 0,
                    "boundary_ids": boundary_ids,
                    "source_bound_signal_ids": scope_signal_ids,
                }
            ],
        },
        "budget": {"soft_warning_bytes": 100000000, "operational_vcd_budget_bytes": 8000000000, "return_budget_bytes": 10000000000, "wall_ceiling_seconds": 3600, "hard_truncation": False, "sampling": False, "size_based_deletion": False},
        "signals": signals,
        "role_coverage": role_coverage,
        "boundaries": boundaries,
        "candidates": [{"candidate_id": item[0], "description": item[1]} for item in candidates],
        "candidate_boundary_matrix": matrix,
        "runtime_policy": {
            "plateau_suspected_cycles": 1048576,
            "plateau_dump_off_cycles": 4194304,
            "post_dump_grace_cycles": 262144,
            "plateau_qualification": ["owner_clock_advancing", "sim_time_advancing", "all_qualified_progress_counters_stable", "complete_source_bound_causal_state_bitwise_stable", "global_progress_witness_stable", "candidate_catalog_coverage_complete", "no_unresolved_xz"],
            "sim_time_freeze_intervals": 3,
            "sim_time_freeze_interval_seconds": 30,
            "termination_sequence": ["TERM", "WAIT", "KILL", "REAP"],
            "disk_write_quota_fail_safe": True,
            "rolling_growth_projection": True,
        },
        "return_receipts": {
            "catalog": "evidence/vcd/catalog.json",
            "candidate_matrix": "evidence/vcd/candidate_matrix.json",
            "actual_argv": "evidence/ACTUAL_COMPILE_SIM_ARGV.json",
            "tb_source": "evidence/vcd/tb_source.json",
            "elaboration": "evidence/vcd/elaboration.json",
            "runtime": "evidence/vcd/runtime.json",
            "vcd": "evidence/vcd/wave.vcd",
            "process_tree": "evidence/PROCESS_TREE_RECEIPT.json",
            "return_manifest": "evidence/vcd/return_manifest.json",
        },
        "claim_boundary": "Local source-bound QAdd package contract only; no production compile, simulation, diagnosis, natural terminal, formal D, E3, E4 or E5 claim.",
    }


def post_request() -> dict[str, Any]:
    core: list[dict[str, Any]] = []
    def add(root: str, source: str, archive: str, required: bool) -> None:
        core.append({"source_root": root, "source": source, "archive": archive, "required": required})
    for source, archive in [
        ("TEST_PACKAGE_MANIFEST.json", "source_package/TEST_PACKAGE_MANIFEST.json"),
        ("contracts/server_diagnostic_mode_selector.json", "source_package/server_diagnostic_mode_selector.json"),
        ("contracts/server_tb_vcd_bounded_causal_cone_contract.json", "source_package/server_tb_vcd_bounded_causal_cone_contract.json"),
        ("diagnostics/tb_vcd_signal_catalog.json", "source_package/tb_vcd_signal_catalog.json"),
        ("diagnostics/tb_vcd_candidate_matrix.json", "source_package/tb_vcd_candidate_matrix.json"),
        ("tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh", "source_package/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh"),
        ("package_tools/server_tb_vcd_retention_analysis.py", "source_package/server_tb_vcd_retention_analysis.py"),
    ]:
        add("package", source, archive, True)
    required_attempt = [
        ("evidence/PACKAGE_MANIFEST.json", "evidence/PACKAGE_MANIFEST.json"),
        ("evidence/compile_exit_status.txt", "evidence/compile_exit_status.txt"),
        ("evidence/simulation_exit_status.txt", "evidence/simulation_exit_status.txt"),
        ("evidence/signal_status.txt", "evidence/signal_status.txt"),
        ("evidence/compile_argv.json", "evidence/compile_argv.json"),
        ("evidence/compile_source_identity.json", "evidence/compile_source_identity.json"),
        ("evidence/compile_exit.txt", "evidence/compile_exit.txt"),
        ("evidence/compile_driver.log", "evidence/compile_driver.log"),
        ("evidence/compile_first_error.txt", "evidence/compile_first_error.txt"),
        ("evidence/compile_log_head.txt", "evidence/compile_log_head.txt"),
        ("evidence/compile_log_tail.txt", "evidence/compile_log_tail.txt"),
        ("evidence/compile_downstream_state.json", "evidence/compile_downstream_state.json"),
        ("evidence/ACTUAL_COMPILE_SIM_ARGV.json", "evidence/ACTUAL_COMPILE_SIM_ARGV.json"),
        ("evidence/SIM_EXIT_RECEIPT.json", "evidence/SIM_EXIT_RECEIPT.json"),
        ("evidence/vcd/catalog.json", "evidence/vcd/catalog.json"),
        ("evidence/vcd/candidate_matrix.json", "evidence/vcd/candidate_matrix.json"),
        ("evidence/vcd/tb_source.json", "evidence/vcd/tb_source.json"),
        ("evidence/vcd/elaboration.json", "evidence/vcd/elaboration.json"),
        ("evidence/vcd/runtime.json", "evidence/vcd/runtime.json"),
        ("evidence/vcd/return_manifest.json", "evidence/vcd/return_manifest.json"),
        ("evidence/vcd/finalization_receipt.json", "evidence/vcd/finalization_receipt.json"),
    ]
    for source, archive in required_attempt:
        add("attempt", source, archive, True)
    optional = [
        ("sim.log", "runs/sim.log"),
        ("evidence/PROCESS_TREE_RECEIPT.json", "evidence/PROCESS_TREE_RECEIPT.json"),
        ("evidence/vcd/supervisor_samples.jsonl", "evidence/vcd/supervisor_samples.jsonl"),
        ("evidence/vcd/runtime_request.json", "evidence/vcd/runtime_request.json"),
        ("evidence/vcd/wave.vcd", "evidence/vcd/wave.vcd"),
        ("evidence/vcd/analysis/analysis_state.json", "evidence/vcd/analysis/analysis_state.json"),
        ("evidence/vcd/analysis/checkpoints.jsonl", "evidence/vcd/analysis/checkpoints.jsonl"),
        ("evidence/vcd/analysis/report.md", "evidence/vcd/analysis/report.md"),
        ("evidence/compile_rootcause/COMPILE_CORE.json", "evidence/compile_rootcause/COMPILE_CORE.json"),
        ("evidence/compile_rootcause/compile_first_error.txt", "evidence/compile_rootcause/compile_first_error.txt"),
        ("evidence/NATIVE_FAILURE_ATTEMPT.json", "evidence/NATIVE_FAILURE_ATTEMPT.json"),
    ]
    for source, archive in optional:
        add("attempt", source, archive, False)
    for slice_id in range(28):
        source = f"op_tail_round/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        add("attempt", source, f"readbacks/{source}", False)
    return {
        "schema": "server-post-sim-return-request-v1",
        "package_id": NEW,
        "result_root": "/home/panqs/ndp/simresult",
        "return_basename_template": "{package_id}_{execution_id}_return.zip",
        "core_entries": core,
        "plugins": [],
        "max_plugin_output_bytes": 262144,
        "claim_boundary": "TB-VCD and compile/simulation core publication; no correctness, natural-terminal, formal-D, E3, E4 or E5 claim from collection alone.",
    }


def main() -> int:
    if BUILD.exists():
        raise RuntimeError("refusing to overwrite one-shot v63 build directory")
    index = json.loads((STORAGE / "PACKAGE_STORAGE_INDEX.json").read_text(encoding="utf-8"))
    pending = [item for item in index.get("packages", []) if item.get("family") == FAMILY and item.get("disposition") == "pending"]
    if index.get("pass") is not True or len(pending) != 1 or pending[0].get("package_base") != OLD:
        raise RuntimeError("v62 is not the unique indexed QAdd pending predecessor")
    declared = [item for item in pending[0].get("files", []) if item.get("relative_path") == f"pending/{OLD}.zip"]
    if len(declared) != 1 or declared[0].get("bytes") != SOURCE_ZIP.stat().st_size or declared[0].get("sha256") != digest(SOURCE_ZIP):
        raise RuntimeError("v62 exact pending identity differs from storage index")
    source_identity = identity(SOURCE_ZIP)

    BUILD.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="qadd-v63-source-") as temporary:
        source = safe_extract(SOURCE_ZIP, Path(temporary) / "extract")
        source_validation = tree_identity(source / "validation")
        source_install = tree_identity(source / "workload/install")
        source_runtime = tree_identity(source / "workload/runtime", {"sca_cfg.json", "sca_cfg_D.json"})
        signals = signal_contract(source)
        shutil.copytree(source, TREE)

    recursive_identity_replace(TREE)
    shutil.rmtree(TREE / "tb_probe")
    (TREE / "tb_probe").mkdir()
    shutil.rmtree(TREE / "diagnostics")
    (TREE / "diagnostics").mkdir()
    observer_contract = TREE / "contracts/server_observer_only_wide_causal_contract.json"
    if observer_contract.exists():
        observer_contract.unlink()
    for name in ("qadd_observer_event_parser.py", "qadd_observer_return_manifest.py", "source_bound_causal_parser.py", "qlinearadd_node0007_source_bound_stage_filter_v57.py"):
        path = TREE / "package_tools" / name
        if path.exists():
            path.unlink()

    tb_path = TREE / "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh"
    tb_path.write_text(make_tb_source(signals), encoding="utf-8", newline="\n")
    for source_name, target_name in [
        ("tools/qlinearadd_node0007_tb_vcd_guarded_supervisor_v63.py", "package_tools/qlinearadd_node0007_tb_vcd_guarded_supervisor_v63.py"),
        ("tools/qlinearadd_node0007_tb_vcd_finalize_v63.py", "package_tools/qlinearadd_node0007_tb_vcd_finalize_v63.py"),
        ("tools/server_tb_vcd_runtime_supervision.py", "package_tools/server_tb_vcd_runtime_supervision.py"),
        ("tools/server_tb_vcd_retention_analysis.py", "package_tools/server_tb_vcd_retention_analysis.py"),
        ("tools/server_post_sim_return.py", "package_tools/server_post_sim_return.py"),
    ]:
        shutil.copy2(ROOT / source_name, TREE / target_name)

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner_path.write_text(RUNNER.replace("__NEW__", NEW), encoding="utf-8", newline="\n")
    runner_path.chmod(runner_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    contract = build_contract(signals, tb_path)
    contract_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    write_json(contract_path, contract)
    write_json(TREE / "diagnostics/tb_vcd_signal_catalog.json", {"schema": "qadd-tb-vcd-signal-catalog-v1", "package_id": NEW, "signal_count": len(signals), "signals": signals, "source_bound": True, "drives_dut": False})
    write_json(TREE / "diagnostics/tb_vcd_candidate_matrix.json", {"schema": "qadd-tb-vcd-candidate-matrix-v1", "package_id": NEW, "boundaries": contract["boundaries"], "candidates": contract["candidates"], "candidate_boundary_matrix": contract["candidate_boundary_matrix"], "pairwise_complete": True})
    write_json(TREE / "diagnostics/progress_contract.json", {"schema": "qadd-tb-vcd-progress-contract-v1", "package_id": NEW, "qualified_counters": ["producer", "clear", "read_accept", "read_valid", "output", "completion"], "global_progress_witness": ["slice0_cycle_since_start", "slice0_start_count", "slice0_done_pulse"], "plateau_requires_strict_intersection": True, "global_progress_advance_forbids_stop": True})
    write_json(TREE / "diagnostics/retention_policy.json", {"schema": "server-tb-vcd-retention-analysis-v1", "kind": "retention_policy", "family": FAMILY, "track": "tailround_lanephase", "max_raw_groups": 3, "protected_slots": ["MAX_PROGRESS", "LATEST_1", "LATEST_2"], "delete_requires": ["analysis_complete", "family_consumed", "mainline_consumed", "deterministic_core_evidence", "protected_set_audit_pass"], "raw_size_deletion": False})

    request = post_request()
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    write_json(request_path, request)
    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    write_json(post_contract_path, {"schema": "server-post-sim-return-contract-v1", "package_id": NEW, "helper_member": "package_tools/server_post_sim_return.py", "helper_sha256": digest(TREE / "package_tools/server_post_sim_return.py"), "request_member": "contracts/server_post_sim_return_request.json", "request_sha256": digest(request_path), "runner_member": "PREPARE_AND_RUN.sh", "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR", "sim_exit_persisted_before_plugins": True, "plugin_failure_blocks_core_return": False, "required_scenarios": ["natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"], "partial_exit_live_causal_record": {"rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001", "enforcement": "required_next_fresh", "required_signals": ["INT", "TERM"], "final_block_ring_sole_input_forbidden": True, "plugin_dispositions": []}, "claim_boundary": "Exact return-core transport only; no DUT claim."})

    runner_contract = {
        "schema": "server-runner-return-resilience-contract-v1", "package_id": NEW,
        "runner_path": f"{NEW}/PREPARE_AND_RUN.sh", "runner_sha256": digest(runner_path), "nounset_required": True,
        "package_owned_variables": ["install_name", "package_id", "return_tag", "result_root", "return_zip", "return_sha", "package_root", "bootstrap_root", "compile_status", "simulation_status", "simulation_started", "signal_name", "run_root", "evidence_root", "compile_root", "process_receipt", "supervisor_heartbeat", "actual_argv_json", "vcd_path"],
        "bootstrap_root_variable": "bootstrap_root", "first_fallible_tokens": ["runner_fail()"],
        "finalizer_arm_tokens": ["trap 'finalize $?' EXIT"],
        "compile_evidence_tokens": {"argv": "compile_argv.json", "source_identity": "compile_source_identity.json", "exit_code": "compile_exit.txt", "driver_log": "compile_driver.log", "first_error": "compile_first_error.txt", "bounded_head": "compile_log_head.txt", "bounded_tail": "compile_log_tail.txt"},
        "return_allowlist_tokens": ["PROCESS_TREE_RECEIPT.json", "SIM_EXIT_RECEIPT.json", "analysis_state.json", "checkpoints.jsonl", "report.md", "wave.vcd", "COMPILE_CORE.json"],
        "claim_boundary": "Static runner/core-return resilience only; no production claim.",
    }
    write_json(TREE / "contracts/server_runner_return_resilience_contract.json", runner_contract)

    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["claim_boundary"] = "Frozen QAdd install/runtime paths with bounded-causal-cone TB-VCD attempt evidence."
    layout["finalizer"]["first_preflight_marker"] = '[ "$#" -eq 1 ]'
    layout["runner_bindings"]["compile_marker"] = "printf 'RUNTIME_LAYOUT_COMPILE_START"
    layout["runner_bindings"]["simulation_marker"] = "printf 'RUNTIME_LAYOUT_SIMULATION_START"
    layout["path_budget"]["additional_projected_paths"] = [
        value.replace("return_observer.log", "evidence/vcd/wave.vcd")
        for value in layout["path_budget"]["additional_projected_paths"]
    ]
    write_json(layout_path, layout)

    member_paths = [path.relative_to(TREE).as_posix() for path in sorted(TREE.rglob("*")) if path.is_file()]
    for extra in ["contracts/server_diagnostic_mode_selector.json", "TEST_PACKAGE_MANIFEST.json"]:
        if extra not in member_paths:
            member_paths.append(extra)
    selector = {
        "schema": "server-diagnostic-mode-selector-v1", "package_id": NEW, "family": FAMILY,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "bulk_evidence": {"observer_jsonl": False, "tb_standard_vcd": True, "vpd": False, "fsdb": False, "ucli_direct_vcd": False, "vendor_signal_query": False},
        "actual_dump_argv": {"DUMP_VCD": "0", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
        "lightweight_progress_supervisor": {"enabled": True, "bulk_signal_events": False, "sim_time_heartbeat": True, "process_tree_reap": True},
        "package_members": sorted(member_paths),
        "return_members": ["evidence/vcd/wave.vcd", "evidence/vcd/runtime.json", "evidence/vcd/analysis/analysis_state.json", "evidence/vcd/analysis/checkpoints.jsonl", "evidence/vcd/analysis/report.md", "evidence/ACTUAL_COMPILE_SIM_ARGV.json", "evidence/PROCESS_TREE_RECEIPT.json", "evidence/SIM_EXIT_RECEIPT.json"],
        "observer_contract_sha256": None, "vcd_contract_sha256": digest(contract_path),
        "claim_boundary": "Exactly one local bulk evidence mode; no production or diagnostic claim.",
    }
    write_json(TREE / "contracts/server_diagnostic_mode_selector.json", selector)
    write_json(TREE / "RETURN_ALLOWLIST.json", {"schema": "server-tb-vcd-return-allowlist-v1", "package_id": NEW, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "no_size_limit": True, "hard_truncation": False, "sampling": False, "size_based_deletion": False, "required": selector["return_members"], "prefixes": [f"{NEW}_return/evidence/vcd/"], "compile_not_started_waveform_optional": True})
    write_json(TREE / "provenance/v62_to_v63_tb_vcd.json", {"schema": "qadd-v62-to-v63-tb-vcd-provenance-v1", "package_id": NEW, "activation_epoch": EPOCH, "previous_version_progress": "v57h localized the DUT boundary after Buffer5 request decode and before selected ping-pong required-lane read accept; v59 exposed manifest/install/SCA identity mismatch; v60 repaired it; v62 preserved the repaired identity and native production flow in an unrun observer-only package.", "current_version_purpose": "Preserve the v62 identity repair, frozen tail-round target and both ping-pong branches while capturing the Buffer5 depth-0 full causal cone, Slice terminal and global progress witness with package-local standard-task VCD in one future return.", "changed_surface": ["fresh identity", "diagnostic mode selector", "package-local TB VCD", "runtime safeguards", "streaming return and retention surfaces"], "frozen_surface": ["configuration", "numeric", "workload", "golden", "functional RTL", "tail-round causal target", "ping-pong behavior"], "server_action": False})

    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["package_id"] = NEW
    manifest["install_name"] = NEW
    manifest["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"
    manifest["server_run_performed"] = False
    manifest["uploaded"] = False
    manifest.pop("observer_only_contract_sha256", None)
    manifest["diagnostic_mode"] = "TB_VCD_BOUNDED_CAUSAL_CONE"
    manifest["diagnostic_mode_selector_sha256"] = digest(TREE / "contracts/server_diagnostic_mode_selector.json")
    manifest["tb_vcd_bounded_causal_cone_sha256"] = digest(contract_path)
    manifest["rule_change_epoch"] = {"epoch_id": EPOCH, "family": FAMILY, "package_id": NEW, "first_fresh_after_change": True, "notification_acknowledged": True, "upload_hold_until": "EXPLICIT_USER_SERVER_AUTHORIZATION"}
    manifest["first_fresh_extra_audit"] = {"bound_package_id": NEW, "epoch_id": EPOCH, "first_fresh_after_change": True, "notification_acknowledged": True, "prior_first_fresh_pass_receipt": None, "upload_hold_until_final_audit_pass": True}
    manifest["files"] = files_map(TREE)
    write_json(manifest_path, manifest)

    frozen = {
        "schema": "qadd-v63-tb-vcd-frozen-surface-v1",
        "validation_golden_byte_equal": tree_identity(TREE / "validation") == source_validation,
        "workload_install_payload_byte_equal": tree_identity(TREE / "workload/install") == source_install,
        "workload_runtime_excluding_identity_sca_byte_equal": tree_identity(TREE / "workload/runtime", {"sca_cfg.json", "sca_cfg_D.json"}) == source_runtime,
        "functional_rtl_modified": False, "config_numeric_workload_golden_semantics_modified": False,
        "ping_pong_behavior_modified": False, "tail_round_target_modified": False,
        "source_v62_pending_unchanged": identity(SOURCE_ZIP) == source_identity,
    }
    frozen["pass"] = (
        frozen["validation_golden_byte_equal"]
        and frozen["workload_install_payload_byte_equal"]
        and frozen["workload_runtime_excluding_identity_sca_byte_equal"]
        and frozen["functional_rtl_modified"] is False
        and frozen["config_numeric_workload_golden_semantics_modified"] is False
        and frozen["ping_pong_behavior_modified"] is False
        and frozen["tail_round_target_modified"] is False
        and frozen["source_v62_pending_unchanged"]
    )
    write_json(OUT / "frozen_surface_receipt.json", frozen)
    if not frozen["pass"]:
        raise RuntimeError(f"frozen surface drift: {frozen}")

    deterministic_zip(TREE, ZIP)
    recheck = zip_recheck(TREE, ZIP)
    ZIP.with_name(ZIP.name + ".sha256").write_text(f"{digest(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    if identity(SOURCE_ZIP) != source_identity:
        raise RuntimeError("v62 pending identity changed during build")
    write_json(BUILD / "build_receipt.json", {"schema": "qadd-v63-tb-vcd-build-v1", "package_id": NEW, "source_v62_pending": source_identity, "activation_epoch": EPOCH, "zip": identity(ZIP), "exact_final_zip_recheck": recheck, "signal_count": len(signals), "role_count": len(ROLES), "candidate_count": len(contract["candidates"]), "matrix_rows": len(contract["candidate_boundary_matrix"]), "frozen_surface": frozen, "server_action": False, "pass": True})
    print(json.dumps({"package_id": NEW, "zip": ZIP.relative_to(ROOT).as_posix(), "signals": len(signals), "roles": len(ROLES), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
