from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as ingress
from tools import validate_qlinearadd_node0007_split_workloads_v25_server_packages as split
from tools import validate_qlinearadd_node0007_split_c_ingress_v28_server_package as v28
from tools import validate_qlinearadd_node0007_split_c_pairmatrix_v29_server_package as v29
from tools import validate_qlinearadd_node0007_fp32_rowpair_v35_server_package as v35


NAME = "r5_qadd_n7_cout32_v36"
SOURCE = "r5_qadd_n7_crow32_v35"
ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    f"{NAME}.zip"
)
SOURCE_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    f"{SOURCE}.zip"
)
LOCAL = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36"
)
PIPELINE = LOCAL / "execplan/pipeline_output"
BUILD = LOCAL / "build_receipt.json"
LOCAL_VALIDATION = LOCAL / "validation.json"
HDL = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36-server-package/"
    "hdl_scope_revalidation.json"
)
OUT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-output32-v36-server-package/"
    "final_zip_self_audit.json"
)
BITSTREAM_MEMBER = (
    "workload/runtime/install/cfg_pkg/"
    "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin"
)
LOCAL_BITSTREAM = (
    PIPELINE
    / "install/cfg_pkg/"
    "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin"
)
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


def normalized_changes(
    files: dict[str, bytes], source: dict[str, bytes]
) -> dict:
    expected = {
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        BITSTREAM_MEMBER,
        "workload/runtime/install/execplan.txt",
        "workload/runtime/install/execplan_op_fp32_add.txt",
    }
    changed = []
    for path in sorted(set(files) | set(source)):
        if path not in files or path not in source:
            changed.append(path)
            continue
        normalized = source[path].replace(SOURCE.encode(), NAME.encode())
        if normalized != files[path]:
            changed.append(path)
    hdl_members = sorted(
        path
        for path in files
        if path.endswith((".sv", ".svh", ".v", ".vh"))
    )
    return {
        "changed_members": changed,
        "expected_changed_members": sorted(expected),
        "exact_changed_set": set(changed) == expected,
        "hdl_members": [
            {
                "path": path,
                "target_sha256": hashlib.sha256(files[path]).hexdigest(),
                "source_sha256": hashlib.sha256(source[path]).hexdigest(),
                "byte_equal": files[path] == source[path],
            }
            for path in hdl_members
        ],
        "all_hdl_byte_equal": bool(hdl_members)
        and all(files[path] == source[path] for path in hdl_members),
    }


def config_contract(files: dict[str, bytes], manifest: dict) -> dict:
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    validation = json.loads(LOCAL_VALIDATION.read_text(encoding="utf-8"))
    correction = manifest["fp32_output32_correction"]
    package_bitstream = files[BITSTREAM_MEMBER]
    package_execplan = files["workload/runtime/install/execplan.txt"]
    local_execplan = (PIPELINE / "install/execplan.txt").read_bytes()
    proof = build["output32_proof"]
    checks = {
        "local_validation_valid": validation["valid"] is True
        and validation["errors"] == [],
        "all_local_negatives_fail_closed": all(
            item["failed_closed"]
            for item in validation["negative_controls"].values()
        ),
        "package_bitstream_exact": package_bitstream
        == LOCAL_BITSTREAM.read_bytes(),
        "package_execplan_exact": package_execplan == local_execplan,
        "eight_unique_pe_lanes": correction["final_pe_names"]
        == ["PE00", "PE02", "PE10", "PE12", "PE20", "PE22", "PE30", "PE32"]
        and len(set(correction["final_pe_names"])) == 8,
        "producer_32B": correction["bytes_per_pe"] == 4
        and correction["producer_bytes"] == 32,
        "buffer5_requires_32B": correction["buffer5_banks"] == 8
        and correction["buffer5_required_bytes"] == 32,
        "causal_ledger_exact": proof["valid"] is True
        and proof["causal_transaction_ledger"]["producer_exact_byte_set"]
        == list(range(32))
        and proof["causal_transaction_ledger"]["consumer_required_byte_set"]
        == list(range(32)),
        "boundary_microtrace_exact": (
            [item["point"] for item in proof["boundary_microtrace"]["events"]]
            == [0, 4, 12, 16, 28, 32, 36]
            and [
                item["point"]
                for item in proof["boundary_microtrace"]["events"]
                if item["accepted"]
            ]
            == [32]
        ),
        "config_length_61_words": validation["config_length"][
            "source_64bit_word_count"
        ]
        == validation["config_length"]["programmed_load_config_length_64bit_words"]
        == 61,
        "transport_padding_classified": validation["config_length"][
            "physical_128bit_rows"
        ]
        == 31
        and validation["config_length"][
            "last_row_high_half_is_transport_padding"
        ]
        is True,
        "address_unchanged": correction["address_changed"] is False
        and validation["checks"]["address_byte_equal_receipt_reuse"] is True,
        "semantic_freeze": correction["numeric_changed"] is False
        and correction["workload_changed"] is False
        and correction["golden_changed"] is False
        and correction["functional_rtl_modified"] is False,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "build_receipt_sha256": sha(BUILD),
        "local_validation_sha256": sha(LOCAL_VALIDATION),
        "package_bitstream_sha256": hashlib.sha256(package_bitstream).hexdigest(),
        "package_execplan_sha256": hashlib.sha256(package_execplan).hexdigest(),
        "equation": "8 lanes * 4B = 32B = Buffer5 8 banks * 4B",
        "causal_transaction_ledger": proof["causal_transaction_ledger"],
        "boundary_microtrace": proof["boundary_microtrace"],
        "config_length": validation["config_length"],
        "negative_controls": validation["negative_controls"],
    }


