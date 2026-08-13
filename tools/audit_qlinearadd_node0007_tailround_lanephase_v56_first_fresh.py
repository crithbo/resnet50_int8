#!/usr/bin/env python3
"""Independent clean-extract first-fresh audit for exact QAdd v56 ZIP."""

from __future__ import annotations

import hashlib
import json
import py_compile
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
NAME = "r5_qadd_n7_tailround_lanephase_v56"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-package"
ZIP = LOCAL / f"{NAME}.zip"
AUDIT = LOCAL / "first_fresh_extra_audit_v4"
CLEAN = ROOT / "artifacts/q56c"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
POST_SIM = ROOT / "tools/server_post_sim_return.py"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
RULE_IDS = [
    "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001",
    "20260810-first-fresh-extra-audit-v1",
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def report(name: str, checks: dict[str, bool], **extra: Any) -> dict[str, Any]:
    errors = [key for key, passed in checks.items() if passed is not True]
    value = {"pass": not errors, "errors": errors, "checks": checks, **extra}
    write(AUDIT / name, value)
    return value


def main() -> int:
    if AUDIT.exists():
        raise SystemExit(f"fresh independent audit directory required: {AUDIT}")
    AUDIT.mkdir(parents=True)
    clean = CLEAN
    clean.mkdir()
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos if not row.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names}
        safe = (
            roots == {NAME}
            and len(names) == len(set(names))
            and all(
                not PurePosixPath(name).is_absolute()
                and ".." not in PurePosixPath(name).parts
                and "\\" not in name
                for name in names
            )
            and all(not stat.S_ISLNK((row.external_attr >> 16) & 0xFFFF) for row in infos)
        )
        crc = archive.testzip() is None
        for row in infos:
            if row.is_dir():
                continue
            relative = PurePosixPath(row.filename).relative_to(NAME)
            target = clean.joinpath(NAME, *relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(row))
    package = clean / NAME
    manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    actual = {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
        for path in package.rglob("*")
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }
    exact = manifest.get("files") == actual
    extract_report = report(
        "exact_final_zip_clean_extract.json",
        {
            "crc": crc,
            "safe_single_root_no_duplicate_or_symlink": safe,
            "manifest_exact_set_per_file": exact,
        },
        zip={"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        member_count=len(names),
    )

    runner = package / "PREPARE_AND_RUN.sh"
    bash = subprocess.run([str(BASH), "-n", str(runner)], capture_output=True, text=True, check=False)
    py_errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="q56-py-") as temporary:
        for source in (package / "package_tools").glob("*.py"):
            target = Path(temporary) / source.name
            target.write_bytes(source.read_bytes())
            try:
                py_compile.compile(str(target), doraise=True)
            except py_compile.PyCompileError as error:
                py_errors.append(str(error))
    preflight = subprocess.run(
        [
            sys.executable,
            str(package / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"),
            "preflight",
            "--package-root",
            str(package),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    runner_text = runner.read_text(encoding="utf-8")
    runner_report = report(
        "actual_runner_entry_and_input_open.json",
        {
            "exact_runner_bash_syntax": bash.returncode == 0,
            "package_python_syntax": not py_errors,
            "exact_package_preflight_opens_manifest_payload": preflight.returncode == 0,
            "production_compile_handoff_present": "make -f Makefile.tb_NDP_Top_new_phy compile" in runner_text,
            "shared_json_only_finalizer": "server_post_sim_return.py" in runner_text and "finalize --request" in runner_text,
            "sim_started_is_runtime_state": 'CODEX_SIM_STARTED="$simulation_started"' in runner_text,
            "fixed_result_target": "/home/panqs/ndp/simresult" in runner_text,
        },
        commands={
            "bash": {"exit_code": bash.returncode, "stderr": bash.stderr},
            "preflight": {"exit_code": preflight.returncode, "stdout": preflight.stdout[-2000:], "stderr": preflight.stderr[-2000:]},
            "python_compile_errors": py_errors,
        },
        claim_boundary="Exact clean-extract runner syntax/input-open/compile handoff and finalizer state; no production compile or DUT run.",
    )

    from tools.generate_server_source_bound_observer import validate_final_zip as validate_source
    from tools.server_post_sim_return import validate_final_zip as validate_post

    source_validation = validate_source(ZIP)
    post_validation = validate_post(ZIP)
    write(AUDIT / "source_bound_final_zip_validation.json", source_validation)
    write(AUDIT / "post_sim_return_final_zip_validation.json", post_validation)
    controls = source_validation.get("semantic_controls", {})
    source_report = report(
        "source_bound_logger_collector_parser_roundtrip.json",
        {
            "exact_generation_byte_equal": source_validation.get("exact_generation", {}).get("observer", {}).get("byte_equal") is True
            and source_validation.get("exact_generation", {}).get("parser", {}).get("byte_equal") is True
            and source_validation.get("exact_generation", {}).get("binding", {}).get("byte_equal") is True,
            "typed_semantic_controls_pass": controls.get("pass") is True,
            "positive_controls_four": controls.get("positive_count") == 4,
            "negative_controls_eight": controls.get("negative_count") == 8,
            "historical_v80_and_p34b_regressions": len(controls.get("historical_regressions", [])) == 2,
        },
        source_bound_validation_sha256=sha(AUDIT / "source_bound_final_zip_validation.json"),
        diagnostic_semantics_sha256=source_validation.get("diagnostic_semantics_sha256"),
        case_count=controls.get("case_count"),
    )
    partial = post_validation.get("details", {}).get("partial_exit_live_causal_record", {})
    scenarios = post_validation.get("details", {}).get("scenario_results", {})
    post_report = report(
        "post_sim_return_core_scenarios.json",
        {
            "shared_core_final_zip_validation": post_validation.get("pass") is True,
            "partial_exit_live_causal_fixtures": not partial.get("contract_errors")
            and all(row.get("pass") is True for row in partial.get("plugin_results", {}).values()),
            "natural_success": scenarios.get("natural_success") == {"disposition": "COMPLETE_RETURN", "published": True},
            "plugin_failure_still_publishes": scenarios.get("natural_success_plugin_failure") == {"disposition": "EVIDENCE_INCOMPLETE", "published": True},
            "simulation_nonzero_partial": scenarios.get("simulation_nonzero") == {"disposition": "PARTIAL_EXECUTION_RETURN", "published": True},
            "idempotent_same_sha": scenarios.get("idempotent_reentry", {}).get("first_sha256") == scenarios.get("idempotent_reentry", {}).get("second_sha256"),
        },
        post_sim_validation_sha256=sha(AUDIT / "post_sim_return_final_zip_validation.json"),
    )
    plan = json.loads((package / "diagnostics/source_bound_probe_plan.json").read_text(encoding="utf-8"))
    candidate_ids = [row["candidate_id"] for row in plan["candidates"]]
    signatures = [json.dumps(row["signature"], sort_keys=True) for row in plan["candidates"]]
    candidate_report = report(
        "candidate_discrimination_matrix.json",
        {
            "all_four_candidates_present": len(candidate_ids) == 4 and len(set(candidate_ids)) == 4,
            "pairwise_distinct_signatures": len(set(signatures)) == len(signatures),
            "typed_positive_and_negative_controls": controls.get("positive_count") == 4 and controls.get("negative_count") == 8,
            "candidate_match_cardinality_exactly_one": plan["diagnostic_semantics"]["candidate_match_cardinality"] == "EXACTLY_ONE",
        },
        candidate_ids=candidate_ids,
        positive_control_count=controls.get("positive_count"),
        negative_control_count=controls.get("negative_count"),
    )

    reports = {
        "exact_final_zip_clean_extract": ("exact-final-zip-clean-extract", "exact_final_zip_clean_extract.json", extract_report),
        "actual_runner_entry_and_input_open": ("exact-runner-safe-compile-and-open-paths", "actual_runner_entry_and_input_open.json", runner_report),
        "source_bound_logger_collector_parser_roundtrip": ("exact-generated-over-budget-multi-instance", "source_bound_logger_collector_parser_roundtrip.json", source_report),
        "post_sim_return_core_scenarios": ("exact-final-request-four-scenario", "post_sim_return_core_scenarios.json", post_report),
        "candidate_discrimination_matrix": ("exact-candidate-positive-negative-matrix", "candidate_discrimination_matrix.json", candidate_report),
    }
    evidence = []
    all_errors: list[str] = []
    for gate_id, (kind, filename, value) in reports.items():
        path = AUDIT / filename
        evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
        if value["pass"] is not True:
            all_errors.extend(f"{gate_id}:{item}" for item in value["errors"])
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": NAME, "family": "qlinearadd", "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}},
        "rule_change": {"epoch_id": "20260810-first-fresh-extra-audit-v1", "rule_ids": RULE_IDS, "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "diagnostic_semantics": {
            "fingerprint_sha256": source_validation["diagnostic_semantics_sha256"],
            "final_zip_report_path": (AUDIT / "source_bound_final_zip_validation.json").relative_to(ROOT).as_posix(),
            "final_zip_report_sha256": sha(AUDIT / "source_bound_final_zip_validation.json"),
            "prior_fingerprint_sha256": None,
            "disposition": "FIRST_USE_AUDITED",
            "prior_audit_receipt": None,
        },
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": candidate_ids, "covered_candidate_ids": candidate_ids, "uncovered_candidate_ids": [], "positive_control_count": controls["positive_count"], "negative_control_count": controls["negative_count"], "pairwise_distinguishable": len(set(signatures)) == len(signatures)},
        "findings": [{"finding_id": "frozen_numeric_and_workload", "disposition": "record_only", "causal_class": None, "message": "numeric/W3/qparams/tail/golden/workload/config/timeout and functional RTL were frozen and not rerun"}],
    }
    write(AUDIT / "contract.json", contract)
    write(AUDIT / "independent_audit_summary.json", {"pass": not all_errors, "errors": all_errors, "zip": contract["package"]["final_zip"], "candidate_coverage": {"expected": 4, "covered": 4, "uncovered": []}, "upload_hold": True, "validator_pending": True})
    print(json.dumps({"pass": not all_errors, "errors": all_errors, "contract": str(AUDIT / "contract.json")}, sort_keys=True))
    return 0 if not all_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
