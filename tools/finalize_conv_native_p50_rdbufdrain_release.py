#!/usr/bin/env python3
"""Fail-closed local release receipt for native Conv p50.

This finalizer never invokes the storage manager and never performs a server
action.  It consumes only the already-built staging tree, deterministic ZIPs,
formal p49 analysis and local gate reports.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p50_rdbufdrain"
SOURCE_ID = "r5_n4_0cc_p49_tbvcdrt2"
FAMILY = "conv_native_four_lane"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release"
TREE = OUT / "build" / PACKAGE_ID
ZIP = OUT / f"{PACKAGE_ID}.zip"
REPEAT = OUT / f"{PACKAGE_ID}.repeat.zip"
GATES = OUT / "gates"
ANALYSIS = ROOT / (
    "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_return_analysis_"
    "r1786716730326805125_2394257"
)
STORAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = STORAGE / "pending" / f"{SOURCE_ID}.zip"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def main() -> int:
    errors: list[str] = []
    required_gate_names = [
        "first_fresh_validation.json",
        "tb_vcd_tree_v4.json",
        "mode_selector_tree_v4.json",
        "mode_selector_zip_v4.json",
        "hdl_lexical_tree_v4.json",
        "hdl_lexical_zip_v4.json",
        "runtime_preflight_v4.json",
        "runner_tree_v4.json",
        "runner_zip_v4.json",
        "post_sim_final_zip_v4.json",
        "package_release_admission.json",
        "package_release_receipt.json",
        "current_shared_regression.json",
    ]
    gate_receipts: list[dict[str, Any]] = []
    for name in required_gate_names:
        path = GATES / name
        if not path.is_file():
            errors.append(f"missing gate: {name}")
            continue
        report = load(path)
        if report.get("pass") is not True:
            errors.append(f"gate not pass: {name}")
        gate_receipts.append({"name": name, **identity(path)})

    for path in (ZIP, REPEAT, SOURCE_ZIP):
        if not path.is_file():
            errors.append(f"required artifact absent: {path}")
    if ZIP.is_file() and REPEAT.is_file() and ZIP.read_bytes() != REPEAT.read_bytes():
        errors.append("deterministic exact-ZIP recomputation differs")

    direct_review_path = ANALYSIS / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json"
    if not direct_review_path.is_file():
        errors.append("p49 direct config/RTL review absent")
        direct_review = {}
    else:
        direct_review = load(direct_review_path)
        if direct_review.get("pass") is not True:
            errors.append("p49 direct config/RTL review is not pass")
        if direct_review.get("root_disposition") != "OPEN_UNVALIDATED_MECHANISM":
            errors.append("p49 root disposition unexpectedly changed")

    manifest_errors: list[str] = []
    if ZIP.is_file():
        with zipfile.ZipFile(ZIP) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                manifest_errors.append("duplicate ZIP member")
            prefix = f"{PACKAGE_ID}/"
            manifest_member = prefix + "package_manifest.json"
            if manifest_member not in names:
                manifest_errors.append("package manifest missing")
            else:
                manifest = json.loads(archive.read(manifest_member))
                expected_files = manifest.get("files", {})
                actual_rel = {name[len(prefix):] for name in names if name.startswith(prefix)}
                expected_rel = set(expected_files) | {"package_manifest.json"}
                if actual_rel != expected_rel:
                    manifest_errors.append("manifest member exact-set mismatch")
                for rel, record in expected_files.items():
                    member = prefix + rel
                    if member not in names:
                        continue
                    payload = archive.read(member)
                    if len(payload) != record.get("size_bytes") or sha_bytes(payload) != record.get("sha256"):
                        manifest_errors.append(f"manifest identity mismatch: {rel}")
                package_review = archive.read(prefix + "diagnostics/p49_config_rtl_direct_evidence_review.json")
                if package_review != direct_review_path.read_bytes():
                    manifest_errors.append("packaged direct config/RTL review differs from p49 analysis receipt")
                packaged_helper = archive.read(prefix + "package_tools/server_post_sim_return.py")
                if packaged_helper != (ROOT / "tools/server_post_sim_return.py").read_bytes():
                    manifest_errors.append("packaged post-sim helper differs from current canonical helper")
    errors.extend(manifest_errors)

    p49_cfg_root = (
        ROOT / "outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_release/build" /
        SOURCE_ID / "workload/runtime/runs/c0"
    )
    p50_cfg_root = TREE / "workload/runtime/runs/c0"
    frozen_config_receipts: list[dict[str, Any]] = []
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        source = p49_cfg_root / name
        current = p50_cfg_root / name
        if not source.is_file() or not current.is_file() or source.read_bytes() != current.read_bytes():
            errors.append(f"frozen config differs: {name}")
        elif current.is_file():
            frozen_config_receipts.append({"name": name, **identity(current)})

    p50_storage_matches = sorted(STORAGE.glob(f"*/**/{PACKAGE_ID}.zip"))
    if p50_storage_matches:
        errors.append("p50 unexpectedly exists in managed storage before serialized release")

    report = {
        "schema": "conv-native-p50-final-zip-release-audit-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "LOCAL_TERMINAL_GATE_FAILURE",
        "storage_disposition": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "unique_future_command": (
            f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01"
        ),
        "expected_return": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_<execution>_return.zip"
        ),
        "zip": identity(ZIP) if ZIP.is_file() else None,
        "repeat_zip": identity(REPEAT) if REPEAT.is_file() else None,
        "source_p49_pending": identity(SOURCE_ZIP) if SOURCE_ZIP.is_file() else None,
        "direct_config_rtl_review": identity(direct_review_path) if direct_review_path.is_file() else None,
        "root_disposition": direct_review.get("root_disposition"),
        "frozen_config_receipts": frozen_config_receipts,
        "gate_receipts": gate_receipts,
        "manifest_exact_set_pass": not manifest_errors,
        "deterministic_zip_pass": ZIP.is_file() and REPEAT.is_file() and ZIP.read_bytes() == REPEAT.read_bytes(),
        "p50_storage_matches": [path.relative_to(ROOT).as_posix() for path in p50_storage_matches],
        "storage_manager_invoked": False,
        "server_actions_performed": [],
        "errors": errors,
        "pass": not errors,
        "claim_boundary": (
            "Local build/gates only. No p50 production compile/simulation, validated root cause, natural terminal, "
            "formal D, E3, E4 or E5 is claimed. Direct config evidence and actual compiler-path evidence do not "
            "substitute for missing actual functional RTL content identity or candidate-specific runtime transitions."
        ),
    }
    final_path = GATES / "final_zip_release_audit.json"
    final_path.write_bytes(canonical(report))
    evidence = {
        "schema": "conv-native-p50-release-evidence-v1",
        "package_id": PACKAGE_ID,
        "family": FAMILY,
        "status": report["status"],
        "final_zip_release_audit": identity(final_path),
        "package": report["zip"],
        "storage_disposition": report["storage_disposition"],
        "previous_version_progress": (
            "p41 passed production compile beyond Datahub; p42 corrected the vector predicate; p46 crossed "
            "descriptor/buffer/MemAG/write-data accepts; p49 narrowed the frozen boundary after target entry."
        ),
        "current_version_purpose": (
            "Validate the prepared-count/data-metadata/output-admission/last-finish mechanisms and the exact "
            "consumed-config dependency with current runtime-v3 evidence, without modifying frozen payloads."
        ),
        "root_disposition": report["root_disposition"],
        "server_actions_performed": [],
        "errors": errors,
        "pass": not errors,
        "claim_boundary": report["claim_boundary"],
    }
    evidence_path = OUT / f"{PACKAGE_ID}.release_evidence.json"
    evidence_path.write_bytes(canonical(evidence))
    wait_path = OUT / "storage_wait_receipt.json"
    wait_path.write_bytes(canonical({
        "schema": "conv-native-p50-storage-wait-v1",
        "package_id": PACKAGE_ID,
        "disposition": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "p50_present_in_managed_storage": bool(p50_storage_matches),
        "storage_manager_invoked": False,
        "server_actions_performed": [],
        "pass": not p50_storage_matches,
    }))
    print(json.dumps({"package_id": PACKAGE_ID, "pass": not errors, "errors": errors}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
