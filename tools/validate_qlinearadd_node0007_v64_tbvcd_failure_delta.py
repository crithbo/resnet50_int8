#!/usr/bin/env python3
"""Family hard gate for the audited QAdd v64 TB-VCD failure-rule delta."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"
TB_REL = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def import_path(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def files_map(root: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(root).as_posix(): (path.stat().st_size, sha(path))
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def source_span(path: Path, name: str) -> str | None:
    rows = path.read_text(encoding="utf-8", errors="strict").splitlines()
    matches = [
        row.strip()
        for row in rows
        if re.search(rf"\b{re.escape(name)}\b", row)
        and not row.lstrip().startswith("//")
    ]
    return hashlib.sha256(matches[0].encode("utf-8")).hexdigest() if matches else None


def exact_dump_check(source: str, expected: set[str]) -> dict[str, Any]:
    rows = re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^;]+?)\s*\)\s*;", source)
    actual = {row.strip() for row in rows}
    return {
        "pass": actual == expected and len(rows) == len(expected),
        "actual_count": len(rows),
        "expected_count": len(expected),
        "missing": sorted(expected - actual),
        "extra": sorted(actual - expected),
        "duplicates": len(rows) != len(actual),
    }


def validate_tree(package: Path, iverilog: Path | None) -> dict[str, Any]:
    errors: list[str] = []
    manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    contract = json.loads((package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
    catalog = json.loads((package / "diagnostics/tb_vcd_signal_catalog.json").read_text(encoding="utf-8"))
    matrix = json.loads((package / "diagnostics/tb_vcd_candidate_matrix.json").read_text(encoding="utf-8"))
    plan = json.loads((package / "diagnostics/tb_vcd_exact_dump_plan.json").read_text(encoding="utf-8"))
    audit = json.loads((package / "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json").read_text(encoding="utf-8"))
    request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
    allowlist = json.loads((package / "RETURN_ALLOWLIST.json").read_text(encoding="utf-8"))
    tb_path = package / TB_REL
    tb = tb_path.read_text(encoding="utf-8")
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    supervisor = (package / "package_tools/qlinearadd_node0007_tb_vcd_guarded_supervisor_v63.py").read_text(encoding="utf-8")
    finalizer = (package / "package_tools/qlinearadd_node0007_tb_vcd_finalize_v63.py").read_text(encoding="utf-8")
    parser = (package / "package_tools/server_tb_vcd_retention_analysis.py").read_text(encoding="utf-8")

    declared = {
        name: (row["size_bytes"], row["sha256"])
        for name, row in manifest.get("files", {}).items()
    }
    checks: dict[str, bool] = {
        "package_identity": manifest.get("package_id") == PACKAGE and manifest.get("install_name") == PACKAGE and contract.get("package_id") == PACKAGE,
        "manifest_exact_set": declared == files_map(package),
        "audit_precedes_build": audit.get("status") == "AUDIT_SUBMITTED_BEFORE_THIRD_ATTEMPT_BUILD" and audit.get("disposition") == "RULE_DELTA_PROPOSAL",
        "catalog_64": catalog.get("signal_count") == 64 and len(catalog.get("signals", [])) == 64,
        "roles_41": len(contract.get("role_coverage", [])) == 41,
        "four_layers": {row.get("layer") for row in contract.get("boundaries", [])} == {"FIRST_DIVERGENCE_UPSTREAM_ONE", "FIRST_DIVERGENCE_CURRENT", "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "STATE_HOLD_CLEAR"},
        "candidate_matrix_complete": len(matrix.get("candidate_boundary_matrix", [])) == len(matrix.get("candidates", [])) * len(matrix.get("boundaries", [])) and matrix.get("pairwise_complete") is True,
        "exact_dump_plan": plan.get("strategy") == "EXPLICIT_SOURCE_BOUND_SIGNAL_ONLY" and plan.get("signal_count") == 64 and plan.get("module_scope_dump_forbidden") is True,
        "heartbeat_no_rtoi": "$rtoi" not in tb and "tbvcd_sim_time_ps = $time;" in tb,
        "heartbeat_cadence": "64'h3fff" in tb and "64'h3ffff" not in tb,
        "real_vcd_time_supervision": all(token in supervisor for token in ("def scan_vcd_time", "last_vcd_time", '"simulation_time": last_vcd_time')),
        "multiline_timescale_parser": 'state.get("timescale") == ""' in parser,
        "finalization_conjunction": '"pass": runtime_receipt.get("diagnostic_status") == "DIAGNOSTIC_EVIDENCE_COMPLETE"' in finalizer and "CODEX_TB_VCD_CLOSED" in finalizer,
        "exact_return_receipt_created": "TB_VCD_RETURN_EXACT_SET.json" in finalizer,
        "live_compile_state": '"compile_succeeded":true,"simulation_started":true' in runner,
        "structured_supervisor_error": "SUPERVISOR_STOP:" in runner,
        "single_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
        "dump_argv_zero": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")),
        "server_action_absent": manifest.get("server_run_performed") is False and manifest.get("uploaded") is False,
    }

    expected = {row["exact_hierarchy"] for row in catalog["signals"]}
    dump = exact_dump_check(tb, expected)
    checks["dumpvars_exact_signal_set"] = dump["pass"]
    exact_receipt = "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json"
    required_entries = {
        row.get("archive")
        for row in request.get("core_entries", [])
        if row.get("required") is True
    }
    checks["exact_receipt_required_in_return"] = exact_receipt in required_entries and exact_receipt in allowlist.get("required", [])

    source_errors: list[str] = []
    for row in catalog["signals"]:
        source = (ROOT / "NDP_copy01" / row["source_path"]).resolve()
        try:
            source.relative_to((ROOT / "NDP_copy01").resolve())
        except ValueError:
            source_errors.append(f"{row['signal_id']}:source_escape")
            continue
        leaf = row["exact_hierarchy"].rsplit(".", 1)[-1]
        if not source.is_file() or sha(source) != row["source_sha256"] or source_span(source, leaf) != row["declaration_span_sha256"]:
            source_errors.append(f"{row['signal_id']}:source_identity")
    checks["source_identity_recomputed"] = not source_errors

    generic_out = package.parent / ".v64_generic_contract.json"
    generic = subprocess.run(
        [
            str(Path(__import__("sys").executable)),
            str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"),
            "--contract", str(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"),
            "--root", str(package),
            "--output", str(generic_out),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    checks["shared_contract_gate"] = generic.returncode == 0 and json.loads(generic_out.read_text(encoding="utf-8")).get("pass") is True
    generic_out.unlink(missing_ok=True)

    frontend: dict[str, Any] = {"run": False}
    if iverilog is not None:
        focused = tb.split("\nbind tb_NDP_Top_new_phy ", 1)[0] + "\n"
        focused = re.sub(r"\$dumpvars\s*\(\s*0\s*,\s*[^;]+?\s*\)\s*;", "$dumpvars;", focused)
        with tempfile.TemporaryDirectory(prefix="qadd-v64-hdl-") as raw:
            positive = Path(raw) / "positive.sv"
            negative = Path(raw) / "negative.sv"
            positive.write_text(focused, encoding="utf-8")
            negative.write_text(focused.replace("tbvcd_owner_cycles = 0;", "tbvcd_owner_cycles = ;", 1), encoding="utf-8")
            command = [str(iverilog), "-g2012", "-tnull", "-s", "codex_qadd_tb_vcd_causal_cone_v64"]
            good = subprocess.run(command + [str(positive)], capture_output=True, text=True, timeout=60, check=False)
            bad = subprocess.run(command + [str(negative)], capture_output=True, text=True, timeout=60, check=False)
        checks["frontend_positive"] = good.returncode == 0
        checks["frontend_negative"] = bad.returncode != 0
        frontend = {"run": True, "positive_exit": good.returncode, "negative_exit": bad.returncode, "positive_stderr": good.stderr[-2048:]}

    retention = import_path(package / "package_tools/server_tb_vcd_retention_analysis.py", "qadd_v64_retention")
    with tempfile.TemporaryDirectory(prefix="qadd-v64-parser-") as raw:
        root = Path(raw)
        vcd = root / "multiline.vcd"
        vcd.write_text("$timescale\n 1ps\n$end\n$scope module top $end\n$var wire 1 ! clk $end\n$upscope $end\n$enddefinitions $end\n#0\n0!\n#1\n1!\n", encoding="ascii")
        retention.analyze_chunk(vcd, root / "state", "vcd", max_bytes=4096)
        parsed = json.loads((root / "state/analysis_state.json").read_text(encoding="utf-8"))
    checks["multiline_timescale_dynamic"] = parsed.get("timescale") == "1ps"

    module_scope = next(row["exact_hierarchy"].rsplit(".", 1)[0] for row in catalog["signals"] if row["signal_id"] == "sig_valid_buf")
    mutated_dump = re.sub(r"\$dumpvars\s*\(\s*0\s*,\s*[^;]+?\s*\)\s*;", f"$dumpvars(0, {module_scope});", tb, count=1)
    negatives = {
        "whole_module_dump_rejected": not exact_dump_check(mutated_dump, expected)["pass"],
        "rtoi_heartbeat_rejected": "$rtoi" in tb.replace("tbvcd_sim_time_ps = $time;", "tbvcd_sim_time_ps = $rtoi($realtime * 1000.0);") and checks["heartbeat_no_rtoi"],
        "sparse_heartbeat_rejected": "64'h3ffff" in tb.replace("64'h3fff", "64'h3ffff") and checks["heartbeat_cadence"],
        "heartbeat_only_freeze_rejected": '"simulation_time": last_vcd_time' not in supervisor.replace('"simulation_time": last_vcd_time', '"simulation_time": last_progress["sim_time"]') and checks["real_vcd_time_supervision"],
        "missing_exact_receipt_rejected": exact_receipt in required_entries and exact_receipt in allowlist.get("required", []),
    }
    checks["first_fresh_negatives"] = all(negatives.values())
    errors.extend(name for name, passed in checks.items() if not passed)
    errors.extend(source_errors)
    return {
        "schema": "qadd-v64-tb-vcd-failure-delta-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "exact_dump": dump,
        "negative_controls": negatives,
        "frontend": frontend,
        "claim_boundary": "Local package and family failure-delta gates only; no production compile, simulation, DUT root, natural terminal, formal D, E3, E4 or E5 claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--tree", type=Path)
    group.add_argument("--zip", type=Path)
    parser.add_argument("--iverilog", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.tree is not None:
        report = validate_tree(args.tree.resolve(), args.iverilog)
    else:
        with tempfile.TemporaryDirectory(prefix="qadd-v64-final-zip-") as raw:
            extract = Path(raw) / "extract"
            with zipfile.ZipFile(args.zip) as archive:
                names = archive.namelist()
                roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
                unsafe = [name for name in names if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts]
                if roots != {PACKAGE} or unsafe or archive.testzip() is not None or len(names) != len(set(names)):
                    raise RuntimeError("unsafe, corrupt, duplicate, or wrong-root final ZIP")
                archive.extractall(extract)
            report = validate_tree(extract / PACKAGE, args.iverilog)
            report["exact_final_zip_sha256"] = sha(args.zip)
            report["from_clean_extract"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "errors": report["errors"]}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
