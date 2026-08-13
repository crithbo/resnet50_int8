#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p28 return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import analyze_conv_native_four_lane_0ccae916_p18_return as common


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p28_b5release"
EXECUTION_ID = "r1786246428371448974_139815"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p28_b5release_"
    r"r1786246428371448974_139815_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 2_830_429
RETURN_SHA256 = "95a73107cc812199aefab7196ae94e49f75ea377213dc66056eaaa67a72d6b44"
SOURCE_BYTES = 5_910_425
SOURCE_SHA256 = "3b15bf1cebf18b95d07e4c290ccf246d7cd6f89e6b2bd6c9665b05186b2e0066"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p28_return_analysis/report.json"
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)
GENERATED = (
    "diagnostics/source_bound_probe_catalog.json",
    "diagnostics/source_bound_probe_plan.json",
    "diagnostics/source_bound_generation_report.json",
    "diagnostics/source_bound_observer_generation.json",
    "diagnostics/source_bound_probe_binding.json",
    "diagnostics/source_bound_final_zip_contract.json",
    "tb_probe/source_bound_causal_observer.svh",
    "tb_probe/source_bound_observer_focus.sv",
    "package_tools/source_bound_causal_parser.py",
)


class AnalysisError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def record_map(value: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in value[key]
    }


def parse_tokens(line: str) -> dict[str, str] | None:
    if not line.startswith("CODEX_PROBE_V1 "):
        return None
    fields: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" not in token:
            raise AnalysisError(f"malformed source-bound token: {token!r}")
        key, value = token.split("=", 1)
        if not key or not value or not re.fullmatch(r"[A-Za-z0-9_.:/%+\[\]$-]+", value):
            raise AnalysisError(f"invalid source-bound token: {token!r}")
        fields[key] = value
    if not {"kind", "boundary", "instance"} <= set(fields):
        raise AnalysisError("source-bound record lacks identity")
    return fields


def parse_public(line: str) -> dict[str, str] | None:
    if not line.startswith("N4B5_EVENT_V1 "):
        return None
    return {
        key: value
        for key, value in (token.split("=", 1) for token in line.split()[1:])
    }


