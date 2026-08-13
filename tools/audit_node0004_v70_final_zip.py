from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v70_branch_owner_diag"
SOURCE_SHA = "e6c94bf8b38e8e0ff7aed6984782a874a665938930dc5f91357323592c2e88eb"
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
    ap.add_argument("--source-v69", required=True, type=Path)
    ap.add_argument("--build-report", required=True, type=Path)
    ap.add_argument("--family-report", required=True, type=Path)
    ap.add_argument("--shared-report", required=True, type=Path)
    ap.add_argument("--observer-report", required=True, type=Path)
    ap.add_argument("--runner-report", required=True, type=Path)
    ap.add_argument("--return-report", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args(); checks: dict[str, bool] = {}; zsha = shaf(a.zip)
    checks["source_identity"] = shaf(a.source_v69) == SOURCE_SHA
    checks["sidecar_identity"] = a.sidecar.read_text(encoding="ascii").split() == [zsha, a.zip.name]
    with zipfile.ZipFile(a.zip) as z, zipfile.ZipFile(a.source_v69) as source_zip:
        infos = z.infolist(); names = [i.filename for i in infos]
        checks["crc"] = z.testzip() is None
        checks["single_root"] = {name.split("/", 1)[0] for name in names} == {PACKAGE}
        checks["no_duplicates"] = len(names) == len(set(names))
        checks["safe_paths"] = all(not PurePosixPath(i.filename).is_absolute()
            and ".." not in PurePosixPath(i.filename).parts and "\\" not in i.filename for i in infos)
        checks["no_symlinks"] = all(not stat.S_ISLNK((i.external_attr >> 16) & 0xFFFF) for i in infos)
        target = {"/".join(i.filename.split("/")[1:]): z.read(i) for i in infos if not i.is_dir()}
        source_root = source_zip.namelist()[0].split("/", 1)[0]
        source = {"/".join(i.filename.split("/")[1:]): source_zip.read(i)
                  for i in source_zip.infolist() if not i.is_dir()}
        manifest = json.loads(target["package_manifest.json"])
        actual = {p: sha(b) for p, b in target.items() if p != "package_manifest.json"}
        checks["manifest_exact_set"] = set(manifest["files"]) == set(actual)
        checks["manifest_receipts"] = manifest["files"] == actual
        checks["manifest_identity"] = (manifest["install_name"] == PACKAGE
            and manifest["source_package_sha256"] == SOURCE_SHA
            and manifest["classification"] == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest["candidate_release"] is False and manifest["configuration_rebuilt"] is False
            and manifest["node0004_workload_rebuilt"] is False and manifest["numeric_analysis_repeated"] is False
            and manifest["functional_rtl_modified"] is False and manifest["server_action"] is False)
        feature = manifest["diagnostic_features"]["RETURN_OBS_BRANCH_OWNER"]
        checks["feature_contract"] = (feature["runtime_enable_parameter"] == "+RETURN_OBS_BRANCH_OWNER"
            and feature["qualified_event_budget"] == 128 and feature["non_progress_state_budget"] == 8
            and feature["state_activity_consumes_qualified_budget"] is False
            and set(feature["candidate_matrix"]) == {"configured_buffer_schedule_exceeds_descriptor_schedule",
                "descriptor_terminal_tag_mismatch", "descriptor_unaware_prefetch",
                "buffer_return_replay_or_stale_lifetime"})
        runner = target["PREPARE_AND_RUN.sh"].decode()
        token = " +RETURN_OBS_BRANCH_OWNER +RETURN_OBS_BRANCH_OWNER_LIMIT=128 +RETURN_OBS_BRANCH_OWNER_STATE_LIMIT=8"
        checks["feature_actual_argv"] = runner.count(token) == 2
        checks["triggered_profile_present"] = "provenance/server_triggered_causal_observability_v70.json" in target
        checks["install_only_v2"] = json.loads(target["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])["required_preexisting_parents"] == ["install"]
        checks["fresh_provenance"] = "provenance/v69_to_v70_branch_owner.json" in target
        frozen = [p for p in source if (p.startswith("workload/") or "golden" in p.lower() or p.endswith(".bin")) and p in target]
        checks["frozen_payload"] = bool(frozen) and all(
            target[p].replace(PACKAGE.encode(), source_root.encode()) == source[p] for p in frozen)
        receipts = manifest.get("active_receipts", {})
        checks["current_rule_receipts"] = (
            receipts.get("generation_index_sha256") == shaf(RULES["index"])
            and receipts.get("server_package_rule_sha256") == shaf(RULES["server"])
            and receipts.get("int8_sa_rule_sha256") == shaf(RULES["int8_sa"]))

    observer = load(a.observer_report)
    reports = {"build": load(a.build_report).get("deterministic_rebuild_equal") is True,
        "family": load(a.family_report).get("valid") is True, "shared": load(a.shared_report).get("pass") is True,
        "observer": observer.get("valid") is True, "runner": load(a.runner_report).get("valid") is True,
        "return": load(a.return_report).get("valid") is True}
    checks.update({f"{key}_report": value for key, value in reports.items()})
    checks["triggered_profile_public_validation"] = observer.get("checks", {}).get("public_triggered_profile") is True
    checks["separate_budget_and_format_trace"] = (
        observer.get("checks", {}).get("separate_budget_logic") is True
        and observer.get("checks", {}).get("logger_parser_exact_format_trace") is True)
    checks["actual_consumer_hdl_controls"] = all(observer.get("checks", {}).get(k) is True for k in (
        "focused_syntax_scope_positive", "missing_declaration_negative", "actual_consumer_typo_negative"))
    matrix = {
        "package_bootstrap_path_runtime_d": {"applicability": "receipt_reuse", "blocking": True, "pass": checks["family_report"] and checks["shared_report"]},
        "runner_compile_finalizer": {"applicability": "receipt_reuse", "blocking": True, "pass": checks["family_report"] and checks["runner_report"]},
        "package_local_hdl_changed": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["observer_report"] and checks["actual_consumer_hdl_controls"]},
        "materialized_config": {"applicability": "not_applicable_byte_equal", "blocking": False, "pass": True},
        "observer_canonical_changed": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["observer_report"] and checks["triggered_profile_public_validation"] and checks["separate_budget_and_format_trace"]},
        "return_result_gate": {"applicability": "receipt_reuse", "blocking": True, "pass": checks["return_report"]},
        "numeric_w3_golden": {"applicability": "record_only_byte_equal", "blocking": False, "pass": checks["frozen_payload"]},
        "unrelated_rtl": {"applicability": "not_applicable", "blocking": False, "pass": True},
    }
    checks["release_gate_matrix"] = all((not row["blocking"]) or row["pass"] for row in matrix.values())
    errors = [key for key, value in checks.items() if not value]
    report = {"schema": "node0004-v70-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors, "errors": errors, "checks": checks,
        "zip": {"path": str(a.zip.resolve()), "bytes": a.zip.stat().st_size, "sha256": zsha},
        "current_rule_receipts": {key: {"path": str(path), "bytes": path.stat().st_size, "sha256": shaf(path)} for key, path in RULES.items()},
        "release_gate_matrix": matrix,
        "claim_boundary": "Exact final ZIP, qualified branch-token owner observer, runner/layout/finalizer and return gate only; no DUT natural terminal/formal320D/E4/E5 claim."}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "sha": zsha}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
