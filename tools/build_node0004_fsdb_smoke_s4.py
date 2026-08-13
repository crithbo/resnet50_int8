#!/usr/bin/env python3
"""Build the fresh serialized-Conv FSDB quiescence diagnostic smoke s4.

The s2/s3 workload, registered smoke probe, config, numeric and golden assets
remain byte/semantic frozen.  This builder changes only the fresh package
identity and the activated simulator-process/quiescence/return surfaces.
"""

from __future__ import annotations

import json
import shutil

import build_node0004_fsdb_smoke_s2 as fixed


base = fixed.base
PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s4"
OLD_ID = "r5_n4_hw_fsdbsmoke_s2"
EPOCH = "waveform-retention-fsdb-quiescence-v1-967ef4e72e6c"

base.PACKAGE_ID = PACKAGE_ID
base.OUT = base.ROOT / "outputs/conv_node0004_fsdb_smoke_s4_quiescence_release1"
base.BUILD_ROOT = base.OUT / "build" / PACKAGE_ID
base.FINAL_ZIP = base.OUT / f"{PACKAGE_ID}.zip"
for name in ("RUNTIME_HELPER", "README", "RUNNER"):
    setattr(base, name, getattr(base, name).replace(OLD_ID, PACKAGE_ID))
base.README = base.README.replace("smoke s1", "smoke s4").replace("smoke s2", "smoke s4")
base.README += """

This fresh diagnostic smoke uses the activated process-tree quiescence gate:
the simulator is supervised as a direct child in a fresh Linux session/PGID
under a child subreaper, emits identity-bound simulation-time heartbeats, and
is archived only after complete process reaping and two stable FSDB snapshots.
"""


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"runner patch anchor count={text.count(old)} for {old!r}")
    return text.replace(old, new, 1)


