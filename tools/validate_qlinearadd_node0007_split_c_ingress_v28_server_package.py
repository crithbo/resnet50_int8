from __future__ import annotations

import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_fp32_ingress_diag_v19_server_package as ingress
from tools import validate_qlinearadd_node0007_split_workloads_v25_server_packages as split


NAME = "r5_qadd_n7_split_c_ingress_v28"
SOURCE = "r5_qadd_n7_split_c_fp32_prefix_v26"
ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}.zip"
SOURCE_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{SOURCE}.zip"
HDL_REPORT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-ingress-v28-server-package/hdl_scope_revalidation.json"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-ingress-v28-server-package/final_zip_self_audit.json"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path, root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        infos = archive.infolist()
        names = [i.filename for i in infos if not i.is_dir()]
        unsafe = []
        for item in infos:
            p = PurePosixPath(item.filename)
            if p.is_absolute() or ".." in p.parts or "\\" in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                unsafe.append(item.filename)
        expected_root = root + "/"
        if bad or len(names) != len(set(names)) or unsafe or any(not n.startswith(expected_root) for n in names):
            raise ValueError("ZIP CRC/root/path/duplicate/symlink gate failed")
        files = {n[len(expected_root):]: archive.read(n) for n in names}
    manifest = json.loads(files["TEST_PACKAGE_MANIFEST.json"])
    return files, manifest


def inventory_ok(files: dict[str, bytes], manifest: dict[str, Any]) -> bool:
    inventory = manifest["files"]
    actual = set(files) - {"TEST_PACKAGE_MANIFEST.json"}
    if set(inventory) != actual:
        return False
    return all(
        len(files[name]) == int(rec["size_bytes"])
        and hashlib.sha256(files[name]).hexdigest() == rec["sha256"]
        for name, rec in inventory.items()
    )


