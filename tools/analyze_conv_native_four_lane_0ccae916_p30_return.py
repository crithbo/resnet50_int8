#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p30 return."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
EXECUTION_ID = "r1786345801746754550_481017"
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p30_bankvalid_"
    r"r1786345801746754550_481017_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
RETURN_BYTES = 148_318
RETURN_SHA256 = "409e0e9264353eac4b883e671b0a0502619257fe6948d0f171dc4c73e9a2e499"
SOURCE_BYTES = 5_943_878
SOURCE_SHA256 = "8229b380c9b33f99c8bd27d3eb21ce2ce17aae1b5eb0278926f27307887cbf34"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_return_analysis/report.json"
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
    "contracts/server_first_fresh_extra_audit_dispatch_v1.json",
    "tools/validate_server_first_fresh_extra_audit.py",
)


class AnalysisError(RuntimeError):
    pass


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_zip(path: Path) -> tuple[str, dict[str, dict[str, Any]], dict[str, bytes], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"crc:{bad}")
        files = [row for row in archive.infolist() if not row.is_dir()]
        roots = {PurePosixPath(row.filename).parts[0] for row in files}
        if len(roots) != 1:
            errors.append(f"root_count:{len(roots)}")
        root = next(iter(roots), "")
        for row in files:
            parts = PurePosixPath(row.filename).parts
            if not parts or parts[0] != root or any(part in {"", ".", ".."} for part in parts):
                errors.append(f"unsafe:{row.filename}")
                continue
            relative = PurePosixPath(*parts[1:]).as_posix()
            if relative in records:
                errors.append(f"duplicate:{relative}")
                continue
            data = archive.read(row)
            payloads[relative] = data
            records[relative] = {"bytes": len(data), "sha256": sha_bytes(data)}
    return root, records, payloads, errors


def parse_kv(line: str, prefix: str) -> dict[str, str] | None:
    if not line.startswith(prefix):
        return None
    result: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" not in token:
            raise AnalysisError(f"malformed token: {token!r}")
        key, value = token.split("=", 1)
        if not re.fullmatch(r"[A-Za-z0-9_.:/%+\[\]$-]+", value):
            raise AnalysisError(f"invalid token value: {value!r}")
        result[key] = value
    return result


