from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import node0004_hang_localization_runtime_v7 as base  # noqa: E402


# The final-ZIP four-way validator intentionally inspects the declared runtime
# source itself. Keep the delegated collector's exact allowlist visible here,
# even though collection remains implemented by the byte-preserved v7 helper.
RETURN_ALLOWLIST_BINDING = (
    "evidence/compile_exit_status.txt",
    "evidence/run_exit_status.txt",
    "evidence/signal_status.txt",
    "evidence/SERVER_RESULT_GATE.json",
    "runs/compile/sim_results/compile_driver.log",
    "runs/compile/sim_results/compile.log",
    "runs/c0/simulator_argv.txt",
    "runs/c0/sim.log",
    "runs/c0/return_observer.log",
    "runs/c0/host_progress.log",
)


package_records = base.package_records
preflight = base.preflight
sha256 = base.sha256
verify_install = base.verify_install
collect = base.collect
write_json = base.write_json


def analyze(
    package_root: Path, evidence_root: Path, run_root: Path
) -> dict[str, Any]:
    compile_status = base._status(evidence_root / "compile_exit_status.txt")
    run_status = base._status(evidence_root / "run_exit_status.txt")
    observer = run_root / "c0/return_observer.log"
    reason_lines: list[str] = []
    summary_lines: list[str] = []
    progress_lines: list[str] = []
    finish_lines: list[str] = []
    if observer.is_file():
        for line in observer.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            if "| DIAG_DECISION |" in line:
                summary_lines.append(line)
                if "reason=" in line and "boundary=" in line:
                    reason_lines.append(line)
            if "| PROGRESS_WINDOW |" in line:
                progress_lines.append(line)
            if "| COMP_FINISH |" in line:
                finish_lines.append(line)
    decision = reason_lines[-1] if reason_lines else None
    if finish_lines:
        status = "C0_NATURAL_TERMINAL_OBSERVED_DIAGNOSTIC_ONLY"
    elif decision and "MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING" in decision:
        status = "C0_STILL_PROGRESSING_NOT_FINISHED_AT_BUDGET"
    elif decision and "STALL_WINDOW_EXCEEDED" in decision:
        status = "C0_HANG_BOUNDARY_LOCALIZED"
    elif decision:
        status = "C0_DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    elif progress_lines:
        status = "C0_EXTERNAL_INTERRUPT_WITH_PROGRESS_HISTORY"
    else:
        status = "C0_DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    value = {
        "schema": "node0004-hang-localization-result-v9",
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "status": status,
        "compile_exit_status": compile_status,
        "run_exit_status": run_status,
        "compile_succeeded": compile_status == 0,
        "natural_terminal_observed": bool(finish_lines),
        "progress_window_count": len(progress_lines),
        "last_progress_window": progress_lines[-1] if progress_lines else None,
        "diagnostic_decision": decision,
        "diagnostic_summary_line_count": len(summary_lines),
        "reason_bearing_decision_line_count": len(reason_lines),
        "formal_readback_claimed": False,
        "e4_claimed": False,
        "e5_claimed": False,
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", value)
    return value


def main() -> int:
    base.analyze = analyze
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
