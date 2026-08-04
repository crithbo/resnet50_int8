from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-gap-ga-accumulator-state-v1"
CONTRACT_PATH = (
    "contracts/operator_config/gap_ga_accumulator_state_v1.json"
)
INBUFFER_RTL = (
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
    "GA_PE_Inbuffer.sv"
)
OUTBUFFER_RTL = (
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
    "GA_PE_Outbuffer.sv"
)
V5_ANALYSIS = (
    "server_returns/gap_hwop0071_probe_v5_return_20260723/"
    "GAP_PROBE_V5_ANALYSIS.md"
)
V7_PACKAGE_ROOT = (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "gap_hwop0071_sum_probe_v7"
)
V7_PACKAGE_ZIP = f"{V7_PACKAGE_ROOT}.zip"
V7_PACKAGE_SHA = f"{V7_PACKAGE_ZIP}.sha256"
V7_RETURN_ROOT = (
    "server_returns/gap_hwop0071_probe_v7_return_20260724"
)
V7_DIAGNOSIS = f"{V7_RETURN_ROOT}/GAP_PROBE_V7_DIAGNOSIS.md"
V7_ANALYSIS = f"{V7_RETURN_ROOT}/gap_probe_v7_analysis.json"
V7_NUMERIC = f"{V7_RETURN_ROOT}/gap_numeric_path_report_v7.json"
V7_ACCEPTANCE = f"{V7_RETURN_ROOT}/native_return_acceptance_v7.json"

RULE_GA_OCCUPANCY = "CDA-GA-OUTBUFFER-OCCUPANCY-001"
RULE_GA_INVALID_SLOT = "CDA-GA-INVALID-SLOT-ISOLATION-001"
RULE_GA_CROSS_BLOCK = "CDA-GA-CROSS-BLOCK-INIT-001"
RULE_ORTHOGONAL = "CDA-GAP-ORTHOGONAL-DEFECTS-001"
RULE_D_RELEASE = "CDA-GAP-D-READBACK-COVERAGE-001"
RULE_MONITOR = "CDA-MSE4-MONITOR-EVIDENCE-001"
RULE_IDENTITY = "CDA-SERVER-FOCUSED-IDENTITY-001"


class GapGaAccumulatorStateError(ValueError):
    pass


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise GapGaAccumulatorStateError(f"required file is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _require_snippets(
    root: Path, relative: str, snippets: tuple[str, ...]
) -> dict[str, Any]:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    missing = [snippet for snippet in snippets if snippet not in text]
    if missing:
        raise GapGaAccumulatorStateError(
            f"RTL accumulator equations differ in {relative}: {missing}"
        )
    return _binding(root, relative)


def int32_noncalculate_operand_decision(
    *,
    matched: bool,
    transout_initial: int,
    calculate: bool,
    outbuffer_valid: bool,
    outbuffer_data: int,
    configured_constant: int = 0,
) -> dict[str, Any]:
    if transout_initial < 0 or transout_initial > 3:
        raise GapGaAccumulatorStateError(
            "transout_initial must be a two-bit value"
        )
    end_initial = transout_initial >= 2
    if transout_initial == 0:
        input_c = configured_constant
        source = "configured_inport2_constant"
    elif calculate:
        input_c = outbuffer_data if outbuffer_valid else 0
        source = (
            "valid_outbuffer_during_calculate"
            if outbuffer_valid
            else "zero_for_invalid_outbuffer_during_calculate"
        )
    elif not end_initial:
        input_c = 0
        source = "zero_during_initial_pair"
    else:
        input_c = outbuffer_data
        source = "outbuffer_data_without_valid_guard"
    return {
        "matched": matched,
        "transout_initial": transout_initial,
        "calculate": calculate,
        "end_transout_initial": end_initial,
        "outbuffer_valid": outbuffer_valid,
        "outbuffer_data": outbuffer_data & 0xFFFFFFFF,
        "input_c": input_c & 0xFFFFFFFF,
        "input_c_source": source,
        "outbuffer_write_enable": matched and transout_initial >= 2,
        "outbuffer_read_enable": matched
        and (end_initial or transout_initial == 0),
        "invalid_slot_reused_as_c": bool(
            matched
            and not calculate
            and transout_initial >= 2
            and not outbuffer_valid
            and (outbuffer_data & 0xFFFFFFFF) != 0
            and (input_c & 0xFFFFFFFF) == (outbuffer_data & 0xFFFFFFFF)
        ),
    }


