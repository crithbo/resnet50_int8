#!/usr/bin/env python3
"""Prove s2 changes only smoke identity and the package-local probe identifier."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


S1 = "r5_n4_hw_fsdbsmoke_s1"
DERIVED = {
    "package_manifest.json",
    "diagnostics/fsdb_smoke_query_source_report.json",
    "provenance/frozen_v88b_workload_import.json",
    "contracts/server_post_sim_return_contract.json",
    "contracts/server_runner_return_resilience.json",
    "README.md",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def members(path: Path, package_id: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"CRC failure: {path}")
        prefix = f"{package_id}/"
        roots = {PurePosixPath(name).parts[0] for name in archive.namelist() if PurePosixPath(name).parts}
        if roots != {package_id}:
            raise ValueError(f"single-root mismatch: {path}")
        return {name[len(prefix):]: archive.read(name) for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/")}


def normalize_new(relative: str, data: bytes, new_package_id: str) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    text = text.replace(new_package_id, S1)
    text = text.replace("event_seq_id", "sequence")
    text = re.sub(r"smoke s\d+", "smoke s1", text)
    return text.encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--s1-zip", type=Path, required=True)
    parser.add_argument("--s2-zip", type=Path, required=True)
    parser.add_argument("--new-package-id", default="r5_n4_hw_fsdbsmoke_s2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    old = members(args.s1_zip, S1)
    new = members(args.s2_zip, args.new_package_id)
    errors: list[str] = []
    if set(old) != set(new):
        errors.append("relative_member_exact_set_changed")
    normalized_mismatches = []
    for relative in sorted((set(old) & set(new)) - DERIVED):
        if old[relative] != normalize_new(relative, new[relative], args.new_package_id):
            normalized_mismatches.append(relative)
    if normalized_mismatches:
        errors.append("undeclared_normalized_member_changes")

    old_manifest = json.loads(old["package_manifest.json"])
    new_manifest = json.loads(new["package_manifest.json"])
    invariant_manifest_fields = ["activation_epoch", "classification", "formal_operator_successor", "candidate_release", "dump", "frozen", "retired_ack_comparator_present", "source_package"]
    manifest_invariants = {field: old_manifest.get(field) == new_manifest.get(field) for field in invariant_manifest_fields}
    if not all(manifest_invariants.values()):
        errors.append("manifest_frozen_invariant_changed")
    old_prov = json.loads(old["provenance/frozen_v88b_workload_import.json"])
    new_prov = json.loads(new["provenance/frozen_v88b_workload_import.json"])
    provenance_checks = {
        "source_zip": old_prov.get("source_zip") == new_prov.get("source_zip"),
        "source_members": old_prov.get("source_members") == new_prov.get("source_members"),
        "source_member_count": old_prov.get("source_member_count") == new_prov.get("source_member_count"),
        "destination_member_count": old_prov.get("destination_member_count") == new_prov.get("destination_member_count"),
        "functional_payload_frozen": old_prov.get("functional_payload_frozen") is True and new_prov.get("functional_payload_frozen") is True,
        "identity_relocation_set": old_prov.get("identity_only_text_relocations") == new_prov.get("identity_only_text_relocations"),
    }
    if not all(provenance_checks.values()):
        errors.append("frozen_v88b_provenance_changed")
    old_post = json.loads(old["contracts/server_post_sim_return_contract.json"])
    new_post = json.loads(new["contracts/server_post_sim_return_contract.json"])
    old_runner_contract = json.loads(old["contracts/server_runner_return_resilience.json"])
    new_runner_contract = json.loads(new["contracts/server_runner_return_resilience.json"])
    derived_contract_checks = {
        "post_request_sha_matches_s2": new_post.get("request_sha256") == sha(new["contracts/server_post_sim_return_request.json"]),
        "post_contract_only_identity_and_request_digest_change": {k: v for k, v in old_post.items() if k not in {"package_id", "request_sha256"}} == {k: v for k, v in new_post.items() if k not in {"package_id", "request_sha256"}},
        "runner_sha_matches_s2": new_runner_contract.get("runner_sha256") == sha(new["PREPARE_AND_RUN.sh"]),
        "runner_contract_normalized_equal": {k: v for k, v in old_runner_contract.items() if k not in {"package_id", "runner_path", "runner_sha256"}} == {k: v for k, v in new_runner_contract.items() if k not in {"package_id", "runner_path", "runner_sha256"}},
    }
    if not all(derived_contract_checks.values()):
        errors.append("derived_contract_identity_change_invalid")
    old_probe = old["tb_probe/fsdb_smoke_event_probe.svh"].decode("utf-8")
    new_probe = new["tb_probe/fsdb_smoke_event_probe.svh"].decode("utf-8")
    probe_checks = {
        "s1_keyword_present": "integer sequence;" in old_probe,
        "s2_safe_identifier_present": "integer event_seq_id;" in new_probe,
        "s2_keyword_declaration_absent": "integer sequence;" not in new_probe,
        "registered_log_field_preserved": "CODEX_FSDB_SMOKE_EVENT_V1 sequence=%0d" in old_probe and "CODEX_FSDB_SMOKE_EVENT_V1 sequence=%0d" in new_probe,
        "identity_normalized_probe_equal": old_probe == new_probe.replace("event_seq_id", "sequence"),
    }
    if not all(probe_checks.values()):
        errors.append("probe_change_exceeds_identifier_rename")
    report = {
        "schema": "node0004-fsdb-smoke-s2-frozen-surface-v1",
        "package_id": args.new_package_id,
        "pass": not errors,
        "errors": errors,
        "s1_zip": {"path": args.s1_zip.as_posix(), "bytes": args.s1_zip.stat().st_size, "sha256": sha(args.s1_zip.read_bytes())},
        "s2_zip": {"path": args.s2_zip.as_posix(), "bytes": args.s2_zip.stat().st_size, "sha256": sha(args.s2_zip.read_bytes())},
        "relative_member_exact_set_equal": set(old) == set(new),
        "derived_identity_members": sorted(DERIVED),
        "normalized_non_derived_mismatches": normalized_mismatches,
        "manifest_invariants": manifest_invariants,
        "frozen_v88b_provenance": provenance_checks,
        "derived_contract_identities": derived_contract_checks,
        "probe_identifier_repair": probe_checks,
        "allowed_changes": ["fresh package identity s1->new smoke", "package-local probe identifier sequence->event_seq_id", "README operator root /home/panqs/ndp->/home/panqs/ndp/NDP_copy01", "derived manifests/receipts bound to those exact bytes"],
        "frozen": {"config": True, "numeric": True, "workload": True, "golden": True, "functional_rtl": True, "fsdb_v3_profile": True},
        "formal_serialized_successor": False,
        "claim_boundary": "Static exact-ZIP comparison only; no production compiler, simulation, FSDB or DUT claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "errors": errors, "mismatches": normalized_mismatches}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
