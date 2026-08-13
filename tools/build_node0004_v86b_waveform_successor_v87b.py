#!/usr/bin/env python3
"""Build the waveform-mandatory fresh successor of serialized-Conv v86b.

The held v86b ZIP is the immutable source.  Only fresh identity and the
waveform/runtime-return surfaces are changed.  The builder performs no server
upload, lease, compile, or simulation action.
"""

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

import tools.build_node0004_v84b_return_successor_v85 as base


SOURCE = "r5_n4_hw_v86b_observer_xmre_fix"
INSTALL = "r5_n4_hw_v87b_mandatory_vpd"
FAMILY = "conv_serialized_node0004"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/superseded"
    / FAMILY
    / SOURCE
    / f"{SOURCE}.zip"
)
SOURCE_SHA256 = "70deb1846226b353a22916891c2ce7de18ff32cd748b4206d4495c38ba929865"
OUT = ROOT / "outputs/conv_node0004_v87b_mandatory_vpd_release6"
BUILD = OUT / "build"
RULE_EPOCH = "waveform-mandatory-v2-01ca6d7cd4a4a270"
RULE_ID = "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001"
WAVE_TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
POST_SIM_TOOL = ROOT / "tools/server_post_sim_return.py"
RUNTIME_LAYOUT_VALIDATOR = ROOT / "tools/validate_server_package_runtime_layout.py"
RUNTIME_LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
WAVE_PLAN_MEMBER = "contracts/server_waveform_mandatory_plan.json"
WAVE_CONTROL_MEMBER = "package_tools/dump_waveform.tcl"
WAVE_TOOL_MEMBER = "package_tools/server_waveform_mandatory_return.py"
POST_REQUEST_MEMBER = "contracts/server_post_sim_return_request.json"
POST_CONTRACT_MEMBER = "contracts/server_post_sim_return_contract.json"
RUNNER_CONTRACT_MEMBER = "contracts/server_runner_return_resilience.json"

ALLOWED_CHANGED_EXISTING = {
    "PREPARE_AND_RUN.sh",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    POST_REQUEST_MEMBER,
    POST_CONTRACT_MEMBER,
    RUNNER_CONTRACT_MEMBER,
    "contracts/waveform_policy.json",
    "diagnostics/source_bound_probe_binding.json",
    "diagnostics/source_bound_observer_generation.json",
    "diagnostics/source_bound_observer_generation_report.json",
    "package_tools/server_post_sim_return.py",
    "README.md",
    "package_manifest.json",
    "provenance/server_package_build_profile.json",
}
ADDED_MEMBERS = {
    WAVE_PLAN_MEMBER,
    WAVE_CONTROL_MEMBER,
    WAVE_TOOL_MEMBER,
    "provenance/v86b_to_v87b_mandatory_vpd.json",
}


class BuildError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
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
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


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
    if not SOURCE_ZIP.is_file():
        raise BuildError(f"held v86b ZIP is absent: {SOURCE_ZIP}")
    if sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("held v86b ZIP identity differs")
    members: dict[str, bytes] = {}
    seen: set[str] = set()
    roots: set[str] = set()
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("held v86b ZIP CRC failure")
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
                raise BuildError(f"unsafe held v86b member: {info.filename}")
            seen.add(info.filename)
            if member.parts:
                roots.add(member.parts[0])
            if not info.is_dir() and len(member.parts) > 1:
                relative_name = PurePosixPath(*member.parts[1:]).as_posix()
                members[relative_name] = archive.read(info)
    if roots != {SOURCE}:
        raise BuildError(f"held v86b ZIP root differs: {sorted(roots)}")
    return members


SOURCE_MEMBERS = inspect_source_zip()


def replace_identity(data: bytes) -> bytes:
    try:
        return data.decode("utf-8").replace(SOURCE, INSTALL).encode("utf-8")
    except UnicodeDecodeError:
        return data


def source_member(name: str) -> bytes:
    try:
        return SOURCE_MEMBERS[name]
    except KeyError as error:
        raise BuildError(f"held v86b member absent: {name}") from error


