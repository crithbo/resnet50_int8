#!/usr/bin/env python3
"""Apply the aggregate native-flow marker repair to the existing v62 staging."""

from __future__ import annotations

import json
from pathlib import Path

import build_qlinearadd_node0007_v62_nativeflow as build


EXPECTED_RUNNER_SHA256 = "10e5e2d8e48b22461dda63ced9c8a8e5b3e64baa3c17106c222f5d62fda0dd46"


def main() -> int:
    runner = build.TREE / "PREPARE_AND_RUN.sh"
    if build.digest(runner) != EXPECTED_RUNNER_SHA256:
        raise RuntimeError("v62 staging runner is not the aggregate-failure identity")
    text = runner.read_text(encoding="utf-8")
    old_marker = 'case "$1" in /*) ;; *) runner_fail 2 "server root argument is not absolute";; esac\n# CODEX_PRODUCTION_LAUNCH\n'
    text = build.replace_once(
        text,
        old_marker,
        'case "$1" in /*) ;; *) runner_fail 2 "server root argument is not absolute";; esac\n',
        "old production marker",
    )
    late = '''trap 'finalize $?' EXIT
trap 'on_signal HUP 129' HUP
trap 'on_signal INT 130' INT
trap 'on_signal TERM 143' TERM
'''
    text = build.replace_once(text, late, "", "late finalizer traps")
    early_anchor = "actual_argv_json=\n"
    early = (
        early_anchor
        + "trap 'finalize $?' EXIT\n"
        + "trap 'on_signal HUP 129' HUP\n"
        + "trap 'on_signal INT 130' INT\n"
        + "trap 'on_signal TERM 143' TERM\n"
        + "# CODEX_PRODUCTION_LAUNCH\n"
    )
    text = build.replace_once(text, early_anchor, early, "early finalizer marker")
    text = text.replace("    root_status=$?\n", "")
    if text.count("# CODEX_PRODUCTION_LAUNCH") != 1:
        raise RuntimeError("repaired production marker is not unique")
    runner.write_text(text, encoding="utf-8", newline="\n")

    contract_path = build.TREE / "contracts/server_runner_return_resilience_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["runner_sha256"] = build.digest(runner)
    build.write_json(contract_path, contract)

    manifest_path = build.TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = build.file_map(build.TREE)
    build.write_json(manifest_path, manifest)

    build.deterministic_zip(build.TREE, build.ZIP)
    recheck = build.exact_zip_recheck(build.TREE, build.ZIP)
    build.ZIP.with_name(build.ZIP.name + ".sha256").write_text(
        f"{build.digest(build.ZIP)}  {build.ZIP.name}\n",
        encoding="ascii",
        newline="\n",
    )
    receipt_path = build.BUILD / "build_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["zip"] = build.identity(build.ZIP)
    receipt["exact_final_zip_recheck"] = recheck
    receipt["aggregate_gate_repair"] = {
        "runtime_preflight_marker_moved_before_function_bodies": True,
        "late_traps_removed": True,
        "staging_rebuilt": False,
    }
    build.write_json(receipt_path, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
