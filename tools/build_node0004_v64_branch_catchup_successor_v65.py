from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v63_dskew_successor_v64 as previous  # noqa: E402


SOURCE = "r5_n4_hw_v64_dskew_diag"
INSTALL = "r5_n4_hw_v65_branchcatch_diag"
SOURCE_SHA = "8d4bce53f152e829973212a0cf8403c59a86c588a62ef9f11ab5e90937dd2268"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
ANALYSIS = ROOT / "outputs/conv_node0004_v64_recovered_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v64_return_v65_successor/build"
base = previous.base


class BuildError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise BuildError(f"replacement count {count} for {old!r}")
    return text.replace(old, new)


BRANCH_BLOCK = r'''

    // v65 BRANCH_CATCHUP_ACTUAL_CONSUMER_BEGIN
    // v65: qualified branch-catchup snapshot. It is triggered by the
    // descriptor-empty epoch edge and subsequent qualified counter changes;
    // held levels do not count as progress.
    bit return_obs_bc_enabled;
    integer return_obs_bc_limit;
    integer return_obs_bc_plusarg_status;
    integer return_obs_bc_records;
    longint unsigned return_obs_bc_prev_terminal;
    longint unsigned return_obs_bc_prev_match;
    longint unsigned return_obs_bc_prev_buf_push;
    longint unsigned return_obs_bc_prev_lc13;
    longint unsigned return_obs_bc_prev_lc14;
    longint unsigned return_obs_bc_prev_lc15;
    longint unsigned return_obs_bc_prev_pe7;

    initial begin
        return_obs_bc_enabled = $test$plusargs("RETURN_OBS_BRANCH_CATCHUP");
        return_obs_bc_limit = 64;
        return_obs_bc_plusarg_status = $value$plusargs(
            "RETURN_OBS_BRANCH_CATCHUP_LIMIT=%d", return_obs_bc_limit
        );
        return_obs_bc_records = 0;
        return_obs_bc_prev_terminal = 0;
        return_obs_bc_prev_match = 0;
        return_obs_bc_prev_buf_push = 0;
        return_obs_bc_prev_lc13 = 0;
        return_obs_bc_prev_lc14 = 0;
        return_obs_bc_prev_lc15 = 0;
        return_obs_bc_prev_pe7 = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_BRANCH_CATCHUP enabled=%0d limit_name=RETURN_OBS_BRANCH_CATCHUP_LIMIT limit=%0d schema=BRANCH_CATCHUP",
                return_obs_bc_enabled, return_obs_bc_limit
            );
            $fflush(return_obs_fd);
        end
    end

    task automatic return_obs_write_branch_catchup(input string event_name);
        if (return_obs_bc_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "%0t | BRANCH_CATCHUP_V1 | event=%s desc_terminal=%0d desc=%0d prepared=%0d delta=%0d mem_vld=%h mem_same=%h mem_gotten=%h mem_masked=%h mem_bp=%h mem_match=%0d mem_q_full=%0d mem_q_empty=%0d lc13=%h lc13_bp=%h lc14=%h lc14_bp=%h lc15=%h lc15_bp=%h lc9=%h lc9_bp=%h pe7_wr=%0d pe7_rd=%0d buf_push=%0d buf_pop=%0d row_full=%0d col_full=%0d bufq_full=%0d prepared_count=%0d prepared_bp=%0d",
                $time, event_name,
                return_obs_wt_desc_terminal,
                return_obs_md_desc_hs,
                return_obs_md_prepared_wr,
                return_obs_md_prepared_wr - return_obs_md_desc_hs,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_unmasked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_same_bit_unmasked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_gotten_bit,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_idx_valid_bit_masked,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mse_mem_queue_bp_pre,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_all_idx_matched,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue.mem_ag_idx_queue_empty,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[6],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[6],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[8],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[8],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[17],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[17],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport[9],
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.iga_lc_outport_bp_post[9],
                return_obs_lp_pe7_write, return_obs_lp_pe7_read,
                return_obs_rb_buf_push, return_obs_rb_buf_pop,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_ROW_LC[4].u_IGA_ROW_LC.u_IGA_ROW_LC_Counter.iga_row_lc_outbuf_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array.IGA_COL_LC[4].u_IGA_COL_LC.u_IGA_COL_LC_Counter.iga_col_lc_outbuf_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue.buf_ag_idx_queue_full,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_data_chl_prepared_data_cnt,
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_WR_Data_Channel.wr_chl_prepared_data_bp_pre
            );
            $fflush(return_obs_fd);
        end
    endtask

    always @(negedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit bc_changed;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_bc_records = 0;
            return_obs_bc_prev_terminal = 0;
            return_obs_bc_prev_match = 0;
            return_obs_bc_prev_buf_push = 0;
            return_obs_bc_prev_lc13 = 0;
            return_obs_bc_prev_lc14 = 0;
            return_obs_bc_prev_lc15 = 0;
            return_obs_bc_prev_pe7 = 0;
        end else if (return_obs_bc_enabled && return_obs_active) begin
            bc_changed =
                return_obs_wt_desc_terminal != return_obs_bc_prev_terminal ||
                return_obs_mi_match != return_obs_bc_prev_match ||
                return_obs_rb_buf_push != return_obs_bc_prev_buf_push ||
                return_obs_lx_13_out != return_obs_bc_prev_lc13 ||
                return_obs_lx_14_out != return_obs_bc_prev_lc14 ||
                return_obs_lx_15_out != return_obs_bc_prev_lc15 ||
                return_obs_lp_pe7_write != return_obs_bc_prev_pe7;
            if (return_obs_wt_desc_terminal >= 2 && bc_changed &&
                return_obs_bc_records < return_obs_bc_limit) begin
                return_obs_bc_records++;
                return_obs_write_branch_catchup("QUALIFIED_CHANGE");
            end
            return_obs_bc_prev_terminal = return_obs_wt_desc_terminal;
            return_obs_bc_prev_match = return_obs_mi_match;
            return_obs_bc_prev_buf_push = return_obs_rb_buf_push;
            return_obs_bc_prev_lc13 = return_obs_lx_13_out;
            return_obs_bc_prev_lc14 = return_obs_lx_14_out;
            return_obs_bc_prev_lc15 = return_obs_lx_15_out;
            return_obs_bc_prev_pe7 = return_obs_lp_pe7_write;
        end
    end
    // v65 BRANCH_CATCHUP_ACTUAL_CONSUMER_END
'''


