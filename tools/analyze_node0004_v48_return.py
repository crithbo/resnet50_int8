from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (  # noqa: E402
    integer_entry,
    load_json,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL_NAME = "r5_n4_hw_v48_lc9_actual"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "91cb18d7e0a1d687597503026ed0155af0c8cf2f491a1712318897122148a27a"
SOURCE_SHA256 = "cdb13ac9039cbaac88306669b8b6e6d9bdb3d3956a4f38425610c6b4f2b7971b"
OBSERVER_SHA256 = "0f84e2b7560c3d0cc698cabf2ce88428bf0aec51ad8c1fd1fc5d0cb3dddf0d45"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
STREAM_ENGINE_SHA256 = (
    "a8718b4c4b043ffbf8c2bd59842ac677f18861783d70ce5eaa3d809c79ac6365"
)


def parse_xmre(log: str) -> list[dict[str, object]]:
    pattern = re.compile(
        r"Error-\[XMRE\].*?"
        r"native_return_observer\.svh,\s*(\d+).*?"
        r"token '([^']+)'.*?"
        r"Source info:\s*(.*?)(?=\n\s*Instance stack trace:)",
        re.DOTALL,
    )
    result: list[dict[str, object]] = []
    for match in pattern.finditer(log):
        result.append(
            {
                "line": int(match.group(1)),
                "token": match.group(2),
                "source_info": " ".join(match.group(3).split()),
            }
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    structural_errors: list[str] = []
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        structural_errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        structural_errors.append("source ZIP SHA mismatch")
    source_sidecar_valid = (
        args.source_sidecar.read_text(encoding="ascii").strip()
        == f"{source_sha}  {source_zip.name}"
    )
    if not source_sidecar_valid:
        structural_errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    structural_errors.extend(return_errors)
    structural_errors.extend(source_errors)

    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    returned = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            structural_errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        if not (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        ):
            structural_errors.append(f"return receipt differs: {path}")
    if set(entries) != expected:
        structural_errors.append("return exact-set differs")

    source_manifest_payload = source.get("package_manifest.json", b"")
    returned_manifest_payload = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    source_manifest = json.loads(source_manifest_payload or b"{}")
    if not (
        returned.get("install_name") == INSTALL_NAME
        and returned.get("records") == records
        and returned_manifest_payload == source_manifest_payload
    ):
        structural_errors.append("return/source manifest binding differs")
    source_files = source_manifest.get("files", {})
    if not (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    ):
        structural_errors.append("source exact-set differs")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(entries, "evidence/observer_precompile.json")
    feature_binding = load_json(entries, "evidence/diagnostic_feature_binding.json")
    compile_status = integer_entry(entries, "evidence/compile_exit_status.txt", 125)
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")

    package_ok = package_preflight.get("valid") is True
    install_ok = (
        install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
    )
    observer_ok = (
        observer_preflight.get("valid") is True
        and observer_preflight.get("observed_sha256") == OBSERVER_SHA256
        and sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
        == OBSERVER_SHA256
    )
    compile_invoked = (
        "vcs" in compile_driver.lower()
        and "native_return_observer.svh" in compile_log
        and "NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f" in compile_driver
    )
    xmre = parse_xmre(compile_log)
    xmre_lines = sorted({int(item["line"]) for item in xmre})
    xmre_tokens = sorted({str(item["token"]) for item in xmre})
    expected_xmre = (
        compile_status == 2
        and run_status == 125
        and signal == "NONE"
        and len(xmre) == 10
        and xmre_tokens == ["WR_MSE"]
        and min(xmre_lines, default=0) == 6306
        and max(xmre_lines, default=0) == 6346
        and "Maximum error count reached" in compile_log
        and "10 errors" in compile_log
        and "Error 255" in compile_driver
    )
    if not all([package_ok, install_ok, observer_ok, compile_invoked]):
        structural_errors.append("preflight/observer/compile invocation differs")
    if not expected_xmre:
        structural_errors.append("v48 XMRE signature differs")

    returned_cloud = source_manifest.get("cloud_rtl_authority", {})
    cloud_manifest_bound = (
        returned_cloud.get("approved_commit") == CLOUD_RTL
        and returned_cloud.get("local_disk_commit") == CLOUD_RTL
        and returned_cloud.get(
            "actual_compile_identity_required_in_return"
        )
        is True
    )
    actual_compile_root = "/home/panqs/ndp/NDP_copy01"
    actual_compile_root_observed = actual_compile_root in compile_log
    actual_commit_receipt_present = False

    formal_expected = int(gate.get("formal_d_expected", 320))
    formal_present = int(gate.get("formal_d_present", 0))
    formal_missing = int(gate.get("formal_d_missing", formal_expected))
    formal_mismatch = int(gate.get("formal_d_mismatch", 0))
    natural_terminal = gate.get("natural_terminal_observed") is True
    simulation_started = False
    joint = (
        compile_status == 0
        and run_status == 0
        and natural_terminal
        and formal_present == formal_expected
        and formal_missing == 0
        and formal_mismatch == 0
    )

    report = {
        "schema": "node0004-v48-return-analysis-v1",
        "valid": not structural_errors,
        "errors": structural_errors,
        "RETURN_ANALYSIS": {
            "status": "PACKAGE_LOCAL_OBSERVER_MSE3_GENERATE_BRANCH_XMRE",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": (
                    "CDA-SERVER-RETURN-TRANSPORT-"
                    "USER-ATTESTED-NO-SIDECAR-001"
                ),
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_valid": source_sidecar_valid,
            },
            "return_meta": return_meta,
            "source_meta": source_meta,
            "checks": {
                "return_crc_path_root": not return_errors,
                "return_exact_set_allowlist_receipts": set(entries) == expected,
                "return_source_manifest_binding": (
                    returned_manifest_payload == source_manifest_payload
                ),
                "package_preflight": package_ok,
                "install_preflight_runtime_d_absent": install_ok,
                "observer_precompile_identity": observer_ok,
                "compile_invoked": compile_invoked,
                "production_vcs_compile": False,
                "diagnostic_simulation_started": simulation_started,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "natural_terminal": natural_terminal,
            "formal_d_expected": formal_expected,
            "formal_d_present": formal_present,
            "formal_d_missing": formal_missing,
            "formal_d_mismatch": formal_mismatch,
            "joint_result_gate": joint,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "ACTUAL_RTL_IDENTITY": {
            "source_manifest_cloud_commit": returned_cloud.get(
                "approved_commit"
            ),
            "source_manifest_bound": cloud_manifest_bound,
            "actual_compile_root": actual_compile_root,
            "actual_compile_root_observed": actual_compile_root_observed,
            "actual_compile_commit_receipt_present": actual_commit_receipt_present,
            "adjudication": (
                "The return proves the production filelist/root and the exact "
                "generate-branch shape needed for this first divergence. It "
                "does not contain a separate immutable Git-commit receipt, so "
                "the formal actual-commit claim remains bounded to the returned "
                "manifest plus the user-confirmed/current local 0cc authority."
            ),
        },
        "LAST_PROVEN_GOOD": (
            "PACKAGE_INSTALL_PREFLIGHT_AND_PRODUCTION_VCS_PARSE_REACHED_"
            "OBSERVER_ELABORATION"
        ),
        "FIRST_DIVERGENCE": (
            "OBSERVER_MSE3_PATH_SELECTS_NONEXISTENT_WR_MSE_GENERATE_BRANCH"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "PACKAGE_LOCAL_OBSERVER_SCOPE_BINDING_ERROR_CONFIRMED",
            "classification": "PACKAGE_LOCAL_DELIVERY_SELF_AUDIT_ESCAPE",
            "observer": {
                "sha256": OBSERVER_SHA256,
                "lines": xmre_lines,
                "token": "WR_MSE",
                "xmre_count": len(xmre),
            },
            "rtl_consumer": {
                "path": (
                    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/"
                    "Stream_Engine.sv"
                ),
                "sha256": STREAM_ENGINE_SHA256,
                "generate_for_line": 448,
                "read_branch_line": 449,
                "write_branch_line": 506,
                "equation": (
                    "MSE_IDX < MEMORY_RD_STREAM_ENGINE_NUM selects RD_MSE; "
                    "MSE3 therefore resolves through "
                    "MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine"
                ),
            },
            "mechanism": (
                "The v48 observer correctly selected logical MSE3 but used the "
                "write-stream generate path WR_MSE.u_Memory_WR_Stream_Engine. "
                "MSE3 is a read stream, so the generated instance is "
                "RD_MSE.u_Memory_RD_Stream_Engine. VCS reports ten WR_MSE "
                "XMREs and stops before simulator creation."
            ),
            "minimum_fix": (
                "Change only the v48-added MSE3 observer hierarchy from "
                "WR_MSE.u_Memory_WR_Stream_Engine to "
                "RD_MSE.u_Memory_RD_Stream_Engine, retain all qualified "
                "predicates, and rebuild a fresh package identity."
            ),
            "functional_rtl_root_cause_proven": False,
            "configuration_root_cause_proven": False,
            "lc9_dynamic_branch_adjudication_reached": False,
        },
        "BLOCKER_DELTA": {
            "closed": [],
            "opened": [
                "B_CONV_NODE0004_V48_OBSERVER_MSE3_GENERATE_BRANCH_XMRE",
            ],
            "preserved": [
                "B_CONV_NODE0004_LC9_TO_LC7_AND_MSE3_ACTUAL_BRANCH_ACCEPT_UNOBSERVED",
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "PACKAGE_AUDIT_ESCAPE_ROOT_CAUSE": {
            "status": "ACTUAL_GENERATE_BRANCH_NOT_VERIFIED_BY_LOCAL_SCOPE_GATE",
            "safe_compile_stub_claim": (
                "runner reachability and finalizer behavior only; no HDL "
                "elaboration or generate-branch name resolution"
            ),
            "old_audit_claim_correction": (
                "v48 actual-consumer coverage and focused scope PASS did not "
                "prove the selected MSE3 generate branch. Those claims remain "
                "valid for listed token coverage but are withdrawn as evidence "
                "of production elaboration readiness."
            ),
            "rule_intent": (
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001 and "
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001 "
                "already require exact actual target hierarchy and a focused "
                "wrapper that does not fabricate leaves."
            ),
            "validator_noncompliance": (
                "The v48 validator matched expected path strings and private "
                "leaf names but did not derive the RD_MSE/WR_MSE generate "
                "selection from Stream_Engine.sv or compile the exact final "
                "observer against that generate wrapper."
            ),
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_SUFFICIENT_VALIDATOR_NONCOMPLIANCE",
            "confirmed_rule_ids": [
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "claim_boundary": (
                "No public rule change is needed for this escape. The fresh "
                "successor must add an exact generate-branch positive and a "
                "wrong-branch negative derived from the actual final consumer."
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
