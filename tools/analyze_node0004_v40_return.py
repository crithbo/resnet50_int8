from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (  # noqa: E402
    integer_entry,
    load_json,
    parse_kv_record,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL_NAME = "r5_n4_hw_v40_wrterm_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "2d0851dd41db8c3c5c7d14eb986a1b1696438397a3f21ae7b452cf40398a777d"
SOURCE_SHA256 = "f1695ec3232e1e651a3242603e299c5ce0b4a46762ec9a23401e0bf7a5523d9e"
CURRENT_RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"


def one_record(observer: str, name: str, errors: list[str]) -> dict[str, str]:
    records = parse_kv_record(observer, name)
    if len(records) != 1:
        errors.append(f"{name} count differs: {len(records)}")
        return {}
    return records[0]


def integer(record: dict[str, str], key: str) -> int:
    try:
        return int(record.get(key, "0"), 0)
    except ValueError:
        return 0


def timestamp(record: dict[str, str]) -> int:
    match = re.match(r"\s*(\d+)\s+\|", record.get("_line", ""))
    return int(match.group(1)) if match else -1


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
    source_sidecar = args.source_sidecar.resolve()
    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    sidecar_valid = (
        source_sidecar.read_text(encoding="ascii").strip()
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
    return_receipts: dict[str, bool] = {}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        return_receipts[path] = (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        )
        if not return_receipts[path]:
            errors.append(f"return receipt differs: {path}")
    return_exact = set(entries) == expected
    if not return_exact:
        errors.append("return exact-set differs")

    source_manifest_payload = source.get("package_manifest.json", b"")
    returned_manifest_payload = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    return_binding = (
        returned.get("install_name") == INSTALL_NAME
        and returned.get("records") == records
        and returned_manifest_payload == source_manifest_payload
    )
    if not return_binding:
        errors.append("return/source manifest binding differs")
    source_manifest = json.loads(source_manifest_payload or b"{}")
    source_files = source_manifest.get("files", {})
    source_exact = (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    )
    if not source_exact:
        errors.append("source exact-set differs")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(entries, "evidence/observer_precompile.json")
    feature_binding = load_json(entries, "evidence/diagnostic_feature_binding.json")
    compile_status = integer_entry(entries, "evidence/compile_exit_status.txt", 125)
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    observer = entries.get("runs/c0/return_observer.log", b"").decode(
        "utf-8", errors="replace"
    )
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    simulator_argv = entries.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )

    canonical = one_record(observer, "CANONICAL_DIAG_DECISION_V1", errors)
    desc = one_record(observer, "MSE4_DESCRIPTOR_BOUNDARY_V1", errors)
    index = one_record(observer, "MSE4_INDEX_BOUNDARY_V1", errors)
    dwrite = one_record(observer, "DWRITE_PATH_BOUNDARY_V1", errors)
    hub = one_record(observer, "DATAHUB_DRAIN_BOUNDARY_V1", errors)
    wrdrain = one_record(observer, "WRDRAIN_BOUNDARY_V1", errors)
    wrterm = one_record(observer, "WRTERM_BOUNDARY_V1", errors)
    wrterm_edges = parse_kv_record(observer, "WRTERM_EDGE_V1")

    actual_terminal_edges = [
        item
        for item in wrterm_edges
        if integer(item, "desc_pop") == 1
        and integer(item, "desc_push") == 0
        and integer(item, "desc_count") == 1
    ]
    if len(actual_terminal_edges) != 1:
        errors.append(
            f"actual final descriptor-pop edge count differs: "
            f"{len(actual_terminal_edges)}"
        )
        actual_terminal = {}
        post_terminal: list[dict[str, str]] = []
    else:
        actual_terminal = actual_terminal_edges[0]
        actual_time = timestamp(actual_terminal)
        post_terminal = [
            item for item in wrterm_edges if timestamp(item) > actual_time
        ]

    post_sums = {
        key: sum(integer(item, key) for item in post_terminal)
        for key in (
            "addr1",
            "desc_push",
            "desc_pop",
            "tag_push",
            "tag_pop",
            "prepare",
            "hold_rise",
        )
    }
    observer_terminal_predicate_defect = (
        integer(wrterm, "desc_terminal") == 31
        and len(actual_terminal_edges) == 1
        and sum(
            1
            for item in wrterm_edges
            if integer(item, "desc_pop") == 1
            and integer(item, "desc_count") == 1
        )
        == 31
    )
    exact_post_terminal_sequence = post_sums == {
        "addr1": 0,
        "desc_push": 0,
        "desc_pop": 0,
        "tag_push": 2,
        "tag_pop": 1,
        "prepare": 1,
        "hold_rise": 1,
    }

    formal_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
    natural_terminal = gate.get("natural_terminal_observed") is True
    compile_clean = (
        compile_status == 0
        and ("0 error(s)" in compile_log or "0 errors" in compile_log)
        and "elaboration done" in compile_log
    )
    source_observer_payload = source.get(
        "tb_probe/native_return_observer.svh", b""
    )
    observer_sha = sha256_bytes(source_observer_payload)
    actual_compile_commit_tokens = sorted(
        set(re.findall(r"\b[0-9a-f]{40}\b", compile_log + "\n" + compile_driver))
    )
    descriptor_conservation = (
        integer(desc, "desc_hs") == 32
        and integer(desc, "fifo_push") == 32
        and integer(desc, "fifo_pop") == 32
        and integer(desc, "mem_req0") == 32
        and integer(desc, "mem_req1") == 32
    )
    downstream_conservation = (
        integer(hub, "addr_in8") + integer(hub, "addr_in9") == 32
        and integer(hub, "data_in8") + integer(hub, "data_in9") == 32
        and integer(hub, "crossbar_accept8")
        + integer(hub, "crossbar_accept9")
        == 32
    )
    two_group_imbalance = (
        integer(desc, "prepared_wr") == 34
        and integer(desc, "prepared_rd") == 32
        and integer(desc, "prepared_count") == 32
        and integer(wrdrain, "hold_vld") == 1
        and integer(dwrite, "queue_count") == 2
    )
    checks = {
        "return_crc_path_root": not return_errors,
        "return_exact_set_allowlist_receipts": (
            return_exact and all(return_receipts.values())
        ),
        "return_source_manifest_binding": return_binding,
        "source_crc_path_root": not source_errors,
        "source_manifest_exact_set": source_exact,
        "package_preflight": package_preflight.get("valid") is True,
        "install_preflight": install_preflight.get("valid") is True,
        "runtime_d_absent": (
            install_preflight.get("runtime_d_initially_absent") is True
        ),
        "observer_identity": (
            observer_preflight.get("valid") is True
            and observer_preflight.get("identity_match") is True
            and observer_preflight.get("observed_sha256") == observer_sha
        ),
        "compile_run_signal": (
            compile_status == 0 and run_status == 0 and signal == "NONE"
        ),
        "compile_elaboration_clean": compile_clean,
        "observer_compile_binding": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
            and f"/{INSTALL_NAME}/tb_probe" in compile_driver
        ),
        "observer_runtime_binding": all(
            token in simulator_argv
            for token in (
                "+RETURN_OBSERVER",
                "+RETURN_OBS_WRTERM",
                "+RETURN_OBS_WRDRAIN",
            )
        ),
        "feature_binding": feature_binding.get("valid") is True,
        "descriptor_conservation": descriptor_conservation,
        "datahub_drain_conservation": downstream_conservation,
        "two_prepared_group_imbalance": two_group_imbalance,
        "wrterm_raw_edges_preserved": len(wrterm_edges) == 34,
        "unique_actual_final_descriptor_pop": len(actual_terminal_edges) == 1,
        "exact_post_terminal_sequence": exact_post_terminal_sequence,
        "observer_terminal_predicate_defect_reproduced": (
            observer_terminal_predicate_defect
        ),
    }
    if not all(checks.values()):
        errors.append("qualified v40 evidence differs")

    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and natural_terminal
        and gate.get("formal_readback_claimed") is True
        and len(formal_members) == 320
        and gate.get("e4_claimed") is True
        and gate.get("e5_claimed") is True
    )
    report: dict[str, Any] = {
        "schema": "node0004-v40-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": (
                "V40_OBSERVER_TERMINAL_PREDICATE_DEFECT_WITH_"
                "RAW_CHRONOLOGY_CONSUMABLE"
            ),
            "regression": False,
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": (
                    "CDA-SERVER-RETURN-TRANSPORT-"
                    "USER-ATTESTED-NO-SIDECAR-001"
                ),
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_sha256": sha256_file(source_sidecar),
                "sidecar_valid": sidecar_valid,
            },
            "return_meta": return_meta,
            "source_meta": source_meta,
            "checks": checks,
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "compile_elaboration_clean": compile_clean,
            "simulation_started": "[RETURN_OBSERVER] enabled" in sim_log,
            "diagnostic_finish_observed": "$finish" in sim_log,
            "natural_terminal": natural_terminal,
            "formal_d_expected": 320,
            "formal_d_present": len(formal_members),
            "formal_d_missing": 320 - len(formal_members),
            "formal_d_mismatch": 0,
            "joint_result_gate": joint_gate,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "qualified_evidence": {
            "canonical": canonical,
            "mse4_descriptor": desc,
            "mse4_index": index,
            "dwrite": dwrite,
            "datahub": hub,
            "wrdrain": wrdrain,
            "wrterm_boundary": wrterm,
            "wrterm_edge_count": len(wrterm_edges),
            "actual_final_descriptor_pop": actual_terminal,
            "post_actual_terminal": post_terminal,
            "post_actual_terminal_sums": post_sums,
        },
        "LAST_PROVEN_GOOD": (
            "UNIQUE_FINAL_DESCRIPTOR_POP_AFTER_32_DESCRIPTORS_"
            "AND_32_DATA_GROUPS_REACH_DATAHUB"
        ),
        "FIRST_DIVERGENCE": (
            "FIRST_CYCLE_AFTER_TRUE_FINAL_DESCRIPTOR_POP_HAS_"
            "TAG_PUSH_TAG_POP_AND_PREPARED_WRITE_WITH_NO_ADDRESS_"
            "OR_DESCRIPTOR_PROGRESS"
        ),
        "HANG_ROOT_CAUSE": {
            "status": (
                "PACKAGE_OBSERVER_FINAL_DESCRIPTOR_PREDICATE_DEFECT_"
                "FIX_REQUIRED_BEFORE_REMAINING_DUT_CAUSE_UNIQUENESS"
            ),
            "package_observer_defect": {
                "source": "tb_probe/native_return_observer.svh",
                "predicate": (
                    "wt_desc_pop && u_wr_chl_queue.fifo_counter == 1"
                ),
                "mechanism": (
                    "The FIFO pre-state count is also one during steady-state "
                    "simultaneous push/pop. The observer therefore arms on 31 "
                    "pops, not on the unique final pop."
                ),
                "minimum_correction": (
                    "require wt_desc_pop && !wt_desc_push && "
                    "fifo_counter==1, then begin post-terminal accounting on "
                    "the following cycle"
                ),
                "functional_dut_modified": False,
            },
            "dut_boundary_still_proven_from_raw_edges": (
                "After the unique pop-without-push at count one, address and "
                "descriptor progress stay zero while two tags enqueue, one "
                "tag/data group is consumed into prepared storage, and the "
                "next data group raises hold."
            ),
            "remaining_candidates": [
                "upstream data/tag schedule continues beyond the address schedule",
                "a stale/replayed tag lifetime generates post-terminal work",
                "WR_Data_Channel admits prefetched data without a live descriptor",
            ],
            "functional_rtl_defect_claimed": False,
            "configuration_fix_claimed": False,
        },
        "compile_source_identity": {
            "actual_compile_paths_recorded": True,
            "actual_compile_commit_tokens": actual_compile_commit_tokens,
            "actual_compile_commit_recorded": bool(
                actual_compile_commit_tokens
            ),
            "server_baseline_user_attested_commit": CURRENT_RTL_COMMIT,
            "claim_boundary": (
                "Compile/elaboration of the recorded server paths is proven; "
                "no formal production commit token was returned, so E3/E4/E5 "
                "remain false."
            ),
        },
        "BLOCKER_DELTA": {
            "closed": (
                "B_CONV_NODE0004_WRTERM_RAW_EDGE_CHRONOLOGY_UNAVAILABLE"
            ),
            "opened": (
                "B_CONV_NODE0004_WRTERM_FINAL_DESCRIPTOR_PREDICATE_AND_"
                "POST_TERMINAL_OWNER_UNRESOLVED"
            ),
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "successor_requirement": {
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "observer_fix": (
                "Use the unique no-push final-pop predicate and snapshot "
                "post-terminal Buffer_AG source tag/index owner, queue "
                "write/read pointers, row/col index and descriptor-live state."
            ),
            "candidate_observation_matrix": {
                "SCHEDULE_EXCESS": [
                    "new source match/tag push after final descriptor pop"
                ],
                "STALE_OR_REPLAYED_LIFETIME": [
                    "post-terminal source row/col/tag equals an already accepted owner"
                ],
                "DESCRIPTOR_UNAWARE_PREFETCH": [
                    "buffer read/prepare occurs with descriptor count zero"
                ],
            },
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_SUFFICIENT",
            "rule_ids": [
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "evidence": (
                "The current rules already require qualified chronology and "
                "one high-information successor; the escape is a package-local "
                "predicate implementation error, not a missing rule."
            ),
        },
        "scope": {
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_analysis_repeated": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
