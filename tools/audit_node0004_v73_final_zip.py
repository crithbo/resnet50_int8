from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v73_sourcebound_epoch_diag"
SOURCE = "r5_n4_hw_v72_token_origin_accept_diag"
SOURCE_SHA = "1cd8c9f55f8120e0c40599c54f6f385fbf159957bf74eafa0055c0ad4feed585"
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
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--sidecar", type=Path, required=True)
    ap.add_argument("--source-v72", type=Path, required=True)
    ap.add_argument("--build-report", type=Path, required=True)
    ap.add_argument("--family-report", type=Path, required=True)
    ap.add_argument("--shared-report", type=Path, required=True)
    ap.add_argument("--runner-report", type=Path, required=True)
    ap.add_argument("--return-report", type=Path, required=True)
    ap.add_argument("--source-bound-report", type=Path, required=True)
    ap.add_argument("--trace-report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    checks: dict[str, bool] = {}
    digest = shaf(args.zip)
    checks["source_identity"] = shaf(args.source_v72) == SOURCE_SHA
    checks["sidecar_identity"] = args.sidecar.read_text(encoding="ascii").split() == [digest, args.zip.name]
    with zipfile.ZipFile(args.zip) as archive, zipfile.ZipFile(args.source_v72) as source_archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = archive.testzip() is None
        checks["single_root"] = {name.split("/", 1)[0] for name in names} == {PACKAGE}
        checks["no_duplicates"] = len(names) == len(set(names))
        checks["safe_paths"] = all(not PurePosixPath(item.filename).is_absolute() and ".." not in PurePosixPath(item.filename).parts and "\\" not in item.filename for item in infos)
        checks["no_symlinks"] = all(not stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF) for item in infos)
        target = {"/".join(item.filename.split("/")[1:]): archive.read(item) for item in infos if not item.is_dir()}
        source = {"/".join(item.filename.split("/")[1:]): source_archive.read(item) for item in source_archive.infolist() if not item.is_dir()}
        manifest = json.loads(target["package_manifest.json"])
        actual = {path: sha(data) for path, data in target.items() if path != "package_manifest.json"}
        checks["manifest_exact_set"] = set(manifest["files"]) == set(actual)
        checks["manifest_receipts"] = manifest["files"] == actual
        checks["manifest_identity"] = manifest.get("install_name") == PACKAGE and manifest.get("source_package_sha256") == SOURCE_SHA
        checks["diagnostic_boundary"] = manifest.get("classification") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX" and manifest.get("candidate_release") is False
        checks["frozen_claims"] = all(manifest.get(key) is False for key in ("numeric_analysis_repeated", "node0004_workload_rebuilt", "configuration_rebuilt", "functional_rtl_modified", "server_action"))
        feature = manifest.get("diagnostic_features", {}).get("CODEX_CAUSAL_OBSERVER", {})
        checks["generated_feature_contract"] = feature.get("generation_mode") == "SOURCE_BOUND_SYMBOL_ID_EXACT_REGENERATION" and feature.get("runtime_enable_parameter") == "+CODEX_CAUSAL_OBSERVER"
        runner = target["PREPARE_AND_RUN.sh"].decode("utf-8")
        checks["actual_compile_binding"] = runner.count("tb_probe/source_bound_causal_observer.svh") >= 1 and "VCS_EXTRA_OPTS=" in runner
        checks["actual_runtime_binding"] = runner.count("+CODEX_CAUSAL_OBSERVER") == 2
        checks["return_binding"] = all(token in runner for token in ("source_bound_causal.log", "source_bound_causal_decision.json"))
        changed = {
            "package_manifest.json", "PREPARE_AND_RUN.sh",
            "package_tools/node0004_hang_localization_runtime_v7.py",
            "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        }
        frozen_equal = []
        for path, source_bytes in source.items():
            if path in changed:
                continue
            target_bytes = target.get(path)
            if target_bytes is None:
                frozen_equal.append(False)
                continue
            try:
                normalized = target_bytes.decode("utf-8").replace(PACKAGE, SOURCE).encode("utf-8")
                frozen_equal.append(normalized == source_bytes)
            except UnicodeDecodeError:
                frozen_equal.append(target_bytes == source_bytes)
        checks["all_predecessor_payload_frozen_except_declared_surface"] = bool(frozen_equal) and all(frozen_equal)
        receipts = manifest.get("active_receipts", {})
        checks["current_rule_receipts"] = receipts.get("generation_index_sha256") == shaf(RULES["index"]) and receipts.get("server_package_rule_sha256") == shaf(RULES["server"]) and receipts.get("int8_sa_rule_sha256") == shaf(RULES["int8_sa"])
        checks["source_bound_rule_bound"] = "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001" in receipts.get("rules", [])

    family = load(args.family_report)
    shared = load(args.shared_report)
    runner_report = load(args.runner_report)
    return_report = load(args.return_report)
    source_bound = load(args.source_bound_report)
    trace = load(args.trace_report)
    build = load(args.build_report)
    checks["deterministic_build"] = build.get("deterministic_rebuild_equal") is True
    checks["family_report"] = family.get("valid") is True and not family.get("errors")
    scenarios = shared.get("scenarios", {})
    checks["shared_six_control_flows"] = set(scenarios) == {"normal", "preflight_fail", "compile_fail", "HUP", "INT", "TERM"} and all(row.get("fixed_result_return_published") is True and row.get("root_exact_set_unchanged") is True for row in scenarios.values())
    checks["runner_visibility"] = runner_report.get("valid") is True
    checks["return_contract"] = return_report.get("valid") is True
    checks["source_bound_exact_regeneration"] = source_bound.get("pass") is True and not source_bound.get("errors") and all(item.get("byte_equal") is True for item in source_bound.get("exact_generation", {}).values())
    checks["source_bound_trace_controls"] = trace.get("valid") is True and all(trace.get("checks", {}).values())
    matrix = {
        "package_bootstrap_path_runtime_d": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["family_report"] and checks["shared_six_control_flows"]},
        "runner_compile_finalizer": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["family_report"] and checks["runner_visibility"]},
        "package_local_hdl_changed": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["source_bound_exact_regeneration"]},
        "materialized_config": {"applicability": "receipt_reuse_identity_only", "blocking": False, "pass": checks["all_predecessor_payload_frozen_except_declared_surface"]},
        "observer_canonical_changed": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["source_bound_exact_regeneration"] and checks["source_bound_trace_controls"]},
        "return_result_gate": {"applicability": "blocking_applicable", "blocking": True, "pass": checks["return_contract"]},
        "numeric_w3_golden": {"applicability": "record_only_frozen", "blocking": False, "pass": checks["all_predecessor_payload_frozen_except_declared_surface"]},
        "unrelated_rtl": {"applicability": "not_applicable", "blocking": False, "pass": True},
    }
    checks["release_gate_matrix"] = all((not row["blocking"]) or row["pass"] for row in matrix.values())
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "node0004-v73-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {"path": str(args.zip.resolve()), "bytes": args.zip.stat().st_size, "sha256": digest},
        "current_rule_receipts": {name: {"path": str(path), "bytes": path.stat().st_size, "sha256": shaf(path)} for name, path in RULES.items()},
        "release_gate_matrix": matrix,
        "claim_boundary": "Exact v73 generated source-bound diagnostic package only; no server execution, natural terminal, formal D, E4 or E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "zip_sha256": digest}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
