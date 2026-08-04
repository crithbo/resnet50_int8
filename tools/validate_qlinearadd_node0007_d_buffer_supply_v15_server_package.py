from __future__ import annotations

import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_d_buffer_supply_v15 import (
    build_configs,
    validate_d_buffer_supply,
)
from tools import validate_qlinearadd_node0007_first_request_chain_v10 as base
from tools import validate_qlinearadd_node0007_minimal_preflight_v11 as v11
from tools import validate_qlinearadd_node0007_config_preload_v14 as v14


INSTALL_NAME = "r5_qadd_n7_dbuf_v15"
SOURCE_NAME = "r5_qadd_n7_cfgpreload_v14"
ZIP_SHA256 = "3beef62deeea914abff9120714f8a8fcbad13e9cc40cd0b2a6f68db74c0eac3a"
SOURCE_ZIP_SHA256 = "78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282"
SERVER_RULE_SHA256 = "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-d-buffer-supply-v15"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"
PIPELINE = EVIDENCE_ROOT / "execplan/pipeline_output"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _configure_base() -> None:
    v11.INSTALL_NAME = INSTALL_NAME
    v11.SOURCE_NAME = SOURCE_NAME
    v11.ZIP_SHA256 = ZIP_SHA256
    v11.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    v11.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    v11.ZIP_PATH = ZIP_PATH
    v11.SIDECAR_PATH = SIDECAR_PATH
    v11.SOURCE_ZIP = SOURCE_ZIP
    v11.BUILD_RECEIPT = BUILD_RECEIPT
    v11.REPORT_PATH = REPORT_PATH


def _load_zip(path: Path, root_name: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        members = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
        }
    manifest = json.loads(
        members[f"{root_name}/TEST_PACKAGE_MANIFEST.json"]
    )
    return members, manifest


