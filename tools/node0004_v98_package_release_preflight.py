#!/usr/bin/env python3
"""Read-only release preflight for the serialized Conv LC-duplication package."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


PACKAGE = "r5_n4_hw_v98b_lcdup_tuple10"
READY = "PACKAGE_READY_NOT_RUN"
MARKER = "package claim boundary differs"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def preflight(root: Path) -> list[str]:
    root = root.resolve(strict=True)
    manifest = load(root / "package_manifest.json")
    contract = load(root / "contracts/observer_only_wide_causal_contract.json")
    proof = load(root / "provenance/lc_branch_duplication_mapper_ab_report.json")
    errors: list[str] = []
    if root.name != PACKAGE or manifest.get("package_id") != PACKAGE:
        errors.append(f"{MARKER}: package identity differs")
    if manifest.get("status") != READY:
        errors.append(f"{MARKER}: embedded status is not {READY}")
    if manifest.get("diagnostic_mode") != "OBSERVER_ONLY_WIDE_CAUSAL":
        errors.append("diagnostic mode differs")
    if manifest.get("dump") != {"DUMP_FSDB": 0, "DUMP_VCD": 0, "TB_DUMP_FSDB": 0}:
        errors.append("dump profile differs")
    if manifest.get("config_workaround") != "DUPLICATE_LC_BRANCH_LC9_TO_LC3_FOR_PE1_INPUT2":
        errors.append("authorized config workaround identity differs")
    if proof.get("classification") != "VALIDATED_CONFIG_WORKAROUND_CANDIDATE_NOT_PRODUCTION_RUN":
        errors.append("mapper A/B proof classification differs")
    if proof.get("cost", {}).get("negligible") is not True:
        errors.append("mapper A/B negligible-cost proof differs")
    if contract.get("package_id") != PACKAGE or contract.get("profile") != "OBSERVER_ONLY_WIDE_CAUSAL_V1":
        errors.append("observer contract identity differs")
    execution = contract.get("execution", {})
    if any(token not in execution.get("compile_argv", []) for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")):
        errors.append("compile dump argv differs")
    runner = (root / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    if runner.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        errors.append("production launch marker count differs")
    if "buf_idx_queue_bp_pre" in (root / "tb_probe/observer_only_wide_causal.svh").read_text(encoding="utf-8"):
        errors.append("retired derived ACK comparator reintroduced")
    declared = manifest.get("files", [])
    actual = [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]
    if declared != actual:
        errors.append("embedded package file map differs")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preflight",))
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        errors = preflight(args.package_root)
    except Exception as exc:
        errors = [str(exc)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 19 if any(MARKER in item for item in errors) else 3
    print(json.dumps({"package_id": PACKAGE, "status": READY, "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
