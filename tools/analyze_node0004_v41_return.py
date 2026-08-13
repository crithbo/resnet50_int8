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


INSTALL_NAME = "r5_n4_hw_v41_wrterm2_diag"
RETURN_ROOT = f"{INSTALL_NAME}_return"
RETURN_SHA256 = "b351089eb76255f23f8190e181a05cbe9bbac1d01c16b555b6eaa3af4424b011"
SOURCE_SHA256 = "e314dfb65b1bc7b8ad0403aa559a79508073092988a45e20b8637f21917933b0"
OBSERVER_SHA256 = "164919ed7533e8f9b29a64a13f0bd7521887ce8577ea5896e13b0e91fcff3db0"
SERVER_RULE_SHA256 = "da0e2dc8dab9a64d4eaca3f15ee0634b3af6b299dfa505e192d6b6bf30ff12b8"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    source_sidecar = args.source_sidecar.resolve()
    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    sidecar_valid = (
        source_sidecar.read_text(encoding="ascii").strip()
        == f"{source_sha}  {source_zip.name}"
    )
    if not sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, return_errors, return_meta = safe_entries(return_zip, RETURN_ROOT)
    source, source_errors, source_meta = safe_entries(source_zip, INSTALL_NAME)
    errors.extend(return_errors)
    errors.extend(source_errors)

    allowlist = load_json(entries, "RETURN_ALLOWLIST.json")
    returned = load_json(entries, "RETURN_MANIFEST.json")
    records = allowlist.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    receipts: dict[str, bool] = {}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        receipts[path] = (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        )
        if not receipts[path]:
            errors.append(f"return receipt differs: {path}")
    return_exact = set(entries) == expected
    if not return_exact:
        errors.append("return exact-set differs")

    source_manifest_payload = source.get("package_manifest.json", b"")
    returned_manifest_payload = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    return_binding = (
        returned.get("install_name") == INSTALL_NAME
        and returned.get("records") == records
        and returned_manifest_payload == source_manifest_payload
    )
    if not return_binding:
        errors.append("return/source manifest binding differs")
    source_manifest = json.loads(source_manifest_payload or b"{}")
    source_files = source_manifest.get("files", {})
    source_exact = (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    )
    if not source_exact:
        errors.append("source exact-set differs")

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

    xmre = re.search(
        r"native_return_observer\.svh,\s*(?P<line>\d+).*?"
        r"token '(?P<token>[^']+)'.*?"
        r"Source info: (?P<source>.*?)\.\.\.Instance stack trace:",
        compile_log,
        re.DOTALL,
    )
    xmre_line = int(xmre.group("line")) if xmre else None
    xmre_token = xmre.group("token") if xmre else None
    exact_xmre = (
        xmre_line == 5974
        and xmre_token == "mem_idx_gotten"
        and "u_Memory_AG_Idx_Queue.mem_idx_gotten[1]" in compile_log
    )
    if not exact_xmre:
        errors.append("expected package-local observer XMRE not uniquely found")

    observer_payload = source.get("tb_probe/native_return_observer.svh", b"")
    observer_identity = sha256_bytes(observer_payload) == OBSERVER_SHA256
    if not observer_identity:
        errors.append("source observer identity differs")
    observer_lines = observer_payload.decode("utf-8", errors="replace").splitlines()
    exact_source_line = (
        0 < 5974 <= len(observer_lines)
        and ".u_Memory_AG_Idx_Queue.mem_idx_gotten[1]," in observer_lines[5973]
    )
    if not exact_source_line:
        errors.append("source line 5974 does not contain the failing leaf")

    rtl_path = (
        ROOT
        / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
        / "Memory_AG_Idx_Queue.sv"
    )
    rtl_text = rtl_path.read_text(encoding="utf-8")
    intended_leaf_unique = (
        "reg  [`MSE_MQ_INPORT_NUM-1:0] mem_idx_gotten_bit;" in rtl_text
        and "mem_idx_gotten[" not in rtl_text
    )
    if not intended_leaf_unique:
        errors.append("intended RTL leaf is not unique")

    package_ok = package_preflight.get("valid") is True
    install_ok = (
        install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
    )
    observer_preflight_ok = (
        observer_preflight.get("valid") is True
        and observer_preflight.get("observed_sha256") == OBSERVER_SHA256
    )
    compile_failure_bound = (
        compile_status == 2
        and run_status == 125
        and signal == "NONE"
        and gate.get("compile_succeeded") is False
        and feature_binding.get("status") == "NOT_REACHED_COMPILE_FAILED"
        and "Parsing included file" in compile_log
        and "native_return_observer.svh" in compile_log
        and "1 error" in compile_log
        and "vcs" in compile_driver.lower()
    )
    if not (package_ok and install_ok and observer_preflight_ok):
        errors.append("precompile receipt gate differs")
    if not compile_failure_bound:
        errors.append("compile failure boundary differs")

    report = {
        "schema": "node0004-v41-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "PACKAGE_LOCAL_OBSERVER_XMRE_COMPILE_FAILURE",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "rule": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
                "sidecar_valid": sidecar_valid,
            },
            "return_meta": return_meta,
            "source_meta": source_meta,
            "checks": {
                "return_crc_path_root": not return_errors,
                "return_exact_set_allowlist_receipts": return_exact
                and all(receipts.values()),
                "return_source_manifest_binding": return_binding,
                "source_crc_path_root": not source_errors,
                "source_manifest_exact_set": source_exact,
                "package_preflight": package_ok,
                "install_preflight_runtime_d_absent": install_ok,
                "observer_precompile_identity": observer_preflight_ok,
                "actual_vcs_compile_invoked": "vcs" in compile_driver.lower(),
                "exact_xmre": exact_xmre,
                "exact_source_line": exact_source_line,
                "intended_leaf_unique": intended_leaf_unique,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "compile_succeeded": False,
            "simulation_started": False,
            "natural_terminal": False,
            "formal_d_expected": 320,
            "formal_d_present": 0,
            "formal_d_missing": 320,
            "formal_d_mismatch": 0,
            "joint_result_gate": False,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "LAST_PROVEN_GOOD": (
            "PACKAGE_AND_INSTALL_PREFLIGHT_PASS_AND_VCS_PARSES_FINAL_OBSERVER"
        ),
        "FIRST_DIVERGENCE": (
            "VCS_SCOPE_RESOLUTION_FAILS_ON_OBSERVER_LINE_5974_TOKEN_MEM_IDX_GOTTEN"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "NOT_EVALUATED_COMPILE_FAILED",
            "reason": (
                "v41 did not start simulation, so no corrected true-final or "
                "post-terminal DUT chronology exists in this return"
            ),
        },
        "PACKAGE_AUDIT_ESCAPE_ROOT_CAUSE": {
            "source": "tb_probe/native_return_observer.svh",
            "line": 5974,
            "token": "mem_idx_gotten",
            "actual_rtl_source": str(rtl_path.relative_to(ROOT)),
            "actual_rtl_declared_leaf": "mem_idx_gotten_bit",
            "mechanism": (
                "The observer references a nonexistent private leaf. The actual "
                "module declares a three-bit mem_idx_gotten_bit register."
            ),
            "minimum_fix": (
                "Remove the nonessential private gotten-state display field. "
                "The existing module-port tag/backpressure surfaces and "
                "qualified accept predicate already distinguish the candidate; "
                "this is preferred over retaining a private XMR."
            ),
            "safe_stub_limit": (
                "The prior safe compile stub proved runner reachability and "
                "finalizer behavior, not production hierarchy name resolution."
            ),
            "functional_rtl_modified": False,
        },
        "BLOCKER_DELTA": {
            "opened": "B_CONV_NODE0004_V41_OBSERVER_MEM_IDX_GOTTEN_XMRE",
            "preserved_unreached": [
                "B_CONV_NODE0004_WRTERM_FINAL_DESCRIPTOR_PREDICATE_AND_POST_TERMINAL_OWNER_UNRESOLVED",
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_SUFFICIENT",
            "current_server_rule_sha256": SERVER_RULE_SHA256,
            "rule_ids": [
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
                "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            ],
            "evidence": (
                "The current rules require exact private-XMR ownership proof, "
                "final-exact predicate traces, and one impact-scoped release "
                "matrix; no new public rule is needed."
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
