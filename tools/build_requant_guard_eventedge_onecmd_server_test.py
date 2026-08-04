#!/usr/bin/env python3
"""Build the frozen Requant guard-only coeff-to-outbuffer event diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# This builder never regenerates ONNX-derived semantics: it is required to copy
# the frozen predecessor byte-for-byte.  Keep the existing package helper
# importable in a minimal packaging environment where the unused ONNX runtime
# dependency is intentionally absent.
try:
    import onnx as _onnx  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    _onnx_stub = types.ModuleType("onnx")
    _onnx_stub.numpy_helper = types.ModuleType("onnx.numpy_helper")
    _onnx_stub.helper = types.ModuleType("onnx.helper")
    _onnx_stub.shape_inference = types.ModuleType("onnx.shape_inference")
    _onnx_stub.checker = types.ModuleType("onnx.checker")
    sys.modules["onnx"] = _onnx_stub
    sys.modules["onnx.numpy_helper"] = _onnx_stub.numpy_helper
    sys.modules["onnx.helper"] = _onnx_stub.helper
    sys.modules["onnx.shape_inference"] = _onnx_stub.shape_inference
if "onnxruntime" not in sys.modules:
    try:
        import onnxruntime as _onnxruntime  # type: ignore[import-not-found]  # noqa: F401
    except ModuleNotFoundError:
        sys.modules["onnxruntime"] = types.ModuleType("onnxruntime")
if "torch" not in sys.modules:
    try:
        import torch as _torch  # type: ignore[import-not-found]  # noqa: F401
    except ModuleNotFoundError:
        _torch_stub = types.ModuleType("torch")
        _torch_nn_stub = types.ModuleType("torch.nn")
        _torch_functional_stub = types.ModuleType("torch.nn.functional")
        _torch_stub.nn = _torch_nn_stub
        _torch_nn_stub.functional = _torch_functional_stub
        sys.modules["torch"] = _torch_stub
        sys.modules["torch.nn"] = _torch_nn_stub
        sys.modules["torch.nn.functional"] = _torch_functional_stub

from tools import build_requant_atomic_onecmd_server_test as base  # noqa: E402
from tools import build_requant_guard_only_onecmd_server_test as predecessor_builder  # noqa: E402


INSTALL_NAME = "rq_node0001_guardonly_sfu_eventedge_stock_v1"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
PREDECESSOR_NAME = "rq_node0001_guardonly_sfu_numeric_stock_v1"
PREDECESSOR = DEFAULT_OUTPUT.with_name(PREDECESSOR_NAME)
PREDECESSOR_ZIP = PREDECESSOR.with_suffix(".zip")
PREDECESSOR_ZIP_SHA256 = (
    "8e96d1bbd6e0379b8d33fca251b27bbc40bb32fc56d82418a3ae85e0515e1a1b"
)
PREDECESSOR_MANIFEST_SHA256 = (
    "d4b7ccf7ca24f0c4a940fb863ada3dc5c367797f71dfa04822aba400adbdf4ae"
)
AUTHORITY = (
    ROOT
    / "server_returns/"
    "rq_node0001_guardonly_sfu_numeric_stock_v1_return_analysis_20260727.json"
)
AUTHORITY_SHA256 = (
    "8dc774b0ddc23b7108414651a3fa7d24b68463232fca06e6ab72952d3adfe22b"
)
AUTHORITY_RECORD = (
    ROOT
    / ".agents/task_records/"
    "20260727_requant_guardonly_sfu_numeric_v1_return_analysis.md"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "f3fe8dd18c9e2009db4a2736c6c1e86841760d8ec023bb7b57562f27f5faff04"
)
REQUANT_RULE = ROOT / ".agents/rules/RequantizeUint8算子配置规则.md"
REQUANT_RULE_SHA256 = (
    "44e8ee38d1361f15d78bf5d7918fa10e4648370153178ad10d044fd5c9d26265"
)
CONTROL_REPORT = (
    ROOT
    / "server_returns/"
    "decode_silu_fp16N_fp32N_control_stock_v1_return_analysis_20260727.json"
)
CONTROL_REPORT_SHA256 = (
    "894b01355a888316a9f9475e38cfb2a565689895ba842955e31cc187dd3f8f6a"
)
CONTROL_RECORD = (
    ROOT
    / ".agents/task_records/"
    "20260727_decode_silu_control_stock_v1_return_analysis.md"
)
CONTROL_RECORD_SHA256 = (
    "b1cda36fc10c592c9093b20dbe69dd546fb25177b8e057e1a37c1c5513502a3e"
)
READ_RECEIPT = (
    ROOT
    / ".agents/task_records/"
    "20260727_requant_guardonly_sfu_eventedge_v1_read_receipt.json"
)
OBSERVER_TAIL_NAME = "requant_mse4_guard_observer_tail.svh"
TB_TARGET_RELATIVE_PATH = "native_return_observer.svh"
MUTABLE_PREDECESSOR_PATHS = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    base.MANIFEST_NAME,
    "package_tools/requant_atomic_server_runtime.py",
    "package_tools/requant_node0001_server_runtime.py",
    f"tb_probe/{OBSERVER_TAIL_NAME}",
    "validation/diagnostic_profile.json",
    "validation/guard_only_provenance.json",
    "validation/semantic_freeze_sfu_ready_v1_to_sfu_numeric_v1.json",
    "workload/runtime/sca_cfg.json",
}
FROZEN_SEMANTIC_PATHS = (
    "golden/guard_slice00_128b.txt",
    "golden/guard_slice01_128b.txt",
    "validation/address_domain_contract.json",
    "validation/expected_mse4_writes.json",
    "validation/generation_receipt.json",
    "validation/guard.json",
    "validation/lifecycle_contract.json",
    "validation/local_contract_report.json",
    "validation/manifest.json",
    "validation/semantic_contract.json",
    "validation/static_configuration_intent.json",
    "validation/native/op_w0_s00_guard/address_bound_config.json",
    "validation/native/op_w0_s00_guard/bitstream_128b.bin",
    "validation/native/op_w0_s00_guard/bitstream_64b.bin",
    "validation/native/op_w0_s00_guard/detailed_dump.txt",
    "validation/native/op_w0_s00_guard/mapping_review.json",
    "validation/native/op_w0_s00_guard/parsed_bitstream.txt",
    "workload/runtime/sca_cfg_D.json",
    "workload/runtime/payloads/execplan.txt",
    (
        "workload/runtime/payloads/cfg_pkg/"
        "op_w0_s00_guard_resnet50_requant_guard_node0001_bitstream_128b.bin"
    ),
    "workload/runtime/payloads/cfg_pkg/RequantGuard.txt",
    (
        "workload/runtime/payloads/inputs/op_w0_s00_guard/slice00/"
        "matrix_A_linearized_128bit.txt"
    ),
    (
        "workload/runtime/payloads/inputs/op_w0_s00_guard/slice01/"
        "matrix_A_linearized_128bit.txt"
    ),
)


class EventEdgePackageError(RuntimeError):
    """Raised when the event-qualified package cannot be proven deterministic."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    base._write_json(path, value)


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _semantic_records(root: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for relative in FROZEN_SEMANTIC_PATHS:
        path = root / relative
        if not path.is_file():
            raise EventEdgePackageError(f"frozen semantic file missing: {relative}")
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return records


def _verify_sources() -> dict[str, Any]:
    expected = (
        (SERVER_RULE, SERVER_RULE_SHA256, "server package rule"),
        (REQUANT_RULE, REQUANT_RULE_SHA256, "Requant rule"),
        (AUTHORITY, AUTHORITY_SHA256, "authoritative return analysis"),
        (
            CONTROL_REPORT,
            CONTROL_REPORT_SHA256,
            "native SiLU control return analysis",
        ),
        (
            CONTROL_RECORD,
            CONTROL_RECORD_SHA256,
            "native SiLU control task record",
        ),
        (
            AUTHORITY_RECORD,
            "ce38cde297f04420ce83c3c85e2ef610510575e8f5c3b0797430641cb7d0da64",
            "authoritative task record",
        ),
        (
            PREDECESSOR / base.MANIFEST_NAME,
            PREDECESSOR_MANIFEST_SHA256,
            "predecessor manifest",
        ),
    )
    identities: dict[str, Any] = {}
    for path, expected_sha, label in expected:
        if not path.is_file() or _sha256(path) != expected_sha:
            raise EventEdgePackageError(f"{label} identity differs")
        identities[label] = {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": expected_sha,
        }
    if (
        not PREDECESSOR.is_dir()
        or not PREDECESSOR_ZIP.is_file()
        or _sha256(PREDECESSOR_ZIP) != PREDECESSOR_ZIP_SHA256
    ):
        raise EventEdgePackageError("frozen numeric predecessor ZIP differs")
    manifest = json.loads(
        (PREDECESSOR / base.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    if manifest.get("files") != base._records(PREDECESSOR, exclude_manifest=True):
        raise EventEdgePackageError("frozen predecessor exact set differs")
    if not READ_RECEIPT.is_file():
        raise EventEdgePackageError("latest mandatory read receipt is missing")
    identities["mandatory read receipt"] = {
        "path": READ_RECEIPT.relative_to(ROOT).as_posix(),
        "size_bytes": READ_RECEIPT.stat().st_size,
        "sha256": _sha256(READ_RECEIPT),
    }
    semantic = _semantic_records(PREDECESSOR)
    identities["frozen predecessor"] = {
        "path": PREDECESSOR_ZIP.relative_to(ROOT).as_posix(),
        "size_bytes": PREDECESSOR_ZIP.stat().st_size,
        "zip_sha256": PREDECESSOR_ZIP_SHA256,
        "manifest_sha256": PREDECESSOR_MANIFEST_SHA256,
        "semantic_file_count": len(semantic),
        "semantic_tree_sha256": base._tree_sha256(semantic),
    }
    return identities


def _replace_exact(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise EventEdgePackageError(f"observer transform anchor missing: {label}")
    return text.replace(old, new, 1)


def _pe_xmr(leaf: str) -> str:
    return (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]\n"
        "                        .u_slice_with_datahub_mc_group"
        ".slice_group_gen[rq_sid]\n"
        "                        .u_slice_wrapper.u_Slice.u_General_Array"
        ".u_GA_PE_Group\n"
        "                        .GA_ROW_PE[rq_row]"
        ".GA_COL_PE[2*rq_slot+1].GA_SFU_PE\n"
        f"                        .u_GA_SFU_PE.{leaf}"
    )


def _eventedge_observer_tail() -> str:
    text = predecessor_builder._sfu_numeric_observer_tail()
    text = text.replace("rq_num", "rq_evt")
    text = text.replace(
        "Requant node0001 guard-only SFU numeric capture-edge observer v1.",
        "Requant node0001 guard-only event-qualified coeff-to-outbuffer observer v1.",
    )
    text = text.replace(
        "REQUANT_GUARD_SFU_NUMERIC_PROBE",
        "REQUANT_GUARD_SFU_EVENTEDGE_PROBE",
    )
    text = text.replace(
        "requant_guard_sfu_numeric_probe",
        "requant_guard_sfu_eventedge_probe",
    )
    text = text.replace(
        "# guard-only SFU numeric capture-edge observer v1",
        "# guard-only event-qualified coeff-to-outbuffer observer v1",
    )
    text = _replace_exact(
        text,
        "    integer rq_evt_mkdir_status;\n",
        """    integer rq_evt_mkdir_status;
    integer rq_evt_coeff_txn [0:1][0:3][0:1];
    integer rq_evt_alu_result_txn [0:1][0:3][0:1];
    integer rq_evt_normal_wr_txn [0:1][0:3][0:1];
    integer rq_evt_normal_rd_txn [0:1][0:3][0:1];
    logic rq_evt_alu1_capture [0:1][0:3][0:1];
    logic rq_evt_alu_result_pending [0:1][0:3][0:1];
    integer rq_evt_alu_result_pending_txn [0:1][0:3][0:1];
""",
        "event counter declarations",
    )
    text = text.replace(
        ".u_GA_SFU_PE.ga_pe_sfu_coeffs_addr;",
        ".u_GA_SFU_PE.ga_pe_sfu_coeff_addr_o;",
    )
    if "ga_pe_sfu_coeffs_addr" in text:
        raise EventEdgePackageError("observer retained the known undriven coeff address")

    input_assign_pattern = re.compile(
        r"""                    assign rq_evt_alu_input_tag.*?
                        \.u_GA_SFU_PE\.u_GA_PE_Inbuffer\.ga_pe_alu_input_tag;
                    assign rq_evt_alu_input0.*?
                        rq_evt_coeff_preprocessed\[rq_sid\]\[rq_row\]\[rq_slot\];
                    assign rq_evt_alu_input1.*?
                        rq_evt_coeff_slope\[rq_sid\]\[rq_row\]\[rq_slot\];
                    assign rq_evt_alu_input2.*?
                        rq_evt_coeff_intercept\[rq_sid\]\[rq_row\]\[rq_slot\];
""",
        flags=re.DOTALL,
    )
    input_replacement = f"""                    assign rq_evt_alu_input_tag[rq_sid][rq_row][rq_slot] = {{
                        {_pe_xmr("u_GA_PE_Inbuffer.alu_input_valid_bit")},
                        {_pe_xmr("u_GA_PE_Inbuffer.alu_input_last_bit")},
                        {_pe_xmr("u_GA_PE_Inbuffer.alu_input_last_index")}
                    }};
                    assign rq_evt_alu_input0[rq_sid][rq_row][rq_slot] =
                        {_pe_xmr("ga_pe_sfu_alu_input_data[0]")};
                    assign rq_evt_alu_input1[rq_sid][rq_row][rq_slot] =
                        {_pe_xmr("ga_pe_sfu_alu_input_data[1]")};
                    assign rq_evt_alu_input2[rq_sid][rq_row][rq_slot] =
                        {_pe_xmr("ga_pe_sfu_alu_input_data[2]")};
                    assign rq_evt_alu1_capture[rq_sid][rq_row][rq_slot] =
                        {_pe_xmr("u_GA_PE_Inbuffer.alu_pipeline0_valid_bit")} &&
                        {_pe_xmr("ga_pe_alu_pipeline1_enable")};
"""
    text, count = input_assign_pattern.subn(input_replacement, text, count=1)
    if count != 1:
        raise EventEdgePackageError("actual ALU input/tag transform did not match once")

    init_anchor = """            end
        end
        if (rq_evt_probe_enabled) begin
"""
    init_replacement = """            end
            for (int row = 0; row < 4; row++)
                for (int slot = 0; slot < 2; slot++) begin
                    rq_evt_coeff_txn[sid][row][slot] = 0;
                    rq_evt_alu_result_txn[sid][row][slot] = 0;
                    rq_evt_normal_wr_txn[sid][row][slot] = 0;
                    rq_evt_normal_rd_txn[sid][row][slot] = 0;
                    rq_evt_alu_result_pending[sid][row][slot] = 0;
                    rq_evt_alu_result_pending_txn[sid][row][slot] = -1;
                end
        end
        if (rq_evt_probe_enabled) begin
"""
    text = _replace_exact(text, init_anchor, init_replacement, "counter initialization")

    text = _replace_exact(
        text,
        (
            '"GUARD_PATH boundary=MSE4_REQ cycle=%0d slice=%0d ch=%0d '
            "witness=accepted_request req_txn_id=%0d "
        ),
        (
            '"GUARD_PATH boundary=MSE4_REQ event=qualified cycle=%0d '
            "slice=%0d ch=%0d txn_id=%0d witness=accepted_request "
            "req_txn_id=%0d "
        ),
        "MSE4 request event fields",
    )
    text = _replace_exact(
        text,
        "rq_evt_cycle, sid, ch, req_id, metadata_valid,\n",
        "rq_evt_cycle, sid, ch, req_id, req_id, metadata_valid,\n",
        "MSE4 request event id argument",
    )
    text = _replace_exact(
        text,
        (
            '"GUARD_PATH boundary=MSE4_WDATA cycle=%0d slice=%0d ch=%0d '
            'witness=accepted_wdata data=0x%032h"'
        ),
        (
            '"GUARD_PATH boundary=MSE4_WDATA event=qualified cycle=%0d '
            "slice=%0d ch=%0d txn_id=%0d witness=accepted_wdata "
            'data=0x%032h"'
        ),
        "MSE4 write-data event fields",
    )
    text = _replace_exact(
        text,
        (
            "rq_evt_cycle, sid, ch,\n"
            "                            return_obs_mse4_local_wdata_mon[0][sid][ch]"
        ),
        (
            "rq_evt_cycle, sid, ch, wdata_id,\n"
            "                            return_obs_mse4_local_wdata_mon[0][sid][ch]"
        ),
        "MSE4 write-data event id argument",
    )

    sample_start = text.index(
        "                for (int row = 0; row < 4; row++)",
        text.index("always @(posedge u_NDP_Top_new.clk_sg"),
    )
    sample_end = text.index("                $fflush(rq_evt_fd[sid]);", sample_start)
    event_sample = r"""                for (int row = 0; row < 4; row++)
                    for (int slot = 0; slot < 2; slot++) begin
                        rq_evt_alu_result_pending[sid][row][slot] = 0;
                        if (rq_evt_coeff_capture[sid][row][slot]) begin
                            $fdisplay(
                                rq_evt_fd[sid],
                                "GUARD_PATH boundary=SFU_COEFF_SRAM_AT_ALU_CAPTURE event=qualified cycle=%0d slice=%0d pe=%0d%0d txn_id=%0d witness=alu_pipeline0_consumer_capture coeff_addr=0x%0h slope=0x%08h intercept=0x%08h data=0x%08h",
                                rq_evt_cycle, sid, row, 2*slot+1,
                                rq_evt_coeff_txn[sid][row][slot],
                                rq_evt_coeff_addr[sid][row][slot],
                                rq_evt_coeff_slope[sid][row][slot],
                                rq_evt_coeff_intercept[sid][row][slot],
                                rq_evt_coeff_preprocessed[sid][row][slot]
                            );
                            $fdisplay(
                                rq_evt_fd[sid],
                                "GUARD_PATH boundary=SFU_ALU_PIPELINE0_ACCEPT event=qualified cycle=%0d slice=%0d pe=%0d%0d txn_id=%0d witness=valid_and_pipeline0_enable tag=0x%0h data0=0x%08h data1=0x%08h data2=0x%08h data=0x%08h",
                                rq_evt_cycle, sid, row, 2*slot+1,
                                rq_evt_coeff_txn[sid][row][slot],
                                rq_evt_alu_input_tag[sid][row][slot],
                                rq_evt_alu_input0[sid][row][slot],
                                rq_evt_alu_input1[sid][row][slot],
                                rq_evt_alu_input2[sid][row][slot],
                                rq_evt_alu_input0[sid][row][slot]
                            );
                            rq_evt_coeff_txn[sid][row][slot]++;
                        end
                        if (rq_evt_alu1_capture[sid][row][slot]) begin
                            rq_evt_alu_result_pending[sid][row][slot] = 1;
                            rq_evt_alu_result_pending_txn[sid][row][slot] =
                                rq_evt_alu_result_txn[sid][row][slot];
                            rq_evt_alu_result_txn[sid][row][slot]++;
                        end
                        if (rq_evt_normal_wr_hs[sid][row][slot]) begin
                            $fdisplay(
                                rq_evt_fd[sid],
                                "GUARD_PATH boundary=SFU_POSTPROCESS_RESULT_AT_OUTBUFFER_ACCEPT event=qualified cycle=%0d slice=%0d pe=%0d%0d txn_id=%0d witness=normal_mode_write_handshake tag=0x%0h alu_data=0x%08h data=0x%08h",
                                rq_evt_cycle, sid, row, 2*slot+1,
                                rq_evt_normal_wr_txn[sid][row][slot],
                                rq_evt_alu_result_tag[sid][row][slot],
                                rq_evt_alu_result[sid][row][slot],
                                rq_evt_postprocess_result[sid][row][slot]
                            );
                            $fdisplay(
                                rq_evt_fd[sid],
                                "GUARD_PATH boundary=NORMAL_OUTBUFFER_WRITE_COMMIT event=qualified cycle=%0d slice=%0d pe=%0d%0d txn_id=%0d witness=normal_mode_write_handshake tag=0x%0h data=0x%08h",
                                rq_evt_cycle, sid, row, 2*slot+1,
                                rq_evt_normal_wr_txn[sid][row][slot],
                                rq_evt_normal_wr_tag[sid][row][slot],
                                rq_evt_normal_wr_data[sid][row][slot]
                            );
                            rq_evt_normal_wr_txn[sid][row][slot]++;
                        end
                        if (rq_evt_normal_rd_hs[sid][row][slot]) begin
                            $fdisplay(
                                rq_evt_fd[sid],
                                "GUARD_PATH boundary=NORMAL_OUTPORT_ACCEPTED event=qualified cycle=%0d slice=%0d pe=%0d%0d txn_id=%0d witness=normal_mode_read_handshake tag=0x%0h data=0x%08h",
                                rq_evt_cycle, sid, row, 2*slot+1,
                                rq_evt_normal_rd_txn[sid][row][slot],
                                rq_evt_normal_rd_tag[sid][row][slot],
                                rq_evt_normal_rd_data[sid][row][slot]
                            );
                            rq_evt_normal_rd_txn[sid][row][slot]++;
                        end
                    end
"""
    text = text[:sample_start] + event_sample + text[sample_end:]
    final_anchor = "    final begin : rq_evt_probe_final\n"
    negedge_block = r"""    always @(negedge u_NDP_Top_new.clk_sg) begin : rq_evt_result_witness
        if (rq_evt_probe_enabled && u_NDP_Top_new.rst_n_sg)
            for (int sid = 0; sid < 2; sid++)
                for (int row = 0; row < 4; row++)
                    for (int slot = 0; slot < 2; slot++)
                        if (rq_evt_alu_result_pending[sid][row][slot])
                            $fdisplay(
                                rq_evt_fd[sid],
                                "GUARD_PATH boundary=SFU_ALU_RESULT_PRODUCED event=qualified cycle=%0d slice=%0d pe=%0d%0d txn_id=%0d witness=post_nba_negedge_after_pipeline1_accept tag=0x%0h data=0x%08h",
                                rq_evt_cycle, sid, row, 2*slot+1,
                                rq_evt_alu_result_pending_txn[sid][row][slot],
                                rq_evt_alu_result_tag[sid][row][slot],
                                rq_evt_alu_result[sid][row][slot]
                            );
    end

"""
    text = _replace_exact(text, final_anchor, negedge_block + final_anchor, "result witness")
    for forbidden in ("force ", "deposit(", "ga_pe_sfu_coeffs_addr"):
        if forbidden in text:
            raise EventEdgePackageError(f"observer contains forbidden text: {forbidden}")
    return text


def _diagnostic_profile() -> dict[str, Any]:
    return {
        "schema": "requant-node0001-guard-only-sfu-eventedge-runtime-profile-v1",
        "mode": "guard_only",
        "diagnostic_submode": "sfu_eventedge_coeff_to_outbuffer",
        "stage_count": 1,
        "exec_lines": 4,
        "exec_word_count": 7,
        "preload_count": 5,
        "formal_readback_count": 2,
        "expected_write_count": 16,
        "observer_plusarg": "REQUANT_GUARD_SFU_EVENTEDGE_PROBE",
        "observer_log_dir": "requant_guard_sfu_eventedge_probe",
        "observer_tail": OBSERVER_TAIL_NAME,
        "capture_edge_safe": True,
        "event_qualified_transactions": True,
        "checkpoint_expected_counts": {
            "SFU_COEFF_SRAM_AT_ALU_CAPTURE": 64,
            "SFU_ALU_PIPELINE0_ACCEPT": 64,
            "SFU_ALU_RESULT_PRODUCED": 64,
            "SFU_POSTPROCESS_RESULT_AT_OUTBUFFER_ACCEPT": 64,
            "NORMAL_OUTBUFFER_WRITE_COMMIT": 64,
            "NORMAL_OUTPORT_ACCEPTED": 64,
            "MSE4_REQ": 16,
            "MSE4_WDATA": 16,
        },
        "checkpoint_observation_only": [],
        "checkpoint_order": [
            "SFU_COEFF_SRAM_AT_ALU_CAPTURE",
            "SFU_ALU_PIPELINE0_ACCEPT",
            "SFU_ALU_RESULT_PRODUCED",
            "SFU_POSTPROCESS_RESULT_AT_OUTBUFFER_ACCEPT",
            "NORMAL_OUTBUFFER_WRITE_COMMIT",
            "NORMAL_OUTPORT_ACCEPTED",
            "MSE4_WDATA",
        ],
        "last_proven_good": "SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT",
        "level_qualifier_count_used_as_transaction_count": False,
        "raw_qualified_parseable_xz_duplicate_columns_required": True,
        "four_level_routing": [
            "selected coefficient SRAM output",
            "ALU pipeline0 capture and ALU result",
            "postprocess and normal outbuffer write",
            "normal outport, MSE4 and formal D",
        ],
        "shared_native_silu_control_evidence": {
            "rule_id": (
                "CDA-REQUANT-NATIVE-SILU-CONTROL-V1-DYNAMIC-EVIDENCE-001"
            ),
            "report_sha256": CONTROL_REPORT_SHA256,
            "common_sfu_normal_outbuffer_path_operational": True,
            "excludes_universal_common_sfu_or_normal_outbuffer_failure": True,
            "does_not_prove_requant_specific_configuration_consumption": True,
        },
    }


def _run_script() -> str:
    script = base._run_script()
    script = _replace_exact(
        script,
        f'install_name="{base.INSTALL_NAME}"\n',
        f'install_name="{INSTALL_NAME}"\n',
        "install namespace",
    )
    script = script.replace(
        "+REQUANT_ATOMIC_PROBE", "+REQUANT_GUARD_SFU_EVENTEDGE_PROBE"
    )
    script = _replace_exact(
        script,
        f'install_name="{INSTALL_NAME}"\n',
        (
            f'install_name="{INSTALL_NAME}"\n'
            f'tb_relative_path="{TB_TARGET_RELATIVE_PATH}"\n'
        ),
        "TB target variable",
    )
    script = script.replace(
        '--ndp-root "${ndp_root}" --evidence-root "${evidence_root}" >/dev/null',
        (
            '--ndp-root "${ndp_root}" --evidence-root "${evidence_root}" '
            '--tb-relative-path "${tb_relative_path}" >/dev/null'
        ),
    )
    script = _replace_exact(
        script,
        '--evidence-root "${evidence_root}" >/dev/null || exit 5\nprobe_installed=1',
        (
            '--evidence-root "${evidence_root}" '
            '--tb-relative-path "${tb_relative_path}" >/dev/null || exit 5\n'
            "probe_installed=1"
        ),
        "probe install explicit target",
    )
    script = _replace_exact(
        script,
        (
            '--evidence-root "${evidence_root}"   '
            '--output "${evidence_root}/tb_probe_precompile_receipt.json" '
            ">/dev/null || exit 5"
        ),
        (
            '--evidence-root "${evidence_root}"   '
            '--tb-relative-path "${tb_relative_path}"   '
            '--output "${evidence_root}/tb_probe_precompile_receipt.json" '
            ">/dev/null || exit 5"
        ),
        "probe verify explicit target",
    )
    return script


def _copy_predecessor_frozen_files(package: Path) -> None:
    for source in sorted(path for path in PREDECESSOR.rglob("*") if path.is_file()):
        relative = source.relative_to(PREDECESSOR).as_posix()
        if relative in MUTABLE_PREDECESSOR_PATHS:
            continue
        _copy(source, package / relative)


def _build_tree(package: Path, sources: dict[str, Any]) -> dict[str, Any]:
    package.mkdir(parents=True)
    _copy_predecessor_frozen_files(package)
    _copy(
        ROOT / "tools/requant_atomic_server_runtime.py",
        package / "package_tools/requant_atomic_server_runtime_base.py",
    )
    _copy(
        ROOT / "tools/requant_guard_eventedge_server_runtime.py",
        package / "package_tools/requant_atomic_server_runtime.py",
    )
    _copy(
        ROOT / "tools/requant_node0001_server_runtime.py",
        package / "package_tools/requant_node0001_server_runtime.py",
    )
    base._write_lf(
        package / "tb_probe" / OBSERVER_TAIL_NAME,
        _eventedge_observer_tail().lstrip(),
    )
    _write_json(package / "validation/diagnostic_profile.json", _diagnostic_profile())
    _copy(READ_RECEIPT, package / "validation/mandatory_read_receipt.json")

    sca_path = package / "workload/runtime/sca_cfg.json"
    sca = json.loads(
        (PREDECESSOR / "workload/runtime/sca_cfg.json").read_text(encoding="utf-8")
    )
    for value in sca.values():
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            value["path"] = value["path"].replace(PREDECESSOR_NAME, INSTALL_NAME)
    _write_json(sca_path, sca)

    new_semantic = _semantic_records(package)
    old_semantic = _semantic_records(PREDECESSOR)
    if new_semantic != old_semantic:
        raise EventEdgePackageError("frozen semantic path/size/SHA set changed")
    semantic_tree = base._tree_sha256(old_semantic)
    _write_json(
        package / "validation/semantic_freeze_numeric_v1_to_eventedge_v1.json",
        {
            "schema": "requant-guard-eventedge-semantic-freeze-v1",
            "status": "pass",
            "semantic_change": False,
            "source_install_name": PREDECESSOR_NAME,
            "target_install_name": INSTALL_NAME,
            "frozen_file_count": len(old_semantic),
            "source_tree_sha256": semantic_tree,
            "target_tree_sha256": semantic_tree,
            "exact_path_size_sha_equal": True,
            "files": old_semantic,
            "sca_change_boundary": (
                "only installed namespace text in sca_cfg.json paths changed; "
                "addresses, Repeat_Num, Exec_Length and SCA_D are frozen"
            ),
        },
    )
    _write_json(
        package / "validation/guard_only_provenance.json",
        {
            "schema": "requant-node0001-guard-only-sfu-eventedge-provenance-v1",
            "status": "frozen_guard_semantics_reused_exactly",
            "direct_predecessor": {
                "install_name": PREDECESSOR_NAME,
                "package_zip_sha256": PREDECESSOR_ZIP_SHA256,
                "return_analysis": AUTHORITY.relative_to(ROOT).as_posix(),
                "return_analysis_sha256": AUTHORITY_SHA256,
                "last_proven_good": (
                    "SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT"
                ),
                "first_unobserved": (
                    "SELECTED_COEFF_SRAM_OUTPUT_TO_ALU_CAPTURE_AND_RESULT"
                ),
            },
            "semantic_change": False,
            "diagnostic_scope_change": (
                "event-qualified selected coefficient SRAM output through ALU, "
                "postprocess and normal outbuffer; all earlier wide probes removed"
            ),
            "known_predecessor_probe_repairs": [
                "ga_pe_sfu_coeffs_addr was undriven; use ga_pe_sfu_coeff_addr_o",
                "ALU tag is captured from the pipeline5-selected input tag",
                "ALU result is sampled at negedge after a real pipeline1 accept",
                "level qualifiers never count as transactions",
            ],
            "shared_native_silu_control_evidence": {
                "report": CONTROL_REPORT.relative_to(ROOT).as_posix(),
                "report_sha256": CONTROL_REPORT_SHA256,
                "rule_id": (
                    "CDA-REQUANT-NATIVE-SILU-CONTROL-V1-DYNAMIC-EVIDENCE-001"
                ),
                "common_sfu_normal_outbuffer_path_operational": True,
                "control_d_coverage_failure_is_independent": True,
                "proves_requant_specific_configuration": False,
            },
            "source_identities": sources,
            "round_only_enabled": False,
            "alias_lifetime_enabled": False,
            "full_e4_enabled": False,
            "functional_rtl_modified": False,
            "tb_driver_modified": False,
        },
    )
    base._write_lf(package / "PREPARE_AND_RUN.sh", _run_script())
    base._write_lf(
        package / "README.md",
        (
            "# Requant node0001 guard-only SFU event-edge diagnostic v1\n\n"
            "Run one command from this extracted package directory:\n\n"
            "```bash\n"
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
            "```\n\n"
            "This read-only FIRST_DYNAMIC diagnostic freezes the previous guard "
            "workload and observes only qualified coefficient/ALU/outbuffer "
            "events. It is not node0001 E4/E5 and contains no rtl/ files.\n"
        ),
    )
    records = base._records(package, exclude_manifest=True)
    manifest = {
        "schema": "requant-node0001-guard-only-sfu-eventedge-stockrtl-package-v1",
        "install_name": INSTALL_NAME,
        "run_kind": "FIRST_DYNAMIC_DIAGNOSTIC",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "functional_rtl_file_count": 0,
        "tb_or_rtl_driver_modification": False,
        "observer_mode": "transactional_read_only_non_rtl_tail",
        "observer_capture_mode": "event_qualified_consumer_capture_and_handshake",
        "tb_probe_target_relative_path": TB_TARGET_RELATIVE_PATH,
        "enabled_atomic_followup": "guard-only",
        "disabled_atomic_followups": ["round-only", "alias-lifetime", "full-E4"],
        "rule_ids": [
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
            "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
            "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
            "CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
            "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
            "CDA-REQUANT-GUARD-CHECKPOINT-ROUTING-001",
            "CDA-REQUANT-GUARD-DIAGNOSTIC-EVIDENCE-BOUNDARY-001",
            "CDA-REQUANT-NATIVE-SILU-CONTROL-V1-DYNAMIC-EVIDENCE-001",
        ],
        "source_identities": sources,
        "generation_tool": {
            "path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
            "sha256": _sha256(Path(__file__).resolve()),
        },
        "expected_return_exact_set_policy": "allowlist-only fail-closed",
        "return_size_budget_bytes": 6 * 1024 * 1024,
        "payload_tree_sha256": base._tree_sha256(records),
        "files": records,
    }
    _write_json(package / base.MANIFEST_NAME, manifest)
    preflight = base.preflight_package(package, INSTALL_NAME)
    return {
        "manifest": manifest,
        "preflight": preflight,
        "semantic_tree_sha256": semantic_tree,
    }


def _fresh_extract_selfcheck(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="rq-eventedge-selfcheck-") as temporary:
        root = Path(temporary)
        extract_root = root / "extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        fresh = extract_root / INSTALL_NAME
        before = base._records(fresh)
        before_tree = base._tree_sha256(before)
        ndp_root = root / "NDP_copy_mock"
        evidence = root / "evidence"
        ndp_root.mkdir()
        evidence.mkdir()
        observer = ndp_root / TB_TARGET_RELATIVE_PATH
        _copy(ROOT / "NDP_copy01/native_return_observer.svh", observer)
        preimage = observer.read_bytes()
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        runtime = fresh / "package_tools/requant_atomic_server_runtime.py"
        common = fresh / "package_tools/requant_node0001_server_runtime.py"

        def run(tool: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
            completed = subprocess.run(
                [sys.executable, str(tool), *arguments],
                cwd=fresh,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                raise EventEdgePackageError(
                    "fresh-extract packaged entry failed: "
                    f"{arguments[0]}: {completed.stderr.strip()}"
                )
            return completed

        preflight_path = root / "package_preflight.json"
        run(
            runtime,
            "preflight-package",
            "--package-root",
            str(fresh),
            "--install-name",
            INSTALL_NAME,
            "--output",
            str(preflight_path),
        )
        run(
            common,
            "install-probe",
            "--ndp-root",
            str(ndp_root),
            "--package-root",
            str(fresh),
            "--evidence-root",
            str(evidence),
            "--tb-relative-path",
            TB_TARGET_RELATIVE_PATH,
        )
        verify_path = evidence / "tb_probe_precompile_receipt.json"
        run(
            common,
            "verify-probe-installed",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
            "--tb-relative-path",
            TB_TARGET_RELATIVE_PATH,
            "--output",
            str(verify_path),
        )
        run(
            common,
            "restore-probe",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
            "--tb-relative-path",
            TB_TARGET_RELATIVE_PATH,
        )
        if observer.read_bytes() != preimage:
            raise EventEdgePackageError("fresh-extract observer restore differs")
        after = base._records(fresh)
        if before != after:
            raise EventEdgePackageError("fresh-extract package tree changed")
        forbidden = [
            relative
            for relative in after
            if "__pycache__" in {part.lower() for part in relative.split("/")}
            or Path(relative).suffix.lower() in {".pyc", ".pyo"}
        ]
        if forbidden:
            raise EventEdgePackageError(f"Python bytecode appeared: {forbidden}")
        install_receipt = json.loads(
            (evidence / "tb_probe_install_receipt.json").read_text(encoding="utf-8")
        )
        verify_receipt = json.loads(verify_path.read_text(encoding="utf-8"))
        isolation = install_receipt["target_directory_isolation"]
        if (
            isolation.get("command_argument_was_explicit") is not True
            or isolation.get("candidate_write_path_count") != 1
            or isolation.get("basename_find_glob_rglob_used") is not False
        ):
            raise EventEdgePackageError("TB target directory isolation receipt failed")
        tail = (
            fresh / f"tb_probe/{OBSERVER_TAIL_NAME}"
        ).read_text(encoding="utf-8")
        if (
            "event=qualified" not in tail
            or "ga_pe_sfu_coeff_addr_o" not in tail
            or "ga_pe_sfu_coeffs_addr" in tail
        ):
            raise EventEdgePackageError("event-qualified observer static gate failed")
        return {
            "schema": "requant-guard-eventedge-fresh-extract-selfcheck-v1",
            "status": "pass",
            "fresh_zip_extraction": True,
            "actual_packaged_runtime_entry": True,
            "package_tree_sha256_before": before_tree,
            "package_tree_sha256_after": base._tree_sha256(after),
            "package_exact_tree_unchanged": True,
            "python_dont_write_bytecode": True,
            "pyc_or_pycache_created": False,
            "observer_installed_verified_restored": True,
            "observer_restored_byte_exact": True,
            "tb_target_directory_isolation": isolation,
            "xmr_elaboration_gate": verify_receipt["xmr_elaboration_gate"],
            "event_qualification_static_gate": {
                "qualified_marker_present": True,
                "true_coeff_address_signal_present": True,
                "undriven_coeff_address_signal_absent": True,
                "force_or_deposit_absent": (
                    "force " not in tail and "deposit(" not in tail
                ),
            },
        }


def build_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = output.resolve()
    if output.name != INSTALL_NAME:
        raise EventEdgePackageError(f"output directory must be {INSTALL_NAME}")
    previous_install_name = base.INSTALL_NAME
    base.INSTALL_NAME = INSTALL_NAME
    try:
        base._fresh_final_targets(output)
        sources = _verify_sources()
        with tempfile.TemporaryDirectory(
            prefix="rq-eventedge-a-"
        ) as left_parent, tempfile.TemporaryDirectory(
            prefix="rq-eventedge-b-"
        ) as right_parent:
            left = Path(left_parent) / INSTALL_NAME
            right = Path(right_parent) / INSTALL_NAME
            left_report = _build_tree(left, sources)
            _build_tree(right, sources)
            left_zip, left_sha = base._zip_tree(left)
            right_zip, right_sha = base._zip_tree(right)
            if (
                left_sha != right_sha
                or left_zip.read_bytes() != right_zip.read_bytes()
                or base._records(left) != base._records(right)
            ):
                raise EventEdgePackageError("two fresh package builds differ")
            shutil.copytree(right, output)
            shutil.copyfile(right_zip, output.with_suffix(".zip"))
            shutil.copyfile(
                right_zip.with_suffix(".zip.sha256"),
                output.with_suffix(".zip.sha256"),
            )
        validation = base._validate_zip(output)
        selfcheck = _fresh_extract_selfcheck(output)
        report = {
            "schema": "requant-guard-eventedge-package-validation-v1",
            "package": output.as_posix(),
            "zip": output.with_suffix(".zip").as_posix(),
            "zip_size_bytes": output.with_suffix(".zip").stat().st_size,
            "zip_sha256": validation["zip_sha256"],
            "sidecar": output.with_suffix(".zip.sha256").as_posix(),
            "payload_tree_sha256": left_report["manifest"]["payload_tree_sha256"],
            "frozen_semantic_tree_sha256": left_report["semantic_tree_sha256"],
            "frozen_semantic_file_count": len(FROZEN_SEMANTIC_PATHS),
            "preflight": validation,
            "fresh_extract_selfcheck": selfcheck,
            "deterministic_package_build_count": 2,
            "deterministic_zip_byte_identical": True,
            "release_gate": {
                "candidate_release": False,
                "counts_as_node0001_e4": False,
                "counts_as_node0001_e5": False,
                "remaining_blockers": [
                    "B_REQUANT_GUARD_DYNAMIC_DATA_PATH",
                    "B_REQUANT_SERVER_E4_E5",
                ],
            },
            "server_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
            "expected_return": f"{INSTALL_NAME}_return.zip",
            "expected_return_sidecar": f"{INSTALL_NAME}_return.zip.sha256",
        }
        receipt_path = output.with_name(f"{INSTALL_NAME}_validation.json")
        _write_json(receipt_path, report)
        report["validation_receipt"] = receipt_path.as_posix()
        return report
    finally:
        base.INSTALL_NAME = previous_install_name


def validate_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    previous_install_name = base.INSTALL_NAME
    base.INSTALL_NAME = INSTALL_NAME
    try:
        validation = base._validate_zip(output.resolve())
        validation["fresh_extract_selfcheck"] = _fresh_extract_selfcheck(
            output.resolve()
        )
        return validation
    finally:
        base.INSTALL_NAME = previous_install_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        report = (
            validate_package(args.output)
            if args.validate_only
            else build_package(args.output)
        )
    except Exception as exc:
        print(f"Requant guard event-edge package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
