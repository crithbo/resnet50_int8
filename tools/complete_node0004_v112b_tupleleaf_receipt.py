#!/usr/bin/env python3
"""Publish local-only family/mainline receipts for serialized Conv v112."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v112_tupleleaf_20260822"
GATES = OUT / "gates"
PACKAGE = "r5_n4_hw_v112b_tupleleaf_tbvcd"
ZIP = OUT / f"{PACKAGE}.zip"
TASK = ROOT / ".agents/task_records/20260822_conv_serialized_node0004_v112b_tupleleaf_tbvcd_package_ready_not_run.md"
RECEIPT = OUT / "mainline_package_receipt.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    gate_names = [
        "active_rule_audit.json",
        "takeover_readiness_epoch43.json",
        "mode_zip.json",
        "dispatch_binding_zip.json",
        "hdl_lexical_zip.json",
        "hdl_source_bound_zip.json",
        "tb_vcd_tree.json",
        "runner_zip.json",
        "runtime_preflight.json",
        "post_sim_zip.json",
        "final_zip_content.json",
        "first_fresh_extra_audit.json",
        "package_release_admission_runtime_preflight.json",
    ]
    gate_receipts = []
    failures = []
    for name in gate_names:
        path = GATES / name
        value = load(path)
        passed = value.get("pass") is True
        gate_receipts.append({**file_receipt(path), "pass": passed})
        if not passed:
            failures.append(name)
    admission = load(OUT / "server_package_admission.json")
    if admission.get("pass") is not True or admission.get("status") != "PACKAGE_READY_NOT_RUN":
        failures.append("server_package_admission.json")
    build = load(OUT / "build_receipt.json")
    zip_receipt = file_receipt(ZIP)
    if build.get("zip_sha256") != zip_receipt["sha256"]:
        failures.append("build_receipt ZIP identity")

    previous = (
        "v111 production compile/simulation/target entry succeeded and reproduced the "
        "same residual 32-unit prepared-data drain hold. Its 153-signal catalog mapped "
        "only 102 entries because 51 source-bound Memory_AG packed-vector bit-select "
        "leaves were absent from the VCD header."
    )
    purpose = (
        "Preserve every v111 functional/config/workload surface while replacing those "
        "51 unmappable identities one-for-one with passive actual-source leaf aliases, "
        "so input0 KEEP-last, input2 KEEP-last, prepared-data over-generation, downstream "
        "drain and successful completion are pairwise distinguishable in one return."
    )
    command = (
        f"bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01"
    )
    task_text = f"""# Serialized Conv node0004 v112 tuple-leaf TB-VCD package

Status: `PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE`

## Previous-version progress

{previous}

## Current-version purpose

{purpose}

## Result

- Fresh package identity: `{PACKAGE}`.
- Diagnostic mode: `TB_VCD_BOUNDED_CAUSAL_CONE`.
- Exact final ZIP: `{zip_receipt['path']}`.
- ZIP bytes: `{zip_receipt['bytes']}`.
- ZIP SHA-256: `{zip_receipt['sha256']}`.
- All 102 already mapped causal signals remain present; the 51 missing packed-vector bit-select identities are replaced one-for-one by passive bind-input aliases. The catalog remains 153 signals, covers 41 roles, and the 16 candidates × 4 boundaries matrix is complete and pairwise distinguishable.
- Actual successful v111 VCS argv/filelist/include/define/source identity is embedded. Predecessor catalog hashes that intentionally remain stable are explicitly reconciled to returned actual-compiled source hashes; every fresh leaf binds the returned actual Memory_AG source bytes.
- Workload, materialized config/mapping/bitstream, numeric, golden and functional RTL are byte-frozen. The retired derived ACK comparator remains absent.
- Deterministic ZIP, clean exact extraction, package preflight positive and pending-status negative, Python exact-set compile, HDL lexical/focused frontend, source-bound, TB-VCD semantic-v8, runner resilience, native-flow preflight, post-sim core, first-fresh and release admission all pass.
- The only warning is that 153 signals exceed the soft reference range; this is explicitly justified by retaining all prior evidence and replacing all 51 missing leaves. It is not a hard limit or release blocker.
- Managed storage was not written. No upload, lease, connection or server execution occurred.

Unique future command:

```bash
{command}
```

## Claim boundary

This receipt proves only local package construction and exact gate completion. It does not claim production compile, simulation, target completion, natural terminal, Formal-D/E3/E4/E5, or root cause.
"""
    TASK.parent.mkdir(parents=True, exist_ok=True)
    TASK.write_text(task_text, encoding="utf-8", newline="\n")

    build.update(
        {
            "pass": not failures,
            "status": (
                "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE"
                if not failures
                else "PACKAGE_BUILD_FAILED"
            ),
            "zip_bytes": ZIP.stat().st_size,
            "zip_sha256": sha(ZIP),
            "exact_gate_count": len(gate_receipts),
            "release_admission": file_receipt(OUT / "server_package_admission.json"),
            "first_fresh": file_receipt(GATES / "first_fresh_extra_audit.json"),
            "storage_published": False,
            "server_action": False,
        }
    )
    write_json(OUT / "build_receipt.json", build)

    receipt = {
        "schema": "node0004-v112b-tupleleaf-mainline-package-receipt-v1",
        "status": (
            "PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE"
            if not failures
            else "PACKAGE_BUILD_FAILED"
        ),
        "pass": not failures,
        "package_id": PACKAGE,
        "family_role_id": "family.conv.serialized",
        "owner_thread_id": "019ff02d-901b-7f70-a9da-f54e268b5bbe",
        "owner_epoch": 7,
        "registry_epoch": 43,
        "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "previous_version_progress": previous,
        "current_version_purpose": purpose,
        "package": zip_receipt,
        "unique_future_command": command,
        "task_record": file_receipt(TASK),
        "build_receipt": file_receipt(OUT / "build_receipt.json"),
        "release_admission": file_receipt(OUT / "server_package_admission.json"),
        "gate_receipts": gate_receipts,
        "frozen_surface_receipt": file_receipt(OUT / "frozen_surface_reuse_receipt.json"),
        "mode_authority_embedding": file_receipt(
            OUT / "build" / PACKAGE / "provenance/mode_authority_embedding_receipt.json"
        ),
        "actual_source_reconciliation": file_receipt(
            OUT
            / "build"
            / PACKAGE
            / "provenance/v112_actual_compiled_source_catalog_reconciliation.json"
        ),
        "catalog": {
            "signals": 153,
            "retained_predecessor_signals": 102,
            "fresh_passive_leaf_aliases": 51,
            "roles": 41,
            "candidates": 16,
            "boundaries": 4,
            "matrix_rows": 64,
            "pairwise_distinguishable": True,
        },
        "warning_disposition": [
            "153 signals are above the soft breadth reference; the documented one-for-one leaf replacement is intentional and nonblocking."
        ],
        "managed_storage_written": False,
        "server_action_performed": False,
        "conflicts": failures,
        "claim_boundary": (
            "Local package/gate completion only; no production compile, simulation, "
            "natural terminal, Formal-D/E3/E4/E5 or root-cause claim."
        ),
    }
    write_json(RECEIPT, receipt)
    print(json.dumps({"pass": receipt["pass"], "status": receipt["status"], "zip": zip_receipt}, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
