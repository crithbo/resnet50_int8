"""Fresh-identity reissue of isolated QAdd tail_round v50 after server extract pollution."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import build_qlinearadd_node0007_tailround_split_colfix_v50_package as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_qadd_n7_tailround_split_v50"
TARGET = "r5_qadd_n7_tailround_split_clean_v51"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_SHA = "c8d1b3c4d43e1a4ec2360226d882881413de6da4739b20a08df43aa70fa6cad3"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-clean-v51-package"
OUT_ZIP = OUT / f"{TARGET}.zip"
RULES = {
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.TARGET = TARGET
    base.SOURCE = SOURCE
    base.SOURCE_SHA = SOURCE_SHA
    base.RULES = RULES


def build_tree(destination: Path) -> Path:
    configure_base()
    package = base.extract(destination)
    base.replace_identity(package)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-tailround-split-clean-server-package-v51",
            "install_name": TARGET,
            "package_id": TARGET,
            "candidate_release": False,
            "successor": {
                "source": SOURCE_ID,
                "source_sha256": SOURCE_SHA,
                "reason": "fresh package/install/run identity after server v50 extraction directory failed manifest exact-set before compile",
                "changed_surface": [
                    "fresh identity and namespaces",
                    "current immutable rule receipts",
                    "manifest/source provenance"
                ],
                "frozen_surface": [
                    "single-stage op_tail_round workload",
                    "COL end=4 stride=2 materialized config",
                    "28 host diagnostic FP32 boundary payloads",
                    "28 UINT8 golden outputs",
                    "observer/canonical/runtime algorithms",
                    "2h timeout",
                    "functional RTL"
                ]
            },
            "source_assets": {
                **manifest.get("source_assets", {}),
                "v50_source_zip": {
                    "path": SOURCE.relative_to(ROOT).as_posix(),
                    "bytes": SOURCE.stat().st_size,
                    "sha256": SOURCE_SHA
                },
                "v50_server_preflight": {
                    "classification": "PACKAGE_EXTRACT_DIRECTORY_EXACT_SET_DIFFERED_BEFORE_COMPILE",
                    "compile_started": False,
                    "simulation_started": False,
                    "config_or_rtl_failure_evaluable": False
                }
            },
            "rule_receipts": {
                key: {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": base.sha(path),
                    "current_match": True
                }
                for key, path in RULES.items()
            },
            "final_zip_rule_self_audit": {
                "required": True,
                "status": "PENDING_EXACT_ZIP_AUDIT"
            },
            "provenance": {
                "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
                "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
                "generator": Path(__file__).relative_to(ROOT).as_posix()
            }
        }
    )
    manifest["files"] = base.records(package)
    base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    if OUT.exists():
        raise RuntimeError("fresh v51 output required")
    OUT.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="q51a-") as a_raw, tempfile.TemporaryDirectory(prefix="q51b-") as b_raw:
        a = build_tree(Path(a_raw))
        b = build_tree(Path(b_raw))
        za = Path(a_raw) / f"{TARGET}.zip"
        zb = Path(b_raw) / f"{TARGET}.zip"
        base.deterministic_zip(a, za)
        base.deterministic_zip(b, zb)
        if za.read_bytes() != zb.read_bytes() or base.sha(za) != base.sha(zb):
            raise RuntimeError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{base.sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {
        "schema": "qlinearadd-node0007-tailround-split-clean-build-v51",
        "status": "BUILT_PENDING_FINAL_AUDIT",
        "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": base.sha(OUT_ZIP)},
        "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": base.sha(sidecar)},
        "source_zip_sha256": SOURCE_SHA,
        "deterministic_double_build": True,
        "identity_only_reissue": True,
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "server_action": False
    }
    base.write_json(OUT / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