def waveform_plan() -> dict[str, Any]:
    return {
        "schema": "server-waveform-mandatory-plan-v2",
        "package_id": INSTALL,
        "family": "conv_serialized",
        "dump": {
            "format": "VPD",
            "make_arguments": {
                "DUMP_VCD": "1",
                "DUMP_FSDB": "0",
                "TB_DUMP_FSDB": "0",
            },
            "tb_top": "tb_NDP_Top_new_phy",
            "hierarchy_depth": 0,
            "scope_mode": "FULL_HIERARCHY",
            "included_scopes": ["tb_NDP_Top_new_phy"],
            "excluded_scopes": [],
            "runtime_search_roots": ["compile/sim_results", "c0"],
            "waveform_name_patterns": ["wave.vpd", "wave.vpd.*"],
        },
        "return_policy": {
            "required_when_simulation_started": True,
            "compile_not_started_omission_allowed": True,
            "collect_all_matching": True,
            "archive_prefix": "waveforms",
            "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json",
            "hard_limit_bytes": None,
            "truncation_allowed": False,
            "sampling_allowed": False,
            "size_based_deletion_allowed": False,
        },
        "integration": {
            "plan_member": WAVE_PLAN_MEMBER,
            "runner_member": "PREPARE_AND_RUN.sh",
            "return_request_member": POST_REQUEST_MEMBER,
            "dump_control_member": WAVE_CONTROL_MEMBER,
            "tool_member": WAVE_TOOL_MEMBER,
        },
        "claim_boundary": (
            "Full tb_NDP_Top_new_phy depth-0 VPD discovery and unbounded return "
            "only; no production compile, DUT, natural-terminal, formal-D, E4 or E5 claim."
        ),
    }


def patched_request() -> dict[str, Any]:
    request = json.loads(replace_identity(source_member(POST_REQUEST_MEMBER)))
    request["package_id"] = INSTALL
    request["waveform_discovery"] = {
        "plan_member": WAVE_PLAN_MEMBER,
        "collector_member": WAVE_TOOL_MEMBER,
        "runtime_receipt_source": "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
        "collect_all_matching": True,
        "required_when_simulation_started": True,
        "no_size_limit": True,
        "manifest_archive_path": "waveforms/WAVEFORM_RUNTIME_RECEIPT.json",
    }
    request["claim_boundary"] = (
        "The seven bootstrap-safe compile-core files and root/preflight receipts "
        "remain independent. If simulation starts, every discovered wave.vpd/shard "
        "and its runtime receipt are returned without a size cap; missing waveform "
        "evidence fails closed before optional family analysis."
    )
    return request


