from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records


PKG_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_qadd_n7_split_c_ingress_v28"
TARGET_NAME = "r5_qadd_n7_split_c_pairmatrix_v29"
SOURCE = PKG_ROOT / SOURCE_NAME
SOURCE_ZIP = PKG_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "f552f2a24ae62b1e4e11c1a69ddff6663ffa2ea4fa177b923d0298c15a739f50"
TARGET = PKG_ROOT / TARGET_NAME
ZIP = PKG_ROOT / f"{TARGET_NAME}.zip"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"preimage count differs for {old!r}: {text.count(old)}")
    return text.replace(old, new)


PAIR_TAIL = r'''
// v29 stage-4-only MSE0/MSE1 index-pair observer.
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0][2:0] qadd_pair_idx_valid;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0][2:0] qadd_pair_idx_ready;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] qadd_pair_match;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] qadd_pair_empty;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] qadd_pair_full;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] qadd_pair_qwr;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] qadd_pair_ag_valid;
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0] qadd_pair_ag_ready;
longint unsigned qadd_pair_idx_hs [0:1][0:2];
longint unsigned qadd_pair_qwr_count [0:1];
longint unsigned qadd_pair_ag_hs_count [0:1];
longint unsigned qadd_pair_snapshot_cycles;

generate
  for (genvar qpm_g=0; qpm_g<`SLICE_GROUP_SIZE; qpm_g++) begin : QADD_PAIR_G
    for (genvar qpm_s=0; qpm_s<`SLICE_GROUP_NUM; qpm_s++) begin : QADD_PAIR_S
      for (genvar qpm_m=0; qpm_m<2; qpm_m++) begin : QADD_PAIR_M
        assign qadd_pair_idx_valid[qpm_g][qpm_s][qpm_m] = {
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag[qpm_m][2][`SE_MEM_INPORT_TAG_WIDTH-1],
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag[qpm_m][1][`SE_MEM_INPORT_TAG_WIDTH-1],
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_tag[qpm_m][0][`SE_MEM_INPORT_TAG_WIDTH-1]};
        assign qadd_pair_idx_ready[qpm_g][qpm_s][qpm_m] =
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.mse_mem_queue_bp_pre[qpm_m];
        assign qadd_pair_match[qpm_g][qpm_s][qpm_m] =
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[qpm_m].RD_MSE.u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue.mem_all_idx_matched;
        assign qadd_pair_empty[qpm_g][qpm_s][qpm_m] =
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[qpm_m].RD_MSE.u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty;
        assign qadd_pair_full[qpm_g][qpm_s][qpm_m] =
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[qpm_m].RD_MSE.u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full;
        assign qadd_pair_qwr[qpm_g][qpm_s][qpm_m] =
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[qpm_m].RD_MSE.u_Memory_RD_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_wr_en;
        assign qadd_pair_ag_valid[qpm_g][qpm_s][qpm_m] =
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[qpm_m].RD_MSE.u_Memory_RD_Stream_Engine.mse_mem_ag_tag_valid;
        assign qadd_pair_ag_ready[qpm_g][qpm_s][qpm_m] =
          u_NDP_Top_new.slice_with_datahub_mc_group_gen[qpm_g].u_slice_with_datahub_mc_group.slice_group_gen[qpm_s].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[qpm_m].RD_MSE.u_Memory_RD_Stream_Engine.mse_mem_ag_bp_post;
      end
    end
  end
endgenerate

initial begin
  qadd_pair_snapshot_cycles = 0;
  for (int m=0; m<2; m++) begin
    qadd_pair_qwr_count[m] = 0;
    qadd_pair_ag_hs_count[m] = 0;
    for (int c=0; c<3; c++) qadd_pair_idx_hs[m][c] = 0;
  end
end

always @(posedge u_NDP_Top_new.clk_sg) begin
  if (u_NDP_Top_new.rst_n_sg && return_obs_enabled && return_obs_deep_enabled &&
      qadd_ingress_enabled && return_obs_active && qadd_ingress_stage_seq == 4) begin
    for (int m=0; m<2; m++) begin
      for (int c=0; c<3; c++)
        if (qadd_pair_idx_valid[return_obs_group_id][return_obs_local_slice_id][m][c] &&
            qadd_pair_idx_ready[return_obs_group_id][return_obs_local_slice_id][m][c])
          qadd_pair_idx_hs[m][c]++;
      if (qadd_pair_qwr[return_obs_group_id][return_obs_local_slice_id][m])
        qadd_pair_qwr_count[m]++;
      if (qadd_pair_ag_valid[return_obs_group_id][return_obs_local_slice_id][m] &&
          qadd_pair_ag_ready[return_obs_group_id][return_obs_local_slice_id][m])
        qadd_pair_ag_hs_count[m]++;
    end
  end
end

always @(posedge u_NDP_Top_new.clk_db) begin
  if (u_NDP_Top_new.rst_n_db && return_obs_enabled && return_obs_deep_enabled &&
      qadd_ingress_enabled && return_obs_fd != 0) begin
    qadd_pair_snapshot_cycles++;
    if (return_obs_active && qadd_ingress_stage_seq == 4 &&
        return_obs_heartbeat_period != 0 &&
        (qadd_pair_snapshot_cycles % return_obs_heartbeat_period) == 0) begin
      $fdisplay(return_obs_fd,
        "%0t | QADD_PAIR_MATRIX | stage_seq=%0d mse0_valid=0x%0h mse0_ready=0x%0h mse0_hs=%0d,%0d,%0d mse0_match=%0b mse0_empty=%0b mse0_full=%0b mse0_qwr=%0d mse0_ag=%0d mse1_valid=0x%0h mse1_ready=0x%0h mse1_hs=%0d,%0d,%0d mse1_match=%0b mse1_empty=%0b mse1_full=%0b mse1_qwr=%0d mse1_ag=%0d",
        $time, qadd_ingress_stage_seq,
        qadd_pair_idx_valid[return_obs_group_id][return_obs_local_slice_id][0],
        qadd_pair_idx_ready[return_obs_group_id][return_obs_local_slice_id][0],
        qadd_pair_idx_hs[0][0], qadd_pair_idx_hs[0][1], qadd_pair_idx_hs[0][2],
        qadd_pair_match[return_obs_group_id][return_obs_local_slice_id][0],
        qadd_pair_empty[return_obs_group_id][return_obs_local_slice_id][0],
        qadd_pair_full[return_obs_group_id][return_obs_local_slice_id][0],
        qadd_pair_qwr_count[0], qadd_pair_ag_hs_count[0],
        qadd_pair_idx_valid[return_obs_group_id][return_obs_local_slice_id][1],
        qadd_pair_idx_ready[return_obs_group_id][return_obs_local_slice_id][1],
        qadd_pair_idx_hs[1][0], qadd_pair_idx_hs[1][1], qadd_pair_idx_hs[1][2],
        qadd_pair_match[return_obs_group_id][return_obs_local_slice_id][1],
        qadd_pair_empty[return_obs_group_id][return_obs_local_slice_id][1],
        qadd_pair_full[return_obs_group_id][return_obs_local_slice_id][1],
        qadd_pair_qwr_count[1], qadd_pair_ag_hs_count[1]);
      $fflush(return_obs_fd);
    end
  end
end
'''


