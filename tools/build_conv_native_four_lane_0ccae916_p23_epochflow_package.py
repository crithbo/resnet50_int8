#!/usr/bin/env python3
"""Build the p23 edge-qualified MSE4 epoch-flow successor from exact p22."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p22_eoenfix_package as previous


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p22_eoenfix"
PACKAGE_ID = "r5_n4_0cc_p23_epochflow"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_876_663
SOURCE_SHA256 = "876f9a16575648ddcb2dd594a881651cf7c678ddb30d344d112c68951f4fd8cf"
P22_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p22_return_analysis/report_v2.json"
BUILD_PROFILE = ROOT / "outputs/conv_native_four_lane_0ccae916_p23_epochflow/server_package_build_profile_v2.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p23_epochflow/build_v2"
OBSERVER = "tb_probe/native_return_observer.svh"
RUNTIME = "package_tools/node0004_assumed_hardware_server_runtime.py"
SOURCE_OBSERVER_SHA256 = "9e43d5300050a9df1a559a376f375ee81f1dfcb326c0ec677f24231e73d80c26"
LOCAL_MEMORY_AG_SHA256 = "b555ab22523540a9aa49d3eb51dee6eea9962086a71429028c69964de3819989"
RULE_PATHS = previous.RULE_PATHS
base = previous.base


XMR = (
    "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
    "slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4]."
    "WR_MSE.u_Memory_WR_Stream_Engine.u_Memory_AG_Idx_Queue"
)
IGA = (
    "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
    "slice_group_gen[0].u_slice_wrapper.u_Slice.u_Index_Generation_Array"
)

EPOCH_FLOW_BLOCK = f'''    // p23 EPOCH_FLOW_ACTUAL_CONSUMER_BEGIN
    // Same-clock qualified transactions only; stable ready/valid levels are snapshots.
    bit return_obs_ef_enabled;
    integer return_obs_ef_limit;
    integer return_obs_ef_plusarg_status;
    integer return_obs_ef_records;
    longint unsigned return_obs_ef_prev_terminal;
    longint unsigned return_obs_ef_prev_desc;
    longint unsigned return_obs_ef_prev_prepared;
    longint unsigned return_obs_ef_prev_buf_push;
    longint unsigned return_obs_ef_prev_buf_pop;

    initial begin
        return_obs_ef_enabled = $test$plusargs("RETURN_OBS_EPOCH_FLOW");
        return_obs_ef_limit = 256;
        return_obs_ef_plusarg_status = $value$plusargs(
            "RETURN_OBS_EPOCH_FLOW_LIMIT=%d", return_obs_ef_limit
        );
        return_obs_ef_records = 0;
        return_obs_ef_prev_terminal = 0;
        return_obs_ef_prev_desc = 0;
        return_obs_ef_prev_prepared = 0;
        return_obs_ef_prev_buf_push = 0;
        return_obs_ef_prev_buf_pop = 0;
        #0;
        if (return_obs_ef_enabled && n4d_fd != 0) begin
            $fdisplay(
                n4d_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_EPOCH_FLOW enabled=%0d limit_name=RETURN_OBS_EPOCH_FLOW_LIMIT limit=%0d schema=EPOCH_FLOW",
                return_obs_ef_enabled, return_obs_ef_limit
            );
            $fflush(n4d_fd);
        end
    end

    task automatic return_obs_write_epoch_flow(input string event_name);
        if (return_obs_ef_enabled && n4d_fd != 0) begin
            $fdisplay(
                n4d_fd,
                "%0t | EPOCH_FLOW_V1 | event=%s desc_terminal=%0d desc=%0d prepared=%0d delta=%0d buf_push=%0d buf_pop=%0d valid=%h same=%h gotten=%h same_keep=%h same_get=%h valid_same_get=%h valid_mask=%h last_mask=%h bp_mask=%h bp=%h match=%0d qfull=%0d qempty=%0d qwr=%0d qrd=%0d tag_valid=%0d mse_enable=%0d mode0=%h mode1=%h mode2=%h keep0=%0d keep1=%0d keep2=%0d idx0=%h idx1=%h idx2=%h tag0=%h tag1=%h tag2=%h lc6=%h bp6=%h lc8=%h bp8=%h lc17=%h bp17=%h lc18=%h bp18=%h",
                $time, event_name,
                return_obs_wt_desc_terminal, return_obs_md_desc_hs,
                return_obs_md_prepared_wr,
                return_obs_md_prepared_wr - return_obs_md_desc_hs,
                return_obs_rb_buf_push, return_obs_rb_buf_pop,
                {XMR}.mem_idx_valid_bit_unmasked,
                {XMR}.mem_idx_same_bit_unmasked,
                {XMR}.mem_idx_gotten_bit,
                {XMR}.mem_idx_same_bit_keep_mask,
                {XMR}.mem_idx_same_gotten_mask,
                {XMR}.mem_idx_valid_same_gotten_masked,
                {XMR}.mem_idx_valid_bit_masked,
                {XMR}.mem_idx_last_bit_masked,
                {XMR}.mem_idx_bp_pre_mask,
                {XMR}.mse_mem_queue_bp_pre,
                {XMR}.mem_all_idx_matched,
                {XMR}.mem_ag_idx_queue_full,
                {XMR}.mem_ag_idx_queue_empty,
                {XMR}.mem_ag_idx_queue_wr_en,
                {XMR}.mem_ag_idx_queue_rd_en,
                {XMR}.mse_mem_ag_tag_valid,
                {XMR}.mse_enable,
                {XMR}.mse_mem_idx_mode[0],
                {XMR}.mse_mem_idx_mode[1],
                {XMR}.mse_mem_idx_mode[2],
                {XMR}.mse_mem_idx_keep_last_index[0],
                {XMR}.mse_mem_idx_keep_last_index[1],
                {XMR}.mse_mem_idx_keep_last_index[2],
                {XMR}.mse_mem_queue_idx[0],
                {XMR}.mse_mem_queue_idx[1],
                {XMR}.mse_mem_queue_idx[2],
                {XMR}.mse_mem_queue_tag[0],
                {XMR}.mse_mem_queue_tag[1],
                {XMR}.mse_mem_queue_tag[2],
                {IGA}.iga_lc_outport[6], {IGA}.iga_lc_outport_bp_post[6],
                {IGA}.iga_lc_outport[8], {IGA}.iga_lc_outport_bp_post[8],
                {IGA}.iga_lc_outport[17], {IGA}.iga_lc_outport_bp_post[17],
                {IGA}.iga_lc_outport[18], {IGA}.iga_lc_outport_bp_post[18]
            );
            $fflush(n4d_fd);
        end
    endtask

    always @(negedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit ef_terminal;
        bit ef_desc;
        bit ef_prepared;
        bit ef_buf;
        bit ef_input0;
        bit ef_input1;
        bit ef_input2;
        bit ef_qwr;
        bit ef_qrd;
        string ef_reason;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_ef_records = 0;
            return_obs_ef_prev_terminal = 0;
            return_obs_ef_prev_desc = 0;
            return_obs_ef_prev_prepared = 0;
            return_obs_ef_prev_buf_push = 0;
            return_obs_ef_prev_buf_pop = 0;
        end else if (return_obs_ef_enabled && n4d_active) begin
            ef_terminal = return_obs_wt_desc_terminal != return_obs_ef_prev_terminal;
            ef_desc = return_obs_md_desc_hs != return_obs_ef_prev_desc;
            ef_prepared = return_obs_md_prepared_wr != return_obs_ef_prev_prepared;
            ef_buf = return_obs_rb_buf_push != return_obs_ef_prev_buf_push ||
                     return_obs_rb_buf_pop != return_obs_ef_prev_buf_pop;
            ef_input0 = {XMR}.mse_mem_queue_bp_pre[0] &&
                        {XMR}.mem_idx_valid_same_gotten_masked[0];
            ef_input1 = {XMR}.mse_mem_queue_bp_pre[1] &&
                        {XMR}.mem_idx_valid_same_gotten_masked[1];
            ef_input2 = {XMR}.mse_mem_queue_bp_pre[2] &&
                        {XMR}.mem_idx_valid_same_gotten_masked[2];
            ef_qwr = {XMR}.mem_ag_idx_queue_wr_en &&
                     !{XMR}.mem_ag_idx_queue_full;
            ef_qrd = {XMR}.mem_ag_idx_queue_rd_en &&
                     !{XMR}.mem_ag_idx_queue_empty;
            if (return_obs_wt_desc_terminal >= 2 &&
                (ef_terminal || ef_desc || ef_prepared || ef_buf || ef_input0 ||
                 ef_input1 || ef_input2 || ef_qwr || ef_qrd) &&
                return_obs_ef_records < return_obs_ef_limit) begin
                if (ef_terminal) ef_reason = "DESC_TERMINAL";
                else if (ef_input1) ef_reason = "INPUT1_ACCEPT";
                else if (ef_input0) ef_reason = "INPUT0_ACCEPT";
                else if (ef_input2) ef_reason = "INPUT2_ACCEPT";
                else if (ef_qwr) ef_reason = "QUEUE_WRITE";
                else if (ef_qrd) ef_reason = "QUEUE_READ";
                else if (ef_desc) ef_reason = "DESC_ACCEPT";
                else if (ef_prepared) ef_reason = "PREPARED_ACCEPT";
                else ef_reason = "BUFFER_ACCEPT";
                return_obs_ef_records++;
                return_obs_write_epoch_flow(ef_reason);
            end
            return_obs_ef_prev_terminal = return_obs_wt_desc_terminal;
            return_obs_ef_prev_desc = return_obs_md_desc_hs;
            return_obs_ef_prev_prepared = return_obs_md_prepared_wr;
            return_obs_ef_prev_buf_push = return_obs_rb_buf_push;
            return_obs_ef_prev_buf_pop = return_obs_rb_buf_pop;
        end
    end
    // p23 EPOCH_FLOW_ACTUAL_CONSUMER_END
'''


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def replace_identity(package: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in base.TEXT_SUFFIXES:
            continue
        payload = path.read_bytes()
        if SOURCE_ID.encode() not in payload:
            continue
        path.write_text(payload.decode().replace(SOURCE_ID, PACKAGE_ID), encoding="utf-8", newline="\n")
        changed.append(path.relative_to(package).as_posix())
    required = {
        "PREPARE_AND_RUN.sh", "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json", "package_manifest.json",
        "workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    if not required <= set(changed):
        raise BuildError(f"identity rebinding surface differs: {sorted(required - set(changed))}")
    return changed


def patch_observer(package: Path) -> dict[str, Any]:
    path = package / OBSERVER
    source = path.read_bytes()
    if base.digest(source) != SOURCE_OBSERVER_SHA256:
        raise BuildError("exact p22 observer identity differs")
    text = source.decode()
    if "RETURN_OBS_EPOCH_FLOW" in text or "p23 EPOCH_FLOW_ACTUAL_CONSUMER_BEGIN" in text:
        raise BuildError("source already contains p23 observer")
    combined = text.rstrip() + "\n" + EPOCH_FLOW_BLOCK.rstrip() + "\n"
    path.write_text(combined, encoding="utf-8", newline="\n")
    return {
        "path": OBSERVER, "source_bytes": len(source), "source_sha256": base.digest(source),
        "block_bytes": len(EPOCH_FLOW_BLOCK.encode()), "block_sha256": base.digest(EPOCH_FLOW_BLOCK.encode()),
        "final_bytes": path.stat().st_size, "final_sha256": base.sha256(path),
        "new_private_xmr_target": "Memory_AG_Idx_Queue.sv",
        "clock": "u_NDP_Top_new.clk_db", "reset": "u_NDP_Top_new.rst_n_db",
        "stable_levels_count_as_transactions": False, "functional_rtl_changed": False,
    }


def patch_runner(package: Path) -> dict[str, Any]:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old = "+RETURN_OBS_EPOCH_OWNER +RETURN_OBS_EPOCH_OWNER_LIMIT=128"
    new = "+RETURN_OBS_EPOCH_FLOW +RETURN_OBS_EPOCH_FLOW_LIMIT=256"
    if text.count(old) != 2 or new in text:
        raise BuildError("p22 epoch plusarg surface differs")
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": "PREPARE_AND_RUN.sh", "sha256": base.sha256(path), "replacement_count": 2}


def patch_runtime_identity(package: Path) -> dict[str, Any]:
    path = package / RUNTIME
    text = path.read_text(encoding="utf-8")
    local_anchor = '''    "Buffer_AG_Idx_Queue.sv": (\n        "b5fc30fa970a4ed38ebdfaf825946a80562ded91d72c600dd1ee89d14103b1ef"\n    ),\n'''
    cloud_anchor = '''    "Buffer_AG_Idx_Queue.sv": "7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca",\n'''
    local_insert = local_anchor + f'''    "Memory_AG_Idx_Queue.sv": (\n        "{LOCAL_MEMORY_AG_SHA256}"\n    ),\n'''
    cloud_insert = cloud_anchor + f'''    "Memory_AG_Idx_Queue.sv": "{LOCAL_MEMORY_AG_SHA256}",\n'''
    if text.count(local_anchor) != 1 or text.count(cloud_anchor) != 1 or "Memory_AG_Idx_Queue.sv" in text:
        raise BuildError("p22 production identity collector surface differs")
    text = text.replace(local_anchor, local_insert, 1).replace(cloud_anchor, cloud_insert, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": RUNTIME, "sha256": base.sha256(path),
        "added_leaf": "Memory_AG_Idx_Queue.sv", "local_and_cloud_sha256": LOCAL_MEMORY_AG_SHA256,
        "collection_timing": "after actual production compile", "identity_difference_blocks_simulator": False,
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p23 freezes p22 DUT/config/numeric payload and adds one bounded edge-qualified "
        "MSE4 epoch-flow observer plus actual Memory_AG_Idx_Queue production identity. "
        "It is c0 diagnostic-only until formal server return."
    )
    paths = base.projected_paths(package, value)
    longest = max(paths, key=lambda item: (len(item), item))
    value["path_budget"]["max_projected_absolute_path_chars"] = value["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(path, value)
    return value


def patch_pointer_readme(package: Path) -> None:
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p23-epochflow-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p23 epoch-flow diagnostic\n\n"
        "Fresh c0 successor of p22. It binds upstream issue, Memory_AG masks and queue "
        "transactions without changing DUT/config/numeric payload.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(
    package: Path, contract: dict[str, Any], changed: list[str],
    observer: dict[str, Any], runner: dict[str, Any], identity: dict[str, Any],
) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P22_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P22_EO_FIX_PASS_EPOCH_FLOW_SUCCESSOR_REQUIRED":
        raise BuildError("formal p22 analysis is not accepted")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p23-epochflow-package-v1",
        "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID, "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip", "status": "PACKAGE_READY_NOT_RUN",
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "rule_receipts": [{"path": rel, "bytes": (ROOT / rel).stat().st_size, "sha256": base.sha256(ROOT / rel)} for rel in RULE_PATHS],
        "rule_receipts_current_match": True,
    })
    value["source_p22_formal_return_analysis"] = {
        "path": P22_ANALYSIS.relative_to(ROOT).as_posix(), "sha256": base.sha256(P22_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"], "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"], "compile_passed": True,
        "c0_natural_terminal": False, "formal_D_claimed": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p22 isolated missing MSE4 input1 token but did not distinguish upstream issue from Memory_AG mask/queue ownership and did not collect the actual target leaf identity",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["observer_binding"].update({
        "sha256": observer["final_sha256"], "source_sha256": observer["final_sha256"],
        "size_bytes": observer["final_bytes"], "changed_in_p23": True,
        "p23_epoch_flow": observer, "new_dut_hierarchy_references": True,
    })
    features = value.get("diagnostic_features", [])
    features.append({
        "feature": "RETURN_OBS_EPOCH_FLOW", "runtime_enable_parameter": "+RETURN_OBS_EPOCH_FLOW",
        "limit_parameter": "+RETURN_OBS_EPOCH_FLOW_LIMIT=256",
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1", "edge_schema": "EPOCH_FLOW_V1",
        "clock": "u_NDP_Top_new.clk_db", "reset": "u_NDP_Top_new.rst_n_db",
        "progress_semantics": "descriptor/Buffer counter edges, new-token accepts and FIFO write/read accepts only; stable levels are snapshots",
    })
    value["diagnostic_features"] = features
    value["p23_epoch_flow_observer"] = {**observer, "runner": runner, "production_identity": identity}
    expected = value["expected_production_rtl_identity"]
    expected["leaves"]["Memory_AG_Idx_Queue.sv"] = LOCAL_MEMORY_AG_SHA256
    expected["cloud_authority_leaves"]["Memory_AG_Idx_Queue.sv"] = LOCAL_MEMORY_AG_SHA256
    value["cloud_rtl_authority"]["leaves"]["Memory_AG_Idx_Queue.sv"] = LOCAL_MEMORY_AG_SHA256
    value["release_gate_applicability"].update({
        "package_local_hdl": "blocking_applicable_changed_private_xmr_observer",
        "diagnostic_predicate_trace": "blocking_applicable_changed_edge_qualification",
        "runner_control_flow": "blocking_applicable_fresh_identity_and_plusarg",
        "materialized_config": "receipt_reuse_byte_equal_p22",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "exact Memory_AG leaf/filelist/instance identity plus focused positive, leaf deletion/rename and wrong sibling negative controls",
    }
    value["release_gate_matrix"]["diagnostic_predicate_trace"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "same-clock edge trace for terminal2/3, input accept, simultaneous queue events and stable-level no-progress",
    }
    value["release_gate_matrix"]["runner_control_flow"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "normal/preflight/compile/HUP/INT/TERM repeatable finalizer; p22 runner control byte-equal after identity and plusarg normalization",
    }
    value["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "87 p22 installed payload members byte-equal and SCA identity-normalized equal",
        "causal_transaction_ledger": "receipt_reuse_p18", "boundary_microtrace": "receipt_reuse_p18",
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    value["identity_rebound_text_members"] = changed
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [item.relative_to(package).as_posix() for item in package.rglob("*") if item.is_file() and item != path] + ["package_manifest.json"]
    value["path_length_budget"].update({
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{rel}") for rel in inner),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(rel).parts) for rel in inner),
        "max_inner_component_chars": max(len(part) for rel in inner for part in PurePosixPath(rel).parts),
        "outer_identity_repeated_inside": False,
    })
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    package = base.safe_extract(SOURCE_ZIP, destination)
    changed = replace_identity(package)
    observer = patch_observer(package)
    runner = patch_runner(package)
    identity = patch_runtime_identity(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, changed, observer, runner, identity)
    return package, {"identity_members": changed, "observer": observer, "runner": runner, "production_identity": identity}


def frozen_checks(package: Path) -> dict[str, Any]:
    import zipfile
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source = {name[len(SOURCE_ID) + 1:]: archive.read(name) for name in archive.namelist() if name.startswith(SOURCE_ID + "/") and not name.endswith("/")}
    frozen = sorted(name for name in source if name.startswith("workload/runtime/runs/c0/install/"))
    exact = all((package / name).read_bytes() == source[name] for name in frozen)
    sca = {}
    for rel in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json"):
        sca[rel] = (package / rel).read_text(encoding="utf-8").replace(PACKAGE_ID, SOURCE_ID) == source[rel].decode()
    return {
        "frozen_install_payload_member_count": len(frozen),
        "frozen_install_payload_byte_equal": exact,
        "sca_identity_normalized_equal": sca,
        "numeric_w3_golden_workload_config_mapping_bitstream_execplan_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json")
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p23 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p22 source differs")
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    if profile.get("contract_valid") is not True or profile.get("package_id") != PACKAGE_ID:
        raise BuildError("current p23 shadow build profile is invalid")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()):
        raise BuildError("frozen p22 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p23_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p23 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p23-epochflow-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT", "package_identity": PACKAGE_ID,
        "source_p22_zip_sha256": SOURCE_SHA256, "source_p22_analysis_sha256": base.sha256(P22_ANALYSIS),
        "build_profile_sha256": base.sha256(BUILD_PROFILE),
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size, "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic, "observer": receipts["observer"],
        "runner": receipts["runner"], "production_identity": receipts["production_identity"],
        "identity_rebound_text_members": receipts["identity_members"], "frozen": frozen,
        "functional_rtl_modified": False, "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
