from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.audit_node0004_v79_final_zip as base


PACKAGE = "r5_n4_hw_v80_ack_phase_diag"


def main() -> int:
    ap = argparse.ArgumentParser()
    for name in (
        "zip", "build-report", "source-bound-report", "post-sim-report", "temporal-report",
        "input-owner-report", "ack-equation-report", "phase-report", "phase-hdl-report", "runner-report",
        "return-contract-report", "shared-layout-report", "prior-first-fresh-report", "output",
    ):
        ap.add_argument("--" + name, required=True, type=Path)
    args = ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="n4v80_audit_") as raw:
        intermediate = Path(raw) / "base.json"
        old = sys.argv
        base.PACKAGE = PACKAGE
        base.base.PACKAGE = PACKAGE
        try:
            sys.argv = [
                "audit-v80", "--zip", str(args.zip), "--build-report", str(args.build_report),
                "--source-bound-report", str(args.source_bound_report), "--post-sim-report", str(args.post_sim_report),
                "--temporal-report", str(args.temporal_report), "--input-owner-report", str(args.input_owner_report),
                "--ack-equation-report", str(args.ack_equation_report), "--runner-report", str(args.runner_report),
                "--return-contract-report", str(args.return_contract_report), "--shared-layout-report", str(args.shared_layout_report),
                "--prior-first-fresh-report", str(args.prior_first_fresh_report), "--output", str(intermediate),
            ]
            base_rc = base.main()
        finally:
            sys.argv = old
        report = json.loads(intermediate.read_text(encoding="utf-8"))
    phase = json.loads(args.phase_report.read_text(encoding="utf-8"))
    phase_hdl = json.loads(args.phase_hdl_report.read_text(encoding="utf-8"))
    with zipfile.ZipFile(args.zip) as archive:
        names = set(archive.namelist())
        prefix = PACKAGE + "/"
        members = all(
            prefix + item in names
            for item in (
                "tb_probe/buffer_ack_phase_observer.svh",
                "package_tools/buffer_ack_phase_parser.py",
                "package_tools/node0004_v80_post_sim_plugin.py",
                "contracts/server_post_sim_return_request.json",
            )
        )
        runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode()
        compile_handoff = runner.count("$package_root/tb_probe/buffer_ack_phase_observer.svh") == 1
        runtime_limit = runner.count("+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128") == 2
    report["schema"] = "conv-node0004-v80-final-zip-audit-v1"
    report["checks"]["v80_phase_products_bound"] = members
    report["checks"]["v80_phase_compile_handoff"] = compile_handoff
    report["checks"]["v80_phase_runtime_binding"] = runtime_limit
    report["checks"]["v80_phase_predicate_trace_and_negatives"] = phase.get("pass") is True
    report["checks"]["v80_phase_focused_hdl_and_scope"] = phase_hdl.get("pass") is True
    changed = report["release_gate_matrix"]["changed_observer_collector_parser"]
    changed["pass"] = changed["pass"] and members and compile_handoff and runtime_limit and phase.get("pass") is True
    report["release_gate_matrix"]["actual_package_local_HDL"] = {"applicability": "blocking_applicable", "pass": members and compile_handoff and phase.get("pass") is True and phase_hdl.get("pass") is True}
    report["report_receipts"]["phase"] = {"path": str(args.phase_report), "bytes": args.phase_report.stat().st_size, "sha256": base.base.sha(args.phase_report)}
    report["report_receipts"]["phase_hdl"] = {"path": str(args.phase_hdl_report), "bytes": args.phase_hdl_report.stat().st_size, "sha256": base.base.sha(args.phase_hdl_report)}
    errors = [key for key, value in report["checks"].items() if not value]
    report["errors"] = errors
    report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] = not errors
    report["claim_boundary"] = "Exact final v80 source-bound products plus package-local Buffer_AG active/delta/stable phase observer, parser traces and unchanged shared gates; no server run, numeric, configuration correction, RTL defect, natural terminal, formal D, E4 or E5 claim."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors, "base_rc": base_rc}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
