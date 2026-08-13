#!/usr/bin/env python3
"""Repair the aggregate v62 heredoc and identity path-budget findings."""

from __future__ import annotations

import json

import build_qlinearadd_node0007_v62_nativeflow as build


def main() -> int:
    runner = build.TREE / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    broken = '},sort_keys=True)+"\n")\nPY\n'
    fixed = '},sort_keys=True)+"\\n")\nPY\n'
    if text.count(broken) != 2:
        raise RuntimeError(f"expected two broken generated heredocs, found {text.count(broken)}")
    runner.write_text(text.replace(broken, fixed), encoding="utf-8", newline="\n")

    runner_contract_path = build.TREE / "contracts/server_runner_return_resilience_contract.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = build.digest(runner)
    build.write_json(runner_contract_path, runner_contract)

    manifest_path = build.TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = manifest["path_length_budget"]
    longest = budget["longest_projected_relative_path"]
    budget["longest_projected_relative_path_chars"] = len(longest)
    budget["max_projected_absolute_path_chars"] = budget["declared_target_root_max_chars"] + 1 + len(longest)

    layout_path = build.TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout_budget = layout["path_budget"]
    layout_budget["max_projected_absolute_path_chars"] = layout_budget["declared_target_root_max_chars"] + 1 + len(longest)
    build.write_json(layout_path, layout)

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
    receipt["runtime_layout_aggregate_repair"] = {
        "generated_python_heredocs_fixed": 2,
        "path_budget_identity_delta_chars": -2,
        "staging_rebuilt": False,
    }
    build.write_json(receipt_path, receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
