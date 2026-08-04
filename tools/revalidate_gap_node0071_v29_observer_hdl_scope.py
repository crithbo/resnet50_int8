from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n71_gap_v29_mse0_buffer_prep_group0_diag"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
EXPECTED_ZIP_SHA256 = "15833d826872e118a9be834b082351ae2b31862da0b138a2a4f271269108e164"
EXPECTED_ZIP_BYTES = 1_818_768
ANCHOR = "    // v29: bounded MSE0 Buffer0-to-prepared-to-GA-group0 diagnostic."
DECL_END = "\n    bit return_obs_enabled;"
SAMPLER_ANCHOR = "    // v29 qualified edge/event sampler; stable levels are state only."
SAMPLER_END = "\n    final begin"
CRITICAL_UPDATE = "return_obs_m0path_group0_accept_count++;"
PREFIX = "return_obs_m0path_"
REQUIRED = {
    "return_obs_m0path_enabled",
    "return_obs_m0path_limit",
    "return_obs_m0path_emit_count",
    "return_obs_m0path_buf_accept_count",
    "return_obs_m0path_arm_accept_count",
    "return_obs_m0path_arm_clear_count",
    "return_obs_m0path_prep_wr_count",
    "return_obs_m0path_prep_rd_count",
    "return_obs_m0path_data_vld_count",
    "return_obs_m0path_group0_accept_count",
    "return_obs_m0path_reset",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], cwd: Path | None = None) -> dict[str, Any]:
    process = subprocess.run(
        argv, cwd=cwd, text=True, capture_output=True, check=False
    )
    return {
        "argv": argv,
        "cwd": str(cwd) if cwd else None,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "stdout_sha256": sha256_bytes(process.stdout.encode()),
        "stderr_sha256": sha256_bytes(process.stderr.encode()),
    }


def read_exact(path: Path) -> tuple[str, dict[str, Any]]:
    if path.stat().st_size != EXPECTED_ZIP_BYTES:
        raise ValueError("final ZIP byte size differs")
    if sha256_path(path) != EXPECTED_ZIP_SHA256:
        raise ValueError("final ZIP SHA256 differs")
    member = f"{INSTALL_NAME}/{OBSERVER_RELATIVE}"
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC differs")
        payload = archive.read(member)
    return payload.decode("utf-8"), {
        "zip": str(path),
        "zip_size_bytes": path.stat().st_size,
        "zip_sha256": sha256_path(path),
        "observer_member": member,
        "observer_size_bytes": len(payload),
        "observer_sha256": sha256_bytes(payload),
    }


def section(text: str, start_token: str, end_token: str) -> str:
    start = text.find(start_token)
    end = text.find(end_token, start)
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"focused section absent: {start_token}")
    return text[start:end]


