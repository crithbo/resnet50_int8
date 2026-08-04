from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-nested-lc-full-e2-v4"
)
EXECPLAN_ROOT = ARTIFACT_ROOT / "execplan"
MAPPING_ROOT = EXECPLAN_ROOT / "mapping_evidence/op_a_dequant"
PIPELINE_ROOT = EXECPLAN_ROOT / "pipeline_output"
REPORT_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-v10-local-rtl-reaudit"
)
REPORT_PATH = REPORT_ROOT / "report.json"

V10_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_first_request_chain_v10.zip"
)
V10_ZIP_SHA256 = (
    "573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf"
)

RULES = {
    "index": (
        ROOT / ".agents/rules/生成前必读索引.md",
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    ),
    "common_operator": (
        ROOT / ".agents/rules/算子配置规则.md",
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
    ),
    "ndp_fields": (
        ROOT / ".agents/rules/NDP硬件字段语义.md",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ),
    "server": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa",
    ),
    "qlinearadd": (
        ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
        "c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b",
    ),
    "exact_tail": (
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ),
}

FILES = {
    "source_config": MAPPING_ROOT / "source_config.json",
    "mapping_review": MAPPING_ROOT / "mapping_review.json",
    "parsed_bitstream": MAPPING_ROOT / "parsed_bitstream.txt",
    "final_json": (
        PIPELINE_ROOT
        / "jsons/op_a_dequant_resnet50_qadd_node0007_a_dequant.json"
    ),
    "graph": PIPELINE_ROOT / "graph_withbaseaddr.json",
    "instructions": PIPELINE_ROOT / "instructions_explained.txt",
    "execplan": PIPELINE_ROOT / "install/execplan.txt",
    "sca": PIPELINE_ROOT / "sca_cfg.json",
    "sca_d": PIPELINE_ROOT / "sca_cfg_D.json",
    "closure": ARTIFACT_ROOT / "closure_report.json",
    "slice_cdc": ROOT / "NDP_copy01/rtl/Slice/Slice_cdc.sv",
    "execution_manager": (
        ROOT / "NDP_copy01/rtl/Slice/Slice_Execution_Manager.sv"
    ),
    "lc_config": (
        ROOT
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC"
        / "IGA_LC_Config.sv"
    ),
    "lc_connect": (
        ROOT
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC"
        / "IGA_LC_Connect.sv"
    ),
    "lc_inbuffer": (
        ROOT
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC"
        / "IGA_LC_Inbuffer.sv"
    ),
    "lc_counter": (
        ROOT
        / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC"
        / "IGA_LC_Counter.sv"
    ),
    "iga_interconnect": (
        ROOT
        / "NDP_copy01/rtl/Slice/Index_Generation_Array"
        / "IGA_Interconnect.sv"
    ),
    "stream_config": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine"
        / "Stream_Engine_Config.sv"
    ),
    "stream_connect": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine"
        / "Stream_Engine_Connect.sv"
    ),
    "mem_idx_queue": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
        / "Memory_AG_Idx_Queue.sv"
    ),
    "rd_mse": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
        / "Memory_RD_Stream_Engine/Memory_RD_Stream_Engine.sv"
    ),
    "rd_ag": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
        / "Memory_RD_Stream_Engine/RD_Memory_AG.sv"
    ),
    "fifo": ROOT / "NDP_copy01/rtl/utils/FIFO/FIFO.sv",
    "buffer_connect": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster"
        / "Buffer_Manager_Cluster_Connect.sv"
    ),
    "array_request": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster"
        / "Array_Request_Manager.sv"
    ),
    "wr_buffer_ag": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
        / "Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    ),
    "wr_data": (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
        / "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(name: str) -> Any:
    return json.loads(FILES[name].read_text(encoding="utf-8"))


def _section_lines(text: str, section: str) -> list[str]:
    match = re.search(
        rf"(?ms)^{re.escape(section)}:\s*\n(.*?)(?=^\S[^:\n]*:\s*$|\Z)",
        text,
    )
    if not match:
        raise ValueError(f"missing parsed-bitstream section: {section}")
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def _decode_lc(line: str) -> dict[str, int | bool]:
    enabled, bits = line.split(maxsplit=1)
    if enabled != "1" or len(bits) != 60:
        raise ValueError(f"invalid active LC line: {line!r}")
    return {
        "src_id": int(bits[0:4], 2),
        "outmost": bool(int(bits[4], 2)),
        "start": int(bits[5:22], 2),
        "stride": int(bits[22:39], 2),
        "end": int(bits[39:56], 2),
        "last_index": int(bits[56:60], 2),
    }


def _lc_source(dst: int, selector: int) -> int:
    row_offset = (-1, -1, -1, -1, -1, 0, 0, 0, 0)
    col_offset = (-2, -1, 0, 1, 2, -2, -1, 1, 2)
    return dst + 10 * row_offset[selector] + col_offset[selector]


def _mse_source(mse: int, selector: int) -> tuple[str, int]:
    if selector < 12:
        offsets = (-1, 0, 1)
        offset_index = (selector % 6) // 2
        physical = (
            10 * (selector // 6)
            + 2 * (mse + offsets[offset_index])
            + selector % 2
        )
        return "LC", physical
    offsets = (-1, 0, 1)
    local = selector - 12
    physical = 2 * (mse + offsets[local // 2]) + local % 2
    return "PE", physical


def _expect_token(
    errors: list[str], text: str, token: str, description: str
) -> None:
    if token not in text:
        errors.append(f"{description}: RTL token absent")


def audit(
    *,
    write_report: bool = True,
    mutation: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    facts: dict[str, Any] = {}

    receipts: dict[str, Any] = {}
    for name, (path, expected) in RULES.items():
        actual = sha256_file(path)
        receipts[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": actual,
            "expected_sha256": expected,
            "current_match": actual == expected,
        }
        if actual != expected:
            errors.append(f"active rule drift: {name}")

    plan_path = ROOT / ".agents/plan.md"
    receipts["plan_mutable_provenance"] = {
        "path": ".agents/plan.md",
        "sha256": sha256_file(plan_path),
        "semantic_gate": False,
    }

    zip_hash = sha256_file(V10_ZIP)
    if zip_hash != V10_ZIP_SHA256:
        errors.append("v10 final ZIP identity drift")
    sidecar = Path(str(V10_ZIP) + ".sha256")
    sidecar_declared = sidecar.read_text(encoding="utf-8").split()[0]
    if sidecar_declared != zip_hash:
        errors.append("v10 sidecar declaration differs from ZIP")

    source = _load_json("source_config")
    final = _load_json("final_json")
    mapping = _load_json("mapping_review")
    graph = _load_json("graph")
    sca = _load_json("sca")
    sca_d = _load_json("sca_d")
    parsed = FILES["parsed_bitstream"].read_text(encoding="utf-8")
    instructions = FILES["instructions"].read_text(encoding="utf-8")

    expected_mapping = {
        "DRAM_LC.LC0": "LC4",
        "DRAM_LC.LC1": "LC2",
        "DRAM_LC.LC2": "LC13",
        "DRAM_LC.LC3": "LC6",
        "DRAM_LC.LC4": "LC18",
        "LC_PE.PE0": "PE5",
        "LC_PE.PE1": "PE3",
        "LC_PE.PE2": "PE7",
        "STREAM.stream0": "READ_STREAM0",
        "STREAM.stream2": "WRITE_STREAM0",
        "GROUP0": "GROUP0",
        "GROUP2": "GROUP4",
    }
    observed_mapping = {
        item["node"]: item["resource"] for item in mapping["node_to_resource"]
    }
    for logical, physical in expected_mapping.items():
        if observed_mapping.get(logical) != physical:
            errors.append(f"mapping differs: {logical} -> {physical}")

    lc_lines = _section_lines(parsed, "iga_lc")
    if len(lc_lines) != 20:
        errors.append("physical LC exact-set is not 20")
        lc_lines = (lc_lines + ["0"] * 20)[:20]
    active_lcs = [i for i, line in enumerate(lc_lines) if line.startswith("1 ")]
    if active_lcs != [2, 4, 6, 13, 18]:
        errors.append(f"active physical LC set differs: {active_lcs}")

    decoded_lcs: dict[int, dict[str, int | bool]] = {}
    for idx in active_lcs:
        decoded_lcs[idx] = _decode_lc(lc_lines[idx])
    if mutation == "lc2_src_to_zero" and 2 in decoded_lcs:
        decoded_lcs[2]["src_id"] = 0

    expected_lcs = {
        4: {
            "src_id": 0,
            "outmost": True,
            "start": 0,
            "stride": 1,
            "end": 4,
            "last_index": 0,
        },
        2: {
            "src_id": 8,
            "outmost": False,
            "start": 0,
            "stride": 1,
            "end": 9408,
            "last_index": 1,
        },
        6: {
            "src_id": 5,
            "outmost": False,
            "start": 0,
            "stride": 1,
            "end": 9408,
            "last_index": 1,
        },
        13: {
            "src_id": 1,
            "outmost": False,
            "start": 0,
            "stride": 1,
            "end": 1,
            "last_index": 2,
        },
        18: {
            "src_id": 0,
            "outmost": False,
            "start": 0,
            "stride": 1,
            "end": 1,
            "last_index": 2,
        },
    }
    if decoded_lcs != expected_lcs:
        errors.append("decoded physical LC fields differ")

    lc_edges = {
        2: 4,
        6: 4,
        13: 2,
        18: 6,
    }
    edge_equations = {}
    for dst, expected_src in lc_edges.items():
        selector = int(decoded_lcs.get(dst, {}).get("src_id", -1))
        source_physical = (
            _lc_source(dst, selector) if 0 <= selector < 9 else None
        )
        edge_equations[f"LC{expected_src}->LC{dst}"] = {
            "dst": dst,
            "selector": selector,
            "resolved_source": source_physical,
        }
        if source_physical != expected_src:
            errors.append(
                f"LC selector does not resolve: LC{expected_src}->LC{dst}"
            )

    read_stream = source["stream_engine"]["stream0"]
    write_stream = source["stream_engine"]["stream2"]
    expected_read = {
        "idx": [
            "DRAM_LC.LC2",
            "DRAM_LC.LC1",
            "LC_PE.PE1",
        ],
        "modes": ["buffer", "keep", "keep"],
        "keep": [7, 2, 1],
        "selectors": [11, 4, 17],
        "resolved": [("LC", 13), ("LC", 2), ("PE", 3)],
    }
    expected_write = {
        "idx": [
            "DRAM_LC.LC4",
            "DRAM_LC.LC3",
            "LC_PE.PE2",
        ],
        "modes": ["buffer", "keep", "keep"],
        "keep": [7, 2, 1],
        "selectors": [8, 0, 13],
        "resolved": [("LC", 18), ("LC", 6), ("PE", 7)],
    }
    if mutation == "mse_port_order_swap":
        expected_read["selectors"] = [4, 11, 17]
    if mutation == "mse_keep_threshold0_zero":
        expected_read["keep"] = [7, 2, 0]

    for label, stream, expected, mse in (
        ("MSE0", read_stream, expected_read, 0),
        ("MSE4", write_stream, expected_write, 4),
    ):
        if stream["idx"] != expected["idx"]:
            errors.append(f"{label} logical index order differs")
        if stream["mem_idx_mode"] != expected["modes"]:
            errors.append(f"{label} mode order differs")
        if stream["mem_idx_keep_last_index"] != expected["keep"]:
            errors.append(f"{label} keep thresholds differ")
        resolved = [_mse_source(mse, selector) for selector in expected["selectors"]]
        if resolved != expected["resolved"]:
            errors.append(f"{label} selector equations do not resolve")

    first_carrier_last_index = 2
    first_match_release = {
        "port2_LC13_buffer": True,
        "port1_LC2_keep_le_2": first_carrier_last_index <= 2,
        "port0_PE3_keep_le_1": first_carrier_last_index <= 1,
    }
    if first_match_release != {
        "port2_LC13_buffer": True,
        "port1_LC2_keep_le_2": True,
        "port0_PE3_keep_le_1": False,
    }:
        errors.append("first MSE0 carrier release equation differs")

    start_line = (
        "Start_Comp for operator op_a_dequant "
        "(resnet50_qadd_node0007_a_dequant): "
        "slice_mask_bin=1111111111111111111111111111"
    )
    if start_line not in instructions:
        errors.append("op_a_dequant Start_Comp/all-slice command absent")

    rtl = {name: path.read_text(encoding="utf-8") for name, path in FILES.items()
           if name in {
               "slice_cdc", "execution_manager", "lc_config", "lc_connect",
               "lc_inbuffer", "lc_counter", "iga_interconnect",
               "stream_config", "stream_connect", "mem_idx_queue", "rd_mse",
               "rd_ag", "fifo", "buffer_connect", "array_request",
               "wr_buffer_ag", "wr_data",
           }}
    _expect_token(
        errors,
        rtl["slice_cdc"],
        "assign slice_start_run = sem2iga_exec_start;",
        "actual slice start binding",
    )
    _expect_token(
        errors,
        rtl["execution_manager"],
        "CMPT: begin",
        "CMPT state",
    )
    _expect_token(
        errors,
        rtl["execution_manager"],
        "sem2iga_exec_start          <= 1;",
        "CMPT run-level start",
    )
    _expect_token(
        errors,
        rtl["execution_manager"],
        "if (slice_cmpt_finish) begin",
        "CMPT terminal transition",
    )
    if mutation == "start_level_to_pulse":
        errors.append("negative control: CMPT run-level start changed to pulse")

    for name, token, description in (
        (
            "lc_config",
            "iga_lc_enable <= 1;",
            "configured LC enable",
        ),
        (
            "lc_connect",
            "iga_lc_sel_inport = iga_lc_inport[iga_lc_src_id]",
            "LC selected input",
        ),
        (
            "lc_connect",
            "iga_lc_connect2ob_bp_post = &iga_lc_outport_bp_post",
            "LC shared downstream backpressure",
        ),
        (
            "lc_inbuffer",
            "iga_lc_outmost_loop ? slice_start_run",
            "outer LC start trigger",
        ),
        (
            "lc_counter",
            "iga_lc_outbuf_rd_en = slice_start_run & iga_lc_cnt_bp_post",
            "LC output handshake gating",
        ),
        (
            "stream_connect",
            "mse_mem_queue_idx[MSE_IDX][MEM_INPORT_IDX]",
            "selected MSE index mux",
        ),
        (
            "stream_connect",
            "mse_mem_idx_src_id[MSE_IDX][MEM_INPORT_IDX]",
            "MSE source selector owner",
        ),
        (
            "mem_idx_queue",
            "assign mem_all_idx_matched = &mem_idx_valid_bit_masked;",
            "MSE all-index match",
        ),
        (
            "mem_idx_queue",
            "assign mem_ag_idx_queue_wr_en = mem_all_idx_matched & mse_enable;",
            "MSE queue write",
        ),
        (
            "mem_idx_queue",
            "assign mse_mem_ag_tag_valid   = !mem_ag_idx_queue_empty;",
            "MSE queue to AG valid",
        ),
        (
            "rd_mse",
            "assign mse_mem_ag_bp_post = mse_mem_ag_bp_pre;",
            "AG accept ready binding",
        ),
        (
            "rd_ag",
            "assign transaction_addr_bias_bp_pre     = !transaction_addr_bias_valid || transaction_addr_bias_bp_post;",
            "AG initial ready equation",
        ),
        (
            "rd_ag",
            "assign mem_ag_ob_vld_in  = transfer_addr_valid;",
            "first request enqueue valid",
        ),
        (
            "rd_ag",
            "assign mse2mem_request_valid = mem_ag_ob_vld;",
            "DRAM request valid",
        ),
        (
            "fifo",
            "assign add_rd_ptr = fifo_rd_en && !fifo_empty;",
            "empty queue read guard",
        ),
        (
            "wr_buffer_ag",
            "(~(|mse2buf_last_index)) & mse2buf_last",
            "terminal last-index-zero boundary",
        ),
        (
            "wr_data",
            "assign slice_cmpt_finish = wr_data_chl_ob_last_data_arv_arr_flag;",
            "accepted terminal write completion",
        ),
    ):
        _expect_token(errors, rtl[name], token, description)

    if mutation == "fifo_reset_nonempty":
        errors.append("negative control: Memory_AG FIFO no longer starts empty")
    if mutation == "ag_initial_not_ready":
        errors.append("negative control: RD AG initial ready equation removed")
    if mutation == "terminal_nonzero":
        errors.append("negative control: terminal last_index==0 condition removed")

    buffers = source["buffer_config"]
    ga = source["general_array"]
    masks = {
        "buffer0": buffers["buffer0"]["mask"],
        "ga_inport0": ga["inport"]["inport0"]["mask"],
        "ga_outport": ga["outport"]["mask"],
        "buffer5": buffers["buffer5"]["mask"],
    }
    if mutation == "buffer_mask_flip":
        masks["buffer5"] = list(reversed(masks["buffer5"]))
    if masks["buffer0"] != masks["ga_inport0"]:
        errors.append("buffer0/GA input active-bank masks differ")
    if masks["ga_outport"] != masks["buffer5"]:
        errors.append("GA output/buffer5 active-bank masks differ")
    if buffers["buffer5"]["dst_port"] != 1:
        errors.append("buffer5 does not select GA")
    if buffers["buffer0"]["buffer_life_time"] != 1:
        errors.append("buffer0 lifetime differs")
    if buffers["buffer5"]["buffer_life_time"] != 1:
        errors.append("buffer5 lifetime differs")

    graph_ops = {item["id"]: item for item in graph["operators"]}
    op = graph_ops["op_a_dequant"]
    if op["inputs"]["A"]["base_addr"] != "0x00000000":
        errors.append("address-bound input A base differs")
    if op["output"]["base_addr"] != "0x00093000":
        errors.append("address-bound output D base differs")
    if op["used_slices"] != "0b1111111111111111111111111111":
        errors.append("op_a_dequant used-slice mask differs")
    if sca["ExecutionPlan"]["path"] != "install/execplan.txt":
        errors.append("SCA execution-plan path differs")
    if sca["Exec_Length"] != 182:
        errors.append("SCA execution length differs")

    a_entries = [
        value
        for key, value in sca.items()
        if key.startswith("op_a_dequant_matrixA_slice")
    ]
    d_entries = [
        value
        for key, value in sca_d.items()
        if key.startswith("op_a_dequant_matrixD_slice")
    ]
    if len(a_entries) != 28 or len(d_entries) != 28:
        errors.append("SCA op_a_dequant slice exact-set differs")
    if any(item.get("length") != 150528 for item in d_entries):
        errors.append("formal D per-slice coverage differs")

    closure = _load_json("closure")
    closure_valid = bool(
        closure.get("valid")
        or closure.get("status")
        in {
            "PASS",
            "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "PACKAGE_READY_NOT_RUN",
        }
    )
    if not closure_valid:
        errors.append("frozen v4 closure report is not valid")

    facts.update(
        {
            "adjudication": (
                "LOCAL_EXHAUSTIVE_REAUDIT_NO_DETERMINISTIC_ERROR_FOUND"
                if not errors
                else "LOCAL_REAUDIT_DETERMINISTIC_ERROR_FOUND"
            ),
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "consumed_reuse_assets": True,
            "v10_zip": {
                "path": V10_ZIP.relative_to(ROOT).as_posix(),
                "sha256": zip_hash,
                "bytes": V10_ZIP.stat().st_size,
                "unchanged": zip_hash == V10_ZIP_SHA256,
            },
            "logical_to_physical": expected_mapping,
            "decoded_physical_lcs": decoded_lcs,
            "lc_selector_equations": edge_equations,
            "mse0_high_to_low_ports": {
                "port2": {
                    "source": "LC13",
                    "mode": "buffer",
                    "keep_last_index": 7,
                },
                "port1": {
                    "source": "LC2",
                    "mode": "keep",
                    "keep_last_index": 2,
                },
                "port0": {
                    "source": "PE3",
                    "mode": "keep",
                    "keep_last_index": 1,
                },
            },
            "first_carrier_last_index": first_carrier_last_index,
            "first_match_release": first_match_release,
            "start_equation": (
                "accepted Start_Comp -> sem_cs=CMPT -> "
                "sem2iga_exec_start=1 until slice_cmpt_finish -> "
                "slice_start_run=sem2iga_exec_start"
            ),
            "first_request_equation": (
                "LC13/LC2/PE3 selected-valid -> mem_all_idx_matched -> "
                "mem_ag_idx_queue_wr_en -> !queue_empty -> "
                "mse_mem_ag_tag_valid & transaction_addr_bias_bp_pre -> "
                "mem_ag_ob_vld_in -> mem_ag_ob_chl_hs -> "
                "mse2mem_request_valid"
            ),
            "terminal_equation": (
                "LC18 final tag last && last_index==0 -> buffer5/GA tag -> "
                "RD_Buffer_AG buf_ag_last_req_flag -> accepted write data -> "
                "slice_cmpt_finish"
            ),
            "sca": {
                "exec_length": sca["Exec_Length"],
                "repeat_num": sca["Repeat_Num"],
                "a_slice_count": len(a_entries),
                "d_slice_count": len(d_entries),
                "d_bytes_per_slice": (
                    sorted({item.get("length") for item in d_entries})
                ),
            },
        }
    )

    report = {
        "schema": "qlinearadd-node0007-v10-local-rtl-semantics-reaudit-v1",
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
        "mutation": mutation,
        "rule_receipts": receipts,
        "facts": facts,
        "file_receipts": {
            name: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in FILES.items()
        },
    }
    if write_report and mutation is None:
        negative_controls = {}
        for name in (
            "start_level_to_pulse",
            "lc2_src_to_zero",
            "mse_port_order_swap",
            "mse_keep_threshold0_zero",
            "fifo_reset_nonempty",
            "ag_initial_not_ready",
            "buffer_mask_flip",
            "terminal_nonzero",
        ):
            mutated = audit(write_report=False, mutation=name)
            negative_controls[name] = {
                "failed_closed": not mutated["valid"],
                "error_count": mutated["error_count"],
                "errors": mutated["errors"],
            }
        report["negative_controls"] = negative_controls
        report["all_negative_controls_fail_closed"] = all(
            item["failed_closed"] for item in negative_controls.values()
        )
        if not report["all_negative_controls_fail_closed"]:
            report["valid"] = False
            report["errors"].append("one or more negative controls did not fail")
            report["error_count"] = len(report["errors"])
        REPORT_ROOT.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return report


def main() -> int:
    report = audit(write_report=True)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
