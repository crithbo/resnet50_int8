#!/usr/bin/env python3
"""Build the p24 public Stream_Engine select-port diagnostic from exact p23."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p23_epochflow_package as previous


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p23_epochflow"
PACKAGE_ID = "r5_n4_0cc_p24_selport"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_878_970
SOURCE_SHA256 = "f70f9a7643012a013736df3026057ca981f19d543c572064d3cd69edaa46a788"
P23_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p23_return_analysis/report.json"
BUILD_PROFILE = ROOT / "outputs/conv_native_four_lane_0ccae916_p24_selport/server_package_build_profile.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p24_selport/build"
OBSERVER = "tb_probe/native_return_observer.svh"
RUNTIME = "package_tools/node0004_assumed_hardware_server_runtime.py"
SOURCE_OBSERVER_SHA256 = "00ed2bd1295ac51bfb7ef8aa1476a0ace09f4246d7fa4c92bf258aec7c580911"
CONNECT_SHA256 = "0ca375c4af56f7f6fe9e7055a39ac7370d91e6048b2aa9f3ae0a4910deae5425"
WR_MSE_SHA256 = "c97a5b4a3587384d5b57b2a5db288a44b2166584c236307c69d26bb04f389127"
RULE_PATHS = previous.RULE_PATHS
base = previous.base

CONNECT = (
    "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
    "slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
    "u_Stream_Engine_Connect"
)
WR_MSE = (
    "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
    "slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4]."
    "WR_MSE.u_Memory_WR_Stream_Engine"
)

SELECT_PORT_BLOCK = f'''    // p24 PUBLIC_SELECT_PORT_BEGIN
    // Public module ports only. Qualified handshakes and state snapshots have
    // independent budgets, so held/changing state cannot consume progress rows.
    bit return_obs_sp_enabled;
    integer return_obs_sp_qualified_limit;
    integer return_obs_sp_state_limit;
    integer return_obs_sp_qualified_plusarg_status;
    integer return_obs_sp_state_plusarg_status;
    integer return_obs_sp_qualified_records;
    integer return_obs_sp_state_records;
    logic [3:0] return_obs_sp_prev_src;
    logic [22:0] return_obs_sp_prev_pe7;
    logic [15:0] return_obs_sp_prev_connect_idx;
    logic [6:0] return_obs_sp_prev_connect_tag;
    logic [15:0] return_obs_sp_prev_memory_idx;
    logic [6:0] return_obs_sp_prev_memory_tag;
    logic [2:0] return_obs_sp_prev_bp;

    initial begin
        return_obs_sp_enabled = $test$plusargs("RETURN_OBS_SELECT_PORT");
        return_obs_sp_qualified_limit = 128;
        return_obs_sp_state_limit = 64;
        return_obs_sp_qualified_plusarg_status = $value$plusargs(
            "RETURN_OBS_SELECT_PORT_QUAL_LIMIT=%d", return_obs_sp_qualified_limit
        );
        return_obs_sp_state_plusarg_status = $value$plusargs(
            "RETURN_OBS_SELECT_PORT_STATE_LIMIT=%d", return_obs_sp_state_limit
        );
        return_obs_sp_qualified_records = 0;
        return_obs_sp_state_records = 0;
        return_obs_sp_prev_src = 0;
        return_obs_sp_prev_pe7 = 0;
        return_obs_sp_prev_connect_idx = 0;
        return_obs_sp_prev_connect_tag = 0;
        return_obs_sp_prev_memory_idx = 0;
        return_obs_sp_prev_memory_tag = 0;
        return_obs_sp_prev_bp = 0;
        #0;
        if (return_obs_sp_enabled && n4d_fd != 0) begin
            $fdisplay(
                n4d_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_SELECT_PORT enabled=%0d qualified_limit=%0d state_limit=%0d schema=PUBLIC_SELECT_PORT_V1",
                return_obs_sp_enabled, return_obs_sp_qualified_limit,
                return_obs_sp_state_limit
            );
            $fflush(n4d_fd);
        end
    end

    task automatic return_obs_write_select_port(
        input integer row_kind,
        input integer event_mask
    );
        if (return_obs_sp_enabled && n4d_fd != 0) begin
            $fdisplay(
                n4d_fd,
                "%0t | PUBLIC_SELECT_PORT_V1 | kind=%0d event_mask=0x%0h qn=%0d sn=%0d terminal=%0d desc=%0d prepared=%0d src_id=%0d src_is_pe7=%0d pe7_word=0x%0h pe7_valid=%0d pe7_bp=%0d connect_idx=0x%0h connect_tag=0x%0h connect_valid=%0d connect_bp=%0d memory_idx=0x%0h memory_tag=0x%0h memory_valid=%0d memory_bp=%0d select_eq=%0d port_eq=%0d",
                $time, row_kind, event_mask,
                return_obs_sp_qualified_records, return_obs_sp_state_records,
                return_obs_wt_desc_terminal, return_obs_md_desc_hs,
                return_obs_md_prepared_wr,
                {CONNECT}.mse_mem_idx_src_id[4][1],
                {CONNECT}.mse_mem_idx_src_id[4][1] == 7,
                {CONNECT}.iga2se_mem_inport[4][7],
                {CONNECT}.iga2se_mem_inport[4][7][22],
                {CONNECT}.se2iga_mem_bp_pre[4][7][1],
                {CONNECT}.mse_mem_queue_idx[4][1],
                {CONNECT}.mse_mem_queue_tag[4][1],
                {CONNECT}.mse_mem_queue_tag[4][1][6],
                {CONNECT}.mse_mem_queue_bp_post[4][1],
                {WR_MSE}.mse_mem_queue_idx[1],
                {WR_MSE}.mse_mem_queue_tag[1],
                {WR_MSE}.mse_mem_queue_tag[1][6],
                {WR_MSE}.mse_mem_queue_bp_pre[1],
                ({CONNECT}.mse_mem_idx_src_id[4][1] == 7) &&
                    ({{{CONNECT}.mse_mem_queue_tag[4][1], {CONNECT}.mse_mem_queue_idx[4][1]}} ==
                     {CONNECT}.iga2se_mem_inport[4][7]),
                ({{{CONNECT}.mse_mem_queue_tag[4][1], {CONNECT}.mse_mem_queue_idx[4][1]}} ==
                 {{{WR_MSE}.mse_mem_queue_tag[1], {WR_MSE}.mse_mem_queue_idx[1]}})
            );
            $fflush(n4d_fd);
        end
    endtask

    always @(negedge u_NDP_Top_new.clk_db or negedge u_NDP_Top_new.rst_n_db) begin
        bit sp_pe7_accept;
        bit sp_connect_accept;
        bit sp_memory_accept;
        bit sp_state_change;
        integer sp_event_mask;
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_sp_qualified_records = 0;
            return_obs_sp_state_records = 0;
            return_obs_sp_prev_src = 0;
            return_obs_sp_prev_pe7 = 0;
            return_obs_sp_prev_connect_idx = 0;
            return_obs_sp_prev_connect_tag = 0;
            return_obs_sp_prev_memory_idx = 0;
            return_obs_sp_prev_memory_tag = 0;
            return_obs_sp_prev_bp = 0;
        end else if (return_obs_sp_enabled && n4d_active) begin
            sp_pe7_accept = {CONNECT}.iga2se_mem_inport[4][7][22] &&
                            {CONNECT}.se2iga_mem_bp_pre[4][7][1];
            sp_connect_accept = {CONNECT}.mse_mem_queue_tag[4][1][6] &&
                                {CONNECT}.mse_mem_queue_bp_post[4][1];
            sp_memory_accept = {WR_MSE}.mse_mem_queue_tag[1][6] &&
                               {WR_MSE}.mse_mem_queue_bp_pre[1];
            sp_event_mask = sp_pe7_accept + (sp_connect_accept << 1) +
                            (sp_memory_accept << 2);
            sp_state_change =
                {CONNECT}.mse_mem_idx_src_id[4][1] != return_obs_sp_prev_src ||
                {CONNECT}.iga2se_mem_inport[4][7] != return_obs_sp_prev_pe7 ||
                {CONNECT}.mse_mem_queue_idx[4][1] != return_obs_sp_prev_connect_idx ||
                {CONNECT}.mse_mem_queue_tag[4][1] != return_obs_sp_prev_connect_tag ||
                {WR_MSE}.mse_mem_queue_idx[1] != return_obs_sp_prev_memory_idx ||
                {WR_MSE}.mse_mem_queue_tag[1] != return_obs_sp_prev_memory_tag ||
                {{{WR_MSE}.mse_mem_queue_bp_pre[1],
                  {CONNECT}.mse_mem_queue_bp_post[4][1],
                  {CONNECT}.se2iga_mem_bp_pre[4][7][1]}} != return_obs_sp_prev_bp;
            if (return_obs_wt_desc_terminal >= 2 && sp_event_mask != 0 &&
                return_obs_sp_qualified_records < return_obs_sp_qualified_limit) begin
                return_obs_sp_qualified_records++;
                return_obs_write_select_port(1, sp_event_mask);
            end
            if (return_obs_wt_desc_terminal >= 2 && sp_state_change &&
                return_obs_sp_state_records < return_obs_sp_state_limit) begin
                return_obs_sp_state_records++;
                return_obs_write_select_port(2, 0);
            end
            return_obs_sp_prev_src = {CONNECT}.mse_mem_idx_src_id[4][1];
            return_obs_sp_prev_pe7 = {CONNECT}.iga2se_mem_inport[4][7];
            return_obs_sp_prev_connect_idx = {CONNECT}.mse_mem_queue_idx[4][1];
            return_obs_sp_prev_connect_tag = {CONNECT}.mse_mem_queue_tag[4][1];
            return_obs_sp_prev_memory_idx = {WR_MSE}.mse_mem_queue_idx[1];
            return_obs_sp_prev_memory_tag = {WR_MSE}.mse_mem_queue_tag[1];
            return_obs_sp_prev_bp = {{{WR_MSE}.mse_mem_queue_bp_pre[1],
                                     {CONNECT}.mse_mem_queue_bp_post[4][1],
                                     {CONNECT}.se2iga_mem_bp_pre[4][7][1]}};
        end
    end
    // p24 PUBLIC_SELECT_PORT_END
'''


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


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
        raise BuildError("exact p23 observer identity differs")
    text = source.decode()
    if "RETURN_OBS_SELECT_PORT" in text or "p24 PUBLIC_SELECT_PORT_BEGIN" in text:
        raise BuildError("source already contains p24 observer")
    combined = text.rstrip() + "\n" + SELECT_PORT_BLOCK.rstrip() + "\n"
    path.write_text(combined, encoding="utf-8", newline="\n")
    return {
        "path": OBSERVER, "source_bytes": len(source), "source_sha256": base.digest(source),
        "block_bytes": len(SELECT_PORT_BLOCK.encode()), "block_sha256": base.digest(SELECT_PORT_BLOCK.encode()),
        "final_bytes": path.stat().st_size, "final_sha256": base.sha256(path),
        "public_module_ports_only": True,
        "target_modules": ["Stream_Engine_Connect", "Memory_WR_Stream_Engine"],
        "clock": "u_NDP_Top_new.clk_db", "reset": "u_NDP_Top_new.rst_n_db",
        "qualified_and_state_budgets_independent": True,
        "functional_rtl_changed": False,
    }


def patch_runner(package: Path) -> dict[str, Any]:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old = "+RETURN_OBS_EPOCH_FLOW +RETURN_OBS_EPOCH_FLOW_LIMIT=256"
    new = "+RETURN_OBS_SELECT_PORT +RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128 +RETURN_OBS_SELECT_PORT_STATE_LIMIT=64"
    if text.count(old) != 2 or new in text:
        raise BuildError("p23 observer plusarg surface differs")
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {"path": "PREPARE_AND_RUN.sh", "sha256": base.sha256(path), "replacement_count": 2}


def patch_runtime_identity(package: Path) -> dict[str, Any]:
    path = package / RUNTIME
    text = path.read_text(encoding="utf-8")
    local_anchor = '''    "Memory_AG_Idx_Queue.sv": (\n        "b555ab22523540a9aa49d3eb51dee6eea9962086a71429028c69964de3819989"\n    ),\n'''
    cloud_anchor = '''    "Memory_AG_Idx_Queue.sv": "b555ab22523540a9aa49d3eb51dee6eea9962086a71429028c69964de3819989",\n'''
    local_insert = local_anchor + f'''    "Stream_Engine_Connect.sv": "{CONNECT_SHA256}",\n    "Memory_WR_Stream_Engine.sv": "{WR_MSE_SHA256}",\n'''
    cloud_insert = cloud_anchor + f'''    "Stream_Engine_Connect.sv": "{CONNECT_SHA256}",\n    "Memory_WR_Stream_Engine.sv": "{WR_MSE_SHA256}",\n'''
    if text.count(local_anchor) != 1 or text.count(cloud_anchor) != 1 or "Stream_Engine_Connect.sv" in text:
        raise BuildError("p23 production identity collector surface differs")
    text = text.replace(local_anchor, local_insert, 1).replace(cloud_anchor, cloud_insert, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": RUNTIME, "sha256": base.sha256(path),
        "added_leaves": {"Stream_Engine_Connect.sv": CONNECT_SHA256, "Memory_WR_Stream_Engine.sv": WR_MSE_SHA256},
        "collection_timing": "after actual production compile",
        "identity_difference_blocks_simulator": False,
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p24 freezes p23 DUT/config/numeric payload and replaces the p23 epoch-flow plusarg "
        "with one bounded public-port select-path observer. It remains c0 diagnostic-only."
    )
    paths = base.projected_paths(package, value)
    longest = max(paths, key=lambda item: (len(item), item))
    value["path_budget"]["max_projected_absolute_path_chars"] = value["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(path, value)
    return value


def patch_pointer_readme(package: Path) -> None:
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p24-select-port-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p24 public select-port diagnostic\n\n"
        "Fresh c0 successor of p23. It observes configured source, PE7 public input, Connect "
        "output and Memory-WR public input without changing DUT/config/numeric payload.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(package: Path, contract: dict[str, Any], changed: list[str], observer: dict[str, Any], runner: dict[str, Any], identity: dict[str, Any]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P23_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P23_EPOCH_FLOW_PASS_CONNECT_SELECTION_SUCCESSOR_REQUIRED":
        raise BuildError("formal p23 analysis is not accepted")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p24-select-port-package-v1",
        "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID, "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip", "status": "PACKAGE_READY_NOT_RUN",
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "rule_receipts": [{"path": rel, "bytes": (ROOT / rel).stat().st_size, "sha256": base.sha256(ROOT / rel)} for rel in RULE_PATHS],
        "rule_receipts_current_match": True,
    })
    value["source_p23_formal_return_analysis"] = {
        "path": P23_ANALYSIS.relative_to(ROOT).as_posix(), "sha256": base.sha256(P23_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"], "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"], "compile_passed": True,
        "c0_natural_terminal": False, "formal_D_claimed": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p23 proved actual Memory_AG queue traffic and PE7 index8 but did not distinguish configured source and the public Connect-to-Memory port boundary",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["observer_binding"].update({
        "sha256": observer["final_sha256"], "source_sha256": observer["final_sha256"],
        "size_bytes": observer["final_bytes"], "changed_in_p24": True,
        "p24_public_select_port": observer, "new_dut_hierarchy_references": True,
    })
    value["diagnostic_features"].append({
        "feature": "RETURN_OBS_SELECT_PORT", "runtime_enable_parameter": "+RETURN_OBS_SELECT_PORT",
        "qualified_limit_parameter": "+RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128",
        "state_limit_parameter": "+RETURN_OBS_SELECT_PORT_STATE_LIMIT=64",
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1", "edge_schema": "PUBLIC_SELECT_PORT_V1",
        "clock": "u_NDP_Top_new.clk_db", "reset": "u_NDP_Top_new.rst_n_db",
        "progress_semantics": "public valid-and-backpressure handshakes only; state snapshots use an independent budget",
    })
    value["p24_public_select_port_observer"] = {**observer, "runner": runner, "production_identity": identity}
    for name, sha in identity["added_leaves"].items():
        value["expected_production_rtl_identity"]["leaves"][name] = sha
        value["expected_production_rtl_identity"]["cloud_authority_leaves"][name] = sha
        value["cloud_rtl_authority"]["leaves"][name] = sha
    value["release_gate_applicability"].update({
        "package_local_hdl": "blocking_applicable_changed_public_port_observer",
        "diagnostic_predicate_trace": "blocking_applicable_changed_public_handshake_and_separate_budgets",
        "runner_control_flow": "blocking_applicable_fresh_identity_and_plusarg",
        "materialized_config": "receipt_reuse_byte_equal_p23",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "public Stream_Engine_Connect and Memory_WR_Stream_Engine ports; exact target module bytes/filelist/instance paths and XMR negatives",
    }
    value["release_gate_matrix"]["diagnostic_predicate_trace"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "same-clock qualified bitmask, separate state budget, exact logger/parser format trace and stable-level negative",
    }
    value["release_gate_matrix"]["runner_control_flow"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "normal/preflight/compile/HUP/INT/TERM repeatable finalizer; p23 runner normalized-equal except identity and plusarg",
    }
    value["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "87 p23 installed payload members byte-equal and SCA identity-normalized equal",
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
        raise BuildError("refusing to overwrite p24 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p23 source differs")
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    if profile.get("contract_valid") is not True or profile.get("package_id") != PACKAGE_ID:
        raise BuildError("current p24 shadow build profile is invalid")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()):
        raise BuildError("frozen p23 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p24_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p24 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p24-select-port-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT", "package_identity": PACKAGE_ID,
        "source_p23_zip_sha256": SOURCE_SHA256, "source_p23_analysis_sha256": base.sha256(P23_ANALYSIS),
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
