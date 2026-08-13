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


INSTALL = "r5_n4_hw_v72_token_origin_accept_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "d645137a8fb4e099061dd5591a1024c3bedff8749b15636d526c8f0d2bd24696"
SOURCE_SHA = "1cd8c9f55f8120e0c40599c54f6f385fbf159957bf74eafa0055c0ad4feed585"
EXECUTION = "r1786210517441748871_19603"


def rows(text: str, marker: str) -> list[dict[str, str]]:
    return [
        dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
        for line in text.splitlines()
        if marker in line
    ]


def num(row: dict[str, str], key: str, base: int = 10) -> int:
    try:
        return int(row.get(key, "-1"), base)
    except ValueError:
        return -1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []

    return_sha = sha256_file(args.return_zip)
    source_sha = sha256_file(args.source_zip)
    if return_sha != RETURN_SHA:
        errors.append("return_sha256_mismatch")
    if source_sha != SOURCE_SHA:
        errors.append("source_sha256_mismatch")

    returned, return_errors, return_meta = safe_entries(args.return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(args.source_zip, INSTALL)
    errors.extend(return_errors)
    errors.extend(source_errors)

    allowlist = load_json(returned, "RETURN_ALLOWLIST.json")
    return_manifest = load_json(returned, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipt_errors: list[str] = []
    for record in records:
        path = record.get("path")
        expected.add(path)
        data = returned.get(path)
        if data is None:
            receipt_errors.append(f"missing:{path}")
        elif len(data) != record.get("size_bytes"):
            receipt_errors.append(f"size:{path}")
        elif sha256_bytes(data) != record.get("sha256"):
            receipt_errors.append(f"sha256:{path}")
    exact_set = set(returned) == expected
    if not exact_set:
        errors.append("return_exact_set_mismatch")
    errors.extend(receipt_errors)

    package_manifest_bytes = source.get("package_manifest.json", b"")
    package_manifest = json.loads(package_manifest_bytes or b"{}")
    source_binding = (
        returned.get("evidence/returned_package_manifest.json") == package_manifest_bytes
        and return_manifest.get("install_name") == INSTALL
        and return_manifest.get("records") == records
        and return_manifest.get("fixed_result_publication", {})
        .get("return_zip", "")
        .endswith(f"{INSTALL}_{EXECUTION}_return.zip")
    )
    source_exact_set = (
        set(package_manifest.get("files", {})) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in package_manifest.get("files", {}).items()
        )
    )
    if not source_binding:
        errors.append("source_or_execution_binding_mismatch")
    if not source_exact_set:
        errors.append("source_exact_set_mismatch")

    gate = load_json(returned, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(returned, "evidence/package_preflight.json")
    install_preflight = load_json(returned, "evidence/install_preflight.json")
    observer_precompile = load_json(returned, "evidence/observer_precompile.json")
    root_gate = load_json(returned, "evidence/ndp_root_toplevel_gate.json")
    publication = load_json(returned, "evidence/publication_preflight.json")
    feature_binding = load_json(returned, "evidence/diagnostic_feature_binding.json")
    compile_exit = integer_entry(returned, "evidence/compile_exit_status.txt", 125)
    run_exit = integer_entry(returned, "evidence/run_exit_status.txt", 125)
    signal = returned.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    observer = returned.get("runs/c0/return_observer.log", b"").decode(errors="replace")
    simulation = returned.get("runs/c0/sim.log", b"").decode(errors="replace")
    simulator_argv = returned.get("runs/c0/simulator_argv.txt", b"").decode(errors="replace")
    compile_driver = returned.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode(errors="replace")

    observer_sha = package_manifest.get("observer_sha256")
    preflight = {
        "package": package_preflight.get("valid") is True,
        "install_reset": install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True,
        "root_direct_set": root_gate.get("valid") is True
        and root_gate.get("ndp_root_toplevel_unchanged") is True,
        "publication": publication.get("publication_state")
        == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
        "observer": observer_precompile.get("valid") is True
        and observer_precompile.get("observed_sha256") == observer_sha
        and sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
        == observer_sha,
        "feature": feature_binding.get("valid") is True,
    }
    if not all(preflight.values()):
        errors.append("preflight_binding_failure")

    compile_ok = (
        compile_exit == 0
        and "vcs" in compile_driver.lower()
        and "Compilation completed!" in compile_driver
    )
    simulation_ok = (
        run_exit == 0
        and signal == "NONE"
        and "[RETURN_OBSERVER] enabled" in simulation
        and "+RETURN_OBS_TOKEN_ORIGIN_ACCEPT" in simulator_argv
    )
    if not compile_ok:
        errors.append("compile_binding_failure")
    if not simulation_ok:
        errors.append("simulation_binding_failure")

    token_rows = rows(observer, "TOKEN_ORIGIN_ACCEPT_EDGE_V2")
    qualification_errors: list[str] = []
    for index, row in enumerate(token_rows, 1):
        expected_mem_write = num(row, "mem_wr_attempt") == 1 and num(row, "mem_full") == 0
        expected_buf_write = num(row, "buf_wr_attempt") == 1 and num(row, "buf_full") == 0
        if (num(row, "mem_wr_ev") == 1) != expected_mem_write:
            qualification_errors.append(f"mem_write:{index}")
        if (num(row, "buf_wr_ev") == 1) != expected_buf_write:
            qualification_errors.append(f"buf_write:{index}")
    if qualification_errors:
        errors.append("accepted_write_qualification_mismatch")

    final_token = token_rows[-1] if token_rows else {}
    event_totals = {
        "mem_write_accept": num(final_token, "mem_wr"),
        "buffer_write_accept": num(final_token, "buf_wr"),
        "mem_pop_accept": num(final_token, "mem_pop"),
        "buffer_pop_accept": num(final_token, "buf_pop"),
        "descriptor_accept": num(final_token, "desc"),
    }
    expected_totals = {
        "mem_write_accept": 9,
        "buffer_write_accept": 27,
        "mem_pop_accept": 9,
        "buffer_pop_accept": 23,
        "descriptor_accept": 18,
    }
    token_acceptance_closed = (
        len(token_rows) == 35
        and not qualification_errors
        and event_totals == expected_totals
    )
    if not token_acceptance_closed:
        errors.append("v72_token_acceptance_evidence_mismatch")

    epoch_rows = rows(observer, "EPOCH_OWNER_V1")
    epoch_final = epoch_rows[-1] if epoch_rows else {}
    branch_rows = rows(observer, "BRANCH_OWNER_EDGE_V1")
    branch_state = rows(observer, "BRANCH_OWNER_STATE_V1")
    epoch_boundary_closed = (
        num(epoch_final, "desc_terminal") == 3
        and num(epoch_final, "desc") == 18
        and num(epoch_final, "prepared") == 20
        and num(epoch_final, "buf_push") == 27
        and num(epoch_final, "buf_pop") == 23
        and num(epoch_final, "valid", 16) == 1
        and num(epoch_final, "same", 16) == 1
        and num(epoch_final, "gotten", 16) == 7
        and num(epoch_final, "masked", 16) == 0
        and num(epoch_final, "match") == 0
        and num(epoch_final, "qempty") == 1
        and num(epoch_final, "idx1", 16) == 7
    )
    if not epoch_boundary_closed:
        errors.append("v72_epoch_boundary_mismatch")

    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_members = [
        path
        for path in returned
        if re.search(r"(^|/)formal.*D|formal_d|readback", path, re.I)
    ]
    formal_expected = 320
    formal_present = 0
    formal_missing = 320
    formal_mismatch = 0
    joint_gate = (
        compile_ok
        and simulation_ok
        and natural_terminal
        and formal_present == formal_expected
        and formal_missing == 0
        and formal_mismatch == 0
    )

    report = {
        "schema": "node0004-v72-token-origin-accept-return-analysis-v1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "identity": {
            "return_path": str(args.return_zip.resolve()),
            "return_bytes": args.return_zip.stat().st_size,
            "return_sha256": return_sha,
            "source_path": str(args.source_zip.resolve()),
            "source_bytes": args.source_zip.stat().st_size,
            "source_sha256": source_sha,
            "execution_id": EXECUTION,
            "expected_cloud_rtl": package_manifest.get("cloud_rtl_authority"),
        },
        "archive": {
            "return": return_meta,
            "source": source_meta,
            "return_crc": not return_errors,
            "return_exact_set": exact_set,
            "per_file_receipts": not receipt_errors,
            "source_binding": source_binding,
            "source_exact_set": source_exact_set,
        },
        "preflight": preflight,
        "runtime": {
            "compile_exit": compile_exit,
            "run_exit": run_exit,
            "signal": signal,
            "compile_bound": compile_ok,
            "simulation_bound": simulation_ok,
            "canonical": gate.get("canonical_decision"),
        },
        "v71_escape_closure": {
            "closed": token_acceptance_closed,
            "qualified_record_count": len(token_rows),
            "budget_limit": 128,
            "qualification_errors": qualification_errors,
            "event_totals": event_totals,
            "proof": "Every accepted write equals wr_attempt && !queue_full; full-held attempts emit state but do not increment accepted-write progress.",
        },
        "causal_boundary": {
            "epoch_record_count": len(epoch_rows),
            "branch_record_count": len(branch_rows),
            "branch_state_count": len(branch_state),
            "epoch_final": epoch_final,
            "memory_queue_conservation": "9 accepted writes == 9 accepted pops; final empty",
            "buffer_queue_conservation": "27 accepted writes - 23 accepted pops = 4 resident tokens",
            "descriptor_and_prepared": "descriptor=18, prepared=20, descriptor terminal count=3",
            "adjudication": "v72 proves the four-token Buffer queue residue is real rather than a held-write observer artifact. At the final boundary Memory input1 remains index7 with valid/same/gotten/masked=0x1/0x1/0x7/0x0, match=0, queue empty, while Buffer accepted writes reach 27. The current records do not identify the exact source declaration and consumer predicate responsible for the post-terminal Buffer tokens versus the absent next Memory token.",
        },
        "last_proven_good": "V72_ACCEPTED_WRITE_QUALIFICATION_CLOSES_V71_ESCAPE_AND_MEMORY_QUEUE_DRAINS_9_OF_9",
        "first_divergence": "POST_DESCRIPTOR18_MEMORY_QUEUE_EMPTY_AT_INPUT1_INDEX7_WHILE_BUFFER_QUEUE_HAS_27_ACCEPTS_23_POPS_AND_FOUR_RESIDENT_TOKENS",
        "hang_root_cause": {
            "status": "UNRESOLVED_EXACT_SOURCE_TO_CONSUMER_TOKEN_OWNERSHIP",
            "classification": "MSE4_MEMORY_VS_BUFFER_POST_TERMINAL_EPOCH_SKEW",
            "reason": "Accepted-event accounting is now trustworthy, but the return observes queue-local attempts/accepts and snapshots rather than source-bound generated predicates from the exact producer declarations through both queue consumers. It cannot distinguish an early Buffer next-epoch token, stale/duplicate Buffer per-input state, or a missing/suppressed Memory input1 token.",
            "functional_rtl_root_proven": False,
            "authorized_config_fix": None,
        },
        "formal_result": {
            "natural_terminal": natural_terminal,
            "expected": formal_expected,
            "present": formal_present,
            "missing": formal_missing,
            "mismatch": formal_mismatch,
            "formal_member_paths": formal_members,
            "all_missing_is_not_numeric_pass": True,
            "joint_gate": joint_gate,
            "dynamic_run_bound": compile_ok and simulation_ok,
            "E3": joint_gate,
            "E4": joint_gate,
            "E5": False,
        },
        "successor_candidate": {
            "required": not joint_gate,
            "publish_blocked_until_current_rule_sync": True,
            "required_rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
            "highest_information_scope": "Generate, do not hand-write, one exact-source-bound same-clock ledger spanning the producer declarations feeding MSE4 Memory input1 and Buffer row/column inputs, their mode/keep/valid/matched predicates, accepted queue writes, queue pops, descriptor join and terminal ownership. Bind generation and exact regeneration in the final ZIP.",
        },
        "blocker_delta": {
            "closed": ["B_CONV_NODE0004_V71_TOKEN_ORIGIN_WRITE_ATTEMPT_MISCOUNT"],
            "opened": ["B_CONV_NODE0004_POST_TERMINAL_SOURCE_TO_CONSUMER_TOKEN_OWNERSHIP_UNOBSERVED"],
            "remains": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": [
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ],
        },
        "frozen": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "golden_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
