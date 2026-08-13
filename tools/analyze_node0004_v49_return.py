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


INSTALL_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "722a1cee4b7e54564d060e202792d8179e6223570b8bfbb5fd51eac3f268637b"
SOURCE_SHA256 = "2b7faeb4b838133f041432ff707792047d113bf65871aa8936e3f2f4c502e27c"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def kv_record(text: str, marker: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if marker in line]
    if not lines:
        return {}
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", lines[-1]))


def i(record: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(record.get(key, str(default)), 0)
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
    source_manifest = json.loads(source_manifest_payload or b"{}")
    if not (
        returned.get("install_name") == INSTALL_NAME
        and returned.get("records") == records
        and returned_manifest_payload == source_manifest_payload
    ):
        errors.append("return/source manifest binding differs")
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
    observer_log = entries.get(
        "runs/c0/return_observer.log", b""
    ).decode("utf-8", errors="replace")
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    argv_log = entries.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )

    observer_sha = source_manifest.get("observer_sha256")
    package_ok = package_preflight.get("valid") is True
    install_ok = (
        install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
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
        and "NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f" in compile_driver
    )
    simulation_started = (
        "[RETURN_OBSERVER] enabled" in sim_log
        and "RETURN_OBS_LC9_ACTUAL" in argv_log
        and "LC9_ACTUAL_BOUNDARY_V1" in observer_log
    )
    if not all(
        [package_ok, install_ok, observer_ok, compile_invoked, simulation_started]
    ):
        errors.append("preflight/observer/compile/simulation binding differs")

    canonical = kv_record(observer_log, "DIAG_DECISION_V1")
    lc9 = kv_record(observer_log, "LC9_ACTUAL_BOUNDARY_V1")
    split = kv_record(observer_log, "LC9_SPLIT_BOUNDARY_V1")
    row4 = kv_record(observer_log, "ROWLC4_BUFAG_BOUNDARY_V1")
    dwrite = kv_record(observer_log, "DWRITE_PATH_BOUNDARY_V1")
    desc = kv_record(observer_log, "MSE4_DESCRIPTOR_BOUNDARY_V1")
    wrterm = kv_record(observer_log, "WRTERM2_BOUNDARY_V1")
    datahub = kv_record(observer_log, "DATAHUB_DRAIN_BOUNDARY_V1")

    dynamic_checks = {
        "canonical_hang_boundary": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and i(canonical, "qualified_progress") == 554
        ),
        "lc9_global_advance": i(lc9, "lc9_advance") == 2,
        "lc7_actual_capture": i(lc9, "lc7_capture") == 2,
        "lc7_actual_output": i(lc9, "lc7_out_accept") == 16,
        "mse3_queue_progress": (
            i(lc9, "mem3_push") == 79 and i(lc9, "mem3_pop") == 71
        ),
        "lc9_all_actual_consumers_ready": (
            i(lc9, "bp0") == 1 and i(lc9, "bp26") == 1
        ),
        "lc9_global_last0_absent": i(lc9, "lc9_last0") == 0,
        "descriptor_and_data_exact_32": (
            i(desc, "desc_hs") == 32
            and i(desc, "fifo_push") == 32
            and i(desc, "fifo_pop") == 32
            and i(desc, "ob_wr0") == 16
            and i(desc, "ob_wr1") == 16
            and i(datahub, "crossbar_accept8") == 16
            and i(datahub, "crossbar_accept9") == 16
        ),
        "source_schedule_exceeds_descriptor": (
            i(row4, "buf_push") == 53
            and i(row4, "buf_pop") == 37
            and i(row4, "bufq_full") == 1
        ),
        "post_descriptor_prefetch_present": (
            i(wrterm, "post_src_push") == 4
            and i(wrterm, "post_tag_push") == 3
            and i(wrterm, "post_prepare") == 2
            and i(wrterm, "post_prefetch_no_desc") == 1
        ),
        "no_last0_or_slice_finish": (
            i(dwrite, "tag_last0") == 0
            and i(dwrite, "buf_read_last0") == 0
            and i(dwrite, "wdata_last_accept") == 0
            and i(dwrite, "slice_finish") == 0
        ),
    }
    if not all(dynamic_checks.values()):
        errors.append("qualified v49 chronology differs")

    formal_expected = int(gate.get("formal_d_expected", 320))
    formal_present = int(gate.get("formal_d_present", 0))
    formal_missing = int(gate.get("formal_d_missing", formal_expected))
    formal_mismatch = int(gate.get("formal_d_mismatch", 0))
    natural_terminal = gate.get("natural_terminal_observed") is True
    joint = (
        compile_status == 0
        and run_status == 0
        and natural_terminal
        and formal_present == formal_expected
        and formal_missing == 0
        and formal_mismatch == 0
    )
    returned_cloud = source_manifest.get("cloud_rtl_authority", {})
    cloud_bound = (
        returned_cloud.get("approved_commit") == CLOUD_RTL
        and returned_cloud.get("local_disk_commit") == CLOUD_RTL
        and returned_cloud.get(
            "identity_difference_blocks_compile_or_simulation"
        )
        is False
    )

    report = {
        "schema": "node0004-v49-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "LONG_RUNNING_HANG_AFTER_LC9_ACTUAL_BRANCH_CROSSED",
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
                "compile_invoked": compile_invoked,
                "production_vcs_compile": compile_status == 0,
                "diagnostic_simulation_started": simulation_started,
                "actual_argv_feature_bound": (
                    "RETURN_OBS_LC9_ACTUAL" in argv_log
                ),
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "diagnostic_finish_not_natural_terminal": (
                run_status == 0 and not natural_terminal
            ),
            "natural_terminal": natural_terminal,
            "formal_d_expected": formal_expected,
            "formal_d_present": formal_present,
            "formal_d_missing": formal_missing,
            "formal_d_mismatch": formal_mismatch,
            "joint_result_gate": joint,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "ACTUAL_RTL_IDENTITY": {
            "source_manifest_cloud_commit": returned_cloud.get(
                "approved_commit"
            ),
            "source_manifest_bound": cloud_bound,
            "production_compile_root_observed": (
                "/home/panqs/ndp/NDP_copy01" in compile_log
            ),
            "actual_compile_commit_receipt_present": False,
            "adjudication": (
                "Production VCS/filelist and the returned package manifest "
                "bind the causal cone to 0cc. No separate immutable Git "
                "receipt is returned; any identity difference is recorded "
                "as nonblocking causal risk after successful compile."
            ),
        },
        "LAST_PROVEN_GOOD": (
            "LC9_GLOBAL_ACCEPT_TO_LC7_CAPTURE_AND_MSE3_QUEUE_PROGRESS_"
            "PLUS_32_DESCRIPTOR_DATAHUB_WRITES"
        ),
        "FIRST_DIVERGENCE": (
            "D_BUFFER_SOURCE_SCHEDULE_CONTINUES_AFTER_MEMORY_DESCRIPTOR_"
            "TERMINAL_WITHOUT_LAST_INDEX0_PROPAGATION"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_AFTER_HIGH_INFORMATION_V49_RETURN",
            "classification": "TERMINAL_OWNER_OR_SCHEDULE_LIFETIME_MISMATCH",
            "qualified_dynamic_evidence": dynamic_checks,
            "closed_hypothesis": (
                "LC9 output was not blocked by either actual destination; "
                "LC7 captured it and MSE3 independently enqueued/drained."
            ),
            "remaining_candidates": [
                "LC13->LC14->LC15 does not deliver the expected global-last0 parent to LC9",
                "LC15 reaches LC9 but LC9 counter/inbuffer does not release the terminal",
                "GROUP4 row/column expansion outlives the 32 memory descriptors",
                "Buffer_AG tag selection suppresses or mis-owns the last-index-zero terminal",
                "descriptor-unaware bounded prefetch is only a consequence, not the root",
            ],
            "why_not_configuration_fix_yet": (
                "The return proves an exact 32-descriptor/data write set and "
                "a 53-push Buffer source schedule, but it does not expose the "
                "LC13/14/15 parent terminal or the GROUP4 selected terminal "
                "owner. Changing a loop end/mode now would be a guess."
            ),
            "next_boundary": (
                "One triggered owner-chain observer must count qualified "
                "LC13/14/15/9 advances and last0, GROUP4 row/column output "
                "accepts and Buffer_AG selected tags, descriptor terminal, "
                "and the first post-descriptor source transaction."
            ),
            "functional_rtl_root_cause_proven": False,
            "configuration_root_cause_proven": False,
        },
        "QUALIFIED_COUNTERS": {
            "canonical": canonical,
            "lc9_actual": lc9,
            "lc9_split_state_corroboration": split,
            "group4_buffer": row4,
            "descriptor": desc,
            "dwrite": dwrite,
            "wrterm": wrterm,
            "datahub": datahub,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_LC9_TO_LC7_AND_MSE3_ACTUAL_BRANCH_ACCEPT_UNOBSERVED",
            ],
            "opened": [
                "B_CONV_NODE0004_D_TERMINAL_OWNER_CHAIN_UNOBSERVED",
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
            "status": "CURRENT_RULES_CORRECTLY_FORCE_CONTINUOUS_CLOSURE",
            "confirmed_rule_ids": [
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
                "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            ],
            "evidence": (
                "v49 separates qualified LC9/LC7/MSE3 handshakes from held "
                "levels, closes that local hypothesis, and leaves exactly one "
                "downstream terminal-owner diagnostic slice."
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
