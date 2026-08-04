from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_rate_limited_clock_v13 as v13
from tools import validate_qlinearadd_node0007_first_request_chain_v10 as base


INSTALL_NAME = "r5_qadd_n7_cfgpreload_v14"
SOURCE_NAME = "r5_qadd_n7_obsrate_v13"
ZIP_SHA256 = "78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282"
SOURCE_ZIP_SHA256 = "fe65a96ad6365872f2f004f6702b197f33fc6b5fcd4397df716714f443b28858"
SERVER_RULE_SHA256 = "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-config-preload-v14"
    / "report.json"
)
INSTRUCTIONS = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-nested-lc-full-e2-v4"
    / "execplan/pipeline_output/instructions_explained.txt"
)
EXPECTED_STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
    "op_tail_mul",
    "op_tail_round",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _configure_v13() -> None:
    v13.INSTALL_NAME = INSTALL_NAME
    v13.SOURCE_NAME = SOURCE_NAME
    v13.ZIP_SHA256 = ZIP_SHA256
    v13.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    v13.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    v13.ZIP_PATH = ZIP_PATH
    v13.SIDECAR_PATH = SIDECAR_PATH
    v13.SOURCE_ZIP = SOURCE_ZIP
    v13.BUILD_RECEIPT = BUILD_RECEIPT
    v13.REPORT_PATH = REPORT_PATH


def _load_zip(
    path: Path, root_name: str
) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        members = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
        }
    root = f"{root_name}/"
    manifest = json.loads(members[root + "TEST_PACKAGE_MANIFEST.json"])
    return members, manifest


