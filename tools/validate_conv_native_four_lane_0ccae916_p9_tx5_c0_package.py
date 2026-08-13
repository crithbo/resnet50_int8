#!/usr/bin/env python3
"""Independent final-ZIP audit for the p9 transout-threshold c0 package."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_conv_native_four_lane_0ccae916_p9_tx5_c0_package as build  # noqa: E402
import tools.validate_conv_native_four_lane_0ccae916_p7_cloudnb_package as p7v  # noqa: E402


INSTALL_NAME = build.INSTALL_NAME
PACKAGE_ROOT = build.OUTPUT_ROOT / INSTALL_NAME
PACKAGE_ZIP = build.OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT = build.OUTPUT_ROOT / f"{INSTALL_NAME}.final_zip_audit.json"
P7_FINAL_AUDIT = (
    build.OUTPUT_ROOT / f"{build.SOURCE_NAME}.final_zip_audit.json"
)
P7_RETURN_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p7_return_analysis/report.json"
)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def relation(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(build.SOURCE_ZIP) as archive:
        source_manifest = json.loads(
            archive.read(f"{build.SOURCE_NAME}/package_manifest.json")
        )
        source = {
            info.filename[len(build.SOURCE_NAME) + 1 :]: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
            and info.filename
            != f"{build.SOURCE_NAME}/package_manifest.json"
        }
    target = {
        path.relative_to(package).as_posix(): path.read_bytes()
        for path in package.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    }
    changed = sorted(
        path
        for path in set(source) & set(target)
        if source[path] != target[path]
    )
    expected = sorted(
        [
            "PREPARE_AND_RUN.sh",
            "README.md",
            "TEST_PACKAGE_MANIFEST.json",
            "package_tools/node0004_assumed_hardware_server_runtime.py",
            (
                "workload/runtime/runs/c0/install/cfg_pkg/"
                "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
            ),
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        ]
    )
    observer = "tb_probe/native_return_observer.svh"
    execplan = "workload/runtime/runs/c0/install/execplan.txt"
    matrix_paths = [path for path in source if "matrix_" in path]
    source_records_exact = source_manifest["files"] == {
        path: {
            "size_bytes": len(payload),
            "sha256": p7v.base.digest(payload),
        }
        for path, payload in source.items()
    }
    result = {
        "missing": sorted(set(source) - set(target)),
        "extra": sorted(set(target) - set(source)),
        "changed": changed,
        "expected_changed": expected,
        "observer_byte_equal": source[observer] == target[observer],
        "execplan_byte_equal": source[execplan] == target[execplan],
        "matrix_payloads_byte_equal": all(
            source[path] == target[path] for path in matrix_paths
        ),
        "source_manifest_records_exact": source_records_exact,
    }
    result["valid"] = (
        not result["missing"]
        and not result["extra"]
        and changed == expected
        and result["observer_byte_equal"]
        and result["execplan_byte_equal"]
        and result["matrix_payloads_byte_equal"]
        and source_records_exact
    )
    return result


def materialized_config(package: Path, closure: dict[str, Any]) -> dict[str, Any]:
    report = json.loads(build.LOCAL_REPORT.read_text(encoding="utf-8"))
    ledger = json.loads(
        (build.LOCAL_ROOT / "causal_transaction_ledger.json").read_text(
            encoding="utf-8"
        )
    )
    trace = json.loads(
        (build.LOCAL_ROOT / "boundary_microtrace.json").read_text(
            encoding="utf-8"
        )
    )
    bitstream = (
        package
        / "workload/runtime/runs/c0/install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    old_bitstream = (
        build.OUTPUT_ROOT
        / f"{build.SOURCE_NAME}/workload/runtime/runs/c0/install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    left = old_bitstream.read_bytes()
    right = bitstream.read_bytes()
    offsets = [
        index
        for index, pair in enumerate(zip(left, right))
        if pair[0] != pair[1]
    ]
    checks = {
        "local_rebuild_pass": (
            report.get("status") == "LOCAL_C0_PHYSICAL_REBUILD_PASS"
        ),
        "single_logical_leaf": (
            report.get("authorized_leaf_changes")
            == [
                {
                    "path": "special_array.transout_last_index",
                    "old": 2,
                    "new": 5,
                }
            ]
        ),
        "exact_bitstream_consumer": (
            build.sha256(bitstream)
            == report["bitstream"]["sha256"]
        ),
        "only_three_bitstream_offsets": (
            len(left) == len(right)
            and offsets == [4459, 4460, 4461]
        ),
        "execplan_consumer_exact": (
            build.sha256(
                package
                / "workload/runtime/runs/c0/install/execplan.txt"
            )
            == report["execplan"]["sha256"]
        ),
        "causal_ledger_pass": (
            ledger.get("status") == "PASS"
            and ledger.get("address_surface_changed") is False
            and ledger["consumer_required_set"]["required_release_count"]
            == 256
        ),
        "boundary_microtrace_pass": (
            trace.get("status") == "PASS"
            and trace["negative_threshold2"] == {
                "released": 0,
                "ignored": 256,
            }
            and trace["threshold5"] == {
                "released": 256,
                "ignored": 0,
            }
        ),
        "physical_address_receipt_reuse": (
            report.get("addresses_changed") is False
        ),
        "consumer_closure": closure.get("valid") is True,
    }
    return {
        "applicability": "blocking_applicable_changed_config",
        "valid": all(checks.values()),
        "checks": checks,
        "bitstream_changed_offsets": offsets,
        "causal_transaction_ledger": ledger,
        "boundary_microtrace": trace,
        "consumer_closure": closure,
        "numeric_w3_golden_repeated": False,
    }


def package_local_hdl(package: Path, relation_receipt: dict[str, Any]) -> dict[str, Any]:
    p7_audit = json.loads(P7_FINAL_AUDIT.read_text(encoding="utf-8"))
    p7_return = json.loads(P7_RETURN_ANALYSIS.read_text(encoding="utf-8"))
    observer = package / "tb_probe/native_return_observer.svh"
    observer_sha = build.sha256(observer)
    expected = p7_return["execution"]["observer_precompile"]["observed_sha256"]
    checks = {
        "p7_final_audit_valid": p7_audit.get("valid") is True,
        "p7_production_compile_zero": (
            p7_return["execution"]["compile_exit_status"] == 0
        ),
        "observer_byte_equal": relation_receipt["observer_byte_equal"],
        "observer_sha_matches_production_receipt": observer_sha == expected,
        "public_surface_no_private_xmr": (
            p7_audit["package_local_hdl"]["valid"] is True
        ),
    }
    return {
        "applicability": "receipt_reuse_byte_equal",
        "valid": all(checks.values()),
        "checks": checks,
        "observer_sha256": observer_sha,
        "production_receipt_scope": (
            "same observer bytes compiled in p7; no fresh HDL surface"
        ),
    }


def deterministic_replay(package: Path, package_zip: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="n4-p9-replay-") as name:
        replay = Path(name) / package_zip.name
        build.deterministic_zip(package, replay)
        result = {
            "source_sha256": build.sha256(package_zip),
            "replay_sha256": build.sha256(replay),
            "source_bytes": package_zip.stat().st_size,
            "replay_bytes": replay.stat().st_size,
        }
    result["valid"] = (
        result["source_sha256"] == result["replay_sha256"]
        and result["source_bytes"] == result["replay_bytes"]
    )
    return result


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--zip", type=Path, default=PACKAGE_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    package = args.package_root.resolve()
    package_zip = args.zip.resolve()

    cloud_audit = json.loads(p7v.build.CLOUD_AUDIT.read_text(encoding="utf-8"))
    cloud_leaves = {
        name: value["sha256"]
        for name, value in cloud_audit[
            "cloud_expected_compiled_leaves"
        ].items()
    }
    p7v.INSTALL_NAME = INSTALL_NAME
    p7v.PACKAGE_ROOT = package
    p7v.PACKAGE_ZIP = package_zip
    p7v.OUTPUT = args.output.resolve()
    p7v.configure_base_helpers(cloud_leaves)

    zip_audit = p7v.base.safe_zip_records(package_zip, INSTALL_NAME)
    directory_records = p7v.numeric_base.package_records(
        package, exclude_manifest=False
    )
    cloud_identity_receipt = p7v.cloud_identity(cloud_audit)
    with tempfile.TemporaryDirectory(prefix="n4-p9-final-") as name:
        extracted = Path(name)
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(extracted)
        audited = extracted / INSTALL_NAME
        audited_records = p7v.numeric_base.package_records(
            audited, exclude_manifest=False
        )
        manifest = json.loads(
            (audited / "package_manifest.json").read_text(encoding="utf-8")
        )
        relation_receipt = relation(audited)
        closure = p7v.base.consumer_closure(audited)
        runtime_gate = p7v.runtime_controls(
            audited, cloud_identity_receipt
        )
        runner_static = p7v.base.runner_controls(audited)
        binding = p7v.base.observer_binding_and_feature_controls(audited)
        canonical = p7v.base.canonical_decision_controls(audited)
        allowlist = p7v.base.return_allowlist_controls(audited)
        runner_e2e = p7v.base.runner_end_to_end_controls(package_zip)
        config_gate = materialized_config(audited, closure)
        hdl_gate = package_local_hdl(audited, relation_receipt)

    manifest_checks = {
        "ready_not_run": manifest.get("status") == "PACKAGE_READY_NOT_RUN",
        "config_functional_fix": (
            manifest.get("candidate_class")
            == "CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS"
        ),
        "candidate_release_false": manifest.get("candidate_release") is False,
        "c0_only_no_formal_d": (
            manifest.get("conv_run_ids") == ["c0"]
            and manifest.get("tail_run_ids") == []
            and manifest.get("formal_readback_count") == 0
            and manifest.get("readback_checks") == []
        ),
        "timeout_exact": (
            manifest["progress_diagnostics"]["run_timeout_seconds"]
            == build.RUN_TIMEOUT_SECONDS
        ),
        "single_config_change": (
            manifest["configuration_fix"]["logical_leaf_changes"]
            == [
                {
                    "path": "special_array.transout_last_index",
                    "old": 2,
                    "new": 5,
                }
            ]
        ),
        "p8f_analysis_bound": (
            manifest["source_p8f_return_analysis"]["sha256"]
            == build.sha256(build.P8F_ANALYSIS)
        ),
        "cloud_identity_nonblocking": (
            manifest["cloud_rtl_authority"][
                "identity_difference_blocks_compile_or_simulation"
            ]
            is False
        ),
        "no_functional_rtl": (
            manifest.get("functional_rtl_modified") is False
            and manifest.get("functional_rtl_file_count") == 0
            and manifest.get("server_rtl_entries") == 0
        ),
        "rule_receipts_current": manifest.get("rule_receipts")
        == {
            relative: build.sha256(ROOT / relative)
            for relative in build.RULE_PATHS
        },
        "manifest_files_exact": manifest.get("files")
        == p7v.numeric_base.package_records(package),
        "path_budget_exact": (
            manifest.get("path_length_budget")
            == build.path_budget(package)
        ),
        "release_matrix_single": (
            isinstance(manifest.get("release_gate_matrix"), dict)
            and manifest["release_gate_matrix"]["materialized_config"][
                "applicability"
            ]
            == "blocking_applicable"
        ),
        "rule_confirmation_only": (
            manifest.get("rule_feedback", {}).get("type")
            == "RULE_CONFIRMATION"
            and manifest.get("rule_feedback", {}).get(
                "rule_delta_proposal"
            )
            == []
        ),
    }
    runner_text = (package / "PREPARE_AND_RUN.sh").read_text(
        encoding="utf-8"
    )
    runner_timeout_exact = (
        runner_text.count(
            'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv"'
        )
        == 1
        and "kill-after=30s 1h" not in runner_text
    )
    runner_static_changed_timeout = (
        all(
            value
            for name, value in runner_static["checks"].items()
            if name != "one_hour_run_timeout"
        )
        and runner_static["checks"]["one_hour_run_timeout"] is False
        and runner_timeout_exact
    )
    replay = deterministic_replay(package, package_zip)
    sidecar = Path(str(package_zip) + ".sha256")
    sidecar_expected = (
        f"{build.sha256(package_zip)}  {package_zip.name}\n"
    )

    core_valid = (
        zip_audit["valid"]
        and zip_audit["records"] == directory_records == audited_records
        and relation_receipt["valid"]
        and all(manifest_checks.values())
        and replay["valid"]
        and sidecar.is_file()
        and sidecar.read_text(encoding="ascii") == sidecar_expected
    )
    runner_valid = (
        runtime_gate["valid"]
        and runner_static_changed_timeout
        and runner_e2e["valid"]
        and runner_e2e["checks"]["natural_reaches_simulator"]
        and runner_timeout_exact
    )
    return_valid = (
        allowlist["valid"]
        and runner_e2e["checks"]["natural_finalizer_return_exact"]
        and runner_e2e["checks"]["natural_return_sidecar_exact"]
        and runner_e2e["checks"][
            "natural_return_has_all_finalizer_receipts"
        ]
    )
    diagnostic_receipt_reuse = (
        relation_receipt["observer_byte_equal"]
        and binding["valid"]
        and canonical["valid"]
    )
    matrix = {
        "schema": "conv-native-four-lane-p9-release-gate-matrix-v1",
        "gates": {
            "core_package_bootstrap_path": {
                "applicability": "blocking_applicable",
                "status": "PASS" if core_valid else "FAIL",
            },
            "runner_compile_finalizer": {
                "applicability": "blocking_applicable_changed_timeout",
                "status": "PASS" if runner_valid else "FAIL",
            },
            "return_result_joint_gate": {
                "applicability": "blocking_applicable",
                "status": "PASS" if return_valid else "FAIL",
            },
            "package_local_hdl": {
                "applicability": "receipt_reuse_byte_equal",
                "status": "PASS" if hdl_gate["valid"] else "FAIL",
            },
            "materialized_config": {
                "applicability": "blocking_applicable_changed_config",
                "status": "PASS" if config_gate["valid"] else "FAIL",
            },
            "diagnostic_predicate_trace": {
                "applicability": "receipt_reuse_byte_equal",
                "status": (
                    "PASS" if diagnostic_receipt_reuse else "FAIL"
                ),
            },
            "numeric_w3_golden": {
                "applicability": "record_only_byte_equal",
                "status": "NOT_REPEATED",
            },
        },
    }
    matrix["valid"] = all(
        gate["status"] in {"PASS", "NOT_REPEATED"}
        for gate in matrix["gates"].values()
    )
    checks = {
        "core_package_bootstrap_path": core_valid,
        "source_p7_relation": relation_receipt["valid"],
        "cloud_identity_exact_nonblocking": (
            cloud_identity_receipt["valid"] and runtime_gate["valid"]
        ),
        "runner_compile_finalizer": runner_valid,
        "return_result_joint_gate": return_valid,
        "package_local_hdl_receipt_reuse": hdl_gate["valid"],
        "materialized_config_changed_slice": config_gate["valid"],
        "diagnostic_semantics_receipt_reuse": diagnostic_receipt_reuse,
        "observer_binding_feature_controls": binding["valid"],
        "canonical_decision_controls": canonical["valid"],
        "release_gate_matrix": matrix["valid"],
    }
    errors = [name for name, value in checks.items() if not value]
    result = {
        "schema": "conv-native-four-lane-0ccae916-p9-tx5-final-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "FAIL",
        "valid": not errors,
        "errors": errors,
        "candidate_class": (
            "CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS"
        ),
        "candidate_release": False,
        "package": str(package),
        "zip": str(package_zip),
        "zip_bytes": package_zip.stat().st_size,
        "zip_sha256": build.sha256(package_zip),
        "sidecar": str(sidecar),
        "sidecar_sha256": build.sha256(sidecar),
        "checks": checks,
        "manifest_checks": manifest_checks,
        "release_gate_matrix": matrix,
        "source_p7_relation": relation_receipt,
        "cloud_identity": cloud_identity_receipt,
        "runtime_controls": runtime_gate,
        "runner_static_controls": runner_static,
        "runner_static_changed_timeout_valid": (
            runner_static_changed_timeout
        ),
        "runner_end_to_end_controls": runner_e2e,
        "return_allowlist_controls": allowlist,
        "package_local_hdl": hdl_gate,
        "materialized_config": config_gate,
        "observer_binding_and_feature_controls": binding,
        "canonical_decision_controls": canonical,
        "reproducibility": replay,
        "claim_boundary": {
            "server_action": False,
            "production_compile_or_dut_simulation": False,
            "formal_320d_in_package": False,
            "E3_E4_E5_claimed": False,
            "performance_claimed": False,
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "rule_delta_proposal": [],
        },
        "final_zip_rule_self_audit": {
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "current_server_package_rule_sha256": build.sha256(
                ROOT / ".agents/rules/服务器测试包生成规则.md"
            ),
            "current_config_rule_sha256": build.sha256(
                ROOT / ".agents/rules/算子配置规则.md"
            ),
            "current_plan_mutable_provenance_sha256": build.sha256(
                ROOT / ".agents/plan.md"
            ),
            "independent_validator": str(Path(__file__).resolve()),
            "independent_validator_sha256": build.sha256(Path(__file__)),
        },
    }
    write_json(args.output.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
