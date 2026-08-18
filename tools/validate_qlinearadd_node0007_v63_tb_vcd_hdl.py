#!/usr/bin/env python3
"""Exact-final-ZIP frontend/scope/state gate for QAdd v63 TB VCD HDL."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
MEMBER = f"{PACKAGE}/tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh"
CONTRACT = f"{PACKAGE}/contracts/server_tb_vcd_bounded_causal_cone_contract.json"
TARGET = "BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"


def focused_source(source: str) -> str:
    """Keep the exact module while replacing only unresolved DUT dump scopes."""
    module = source.split("\nbind tb_NDP_Top_new_phy ", 1)[0] + "\n"
    module = re.sub(r"\$dumpvars\(0,\s*[^;]+\);", "$dumpvars;", module)
    return module


def static_checks(source: str, contract: dict) -> dict[str, bool]:
    signals = contract.get("signals", [])
    ids = [row.get("signal_id") for row in signals]
    bound_ids = set(re.findall(r"\.([A-Za-z_][A-Za-z0-9_]*)\(", source))
    buffer_prefix = next(row["exact_hierarchy"].rsplit(".", 1)[0] for row in signals if row.get("signal_id") == "sig_valid_buf")
    all_covered = all(row.get("signal_id") in bound_ids or str(row.get("exact_hierarchy", "")).startswith(buffer_prefix + ".") for row in signals)
    exact_dump = f"$dumpvars(0, {buffer_prefix});"
    return {
        "single_exact_module": source.count("module codex_qadd_tb_vcd_causal_cone_v63(") == 1,
        "all_bound_signal_ports": all(re.search(rf"\binput\s+wire\b[^;\n]*\b{re.escape(str(sid))}\b", source) for sid in bound_ids if sid.startswith("sig_")),
        "all_contract_signals_dump_covered": all_covered,
        "buffer5_depth0_dump": exact_dump in source and TARGET in exact_dump,
        "standard_tasks_complete": all(token in source for token in ("$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush")),
        "strict_plateau_intersection": all(token in source for token in (
            "$time > tbvcd_last_sim_time", "tbvcd_state_current === tbvcd_state_previous",
            "tbvcd_counter_current === tbvcd_counter_previous",
            "sig_global_cycle === tbvcd_global_cycle_previous",
            "sig_global_start_count === tbvcd_global_start_count_previous",
            "!$isunknown(tbvcd_state_current)",
        )),
        "exact_thresholds": all(token in source for token in ("64'd1048576", "64'd4194304", "64'd262144")),
        "read_only": not re.search(r"\b(?:assign|force)\s+sig_|\bsig_[A-Za-z0-9_]+\s*(?:<=|=(?!=))", source),
        "actual_source_only": all(row.get("source_binding") == "ACTUAL_SOURCE_NET" and row.get("derived_expected_equation") is False and row.get("drives_dut") is False for row in signals),
        "all_41_roles": len(contract.get("role_coverage", [])) == 41,
        "all_four_layers": {row.get("layer") for row in contract.get("boundaries", [])} == {"FIRST_DIVERGENCE_UPSTREAM_ONE", "FIRST_DIVERGENCE_CURRENT", "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "STATE_HOLD_CLEAR"},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as archive:
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if roots != {PACKAGE} or archive.testzip() is not None:
            errors.append("zip_identity_or_crc")
        data = archive.read(MEMBER)
        source = data.decode("utf-8", errors="strict")
        contract = json.loads(archive.read(CONTRACT))

    checks = static_checks(source, contract)
    errors.extend(name for name, passed in checks.items() if not passed)
    focus = focused_source(source)
    with tempfile.TemporaryDirectory(prefix="qadd-v63-tbvcd-hdl-") as temporary:
        root = Path(temporary)
        positive = root / "positive.sv"
        syntax_negative = root / "syntax_negative.sv"
        positive.write_text(focus, encoding="utf-8", newline="\n")
        syntax_negative.write_text(focus.replace("tbvcd_owner_cycles = 0;", "tbvcd_owner_cycles = ;", 1), encoding="utf-8", newline="\n")
        command = [str(args.iverilog), "-g2012", "-tnull", "-s", "codex_qadd_tb_vcd_causal_cone_v63"]
        good = subprocess.run(command + [str(positive)], capture_output=True, text=True, timeout=60, check=False)
        bad = subprocess.run(command + [str(syntax_negative)], capture_output=True, text=True, timeout=60, check=False)
    if good.returncode != 0:
        errors.append("iverilog_exact_module_frontend_failed")
    if bad.returncode == 0:
        errors.append("syntax_negative_not_rejected")

    scope_negative = static_checks(source.replace("$dumpvars(0, tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer);", "$dumpvars(0, tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[4].u_Buffer_Manager.u_Buffer);", 1), contract)
    state_negative = static_checks(source.replace("(sig_global_cycle === tbvcd_global_cycle_previous) &&", "1'b1 &&", 1), contract)
    controls = {
        "positive_frontend": good.returncode == 0,
        "syntax_negative_rejected": bad.returncode != 0,
        "wrong_scope_negative_rejected": scope_negative["buffer5_depth0_dump"] is False,
        "missing_global_witness_negative_rejected": state_negative["strict_plateau_intersection"] is False,
    }
    if not all(controls.values()):
        errors.append("negative_control_failure")
    report = {
        "schema": "qadd-node0007-v63-tb-vcd-hdl-gate-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "probe": {"member": MEMBER, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "frontend": {"tool": str(args.iverilog.resolve()), "positive_exit": good.returncode, "positive_stderr": good.stderr[-4096:], "syntax_negative_exit": bad.returncode},
        "scope_state": {"slice": 0, "buffer": 5, "signal_count": len(contract.get("signals", [])), "role_count": len(contract.get("role_coverage", [])), "actual_net_only": True, "read_only": True, "checks": checks},
        "negative_controls": controls,
        "claim_boundary": "Exact-final-ZIP focused module frontend plus static source-bound Buffer5 bind, depth-0 dump and plateau-state closure; production VCS compile/elaboration remains the dynamic proof boundary.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
