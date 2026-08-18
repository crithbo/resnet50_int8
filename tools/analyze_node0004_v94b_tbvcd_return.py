#!/usr/bin/env python3
"""Stream and summarize the serialized Conv v94b formal return.

The raw VCD and logs are consumed line-by-line.  The tool writes an immutable
non-clock transition derivative and bounded summaries; it never materializes
the VCD or full simulator log in memory.
"""

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
PACKAGE = "r5_n4_hw_v94b_tbvcd_wrdrain"
RETURN_ROOT = f"{PACKAGE}_return/"
VCD_REL = "waveforms/causal_cone.vcd"
CATALOG_REL = "evidence/vcd/VCD_SIGNAL_CATALOG.json"
ANALYSIS = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_return_analysis"
STREAM = ANALYSIS / "streaming"
PENDING = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{PACKAGE}.zip"


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


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        stream.write(payload)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def load_json(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    with archive.open(RETURN_ROOT + relative) as stream:
        return json.load(stream)


def normalize(value: str | None, width: int) -> str | None:
    if value is None or not value or any(bit not in "01xz" for bit in value.lower()):
        return None
    value = value.lower()
    if len(value) > width:
        value = value[-width:]
    if len(value) < width:
        fill = value[0] if value[0] in "xz" else "0"
        value = fill * (width - len(value)) + value
    return value


def known_int(value: str | None, width: int) -> int | None:
    value = normalize(value, width)
    if value is None or any(bit not in "01" for bit in value):
        return None
    return int(value, 2)


def verify_return_manifest(archive: zipfile.ZipFile, manifest: dict[str, Any]) -> dict[str, Any]:
    names = set(archive.namelist())
    errors: list[str] = []
    checked = 0
    for row in manifest.get("core_entry_receipts", []):
        name = RETURN_ROOT + row["path"]
        if name not in names:
            errors.append(f"missing:{row['path']}")
            continue
        info = archive.getinfo(name)
        if info.file_size != row["bytes"]:
            errors.append(f"bytes:{row['path']}")
            continue
        with archive.open(name) as stream:
            _, digest = sha_stream(stream)
        if digest != row["sha256"]:
            errors.append(f"sha256:{row['path']}")
        checked += 1
    return {
        "pass": not errors and not manifest.get("missing_required_entries") and not manifest.get("required_plugin_failures"),
        "checked_receipts": checked,
        "errors": errors,
        "missing_required_entries": manifest.get("missing_required_entries", []),
        "required_plugin_failures": manifest.get("required_plugin_failures", []),
    }


def verify_source_package(returned_manifest: bytes) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(PENDING), "present": PENDING.is_file(), "errors": []}
    if not PENDING.is_file():
        result["errors"].append("pending source package absent")
        result["pass"] = False
        return result
    with zipfile.ZipFile(PENDING) as archive:
        roots = {Path(name).parts[0] for name in archive.namelist() if Path(name).parts}
        if roots != {PACKAGE} or archive.testzip() is not None:
            result["errors"].append("pending source ZIP root/CRC invalid")
        internal = archive.read(f"{PACKAGE}/package_manifest.json")
        result["manifest_byte_equal"] = internal == returned_manifest
        if internal != returned_manifest:
            result["errors"].append("returned package manifest differs from pending source ZIP")
        manifest = json.loads(returned_manifest)
        verified = 0
        for row in manifest.get("files", []):
            name = f"{PACKAGE}/{row['path']}"
            try:
                info = archive.getinfo(name)
            except KeyError:
                result["errors"].append(f"missing package member:{row['path']}")
                continue
            if info.file_size != row["bytes"]:
                result["errors"].append(f"package member size drift:{row['path']}")
                continue
            with archive.open(name) as stream:
                _, digest = sha_stream(stream)
            if digest != row["sha256"]:
                result["errors"].append(f"package member hash drift:{row['path']}")
            verified += 1
        result["members_verified"] = verified
    result["bytes"], result["sha256"] = sha_path(PENDING)
    result["pass"] = not result["errors"]
    return result


