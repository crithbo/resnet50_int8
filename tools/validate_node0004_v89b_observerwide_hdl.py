#!/usr/bin/env python3
"""Exact-ZIP frontend/scope/state gate for the v89b observer."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v89b_obswide"
MEMBER = f"{PACKAGE}/tb_probe/observer_only_wide_causal.svh"


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
        source = data.decode("utf-8")
        contract = json.loads(archive.read(f"{PACKAGE}/contracts/observer_only_wide_causal_contract.json"))
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
    if "buf_idx_queue_bp_pre" in source:
        errors.append("retired_derived_ack_comparator_reintroduced")
    expected = [item["signal_id"] for item in contract["signals"]]
    missing = [signal_id for signal_id in expected if f"input wire" not in source or signal_id not in source]
    if missing:
        errors.append("catalog_signal_missing:" + ",".join(missing))
    if source.count("$fdisplay(codex_fd") != len(expected) + 1:
        errors.append("event_or_heartbeat_logger_cardinality")
    if "bind tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]" not in source:
        errors.append("exact_slice13_group1_mse4_scope_absent")
    if manifest.get("retired_buf_idx_queue_bp_pre_comparator_present") is not False:
        errors.append("manifest_retired_comparator_disposition")
    module_body = source.split("\nbind tb_NDP_Top_new_phy", 1)[0] + "\n"
    with tempfile.TemporaryDirectory(prefix="node0004-v89b-hdl-") as temporary:
        root = Path(temporary)
        positive = root / "positive.sv"
        typo = root / "negative_typo.sv"
        positive.write_text(module_body, encoding="utf-8", newline="\n")
        typo.write_text(module_body.replace("codex_seq = codex_seq + 1;", "codex_seq_typo = codex_seq + 1;", 1), encoding="utf-8", newline="\n")
        command = [str(args.iverilog), "-g2012", "-tnull", "-s", "codex_node0004_observerwide"]
        good = subprocess.run(command + [str(positive)], capture_output=True, text=True, timeout=30, check=False)
        bad = subprocess.run(command + [str(typo)], capture_output=True, text=True, timeout=30, check=False)
    if good.returncode != 0:
        errors.append("iverilog_exact_module_frontend_failed")
    if bad.returncode == 0:
        errors.append("undeclared_consumer_negative_not_rejected")
    report = {
        "schema": "node0004-v89b-observerwide-hdl-gate-v1", "package_id": PACKAGE,
        "pass": not errors, "errors": errors,
        "probe": {"member": MEMBER, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "frontend": {"tool": str(args.iverilog.resolve()), "positive_exit": good.returncode, "positive_stderr": good.stderr[-4096:], "negative_exit": bad.returncode},
        "scope": {"slice": 13, "group": 1, "mse": 4, "signal_count": len(expected)},
        "claim_boundary": "Exact-final-ZIP module-body frontend and exact bind/catalog closure; production VCS elaboration remains the dynamic proof boundary.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
