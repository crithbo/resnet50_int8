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


INSTALL = "r5_n4_hw_v64_dskew_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "755d653ae220fe46d3cd7b026229c459455c5c5ae6bc1c70728f139120ad7bae"
SOURCE_SHA = "8d4bce53f152e829973212a0cf8403c59a86c588a62ef9f11ab5e90937dd2268"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def kv_records(text: str, marker: str) -> list[dict[str, str]]:
    return [
        dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
        for line in text.splitlines()
        if marker in line
    ]


def number(row: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(row.get(key, str(default)), 0)
    except ValueError:
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    ret = args.return_zip.resolve()
    src = args.source_zip.resolve()
    ret_sha = sha256_file(ret)
    src_sha = sha256_file(src)
    if ret_sha != RETURN_SHA:
        errors.append("return SHA mismatch")
    if src_sha != SOURCE_SHA:
        errors.append("source SHA mismatch")
    sidecar_valid = args.source_sidecar.read_text(encoding="ascii").strip() == (
        f"{src_sha}  {src.name}"
    )
    if not sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, ret_errors, ret_meta = safe_entries(ret, RETURN_ROOT)
    source, src_errors, src_meta = safe_entries(src, INSTALL)
    errors += ret_errors + src_errors
    allow = load_json(entries, "RETURN_ALLOWLIST.json")
    returned = load_json(entries, "RETURN_MANIFEST.json")
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    allow_records = allow.get("records", [])
    for item in allow_records:
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
            errors.append(f"receipt differs:{path}")
    exact_return_set = set(entries) == expected
    if not exact_return_set:
        errors.append("return exact-set differs")

    source_manifest = source.get("package_manifest.json", b"")
    returned_manifest = entries.get("evidence/returned_package_manifest.json", b"")
    manifest = json.loads(source_manifest or b"{}")
    source_bound = (
        returned.get("install_name") == INSTALL
        and returned.get("records") == allow_records
        and returned_manifest == source_manifest
    )
    if not source_bound:
        errors.append("return/source manifest binding differs")
    source_files = manifest.get("files", {})
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
    root_gate = load_json(entries, "evidence/ndp_root_toplevel_gate.json")
    publication = load_json(entries, "evidence/publication_preflight.json")
    compile_status = integer_entry(entries, "evidence/compile_exit_status.txt", 125)
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    observer_log = entries.get(
        "runs/c0/return_observer.log", b""
    ).decode("utf-8", errors="replace")
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    argv = entries.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )

    observer_sha = manifest.get("observer_sha256")
    package_ok = package_preflight.get("valid") is True
    install_ok = (
        install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
    )
    root_ok = (
        root_gate.get("valid") is True
        and root_gate.get("ndp_root_toplevel_unchanged") is True
    )
    publication_ok = (
        publication.get("publication_state")
        == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING"
        and publication.get("server_root_duplicate_absent") is True
        and publication.get("package_root_duplicate_absent") is True
        and publication.get("install_namespace_duplicate_absent") is True
        and publication.get("run_root_duplicate_absent") is True
        and publication.get("launch_cwd_duplicate_absent") is True
    )
    observer_ok = (
        observer_preflight.get("valid") is True
        and observer_preflight.get("observed_sha256") == observer_sha
        and sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
        == observer_sha
    )
    compile_invoked = (
        compile_status == 0
        and "vcs" in compile_driver.lower()
        and "native_return_observer.svh" in compile_log
    )
    simulation_started = (
        run_status == 0
        and signal == "NONE"
        and "[RETURN_OBSERVER] enabled" in sim_log
        and "+RETURN_OBS_DSKEW" in argv
        and "CANONICAL_DIAG_DECISION_V1" in observer_log
        and feature_binding.get("valid") is True
    )
    if not all(
        (
            package_ok,
            install_ok,
            root_ok,
            publication_ok,
            observer_ok,
            compile_invoked,
            simulation_started,
        )
    ):
        errors.append("preflight/compile/simulation binding differs")

    canonical_rows = kv_records(observer_log, "CANONICAL_DIAG_DECISION_V1")
    dskew_edges = kv_records(observer_log, "DSKEW_EDGE_V1")
    dskew_boundary_rows = kv_records(observer_log, "DSKEW_BOUNDARY_V1")
    descriptor_rows = kv_records(observer_log, "MSE4_DESCRIPTOR_BOUNDARY_V1")
    index_rows = kv_records(observer_log, "MSE4_INDEX_BOUNDARY_V1")
    row_rows = kv_records(observer_log, "ROWLC4_BUFAG_BOUNDARY_V1")
    canonical = canonical_rows[-1] if canonical_rows else {}
    dskew_boundary = dskew_boundary_rows[-1] if dskew_boundary_rows else {}
    descriptor = descriptor_rows[-1] if descriptor_rows else {}
    index = index_rows[-1] if index_rows else {}
    row = row_rows[-1] if row_rows else {}
    by_n = {number(item, "n"): item for item in dskew_edges}
    chronology = {
        "first_empty_window_delta_1_then_2": (
            number(by_n.get(30, {}), "delta") == 1
            and number(by_n.get(31, {}), "delta") == 2
        ),
        "first_window_recovers": number(by_n.get(33, {}), "delta") == 0,
        "second_empty_window_delta_1_then_2": (
            number(by_n.get(34, {}), "delta") == 1
            and number(by_n.get(36, {}), "delta") == 2
        ),
        "second_window_recovers": number(by_n.get(40, {}), "delta") == 0,
        "third_empty_window_delta_1_then_2": (
            number(by_n.get(41, {}), "delta") == 1
            and number(by_n.get(42, {}), "delta") == 2
        ),
        "third_window_never_recovers": (
            number(dskew_boundary, "delta") == 2
            and number(dskew_boundary, "desc") == 18
            and number(dskew_boundary, "prepared") == 20
        ),
        "address_queue_empty_waiting_inputs": (
            number(index, "q_empty") == 1
            and number(index, "q_count") == 0
            and number(index, "input_vld") == 0x1
            and number(index, "masked_vld") == 0
        ),
        "buffer_branch_full": (
            number(row, "row_full") == 1
            and number(row, "col_full") == 1
            and number(row, "bufq_full") == 1
            and number(row, "rd_full") == 1
            and number(descriptor, "prepared_count") == 32
        ),
        "canonical_hang": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and number(canonical, "qualified_delta") == 0
            and number(canonical, "no_progress_windows") == 4
        ),
    }
    if not all(chronology.values()):
        errors.append("qualified v64 DSKEW chronology differs")

    formal_expected = int(gate.get("formal_d_expected", 320))
    formal_present = int(gate.get("formal_d_present", 0))
    formal_missing = int(gate.get("formal_d_missing", formal_expected))
    formal_mismatch = int(gate.get("formal_d_mismatch", 0))
    natural = gate.get("natural_terminal_observed") is True
    joint = (
        compile_status == 0
        and run_status == 0
        and natural
        and formal_present == formal_expected
        and formal_missing == 0
        and formal_mismatch == 0
    )
    cloud = manifest.get("cloud_rtl_authority", {})
    report = {
        "schema": "node0004-v64-recovered-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "VALID_RECOVERED_RETURN_D_SKEW_CAUSAL_BOUNDARY_REFINED",
            "return_zip": {
                "path": str(ret),
                "bytes": ret.stat().st_size,
                "sha256": ret_sha,
                "external_sidecar_required": False,
                "transport_policy": "USER_ATTESTED_NO_SIDECAR",
            },
            "source_zip": {
                "path": str(src),
                "bytes": src.stat().st_size,
                "sha256": src_sha,
                "sidecar_valid": sidecar_valid,
            },
            "return_meta": ret_meta,
            "source_meta": src_meta,
            "checks": {
                "crc_root_path": not ret_errors,
                "exact_set_allowlist_receipts": exact_return_set,
                "source_manifest_binding": source_bound,
                "source_exact_set": source_exact,
                "package_preflight": package_ok,
                "install_preflight_runtime_d_absent": install_ok,
                "ndp_root_toplevel_unchanged": root_ok,
                "fixed_publication_preflight": publication_ok,
                "observer_precompile": observer_ok,
                "compile_invoked": compile_invoked,
                "dskew_feature_runtime_bound": simulation_started,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "natural_terminal": natural,
            "formal_d_expected": formal_expected,
            "formal_d_present": formal_present,
            "formal_d_missing": formal_missing,
            "formal_d_mismatch": formal_mismatch,
            "all_missing_is_not_numeric_pass": (
                formal_present == 0
                and formal_missing == formal_expected
                and formal_mismatch == 0
            ),
            "joint_result_gate": joint,
            "E3": True,
            "E4": False,
            "E5": False,
        },
        "ACTUAL_RTL_IDENTITY": {
            "manifest_cloud_commit": cloud.get("approved_commit"),
            "expected_cloud_commit": CLOUD_RTL,
            "production_compile_root_observed": (
                "/home/panqs/ndp/NDP_copy01" in compile_log
            ),
            "separate_immutable_actual_compile_commit_receipt": False,
            "identity_difference_nonblocking": True,
        },
        "LAST_PROVEN_GOOD": (
            "FIRST_TWO_TRANSIENT_DESCRIPTOR_EMPTY_WINDOWS_RECOVER_TO_"
            "PREPARED_MINUS_DESCRIPTOR_DELTA_ZERO"
        ),
        "FIRST_DIVERGENCE": (
            "THIRD_DESCRIPTOR_EMPTY_AT_DESC18_LEAVES_PREPARED20_DELTA2_"
            "WHILE_MEMORY_AG_QUEUE_IS_EMPTY_AND_BUFFER_BRANCH_IS_FULL"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AFTER_STATIC_CAUSAL_CONE_AUDIT",
            "classification": (
                "SHARED_LC_ADDRESS_BRANCH_CATCHUP_VS_BUFFER_BRANCH_CAPACITY_CYCLE"
            ),
            "mechanism": (
                "A two-group data lead is not itself the defect: it occurs "
                "twice and is caught by later descriptors. At the third "
                "descriptor-empty epoch, prepared data advances from 18 to "
                "20 while descriptors stay at 18. The Memory_AG index queue "
                "is empty and lacks a complete three-input match; meanwhile "
                "the Buffer_AG row, column, source/tag queues and the 32-entry "
                "prepared store are full. No branch can demonstrate the next "
                "qualified capture, so the shared-source fanout cannot catch "
                "the address branch up."
            ),
            "qualified_dynamic_evidence": chronology,
            "closed_candidates": [
                "descriptor FIFO silently drops a pushed entry",
                "every two-group data lead is illegal",
                "the third descriptor-empty event is the global Conv terminal",
                "the v62 PE keep threshold regression reappears",
                "the package failed to compile or start simulation",
            ],
            "remaining_candidates": [
                "shared LC9 partial capture leaves the Memory_AG branch one epoch behind",
                "LC13/LC14/LC15 terminal or keep state stops the next address tuple",
                "Memory_AG same/gotten state suppresses the required next input",
                "Buffer_AG accepts the next epoch before the corresponding address epoch can become live",
            ],
            "why_not_yet_config_or_rtl_fix": (
                "The return contains aggregate qualified counts but not the "
                "per-destination ready/capture vector at the third empty "
                "transition. All four remaining causes predict the same final "
                "aggregate state, so changing a leaf now would be speculative."
            ),
            "functional_rtl_root_cause_proven": False,
            "configuration_root_cause_proven": False,
        },
        "QUALIFIED_EVIDENCE": {
            "canonical": canonical,
            "dskew_edges": dskew_edges,
            "dskew_boundary": dskew_boundary,
            "mse4_descriptor": descriptor,
            "mse4_index": index,
            "rowlc4_bufag": row,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_V64_RESULT_RECOVERY",
                "B_CONV_NODE0004_DESCRIPTOR_FIFO_PUSH_POP_LOSS",
                "B_CONV_NODE0004_UNBOUNDED_DATA_PREFETCH_ASSUMPTION",
            ],
            "refined": {
                "from": "B_CONV_NODE0004_D_PREPARED_DESCRIPTOR_FIRST_SKEW_CAUSE_UNOBSERVED",
                "to": "B_CONV_NODE0004_THIRD_DESCRIPTOR_EMPTY_SHARED_BRANCH_CATCHUP_UNOBSERVED",
            },
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_SUFFICIENT",
            "evidence": (
                "The recovered partial return is consumable because internal "
                "identity, allowlist and per-file receipts are complete. The "
                "continuous-closure and information-gain rules correctly "
                "require one branch-capture diagnostic rather than a guessed "
                "config or RTL change."
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
