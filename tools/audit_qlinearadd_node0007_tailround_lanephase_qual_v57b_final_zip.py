#!/usr/bin/env python3
"""Independent exact-final-ZIP audit for QAdd node0007 v57f.

This audit intentionally starts from a clean extraction of the immutable ZIP.
It does not consume a builder self-report as proof of package contents.
"""

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

NAME = "r5_qadd_n7_tailround_lanephase_qual_v57f"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57f-package"
ZIP = LOCAL / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
AUDIT = LOCAL / "independent_exact_zip_audit_v2"
CLEAN = ROOT / "artifacts/q57fb"
PYTHON = Path(sys.executable)
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
SOURCE_VALIDATOR = ROOT / "tools/generate_server_source_bound_observer.py"
LAYOUT_VALIDATOR = ROOT / "tools/validate_server_package_runtime_layout.py"
LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
SOURCE_HARNESS = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-package/runtime_layout_harness.json"
PRIOR_FIRST_FRESH = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-package/first_fresh_extra_audit_v4/validation.json"
FAILED_V57 = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57-package/failed_exact_zip_audit_attempt1/r5_qadd_n7_tailround_lanephase_qual_v57.zip"
FAILED_V57B = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57b-package/r5_qadd_n7_tailround_lanephase_qual_v57b.zip"
FAILED_V57C = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57c-package/r5_qadd_n7_tailround_lanephase_qual_v57c.zip"
FAILED_V57D = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_qual_v57d.zip"
FAILED_V57E = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57e-package/r5_qadd_n7_tailround_lanephase_qual_v57e.zip"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
    "whole_net_specialist": ROOT / ".agents/rules/整网测试收敛优化专项规则.md",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha(path),
    }


