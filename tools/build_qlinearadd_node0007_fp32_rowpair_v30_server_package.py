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
SOURCE_NAME = "r5_qadd_n7_split_c_pairmatrix_v29"
TARGET_NAME = "r5_qadd_n7_split_c_rowpairfix_v30"
SOURCE = PKG / SOURCE_NAME
SOURCE_ZIP = PKG / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "c92985b32e31c30ffcb023a6b637a6b059748e5395e2eabac2a65e3ae79c0af3"
PIPELINE = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-rowpair-v30/execplan/pipeline_output"
)
BUILD_RECEIPT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-rowpair-v30/build_receipt.json"
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
    for item in result.values():
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            path = item["path"].replace("\\", "/")
            if path.startswith("install/"):
                suffix = path.split("/", 3)[-1] if path.startswith("install/cfg_pkg/") else path.removeprefix("install/")
                item["path"] = f"install/cfg_pkg/{TARGET_NAME}/{suffix}"
    return result


def materialize(parent: Path) -> Path:
    out = parent / TARGET_NAME
    shutil.copytree(SOURCE, out)
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
    sca = {
        key: value
        for key, value in sca.items()
        if not key.startswith("op_fp32_add_matrix")
    }
    sca_d = json.loads((PIPELINE / "sca_cfg_D.json").read_text(encoding="utf-8"))
    sca_d = {
        key: value
        for key, value in sca_d.items()
        if key.startswith("op_fp32_add_matrixD_slice")
    }
    if len(sca_d) != 28:
        raise ValueError("FP32 readback exact-set differs")
    write_json(runtime / "sca_cfg.json", namespace_sca(sca))
    write_json(runtime / "sca_cfg_D.json", namespace_sca(sca_d))

    runner = out / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    if SOURCE_NAME in text:
        text = text.replace(SOURCE_NAME, TARGET_NAME)
    runner.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )
    readme = out / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace(SOURCE_NAME, TARGET_NAME)
        + "\nV30 changes only op_fp32_add transaction grouping: 32-byte streams, "
        "paired 16-byte Buffer_AG columns, and 9408 inner occurrences. "
        "It retains the v29 low-cost paired-ingress observer.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET_NAME
    manifest["claim"] = "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
    manifest["source_assets"]["split_c_pairmatrix_v29_source_zip"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_SHA,
        "immutable": True,
        "runtime_identity": "QUARANTINED_AFTER_V29_RETURN",
    }
    manifest["source_assets"]["fp32_rowpair_v30_build_receipt"] = {
        "path": BUILD_RECEIPT.relative_to(ROOT).as_posix(),
        "sha256": sha(BUILD_RECEIPT),
    }
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_fp32_rowpair_v30_server_package.py"
    )
    manifest["provenance"]["successor_reason"] = (
        "v29 dynamic 16B input write cannot satisfy 32B all-bank ARM read"
    )
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
    manifest["fp32_rowpair_correction"] = {
        "stage": "op_fp32_add",
        "transaction_bytes": 32,
        "mse_window_bytes": 16,
        "column_windows": [[0, 16], [16, 32]],
        "inner_occurrences": 9408,
        "outer_occurrences": 8,
        "total_bytes_per_slice": 2408448,
        "old_hang_boundary": "BUFFER0_BUFFER2_ARM_READ_ACCEPT",
        "observer_checkpoint_retained": True,
    }
    for key, path in RULES.items():
        manifest["rule_receipts"][key] = {
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha(path),
            "current_match": True,
        }
    manifest["final_zip_rule_self_audit"] = {
        "required": True,
        "status": "PENDING_POST_BUILD_DIRECT_FINAL_ZIP_AUDIT",
    }
    manifest["files"] = file_records(out, exclude_manifest=True)
    write_json(manifest_path, manifest)
    return out


def main() -> int:
    if sha(SOURCE_ZIP) != SOURCE_SHA or not BUILD_RECEIPT.is_file():
        raise ValueError("frozen source/build receipt differs")
    if TARGET.exists() or ZIP.exists():
        raise ValueError("fresh v30 package identity already exists")
    with tempfile.TemporaryDirectory(prefix="qadd-v30-a-") as first, tempfile.TemporaryDirectory(prefix="qadd-v30-b-") as second:
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
    sidecar.write_text(
        f"{sha(ZIP)}  {ZIP.name}\n", encoding="ascii", newline="\n"
    )
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
