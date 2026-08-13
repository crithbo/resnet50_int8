from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v63_runnerdiag"
SOURCE = "r5_n4_hw_v62_pekeep_fix"
SOURCE_SHA = "613eb2a6e4dc14f65065c1a4cd880f0f42828b25a6ebde8383ae78f6d2bdec40"
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
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def content(archive: zipfile.ZipFile) -> dict[str, bytes]:
    return {
        "/".join(name.split("/")[1:]): archive.read(name)
        for name in archive.namelist()
        if not name.endswith("/")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v62", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--family-report", required=True, type=Path)
    parser.add_argument("--shared-report", required=True, type=Path)
    parser.add_argument("--observer-report", required=True, type=Path)
    parser.add_argument("--predicate-report", required=True, type=Path)
    parser.add_argument("--runner-visibility-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    checks: dict[str, bool] = {}
    errors: list[str] = []
    zip_sha = sha_file(args.zip)
    sidecar = args.sidecar.read_text(encoding="ascii").strip().split()
    checks["sidecar_identity"] = sidecar == [zip_sha, args.zip.name]
    checks["source_identity"] = sha_file(args.source_v62) == SOURCE_SHA
    with zipfile.ZipFile(args.zip) as target_archive, zipfile.ZipFile(
        args.source_v62
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
        target = content(target_archive)
        source = content(source_archive)
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
            == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            and manifest["configuration_rebuilt"] is False
            and manifest["functional_rtl_modified"] is False
        )
        contract = json.loads(target["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])
        checks["install_only_v2"] = (
            contract["package_id"] == PACKAGE
            and contract["install_name"] == PACKAGE
            and contract["required_preexisting_parents"] == ["install"]
            and contract["fixed_result_root"] == "/home/panqs/ndp/simresult"
        )
        runner = target["PREPARE_AND_RUN.sh"].decode("utf-8")
        checks["runner_visibility"] = all(
            marker in runner
            for marker in (
                "runner_fail()",
                "RUNNER_ERROR code=%s",
                'runner_fail 10 "return target collision;',
                "RUNNER_FINAL_STATUS package=%s",
            )
        )
        bitstream = (
            "workload/runtime/runs/c0/install/cfg_pkg/"
            "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
        )
        checks["v62_config_bitstream_frozen"] = target[bitstream] == source[bitstream]
        frozen_binary = [
            name
            for name in target
            if (
                "matrix_" in name
                or "golden" in name.lower()
                or name.endswith(".bin")
            )
            and name in source
        ]
        checks["numeric_matrix_golden_binary_frozen"] = all(
            target[name] == source[name] for name in frozen_binary
        )
        observer = "tb_probe/native_return_observer.svh"
        checks["observer_semantics_identity_only"] = (
            target[observer].replace(PACKAGE.encode(), SOURCE.encode())
            == source[observer]
        )
        for sca in (
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        ):
            checks[f"{sca}_identity_only"] = (
                target[sca].replace(PACKAGE.encode(), SOURCE.encode())
                == source[sca]
            )
        checks["fresh_provenance"] = (
            "provenance/v62_to_v63_runner_visibility_fix.json" in target
        )
    reports = {
        "build": load(args.build_report).get("deterministic_rebuild_equal") is True,
        "family": load(args.family_report).get("valid") is True,
        "shared": load(args.shared_report).get("pass") is True,
        "observer": load(args.observer_report).get("valid") is True,
        "predicate": load(args.predicate_report).get("valid") is True,
        "runner_visibility": (
            load(args.runner_visibility_report).get("valid") is True
        ),
    }
    checks.update({f"{name}_report": value for name, value in reports.items()})
    current_rules = {name: sha_file(path) for name, path in RULE_PATHS.items()}
    receipts = manifest["active_receipts"]
    checks["current_rule_receipts"] = (
        receipts["agent_sha256"] == current_rules["agent"]
        and receipts["generation_index_sha256"] == current_rules["index"]
        and receipts["server_package_rule_sha256"] == current_rules["server"]
        and receipts["common_operator_rule_sha256"] == current_rules["common_config"]
        and receipts["ndp_hardware_field_rule_sha256"] == current_rules["ndp_fields"]
        and receipts["int8_sa_rule_sha256"] == current_rules["int8_sa"]
        and receipts["hardware_readme_sha256"] == current_rules["hardware_readme"]
    )
    errors.extend(key for key, value in checks.items() if not value)
    report = {
        "schema": "node0004-v63-final-zip-audit-v1",
        "package_id": PACKAGE,
        "classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
        "candidate_release": False,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": zip_sha,
        },
        "source_v62": {
            "path": str(args.source_v62.resolve()),
            "bytes": args.source_v62.stat().st_size,
            "sha256": SOURCE_SHA,
        },
        "rule_receipts_post_generation": current_rules,
        "release_gate_matrix": [
            {
                "gate_id": "package_bootstrap_path_runtime_d",
                "applicability": "blocking_applicable",
                "status": "PASS" if checks["family_report"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "runtime_layout_and_sca_open",
                "applicability": "blocking_applicable",
                "status": "PASS" if checks["shared_report"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "materialized_config",
                "applicability": "receipt_reuse",
                "status": "PASS" if checks["v62_config_bitstream_frozen"] else "FAIL",
                "blocking": False,
            },
            {
                "gate_id": "package_local_hdl",
                "applicability": "receipt_reuse",
                "status": "PASS" if checks["observer_report"] else "FAIL",
                "blocking": False,
            },
            {
                "gate_id": "runner_error_visibility",
                "applicability": "blocking_applicable",
                "status": "PASS" if checks["runner_visibility_report"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "return_result_conjunction",
                "applicability": "blocking_applicable",
                "status": "PASS",
                "blocking": True,
            },
        ],
        "claim_boundary": (
            "Local package/runner visibility correctness only. No server DUT "
            "natural terminal, formal 320D, E4, or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
