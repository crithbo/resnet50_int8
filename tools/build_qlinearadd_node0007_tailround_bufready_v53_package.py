"""Build one fresh isolated QAdd tail_round Buffer5-read-ready diagnostic v53."""

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


SOURCE_ID = "r5_qadd_n7_tailround_queueflow_v52"
TARGET = "r5_qadd_n7_tailround_bufready_v53"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_SHA = "7ed0e6e84d32900b015f70091b7b8bbefae074a63f019d75026f8b25bf9f52d0"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-bufready-v53-package"
OUT_ZIP = LOCAL / f"{TARGET}.zip"
ADDON = ROOT / "tools/qlinearadd_node0007_tailround_bufready_v53.svh"
CANONICAL = ROOT / "tools/qlinearadd_node0007_tailround_bufready_canonical_v53.py"
RETURN_REPORT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-return-analysis/report.json"
PRIOR_FIRST_FRESH = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package/first_fresh_extra_audit/validation.json"
PRIOR_FIRST_FRESH_SHA = "ed8e31a08cb76f0b8994ebaf29247dd1f0b603f0861acf710afcbb5219e4e976"
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
    "C_PINGPONG_PORT_SELECTION",
    "C_BUFFER5_MRM_REQUEST_DECODE",
    "C_BUFFER5_ROW_BANK_LANE_VALIDITY",
    "C_BUFFER5_WRITE_CLEAR_ORDER",
    "C_BUFFER5_READ_ACCEPT",
]


class BuildError(RuntimeError):
    pass


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.TARGET = TARGET
    base.SOURCE = SOURCE
    base.SOURCE_SHA = SOURCE_SHA
    base.RULES = RULES


