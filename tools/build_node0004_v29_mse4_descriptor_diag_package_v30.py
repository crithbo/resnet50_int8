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

import tools.build_node0004_v28_datahub_drain_diag_package_v29 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v29_datahub_drain_diag"
INSTALL_NAME = "r5_n4_hw_v30_mse4_descriptor_diag"
SOURCE_SHA256 = "4537f98ea18b281aa0f42f8355d7961594bbe0d3cd5991e906d708d9273173bc"
RETURN_SHA256 = "80bc305d70106952a15887e9e72b275d8572126d5dd46d17087523c37656d069"
SERVER_RULE_SHA256 = "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
RTL_COMMIT = "d0aa87f682880a260fb792aaac88f70a23aba414"
RTL_SYNC_REPORT = ROOT / "artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json"
RTL_SYNC_REPORT_SHA256 = "fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
RTL_BASE = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine"
RTL_LEAVES = (
    "RD_Buffer_AG.sv",
    "WR_Data_Channel.sv",
    "WR_Memory_AG.sv",
    "Memory_WR_Stream_Engine.sv",
)


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v29 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v29 source CRC failed")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename or info.filename in seen:
                raise BuildError(f"unsafe/duplicate member: {info.filename}")
            seen.add(info.filename)
            if path.parts:
                roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v29 root differs: {sorted(roots)}")
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
            path.write_text(text.replace(SOURCE_NAME, INSTALL_NAME), encoding="utf-8", newline="\n")


