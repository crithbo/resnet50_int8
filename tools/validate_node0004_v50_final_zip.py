from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n4_hw_v50_dterm_owner_diag"
SOURCE_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
ZIP_SHA = "c8a809f8ebb723c286b5c0190bcd1142f9ba2d8965731b8ee194182c0922c830"
SOURCE_SHA = "2b7faeb4b838133f041432ff707792047d113bf65871aa8936e3f2f4c502e27c"
RETURN_SHA = "722a1cee4b7e54564d060e202792d8179e6223570b8bfbb5fd51eac3f268637b"
CURRENT = {
    "agent": ("32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
              ".agents/agent.md"),
    "plan": ("43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70",
             ".agents/plan.md"),
    "index": ("2697fec8192f5008a0b5f288a4c38c36e9f493ff85db264479e4c5a88b03b706",
              ".agents/rules/生成前必读索引.md"),
    "server": ("5540e9c724e9c313e9a874a8251ad291328d4df80f01382ca091520893e757a1",
               ".agents/rules/服务器测试包生成规则.md"),
    "common": ("dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
               ".agents/rules/算子配置规则.md"),
    "ndp": ("603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
            ".agents/rules/NDP硬件字段语义.md"),
    "int8_sa": ("54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
                ".agents/rules/INT8_SA点积专项规则.md"),
    "readme": ("0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
               "NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
}
RULES = {
    "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
    "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
    "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
    "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(path: Path) -> str:
    return sha(path.read_bytes())


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], list[str]]:
    result: dict[str, bytes] = {}
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            errors.append("crc")
        seen: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            posix = PurePosixPath(info.filename)
            if (
                info.filename in seen or posix.is_absolute()
                or ".." in posix.parts or "\\" in info.filename
            ):
                errors.append(f"unsafe:{info.filename}")
            seen.add(info.filename)
            if posix.parts:
                roots.add(posix.parts[0])
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                errors.append(f"symlink:{info.filename}")
            if not info.is_dir() and len(posix.parts) > 1:
                result[PurePosixPath(*posix.parts[1:]).as_posix()] = archive.read(info)
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
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True, type=Path)
    p.add_argument("--sidecar", required=True, type=Path)
    p.add_argument("--source-v49", required=True, type=Path)
    p.add_argument("--return-report", required=True, type=Path)
    p.add_argument("--build-report", required=True, type=Path)
    p.add_argument("--runner-controls", required=True, type=Path)
    p.add_argument("--observer-syntax", required=True, type=Path)
    p.add_argument("--actual-consumer", required=True, type=Path)
    p.add_argument("--predicate-trace", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    entries, zip_errors = read_zip(args.zip, INSTALL_NAME)
    source, source_errors = read_zip(args.source_v49, SOURCE_NAME)
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    reports = {
        "return": load(args.return_report),
        "build": load(args.build_report),
        "runner": load(args.runner_controls),
        "syntax": load(args.observer_syntax),
        "scope": load(args.actual_consumer),
        "trace": load(args.predicate_trace),
    }
    digest = file_sha(args.zip)
    files = manifest.get("files", {})
    paths = set(entries) - {"package_manifest.json"}
    receipts = manifest.get("active_receipts", {})
    current = {name: file_sha(ROOT / path) for name, (_, path) in CURRENT.items()}
    common = set(entries) & set(source)
    changed = sorted(
        path for path in common if normalize(entries[path]) != normalize(source[path])
    )
    added = sorted(set(entries) - set(source))
    removed = sorted(set(source) - set(entries))
    matrix = manifest.get("release_gate_matrix", [])
    return_analysis = reports["return"].get("RETURN_ANALYSIS", {})
    observer = entries.get("tb_probe/native_return_observer.svh", b"")
    checks = {
        "zip_sha": digest == ZIP_SHA,
        "sidecar_exact": args.sidecar.read_text(encoding="ascii")
        == f"{digest}  {args.zip.name}\n",
        "source_sha": file_sha(args.source_v49) == SOURCE_SHA,
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
            and return_analysis.get("return_zip", {}).get("sha256") == RETURN_SHA
        ),
        "v49_dynamic_gate_fail_closed": (
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
            for name in ("runner", "syntax", "scope", "trace")
        ),
        "current_receipts": all(
            current[name] == expected for name, (expected, _) in CURRENT.items()
        ),
        "manifest_current_receipts": (
            receipts.get("server_package_rule_sha256") == CURRENT["server"][0]
            and receipts.get("common_operator_rule_sha256") == CURRENT["common"][0]
        ),
        "required_rules": RULES <= set(receipts.get("rules", [])),
        "release_gate_matrix": (
            len(matrix) == 9
            and len({row.get("gate_id") for row in matrix}) == 9
            and all(row.get("applicability") in {
                "blocking_applicable", "receipt_reuse", "record_only",
                "not_applicable"
            } for row in matrix)
        ),
        "observer_sha_consistent": (
            sha(observer)
            == reports["syntax"].get("observer", {}).get("sha256")
            == reports["scope"].get("observer", {}).get("sha256")
            == reports["trace"].get("observer", {}).get("sha256")
        ),
        "runner_exit_term": (
            reports["runner"].get("exit_control", {}).get("runner_exit_code") == 74
            and reports["runner"].get("term_control", {}).get("runner_exit_code") == 143
        ),
        "runner_feature_receipt": (
            reports["runner"].get("exit_control", {}).get("checks", {}).get(
                "four_feature_receipt_valid"
            ) is True
        ),
        "changed_surface_exact": set(changed) == {
            "PREPARE_AND_RUN.sh",
            "README.md",
            "package_manifest.json",
            "package_tools/node0004_hang_localization_runtime.py",
            "tb_probe/native_return_observer.svh",
        },
        "added_surface_exact": added == [
            "provenance/v49_return_v50_dterm_owner_diag.json"
        ],
        "nothing_removed": not removed,
        "frozen_runtime_config": all(
            normalize(entries[path]) == normalize(source[path])
            for path in entries if path.startswith("workload/runtime/")
        ),
        "path_budget": max(map(len, entries)) <= 240,
        "old_occupancy_invalidated": manifest.get(
            "v49_return_adjudication", {}
        ).get("old_outbuffer_occupancy") == "INVALIDATED_NOT_RTL_BUG",
        "cloud_rtl_nonblocking": (
            manifest.get("cloud_rtl_authority", {}).get("approved_commit")
            == "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
            and manifest.get("cloud_rtl_authority", {}).get(
                "identity_difference_blocks_compile_or_simulation"
            ) is False
        ),
    }
    valid = all(checks.values())
    report = {
        "schema": "node0004-v50-final-zip-current-rule-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "valid": valid,
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {"path": str(args.zip), "bytes": args.zip.stat().st_size,
                "sha256": digest},
        "source_v49_sha256": SOURCE_SHA,
        "bound_return_sha256": RETURN_SHA,
        "current_rule_receipts": current,
        "release_gate_matrix": matrix,
        "changed_files": changed,
        "added_files": added,
        "removed_files": removed,
        "report_receipts": {
            name: {"path": str(path), "sha256": file_sha(path),
                   "valid": reports[name].get("valid", True)}
            for name, path in {
                "return": args.return_report, "build": args.build_report,
                "runner": args.runner_controls, "syntax": args.observer_syntax,
                "scope": args.actual_consumer, "trace": args.predicate_trace,
            }.items()
        },
        "control_exit_codes": {
            "focused_hdl_positive": reports["syntax"]["positive"]["exit_code"],
            "missing_declaration": reports["syntax"]["negative_controls"][
                "missing_declaration"
            ]["exit_code"],
            "task_typo": reports["syntax"]["negative_controls"]["task_typo"][
                "exit_code"
            ],
            "actual_consumer_typo": reports["syntax"]["negative_controls"][
                "actual_consumer_typo"
            ]["exit_code"],
            "runner_exit_stub": reports["runner"]["exit_control"][
                "runner_exit_code"
            ],
            "runner_term_finalizer": reports["runner"]["term_control"][
                "runner_exit_code"
            ],
        },
        "package_release": "PACKAGE_READY_NOT_RUN" if valid else "QUARANTINED",
        "expected_return": f"{INSTALL_NAME}_return.zip",
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
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
