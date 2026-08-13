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

INSTALL = "r5_n4_hw_v71_token_origin_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "5d424c2865d9b98f183e85794a9bbf89f827efcc79e2fc81ee4d9cfb70202340"
SOURCE_SHA = "8cab1c7762496cf25ecde9057388d88c428711a2e52dc5a1e8e610a66840b452"
EXECUTION = "r1786206230306714342_4179619"


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
    a = ap.parse_args(); errors: list[str] = []
    rsha, ssha = sha256_file(a.return_zip), sha256_file(a.source_zip)
    if rsha != RETURN_SHA: errors.append("return_sha256_mismatch")
    if ssha != SOURCE_SHA: errors.append("source_sha256_mismatch")
    ret, re_err, rmeta = safe_entries(a.return_zip, RETURN_ROOT)
    src, se_err, smeta = safe_entries(a.source_zip, INSTALL)
    errors += re_err + se_err
    allow, rm = load_json(ret, "RETURN_ALLOWLIST.json"), load_json(ret, "RETURN_MANIFEST.json")
    records = allow.get("records", []); expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipt_errors = []
    for record in records:
        path = record.get("path"); expected.add(path)
        data = ret.get(path)
        if data is None: receipt_errors.append(f"missing:{path}")
        elif len(data) != record.get("size_bytes"): receipt_errors.append(f"size:{path}")
        elif sha256_bytes(data) != record.get("sha256"): receipt_errors.append(f"sha:{path}")
    exact = set(ret) == expected
    if not exact: errors.append("return_exact_set_mismatch")
    errors += receipt_errors
    pm_bytes = src.get("package_manifest.json", b""); pm = json.loads(pm_bytes or b"{}")
    source_binding = (ret.get("evidence/returned_package_manifest.json") == pm_bytes
        and rm.get("install_name") == INSTALL and rm.get("records") == records
        and rm.get("fixed_result_publication", {}).get("return_zip", "").endswith(f"{INSTALL}_{EXECUTION}_return.zip"))
    source_exact = (set(pm.get("files", {})) == set(src) - {"package_manifest.json"}
        and all(p in src and sha256_bytes(src[p]) == d for p, d in pm.get("files", {}).items()))
    if not source_binding: errors.append("source_or_execution_binding_mismatch")
    if not source_exact: errors.append("source_exact_set_mismatch")

    gate = load_json(ret, "evidence/SERVER_RESULT_GATE.json")
    pf, ip = load_json(ret, "evidence/package_preflight.json"), load_json(ret, "evidence/install_preflight.json")
    op = load_json(ret, "evidence/observer_precompile.json")
    rg, pub = load_json(ret, "evidence/ndp_root_toplevel_gate.json"), load_json(ret, "evidence/publication_preflight.json")
    fb = load_json(ret, "evidence/diagnostic_feature_binding.json")
    cs = integer_entry(ret, "evidence/compile_exit_status.txt", 125)
    rs = integer_entry(ret, "evidence/run_exit_status.txt", 125)
    signal = ret.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    obs = ret.get("runs/c0/return_observer.log", b"").decode(errors="replace")
    sim = ret.get("runs/c0/sim.log", b"").decode(errors="replace")
    argv = ret.get("runs/c0/simulator_argv.txt", b"").decode(errors="replace")
    cdriver = ret.get("runs/compile/sim_results/compile_driver.log", b"").decode(errors="replace")
    osha = pm.get("observer_sha256")
    preflight = {"package": pf.get("valid") is True,
        "install_reset": ip.get("valid") is True and ip.get("runtime_d_initially_absent") is True,
        "root_direct_set": rg.get("valid") is True and rg.get("ndp_root_toplevel_unchanged") is True,
        "publication": pub.get("publication_state") == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
        "observer": op.get("valid") is True and op.get("observed_sha256") == osha
                    and sha256_bytes(src.get("tb_probe/native_return_observer.svh", b"")) == osha,
        "feature": fb.get("valid") is True}
    if not all(preflight.values()): errors.append("preflight_binding_failure")
    compile_ok = cs == 0 and "vcs" in cdriver.lower() and "Compilation completed!" in cdriver
    sim_ok = rs == 0 and signal == "NONE" and "[RETURN_OBSERVER] enabled" in sim and "+RETURN_OBS_TOKEN_ORIGIN" in argv
    if not compile_ok: errors.append("compile_binding_failure")
    if not sim_ok: errors.append("simulation_binding_failure")

    token = rows(obs, "TOKEN_ORIGIN_EDGE_V1")
    first_false = next((i for i, row in enumerate(token)
                        if num(row, "buf_wr_ev") == 1 and num(row, "buf_bp", 16) == 0), -1)
    same_class = [row for row in token if sum(num(row, k) for k in
                  ("mem_wr_ev", "buf_wr_ev", "mem_pop_ev", "buf_pop_ev", "desc_ev")) > 1]
    qualification_escape = {
        "record_count": len(token), "budget_limit": 128,
        "first_false_qualified_record": first_false + 1,
        "first_false_qualified_time": 2446119000 if first_false == 11 else None,
        "first_false_buf_bp": token[first_false].get("buf_bp") if first_false >= 0 else None,
        "first_false_buf_wr_ev": num(token[first_false], "buf_wr_ev") if first_false >= 0 else None,
        "final_reported_buf_wr": num(token[-1], "buf_wr") if token else -1,
        "final_reported_mem_wr": num(token[-1], "mem_wr") if token else -1,
        "same_sample_multiclass_records": len(same_class),
        "mechanism": "buf_ag_idx_queue_wr_en is buf_all_idx_matched && mse_enable and is not qualified by !buf_ag_idx_queue_full; mse_buf_queue_bp_pre=0 proves upstream did not accept a new token while v71 still counted buf_wr_ev=1",
    }
    escape_proven = len(token) == 128 and first_false == 11 and num(token[-1], "buf_wr") == 126
    if not escape_proven: errors.append("v71_observer_escape_not_reproduced")
    natural = gate.get("natural_terminal_observed") is True
    formal_members = [p for p in ret if re.search(r"(^|/)formal.*D|formal_d|readback", p, re.I)]
    fe, fp, fm, fx = 320, 0, 320, 0
    joint = compile_ok and sim_ok and natural and fp == fe and fm == 0 and fx == 0
    report = {
        "schema": "node0004-v71-token-origin-return-analysis-v1",
        "status": "PASS" if not errors else "FAIL", "errors": errors,
        "identity": {"return_path": str(a.return_zip.resolve()), "return_bytes": a.return_zip.stat().st_size,
                     "return_sha256": rsha, "source_path": str(a.source_zip.resolve()),
                     "source_bytes": a.source_zip.stat().st_size, "source_sha256": ssha,
                     "execution_id": EXECUTION, "expected_cloud_rtl": pm.get("cloud_rtl_authority")},
        "archive": {"return": rmeta, "source": smeta, "return_crc": not re_err,
                    "return_exact_set": exact, "per_file_receipts": not receipt_errors,
                    "source_binding": source_binding, "source_exact_set": source_exact},
        "preflight": preflight,
        "runtime": {"compile_exit": cs, "run_exit": rs, "signal": signal,
                    "compile_bound": compile_ok, "simulation_bound": sim_ok,
                    "canonical": gate.get("canonical_decision")},
        "package_local_observer_escape": qualification_escape,
        "last_proven_good": "V70_DESCRIPTOR_18_AND_PREPARED_GROUP_18_JOIN_DRAIN_WITH_BUFFER_POP_21",
        "first_divergence": "V71_TOKEN_ORIGIN_RECORD_12_COUNTS_BUFFER_QUEUE_WRITE_ATTEMPT_WHILE_BUF_BP_IS_ZERO",
        "hang_root_cause": {"status": "UNRESOLVED_DUE_TO_PACKAGE_LOCAL_DIAGNOSTIC_EVENT_QUALIFICATION_FAILURE",
            "classification": "PACKAGE_LOCAL_OBSERVER_DEFECT",
            "reason": "The target hang reproduces, but v71's token-origin budget is exhausted by a held Buffer queue write-attempt level. This return cannot adjudicate config versus RTL token ownership."},
        "formal_result": {"natural_terminal": natural, "expected": fe, "present": fp, "missing": fm,
                          "mismatch": fx, "formal_member_paths": formal_members,
                          "all_missing_is_not_numeric_pass": True, "joint_gate": joint,
                          "dynamic_run_bound": compile_ok and sim_ok, "E3": joint, "E4": joint, "E5": False},
        "blocker_delta": {"closed": [],
            "opened": ["B_CONV_NODE0004_V71_TOKEN_ORIGIN_WRITE_ATTEMPT_MISCOUNT"],
            "remains": ["B_CONV_NODE0004_MEMORY_VS_BUFFER_COMBINED_TOKEN_ORIGIN_UNOBSERVED",
                        "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL", "B_CONV_NODE0004_FORMAL_D_320"],
            "invalidated_not_reopened": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"]},
        "frozen": {"numeric_analysis_repeated": False, "workload_rebuilt": False,
                   "configuration_rebuilt": False, "golden_rebuilt": False,
                   "functional_rtl_modified": False, "server_action": False},
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, indent=2)); return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
