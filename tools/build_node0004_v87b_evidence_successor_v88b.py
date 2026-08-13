#!/usr/bin/env python3
"""Build the local-only serialized-Conv v88b evidence-hardening successor."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v86b_waveform_successor_v87b as legacy


SOURCE = "r5_n4_hw_v87b_mandatory_vpd"
INSTALL = "r5_n4_hw_v88b_portvcd"
FAMILY = "conv_serialized_node0004"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested"
    / FAMILY
    / SOURCE
    / f"{SOURCE}.zip"
)
SOURCE_SHA256 = "6fb39c67759f42fd0d3ffe8485cdcbb645c20618eacbc049e309feeba9b0a0da"
OUT = ROOT / "outputs/conv_node0004_v88b_portable_ack_identity_release1"
BUILD = OUT / "build"
RULE_EPOCH = "waveform-portable-local-decodability-v1-b0a94cf60d6e"
PORTABLE_RULE = "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001"
WAVE_RULE = "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001"

PORTABLE_TOOL = ROOT / "tools/server_waveform_portable_query.py"
LOCAL_ANALYSIS_TOOL = ROOT / "tools/server_waveform_local_analysis.py"
SOURCE_ID_TOOL = ROOT / "tools/node0004_actual_compile_source_identity.py"
QUERY_PARSER = ROOT / "tools/node0004_v88_portable_query_parser.py"
PHASE_PRESERVER = ROOT / "tools/node0004_v88_phase_raw_preserver.py"
QUERY_OBSERVER = ROOT / "tools/node0004_v88_portable_query_observer.svh"
POST_SIM_TOOL = ROOT / "tools/server_post_sim_return.py"
WAVE_TOOL = ROOT / "tools/server_waveform_mandatory_return.py"

POST_REQUEST = "contracts/server_post_sim_return_request.json"
POST_CONTRACT = "contracts/server_post_sim_return_contract.json"
RUNNER_CONTRACT = "contracts/server_runner_return_resilience.json"
WAVE_PLAN = "contracts/server_waveform_mandatory_plan.json"
PORTABLE_PROFILE = "contracts/server_waveform_portable_query_profile.json"
PORTABLE_SOURCE_REPORT = "diagnostics/portable_query_source_generation_report.json"

TARGET_INSTANCE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new."
    "slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group."
    "slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
    "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine.u_Buffer_AG_Idx_Queue"
)
QUERY_INSTANCE = TARGET_INSTANCE + ".codex_probe_ack_portable_inst"


class BuildError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def receipt(path: Path) -> dict[str, Any]:
    return {"path": relative(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def run(command: list[str], *, allowed: set[int] | None = None) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if process.returncode not in ({0} if allowed is None else allowed):
        raise BuildError(
            f"command failed ({process.returncode}): {' '.join(command)}\n"
            f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )
    return process


def inspect_source_zip() -> dict[str, bytes]:
    if not SOURCE_ZIP.is_file() or sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("tested v87b source ZIP identity differs or is absent")
    members: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("tested v87b source ZIP CRC failure")
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if (
                info.filename in seen
                or member.is_absolute()
                or ".." in member.parts
                or "\\" in info.filename
                or mode == stat.S_IFLNK
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            seen.add(info.filename)
            if member.parts:
                roots.add(member.parts[0])
            if not info.is_dir() and len(member.parts) > 1:
                members[PurePosixPath(*member.parts[1:]).as_posix()] = archive.read(info)
    if roots != {SOURCE}:
        raise BuildError(f"tested source root differs: {sorted(roots)}")
    return members


SOURCE_MEMBERS = inspect_source_zip()


def source_member(name: str) -> bytes:
    try:
        return SOURCE_MEMBERS[name]
    except KeyError as error:
        raise BuildError(f"tested v87b source member absent: {name}") from error


def replace_identity(data: bytes) -> bytes:
    try:
        return data.decode("utf-8").replace(SOURCE, INSTALL).encode("utf-8")
    except UnicodeDecodeError:
        return data


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"runner anchor differs for {label}: count={text.count(old)}")
    return text.replace(old, new, 1)


def probe_catalog() -> list[dict[str, Any]]:
    rows = [
        ("target_clk", f"{TARGET_INSTANCE}.clk", 1),
        ("target_rst_n", f"{TARGET_INSTANCE}.rst_n", 1),
        ("target_slice_rst", f"{TARGET_INSTANCE}.slice_rst", 1),
        ("queue_wr_en", f"{TARGET_INSTANCE}.buf_ag_idx_queue_wr_en", 1),
        ("queue_full", f"{TARGET_INSTANCE}.buf_ag_idx_queue_full", 1),
        ("all_idx_matched", f"{TARGET_INSTANCE}.buf_all_idx_matched", 1),
        ("same_bit_masked", f"{TARGET_INSTANCE}.buf_idx_same_bit_masked", 2),
        ("gotten_bit", f"{TARGET_INSTANCE}.buf_idx_gotten_bit", 2),
        ("bp_pre_mask", f"{TARGET_INSTANCE}.buf_idx_bp_pre_mask", 2),
        ("public_ack", f"{TARGET_INSTANCE}.mse_buf_queue_bp_pre", 2),
        ("inline_rhs", f"{QUERY_INSTANCE}.codex_inline_rhs", 2),
        ("public_xor_inline_rhs", f"{QUERY_INSTANCE}.codex_public_xor", 2),
        ("positive_ack_control", f"{QUERY_INSTANCE}.codex_positive_control", 2),
        (
            "deliberate_negative_ack_control",
            f"{QUERY_INSTANCE}.codex_negative_control",
            2,
        ),
    ]
    return [
        {"candidate_id": candidate, "hierarchical_path": path, "width": width}
        for candidate, path, width in rows
    ]


def catalog_sha(catalog: list[dict[str, Any]]) -> str:
    encoded = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def source_generation_report(package: Path) -> dict[str, Any]:
    catalog = probe_catalog()
    return {
        "schema": "node0004-portable-query-source-generation-report-v1",
        "package_id": INSTALL,
        "target_instance": TARGET_INSTANCE,
        "target_widths": {item["candidate_id"]: item["width"] for item in catalog},
        "probe_catalog": catalog,
        "probe_catalog_sha256": catalog_sha(catalog),
        "observer": {
            "member": "tb_probe/buffer_ack_portable_query_observer.svh",
            "bytes": (package / "tb_probe/buffer_ack_portable_query_observer.svh").stat().st_size,
            "sha256": sha256_file(package / "tb_probe/buffer_ack_portable_query_observer.svh"),
            "input_only": True,
            "dut_driver_count": 0,
        },
        "parser": {
            "member": "package_tools/node0004_portable_query_parser.py",
            "bytes": (package / "package_tools/node0004_portable_query_parser.py").stat().st_size,
            "sha256": sha256_file(package / "package_tools/node0004_portable_query_parser.py"),
        },
        "capture": {
            "timescale": "1ns/1ps",
            "time_tick": "1ps",
            "ordered_every_0_1_x_z_transition": True,
            "contiguous_sequence": True,
            "hard_byte_limit": None,
            "hard_event_limit": None,
            "sampling": False,
            "truncation": False,
        },
        "controls": {
            "positive": "inline RHS XOR independent identical recomputation = 2'b00",
            "deliberate_negative": "inline RHS XOR bit1-flipped recomputation = 2'b10",
        },
        "claim_boundary": (
            "Source generation and transport semantics only; no production simulation or RTL-defect claim."
        ),
    }


def portable_profile(source_report_sha: str) -> dict[str, Any]:
    catalog = probe_catalog()
    return {
        "schema": "server-waveform-portable-query-profile-v1",
        "rule_id": PORTABLE_RULE,
        "activation": "required_next_fresh",
        "activation_epoch": RULE_EPOCH,
        "raw_vpd": {
            "authoritative": True,
            "existing_dump_vcd_semantics": "VPD",
            "make_arguments": {"DUMP_VCD": "1", "DUMP_FSDB": "0", "TB_DUMP_FSDB": "0"},
            "hard_limit_bytes": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
        "portable_vcd": {
            "format": "VCD",
            "ucli_type": "VCD",
            "make_argument": {"DUMP_PORTABLE_VCD": "1"},
            "first_fresh_required": True,
            "source_bound_scope": {
                "top": "tb_NDP_Top_new_phy",
                "depth": 0,
                "source_receipt_sha256": source_report_sha,
            },
            "hard_limit_bytes": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
        },
        "signal_query": {
            "format": "REGISTERED_EVENT_ROWS",
            "custom_free_form_text": False,
            "hard_limit_bytes": None,
            "hard_limit_events": None,
            "sampling": False,
            "truncation": False,
            "ordered_every_transition": True,
        },
        "probe_catalog": catalog,
        "probe_catalog_sha256": catalog_sha(catalog),
        "failure_semantics": {
            "return_must_publish": True,
            "diagnostic_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "preserve": ["raw_vpd", "compile_core", "sim_core", "signal_core", "return_core"],
        },
        "claim_boundary": (
            "Serialized-Conv ACK portable waveform/query transport only; family classification remains conditional."
        ),
    }


def waveform_plan() -> dict[str, Any]:
    plan = json.loads(replace_identity(source_member(WAVE_PLAN)))
    plan["package_id"] = INSTALL
    roots = list(plan["dump"]["runtime_search_roots"])
    if "run/sim_results" not in roots:
        roots.insert(0, "run/sim_results")
    plan["dump"]["runtime_search_roots"] = roots
    plan["claim_boundary"] = (
        "Authoritative full tb_NDP_Top_new_phy depth-0 raw VPD discovery and unbounded return; "
        "the distinct VCD/query derivative cannot replace it."
    )
    return plan


def append_core_entry(request: dict[str, Any], archive: str, source: str, *, root: str = "attempt") -> None:
    if archive not in {item["archive"] for item in request["core_entries"]}:
        request["core_entries"].append(
            {"archive": archive, "required": False, "source": source, "source_root": root}
        )


def patched_request() -> dict[str, Any]:
    request = json.loads(replace_identity(source_member(POST_REQUEST)))
    request["package_id"] = INSTALL
    additions = [
        ("evidence/compiled_source/actual_vcs_argv.json", "evidence/compiled_source/actual_vcs_argv.json"),
        ("evidence/compiled_source/actual_top_filelist.f", "evidence/compiled_source/actual_top_filelist.f"),
        ("evidence/compiled_source/actual_target_source.sv", "evidence/compiled_source/actual_target_source.sv"),
        ("evidence/compiled_source/actual_parameter_header.svh", "evidence/compiled_source/actual_parameter_header.svh"),
        ("evidence/compiled_source/preprocessed_target.sv", "evidence/compiled_source/preprocessed_target.sv"),
        ("evidence/compiled_source/preprocessed_target_receipt.json", "evidence/compiled_source/preprocessed_target_receipt.json"),
        ("evidence/compiled_source/elaborated_ack_driver_set.json", "evidence/compiled_source/elaborated_ack_driver_set.json"),
        ("runs/c0/buffer_ack_phase_events.full.log", "c0/buffer_ack_phase_events.full.log"),
        ("evidence/buffer_ack_phase_raw_preservation.json", "evidence/buffer_ack_phase_raw_preservation.json"),
        ("waveforms/portable/wave.vcd", "run/sim_results/wave.vcd"),
        ("waveforms/portable/PORTABLE_RUNTIME_RECEIPT.json", "evidence/waveform/PORTABLE_RUNTIME_RECEIPT.json"),
        ("waveforms/portable/PORTABLE_RUNTIME_VALIDATION.json", "evidence/waveform/PORTABLE_RUNTIME_VALIDATION.json"),
        ("waveforms/portable/SIGNAL_QUERY_RECEIPT.json", "evidence/waveform/SIGNAL_QUERY_RECEIPT.json"),
        ("waveforms/portable/portable_query_source_generation_report.json", "evidence/waveform/portable_query_source_generation_report.json"),
        ("waveforms/portable/actual_sim_argv.json", "evidence/waveform/actual_sim_argv.json"),
        ("waveforms/portable/portable_return_allowlist.json", "evidence/waveform/portable_return_allowlist.json"),
        ("waveforms/portable/portable_runtime_request.json", "evidence/waveform/portable_runtime_request.json"),
        ("waveforms/portable/codex_wave_dump.tcl", "run/sim_results/codex_wave_dump.tcl"),
    ]
    for archive, source in additions:
        append_core_entry(request, archive, source)
    request["waveform_discovery"] = {
        "plan_member": WAVE_PLAN,
        "collector_member": "package_tools/server_waveform_mandatory_return.py",
        "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        "collect_all_matching": True,
        "required_when_simulation_started": True,
        "no_size_limit": True,
        "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json",
    }
    request["claim_boundary"] = (
        "Compile/sim/signal/core and authoritative VPD return remain independent. Portable VCD/query/source-identity "
        "failure is returned as DIAGNOSTIC_EVIDENCE_INCOMPLETE and cannot suppress the raw return."
    )
    return request


def patched_runner() -> str:
    runner = replace_identity(source_member("PREPARE_AND_RUN.sh")).decode("utf-8")
    runner = replace_once(
        runner,
        "waveform_receipt_rc=0\nruntime_dump_tcl=\n",
        "waveform_receipt_rc=0\nportable_receipt_rc=0\nsource_identity_rc=0\nphase_preserve_rc=0\nquery_receipt_rc=0\nruntime_dump_tcl=\nportable_attempt_root=\nportable_asset_root=\nactual_sim_argv_json=\n",
        "portable variables",
    )
    runner = replace_once(
        runner,
        'mkdir -p -- "$compile_root/sim_results" "$run_root/c0"\n',
        'mkdir -p -- "$compile_root/sim_results" "$run_root/c0" "$run_root/run/sim_results" "$evidence_root/compiled_source" "$evidence_root/waveform"\n'
        'portable_asset_root="$server_root"\n'
        'portable_attempt_root="install/codex_runs/$package_id/$attempt"\n'
        'cp -f -- "$package_root/diagnostics/portable_query_source_generation_report.json" "$evidence_root/waveform/portable_query_source_generation_report.json" || runner_fail 15 "cannot bind portable query source report"\n',
        "attempt evidence roots",
    )
    runner = replace_once(
        runner,
        "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 \"RUN_DIR=$compile_root\"",
        "DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 \"RUN_DIR=$compile_root\"",
        "compile make waveform args",
    )
    runner = replace_once(
        runner,
        "$package_root/tb_probe/source_bound_causal_observer.svh $package_root/tb_probe/buffer_ack_phase_observer.svh\"",
        "$package_root/tb_probe/source_bound_causal_observer.svh $package_root/tb_probe/buffer_ack_phase_observer.svh $package_root/tb_probe/buffer_ack_portable_query_observer.svh\"",
        "compile portable observer",
    )
    runner = replace_once(
        runner,
        '  "$package_root/tb_probe/buffer_ack_phase_observer.svh" \\\n  "$package_root/tb_probe/native_return_observer.svh" <<\'PY\'\n',
        '  "$package_root/tb_probe/buffer_ack_phase_observer.svh" \\\n  "$package_root/tb_probe/buffer_ack_portable_query_observer.svh" \\\n  "$package_root/tb_probe/native_return_observer.svh" <<\'PY\'\n',
        "bootstrap selected observer identity",
    )
    evidence_anchor = r'''evidence_rc=$?
publish_compile_evidence_to_attempt
[ "$evidence_rc" -eq 0 ] || runner_fail 14 "cannot derive bounded compile evidence from: $compile_full_log"
[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; bounded root cause: $compile_first_error_txt"
runtime_dump_tcl="$compile_root/sim_results/codex_wave_dump.tcl"
printf 'set CODEX_WAVE_PATH {%s}\n' "$compile_root/sim_results/wave.vpd" > "$runtime_dump_tcl" || runner_fail 15 "cannot bind runtime VPD path"
cat "$package_root/package_tools/dump_waveform.tcl" >> "$runtime_dump_tcl" || runner_fail 15 "cannot materialize plan-derived VPD control"
'''
    evidence_replacement = r'''evidence_rc=$?
[ "$evidence_rc" -eq 0 ] || runner_fail 14 "cannot derive bounded compile evidence from: $compile_full_log"
python3 "$package_root/package_tools/node0004_actual_compile_source_identity.py" \
  --server-root "$server_root" --package-root "$package_root" \
  --compile-log "$compile_full_log" --compile-exit "$compile_exit_txt" \
  --target-instance "''' + TARGET_INSTANCE + '''" \
  --output-dir "$evidence_root/compiled_source" --output "$compile_source_identity_json"
source_identity_rc=$?
publish_compile_evidence_to_attempt
[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; bounded root cause: $compile_first_error_txt"
runtime_dump_tcl="$run_root/run/sim_results/codex_wave_dump.tcl"
python3 "$package_root/package_tools/server_waveform_portable_query.py" render-dump-tcl \
  --profile "$package_root/contracts/server_waveform_portable_query_profile.json" \
  --attempt-root "$portable_attempt_root" --sim-time 1000000000000ns \
  --capture-mode DIRECT_VCD_AND_QUERY --output "$runtime_dump_tcl" || runner_fail 15 "cannot materialize VPD+portable-VCD dump Tcl"
'''
    runner = replace_once(runner, evidence_anchor, evidence_replacement, "post-compile source/dump")
    runner = runner.replace(
        "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 $simv",
        "DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 $simv",
    )
    runner = runner.replace(
        "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout",
        "DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout",
    )
    runner = runner.replace(
        "+CODEX_CAUSAL_OBSERVER +RETURN_OBS_BUF_ACK_PHASE_LIMIT=128",
        "+CODEX_CAUSAL_OBSERVER +CODEX_PORTABLE_ACK_QUERY +RETURN_OBS_BUF_ACK_PHASE_LIMIT=128",
    )
    argv_anchor = '  > "$run_root/c0/simulator_argv.txt"\nDUMP_VCD=1 DUMP_PORTABLE_VCD=1'
    argv_replacement = r'''  > "$run_root/c0/simulator_argv.txt"
actual_sim_argv_json="$evidence_root/waveform/actual_sim_argv.json"
python3 - "$run_root/c0/simulator_argv.txt" "$actual_sim_argv_json" <<'PY'
import json, pathlib, shlex, sys
source, target = map(pathlib.Path, sys.argv[1:])
target.write_text(json.dumps(shlex.split(source.read_text(encoding="utf-8")), indent=2) + "\n", encoding="utf-8")
PY
[ "$?" -eq 0 ] || runner_fail 15 "cannot persist actual simulator argv"
DUMP_VCD=1 DUMP_PORTABLE_VCD=1'''
    runner = replace_once(runner, argv_anchor, argv_replacement, "actual sim argv JSON")

    final_anchor = '''  waveform_receipt_rc=$?
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL="$natural"
'''
    final_replacement = r'''  waveform_receipt_rc=$?
  python3 "$package_root/package_tools/node0004_phase_raw_preserver.py" \
    --log "$run_root/c0/sim.log" --events "$run_root/c0/buffer_ack_phase_events.full.log" \
    --receipt "$evidence_root/buffer_ack_phase_raw_preservation.json" --expected-events 65
  phase_preserve_rc=$?
  if [ "$sim_started" = true ]; then
    python3 "$package_root/package_tools/node0004_portable_query_parser.py" \
      --log "$run_root/c0/sim.log" --profile "$package_root/contracts/server_waveform_portable_query_profile.json" \
      --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" \
      --exit-kind "$waveform_exit_kind" \
      --source-generation-report "$evidence_root/waveform/portable_query_source_generation_report.json" \
      --source-generation-report-path "$portable_attempt_root/evidence/waveform/portable_query_source_generation_report.json" \
      --output "$evidence_root/waveform/SIGNAL_QUERY_RECEIPT.json"
    query_receipt_rc=$?
    python3 - "$server_root" "$portable_attempt_root" "$attempt" "$package_id" "$return_tag" "$waveform_exit_kind" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1]); attempt_root, attempt_id, package_id, execution_id, exit_kind = sys.argv[2:]
evidence = root / attempt_root / "evidence/waveform"
raw_path = evidence / "WAVEFORM_RUNTIME_RECEIPT.json"
raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.is_file() else {}
allow = [
  f"{attempt_root}/run/sim_results/codex_wave_dump.tcl",
  f"{attempt_root}/run/sim_results/wave.vcd",
  f"{attempt_root}/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
  f"{attempt_root}/evidence/waveform/SIGNAL_QUERY_RECEIPT.json",
  f"{attempt_root}/evidence/waveform/portable_query_source_generation_report.json",
  f"{attempt_root}/evidence/waveform/actual_sim_argv.json",
]
for wave in raw.get("waveforms", []):
  source = wave.get("source_path")
  if isinstance(source, str): allow.append(f"{attempt_root}/{source}")
allow = list(dict.fromkeys(allow))
(evidence / "portable_return_allowlist.json").write_text(json.dumps(allow, indent=2) + "\n", encoding="utf-8")
request = {
  "package_id": package_id, "execution_id": execution_id, "attempt_id": attempt_id,
  "attempt_root": attempt_root, "first_fresh_for_profile": True,
  "capture_mode": "DIRECT_VCD_AND_QUERY", "simulation_started": True, "exit_kind": exit_kind,
  "actual_sim_argv_path": f"{attempt_root}/evidence/waveform/actual_sim_argv.json",
  "dump_tcl_path": f"{attempt_root}/run/sim_results/codex_wave_dump.tcl",
  "raw_vpd_runtime_receipt_path": f"{attempt_root}/evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
  "portable_vcd_path": f"{attempt_root}/run/sim_results/wave.vcd",
  "signal_query_receipt_path": f"{attempt_root}/evidence/waveform/SIGNAL_QUERY_RECEIPT.json",
  "return_allowlist_path": f"{attempt_root}/evidence/waveform/portable_return_allowlist.json",
}
(evidence / "portable_runtime_request.json").write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    python3 "$package_root/package_tools/server_waveform_portable_query.py" build-runtime-receipt \
      --profile "$package_root/contracts/server_waveform_portable_query_profile.json" \
      --request "$evidence_root/waveform/portable_runtime_request.json" --asset-root "$portable_asset_root" \
      --output "$evidence_root/waveform/PORTABLE_RUNTIME_RECEIPT.json"
    portable_receipt_rc=$?
    python3 "$package_root/package_tools/server_waveform_portable_query.py" validate-runtime-receipt \
      --profile "$package_root/contracts/server_waveform_portable_query_profile.json" \
      --receipt "$evidence_root/waveform/PORTABLE_RUNTIME_RECEIPT.json" --asset-root "$portable_asset_root" \
      --output "$evidence_root/waveform/PORTABLE_RUNTIME_VALIDATION.json"
  else
    printf '%s\n' '{"schema":"server-waveform-portable-not-applicable-v1","diagnostic_status":"NOT_APPLICABLE_SIMULATION_NOT_STARTED","return_must_publish":true}' > "$evidence_root/waveform/PORTABLE_RUNTIME_VALIDATION.json"
  fi
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL="$natural"
'''
    runner = replace_once(runner, final_anchor, final_replacement, "portable finalization")
    required = (
        "DUMP_VCD=1",
        "DUMP_PORTABLE_VCD=1",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        "server_waveform_portable_query.py\" render-dump-tcl",
        "PORTABLE_RUNTIME_RECEIPT.json",
        "SIGNAL_QUERY_RECEIPT.json",
        "node0004_actual_compile_source_identity.py",
        "buffer_ack_phase_events.full.log",
        "+CODEX_PORTABLE_ACK_QUERY",
    )
    if not all(token in runner for token in required) or "DUMP_VCD=0" in runner:
        raise BuildError("fresh runner evidence-hardening tokens differ")
    return runner


def runner_contract(runner: str, *, final_zip: bool) -> dict[str, Any]:
    contract = json.loads(replace_identity(source_member(RUNNER_CONTRACT)))
    contract["package_id"] = INSTALL
    contract["runner_path"] = f"{INSTALL}/PREPARE_AND_RUN.sh" if final_zip else "PREPARE_AND_RUN.sh"
    contract["runner_sha256"] = (
        runner if re.fullmatch(r"[0-9a-f]{64}", runner) else sha256_bytes(runner.encode("utf-8"))
    )
    variables = list(contract["package_owned_variables"])
    for name in (
        "portable_receipt_rc",
        "source_identity_rc",
        "phase_preserve_rc",
        "query_receipt_rc",
        "portable_attempt_root",
        "portable_asset_root",
        "actual_sim_argv_json",
    ):
        if name not in variables:
            variables.append(name)
    contract["package_owned_variables"] = variables
    for token in (
        "DUMP_PORTABLE_VCD=1",
        "server_waveform_portable_query.py",
        "PORTABLE_RUNTIME_RECEIPT.json",
        "SIGNAL_QUERY_RECEIPT.json",
        "node0004_actual_compile_source_identity.py",
        "buffer_ack_phase_events.full.log",
    ):
        if token not in contract["return_allowlist_tokens"]:
            contract["return_allowlist_tokens"].append(token)
    return contract


ALLOWED_CHANGED_EXISTING = {
    "PREPARE_AND_RUN.sh",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    POST_REQUEST,
    POST_CONTRACT,
    RUNNER_CONTRACT,
    WAVE_PLAN,
    "contracts/waveform_policy.json",
    "diagnostics/source_bound_probe_binding.json",
    "diagnostics/source_bound_observer_generation.json",
    "diagnostics/source_bound_observer_generation_report.json",
    "package_tools/server_post_sim_return.py",
    "package_manifest.json",
    "README.md",
    "provenance/server_package_build_profile.json",
}

ADDED_MEMBERS = {
    PORTABLE_PROFILE,
    PORTABLE_SOURCE_REPORT,
    "tb_probe/buffer_ack_portable_query_observer.svh",
    "package_tools/node0004_portable_query_parser.py",
    "package_tools/node0004_phase_raw_preserver.py",
    "package_tools/node0004_actual_compile_source_identity.py",
    "package_tools/server_waveform_portable_query.py",
    "tools/__init__.py",
    "tools/server_waveform_local_analysis.py",
    "provenance/v87b_to_v88b_evidence_hardening.json",
}


def safe_extract(destination: Path) -> Path:
    package = destination / INSTALL
    package.mkdir(parents=True, exist_ok=False)
    for name, payload in SOURCE_MEMBERS.items():
        target = package / Path(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(replace_identity(payload))
    return package


def package_records(package: Path) -> dict[str, str]:
    manifest = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): sha256_file(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def current_receipts() -> dict[str, str]:
    paths = {
        "agent_sha256": ROOT / ".agents/agent.md",
        "plan_sha256": ROOT / ".agents/plan.md",
        "generation_index_sha256": ROOT / ".agents/rules/生成前必读索引.md",
        "server_package_rule_sha256": ROOT / ".agents/rules/服务器测试包生成规则.md",
        "active_rule_registry_sha256": ROOT / "contracts/active_rule_registry_v1.json",
        "owner_registry_sha256": ROOT / "contracts/current_session_owner_registry_v1.json",
        "build_gate_registry_sha256": ROOT / "contracts/server_package_build_gate_registry_v1.json",
        "mandatory_waveform_dispatch_sha256": ROOT / "contracts/server_waveform_mandatory_return_dispatch_v2.json",
        "portable_dispatch_sha256": ROOT / "contracts/server_waveform_portable_query_profile_v1.json",
        "portable_tool_sha256": PORTABLE_TOOL,
        "post_sim_dispatch_sha256": ROOT / "contracts/server_post_sim_return_next_fresh_dispatch_v1.json",
        "post_sim_helper_sha256": POST_SIM_TOOL,
    }
    return {key: sha256_file(path) for key, path in paths.items()}


def configure_package(package: Path, runner: str, cheap: dict[str, Any]) -> None:
    (package / "PREPARE_AND_RUN.sh").write_text(runner, encoding="utf-8", newline="\n")
    shutil.copy2(POST_SIM_TOOL, package / "package_tools/server_post_sim_return.py")
    shutil.copy2(PORTABLE_TOOL, package / "package_tools/server_waveform_portable_query.py")
    (package / "tools").mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOCAL_ANALYSIS_TOOL, package / "tools/server_waveform_local_analysis.py")
    (package / "tools/__init__.py").write_text("\n", encoding="utf-8")
    shutil.copy2(SOURCE_ID_TOOL, package / "package_tools/node0004_actual_compile_source_identity.py")
    shutil.copy2(QUERY_PARSER, package / "package_tools/node0004_portable_query_parser.py")
    shutil.copy2(PHASE_PRESERVER, package / "package_tools/node0004_phase_raw_preserver.py")
    shutil.copy2(QUERY_OBSERVER, package / "tb_probe/buffer_ack_portable_query_observer.svh")
    shutil.copy2(cheap["generated"]["hdl"], package / "tb_probe/source_bound_causal_observer.svh")
    shutil.copy2(cheap["generated"]["parser"], package / "package_tools/source_bound_causal_parser.py")
    shutil.copy2(cheap["generated"]["binding"], package / "diagnostics/source_bound_probe_binding.json")
    shutil.copy2(cheap["generation_report"], package / "diagnostics/source_bound_observer_generation_report.json")
    shutil.copy2(cheap["generation_cheap"], package / "diagnostics/source_bound_observer_generation.json")

    write_json(package / WAVE_PLAN, waveform_plan())
    source_report_path = package / PORTABLE_SOURCE_REPORT
    write_json(source_report_path, source_generation_report(package))
    profile_path = package / PORTABLE_PROFILE
    write_json(profile_path, portable_profile(sha256_file(source_report_path)))
    validation = OUT / "portable_profile_staging_validation.json"
    run(
        [
            sys.executable,
            str(PORTABLE_TOOL),
            "validate-profile",
            "--profile",
            str(profile_path),
            "--output",
            str(validation),
        ]
    )
    if load_json(validation).get("pass") is not True:
        raise BuildError("portable profile staging validation failed")

    request_path = package / POST_REQUEST
    write_json(request_path, patched_request())
    post_contract = json.loads(replace_identity(source_member(POST_CONTRACT)))
    post_contract["package_id"] = INSTALL
    post_contract["helper_sha256"] = sha256_file(POST_SIM_TOOL)
    post_contract["request_sha256"] = sha256_file(request_path)
    post_contract["claim_boundary"] = (
        "Independent core/raw-VPD publication plus optional unbounded portable VCD/query/source identity."
    )
    write_json(package / POST_CONTRACT, post_contract)
    write_json(package / RUNNER_CONTRACT, runner_contract(runner, final_zip=True))
    write_json(
        package / "contracts/waveform_policy.json",
        {
            "schema": "server-waveform-policy-v3",
            "package_id": INSTALL,
            "rule_ids": [WAVE_RULE, PORTABLE_RULE],
            "activation_epoch": RULE_EPOCH,
            "raw_vpd": {"DUMP_VCD": 1, "authoritative": True, "unbounded": True},
            "portable_vcd": {"DUMP_PORTABLE_VCD": 1, "first_fresh": True, "unbounded": True},
            "DUMP_FSDB": 0,
            "TB_DUMP_FSDB": 0,
            "scope": "tb_NDP_Top_new_phy",
            "depth": 0,
            "failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "return_must_publish": True,
        },
    )

    shutil.copy2(cheap["profile"], package / "provenance/server_package_build_profile.json")
    write_json(
        package / "provenance/v87b_to_v88b_evidence_hardening.json",
        {
            "schema": "conv-node0004-v87b-to-v88b-evidence-hardening-v1",
            "source_package": {**receipt(SOURCE_ZIP), "package_id": SOURCE},
            "activation_epoch": RULE_EPOCH,
            "rule_ids": [WAVE_RULE, PORTABLE_RULE],
            "previous_progress": (
                "v87b passed production compile, started simulation and returned authoritative raw VPD; "
                "its exact phase observer strongly rebutted ordinary TB/settling/XZ explanations, but raw rows, "
                "slice_rst, portable decoding and actual compiled-source identity were absent."
            ),
            "current_purpose": (
                "Close observer/source-identity alternatives with same-attempt raw VPD plus direct VCD/query, "
                "all 65 phase rows, reset context, controls and actual compile source/preprocess/driver evidence."
            ),
            "classification": "EVIDENCE_INCOMPLETE_CONDITIONAL_RTL_OR_SOURCE_IDENTITY",
            "CONFIG_WORKAROUND": "NONE",
            "changed_surfaces": ["fresh identity", "portable waveform/query", "runtime return", "source identity evidence"],
            "frozen": ["config", "numeric", "workload", "golden", "functional RTL", "v87b target diagnostic"],
            "server_action": False,
        },
    )
    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## v88b portable ACK/source-identity evidence hardening\n\n"
        + "This fresh identity preserves every v87b workload/config/numeric/golden/functional-RTL byte and the "
        + "existing target phase observer. It retains authoritative full-hierarchy VPD and adds direct unbounded "
        + "VCD plus a registered exact ACK event receipt, raw 65-row preservation, clk/rst_n/slice_rst, positive/"
        + "deliberate-negative controls, and actual production compile source/filelist/preprocess/driver receipts. "
        + "Portable evidence failure cannot suppress the raw/core return and is classified DIAGNOSTIC_EVIDENCE_INCOMPLETE.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = load_json(manifest_path)
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_READY_NOT_RUN_PENDING_EXACT_FINAL_ZIP_GATES"
    manifest["active_receipts"] = current_receipts()
    manifest["rule_change_epoch"] = RULE_EPOCH
    manifest["first_fresh_after_change"] = True
    manifest["upload_hold_until"] = "EXACT_FINAL_ZIP_PORTABLE_QUERY_SOURCE_BOUND_POST_SIM_RUNNER_SIX_EXIT_FIRST_FRESH_PASS"
    manifest["portable_waveform_gate"] = {
        "rule_id": PORTABLE_RULE,
        "raw_vpd_authoritative": True,
        "DUMP_VCD": 1,
        "DUMP_PORTABLE_VCD": 1,
        "DUMP_FSDB": 0,
        "TB_DUMP_FSDB": 0,
        "scope": "tb_NDP_Top_new_phy",
        "depth": 0,
        "direct_vcd_unbounded": True,
        "query_unbounded": True,
        "query_catalog_sha256": catalog_sha(probe_catalog()),
        "failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
    }
    manifest["v88b_evidence_successor"] = {
        "source_package": SOURCE,
        "v87b_target_phase_observer_exact_bytes_preserved": True,
        "functional_rtl_modified": False,
        "config_numeric_workload_golden_frozen": True,
        "CONFIG_WORKAROUND": "NONE",
        "classification": "CONDITIONAL_RTL_OR_SOURCE_IDENTITY",
        "server_action": False,
    }
    manifest["files"] = {}
    write_json(manifest_path, manifest)
    legacy.base.INSTALL = INSTALL
    legacy.base.refresh_path_budget(package)
    manifest = load_json(manifest_path)
    observer = package / "tb_probe/native_return_observer.svh"
    binding = manifest.get("observer_binding_four_way", {})
    if not isinstance(binding, dict) or not isinstance(binding.get("source"), dict):
        raise BuildError("observer binding is absent")
    binding["source"] = {
        "path": "tb_probe/native_return_observer.svh",
        "sha256": sha256_file(observer),
        "size_bytes": observer.stat().st_size,
    }
    manifest["files"] = package_records(package)
    write_json(manifest_path, manifest)


def verify_frozen_surfaces(package: Path) -> dict[str, Any]:
    errors: list[str] = []
    exact = 0
    identity_only: list[str] = []
    for name, old in SOURCE_MEMBERS.items():
        target = package / Path(*PurePosixPath(name).parts)
        if not target.is_file():
            errors.append(f"source member removed: {name}")
            continue
        if name in ALLOWED_CHANGED_EXISTING:
            continue
        new = target.read_bytes()
        if new == old:
            exact += 1
        elif new.replace(INSTALL.encode(), SOURCE.encode()) == old:
            identity_only.append(name)
        elif name == "tb_probe/source_bound_causal_observer.svh" and re.sub(
            rb"(?m)^// plan_semantic_sha256=[0-9a-f]{64}$",
            b"// plan_semantic_sha256=<FRESH_PLAN_IDENTITY>",
            new.replace(INSTALL.encode(), SOURCE.encode()),
        ) == re.sub(
            rb"(?m)^// plan_semantic_sha256=[0-9a-f]{64}$",
            b"// plan_semantic_sha256=<FRESH_PLAN_IDENTITY>",
            old,
        ):
            identity_only.append(name)
        else:
            errors.append(f"frozen member changed beyond identity: {name}")
    actual = {path.relative_to(package).as_posix() for path in package.rglob("*") if path.is_file()}
    for name in sorted(actual - set(SOURCE_MEMBERS) - ADDED_MEMBERS):
        errors.append(f"unexpected added member: {name}")
    checks = {
        "tested_v87b_source_identity": sha256_file(SOURCE_ZIP) == SOURCE_SHA256,
        "workload_config_numeric_golden_exact_or_identity_only": not any(
            error.startswith("frozen member changed beyond identity: workload/") for error in errors
        ),
        "functional_rtl_unchanged": True,
        "native_observer_exact_v87b": (package / "tb_probe/native_return_observer.svh").read_bytes()
        == source_member("tb_probe/native_return_observer.svh"),
        "phase_observer_exact_v87b": (package / "tb_probe/buffer_ack_phase_observer.svh").read_bytes()
        == source_member("tb_probe/buffer_ack_phase_observer.svh"),
        "new_observer_input_only": False,
    }
    # Keep this syntactic check separate from functional simulation claims.
    query_text = (package / "tb_probe/buffer_ack_portable_query_observer.svh").read_text(encoding="utf-8")
    checks["new_observer_input_only"] = not re.search(
        r"(?m)^\s*(?:(?:assign|force)\s+)?(?:mse_buf_queue_bp_pre|buf_idx_[A-Za-z0-9_]*|buf_ag_idx_queue_[A-Za-z0-9_]*)\s*(?:\[.*?\])?\s*(?:=|<=)",
        query_text,
    )
    errors.extend(name for name, passed in checks.items() if passed is not True)
    return {
        "schema": "conv-node0004-v88b-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "exact_member_count": exact,
        "identity_only_members": identity_only,
        "allowed_changed_existing": sorted(ALLOWED_CHANGED_EXISTING),
        "added_evidence_members": sorted(ADDED_MEMBERS),
        "claim_boundary": (
            "Only identity and enumerated portable/query/source-evidence/runtime-return surfaces may differ; "
            "functional RTL and the v87b target diagnostic are frozen."
        ),
    }


def prepare_cheap_aggregate(runner: str) -> dict[str, Any]:
    # The shared aggregate's historical storage cheap-check expects its source
    # ZIP beside a pending-like exact-name entry.  Use an output-local hard copy
    # of the tested immutable source; canonical provenance remains SOURCE_ZIP.
    shadow = OUT / "cheap_source_shadow" / f"{SOURCE}.zip"
    shadow.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_ZIP, shadow)
    base = legacy.base
    base.SOURCE = SOURCE
    base.INSTALL = INSTALL
    base.SOURCE_ZIP = shadow
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.RULE_EPOCH = RULE_EPOCH
    base.OUT = OUT
    base.EXTRA_SURFACE_INPUTS = [
        (SOURCE_ZIP, "package_identity"),
        (PORTABLE_TOOL, "waveform"),
        (QUERY_OBSERVER, "package_local_hdl"),
        (QUERY_PARSER, "parser"),
        (SOURCE_ID_TOOL, "return_collector"),
        (PHASE_PRESERVER, "return_collector"),
        (POST_SIM_TOOL, "return_collector"),
    ]
    base.EXTRA_CHANGED_SURFACES = ["waveform", "package_local_hdl", "parser"]
    base.patched_request = patched_request
    base.patched_runner = patched_runner
    base.runner_contract = runner_contract
    cheap = base.prepare_cheap_aggregate(OUT, runner)
    profile = load_json(cheap["profile"])
    if profile.get("contract_valid") is not True:
        raise BuildError("shared cheap aggregate did not pass")
    return cheap


def deterministic_zip(package: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise BuildError(f"refusing to overwrite final ZIP: {target}")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            name = path.relative_to(package).as_posix()
            info = zipfile.ZipInfo(f"{INSTALL}/{name}", (1980, 1, 1, 0, 0, 0))
            mode = 0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise BuildError("deterministic ZIP CRC failure")


def main() -> int:
    if OUT.exists():
        raise BuildError(f"output root already exists: {OUT}")
    OUT.mkdir(parents=True)
    runner = patched_runner()
    cheap = prepare_cheap_aggregate(runner)
    package = safe_extract(BUILD)
    configure_package(package, runner, cheap)
    frozen = verify_frozen_surfaces(package)
    write_json(OUT / "staging_frozen_surface_validation.json", frozen)
    if frozen["pass"] is not True:
        raise BuildError(f"staging frozen surface gate failed: {frozen['errors']}")
    with tempfile.TemporaryDirectory(prefix="node0004-v88b-repeat-") as raw:
        repeat = safe_extract(Path(raw))
        configure_package(repeat, runner, cheap)
        if package_records(package) != package_records(repeat):
            raise BuildError("deterministic directory rebuild differs")
    zip_path = BUILD / f"{INSTALL}.zip"
    deterministic_zip(package, zip_path)
    sidecar = BUILD / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{sha256_file(zip_path)}  {zip_path.name}\n", encoding="ascii", newline="\n")
    write_json(
        BUILD / f"{INSTALL}.build.json",
        {
            "schema": "conv-node0004-v88b-build-v1",
            "status": "PACKAGE_BUILT_PENDING_EXACT_FINAL_ZIP_GATES",
            "package_id": INSTALL,
            "source": receipt(SOURCE_ZIP),
            "zip": receipt(zip_path),
            "sidecar": receipt(sidecar),
            "shared_aggregate_profile": receipt(cheap["profile"]),
            "deterministic_directory_rebuild_equal": True,
            "server_action": False,
        },
    )
    print(json.dumps({"package_id": INSTALL, "zip": relative(zip_path), "server_action": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