def scan_log(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    open_re = re.compile(r"cannot open|failed to open|unable to open", re.I)
    heartbeat_re = re.compile(
        r"CODEX_TB_VCD_HEARTBEAT_V1 sim_time=(\d+) owner_cycles=(\d+) progress=(\d+) state=([^ ]+) global=([^ ]+) xz=(\d+)"
    )
    exact_binary_re = re.compile(r"^\s*[01xXzZ]{7,}\s*$")
    tail: deque[dict[str, Any]] = deque(maxlen=160)
    open_rows: list[dict[str, Any]] = []
    binary_rows: list[dict[str, Any]] = []
    literal_rows: list[dict[str, Any]] = []
    heartbeats: list[dict[str, Any]] = []
    markers: list[dict[str, Any]] = []
    line_count = 0
    member = RETURN_ROOT + relative
    with archive.open(member) as raw:
        for line_count, payload in enumerate(raw, 1):
            line = payload.decode("utf-8", errors="replace").rstrip("\r\n")
            tail.append({"line": line_count, "text": line[:1000]})
            if open_re.search(line) and len(open_rows) < 64:
                open_rows.append({"line": line_count, "text": line[:1000]})
            if exact_binary_re.fullmatch(line):
                if len(binary_rows) < 64:
                    binary_rows.append({"line": line_count, "text": line[:1000]})
            if "0001001" in line and len(literal_rows) < 64:
                literal_rows.append({"line": line_count, "text": line[:1000]})
            match = heartbeat_re.search(line)
            if match:
                heartbeats.append(
                    {
                        "line": line_count,
                        "sim_time": int(match.group(1)),
                        "owner_cycles": int(match.group(2)),
                        "progress": int(match.group(3)),
                        "state": match.group(4),
                        "global": match.group(5),
                        "xz": int(match.group(6)),
                    }
                )
            if any(token in line for token in ("CODEX_TB_VCD_START_V1", "CODEX_TB_VCD_DUMPOFF", "CODEX_TB_VCD_STOP_REQUEST", "$finish", "UVM_FATAL")):
                if len(markers) < 128:
                    markers.append({"line": line_count, "text": line[:1000]})
    open_count = sum(1 for row in tail if open_re.search(row["text"]))
    # The exact total is recovered by the known warning stride only for the simulator log;
    # retain the bounded samples and derive total separately in the second streaming pass.
    return {
        "member": relative,
        "line_count": line_count,
        "open_warning_samples": open_rows,
        "open_warning_tail_count": open_count,
        "binary_only_samples": binary_rows,
        "literal_0001001_samples": literal_rows,
        "heartbeat_count": len(heartbeats),
        "first_heartbeat": heartbeats[0] if heartbeats else None,
        "last_heartbeat": heartbeats[-1] if heartbeats else None,
        "first_nonzero_progress": next((row for row in heartbeats if row["progress"] > 0), None),
        "last_progress_change": next((heartbeats[i] for i in range(len(heartbeats) - 1, 0, -1) if heartbeats[i]["progress"] != heartbeats[i - 1]["progress"]), None),
        "heartbeat_sim_time_strict": all(b["sim_time"] > a["sim_time"] for a, b in zip(heartbeats, heartbeats[1:])),
        "heartbeat_owner_cycles_strict": all(b["owner_cycles"] > a["owner_cycles"] for a, b in zip(heartbeats, heartbeats[1:])),
        "markers": markers,
        "tail": list(tail),
    }


def count_log_patterns(archive: zipfile.ZipFile, relative: str) -> dict[str, int]:
    counts = {"cannot_open": 0, "binary_only": 0, "literal_0001001": 0}
    exact_binary_re = re.compile(r"^\s*[01xXzZ]{7,}\s*$")
    with archive.open(RETURN_ROOT + relative) as raw:
        for payload in raw:
            line = payload.decode("utf-8", errors="replace").rstrip("\r\n")
            counts["cannot_open"] += int("cannot open file" in line.lower())
            counts["binary_only"] += int(exact_binary_re.fullmatch(line) is not None)
            counts["literal_0001001"] += int("0001001" in line)
    return counts


def transition_summary() -> dict[str, Any]:
    return {"transitions": 0, "xz_transitions": 0, "first_time": None, "first_value": None, "last_time": None, "last_value": None}


def stream_vcd(archive: zipfile.ZipFile, catalog: dict[str, Any]) -> dict[str, Any]:
    info = archive.getinfo(RETURN_ROOT + VCD_REL)
    rows = catalog["signals"]
    hierarchy_to_id = {row["exact_hierarchy"]: row["signal_id"] for row in rows}
    widths = {row["signal_id"]: int(row["width_bits"]) for row in rows}
    summaries = {row["signal_id"]: transition_summary() for row in rows}
    code_to_id: dict[str, str] = {}
    scopes: list[str] = []
    values: dict[str, str] = {}
    current_time = 0
    line_count = 0
    events = 0
    non_clock_events = 0
    last_nonclock_time = None
    first_nonclock_time = None
    timescale = None
    directive: str | None = None
    directive_body: list[str] = []
    header_hierarchies: list[str] = []
    transition_path = STREAM / "causal_transitions.jsonl"
    temporary = transition_path.with_name(f".{transition_path.name}.tmp.{os.getpid()}")
    with archive.open(info) as raw, temporary.open("w", encoding="utf-8", newline="\n") as output:
        for payload in raw:
            line_count += 1
            line = payload.decode("utf-8", errors="strict").strip()
            if not line:
                continue
            if directive is not None:
                if line == "$end":
                    if directive == "$timescale":
                        timescale = " ".join(directive_body).strip()
                    directive = None
                    directive_body = []
                else:
                    directive_body.append(line)
                continue
            if line in {"$timescale", "$date", "$version"}:
                directive = line
                directive_body = []
                continue
            if line.startswith("$scope"):
                parts = line.split()
                if len(parts) >= 4:
                    scopes.append(parts[2])
                continue
            if line.startswith("$upscope"):
                if scopes:
                    scopes.pop()
                continue
            if line.startswith("$var"):
                parts = line.split()
                if len(parts) >= 6:
                    code = parts[3]
                    reference = parts[4]
                    hierarchy = ".".join([*scopes, reference])
                    header_hierarchies.append(hierarchy)
                    signal_id = hierarchy_to_id.get(hierarchy)
                    if signal_id is not None:
                        code_to_id[code] = signal_id
                continue
            if line.startswith("#") and line[1:].isdigit():
                current_time = int(line[1:])
                continue
            if line[0] in "01xXzZ":
                value, code = line[0].lower(), line[1:]
            elif line[0] in "bB":
                parts = line.split()
                if len(parts) != 2:
                    continue
                value, code = parts[0][1:].lower(), parts[1]
            else:
                continue
            signal_id = code_to_id.get(code)
            if signal_id is None:
                continue
            value = normalize(value, widths[signal_id]) or value
            if values.get(signal_id) == value:
                continue
            values[signal_id] = value
            events += 1
            summary = summaries[signal_id]
            summary["transitions"] += 1
            summary["xz_transitions"] += int(any(bit in "xz" for bit in value))
            if summary["first_time"] is None:
                summary["first_time"] = current_time
                summary["first_value"] = value
            summary["last_time"] = current_time
            summary["last_value"] = value
            if signal_id != "sig_clk":
                non_clock_events += 1
                first_nonclock_time = current_time if first_nonclock_time is None else first_nonclock_time
                last_nonclock_time = current_time
                output.write(json.dumps({"sequence": non_clock_events, "time": current_time, "signal_id": signal_id, "value_4state": value}, sort_keys=True) + "\n")
    os.replace(temporary, transition_path)
    with archive.open(info) as raw:
        vcd_bytes, vcd_sha = sha_stream(raw)
    missing = sorted(set(hierarchy_to_id) - set(header_hierarchies))
    unexpected = sorted(set(header_hierarchies) - set(hierarchy_to_id))
    return {
        "member": RETURN_ROOT + VCD_REL,
        "bytes": vcd_bytes,
        "sha256": vcd_sha,
        "crc32": f"{info.CRC:08x}",
        "timescale": timescale,
        "line_count": line_count,
        "last_timestamp": current_time,
        "first_nonclock_time": first_nonclock_time,
        "last_nonclock_time": last_nonclock_time,
        "mapped_catalog_count": len(code_to_id),
        "catalog_count": len(rows),
        "missing_catalog_hierarchies": missing,
        "unexpected_header_hierarchies": unexpected,
        "event_count": events,
        "non_clock_event_count": non_clock_events,
        "signal_summaries": summaries,
        "final_values": values,
        "transition_derivative": str(transition_path),
    }


def extract_sources(archive: zipfile.ZipFile) -> list[dict[str, Any]]:
    prefix = RETURN_ROOT + "evidence/compiled_source/actual_source_files/"
    target = ANALYSIS / "actual_source"
    target.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
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
        rows.append({"path": str(output), "bytes": total, "sha256": digest.hexdigest()})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    args = parser.parse_args()
    source = args.return_zip.resolve(strict=True)
    STREAM.mkdir(parents=True, exist_ok=True)
    base_state_path = STREAM / "analysis_state.json"
    if not base_state_path.is_file():
        raise RuntimeError("shared bounded streaming state is absent")
    base_state = json.loads(base_state_path.read_text(encoding="utf-8"))
    if base_state.get("status") != "EOF_REACHED":
        raise RuntimeError("shared bounded streaming state has not reached EOF")
    source_bytes, source_sha = sha_path(source)
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("formal return CRC failure")
        manifest = load_json(archive, "RETURN_CORE_MANIFEST.json")
        returned_manifest = archive.read(RETURN_ROOT + "evidence/returned_package_manifest.json")
        catalog = load_json(archive, CATALOG_REL)
        manifest_check = verify_return_manifest(archive, manifest)
        source_package = verify_source_package(returned_manifest)
        sim_log = scan_log(archive, "runs/c0/sim.log")
        sim_log["counts"] = count_log_patterns(archive, "runs/c0/sim.log")
        compile_log = scan_log(archive, "evidence/compile_rootcause/compile_driver.full.log")
        compile_log["counts"] = count_log_patterns(archive, "evidence/compile_rootcause/compile_driver.full.log")
        vcd = stream_vcd(archive, catalog)
        sources = extract_sources(archive)
        receipts = {
            "return_core_status": load_json(archive, "return_core/RETURN_CORE_STATUS.json"),
            "sim_exit_evidence": load_json(archive, "evidence/SIM_EXIT_RECEIPT.json"),
            "sim_exit_core": load_json(archive, "return_core/SIM_EXIT_RECEIPT.json"),
            "compile_core": load_json(archive, "evidence/compile_rootcause/COMPILE_CORE.json"),
            "native_attempt": load_json(archive, "evidence/NATIVE_FLOW_ATTEMPT.json"),
            "runtime": load_json(archive, "evidence/vcd/VCD_RUNTIME_RECEIPT.json"),
            "stop": load_json(archive, "evidence/vcd/VCD_STOP_RECEIPT.json"),
            "archive_timestamp": load_json(archive, "evidence/vcd/TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json"),
            "return_exact_set": load_json(archive, "evidence/vcd/TB_VCD_RETURN_EXACT_SET.json"),
            "vcd_identity": load_json(archive, "evidence/vcd/VCD_IDENTITY.json"),
            "process_tree": load_json(archive, "evidence/PROCESS_TREE_RECEIPT.json"),
            "argv": load_json(archive, "evidence/ACTUAL_COMPILE_SIM_ARGV.json"),
            "candidate_matrix": load_json(archive, "evidence/vcd/VCD_CANDIDATE_MATRIX.json"),
        }
    report = {
        "schema": "node0004-v94b-tbvcd-return-streaming-analysis-v1",
        "source": {"path": str(source), "bytes": source_bytes, "sha256": source_sha},
        "package_id": PACKAGE,
        "integrity": {"zip_crc": True, "return_manifest": manifest_check, "source_package": source_package},
        "shared_streaming_state": base_state,
        "sim_log": sim_log,
        "compile_log": compile_log,
        "vcd": vcd,
        "receipts": receipts,
        "actual_sources": sources,
        "claim_boundary": "Identity, bounded log attribution, and complete local streaming parse of the exact v94b return; family causal/root adjudication is written separately.",
        "pass": manifest_check["pass"] and source_package["pass"] and vcd["mapped_catalog_count"] == vcd["catalog_count"] and not vcd["missing_catalog_hierarchies"],
    }
    atomic_json(ANALYSIS / "streaming_summary.json", report)
    sequence = int(base_state.get("checkpoint_count", 0)) + 1
    checkpoint = {
        "schema": "server-tb-vcd-retention-analysis-v1",
        "kind": "family_v94b_full_causal_stream",
        "sequence": sequence,
        "source_sha256": source_sha,
        "member_sha256": vcd["sha256"],
        "last_sim_time": vcd["last_timestamp"],
        "last_nonclock_time": vcd["last_nonclock_time"],
        "non_clock_events": vcd["non_clock_event_count"],
        "mapped_catalog_count": vcd["mapped_catalog_count"],
        "status": "EOF_REACHED",
    }
    checkpoint_path = STREAM / "checkpoints.jsonl"
    existing = checkpoint_path.read_text(encoding="utf-8") if checkpoint_path.is_file() else ""
    if '"kind": "family_v94b_full_causal_stream"' not in existing:
        with checkpoint_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(checkpoint, sort_keys=True) + "\n")
        base_state["checkpoint_count"] = sequence
    base_state["family_causal_pass"] = {
        "status": "EOF_REACHED",
        "summary": "../streaming_summary.json",
        "transitions": "causal_transitions.jsonl",
        "member_sha256": vcd["sha256"],
        "non_clock_events": vcd["non_clock_event_count"],
        "mapped_catalog_count": vcd["mapped_catalog_count"],
    }
    atomic_json(base_state_path, base_state)
    report_path = STREAM / "report.md"
    text = report_path.read_text(encoding="utf-8") if report_path.is_file() else "# Incremental v94b review\n"
    if "## Family exact-hierarchy causal stream" not in text:
        text += (
            "\n## Family exact-hierarchy causal stream\n\n"
            f"- catalog mapped: `{vcd['mapped_catalog_count']}/{vcd['catalog_count']}`\n"
            f"- VCD last timestamp: `{vcd['last_timestamp']}`\n"
            f"- last non-clock transition: `{vcd['last_nonclock_time']}`\n"
            f"- retained non-clock transitions: `{vcd['non_clock_event_count']}`\n"
            f"- simulator warning `Cannot open file`: `{sim_log['counts']['cannot_open']}`\n"
            f"- exact binary-only simulator lines: `{sim_log['counts']['binary_only']}`\n"
            f"- simulator lines containing `0001001`: `{sim_log['counts']['literal_0001001']}`\n"
        )
        report_path.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"pass": report["pass"], "summary": str(ANALYSIS / 'streaming_summary.json'), "last_timestamp": vcd["last_timestamp"], "last_nonclock": vcd["last_nonclock_time"], "nonclock_events": vcd["non_clock_event_count"], "catalog": [vcd["mapped_catalog_count"], vcd["catalog_count"]]}))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
