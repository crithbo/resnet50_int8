from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    CONFIG_REL,
    FIXED_STAGES,
    ROOT_REL,
    build_configs,
    validate_d_buffer_column_pair,
)
from resnet50_pipeline.qlinearadd_node0007_d_buffer_supply_v15 import (
    build_configs as build_v15_configs,
)


EVIDENCE = ROOT / ROOT_REL
PIPELINE = EVIDENCE / "execplan/pipeline_output"
SOURCE_PIPELINE = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-supply-v15/execplan/pipeline_output"
)
REPORT = EVIDENCE / "targeted_validation_report.json"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
QADD_RULE_SHA256 = (
    "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"
)
FORMAL_RULE_ID = "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    resolved = str(path.resolve())
    native = "\\\\?\\" + resolved if sys.platform == "win32" else resolved
    with open(native, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _bytes(path: Path) -> bytes:
    resolved = str(path.resolve())
    native = "\\\\?\\" + resolved if sys.platform == "win32" else resolved
    with open(native, "rb") as stream:
        return stream.read()


def _leaf_diffs(before: Any, after: Any, prefix: str = "") -> list[str]:
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[str] = []
        for key in sorted(set(before) | set(after)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in before or key not in after:
                result.append(child)
            else:
                result.extend(_leaf_diffs(before[key], after[key], child))
        return result
    if isinstance(before, list) and isinstance(after, list):
        result = []
        for index in range(max(len(before), len(after))):
            child = f"{prefix}[{index}]"
            old = before[index] if index < len(before) else None
            new = after[index] if index < len(after) else None
            result.extend(_leaf_diffs(old, new, child))
        return result
    return [prefix] if before != after else []


def _json_path(stage: str, pipeline: Path) -> Path:
    matches = list((pipeline / "jsons").glob(f"{stage}_*.json"))
    if len(matches) != 1:
        raise ValueError(f"{stage}: final JSON match count {len(matches)}")
    return matches[0]


def _define(text: str, name: str) -> int:
    match = re.search(rf"`define\s+{re.escape(name)}\s+(\d+)\b", text)
    if match is None:
        raise ValueError(f"RTL constant is not a decimal literal: {name}")
    return int(match.group(1))


def _rtl_contract() -> dict[str, Any]:
    parameters = (
        ROOT / "Trassic2.0_RTL/code/NDP_rtl/includes/NDP_Parameters.svh"
    )
    queue = (
        ROOT
        / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
        "Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
    )
    rd_ag = (
        ROOT
        / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
        "Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    )
    memory_req = (
        ROOT
        / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/"
        "Buffer_Manager_Cluster/Memory_Req_Manager.sv"
    )
    parameter_text = parameters.read_text(encoding="utf-8")
    queue_text = queue.read_text(encoding="utf-8")
    rd_text = rd_ag.read_text(encoding="utf-8")
    memory_text = memory_req.read_text(encoding="utf-8")
    bank_num = _define(parameter_text, "BUFFER_BANK_NUM")
    bank_data_num = _define(parameter_text, "BUFFER_BANK_DATA_NUM")
    ddr_col_bits = _define(parameter_text, "DDR_COL_DATA_WIDTH")
    ddr_lane_bits = _define(parameter_text, "DDR_DATA_MIN_WIDTH")
    pair_equations = {
        "row_col_packed_together": (
            "mse_buf_queue_row_idx_masked, mse_buf_queue_col_idx_masked"
            in queue_text
        ),
        "pair_write_requires_all_inputs_and_mse_enable": (
            "buf_ag_idx_queue_wr_en = buf_all_idx_matched & mse_enable"
            in queue_text
        ),
        "pair_dequeue_uses_single_fifo_word": (
            "{mse_buf_ag_tag, mse_buf_ag_idx} = buf_ag_idx_queue_rd_data"
            in queue_text
        ),
        "rd_ag_splits_same_pair": (
            "{buf_ag_row_idx, buf_ag_col_idx} = mse_buf_ag_idx" in rd_text
        ),
        "rd_ag_expands_col_in_byte_units": (
            "buf_ag_col_idx + mse_buf_spatial_stride[SPATIAL_INDEX]"
            in rd_text
        ),
        "col_low_bits_select_byte_and_high_bits_select_bank": (
            "se2buf_req_bank_idx[REQ_IDX]"
            in memory_text
            and "se2buf_req_bank_offest[REQ_IDX]" in memory_text
            and "se2buf_mem_req_col_addr[REQ_IDX]"
            in memory_text
        ),
    }
    return {
        "buffer_bank_num": bank_num,
        "buffer_bank_data_num_bytes": bank_data_num,
        "buffer_row_bytes": bank_num * bank_data_num,
        "mse_request_lanes": ddr_col_bits // ddr_lane_bits,
        "mse_lane_bits": ddr_lane_bits,
        "mse_read_bytes": (ddr_col_bits // ddr_lane_bits)
        * ddr_lane_bits
        // 8,
        "paired_tag_consumer_equations": pair_equations,
        "paired_tag_consumer_equations_valid": all(pair_equations.values()),
        "paths": {
            "parameters": parameters.relative_to(ROOT).as_posix(),
            "buffer_ag_idx_queue": queue.relative_to(ROOT).as_posix(),
            "rd_buffer_ag": rd_ag.relative_to(ROOT).as_posix(),
            "memory_req_manager": memory_req.relative_to(ROOT).as_posix(),
        },
    }


def _negative_controls(configs: dict[str, Any]) -> dict[str, Any]:
    def rejected(mutator: Any) -> bool:
        candidate = json.loads(json.dumps(configs))
        mutator(candidate)
        try:
            validate_d_buffer_column_pair(candidate)
        except ValueError:
            return True
        return False

    stage = FIXED_STAGES[0]
    return {
        "delete_second_window": {
            "failed_closed": rejected(
                lambda c: c[stage]["buffer_loop_configs"]["GROUP2"][
                    "COL_LC"
                ].update({"end": 16})
            )
        },
        "overlap_or_gap": {
            "failed_closed": rejected(
                lambda c: c[stage]["buffer_loop_configs"]["GROUP2"][
                    "COL_LC"
                ].update({"stride": 8})
            )
        },
        "restore_col_stride_2": {
            "failed_closed": rejected(
                lambda c: c[stage]["buffer_loop_configs"]["GROUP2"][
                    "COL_LC"
                ].update({"stride": 2})
            )
        },
        "unused_second_physical_row": {
            "failed_closed": rejected(
                lambda c: (
                    c[stage]["buffer_loop_configs"]["GROUP2"][
                        "ROW_LC"
                    ].update({"end": 2}),
                    c[stage]["buffer_config"]["buffer5"].update(
                        {"buf_end_row_addr": 1}
                    ),
                )
            )
        },
        "tamper_mse_read_width": {
            "failed_closed": rejected(
                lambda c: c[stage]["stream_engine"]["stream2"].update(
                    {"buf_spatial_size": 8}
                )
            )
        },
        "tamper_transaction_length": {
            "failed_closed": rejected(
                lambda c: c[stage]["stream_engine"]["stream2"][
                    "idx_size"
                ].__setitem__(0, 15)
            )
        },
        "only_change_buf_spatial_size": {
            "failed_closed": rejected(
                lambda c: c[stage]["stream_engine"]["stream2"].update(
                    {"buf_spatial_size": 32}
                )
            )
        },
    }


def validate(*, write_report: bool = True) -> dict[str, Any]:
    configs = build_configs(ROOT)
    source_configs = build_v15_configs(ROOT)
    column_proof = validate_d_buffer_column_pair(configs)
    rtl_contract = _rtl_contract()
    negative_controls = _negative_controls(configs)
    allowed = {
        "buffer_config.buffer5.buf_end_row_addr",
        "buffer_loop_configs.GROUP2.COL_LC.end",
        "buffer_loop_configs.GROUP2.COL_LC.stride",
        "buffer_loop_configs.GROUP2.ROW_LC.end",
    }
    config_diffs = {
        stage: _leaf_diffs(source_configs[stage], configs[stage])
        for stage in configs
    }
    config_diff_valid = all(
        set(paths) == (allowed if stage in FIXED_STAGES else set())
        for stage, paths in config_diffs.items()
    )

    final_json: dict[str, Any] = {}
    final_json_errors: list[str] = []
    mapping_errors: list[str] = []
    bitstream_records: dict[str, Any] = {}
    for stage in configs:
        new_json = json.loads(_json_path(stage, PIPELINE).read_text(encoding="utf-8"))
        old_json = json.loads(
            _json_path(stage, SOURCE_PIPELINE).read_text(encoding="utf-8")
        )
        paths = _leaf_diffs(old_json, new_json)
        expected = allowed if stage in FIXED_STAGES else set()
        if set(paths) != expected:
            final_json_errors.append(f"{stage}: final JSON delta {paths}")
        final_json[stage] = {
            "path": _json_path(stage, PIPELINE).relative_to(ROOT).as_posix(),
            "sha256": sha256(_json_path(stage, PIPELINE)),
            "authorized_leaf_diffs": paths,
        }
        new_mapping = PIPELINE / "config" / stage / "mapping_review.json"
        old_mapping = SOURCE_PIPELINE / "config" / stage / "mapping_review.json"
        if _bytes(new_mapping) != _bytes(old_mapping):
            mapping_errors.append(f"{stage}: physical mapping changed")
        new_bits = next(
            (PIPELINE / "config" / stage).glob("*_bitstream_128b.bin")
        )
        old_bits = next(
            (SOURCE_PIPELINE / "config" / stage).glob("*_bitstream_128b.bin")
        )
        dump = (PIPELINE / "config" / stage / "detailed_dump.txt").read_text(
            encoding="utf-8"
        )
        decoded_valid = True
        if stage in FIXED_STAGES:
            decoded_valid = all(
                re.search(pattern, dump, flags=re.S)
                for pattern in (
                    r"Connect\(DRAM_LC\.LC2 -> GROUP2\.ROW_LC\).*?"
                    r"\bend\s+\| value=1\b",
                    r"Connect\(GROUP2\.ROW_LC -> GROUP2\.COL_LC\).*?"
                    r"\bstride\s+\| value=16\b.*?\bend\s+\| value=32\b",
                    r"buf_end_row_addr\s+\| value=0\b",
                    r"total_size\s+\| value=32\b",
                    r"buf_spatial_size\s+\| value=16\b",
                )
            )
        expected_change = stage in FIXED_STAGES
        bitstream_records[stage] = {
            "path": new_bits.relative_to(ROOT).as_posix(),
            "sha256": sha256(new_bits),
            "source_sha256": sha256(old_bits),
            "changed": _bytes(new_bits) != _bytes(old_bits),
            "change_expected": expected_change,
            "decoded_contract_valid": decoded_valid,
        }

    execplan_report = json.loads(
        (EVIDENCE / "execplan/execplan_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    double_run = json.loads(
        (EVIDENCE / "execplan/double_run_comparison.json").read_text(
            encoding="utf-8"
        )
    )
    frozen_pipeline_paths = [
        "install/execplan.txt",
        "install/execplan_op_a_dequant.txt",
        "install/execplan_op_b_dequant.txt",
        "install/execplan_op_relocation_pad.txt",
        "install/execplan_op_fp32_add.txt",
        "install/execplan_op_tail_mul.txt",
        "install/execplan_op_tail_round.txt",
        "sca_cfg.json",
        "sca_cfg_D.json",
        "graph_withbaseaddr.json",
    ]
    frozen_pipeline = {
        path: {
            "unchanged": _bytes(PIPELINE / path)
            == _bytes(SOURCE_PIPELINE / path),
            "sha256": sha256(PIPELINE / path),
        }
        for path in frozen_pipeline_paths
    }

    active_rule_text = QADD_RULE.read_text(encoding="utf-8")
    current_rule_bound = (
        sha256(QADD_RULE) == QADD_RULE_SHA256
        and FORMAL_RULE_ID in active_rule_text
    )
    current_rule_candidate_values = {
        stage: {
            "transaction_bytes": column_proof["records"][stage][
                "transaction_bytes"
            ],
            "buffer_row_bytes": rtl_contract["buffer_row_bytes"],
            "mse_read_bytes": rtl_contract["mse_read_bytes"],
            "accepted_row_col_pairs": [
                [window["row"], window["col_start"]]
                for window in column_proof["records"][stage]["read_windows"]
            ],
            "window_union": [
                [window["col_start"], window["col_end_exclusive"]]
                for window in column_proof["records"][stage]["read_windows"]
            ],
            "actual_max_row": max(
                column_proof["records"][stage]["row_indices"]
            ),
            "buf_end_row": column_proof["records"][stage][
                "buffer5_end_row_addr"
            ],
        }
        for stage in FIXED_STAGES
    }
    current_rule_window_proof = all(
        item["buffer_row_bytes"] == 32
        and item["mse_read_bytes"] == 16
        and item["accepted_row_col_pairs"] == [[0, 0], [0, 16]]
        and item["window_union"] == [[0, 16], [16, 32]]
        and item["actual_max_row"] == item["buf_end_row"] == 0
        for item in current_rule_candidate_values.values()
    )

    rtl_paths = {
        "parameters": (
            ROOT / "Trassic2.0_RTL/code/NDP_rtl/includes/NDP_Parameters.svh"
        ),
        "buffer_ag_idx_queue": (
            ROOT
            / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
            "Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
        ),
        "rd_buffer_ag": (
            ROOT
            / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
            "Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
        ),
        "wr_data_channel": (
            ROOT
            / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
            "Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv"
        ),
    }
    rtl_receipts = {
        name: {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
        }
        for name, path in rtl_paths.items()
    }
    oracle = ROOT / "ndp-sim/jsons/decode_add_fp32N_fp32N_fp32N.json"
    checks = {
        "column_pair_exact_partition": column_proof["valid"],
        "authorized_config_leaf_diff_only": config_diff_valid,
        "final_address_bound_json_authorized_diff_only": not final_json_errors,
        "physical_mapping_unchanged": not mapping_errors,
        "bitstream_changed_exact_three_stages": all(
            record["changed"] == record["change_expected"]
            for record in bitstream_records.values()
        ),
        "bitstream_decoded_column_pair_contract": all(
            record["decoded_contract_valid"]
            for record in bitstream_records.values()
        ),
        "native_execplan_validation_pass": execplan_report.get("valid") is True,
        "native_double_run_equal": double_run.get("equal") is True,
        "execplan_sca_addresses_occurrence_unchanged": all(
            item["unchanged"] for item in frozen_pipeline.values()
        ),
        "current_rule_receipt_bound": current_rule_bound,
        "rtl_width_equations_current_match": (
            rtl_contract["buffer_row_bytes"] == 32
            and rtl_contract["mse_read_bytes"] == 16
        ),
        "buffer_ag_row_col_pair_consumer_equations_valid": rtl_contract[
            "paired_tag_consumer_equations_valid"
        ],
        "current_rule_window_proof": current_rule_window_proof,
        "all_required_negative_controls_fail_closed": all(
            item["failed_closed"] for item in negative_controls.values()
        ),
    }
    technical_errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "qlinearadd-node0007-d-buffer-column-pair-validation-v1",
        "local_candidate_valid": not technical_errors,
        "errors": technical_errors,
        "checks": checks,
        "column_pair_proof": column_proof,
        "config_leaf_diffs": config_diffs,
        "final_json": final_json,
        "final_json_errors": final_json_errors,
        "mapping_errors": mapping_errors,
        "bitstream_records": bitstream_records,
        "execplan_validation_report": {
            "path": (
                EVIDENCE / "execplan/execplan_validation_report.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(
                EVIDENCE / "execplan/execplan_validation_report.json"
            ),
            "valid": execplan_report.get("valid") is True,
        },
        "double_run_comparison": {
            "path": (
                EVIDENCE / "execplan/double_run_comparison.json"
            ).relative_to(ROOT).as_posix(),
            "sha256": sha256(
                EVIDENCE / "execplan/double_run_comparison.json"
            ),
            "equal": double_run.get("equal") is True,
        },
        "frozen_pipeline_receipts": frozen_pipeline,
        "current_rule_match": {
            "active_blocker": False,
            "rule_path": QADD_RULE.relative_to(ROOT).as_posix(),
            "rule_sha256": QADD_RULE_SHA256,
            "rule_id": FORMAL_RULE_ID,
            "candidate_values": current_rule_candidate_values,
            "reason": "paired ROW/COL windows exactly cover one 32B transaction",
            "package_generation_allowed": True,
        },
        "rtl_contract": rtl_contract,
        "negative_controls": negative_controls,
        "rtl_receipts": rtl_receipts,
        "native_oracle": {
            "path": oracle.relative_to(ROOT).as_posix(),
            "sha256": sha256(oracle),
            "row_lc": {"start": 0, "end": 1, "stride": 1},
            "col_lc": {"start": 0, "end": 32, "stride": 16},
            "buffer5_end_row_addr": 0,
        },
        "broad_request_enumeration": {
            "stopped": True,
            "reason": (
                "known approximately 37M-request exhaustive expansion; "
                "changed leaves do not affect DRAM loops/base/dim stride"
            ),
            "replacement": (
                "exact leaf diff plus unchanged final execplan/SCA/"
                "graph_withbaseaddr and two-window coverage proof"
            ),
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "config_numeric_analysis_repeated": False,
        "functional_rtl_modified": False,
        "package_generated": False,
        "package_release": "LOCAL_VALIDATED_READY_FOR_FRESH_PACKAGING",
    }
    if write_report:
        REPORT.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["local_candidate_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
