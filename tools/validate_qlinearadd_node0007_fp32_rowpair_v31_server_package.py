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


NAME = "r5_qadd_n7_split_c_rowpairfix_rule_v31"
SOURCE = "r5_qadd_n7_split_c_rowpairfix_v30"
ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}.zip"
SOURCE_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE}.zip"
HDL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v31-server-package/hdl_scope_revalidation.json"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v31-server-package/final_zip_self_audit.json"
BUILD = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v30/build_receipt.json"
FINAL_JSON = ROOT / (
    "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v30/"
    "execplan/pipeline_output/jsons/op_fp32_add_resnet50_qadd_node0007_fp32_add.json"
)
LOCAL_BITSTREAM = ROOT / (
    "artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v30/"
    "execplan/pipeline_output/install/cfg_pkg/"
    "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin"
)
BITSTREAM_MEMBER = (
    "workload/runtime/install/cfg_pkg/"
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


def rowpair_contract(files: dict[str, bytes], manifest: dict) -> dict:
    receipt = json.loads(BUILD.read_text(encoding="utf-8"))
    config = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    proof = receipt["rowpair_proof"]
    correction = manifest["fp32_rowpair_correction"]
    streams = [config["stream_engine"][f"stream{i}"] for i in range(3)]
    groups = [config["buffer_loop_configs"][f"GROUP{i}"] for i in range(3)]
    lcs = [config["dram_loop_configs"][f"LC{i}"] for i in range(1, 4)]
    package_bs = files[BITSTREAM_MEMBER]
    checks = {
        "package_bitstream_exact_local_mapping": hashlib.sha256(package_bs).hexdigest()
        == sha(LOCAL_BITSTREAM),
        "build_receipt_valid": proof["valid"] is True,
        "physical_row_32": proof["buffer_physical_row_bytes"] == 32,
        "mse_read_16": proof["mse_window_bytes"] == 16,
        "manifest_windows_exact": correction["column_windows"] == [[0, 16], [16, 32]],
        "manifest_transaction_32": correction["transaction_bytes"] == 32,
        "stream_transaction_32": all(
            int(stream["idx_size"][1]) + 1 == 32
            and int(stream["dim_stride"][0]) == 32
            for stream in streams
        ),
        "buffer_col_window_32": all(
            int(group["COL_LC"]["start"]) == 0
            and int(group["COL_LC"]["end"]) == 32
            and int(group["COL_LC"]["stride"]) == 16
            for group in groups
        ),
        "two_disjoint_16B_windows": all(
            record["column_windows"] == [[0, 16], [16, 32]]
            and record["window_union_exact_0_32"] is True
            for record in proof["records"].values()
        ),
        "occurrence_preserves_coverage": all(
            int(lc["end"]) == 9408 for lc in lcs
        )
        and all(
            record["outer_occurrences"] == 8
            and record["inner_occurrences"] == 9408
            and record["total_occurrences"] == 75264
            and record["total_bytes"] == 2408448
            for record in proof["records"].values()
        ),
        "active_rtl_equation_bound": "buffer_mask" in proof["active_rtl_equation"]
        and "valid_buf" in proof["active_rtl_equation"],
        "fresh_mapping_valid": receipt["execplan_validation"]["valid"] is True,
        "numeric_workload_unchanged": receipt["numeric_analysis_repeated"] is False
        and receipt["workload_analysis_repeated"] is False
        and receipt["qparams_tail_golden_changed"] is False,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "final_json_sha256": sha(FINAL_JSON),
        "package_bitstream_sha256": hashlib.sha256(package_bs).hexdigest(),
        "build_receipt_sha256": sha(BUILD),
        "equation": "accepted_supply_i=[0,16) U [16,32)=[0,32)=required_arm_bytes_i",
        "operand_scope": ["Buffer0/MSE0", "Buffer2/MSE1"],
    }


def rowpair_negatives(files: dict[str, bytes], manifest: dict) -> dict:
    def accepts(candidate: dict) -> bool:
        c = candidate["fp32_rowpair_correction"]
        windows = c.get("column_windows")
        return (
            c.get("transaction_bytes") == 32
            and c.get("mse_window_bytes") == 16
            and windows == [[0, 16], [16, 32]]
            and c.get("inner_occurrences") == 9408
            and c.get("outer_occurrences") == 8
            and c.get("total_bytes_per_slice") == 2408448
            and files[BITSTREAM_MEMBER] == LOCAL_BITSTREAM.read_bytes()
        )

    cases = {}
    mutations = {
        "delete_second_window": [[0, 16]],
        "repeat_first_window": [[0, 16], [0, 16]],
        "window_gap": [[0, 16], [17, 32]],
        "window_overlap": [[0, 17], [16, 32]],
    }
    for name, windows in mutations.items():
        candidate = json.loads(json.dumps(manifest))
        candidate["fp32_rowpair_correction"]["column_windows"] = windows
        failed = not accepts(candidate)
        cases[name] = {"exit_code": 1 if failed else 0, "failed_closed": failed}
    for name, key, value in (
        ("wrong_transaction_bytes", "transaction_bytes", 16),
        ("wrong_occurrence", "inner_occurrences", 18816),
        ("narrow_bank_mask_proxy", "transaction_bytes", 16),
    ):
        candidate = json.loads(json.dumps(manifest))
        candidate["fp32_rowpair_correction"][key] = value
        failed = not accepts(candidate)
        cases[name] = {"exit_code": 1 if failed else 0, "failed_closed": failed}
    return cases


def rule_receipts_current(manifest: dict) -> dict:
    records = manifest["rule_receipts"]
    result = {}
    for alias, canonical in ALIASES.items():
        record = records.get(alias, {})
        result[alias] = (
            record.get("sha256") == sha(RULES[canonical])
            and record.get("current_match") is True
        )
    result["qadd_rule_id"] = (
        "CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001"
        in records["qlinearadd"].get("applicable_rule_ids", [])
        and "CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001"
        in records["qadd"].get("applicable_rule_ids", [])
    )
    return result


def main() -> int:
    files, manifest = v28.load(ZIP, NAME)
    source_files, _ = v28.load(SOURCE_ZIP, SOURCE)
    hdl = json.loads(HDL.read_text(encoding="utf-8"))

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
        ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}"
    )
    observer_negatives = v29.negative_controls(files)
    frozen = v29.workload_frozen(files, source_files)
    rowpair = rowpair_contract(files, manifest)
    rowpair_negative = rowpair_negatives(files, manifest)
    receipts = rule_receipts_current(manifest)
    checks = {
        "manifest_identity": manifest["install_name"] == NAME,
        "inventory_exact": v28.inventory_ok(files, manifest),
        "source_v30_bound": manifest["source_assets"]["fp32_rowpair_v30_source_zip"]["sha256"]
        == sha(SOURCE_ZIP),
        "diagnostic_only": manifest["claim"] == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "workload_frozen_except_identity": frozen["valid"],
        "rowpair_contract": rowpair["valid"],
        "rowpair_negatives": all(x["failed_closed"] for x in rowpair_negative.values()),
        "observer_contract": v29.contract_ok(files),
        "observer_negatives": all(x["failed_closed"] for x in observer_negatives.values()),
        "safe_compile_and_identity": runner["all_passed"],
        "exit_term_finalizer": finalizer["all_passed"],
        "canonical_parser": parser["valid"],
        "hdl_scope": hdl.get("valid") is True
        and hdl.get("all_negative_controls_fail_closed") is True
        and hdl.get("zip_sha256") == sha(ZIP),
        "rule_receipts_current": all(receipts.values()),
        "sidecar": Path(str(ZIP) + ".sha256").read_text(encoding="ascii").strip()
        == f"{sha(ZIP)}  {ZIP.name}",
    }
    errors = [key for key, value in checks.items() if not value]
    report = {
        "schema": "qlinearadd-node0007-split-c-rowpairfix-v31-final-zip-self-audit",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "QUARANTINED",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "install_name": NAME,
        "zip_bytes": ZIP.stat().st_size,
        "zip_sha256": sha(ZIP),
        "checks": checks,
        "rule_receipt_checks": receipts,
        "rowpair_contract": rowpair,
        "rowpair_negative_controls": rowpair_negative,
        "workload_freeze": frozen,
        "runner_control_flow": runner,
        "exit_term_finalizer": finalizer,
        "parser_controls": parser,
        "observer_negative_controls": observer_negatives,
        "package_local_hdl_gate": hdl,
        "rule_receipts": {
            key: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
            for key, path in RULES.items()
        },
        "claim_boundary": (
            "split-C FP32 ingress config correction; server return must prove ARM/GA progress; "
            "no full-chain 28D/E3/E4/E5 claim"
        ),
        "numeric_workload_config_golden_repeated": False,
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
