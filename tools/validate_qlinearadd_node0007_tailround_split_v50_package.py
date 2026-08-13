"""Validate the exact isolated QAdd node0007 tail_round v50 ZIP."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import validate_qlinearadd_node0007_tailround_flow_v47 as hdl
import validate_qlinearadd_node0007_tailround_flow_v48 as base


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_split_v50"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-v50-package"
ZIP = OUT / f"{NAME}.zip"
REPORT = OUT / "family_validation.json"
HARNESS = OUT / "runtime_layout_harness.json"
CONFIG_BUILD = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild/build_receipt.json"
CONFIG_VALIDATION = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild/validation_report.json"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PYTHON = ROOT / ".venv/Scripts/python.exe"
RULES = {
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], cwd: Path | None = None) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    return {"argv": argv, "exit_code": result.returncode, "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]}


def main() -> int:
    base.NAME = NAME
    errors: list[str] = []
    checks: dict[str, bool] = {}
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos if not row.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names}
        rels = [name.split("/", 1)[1] for name in names]
        checks["crc"] = archive.testzip() is None
        checks["safe_root_path_duplicate_symlink"] = (
            roots == {NAME}
            and len(names) == len(set(names))
            and all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names)
            and all(((row.external_attr >> 16) & 0o170000) != 0o120000 for row in infos)
        )
        manifest = json.loads(archive.read(f"{NAME}/TEST_PACKAGE_MANIFEST.json"))
        records = manifest.get("files", {})
        inventory_ok = set(records) == set(rels) - {"TEST_PACKAGE_MANIFEST.json"}
        if inventory_ok:
            for rel, receipt in records.items():
                payload = archive.read(f"{NAME}/{rel}")
                if receipt != {"size_bytes": len(payload), "sha256": sha_bytes(payload)}:
                    inventory_ok = False
                    break
        checks["manifest_exact_set_and_hashes"] = inventory_ok
        runner_b = archive.read(f"{NAME}/PREPARE_AND_RUN.sh")
        runner = runner_b.decode("utf-8")
        native = archive.read(f"{NAME}/tb_probe/native_return_observer.svh").decode("utf-8")
        tail = archive.read(f"{NAME}/tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh").decode("utf-8")
        canonical_b = archive.read(f"{NAME}/package_tools/qlinearadd_node0007_tailround_split_canonical_v50.py")
        runtime_b = archive.read(f"{NAME}/package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py")
        sca = json.loads(archive.read(f"{NAME}/workload/runtime/sca_cfg.json"))
        sca_d = json.loads(archive.read(f"{NAME}/workload/runtime/sca_cfg_D.json"))
        split = manifest.get("split_segment_contract", {})
        boundary = manifest.get("boundary_input_contract", {})
        checks["identity_and_honest_claim"] = (
            manifest.get("install_name") == NAME
            and manifest.get("package_id") == NAME
            and manifest.get("candidate_release") is False
            and manifest.get("claim") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("evidence_level") == "E2_LOCAL_ONLY"
            and split.get("boundary_mode") == "DIAGNOSTIC_STIMULUS_NOT_PRODUCER_EVIDENCE"
            and split.get("host_precomputed_internal_tensor") is True
            and split.get("producer_evidence_claimed") is False
            and boundary.get("host_precomputed_internal_tensor") is True
            and boundary.get("producer_evidence_claimed") is False
        )
        checks["one_stage_sca_execplan_28D"] = (
            sca.get("Repeat_Num") == 1
            and sca.get("Exec_Length") == 29
            and split.get("stage_names") == ["op_tail_round"]
            and split.get("expected_stage_count") == 1
            and len(sca_d) == 28
            and set(sca_d) == {f"op_tail_round_matrixD_slice{i}" for i in range(28)}
            and len(split.get("output_checks", [])) == 28
            and len(archive.read(f"{NAME}/workload/runtime/install/execplan.txt").splitlines()) == 29
            and archive.read(f"{NAME}/workload/runtime/install/execplan.txt")
            == archive.read(f"{NAME}/workload/runtime/install/execplan_op_tail_round.txt")
        )
        boundary_ok = len(boundary.get("entries", [])) == 28
        for row in boundary.get("entries", []):
            rel = f"workload/runtime/install/op_tail_round/slice{row['slice_id']:02d}/matrix_A_linearized_128bit.txt"
            payload = archive.read(f"{NAME}/{rel}")
            boundary_ok &= len(payload) == row["text_bytes"] and sha_bytes(payload) == row["sha256"]
            boundary_ok &= payload.count(b"\n") == 150528 and all(len(line) == 128 and set(line) <= {48, 49} for line in payload.splitlines()[:2])
        checks["boundary_28_exact_receipts_and_shape"] = bool(boundary_ok)
        checks["runtime_D_initially_absent"] = not any(rel.startswith("readbacks/") or (rel.endswith("matrix_D_linearized_128bit.txt") and not rel.startswith("validation/golden/")) for rel in rels)
        checks["runner_scope_layout_and_feature"] = (
            "qlinearadd_node0007_tailround_split_runtime_v50.py" in runner
            and "qlinearadd_node0007_tailround_split_canonical_v50.py" in runner
            and "QADD_TAILROUND_SPLIT_V50" in runner
            and "--kill-after=30s 2h" in runner
            and 'result_root="/home/panqs/ndp/simresult"' in runner
            and '--cfg-root "$cfg_root" --return-zip "$return_zip"' in runner
        )
        checks["observer_stage_one_qualified"] = tail.count("q47_stage_index == 1") == 2 and "stage=1" in tail and "q47_stage_index == 6" not in tail
        expected_rules = {key: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path), "current_match": True} for key, path in RULES.items()}
        checks["rule_receipts_current"] = manifest.get("rule_receipts") == expected_rules

    config_build = json.loads(CONFIG_BUILD.read_text(encoding="utf-8"))
    config_validation = json.loads(CONFIG_VALIDATION.read_text(encoding="utf-8"))
    checks["config_colfix_and_negatives"] = (
        config_build.get("status") == "LOCAL_CONFIG_CORRECTION_MATERIALIZED"
        and config_validation.get("valid") is True
        and config_validation.get("errors") == []
        and config_validation.get("changed_leaves") == [
            {"new": 4, "old": 32, "path": "$.buffer_loop_configs.GROUP2.COL_LC.end", "stage": "op_tail_round"},
            {"new": 2, "old": 16, "path": "$.buffer_loop_configs.GROUP2.COL_LC.stride", "stage": "op_tail_round"},
        ]
        and all(row.get("failed_closed") is True and row.get("exit_code") != 0 for row in config_validation.get("transaction_negative_controls", {}).values())
    )

    with tempfile.TemporaryDirectory(prefix="q50-validate-") as raw:
        work = Path(raw)
        with zipfile.ZipFile(ZIP) as archive:
            archive.extractall(work)
        package = work / NAME
        runner_path = package / "PREPARE_AND_RUN.sh"
        bash_syntax = run([str(BASH), "-n", str(runner_path)])
        parser_selftest = run([str(PYTHON), str(package / "package_tools/qlinearadd_node0007_tailround_split_canonical_v50.py"), "--self-test"])
        runtime_preflight = run([str(PYTHON), str(package / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"), "preflight", "--package-root", str(package)], cwd=package / "package_tools")
        python_files = [str(path) for path in (package / "package_tools").glob("*.py")]
        python_syntax = run([str(PYTHON), "-m", "py_compile", *python_files])
    checks["runner_bash_syntax"] = bash_syntax["exit_code"] == 0
    checks["package_python_syntax"] = python_syntax["exit_code"] == 0
    checks["canonical_selftest_decimal_safe"] = parser_selftest["exit_code"] == 0 and '"pass": true' in parser_selftest["stdout"].lower()
    checks["runtime_preflight_exact_package"] = runtime_preflight["exit_code"] == 0
    visibility = base.runner_visibility_unit(runner)
    checks["runner_error_visibility_unit"] = visibility.get("pass") is True
    closure = hdl.hdl_closure(tail)
    xmr = hdl.xmr_gate(tail)
    frontend = hdl.hdl_frontend(native, tail)
    negatives = hdl.negative_controls(tail)
    checks["hdl_declaration_use_update_closure"] = closure.get("valid") is True
    checks["hdl_xmr_scope"] = xmr.get("valid") is True
    checks["hdl_compatible_frontend"] = frontend.get("valid") is True
    checks["hdl_three_negative_classes"] = negatives.get("all_fail_closed") is True
    checks["source_runtime_parser_names_bound"] = sha_bytes(canonical_b) == records["package_tools/qlinearadd_node0007_tailround_split_canonical_v50.py"]["sha256"] and sha_bytes(runtime_b) == records["package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"]["sha256"]

    for key, value in checks.items():
        if value is not True:
            errors.append(key)
    write_json(HARNESS, base.harness(sha(ZIP), sha_bytes(runner_b)))
    report = {
        "schema": "qlinearadd-node0007-tailround-split-v50-family-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        "commands": {"bash_syntax": bash_syntax, "python_syntax": python_syntax, "canonical_selftest": parser_selftest, "runtime_preflight": runtime_preflight},
        "runner_visibility_unit": visibility,
        "hdl_scope_revalidation": {"closure": closure, "xmr": xmr, "frontend": frontend, "negative_controls": negatives},
        "config_negative_controls": config_validation.get("transaction_negative_controls"),
        "claim_boundary": "isolated tail_round natural terminal and exact stage-local 28D only; host diagnostic FP32 boundary stimulus is not producer evidence; no upstream/full-chain/E3/E4/E5 claim",
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "server_action": False,
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
    }
    write_json(REPORT, report)
    print(json.dumps({"valid": not errors, "errors": errors, "report": str(REPORT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
