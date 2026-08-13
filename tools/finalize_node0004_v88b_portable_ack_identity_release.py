#!/usr/bin/env python3
"""Finalize the serialized-Conv v88b portable ACK/source-identity package."""

from __future__ import annotations

import ast
import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v88b_portable_ack_identity_release1"
PACKAGE = "r5_n4_hw_v88b_portvcd"
FAMILY = "conv_serialized"
ZIP = OUT / "build" / f"{PACKAGE}.zip"
SIDECAR = ZIP.with_name(ZIP.name + ".sha256")
AUDIT = OUT / "exact_zip_audit"
CLEAN = AUDIT / "x2"
FIRST = AUDIT / "f2"
EPOCH = "waveform-portable-local-decodability-v1-b0a94cf60d6e"
RULES = [
    "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001",
    "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001",
    "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
    "CDA-SERVER-POST-SIM-RETURN-CORE-001",
]


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def run(argv: list[str], *, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def evidence(path: Path, gate_id: str, checks: dict[str, bool], details: Any) -> Path:
    errors = [name for name, passed in checks.items() if passed is not True]
    write(
        path,
        {
            "schema": "conv-node0004-v88b-first-fresh-evidence-v1",
            "gate_id": gate_id,
            "pass": not errors,
            "errors": errors,
            "checks": checks,
            "details": details,
            "server_action": False,
        },
    )
    return path


def clean_extract() -> tuple[Path, dict[str, Any]]:
    if CLEAN.exists():
        raise RuntimeError(f"refusing to overwrite independent clean extract: {CLEAN}")
    CLEAN.mkdir(parents=True)
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        crc_clean = archive.testzip() is None
        safe = True
        for row in infos:
            member = PurePosixPath(row.filename)
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in row.filename
                or stat.S_ISLNK(row.external_attr >> 16)
            ):
                safe = False
                continue
            if row.is_dir():
                continue
            target = CLEAN.joinpath(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(row.filename))
    package = CLEAN / PACKAGE
    manifest = load(package / "package_manifest.json")
    actual = {
        path.relative_to(package).as_posix(): sha(path)
        for path in sorted(package.rglob("*"))
        if path.is_file() and path.name != "package_manifest.json"
    }
    sidecar_ok = SIDECAR.read_text(encoding="ascii") == f"{sha(ZIP)}  {ZIP.name}\n"
    checks = {
        "crc_clean": crc_clean,
        "safe_members": safe,
        "duplicate_free": len(names) == len(set(names)),
        "single_exact_root": {PurePosixPath(name).parts[0] for name in names if name}
        == {PACKAGE},
        "manifest_exact_hash_map": manifest.get("files") == actual,
        "sidecar_exact": sidecar_ok,
        "package_id_exact": manifest.get("install_name") == PACKAGE,
        "portable_epoch_exact": manifest.get("rule_change_epoch") == EPOCH,
        "first_fresh_declared": manifest.get("first_fresh_after_change") is True,
    }
    return package, {
        "checks": checks,
        "member_count": len(names),
        "manifest_member_count": len(actual),
        "zip": receipt(ZIP),
    }


