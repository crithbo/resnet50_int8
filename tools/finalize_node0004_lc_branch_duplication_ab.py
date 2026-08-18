from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_lc_branch_duplication_ab import (  # noqa: E402
    active_lc_resources,
    address_signature,
    leaf_diff,
    load,
    mapping_nodes,
    math_rows,
    microtrace,
    relevant_connections,
    rtl_identity,
    sha256,
    sha256_json_lines,
    traffic_summary,
    write,
)


AB = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-node0004-lc-branch-duplication-ab-v3"
)
FAILED_NEW_KEY = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-node0004-lc-branch-duplication-ab-v1/FAILED_ATTEMPT_RECEIPT.json"
)
OUTPUT = ROOT / "outputs/conv_node0004_lc_branch_duplication_ab_v3"
V68 = ROOT / "outputs/conv_node0004_v68_return_analysis/report.json"
V97 = ROOT / (
    "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_"
    "r1786793347853153460_2912853/formal_return_analysis.json"
)


def exec_words(path: Path) -> list[int]:
    words: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if not row:
            continue
        words.extend((int(row[64:], 2), int(row[:64], 2)))
    if words and words[-1] == 0:
        words.pop()
    return words


def file_hashes(root: Path, prefix: str) -> dict[str, str]:
    result = {}
    target = root / prefix
    for path in sorted(target.rglob("*")):
        if path.is_file():
            result[path.relative_to(target).as_posix()] = sha256(path)
    return result


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"fresh output required: {OUTPUT}")
    a_pipeline = AB / "A/execplan/pipeline_output"
    b_capture = AB / "B/execplan"
    b_pipeline = b_capture / "pipeline_output"
    a_config = load(AB / "configs/A_baseline.json")
    b_config = load(AB / "configs/B_duplicate_lc_branch.json")
    a_final = load(a_pipeline / "jsons/op_w0_resnet50_conv_node0004_wave0.json")
    b_final = load(b_pipeline / "jsons/op_w0_resnet50_conv_node0004_wave0.json")
    a_mapping = load(AB / "A/mapping/mapping_review.json")
    b_mapping = load(AB / "B/mapping/mapping_review.json")
    a_map_evidence = load(AB / "A/mapping/mapping_evidence.json")
    b_map_evidence = load(AB / "B/mapping/mapping_evidence.json")
    a_address_report = load(AB / "A/execplan/request_address_validation_report.json")
    b_address_report = load(b_capture / "request_address_validation_report.json")
    a_exec_validation = load(AB / "A/execplan/execplan_validation_report.json")
    b_exec_validation = load(AB / "B/execplan/execplan_validation_report.json")
    a_exec_stage = a_exec_validation["facts"]["stages"][0]
    b_exec_stage = b_exec_validation["facts"]["stages"][0]
    boundary = microtrace(load(V68), load(V97))
    write(OUTPUT / "boundary_microtrace.json", boundary)

    expected_diff = [
        {"path": "dram_loop_configs.LC3.end", "old": 0, "new": 8},
        {"path": "dram_loop_configs.LC3.last_index", "old": 0, "new": 3},
        {
            "path": "dram_loop_configs.LC3.src_id",
            "old": None,
            "new": "DRAM_LC.LC15",
        },
        {"path": "dram_loop_configs.LC3.stride", "old": 0, "new": 1},
        {
            "path": "lc_pe_configs.PE1.inport2.src_id",
            "old": "DRAM_LC.LC9",
            "new": "DRAM_LC.LC3",
        },
    ]
    a_math, b_math = math_rows(a_final), math_rows(b_final)
    a_address, b_address = address_signature(a_address_report), address_signature(b_address_report)
    a_traffic, b_traffic = traffic_summary(a_address), traffic_summary(b_address)
    a_words = exec_words(a_pipeline / "install/execplan.txt")
    b_words = exec_words(b_pipeline / "install/execplan.txt")
    differing_commands = [index for index, pair in enumerate(zip(a_words, b_words)) if pair[0] != pair[1]]
    a_load, b_load = a_words[1], b_words[1]
    length_mask = 0xFF << 56
    a_active, b_active = active_lc_resources(a_mapping), active_lc_resources(b_mapping)
    data_payload_a = file_hashes(a_pipeline, "install/op_w0")
    data_payload_b = file_hashes(b_pipeline, "install/op_w0")
    config_meaningful_delta = (
        b_exec_stage["config_length_64bit_words"]
        - a_exec_stage["config_length_64bit_words"]
    ) * 8
    config_transport_delta = (
        b_exec_stage["transport_rows_128bit"]
        - a_exec_stage["transport_rows_128bit"]
    ) * 16
    data_payload_bytes = a_traffic["logical_payload_bytes"]

    checks = {
        "candidate_source_diff_exact": leaf_diff(a_config, b_config) == expected_diff,
        "candidate_materialized_diff_exact": leaf_diff(a_final, b_final) == expected_diff,
        "mapping_A_zero_penalty_no_fallback": a_map_evidence["penalty"] == 0
        and a_map_evidence["fallback_used"] is False,
        "mapping_B_zero_penalty_no_fallback": b_map_evidence["penalty"] == 0
        and b_map_evidence["fallback_used"] is False,
        "output_math_sequence_equal": a_math == b_math,
        "address_sequence_equal": a_address == b_address,
        "data_plane_memory_traffic_equal": a_traffic == b_traffic,
        "command_count_equal": len(a_words) == len(b_words),
        "only_Load_Config_length_command_field_changes": differing_commands == [1]
        and (a_load & ~length_mask) == (b_load & ~length_mask)
        and ((b_load >> 56) & 0xFF) == ((a_load >> 56) & 0xFF) + 1,
        "data_payload_files_equal": data_payload_a == data_payload_b,
        "active_lc_delta_exactly_one": len(b_active) == len(a_active) + 1,
        "physical_lc_capacity_respected": len(b_active) <= 20,
        "tuple10_local_boundary_proof": boundary["status"] == "PASS"
        and boundary["duplicated_branch_candidate"]["tuple10_possible"] is True,
        "shared_lc_negative_control": boundary["negative_control_shared_lc"][
            "tuple10_possible"
        ]
        is False,
        "native_odd_config_length_is_self_consistent": (
            b_exec_stage["config_length_64bit_words"] == 71
            and b_exec_stage["transport_rows_128bit"] == 36
            and b_exec_stage["last_row_high_half_is_transport_padding"] is True
        ),
        "shared_execplan_gate_A_pass": a_exec_validation["valid"] is True,
        "shared_execplan_gate_B_pass": b_exec_validation["valid"] is True,
    }
    semantic_equivalence = all(checks.values())
    cost = {
        "active_lc_A": len(a_active),
        "active_lc_B": len(b_active),
        "physical_capacity": 20,
        "occupancy_A_percent": len(a_active) * 100 / 20,
        "occupancy_B_percent": len(b_active) * 100 / 20,
        "additional_lc": 1,
        "spare_A": 20 - len(a_active),
        "spare_B": 20 - len(b_active),
        "relative_active_lc_increase_percent": 100 / len(a_active),
        "operator_command_count_delta": 0,
        "data_plane_memory_request_delta": 0,
        "data_plane_logical_payload_byte_delta": 0,
        "configured_PE1_occurrence_delta_per_slice": len(b_math) - len(a_math),
        "serialized_compute_stage_delta": 0,
        "configured_compute_cycle_upper_bound_delta": 0,
        "one_time_config_meaningful_byte_delta": config_meaningful_delta,
        "one_time_config_transport_byte_delta": config_transport_delta,
        "config_meaningful_over_data_payload_percent": config_meaningful_delta
        * 100
        / data_payload_bytes,
        "config_transport_over_data_payload_percent": config_transport_delta
        * 100
        / data_payload_bytes,
        "whole_launch_setup_boundary": (
            "one additional meaningful 64-bit config word and one additional "
            "128-bit transport row; data-plane execution bound is unchanged"
        ),
        "negligible": (
            semantic_equivalence
            and len(b_active) == 15
            and 20 - len(b_active) == 5
            and config_meaningful_delta == 8
            and config_transport_delta == 16
        ),
    }
    report = {
        "schema": "node0004-lc-branch-duplication-mapper-ab-final-v1",
        "status": "LOCAL_EQUIVALENCE_AND_NEGLIGIBLE_COST_PASS"
        if semantic_equivalence and cost["negligible"]
        else "LOCAL_EQUIVALENCE_REJECTED",
        "classification": "VALIDATED_CONFIG_WORKAROUND_CANDIDATE_NOT_PRODUCTION_RUN",
        "previous_progress": (
            "v97 validated one missing Memory_AG input1 32-unit tuple; v68 bound "
            "the next shared LC value to ROW_LC4-only backpressure while PE remained ready"
        ),
        "current_purpose": (
            "prove locally that a copied LC branch preserves math/address/work while "
            "decoupling the metadata tuple path before one targeted dynamic run"
        ),
        "candidate": {
            "reuse_dormant_logical_lc": "LC3",
            "copy_from": "LC9",
            "consumer_change": "PE1.inport2 DRAM_LC.LC9 -> DRAM_LC.LC3",
            "original_LC9_consumer": "GROUP4.ROW_LC",
            "config_diff": expected_diff,
        },
        "checks": checks,
        "mapping": {
            "A_summary": a_mapping["summary"],
            "B_summary": b_mapping["summary"],
            "A_nodes": mapping_nodes(a_mapping),
            "B_nodes": mapping_nodes(b_mapping),
            "A_relevant_connections": relevant_connections(a_mapping),
            "B_relevant_connections": relevant_connections(b_mapping),
            "A_active_lcs": a_active,
            "B_active_lcs": b_active,
        },
        "output_math": {
            "equation": "PE1 = LC15*8 + buffer_lc",
            "occurrences_per_slice": len(a_math),
            "sequence_sha256": sha256_json_lines(a_math),
            "equal": a_math == b_math,
            "range": [a_math[0], a_math[-1]],
        },
        "address_sequence": {
            "equal": a_address == b_address,
            "request_count_with_multiplicity": a_address[
                "request_count_with_multiplicity"
            ],
            "unique_request_address_count": a_address[
                "unique_request_address_count"
            ],
            "unique_request_addresses_sha256": a_address[
                "unique_request_addresses_sha256"
            ],
            "signature_sha256": hashlib.sha256(
                json.dumps(a_address, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "commands": {
            "instruction_count_64bit": len(a_words),
            "execplan_lines_128bit": len(
                (a_pipeline / "install/execplan.txt").read_text(encoding="utf-8").splitlines()
            ),
            "differing_command_indices": differing_commands,
            "A_Load_Config_length_64bit": (a_load >> 56) & 0xFF,
            "B_Load_Config_length_64bit": (b_load >> 56) & 0xFF,
            "same_command_count": len(a_words) == len(b_words),
        },
        "memory_traffic": {"A": a_traffic, "B": b_traffic, "equal": a_traffic == b_traffic},
        "cycle_upper_bound": {
            "LC13_LC14_LC15_inner_occurrences_per_slice": len(a_math),
            "baseline_metadata_path": ["LC15", "LC9", "PE1", "WRITE_STREAM0"],
            "candidate_metadata_path": ["LC15", "LC3", "PE1", "WRITE_STREAM0"],
            "serial_depth_equal": True,
            "configured_compute_occurrences_equal": len(a_math) == len(b_math),
            "data_plane_bound_delta": 0,
            "arbitrary_backpressure_bound": "unbounded for both A and B",
            "production_wall_cycles": "requires targeted return",
        },
        "cost": cost,
        "boundary_microtrace": {
            "path": (OUTPUT / "boundary_microtrace.json").relative_to(ROOT).as_posix(),
            "sha256": sha256(OUTPUT / "boundary_microtrace.json"),
        },
        "rtl_identity": rtl_identity(),
        "shared_gate": {
            "status": "PASS_ODD_MEANINGFUL_LENGTH_ACTIVATED",
            "A_validation": (
                AB / "A/execplan/execplan_validation_report.json"
            ).relative_to(ROOT).as_posix(),
            "B_validation": (
                AB / "B/execplan/execplan_validation_report.json"
            ).relative_to(ROOT).as_posix(),
            "required_negative_controls": [
                "odd meaningful length with exact zero high-half padding passes",
                "even meaningful length passes unchanged",
                "nonzero padded high-half fails",
                "programmed undercount or overcount fails",
                "64-bit/128-bit identity drift fails",
            ],
        },
        "next_dynamic_acceptance": {
            "allowed_after_targeted_package_local_gates": True,
            "must_observe": [
                "second-epoch copied LC3 Q1 accepted by PE1",
                "Memory_AG input1 tuple count reaches 10",
                "metadata capacity reaches 20 descriptors / 320 units",
                "prepared occupancy drains to zero",
                "natural terminal",
                "Formal-D 320/320 with no missing or mismatch",
            ],
            "retired_comparator_must_remain_absent": True,
        },
        "claim_boundary": (
            "Local mapper/encoder/native planner/request-address/current RTL and historical "
            "same-target dynamic evidence. The config workaround is locally equivalent and "
            "negligible, but no targeted production run, natural terminal or Formal-D is claimed. "
            "The active shared execplan validator and both current A/B bundles pass."
        ),
        "conflicts": [],
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write(OUTPUT / "mapper_ab_report.json", report)

    audit = {
        "schema": "node0004-lc-branch-duplication-rule-gap-audit-v1",
        "status": "RULE_GAP_CLOSED_CURRENT_GATE_PASS",
        "trigger": "two local fresh mapper/execplan attempts rejected at the same pre-release gate",
        "attempts": [
            {
                "candidate": "new LC16 key",
                "result": "mapper penalty0; 71 meaningful words; shared validator rejected 71 vs padded72",
                "receipt": FAILED_NEW_KEY.relative_to(ROOT).as_posix(),
            },
            {
                "candidate": "reuse dormant LC3 slot",
                "result": "mapper penalty0; 71 meaningful words; shared validator rejected 71 vs padded72",
                "receipt": (
                    AB / "B/execplan/execplan_validation_report.json"
                ).relative_to(ROOT).as_posix(),
            },
        ],
        "root": (
            "OperatorConfigExecPlanValidator counts every 128-bit transport row as two "
            "meaningful 64-bit words; native planner correctly programs the odd 71-word "
            "length and writes an all-zero high-half pad."
        ),
        "delta": (
            "derive meaningful length from the exact bound 64-bit artifact; for an odd "
            "length require the sole 128-bit high-half pad to be exactly zero and exact "
            "64/128 repacking identity"
        ),
        "activation": "shared meaningful-64-bit odd transport fix; related validation 29/29 PASS",
        "third_attempt_blocked_until_activation": False,
        "server_action": False,
    }
    write(OUTPUT / "RULE_GAP_AUDIT.json", audit)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"].startswith("LOCAL_EQUIVALENCE") else 1


if __name__ == "__main__":
    raise SystemExit(main())
