from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, preflight, write_json
from tools import build_qlinearadd_node0007_rate_limited_clock_v13_server_package as v13


INSTALL_NAME = "r5_qadd_n7_cfgpreload_v14"
SOURCE_NAME = "r5_qadd_n7_obsrate_v13"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "fe65a96ad6365872f2f004f6702b197f33fc6b5fcd4397df716714f443b28858"
INDEX = v13.INDEX
INDEX_SHA256 = v13.INDEX_SHA256
SERVER_RULE = v13.SERVER_RULE
SERVER_RULE_SHA256 = "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
QADD_RULE = v13.QADD_RULE
QADD_RULE_SHA256 = v13.QADD_RULE_SHA256
COMMON_RULE = ROOT / ".agents/rules/算子配置规则.md"
COMMON_RULE_SHA256 = "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
NDP_RULE = ROOT / ".agents/rules/NDP硬件字段语义.md"
NDP_RULE_SHA256 = "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
RUNTIME_SOURCE = ROOT / "tools/qlinearadd_node0007_server_runtime.py"
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-config-preload-v14/report.json"
)

CONFIG_PRELOADS = (
    (
        "op_a_dequant_config",
        "op_a_dequant",
        "0x00D2B000",
        "op_a_dequant_resnet50_qadd_node0007_a_dequant_bitstream_128b.bin",
        52,
    ),
    (
        "op_b_dequant_config",
        "op_b_dequant",
        "0x00D2B400",
        "op_b_dequant_resnet50_qadd_node0007_b_dequant_bitstream_128b.bin",
        52,
    ),
    (
        "op_relocation_pad_config",
        "op_relocation_pad",
        "0x00D2B800",
        "op_relocation_pad_resnet50_qadd_node0007_relocation_pad_bitstream_128b.bin",
        50,
    ),
    (
        "op_fp32_add_config",
        "op_fp32_add",
        "0x00D2BC00",
        "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin",
        52,
    ),
    (
        "op_tail_mul_config",
        "op_tail_mul",
        "0x00D2C000",
        "op_tail_mul_resnet50_qadd_node0007_tail_mul_bitstream_128b.bin",
        50,
    ),
    (
        "op_tail_round_config",
        "op_tail_round",
        "0x00D2C400",
        "op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin",
        68,
    ),
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
    return re.findall(r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8"))


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


def _extract(destination: Path) -> Path:
    package = destination / INSTALL_NAME
    with tempfile.TemporaryDirectory(prefix="q14-source-") as raw:
        staging = Path(raw)
        with zipfile.ZipFile(SOURCE_ZIP) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise BuildError(f"source ZIP CRC failure: {bad}")
            archive.extractall(staging)
        source = staging / SOURCE_NAME
        if not source.is_dir():
            raise BuildError("source ZIP root differs")
        shutil.move(str(source), str(package))
    return package


def _replace_namespace(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(SOURCE_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )


def _materialize_config_preloads(package: Path) -> list[dict[str, Any]]:
    runtime = package / "workload/runtime"
    sca_path = runtime / "sca_cfg.json"
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for key, stage, base, filename, config_length in CONFIG_PRELOADS:
        path = f"install/cfg_pkg/{INSTALL_NAME}/install/cfg_pkg/{filename}"
        payload = runtime / "install/cfg_pkg" / filename
        if not payload.is_file():
            raise BuildError(f"missing frozen config payload: {filename}")
        line_count = len(payload.read_bytes().splitlines())
        if line_count != config_length // 2:
            raise BuildError(f"config length differs: {stage}")
        sca[key] = {"base_addr": base, "path": path}
        records.append(
            {
                "sca_key": key,
                "stage": stage,
                "base_addr": base,
                "path": path,
                "sha256": sha256(payload),
                "line_count": line_count,
                "config_length_64b": config_length,
                "load_config_address_equation": (
                    f"ddr_config_addr={hex(int(base, 16) >> 10)}; "
                    "base_addr=ddr_config_addr<<10"
                ),
            }
        )
    write_json(sca_path, sca)
    return records


def build_directory(destination: Path) -> Path:
    _assert_receipts()
    package = _extract(destination)
    for relative in (
        Path("TEST_PACKAGE_MANIFEST.json"),
        Path("workload/runtime/sca_cfg.json"),
        Path("workload/runtime/sca_cfg_D.json"),
    ):
        _replace_namespace(package / relative)

    shutil.copy2(
        RUNTIME_SOURCE,
        package / "package_tools/qlinearadd_node0007_server_runtime.py",
    )
    preload_records = _materialize_config_preloads(package)

    (package / "README.md").write_text(
        "# QLinearAdd node0007 config-preload functional fix v14\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "v13 dynamically proved slice_start_run but all expected physical LC "
        "enable bits remained zero. Its SCA preloaded execplan and tensor data "
        "but omitted all six frozen bitstreams addressed by Load_Config. v14 "
        "adds exactly those six package-local SCA preload records. Final JSON, "
        "mapping, bitstreams, execplan, SCA_D, tensor data, golden, qparams and "
        "observer logic are otherwise byte-identical after namespace change.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-config-preload-server-package-v14",
            "install_name": INSTALL_NAME,
            "package_class": (
                "FUNCTIONAL_CONFIG_MATERIALIZATION_FIX_WITH_DEFAULT_DIAGNOSTICS"
            ),
            "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "claim_boundary": (
                "node0007 frozen QLinearAdd configuration-only correctness "
                "baseline with six package-local SCA config preloads; no "
                "functional RTL change and no production/performance claim"
            ),
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "QUARANTINED_MISSING_SCA_CONFIG_PRELOADS",
                "numeric_workload_and_config_bits_unchanged": True,
            },
            "functional_configuration_fix": {
                "first_dynamic_divergence": (
                    "slice_start_run=1 but mapped physical LC2/4/6/13/18 "
                    "enable=0 and no qualified handshake"
                ),
                "root_cause": (
                    "sca_cfg.json omitted the six bitstream preload objects "
                    "targeted by execplan Load_Config"
                ),
                "changed_semantic_layer": "SCA_PRELOAD_MATERIALIZATION_ONLY",
                "functional_rtl_modified": False,
                "final_json_changed": False,
                "mapping_changed": False,
                "bitstream_bytes_changed": False,
                "execplan_bytes_changed": False,
                "sca_d_changed_except_namespace": False,
                "numeric_workload_or_qparam_changed": False,
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
        "validator": "tools/validate_qlinearadd_node0007_config_preload_v14.py",
        "report": REPORT_REL,
    }
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_config_preload_v14_server_package.py"
    )
    manifest["provenance"]["generation_index"] = {
        "path": INDEX.relative_to(ROOT).as_posix(),
        "sha256": INDEX_SHA256,
    }
    manifest["provenance"]["server_package_rule"] = {
        "path": SERVER_RULE.relative_to(ROOT).as_posix(),
        "sha256": SERVER_RULE_SHA256,
    }
    manifest["provenance"]["qlinearadd_rule"] = {
        "path": QADD_RULE.relative_to(ROOT).as_posix(),
        "sha256": QADD_RULE_SHA256,
    }
    manifest["provenance"]["common_operator_rule"] = {
        "path": COMMON_RULE.relative_to(ROOT).as_posix(),
        "sha256": COMMON_RULE_SHA256,
    }
    manifest["provenance"]["ndp_field_rule"] = {
        "path": NDP_RULE.relative_to(ROOT).as_posix(),
        "sha256": NDP_RULE_SHA256,
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
        if built != output:
            raise BuildError("unexpected output path")
        with tempfile.TemporaryDirectory(prefix="qadd-v14-repeat-") as raw:
            _, repeat_zip, repeat_records = _build_once(Path(raw))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": sha256(output) == sha256(repeat_zip),
                "repeat_zip_sha256": sha256(repeat_zip),
            }
        if not repeated["package_tree_equal"] or not repeated["zip_equal"]:
            raise BuildError("deterministic rebuild differs")
        digest = sha256(output)
        sidecar.write_text(
            f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
        )
        receipt: dict[str, Any] = {
            "schema": "qlinearadd-node0007-config-preload-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
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
