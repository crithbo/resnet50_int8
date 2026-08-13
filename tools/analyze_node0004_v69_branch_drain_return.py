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

INSTALL = "r5_n4_hw_v69_branch_drain_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "ac7ccf08989db2b7afebaa1937ce7b337acfb16e94fffa39878bcf6b86f36ddb"
SOURCE_SHA = "e6c94bf8b38e8e0ff7aed6984782a874a665938930dc5f91357323592c2e88eb"
EXECUTION = "r1786189341014104411_4099642"


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
             and "+RETURN_OBS_BRANCH_DRAIN" in argv
    if not compile_ok:
        errors.append("compile_binding_failure")
    if not sim_ok:
        errors.append("simulation_binding_failure")

    branch = rows(obs, "BRANCH_DRAIN_V1")
    final = branch[-1] if branch else {}
    first_desc18 = next((i for i, x in enumerate(branch) if num(x, "desc") == 18), -1)
    first_post_desc_prep = next((i for i, x in enumerate(branch)
                                 if first_desc18 >= 0 and i >= first_desc18
                                 and num(x, "desc") == 18 and num(x, "prep_wr") >= 19), -1)
    second_post_desc_prep = next((i for i, x in enumerate(branch)
                                  if first_desc18 >= 0 and i >= first_desc18
                                  and num(x, "desc") == 18 and num(x, "prep_wr") >= 20), -1)
    chronology = {
        "final_descriptor_index": first_desc18,
        "first_prepared_write_beyond_descriptor_index": first_post_desc_prep,
        "second_prepared_write_beyond_descriptor_index": second_post_desc_prep,
        "final_descriptor_count": num(final, "desc"),
        "descriptor_request_count": num(final, "req"),
        "write_data_count": num(final, "wdata"),
        "prepared_write_count": num(final, "prep_wr"),
        "prepared_read_count": num(final, "prep_rd"),
        "prepared_surplus": num(final, "prep_wr") - num(final, "prep_rd"),
        "buffer_queue_push_pop": [num(final, "buf_push"), num(final, "buf_pop")],
        "rd_buffer_write_read": [num(final, "rd_wr"), num(final, "rd_rd")],
        "buffer_request_return": [num(final, "buf_req"), num(final, "buf_ret")],
        "memory_index_match_push_pop": [num(final, "mem_match"), num(final, "memq_push"), num(final, "memq_pop")],
    }
    candidates = {
        "address_request_queue": {
            "decision": "EXCLUDED_AS_FINAL_STALL_OWNER",
            "evidence": "memory index push/pop are 9/9, descriptor input is invalid, and request queue is empty at the final snapshot",
            "memq_empty": num(final, "memq_empty") == 1,
            "reqq_empty": num(final, "reqq_empty") == 1,
        },
        "prepared_data_request_join": {
            "decision": "CONFIRMED_FIRST_PERSISTENT_SKEW_BOUNDARY",
            "evidence": "all 18 descriptors drain, then prepared writes advance to 19 and 20 while descriptor count stays 18; final prepared occupancy is 32 and write-ready is low",
            "post_descriptor_prepared_writes": chronology["prepared_surplus"],
            "prepared_full": num(final, "prep_count") == 32 and num(final, "prep_bp") == 0,
        },
        "memory_channel_backpressure": {
            "decision": "EXCLUDED_AS_CAUSE",
            "evidence": "final request/wdata valid are zero while both ready bits are high; matched index queue fully drains",
            "request_valid": num(final, "req_v", 16),
            "request_ready": num(final, "req_r", 16),
            "wdata_valid": num(final, "wdata_v", 16),
            "wdata_ready": num(final, "wdata_r", 16),
        },
        "buffer_read_return_acceptance": {
            "decision": "DOWNSTREAM_BACKPRESSURE_CONSEQUENCE_NOT_FIRST_DIVERGENCE",
            "evidence": "21 read requests yield 18 returns and 20 prepared writes; once the two surplus prepared groups fill the join buffer, write-ready deasserts and three read requests remain outstanding",
            "outstanding_read_requests": num(final, "buf_req") - num(final, "buf_ret"),
            "rd_buffer_full": num(final, "rd_full") == 1,
        },
    }
    evidence_ok = (
        chronology["final_descriptor_count"] == 18
        and chronology["prepared_write_count"] == 20
        and chronology["prepared_read_count"] == 18
        and first_post_desc_prep >= first_desc18 >= 0
        and second_post_desc_prep >= first_post_desc_prep
        and chronology["memory_index_match_push_pop"] == [9, 9, 9]
        and num(final, "memq_empty") == num(final, "reqq_empty") == 1
        and num(final, "req_v", 16) == num(final, "wdata_v", 16) == 0
        and num(final, "req_r", 16) == num(final, "wdata_r", 16) == 3
        and num(final, "prep_count") == 32 and num(final, "prep_bp") == 0
    )
    if not evidence_ok:
        errors.append("v69_causal_evidence_unexpected")

    natural = gate.get("natural_terminal_observed") is True
    formal_members = [p for p in ret if re.search(r"(^|/)formal.*D|formal_d|readback", p, re.I)]
    fe, fp = 320, 0
    fm, fx = 320, 0
    joint = compile_ok and sim_ok and natural and fp == fe and fm == 0 and fx == 0
    report = {
        "schema": "node0004-v69-branch-drain-return-analysis-v1",
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
        "qualified_branch_drain_chronology": chronology,
        "four_candidate_adjudication": candidates,
        "last_proven_good": "FINAL_18TH_DESCRIPTOR_AND_18TH_PREPARED_GROUP_JOIN_AND_DRAIN",
        "first_divergence": "BUFFER_BRANCH_ACCEPTS_PREPARED_GROUP_19_AFTER_DESCRIPTOR_COUNT_STOPS_AT_18",
        "hang_root_cause": {
            "status": "UNRESOLVED_POST_FINAL_DESCRIPTOR_BUFFER_TOKEN_OWNER",
            "classification": "DETERMINISTIC_DESCRIPTOR_DATA_LIFETIME_SKEW",
            "reason": "v69 proves a two-group data surplus after the final descriptor: descriptors stop at 18 while prepared writes reach 20 and the prepared join fills to 32. Address-index and request queues drain, and neither memory request nor write-data channel is backpressured. The return does not carry a token-level last/index/epoch ledger that binds the final descriptor to Buffer_AG request, read return, prepared write and join consumption, so it cannot decide whether the surplus is a configured terminal/tag schedule mismatch or a functional prefetch/lifetime defect."
        },
        "next_candidate_matrix": {
            "configured_buffer_schedule_exceeds_descriptor_schedule": "buffer tag/index/last keeps advancing after the descriptor terminal token",
            "descriptor_terminal_tag_mismatch": "descriptor last/index/epoch differs from the corresponding Buffer_AG token",
            "descriptor_unaware_prefetch": "Buffer_AG accepts a new request after final descriptor ownership has retired",
            "buffer_return_replay_or_stale_lifetime": "the same tag/index is returned or prepared twice without a new descriptor-owned request",
        },
        "formal_result": {"natural_terminal": natural, "expected": fe, "present": fp,
                          "missing": fm, "mismatch": fx, "formal_member_paths": formal_members,
                          "all_missing_is_not_numeric_pass": True,
                          "joint_gate": joint, "dynamic_run_bound": compile_ok and sim_ok,
                          "E3": joint, "E4": joint, "E5": False},
        "blocker_delta": {
            "closed": ["B_CONV_NODE0004_ROWLC4_BUFFER_BRANCH_DRAIN_CONJUNCTION_UNOBSERVED"],
            "opened": ["B_CONV_NODE0004_POST_FINAL_DESCRIPTOR_BUFFER_TOKEN_OWNERSHIP_UNOBSERVED"],
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