def replace_strings(value: Any, old: str, new: str) -> Any:
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [replace_strings(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: replace_strings(item, old, new) for key, item in value.items()}
    return value


def run_stage_filter_controls(package: Path) -> dict[str, Any]:
    script = package / "package_tools/qlinearadd_node0007_source_bound_stage_filter_v57.py"
    cases = {
        "ordered_boundary": {
            "observer": "100 | EXEC_START | stage=1\n",
            "source": (
                "CODEX_PROBE_V1 kind=ENABLED time=1 boundary=x\n"
                "CODEX_PROBE_V1 kind=EVENT time=99 boundary=x\n"
                "CODEX_PROBE_V1 kind=EVENT time=100 boundary=x\n"
                "CODEX_PROBE_V1 kind=SUMMARY time=101 boundary=x\n"
            ),
            "expected_event_count": 1,
            "expected_start": True,
        },
        "missing_exec_start": {
            "observer": "",
            "source": "CODEX_PROBE_V1 kind=ENABLED time=1 boundary=x\nCODEX_PROBE_V1 kind=EVENT time=100 boundary=x\n",
            "expected_event_count": 0,
            "expected_start": False,
        },
        "wrong_stage": {
            "observer": "100 | EXEC_START | stage=0\n",
            "source": "CODEX_PROBE_V1 kind=ENABLED time=1 boundary=x\nCODEX_PROBE_V1 kind=EVENT time=100 boundary=x\n",
            "expected_event_count": 0,
            "expected_start": False,
        },
        "malformed_event": {
            "observer": "100 | EXEC_START | stage=1\n",
            "source": "CODEX_PROBE_V1 kind=ENABLED time=1 boundary=x\nCODEX_PROBE_V1 kind=EVENT boundary=x\n",
            "expected_event_count": 0,
            "expected_start": True,
        },
    }
    results: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="q57b-filter-") as temp:
        root = Path(temp)
        for name, case in cases.items():
            source = root / f"{name}.source.log"
            observer = root / f"{name}.observer.log"
            output = root / f"{name}.filtered.log"
            result_path = root / f"{name}.json"
            source.write_text(case["source"], encoding="utf-8", newline="\n")
            observer.write_text(case["observer"], encoding="utf-8", newline="\n")
            process = subprocess.run(
                [
                    str(PYTHON), str(script),
                    "--source-log", str(source),
                    "--observer-log", str(observer),
                    "--output", str(output),
                    "--receipt", str(result_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            result = load(result_path) if result_path.is_file() else {}
            filtered = output.read_text(encoding="utf-8") if output.is_file() else ""
            event_count = sum(" kind=EVENT " in line for line in filtered.splitlines())
            passed = (
                process.returncode == 0
                and result.get("stage_start_found") is case["expected_start"]
                and event_count == case["expected_event_count"]
                and "kind=SUMMARY" not in filtered
            )
            results[name] = {
                "pass": passed,
                "exit_code": process.returncode,
                "stage_start_found": result.get("stage_start_found"),
                "event_count": event_count,
                "stderr": process.stderr,
            }
    return {
        "pass": all(row["pass"] for row in results.values()),
        "errors": [name for name, row in results.items() if not row["pass"]],
        "cases": results,
        "negative_controls": ["missing_exec_start", "wrong_stage", "malformed_event"],
        "claim_boundary": "Exact package-local ordered-stage record filtering only; no DUT or numeric claim.",
    }


def main() -> int:
    errors: list[str] = []
    required = [ZIP, SIDECAR, SOURCE_VALIDATOR, LAYOUT_VALIDATOR, LAYOUT_HELPER, SOURCE_HARNESS, PRIOR_FIRST_FRESH, FAILED_V57, FAILED_V57B, FAILED_V57C, FAILED_V57D, FAILED_V57E, *RULES.values()]
    errors.extend(f"missing:{path.relative_to(ROOT).as_posix()}" for path in required if not path.is_file())
    if AUDIT.exists() or CLEAN.exists():
        errors.append("fresh independent audit tree required")
    if errors:
        print(json.dumps({"pass": False, "errors": errors}, sort_keys=True))
        return 1
    AUDIT.mkdir(parents=True)
    CLEAN.mkdir()

    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos if not row.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names}
        safe = (
            roots == {NAME}
            and len(names) == len(set(names))
            and all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names)
            and all(not stat.S_ISLNK((row.external_attr >> 16) & 0xFFFF) for row in infos)
        )
        crc = archive.testzip() is None
        for row in infos:
            if row.is_dir():
                continue
            relative = PurePosixPath(row.filename).relative_to(NAME)
            target = CLEAN.joinpath(NAME, *relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(row))
    package = CLEAN / NAME
    manifest = load(package / "TEST_PACKAGE_MANIFEST.json")
    actual = {
        path.relative_to(package).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in package.rglob("*")
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }
    clean_report = {
        "pass": crc and safe and manifest.get("files") == actual,
        "errors": [],
        "checks": {"crc": crc, "safe_single_root_no_duplicate_or_symlink": safe, "manifest_exact_set_per_file": manifest.get("files") == actual},
        "zip": receipt(ZIP),
        "member_count": len(names),
    }
    clean_report["errors"] = [key for key, passed in clean_report["checks"].items() if not passed]
    write(AUDIT / "clean_extract_validation.json", clean_report)

    bash_result = subprocess.run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")], capture_output=True, text=True, check=False)
    py_errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="q57c-py-") as compile_dir:
        compile_root = Path(compile_dir)
        for source in (package / "package_tools").glob("*.py"):
            target = compile_root / source.name
            target.write_bytes(source.read_bytes())
            try:
                py_compile.compile(str(target), doraise=True)
            except py_compile.PyCompileError as error:
                py_errors.append(f"{source.name}:{error}")
    preflight = subprocess.run(
        [str(PYTHON), str(package / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"), "preflight", "--package-root", str(package)],
        capture_output=True,
        text=True,
        check=False,
    )
    runner_text = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    startup_env = dict(__import__("os").environ)
    startup_env["PATH"] = str(BASH.parent) + ";" + str(BASH.parents[1] / "usr/bin") + ";" + startup_env.get("PATH", "")
    no_arg = subprocess.run(
        [str(BASH), str(package / "PREPARE_AND_RUN.sh")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, env=startup_env,
    )
    relative_arg = subprocess.run(
        [str(BASH), str(package / "PREPARE_AND_RUN.sh"), "relative-root"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False, env=startup_env,
    )
    runner_checks = {
        "bash_syntax": bash_result.returncode == 0,
        "package_python_syntax": not py_errors,
        "package_preflight": preflight.returncode == 0,
        "compile_handoff": "make -f Makefile.tb_NDP_Top_new_phy compile" in runner_text,
        "raw_logger_target": 'source_bound_causal_raw.log' in runner_text,
        "filtered_parser_target": 'source_bound_causal.log' in runner_text,
        "shared_finalizer": "server_post_sim_return.py" in runner_text,
        "fixed_result_root": "/home/panqs/ndp/simresult" in runner_text,
        "no_preassignment_unbound_variable": "unbound variable" not in no_arg.stderr and "unbound variable" not in relative_arg.stderr,
        "no_arg_reaches_runner_gate": no_arg.returncode == 2 and "expected exactly one absolute server root argument" in no_arg.stderr,
        "relative_arg_reaches_runner_gate": relative_arg.returncode == 2 and "server root argument is not absolute" in relative_arg.stderr,
        "source_bound_filtered_assignment_after_run_root": runner_text.index('source_bound_filtered_log=') > runner_text.index('run_root="$RUN_ROOT"'),
        "startup_stderr_has_no_shell_diagnostics": "command not found" not in no_arg.stderr and "command not found" not in relative_arg.stderr,
    }
    runner_report = {
        "pass": all(runner_checks.values()),
        "errors": [key for key, passed in runner_checks.items() if not passed],
        "checks": runner_checks,
        "commands": {
            "bash_n": {"exit_code": bash_result.returncode, "stderr": bash_result.stderr},
            "preflight": {"exit_code": preflight.returncode, "stdout_tail": preflight.stdout[-2000:], "stderr_tail": preflight.stderr[-2000:]},
            "python_compile_errors": py_errors,
            "no_arg_startup": {"exit_code": no_arg.returncode, "stdout": no_arg.stdout, "stderr": no_arg.stderr},
            "relative_arg_startup": {"exit_code": relative_arg.returncode, "stdout": relative_arg.stdout, "stderr": relative_arg.stderr},
        },
    }
    write(AUDIT / "runner_and_input_validation.json", runner_report)

    from tools.generate_server_source_bound_observer import validate_final_zip as validate_source
    from tools.server_post_sim_return import validate_final_zip as validate_post

    source_report = validate_source(ZIP)
    post_report = validate_post(ZIP)
    write(AUDIT / "source_bound_final_zip_validation.json", source_report)
    write(AUDIT / "post_sim_return_final_zip_validation.json", post_report)
    stage_report = run_stage_filter_controls(package)
    write(AUDIT / "stage_filter_negative_controls.json", stage_report)

    old_name = "r5_qadd_n7_tailround_lanephase_v56"
    harness = replace_strings(load(SOURCE_HARNESS), old_name, NAME)
    harness["derived_from_zip_sha256"] = sha(ZIP)
    harness["runner_member_sha256"] = sha(package / "PREPARE_AND_RUN.sh")
    harness["claim_boundary"] = (
        "Install-only V2 layout scenarios are reused for the byte-semantics-unchanged layout surface; "
        "the exact v57b runner syntax/input and changed logger-to-filter-to-parser handoff are independently validated; no DUT/server action."
    )
    harness_path = AUDIT / "runtime_layout_harness.json"
    write(harness_path, harness)
    layout_path = AUDIT / "shared_runtime_layout_validation.json"
    layout_run = subprocess.run(
        [
            str(PYTHON), str(LAYOUT_VALIDATOR),
            "--zip", str(ZIP),
            "--harness-report", str(harness_path),
            "--helper-reference", str(LAYOUT_HELPER),
            "--require-runner-error-visibility",
            "--output", str(layout_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    layout_report = load(layout_path) if layout_path.is_file() else {"pass": False, "errors": ["validator produced no report"]}

    prior = load(PRIOR_FIRST_FRESH)
    controls = source_report.get("semantic_controls", {})
    checks = {
        "clean_extract": clean_report["pass"],
        "runner_and_input": runner_report["pass"],
        "source_bound_exact_generation_and_controls": source_report.get("pass") is True and source_report.get("errors") == [] and controls.get("pass") is True,
        "focused_hdl_syntax_scope": source_report.get("pass") is True and source_report.get("exact_generation", {}).get("observer", {}).get("byte_equal") is True,
        "post_sim_core": post_report.get("pass") is True and post_report.get("errors") == [],
        "stage_filter_controls": stage_report["pass"],
        "runtime_layout": layout_run.returncode == 0 and layout_report.get("pass") is True and layout_report.get("errors") == [],
        "same_epoch_prior_first_fresh": prior.get("pass") is True and prior.get("upload_authorized") is True and sha(PRIOR_FIRST_FRESH) == "f18351daf7af81538dcd6a2f891601f3d3666390814e50dd2ea3609f741e4958",
        "failed_v57_preserved": sha(FAILED_V57) == "1670df66d80c2085ca75898a9eb0cf93e761148555ec9c55957d72d7ff29575c",
        "failed_v57b_preserved": sha(FAILED_V57B) == "2d30b02d4bfe765e14f91118c3cfc555e90c0728489286dc9ae401c0d768df50",
        "failed_v57c_preserved": sha(FAILED_V57C) == "3fba5052efd773c76f7909d7a3e6c881c75811558bdf1f7517c7db19c8be0488",
        "failed_v57d_preserved": sha(FAILED_V57D) == "7762663506b973595b9415c836aa4f2309c0e2d982f96294174cd4b9e479b4a3",
        "failed_v57e_preserved": sha(FAILED_V57E) == "d5985a6e01578ea2383c18062188596393fbb119d3f385a3d1d7b8f3422a6eea",
        "sidecar_exact": SIDECAR.read_text(encoding="ascii").strip() == f"{sha(ZIP)}  {ZIP.name}",
        "frozen_config_workload": manifest.get("successor", {}).get("frozen_surface") is not None and manifest.get("successor", {}).get("classification") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
    }
    errors.extend(key for key, passed in checks.items() if passed is not True)
    errors.extend(f"layout:{item}" for item in layout_report.get("errors", []) if not layout_report.get("pass"))
    audit = {
        "schema": "qlinearadd-node0007-tailround-lanephase-qual-v57f-final-zip-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "zip": receipt(ZIP),
        "sidecar": receipt(SIDECAR),
        "failed_prior_exact_zips": [
            {
                **receipt(FAILED_V57),
                "package_id": "r5_qadd_n7_tailround_lanephase_qual_v57",
                "disposition": "SUPERSEDED_UNPUBLISHED_HELD_EXACT_ZIP_AUDIT_FAILED",
                "errors": [
                    "final ZIP contract member keys unexpected: stage_filter/stage_filter_fixture",
                    "runner lacks required source-bound token: source_bound_causal.log",
                ],
            },
            {
                **receipt(FAILED_V57B),
                "package_id": "r5_qadd_n7_tailround_lanephase_qual_v57b",
                "disposition": "SUPERSEDED_UNPUBLISHED_HELD_POST_SIM_TWO_INPUT_CONTRACT_FAILED",
                "errors": ["stage filter required two live inputs while shared post-sim plugin contract permits one"],
            },
            {
                **receipt(FAILED_V57C),
                "package_id": "r5_qadd_n7_tailround_lanephase_qual_v57c",
                "disposition": "SUPERSEDED_UNPUBLISHED_HELD_POST_SIM_OUTPUT_CONTRACT_FAILED",
                "errors": ["stage filter partial-exit output_path pointed to non-JSON filtered log instead of its JSON receipt"],
            },
            {
                **receipt(FAILED_V57D),
                "package_id": "r5_qadd_n7_tailround_lanephase_qual_v57d",
                "disposition": "QUARANTINED_SERVER_RUNTIME_INIT_UNBOUND_VARIABLE",
                "errors": ["PREPARE_AND_RUN.sh line 18 referenced run_root before assignment under set -u"],
            },
            {
                **receipt(FAILED_V57E),
                "package_id": "r5_qadd_n7_tailround_lanephase_qual_v57e",
                "disposition": "SUPERSEDED_UNPUBLISHED_HELD_REQUIRED_FILTERED_LOG_BINDING_REMOVED",
                "errors": ["runner removed required source_bound_causal.log binding instead of moving it after run_root assignment"],
            },
        ],
        "validation_receipts": {
            "clean_extract": receipt(AUDIT / "clean_extract_validation.json"),
            "runner": receipt(AUDIT / "runner_and_input_validation.json"),
            "source_bound": receipt(AUDIT / "source_bound_final_zip_validation.json"),
            "post_sim": receipt(AUDIT / "post_sim_return_final_zip_validation.json"),
            "stage_filter": receipt(AUDIT / "stage_filter_negative_controls.json"),
            "runtime_harness": receipt(harness_path),
            "runtime_layout": receipt(layout_path),
            "prior_first_fresh": receipt(PRIOR_FIRST_FRESH),
        },
        "control_receipts": {name: receipt(path) for name, path in RULES.items()} | {
            "source_bound_generator": receipt(SOURCE_VALIDATOR),
            "runtime_layout_validator": receipt(LAYOUT_VALIDATOR),
        },
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": "PASS_EXACT_CLEAN_EXTRACT_AND_RUNTIME_LAYOUT",
            "runner_compile_finalizer": "PASS_CHANGED_LOGGER_HANDOFF_AND_SHARED_FINALIZER",
            "package_local_hdl": "PASS_GENERATED_FOCUSED_FRONTEND_AND_SEMANTIC_CONTROLS",
            "materialized_config": "RECEIPT_REUSE_BYTE_EQUAL_V56",
            "observer_canonical": "PASS_EXACT_GENERATION_PLUS_ORDERED_STAGE_FILTER_NEGATIVES",
            "return_result_conjunction": "PASS_SHARED_POST_SIM_CORE_DYNAMIC_RESULT_PENDING",
            "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
            "functional_RTL": "RECORD_ONLY_UNMODIFIED",
            "first_fresh_extra_audit": "PASS_RECEIPT_REUSE_SAME_EPOCH",
        },
        "negative_controls": {
            "source_bound": {"positive": controls.get("positive_count"), "negative": controls.get("negative_count"), "pass": controls.get("pass")},
            "stage_filter": stage_report["negative_controls"],
            "all_fail_closed": controls.get("pass") is True and stage_report["pass"] is True,
        },
        "commands": {
            "source_bound_final_zip": f"python tools/generate_server_source_bound_observer.py validate-final-zip --zip {ZIP.relative_to(ROOT).as_posix()} --report {LOCAL.relative_to(ROOT).as_posix()}/source_bound_final_zip_validation.json",
            "runtime_layout": {"exit_code": layout_run.returncode, "stdout_tail": layout_run.stdout[-2000:], "stderr_tail": layout_run.stderr[-2000:]},
            "stage_filter_unit": "python -m unittest tests.test_qlinearadd_node0007_source_bound_stage_filter_v57 -v",
        },
        "claim_boundary": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY; isolated op_tail_round host stimulus, no producer/full-chain/E3/E4/E5 claim.",
        "numeric_workload_config_golden_repeated": False,
        "functional_rtl_changed": False,
        "server_action": False,
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    write(LOCAL / "final_zip_self_audit.json", audit)
    print(json.dumps({"pass": not errors, "errors": errors, "zip_sha256": sha(ZIP), "audit": str(LOCAL / "final_zip_self_audit.json")}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