def ledger(observer: str) -> dict[str, Any]:
    decl = section(observer, ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    identifiers = set(re.findall(r"\breturn_obs_m0path_[A-Za-z0-9_]+\b", decl + sampler))
    declared = set(
        re.findall(
            r"\b(?:bit|int|longint unsigned)\s+(return_obs_m0path_[A-Za-z0-9_]+)",
            decl,
        )
    )
    declared.update(
        re.findall(
            r"\btask\s+automatic\s+(return_obs_m0path_[A-Za-z0-9_]+)",
            decl,
        )
    )
    missing_decl = sorted((identifiers & REQUIRED) - declared)
    missing_required = sorted(REQUIRED - identifiers)
    undeclared = sorted(identifiers - declared)
    updates = {
        name: len(re.findall(rf"\b{re.escape(name)}\s*(?:\+\+|=)", decl + sampler))
        for name in REQUIRED
        if name.endswith("_count")
    }
    required_records = [
        "MSE0_BUFFER_PREP_GROUP0_EVENT_V1",
        "MSE0_BUFFER_PREP_GROUP0_COUNTS_V1",
        "MSE0_BUFFER_PREP_GROUP0_STATE_V1",
        "MSE0_BUFFER_PREP_GROUP0_WITNESS_V1",
    ]
    return {
        "scope_prefix": PREFIX,
        "identifiers": sorted(identifiers),
        "declared": sorted(declared),
        "missing_declarations": missing_decl,
        "undeclared_identifiers": undeclared,
        "missing_required_identifiers": missing_required,
        "qualified_counter_updates": updates,
        "critical_update_present": CRITICAL_UPDATE in sampler,
        "required_records_present": {
            item: item in observer for item in required_records
        },
        "valid": (
            not missing_decl
            and not undeclared
            and not missing_required
            and all(count > 0 for count in updates.values())
            and CRITICAL_UPDATE in sampler
            and all(item in observer for item in required_records)
        ),
    }


def projection_source(observer: str) -> str:
    decl = section(observer, ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    update_lines = []
    for line in sampler.splitlines():
        stripped = line.strip()
        if stripped.startswith(PREFIX) and (
            stripped.endswith("++;") or " = return_obs_sg_clock_edge_count;" in stripped
        ):
            update_lines.append("        " + stripped)
    if CRITICAL_UPDATE not in "\n".join(update_lines):
        raise ValueError("critical update absent from exact sampler projection")
    return (
        "`timescale 1ns/1ps\n"
        "module v29_mse0_path_projection;\n"
        + decl
        + "\n    longint unsigned return_obs_sg_clock_edge_count;\n"
        "    initial begin\n"
        "        return_obs_sg_clock_edge_count = 1;\n"
        "        return_obs_m0path_reset();\n"
        + "\n".join(update_lines)
        + "\n        if (return_obs_m0path_group0_accept_count != 1) $fatal;\n"
        "    end\n"
        "endmodule\n"
    )


def evaluate(
    observer: str, iverilog: Path, temporary: Path, stem: str
) -> dict[str, Any]:
    closure = ledger(observer)
    try:
        source = projection_source(observer)
        source_path = temporary / f"{stem}.sv"
        source_path.write_text(source, encoding="utf-8", newline="\n")
        compile_result = run(
            [
                str(iverilog),
                "-g2012",
                "-tnull",
                "-s",
                "v29_mse0_path_projection",
                str(source_path),
            ],
            temporary,
        )
        projection_sha = sha256_bytes(source.encode())
    except Exception as error:
        compile_result = {"exit_code": 1, "stdout": "", "stderr": str(error)}
        projection_sha = None
    return {
        "valid": closure["valid"] and compile_result["exit_code"] == 0,
        "scoped_identifier_closure": closure,
        "projection_compile": compile_result,
        "projection_sha256": projection_sha,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--iverilog",
        type=Path,
        default=Path(r"C:\iverilog\bin\iverilog.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        observer, receipt = read_exact(args.target_zip.resolve())
        version = run([str(args.iverilog.resolve()), "-V"])
        with tempfile.TemporaryDirectory(prefix="gap-v29-hdl-") as temp:
            temporary = Path(temp)
            positive = evaluate(
                observer, args.iverilog.resolve(), temporary, "positive"
            )
            mutations = {
                "delete_required_declaration": observer.replace(
                    "    bit return_obs_m0path_enabled;\n", "", 1
                ),
                "typo_required_use": observer.replace(
                    "            return_obs_m0path_enabled &&\n",
                    "            return_obs_m0path_enabled_typo &&\n",
                    1,
                ),
                "delete_required_update": observer.replace(
                    "                return_obs_m0path_group0_accept_count++;\n",
                    "",
                    1,
                ),
            }
            negatives = {
                name: evaluate(
                    mutated, args.iverilog.resolve(), temporary, f"negative_{name}"
                )
                for name, mutated in mutations.items()
            }
        all_negatives = all(not item["valid"] for item in negatives.values())
        passed = positive["valid"] and all_negatives
        result = {
            "schema": "gap-node0071-v29-focused-observer-hdl-scope-v1",
            "status": "PASS" if passed else "FAIL",
            "pass": passed,
            "rule_id": (
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-"
                "POSITIVE-001"
            ),
            "target_receipt": receipt,
            "tool": {
                "name": "iverilog",
                "version_command": version,
            },
            "positive": positive,
            "negative_controls": {
                name: {
                    "failed_closed": not item["valid"],
                    "closure_valid": item["scoped_identifier_closure"]["valid"],
                    "compile_exit_code": item["projection_compile"]["exit_code"],
                }
                for name, item in negatives.items()
            },
            "all_negative_controls_fail_closed": all_negatives,
            "scope": (
                "exact final v29 declarations/reset/update/use and required "
                "record identifiers only; inherited XMR/full-design "
                "elaboration not repeated"
            ),
            "full_design_elaboration_claimed": False,
            "server_source_files_inspected": False,
            "package_bytes_changed": False,
        }
    except Exception as error:
        result = {
            "schema": "gap-node0071-v29-focused-observer-hdl-scope-v1",
            "status": "FAIL",
            "pass": False,
            "error": str(error),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