def rule_receipts(manifest: dict) -> dict:
    records = manifest["rule_receipts"]
    result = {}
    for alias, canonical in ALIASES.items():
        record = records.get(alias, {})
        result[alias] = (
            record.get("sha256") == sha(RULES[canonical])
            and record.get("current_match") is True
        )
    result["server_applicability"] = all(
        rule_id in records["server"]["applicable_rule_ids"]
        for rule_id in (
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001",
        )
    )
    result["changed_config_rules"] = all(
        rule_id in records["common"]["applicable_rule_ids"]
        for rule_id in (
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
        )
    )
    return result


def release_matrix(manifest: dict) -> dict:
    matrix = manifest.get("release_gate_matrix", {})
    gates = matrix.get("gates", {})
    checks = {
        "single_record": matrix.get("single_machine_record") is True,
        "core_required": gates.get("package_bootstrap_path_runtime_D", {}).get(
            "applicability"
        )
        == "required",
        "runner_required": gates.get("runner_compile_finalizer", {}).get(
            "applicability"
        )
        == "required",
        "config_required": gates.get("materialized_config", {}).get(
            "applicability"
        )
        == "required",
        "return_required": gates.get("return_result", {}).get("applicability")
        == "required",
        "hdl_receipt_reuse": gates.get("package_local_HDL", {}).get(
            "applicability"
        )
        == "receipt_reuse",
        "observer_receipt_reuse": gates.get("observer_canonical", {}).get(
            "applicability"
        )
        == "receipt_reuse",
        "numeric_record_only": gates.get("numeric_W3_golden", {}).get(
            "applicability"
        )
        == "record_only",
    }
    return {"valid": all(checks.values()), "checks": checks, "record": matrix}


