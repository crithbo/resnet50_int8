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

import tools.build_node0004_v29_mse4_descriptor_diag_package_v30 as previous  # noqa: E402


base = previous.base
SOURCE_NAME = "r5_n4_hw_v30_mse4_descriptor_diag"
INSTALL_NAME = "r5_n4_hw_v32_mse4_index_diag"
SOURCE_SHA256 = "0c358f254cac4128a7a320a4201a50f266f1620105fd9b859cf26ac84aa6ad81"
RETURN_SHA256 = "cad26c94a8f16ee290b8dfd519f4eabad76873b933f3193e281fedd0b061b94f"
SERVER_RULE_SHA256 = "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
RTL_COMMIT = "d0aa87f682880a260fb792aaac88f70a23aba414"
RTL_SYNC_REPORT = ROOT / "artifacts/rtl_sync/trassic_master_d0aa87f_20260803/report.json"
RTL_SYNC_REPORT_SHA256 = "fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771"
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
RTL_BASE = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
RTL_LEAVES = (
    "Memory_AG_Idx_Queue.sv",
    "Memory_WR_Stream_Engine/WR_Memory_AG.sv",
    "Memory_WR_Stream_Engine/WR_Data_Channel.sv",
    "Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv",
)


class BuildError(RuntimeError):
    pass


def extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("v30 source SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v30 source CRC failed")
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
            raise BuildError(f"v30 root differs: {sorted(roots)}")
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


def mseq(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]"
        ".u_slice_with_datahub_mc_group.slice_group_gen[0]"
        ".u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine"
        ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
        f".u_Memory_AG_Idx_Queue.{leaf}"
    )


def mseag(leaf: str) -> str:
    return previous.mse("u_WR_Memory_AG", leaf)


