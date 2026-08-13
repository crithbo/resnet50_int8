from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v78_buffer_input_owner_diag"
EPOCH = "20260810-first-fresh-extra-audit-v1"
PRIOR_PASS_SHA = "db884337d0a4026a51e7f1cc6aa9106d1628cbdc8c6b2b362704cb4e23ec19c2"


def sha(path: Path) -> str:
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
    ap.add_argument("--input-owner-report", required=True, type=Path)
    ap.add_argument("--runner-report", required=True, type=Path)
    ap.add_argument("--return-contract-report", required=True, type=Path)
    ap.add_argument("--shared-layout-report", required=True, type=Path)
    ap.add_argument("--prior-first-fresh-report", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    checks: dict[str, bool] = {}
    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = archive.testzip() is None
        checks["single_root"] = {
            PurePosixPath(name).parts[0] for name in names if name
        } == {PACKAGE}
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
        epoch = manifest.get("first_fresh_extra_audit", {})
        checks["same_epoch_prior_pass_reuse"] = (
            epoch.get("epoch_id") == EPOCH
            and epoch.get("first_fresh_after_change") is False
            and epoch.get("bound_package_id") == PACKAGE
            and epoch.get("prior_first_fresh_pass_receipt", {}).get("sha256")
            == PRIOR_PASS_SHA
        )
        checks["changed_owner_products_bound"] = all(
            item in files
            for item in (
                "package_tools/node0004_v78_post_sim_plugin.py",
                "package_tools/post_final_buffer_input_owner_parser.py",
                "contracts/server_post_sim_return_request.json",
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
        checks["current_rule_receipts"] = (
            receipts.get("server_package_rule_sha256")
            == sha(ROOT / ".agents/rules/服务器测试包生成规则.md")
            and receipts.get("generation_index_sha256")
            == sha(ROOT / ".agents/rules/生成前必读索引.md")
            and receipts.get("source_bound_generator_sha256")
            == sha(ROOT / "tools/generate_server_source_bound_observer.py")
            and receipts.get("server_post_sim_return_helper_sha256")
            == sha(ROOT / "tools/server_post_sim_return.py")
        )

    reports = {
        "build": load(args.build_report),
        "source_bound": load(args.source_bound_report),
        "post_sim": load(args.post_sim_report),
        "temporal": load(args.temporal_report),
        "input_owner": load(args.input_owner_report),
        "runner": load(args.runner_report),
        "return_contract": load(args.return_contract_report),
        "shared_layout": load(args.shared_layout_report),
        "prior_first_fresh": load(args.prior_first_fresh_report),
    }
    checks.update(
        {
            "deterministic_double_build": reports["build"].get("deterministic_rebuild_equal") is True
            and reports["build"].get("zip_sha256") == sha(args.zip),
            "source_bound_exact_regeneration": reports["source_bound"].get("pass") is True,
            "post_sim_four_scenarios": reports["post_sim"].get("pass") is True,
            "temporal_collector_controls": reports["temporal"].get("pass") is True,
            "input_owner_predicate_and_negatives": reports["input_owner"].get("pass") is True,
            "runner_controls": reports["runner"].get("valid") is True,
            "return_joint_gate": reports["return_contract"].get("valid") is True,
            "runtime_layout": reports["shared_layout"].get("pass") is True,
            "prior_first_fresh_pass": reports["prior_first_fresh"].get("pass") is True
            and reports["prior_first_fresh"].get("upload_authorized") is True
            and sha(args.prior_first_fresh_report) == PRIOR_PASS_SHA,
        }
    )
    errors = [name for name, value in checks.items() if not value]
    matrix = {
        "package_bootstrap_path_runtime_D": {
            "applicability": "blocking_applicable",
            "pass": all(checks[name] for name in ("crc", "single_root", "safe_members", "no_duplicates", "manifest_exact")),
        },
        "runner_compile_finalizer_SCA_open": {
            "applicability": "blocking_applicable",
            "pass": checks["runner_controls"] and checks["runtime_layout"],
        },
        "actual_package_local_HDL": {
            "applicability": "receipt_reuse",
            "pass": checks["source_bound_exact_regeneration"],
        },
        "changed_observer_collector_parser": {
            "applicability": "blocking_applicable",
            "pass": checks["temporal_collector_controls"] and checks["input_owner_predicate_and_negatives"],
        },
        "post_sim_core_and_result_conjunction": {
            "applicability": "blocking_applicable",
            "pass": checks["post_sim_four_scenarios"] and checks["return_joint_gate"],
        },
        "same_epoch_first_fresh_receipt": {
            "applicability": "receipt_reuse",
            "pass": checks["same_epoch_prior_pass_reuse"] and checks["prior_first_fresh_pass"],
        },
        "numeric_W3_golden_config_RTL": {
            "applicability": "receipt_reuse_frozen",
            "pass": checks["frozen_surfaces"],
        },
    }
    report = {
        "schema": "conv-node0004-v78-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "release_gate_matrix": matrix,
        "zip": {"path": str(args.zip.resolve()), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "report_receipts": {
            name: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}
            for name, path in (
                ("build", args.build_report),
                ("source_bound", args.source_bound_report),
                ("post_sim", args.post_sim_report),
                ("temporal", args.temporal_report),
                ("input_owner", args.input_owner_report),
                ("runner", args.runner_report),
                ("return_contract", args.return_contract_report),
                ("shared_layout", args.shared_layout_report),
                ("prior_first_fresh", args.prior_first_fresh_report),
            )
        },
        "claim_boundary": "Exact final package and changed input-owner parser/collector/return gates only; no server run, natural terminal, formal D, E4 or E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
