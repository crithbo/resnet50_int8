#!/usr/bin/env python3
"""Build the fresh serialized Conv LC-branch A/B targeted successor."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v98b_lcdup_tuple10"
OLD = "r5_n4_hw_v91b_normfix"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v98b_lcdup_tuple10_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_serialized_node0004/r5_n4_hw_v91b_normfix/r5_n4_hw_v91b_normfix.zip"
AB = ROOT / "artifacts/operator_config_validation/r5-node0004-lc-branch-duplication-ab-v3"
AB_OUT = ROOT / "outputs/conv_node0004_lc_branch_duplication_ab_v3"
B_PIPE = AB / "B/execplan/pipeline_output"
TEXT = {".json", ".md", ".sh", ".py", ".sv", ".svh", ".v", ".vh", ".txt"}

TOP = "u_NDP_Top_new"
SLICE = TOP + ".slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice"
IGA = SLICE + ".u_Index_Generation_Array"
MSE = SLICE + ".u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
MEMQ = MSE + ".u_Memory_AG_Idx_Queue"
PE8 = IGA + ".IGA_PE[8].u_IGA_PE"
LC7 = IGA + ".IGA_LC[7].u_IGA_LC"
LC19 = IGA + ".IGA_LC[19].u_IGA_LC"
LC6 = IGA + ".IGA_LC[6].u_IGA_LC"

TOP_SRC = "rtl/NDP_Top.sv"
IGA_SRC = "rtl/Slice/Index_Generation_Array/Index_Generation_Array.sv"
LC_SRC = "rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC.sv"
LCC_SRC = "rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC_Counter.sv"
PE_SRC = "rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE.sv"
PEI_SRC = "rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE_Inbuffer.sv"
PEO_SRC = "rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE_Outbuffer.sv"
MEM_SRC = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv"
WR_SRC = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
DATA_SRC = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv"
GLOBAL_SRC = "rtl/Global/global_ctrl.sv"


def row(signal_id: str, width: int, hierarchy: str, source: str, module: str, roles: list[str]) -> tuple[str, int, str, str, str, list[str]]:
    return signal_id, width, hierarchy, source, module, roles


RAW = [
    row("sig_clk", 1, TOP + ".clk_db", TOP_SRC, "NDP_Top_new", ["clock"]),
    row("sig_rst_n", 1, TOP + ".rst_n_db", TOP_SRC, "NDP_Top_new", ["reset"]),
    row("sig_slice_rst", 1, MSE + ".slice_rst", WR_SRC, "Memory_WR_Stream_Engine", ["reset", "internal_clear"]),
    row("sig_lc15_out", 23, IGA + ".iga_lc_outport[7]", IGA_SRC, "Index_Generation_Array", ["source", "producer"]),
    row("sig_lc15_valid", 1, LC7 + ".u_IGA_LC_Counter.iga_lc_cnt_outport_valid_bit", LCC_SRC, "IGA_LC_Counter", ["valid"]),
    row("sig_lc15_bp", 1, LC7 + ".iga_lc_cnt_bp_post", LC_SRC, "IGA_LC", ["ready", "backpressure"]),
    row("sig_lc3_out", 23, IGA + ".iga_lc_outport[19]", IGA_SRC, "Index_Generation_Array", ["source", "producer", "output"]),
    row("sig_lc3_valid", 1, LC19 + ".u_IGA_LC_Counter.iga_lc_cnt_outport_valid_bit", LCC_SRC, "IGA_LC_Counter", ["valid"]),
    row("sig_lc3_bp", 1, LC19 + ".iga_lc_cnt_bp_post", LC_SRC, "IGA_LC", ["ready", "backpressure"]),
    row("sig_lc9_out", 23, IGA + ".iga_lc_outport[6]", IGA_SRC, "Index_Generation_Array", ["source", "producer"]),
    row("sig_lc9_valid", 1, LC6 + ".u_IGA_LC_Counter.iga_lc_cnt_outport_valid_bit", LCC_SRC, "IGA_LC_Counter", ["valid"]),
    row("sig_lc9_bp", 1, LC6 + ".iga_lc_cnt_bp_post", LC_SRC, "IGA_LC", ["ready", "backpressure"]),
    row("sig_pe8_enable0", 1, PE8 + ".u_IGA_PE_Inbuffer.iga_pe_inbuffer_enbale[0]", PEI_SRC, "IGA_PE_Inbuffer", ["request"]),
    row("sig_pe8_enable2", 1, PE8 + ".u_IGA_PE_Inbuffer.iga_pe_inbuffer_enbale[2]", PEI_SRC, "IGA_PE_Inbuffer", ["request", "accept"]),
    row("sig_pe8_valid", 3, PE8 + ".u_IGA_PE_Inbuffer.iga_pe_inport_valid_bit", PEI_SRC, "IGA_PE_Inbuffer", ["valid"]),
    row("sig_pe8_last", 3, PE8 + ".u_IGA_PE_Inbuffer.iga_pe_inport_last_bit", PEI_SRC, "IGA_PE_Inbuffer", ["internal_state"]),
    row("sig_pe8_last_index", 12, PE8 + ".u_IGA_PE_Inbuffer.iga_pe_inport_last_index", PEI_SRC, "IGA_PE_Inbuffer", ["selected_port", "selected_bank", "selected_lane"]),
    row("sig_pe8_bp", 3, PE8 + ".iga_pe_inbuffer_bp_pre", PE_SRC, "IGA_PE", ["ready", "backpressure"]),
    row("sig_pe8_matched", 1, PE8 + ".u_IGA_PE_Inbuffer.iga_pe_inbuffer_matched", PEI_SRC, "IGA_PE_Inbuffer", ["internal_match"]),
    row("sig_pe8_wr", 1, PE8 + ".u_IGA_PE_Outbuffer.normal_mode_wr_handshake", PEO_SRC, "IGA_PE_Outbuffer", ["queue_enqueue", "accept"]),
    row("sig_pe8_rd", 1, PE8 + ".u_IGA_PE_Outbuffer.normal_mode_rd_handshake", PEO_SRC, "IGA_PE_Outbuffer", ["queue_dequeue"]),
    row("sig_pe8_count", 2, PE8 + ".u_IGA_PE_Outbuffer.iga_pe_outbuffer_count", PEO_SRC, "IGA_PE_Outbuffer", ["queue_count", "internal_state"]),
    row("sig_pe8_out", 23, PE8 + ".iga_pe_outport", PE_SRC, "IGA_PE", ["output"]),
    row("sig_mem_i1_port", 23, IGA + ".iga_pe_outport[8]", IGA_SRC, "Index_Generation_Array", ["source", "producer"]),
    row("sig_mem_i1_valid", 1, MEMQ + ".mem_idx_valid_bit_unmasked[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["valid"]),
    row("sig_mem_i1_last", 1, MEMQ + ".mem_idx_last_bit_unmasked[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["internal_state"]),
    row("sig_mem_i1_same", 1, MEMQ + ".mem_idx_same_bit_unmasked[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["internal_state"]),
    row("sig_mem_i1_last_index", 4, MEMQ + ".mem_idx_last_index[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["selected_port"]),
    row("sig_mem_i1_index", 16, MEMQ + ".mse_mem_queue_idx[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["source"]),
    row("sig_mem_i1_bp", 1, MEMQ + ".mse_mem_queue_bp_pre[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["ready", "accept"]),
    row("sig_mem_i1_gotten", 1, MEMQ + ".mem_idx_gotten_bit[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["internal_state"]),
    row("sig_mem_i1_split_wr", 1, MEMQ + ".mem_idx_split_fifo_wr_en[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["queue_enqueue"]),
    row("sig_mem_i1_split_empty", 1, MEMQ + ".idx_split_fifo_empty[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["queue_empty"]),
    row("sig_mem_i1_fifo_valid", 1, MEMQ + ".mem_idx_fifo_valid_bit_masked[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["valid"]),
    row("sig_mem_i1_queue_bp", 1, MEMQ + ".mem_idx_queue_bp_pre[1]", MEM_SRC, "Memory_AG_Idx_Queue", ["ready", "backpressure"]),
    row("sig_mem_all_match", 1, MEMQ + ".mem_all_idx_matched", MEM_SRC, "Memory_AG_Idx_Queue", ["internal_match"]),
    row("sig_mem_ag_wr", 1, MEMQ + ".mem_ag_idx_queue_wr_en", MEM_SRC, "Memory_AG_Idx_Queue", ["queue_enqueue", "accept"]),
    row("sig_mem_ag_rd", 1, MEMQ + ".mem_ag_idx_queue_rd_en", MEM_SRC, "Memory_AG_Idx_Queue", ["queue_dequeue"]),
    row("sig_mem_ag_empty", 1, MEMQ + ".mem_ag_idx_queue_empty", MEM_SRC, "Memory_AG_Idx_Queue", ["queue_empty"]),
    row("sig_mem_ag_full", 1, MEMQ + ".mem_ag_idx_queue_full", MEM_SRC, "Memory_AG_Idx_Queue", ["queue_full", "backpressure"]),
    row("sig_mem_tag_valid", 1, MSE + ".mse_mem_ag_tag_valid", WR_SRC, "Memory_WR_Stream_Engine", ["valid", "output"]),
    row("sig_mem_tag", 6, MSE + ".mse_mem_ag_tag", WR_SRC, "Memory_WR_Stream_Engine", ["output"]),
    row("sig_mem_idx", 48, MSE + ".mse_mem_ag_idx", WR_SRC, "Memory_WR_Stream_Engine", ["output"]),
    row("sig_prepared_count", 6, MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_cnt", DATA_SRC, "WR_Data_Channel", ["queue_count", "internal_state"]),
    row("sig_prepared_wr", 1, MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_wr_hs", DATA_SRC, "WR_Data_Channel", ["queue_enqueue", "producer"]),
    row("sig_prepared_rd", 1, MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_rd_hs", DATA_SRC, "WR_Data_Channel", ["queue_dequeue", "accept"]),
    row("sig_prepared_valid", 1, MSE + ".u_WR_Data_Channel.wr_data_chl_prepared_data_vld", DATA_SRC, "WR_Data_Channel", ["valid"]),
    row("sig_wdata_valid", 2, MSE + ".mse2mem_wdata_valid", WR_SRC, "Memory_WR_Stream_Engine", ["valid", "wdata"]),
    row("sig_wdata_ready", 2, MSE + ".mem2mse_wdata_ready", WR_SRC, "Memory_WR_Stream_Engine", ["ready", "accept"]),
    row("sig_slice_finish", 1, MSE + ".slice_cmpt_finish", WR_SRC, "Memory_WR_Stream_Engine", ["terminal", "finish"]),
    row("sig_exec_fetch_finish", 1, TOP + ".u_global_ctrl.exec_fetch_finish", GLOBAL_SRC, "global_ctrl", ["stage", "terminal"]),
    row("sig_exec_slice13_finish", 1, TOP + ".u_global_ctrl.exec_slice_finish[13]", GLOBAL_SRC, "global_ctrl", ["finish", "formal_d"]),
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def safe_import() -> None:
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("source ZIP CRC failure")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts or pure.parts[0] != OLD:
                raise RuntimeError(f"unsafe source member: {info.filename}")
            relative = PurePosixPath(*pure.parts[1:])
            if not relative.parts:
                continue
            data = archive.read(info)
            target = TREE.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.suffix.lower() in TEXT:
                data = data.decode("utf-8").replace(OLD, PACKAGE).encode("utf-8")
            target.write_bytes(data)
            if (info.external_attr >> 16) & stat.S_IXUSR:
                target.chmod(0o755)


def load_base() -> Any:
    source = ROOT / "tools/build_node0004_v88b_observerwide_successor_v89b.py"
    spec = importlib.util.spec_from_file_location("v89_observer_base", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE
    module.HIER = "tb_NDP_Top_new_phy"
    module.RAW_SIGNALS = RAW
    return module


def source_bytes(relative: str) -> bytes:
    return (ROOT / "NDP_copy01" / relative).read_bytes()


def signal_catalog() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for signal_id, width, hierarchy, source, module, roles in RAW:
        leaf = re.sub(r"\[[0-9]+\]", "", hierarchy.rsplit(".", 1)[-1])
        lines = source_bytes(source).decode("utf-8", errors="replace").splitlines()
        match = next((line.strip() for line in lines if leaf in line and not line.strip().startswith("//")), leaf)
        result.append({
            "signal_id": signal_id,
            "symbol_id": "sym_" + sha_bytes(f"{source}:{leaf}".encode())[:24],
            "exact_hierarchy": "tb_NDP_Top_new_phy." + hierarchy,
            "target_module": module,
            "source_path": source,
            "source_sha256": sha_bytes(source_bytes(source)),
            "declaration_span_sha256": sha_bytes(match.encode()),
            "width_bits": width,
            "owner_clock_signal_id": "sig_clk",
            "owner_reset_signal_id": "sig_rst_n",
            "roles": roles,
            "source_binding": "ACTUAL_SOURCE_NET",
            "derived_expected_equation": False,
            "observer_drives_dut": False,
        })
    return result


def make_contract(base: Any) -> dict[str, object]:
    value = base.contract()
    signals = signal_catalog()
    roles = [
        "clock", "reset", "stage", "source", "producer", "queue_enqueue", "queue_dequeue",
        "queue_count", "queue_full", "queue_empty", "request", "valid", "ready", "accept",
        "backpressure", "selected_port", "selected_bank", "selected_lane", "internal_match",
        "internal_state", "internal_clear", "output", "wdata", "terminal", "finish", "formal_d",
    ]
    observations = [
        {"observation_id": "obs_copied_lc", "layer": "FIRST_DIVERGENCE_UPSTREAM_ONE", "signal_ids": ["sig_lc15_valid", "sig_lc15_bp", "sig_lc3_valid", "sig_lc3_bp", "sig_lc9_valid", "sig_lc9_bp"], "predicate": "copied LC3 receives LC15 epoch and advances independently of original LC9 row branch"},
        {"observation_id": "obs_pe8_tuple10", "layer": "FIRST_DIVERGENCE_CURRENT", "signal_ids": ["sig_pe8_enable0", "sig_pe8_enable2", "sig_pe8_valid", "sig_pe8_last", "sig_pe8_last_index", "sig_pe8_matched", "sig_pe8_wr", "sig_pe8_rd", "sig_pe8_out"], "predicate": "PE8 joins second-epoch Q1 and emits metadata tuple 10"},
        {"observation_id": "obs_memory_tuple", "layer": "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "signal_ids": ["sig_mem_i1_valid", "sig_mem_i1_last", "sig_mem_i1_same", "sig_mem_i1_index", "sig_mem_i1_bp", "sig_mem_i1_split_wr", "sig_mem_all_match", "sig_mem_ag_wr", "sig_mem_tag_valid"], "predicate": "Memory_AG accepts the tenth tuple and completes ten 32-unit metadata transactions"},
        {"observation_id": "obs_terminal_formald", "layer": "STATE_HOLD_CLEAR", "signal_ids": ["sig_slice_rst", "sig_mem_ag_empty", "sig_prepared_count", "sig_prepared_wr", "sig_prepared_rd", "sig_prepared_valid", "sig_wdata_valid", "sig_wdata_ready", "sig_slice_finish", "sig_exec_fetch_finish", "sig_exec_slice13_finish"], "predicate": "320 prepared units drain against ten metadata tuples and reach natural terminal/Formal-D"},
    ]
    signatures = [
        ("candidate_success_tuple10_natural_formald", [True, True, True, True]),
        ("candidate_copied_lc_not_advancing", [False, False, False, False]),
        ("candidate_pe8_join_or_output_hold", [True, False, False, False]),
        ("candidate_memory_input1_accept_hold", [True, True, False, False]),
        ("candidate_post_tuple10_drain_hold", [True, True, True, False]),
    ]
    obs_ids = [item["observation_id"] for item in observations]
    value.update({
        "activation_epoch": "observer-only-wide-causal-v1",
        "signals": signals,
        "role_coverage": [{"role": role, "disposition": "covered", "signal_ids": [item["signal_id"] for item in signals if role in item["roles"]]} for role in roles],
        "boundary_observations": observations,
        "candidates": [{"candidate_id": name, "signature": dict(zip(obs_ids, signature))} for name, signature in signatures],
        "config_mapper_ab_binding": {
            "workaround": "duplicate logical LC9 branch into formerly dormant logical LC3 and route PE1.inport2 to LC3",
            "logical_to_physical": {"LC15": "LC7", "copied_LC3": "LC19", "original_LC9": "LC6", "PE1": "PE8", "GROUP4_ROW_LC": "ROW_LC4"},
            "expected_metadata_tuple_count": 10,
            "expected_prepared_unit_count": 320,
            "mapper_report_member": f"{PACKAGE}/provenance/lc_branch_duplication_mapper_ab_report.json",
        },
        "family_target_epoch": "node0004-lc-branch-duplication-targeted-v1",
        "claim_boundary": "Source-bound actual-net targeted observer transport for the locally equivalent LC-branch workaround. Production tuple10, natural terminal and Formal-D remain unproven until the formal return.",
    })
    return value


def file_rows() -> list[dict[str, object]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def deterministic_zip() -> None:
    temporary = ZIP.with_name(f".{ZIP.name}.tmp.{os.getpid()}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            relative = path.relative_to(TREE.parent).as_posix()
            info = zipfile.ZipInfo(relative, (2026, 8, 16, 0, 0, 0))
            mode = 0o755 if os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("generated ZIP CRC failure")
    os.replace(temporary, ZIP)


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    TREE.mkdir(parents=True)
    safe_import()
    base = load_base()

    replacements = {
        B_PIPE / "install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin": TREE / "workload/runtime/runs/c0/install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
        B_PIPE / "install/execplan.txt": TREE / "workload/runtime/runs/c0/install/execplan.txt",
        B_PIPE / "install/execplan_op_w0.txt": TREE / "workload/runtime/runs/c0/install/execplan_op_w0.txt",
    }
    for source, target in replacements.items():
        shutil.copyfile(source, target)

    provenance = {
        AB_OUT / "mapper_ab_report.json": TREE / "provenance/lc_branch_duplication_mapper_ab_report.json",
        AB_OUT / "boundary_microtrace.json": TREE / "provenance/lc_branch_duplication_boundary_microtrace.json",
        AB_OUT / "RULE_GAP_AUDIT.json": TREE / "provenance/lc_branch_duplication_rule_gap_audit.json",
        AB / "B/execplan/execplan_validation_report.json": TREE / "provenance/B_execplan_validation_report.json",
        AB / "B/execplan/request_address_validation_report.json": TREE / "provenance/B_request_address_validation_report.json",
        AB / "B/execplan/mapping_evidence/op_w0/mapping_review.json": TREE / "provenance/B_mapping_review.json",
        AB / "configs/B_duplicate_lc_branch.json": TREE / "provenance/B_duplicate_lc_branch_config.json",
    }
    for source, target in provenance.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    contract = make_contract(base)
    write_json(TREE / "contracts/observer_only_wide_causal_contract.json", contract)
    (TREE / "tb_probe/observer_only_wide_causal.svh").write_text(base.observer_source(contract["signals"]), encoding="utf-8", newline="\n")
    write_json(TREE / "contracts/server_post_sim_return_request.json", base.post_request())
    shutil.copyfile(ROOT / "tools/node0004_v98_package_release_preflight.py", TREE / "package_tools/package_release_preflight.py")

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        raise RuntimeError("source runner production marker differs")
    runner_path.write_text(runner, encoding="utf-8", newline="\n")
    runner_path.chmod(0o755)

    runner_contract_path = TREE / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = sha_file(runner_path)
    write_json(runner_contract_path, runner_contract)
    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["request_sha256"] = sha_file(TREE / "contracts/server_post_sim_return_request.json")
    write_json(post_contract_path, post_contract)

    mapper = json.loads((AB_OUT / "mapper_ab_report.json").read_text(encoding="utf-8"))
    manifest = {
        "schema": "node0004-v98b-lcdup-tuple10-package-manifest-v1",
        "package_id": PACKAGE,
        "install_name": PACKAGE,
        "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "diagnostic_mode": "OBSERVER_ONLY_WIDE_CAUSAL",
        "observer_only_profile": "OBSERVER_ONLY_WIDE_CAUSAL_V1",
        "observer_only_contract_sha256": sha_file(TREE / "contracts/observer_only_wide_causal_contract.json"),
        "activation_epoch": "node0004-lc-branch-duplication-targeted-v1",
        "post_sim_conjunction_activation_epoch": "observer-only-post-sim-conjunction-fix-v1",
        "runtime_preflight_native_flow_activation_epoch": "runtime-preflight-native-flow-v1",
        "first_fresh_after_change": True,
        "release_admission_required": True,
        "dump": {"DUMP_VCD": 0, "DUMP_FSDB": 0, "TB_DUMP_FSDB": 0},
        "config_workaround": "DUPLICATE_LC_BRANCH_LC9_TO_LC3_FOR_PE1_INPUT2",
        "config_mapper_ab_status": mapper["classification"],
        "config_mapper_ab_negligible_cost": mapper["cost"]["negligible"],
        "frozen": {"numeric": True, "workload": True, "golden": True, "functional_rtl": True, "target_diagnostic": True},
        "authorized_config_diff": mapper["candidate"]["config_diff"],
        "retired_buf_idx_queue_bp_pre_comparator_present": False,
        "source_package": OLD,
        "previous_version_progress": "v97 validated one missing 32-unit Memory_AG input1 metadata tuple; local mapper A/B then proved a copied LC branch preserves address order, output math, command count, data-plane traffic and configured data-plane cycle bound with one extra LC and negligible one-shot configuration overhead.",
        "current_purpose": "Production-confirm that copied logical LC3 emits second-epoch Q1, PE1/physical PE8 produces tuple10, Memory_AG consumes ten tuples for 320 prepared units, and the unchanged operator reaches natural terminal and Formal-D.",
        "server_actions_performed": [],
        "files": [],
    }
    write_json(TREE / "package_manifest.json", manifest)
    readme = f"""# {PACKAGE}

