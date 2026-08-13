#!/usr/bin/env python3
"""Independent final-ZIP audit for the p7 cloud-nonblocking successor."""

from __future__ import annotations

import argparse
import importlib.util
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

from tools import build_conv_native_four_lane_0ccae916_p7_cloudnb_package as build
from tools import validate_conv_native_four_lane_e1fb0f7_c0_diag_package as base
from tools import node0004_assumed_hardware_server_runtime_v2 as numeric_base


INSTALL_NAME = build.INSTALL_NAME
PACKAGE_ROOT = build.OUTPUT_ROOT / INSTALL_NAME
PACKAGE_ZIP = build.OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
OUTPUT = build.OUTPUT_ROOT / f"{INSTALL_NAME}.final_zip_audit.json"
P6_FINAL_AUDIT = (
    build.OUTPUT_ROOT / f"{build.SOURCE_NAME}.final_zip_audit.json"
)
P6_FINAL_AUDIT_SHA256 = (
    "d961e4196abbe217c60ecc27f00af1e89be35156c3203318e7ebc0b13e581670"
)
RTL_REPO = ROOT / "Trassic2.0_RTL"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def git_blob(commit: str, path: str) -> bytes:
    safe = RTL_REPO.resolve().as_posix()
    result = base.run(
        [
            "git",
            "-c",
            f"safe.directory={safe}",
            "-C",
            str(RTL_REPO),
            "show",
            f"{commit}:{path}",
        ],
        ROOT,
        binary=True,
    )
    if result["exit_code"] != 0:
        raise RuntimeError(f"cannot read immutable Git blob: {path}")
    return result["stdout"]