def number(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError:
        return -1


def decode_payload(value: str) -> dict[str, int]:
    widths = (
        ("bank_ready", 8),
        ("buffer_mask", 8),
        ("mrm_clear", 8),
        ("valid_buf_clear", 8),
        ("valid_buf_wr_en", 8),
        ("arm2buf_wr_en", 8),
        ("buf_wr_en", 8),
        ("buf_wr_addr", 2),
        ("tag_buf_row_empty", 4),
    )
    numeric = int(value, 16)
    decoded: dict[str, int] = {}
    for name, width in reversed(widths):
        decoded[name] = numeric & ((1 << width) - 1)
        numeric >>= width
    return {name: decoded[name] for name, _ in widths}


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
    feature = json.loads(payloads["evidence/feature_binding/c0.json"])
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    request = json.loads(source_payloads["contracts/server_post_sim_return_request.json"])
    generation = json.loads(payloads["source_package/source_bound_generation_report.json"])
    binding = json.loads(payloads["source_package/source_bound_probe_binding.json"])

    receipts = {
        row["path"]: {"bytes": row["bytes"], "sha256": row["sha256"]}
        for row in core["core_entry_receipts"]
    }
    plugin_ids = [row["plugin_id"] for row in request["plugins"]]
    expected = {
        "RETURN_CORE_MANIFEST.json",
        "return_core/RETURN_CORE_STATUS.json",
        "return_core/RETURN_PLUGIN_STATUS.json",
        "return_core/SIM_EXIT_RECEIPT.json",
        *receipts,
    }
    for plugin_id in plugin_ids:
        expected |= {
            f"return_core/plugins/{plugin_id}.status.json",
            f"return_core/plugins/{plugin_id}.stdout.log",
            f"return_core/plugins/{plugin_id}.stderr.log",
        }
    receipt_mismatches = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in receipts.items()
        if records.get(path) != row
    }
    plugin_mismatches: dict[str, Any] = {}
    for row in plugins:
        member = json.loads(payloads[f"return_core/plugins/{row['plugin_id']}.status.json"])
        if member != row:
            plugin_mismatches[row["plugin_id"]] = {"aggregate": row, "member": member}

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
    plugins_pass = (
        [row["plugin_id"] for row in plugins] == plugin_ids
        and all(row["pass"] and row["exit_code"] == 0 and not row["timed_out"] for row in plugins)
        and not plugin_mismatches
        and not core["required_plugin_failures"]
    )

    probe_rows = [
        row
        for line in payloads["runs/c0/source_bound_causal.log"].decode(errors="replace").splitlines()
        if (row := parse_kv(line, "CODEX_PROBE_V1 ")) is not None
    ]
    target = "slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0]"
    target_rows = [
        row for row in probe_rows
        if target in row.get("instance", "") and "BUFFER_MANAGER[5]" in row.get("instance", "")
    ]
    target_arm = [row for row in target_rows if row.get("boundary") == "row2_arm_bank_valid_timeline"]
    target_mrm = [row for row in target_rows if row.get("boundary") == "row2_mrm_clear_valid_timeline"]
    arm_payloads = [
        {**row, "decoded": decode_payload(row["payload"])}
        for row in target_arm
        if row.get("payload") not in {None, "0"}
    ]
    mrm_payloads = [
        {**row, "decoded": decode_payload(row["payload"])}
        for row in target_mrm
        if row.get("payload") not in {None, "0"}
    ]
    last_target_arm = target_arm[-1]
    final_summary_absent = not any(row.get("kind") == "SUMMARY" for row in target_arm)
    final_ring_absent = not any(row.get("kind") in {"RING_STATE", "RING_POST"} for row in target_arm)
    stall_payload_zero = last_target_arm.get("kind") == "STALL" and last_target_arm.get("payload") == "0"

    public_rows = [
        row
        for line in payloads["runs/c0/buffer5_public_observer.log"].decode(errors="replace").splitlines()
        if (row := parse_kv(line, "N4B5_EVENT_V1 ")) is not None
    ]
    final_blocked = [
        row for row in public_rows
        if number(row["arm_addr"]) == 2
        and number(row["arm_rw"]) == 1
        and number(row["arm_wvalid"]) == 1
        and number(row["arm_ready"]) == 0
        and row["sa_tag"] == "0x3fdf"
    ]
    row2_clears = list({
        number(row["cycle"]): row for row in public_rows
        if number(row["mrm_addr"]) == 2
        and number(row["mrm_valid"]) != 0
        and number(row["mrm_rw"]) == 0
        and number(row["mrm_ready"]) == 1
        and number(row["mrm_clear"]) != 0
    }.values())
    final_block_start = min(number(row["cycle"]) for row in final_blocked)
    prior_clear = max(
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
        and binding.get("private_hierarchical_xmr_generated") is False
    )
    p30_signature = (
        decision["decision"] == "BUFFER5_ROW2_BANKVALID_SIGNATURE_1101010110"
        and decision["matching_candidate_ids"] == ["row2_bankvalid_signature_1101010110"]
        and decision["errors"] == []
        and decision["raw_record_count"] == 616
        and decision["observations"] == {
            "arm_accept_seen": True,
            "arm_blocked_seen": True,
            "bank_ready_00_seen": False,
            "bank_ready_0f_seen": True,
            "bank_ready_f0_seen": False,
            "bank_ready_ff_seen": True,
            "bank_ready_other_seen": False,
            "clear_0f_seen": True,
            "clear_f0_seen": True,
            "clear_other_seen": False,
        }
    )
    no_formal = (
        source_manifest["formal_readback_count"] == 0
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    interrupted = (
        signal_status == "INT"
        and sim_exit["signal"] == "INT"
        and sim_exit["sim_exit_code"] == 130
        and core["disposition"] == "PARTIAL_EXECUTION_RETURN"
        and core_status["disposition"] == "PARTIAL_EXECUTION_RETURN"
    )
    evidence_escape = (
        interrupted
        and final_summary_absent
        and final_ring_absent
        and stall_payload_zero
        and last_target_arm.get("mask") == "2b"
        and final_block_start == 151
        and number(prior_clear["cycle"]) == 150
        and len(final_blocked) >= 2
    )

    checks = {
        "transport_identity_exact": RETURN_ZIP.stat().st_size == RETURN_BYTES and sha_file(RETURN_ZIP) == RETURN_SHA256,
        "source_identity_exact": SOURCE_ZIP.stat().st_size == SOURCE_BYTES and sha_file(SOURCE_ZIP) == SOURCE_SHA256,
        "return_crc_single_root_path_safe": not return_errors and return_root == f"{PACKAGE_ID}_return",
        "source_crc_single_root_path_safe": not source_errors and source_root == PACKAGE_ID,
        "return_exact_set": set(records) == expected,
        "return_core_per_file_receipts_exact": not receipt_mismatches,
        "source_manifest_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": payloads["source_package/package_manifest.json"] == source_payloads["package_manifest.json"],
        "execution_and_unique_basename_exact": core["execution_id"] == EXECUTION_ID and core["return_basename"] == RETURN_ZIP.name and sim_exit["execution_id"] == EXECUTION_ID,
        "install_root_package_observer_preflights_pass": package_preflight["valid"] and install_preflight["valid"] and observer_preflight["valid"] and root_gate["valid"] and root_gate["ndp_root_toplevel_unchanged"],
        "generated_source_bound_identity_exact": generated_exact,
        "production_compile_pass": compile_pass,
        "simulation_started_then_external_int": simulation_started and interrupted,
        "post_sim_core_and_plugins_pass": core_status["return_publication_independent_of_plugin_success"] and plugins_pass,
        "source_bound_lifetime_signature_exact": p30_signature,
        "final_state_evidence_escape_exact": evidence_escape,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())
    status = "P30_PARTIAL_INTERRUPTED_FINAL_BANK_STATE_EVIDENCE_ESCAPE_SUCCESSOR_REQUIRED" if valid else "RETURN_VALIDATION_FAILED"
    report = {
        "schema": "conv-native-four-lane-0ccae916-p30-return-analysis-v1",
        "status": status,
        "valid": valid,
        "classification": "PARTIAL_INTERRUPTED_WITH_QUALIFIED_PROGRESS_AND_OBSERVER_STATE_ESCAPE" if valid else "RETURN_VALIDATION_FAILED",
        "return_identity": {
            "path": str(RETURN_ZIP),
            "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha_file(RETURN_ZIP),
            "execution_id": EXECUTION_ID,
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha_file(SOURCE_ZIP),
            "source_manifest_sha256": sha_bytes(source_payloads["package_manifest.json"]),
        },
        "internal_receipt": {
            "return_root": return_root,
            "return_file_count": len(records),
            "source_root": source_root,
            "source_file_count": len(source_records),
            "return_errors": return_errors,
            "source_errors": source_errors,
            "missing": sorted(expected - set(records)),
            "extra": sorted(set(records) - expected),
            "core_receipt_mismatches": receipt_mismatches,
            "plugin_status_mismatches": plugin_mismatches,
            "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "sim_exit_code": sim_exit["sim_exit_code"],
            "compile_succeeded": compile_pass,
            "dut_simulation_started": simulation_started,
            "natural_terminal": False,
            "c0_slice_finish": False,
            "formal_D_payload_present": False,
            "post_sim_core_disposition": core["disposition"],
            "all_plugins_pass": plugins_pass,
            "interruption_adjudication": "INT after qualified c0 progress; absence of terminal/D is not a DUT, config, RTL or numeric failure.",
        },
        "production_rtl_identity": {
            "collection_valid": identity.get("collection_valid"),
            "actual_differs_cloud_authority": identity.get("actual_differs_cloud_authority"),
            "identity_difference_blocks_simulator": False,
            "buffer_leaf": identity.get("leaves", {}).get("Buffer.sv"),
            "memory_req_manager_leaf": identity.get("leaves", {}).get("Memory_Req_Manager.sv"),
            "causal_cone_adjudication": "Actual production Buffer/Memory_Req_Manager bytes differ from local/cloud provenance, but compile and c0 simulation succeeded. The difference is nonblocking provenance; exact dynamic evidence remains authoritative.",
        },
        "source_bound_bank_evidence": {
            "decision": decision,
            "target_arm_rows": target_arm,
            "target_arm_payloads_decoded": arm_payloads,
            "target_mrm_payloads_decoded": mrm_payloads,
            "last_target_arm_record": last_target_arm,
            "final_summary_absent": final_summary_absent,
            "final_ring_absent": final_ring_absent,
            "stall_payload_zero": stall_payload_zero,
            "public_prior_row2_clear": prior_clear,
            "public_final_block_start_cycle": final_block_start,
            "public_final_block_last": final_blocked[-1],
            "adjudication": "p30 proves row2 blocked/accepted epochs and observed 0x0f->0xff recovery on earlier row2 epochs. The final held row2 epoch begins after cycle-150 clear, but INT prevents final/ring publication and the only stall record hard-codes payload=0; sticky mask 0x2b is lifetime-OR, not the current final bank vector.",
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": "production compile and c0 simulation; source-bound generated observer active; earlier row2 blocked bank_ready=0x0f followed by accepted bank_ready=0xff; final public row2 clear at cycle 150; final same-tag row2 request enters sustained block at cycle 151",
            "FIRST_DIVERGENCE": "required final-bank adjudication at the sustained cycle-151 row2 block: exact current bank vector was not published before INT",
            "HANG_ROOT_CAUSE": {
                "status": "DUT_ROOT_UNRESOLVED_OBSERVER_EVIDENCE_ESCAPE",
                "classification": "PACKAGE_LOCAL_NON_PROGRESS_CURRENT_STATE_NOT_SIGNAL_SAFE",
                "closed": ["production compile/XMR failure", "c0 not reached", "bank-ready never recovers on earlier row2 epochs"],
                "remaining_observational_equivalents": [
                    "the final post-clear row2 remains bank_ready=0x0f because one half-bank validity owner remains live",
                    "the final post-clear row2 reaches bank_ready=0xff while aggregate buf2arm_req_ready remains low",
                ],
                "functional_rtl_root_cause_proven": False,
                "authorized_config_fix": None,
            },
        },
        "result_conjunction": {
            "compile": compile_pass,
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
                "B_CONV_NATIVE_P30_PRODUCTION_COMPILE_UNPROVEN",
                "B_CONV_NATIVE_P30_SOURCE_BOUND_GENERATION_UNPROVEN",
                "B_CONV_NATIVE_P30_POST_SIM_CORE_UNPROVEN",
            ],
            "added": {
                "B_CONV_NATIVE_P30_FINAL_BANK_STATE_SIGNAL_SAFE_EVIDENCE_ESCAPE": "stall payload is zero and final/ring state is absent on INT",
            },
            "preserved": [
                "B_CONV_NATIVE_BUFFER5_POST_ROW2_CLEAR_VALID_OWNERSHIP_UNRESOLVED",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid,
            "package_id": "r5_n4_0cc_p31_postclear",
            "fresh_identity": True,
            "highest_information_scope": "source-bound candidate-decomposed immediate triggers for blocked row2 bank_ready=00/0f/f0/ff/other plus Array_Request_Manager same-bit final-row2 marker; every required state is published when first true rather than deferred to SystemVerilog final",
            "first_fresh_epoch": "20260810-first-fresh-extra-audit-v1",
            "first_fresh_after_change": True,
            "frozen": "87 payload members, numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/functional RTL",
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {"bytes": (ROOT / path).stat().st_size, "sha256": sha_file(ROOT / path)}
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
                "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
            ],
            "delta": None,
            "claim_boundary": "Current rules already require signal/exit-safe bounded state evidence; p31 fixes the family plan with immediate candidate triggers rather than changing public rules.",
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {OUTPUT}")
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": status, "valid": valid, "output": str(OUTPUT)}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
