from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v65_epoch_owner_successor_v66 as previous  # noqa: E402

SOURCE = "r5_n4_hw_v66_epoch_owner_diag"
INSTALL = "r5_n4_hw_v67_pe1_pair_diag"
SOURCE_SHA = "b0f4a0d83a82ccd1b039247da09318a1d9121ae08a9857f268a8568538050d1e"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v66_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v66_return_v67_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"replacement count differs: {old[:80]!r}")
    return text.replace(old, new, 1)


PE1_BLOCK = r'''

    // v67 PE1_PAIR_ACTUAL_CONSUMER_BEGIN
    // Qualified chain: logical LC15/LC9 capture -> PE1 match -> ALU/OB -> MSE4.
    bit return_obs_p1_enabled;
    integer return_obs_p1_limit;
    integer return_obs_p1_plusarg_status;
    integer return_obs_p1_records;
    longint unsigned return_obs_p1_lc15_in0;
    longint unsigned return_obs_p1_lc9_in2;
    longint unsigned return_obs_p1_match;
    longint unsigned return_obs_p1_ob_wr;
    longint unsigned return_obs_p1_ob_rd;
    longint unsigned return_obs_p1_out;
    longint unsigned return_obs_p1_mse1;
    logic [2:0] return_obs_p1_prev_in_valid;
    logic [2:0] return_obs_p1_prev_buf_valid;
    logic [11:0] return_obs_p1_prev_buf_index;

    initial begin
        return_obs_p1_enabled = $test$plusargs("RETURN_OBS_PE1_PAIR");
        return_obs_p1_limit = 128;
        return_obs_p1_plusarg_status = $value$plusargs(
            "RETURN_OBS_PE1_PAIR_LIMIT=%d", return_obs_p1_limit
        );
        return_obs_p1_records = 0;
        return_obs_p1_lc15_in0 = 0;
        return_obs_p1_lc9_in2 = 0;
        return_obs_p1_match = 0;
        return_obs_p1_ob_wr = 0;
        return_obs_p1_ob_rd = 0;
        return_obs_p1_out = 0;
        return_obs_p1_mse1 = 0;
        return_obs_p1_prev_in_valid = 0;
        return_obs_p1_prev_buf_valid = 0;
        return_obs_p1_prev_buf_index = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_PE1_PAIR enabled=%0d limit_name=RETURN_OBS_PE1_PAIR_LIMIT limit=%0d schema=PE1_PAIR",
                return_obs_p1_enabled, return_obs_p1_limit);
            $fflush(return_obs_fd);
        end
    end

    task automatic return_obs_write_pe1_pair(input string event_name);
        if (return_obs_p1_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "%0t | PE1_PAIR_V1 | event=%s lc15_in0=%0d lc9_in2=%0d match=%0d ob_wr=%0d ob_rd=%0d pe_out=%0d mse1=%0d in_valid=%h in_masked=%h gotten=%h in_last=%h in_index=%h buf_valid=%h buf_last=%h buf_index=%h bp=%h matched=%0d alu_tag=%h ob_count=%0d pe_port=%h pe_bp=%h mse1_tag=%h mse1_bp=%0d lc15_port=%h lc15_bp=%h lc9_port=%h lc9_bp=%h",
                $time, event_name,
                return_obs_p1_lc15_in0, return_obs_p1_lc9_in2,
                return_obs_p1_match, return_obs_p1_ob_wr,
                return_obs_p1_ob_rd, return_obs_p1_out,
                return_obs_p1_mse1,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inport_valid_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inport_valid_bit_masked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_gotten_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inport_last_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inport_last_index,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_valid_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_last_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_last_index,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.iga_pe_inbuffer_bp_pre,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_matched,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.iga_pe_alu_result_tag,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Outbuffer.iga_pe_outbuffer_count,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport_bp_post[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_tag[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.mse_mem_queue_bp_pre[1],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[17],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[17],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[9],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9]
            );
            $fflush(return_obs_fd);
        end
    endtask

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit p1_in0, p1_in2, p1_match, p1_ob_wr, p1_ob_rd, p1_out, p1_mse1;
        bit p1_state_change;
        logic [2:0] p1_in_valid, p1_buf_valid;
        logic [11:0] p1_buf_index;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_p1_records = 0;
            return_obs_p1_lc15_in0 = 0; return_obs_p1_lc9_in2 = 0;
            return_obs_p1_match = 0; return_obs_p1_ob_wr = 0;
            return_obs_p1_ob_rd = 0; return_obs_p1_out = 0;
            return_obs_p1_mse1 = 0; return_obs_p1_prev_in_valid = 0;
            return_obs_p1_prev_buf_valid = 0; return_obs_p1_prev_buf_index = 0;
        end else if (return_obs_p1_enabled && return_obs_active) begin
            p1_in0 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_enbale[0];
            p1_in2 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_enbale[2];
            p1_match = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_matched;
            p1_ob_wr = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Outbuffer.normal_mode_wr_handshake;
            p1_ob_rd = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Outbuffer.normal_mode_rd_handshake;
            p1_out = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport[1][22] && &u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_pe_outport_bp_post[1];
            p1_mse1 = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_same_gotten_masked[1] && u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre[1];
            p1_in_valid = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inport_valid_bit;
            p1_buf_valid = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_valid_bit;
            p1_buf_index = u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_PE[1].u_IGA_PE.u_IGA_PE_Inbuffer.iga_pe_inbuffer_last_index;
            p1_state_change = p1_in_valid != return_obs_p1_prev_in_valid || p1_buf_valid != return_obs_p1_prev_buf_valid || p1_buf_index != return_obs_p1_prev_buf_index;
            if (p1_in0) return_obs_p1_lc15_in0++;
            if (p1_in2) return_obs_p1_lc9_in2++;
            if (p1_match) return_obs_p1_match++;
            if (p1_ob_wr) return_obs_p1_ob_wr++;
            if (p1_ob_rd) return_obs_p1_ob_rd++;
            if (p1_out) return_obs_p1_out++;
            if (p1_mse1) return_obs_p1_mse1++;
            if ((p1_in0 || p1_in2 || p1_match || p1_ob_wr || p1_ob_rd || p1_out || p1_mse1 || p1_state_change) && return_obs_p1_records < return_obs_p1_limit) begin
                return_obs_p1_records++;
                return_obs_write_pe1_pair("QUALIFIED_OR_STATE_EDGE");
            end
            return_obs_p1_prev_in_valid = p1_in_valid;
            return_obs_p1_prev_buf_valid = p1_buf_valid;
            return_obs_p1_prev_buf_index = p1_buf_index;
        end
    end
    // v67 PE1_PAIR_ACTUAL_CONSUMER_END
'''


