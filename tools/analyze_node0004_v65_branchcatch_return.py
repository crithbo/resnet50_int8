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


INSTALL = "r5_n4_hw_v65_branchcatch_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "55aa22054535bfe032b62639c36f67cf058b09e84752fe3eeef13a0d186dacd3"
SOURCE_SHA = "b78e3c7257a34e23fab6cf046922a488c8e1f17356d6dfa6df11234e882a3816"
EXECUTION = "r1786123560502887410_3800700"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def records(text: str, marker: str) -> list[dict[str, str]]:
    return [
        dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
        for line in text.splitlines()
        if marker in line
    ]


def num(row: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(row.get(key, str(default)), 0)
    except ValueError:
        return default


def hexnum(row: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(row.get(key, ""), 16)
    except ValueError:
        return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", required=True, type=Path)
    ap.add_argument("--source-zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    errors: list[str] = []
    ret_sha = sha256_file(args.return_zip)
    src_sha = sha256_file(args.source_zip)
    if ret_sha != RETURN_SHA:
        errors.append("return_sha256_mismatch")
    if src_sha != SOURCE_SHA:
        errors.append("source_sha256_mismatch")

    returned, ret_errors, ret_meta = safe_entries(args.return_zip, RETURN_ROOT)
    source, src_errors, src_meta = safe_entries(args.source_zip, INSTALL)
    errors.extend(ret_errors)
    errors.extend(src_errors)

    allow = load_json(returned, "RETURN_ALLOWLIST.json")
    rmanifest = load_json(returned, "RETURN_MANIFEST.json")
    allow_records = allow.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipt_errors: list[str] = []
    for item in allow_records:
        path = item.get("path")
        if not isinstance(path, str):
            receipt_errors.append("invalid_allowlist_path")
            continue
        expected.add(path)
        payload = returned.get(path)
        if payload is None:
            receipt_errors.append(f"missing:{path}")
        elif len(payload) != item.get("size_bytes"):
            receipt_errors.append(f"size:{path}")
        elif sha256_bytes(payload) != item.get("sha256"):
            receipt_errors.append(f"sha256:{path}")
    exact_set = set(returned) == expected
    if not exact_set:
        errors.append("return_exact_set_mismatch")
    errors.extend(receipt_errors)

    source_manifest = source.get("package_manifest.json", b"")
    returned_manifest = returned.get("evidence/returned_package_manifest.json", b"")
    package_manifest = json.loads(source_manifest or b"{}")
    source_binding = (
        returned_manifest == source_manifest
        and rmanifest.get("install_name") == INSTALL
        and rmanifest.get("records") == allow_records
        and rmanifest.get("fixed_result_publication", {})
        .get("return_zip", "")
        .endswith(f"{INSTALL}_{EXECUTION}_return.zip")
    )
    if not source_binding:
        errors.append("source_or_execution_binding_mismatch")
    source_files = package_manifest.get("files", {})
    source_exact = (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    )
    if not source_exact:
        errors.append("source_exact_set_mismatch")

    gate = load_json(returned, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(returned, "evidence/package_preflight.json")
    install_preflight = load_json(returned, "evidence/install_preflight.json")
    observer_preflight = load_json(returned, "evidence/observer_precompile.json")
    feature_binding = load_json(
        returned, "evidence/diagnostic_feature_binding.json"
    )
    root_gate = load_json(returned, "evidence/ndp_root_toplevel_gate.json")
    publication = load_json(returned, "evidence/publication_preflight.json")
    compile_status = integer_entry(
        returned, "evidence/compile_exit_status.txt", 125
    )
    run_status = integer_entry(returned, "evidence/run_exit_status.txt", 125)
    signal = returned.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    observer_log = returned.get("runs/c0/return_observer.log", b"").decode(
        "utf-8", errors="replace"
    )
    sim_log = returned.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    argv = returned.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )
    compile_log = returned.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = returned.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")

    observer_sha = package_manifest.get("observer_sha256")
    preflight = {
        "package": package_preflight.get("valid") is True,
        "install_reset": (
            install_preflight.get("valid") is True
            and install_preflight.get("runtime_d_initially_absent") is True
        ),
        "root_direct_set": (
            root_gate.get("valid") is True
            and root_gate.get("ndp_root_toplevel_unchanged") is True
        ),
        "publication": (
            publication.get("publication_state")
            == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING"
            and all(
                publication.get(k) is True
                for k in (
                    "server_root_duplicate_absent",
                    "package_root_duplicate_absent",
                    "install_namespace_duplicate_absent",
                    "run_root_duplicate_absent",
                    "launch_cwd_duplicate_absent",
                )
            )
        ),
        "observer": (
            observer_preflight.get("valid") is True
            and observer_preflight.get("observed_sha256") == observer_sha
            and sha256_bytes(
                source.get("tb_probe/native_return_observer.svh", b"")
            )
            == observer_sha
        ),
        "feature": feature_binding.get("valid") is True,
    }
    if not all(preflight.values()):
        errors.append("preflight_binding_failure")

    compile_ok = (
        compile_status == 0
        and "vcs" in compile_driver.lower()
        and "native_return_observer.svh" in compile_log
        and "Compilation completed!" in compile_driver
    )
    sim_ok = (
        run_status == 0
        and signal == "NONE"
        and "[RETURN_OBSERVER] enabled" in sim_log
        and "+RETURN_OBS_BRANCH_CATCHUP" in argv
        and f"/{INSTALL}/" in argv
    )
    if not compile_ok:
        errors.append("compile_binding_failure")
    if not sim_ok:
        errors.append("simulation_binding_failure")

    branch = records(observer_log, "BRANCH_CATCHUP_V1")
    edge = [row for row in branch if row.get("event") == "QUALIFIED_CHANGE"]
    decision = [row for row in branch if row.get("event") == "DIAG_DECISION"]
    final = decision[-1] if decision else {}
    chronology = {
        "feature_enabled": (
            "feature=RETURN_OBS_BRANCH_CATCHUP enabled=1" in observer_log
        ),
        "qualified_edge_count": len(edge) == 7,
        "first_partial_input": (
            len(edge) >= 2
            and num(edge[0], "mem_vld") == 0x1
            and num(edge[1], "mem_vld") == 0x3
            and num(edge[1], "mem_masked") == 0x2
        ),
        "third_window_delta2": (
            num(final, "desc_terminal") == 3
            and num(final, "desc") == 18
            and num(final, "prepared") == 20
            and num(final, "delta") == 2
        ),
        "same_gotten_suppression": (
            num(final, "mem_vld") == 0x1
            and num(final, "mem_same") == 0x1
            and num(final, "mem_gotten") == 0x7
            and num(final, "mem_masked") == 0
            and num(final, "mem_match") == 0
        ),
        "memory_queue_empty": (
            num(final, "mem_q_full") == 0
            and num(final, "mem_q_empty") == 1
        ),
        "physical_lc_chain_stopped": (
            hexnum(final, "lc13") == 0
            and hexnum(final, "lc14") == 0x510004
            and hexnum(final, "lc15") == 0x520002
            and hexnum(final, "lc9") == 0
            and num(final, "pe7_wr") == num(final, "pe7_rd") == 9
        ),
        "buffer_branch_ahead_and_full": (
            num(final, "buf_push") == 27
            and num(final, "buf_pop") == 23
            and num(final, "row_full") == 1
            and num(final, "col_full") == 1
            and num(final, "bufq_full") == 1
            and num(final, "prepared_count") == 32
            and num(final, "prepared_bp") == 0
        ),
    }
    if not all(chronology.values()):
        errors.append("branch_catchup_chronology_mismatch")

    natural = gate.get("natural_terminal_observed") is True
    formal_expected = int(gate.get("formal_d_expected", 320))
    formal_present = int(gate.get("formal_d_present", 0))
    formal_missing = int(gate.get("formal_d_missing", formal_expected))
    formal_mismatch = int(gate.get("formal_d_mismatch", 0))
    joint = (
        compile_status == 0
        and run_status == 0
        and natural
        and formal_present == formal_expected
        and formal_missing == 0
        and formal_mismatch == 0
    )

    candidate_matrix = {
        "shared_source_partial_capture": {
            "status": "COMPATIBLE_NOT_UNIQUE",
            "evidence": (
                "physical LC8/17 remain held with unequal destination-ready "
                "vectors, but v65 does not identify which destination owns "
                "each Memory_AG input acceptance"
            ),
        },
        "lc_terminal_or_keep_stop": {
            "status": "OBSERVED_NOT_ROOT_UNIQUE",
            "evidence": (
                "physical LC6 is empty while LC8/17 are held and all three "
                "qualified advance counters stop before a new Memory_AG match"
            ),
        },
        "memory_ag_same_gotten_suppression": {
            "status": "OBSERVED_EXPECTED_MECHANISM_NOT_PROVEN_DEFECT",
            "evidence": (
                "final raw/same/gotten/masked=1/1/7/0; RTL intentionally "
                "suppresses a held same token already accepted"
            ),
        },
        "buffer_branch_early_epoch_accept": {
            "status": "OBSERVED_NOT_ROOT_UNIQUE",
            "evidence": (
                "Buffer pushes reach 27/23 and prepared storage reaches 32 "
                "while address descriptors remain 18/18"
            ),
        },
    }
    root_status = "UNRESOLVED_AFTER_V65_BRANCH_CATCHUP"
    first_divergence = (
        "AFTER_THIRD_DESCRIPTOR_TERMINAL_ADDRESS_BRANCH_HAS_NO_COMPLETE_NEW_"
        "THREE_INPUT_TUPLE_WHILE_BUFFER_BRANCH_ACCEPTS_TWO_UNMATCHED_GROUPS"
    )
    report = {
        "schema": "node0004-v65-branchcatch-return-analysis-v1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "identity": {
            "return_path": str(args.return_zip.resolve()),
            "return_bytes": args.return_zip.stat().st_size,
            "return_sha256": ret_sha,
            "source_path": str(args.source_zip.resolve()),
            "source_bytes": args.source_zip.stat().st_size,
            "source_sha256": src_sha,
            "execution_id": EXECUTION,
            "unique_return_basename_is_not_source_identity": True,
            "cloud_rtl_authority": CLOUD_RTL,
            "returned_manifest_cloud_identity": package_manifest.get(
                "cloud_rtl_authority"
            ),
        },
        "archive": {
            "return": ret_meta,
            "source": src_meta,
            "return_crc": "PASS" if not ret_errors else "FAIL",
            "return_exact_set": exact_set,
            "per_file_receipts": "PASS" if not receipt_errors else "FAIL",
            "source_binding": source_binding,
            "source_exact_set": source_exact,
        },
        "preflight": preflight,
        "runtime": {
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "compile_bound": compile_ok,
            "simulation_bound": sim_ok,
            "canonical": gate.get("canonical_decision"),
        },
        "qualified_branch_catchup": {
            "edge_count": len(edge),
            "decision_count": len(decision),
            "chronology": chronology,
            "final_snapshot": final,
            "candidate_matrix": candidate_matrix,
        },
        "last_proven_good": (
            "THIRD_DESCRIPTOR_TERMINAL_AND_DESC18_PREPARED18_RECOVER_TO_DELTA0"
        ),
        "first_divergence": first_divergence,
        "hang_root_cause": {
            "status": root_status,
            "reason": (
                "v65 proves the address and Buffer branches diverge and proves "
                "same/gotten suppression is active, but it lacks per-input "
                "source/epoch ownership and per-destination accept chronology; "
                "the four mechanisms are therefore not causally ordered."
            ),
        },
        "formal_result": {
            "natural_terminal": natural,
            "expected": formal_expected,
            "present": formal_present,
            "missing": formal_missing,
            "mismatch": formal_mismatch,
            "all_missing_is_not_numeric_pass": (
                formal_present == 0
                and formal_missing == formal_expected
                and formal_mismatch == 0
            ),
            "joint_gate": joint,
            "E3": compile_ok and sim_ok,
            "E4": joint,
            "E5": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NODE0004_V65_REPEAT_EXECUTION_RETURN_COLLECTOR_ABI",
                "B_CONV_NODE0004_V64_BRANCH_CATCHUP_COARSE_BOUNDARY_UNOBSERVED",
            ],
            "opened": [
                "B_CONV_NODE0004_MSE4_PER_INPUT_EPOCH_OWNERSHIP_UNOBSERVED"
            ],
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
            "timeout_or_backpressure_changed": False,
            "functional_rtl_modified": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
