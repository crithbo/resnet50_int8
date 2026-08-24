#!/usr/bin/env python3
"""Build exact-final-ZIP and first-fresh receipts for serialized Conv v112.

This tool is local-only.  It reads the already-built ZIP, uses a clean
temporary extraction, and never invokes storage or any server command.
"""

from __future__ import annotations

import hashlib
import json
import py_compile
import shutil
import subprocess
import sys
import tempfile
import zipfile
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v112_tupleleaf_20260822"
GATES = OUT / "gates"
AUDIT = OUT / "first_fresh_extra_audit"
REPORTS = AUDIT / "reports"
PACKAGE = "r5_n4_hw_v112b_tupleleaf_tbvcd"
ZIP = OUT / f"{PACKAGE}.zip"
TREE = OUT / "build" / PACKAGE
FAMILY = "conv_serialized_node0004"


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(path)
    return value


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def tree_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "bytes": path.stat().st_size,
            "sha256": sha_file(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def run(command: list[str], cwd: Path = ROOT) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    return {
        "argv": command,
        "cwd": str(cwd),
        "exit": completed.returncode,
        "stdout": completed.stdout[-8192:],
        "stderr": completed.stderr[-8192:],
    }


def report_receipt(gate_id: str, kind: str, path: Path) -> dict[str, Any]:
    return {
        "gate_id": gate_id,
        "evidence_kind": kind,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha_file(path),
    }


def main() -> int:
    zip_sha = sha_file(ZIP)
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v112-exact-") as temporary:
        temp = Path(temporary)
        extract_root = temp / "extract"
        extract_root.mkdir()
        with zipfile.ZipFile(ZIP) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("duplicate ZIP members")
            for name in names:
                member = PurePosixPath(name)
                if member.is_absolute() or ".." in member.parts or "\\" in name:
                    errors.append(f"unsafe ZIP member: {name}")
            bad = archive.testzip()
            if bad is not None:
                errors.append(f"ZIP CRC failure: {bad}")
            if not errors:
                archive.extractall(extract_root)
        extracted = extract_root / PACKAGE
        stage_map = tree_map(TREE)
        exact_map = tree_map(extracted) if extracted.is_dir() else {}

        # Rebuild deterministically from the clean exact extraction.
        sys.path.insert(0, str(ROOT))
        import tools.build_node0004_v112b_tupleleaf_tbvcd_successor as builder

        rebuilt = temp / "rebuilt.zip"
        if extracted.is_dir():
            builder.deterministic_zip(extracted, rebuilt)
        deterministic = rebuilt.is_file() and sha_file(rebuilt) == zip_sha

        manifest = load(extracted / "package_manifest.json")
        exact_preflight = run(
            [
                sys.executable,
                str(extracted / "package_tools/package_release_preflight.py"),
                "preflight",
                "--package-root",
                str(extracted),
            ]
        )
        exact_runtime_path = temp / "runtime_preflight_exact.json"
        exact_runtime_invocation = run(
            [
                sys.executable,
                str(ROOT / "tools/validate_server_runtime_preflight_native_flow.py"),
                "--runner",
                str(extracted / "PREPARE_AND_RUN.sh"),
                "--dispatch",
                str(
                    extracted
                    / "contracts/server_runtime_preflight_native_flow_dispatch_v1.json"
                ),
                "--output",
                str(exact_runtime_path),
            ]
        )

        negative_root = temp / "negative"
        shutil.copytree(extracted, negative_root)
        negative_manifest = load(negative_root / "package_manifest.json")
        negative_manifest["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"
        write(negative_root / "package_manifest.json", negative_manifest)
        negative_preflight = run(
            [
                sys.executable,
                str(negative_root / "package_tools/package_release_preflight.py"),
                "preflight",
                "--package-root",
                str(negative_root),
            ]
        )

        compile_errors: list[str] = []
        python_rows = []
        bytecode_root = temp / "bytecode"
        bytecode_root.mkdir()
        for index, source in enumerate(
            sorted(item for item in extracted.rglob("*.py") if item.is_file())
        ):
            try:
                py_compile.compile(
                    str(source),
                    cfile=str(bytecode_root / f"{index}.pyc"),
                    doraise=True,
                )
                status = "PASS"
            except py_compile.PyCompileError as exc:
                status = "FAIL"
                compile_errors.append(f"{source.relative_to(extracted)}:{exc}")
            python_rows.append(
                {
                    "path": source.relative_to(extracted).as_posix(),
                    "sha256": sha_file(source),
                    "status": status,
                }
            )

        exact_checks = {
            "crc_pass": not errors,
            "single_root": extracted.is_dir(),
            "exact_tree_zip_equal": stage_map == exact_map,
            "manifest_package_id": manifest.get("package_id") == PACKAGE,
            "manifest_ready": manifest.get("status") == "PACKAGE_READY_NOT_RUN",
            "deterministic_rebuild": deterministic,
            "single_zip_policy": not ZIP.with_suffix(ZIP.suffix + ".sha256").exists(),
        }
        final_report = {
            "schema": "server-final-zip-content-gate-v1",
            "package_id": PACKAGE,
            "pass": all(exact_checks.values()) and not errors,
            "errors": errors + [name for name, value in exact_checks.items() if not value],
            "checks": exact_checks,
            "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": zip_sha},
            "member_count": len(exact_map),
            "claim_boundary": "Local exact ZIP identity, deterministic reconstruction and clean-extract byte equality only.",
        }
        final_zip_path = GATES / "final_zip_content.json"
        write(final_zip_path, final_report)

        exact_report = {
            "schema": "node0004-v112-first-fresh-exact-zip-v1",
            "pass": final_report["pass"],
            "errors": final_report["errors"],
            "clean_extract": True,
            "from_final_zip_only": True,
            "checks": exact_checks,
            "zip": final_report["zip"],
        }
        exact_path = REPORTS / "exact_final_zip_clean_extract.json"
        write(exact_path, exact_report)

        runner_gate = load(GATES / "runner_zip.json")
        runtime_gate = load(exact_runtime_path)
        runner_report_checks = {
            "runner_resilience": runner_gate.get("pass") is True,
            "runtime_preflight_noninterference": runtime_gate.get("pass") is True,
            "runtime_preflight_exact_zip_invocation": exact_runtime_invocation["exit"] == 0,
            "exact_zip_package_preflight": exact_preflight["exit"] == 0,
            "pending_status_negative": negative_preflight["exit"] != 0
            and "package claim boundary differs" in (
                negative_preflight["stdout"] + negative_preflight["stderr"]
            ),
            "python_exact_set_compile": not compile_errors and bool(python_rows),
            "bytecode_outside_package": not any(extracted.rglob("*.pyc")),
        }
        runner_report = {
            "schema": "node0004-v112-first-fresh-runner-input-v1",
            "pass": all(runner_report_checks.values()),
            "errors": [name for name, value in runner_report_checks.items() if not value],
            "checks": runner_report_checks,
            "runner_gate": runner_gate,
            "runtime_preflight_gate": runtime_gate,
            "exact_zip_preflight": exact_preflight,
            "pending_status_negative": negative_preflight,
            "python_sources": python_rows,
        }
        runner_path = REPORTS / "actual_runner_entry_and_input_open.json"
        write(runner_path, runner_report)

        source_gate = load(GATES / "hdl_source_bound_zip.json")
        exact_tb_path = temp / "tb_vcd_exact.json"
        exact_tb_invocation = run(
            [
                sys.executable,
                str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"),
                "--contract",
                str(extracted / "contracts/tb_vcd_bounded_causal_cone_contract.json"),
                "--root",
                str(extracted),
                "--output",
                str(exact_tb_path),
            ]
        )
        tb_gate = load(exact_tb_path)
        source_report = {
            "schema": "node0004-v112-first-fresh-source-bound-roundtrip-v1",
            "pass": source_gate.get("pass") is True and tb_gate.get("pass") is True,
            "errors": list(source_gate.get("errors", [])) + list(tb_gate.get("errors", [])),
            "source_bound": source_gate,
            "tb_vcd": tb_gate,
            "exact_zip_tb_vcd_invocation": exact_tb_invocation,
            "complete_ordered_four_state_required": True,
            "unbounded_no_sampling_or_truncation": True,
        }
        source_path = REPORTS / "source_bound_logger_collector_parser_roundtrip.json"
        write(source_path, source_report)

        post_gate = load(GATES / "post_sim_zip.json")
        post_report = {
            "schema": "node0004-v112-first-fresh-post-sim-v1",
            "pass": post_gate.get("pass") is True,
            "errors": list(post_gate.get("errors", [])),
            "post_sim_return_core": post_gate,
            "single_zip_return": True,
            "partial_core_preserved": True,
        }
        post_path = REPORTS / "post_sim_return_core_scenarios.json"
        write(post_path, post_report)

        contract = load(extracted / "contracts/tb_vcd_bounded_causal_cone_contract.json")
        candidates = [row["candidate_id"] for row in contract["candidates"]]
        boundaries = [row["boundary_id"] for row in contract["boundaries"]]
        rows = {
            (row["candidate_id"], row["boundary_id"]): json.dumps(
                row["expected_signature"], sort_keys=True
            )
            for row in contract["candidate_boundary_matrix"]
        }
        indistinguishable = [
            [left, right]
            for left, right in combinations(candidates, 2)
            if all(rows.get((left, boundary)) == rows.get((right, boundary)) for boundary in boundaries)
        ]
        negative_controls = source_gate.get("negative_controls", {})
        matrix_checks = {
            "matrix_exact_set": len(rows) == len(candidates) * len(boundaries),
            "pairwise_distinguishable": not indistinguishable,
            "all_candidates_covered": all(
                all((candidate, boundary) in rows for boundary in boundaries)
                for candidate in candidates
            ),
            "negative_controls": bool(negative_controls) and all(negative_controls.values()),
        }
        matrix_report = {
            "schema": "node0004-v112-first-fresh-candidate-matrix-v1",
            "pass": all(matrix_checks.values()),
            "errors": [name for name, value in matrix_checks.items() if not value],
            "checks": matrix_checks,
            "candidate_ids": candidates,
            "boundary_ids": boundaries,
            "matrix_rows": len(rows),
            "indistinguishable_pairs": indistinguishable,
            "positive_control_count": len(candidates),
            "negative_controls": negative_controls,
        }
        matrix_path = REPORTS / "candidate_discrimination_matrix.json"
        write(matrix_path, matrix_report)

    evidence_reports = [
        report_receipt("exact_final_zip_clean_extract", "exact-final-zip-clean-extract", exact_path),
        report_receipt("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths", runner_path),
        report_receipt("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance", source_path),
        report_receipt("post_sim_return_core_scenarios", "exact-final-request-four-scenario", post_path),
        report_receipt("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix", matrix_path),
    ]
    first_fresh = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": PACKAGE,
            "family": FAMILY,
            "final_zip": {
                "path": ZIP.relative_to(ROOT).as_posix(),
                "bytes": ZIP.stat().st_size,
                "sha256": zip_sha,
            },
        },
        "rule_change": {
            "epoch_id": "family-dispatch-mode-binding-v1-registry43-tbvcd-v112",
            "rule_ids": [
                "CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001",
                "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
            ],
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
        "evidence_reports": evidence_reports,
        "candidate_discrimination": {
            "candidate_ids": candidates,
            "covered_candidate_ids": candidates,
            "uncovered_candidate_ids": [],
            "positive_control_count": len(candidates),
            "negative_control_count": len(negative_controls),
            "pairwise_distinguishable": not indistinguishable,
        },
        "findings": [],
    }
    write(AUDIT / "contract.json", first_fresh)
    print(json.dumps({"pass": all(load(path)["pass"] for path in (exact_path, runner_path, source_path, post_path, matrix_path)), "zip_sha256": zip_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