def outbuffer_occupancy_transition(
    *,
    before_count: int,
    after_count: int,
    depth: int,
    removed_valid_count: int,
    accepted_write_count: int,
) -> dict[str, Any]:
    if depth <= 0:
        raise GapGaAccumulatorStateError("outbuffer depth must be positive")
    if min(
        before_count,
        after_count,
        removed_valid_count,
        accepted_write_count,
    ) < 0:
        raise GapGaAccumulatorStateError(
            "outbuffer transition values must be non-negative"
        )
    expected_count = (
        before_count - removed_valid_count + accepted_write_count
    )
    reasons: list[str] = []
    if not 0 <= before_count <= depth:
        reasons.append("before_count_out_of_range")
    if removed_valid_count > before_count:
        reasons.append("remove_exceeds_occupancy")
    if not 0 <= after_count <= depth:
        reasons.append("after_count_out_of_range")
    if after_count != expected_count:
        reasons.append("count_delta_not_explained_by_valid_items_and_handshakes")
    return {
        "rule_id": RULE_GA_OCCUPANCY,
        "before_count": before_count,
        "after_count": after_count,
        "depth": depth,
        "removed_valid_count": removed_valid_count,
        "accepted_write_count": accepted_write_count,
        "expected_count": expected_count,
        "valid": not reasons,
        "violations": reasons,
    }


def feedback_operand_is_legal(
    *,
    outbuffer_valid: bool,
    new_partial_valid: bool,
    input_c: int,
) -> bool:
    if not new_partial_valid:
        return input_c == 0
    return outbuffer_valid


def _v7_return(root: Path) -> dict[str, Any]:
    analysis = json.loads((root / V7_ANALYSIS).read_text(encoding="utf-8"))
    numeric = json.loads((root / V7_NUMERIC).read_text(encoding="utf-8"))
    acceptance = json.loads(
        (root / V7_ACCEPTANCE).read_text(encoding="utf-8")
    )
    state = analysis.get("ga_accumulator_state", {})
    mse4_address = numeric.get("mse4_write_address_check", {})
    mse4_output = numeric.get("mse4_output_check", {})
    matrices = acceptance.get("numeric", {}).get("matrices", [])
    expected_classification = (
        "ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse"
    )
    if (
        analysis.get("classification") != expected_classification
        or state.get("configured_outbuffer_depth") != 2
        or state.get("underflow_transition_count") != 8
        or state.get("invalid_slot_c_reuse_count") != 217
        or mse4_address.get("request_count") != 512
        or mse4_address.get("unique_address_count") != 2
        or len(matrices) != 16
        or any(item.get("expected_length_128bit") != 512 for item in matrices)
    ):
        raise GapGaAccumulatorStateError(
            "probe_v7 dynamic evidence no longer matches the adjudicated rules"
        )
    first = state["first_underflow_transitions"][0]
    occupancy = outbuffer_occupancy_transition(
        before_count=first["before_count"],
        after_count=first["after_count"],
        depth=first["configured_depth"],
        removed_valid_count=2,
        accepted_write_count=first["observed_write_handshake"],
    )
    if occupancy["valid"]:
        raise GapGaAccumulatorStateError(
            "probe_v7 occupancy violation no longer reproduces"
        )
    return {
        "status": "server_dynamic_counterexample_accepted",
        "classification": expected_classification,
        "bindings": {
            "diagnosis": _binding(root, V7_DIAGNOSIS),
            "analysis": _binding(root, V7_ANALYSIS),
            "numeric": _binding(root, V7_NUMERIC),
            "native_acceptance": _binding(root, V7_ACCEPTANCE),
        },
        "ga": {
            "event_count": state["event_count"],
            "depth": state["configured_outbuffer_depth"],
            "illegal_count_event_count": state[
                "illegal_outbuffer_count_event_count"
            ],
            "underflow_transition_count": state[
                "underflow_transition_count"
            ],
            "first_underflow_transition": first,
            "occupancy_validation": occupancy,
            "invalid_slot_c_reuse_count": state[
                "invalid_slot_c_reuse_count"
            ],
            "first_invalid_slot_c_reuse": state[
                "first_invalid_slot_c_reuse"
            ][0],
        },
        "independent_config_failure": {
            "mse4_request_count": mse4_address["request_count"],
            "unique_d_address_count": mse4_address["unique_address_count"],
            "slice_count": len(matrices),
            "expected_lines_per_slice": 512,
            "passed_slice_count": acceptance["numeric"][
                "passed_matrix_count"
            ],
        },
        "monitor_boundary": {
            "local_wdata_records": mse4_output[
                "actual_128bit_record_count"
            ],
            "same_clock_v5_request_count": 512,
            "same_clock_v5_wdata_count": 512,
            "local_count_delta_is_drop_proof": False,
        },
        "identity": {
            "focused_rtl_match_count": 14,
            "focused_rtl_expected_count": 14,
            "pre_post_post_run_stable": True,
            "whole_tree_hash_mismatch_is_rejection_by_itself": False,
        },
    }