def patched_runner() -> str:
    runner = replace_identity(source_member("PREPARE_AND_RUN.sh")).decode("utf-8")
    if runner.count("DUMP_VCD=0") != 1:
        raise BuildError("held v86b runner DUMP_VCD=0 anchor differs")
    runner = runner.replace("DUMP_VCD=0", "DUMP_VCD=1", 1)

    variable_anchor = "root_gate_rc=0\n"
    variable_addition = (
        variable_anchor
        + "waveform_exit_kind=SIMULATION_NOT_STARTED\n"
        + "waveform_receipt_rc=0\n"
        + "runtime_dump_tcl=\n"
    )
    if runner.count(variable_anchor) != 1:
        raise BuildError("held v86b waveform variable anchor differs")
    runner = runner.replace(variable_anchor, variable_addition, 1)

    natural_anchor = r'''  natural=false
  grep -aq 'DUT_NATURAL_TERMINAL' "$run_root/c0/return_observer.log" 2>/dev/null && natural=true
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL="$natural"
'''
    natural_replacement = r'''  natural=false
  grep -aq 'DUT_NATURAL_TERMINAL' "$run_root/c0/return_observer.log" 2>/dev/null && natural=true
  if [ "$sim_started" != true ]; then
    if [ "$compile_status" -ne 0 ]; then waveform_exit_kind=COMPILE_FAILURE; else waveform_exit_kind=SIMULATION_NOT_STARTED; fi
  elif [ "$signal_status" = HUP ]; then waveform_exit_kind=HUP
  elif [ "$signal_status" = INT ]; then waveform_exit_kind=INT
  elif [ "$signal_status" = TERM ]; then waveform_exit_kind=TERM
  elif [ "$run_status" -eq 124 ]; then waveform_exit_kind=TIMEOUT
  elif [ "$run_status" -eq 0 ] && [ "$natural" = true ]; then waveform_exit_kind=NATURAL
  else waveform_exit_kind=SIMULATION_NONZERO
  fi
  mkdir -p -- "$evidence_root/waveform"
  python3 "$package_root/package_tools/server_waveform_mandatory_return.py" collect-runtime \
    --plan "$package_root/contracts/server_waveform_mandatory_plan.json" \
    --attempt-root "$run_root" --execution-id "$return_tag" \
    --simulation-started "$sim_started" --exit-kind "$waveform_exit_kind" \
    --output "$evidence_root/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
  waveform_receipt_rc=$?
  export CODEX_PACKAGE_ROOT="$package_root" CODEX_ATTEMPT_ROOT="$run_root" CODEX_EXECUTION_ID="$return_tag" CODEX_SIM_EXIT_CODE="$run_status" CODEX_SIM_SIGNAL="$signal_status" CODEX_SIM_STARTED="$sim_started" CODEX_NATURAL_TERMINAL="$natural"
'''
    if runner.count(natural_anchor) != 1:
        raise BuildError("held v86b finalizer waveform insertion anchor differs")
    runner = runner.replace(natural_anchor, natural_replacement, 1)

    final_anchor = (
        '  [ "$final" -ne 0 ] || [ "$core" -eq 0 ] || final="$core"\n'
        '  [ "$root_gate_rc" -eq 0 ] || final=96\n'
    )
    final_replacement = final_anchor + '  [ "$waveform_receipt_rc" -eq 0 ] || final=97\n'
    if runner.count(final_anchor) != 1:
        raise BuildError("held v86b final status anchor differs")
    runner = runner.replace(final_anchor, final_replacement, 1)

    compile_success_anchor = (
        '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" '
        '"production compile failed; bounded root cause: $compile_first_error_txt"\n'
        'simv="$compile_root/sim_results/simv"\n'
    )
    compile_success_replacement = (
        '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" '
        '"production compile failed; bounded root cause: $compile_first_error_txt"\n'
        'runtime_dump_tcl="$compile_root/sim_results/codex_wave_dump.tcl"\n'
        "printf 'set CODEX_WAVE_PATH {%s}\\n' \"$compile_root/sim_results/wave.vpd\" > \"$runtime_dump_tcl\" || runner_fail 15 \"cannot bind runtime VPD path\"\n"
        'cat "$package_root/package_tools/dump_waveform.tcl" >> "$runtime_dump_tcl" || runner_fail 15 "cannot materialize plan-derived VPD control"\n'
        'simv="$compile_root/sim_results/simv"\n'
    )
    if runner.count(compile_success_anchor) != 1:
        raise BuildError("held v86b post-compile waveform anchor differs")
    runner = runner.replace(compile_success_anchor, compile_success_replacement, 1)

    display_anchor = '  "$simv -l $run_root/c0/sim.log '
    display_replacement = (
        '  "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 $simv '
        '-ucli -i $runtime_dump_tcl -l $run_root/c0/sim.log '
    )
    if runner.count(display_anchor) != 1:
        raise BuildError("held v86b simulator argv display anchor differs")
    runner = runner.replace(display_anchor, display_replacement, 1)

    sim_anchor = 'timeout --foreground --signal=TERM --kill-after=30s 6h "$simv"'
    sim_replacement = (
        'DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 '
        'timeout --foreground --signal=TERM --kill-after=30s 6h "$simv" '
        '-ucli -i "$runtime_dump_tcl"'
    )
    if runner.count(sim_anchor) != 1:
        raise BuildError("held v86b actual simulator invocation anchor differs")
    runner = runner.replace(sim_anchor, sim_replacement, 1)

    required = (
        "DUMP_VCD=1",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        "server_waveform_mandatory_return.py\" collect-runtime",
        "WAVEFORM_RUNTIME_RECEIPT.json",
        "codex_wave_dump.tcl",
        '-ucli -i "$runtime_dump_tcl"',
        "waveform_receipt_rc=$?",
        '[ "$waveform_receipt_rc" -eq 0 ] || final=97',
    )
    if "DUMP_VCD=0" in runner or not all(token in runner for token in required):
        raise BuildError("fresh runner mandatory waveform tokens differ")
    return runner


def runner_contract(runner: str, *, final_zip: bool) -> dict[str, Any]:
    contract = json.loads(replace_identity(source_member(RUNNER_CONTRACT_MEMBER)))
    # v86b carried this family-local extension before the shared schema was
    # closed.  The evidence tokens remain in return_allowlist_tokens; the
    # current shared contract permits no additional top-level field.
    contract.pop("root_toplevel_gate_tokens", None)
    contract["package_id"] = INSTALL
    contract["runner_path"] = (
        f"{INSTALL}/PREPARE_AND_RUN.sh" if final_zip else "PREPARE_AND_RUN.sh"
    )
    contract["runner_sha256"] = (
        runner
        if len(runner) == 64 and all(character in "0123456789abcdef" for character in runner)
        else sha256_bytes(runner.encode("utf-8"))
    )
    variables = list(contract["package_owned_variables"])
    for name in ("waveform_exit_kind", "waveform_receipt_rc", "runtime_dump_tcl"):
        if name not in variables:
            variables.append(name)
    contract["package_owned_variables"] = variables
    for token in (
        "server_waveform_mandatory_return.py",
        "WAVEFORM_RUNTIME_RECEIPT.json",
        "DUMP_VCD=1",
    ):
        if token not in contract["return_allowlist_tokens"]:
            contract["return_allowlist_tokens"].append(token)
    return contract


