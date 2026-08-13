from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n4_hw_v46_lc9_split_cloudrtl"
VERSION = 46
SOURCE_NAME = "r5_n4_hw_v43_wrterm2_compilefix"
ZIP_SHA256 = "b80bdae2da23a9c85e433430b0740ab34a0cf1957ea86ceef3aa68edf193bcc2"
SOURCE_SHA256 = "ba3c2df775c8f7f7bef47eec15d079651eb7c60e20145aca7dedef7345fe54e2"
RETURN_SHA256 = "5ed315d6121dba0a7e2bc81b9672ab8604c66a5b32b280b647dbc2e5af6b4e11"
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
CURRENT = {
    "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    "index": "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    "server": "61753f6866f49aca142545394451cd73c4e634a5aa160b066e020b7c9067cedd",
    "common": "d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0",
    "ndp": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    "readme": "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}
RULE_PATHS = {
    "agent": ".agents/agent.md",
    "plan_mutable": ".agents/plan.md",
    "index": ".agents/rules/生成前必读索引.md",
    "server": ".agents/rules/服务器测试包生成规则.md",
    "common": ".agents/rules/算子配置规则.md",
    "ndp": ".agents/rules/NDP硬件字段语义.md",
    "int8_sa": ".agents/rules/INT8_SA点积专项规则.md",
    "readme": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}
REQUIRED_RULES = {
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
    "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    entries: dict[str, bytes] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failure: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                errors.append(f"unsafe/duplicate path: {info.filename}")
                continue
            seen.add(info.filename)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                errors.append(f"symlink member: {info.filename}")
            if not pure.parts or pure.parts[0] != root:
                errors.append(f"wrong root: {info.filename}")
                continue
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            entries[relative] = archive.read(info)
    return entries, errors


def normalized(data: bytes, identity: str) -> bytes:
    return data.replace(identity.encode(), b"<PACKAGE_IDENTITY>")


def feature_contract(
    prepare: str,
    runtime: str,
    observer: str,
    feature: dict[str, Any],
) -> bool:
    enable = feature["runtime_enable_parameter"]
    limit = feature["limit_or_budget_parameters"][0]
    marker = feature["time_zero_marker"]
    target = feature["returned_record_target"]
    feature_name = feature["feature"]
    limit_name, limit_value = limit.removeprefix("+").split("=", 1)
    schema = feature["expected_record_schema"].removesuffix("_BOUNDARY_V1")
    source_marker = (
        "DIAGNOSTIC_FEATURE_ENABLE_V1 | "
        f"feature={feature_name} enabled=%0d "
        f"limit_name={limit_name} limit=%0d schema={schema}"
    )
    expected_runtime_marker = (
        "DIAGNOSTIC_FEATURE_ENABLE_V1 "
        f"feature={feature_name} enabled=1 "
        f"limit_name={limit_name} limit={limit_value} schema={schema}"
    )
    prepare_tokens = prepare.replace("\\\n", " ").replace('"', "").split()
    return (
        prepare_tokens.count(enable) >= 2
        and prepare_tokens.count(limit) >= 2
        and enable in runtime
        and limit in runtime
        and marker == expected_runtime_marker
        and source_marker in observer
        and "LC9_SPLIT_BOUNDARY_V1" in observer
        and target == "runs/c0/return_observer.log"
    )


def feature_source_marker(feature: dict[str, Any]) -> str:
    limit = feature["limit_or_budget_parameters"][0]
    limit_name = limit.removeprefix("+").split("=", 1)[0]
    schema = feature["expected_record_schema"].removesuffix("_BOUNDARY_V1")
    return (
        "DIAGNOSTIC_FEATURE_ENABLE_V1 | "
        f"feature={feature['feature']} enabled=%0d "
        f"limit_name={limit_name} limit=%0d schema={schema}"
    )


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v43", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--cloud-causal-cone", required=True, type=Path)
    parser.add_argument("--observer-syntax", required=True, type=Path)
    parser.add_argument("--predicate-trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    entries, zip_errors = read_zip(zip_path, INSTALL_NAME)
    source, source_errors = read_zip(args.source_v43.resolve(), SOURCE_NAME)
    errors = zip_errors + source_errors
    digest = sha256_file(zip_path)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    files = manifest.get("files", {})
    paths = set(entries) - {"package_manifest.json"}
    prepare = entries.get("PREPARE_AND_RUN.sh", b"").decode(errors="replace")
    runtime = entries.get(
        "package_tools/node0004_hang_localization_runtime.py", b""
    ).decode(errors="replace")
    observer = entries.get(
        "tb_probe/native_return_observer.svh", b""
    ).decode(errors="replace")

    reports = {
        "return": load(args.return_report),
        "build": load(args.build_report),
        "runner": load(args.runner_controls),
        "cloud": load(args.cloud_causal_cone),
        "syntax": load(args.observer_syntax),
        "trace": load(args.predicate_trace),
    }
    current_receipts = {
        name: sha256_file(ROOT / path) for name, path in RULE_PATHS.items()
    }
    rules = set(manifest.get("active_receipts", {}).get("rules", []))
    matrix = manifest.get("release_gate_matrix", [])
    matrix_ids = [row.get("gate_id") for row in matrix]
    required_matrix = {
        "PACKAGE_BOOTSTRAP_PATH_RUNTIME_D",
        "RUNNER_TO_COMPILE_AND_FINALIZER",
        "ACTUALLY_REFERENCED_PACKAGE_LOCAL_HDL",
        "CHANGED_MATERIALIZED_CONFIG_CONSUMER_CONTRACT",
        "CHANGED_OBSERVER_OR_CANONICAL_SEMANTICS",
        "RETURN_RESULT_JOINT_GATE",
        "FROZEN_NUMERIC_W3_GOLDEN",
        "UNRELATED_FUNCTIONAL_RTL",
        "REPORT_STYLE_OR_SYNONYMOUS_NEGATIVES",
    }

    runtime_paths = {
        path for path in entries if path.startswith("workload/runtime/")
    }
    source_runtime_paths = {
        path for path in source if path.startswith("workload/runtime/")
    }
    runtime_equal = runtime_paths == source_runtime_paths and all(
        normalized(entries[path], INSTALL_NAME)
        == normalized(source[path], SOURCE_NAME)
        for path in runtime_paths
    )
    common_paths = set(entries) & set(source)
    semantic_changed = sorted(
        path
        for path in common_paths
        if normalized(entries[path], INSTALL_NAME)
        != normalized(source[path], SOURCE_NAME)
    )
    allowed_changed = {
        "README.md",
        "package_manifest.json",
        "PREPARE_AND_RUN.sh",
        "package_tools/node0004_hang_localization_runtime.py",
        "tb_probe/native_return_observer.svh",
    }
    added = sorted(set(entries) - set(source))
    removed = sorted(set(source) - set(entries))

    feature = next(
        item
        for item in manifest["diagnostic_feature_runtime_binding"]["features"]
        if item.get("feature") == "RETURN_OBS_LC9_SPLIT"
    )
    feature_positive = feature_contract(prepare, runtime, observer, feature)
    feature_negatives = {
        "delete_enable_fail_closed": not feature_contract(
            prepare.replace(
                feature["runtime_enable_parameter"] + " ", "", 2
            ),
            runtime,
            observer,
            feature,
        ),
        "delete_limit_fail_closed": not feature_contract(
            prepare.replace(feature["limit_or_budget_parameters"][0], "", 2),
            runtime,
            observer,
            feature,
        ),
        "delete_time0_marker_fail_closed": not feature_contract(
            prepare,
            runtime,
            observer.replace(feature_source_marker(feature), "", 1),
            feature,
        ),
        "wrong_return_target_fail_closed": not feature_contract(
            prepare,
            runtime,
            observer,
            {**feature, "returned_record_target": "runs/c0/wrong.log"},
        ),
    }

    manifest_receipts = manifest.get("active_receipts", {})
    cloud = manifest.get("cloud_rtl_authority", {})
    checks = {
        "zip_sha": digest == ZIP_SHA256,
        "sidecar_exact": args.sidecar.read_text(encoding="ascii")
        == f"{digest}  {zip_path.name}\n",
        "source_v43_sha": sha256_file(args.source_v43) == SOURCE_SHA256,
        "zip_crc_root_path_duplicate_symlink": not errors,
        "manifest_exact_set": set(files) == paths,
        "manifest_per_file_hashes": all(
            path in entries and sha256(entries[path]) == value
            for path, value in files.items()
        ),
        "manifest_identity": manifest.get("install_name") == INSTALL_NAME,
        "diagnostic_classification": (
            manifest.get("candidate_release") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("functional_rtl_modified") is False
        ),
        "return_report_bound": (
            reports["return"].get("valid") is True
            and reports["return"].get("RETURN_ANALYSIS", {})
            .get("return_zip", {})
            .get("sha256")
            == RETURN_SHA256
        ),
        "v43_compile_crossed_xmre": (
            reports["return"].get("RETURN_ANALYSIS", {})
            .get("checks", {})
            .get("production_vcs_compile_crossed_v41_xmre")
            is True
        ),
        "build_deterministic": (
            reports["build"].get("zip_sha256") == digest
            and reports["build"].get("deterministic_rebuild_equal") is True
        ),
        "reports_valid": all(
            reports[name].get("valid") is True
            for name in ("runner", "cloud", "syntax", "trace")
        ),
        "current_rule_receipts": all(
            current_receipts[name] == value for name, value in CURRENT.items()
        ),
        "manifest_current_server_rule": (
            manifest_receipts.get("server_package_rule_sha256")
            == CURRENT["server"]
        ),
        "manifest_current_common_rule": (
            manifest_receipts.get("common_operator_rule_sha256")
            == CURRENT["common"]
        ),
        "required_rule_ids": REQUIRED_RULES <= rules,
        "release_gate_matrix_single_complete": (
            len(matrix) == 9
            and len(set(matrix_ids)) == 9
            and set(matrix_ids) == required_matrix
            and all(
                {
                    "gate_id",
                    "applicable",
                    "reason",
                    "changed_surface",
                    "evidence",
                    "blocking",
                }
                <= set(row)
                for row in matrix
            )
        ),
        "release_gate_matrix_no_stale_v44_label": (
            "v44 span" not in json.dumps(matrix)
        ),
        "cloud_authority_exact_nonblocking": (
            cloud.get("approved_commit") == CLOUD_COMMIT
            and cloud.get("identity_difference_blocks_compile_or_simulation")
            is False
            and reports["cloud"].get("valid") is True
        ),
        "actual_consumer_uncovered_zero": (
            reports["cloud"]
            .get("serialized_conv_causal_cone", {})
            .get("observer_uncovered")
            == 0
        ),
        "feature_binding_positive": feature_positive,
        "feature_binding_negatives": all(feature_negatives.values()),
        "observer_syntax_positive_and_negatives": (
            reports["syntax"].get("valid") is True
        ),
        "predicate_trace_positive_and_negatives": (
            reports["trace"].get("valid") is True
        ),
        "runner_safe_compile_exit_term_controls": (
            reports["runner"].get("valid") is True
            and reports["runner"].get("exit_control", {}).get(
                "runner_exit_code"
            )
            == 74
            and reports["runner"].get("term_control", {}).get(
                "runner_exit_code"
            )
            == 143
        ),
        "frozen_runtime_payload_byte_equal": runtime_equal,
        "semantic_changes_exact": set(semantic_changed) == allowed_changed,
        "no_source_file_removed": not removed,
        "only_expected_provenance_added": (
            added == [f"provenance/v43_return_v{VERSION}_lc9_split.json"]
        ),
        "config_rules_receipt_reuse": (
            manifest.get("materialized_config_rule_applicability", {}).get(
                "causal_transaction_ledger"
            )
            == "RECEIPT_REUSE_BYTE_EQUAL"
            and manifest.get("materialized_config_rule_applicability", {}).get(
                "boundary_microtrace"
            )
            == "NOT_APPLICABLE_NO_CHANGED_CONFIG_PREDICATE"
        ),
        "internal_path_budget": max(len(path) for path in entries) <= 240,
        "no_nested_identity_repetition": all(
            path.count(INSTALL_NAME) <= 1 for path in entries
        ),
        "old_occupancy_not_reopened": (
            manifest.get("v43_return_adjudication", {}).get(
                "old_outbuffer_occupancy"
            )
            == "INVALIDATED_NOT_RTL_BUG"
        ),
    }
    final_valid = all(checks.values())
    report: dict[str, Any] = {
        "schema": (
            f"node0004-v{VERSION}-final-zip-current-rule-audit-v1"
        ),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": final_valid,
        "valid": final_valid,
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "source_v43_sha256": SOURCE_SHA256,
        "bound_return_sha256": RETURN_SHA256,
        "current_rule_receipts": current_receipts,
        "plan_mutable_provenance": {
            "builder_receipt": manifest_receipts.get(
                "plan_mutable_provenance_sha256"
            ),
            "current": current_receipts["plan_mutable"],
            "blocking": False,
        },
        "release_gate_matrix": matrix,
        "feature_negative_controls": feature_negatives,
        "semantic_changed_files": semantic_changed,
        "added_files": added,
        "removed_files": removed,
        "report_receipts": {
            name: {
                "path": str(path),
                "sha256": sha256_file(path),
                "valid": reports[name].get("valid", True),
            }
            for name, path in {
                "return": args.return_report,
                "build": args.build_report,
                "runner": args.runner_controls,
                "cloud": args.cloud_causal_cone,
                "syntax": args.observer_syntax,
                "trace": args.predicate_trace,
            }.items()
        },
        "package_release": (
            "PACKAGE_READY_NOT_RUN" if final_valid else "QUARANTINED"
        ),
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if final_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
