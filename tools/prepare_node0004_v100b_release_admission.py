#!/usr/bin/env python3
"""Prepare exact release-admission inputs for serialized v100."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v99b_lcdup_guarded"
NEW = "r5_n4_hw_v100b_lcdup_guardv2"
OUT = ROOT / "outputs/conv_node0004_v100b_lcdup_guardv2_release1"
ZIP = OUT / f"{NEW}.zip"
ADMISSION = OUT / "release_admission"
CLAIM = "Local mapper-A/B-preserving operational guard-v2 observer package release; no production tuple10, natural-terminal, Formal-D, E3, E4 or E5 claim."


def canonical(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    ADMISSION.mkdir(parents=True, exist_ok=True)
    zip_sha = sha_file(ZIP)
    with zipfile.ZipFile(ZIP) as archive:
        runner = archive.read(f"{NEW}/PREPARE_AND_RUN.sh")
    precompile = {
        "schema": "server-precompile-preflight-failure-core-v1",
        "package_id": NEW,
        "final_zip_sha256": zip_sha,
        "runner_member_sha256": hashlib.sha256(runner).hexdigest(),
        "compile_started": False,
        "simulation_started": False,
        "preflight": {"exit_code": 19, "stdout": "", "stderr": "package claim boundary differs\n"},
        "core_return": {"classification": "COMPILE_NOT_STARTED", "published": True, "required_evidence": ["preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"]},
        "claim_boundary": "Precompile package-claim failure visibility only.",
    }
    precompile_path = ADMISSION / "precompile_failure_core.json"
    precompile_path.write_bytes(canonical(precompile))
    release = {
        "schema": "node0004-v100b-release-admission-receipt-v1",
        "package_id": NEW,
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "pass": True,
        "package": {"path": str(ZIP.relative_to(ROOT)).replace("\\", "/"), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
        "claim_boundary": CLAIM,
    }
    release_path = ADMISSION / "release_receipt.json"
    release_path.write_bytes(canonical(release))
    source = json.loads((ROOT / "outputs/conv_node0004_v99b_lcdup_guarded_release6/release_admission/contract.json").read_text(encoding="utf-8"))
    rendered = json.loads(json.dumps(source).replace("outputs/conv_node0004_v99b_lcdup_guarded_release6", "outputs/conv_node0004_v100b_lcdup_guardv2_release1").replace(OLD, NEW))
    rendered["package"]["final_zip"] = {"path": str(ZIP.relative_to(ROOT)).replace("\\", "/"), "bytes": ZIP.stat().st_size, "sha256": zip_sha}
    rendered["precompile_failure_core"]["sha256"] = sha_file(precompile_path)
    rendered["release_receipt"]["expected_claim_boundary"] = CLAIM
    rendered["release_receipt"]["sha256"] = sha_file(release_path)
    contract_path = ADMISSION / "contract.json"
    contract_path.write_bytes(canonical(rendered))
    print(contract_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
