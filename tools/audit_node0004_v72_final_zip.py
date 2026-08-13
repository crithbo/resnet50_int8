from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v72_token_origin_accept_diag"
SOURCE_SHA = "8cab1c7762496cf25ecde9057388d88c428711a2e52dc5a1e8e610a66840b452"
RULES = {
    "agent": ROOT / ".agents/agent.md",
    "plan_mutable": ROOT / ".agents/plan.md",
    "index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common": ROOT / ".agents/rules/算子配置规则.md",
    "ndp": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "int8_sa": ROOT / ".agents/rules/INT8_SA点积专项规则.md",
    "readme": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shaf(path: Path) -> str:
    return sha(path.read_bytes())


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--sidecar", required=True, type=Path)
    ap.add_argument("--source-v71", required=True, type=Path)
    ap.add_argument("--build-report", required=True, type=Path)
    ap.add_argument("--family-report", required=True, type=Path)
    ap.add_argument("--shared-report", required=True, type=Path)
    ap.add_argument("--observer-report", required=True, type=Path)
    ap.add_argument("--runner-report", required=True, type=Path)
    ap.add_argument("--return-report", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    checks: dict[str, bool] = {}
    zip_sha = shaf(args.zip)
    checks["source_identity"] = shaf(args.source_v71) == SOURCE_SHA
    checks["sidecar_identity"] = args.sidecar.read_text(encoding="ascii").split() == [zip_sha, args.zip.name]
    with zipfile.ZipFile(args.zip) as archive, zipfile.ZipFile(args.source_v71) as source_archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = archive.testzip() is None
        checks["single_root"] = {name.split("/", 1)[0] for name in names} == {PACKAGE}
        checks["no_duplicates"] = len(names) == len(set(names))
        checks["safe_paths"] = all(not PurePosixPath(item.filename).is_absolute()
            and ".." not in PurePosixPath(item.filename).parts and "\\" not in item.filename for item in infos)
        checks["no_symlinks"] = all(not stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF) for item in infos)
        target = {"/".join(item.filename.split("/")[1:]): archive.read(item)
                  for item in infos if not item.is_dir()}
        source_root = source_archive.namelist()[0].split("/", 1)[0]
        source = {"/".join(item.filename.split("/")[1:]): source_archive.read(item)
                  for item in source_archive.infolist() if not item.is_dir()}
        manifest = json.loads(target["package_manifest.json"])
        actual = {path: sha(data) for path, data in target.items() if path != "package_manifest.json"}
        checks["manifest_exact_set"] = set(manifest["files"]) == set(actual)
        checks["manifest_receipts"] = manifest["files"] == actual
        checks["manifest_identity"] = (
            manifest["install_name"] == PACKAGE
            and manifest["source_package_sha256"] == SOURCE_SHA
            and manifest["classification"] == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest["candidate_release"] is False
            and manifest["configuration_rebuilt"] is False
            and manifest["node0004_workload_rebuilt"] is False
            and manifest["numeric_analysis_repeated"] is False
            and manifest["functional_rtl_modified"] is False
            and manifest["server_action"] is False)
        feature = manifest["diagnostic_features"]["RETURN_OBS_TOKEN_ORIGIN_ACCEPT"]
        checks["feature_contract"] = (
            feature["runtime_enable_parameter"] == "+RETURN_OBS_TOKEN_ORIGIN_ACCEPT"
            and feature["edge_schema"] == "TOKEN_ORIGIN_ACCEPT_EDGE_V2"
            and feature["multiclass_strategy"] == "ALL_CLASS_BITSET_PER_RECORD"
            and feature["qualification"]["mem_queue_write"] == "mem_ag_idx_queue_wr_en && !mem_ag_idx_queue_full"
            and feature["qualification"]["buf_queue_write"] == "buf_ag_idx_queue_wr_en && !buf_ag_idx_queue_full")
        runner = target["PREPARE_AND_RUN.sh"].decode()
        checks["feature_actual_argv"] = runner.count(
            " +RETURN_OBS_TOKEN_ORIGIN_ACCEPT +RETURN_OBS_TOKEN_ORIGIN_ACCEPT_LIMIT=128") == 2
        checks["old_buggy_feature_absent"] = " +RETURN_OBS_TOKEN_ORIGIN +RETURN_OBS_TOKEN_ORIGIN_LIMIT=128" not in runner
        checks["install_only_v2"] = json.loads(target["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])["required_preexisting_parents"] == ["install"]
        checks["fresh_provenance"] = "provenance/v71_to_v72_token_origin_accept.json" in target
        frozen = [path for path in source if (path.startswith("workload/") or "golden" in path.lower() or path.endswith(".bin")) and path in target]
        checks["frozen_payload"] = bool(frozen) and all(
            target[path].replace(PACKAGE.encode(), source_root.encode()) == source[path] for path in frozen)
        receipts = manifest.get("active_receipts", {})
        checks["current_rule_receipts"] = (
            receipts.get("generation_index_sha256") == shaf(RULES["index"])
            and receipts.get("server_package_rule_sha256") == shaf(RULES["server"])
            and receipts.get("int8_sa_rule_sha256") == shaf(RULES["int8_sa"]))

    family = load(args.family_report)
    shared = load(args.shared_report)
    observer = load(args.observer_report)
    runner_report = load(args.runner_report)
    return_report = load(args.return_report)
    build = load(args.build_report)
    checks["deterministic_build"] = build.get("deterministic_rebuild_equal") is True
    checks["family_report"] = family.get("valid") is True
    scenarios = shared.get("scenarios", {})
    checks["shared_layout_six_paths"] = (
        set(scenarios) == {"normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"}
        and all(row.get("fixed_result_return_published") is True and row.get("root_exact_set_unchanged") is True
                for row in scenarios.values()))
    checks["observer_report"] = observer.get("valid") is True
    checks["runner_report"] = runner_report.get("valid") is True
    checks["return_report"] = return_report.get("valid") is True
    checks["actual_consumer_hdl_controls"] = all(observer.get("checks", {}).get(name) is True for name in (
        "focused_syntax_scope_positive", "missing_declaration_negative", "actual_consumer_typo_negative"))
    checks["qualified_predicate_controls"] = all(observer.get("checks", {}).get(name) is True for name in (
        "accepted_write_predicates", "attempt_and_full_state_exposed", "predicate_trace_exact",
        "stable_full_attempt_zero_progress", "old_attempt_only_negative_fails", "multiclass_edge_no_loss_trace"))
    matrix = {
        "package_bootstrap_path_runtime_d": {"applicability": "blocking_applicable", "blocking": True,
            "pass": checks["family_report"] and checks["shared_layout_six_paths"]},
        "runner_compile_finalizer": {"applicability": "blocking_applicable", "blocking": True,
            "pass": checks["family_report"] and checks["runner_report"]},
        "package_local_hdl_changed": {"applicability": "blocking_applicable", "blocking": True,
            "pass": checks["observer_report"] and checks["actual_consumer_hdl_controls"]},
        "materialized_config": {"applicability": "not_applicable_byte_equal", "blocking": False, "pass": True},
        "observer_canonical_changed": {"applicability": "blocking_applicable", "blocking": True,
            "pass": checks["observer_report"] and checks["qualified_predicate_controls"]},
        "return_result_gate": {"applicability": "blocking_applicable", "blocking": True,
            "pass": checks["return_report"]},
        "numeric_w3_golden": {"applicability": "record_only_byte_equal", "blocking": False,
            "pass": checks["frozen_payload"]},
        "unrelated_rtl": {"applicability": "not_applicable", "blocking": False, "pass": True},
    }
    checks["release_gate_matrix"] = all((not row["blocking"]) or row["pass"] for row in matrix.values())
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "node0004-v72-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": str(args.zip.resolve()), "bytes": args.zip.stat().st_size, "sha256": zip_sha},
        "current_rule_receipts": {name: {"path": str(path), "bytes": path.stat().st_size, "sha256": shaf(path)}
                                  for name, path in RULES.items()},
        "release_gate_matrix": matrix,
        "claim_boundary": "Exact final ZIP and corrected token-origin accept diagnostic only; no DUT terminal/formal-D/E4/E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "sha": zip_sha}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