runner = base.RUNNER
runner = replace_once(
    runner,
    "query_receipt_rc=0\n",
    "query_receipt_rc=0\n"
    "quiescence_helper=\"${package_root}/package_tools/server_fsdb_runtime_quiescence.py\"\n"
    "process_tree_receipt=\n"
    "sim_time_heartbeat=\n"
    "fsdb_quiescence_receipt=\n"
    "quiescence_rc=0\n"
    "supervisor_status=125\n",
)
runner = replace_once(
    runner,
    "on_signal() { signal_status=\"$1\"; [ -z \"$sim_pid\" ] || kill -TERM \"$sim_pid\" 2>/dev/null; finalize \"$2\"; }",
    "on_signal() { signal_status=\"$1\"; if [ -n \"$sim_pid\" ]; then kill -TERM \"$sim_pid\" 2>/dev/null; wait \"$sim_pid\" 2>/dev/null; supervisor_status=$?; run_status=$supervisor_status; sim_pid=; fi; finalize \"$2\"; }",
)
runner = replace_once(
    runner,
    "eval \"$layout_values\"; cfg_root=\"$CFG_ROOT\"; run_root=\"$RUN_ROOT\"; evidence_root=\"$EVIDENCE_ROOT\"; compile_root=\"$COMPILE_ROOT\"\n",
    "eval \"$layout_values\"; cfg_root=\"$CFG_ROOT\"; run_root=\"$RUN_ROOT\"; evidence_root=\"$EVIDENCE_ROOT\"; compile_root=\"$COMPILE_ROOT\"\n"
    "quiescence_helper=\"${package_root}/package_tools/server_fsdb_runtime_quiescence.py\"\n"
    "process_tree_receipt=\"$evidence_root/fsdb_process_tree_receipt.json\"\n"
    "sim_time_heartbeat=\"$evidence_root/sim_time_heartbeat.jsonl\"\n"
    "fsdb_quiescence_receipt=\"$evidence_root/fsdb_quiescence_receipt.json\"\n",
)
runner = replace_once(
    runner,
    "  mkdir -p -- \"$evidence_root/waveform\"\n  python3 \"$package_root/package_tools/server_waveform_mandatory_return.py\" collect-runtime",
    "  mkdir -p -- \"$evidence_root/waveform\"\n"
    "  if [ \"$sim_started\" = true ]; then\n"
    "    python3 \"$quiescence_helper\" quiesce --attempt-root \"$run_root\" --process-receipt \"$process_tree_receipt\" --heartbeat \"$sim_time_heartbeat\" --plateau-seconds 300 --settle-seconds 2 --output \"$fsdb_quiescence_receipt\"; quiescence_rc=$?\n"
    "    if [ ! -f \"$fsdb_quiescence_receipt\" ]; then\n"
    "      python3 - \"$fsdb_quiescence_receipt\" \"$quiescence_rc\" <<'PY'\n"
    "import json,pathlib,sys\n"
    "pathlib.Path(sys.argv[1]).write_text(json.dumps({\"schema\":\"server-fsdb-runtime-quiescence-v1\",\"kind\":\"quiescence_receipt\",\"rule_id\":\"CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001\",\"stable_exact_set\":False,\"diagnostic_status\":\"DIAGNOSTIC_EVIDENCE_INCOMPLETE\",\"pass\":False,\"errors\":[\"quiescence helper failed before publishing a receipt; exit=\"+sys.argv[2]],\"failure_isolation\":\"Raw FSDB and compile/sim/signal/core return remain publishable as PARTIAL evidence.\",\"claim_boundary\":\"Process-tree, simulation-time heartbeat and stable FSDB snapshot only.\"},indent=2,sort_keys=True)+\"\\n\")\n"
    "PY\n"
    "    fi\n"
    "  fi\n"
    "  python3 \"$package_root/package_tools/server_waveform_mandatory_return.py\" collect-runtime",
)
runner = replace_once(
    runner,
    "final=\"$original\"; [ \"$final\" -ne 0 ] || [ \"$core\" -eq 0 ] || final=\"$core\"; [ \"$root_gate_rc\" -eq 0 ] || final=96; [ \"$waveform_receipt_rc\" -eq 0 ] || final=97; [ \"$query_receipt_rc\" -eq 0 ] || [ \"$final\" -ne 0 ] || final=95",
    "final=\"$original\"; [ \"$final\" -ne 0 ] || [ \"$core\" -eq 0 ] || final=\"$core\"; [ \"$root_gate_rc\" -eq 0 ] || final=96; [ \"$waveform_receipt_rc\" -eq 0 ] || final=97; [ \"$query_receipt_rc\" -eq 0 ] || [ \"$final\" -ne 0 ] || final=95; [ \"$quiescence_rc\" -eq 0 ] || [ \"$final\" -ne 0 ] || final=94",
)
old_run = r'''DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 timeout --foreground --signal=TERM --kill-after=30s 6h "$simv" -ucli -i "$runtime_dump_tcl" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_FSDB_SMOKE_QUERY &
sim_pid=$!
( while kill -0 "$sim_pid" 2>/dev/null; do read -r host_monotonic _ < /proc/uptime; printf 'host_epoch=%s host_monotonic=%s stage=fsdb_smoke sim_log_bytes=%s\n' "$(date +%s)" "$host_monotonic" "$(wc -c < "$run_root/c0/sim.log" 2>/dev/null || printf 0)"; sleep 60; done ) > "$run_root/c0/host_progress.log" 2>&1 &
host_progress_pid=$!; wait "$sim_pid"; run_status=$?; sim_pid=; kill "$host_progress_pid" 2>/dev/null; wait "$host_progress_pid" 2>/dev/null; host_progress_pid=; exit "$run_status"'''
new_run = '''DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0 python3 "$quiescence_helper" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --receipt "$process_tree_receipt" --heartbeat-source "$run_root/c0/sim.log" --heartbeat-output "$sim_time_heartbeat" --heartbeat-regex 'CODEX_FSDB_SMOKE_EVENT_V1.*time_tick=([0-9]+)' --timescale 1ps --heartbeat-interval 30 --term-grace 30 --kill-grace 10 --runtime-timeout-seconds 21600 -- "$simv" -ucli -i "$runtime_dump_tcl" -l "$run_root/c0/sim.log" +vcs+lic+wait "+SCA_CFG=$cfg_root/runs/c0/sca_cfg.json" "+SCA_CFG_D=$cfg_root/runs/c0/sca_cfg_D.json" +CODEX_FSDB_SMOKE_QUERY &
sim_pid=$!
wait "$sim_pid"; supervisor_status=$?; run_status=$supervisor_status; sim_pid=
if [ -f "$process_tree_receipt" ] && python3 - "$process_tree_receipt" <<'PY'
import json,sys
raise SystemExit(0 if json.load(open(sys.argv[1],encoding="utf-8")).get("termination_reason")=="TIMEOUT" else 1)
PY
then run_status=124; fi
exit "$run_status"'''
runner = replace_once(runner, old_run, new_run)
base.RUNNER = runner