def _v7_package(root: Path) -> dict[str, Any]:
    manifest_rel = f"{V7_PACKAGE_ROOT}/TEST_PACKAGE_MANIFEST.json"
    manifest_path = root / manifest_rel
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise GapGaAccumulatorStateError("v7 package manifest is malformed")
    zip_binding = _binding(root, V7_PACKAGE_ZIP)
    sidecar = (root / V7_PACKAGE_SHA).read_text(
        encoding="utf-8"
    ).strip()
    expected_sidecar = f"{zip_binding['sha256']}  {Path(V7_PACKAGE_ZIP).name}"
    if sidecar != expected_sidecar:
        raise GapGaAccumulatorStateError("v7 ZIP SHA sidecar differs")
    if (
        manifest.get("schema") != "resnet50-gap-probe-test-package-v7"
        or manifest.get("install_name") != "gap_hwop0071_sum_probe_v7"
        or manifest.get("probe_policy", {}).get(
            "functional_rtl_v_or_sv_included"
        )
        is not False
        or manifest.get("probe_policy", {}).get(
            "functional_rtl_modified_by_installer"
        )
        is not False
        or manifest.get("return_policy", {}).get("waveforms_forbidden")
        is not True
    ):
        raise GapGaAccumulatorStateError("v7 package policy differs")
    return {
        "status": "generated_frozen_server_return_accepted",
        "zip": zip_binding,
        "sha256_sidecar": _binding(root, V7_PACKAGE_SHA),
        "manifest": _binding(root, manifest_rel),
        "functional_rtl_included": False,
        "wave_dump_enabled": False,
        "observer_event": "GA_ACCUM_STATE",
        "event_limit": 512,
        "expected_return_name": "gap_hwop0071_sum_probe_v7_return.zip",
    }