def materialize(parent: Path) -> Path:
    out = parent / TARGET_NAME
    shutil.copytree(SOURCE, out)
    for rel in ("workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"):
        p = out / rel
        text = p.read_text(encoding="utf-8")
        if SOURCE_NAME not in text:
            raise ValueError(f"source namespace absent: {rel}")
        p.write_text(text.replace(SOURCE_NAME, TARGET_NAME), encoding="utf-8", newline="\n")

    tail = out / "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
    text = tail.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "            qadd_ingress_enabled &&\n            return_obs_active\n",
        "            qadd_ingress_enabled\n",
    )
    text = replace_once(
        text,
        "            for (int qadd_ingress_mse = 0;",
        "            if (return_obs_active && qadd_ingress_stage_seq == 4) begin\n            for (int qadd_ingress_mse = 0;",
    )
    text = replace_once(
        text,
        "            end\n        end\n    end\n\n    // Low-rate snapshot",
        "            end\n            end\n        end\n    end\n\n    // Low-rate snapshot",
    )
    text = replace_once(
        text,
        "                return_obs_active &&\n                return_obs_heartbeat_period != 0 &&",
        "                return_obs_active &&\n                qadd_ingress_stage_seq == 4 &&\n                return_obs_heartbeat_period != 0 &&",
    )
    tail.write_text(text, encoding="utf-8", newline="\n")
    pair_tail = out / "tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"
    pair_tail.write_text(PAIR_TAIL.strip() + "\n", encoding="utf-8", newline="\n")
    native = out / "tb_probe/native_return_observer.svh"
    native_text = native.read_text(encoding="utf-8")
    native_text += '\n`include "qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"\n'
    native.write_text(native_text, encoding="utf-8", newline="\n")

    parser = out / "package_tools/qlinearadd_node0007_fp32_ingress_canonical_v19.py"
    ptext = parser.read_text(encoding="utf-8")
    ptext = replace_once(
        ptext,
        "    if not marker_present:\n",
        "    if last_stage != 4:\n"
        "        decision = \"PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE\"\n"
        "        boundary = \"FP32_INGRESS_EXACT_STAGE_SCOPE\"\n"
        "        reason = f\"expected stage_seq=4, observed {last_stage}\"\n"
        "    elif not marker_present:\n",
    )
    parser_v29 = out / "package_tools/qlinearadd_node0007_fp32_ingress_canonical_v29.py"
    parser_v29.write_text(ptext.replace("canonical-v19", "canonical-v29"), encoding="utf-8", newline="\n")

    runner = out / "PREPARE_AND_RUN.sh"
    rtext = runner.read_text(encoding="utf-8").replace(SOURCE_NAME, TARGET_NAME)
    rtext = rtext.replace("qlinearadd_node0007_fp32_ingress_canonical_v19.py", "qlinearadd_node0007_fp32_ingress_canonical_v29.py")
    runner.write_text(rtext, encoding="utf-8", newline="\n")

    matrix = {
        "schema": "qlinearadd-node0007-split-c-candidate-observation-matrix-v29",
        "target_stage_seq": 4,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidates": {
            "MSE0_INDEX_PAIR_STARVATION": ["mse0_valid/ready/hs", "mse0_match/empty/full/qwr", "mse0_req/rdata"],
            "MSE1_INDEX_PAIR_STARVATION": ["mse1_valid/ready/hs", "mse1_match/empty/full/qwr", "mse1_req/rdata"],
            "BUFFER0_DELIVERY_STALL": ["mse0_buf", "buf0_wr/arm_req/array", "buf_valid/arm_ready"],
            "BUFFER2_DELIVERY_STALL": ["mse1_buf", "buf2_wr/arm_req/array", "buf_valid/arm_ready"],
            "GA_OPERAND_CAPTURE_ASYMMETRY": ["ga0_capture", "ga1_capture"],
            "GA_PAIR_TAG_MASK_REJECT": ["ga_pair", "ga_accept"],
            "GA_OUTPUT_STALL": ["ga_accept", "ga_output"],
        },
        "interpretation": "qualified source-clock counters only; levels are state; all snapshots require exact stage_seq=4",
        "execution": "shortest legal cumulative prefix A+B+relocation+FP32; no host or unbound internal replay",
    }
    matrix_path = out / "diagnostics/candidate_observation_matrix.json"
    matrix_path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    readme = out / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(SOURCE_NAME, TARGET_NAME)
        + "\nV29 fixes exact cross-stage observer scope and adds the MSE0/MSE1 candidate matrix; workload and timeout are unchanged.\n",
        encoding="utf-8", newline="\n",
    )
    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET_NAME
    manifest["provenance"]["generator"] = "tools/build_qlinearadd_node0007_split_c_pairmatrix_v29_server_package.py"
    manifest["source_assets"]["split_c_ingress_v28_source_zip"] = {
        "path": f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE_NAME}.zip",
        "sha256": SOURCE_SHA,
        "immutable": True,
    }
    manifest["observer_contract"].update({
        "exact_stage_seq": 4,
        "stage_edge_history_updates_outside_return_obs_active": True,
        "candidate_matrix": "diagnostics/candidate_observation_matrix.json",
        "diagnostic_scope": "MSE0+MSE1 index queues/req/rdata through Buffer0+2 and dual GA ingress",
    })
    manifest["final_zip_rule_self_audit"] = {"required": True, "status": "PENDING_POST_BUILD_DIRECT_FINAL_ZIP_AUDIT"}
    manifest["files"] = file_records(out, exclude_manifest=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return out


def main() -> int:
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise ValueError("frozen v28 source differs")
    if TARGET.exists() or ZIP.exists():
        raise ValueError("fresh v29 identity already exists")
    with tempfile.TemporaryDirectory(prefix="qadd-v29-a-") as a, tempfile.TemporaryDirectory(prefix="qadd-v29-b-") as b:
        pa, pb = materialize(Path(a)), materialize(Path(b))
        za, zb = Path(a) / f"{TARGET_NAME}.zip", Path(b) / f"{TARGET_NAME}.zip"
        deterministic_zip(pa, za)
        deterministic_zip(pb, zb)
        if sha(za) != sha(zb):
            raise ValueError("deterministic double build differs")
        shutil.copytree(pa, TARGET)
        shutil.copy2(za, ZIP)
    sidecar = Path(str(ZIP) + ".sha256")
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    print(json.dumps({"zip": str(ZIP), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP), "sidecar_sha256": sha(sidecar)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
