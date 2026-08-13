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
    integer_entry, load_json, safe_entries, sha256_bytes, sha256_file,
)

INSTALL = "r5_n4_hw_v68_pe7_pair_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "2a39ff084c605e06343fba9b6193d1e5666640f519266a5aa2d1f332b807d97e"
SOURCE_SHA = "372c6135f064dfb5847bedfea3741b8724113eb8e3b0c7f644e87f4fa877fdee"
EXECUTION = "r1786179996625945329_4055038"
MAPPING_REVIEW = ROOT / "artifacts/operator_config_validation/r5-node0004-pe1-keep-last-index-fix-c0-v62/mapping/conv/op_w0/mapping_review.json"


def rows(text: str, marker: str) -> list[dict[str, str]]:
    return [dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
            for line in text.splitlines() if marker in line]


def num(row: dict[str, str], key: str, base: int = 10) -> int:
    try:
        return int(row.get(key, "-1"), base)
    except ValueError:
        return -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", required=True, type=Path)
    ap.add_argument("--source-zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    errors: list[str] = []
    rsha, ssha = sha256_file(a.return_zip), sha256_file(a.source_zip)
    if rsha != RETURN_SHA:
        errors.append("return_sha256_mismatch")
    if ssha != SOURCE_SHA:
        errors.append("source_sha256_mismatch")
    ret, re_err, rmeta = safe_entries(a.return_zip, RETURN_ROOT)
    src, se_err, smeta = safe_entries(a.source_zip, INSTALL)
    errors += re_err + se_err

    allow = load_json(ret, "RETURN_ALLOWLIST.json")
    rm = load_json(ret, "RETURN_MANIFEST.json")
    records = allow.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipt_errors: list[str] = []
    for record in records:
        path = record.get("path")
        if not isinstance(path, str):
            receipt_errors.append("invalid_path")
            continue
        expected.add(path)
        data = ret.get(path)
        if data is None:
            receipt_errors.append(f"missing:{path}")
        elif len(data) != record.get("size_bytes"):
            receipt_errors.append(f"size:{path}")
        elif sha256_bytes(data) != record.get("sha256"):
            receipt_errors.append(f"sha:{path}")
    exact = set(ret) == expected
    if not exact:
        errors.append("return_exact_set_mismatch")
    errors += receipt_errors

    pm_bytes = src.get("package_manifest.json", b"")
    pm = json.loads(pm_bytes or b"{}")
    source_binding = (
        ret.get("evidence/returned_package_manifest.json") == pm_bytes
        and rm.get("install_name") == INSTALL
        and rm.get("records") == records
        and rm.get("fixed_result_publication", {}).get("return_zip", "")
        .endswith(f"{INSTALL}_{EXECUTION}_return.zip")
    )
    if not source_binding:
        errors.append("source_or_execution_binding_mismatch")
    source_exact = (
        set(pm.get("files", {})) == set(src) - {"package_manifest.json"}
        and all(path in src and sha256_bytes(src[path]) == digest
                for path, digest in pm.get("files", {}).items())
    )
    if not source_exact:
        errors.append("source_exact_set_mismatch")

    gate = load_json(ret, "evidence/SERVER_RESULT_GATE.json")
    fb = load_json(ret, "evidence/diagnostic_feature_binding.json")
    pf = load_json(ret, "evidence/package_preflight.json")
    ip = load_json(ret, "evidence/install_preflight.json")
    op = load_json(ret, "evidence/observer_precompile.json")
    rg = load_json(ret, "evidence/ndp_root_toplevel_gate.json")
    pub = load_json(ret, "evidence/publication_preflight.json")
    cs = integer_entry(ret, "evidence/compile_exit_status.txt", 125)
    rs = integer_entry(ret, "evidence/run_exit_status.txt", 125)
    signal = ret.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    obs = ret.get("runs/c0/return_observer.log", b"").decode(errors="replace")
    sim = ret.get("runs/c0/sim.log", b"").decode(errors="replace")
    argv = ret.get("runs/c0/simulator_argv.txt", b"").decode(errors="replace")
    cdriver = ret.get("runs/compile/sim_results/compile_driver.log", b"").decode(errors="replace")
    osha = pm.get("observer_sha256")
    preflight = {
        "package": pf.get("valid") is True,
        "install_reset": ip.get("valid") is True and ip.get("runtime_d_initially_absent") is True,
        "root_direct_set": rg.get("valid") is True and rg.get("ndp_root_toplevel_unchanged") is True,
        "publication": pub.get("publication_state") == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
        "observer": op.get("valid") is True and op.get("observed_sha256") == osha
                    and sha256_bytes(src.get("tb_probe/native_return_observer.svh", b"")) == osha,
        "feature": fb.get("valid") is True,
    }
    if not all(preflight.values()):
        errors.append("preflight_binding_failure")
    compile_ok = cs == 0 and "vcs" in cdriver.lower() and "Compilation completed!" in cdriver
    sim_ok = rs == 0 and signal == "NONE" and "[RETURN_OBSERVER] enabled" in sim \
             and "+RETURN_OBS_PE7_PAIR" in argv
    if not compile_ok:
        errors.append("compile_binding_failure")
    if not sim_ok:
        errors.append("simulation_binding_failure")

    pe = rows(obs, "PE7_PAIR_V1")
    pe_final = pe[-1] if pe else {}
    row = rows(obs, "ROWLC4_BUFAG_BOUNDARY_V1")
    row_final = row[-1] if row else {}
    mapping = json.loads(MAPPING_REVIEW.read_text(encoding="utf-8"))
    lc18_edges = [x for x in mapping["connection_mapping"] if x.get("src_resource") == "LC18"]
    mapping_destinations = sorted(x.get("dst_resource") for x in lc18_edges)

    bp = num(pe_final, "lc18_bp", 16)
    low_bits = [bit for bit in range(33) if bp >= 0 and not ((bp >> bit) & 1)]
    pe7_ok = {
        "input0_accept": num(pe_final, "lc15_in0"),
        "input2_accept": num(pe_final, "lc18_in2"),
        "matches": num(pe_final, "match"),
        "outbuffer_writes": num(pe_final, "ob_wr"),
        "outbuffer_reads": num(pe_final, "ob_rd"),
        "outputs": num(pe_final, "pe_out"),
        "tenth_input2_ready": bool(num(pe_final, "bp", 16) & 0x4),
        "input2_same_gotten_suppressed": (
            bool(num(pe_final, "in_valid", 16) & 0x4)
            and not bool(num(pe_final, "in_masked", 16) & 0x4)
            and bool(num(pe_final, "gotten", 16) & 0x4)
        ),
    }
    branch_cycle = {
        "lc18_destinations_from_final_mapping": mapping_destinations,
        "lc18_bp_vector_hex": pe_final.get("lc18_bp"),
        "only_low_destination_bit": low_bits,
        "bit10_is_ROW_LC4": low_bits == [10] and "ROW_LC4" in mapping_destinations,
        "PE7_input2_is_ready": pe7_ok["tenth_input2_ready"],
        "row_buffer_queue_full": num(row_final, "bufq_full") == 1,
        "rd_buffer_full": num(row_final, "rd_full") == 1,
        "wr_data_not_ready": num(row_final, "wr_ready") == 0,
        "prepared_data_count": num(row_final, "prepared_count"),
        "prepared_data_backpressure": num(row_final, "prepared_bp") == 0,
        "buffer_push_pop": [num(row_final, "buf_push"), num(row_final, "buf_pop")],
    }
    evidence_ok = (
        pe7_ok["input0_accept"] == 2 and pe7_ok["input2_accept"] == 9
        and pe7_ok["matches"] == pe7_ok["outbuffer_writes"] == pe7_ok["outbuffer_reads"] == pe7_ok["outputs"] == 9
        and pe7_ok["tenth_input2_ready"] and pe7_ok["input2_same_gotten_suppressed"]
        and branch_cycle["bit10_is_ROW_LC4"] and branch_cycle["row_buffer_queue_full"]
        and branch_cycle["rd_buffer_full"] and branch_cycle["wr_data_not_ready"]
        and branch_cycle["prepared_data_count"] == 32 and branch_cycle["prepared_data_backpressure"]
    )
    if not evidence_ok:
        errors.append("v68_causal_evidence_unexpected")

    natural = gate.get("natural_terminal_observed") is True
    fe = int(gate.get("formal_d_expected", 320)); fp = int(gate.get("formal_d_present", 0))
    fm = int(gate.get("formal_d_missing", fe)); fx = int(gate.get("formal_d_mismatch", 0))
    joint = compile_ok and sim_ok and natural and fp == fe and fm == 0 and fx == 0
    report = {
        "schema": "node0004-v68-pe7-pair-return-analysis-v1",
        "status": "PASS" if not errors else "FAIL", "errors": errors,
        "identity": {"return_path": str(a.return_zip.resolve()), "return_bytes": a.return_zip.stat().st_size,
                     "return_sha256": rsha, "source_path": str(a.source_zip.resolve()),
                     "source_bytes": a.source_zip.stat().st_size, "source_sha256": ssha,
                     "execution_id": EXECUTION, "actual_compile_identity": pm.get("cloud_rtl_authority")},
        "archive": {"return": rmeta, "source": smeta, "return_crc": not re_err,
                    "return_exact_set": exact, "per_file_receipts": not receipt_errors,
                    "source_binding": source_binding, "source_exact_set": source_exact},
        "preflight": preflight,
        "runtime": {"compile_exit": cs, "run_exit": rs, "signal": signal,
                    "compile_bound": compile_ok, "simulation_bound": sim_ok,
                    "canonical": gate.get("canonical_decision")},
        "physical_pe7_tenth_pair_adjudication": pe7_ok,
        "lc18_fanout_backpressure_adjudication": branch_cycle,
        "last_proven_good": "SECOND_EPOCH_LC18_Q0_REACHES_PE7_AND_COMPLETES_NINTH_MATCH_WRITE_READ_OUTPUT",
        "first_divergence": "LC18_NEXT_TOKEN_IS_BLOCKED_ONLY_BY_ROW_LC4_BIT10_WHILE_PE7_INPUT2_REMAINS_READY",
        "hang_root_cause": {
            "status": "UNRESOLVED_AT_BUFFER_BRANCH_DRAIN_CAUSE",
            "classification": "DETERMINISTIC_CROSS_BRANCH_BACKPRESSURE_CYCLE_BOUNDARY",
            "reason": "v68 closes every PE7-local candidate. LC18 has exactly two configured consumers (ROW_LC4 and PE7); its final 33-bit destination-ready vector has only bit10 low, which is ROW_LC4, while PE7 input2 is ready. ROW_LC4 feeds a full Buffer_AG queue, the RD_Buffer_AG is full, WR data has 32 prepared elements and is not ready. The return does not expose the exact WR request/prepared-data drain conjunction, so it cannot yet distinguish missing address-request descriptor, request-channel backpressure, or prepared-data/output-channel ownership."
        },
        "next_candidate_matrix": {
            "address_request_queue_empty": "Memory_AG match/queue/output and WR_Data request queue empty/read/write",
            "prepared_data_cannot_join_request": "prepared count/valid plus request size and wr_chl_ob write handshake",
            "memory_write_channel_backpressure": "mse2mem request/wdata valid-ready per channel",
            "buffer_read_return_not_accepted": "RD_Buffer read request/return and WR data ready/hold chronology",
        },
        "formal_result": {"natural_terminal": natural, "expected": fe, "present": fp,
                          "missing": fm, "mismatch": fx,
                          "all_missing_is_not_numeric_pass": fp == 0 and fm == fe and fx == 0,
                          "joint_gate": joint, "E3": compile_ok and sim_ok, "E4": joint, "E5": False},
        "blocker_delta": {
            "closed": ["B_CONV_NODE0004_PE7_TENTH_PAIR_FIRST_MISSING_BOUNDARY_UNOBSERVED",
                       "B_CONV_NODE0004_V67_PE1_PAIR_OBSERVER_PHYSICAL_TARGET_MISMATCH"],
            "opened": ["B_CONV_NODE0004_ROWLC4_BUFFER_BRANCH_DRAIN_CONJUNCTION_UNOBSERVED"],
            "remains": ["B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL", "B_CONV_NODE0004_FORMAL_D_320"],
            "invalidated_not_reopened": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "frozen": {"numeric_analysis_repeated": False, "workload_rebuilt": False,
                   "configuration_rebuilt": False, "golden_rebuilt": False,
                   "functional_rtl_modified": False, "server_action": False},
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