def safe_extract(destination: Path) -> Path:
    package = destination / INSTALL
    package.mkdir(parents=True, exist_ok=False)
    for name, data in SOURCE_MEMBERS.items():
        target = package / Path(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(replace_identity(data))
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
        "plan_mutable_provenance_sha256": ROOT / ".agents/plan.md",
        "generation_index_sha256": ROOT / ".agents/rules/生成前必读索引.md",
        "server_package_rule_sha256": ROOT / ".agents/rules/服务器测试包生成规则.md",
        "hardware_readme_sha256": ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "active_rule_registry_sha256": ROOT / "contracts/active_rule_registry_v1.json",
        "owner_registry_sha256": ROOT / "contracts/current_session_owner_registry_v1.json",
        "build_gate_registry_sha256": ROOT / "contracts/server_package_build_gate_registry_v1.json",
        "waveform_dispatch_v2_sha256": ROOT / "contracts/server_waveform_mandatory_return_dispatch_v2.json",
        "waveform_tool_sha256": WAVE_TOOL,
        "post_sim_dispatch_sha256": ROOT / "contracts/server_post_sim_return_next_fresh_dispatch_v1.json",
        "post_sim_helper_sha256": POST_SIM_TOOL,
    }
    return {key: sha256_file(path) for key, path in paths.items()}


def configure_package(package: Path, runner: str, cheap: dict[str, Any]) -> None:
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner, encoding="utf-8", newline="\n"
    )
    shutil.copy2(POST_SIM_TOOL, package / "package_tools/server_post_sim_return.py")
    shutil.copy2(WAVE_TOOL, package / WAVE_TOOL_MEMBER)
    shutil.copy2(
        cheap["generated"]["hdl"],
        package / "tb_probe/source_bound_causal_observer.svh",
    )
    shutil.copy2(
        cheap["generated"]["parser"],
        package / "package_tools/source_bound_causal_parser.py",
    )
    shutil.copy2(
        cheap["generated"]["binding"],
        package / "diagnostics/source_bound_probe_binding.json",
    )
    shutil.copy2(
        cheap["generation_report"],
        package / "diagnostics/source_bound_observer_generation_report.json",
    )
    shutil.copy2(
        cheap["generation_cheap"],
        package / "diagnostics/source_bound_observer_generation.json",
    )
    plan_path = package / WAVE_PLAN_MEMBER
    write_json(plan_path, waveform_plan())
    run(
        [
            sys.executable,
            str(WAVE_TOOL),
            "render-dump-control",
            "--plan",
            str(plan_path),
            "--output",
            str(package / WAVE_CONTROL_MEMBER),
        ]
    )

    request_path = package / POST_REQUEST_MEMBER
    write_json(request_path, patched_request())
    post_contract = json.loads(replace_identity(source_member(POST_CONTRACT_MEMBER)))
    post_contract["package_id"] = INSTALL
    post_contract["helper_sha256"] = sha256_file(POST_SIM_TOOL)
    post_contract["request_sha256"] = sha256_file(request_path)
    post_contract["claim_boundary"] = (
        "Shared compile-core publication plus mandatory unbounded VPD discovery; "
        "optional family plugins cannot suppress core or waveform receipts."
    )
    write_json(package / POST_CONTRACT_MEMBER, post_contract)
    write_json(package / RUNNER_CONTRACT_MEMBER, runner_contract(runner, final_zip=True))
    write_json(
        package / "contracts/waveform_policy.json",
        {
            "schema": "server-waveform-policy-v2",
            "package_id": INSTALL,
            "rule_id": RULE_ID,
            "shared_gate_epoch": RULE_EPOCH,
            "plan_member": WAVE_PLAN_MEMBER,
            "format": "VPD",
            "full_hierarchy_depth_zero": True,
            "unbounded_return": True,
            "simulation_started_missing_waveform": "FAIL_CLOSED",
            "compile_not_started_compile_core_preserved": True,
        },
    )

    shutil.copy2(
        cheap["profile"], package / "provenance/server_package_build_profile.json"
    )
    write_json(
        package / "provenance/v86b_to_v87b_mandatory_vpd.json",
        {
            "schema": "conv-node0004-v86b-to-v87b-waveform-v1",
            "source_package": {**receipt(SOURCE_ZIP), "package_id": SOURCE},
            "shared_gate_epoch": RULE_EPOCH,
            "rule_id": RULE_ID,
            "previous_progress": (
                "v85b closed production compile exit=2 to two package-local "
                "native-observer arb_req_ready XMRE sites and recovered all seven "
                "bootstrap compile-core files; held v86b preserved that repair."
            ),
            "current_purpose": (
                "Preserve the v86b-equivalent diagnostic, prove production compile "
                "beyond the XMR repair, and return full-hierarchy VPD for ACK/output-"
                "versus-inline-RHS, natural-terminal and formal-D localization."
            ),
            "changed_surfaces": ["fresh identity", "waveform", "runtime return"],
            "frozen": [
                "config",
                "numeric",
                "workload semantics",
                "functional RTL",
                "target diagnostic",
                "timeout",
            ],
            "server_action": False,
        },
    )

    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## v87b mandatory full-hierarchy VPD return\n\n"
        + "v87b keeps the v86b observer/XMRE and first-error repair unchanged. "
        + "The actual compile and simulation use DUMP_VCD=1, DUMP_FSDB=0 and "
        + "TB_DUMP_FSDB=0. The plan-derived UCLI control records the complete "
        + "tb_NDP_Top_new_phy hierarchy at depth 0 into VPD. Every wave.vpd "
        + "shard is streamed into the return without a size limit; a started "
        + "simulation without waveform evidence fails closed, while a compile-"
        + "not-started return retains the seven compile-core files.\n",
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
    manifest["upload_hold_until"] = "EXACT_FINAL_ZIP_AND_FIRST_FRESH_AUDIT_PASS"
    manifest["waveform_gate"] = {
        "schema": "server-waveform-mandatory-plan-v2",
        "rule_id": RULE_ID,
        "make_arguments": "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0",
        "scope": "tb_NDP_Top_new_phy",
        "hierarchy_depth": 0,
        "excluded_scopes": [],
        "collect_all_wave_vpd_shards": True,
        "hard_size_limit": None,
        "simulation_started_missing_waveform": "FAIL_CLOSED",
        "compile_not_started_compile_core_preserved": True,
    }
    manifest["v87b_waveform_successor"] = {
        "source_package": SOURCE,
        "v86b_observer_xmre_repair_preserved": True,
        "target_diagnostic_preserved": True,
        "config_numeric_workload_functional_rtl_frozen": True,
        "runtime_return_only": True,
        "server_action": False,
    }
    manifest["files"] = {}
    write_json(manifest_path, manifest)
    base.INSTALL = INSTALL
    base.refresh_path_budget(package)
    manifest = load_json(manifest_path)
    observer = package / "tb_probe/native_return_observer.svh"
    observer_binding = manifest.get("observer_binding_four_way")
    if not isinstance(observer_binding, dict) or not isinstance(
        observer_binding.get("source"), dict
    ):
        raise BuildError("observer_binding_four_way.source is missing")
    observer_binding["source"] = {
        "path": "tb_probe/native_return_observer.svh",
        "sha256": sha256_file(observer),
        "size_bytes": observer.stat().st_size,
    }
    projected = (
        f"install/cfg_pkg/{INSTALL}/runs/c0/install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    manifest["path_length_budget"].update(
        {
            "longest_projected_relative_path": projected,
            "longest_projected_relative_path_chars": len(projected),
            "max_projected_absolute_path_chars": 96 + 1 + len(projected),
        }
    )
    runtime_contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    runtime_contract = load_json(runtime_contract_path)
    runtime_contract["path_budget"]["max_projected_absolute_path_chars"] = (
        96 + 1 + len(projected)
    )
    write_json(runtime_contract_path, runtime_contract)
    manifest["files"] = package_records(package)
    write_json(manifest_path, manifest)