# The package-local cheap preflight must require the new exact helper.
base.RUNTIME_HELPER = replace_once(
    base.RUNTIME_HELPER,
    '"package_tools/server_post_sim_return.py","package_tools/server_package_runtime_layout.py",',
    '"package_tools/server_post_sim_return.py","package_tools/server_package_runtime_layout.py","package_tools/server_fsdb_runtime_quiescence.py",',
)


ORIGINAL_POST_REQUEST = base.post_request


def _post_request_with_quiescence() -> dict[str, object]:
    request = ORIGINAL_POST_REQUEST()
    entries = request["core_entries"]
    assert isinstance(entries, list)
    entries.extend(
        [
            {"source_root": "attempt", "source": "evidence/fsdb_process_tree_receipt.json", "archive": "evidence/fsdb_process_tree_receipt.json", "required": False},
            {"source_root": "attempt", "source": "evidence/sim_time_heartbeat.jsonl", "archive": "evidence/sim_time_heartbeat.jsonl", "required": False},
            {"source_root": "attempt", "source": "evidence/fsdb_quiescence_receipt.json", "archive": "evidence/fsdb_quiescence_receipt.json", "required": False},
        ]
    )
    request["claim_boundary"] = "Core and authoritative raw FSDB return survive query or quiescence failure; process-tree, heartbeat and stable-snapshot evidence are same-attempt bound."
    return request


base.post_request = _post_request_with_quiescence


