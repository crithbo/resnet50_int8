from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import manage_server_test_package_storage as storage


STORE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
OUT = ROOT / "outputs/conv_node0004_v76_return_v77_successor"
BUILD = OUT / "build"
FAMILY = "conv_serialized_node0004"
PREVIOUS = "r5_n4_hw_v76_sourcebound_boundfix"
CURRENT = "r5_n4_hw_v77_terminal_temporal_ledger_diag"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    result: dict
    try:
        before = storage.audit(STORE)
    except storage.StorageError as exc:
        # Exact idempotent continuation after a process interruption between
        # per-file moves and the final atomic index rewrite.
        partial_receipt_dir = STORE / "pending_receipts" / FAMILY / CURRENT
        prior_tested = STORE / "tested" / FAMILY / PREVIOUS / f"{PREVIOUS}.zip"
        moved_build = partial_receipt_dir / f"{CURRENT}.build.json"
        expected_partial = (
            prior_tested.is_file()
            and moved_build.is_file()
            and not (STORE / "pending" / f"{PREVIOUS}.zip").exists()
            and not (STORE / "pending" / f"{CURRENT}.zip").exists()
            and not (BUILD / f"{CURRENT}.build.json").exists()
        )
        if not expected_partial:
            raise
        annotations = storage.existing_annotations(STORE)
        # A parallel QAdd rotation may have completed its file moves but not
        # its final shared-index commit. Preserve that exact tree without
        # moving or rewriting any QAdd artifact, and add only a transparent
        # storage-recovery annotation so collect_tree_index can represent it.
        for pending_zip in sorted((STORE / "pending").glob("*.zip")):
            base = pending_zip.name[: -len(".zip")]
            if base in annotations:
                continue
            matches = [
                child
                for family_dir in (STORE / "pending_receipts").iterdir()
                if family_dir.is_dir()
                for child in family_dir.iterdir()
                if child.is_dir() and child.name == base
            ]
            if len(matches) != 1:
                raise storage.StorageError(
                    f"cannot uniquely preserve parallel pending identity {base}: {matches}"
                )
            receipt_dir = matches[0]
            evidence_candidates = sorted(receipt_dir.glob("*family_validation.json"))
            if not evidence_candidates:
                evidence_candidates = sorted(receipt_dir.glob("*.build.json"))
            if not evidence_candidates:
                raise storage.StorageError(f"parallel pending identity lacks receipt: {base}")
            evidence = evidence_candidates[0]
            annotations[base] = {
                "family": receipt_dir.parent.name,
                "reason": "parallel pending asset preserved during shared index interrupted-rotation recovery",
                "evidence": {"path": str(evidence), "sha256": sha(evidence)},
            }
        qadd_previous = STORE / "tested/qlinearadd_node0007/r5_qadd_n7_tailround_split_clean_v51"
        if qadd_previous.is_dir():
            qadd_evidence = qadd_previous / "r5_qadd_n7_tailround_split_clean_v51.family_validation.json"
            if qadd_evidence.is_file():
                annotations["r5_qadd_n7_tailround_split_clean_v51"] = {
                    "family": "qlinearadd_node0007",
                    "reason": "parallel predecessor already moved to tested before shared index interruption",
                    "evidence": {"path": str(qadd_evidence), "sha256": sha(qadd_evidence)},
                }
        remaining = storage.validate_source_set(BUILD, CURRENT)
        for source in remaining:
            target = (
                STORE / "pending" / source.name
                if source.name == f"{CURRENT}.zip"
                else partial_receipt_dir / source.name
            )
            if target.exists():
                raise storage.StorageError(f"recovery target already exists: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        previous_evidence = OUT.parent / "conv_node0004_v75_return_v76_successor/release_report.json"
        new_evidence = OUT / "release_report.json"
        annotations[PREVIOUS] = {
            "family": FAMILY,
            "reason": "formal v76 return consumed; bounded collector and canonical temporal-skew class passed",
            "evidence": {"path": str(previous_evidence), "sha256": sha(previous_evidence)},
        }
        annotations[CURRENT] = {
            "family": FAMILY,
            "reason": "v77 exact-target temporal ledger diagnostic; first-fresh independent audit PASS",
            "evidence": {"path": str(new_evidence), "sha256": sha(new_evidence)},
        }
        result = storage.write_index(STORE, annotations)
    else:
        if before.get("pending_by_family", {}).get(FAMILY) != [PREVIOUS]:
            raise SystemExit(
                f"serialized Conv pending identity changed: {before.get('pending_by_family', {}).get(FAMILY)}"
            )
        result = storage.rotate(
            root=STORE,
            source_dir=BUILD,
            family=FAMILY,
            new_base=CURRENT,
            previous_disposition="tested",
            previous_reason="formal v76 return consumed; bounded collector and canonical temporal-skew class passed",
            previous_evidence=OUT.parent / "conv_node0004_v75_return_v76_successor/release_report.json",
            new_reason="v77 exact-target temporal ledger diagnostic; first-fresh independent audit PASS",
            new_evidence=BUILD / f"{CURRENT}.release_report.json",
        )
    after = storage.audit(STORE)
    errors: list[str] = []
    if after.get("pending_by_family", {}).get(FAMILY) != [CURRENT]:
        errors.append("pending family identity mismatch")
    pending = STORE / "pending" / f"{CURRENT}.zip"
    if not pending.is_file():
        errors.append("pending pickup ZIP missing")
    if (STORE / "pending" / f"{PREVIOUS}.zip").exists():
        errors.append("previous ZIP remains pending")
    tested = STORE / "tested" / FAMILY / PREVIOUS / f"{PREVIOUS}.zip"
    if not tested.is_file():
        errors.append("previous ZIP missing from tested archive")
    index = STORE / storage.INDEX_NAME
    write(OUT / "storage_audit.json", after)
    report = {
        "schema": "conv-node0004-v76-v77-storage-rotation-v1",
        "pass": not errors,
        "errors": errors,
        "family": FAMILY,
        "previous": {
            "package_id": PREVIOUS,
            "disposition": "tested",
            "tested_zip": tested.resolve().relative_to(ROOT).as_posix(),
            "tested_zip_sha256": sha(tested) if tested.is_file() else None,
        },
        "current": {
            "package_id": CURRENT,
            "disposition": "pending",
            "pickup_zip": pending.resolve().relative_to(ROOT).as_posix(),
            "zip_bytes": pending.stat().st_size if pending.is_file() else None,
            "zip_sha256": sha(pending) if pending.is_file() else None,
            "receipt_dir": (STORE / "pending_receipts" / FAMILY / CURRENT).resolve().relative_to(ROOT).as_posix(),
        },
        "storage_index": {
            "path": index.resolve().relative_to(ROOT).as_posix(),
            "bytes": index.stat().st_size,
            "sha256": sha(index),
            "pending_by_family": after.get("pending_by_family", {}).get(FAMILY),
            "global_counts": after.get("counts"),
        },
        "rotation_result_index_sha256": hashlib.sha256(
            (json.dumps(result, sort_keys=True) + "\n").encode("utf-8")
        ).hexdigest(),
        "claim_boundary": "Storage disposition and byte identity only; no server execution claim.",
    }
    write(OUT / "storage_rotation_report.json", report)
    print(json.dumps({"pass": not errors, "errors": errors, "index_sha256": sha(index)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