def observer_check(files: dict[str, bytes]) -> bool:
    runner = files["PREPARE_AND_RUN.sh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    tail = files["tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"].decode()
    required_runner = (
        "+incdir+$package_root/tb_probe",
        "+define+NATIVE_RETURN_OBSERVER_ENABLE",
        "+RETURN_OBS_DEEP",
        "+QADD_FP32_INGRESS_OBSERVER",
        "QADD_FP32_INGRESS_OBSERVER_V19_TIME0",
        "# QADD_FP32_INGRESS_OBSERVER_V19 ",
        "fp32_ingress_feature_receipt.txt",
    )
    return (
        all(x in runner for x in required_runner)
        and '`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"' in native
        and '`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"' in files["tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"].decode()
        and "MSE_INST[0]" in tail
        and "MSE_INST[1]" in tail
        and "qadd_ingress_pair * 2" in tail
        and "always @(posedge u_NDP_Top_new.clk_sg)" in tail
        and "always @(posedge u_NDP_Top_new.clk_db)" in tail
        and "qadd_ingress_ga_consumer_accept" in tail
        and "qadd_ingress_ga_first_output" in tail
    )


def negative_controls(files: dict[str, bytes]) -> dict[str, Any]:
    cases = (
        ("delete_source_include", "tb_probe/native_return_observer.svh", b'`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"'),
        ("delete_incdir", "PREPARE_AND_RUN.sh", b"+incdir+$package_root/tb_probe"),
        ("delete_macro", "PREPARE_AND_RUN.sh", b"+define+NATIVE_RETURN_OBSERVER_ENABLE"),
        ("delete_feature", "PREPARE_AND_RUN.sh", b"+QADD_FP32_INGRESS_OBSERVER"),
        ("delete_time0", "PREPARE_AND_RUN.sh", b"QADD_FP32_INGRESS_OBSERVER_V19_TIME0"),
        ("delete_return_receipt", "PREPARE_AND_RUN.sh", b"fp32_ingress_feature_receipt.txt"),
        ("delete_stage_event", "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh", b"qadd_ingress_ga_consumer_accept"),
    )
    result = {}
    for name, member, token in cases:
        mutated = dict(files)
        mutated[member] = mutated[member].replace(token, b"")
        failed = not observer_check(mutated)
        result[name] = {"exit_code": 1 if failed else 0, "failed_closed": failed}
    return result


def frozen_workload(files: dict[str, bytes], source: dict[str, bytes]) -> dict[str, Any]:
    target_paths = {p for p in files if p.startswith("workload/")}
    source_paths = {p for p in source if p.startswith("workload/")}
    same_set = target_paths == source_paths
    mismatches = []
    for path in sorted(target_paths & source_paths):
        a, b = files[path], source[path]
        if path in {"workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"}:
            a = a.replace(NAME.encode(), SOURCE.encode())
        if a != b:
            mismatches.append(path)
    return {
        "path_exact_set": same_set,
        "semantic_byte_mismatch_after_identity_normalization": mismatches,
        "numeric_W3_qparam_tail_workload_config_golden_repeated": False,
        "frozen": same_set and not mismatches,
    }


def main() -> int:
    files, manifest = load(ZIP, NAME)
    source_files, _ = load(SOURCE_ZIP, SOURCE)
    hdl = json.loads(HDL_REPORT.read_text(encoding="utf-8"))

    split.runner_validator.INSTALL_NAME = NAME
    split.base.INSTALL_NAME = NAME
    runner = split.runner_controls(ZIP, NAME)
    ingress.INSTALL_NAME = NAME
    ingress.ZIP_PATH = ZIP
    ingress.SIDECAR_PATH = Path(str(ZIP) + ".sha256")
    ingress.runner_validator.INSTALL_NAME = NAME
    finalizer = ingress.exit_and_signal_finalizer_controls()
    parser = ingress.parser_controls()
    negatives = negative_controls(files)
    workload = frozen_workload(files, source_files)
    checks = {
        "manifest_identity": manifest["install_name"] == NAME,
        "manifest_inventory_exact": inventory_ok(files, manifest),
        "source_zip_bound": manifest["source_assets"]["split_c_v26_source_zip"]["sha256"] == sha(SOURCE_ZIP),
        "diagnostic_claim_only": manifest["claim"] == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "observer_binding": observer_check(files),
        "workload_frozen": workload["frozen"],
        "safe_runner_compile_stub": runner["all_passed"],
        "safe_exit_term_finalizer": finalizer["all_passed"],
        "canonical_parser": parser["valid"],
        "hdl_scope": hdl.get("valid") is True and hdl.get("all_negative_controls_fail_closed") is True,
        "all_static_negatives": all(v["failed_closed"] for v in negatives.values()),
        "sidecar": Path(str(ZIP) + ".sha256").read_text(encoding="ascii").strip() == f"{sha(ZIP)}  {ZIP.name}",
        "v27_not_release": True,
    }
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "qlinearadd-node0007-split-c-ingress-v28-final-zip-self-audit",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "QUARANTINED",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "install_name": NAME,
        "zip": ZIP.relative_to(ROOT).as_posix(),
        "zip_bytes": ZIP.stat().st_size,
        "zip_sha256": sha(ZIP),
        "source_split_c_v26_sha256": sha(SOURCE_ZIP),
        "checks": checks,
        "workload_freeze": workload,
        "runner_control_flow": runner,
        "exit_term_finalizer": finalizer,
        "canonical_parser_controls": parser,
        "observer_negative_controls": negatives,
        "package_local_hdl_gate": hdl,
        "v27_adjudication": "QUARANTINED_SCA_NAMESPACE_PRECOMPILE_FAILURE",
        "rule_receipts": {k: {"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for k, p in RULES.items()},
        "claim_boundary": "split-C diagnostic only; no full-chain 28D, E3, E4, or E5 claim",
        "functional_rtl_modified": False,
        "server_action": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "errors": errors, "zip_sha256": report["zip_sha256"], "report": str(OUT), "report_sha256": sha(OUT)}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
