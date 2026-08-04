from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import node0004_hang_localization_runtime_v7 as base  # noqa: E402


RETURN_ALLOWLIST_BINDING = (
    "evidence/compile_exit_status.txt",
    "evidence/run_exit_status.txt",
    "evidence/signal_status.txt",
    "evidence/SERVER_RESULT_GATE.json",
    "runs/compile/sim_results/compile_driver.log",
    "runs/compile/sim_results/compile.log",
    "runs/c0/simulator_argv.txt",
    "runs/c0/sim.log",
    "runs/c0/return_observer.log",
    "runs/c0/host_progress.log",
)
CANONICAL_PREFIX = "| CANONICAL_DIAG_DECISION_V1 |"
REQUIRED_FIELDS = (
    "schema",
    "version",
    "decision",
    "reason",
    "boundary",
    "window_first",
    "window_last",
    "window_cycles",
    "qualified_progress",
    "qualified_delta",
    "req0",
    "req1",
    "req3",
    "rdata0",
    "rdata1",
    "rdata3",
    "d_req",
    "d_wdata",
    "content_digest",
)
INTEGER_FIELDS = (
    "version",
    "window_first",
    "window_last",
    "window_cycles",
    "qualified_progress",
    "qualified_delta",
    "req0",
    "req1",
    "req3",
    "rdata0",
    "rdata1",
    "rdata3",
    "d_req",
    "d_wdata",
)


package_records = base.package_records
preflight = base.preflight
sha256 = base.sha256
verify_install = base.verify_install
write_json = base.write_json
_base_collect = base.collect

RETURN_ZIP_MAX_BYTES = 16 * 1024 * 1024
RETURN_UNCOMPRESSED_MAX_BYTES = 32 * 1024 * 1024
RETURN_TEXT_MAX_BYTES = 8 * 1024 * 1024
REQUIRED_AFTER_COMPILE_SUCCESS = (
    "runs/c0/simulator_argv.txt",
    "runs/c0/sim.log",
    "runs/c0/return_observer.log",
    "runs/c0/host_progress.log",
)
FORBIDDEN_SUFFIXES = (
    ".vcd",
    ".fsdb",
    ".daidir",
    ".sdb",
    ".so",
    ".a",
    ".pyc",
    ".zip",
)


def parse_canonical_records(lines: list[str]) -> dict[str, Any]:
    candidates = [line for line in lines if CANONICAL_PREFIX in line]
    errors: list[str] = []
    parsed: list[dict[str, Any]] = []
    for index, line in enumerate(candidates):
        suffix = line.split(CANONICAL_PREFIX, 1)[1].strip()
        fields = dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", suffix))
        missing = [name for name in REQUIRED_FIELDS if name not in fields]
        if missing:
            errors.append(
                f"candidate[{index}] missing fields: {','.join(missing)}"
            )
            continue
        try:
            numeric = {name: int(fields[name]) for name in INTEGER_FIELDS}
        except ValueError:
            errors.append(f"candidate[{index}] has non-integer field")
            continue
        if fields["schema"] != "node0004_hang_diag" or numeric["version"] != 1:
            errors.append(f"candidate[{index}] schema/version differs")
        if numeric["window_first"] != 1:
            errors.append(f"candidate[{index}] window_first differs")
        if (
            numeric["window_last"] < numeric["window_first"]
            or numeric["window_cycles"] <= 0
        ):
            errors.append(f"candidate[{index}] window range invalid")
        qualified_sum = sum(
            numeric[name]
            for name in (
                "req0",
                "req1",
                "req3",
                "rdata0",
                "rdata1",
                "rdata3",
                "d_req",
                "d_wdata",
            )
        )
        if qualified_sum != numeric["qualified_progress"]:
            errors.append(f"candidate[{index}] qualified sum differs")
        expected_digest = (
            f"QIOV1_{numeric['qualified_progress']}_"
            f"{numeric['qualified_delta']}_{numeric['window_last']}"
        )
        if fields["content_digest"] != expected_digest:
            errors.append(f"candidate[{index}] content digest differs")
        expected_decision = {
            "STALL_WINDOW_EXCEEDED": (
                f"LONG_RUNNING_HANG_AT_{fields['boundary']}"
            ),
            "MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING": "STILL_PROGRESSING",
            "MAX_DIAGNOSTIC_CYCLE_BUDGET_INSUFFICIENT_PROGRESS": (
                "EVIDENCE_INSUFFICIENT"
            ),
        }.get(fields["reason"])
        if expected_decision is None or fields["decision"] != expected_decision:
            errors.append(f"candidate[{index}] decision/reason differs")
        parsed.append({"line": line, "fields": fields, "numeric": numeric})
    if len(candidates) > 1:
        errors.append(f"canonical candidate count is {len(candidates)}")
    valid = len(candidates) == 1 and len(parsed) == 1 and not errors
    return {
        "valid": valid,
        "candidate_count": len(candidates),
        "parsed_count": len(parsed),
        "errors": errors,
        "record": parsed[0] if valid else None,
    }


