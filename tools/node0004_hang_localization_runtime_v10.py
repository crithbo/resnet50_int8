from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import node0004_hang_localization_runtime_v7 as base  # noqa: E402


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
CANONICAL_PREFIX = "| CANONICAL_DIAG_DECISION_V1 |"
REQUIRED_FIELDS = (
    "schema",
    "version",
    "decision",
    "reason",
    "boundary",
    "window_first",
    "window_last",
    "window_cycles",
    "qualified_progress",
    "qualified_delta",
    "req0",
    "req1",
    "req3",
    "rdata0",
    "rdata1",
    "rdata3",
    "d_req",
    "d_wdata",
    "content_digest",
)
INTEGER_FIELDS = (
    "version",
    "window_first",
    "window_last",
    "window_cycles",
    "qualified_progress",
    "qualified_delta",
    "req0",
    "req1",
    "req3",
    "rdata0",
    "rdata1",
    "rdata3",
    "d_req",
    "d_wdata",
)


package_records = base.package_records
preflight = base.preflight
sha256 = base.sha256
verify_install = base.verify_install
collect = base.collect
write_json = base.write_json


def parse_canonical_records(lines: list[str]) -> dict[str, Any]:
    candidates = [line for line in lines if CANONICAL_PREFIX in line]
    errors: list[str] = []
    parsed: list[dict[str, Any]] = []
    for index, line in enumerate(candidates):
        suffix = line.split(CANONICAL_PREFIX, 1)[1].strip()
        fields = dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", suffix))
        missing = [name for name in REQUIRED_FIELDS if name not in fields]
        if missing:
            errors.append(
                f"candidate[{index}] missing fields: {','.join(missing)}"
            )
            continue
        try:
            numeric = {name: int(fields[name]) for name in INTEGER_FIELDS}
        except ValueError:
            errors.append(f"candidate[{index}] has non-integer field")
            continue
        if fields["schema"] != "node0004_hang_diag" or numeric["version"] != 1:
            errors.append(f"candidate[{index}] schema/version differs")
        if numeric["window_first"] != 1:
            errors.append(f"candidate[{index}] window_first differs")
        if (
            numeric["window_last"] < numeric["window_first"]
            or numeric["window_cycles"] <= 0
        ):
            errors.append(f"candidate[{index}] window range invalid")
        qualified_sum = sum(
            numeric[name]
            for name in (
                "req0",
                "req1",
                "req3",
                "rdata0",
                "rdata1",
                "rdata3",
                "d_req",
                "d_wdata",
            )
        )
        if qualified_sum != numeric["qualified_progress"]:
            errors.append(f"candidate[{index}] qualified sum differs")
        expected_digest = (
            f"QIOV1_{numeric['qualified_progress']}_"
            f"{numeric['qualified_delta']}_{numeric['window_last']}"
        )
        if fields["content_digest"] != expected_digest:
            errors.append(f"candidate[{index}] content digest differs")
        expected_decision = {
            "STALL_WINDOW_EXCEEDED": (
                f"LONG_RUNNING_HANG_AT_{fields['boundary']}"
            ),
            "MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING": "STILL_PROGRESSING",
            "MAX_DIAGNOSTIC_CYCLE_BUDGET_INSUFFICIENT_PROGRESS": (
                "EVIDENCE_INSUFFICIENT"
            ),
        }.get(fields["reason"])
        if expected_decision is None or fields["decision"] != expected_decision:
            errors.append(f"candidate[{index}] decision/reason differs")
        parsed.append({"line": line, "fields": fields, "numeric": numeric})
    if len(candidates) > 1:
        errors.append(f"canonical candidate count is {len(candidates)}")
    valid = len(candidates) == 1 and len(parsed) == 1 and not errors
    return {
        "valid": valid,
        "candidate_count": len(candidates),
        "parsed_count": len(parsed),
        "errors": errors,
        "record": parsed[0] if valid else None,
    }


def analyze(
    package_root: Path, evidence_root: Path, run_root: Path
) -> dict[str, Any]:
    compile_status = base._status(evidence_root / "compile_exit_status.txt")
    run_status = base._status(evidence_root / "run_exit_status.txt")
    observer = run_root / "c0/return_observer.log"
    lines = (
        observer.read_text(encoding="utf-8", errors="replace").splitlines()
        if observer.is_file()
        else []
    )
    progress_lines = [line for line in lines if "| PROGRESS_WINDOW |" in line]
    finish_lines = [line for line in lines if "| COMP_FINISH |" in line]
    canonical = parse_canonical_records(lines)
    record = canonical["record"]
    if finish_lines:
        status = "C0_NATURAL_TERMINAL_OBSERVED_DIAGNOSTIC_ONLY"
    elif canonical["candidate_count"] and not canonical["valid"]:
        status = "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
    elif record:
        status = record["fields"]["decision"]
    elif progress_lines:
        status = "C0_EXTERNAL_INTERRUPT_WITH_PROGRESS_HISTORY"
    else:
        status = "C0_DIAGNOSTIC_EVIDENCE_INCOMPLETE"
    value = {
        "schema": "node0004-hang-localization-result-v10",
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "status": status,
        "compile_exit_status": compile_status,
        "run_exit_status": run_status,
        "compile_succeeded": compile_status == 0,
        "natural_terminal_observed": bool(finish_lines),
        "progress_window_count": len(progress_lines),
        "last_progress_window": progress_lines[-1] if progress_lines else None,
        "canonical_decision": record,
        "canonical_validation": {
            "valid": canonical["valid"],
            "candidate_count": canonical["candidate_count"],
            "parsed_count": canonical["parsed_count"],
            "errors": canonical["errors"],
        },
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
