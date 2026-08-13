#!/usr/bin/env python3
"""Build the bank-row-relocated node0071 -> node0075 cloud-aware v6 package."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_PATH = (
    ROOT
    / "tools/build_node0071_node0075_e1fb0f7_native_ordering_package_v5.py"
)
SPEC = importlib.util.spec_from_file_location("node0071_node0075_v5_builder", BASE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load v5 package builder")
BASE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BASE)

PACKAGE_NAME = "r5_n71_n75_0cc_bankrow_v9"
PACKAGE_DIR = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages" / PACKAGE_NAME
)
ZIP_PATH = PACKAGE_DIR.with_suffix(".zip")
SIDECAR = Path(str(ZIP_PATH) + ".sha256")
BUILD_ID = "r5-node0071-node0075-0ccae91-bankrow-package-v9"
REPORT_DIR = ROOT / "artifacts/operator_config_validation" / BUILD_ID
INTEGRATION = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-bankrow-relocated-integration-v2"
)
N75_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2/"
    "materializer_report.json"
)
V5_RETURN_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-v5-return-analysis/report.json"
)
CLOUD_IMPACT = INTEGRATION / "cloud_rtl_0ccae91_impact_audit.json"
CAUSAL_LEDGER = INTEGRATION / "causal_transaction_ledger.json"
BOUNDARY_MICROTRACE = INTEGRATION / "boundary_microtrace.json"
RUNTIME_WRAPPER = ROOT / "tools/node0071_node0075_bankrow_server_runtime_v2.py"
RUNTIME_BASE = ROOT / "tools/node0071_node0075_native_ordering_server_runtime.py"


def cloud_identity_runner_block() -> str:
    return r'''python3 - "$server_root" "$evidence_root/cloud_rtl_identity.json" "$compile_status" <<'PY' || true
import hashlib, json, pathlib, sys
root=pathlib.Path(sys.argv[1])
out=pathlib.Path(sys.argv[2])
compile_status=int(sys.argv[3])
paths=[
 "Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC.sv",
 "Slice/Index_Generation_Array/IGA_ROW_LC/IGA_ROW_LC_Inbuffer.sv",
 "Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
 "Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
 "Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster.sv",
 "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv",
 "Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv",
 "Slice/Specialized_Array/SA_Inport/SA_Inport_Connect.sv",
 "includes/NDP_Parameters.svh",
]
records=[]
for rel in paths:
    path=root/"rtl"/rel
    payload=path.read_bytes() if path.is_file() else None
    records.append({
        "path": "rtl/"+rel,
        "exists": payload is not None,
        "bytes": None if payload is None else len(payload),
        "sha256": None if payload is None else hashlib.sha256(payload).hexdigest(),
    })
payload={
 "schema":"cloud-rtl-post-compile-nonblocking-identity-v1",
 "cloud_authority_commit":"0ccae916ef61904a64d6cf8ec1d1931b45e428d8",
 "local_expected_hint":"e1fb0f7bb2761d6c804867de0c5d2cb77554c48d",
 "compile_exit_status":compile_status,
 "identity_difference_is_simulation_blocker":False,
 "comparison_or_match_claim":False,
 "actual_files":records,
}
out.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
PY
'''


def configure_base() -> None:
    BASE.PACKAGE_NAME = PACKAGE_NAME
    BASE.PACKAGE_DIR = PACKAGE_DIR
    BASE.ZIP_PATH = ZIP_PATH
    BASE.SIDECAR = SIDECAR
    BASE.BUILD_ID = BUILD_ID
    BASE.REPORT_DIR = REPORT_DIR
    BASE.INTEGRATION = INTEGRATION
    BASE.INTEGRATION_WORKLOAD = INTEGRATION / "workload"
    BASE.INTEGRATION_REPORT = INTEGRATION / "report.json"
    BASE.INTEGRATION_VALIDATION = INTEGRATION / "validation.json"
    BASE.N75_REPORT = N75_REPORT
    BASE.V3_RETURN_ANALYSIS = V5_RETURN_ANALYSIS
    BASE.RUNTIME_SOURCE = RUNTIME_WRAPPER
    runner = BASE.RUNNER.replace(
        'install_name="r5_n71_n75_e1f_native_v5"',
        f'install_name="{PACKAGE_NAME}"',
    )
    marker = "compile_status=$?\nset -e\n"
    if runner.count(marker) != 1:
        raise RuntimeError("v5 runner compile-status insertion point differs")
    BASE.RUNNER = runner.replace(
        marker,
        marker + cloud_identity_runner_block(),
        1,
    )
    finalize_marker = (
        "  fi\n"
        "  python3 \"$runtime\" analyze --package-root \"$package_root\""
    )
    if BASE.RUNNER.count(finalize_marker) != 1:
        raise RuntimeError("v5 runner finalizer evidence insertion point differs")
    cloud_return = (
        "  fi\n"
        "  if [ -f \"$evidence_root/cloud_rtl_identity.json\" ]; then\n"
        "    printf 'cloud_rtl_identity_json=' "
        ">>\"$evidence_root/observer_binding.txt\"\n"
        "    tr '\\n' ' ' <\"$evidence_root/cloud_rtl_identity.json\" "
        ">>\"$evidence_root/observer_binding.txt\"\n"
        "    printf '\\n' >>\"$evidence_root/observer_binding.txt\"\n"
        "  fi\n"
        "  python3 \"$runtime\" analyze --package-root \"$package_root\""
    )
    BASE.RUNNER = BASE.RUNNER.replace(finalize_marker, cloud_return, 1)


configure_base()
ORIGINAL_COPY_PAYLOADS = BASE._copy_payloads
ORIGINAL_RETURN_ALLOWLIST = BASE._return_allowlist
ORIGINAL_BUILD_TREE = BASE._build_tree


def copy_payloads(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    sca, sca_d = ORIGINAL_COPY_PAYLOADS(root)
    source_sca = BASE.load_json(INTEGRATION / "workload/sca_cfg.json")
    exec_base = source_sca["Exec_Base"]
    exec_length = source_sca["Exec_Length"]
    repeat_num = source_sca["Repeat_Num"]
    if (
        exec_base != "0x002ACC00"
        or exec_length != 518
        or repeat_num != 32
    ):
        raise BASE.PackageError("relocated integration exec binding differs")
    sca["Exec_Base"] = exec_base
    sca["Exec_Length"] = exec_length
    sca["ExecutionPlan"]["base_addr"] = exec_base
    sca["Repeat_Num"] = repeat_num
    BASE.write_json(root / "workload/sca_cfg.json", sca)
    return sca, sca_d


def return_allowlist(readback_checks: list[dict[str, Any]]) -> dict[str, Any]:
    return ORIGINAL_RETURN_ALLOWLIST(readback_checks)


def build_tree(root: Path) -> dict[str, Any]:
    manifest = ORIGINAL_BUILD_TREE(root)
    for source, destination in (
        (V5_RETURN_ANALYSIS, root / "p/v5_return_analysis.json"),
        (CLOUD_IMPACT, root / "p/cloud_rtl_0ccae91_impact.json"),
        (CAUSAL_LEDGER, root / "p/causal_transaction_ledger.json"),
        (BOUNDARY_MICROTRACE, root / "p/boundary_microtrace.json"),
        (RUNTIME_BASE, root / "pkg/runtime_base.py"),
    ):
        BASE.copy_exact(source, destination)

    manifest["schema"] = (
        "node0071-node0075-bankrow-cloud-aware-server-package-v2"
    )
    manifest["successor_of"] = {
        "package_name": "r5_n71_n75_e1f_native_v5",
        "return_zip_sha256": (
            "bb9b98ddfb70e1b6474ff56bfcd9f6d3253f28bd7390b0c9f760c0e7bfe738c4"
        ),
        "return_classification": (
            "PRODUCTION_COMPILE_PASS_SIM_STARTED_PRE_STAGE_SCA_BANK_ROW_FAILURE"
        ),
        "first_divergence": (
            "first execplan preload at 0x01706400 decoded as disabled bank2 "
            "row 0x1c19 and returned X before CONFIG/stage00"
        ),
        "repair_scope": (
            "relocate D/CONFIG/execplan storage to enabled bank0 rows; "
            "arithmetic, scheduling, observer, golden and functional RTL unchanged"
        ),
        "causal_materialized_semantics_changed": True,
        "package_namespace_sca_path_bytes_changed": True,
    }
    manifest["supersedes_held_identity"] = {
        "package_name": "r5_n71_n75_0cc_bankrow_v8",
        "status": "HELD_PRE_AUDIT_RUNTIME_EXEC_BASE_CONSUMER_ESCAPE",
        "reason": (
            "v8 corrected the final SCA address and 162-member allowlist but "
            "the frozen runtime preflight still required Exec_Base 0x01706400; "
            "v9 package-locally updates only that exact consumer guard"
        ),
        "prior_held_identity": {
            "package_name": "r5_n71_n75_0cc_bankrow_v7",
            "status": "HELD_PRE_AUDIT_RETURN_ALLOWLIST_CONTRACT_ESCAPE",
        },
    }
    manifest["materialized_config_rule_applicability"] = {
        "changed_surface": (
            "D_CONFIG_EXECPLAN_PHYSICAL_STORAGE_ADDRESS_RELOCATION_ONLY"
        ),
        "causal_transaction_ledger": {
            "rule_id": "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "applicable": True,
            "status": "PASS",
            "path": "p/causal_transaction_ledger.json",
        },
        "boundary_microtrace": {
            "rule_id": "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "applicable": True,
            "status": "PASS",
            "dut_executed": False,
            "path": "p/boundary_microtrace.json",
        },
    }
    manifest["cloud_rtl_authority"] = {
        "rule_id": (
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001"
        ),
        "repository": "xlsjdjdk/Trassic2.0_RTL",
        "branch": "master",
        "cloud_approved_commit": (
            "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
        ),
        "local_expected_hint": (
            "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
        ),
        "affected_operator_causal_cone": True,
        "local_targeted_audit": "p/cloud_rtl_0ccae91_impact.json",
        "actual_identity_receipt": (
            "e/observer_binding.txt#cloud_rtl_identity_json"
        ),
        "actual_local_or_cloud_difference_blocks_simulation": False,
        "post_compile_chronology": (
            "collect identity receipt, then continue to simulator whenever "
            "production compile exit is zero"
        ),
        "dynamic_revalidation_required": [
            "producer downstream acceptance before node0075 pass00 first read",
            "8192 actual A request/data accepts and pass/slice hashes",
            "natural terminal",
            "144 formal D conjunction",
        ],
    }
    manifest["observer_change_applicability"] = {
        "observer_bytes_changed_from_v5": False,
        "parser_or_canonical_predicate_changed": False,
        "diagnostic_predicate_trace_rule_applicable": False,
        "receipt_reuse_basis": (
            "package-local observer byte-equal to production-compiled v5; "
            "cloud-changed private RD leaf name/width is byte-equal and its "
            "affected binding is recorded in p/cloud_rtl_0ccae91_impact.json"
        ),
        "production_compile_remains_dynamic_gate": True,
    }
    manifest["return_allowlist"] = return_allowlist(
        manifest["readback_checks"]
    )
    manifest["source_inputs"].extend(
        BASE.identity(path)
        for path in (
            V5_RETURN_ANALYSIS,
            CLOUD_IMPACT,
            CAUSAL_LEDGER,
            BOUNDARY_MICROTRACE,
            RUNTIME_BASE,
        )
    )
    feedback = manifest["rule_feedback"]
    feedback["type"] = "RULE_DELTA_PROPOSAL"
    if (
        "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001"
        not in feedback["confirmed_rule_ids"]
    ):
        feedback["confirmed_rule_ids"].append(
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001"
        )
    feedback["rule_delta_proposal"] = [
        {
            "id": "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
            "non_synonymous_evidence": (
                "v5 stayed below aggregate 24MiB capacity yet its first SCA "
                "preload decoded to disabled bank2 row 0x1c19 and returned X"
            ),
            "proposal": (
                "Decode every changed final address-bound interval through "
                "physical bank/row/column fields and reject disabled row holes, "
                "including first/final and crossed-bank lines."
            ),
        }
    ]
    manifest["workload_files"] = BASE.records(root / "workload")
    manifest["files"] = BASE.records(root, {"TEST_PACKAGE_MANIFEST.json"})
    BASE.write_json(root / "TEST_PACKAGE_MANIFEST.json", manifest)
    return manifest


BASE._copy_payloads = copy_payloads
BASE._return_allowlist = return_allowlist
BASE._build_tree = build_tree


def main() -> int:
    required = [
        V5_RETURN_ANALYSIS,
        CLOUD_IMPACT,
        CAUSAL_LEDGER,
        BOUNDARY_MICROTRACE,
        RUNTIME_WRAPPER,
        RUNTIME_BASE,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print(f"PACKAGE_BUILD_FAIL: required v6 input missing: {missing}")
        return 1
    for path in (CLOUD_IMPACT, CAUSAL_LEDGER, BOUNDARY_MICROTRACE):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("passed") is False or payload.get("status") not in {
            "AFFECTED_CAUSAL_CONE_REVALIDATION_PASS",
            "PASS",
        }:
            print(f"PACKAGE_BUILD_FAIL: prerequisite not pass: {path}")
            return 1
    return BASE.main()


if __name__ == "__main__":
    raise SystemExit(main())
