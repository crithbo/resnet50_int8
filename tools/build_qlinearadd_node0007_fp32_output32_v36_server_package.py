from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records


PKG = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_qadd_n7_crow32_v35"
TARGET_NAME = "r5_qadd_n7_cout32_v36"
SOURCE = PKG / SOURCE_NAME
SOURCE_ZIP = PKG / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829"
PIPELINE = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36/execplan/pipeline_output"
)
BUILD_RECEIPT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36/build_receipt.json"
)
LOCAL_VALIDATION = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36/validation.json"
)
RETURN_REPORT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v35-return-analysis/report.json"
)
TARGET = PKG / TARGET_NAME
ZIP = PKG / f"{TARGET_NAME}.zip"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common": ROOT / ".agents/rules/算子配置规则.md",
    "hardware": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}
ALIASES = {
    "agent": "agent",
    "index": "index",
    "generation_index": "index",
    "server": "server",
    "server_package": "server",
    "common": "common",
    "common_operator": "common",
    "hardware": "hardware",
    "hardware_fields": "hardware",
    "qadd": "qadd",
    "qlinearadd": "qadd",
    "tail": "tail",
    "exact_tail": "tail",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def namespace_sca(value: dict) -> dict:
    result = json.loads(json.dumps(value))
    for record in result.values():
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            continue
        path = record["path"].replace("\\", "/")
        if path.startswith("install/"):
            record["path"] = f"install/cfg_pkg/{TARGET_NAME}/{path}"
    return result


def projected_paths(out: Path, manifest: dict) -> list[str]:
    result = {f"{TARGET_NAME}/{path}" for path in manifest["files"]}
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        value = json.loads((out / "workload/runtime" / name).read_text(encoding="utf-8"))
        for record in value.values():
            if isinstance(record, dict) and isinstance(record.get("path"), str):
                result.add(record["path"])
    result.update(
        {
            f"run_{TARGET_NAME}/sim_results/return_observer/return_observer.log",
            f"evidence_{TARGET_NAME}/CANONICAL_PROGRESS_DECISION.json",
            f"evidence_{TARGET_NAME}/actual_simulator_argv.txt",
            f"{TARGET_NAME}_return/RETURN_MANIFEST.json",
            f"{TARGET_NAME}_return.zip.sha256",
        }
    )
    return sorted(result)


def materialize(parent: Path) -> Path:
    out = parent / TARGET_NAME
    shutil.copytree(SOURCE, out)
    for path in out.rglob("*"):
        if not path.is_file() or path.name == "TEST_PACKAGE_MANIFEST.json":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, TARGET_NAME),
                encoding="utf-8",
                newline="\n",
            )

    runtime = out / "workload/runtime"
    install = runtime / "install"
    for path in [install / "execplan.txt", *install.glob("execplan_*.txt")]:
        path.unlink()
    shutil.rmtree(install / "cfg_pkg")
    (install / "cfg_pkg").mkdir()
    shutil.copy2(PIPELINE / "install/execplan.txt", install / "execplan.txt")
    for path in (PIPELINE / "install").glob("execplan_*.txt"):
        shutil.copy2(path, install / path.name)
    for path in (PIPELINE / "install/cfg_pkg").glob("*"):
        shutil.copy2(path, install / "cfg_pkg" / path.name)
    sca = json.loads((PIPELINE / "sca_cfg.json").read_text(encoding="utf-8"))
    sca_d = {
        key: value
        for key, value in json.loads(
            (PIPELINE / "sca_cfg_D.json").read_text(encoding="utf-8")
        ).items()
        if key.startswith("op_fp32_add_matrixD_slice")
    }
    if len(sca_d) != 28:
        raise ValueError("FP32 stage-local D exact-set differs")
    write_json(runtime / "sca_cfg.json", namespace_sca(sca))
    write_json(runtime / "sca_cfg_D.json", namespace_sca(sca_d))

    readme = out / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\nV36 changes only op_fp32_add GA output population: it adds native "
        "PE10/PE12/PE30/PE32 so eight 4-byte lanes form one 32-byte Buffer5 "
        "row. The v35 row-paired inputs, workload, observer and timeout are frozen.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET_NAME
    manifest["claim"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_fp32_output32_v36_server_package.py"
    )
    manifest["provenance"]["successor_reason"] = (
        "v35 return proves four configured GA PEs supply 16B while Buffer5 and "
        "MSE4 require one accepted 32B row"
    )
    manifest["source_assets"]["v35_source_zip"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_SHA,
        "immutable": True,
        "runtime_identity": "QUARANTINED_AFTER_V35_OUTPUT_SUPPLY_HANG",
    }
    manifest["source_assets"]["v35_return_analysis"] = {
        "path": RETURN_REPORT.relative_to(ROOT).as_posix(),
        "sha256": sha(RETURN_REPORT),
    }
    manifest["source_assets"]["fp32_output32_v36_build_receipt"] = {
        "path": BUILD_RECEIPT.relative_to(ROOT).as_posix(),
        "sha256": sha(BUILD_RECEIPT),
    }
    manifest["source_assets"]["fp32_output32_v36_validation"] = {
        "path": LOCAL_VALIDATION.relative_to(ROOT).as_posix(),
        "sha256": sha(LOCAL_VALIDATION),
    }
    manifest["fp32_output32_correction"] = {
        "stage": "op_fp32_add",
        "added_pe_names": ["PE10", "PE12", "PE30", "PE32"],
        "final_pe_names": [
            "PE00",
            "PE02",
            "PE10",
            "PE12",
            "PE20",
            "PE22",
            "PE30",
            "PE32",
        ],
        "bytes_per_pe": 4,
        "producer_bytes": 32,
        "buffer5_banks": 8,
        "buffer5_required_bytes": 32,
        "old_boundary": "GA_OUTPUT_WITHOUT_BUFFER5_ACCEPTED_WRITE",
        "checkpoint_retained": (
            "GA output -> Buffer5 accepted write -> MSE4 request/wdata -> "
            "natural stage finish -> 28 stage-local D"
        ),
        "address_changed": False,
        "numeric_changed": False,
        "workload_changed": False,
        "golden_changed": False,
        "functional_rtl_modified": False,
    }
    manifest["frozen_semantics"].update(
        {
            "numeric": True,
            "W3_order": True,
            "six_qparams": True,
            "exact_uint8_tail": True,
            "workload_values": True,
            "golden_values": True,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
        }
    )
    receipts = manifest["rule_receipts"]
    for alias, canonical in ALIASES.items():
        path = RULES[canonical]
        record = dict(receipts.get(alias, {}))
        record.update(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha(path),
                "current_match": True,
            }
        )
        receipts[alias] = record
    applicable_server = set(receipts["server"].get("applicable_rule_ids", []))
    applicable_server.update(
        {
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001",
        }
    )
    receipts["server"]["applicable_rule_ids"] = sorted(applicable_server)
    receipts["server_package"]["applicable_rule_ids"] = sorted(applicable_server)
    applicable_common = set(receipts["common"].get("applicable_rule_ids", []))
    applicable_common.update(
        {
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
        }
    )
    receipts["common"]["applicable_rule_ids"] = sorted(applicable_common)
    receipts["common_operator"]["applicable_rule_ids"] = sorted(applicable_common)
    manifest["release_gate_matrix"] = {
        "schema": "server-package-release-gate-matrix-v1",
        "single_machine_record": True,
        "gates": {
            "package_bootstrap_path_runtime_D": {
                "applicability": "required",
                "reason": "fresh identity and changed cfg payload",
            },
            "runner_compile_finalizer": {
                "applicability": "required",
                "reason": "fresh runner identity substitution",
            },
            "package_local_HDL": {
                "applicability": "receipt_reuse",
                "reason": "all HDL members byte-equal to v35",
            },
            "materialized_config": {
                "applicability": "required",
                "reason": "four GA PE leaves and config length changed",
                "rules": [
                    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
                    "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
                    "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
                ],
            },
            "observer_canonical": {
                "applicability": "receipt_reuse",
                "reason": "observer and predicate bytes unchanged from v35",
            },
            "return_result": {
                "applicability": "required",
                "reason": "fresh identity must preserve exact-set and conjunction",
            },
            "numeric_W3_golden": {
                "applicability": "record_only",
                "reason": "byte-equal frozen semantic assets",
            },
            "unrelated_RTL": {
                "applicability": "record_only",
                "reason": "no package RTL or functional RTL change",
            },
        },
    }
    manifest["final_zip_rule_self_audit"] = {
        "required": True,
        "status": "PENDING_POST_BUILD_DIRECT_FINAL_ZIP_AUDIT",
    }
    manifest["files"] = file_records(out, exclude_manifest=True)
    projections = projected_paths(out, manifest)
    inner = list(manifest["files"])
    manifest["path_length_budget"]["projected_relative_paths"] = projections
    manifest["path_length_budget"]["max_projected_relative_path_chars"] = max(
        map(len, projections)
    )
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = (
        manifest["path_length_budget"]["declared_target_root_max_chars"]
        + 1
        + max(map(len, projections))
    )
    manifest["path_length_budget"]["max_zip_member_chars"] = max(
        len(TARGET_NAME + "/" + path)
        for path in [*inner, "TEST_PACKAGE_MANIFEST.json"]
    )
    manifest["path_length_budget"]["max_inner_suffix_chars"] = max(map(len, inner))
    manifest["path_length_budget"]["max_inner_depth"] = max(
        path.count("/") + 1 for path in inner
    )
    write_json(manifest_path, manifest)
    return out


