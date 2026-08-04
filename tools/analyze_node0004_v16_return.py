from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import analyze_node0004_v14_return as common


EXPECTED_RETURN_SHA256 = (
    "561e29d888b8970d44ff90405d8709cc6e9aae63393d02261652aa5ff7888d4f"
)
EXPECTED_RETURN_BYTES = 77352
EXPECTED_SOURCE_SHA256 = (
    "e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1"
)
EXPECTED_INSTALL_NAME = "r5_n4_hw_v16_abpe_runnerpc"
EXPECTED_OBSERVER_SHA256 = (
    "61dd2dd47558672b4929b8cd30b9147fa3a68c1a12e67dfa4865b33f8e4fb3ee"
)
CURRENT_SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
EXPECTED_DRIFT_RECEIPT_SHA256 = (
    "cfc12f55e51eed1e4deb865a13d58170720bddc56007298caf4acccad659a23b"
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
    drift_receipt: Path,
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
    drift_sha = common.sha256_file(drift_receipt)
    if return_sha != EXPECTED_RETURN_SHA256 or return_bytes != EXPECTED_RETURN_BYTES:
        errors.append("return ZIP identity differs")
    if not sidecar_valid:
        errors.append("external sidecar differs")
    if source_sha != EXPECTED_SOURCE_SHA256:
        errors.append("source ZIP identity differs")
    if drift_sha != EXPECTED_DRIFT_RECEIPT_SHA256:
        errors.append("current-rule drift receipt identity differs")

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
    drift = json.loads(drift_receipt.read_text(encoding="utf-8"))
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
    )
    drift_valid = (
        drift.get("status") == "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"
        and drift.get("current_server_rule_sha256")
        == CURRENT_SERVER_RULE_SHA256
        and drift.get("final_zip", {}).get("sha256_before")
        == EXPECTED_SOURCE_SHA256
        and drift.get("final_zip", {}).get("sha256_after")
        == EXPECTED_SOURCE_SHA256
    )
    if not identity_valid:
        errors.append("package/install/observer identity differs")
    if not preflight_valid:
        errors.append("package/install/observer preflight differs")
    if not drift_valid:
        errors.append("current-rule content-neutral revalidation differs")

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
    canonical = parse_kv(canonical_lines[0]) if len(canonical_lines) == 1 else {}
    abpe = parse_kv(abpe_lines[-1]) if abpe_lines else {}
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
        abpe.get("a_group_accept") == "1"
        and abpe.get("b_group_accept") == "1"
        and abpe.get("c_group_accept") == "8"
        and abpe.get("alu_accept") == "64"
        and abpe.get("pe_out_accept") == "0"
        and abpe.get("sa_group_out_accept") == "0"
        and abpe.get("masked_a") == "0x0"
        and abpe.get("masked_b") == "0xffffffffffffffff"
    )
    dynamic_valid = (
        compile_valid
        and run_status == 0
        and signal_status == "NONE"
        and runtime_binding_valid
        and canonical_valid
        and progress_valid
        and abpe_valid
    )
    if not dynamic_valid:
        errors.append("compile/runtime/canonical/ABPE dynamic evidence differs")

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
        "schema": "node0004-v16-return-analysis-v1",
        "status": (
            "LONG_RUNNING_HANG_AFTER_FIRST_SA_OPERAND_ACCEPT"
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
            "current_rule_drift_receipt": str(drift_receipt.resolve()),
            "current_rule_drift_receipt_sha256": drift_sha,
            "current_rule_drift_valid": drift_valid,
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
            "formal_d_member_count": len(formal_d_members),
            "formal_d_readback": formal_claimed,
            "mismatch_zero_with_all_missing_is_pass": False,
        },
        "first_divergence": {
            "last_good": (
                "MSE0/1/3 returned data; A/B/C each reached SA; 64 PE "
                "operand accepts prove one complete A/B product issue"
            ),
            "first_bad": (
                "after that issue, A is absent while B remains held; no "
                "second PE operand accept, PE output, SA group output, or "
                "Buffer5 write occurs for four qualified windows"
            ),
            "boundary": (
                "MSE0_RETURN_TO_BUFFER0_1_TO_SA_INPORT0_SECOND_ACCEPT"
            ),
            "not_transout_last_index_error": (
                "transout_last_index=2 intentionally accumulates upstream "
                "last_index>2; no PE output after only the first product is "
                "not by itself a transout failure"
            ),
        },
        "hang_root_cause": {
            "classification": "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT",
            "known_failed_interval": (
                "A producer/Buffer0-1/SA-inport0 delivery and reuse after "
                "the first matched product"
            ),
            "excluded": [
                "compile or observer binding failure",
                "external timeout without an internal stall",
                "absence of initial A/B/C delivery",
                "normal transout_last_index=2 accumulation semantics",
                "tail, later stage barrier, or formal-D comparison",
            ],
            "missing_runtime_discriminator": [
                "MSE0 producer ping-pong selector and accepted writes per Buffer0/1",
                "Buffer0/1 valid/full/clear/lifetime state",
                "SA inport0 selected source and accepted events per source",
                "PE pipeline0 and ALU-to-outbuffer write handshake",
            ],
            "functional_rtl_implicated": False,
            "configuration_error_proven": False,
        },
        "evidence_levels": {
            "E3": True,
            "E4": False,
            "E5": False,
            "joint_gate_passed": joint_gate,
            "reason": (
                "bound compile and simulation/observer execution exist, but "
                "the DUT did not reach natural terminal and no 320-item "
                "formal D readback exists"
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_source_consumed_read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--drift-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(
        args.return_zip, args.sidecar, args.source_zip, args.drift_receipt
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
