#!/usr/bin/env python3
"""Validate the observer/VCD diagnostic bulk-evidence mode selector."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


SCHEMA = "server-diagnostic-mode-selector-v1"
OBSERVER = "OBSERVER_ONLY_WIDE_CAUSAL"
VCD = "TB_VCD_BOUNDED_CAUSAL_CONE"
WAVE_SUFFIXES = (".vpd", ".fsdb", ".vcd", ".fst")
FORBIDDEN_TEXT = (
    re.compile(r"\$fsdb", re.I),
    re.compile(r"\bUCLI\b|\bdump\s+-file\b", re.I),
    re.compile(r"\b(?:vpd2vcd|verdi|dve|waveutils)\b", re.I),
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("selector must be a JSON object")
    return value


def validate_selector(value: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if value.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    mode = value.get("selected_mode")
    if mode not in {OBSERVER, VCD}:
        errors.append("selected_mode is unsupported")
    bulk = value.get("bulk_evidence") if isinstance(value.get("bulk_evidence"), dict) else {}
    active = [name for name in ("observer_jsonl", "tb_standard_vcd") if bulk.get(name) is True]
    if len(active) != 1:
        errors.append("exactly one bulk evidence mode must be enabled")
    if mode == OBSERVER and active != ["observer_jsonl"]:
        errors.append("observer mode must enable only observer_jsonl bulk evidence")
    if mode == VCD and active != ["tb_standard_vcd"]:
        errors.append("VCD mode must enable only tb_standard_vcd bulk evidence")
    for name in ("vpd", "fsdb", "ucli_direct_vcd", "vendor_signal_query"):
        if bulk.get(name) is not False:
            errors.append(f"{name} must be false")

    argv = value.get("actual_dump_argv") if isinstance(value.get("actual_dump_argv"), dict) else {}
    for name in ("DUMP_VCD", "DUMP_FSDB", "TB_DUMP_FSDB"):
        if argv.get(name) != "0":
            errors.append(f"{name} must be string 0")

    progress = value.get("lightweight_progress_supervisor")
    if not isinstance(progress, dict):
        errors.append("lightweight_progress_supervisor is required")
    else:
        expected = {
            "enabled": True,
            "bulk_signal_events": False,
            "sim_time_heartbeat": True,
            "process_tree_reap": True,
        }
        for key, wanted in expected.items():
            if progress.get(key) is not wanted:
                errors.append(f"lightweight progress {key} must be {wanted}")

    package_members = value.get("package_members") if isinstance(value.get("package_members"), list) else []
    return_members = value.get("return_members") if isinstance(value.get("return_members"), list) else []
    all_members = [str(item).lower() for item in package_members + return_members]
    for member in (str(item).lower() for item in package_members):
        if member.endswith(WAVE_SUFFIXES):
            errors.append(f"package must not self-include runtime waveform evidence: {member}")
    for member in all_members:
        if member.endswith((".vpd", ".fsdb", ".fst")):
            errors.append(f"forbidden waveform member: {member}")
    if mode == OBSERVER:
        if any(member.endswith(".vcd") for member in all_members):
            errors.append("observer mode must not contain VCD members")
        if value.get("observer_contract_sha256") is None:
            errors.append("observer mode must bind observer contract SHA")
        if value.get("vcd_contract_sha256") is not None:
            errors.append("observer mode must not bind VCD contract SHA")
    if mode == VCD:
        if not any(member.endswith(".vcd") for member in return_members):
            errors.append("VCD mode return must include a VCD member")
        if any("observer/chunks/" in member or member.endswith(".jsonl") and "observer" in member for member in all_members):
            errors.append("VCD mode must not include full observer JSONL chunks")
        if value.get("vcd_contract_sha256") is None:
            errors.append("VCD mode must bind VCD contract SHA")
        if value.get("observer_contract_sha256") is not None:
            errors.append("VCD mode must not bind observer contract SHA")

    return {
        "schema": "server-diagnostic-mode-selector-validation-v1",
        "pass": not errors,
        "selected_mode": mode,
        "active_bulk_modes": active,
        "errors": errors,
        "claim_boundary": "Local mode exclusivity only; no production or diagnostic claim.",
    }


def validate_zip(path: Path, selector: dict[str, Any]) -> dict[str, Any]:
    report = validate_selector(selector)
    errors = list(report["errors"])
    mode = selector.get("selected_mode")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]
        lower = [name.lower() for name in names]
        for name in lower:
            if name.endswith((".vpd", ".fsdb", ".fst")):
                errors.append(f"final ZIP contains forbidden waveform member: {name}")
            if mode == VCD and name.endswith(".vcd"):
                errors.append(f"VCD final ZIP must not self-include runtime VCD evidence: {name}")
            if mode == OBSERVER and name.endswith(".vcd"):
                errors.append(f"observer final ZIP contains VCD member: {name}")
            if mode == VCD and ("observer/chunks/" in name or name.endswith(".jsonl") and "observer" in name):
                errors.append(f"VCD final ZIP contains forbidden full observer JSONL: {name}")
        text_suffixes = (".sh", ".py", ".tcl", ".sv", ".svh", ".v", ".vh", ".mk")
        for info in infos:
            if info.is_dir() or not info.filename.lower().endswith(text_suffixes):
                continue
            text = archive.read(info).decode("utf-8", errors="replace")
            for pattern in FORBIDDEN_TEXT:
                if pattern.search(text):
                    errors.append(f"{info.filename}: forbidden vendor waveform control")
            if mode == VCD and "DUMP_VCD=1" in text:
                errors.append(f"{info.filename}: Makefile DUMP_VCD=1 is forbidden because it produces VPD")
    report.update({"pass": not errors, "errors": errors, "final_zip": path.as_posix(), "final_zip_sha256": _sha(path)})
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selector", required=True, type=Path)
    parser.add_argument("--zip", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    selector = load(args.selector)
    report = validate_zip(args.zip, selector) if args.zip else validate_selector(selector)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
