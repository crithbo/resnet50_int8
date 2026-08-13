from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (  # noqa: E402
    integer_entry,
    load_json,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL_NAME = "r5_n4_hw_v47_lc9_split_cloudrtl"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "d05cca4f9d823be3c9ff0b675b2a1601ce863f5075dc29ce057eac0371d3589c"
SOURCE_SHA256 = "516173e54132e2ee31cf2d4f750c46a595bb0bf31afb7f5b6661fc5a0ed6a015"
OBSERVER_SHA256 = "339b2cf53cda1482c9b9715f27f658fbe10bfaa9fb814295a399df52bb760eb5"


def parse_fields(line: str) -> dict[str, str]:
    return dict(re.findall(r"\b([A-Za-z][A-Za-z0-9_]*)=([^\s]+)", line))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    sidecar_valid = (
        args.source_sidecar.read_text(encoding="ascii").strip()
        == f"{source_sha}  {source_zip.name}"
    )
    if not sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors.extend(return_errors)
    errors.extend(source_errors)

    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    returned = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        if not (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        ):
            errors.append(f"return receipt differs: {path}")
    if set(entries) != expected:
        errors.append("return exact-set differs")

    source_manifest_payload = source.get("package_manifest.json", b"")
    returned_manifest_payload = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    if not (
        returned.get("install_name") == INSTALL_NAME
        and returned.get("records") == records
        and returned_manifest_payload == source_manifest_payload
    ):
        errors.append("return/source manifest binding differs")
    source_manifest = json.loads(source_manifest_payload or b"{}")
    source_files = source_manifest.get("files", {})
    if not (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    ):
        errors.append("source exact-set differs")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(entries, "evidence/observer_precompile.json")
    feature_binding = load_json(entries, "evidence/diagnostic_feature_binding.json")
    compile_status = integer_entry(entries, "evidence/compile_exit_status.txt", 125)
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    observer_log = entries.get("runs/c0/return_observer.log", b"").decode(
        "utf-8", errors="replace"
    )
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )

    package_ok = package_preflight.get("valid") is True
    install_ok = (
        install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
    )
    observer_ok = (
        observer_preflight.get("valid") is True
        and observer_preflight.get("observed_sha256") == OBSERVER_SHA256
        and sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
        == OBSERVER_SHA256
    )
    features_ok = (
        feature_binding.get("valid") is True
        and all(item.get("valid") is True for item in feature_binding.get("features", []))
    )
    compile_ok = (
        compile_status == 0
        and "0 error(s)" in compile_log
        and "vcs" in compile_driver.lower()
    )
    dynamic_ok = (
        run_status == 0
        and signal == "NONE"
        and "$finish at simulation time" in sim_log
        and "CANONICAL_DIAG_DECISION_V1" in observer_log
    )
    if not all([package_ok, install_ok, observer_ok, features_ok]):
        errors.append("preflight/observer/feature binding differs")
    if not compile_ok:
        errors.append("production compile evidence differs")
    if not dynamic_ok:
        errors.append("diagnostic simulation evidence incomplete")

    boundary_lines = [
        line
        for line in observer_log.splitlines()
        if "LC9_SPLIT_BOUNDARY_V1" in line
    ]
    edge_lines = [
        line for line in observer_log.splitlines() if "LC9_SPLIT_EDGE_V1" in line
    ]
    if len(boundary_lines) != 1:
        errors.append("LC9 split boundary uniqueness differs")
    boundary = parse_fields(boundary_lines[0]) if boundary_lines else {}
    edge_fields = [parse_fields(line) for line in edge_lines]
    bp_hex = boundary.get("lc9_bp", "0")
    try:
        bp_value = int(bp_hex, 16)
        zero_bp_bits = [bit for bit in range(33) if not ((bp_value >> bit) & 1)]
    except ValueError:
        zero_bp_bits = []
        errors.append("LC9 backpressure vector is not fully known")

    active_cycles = int(
        gate.get("canonical_decision", {}).get("numeric", {}).get(
            "window_cycles", 0
        )
    ) * int(
        gate.get("canonical_decision", {}).get("fields", {}).get(
            "window_last", "0"
        )
    )
    pe1_count = int(boundary.get("pe1_in2_accept", "-1"))
    observer_qualification_escape = (
        int(boundary.get("lc9_advance", "-1")) == 0
        and pe1_count > 1_000_000
        and active_cycles == 1_310_720
        and pe1_count == active_cycles - 3
    )
    actual_decode = {
        "zero_backpressure_bits": zero_bp_bits,
        "bit0": {
            "consumer": "LC7 source slot 8",
            "equation": "iga_lc_outport_bp_post[9][0] = iga_lc_inport_bp_pre[7][8]",
        },
        "bit26": {
            "consumer": "MSE3 memory-index source slot 5 input 2",
            "equation": "iga_lc_outport_bp_post[9][26] = se2iga_mem_bp_pre[3][5][2]",
        },
    }
    local_boundary_not_closed = (
        zero_bp_bits == [0, 26]
        and observer_qualification_escape
        and int(boundary.get("lc9_advance", "-1")) == 0
        and int(boundary.get("lc9_last0", "-1")) == 0
    )
    if not local_boundary_not_closed:
        errors.append("LC9 actual-consumer adjudication differs")

    formal_expected = int(gate.get("formal_d_expected", 320))
    formal_present = int(gate.get("formal_d_present", 0))
    formal_missing = int(gate.get("formal_d_missing", formal_expected))
    formal_mismatch = int(gate.get("formal_d_mismatch", 0))
    natural_terminal = gate.get("natural_terminal_observed") is True

    report = {
        "schema": "node0004-v47-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "LC9_SPLIT_OBSERVER_MISBOUND_ACTUAL_CONSUMERS_UNRESOLVED",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_valid": sidecar_valid,
            },
            "return_meta": return_meta,
            "source_meta": source_meta,
            "checks": {
                "return_crc_path_root": not return_errors,
                "return_exact_set_allowlist_receipts": set(entries) == expected,
                "return_source_manifest_binding": (
                    returned_manifest_payload == source_manifest_payload
                ),
                "package_preflight": package_ok,
                "install_preflight_runtime_d_absent": install_ok,
                "observer_precompile_identity": observer_ok,
                "diagnostic_feature_binding": features_ok,
                "production_vcs_compile": compile_ok,
                "diagnostic_simulation_started": dynamic_ok,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "natural_terminal": natural_terminal,
            "formal_d_expected": formal_expected,
            "formal_d_present": formal_present,
            "formal_d_missing": formal_missing,
            "formal_d_mismatch": formal_mismatch,
            "joint_result_gate": (
                compile_status == 0
                and run_status == 0
                and natural_terminal
                and formal_present == formal_expected
                and formal_missing == 0
                and formal_mismatch == 0
            ),
            "E3": compile_status == 0 and dynamic_ok,
            "E4": (
                natural_terminal
                and formal_present == formal_expected
                and formal_missing == 0
                and formal_mismatch == 0
            ),
            "E5": False,
        },
        "qualified_chronology": {
            "edge_record_count": len(edge_lines),
            "lc9_advance": int(boundary.get("lc9_advance", "-1")),
            "lc9_last0": int(boundary.get("lc9_last0", "-1")),
            "reported_pe1_in2_accept": pe1_count,
            "canonical_active_cycles": active_cycles,
            "observer_pe1_counter_is_held_level_not_transaction": (
                observer_qualification_escape
            ),
            "mem1_accept_observed_wrong_branch": int(
                boundary.get("mem1_accept", "-1")
            ),
            "row4_accept_observed_nonblocking_branch": int(
                boundary.get("row4_accept", "-1")
            ),
            "final_lc9_port": boundary.get("lc9_port"),
            "final_lc9_bp": bp_hex,
            "actual_consumer_decode": actual_decode,
            "first_edge": edge_fields[0] if edge_fields else {},
            "last_edge": edge_fields[-1] if edge_fields else {},
        },
        "LAST_PROVEN_GOOD": (
            "LC9_VALID_HELD_AND_NONBLOCKING_BRANCHES_CAPTURE_WHILE_"
            "GLOBAL_LC9_ADVANCE_REMAINS_ZERO"
        ),
        "FIRST_DIVERGENCE": (
            "LC9_ACTUAL_BACKPRESSURE_BITS_0_AND_26_DEASSERT_AT_LC7_"
            "SOURCE8_AND_MSE3_SOURCE5_INPUT2"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "PACKAGE_OBSERVER_CAUSAL_CONSUMER_MISBIND_REQUIRES_FRESH_DIAGNOSTIC",
            "mechanism": (
                "v47 sampled PE1 source index 9, MSE4 input1 and ROW4, but "
                "the final LC9 backpressure vector has only bits 0 and 26 "
                "low. The interconnect equations decode those bits to LC7 "
                "source slot8 and MSE3 source slot5/input2. In addition, "
                "pe1_in2_accept was counted as LC9-valid AND a single branch "
                "ready, so a held valid level produced 1,310,717 false "
                "transactions while global LC9 advance stayed zero."
            ),
            "functional_rtl_root_cause_proven": False,
            "configuration_root_cause_proven": False,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_V47_PRODUCTION_COMPILE_AND_FEATURE_BINDING",
            ],
            "opened": [
                "B_CONV_NODE0004_V47_LC9_OBSERVER_ACTUAL_CONSUMER_MISBIND",
            ],
            "refined": {
                "from": "B_CONV_NODE0004_SHARED_LC9_TO_MEMORY_AND_BUFFER_BRANCH_ACCEPT_UNOBSERVED",
                "to": "B_CONV_NODE0004_LC9_TO_LC7_AND_MSE3_ACTUAL_BRANCH_ACCEPT_UNOBSERVED",
            },
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
