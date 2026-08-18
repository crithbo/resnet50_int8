#!/usr/bin/env python3
"""Validate exact QAdd v69 plus the recurring precompile-core control."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v69_pfc"
PRIOR = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"
PRIOR_SHA = "449e07e917bca6ff406bd94804903375e24d51b74b5c20762dc53e110ff228f4"
TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v69.svh"
LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v69.py"
FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v69.py"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def adapted_v68_main(args: argparse.Namespace) -> int:
    source_path = ROOT / "tools/validate_qlinearadd_node0007_v68_cfg42_tick.py"
    source = source_path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"', f'PACKAGE = "{PACKAGE}"'),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"', f'PRIOR = "{PRIOR}"'),
        ('PRIOR_SHA = "dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740"', f'PRIOR_SHA = "{PRIOR_SHA}"'),
        ('TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v68.svh"', f'TB = "{TB}"'),
        ('LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v68.py"', f'LIVE = "{LIVE}"'),
        ('qlinearadd_node0007_tb_vcd_live_supervision_v68.py', 'qlinearadd_node0007_tb_vcd_live_supervision_v69.py'),
        ('qlinearadd_node0007_tb_vcd_finalize_v68.py', 'qlinearadd_node0007_tb_vcd_finalize_v69.py'),
        ('qadd-v68', 'qadd-v69'),
        ('qadd_v68', 'qadd_v69'),
        ('QAdd v68', 'QAdd v69'),
        ('v68-negative-control', 'v69-negative-control'),
        ('round_index") == 2', 'round_index") == 3'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v68 validator adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v69_adapted_v68_validator", "__file__": str(source_path)}
    exec(compile(source, str(source_path), "exec"), namespace)
    prior_argv = sys.argv
    try:
        sys.argv = [
            str(source_path),
            "--tree", str(args.tree),
            "--zip", str(args.zip),
            "--repeat-zip", str(args.repeat_zip),
            "--prior-zip", str(args.prior_zip),
            "--output", str(args.base_output),
        ]
        return int(namespace["main"]())
    finally:
        sys.argv = prior_argv


def zip_json(archive: zipfile.ZipFile, relative: str) -> Any:
    return json.loads(archive.read(f"{PACKAGE}/{relative}"))


def capture_checks(tree: Path, package_zip: Path, prior_zip: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    runner_tree = (tree / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    request_tree = load(tree / "contracts/server_post_sim_return_request.json")
    allow_tree = load(tree / "RETURN_ALLOWLIST.json")
    contract_tree = load(tree / "diagnostics/precompile_core_capture_contract.json")
    manifest_tree = load(tree / "TEST_PACKAGE_MANIFEST.json")
    with zipfile.ZipFile(package_zip) as archive:
        runner_zip = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode("utf-8")
        request_zip = zip_json(archive, "contracts/server_post_sim_return_request.json")
        allow_zip = zip_json(archive, "RETURN_ALLOWLIST.json")
        contract_zip = zip_json(archive, "diagnostics/precompile_core_capture_contract.json")
        manifest_zip = zip_json(archive, "TEST_PACKAGE_MANIFEST.json")

    required = set(contract_tree["required_return_members"])
    request_map = {row["archive"]: row for row in request_tree["core_entries"]}
    zip_request_map = {row["archive"]: row for row in request_zip["core_entries"]}
    exact_tokens = [
        'package_preflight_stdout="$evidence_root/PACKAGE_PREFLIGHT_STDOUT.txt"',
        'package_preflight_stderr="$evidence_root/PACKAGE_PREFLIGHT_STDERR.txt"',
        'package_preflight_receipt="$evidence_root/PACKAGE_PREFLIGHT_EXECUTION.json"',
        'runner_stage_receipt="$evidence_root/RUNNER_STAGE_RECEIPT.json"',
        '>"$package_preflight_stdout" 2>"$package_preflight_stderr"',
        'package_preflight_status=$?',
        "qadd-package-runtime-preflight-execution-v1",
        "qadd-runner-stage-receipt-v1",
        "blocked_stage':'PACKAGE_RUNTIME_PREFLIGHT",
        "source_identity_status':'COMPILE_NOT_STARTED",
        "'compile_argv':[],'sim_argv':[]",
        "compile_first_error.txt",
        "stdout/stderr/exit/stage/first-error captured",
    ]
    no_probe_tokens = ["command -v", "which ", "find ", "stat ", "git ", "make -n", "make --dry-run"]

    runtime = tree / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    positive = subprocess.run(
        [sys.executable, str(runtime), "preflight", "--package-root", str(tree)],
        text=True, capture_output=True, env=env, check=False,
    )
    negative_member = tree / ".qadd_v69_preflight_negative_control"
    if negative_member.exists():
        raise RuntimeError("negative-control sentinel already exists")
    negative_member.write_text("intentional exact-set mismatch\n", encoding="utf-8")
    try:
        negative = subprocess.run(
            [sys.executable, str(runtime), "preflight", "--package-root", str(tree)],
            text=True, capture_output=True, env=env, check=False,
        )
    finally:
        negative_member.unlink()

    checks = {
        "base_exact_runner_equal": runner_tree == runner_zip,
        "capture_tokens_staging": all(token in runner_tree for token in exact_tokens),
        "capture_tokens_exact_zip": all(token in runner_zip for token in exact_tokens),
        "single_production_launch_marker": runner_tree.count("# CODEX_PRODUCTION_LAUNCH") == 1,
        "no_added_server_inventory_probe": not any(token in runner_tree for token in no_probe_tokens),
        "required_capture_entries_staging": all(path in request_map and request_map[path].get("required") is True for path in required),
        "required_capture_entries_exact_zip": all(path in zip_request_map and zip_request_map[path].get("required") is True for path in required),
        "required_capture_allowlist_staging": all(path in allow_tree.get("required", []) and f"{PACKAGE}_return/{path}" in allow_tree.get("required", []) for path in required),
        "required_capture_allowlist_exact_zip": all(path in allow_zip.get("required", []) and f"{PACKAGE}_return/{path}" in allow_zip.get("required", []) for path in required),
        "contract_tree_zip_equal": contract_tree == contract_zip,
        "contract_pass": contract_tree.get("pass") is True and contract_tree.get("functional_delta") is False,
        "manifest_identity_exact": all(manifest_tree.get(key) == PACKAGE for key in ("package_id", "package_identity", "install_name")) and manifest_tree == manifest_zip,
        "runtime_preflight_positive": positive.returncode == 0 and '"valid": true' in positive.stdout.lower() and not positive.stderr.strip(),
        "runtime_preflight_negative": negative.returncode != 0 and "package exact-set differs" in negative.stderr,
        "negative_control_removed": not negative_member.exists(),
        "prior_pending_byte_frozen": prior_zip.stat().st_size == 108_709_836 and sha(prior_zip) == PRIOR_SHA,
    }
    facts = {
        "positive": {"exit": positive.returncode, "stdout": positive.stdout[:4096], "stderr": positive.stderr[:4096]},
        "negative": {"exit": negative.returncode, "stdout": negative.stdout[:4096], "stderr": negative.stderr[:4096]},
        "capture_required": sorted(required),
        "runner_sha256": hashlib.sha256(runner_tree.encode()).hexdigest(),
    }
    return checks, facts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--base-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.base_output is None:
        args.base_output = args.output.with_name(args.output.stem + ".base.json")
    base_exit = adapted_v68_main(args)
    checks, facts = capture_checks(args.tree.resolve(), args.zip.resolve(), args.prior_zip.resolve())
    errors = [name for name, passed in checks.items() if not passed]
    if base_exit != 0:
        errors.append("adapted_v68_exact_suite")
    report = {
        "schema": "qadd-v69-precompile-core-exact-validation-v1",
        "package_id": PACKAGE,
        "base_suite": {"path": args.base_output.as_posix(), "exit": base_exit, "pass": base_exit == 0},
        "capture_checks": checks,
        "facts": facts,
        "package": {"path": args.zip.as_posix(), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "prior_pending": {"path": args.prior_zip.as_posix(), "bytes": args.prior_zip.stat().st_size, "sha256": sha(args.prior_zip)},
        "storage_manager_called": False,
        "server_actions_performed": [],
        "pass": not errors,
        "errors": errors,
        "claim_boundary": "Local exact final-ZIP and precompile capture controls only; no production compile/simulation/functional/terminal claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
