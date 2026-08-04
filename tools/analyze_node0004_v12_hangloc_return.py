from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "4c6913a037b3211fbacb1c6c81bad29ea854b71787969ca6becff40450045efb"
)
EXPECTED_RETURN_BYTES = 76005
EXPECTED_SOURCE_SHA256 = (
    "80d489798af019b00bba7ee7a7b6060de9f4cf77c2b6e57b11955995803e2e6d"
)
EXPECTED_INSTALL_NAME = "r5_n4_hw_v12_hangloc_returngate"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def entries(path: Path) -> tuple[str, dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        crc_failure = archive.testzip()
        if crc_failure is not None:
            raise ValueError(f"CRC failure: {crc_failure}")
        infos = [item for item in archive.infolist() if not item.is_dir()]
        roots: set[str] = set()
        result: dict[str, bytes] = {}
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise ValueError(f"unsafe member: {info.filename}")
            roots.add(pure.parts[0])
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in result:
                raise ValueError(f"duplicate member: {relative}")
            result[relative] = archive.read(info)
    if len(roots) != 1:
        raise ValueError(f"return root differs: {sorted(roots)}")
    return next(iter(roots)), result


def parse_internal_state(text: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if "| INTERNAL_STATE |" in line]
    if not lines:
        return {}
    return dict(re.findall(r"(\w+)=([^\s]+)", lines[-1]))


def analyze(
    return_zip: Path,
    sidecar: Path,
    source_zip: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    return_sha = sha256_file(return_zip)
    return_bytes = return_zip.stat().st_size
    if return_sha != EXPECTED_RETURN_SHA256:
        errors.append("return ZIP SHA differs")
    if return_bytes != EXPECTED_RETURN_BYTES:
        errors.append("return ZIP byte size differs")
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    sidecar_valid = (
        len(sidecar_tokens) == 2
        and sidecar_tokens[0] == return_sha
        and sidecar_tokens[1] == return_zip.name
    )
    if not sidecar_valid:
        errors.append("external sidecar differs")
    source_sha = sha256_file(source_zip)
    if source_sha != EXPECTED_SOURCE_SHA256:
        errors.append("source package SHA differs")

    root, payloads = entries(return_zip)
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    records = {item["path"]: item for item in allowlist["records"]}
    observed = {
        relative: payload
        for relative, payload in payloads.items()
        if relative != "RETURN_ALLOWLIST.json"
    }
    exact_set = set(records) == set(observed)
    if not exact_set:
        errors.append("return exact-set differs from allowlist")
    mismatched_records: list[str] = []
    for relative in sorted(set(records) & set(observed)):
        record = records[relative]
        payload = observed[relative]
        if (
            record["size_bytes"] != len(payload)
            or record["sha256"] != sha256_bytes(payload)
        ):
            mismatched_records.append(relative)
    if mismatched_records:
        errors.append("return allowlist hashes/sizes differ")

    package_preflight = json.loads(observed["evidence/package_preflight.json"])
    install_preflight = json.loads(observed["evidence/install_preflight.json"])
    observer_precompile = json.loads(
        observed["evidence/observer_precompile.json"]
    )
    gate = json.loads(observed["evidence/SERVER_RESULT_GATE.json"])
    compile_status = int(
        observed["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        observed["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = observed["evidence/signal_status.txt"].decode().strip()
    observer = observed["runs/c0/return_observer.log"].decode(
        "utf-8", errors="replace"
    )
    sim_log = observed["runs/c0/sim.log"].decode(
        "utf-8", errors="replace"
    )
    progress_lines = [
        line for line in observer.splitlines() if "| PROGRESS_WINDOW |" in line
    ]
    canonical_lines = [
        line
        for line in observer.splitlines()
        if "| CANONICAL_DIAG_DECISION_V1 |" in line
    ]
    last_state = parse_internal_state(observer)
    four_zero_windows = (
        len(progress_lines) == 5
        and all("delta=0" in line for line in progress_lines[-4:])
    )
    no_natural_terminal = not gate["natural_terminal_observed"]
    no_formal_d = not gate["formal_readback_claimed"]
    sim_bounded_stop = (
        "RETURN_HANG_DIAG stopped after bounded no-progress window" in sim_log
        and "$finish at simulation time" in sim_log
    )
    formal_joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal_status == "NONE"
        and not no_natural_terminal
        and not no_formal_d
    )
    if formal_joint_gate:
        errors.append("unexpected formal pass from a diagnostic stop")

    return {
        "schema": "node0004-v12-hangloc-return-analysis-v1",
        "status": (
            "LONG_RUNNING_HANG_PENDING_NARROW_ABPE_BOUNDARY"
            if not errors
            else "RETURN_IDENTITY_OR_CONTRACT_FAILURE"
        ),
        "valid": not errors,
        "errors": errors,
        "identity": {
            "return_zip": str(return_zip.resolve()),
            "return_zip_bytes": return_bytes,
            "return_zip_sha256": return_sha,
            "sidecar": str(sidecar.resolve()),
            "sidecar_sha256": sha256_file(sidecar),
            "sidecar_valid": sidecar_valid,
            "source_zip": str(source_zip.resolve()),
            "source_zip_sha256": source_sha,
            "install_name": allowlist["install_name"],
            "install_name_valid": (
                allowlist["install_name"] == EXPECTED_INSTALL_NAME
            ),
        },
        "return_envelope": {
            "crc_pass": True,
            "single_root": root,
            "entry_count": len(payloads),
            "exact_set_valid": exact_set,
            "allowlist_record_count": len(records),
            "hash_size_mismatches": mismatched_records,
        },
        "preflight": {
            "package": package_preflight,
            "install": install_preflight,
            "observer": observer_precompile,
        },
        "dynamic": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "simulation_started": True,
            "bounded_diagnostic_stop": sim_bounded_stop,
            "natural_terminal": not no_natural_terminal,
            "formal_d_readback": not no_formal_d,
            "progress_window_count": len(progress_lines),
            "four_consecutive_zero_delta_windows": four_zero_windows,
            "canonical_decision_count": len(canonical_lines),
            "canonical": gate["canonical_decision"],
            "last_internal_state": last_state,
        },
        "joint_gate": {
            "passed": formal_joint_gate,
            "compile0": compile_status == 0,
            "run0": run_status == 0,
            "signal_none": signal_status == "NONE",
            "natural_terminal": not no_natural_terminal,
            "formal_readback": not no_formal_d,
            "missing_all_mismatch_zero_is_pass": False,
        },
        "adjudication": {
            "last_good": (
                "c0 Start_Comp; qualified A/B/C requests and read data; "
                "one Buffer4 read-edge witness"
            ),
            "first_bad": (
                "before the first qualified Buffer5 write and before any "
                "visible SA group result"
            ),
            "root_cause": "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT",
            "why_not_config_fix": (
                "v12 lacks per-PE masked A/B, ALU-accept, PE-outbuffer, and "
                "SA-group-output qualified boundaries; stream and SA "
                "ping-pong are both disabled, so no unilateral ping-pong "
                "mismatch is proven"
            ),
            "narrow_missing_boundary": (
                "buffer0/2 group acceptance -> per-PE masked operand match -> "
                "ALU accept -> PE outbuffer accept -> SA group output"
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_source_consumed_read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.return_zip, args.sidecar, args.source_zip)
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