def refresh_package() -> None:
    package = base.BUILD_ROOT
    helper = package / "package_tools/server_fsdb_runtime_quiescence.py"
    shutil.copyfile(base.ROOT / "tools/server_fsdb_runtime_quiescence.py", helper)

    contract = {
        "schema": "node0004-fsdb-smoke-quiescence-integration-v1",
        "package_id": PACKAGE_ID,
        "activation_epoch": EPOCH,
        "rule_id": "CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001",
        "helper": {"member": "package_tools/server_fsdb_runtime_quiescence.py", "bytes": helper.stat().st_size, "sha256": base.sha(helper.read_bytes())},
        "supervision": {"child_subreaper": True, "fresh_session_and_pgid": True, "internal_timeout_seconds": 21600, "term_grace_seconds": 30, "kill_grace_seconds": 10, "root_and_adopted_reap_required": True},
        "heartbeat": {"source": "c0/sim.log", "output": "evidence/sim_time_heartbeat.jsonl", "timescale": "1ps", "interval_seconds": 30, "plateau_seconds": 300, "same_attempt_progress_required": True},
        "snapshot": {"output": "evidence/fsdb_quiescence_receipt.json", "settle_seconds": 2, "two_identity_equal_snapshots": True, "reject_lock_temp_empty": True},
        "failure": "PRESERVE_PARTIAL_RAW_AND_CORE_RETURN_DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "claim_boundary": "Runtime process-tree, simulation-time and FSDB snapshot integrity only; no DUT/RTL/config/numeric/natural-terminal/formal-D claim.",
    }
    base.write_json("contracts/server_fsdb_runtime_quiescence.json", contract)

    request_path = package / "contracts/server_post_sim_return_request.json"
    base.write_json("contracts/server_post_sim_return_request.json", _post_request_with_quiescence())

    post_contract_path = package / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["request_sha256"] = base.sha(request_path.read_bytes())
    post_contract["quiescence_failure_blocks_core_return"] = False
    post_contract["quiescence_receipts"] = [
        "evidence/fsdb_process_tree_receipt.json",
        "evidence/sim_time_heartbeat.jsonl",
        "evidence/fsdb_quiescence_receipt.json",
    ]
    base.write_json("contracts/server_post_sim_return_contract.json", post_contract)

    resilience_path = package / "contracts/server_runner_return_resilience.json"
    resilience = json.loads(resilience_path.read_text(encoding="utf-8"))
    resilience["runner_sha256"] = base.sha((package / "PREPARE_AND_RUN.sh").read_bytes())
    resilience["package_owned_variables"].extend(
        ["quiescence_helper", "process_tree_receipt", "sim_time_heartbeat", "fsdb_quiescence_receipt", "quiescence_rc", "supervisor_status"]
    )
    resilience["return_allowlist_tokens"].extend(
        ["server_fsdb_runtime_quiescence.py", "fsdb_process_tree_receipt.json", "sim_time_heartbeat.jsonl", "fsdb_quiescence_receipt.json"]
    )
    base.write_json("contracts/server_runner_return_resilience.json", resilience)

    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["path_budget"]["additional_projected_paths"].extend(
        [
            f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/fsdb_process_tree_receipt.json",
            f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/sim_time_heartbeat.jsonl",
            f"install/codex_runs/{PACKAGE_ID}/{{attempt}}/evidence/fsdb_quiescence_receipt.json",
        ]
    )
    layout["simulator_process_tree"] = {"helper_member": "package_tools/server_fsdb_runtime_quiescence.py", "fresh_session_and_pgid": True, "child_subreaper": True, "signal_wait_before_finalizer": True}
    base.write_json("SERVER_RUNTIME_LAYOUT_CONTRACT.json", layout)

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "activation_epoch": EPOCH,
            "previous_version_progress": "s2 production compile passed, FSDB writer started and simulation advanced to 2.446091 ms; it then plateaued for at least 42 minutes and an INT return captured a still-changing FSDB set. The unrun s3 runtime is equivalent and remains held.",
            "current_purpose": "Production-prove child-subreaper process-tree termination/reaping, identity-bound simulation-time heartbeat and two stable FSDB snapshots before return publication; this is not a formal serialized Conv successor.",
            "quiescence_contract": "contracts/server_fsdb_runtime_quiescence.json",
            "allowed_changed_surfaces": ["fresh_identity", "simulator_process_supervision", "simulation_time_heartbeat", "fsdb_stable_snapshot", "return_identity"],
        }
    )
    manifest["files"] = [row for row in base.file_map() if row["path"] != "package_manifest.json"]
    base.write_json("package_manifest.json", manifest)
    base.deterministic_zip(package, base.FINAL_ZIP)
    base.write_json(
        "../../release_receipt.json",
        {
            "schema": "node0004-fsdb-smoke-release-receipt-v1",
            "package_id": PACKAGE_ID,
            "status": "PACKAGE_BUILT_AWAITING_GATES",
            "zip": base.file_identity(base.FINAL_ZIP),
            "runner": base.file_identity(package / "PREPARE_AND_RUN.sh"),
            "manifest": base.file_identity(manifest_path),
            "activation_epoch": EPOCH,
            "server_action": "NONE",
        },
    )


def main() -> int:
    status = base.main()
    if status == 0:
        refresh_package()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
