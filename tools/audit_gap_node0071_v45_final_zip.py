from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_gap_v47_stage_transition_rootfix"
EXPECTED_RULES = {
    "agent": (
        ".agents/agent.md",
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ),
    "index": (
        ".agents/rules/生成前必读索引.md",
        "37f75653e2c5c167a6fb5d178785b9d3f3a3262b78cddf19d34663418c179e88",
    ),
    "server": (
        ".agents/rules/服务器测试包生成规则.md",
        "755672c11626accf38160ddd5e2959cdf8949c0b4483f1243ff6b3a3bdb0ad8c",
    ),
    "config": (
        ".agents/rules/算子配置规则.md",
        "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
    ),
    "ndp": (
        ".agents/rules/NDP硬件字段语义.md",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ),
    "gap_mac": (
        ".agents/rules/GAP_int32_mac_bypass_rules.md",
        "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b",
    ),
    "gap_probe": (
        ".agents/rules/GAP_probe_v7_validator_rules.md",
        "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1",
    ),
    "tail": (
        ".agents/rules/精确UINT8量化尾专项规则.md",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ),
}
EXPECTED_RULES.update(
    {
        "index": (
            ".agents/rules/生成前必读索引.md",
            "1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500",
        ),
        "server": (
            ".agents/rules/服务器测试包生成规则.md",
            "b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724",
        ),
        "config": (
            ".agents/rules/算子配置规则.md",
            "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
        ),
        "ndp": (
            ".agents/rules/NDP硬件字段语义.md",
            "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
        ),
        "tail": (
            ".agents/rules/精确UINT8量化尾专项规则.md",
            "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
        ),
    }
)
REQUIRED_RULE_IDS = {
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
    "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
    "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
    "CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001",
}


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_path(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def run(argv: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    return {
        "argv": argv,
        "exit_code": completed.returncode,
        "stdout_sha256": sha_bytes(completed.stdout.encode()),
        "stderr_sha256": sha_bytes(completed.stderr.encode()),
        "stderr_empty": completed.stderr == "",
    }


def read_final_zip(
    target: Path,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValueError("CRC failure")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or len(pure.parts) < 2
                or pure.parts[0] != NAME
            ):
                raise ValueError(f"unsafe member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in seen:
                raise ValueError(f"duplicate: {relative}")
            seen.add(relative)
            files[relative] = archive.read(info)
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    return files, manifest


def feature_contract(text: str, manifest: dict[str, Any]) -> dict[str, bool]:
    checks = {
        "plusarg_enable": "+RETURN_OBS_STAGE_TRANSITION" in text,
        "plusarg_heartbeat":
            "+RETURN_OBS_STAGE_HEARTBEAT_CYCLES=1048576" in text,
        "time0_binding":
            "stage_transition_enabled=true" in text
            and "stage_transition_records_returned=true" in text,
        "record_binding":
            "GEXEC_STAGE_TRANSITION_STATE_V1" in text,
        "self_test_before_compile":
            'stage_tool" self-test' in text,
        "parser_in_finalizer":
            'stage_tool" analyze' in text,
        "decision_allowlisted": any(
            item["target_path"]
            == "evidence/stage_transition_decision.json"
            and item["required"] is True
            for item in manifest["return_allowlist"]
        ),
        "self_test_allowlisted": any(
            item["target_path"]
            == "evidence/stage_transition_predicate_self_test.json"
            and item["required"] is True
            for item in manifest["return_allowlist"]
        ),
    }
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--hdl-report", type=Path, required=True)
    parser.add_argument("--runner-report", type=Path, required=True)
    parser.add_argument("--predicate-trace", type=Path, required=True)
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--bash", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    try:
        target = args.target_zip.resolve()
        sidecar = args.sidecar.resolve()
        target_sha = sha_path(target)
        sidecar_text = sidecar.read_text(encoding="ascii")
        files, manifest = read_final_zip(target)
        observed = {
            path: {
                "size_bytes": len(payload),
                "sha256": sha_bytes(payload),
            }
            for path, payload in files.items()
            if path != "TEST_PACKAGE_MANIFEST.json"
        }
        declared = manifest["files"]
        runner = files["PREPARE_AND_RUN.sh"].decode("utf-8")
        current_receipts = {
            key: sha_path(ROOT / relative)
            for key, (relative, _) in EXPECTED_RULES.items()
        }
        expected_receipts = {
            key: expected for key, (_, expected) in EXPECTED_RULES.items()
        }
        hdl = json.loads(args.hdl_report.read_text(encoding="utf-8"))
        runner_report = json.loads(
            args.runner_report.read_text(encoding="utf-8")
        )
        predicate = json.loads(
            args.predicate_trace.read_text(encoding="utf-8")
        )
        build = json.loads(
            args.build_report.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory(
            prefix=".gap-v46-final-audit-", dir=ROOT
        ) as raw:
            extract_root = Path(raw)
            with zipfile.ZipFile(target) as archive:
                archive.extractall(extract_root)
            package = extract_root / NAME
            runtime_d_absent = all(
                not (
                    package / record["runtime_path"]
                ).exists()
                and not (
                    package / "workload" / record["runtime_path"]
                ).exists()
                for record in manifest["readback_checks"]
            )
            bash_syntax = run(
                [
                    str(args.bash),
                    "-n",
                    str(package / "PREPARE_AND_RUN.sh"),
                ],
                package,
            )
            python_members = sorted(
                path for path in package.rglob("*.py") if path.is_file()
            )
            ast_receipts = {}
            for path in python_members:
                ast.parse(path.read_text(encoding="utf-8"))
                ast_receipts[path.relative_to(package).as_posix()] = {
                    "sha256": sha_path(path),
                    "ast_parse": True,
                }
            runtime_preflight = run(
                [
                    str(args.python),
                    str(
                        package
                        / "package_tools/"
                        "gap_node0071_complete_server_runtime.py"
                    ),
                    "preflight",
                    "--package-root",
                    str(package),
                ],
                package,
            )
            observer_guard = run(
                [
                    str(args.python),
                    str(
                        package
                        / "package_tools/"
                        "gap_node0071_package_observer_guard.py"
                    ),
                    "--package-root",
                    str(package),
                    "--manifest",
                    str(package / "TEST_PACKAGE_MANIFEST.json"),
                    "--runner",
                    str(package / "PREPARE_AND_RUN.sh"),
                ],
                package,
            )
            canonical_selftest = run(
                [
                    str(args.python),
                    str(
                        package
                        / "package_tools/"
                        "gap_node0071_canonical_decision.py"
                    ),
                    "self-test",
                ],
                package,
            )
            stage_selftest = run(
                [
                    str(args.python),
                    str(
                        package
                        / "package_tools/"
                        "gap_node0071_stage_transition_decision.py"
                    ),
                    "self-test",
                ],
                package,
            )
        feature_positive = feature_contract(runner, manifest)
        feature_negatives = []
        for name, mutated in (
            (
                "feature_enable_removed",
                runner.replace(
                    "+RETURN_OBS_STAGE_TRANSITION",
                    "+RETURN_OBS_STAGE_DISABLED",
                ),
            ),
            (
                "heartbeat_removed",
                runner.replace(
                    "+RETURN_OBS_STAGE_HEARTBEAT_CYCLES=1048576",
                    "+RETURN_OBS_STAGE_HEARTBEAT_DISABLED=1048576",
                ),
            ),
            (
                "time0_binding_removed",
                runner.replace(
                    "stage_transition_enabled=true",
                    "stage_transition_enabled=UNKNOWN",
                    1,
                ),
            ),
            (
                "parser_call_removed",
                runner.replace(
                    'python3 "$stage_tool" analyze',
                    'python3 "$stage_tool" disabled',
                    1,
                ),
            ),
        ):
            changed = feature_contract(mutated, manifest)
            feature_negatives.append(
                {
                    "name": name,
                    "failed_closed": not all(changed.values()),
                    "failed_checks": [
                        key for key, value in changed.items() if not value
                    ],
                }
            )
        max_suffix = max(len(path) for path in files)
        path_budget = manifest["path_length_budget"]
        release_matrix = manifest["release_gate_matrix"]
        checks = {
            "zip_crc_root_path_duplicate_symlink_safe": True,
            "sidecar_exact":
                sidecar_text == f"{target_sha}  {target.name}\n",
            "manifest_identity":
                manifest["install_name"] == NAME
                and manifest["package_name"] == NAME
                and manifest["return_name"] == f"{NAME}_return",
            "manifest_exact_set": observed == declared,
            "rule_receipts_current":
                current_receipts == expected_receipts
                and manifest["rule_receipts"] == expected_receipts,
            "required_rule_ids":
                REQUIRED_RULE_IDS
                <= set(manifest["applicable_rule_ids"]),
            "release_gate_matrix_single":
                release_matrix.get("single_matrix") is True
                and all(
                    key in release_matrix
                    for key in (
                        "package_bootstrap_path_runtime_D",
                        "runner_compile_finalizer",
                        "package_local_hdl",
                        "materialized_config",
                        "diagnostic_semantics",
                        "return_result_conjunction",
                    )
                ),
            "frozen_config_receipt_reuse":
                build["unchanged_nonidentity_nonrunner_members_equal"]
                is True
                and release_matrix["materialized_config"]["blocking"]
                is False,
            "frozen_numeric_receipt_reuse":
                build["unchanged_nonidentity_nonrunner_members_equal"]
                is True,
            "deterministic_double_build":
                build["deterministic_double_build_equal"] is True,
            "runtime_D_absent": runtime_d_absent,
            "path_budget":
                max_suffix
                <= path_budget["max_inner_suffix_chars"],
            "bash_syntax": bash_syntax["exit_code"] == 0,
            "python_ast": all(
                item["ast_parse"] for item in ast_receipts.values()
            ),
            "runtime_preflight": runtime_preflight["exit_code"] == 0,
            "observer_guard": observer_guard["exit_code"] == 0,
            "canonical_selftest":
                canonical_selftest["exit_code"] == 0,
            "stage_predicate_trace":
                stage_selftest["exit_code"] == 0
                and predicate["pass"] is True,
            "feature_contract": all(feature_positive.values()),
            "feature_negatives_fail_closed": all(
                item["failed_closed"] for item in feature_negatives
            ),
            "hdl_scope": hdl["pass"] is True,
            "fixed_result_runner": runner_report["pass"] is True,
            "ndp_root_toplevel_gate":
                runner_report["checks"].get(
                    "all_root_toplevel_negatives_fail_closed"
                )
                is True
                and all(
                    item.get("ndp_root_toplevel_unchanged") is True
                    for item in runner_report["execution_modes"].values()
                )
                and 'existing_parent="$server_root/install"' in runner
                and 'workspace_root="$existing_parent/' in runner
                and any(
                    item["target_path"]
                    == "evidence/ndp_root_toplevel_exact_set.json"
                    and item["required"] is True
                    for item in manifest["return_allowlist"]
                ),
            "fixed_server_path_not_local":
                not Path("/home/panqs/ndp/simresult").exists(),
            "package_class_boundary":
                manifest["package_class"]
                == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
                and manifest["candidate_release"] is False
                and manifest["evidence_ceiling"] == "E2_LOCAL_ONLY",
        }
        errors.extend(key for key, value in checks.items() if not value)
        passed = not errors
        result = {
            "schema": "gap-node0071-v47-final-zip-self-audit-v1",
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
            "status": "PASS" if passed else "FAIL",
            "errors": errors,
            "error_count": len(errors),
            "target_zip": str(target),
            "target_zip_size_bytes": target.stat().st_size,
            "target_zip_sha256": target_sha,
            "sidecar": str(sidecar),
            "sidecar_size_bytes": sidecar.stat().st_size,
            "sidecar_sha256": sha_path(sidecar),
            "checks": checks,
            "rule_receipts": {
                "current": current_receipts,
                "expected": expected_receipts,
                "manifest": manifest["rule_receipts"],
            },
            "release_gate_matrix": release_matrix,
            "feature_positive": feature_positive,
            "feature_negative_controls": feature_negatives,
            "commands": {
                "bash_syntax": bash_syntax,
                "runtime_preflight": runtime_preflight,
                "observer_guard": observer_guard,
                "canonical_selftest": canonical_selftest,
                "stage_selftest": stage_selftest,
            },
            "python_ast_receipts": ast_receipts,
            "hdl_report": {
                "path": str(args.hdl_report),
                "sha256": sha_path(args.hdl_report),
            },
            "runner_report": {
                "path": str(args.runner_report),
                "sha256": sha_path(args.runner_report),
            },
            "predicate_trace": {
                "path": str(args.predicate_trace),
                "sha256": sha_path(args.predicate_trace),
            },
            "build_report": {
                "path": str(args.build_report),
                "sha256": sha_path(args.build_report),
            },
            "max_inner_suffix_chars": max_suffix,
            "runtime_D_absent": runtime_d_absent,
            "local_fixed_server_result_root_created": False,
            "production_return_zip":
                f"/home/panqs/ndp/simresult/{NAME}_return.zip",
            "production_return_sidecar":
                f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256",
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {
            "schema": "gap-node0071-v47-final-zip-self-audit-v1",
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": False,
            "status": "FAIL",
            "errors": [str(error)],
            "error_count": 1,
        }
        exit_code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "pass": result["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
                "errors": result["errors"],
                "target_zip_sha256": result.get("target_zip_sha256"),
            },
            ensure_ascii=False,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
