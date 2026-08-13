#!/usr/bin/env python3
"""Validate and classify the formal p6 ARM-interface diagnostic return."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-08\r5_n4_e1f_p6_armif_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n4_e1f_p6_armif.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_e1fb0f7_p6_return_analysis"
    / "report.json"
)
INSTALL_NAME = "r5_n4_e1f_p6_armif"
RETURN_ROOT = f"{INSTALL_NAME}_return"
EXPECTED_RETURN_SHA = (
    "9c590ae7ae17b55ef3471032dc8b3471bbf949e07eeb1a9dd61b0639fd5ccf59"
)
EXPECTED_RETURN_BYTES = 51456
EXPECTED_SOURCE_SHA = (
    "05fc4f385d544195ad3cbc68256525d70775cc490d4a42ff784e9b9f7c5d34c1"
)
EXPECTED_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
RULE_RECEIPTS = {
    ".agents/agent.md": (
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
    ),
    ".agents/rules/生成前必读索引.md": (
        "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2"
    ),
    ".agents/rules/算子配置规则.md": (
        "d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d"
    ),
    ".agents/rules/INT8_SA点积专项规则.md": (
        "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
    ),
    ".agents/rules/精确UINT8量化尾专项规则.md": (
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba"
    ),
}
GIT_PATHS = {
    "Array_Request_Manager.sv": (
        "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Array_Request_Manager.sv"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    ),
    "RD_Data_Channel.sv": (
        "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Data_Channel.sv"
    ),
}


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_records(
    archive: zipfile.ZipFile, expected_root: str
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    errors: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        pure = PurePosixPath(name)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in name
            or not pure.parts
            or pure.parts[0] != expected_root
            or name in seen
            or stat.S_ISLNK(mode)
        ):
            errors.append(name)
            continue
        seen.add(name)
        if info.is_dir():
            continue
        payload = archive.read(info)
        relative = PurePosixPath(*pure.parts[1:]).as_posix()
        records[relative] = {
            "size_bytes": len(payload),
            "sha256": digest(payload),
        }
        payloads[relative] = payload
    return records, payloads, errors


def git_command(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    safe = str(repo.resolve()).replace("\\", "/")
    return subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={safe}",
            "-C",
            str(repo),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )


def known_git_blob_matches(
    actual_leaves: dict[str, Any],
) -> dict[str, Any]:
    repo = ROOT / "Trassic2.0_RTL"
    results: dict[str, Any] = {}
    for basename, path in GIT_PATHS.items():
        commits_process = git_command(
            repo, "log", "--all", "--format=%H", "--", path
        )
        commits = commits_process.stdout.decode().split()
        variants: dict[str, dict[str, Any]] = {}
        for commit in commits:
            shown = git_command(repo, "show", f"{commit}:{path}")
            if shown.returncode:
                continue
            value = digest(shown.stdout)
            variants.setdefault(
                value,
                {
                    "commit": commit,
                    "size_bytes": len(shown.stdout),
                },
            )
        actual = actual_leaves[basename]["sha256"]
        results[basename] = {
            "actual_sha256": actual,
            "known_git_blob_match": actual in variants,
            "matching_identity": variants.get(actual),
            "known_unique_blob_count": len(variants),
        }
    return {
        "valid": all(
            not value["known_git_blob_match"] for value in results.values()
        ),
        "meaning": (
            "none of the three mismatching production bytes equals any blob "
            "for the same path reachable from current local Git refs"
        ),
        "leaves": results,
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    outer = {
        "path": str(return_zip),
        "size_bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "expected_size_bytes": EXPECTED_RETURN_BYTES,
        "expected_sha256": EXPECTED_RETURN_SHA,
        "adjacent_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "external_transport_sidecar_optional": True,
    }
    source = {
        "path": str(SOURCE_ZIP),
        "size_bytes": SOURCE_ZIP.stat().st_size,
        "sha256": sha256(SOURCE_ZIP),
        "expected_sha256": EXPECTED_SOURCE_SHA,
    }
    with zipfile.ZipFile(return_zip) as archive:
        return_records, payloads, return_errors = safe_records(
            archive, RETURN_ROOT
        )
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_records, source_payloads, source_errors = safe_records(
            archive, INSTALL_NAME
        )

    return_manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    result_gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(
        payloads["evidence/production_rtl_identity.json"]
    )
    returned_package_manifest = payloads[
        "source_package/package_manifest.json"
    ]
    source_package_manifest = source_payloads["package_manifest.json"]
    package_preflight = json.loads(
        payloads["evidence/package_preflight.json"]
    )
    install_preflight = json.loads(
        payloads["evidence/install_preflight.json"]
    )
    observer_precompile = json.loads(
        payloads["evidence/observer_precompile.json"]
    )
    compile_argv = payloads["evidence/compile_argv.txt"].decode().strip()
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_log = payloads["runs/compile/compile.log"].decode(
        errors="replace"
    )
    driver_log = payloads["runs/compile/compile_driver.log"].decode(
        errors="replace"
    )

    declared_records = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in return_manifest["records_excluding_this_manifest"]
    }
    expected_set = set(declared_records) | {
        "RETURN_MANIFEST.json",
        "RETURN_ALLOWLIST.json",
    }
    observed_set = set(return_records)
    record_mismatches = {
        path: {
            "expected": expected,
            "observed": return_records.get(path),
        }
        for path, expected in declared_records.items()
        if return_records.get(path) != expected
    }
    allowlist_return_manifest = next(
        item
        for item in allowlist["records"]
        if item["path"] == "RETURN_MANIFEST.json"
    )
    dynamic_paths = sorted(
        path
        for path in return_records
        if path.startswith("runs/c0/")
        or path.startswith("evidence/feature_binding/")
        or path.startswith("evidence/natural_terminal/")
    )
    mismatches = {
        basename: value
        for basename, value in identity["leaves"].items()
        if not value["match"]
    }
    matches = {
        basename: value
        for basename, value in identity["leaves"].items()
        if value["match"]
    }
    history = known_git_blob_matches(mismatches)
    current_rules = {
        relative: sha256(ROOT / relative) for relative in RULE_RECEIPTS
    }

    receipt_checks = {
        "outer_identity_exact": (
            outer["size_bytes"] == EXPECTED_RETURN_BYTES
            and outer["sha256"] == EXPECTED_RETURN_SHA
        ),
        "source_identity_exact": source["sha256"] == EXPECTED_SOURCE_SHA,
        "return_zip_safe": not return_errors,
        "source_zip_safe": not source_errors,
        "return_exact_set": observed_set == expected_set,
        "return_record_hashes_exact": not record_mismatches,
        "allowlist_manifest_binding": (
            allowlist_return_manifest["size_bytes"]
            == return_records["RETURN_MANIFEST.json"]["size_bytes"]
            and allowlist_return_manifest["sha256"]
            == return_records["RETURN_MANIFEST.json"]["sha256"]
            and allowlist["declared_allowlist"]
            == return_manifest["declared_allowlist"]
        ),
        "source_package_manifest_exact": (
            returned_package_manifest == source_package_manifest
            and digest(returned_package_manifest)
            == return_manifest["source_package_manifest_sha256"]
        ),
        "source_package_manifest_files_exact": (
            json.loads(source_package_manifest)["files"]
            == {
                path: value
                for path, value in source_records.items()
                if path != "package_manifest.json"
            }
        ),
        "package_preflight_valid": package_preflight.get("valid") is True,
        "install_preflight_valid": install_preflight.get("valid") is True,
        "observer_precompile_valid": observer_precompile.get("valid") is True,
        "compile_succeeded": (
            compile_status == 0
            and result_gate["execution_gate"]["compile_succeeded"] is True
            and "Compilation completed!" in driver_log
            and "0 error(s)" in driver_log
        ),
        "private_xmr_compile_escape_closed": (
            "Error-[XMRE]" not in driver_log
            and "buf2arm_valid_hold" not in driver_log
            and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_argv
        ),
        "actual_identity_receipt_bound": (
            identity["compile_log_sha256"]
            == digest(payloads["runs/compile/compile_driver.log"])
            and identity == result_gate["production_rtl_identity"]
        ),
        "identity_mismatch_exact_three": (
            set(mismatches)
            == {
                "Array_Request_Manager.sv",
                "Buffer_AG_Idx_Queue.sv",
                "RD_Data_Channel.sv",
            }
            and len(matches) == 5
        ),
        "simulation_not_started": (
            run_status == 125
            and signal_status == "NONE"
            and not dynamic_paths
            and result_gate["canonical_record_count"] == 0
        ),
        "formal_d_not_claimed": (
            json.loads(source_package_manifest)["formal_readback_count"] == 0
            and result_gate["execution_gate"]["formal_D_claimed"] is False
        ),
        "current_rules_exact": current_rules == RULE_RECEIPTS,
        "mismatching_bytes_not_known_git_blobs": history["valid"],
    }
    valid = all(receipt_checks.values())
    return {
        "schema": "conv-native-four-lane-p6-return-analysis-v1",
        "status": (
            "TERMINAL_NO_PACKAGE_SERVER_RTL_IDENTITY_MISMATCH"
            if valid
            else "FAIL"
        ),
        "valid": valid,
        "classification": (
            "SERVER_PRODUCTION_RTL_IDENTITY_MISMATCH_TERMINAL_NO_PACKAGE"
        ),
        "outer_return_identity": outer,
        "source_package_identity": source,
        "internal_receipt": {
            "return_root": RETURN_ROOT,
            "entry_count": len(return_records),
            "return_manifest_sha256": return_records[
                "RETURN_MANIFEST.json"
            ]["sha256"],
            "return_allowlist_sha256": return_records[
                "RETURN_ALLOWLIST.json"
            ]["sha256"],
            "source_package_manifest_sha256": digest(
                returned_package_manifest
            ),
            "return_zip_errors": return_errors,
            "source_zip_errors": source_errors,
            "exact_set_missing": sorted(expected_set - observed_set),
            "exact_set_extra": sorted(observed_set - expected_set),
            "record_mismatches": record_mismatches,
            "checks": receipt_checks,
        },
        "execution": {
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "observer_precompile": observer_precompile,
            "compile_argv": compile_argv,
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "simulation_started": False,
            "dynamic_c0_artifacts": dynamic_paths,
            "formal_320d_scope_in_package": False,
            "formal_320d_result": "NOT_APPLICABLE_TO_P6_DIAGNOSTIC",
        },
        "private_xmr_adjudication": {
            "closed": True,
            "production_compile_completed": True,
            "vcs_xmre_count": driver_log.count("Error-[XMRE]"),
            "private_token_in_compile_log": (
                "buf2arm_valid_hold" in driver_log
            ),
            "compile_driver_log_sha256": digest(
                payloads["runs/compile/compile_driver.log"]
            ),
            "compile_log_sha256": digest(
                payloads["runs/compile/compile.log"]
            ),
            "production_compile_summary": (
                "91.464 seconds compile + 4.998 seconds elaboration + "
                "1.818 seconds link; 0 errors, 1 warning"
            ),
        },
        "actual_production_rtl_identity": {
            "receipt_valid": identity["valid"],
            "expected_commit": identity["expected_commit"],
            "identity_source": identity["identity_source"],
            "matched_leaf_count": len(matches),
            "mismatched_leaf_count": len(mismatches),
            "matched_leaves": matches,
            "mismatched_leaves": mismatches,
            "known_git_blob_probe": history,
            "claim": (
                "the actual compile identity is known and is not the package-"
                "approved e1fb0f7 eight-leaf identity"
            ),
        },
        "failure_localization": {
            "LPG": [
                "exact p6 source and exact formal return",
                "internal exact-set/hash/source-manifest binding",
                "package/install/observer precompile guards",
                "production VCS compile/elaboration/link with public observer",
                "post-compile hashing of all eight required production leaves",
            ],
            "FD": (
                "post-compile production RTL identity conjunction before "
                "the first c0 simulator invocation"
            ),
            "HANG_ROOT_CAUSE": (
                "NOT_ENTERED_C0_SERVER_PRODUCTION_RTL_IDENTITY_MISMATCH"
            ),
            "c0_exec_to_slice_finish_localization": (
                "NOT_OBSERVED_RUNNER_FAILED_CLOSED_BEFORE_SIMULATION"
            ),
        },
        "blocker_delta": {
            "closed": [
                "B_P5_OBSERVER_PRIVATE_XMR_PRODUCTION_RESOLUTION",
                "production VCS compile/elaboration/link reachability",
                "actual production eight-leaf identity collection",
            ],
            "terminal": [
                "B_P6_ACTUAL_PRODUCTION_RTL_IDENTITY_MISMATCH_3_OF_8",
            ],
            "preserved": [
                "B_CONV_NATIVE4_C0_EXEC_TO_SLICE_FINISH_UNDIAGNOSED",
                "B_CONV_NATIVE4_NATURAL_TERMINAL_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_NOT_IN_P6_SCOPE",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "release_gate_matrix": {
            "core_always": {
                "applicable": True,
                "pass": True,
                "evidence": "exact source/return/internal receipt and preflight",
            },
            "runner": {
                "applicable": True,
                "pass": True,
                "evidence": (
                    "real runner reached compile, post-compile identity gate, "
                    "finalizer and allowlist return; it failed closed before sim"
                ),
            },
            "package_local_hdl": {
                "applicable": True,
                "pass": True,
                "evidence": (
                    "actual VCS compiled/elaborated/linked the p6 public-surface "
                    "observer with zero XMRE"
                ),
            },
            "materialized_config": {
                "applicable": False,
                "pass": True,
                "disposition": "receipt_reuse",
                "reason": (
                    "p6 causal config/workload is byte-bound to the frozen "
                    "source package; no successor or config change is emitted"
                ),
                "transaction_ledger": "not_applicable",
                "boundary_microtrace": "not_applicable",
            },
            "diagnostic_semantics": {
                "applicable": False,
                "pass": True,
                "disposition": "record_only",
                "reason": (
                    "no fresh changed observer/parser/canonical predicate is "
                    "being released; p6 predates the new trace-unit rule"
                ),
                "predicate_trace": "not_applicable",
                "public_surface_proof": (
                    "p6 positive example confirmed by actual VCS compile"
                ),
            },
            "return_result": {
                "applicable": True,
                "pass": False,
                "blocking_failure": (
                    "actual production RTL identity differs for three of eight "
                    "required leaves; c0 simulation did not start"
                ),
            },
            "record_only_warnings": [
                "adjacent external return sidecar absent and optional",
                "no known Git blob match for any mismatching server leaf",
            ],
            "blocking_failures": [
                "B_P6_ACTUAL_PRODUCTION_RTL_IDENTITY_MISMATCH_3_OF_8"
            ],
            "pass": False,
            "status": "TERMINAL_NO_PACKAGE",
        },
        "successor_decision": {
            "package_release": "NONE",
            "fresh_successor_generated": False,
            "reason": (
                "a package-local/config/observer successor cannot repair or "
                "legitimately accept unknown, non-authoritative production RTL "
                "bytes; functional/server RTL synchronization needs authority "
                "outside this owner"
            ),
            "minimum_next_action": (
                "operator synchronizes the real server RTL to one approved "
                "immutable identity, then reruns a freshly dispatched package "
                "bound to those exact bytes"
            ),
        },
        "claim_boundary": {
            "c0_dynamic_evidence": "ZERO_NOT_STARTED",
            "natural_terminal_claimed": False,
            "formal_320d_claimed": False,
            "performance_E3_E4_E5_claimed": False,
            "server_action_by_analyzer": False,
        },
        "current_rule_receipts": current_rules,
        "current_plan_mutable_provenance_sha256": sha256(
            ROOT / ".agents/plan.md"
        ),
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "confirmed": [
                "actual post-compile production identity is a blocking result gate",
                "public-surface observer is preferred over private XMR",
                "unchanged materialized config uses receipt reuse",
                "compile success without simulation/natural/formal-D cannot raise E3-E5",
            ],
            "rule_delta_proposal": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=RETURN_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve())
    write_json(args.output.resolve(), result)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
