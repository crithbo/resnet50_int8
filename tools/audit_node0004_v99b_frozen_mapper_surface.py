#!/usr/bin/env python3
"""Prove that v99 preserves v98 workload/config and the authorized mapper A/B."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import PurePosixPath


OLD = "r5_n4_hw_v98b_lcdup_tuple10"
NEW = "r5_n4_hw_v99b_lcdup_guarded"


def normalized(data: bytes) -> bytes:
    try:
        return data.decode("utf-8").replace(NEW, OLD).encode("utf-8")
    except UnicodeDecodeError:
        return data


def load_members(path, package: str) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"CRC failure: {path}")
        result = {}
        for name in archive.namelist():
            member = PurePosixPath(name)
            if not member.parts or member.parts[0] != package:
                raise ValueError(f"root mismatch: {name}")
            relative = PurePosixPath(*member.parts[1:]).as_posix()
            if relative:
                result[relative] = archive.read(name)
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    errors: list[str] = []
    old = load_members(args.source, OLD)
    new = load_members(args.zip, NEW)
    old_workload = {name: data for name, data in old.items() if name.startswith("workload/")}
    new_workload = {name: data for name, data in new.items() if name.startswith("workload/")}
    if set(old_workload) != set(new_workload):
        errors.append("workload member set differs")
    different = [name for name in sorted(set(old_workload) & set(new_workload)) if old_workload[name] != normalized(new_workload[name])]
    if different:
        errors.append(f"workload/config/numeric/golden bytes differ: {different[:8]}")
    proof_name = "provenance/lc_branch_duplication_mapper_ab_report.json"
    if normalized(new.get(proof_name, b"")) != old.get(proof_name, b""):
        errors.append("mapper A/B proof identity differs")
    proof = json.loads(new[proof_name])
    cost = proof.get("cost", {})
    proof_checks = proof.get("checks", {})
    equivalence = {
        "address_sequence_equal": proof.get("address_sequence", {}).get("equal"),
        "output_math_equal": proof.get("output_math", {}).get("equal"),
        "command_count_equal": proof.get("commands", {}).get("same_command_count"),
        "data_plane_memory_traffic_equal": proof.get("memory_traffic", {}).get("equal"),
    }
    if proof.get("classification") != "VALIDATED_CONFIG_WORKAROUND_CANDIDATE_NOT_PRODUCTION_RUN":
        errors.append("mapper classification differs")
    if cost.get("negligible") is not True or cost.get("additional_lc") != 1 or cost.get("spare_B") != 5:
        errors.append("mapper cost proof differs")
    proof_check_keys = {
        "address_sequence_equal": "address_sequence_equal",
        "output_math_equal": "output_math_sequence_equal",
        "command_count_equal": "command_count_equal",
        "data_plane_memory_traffic_equal": "data_plane_memory_traffic_equal",
    }
    for key, proof_key in proof_check_keys.items():
        if equivalence.get(key) is not True or proof_checks.get(proof_key) is not True:
            errors.append(f"mapper equivalence differs: {key}")
    manifest = json.loads(new["package_manifest.json"])
    if manifest.get("config_workaround") != "DUPLICATE_LC_BRANCH_LC9_TO_LC3_FOR_PE1_INPUT2":
        errors.append("authorized workaround differs")
    observer = new.get("tb_probe/observer_only_wide_causal.svh", b"")
    if b"buf_idx_queue_bp_pre" in observer:
        errors.append("retired ACK comparator reintroduced")
    report = {
        "schema": "node0004-v99b-frozen-mapper-surface-audit-v1",
        "package_id": NEW,
        "pass": not errors,
        "errors": errors,
        "checks": {
            "workload_config_numeric_golden_normalized_byte_equal": not different and set(old_workload) == set(new_workload),
            "mapper_ab_proof_identity_equal": normalized(new.get(proof_name, b"")) == old.get(proof_name, b""),
            "retired_ack_comparator_absent": b"buf_idx_queue_bp_pre" not in observer,
        },
        "workload_member_count": len(new_workload),
        "mapper_ab": {"equivalence": equivalence, "cost": cost},
        "claim_boundary": "Local frozen-surface and mapper A/B identity only; no production tuple10, natural-terminal or Formal-D claim.",
    }
    with open(args.output, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
