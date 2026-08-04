from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RETURN_SHA256 = (
    "5a075ae69e0f89aa2da356c9968ea79de099ec7b38e1ba20b19c8a6757d2525d"
)
EXPECTED_RETURN_BYTES = 28346
EXPECTED_SOURCE_SHA256 = (
    "4bf890b5ad57d8952226125de4979e96e0c00a1d347d2fb59aec7cabb1cf44b2"
)
EXPECTED_INSTALL_NAME = "r5_n4_hw_v14_a_pingpong_fix"
EXPECTED_OBSERVER_SHA256 = (
    "a40c522fc3dc962dedcda76291df97bb856315c82ff71fbd593127c541322b0a"
)


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

    _, source_payloads = entries(source_zip)
    source_manifest = json.loads(source_payloads["package_manifest.json"])
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
    compile_log = observed[
        "runs/compile/sim_results/compile.log"
    ].decode("utf-8", errors="replace")
    driver_log = observed[
        "runs/compile/sim_results/compile_driver.log"
    ].decode("utf-8", errors="replace")
    syntax_match = re.search(
        r"native_return_observer\.svh[\"'],\s*2405.*?token is",
        compile_log,
        re.DOTALL,
    )
    source_observer = source_payloads[
        "tb_probe/native_return_observer.svh"
    ].decode("utf-8")
    expression_present = (
        "return_obs_abpe_masked_valid_mon" in source_observer
        and "[`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][0]"
        in source_observer
        and "[`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][0]"
        in compile_log
    )
    package_identity = (
        allowlist.get("install_name") == EXPECTED_INSTALL_NAME
        and source_manifest.get("install_name") == EXPECTED_INSTALL_NAME
        and package_preflight.get("install_name") == EXPECTED_INSTALL_NAME
    )
    observer_identity = (
        package_preflight.get("observer_sha256") == EXPECTED_OBSERVER_SHA256
        and observer_precompile.get("expected_sha256")
        == EXPECTED_OBSERVER_SHA256
        and observer_precompile.get("observed_sha256")
        == EXPECTED_OBSERVER_SHA256
        and source_manifest.get("observer_sha256") == EXPECTED_OBSERVER_SHA256
    )
    preflight_valid = (
        package_preflight.get("valid") is True
        and install_preflight.get("valid") is True
        and observer_precompile.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
        and observer_precompile.get("identity_match") is True
    )
    if not package_identity:
        errors.append("package/install identity differs")
    if not observer_identity:
        errors.append("observer identity differs")
    if not preflight_valid:
        errors.append("package/install/observer preflight differs")
    if not syntax_match or not expression_present:
        errors.append("expected VCS observer syntax first divergence not found")

    simulation_started = (
        compile_status == 0
        and "runs/c0/simulator_argv.txt" in observed
        and "runs/c0/sim.log" in observed
    )
    formal_d_members = sorted(
        name for name in observed if name.startswith("runs/c0/formal_d/")
    )
    joint_gate = (
        compile_status == 0
        and run_status == 0
        and signal_status == "NONE"
        and gate.get("natural_terminal_observed") is True
        and gate.get("formal_readback_claimed") is True
        and bool(formal_d_members)
    )
    if joint_gate:
        errors.append("unexpected dynamic pass after compile failure")

    return {
        "schema": "node0004-v14-return-analysis-v1",
        "status": (
            "PACKAGE_LOCAL_OBSERVER_VCS_SYNTAX_COMPILE_FAILURE"
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
            "install_name": allowlist.get("install_name"),
            "package_identity_valid": package_identity,
            "observer_sha256": EXPECTED_OBSERVER_SHA256,
            "observer_identity_valid": observer_identity,
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
            "valid": preflight_valid,
            "package": package_preflight,
            "install": install_preflight,
            "observer": observer_precompile,
        },
        "dynamic": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "simulation_started": simulation_started,
            "natural_terminal": gate.get("natural_terminal_observed", False),
            "canonical_progress_is_actual": False,
            "canonical_fallback_used": gate.get(
                "canonical_fallback_used", False
            ),
            "formal_d_member_count": len(formal_d_members),
            "formal_d_readback": gate.get("formal_readback_claimed", False),
            "mismatch_zero_with_all_missing_is_pass": False,
        },
        "first_divergence": {
            "boundary": "COMPILE_PACKAGE_LOCAL_RETURN_OBSERVER",
            "file": "tb_probe/native_return_observer.svh",
            "line": 2405,
            "tool": "VCS",
            "token": "[",
            "expression": (
                "runtime group/slice packed selects followed by whole "
                "ROW/COL packed ranges and final bit select"
            ),
            "compile_log_match": bool(syntax_match and expression_present),
            "driver_make_exit2": "make: ***" in driver_log,
        },
        "evidence_levels": {
            "E3": False,
            "E4": False,
            "E5": False,
            "joint_gate_passed": joint_gate,
            "reason": "compile failed before elaboration and simulation",
        },
        "adjudication": {
            "root_cause": "PACKAGE_LOCAL_READ_ONLY_OBSERVER_SYNTAX",
            "functional_rtl_implicated": False,
            "conv_configuration_implicated": False,
            "legal_minimal_fix": (
                "replace the rejected post-index packed slice with "
                "elaboration-time per-PE A/B aggregate monitor nets"
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
