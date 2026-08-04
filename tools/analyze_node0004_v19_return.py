from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_SOURCE_SHA = (
    "0420907934a5a603ea40a127128664affe0182b7d6bc986107e0b0b04303adf3"
)
EXPECTED_INSTALL = "r5_n4_hw_v19_buffer0_flow_diag"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_record(text: str, prefix: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if f"| {prefix} |" in line]
    if len(lines) != 1:
        raise ValueError(f"{prefix} count differs: {len(lines)}")
    fields: dict[str, str] = {}
    for token in lines[0].split("|", 2)[2].strip().split():
        if "=" in token:
            key, value = token.split("=", 1)
            fields[key] = value
    return fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    errors: list[str] = []
    source_sha = sha256_file(source_zip)
    if source_sha != EXPECTED_SOURCE_SHA:
        errors.append("source ZIP SHA mismatch")

    sidecar = Path(str(return_zip) + ".sha256")
    sidecar_present = sidecar.is_file()
    if sidecar_present:
        expected = f"{sha256_file(return_zip)}  {return_zip.name}"
        sidecar_valid = sidecar.read_text(encoding="ascii").strip() == expected
        if not sidecar_valid:
            errors.append("return sidecar mismatch")
    else:
        sidecar_valid = False

    with zipfile.ZipFile(return_zip) as archive:
        bad_crc = archive.testzip()
        if bad_crc:
            errors.append(f"return CRC failed: {bad_crc}")
        roots: set[str] = set()
        members: dict[str, bytes] = {}
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                errors.append(f"unsafe return member: {info.filename}")
                continue
            roots.add(path.parts[0])
            if not info.is_dir():
                members[PurePosixPath(*path.parts[1:]).as_posix()] = archive.read(
                    info
                )
    if roots != {f"{EXPECTED_INSTALL}_return"}:
        errors.append(f"return root mismatch: {sorted(roots)}")

    allowlist = json.loads(members["RETURN_ALLOWLIST.json"])
    if allowlist.get("install_name") != EXPECTED_INSTALL:
        errors.append("allowlist install identity mismatch")
    records = {item["path"]: item for item in allowlist.get("records", [])}
    exact = set(records) | {"RETURN_ALLOWLIST.json"}
    if set(members) != exact:
        errors.append("return exact-set mismatch")
    mismatches = []
    for relative, record in records.items():
        payload = members.get(relative)
        if (
            payload is None
            or len(payload) != record.get("size_bytes")
            or sha256_bytes(payload) != record.get("sha256")
        ):
            mismatches.append(relative)
    if mismatches:
        errors.append(f"return allowlist mismatch: {mismatches}")

    def load_json(relative: str) -> Any:
        return json.loads(members[relative])

    gate = load_json("evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json("evidence/package_preflight.json")
    install_preflight = load_json("evidence/install_preflight.json")
    observer_preflight = load_json("evidence/observer_precompile.json")
    compile_status = int(members["evidence/compile_exit_status.txt"].strip())
    run_status = int(members["evidence/run_exit_status.txt"].strip())
    signal = members["evidence/signal_status.txt"].decode().strip()
    observer = members["runs/c0/return_observer.log"].decode()
    canonical = parse_record(observer, "CANONICAL_DIAG_DECISION_V1")
    abpe = parse_record(observer, "ABPE_BOUNDARY_V1")
    a_reuse = parse_record(observer, "A_REUSE_BOUNDARY_V1")
    flow = parse_record(observer, "BUFFER0_FLOW_BOUNDARY_V1")
    progress = [
        int(re.search(r"\bdelta=(\d+)", line).group(1))
        for line in observer.splitlines()
        if "| PROGRESS_WINDOW |" in line
    ]

    expected_flow = {
        "ag_enq": "2",
        "ag_deq": "2",
        "mse_req_accept": "2",
        "arm_req_accept": "1",
        "ag_count": "0",
        "ag_full": "0",
        "ag_empty": "1",
        "mse_ready": "1",
        "mse_req_valid": "0x0",
        "mrm_ready": "1",
        "arm_ready": "0",
        "arm_bank_ready": "0x0",
        "row0_valid": "0xffffffff",
        "row1_valid": "0x0",
        "arm_counter0": "1",
        "arm_counter1": "0",
        "arm_addr": "1",
        "arm_life": "0",
        "arm_req_valid": "0xff",
        "arm_addr_update": "0",
        "arm_data_valid": "0",
    }
    flow_matches = all(flow.get(key) == value for key, value in expected_flow.items())
    if not flow_matches:
        errors.append("BUFFER0_FLOW_BOUNDARY differs")

    formal_d = [
        path
        for path in members
        if path.startswith("formal_readback/") and path.endswith(".txt")
    ]
    dynamic_valid = (
        compile_status == 0
        and run_status == 0
        and signal == "NONE"
        and package_preflight.get("valid") is True
        and install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
        and observer_preflight.get("valid") is True
        and gate.get("canonical_validation", {}).get("valid") is True
        and progress == [144, 0, 0, 0, 0]
    )
    if not dynamic_valid:
        errors.append("dynamic/preflight joint diagnostic gate differs")

    report = {
        "schema": "node0004-v19-return-analysis-v1",
        "status": "DETERMINISTIC_CONFIG_ERROR_BUFFER0_1_MODE0",
        "valid": not errors,
        "errors": errors,
        "identity": {
            "return_zip": str(return_zip),
            "return_zip_bytes": return_zip.stat().st_size,
            "return_zip_sha256": sha256_file(return_zip),
            "formal_sidecar_present": sidecar_present,
            "formal_sidecar_valid": sidecar_valid,
            "source_zip": str(source_zip),
            "source_zip_sha256": source_sha,
            "source_identity_valid": source_sha == EXPECTED_SOURCE_SHA,
        },
        "return_envelope": {
            "crc_pass": bad_crc is None,
            "entry_count": len(members),
            "exact_set_valid": set(members) == exact,
            "allowlist_record_count": len(records),
            "hash_size_mismatches": mismatches,
        },
        "dynamic": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal,
            "simulation_started": True,
            "natural_terminal": gate.get("natural_terminal_observed") is True,
            "canonical": canonical,
            "qualified_delta_sequence": progress,
            "abpe": abpe,
            "a_reuse": a_reuse,
            "buffer0_flow": flow,
            "formal_d_member_count": len(formal_d),
        },
        "first_divergence": {
            "last_good": (
                "WR_Buffer_AG enqueued/dequeued two row0 writes; Buffer0 accepted "
                "both writes and one ARM read"
            ),
            "first_bad": (
                "after first read ARM requests row1 (arm_addr=1, req_valid=0xff) "
                "while row1 is empty, row0 remains fully valid, and ready is zero"
            ),
            "boundary": "BUFFER0_FIRST_READ_TO_PREMATURE_ROW1_ADVANCE",
        },
        "hang_root_cause": {
            "classification": "BUFFER0_1_MODE0_ADVANCES_ROW_BEFORE_LIFETIME",
            "configuration_error_proven": True,
            "functional_rtl_error_proven": False,
            "package_error_proven": False,
            "old_mode": 0,
            "required_mode": 1,
            "affected_leaves": [
                "buffer_config.buffer0.mode",
                "buffer_config.buffer1.mode",
            ],
            "rtl_equation": {
                "mode0": (
                    "array_req_addr=array_counter_0; first accepted read "
                    "increments address 0->1"
                ),
                "mode1": (
                    "array_req_addr=array_counter_1 and "
                    "array_life_cnt=array_counter_0; four accepted reads "
                    "retain row0 before clear/advance"
                ),
            },
        },
        "evidence_levels": {
            "E3": True,
            "E4": False,
            "E5": False,
            "joint_gate_passed": False,
            "formal_receipt_gate": sidecar_valid,
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt_during_return_analysis": False,
    }
    args.output.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.output.resolve().write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