def load_package_runtime(package: Path) -> Any:
    path = (
        package
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    package_tools = str(path.parent)
    if package_tools not in sys.path:
        sys.path.insert(0, package_tools)
    name = f"n4_p7_runtime_{base.digest(str(package).encode())[:12]}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load exact package runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configure_base_helpers(cloud_leaves: dict[str, str]) -> None:
    base.INSTALL_NAME = INSTALL_NAME
    base.PACKAGE_ROOT = PACKAGE_ROOT
    base.PACKAGE_ZIP = PACKAGE_ZIP
    base.OUTPUT = OUTPUT
    base.runtime.INSTALL_NAME = INSTALL_NAME
    base.runtime.EXPECTED_COMMIT = build.CLOUD_COMMIT
    base.runtime.EXPECTED_LEAVES = cloud_leaves
    tokens = tuple(
        token
        for token in base.SCOPE_TOKENS["Array_Request_Manager.sv"]
        if token != "buf2arm_valid_hold"
    )
    base.SCOPE_TOKENS["Array_Request_Manager.sv"] = tokens


def p6_relation(package: Path) -> dict[str, Any]:
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
    expected_changed = sorted(
        [
            "PREPARE_AND_RUN.sh",
            "README.md",
            "TEST_PACKAGE_MANIFEST.json",
            (
                "package_tools/"
                "node0004_assumed_hardware_server_runtime.py"
            ),
            "provenance/current_local_rtl_binding.json",
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        ]
    )
    identity_normalized = sorted(
        path
        for path in (
            "TEST_PACKAGE_MANIFEST.json",
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        )
        if source[path].replace(
            build.SOURCE_NAME.encode(), INSTALL_NAME.encode()
        )
        == target[path]
    )
    unchanged_workload = all(
        source[path] == target[path]
        for path in source
        if path.startswith("workload/")
        and path
        not in {
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        }
    )
    observer_equal = (
        source["tb_probe/native_return_observer.svh"]
        == target["tb_probe/native_return_observer.svh"]
    )
    return {
        "valid": (
            not (set(source) - set(target))
            and not (set(target) - set(source))
            and changed == expected_changed
            and identity_normalized
            == [
                "TEST_PACKAGE_MANIFEST.json",
                "workload/runtime/runs/c0/sca_cfg.json",
                "workload/runtime/runs/c0/sca_cfg_D.json",
            ]
            and unchanged_workload
            and observer_equal
            and source_manifest["files"]
            == {
                path: {
                    "size_bytes": len(payload),
                    "sha256": base.digest(payload),
                }
                for path, payload in source.items()
            }
        ),
        "source_file_count": len(source),
        "target_file_count": len(target),
        "missing": sorted(set(source) - set(target)),
        "extra": sorted(set(target) - set(source)),
        "changed": changed,
        "expected_changed": expected_changed,
        "identity_normalized": identity_normalized,
        "workload_config_bitstream_execplan_payload_byte_equal": (
            unchanged_workload
        ),
        "observer_byte_equal": observer_equal,
    }


def cloud_identity(
    cloud_audit: dict[str, Any],
) -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    for basename, relative in base.GIT_PATHS.items():
        payload = git_blob(build.CLOUD_COMMIT, relative)
        expected = cloud_audit["cloud_expected_compiled_leaves"][
            basename
        ]
        leaves[basename] = {
            "path": relative,
            "bytes": len(payload),
            "sha256": base.digest(payload),
            "expected_bytes": expected["bytes"],
            "expected_sha256": expected["sha256"],
            "match": (
                len(payload) == expected["bytes"]
                and base.digest(payload) == expected["sha256"]
            ),
            "changed_from_local_base": expected[
                "changed_from_local_base"
            ],
        }
    changed = sorted(
        name
        for name, value in leaves.items()
        if value["changed_from_local_base"]
    )
    return {
        "valid": all(value["match"] for value in leaves.values())
        and changed
        == [
            "Array_Request_Manager.sv",
            "Buffer_AG_Idx_Queue.sv",
            "RD_Data_Channel.sv",
        ],
        "repository": "xlsjdjdk/Trassic2.0_RTL",
        "branch": "master",
        "commit": build.CLOUD_COMMIT,
        "changed_compiled_leaves": changed,
        "leaves": leaves,
    }


def runtime_controls(
    package: Path,
    cloud_identity_receipt: dict[str, Any],
) -> dict[str, Any]:
    runtime = load_package_runtime(package)
    positive_preflight = runtime.preflight(package)
    with tempfile.TemporaryDirectory(prefix="n4-p7-runtime-") as name:
        root = Path(name)
        leaf_root = root / "cloud_leaves"
        leaf_root.mkdir()
        compile_lines: list[str] = []
        for basename, relative in base.GIT_PATHS.items():
            leaf = leaf_root / basename
            leaf.write_bytes(git_blob(build.CLOUD_COMMIT, relative))
            compile_lines.append(f"Parsing design file '{leaf}'")
        compile_log = root / "compile.log"
        compile_log.write_text(
            "\n".join(compile_lines) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        exact_cloud = runtime.collect_compile_identity(
            compile_log, root / "identity_cloud.json"
        )

        wrong_leaf = leaf_root / "Array_Request_Manager.sv"
        wrong_leaf.write_bytes(b"safe non-RTL identity mismatch fixture\n")
        arbitrary_actual = runtime.collect_compile_identity(
            compile_log, root / "identity_arbitrary.json"
        )

        incomplete_log = root / "compile_incomplete.log"
        incomplete_log.write_text(
            "\n".join(
                line
                for line in compile_lines
                if "RD_Data_Channel.sv" not in line
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        incomplete = runtime.collect_compile_identity(
            incomplete_log, root / "identity_incomplete.json"
        )

        removed = root / INSTALL_NAME
        shutil.copytree(package, removed)
        (
            removed
            / "workload/runtime/runs/c0/install/execplan_op_w0.txt"
        ).unlink()
        missing_member_failed = False
        try:
            runtime.preflight(removed)
        except runtime.RuntimeErrorContract:
            missing_member_failed = True

        long_root_failed = False
        try:
            runtime.path_budget(package, Path("C:/" + "x" * 241))
        except runtime.RuntimeErrorContract:
            long_root_failed = True

    exact_cloud_checks = {
        "collection_valid": exact_cloud.get("collection_valid") is True,
        "three_leaves_differ_local": sorted(
            name
            for name, value in exact_cloud["leaves"].items()
            if not value["matches_local_provenance"]
        )
        == cloud_identity_receipt["changed_compiled_leaves"],
        "all_leaves_match_cloud": all(
            value["matches_cloud_authority"]
            for value in exact_cloud["leaves"].values()
        ),
        "local_difference_nonblocking": (
            exact_cloud["actual_differs_local_provenance"] is True
            and exact_cloud["identity_difference_blocks_simulator"] is False
        ),
        "cloud_classification_exact": (
            exact_cloud["authority_classification"]
            == "ACTUAL_MATCHES_CURRENT_CLOUD"
        ),
    }
    arbitrary_checks = {
        "collection_still_valid": arbitrary_actual["collection_valid"] is True,
        "cloud_difference_recorded": (
            arbitrary_actual["actual_differs_cloud_authority"] is True
        ),
        "difference_nonblocking": (
            arbitrary_actual["identity_difference_blocks_simulator"] is False
        ),
    }
    incomplete_checks = {
        "collection_invalid": incomplete["collection_valid"] is False,
        "missing_leaf_recorded": any(
            "RD_Data_Channel.sv" in error
            for error in incomplete["collection_errors"]
        ),
        "collector_returns_receipt": (
            incomplete["identity_difference_blocks_simulator"] is False
        ),
    }
    checks = {
        "positive_preflight": positive_preflight["valid"] is True,
        "cloud_identity_receipt": all(exact_cloud_checks.values()),
        "arbitrary_identity_difference_is_nonblocking": all(
            arbitrary_checks.values()
        ),
        "incomplete_collection_returns_nonblocking_receipt": all(
            incomplete_checks.values()
        ),
        "missing_exact_member_fails_precompile": missing_member_failed,
        "overlong_server_root_fails": long_root_failed,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "exact_cloud_positive": {
            "checks": exact_cloud_checks,
            "receipt": exact_cloud,
        },
        "arbitrary_actual_positive": {
            "checks": arbitrary_checks,
            "receipt": arbitrary_actual,
        },
        "incomplete_collection": {
            "checks": incomplete_checks,
            "receipt": incomplete,
        },
        "claim_boundary": (
            "exact final runtime logic only; no production compile or DUT "
            "simulation"
        ),
    }


def p6_compile_reuse(
    cloud_identity_receipt: dict[str, Any],
) -> dict[str, Any]:
    report = json.loads(
        build.P6_RETURN_ANALYSIS.read_text(encoding="utf-8")
    )
    actual = report["actual_production_rtl_identity"]
    observed = {
        **actual["matched_leaves"],
        **actual["mismatched_leaves"],
    }
    matches_cloud = {
        name: (
            observed[name]["sha256"]
            == cloud_identity_receipt["leaves"][name]["sha256"]
            and observed[name]["size_bytes"]
            == cloud_identity_receipt["leaves"][name]["bytes"]
        )
        for name in cloud_identity_receipt["leaves"]
    }
    p6_audit = json.loads(P6_FINAL_AUDIT.read_text(encoding="utf-8"))
    return {
        "valid": (
            sha256(P6_FINAL_AUDIT) == P6_FINAL_AUDIT_SHA256
            and p6_audit.get("valid") is True
            and report["execution"]["compile_exit_status"] == 0
            and report["private_xmr_adjudication"]["vcs_xmre_count"] == 0
            and all(matches_cloud.values())
        ),
        "p6_final_audit_sha256": sha256(P6_FINAL_AUDIT),
        "p6_observer_sha256": report["execution"][
            "observer_precompile"
        ]["observed_sha256"],
        "production_compile_exit": report["execution"][
            "compile_exit_status"
        ],
        "production_vcs_xmre_count": report[
            "private_xmr_adjudication"
        ]["vcs_xmre_count"],
        "all_eight_actual_p6_leaves_match_0ccae916": all(
            matches_cloud.values()
        ),
        "leaf_matches": matches_cloud,
        "reuse_scope": (
            "byte-equal package observer compile compatibility only; p6 did "
            "not launch simulation and supplies no c0 dynamic result"
        ),
    }


def deterministic_replay(package: Path, package_zip: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="n4-p7-replay-") as name:
        replay = Path(name) / package_zip.name
        build.deterministic_zip(package, replay)
        replay_sha = sha256(replay)
        replay_bytes = replay.stat().st_size
    return {
        "valid": (
            replay_sha == sha256(package_zip)
            and replay_bytes == package_zip.stat().st_size
        ),
        "replay_sha256": replay_sha,
        "source_sha256": sha256(package_zip),
        "replay_bytes": replay_bytes,
        "source_bytes": package_zip.stat().st_size,
    }


def sha256(path: Path) -> str:
    return numeric_base.sha256(path)


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=PACKAGE_ROOT)
    parser.add_argument("--zip", type=Path, default=PACKAGE_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    package = args.package_root.resolve()
    package_zip = args.zip.resolve()

    cloud_audit = json.loads(build.CLOUD_AUDIT.read_text(encoding="utf-8"))
    cloud_leaves = {
        name: value["sha256"]
        for name, value in cloud_audit[
            "cloud_expected_compiled_leaves"
        ].items()
    }
    configure_base_helpers(cloud_leaves)

    zip_audit = base.safe_zip_records(package_zip, INSTALL_NAME)
    directory_records = numeric_base.package_records(
        package, exclude_manifest=False
    )
    with tempfile.TemporaryDirectory(prefix="n4-p7-final-") as name:
        extracted = Path(name)
        with zipfile.ZipFile(package_zip) as archive:
            archive.extractall(extracted)
        audited = extracted / INSTALL_NAME
        audited_records = numeric_base.package_records(
            audited, exclude_manifest=False
        )
        manifest = json.loads(
            (audited / "package_manifest.json").read_text(encoding="utf-8")
        )
        relation = p6_relation(audited)
        closure = base.consumer_closure(audited)
        runtime_gate = runtime_controls(audited, cloud_identity(cloud_audit))
        runner_static = base.runner_controls(audited)
        binding = base.observer_binding_and_feature_controls(audited)
        canonical = base.canonical_decision_controls(audited)
        allowlist = base.return_allowlist_controls(audited)
        runner_e2e = base.runner_end_to_end_controls(package_zip)

    cloud_identity_receipt = cloud_identity(cloud_audit)
    compile_reuse = p6_compile_reuse(cloud_identity_receipt)
    observer_hash = sha256(
        package / "tb_probe/native_return_observer.svh"
    )
    source_observer_hash = zip_audit["records"][
        "tb_probe/native_return_observer.svh"
    ]["sha256"]
    package_local_hdl = {
        "applicability": "receipt_reuse_byte_equal",
        "valid": (
            relation["observer_byte_equal"]
            and observer_hash == source_observer_hash
            and compile_reuse["valid"]
            and cloud_audit["checks"][
                "observer_public_surface_cloud_covered"
            ]
        ),
        "observer_sha256": observer_hash,
        "p6_production_compile_reuse": compile_reuse,
        "fresh_frontend_not_repeated": True,
        "reason": (
            "observer bytes/parser/canonical predicates are byte-equal to p6; "
            "p6 production VCS successfully compiled the same observer "
            "against all eight exact 0ccae916 leaf bytes"
        ),
    }
    materialized_config = {
        "applicability": "not_applicable_receipt_reuse",
        "valid": relation[
            "workload_config_bitstream_execplan_payload_byte_equal"
        ],
        "transaction_ledger": "not_repeated_byte_equal",
        "config_boundary_microtrace": "not_repeated_byte_equal",
        "numeric_w3_golden": "not_repeated",
        "consumer_closure": closure,
    }
    diagnostic_trace = {
        "applicability": "not_applicable_observer_semantics_byte_equal",
        "valid": relation["observer_byte_equal"],
        "predicate_trace": "not_repeated",
        "p6_observer_sha256": compile_reuse["p6_observer_sha256"],
        "p7_observer_sha256": observer_hash,
    }

    manifest_checks = {
        "ready_not_run": manifest.get("status") == "PACKAGE_READY_NOT_RUN",
        "diagnostic_only": (
            manifest.get("candidate_class")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        ),
        "candidate_release_false": manifest.get("candidate_release") is False,
        "c0_only_no_formal_d": (
            manifest.get("conv_run_ids") == ["c0"]
            and manifest.get("tail_run_ids") == []
            and manifest.get("formal_readback_count") == 0
            and manifest.get("readback_checks") == []
        ),
        "no_functional_rtl": (
            manifest.get("functional_rtl_modified") is False
            and manifest.get("functional_rtl_file_count") == 0
            and manifest.get("server_rtl_entries") == 0
        ),
        "source_p6_exact": (
            manifest.get("delivery_successor", {}).get("source_sha256")
            == build.SOURCE_ZIP_SHA256
        ),
        "p6_return_supersession_exact": (
            manifest.get("source_return_analysis", {}).get("sha256")
            == build.P6_RETURN_ANALYSIS_SHA256
            and manifest.get("source_return_analysis", {}).get(
                "superseded_by_current_rule"
            )
            is True
        ),
        "cloud_authority_exact_nonblocking": (
            manifest.get("cloud_rtl_authority", {}).get(
                "approved_commit"
            )
            == build.CLOUD_COMMIT
            and manifest.get("cloud_rtl_authority", {}).get("leaves")
            == cloud_leaves
            and manifest.get("cloud_rtl_authority", {}).get(
                "identity_difference_blocks_compile_or_simulation"
            )
            is False
        ),
        "local_identity_is_hint_only": (
            manifest.get("expected_production_rtl_identity", {}).get(
                "commit"
            )
            == build.LOCAL_COMMIT
            and manifest.get("expected_production_rtl_identity", {}).get(
                "role"
            )
            == "local_provenance_hint_only"
        ),
        "cloud_audit_exact": (
            manifest.get("cloud_causal_cone_audit", {}).get("sha256")
            == sha256(build.CLOUD_AUDIT)
            and cloud_audit.get("valid") is True
        ),
        "observer_exact": (
            manifest.get("observer_binding", {}).get("source_sha256")
            == observer_hash
            and manifest.get("observer_binding", {}).get(
                "source_relation_to_p6"
            )
            == "byte_equal"
        ),
        "rule_receipts_current": manifest.get("rule_receipts")
        == {
            relative: sha256(ROOT / relative)
            for relative in build.RULE_PATHS
        },
        "rule_confirmation_only": (
            manifest.get("rule_feedback", {}).get("type")
            == "RULE_CONFIRMATION"
            and manifest.get("rule_feedback", {}).get(
                "rule_delta_proposal"
            )
            == []
        ),
        "manifest_files_exact": manifest.get("files")
        == numeric_base.package_records(package),
        "path_budget_exact": (
            manifest.get("path_length_budget")
            == build.path_budget(package)
            and manifest["path_length_budget"][
                "max_projected_absolute_path_chars"
            ]
            <= manifest["path_length_budget"][
                "max_projected_absolute_path_limit_chars"
            ]
        ),
    }
    replay = deterministic_replay(package, package_zip)
    sidecar = Path(str(package_zip) + ".sha256")
    sidecar_expected = f"{sha256(package_zip)}  {package_zip.name}\n"

    core_valid = (
        zip_audit["valid"]
        and zip_audit["records"] == directory_records == audited_records
        and relation["valid"]
        and all(manifest_checks.values())
        and replay["valid"]
        and sidecar.is_file()
        and sidecar.read_text(encoding="ascii") == sidecar_expected
    )
    runner_valid = (
        runtime_gate["valid"]
        and runner_static["valid"]
        and runner_e2e["valid"]
        and runtime_gate["exact_cloud_positive"]["checks"][
            "three_leaves_differ_local"
        ]
        and runner_e2e["checks"]["natural_reaches_simulator"]
    )
    return_result_valid = (
        allowlist["valid"]
        and runner_e2e["checks"]["natural_finalizer_return_exact"]
        and runner_e2e["checks"]["natural_return_sidecar_exact"]
        and runner_e2e["checks"][
            "natural_return_has_all_finalizer_receipts"
        ]
    )
    release_gate_matrix = {
        "schema": (
            "conv-native-four-lane-p7-release-gate-impact-matrix-v1"
        ),
        "valid": all(
            (
                core_valid,
                runner_valid,
                return_result_valid,
                package_local_hdl["valid"],
                materialized_config["valid"],
                diagnostic_trace["valid"],
                cloud_identity_receipt["valid"],
            )
        ),
        "gates": {
            "core_package_bootstrap_path": {
                "applicability": "applicable",
                "blocking": True,
                "status": "PASS" if core_valid else "FAIL",
                "evidence": [
                    "safe final ZIP exact-set",
                    "manifest/current rule receipts",
                    "path budget",
                    "deterministic replay",
                    "sidecar",
                ],
            },
            "runner_compile_finalizer": {
                "applicability": "applicable_changed",
                "blocking": True,
                "status": "PASS" if runner_valid else "FAIL",
                "evidence": [
                    (
                        "safe compile stub uses exact 0ccae916 leaves; three "
                        "SHA differ from local e1fb0f7"
                    ),
                    "exact final runner still reaches simulator stub",
                    "signal finalizer and precompile negative",
                ],
            },
            "return_result_joint_gate": {
                "applicability": "applicable_changed",
                "blocking": True,
                "status": "PASS" if return_result_valid else "FAIL",
                "evidence": [
                    "natural local-stub return exact",
                    "identity receipt returned",
                    "no formal 320D claim",
                ],
            },
            "cloud_rtl_causal_cone": {
                "applicability": "applicable_changed",
                "blocking": True,
                "status": (
                    "PASS" if cloud_identity_receipt["valid"] else "FAIL"
                ),
                "evidence": [
                    "0ccae916 exact 12-commit/11-file diff",
                    "three directly changed compiled observer owners",
                    "targeted predicate/queue boundary trace",
                ],
            },
            "package_local_hdl": {
                "applicability": "receipt_reuse_byte_equal",
                "blocking": True,
                "status": (
                    "PASS" if package_local_hdl["valid"] else "FAIL"
                ),
                "evidence": [
                    "byte-equal p6 public observer",
                    "p6 production VCS compile against exact 0ccae916 leaves",
                ],
            },
            "materialized_config": {
                "applicability": "not_applicable_receipt_reuse",
                "blocking": False,
                "status": (
                    "RECEIPT_REUSE"
                    if materialized_config["valid"]
                    else "FAIL"
                ),
                "evidence": [
                    "byte-equal workload/config/bitstream/execplan",
                    "identity-only SCA normalization",
                ],
            },
            "diagnostic_predicate_trace": {
                "applicability": (
                    "not_applicable_observer_parser_canonical_byte_equal"
                ),
                "blocking": False,
                "status": (
                    "RECEIPT_REUSE"
                    if diagnostic_trace["valid"]
                    else "FAIL"
                ),
                "evidence": ["p6 observer/canonical semantics byte-equal"],
            },
            "numeric_w3_golden": {
                "applicability": "record_only_byte_equal",
                "blocking": False,
                "status": "NOT_REPEATED",
                "evidence": [
                    "p6/p7 workload payload relation",
                    "no numeric, W3, golden or local E2 rerun",
                ],
            },
        },
    }
    checks = {
        "core_package_bootstrap_path": core_valid,
        "p6_content_relation": relation["valid"],
        "cloud_causal_cone": cloud_audit["valid"],
        "cloud_identity_exact": cloud_identity_receipt["valid"],
        "package_local_hdl_receipt_reuse": package_local_hdl["valid"],
        "materialized_config_receipt_reuse": materialized_config["valid"],
        "diagnostic_semantics_receipt_reuse": diagnostic_trace["valid"],
        "runtime_cloud_identity_nonblocking_controls": runtime_gate["valid"],
        "runner_static_controls": runner_static["valid"],
        "observer_binding_feature_controls": binding["valid"],
        "canonical_decision_controls": canonical["valid"],
        "return_allowlist_controls": allowlist["valid"],
        "runner_actual_local_sha_diff_reaches_simulator_stub": runner_valid,
        "return_result_joint_gate": return_result_valid,
        "release_gate_matrix": release_gate_matrix["valid"],
    }
    errors = [name for name, value in checks.items() if not value]
    result = {
        "schema": "conv-native-four-lane-0ccae916-p7-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "FAIL",
        "valid": not errors,
        "errors": errors,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package": str(package),
        "zip": str(package_zip),
        "zip_bytes": package_zip.stat().st_size,
        "zip_sha256": sha256(package_zip),
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        "checks": checks,
        "manifest_checks": manifest_checks,
        "release_gate_matrix": release_gate_matrix,
        "source_p6_relation": relation,
        "cloud_causal_cone_audit": {
            "path": str(build.CLOUD_AUDIT),
            "sha256": sha256(build.CLOUD_AUDIT),
            "status": cloud_audit["status"],
            "checks": cloud_audit["checks"],
        },
        "cloud_identity": cloud_identity_receipt,
        "package_local_hdl": package_local_hdl,
        "materialized_config": materialized_config,
        "diagnostic_predicate_trace": diagnostic_trace,
        "runtime_controls": runtime_gate,
        "runner_static_controls": runner_static,
        "runner_end_to_end_controls": runner_e2e,
        "observer_binding_and_feature_controls": binding,
        "canonical_decision_controls": canonical,
        "return_allowlist_controls": allowlist,
        "zip_audit": {
            key: value for key, value in zip_audit.items()
            if key != "records"
        },
        "reproducibility": replay,
        "final_zip_rule_self_audit": {
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "current_server_package_rule_sha256": sha256(
                ROOT / ".agents/rules/服务器测试包生成规则.md"
            ),
            "current_config_rule_sha256": sha256(
                ROOT / ".agents/rules/算子配置规则.md"
            ),
            "current_plan_mutable_provenance_sha256": sha256(
                ROOT / ".agents/plan.md"
            ),
            "independent_validator": str(Path(__file__).resolve()),
            "independent_validator_sha256": sha256(Path(__file__)),
        },
        "claim_boundary": {
            "server_action": False,
            "production_vcs_or_dut_simulation": False,
            "formal_320d_in_package": False,
            "E3_E4_E5_claimed": False,
            "purpose": (
                "launch one fresh c0 production simulation despite expected "
                "actual/local/cloud identity differences after compile"
            ),
        },
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "rule_delta_proposal": [],
        },
    }
    write_json(args.output.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
