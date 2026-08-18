#!/usr/bin/env python3
"""Validate exact v72 semantic-v7, finalizer and dependency-binding surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v72_wall8400_v7"
V70_PASS_SHA = "6d6e1bb1212c60e2aa0e211dac0661d1b91f01bed84a680b8988e1b6a423137b"
V7_ACTIVATION_SHA = "ad8b0391c48916adf0507b7e8f2d664d777c72b0c583bb5e9efcaf20c26412b0"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_path = ROOT / "tools/validate_qlinearadd_node0007_v71_wall8400.py"
    source = source_path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v71_wall8400"', f'PACKAGE = "{PACKAGE}"'),
        ('LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v71.py"', 'LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v72.py"'),
        ('{"tb_vcd_bounded_causal_cone_final_zip": 6, "first_fresh_extra_audit": 5, "runtime_layout": 5}', '{"tb_vcd_bounded_causal_cone_final_zip": 7, "first_fresh_extra_audit": 6, "runtime_layout": 5}'),
        ('manifest_gate_semantics_6_5_5', 'manifest_gate_semantics_7_6_5'),
        ('qadd-v71-wall8400-exact-validation-v1', 'qadd-v72-wall8400-semantic-v7-exact-validation-v1'),
        ('qadd_v71_runtime_evaluator', 'qadd_v72_runtime_evaluator'),
        ('qadd_v71_live_supervisor', 'qadd_v72_live_supervisor'),
        ('qadd_v71_budget_admission', 'qadd_v72_budget_admission'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v71 exact-validator anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v72_exact_base", "__file__": str(source_path)}
    exec(compile(source, str(source_path), "exec"), namespace)
    prior_argv = sys.argv
    try:
        sys.argv = [str(source_path), "--tree", str(args.tree), "--zip", str(args.zip), "--repeat-zip", str(args.repeat_zip), "--prior-zip", str(args.prior_zip), "--output", str(args.output)]
        base_exit = int(namespace["main"]())
    finally:
        sys.argv = prior_argv
    report = load(args.output)
    tree = args.tree.resolve()
    contract = load(tree / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    predecessor = contract["diagnostic_round"]["evolution"]["predecessor"]
    finalizer = (tree / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v72.py").read_text(encoding="utf-8")
    pass_receipt = tree / "provenance/v70_published_pass_release_receipt.json"
    activation = tree / "provenance/tbvcd_predecessor_semantic_v7_activation_receipt.json"
    supplemental = {
        "legacy_v70_semantic_v5_declared": predecessor.get("published_gate_semantic_version") == "5",
        "v70_published_pass_exact": predecessor.get("published_pass_receipt_sha256") == V70_PASS_SHA and sha(pass_receipt) == V70_PASS_SHA,
        "semantic_v7_activation_exact": sha(activation) == V7_ACTIVATION_SHA,
        "predecessor_immediate_round": contract["diagnostic_round"]["round_index"] == 5 and predecessor.get("round_index") == 4,
        "finalizer_runtime_admission_propagated": '"runtime_budget_admission": load(package / "diagnostics/runtime_budget_admission.json")' in finalizer,
        "finalizer_post_kill_fields_propagated": all(token in finalizer for token in ("post_kill_reap_deadline_origin", "last_kill_host_monotonic_ns", "post_kill_reap_deadline_host_monotonic_ns", "post_kill_reap_completed")),
        "repository_schema_runtime_present": (ROOT / "outputs/qlinearadd_node0007_v70_pmapfix_release/gate_runtime/python").is_dir(),
        "absent_v71_dependency_not_used": "outputs/qlinearadd_node0007_v71_wall8400_release/gate_runtime/python" not in finalizer,
    }
    report["checks"].update(supplemental)
    supplemental_errors = [name for name, passed in supplemental.items() if not passed]
    report["errors"] = sorted(set(report.get("errors", [])) | set(supplemental_errors))
    report["pass"] = base_exit == 0 and not report["errors"]
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": report["errors"]}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
