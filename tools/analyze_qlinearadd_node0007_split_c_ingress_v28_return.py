from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
INSTALL = "r5_qadd_n7_split_c_ingress_v28"
RETURN_SHA = "e42e6159912e111e4b04293f7682de2078fd3459a921203f5a44ad7b1aebd417"
SOURCE_SHA = "f552f2a24ae62b1e4e11c1a69ddff6663ffa2ea4fa177b923d0298c15a739f50"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


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


def kv(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def canonical_digest_valid(value: dict) -> bool:
    work = dict(value)
    stored = work.pop("content_digest", {}).get("value")
    packed = json.dumps(work, sort_keys=True, separators=(",", ":")).encode()
    return stored == sha_bytes(packed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", type=Path, required=True)
    ap.add_argument("--source-zip", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    errors: list[str] = []
    if args.return_zip.stat().st_size != 170607 or sha_file(args.return_zip) != RETURN_SHA:
        errors.append("outer return bytes/SHA differ")
    if args.source_zip.stat().st_size != 26163932 or sha_file(args.source_zip) != SOURCE_SHA:
        errors.append("source bytes/SHA differ")
    with zipfile.ZipFile(args.return_zip) as rz, zipfile.ZipFile(args.source_zip) as sz:
        rs, ss = structure(rz), structure(sz)
        rroot = rs["roots"][0] if rs["single_root"] else ""
        sroot = ss["roots"][0] if ss["single_root"] else ""
        if any(not x for x in (rs["crc_valid"], rs["single_root"], ss["crc_valid"], ss["single_root"])) or any(rs[k] or ss[k] for k in ("duplicate_count", "unsafe_path_count", "symlink_count")):
            errors.append("ZIP structure gate failed")
        if rroot != INSTALL + "_return" or sroot != INSTALL:
            errors.append("internal root identity differs")
        def rbytes(rel: str) -> bytes:
            return rz.read(f"{rroot}/{rel}")
        def rjson(rel: str) -> dict:
            return json.loads(rbytes(rel))
        rm = rjson("RETURN_MANIFEST.json")
        pm_raw = rbytes("evidence/PACKAGE_MANIFEST.json")
        source_pm_raw = sz.read(f"{sroot}/TEST_PACKAGE_MANIFEST.json")
        pm = json.loads(pm_raw)
        declared = {x["path"]: x for x in rm["files"]}
        actual = {n[len(rroot) + 1:] for n in rz.namelist() if n != f"{rroot}/RETURN_MANIFEST.json" and not n.endswith("/")}
        missing = set(rm["required_missing"])
        allow = {x["target_path"]: x for x in pm["return_allowlist"]}
        exact = set(declared) == actual and actual == set(allow) - missing and missing == set(allow) - actual
        receipts = all(
            len(rbytes(rel)) == rec["size_bytes"]
            and sha_bytes(rbytes(rel)) == rec["sha256"]
            and len(rbytes(rel)) <= allow[rel]["max_bytes"]
            for rel, rec in declared.items()
        )
        source_members = {n[len(sroot) + 1:] for n in sz.namelist() if n != f"{sroot}/TEST_PACKAGE_MANIFEST.json" and not n.endswith("/")}
        source_exact = pm_raw == source_pm_raw and source_members == set(pm["files"])
        if source_exact:
            source_exact = all(
                len(sz.read(f"{sroot}/{rel}")) == rec["size_bytes"]
                and sha_bytes(sz.read(f"{sroot}/{rel}")) == rec["sha256"]
                for rel, rec in pm["files"].items()
            )
        if not exact: errors.append("return exact-set/allowlist/missing gate failed")
        if not receipts: errors.append("per-file return receipts failed")
        if not source_exact: errors.append("returned source manifest/member binding failed")
        package_preflight = rjson("evidence/package_preflight.json")
        installed_preflight = rjson("evidence/installed_preflight.json")
        canonical = rjson("evidence/CANONICAL_PROGRESS_DECISION.json")
        gate = rjson("evidence/SERVER_RESULT_GATE.json")
        compile_exit = int(rbytes("evidence/compile_exit_status.txt").strip())
        sim_exit = int(rbytes("evidence/simulation_exit_status.txt").strip())
        canonical_exit = int(rbytes("evidence/canonical_decision_exit_status.txt").strip())
        signal = kv(rbytes("evidence/signal_status.txt").decode())
        timing = {k: int(v) for k, v in kv(rbytes("evidence/host_timing.txt").decode()).items()}
        feature = kv(rbytes("evidence/split_feature_receipt.txt").decode())
        observer = rbytes("runs/return_observer.log").decode(errors="replace")
        sim_log = rbytes("runs/sim.log").decode(errors="replace")
        starts = [int(x) for x in re.findall(r"^(\d+) \| EXEC_START \|", observer, re.M)]
        finishes = [(int(a), int(b)) for a, b in re.findall(r"^(\d+) \| COMP_FINISH \|.*active_cycles=(\d+)", observer, re.M)]
        ingress = re.findall(r"^(\d+) \| QADD_FP32_INGRESS \| (.+)$", observer, re.M)
        snapshot = {}
        if ingress:
            snapshot = {k: int(v, 0) for k, v in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+)", ingress[-1][1])}
        observer_binding = (
            feature == {"feature": "QADD_SPLIT_C_FP32_INGRESS", "argv_enabled": "true", "time0_marker": "true", "returned_snapshot_marker": "true"}
            and canonical_digest_valid(canonical)
        )
        if not observer_binding:
            errors.append("observer/feature/canonical binding failed")
        report = {
            "schema": "qlinearadd-node0007-split-c-ingress-v28-return-analysis-v1",
            "status": "RETURN_ANALYSIS_COMPLETE" if not errors else "RETURN_ANALYSIS_FAIL_CLOSED",
            "analysis_valid": not errors,
            "analysis_errors": errors,
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "RETURN_ANALYSIS": "SPLIT_C_INTERRUPTED_DURING_OP_B_DEQUANT_BEFORE_TARGET_FP32_STAGE",
            "LAST_PROVEN_GOOD": "OP_A_DEQUANT_COMP_FINISH",
            "FIRST_DIVERGENCE": "OP_B_DEQUANT_MANUAL_INTERRUPT_BEFORE_COMP_FINISH",
            "HANG_ROOT_CAUSE": "TARGET_FP32_HANG_NOT_REACHED; V28_INGRESS_STAGE_SCOPE_COUNTER_RESET_DEFECT_CONFIRMED",
            "return_transport": {"path": str(args.return_zip), "bytes": args.return_zip.stat().st_size, "sha256": sha_file(args.return_zip), "adjacent_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY"},
            "source_package": {"path": str(args.source_zip), "bytes": args.source_zip.stat().st_size, "sha256": sha_file(args.source_zip)},
            "zip_structure": rs,
            "source_zip_structure": ss,
            "identity": {"install_name": pm.get("install_name"), "return_manifest_exact": exact, "per_file_receipts_exact": receipts, "source_binding_exact": source_exact},
            "preflight": {"package_valid": package_preflight.get("valid"), "installed_valid": installed_preflight.get("valid"), "runtime_targets_initially_absent": package_preflight.get("formal_readback_targets_absent") and installed_preflight.get("formal_readback_targets_absent")},
            "execution": {"compile_exit": compile_exit, "simulation_exit": sim_exit, "canonical_exit": canonical_exit, "signal": signal.get("signal"), "natural_terminal": False, "host_wall_seconds": (timing["final_epoch_ns"] - timing["package_start_epoch_ns"]) / 1e9, "simulation_wall_seconds": (timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]) / 1e9, "stage_starts_ps": starts, "stage_finishes": [{"time_ps": x, "active_cycles": y} for x, y in finishes], "sim_finish_present": "$finish at simulation time" in sim_log},
            "ordered_scope": {"expected": ["op_a_dequant", "op_b_dequant", "op_relocation_pad", "op_fp32_add"], "observed_start_count": len(starts), "observed_finish_count": len(finishes), "reached_target_fp32_stage": len(starts) >= 4},
            "canonical_adjudication": {"returned_decision": canonical.get("decision"), "returned_boundary": canonical.get("boundary"), "formally_consumable_as_fp32_stage_evidence": False, "reason": "only one ingress snapshot existed with stage_seq=1 while only op_a finished and op_b was active; counters were accumulated from an earlier stage and cannot establish FP32 progress"},
            "ingress_snapshot": snapshot,
            "formal_D": {"expected": 28, "present": gate.get("observed_readback_count"), "missing": gate.get("missing_count"), "invalid": gate.get("invalid_count"), "mismatch_evaluable": False, "SERVER_RESULT_GATE": False},
            "E3": False, "E4": False, "E5": False,
            "BLOCKER_DELTA": {"closed": [], "opened": ["B_QADD_SPLIT_C_V28_INGRESS_STAGE_SCOPE_COUNTER_RESET"], "kept_open": ["B_QADD_SPLIT_C_FP32_PREFIX_DYNAMIC_PASS_UNPROVEN", "B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN"]},
            "successor_requirement": {
                "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "stage_tracker_fix": "track EXEC_START deassertion outside return_obs_active, reset per stage, count/snapshot ingress only at exact stage_seq=4",
                "candidate_observation_matrix_required": True,
                "minimum_scope": "MSE0+MSE1 queue/req/rdata -> Buffer0+2 -> GA dual capture/pair/accept/output",
                "shortest_legal_execution": "cumulative A+B+relocation+FP32 prefix; no legal internal A/B/relocation replay is currently bound",
            },
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "configuration_recomputed": False,
            "golden_recomputed": False,
            "functional_rtl_modified": False,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": report["analysis_valid"], "outcome": report["RETURN_ANALYSIS"], "output": str(args.output)}, indent=2))
    return 0 if report["analysis_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
