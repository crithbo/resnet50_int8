from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_node0004_canonical_decision_v10 import (
    validate as validate_canonical,
)
from tools.validate_node0004_observer_four_way_binding import (
    run_negative_controls,
    validate_zip as validate_four_way,
)
from tools.validate_node0004_return_gate_v12 import (
    validate as validate_return_gate,
)


CURRENT_RECEIPTS = {
    ".agents/rules/生成前必读索引.md": (
        "12583308ec9a16dbb8ea15571a5280291"
        "fed7e152167d2e4e8e00509a9a6370f"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "7672b44bbcb7e130792d6b288188caa25"
        "09dc72b1ea3962bf44ffb82588009aa"
    ),
    ".agents/rules/INT8_SA点积专项规则.md": (
        "54a1e12541aaeb6f62dadb19c47a6154e"
        "b0462b758a35a9a5bc4a0043cb37dce"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "4318f3a28de399fb522740315f11bdddf"
        "346e71969cf1e45686899a568b042d7"
    ),
}
PLAN_SHA256 = (
    "8625b61df7094b20e71b07cb658e7fe80"
    "599df847d1c7b22adf5af613028b851"
)
REQUIRED_RULE_IDS = {
    "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
    "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
    "CDA-SERVER-ONE-COMMAND-001",
    "CDA-SCA-D-TB-READBACK-LENGTH-001",
    "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
    "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
    "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
    "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
    "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
    "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
    "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
    "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
    "CDA-SERVER-RETURN-RECEIPT-001",
    "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
    "CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe(name: str) -> PurePosixPath:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name:
        raise ValueError(f"unsafe ZIP path: {name}")
    return pure


def _entries(path: Path) -> tuple[str, dict[str, bytes]]:
    with zipfile.ZipFile(path) as archive:
        crc = archive.testzip()
        if crc is not None:
            raise ValueError(f"CRC failure: {crc}")
        infos = [item for item in archive.infolist() if not item.is_dir()]
        roots = {_safe(item.filename).parts[0] for item in infos}
        if len(roots) != 1:
            raise ValueError(f"ZIP root differs: {sorted(roots)}")
        root = next(iter(roots))
        entries: dict[str, bytes] = {}
        for info in infos:
            pure = _safe(info.filename)
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in entries:
                raise ValueError(f"duplicate ZIP member: {relative}")
            entries[relative] = archive.read(info)
    return root, entries


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def _replace_prefix(value: Any, old: str, new: str) -> tuple[Any, int]:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        count = 0
        for key, item in value.items():
            out[key], delta = _replace_prefix(item, old, new)
            count += delta
        return out, count
    if isinstance(value, list):
        out_list: list[Any] = []
        count = 0
        for item in value:
            changed, delta = _replace_prefix(item, old, new)
            out_list.append(changed)
            count += delta
        return out_list, count
    if isinstance(value, str) and value.startswith(old):
        return new + value[len(old):], 1
    return value, 0


def _frozen_workload_equal(
    project_root: Path,
    entries: dict[str, bytes],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    source = manifest["frozen_source_package"]
    source_path = project_root / source["path"]
    if not source_path.is_file():
        return {"valid": False, "error": "frozen source ZIP missing"}
    observed_sha = sha256_file(source_path)
    if observed_sha != source["sha256"]:
        return {
            "valid": False,
            "error": "frozen source ZIP SHA differs",
            "observed_sha256": observed_sha,
        }
    source_root, source_entries = _entries(source_path)
    current_name = manifest["install_name"]
    old_prefix = f"install/cfg_pkg/{source_root}/"
    new_prefix = f"install/cfg_pkg/{current_name}/"
    current_workload = {
        key: value
        for key, value in entries.items()
        if key.startswith("workload/runtime/")
    }
    source_workload = {
        key: value
        for key, value in source_entries.items()
        if key.startswith("workload/runtime/")
    }
    errors: list[str] = []
    changed_leaf_counts: dict[str, int] = {}
    if set(current_workload) != set(source_workload):
        errors.append("frozen workload path set differs")
    for relative in sorted(set(current_workload) & set(source_workload)):
        if relative.endswith(("sca_cfg.json", "sca_cfg_D.json")):
            source_json = json.loads(source_workload[relative])
            expected, count = _replace_prefix(
                source_json, old_prefix, new_prefix
            )
            observed = json.loads(current_workload[relative])
            if observed != expected:
                errors.append(f"non-root SCA change: {relative}")
            changed_leaf_counts[relative] = count
        elif current_workload[relative] != source_workload[relative]:
            errors.append(f"frozen workload bytes differ: {relative}")
    return {
        "valid": not errors,
        "source_path": str(source_path),
        "source_sha256": observed_sha,
        "source_root": source_root,
        "file_count": len(current_workload),
        "changed_sca_leaf_counts": changed_leaf_counts,
        "errors": errors,
    }


def audit(
    project_root: Path,
    zip_path: Path,
    sidecar: Path,
    python: Path,
    builder: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, Any] = {}
    zip_sha = sha256_file(zip_path)
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    checks["sidecar_exact"] = (
        len(sidecar_tokens) == 2
        and sidecar_tokens[0] == zip_sha
        and sidecar_tokens[1] == zip_path.name
    )
    root, entries = _entries(zip_path)
    manifest = json.loads(entries["package_manifest.json"])

    observed_records = {
        relative: sha256_bytes(payload)
        for relative, payload in entries.items()
        if relative != "package_manifest.json"
    }
    checks["manifest_exact_file_hash_set"] = (
        manifest.get("files") == observed_records
    )
    checks["candidate_release_false"] = (
        manifest.get("candidate_release") is False
    )
    checks["diagnostic_only"] = (
        manifest.get("classification")
        == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    )
    checks["no_functional_rtl"] = (
        manifest.get("functional_rtl_modified") is False
        and manifest.get("server_rtl_entries") == 0
        and not any("/rtl/" in f"/{name}/" for name in entries)
    )
    return_budget = manifest.get("return_budget", {})
    checks["return_budget_contract"] = return_budget == {
        "compressed_zip_max_bytes": 16777216,
        "uncompressed_max_bytes": 33554432,
        "per_text_file_max_bytes": 8388608,
        "final_exact_set_required": True,
        "crc_required": True,
        "sidecar_required": True,
        "forbidden_suffixes": [
            ".vcd",
            ".fsdb",
            ".daidir",
            ".sdb",
            ".so",
            ".a",
            ".pyc",
            ".zip",
        ],
    }
    forbidden_suffixes = (
        ".vcd",
        ".fsdb",
        ".daidir",
        ".sdb",
        ".so",
        ".a",
        ".pyc",
    )
    checks["forbidden_entries_absent"] = not any(
        name.endswith(forbidden_suffixes)
        or "__pycache__" in PurePosixPath(name).parts
        or name.endswith(".zip")
        for name in entries
    )

    receipts = manifest.get("active_receipts", {})
    read_receipt = {
        item["path"]: item["sha256"]
        for item in receipts.get("generation_read_receipt", [])
    }
    current_hashes = {
        relative: sha256_file(project_root / relative)
        for relative in CURRENT_RECEIPTS
    }
    checks["current_rule_receipts_match"] = (
        current_hashes == CURRENT_RECEIPTS
        and read_receipt == CURRENT_RECEIPTS
        and receipts.get("server_package_rule_sha256")
        == CURRENT_RECEIPTS[".agents/rules/服务器测试包生成规则.md"]
        and receipts.get("plan_mutable_provenance_sha256") == PLAN_SHA256
    )
    checks["required_rule_ids_complete"] = REQUIRED_RULE_IDS.issubset(
        set(receipts.get("rules", []))
    )

    runner = entries["PREPARE_AND_RUN.sh"].decode("utf-8")
    runtime_path = manifest["observer_binding_four_way"]["runtime_return"][
        "runtime_source"
    ]
    runtime = entries[runtime_path].decode("utf-8")
    export_index = runner.find("export PYTHONDONTWRITEBYTECODE=1")
    first_python_index = runner.find("python3 ")
    dont_index = runtime.find("sys.dont_write_bytecode = True")
    helper_import_index = runtime.find(
        "import node0004_hang_localization_runtime_v7"
    )
    checks["bootstrap_static_order"] = (
        0 <= export_index < first_python_index
        and 0 <= dont_index < helper_import_index
    )
    checks["one_command_runner"] = all(
        token in runner
        for token in (
            'if [ "$#" -ne 1 ]',
            "server_root must be absolute",
            "bash PREPARE_AND_RUN.sh",
            'package_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"',
        )
    )
    checks["sca_pair_bound"] = (
        "+SCA_CFG=" in runner
        and "+SCA_CFG_D=" in runner
        and "sca_cfg_D_softmax" not in runner
    )
    checks["isolated_namespaces"] = all(
        token in runner
        for token in (
            'run_root="${server_root}/run_${install_name}"',
            'evidence_root="${server_root}/evidence_${install_name}"',
            'return_dir="${server_root}/${install_name}_return"',
            "Fresh namespace required:",
        )
    )
    checks["signal_traps_and_return"] = all(
        token in runner
        for token in (
            "trap 'on_signal HUP 129' HUP",
            "trap 'on_signal INT 130' INT",
            "trap 'on_signal TERM 143' TERM",
            'python3 "$runtime" collect',
        )
    )
    checks["return_gate_runtime_bound"] = all(
        token in runtime
        for token in (
            "RETURN_ZIP_MAX_BYTES = 16 * 1024 * 1024",
            "RETURN_UNCOMPRESSED_MAX_BYTES = 32 * 1024 * 1024",
            "RETURN_TEXT_MAX_BYTES = 8 * 1024 * 1024",
            "def validate_return_zip(",
            "return exact-set differs",
            "required progress diagnostic missing after compile",
            "base.collect = collect",
        )
    )
    checks["external_signal_canonical_fallback_bound"] = all(
        token in runtime
        for token in (
            "def _fallback_canonical(",
            '"decision": "EVIDENCE_INSUFFICIENT"',
            '"reason": "EXTERNAL_SIGNAL_BEFORE_OBSERVER_CANONICAL"',
            '"canonical_fallback_used": fallback_used',
        )
    )
    checks["required_progress_diagnostics_manifest"] = (
        manifest.get("return_diagnostics_required_after_compile_success")
        == [
            "runs/c0/simulator_argv.txt",
            "runs/c0/sim.log",
            "runs/c0/return_observer.log",
            "runs/c0/host_progress.log",
        ]
    )
    progress = manifest.get("progress_contract", {})
    checks["default_progress_diagnostics"] = (
        progress.get("default_progress_diagnostics_enabled") is True
        and progress.get("default_progress_diagnostics_exemption") is None
        and "+RETURN_HANG_DIAG" in runner
        and "host_progress.log" in runner
    )

    frozen = _frozen_workload_equal(project_root, entries, manifest)
    checks["frozen_workload_provenance"] = frozen["valid"]

    four_way = validate_four_way(zip_path)
    four_negative = run_negative_controls(zip_path)
    checks["observer_four_way"] = (
        four_way["valid"] and four_negative["all_failed_closed"]
    )
    canonical = validate_canonical(zip_path)
    checks["canonical_decision"] = (
        canonical["valid"]
        and canonical["negative_controls"][
            "persistent_high_level_not_n_transactions"
        ]
        and canonical["negative_controls"][
            "summary_only_append_fails_closed"
        ]
        and canonical["negative_controls"][
            "conflicting_double_decision_fails_closed"
        ]
        and canonical["negative_controls"]["missing_reason_fails_closed"]
        and canonical["negative_controls"]["missing_boundary_fails_closed"]
    )
    return_gate = validate_return_gate()
    checks["return_gate_negative_controls"] = (
        return_gate["valid"]
        and return_gate["all_negative_controls_fail_closed"]
        and return_gate["external_signal_canonical_fallback_valid"]
    )

    with tempfile.TemporaryDirectory(
        prefix="node0004-v12-final-audit-"
    ) as temporary:
        extract_parent = Path(temporary)
        package = extract_parent / root
        for relative, payload in entries.items():
            target = package / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        before = _tree_hashes(package)
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        command = [
            str(python),
            "-B",
            str(package / runtime_path),
            "preflight",
            "--package-root",
            str(package),
        ]
        completed = subprocess.run(
            command,
            cwd=package,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        after = _tree_hashes(package)
        checks["fresh_extract_runtime_preflight"] = completed.returncode == 0
        checks["bootstrap_tree_immutable"] = before == after
        checks["runtime_d_absent"] = (
            completed.returncode == 0
            and json.loads(completed.stdout).get("c0_absent_d_leaf_count") == 28
        )
        bootstrap_receipt = {
            "command": command,
            "cwd": str(package),
            "exit_code": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            "tree_equal": before == after,
            "file_count_before": len(before),
            "file_count_after": len(after),
        }

    with tempfile.TemporaryDirectory(
        prefix="node0004-v12-independent-rebuild-"
    ) as temporary:
        rebuild_root = Path(temporary)
        rebuild_command = [
            str(python),
            str(builder),
            "--output-root",
            str(rebuild_root),
        ]
        rebuild = subprocess.run(
            rebuild_command,
            cwd=project_root,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        rebuilt_zip = rebuild_root / zip_path.name
        rebuilt_sha = (
            sha256_file(rebuilt_zip) if rebuilt_zip.is_file() else None
        )
        checks["independent_deterministic_rebuild"] = (
            rebuild.returncode == 0 and rebuilt_sha == zip_sha
        )
        rebuild_receipt = {
            "command": rebuild_command,
            "cwd": str(project_root),
            "exit_code": rebuild.returncode,
            "rebuilt_zip_sha256": rebuilt_sha,
            "final_zip_sha256": zip_sha,
            "equal": rebuilt_sha == zip_sha,
            "stdout_tail": rebuild.stdout[-4000:],
            "stderr_tail": rebuild.stderr[-4000:],
        }

    applicable = {
        "CDA-SERVER-WORKLOAD-PROVENANCE-001": checks[
            "frozen_workload_provenance"
        ],
        "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001": True,
        "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001": (
            checks["bootstrap_static_order"]
            and checks["fresh_extract_runtime_preflight"]
            and checks["bootstrap_tree_immutable"]
        ),
        "CDA-SERVER-ONE-COMMAND-001": checks["one_command_runner"],
        "CDA-SCA-D-TB-READBACK-LENGTH-001": checks["sca_pair_bound"],
        "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001": checks[
            "runtime_d_absent"
        ],
        "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001": checks[
            "default_progress_diagnostics"
        ],
        "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001": checks[
            "observer_four_way"
        ],
        "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001": canonical["checks"][
            "qualified_progress_only"
        ],
        "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001": checks[
            "canonical_decision"
        ],
        "CDA-SERVER-RETURN-RECEIPT-001": checks[
            "signal_traps_and_return"
        ] and checks["return_gate_runtime_bound"],
        "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001": checks[
            "forbidden_entries_absent"
        ] and checks["return_gate_negative_controls"],
        "CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001": (
            manifest.get("candidate_release") is False
            and manifest.get("numeric_analysis_repeated") is False
            and manifest.get("node0004_workload_rebuilt") is False
        ),
    }
    not_applicable = {
        "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001": (
            "package-local observer is compiled by +incdir; no server TB "
            "file is installed, modified, or restored"
        ),
        "CDA-SERVER-RESULT-GATE-CONJUNCTION-001": (
            "diagnostic package cannot claim PASS/E3/E4/E5; runtime result "
            "schema keeps formal_readback_claimed/e4/e5 false"
        ),
        "functional_RTL_repair_profile": (
            "no functional RTL entry and no RTL repair authorization"
        ),
    }
    for name, passed in checks.items():
        if isinstance(passed, bool) and not passed:
            errors.append(f"check failed: {name}")
    for rule_id, passed in applicable.items():
        if not passed:
            errors.append(f"rule failed: {rule_id}")
    all_negative_fail_closed = (
        four_negative["all_failed_closed"]
        and canonical["checks"]["all_negative_controls_fail_closed"]
        and return_gate["all_negative_controls_fail_closed"]
    )
    passed = not errors and all_negative_fail_closed
    return {
        "schema": "node0004-final-zip-rule-self-audit-v12",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if passed
            else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "errors": errors,
        "error_count": len(errors),
        "all_required_negative_controls_fail_closed": (
            all_negative_fail_closed
        ),
        "zip": {
            "path": str(zip_path.resolve()),
            "size_bytes": zip_path.stat().st_size,
            "sha256": zip_sha,
            "root": root,
            "entry_count": len(entries),
        },
        "sidecar": {
            "path": str(sidecar.resolve()),
            "sha256": sha256_file(sidecar),
            "match": checks["sidecar_exact"],
        },
        "post_generation_read_receipt": [
            {
                "path": path,
                "sha256": current_hashes[path],
                "current_match": current_hashes[path] == expected,
            }
            for path, expected in CURRENT_RECEIPTS.items()
        ],
        "plan_mutable_provenance_sha256": PLAN_SHA256,
        "applicable_rule_ids": applicable,
        "not_applicable": not_applicable,
        "checks": checks,
        "frozen_workload": frozen,
        "bootstrap_runtime": bootstrap_receipt,
        "independent_rebuild": rebuild_receipt,
        "four_way": four_way,
        "four_way_negative_controls": four_negative,
        "canonical": canonical,
        "return_gate": return_gate,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--builder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(
        args.project_root.resolve(),
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.python.resolve(),
        args.builder.resolve(),
    )
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
