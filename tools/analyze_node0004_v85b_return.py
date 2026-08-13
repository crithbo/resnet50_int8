#!/usr/bin/env python3
"""Validate and adjudicate the exact serialized-Conv v85b formal return.

This analyzer is intentionally read-only with respect to the supplied return and
source ZIPs.  It verifies archive safety, the return-core receipts, source
package binding, and the seven bootstrap compile-rootcause files before
classifying the first production compiler error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v85b_compile_rootcause"
RETURN_ROOT = f"{PACKAGE}_return"
EXECUTION_ID = "r1786447856031491701_1116783"
RETURN_BASENAME = f"{PACKAGE}_{EXECUTION_ID}_return.zip"
RETURN_BYTES = 60_848
RETURN_SHA256 = "a2de42f82e288f5c0739649bbeb3995446d644ff2950ff2c18f9f1ac2a3ea59d"
SOURCE_BYTES = 5_272_850
SOURCE_SHA256 = "d8b5c3ecfbc44839863ff7db1e8f0ad4559a343bf92d640a2455e9d06de5aad7"

CORE_FILES = (
    "compile_argv.json",
    "compile_source_identity.json",
    "compile_exit.txt",
    "compile_driver.log",
    "compile_first_error.txt",
    "compile_log_head.txt",
    "compile_log_tail.txt",
)
GENERATED_CORE = {
    "RETURN_CORE_MANIFEST.json",
    "return_core/RETURN_CORE_STATUS.json",
    "return_core/RETURN_PLUGIN_STATUS.json",
    "return_core/SIM_EXIT_RECEIPT.json",
    "return_core/plugins/node0004_source_bound_collect.status.json",
    "return_core/plugins/node0004_source_bound_collect.stderr.log",
    "return_core/plugins/node0004_source_bound_collect.stdout.log",
}
NATIVE_OBSERVER = "tb_probe/native_return_observer.svh"
BAD_XMRS = {
    4816: "local_req_full_channels[8].wr_en.u_local_req_full_channel.arb_req_ready[0]",
    4821: "local_req_full_channels[9].wr_en.u_local_req_full_channel.arb_req_ready[0]",
}


class AnalysisError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def archive_payloads(
    path: Path, expected_root: str, errors: list[str]
) -> tuple[dict[str, bytes], dict[str, Any]]:
    payloads: dict[str, bytes] = {}
    names: list[str] = []
    roots: set[str] = set()
    expanded = 0
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            errors.append(f"crc_failure:{bad_crc}")
        for info in archive.infolist():
            name = info.filename
            names.append(name)
            member = PurePosixPath(name)
            if member.parts:
                roots.add(member.parts[0])
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in name
                or stat.S_ISLNK(mode)
            ):
                errors.append(f"unsafe_member:{name}")
                continue
            if info.is_dir():
                continue
            if len(member.parts) < 2 or member.parts[0] != expected_root:
                errors.append(f"root_mismatch_member:{name}")
                continue
            relative = PurePosixPath(*member.parts[1:]).as_posix()
            payloads[relative] = archive.read(info)
            expanded += info.file_size
    if len(names) != len(set(names)):
        errors.append("duplicate_member")
    if roots != {expected_root}:
        errors.append(f"single_root_mismatch:{sorted(roots)}")
    if len(payloads) != sum(1 for name in names if not name.endswith("/")):
        errors.append("payload_member_count_mismatch")
    return payloads, {
        "member_count": len(names),
        "file_count": len(payloads),
        "roots": sorted(roots),
        "expanded_bytes": expanded,
        "compressed_bytes": path.stat().st_size,
        "diagnostic_budget_pass": path.stat().st_size <= 16 * 1024 * 1024
        and expanded <= 32 * 1024 * 1024,
    }


def object_json(payloads: dict[str, bytes], name: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(payloads[name])
    except (KeyError, json.JSONDecodeError) as exc:
        errors.append(f"invalid_json:{name}:{exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"json_not_object:{name}")
        return {}
    return value


def integer_text(payloads: dict[str, bytes], name: str, errors: list[str]) -> int | None:
    try:
        return int(payloads[name].decode("ascii").strip())
    except (KeyError, UnicodeDecodeError, ValueError) as exc:
        errors.append(f"invalid_integer:{name}:{exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    if not args.return_zip.is_file():
        raise AnalysisError(f"return ZIP is absent: {args.return_zip}")
    if not args.source_zip.is_file():
        raise AnalysisError(f"source ZIP is absent: {args.source_zip}")
    return_identity = {
        "path": str(args.return_zip.resolve()),
        "bytes": args.return_zip.stat().st_size,
        "sha256": sha256_file(args.return_zip),
    }
    source_identity = {
        "path": str(args.source_zip.resolve()),
        "bytes": args.source_zip.stat().st_size,
        "sha256": sha256_file(args.source_zip),
    }
    if return_identity["bytes"] != RETURN_BYTES or return_identity["sha256"] != RETURN_SHA256:
        errors.append("external_return_identity_mismatch")
    if source_identity["bytes"] != SOURCE_BYTES or source_identity["sha256"] != SOURCE_SHA256:
        errors.append("source_package_identity_mismatch")
    if args.return_zip.name != RETURN_BASENAME:
        errors.append("return_basename_mismatch")

    returned, return_zip_audit = archive_payloads(args.return_zip, RETURN_ROOT, errors)
    source, source_zip_audit = archive_payloads(args.source_zip, PACKAGE, errors)
    manifest = object_json(returned, "RETURN_CORE_MANIFEST.json", errors)
    core = object_json(returned, "return_core/RETURN_CORE_STATUS.json", errors)
    sim = object_json(returned, "return_core/SIM_EXIT_RECEIPT.json", errors)
    plugin = object_json(
        returned,
        "return_core/plugins/node0004_source_bound_collect.status.json",
        errors,
    )
    compile_argv = object_json(
        returned, "evidence/compile_rootcause/compile_argv.json", errors
    )
    compile_sources = object_json(
        returned, "evidence/compile_rootcause/compile_source_identity.json", errors
    )

    receipt_rows = manifest.get("core_entry_receipts", [])
    if not isinstance(receipt_rows, list):
        errors.append("core_entry_receipts_not_list")
        receipt_rows = []
    declared: set[str] = set()
    for row in receipt_rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            errors.append("invalid_core_entry_receipt")
            continue
        name = row["path"]
        declared.add(name)
        payload = returned.get(name)
        if payload is None:
            errors.append(f"missing_declared_core_entry:{name}")
        elif len(payload) != row.get("bytes") or sha256_bytes(payload) != row.get("sha256"):
            errors.append(f"core_entry_receipt_mismatch:{name}")
    expected_set = declared | GENERATED_CORE
    if set(returned) != expected_set:
        errors.append(
            "return_exact_set_mismatch:"
            + json.dumps(
                {
                    "missing": sorted(expected_set - set(returned)),
                    "unexpected": sorted(set(returned) - expected_set),
                },
                sort_keys=True,
            )
        )

    required_compile_paths = {
        f"evidence/compile_rootcause/{name}" for name in CORE_FILES
    }
    if not required_compile_paths <= declared:
        errors.append(
            "seven_compile_core_entries_missing:"
            + json.dumps(sorted(required_compile_paths - declared))
        )

    source_manifest = source.get("package_manifest.json", b"")
    returned_manifest = returned.get("evidence/returned_package_manifest.json", b"")
    source_manifest_bound = bool(source_manifest) and returned_manifest == source_manifest
    if not source_manifest_bound:
        errors.append("returned_package_manifest_byte_binding_mismatch")

    for value, label in ((manifest, "manifest"), (core, "core"), (sim, "sim")):
        if value.get("package_id") != PACKAGE or value.get("execution_id") != EXECUTION_ID:
            errors.append(f"internal_identity_mismatch:{label}")
    if manifest.get("return_basename") != RETURN_BASENAME:
        errors.append("internal_return_basename_mismatch")

    compile_exit = integer_text(
        returned, "evidence/compile_rootcause/compile_exit.txt", errors
    )
    compile_exit_status = integer_text(returned, "evidence/compile_exit_status.txt", errors)
    run_exit = integer_text(returned, "evidence/run_exit_status.txt", errors)
    if compile_exit != 2 or compile_exit_status != 2:
        errors.append("compile_exit_not_exact_2")
    if run_exit != 125:
        errors.append("run_exit_not_exact_125")
    signal = returned.get("evidence/signal_status.txt", b"").decode("ascii", errors="replace").strip()
    if signal != "NONE":
        errors.append("signal_not_NONE")
    if sim.get("sim_started") is not False or sim.get("sim_exit_code") != 125:
        errors.append("simulation_state_mismatch")

    argv = compile_argv.get("argv", [])
    argv_text = "\n".join(str(item) for item in argv) if isinstance(argv, list) else ""
    expected_compile_binding = all(
        token in argv_text
        for token in (
            "Makefile.tb_NDP_Top_new_phy",
            "source_bound_causal_observer.svh",
            "buffer_ack_phase_observer.svh",
            "+define+NATIVE_RETURN_OBSERVER_ENABLE",
        )
    )
    if not expected_compile_binding:
        errors.append("actual_compile_argv_binding_incomplete")

    selected_rows = compile_sources.get("selected_sources", [])
    selected_by_name = {
        Path(str(row.get("path", ""))).name: row
        for row in selected_rows
        if isinstance(row, dict)
    }
    for relative in (
        "tb_probe/source_bound_causal_observer.svh",
        "tb_probe/buffer_ack_phase_observer.svh",
    ):
        payload = source.get(relative)
        row = selected_by_name.get(Path(relative).name, {})
        if (
            payload is None
            or row.get("exists") is not True
            or row.get("bytes") != len(payload)
            or row.get("sha256") != sha256_bytes(payload)
        ):
            errors.append(f"selected_package_source_identity_mismatch:{relative}")

    driver = returned.get("evidence/compile_rootcause/compile_driver.log", b"").decode(
        "utf-8", errors="replace"
    )
    bounded_head = returned.get("evidence/compile_rootcause/compile_log_head.txt", b"")
    bounded_tail = returned.get("evidence/compile_rootcause/compile_log_tail.txt", b"")
    first_error_text = returned.get(
        "evidence/compile_rootcause/compile_first_error.txt", b""
    ).decode("utf-8", errors="replace").strip()
    bounded_relationship = (
        len(bounded_head) == 65_536
        and len(bounded_tail) == 65_536
        and driver.startswith(bounded_head.decode("utf-8", errors="replace"))
        and driver.endswith(bounded_tail.decode("utf-8", errors="replace"))
    )
    if not bounded_relationship:
        errors.append("bounded_head_tail_driver_relationship_mismatch")

    xmre_matches = list(
        re.finditer(
            r"Error-\[XMRE\].*?\n(?P<path>/home/[^,\n]+), (?P<line>\d+).*?\n"
            r"\s*Error found while trying to resolve cross-module reference\.\n"
            r"\s*token '(?P<token>[^']+)'\.",
            driver,
            flags=re.S,
        )
    )
    xmre_rows = [
        {
            "path": match.group("path"),
            "line": int(match.group("line")),
            "token": match.group("token"),
        }
        for match in xmre_matches
    ]
    if xmre_rows != [
        {
            "path": f"/home/panqs/ndp/{PACKAGE}/{NATIVE_OBSERVER}",
            "line": 4816,
            "token": "arb_req_ready",
        },
        {
            "path": f"/home/panqs/ndp/{PACKAGE}/{NATIVE_OBSERVER}",
            "line": 4821,
            "token": "arb_req_ready",
        },
    ]:
        errors.append(f"unexpected_first_compiler_errors:{xmre_rows}")
    if "2 errors" not in driver or "make: *** [Makefile.tb_NDP_Top_new_phy:306: compile] Error 255" not in driver:
        errors.append("compile_terminal_summary_missing")

    native_payload = source.get(NATIVE_OBSERVER, b"")
    native_lines = native_payload.decode("utf-8", errors="replace").splitlines()
    observer_line_binding: dict[str, str] = {}
    for line_number, token in BAD_XMRS.items():
        line = native_lines[line_number - 1] if len(native_lines) >= line_number else ""
        observer_line_binding[str(line_number)] = line
        if token not in line:
            errors.append(f"source_observer_xmr_line_mismatch:{line_number}")

    first_error_selector_false_positive = (
        "error message report" in first_error_text.lower()
        and not first_error_text.lstrip().startswith("Error-[XMRE]")
    )
    if not first_error_selector_false_positive:
        errors.append("expected_first_error_selector_false_positive_not_observed")

    plugin_stderr = returned.get(
        "return_core/plugins/node0004_source_bound_collect.stderr.log", b""
    ).decode("utf-8", errors="replace")
    plugin_consequential = (
        plugin.get("exit_code") == 1
        and "immutable raw inline-realtime input is missing" in plugin_stderr
        and sim.get("sim_started") is False
    )
    if not plugin_consequential:
        errors.append("plugin_failure_not_bound_as_compile_consequence")

    report = {
        "schema": "conv-node0004-v85b-formal-return-analysis-v1",
        "analysis_valid": not errors,
        "structural_errors": errors,
        "RETURN_ANALYSIS": {
            "return": return_identity,
            "source_package": source_identity,
            "return_zip_audit": return_zip_audit,
            "source_zip_audit": source_zip_audit,
            "return_exact_set": set(returned) == expected_set,
            "core_entry_receipts": not any(
                error.startswith(("missing_declared", "core_entry_receipt"))
                for error in errors
            ),
            "seven_bootstrap_compile_rootcause_files": required_compile_paths <= declared,
            "source_package_manifest_byte_binding": source_manifest_bound,
            "internal_package_execution_return_identity": not any(
                error.startswith("internal_") for error in errors
            ),
            "compile_exit": compile_exit,
            "run_exit": run_exit,
            "signal": signal,
            "simulation_started": sim.get("sim_started"),
            "natural_terminal": False,
            "formal_d": {
                "expected": 320,
                "present": 0,
                "missing": 320,
                "mismatch": None,
                "adjudication": "NOT_EVALUATED_SIMULATION_NEVER_STARTED",
            },
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "LAST_PROVEN_GOOD": (
            "EXACT_V85B_SOURCE_AND_EXECUTION_BOUND_CORE_RETURN_PUBLISHED_WITH_"
            "SEVEN_BOOTSTRAP_COMPILE_ROOTCAUSE_FILES"
        ),
        "FIRST_DIVERGENCE": "PRODUCTION_VCS_ELABORATION_XMRE_BEFORE_SIMULATION_START",
        "ROOT_CAUSE": {
            "classification": "PACKAGE_LOCAL_OBSERVER_HIERARCHY_COMPILE_DEFECT",
            "repair_authority": "PACKAGE_LOCAL_OBSERVER_AND_RUNNER_ONLY",
            "functional_rtl_root_cause": False,
            "actual_compile_argv_bound": expected_compile_binding,
            "actual_selected_source_identity_bound": True,
            "compiler_errors": xmre_rows,
            "package_member": {
                "path": NATIVE_OBSERVER,
                "bytes": len(native_payload),
                "sha256": sha256_bytes(native_payload),
                "returned_manifest_sha256": (
                    json.loads(source_manifest).get("files", {}).get(NATIVE_OBSERVER)
                    if source_manifest
                    else None
                ),
            },
            "source_lines": observer_line_binding,
            "explanation": (
                "The package-local native_return_observer dereferences arb_req_ready[0] "
                "for channels 8 and 9. The actual production elaboration cannot resolve "
                "that internal token, yielding the only two VCS XMRE errors and compile exit 2."
            ),
            "consequential_plugin_failure": (
                "node0004_source_bound_collect lacks sim.log only because compile did not "
                "produce a simulator; it is not the root cause."
            ),
        },
        "COMPILE_CORE_QUALITY": {
            "bounded_driver_contains_root": True,
            "head_tail_relationship": bounded_relationship,
            "first_error_text": first_error_text,
            "first_error_selector_false_positive": first_error_selector_false_positive,
            "repair_required": (
                "Prioritize anchored compiler diagnostics such as Error-[...] over prose "
                "containing the word 'error'."
            ),
        },
        "PREVIOUS_VERSION_PROGRESS": {
            "version": "v84b",
            "progress": (
                "Reached production compile and exited 2; simulation never started. The "
                "formal return bound package/execution and survived plugin failure, but "
                "omitted actual compile argv/source/log/first-error evidence."
            ),
            "natural_terminal": False,
            "formal_d": "0/320",
            "E3_E4_E5": "false/false/false",
        },
        "CURRENT_VERSION_PURPOSE_AND_RESULT": {
            "version": "v85b",
            "purpose": (
                "Capture the seven missing bootstrap compile-rootcause files and uniquely "
                "locate the production compile exit-2 cause."
            ),
            "result": (
                "Purpose achieved: the bounded compile tail uniquely identifies two "
                "package-local observer XMREs at native_return_observer.svh:4816 and :4821."
            ),
            "functional_progress": False,
            "diagnostic_progress": True,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_COMPILEFAIL_ROOT_CAUSE_UNOBSERVED",
                "B_CONV_NODE0004_COMPILEFAIL_RETURN_OMITS_DRIVER_LOG",
            ],
            "opened": [
                "B_CONV_NODE0004_PACKAGE_LOCAL_NATIVE_RETURN_OBSERVER_ARB_REQ_READY_XMRE",
                "B_CONV_NODE0004_FIRST_ERROR_SELECTOR_WARNING_PROSE_FALSE_POSITIVE",
            ],
            "retained": [
                "B_CONV_NODE0004_ACK_OUTPUT_VS_INLINE_RHS_STABLE_MISMATCH_UNRESOLVED",
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
        },
        "SUCCESSOR_DECISION": {
            "required": True,
            "status": "PACKAGE_LOCAL_REPAIR_AUTHORIZED_FRESH_SUCCESSOR_REQUIRED",
            "allowed_changes": [
                "fresh package identity",
                "two package-local observer XMR expressions",
                "first-error extraction precedence",
                "directly required runner/return receipts and manifests",
            ],
            "frozen": ["config", "numeric", "workload", "functional RTL"],
        },
        "RULE_CONFIRMATION": {
            "rule_ids": [
                "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
                "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
            ],
            "evidence": (
                "Seven bootstrap files survived compile exit 2 and plugin failure; the "
                "bounded tail resolved the exact package-local XMR root."
            ),
            "claim_boundary": (
                "The stable rule is sufficient. The first-error false positive is a "
                "package implementation defect to repair in the successor, not a rule gap."
            ),
        },
        "claims": {
            "configuration_modified": False,
            "numeric_modified": False,
            "workload_modified": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
    }
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "analysis_valid": report["analysis_valid"],
                "errors": errors,
                "first_divergence": report["FIRST_DIVERGENCE"],
                "root_cause": report["ROOT_CAUSE"]["classification"],
            },
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
