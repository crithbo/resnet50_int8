#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p29 return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
EXECUTION_ID = "r1786262719723400641_201731"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p29_row2own_"
    r"r1786262719723400641_201731_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 174_126
RETURN_SHA256 = "a4c6a968b70c1d6a7ec5b1b6fd047c69c82b76dbdb1a5febadc18bce02dc446b"
SOURCE_BYTES = 5_920_486
SOURCE_SHA256 = "43cfd63753ee964a92efec955f1dcba05c772c659406bd0142da8e37d2bd0f49"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_return_analysis/report_v2.json"
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


class AnalysisError(RuntimeError):
    pass


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_zip(path: Path) -> tuple[str, dict[str, dict[str, Any]], dict[str, bytes], list[str]]:
    errors: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"crc:{bad}")
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if len(roots) != 1:
            errors.append(f"root_count:{len(roots)}")
        root = next(iter(roots), "")
        for item in archive.infolist():
            if item.is_dir():
                continue
            parts = PurePosixPath(item.filename).parts
            if not parts or parts[0] != root or any(part in {"", ".", ".."} for part in parts):
                errors.append(f"unsafe:{item.filename}")
                continue
            rel = PurePosixPath(*parts[1:]).as_posix()
            if rel in records:
                errors.append(f"duplicate:{rel}")
                continue
            data = archive.read(item)
            payloads[rel] = data
            records[rel] = {"bytes": len(data), "sha256": digest_bytes(data)}
    return root, records, payloads, errors


def parse_probe(line: str) -> dict[str, str] | None:
    if not line.startswith("CODEX_PROBE_V1 "):
        return None
    result: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" not in token:
            raise AnalysisError(f"malformed probe token: {token!r}")
        key, value = token.split("=", 1)
        if not re.fullmatch(r"[A-Za-z0-9_.:/%+\[\]$-]+", value):
            raise AnalysisError(f"invalid probe value: {value!r}")
        result[key] = value
    return result


def parse_public(line: str) -> dict[str, str] | None:
    if not line.startswith("N4B5_EVENT_V1 "):
        return None
    return dict(token.split("=", 1) for token in line.split()[1:])


