#!/usr/bin/env python3
"""Build the v64 QAdd TB-VCD package after the mandatory failure-rule audit."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = ROOT / "tools/build_qlinearadd_node0007_v63_tb_vcd.py"
OLD = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
NEW = "r5_qadd_n7_tailround_lanephase_v64_tbvcdfix"
OUT = ROOT / "outputs/qlinearadd_node0007_v64_tb_vcd_fix_release"
AUDIT = (
    ROOT
    / "outputs/qlinearadd_node0007_v63_return_r1786698111383862725_2250595"
    / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
)


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("qadd_v63_builder_base", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import v63 builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def signals_from_v63(source_tree: Path) -> list[dict[str, Any]]:
    catalog = json.loads(
        (source_tree / "diagnostics/tb_vcd_signal_catalog.json").read_text(encoding="utf-8")
    )
    signals = catalog.get("signals")
    if not isinstance(signals, list) or len(signals) != 64:
        raise RuntimeError("v63 source-bound 64-signal catalog is absent")
    return signals


def exact_signal_tb(base: Any, signals: list[dict[str, Any]]) -> str:
    text = base._v63_make_tb_source(signals)
    text = text.replace("QAdd v63", "QAdd v64").replace(
        "codex_qadd_tb_vcd_causal_cone_v63", "codex_qadd_tb_vcd_causal_cone_v64"
    )
    first = text.index("      $dumpvars(0, ")
    last = text.index("      $dumpon;", first)
    dump_rows = "\n".join(
        f"      $dumpvars(0, {item['exact_hierarchy']});" for item in signals
    )
    text = text[:first] + dump_rows + "\n" + text[last:]
    text = text.replace(
        "  longint unsigned tbvcd_sim_time_ps;", "  time tbvcd_sim_time_ps;"
    )
    text = text.replace(
        "(tbvcd_owner_cycles & 64'h3ffff) == 0",
        "(tbvcd_owner_cycles & 64'h3fff) == 0",
    )
    text = text.replace(
        "tbvcd_sim_time_ps = $rtoi($realtime * 1000.0);",
        "tbvcd_sim_time_ps = $time;",
    )
    return text


def fixed_runner(base_runner: str) -> str:
    runner = base_runner
    compile_success = '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; core evidence will return"\n'
    compile_state = compile_success + r'''cat >"$bootstrap_root/compile_downstream_state.json" <<'EOF'
{"schema":"server-compile-downstream-state-v1","compile_succeeded":true,"simulation_started":false,"sim_log":"not-started-after-successful-compile","formal_D":"not-produced-before-simulation"}
EOF
cp -- "$bootstrap_root/compile_downstream_state.json" "$evidence_root/compile_downstream_state.json"
'''
    if runner.count(compile_success) != 1:
        raise RuntimeError("compile-success insertion point drifted")
    runner = runner.replace(compile_success, compile_state)
    simulation_start = "simulation_started=true\nprintf 'RUNTIME_LAYOUT_SIMULATION_START\\n' >\"$evidence_root/simulation_started.marker\"\n"
    simulation_state = simulation_start + r'''cat >"$bootstrap_root/compile_downstream_state.json" <<'EOF'
{"schema":"server-compile-downstream-state-v1","compile_succeeded":true,"simulation_started":true,"sim_log":"attempt-owned-complete-log","formal_D":"pending-natural-simulation"}
EOF
cp -- "$bootstrap_root/compile_downstream_state.json" "$evidence_root/compile_downstream_state.json"
'''
    if runner.count(simulation_start) != 1:
        raise RuntimeError("simulation-start insertion point drifted")
    runner = runner.replace(simulation_start, simulation_state)

    invocation = '"$evidence_root/compile_first_error.txt" <<\'PY\''
    if runner.count(invocation) != 1:
        raise RuntimeError("native failure receipt invocation drifted")
    runner = runner.replace(invocation, '"$evidence_root/compile_first_error.txt" "$process_receipt" <<\'PY\'')
    setup = "a=json.loads(actual.read_text()) if actual.is_file() else {};error=first.read_text(errors='replace').strip() if ce and first.is_file() else ''"
    replacement = setup + ";proc=pathlib.Path(sys.argv[13]);p=json.loads(proc.read_text()) if proc.is_file() else {}"
    if runner.count(setup) != 1:
        raise RuntimeError("native failure receipt setup drifted")
    runner = runner.replace(setup, replacement)
    broad = "re.search(r'(?i)error|fatal|timeout|terminated',line)"
    narrow = "re.search(r'(?i)(?:Error-\\[|^Error:|fatal|timeout|terminated|RUNNER_ERROR)',line)"
    if runner.count(broad) != 1:
        raise RuntimeError("first-error regex drifted")
    runner = runner.replace(broad, narrow)
    marker = "        if error: break\nreceipts=[]"
    structured = "        if error: break\nif not error and p.get('stop_reason') not in (None,'PROCESS_EXIT'):\n    error='SUPERVISOR_STOP:'+str(p.get('stop_reason'))\nreceipts=[]"
    if runner.count(marker) != 1:
        raise RuntimeError("structured supervisor error insertion drifted")
    return runner.replace(marker, structured)


def repair_path_budget(base: Any, tree: Path) -> None:
    manifest_path = tree / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = manifest["path_length_budget"]
    longest = budget["longest_projected_relative_path"]
    budget["longest_projected_relative_path_chars"] = len(longest)
    budget["max_projected_absolute_path_chars"] = (
        budget["declared_target_root_max_chars"] + 1 + len(longest)
    )
    base.write_json(manifest_path, manifest)
    layout_path = tree / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout_budget = layout["path_budget"]
    layout_budget["max_projected_absolute_path_chars"] = (
        layout_budget["declared_target_root_max_chars"] + 1 + len(longest)
    )
    base.write_json(layout_path, layout)


def main() -> int:
    if not AUDIT.is_file():
        raise RuntimeError("PACKAGE_BUILD_FAILURE_RULE_AUDIT must exist before v64 build")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("status") != "AUDIT_SUBMITTED_BEFORE_THIRD_ATTEMPT_BUILD":
        raise RuntimeError("failure-rule audit is not active")

    base = load_base()
    base._v63_make_tb_source = base.make_tb_source
    base.OLD = OLD
    base.NEW = NEW
    base.EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437+qadd-failure-delta-v1"
    base.SOURCE_ZIP = base.STORAGE / "pending" / f"{OLD}.zip"
    base.OUT = OUT
    base.BUILD = OUT / "build"
    base.TREE = base.BUILD / NEW
    base.ZIP = base.BUILD / f"{NEW}.zip"
    base.signal_contract = signals_from_v63
    base.make_tb_source = lambda signals: exact_signal_tb(base, signals)
    base.RUNNER = fixed_runner(base.RUNNER)
    original_post_request = base.post_request

    def post_request() -> dict[str, Any]:
        request = original_post_request()
        request["core_entries"].append(
            {
                "source_root": "attempt",
                "source": "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json",
                "archive": "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json",
                "required": True,
            }
        )
        return request

    base.post_request = post_request
    result = base.main()

    tree = base.TREE
    stale_provenance = tree / "provenance/v62_to_v63_tb_vcd.json"
    if stale_provenance.exists():
        stale_provenance.unlink()
    base.write_json(
        tree / "provenance/v63_to_v64_tb_vcd_failure_fix.json",
        {
            "schema": "qadd-v63-to-v64-tb-vcd-failure-fix-v1",
            "package_id": NEW,
            "previous_version_progress": "v57h localized the DUT boundary after Buffer5 request decode and before selected ping-pong required-lane read accept. v63 compiled and started simulation but a package-local false freeze stopped slice16 preload before the target executed.",
            "current_version_purpose": "Preserve v63 configuration, identity repair, tail-round target, 41-role/64-signal cone and both ping-pong branches while repairing exact-signal dumping, real-VCD-time supervision, multiline parsing, process/return conjunction and structured failure receipts.",
            "changed_surface": ["fresh identity", "package-local TB", "runtime supervisor", "VCD parser", "return receipts", "family hard gates"],
            "frozen_surface": ["configuration", "numeric", "workload", "golden", "functional RTL", "tail-round target", "ping-pong behavior"],
            "server_action": False,
        },
    )
    (tree / "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json").write_bytes(AUDIT.read_bytes())
    signals = json.loads((tree / "diagnostics/tb_vcd_signal_catalog.json").read_text(encoding="utf-8"))["signals"]
    base.write_json(
        tree / "diagnostics/tb_vcd_exact_dump_plan.json",
        {
            "schema": "qadd-tb-vcd-exact-dump-plan-v1",
            "package_id": NEW,
            "strategy": "EXPLICIT_SOURCE_BOUND_SIGNAL_ONLY",
            "signal_count": len(signals),
            "signal_ids": [item["signal_id"] for item in signals],
            "exact_hierarchies": [item["exact_hierarchy"] for item in signals],
            "module_scope_dump_forbidden": True,
            "uncataloged_signal_forbidden": True,
            "pass": True,
        },
    )
    selector_path = tree / "contracts/server_diagnostic_mode_selector.json"
    selector = json.loads(selector_path.read_text(encoding="utf-8"))
    exact_receipt = "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json"
    if exact_receipt not in selector["return_members"]:
        selector["return_members"].append(exact_receipt)
    selector["return_members"] = sorted(selector["return_members"])
    selector["package_members"] = sorted(
        {path.relative_to(tree).as_posix() for path in tree.rglob("*") if path.is_file()}
        | {"contracts/server_diagnostic_mode_selector.json", "TEST_PACKAGE_MANIFEST.json"}
    )
    base.write_json(selector_path, selector)
    allowlist_path = tree / "RETURN_ALLOWLIST.json"
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    if exact_receipt not in allowlist["required"]:
        allowlist["required"].append(exact_receipt)
    allowlist["required"] = sorted(allowlist["required"])
    base.write_json(allowlist_path, allowlist)
    repair_path_budget(base, tree)
    manifest_path = tree / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_FAILURE_DELTA_GATES"
    manifest["package_build_failure_rule_audit"] = "provenance/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"
    manifest["files"] = base.files_map(tree)
    base.write_json(manifest_path, manifest)
    base.deterministic_zip(tree, base.ZIP)
    recheck = base.zip_recheck(tree, base.ZIP)
    base.ZIP.with_name(base.ZIP.name + ".sha256").write_text(
        f"{base.digest(base.ZIP)}  {base.ZIP.name}\n", encoding="ascii", newline="\n"
    )
    receipt_path = base.BUILD / "build_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update(
        {
            "schema": "qadd-v64-tb-vcd-failure-fix-build-v1",
            "package_id": NEW,
            "source_v63_pending": base.identity(base.SOURCE_ZIP),
            "zip": base.identity(base.ZIP),
            "exact_final_zip_recheck": recheck,
            "package_build_failure_rule_audit": base.identity(AUDIT),
            "server_action": False,
            "pass": True,
        }
    )
    base.write_json(receipt_path, receipt)
    print(json.dumps({"package_id": NEW, "zip": base.ZIP.relative_to(ROOT).as_posix(), "pass": True}, sort_keys=True))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
