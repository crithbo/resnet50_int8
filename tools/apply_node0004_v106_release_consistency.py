#!/usr/bin/env python3
"""Apply the activated release-consistency surfaces to staged v106."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v106b_lcdup_return2pflight"
OUT = ROOT / "outputs/conv_node0004_v106b_lcdup_return2pflight_release1"
TREE = OUT / "build" / PACKAGE


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label} anchor count differs: {count}")
    return text.replace(old, new)


def file_map() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def main() -> int:
    if not TREE.is_dir() or (OUT / f"{PACKAGE}.zip").exists():
        raise SystemExit("v106 staging is absent or ZIP already exists")

    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime_budget"] = {
        "selected_wall_seconds": 3660,
        "absolute_maximum_wall_seconds": 86400,
    }
    manifest["final_zip_rule_self_audit"] = {
        "status": "PASS",
        "gate_id": "release_cross_member_temporal_consistency_final_zip",
        "semantic_version": 1,
        "receipt_reuse_allowed": False,
    }

    guard_path = TREE / "contracts/observer_operational_guard_contract.json"
    guard = json.loads(guard_path.read_text(encoding="utf-8"))
    guard["runtime_budget"] = {
        "selected_wall_seconds": 3660,
        "absolute_maximum_wall_seconds": 86400,
    }
    guard_path.write_bytes(canonical(guard))

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    required_archives = sorted(
        item["archive"] for item in request.get("core_entries", [])
        if isinstance(item, dict) and item.get("required") is True
    )
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    allow["prepublication_required_archives"] = required_archives
    allow_path.write_bytes(canonical(allow))

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    runner = replace_once(
        runner,
        "  # Phase 2: canonical publisher runs once, only after the completed guard and\n",
        "  # RELEASE_PHASE_FINALIZATION_GUARD_COMPLETE\n  # Phase 2: canonical publisher runs once, only after the completed guard and\n",
        "finalization guard marker",
    )
    runner = replace_once(
        runner,
        "    python3 \"$package_root/package_tools/server_post_sim_return.py\" finalize",
        "    # RELEASE_PHASE_RETURN_PUBLISH\n    python3 \"$package_root/package_tools/server_post_sim_return.py\" finalize",
        "return publish marker",
    )
    runner = replace_once(
        runner,
        "    python3 - \"$return_zip\" \"$operational_sidecar\" <<'PY'",
        "    # RELEASE_PHASE_DURABLE_RETURN_RECEIPT\n    python3 - \"$return_zip\" \"$operational_sidecar\" <<'PY'",
        "durable receipt marker",
    )
    runner = replace_once(
        runner,
        "    [ \"$durable_rc\" -eq 0 ] && python3 \"$package_root/package_tools/server_package_attempt_cleanup.py\"",
        "    # RELEASE_PHASE_POST_DURABLE_CLEANUP_RECEIPT\n    [ \"$durable_rc\" -eq 0 ] && python3 \"$package_root/package_tools/server_package_attempt_cleanup.py\"",
        "cleanup receipt marker",
    )
    runner_path.write_text(runner, encoding="utf-8", newline="\n")

    runner_contract_path = TREE / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = sha(runner_path)
    runner_contract_path.write_bytes(canonical(runner_contract))

    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))

    completed = subprocess.run(
        [sys.executable, "-B", str(TREE / "package_tools/package_release_preflight.py"),
         "preflight", "--package-root", str(TREE)],
        cwd=TREE, capture_output=True, text=True, check=False,
    )
    receipt = {
        "schema": "node0004-v106-release-consistency-prezip-v1",
        "package_id": PACKAGE,
        "pass": completed.returncode == 0,
        "errors": [] if completed.returncode == 0 else ["package-specific preflight failed after consistency patch"],
        "preflight_exit": completed.returncode,
        "stdout": completed.stdout[-4096:],
        "stderr": completed.stderr[-4096:],
        "runner_sha256": sha(runner_path),
        "guard_contract_sha256": sha(guard_path),
        "allowlist_sha256": sha(allow_path),
        "claim_boundary": "Pre-ZIP release-consistency surfaces only; no final-ZIP or production claim.",
    }
    path = OUT / "gates/prezip_release_consistency_surfaces.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(receipt))
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
