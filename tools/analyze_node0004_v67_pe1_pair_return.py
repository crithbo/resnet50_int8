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

INSTALL = "r5_n4_hw_v67_pe1_pair_diag"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "1ac57340c9c37adae664be47d21364a9011a229ee440509a610238c087257c9b"
SOURCE_SHA = "be8fb8fd8cda13282cc1d740a837325ce811f7c1ad52d7efd096d71d56c0e83e"
EXECUTION = "r1786169108703435693_3996582"
MAPPING = ROOT / "artifacts/operator_config_validation/r5-node0004-pe1-keep-last-index-fix-c0-v62/mapping/conv/op_w0/mapping_cache/72d2720125714878.json"


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
    if rsha != RETURN_SHA: errors.append("return_sha256_mismatch")
    if ssha != SOURCE_SHA: errors.append("source_sha256_mismatch")
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
        if data is None: receipt_errors.append(f"missing:{path}")
        elif len(data) != record.get("size_bytes"): receipt_errors.append(f"size:{path}")
        elif sha256_bytes(data) != record.get("sha256"): receipt_errors.append(f"sha:{path}")
    exact = set(ret) == expected
    if not exact: errors.append("return_exact_set_mismatch")
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
    if not source_binding: errors.append("source_or_execution_binding_mismatch")
    source_exact = (
        set(pm.get("files", {})) == set(src) - {"package_manifest.json"}
        and all(path in src and sha256_bytes(src[path]) == digest
                for path, digest in pm.get("files", {}).items())
    )
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
    if not all(preflight.values()): errors.append("preflight_binding_failure")
    compile_ok = cs == 0 and "vcs" in cdriver.lower() and "Compilation completed!" in cdriver
    sim_ok = rs == 0 and signal == "NONE" and "[RETURN_OBSERVER] enabled" in sim \
             and "+RETURN_OBS_PE1_PAIR" in argv
    if not compile_ok: errors.append("compile_binding_failure")
    if not sim_ok: errors.append("simulation_binding_failure")

    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    physical_binding = {
        "logical_PE1": mapping.get("LC_PE.PE1"),
        "logical_LC15": mapping.get("DRAM_LC.LC15"),
        "logical_LC9": mapping.get("DRAM_LC.LC9"),
    }
    binding_proven = physical_binding == {
        "logical_PE1": "PE7", "logical_LC15": "LC17", "logical_LC9": "LC18",
    }
    if not binding_proven: errors.append("mapping_binding_unexpected")

    wrong = rows(obs, "PE1_PAIR_V1")
    wrong_final = wrong[-1] if wrong else {}
    correct = rows(obs, "LC18_PE7_EDGE_V1")
    epoch = rows(obs, "EPOCH_OWNER_V1")
    epoch_changes = [x for x in epoch if x.get("event") == "QUALIFIED_CHANGE"]
    epoch_final = epoch[-1] if epoch else {}
    dskew = rows(obs, "DSKEW_BOUNDARY_V1")
    dskew_final = dskew[-1] if dskew else {}
    pe7 = {
        "edge_records": len(correct),
        "both_inputs_seen": any(num(x, "pe7_in_valid", 16) == 5 for x in correct),
        "match_seen": any(num(x, "pe7_matched") == 1 for x in correct),
        "output_seen": any(num(x, "pe7_out", 16) >= 0x400000 for x in correct),
        "mse4_input1_valid_seen": any(num(x, "mse_in1_valid") == 1 for x in correct),
        "writes": num(dskew_final, "pe7_wr"),
        "reads": num(dskew_final, "pe7_rd"),
        "last_edge": correct[-1] if correct else {},
    }
    wrong_target_zero = all(num(wrong_final, key) == 0 for key in
                            ("lc15_in0", "lc9_in2", "match", "ob_wr", "ob_rd", "pe_out", "mse1"))
    corrected_shadow = {
        "records": len(epoch_changes),
        "final_lc17_23bit": epoch_final.get("lc17") == "520002",
        "final_lc18_23bit": epoch_final.get("lc18") == "530000",
        "corrected_width_visible": epoch_final.get("lc17") == "520002" and epoch_final.get("lc18") == "530000",
    }
    if not (wrong_target_zero and all((pe7["both_inputs_seen"], pe7["match_seen"],
                                      pe7["output_seen"], pe7["mse4_input1_valid_seen"]))):
        errors.append("causal_evidence_unexpected")

    natural = gate.get("natural_terminal_observed") is True
    fe = int(gate.get("formal_d_expected", 320)); fp = int(gate.get("formal_d_present", 0))
    fm = int(gate.get("formal_d_missing", fe)); fx = int(gate.get("formal_d_mismatch", 0))
    joint = compile_ok and sim_ok and natural and fp == fe and fm == 0 and fx == 0
    report = {
        "schema": "node0004-v67-pe1-pair-return-analysis-v1",
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
        "corrected_width_shadow": corrected_shadow,
        "observer_target_adjudication": {
            "mapping_path": str(MAPPING), "mapping_sha256": sha256_file(MAPPING),
            "physical_binding": physical_binding, "binding_proven": binding_proven,
            "v67_PE1_PAIR_actual_target": "physical PE1 plus physical LC17 and LC9",
            "required_target": "physical PE7 plus physical LC17 and LC18",
            "wrong_target_zero_snapshot": wrong_final,
            "wrong_target_zero_is_not_DUT_failure": wrong_target_zero,
            "package_local_observer_target_bug": True,
        },
        "correct_physical_pe7_chain_from_retained_observer": pe7,
        "last_proven_good": "PHYSICAL_LC17_AND_LC18_REACH_PE7_MATCH_OUTPUT_AND_MSE4_INPUT1_FOR_NINE_TRANSACTIONS",
        "first_divergence": "AFTER_NINTH_PE7_OUTPUT_PHYSICAL_LC17_LC18_REMAIN_PRESENT_BUT_TENTH_PE7_PAIR_MATCH_DOES_NOT_OCCUR",
        "hang_root_cause": {
            "status": "UNRESOLVED_BECAUSE_V67_NEW_OBSERVER_TARGETED_WRONG_PHYSICAL_PE",
            "classification": "PACKAGE_LOCAL_OBSERVER_TARGET_BINDING_ERROR",
            "reason": "The mapper binds logical PE1 to physical PE7, LC15 to LC17 and LC9 to LC18. v67 sampled IGA_PE[1] and LC9. Its zero record is unrelated. The retained physical-PE7 observer proves nine full input/match/output/MSE4 handoffs, but does not expose physical PE7 buffered-valid/clear/keep state at the first missing tenth pairing."
        },
        "next_candidate_matrix": {
            "PE7_input0_held_token_cleared_or_blocked": "physical PE7 inbuffer valid/clear/bp-mask plus mode/keep",
            "PE7_input2_next_epoch_not_captured": "physical LC18 raw edge versus PE7 input2 enable/buffered valid",
            "PE7_both_tokens_buffered_but_not_matched": "buffered valid,last,index plus matched and tag",
            "PE7_match_occurs_but_output_or_MSE4_missing": "ALU/outbuffer/PE output/MSE4 input1 same-clock ledger",
        },
        "formal_result": {"natural_terminal": natural, "expected": fe, "present": fp,
                          "missing": fm, "mismatch": fx,
                          "all_missing_is_not_numeric_pass": fp == 0 and fm == fe and fx == 0,
                          "joint_gate": joint, "E3": compile_ok and sim_ok, "E4": joint, "E5": False},
        "blocker_delta": {
            "closed": ["B_CONV_NODE0004_V66_SHADOW_WIDTH_ALIASING"],
            "opened": ["B_CONV_NODE0004_V67_PE1_PAIR_OBSERVER_PHYSICAL_TARGET_MISMATCH",
                       "B_CONV_NODE0004_PE7_TENTH_PAIR_FIRST_MISSING_BOUNDARY_UNOBSERVED"],
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
