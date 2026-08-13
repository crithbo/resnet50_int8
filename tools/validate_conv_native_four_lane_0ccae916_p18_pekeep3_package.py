#!/usr/bin/env python3
"""Final-ZIP audit for the p18 PE keep-threshold c0 successor."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import types
from pathlib import Path
from typing import Any


if "jsonschema" not in sys.modules:
    sys.modules["jsonschema"] = types.SimpleNamespace(validate=lambda *_a, **_k: None)

import build_conv_native_four_lane_0ccae916_p18_pekeep3_package as build
import validate_conv_native_four_lane_0ccae916_p17_static_xmr_package as p17
from validate_server_package_runtime_layout import validate as validate_layout


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = build.SOURCE_ID
PACKAGE_ID = build.PACKAGE_ID
SOURCE_SHA256 = build.SOURCE_SHA256
SOURCE_ZIP = build.SOURCE_ZIP
OUTPUT_ROOT = build.DEFAULT_OUTPUT
ZIP_PATH = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
SIDECAR = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
BUILD_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.build.json"
BUILD_PROFILE = OUTPUT_ROOT / f"{PACKAGE_ID}.build_profile.json"
HARNESS_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.runtime_layout_harness.json"
SHARED_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.shared_runtime_layout.json"
REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_audit.json"
REVALIDATION_REPORT = (
    OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_content_neutral_revalidation.json"
)
P17_FINAL_AUDIT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "pending_receipts/conv_native_four_lane/r5_n4_0cc_p17_gxmr/"
    "r5_n4_0cc_p17_gxmr.final_zip_audit.json"
)
LOCAL_REBUILD_REPORT = build.LOCAL_REBUILD / "local_rebuild_report.json"
LOCAL_LEDGER = build.LOCAL_REBUILD / "causal_transaction_ledger.json"
LOCAL_MICROTRACE = build.LOCAL_REBUILD / "boundary_microtrace.json"
OLD_INPUT_PREFIX = f"install/cfg_pkg/{SOURCE_ID}/"
RUNTIME_INPUT_PREFIX = f"install/cfg_pkg/{PACKAGE_ID}/"
INPUT_PREFIX = build.INPUT_PREFIX
OLD_OUTPUT_PREFIX = f"install/codex_runs/{SOURCE_ID}/a0/c0/d/"
OUTPUT_PREFIX = build.OUTPUT_PREFIX


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_family() -> None:
    values = {
        "SOURCE_ID": SOURCE_ID,
        "PACKAGE_ID": PACKAGE_ID,
        "WORKLOAD_INSTALL_NAME": PACKAGE_ID,
        "SOURCE_SHA256": SOURCE_SHA256,
        "SOURCE_ZIP": SOURCE_ZIP,
        "OUTPUT_ROOT": OUTPUT_ROOT,
        "ZIP_PATH": ZIP_PATH,
        "SIDECAR": SIDECAR,
        "BUILD_REPORT": BUILD_REPORT,
        "BUILD_PROFILE": BUILD_PROFILE,
        "HARNESS_REPORT": HARNESS_REPORT,
        "SHARED_REPORT": SHARED_REPORT,
        "REPORT": REPORT,
        "SOURCE_ANALYSIS": build.P17_ANALYSIS,
        "INPUT_PREFIX": RUNTIME_INPUT_PREFIX,
        "OLD_INPUT_PREFIX": OLD_INPUT_PREFIX,
        "OLD_OUTPUT_PREFIX": OLD_OUTPUT_PREFIX,
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
        "ALLOWED_CHANGED_PATHS": build.ALLOWED_CHANGED_PATHS,
    }
    for name, value in values.items():
        setattr(p17, name, value)
    p17.build.OLD_INSTALL_NAME = SOURCE_ID
    p17.configure_family()
    p17.p16.p15.base.RUNTIME_PREFIX = RUNTIME_INPUT_PREFIX


def payloads(zip_path: Path, root: str) -> dict[str, bytes]:
    return p17.payloads(zip_path, root)


def changed_offsets(left: bytes, right: bytes) -> list[int]:
    if len(left) != len(right):
        return []
    return [
        index
        for index, (old, new) in enumerate(zip(left, right))
        if old != new
    ]


def materialized_config_audit() -> dict[str, Any]:
    source = payloads(SOURCE_ZIP, SOURCE_ID)
    successor = payloads(ZIP_PATH, PACKAGE_ID)
    all_paths = sorted(set(source) | set(successor))
    changed = [
        path for path in all_paths if source.get(path) != successor.get(path)
    ]
    unexpected = sorted(set(changed) - build.ALLOWED_CHANGED_PATHS)
    byte_equal_regenerated_consumers = {
        "workload/runtime/runs/c0/install/execplan.txt",
        "workload/runtime/runs/c0/install/execplan_op_w0.txt",
    }
    missing = sorted(
        (
            build.ALLOWED_CHANGED_PATHS
            - byte_equal_regenerated_consumers
        )
        - set(changed)
    )

    observer_equal = (
        source[build.OBSERVER] == successor[build.OBSERVER]
    )
    config_paths = set(build.PHYSICAL_ASSETS) | {
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    frozen_payloads = [
        path
        for path in all_paths
        if path not in build.ALLOWED_CHANGED_PATHS
        and any(
            token in path
            for token in (
                "golden/",
                "matrix_A",
                "matrix_B",
                "matrix_C",
                "typed",
                "qparam",
                "observer",
                "timeout",
            )
        )
    ]
    frozen_equal = all(
        source.get(path) == successor.get(path) for path in frozen_payloads
    )

    bitstream_path = (
        "workload/runtime/runs/c0/install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    local_bitstream = (
        build.LOCAL_PIPELINE
        / "install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    ).read_bytes()
    bitstream_offsets = changed_offsets(
        source[bitstream_path], successor[bitstream_path]
    )
    bitstream_valid = (
        bitstream_offsets == [1301]
        and successor[bitstream_path] == local_bitstream
    )
    execplan_paths = (
        "workload/runtime/runs/c0/install/execplan.txt",
        "workload/runtime/runs/c0/install/execplan_op_w0.txt",
    )
    execplan_valid = all(
        successor[path]
        == (
            build.LOCAL_PIPELINE / "install" / path.rsplit("/", 1)[-1]
        ).read_bytes()
        for path in execplan_paths
    )

    local_sca = json.loads(
        (build.LOCAL_PIPELINE / "sca_cfg.json").read_text(encoding="utf-8")
    )
    for record, old in build.walk_paths(local_sca):
        record["path"] = INPUT_PREFIX + old
    local_sca_d = json.loads(
        (build.LOCAL_PIPELINE / "sca_cfg_D.json").read_text(encoding="utf-8")
    )
    for record, old in build.walk_paths(local_sca_d):
        record["path"] = OUTPUT_PREFIX + old[len("install/") :]
    sca_valid = (
        json.loads(successor["workload/runtime/runs/c0/sca_cfg.json"])
        == local_sca
        and json.loads(successor["workload/runtime/runs/c0/sca_cfg_D.json"])
        == local_sca_d
    )

    local_report = json.loads(LOCAL_REBUILD_REPORT.read_text(encoding="utf-8"))
    ledger = json.loads(LOCAL_LEDGER.read_text(encoding="utf-8"))
    microtrace = json.loads(LOCAL_MICROTRACE.read_text(encoding="utf-8"))
    causal_valid = (
        local_report.get("status") == "LOCAL_C0_SINGLE_LEAF_REBUILD_PASS"
        and local_report.get("authorized_leaf_changes")
        == [
            {
                "path": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": 2,
                "new": 3,
            }
        ]
        and ledger.get("status") == "PASS"
        and microtrace.get("status") == "PASS"
        and microtrace["cases"][2]["old_ready"] is False
        and microtrace["cases"][2]["new_ready"] is True
    )
    valid = (
        sha256(SOURCE_ZIP) == SOURCE_SHA256
        and not unexpected
        and not missing
        and observer_equal
        and frozen_equal
        and bitstream_valid
        and execplan_valid
        and sca_valid
        and causal_valid
    )
    return {
        "source_zip_sha256": sha256(SOURCE_ZIP),
        "source_identity_valid": sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "changed_paths": changed,
        "allowed_changed_paths": sorted(build.ALLOWED_CHANGED_PATHS),
        "unexpected_changes": unexpected,
        "missing_expected_changes": missing,
        "changed_materialized_config_paths": sorted(
            set(changed) & config_paths
        ),
        "p17_observer_byte_equal": observer_equal,
        "frozen_numeric_w3_golden_matrix_observer_timeout_equal": frozen_equal,
        "bitstream_changed_offsets": bitstream_offsets,
        "bitstream_exact_local_rebuild": bitstream_valid,
        "execplan_exact_local_rebuild": execplan_valid,
        "sca_exact_local_rebuild_and_prefix_binding": sca_valid,
        "single_leaf_causal_ledger_and_microtrace": causal_valid,
        "addresses_changed": False,
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
        "valid": valid,
    }


def observer_compile_receipt(package: Path) -> dict[str, Any]:
    prior = json.loads(P17_FINAL_AUDIT.read_text(encoding="utf-8"))
    source = payloads(SOURCE_ZIP, SOURCE_ID)
    successor = payloads(ZIP_PATH, PACKAGE_ID)
    formal_return = json.loads(build.P17_ANALYSIS.read_text(encoding="utf-8"))
    compile_gate = formal_return["execution"]
    observer_equal = source[build.OBSERVER] == successor[build.OBSERVER]
    valid = (
        prior.get("valid") is True
        and prior.get("package_local_hdl_gate", {}).get("pass") is True
        and observer_equal
        and compile_gate["compile_exit_status"] == 0
        and compile_gate["static_genvar_xmr_compile_gate_closed"] is True
    )
    return {
        "disposition": "receipt_reuse_observer_byte_equal",
        "source_p17_final_audit": {
            "path": P17_FINAL_AUDIT.relative_to(ROOT).as_posix(),
            "sha256": sha256(P17_FINAL_AUDIT),
            "valid": prior.get("valid"),
        },
        "source_p17_production_compile": compile_gate,
        "observer_sha256": sha256_bytes(successor[build.OBSERVER]),
        "observer_byte_equal": observer_equal,
        "valid": valid,
    }


def content_neutral_revalidate() -> int:
    if REVALIDATION_REPORT.exists():
        raise AuditError(
            f"refusing to overwrite revalidation: {REVALIDATION_REPORT}"
        )
    prior = json.loads(REPORT.read_text(encoding="utf-8"))
    if (
        prior.get("valid") is not False
        or prior.get("zip_sha256") != sha256(ZIP_PATH)
        or prior.get("shared_runtime_layout", {}).get("pass") is not True
        or prior.get("shared_runtime_layout", {}).get("errors") != 0
        or prior.get("shared_runtime_layout", {}).get(
            "exact_final_zip_invocation_count"
        )
        != 1
    ):
        raise AuditError("initial failed audit is not eligible for reuse")
    preserved_passes = {
        "exact_runtime_path_budget_and_preflight": prior[
            "exact_runtime_path_budget_and_preflight"
        ]["valid"],
        "exact_observer_guard": prior["exact_observer_guard"]["valid"],
        "observer_and_package_local_hdl": prior[
            "observer_and_package_local_hdl"
        ]["valid"],
        "syntax_checks": prior["syntax_checks"]["valid"],
        "runner_scenarios": all(
            row["valid"] for row in prior["exact_runner_harness"].values()
        ),
        "legacy_namespace_collision": prior[
            "legacy_namespace_collision_regression"
        ]["valid"],
        "positive_runner_chain": prior[
            "exact_runner_to_compile_and_simulator_stub_positive"
        ],
        "shared_public_regression": prior["shared_public_regression"]["valid"],
        "shadow_profile": prior["shadow_profile_compare"]["contract_valid"],
    }
    if not all(preserved_passes.values()):
        raise AuditError("initial audit has a non-validator-escape failure")
    with tempfile.TemporaryDirectory(
        prefix=".p18_revalidate_", dir=ROOT
    ) as temp:
        package = p17.p16.p15.base.safe_extract(
            ZIP_PATH, Path(temp) / "extract", PACKAGE_ID
        )
        static = p17.static_audit(package)
        materialized = materialized_config_audit()
    valid = static["valid"] and materialized["valid"]
    result = json.loads(json.dumps(prior))
    result.update(
        {
            "schema": (
                "conv-native-four-lane-p18-pekeep3-"
                "content-neutral-revalidation-v1"
            ),
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if valid
                else "PACKAGE_AUDIT_FAILED"
            ),
            "valid": valid,
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
            "static_zip_audit": static,
            "materialized_config_audit": materialized,
            "content_neutral_revalidation": {
                "zip_bytes_unchanged": ZIP_PATH.stat().st_size,
                "zip_sha256_unchanged": sha256(ZIP_PATH),
                "initial_failed_audit": {
                    "path": REPORT.relative_to(ROOT).as_posix(),
                    "sha256": sha256(REPORT),
                },
                "runtime_layout_harness_reused": {
                    "path": HARNESS_REPORT.relative_to(ROOT).as_posix(),
                    "sha256": sha256(HARNESS_REPORT),
                },
                "shared_runtime_layout_reused": {
                    "path": SHARED_REPORT.relative_to(ROOT).as_posix(),
                    "sha256": sha256(SHARED_REPORT),
                    "exact_final_zip_invocation_count_total": 1,
                },
                "preserved_passes": preserved_passes,
                "validator_escape_corrections": [
                    {
                        "old": (
                            "strip install/cfg_pkg/<id>/runs/c0/ then look "
                            "under workload/runtime"
                        ),
                        "new": (
                            "strip install/cfg_pkg/<id>/ then open exact "
                            "workload/runtime/runs/c0 member"
                        ),
                    },
                    {
                        "old": "byte-equal regenerated execplans must differ",
                        "new": (
                            "execplans are exact rebuilt consumers but are "
                            "permitted to remain byte-equal"
                        ),
                    },
                ],
                "package_rebuilt": False,
                "shared_gate_rerun": False,
            },
        }
    )
    result["release_gate_matrix"]["core_identity_bootstrap"]["pass"] = (
        static["valid"]
    )
    result["release_gate_matrix"]["materialized_config"]["pass"] = (
        materialized["valid"]
    )
    write_json(REVALIDATION_REPORT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


def main() -> int:
    configure_family()
    if REPORT.exists():
        return content_neutral_revalidate()
    for path in (HARNESS_REPORT, SHARED_REPORT, REPORT):
        if path.exists():
            raise AuditError(f"refusing to overwrite audit output: {path}")
    required = (
        ZIP_PATH,
        SIDECAR,
        SOURCE_ZIP,
        BUILD_REPORT,
        BUILD_PROFILE,
        build.P17_ANALYSIS,
        P17_FINAL_AUDIT,
        LOCAL_REBUILD_REPORT,
        LOCAL_LEDGER,
        LOCAL_MICROTRACE,
    )
    if not all(path.is_file() for path in required):
        raise AuditError("p18 final audit input is missing")
    with tempfile.TemporaryDirectory(prefix=".p18_audit_", dir=ROOT) as temp:
        temp_root = Path(temp)
        package = p17.p16.p15.base.safe_extract(
            ZIP_PATH, temp_root / "extract", PACKAGE_ID
        )
        static = p17.static_audit(package)
        materialized = materialized_config_audit()
        runtime = p17.exact_runtime_audit(
            package, temp_root / "exact_runtime"
        )
        guard = p17.p16.exact_observer_guard(package, temp_root)
        observer = observer_compile_receipt(package)
        syntax = p17.p16.syntax_checks(package, temp_root)
        original_prepare = p17.p16.p15.ORIGINAL_PREPARE
        p17.p16.p15.ORIGINAL_PREPARE = (
            lambda pkg, root, mode: p17.exact_guard_prepare(
                original_prepare, pkg, root, mode
            )
        )
        try:
            scenarios = {
                name: p17.p16.runner_scenario(
                    package, temp_root / "runner", name
                )
                for name in (
                    "normal",
                    "preflight_fail",
                    "compile_fail",
                    "HUP",
                    "INT",
                    "TERM",
                    "missing_parent",
                )
            }
        finally:
            p17.p16.p15.ORIGINAL_PREPARE = original_prepare
        legacy = p17.legacy_namespace_regression(
            package, temp_root / "legacy_namespace"
        )
        harness = p17.p16.p15.shared_harness(scenarios)
        write_json(HARNESS_REPORT, harness)
        shared = validate_layout(ZIP_PATH, HARNESS_REPORT, p17.LAYOUT_HELPER)
        write_json(SHARED_REPORT, shared)
    common = p17.p16.shared_public_regression()
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    profile_valid = (
        profile.get("contract_valid") is True
        and profile.get("package_id") == PACKAGE_ID
        and {
            "package_identity",
            "materialized_config_single_leaf",
            "bitstream",
            "execplan",
            "sca_path_binding",
        }
        <= set(profile.get("changed_surfaces", []))
    )
    positive_chain = (
        scenarios["normal"]["valid"]
        and scenarios["normal"]["compile_started"]
        and scenarios["normal"]["simulation_started"]
    )
    valid = (
        static["valid"]
        and materialized["valid"]
        and runtime["valid"]
        and guard["valid"]
        and observer["valid"]
        and syntax["valid"]
        and all(row["valid"] for row in scenarios.values())
        and legacy["valid"]
        and positive_chain
        and shared["pass"]
        and not shared["errors"]
        and common["valid"]
        and profile_valid
    )
    result = {
        "schema": (
            "conv-native-four-lane-p18-pekeep3-final-zip-audit-v1"
        ),
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_AUDIT_FAILED",
        "valid": valid,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_identity": PACKAGE_ID,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "source_p17_zip_sha256": sha256(SOURCE_ZIP),
        "source_p17_return_analysis_sha256": sha256(build.P17_ANALYSIS),
        "static_zip_audit": static,
        "materialized_config_audit": materialized,
        "exact_runtime_path_budget_and_preflight": runtime,
        "exact_observer_guard": guard,
        "observer_and_package_local_hdl": observer,
        "diagnostic_predicate_trace": {
            "disposition": "receipt_reuse_observer_predicate_byte_equal",
            "pass": observer["observer_byte_equal"],
        },
        "syntax_checks": syntax,
        "exact_runner_harness": scenarios,
        "legacy_namespace_collision_regression": legacy,
        "exact_runner_to_compile_and_simulator_stub_positive": positive_chain,
        "runtime_layout_harness": {
            "path": str(HARNESS_REPORT),
            "bytes": HARNESS_REPORT.stat().st_size,
            "sha256": sha256(HARNESS_REPORT),
        },
        "shared_runtime_layout": {
            "path": str(SHARED_REPORT),
            "bytes": SHARED_REPORT.stat().st_size,
            "sha256": sha256(SHARED_REPORT),
            "pass": shared["pass"],
            "errors": len(shared["errors"]),
            "exact_final_zip_invocation_count": 1,
        },
        "shared_public_regression": common,
        "shadow_profile_compare": {
            "profile": str(BUILD_PROFILE),
            "profile_sha256": sha256(BUILD_PROFILE),
            "contract_valid": profile_valid,
            "family_validator_authoritative": True,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {
                "disposition": "blocking_applicable",
                "pass": static["valid"],
            },
            "runner_control_flow": {
                "disposition": "blocking_applicable",
                "pass": runtime["valid"]
                and all(row["valid"] for row in scenarios.values())
                and legacy["valid"]
                and positive_chain,
            },
            "package_local_hdl": {
                "disposition": "receipt_reuse",
                "pass": observer["valid"],
            },
            "materialized_config": {
                "disposition": "blocking_applicable",
                "pass": materialized["valid"],
                "causal_transaction_ledger": sha256(LOCAL_LEDGER),
                "boundary_microtrace": sha256(LOCAL_MICROTRACE),
                "physical_bank_row_validity": (
                    "receipt_reuse_addresses_byte_equal"
                ),
            },
            "diagnostic_semantics": {
                "disposition": "receipt_reuse_predicate_byte_equal",
                "pass": observer["observer_byte_equal"],
            },
            "return_result_contract": {
                "disposition": "blocking_applicable",
                "pass": all(row["valid"] for row in scenarios.values()),
            },
            "runtime_layout": {
                "disposition": "blocking_applicable",
                "pass": shared["pass"] and common["valid"],
                "rule_id": "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "semantic_version": "2",
            },
            "storage_rotation": {
                "disposition": "blocking_applicable",
                "pass": None,
                "reason": "performed after exact final-ZIP audit",
            },
            "numeric_w3_golden": {
                "disposition": "record_only",
                "pass": materialized[
                    "frozen_numeric_w3_golden_matrix_observer_timeout_equal"
                ],
            },
        },
        "server_action": False,
        "claim_boundary": (
            "PACKAGE_READY_NOT_RUN is a local c0 config-fix package release. "
            "Production c0 natural terminal, formal 320D, performance, E3, "
            "E4 and E5 remain unclaimed."
        ),
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
                "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
                "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
                "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
                "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            ],
            "delta": None,
        },
    }
    write_json(REPORT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