def configure() -> None:
    previous.SOURCE = SOURCE
    previous.INSTALL = INSTALL
    previous.SOURCE_SHA = SOURCE_SHA
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    previous.configure()


def build_directory(output: Path) -> Path:
    configure()
    with tempfile.TemporaryDirectory(prefix="node0004-v67-source-") as td:
        source = base.extract_source(Path(td))
        package = output / INSTALL
        if package.exists(): raise BuildError(f"refusing to overwrite {package}")
        shutil.copytree(source, package)
    base.replace_identity(package)
    op = package / "tb_probe/native_return_observer.svh"
    observer = op.read_text(encoding="utf-8")
    observer = observer.replace("logic [17:0] return_obs_eo_prev_tag", "logic [6:0] return_obs_eo_prev_tag")
    observer = observer.replace("logic [20:0] return_obs_eo_prev_lc", "logic [22:0] return_obs_eo_prev_lc")
    if observer.count("logic [6:0] return_obs_eo_prev_tag") != 3 or observer.count("logic [22:0] return_obs_eo_prev_lc") != 3:
        raise BuildError("v66 observer width correction count differs")
    observer = once(observer, '                return_obs_write_epoch_owner("DIAG_DECISION");\n',
                    '                return_obs_write_epoch_owner("DIAG_DECISION");\n                return_obs_write_pe1_pair("DIAG_DECISION");\n')
    observer += PE1_BLOCK
    op.write_text(observer, encoding="utf-8", newline="\n")

    rp = package / "PREPARE_AND_RUN.sh"
    runner = rp.read_text(encoding="utf-8")
    token = "+RETURN_OBS_EPOCH_OWNER +RETURN_OBS_EPOCH_OWNER_LIMIT=128"
    if runner.count(token) != 2: raise BuildError("epoch argv count differs")
    runner = runner.replace(token, token + " +RETURN_OBS_PE1_PAIR +RETURN_OBS_PE1_PAIR_LIMIT=128")
    rp.write_text(runner, encoding="utf-8", newline="\n")

    runtime_path = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime = runtime_path.read_text(encoding="utf-8")
    needle = '''    {
        "feature": "RETURN_OBS_EPOCH_OWNER",
        "enable": "+RETURN_OBS_EPOCH_OWNER",
        "limits": ("+RETURN_OBS_EPOCH_OWNER_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_EPOCH_OWNER", "enabled=1", "limit=128",
        ),
    },
'''
    addition = needle + '''    {
        "feature": "RETURN_OBS_PE1_PAIR",
        "enable": "+RETURN_OBS_PE1_PAIR",
        "limits": ("+RETURN_OBS_PE1_PAIR_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_PE1_PAIR", "enabled=1", "limit=128",
        ),
    },
'''
    runtime = once(runtime, needle, addition)
    runtime_path.write_text(runtime, encoding="utf-8", newline="\n")

    manifest_path = package / "package_manifest.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_sha, new_sha = old["observer_sha256"], base.sha256(op)
    manifest = base.replace_hash(old, old_sha, new_sha)
    manifest.update({"install_name":INSTALL,"source_package_sha256":SOURCE_SHA,
                     "status":"PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
                     "observer_sha256":new_sha,"classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                     "candidate_release":False,"configuration_rebuilt":False,
                     "configuration_rebuilt_in_this_successor":False,"mapping_rebuilt":False,
                     "bitstream_rebuilt":False,"execplan_rebuilt":False,"sca_semantics_rebuilt":False,
                     "numeric_analysis_repeated":False,"node0004_workload_rebuilt":False,
                     "functional_rtl_modified":False,"server_action":False})
    manifest.setdefault("diagnostic_features", {})["RETURN_OBS_PE1_PAIR"] = {
        "runtime_enable_parameter":"+RETURN_OBS_PE1_PAIR","limit_parameter":"+RETURN_OBS_PE1_PAIR_LIMIT=128",
        "time_zero_marker":"DIAGNOSTIC_FEATURE_ENABLE_V1","edge_schema":"PE1_PAIR_V1",
        "boundary_schema":"PE1_PAIR_V1","clock":"u_NDP_Top_new.clk_db","reset":"u_NDP_Top_new.rst_n_db",
        "progress_semantics":"qualified handshakes only; state transitions are explicitly labeled non-progress"}
    base.write_json(package / "provenance/v66_to_v67_pe1_pair.json", {
        "schema":"node0004-v66-to-v67-pe1-pair-v1","source_v66_sha256":SOURCE_SHA,
        "v66_return_sha256":"c7dc6b54a7a2c47ca538cb99232b452377996fd5d1bc2558f7a0f4468261d80d",
        "analysis_sha256":base.sha256(ANALYSIS),
        "changed_surface":["fresh identity","v66 observer shadow width correction","PE1 pair causal observer","runtime feature binding"],
        "candidate_observation_matrix":{
            "LC15_missing_at_PE1_in0":"LC15/in0 capture counter and tags",
            "PE1_epoch_tag_mismatch":"per-port input/buffer valid,last,index and matched",
            "PE1_pipeline_or_outbuffer":"matched, ALU tag, outbuffer write/read and PE output",
            "MSE4_input1_rejection":"PE output vs MSE4 input1 acceptance"},
        "frozen":["numeric/W3/qparams/tail/workload/config/golden","timeout/backpressure","functional RTL/ISA/hardware/active ndp-sim"]})
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package); base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT); a=ap.parse_args()
    out=a.output_root.resolve(); out.mkdir(parents=True, exist_ok=True)
    package=build_directory(out); archive=out/f"{INSTALL}.zip"; base.deterministic_zip(package, archive); digest=base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v67-repeat-") as td:
        repeat=build_directory(Path(td)); rz=Path(td)/f"{INSTALL}.zip"; base.deterministic_zip(repeat,rz); deterministic=base.sha256(rz)==digest
    if not deterministic: raise BuildError("deterministic rebuild differs")
    sidecar=out/f"{INSTALL}.zip.sha256"; sidecar.write_text(f"{digest}  {archive.name}\n",encoding="ascii",newline="\n")
    report={"schema":"node0004-v66-to-v67-pe1-pair-build-v1","status":"PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
            "zip":str(archive),"zip_bytes":archive.stat().st_size,"zip_sha256":digest,"sidecar":str(sidecar),
            "deterministic_rebuild_equal":deterministic,"source_v66_sha256":SOURCE_SHA,
            "classification":"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX","numeric_analysis_repeated":False,
            "node0004_workload_rebuilt":False,"configuration_rebuilt":False,"functional_rtl_modified":False,"server_action":False}
    base.write_json(out/f"{INSTALL}.build.json",report); print(json.dumps(report,indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
