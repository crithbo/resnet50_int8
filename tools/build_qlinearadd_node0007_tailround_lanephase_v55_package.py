"""Build the source-bound QAdd tail_round lane-phase diagnostic successor v55.

The v54 workload/config/numeric/golden/timeout surface is copied byte-for-byte.
Only identity, generated source-bound diagnostics, and the shared post-sim return
path are changed.  The script intentionally refuses to build unless the
pre-generated source-bound artifacts bind the current shared generator.
"""

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


SOURCE_ID = "r5_qadd_n7_tailround_bufready_v54"
TARGET = "r5_qadd_n7_tailround_lanephase_v55"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_SHA = "e0b4cc00cbd29716c3399b5fcb95265ae10a1d2d67765466a023312b8cde3f26"
RETURN_REPORT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-bufready-v54-return-analysis/report.json"
CANDIDATE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v55-candidate"
GENERATOR = ROOT / "tools/generate_server_source_bound_observer.py"
POST_SIM = ROOT / "tools/server_post_sim_return.py"
POST_SIM_PLUGIN = ROOT / "tools/qlinearadd_node0007_tailround_post_sim_plugin_v56.py"
LOCAL = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v55-package"
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
    required = [SOURCE, RETURN_REPORT, GENERATOR, POST_SIM, POST_SIM_PLUGIN, *RULES.values()]
    required += [
        CANDIDATE / "source_bound_probe_catalog.json",
        CANDIDATE / "source_bound_probe_plan.json",
        CANDIDATE / "source_bound_observer_generation_report.json",
        CANDIDATE / "source_bound_observer_generation_cheap_check.json",
        CANDIDATE / "generated/source_bound_causal_observer.svh",
        CANDIDATE / "generated/source_bound_causal_parser.py",
        CANDIDATE / "generated/source_bound_probe_binding.json",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing input: {path.relative_to(ROOT).as_posix()}")
    if SOURCE.is_file() and base.sha(SOURCE) != SOURCE_SHA:
        errors.append("frozen v54 source ZIP identity differs")
    if not errors:
        generation = load(CANDIDATE / "source_bound_observer_generation_report.json")
        cheap = load(CANDIDATE / "source_bound_observer_generation_cheap_check.json")
        if generation.get("pass") is not True or generation.get("errors") != []:
            errors.append("source-bound generation report did not pass")
        if cheap.get("pass") is not True or cheap.get("errors") != []:
            errors.append("source-bound cheap check did not pass")
        artifact = {Path(x["path"]).name: x for x in generation.get("generated_artifacts", [])}
        for name in ("source_bound_causal_observer.svh", "source_bound_causal_parser.py", "source_bound_probe_binding.json"):
            path = CANDIDATE / "generated" / name
            if artifact.get(name, {}).get("sha256") != base.sha(path):
                errors.append(f"generated artifact receipt differs: {name}")
    report = {
        "schema": f"qlinearadd-node0007-{TARGET}-prebuild-aggregate-v1",
        "pass": not errors,
        "errors": errors,
        "all_errors_collected": True,
        "top_level_invocations": 1,
        "bound_package_id": TARGET,
        "source_zip_sha256": SOURCE_SHA,
        "source_bound_generator_sha256": base.sha(GENERATOR) if GENERATOR.is_file() else None,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "numeric_workload_config_golden_repeated": False,
    }
    LOCAL.mkdir(parents=True, exist_ok=True)
    base.write_json(LOCAL / "prebuild_aggregate.json", report)
    return report


def copy_source_bound(package: Path) -> None:
    copies = {
        CANDIDATE / "source_bound_probe_catalog.json": package / "diagnostics/source_bound_probe_catalog.json",
        CANDIDATE / "source_bound_probe_plan.json": package / "diagnostics/source_bound_probe_plan.json",
        CANDIDATE / "source_bound_observer_generation_report.json": package / "diagnostics/source_bound_observer_generation_report.json",
        CANDIDATE / "source_bound_observer_generation_cheap_check.json": package / "diagnostics/source_bound_observer_generation.json",
        CANDIDATE / "generated/source_bound_causal_observer.svh": package / "tb_probe/source_bound_causal_observer.svh",
        CANDIDATE / "generated/source_bound_causal_parser.py": package / "package_tools/source_bound_causal_parser.py",
        CANDIDATE / "generated/source_bound_probe_binding.json": package / "diagnostics/source_bound_probe_binding.json",
        POST_SIM: package / "package_tools/server_post_sim_return.py",
        POST_SIM_PLUGIN: package / "package_tools/qlinearadd_node0007_tailround_post_sim_plugin_v56.py",
    }
    for source, target in copies.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    # The shared post-sim core forbids retaining a family positional return
    # collector anywhere in the exact ZIP.  v56 still needs the frozen
    # preflight/analyze logic, so keep only that causal subset in the copied
    # package-local runtimes.
    base_runtime = package / "package_tools/qlinearadd_node0007_split_server_runtime_v25.py"
    base_text = base_runtime.read_text(encoding="utf-8")
    collect_anchor = "\ndef collect(\n"
    if base_text.count(collect_anchor) != 1:
        raise BuildError("base runtime collector anchor differs")
    base_runtime.write_text(
        base_text.split(collect_anchor, 1)[0] + "\n",
        encoding="utf-8",
        newline="\n",
    )
    tail_runtime = package / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"
    tail_text = tail_runtime.read_text(encoding="utf-8")
    parser_start = '    collect = sub.add_parser("collect")\n'
    parser_end = "    args = parser.parse_args()\n"
    if tail_text.count(parser_start) != 1 or tail_text.count(parser_end) != 1:
        raise BuildError("tail runtime collector parser anchor differs")
    before, rest = tail_text.split(parser_start, 1)
    _, after = rest.split(parser_end, 1)
    tail_text = before + parser_end + after
    branch_start = "        else:\n            print(\n                json.dumps(\n                    base.collect(\n"
    branch_end = "    except Exception as error:\n"
    if tail_text.count(branch_start) != 1 or tail_text.count(branch_end) != 1:
        raise BuildError("tail runtime collector branch anchor differs")
    before, rest = tail_text.split(branch_start, 1)
    _, after = rest.split(branch_end, 1)
    tail_text = before + '        else:\n            raise RuntimeGateError("unsupported command")\n' + branch_end + after
    tail_runtime.write_text(tail_text, encoding="utf-8", newline="\n")

    from tools.generate_server_source_bound_observer import _candidate_control_log

    plan = load(CANDIDATE / "source_bound_probe_plan.json")
    live_root = package / "diagnostics/live_fixtures"
    live_root.mkdir(parents=True, exist_ok=True)
    source_lines = _candidate_control_log(plan, plan["candidates"][0])
    (live_root / "source_bound_event.log").write_text(
        "\n".join(source_lines) + "\n", encoding="utf-8", newline="\n"
    )
    qualified = "stage=1 active_cycles=1 " + " ".join(
        f"{name}=0"
        for name in (
            "base_req", "base_rdata", "base_wdata", "addr_enqueue", "req_hs",
            "meta", "consume", "buffer", "ga", "mse4_idx", "sg_in", "sg_out",
            "mse4_req_ch0", "mse4_req_ch1", "mse4_wdata_ch0", "mse4_wdata_ch1",
            "mse4_outstanding_ch0", "mse4_outstanding_ch1",
        )
    )
    qadd_fixture = (
        "CODEX_PARTIAL_EXIT_PERSISTED_V1 qualified=true signal_safe=true\n"
        "# QADD_TAILROUND_BUFREADY_V53 enabled=1\n"
        "1 | EXEC_START | stage=1\n"
        "2 | Q53_STATE | stage=1 group=0 local_slice=0 pingpong=0 ready0=0 ready1=1 "
        "selected_ready=0 mrm_ready5=0 req_valid=0x1 req_rw=0 req_addr=0 req_strb=0xf "
        "rd_en=0x1 bank_ready=0xfe valid_at_req=0x7 rreq_ready=0 buffer_mask=0xff nrm_barrier=0\n"
        "3 | Q53_EVENT | kind=BUF5_WRITE_ACCEPT wr_en=0xff row=0 req_valid=0xff req_strb=0xffffffff\n"
        + "\n".join(f"{20 + index} | TAILROUND_FLOW | {qualified}" for index in range(4))
        + "\n"
    )
    (live_root / "qadd_bufready_event.log").write_text(
        qadd_fixture, encoding="utf-8", newline="\n"
    )
    base.write_json(package / "diagnostics/source_bound_final_zip_contract.json", {
        "schema": "server-source-bound-final-zip-contract-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "enforcement": "required_next_fresh",
        "members": {
            "catalog": "diagnostics/source_bound_probe_catalog.json",
            "plan": "diagnostics/source_bound_probe_plan.json",
            "observer": "tb_probe/source_bound_causal_observer.svh",
            "parser": "package_tools/source_bound_causal_parser.py",
            "binding": "diagnostics/source_bound_probe_binding.json",
            "generation_report": "diagnostics/source_bound_observer_generation_report.json",
            "runner": "PREPARE_AND_RUN.sh",
        },
        "compile_observer_token": "source_bound_causal_observer.svh",
        "runtime_plusarg": "+CODEX_CAUSAL_OBSERVER",
        "return_log_token": "source_bound_causal.log",
        "return_decision_token": "source_bound_causal_decision.json",
        "claim_boundary": "Exact generated Buffer5 lane-phase observer/parser/binding only; no production simulation or numeric claim.",
    })


def write_post_sim_contract(package: Path) -> None:
    core_entries = [
        {"source_root": "package", "source": "TEST_PACKAGE_MANIFEST.json", "archive": "source_package/TEST_PACKAGE_MANIFEST.json", "required": True},
        {"source_root": "package", "source": "diagnostics/source_bound_probe_binding.json", "archive": "source_package/source_bound_probe_binding.json", "required": True},
        {"source_root": "package", "source": "diagnostics/source_bound_observer_generation_report.json", "archive": "source_package/source_bound_generation_report.json", "required": True},
    ]
    for name in (
        "package_preflight.json", "installed_preflight.json", "PACKAGE_MANIFEST.json",
        "compile_exit_status.txt", "simulation_exit_status.txt", "signal_status.txt",
        "host_timing.txt", "actual_compile_argv.txt", "actual_simulator_argv.txt",
        "observer_binding.txt", "feature_receipt.txt", "progress_contract.json",
        "runtime_layout_receipt.json", "ndp_root_toplevel_pre.json",
        "ndp_root_toplevel_post.json", "fixed_result_preflight.json",
    ):
        core_entries.append({"source_root": "attempt", "source": f"evidence/{name}", "archive": f"evidence/{name}", "required": True})
    core_entries += [
        {"source_root": "attempt", "source": "sim.log", "archive": "runs/sim.log", "required": False},
        {"source_root": "attempt", "source": "return_observer.log", "archive": "runs/return_observer.log", "required": False},
        {"source_root": "attempt", "source": "source_bound_causal.log", "archive": "runs/source_bound_causal.log", "required": False},
        {"source_root": "attempt", "source": "evidence/source_bound_causal_decision.json", "archive": "evidence/source_bound_causal_decision.json", "required": False},
        {"source_root": "attempt", "source": "evidence/CANONICAL_PROGRESS_DECISION.json", "archive": "evidence/CANONICAL_PROGRESS_DECISION.json", "required": False},
        {"source_root": "attempt", "source": "evidence/canonical_decision_exit_status.txt", "archive": "evidence/canonical_decision_exit_status.txt", "required": False},
        {"source_root": "attempt", "source": "evidence/SERVER_RESULT_GATE.json", "archive": "evidence/SERVER_RESULT_GATE.json", "required": False},
        {"source_root": "attempt", "source": "evidence/source_bound_parser_exit_status.txt", "archive": "evidence/source_bound_parser_exit_status.txt", "required": False},
        {"source_root": "attempt", "source": "sim_tail.log", "archive": "runs/sim_tail.log", "required": False},
        {"source_root": "attempt", "source": "return_observer_tail.log", "archive": "runs/return_observer_tail.log", "required": False},
        {"source_root": "attempt", "source": "compile/sim_results/compile_driver.log", "archive": "runs/compile_driver.log", "required": False},
    ]
    for slice_id in range(28):
        rel = f"op_tail_round/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        core_entries.append({"source_root": "attempt", "source": rel, "archive": f"readbacks/{rel}", "required": False})
    request = {
        "schema": "server-post-sim-return-request-v1",
        "package_id": TARGET,
        "result_root": "/home/panqs/ndp/simresult",
        "return_basename_template": "{package_id}_{execution_id}_return.zip",
        "max_plugin_output_bytes": 262144,
        "claim_boundary": "Isolated host-stimulus tail_round lane-phase diagnostic; core publication is independent of plugin success and no producer/full-chain/E3/E4/E5 claim is made.",
        "core_entries": core_entries,
        "plugins": [
            {
                "plugin_id": "source_bound_parser", "required_for_adjudication": True,
                "timeout_seconds": 120, "cwd_root": "attempt",
                "argv": ["python3", "{package_root}/package_tools/source_bound_causal_parser.py", "--log", "{attempt_root}/source_bound_causal.log", "--output", "{attempt_root}/evidence/source_bound_causal_decision.json"],
            },
            {
                "plugin_id": "qadd_canonical", "required_for_adjudication": True,
                "timeout_seconds": 120, "cwd_root": "attempt",
                "argv": ["python3", "{package_root}/package_tools/qlinearadd_node0007_tailround_bufready_canonical_v53.py", "--observer-log", "{attempt_root}/return_observer.log", "--output", "{attempt_root}/evidence/CANONICAL_PROGRESS_DECISION.json"],
            },
            {
                "plugin_id": "qadd_stage_analyze", "required_for_adjudication": True,
                "timeout_seconds": 180, "cwd_root": "attempt",
                "argv": ["python3", "{package_root}/package_tools/qlinearadd_node0007_tailround_post_sim_plugin_v56.py", "--package-root", "{package_root}", "--attempt-root", "{attempt_root}"],
            },
        ],
    }
    request_path = package / "contracts/server_post_sim_return_request.json"
    base.write_json(request_path, request)
    contract = {
        "schema": "server-post-sim-return-contract-v1",
        "package_id": TARGET,
        "helper_member": "package_tools/server_post_sim_return.py",
        "helper_sha256": base.sha(package / "package_tools/server_post_sim_return.py"),
        "request_member": "contracts/server_post_sim_return_request.json",
        "request_sha256": base.sha(request_path),
        "runner_member": "PREPARE_AND_RUN.sh",
        "invocation_mode": "JSON_REQUEST_ONLY_NO_POSITIONAL_COLLECTOR",
        "plugin_failure_blocks_core_return": False,
        "sim_exit_persisted_before_plugins": True,
        "required_scenarios": ["natural_success", "natural_success_plugin_failure", "simulation_nonzero", "idempotent_reentry"],
        "partial_exit_live_causal_record": {
            "rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
            "enforcement": "required_next_fresh",
            "required_signals": ["INT", "TERM"],
            "final_block_ring_sole_input_forbidden": True,
            "plugin_dispositions": [
                {"plugin_id": "source_bound_parser", "disposition": "LIVE_CAUSAL_FIXTURE", "fixture_member": "diagnostics/live_fixtures/source_bound_event.log", "input_kind": "QUALIFIED_LIVE_RECORD", "input_root": "attempt", "input_path": "source_bound_causal.log", "output_root": "attempt", "output_path": "evidence/source_bound_causal_decision.json", "timeout_seconds": 30, "expected_exit_code": 0},
                {"plugin_id": "qadd_canonical", "disposition": "LIVE_CAUSAL_FIXTURE", "fixture_member": "diagnostics/live_fixtures/qadd_bufready_event.log", "input_kind": "SIGNAL_SAFE_PERSISTED_EQUIVALENT", "input_root": "attempt", "input_path": "return_observer.log", "output_root": "attempt", "output_path": "evidence/CANONICAL_PROGRESS_DECISION.json", "timeout_seconds": 30, "expected_exit_code": 0},
                {"plugin_id": "qadd_stage_analyze", "disposition": "NOT_APPLICABLE_NON_CAUSAL_PLUGIN", "reason": "static result aggregation, not the source of partial-exit causal facts"},
            ],
        },
        "claim_boundary": request["claim_boundary"],
    }
    base.write_json(package / "contracts/server_post_sim_return_contract.json", contract)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    marker = 'layout_helper="$package_root/package_tools/server_package_runtime_layout.py"\n'
    addition = marker + 'post_sim_helper="$package_root/package_tools/server_post_sim_return.py"\npost_sim_request="$package_root/contracts/server_post_sim_return_request.json"\nsource_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"\nsource_bound_decision_name="source_bound_causal_decision.json"\nreturn_finalizer_state_name="RETURN_FINALIZER_STATE.json"\n'
    if text.count(marker) != 2:
        raise BuildError("runner layout helper anchor differs")
    text = text.replace(marker, addition)
    old = '''    python3 "$package_root/package_tools/qlinearadd_node0007_tailround_bufready_canonical_v53.py"       --observer-log "$run_root/return_observer.log"       --output "$evidence_root/CANONICAL_PROGRESS_DECISION.json"
    canonical_status=$?
    printf '%s\\n' "$canonical_status" >"$evidence_root/canonical_decision_exit_status.txt"
    python3 "$runtime" analyze --package-root "$package_root"       --evidence-root "$evidence_root" --run-root "$run_root"       --compile-status "$compile_status" --simulation-status "$simulation_status"
    analysis_status=$?
    python3 "$root_guard" compare --server-root "$server_root"       --pre "$evidence_root/ndp_root_toplevel_pre.json"       --output "$evidence_root/ndp_root_toplevel_post.json"
    root_status=$?
    python3 "$runtime" collect --server-root "$server_root"       --install-name "$install_name" --package-root "$package_root"       --evidence-root "$evidence_root" --run-root "$run_root" --cfg-root "$cfg_root" --return-zip "$return_zip"
    collect_status=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$canonical_status" -eq 0 ] || final="$canonical_status"
    [ "$final" -ne 0 ] || [ "$analysis_status" -eq 0 ] || final="$analysis_status"
    [ "$final" -ne 0 ] || [ "$root_status" -eq 0 ] || final="$root_status"
    [ "$final" -ne 0 ] || [ "$collect_status" -eq 0 ] || final="$collect_status"
'''
    new = '''    grep '^CODEX_PROBE_V1 ' "$run_root/sim.log" >"$run_root/source_bound_causal.log" || true
    python3 "$root_guard" compare --server-root "$server_root"       --pre "$evidence_root/ndp_root_toplevel_pre.json"       --output "$evidence_root/ndp_root_toplevel_post.json"
    root_status=$?
    export CODEX_PACKAGE_ROOT="$package_root"
    export CODEX_ATTEMPT_ROOT="$run_root"
    export CODEX_EXECUTION_ID="$return_tag"
    export CODEX_SIM_EXIT_CODE="$simulation_status"
    export CODEX_SIM_SIGNAL="$signal_name"
    export CODEX_SIM_STARTED="$simulation_started"
    export CODEX_NATURAL_TERMINAL=$([ "$simulation_status" -eq 0 ] && printf true || printf false)
    export CODEX_COMPILE_STATUS="$compile_status"
    export CODEX_SIMULATION_STATUS="$simulation_status"
    python3 "$post_sim_helper" finalize --request "$post_sim_request"
    collect_status=$?
    final="$original"
    [ "$final" -ne 0 ] || [ "$root_status" -eq 0 ] || final="$root_status"
    [ "$final" -ne 0 ] || [ "$collect_status" -eq 0 ] || final="$collect_status"
'''
    if text.count(old) != 1:
        raise BuildError("runner finalizer anchor differs")
    text = text.replace(old, new, 1)
    old_opts = '+incdir+$package_root/tb_probe +define+NATIVE_RETURN_OBSERVER_ENABLE'
    new_opts = old_opts + ' $package_root/tb_probe/source_bound_causal_observer.svh'
    if text.count(old_opts) != 2:
        raise BuildError(f"runner compile option anchors differ: {text.count(old_opts)}")
    text = text.replace(old_opts, new_opts)
    sim_anchor = '  +RETURN_OBSERVER +QADD_TAILROUND_BUFREADY +RETURN_OBS_SLICE=0\n'
    if text.count(sim_anchor) != 1:
        raise BuildError("runner simulator option anchor differs")
    text = text.replace(sim_anchor, '  +CODEX_CAUSAL_OBSERVER\n' + sim_anchor, 1)
    sim_start_anchor = "printf 'RUNTIME_LAYOUT_SIMULATION_START\\n' >\"$evidence_root/simulation_started.marker\"\n"
    if text.count(sim_start_anchor) != 1:
        raise BuildError("runner simulation-start anchor differs")
    text = text.replace(sim_start_anchor, sim_start_anchor + "simulation_started=true\n", 1)
    init_anchor = "simulation_status=125\nsignal_name=NONE\n"
    if text.count(init_anchor) != 1:
        raise BuildError("runner simulation-state anchor differs")
    text = text.replace(init_anchor, "simulation_status=125\nsimulation_started=false\nsignal_name=NONE\n", 1)
    text = text.replace('plusarg=RETURN_OBSERVER,QADD_TAILROUND_BUFREADY', 'plusarg=RETURN_OBSERVER,QADD_TAILROUND_BUFREADY,CODEX_CAUSAL_OBSERVER', 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(path)
    generation = load(CANDIDATE / "source_bound_observer_generation_report.json")
    manifest.update({
        "schema": f"qlinearadd-node0007-tailround-lanephase-server-package-{TARGET.rsplit('_v', 1)[-1]}",
        "package_id": TARGET,
        "install_name": TARGET,
        "candidate_release": False,
        "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "diagnostic_only": True,
        "first_fresh_extra_audit": {"epoch_id": EPOCH, "notification_acknowledged": True, "first_fresh_after_change": True, "bound_package_id": TARGET, "upload_hold_until_final_audit_pass": True},
        "source_bound_observer": {"profile": "HIGH_INFORMATION_CAUSAL_V1", "plan_schema": "server-source-bound-probe-plan-v2", "diagnostic_semantics_sha256": generation["diagnostic_semantics_sha256"], "exact_instance_match": True, "payload_binary_known_width_fail_closed": True, "semantic_first_use_required": True},
        "source_assets": {**manifest.get("source_assets", {}), "v54_source_zip": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": SOURCE_SHA}, "v54_return_analysis": {"path": RETURN_REPORT.relative_to(ROOT).as_posix(), "bytes": RETURN_REPORT.stat().st_size, "sha256": base.sha(RETURN_REPORT)}},
        "successor": {"source": SOURCE_ID, "source_sha256": SOURCE_SHA, "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "reason": "v54 uniquely proved a temporal lane-phase supply/consumer mismatch but not the correcting config leaf", "changed_surface": ["fresh identity", "generated exact-instance source-bound observer/parser/binding", "shared JSON-only post-sim return core"], "frozen_surface": ["single op_tail_round workload/config/bitstream/execplan/SCA", "28 host diagnostic FP32 inputs and UINT8 golden outputs", "numeric/W3/qparams/tail", "2h timeout", "functional RTL"]},
        "rule_change_ack": {"epoch_id": EPOCH, "first_fresh_after_change": True, "rule_ids": ["CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001", "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001", "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001"], "upload_hold_until": "INDEPENDENT_EXTRA_AUDIT_PASS"},
        "rule_receipts": {name: {"path": rule.relative_to(ROOT).as_posix(), "sha256": base.sha(rule), "current_match": True} for name, rule in RULES.items()},
        "release_gate_matrix": {"package_bootstrap_path_runtime_D": "BLOCKING_REVALIDATE", "runner_compile_finalizer": "BLOCKING_CHANGED_SHARED_CORE", "package_local_hdl": "BLOCKING_CHANGED_GENERATED_OBSERVER", "materialized_config": "NOT_APPLICABLE_BYTE_EQUAL_RECEIPT_REUSE", "observer_canonical": "BLOCKING_TYPED_V2_FIRST_USE", "return_result_conjunction": "BLOCKING_SHARED_CORE", "numeric_W3_golden": "RECORD_ONLY_FROZEN_NOT_RERUN", "functional_RTL": "RECORD_ONLY_UNMODIFIED", "first_fresh_extra_audit": "BLOCKING_FIRST_FRESH_EXACT_ZIP"},
        "final_zip_rule_self_audit": {"required": True, "status": "PENDING_EXACT_ZIP_AUDIT"},
        "provenance": {"analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3", "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d", "generator": Path(__file__).relative_to(ROOT).as_posix()},
    })
    manifest["files"] = base.records(package)
    base.write_json(path, manifest)


def build_tree(destination: Path) -> Path:
    configure_base()
    package = base.extract(destination)
    base.replace_identity(package)
    copy_source_bound(package)
    write_post_sim_contract(package)
    patch_runner(package)
    update_manifest(package)
    base.update_path_budget(package)
    package.joinpath("README.md").write_text(
        f"# QLinearAdd node0007 isolated tail_round lane-phase {TARGET.rsplit('_v', 1)[-1]}\n\n"
        "Run: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. Workload/config/numeric/golden/timeout/RTL are frozen from v54. "
        "Generated exact-instance Buffer5 probes distinguish the remaining lane-phase chronology candidates.\n",
        encoding="utf-8", newline="\n",
    )
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["files"] = base.records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    if OUT_ZIP.exists():
        raise BuildError("fresh v55 ZIP output required")
    LOCAL.mkdir(parents=True, exist_ok=True)
    aggregate = prebuild_aggregate()
    if not aggregate["pass"]:
        raise BuildError(f"prebuild aggregate failed: {aggregate['errors']}")
    with tempfile.TemporaryDirectory(prefix="q55a-") as first, tempfile.TemporaryDirectory(prefix="q55b-") as second:
        a = build_tree(Path(first)); b = build_tree(Path(second))
        za = Path(first) / f"{TARGET}.zip"; zb = Path(second) / f"{TARGET}.zip"
        configure_base(); base.deterministic_zip(a, za); base.deterministic_zip(b, zb)
        if base.sha(za) != base.sha(zb) or za.read_bytes() != zb.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{base.sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {"schema": f"qlinearadd-node0007-tailround-lanephase-build-{TARGET.rsplit('_v', 1)[-1]}", "status": "BUILT_UPLOAD_HOLD_PENDING_EXACT_FINAL_ZIP_AUDIT", "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": base.sha(OUT_ZIP)}, "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": base.sha(sidecar)}, "source_zip_sha256": SOURCE_SHA, "deterministic_double_build": True, "rule_change_epoch_id": EPOCH, "first_fresh_after_change": True, "prebuild_aggregate_invocations": 1, "final_zip_count": 1, "numeric_workload_config_golden_repeated": False, "server_action": False}
    base.write_json(LOCAL / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
