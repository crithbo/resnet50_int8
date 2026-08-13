from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (
    integer_entry,
    load_json,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL = "r5_n4_hw_v50_dterm_owner_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "5401413f1586e8b7de4ad6ed2be2f8b2a0b4eea5072a80349b5b3217601e9d8a"
SOURCE_SHA = "c8a809f8ebb723c286b5c0190bcd1142f9ba2d8965731b8ee194182c0922c830"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def kv(text: str, marker: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if marker in line]
    return (
        dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", lines[-1]))
        if lines else {}
    )


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
    records = allow.get("records", [])
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
            errors.append(f"receipt differs:{path}")
    if set(entries) != expected:
        errors.append("return exact-set differs")
    source_manifest_bytes = source.get("package_manifest.json", b"")
    returned_manifest_bytes = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    manifest = json.loads(source_manifest_bytes or b"{}")
    if not (
        returned.get("install_name") == INSTALL
        and returned.get("records") == records
        and returned_manifest_bytes == source_manifest_bytes
    ):
        errors.append("return/source binding differs")
    source_files = manifest.get("files", {})
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
    argv = entries.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )
    observer_sha = manifest.get("observer_sha256")
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
        and "NDP_Top_phy_filelist.f" in compile_driver
    )
    simulation_started = (
        "[RETURN_OBSERVER] enabled" in sim_log
        and "+RETURN_OBS_DTERM_OWNER" in argv
        and "DTERM_OWNER_BOUNDARY_V1" in observer_log
        and feature_binding.get("valid") is True
    )
    if not all((package_ok, install_ok, observer_ok, compile_invoked, simulation_started)):
        errors.append("preflight/compile/simulation binding differs")

    canonical = kv(observer_log, "CANONICAL_DIAG_DECISION_V1")
    dterm = kv(observer_log, "DTERM_OWNER_BOUNDARY_V1")
    row4 = kv(observer_log, "ROWLC4_BUFAG_BOUNDARY_V1")
    descriptor = kv(observer_log, "MSE4_DESCRIPTOR_BOUNDARY_V1")
    wrterm = kv(observer_log, "WRTERM2_BOUNDARY_V1")
    dynamic = {
        "canonical_same_hang": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and number(canonical, "qualified_progress") == 554
        ),
        "lc9_terminal_really_accepted": (
            number(dterm, "lc9_adv") == 2
            and number(dterm, "lc9_last0") == 1
        ),
        "lc13_only_one_nonterminal_advance": (
            number(dterm, "lc13_adv") == 1
            and number(dterm, "lc13_last0") == 0
        ),
        "lc14_lc15_never_release": (
            number(dterm, "lc14_adv") == 0
            and number(dterm, "lc15_adv") == 0
        ),
        "group4_no_terminal": (
            number(dterm, "row_out") == 42
            and number(dterm, "col_out") == 69
            and number(dterm, "row_last0") == 0
            and number(dterm, "col_last0") == 0
        ),
        "buffer_selected_terminal_absent": (
            number(dterm, "buf_push") == 53
            and number(dterm, "buf_pop") == 37
            and number(dterm, "buf_last0") == 0
        ),
        "descriptor_terminal_then_source_continues": (
            number(dterm, "desc_push") == 32
            and number(dterm, "desc_pop") == 32
            and number(dterm, "post_desc_buf_push") == 3
        ),
        "corroborating_source_counts": (
            number(row4, "buf_push") == 53
            and number(row4, "buf_pop") == 37
            and number(descriptor, "fifo_push") == 32
            and number(descriptor, "fifo_pop") == 32
            and number(wrterm, "post_src_push") == 4
        ),
    }
    if not all(dynamic.values()):
        errors.append("qualified v50 chronology differs")

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
    cloud_bound = (
        cloud.get("approved_commit") == CLOUD_RTL
        and cloud.get("local_disk_commit") == CLOUD_RTL
        and cloud.get("identity_difference_blocks_compile_or_simulation") is False
    )
    report = {
        "schema": "node0004-v50-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "RUN_COMPLETED_DIAGNOSTIC_HANG_LC13_TO_LC14_BOUNDARY",
            "user_attested_run_completed": True,
            "external_interruption_assumption_applied": False,
            "return_zip": {
                "path": str(ret), "bytes": ret.stat().st_size, "sha256": ret_sha
            },
            "source_zip": {
                "path": str(src), "bytes": src.stat().st_size,
                "sha256": src_sha, "sidecar_valid": sidecar_valid
            },
            "return_meta": ret_meta,
            "source_meta": src_meta,
            "checks": {
                "crc_root_path": not ret_errors,
                "exact_set_allowlist_receipts": set(entries) == expected,
                "source_manifest_binding": returned_manifest_bytes == source_manifest_bytes,
                "package_preflight": package_ok,
                "install_preflight_runtime_d_absent": install_ok,
                "observer_precompile": observer_ok,
                "compile_invoked": compile_invoked,
                "diagnostic_feature_runtime_bound": simulation_started,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "observer_finish": "$finish called from file" in sim_log,
            "natural_terminal": natural,
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
            "manifest_cloud_commit": cloud.get("approved_commit"),
            "cloud_identity_bound": cloud_bound,
            "production_compile_root_observed": "/home/panqs/ndp/NDP_copy01" in compile_log,
            "separate_immutable_compile_commit_receipt": False,
            "difference_nonblocking_causal_risk": True,
        },
        "LAST_PROVEN_GOOD": (
            "LC9_ACCEPTS_TRUE_LAST_INDEX0_AND_D_WRITES_32_DESCRIPTORS_"
            "WHILE_LC13_RELEASES_FIRST_NONTERMINAL_VALUE"
        ),
        "FIRST_DIVERGENCE": (
            "LC13_SECOND_OR_TERMINAL_VALUE_NOT_GLOBALLY_ACCEPTED_"
            "AND_LC14_LC15_NEVER_RELEASE"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_WITH_FIRST_BOUNDARY_UNIQUELY_LOCALIZED",
            "classification": "LC13_TO_LC14_NESTED_LOOP_RELEASE_OR_SAME_GOTTEN",
            "qualified_dynamic_evidence": dynamic,
            "important_correction": (
                "v49 LC9_ACTUAL lc9_last0=0 decoded low data bits [5:0]. "
                "v50 DTERM uses real tag bits [21] and [19:16] and proves one "
                "accepted LC9 last-index-zero event."
            ),
            "closed_candidates": [
                "LC15-to-LC9 terminal loss",
                "LC9 terminal generation failure",
                "Buffer_AG terminal selection as the first divergence",
                "descriptor terminal as the first divergence",
            ],
            "remaining_candidates": [
                "LC13 second value is held by LC14 backpressure",
                "LC14 source selection or same-gotten suppresses LC13 second value",
                "LC14 counter accepts input but cannot emit toward LC15",
                "LC13 local counter/output state fails to mark or release its terminal",
            ],
            "why_no_config_fix": (
                "The return proves the first non-advancing link but does not "
                "expose LC13 downstream-ready, LC14 selected input/same-gotten, "
                "or LC14 counter occupancy. A config change would still guess."
            ),
            "functional_rtl_root_cause_proven": False,
            "configuration_root_cause_proven": False,
        },
        "QUALIFIED_COUNTERS": {
            "canonical": canonical,
            "dterm_owner": dterm,
            "group4": row4,
            "descriptor": descriptor,
            "wrterm": wrterm,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_D_TERMINAL_OWNER_CHAIN_UNOBSERVED",
                "B_CONV_NODE0004_LC9_TRUE_LAST0_UNOBSERVED",
            ],
            "opened": [
                "B_CONV_NODE0004_LC13_TO_LC14_TERMINAL_RELEASE_UNOBSERVED"
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
            "status": "CURRENT_RULES_SUFFICIENT_NO_DELTA",
            "evidence": (
                "Qualified tag-bit decoding and one high-information owner-chain "
                "observer move the boundary upstream without guessing config."
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
