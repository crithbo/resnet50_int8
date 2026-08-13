#!/usr/bin/env python3
"""Exact-final-ZIP lexical guard for package-owned SystemVerilog probes.

This deliberately does not claim to replace production VCS. It closes the
observed s1 class: a reserved SystemVerilog keyword used as a declared probe
identifier. A built-in negative control proves that `integer sequence;` is
rejected by the same gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


SV_KEYWORDS = frozenset(
    "accept_on alias always always_comb always_ff always_latch and assert assign assume automatic before begin bind bins binsof bit break buf bufif0 bufif1 byte case casex casez cell chandle checker class clocking cmos config const constraint context continue cover covergroup coverpoint cross deassign default defparam design disable dist do edge else end endchecker endclass endclocking endconfig endfunction endgenerate endgroup endinterface endmodule endpackage endprimitive endprogram endproperty endspecify endsequence endtable endtask enum event eventually expect export extends extern final first_match for force foreach forever fork forkjoin function generate genvar global highz0 highz1 if iff ifnone ignore_bins illegal_bins implements implies import incdir include initial inout input inside instance int integer interconnect interface intersect join join_any join_none large let liblist library local localparam logic longint macromodule matches medium modport module nand negedge nettype new nexttime nmos nor noshowcancelled not notif0 notif1 null or output package packed parameter pmos posedge primitive priority program property protected pull0 pull1 pulldown pullup pulsestyle_ondetect pulsestyle_onevent pure rand randc randcase randsequence rcmos real realtime ref reg reject_on release repeat restrict return rnmos rpmos rtran rtranif0 rtranif1 s_always s_eventually s_nexttime s_until s_until_with scalared sequence shortint shortreal showcancelled signed small solve specify specparam static string strong strong0 strong1 struct super supply0 supply1 sync_accept_on sync_reject_on table tagged task this throughout time timeprecision timeunit tran tranif0 tranif1 tri tri0 tri1 triand trior trireg type typedef union unique unique0 unsigned use uwire var vectored virtual void wait wait_order wand weak weak0 weak1 while wildcard wire with within wor xnor xor".split()
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def declared_identifiers(source: str) -> list[str]:
    # Strip comments and strings so the required log key `sequence=` remains
    # legal and invisible to the declaration check.
    clean = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    clean = re.sub(r"//[^\n]*", " ", clean)
    clean = re.sub(r'"(?:\\.|[^"\\])*"', '""', clean)
    result: list[str] = []
    declaration = re.compile(
        r"\b(?:integer|int|logic|bit|reg|wire|string|time|byte|shortint|longint)\b\s+(?:signed\s+|unsigned\s+)?(?:\[[^\]]+\]\s*)?([A-Za-z_$][A-Za-z0-9_$]*)"
    )
    result.extend(match.group(1) for match in declaration.finditer(clean))
    return result


def violations(source: str) -> list[str]:
    return sorted({token for token in declared_identifiers(source) if token in SV_KEYWORDS})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    member = f"{args.package_id}/tb_probe/fsdb_smoke_event_probe.svh"
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as archive:
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if archive.testzip() is not None:
            errors.append("zip_crc")
        if roots != {args.package_id}:
            errors.append("single_root_identity")
        source_bytes = archive.read(member)
        manifest = json.loads(archive.read(f"{args.package_id}/package_manifest.json"))
    source = source_bytes.decode("utf-8")
    actual_violations = violations(source)
    if actual_violations:
        errors.append("reserved_declared_identifiers:" + ",".join(actual_violations))
    if "integer event_seq_id;" not in source or "integer sequence;" in source:
        errors.append("expected_identifier_repair_absent")
    if "CODEX_FSDB_SMOKE_EVENT_V1 sequence=%0d" not in source:
        errors.append("registered_log_field_changed")
    rows = {row.get("path"): row for row in manifest.get("files", [])}
    row = rows.get("tb_probe/fsdb_smoke_event_probe.svh", {})
    if row.get("bytes") != len(source_bytes) or row.get("sha256") != digest(source_bytes):
        errors.append("manifest_probe_identity_mismatch")
    negative_source = source.replace("integer event_seq_id;", "integer sequence;", 1)
    negative_hits = violations(negative_source)
    if "sequence" not in negative_hits:
        errors.append("negative_control_not_rejected")
    # Icarus does not support this package's final bind statement. Compile the
    # exact probe module body, while the lexical checks above retain and verify
    # the exact bind-bearing ZIP member.
    module_body = re.sub(r"^bind\s+tb_NDP_Top_new_phy.*?;\s*$", "", source, flags=re.M)
    negative_body = re.sub(r"^bind\s+tb_NDP_Top_new_phy.*?;\s*$", "", negative_source, flags=re.M)
    with tempfile.TemporaryDirectory(prefix="node0004-fsdb-probe-sv-") as temp:
        root = Path(temp)
        positive_path = root / "probe_positive.sv"
        negative_path = root / "probe_negative.sv"
        positive_path.write_text(module_body, encoding="utf-8", newline="\n")
        negative_path.write_text(negative_body, encoding="utf-8", newline="\n")
        positive_compile = subprocess.run(
            [str(args.iverilog), "-g2012", "-tnull", "-s", "codex_fsdb_smoke_event_probe", str(positive_path)],
            text=True, capture_output=True, timeout=30, check=False,
        )
        negative_compile = subprocess.run(
            [str(args.iverilog), "-g2012", "-tnull", "-s", "codex_fsdb_smoke_event_probe", str(negative_path)],
            text=True, capture_output=True, timeout=30, check=False,
        )
    if positive_compile.returncode != 0:
        errors.append("iverilog_module_body_parse_failed")
    if negative_compile.returncode == 0 or "probe_negative.sv:3" not in negative_compile.stderr:
        errors.append("iverilog_negative_control_not_rejected_at_line3")
    report = {
        "schema": "node0004-fsdb-smoke-probe-sv-lexical-gate-v1",
        "package_id": args.package_id,
        "pass": not errors,
        "errors": errors,
        "probe": {"member": member, "bytes": len(source_bytes), "sha256": digest(source_bytes)},
        "declared_identifiers": declared_identifiers(source),
        "reserved_identifier_violations": actual_violations,
        "negative_control": {"mutation": "integer event_seq_id; -> integer sequence;", "rejected": "sequence" in negative_hits, "violations": negative_hits},
        "module_body_parser": {
            "tool": str(args.iverilog.resolve()),
            "positive_exit": positive_compile.returncode,
            "positive_stderr": positive_compile.stderr[-4096:],
            "negative_exit": negative_compile.returncode,
            "negative_stderr": negative_compile.stderr[-4096:],
            "bind_statement_handling": "Exact bind-bearing member checked lexically; unsupported bind statement removed only for the Icarus module-body parse control.",
        },
        "claim_boundary": "Exact-final-ZIP lexical guard plus Icarus parse of the exact package-owned probe module body; not a substitute for production VCS parsing/elaboration of the bind-bearing full design.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "errors": errors, "output": args.output.as_posix()}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
