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
from tools import build_qlinearadd_node0007_config_preload_v14_server_package as v14
from tools import validate_qlinearadd_node0007_first_request_chain_v10 as base_validator


INSTALL_NAME = "r5_qadd_n7_dbuf_v15"
SOURCE_NAME = "r5_qadd_n7_cfgpreload_v14"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
EVIDENCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-d-buffer-supply-v15"
)
PIPELINE = EVIDENCE_ROOT / "execplan/pipeline_output"
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
COMMON_RULE = ROOT / ".agents/rules/算子配置规则.md"
NDP_RULE = ROOT / ".agents/rules/NDP硬件字段语义.md"
SERVER_RULE_SHA256 = "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
QADD_RULE_SHA256 = "c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b"
INDEX_SHA256 = "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
COMMON_RULE_SHA256 = "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
NDP_RULE_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
RUNTIME_SOURCE = ROOT / "tools/qlinearadd_node0007_server_runtime.py"
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-supply-v15/final_zip_self_audit.json"
)


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rule_ids(path: Path) -> list[str]:
    return base_validator._rule_ids(path)


def _assert_receipts() -> None:
    expected = {
        SOURCE_ZIP: SOURCE_ZIP_SHA256,
        INDEX: INDEX_SHA256,
        SERVER_RULE: SERVER_RULE_SHA256,
        QADD_RULE: QADD_RULE_SHA256,
        COMMON_RULE: COMMON_RULE_SHA256,
        NDP_RULE: NDP_RULE_SHA256,
    }
    drift = {
        str(path): {"expected": wanted, "actual": sha256(path)}
        for path, wanted in expected.items()
        if not path.is_file() or sha256(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")
    if not (PIPELINE.parent / "execplan_validation_report.json").is_file():
        raise BuildError("fresh execplan validation report is absent")
    execplan_report = json.loads(
        (PIPELINE.parent / "execplan_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    if execplan_report.get("valid") is not True:
        raise BuildError("fresh execplan validator is not clean")


def _copy_source(destination: Path) -> Path:
    package = destination / INSTALL_NAME
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)
    return package


def _replace_namespace_tree(package: Path) -> None:
    binary_suffixes = {".bin", ".png", ".npy", ".npz"}
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in binary_suffixes:
            continue
        payload = path.read_bytes()
        if SOURCE_NAME.encode() in payload:
            path.write_bytes(payload.replace(SOURCE_NAME.encode(), INSTALL_NAME.encode()))


def _replace_fresh_native_chain(package: Path) -> None:
    runtime_install = package / "workload/runtime/install"
    fresh_install = PIPELINE / "install"
    for source in fresh_install.glob("execplan*.txt"):
        shutil.copy2(source, runtime_install / source.name)
    for source in (fresh_install / "cfg_pkg").glob("*_bitstream_128b.bin"):
        shutil.copy2(source, runtime_install / "cfg_pkg" / source.name)


def _refresh_preload_contract(package: Path) -> list[dict[str, Any]]:
    runtime = package / "workload/runtime"
    sca = json.loads((runtime / "sca_cfg.json").read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for key, stage, base, filename, config_length in v14.CONFIG_PRELOADS:
        payload = runtime / "install/cfg_pkg" / filename
        lines = payload.read_bytes().splitlines()
        if len(lines) * 2 != config_length:
            raise BuildError(f"fresh config length differs: {stage}")
        path = f"install/cfg_pkg/{INSTALL_NAME}/install/cfg_pkg/{filename}"
        sca[key] = {"base_addr": base, "path": path}
        records.append(
            {
                "sca_key": key,
                "stage": stage,
                "base_addr": base,
                "path": path,
                "sha256": sha256(payload),
                "line_count": len(lines),
                "config_length_64b": config_length,
                "load_config_address_equation": (
                    f"ddr_config_addr={hex(int(base, 16) >> 10)}; "
                    "base_addr=ddr_config_addr<<10"
                ),
            }
        )
    write_json(runtime / "sca_cfg.json", sca)
    return records


def build_directory(destination: Path) -> Path:
    _assert_receipts()
    package = _copy_source(destination)
    _replace_namespace_tree(package)
    _replace_fresh_native_chain(package)
    shutil.copy2(
        RUNTIME_SOURCE,
        package / "package_tools/qlinearadd_node0007_server_runtime.py",
    )
    preload_records = _refresh_preload_contract(package)
    (package / "README.md").write_text(
        "# QLinearAdd node0007 D-buffer supply fix v15\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "The v14 return completed both dequant stages, then permanently "
        "stalled in op_relocation_pad after two write-address requests but "
        "only one write-data beat. The frozen 32-byte D transactions had "
        "only one 16-byte buffer row. v15 changes only GROUP2.ROW_LC.end "
        "from 1 to 2 and buffer5.buf_end_row_addr from 0 to 1 for "
        "op_relocation_pad, op_tail_mul and op_tail_round. It rebuilds "
        "mapping, bitstreams and execplan from empty state. W3, qparams, "
        "addresses, DRAM occurrence loops, workload, golden and functional "
        "RTL are unchanged.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-d-buffer-supply-server-package-v15",
            "install_name": INSTALL_NAME,
            "package_class": (
                "FUNCTIONAL_CONFIG_FIX_WITH_DEFAULT_PROGRESS_DIAGNOSTICS"
            ),
            "functional_fix": True,
            "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "claim_boundary": (
                "node0007 configuration-only D-buffer supply correction; "
                "no E4/E5, production, performance or functional-RTL claim"
            ),
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "QUARANTINED_DYNAMIC_D_BUFFER_UNDERSUPPLY",
                "numeric_workload_and_golden_unchanged": True,
            },
            "functional_configuration_fix": {
                "first_dynamic_divergence": (
                    "op_relocation_pad: MSE4 requests=(2,1), "
                    "write-data=(1,0), outstanding=(1,1), then flat for "
                    "more than 38 stall windows"
                ),
                "root_cause": (
                    "32-byte D transaction supplied by one 16-byte "
                    "buffer5 row"
                ),
                "changed_semantic_layer": "D_BUFFER_SUPPLY_CONSERVATION",
                "changed_stages": [
                    "op_relocation_pad",
                    "op_tail_mul",
                    "op_tail_round",
                ],
                "changed_leaves_per_stage": {
                    "buffer_loop_configs.GROUP2.ROW_LC.end": [1, 2],
                    "buffer_config.buffer5.buf_end_row_addr": [0, 1],
                },
                "transaction_bytes": 32,
                "buffer_bytes_per_row": 16,
                "old_supply_bytes": 16,
                "new_supply_bytes": 32,
                "functional_rtl_modified": False,
                "w3_qparams_tail_workload_golden_changed": False,
                "dram_loop_address_occurrence_changed": False,
            },
            "config_preload_contract": {
                "owner": "QLinearAdd package SCA materializer",
                "expected_sca_preload_count": 91,
                "source_preload_count": 85,
                "added_config_preload_count": 6,
                "entries": preload_records,
            },
        }
    )
    manifest["provenance"].update(
        {
            "generator": (
                "tools/build_qlinearadd_node0007_"
                "d_buffer_supply_v15_server_package.py"
            ),
            "generation_index": {
                "path": INDEX.relative_to(ROOT).as_posix(),
                "sha256": INDEX_SHA256,
            },
            "server_package_rule": {
                "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                "sha256": SERVER_RULE_SHA256,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE.relative_to(ROOT).as_posix(),
                "sha256": QADD_RULE_SHA256,
            },
            "common_operator_rule": {
                "path": COMMON_RULE.relative_to(ROOT).as_posix(),
                "sha256": COMMON_RULE_SHA256,
            },
            "ndp_field_rule": {
                "path": NDP_RULE.relative_to(ROOT).as_posix(),
                "sha256": NDP_RULE_SHA256,
            },
            "fresh_native_chain": {
                "root": EVIDENCE_ROOT.relative_to(ROOT).as_posix(),
                "execplan_validation_sha256": sha256(
                    PIPELINE.parent / "execplan_validation_report.json"
                ),
                "double_run_sha256": sha256(
                    PIPELINE.parent / "double_run_comparison.json"
                ),
            },
        }
    )
    manifest["final_zip_rule_self_audit"] = {
        "rule_id": "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
        "rule_receipts": {
            "generation_index": {
                "path": INDEX.relative_to(ROOT).as_posix(),
                "sha256": INDEX_SHA256,
                "current_match": True,
            },
            "server_package_rule": {
                "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                "sha256": SERVER_RULE_SHA256,
                "current_match": True,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE.relative_to(ROOT).as_posix(),
                "sha256": QADD_RULE_SHA256,
                "current_match": True,
            },
        },
        "applicable_server_rule_ids": _rule_ids(SERVER_RULE),
        "applicable_qlinearadd_rule_ids": _rule_ids(QADD_RULE),
        "direct_final_zip_and_sidecar_validation_required": True,
        "all_required_negative_controls_required": True,
        "pass_field": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
        "errors_must_equal": 0,
        "validator": (
            "tools/validate_qlinearadd_node0007_"
            "d_buffer_supply_v15_server_package.py"
        ),
        "report": REPORT_REL,
    }
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def _build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package = build_directory(destination)
    output = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output)
    return package, output, file_records(package, exclude_manifest=False)


def main() -> int:
    package = PACKAGE_ROOT / INSTALL_NAME
    output = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(output) + ".sha256")
    for path in (package, output, sidecar, VALIDATION_PATH):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, built, records = _build_once(PACKAGE_ROOT)
        with tempfile.TemporaryDirectory(prefix="qadd-v15-repeat-") as raw:
            _, repeat_zip, repeat_records = _build_once(Path(raw))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": sha256(built) == sha256(repeat_zip),
                "repeat_zip_sha256": sha256(repeat_zip),
            }
        if not repeated["package_tree_equal"] or not repeated["zip_equal"]:
            raise BuildError("deterministic rebuild differs")
        digest = sha256(output)
        sidecar.write_text(
            f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
        )
        receipt: dict[str, Any] = {
            "schema": "qlinearadd-node0007-d-buffer-supply-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "zip_bytes": output.stat().st_size,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha256(sidecar),
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "file_count": len(records),
            "repeated_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "config_numeric_analysis_repeated": False,
            "consumed_reuse_assets": True,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(VALIDATION_PATH, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
