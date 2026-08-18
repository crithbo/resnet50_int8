#!/usr/bin/env python3
"""Validate exact QAdd v70 and the v69 PID-map recurrence controls."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v70_pmapfix"
PRIOR = "r5_qadd_n7_tailround_lanephase_v69_pfc"
PRIOR_SHA = "2f4196597f12e424df97a94af2e614e413dea8032a04752c0c97fc57ec1d8597"
LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v70.py"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def adapted_v69(args: argparse.Namespace) -> int:
    path = ROOT / "tools/validate_qlinearadd_node0007_v69_cfg42_pfcore.py"
    source = path.read_text(encoding="utf-8")
    replacements = [
        ('PACKAGE = "r5_qadd_n7_tailround_lanephase_v69_pfc"', f'PACKAGE = "{PACKAGE}"'),
        ('PRIOR = "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2"', f'PRIOR = "{PRIOR}"'),
        ('PRIOR_SHA = "449e07e917bca6ff406bd94804903375e24d51b74b5c20762dc53e110ff228f4"', f'PRIOR_SHA = "{PRIOR_SHA}"'),
        ('qlinearadd_node0007_tb_vcd_causal_cone_v69.svh', 'qlinearadd_node0007_tb_vcd_causal_cone_v70.svh'),
        ('qlinearadd_node0007_tb_vcd_live_supervision_v69.py', 'qlinearadd_node0007_tb_vcd_live_supervision_v70.py'),
        ('qlinearadd_node0007_tb_vcd_finalize_v69.py', 'qlinearadd_node0007_tb_vcd_finalize_v70.py'),
        ('qadd-v69', 'qadd-v70'), ('qadd_v69', 'qadd_v70'), ('QAdd v69', 'QAdd v70'),
        ('v69-negative-control', 'v70-negative-control'),
        ('round_index") == 3', 'round_index") == 4'),
        ('prior_zip.stat().st_size == 108_709_836', 'prior_zip.stat().st_size == 108_735_727'),
    ]
    for old, new in replacements:
        if old not in source:
            raise RuntimeError(f"v69 validator adapter anchor drifted: {old}")
        source = source.replace(old, new)
    namespace: dict[str, Any] = {"__name__": "qadd_v70_adapted_v69_validator", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), namespace)
    prior_argv = sys.argv
    try:
        sys.argv = [str(path), "--tree", str(args.tree), "--zip", str(args.zip), "--repeat-zip", str(args.repeat_zip), "--prior-zip", str(args.prior_zip), "--base-output", str(args.base_output), "--output", str(args.adapted_output)]
        return int(namespace["main"]())
    finally:
        sys.argv = prior_argv


def exact_checks(tree: Path, package_zip: Path, prior_zip: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    supervisor = (tree / LIVE).read_text(encoding="utf-8")
    runner = (tree / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    request = load(tree / "contracts/server_post_sim_return_request.json")
    allow = load(tree / "RETURN_ALLOWLIST.json")
    contract = load(tree / "diagnostics/supervisor_pid_map_fix_contract.json")
    with zipfile.ZipFile(package_zip) as archive:
        zip_supervisor = archive.read(f"{PACKAGE}/{LIVE}").decode()
        zip_runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode()
        zip_request = json.loads(archive.read(f"{PACKAGE}/contracts/server_post_sim_return_request.json"))
        zip_allow = json.loads(archive.read(f"{PACKAGE}/RETURN_ALLOWLIST.json"))
        zip_contract = json.loads(archive.read(f"{PACKAGE}/diagnostics/supervisor_pid_map_fix_contract.json"))
    tree_ast = ast.parse(supervisor)
    declarations = [node for node in ast.walk(tree_ast) if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "known"]
    known_dict = len(declarations) == 1 and isinstance(declarations[0].value, ast.Dict)
    old_set = supervisor.replace("known: dict[int, int | None] = {}\n    remember(known, root_row)", "known: dict[int, int | None] = {process.pid}")
    old_declarations = [node for node in ast.walk(ast.parse(old_set)) if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "known"]
    historical_negative = len(old_declarations) == 1 and isinstance(old_declarations[0].value, ast.Set)
    required = ["evidence/SUPERVISOR_STDOUT.txt", "evidence/SUPERVISOR_STDERR.txt", "evidence/SUPERVISOR_EXECUTION.json", "source_package/supervisor_pid_map_fix_contract.json", "source_package/v69_formal_return_analysis.json", "source_package/v69_PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"]
    request_map = {row["archive"]: row for row in request["core_entries"]}
    zip_request_map = {row["archive"]: row for row in zip_request["core_entries"]}
    tokens = ['supervisor_stdout="$evidence_root/SUPERVISOR_STDOUT.txt"', 'supervisor_stderr="$evidence_root/SUPERVISOR_STDERR.txt"', 'supervisor_execution="$evidence_root/SUPERVISOR_EXECUTION.json"', '>"$supervisor_stdout" 2>"$supervisor_stderr" &', "qadd-supervisor-execution-v1", 'logs=[pathlib.Path(x) for x in sys.argv[10:13]]']
    checks = {
        "adapted_exact_tree_zip_supervisor": supervisor == zip_supervisor,
        "adapted_exact_tree_zip_runner": runner == zip_runner,
        "pid_map_is_dict": known_dict,
        "root_start_time_bound": 'remember(known, root_row)' in supervisor and 'simulator root identity unavailable immediately after Popen' in supervisor,
        "historical_set_negative_control": historical_negative,
        "supervisor_capture_tokens_tree": all(token in runner for token in tokens),
        "supervisor_capture_tokens_zip": all(token in zip_runner for token in tokens),
        "required_entries_tree": all(path in request_map and request_map[path].get("required") is True for path in required),
        "required_entries_zip": all(path in zip_request_map and zip_request_map[path].get("required") is True for path in required),
        "allowlist_tree": all(path in allow.get("required", []) and f"{PACKAGE}_return/{path}" in allow.get("required", []) for path in required),
        "allowlist_zip": all(path in zip_allow.get("required", []) and f"{PACKAGE}_return/{path}" in zip_allow.get("required", []) for path in required),
        "fix_contract_exact": contract == zip_contract and contract.get("pass") is True and contract.get("functional_delta") is False,
        "prior_v69_byte_frozen": prior_zip.stat().st_size == 108_735_727 and sha(prior_zip) == PRIOR_SHA,
        "no_functional_rtl": not (tree / "rtl").exists(),
    }
    facts = {"known_initializer": ast.unparse(declarations[0].value) if declarations else None, "runner_sha256": hashlib.sha256(runner.encode()).hexdigest(), "supervisor_sha256": hashlib.sha256(supervisor.encode()).hexdigest(), "required": required}
    return checks, facts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--base-output", type=Path)
    parser.add_argument("--adapted-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.base_output is None:
        args.base_output = args.output.with_name(args.output.stem + ".base.json")
    if args.adapted_output is None:
        args.adapted_output = args.output.with_name(args.output.stem + ".adapted.json")
    base_exit = adapted_v69(args)
    checks, facts = exact_checks(args.tree.resolve(), args.zip.resolve(), args.prior_zip.resolve())
    errors = [name for name, passed in checks.items() if not passed]
    if base_exit:
        errors.append("adapted_v69_exact_suite")
    result = {"schema": "qadd-v70-supervisor-pidmap-exact-validation-v1", "package_id": PACKAGE, "adapted_v69_suite": {"exit": base_exit, "report": args.adapted_output.as_posix()}, "checks": checks, "facts": facts, "package": {"path": args.zip.as_posix(), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)}, "prior_v69": {"path": args.prior_zip.as_posix(), "bytes": args.prior_zip.stat().st_size, "sha256": sha(args.prior_zip)}, "storage_manager_called": False, "server_actions_performed": [], "pass": not errors, "errors": errors, "claim_boundary": "Local exact package and recurrence controls only; no production target/4-2/terminal claim."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": result["pass"], "errors": errors}, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
