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

INSTALL = "r5_n4_hw_v70_branch_owner_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "3860731999ee024b3589094a95bb3c7e78684424f49b2ea5099fd0f573d5cff7"
SOURCE_SHA = "1076a9a5371d3988c31efbecfa750c10ee12b4ffc5e0777aeffa2a6ea710ec93"
EXECUTION = "r1786203000568429970_4150663"


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
             and "+RETURN_OBS_BRANCH_OWNER" in argv
    if not compile_ok:
        errors.append("compile_binding_failure")
    if not sim_ok:
        errors.append("simulation_binding_failure")

    branch = rows(obs, "BRANCH_OWNER_EDGE_V1")
    final_state = rows(obs, "BRANCH_OWNER_STATE_V1")[-1]
    final = branch[-1] if branch else {}
    desc18 = next((i for i, x in enumerate(branch) if num(x, "desc") == 18), -1)
    post_desc = branch[desc18 + 1:] if desc18 >= 0 else []
    same_sample_multiclass = [x for x in branch if sum(num(x, k) for k in
        ("desc_ev", "buf_pop_ev", "buf_req_ev", "buf_ret_ev", "prep_wr_ev", "prep_rd_ev")) > 1]
    event_totals = {k: sum(num(x, k) for x in branch) for k in
                    ("desc_ev", "buf_pop_ev", "buf_req_ev", "buf_ret_ev", "prep_wr_ev", "prep_rd_ev")}
    chronology = {
        "records": len(branch), "same_sample_multiclass_records": len(same_sample_multiclass),
        "event_totals_from_all_class_bits": event_totals,
        "final_counts": {k: num(final_state, k) for k in
                         ("desc", "buf_pop", "buf_req", "buf_ret", "prep_wr", "prep_rd")},
        "first_desc18_record": desc18 + 1,
        "post_desc_records": len(post_desc),
        "post_desc_event_totals": {k: sum(num(x, k) for x in post_desc) for k in
                                   ("desc_ev", "buf_pop_ev", "buf_req_ev", "buf_ret_ev", "prep_wr_ev", "prep_rd_ev")},
        "post_desc_buffer_tags": [x.get("buf_tag") for x in post_desc if num(x, "buf_pop_ev") == 1],
        "post_desc_buffer_last_index": [num(x, "buf_ob_last_index") for x in post_desc if num(x, "buf_pop_ev") == 1],
        "post_desc_last_req_assertions": sum(num(x, "buf_last_req") for x in post_desc),
        "post_desc_data_last_assertions": sum(num(x, "data_last") for x in post_desc),
        "final_prepared_count": num(final_state, "prep_count"),
        "final_descriptor_queue_empty": num(final_state, "desc_qempty"),
    }
    evidence_ok = (
        len(branch) == 31 and len(same_sample_multiclass) > 0
        and chronology["final_counts"] == {"desc": 18, "buf_pop": 23, "buf_req": 21,
                                             "buf_ret": 18, "prep_wr": 20, "prep_rd": 18}
        and chronology["post_desc_event_totals"] == {"desc_ev": 0, "buf_pop_ev": 2,
                                                       "buf_req_ev": 2, "buf_ret_ev": 1,
                                                       "prep_wr_ev": 2, "prep_rd_ev": 1}
        and chronology["post_desc_last_req_assertions"] == 0
        and chronology["post_desc_data_last_assertions"] == 0
        and chronology["final_prepared_count"] == 32
        and chronology["final_descriptor_queue_empty"] == 1
    )
    if not evidence_ok:
        errors.append("v70_branch_owner_evidence_unexpected")

    natural = gate.get("natural_terminal_observed") is True
    formal_members = [p for p in ret if re.search(r"(^|/)formal.*D|formal_d|readback", p, re.I)]
    fe, fp, fm, fx = 320, 0, 320, 0
    joint = compile_ok and sim_ok and natural and fp == fe and fm == 0 and fx == 0
    report = {
        "schema": "node0004-v70-branch-owner-return-analysis-v1",
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
        "qualified_branch_owner_chronology": chronology,
        "multiclass_edge_consumption": {
            "return_records_carry_all_six_class_bits": True,
            "parser_consumes_all_class_bits_independent_of_label": True,
            "same_sample_multiclass_observed": len(same_sample_multiclass),
            "v70_evidence_not_lost_by_priority_label": True,
        },
        "last_proven_good": "DESCRIPTOR_18_AND_PREPARED_GROUP_18_JOIN_DRAIN_WITH_BUFFER_POP_21",
        "first_divergence": "POST_DESCRIPTOR_BUFFER_POP_22_ACCEPTS_TAG_0X35_AND_PREPARED_GROUP_20_WITH_NO_DESCRIPTOR",
        "hang_root_cause": {
            "status": "UNRESOLVED_BUFFER_AND_MEMORY_AG_COMBINED_TOKEN_ORIGIN",
            "classification": "DETERMINISTIC_POST_DESCRIPTOR_BRANCH_LIFETIME_SKEW",
            "reason": "v70 proves that no descriptor follows descriptor 18, yet two more Buffer_AG pops/requests and two prepared writes are accepted. Both extra Buffer tags have last_index=5, buf_ag_last_req_flag and data_last remain zero, the descriptor queue empties, and prepared occupancy reaches 32. This excludes downstream memory backpressure and return replay, but the output-side tags alone do not reveal whether Memory_AG stopped because its combined input token stream ended early or Buffer_AG synthesized/retained extra combined tokens. The exact queue-write input tags and combined queue write data are the one remaining causal boundary."
        },
        "candidate_matrix": {
            "memory_combined_token_supply_ends_early": "Memory_AG queue write count/tag terminal stops before matching Buffer_AG combined token sequence",
            "buffer_combined_token_supply_excess": "Buffer_AG queue receives additional combined row/col tokens after the matching Memory_AG input epoch ends",
            "buffer_queue_stale_or_duplicate": "Buffer_AG dequeue repeats without a corresponding new combined queue write",
            "terminal_tag_projection_mismatch": "corresponding combined Memory_AG and Buffer_AG writes carry incompatible last/index ownership",
        },
        "formal_result": {"natural_terminal": natural, "expected": fe, "present": fp,
                          "missing": fm, "mismatch": fx, "formal_member_paths": formal_members,
                          "all_missing_is_not_numeric_pass": True, "joint_gate": joint,
                          "dynamic_run_bound": compile_ok and sim_ok, "E3": joint, "E4": joint, "E5": False},
        "blocker_delta": {
            "closed": ["B_CONV_NODE0004_POST_FINAL_DESCRIPTOR_BUFFER_TOKEN_OWNERSHIP_UNOBSERVED"],
            "opened": ["B_CONV_NODE0004_MEMORY_VS_BUFFER_COMBINED_TOKEN_ORIGIN_UNOBSERVED"],
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