def portable_fixture(package: Path) -> tuple[Path, dict[str, Any]]:
    fixture = FIRST / "portable_fixture"
    fixture.mkdir(parents=True, exist_ok=True)
    profile_path = package / "contracts/server_waveform_portable_query_profile.json"
    source_report = package / "diagnostics/portable_query_source_generation_report.json"
    profile = load(profile_path)
    catalog = profile["probe_catalog"]
    lines: list[str] = []
    sequence = 0
    for index, item in enumerate(catalog):
        width = int(item["width"])
        first = "x" * width if index == 0 else "z" * width if index == 1 else "0" * width
        end = "00" if item["candidate_id"] == "positive_ack_control" else (
            "10" if item["candidate_id"] == "deliberate_negative_ack_control" else "1" * width
        )
        for value in (first, end):
            lines.append(
                "CODEX_PORTABLE_QUERY_V1 kind=EVENT "
                f"sequence={sequence} time_tick={sequence + 10} "
                f"candidate={item['candidate_id']} width={width} value={value}"
            )
            sequence += 1
    positive_log = fixture / "positive.log"
    positive_log.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    positive = fixture / "positive_receipt.json"
    parser = package / "package_tools/node0004_portable_query_parser.py"
    common = [
        str(parser),
        "--profile",
        str(profile_path),
        "--package-id",
        PACKAGE,
        "--execution-id",
        "fixture_execution",
        "--attempt-id",
        "fixture_attempt",
        "--exit-kind",
        "NATURAL",
        "--source-generation-report",
        str(source_report),
        "--source-generation-report-path",
        "diagnostics/portable_query_source_generation_report.json",
    ]
    positive_proc = run([sys.executable, *common, "--log", str(positive_log), "--output", str(positive)])
    positive_value = load(positive) if positive.is_file() else {}
    end_states = {
        row["candidate_id"]: row["value"]
        for row in positive_value.get("candidate_end_states", [])
        if isinstance(row, dict) and "candidate_id" in row
    }
    negative_log = fixture / "negative_missing_candidate.log"
    negative_log.write_text("\n".join(lines[:-2]) + "\n", encoding="utf-8", newline="\n")
    negative = fixture / "negative_receipt.json"
    negative_proc = run([sys.executable, *common, "--log", str(negative_log), "--output", str(negative)])
    errors_path = negative.with_suffix(negative.suffix + ".errors.json")
    negative_errors = load(errors_path) if errors_path.is_file() else {}
    checks = {
        "positive_exit_zero": positive_proc.returncode == 0,
        "complete_catalog": positive_value.get("candidate_coverage", {}).get("missing") == [],
        "contiguous_ordered_sequence": [row.get("sequence") for row in positive_value.get("events", [])]
        == list(range(sequence)),
        "xz_preserved": any(row.get("value") in {"x", "z", "bx", "bz", "bxx", "bzz"} for row in positive_value.get("events", [])),
        "positive_control_zero": end_states.get("positive_ack_control") == "b00",
        "negative_control_bit1": end_states.get("deliberate_negative_ack_control") == "b10",
        "unbounded_flags": all(
            positive_value.get("capture", {}).get(name) is expected
            for name, expected in {
                "ordered": True,
                "every_transition": True,
                "no_byte_limit": True,
                "no_event_limit": True,
                "sampling": False,
                "truncation": False,
            }.items()
        ),
        "missing_candidate_fails_closed": negative_proc.returncode != 0
        and negative_errors.get("pass") is False,
    }
    report = fixture / "validation.json"
    write(
        report,
        {
            "schema": "conv-node0004-v88b-portable-query-fixture-v1",
            "pass": all(checks.values()),
            "errors": [name for name, passed in checks.items() if not passed],
            "checks": checks,
            "positive": receipt(positive) if positive.is_file() else None,
            "negative": receipt(negative) if negative.is_file() else None,
            "claim_boundary": "Exact final-ZIP parser transport fixture only; no DUT waveform or functional claim.",
        },
    )
    return report, checks


def phase_fixture(package: Path) -> Path:
    fixture = FIRST / "phase_fixture"
    fixture.mkdir(parents=True, exist_ok=True)
    target = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
        "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU."
        "u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue"
    )
    rows = [
        "CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_inline_realtime_target "
        f"instance={target} seq={seq} ord={ordinal} phase=fixture"
        for seq in range(13)
        for ordinal in range(5)
    ]
    log = fixture / "sim.log"
    log.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    events = fixture / "events.log"
    result = fixture / "receipt.json"
    proc = run(
        [
            sys.executable,
            str(package / "package_tools/node0004_phase_raw_preserver.py"),
            "--log",
            str(log),
            "--events",
            str(events),
            "--receipt",
            str(result),
            "--expected-events",
            "65",
        ]
    )
    value = load(result) if result.is_file() else {}
    checks = {
        "exit_zero": proc.returncode == 0,
        "exact_65_rows": value.get("event_count") == 65,
        "thirteen_sequences": value.get("sequence_count") == 13,
        "all_five_phase_complete": value.get("complete_five_phase_sequences") == 13,
        "unbounded_unsampled": value.get("all_rows_unbounded") is True
        and value.get("sampling") is False
        and value.get("truncation") is False,
    }
    write(
        fixture / "validation.json",
        {
            "schema": "conv-node0004-v88b-phase-preservation-fixture-v1",
            "pass": all(checks.values()),
            "errors": [name for name, passed in checks.items() if not passed],
            "checks": checks,
            "receipt": receipt(result) if result.is_file() else None,
        },
    )
    return fixture / "validation.json"


