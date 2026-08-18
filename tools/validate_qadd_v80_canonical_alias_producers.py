#!/usr/bin/env python3
"""Production-shaped validation of v80 canonical VCD alias producers and guard."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ALIASES = {
    "catalog.json",
    "candidate_matrix.json",
    "tb_source.json",
    "elaboration.json",
    "runtime.json",
    "return_manifest.json",
}
FINAL_RECEIPT = "finalization_receipt.json"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def guard(root: Path, package_id: str, execution_id: str, attempt_id: str) -> bool:
    receipt = root / FINAL_RECEIPT
    if not receipt.is_file() or receipt.is_symlink() or not root.is_dir() or root.is_symlink():
        return False
    value = load(receipt)
    if (
        value.get("schema") != "qadd-tb-vcd-finalization-guard-receipt-v1"
        or value.get("package_id") != package_id
        or value.get("execution_id") != execution_id
        or value.get("attempt_id") != attempt_id
        or value.get("ready_for_return_publish") is not True
    ):
        return False
    rows = value.get("required_aliases")
    mapped = {row.get("name"): row for row in rows if isinstance(row, dict)} if isinstance(rows, list) else {}
    if set(mapped) != ALIASES:
        return False
    for name in sorted(ALIASES):
        path = root / name
        if not path.is_file() or path.is_symlink():
            return False
        if mapped[name].get("bytes") != path.stat().st_size or mapped[name].get("sha256") != sha(path):
            return False
    manifest = load(root / "return_manifest.json")
    manifest_rows = {row.get("name"): row for row in manifest.get("aliases", []) if isinstance(row, dict)}
    return set(manifest_rows) == ALIASES - {"return_manifest.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = args.package_root.resolve()
    package_id = "r5_qadd_n7_tr_v80_w15kqf"
    execution_id = "producer-harness"
    attempt_id = "attempt-producer-harness"
    finalizer = package / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v80.py"
    with tempfile.TemporaryDirectory(prefix="qadd-v80-producer-") as temporary:
        root = Path(temporary)
        attempt = root / "attempt"
        evidence = attempt / "evidence"
        attempt.mkdir()
        command = [
            sys.executable,
            "-B",
            str(finalizer),
            "--package-root", str(package),
            "--attempt-root", str(attempt),
            "--evidence-root", str(evidence),
            "--package-id", package_id,
            "--execution-id", execution_id,
            "--attempt-id", attempt_id,
            "--actual-root", "/synthetic/NDP_copy04",
            "--published-root", "/synthetic/NDP_copy04",
            "--compile-exit", "2",
            "--sim-exit", "125",
            "--signal", "NONE",
            "--vcd", str(attempt / "absent.vcd"),
            "--sim-log", str(attempt / "absent.log"),
            "--samples", str(attempt / "absent.jsonl"),
            "--process-receipt", str(attempt / "absent-process.json"),
            "--safety-receipt", str(attempt / "absent-safety.json"),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        vcd_root = evidence / "vcd"
        positive = result.returncode in {0, 97} and guard(vcd_root, package_id, execution_id, attempt_id)
        missing_negatives: dict[str, bool] = {}
        corruption_negatives: dict[str, bool] = {}
        for name in sorted({*ALIASES, FINAL_RECEIPT}):
            case = root / f"missing-{name.replace('.', '-') }"
            shutil.copytree(vcd_root, case)
            (case / name).unlink()
            missing_negatives[name] = not guard(case, package_id, execution_id, attempt_id)
            case = root / f"corrupt-{name.replace('.', '-') }"
            shutil.copytree(vcd_root, case)
            if name == FINAL_RECEIPT:
                corrupted = load(case / name)
                corrupted["ready_for_return_publish"] = False
                (case / name).write_text(json.dumps(corrupted, sort_keys=True) + "\n", encoding="utf-8")
            else:
                (case / name).write_bytes((case / name).read_bytes() + b"\n")
            corruption_negatives[name] = not guard(case, package_id, execution_id, attempt_id)
        report = {
            "schema": "qadd-v80-canonical-alias-producer-validation-v1",
            "package_id": package_id,
            "finalizer": {"path": str(finalizer), "bytes": finalizer.stat().st_size, "sha256": sha(finalizer)},
            "invocation": {"argv": command, "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr},
            "positive_producer_and_guard": positive,
            "missing_alias_negatives_fail_closed": missing_negatives,
            "corrupt_alias_negatives_fail_closed": corruption_negatives,
            "pass": positive and all(missing_negatives.values()) and all(corruption_negatives.values()),
            "errors": [],
            "claim_boundary": "Local production-shaped package finalizer/guard evidence only; no production Linux/VCS or DUT claim.",
        }
        if not report["pass"]:
            report["errors"] = ["canonical alias producer/guard positive or negative control failed"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": package_id, "pass": report["pass"], "exit_code": result.returncode}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