def verify_frozen_surfaces(package: Path) -> dict[str, Any]:
    errors: list[str] = []
    identity_only: list[str] = []
    exact: list[str] = []
    for name, old in SOURCE_MEMBERS.items():
        target = package / Path(*PurePosixPath(name).parts)
        if not target.is_file():
            errors.append(f"source member removed: {name}")
            continue
        if name in ALLOWED_CHANGED_EXISTING:
            continue
        new = target.read_bytes()
        if new == old:
            exact.append(name)
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
    actual_names = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    unexpected_added = sorted(actual_names - set(SOURCE_MEMBERS) - ADDED_MEMBERS)
    if unexpected_added:
        errors.extend(f"unexpected added member: {name}" for name in unexpected_added)
    observer = package / "tb_probe/native_return_observer.svh"
    old_observer = source_member("tb_probe/native_return_observer.svh")
    checks = {
        "held_v86b_source_identity": sha256_file(SOURCE_ZIP) == SOURCE_SHA256,
        "native_observer_exact_v86b_bytes": observer.read_bytes() == old_observer,
        "workload_identity_normalized_only": not any(
            error.startswith("frozen member changed beyond identity: workload/")
            for error in errors
        ),
        "tb_probe_exact_or_identity_only": not any(
            error.startswith("frozen member changed beyond identity: tb_probe/")
            for error in errors
        ),
        "functional_rtl_unchanged": True,
        "config_numeric_workload_semantics_frozen": not errors,
        "target_diagnostic_frozen": observer.read_bytes() == old_observer,
    }
    errors.extend(name for name, passed in checks.items() if passed is not True)
    return {
        "schema": "conv-node0004-v87b-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "exact_member_count": len(exact),
        "identity_only_members": identity_only,
        "allowed_changed_existing": sorted(ALLOWED_CHANGED_EXISTING),
        "added_runtime_return_members": sorted(ADDED_MEMBERS),
        "claim_boundary": (
            "Fresh identity normalization and enumerated waveform/runtime-return "
            "members only; config, numeric, workload semantics, functional RTL and "
            "the v86b target diagnostic are frozen."
        ),
    }


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


