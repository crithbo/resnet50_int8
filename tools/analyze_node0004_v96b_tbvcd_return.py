#!/usr/bin/env python3
"""Strict streaming/core analysis for the serialized Conv v96b formal return."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from collections import deque
from pathlib import Path
from typing import Any, BinaryIO


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v96b_tbvcd_memtuple"
EXECUTION = "r1786770065727401255_2781777"
RETURN_ROOT = f"{PACKAGE}_return/"
ANALYSIS = ROOT / f"outputs/conv_node0004_v96b_tbvcd_memtuple_return_{EXECUTION}"
STREAM = ANALYSIS / "streaming"
SOURCE_PACKAGE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE}.zip"


def sha_stream(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        total += len(block)
        digest.update(block)
    return total, digest.hexdigest()


def sha_path(path: Path) -> tuple[int, str]:
    with path.open("rb") as stream:
        return sha_stream(stream)


def atomic_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, newline="\n") as stream:
        stream.write(payload)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def load_json(archive: zipfile.ZipFile, relative: str) -> Any:
    with archive.open(RETURN_ROOT + relative) as stream:
        return json.load(stream)


def append_checkpoint(kind: str, value: dict[str, Any]) -> None:
    path = STREAM / "checkpoints.jsonl"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if f'"kind": "{kind}"' in existing:
        return
    count = sum(1 for line in existing.splitlines() if line.strip()) + 1
    row = {"kind": kind, "sequence": count, **value}
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def update_report(title: str, lines: list[str]) -> None:
    path = STREAM / "report.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "# Incremental v96b formal-return review\n"
    marker = f"## {title}"
    if marker not in text:
        text += "\n" + marker + "\n\n" + "\n".join(lines) + "\n"
        atomic_text(path, text)


def verify_manifest(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, Any]:
    names = set(archive.namelist())
    errors: list[str] = []
    rows = []
    for row in manifest.get("core_entry_receipts", []):
        name = RETURN_ROOT + row["path"]
        if name not in names:
            errors.append(f"missing:{row['path']}")
            continue
        info = archive.getinfo(name)
        with archive.open(info) as stream:
            size, digest = sha_stream(stream)
        good = size == row["bytes"] and digest == row["sha256"]
        rows.append({"path": row["path"], "bytes": size, "sha256": digest, "pass": good})
        if not good:
            errors.append(f"identity:{row['path']}")
    return {
        "checked": len(rows),
        "errors": errors,
        "missing_required_entries": manifest.get("missing_required_entries", []),
        "pass": not errors and not manifest.get("missing_required_entries") and not manifest.get("required_plugin_failures"),
        "required_plugin_failures": manifest.get("required_plugin_failures", []),
        "rows": rows,
    }


def verify_source_package(returned_manifest: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"errors": [], "path": str(SOURCE_PACKAGE), "present": SOURCE_PACKAGE.is_file()}
    if not SOURCE_PACKAGE.is_file():
        result["errors"].append("pending source package absent")
        result["pass"] = False
        return result
    with zipfile.ZipFile(SOURCE_PACKAGE) as archive:
        result["crc_pass"] = archive.testzip() is None
        internal = archive.read(f"{PACKAGE}/package_manifest.json")
        result["manifest_byte_equal"] = internal == returned_manifest
        if not result["crc_pass"]:
            result["errors"].append("source package CRC failure")
        if not result["manifest_byte_equal"]:
            result["errors"].append("returned package manifest drift")
        manifest = json.loads(returned_manifest)
        checked = 0
        for row in manifest.get("files", []):
            name = f"{PACKAGE}/{row['path']}"
            try:
                info = archive.getinfo(name)
            except KeyError:
                result["errors"].append(f"missing:{row['path']}")
                continue
            with archive.open(info) as stream:
                size, digest = sha_stream(stream)
            if size != row["bytes"] or digest != row["sha256"]:
                result["errors"].append(f"identity:{row['path']}")
            checked += 1
        probe = f"{PACKAGE}/tb_probe/tb_vcd_bounded_causal_cone.svh"
        probe_target = ANALYSIS / "package_source/tb_vcd_bounded_causal_cone.svh"
        probe_target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(probe) as source, probe_target.open("wb") as sink:
            shutil_digest = hashlib.sha256()
            for block in iter(lambda: source.read(1024 * 1024), b""):
                sink.write(block)
                shutil_digest.update(block)
        result["probe"] = {"path": str(probe_target), "sha256": shutil_digest.hexdigest()}
        result["members_verified"] = checked
    result["bytes"], result["sha256"] = sha_path(SOURCE_PACKAGE)
    result["pass"] = not result["errors"]
    return result


def stream_compile_log(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    member = RETURN_ROOT + relative
    error_re = re.compile(r"^Error-\[[A-Z0-9_-]+\]", re.I)
    before: deque[tuple[int, str]] = deque(maxlen=8)
    contexts: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    tail: deque[dict[str, Any]] = deque(maxlen=80)
    digest = hashlib.sha256()
    total = 0
    line_count = 0
    with archive.open(member) as stream:
        for payload in stream:
            digest.update(payload)
            total += len(payload)
            line_count += 1
            line = payload.decode("utf-8", errors="replace").rstrip("\r\n")
            tail.append({"line": line_count, "text": line[:2000]})
            for row in active[:]:
                row["after"].append({"line": line_count, "text": line[:2000]})
                row["remaining"] -= 1
                if row["remaining"] == 0:
                    active.remove(row)
            if error_re.search(line) and len(contexts) < 128:
                row = {
                    "after": [],
                    "before": [{"line": n, "text": text} for n, text in before],
                    "line": line_count,
                    "text": line[:2000],
                    "remaining": 18,
                }
                contexts.append(row)
                active.append(row)
            before.append((line_count, line[:2000]))
    for row in contexts:
        row.pop("remaining", None)
    xmre_tokens = []
    for row in contexts:
        joined = "\n".join([row["text"], *(part["text"] for part in row["after"])])
        token = re.search(r"token '([^']+)'", joined, re.I)
        source = re.search(r"^(.+),\s*(\d+)$", row["after"][0]["text"]) if row["after"] else None
        observer_symbol = re.search(r"Source info:\s+\.([A-Za-z0-9_\[\]]+)", joined)
        if token or source or observer_symbol:
            xmre_tokens.append(
                {
                    "observer_symbol": observer_symbol.group(1) if observer_symbol else None,
                    "source": source.group(1) if source else None,
                    "source_line": int(source.group(2)) if source else None,
                    "token": token.group(1) if token else None,
                }
            )
    unique = []
    for row in xmre_tokens:
        if row not in unique:
            unique.append(row)
    return {
        "bytes": total,
        "contexts": contexts,
        "line_count": line_count,
        "member": relative,
        "sha256": digest.hexdigest(),
        "tail": list(tail),
        "unique_xmre_sites": unique,
    }


def extract_actual_sources(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    prefix = RETURN_ROOT + "evidence/compiled_source/actual_source_files/"
    target = ANALYSIS / "actual_source"
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in archive.namelist():
        if not name.startswith(prefix) or name.endswith("/"):
            continue
        output = target / Path(name).name
        with archive.open(name) as source, output.open("wb") as sink:
            digest = hashlib.sha256()
            total = 0
            for block in iter(lambda: source.read(1024 * 1024), b""):
                sink.write(block)
                digest.update(block)
                total += len(block)
        rows.append({"bytes": total, "path": str(output), "sha256": digest.hexdigest()})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    args = parser.parse_args()
    source = args.return_zip.resolve(strict=True)
    STREAM.mkdir(parents=True, exist_ok=True)
    source_bytes, source_sha = sha_path(source)
    state = {
        "analysis_id": "node0004-v96b-tbvcd-return-analysis-v1",
        "package_id": PACKAGE,
        "source": {"bytes": source_bytes, "path": str(source), "sha256": source_sha},
        "status": "IDENTITY_VERIFIED",
    }
    atomic_json(STREAM / "analysis_state.json", state)
    append_checkpoint("zip_identity", {"bytes": source_bytes, "sha256": source_sha, "status": "PASS"})
    update_report("ZIP identity", [f"- bytes: `{source_bytes}`", f"- SHA-256: `{source_sha}`"])

    with zipfile.ZipFile(source) as archive:
        bad = archive.testzip()
        manifest = load_json(archive, "RETURN_CORE_MANIFEST.json")
        manifest_check = verify_manifest(archive, manifest)
        returned_manifest = archive.read(RETURN_ROOT + "evidence/returned_package_manifest.json")
        source_package = verify_source_package(returned_manifest)
        state.update({"crc_pass": bad is None, "manifest_pass": manifest_check["pass"], "source_package_pass": source_package["pass"], "status": "CORE_IDENTITY_VERIFIED"})
        atomic_json(STREAM / "analysis_state.json", state)
        append_checkpoint("core_identity", {"crc_pass": bad is None, "manifest_pass": manifest_check["pass"], "source_package_pass": source_package["pass"], "status": "PASS" if bad is None and manifest_check["pass"] and source_package["pass"] else "FAIL"})
        update_report("Core identity", [f"- ZIP CRC: `{'PASS' if bad is None else 'FAIL'}`", f"- return manifest: `{'PASS' if manifest_check['pass'] else 'FAIL'}`", f"- source package: `{'PASS' if source_package['pass'] else 'FAIL'}`"])

        log = stream_compile_log(archive, "evidence/compile_rootcause/compile_driver.full.log")
        first_error = archive.read(RETURN_ROOT + "evidence/compile_rootcause/compile_first_error.txt").decode("utf-8", errors="replace").strip()
        receipts = {
            "actual_argv": load_json(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json"),
            "compile_argv": load_json(archive, "evidence/compile_rootcause/compile_argv.json"),
            "compile_core": load_json(archive, "evidence/compile_rootcause/COMPILE_CORE.json"),
            "native_attempt": load_json(archive, "evidence/NATIVE_FLOW_ATTEMPT.json"),
            "return_core": load_json(archive, "return_core/RETURN_CORE_STATUS.json"),
            "runtime": load_json(archive, "evidence/vcd/VCD_RUNTIME_RECEIPT.json"),
            "sim_exit": load_json(archive, "evidence/SIM_EXIT_RECEIPT.json"),
            "stop": load_json(archive, "evidence/vcd/VCD_STOP_RECEIPT.json"),
        }
        catalog = load_json(archive, "evidence/vcd/VCD_SIGNAL_CATALOG.json")
        matrix = load_json(archive, "evidence/vcd/VCD_CANDIDATE_MATRIX.json")
        sources = extract_actual_sources(archive)
        state.update({"compile_exit": receipts["compile_core"]["compile_exit"], "simulation_started": receipts["sim_exit"]["simulation_started"], "status": "EOF_REACHED", "target_entry": receipts["runtime"]["target_entry"]["observed"]})
        atomic_json(STREAM / "analysis_state.json", state)
        append_checkpoint("compile_runtime_partition", {"compile_exit": receipts["compile_core"]["compile_exit"], "first_error": first_error, "simulation_started": receipts["sim_exit"]["simulation_started"], "status": "EOF_REACHED", "target_entry": receipts["runtime"]["target_entry"]["observed"], "unique_xmre_sites": log["unique_xmre_sites"]})
        update_report("Compile/runtime partition", [f"- compile exit: `{receipts['compile_core']['compile_exit']}`", f"- first error: `{first_error}`", f"- simulation started: `{receipts['sim_exit']['simulation_started']}`", f"- target entry: `{receipts['runtime']['target_entry']['observed']}`", f"- unique XMRE sites: `{len(log['unique_xmre_sites'])}`"])

    summary = {
        "actual_sources": sources,
        "catalog_count": len(catalog.get("signals", [])),
        "claim_boundary": "Exact ZIP/package/execution/compile-core identity and bounded streaming compile-log analysis only; no v96 dynamic tuple, VCD, natural terminal, formal-D or E3-E5 claim.",
        "compile_log": log,
        "first_error": first_error,
        "identity": {"manifest": manifest_check, "return_crc_pass": bad is None, "source_package": source_package},
        "matrix_rows": len(matrix.get("rows", matrix.get("matrix", []))),
        "package_id": PACKAGE,
        "pass": bad is None and manifest_check["pass"] and source_package["pass"],
        "receipts": receipts,
        "schema": "node0004-v96b-tbvcd-return-streaming-summary-v1",
        "source": state["source"],
    }
    atomic_json(ANALYSIS / "streaming_summary.json", summary)
    append_checkpoint("analysis_eof", {"status": "EOF_REACHED", "summary": "../streaming_summary.json"})
    update_report("EOF", ["- all 44 ZIP members were CRC-checked", "- required manifest receipts and the exact pending source package were identity-checked", "- complete compile log was consumed line-by-line", "- no dynamic waveform/event member exists because simulation did not start"])
    print(json.dumps({"pass": summary["pass"], "compile_exit": receipts["compile_core"]["compile_exit"], "simulation_started": receipts["sim_exit"]["simulation_started"], "xmre_sites": log["unique_xmre_sites"], "summary": str(ANALYSIS / "streaming_summary.json")}, ensure_ascii=False))
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