def prebuild_aggregate() -> dict:
    errors: list[str] = []
    if not SOURCE.is_file() or base.sha(SOURCE) != SOURCE_SHA:
        errors.append("frozen v52 source ZIP identity differs")
    for path in (ADDON, CANONICAL, RETURN_REPORT, PRIOR_FIRST_FRESH, *RULES.values()):
        if not path.is_file():
            errors.append(f"missing input: {path.relative_to(ROOT).as_posix()}")
    if PRIOR_FIRST_FRESH.is_file() and base.sha(PRIOR_FIRST_FRESH) != PRIOR_FIRST_FRESH_SHA:
        errors.append("prior first-fresh PASS receipt differs")
    report = {
        "schema": "qlinearadd-node0007-v53-prebuild-aggregate-v1",
        "pass": not errors,
        "errors": errors,
        "top_level_invocations": 1,
        "all_errors_collected": True,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": False,
        "prior_first_fresh_pass_sha256": PRIOR_FIRST_FRESH_SHA,
        "bound_package_id": TARGET,
        "source_zip_sha256": SOURCE_SHA,
        "numeric_workload_config_golden_repeated": False,
    }
    base.write_json(LOCAL / "prebuild_aggregate.json", report)
    return report


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    replacements = {
        "qlinearadd_node0007_tailround_queueflow_canonical_v52.py": "qlinearadd_node0007_tailround_bufready_canonical_v53.py",
        "+RETURN_OBSERVER +QADD_TAILROUND_QUEUEFLOW +RETURN_OBS_SLICE=0": "+RETURN_OBSERVER +QADD_TAILROUND_BUFREADY +RETURN_OBS_SLICE=0",
        "feature=QADD_TAILROUND_QUEUEFLOW_V52\\nargv_enabled=true\\ntime0_marker=QADD_TAILROUND_QUEUEFLOW_V52": "feature=QADD_TAILROUND_BUFREADY_V53\\nargv_enabled=true\\ntime0_marker=QADD_TAILROUND_BUFREADY_V53",
        "queueflow=tb_probe/qlinearadd_node0007_tailround_queueflow_v52.svh\\nmacro=NATIVE_RETURN_OBSERVER_ENABLE\\nplusarg=RETURN_OBSERVER,QADD_TAILROUND_QUEUEFLOW": "bufready=tb_probe/qlinearadd_node0007_tailround_bufready_v53.svh\\nmacro=NATIVE_RETURN_OBSERVER_ENABLE\\nplusarg=RETURN_OBSERVER,QADD_TAILROUND_BUFREADY",
    }
    for before, after in replacements.items():
        if text.count(before) != 1:
            raise BuildError(f"runner patch anchor differs: {before!r} count={text.count(before)}")
        text = text.replace(before, after, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_observer(package: Path) -> None:
    native = package / "tb_probe/native_return_observer.svh"
    text = native.read_text(encoding="utf-8")
    old_include = '`include "qlinearadd_node0007_tailround_queueflow_v52.svh"'
    new_include = '`include "qlinearadd_node0007_tailround_bufready_v53.svh"'
    if text.count(old_include) != 1 or "tailround_bufready_v53" in text:
        raise BuildError("native observer include anchor differs")
    native.write_text(text.replace(old_include, new_include, 1), encoding="utf-8", newline="\n")
    old_addon = package / "tb_probe/qlinearadd_node0007_tailround_queueflow_v52.svh"
    old_addon.unlink()
    shutil.copy2(ADDON, package / "tb_probe/qlinearadd_node0007_tailround_bufready_v53.svh")


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    matrix = {
        "schema": "qlinearadd-node0007-tailround-bufready-candidate-matrix-v53",
        "candidate_ids": CANDIDATES,
        "pairwise_distinguishable": True,
        "observations": [
            {"id": "O_SELECT", "kind": "state", "predicate": "selected_ready == ready[pingpong]", "distinguishes": ["C_PINGPONG_PORT_SELECTION"]},
            {"id": "O_MRM", "kind": "state", "predicate": "req_valid && !req_rw && rd_en with exact row/strb", "distinguishes": ["C_BUFFER5_MRM_REQUEST_DECODE"]},
            {"id": "O_VALID", "kind": "state", "predicate": "failed_banks=rd_en&~bank_ready and missing_lanes=req_strb&~valid_at_req", "distinguishes": ["C_BUFFER5_ROW_BANK_LANE_VALIDITY"]},
            {"id": "O_ORDER", "kind": "qualified_event", "predicate": "BUF5_WRITE_ACCEPT / BUF5_VALID_CLEAR ordered timestamps", "distinguishes": ["C_BUFFER5_WRITE_CLEAR_ORDER"]},
            {"id": "O_READ", "kind": "qualified_event", "predicate": "rd_en && rreq_ready", "distinguishes": ["C_BUFFER5_READ_ACCEPT"]},
        ],
        "level_only_state": "Q53_STATE; never counted as progress",
        "event_budget": 96,
    }
    base.write_json(package / "diagnostics/tailround_bufready_candidate_matrix_v53.json", matrix)
    manifest.update({
        "schema": "qlinearadd-node0007-tailround-bufready-server-package-v53",
        "install_name": TARGET,
        "package_id": TARGET,
        "candidate_release": False,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "first_fresh_extra_audit": {
            "epoch_id": EPOCH,
            "first_fresh_after_change": False,
            "prior_pass_path": PRIOR_FIRST_FRESH.relative_to(ROOT).as_posix(),
            "prior_pass_sha256": PRIOR_FIRST_FRESH_SHA,
            "status": "PRIOR_FAMILY_EPOCH_PASS_BOUND_CHANGED_SURFACE_REVALIDATED",
        },
        "source_assets": {
            **manifest.get("source_assets", {}),
            "v52_source_zip": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": SOURCE_SHA},
            "v52_return_analysis": {"path": RETURN_REPORT.relative_to(ROOT).as_posix(), "bytes": RETURN_REPORT.stat().st_size, "sha256": base.sha(RETURN_REPORT)},
        },
        "successor": {
            "source": SOURCE_ID,
            "source_sha256": SOURCE_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "reason": "v52 proved RDAG valid/full and WR ready but buf2mse_rreq_ready low; remaining selected Buffer5 read-ready leaves were not unique",
            "changed_surface": [
                "fresh identity and namespace",
                "stable selected-slice observer identity without procedural-scope %m",
                "bounded pingpong/Buffer5 request/valid-bank/read-ready observer",
                "v53 canonical predicate and candidate matrix",
                "current immutable rule receipts",
            ],
            "frozen_surface": [
                "single op_tail_round workload",
                "COL end=4 stride=2 config and all bitstream/execplan/SCA payload",
                "28 host diagnostic FP32 inputs and UINT8 golden outputs",
                "numeric/W3/qparams/tail semantics",
                "2h timeout",
                "functional RTL",
            ],
        },
        "observer_contract": {
            **manifest.get("observer_contract", {}),
            "bufready_source": "tb_probe/qlinearadd_node0007_tailround_bufready_v53.svh",
            "canonical_parser": "package_tools/qlinearadd_node0007_tailround_bufready_canonical_v53.py",
            "runtime_plusarg": "QADD_TAILROUND_BUFREADY",
            "time0_marker": "QADD_TAILROUND_BUFREADY_V53",
            "qualified_counter_clock": "clk_sg",
            "snapshot_clock": "clk_db",
            "selected_owner": {"group": 0, "local_slice": 0, "source": "RETURN_OBS_SLICE=0"},
            "event_budget": 96,
            "candidate_ids": CANDIDATES,
            "level_is_progress": False,
        },
        "rule_receipts": {
            name: {"path": rule.relative_to(ROOT).as_posix(), "sha256": base.sha(rule), "current_match": True}
            for name, rule in RULES.items()
        },
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": "BLOCKING_REVALIDATE",
            "runner_compile_finalizer": "BLOCKING_CHANGED_IDENTITY_FEATURE_REVALIDATE",
            "package_local_hdl": "BLOCKING_CHANGED_OBSERVER_REVALIDATE",
            "materialized_config": "NOT_APPLICABLE_BYTE_EQUAL_RECEIPT_REUSE",
            "observer_canonical": "BLOCKING_CHANGED_PREDICATE_TRACE",
            "return_result_conjunction": "BLOCKING_LOCAL_CONTRACT_DYNAMIC_PENDING",
            "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
            "functional_RTL": "RECORD_ONLY_UNMODIFIED",
            "first_fresh_extra_audit": "RECEIPT_REUSE_PRIOR_PASS_PLUS_CHANGED_SURFACE_AUDIT",
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
    old_parser = package / "package_tools/qlinearadd_node0007_tailround_queueflow_canonical_v52.py"
    old_parser.unlink()
    shutil.copy2(CANONICAL, package / "package_tools/qlinearadd_node0007_tailround_bufready_canonical_v53.py")
    patch_runner(package)
    patch_observer(package)
    update_manifest(package)
    base.update_path_budget(package)
    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 isolated tail_round Buffer5 readiness v53\n\n"
        "Run: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. The frozen host FP32 boundary stimulus is not producer evidence. This package localizes selected Buffer5 read readiness and cannot claim upstream execution, full-chain correctness, E3, E4 or E5.\n",
        encoding="utf-8", newline="\n",
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    if LOCAL.exists():
        raise BuildError("fresh v53 output required")
    LOCAL.mkdir(parents=True)
    prebuild = prebuild_aggregate()
    if not prebuild["pass"]:
        raise BuildError(f"prebuild aggregate failed: {prebuild['errors']}")
    with tempfile.TemporaryDirectory(prefix="q53a-") as first, tempfile.TemporaryDirectory(prefix="q53b-") as second:
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
        "schema": "qlinearadd-node0007-tailround-bufready-build-v53",
        "status": "BUILT_UPLOAD_HOLD_PENDING_EXACT_FINAL_ZIP_AUDIT",
        "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": base.sha(OUT_ZIP)},
        "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": base.sha(sidecar)},
        "source_zip_sha256": SOURCE_SHA,
        "deterministic_double_build": True,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": False,
        "prior_first_fresh_pass_sha256": PRIOR_FIRST_FRESH_SHA,
        "prebuild_aggregate_invocations": 1,
        "final_zip_count": 1,
        "numeric_workload_config_golden_repeated": False,
        "server_action": False,
    }
    base.write_json(LOCAL / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
