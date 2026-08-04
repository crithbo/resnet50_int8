from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import analyze_node0004_v14_return as common


EXPECTED_RETURN_SHA256 = (
    "c064ea3a88bbba648f2d9fedb4cf8c1f833680711820014d62a2013bb3fa69c0"
)
EXPECTED_RETURN_BYTES = 77452
EXPECTED_SOURCE_SHA256 = (
    "aa12edc55f10e28133e843e3ddeff832831a8d8c71cef47c5bc69e7c48f73fc1"
)
EXPECTED_INSTALL_NAME = "r5_n4_hw_v18_a_reuse_diag"
EXPECTED_OBSERVER_SHA256 = (
    "db36700079225c70b2811f674791a2fd9d08aa3878f85f7bfd6e8d879c03172b"
)
EXPECTED_FINAL_AUDIT_SHA256 = (
    "e0b07aff542dadccaabbc1269c794220dd86d622ddd275ca8b4085aadb0fa08d"
)
CURRENT_SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)


def parse_kv(line: str) -> dict[str, str]:
    return {
        key: value
        for key, value in re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line)
    }


def analyze(
    return_zip: Path,
    sidecar: Path,
    source_zip: Path,
    final_audit: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    return_sha = common.sha256_file(return_zip)
    return_bytes = return_zip.stat().st_size
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    sidecar_valid = (
        len(sidecar_tokens) == 2
        and sidecar_tokens[0] == return_sha
        and sidecar_tokens[1] == return_zip.name
    )
    source_sha = common.sha256_file(source_zip)
    final_audit_sha = common.sha256_file(final_audit)
    if return_sha != EXPECTED_RETURN_SHA256 or return_bytes != EXPECTED_RETURN_BYTES:
        errors.append("return ZIP identity differs")
    if not sidecar_valid:
        errors.append("external sidecar differs")
    if source_sha != EXPECTED_SOURCE_SHA256:
        errors.append("source ZIP identity differs")
    if final_audit_sha != EXPECTED_FINAL_AUDIT_SHA256:
        errors.append("source final-ZIP audit identity differs")

    root, payloads = common.entries(return_zip)
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    records = {item["path"]: item for item in allowlist["records"]}
    observed = {
        relative: payload
        for relative, payload in payloads.items()
        if relative != "RETURN_ALLOWLIST.json"
    }
    exact_set = set(records) == set(observed)
    mismatched_records: list[str] = []
    for relative in sorted(set(records) & set(observed)):
        record = records[relative]
        payload = observed[relative]
        if (
            record["size_bytes"] != len(payload)
            or record["sha256"] != common.sha256_bytes(payload)
        ):
            mismatched_records.append(relative)
    if not exact_set:
        errors.append("return exact-set differs from allowlist")
    if mismatched_records:
        errors.append("return allowlist hashes/sizes differ")

    _, source_payloads = common.entries(source_zip)
    manifest = json.loads(source_payloads["package_manifest.json"])
    package_preflight = json.loads(observed["evidence/package_preflight.json"])
    install_preflight = json.loads(observed["evidence/install_preflight.json"])
    observer_precompile = json.loads(
        observed["evidence/observer_precompile.json"]
    )
    gate = json.loads(observed["evidence/SERVER_RESULT_GATE.json"])
    source_audit = json.loads(final_audit.read_text(encoding="utf-8"))
    compile_status = int(
        observed["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        observed["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = observed["evidence/signal_status.txt"].decode().strip()
    compile_log = observed[
        "runs/compile/sim_results/compile.log"
    ].decode("utf-8", errors="replace")
    driver_log = observed[
        "runs/compile/sim_results/compile_driver.log"
    ].decode("utf-8", errors="replace")
    sim_log = observed["runs/c0/sim.log"].decode("utf-8", errors="replace")
    sim_argv = observed["runs/c0/simulator_argv.txt"].decode().strip()
    observer_log = observed["runs/c0/return_observer.log"].decode(
        "utf-8", errors="replace"
    )
    host_progress = observed["runs/c0/host_progress.log"].decode(
        "utf-8", errors="replace"
    )

    identity_valid = (
        allowlist.get("install_name") == EXPECTED_INSTALL_NAME
        and manifest.get("install_name") == EXPECTED_INSTALL_NAME
        and manifest.get("classification")
        == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        and package_preflight.get("install_name") == EXPECTED_INSTALL_NAME
        and manifest.get("observer_sha256") == EXPECTED_OBSERVER_SHA256
        and package_preflight.get("observer_sha256")
        == EXPECTED_OBSERVER_SHA256
        and observer_precompile.get("expected_sha256")
        == EXPECTED_OBSERVER_SHA256
        and observer_precompile.get("observed_sha256")
        == EXPECTED_OBSERVER_SHA256
    )
    preflight_valid = (
        package_preflight.get("valid") is True
        and install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
        and observer_precompile.get("valid") is True
        and observer_precompile.get("identity_match") is True
        and observer_precompile.get("expected_identity_source", "").startswith(
            "package_manifest.json:"
        )
        and observer_precompile.get("xmr_static_gate", {}).get("status")
        == "pass"
        and observer_precompile.get("xmr_static_gate", {}).get(
            "runtime_indexed_generated_instance_reference_count"
        )
        == 0
    )
    source_audit_valid = (
        source_audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is True
        and source_audit.get("error_count") == 0
        and source_audit.get("all_required_negative_controls_fail_closed")
        is True
        and source_audit.get("zip", {}).get("sha256")
        == EXPECTED_SOURCE_SHA256
        and source_audit.get("rule_receipts", {})
        .get(".agents/rules/服务器测试包生成规则.md", {})
        .get("observed_sha256")
        == CURRENT_SERVER_RULE_SHA256
    )
    if not identity_valid:
        errors.append("package/install/observer identity differs")
    if not preflight_valid:
        errors.append("package/install/observer preflight differs")
    if not source_audit_valid:
        errors.append("source final-ZIP current-rule audit differs")

    compile_valid = (
        compile_status == 0
        and "Error-[SE]" not in compile_log
        and "CPU time:" in compile_log
        and "seconds to elab" in compile_log
        and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in driver_log
        and f"+incdir+/home/panqs/ndp/{EXPECTED_INSTALL_NAME}/tb_probe"
        in driver_log
    )
    runtime_binding_valid = all(
        item in sim_argv
        for item in (
            "+RETURN_OBSERVER",
            "+RETURN_OBS_DEEP",
            "+RETURN_OBS_ABPE",
            "+RETURN_HANG_DIAG",
            "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
            "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
        )
    ) and "[RETURN_OBSERVER] enabled for slice 0" in sim_log
    canonical_lines = [
        line
        for line in observer_log.splitlines()
        if " | CANONICAL_DIAG_DECISION_V1 | " in line
    ]
    progress_lines = [
        line
        for line in observer_log.splitlines()
        if " | PROGRESS_WINDOW | " in line
    ]
    abpe_lines = [
        line
        for line in observer_log.splitlines()
        if " | ABPE_BOUNDARY_V1 | " in line
    ]
    a_reuse_lines = [
        line
        for line in observer_log.splitlines()
        if " | A_REUSE_BOUNDARY_V1 | " in line
    ]
    canonical = parse_kv(canonical_lines[0]) if len(canonical_lines) == 1 else {}
    abpe = parse_kv(abpe_lines[0]) if len(abpe_lines) == 1 else {}
    a_reuse = (
        parse_kv(a_reuse_lines[0]) if len(a_reuse_lines) == 1 else {}
    )
    progress = [parse_kv(line) for line in progress_lines]
    canonical_valid = (
        len(canonical_lines) == 1
        and gate.get("canonical_validation", {}).get("valid") is True
        and gate.get("canonical_validation", {}).get("candidate_count") == 1
        and canonical.get("decision")
        == "LONG_RUNNING_HANG_AT_BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS"
        and canonical.get("reason") == "STALL_WINDOW_EXCEEDED"
        and canonical.get("no_progress_windows") == "4"
        and canonical.get("qualified_delta") == "0"
    )
    qualified_sequence = [
        int(item["qualified_progress"]) for item in progress
    ]
    delta_sequence = [int(item["delta"]) for item in progress]
    progress_valid = (
        len(progress) == 5
        and qualified_sequence == [144, 144, 144, 144, 144]
        and delta_sequence == [144, 0, 0, 0, 0]
        and "last_progress=" in host_progress
    )
    abpe_valid = (
        len(abpe_lines) == 1
        and abpe.get("a_group_accept") == "1"
        and abpe.get("b_group_accept") == "1"
        and abpe.get("c_group_accept") == "8"
        and abpe.get("alu_accept") == "64"
        and abpe.get("pe_out_accept") == "0"
        and abpe.get("sa_group_out_accept") == "0"
        and abpe.get("masked_a") == "0x0"
        and abpe.get("masked_b") == "0xffffffffffffffff"
    )
    a_reuse_valid = (
        len(a_reuse_lines) == 1
        and a_reuse.get("req_accept0") == "2"
        and a_reuse.get("req_accept1") == "0"
        and a_reuse.get("data_accept0") == "2"
        and a_reuse.get("data_accept1") == "0"
        and a_reuse.get("buf_read0") == "1"
        and a_reuse.get("buf_read1") == "0"
        and a_reuse.get("mem_clear0") == "0"
        and a_reuse.get("mem_clear1") == "0"
        and a_reuse.get("array_clear0") == "0"
        and a_reuse.get("array_clear1") == "0"
        and a_reuse.get("sa_src_accept0") == "1"
        and a_reuse.get("sa_src_accept1") == "0"
        and a_reuse.get("alu2ob_cycles") == "1"
        and a_reuse.get("mse0_req_sel") == "0x1"
        and a_reuse.get("sa_src_sel") == "0"
        and a_reuse.get("buf0_rtag") == "0x5"
        and a_reuse.get("buf1_rtag") == "0x0"
        and a_reuse.get("pipeline0_valid") == "0x0"
        and a_reuse.get("alu2ob_write") == "0x0"
        and a_reuse.get("psum_ready") == "0xffffffffffffffff"
    )
    dynamic_valid = (
        compile_valid
        and run_status == 0
        and signal_status == "NONE"
        and runtime_binding_valid
        and canonical_valid
        and progress_valid
        and abpe_valid
        and a_reuse_valid
    )
    if not dynamic_valid:
        errors.append("compile/runtime/canonical/A_REUSE dynamic evidence differs")

    formal_d_members = sorted(
        name for name in observed if name.startswith("runs/c0/formal_d/")
    )
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_claimed = gate.get("formal_readback_claimed") is True
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal_status == "NONE"
        and natural_terminal
        and formal_claimed
        and len(formal_d_members) == 320
    )
    if joint_gate:
        errors.append("unexpected E4/E5 pass in diagnostic hang return")

    return {
        "schema": "node0004-v18-return-analysis-v1",
        "status": (
            "LONG_RUNNING_HANG_AT_BUFFER0_POST_FIRST_READ"
            if not errors
            else "RETURN_IDENTITY_OR_CONTRACT_FAILURE"
        ),
        "valid": not errors,
        "errors": errors,
        "identity": {
            "return_zip": str(return_zip.resolve()),
            "return_zip_bytes": return_bytes,
            "return_zip_sha256": return_sha,
            "sidecar": str(sidecar.resolve()),
            "sidecar_sha256": common.sha256_file(sidecar),
            "sidecar_valid": sidecar_valid,
            "source_zip": str(source_zip.resolve()),
            "source_zip_sha256": source_sha,
            "install_name": allowlist.get("install_name"),
            "identity_valid": identity_valid,
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
            "source_final_audit": str(final_audit.resolve()),
            "source_final_audit_sha256": final_audit_sha,
            "source_final_audit_valid": source_audit_valid,
        },
        "return_envelope": {
            "crc_pass": True,
            "single_root": root,
            "entry_count": len(payloads),
            "exact_set_valid": exact_set,
            "allowlist_record_count": len(records),
            "hash_size_mismatches": mismatched_records,
        },
        "preflight": {
            "valid": preflight_valid,
            "package": package_preflight,
            "install": install_preflight,
            "observer": observer_precompile,
        },
        "dynamic": {
            "compile_exit_status": compile_status,
            "compile_valid": compile_valid,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "runtime_binding_valid": runtime_binding_valid,
            "simulation_started": True,
            "diagnostic_fatal_terminal": True,
            "natural_terminal": natural_terminal,
            "canonical_valid": canonical_valid,
            "canonical": canonical,
            "qualified_progress_sequence": qualified_sequence,
            "qualified_delta_sequence": delta_sequence,
            "abpe_valid": abpe_valid,
            "abpe": abpe,
            "a_reuse_valid": a_reuse_valid,
            "a_reuse": a_reuse,
            "formal_d_member_count": len(formal_d_members),
            "formal_d_readback": formal_claimed,
            "mismatch_zero_with_all_missing_is_pass": False,
        },
        "first_divergence": {
            "last_good": (
                "MSE0 accepted two request/data transfers into Buffer0; "
                "Buffer0 supplied one qualified A read; SA source0 accepted "
                "it and all 64 ALUs wrote one result to their outbuffers"
            ),
            "first_bad": (
                "after the first Buffer0 read, no second Buffer0/1 read or "
                "SA inport0 acceptance occurs; Buffer0 presents no valid "
                "bank bits (rtag=0x5) while the producer and consumer both "
                "remain selected on source0"
            ),
            "boundary": (
                "BUFFER0_FIRST_READ_TO_BUFFER0_NEXT_ROW_VALID_OR_READ"
            ),
            "selector_adjudication": (
                "mse0_req_sel=0x1 and sa_src_sel=0 prove producer/consumer "
                "selector alignment at the decision; the prior selector "
                "divergence hypothesis is excluded"
            ),
        },
        "hang_root_cause": {
            "classification": "UNRESOLVED_BUFFER0_VALID_LIFETIME_SUBBOUNDARY",
            "known_failed_interval": (
                "MSE0 WR_Buffer_AG next row/request -> Buffer0 valid/full "
                "state -> Array_Request_Manager next address/read"
            ),
            "proved": [
                "two 16-byte MSE0 payloads reached Buffer0",
                "one Buffer0-to-SA read and one ALU-to-outbuffer write occurred",
                "producer and SA consumer both select source0 at the stall",
                "no Buffer0/1 clear edge occurred before the stall",
                "final Buffer0 rtag contains last_index=5 but no valid bank bits",
            ],
            "excluded": [
                "package/compile/observer/runtime binding failure",
                "producer/consumer ping-pong selector divergence",
                "SA inport0 accepting data but PE pipeline rejecting it",
                "PE outbuffer unable to accept the first product",
                "tail, later stage barrier, formal-D comparison",
            ],
            "single_missing_runtime_boundary": [
                "MSE0 WR_Buffer_AG queue count/current row/valid/ready",
                "Buffer0 per-row valid bits and mrm/arm ready",
                "Buffer0 Array_Request_Manager address/lifetime counters",
            ],
            "functional_rtl_implicated": False,
            "configuration_error_proven": False,
            "successor_allowed": True,
            "successor_scope": (
                "one diagnostic-only record for MSE0 WR_Buffer_AG -> "
                "Buffer0 row-valid/full -> Array_Request_Manager address/life"
            ),
        },
        "evidence_levels": {
            "E3": True,
            "E4": False,
            "E5": False,
            "joint_gate_passed": joint_gate,
            "reason": (
                "compile and diagnostic simulation are bound, but no natural "
                "terminal or 320-item formal D readback exists"
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "frozen_source_consumed_read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--final-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(
        args.return_zip, args.sidecar, args.source_zip, args.final_audit
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
