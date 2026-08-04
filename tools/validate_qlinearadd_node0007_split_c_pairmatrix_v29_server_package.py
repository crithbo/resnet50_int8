from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as ingress
from tools import validate_qlinearadd_node0007_split_workloads_v25_server_packages as split
from tools import validate_qlinearadd_node0007_split_c_ingress_v28_server_package as v28


NAME = "r5_qadd_n7_split_c_pairmatrix_v29"
SOURCE = "r5_qadd_n7_split_c_ingress_v28"
ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}.zip"
SOURCE_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE}.zip"
HDL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-pairmatrix-v29-server-package/hdl_scope_revalidation.json"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-pairmatrix-v29-server-package/final_zip_self_audit.json"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "qadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def contract_ok(files: dict[str, bytes]) -> bool:
    runner = files["PREPARE_AND_RUN.sh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    tail = files["tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"].decode()
    pair = files["tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"].decode()
    parser = files["package_tools/qlinearadd_node0007_fp32_ingress_canonical_v29.py"].decode()
    required = (
        "+incdir+$package_root/tb_probe",
        "+define+NATIVE_RETURN_OBSERVER_ENABLE",
        "+RETURN_OBS_DEEP",
        "+QADD_FP32_INGRESS_OBSERVER",
        "QADD_FP32_INGRESS_OBSERVER_V19_TIME0",
        "fp32_ingress_feature_receipt.txt",
        "qlinearadd_node0007_fp32_ingress_canonical_v29.py",
    )
    return (
        all(x in runner for x in required)
        and native.count('`include "qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"') == 1
        and tail.count("qadd_ingress_stage_seq == 4") >= 2
        and "qadd_ingress_enabled &&\n            return_obs_active" not in tail
        and "MSE_INST[qpm_m]" in pair
        and "qadd_pair_idx_hs[m][c]++;" in pair
        and "qadd_pair_qwr_count[m]++;" in pair
        and "qadd_pair_ag_hs_count[m]++;" in pair
        and "QADD_PAIR_MATRIX" in pair
        and 'last_stage != 4' in parser
    )


def negative_controls(files: dict[str, bytes]) -> dict:
    cases = (
        ("delete_pair_include", "tb_probe/native_return_observer.svh", b'`include "qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"'),
        ("delete_incdir", "PREPARE_AND_RUN.sh", b"+incdir+$package_root/tb_probe"),
        ("delete_macro", "PREPARE_AND_RUN.sh", b"+define+NATIVE_RETURN_OBSERVER_ENABLE"),
        ("delete_feature", "PREPARE_AND_RUN.sh", b"+QADD_FP32_INGRESS_OBSERVER"),
        ("delete_time0", "PREPARE_AND_RUN.sh", b"QADD_FP32_INGRESS_OBSERVER_V19_TIME0"),
        ("delete_receipt", "PREPARE_AND_RUN.sh", b"fp32_ingress_feature_receipt.txt"),
        ("delete_exact_stage_gate", "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh", b"qadd_ingress_stage_seq == 4"),
        ("delete_mse1_queue_update", "tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh", b"qadd_pair_qwr_count[m]++;"),
    )
    result = {}
    for name, member, token in cases:
        mutated = dict(files)
        mutated[member] = mutated[member].replace(token, b"")
        failed = not contract_ok(mutated)
        result[name] = {"exit_code": 1 if failed else 0, "failed_closed": failed}
    return result


def parser_controls(package_dir: Path) -> dict:
    path = package_dir / "package_tools/qlinearadd_node0007_fp32_ingress_canonical_v29.py"
    spec = importlib.util.spec_from_file_location("qadd_v29_canonical", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    marker = "# QADD_FP32_INGRESS_OBSERVER_V19 enabled=1 source_clock=clk_sg snapshot_clock=clk_db level_is_progress=0\n"
    def line(stage: int, cycle: int, value: int) -> str:
        vals = {name: value for name in module.QUALIFIED}
        body = " ".join(
            ["slice=0", f"stage_seq={stage}", f"snapshot_cycles={cycle}"]
            + [f"{k}={vals[k]}" for k in module.QUALIFIED]
            + ["buf_valid=0x3", "buf_arm_ready=0x3"]
        )
        return f"{cycle} | QADD_FP32_INGRESS | {body}\n"
    wrong = module.decide((marker + line(1, 0, 0)).encode(), stall_window_cycles=1048576, minimum_progress_windows=3)
    progress = module.decide((marker + "".join(line(4, i * 1048576, i) for i in range(4))).encode(), stall_window_cycles=1048576, minimum_progress_windows=3)
    checks = {
        "wrong_stage_fails_closed": wrong["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE" and wrong["boundary"] == "FP32_INGRESS_EXACT_STAGE_SCOPE",
        "exact_stage4_progress": progress["decision"] == "FP32_ADD_FIRST_OUTPUT_OBSERVED_CONTINUE_STANDARD_PROGRESS",
    }
    return {"valid": all(checks.values()), "checks": checks, "wrong_stage": wrong["decision"], "stage4": progress["decision"]}


def workload_frozen(files: dict[str, bytes], source: dict[str, bytes]) -> dict:
    paths = {x for x in files if x.startswith("workload/")}
    source_paths = {x for x in source if x.startswith("workload/")}
    mismatches = []
    for p in sorted(paths & source_paths):
        a, b = files[p], source[p]
        if p in {"workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"}:
            a = a.replace(NAME.encode(), SOURCE.encode())
        if a != b:
            mismatches.append(p)
    return {"exact_set": paths == source_paths, "mismatches_after_identity_normalization": mismatches, "valid": paths == source_paths and not mismatches}


def main() -> int:
    files, manifest = v28.load(ZIP, NAME)
    source_files, _ = v28.load(SOURCE_ZIP, SOURCE)
    hdl = json.loads(HDL.read_text(encoding="utf-8"))
    split.runner_validator.INSTALL_NAME = NAME
    split.base.INSTALL_NAME = NAME
    runner = split.runner_controls(ZIP, NAME)
    ingress.INSTALL_NAME = NAME
    ingress.ZIP_PATH = ZIP
    ingress.SIDECAR_PATH = Path(str(ZIP) + ".sha256")
    ingress.runner_validator.INSTALL_NAME = NAME
    finalizer = ingress.exit_and_signal_finalizer_controls()
    parser = parser_controls(ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}")
    negatives = negative_controls(files)
    frozen = workload_frozen(files, source_files)
    matrix = json.loads(files["diagnostics/candidate_observation_matrix.json"])
    checks = {
        "manifest_identity": manifest["install_name"] == NAME,
        "inventory_exact": v28.inventory_ok(files, manifest),
        "source_v28_bound": manifest["source_assets"]["split_c_ingress_v28_source_zip"]["sha256"] == sha(SOURCE_ZIP),
        "diagnostic_only": manifest["claim"] == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "observer_contract": contract_ok(files),
        "candidate_matrix_complete": set(matrix["candidates"]) == {
            "MSE0_INDEX_PAIR_STARVATION", "MSE1_INDEX_PAIR_STARVATION", "BUFFER0_DELIVERY_STALL",
            "BUFFER2_DELIVERY_STALL", "GA_OPERAND_CAPTURE_ASYMMETRY", "GA_PAIR_TAG_MASK_REJECT", "GA_OUTPUT_STALL"
        },
        "workload_frozen": frozen["valid"],
        "safe_compile_and_identity": runner["all_passed"],
        "exit_term_finalizer": finalizer["all_passed"],
        "canonical_parser": parser["valid"],
        "hdl_scope": hdl.get("valid") is True and hdl.get("all_negative_controls_fail_closed") is True,
        "all_negatives": all(x["failed_closed"] for x in negatives.values()),
        "sidecar": Path(str(ZIP) + ".sha256").read_text(encoding="ascii").strip() == f"{sha(ZIP)}  {ZIP.name}",
    }
    errors = [k for k, v in checks.items() if not v]
    report = {
        "schema": "qlinearadd-node0007-split-c-pairmatrix-v29-final-zip-self-audit",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "QUARANTINED",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "install_name": NAME,
        "zip_bytes": ZIP.stat().st_size,
        "zip_sha256": sha(ZIP),
        "checks": checks,
        "candidate_observation_matrix": matrix,
        "workload_freeze": frozen,
        "runner_control_flow": runner,
        "exit_term_finalizer": finalizer,
        "parser_controls": parser,
        "negative_controls": negatives,
        "package_local_hdl_gate": hdl,
        "rule_receipts": {k: {"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for k, p in RULES.items()},
        "claim_boundary": "split-C diagnostic only; no full-chain 28D/E3/E4/E5 claim",
        "numeric_workload_config_golden_repeated": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "errors": errors, "zip_sha256": report["zip_sha256"], "report_sha256": sha(OUT)}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