def _integer_fields(line: str) -> dict[str, int]:
    fields = dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", line))
    result: dict[str, int] = {}
    for name in (
        "sample",
        "qualified_progress",
        "delta",
        "req0",
        "req1",
        "req3",
        "rdata0",
        "rdata1",
        "rdata3",
        "d_req",
        "d_wdata",
    ):
        try:
            result[name] = int(fields.get(name, "0"))
        except ValueError:
            result[name] = 0
    return result


def _boundary_from_counters(counters: dict[str, int]) -> str:
    if counters["req0"] + counters["req1"] + counters["req3"] == 0:
        return "LC_TO_READ_REQUEST"
    if counters["rdata0"] + counters["rdata1"] + counters["rdata3"] == 0:
        return "READ_REQUEST_TO_MEMORY_DATA"
    if counters["d_req"] == 0:
        return "READ_DATA_TO_D_WRITE_REQUEST_UNRESOLVED_INTERNAL"
    if counters["d_wdata"] == 0:
        return "D_WRITE_REQUEST_TO_D_WRITE_DATA"
    return "D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"


def _fallback_canonical(
    progress_lines: list[str], signal_status: str
) -> dict[str, Any]:
    counters = _integer_fields(progress_lines[-1]) if progress_lines else {
        name: 0
        for name in (
            "sample",
            "qualified_progress",
            "delta",
            "req0",
            "req1",
            "req3",
            "rdata0",
            "rdata1",
            "rdata3",
            "d_req",
            "d_wdata",
        )
    }
    sample = max(1, counters["sample"])
    fields = {
        "schema": "node0004_hang_diag",
        "version": 1,
        "decision": "EVIDENCE_INSUFFICIENT",
        "reason": "EXTERNAL_SIGNAL_BEFORE_OBSERVER_CANONICAL",
        "boundary": _boundary_from_counters(counters),
        "window_first": 1,
        "window_last": sample,
        "window_cycles": 262144,
        "qualified_progress": counters["qualified_progress"],
        "qualified_delta": counters["delta"],
        "req0": counters["req0"],
        "req1": counters["req1"],
        "req3": counters["req3"],
        "rdata0": counters["rdata0"],
        "rdata1": counters["rdata1"],
        "rdata3": counters["rdata3"],
        "d_req": counters["d_req"],
        "d_wdata": counters["d_wdata"],
        "content_digest": (
            f"QIOV1_{counters['qualified_progress']}_"
            f"{counters['delta']}_{sample}"
        ),
        "source": "PACKAGE_RUNTIME_EXTERNAL_SIGNAL_FALLBACK",
        "signal_status": signal_status,
    }
    return {"line": None, "fields": fields, "numeric": counters}


def _safe_member(name: str) -> PurePosixPath:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name:
        raise base.DiagnosticRuntimeError(f"unsafe return ZIP member: {name}")
    return pure


