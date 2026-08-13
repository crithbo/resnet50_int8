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


INSTALL = "r5_n4_hw_v63_runnerdiag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "87ed7fab2c214b260f5a7ec9761e4e47581fcd321bb458e2a32f9a5d52456109"
SOURCE_SHA = "99f50faeed69d89cff3211121661b5331a9e98d8135064b41b76203f7c277712"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def kv(text: str, marker: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if marker in line]
    return (
        dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", lines[-1]))
        if lines
        else {}
    )


def records(text: str, marker: str) -> list[dict[str, str]]:
    return [
        dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
        for line in text.splitlines()
        if marker in line
    ]


def number(record: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(record.get(key, str(default)), 0)
    except ValueError:
        return default


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--return-zip", required=True, type=Path)
    p.add_argument("--source-zip", required=True, type=Path)
    p.add_argument("--source-sidecar", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

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
    allow_records = allow.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
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

    source_manifest_bytes = source.get("package_manifest.json", b"")
    returned_manifest_bytes = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    manifest = json.loads(source_manifest_bytes or b"{}")
    source_bound = (
        returned.get("install_name") == INSTALL
        and returned.get("records") == allow_records
        and returned_manifest_bytes == source_manifest_bytes
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
    compile_status = integer_entry(
        entries, "evidence/compile_exit_status.txt", 125
    )
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
    runner = source.get("PREPARE_AND_RUN.sh", b"").decode(
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
        "vcs" in compile_driver.lower()
        and "native_return_observer.svh" in compile_log
        and "NDP_Top_phy_filelist.f" in compile_driver
    )
    simulation_started = (
        "[RETURN_OBSERVER] enabled" in sim_log
        and "+RETURN_OBS_LC18_PE7" in argv
        and "+RETURN_OBS_LC13_LC14" in argv
        and "CANONICAL_DIAG_DECISION_V1" in observer_log
        and feature_binding.get("valid") is True
    )
    runner_visibility_contract = (
        "RUNNER_ERROR code=%s package=%s message=%s" in runner
        and "RUNNER_FINAL_STATUS package=%s" in runner
        and "return target collision; preserve and move" in runner
    )
    silent_exit_escape_closed = (
        runner_visibility_contract
        and package_ok
        and install_ok
        and compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and compile_invoked
        and simulation_started
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
            runner_visibility_contract,
            silent_exit_escape_closed,
        )
    ):
        errors.append("preflight/runner/compile/simulation binding differs")

    canonical = kv(observer_log, "CANONICAL_DIAG_DECISION_V1")
    lc18_edges = records(observer_log, "LC18_PE7_EDGE_V1")
    lc18 = kv(observer_log, "LC18_PE7_BOUNDARY_V1")
    lc_chain = kv(observer_log, "LC13_LC14_BOUNDARY_V1")
    dterm = kv(observer_log, "DTERM_OWNER_BOUNDARY_V1")
    descriptor = kv(observer_log, "MSE4_DESCRIPTOR_BOUNDARY_V1")
    index = kv(observer_log, "MSE4_INDEX_BOUNDARY_V1")
    dwrite = kv(observer_log, "DWRITE_PATH_BOUNDARY_V1")
    row4 = kv(observer_log, "ROWLC4_BUFAG_BOUNDARY_V1")
    wrterm = kv(observer_log, "WRTERM2_BOUNDARY_V1")

    terminal_accept = next(
        (
            row
            for row in lc18_edges
            if number(row, "lc18_port") == 0x730007
            and number(row, "pe7_in_bp") == 0x7
            and number(row, "pe7_matched") == 1
        ),
        {},
    )
    next_lc17 = next(
        (
            row
            for row in lc18_edges
            if terminal_accept
            and number(row, "n") > number(terminal_accept, "n")
            and number(row, "lc17_port") == 0x420002
        ),
        {},
    )
    terminal_result = next(
        (
            row
            for row in lc18_edges
            if number(row, "pe7_out") == 0x630007
        ),
        {},
    )
    dynamic = {
        "canonical_stall": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and number(canonical, "qualified_progress") == 298
            and number(canonical, "qualified_delta") == 0
            and number(canonical, "no_progress_windows") == 4
        ),
        "pe_keep_index3_terminal_accepted": bool(terminal_accept),
        "lc17_advanced_to_index2_after_terminal": bool(next_lc17),
        "pe7_terminal_result_released": bool(terminal_result),
        "physical_chain_progress_increased": (
            number(lc_chain, "q13_out") == 2
            and number(lc_chain, "q14_out") == 4
            and number(lc_chain, "q15_out") == 2
        ),
        "two_group_descriptor_skew": (
            number(descriptor, "prepared_wr") == 20
            and number(descriptor, "prepared_rd") == 18
            and number(descriptor, "fifo_push") == 18
            and number(descriptor, "fifo_pop") == 18
            and number(descriptor, "prepared_count") == 32
        ),
        "address_index_conserved": (
            number(index, "match") == 9
            and number(index, "push") == 9
            and number(index, "pop") == 9
            and number(index, "desc") == 18
        ),
        "no_d_last_or_slice_finish": (
            number(dwrite, "wdata_last_accept") == 0
            and number(dwrite, "slice_finish") == 0
        ),
        "descriptor_empty_data_full": (
            number(wrterm, "desc_empty") == 1
            and number(wrterm, "desc_count") == 0
            and number(wrterm, "prepared_count") == 32
            and number(wrterm, "hold") == 1
        ),
    }
    if not all(dynamic.values()):
        errors.append("qualified v63 chronology differs")

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
    cloud_manifest_bound = (
        cloud.get("approved_commit") == CLOUD_RTL
        and cloud.get("local_disk_commit") == CLOUD_RTL
        and cloud.get("identity_difference_blocks_compile_or_simulation") is False
    )

    report = {
        "schema": "node0004-v63-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "V62_SILENT_EXIT_CLOSED_PEKEEP_FIX_DYNAMIC_PASS_NEW_D_SKEW_STALL",
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
                "runner_stderr_and_final_status_contract": runner_visibility_contract,
                "v62_silent_exit_escape_closed": silent_exit_escape_closed,
                "compile_invoked": compile_invoked,
                "diagnostic_feature_runtime_bound": simulation_started,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "observer_finish": "$finish at simulation time" in sim_log,
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
            "cloud_manifest_bound": cloud_manifest_bound,
            "production_compile_root_observed": (
                "/home/panqs/ndp/NDP_copy01" in compile_log
            ),
            "separate_immutable_actual_compile_commit_receipt": False,
            "identity_difference_nonblocking": True,
        },
        "LAST_PROVEN_GOOD": (
            "LC18_INDEX3_TERMINAL_ACCEPTED_BY_PE7_KEEP_INPORT0_AND_"
            "PE7_RESULT_RELEASED_WHILE_PHYSICAL_LC17_ADVANCES_TO_INDEX2"
        ),
        "FIRST_DIVERGENCE": (
            "D_DATA_PREPARE_TOTAL20_EXCEEDS_DESCRIPTOR_TOTAL18_AND_"
            "PREPARED_FIFO_REACHES32_WITH_DESCRIPTOR_FIFO_EMPTY"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_WITH_CAUSAL_SKEW_BOUNDARY_UNIQUE",
            "classification": "D_PREPARED_DATA_VS_DESCRIPTOR_TWO_GROUP_SKEW",
            "mechanism": (
                "The keep threshold fix works dynamically. Downstream, twenty "
                "16-entry data groups are prepared but only eighteen matching "
                "write descriptors are emitted and drained. The remaining two "
                "groups fill prepared storage to 32 entries; descriptor FIFO "
                "is empty, WR ready is low, upstream row/column and Buffer_AG "
                "queues backpressure, and no D last or slice-finish occurs."
            ),
            "qualified_dynamic_evidence": dynamic,
            "closed_candidates": [
                "v62 package silently exits before compile",
                "PE1 keep_last_index=3 fails to accept LC18 terminal index3",
                "PE7 drops the accepted terminal result",
                "LC17 fails to advance after LC18 terminal release",
                "descriptor FIFO loses a pushed descriptor",
                "DataHub rejects an emitted descriptor/data transaction",
            ],
            "remaining_candidates": [
                "data/tag preparation is allowed two groups ahead of live descriptor ownership",
                "Memory_AG next descriptor eligibility is cyclically blocked by prepared-data capacity",
                "Buffer_AG row/column source lifetime advances beyond the current descriptor epoch",
                "an inter-burst descriptor terminal is treated as a global lifetime boundary by one side only",
            ],
            "why_no_config_or_rtl_fix_yet": (
                "v63 reports final totals but not the first cycle at which the "
                "prepare-minus-descriptor ledger becomes positive together "
                "with the exact owner/tag/descriptor-live and next-descriptor "
                "eligibility predicates. Changing config or RTL now would "
                "select among four still-compatible mechanisms."
            ),
            "functional_rtl_root_cause_proven": False,
            "configuration_root_cause_proven": False,
        },
        "QUALIFIED_COUNTERS": {
            "canonical": canonical,
            "lc18_pe7_terminal_accept": terminal_accept,
            "lc17_next_value": next_lc17,
            "pe7_terminal_result": terminal_result,
            "lc13_lc14_lc15": lc_chain,
            "dterm_owner": dterm,
            "mse4_descriptor": descriptor,
            "mse4_index": index,
            "dwrite": dwrite,
            "rowlc4_bufag": row4,
            "wrterm": wrterm,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_V63_RUNNER_VISIBLE_START_AND_RETURN",
                "B_CONV_NODE0004_PE1_INPORT0_KEEP_LAST_INDEX_CONFIG_FIX_DYNAMIC",
                "B_CONV_NODE0004_LC18_TERMINAL_TO_PE7_AND_LC17_ADVANCE",
            ],
            "opened": [
                "B_CONV_NODE0004_D_PREPARED_DESCRIPTOR_FIRST_SKEW_CAUSE_UNOBSERVED"
            ],
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
                "The newly published nonzero-exit stderr rule is confirmed by "
                "the source runner and a real compile/simulation return. The "
                "continuous-closure and information-gain rules require one "
                "time-aligned skew-ledger successor rather than a speculative "
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
