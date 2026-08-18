#!/usr/bin/env python3
"""Build the fresh serialized Conv v100 guard-v2 successor from exact v99."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OLD = "r5_n4_hw_v99b_lcdup_guarded"
NEW = "r5_n4_hw_v100b_lcdup_guardv2"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
OUT = ROOT / "outputs/conv_node0004_v100b_lcdup_guardv2_release1"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_extract() -> None:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v99 source ZIP CRC failure")
        infos = archive.infolist()
        roots = {PurePosixPath(info.filename).parts[0] for info in infos if PurePosixPath(info.filename).parts}
        if roots != {OLD}:
            raise RuntimeError(f"v99 source ZIP root mismatch: {sorted(roots)}")
        for info in infos:
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or stat.S_ISLNK(mode):
                raise RuntimeError(f"unsafe v99 source member: {info.filename}")
        base = (OUT / "build").resolve()
        for info in infos:
            pure = PurePosixPath(info.filename)
            mapped = Path(NEW, *pure.parts[1:])
            target = (OUT / "build" / mapped).resolve()
            if base not in target.parents and target != base:
                raise RuntimeError(f"unsafe mapped v99 source member: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)


def replace_identity_in_text_tree() -> None:
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if OLD in text:
            path.write_text(text.replace(OLD, NEW), encoding="utf-8", newline="\n")


def copy_shared_assets() -> None:
    destinations = {
        ROOT / "tools/server_observer_operational_guard_v2.py": TREE / "package_tools/server_observer_operational_guard_v2.py",
        ROOT / "tools/server_observer_operational_attempt_boundary.py": TREE / "package_tools/server_observer_operational_attempt_boundary.py",
        ROOT / "tools/server_observer_runtime_supervision.py": TREE / "package_tools/server_observer_runtime_supervision.py",
        ROOT / "schemas/server_observer_operational_guard_receipt_v2.schema.json": TREE / "schemas/server_observer_operational_guard_receipt_v2.schema.json",
        ROOT / "schemas/server_observer_operational_live_tree_policy_v2.schema.json": TREE / "schemas/server_observer_operational_live_tree_policy_v2.schema.json",
        ROOT / "fixtures/server_observer_operational_guard_live_tree_v2/positive_live_tree_policy.json": TREE / "receipts/observer_operational_live_tree_policy_v2.json",
    }
    for source, target in destinations.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    legacy_base = TREE / "package_tools/server_observer_runtime_supervision_base.py"
    if legacy_base.exists():
        legacy_base.unlink()


def write_operational_contract() -> None:
    components = [
        {"component_id": "compile_outputs", "max_bytes": 8_000_000_000, "basis": "v99 compile tree ceiling"},
        {"component_id": "observer_chunks", "max_bytes": 400_000_000, "basis": "complete non-clock causal JSONL ceiling"},
        {"component_id": "simulator_log_duplication", "max_bytes": 400_000_000, "basis": "compile and simulation diagnostic logs"},
        {"component_id": "parser_rewrite_scratch", "max_bytes": 400_000_000, "basis": "streaming parser/index temporary projection"},
        {"component_id": "return_zip_staging", "max_bytes": 1_599_000_000, "basis": "bounded complete observer/core return staging"},
        {"component_id": "publication_sidecar", "max_bytes": 1_000_000, "basis": "SHA/member/durable cleanup receipts"},
    ]
    threshold = {
        "schema": "node0004-observer-operational-budget-source-v2",
        "package_id": NEW,
        "source_package": OLD,
        "components": components,
        "peak_transient_bytes": sum(item["max_bytes"] for item in components),
        "minimum_free_reserve_bytes": 20_000_000_000,
        "method": "v99 declared operational ceilings with exact six-component decomposition",
        "claim_boundary": "Package-local transient-space projection only; no production runtime or DUT claim.",
    }
    threshold_path = TREE / "receipts/operational_budget_source.json"
    threshold_path.parent.mkdir(parents=True, exist_ok=True)
    threshold_path.write_bytes(canonical(threshold))
    policy_path = TREE / "receipts/observer_operational_live_tree_policy_v2.json"
    peak = threshold["peak_transient_bytes"]
    reserve = threshold["minimum_free_reserve_bytes"]
    contract = {
        "schema": "server-observer-operational-attempt-boundary-v1",
        "activation_epoch": "observer-operational-attempt-boundary-v1",
        "package_id": NEW,
        "family": "conv_serialized_node0004",
        "threshold_source": {
            "path": "receipts/operational_budget_source.json",
            "sha256": sha_file(threshold_path),
            "units": "bytes",
            "method": threshold["method"],
        },
        "live_tree_policy": {
            "schema": "server-observer-operational-live-tree-policy-v2",
            "path": "receipts/observer_operational_live_tree_policy_v2.json",
            "sha256": sha_file(policy_path),
            "units": "bytes",
            "method": "canonical guard-live-tree-v2 no-follow policy",
        },
        "pre_run_peak_projection": {
            "components": components,
            "peak_transient_bytes": peak,
            "minimum_free_reserve_bytes": reserve,
            "start_required_free_bytes": peak + reserve,
            "unknown_or_unbounded_amplification": False,
        },
        "phase_watches": [
            {"phase": "compile", "watched_paths": ["compile", "evidence/compile_rootcause"], "growth_limit_bytes": 8_000_000_000, "remaining_projection_bytes": 2_800_000_000, "monitor_interval_seconds": 2},
            {"phase": "simulation", "watched_paths": ["evidence/observer", "c0/sim.log"], "growth_limit_bytes": 800_000_000, "remaining_projection_bytes": 2_000_000_000, "monitor_interval_seconds": 2},
            {"phase": "finalization", "watched_paths": ["evidence", "c0"], "growth_limit_bytes": 2_000_000_000, "remaining_projection_bytes": 1_600_000_000, "monitor_interval_seconds": 2},
        ],
        "operational_stop": {
            "one_shot": True, "attempt_wide": True, "preserve_completed_rows": True,
            "flush_all_flushable_rows": True, "partial_exit_marker": True, "term_wait_kill_reap": True,
            "event_cap": None, "byte_cap": None, "sampling": False, "truncation": False,
            "rolling_overwrite": False, "size_based_evidence_deletion": False,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "forbidden_claims": ["NATURAL_TERMINAL", "FORMAL_D", "E4", "E5"],
        },
        "durable_partial_return": {
            "atomic_unique_publication": True, "zip_crc_verified": True,
            "exact_member_set_verified": True, "sidecar_bytes_sha256_verified": True,
            "streaming_or_bounded_staging": True, "recursive_self_staging_forbidden": True,
        },
        "post_durable_cleanup": {
            "after_durable_return_only": True,
            "exact_owned_attempt_and_bootstrap_leaves_only": True,
            "root_and_ancestor_symlinks_forbidden": True,
            "internal_owned_symlink_entries_no_follow": True,
            "internal_symlink_target_traversal_forbidden": True,
            "lexical_target_escape_forbidden": True,
            "special_entries_forbidden": True,
            "bounded_live_tree_resampling": True,
            "post_durable_unlink_internal_links_no_follow": True,
            "preserve_foreign_siblings": True,
            "failed_publication_uncleaned": True,
        },
        "claim_boundary": "Guard-v2 operational safety only; no production compile, simulation, tuple10, natural-terminal or Formal-D claim.",
    }
    (TREE / "contracts/observer_operational_attempt_boundary.json").write_bytes(canonical(contract))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label} anchor count differs: {count}")
    return text.replace(old, new)


def rewrite_runner() -> None:
    runner_path = TREE / "PREPARE_AND_RUN.sh"
    text = runner_path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "finalization_guard_receipt=\n",
        "finalization_guard_receipt=\noperational_contract=\noperational_preflight_receipt=\noperational_phase_samples=\noperational_stop_receipt=\noperational_guard_log=\ncompile_guard_exit_classification=\ndurable_return_receipt=\npost_durable_cleanup_receipt=\noperational_sidecar=\n",
        "operational variables",
    )
    old_paths = 'cfg_root="$CFG_ROOT"; run_root="$RUN_ROOT"; evidence_root="$EVIDENCE_ROOT"; compile_root="$COMPILE_ROOT"; guard_receipt="$evidence_root/OPERATIONAL_GUARD_RECEIPT.json"; compile_guard_receipt="$evidence_root/COMPILE_OPERATIONAL_GUARD_RECEIPT.json"; finalization_guard_receipt="$evidence_root/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json"'
    new_paths = 'cfg_root="$CFG_ROOT"; run_root="$RUN_ROOT"; evidence_root="$EVIDENCE_ROOT"; compile_root="$COMPILE_ROOT"; operational_contract="$package_root/contracts/observer_operational_attempt_boundary.json"; operational_preflight_receipt="$evidence_root/OPERATIONAL_PREFLIGHT_RECEIPT.json"; operational_phase_samples="$evidence_root/OPERATIONAL_PHASE_SAMPLES.jsonl"; operational_stop_receipt="$evidence_root/OPERATIONAL_STOP_RECEIPT.json"; guard_receipt="$operational_stop_receipt"; compile_guard_receipt="$evidence_root/COMPILE_OPERATIONAL_GUARD_RECEIPT.json"; finalization_guard_receipt="$evidence_root/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json"; operational_guard_log="$evidence_root/OPERATIONAL_GUARD_STDERR.log"; compile_guard_exit_classification="$evidence_root/COMPILE_GUARD_EXIT_CLASSIFICATION.json"; durable_return_receipt="$result_root/${package_id}_${return_tag}_DURABLE_RETURN_RECEIPT.json"; post_durable_cleanup_receipt="$result_root/${package_id}_${return_tag}_POST_DURABLE_CLEANUP_RECEIPT.json"; operational_sidecar="$return_zip.operational.json"'
    text = replace_once(text, old_paths, new_paths, "guard v2 paths")
    mkdir_line = 'mkdir -p "$run_root/c0" "$evidence_root/compile_rootcause" "$evidence_root/compiled_source" "$evidence_root/observer/chunks" "$compile_root/sim_results" || runner_fail 14 "attempt layout create failed"'
    preflight = mkdir_line + '\n# server_observer_operational_attempt_boundary.py preflight\npython3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" preflight --contract "$operational_contract" --attempt-root "$run_root" --receipt "$operational_preflight_receipt" || runner_fail 122 "operational preflight failed"'
    text = replace_once(text, mkdir_line, preflight, "operational preflight")
    old_compile = 'set +e; python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --mode compile --attempt-root "$run_root" --owned-root "$bootstrap_root" --cwd "$server_root" --disk-path "$server_root/install" --min-free-bytes 20000000000 --growth-limit-bytes 8000000000 --watch "compile_log=$compile_log=200000000" --file-size-limit-bytes 500000000 --timeout 7200 --interval 2 --grace 30 --receipt "$compile_guard_receipt" --log "$compile_log" -- "${compile_argv[@]}"; compile_status=$?; set -e'
    new_compile = 'set +e; python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" supervise-phase --phase compile --contract "$operational_contract" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --samples "$operational_phase_samples" --receipt "$compile_guard_receipt" --guard-log "$operational_guard_log" --timeout 7200 --grace 30 -- "${compile_argv[@]}"; compile_status=$?; set -e\n[ -f "$operational_guard_log" ] && cp -f "$operational_guard_log" "$compile_full_log"\nif [ -f "$compile_guard_receipt" ]; then python3 "$package_root/package_tools/server_observer_operational_guard_v2.py" classify-exit --exit-code "$compile_status" --receipt "$compile_guard_receipt" --output "$compile_guard_exit_classification"; else python3 "$package_root/package_tools/server_observer_operational_guard_v2.py" classify-exit --exit-code "$compile_status" --output "$compile_guard_exit_classification"; fi'
    text = replace_once(text, old_compile, new_compile, "guarded compile v2")
    old_failure = '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed"'
    new_failure = '''if [ "$compile_status" -ne 0 ]; then
  production_compile_error="$(python3 - "$compile_guard_exit_classification" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); print(str(json.loads(p.read_text()).get("production_compile_error",False)).lower() if p.is_file() else "false")
PY
)"
  [ "$production_compile_error" = true ] && runner_fail "$compile_status" "production compile failed"
  runner_fail 122 "operational compile infrastructure failure"
fi'''
    text = replace_once(text, old_failure, new_failure, "compile exit classification")
    old_sim = 'DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --mode simulation --attempt-root "$run_root" --cwd "$server_root" --disk-path "$server_root/install" --min-free-bytes 20000000000 --growth-limit-bytes 800000000 --watch "observer=$observer_chunk=400000000" --watch "sim_log=$run_root/c0/sim.log=200000000" --file-size-limit-bytes 500000000 --timeout 3600 --interval 2 --grace 45 --receipt "$guard_receipt" -- python3 "$package_root/package_tools/server_observer_runtime_supervision_base.py" supervise'
    new_sim = 'DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" supervise-phase --phase simulation --contract "$operational_contract" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --samples "$operational_phase_samples" --receipt "$operational_stop_receipt" --guard-log "$operational_guard_log" --timeout 3600 --grace 45 -- python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise'
    text = replace_once(text, old_sim, new_sim, "guarded simulation v2")
    old_final = 'python3 "$package_root/package_tools/server_observer_runtime_supervision.py" supervise --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --mode finalization --attempt-root "$run_root" --owned-root "$bootstrap_root" --cwd "$server_root" --disk-path "$server_root/install" --min-free-bytes 20000000000 --growth-limit-bytes 2000000000 --timeout 900 --interval 2 --grace 30 --receipt "$finalization_guard_receipt" -- python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"'
    new_final = 'python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" supervise-phase --phase finalization --contract "$operational_contract" --execution-id "$return_tag" --attempt-id "$attempt" --attempt-root "$run_root" --cwd "$server_root" --samples "$operational_phase_samples" --receipt "$finalization_guard_receipt" --guard-log "$operational_guard_log" --timeout 900 --grace 30 -- python3 "$package_root/package_tools/server_post_sim_return.py" finalize --request "$package_root/contracts/server_post_sim_return_request.json"'
    text = replace_once(text, old_final, new_final, "guarded finalization v2")
    old_cleanup = 'if [ -f "$return_zip" ]; then python3 "$package_root/package_tools/server_package_attempt_cleanup.py" --server-root "$server_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --run-root "$run_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip" --finalization-guard-receipt "$finalization_guard_receipt" --output "$cleanup_receipt"; cleanup_rc=$?; fi'
    new_cleanup = '''if [ -f "$return_zip" ]; then
    # DURABLE_RETURN_RECEIPT must be verified before package-owned cleanup.
    python3 - "$return_zip" "$operational_sidecar" <<'PY'
import hashlib,json,pathlib,sys,zipfile
z,s=map(pathlib.Path,sys.argv[1:]); h=hashlib.sha256(); size=0
with z.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""): size+=len(b); h.update(b)
with zipfile.ZipFile(z) as a: names=a.namelist(); bad=a.testzip()
if bad is not None: raise SystemExit("return CRC failure")
s.write_text(json.dumps({"bytes":size,"sha256":h.hexdigest(),"members":names},indent=2,sort_keys=True)+"\\n")
PY
    python3 "$package_root/package_tools/server_observer_operational_attempt_boundary.py" cleanup-after-durable-return --contract "$operational_contract" --attempt-root "$run_root" --return-zip "$return_zip" --sidecar "$operational_sidecar" --owned-leaf "evidence/observer" --receipt "$durable_return_receipt"
    durable_rc=$?
    [ "$durable_rc" -eq 0 ] && python3 "$package_root/package_tools/server_package_attempt_cleanup.py" --server-root "$server_root" --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" --run-root "$run_root" --bootstrap-root "$bootstrap_root" --return-zip "$return_zip" --finalization-guard-receipt "$finalization_guard_receipt" --output "$post_durable_cleanup_receipt"
    cleanup_rc=$?
    [ -f "$post_durable_cleanup_receipt" ] && cp -f "$post_durable_cleanup_receipt" "$cleanup_receipt"
  fi'''
    text = replace_once(text, old_cleanup, new_cleanup, "durable cleanup v2")
    publish_loop = 'for source in "$guard_receipt" "$compile_guard_receipt" "$finalization_guard_receipt" "$evidence_root/PROCESS_TREE_RECEIPT.json" "$evidence_root/SIM_EXIT_RECEIPT.json"; do'
    expanded = 'for source in "$guard_receipt" "$compile_guard_receipt" "$finalization_guard_receipt" "$operational_preflight_receipt" "$operational_phase_samples" "$operational_guard_log" "$compile_guard_exit_classification" "$evidence_root/PROCESS_TREE_RECEIPT.json" "$evidence_root/SIM_EXIT_RECEIPT.json"; do'
    text = replace_once(text, publish_loop, expanded, "minimal operational evidence")
    runner_path.write_text(text, encoding="utf-8", newline="\n")


def update_return_contracts() -> None:
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = json.loads(allow_path.read_text(encoding="utf-8"))
    additions = [
        "OPERATIONAL_PREFLIGHT_RECEIPT.json", "OPERATIONAL_PHASE_SAMPLES.jsonl",
        "OPERATIONAL_STOP_RECEIPT.json", "DURABLE_RETURN_RECEIPT.json",
        "POST_DURABLE_CLEANUP_RECEIPT.json", "OPERATIONAL_GUARD_STDERR.log",
    ]
    for basename in additions:
        member = f"{NEW}_return/evidence/{basename}"
        if member not in allow["required"]:
            allow["required"].append(member)
    allow_path.write_bytes(canonical(allow))

    runner_contract_path = TREE / "contracts/server_runner_return_resilience.json"
    runner_contract = json.loads(runner_contract_path.read_text(encoding="utf-8"))
    runner_contract["runner_sha256"] = sha_file(TREE / "PREPARE_AND_RUN.sh")
    runner_contract_path.write_bytes(canonical(runner_contract))

    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    existing = {item["archive"] for item in request["core_entries"]}
    for basename in (
        "OPERATIONAL_PREFLIGHT_RECEIPT.json", "OPERATIONAL_PHASE_SAMPLES.jsonl",
        "OPERATIONAL_STOP_RECEIPT.json", "FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
        "OPERATIONAL_GUARD_STDERR.log", "COMPILE_GUARD_EXIT_CLASSIFICATION.json",
    ):
        archive = f"evidence/{basename}"
        if archive not in existing:
            request["core_entries"].append({"archive": archive, "required": False, "source": archive, "source_root": "attempt"})
    for package_member in (
        "contracts/observer_operational_attempt_boundary.json",
        "receipts/observer_operational_live_tree_policy_v2.json",
        "schemas/server_observer_operational_guard_receipt_v2.schema.json",
        "schemas/server_observer_operational_live_tree_policy_v2.schema.json",
    ):
        archive = "evidence/" + PurePosixPath(package_member).name
        if archive not in existing:
            request["core_entries"].append({"archive": archive, "required": True, "source": package_member, "source_root": "package"})
    request_path.write_bytes(canonical(request))

    post_contract_path = TREE / "contracts/server_post_sim_return_contract.json"
    post_contract = json.loads(post_contract_path.read_text(encoding="utf-8"))
    post_contract["request_sha256"] = sha_file(request_path)
    post_contract_path.write_bytes(canonical(post_contract))


def update_package_preflight() -> None:
    path = TREE / "package_tools/package_release_preflight.py"
    text = path.read_text(encoding="utf-8")
    old = '''    required_runner = (
        "server_observer_runtime_supervision.py",
        "--min-free-bytes 20000000000",
        "--growth-limit-bytes 800000000",
        "observer=$observer_chunk=400000000",
        "sim_log=$run_root/c0/sim.log=200000000",
        "server_package_attempt_cleanup.py",
        "filter_source_bound_log.py",
    )'''
    new = '''    required_runner = (
        "server_observer_operational_attempt_boundary.py",
        "supervise-phase --phase compile",
        "supervise-phase --phase simulation",
        "supervise-phase --phase finalization",
        "--guard-log",
        "cleanup-after-durable-return",
        "server_package_attempt_cleanup.py",
        "filter_source_bound_log.py",
    )'''
    text = replace_once(text, old, new, "package preflight guard tokens")
    path.write_text(text, encoding="utf-8", newline="\n")


def regenerate_source_bound_observer() -> None:
    generated = OUT / "source_bound_regenerated"
    command = [
        sys.executable,
        str(ROOT / "tools/generate_server_source_bound_observer.py"),
        "materialize",
        "--catalog", str(TREE / "diagnostics/source_bound_probe_catalog.json"),
        "--plan", str(TREE / "diagnostics/source_bound_probe_plan.json"),
        "--output-dir", str(generated),
        "--report", str(generated / "source_bound_observer_generation_report.json"),
        "--cheap-check-output", str(generated / "cheap_prebuild.json"),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"source-bound regeneration failed: {completed.stderr[-4096:]}")
    destinations = {
        "source_bound_causal_observer.svh": (
            "diagnostics/source_bound_causal_observer.svh",
            "tb_probe/source_bound_causal_observer.svh",
        ),
        "source_bound_causal_parser.py": (
            "diagnostics/source_bound_causal_parser.py",
            "package_tools/source_bound_causal_parser.py",
        ),
        "source_bound_observer_focus.sv": ("diagnostics/source_bound_observer_focus.sv",),
        "source_bound_probe_binding.json": ("diagnostics/source_bound_probe_binding.json",),
        "source_bound_observer_generation_report.json": ("diagnostics/source_bound_observer_generation_report.json",),
    }
    for name, relatives in destinations.items():
        for relative in relatives:
            shutil.copyfile(generated / name, TREE / relative)


def update_manifest_and_readme() -> None:
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": "node0004-v100b-lcdup-guardv2-package-manifest-v1",
        "activation_epoch": "observer-operational-guard-live-tree-v2",
        "observer_only_contract_sha256": sha_file(TREE / "contracts/observer_only_wide_causal_contract.json"),
        "source_package": OLD,
        "previous_version_progress": "v99 production VCS reached elaboration/link preparation, but the v1 live-tree monitor exited without mandatory receipts before simulation; tuple10 was not tested.",
        "current_purpose": "Run the frozen LC9-to-LC3 tuple10 diagnostic with canonical no-follow live-tree guard-v2, emergency receipt/reap and durable cleanup classification.",
        "diagnostic_mode": "OBSERVER_ONLY_WIDE_CAUSAL_GUARDED",
        "first_fresh_after_change": True,
        "first_fresh_semantic_version": 4,
        "status": "PACKAGE_READY_NOT_RUN",
        "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
        "server_actions_performed": [],
    })
    provenance = TREE / "provenance"
    shutil.copy2(
        ROOT / "outputs/conv_node0004_v99b_lcdup_guarded_return_r1786886164441131999_3461318/formal_return_analysis.json",
        provenance / "v99b_formal_return_analysis.json",
    )
    shutil.copy2(
        ROOT / "outputs/conv_node0004_v99b_lcdup_guarded_return_r1786886164441131999_3461318/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json",
        provenance / "v99b_package_build_failure_rule_audit.json",
    )
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))
    readme = TREE / "README.md"
    readme.write_text(
        "# Serialized Conv node0004 v100 guard-v2\n\n"
        "Previous progress: v99 reached production VCS elaboration/link preparation but its v1 operational monitor failed before simulation, so tuple10 was not tested.\n\n"
        "Current purpose: preserve the mapper-proven LC9-to-LC3 duplication and the 52-signal tuple10/downstream/natural-terminal/Formal-D target while using canonical live-tree guard-v2.\n\n"
        "Future command after mainline storage publication and separate server authorization:\n\n"
        f"`bash {NEW}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`\n\n"
        "This package has not been uploaded or run.\n",
        encoding="utf-8", newline="\n",
    )
    manifest["files"] = file_map()
    manifest_path.write_bytes(canonical(manifest))


def file_map() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha_file(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def deterministic_zip() -> None:
    with zipfile.ZipFile(ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            name = f"{NEW}/{path.relative_to(TREE).as_posix()}"
            info = zipfile.ZipInfo(name, (2026, 8, 16, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def main() -> int:
    if OUT.exists():
        raise SystemExit(f"fresh output already exists: {OUT}")
    OUT.mkdir(parents=True)
    safe_extract()
    replace_identity_in_text_tree()
    copy_shared_assets()
    write_operational_contract()
    rewrite_runner()
    update_return_contracts()
    update_package_preflight()
    regenerate_source_bound_observer()
    update_manifest_and_readme()
    deterministic_zip()
    receipt = {
        "schema": "node0004-v100b-lcdup-guardv2-build-v1",
        "package_id": NEW,
        "source_zip": {"path": str(SOURCE_ZIP.relative_to(ROOT)), "bytes": SOURCE_ZIP.stat().st_size, "sha256": sha_file(SOURCE_ZIP)},
        "package_zip": {"path": str(ZIP.relative_to(ROOT)), "bytes": ZIP.stat().st_size, "sha256": sha_file(ZIP)},
        "changed_surface": ["fresh identity", "guard-v2 live-tree runtime/schema/policy", "three-phase boundary runner", "guard exit classification", "durable cleanup receipts"],
        "frozen_surface": ["config", "numeric", "workload", "golden", "functional RTL", "LC9-to-LC3 mapper semantics", "52-signal tuple10 target"],
        "server_actions": [],
        "storage_manager_called": False,
        "status": "LOCAL_BUILD_PENDING_GATES",
    }
    (OUT / "build_receipt.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
