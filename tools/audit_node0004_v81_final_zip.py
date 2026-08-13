#!/usr/bin/env python3
"""Aggregate the exact final-ZIP release gates for serialized Conv v81."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE = "r5_n4_hw_v81_ack_phase_targetfix"
RULE_SHA = "2283153ad28ac3cfc21584ac705ef90e640bf157146153f4bc50dfd0e8f0af0e"
INDEX_SHA = "d55645b911ae21c1e4a0b653f9c6c0c0ef12d8c1aead8f3bd27925d52734e767"
EPOCH = "20260811-partial-exit-live-causal-record-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def receipt(path: Path) -> dict[str, Any]:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--validation-root", required=True, type=Path)
    parser.add_argument("--first-fresh-contract", required=True, type=Path)
    parser.add_argument("--first-fresh-validation", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    reports = {
        name: args.validation_root / filename
        for name, filename in {
            "source_bound": "source_bound.json",
            "post_sim": "post_sim.json",
            "phase": "phase.json",
            "ack_equation": "ack_equation.json",
            "input_owner": "input_owner.json",
            "temporal": "temporal.json",
            "runner": "runner.json",
            "shared_harness": "shared_harness.json",
            "shared_runtime_layout": "shared_runtime_layout.json",
            "return_contract": "return_contract.json",
        }.items()
    }
    missing = [name for name, path in reports.items() if not path.is_file()]
    values = {name: load(path) for name, path in reports.items() if path.is_file()}
    build = load(args.build_report)
    extra_contract = load(args.first_fresh_contract)
    extra = load(args.first_fresh_validation)

    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        crc = archive.testzip() is None
        safe = all(
            not PurePosixPath(item.filename).is_absolute()
            and ".." not in PurePosixPath(item.filename).parts
            and "\\" not in item.filename
            and not stat.S_ISLNK(item.external_attr >> 16)
            for item in infos
        )
        root_ok = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
        duplicate_free = len(names) == len(set(names))
        prefix = PACKAGE + "/"
        manifest = json.loads(archive.read(prefix + "package_manifest.json"))
        actual = {
            item.filename[len(prefix):]: hashlib.sha256(archive.read(item)).hexdigest()
            for item in infos
            if item.filename.startswith(prefix)
            and item.filename != prefix + "package_manifest.json"
            and not item.is_dir()
        }
        required_members = all(
            prefix + member in names
            for member in (
                "PREPARE_AND_RUN.sh",
                "tb_probe/source_bound_causal_observer.svh",
                "tb_probe/buffer_ack_phase_observer.svh",
                "package_tools/source_bound_causal_parser.py",
                "package_tools/buffer_ack_phase_parser.py",
                "package_tools/server_post_sim_return.py",
                "package_tools/node0004_v81_post_sim_plugin.py",
                "diagnostics/partial_exit_live/buffer_ack_phase_live.log",
                "contracts/server_post_sim_return_contract.json",
                "contracts/server_post_sim_return_request.json",
            )
        )
        runner_text = archive.read(prefix + "PREPARE_AND_RUN.sh").decode("utf-8")

    sidecar_tokens = args.sidecar.read_text(encoding="utf-8").strip().split()
    sidecar_ok = bool(sidecar_tokens) and sidecar_tokens[0] == sha(args.zip) and sidecar_tokens[-1].endswith(args.zip.name)
    manifest_receipts = manifest.get("active_receipts", {})
    generation_receipts = {
        row.get("path"): row.get("sha256")
        for row in manifest_receipts.get("generation_read_receipt", [])
    }
    checks = {
        "zip_crc": crc,
        "zip_safe_members": safe,
        "zip_single_root": root_ok,
        "zip_duplicate_free": duplicate_free,
        "sidecar_exact": sidecar_ok,
        "manifest_exact": manifest.get("files") == actual,
        "required_members": required_members,
        "deterministic_double_build": build.get("deterministic_rebuild_equal") is True,
        "build_zip_identity": build.get("zip_sha256") == sha(args.zip) and build.get("zip_bytes") == args.zip.stat().st_size,
        "current_rule_receipt": manifest_receipts.get("server_package_rule_sha256") == RULE_SHA,
        "current_index_receipt": manifest_receipts.get("generation_index_sha256") == INDEX_SHA,
        "post_generation_receipts": generation_receipts.get(".agents/rules/服务器测试包生成规则.md") == RULE_SHA
        and generation_receipts.get(".agents/rules/生成前必读索引.md") == INDEX_SHA,
        "epoch_ack": manifest.get("first_fresh_extra_audit", {}).get("epoch_id") == EPOCH
        and manifest.get("first_fresh_extra_audit", {}).get("first_fresh_after_change") is True,
        "source_bound": values.get("source_bound", {}).get("pass") is True and values.get("source_bound", {}).get("errors") == [],
        "post_sim": values.get("post_sim", {}).get("pass") is True and values.get("post_sim", {}).get("errors") == [],
        "partial_exit_live_fixture": values.get("post_sim", {}).get("details", {}).get("partial_exit_live_causal_record", {}).get("contract_errors") == [],
        "phase_predicates_and_scope": values.get("phase", {}).get("pass") is True and values.get("phase", {}).get("errors") == [],
        "phase_live_only_and_final_ring_negative": values.get("phase", {}).get("checks", {}).get("tiny_live_fixture_passes") is True
        and values.get("phase", {}).get("checks", {}).get("final_ring_only_fails_closed") is True,
        "legacy_parsers_receipt_reuse": all(values.get(name, {}).get("pass") is True for name in ("ack_equation", "input_owner", "temporal")),
        "runner": values.get("runner", {}).get("valid") is True and values.get("runner", {}).get("errors") == [],
        "runtime_layout": values.get("shared_runtime_layout", {}).get("pass") is True and values.get("shared_runtime_layout", {}).get("errors") == [],
        "return_contract": values.get("return_contract", {}).get("valid") is True and values.get("return_contract", {}).get("errors") == [],
        "runner_compile_handoff": runner_text.count("$package_root/tb_probe/buffer_ack_phase_observer.svh") == 1,
        "runner_runtime_feature": "+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128" in runner_text and "+CODEX_CAUSAL_OBSERVER" in runner_text,
        "first_fresh_contract_identity": extra_contract.get("package", {}).get("final_zip", {}).get("sha256") == sha(args.zip),
        "first_fresh_independent_pass": extra.get("pass") is True and extra.get("upload_authorized") is True and extra.get("errors") == [],
        "all_validation_reports_present": not missing,
    }

    release_gate_matrix = {
        "package_bootstrap_path_runtime_D": {"applicability": "blocking_applicable", "pass": all(checks[key] for key in ("zip_crc", "zip_safe_members", "zip_single_root", "zip_duplicate_free", "manifest_exact", "sidecar_exact"))},
        "actual_runner_compile_finalizer_and_86_inputs": {"applicability": "blocking_applicable", "pass": checks["runner"] and checks["runtime_layout"] and checks["runner_compile_handoff"]},
        "actual_package_local_HDL": {"applicability": "blocking_applicable", "pass": checks["phase_predicates_and_scope"] and checks["required_members"]},
        "changed_observer_and_canonical_semantics": {"applicability": "blocking_applicable", "pass": checks["source_bound"] and checks["post_sim"] and checks["partial_exit_live_fixture"] and checks["phase_live_only_and_final_ring_negative"]},
        "return_result_joint_gate": {"applicability": "blocking_applicable", "pass": checks["return_contract"]},
        "first_fresh_independent_reaudit": {"applicability": "blocking_applicable", "pass": checks["first_fresh_independent_pass"]},
        "materialized_config": {"applicability": "receipt_reuse", "pass": True, "reason": "byte-identical frozen v80 workload/config/address/golden"},
        "numeric_W3_golden": {"applicability": "not_applicable", "pass": True, "reason": "not changed and not repeated"},
        "functional_RTL": {"applicability": "not_applicable", "pass": True, "reason": "not modified"},
    }
    errors = [name for name, passed in checks.items() if not passed]
    errors.extend(f"release_gate_matrix:{name}" for name, row in release_gate_matrix.items() if row.get("pass") is not True)
    report = {
        "schema": "conv-node0004-v81-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "release_gate_matrix": release_gate_matrix,
        "zip": {"path": str(args.zip), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
        "active_rule_receipts": {
            "generation_index_sha256": INDEX_SHA,
            "server_package_rule_sha256": RULE_SHA,
            "partial_exit_rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
            "first_fresh_rule_id": "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
        },
        "report_receipts": {name: receipt(path) for name, path in reports.items()},
        "first_fresh_receipts": {
            "contract": receipt(args.first_fresh_contract),
            "validation": receipt(args.first_fresh_validation),
        },
        "claims": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
        "claim_boundary": "Exact package bytes and local execution/diagnostic gates only; no DUT natural terminal, formal D, E3, E4 or E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "zip_sha256": sha(args.zip)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
