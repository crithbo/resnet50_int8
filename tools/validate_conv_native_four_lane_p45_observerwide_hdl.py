#!/usr/bin/env python3
"""Exact-ZIP frontend, scope, state, and negative controls for native p45."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


DEFAULT_PACKAGE = "r5_n4_0cc_p45_obswide"
MODULE = "codex_conv_native_observerwide"
HIERARCHY = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
    "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
)


def compile_source(tool: Path, source: str, root: Path, name: str) -> subprocess.CompletedProcess[str]:
    path = root / f"{name}.sv"
    path.write_text(source, encoding="utf-8", newline="\n")
    return subprocess.run(
        [str(tool), "-g2012", "-tnull", "-s", MODULE, str(path)],
        capture_output=True, text=True, timeout=30, check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--package-id", default=DEFAULT_PACKAGE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package_id = args.package_id
    member = f"{package_id}/tb_probe/observer_only_wide_causal.svh"
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as archive:
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if roots != {package_id} or archive.testzip() is not None:
            errors.append("zip_identity_or_crc")
        data = archive.read(member)
        source = data.decode("utf-8")
        contract = json.loads(archive.read(f"{package_id}/contracts/observer_only_wide_causal_contract.json"))
        manifest = json.loads(archive.read(f"{package_id}/package_manifest.json"))
        predicate = json.loads(archive.read(f"{package_id}/diagnostics/vector_handshake_predicate.json"))
    signals = contract.get("signals", [])
    signal_ids = [row.get("signal_id") for row in signals]
    missing = [signal_id for signal_id in signal_ids if not isinstance(signal_id, str) or signal_id not in source]
    if missing:
        errors.append("catalog_signal_missing:" + ",".join(map(str, missing)))
    if source.count("$fdisplay(codex_fd") != len(signal_ids) + 1:
        errors.append("event_or_heartbeat_logger_cardinality")
    if f"bind {HIERARCHY} {MODULE}" not in source:
        errors.append("exact_slice0_group0_mse4_scope_absent")
    if any(token in source.lower() for token in ("$fsdbdump", "$vcdplus", "$dumpfile", "$dumpvars")):
        errors.append("waveform_writer_reintroduced")
    if not all(token in source for token in ("$fflush(codex_fd)", "$fclose(codex_fd)", "final if (codex_enabled && codex_fd)")):
        errors.append("close_flush_state_machine_incomplete")
    if predicate.get("expression") != "(|(mse2mem_wdata_valid & mem2mse_wdata_ready)) === 1'b1":
        errors.append("p42_vector_predicate_drift")
    files = manifest.get("files", {})
    declared = files.get("tb_probe/observer_only_wide_causal.svh", {}) if isinstance(files, dict) else {}
    if declared != {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}:
        errors.append("manifest_observer_identity_mismatch")
    module_body = source.split("\nbind tb_NDP_Top_new_phy", 1)[0] + "\n"
    with tempfile.TemporaryDirectory(prefix="native-p45-observer-hdl-") as temporary:
        root = Path(temporary)
        good = compile_source(args.iverilog, module_body, root, "positive")
        typo = compile_source(
            args.iverilog,
            module_body.replace("codex_seq = codex_seq + 1;", "codex_seq_typo = codex_seq + 1;", 1),
            root, "negative_consumer_typo",
        )
        reserved = compile_source(
            args.iverilog,
            module_body.replace("integer codex_enabled;", "integer sequence;", 1),
            root, "negative_reserved_identifier",
        )
        missing_decl = compile_source(
            args.iverilog,
            module_body.replace("  integer codex_enabled;\n", "", 1),
            root, "negative_missing_declaration",
        )
    if good.returncode != 0:
        errors.append("iverilog_exact_module_frontend_failed")
    if typo.returncode == 0:
        errors.append("undeclared_consumer_negative_not_rejected")
    if reserved.returncode == 0:
        errors.append("reserved_identifier_negative_not_rejected")
    if missing_decl.returncode == 0:
        errors.append("missing_declaration_negative_not_rejected")
    state_controls = {
        "initial_state_present": all(token in source for token in ("codex_seq = 0;", "codex_clock_count = 0;", "codex_have_previous = 0;")),
        "transition_state_updated": all(f"prev_{signal_id} = {signal_id};" in source for signal_id in signal_ids),
        "ordered_four_state_comparison": all(f"{signal_id} !== prev_{signal_id}" in source for signal_id in signal_ids),
        "unbounded_no_sampling": contract.get("event_recording", {}).get("event_cap") is None and contract.get("event_recording", {}).get("sampling") is False,
        "scope_mutation_rejected": f"bind {HIERARCHY.replace('[0]', '[1]', 1)} {MODULE}" not in source,
    }
    if not all(state_controls.values()):
        errors.extend(key for key, passed in state_controls.items() if not passed)
    report = {
        "schema": "conv-native-p45-observerwide-hdl-gate-v1",
        "package_id": package_id,
        "pass": not errors,
        "errors": errors,
        "probe": {"member": member, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "frontend": {
            "tool": str(args.iverilog.resolve()),
            "positive_exit": good.returncode,
            "positive_stderr": good.stderr[-4096:],
            "consumer_typo_exit": typo.returncode,
            "reserved_identifier_exit": reserved.returncode,
            "missing_declaration_exit": missing_decl.returncode,
        },
        "scope": {"slice": 0, "group": 0, "mse": 4, "exact_hierarchy": HIERARCHY, "signal_count": len(signal_ids)},
        "state_controls": state_controls,
        "claim_boundary": "Exact-final-ZIP package-local HDL frontend/scope/state controls; production VCS elaboration and DUT results remain unclaimed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
