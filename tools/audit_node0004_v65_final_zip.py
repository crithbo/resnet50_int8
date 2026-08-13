from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v65_branchcatch_diag"
SOURCE = "r5_n4_hw_v64_dskew_diag"
SOURCE_SHA = "8d4bce53f152e829973212a0cf8403c59a86c588a62ef9f11ab5e90937dd2268"
RULE_PATHS = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "int8_sa": ROOT / ".agents/rules/INT8_SA点积专项规则.md",
    "hardware_readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def members(archive: zipfile.ZipFile) -> dict[str, bytes]:
    return {
        "/".join(info.filename.split("/")[1:]): archive.read(info)
        for info in archive.infolist()
        if not info.is_dir()
    }


def normalize_identity(value: bytes) -> bytes:
    return value.replace(PACKAGE.encode(), SOURCE.encode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v64", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--family-report", required=True, type=Path)
    parser.add_argument("--shared-report", required=True, type=Path)
    parser.add_argument("--observer-report", required=True, type=Path)
    parser.add_argument("--runner-report", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    checks: dict[str, bool] = {}
    zip_sha = sha_file(args.zip)
    checks["source_identity"] = sha_file(args.source_v64) == SOURCE_SHA
    checks["sidecar_identity"] = (
        args.sidecar.read_text(encoding="ascii").split()
        == [zip_sha, args.zip.name]
    )
    with zipfile.ZipFile(args.zip) as target_archive, zipfile.ZipFile(
        args.source_v64
    ) as source_archive:
        infos = target_archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = target_archive.testzip() is None
        checks["single_root"] = {
            name.split("/", 1)[0] for name in names
        } == {PACKAGE}
        checks["no_duplicates"] = len(names) == len(set(names))
        checks["safe_paths"] = all(
            not PurePosixPath(item.filename).is_absolute()
            and ".." not in PurePosixPath(item.filename).parts
            and "\\" not in item.filename
            for item in infos
        )
        checks["no_symlinks"] = all(
            not stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF)
            for item in infos
        )
        target = members(target_archive)
        source = members(source_archive)
        manifest = json.loads(target["package_manifest.json"])
        actual = {
            name: sha_bytes(value)
            for name, value in target.items()
            if name != "package_manifest.json"
        }
        checks["manifest_exact_set"] = set(manifest["files"]) == set(actual)
        checks["manifest_receipts"] = manifest["files"] == actual
        checks["manifest_identity"] = (
            manifest["install_name"] == PACKAGE
            and manifest["source_package_sha256"] == SOURCE_SHA
            and manifest["classification"]
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest["candidate_release"] is False
            and manifest["configuration_rebuilt"] is False
            and manifest["node0004_workload_rebuilt"] is False
            and manifest["numeric_analysis_repeated"] is False
            and manifest["functional_rtl_modified"] is False
            and manifest["server_action"] is False
        )
        feature = manifest["diagnostic_features"]["RETURN_OBS_BRANCH_CATCHUP"]
        checks["feature_contract"] = (
            feature["runtime_enable_parameter"] == "+RETURN_OBS_BRANCH_CATCHUP"
            and feature["limit_parameter"]
            == "+RETURN_OBS_BRANCH_CATCHUP_LIMIT=64"
            and feature["edge_schema"] == "BRANCH_CATCHUP_V1"
            and feature["boundary_schema"] == "BRANCH_CATCHUP_V1"
        )
        contract = json.loads(target["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])
        checks["install_only_v2"] = (
            contract["package_id"] == PACKAGE
            and contract["install_name"] == PACKAGE
            and contract["required_preexisting_parents"] == ["install"]
            and contract["fixed_result_root"] == "/home/panqs/ndp/simresult"
        )
        runner = target["PREPARE_AND_RUN.sh"].decode("utf-8")
        runtime = target[
            "package_tools/node0004_hang_localization_runtime.py"
        ].decode("utf-8")
        checks["repeatable_return_and_collector_abi"] = (
            'return_tag="r$(date -u +%s%N)_$$"' in runner
            and "--return-zip \"$return_zip\"" in runner
            and "return_zip: Path," in runtime
            and "_base_collect(\n        server_root, ndp_root, "
            "install_name, evidence_root, run_root, return_zip\n"
            in runtime
        )
        checks["feature_actual_argv"] = (
            runner.count(
                " +RETURN_OBS_BRANCH_CATCHUP "
                "+RETURN_OBS_BRANCH_CATCHUP_LIMIT=64"
            )
            == 2
        )
        frozen = [
            name
            for name in target
            if (
                name.startswith("workload/")
                or "golden" in name.lower()
                or name.endswith(".bin")
            )
            and name in source
        ]
        checks["frozen_payload"] = bool(frozen) and all(
            normalize_identity(target[name]) == source[name]
            for name in frozen
        )
        checks["fresh_provenance"] = (
            "provenance/v64_to_v65_branch_catchup.json" in target
        )

    reports = {
        "build": load(args.build_report).get("deterministic_rebuild_equal")
        is True,
        "family": load(args.family_report).get("valid") is True,
        "shared": load(args.shared_report).get("pass") is True,
        "observer": load(args.observer_report).get("valid") is True,
        "runner": load(args.runner_report).get("valid") is True,
        "return": load(args.return_report).get("valid") is True,
    }
    checks.update({f"{name}_report": value for name, value in reports.items()})
    current_rules = {name: sha_file(path) for name, path in RULE_PATHS.items()}
    receipts = manifest["active_receipts"]
    checks["current_rule_receipts"] = (
        receipts["agent_sha256"] == current_rules["agent"]
        and receipts["generation_index_sha256"] == current_rules["index"]
        and receipts["server_package_rule_sha256"] == current_rules["server"]
        and receipts["common_operator_rule_sha256"]
        == current_rules["common_config"]
        and receipts["ndp_hardware_field_rule_sha256"]
        == current_rules["ndp_fields"]
        and receipts["int8_sa_rule_sha256"] == current_rules["int8_sa"]
        and receipts["hardware_readme_sha256"]
        == current_rules["hardware_readme"]
    )
    errors = [key for key, value in checks.items() if not value]
    release_gate_matrix = [
        {
            "gate_id": gate,
            "applicability": applicability,
            "status": "PASS" if checks[check] else "FAIL",
            "blocking": blocking,
        }
        for gate, applicability, check, blocking in (
            (
                "package_bootstrap_path_runtime_d",
                "blocking_applicable",
                "family_report",
                True,
            ),
            (
                "runtime_layout_and_sca_open",
                "blocking_applicable",
                "shared_report",
                True,
            ),
            (
                "materialized_config",
                "receipt_reuse",
                "frozen_payload",
                False,
            ),
            (
                "changed_observer_actual_consumer",
                "blocking_applicable",
                "observer_report",
                True,
            ),
            (
                "repeatable_return_collector",
                "blocking_applicable",
                "repeatable_return_and_collector_abi",
                True,
            ),
            (
                "runner_error_visibility",
                "blocking_applicable",
                "runner_report",
                True,
            ),
            (
                "return_result_conjunction",
                "blocking_applicable",
                "return_report",
                True,
            ),
        )
    ]
    report = {
        "schema": "node0004-v65-final-zip-audit-v1",
        "package_id": PACKAGE,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": zip_sha,
        },
        "source_v64": {
            "path": str(args.source_v64.resolve()),
            "bytes": args.source_v64.stat().st_size,
            "sha256": SOURCE_SHA,
        },
        "rule_receipts_post_generation": current_rules,
        "release_gate_matrix": release_gate_matrix,
        "claim_boundary": (
            "Local exact package/runner/install layout, changed branch-catchup "
            "observer and return collector only. No server natural terminal, "
            "formal 320D, E4, or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"pass": not errors, "errors": errors, "sha": zip_sha}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