def mse(module: str, leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
        f"{module}.{leaf}"
    )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "MSE4_DESCRIPTOR_BOUNDARY_V1" in text:
        raise BuildError("v30 descriptor diagnostic already present")
    call = "                return_obs_write_datahub_drain_state(event_name);"
    if text.count(call) != 1:
        raise BuildError("observer decision hook anchor differs")
    text = text.replace(call, call + "\n                return_obs_write_mse4_descriptor_state(event_name);", 1)
    block = f'''

    // v30: qualified WR_Memory_AG descriptor -> WR_Data_Channel FIFO/data release.
    // FIFO occupancy and combinational ready/valid levels are corroborating state only.
    bit return_obs_md_enabled;
    integer return_obs_md_limit;
    integer return_obs_md_plusarg_status;
    integer return_obs_md_edge_records;
    longint unsigned return_obs_md_desc_hs;
    longint unsigned return_obs_md_fifo_push;
    longint unsigned return_obs_md_fifo_pop;
    longint unsigned return_obs_md_mem_req_hs0;
    longint unsigned return_obs_md_mem_req_hs1;
    longint unsigned return_obs_md_prepared_wr;
    longint unsigned return_obs_md_prepared_rd;
    longint unsigned return_obs_md_ob_wr0;
    longint unsigned return_obs_md_ob_wr1;
    longint unsigned return_obs_md_ob_rd0;
    longint unsigned return_obs_md_ob_rd1;

    initial begin
        return_obs_md_enabled = $test$plusargs("RETURN_OBS_MSE4_DESCRIPTOR");
        return_obs_md_limit = 96;
        return_obs_md_plusarg_status = $value$plusargs(
            "RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=%d", return_obs_md_limit
        );
        return_obs_md_edge_records = 0;
        return_obs_md_desc_hs = 0;
        return_obs_md_fifo_push = 0;
        return_obs_md_fifo_pop = 0;
        return_obs_md_mem_req_hs0 = 0;
        return_obs_md_mem_req_hs1 = 0;
        return_obs_md_prepared_wr = 0;
        return_obs_md_prepared_rd = 0;
        return_obs_md_ob_wr0 = 0;
        return_obs_md_ob_wr1 = 0;
        return_obs_md_ob_rd0 = 0;
        return_obs_md_ob_rd1 = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_MSE4_DESCRIPTOR enabled=%0d limit_name=RETURN_OBS_MSE4_DESCRIPTOR_LIMIT limit=%0d",
                return_obs_md_enabled, return_obs_md_limit);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit md_desc_hs;
        bit md_fifo_push;
        bit md_fifo_pop;
        bit md_mem_req_hs0;
        bit md_mem_req_hs1;
        bit md_prepared_wr;
        bit md_prepared_rd;
        bit md_ob_wr0;
        bit md_ob_wr1;
        bit md_ob_rd0;
        bit md_ob_rd1;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_md_edge_records = 0;
            return_obs_md_desc_hs = 0;
            return_obs_md_fifo_push = 0;
            return_obs_md_fifo_pop = 0;
            return_obs_md_mem_req_hs0 = 0;
            return_obs_md_mem_req_hs1 = 0;
            return_obs_md_prepared_wr = 0;
            return_obs_md_prepared_rd = 0;
            return_obs_md_ob_wr0 = 0;
            return_obs_md_ob_wr1 = 0;
            return_obs_md_ob_rd0 = 0;
            return_obs_md_ob_rd1 = 0;
        end else if (return_obs_md_enabled && return_obs_active) begin
            md_desc_hs = {mse('u_WR_Memory_AG', 'wr_data_chl_req_valid')} && {mse('u_WR_Memory_AG', 'wr_data_chl_req_ready')};
            md_fifo_push = {mse('u_WR_Data_Channel', 'wr_chl_queue_wr_en')} && !{mse('u_WR_Data_Channel', 'wr_chl_queue_full')};
            md_fifo_pop = {mse('u_WR_Data_Channel', 'wr_chl_queue_rd_en')} && !{mse('u_WR_Data_Channel', 'wr_chl_queue_empty')};
            md_mem_req_hs0 = {mse('u_WR_Memory_AG', 'mse2mem_request_valid[0]')} && {mse('u_WR_Memory_AG', 'mem2mse_request_ready[0]')};
            md_mem_req_hs1 = {mse('u_WR_Memory_AG', 'mse2mem_request_valid[1]')} && {mse('u_WR_Memory_AG', 'mem2mse_request_ready[1]')};
            md_prepared_wr = {mse('u_WR_Data_Channel', 'wr_data_chl_prepared_data_wr_hs')};
            md_prepared_rd = {mse('u_WR_Data_Channel', 'wr_data_chl_prepared_data_rd_hs')};
            md_ob_wr0 = {mse('u_WR_Data_Channel', 'wr_chl_ob_wr_hs[0]')};
            md_ob_wr1 = {mse('u_WR_Data_Channel', 'wr_chl_ob_wr_hs[1]')};
            md_ob_rd0 = {mse('u_WR_Data_Channel', 'wr_chl_ob_rd_hs[0]')};
            md_ob_rd1 = {mse('u_WR_Data_Channel', 'wr_chl_ob_rd_hs[1]')};
            if (md_desc_hs) return_obs_md_desc_hs++;
            if (md_fifo_push) return_obs_md_fifo_push++;
            if (md_fifo_pop) return_obs_md_fifo_pop++;
            if (md_mem_req_hs0) return_obs_md_mem_req_hs0++;
            if (md_mem_req_hs1) return_obs_md_mem_req_hs1++;
            if (md_prepared_wr) return_obs_md_prepared_wr++;
            if (md_prepared_rd) return_obs_md_prepared_rd++;
            if (md_ob_wr0) return_obs_md_ob_wr0++;
            if (md_ob_wr1) return_obs_md_ob_wr1++;
            if (md_ob_rd0) return_obs_md_ob_rd0++;
            if (md_ob_rd1) return_obs_md_ob_rd1++;
            if (return_obs_md_edge_records < return_obs_md_limit &&
                (md_desc_hs || md_fifo_push || md_fifo_pop || md_mem_req_hs0 ||
                 md_mem_req_hs1 || md_prepared_wr || md_prepared_rd ||
                 md_ob_wr0 || md_ob_wr1 || md_ob_rd0 || md_ob_rd1)) begin
                $fdisplay(return_obs_fd,
                    "%0t | MSE4_DESCRIPTOR_EDGE_V1 | n=%0d desc_hs=%0d fifo_push=%0d fifo_pop=%0d mem_req0=%0d mem_req1=%0d prepare_wr=%0d prepare_rd=%0d ob_wr=0x%0h ob_rd=0x%0h desc_full=%0d desc_empty=%0d desc_count=%0d desc_size=%0d prepared_count=%0d prepared_vld=%0d prepared_bp=%0d ob_sel=%0d ob_vld=0x%0h ob_bp=0x%0h trans_valid=%0d trans_size=%0d trans_left=%0d last_req=%0d",
                    $time, return_obs_md_edge_records + 1, md_desc_hs,
                    md_fifo_push, md_fifo_pop, md_mem_req_hs0, md_mem_req_hs1,
                    md_prepared_wr, md_prepared_rd,
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_wr_hs')},
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_rd_hs')},
                    {mse('u_WR_Data_Channel', 'wr_chl_queue_full')},
                    {mse('u_WR_Data_Channel', 'wr_chl_queue_empty')},
                    {mse('u_WR_Data_Channel', 'u_wr_chl_queue.fifo_counter')},
                    {mse('u_WR_Data_Channel', 'wr_chl_queue_rd_tsf_size')},
                    {mse('u_WR_Data_Channel', 'wr_data_chl_prepared_data_cnt')},
                    {mse('u_WR_Data_Channel', 'wr_data_chl_prepared_data_vld')},
                    {mse('u_WR_Data_Channel', 'wr_chl_prepared_data_bp_pre')},
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_sel')},
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_vld')},
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_bp_pre')},
                    {mse('u_WR_Memory_AG', 'transaction_addr_valid')},
                    {mse('u_WR_Memory_AG', 'transfer_final_size')},
                    {mse('u_WR_Memory_AG', 'cur_transaction_size_left')},
                    {mse('u_RD_Buffer_AG', 'buf_ag_last_req_flag')});
                return_obs_md_edge_records++;
                $fflush(return_obs_fd);
            end
        end
    end

    task automatic return_obs_write_mse4_descriptor_state(input string event_name);
        begin
            if (return_obs_md_enabled && return_obs_fd != 0) begin
                $fdisplay(return_obs_fd,
                    "%0t | MSE4_DESCRIPTOR_BOUNDARY_V1 | event=%s desc_hs=%0d fifo_push=%0d fifo_pop=%0d mem_req0=%0d mem_req1=%0d prepared_wr=%0d prepared_rd=%0d ob_wr0=%0d ob_wr1=%0d ob_rd0=%0d ob_rd1=%0d desc_full=%0d desc_empty=%0d desc_count=%0d desc_size=%0d prepared_count=%0d prepared_vld=%0d prepared_bp=%0d ob_sel=%0d ob_vld=0x%0h ob_bp=0x%0h trans_valid=%0d trans_size=%0d trans_left=%0d mem_ob_vld=0x%0h mem_ob_sel=%0d last_req=%0d wr_ready=%0d",
                    $time, event_name, return_obs_md_desc_hs,
                    return_obs_md_fifo_push, return_obs_md_fifo_pop,
                    return_obs_md_mem_req_hs0, return_obs_md_mem_req_hs1,
                    return_obs_md_prepared_wr, return_obs_md_prepared_rd,
                    return_obs_md_ob_wr0, return_obs_md_ob_wr1,
                    return_obs_md_ob_rd0, return_obs_md_ob_rd1,
                    {mse('u_WR_Data_Channel', 'wr_chl_queue_full')},
                    {mse('u_WR_Data_Channel', 'wr_chl_queue_empty')},
                    {mse('u_WR_Data_Channel', 'u_wr_chl_queue.fifo_counter')},
                    {mse('u_WR_Data_Channel', 'wr_chl_queue_rd_tsf_size')},
                    {mse('u_WR_Data_Channel', 'wr_data_chl_prepared_data_cnt')},
                    {mse('u_WR_Data_Channel', 'wr_data_chl_prepared_data_vld')},
                    {mse('u_WR_Data_Channel', 'wr_chl_prepared_data_bp_pre')},
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_sel')},
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_vld')},
                    {mse('u_WR_Data_Channel', 'wr_chl_ob_bp_pre')},
                    {mse('u_WR_Memory_AG', 'transaction_addr_valid')},
                    {mse('u_WR_Memory_AG', 'transfer_final_size')},
                    {mse('u_WR_Memory_AG', 'cur_transaction_size_left')},
                    {mse('u_WR_Memory_AG', 'mem_ag_ob_vld')},
                    {mse('u_WR_Memory_AG', 'mem_ag_ob_sel')},
                    {mse('u_RD_Buffer_AG', 'buf_ag_last_req_flag')},
                    {mse('u_RD_Buffer_AG', 'wr_data_chl_ready')});
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
    token = "+RETURN_OBS_DATAHUB_DRAIN_LIMIT=64"
    if text.count(token) != 2:
        raise BuildError("runner feature anchor differs")
    text = text.replace(token, token + " +RETURN_OBS_MSE4_DESCRIPTOR +RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = '''    {
        "feature": "RETURN_OBS_DATAHUB_DRAIN",
        "enable": "+RETURN_OBS_DATAHUB_DRAIN",
        "limits": ("+RETURN_OBS_DATAHUB_DRAIN_LIMIT=64",),
        "marker_tokens": (
            "feature=RETURN_OBS_DATAHUB_DRAIN",
            "enabled=1",
            "limit=64",
        ),
    },
)
'''
    replacement = anchor[:-3] + '''    {
        "feature": "RETURN_OBS_MSE4_DESCRIPTOR",
        "enable": "+RETURN_OBS_MSE4_DESCRIPTOR",
        "limits": ("+RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96",),
        "marker_tokens": (
            "feature=RETURN_OBS_MSE4_DESCRIPTOR",
            "enabled=1",
            "limit=96",
        ),
    },
)
'''
    if text.count(anchor) != 1:
        raise BuildError("runtime feature anchor differs")
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8", newline="\n")


def rtl_binding() -> dict[str, Any]:
    if base.sha256(RTL_SYNC_REPORT) != RTL_SYNC_REPORT_SHA256:
        raise BuildError("current RTL sync report SHA differs")
    leaves = []
    for name in RTL_LEAVES:
        path = RTL_BASE / name
        leaves.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": base.sha256(path)})
    return {
        "schema": "node0004-v30-current-local-rtl-binding-v1",
        "current_local_rtl_commit": RTL_COMMIT,
        "sync_report_path": str(RTL_SYNC_REPORT.relative_to(ROOT)).replace("\\", "/"),
        "sync_report_sha256": RTL_SYNC_REPORT_SHA256,
        "focused_direct_consumers": leaves,
        "server_runtime_source_preflight": False,
        "server_run_rtl_identity_bound": False,
        "claim_boundary": "local successor analysis/build identity only; compile/run naturally adjudicates the user-supplied server root",
        "source_sync_not_functional_repair": True,
    }


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v30-source-") as temp:
        shutil.copytree(extract(Path(temp)), package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runner(package)
    patch_runtime(package)
    binding = rtl_binding()
    provenance = package / "provenance"
    provenance.mkdir(exist_ok=True)
    base.write_json(provenance / "current_local_rtl_binding.json", binding)
    (package / "README.md").write_text(
        f"# node0004 v30 MSE4 descriptor diagnostic\n\nClassification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\nv29 proved that DataHub local channels 8/9 each accepted and drained all seven address/data pairs. This package freezes workload, configuration, golden, timeout, backpressure and functional RTL, and adds one qualified boundary from WR_Memory_AG descriptor handshakes through the WR_Data_Channel descriptor FIFO, prepared-data eligibility and two output buffers.\n\nCurrent local RTL analysis identity: `{RTL_COMMIT}`. This is not a server runtime preflight or a functional-repair claim.\n\nRun: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\nExpected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8", newline="\n"
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "resnet50-node0004-mse4-descriptor-diagnostic-package-v30",
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
    })
    manifest["active_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA256
    manifest["v29_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "MSE4_DESCRIPTOR_TO_WR_DATA_CHANNEL_BOUNDARY_UNRESOLVED",
        "last_proven_good": "MSE4_DATAHUB_LOCAL_CHANNELS_8_9_EACH_ACCEPTED_ALL_7_ADDRESS_DATA_PAIRS_THROUGH_BANK_CROSSBAR_AND_DRAINED",
        "first_divergence": "MSE4_WR_MEMORY_DESCRIPTOR_TO_WR_DATA_CHANNEL_RELEASE_OF_FINAL_TWO_PREPARED_GROUPS",
        "root_cause": "UNRESOLVED_REQUIRES_DESCRIPTOR_FIFO_AND_PREPARED_DATA_RELEASE_BOUNDARY",
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
    }
    feature = {
        "feature": "RETURN_OBS_MSE4_DESCRIPTOR",
        "runtime_enable_parameter": "+RETURN_OBS_MSE4_DESCRIPTOR",
        "limit_or_budget_parameters": ["+RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96"],
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1 feature=RETURN_OBS_MSE4_DESCRIPTOR enabled=1 limit=96",
        "expected_record_schema": "MSE4_DESCRIPTOR_BOUNDARY_V1",
    }
    manifest["diagnostic_feature_runtime_binding"]["features"].append(feature)
    manifest["mse4_descriptor_diagnostic"] = {
        **feature,
        "edge_record": "MSE4_DESCRIPTOR_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "qualified_boundary": "WR_Memory_AG descriptor handshake -> WR_Data_Channel FIFO push/pop -> prepared-data read -> output-buffer write/read",
        "state_only": ["FIFO count/full/empty", "current descriptor size", "prepared count/valid/backpressure", "output selector/valid/backpressure", "transaction size/left", "last-request flag"],
        "functional_fix": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "configuration_changed": False,
    }
    manifest["current_local_rtl_binding"] = binding
    manifest["superseded_v29_package"] = {"path": f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE_NAME}.zip", "sha256": SOURCE_SHA256, "status": "RETURN_CONSUMED_SUPERSEDED_BY_NARROWER_DIAGNOSTIC"}
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update({"sha256": observer_sha, "size_bytes": (package / "tb_probe/native_return_observer.svh").stat().st_size})
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
    targets = [output / INSTALL_NAME, output / f"{INSTALL_NAME}.zip", output / f"{INSTALL_NAME}.zip.sha256", output / f"{INSTALL_NAME}.validation.json"]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v30 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v30-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v30 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report: dict[str, Any] = {
        "schema": "node0004-mse4-descriptor-diagnostic-build-v30",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size, "zip_sha256": digest,
        "sidecar": str(sidecar), "deterministic_rebuild_equal": deterministic,
        "source_v29_sha256": SOURCE_SHA256, "bound_v29_return_sha256": RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "current_local_rtl_commit": RTL_COMMIT, "rtl_sync_report_sha256": RTL_SYNC_REPORT_SHA256,
        "numeric_analysis_repeated": False, "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False, "functional_rtl_modified": False,
        "server_action": False, "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(output / f"{INSTALL_NAME}.validation.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
