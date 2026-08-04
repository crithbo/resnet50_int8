from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v30_mse4_index_diag_package_v32 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v32_mse4_index_diag"
INSTALL_NAME = "r5_n4_hw_v33_lc18_pe7_diag"
SOURCE_SHA256 = "87a3e3474c3c1fbd28a8a4220919a8249c310c915da87bba58c28a7e6d8eb835"
RETURN_SHA256 = "757c64ad8232e6dbad311eb29864c4c20f692c7585eec7e8d6156bbc100bfbed"
SERVER_RULE_SHA256 = "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
RTL_COMMIT = "d0aa87f682880a260fb792aaac88f70a23aba414"
RTL_SYNC_REPORT = (
    ROOT / "artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json"
)
RTL_SYNC_REPORT_SHA256 = (
    "fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
MAPPING_CACHE = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-transout-threshold-fix-c0-v5/mapping/conv/op_w0/"
    "mapping_cache/72d2720125714878.json"
)
MAPPING_REVIEW = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-transout-threshold-fix-c0-v5/mapping/conv/op_w0/"
    "mapping_review.json"
)
RTL_LEAVES = (
    "NDP_copy01/rtl/Slice/Index_Generation_Array/Index_Generation_Array.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_Interconnect.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC_Counter.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE_Outbuffer.sv",
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv",
)


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v32 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v32 source CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v32 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def iga(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_Index_Generation_Array"
        f".{leaf}"
    )


def lc(index: int, leaf: str) -> str:
    return iga(f"IGA_LC[{index}].u_IGA_LC.{leaf}")


def pe7(leaf: str) -> str:
    return iga(f"IGA_PE[7].u_IGA_PE.{leaf}")


