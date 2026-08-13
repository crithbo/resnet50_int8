#!/usr/bin/env python3
"""Create portable VCD evidence from VPD and analyze VCD without loading it all.

The raw VPD remains authoritative.  Conversion is performed only with an
explicit or discovered Synopsys ``vpd2vcd`` executable, and every input/tool/
output identity is recorded.  VCD catalog and trace extraction are streaming
operations and impose no implicit waveform byte or event limit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterable


SCHEMA = "server-waveform-local-analysis-v1"
WAVE_RECEIPT_SCHEMA = "server-waveform-runtime-receipt-v2"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class AnalysisError(ValueError):
    """A conversion request, tool identity, waveform or VCD is invalid."""


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    temporary.write_bytes(json_bytes(value))
    os.replace(temporary, path)


def hash_stream(stream: BinaryIO) -> tuple[int, str]:
    digest = hashlib.sha256()
    total = 0
    while True:
        block = stream.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        digest.update(block)
    return total, digest.hexdigest()


def hash_file(path: Path) -> tuple[int, str]:
    with path.open("rb") as stream:
        return hash_stream(stream)


def safe_relative(label: str, value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise AnalysisError(f"{label} must be a POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise AnalysisError(f"{label} is unsafe: {value}")
    return path


def safe_zip(archive: zipfile.ZipFile) -> tuple[str, list[str]]:
    names = archive.namelist()
    if not names or archive.testzip() is not None:
        raise AnalysisError("return ZIP is empty or fails CRC")
    roots: set[str] = set()
    for name in names:
        path = safe_relative("ZIP member", name)
        roots.add(path.parts[0])
        info = archive.getinfo(name)
        if ((info.external_attr >> 16) & 0o170000) == 0o120000:
            raise AnalysisError(f"ZIP member is a symlink: {name}")
    if len(roots) != 1:
        raise AnalysisError(f"return ZIP must have one root: {sorted(roots)}")
    return next(iter(roots)), names


def executable_identity(path: str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        return None
    size, digest = hash_file(candidate)
    return {"path": str(candidate.resolve()), "bytes": size, "sha256": digest}


def probe_tool_version(path: Path) -> dict[str, Any]:
    """Capture a best-effort version receipt without making version text authoritative."""
    attempts: list[dict[str, Any]] = []
    for option in ("-version", "--version", "-V", "-help"):
        argv = _tool_argv(path, [option])
        try:
            completed = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            attempt = {
                "argv": argv,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            attempts.append(attempt)
            combined = (completed.stdout + "\n" + completed.stderr).strip()
            if completed.returncode == 0 and combined:
                return {"available": True, "text": combined, "attempts": attempts}
        except (OSError, subprocess.TimeoutExpired) as error:
            attempts.append(
                {
                    "argv": argv,
                    "exit_code": None,
                    "stdout": "",
                    "stderr": f"{type(error).__name__}: {error}",
                }
            )
    return {"available": False, "text": None, "attempts": attempts}


def discover_executable(name: str, explicit: Path | None = None) -> str | None:
    if explicit is not None:
        return str(explicit.resolve()) if explicit.is_file() and not explicit.is_symlink() else None
    direct = shutil.which(name)
    if direct:
        return direct
    suffixes = ("", ".exe") if os.name == "nt" else ("",)
    for env_name in ("VCS_HOME", "VERDI_HOME"):
        root = os.environ.get(env_name)
        if not root:
            continue
        for suffix in suffixes:
            candidate = Path(root) / "bin" / f"{name}{suffix}"
            if candidate.is_file() and not candidate.is_symlink():
                return str(candidate.resolve())
    return None


def inspect_toolchain() -> dict[str, Any]:
    tools: dict[str, Any] = {}
    for name in ("vpd2vcd", "verdi", "dve", "vcd2fst", "gtkwave"):
        resolved = discover_executable(name)
        tools[name] = {"available": resolved is not None, "identity": executable_identity(resolved)}
    portable_ready = tools["vpd2vcd"]["available"]
    local_ready = tools["gtkwave"]["available"] or tools["verdi"]["available"] or tools["dve"]["available"]
    return {
        "schema": SCHEMA,
        "kind": "toolchain",
        "pass": portable_ready and local_ready,
        "errors": [
            message
            for condition, message in (
                (portable_ready, "vpd2vcd is unavailable; raw VPD cannot be portably decoded here"),
                (local_ready, "no local waveform viewer is available"),
            )
            if not condition
        ],
        "tools": tools,
        "recommended_flow": "server vpd2vcd -> returned VCD -> optional local vcd2fst -> GTKWave",
        "claim_boundary": "Tool availability only; no waveform semantic claim.",
    }


def prepare_conversion_request(return_zip: Path) -> dict[str, Any]:
    errors: list[str] = []
    jobs: list[dict[str, Any]] = []
    try:
        zip_size, zip_sha = hash_file(return_zip)
        with zipfile.ZipFile(return_zip) as archive:
            root, names = safe_zip(archive)
            receipts = [name for name in names if name.endswith("/WAVEFORM_RUNTIME_RECEIPT.json")]
            if len(receipts) != 1:
                raise AnalysisError(
                    f"expected one waveform runtime receipt, found {len(receipts)}"
                )
            receipt = json.loads(archive.read(receipts[0]))
            if receipt.get("schema") != WAVE_RECEIPT_SCHEMA:
                errors.append("waveform runtime receipt schema mismatch")
            if receipt.get("pass") is not True or receipt.get("errors") != []:
                errors.append("waveform runtime receipt did not pass")
            for index, waveform in enumerate(receipt.get("waveforms", [])):
                archive_path = safe_relative(
                    f"waveforms[{index}].archive_path", waveform.get("archive_path")
                ).as_posix()
                member = f"{root}/{archive_path}"
                if member not in names:
                    errors.append(f"waveform member is absent: {member}")
                    continue
                with archive.open(member) as stream:
                    size, digest = hash_stream(stream)
                if size != waveform.get("bytes") or digest != waveform.get("sha256"):
                    errors.append(f"waveform identity mismatch: {member}")
                    continue
                stem = PurePosixPath(member).name
                output_name = f"{stem}.vcd"
                jobs.append(
                    {
                        "input_member": member,
                        "input_bytes": size,
                        "input_sha256": digest,
                        "input_completeness": waveform.get("completeness"),
                        "required_server_tool": "vpd2vcd",
                        "server_argv_template": ["vpd2vcd", stem, output_name],
                        "portable_output_name": output_name,
                        "portable_output_format": "VCD",
                        "no_size_limit": True,
                    }
                )
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, AnalysisError) as error:
        errors.append(f"{type(error).__name__}: {error}")
        zip_size, zip_sha = (return_zip.stat().st_size, None) if return_zip.exists() else (0, None)
    return {
        "schema": SCHEMA,
        "kind": "conversion_request",
        "pass": not errors and bool(jobs),
        "errors": errors or ([] if jobs else ["no waveform conversion job was produced"]),
        "return_zip": {"path": str(return_zip), "bytes": zip_size, "sha256": zip_sha},
        "jobs": jobs,
        "rerun_simulation_required": False,
        "claim_boundary": "Conversion request and byte identity only; no signal diagnosis.",
    }


def _converter_argv(converter: Path, source: Path, destination: Path) -> list[str]:
    return _tool_argv(converter, [str(source), str(destination)])


def _tool_argv(tool: Path, arguments: list[str]) -> list[str]:
    if tool.suffix.lower() == ".py":
        return [sys.executable, str(tool), *arguments]
    return [str(tool), *arguments]


def validate_vcd(path: Path, *, include_signals: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    scopes: list[str] = []
    signals: list[dict[str, Any]] = []
    timescale: str | None = None
    version: str | None = None
    date: str | None = None
    header_done = False
    first_time: int | None = None
    last_time: int | None = None
    pending: tuple[str, list[str]] | None = None
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
            for raw in stream:
                line = raw.strip()
                if not header_done:
                    if pending is not None:
                        keyword, parts = pending
                        if "$end" in line:
                            before = line.split("$end", 1)[0].strip()
                            if before:
                                parts.append(before)
                            value = " ".join(parts).strip()
                            if keyword == "$timescale":
                                timescale = value
                            elif keyword == "$version":
                                version = value
                            else:
                                date = value
                            pending = None
                        else:
                            parts.append(line)
                        continue
                    if line.startswith(("$timescale", "$version", "$date")):
                        keyword = line.split(None, 1)[0]
                        remainder = line[len(keyword) :].strip()
                        if "$end" in remainder:
                            value = remainder.split("$end", 1)[0].strip()
                            if keyword == "$timescale":
                                timescale = value
                            elif keyword == "$version":
                                version = value
                            else:
                                date = value
                        else:
                            pending = (keyword, [remainder] if remainder else [])
                    elif line.startswith("$scope "):
                        tokens = line.split()
                        if len(tokens) >= 4:
                            scopes.append(tokens[2])
                    elif line.startswith("$upscope"):
                        if scopes:
                            scopes.pop()
                    elif line.startswith("$var "):
                        tokens = line.split()
                        if len(tokens) < 6 or tokens[-1] != "$end":
                            errors.append(f"malformed VCD var declaration: {line[:160]}")
                            continue
                        try:
                            width = int(tokens[2], 10)
                        except ValueError:
                            errors.append(f"non-decimal VCD width: {tokens[2]}")
                            continue
                        reference = " ".join(tokens[4:-1])
                        signal = {
                            "path": ".".join([*scopes, reference]),
                            "type": tokens[1],
                            "width": width,
                            "id": tokens[3],
                        }
                        if include_signals:
                            signals.append(signal)
                    elif line.startswith("$enddefinitions"):
                        header_done = True
                elif line.startswith("#"):
                    try:
                        timestamp = int(line[1:], 10)
                    except ValueError:
                        errors.append(f"invalid VCD timestamp: {line[:80]}")
                        continue
                    first_time = timestamp if first_time is None else first_time
                    last_time = timestamp
        if not header_done:
            errors.append("VCD lacks $enddefinitions")
        if not signals and include_signals:
            errors.append("VCD declares no signals")
        if first_time is None:
            errors.append("VCD contains no timestamps")
    except OSError as error:
        errors.append(f"{type(error).__name__}: {error}")
    size, digest = hash_file(path) if path.is_file() else (0, None)
    return {
        "schema": SCHEMA,
        "kind": "vcd_catalog",
        "pass": not errors,
        "errors": errors,
        "vcd": {"path": str(path), "bytes": size, "sha256": digest},
        "timescale": timescale,
        "version": version,
        "date": date,
        "signal_count": len(signals),
        "signals": signals,
        "first_time": first_time,
        "last_time": last_time,
        "claim_boundary": "VCD header and time catalog only; no family root-cause claim.",
    }


def convert_vpd(vpd: Path, output_dir: Path, converter: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    logs: dict[str, str] = {"stdout": "", "stderr": ""}
    output_dir.mkdir(parents=True, exist_ok=True)
    vcd = output_dir / f"{vpd.name}.vcd"
    resolved = discover_executable("vpd2vcd", converter)
    tool_identity = executable_identity(resolved)
    version_probe = probe_tool_version(Path(resolved)) if resolved is not None else None
    if not vpd.is_file() or vpd.is_symlink():
        errors.append("input VPD must be a real file")
    if resolved is None or tool_identity is None:
        errors.append("vpd2vcd is unavailable")
    if vcd.exists():
        errors.append(f"conversion output already exists: {vcd}")
    input_size, input_sha = hash_file(vpd) if vpd.is_file() else (0, None)
    argv: list[str] = []
    exit_code: int | None = None
    if not errors:
        argv = _converter_argv(Path(resolved), vpd.resolve(), vcd.resolve())
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, check=False)
            exit_code = completed.returncode
            logs = {"stdout": completed.stdout, "stderr": completed.stderr}
            if exit_code != 0:
                errors.append(f"vpd2vcd exited {exit_code}")
        except OSError as error:
            errors.append(f"{type(error).__name__}: {error}")
    catalog: dict[str, Any] | None = None
    if not errors:
        catalog = validate_vcd(vcd)
        if not catalog["pass"]:
            errors.extend(f"converted VCD: {item}" for item in catalog["errors"])
    return {
        "schema": SCHEMA,
        "kind": "conversion",
        "pass": not errors,
        "errors": errors,
        "input_vpd": {"path": str(vpd), "bytes": input_size, "sha256": input_sha},
        "converter": tool_identity,
        "converter_version_probe": version_probe,
        "argv": argv,
        "exit_code": exit_code,
        "stdout": logs["stdout"],
        "stderr": logs["stderr"],
        "output_vcd": None if catalog is None else catalog["vcd"],
        "vcd_catalog": catalog,
        "no_size_limit": True,
        "claim_boundary": "Format conversion and identity only; no family diagnosis.",
    }


def convert_vcd_to_fst(vcd: Path, output_dir: Path, converter: Path | None = None) -> dict[str, Any]:
    """Create an optional compact local-viewer derivative while retaining VCD."""
    errors: list[str] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    fst = output_dir / f"{vcd.name}.fst"
    resolved = discover_executable("vcd2fst", converter)
    tool_identity = executable_identity(resolved)
    if not vcd.is_file() or vcd.is_symlink():
        errors.append("input VCD must be a real file")
    if resolved is None or tool_identity is None:
        errors.append("vcd2fst is unavailable")
    if fst.exists():
        errors.append(f"conversion output already exists: {fst}")
    catalog = validate_vcd(vcd) if vcd.is_file() else None
    if catalog is not None and not catalog["pass"]:
        errors.extend(f"input VCD: {item}" for item in catalog["errors"])
    argv: list[str] = []
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    if not errors:
        argv = _tool_argv(Path(resolved), [str(vcd.resolve()), str(fst.resolve())])
        try:
            completed = subprocess.run(argv, capture_output=True, text=True, check=False)
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            if exit_code != 0:
                errors.append(f"vcd2fst exited {exit_code}")
        except OSError as error:
            errors.append(f"{type(error).__name__}: {error}")
    output_identity = None
    if not errors:
        if not fst.is_file() or fst.is_symlink():
            errors.append("vcd2fst did not create a real output file")
        else:
            size, digest = hash_file(fst)
            if size == 0:
                errors.append("vcd2fst created an empty output")
            else:
                output_identity = {"path": str(fst), "bytes": size, "sha256": digest}
    return {
        "schema": SCHEMA,
        "kind": "fst_conversion",
        "pass": not errors,
        "errors": errors,
        "input_vcd": None if catalog is None else catalog.get("vcd"),
        "converter": tool_identity,
        "argv": argv,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "output_fst": output_identity,
        "no_size_limit": True,
        "claim_boundary": "Optional VCD-to-FST conversion only; no family diagnosis.",
    }


def extract_vcd(
    vcd: Path,
    patterns: list[str],
    start_time: int | None = None,
    end_time: int | None = None,
) -> dict[str, Any]:
    catalog = validate_vcd(vcd)
    errors = list(catalog["errors"])
    try:
        regexes = [re.compile(pattern) for pattern in patterns]
    except re.error as error:
        return {
            "schema": SCHEMA,
            "kind": "vcd_extract",
            "pass": False,
            "errors": [f"invalid signal regex: {error}"],
            "claim_boundary": "Selected VCD trace extraction only.",
        }
    selected = {
        signal["id"]: signal
        for signal in catalog.get("signals", [])
        if any(regex.search(signal["path"]) for regex in regexes)
    }
    if not selected:
        errors.append("no signal matched the requested regexes")
    events: list[dict[str, Any]] = []
    current_time = 0
    header_done = False
    if not errors:
        try:
            with vcd.open("r", encoding="utf-8", errors="replace", newline="") as stream:
                for raw in stream:
                    line = raw.strip()
                    if not header_done:
                        if line.startswith("$enddefinitions"):
                            header_done = True
                        continue
                    if not line or line.startswith("$"):
                        continue
                    if line.startswith("#"):
                        current_time = int(line[1:], 10)
                        if end_time is not None and current_time > end_time:
                            break
                        continue
                    if start_time is not None and current_time < start_time:
                        continue
                    if line[0] in "01xXzZ" and len(line) > 1:
                        value, identifier = line[0].lower(), line[1:]
                    elif line[0] in "bBrRsS" and " " in line:
                        value, identifier = line.split(None, 1)
                        value = value.lower()
                    else:
                        continue
                    signal = selected.get(identifier)
                    if signal is not None:
                        events.append(
                            {"time": current_time, "id": identifier, "path": signal["path"], "value": value}
                        )
        except (OSError, ValueError) as error:
            errors.append(f"{type(error).__name__}: {error}")
    return {
        "schema": SCHEMA,
        "kind": "vcd_extract",
        "pass": not errors,
        "errors": errors,
        "vcd": catalog.get("vcd"),
        "patterns": patterns,
        "start_time": start_time,
        "end_time": end_time,
        "selected_signals": list(selected.values()),
        "event_count": len(events),
        "events": events,
        "no_event_limit": True,
        "claim_boundary": "Selected VCD value changes only; family owner performs diagnosis.",
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    toolchain = commands.add_parser("toolchain")
    toolchain.add_argument("--output", type=Path, required=True)
    request = commands.add_parser("prepare-request")
    request.add_argument("--return-zip", type=Path, required=True)
    request.add_argument("--output", type=Path, required=True)
    convert = commands.add_parser("convert")
    convert.add_argument("--vpd", type=Path, required=True)
    convert.add_argument("--output-dir", type=Path, required=True)
    convert.add_argument("--converter", type=Path)
    convert.add_argument("--output", type=Path, required=True)
    fst = commands.add_parser("convert-fst")
    fst.add_argument("--vcd", type=Path, required=True)
    fst.add_argument("--output-dir", type=Path, required=True)
    fst.add_argument("--converter", type=Path)
    fst.add_argument("--output", type=Path, required=True)
    catalog = commands.add_parser("catalog-vcd")
    catalog.add_argument("--vcd", type=Path, required=True)
    catalog.add_argument("--output", type=Path, required=True)
    extract = commands.add_parser("extract-vcd")
    extract.add_argument("--vcd", type=Path, required=True)
    extract.add_argument("--signal-regex", action="append", required=True)
    extract.add_argument("--start-time", type=int)
    extract.add_argument("--end-time", type=int)
    extract.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Iterable[str] | None = None) -> int:
    args = parser().parse_args(list(argv) if argv is not None else None)
    if args.command == "toolchain":
        report = inspect_toolchain()
    elif args.command == "prepare-request":
        report = prepare_conversion_request(args.return_zip)
    elif args.command == "convert":
        report = convert_vpd(args.vpd, args.output_dir, args.converter)
    elif args.command == "convert-fst":
        report = convert_vcd_to_fst(args.vcd, args.output_dir, args.converter)
    elif args.command == "catalog-vcd":
        report = validate_vcd(args.vcd)
    else:
        report = extract_vcd(args.vcd, args.signal_regex, args.start_time, args.end_time)
    write_json(args.output, report)
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