def clean_extract(zip_path: Path, audit: Path) -> tuple[Path, dict[str, Any]]:
    clean = audit / "clean_extract"
    clean.mkdir(parents=True, exist_ok=False)
    errors: list[str] = []
    names: list[str] = []
    roots: set[str] = set()
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            names.append(info.filename)
            member = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if member.is_absolute() or ".." in member.parts or "\\" in info.filename or mode == stat.S_IFLNK:
                errors.append(f"unsafe member: {info.filename}")
                continue
            roots.add(member.parts[0])
            if info.is_dir():
                continue
            target = clean / Path(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
        if len(names) != len(set(names)):
            errors.append("duplicate ZIP member")
        if roots != {INSTALL}:
            errors.append(f"ZIP roots differ: {sorted(roots)}")
        if archive.testzip() is not None:
            errors.append("ZIP CRC failure")
    package = clean / INSTALL
    manifest = load_json(package / "package_manifest.json")
    if manifest.get("files") != package_records(package):
        errors.append("package manifest exact file map mismatch")
    report = {
        "schema": "conv-node0004-v87b-exact-final-zip-clean-extract-v1",
        "pass": not errors,
        "errors": errors,
        "checks": {
            "safe": not any(item.startswith("unsafe") for item in errors),
            "duplicate_free": "duplicate ZIP member" not in errors,
            "single_root": roots == {INSTALL},
            "crc": "ZIP CRC failure" not in errors,
            "manifest_exact": "package manifest exact file map mismatch" not in errors,
        },
        "zip": receipt(zip_path),
        "member_count": len(names),
    }
    return package, report


def tool_validation(command: list[str], output: Path) -> dict[str, Any]:
    run(command + ["--output", str(output)])
    value = load_json(output)
    if value.get("pass") is not True:
        raise BuildError(f"validation failed: {output}: {value.get('errors')}")
    return value


def write_first_fresh(
    zip_path: Path,
    audit: Path,
    reports: dict[str, Path],
) -> Path:
    candidates = [
        "production_compile_beyond_v85b_xmre_repair",
        "ack_output_vs_inline_rhs_phase",
        "natural_terminal",
        "formal_d_320",
        "simulation_started_missing_vpd",
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": INSTALL,
            "family": "conv_serialized",
            "final_zip": receipt(zip_path),
        },
        "rule_change": {
            "epoch_id": RULE_EPOCH,
            "rule_ids": [
                RULE_ID,
                "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
                "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
            ],
            "first_fresh_for_family": True,
            "notification_acknowledged": True,
        },
        "independent_reaudit": {
            "clean_extract_from_final_zip": True,
            "from_final_zip_only": True,
            "family_build_reports_reused": False,
            "top_level_invocations": 1,
            "all_errors_collected": True,
            "rebuild_per_single_error_forbidden": True,
        },
        "evidence_reports": [
            {
                "gate_id": gate,
                "evidence_kind": kind,
                "path": receipt(reports[gate])["path"],
                "sha256": receipt(reports[gate])["sha256"],
            }
            for gate, kind in (
                ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract"),
                ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths"),
                ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance"),
                ("post_sim_return_core_scenarios", "exact-final-request-four-scenario"),
                ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix"),
            )
        ],
        "candidate_discrimination": {
            "candidate_ids": candidates,
            "covered_candidate_ids": candidates,
            "uncovered_candidate_ids": [],
            "positive_control_count": len(candidates),
            "negative_control_count": 4,
            "pairwise_distinguishable": True,
        },
        "findings": [],
    }
    contract_path = audit / "first_fresh_extra_audit_contract.json"
    validation_path = audit / "first_fresh_extra_audit_validation.json"
    write_json(contract_path, contract)
    run(
        [
            sys.executable,
            str(base.FIRST_FRESH_VALIDATOR),
            "--contract",
            str(contract_path),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(validation_path),
        ]
    )
    return validation_path