Previous progress: v97 validated that Memory_AG input1 receives nine metadata tuples for 320 prepared-data units. The local mapper A/B proves that copying logical LC9 into dormant LC3 and routing PE1.inport2 to LC3 preserves output math, address order, command count, data-plane memory traffic and configured data-plane cycle bound. It consumes one additional LC (15/20 active, five spare) and one additional 64-bit configuration word.

Current purpose: confirm in one targeted observer-only run that copied LC3 emits second-epoch Q1, physical PE8 creates tuple10, Memory_AG accepts ten tuples, 320 prepared units drain, and natural terminal/Formal-D are reached.

Run only after separate authorization:

    bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01

No VPD/FSDB/VCD/FST is used. Functional RTL, numeric, workload and golden payloads are frozen. The old derived ACK comparator remains absent.
"""
    (TREE / "README.md").write_text(readme, encoding="utf-8", newline="\n")

    manifest["files"] = file_rows()
    write_json(TREE / "package_manifest.json", manifest)
    deterministic_zip()
    write_json(OUT / "build_receipt.json", {
        "schema": "node0004-v98b-lcdup-tuple10-build-v1",
        "package_id": PACKAGE,
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha_file(ZIP)},
        "mapper_ab_report": {"path": (AB_OUT / "mapper_ab_report.json").relative_to(ROOT).as_posix(), "sha256": sha_file(AB_OUT / "mapper_ab_report.json")},
        "signal_count": len(RAW),
        "pass": True,
        "errors": [],
    })
    print(json.dumps({"package": PACKAGE, "signals": len(RAW), "zip": str(ZIP)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
