#!/usr/bin/env python3
"""Prove s4 changes only the authorized quiescence/runtime-return surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


OLD_ID = "r5_n4_hw_fsdbsmoke_s3"
NEW_ID = "r5_n4_hw_fsdbsmoke_s4"
ALLOWED_CHANGED = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "package_manifest.json",
    "package_tools/fsdb_smoke_runtime.py",
    "package_tools/server_fsdb_runtime_quiescence.py",
    "contracts/server_fsdb_runtime_quiescence.json",
    "contracts/server_post_sim_return_contract.json",
    "contracts/server_post_sim_return_request.json",
    "contracts/server_runner_return_resilience.json",
    "contracts/waveform_policy.json",
    "contracts/server_waveform_mandatory_plan.json",
    "contracts/fsdb_smoke_query_profile.json",
    "diagnostics/fsdb_smoke_query_source_report.json",
    "provenance/frozen_v88b_workload_import.json",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def members(path: Path, package_id: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"CRC failure: {path}")
        prefix = f"{package_id}/"
        return {name[len(prefix):]: archive.read(name) for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/")}


def normalized(data: bytes) -> bytes:
    try:
        return data.decode("utf-8").replace(NEW_ID, OLD_ID).encode("utf-8")
    except UnicodeDecodeError:
        return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-zip", required=True, type=Path)
    parser.add_argument("--s4-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    old = members(args.s3_zip, OLD_ID)
    new = members(args.s4_zip, NEW_ID)
    errors: list[str] = []
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    if added != ["contracts/server_fsdb_runtime_quiescence.json", "package_tools/server_fsdb_runtime_quiescence.py"]:
        errors.append("unexpected_added_members")
    if removed:
        errors.append("removed_members")
    normalized_changed = sorted(path for path in set(old) & set(new) if old[path] != normalized(new[path]))
    unauthorized = sorted(set(normalized_changed) - ALLOWED_CHANGED)
    if unauthorized:
        errors.append("unauthorized_normalized_changes")
    frozen_prefix = "workload/runtime/"
    frozen_rows = []
    for path in sorted(name for name in old if name.startswith(frozen_prefix)):
        equal = path in new and old[path] == normalized(new[path])
        frozen_rows.append({"path": path, "equal_after_identity_relocation": equal})
        if not equal:
            errors.append(f"frozen_workload:{path}")
    probes = sorted(name for name in old if name.startswith("tb_probe/"))
    probe_equal = all(name in new and old[name] == new[name] for name in probes)
    if not probe_equal:
        errors.append("probe_changed")
    dump_equal = old.get("package_tools/dump_waveform.tcl") == new.get("package_tools/dump_waveform.tcl")
    parser_equal = old.get("package_tools/fsdb_smoke_event_parser.py") == new.get("package_tools/fsdb_smoke_event_parser.py")
    if not dump_equal:
        errors.append("dump_control_changed")
    if not parser_equal:
        errors.append("query_parser_changed")
    functional_rtl = [name for name in new if name.startswith("rtl/")]
    if functional_rtl:
        errors.append("functional_rtl_present")
    report = {
        "schema": "node0004-fsdb-smoke-s4-frozen-surface-v1",
        "package_id": NEW_ID,
        "pass": not errors,
        "errors": errors,
        "s3_zip": {"path": str(args.s3_zip), "bytes": args.s3_zip.stat().st_size, "sha256": sha(args.s3_zip.read_bytes())},
        "s4_zip": {"path": str(args.s4_zip), "bytes": args.s4_zip.stat().st_size, "sha256": sha(args.s4_zip.read_bytes())},
        "added_members": added,
        "removed_members": removed,
        "normalized_changed_members": normalized_changed,
        "unauthorized_normalized_changes": unauthorized,
        "frozen_workload_member_count": len(frozen_rows),
        "frozen_workload_all_equal": all(row["equal_after_identity_relocation"] for row in frozen_rows),
        "probe_exact_equal": probe_equal,
        "dump_control_exact_equal": dump_equal,
        "query_parser_exact_equal": parser_equal,
        "functional_rtl_members": functional_rtl,
        "allowed_changed_surfaces": ["fresh_identity", "simulator_process_supervision", "simulation_time_heartbeat", "fsdb_stable_snapshot", "return_identity"],
        "claim_boundary": "Static s3-to-s4 exact ZIP comparison; only activated runtime/quiescence/return surfaces are allowed to differ.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": report["pass"], "errors": errors, "unauthorized": unauthorized}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