def build_gap_ga_accumulator_state_contract(
    project_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    inbuffer = _require_snippets(
        root,
        INBUFFER_RTL,
        (
            "ga_pe_inbuffer_valid_bit[2] | "
            "(alu_op_is_transout&&(transout_initial[0]|transout_initial[1]))",
            "else if (ga_pe_transout_calculate_done) begin",
            "assign end_transout_initial = alu_is_fp32 ? "
            "(transout_initial==2'b11) : (alu_is_int32 ? "
            "(transout_initial>=2'b10)",
            "assign ga_pe_outbuffer_wr_enable = ga_pe_inbuffer_matched",
            "assign ga_pe_outbuffer_rd_enable = ga_pe_inbuffer_matched",
            "ga_pe_outbuffer2alu_data;//ga_pe_outbuffer2alu_valid_bit",
        ),
    )
    outbuffer = _require_snippets(
        root,
        OUTBUFFER_RTL,
        (
            "ga_pe_outbuffer_tag[ga_pe_outbuffer_rd_ptr] <= 'b0;",
            "ga_pe_outbuffer_tag[0] <= 'b0;",
            "ga_pe_outbuffer_tag[1] <= 'b0;",
            "if (ga_pe_outbuffer_wr_en) begin",
            "ga_pe_outbuffer_data[ga_pe_outbuffer_wr_ptr] "
            "<= ga_pe_outbuffer_wr_data;",
            "assign ga_pe_outbuffer_rd_data = "
            "ga_pe_outbuffer_data[ga_pe_outbuffer_rd_ptr];",
            "assign ga_pe_outbuffer2alu_valid_bit",
            "assign ga_pe_outbuffer2alu_data",
        ),
    )
    counterexample = int32_noncalculate_operand_decision(
        matched=True,
        transout_initial=3,
        calculate=False,
        outbuffer_valid=False,
        outbuffer_data=0x00012AB3,
    )
    if not counterexample["invalid_slot_reused_as_c"]:
        raise GapGaAccumulatorStateError(
            "static invalid-slot counterexample no longer reproduces"
        )
    reset_decision = int32_noncalculate_operand_decision(
        matched=True,
        transout_initial=0,
        calculate=False,
        outbuffer_valid=False,
        outbuffer_data=0x00012AB3,
    )
    if reset_decision["input_c"] != 0:
        raise GapGaAccumulatorStateError(
            "first INT32 reduction event no longer uses configured zero"
        )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "server_dynamic_root_cause_closed_release_blocked",
        "inputs": {
            "inbuffer_rtl": inbuffer,
            "outbuffer_rtl": outbuffer,
            "v5_numeric_boundary": _binding(root, V5_ANALYSIS),
        },
        "rtl_equations": {
            "match": (
                "for transout with transout_initial bit0|bit1 set, inport2 "
                "valid is not required for ga_pe_inbuffer_matched"
            ),
            "int32_end_initial": "end_transout_initial=(transout_initial>=2)",
            "noncalculate_input_c": (
                "transout_initial==0 ? configured_C : "
                "!end_transout_initial ? 0 : outbuffer_data[rd_ptr]"
            ),
            "missing_guard": (
                "the final branch does not test ga_pe_outbuffer2alu_valid_bit"
            ),
            "tag_lifetime": (
                "read/calculate/result-last branches clear outbuffer tags"
            ),
            "data_lifetime": (
                "outbuffer data has only a write-enable assignment and is not "
                "cleared when its tag is cleared"
            ),
            "selected_data": (
                "ga_pe_outbuffer_rd_data always reads data[rd_ptr], independent "
                "of tag valid and count"
            ),
        },
        "state_transition_counterexample": {
            "precondition": {
                "opcode": "int32_sum",
                "matched": True,
                "transout_initial": 3,
                "calculate": False,
                "selected_outbuffer_tag_valid": False,
                "selected_outbuffer_data": "0x00012ab3",
            },
            "decision": counterexample,
            "result": (
                "ALU input C is 0x00012ab3 even though the selected slot is "
                "invalid; the arithmetic result can therefore include stale "
                "state from a preceding reduction block"
            ),
            "classification": "CONTRADICTED",
            "scope": (
                "universal RTL state counterexample and reachability mechanism; "
                "not yet an observed v7 occurrence in the exact server run"
            ),
        },
        "reachability": {
            "tag_clear_without_data_clear": True,
            "read_pointer_selects_cleared_slot_data": True,
            "transout_initial_saturates_at_three_until_calculate_done": True,
            "calculate_done_resets_transout_initial_to_zero": True,
            "v5_exact_boundary": {
                "block0_matches_golden": True,
                "block1_first_c8_mismatches": True,
                "full_int32_match_count": 10,
                "full_int32_mismatch_count": 2038,
                "first_wrong_boundary": (
                    "GA block1 final input0+input2 operands before MSE4"
                ),
            },
            "remaining_dynamic_question": None,
        },
        "server_test": _v7_package(root),
        "server_return": _v7_return(root),
        "rule_ids": [
            RULE_GA_OCCUPANCY,
            RULE_GA_INVALID_SLOT,
            RULE_GA_CROSS_BLOCK,
            RULE_ORTHOGONAL,
            RULE_D_RELEASE,
            RULE_MONITOR,
            RULE_IDENTITY,
        ],
        "validation_rules": {
            RULE_GA_OCCUPANCY: (
                "0<=count<=DEPTH at every cycle; compaction removes only "
                "actually valid entries and accepted writes alone add entries"
            ),
            RULE_GA_INVALID_SLOT: (
                "an invalid tag/valid slot cannot drive an ALU tag or input C"
            ),
            RULE_GA_CROSS_BLOCK: (
                "a new block keeps C=0 until a new partial is valid; "
                "transout_initial alone never authorizes feedback"
            ),
            RULE_ORTHOGONAL: (
                "RTL_CONTROL and CONFIG_SEMANTICS failures are independent "
                "blockers and must be released independently"
            ),
            RULE_D_RELEASE: (
                "each slice must cover all 512 expected D readback lines and "
                "pass golden; aggregate request count is insufficient"
            ),
            RULE_MONITOR: (
                "a local request/wdata delta cannot prove a lost write without "
                "same-clock observation or formal readback"
            ),
            RULE_IDENTITY: (
                "server identity uses pre/post/post-run stability plus focused "
                "file matches; whole-tree hash mismatch alone is not rejection"
            ),
        },
        "acceptance": {
            "decisive_condition": (
                "matched && trans_init>=2 && !calc && !ob_valid && "
                "input2==outbuffer_data[rd_ptr] && input2!=0"
            ),
            "if_observed": (
                "classify exact GAP root as "
                "ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse"
            ),
            "observed": True,
        },
        "release": {
            "blocker": "B_GAP_GA_ACCUM_STATE",
            "blocker_resolved": False,
            "functional_rtl_modified": False,
            "gap_candidate_allowed": False,
        },
    }
    payload["contract_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_gap_ga_accumulator_state_contract(
    value: Mapping[str, Any], project_root: Path
) -> None:
    expected = build_gap_ga_accumulator_state_contract(project_root)
    if value != expected:
        raise GapGaAccumulatorStateError(
            "GAP GA accumulator state contract differs from hash-bound inputs"
        )


def write_gap_ga_accumulator_state_contract(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CONTRACT_PATH",
    "GapGaAccumulatorStateError",
    "SCHEMA",
    "build_gap_ga_accumulator_state_contract",
    "feedback_operand_is_legal",
    "int32_noncalculate_operand_decision",
    "outbuffer_occupancy_transition",
    "validate_gap_ga_accumulator_state_contract",
    "write_gap_ga_accumulator_state_contract",
]
