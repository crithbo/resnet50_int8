#!/usr/bin/env python3
"""Exact-final-ZIP frontend/scope/state controls for the p44 FSDB event probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_0cc_p44_fsdbvq"
MEMBER = f"{PACKAGE}/tb_probe/native_fsdb_event_probe.svh"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compile_source(iverilog: Path, source: str, root: Path, name: str) -> subprocess.CompletedProcess[str]:
    path = root / f"{name}.sv"
    path.write_text(source, encoding="utf-8", newline="\n")
    return subprocess.run(
        [str(iverilog), "-g2012", "-tnull", "-s", "codex_native_fsdb_event_probe", str(path)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


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
        source_bytes = archive.read(MEMBER)
        manifest = json.loads(archive.read(f"{PACKAGE}/package_manifest.json"))
        profile = json.loads(archive.read(f"{PACKAGE}/contracts/native_fsdb_query_profile.json"))
        source_report = json.loads(archive.read(f"{PACKAGE}/diagnostics/native_fsdb_query_source_report.json"))
    source = source_bytes.decode("utf-8")
    module_body = source.split("\nbind Memory_WR_Stream_Engine", 1)[0] + "\n"
    expected_tokens = (
        "integer event_seq_id;",
        "event_seq_id = 0;",
        "event_seq_id = event_seq_id + 1;",
        "always @(mse_mem_ag_tag_valid",
        "$test$plusargs(\"CODEX_NATIVE_FSDB_QUERY\")",
        "CODEX_NATIVE_FSDB_SUMMARY_V1",
        "bind Memory_WR_Stream_Engine",
        "u_codex_native_fsdb_event_probe",
    )
    missing_tokens = [token for token in expected_tokens if token not in source]
    if missing_tokens:
        errors.append("semantic_closure_missing:" + ",".join(missing_tokens))
    if "integer sequence;" in source:
        errors.append("reserved_sequence_declaration_present")
    if source.count("event_seq_id = event_seq_id + 1;") != len(profile["candidates"]):
        errors.append("producer_consumer_increment_closure")
    if profile.get("exact_probe_instance") != source_report.get("exact_probe_instance"):
        errors.append("scope_identity_drift")
    parent = source_report.get("exact_parent_instance", "")
    if profile.get("exact_probe_instance") != parent + ".u_codex_native_fsdb_event_probe":
        errors.append("bind_instance_scope_mismatch")
    candidate_ids = [row["candidate_id"] for row in profile["candidates"]]
    if candidate_ids != [row["candidate_id"] for row in source_report["candidate_exact_set"]]:
        errors.append("candidate_exact_set_drift")
    files = manifest.get("files", {})
    row = files.get("tb_probe/native_fsdb_event_probe.svh", {}) if isinstance(files, dict) else {}
    if row.get("size_bytes") != len(source_bytes) or row.get("sha256") != digest(source_bytes):
        errors.append("manifest_probe_identity_mismatch")

    with tempfile.TemporaryDirectory(prefix="native-p44-hdl-") as temporary:
        root = Path(temporary)
        positive = compile_source(args.iverilog, module_body, root, "positive")
        reserved = compile_source(
            args.iverilog,
            module_body.replace("integer event_seq_id;", "integer sequence;", 1),
            root,
            "negative_reserved",
        )
        deleted = compile_source(
            args.iverilog,
            module_body.replace("  integer event_seq_id;\n", "", 1),
            root,
            "negative_deleted_declaration",
        )
        typo = compile_source(
            args.iverilog,
            module_body.replace("event_seq_id = event_seq_id + 1;", "event_seq_typo = event_seq_id + 1;", 1),
            root,
            "negative_consumer_typo",
        )
    if positive.returncode != 0:
        errors.append("iverilog_exact_module_body_frontend_failed")
    if reserved.returncode == 0:
        errors.append("reserved_keyword_negative_not_rejected")
    if deleted.returncode == 0:
        errors.append("declaration_delete_negative_not_rejected")
    if typo.returncode == 0:
        errors.append("consumer_typo_negative_not_rejected")
    state_negatives = {
        "delete_initialization_rejected": "event_seq_id = 0;" not in source.replace("event_seq_id = 0;", "", 1),
        "delete_increment_rejected": source.replace("event_seq_id = event_seq_id + 1;", "", 1).count("event_seq_id = event_seq_id + 1;") != len(profile["candidates"]),
        "scope_profile_drift_rejected": (profile["exact_probe_instance"] + ".wrong") != source_report["exact_probe_instance"],
    }
    if not all(state_negatives.values()):
        errors.append("state_or_scope_negative_control_failed")
    report = {
        "schema": "conv-native-p44-package-local-hdl-full-gate-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "probe": {"member": MEMBER, "bytes": len(source_bytes), "sha256": digest(source_bytes)},
        "frontend": {
            "tool": str(args.iverilog.resolve()),
            "positive_exit": positive.returncode,
            "positive_stderr": positive.stderr[-4096:],
        },
        "negative_controls": {
            "reserved_keyword_exit": reserved.returncode,
            "declaration_delete_exit": deleted.returncode,
            "consumer_typo_exit": typo.returncode,
            **state_negatives,
        },
        "scope": {
            "bind_module": "Memory_WR_Stream_Engine",
            "exact_parent_instance": parent,
            "exact_probe_instance": profile.get("exact_probe_instance"),
            "candidate_ids": candidate_ids,
        },
        "claim_boundary": (
            "Exact-final-ZIP package-local HDL lexical/frontend plus declaration, consumer, state and exact-scope controls; "
            "not production VCS elaboration or a dynamic DUT result."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": report["pass"], "errors": errors, "output": str(args.output)}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