def as_int(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError:
        return -1


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")
    with zipfile.ZipFile(RETURN_ZIP) as archive:
        records, payloads, return_errors = common.safe_records(
            archive, f"{PACKAGE_ID}_return"
        )
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_records, source_payloads, source_errors = common.safe_records(
            archive, PACKAGE_ID
        )

    manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    feature = json.loads(payloads["evidence/feature_binding/c0.json"])
    package_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_preflight = json.loads(payloads["evidence/observer_precompile.json"])
    path_budget = json.loads(payloads["evidence/path_budget.json"])
    layout = json.loads(payloads["evidence/runtime_layout_receipt.json"])
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    publication = json.loads(payloads["evidence/publication_preflight.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    public_order = json.loads(payloads["evidence/public_order_summary.json"])
    triggered = json.loads(payloads["evidence/triggered_causal_summary.json"])
    returned_decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    generation = json.loads(
        source_payloads["diagnostics/source_bound_generation_report.json"]
    )
    cheap = json.loads(
        source_payloads["diagnostics/source_bound_observer_generation.json"]
    )
    binding = json.loads(
        source_payloads["diagnostics/source_bound_probe_binding.json"]
    )

    declared = record_map(manifest, "records_excluding_this_manifest")
    expected = set(declared) | {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"}
    allowed = record_map(allowlist, "records")
    allowed_set = set(allowed) | {"RETURN_ALLOWLIST.json"}
    declared_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in declared.items()
        if records.get(path) != row
    }
    allowed_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in allowed.items()
        if records.get(path) != row
    }
    source_files = {
        path: row
        for path, row in source_records.items()
        if path != "package_manifest.json"
    }
    generated_receipts = source_manifest["source_bound_observer_binding"][
        "generated_members"
    ]
    generated_exact = all(
        path in source_records
        and generated_receipts[path]["bytes"] == source_records[path]["size_bytes"]
        and generated_receipts[path]["sha256"] == source_records[path]["sha256"]
        for path in GENERATED
    )
    compile_status = int(payloads["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(payloads["evidence/run_exit_status.txt"].decode().strip())
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_log = payloads["runs/compile/compile_driver.log"].decode(errors="replace")
    sim_log = payloads["runs/c0/sim.log"].decode(errors="replace")
    simulator_argv = payloads["runs/c0/simulator_argv.txt"].decode(errors="replace")
    unique_return = (
        RETURN_ZIP.name == f"{PACKAGE_ID}_{EXECUTION_ID}_return.zip"
        and manifest["fixed_result_publication"]["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
    )
    compile_success = (
        compile_status == 0
        and "Verdi KDB elaboration finished with 0 error(s)" in compile_log
        and "Compilation completed!" in compile_log
        and "Error-[XMRE]" not in compile_log
        and "Error-[IND]" not in compile_log
    )
    simulation_started = (
        "+CODEX_CAUSAL_OBSERVER" in simulator_argv
        and "+N4B5_PUBLIC_CAUSAL" in simulator_argv
        and "CODEX_PROBE_V1 kind=ENABLED" in payloads[
            "runs/c0/source_bound_causal.log"
        ].decode(errors="replace")
        and feature.get("valid") is True
    )

    source_bound_records = [
        row
        for line in payloads["runs/c0/source_bound_causal.log"]
        .decode(errors="replace")
        .splitlines()
        if (row := parse_tokens(line)) is not None
    ]
    enabled = {
        row["boundary"] for row in source_bound_records if row["kind"] == "ENABLED"
    }
    expected_boundaries = {
        "memory_read_response",
        "buffer5_last_write_state",
        "buffer5_blocked_read_response",
        "buffer5_blocked_output_accept",
        "buffer5_last_write_terminal",
    }
    target_mrm = [
        row
        for row in source_bound_records
        if "BUFFER_MANAGER[5]" in row["instance"]
        and row["boundary"] == "memory_read_response"
        and int(row.get("mask", "0"), 16) != 0
    ]
    raw_mrm_response_seen = any(int(row["mask"], 16) & 1 for row in target_mrm)

    public_rows = [
        row
        for line in payloads["runs/c0/buffer5_public_observer.log"]
        .decode(errors="replace")
        .splitlines()
        if (row := parse_public(line)) is not None
    ]
    row2_read_samples = [
        row
        for row in public_rows
        if as_int(row["mrm_addr"]) == 2
        and as_int(row["mrm_valid"]) != 0
        and as_int(row["mrm_rw"]) == 0
        and as_int(row["mrm_ready"]) == 1
        and as_int(row["mrm_clear"]) != 0
    ]
    row2_reads = list(
        {
            (as_int(row["cycle"]), as_int(row["mrm_accept"])): row
            for row in row2_read_samples
        }.values()
    )
    row2_blocked = [
        row
        for row in public_rows
        if as_int(row["arm_addr"]) == 2
        and as_int(row["arm_rw"]) == 1
        and as_int(row["arm_wvalid"]) == 1
        and as_int(row["arm_ready"]) == 0
    ]
    final_row2 = max(row2_blocked, key=lambda row: as_int(row["cycle"]))
    final_block_start = min(
        as_int(row["cycle"])
        for row in row2_blocked
        if row["sa_tag"] == "0x3fdf"
    )
    prior_clear = max(
        (row for row in row2_reads if as_int(row["cycle"]) < final_block_start),
        key=lambda row: as_int(row["cycle"]),
    )
    row2_chain = (
        len(row2_reads) == 3
        and [as_int(row["mrm_clear"]) for row in row2_reads] == [0xF0, 0xF0, 0xF]
        and as_int(prior_clear["cycle"]) == 150
        and final_block_start == 151
        and as_int(final_row2["cycle"]) >= 5_700_000
        and as_int(final_row2["arm_ready"]) == 0
        and as_int(final_row2["mrm_valid"]) == 0
        and as_int(final_row2["mrm_clear"]) == 0
    )
    parser_escape = (
        returned_decision.get("decision") == "EVIDENCE_INCOMPLETE"
        and returned_decision.get("raw_record_count") == 0
        and len(returned_decision.get("errors", [])) == len(source_bound_records)
        and len(source_bound_records) == 1036
        and all("invalid logger token" in item for item in returned_decision["errors"])
        and b"TOKEN_RE = re.compile(r\"^[A-Za-z0-9_.:/%+-]+$\")"
        in source_payloads["package_tools/source_bound_causal_parser.py"]
    )
    no_formal = (
        source_manifest["formal_readback_count"] == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )

    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES
        and sha256(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES
        and sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_root_path_safe": not return_errors,
        "source_crc_root_path_safe": not source_errors,
        "return_exact_set": set(records) == expected,
        "return_manifest_records_exact": not declared_mismatch,
        "return_allowlist_exact": set(records) == allowed_set
        and not allowed_mismatch,
        "source_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": payloads[
            "source_package/package_manifest.json"
        ]
        == source_payloads["package_manifest.json"]
        and manifest["source_package_manifest_sha256"]
        == common.digest(source_payloads["package_manifest.json"]),
        "per_execution_unique_return_valid": unique_return,
        "package_install_observer_preflights_valid": package_preflight["valid"]
        and install_preflight["valid"]
        and observer_preflight["valid"]
        and path_budget["valid"]
        and package_status["production_compile_started"]
        and package_status["dut_simulation_started"]
        and path_budget["longest_projected_relative_path_chars"]
        == len(path_budget["longest_projected_relative_path"])
        == path_budget["max_projected_relative_path_chars"],
        "install_only_root_gate_valid": root_gate["valid"]
        and root_gate["ndp_root_toplevel_unchanged"]
        and layout["all_package_owned_paths_under_install"]
        and layout["root_exact_set_unchanged"]
        and not layout["unknown_items_deleted_or_overwritten"],
        "source_bound_release_generation_receipts_exact": generation["pass"]
        and not generation["errors"]
        and cheap["pass"]
        and not cheap["errors"]
        and generated_exact
        and binding["private_hierarchical_xmr_generated"] is False
        and binding["free_form_hdl_identifiers_accepted"] is False,
        "production_compile_pass": compile_success,
        "simulation_started": simulation_started,
        "external_int_after_qualified_progress": run_status == 125
        and signal_status == "INT"
        and public_order["observer"]["event_counts"]["SA_OUT_ACCEPT"] == 5
        and triggered["observer"]["natural_slice_finish_observed"] is False,
        "raw_source_bound_records_salvage_exact": len(source_bound_records) == 1036
        and enabled == expected_boundaries
        and raw_mrm_response_seen,
        "generated_parser_hierarchy_charset_escape_proven": parser_escape,
        "buffer5_row2_read_clear_then_final_block_chain_pass": row2_chain,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p28-return-analysis-v1",
        "status": "P28_ROW2_CLEAR_VISIBLE_READY_STILL_BLOCKED_SUCCESSOR_REQUIRED"
        if valid
        else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_AFTER_BUFFER5_ROW2_READ_CLEAR_WITH_READY_STILL_LOW_AND_GENERATED_PARSER_ESCAPE"
        if valid
        else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP),
            "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha256(RETURN_ZIP),
            "execution_identity": EXECUTION_ID,
            "unique_per_execution_basename_valid": unique_return,
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
            "source_manifest_sha256": common.digest(
                source_payloads["package_manifest.json"]
            ),
        },
        "internal_receipt": {
            "return_file_count": len(records),
            "source_file_count": len(source_records),
            "return_errors": return_errors,
            "source_errors": source_errors,
            "missing": sorted(expected - set(records)),
            "extra": sorted(set(records) - expected),
            "manifest_record_mismatches": declared_mismatch,
            "allowlist_record_mismatches": allowed_mismatch,
            "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "compile_succeeded": compile_success,
            "dut_simulation_started": simulation_started,
            "natural_terminal": False,
            "formal_D_payload_present": False,
        },
        "production_rtl_identity": {
            "valid": identity.get("collection_valid") is True,
            "actual_differs_cloud_authority": identity.get(
                "actual_differs_cloud_authority"
            ),
            "identity_difference_blocks_simulator": False,
            "buffer_leaf": identity.get("leaves", {}).get("Buffer.sv"),
            "memory_req_manager_leaf": identity.get("leaves", {}).get(
                "Memory_Req_Manager.sv"
            ),
            "causal_cone_adjudication": "Both actual leaves differ from 0cc provenance, but the generated module-local binds compiled and their dynamic records therefore bind to the actual production leaves. The difference is nonblocking provenance, not a simulation veto.",
        },
        "source_bound_parser_escape": {
            "classification": "PACKAGE_LOCAL_GENERATED_PARSER_INSTANCE_TOKEN_CHARSET_ESCAPE",
            "returned_decision": returned_decision["decision"],
            "returned_parser_raw_record_count": returned_decision["raw_record_count"],
            "returned_parser_error_count": len(returned_decision["errors"]),
            "independent_exact_record_count": len(source_bound_records),
            "enabled_boundaries": sorted(enabled),
            "target_buffer5_mrm_nonzero_record_count": len(target_mrm),
            "target_buffer5_mrm_response_seen": raw_mrm_response_seen,
            "root_cause": "The release-time generated parser rejected '[' and ']' in legal %m generate-array instance names; the raw logger and observer were enabled and complete within the bounded partial run.",
            "dut_or_config_failure": False,
        },
        "buffer5_row2_chain": {
            "row2_read_clear_count": len(row2_reads),
            "row2_read_clear_cycles": [as_int(row["cycle"]) for row in row2_reads],
            "row2_read_clear_masks": [row["mrm_clear"] for row in row2_reads],
            "final_preceding_row2_clear": prior_clear,
            "final_row2_block_start_cycle": final_block_start,
            "final_observed_row2_state": final_row2,
            "adjudication": "Buffer5 accepted row2 MRM reads with visible clear masks, including a row2 clear at cycle 150. The next cycle starts the final SA/ARM row2 write block, and ready remains low for more than 5.7M cycles with no later MRM request/clear. Held levels are state, not transactions.",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "production compile/simulation; upstream PE7/source13 and actual Memory_AG delivery from p26; Buffer5 public MRM read acceptance at row2 with nonzero clear; generated raw Buffer5 MRM response evidence",
            "FIRST_DIVERGENCE": "after the final observed Buffer5 row2 read/clear at cycle 150 and at the row2 SA/ARM write presented at cycle 151, where buf2arm_req_ready remains low",
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE_POST_ROW2_CLEAR_VALID_OWNERSHIP",
                "classification": "BUFFER5_ROW2_CLEAR_VISIBLE_BUT_ROW_NOT_RELEASED",
                "remaining_observational_equivalents": [
                    "another writer or ownership source repopulates row2 between the observed clear and ready recomputation",
                    "the visible MRM clear mask does not clear every byte-valid owner required by the 0xff ARM write",
                    "row2 byte-valid state is clear but bank-ready/aggregate-ready recomputation remains low",
                ],
                "authorized_config_fix": None,
                "functional_rtl_root_cause_proven": False,
            },
        },
        "result_conjunction": {
            "compile": compile_success,
            "simulator_started": simulation_started,
            "c0_slice_finish": False,
            "natural_terminal_27_of_27": False,
            "formal_D_320_of_320": False,
            "mismatch_zero_claim": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "performance_claimed": False,
            "passed": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE_BUFFER5_NO_MEMORY_REQUEST_MANAGER_READ_VISIBLE",
                "B_CONV_NATIVE_BUFFER5_ROW2_MATCH_UNPROVEN",
                "B_CONV_NATIVE_BUFFER5_ROW2_CLEAR_VISIBILITY_UNPROVEN",
            ],
            "opened": [
                "B_CONV_NATIVE_GENERATED_PARSER_INSTANCE_TOKEN_CHARSET_ESCAPE",
                "B_CONV_NATIVE_BUFFER5_POST_ROW2_CLEAR_VALID_OWNERSHIP_UNRESOLVED",
            ],
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid,
            "fresh_identity": True,
            "highest_information_scope": "regenerate with the corrected shared parser and source-bound row2 monitor that removes the false arm2buf_last_bit gate, qualifies row2 write block/MRM read/clear, and distinguishes post-clear bank-valid ownership from ready recomputation; preserve the focused Buffer5 public timeline for exact ordering",
            "frozen": "87 payload members, numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/functional RTL",
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {
                "bytes": (ROOT / path).stat().st_size,
                "sha256": sha256(ROOT / path),
            }
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_DELTA_PROPOSAL",
            "confirmed": [
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "delta": "Generated parser exact traces must include legal %m generate-array and '$' hierarchy tokens; flat tb.dut.probe alone did not exercise the production logger surface.",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {"status": result["status"], "valid": valid, "output": str(OUTPUT)},
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
