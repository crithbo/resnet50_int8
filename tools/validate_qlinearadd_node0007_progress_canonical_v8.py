from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    validate_qlinearadd_node0007_progress_bind_v6_four_way as four_way_tool,
)
from tools import (
    validate_qlinearadd_node0007_progress_canonical_v7 as canonical_tool,
)


INSTALL_NAME = "r5_qadd_n7_progress_canon_v8"
SOURCE_NAME = "r5_qadd_n7_progress_canon_v7"
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = ZIP_PATH.with_suffix(".zip.sha256")
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
ZIP_SHA256 = (
    "b74b18f906fbf32851ce016906c599889236e7088ad7209607e52368bad69100"
)
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "1ed2ed3cb1015e62b585a77dbff0b82b45e592a27695ddd9331b47eb1196df1f"
)
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
INDEX_SHA256 = (
    "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
QADD_RULE_SHA256 = (
    "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba"
)
CANONICAL_REL = "package_tools/qlinearadd_progress_canonical_decision.py"
CANONICAL_SHA256 = (
    "6423f96c6e2647cd30fe20cd4ad1d5291bf5c4751187bbf2dcaf4b923a8145e3"
)
OBSERVER_REL = "tb_probe/native_return_observer.svh"
OBSERVER_SHA256 = four_way_tool.OBSERVER_SHA256
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-progress-canonical-v8"
    / "report.json"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rule_ids(path: Path) -> list[str]:
    return re.findall(
        r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8")
    )


def _records(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def _bootstrap_receipt() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qadd-v8-bootstrap-") as temporary:
        destination = Path(temporary)
        with zipfile.ZipFile(ZIP_PATH) as archive:
            archive.extractall(destination)
        package = destination / INSTALL_NAME
        before = _records(package)
        runtime = (
            package
            / "package_tools/qlinearadd_node0007_server_runtime.py"
        )
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(runtime),
                "preflight",
                "--package-root",
                str(package),
            ],
            cwd=package,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        after = _records(package)
    return {
        "command": (
            "<current-python> package_tools/"
            "qlinearadd_node0007_server_runtime.py preflight --package-root "
            "<fresh-extract>"
        ),
        "cwd": "<fresh-extract-package-root>",
        "exit_code": result.returncode,
        "stdout_is_json": result.stdout.lstrip().startswith("{"),
        "stderr": result.stderr,
        "package_tree_unchanged": before == after,
        "pycache_absent": not any(
            "__pycache__" in name or name.endswith(".pyc") for name in after
        ),
        "passed": (
            result.returncode == 0
            and before == after
            and not any(
                "__pycache__" in name or name.endswith(".pyc")
                for name in after
            )
        ),
    }


def _workload_equivalent(
    source: dict[str, bytes], successor: dict[str, bytes]
) -> dict[str, Any]:
    old_prefix = f"{SOURCE_NAME}/workload/runtime/"
    new_prefix = f"{INSTALL_NAME}/workload/runtime/"
    old = {
        name[len(old_prefix) :]: payload
        for name, payload in source.items()
        if name.startswith(old_prefix)
    }
    new = {
        name[len(new_prefix) :]: payload
        for name, payload in successor.items()
        if name.startswith(new_prefix)
    }
    changed = [
        name
        for name in sorted(set(old) & set(new))
        if new[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        != old[name]
    ]
    missing = sorted(set(old) - set(new))
    extra = sorted(set(new) - set(old))
    return {
        "valid": not changed and not missing and not extra,
        "file_count": len(old),
        "changed_after_namespace_normalization": changed,
        "missing": missing,
        "extra": extra,
    }


def _exact_set(
    members: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    prefix = f"{INSTALL_NAME}/"
    observed = {
        name[len(prefix) :]: {
            "size_bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
        for name, payload in members.items()
        if name.startswith(prefix)
        and name != prefix + "TEST_PACKAGE_MANIFEST.json"
    }
    expected = manifest.get("files", {})
    return {
        "valid": observed == expected,
        "missing": sorted(set(expected) - set(observed)),
        "extra": sorted(set(observed) - set(expected)),
        "changed": sorted(
            name
            for name in set(expected) & set(observed)
            if expected[name] != observed[name]
        ),
    }


def validate_final_zip() -> dict[str, Any]:
    members, manifest = canonical_tool._load_zip(ZIP_PATH, INSTALL_NAME)
    source_members, _ = canonical_tool._load_zip(SOURCE_ZIP, SOURCE_NAME)
    root = f"{INSTALL_NAME}/"
    runner = members[root + "PREPARE_AND_RUN.sh"].decode()
    runtime = members[
        root + "package_tools/qlinearadd_node0007_server_runtime.py"
    ].decode()
    parser_payload = members[root + CANONICAL_REL]
    observer = members[root + OBSERVER_REL].decode(errors="replace")
    allowlist = manifest["return_allowlist"]
    required_targets = {
        item["target_path"]
        for item in allowlist
        if item.get("required") is True
    }
    audit = manifest.get("final_zip_rule_self_audit", {})
    receipts = audit.get("rule_receipts", {})
    current_receipts = {
        "generation_index": {
            "path": ".agents/rules/生成前必读索引.md",
            "sha256": sha256_file(INDEX),
            "current_match": sha256_file(INDEX) == INDEX_SHA256,
        },
        "server_package_rule": {
            "path": ".agents/rules/服务器测试包生成规则.md",
            "sha256": sha256_file(SERVER_RULE),
            "current_match": sha256_file(SERVER_RULE) == SERVER_RULE_SHA256,
        },
        "qlinearadd_rule": {
            "path": ".agents/rules/QLinearAdd算子配置规则.md",
            "sha256": sha256_file(QADD_RULE),
            "current_match": sha256_file(QADD_RULE) == QADD_RULE_SHA256,
        },
    }
    rule_receipts_valid = receipts == current_receipts
    rule_ids_valid = (
        audit.get("applicable_server_rule_ids") == _rule_ids(SERVER_RULE)
        and audit.get("applicable_qlinearadd_rule_ids")
        == _rule_ids(QADD_RULE)
    )

    exact_set = _exact_set(members, manifest)
    validation = json.loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    deterministic = (
        validation.get("repeated_build", {}).get("package_tree_equal") is True
        and validation.get("repeated_build", {}).get("zip_equal") is True
        and validation.get("repeated_build", {}).get("repeat_zip_sha256")
        == ZIP_SHA256
    )
    one_command = (
        'if [ "$#" -ne 1 ]' in runner
        and "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
        in runner
        and "server_source_preflight_performed" in json.dumps(manifest)
        and manifest.get("server_source_preflight_performed") is False
    )
    bootstrap = _bootstrap_receipt()
    runtime_d_absent = not any(
        "/workload/runtime/" in name
        and "matrix_D_linearized_128bit" in name
        for name in members
    )
    result_gate = manifest.get("result_gate") == (
        "compile0 AND simulation0 AND natural_terminal AND loader_exact "
        "AND readback_exact_set AND missing0 AND mismatch0"
    )
    return_allowlist = (
        manifest.get("return_collection_policy")
        == "MANIFEST_EXPLICIT_ALLOWLIST_ONLY"
        and len(allowlist) == 48
        and len({item["target_path"] for item in allowlist}) == len(allowlist)
        and "evidence/CANONICAL_PROGRESS_DECISION.json"
        in required_targets
        and "runs/return_observer.log" in required_targets
        and 'python3 "$runtime" collect' in runner
    )
    event_qualification = all(
        token in observer
        for token in (
            "gexec2slice_fire_mon",
            "local_req_hs",
            "local_rdata_hs",
            "local_wdata_hs",
            "return_obs_req_count[mse]++",
            "return_obs_rdata_count[mse]++",
            "return_obs_wdata_count[mse]++",
        )
    )
    canonical_manifest = manifest.get("canonical_decision_contract", {})
    canonical_valid = (
        sha256_bytes(parser_payload) == CANONICAL_SHA256
        and canonical_manifest.get("rule_id")
        == "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001"
        and canonical_manifest.get("unique_complete_record_required") is True
        and canonical_manifest.get("qualified_counters")
        == ["gexec", "req", "rdata", "wdata"]
        and canonical_manifest.get("raw_state_excluded_from_progress")
        == ["buf4_wr", "buf4_rd", "buf5_wr", "buf5_rd"]
        and 'python3 "$decision_runtime"' in runner
        and "canonical_decision_exit_status.txt" in runner
    )
    defaults = manifest.get("default_progress_diagnostics", {})
    default_progress = (
        defaults.get("rule_id")
        == "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001"
        and defaults.get("enabled_by_default") is True
        and defaults.get("read_only") is True
        and defaults.get("rate_limited") is True
        and defaults.get("partial_return_on_exit_and_signals") is True
        and all(
            target in required_targets
            for target in (
                "evidence/actual_compile_argv.txt",
                "evidence/actual_simulator_argv.txt",
                "evidence/host_timing.txt",
                "evidence/progress_samples.log",
                "evidence/signal_status.txt",
                "runs/return_observer.log",
                "evidence/CANONICAL_PROGRESS_DECISION.json",
            )
        )
    )

    four_way_tool.INSTALL_NAME = INSTALL_NAME
    four_way_tool.ZIP_PATH = ZIP_PATH
    four_way_tool.SIDECAR_PATH = SIDECAR_PATH
    four_way_tool.ZIP_SHA256 = ZIP_SHA256
    four_way_tool.SERVER_RULE = SERVER_RULE
    four_way_tool.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    final_four_way = four_way_tool._inspect(
        members, manifest, require_fresh_extract=True
    )
    four_way_controls = four_way_tool.negative_control_receipts()
    four_way_controls_valid = all(
        item["failed_closed"] for item in four_way_controls.values()
    )
    canonical_controls = canonical_tool._canonical_negative_controls()
    canonical_controls_valid = all(
        item["failed_closed"] for item in canonical_controls.values()
    )
    workload = _workload_equivalent(source_members, members)
    source_quarantined = (
        sha256_file(SOURCE_ZIP) == SOURCE_ZIP_SHA256
        and manifest.get("superseded_diagnostic", {}).get("status")
        == "QUARANTINED_NOT_RUN_ACTIVE_RULE_DRIFT_AFTER_BUILD"
    )
    sidecar_exact = SIDECAR_PATH.read_text(encoding="ascii").split() == [
        ZIP_SHA256,
        ZIP_PATH.name,
    ]
    zip_exact = sha256_file(ZIP_PATH) == ZIP_SHA256
    bootstrap_static = (
        "export PYTHONDONTWRITEBYTECODE=1" in runner
        and "sys.dont_write_bytecode = True" in runtime
        and "__pycache__" not in manifest.get("files", {})
    )
    audit_contract_valid = (
        audit.get("rule_id")
        == "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001"
        and audit.get("direct_final_zip_and_sidecar_validation_required")
        is True
        and audit.get("all_required_negative_controls_required") is True
        and audit.get("errors_must_equal") == 0
        and audit.get("pass_field") == "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
    )

    gates = {
        "zip_sha_and_sidecar": zip_exact and sidecar_exact,
        "current_rule_receipts": rule_receipts_valid and rule_ids_valid,
        "final_zip_exact_set": exact_set["valid"],
        "deterministic_double_build": deterministic,
        "bootstrap_immutability": bootstrap_static and bootstrap["passed"],
        "one_command_and_no_server_source_preflight": one_command,
        "runtime_D_absent": runtime_d_absent,
        "default_progress_diagnostics": default_progress,
        "observer_four_way_binding": final_four_way["valid"],
        "observer_event_qualification": event_qualification,
        "canonical_decision": canonical_valid,
        "dynamic_result_gate_conjunction": result_gate,
        "manifest_return_allowlist": return_allowlist,
        "frozen_workload_equivalence": workload["valid"],
        "source_v7_quarantined": source_quarantined,
        "self_audit_contract": audit_contract_valid,
        "four_way_negative_controls": four_way_controls_valid,
        "canonical_negative_controls": canonical_controls_valid,
    }
    errors = sorted(name for name, passed in gates.items() if not passed)
    passed = not errors
    return {
        "schema": "qlinearadd-node0007-final-zip-rule-self-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "errors": errors,
        "error_count": len(errors),
        "status": (
            "CANONICAL_DECISION_RULE_VALIDATED"
            if passed
            else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": sha256_file(ZIP_PATH),
        "sidecar": SIDECAR_PATH.relative_to(ROOT).as_posix(),
        "sidecar_exact": sidecar_exact,
        "post_build_rule_receipts": current_receipts,
        "applicable_server_rule_ids": _rule_ids(SERVER_RULE),
        "applicable_qlinearadd_rule_ids": _rule_ids(QADD_RULE),
        "gates": gates,
        "final_zip_exact_set": exact_set,
        "bootstrap_receipt": bootstrap,
        "deterministic_build_receipt": validation.get("repeated_build"),
        "four_way_binding": final_four_way,
        "four_way_negative_controls": four_way_controls,
        "canonical_negative_controls": canonical_controls,
        "all_required_negative_controls_fail_closed": (
            four_way_controls_valid and canonical_controls_valid
        ),
        "frozen_workload_equivalence": workload,
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "server_action": False,
    }


def main() -> int:
    report = validate_final_zip()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
