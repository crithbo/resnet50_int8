#!/usr/bin/env python3
"""Validate and classify the exact p39 production compile-core return."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p39_compilecore"
EXECUTION = "r1786447845737357042_1115149"
RETURN = Path(r"C:\Users\15383\Downloads\r5_n4_0cc_p39_compilecore_r1786447845737357042_1115149_return.zip")
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p39_compilecore.zip"
FINAL_AUDIT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p39_compilecore/r5_n4_0cc_p39_compilecore.final_zip_audit.json"
OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p39_return_analysis/report.json"
RETURN_BYTES = 12_228
RETURN_SHA256 = "7fee000c0707d94aaad7494ab34120628165b0b09abade707df1c618127f9e45"
SOURCE_BYTES = 5_973_514
SOURCE_SHA256 = "d99d078a53ec88f5dc0374f0b080350d2e62a6e2121237f7da4dbce9a6c6b515"
SOURCE_MANIFEST_SHA256 = "09a322a0a39dbd279aa8921b2b1507ed320af0fc63264264bc1a99644ac73493"
RETURN_ROOT = PACKAGE
EXPECTED_ALLOWLIST = [
    "RETURN_MANIFEST.json",
    "RETURN_ALLOWLIST.txt",
    "evidence/package_local_preflight_status.json",
    "compile_core/compile_argv.json",
    "compile_core/compile_source_identity.json",
    "compile_core/compile_exit.txt",
    "compile_core/compile_log_receipt.json",
    "compile_core/compile_log_head.txt",
    "compile_core/compile_log_tail.txt",
    "compile_core/compile_first_error.txt",
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    try:
        label = path.relative_to(ROOT).as_posix()
    except ValueError:
        label = str(path)
    return {"path": label, "bytes": path.stat().st_size, "sha256": sha(path)}


def json_member(archive: zipfile.ZipFile, relative: str) -> dict[str, Any]:
    return json.loads(archive.read(f"{RETURN_ROOT}/{relative}"))


def path_safe(name: str, root: str) -> bool:
    pure = PurePosixPath(name)
    return (
        bool(name)
        and "\\" not in name
        and not pure.is_absolute()
        and ".." not in pure.parts
        and pure.parts[0] == root
    )


def zip_identity(path: Path, expected_root: str) -> tuple[dict[str, Any], zipfile.ZipFile]:
    archive = zipfile.ZipFile(path)
    names = archive.namelist()
    roots = sorted({PurePosixPath(name).parts[0] for name in names if name})
    duplicates = sorted({name for name in names if names.count(name) > 1})
    special = []
    for info in archive.infolist():
        mode = stat.S_IFMT(info.external_attr >> 16)
        if mode not in (0, stat.S_IFDIR, stat.S_IFREG):
            special.append(info.filename)
    return ({
        **receipt(path),
        "member_count": len(names),
        "roots": roots,
        "crc_bad_member": archive.testzip(),
        "unsafe_paths": [name for name in names if not path_safe(name, expected_root)],
        "duplicate_members": duplicates,
        "special_members": special,
        "single_expected_root": roots == [expected_root],
    }, archive)


def manifest_check(source_zip: zipfile.ZipFile) -> dict[str, Any]:
    manifest_bytes = source_zip.read(f"{PACKAGE}/package_manifest.json")
    manifest = json.loads(manifest_bytes)
    declared = manifest["files"]
    names = set(source_zip.namelist())
    expected = {f"{PACKAGE}/package_manifest.json"} | {
        f"{PACKAGE}/{relative}" for relative in declared
    }
    mismatches: dict[str, Any] = {}
    for relative, expected_row in declared.items():
        member = f"{PACKAGE}/{relative}"
        if member not in names:
            mismatches[relative] = "missing"
            continue
        data = source_zip.read(member)
        actual = {"size_bytes": len(data), "sha256": sha_bytes(data)}
        wanted = {"size_bytes": expected_row["size_bytes"], "sha256": expected_row["sha256"]}
        if actual != wanted:
            mismatches[relative] = {"expected": wanted, "actual": actual}
    return {
        "manifest": manifest,
        "manifest_bytes": manifest_bytes,
        "exact_set": names == expected,
        "per_file_mismatches": mismatches,
        "member_count": len(names),
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite p39 return analysis")
    return_identity, return_zip = zip_identity(RETURN, RETURN_ROOT)
    source_identity, source_zip = zip_identity(SOURCE, PACKAGE)
    try:
        source = manifest_check(source_zip)
        return_names = set(return_zip.namelist())
        allowlist_text = return_zip.read(f"{RETURN_ROOT}/RETURN_ALLOWLIST.txt").decode("utf-8")
        allowlist = allowlist_text.splitlines()
        expected_names = {f"{RETURN_ROOT}/{relative}" for relative in EXPECTED_ALLOWLIST}
        manifest = json_member(return_zip, "RETURN_MANIFEST.json")
        argv = json_member(return_zip, "compile_core/compile_argv.json")
        source_receipt = json_member(return_zip, "compile_core/compile_source_identity.json")
        log_receipt = json_member(return_zip, "compile_core/compile_log_receipt.json")
        preflight = json_member(return_zip, "evidence/package_local_preflight_status.json")
        exit_text = return_zip.read(f"{RETURN_ROOT}/compile_core/compile_exit.txt").decode("ascii")
        head = return_zip.read(f"{RETURN_ROOT}/compile_core/compile_log_head.txt")
        tail = return_zip.read(f"{RETURN_ROOT}/compile_core/compile_log_tail.txt")
        first_error = return_zip.read(f"{RETURN_ROOT}/compile_core/compile_first_error.txt")
        tail_text = tail.decode("utf-8", "replace")
        first_error_text = first_error.decode("utf-8", "replace")
        member_errors: dict[str, Any] = {}
        for row in manifest["members"]:
            member = f"{RETURN_ROOT}/{row['path']}"
            if member not in return_names:
                member_errors[row["path"]] = "missing"
                continue
            data = return_zip.read(member)
            actual = {"bytes": len(data), "sha256": sha_bytes(data)}
            wanted = {"bytes": row["bytes"], "sha256": row["sha256"]}
            if actual != wanted:
                member_errors[row["path"]] = {"expected": wanted, "actual": actual}

        package_source_member = f"{PACKAGE}/tb_probe/source_bound_causal_observer.svh"
        package_source = source_zip.read(package_source_member)
        observer_member = f"{PACKAGE}/tb_probe/native_return_observer.svh"
        native_observer = source_zip.read(observer_member).decode("utf-8")
        observer_lines = native_observer.splitlines()
        line_2462 = observer_lines[2461]
        line_2467 = observer_lines[2466]
        expected_argv = [
            "timeout", "--foreground", "--signal=TERM", "--kill-after=30s", "2h",
            "make", "-f", "Makefile.tb_NDP_Top_new_phy", "compile",
            "DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0",
            f"RUN_DIR=/home/panqs/ndp/NDP_copy02/install/codex_runs/{PACKAGE}/a0/compile",
            f"VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+/home/panqs/ndp/{PACKAGE}/tb_probe /home/panqs/ndp/{PACKAGE}/tb_probe/source_bound_causal_observer.svh",
        ]
        error_blocks = re.findall(
            rf"Error-\[XMRE\] Cross-module reference resolution error\s+"
            rf"/home/panqs/ndp/{re.escape(PACKAGE)}/tb_probe/native_return_observer\.svh, (2462|2467)"
            rf".*?token 'arb_req_ready'\.",
            tail_text,
            flags=re.DOTALL,
        )
        checks = {
            "formal_return_transport_exact": return_identity["bytes"] == RETURN_BYTES and return_identity["sha256"] == RETURN_SHA256,
            "return_crc_single_root_path_safe": return_identity["crc_bad_member"] is None and return_identity["single_expected_root"] and not return_identity["unsafe_paths"] and not return_identity["duplicate_members"] and not return_identity["special_members"],
            "return_allowlist_order_exact": allowlist == EXPECTED_ALLOWLIST,
            "return_exact_set": return_names == expected_names,
            "return_manifest_members_exact": {row["path"] for row in manifest["members"]} == set(EXPECTED_ALLOWLIST[2:]) and not member_errors,
            "return_identity_stage_exit_exact": manifest.get("package_identity") == PACKAGE and manifest.get("stage") == "PRODUCTION_COMPILE" and manifest.get("runner_exit_code") == 2 and manifest.get("signal_name") == "NONE",
            "return_compile_core_complete": manifest.get("compile_core_complete") is True and manifest.get("missing_optional_before_stage") == [],
            "return_no_waveform_or_full_log": manifest.get("waveform_included") is False and manifest.get("full_compile_driver_log_included") is False,
            "preflight_compile_started_sim_not_started": preflight.get("production_compile_started") is True and preflight.get("dut_simulation_started") is False and preflight.get("runner_exit_code") == 2,
            "compile_exit_exact": exit_text == "2\n",
            "compile_argv_exact_no_pipeline": argv.get("argv") == expected_argv and argv.get("cwd") == "/home/panqs/ndp/NDP_copy02" and argv.get("shell_pipeline") is False,
            "waveforms_explicitly_disabled": argv.get("waveforms_explicitly_disabled") == ["DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0"],
            "source_zip_transport_exact": source_identity["bytes"] == SOURCE_BYTES and source_identity["sha256"] == SOURCE_SHA256,
            "source_zip_crc_single_root_path_safe": source_identity["crc_bad_member"] is None and source_identity["single_expected_root"] and not source_identity["unsafe_paths"] and not source_identity["duplicate_members"] and not source_identity["special_members"],
            "source_manifest_exact_set_per_file": source["exact_set"] and not source["per_file_mismatches"],
            "source_manifest_identity_exact": sha_bytes(source["manifest_bytes"]) == SOURCE_MANIFEST_SHA256 and source["manifest"].get("package_identity") == PACKAGE,
            "actual_package_source_bound": source_receipt.get("source_binding") == "ACTUAL_PACKAGE_LOCAL_SOURCE_PASSED_TO_PRODUCTION_COMPILE_ARGV" and source_receipt.get("package_source", {}).get("bytes") == len(package_source) and source_receipt.get("package_source", {}).get("sha256") == sha_bytes(package_source),
            "compile_log_bounded_receipt_exact": log_receipt.get("exists") is True and log_receipt.get("bytes") == 293245 and log_receipt.get("sha256") == "af6a546121b3d3fb28d2f4a434de57a9d0068d840a1b7ffcc3b2d36e0acb0b96" and len(head) == 65536 and len(tail) == 65536,
            "xmre_two_exact_sites": error_blocks == ["2462", "2467"] and tail_text.count("Error-[XMRE] Cross-module reference resolution error") == 2,
            "xmre_source_matches_package_member": "arb_req_ready[0]" in line_2462 and "arb_req_ready[0]" in line_2467,
            "compile_terminates_make_error": "7 warnings\n2 errors" in tail_text and "Makefile.tb_NDP_Top_new_phy:306: compile] Error 255" in tail_text,
            "first_error_extractor_misclassified_warning": "Ubuntu VERSION_ID=22.04" in first_error_text and "Error-[XMRE]" not in first_error_text,
            "source_release_final_audit_pass": json.loads(FINAL_AUDIT.read_text(encoding="utf-8")).get("valid") is True,
        }
        valid = all(checks.values())
        report = {
            "schema": "conv-native-four-lane-0ccae916-p39-return-analysis-v1",
            "status": "P39_VALID_COMPILE_CORE_RETURN_PACKAGE_LOCAL_OBSERVER_XMRE_ROOT_CAUSE",
            "valid": valid,
            "role_id": "family.conv.native",
            "owner_thread_id": "019ff02d-974d-7c72-a4d5-de8dbf4ae60c",
            "owner_epoch": 2,
            "previous_version_progress": "p38 reached the production compile stage and exited 2, but did not return actual compile argv, source identity, bounded log or first-error evidence.",
            "current_version_purpose": "p39 was a runner/return-only successor intended to preserve compile-core evidence and locate the production compile exit=2 root cause.",
            "return_identity": {**return_identity, "execution_id": EXECUTION, "adjacent_sidecar_present": Path(str(RETURN) + ".sha256").is_file()},
            "source_identity": {**source_identity, "package_manifest_bytes": len(source["manifest_bytes"]), "package_manifest_sha256": sha_bytes(source["manifest_bytes"])},
            "integrity": {"checks": checks, "return_member_errors": member_errors, "source_member_errors": source["per_file_mismatches"], "pass": valid},
            "execution": {
                "stage": "PRODUCTION_COMPILE",
                "runner_exit_code": 2,
                "signal_name": "NONE",
                "actual_compile_argv_collected": True,
                "actual_package_source_identity_collected": True,
                "bounded_compile_log_collected": True,
                "first_error_file_collected_but_semantically_misclassified": True,
                "dut_simulation_started": False,
            },
            "failure_localization": {
                "LAST_PROVEN_GOOD": "The exact p39 package entered the actual production make compile with a source-bound package-local observer, and the bootstrap collector persisted the argv/source/log/exit core.",
                "FIRST_DIVERGENCE": "VCS compilation of package-local tb_probe/native_return_observer.svh at lines 2462 and 2467 cannot resolve private hierarchical token arb_req_ready[0].",
                "ROOT_CAUSE": {
                    "status": "PACKAGE_LOCAL_OBSERVER_PRIVATE_XMR_ARB_REQ_READY_UNRESOLVED",
                    "compiler_class": "Error-[XMRE] Cross-module reference resolution error",
                    "source_member": "tb_probe/native_return_observer.svh",
                    "sites": [
                        {"line": 2462, "token": "arb_req_ready", "channel": 8},
                        {"line": 2467, "token": "arb_req_ready", "channel": 9},
                    ],
                    "production_compile_error_count": 2,
                    "repair_surface": "package-local observer plus compile first-error collector",
                    "functional_rtl_fix_required": False,
                },
            },
            "first_error_collector_defect": {
                "identified": True,
                "description": "The broad first-error regex selected a platform-support warning sentence containing the word error before the first VCS Error-[XMRE] diagnostic.",
                "bounded_tail_still_proves_root_cause": True,
                "successor_requirement": "select structured compiler error headers before generic error text",
            },
            "result_conjunction": {
                "compile": False,
                "simulator_started": False,
                "c0_slice_finish": False,
                "natural_terminal_27_of_27": False,
                "formal_D_320_of_320": False,
                "mismatch_zero_claim": False,
                "E3": False,
                "E4": False,
                "E5": False,
                "performance_claimed": False,
                "passed": False,
            },
            "claim_boundary": "p39 closes only the production compile-core diagnostic gap. The failure is package-local observer XMR; simulation did not start, so no DUT functional, config, numeric, workload, convergence, waveform or performance claim is permitted.",
            "successor_adjudication": {
                "decision": "BUILD_FRESH_PACKAGE_RUNNER_OBSERVER_SUCCESSOR",
                "reason": "The failure is repairable without functional RTL, config, numeric or workload changes.",
                "frozen_surfaces": ["config", "numeric", "workload", "functional RTL"],
                "allowed_surfaces": ["package identity", "package-local observer", "compile first-error collector", "runner receipts"],
            },
            "server_action": False,
        }
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"valid": valid, "status": report["status"], "output": str(OUTPUT), "bytes": OUTPUT.stat().st_size, "sha256": sha(OUTPUT)}, sort_keys=True))
        return 0 if valid else 1
    finally:
        return_zip.close()
        source_zip.close()


if __name__ == "__main__":
    raise SystemExit(main())