def _stream_sha256(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str:
    digest = hashlib.sha256()
    with archive.open(info) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_return_zip(
    return_zip: Path,
    return_sha: Path,
    *,
    zip_max_bytes: int = RETURN_ZIP_MAX_BYTES,
    uncompressed_max_bytes: int = RETURN_UNCOMPRESSED_MAX_BYTES,
    text_max_bytes: int = RETURN_TEXT_MAX_BYTES,
) -> dict[str, Any]:
    if not return_zip.is_file() or not return_sha.is_file():
        raise base.DiagnosticRuntimeError("return ZIP or sidecar missing")
    if return_zip.stat().st_size > zip_max_bytes:
        raise base.DiagnosticRuntimeError("return ZIP exceeds compressed budget")
    sidecar = return_sha.read_text(encoding="ascii").split()
    digest = sha256(return_zip)
    if (
        len(sidecar) != 2
        or sidecar[0] != digest
        or sidecar[1] != return_zip.name
    ):
        raise base.DiagnosticRuntimeError("return sidecar differs")
    with zipfile.ZipFile(return_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise base.DiagnosticRuntimeError(f"return ZIP CRC failure: {bad}")
        infos = [item for item in archive.infolist() if not item.is_dir()]
        roots = {_safe_member(item.filename).parts[0] for item in infos}
        if len(roots) != 1:
            raise base.DiagnosticRuntimeError("return ZIP root differs")
        root = next(iter(roots))
        by_relative: dict[str, zipfile.ZipInfo] = {}
        total = 0
        for info in infos:
            pure = _safe_member(info.filename)
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in by_relative:
                raise base.DiagnosticRuntimeError(
                    f"duplicate return member: {relative}"
                )
            by_relative[relative] = info
            total += info.file_size
            if info.file_size > text_max_bytes:
                raise base.DiagnosticRuntimeError(
                    f"return text exceeds budget: {relative}"
                )
            if (
                "__pycache__" in pure.parts
                or relative.endswith(FORBIDDEN_SUFFIXES)
            ):
                raise base.DiagnosticRuntimeError(
                    f"forbidden return member: {relative}"
                )
        if total > uncompressed_max_bytes:
            raise base.DiagnosticRuntimeError(
                "return ZIP exceeds uncompressed budget"
            )
        allow_info = by_relative.get("RETURN_ALLOWLIST.json")
        if allow_info is None:
            raise base.DiagnosticRuntimeError("return allowlist missing")
        allowlist = json.loads(archive.read(allow_info))
        records = allowlist.get("records")
        if not isinstance(records, list):
            raise base.DiagnosticRuntimeError("return allowlist records invalid")
        expected = {"RETURN_ALLOWLIST.json"}
        for record in records:
            relative = record.get("path")
            if not isinstance(relative, str):
                raise base.DiagnosticRuntimeError(
                    "return allowlist path invalid"
                )
            expected.add(relative)
            info = by_relative.get(relative)
            if info is None:
                raise base.DiagnosticRuntimeError(
                    f"allowlisted return member missing: {relative}"
                )
            if record.get("size_bytes") != info.file_size:
                raise base.DiagnosticRuntimeError(
                    f"return size differs: {relative}"
                )
            if record.get("sha256") != _stream_sha256(archive, info):
                raise base.DiagnosticRuntimeError(
                    f"return SHA differs: {relative}"
                )
        if set(by_relative) != expected:
            raise base.DiagnosticRuntimeError("return exact-set differs")
        compile_info = by_relative.get("evidence/compile_exit_status.txt")
        if compile_info is None:
            raise base.DiagnosticRuntimeError("compile status missing")
        try:
            compile_status = int(
                archive.read(compile_info).decode("ascii").strip()
            )
        except ValueError as error:
            raise base.DiagnosticRuntimeError(
                "compile status invalid"
            ) from error
        if compile_status == 0:
            missing = [
                relative
                for relative in REQUIRED_AFTER_COMPILE_SUCCESS
                if relative not in by_relative
            ]
            if missing:
                raise base.DiagnosticRuntimeError(
                    "required progress diagnostic missing after compile "
                    f"success: {','.join(missing)}"
                )
    return {
        "schema": "node0004-return-zip-gate-v12",
        "valid": True,
        "zip": str(return_zip),
        "zip_sha256": digest,
        "zip_bytes": return_zip.stat().st_size,
        "uncompressed_bytes": total,
        "entry_count": len(by_relative),
        "root": root,
        "compile_exit_status": compile_status,
        "required_progress_diagnostics_present": compile_status != 0
        or all(name in by_relative for name in REQUIRED_AFTER_COMPILE_SUCCESS),
        "exact_set_valid": True,
    }


def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
) -> dict[str, Any]:
    result = _base_collect(server_root, install_name, evidence_root, run_root)
    return_zip = server_root / f"{install_name}_return.zip"
    return_sha = Path(str(return_zip) + ".sha256")
    result["final_return_gate"] = validate_return_zip(return_zip, return_sha)
    return result


def analyze(
    package_root: Path, evidence_root: Path, run_root: Path
) -> dict[str, Any]:
    compile_status = base._status(evidence_root / "compile_exit_status.txt")
    run_status = base._status(evidence_root / "run_exit_status.txt")
    observer = run_root / "c0/return_observer.log"
    lines = (
        observer.read_text(encoding="utf-8", errors="replace").splitlines()
        if observer.is_file()
        else []
    )
    progress_lines = [line for line in lines if "| PROGRESS_WINDOW |" in line]
    finish_lines = [line for line in lines if "| COMP_FINISH |" in line]
    canonical = parse_canonical_records(lines)
    record = canonical["record"]
    signal_path = evidence_root / "signal_status.txt"
    signal_status = (
        signal_path.read_text(encoding="ascii", errors="replace").strip()
        if signal_path.is_file()
        else "MISSING"
    )
    fallback_used = False
    if finish_lines:
        status = "C0_NATURAL_TERMINAL_OBSERVED_DIAGNOSTIC_ONLY"
    elif canonical["candidate_count"] and not canonical["valid"]:
        status = "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
    elif record:
        status = record["fields"]["decision"]
    else:
        record = _fallback_canonical(progress_lines, signal_status)
        fallback_used = True
        status = "EVIDENCE_INSUFFICIENT"
    value = {
        "schema": "node0004-hang-localization-result-v12",
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "status": status,
        "compile_exit_status": compile_status,
        "run_exit_status": run_status,
        "compile_succeeded": compile_status == 0,
        "natural_terminal_observed": bool(finish_lines),
        "progress_window_count": len(progress_lines),
        "last_progress_window": progress_lines[-1] if progress_lines else None,
        "canonical_decision": record,
        "canonical_fallback_used": fallback_used,
        "signal_status": signal_status,
        "canonical_validation": {
            "valid": canonical["valid"],
            "candidate_count": canonical["candidate_count"],
            "parsed_count": canonical["parsed_count"],
            "errors": canonical["errors"],
        },
        "formal_readback_claimed": False,
        "e4_claimed": False,
        "e5_claimed": False,
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", value)
    return value


def main() -> int:
    base.analyze = analyze
    base.collect = collect
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
