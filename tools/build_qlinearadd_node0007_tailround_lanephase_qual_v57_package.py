"""Build the v57 QAdd low-overhead, stage-qualified lane-phase successor."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_qlinearadd_node0007_tailround_split_colfix_v50_package as base


SOURCE_ID = "r5_qadd_n7_tailround_lanephase_v56"
TARGET = "r5_qadd_n7_tailround_lanephase_qual_v57f"
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested/qlinearadd_node0007"
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
SOURCE_SHA = "78e98876977060c3ea5c29ec93e130dbd48dc13c0d8386e8c5e42c075e2055fc"
RETURN_REPORT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-return-analysis/report.json"
CANDIDATE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57f-candidate"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
STAGE_FILTER = ROOT / "tools/qlinearadd_node0007_source_bound_stage_filter_v57.py"
PRIOR_FIRST_FRESH = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-package/first_fresh_extra_audit_v4/validation.json"
PRIOR_FIRST_FRESH_SHA = "f18351daf7af81538dcd6a2f891601f3d3666390814e50dd2ea3609f741e4958"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57f-package"
OUT_ZIP = LOCAL / f"{TARGET}.zip"
EPOCH = "20260810-first-fresh-extra-audit-v1"
RULES = {
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_config": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_fields": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
    "whole_net_specialist": ROOT / ".agents/rules/整网测试收敛优化专项规则.md",
}


class BuildError(RuntimeError):
    pass


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.TARGET = TARGET
    base.SOURCE = SOURCE
    base.SOURCE_SHA = SOURCE_SHA
    base.RULES = RULES


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prebuild_aggregate() -> dict:
    errors: list[str] = []
    required = [SOURCE, RETURN_REPORT, GENERATOR, STAGE_FILTER, PRIOR_FIRST_FRESH, *RULES.values()]
    required += [
        CANDIDATE / "source_bound_probe_catalog.json",
        CANDIDATE / "source_bound_probe_plan_v2.json",
        CANDIDATE / "source_bound_observer_generation_report_v2.json",
        CANDIDATE / "source_bound_observer_generation_cheap_check_v2.json",
        CANDIDATE / "generated_v2/source_bound_causal_observer.svh",
        CANDIDATE / "generated_v2/source_bound_causal_parser.py",
        CANDIDATE / "generated_v2/source_bound_probe_binding.json",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing input: {path.relative_to(ROOT).as_posix()}")
    if SOURCE.is_file() and base.sha(SOURCE) != SOURCE_SHA:
        errors.append("frozen v56 source ZIP identity differs")
    if PRIOR_FIRST_FRESH.is_file():
        prior = load(PRIOR_FIRST_FRESH)
        if base.sha(PRIOR_FIRST_FRESH) != PRIOR_FIRST_FRESH_SHA or prior.get("pass") is not True or prior.get("upload_authorized") is not True:
            errors.append("same-epoch prior first-fresh PASS receipt differs")
    if not errors:
        generation = load(CANDIDATE / "source_bound_observer_generation_report_v2.json")
        cheap = load(CANDIDATE / "source_bound_observer_generation_cheap_check_v2.json")
        if generation.get("pass") is not True or generation.get("errors") != []:
            errors.append("v57 generated source-bound report did not pass")
        if cheap.get("pass") is not True or cheap.get("errors") != []:
            errors.append("v57 cheap source-bound gate did not pass")
        if generation.get("contract", {}).get("boundary_count") != 3:
            errors.append("v57 must contain exactly three nonredundant generated boundaries")
    report = {
        "schema": "qlinearadd-node0007-tailround-lanephase-qual-v57-prebuild-v1",
        "pass": not errors,
        "errors": errors,
        "all_errors_collected": True,
        "top_level_invocations": 1,
        "bound_package_id": TARGET,
        "source_zip_sha256": SOURCE_SHA,
        "source_bound_generator_sha256": base.sha(GENERATOR) if GENERATOR.is_file() else None,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": False,
        "prior_first_fresh_pass_receipt_sha256": PRIOR_FIRST_FRESH_SHA,
        "numeric_workload_config_golden_repeated": False,
        "functional_rtl_modified": False,
    }
    LOCAL.mkdir(parents=True, exist_ok=True)
    base.write_json(LOCAL / "prebuild_aggregate.json", report)
    return report


def copy_generated_assets(package: Path) -> None:
    copies = {
        CANDIDATE / "source_bound_probe_catalog.json": package / "diagnostics/source_bound_probe_catalog.json",
        CANDIDATE / "source_bound_probe_plan_v2.json": package / "diagnostics/source_bound_probe_plan.json",
        CANDIDATE / "source_bound_observer_generation_report_v2.json": package / "diagnostics/source_bound_observer_generation_report.json",
        CANDIDATE / "source_bound_observer_generation_cheap_check_v2.json": package / "diagnostics/source_bound_observer_generation.json",
        CANDIDATE / "generated_v2/source_bound_causal_observer.svh": package / "tb_probe/source_bound_causal_observer.svh",
        CANDIDATE / "generated_v2/source_bound_causal_parser.py": package / "package_tools/source_bound_causal_parser.py",
        CANDIDATE / "generated_v2/source_bound_probe_binding.json": package / "diagnostics/source_bound_probe_binding.json",
        STAGE_FILTER: package / "package_tools/qlinearadd_node0007_source_bound_stage_filter_v57.py",
    }
    for source, target in copies.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    from tools.generate_server_source_bound_observer import _candidate_control_log

    plan = load(CANDIDATE / "source_bound_probe_plan_v2.json")
    live = package / "diagnostics/live_fixtures"
    live.mkdir(parents=True, exist_ok=True)
    source_lines = _candidate_control_log(plan, plan["candidates"][0])
    combined_lines = ["100 | EXEC_START | stage=1", *source_lines]
    (live / "source_bound_event.log").write_text("\n".join(combined_lines) + "\n", encoding="utf-8", newline="\n")
    contract_path = package / "diagnostics/source_bound_final_zip_contract.json"
    contract = load(contract_path)
    contract["stage_qualification"] = {
        "mode": "ORDERED_EXEC_START_FILTER_BEFORE_GENERATED_PARSER",
        "filter_member": "package_tools/qlinearadd_node0007_source_bound_stage_filter_v57.py",
        "filter_fixture_member": "diagnostics/live_fixtures/source_bound_event.log",
        "raw_log": "source_bound_causal_raw.log",
        "filtered_log": "source_bound_causal.log",
        "receipt": "evidence/source_bound_stage_filter_receipt.json",
        "pre_stage_records_are_functionally_non_consumable": True,
    }
    contract["claim_boundary"] = "Three generated Buffer boundaries plus package-local ordered EXEC_START record filter; no config/numeric/terminal/D claim."
    base.write_json(contract_path, contract)


def patch_post_sim(package: Path) -> None:
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    entries = request["core_entries"]
    additions = [
        {"source_root": "attempt", "source": "source_bound_causal_raw.log", "archive": "runs/source_bound_causal_raw.log", "required": False},
        {"source_root": "attempt", "source": "source_bound_causal.log", "archive": "runs/source_bound_causal.log", "required": False},
        {"source_root": "attempt", "source": "evidence/source_bound_stage_filter_receipt.json", "archive": "evidence/source_bound_stage_filter_receipt.json", "required": False},
    ]
    by_archive = {row["archive"]: row for row in entries}
    by_archive.pop("runs/source_bound_causal.log", None)
    for row in additions:
        by_archive[row["archive"]] = row
    request["core_entries"] = list(by_archive.values())
    parser_plugin = next(row for row in request["plugins"] if row["plugin_id"] == "source_bound_parser")
    parser_plugin["argv"] = [
        "python3", "{package_root}/package_tools/source_bound_causal_parser.py",
        "--log", "{attempt_root}/source_bound_causal.log",
        "--output", "{attempt_root}/evidence/source_bound_causal_decision.json",
    ]
    filter_plugin = {
        "plugin_id": "source_bound_stage_filter",
        "required_for_adjudication": True,
        "timeout_seconds": 120,
        "cwd_root": "attempt",
        "argv": [
            "python3", "{package_root}/package_tools/qlinearadd_node0007_source_bound_stage_filter_v57.py",
            "--source-log", "{attempt_root}/source_bound_causal_raw.log",
            "--output", "{attempt_root}/source_bound_causal.log",
            "--receipt", "{attempt_root}/evidence/source_bound_stage_filter_receipt.json",
        ],
    }
    request["plugins"] = [filter_plugin] + request["plugins"]
    request["claim_boundary"] = "Isolated host-stimulus tail_round stage-qualified lane-phase diagnostic; no producer/full-chain/E3/E4/E5 claim."
    base.write_json(request_path, request)

    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = load(contract_path)
    contract["request_sha256"] = base.sha(request_path)
    partial = contract["partial_exit_live_causal_record"]
    partial["plugin_dispositions"] = [
        {
            "plugin_id": "source_bound_stage_filter",
            "disposition": "LIVE_CAUSAL_FIXTURE",
            "fixture_member": "diagnostics/live_fixtures/source_bound_event.log",
            "input_root": "attempt",
            "input_path": "source_bound_causal_raw.log",
            "input_kind": "QUALIFIED_LIVE_RECORD",
            "output_root": "attempt",
            "output_path": "evidence/source_bound_stage_filter_receipt.json",
            "timeout_seconds": 30,
            "expected_exit_code": 0,
        }
    ] + partial["plugin_dispositions"]
    contract["claim_boundary"] = request["claim_boundary"]
    base.write_json(contract_path, contract)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old = 'grep \'^CODEX_PROBE_V1 \' "$run_root/sim.log" >"$run_root/source_bound_causal.log" || true\n'
    new = (
        'grep \' | EXEC_START | stage=1\' "$run_root/return_observer.log" >"$run_root/source_bound_causal_raw.log" || true\n'
        'grep \'^CODEX_PROBE_V1 \' "$run_root/sim.log" >>"$run_root/source_bound_causal_raw.log" || true\n'
    )
    if text.count(old) != 1:
        raise BuildError("v56 raw source-bound logger handoff anchor differs")
    text = text.replace(old, new, 1)
    if "source_bound_filtered_log=" in text:
        raise BuildError("fresh source runner unexpectedly contains source_bound_filtered_log assignment")
    run_root_anchor = 'run_root="$RUN_ROOT"\n'
    if text.count(run_root_anchor) != 1:
        raise BuildError("run_root assignment anchor differs")
    text = text.replace(
        run_root_anchor,
        run_root_anchor + 'source_bound_filtered_log="$run_root/source_bound_causal.log"\n',
        1,
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(path)
    generation = load(CANDIDATE / "source_bound_observer_generation_report_v2.json")
    manifest.update({
        "schema": "qlinearadd-node0007-tailround-lanephase-server-package-v57f",
        "package_id": TARGET,
        "install_name": TARGET,
        "candidate_release": False,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "diagnostic_only": True,
        "first_fresh_extra_audit": {
            "epoch_id": EPOCH,
            "notification_acknowledged": True,
            "first_fresh_after_change": False,
            "bound_package_id": TARGET,
            "prior_first_fresh_pass_receipt": {
                "path": PRIOR_FIRST_FRESH.relative_to(ROOT).as_posix(),
                "sha256": PRIOR_FIRST_FRESH_SHA,
            },
            "upload_hold_until_final_audit_pass": True,
        },
        "source_bound_observer": {
            "profile": "HIGH_INFORMATION_CAUSAL_V1",
            "plan_schema": "server-source-bound-probe-plan-v2",
            "diagnostic_semantics_sha256": generation["diagnostic_semantics_sha256"],
            "exact_instance_match": True,
            "payload_binary_known_width_fail_closed": True,
            "semantic_first_use_required": True,
            "generated_boundary_count": 3,
            "stage_qualification": "ORDERED_EXEC_START_FILTER_BEFORE_GENERATED_PARSER",
        },
        "source_assets": {
            **manifest.get("source_assets", {}),
            "v56_source_zip": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": SOURCE_SHA},
            "v56_return_analysis": {"path": RETURN_REPORT.relative_to(ROOT).as_posix(), "bytes": RETURN_REPORT.stat().st_size, "sha256": base.sha(RETURN_REPORT)},
        },
        "successor": {
            "source": SOURCE_ID,
            "source_sha256": SOURCE_SHA,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "reason": "v56 timed out before EXEC_START after materializing 1008 probes and admitted pre-stage records; no config leaf was observed or changed",
            "changed_surface": [
                "fresh identity",
                "generated source-bound plan reduced from six to three nonredundant boundaries",
                "package-local ordered EXEC_START record filter before the generated parser",
                "post-sim request/parser handoff for raw versus stage-qualified logs",
            ],
            "frozen_surface": [
                "single op_tail_round workload/config/bitstream/execplan/SCA",
                "28 host diagnostic FP32 inputs and UINT8 golden outputs",
                "numeric/W3/qparams/tail",
                "2h timeout",
                "functional RTL",
            ],
        },
        "rule_change_ack": {
            "epoch_id": EPOCH,
            "first_fresh_after_change": False,
            "prior_first_fresh_pass_receipt_sha256": PRIOR_FIRST_FRESH_SHA,
            "upload_hold_until": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
        },
        "rule_receipts": {
            name: {"path": rule.relative_to(ROOT).as_posix(), "sha256": base.sha(rule), "current_match": True}
            for name, rule in RULES.items()
        },
        "release_gate_matrix": {
            "package_bootstrap_path_runtime_D": "BLOCKING_REVALIDATE",
            "runner_compile_finalizer": "BLOCKING_CHANGED_POST_SIM_HANDOFF",
            "package_local_hdl": "BLOCKING_CHANGED_GENERATED_OBSERVER",
            "materialized_config": "RECEIPT_REUSE_BYTE_EQUAL",
            "observer_canonical": "BLOCKING_CHANGED_STAGE_QUALIFICATION",
            "return_result_conjunction": "BLOCKING_CHANGED_PLUGIN_CHAIN",
            "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN",
            "functional_RTL": "RECORD_ONLY_UNMODIFIED",
            "first_fresh_extra_audit": "RECEIPT_REUSE_SAME_EPOCH",
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
    copy_generated_assets(package)
    patch_post_sim(package)
    patch_runner(package)
    update_manifest(package)
    base.update_path_budget(package)
    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 isolated tail_round lane-phase v57f\n\n"
        "Run: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. The v56 workload/config/numeric/golden/2h timeout/RTL are byte-equal. "
        "Three generated Buffer probes replace six redundant probes, and only records after ordered EXEC_START enter the generated parser.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["files"] = base.records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    if OUT_ZIP.exists():
        raise BuildError("fresh v57 ZIP output required")
    LOCAL.mkdir(parents=True, exist_ok=True)
    aggregate = prebuild_aggregate()
    if not aggregate["pass"]:
        raise BuildError(f"prebuild aggregate failed: {aggregate['errors']}")
    with tempfile.TemporaryDirectory(prefix="q57a-") as first, tempfile.TemporaryDirectory(prefix="q57b-") as second:
        a = build_tree(Path(first))
        b = build_tree(Path(second))
        za = Path(first) / f"{TARGET}.zip"
        zb = Path(second) / f"{TARGET}.zip"
        base.deterministic_zip(a, za)
        base.deterministic_zip(b, zb)
        if base.sha(za) != base.sha(zb) or za.read_bytes() != zb.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{base.sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {
        "schema": "qlinearadd-node0007-tailround-lanephase-qual-v57f-build-v1",
        "status": "BUILT_UPLOAD_HOLD_PENDING_EXACT_FINAL_ZIP_AUDIT",
        "package_id": TARGET,
        "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": base.sha(OUT_ZIP)},
        "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": base.sha(sidecar)},
        "source_zip_sha256": SOURCE_SHA,
        "deterministic_double_build": True,
        "cheap_aggregate_invocations": 1,
        "final_zip_count": 1,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": False,
        "prior_first_fresh_pass_receipt_sha256": PRIOR_FIRST_FRESH_SHA,
        "numeric_workload_config_golden_repeated": False,
        "configuration_changed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(LOCAL / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
