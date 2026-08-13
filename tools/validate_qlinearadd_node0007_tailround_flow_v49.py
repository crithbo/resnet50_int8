"""Validate exact QAdd v49 after the canonical rule-path correction."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import validate_qlinearadd_node0007_tailround_flow_v47 as hdl
import validate_qlinearadd_node0007_tailround_flow_v48 as base


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_flow_v49"
SOURCE_NAME = "r5_qadd_n7_tailround_flow_v48"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v49-package"
ZIP = OUT / f"{NAME}.zip"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v48-package/r5_qadd_n7_tailround_flow_v48.zip"
REPORT = OUT / "family_validation.json"
HARNESS = OUT / "runtime_layout_harness.json"
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
CHANGED = {"README.md", "TEST_PACKAGE_MANIFEST.json"}
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


def normalize(value: bytes) -> bytes:
    try:
        return value.decode("utf-8").replace(NAME, SOURCE_NAME).encode("utf-8")
    except UnicodeDecodeError:
        return value


def main() -> int:
    files, manifest = base.read_zip(ZIP, NAME)
    source, _ = base.read_zip(SOURCE, SOURCE_NAME)
    records = manifest.get("files", {})
    inventory = set(records) == (set(files) - {"TEST_PACKAGE_MANIFEST.json"}) and all(row.get("size_bytes") == len(files[name]) and row.get("sha256") == sha_bytes(files[name]) for name, row in records.items())
    changed = sorted(name for name in set(files) | set(source) if name == "TEST_PACKAGE_MANIFEST.json" or name not in files or name not in source or normalize(files[name]) != source[name])
    runner = files["PREPARE_AND_RUN.sh"].decode(); tail = files["tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh"].decode(); native = files["tb_probe/native_return_observer.svh"].decode()
    with tempfile.NamedTemporaryFile(prefix="q49-runner-", suffix=".sh", delete=False, mode="w", encoding="utf-8") as stream:
        runner_path = Path(stream.name); stream.write(runner)
    bash = subprocess.run([str(BASH), "-n", str(runner_path)], capture_output=True, text=True, check=False); runner_path.unlink()
    with tempfile.TemporaryDirectory(prefix="q49-py-") as raw:
        paths = []
        for member, payload in files.items():
            if member.startswith("package_tools/") and member.endswith(".py"):
                path = Path(raw) / Path(member).name; path.write_bytes(payload); paths.append(str(path))
        py = subprocess.run([str(PYTHON), "-m", "py_compile", *paths], capture_output=True, text=True, check=False)
    base.NAME = NAME
    visibility = base.runner_visibility_unit(runner)
    closure = hdl.hdl_closure(tail); xmr = hdl.xmr_gate(tail); frontend = hdl.hdl_frontend(native, tail); negatives = hdl.negative_controls(tail)
    expected_receipts = {key: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)} for key, path in RULES.items()}
    checks = {
        "zip_manifest_exact": inventory,
        "identity": manifest.get("install_name") == NAME,
        "changed_surface_exact": changed == sorted(CHANGED),
        "rule_receipts_current_and_canonical": manifest.get("rule_receipts") == expected_receipts,
        "runner_bash_syntax": bash.returncode == 0,
        "package_python_syntax": py.returncode == 0,
        "runner_error_visibility_unit": visibility["pass"],
        "collector_cfg_root_return_zip_bound": '--cfg-root "$cfg_root" --return-zip "$return_zip"' in runner,
        "canonical_qualified_only": '"buf4_wr"' not in files["package_tools/qlinearadd_node0007_tailround_flow_canonical_v47.py"].decode().split("QUALIFIED =", 1)[1].split(")", 1)[0],
        "hdl_closure": closure["valid"], "hdl_xmr": xmr["valid"], "hdl_frontend": frontend["valid"], "hdl_negatives": negatives["all_fail_closed"],
        "timeout_frozen_8h": "--kill-after=30s 8h" in runner,
        "fixed_result": 'result_root="/home/panqs/ndp/simresult"' in runner,
        "runtime_D_absent": not any(name.startswith("readbacks/") or (name.endswith("matrix_D_linearized_128bit.txt") and not name.startswith("validation/golden/")) for name in files),
    }
    errors = [key for key, value in checks.items() if value is not True]
    write_json(HARNESS, base.harness(sha(ZIP), sha_bytes(files["PREPARE_AND_RUN.sh"])))
    report = {"schema": "qadd-tailround-flow-v49-family-validation-v1", "valid": not errors, "errors": errors, "checks": checks, "zip": {"bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}, "changed_members": changed, "expected_changed_members": sorted(CHANGED), "rule_receipts": expected_receipts, "runner_visibility_unit": visibility, "hdl_scope_revalidation": {"closure": closure, "xmr": xmr, "frontend": frontend, "negative_controls": negatives}, "runner": {"bash_exit": bash.returncode, "bash_stderr": bash.stderr, "python_compile_exit": py.returncode, "python_stderr": py.stderr}, "claim_boundary": "exact v49 ZIP, canonical current rule paths, inherited exact v48 runner/diagnostic/functional semantics after identity normalization; no DUT/server/terminal/D/E3/E4/E5", "numeric_workload_config_golden_repeated": False, "server_action": False}
    write_json(REPORT, report)
    print(json.dumps({"valid": not errors, "errors": errors, "report": str(REPORT)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
