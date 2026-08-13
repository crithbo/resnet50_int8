"""Attach v54 release receipts and refresh the shared storage index."""

from __future__ import annotations

import shutil
from pathlib import Path

import manage_server_test_package_storage as storage


ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-bufready-v54-package"
FAMILY = "qlinearadd_node0007"
NAME = "r5_qadd_n7_tailround_bufready_v54"
RECEIPTS = STORE / "pending_receipts" / FAMILY / NAME
FILES = {
    "build_receipt.json": f"{NAME}.build.json",
    "prebuild_aggregate.json": f"{NAME}.prebuild.json",
    "family_validation.json": f"{NAME}.family_validation.json",
    "final_zip_self_audit.json": f"{NAME}.final_zip_audit.json",
    "hdl_gate_positive.json": f"{NAME}.hdl_gate.json",
    "predicate_trace_validation.json": f"{NAME}.predicate_trace.json",
    "runtime_layout_harness.json": f"{NAME}.runtime_layout_harness.json",
    "shared_runtime_layout_validation.json": f"{NAME}.shared_runtime_layout.json",
    "release_report.json": f"{NAME}.release_report.json",
}


def main() -> int:
    pending_before = sorted(path.name for path in (STORE / "pending").glob("*.zip"))
    expected = {
        "r5_n4_0cc_p32b_validowner.zip",
        "r5_n4_hw_v78_buffer_input_owner_diag.zip",
        f"{NAME}.zip",
    }
    if set(pending_before) != expected:
        raise RuntimeError(f"pending set differs before receipt attachment: {pending_before}")
    for source_name, target_name in FILES.items():
        source = LOCAL / source_name
        target = RECEIPTS / target_name
        if not source.is_file():
            raise RuntimeError(f"missing release receipt: {source}")
        if target.exists():
            raise RuntimeError(f"refusing receipt overwrite: {target}")
        shutil.copy2(source, target)
    annotations = storage.existing_annotations(STORE)
    evidence = RECEIPTS / f"{NAME}.final_zip_audit.json"
    annotations[NAME] = {
        "family": FAMILY,
        "reason": "v52 continuous-closure highest-information isolated Buffer5 selected-read-ready diagnostic; PACKAGE_READY_NOT_RUN",
        "evidence": {"path": str(evidence.resolve()), "sha256": storage.sha256(evidence)},
    }
    index = storage.write_index(STORE, annotations)
    pending_after = sorted(path.name for path in (STORE / "pending").glob("*.zip"))
    if pending_after != pending_before or index["pending_by_family"].get(FAMILY) != [NAME]:
        raise RuntimeError("pending identities changed while attaching receipts")
    print({"pass": True, "pending": pending_after, "receipt_count": len(FILES), "index": str(STORE / storage.INDEX_NAME)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