def mse_queue(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
        f".u_Memory_AG_Idx_Queue.{leaf}"
    )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "LC18_PE7_BOUNDARY_V1" in text:
        raise BuildError("v33 physical LC/PE diagnostic already present")
    call = "                return_obs_write_mse4_index_state(event_name);"
    if text.count(call) != 1:
        raise BuildError("observer decision hook anchor differs")
    text = text.replace(
        call,
        call + "\n                return_obs_write_lc18_pe7_state(event_name);",
        1,
    )
    block = f'''

    // v33: mapped physical LC17/LC18/PE7 -> WRITE_STREAM0 input1 boundary.
    // Only qualified captures/writes/reads are progress; tags/ready/valid are state.
    bit return_obs_lp_enabled;
    integer return_obs_lp_limit;
    integer return_obs_lp_plusarg_status;
    integer return_obs_lp_edge_records;
    longint unsigned return_obs_lp_lc17_out;
    longint unsigned return_obs_lp_lc18_parent;
    longint unsigned return_obs_lp_lc18_out;
    longint unsigned return_obs_lp_pe7_in0;
    longint unsigned return_obs_lp_pe7_in2;
    longint unsigned return_obs_lp_pe7_write;
    longint unsigned return_obs_lp_pe7_read;
    longint unsigned return_obs_lp_mse_input1;

    initial begin
        return_obs_lp_enabled = $test$plusargs("RETURN_OBS_LC18_PE7");
        return_obs_lp_limit = 96;
        return_obs_lp_plusarg_status = $value$plusargs(
            "RETURN_OBS_LC18_PE7_LIMIT=%d", return_obs_lp_limit
        );
        return_obs_lp_edge_records = 0;
        return_obs_lp_lc17_out = 0;
        return_obs_lp_lc18_parent = 0;
        return_obs_lp_lc18_out = 0;
        return_obs_lp_pe7_in0 = 0;
        return_obs_lp_pe7_in2 = 0;
        return_obs_lp_pe7_write = 0;
        return_obs_lp_pe7_read = 0;
        return_obs_lp_mse_input1 = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_LC18_PE7 enabled=%0d limit_name=RETURN_OBS_LC18_PE7_LIMIT limit=%0d",
                return_obs_lp_enabled, return_obs_lp_limit);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit lp_lc17_out;
        bit lp_lc18_parent;
        bit lp_lc18_out;
        bit lp_pe7_in0;
        bit lp_pe7_in2;
        bit lp_pe7_write;
        bit lp_pe7_read;
        bit lp_mse_input1;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_lp_edge_records = 0;
            return_obs_lp_lc17_out = 0;
            return_obs_lp_lc18_parent = 0;
            return_obs_lp_lc18_out = 0;
            return_obs_lp_pe7_in0 = 0;
            return_obs_lp_pe7_in2 = 0;
            return_obs_lp_pe7_write = 0;
            return_obs_lp_pe7_read = 0;
            return_obs_lp_mse_input1 = 0;
        end else if (return_obs_lp_enabled && return_obs_active) begin
            lp_lc17_out = {lc(17, 'u_IGA_LC_Counter.iga_lc_cnt_outport_valid_bit')} &&
                          {lc(17, 'iga_lc_cnt_bp_post')};
            lp_lc18_parent = {lc(18, 'iga_lc_inbuffer_valid_bit')} &&
                             {lc(18, 'iga_lc_cnt_bp_pre')};
            lp_lc18_out = {lc(18, 'u_IGA_LC_Counter.iga_lc_cnt_outport_valid_bit')} &&
                          {lc(18, 'iga_lc_cnt_bp_post')};
            lp_pe7_in0 = {pe7('u_IGA_PE_Inbuffer.iga_pe_inbuffer_enbale[0]')};
            lp_pe7_in2 = {pe7('u_IGA_PE_Inbuffer.iga_pe_inbuffer_enbale[2]')};
            lp_pe7_write = {pe7('u_IGA_PE_Outbuffer.normal_mode_wr_handshake')};
            lp_pe7_read = {pe7('u_IGA_PE_Outbuffer.normal_mode_rd_handshake')};
            lp_mse_input1 = {mse_queue('mse_mem_queue_bp_pre[1]')} &&
                            {mse_queue('mem_idx_valid_same_gotten_masked[1]')};
            if (lp_lc17_out) return_obs_lp_lc17_out++;
            if (lp_lc18_parent) return_obs_lp_lc18_parent++;
            if (lp_lc18_out) return_obs_lp_lc18_out++;
            if (lp_pe7_in0) return_obs_lp_pe7_in0++;
            if (lp_pe7_in2) return_obs_lp_pe7_in2++;
            if (lp_pe7_write) return_obs_lp_pe7_write++;
            if (lp_pe7_read) return_obs_lp_pe7_read++;
            if (lp_mse_input1) return_obs_lp_mse_input1++;
            if (return_obs_lp_edge_records < return_obs_lp_limit &&
                (lp_lc17_out || lp_lc18_parent || lp_lc18_out || lp_pe7_in0 ||
                 lp_pe7_in2 || lp_pe7_write || lp_pe7_read || lp_mse_input1)) begin
                $fdisplay(return_obs_fd,
                    "%0t | LC18_PE7_EDGE_V1 | n=%0d edge=0x%0h lc17_port=0x%0h lc17_bp=0x%0h lc18_port=0x%0h lc18_bp=0x%0h pe7_in_valid=0x%0h pe7_in_last=0x%0h pe7_in_index=0x%0h pe7_in_bp=0x%0h pe7_matched=%0d pe7_alu_tag=0x%0h pe7_out=0x%0h pe7_ob_count=%0d mse_in1_valid=%0d mse_in1_same=%0d mse_in1_bp=%0d mse_gotten1=%0d",
                    $time, return_obs_lp_edge_records + 1,
                    {{lp_mse_input1, lp_pe7_read, lp_pe7_write, lp_pe7_in2,
                      lp_pe7_in0, lp_lc18_out, lp_lc18_parent, lp_lc17_out}},
                    {lc(17, 'iga_lc_outport')},
                    {iga('iga_lc_outport_bp_post[17]')},
                    {lc(18, 'iga_lc_outport')},
                    {iga('iga_lc_outport_bp_post[18]')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inport_valid_bit')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inport_last_bit')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inport_last_index')},
                    {pe7('iga_pe_inbuffer_bp_pre')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inbuffer_matched')},
                    {pe7('iga_pe_alu_result_tag')},
                    {pe7('iga_pe_outport')},
                    {pe7('u_IGA_PE_Outbuffer.iga_pe_outbuffer_count')},
                    {mse_queue('mem_idx_valid_bit_unmasked[1]')},
                    {mse_queue('mem_idx_same_bit_unmasked[1]')},
                    {mse_queue('mse_mem_queue_bp_pre[1]')},
                    {mse_queue('mem_idx_gotten_bit[1]')});
                return_obs_lp_edge_records++;
                $fflush(return_obs_fd);
            end
        end
    end

    task automatic return_obs_write_lc18_pe7_state(input string event_name);
        begin
            if (return_obs_lp_enabled && return_obs_fd != 0) begin
                $fdisplay(return_obs_fd,
                    "%0t | LC18_PE7_BOUNDARY_V1 | event=%s lc17_out=%0d lc18_parent=%0d lc18_out=%0d pe7_in0=%0d pe7_in2=%0d pe7_write=%0d pe7_read=%0d mse_input1=%0d lc17_port=0x%0h lc17_bp=0x%0h lc18_port=0x%0h lc18_bp=0x%0h pe7_in_valid=0x%0h pe7_in_last=0x%0h pe7_in_index=0x%0h pe7_in_bp=0x%0h pe7_matched=%0d pe7_alu_tag=0x%0h pe7_out=0x%0h pe7_ob_count=%0d mse_in1_valid=%0d mse_in1_same=%0d mse_in1_bp=%0d mse_gotten1=%0d",
                    $time, event_name,
                    return_obs_lp_lc17_out, return_obs_lp_lc18_parent,
                    return_obs_lp_lc18_out, return_obs_lp_pe7_in0,
                    return_obs_lp_pe7_in2, return_obs_lp_pe7_write,
                    return_obs_lp_pe7_read, return_obs_lp_mse_input1,
                    {lc(17, 'iga_lc_outport')},
                    {iga('iga_lc_outport_bp_post[17]')},
                    {lc(18, 'iga_lc_outport')},
                    {iga('iga_lc_outport_bp_post[18]')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inport_valid_bit')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inport_last_bit')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inport_last_index')},
                    {pe7('iga_pe_inbuffer_bp_pre')},
                    {pe7('u_IGA_PE_Inbuffer.iga_pe_inbuffer_matched')},
                    {pe7('iga_pe_alu_result_tag')},
                    {pe7('iga_pe_outport')},
                    {pe7('u_IGA_PE_Outbuffer.iga_pe_outbuffer_count')},
                    {mse_queue('mem_idx_valid_bit_unmasked[1]')},
                    {mse_queue('mem_idx_same_bit_unmasked[1]')},
                    {mse_queue('mse_mem_queue_bp_pre[1]')},
                    {mse_queue('mem_idx_gotten_bit[1]')});
                $fflush(return_obs_fd);
            end
        end
    endtask
'''
    path.write_text(text + block, encoding="utf-8", newline="\n")
    return base.sha256(path)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    token = "+RETURN_OBS_MSE4_INDEX_LIMIT=96"
    if text.count(token) != 2:
        raise BuildError("runner feature anchor differs")
    text = text.replace(
        token,
        token + " +RETURN_OBS_LC18_PE7 +RETURN_OBS_LC18_PE7_LIMIT=96",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = '''    {
        "feature": "RETURN_OBS_MSE4_INDEX",
        "enable": "+RETURN_OBS_MSE4_INDEX",
        "limits": ("+RETURN_OBS_MSE4_INDEX_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_MSE4_INDEX",
            "enabled=1",
            "limit=96",
        ),
    },
)
'''
    replacement = anchor[:-3] + '''    {
        "feature": "RETURN_OBS_LC18_PE7",
        "enable": "+RETURN_OBS_LC18_PE7",
        "limits": ("+RETURN_OBS_LC18_PE7_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_LC18_PE7",
            "enabled=1",
            "limit=96",
        ),
    },
)
'''
    if text.count(anchor) != 1:
        raise BuildError("runtime feature anchor differs")
    path.write_text(
        text.replace(anchor, replacement, 1),
        encoding="utf-8",
        newline="\n",
    )


def rtl_binding() -> dict[str, Any]:
    if base.sha256(RTL_SYNC_REPORT) != RTL_SYNC_REPORT_SHA256:
        raise BuildError("current RTL sync report SHA differs")
    mapping = json.loads(MAPPING_CACHE.read_text(encoding="utf-8"))
    required = {
        "DRAM_LC.LC15": "LC17",
        "DRAM_LC.LC9": "LC18",
        "LC_PE.PE1": "PE7",
        "STREAM.stream4": "WRITE_STREAM0",
    }
    if any(mapping.get(key) != value for key, value in required.items()):
        raise BuildError("frozen logical-to-physical mapping differs")
    leaves = []
    for relative in RTL_LEAVES:
        path = ROOT / relative
        leaves.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": base.sha256(path),
            }
        )
    return {
        "schema": "node0004-v33-current-local-rtl-and-mapping-binding-v1",
        "current_local_rtl_commit": RTL_COMMIT,
        "sync_report_path": str(RTL_SYNC_REPORT.relative_to(ROOT)).replace(
            "\\", "/"
        ),
        "sync_report_sha256": RTL_SYNC_REPORT_SHA256,
        "mapping_cache": {
            "path": str(MAPPING_CACHE.relative_to(ROOT)).replace("\\", "/"),
            "sha256": base.sha256(MAPPING_CACHE),
            "required": required,
        },
        "mapping_review": {
            "path": str(MAPPING_REVIEW.relative_to(ROOT)).replace("\\", "/"),
            "sha256": base.sha256(MAPPING_REVIEW),
        },
        "focused_direct_consumers": leaves,
        "server_runtime_source_preflight": False,
        "server_run_rtl_identity_bound": False,
        "claim_boundary": (
            "local successor analysis/build identity only; compile/run "
            "naturally adjudicates the user-supplied server root"
        ),
        "source_sync_not_functional_repair": True,
    }


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v33-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    binding = rtl_binding()
    provenance = package / "provenance"
    base.write_json(provenance / "current_local_rtl_binding.json", binding)
    (package / "README.md").write_text(
        f"# node0004 v33 physical LC18/PE7 diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v32 proved seven fresh WRITE_STREAM0 buffer-index accepts and "
        "one-for-one conservation through Memory_AG_Idx_Queue and WR_Memory_AG, "
        "but the eighth tuple required by the already-prepared data never "
        "arrived. This package freezes workload, configuration, golden, timeout, "
        "backpressure and functional RTL, and adds qualified counters at mapped "
        "LC17/LC18/PE7 and WRITE_STREAM0 input1.\n\n"
        f"Current local RTL analysis identity: `{RTL_COMMIT}`. "
        "This is not a server source preflight or a functional-repair claim.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh "
        "/absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-lc18-pe7-diagnostic-package-v33",
            "install_name": INSTALL_NAME,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    manifest["active_receipts"]["server_package_rule_sha256"] = (
        SERVER_RULE_SHA256
    )
    manifest["v32_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "MISSING_EIGHTH_MSE4_BUFFER_INDEX_ACCEPT",
        "last_proven_good": (
            "MSE4_SEVENTH_BUFFER_INDEX_ACCEPT_MATCH_QUEUE_PUSH_POP_WR_AG_"
            "TRANSACTION_FINISH_AND_TWO_DESCRIPTOR_HANDSHAKES"
        ),
        "first_divergence": (
            "EXPECTED_EIGHTH_PE7_BUFFER_INDEX_OUTPUT_TO_MSE4_"
            "MEMORY_AG_IDX_QUEUE_INPUT1_ACCEPT"
        ),
        "root_cause": (
            "UNRESOLVED_REQUIRES_MAPPED_PHYSICAL_LC18_PE7_BOUNDARY"
        ),
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "buffer_index_accepts": 7,
        "matched_transactions": 7,
        "descriptor_count": 14,
        "prepared_group_count": 16,
    }
    feature = {
        "feature": "RETURN_OBS_LC18_PE7",
        "runtime_enable_parameter": "+RETURN_OBS_LC18_PE7",
        "limit_or_budget_parameters": ["+RETURN_OBS_LC18_PE7_LIMIT=96"],
        "time_zero_marker": (
            "DIAGNOSTIC_FEATURE_ENABLE_V1 feature=RETURN_OBS_LC18_PE7 "
            "enabled=1 limit=96"
        ),
        "expected_record_schema": "LC18_PE7_BOUNDARY_V1",
    }
    manifest["diagnostic_feature_runtime_binding"]["features"].append(feature)
    manifest["lc18_pe7_diagnostic"] = {
        **feature,
        "edge_record": "LC18_PE7_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "qualified_boundary": (
            "mapped LC17 parent -> LC18 counter -> PE7 inport0/inport2 -> "
            "PE7 outbuffer write/read -> WRITE_STREAM0 input1 accept"
        ),
        "physical_mapping": binding["mapping_cache"]["required"],
        "state_only": [
            "raw LC/PE/MSE valid and same",
            "fanout backpressure vectors",
            "last/last_index tags",
            "PE outbuffer count",
        ],
        "decision_map": {
            "lc18_out_less_than_eight": "LC17/LC18 production or fanout release",
            "lc18_out_eight_pe7_in2_less_than_eight": (
                "LC18 to PE7 inport2 acceptance"
            ),
            "pe7_in2_eight_pe7_write_less_than_eight": (
                "PE7 matching/ALU/outbuffer write"
            ),
            "pe7_write_eight_pe7_read_less_than_eight": (
                "PE7 outbuffer release/backpressure"
            ),
            "pe7_read_eight_mse_input1_less_than_eight": (
                "PE7 to WRITE_STREAM0 input1 same/gotten acceptance"
            ),
        },
        "functional_fix": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "configuration_changed": False,
    }
    manifest["current_local_rtl_binding"] = binding
    manifest["superseded_v32_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_NARROWER_DIAGNOSTIC",
    }
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update(
        {
            "sha256": observer_sha,
            "size_bytes": (
                package / "tb_probe/native_return_observer.svh"
            ).stat().st_size,
        }
    )
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    receipt = base.observer_precompile_receipt(package, observer_sha)
    if not receipt["valid"]:
        raise BuildError(f"observer static gate failed: {receipt['errors']}")
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL_NAME,
        output / f"{INSTALL_NAME}.zip",
        output / f"{INSTALL_NAME}.zip.sha256",
        output / f"{INSTALL_NAME}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v33 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v33-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v33 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-lc18-pe7-diagnostic-build-v33",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v32_sha256": SOURCE_SHA256,
        "bound_v32_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "current_local_rtl_commit": RTL_COMMIT,
        "rtl_sync_report_sha256": RTL_SYNC_REPORT_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(output / f"{INSTALL_NAME}.validation.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
