#!/usr/bin/env python3
"""Exact-final-ZIP frontend/scope/state gate for QAdd v61 observer-only HDL."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_qadd_n7_tailround_lanephase_v61_obswide"
MEMBER = f"{PACKAGE}/tb_probe/qadd_observer_wide_impl.svh"
CONTRACT = f"{PACKAGE}/contracts/server_observer_only_wide_causal_contract.json"
MANIFEST = f"{PACKAGE}/TEST_PACKAGE_MANIFEST.json"
TARGET = "BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"


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
        manifest = json.loads(archive.read(MANIFEST))

    expected = [item["signal_id"] for item in contract["signals"]]
    missing_ports = [sid for sid in expected if not re.search(rf"\binput\s+wire\b[^;\n]*\b{re.escape(sid)}\b", source)]
    missing_state = [sid for sid in expected if f"prev_{sid}" not in source or f"prev_{sid} = {sid};" not in source]
    missing_binding = [sid for sid in expected if f".{sid}(" not in source]
    if missing_ports:
        errors.append("catalog_ports_missing:" + ",".join(missing_ports))
    if missing_state:
        errors.append("transition_state_missing:" + ",".join(missing_state))
    if missing_binding:
        errors.append("exact_binding_missing:" + ",".join(missing_binding))
    if source.count("$fdisplay(qow_fd") != len(expected) + 1:
        errors.append("event_or_heartbeat_logger_cardinality")
    if TARGET not in source:
        errors.append("exact_buffer5_scope_absent")
    for required in ("sem2iga_exec_start", "slice_cmpt_finish", "valid_buf", "buf2mrm_rreq_bank_ready", "buf2arm_rreq_bank_ready", "buf2mrm_rvalid", "buf2mrm_rdata"):
        if required not in source:
            errors.append(f"causal_chain_signal_absent:{required}")
    if re.search(r"\$dump(?:file|vars|all|on|off)|\$fsdb|dump\s+-file", source, re.I):
        errors.append("binary_dump_writer_present")
    if any(item.get("derived_expected_equation") is not False or item.get("observer_drives_dut") is not False for item in contract["signals"]):
        errors.append("observer_not_actual_read_only")
    if manifest.get("functional_rtl_modified") is not False:
        errors.append("functional_rtl_freeze_missing")

    with tempfile.TemporaryDirectory(prefix="qadd-v61-observer-hdl-") as temporary:
        root = Path(temporary)
        positive = root / "positive.sv"
        typo = root / "negative_undeclared.sv"
        positive.write_text(source, encoding="utf-8", newline="\n")
        typo.write_text(source.replace("qow_seq = qow_seq + 1;", "qow_seq_typo = qow_seq + 1;", 1), encoding="utf-8", newline="\n")
        command = [str(args.iverilog), "-g2012", "-DCODEX_QADD_OBSERVER_FOCUS", "-tnull", "-s", "codex_qadd_observer_wide_v61"]
        good = subprocess.run(command + [str(positive)], capture_output=True, text=True, timeout=60, check=False)
        bad = subprocess.run(command + [str(typo)], capture_output=True, text=True, timeout=60, check=False)
    if good.returncode != 0:
        errors.append("iverilog_exact_module_frontend_failed")
    if bad.returncode == 0:
        errors.append("undeclared_state_negative_not_rejected")

    report = {
        "schema": "qadd-node0007-v61-observerwide-hdl-gate-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "probe": {"member": MEMBER, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "frontend": {
            "tool": str(args.iverilog.resolve()),
            "positive_exit": good.returncode,
            "positive_stderr": good.stderr[-4096:],
            "undeclared_state_negative_exit": bad.returncode,
        },
        "scope_state": {
            "slice": 0,
            "buffer": 5,
            "signal_count": len(expected),
            "actual_net_only": True,
            "read_only": True,
            "transition_state_per_signal": True,
        },
        "claim_boundary": "Exact-final-ZIP module frontend and Buffer5 bind/catalog/state closure; production VCS elaboration remains the dynamic proof boundary.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
