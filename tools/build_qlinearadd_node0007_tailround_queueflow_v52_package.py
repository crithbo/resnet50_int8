"""Build one fresh isolated QAdd tail_round queue-flow diagnostic v52."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build_qlinearadd_node0007_tailround_split_colfix_v50_package as base


SOURCE_ID = "r5_qadd_n7_tailround_split_clean_v51"
TARGET = "r5_qadd_n7_tailround_queueflow_v52"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_SHA = "cf499102675dda4501e4e0c2e9cde1142985b3aca6b94a46edf7afb45f668141"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package"
OUT_ZIP = LOCAL / f"{TARGET}.zip"
ADDON = ROOT / "tools/qlinearadd_node0007_tailround_queueflow_v52.svh"
CANONICAL = ROOT / "tools/qlinearadd_node0007_tailround_queueflow_canonical_v52.py"
RETURN_REPORT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-clean-v51-return-analysis/report.json"
EPOCH = "20260810-first-fresh-extra-audit-v1"
RULES = {
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}
CANDIDATES = [
    "C_BAG_PAIR_DEQUEUE",
    "C_RDAG_ELIGIBILITY_READ_REQUEST",
    "C_WR_PREPARED_SECOND_BEAT",
    "C_CHANNEL1_OUTPUT_DELIVERY",
]


class BuildError(RuntimeError):
    pass


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.TARGET = TARGET
    base.SOURCE = SOURCE
    base.SOURCE_SHA = SOURCE_SHA
    base.RULES = RULES


def cheap_prebuild_aggregate() -> dict:
    errors: list[str] = []
    if not SOURCE.is_file() or base.sha(SOURCE) != SOURCE_SHA:
        errors.append("frozen v51 source ZIP identity differs")
    for path in (ADDON, CANONICAL, RETURN_REPORT, *RULES.values()):
        if not path.is_file():
            errors.append(f"missing input: {path.relative_to(ROOT).as_posix()}")
    if SOURCE.is_file():
        import zipfile
        with zipfile.ZipFile(SOURCE) as archive:
            if archive.testzip() is not None:
                errors.append("frozen v51 source CRC differs")
            if f"{SOURCE_ID}/TEST_PACKAGE_MANIFEST.json" not in archive.namelist():
                errors.append("frozen v51 source manifest absent")
    report = {
        "schema": "qlinearadd-node0007-v52-cheap-prebuild-aggregate-v1",
        "pass": not errors,
        "errors": errors,
        "top_level_invocations": 1,
        "all_errors_collected": True,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "bound_package_id": TARGET,
        "source_zip_sha256": SOURCE_SHA,
        "numeric_workload_config_golden_repeated": False,
    }
    base.write_json(LOCAL / "cheap_prebuild_aggregate.json", report)
    return report


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "qlinearadd_node0007_tailround_split_canonical_v50.py": "qlinearadd_node0007_tailround_queueflow_canonical_v52.py",
        "+RETURN_OBSERVER +RETURN_OBS_SLICE=0": "+RETURN_OBSERVER +QADD_TAILROUND_QUEUEFLOW +RETURN_OBS_SLICE=0",
        "feature=QADD_TAILROUND_SPLIT_V50\\nargv_enabled=true\\ntime0_marker=QADD_TAILROUND_SPLIT_V50": "feature=QADD_TAILROUND_QUEUEFLOW_V52\\nargv_enabled=true\\ntime0_marker=QADD_TAILROUND_QUEUEFLOW_V52",
        "tail=tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh\\nmacro=NATIVE_RETURN_OBSERVER_ENABLE\\nplusarg=RETURN_OBSERVER": "tail=tb_probe/qlinearadd_node0007_tailround_flow_tail_v47.svh\\nqueueflow=tb_probe/qlinearadd_node0007_tailround_queueflow_v52.svh\\nmacro=NATIVE_RETURN_OBSERVER_ENABLE\\nplusarg=RETURN_OBSERVER,QADD_TAILROUND_QUEUEFLOW",
    }
    for before, after in replacements.items():
        if text.count(before) != 1:
            raise BuildError(f"runner patch anchor differs: {before!r} count={text.count(before)}")
        text = text.replace(before, after, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_observer(package: Path) -> None:
    native = package / "tb_probe/native_return_observer.svh"
    text = native.read_text(encoding="utf-8")
    anchor = '`include "qlinearadd_node0007_tailround_flow_tail_v47.svh"'
    replacement = anchor + '\n\n`include "qlinearadd_node0007_tailround_queueflow_v52.svh"'
    if text.count(anchor) != 1 or "tailround_queueflow_v52" in text:
        raise BuildError("native observer include anchor differs")
    native.write_text(text.replace(anchor, replacement, 1), encoding="utf-8", newline="\n")
    shutil.copy2(ADDON, package / "tb_probe/qlinearadd_node0007_tailround_queueflow_v52.svh")


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    matrix = {
        "schema": "qlinearadd-node0007-tailround-queueflow-candidate-matrix-v52",
        "candidate_ids": CANDIDATES,
        "pairwise_distinguishable": True,
        "observations": [
            {"id": "O_BAG_PAIR", "qualified": "BAG_ENQ/BAG_DEQ with ROW/COL/tag", "distinguishes": ["C_BAG_PAIR_DEQUEUE"]},
            {"id": "O_RDAG", "qualified": "RDAG_ENQ/DEQ/RREQ with count/pointer/valid/ready", "distinguishes": ["C_RDAG_ELIGIBILITY_READ_REQUEST"]},
            {"id": "O_PREPARED", "qualified": "WR_REQ/WR_PREPARED with prepared count/data/hold", "distinguishes": ["C_WR_PREPARED_SECOND_BEAT"]},
            {"id": "O_CHANNEL", "qualified": "WR_OB_ENQ and MSE4 request/wdata by channel", "distinguishes": ["C_CHANNEL1_OUTPUT_DELIVERY"]},
        ],
        "level_only_state": "Q52_STATE; never progress",
        "event_budget": 96,
    }
    base.write_json(package / "diagnostics/tailround_queueflow_candidate_matrix_v52.json", matrix)
    manifest.update({
        "schema": "qlinearadd-node0007-tailround-queueflow-server-package-v52",
        "install_name": TARGET,
        "package_id": TARGET,
        "candidate_release": False,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "first_fresh_extra_audit": {
            "epoch_id": EPOCH,
            "notification_acknowledged": True,
            "first_fresh_after_change": True,
            "bound_package_id": TARGET,
            "status": "PENDING_EXACT_FINAL_ZIP_INDEPENDENT_AUDIT",
        },
        "source_assets": {
            **manifest.get("source_assets", {}),
            "v51_source_zip": {
                "path": SOURCE.relative_to(ROOT).as_posix(),
                "bytes": SOURCE.stat().st_size,
                "sha256": SOURCE_SHA,
            },
            "v51_return_analysis": {
                "path": RETURN_REPORT.relative_to(ROOT).as_posix(),
                "bytes": RETURN_REPORT.stat().st_size,
                "sha256": base.sha(RETURN_REPORT),
            },
        },
        "successor": {
            "source": SOURCE_ID,
            "source_sha256": SOURCE_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "reason": "v51 froze after finite Buffer_AG/RDAG/WR activity without uniquely identifying the first blocking leaf",
            "changed_surface": [
                "fresh identity and namespace",
                "runtime-gated bounded queue-flow observer",
                "queue-flow canonical parser and candidate matrix",
                "current immutable rule receipts",
            ],
            "frozen_surface": [
                "single op_tail_round workload",
                "COL end=4 stride=2 config",
                "28 host diagnostic FP32 inputs",
                "28 UINT8 golden outputs",
                "numeric/W3/qparams/tail semantics",
                "2h timeout",
                "functional RTL",
            ],
        },
        "observer_contract": {
            **manifest.get("observer_contract", {}),
            "queueflow_source": "tb_probe/qlinearadd_node0007_tailround_queueflow_v52.svh",
            "canonical_parser": "package_tools/qlinearadd_node0007_tailround_queueflow_canonical_v52.py",
            "runtime_plusarg": "QADD_TAILROUND_QUEUEFLOW",
            "time0_marker": "QADD_TAILROUND_QUEUEFLOW_V52",
            "qualified_counter_clock": "clk_sg",
            "snapshot_clock": "clk_db",
            "event_budget": 96,
            "candidate_ids": CANDIDATES,
            "level_is_progress": False,
        },
        "rule_receipts": {
            name: {
                "path": rule.relative_to(ROOT).as_posix(),
                "sha256": base.sha(rule),
                "current_match": True,
            }
            for name, rule in RULES.items()
        },
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": "BLOCKING_REVALIDATE",
            "runner_compile_finalizer": "BLOCKING_REVALIDATE",
            "package_local_hdl": "BLOCKING_CHANGED_OBSERVER",
            "materialized_config": "RECEIPT_REUSE_BYTE_EQUAL",
            "observer_canonical": "BLOCKING_CHANGED_PREDICATE",
            "return_result_conjunction": "BLOCKING_LOCAL_CONTRACT_DYNAMIC_PENDING",
            "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
            "functional_RTL": "RECORD_ONLY_UNMODIFIED",
            "first_fresh_extra_audit": "BLOCKING_PENDING",
        },
        "final_zip_rule_self_audit": {"required": True, "status": "PENDING_EXACT_ZIP_AUDIT"},
        "provenance": {
            "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "generator": Path(__file__).relative_to(ROOT).as_posix(),
        },
    })
    manifest["files"] = base.records(package)
    base.write_json(path, manifest)


def build_tree(destination: Path) -> Path:
    configure_base()
    package = base.extract(destination)
    base.replace_identity(package)
    old_parser = package / "package_tools/qlinearadd_node0007_tailround_split_canonical_v50.py"
    old_parser.unlink()
    shutil.copy2(CANONICAL, package / "package_tools/qlinearadd_node0007_tailround_queueflow_canonical_v52.py")
    patch_runner(package)
    patch_observer(package)
    update_manifest(package)
    base.update_path_budget(package)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    if LOCAL.exists():
        raise BuildError("fresh v52 output required")
    LOCAL.mkdir(parents=True)
    cheap = cheap_prebuild_aggregate()
    if not cheap["pass"]:
        raise BuildError(f"cheap prebuild aggregate failed: {cheap['errors']}")
    with tempfile.TemporaryDirectory(prefix="q52a-") as first, tempfile.TemporaryDirectory(prefix="q52b-") as second:
        a = build_tree(Path(first))
        b = build_tree(Path(second))
        za = Path(first) / f"{TARGET}.zip"
        zb = Path(second) / f"{TARGET}.zip"
        configure_base()
        base.deterministic_zip(a, za)
        base.deterministic_zip(b, zb)
        if base.sha(za) != base.sha(zb) or za.read_bytes() != zb.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{base.sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {
        "schema": "qlinearadd-node0007-tailround-queueflow-build-v52",
        "status": "BUILT_UPLOAD_HOLD_PENDING_FIRST_FRESH_EXTRA_AUDIT",
        "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": base.sha(OUT_ZIP)},
        "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": base.sha(sidecar)},
        "source_zip_sha256": SOURCE_SHA,
        "deterministic_double_build": True,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "cheap_prebuild_aggregate_invocations": 1,
        "final_zip_count": 1,
        "numeric_workload_config_golden_repeated": False,
        "server_action": False,
    }
    base.write_json(LOCAL / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
