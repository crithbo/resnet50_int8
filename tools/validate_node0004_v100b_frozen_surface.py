#!/usr/bin/env python3
"""Verify v100 changes only operational guard/identity surfaces relative to v99."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import PurePosixPath


OLD = "r5_n4_hw_v99b_lcdup_guarded"
NEW = "r5_n4_hw_v100b_lcdup_guardv2"
FROZEN_PREFIXES = ("workload/",)
FROZEN_FILES = (
    "tb_probe/observer_only_wide_causal.svh",
    "provenance/v88_actual_target_source.sv",
    "provenance/lc_branch_duplication_mapper_ab_report.json",
    "provenance/B_duplicate_lc_branch_config.json",
    "diagnostics/source_bound_probe_catalog.json",
    "diagnostics/source_bound_probe_plan.json",
    "diagnostics/source_bound_exact_instance_identity.json",
)


def normalized(data: bytes) -> bytes:
    try:
        return data.decode("utf-8").replace(NEW, OLD).encode("utf-8")
    except UnicodeDecodeError:
        return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-zip", required=True)
    parser.add_argument("--fresh-zip", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    errors: list[str] = []
    rows: list[dict[str, object]] = []
    with zipfile.ZipFile(args.source_zip) as source, zipfile.ZipFile(args.fresh_zip) as fresh:
        old = {PurePosixPath(n).relative_to(OLD).as_posix(): source.read(n) for n in source.namelist() if n.startswith(OLD + "/") and not n.endswith("/")}
        new = {PurePosixPath(n).relative_to(NEW).as_posix(): fresh.read(n) for n in fresh.namelist() if n.startswith(NEW + "/") and not n.endswith("/")}
        required = sorted({p for p in old if p.startswith(FROZEN_PREFIXES)} | set(FROZEN_FILES))
        for path in required:
            if path not in old or path not in new:
                errors.append(f"frozen member absent: {path}")
                continue
            same = normalized(new[path]) == old[path]
            rows.append({"path": path, "normalized_equal": same, "old_sha256": hashlib.sha256(old[path]).hexdigest(), "new_sha256": hashlib.sha256(new[path]).hexdigest()})
            if not same:
                errors.append(f"frozen member differs: {path}")
        old_workload = sorted(p for p in old if p.startswith("workload/"))
        new_workload = sorted(p for p in new if p.startswith("workload/"))
        if old_workload != new_workload:
            errors.append("workload member set differs")
        observer = new.get("tb_probe/observer_only_wide_causal.svh", b"").decode("utf-8", errors="replace")
        if "buf_idx_queue_bp_pre" in observer:
            errors.append("retired derived ACK comparator reintroduced")
        mapper = json.loads(new["provenance/lc_branch_duplication_mapper_ab_report.json"])
        if mapper.get("classification") != "VALIDATED_CONFIG_WORKAROUND_CANDIDATE_NOT_PRODUCTION_RUN" or mapper.get("cost", {}).get("negligible") is not True:
            errors.append("mapper A/B equivalence or negligible-cost conclusion differs")
    report = {
        "schema": "node0004-v100b-frozen-surface-validation-v1",
        "package_id": NEW,
        "pass": not errors,
        "errors": errors,
        "checked_member_count": len(rows),
        "rows": rows,
        "frozen": ["config", "numeric", "workload", "golden", "functional RTL", "LC9-to-LC3 mapper semantics", "52-signal tuple10 target"],
        "claim_boundary": "Byte/identity-normalized local frozen-surface comparison only; no production execution or tuple10 claim.",
    }
    from pathlib import Path
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
