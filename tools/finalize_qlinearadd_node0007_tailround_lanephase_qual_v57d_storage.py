#!/usr/bin/env python3
"""Publish the audited QAdd v57f runner fix without clobbering concurrent families."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import manage_server_test_package_storage as storage


STORE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
INDEX = STORE / storage.INDEX_NAME
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57f-package"
SOURCE = LOCAL / "storage_release_source"
NAME = "r5_qadd_n7_tailround_lanephase_qual_v57f"
FAMILY = "qlinearadd_node0007"
PREVIOUS = "r5_qadd_n7_tailround_lanephase_qual_v57d"
EXPECTED_INDEX_SHA = "df80bdcbc35977b0b35817fb92b5465d92ee1beee9dd7b100c07a07c0a6ab842"
EXPECTED_PENDING = {
    "r5_n4_0cc_p38_mse4join.zip",
    "r5_n4_hw_v84b_ack_inline_realtime_diag.zip",
    "r5_qadd_n7_tailround_lanephase_qual_v57d.zip",
}
PREVIOUS_EVIDENCE = (
    STORE
    / "pending_receipts/qlinearadd_node0007/r5_qadd_n7_tailround_lanephase_qual_v57d"
    / "r5_qadd_n7_tailround_lanephase_qual_v57d.final_zip_audit.json"
)
TASK = ROOT / ".agents/task_records/20260811_qlinearadd_node0007_v57d_runtime_failure_v57f_runnerfix.md"
FILES = {
    LOCAL / f"{NAME}.zip": f"{NAME}.zip",
    LOCAL / f"{NAME}.zip.sha256": f"{NAME}.zip.sha256",
    LOCAL / "prebuild_aggregate.json": f"{NAME}.prebuild.json",
    LOCAL / "build_receipt.json": f"{NAME}.build.json",
    LOCAL / "family_validation.json": f"{NAME}.family_validation.json",
    LOCAL / "final_zip_self_audit.json": f"{NAME}.final_zip_audit.json",
    LOCAL / "release_report.json": f"{NAME}.release_report.json",
    LOCAL / "independent_exact_zip_audit_v2/clean_extract_validation.json": f"{NAME}.clean_extract.json",
    LOCAL / "independent_exact_zip_audit_v2/runner_and_input_validation.json": f"{NAME}.runner_input.json",
    LOCAL / "independent_exact_zip_audit_v2/source_bound_final_zip_validation.json": f"{NAME}.source_bound_final_zip.json",
    LOCAL / "independent_exact_zip_audit_v2/post_sim_return_final_zip_validation.json": f"{NAME}.post_sim.json",
    LOCAL / "independent_exact_zip_audit_v2/stage_filter_negative_controls.json": f"{NAME}.stage_filter.json",
    LOCAL / "independent_exact_zip_audit_v2/runtime_layout_harness.json": f"{NAME}.runtime_layout_harness.json",
    LOCAL / "independent_exact_zip_audit_v2/shared_runtime_layout_validation.json": f"{NAME}.shared_layout.json",
    TASK: f"{NAME}.task_record.md",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if sha(INDEX) != EXPECTED_INDEX_SHA:
        raise RuntimeError(f"storage preimage drift: {sha(INDEX)}")
    pending_before = {path.name for path in (STORE / "pending").glob("*.zip")}
    if pending_before != EXPECTED_PENDING:
        raise RuntimeError(f"pending preimage differs: {sorted(pending_before)}")
    if SOURCE.exists():
        raise RuntimeError(f"fresh storage source required: {SOURCE}")
    missing = [str(path) for path in FILES if not path.is_file()]
    if missing:
        raise RuntimeError(f"release inputs missing: {missing}")
    SOURCE.mkdir(parents=True)
    for source, name in FILES.items():
        shutil.copy2(source, SOURCE / name)
    result = storage.rotate(
        root=STORE,
        source_dir=SOURCE,
        family=FAMILY,
        new_base=NAME,
        previous_disposition="superseded",
        previous_reason="v57d server run terminated at runner line 18 because run_root was referenced before assignment under set -u",
        previous_evidence=PREVIOUS_EVIDENCE,
        new_reason="v57d runner-only initialization fix with exact startup controls; all current exact-ZIP gates PASS; PACKAGE_READY_NOT_RUN",
        new_evidence=SOURCE / f"{NAME}.final_zip_audit.json",
    )
    pending_after = {path.name for path in (STORE / "pending").glob("*.zip")}
    expected_after = {
        "r5_n4_0cc_p38_mse4join.zip",
        "r5_n4_hw_v84b_ack_inline_realtime_diag.zip",
        f"{NAME}.zip",
    }
    if pending_after != expected_after:
        raise RuntimeError(f"pending postimage differs: {sorted(pending_after)}")
    current = storage.load_json(INDEX)
    checks = {
        "preimage_exact": True,
        "native_p38_preserved": "r5_n4_0cc_p38_mse4join" in current.get("pending_by_family", {}).get("conv_native_four_lane", []),
        "serialized_v84b_preserved": "r5_n4_hw_v84b_ack_inline_realtime_diag" in current.get("pending_by_family", {}).get("conv_serialized_node0004", []),
        "qadd_v57f_unique_pending": current.get("pending_by_family", {}).get(FAMILY) == [NAME],
        "qadd_v57d_superseded": any(row.get("package_base") == PREVIOUS and row.get("disposition") == "superseded" for row in current.get("packages", [])),
        "pending_zip_only": all(path.suffix == ".zip" for path in (STORE / "pending").iterdir() if path.is_file()),
    }
    receipt = {
        "schema": "qlinearadd-node0007-tailround-lanephase-qual-v57f-storage-rotation-v1",
        "pass": all(checks.values()),
        "errors": [key for key, passed in checks.items() if not passed],
        "checks": checks,
        "index_preimage": {"bytes": 351212, "sha256": EXPECTED_INDEX_SHA},
        "index_postimage": {"bytes": INDEX.stat().st_size, "sha256": sha(INDEX)},
        "pending_before": sorted(pending_before),
        "pending_after": sorted(pending_after),
        "pickup": f"artifacts/operator_config_validation/r5-server-test-packages/pending/{NAME}.zip",
        "manager_result_counts": result.get("counts"),
    }
    write(LOCAL / "storage_rotation_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