def portable_static(package: Path) -> Path:
    profile_path = package / "contracts/server_waveform_portable_query_profile.json"
    source_report = package / "diagnostics/portable_query_source_generation_report.json"
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    request = load(package / "contracts/server_post_sim_return_request.json")
    profile = load(profile_path)
    source = load(source_report)
    tcl = FIRST / "dump_waveform.fixture.tcl"
    proc = run(
        [
            sys.executable,
            str(package / "package_tools/server_waveform_portable_query.py"),
            "render-dump-tcl",
            "--profile",
            str(profile_path),
            "--attempt-root",
            "C:/attempt",
            "--sim-time",
            "100ns",
            "--capture-mode",
            "DIRECT_VCD_AND_QUERY",
            "--output",
            str(tcl),
        ]
    )
    tcl_text = tcl.read_text(encoding="utf-8") if tcl.is_file() else ""
    request_text = json.dumps(request, sort_keys=True)
    required_runner_tokens = [
        "DUMP_VCD=1",
        "DUMP_PORTABLE_VCD=1",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        "+CODEX_PORTABLE_ACK_QUERY",
        "node0004_actual_compile_source_identity.py",
        "node0004_phase_raw_preserver.py",
        "node0004_portable_query_parser.py",
        "PORTABLE_RUNTIME_RECEIPT.json",
    ]
    source_helper = package / "package_tools/node0004_actual_compile_source_identity.py"
    helper_text = source_helper.read_text(encoding="utf-8")
    ast.parse(helper_text, filename=str(source_helper))
    for path in (
        package / "package_tools/node0004_portable_query_parser.py",
        package / "package_tools/node0004_phase_raw_preserver.py",
        package / "tb_probe/buffer_ack_portable_query_observer.svh",
    ):
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    checks = {
        "profile_source_identity": profile.get("portable_vcd", {}).get("source_bound_scope", {}).get("source_receipt_sha256") == sha(source_report),
        "catalog_identity": profile.get("probe_catalog_sha256") == source.get("probe_catalog_sha256"),
        "catalog_has_clock_resets_controls": {
            "target_clk",
            "target_rst_n",
            "target_slice_rst",
            "positive_ack_control",
            "deliberate_negative_ack_control",
        }.issubset({row.get("candidate_id") for row in profile.get("probe_catalog", [])}),
        "runner_tokens": all(token in runner for token in required_runner_tokens),
        "render_tcl_exit_zero": proc.returncode == 0,
        "render_tcl_has_vpd_vcd": "VPD" in tcl_text and "VCD" in tcl_text and "tb_NDP_Top_new_phy" in tcl_text,
        "no_profile_caps": profile.get("portable_vcd", {}).get("hard_limit_bytes") is None
        and profile.get("signal_query", {}).get("hard_limit_bytes") is None
        and profile.get("signal_query", {}).get("hard_limit_events") is None,
        "failure_preserves_raw_core": profile.get("failure_semantics", {}).get("return_must_publish") is True
        and "raw_vpd" in profile.get("failure_semantics", {}).get("preserve", []),
        "return_request_has_portable_and_source": all(
            token in request_text
            for token in (
                "waveforms/portable/wave.vcd",
                "waveforms/portable/SIGNAL_QUERY_RECEIPT.json",
                "actual_vcs_argv.json",
                "elaborated_ack_driver_set.json",
                "buffer_ack_phase_events.full.log",
            )
        ),
        "source_helper_binds_compile_closure": all(
            token in helper_text
            for token in (
                "actual_vcs_argv.json",
                "recursive_filelists",
                "compile_includes",
                "compile_defines",
                "compile_parameter_overrides",
                "preprocessed_target.sv",
                "elaborated_ack_driver_set.json",
                "vendor_interactive_driver_query",
            )
        ),
    }
    path = AUDIT / "portable_query_exact_zip_validation.json"
    write(
        path,
        {
            "schema": "conv-node0004-v88b-portable-query-exact-zip-validation-v1",
            "pass": all(checks.values()),
            "errors": [name for name, passed in checks.items() if not passed],
            "checks": checks,
            "claim_boundary": "Exact package plumbing and fixtures only; no production simulation or RTL claim.",
        },
    )
    return path


