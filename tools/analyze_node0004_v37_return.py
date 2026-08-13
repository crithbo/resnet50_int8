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


INSTALL_NAME = "r5_n4_hw_v37_wrdrain_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "6a2cc106f6124f3640340531d5f1e62bac245e3c8674bd3fdb0e3307714a2d37"
SOURCE_SHA256 = "cd37675c41c3920c292bdb7ff342443222f96a412fe66d7d4d1319540549dbe0"
CURRENT_RTL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"


def one_record(observer: str, name: str, errors: list[str]) -> dict[str, str]:
    records = parse_kv_record(observer, name)
    if len(records) != 1:
        errors.append(f"{name} count differs: {len(records)}")
        return {}
    return records[0]


def i(record: dict[str, str], key: str) -> int:
    try:
        return int(record.get(key, "0"), 0)
    except ValueError:
        return 0


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
    errors += return_errors + source_errors
    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    returned = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipts: dict[str, bool] = {}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        receipts[path] = (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        )
        if not receipts[path]:
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
    row = one_record(observer, "ROWLC4_BUFAG_BOUNDARY_V1", errors)
    b5 = one_record(observer, "B5RD_BOUNDARY_V1", errors)
    desc = one_record(observer, "MSE4_DESCRIPTOR_BOUNDARY_V1", errors)
    idx = one_record(observer, "MSE4_INDEX_BOUNDARY_V1", errors)
    dwrite = one_record(observer, "DWRITE_PATH_BOUNDARY_V1", errors)
    hub = one_record(observer, "DATAHUB_DRAIN_BOUNDARY_V1", errors)
    wr = one_record(observer, "WRDRAIN_BOUNDARY_V1", errors)

    formal_members = [
        path for path in entries if "/D/" in path or "matrix_D_" in path
    ]
    natural_terminal = gate.get("natural_terminal_observed") is True
    compile_clean = (
        compile_status == 0
        and ("0 error(s)" in compile_log or "0 errors" in compile_log)
        and "elaboration done" in compile_log
    )
    source_observer = source.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode("utf-8", errors="replace")
    observer_sha = sha256_bytes(
        source.get("tb_probe/native_return_observer.svh", b"")
    )
    actual_compile_commit_tokens = sorted(
        set(re.findall(r"\b[0-9a-f]{40}\b", compile_log + "\n" + compile_driver))
    )

    five_candidates = {
        "DESCRIPTOR_FIFO_LIVE_STALL": (
            i(wr, "desc_empty") == 0 or i(wr, "desc_count") != 0
        ),
        "MASK_DEPENDENCY": i(wr, "mask_flag") != 0,
        "OUTPUT_SLOT_BACKPRESSURE": i(wr, "ob_bp") != 3,
        "MEMORY_WRITE_DATA_NOT_READY": i(wr, "mem_ready") != 3,
        "DATAHUB_ARBITER_OR_BANK_STALL": (
            i(hub, "head_x") != 0
            or i(hub, "no_bank_match") != 0
            or i(hub, "queue_full8") != 0
            or i(hub, "queue_full9") != 0
        ),
    }
    descriptor_conservation = (
        i(desc, "desc_hs") == 32
        and i(desc, "fifo_push") == 32
        and i(desc, "fifo_pop") == 32
        and i(desc, "mem_req0") == 32
        and i(desc, "mem_req1") == 32
    )
    index_conservation = (
        i(idx, "accept1") == 16
        and i(idx, "match") == 16
        and i(idx, "push") == 16
        and i(idx, "pop") == 16
        and i(idx, "desc") == 32
    )
    downstream_drain = (
        i(hub, "addr_in8") + i(hub, "addr_in9") == 32
        and i(hub, "data_in8") + i(hub, "data_in9") == 32
        and i(hub, "crossbar_accept8") + i(hub, "crossbar_accept9") == 32
    )
    two_group_imbalance = (
        i(desc, "prepared_wr") == 34
        and i(desc, "prepared_rd") == 32
        and i(desc, "prepared_count") == 32
        and i(wr, "hold_vld") == 1
        and i(dwrite, "queue_count") == 2
        and i(dwrite, "queue_full") == 1
    )
    checks = {
        "return_crc_path_root": not return_errors,
        "return_exact_set_allowlist_receipts": (
            return_exact and all(receipts.values())
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
                "+RETURN_OBS_WRDRAIN",
                "+RETURN_OBS_DWRITE_PATH",
                "+RETURN_OBS_DATAHUB_DRAIN",
            )
        ),
        "feature_binding": feature_binding.get("valid") is True,
        "descriptor_conservation": descriptor_conservation,
        "index_conservation": index_conservation,
        "datahub_drain_conservation": downstream_drain,
        "two_prepared_group_imbalance": two_group_imbalance,
        "five_v37_candidates_excluded": not any(five_candidates.values()),
    }
    if not all(checks.values()):
        errors.append("qualified v37 evidence differs")

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
        "schema": "node0004-v37-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "V37_WRDRAIN_CANDIDATES_CLOSED_BOUNDARY_ADVANCED",
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
            "rowlc4": row,
            "buffer5": b5,
            "mse4_descriptor": desc,
            "mse4_index": idx,
            "dwrite": dwrite,
            "datahub": hub,
            "wrdrain": wr,
            "candidate_truth_means_stall_present": five_candidates,
        },
        "LAST_PROVEN_GOOD": (
            "32_WR_DESCRIPTORS_AND_32_PREPARED_GROUPS_CONSUMED_THROUGH_"
            "DATAHUB_CROSSBAR"
        ),
        "FIRST_DIVERGENCE": (
            "PREPARED_GROUP_33_AND_34_HAVE_NO_CORRESPONDING_WR_DESCRIPTOR_"
            "AND_REMAIN_AS_COUNT32_PLUS_ONE_HOLD"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "BOUNDARY_UNIQUE_CAUSE_CLASS_NOT_YET_UNIQUE",
            "mechanism": (
                "The address side accepts 16 Memory_AG input1 tuples and "
                "produces exactly 32 descriptors; all 32 descriptors are "
                "pushed, popped, written and accepted by DataHub. The data/tag "
                "side prepares 34 spatial groups. After 32 drains the "
                "descriptor FIFO is empty, two 16-entry groups remain "
                "(prepared_count=32), one later group is held, upstream "
                "RD_Buffer_AG is full and wr_ready is low."
            ),
            "not_root_causes": list(
                key for key, present in five_candidates.items() if not present
            ),
            "remaining_candidates": [
                "Buffer_AG data/tag schedule legitimately emits two groups more than the Memory_AG descriptor schedule",
                "tag/data association or last/index lifetime lets two stale groups enter WR_Data_Channel after descriptor completion",
                "Memory_AG input1 terminal/source lifetime ends two descriptors early relative to the data schedule",
                "WR_Data_Channel prefetch/hold admission lacks a descriptor-lifetime guard at terminal",
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
                "The return proves compile/elaboration of recorded paths; "
                "the user-attested commit cannot substitute for E3/E4/E5."
            ),
        },
        "BLOCKER_DELTA": {
            "closed": (
                "B_CONV_NODE0004_WR_DATA_PREPARED_TO_OUTPUT_AND_DATAHUB_DRAIN_UNOBSERVED"
            ),
            "opened": (
                "B_CONV_NODE0004_WR_DESCRIPTOR_VS_PREPARED_DATA_TERMINAL_LIFETIME_UNOBSERVED"
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
            "candidate_matrix": {
                "DATA_TAG_SCHEDULE_EXCESS": [
                    "qualified data/tag generation and prepare exceeds address descriptor terminal count"
                ],
                "STALE_TAG_OR_DATA_LIFETIME": [
                    "post-descriptor-completion prepare has stale/replayed tag or data owner"
                ],
                "ADDRESS_TERMINAL_EARLY": [
                    "Memory_AG input1 producer stops before corresponding data/tag terminal"
                ],
                "WR_PREFETCH_WITHOUT_DESCRIPTOR_GUARD": [
                    "prepared admission occurs after descriptor terminal with no live descriptor"
                ],
            },
            "required_observation": (
                "one chronology binds descriptor-terminal edge to the next "
                "qualified tag, buffer-read, prepared-write and hold events, "
                "including owner tag/last/index and live descriptor count"
            ),
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_SUFFICIENT",
            "rule_ids": [
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "evidence": (
                "One successor can distinguish every remaining low-cost "
                "candidate at the descriptor-terminal/data-admission boundary."
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
