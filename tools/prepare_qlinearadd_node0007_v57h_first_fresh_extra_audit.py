#!/usr/bin/env python3
"""Prepare the independent first-fresh exact-ZIP audit for QAdd v57h."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_qual_v57h"
FAMILY = "qlinearadd"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57h-package"
ZIP = LOCAL / f"{PACKAGE}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
AUDIT = LOCAL / "first_fresh_extra_audit_v2"
RUNNER_VALIDATION = LOCAL / f"{PACKAGE}.runner_resilience.json"
SOURCE_VALIDATION = LOCAL / f"{PACKAGE}.source_bound_final_zip.json"
POST_VALIDATION = LOCAL / f"{PACKAGE}.post_sim.json"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
RULE_IDS = [
    "CDA-SERVER-RUNNER-SET-U-DEFINITION-BEFORE-USE-001",
    "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
    "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
]
COMPILE_EVIDENCE = {
    "compile_argv.json",
    "compile_source_identity.json",
    "compile_exit.txt",
    "compile_driver.log",
    "compile_first_error.txt",
    "compile_log_head.txt",
    "compile_log_tail.txt",
    "compile_downstream_state.json",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def make_report(
    name: str, checks: dict[str, bool], details: dict[str, Any]
) -> Path:
    path = AUDIT / f"{name}.json"
    errors = [key for key, passed in checks.items() if passed is not True]
    write(
        path,
        {
            "schema": "qlinearadd-node0007-v57h-first-fresh-evidence-v1",
            "gate_id": name,
            "pass": not errors,
            "errors": errors,
            "checks": checks,
            "details": details,
            "server_action": False,
        },
    )
    return path


def run(argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=300,
    )


def main() -> int:
    required = [ZIP, SIDECAR, RUNNER_VALIDATION, SOURCE_VALIDATION, POST_VALIDATION, BASH]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing exact audit inputs: {missing}")
    if AUDIT.exists():
        raise RuntimeError(f"fresh audit directory required: {AUDIT}")
    AUDIT.mkdir(parents=True)

    runner_static = load(RUNNER_VALIDATION)
    source = load(SOURCE_VALIDATION)
    post = load(POST_VALIDATION)
    with tempfile.TemporaryDirectory(prefix="q57h-first-fresh-") as directory:
        clean_root = Path(directory)
        with zipfile.ZipFile(ZIP) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos if not info.is_dir()]
            crc = archive.testzip() is None
            safe = all(
                not PurePosixPath(info.filename).is_absolute()
                and ".." not in PurePosixPath(info.filename).parts
                and "\\" not in info.filename
                and not stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)
                for info in infos
            )
            single_root = {
                PurePosixPath(name).parts[0] for name in names if name
            } == {PACKAGE}
            duplicate_free = len(names) == len(set(names))
            archive.extractall(clean_root)
        package = clean_root / PACKAGE
        manifest = load(package / "TEST_PACKAGE_MANIFEST.json")
        actual = {
            path.relative_to(package).as_posix(): {
                "size_bytes": path.stat().st_size,
                "sha256": sha(path),
            }
            for path in sorted(item for item in package.rglob("*") if item.is_file())
            if path.name != "TEST_PACKAGE_MANIFEST.json"
        }
        sidecar_exact = (
            SIDECAR.read_text(encoding="ascii").strip()
            == f"{sha(ZIP)}  {ZIP.name}"
        )
        clean_report = make_report(
            "exact_final_zip_clean_extract",
            {
                "crc": crc,
                "safe": safe,
                "single_root": single_root,
                "duplicate_free": duplicate_free,
                "manifest_exact": manifest.get("files") == actual,
                "sidecar_exact": sidecar_exact,
                "epoch_ack": manifest.get("first_fresh_extra_audit", {}).get("epoch_id") == EPOCH,
                "first_fresh": manifest.get("first_fresh_extra_audit", {}).get("first_fresh_after_change") is True,
                "package_bound": manifest.get("first_fresh_extra_audit", {}).get("bound_package_id") == PACKAGE,
            },
            {
                "zip": {
                    "path": ZIP.relative_to(ROOT).as_posix(),
                    "bytes": ZIP.stat().st_size,
                    "sha256": sha(ZIP),
                },
                "member_count": len(names),
            },
        )

        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PATH"] = (
            str(BASH.parent)
            + ";"
            + str(BASH.parents[1] / "usr/bin")
            + ";"
            + env.get("PATH", "")
        )
        runner = package / "PREPARE_AND_RUN.sh"
        bash_syntax = run([str(BASH), "-n", str(runner)], env=env)
        no_arg = run([str(BASH), str(runner)], env=env)
        relative_arg = run([str(BASH), str(runner), "relative-root"], env=env)
        runtime = package / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
        preflight = run(
            [
                sys.executable,
                str(runtime),
                "preflight",
                "--package-root",
                str(package),
            ],
            env=env,
        )
        request = load(package / "contracts/server_post_sim_return_request.json")
        returned_compile_names = {
            Path(str(row.get("archive", ""))).name
            for row in request.get("core_entries", [])
            if isinstance(row, dict)
        }
        runner_text = runner.read_text(encoding="utf-8")
        fixture_tests = run(
            [
                sys.executable,
                "-m",
                "unittest",
                "tests.test_server_runner_return_resilience",
                "-v",
            ],
            env=env,
        )
        sca = load(package / "workload/runtime/sca_cfg.json")
        input_prefix = f"install/cfg_pkg/{PACKAGE}/"
        missing_inputs: list[str] = []
        input_count = 0
        for value in sca.values():
            if not isinstance(value, dict) or not isinstance(value.get("path"), str):
                continue
            input_count += 1
            declared = value["path"]
            if not declared.startswith(input_prefix):
                missing_inputs.append(declared)
                continue
            input_source = package / "workload/runtime" / declared[len(input_prefix) :]
            if not input_source.is_file():
                missing_inputs.append(declared)
        runner_report = make_report(
            "actual_runner_entry_and_input_open",
            {
                "exact_runner_static_contract": runner_static.get("pass") is True,
                "definition_before_use": runner_static.get("definition_before_use", {}).get("unsafe_uses") == [],
                "bootstrap_before_compile": runner_static.get("bootstrap", {}).get("assignment_line", 10**9) < runner_static.get("bootstrap", {}).get("first_fallible_line", -1),
                "bash_syntax": bash_syntax.returncode == 0,
                "no_arg_gate": no_arg.returncode == 2 and "expected exactly one absolute server root argument" in no_arg.stderr,
                "relative_arg_gate": relative_arg.returncode == 2 and "server root argument is not absolute" in relative_arg.stderr,
                "startup_no_unbound": "unbound variable" not in no_arg.stderr + relative_arg.stderr,
                "package_preflight": preflight.returncode == 0,
                "all_declared_inputs_open": input_count > 0 and not missing_inputs,
                "compile_evidence_returned": COMPILE_EVIDENCE <= returned_compile_names,
                "compile_evidence_bootstrap_rooted": all(
                    f'$bootstrap_root/{name}' in runner_text for name in COMPILE_EVIDENCE
                ),
                "shared_negative_fixtures": fixture_tests.returncode == 0,
            },
            {
                "runner_validation": {
                    "path": RUNNER_VALIDATION.relative_to(ROOT).as_posix(),
                    "sha256": sha(RUNNER_VALIDATION),
                },
                "input_count": input_count,
                "missing_inputs": missing_inputs,
                "compile_evidence": sorted(COMPILE_EVIDENCE),
                "fixture_test_exit": fixture_tests.returncode,
                "fixture_test_stdout": fixture_tests.stdout[-4000:],
                "fixture_test_stderr": fixture_tests.stderr[-4000:],
            },
        )

        controls = source.get("semantic_controls", {})
        source_report = make_report(
            "source_bound_logger_collector_parser_roundtrip",
            {
                "typed_exact_final_zip": source.get("schema") == "server-source-bound-final-zip-validation-v2",
                "exact_generation": source.get("pass") is True and source.get("errors") == [],
                "semantic_controls": controls.get("pass") is True,
                "positive_controls": controls.get("positive_count") == 4,
                "negative_controls": controls.get("negative_count", 0) >= 8,
            },
            {
                "source_validation": {
                    "path": SOURCE_VALIDATION.relative_to(ROOT).as_posix(),
                    "sha256": sha(SOURCE_VALIDATION),
                },
                "diagnostic_semantics_sha256": source.get("diagnostic_semantics_sha256"),
            },
        )

        scenarios = set(post.get("details", {}).get("scenario_results", {}))
        post_report = make_report(
            "post_sim_return_core_scenarios",
            {
                "exact_post_sim": post.get("pass") is True and post.get("errors") == [],
                "four_scenarios": scenarios
                == {
                    "natural_success",
                    "natural_success_plugin_failure",
                    "simulation_nonzero",
                    "idempotent_reentry",
                },
            },
            {
                "post_validation": {
                    "path": POST_VALIDATION.relative_to(ROOT).as_posix(),
                    "sha256": sha(POST_VALIDATION),
                },
                "scenarios": sorted(scenarios),
            },
        )

        plan = load(package / "diagnostics/source_bound_probe_plan.json")
        candidate_ids = [str(row["candidate_id"]) for row in plan["candidates"]]
        positive_cases = [
            row
            for row in controls.get("cases", [])
            if row.get("control_class") == "positive" and row.get("pass") is True
        ]
        negative_cases = [
            row
            for row in controls.get("cases", [])
            if row.get("control_class") == "negative" and row.get("pass") is True
        ]
        covered = sorted(
            {
                str(match)
                for row in positive_cases
                for match in row.get("matching_candidate_ids", [])
            }
        )
        candidate_report = make_report(
            "candidate_discrimination_matrix",
            {
                "all_candidates_covered": set(covered) == set(candidate_ids),
                "one_positive_per_candidate": len(positive_cases) == len(candidate_ids),
                "negative_controls": len(negative_cases) >= 8,
                "pairwise_distinguishable": len(
                    {
                        json.dumps(row.get("signature"), sort_keys=True)
                        for row in plan["candidates"]
                    }
                )
                == len(candidate_ids),
            },
            {
                "candidate_ids": candidate_ids,
                "covered_candidate_ids": covered,
                "positive_count": len(positive_cases),
                "negative_count": len(negative_cases),
            },
        )

    evidence_rows = [
        (
            "exact_final_zip_clean_extract",
            "exact-final-zip-clean-extract",
            clean_report,
        ),
        (
            "actual_runner_entry_and_input_open",
            "exact-runner-safe-compile-and-open-paths",
            runner_report,
        ),
        (
            "source_bound_logger_collector_parser_roundtrip",
            "exact-generated-over-budget-multi-instance",
            source_report,
        ),
        (
            "post_sim_return_core_scenarios",
            "exact-final-request-four-scenario",
            post_report,
        ),
        (
            "candidate_discrimination_matrix",
            "exact-candidate-positive-negative-matrix",
            candidate_report,
        ),
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": PACKAGE,
            "family": FAMILY,
            "final_zip": {
                "path": ZIP.relative_to(ROOT).as_posix(),
                "bytes": ZIP.stat().st_size,
                "sha256": sha(ZIP),
            },
        },
        "rule_change": {
            "epoch_id": EPOCH,
            "rule_ids": RULE_IDS,
            "first_fresh_for_family": True,
            "notification_acknowledged": True,
        },
        "independent_reaudit": {
            "clean_extract_from_final_zip": True,
            "from_final_zip_only": True,
            "family_build_reports_reused": False,
            "top_level_invocations": 1,
            "all_errors_collected": True,
            "rebuild_per_single_error_forbidden": True,
        },
        "diagnostic_semantics": {
            "fingerprint_sha256": source["diagnostic_semantics_sha256"],
            "final_zip_report_path": SOURCE_VALIDATION.relative_to(ROOT).as_posix(),
            "final_zip_report_sha256": sha(SOURCE_VALIDATION),
            "prior_fingerprint_sha256": source["diagnostic_semantics_sha256"],
            "disposition": "FIRST_USE_AUDITED",
            "prior_audit_receipt": None,
        },
        "evidence_reports": [
            {
                "gate_id": gate_id,
                "evidence_kind": kind,
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
            }
            for gate_id, kind, path in evidence_rows
        ],
        "candidate_discrimination": {
            "candidate_ids": candidate_ids,
            "covered_candidate_ids": candidate_ids,
            "uncovered_candidate_ids": [],
            "positive_control_count": len(positive_cases),
            "negative_control_count": len(negative_cases),
            "pairwise_distinguishable": True,
        },
        "findings": [
            {
                "finding_id": "v57f_missing_runner_resilience_contract",
                "disposition": "record_only",
                "causal_class": None,
                "message": "Immutable v57f failed the new gate and was not modified.",
            },
            {
                "finding_id": "v57g_source_bound_freeze_failure",
                "disposition": "record_only",
                "causal_class": None,
                "message": "Unpublished v57g changed generated diagnostic identity bytes and was superseded by fresh v57h.",
            },
        ],
    }
    contract_path = AUDIT / "contract.json"
    write(contract_path, contract)
    failed = [
        path.name for _gate, _kind, path in evidence_rows if load(path).get("pass") is not True
    ]
    preparation = {
        "schema": "qlinearadd-node0007-v57h-first-fresh-preparation-v1",
        "pass": not failed,
        "errors": failed,
        "package_id": PACKAGE,
        "zip_sha256": sha(ZIP),
        "contract_sha256": sha(contract_path),
        "server_action": False,
    }
    write(AUDIT / "preparation_report.json", preparation)
    print(json.dumps(preparation, ensure_ascii=False, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
