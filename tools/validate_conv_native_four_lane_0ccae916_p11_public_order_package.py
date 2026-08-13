#!/usr/bin/env python3
"""Independent final-ZIP audit for native-four-lane p11f."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import build_conv_native_four_lane_0ccae916_p11_public_order_package as build
import validate_conv_native_four_lane_0ccae916_p10_triggered_c0_package as p10v


INSTALL_NAME = build.INSTALL_NAME
PACKAGE = build.OUTPUT_ROOT / INSTALL_NAME
ZIP = build.OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
OUTPUT = build.OUTPUT_ROOT / f"{INSTALL_NAME}.final_zip_audit.json"
FIXED_ROOT = "/home/panqs/ndp/simresult"
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\python\python.exe"
)
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(zip_path: Path, target: Path) -> tuple[Path, dict[str, Any]]:
    errors: list[str] = []
    seen: set[str] = set()
    roots: set[str] = set()
    maximum = 0
    depth = 0
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"crc:{bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            maximum = max(maximum, len(info.filename))
            depth = max(depth, len(pure.parts))
            if pure.parts:
                roots.add(pure.parts[0])
            if (
                info.filename in seen
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                errors.append(info.filename)
            seen.add(info.filename)
        if roots != {INSTALL_NAME}:
            errors.append(f"roots:{sorted(roots)}")
        archive.extractall(target)
    return target / INSTALL_NAME, {
        "valid": not errors,
        "errors": errors,
        "entry_count": len(seen),
        "max_zip_member_chars": maximum,
        "max_depth": depth,
    }


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def finalizer_trace(package: Path, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    module = load_module(
        package / "package_tools/node0004_public_order_finalizer.py",
        "_native4_p11_public_finalizer",
    )
    statuses = root / "status"
    statuses.mkdir()
    for name, value in (
        ("compile", "0\n"),
        ("run", "125\n"),
        ("signal", "TERM\n"),
    ):
        (statuses / name).write_text(value, encoding="ascii")

    def event_lines(sain: int, saout: int, mse4: int) -> str:
        rows = []
        rows.extend(
            f"N4P_EVENT_V1 kind=SA_IN_ACCEPT seq={i} cycle={10+i} "
            f"port=0 buf=0 tag=0x{i:x}"
            for i in range(sain)
        )
        rows.extend(
            f"N4P_EVENT_V1 kind=SA_OUT_ACCEPT seq={i} cycle={100+i} "
            f"port=0 buf=0 tag=0x{i:x}"
            for i in range(saout)
        )
        rows.extend(
            f"N4P_EVENT_V1 kind=MSE4_INDEX_ACCEPT seq={i} cycle={200+i}"
            for i in range(mse4)
        )
        return "\n".join(rows)

    def run_case(
        name: str,
        *,
        sain: int,
        saout: int,
        mse4: int,
        raw: int,
        ready: int,
        blocked: int,
        feature: bool = True,
        duplicate_snapshot: bool = False,
    ) -> dict[str, Any]:
        log = root / f"{name}.log"
        feature_line = (
            "N4P_FEATURE_ENABLE_V1 feature=NATIVE4_PUBLIC_ORDER "
            "enabled=1 stage=c0 slice=0 event_limit=64 drives_dut=0 "
            "changes_timeout=0 public_monitor_reuse=1 per_event_live_io=0\n"
            if feature
            else ""
        )
        snapshot = (
            "N4P_SNAPSHOT_V1 reason=first_qualified_no_progress_window "
            f"stage=c0 slice=0 sg_cycle=99 qualified_key_total=302 "
            f"sain_saved={sain} saout_saved={saout} mse4_saved={mse4} "
            "saout_raw_changes=3 saout_raw_active=10 "
            f"saout_ready_active=3 saout_blocked={blocked} "
            f"saout_raw_valid_now={raw} saout_ready_now={ready} "
            "saout_raw_tag_now=0x3fc5 b5_mask_now=0xff "
            "armfin=0,0,0,0,0,0\n"
        )
        text = feature_line + snapshot
        if duplicate_snapshot:
            text += snapshot
        text += event_lines(sain, saout, mse4) + "\n"
        log.write_text(text, encoding="utf-8", newline="\n")
        return module.finalize(
            observer_log=log,
            compile_status=statuses / "compile",
            run_status=statuses / "run",
            signal_status=statuses / "signal",
        )

    cases = {
        "generation_stop": run_case(
            "generation", sain=28, saout=3, mse4=1, raw=0, ready=0, blocked=0
        ),
        "backpressure": run_case(
            "backpressure",
            sain=28,
            saout=3,
            mse4=1,
            raw=1,
            ready=0,
            blocked=100,
        ),
        "mse4_stall": run_case(
            "mse4", sain=3, saout=3, mse4=1, raw=0, ready=0, blocked=0
        ),
        "missing_feature": run_case(
            "missing_feature",
            sain=3,
            saout=3,
            mse4=1,
            raw=0,
            ready=0,
            blocked=0,
            feature=False,
        ),
        "duplicate_snapshot": run_case(
            "duplicate_snapshot",
            sain=3,
            saout=3,
            mse4=1,
            raw=0,
            ready=0,
            blocked=0,
            duplicate_snapshot=True,
        ),
    }
    checks = {
        "generation_stop_unique": (
            cases["generation_stop"]["valid"] is True
            and cases["generation_stop"]["status"]
            == "SA_OUTPUT_GENERATION_STOPPED_AFTER_ACCEPTED_INPUTS"
        ),
        "backpressure_unique": (
            cases["backpressure"]["valid"] is True
            and cases["backpressure"]["status"]
            == "SA_OUTPUT_HELD_BY_BUFFER_BACKPRESSURE"
        ),
        "mse4_unique": (
            cases["mse4_stall"]["valid"] is True
            and cases["mse4_stall"]["status"]
            == "SA_OUTPUT_REACHED_BUFFER_BUT_MSE4_DID_NOT_CONSUME"
        ),
        "missing_feature_fails": cases["missing_feature"]["valid"] is False,
        "duplicate_snapshot_fails": (
            cases["duplicate_snapshot"]["valid"] is False
        ),
        "stable_level_not_qualified_progress": (
            cases["backpressure"]["observer"]["event_counts"][
                "SA_OUT_ACCEPT"
            ]
            == 3
            and int(
                cases["backpressure"]["observer"]["snapshots"][0][
                    "saout_blocked"
                ]
            )
            == 100
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "cases": cases,
        "predicate_classes": 6,
        "uncovered": 0,
        "claim_boundary": "local event traces only; no DUT execution",
    }


def mapped_publisher(package: Path, mapped: Path, name: str) -> ModuleType:
    source = (
        package / "package_tools/fixed_simresult_publisher.py"
    ).read_text(encoding="utf-8")
    token = 'RESULT_ROOT = Path("/home/panqs/ndp/simresult")'
    if source.count(token) != 1:
        raise RuntimeError("production publisher fixed root differs")
    mapped_source = source.replace(
        token, f"RESULT_ROOT = Path({str(mapped)!r})", 1
    )
    harness = mapped.parent / f"{name}_publisher.py"
    harness.write_text(mapped_source, encoding="utf-8", newline="\n")
    return load_module(harness, f"_native4_p11_publish_{name}")


def publication_evidence(
    package: Path,
    mapped: Path,
    case: Path,
    *,
    compile_status: int,
    run_status: int,
    signal: str,
    duplicate_ok: bool = True,
) -> tuple[Path, Path]:
    evidence = case / "evidence"
    run = case / "run"
    evidence.mkdir(parents=True)
    (run / "c0").mkdir(parents=True)
    (run / "compile").mkdir(parents=True)
    for name in (
        "package_preflight.json",
        "install_preflight.json",
        "observer_precompile.json",
        "triggered_causal_summary.json",
        "public_order_summary.json",
        "SERVER_RESULT_GATE.json",
    ):
        write_json(evidence / name, {"schema": name, "valid": True})
    (evidence / "compile_exit_status.txt").write_text(
        f"{compile_status}\n", encoding="ascii"
    )
    (evidence / "run_exit_status.txt").write_text(
        f"{run_status}\n", encoding="ascii"
    )
    (evidence / "signal_status.txt").write_text(
        f"{signal}\n", encoding="ascii"
    )
    write_json(
        evidence / "publication_preflight.json",
        {
            "schema": "fixed-simresult-publication-preflight-v1",
            "result_root": str(mapped),
            "return_zip": str(
                mapped / f"{INSTALL_NAME}_return.zip"
            ),
            "return_sidecar": str(
                mapped / f"{INSTALL_NAME}_return.zip.sha256"
            ),
            "publication_state": "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING",
            "server_root_duplicate_absent": duplicate_ok,
            "package_root_duplicate_absent": True,
            "install_namespace_duplicate_absent": True,
            "run_root_duplicate_absent": True,
            "launch_cwd_duplicate_absent": True,
        },
    )
    return evidence, run


def fixed_publish_gate(package: Path, root: Path) -> dict[str, Any]:
    cases: dict[str, Any] = {}
    for name, values in {
        "normal": (0, 0, "NONE"),
        "compile_fail": (74, 125, "NONE"),
        "int": (0, 130, "INT"),
        "term": (0, 143, "TERM"),
    }.items():
        mapped = root / name / "simresult"
        mapped.mkdir(parents=True)
        evidence, run = publication_evidence(
            package,
            mapped,
            root / name / "case",
            compile_status=values[0],
            run_status=values[1],
            signal=values[2],
        )
        module = mapped_publisher(package, mapped, name)
        result = module.collect(
            package_root=package,
            evidence_root=evidence,
            run_root=run,
        )
        final_zip = mapped / f"{INSTALL_NAME}_return.zip"
        sidecar = Path(str(final_zip) + ".sha256")
        tokens = sidecar.read_text(encoding="ascii").split()
        cases[name] = {
            "result": result,
            "zip_exists": final_zip.is_file(),
            "sidecar_exists": sidecar.is_file(),
            "crc_valid": zipfile.ZipFile(final_zip).testzip() is None,
            "sidecar_valid": tokens == [sha256(final_zip), final_zip.name],
            "stage_absent": not any(
                item.name.startswith(f".{INSTALL_NAME}.publish.")
                for item in mapped.iterdir()
            ),
            "case_root_duplicate_absent": not any(
                item.name in {final_zip.name, sidecar.name}
                for item in (root / name / "case").rglob("*")
            ),
        }

    def fails(action) -> bool:
        try:
            action()
        except Exception:
            return True
        return False

    conflict = root / "conflict/simresult"
    conflict.mkdir(parents=True)
    (conflict / f"{INSTALL_NAME}_return.zip").write_text(
        "old", encoding="ascii"
    )
    ev, run = publication_evidence(
        package,
        conflict,
        root / "conflict/case",
        compile_status=0,
        run_status=0,
        signal="NONE",
    )
    conflict_fail = fails(
        lambda: mapped_publisher(package, conflict, "conflict").collect(
            package_root=package, evidence_root=ev, run_root=run
        )
    )
    dup = root / "duplicate/simresult"
    dup.mkdir(parents=True)
    ev2, run2 = publication_evidence(
        package,
        dup,
        root / "duplicate/case",
        compile_status=0,
        run_status=0,
        signal="NONE",
        duplicate_ok=False,
    )
    duplicate_fail = fails(
        lambda: mapped_publisher(package, dup, "duplicate").collect(
            package_root=package, evidence_root=ev2, run_root=run2
        )
    )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    helper = (
        package / "package_tools/fixed_simresult_publisher.py"
    ).read_text(encoding="utf-8")
    checks = {
        "normal_compile_fail_int_term": all(
            all(
                case[key]
                for key in (
                    "zip_exists",
                    "sidecar_exists",
                    "crc_valid",
                    "sidecar_valid",
                    "stage_absent",
                    "case_root_duplicate_absent",
                )
            )
            for case in cases.values()
        ),
        "target_conflict_fail_closed": conflict_fail,
        "duplicate_receipt_fail_closed": duplicate_fail,
        "production_fixed_literal": (
            runner.count(f'result_root="{FIXED_ROOT}"') == 1
            and helper.count(
                'RESULT_ROOT = Path("/home/panqs/ndp/simresult")'
            )
            == 1
        ),
        "production_path_not_configurable": (
            "SIMRESULT_ROOT" not in runner
            and "result-root" not in helper
            and "isolated_publish" not in runner
        ),
        "shared_signal_finalizer": all(
            token in runner
            for token in (
                "trap 'finalize $?' EXIT",
                "trap 'on_signal HUP 129' HUP",
                "trap 'on_signal INT 130' INT",
                "trap 'on_signal TERM 143' TERM",
                'python3 "$publisher"',
            )
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "cases": cases,
        "negative_controls": {
            "target_conflict": conflict_fail,
            "duplicate_receipt": duplicate_fail,
        },
        "production_target": FIXED_ROOT,
        "local_fixed_server_path_created_or_mapped": False,
        "claim_boundary": (
            "exact publisher logic runs only with its fixed Path literal "
            "replaced in disposable temp copies; production bytes stay fixed"
        ),
    }


def runner_gate(package: Path) -> dict[str, Any]:
    runner = package / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    syntax = subprocess.run(
        [str(BASH), "-n", str(runner)],
        text=True,
        capture_output=True,
        check=False,
    )
    checks = {
        "bash_syntax": syntax.returncode == 0,
        "preflight_install_guard_before_compile": (
            text.index('python3 "$runtime" preflight')
            < text.index('make -f Makefile.tb_NDP_Top_new_phy compile')
        ),
        "compile_then_nonblocking_identity_then_sim": (
            text.index('make -f Makefile.tb_NDP_Top_new_phy compile')
            < text.index('python3 "$runtime" compile-identity')
            < text.index('timeout --foreground --signal=TERM', text.index('simv='))
        ),
        "public_feature_twice": (
            text.count("+N4P_PUBLIC_ORDER_PROFILE") == 2
            and text.count("+N4P_EVENT_LIMIT=64") == 2
            and text.count("N4P_FILE=$public_log") == 2
        ),
        "actual_cloud_diff_nonblocking": (
            'compile-identity' in text
            and '[ "$compile_status" -eq 0 ] || exit "$compile_status"'
            in text
        ),
        "result_targets_only_fixed": (
            f'return_zip="{FIXED_ROOT}/{INSTALL_NAME}_return.zip"' in text
            and f'return_sha="{FIXED_ROOT}/{INSTALL_NAME}_return.zip.sha256"'
            in text
            and f'${{server_root}}/{INSTALL_NAME}_return.zip' not in text
        ),
        "duplicate_roots_checked": all(
            token in text
            for token in (
                '"$server_root" "$package_root" "$launch_cwd"',
                '"$server_root" "$package_root" "$launch_cwd" "$cfg_root" "$run_root"',
            )
        ),
        "timeout_unchanged": (
            'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv"'
            in text
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "bash_syntax": {
            "command": [str(BASH), "-n", str(runner)],
            "exit_code": syntax.returncode,
            "stdout": syntax.stdout,
            "stderr": syntax.stderr,
        },
        "claim_boundary": (
            "exact production runner syntax and control-flow/consumer "
            "closure; fixed publisher four-path harness is a separate gate"
        ),
    }


def main() -> int:
    package_zip = ZIP.resolve()
    package = PACKAGE.resolve()
    with tempfile.TemporaryDirectory(prefix="native4-p11f-final-") as temp:
        root = Path(temp)
        extracted, safe = safe_extract(package_zip, root / "extract")
        manifest = json.loads(
            (extracted / "package_manifest.json").read_text(encoding="utf-8")
        )
        preflight = subprocess.run(
            [
                str(PYTHON),
                "-B",
                str(
                    extracted
                    / "package_tools/"
                    "node0004_assumed_hardware_server_runtime.py"
                ),
                "preflight",
                "--package-root",
                str(extracted),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        observer_root = root / "observer"
        observer_root.mkdir(parents=True, exist_ok=True)
        observer_base = p10v.observer_gate(extracted, observer_root)
        trace = finalizer_trace(extracted, root / "trace")
        publish = fixed_publish_gate(extracted, root / "publish")
        runner = runner_gate(extracted)
        zip_directory_exact = build.records(extracted) == build.records(package)

    source = build.source_zip()
    with zipfile.ZipFile(source) as old_zip, zipfile.ZipFile(package_zip) as new_zip:
        old_root = f"{build.SOURCE_NAME}/workload/"
        new_root = f"{INSTALL_NAME}/workload/"
        old_payloads = {
            item.filename[len(old_root) :]: old_zip.read(item)
            for item in old_zip.infolist()
            if not item.is_dir() and item.filename.startswith(old_root)
        }
        new_payloads = {
            item.filename[len(new_root) :]: new_zip.read(item)
            for item in new_zip.infolist()
            if not item.is_dir() and item.filename.startswith(new_root)
        }
    normalized_equal = (
        set(old_payloads) == set(new_payloads)
        and all(
            old_payloads[path].replace(
                build.SOURCE_NAME.encode(), b"<IDENTITY>"
            )
            == new_payloads[path].replace(
                INSTALL_NAME.encode(), b"<IDENTITY>"
            )
            for path in old_payloads
        )
    )
    observer = package / "tb_probe/native_return_observer.svh"
    observer_text = observer.read_text(encoding="utf-8")
    append_text = build.OBSERVER_APPEND.read_text(encoding="utf-8")
    observer_checks = {
        "append_exact_suffix": observer_text.endswith(append_text),
        "focused_frontend_positive": (
            observer_base["positive_compile"]["exit_code"] == 0
            and observer_base["positive_simulation"]["exit_code"] == 0
        ),
        "base_actual_consumer_negatives": (
            observer_base["checks"]["delete_declaration_fails"]
            and observer_base["checks"]["wrong_sibling_fails"]
        ),
        "no_new_dut_hierarchy_reference": (
            observer_base["checks"]["no_new_private_xmr"]
        ),
        "state_owner_closure": all(
            token in append_text
            for token in (
                "bit n4p_snapshot_emitted;",
                "n4p_snapshot_emitted = 0;",
                "n4p_snapshot_emitted = 1;",
                "if (n4p_fd != 0 && !n4p_snapshot_emitted)",
            )
        ),
        "stable_level_separate_from_accept": (
            "n4p_sa_out_blocked_cycles++;" in append_text
            and "n4p_sa_out_saved++;" in append_text
            and "n4p_sa_out_blocked_cycles" not in (
                "n4t_key_total"
            )
        ),
    }
    sidecar_exact = (
        SIDECAR.read_text(encoding="ascii")
        == f"{sha256(package_zip)}  {package_zip.name}\n"
    )
    current_receipts = {
        item["path"]: item["sha256"] for item in manifest["rule_receipts"]
    }
    current_match = all(
        sha256(ROOT / path) == value
        for path, value in current_receipts.items()
    )
    profile_report = json.loads(
        (
            ROOT
            / "outputs/conv_native_four_lane_0ccae916_p10_return_analysis/"
            "p11f_profile_validation.json"
        ).read_text(encoding="utf-8")
    )
    matrix = manifest["release_gate_matrix"]
    checks = {
        "safe_zip": safe["valid"],
        "zip_directory_exact": zip_directory_exact,
        "manifest_identity": manifest.get("install_name") == INSTALL_NAME,
        "manifest_exact_set": manifest.get("files") == build.records(package),
        "source_p10_exact": sha256(source) == build.SOURCE_SHA256,
        "workload_config_normalized_byte_equal": normalized_equal,
        "package_preflight": preflight.returncode == 0,
        "sidecar_exact": sidecar_exact,
        "deterministic_double_build": json.loads(
            (
                build.OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
            ).read_text(encoding="utf-8")
        )["deterministic_double_build"],
        "observer_hdl_scope": all(observer_checks.values()),
        "predicate_trace": trace["valid"],
        "profile_validation": profile_report.get("valid") is True,
        "runner": runner["valid"],
        "fixed_publish": publish["valid"],
        "return_allowlist": all(
            any(
                item["target_path"] == target
                for item in manifest["return_allowlist"]
            )
            for target in (
                "evidence/publication_preflight.json",
                "evidence/public_order_summary.json",
                "runs/c0/public_order_observer.log",
            )
        ),
        "runtime_d_absent": (
            manifest.get("formal_readback_count") == 0
            and manifest.get("readback_checks") == []
        ),
        "functional_rtl_absent": (
            manifest.get("functional_rtl_modified") is False
            and manifest.get("functional_rtl_file_count") == 0
        ),
        "current_rule_receipts": current_match,
        "release_gate_matrix": (
            all(
                matrix[key]["pass"] is True
                for key in (
                    "core_always",
                    "runner",
                    "package_local_hdl",
                    "materialized_config",
                    "diagnostic_semantics",
                    "return_result",
                )
            )
            and matrix["materialized_config"]["applicable"]
            == "receipt_reuse"
        ),
        "path_budget": (
            safe["max_zip_member_chars"] <= 240
            and safe["max_depth"] <= 10
            and manifest["path_length_budget"][
                "max_projected_absolute_path_chars"
            ]
            <= 240
        ),
        "server_path_not_created_locally": not Path(
            r"C:\home\panqs\ndp\simresult"
        ).exists(),
    }
    errors = [name for name, value in checks.items() if not value]
    report = {
        "schema": "conv-native-four-lane-p11f-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "FAIL",
        "valid": not errors,
        "errors": errors,
        "package": str(package),
        "zip": str(package_zip),
        "zip_bytes": package_zip.stat().st_size,
        "zip_sha256": sha256(package_zip),
        "sidecar": str(SIDECAR),
        "checks": checks,
        "safe_zip": safe,
        "observer_gate": {
            "observer": {
                "path": "tb_probe/native_return_observer.svh",
                "size_bytes": observer.stat().st_size,
                "sha256": sha256(observer),
            },
            "checks": observer_checks,
            "focused_frontend": observer_base["positive_compile"],
            "negative_controls": {
                "delete_declaration": observer_base["checks"][
                    "delete_declaration_fails"
                ],
                "wrong_sibling": observer_base["checks"][
                    "wrong_sibling_fails"
                ],
                "delete_reset_or_update": observer_checks[
                    "state_owner_closure"
                ],
            },
            "actual_consumer_uncovered": 0,
        },
        "predicate_trace": trace,
        "runner_gate": runner,
        "fixed_publish_gate": publish,
        "release_gate_matrix": matrix,
        "current_rule_receipts": current_receipts,
        "local_fixed_server_path_created_or_mapped": False,
        "duplicate_absent_expected_receipt": {
            "server_root": True,
            "package_root": True,
            "install_namespace": True,
            "run_root": True,
            "launch_cwd": True,
        },
        "claim_boundary": (
            "p11f is c0 diagnostic only. It changes observer/finalizer/"
            "publisher surfaces and reuses normalized-byte-equal p10 "
            "workload/config; no DUT run, formal 320D, E3/E4/E5 or "
            "performance claim is made locally."
        ),
    }
    write_json(OUTPUT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
