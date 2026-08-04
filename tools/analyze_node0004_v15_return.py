from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import analyze_node0004_v14_return as prior


EXPECTED_RETURN_SHA256 = (
    "592d792e9f0d647f1a3d43bdc8b3a5bbffb1956d4ff908916d0f6d78cf9a94d2"
)
EXPECTED_RETURN_BYTES = 28328
EXPECTED_SOURCE_SHA256 = (
    "65e5b50b00046d662d219b71054f7f3f64c5794c98bf87dc134b5b3dd09a2130"
)
EXPECTED_INSTALL_NAME = "r5_n4_hw_v15_abpe_syntax_fix"
EXPECTED_OBSERVER_SHA256 = (
    "d4fad8b0bd85bdb3e6848c21c8809d3c05ceedfe668a417767bf5f267bcb3636"
)


def analyze(
    return_zip: Path,
    sidecar: Path,
    source_zip: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    return_sha = prior.sha256_file(return_zip)
    return_bytes = return_zip.stat().st_size
    if return_sha != EXPECTED_RETURN_SHA256:
        errors.append("return ZIP SHA differs")
    if return_bytes != EXPECTED_RETURN_BYTES:
        errors.append("return ZIP byte size differs")
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    sidecar_valid = (
        len(sidecar_tokens) == 2
        and sidecar_tokens[0] == return_sha
        and sidecar_tokens[1] == return_zip.name
    )
    if not sidecar_valid:
        errors.append("external sidecar differs")
    source_sha = prior.sha256_file(source_zip)
    if source_sha != EXPECTED_SOURCE_SHA256:
        errors.append("source package SHA differs")

    root, payloads = prior.entries(return_zip)
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    records = {item["path"]: item for item in allowlist["records"]}
    observed = {
        relative: payload
        for relative, payload in payloads.items()
        if relative != "RETURN_ALLOWLIST.json"
    }
    exact_set = set(records) == set(observed)
    if not exact_set:
        errors.append("return exact-set differs from allowlist")
    mismatched_records: list[str] = []
    for relative in sorted(set(records) & set(observed)):
        record = records[relative]
        payload = observed[relative]
        if (
            record["size_bytes"] != len(payload)
            or record["sha256"] != prior.sha256_bytes(payload)
        ):
            mismatched_records.append(relative)
    if mismatched_records:
        errors.append("return allowlist hashes/sizes differ")

    _, source_payloads = prior.entries(source_zip)
    manifest = json.loads(source_payloads["package_manifest.json"])
    source_observer = source_payloads[
        "tb_probe/native_return_observer.svh"
    ].decode("utf-8")
    package_preflight = json.loads(observed["evidence/package_preflight.json"])
    install_preflight = json.loads(observed["evidence/install_preflight.json"])
    observer_precompile = json.loads(
        observed["evidence/observer_precompile.json"]
    )
    gate = json.loads(observed["evidence/SERVER_RESULT_GATE.json"])
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
    )
    if not identity_valid:
        errors.append("package/install/observer identity differs")
    if not preflight_valid:
        errors.append("package/install/observer preflight differs")

    compile_match = bool(
        re.search(
            r"native_return_observer\.svh[\"'],\s*2433:"
            r"\s*token is 'end'",
            compile_log,
            flags=re.DOTALL,
        )
        and "keyword 'endtask' is missing" in compile_log
    )
    source_match = (
        "task automatic return_obs_write_abpe_state" in source_observer
        and re.search(
            r"task automatic return_obs_write_abpe_state.*?"
            r"\$fflush\(return_obs_fd\);.*?"
            r"\n\s*end\n\s*end\n\s*$",
            source_observer,
            flags=re.DOTALL,
        )
        is not None
        and "endtask" not in source_observer[
            source_observer.index(
                "task automatic return_obs_write_abpe_state"
            ):
        ]
    )
    if not compile_match or not source_match:
        errors.append("expected missing-endtask first divergence not proven")

    simulation_started = (
        compile_status == 0
        and "runs/c0/sim.log" in observed
        and "runs/c0/simulator_argv.txt" in observed
    )
    formal_d_members = sorted(
        name for name in observed if name.startswith("runs/c0/formal_d/")
    )
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal_status == "NONE"
        and gate.get("natural_terminal_observed") is True
        and gate.get("formal_readback_claimed") is True
        and bool(formal_d_members)
    )
    if joint_gate:
        errors.append("unexpected dynamic pass after compile failure")

    return {
        "schema": "node0004-v15-return-analysis-v1",
        "status": (
            "PACKAGE_LOCAL_OBSERVER_MISSING_ENDTASK_COMPILE_FAILURE"
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
            "sidecar_sha256": prior.sha256_file(sidecar),
            "sidecar_valid": sidecar_valid,
            "source_zip": str(source_zip.resolve()),
            "source_zip_sha256": source_sha,
            "install_name": allowlist.get("install_name"),
            "identity_valid": identity_valid,
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
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
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "simulation_started": simulation_started,
            "natural_terminal": gate.get("natural_terminal_observed", False),
            "canonical_progress_is_actual": False,
            "canonical_fallback_used": gate.get(
                "canonical_fallback_used", False
            ),
            "formal_d_member_count": len(formal_d_members),
            "formal_d_readback": gate.get("formal_readback_claimed", False),
            "mismatch_zero_with_all_missing_is_pass": False,
        },
        "first_divergence": {
            "boundary": "COMPILE_PACKAGE_LOCAL_RETURN_OBSERVER",
            "file": "tb_probe/native_return_observer.svh",
            "line": 2433,
            "tool": "VCS",
            "token": "end",
            "diagnostic": "keyword 'endtask' is missing",
            "source_mechanism": (
                "return_obs_write_abpe_state opens a task and an explicit "
                "begin block but closes both levels with end; the task "
                "declaration requires endtask"
            ),
            "compile_log_match": compile_match,
            "source_match": source_match,
            "driver_make_exit2": "make: ***" in driver_log,
        },
        "evidence_levels": {
            "E3": False,
            "E4": False,
            "E5": False,
            "joint_gate_passed": joint_gate,
            "reason": "compile failed before elaboration and simulation",
        },
        "adjudication": {
            "root_cause": "PACKAGE_LOCAL_READ_ONLY_OBSERVER_MISSING_ENDTASK",
            "functional_rtl_implicated": False,
            "conv_configuration_implicated": False,
            "legal_minimal_fix": (
                "replace only the final task-closing end with endtask in "
                "the package-local read-only observer"
            ),
            "successor_status": (
                "HOLD_PENDING_NEW_SERVER_RULE_SHA_AND_SINGLE_SOURCE_"
                "MANIFEST_BINDING"
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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.return_zip, args.sidecar, args.source_zip)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