def _precise_workload_equivalence(
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
    errors: list[str] = []
    if set(old) != set(new):
        errors.append("workload runtime exact-set differs")
    for name in sorted(set(old) & set(new)):
        if name == "sca_cfg.json":
            old_sca = json.loads(old[name])
            new_sca = json.loads(
                new[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
            )
            added = {
                key: new_sca.pop(key, None)
                for key in (
                    "op_a_dequant_config",
                    "op_b_dequant_config",
                    "op_relocation_pad_config",
                    "op_fp32_add_config",
                    "op_tail_mul_config",
                    "op_tail_round_config",
                )
            }
            if any(value is None for value in added.values()):
                errors.append("one or more config preload objects are absent")
            if new_sca != old_sca:
                errors.append("non-preload SCA content differs")
            continue
        normalized = new[name].replace(
            INSTALL_NAME.encode(), SOURCE_NAME.encode()
        )
        if normalized != old[name]:
            errors.append(f"frozen workload changed: {name}")
    return {
        "valid": not errors,
        "file_count": len(old),
        "allowed_delta": "six SCA config preload objects only",
        "errors": errors,
        "missing": sorted(set(old) - set(new)),
        "extra": sorted(set(new) - set(old)),
    }


def _load_config_contract() -> dict[str, dict[str, Any]]:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    pattern = re.compile(
        r"<([01]{64})>\s+Load_Config for operator (\w+) .*?"
        r"config_length_bin=([01]+), ddr_config_addr_bin=([01]+),"
    )
    found: dict[str, dict[str, Any]] = {}
    for command, stage, length_bits, address_bits in pattern.findall(text):
        found[stage] = {
            "command_64b": command,
            "config_length_64b": int(length_bits, 2),
            "ddr_config_addr": int(address_bits, 2),
            "base_addr": f"0x{int(address_bits, 2) << 10:08X}",
        }
    if tuple(found) != EXPECTED_STAGES:
        raise ValueError(f"Load_Config stage order differs: {tuple(found)}")
    return found


def _preload_errors(
    members: dict[str, bytes],
    manifest: dict[str, Any],
    *,
    contract_override: dict[str, Any] | None = None,
    sca_override: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    root = f"{INSTALL_NAME}/"
    sca = (
        copy.deepcopy(sca_override)
        if sca_override is not None
        else json.loads(
            members[root + "workload/runtime/sca_cfg.json"]
        )
    )
    contract = (
        copy.deepcopy(contract_override)
        if contract_override is not None
        else copy.deepcopy(manifest.get("config_preload_contract"))
    )
    if not isinstance(contract, dict):
        return ["config preload contract absent"]
    entries = contract.get("entries")
    if (
        contract.get("expected_sca_preload_count") != 91
        or contract.get("source_preload_count") != 85
        or contract.get("added_config_preload_count") != 6
        or not isinstance(entries, list)
        or len(entries) != 6
    ):
        errors.append("config preload contract cardinality differs")
        entries = entries if isinstance(entries, list) else []

    load_contract = _load_config_contract()
    execplan = members[
        root + "workload/runtime/install/execplan.txt"
    ].decode("ascii")
    sca_objects = {
        key: value
        for key, value in sca.items()
        if isinstance(value, dict) and "path" in value
    }
    if len(sca_objects) != 91:
        errors.append(f"SCA preload exact count differs: {len(sca_objects)}")
    seen_stages: set[str] = set()
    for record in entries:
        if not isinstance(record, dict):
            errors.append("config preload record is not an object")
            continue
        stage = str(record.get("stage", ""))
        key = str(record.get("sca_key", ""))
        path = str(record.get("path", ""))
        expected = load_contract.get(stage)
        if expected is None or stage in seen_stages:
            errors.append(f"config preload stage differs: {stage}")
            continue
        seen_stages.add(stage)
        if execplan.count(expected["command_64b"]) != 1:
            errors.append(f"Load_Config command binding differs: {stage}")
        if record.get("base_addr") != expected["base_addr"]:
            errors.append(f"Load_Config/SCA base differs: {stage}")
        if record.get("config_length_64b") != expected["config_length_64b"]:
            errors.append(f"Load_Config length differs: {stage}")
        if sca.get(key) != {
            "base_addr": record.get("base_addr"),
            "path": path,
        }:
            errors.append(f"SCA config object differs: {stage}")
        payload_name = root + "workload/runtime/" + path.removeprefix(
            f"install/cfg_pkg/{INSTALL_NAME}/"
        )
        payload = members.get(payload_name)
        if payload is None:
            errors.append(f"config payload absent: {stage}")
            continue
        lines = payload.splitlines()
        if (
            any(len(line) != 128 or set(line) - {48, 49} for line in lines)
            or len(lines) * 2 != expected["config_length_64b"]
        ):
            errors.append(f"config payload line/length differs: {stage}")
        if record.get("line_count") != len(lines):
            errors.append(f"config payload declared line count differs: {stage}")
        digest = hashlib.sha256(payload).hexdigest()
        if record.get("sha256") != digest:
            errors.append(f"config payload hash differs: {stage}")
        if int(record.get("base_addr", "0"), 16) + len(lines) * 16 > int(
            "0x00D2C800", 16
        ):
            errors.append(f"config payload overlaps execplan: {stage}")
    if seen_stages != set(EXPECTED_STAGES):
        errors.append("config preload stage exact-set differs")
    return errors


def _preload_negative_controls(
    members: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    sca = json.loads(
        members[
            f"{INSTALL_NAME}/workload/runtime/sca_cfg.json"
        ]
    )
    contract = copy.deepcopy(manifest["config_preload_contract"])
    cases: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for record in contract["entries"]:
        changed_sca = copy.deepcopy(sca)
        changed_sca.pop(record["sca_key"])
        cases[f"delete_{record['stage']}_sca_preload"] = (
            copy.deepcopy(contract),
            changed_sca,
        )
    wrong_base = copy.deepcopy(contract)
    wrong_base["entries"][0]["base_addr"] = "0x00D2B400"
    cases["wrong_load_config_base"] = (wrong_base, copy.deepcopy(sca))
    wrong_hash = copy.deepcopy(contract)
    wrong_hash["entries"][0]["sha256"] = "0" * 64
    cases["wrong_config_payload_hash"] = (wrong_hash, copy.deepcopy(sca))
    wrong_length = copy.deepcopy(contract)
    wrong_length["entries"][0]["line_count"] += 1
    cases["wrong_config_payload_length"] = (wrong_length, copy.deepcopy(sca))
    controls: dict[str, Any] = {}
    for name, (changed_contract, changed_sca) in cases.items():
        errors = _preload_errors(
            members,
            manifest,
            contract_override=changed_contract,
            sca_override=changed_sca,
        )
        controls[name] = {
            "failed_closed": bool(errors),
            "exit_code": 1 if errors else 0,
            "first_error": errors[0] if errors else None,
        }
    return controls


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    _configure_v13()
    original = base._workload_equivalence
    base._workload_equivalence = _precise_workload_equivalence
    try:
        report = v13.validate_final_zip(write_report=False)
    finally:
        base._workload_equivalence = original
    members, manifest = _load_zip(ZIP_PATH, INSTALL_NAME)
    preload_errors = _preload_errors(members, manifest)
    negatives = _preload_negative_controls(members, manifest)
    preload_checks = {
        "load_config_to_sca_preload_binding": not preload_errors,
        "config_preload_negative_controls": all(
            item["failed_closed"] for item in negatives.values()
        ),
        "config_preload_runtime_gate_embedded": (
            b"config preload contract differs"
            in members[
                f"{INSTALL_NAME}/package_tools/"
                "qlinearadd_node0007_server_runtime.py"
            ]
        ),
    }
    report["checks"].update(preload_checks)
    report["checks"]["manifest_identity"] = (
        manifest.get("install_name") == INSTALL_NAME
        and manifest.get("claim") == "CONFIG_ONLY_CORRECTNESS_BASELINE"
        and manifest.get("functional_rtl_modified") is False
        and manifest.get("server_rtl_entries") == 0
    )
    report["checks"]["functional_claim_boundary"] = (
        manifest.get("claim") == "CONFIG_ONLY_CORRECTNESS_BASELINE"
        and manifest.get("package_class")
        == "FUNCTIONAL_CONFIG_MATERIALIZATION_FIX_WITH_DEFAULT_DIAGNOSTICS"
        and "no functional RTL change"
        in manifest.get("claim_boundary", "")
    )
    errors = [name for name, passed in report["checks"].items() if not passed]
    errors.extend(f"config_preload: {error}" for error in preload_errors)
    report.update(
        {
            "schema": (
                "qlinearadd-node0007-config-preload-"
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
            "config_preload_errors": preload_errors,
            "config_preload_negative_controls": negatives,
            "all_required_negative_controls_fail_closed": (
                report.get("all_required_negative_controls_fail_closed") is True
                and all(item["failed_closed"] for item in negatives.values())
            ),
            "load_config_evidence": {
                "instructions_path": INSTRUCTIONS.relative_to(ROOT).as_posix(),
                "instructions_sha256": sha256(INSTRUCTIONS),
                "decoded": _load_config_contract(),
            },
            "source_v13_status": "QUARANTINED_MISSING_SCA_CONFIG_PRELOADS",
            "expected_return": f"{INSTALL_NAME}_return.zip",
            "expected_return_sidecar": f"{INSTALL_NAME}_return.zip.sha256",
            "package_class": manifest.get("package_class"),
            "functional_fix": True,
            "functional_fix_scope": "SCA_CONFIG_PRELOAD_MATERIALIZATION_ONLY",
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "config_numeric_analysis_repeated": False,
        }
    )
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
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
                "final_self_audit_report": REPORT_PATH.relative_to(ROOT).as_posix(),
                "final_self_audit_report_sha256": sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
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
