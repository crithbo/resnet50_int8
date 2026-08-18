#!/usr/bin/env python3
"""Verify that v101 changes only the authorized package/runtime surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


OLD = "r5_n4_hw_v100b_lcdup_guardv2"
NEW = "r5_n4_hw_v101b_lcdup_guardprocfix"
FROZEN_PREFIXES = ("workload/",)
FROZEN_FILES = (
    "tb_probe/observer_only_wide_causal.svh",
    "tb_probe/source_bound_causal_observer.svh",
    "provenance/v88_actual_target_source.sv",
    "provenance/lc_branch_duplication_mapper_ab_report.json",
    "provenance/B_duplicate_lc_branch_config.json",
    "diagnostics/source_bound_probe_catalog.json",
    "diagnostics/source_bound_probe_plan.json",
    "diagnostics/source_bound_exact_instance_identity.json",
)


def normalized(data: bytes) -> bytes:
    try:
        text = data.decode("utf-8").replace(NEW, OLD)
        # This fingerprint is regenerated from the identity-bound plan.  Its
        # package-id-only delta is an authorized derived identity change; the
        # remaining observer source must stay byte-equal.
        text = re.sub(
            r"(?m)^// plan_semantic_sha256=[0-9a-f]{64}\r?$",
            "// plan_semantic_sha256=<IDENTITY_BOUND>",
            text,
        )
        return text.encode("utf-8")
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
        old = {PurePosixPath(name).relative_to(OLD).as_posix(): source.read(name) for name in source.namelist() if name.startswith(OLD + "/") and not name.endswith("/")}
        new = {PurePosixPath(name).relative_to(NEW).as_posix(): fresh.read(name) for name in fresh.namelist() if name.startswith(NEW + "/") and not name.endswith("/")}
        required = sorted({path for path in old if path.startswith(FROZEN_PREFIXES)} | set(FROZEN_FILES))
        for path in required:
            if path not in old or path not in new:
                errors.append(f"frozen member absent: {path}")
                continue
            same = normalized(new[path]) == normalized(old[path])
            rows.append({"path": path, "normalized_equal": same, "old_sha256": hashlib.sha256(old[path]).hexdigest(), "new_sha256": hashlib.sha256(new[path]).hexdigest()})
            if not same:
                errors.append(f"frozen member differs: {path}")
        if sorted(path for path in old if path.startswith("workload/")) != sorted(path for path in new if path.startswith("workload/")):
            errors.append("workload member set differs")
        observer = new.get("tb_probe/observer_only_wide_causal.svh", b"").decode("utf-8", errors="replace")
        if "buf_idx_queue_bp_pre" in observer:
            errors.append("retired derived ACK comparator reintroduced")
        mapper = json.loads(new["provenance/lc_branch_duplication_mapper_ab_report.json"])
        if mapper.get("classification") != "VALIDATED_CONFIG_WORKAROUND_CANDIDATE_NOT_PRODUCTION_RUN" or mapper.get("cost", {}).get("negligible") is not True:
            errors.append("mapper equivalence/negligible-cost finding differs")
    report = {
        "schema": "node0004-v101b-frozen-surface-validation-v1",
        "package_id": NEW,
        "pass": not errors,
        "errors": errors,
        "checked_member_count": len(rows),
        "rows": rows,
        "frozen": ["config", "numeric", "workload", "golden", "functional RTL", "LC9-to-LC3 mapper semantics", "52-signal tuple10 target"],
        "claim_boundary": "Byte/identity-normalized frozen-surface comparison only; no production or tuple10 claim.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