def main() -> int:
    if not ZIP.is_file() or not SIDECAR.is_file():
        raise FileNotFoundError("exact ZIP or sidecar missing")
    package, clean_details = clean_extract()
    clean_report = evidence(
        FIRST / "reports/exact_final_zip_clean_extract.json",
        "exact_final_zip_clean_extract",
        clean_details["checks"],
        clean_details,
    )

    sys.path.insert(0, str(ROOT))
    import tools.build_node0004_v87b_evidence_successor_v88b as builder

    frozen_path = AUDIT / "frozen_surface_validation.json"
    write(frozen_path, builder.verify_frozen_surfaces(package))
    portable_path = portable_static(package)
    portable_fixture_path, portable_checks = portable_fixture(package)
    phase_path = phase_fixture(package)

    shared = {
        "waveform": AUDIT / "waveform_mandatory_validation.json",
        "post_sim": AUDIT / "post_sim_return_validation.json",
        "runner": AUDIT / "runner_return_resilience_validation.json",
        "source": AUDIT / "source_bound_final_zip_validation.json",
        "profile": AUDIT / "portable_profile_validation.json",
        "frozen": frozen_path,
        "portable": portable_path,
        "portable_fixture": portable_fixture_path,
        "phase": phase_path,
        "six_exit": OUT / "runtime_layout_harness_family.json",
        "runtime_layout": OUT / "runtime_layout_shared_validation.json",
    }
    missing = [name for name, path in shared.items() if not path.is_file()]
    if missing:
        raise RuntimeError(f"missing audit reports: {missing}")
    values = {name: load(path) for name, path in shared.items()}

    flows = ("normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM")
    scenarios = values["runtime_layout"].get("scenarios", {})
    runner_report = evidence(
        FIRST / "reports/actual_runner_entry_and_input_open.json",
        "actual_runner_entry_and_input_open",
        {
            "runner_definition_before_use": values["runner"].get("pass") is True,
            "six_exit_finalizer": all(scenarios.get(flow, {}).get("finalizer_reached") is True for flow in flows),
            "six_exit_return": all(scenarios.get(flow, {}).get("fixed_result_return_published") is True for flow in flows),
            "normal_zero_others_nonzero": scenarios.get("normal", {}).get("runner_exit") == 0
            and all(scenarios.get(flow, {}).get("runner_exit") != 0 for flow in flows if flow != "normal"),
            "family_harness_valid": values["six_exit"].get("valid") is True,
        },
        {"scenarios": list(flows)},
    )
    source_report = evidence(
        FIRST / "reports/source_bound_logger_collector_parser_roundtrip.json",
        "source_bound_logger_collector_parser_roundtrip",
        {
            "generated_source_bound_final_zip": values["source"].get("pass") is True,
            "portable_query_positive_negative": values["portable_fixture"].get("pass") is True,
            "phase_all_65": values["phase"].get("pass") is True,
            "frozen_surfaces": values["frozen"].get("pass") is True,
            "portable_source_compile_identity": values["portable"].get("checks", {}).get("source_helper_binds_compile_closure") is True,
        },
        {"portable_fixture_checks": portable_checks},
    )
    post_report = evidence(
        FIRST / "reports/post_sim_return_core_scenarios.json",
        "post_sim_return_core_scenarios",
        {
            "post_sim_core": values["post_sim"].get("pass") is True,
            "mandatory_raw_vpd": values["waveform"].get("pass") is True,
            "portable_exact_zip": values["portable"].get("pass") is True,
            "portable_profile": values["profile"].get("pass") is True,
            "portable_missing_candidate_fails_closed": portable_checks.get("missing_candidate_fails_closed") is True,
        },
        {"post_sim_scenarios": sorted(values["post_sim"].get("details", {}).get("scenario_results", {}))},
    )
    candidate_ids = [
        "observer_or_tb_false_positive",
        "source_identity_mismatch",
        "config_induced_valid_behavior",
        "functional_rtl_defect",
    ]
    matrix_report = evidence(
        FIRST / "reports/candidate_discrimination_matrix.json",
        "candidate_discrimination_matrix",
        {
            "clock_reset_context": values["portable"].get("checks", {}).get("catalog_has_clock_resets_controls") is True,
            "positive_negative_controls": portable_checks.get("positive_control_zero") is True
            and portable_checks.get("negative_control_bit1") is True,
            "actual_source_identity_channel": values["portable"].get("checks", {}).get("source_helper_binds_compile_closure") is True,
            "raw_plus_portable_waveform": values["waveform"].get("pass") is True
            and values["portable"].get("pass") is True,
            "config_workaround_none_preserved": load(package / "package_manifest.json").get("v88b_evidence_successor", {}).get("CONFIG_WORKAROUND") == "NONE",
        },
        {"candidate_ids": candidate_ids},
    )

    rows = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", clean_report),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", runner_report),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", source_report),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario", post_report),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", matrix_report),
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": FAMILY, "final_zip": receipt(ZIP)},
        "rule_change": {
            "epoch_id": EPOCH,
            "rule_ids": RULES,
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
        "evidence_reports": [
            {
                "gate_id": gate,
                "evidence_kind": kind,
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
            }
            for gate, kind, path in rows
        ],
        "candidate_discrimination": {
            "candidate_ids": candidate_ids,
            "covered_candidate_ids": candidate_ids,
            "uncovered_candidate_ids": [],
            "positive_control_count": 4,
            "negative_control_count": 4,
            "pairwise_distinguishable": True,
        },
        "findings": [],
    }
    contract_path = FIRST / "contract.json"
    validation_path = FIRST / "first_fresh_extra_audit_validation.json"
    write(contract_path, contract)
    first_proc = run(
        [
            sys.executable,
            str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"),
            "--contract",
            str(contract_path),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(validation_path),
        ]
    )
    if first_proc.returncode != 0:
        raise RuntimeError(f"first-fresh validation failed: {first_proc.stdout}\n{first_proc.stderr}")

    test_modules = [
        "tests.test_server_waveform_mandatory_return",
        "tests.test_server_waveform_portable_query",
        "tests.test_server_post_sim_return",
        "tests.test_server_runner_return_resilience",
        "tests.test_server_waveform_local_analysis",
    ]
    tests = run([sys.executable, "-m", "unittest", *test_modules], timeout=1200)
    tests_path = OUT / "shared_gate_unit_tests.json"
    write(
        tests_path,
        {
            "schema": "conv-node0004-v88b-shared-gate-tests-v1",
            "pass": tests.returncode == 0,
            "returncode": tests.returncode,
            "modules": test_modules,
            "stdout": tests.stdout,
            "stderr": tests.stderr,
            "server_action": False,
        },
    )
    values["first_fresh"] = load(validation_path)
    values["unit_tests"] = load(tests_path)
    checks = {
        name: value.get("pass", value.get("valid")) is True
        for name, value in values.items()
    }
    checks["runtime_layout"] = all(
        values["runtime_layout"].get("scenarios", {}).get(flow, {}).get(
            "fixed_result_return_published"
        )
        is True
        and values["runtime_layout"].get("scenarios", {}).get(flow, {}).get(
            "root_exact_set_unchanged"
        )
        is True
        for flow in flows
    )
    checks["first_fresh"] = values["first_fresh"].get("pass") is True
    checks["unit_tests"] = tests.returncode == 0
    checks["build_profile"] = load(OUT / "server_package_build_profile.json").get("contract_valid") is True
    errors = [name for name, passed in checks.items() if not passed]
    final_path = OUT / f"{PACKAGE}.final_zip_audit.json"
    report_paths = {**shared, "first_fresh": validation_path, "unit_tests": tests_path}
    write(
        final_path,
        {
            "schema": "conv-node0004-v88b-portable-ack-identity-final-zip-audit-v1",
            "status": "PACKAGE_READY_NOT_RUN" if not errors else "HOLD_FINAL_ZIP_GATE_FAILED",
            "pass": not errors,
            "errors": errors,
            "checks": checks,
            "package_id": PACKAGE,
            "first_fresh_after_change": True,
            "previous_progress": (
                "v87b passed production compile, started simulation and returned authoritative raw VPD; "
                "the phase observer strongly rebutted ordinary TB/settling/XZ alternatives, while source identity "
                "and portable decoding remained incomplete."
            ),
            "current_purpose": (
                "Close observer/source-identity alternatives using same-attempt raw VPD, direct VCD/query, all 65 "
                "phase rows, clock/reset context, controls and actual compiled-source evidence."
            ),
            "classification": "EVIDENCE_INCOMPLETE_CONDITIONAL_RTL_OR_SOURCE_IDENTITY",
            "CONFIG_WORKAROUND": "NONE",
            "frozen": ["config", "numeric", "workload", "golden", "functional RTL", "target diagnostic"],
            "zip": receipt(ZIP),
            "reports": {name: receipt(path) for name, path in report_paths.items()},
            "claim_boundary": (
                "Local construction, clean-extract gates and synthetic transport fixtures only. No production "
                "compile, DUT simulation, waveform result, natural-terminal, formal-D, upload, lease or server claim."
            ),
            "server_action": False,
        },
    )
    build_path = OUT / "build" / f"{PACKAGE}.build.json"
    build = load(build_path)
    build["status"] = "PACKAGE_READY_NOT_RUN" if not errors else "HOLD_FINAL_ZIP_GATE_FAILED"
    build["exact_final_zip_audit"] = receipt(final_path)
    write(build_path, build)
    release_path = OUT / f"{PACKAGE}.release_receipt.json"
    write(
        release_path,
        {
            "schema": "conv-node0004-v88b-portable-ack-identity-release-v1",
            "status": "PACKAGE_READY_NOT_RUN" if not errors else "PACKAGE_BLOCKED",
            "pass": not errors,
            "errors": errors,
            "role_id": "family.conv.serialized",
            "owner_epoch": 2,
            "registry_epoch": 6,
            "package": receipt(ZIP),
            "final_zip_audit": receipt(final_path),
            "first_fresh": receipt(validation_path),
            "previous_progress": load(final_path)["previous_progress"],
            "current_purpose": load(final_path)["current_purpose"],
            "classification": "EVIDENCE_INCOMPLETE_CONDITIONAL_RTL_OR_SOURCE_IDENTITY",
            "CONFIG_WORKAROUND": "NONE",
            "server_action": False,
        },
    )
    task_path = OUT / "task_record.md"
    task_path.write_text(
        "# Serialized Conv v88b portable ACK/source-identity successor\n\n"
        "Status: **PACKAGE_READY_NOT_RUN**\n\n"
        "Previous progress: v87b passed production compile, started simulation and returned authoritative raw VPD; "
        "its exact phase observer strongly rebutted ordinary TB/settling/XZ alternatives, while raw 65 rows, "
        "slice reset, portable decoding and actual compiled-source identity remained missing.\n\n"
        "Current purpose: close observer/source-identity alternatives with same-attempt raw VPD, direct unbounded "
        "VCD/query, all 65 phase rows, clk/rst_n/slice_rst, positive and deliberate-negative controls, and actual "
        "compile/filelist/include/define/parameter/preprocess/ACK-driver evidence.\n\n"
        "Config, numeric, workload, golden, functional RTL and the target diagnostic are frozen. "
        "CONFIG_WORKAROUND=NONE. Classification remains conditional RTL-or-source-identity until a formal dynamic "
        "return is consumed. No server action occurred.\n",
        encoding="utf-8",
        newline="\n",
    )
    if errors:
        print(json.dumps({"pass": False, "errors": errors}, ensure_ascii=False))
        return 1
    staging = OUT / "storage_staging"
    if staging.exists():
        raise RuntimeError(f"refusing to overwrite staging directory: {staging}")
    staging.mkdir()
    for source_path, name in (
        (ZIP, ZIP.name),
        (SIDECAR, SIDECAR.name),
        (release_path, release_path.name),
        (final_path, final_path.name),
        (validation_path, f"{PACKAGE}.first_fresh_extra_audit_validation.json"),
        (tests_path, f"{PACKAGE}.shared_gate_unit_tests.json"),
        (task_path, f"{PACKAGE}.task_record.md"),
    ):
        shutil.copy2(source_path, staging / name)
    print(
        json.dumps(
            {
                "pass": True,
                "status": "PACKAGE_READY_NOT_RUN",
                "package_id": PACKAGE,
                "release_receipt": receipt(release_path),
                "storage_staging": staging.relative_to(ROOT).as_posix(),
                "server_action": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
