from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v77_terminal_temporal_ledger_diag"
EPOCH = "20260810-first-fresh-extra-audit-v1"


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--build-report", required=True, type=Path)
    ap.add_argument("--source-bound-report", required=True, type=Path)
    ap.add_argument("--post-sim-report", required=True, type=Path)
    ap.add_argument("--temporal-report", required=True, type=Path)
    ap.add_argument("--runner-report", required=True, type=Path)
    ap.add_argument("--return-contract-report", required=True, type=Path)
    ap.add_argument("--first-fresh-report", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    checks: dict[str, bool] = {}
    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = archive.testzip() is None
        checks["single_root"] = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
        checks["safe_members"] = all(
            not PurePosixPath(name).is_absolute()
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
            and not stat.S_ISLNK(info.external_attr >> 16)
            for name, info in zip(names, infos)
        )
        checks["no_duplicates"] = len(names) == len(set(names))
        files = {
            name.split("/", 1)[1]: archive.read(name)
            for name in names
            if "/" in name and not name.endswith("/")
        }
        manifest = json.loads(files["package_manifest.json"])
        actual = {
            relative: sha_bytes(value)
            for relative, value in files.items()
            if relative != "package_manifest.json"
        }
        checks["manifest_exact"] = manifest.get("files") == actual
        checks["epoch_ack"] = (
            manifest.get("first_fresh_extra_audit", {}).get("epoch_id") == EPOCH
            and manifest.get("first_fresh_extra_audit", {}).get("first_fresh_after_change") is True
            and manifest.get("first_fresh_extra_audit", {}).get("bound_package_id") == PACKAGE
        )
        checks["changed_temporal_products_bound"] = all(
            item in files
            for item in (
                "package_tools/node0004_v77_post_sim_plugin.py",
                "contracts/server_post_sim_return_request.json",
                "package_tools/node0004_hang_localization_runtime_v7.py",
            )
        )
        checks["frozen_surfaces"] = all(
            manifest.get(key) is False
            for key in (
                "numeric_analysis_repeated",
                "node0004_workload_rebuilt",
                "configuration_rebuilt",
                "functional_rtl_modified",
                "server_action",
            )
        )
        receipts = manifest.get("active_receipts", {})
        # Exact current files are read here after final ZIP materialization.
        server_rule = ROOT / ".agents/rules/服务器测试包生成规则.md"
        index_rule = ROOT / ".agents/rules/生成前必读索引.md"
        checks["current_rule_receipts"] = (
            receipts.get("server_package_rule_sha256") == sha_file(server_rule)
            and receipts.get("generation_index_sha256") == sha_file(index_rule)
            and receipts.get("source_bound_generator_sha256")
            == sha_file(ROOT / "tools/generate_server_source_bound_observer.py")
            and receipts.get("server_post_sim_return_helper_sha256")
            == sha_file(ROOT / "tools/server_post_sim_return.py")
        )

    reports = {
        "build": load(args.build_report),
        "source_bound": load(args.source_bound_report),
        "post_sim": load(args.post_sim_report),
        "temporal": load(args.temporal_report),
        "runner": load(args.runner_report),
        "return_contract": load(args.return_contract_report),
        "first_fresh": load(args.first_fresh_report),
    }
    checks.update(
        {
            "deterministic_double_build": reports["build"].get("deterministic_rebuild_equal") is True
            and reports["build"].get("zip_sha256") == sha_file(args.zip),
            "source_bound_exact_regeneration": reports["source_bound"].get("pass") is True,
            "post_sim_four_scenarios": reports["post_sim"].get("pass") is True,
            "temporal_overbudget_and_negatives": reports["temporal"].get("pass") is True,
            "runner_controls": reports["runner"].get("valid") is True,
            "return_joint_gate": reports["return_contract"].get("valid") is True,
            "first_fresh_independent_extra_audit": reports["first_fresh"].get("pass") is True
            and reports["first_fresh"].get("upload_authorized") is True,
        }
    )
    errors = [name for name, value in checks.items() if not value]
    matrix = {
        "package_bootstrap_path_runtime_D": {"applicability": "blocking_applicable", "pass": all(checks[x] for x in ("crc", "single_root", "safe_members", "no_duplicates", "manifest_exact"))},
        "runner_compile_finalizer_SCA_open": {"applicability": "blocking_applicable", "pass": checks["runner_controls"]},
        "actual_package_local_HDL": {"applicability": "receipt_reuse", "pass": checks["source_bound_exact_regeneration"]},
        "changed_observer_collector_parser": {"applicability": "blocking_applicable", "pass": checks["temporal_overbudget_and_negatives"]},
        "post_sim_core_and_result_conjunction": {"applicability": "blocking_applicable", "pass": checks["post_sim_four_scenarios"] and checks["return_joint_gate"]},
        "first_fresh_extra_audit": {"applicability": "blocking_applicable", "pass": checks["first_fresh_independent_extra_audit"]},
        "numeric_W3_golden_config_RTL": {"applicability": "receipt_reuse_frozen", "pass": checks["frozen_surfaces"]},
    }
    report = {
        "schema": "conv-node0004-v77-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "release_gate_matrix": matrix,
        "zip": {"path": str(args.zip.resolve()), "bytes": args.zip.stat().st_size, "sha256": sha_file(args.zip)},
        "report_receipts": {name: {"path": str(path), "sha256": sha_file(path)} for name, path in (
            ("build", args.build_report), ("source_bound", args.source_bound_report),
            ("post_sim", args.post_sim_report), ("temporal", args.temporal_report),
            ("runner", args.runner_report), ("return_contract", args.return_contract_report),
            ("first_fresh", args.first_fresh_report),
        )},
        "claim_boundary": "Final package and changed observer/collector/return gates only; no server run, natural terminal, formal D, E4 or E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
