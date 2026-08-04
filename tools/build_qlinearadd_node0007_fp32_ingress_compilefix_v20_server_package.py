from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, preflight, write_json


INSTALL_NAME = "r5_qadd_n7_fp32_ingress_compilefix_v20"
SOURCE_NAME = "r5_qadd_n7_fp32_ingress_diag_v19"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "f32abc4b2b91bf5e854ab113aa98fd1f7925e68a3bd8958f2454762a524709ba"
RETURN_REPORT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-ingress-v19-return-analysis/report.json"
)
SHIM = ROOT / "tools/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"
VALIDATION = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-ingress-compilefix-v20"
)
RULES = {
    "generation_index": (
        ROOT / ".agents/rules/生成前必读索引.md",
        "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8",
    ),
    "server_package_rule": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141",
    ),
    "qlinearadd_rule": (
        ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
        "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f",
    ),
    "exact_uint8_tail_rule": (
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ),
}


class BuildError(ValueError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rule_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"规则 ID：`([^`]+)`", text)


def assert_receipts() -> None:
    expected = {SOURCE_ZIP: SOURCE_SHA, **{p: s for p, s in RULES.values()}}
    drift = {
        str(path): {"expected": wanted, "actual": sha(path) if path.is_file() else None}
        for path, wanted in expected.items()
        if not path.is_file() or sha(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")
    for path in (SOURCE_DIR, SHIM, RETURN_REPORT):
        if not path.exists():
            raise BuildError(f"required input absent: {path}")


def replace_namespace(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".bin", ".npy", ".npz", ".png"}:
            continue
        payload = path.read_bytes()
        path.write_bytes(payload.replace(SOURCE_NAME.encode(), INSTALL_NAME.encode()))


def patch_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(f"preimage count differs for {path}: {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def build_directory(destination: Path) -> Path:
    assert_receipts()
    package = destination / INSTALL_NAME
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)
    replace_namespace(package)

    shim_target = package / "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"
    shutil.copy2(SHIM, shim_target)
    native = package / "tb_probe/native_return_observer.svh"
    patch_once(
        native,
        '`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"',
        '`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"',
    )
    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 FP32 ingress compile fix v20\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. This successor preserves the "
        "v19 workload, configuration, mapping, bitstream, execplan, SCA, "
        "qparams, exact tail and golden. The sole repair declares and binds "
        "the qualified GA operand-capture monitor consumed by the unchanged "
        "v19 observer tail. No functional RTL or timeout is changed.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return_report_sha = sha(RETURN_REPORT)
    manifest.update(
        {
            "schema": "qlinearadd-node0007-fp32-ingress-compilefix-server-package-v20",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "repairs the package-local v19 observer declaration/XMR binding "
                "only; no dynamic QAdd, E4/E5, production, performance or RTL claim"
            ),
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_SHA,
                "status": "QUARANTINED_OBSERVER_COMPILE_IDENTIFIER_UNDECLARED",
                "numeric_workload_config_golden_unchanged": True,
            },
            "successor_reason": {
                "last_proven_good": "VCS_PARSED_QADD_FP32_INGRESS_OBSERVER_THROUGH_LINE_239",
                "first_divergence": "OBSERVER_V19_LINE_240_UNDECLARED_RETURN_OBS_GA_OPERAND_CAPTURE_MON",
                "unique_root_cause_proven": True,
                "root_cause_scope": "PACKAGE_LOCAL_OBSERVER_ONLY",
            },
            "observer_compilefix_v20": {
                "source_path": shim_target.relative_to(package).as_posix(),
                "source_sha256": sha(shim_target),
                "declared_identifier": "return_obs_ga_operand_capture_mon",
                "qualified_rtl_leaf": "GA_PE_Inbuffer.ga_pe_inbuffer_enable",
                "physical_ga_columns": [0, 2],
                "v19_tail_unchanged_sha256": sha(
                    package / "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
                ),
                "functional_rtl_modified": False,
                "configuration_modified": False,
                "timeout_modified": False,
            },
            "server_tb_or_observer_entries": 4,
        }
    )
    manifest["provenance"].update(
        {
            "generator": (
                "tools/build_qlinearadd_node0007_"
                "fp32_ingress_compilefix_v20_server_package.py"
            ),
            "v19_return_analysis_report": {
                "path": RETURN_REPORT.relative_to(ROOT).as_posix(),
                "sha256": return_report_sha,
            },
        }
    )
    manifest["final_zip_rule_self_audit"].update(
        {
            "validator": (
                "tools/validate_qlinearadd_node0007_"
                "fp32_ingress_compilefix_v20_server_package.py"
            ),
            "report": (
                "artifacts/operator_config_validation/"
                "r5-qlinearadd-node0007-fp32-ingress-compilefix-v20/"
                "final_zip_self_audit.json"
            ),
            "rule_receipts": {
                key: {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": digest,
                    "current_match": True,
                }
                for key, (path, digest) in RULES.items()
            },
            "applicable_server_rule_ids": rule_ids(RULES["server_package_rule"][0]),
            "applicable_qlinearadd_rule_ids": rule_ids(RULES["qlinearadd_rule"][0]),
            "applicable_exact_tail_rule_ids": rule_ids(RULES["exact_uint8_tail_rule"][0]),
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package = build_directory(destination)
    output = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output)
    return package, output, file_records(package, exclude_manifest=False)


def main() -> int:
    package = PACKAGE_ROOT / INSTALL_NAME
    output = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(output) + ".sha256")
    for path in (package, output, sidecar, VALIDATION):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, output, records = build_once(PACKAGE_ROOT)
        with tempfile.TemporaryDirectory(prefix="qadd-v20-repeat-") as raw:
            _, repeat_zip, repeat_records = build_once(Path(raw))
            repeat_sha = sha(repeat_zip)
        if records != repeat_records or sha(output) != repeat_sha:
            raise BuildError("deterministic rebuild differs")
        digest = sha(output)
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt = {
            "schema": "qlinearadd-node0007-fp32-ingress-compilefix-build-v20",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "zip_bytes": output.stat().st_size,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha(sidecar),
            "source_zip_sha256": SOURCE_SHA,
            "file_count": len(records),
            "repeated_build": {
                "package_tree_equal": records == repeat_records,
                "zip_equal": digest == repeat_sha,
                "repeat_zip_sha256": repeat_sha,
            },
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "configuration_changed": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(VALIDATION, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