def configure_base() -> None:
    base.SOURCE = SOURCE
    base.INSTALL = INSTALL
    base.SOURCE_SHA = SOURCE_SHA
    base.SOURCE_ZIP = SOURCE_ZIP
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT


def extract_and_reidentify(output: Path) -> Path:
    configure_base()
    with tempfile.TemporaryDirectory(prefix="node0004-v65-source-") as temp:
        source = base.extract_source(Path(temp))
        package = output / INSTALL
        if package.exists():
            raise BuildError("refusing to overwrite v65 package")
        shutil.copytree(source, package)
    base.replace_identity(package)
    return package


def patch_observer(package: Path) -> tuple[str, str]:
    path = package / "tb_probe/native_return_observer.svh"
    old_sha = base.sha256(path)
    text = path.read_text(encoding="utf-8")
    if "RETURN_OBS_BRANCH_CATCHUP" in text:
        raise BuildError("source observer already contains branch-catchup feature")
    text = replace_once(
        text,
        '                return_obs_write_dskew_state("DIAG_DECISION");\n',
        '                return_obs_write_dskew_state("DIAG_DECISION");\n'
        '                return_obs_write_branch_catchup("DIAG_DECISION");\n',
    )
    text += BRANCH_BLOCK
    path.write_text(text, encoding="utf-8", newline="\n")
    return old_sha, base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    needle = "+RETURN_OBS_DSKEW +RETURN_OBS_DSKEW_LIMIT=128"
    if text.count(needle) != 2:
        raise BuildError("runner DSKEW plusarg occurrence count differs")
    text = text.replace(
        needle,
        needle
        + " +RETURN_OBS_BRANCH_CATCHUP +RETURN_OBS_BRANCH_CATCHUP_LIMIT=64",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    old = '''def collect(
    server_root: Path,
    ndp_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    result = _base_collect(
        server_root, ndp_root, install_name, evidence_root, run_root
    )
    return_zip = server_root / f"{install_name}_return.zip"
'''
    new = '''def collect(
    server_root: Path,
    ndp_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    return_zip: Path,
) -> dict[str, Any]:
    result = _base_collect(
        server_root, ndp_root, install_name, evidence_root, run_root, return_zip
    )
'''
    text = replace_once(text, old, new)
    needle = '''    {
        "feature": "RETURN_OBS_DSKEW",
        "enable": "+RETURN_OBS_DSKEW",
        "limits": ("+RETURN_OBS_DSKEW_LIMIT=128",),
        "marker_tokens": (
            "feature=RETURN_OBS_DSKEW", "enabled=1", "limit=128",
        ),
    },
'''
    addition = needle + '''    {
        "feature": "RETURN_OBS_BRANCH_CATCHUP",
        "enable": "+RETURN_OBS_BRANCH_CATCHUP",
        "limits": ("+RETURN_OBS_BRANCH_CATCHUP_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_BRANCH_CATCHUP", "enabled=1", "limit=64",
        ),
    },
'''
    text = replace_once(text, needle, addition)
    path.write_text(text, encoding="utf-8", newline="\n")


def update_metadata(package: Path, old_sha: str, new_sha: str) -> None:
    base.write_json(
        package / "provenance/v64_to_v65_branch_catchup.json",
        {
            "schema": "node0004-v64-to-v65-branch-catchup-v1",
            "source_v64_sha256": SOURCE_SHA,
            "v64_return_analysis": {
                "path": ANALYSIS.relative_to(ROOT).as_posix(),
                "sha256": base.sha256(ANALYSIS),
                "last_proven_good": (
                    "first two transient descriptor-empty windows recover"
                ),
                "first_divergence": (
                    "third descriptor-empty leaves delta2 with Memory_AG empty "
                    "and Buffer branch full"
                ),
            },
            "changed_surface": [
                "fresh identity",
                "qualified RETURN_OBS_BRANCH_CATCHUP snapshots",
                "runtime feature binding",
                "return collector six-argument ABI repair",
                "manifest and return identity projection",
            ],
            "candidate_observation_matrix": {
                "shared_source_partial_capture": "LC/bp vector differs by consumer",
                "lc_terminal_or_keep_stop": "physical LC13/14/15 ports stop before Memory_AG match",
                "memory_ag_same_gotten_suppression": "unmasked valid exists but masked vector remains incomplete",
                "buffer_branch_early_epoch_accept": "Buffer push/queue full advances without address tuple",
            },
            "frozen": [
                "numeric/W3/qparams/tail/workload/config/golden",
                "mapping/bitstream/execplan/SCA semantics",
                "timeout/backpressure",
                "functional RTL/ISA/hardware/active ndp-sim",
            ],
        },
    )
    readme = package / "README.md"
    readme.write_text(
        "# node0004 v65 branch-catchup diagnostic\n\n"
        "This package freezes v64 computation and adds a qualified snapshot of "
        "the address and Buffer fanout at the third descriptor-empty epoch. "
        "It also repairs the package-local return collector ABI exposed when "
        "v64 was reissued for repeat execution.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "The final return ZIP is atomically published under "
        "`/home/panqs/ndp/simresult`.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = base.replace_hash(manifest, old_sha, new_sha)
    manifest.update(
        {
            "install_name": INSTALL,
            "source_package_sha256": SOURCE_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "mapping_rebuilt": False,
            "bitstream_rebuilt": False,
            "execplan_rebuilt": False,
            "sca_semantics_rebuilt": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
            "observer_sha256": new_sha,
        }
    )
    manifest["v64_return_reanalysis"] = {
        "return_sha256": (
            "755d653ae220fe46d3cd7b026229c459455c5c5ae6bc1c70728f139120ad7bae"
        ),
        "valid_recovered_return": True,
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_expected": 320,
        "first_divergence": (
            "THIRD_DESCRIPTOR_EMPTY_DESC18_PREPARED20_SHARED_BRANCH_CATCHUP"
        ),
    }
    manifest.setdefault("diagnostic_features", {})[
        "RETURN_OBS_BRANCH_CATCHUP"
    ] = {
        "runtime_enable_parameter": "+RETURN_OBS_BRANCH_CATCHUP",
        "limit_parameter": "+RETURN_OBS_BRANCH_CATCHUP_LIMIT=64",
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1",
        "edge_schema": "BRANCH_CATCHUP_V1",
        "boundary_schema": "BRANCH_CATCHUP_V1",
        "clock": "u_NDP_Top_new.clk_db",
        "reset": "u_NDP_Top_new.rst_n_db",
        "progress_semantics": "qualified changes only; held levels are snapshots",
    }
    base.refresh_receipts(manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)


def build_directory(output: Path) -> Path:
    package = extract_and_reidentify(output)
    old_sha, new_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    update_metadata(package, old_sha, new_sha)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for path in (
        output / INSTALL,
        output / f"{INSTALL}.zip",
        output / f"{INSTALL}.zip.sha256",
        output / f"{INSTALL}.validation.json",
    ):
        if path.exists():
            raise BuildError(f"refusing to overwrite {path}")
    package = build_directory(output)
    zip_path = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v65-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v65 deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v64-to-v65-branch-catchup-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v64_sha256": SOURCE_SHA,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "collector_abi_repaired": True,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(output / f"{INSTALL}.validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