def main() -> int:
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise ValueError("frozen v35 source ZIP differs")
    if TARGET.exists() or ZIP.exists():
        raise ValueError("fresh v36 package identity already exists")
    required = [PIPELINE, BUILD_RECEIPT, LOCAL_VALIDATION, RETURN_REPORT]
    if any(not path.exists() for path in required):
        raise FileNotFoundError("v36 local inputs incomplete")
    validation = json.loads(LOCAL_VALIDATION.read_text(encoding="utf-8"))
    if not validation.get("valid"):
        raise ValueError("v36 local validation is not valid")
    with tempfile.TemporaryDirectory(prefix="qadd-v36-a-") as first, tempfile.TemporaryDirectory(
        prefix="qadd-v36-b-"
    ) as second:
        package_a = materialize(Path(first))
        package_b = materialize(Path(second))
        zip_a = Path(first) / f"{TARGET_NAME}.zip"
        zip_b = Path(second) / f"{TARGET_NAME}.zip"
        deterministic_zip(package_a, zip_a)
        deterministic_zip(package_b, zip_b)
        if sha(zip_a) != sha(zip_b):
            raise ValueError("deterministic double build differs")
        shutil.copytree(package_a, TARGET)
        shutil.copy2(zip_a, ZIP)
    sidecar = Path(str(ZIP) + ".sha256")
    sidecar.write_text(f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n")
    print(
        json.dumps(
            {
                "zip": str(ZIP),
                "bytes": ZIP.stat().st_size,
                "sha256": sha(ZIP),
                "sidecar_sha256": sha(sidecar),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
