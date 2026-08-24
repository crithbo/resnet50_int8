#!/usr/bin/env python3
"""Prepare typed gate results for the v112 patch-first release admission."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v112_tupleleaf_20260822"
GATES = OUT / "gates"
PACKAGE = "r5_n4_hw_v112b_tupleleaf_tbvcd"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def row(gate_id: str, name: str) -> dict[str, Any]:
    path = GATES / name
    report = load(path)
    return {
        "gate_id": gate_id,
        "pass": report.get("pass") is True,
        "errors": list(report.get("errors", [])),
        "warnings": list(report.get("warnings", [])),
        "detail_path": path.relative_to(ROOT).as_posix(),
    }


def main() -> int:
    results = [
        row("runner_control_flow", "runner_zip.json"),
        row("runner_return_resilience", "runner_zip.json"),
        row("runtime_preflight_noninterference_final_zip", "runtime_preflight.json"),
        row("package_local_hdl", "hdl_source_bound_zip.json"),
        row("package_local_hdl_lexical_final_zip", "hdl_lexical_zip.json"),
        row("post_sim_return_core", "post_sim_zip.json"),
        row("return_result_contract", "post_sim_zip.json"),
        row("source_bound_final_zip", "hdl_source_bound_zip.json"),
        row("tb_vcd_bounded_causal_cone_final_zip", "tb_vcd_tree.json"),
        row("first_fresh_extra_audit", "first_fresh_extra_audit.json"),
        row("final_zip_content", "final_zip_content.json"),
    ]
    value = {
        "schema": "server-package-gate-results-v1",
        "package_id": PACKAGE,
        "results": results,
        "claim_boundary": (
            "Local exact-final-ZIP gate aggregation only; no server, storage, "
            "compile, simulation or diagnostic-result claim."
        ),
    }
    target = OUT / "server_package_gate_results.json"
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"pass": all(row["pass"] for row in results), "gate_count": len(results)}, sort_keys=True))
    return 0 if all(row["pass"] for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