def msedata(leaf: str) -> str:
    return previous.mse("u_WR_Data_Channel", leaf)


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    if "MSE4_INDEX_BOUNDARY_V1" in text:
        raise BuildError("v32 index diagnostic already present")
    call = "                return_obs_write_mse4_descriptor_state(event_name);"
    if text.count(call) != 1:
        raise BuildError("observer decision hook anchor differs")
    text = text.replace(call, call + "\n                return_obs_write_mse4_index_state(event_name);", 1)
    block = f'''

    // v32: qualified MSE4 memory-index matching/queue -> WR_Memory_AG pipeline.
    // Valid/ready/full levels are state only; progress counters require a qualified edge.
    bit return_obs_mi_enabled;
    integer return_obs_mi_limit;
    integer return_obs_mi_plusarg_status;
    integer return_obs_mi_edge_records;
    longint unsigned return_obs_mi_accept0;
    longint unsigned return_obs_mi_accept1;
    longint unsigned return_obs_mi_accept2;
    longint unsigned return_obs_mi_match;
    longint unsigned return_obs_mi_push;
    longint unsigned return_obs_mi_pop;
    longint unsigned return_obs_mi_bias_capture;
    longint unsigned return_obs_mi_transaction_capture;
    longint unsigned return_obs_mi_transaction_finish;
    longint unsigned return_obs_mi_descriptor;
    longint unsigned return_obs_mi_prepared;

    initial begin
        return_obs_mi_enabled = $test$plusargs("RETURN_OBS_MSE4_INDEX");
        return_obs_mi_limit = 96;
        return_obs_mi_plusarg_status = $value$plusargs(
            "RETURN_OBS_MSE4_INDEX_LIMIT=%d", return_obs_mi_limit
        );
        return_obs_mi_edge_records = 0;
        return_obs_mi_accept0 = 0;
        return_obs_mi_accept1 = 0;
        return_obs_mi_accept2 = 0;
        return_obs_mi_match = 0;
        return_obs_mi_push = 0;
        return_obs_mi_pop = 0;
        return_obs_mi_bias_capture = 0;
        return_obs_mi_transaction_capture = 0;
        return_obs_mi_transaction_finish = 0;
        return_obs_mi_descriptor = 0;
        return_obs_mi_prepared = 0;
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_MSE4_INDEX enabled=%0d limit_name=RETURN_OBS_MSE4_INDEX_LIMIT limit=%0d",
                return_obs_mi_enabled, return_obs_mi_limit);
            $fflush(return_obs_fd);
        end
    end

    always @(posedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit mi_accept0;
        bit mi_accept1;
        bit mi_accept2;
        bit mi_match;
        bit mi_push;
        bit mi_pop;
        bit mi_bias_capture;
        bit mi_transaction_capture;
        bit mi_transaction_finish;
        bit mi_descriptor;
        bit mi_prepared;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_mi_edge_records = 0;
            return_obs_mi_accept0 = 0;
            return_obs_mi_accept1 = 0;
            return_obs_mi_accept2 = 0;
            return_obs_mi_match = 0;
            return_obs_mi_push = 0;
            return_obs_mi_pop = 0;
            return_obs_mi_bias_capture = 0;
            return_obs_mi_transaction_capture = 0;
            return_obs_mi_transaction_finish = 0;
            return_obs_mi_descriptor = 0;
            return_obs_mi_prepared = 0;
        end else if (return_obs_mi_enabled && return_obs_active) begin
            mi_accept0 = {mseq('mse_mem_queue_bp_pre[0]')} && {mseq('mem_idx_valid_same_gotten_masked[0]')};
            mi_accept1 = {mseq('mse_mem_queue_bp_pre[1]')} && {mseq('mem_idx_valid_same_gotten_masked[1]')};
            mi_accept2 = {mseq('mse_mem_queue_bp_pre[2]')} && {mseq('mem_idx_valid_same_gotten_masked[2]')};
            mi_match = {mseq('mem_all_idx_matched')} && !{mseq('mem_ag_idx_queue_full')};
            mi_push = {mseq('mem_ag_idx_queue_wr_en')} && !{mseq('mem_ag_idx_queue_full')};
            mi_pop = {mseq('mem_ag_idx_queue_rd_en')} && !{mseq('mem_ag_idx_queue_empty')};
            mi_bias_capture = {mseag('mem_ag_idx_valid_bit')} && {mseag('transaction_addr_bias_bp_pre')};
            mi_transaction_capture = {mseag('transaction_addr_bias_valid')} && {mseag('transaction_addr_bp_pre')};
            mi_transaction_finish = {mseag('transaction_finish')};
            mi_descriptor = {mseag('wr_data_chl_req_valid')} && {mseag('wr_data_chl_req_ready')};
            mi_prepared = {msedata('wr_data_chl_prepared_data_wr_hs')};
            if (mi_accept0) return_obs_mi_accept0++;
            if (mi_accept1) return_obs_mi_accept1++;
            if (mi_accept2) return_obs_mi_accept2++;
            if (mi_match) return_obs_mi_match++;
            if (mi_push) return_obs_mi_push++;
            if (mi_pop) return_obs_mi_pop++;
            if (mi_bias_capture) return_obs_mi_bias_capture++;
            if (mi_transaction_capture) return_obs_mi_transaction_capture++;
            if (mi_transaction_finish) return_obs_mi_transaction_finish++;
            if (mi_descriptor) return_obs_mi_descriptor++;
            if (mi_prepared) return_obs_mi_prepared++;
            if (return_obs_mi_edge_records < return_obs_mi_limit &&
                (mi_accept0 || mi_accept1 || mi_accept2 || mi_match || mi_push ||
                 mi_pop || mi_bias_capture || mi_transaction_capture ||
                 mi_transaction_finish || mi_descriptor || mi_prepared)) begin
                $fdisplay(return_obs_fd,
                    "%0t | MSE4_INDEX_EDGE_V1 | n=%0d acc=0x%0h match=%0d push=%0d pop=%0d bias=%0d trans=%0d finish=%0d desc=%0d prepared=%0d input_vld=0x%0h input_same=0x%0h input_bp=0x%0h gotten=0x%0h matched=%0d q_full=%0d q_empty=%0d q_count=%0d tag_valid=%0d ag_bp=%0d bias_valid=%0d trans_valid=%0d trans_left=%0d desc_ready=%0d prepared_count=%0d prepared_bp=%0d",
                    $time, return_obs_mi_edge_records + 1,
                    {{mi_accept2, mi_accept1, mi_accept0}}, mi_match, mi_push,
                    mi_pop, mi_bias_capture, mi_transaction_capture,
                    mi_transaction_finish, mi_descriptor, mi_prepared,
                    {mseq('mem_idx_valid_bit_unmasked')},
                    {mseq('mem_idx_same_bit_unmasked')},
                    {mseq('mse_mem_queue_bp_pre')},
                    {mseq('mem_idx_gotten_bit')},
                    {mseq('mem_all_idx_matched')},
                    {mseq('mem_ag_idx_queue_full')},
                    {mseq('mem_ag_idx_queue_empty')},
                    {mseq('u_mem_ag_idx_queue.fifo_counter')},
                    {mseq('mse_mem_ag_tag_valid')},
                    {mseag('mse_mem_ag_bp_pre')},
                    {mseag('transaction_addr_bias_valid')},
                    {mseag('transaction_addr_valid')},
                    {mseag('cur_transaction_size_left')},
                    {mseag('wr_data_chl_req_ready')},
                    {msedata('wr_data_chl_prepared_data_cnt')},
                    {msedata('wr_chl_prepared_data_bp_pre')});
                return_obs_mi_edge_records++;
                $fflush(return_obs_fd);
            end
        end
    end

    task automatic return_obs_write_mse4_index_state(input string event_name);
        begin
            if (return_obs_mi_enabled && return_obs_fd != 0) begin
                $fdisplay(return_obs_fd,
                    "%0t | MSE4_INDEX_BOUNDARY_V1 | event=%s accept0=%0d accept1=%0d accept2=%0d match=%0d push=%0d pop=%0d bias=%0d trans=%0d finish=%0d desc=%0d prepared=%0d input_vld=0x%0h input_same=0x%0h input_bp=0x%0h gotten=0x%0h masked_vld=0x%0h matched=%0d q_full=%0d q_empty=%0d q_count=%0d tag_valid=%0d tag_last=%0d tag_index=%0d ag_bp=%0d bias_valid=%0d trans_valid=%0d trans_left=%0d desc_ready=%0d prepared_count=%0d prepared_vld=%0d prepared_bp=%0d",
                    $time, event_name, return_obs_mi_accept0,
                    return_obs_mi_accept1, return_obs_mi_accept2,
                    return_obs_mi_match, return_obs_mi_push,
                    return_obs_mi_pop, return_obs_mi_bias_capture,
                    return_obs_mi_transaction_capture,
                    return_obs_mi_transaction_finish,
                    return_obs_mi_descriptor, return_obs_mi_prepared,
                    {mseq('mem_idx_valid_bit_unmasked')},
                    {mseq('mem_idx_same_bit_unmasked')},
                    {mseq('mse_mem_queue_bp_pre')},
                    {mseq('mem_idx_gotten_bit')},
                    {mseq('mem_idx_valid_bit_masked')},
                    {mseq('mem_all_idx_matched')},
                    {mseq('mem_ag_idx_queue_full')},
                    {mseq('mem_ag_idx_queue_empty')},
                    {mseq('u_mem_ag_idx_queue.fifo_counter')},
                    {mseq('mse_mem_ag_tag_valid')},
                    {mseag('mem_ag_idx_last_bit')},
                    {mseag('mem_ag_idx_last_index')},
                    {mseag('mse_mem_ag_bp_pre')},
                    {mseag('transaction_addr_bias_valid')},
                    {mseag('transaction_addr_valid')},
                    {mseag('cur_transaction_size_left')},
                    {mseag('wr_data_chl_req_ready')},
                    {msedata('wr_data_chl_prepared_data_cnt')},
                    {msedata('wr_data_chl_prepared_data_vld')},
                    {msedata('wr_chl_prepared_data_bp_pre')});
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
    token = "+RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96"
    if text.count(token) != 2:
        raise BuildError("runner feature anchor differs")
    text = text.replace(token, token + " +RETURN_OBS_MSE4_INDEX +RETURN_OBS_MSE4_INDEX_LIMIT=96")
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    text = path.read_text(encoding="utf-8")
    anchor = '''    {
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
    replacement = anchor[:-3] + '''    {
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
    if text.count(anchor) != 1:
        raise BuildError("runtime feature anchor differs")
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8", newline="\n")


def rtl_binding() -> dict[str, Any]:
    if base.sha256(RTL_SYNC_REPORT) != RTL_SYNC_REPORT_SHA256:
        raise BuildError("current RTL sync report SHA differs")
    leaves = []
    for name in RTL_LEAVES:
        path = RTL_BASE / name
        leaves.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": base.sha256(path),
            }
        )
    return {
        "schema": "node0004-v32-current-local-rtl-binding-v1",
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
    with tempfile.TemporaryDirectory(prefix="node0004-v32-source-") as temp:
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
        f"# node0004 v32 MSE4 memory-index diagnostic\n\n"
        "Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.\n\n"
        "v30 proved that all 14 generated descriptors were conserved through FIFO, both memory requests and both output buffers, while 16 prepared groups existed. "
        "This package freezes workload, configuration, golden, timeout, backpressure and functional RTL, and adds one qualified boundary across Memory_AG_Idx_Queue ingress/match/push/pop and the WR_Memory_AG bias/transaction/finish/descriptor pipeline.\n\n"
        f"Current local RTL analysis identity: `{RTL_COMMIT}`. This is not a server runtime source preflight or a functional-repair claim.\n\n"
        f"Run: `bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`\n\n"
        f"Expected return: `{INSTALL_NAME}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-mse4-index-diagnostic-package-v32",
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
    manifest["active_receipts"]["server_package_rule_sha256"] = SERVER_RULE_SHA256
    manifest["active_receipts"]["common_operator_rule_sha256"] = "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
    manifest["active_receipts"]["ndp_hardware_fields_rule_sha256"] = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    manifest["v30_return_adjudication"] = {
        "bound_return_sha256": RETURN_SHA256,
        "status": "MSE4_MEMORY_INDEX_TO_DESCRIPTOR_GENERATION_BOUNDARY_UNRESOLVED",
        "last_proven_good": "MSE4_ALL_14_GENERATED_DESCRIPTORS_PUSHED_POPPED_AND_CONSERVED_THROUGH_BOTH_MEMORY_REQUESTS_AND_ALTERNATING_OUTPUT_BUFFERS",
        "first_divergence": "MSE4_MEMORY_INDEX_MATCH_QUEUE_TO_WR_MEMORY_AG_GENERATION_OF_FINAL_TWO_DESCRIPTORS_FOR_ALREADY_PREPARED_GROUPS",
        "root_cause": "UNRESOLVED_REQUIRES_MEMORY_INDEX_QUEUE_AND_WR_MEMORY_AG_PIPELINE_BOUNDARY",
        "natural_terminal": False,
        "formal_d_present": 0,
        "formal_d_missing": 320,
        "descriptor_count": 14,
        "prepared_group_count": 16,
    }
    feature = {
        "feature": "RETURN_OBS_MSE4_INDEX",
        "runtime_enable_parameter": "+RETURN_OBS_MSE4_INDEX",
        "limit_or_budget_parameters": ["+RETURN_OBS_MSE4_INDEX_LIMIT=96"],
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1 feature=RETURN_OBS_MSE4_INDEX enabled=1 limit=96",
        "expected_record_schema": "MSE4_INDEX_BOUNDARY_V1",
    }
    manifest["diagnostic_feature_runtime_binding"]["features"].append(feature)
    manifest["mse4_index_diagnostic"] = {
        **feature,
        "edge_record": "MSE4_INDEX_EDGE_V1",
        "returned_record_target": "runs/c0/return_observer.log",
        "qualified_boundary": "Memory_AG_Idx_Queue per-input accepts -> all-index match -> queue push/pop -> WR_Memory_AG bias/transaction/finish -> descriptor handshake",
        "state_only": [
            "raw input valid/same",
            "input backpressure and gotten mask",
            "queue count/full/empty",
            "bias/transaction valid",
            "remaining transfer size",
            "prepared count/valid/backpressure",
        ],
        "decision_map": {
            "per_input_accept_stops_before_match": "shared-source or per-port matching starvation",
            "match_or_push_exceeds_pop": "Memory_AG_Idx_Queue conservation/acceptance fault",
            "pop_exceeds_bias_or_transaction_or_finish": "WR_Memory_AG pipeline loss/stall",
            "finish_exceeds_descriptor": "descriptor-ready boundary",
        },
        "functional_fix": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "configuration_changed": False,
    }
    manifest["current_local_rtl_binding"] = binding
    manifest["superseded_v30_package"] = {
        "path": f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE_NAME}.zip",
        "sha256": SOURCE_SHA256,
        "status": "RETURN_CONSUMED_SUPERSEDED_BY_NARROWER_DIAGNOSTIC",
    }
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"].update(
        {"sha256": observer_sha, "size_bytes": (package / "tb_probe/native_return_observer.svh").stat().st_size}
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
        raise BuildError("refusing to overwrite existing v32 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL_NAME}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v32-repeat-") as temp:
        repeat_root = Path(temp)
        repeat = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v32 deterministic rebuild differs")
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report: dict[str, Any] = {
        "schema": "node0004-mse4-index-diagnostic-build-v32",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v30_sha256": SOURCE_SHA256,
        "bound_v30_return_sha256": RETURN_SHA256,
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