def main() -> int:
    if ZIP.stat().st_size != 26_181_302:
        raise ValueError("v36 ZIP byte count drift")
    if sha(ZIP) != "b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382":
        raise ValueError("v36 ZIP SHA drift")
    files, manifest = v28.load(ZIP, NAME)
    source_files, _ = v28.load(SOURCE_ZIP, SOURCE)
    hdl = json.loads(HDL.read_text(encoding="utf-8"))
    prior = (
        json.loads(OUT.read_text(encoding="utf-8"))
        if OUT.exists()
        else None
    )

    changes = normalized_changes(files, source_files)
    config = config_contract(files, manifest)
    receipts = rule_receipts(manifest)
    matrix = release_matrix(manifest)
    reusable_runtime_receipt = (
        isinstance(prior, dict)
        and prior.get("zip_sha256") == sha(ZIP)
        and prior.get("runner_control_flow", {}).get("all_passed") is True
        and prior.get("exit_term_finalizer", {}).get("all_passed") is True
        and prior.get("parser_controls", {}).get("valid") is True
        and all(
            item.get("failed_closed") is True
            for item in prior.get("observer_negative_controls", {}).values()
        )
    )
    if reusable_runtime_receipt:
        runner = prior["runner_control_flow"]
        finalizer = prior["exit_term_finalizer"]
        parser = prior["parser_controls"]
        observer_negatives = prior["observer_negative_controls"]
    else:
        v29.NAME = NAME
        v29.SOURCE = SOURCE
        split.runner_validator.INSTALL_NAME = NAME
        split.base.INSTALL_NAME = NAME
        runner = split.runner_controls(ZIP, NAME)
        ingress.INSTALL_NAME = NAME
        ingress.ZIP_PATH = ZIP
        ingress.SIDECAR_PATH = Path(str(ZIP) + ".sha256")
        ingress.runner_validator.INSTALL_NAME = NAME
        finalizer = ingress.exit_and_signal_finalizer_controls()
        parser = v29.parser_controls(
            ROOT
            / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}"
        )
        observer_negatives = v29.negative_controls(files)
    v35.NAME = NAME
    v35.base.ZIP = ZIP
    budget_valid = v35.budget_contract(files, manifest)
    budget_negatives = v35.budget_controls(files, manifest)
    sca_d = json.loads(files["workload/runtime/sca_cfg_D.json"])
    runtime_d = [
        value["path"]
        for value in sca_d.values()
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    ]
    runtime_d_present = [
        path
        for path in runtime_d
        if "workload/runtime/" + path.split(f"{NAME}/", 1)[-1] in files
    ]
    checks = {
        "manifest_identity": manifest["install_name"] == NAME,
        "inventory_exact": v28.inventory_ok(files, manifest),
        "source_v35_bound": manifest["source_assets"]["v35_source_zip"]["sha256"]
        == sha(SOURCE_ZIP),
        "diagnostic_claim": manifest["claim"]
        == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "changed_member_scope": changes["exact_changed_set"],
        "package_local_hdl_byte_equal": changes["all_hdl_byte_equal"],
        "materialized_config": config["valid"],
        "observer_contract": v29.contract_ok(files),
        "observer_negatives": all(
            item["failed_closed"] for item in observer_negatives.values()
        ),
        "safe_compile_and_identity": runner["all_passed"],
        "exit_term_finalizer": finalizer["all_passed"],
        "canonical_parser": parser["valid"],
        "hdl_scope": hdl.get("valid") is True
        and hdl.get("all_negative_controls_fail_closed") is True
        and hdl["zip"]["sha256_after"] == sha(ZIP)
        and hdl["actual_consumer_coverage"]["uncovered_expression_total"] == 0,
        "rule_receipts_current": all(receipts.values()),
        "release_gate_matrix": matrix["valid"],
        "path_length_budget": budget_valid,
        "path_length_negatives": all(
            item["failed_closed"] for item in budget_negatives.values()
        ),
        "28_stage_local_D": len(sca_d) == 28,
        "runtime_D_absent": not runtime_d_present,
        "sidecar": Path(str(ZIP) + ".sha256").read_text(
            encoding="ascii"
        ).strip()
        == f"{sha(ZIP)}  {ZIP.name}",
    }
    errors = [key for key, value in checks.items() if not value]
    report = {
        "schema": "qlinearadd-node0007-fp32-output32-v36-final-zip-self-audit",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "QUARANTINED",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "install_name": NAME,
        "zip_bytes": ZIP.stat().st_size,
        "zip_sha256": sha(ZIP),
        "checks": checks,
        "rule_receipt_checks": receipts,
        "rule_receipts": {
            key: {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha(path),
            }
            for key, path in RULES.items()
        },
        "release_gate_matrix": matrix,
        "changed_member_scope": changes,
        "materialized_config_gate": config,
        "runner_control_flow": runner,
        "runtime_gate_receipt_reused_from_exact_zip_audit": reusable_runtime_receipt,
        "exit_term_finalizer": finalizer,
        "parser_controls": parser,
        "observer_negative_controls": observer_negatives,
        "package_local_hdl_gate": hdl,
        "path_length_budget": manifest["path_length_budget"],
        "path_length_negative_controls": budget_negatives,
        "formal_D_scope": {
            "expected": 28,
            "runtime_present_before_run": len(runtime_d_present),
            "runtime_D_absent": not runtime_d_present,
            "claim": "split-C op_fp32_add stage-local outputs only",
        },
        "claim_boundary": (
            "v36 corrects only FP32 add GA output supply from 16B to one 32B "
            "Buffer5 row; server return must prove accepted Buffer5 write, "
            "MSE4 wdata, natural split-C terminal and 28 stage-local D. No "
            "full-chain E3/E4/E5 claim."
        ),
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "golden_recomputed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "errors": errors,
                "zip_sha256": report["zip_sha256"],
                "report_sha256": sha(OUT),
            },
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
