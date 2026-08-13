from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
SOURCE_NAME = "r5_n4_hw_v50_dterm_owner_diag"
SOURCE_SHA = "c8a809f8ebb723c286b5c0190bcd1142f9ba2d8965731b8ee194182c0922c830"
RETURN_SHA = "5401413f1586e8b7de4ad6ed2be2f8b2a0b4eea5072a80349b5b3217601e9d8a"
CURRENT = {
    "agent": (
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
        ".agents/agent.md",
    ),
    "plan": (
        "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70",
        ".agents/plan.md",
    ),
    "index": (
        "37f75653e2c5c167a6fb5d178785b9d3f3a3262b78cddf19d34663418c179e88",
        ".agents/rules/生成前必读索引.md",
    ),
    "server": (
        "755672c11626accf38160ddd5e2959cdf8949c0b4483f1243ff6b3a3bdb0ad8c",
        ".agents/rules/服务器测试包生成规则.md",
    ),
    "common": (
        "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
        ".agents/rules/算子配置规则.md",
    ),
    "ndp": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
        ".agents/rules/NDP硬件字段语义.md",
    ),
    "int8_sa": (
        "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
        ".agents/rules/INT8_SA点积专项规则.md",
    ),
    "readme": (
        "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    ),
}
RULES = {
    "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
    "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], list[str]]:
    result: dict[str, bytes] = {}
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"crc:{bad}")
        roots: set[str] = set()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                info.filename in seen
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
            ):
                errors.append(f"unsafe:{info.filename}")
            seen.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            if stat.S_ISLNK(info.external_attr >> 16):
                errors.append(f"symlink:{info.filename}")
            if not info.is_dir() and len(pure.parts) > 1:
                relative = PurePosixPath(*pure.parts[1:]).as_posix()
                if relative in result:
                    errors.append(f"duplicate:{relative}")
                result[relative] = archive.read(info)
        if roots != {root}:
            errors.append(f"root:{sorted(roots)}")
    return result, errors


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(data: bytes) -> bytes:
    for name in (INSTALL_NAME, SOURCE_NAME):
        data = data.replace(name.encode(), b"<IDENTITY>")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--source-v50", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--runner-controls", required=True, type=Path)
    parser.add_argument("--fixed-publish", required=True, type=Path)
    parser.add_argument("--observer-syntax", required=True, type=Path)
    parser.add_argument("--actual-consumer", required=True, type=Path)
    parser.add_argument("--predicate-trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    entries, zip_errors = read_zip(args.zip.resolve(), INSTALL_NAME)
    source, source_errors = read_zip(
        args.source_v50.resolve(), SOURCE_NAME
    )
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    reports = {
        "return": load(args.return_report),
        "build": load(args.build_report),
        "runner": load(args.runner_controls),
        "publish": load(args.fixed_publish),
        "syntax": load(args.observer_syntax),
        "scope": load(args.actual_consumer),
        "trace": load(args.predicate_trace),
    }
    digest = file_sha(args.zip)
    files = manifest.get("files", {})
    paths = set(entries) - {"package_manifest.json"}
    receipts = manifest.get("active_receipts", {})
    current = {
        name: file_sha(ROOT / path)
        for name, (_, path) in CURRENT.items()
    }
    common = set(entries) & set(source)
    changed = sorted(
        path
        for path in common
        if normalize(entries[path]) != normalize(source[path])
    )
    added = sorted(set(entries) - set(source))
    removed = sorted(set(source) - set(entries))
    matrix = manifest.get("release_gate_matrix", [])
    return_analysis = reports["return"].get("RETURN_ANALYSIS", {})
    observer = entries.get("tb_probe/native_return_observer.svh", b"")
    fixed = manifest.get("fixed_server_result_publication", {})
    expected_return_abs = (
        f"/home/panqs/ndp/simresult/{INSTALL_NAME}_return.zip"
    )
    checks = {
        "zip_sha": digest == args.expected_zip_sha256,
        "sidecar_exact": (
            args.sidecar.read_text(encoding="ascii")
            == f"{digest}  {args.zip.name}\n"
        ),
        "source_sha": file_sha(args.source_v50) == SOURCE_SHA,
        "zip_safety": not (zip_errors + source_errors),
        "manifest_identity": manifest.get("install_name") == INSTALL_NAME,
        "manifest_exact_set": set(files) == paths,
        "manifest_hashes": all(
            path in entries and sha(entries[path]) == value
            for path, value in files.items()
        ),
        "classification": (
            manifest.get("candidate_release") is False
            and manifest.get("server_rtl_entries") == 0
            and manifest.get("functional_rtl_modified") is False
        ),
        "return_bound": (
            reports["return"].get("valid") is True
            and return_analysis.get("return_zip", {}).get("sha256")
            == RETURN_SHA
        ),
        "v50_dynamic_gate_fail_closed": (
            return_analysis.get("compile_exit") == 0
            and return_analysis.get("run_exit") == 0
            and return_analysis.get("natural_terminal") is False
            and return_analysis.get("formal_d_present") == 0
            and return_analysis.get("formal_d_missing") == 320
            and return_analysis.get("joint_result_gate") is False
        ),
        "build_deterministic": (
            reports["build"].get("zip_sha256") == digest
            and reports["build"].get("deterministic_rebuild_equal") is True
        ),
        "specialized_reports_valid": all(
            reports[name].get("valid") is True
            for name in (
                "runner",
                "publish",
                "syntax",
                "scope",
                "trace",
            )
        ),
        "current_receipts": all(
            current[name] == expected
            for name, (expected, _) in CURRENT.items()
        ),
        "manifest_current_receipts": (
            receipts.get("server_package_rule_sha256")
            == CURRENT["server"][0]
            and receipts.get("common_operator_rule_sha256")
            == CURRENT["common"][0]
        ),
        "required_rules": RULES <= set(receipts.get("rules", [])),
        "release_gate_matrix": (
            len(matrix) == 9
            and len({row.get("gate_id") for row in matrix}) == 9
            and all(
                row.get("applicability")
                in {
                    "blocking_applicable",
                    "receipt_reuse",
                    "record_only",
                    "not_applicable",
                }
                for row in matrix
            )
        ),
        "fixed_server_publication": (
            fixed.get("result_root") == "/home/panqs/ndp/simresult"
            and fixed.get("return_zip") == expected_return_abs
            and fixed.get("configurable") is False
            and fixed.get("shared_exactly_once_finalizer") is True
            and fixed.get("atomic_hidden_staging") is True
            and fixed.get("local_workspace_mapping_forbidden") is True
        ),
        "observer_sha_consistent": (
            sha(observer)
            == reports["syntax"].get("observer", {}).get("sha256")
            == reports["scope"].get("observer", {}).get("sha256")
            == reports["trace"].get("observer", {}).get("sha256")
        ),
        "runner_exit_term": (
            reports["runner"].get("exit_control", {}).get(
                "runner_exit_code"
            )
            == 74
            and reports["runner"].get("term_control", {}).get(
                "runner_exit_code"
            )
            == 143
        ),
        "fixed_publish_four_paths": all(
            reports["publish"].get("cases", {}).get(case, {}).get(
                "sidecar_valid"
            )
            is True
            for case in ("normal", "compile_fail", "int", "term")
        ),
        "fixed_publish_negatives": all(
            reports["publish"].get("negative_controls", {}).values()
        ),
        "changed_surface_exact": set(changed)
        == {
            "PREPARE_AND_RUN.sh",
            "README.md",
            "package_manifest.json",
            "package_tools/node0004_hang_localization_runtime.py",
            "package_tools/node0004_hang_localization_runtime_v7.py",
            "tb_probe/native_return_observer.svh",
        },
        "added_surface_exact": added
        == ["provenance/v50_return_v51_lc13_lc14_diag.json"],
        "nothing_removed": not removed,
        "frozen_runtime_config": all(
            normalize(entries[path]) == normalize(source[path])
            for path in entries
            if path.startswith("workload/runtime/")
        ),
        "path_budget": max(map(len, entries)) <= 240,
        "old_occupancy_invalidated": manifest.get(
            "v50_return_adjudication", {}
        ).get("old_outbuffer_occupancy")
        == "INVALIDATED_NOT_RTL_BUG",
        "cloud_rtl_nonblocking": (
            manifest.get("cloud_rtl_authority", {}).get(
                "approved_commit"
            )
            == "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
            and manifest.get("cloud_rtl_authority", {}).get(
                "identity_difference_blocks_compile_or_simulation"
            )
            is False
        ),
        "local_server_result_path_not_created": (
            reports["publish"].get(
                "local_fixed_server_path_created_or_mapped"
            )
            is False
            and reports["runner"].get(
                "local_fixed_server_path_created_or_mapped"
            )
            is False
        ),
    }
    valid = all(checks.values())
    report = {
        "schema": "node0004-v51-final-zip-current-rule-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "valid": valid,
        "errors": [
            name for name, passed in checks.items() if not passed
        ],
        "checks": checks,
        "zip": {
            "path": str(args.zip),
            "bytes": args.zip.stat().st_size,
            "sha256": digest,
        },
        "source_v50_sha256": SOURCE_SHA,
        "bound_return_sha256": RETURN_SHA,
        "current_rule_receipts": current,
        "release_gate_matrix": matrix,
        "changed_files": changed,
        "added_files": added,
        "removed_files": removed,
        "report_receipts": {
            name: {
                "path": str(path),
                "sha256": file_sha(path),
                "valid": reports[name].get("valid", True),
            }
            for name, path in {
                "return": args.return_report,
                "build": args.build_report,
                "runner": args.runner_controls,
                "publish": args.fixed_publish,
                "syntax": args.observer_syntax,
                "scope": args.actual_consumer,
                "trace": args.predicate_trace,
            }.items()
        },
        "control_exit_codes": {
            "focused_hdl_positive": reports["syntax"]["positive"][
                "exit_code"
            ],
            "missing_declaration": reports["syntax"][
                "negative_controls"
            ]["missing_declaration"]["exit_code"],
            "task_typo": reports["syntax"]["negative_controls"][
                "task_typo"
            ]["exit_code"],
            "actual_consumer_typo": reports["syntax"][
                "negative_controls"
            ]["actual_consumer_typo"]["exit_code"],
            "runner_exit_stub": reports["runner"]["exit_control"][
                "runner_exit_code"
            ],
            "runner_term_finalizer": reports["runner"]["term_control"][
                "runner_exit_code"
            ],
        },
        "package_release": (
            "PACKAGE_READY_NOT_RUN" if valid else "QUARANTINED"
        ),
        "expected_return": expected_return_abs,
        "duplicate_absent_receipt": {
            "server_root": True,
            "package_root": True,
            "install_namespace": True,
            "run_root": True,
            "launch_cwd": True,
        },
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
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
