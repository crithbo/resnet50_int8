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


INSTALL_NAME = "r5_n4_hw_v43_wrterm2_compilefix"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "5ed315d6121dba0a7e2bc81b9672ab8604c66a5b32b280b647dbc2e5af6b4e11"
SOURCE_SHA256 = "ba3c2df775c8f7f7bef47eec15d079651eb7c60e20145aca7dedef7345fe54e2"
OBSERVER_SHA256 = "57c960833a1242ba77d48ea6ebf96027bfe1d0e527c0fc0bc234b993bda63553"


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
    exact_set = set(entries) == expected
    if not exact_set:
        errors.append("return exact-set differs")

    source_manifest_payload = source.get("package_manifest.json", b"")
    returned_manifest_payload = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    manifest_binding = (
        returned.get("install_name") == INSTALL_NAME
        and returned.get("records") == records
        and returned_manifest_payload == source_manifest_payload
    )
    if not manifest_binding:
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

    observer_identity = (
        sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
        == OBSERVER_SHA256
    )
    production_compile_passed = (
        compile_status == 0
        and "0 error(s)" in compile_log
        and "VCS" in compile_log
        and "vcs" in compile_driver.lower()
        and "mem_idx_gotten" not in compile_log
    )
    package_ok = package_preflight.get("valid") is True
    install_ok = (
        install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
    )
    observer_ok = (
        observer_preflight.get("valid") is True
        and observer_preflight.get("observed_sha256") == OBSERVER_SHA256
        and observer_identity
    )
    features_ok = (
        feature_binding.get("valid") is True
        and all(item.get("valid") is True for item in feature_binding.get("features", []))
    )
    dynamic_ok = (
        run_status == 0
        and signal == "NONE"
        and "$finish at simulation time" in sim_log
        and "CANONICAL_DIAG_DECISION_V1" in observer_log
    )
    if not all([package_ok, install_ok, observer_ok, features_ok]):
        errors.append("preflight/observer/feature binding differs")
    if not production_compile_passed:
        errors.append("production compile did not prove v41 XMRE crossed")
    if not dynamic_ok:
        errors.append("diagnostic simulation evidence incomplete")

    wr_edges = [
        line for line in observer_log.splitlines() if "WRTERM2_EDGE_V1" in line
    ]
    wr_final = [
        line
        for line in observer_log.splitlines()
        if "WRTERM2_FINAL_POP_V1" in line
    ]
    wr_boundary_lines = [
        line
        for line in observer_log.splitlines()
        if "WRTERM2_BOUNDARY_V1" in line
    ]
    dwrite_lines = [
        line
        for line in observer_log.splitlines()
        if "DWRITE_PATH_BOUNDARY_V1" in line
    ]
    mse_index_lines = [
        line
        for line in observer_log.splitlines()
        if "MSE4_INDEX_BOUNDARY_V1" in line
    ]
    if not (
        len(wr_final) == 1
        and len(wr_boundary_lines) == 1
        and len(dwrite_lines) == 1
        and len(mse_index_lines) == 1
    ):
        errors.append("required unique boundary records differ")
    wr = parse_fields(wr_boundary_lines[0]) if wr_boundary_lines else {}
    dw = parse_fields(dwrite_lines[0]) if dwrite_lines else {}
    mi = parse_fields(mse_index_lines[0]) if mse_index_lines else {}
    edge_fields = [parse_fields(line) for line in wr_edges]

    chronology = {
        "descriptor_fifo_one_to_zero_candidate_count": len(wr_final),
        "post_descriptor_push": int(wr.get("post_desc_push", "-1")),
        "post_descriptor_pop": int(wr.get("post_desc_pop", "-1")),
        "post_source_push": int(wr.get("post_src_push", "-1")),
        "post_source_pop": int(wr.get("post_src_pop", "-1")),
        "post_tag_push": int(wr.get("post_tag_push", "-1")),
        "post_tag_pop": int(wr.get("post_tag_pop", "-1")),
        "post_prepare": int(wr.get("post_prepare", "-1")),
        "post_prefetch_no_desc": int(wr.get("post_prefetch_no_desc", "-1")),
        "post_last0": int(wr.get("post_last0", "-1")),
        "source_replay_edges": sum(
            int(item.get("src_replay", "0")) for item in edge_fields
        ),
        "final_desc_head_last": int(wr.get("head_last", "-1")),
        "final_desc_head_index": int(wr.get("head_index", "-1")),
        "final_source_count": int(wr.get("src_count", "-1")),
        "final_tag_count": int(wr.get("tag_count", "-1")),
        "final_prepared_count": int(wr.get("prepared_count", "-1")),
        "dwrite_tag_last": int(dw.get("tag_last", "-1")),
        "dwrite_tag_last0": int(dw.get("tag_last0", "-1")),
        "dwrite_prepare_last": int(dw.get("prepare_last", "-1")),
        "dwrite_wdata_last": int(dw.get("wdata_last_accept", "-1")),
        "slice_finish": int(dw.get("slice_finish", "-1")),
        "memory_index_accept1": int(mi.get("accept1", "-1")),
        "memory_index_finish": int(mi.get("finish", "-1")),
        "memory_descriptor_count": int(mi.get("desc", "-1")),
        "memory_input_valid": mi.get("input_vld"),
        "memory_input_same": mi.get("input_same"),
        "memory_input_gotten": mi.get("gotten"),
        "memory_input_bp": mi.get("input_bp"),
        "memory_matched": int(mi.get("matched", "-1")),
    }
    chronology_ok = (
        chronology["post_descriptor_push"] == 0
        and chronology["post_source_push"] == 19
        and chronology["post_source_pop"] == 3
        and chronology["post_prepare"] == 2
        and chronology["post_prefetch_no_desc"] == 1
        and chronology["source_replay_edges"] == 0
        and chronology["final_desc_head_last"] == 1
        and chronology["final_desc_head_index"] == 5
        and chronology["post_last0"] == 0
        and chronology["dwrite_tag_last0"] == 0
        and chronology["dwrite_prepare_last"] == 0
        and chronology["dwrite_wdata_last"] == 0
        and chronology["slice_finish"] == 0
        and chronology["memory_index_finish"] == 16
        and chronology["memory_descriptor_count"] == 32
        and chronology["memory_input_valid"] == "0x5"
        and chronology["memory_input_same"] == "0x5"
        and chronology["memory_input_gotten"] == "0x2"
        and chronology["memory_input_bp"] == "0x2"
        and chronology["memory_matched"] == 0
    )
    if not chronology_ok:
        errors.append("qualified WRTERM2/MSE4 chronology differs")

    formal_present = 0
    formal_expected = 320
    natural_terminal = gate.get("natural_terminal_observed") is True
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and natural_terminal
        and formal_present == formal_expected
    )
    report = {
        "schema": "node0004-v43-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "COMPILE_FIX_CROSSED_DYNAMIC_STALL_REFINED",
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
                "return_exact_set_allowlist_receipts": exact_set
                and all(receipts.values()),
                "return_source_manifest_binding": manifest_binding,
                "source_crc_path_root": not source_errors,
                "source_manifest_exact_set": source_exact,
                "package_preflight": package_ok,
                "install_preflight_runtime_d_absent": install_ok,
                "observer_precompile_identity": observer_ok,
                "diagnostic_feature_binding": features_ok,
                "production_vcs_compile_crossed_v41_xmre": production_compile_passed,
                "diagnostic_simulation_started": dynamic_ok,
                "qualified_wrterm_chronology": chronology_ok,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "natural_terminal": natural_terminal,
            "formal_d_expected": formal_expected,
            "formal_d_present": formal_present,
            "formal_d_missing": formal_expected - formal_present,
            "formal_d_mismatch": 0,
            "joint_result_gate": joint_gate,
            "E3": production_compile_passed and dynamic_ok,
            "E4": False,
            "E5": False,
        },
        "qualified_chronology": chronology,
        "LAST_PROVEN_GOOD": (
            "32_MEMORY_DESCRIPTORS_CONSUMED_AND_DESCRIPTOR_FIFO_DRAINS_"
            "WHILE_BUFFER_DATA_PATH_REMAINS_ACTIVE"
        ),
        "FIRST_DIVERGENCE": (
            "MSE4_MEMORY_BUFFER_CARRIER_STOPS_BEFORE_GLOBAL_LAST0_WHILE_"
            "BUFFER_AG_SOURCE_CONTINUES_TO_CAPACITY"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "UNRESOLVED_REQUIRES_SHARED_LC9_BRANCH_DIAGNOSTIC",
            "excluded": {
                "v41_private_xmr_compile_failure": True,
                "consecutive_source_replay": chronology[
                    "source_replay_edges"
                ] == 0,
                "descriptor_fifo_pop_is_global_true_final": False,
                "old_outbuffer_occupancy_theory": "INVALIDATED_NOT_RTL_BUG",
            },
            "reason": (
                "The FIFO 1->0 pop carries last_index 5, not global last_index "
                "0. Afterwards the Memory-AG buffer carrier is absent/gotten "
                "while keep inputs remain same, no descriptor is produced, and "
                "the Buffer-AG branch continues until source/tag/prepared "
                "capacity. The return does not expose which LC9->PE1/Buffer-AG "
                "consumer first stops acknowledging the shared producer."
            ),
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_V41_OBSERVER_MEM_IDX_GOTTEN_XMRE",
                "B_CONV_NODE0004_WRTERM_TRUE_FINAL_DESCRIPTOR_IDENTITY_UNOBSERVED",
            ],
            "opened": [
                "B_CONV_NODE0004_SHARED_LC9_TO_MEMORY_AND_BUFFER_BRANCH_ACCEPT_UNOBSERVED"
            ],
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