def number(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError:
        return -1


def main() -> int:
    for path in (RETURN_ZIP, SOURCE_ZIP):
        if not path.is_file():
            raise AnalysisError(f"required identity is absent: {path}")
    return_root, records, payloads, return_errors = safe_zip(RETURN_ZIP)
    source_root, source_records, source_payloads, source_errors = safe_zip(SOURCE_ZIP)

    core = json.loads(payloads["RETURN_CORE_MANIFEST.json"])
    core_status = json.loads(payloads["return_core/RETURN_CORE_STATUS.json"])
    sim_exit = json.loads(payloads["return_core/SIM_EXIT_RECEIPT.json"])
    plugins = json.loads(payloads["return_core/RETURN_PLUGIN_STATUS.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_status = json.loads(payloads["evidence/package_local_preflight_status.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_preflight = json.loads(payloads["evidence/observer_precompile.json"])
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    decision = json.loads(payloads["evidence/source_bound_causal_decision.json"])
    triggered = json.loads(payloads["evidence/triggered_causal_summary.json"])
    public_order = json.loads(payloads["evidence/public_order_summary.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    feature = json.loads(payloads["evidence/feature_binding/c0.json"])
    returned_source_manifest = payloads["source_package/package_manifest.json"]
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    generation = json.loads(payloads["source_package/source_bound_generation_report.json"])
    binding = json.loads(payloads["source_package/source_bound_probe_binding.json"])

    core_receipts = {row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]} for row in core["core_entry_receipts"]}
    plugin_ids = [row["plugin_id"] for row in request["plugins"]]
    expected = {
        "RETURN_CORE_MANIFEST.json",
        "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json",
        "return_core/SIM_EXIT_RECEIPT.json",
        *core_receipts,
    }
    for plugin_id in plugin_ids:
        expected |= {
            f"return_core/plugins/{plugin_id}.status.json",
            f"return_core/plugins/{plugin_id}.stdout.log",
            f"return_core/plugins/{plugin_id}.stderr.log",
        }
    receipt_mismatch = {
        path: {"expected": expected_row, "observed": records.get(path)}
        for path, expected_row in core_receipts.items()
        if records.get(path) != expected_row
    }
    plugin_status_mismatch: dict[str, Any] = {}
    for row in plugins:
        path = f"return_core/plugins/{row['plugin_id']}.status.json"
        observed = json.loads(payloads[path])
        if observed != row:
            plugin_status_mismatch[row["plugin_id"]] = {"aggregate": row, "member": observed}

    source_files = {
        path: {"size_bytes": row["bytes"], "sha256": row["sha256"]}
        for path, row in source_records.items()
        if path != "package_manifest.json"
    }
    compile_status = int(payloads["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(payloads["evidence/run_exit_status.txt"].decode().strip())
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_log = payloads["runs/compile/compile_driver.log"].decode(errors="replace")
    simulator_argv = payloads["runs/c0/simulator_argv.txt"].decode(errors="replace")
    compile_pass = (
        compile_status == 0
        and "Verdi KDB elaboration finished with 0 error(s)" in compile_log
        and "Compilation completed!" in compile_log
        and "Error-[XMRE]" not in compile_log
    )
    simulation_started = (
        package_status.get("dut_simulation_started") is True
        and sim_exit.get("sim_started") is True
        and "+CODEX_CAUSAL_OBSERVER" in simulator_argv
        and feature.get("valid") is True
    )

    probe_rows = [
        row
        for line in payloads["runs/c0/source_bound_causal.log"].decode(errors="replace").splitlines()
        if (row := parse_probe(line)) is not None
    ]
    target = "slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0]"
    target_b5 = [
        row for row in probe_rows
        if target in row.get("instance", "") and "BUFFER_MANAGER[5]" in row.get("instance", "")
    ]
    boundary_records = {
        boundary: [row for row in target_b5 if row.get("boundary") == boundary]
        for boundary in decision["enabled_boundaries"]
    }
    public_rows = [
        row
        for line in payloads["runs/c0/buffer5_public_observer.log"].decode(errors="replace").splitlines()
        if (row := parse_public(line)) is not None
    ]
    row2_clears = [
        row for row in public_rows
        if number(row["mrm_addr"]) == 2
        and number(row["mrm_valid"]) != 0
        and number(row["mrm_rw"]) == 0
        and number(row["mrm_ready"]) == 1
        and number(row["mrm_clear"]) != 0
    ]
    # The public monitor can emit two reasons at one cycle; adjudicate transactions once.
    row2_clears = list({number(row["cycle"]): row for row in row2_clears}.values())
    final_blocked = [
        row for row in public_rows
        if number(row["arm_addr"]) == 2
        and number(row["arm_rw"]) == 1
        and number(row["arm_wvalid"]) == 1
        and number(row["arm_ready"]) == 0
        and row["sa_tag"] == "0x3fdf"
    ]
    final_state = max(final_blocked, key=lambda row: number(row["cycle"]))
    final_block_start = min(number(row["cycle"]) for row in final_blocked)
    final_clear = max(
        (row for row in row2_clears if number(row["cycle"]) < final_block_start),
        key=lambda row: number(row["cycle"]),
    )
    generated_exact = (
        payloads["source_package/source_bound_generation_report.json"]
        == source_payloads["diagnostics/source_bound_generation_report.json"]
        and payloads["source_package/source_bound_probe_binding.json"]
        == source_payloads["diagnostics/source_bound_probe_binding.json"]
        and generation.get("pass") is True
        and not generation.get("errors")
    )
    core_plugin_pass = (
        [row["plugin_id"] for row in plugins] == plugin_ids
        and all(row["pass"] and row["exit_code"] == 0 and not row["timed_out"] for row in plugins)
        and not plugin_status_mismatch
        and not core["required_plugin_failures"]
    )
    no_formal = (
        source_manifest["formal_readback_count"] == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    p29_signature = (
        decision["decision"] == "BUFFER5_ROW2_OWNERSHIP_SIGNATURE_11110"
        and decision["matching_candidate_ids"] == ["row2_signature_11110"]
        and decision["errors"] == []
        and decision["raw_record_count"] == 840
        and decision["observations"] == {
            "competing_row2_writer_seen": False,
            "row2_bank_not_all_seen": True,
            "row2_clear_seen": True,
            "row2_write_accept_seen": True,
            "row2_write_blocked_seen": True,
        }
    )
    causal_chain = (
        [number(row["cycle"]) for row in row2_clears] == [138, 142, 150]
        and [number(row["mrm_clear"]) for row in row2_clears] == [0xF0, 0xF0, 0x0F]
        and number(final_clear["cycle"]) == 150
        and final_block_start == 151
        and number(final_state["cycle"]) >= 28_000_000
        and number(final_state["mrm_valid"]) == 0
        and number(final_state["mrm_clear"]) == 0
        and number(final_state["arm_ready"]) == 0
        and not decision["observations"]["competing_row2_writer_seen"]
    )

    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and digest_file(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and digest_file(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_single_root_path_safe": not return_errors and return_root == f"{PACKAGE_ID}_return",
        "source_crc_single_root_path_safe": not source_errors and source_root == PACKAGE_ID,
        "return_exact_set": set(records) == expected,
        "return_core_per_file_receipts_exact": not receipt_mismatch,
        "source_manifest_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": returned_source_manifest == source_payloads["package_manifest.json"],
        "execution_and_unique_basename_exact": core["execution_id"] == EXECUTION_ID and core["return_basename"] == RETURN_ZIP.name and sim_exit["execution_id"] == EXECUTION_ID,
        "install_root_package_observer_preflights_pass": package_preflight["valid"] and install_preflight["valid"] and observer_preflight["valid"] and root_gate["valid"] and root_gate["ndp_root_toplevel_unchanged"],
        "generated_source_bound_identity_exact": generated_exact and binding["private_hierarchical_xmr_generated"] is False,
        "production_compile_pass": compile_pass,
        "simulation_started_bounded_timeout_no_signal": simulation_started and run_status == 124 and signal_status == "NONE" and sim_exit["sim_exit_code"] == 124 and sim_exit["signal"] == "NONE",
        "post_sim_core_and_plugins_pass": core_status["return_publication_independent_of_plugin_success"] and core_plugin_pass,
        "source_bound_parser_signature_exact": p29_signature,
        "row2_clear_no_competing_writer_final_block_chain": causal_chain,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    result = {
        "schema": "conv-native-four-lane-0ccae916-p29-return-analysis-v1",
        "status": "P29_COMPETING_WRITER_CLOSED_BANK_VALID_READY_RECOMPUTE_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED",
        "valid": valid,
        "classification": "BOUNDED_DIAGNOSTIC_TIMEOUT_AFTER_QUALIFIED_PROGRESS_WITH_COMPLETE_CORE_RETURN" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP), "bytes": RETURN_ZIP.stat().st_size, "sha256": digest_file(RETURN_ZIP),
            "execution_id": EXECUTION_ID, "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(), "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": digest_file(SOURCE_ZIP), "source_manifest_sha256": digest_bytes(source_payloads["package_manifest.json"]),
        },
        "internal_receipt": {
            "return_root": return_root, "return_file_count": len(records), "source_root": source_root,
            "source_file_count": len(source_records), "return_errors": return_errors, "source_errors": source_errors,
            "missing": sorted(expected - set(records)), "extra": sorted(set(records) - expected),
            "core_receipt_mismatches": receipt_mismatch, "plugin_status_mismatches": plugin_status_mismatch,
            "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status, "run_exit_status": run_status, "signal_status": signal_status,
            "compile_succeeded": compile_pass, "dut_simulation_started": simulation_started,
            "natural_terminal": False, "c0_slice_finish": False, "formal_D_payload_present": False,
            "post_sim_core_disposition": core["disposition"], "all_six_plugins_pass": core_plugin_pass,
        },
        "production_rtl_identity": {
            "collection_valid": identity.get("collection_valid"),
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "buffer_leaf": identity.get("leaves", {}).get("Buffer.sv"),
            "memory_req_manager_leaf": identity.get("leaves", {}).get("Memory_Req_Manager.sv"),
            "causal_cone_adjudication": "Actual Buffer and Memory_Req_Manager bytes differ from 0cc provenance, but the package-local module binds compiled against and dynamically recorded the actual production modules. The difference remains nonblocking provenance, not a simulation veto.",
        },
        "source_bound_row2_evidence": {
            "decision": decision,
            "target_slice0_buffer5_record_counts": {key: len(value) for key, value in boundary_records.items()},
            "row2_clear_cycles": [number(row["cycle"]) for row in row2_clears],
            "row2_clear_masks": [row["mrm_clear"] for row in row2_clears],
            "final_clear": final_clear,
            "final_block_start_cycle": final_block_start,
            "final_observed_state": final_state,
            "adjudication": "p29 closes competing row2 writers. It proves accepted row2 MRM clears and both accepted/blocked row2 ARM states, but class_seen is lifetime-sticky; it does not expose the exact per-bank valid vector after the final clear. The remaining split is therefore clear/valid ownership versus ready recomputation.",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "production compile and c0 simulation; five SA outputs; ten Buffer5 MRM accepts; row2 MRM clear at cycles 138/142/150; generated parser exact signature; no competing row2 writer during final block",
            "FIRST_DIVERGENCE": "cycle 151, immediately after the last visible row2 clear at cycle 150, where the next Buffer5 row2 ARM write sees buf2arm_req_ready=0 and remains blocked",
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NARROWED_TO_TWO_POST_CLEAR_EQUIVALENTS",
                "classification": "BUFFER5_ROW2_BANK_VALID_OR_READY_RECOMPUTATION_UNRESOLVED",
                "closed": ["COMPETING_ROW2_WRITER_REPOPULATION"],
                "remaining_observational_equivalents": [
                    "the row2 clear sequence leaves at least one enabled bank byte-valid bit owned, so buf2arm_wreq_bank_ready is legitimately not all-ready",
                    "the row2 byte-valid state is fully clear but per-bank or aggregate ARM ready recomputation remains low",
                ],
                "authorized_config_fix": None,
                "functional_rtl_root_cause_proven": False,
            },
        },
        "result_conjunction": {
            "compile": compile_pass, "simulator_started": simulation_started, "c0_slice_finish": False,
            "natural_terminal_27_of_27": False, "formal_D_320_of_320": False, "mismatch_zero_claim": False,
            "E3": False, "E4": False, "E5": False, "performance_claimed": False, "passed": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE_GENERATED_PARSER_INSTANCE_TOKEN_CHARSET_ESCAPE",
                "B_CONV_NATIVE_POST_SIM_CORE_RETURN_UNPROVEN",
                "B_CONV_NATIVE_BUFFER5_COMPETING_ROW2_WRITER_UNRESOLVED",
            ],
            "narrowed": {
                "B_CONV_NATIVE_BUFFER5_POST_ROW2_CLEAR_VALID_OWNERSHIP_UNRESOLVED": "two equivalents remain: byte-valid ownership versus ready recomputation",
            },
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN", "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN", "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid, "fresh_identity": True,
            "highest_information_scope": "source-bound final-row2-block probe carrying exact 8-bank ready and 8x4x4 valid_buf state plus row2 MRM clear/strb payload around the clear-to-block boundary; distinguish valid state nonempty from fully-clear-but-ready-low in one run",
            "frozen": "87 payload members, numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/functional RTL",
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {"bytes": (ROOT / path).stat().st_size, "sha256": digest_file(ROOT / path)}
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
                "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
                "CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "delta": None,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": result["status"], "valid": valid, "output": str(OUTPUT)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