def _workload_equivalence(
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
    allowed_native = {
        name
        for name in set(old) | set(new)
        if name.startswith("install/execplan")
        or (
            name.startswith("install/cfg_pkg/")
            and name.endswith("_bitstream_128b.bin")
        )
    }
    errors: list[str] = []
    if set(old) != set(new):
        errors.append("workload runtime exact-set differs")
    for name in sorted(set(old) & set(new)):
        normalized = new[name].replace(
            INSTALL_NAME.encode(), SOURCE_NAME.encode()
        )
        if name in allowed_native:
            continue
        if normalized != old[name]:
            errors.append(f"unrelated frozen workload changed: {name}")
    return {
        "valid": not errors,
        "file_count": len(new),
        "allowed_delta": (
            "fresh execplan and six config bitstreams only; tensor payload, "
            "SCA/SCA_D values, golden and observer unchanged after namespace"
        ),
        "allowed_native_paths": sorted(allowed_native),
        "errors": errors,
    }


def _native_chain_checks(members: dict[str, bytes]) -> dict[str, Any]:
    root = f"{INSTALL_NAME}/workload/runtime/"
    errors: list[str] = []
    for source in (PIPELINE / "install").glob("execplan*.txt"):
        name = root + "install/" + source.name
        if members.get(name) != source.read_bytes():
            errors.append(f"fresh execplan differs: {source.name}")
    for source in (PIPELINE / "install/cfg_pkg").glob("*_bitstream_128b.bin"):
        name = root + "install/cfg_pkg/" + source.name
        if members.get(name) != source.read_bytes():
            errors.append(f"fresh bitstream differs: {source.name}")
    execplan_report = json.loads(
        (PIPELINE.parent / "execplan_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    double_run = json.loads(
        (PIPELINE.parent / "double_run_comparison.json").read_text(
            encoding="utf-8"
        )
    )
    if execplan_report.get("valid") is not True:
        errors.append("execplan validator is not clean")
    if double_run.get("equal") is not True:
        errors.append("fresh native chain double run differs")
    return {
        "valid": not errors,
        "errors": errors,
        "execplan_validation_report_sha256": sha256(
            PIPELINE.parent / "execplan_validation_report.json"
        ),
        "double_run_comparison_sha256": sha256(
            PIPELINE.parent / "double_run_comparison.json"
        ),
    }


def _supply_contract_errors(
    manifest: dict[str, Any],
    *,
    override: dict[str, Any] | None = None,
) -> list[str]:
    record = copy.deepcopy(
        override
        if override is not None
        else manifest.get("functional_configuration_fix")
    )
    if not isinstance(record, dict):
        return ["D-buffer functional fix contract absent"]
    expected = {
        "changed_stages": [
            "op_relocation_pad",
            "op_tail_mul",
            "op_tail_round",
        ],
        "transaction_bytes": 32,
        "buffer_bytes_per_row": 16,
        "old_supply_bytes": 16,
        "new_supply_bytes": 32,
        "functional_rtl_modified": False,
        "w3_qparams_tail_workload_golden_changed": False,
        "dram_loop_address_occurrence_changed": False,
    }
    errors = [
        f"D-buffer fix field differs: {key}"
        for key, value in expected.items()
        if record.get(key) != value
    ]
    leaves = record.get("changed_leaves_per_stage", {})
    if leaves != {
        "buffer_loop_configs.GROUP2.ROW_LC.end": [1, 2],
        "buffer_config.buffer5.buf_end_row_addr": [0, 1],
    }:
        errors.append("D-buffer exact leaf delta differs")
    return errors


def _supply_negative_controls(manifest: dict[str, Any]) -> dict[str, Any]:
    base_record = copy.deepcopy(manifest["functional_configuration_fix"])
    cases: dict[str, dict[str, Any]] = {}
    for name, path, value in (
        ("restore_row_undersupply", "new_supply_bytes", 16),
        ("delete_tail_round_stage", "changed_stages", ["op_relocation_pad", "op_tail_mul"]),
        ("change_transaction_bytes", "transaction_bytes", 16),
        ("claim_address_change", "dram_loop_address_occurrence_changed", True),
    ):
        changed = copy.deepcopy(base_record)
        changed[path] = value
        cases[name] = changed
    return {
        name: {
            "failed_closed": bool(_supply_contract_errors(manifest, override=value)),
            "exit_code": 1 if _supply_contract_errors(manifest, override=value) else 0,
            "first_error": (
                _supply_contract_errors(manifest, override=value)[0]
                if _supply_contract_errors(manifest, override=value)
                else None
            ),
        }
        for name, value in cases.items()
    }


def _runtime_feature_e2e(
    members: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    root = f"{INSTALL_NAME}/"
    runner = members[root + "PREPARE_AND_RUN.sh"].decode(errors="replace")
    observer = members[root + "tb_probe/native_return_observer.svh"].decode(
        errors="replace"
    )
    allowlist = {
        str(item["target_path"]) for item in manifest["return_allowlist"]
    }
    checks = {
        "sim_argv_enable": "+RETURN_OBSERVER" in runner,
        "compile_incdir": "+incdir+$package_root/tb_probe" in runner,
        "compile_macro": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner,
        "time0_marker": (
            "# Native NDP return observer v4" in observer
            and "grep -q 'Native NDP return observer'" in runner
        ),
        "feature_receipt_allowlisted": (
            "evidence/observer_binding.txt" in allowlist
            and "evidence/progress_contract.json" in allowlist
        ),
        "runtime_log_allowlisted": "runs/return_observer.log" in allowlist,
        "canonical_return_allowlisted": (
            "evidence/CANONICAL_PROGRESS_DECISION.json" in allowlist
        ),
        "signal_trap_collection": all(
            f"trap 'signal_name={signal};" in runner
            for signal in ("HUP", "INT", "TERM")
        ),
    }
    controls = {
        "delete_runtime_enable": "+RETURN_OBSERVER" not in runner.replace(
            "+RETURN_OBSERVER", "", 1
        ),
        "delete_time0_marker": "# Native NDP return observer v4"
        not in observer.replace("# Native NDP return observer v4", "", 1),
        "delete_feature_receipt": (
            "evidence/observer_binding.txt"
            not in (allowlist - {"evidence/observer_binding.txt"})
        ),
        "delete_return_target": (
            "runs/return_observer.log"
            not in (allowlist - {"runs/return_observer.log"})
        ),
    }
    return {
        "passed": all(checks.values()) and all(controls.values()),
        "checks": checks,
        "four_negative_controls": {
            name: {"failed_closed": passed, "exit_code": 1 if passed else 0}
            for name, passed in controls.items()
        },
    }


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    _configure_base()
    original = base._workload_equivalence
    base._workload_equivalence = _workload_equivalence
    try:
        report = v11.validate_final_zip(write_report=False)
    finally:
        base._workload_equivalence = original
    members, manifest = _load_zip(ZIP_PATH, INSTALL_NAME)
    native = _native_chain_checks(members)
    supply_proof = validate_d_buffer_supply(build_configs(ROOT))
    supply_errors = _supply_contract_errors(manifest)
    supply_negatives = _supply_negative_controls(manifest)
    feature = _runtime_feature_e2e(members, manifest)

    v14.INSTALL_NAME = INSTALL_NAME
    v14.INSTRUCTIONS = PIPELINE / "instructions_explained.txt"
    preload_errors = v14._preload_errors(members, manifest)
    preload_negatives = v14._preload_negative_controls(members, manifest)
    runtime = members[
        f"{INSTALL_NAME}/package_tools/qlinearadd_node0007_server_runtime.py"
    ].decode(errors="replace")
    report["checks"].update(
        {
            "manifest_identity": (
                manifest.get("install_name") == INSTALL_NAME
                and manifest.get("claim") == "CONFIG_ONLY_CORRECTNESS_BASELINE"
                and manifest.get("functional_rtl_modified") is False
                and manifest.get("server_rtl_entries") == 0
            ),
            "d_buffer_supply_proof": (
                supply_proof["valid"] and not supply_errors
            ),
            "fresh_empty_mapping_native_chain": native["valid"],
            "six_config_preloads_bound": not preload_errors,
            "manifest_driven_preload_result_gate": (
                "expected_preload_count = int(" in runtime
                and "expected_sca_preload_count" in runtime
                and r"JSON config:\s*85\s+matrices loaded" not in runtime
            ),
            "diagnostic_feature_runtime_enable_end_to_end": feature["passed"],
            "d_buffer_negative_controls": all(
                item["failed_closed"] for item in supply_negatives.values()
            ),
            "preload_negative_controls": all(
                item["failed_closed"] for item in preload_negatives.values()
            ),
        }
    )
    errors = [name for name, passed in report["checks"].items() if not passed]
    errors.extend(f"d_buffer: {error}" for error in supply_errors)
    errors.extend(f"native_chain: {error}" for error in native["errors"])
    errors.extend(f"config_preload: {error}" for error in preload_errors)
    all_negatives = (
        report.get("all_required_negative_controls_fail_closed") is True
        and all(item["failed_closed"] for item in supply_negatives.values())
        and all(item["failed_closed"] for item in preload_negatives.values())
        and all(
            item["failed_closed"]
            for item in feature["four_negative_controls"].values()
        )
    )
    if not all_negatives:
        errors.append("all_required_negative_controls_fail_closed")
    report.update(
        {
            "schema": (
                "qlinearadd-node0007-d-buffer-supply-"
                "final-zip-self-audit-v1"
            ),
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if not errors
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "errors": errors,
            "error_count": len(errors),
            "all_required_negative_controls_fail_closed": all_negatives,
            "d_buffer_supply_proof": supply_proof,
            "d_buffer_supply_negative_controls": supply_negatives,
            "fresh_native_chain": native,
            "config_preload_errors": preload_errors,
            "config_preload_negative_controls": preload_negatives,
            "diagnostic_feature_runtime_enable_end_to_end": feature,
            "package_class": manifest.get("package_class"),
            "functional_fix": True,
            "functional_fix_scope": "D_BUFFER_SUPPLY_CONSERVATION",
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "config_numeric_analysis_repeated": False,
            "expected_return": f"{INSTALL_NAME}_return.zip",
            "expected_return_sidecar": (
                "generated server-side; user upload optional under "
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
            ),
        }
    )
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        build.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(
                    ROOT
                ).as_posix(),
                "final_self_audit_report_sha256": sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate_final_zip()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
