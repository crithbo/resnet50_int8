#!/usr/bin/env python3
"""Bind consumed config, actual compiled source capture and dynamic receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def identity(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--actual-root", required=True)
    parser.add_argument("--published-root", required=True)
    parser.add_argument("--config-root", required=True, type=Path)
    parser.add_argument("--bootstrap-root", required=True, type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--compile-exit", required=True, type=int)
    parser.add_argument("--sim-exit", required=True, type=int)
    args = parser.parse_args()

    source_manifest_path = args.bootstrap_root / "actual_compiled_sources/manifest.json"
    source_manifest = load(source_manifest_path)
    config_paths = [args.config_root / "runs/c0/sca_cfg.json", args.config_root / "runs/c0/sca_cfg_D.json"]
    actual_argv_path = args.bootstrap_root / "ACTUAL_COMPILE_SIM_ARGV.json"
    runtime_path = args.evidence_root / "TB_VCD_RUNTIME_RECEIPT.json"
    stop_path = args.evidence_root / "TB_VCD_STOP_RECEIPT.json"
    review = {
        "schema": "conv-native-config-actual-rtl-dynamic-evidence-review-v1",
        "package_id": args.package_id,
        "execution_id": args.execution_id,
        "attempt_id": args.attempt_id,
        "actual_root": args.actual_root,
        "published_root": args.published_root,
        "root_match": args.actual_root == args.published_root,
        "compile_exit": args.compile_exit,
        "sim_exit": args.sim_exit,
        "DIRECT_CONFIG_EVIDENCE": {
            "consumed_config_identities": [identity(path) for path in config_paths],
            "config_bytes_modified_by_package": False,
            "validated_config_to_join_cause": False,
        },
        "DIRECT_ACTUAL_RTL_EVIDENCE": {
            "post_compile_capture_manifest": identity(source_manifest_path),
            "capture": source_manifest,
            "actual_argv": identity(actual_argv_path),
            "actual_source_bytes_returned": bool(isinstance(source_manifest, dict) and source_manifest.get("complete")),
        },
        "DYNAMIC_EXECUTION_EVIDENCE": {
            "runtime_receipt": identity(runtime_path),
            "runtime": load(runtime_path),
            "stop_receipt": identity(stop_path),
            "stop": load(stop_path),
        },
        "root_disposition": "OPEN_UNVALIDATED_MECHANISM",
        "CONFIG_WORKAROUND": None,
        "claim_boundary": (
            "The receipt binds direct config, post-compile actual RTL bytes and dynamic runtime evidence. "
            "It does not itself promote a mechanism to VALIDATED_ROOT_CAUSE."
        ),
    }
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    output = args.evidence_root / "CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json"
    output.write_text(json.dumps(review, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
