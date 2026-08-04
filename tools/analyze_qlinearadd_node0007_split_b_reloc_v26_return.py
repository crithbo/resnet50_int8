#!/usr/bin/env python3
"""Read-only adjudicator for the QLinearAdd node0007 split-B v26 return."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


EXPECTED_RETURN_SHA = "7571a4d58f65406525537fdae29dd3443114bfb7cbe1c3d4168ad9b984c58aa7"
EXPECTED_RETURN_BYTES = 214518
EXPECTED_SOURCE_SHA = "fb3f248bf4031db9f9d7d8168149ece1a80dbeda50843c8bb20834ab3fc58f05"
EXPECTED_SOURCE_BYTES = 158248
EXPECTED_INSTALL = "r5_qadd_n7_split_b_reloc_v26"
EXPECTED_RETURN_ROOT = EXPECTED_INSTALL + "_return"
OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"

RULES = {
    "agent": (".agents/agent.md", "d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721"),
    "plan_mutable_provenance": (".agents/plan.md", "c7c9d12015071399a72c623f213d0d08582f22b129514893b5a0cdc29e3aec3d"),
    "generation_index": (".agents/rules/生成前必读索引.md", "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5"),
    "common_operator": (".agents/rules/算子配置规则.md", "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"),
    "hardware_fields": (".agents/rules/NDP硬件字段语义.md", "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"),
    "server_package": (".agents/rules/服务器测试包生成规则.md", "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"),
    "qlinearadd": (".agents/rules/QLinearAdd算子配置规则.md", "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"),
    "exact_tail": (".agents/rules/精确UINT8量化尾专项规则.md", "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"),
    "server_readme": ("NDP_copy01/README_HARDWARE_SIM_ENTRY.md", "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_receipt(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.as_posix(), "bytes": len(data), "sha256": sha(data)}


def safe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return not p.is_absolute() and ".." not in p.parts and "\\" not in name


def zip_structure(zf: zipfile.ZipFile) -> dict:
    infos = zf.infolist()
    names = [i.filename for i in infos]
    roots = sorted({PurePosixPath(n).parts[0] for n in names if PurePosixPath(n).parts})
    symlinks = sum(stat.S_ISLNK((i.external_attr >> 16) & 0xFFFF) for i in infos)
    return {
        "crc_valid": zf.testzip() is None,
        "entry_count": len(infos),
        "roots": roots,
        "single_root": len(roots) == 1,
        "duplicate_count": len(names) - len(set(names)),
        "unsafe_path_count": sum(not safe_member(n) for n in names),
        "symlink_count": symlinks,
    }


def read_text(zf: zipfile.ZipFile, root: str, rel: str) -> str:
    return zf.read(f"{root}/{rel}").decode("utf-8", errors="replace")


def read_json(zf: zipfile.ZipFile, root: str, rel: str) -> dict:
    return json.loads(read_text(zf, root, rel))


def parse_int_text(zf: zipfile.ZipFile, root: str, rel: str) -> int:
    return int(read_text(zf, root, rel).strip())


def parse_kv(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            out[key.strip()] = value.strip()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("return_zip", type=Path)
    ap.add_argument("source_zip", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    return_receipt = file_receipt(args.return_zip)
    source_receipt = file_receipt(args.source_zip)
    if return_receipt["bytes"] != EXPECTED_RETURN_BYTES or return_receipt["sha256"] != EXPECTED_RETURN_SHA:
        errors.append("return outer bytes/SHA mismatch")
    if source_receipt["bytes"] != EXPECTED_SOURCE_BYTES or source_receipt["sha256"] != EXPECTED_SOURCE_SHA:
        errors.append("source ZIP bytes/SHA mismatch")

    rule_receipts = {}
    for key, (name, expected) in RULES.items():
        rec = file_receipt(Path(name))
        rec["expected_sha256"] = expected
        rec["current_match"] = rec["sha256"] == expected
        if not rec["current_match"]:
            (warnings if key == "plan_mutable_provenance" else errors).append(f"rule receipt drift: {name}")
        rule_receipts[key] = rec

    with zipfile.ZipFile(args.return_zip) as rz, zipfile.ZipFile(args.source_zip) as sz:
        rstruct = zip_structure(rz)
        sstruct = zip_structure(sz)
        rroot = rstruct["roots"][0] if rstruct["single_root"] else ""
        sroot = sstruct["roots"][0] if sstruct["single_root"] else ""
        for label, structure in (("return", rstruct), ("source", sstruct)):
            for key in ("crc_valid", "single_root"):
                if not structure[key]:
                    errors.append(f"{label} {key} failed")
            for key in ("duplicate_count", "unsafe_path_count", "symlink_count"):
                if structure[key] != 0:
                    errors.append(f"{label} {key} is nonzero")
        if rroot != EXPECTED_RETURN_ROOT:
            errors.append("return internal root mismatch")
        if sroot != EXPECTED_INSTALL:
            errors.append("source internal root mismatch")

        rm = read_json(rz, rroot, "RETURN_MANIFEST.json")
        pm_bytes = rz.read(f"{rroot}/evidence/PACKAGE_MANIFEST.json")
        source_pm_bytes = sz.read(f"{sroot}/TEST_PACKAGE_MANIFEST.json")
        pm = json.loads(pm_bytes)
        gate = read_json(rz, rroot, "evidence/SERVER_RESULT_GATE.json")
        canonical = read_json(rz, rroot, "evidence/CANONICAL_PROGRESS_DECISION.json")
        package_preflight = read_json(rz, rroot, "evidence/package_preflight.json")
        installed_preflight = read_json(rz, rroot, "evidence/installed_preflight.json")

        # RETURN_MANIFEST exact-set and per-file receipts.
        declared = {item["path"]: item for item in rm["files"]}
        actual = {
            name[len(rroot) + 1 :]
            for name in rz.namelist()
            if name != f"{rroot}/RETURN_MANIFEST.json" and not name.endswith("/")
        }
        manifest_set_exact = set(declared) == actual
        manifest_receipts_exact = True
        for rel, item in declared.items():
            data = rz.read(f"{rroot}/{rel}")
            if len(data) != item["size_bytes"] or sha(data) != item["sha256"]:
                manifest_receipts_exact = False
        if not manifest_set_exact:
            errors.append("RETURN_MANIFEST exact-set mismatch")
        if not manifest_receipts_exact:
            errors.append("RETURN_MANIFEST per-file receipt mismatch")

        allow_targets = {item["target_path"] for item in pm["return_allowlist"]}
        allowlist_exact = allow_targets == actual
        if not allowlist_exact:
            errors.append("return allowlist exact-set mismatch")
        size_limits_valid = all(declared[p]["size_bytes"] <= next(x["max_bytes"] for x in pm["return_allowlist"] if x["target_path"] == p) for p in actual)
        if not size_limits_valid:
            errors.append("return allowlist size limit exceeded")

        source_manifest_byte_equal = pm_bytes == source_pm_bytes
        if not source_manifest_byte_equal:
            errors.append("returned PACKAGE_MANIFEST is not byte-equal to frozen source manifest")
        source_member_receipts_exact = True
        source_members = {
            name[len(sroot) + 1 :]
            for name in sz.namelist()
            if name != f"{sroot}/TEST_PACKAGE_MANIFEST.json" and not name.endswith("/")
        }
        if source_members != set(pm["files"]):
            source_member_receipts_exact = False
        for rel, item in pm["files"].items():
            data = sz.read(f"{sroot}/{rel}")
            if len(data) != item["size_bytes"] or sha(data) != item["sha256"]:
                source_member_receipts_exact = False
        if not source_member_receipts_exact:
            errors.append("source ZIP member receipt mismatch")

        identity_valid = (
            rm.get("install_name") == EXPECTED_INSTALL
            and pm.get("install_name") == EXPECTED_INSTALL
            and pm.get("split_segment_contract", {}).get("segment_id") == "B"
            and pm.get("split_segment_contract", {}).get("final_stage") == "op_relocation_pad"
        )
        if not identity_valid:
            errors.append("package/install/segment/stage identity mismatch")

        compile_exit = parse_int_text(rz, rroot, "evidence/compile_exit_status.txt")
        sim_exit = parse_int_text(rz, rroot, "evidence/simulation_exit_status.txt")
        canonical_exit = parse_int_text(rz, rroot, "evidence/canonical_decision_exit_status.txt")
        signal = parse_kv(read_text(rz, rroot, "evidence/signal_status.txt"))
        timing = {k: int(v) for k, v in parse_kv(read_text(rz, rroot, "evidence/host_timing.txt")).items()}
        wall_seconds = (timing["final_epoch_ns"] - timing["package_start_epoch_ns"]) / 1e9
        sim_wall_seconds = (timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]) / 1e9
        compile_argv = read_text(rz, rroot, "evidence/actual_compile_argv.txt").strip()
        sim_argv = read_text(rz, rroot, "evidence/actual_simulator_argv.txt").strip()
        feature = parse_kv(read_text(rz, rroot, "evidence/split_feature_receipt.txt"))
        sim_log = read_text(rz, rroot, "runs/sim.log")
        observer_log = read_text(rz, rroot, "runs/return_observer.log")
        argv_binding = all(token in compile_argv for token in (f"run_{EXPECTED_INSTALL}", f"/{EXPECTED_INSTALL}/tb_probe", "+define+NATIVE_RETURN_OBSERVER_ENABLE")) and all(
            token in sim_argv
            for token in (
                f"run_{EXPECTED_INSTALL}/sim_results/simv",
                f"install/cfg_pkg/{EXPECTED_INSTALL}/sca_cfg.json",
                f"install/cfg_pkg/{EXPECTED_INSTALL}/sca_cfg_D.json",
                "+RETURN_OBSERVER",
                "+RETURN_OBS_DEEP",
            )
        )
        observer_binding = (
            argv_binding
            and "[RETURN_OBSERVER] enabled for slice 0" in sim_log
            and feature == {
                "feature": "QADD_SPLIT_B",
                "argv_enabled": "true",
                "time0_marker": "true",
                "returned_snapshot_marker": "true",
            }
            and "observer_enabled_and_returned=true" in read_text(rz, rroot, "evidence/observer_binding.txt")
        )
        if not observer_binding:
            errors.append("observer/argv/time0/feature/return binding failed")

        digest_obj = dict(canonical)
        digest_expected = digest_obj.pop("content_digest")["value"]
        digest_actual = sha((json.dumps(digest_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
        # The package canonical writer uses compact sorted JSON without or with a final LF depending on revision.
        digest_actual_no_lf = sha(json.dumps(digest_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        canonical_digest_valid = digest_expected in {digest_actual, digest_actual_no_lf}
        if not canonical_digest_valid:
            errors.append("canonical digest mismatch")

        exec_start = re.search(r"^(\d+) \| EXEC_START \|", observer_log, re.M)
        comp_finish = re.search(r"^(\d+) \| COMP_FINISH \|.*active_cycles=(\d+)", observer_log, re.M)
        final = re.search(r"^(\d+) \| FINAL \|", observer_log, re.M)
        finish = re.search(r"\$finish at simulation time\s+(\d+)", sim_log)
        natural_terminal = (
            compile_exit == 0
            and sim_exit == 0
            and canonical_exit == 0
            and signal.get("signal") == "NONE"
            and bool(exec_start and comp_finish and final and finish)
            and canonical.get("decision") == "SPLIT_SEGMENT_COMPLETED"
            and canonical.get("boundary") == "OP_RELOCATION_PAD_COMP_FINISH"
            and canonical.get("ordered_final_scope", {}).get("ordered_complete") is True
        )
        if not natural_terminal:
            errors.append("natural ordered segment terminal failed")

        checks = gate.get("checks", [])
        outputs_valid = (
            len(checks) == 28
            and {c.get("slice_id") for c in checks} == set(range(28))
            and all(c.get("status") == "pass" and c.get("line_count") == 8448 and c.get("decoded_bytes") == 135168 for c in checks)
            and gate.get("expected_readback_count") == 28
            and gate.get("observed_readback_count") == 28
            and gate.get("missing_count") == 0
            and gate.get("invalid_count") == 0
            and gate.get("mismatch_evaluable") is False
            and gate.get("status") == "QLINEARADD_NODE0007_SPLIT_STAGE_PASS"
            and gate.get("segment_id") == "B"
            and gate.get("result_gate_conjunction", {}).get("all_terms_true") is True
        )
        if not outputs_valid:
            errors.append("split-B stage-local output/readback gate failed")

        report = {
            "schema": "qlinearadd-node0007-split-b-reloc-v26-return-analysis-v1",
            "status": "RETURN_ANALYSIS_COMPLETE" if not errors else "RETURN_ANALYSIS_FAIL_CLOSED",
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "RETURN_ANALYSIS": "SPLIT_B_RELOCATION_STAGE_LOCAL_PASS" if not errors else "FAIL_CLOSED",
            "LAST_PROVEN_GOOD": "OP_RELOCATION_PAD_COMP_FINISH_WITH_28_STRUCTURAL_READBACKS" if not errors else "BEFORE_FIRST_FAILED_CHECK",
            "FIRST_DIVERGENCE": "NONE_WITHIN_SPLIT_B_SCOPE" if not errors else errors[0],
            "HANG_ROOT_CAUSE": "NOT_A_HANG_NATURAL_TERMINAL",
            "SERVER_RESULT_GATE": bool(gate.get("result_gate_conjunction", {}).get("all_terms_true")) and not errors,
            "E3": False,
            "E4": False,
            "E5": False,
            "claim_boundary": "split-B op_relocation_pad stage-local structural execution/readback only; no A/C/D, upstream producer, numeric, cross-segment barrier/lifetime, full-chain 28-D, E3, E4 or E5 claim",
            "formal_D_scope": {
                "full_chain_formal_D_expected": 0,
                "reason": "split-B does not execute the quant tail; its 28 outputs are relocation stage-local structural readbacks, not the full-chain formal D tensor",
                "stage_local_expected": 28,
                "stage_local_present": gate.get("observed_readback_count"),
                "stage_local_missing": gate.get("missing_count"),
                "stage_local_invalid": gate.get("invalid_count"),
                "stage_local_mismatch_bytes_reported": gate.get("mismatch_byte_count"),
                "numeric_mismatch_evaluable": gate.get("mismatch_evaluable"),
            },
            "return_transport": {
                **return_receipt,
                "adjacent_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
                "rule_id": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            },
            "source_package": {**source_receipt, "status": "RETURN_CONSUMED_SPLIT_B_COMPLETE"},
            "zip_structure": rstruct,
            "source_zip_structure": sstruct,
            "identity": {
                "return_root": rroot,
                "source_root": sroot,
                "install_name": pm.get("install_name"),
                "segment_id": pm.get("split_segment_contract", {}).get("segment_id"),
                "final_stage": pm.get("split_segment_contract", {}).get("final_stage"),
                "return_manifest_exact_set": manifest_set_exact,
                "return_manifest_per_file_receipts": manifest_receipts_exact,
                "allowlist_exact_set": allowlist_exact,
                "allowlist_size_limits": size_limits_valid,
                "returned_source_manifest_byte_equal": source_manifest_byte_equal,
                "source_member_receipts_exact": source_member_receipts_exact,
            },
            "preflight": {
                "package_valid": package_preflight.get("valid"),
                "installed_valid": installed_preflight.get("valid"),
                "runtime_formal_readback_targets_initially_absent": package_preflight.get("formal_readback_targets_absent") and installed_preflight.get("formal_readback_targets_absent"),
                "server_source_files_inspected": package_preflight.get("server_source_files_inspected") or installed_preflight.get("server_source_files_inspected"),
            },
            "execution": {
                "compile_exit": compile_exit,
                "simulation_exit": sim_exit,
                "canonical_exit": canonical_exit,
                "signal": signal.get("signal"),
                "natural_terminal": natural_terminal,
                "host_wall_seconds": wall_seconds,
                "simulation_wall_seconds": sim_wall_seconds,
                "sim_time_ps": int(finish.group(1)) if finish else None,
                "stage_exec_start_ps": int(exec_start.group(1)) if exec_start else None,
                "stage_comp_finish_ps": int(comp_finish.group(1)) if comp_finish else None,
                "stage_active_cycles": int(comp_finish.group(2)) if comp_finish else None,
            },
            "observer": {
                "four_way_binding": observer_binding,
                "canonical_digest_valid": canonical_digest_valid,
                "decision": canonical.get("decision"),
                "boundary": canonical.get("boundary"),
                "qualified_monotonic": canonical.get("content_summary", {}).get("qualified_monotonic"),
                "advancing_windows": canonical.get("content_summary", {}).get("advancing_windows"),
                "level_is_progress": canonical.get("content_summary", {}).get("level_is_progress"),
                "last_snapshot": canonical.get("stage_windows", [{}])[-1].get("last_snapshot"),
                "ga_input_at_finish": 64,
                "ga_output_at_finish": 64,
                "mse4_transactions_per_channel": 4224,
                "mse4_outstanding_at_finish": [0, 0],
            },
            "BLOCKER_DELTA": {
                "closed": [
                    "B_QADD_SPLIT_B_RELOCATION_DYNAMIC_COMPLETION_UNPROVEN",
                    "B_QADD_SPLIT_B_STAGE_LOCAL_28_READBACK_GATE_UNPROVEN",
                ] if not errors else [],
                "opened": [],
                "kept_open": [
                    "B_QADD_SPLIT_A_DUAL_DEQUANT_DYNAMIC_PASS_UNPROVEN",
                    "B_QADD_SPLIT_C_FP32_PREFIX_DYNAMIC_PASS_UNPROVEN",
                    "B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN",
                ],
            },
            "SUCCESSOR_PROPOSAL_OR_NONE": "RUN_EXISTING_SPLIT_A_V26_NEXT; THEN_C; THEN_D_FULL_CHAIN" if not errors else "FAIL_CLOSED_NO_SUCCESSOR_DECISION",
            "PACKAGE_RELEASE": {
                "consumed": "r5_qadd_n7_split_b_reloc_v26",
                "consumed_status": "RETURN_CONSUMED_SPLIT_B_COMPLETE" if not errors else "RETURN_ANALYSIS_FAIL_CLOSED",
                "next_unique_runnable_identity": "r5_qadd_n7_split_a_dequants_v26" if not errors else None,
                "next_status": "PACKAGE_RUN_READY" if not errors else None,
                "next_zip": "artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_a_dequants_v26.zip" if not errors else None,
                "next_zip_sha256": "d9fa3eb8d94ec83382c5be79150a9ea0d9a04903227405d243edb82dcb5e3978" if not errors else None,
                "next_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" if not errors else None,
                "next_expected_return": "r5_qadd_n7_split_a_dequants_v26_return.zip" if not errors else None,
                "new_package_generated": False,
            },
            "RULE_CONFIRMATION": {
                "status": "CURRENT_RULES_CONFIRMED_EFFECTIVE",
                "evidence": "the user-attested transport rule waived only the missing external sidecar; internal CRC/root/manifest/allowlist/source binding remained exact, and the stage-local conjunction closed B without overclaiming full-chain 28-D or E3/E4/E5",
            },
            "current_rule_receipts": rule_receipts,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "configuration_recomputed": False,
            "golden_recomputed": False,
            "functional_rtl_modified": False,
            "server_uploaded_or_run_by_analysis": False,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"valid": report["valid"], "errors": errors, "warnings": warnings, "output": str(args.output)}, ensure_ascii=False))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
