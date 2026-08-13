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

INSTALL = "r5_n4_hw_v66_epoch_owner_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "c7dc6b54a7a2c47ca538cb99232b452377996fd5d1bc2558f7a0f4468261d80d"
SOURCE_SHA = "b0f4a0d83a82ccd1b039247da09318a1d9121ae08a9857f268a8568538050d1e"
EXECUTION = "r1786159968158262861_3953004"


def rows(text: str, marker: str) -> list[dict[str, str]]:
    return [dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
            for line in text.splitlines() if marker in line]


def n(row: dict[str, str], key: str, base: int = 10) -> int:
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
    if rsha != RETURN_SHA: errors.append("return_sha256_mismatch")
    if ssha != SOURCE_SHA: errors.append("source_sha256_mismatch")
    ret, re, rmeta = safe_entries(a.return_zip, RETURN_ROOT)
    src, se, smeta = safe_entries(a.source_zip, INSTALL)
    errors += re + se

    allow = load_json(ret, "RETURN_ALLOWLIST.json")
    rmanifest = load_json(ret, "RETURN_MANIFEST.json")
    records = allow.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipt_errors = []
    for x in records:
        p = x.get("path")
        if not isinstance(p, str):
            receipt_errors.append("invalid_path")
            continue
        expected.add(p)
        b = ret.get(p)
        if b is None: receipt_errors.append(f"missing:{p}")
        elif len(b) != x.get("size_bytes"): receipt_errors.append(f"size:{p}")
        elif sha256_bytes(b) != x.get("sha256"): receipt_errors.append(f"sha:{p}")
    exact = set(ret) == expected
    if not exact: errors.append("return_exact_set_mismatch")
    errors += receipt_errors

    pm_bytes = src.get("package_manifest.json", b"")
    returned_pm = ret.get("evidence/returned_package_manifest.json", b"")
    pm = json.loads(pm_bytes or b"{}")
    source_binding = (
        returned_pm == pm_bytes
        and rmanifest.get("install_name") == INSTALL
        and rmanifest.get("records") == records
        and rmanifest.get("fixed_result_publication", {}).get("return_zip", "")
            .endswith(f"{INSTALL}_{EXECUTION}_return.zip")
    )
    if not source_binding: errors.append("source_or_execution_binding_mismatch")
    sf = pm.get("files", {})
    source_exact = (set(sf) == set(src) - {"package_manifest.json"} and
                    all(p in src and sha256_bytes(src[p]) == h for p, h in sf.items()))
    if not source_exact: errors.append("source_exact_set_mismatch")

    gate = load_json(ret, "evidence/SERVER_RESULT_GATE.json")
    fb = load_json(ret, "evidence/diagnostic_feature_binding.json")
    pf = load_json(ret, "evidence/package_preflight.json")
    ip = load_json(ret, "evidence/install_preflight.json")
    op = load_json(ret, "evidence/observer_precompile.json")
    rg = load_json(ret, "evidence/ndp_root_toplevel_gate.json")
    pub = load_json(ret, "evidence/publication_preflight.json")
    cs = integer_entry(ret, "evidence/compile_exit_status.txt", 125)
    rs = integer_entry(ret, "evidence/run_exit_status.txt", 125)
    sig = ret.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    obs = ret.get("runs/c0/return_observer.log", b"").decode(errors="replace")
    sim = ret.get("runs/c0/sim.log", b"").decode(errors="replace")
    argv = ret.get("runs/c0/simulator_argv.txt", b"").decode(errors="replace")
    clog = ret.get("runs/compile/sim_results/compile.log", b"").decode(errors="replace")
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
    if not all(preflight.values()): errors.append("preflight_binding_failure")
    compile_ok = cs == 0 and "vcs" in cdriver.lower() and "Compilation completed!" in cdriver
    sim_ok = rs == 0 and sig == "NONE" and "[RETURN_OBSERVER] enabled" in sim and "+RETURN_OBS_EPOCH_OWNER" in argv
    if not compile_ok: errors.append("compile_binding_failure")
    if not sim_ok: errors.append("simulation_binding_failure")

    epoch = rows(obs, "EPOCH_OWNER_V1")
    changes = [x for x in epoch if x.get("event") == "QUALIFIED_CHANGE"]
    decisions = [x for x in epoch if x.get("event") == "DIAG_DECISION"]
    final = decisions[-1] if decisions else {}
    printed_keys = tuple(sorted(k for k in final if k != "event"))
    unique_printed = {tuple(x.get(k) for k in printed_keys) for x in changes}
    duplicate_printed_records = len(changes) - len(unique_printed)
    split = rows(obs, "LC9_SPLIT_BOUNDARY_V1")
    split_final = split[-1] if split else {}
    lcb = rows(obs, "LC13_LC14_BOUNDARY_V1")
    lc_final = lcb[-1] if lcb else {}
    chronology = {
        "feature_enabled": "feature=RETURN_OBS_EPOCH_OWNER enabled=1" in obs,
        "pre_third_terminal_delta_zero_seen": any(n(x,"desc_terminal")==2 and n(x,"desc")==18 and n(x,"prepared")==18 for x in changes),
        "final_delta_two": n(final,"desc_terminal")==3 and n(final,"desc")==18 and n(final,"prepared")==20 and n(final,"delta")==2,
        "final_only_input0_raw_and_same_suppressed": n(final,"valid",16)==1 and n(final,"same",16)==1 and n(final,"gotten",16)==7 and n(final,"masked",16)==0,
        "queue_not_full_and_empty": n(final,"qempty")==1 and n(final,"bp",16)==7,
        "buffer_branch_ahead": n(final,"buf_push")==27 and n(final,"buf_pop")==23,
        "pe1_in2_without_match_or_output": n(split_final,"pe1_in2_accept")==2 and n(split_final,"pe1_match")==0 and n(split_final,"pe1_out_accept")==0,
    }
    if not all(chronology.values()): errors.append("epoch_chronology_mismatch")

    natural = gate.get("natural_terminal_observed") is True
    fe, fpresent = int(gate.get("formal_d_expected",320)), int(gate.get("formal_d_present",0))
    fmissing, fmismatch = int(gate.get("formal_d_missing",fe)), int(gate.get("formal_d_mismatch",0))
    joint = compile_ok and sim_ok and natural and fpresent == fe and fmissing == 0 and fmismatch == 0
    report = {
        "schema": "node0004-v66-epoch-owner-return-analysis-v1",
        "status": "PASS" if not errors else "FAIL", "errors": errors,
        "identity": {"return_path": str(a.return_zip.resolve()), "return_bytes": a.return_zip.stat().st_size, "return_sha256": rsha,
                     "source_path": str(a.source_zip.resolve()), "source_bytes": a.source_zip.stat().st_size, "source_sha256": ssha,
                     "execution_id": EXECUTION, "unique_return_basename_is_not_source_identity": True,
                     "actual_compile_identity": pm.get("cloud_rtl_authority")},
        "archive": {"return": rmeta, "source": smeta, "return_crc": not re, "return_exact_set": exact,
                    "per_file_receipts": not receipt_errors, "source_binding": source_binding, "source_exact_set": source_exact},
        "preflight": preflight,
        "runtime": {"compile_exit": cs, "run_exit": rs, "signal": sig, "compile_bound": compile_ok, "simulation_bound": sim_ok,
                    "canonical": gate.get("canonical_decision")},
        "qualified_epoch_owner": {"record_count": len(changes), "unique_printed_tuple_count": len(unique_printed),
                                  "duplicate_printed_record_count": duplicate_printed_records,
                                  "observer_predicate_output_escape": duplicate_printed_records > 0,
                                  "chronology": chronology, "final_snapshot": final, "lc9_split_final": split_final,
                                  "lc13_lc14_final": lc_final,
                                  "physical_mapping": {"input0":"logical_LC14/physical_LC8", "input1":"PE1", "input2":"logical_LC13/physical_LC6",
                                                       "logical_LC15":"physical_LC17 feeds PE1 input0", "logical_LC9":"feeds PE1 input2"}},
        "last_proven_good": "LOGICAL_LC9_TO_PE1_INPUT2_ACCEPT_TWICE_AND_THIRD_DESCRIPTOR_TERMINAL_DELTA_RECOVERS_TO_ZERO",
        "first_divergence": "PE1_RECEIVES_LC9_INPUT2_BUT_NEVER_FORMS_A_MATCH_OR_OUTPUT_FOR_MSE4_INPUT1",
        "hang_root_cause": {"status":"UNRESOLVED_AFTER_V66_EPOCH_OWNER",
            "reason":"Address input0 is an expected held-same token already consumed; input1 PE1 and input2 logical LC13 are raw-invalid. Existing qualified evidence proves PE1 accepted LC9 twice but never matched/output. It does not record PE1 input0 from logical LC15, PE1 per-port inbuffer epoch tags, or PE1 ALU/outbuffer/MSE4 handoffs, so LC15 absence, epoch mismatch, PE pipeline failure, and MSE4 rejection remain distinguishable candidates."},
        "candidate_matrix": {
            "LC15_missing_at_PE1_in0":"needs PE1 input0 valid/ready/accept and logical LC15/physical LC17 edge",
            "PE1_epoch_tag_mismatch":"needs per-port buffered valid/last/index and matched",
            "PE1_pipeline_or_outbuffer":"needs matched, ALU result, outbuffer write/read and PE out accept",
            "MSE4_input1_rejection":"needs PE out accept and MSE4 input1 accept in same clock ledger"},
        "formal_result": {"natural_terminal":natural,"expected":fe,"present":fpresent,"missing":fmissing,"mismatch":fmismatch,
                          "all_missing_is_not_numeric_pass":fpresent==0 and fmissing==fe and fmismatch==0,
                          "joint_gate":joint,"E3":compile_ok and sim_ok,"E4":joint,"E5":False},
        "blocker_delta": {"closed":["B_CONV_NODE0004_MSE4_PER_INPUT_EPOCH_OWNERSHIP_UNOBSERVED"],
                          "opened":["B_CONV_NODE0004_PE1_PAIR_MATCH_AND_OUTPUT_CAUSAL_CHAIN_UNOBSERVED"],
                          "remains":["B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL","B_CONV_NODE0004_FORMAL_D_320"],
                          "invalidated_not_reopened":["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"]},
        "frozen":{"numeric_analysis_repeated":False,"workload_rebuilt":False,"configuration_rebuilt":False,"golden_rebuilt":False,"functional_rtl_modified":False}
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