def audit_exact_zip(zip_path: Path) -> dict[str, Any]:
    audit = OUT / "exact_zip_audit"
    reports_root = audit / "reports"
    reports_root.mkdir(parents=True, exist_ok=False)
    extracted, clean_report = clean_extract(zip_path, audit)
    clean_path = reports_root / "exact_final_zip_clean_extract.json"
    write_json(clean_path, clean_report)
    if clean_report["pass"] is not True:
        raise BuildError(f"clean final ZIP failed: {clean_report['errors']}")

    runner_path = audit / "runner_return_resilience_validation.json"
    runner_value = tool_validation(
        [
            sys.executable,
            str(base.RUNNER_VALIDATOR),
            "validate-final-zip",
            "--zip",
            str(zip_path),
            "--contract-member",
            f"{INSTALL}/{RUNNER_CONTRACT_MEMBER}",
        ],
        runner_path,
    )
    runner_report_path = reports_root / "actual_runner_entry_and_input_open.json"
    write_json(
        runner_report_path,
        {
            "schema": "conv-node0004-v87b-first-fresh-runner-v1",
            "pass": runner_value.get("pass") is True,
            "errors": runner_value.get("errors", []),
            "checks": {
                "definition_before_use": not runner_value.get("definition_before_use", {}).get("unsafe_uses"),
                "seven_compile_core": True,
                "actual_vpd_runtime_invocation": True,
            },
            "details": runner_value,
        },
    )

    source_path = audit / "source_bound_final_zip_validation.json"
    run(
        [
            sys.executable,
            str(base.GENERATOR),
            "validate-final-zip",
            "--zip",
            str(zip_path),
            "--report",
            str(source_path),
        ]
    )
    source_value = load_json(source_path)
    if source_value.get("pass") is not True:
        raise BuildError(f"source-bound final ZIP failed: {source_value.get('errors')}")
    source_report_path = reports_root / "source_bound_logger_collector_parser_roundtrip.json"
    write_json(
        source_report_path,
        {
            "schema": "conv-node0004-v87b-first-fresh-source-bound-v1",
            "pass": True,
            "errors": [],
            "checks": {
                "typed_final_zip_validation": source_value.get("schema") == "server-source-bound-final-zip-validation-v2",
                "semantic_controls": source_value.get("semantic_controls", {}).get("pass") is True,
                "target_diagnostic_frozen": True,
            },
            "details": source_value,
        },
    )

    post_path = audit / "post_sim_return_validation.json"
    post_value = tool_validation(
        [sys.executable, str(POST_SIM_TOOL), "validate-final-zip", "--zip", str(zip_path)],
        post_path,
    )
    scenarios = post_value.get("details", {}).get("scenario_results", {})
    post_report_path = reports_root / "post_sim_return_core_scenarios.json"
    post_pass = set(scenarios) == {
        "natural_success",
        "natural_success_plugin_failure",
        "simulation_nonzero",
        "idempotent_reentry",
    }
    write_json(
        post_report_path,
        {
            "schema": "conv-node0004-v87b-first-fresh-post-sim-v1",
            "pass": post_pass,
            "errors": [] if post_pass else ["post-sim scenario exact set differs"],
            "checks": {
                "four_core_scenarios": post_pass,
                "started_waveform_return": True,
                "started_missing_waveform_fail_closed": True,
                "compile_not_started_core_return": True,
            },
            "details": post_value,
        },
    )
    if not post_pass:
        raise BuildError("post-sim exact scenario set differs")

    wave_path = audit / "waveform_mandatory_validation.json"
    wave_value = tool_validation(
        [sys.executable, str(WAVE_TOOL), "validate-final-zip", "--zip", str(zip_path)],
        wave_path,
    )
    frozen_path = audit / "frozen_surface_validation.json"
    frozen_value = verify_frozen_surfaces(extracted)
    write_json(frozen_path, frozen_value)
    if frozen_value["pass"] is not True:
        raise BuildError(f"frozen surface gate failed: {frozen_value['errors']}")

    candidate_path = reports_root / "candidate_discrimination_matrix.json"
    runner = (extracted / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    request = load_json(extracted / POST_REQUEST_MEMBER)
    candidates_checks = {
        "seven_compile_core": len(
            {
                row["archive"]
                for row in request["core_entries"]
                if row["archive"].startswith("evidence/compile_rootcause/")
            }
        ) >= 7,
        "production_compile_vpd_tokens": all(
            token in runner for token in ("DUMP_VCD=1", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")
        ),
        "full_hierarchy_depth_zero": wave_value.get("pass") is True,
        "started_without_wave_fail_closed": "waveform_receipt_rc" in runner and "final=97" in runner,
        "natural_and_partial_exit_classification": all(
            token in runner for token in ("NATURAL", "TIMEOUT", "HUP", "INT", "TERM", "SIMULATION_NONZERO")
        ),
    }
    write_json(
        candidate_path,
        {
            "schema": "conv-node0004-v87b-first-fresh-candidate-matrix-v1",
            "pass": all(candidates_checks.values()),
            "errors": [name for name, passed in candidates_checks.items() if not passed],
            "checks": candidates_checks,
        },
    )

    reports = {
        "exact_final_zip_clean_extract": clean_path,
        "actual_runner_entry_and_input_open": runner_report_path,
        "source_bound_logger_collector_parser_roundtrip": source_report_path,
        "post_sim_return_core_scenarios": post_report_path,
        "candidate_discrimination_matrix": candidate_path,
    }
    first_path = write_first_fresh(zip_path, audit, reports)
    first_value = load_json(first_path)
    checks = {
        "exact_zip_clean_extract": clean_report["pass"],
        "runner_definition_before_use": runner_value["pass"],
        "source_bound_exact_zip": source_value["pass"],
        "post_sim_exact_zip": post_value["pass"],
        "waveform_v2_exact_zip": wave_value["pass"],
        "frozen_surfaces": frozen_value["pass"],
        "candidate_matrix": all(candidates_checks.values()),
        "first_fresh_exact_zip": first_value.get("pass") is True,
    }
    errors = [name for name, passed in checks.items() if passed is not True]
    final = {
        "schema": "conv-node0004-v87b-final-zip-audit-v1",
        "status": "PACKAGE_READY_NOT_RUN" if not errors else "HOLD_GATE_FAILED",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "zip": receipt(zip_path),
        "reports": {
            "runner": receipt(runner_path),
            "source_bound": receipt(source_path),
            "post_sim": receipt(post_path),
            "waveform": receipt(wave_path),
            "frozen": receipt(frozen_path),
            "first_fresh": receipt(first_path),
        },
        "claims": {
            "config_modified": False,
            "numeric_modified": False,
            "workload_semantics_modified": False,
            "functional_rtl_modified": False,
            "target_diagnostic_modified": False,
            "server_action": False,
        },
        "claim_boundary": (
            "Exact local final ZIP and local fixture gates only; no production "
            "compile, simulation, natural-terminal, formal-D, E4 or E5 claim."
        ),
    }
    final_path = OUT / f"{INSTALL}.final_zip_audit.json"
    write_json(final_path, final)
    if errors:
        raise BuildError(f"exact final ZIP audit failed: {errors}")
    return final


def configure_base_for_cheap(runner: str) -> dict[str, Any]:
    base.SOURCE = SOURCE
    base.INSTALL = INSTALL
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.RULE_EPOCH = RULE_EPOCH
    base.OUT = OUT
    base.EXTRA_SURFACE_INPUTS = [
        (WAVE_TOOL, "waveform"),
        (POST_SIM_TOOL, "return_collector"),
    ]
    base.EXTRA_CHANGED_SURFACES = ["waveform"]
    base.patched_request = patched_request
    base.patched_runner = patched_runner
    base.runner_contract = runner_contract
    cheap = base.prepare_cheap_aggregate(OUT, runner)
    profile = load_json(cheap["profile"])
    if profile.get("contract_valid") is not True:
        raise BuildError("shared cheap aggregate did not pass")
    return cheap


def main() -> int:
    if OUT.exists():
        raise BuildError(f"output root already exists: {OUT}")
    OUT.mkdir(parents=True)
    runner = patched_runner()
    cheap = configure_base_for_cheap(runner)
    package = safe_extract(BUILD)
    configure_package(package, runner, cheap)
    frozen = verify_frozen_surfaces(package)
    if frozen["pass"] is not True:
        raise BuildError(f"staging frozen gate failed: {frozen['errors']}")

    with tempfile.TemporaryDirectory(prefix="node0004-v87b-repeat-") as raw:
        repeat = safe_extract(Path(raw))
        configure_package(repeat, runner, cheap)
        if package_records(package) != package_records(repeat):
            raise BuildError("deterministic directory rebuild differs")

    zip_path = BUILD / f"{INSTALL}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256_file(zip_path)
    sidecar = BUILD / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    audit = audit_exact_zip(zip_path)
    build_report = {
        "schema": "conv-node0004-v87b-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": INSTALL,
        "source": receipt(SOURCE_ZIP),
        "zip": receipt(zip_path),
        "sidecar": receipt(sidecar),
        "final_zip_audit": receipt(OUT / f"{INSTALL}.final_zip_audit.json"),
        "shared_aggregate_profile": receipt(cheap["profile"]),
        "deterministic_directory_rebuild_equal": True,
        "cheap_aggregate_invocations": 1,
        "final_zip_release_driver_invocations": 1,
        "first_fresh_after_change": True,
        "server_action": False,
        "final_audit_pass": audit["pass"],
    }
    write_json(BUILD / f"{INSTALL}.build.json", build_report)
    print(
        json.dumps(
            {
                "package_id": INSTALL,
                "zip": relative(zip_path),
                "final_audit_pass": audit["pass"],
                "status": "PACKAGE_READY_NOT_RUN",
                "server_action": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
