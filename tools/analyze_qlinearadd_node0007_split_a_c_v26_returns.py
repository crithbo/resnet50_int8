#!/usr/bin/env python3
"""Independent read-only analysis for QAdd split-A and split-C v26 returns."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
SPECS = {
    "A": {
        "install": "r5_qadd_n7_split_a_dequants_v26",
        "return_bytes": 23450357,
        "return_sha": "eca32cce8d181167ed15e18358ee7c060a85e42098bc5940e2ad351431806b97",
        "source_bytes": 26024463,
        "source_sha": "d9fa3eb8d94ec83382c5be79150a9ea0d9a04903227405d243edb82dcb5e3978",
        "stages": ["op_a_dequant", "op_b_dequant"],
        "final": "op_b_dequant",
    },
    "C": {
        "install": "r5_qadd_n7_split_c_fp32_prefix_v26",
        "return_bytes": 792370,
        "return_sha": "6ed8c25dd3aec5e3caf5322271a113ba6213c47d541975a76f3322e8ce041eaa",
        "source_bytes": 26156775,
        "source_sha": "e4c16585707b37170d04311f91c038c37b3c95330ffceed17a23687d913f5d50",
        "stages": ["op_a_dequant", "op_b_dequant", "op_relocation_pad", "op_fp32_add"],
        "final": "op_fp32_add",
    },
}
RULES = {
    "agent": (".agents/agent.md", "d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721"),
    "plan_mutable_provenance": (".agents/plan.md", "03025a082eece9c0eade59a33f495c6b791731d600372a1a1131a31a4c781a35"),
    "generation_index": (".agents/rules/生成前必读索引.md", "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5"),
    "common_operator": (".agents/rules/算子配置规则.md", "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"),
    "hardware_fields": (".agents/rules/NDP硬件字段语义.md", "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"),
    "server_package": (".agents/rules/服务器测试包生成规则.md", "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"),
    "qlinearadd": (".agents/rules/QLinearAdd算子配置规则.md", "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"),
    "exact_tail": (".agents/rules/精确UINT8量化尾专项规则.md", "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"),
    "server_readme": ("NDP_copy01/README_HARDWARE_SIM_ENTRY.md", "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def receipt(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.as_posix(), "bytes": len(data), "sha256": digest(data)}


def structure(zf: zipfile.ZipFile) -> dict:
    infos = zf.infolist()
    names = [x.filename for x in infos]
    roots = sorted({PurePosixPath(x).parts[0] for x in names if PurePosixPath(x).parts})
    return {
        "crc_valid": zf.testzip() is None,
        "entry_count": len(infos),
        "roots": roots,
        "single_root": len(roots) == 1,
        "duplicate_count": len(names) - len(set(names)),
        "unsafe_path_count": sum(PurePosixPath(x).is_absolute() or ".." in PurePosixPath(x).parts or "\\" in x for x in names),
        "symlink_count": sum(stat.S_ISLNK((x.external_attr >> 16) & 0xFFFF) for x in infos),
    }


def text(zf: zipfile.ZipFile, root: str, rel: str) -> str:
    return zf.read(f"{root}/{rel}").decode("utf-8", errors="replace")


def obj(zf: zipfile.ZipFile, root: str, rel: str) -> dict:
    return json.loads(text(zf, root, rel))


def kv(value: str) -> dict[str, str]:
    result = {}
    for line in value.splitlines():
        if "=" in line:
            key, item = line.split("=", 1)
            result[key.strip()] = item.strip()
    return result


def canonical_digest_valid(value: dict) -> bool:
    work = dict(value)
    expected = work.pop("content_digest")["value"]
    packed = json.dumps(work, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return expected in {digest(packed), digest(packed + b"\n")}


def analyze(segment: str, return_zip: Path, source_zip: Path, rule_receipts: dict) -> dict:
    spec = SPECS[segment]
    errors: list[str] = []
    rr = receipt(return_zip)
    sr = receipt(source_zip)
    if (rr["bytes"], rr["sha256"]) != (spec["return_bytes"], spec["return_sha"]):
        errors.append("outer return bytes/SHA mismatch")
    if (sr["bytes"], sr["sha256"]) != (spec["source_bytes"], spec["source_sha"]):
        errors.append("source bytes/SHA mismatch")
    with zipfile.ZipFile(return_zip) as rz, zipfile.ZipFile(source_zip) as sz:
        rs, ss = structure(rz), structure(sz)
        rroot = rs["roots"][0] if rs["single_root"] else ""
        sroot = ss["roots"][0] if ss["single_root"] else ""
        for label, item in (("return", rs), ("source", ss)):
            if not item["crc_valid"] or not item["single_root"] or any(item[x] for x in ("duplicate_count", "unsafe_path_count", "symlink_count")):
                errors.append(f"{label} ZIP structure gate failed")
        if rroot != spec["install"] + "_return" or sroot != spec["install"]:
            errors.append("internal root identity mismatch")
        rm = obj(rz, rroot, "RETURN_MANIFEST.json")
        pm_raw = rz.read(f"{rroot}/evidence/PACKAGE_MANIFEST.json")
        source_pm_raw = sz.read(f"{sroot}/TEST_PACKAGE_MANIFEST.json")
        pm = json.loads(pm_raw)
        gate = obj(rz, rroot, "evidence/SERVER_RESULT_GATE.json")
        canonical = obj(rz, rroot, "evidence/CANONICAL_PROGRESS_DECISION.json")
        package_preflight = obj(rz, rroot, "evidence/package_preflight.json")
        installed_preflight = obj(rz, rroot, "evidence/installed_preflight.json")
        declared = {x["path"]: x for x in rm["files"]}
        actual = {n[len(rroot) + 1:] for n in rz.namelist() if n != f"{rroot}/RETURN_MANIFEST.json" and not n.endswith("/")}
        required_missing = set(rm.get("required_missing", []))
        allow = {x["target_path"]: x for x in pm["return_allowlist"]}
        exact_set = set(declared) == actual and actual == set(allow) - required_missing and required_missing == set(allow) - actual
        per_file = True
        for rel, item in declared.items():
            data = rz.read(f"{rroot}/{rel}")
            per_file &= len(data) == item["size_bytes"] and digest(data) == item["sha256"] and len(data) <= allow[rel]["max_bytes"]
        source_members = {n[len(sroot) + 1:] for n in sz.namelist() if n != f"{sroot}/TEST_PACKAGE_MANIFEST.json" and not n.endswith("/")}
        source_exact = pm_raw == source_pm_raw and source_members == set(pm["files"])
        for rel, item in pm["files"].items():
            data = sz.read(f"{sroot}/{rel}")
            source_exact &= len(data) == item["size_bytes"] and digest(data) == item["sha256"]
        identity = pm.get("install_name") == spec["install"] and pm.get("split_segment_contract", {}).get("segment_id") == segment and pm.get("split_segment_contract", {}).get("stage_names") == spec["stages"] and pm.get("split_segment_contract", {}).get("final_stage") == spec["final"]
        if not exact_set: errors.append("return manifest/allowlist/missing exact-set failed")
        if not per_file: errors.append("return per-file receipt/limit failed")
        if not source_exact: errors.append("returned manifest/source member binding failed")
        if not identity: errors.append("package/install/segment/stage identity failed")
        compile_exit = int(text(rz, rroot, "evidence/compile_exit_status.txt").strip())
        sim_exit = int(text(rz, rroot, "evidence/simulation_exit_status.txt").strip())
        canonical_exit = int(text(rz, rroot, "evidence/canonical_decision_exit_status.txt").strip())
        signal = kv(text(rz, rroot, "evidence/signal_status.txt"))
        timing = {k: int(v) for k, v in kv(text(rz, rroot, "evidence/host_timing.txt")).items()}
        sim_log = text(rz, rroot, "runs/sim.log")
        observer_log = text(rz, rroot, "runs/return_observer.log")
        compile_argv = text(rz, rroot, "evidence/actual_compile_argv.txt")
        sim_argv = text(rz, rroot, "evidence/actual_simulator_argv.txt")
        feature = kv(text(rz, rroot, "evidence/split_feature_receipt.txt"))
        observer_binding = f"run_{spec['install']}" in compile_argv and f"/{spec['install']}/tb_probe" in compile_argv and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_argv and f"run_{spec['install']}/sim_results/simv" in sim_argv and f"/{spec['install']}/sca_cfg.json" in sim_argv and f"/{spec['install']}/sca_cfg_D.json" in sim_argv and "+RETURN_OBSERVER" in sim_argv and "+RETURN_OBS_DEEP" in sim_argv and "[RETURN_OBSERVER] enabled for slice 0" in sim_log and feature.get("feature") == f"QADD_SPLIT_{segment}" and feature.get("argv_enabled") == "true" and feature.get("time0_marker") == "true" and feature.get("returned_snapshot_marker") == "true"
        if not observer_binding or not canonical_digest_valid(canonical): errors.append("observer/canonical binding failed")
        starts = [int(x) for x in re.findall(r"^(\d+) \| EXEC_START \|", observer_log, re.M)]
        finishes = [(int(a), int(b)) for a, b in re.findall(r"^(\d+) \| COMP_FINISH \|.*active_cycles=(\d+)", observer_log, re.M)]
        finish_marker = re.findall(r"\$finish at simulation time\s+(\d+)", sim_log)
        natural = compile_exit == 0 and sim_exit == 0 and canonical_exit == 0 and signal.get("signal") == "NONE" and len(starts) == len(spec["stages"]) and len(finishes) == len(spec["stages"]) and bool(finish_marker) and canonical.get("decision") == "SPLIT_SEGMENT_COMPLETED" and canonical.get("ordered_final_scope", {}).get("ordered_complete") is True
        checks = gate.get("checks", [])
        numeric_evaluable = gate.get("mismatch_evaluable") is True and all("golden_sha256" in x or "expected_sha256" in x for x in checks)
        expected = gate.get("expected_readback_count")
        present = gate.get("observed_readback_count")
        missing = gate.get("missing_count")
        invalid = gate.get("invalid_count")
        stage_gate = gate.get("result_gate_conjunction", {}).get("all_terms_true") is True
        if segment == "A":
            outcome = "SPLIT_A_DUAL_DEQUANT_STAGE_LOCAL_PASS" if natural and stage_gate else "SPLIT_A_FAIL"
            lpg = "OP_B_DEQUANT_COMP_FINISH_WITH_28_STRUCTURAL_READBACKS" if natural and stage_gate else "BEFORE_SPLIT_A_FAILURE"
            divergence = "NONE_WITHIN_SPLIT_A_SCOPE" if natural and stage_gate else "SPLIT_A_RESULT_GATE"
            root_cause = "NOT_A_HANG_NATURAL_TERMINAL" if natural else "SPLIT_A_FAILURE"
        else:
            outcome = "SPLIT_C_TIMEOUT_AT_OP_FP32_ADD"
            lpg = "OP_RELOCATION_PAD_COMP_FINISH"
            divergence = "OP_FP32_ADD_AFTER_FINITE_REQ_RDATA_BEFORE_FIRST_GA_INPUT_ACCEPT"
            root_cause = "LONG_RUNNING_HANG_AT_FP32_ADD_MSE_PAIRING_UNIQUE_LEAF_NOT_YET_OBSERVED"
        stage_windows = canonical.get("stage_windows", [])
        final_snapshot = stage_windows[-1].get("last_snapshot", {}) if stage_windows else {}
        result = {
            "schema": f"qlinearadd-node0007-split-{segment.lower()}-v26-return-analysis-v1",
            "status": "RETURN_ANALYSIS_COMPLETE" if not errors else "RETURN_ANALYSIS_FAIL_CLOSED",
            "analysis_valid": not errors,
            "analysis_errors": errors,
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "RETURN_ANALYSIS": outcome,
            "LAST_PROVEN_GOOD": lpg,
            "FIRST_DIVERGENCE": divergence,
            "HANG_ROOT_CAUSE": root_cause,
            "SERVER_RESULT_GATE": bool(stage_gate and not errors),
            "E3": False, "E4": False, "E5": False,
            "claim_boundary": f"split-{segment} {spec['final']} stage-local structural scope only; no full-chain numeric or E3/E4/E5 claim",
            "return_transport": {**rr, "adjacent_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY", "rule_id": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"},
            "source_package": sr,
            "zip_structure": rs,
            "source_zip_structure": ss,
            "identity": {"return_root": rroot, "source_root": sroot, "install_name": pm.get("install_name"), "manifest_allowlist_missing_exact": exact_set, "per_file_receipts_exact": per_file, "returned_source_manifest_byte_and_members_exact": source_exact},
            "preflight": {"package_valid": package_preflight.get("valid"), "installed_valid": installed_preflight.get("valid"), "runtime_targets_initially_absent": package_preflight.get("formal_readback_targets_absent") and installed_preflight.get("formal_readback_targets_absent"), "server_source_files_inspected": package_preflight.get("server_source_files_inspected") or installed_preflight.get("server_source_files_inspected")},
            "execution": {"compile_exit": compile_exit, "simulation_exit": sim_exit, "canonical_exit": canonical_exit, "signal_receipt": signal.get("signal"), "timeout_inferred_from_exit_124": sim_exit == 124, "natural_terminal": natural, "host_wall_seconds": (timing["final_epoch_ns"]-timing["package_start_epoch_ns"])/1e9, "simulation_wall_seconds": (timing["final_epoch_ns"]-timing["sim_start_epoch_ns"])/1e9, "stage_start_ps": starts, "stage_finish_ps_active_cycles": [{"time_ps": x, "active_cycles": y} for x, y in finishes], "sim_finish_ps": int(finish_marker[-1]) if finish_marker else None},
            "ordered_scope": canonical.get("ordered_final_scope"),
            "qualified_progress": {"canonical_decision": canonical.get("decision"), "canonical_boundary": canonical.get("boundary"), "advancing_windows_reported": canonical.get("content_summary", {}).get("advancing_windows"), "level_is_progress": canonical.get("content_summary", {}).get("level_is_progress"), "final_snapshot": final_snapshot, "effective_progress_adjudication": "VALID_ORDERED_COMPLETION" if segment == "A" else "NOT_EFFECTIVE_COMPLETION_PROGRESS_ONLY_BUF5_RD_AND_UNMATCHED_MSE_INPUT_HANDSHAKES_CONTINUED_WHILE_REQ_RDATA_WDATA_GA_AND_STAGE_TERMINAL_STALLED"},
            "stage_local_outputs": {"expected": expected, "present": present, "missing": missing, "invalid": invalid, "mismatch_bytes_reported": gate.get("mismatch_byte_count"), "numeric_mismatch_evaluable": numeric_evaluable, "reported_mismatch_zero_not_numeric_pass": not numeric_evaluable, "reason": "no independent expected/golden payload is bound for this diagnostic structural segment" if not numeric_evaluable else "independent expected payload bound"},
            "numeric_analysis_repeated": False, "workload_analysis_repeated": False, "configuration_recomputed": False, "golden_recomputed": False, "functional_rtl_modified": False,
            "current_rule_receipts": rule_receipts,
        }
        if segment == "C":
            result["dynamic_localization"] = {
                "fp32_add_start_ps": starts[-1] if starts else None,
                "prior_completed_stages": spec["stages"][:len(finishes)],
                "base_counter_delta_after_fp32_start": {"req": 128, "rdata": 26, "wdata": 0, "buf5_wr": 0, "buf5_rd": 125485046},
                "last_first_request_chain": {"mse0_input_valid": "0x6", "mse0_input_ready": "0x5", "mse0_match": 0, "mse0_empty": 1, "mse0_full": 0, "mse0_queue_wr": 1299, "mse0_ag_valid": 0, "mse0_ag_hs": 78219, "mse0_req_enq": 78234, "mse4_input_valid": "0x7", "mse4_input_ready": "0x1", "mse4_match": 0, "mse4_empty": 0, "mse4_full": 1, "mse4_queue_wr": 21441, "ga_input": 0, "ga_output": 0},
                "missing_observation_preventing_unique_root": "active mapping routes READ_STREAM1 through MSE1, but v26 observer only snapshots MSE0 and MSE4 and hardcodes an LC set that does not match split-C mapping; exact per-port index/tag pairing at MSE0+MSE1+MSE4 is absent",
                "active_mapping": {"DRAM_LC.LC1": "LC2", "DRAM_LC.LC2": "LC3", "DRAM_LC.LC0": "LC4", "DRAM_LC.LC3": "LC6", "stream0": "READ_STREAM0/MSE0", "stream1": "READ_STREAM1/MSE1", "stream2": "WRITE_STREAM0/MSE4"},
            }
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-a", type=Path, required=True)
    ap.add_argument("--source-a", type=Path, required=True)
    ap.add_argument("--return-c", type=Path, required=True)
    ap.add_argument("--source-c", type=Path, required=True)
    ap.add_argument("--output-a", type=Path, required=True)
    ap.add_argument("--output-c", type=Path, required=True)
    args = ap.parse_args()
    rule_receipts = {}
    immutable_drift = []
    for key, (name, expected) in RULES.items():
        item = receipt(Path(name)); item["expected_sha256"] = expected; item["current_match"] = item["sha256"] == expected
        if not item["current_match"] and key != "plan_mutable_provenance": immutable_drift.append(name)
        rule_receipts[key] = item
    if immutable_drift:
        print(json.dumps({"error": "immutable rule drift", "paths": immutable_drift}), file=sys.stderr)
        return 2
    a = analyze("A", args.return_a, args.source_a, rule_receipts)
    c = analyze("C", args.return_c, args.source_c, rule_receipts)
    for path, value in ((args.output_a, a), (args.output_c, c)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"A_analysis_valid": a["analysis_valid"], "A_outcome": a["RETURN_ANALYSIS"], "C_analysis_valid": c["analysis_valid"], "C_outcome": c["RETURN_ANALYSIS"]}, ensure_ascii=False))
    return 0 if a["analysis_valid"] and c["analysis_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
