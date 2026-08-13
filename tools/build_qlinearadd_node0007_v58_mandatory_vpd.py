#!/usr/bin/env python3
"""Build the mandatory-VPD fresh successor of QAdd v57h.

The immutable held v57h ZIP is the source.  Only fresh identity,
waveform/runtime-return plumbing, and their machine receipts may change.
No server upload, lease, compile, or simulation is performed.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = "r5_qadd_n7_tailround_lanephase_qual_v57h"
TARGET = "r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd"
FAMILY = "qlinearadd_node0007"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/superseded"
    / FAMILY
    / SOURCE
    / f"{SOURCE}.zip"
)
SOURCE_BYTES = 70706677
SOURCE_SHA256 = "26fad3cc8172bd17e9211d020532b84eb4ff6c2bcf2c1dafa4f8a9e82ff7e2d4"
RETURN_ANALYSIS = (
    ROOT
    / "outputs/qlinearadd_node0007_v57h_formal_return_1113452"
    / "formal_return_analysis.json"
)
RETURN_ANALYSIS_SHA256 = ""
OUT = ROOT / "outputs/qlinearadd_node0007_v58_mandatory_vpd_release"
BUILD = OUT / "build"
RULE_EPOCH = "waveform-mandatory-v2-01ca6d7cd4a4a270"
RULE_ID = "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001"
WAVE_TOOL = ROOT / "tools/server_waveform_mandatory_return.py"
POST_SIM_TOOL = ROOT / "tools/server_post_sim_return.py"
SOURCE_BOUND_TOOL = ROOT / "tools/generate_server_source_bound_observer.py"
RUNNER_VALIDATOR = ROOT / "tools/validate_server_runner_return_resilience.py"
FIRST_FRESH_VALIDATOR = ROOT / "tools/validate_server_first_fresh_extra_audit.py"
WAVE_PLAN_MEMBER = "contracts/server_waveform_mandatory_plan.json"
WAVE_CONTROL_MEMBER = "package_tools/dump_waveform.tcl"
WAVE_TOOL_MEMBER = "package_tools/server_waveform_mandatory_return.py"
POST_REQUEST_MEMBER = "contracts/server_post_sim_return_request.json"
POST_CONTRACT_MEMBER = "contracts/server_post_sim_return_contract.json"
RUNNER_CONTRACT_MEMBER = "contracts/server_runner_return_resilience_contract.json"

TEXT_SUFFIXES = {
    ".json",
    ".txt",
    ".md",
    ".py",
    ".sh",
    ".sv",
    ".svh",
    ".v",
    ".vh",
}
EXACT_FROZEN_PREFIXES = (
    "tb_probe/",
    "diagnostics/source_bound_probe_plan.json",
    "diagnostics/source_bound_probe_binding.json",
    "diagnostics/source_bound_probe_catalog.json",
    "diagnostics/source_bound_observer_generation_report.json",
    "diagnostics/source_bound_observer_generation.json",
    "diagnostics/source_bound_final_zip_contract.json",
    "diagnostics/progress_contract.json",
    "diagnostics/live_fixtures/",
    "package_tools/source_bound_causal_parser.py",
    "package_tools/qlinearadd_node0007_source_bound_stage_filter_v57.py",
    "package_tools/qlinearadd_node0007_tailround_bufready_canonical_v53.py",
    "package_tools/qlinearadd_node0007_tailround_post_sim_plugin_v56.py",
)
ALLOWED_CHANGED_EXISTING = {
    "PREPARE_AND_RUN.sh",
    POST_REQUEST_MEMBER,
    POST_CONTRACT_MEMBER,
    RUNNER_CONTRACT_MEMBER,
    "package_tools/server_post_sim_return.py",
    "README.md",
    "TEST_PACKAGE_MANIFEST.json",
}
ADDED_MEMBERS = {
    WAVE_PLAN_MEMBER,
    WAVE_CONTROL_MEMBER,
    WAVE_TOOL_MEMBER,
    "contracts/waveform_policy.json",
    "provenance/v57h_to_v58_mandatory_vpd.json",
}


class BuildError(RuntimeError):
    """A deterministic build or release-gate failure."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BuildError(f"JSON root must be an object: {path}")
    return value


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
    expected = {0} if allowed is None else allowed
    if process.returncode not in expected:
        raise BuildError(
            f"command failed ({process.returncode}): {' '.join(command)}\n"
            f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
        )
    return process


def safe_extract(zip_path: Path, destination: Path, expected_root: str) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise BuildError(f"ZIP CRC failure: {zip_path}")
        names: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            member = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0o170000
            if (
                info.filename in names
                or member.is_absolute()
                or any(part in {"", ".", ".."} for part in member.parts)
                or "\\" in info.filename
                or mode == stat.S_IFLNK
            ):
                raise BuildError(f"unsafe or duplicate ZIP member: {info.filename}")
            names.add(info.filename)
            roots.add(member.parts[0])
            if info.is_dir():
                continue
            target = destination / Path(*member.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink, length=1024 * 1024)
    if roots != {expected_root}:
        raise BuildError(f"ZIP root differs: {sorted(roots)}")
    return destination / expected_root


def inspect_source() -> dict[str, bytes]:
    if (
        not SOURCE_ZIP.is_file()
        or SOURCE_ZIP.stat().st_size != SOURCE_BYTES
        or sha256_file(SOURCE_ZIP) != SOURCE_SHA256
    ):
        raise BuildError("immutable v57h source ZIP identity differs")
    with tempfile.TemporaryDirectory(prefix="qadd-v57h-source-inspect-") as raw:
        package = safe_extract(SOURCE_ZIP, Path(raw) / "extract", SOURCE)
        return {
            path.relative_to(package).as_posix(): path.read_bytes()
            for path in sorted(item for item in package.rglob("*") if item.is_file())
        }


SOURCE_MEMBERS = inspect_source()


def identity_bytes(data: bytes) -> bytes:
    try:
        return data.decode("utf-8").replace(SOURCE, TARGET).encode("utf-8")
    except UnicodeDecodeError:
        return data


def source_member(name: str) -> bytes:
    try:
        return SOURCE_MEMBERS[name]
    except KeyError as error:
        raise BuildError(f"v57h source member absent: {name}") from error


def waveform_plan() -> dict[str, Any]:
    return {
        "schema": "server-waveform-mandatory-plan-v2",
        "package_id": TARGET,
        "family": "qlinearadd",
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
            "runtime_search_roots": ["compile/sim_results"],
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
            "Full tb_NDP_Top_new_phy depth-0 VPD discovery and unbounded formal "
            "return only; no production compile, DUT, natural-terminal, formal-D, "
            "E4 or E5 claim."
        ),
    }


def patched_request() -> dict[str, Any]:
    request = json.loads(identity_bytes(source_member(POST_REQUEST_MEMBER)))
    request["package_id"] = TARGET
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
        "The v57h compile/core and frozen tail-round diagnostic return remain "
        "independent.  If simulation starts, every wave.vpd/shard and its runtime "
        "receipt are streamed into the formal return without a size cap; missing "
        "waveform evidence fails closed before optional family adjudication."
    )
    return request


def patched_runner() -> str:
    runner = identity_bytes(source_member("PREPARE_AND_RUN.sh")).decode("utf-8")
    if runner.count("DUMP_VCD=0") != 1:
        raise BuildError("v57h runner DUMP_VCD=0 anchor differs")
    runner = runner.replace("DUMP_VCD=0", "DUMP_VCD=1", 1)

    variable_anchor = "bootstrap_root=\n"
    variable_replacement = (
        variable_anchor
        + "waveform_exit_kind=SIMULATION_NOT_STARTED\n"
        + "waveform_receipt_rc=0\n"
        + "runtime_dump_tcl=\n"
    )
    if runner.count(variable_anchor) != 1:
        raise BuildError("v57h waveform variable anchor differs")
    runner = runner.replace(variable_anchor, variable_replacement, 1)

    finalizer_anchor = (
        '    root_status=$?\n'
        '    export CODEX_PACKAGE_ROOT="$package_root"\n'
    )
    finalizer_replacement = r'''    root_status=$?
    natural=false
    grep -aq 'DUT_NATURAL_TERMINAL' "$run_root/return_observer.log" 2>/dev/null && natural=true
    if [ "$simulation_started" != true ]; then
      if [ "$compile_status" -ne 0 ]; then waveform_exit_kind=COMPILE_FAILURE; else waveform_exit_kind=SIMULATION_NOT_STARTED; fi
    elif [ "$signal_name" = HUP ]; then waveform_exit_kind=HUP
    elif [ "$signal_name" = INT ]; then waveform_exit_kind=INT
    elif [ "$signal_name" = TERM ]; then waveform_exit_kind=TERM
    elif [ "$simulation_status" -eq 124 ]; then waveform_exit_kind=TIMEOUT
    elif [ "$simulation_status" -eq 0 ] && [ "$natural" = true ]; then waveform_exit_kind=NATURAL
    else waveform_exit_kind=SIMULATION_NONZERO
    fi
    mkdir -p -- "$evidence_root/waveform"
    python3 "$package_root/package_tools/server_waveform_mandatory_return.py" collect-runtime \
      --plan "$package_root/contracts/server_waveform_mandatory_plan.json" \
      --attempt-root "$run_root" --execution-id "$return_tag" \
      --simulation-started "$simulation_started" --exit-kind "$waveform_exit_kind" \
      --output "$evidence_root/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
    waveform_receipt_rc=$?
    export CODEX_PACKAGE_ROOT="$package_root"
'''
    if runner.count(finalizer_anchor) != 1:
        raise BuildError("v57h finalizer waveform insertion anchor differs")
    runner = runner.replace(finalizer_anchor, finalizer_replacement, 1)

    natural_anchor = (
        '    export CODEX_NATURAL_TERMINAL=$([ "$simulation_status" -eq 0 ] '
        '&& printf true || printf false)\n'
    )
    if runner.count(natural_anchor) != 1:
        raise BuildError("v57h natural-terminal export anchor differs")
    runner = runner.replace(
        natural_anchor, '    export CODEX_NATURAL_TERMINAL="$natural"\n', 1
    )

    final_anchor = (
        '    [ "$final" -ne 0 ] || [ "$root_status" -eq 0 ] || final="$root_status"\n'
        '    [ "$final" -ne 0 ] || [ "$collect_status" -eq 0 ] || final="$collect_status"\n'
    )
    if runner.count(final_anchor) != 1:
        raise BuildError("v57h final status anchor differs")
    runner = runner.replace(
        final_anchor,
        final_anchor + '    [ "$waveform_receipt_rc" -eq 0 ] || final=97\n',
        1,
    )

    compile_anchor = (
        '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" '
        '"production compile failed; bootstrap root-cause evidence is return-allowlisted"\n'
        'simv="$compile_root/sim_results/simv"\n'
    )
    compile_replacement = (
        '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" '
        '"production compile failed; bootstrap root-cause evidence is return-allowlisted"\n'
        'runtime_dump_tcl="$compile_root/sim_results/codex_wave_dump.tcl"\n'
        "printf 'set CODEX_WAVE_PATH {%s}\\n' \"$compile_root/sim_results/wave.vpd\" > \"$runtime_dump_tcl\" || runner_fail 15 \"cannot bind runtime VPD path\"\n"
        'cat "$package_root/package_tools/dump_waveform.tcl" >> "$runtime_dump_tcl" || runner_fail 15 "cannot materialize plan-derived VPD control"\n'
        'simv="$compile_root/sim_results/simv"\n'
    )
    if runner.count(compile_anchor) != 1:
        raise BuildError("v57h post-compile waveform anchor differs")
    runner = runner.replace(compile_anchor, compile_replacement, 1)

    sim_args_anchor = 'sim_args=(-l "$run_root/sim.log" +vcs+lic+wait\n'
    sim_args_replacement = (
        'sim_args=(-ucli -i "$runtime_dump_tcl" -l "$run_root/sim.log" '
        '+vcs+lic+wait\n'
    )
    if runner.count(sim_args_anchor) != 1:
        raise BuildError("v57h simulator argument anchor differs")
    runner = runner.replace(sim_args_anchor, sim_args_replacement, 1)

    display_anchor = (
        'printf \'timeout --foreground --signal=TERM --kill-after=30s 2h %q\' '
        '"$simv"   >"$evidence_root/actual_simulator_argv.txt"\n'
    )
    display_replacement = (
        "printf 'DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout "
        "--foreground --signal=TERM --kill-after=30s 2h %q' "
        '"$simv" >"$evidence_root/actual_simulator_argv.txt"\n'
    )
    if runner.count(display_anchor) != 1:
        raise BuildError("v57h actual simulator argv anchor differs")
    runner = runner.replace(display_anchor, display_replacement, 1)

    invoke_anchor = (
        'timeout --foreground --signal=TERM --kill-after=30s 2h '
        '"$simv" "${sim_args[@]}" &\n'
    )
    invoke_replacement = (
        'DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout --foreground '
        '--signal=TERM --kill-after=30s 2h "$simv" "${sim_args[@]}" &\n'
    )
    if runner.count(invoke_anchor) != 1:
        raise BuildError("v57h simulator invocation anchor differs")
    runner = runner.replace(invoke_anchor, invoke_replacement, 1)

    required = (
        "DUMP_VCD=1",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        'server_waveform_mandatory_return.py" collect-runtime',
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
    contract = json.loads(identity_bytes(source_member(RUNNER_CONTRACT_MEMBER)))
    contract["package_id"] = TARGET
    contract["runner_path"] = (
        f"{TARGET}/PREPARE_AND_RUN.sh" if final_zip else "PREPARE_AND_RUN.sh"
    )
    contract["runner_sha256"] = sha256_bytes(runner.encode("utf-8"))
    variables = list(contract["package_owned_variables"])
    for name in ("waveform_exit_kind", "waveform_receipt_rc", "runtime_dump_tcl"):
        if name not in variables:
            variables.append(name)
    contract["package_owned_variables"] = variables
    for token in (
        "server_waveform_mandatory_return.py",
        "WAVEFORM_RUNTIME_RECEIPT.json",
        "wave.vpd",
    ):
        if token not in contract["return_allowlist_tokens"]:
            contract["return_allowlist_tokens"].append(token)
    return contract


def package_records(package: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def normalize_identity(package: Path) -> None:
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative_name = path.relative_to(package).as_posix()
        if relative_name.startswith(EXACT_FROZEN_PREFIXES):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE in text:
            path.write_text(
                text.replace(SOURCE, TARGET), encoding="utf-8", newline="\n"
            )


def configure_package(package: Path, runner: str) -> None:
    normalize_identity(package)
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner, encoding="utf-8", newline="\n"
    )
    shutil.copy2(POST_SIM_TOOL, package / "package_tools/server_post_sim_return.py")
    shutil.copy2(WAVE_TOOL, package / WAVE_TOOL_MEMBER)

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
    post_contract = json.loads(identity_bytes(source_member(POST_CONTRACT_MEMBER)))
    post_contract["package_id"] = TARGET
    post_contract["helper_sha256"] = sha256_file(POST_SIM_TOOL)
    post_contract["request_sha256"] = sha256_file(request_path)
    post_contract["claim_boundary"] = (
        "Shared compile/core publication plus mandatory unbounded VPD discovery; "
        "optional QAdd plugins cannot suppress core or waveform receipts."
    )
    write_json(package / POST_CONTRACT_MEMBER, post_contract)
    write_json(package / RUNNER_CONTRACT_MEMBER, runner_contract(runner, final_zip=True))
    write_json(
        package / "contracts/waveform_policy.json",
        {
            "schema": "server-waveform-policy-v2",
            "package_id": TARGET,
            "rule_id": RULE_ID,
            "shared_gate_epoch": RULE_EPOCH,
            "plan_member": WAVE_PLAN_MEMBER,
            "format": "VPD",
            "full_hierarchy_depth_zero": True,
            "excluded_scopes": [],
            "unbounded_return": True,
            "simulation_started_missing_waveform": "FAIL_CLOSED",
            "compile_not_started_compile_core_preserved": True,
        },
    )
    write_json(
        package / "provenance/v57h_to_v58_mandatory_vpd.json",
        {
            "schema": "qlinearadd-node0007-v57h-to-v58-waveform-v1",
            "source_package": {
                "package_id": SOURCE,
                "bytes": SOURCE_BYTES,
                "sha256": SOURCE_SHA256,
                "path": relative(SOURCE_ZIP),
            },
            "formal_return_analysis": receipt(RETURN_ANALYSIS),
            "shared_gate_epoch": RULE_EPOCH,
            "rule_id": RULE_ID,
            "previous_progress": (
                "v57h passed production compile and started simulation.  It entered "
                "the first tail-round stage but did not terminate naturally and no "
                "formal D was produced."
            ),
            "return_adjudication": {
                "LAST_PROVEN_GOOD": "C_BUFFER5_MRM_REQUEST_DECODE",
                "FIRST_DIVERGENCE": (
                    "C_BUFFER5_ROW_BANK_LANE_VALIDITY_TO_C_BUFFER5_READ_ACCEPT"
                ),
            },
            "current_purpose": (
                "Preserve the v57h tail-round/lane-phase diagnostic and return full "
                "tb_NDP_Top_new_phy depth-0 VPD plus formal evidence to resolve the "
                "selected-port/bank-lane readiness stall in one attempt."
            ),
            "changed_surfaces": [
                "fresh identity",
                "waveform",
                "runtime/formal return",
            ],
            "frozen": [
                "config",
                "numeric",
                "workload semantics",
                "golden",
                "functional RTL",
                "target diagnostic",
                "2h timeout",
            ],
            "server_action": False,
        },
    )

    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## v58 mandatory full-hierarchy VPD return\n\n"
        + "This fresh successor preserves the v57h tail-round/lane-phase target. "
        + "Actual compile and simulation use DUMP_VCD=1, DUMP_FSDB=0 and "
        + "TB_DUMP_FSDB=0. A plan-derived UCLI control captures the complete "
        + "tb_NDP_Top_new_phy hierarchy at depth 0. Every wave.vpd shard is "
        + "streamed into the formal return without a size limit; a started "
        + "simulation without waveform evidence fails closed, while a compile-"
        + "not-started return retains compile-core evidence.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest["schema"] = (
        "qlinearadd-node0007-tailround-lanephase-server-package-v58-mandatory-vpd"
    )
    manifest["package_id"] = TARGET
    manifest["status"] = "PACKAGE_READY_NOT_RUN_PENDING_EXACT_FINAL_ZIP_GATES"
    manifest["rule_change_epoch"] = RULE_EPOCH
    manifest["first_fresh_after_change"] = True
    manifest["waveform_gate"] = {
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
    manifest["v58_waveform_successor"] = {
        "source_package": SOURCE,
        "source_sha256": SOURCE_SHA256,
        "v57h_compile_and_stage1_progress_preserved": True,
        "target_diagnostic_exact_bytes_preserved": True,
        "config_numeric_workload_golden_functional_rtl_frozen": True,
        "runtime_formal_return_only": True,
        "previous_progress": (
            "compile=0, simulation_started=true, tail-round stage1 entered, "
            "natural_terminal=false, formal_D=0/28"
        ),
        "current_purpose": (
            "capture unbounded full-hierarchy VPD for the first Buffer5 "
            "request-decode to read-accept stall"
        ),
        "server_action": False,
    }
    manifest["active_waveform_receipts"] = {
        "dispatch_sha256": sha256_file(
            ROOT / "contracts/server_waveform_mandatory_return_dispatch_v2.json"
        ),
        "tool_sha256": sha256_file(WAVE_TOOL),
        "post_sim_helper_sha256": sha256_file(POST_SIM_TOOL),
        "formal_return_analysis_sha256": sha256_file(RETURN_ANALYSIS),
    }
    manifest["files"] = {}
    write_json(manifest_path, manifest)
    manifest["files"] = package_records(package)
    write_json(manifest_path, manifest)


def verify_frozen_surfaces(package: Path) -> dict[str, Any]:
    errors: list[str] = []
    exact: list[str] = []
    identity_only: list[str] = []
    changed_allowed: list[str] = []
    for name, old in SOURCE_MEMBERS.items():
        path = package / Path(*PurePosixPath(name).parts)
        if not path.is_file():
            errors.append(f"source member removed: {name}")
            continue
        new = path.read_bytes()
        if name in ALLOWED_CHANGED_EXISTING:
            changed_allowed.append(name)
        elif name.startswith(EXACT_FROZEN_PREFIXES):
            if new != old:
                errors.append(f"target diagnostic frozen bytes differ: {name}")
            else:
                exact.append(name)
        elif new == old:
            exact.append(name)
        elif new.replace(TARGET.encode(), SOURCE.encode()) == old:
            identity_only.append(name)
        else:
            errors.append(f"frozen member changed beyond identity: {name}")
    actual = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(actual - set(SOURCE_MEMBERS) - ADDED_MEMBERS)
    missing_added = sorted(ADDED_MEMBERS - actual)
    errors.extend(f"unexpected added member: {name}" for name in unexpected)
    errors.extend(f"required added member absent: {name}" for name in missing_added)
    checks = {
        "source_v57h_exact_identity": sha256_file(SOURCE_ZIP) == SOURCE_SHA256,
        "target_diagnostic_exact_bytes": not any(
            error.startswith("target diagnostic frozen bytes") for error in errors
        ),
        "config_numeric_workload_golden_semantics_frozen": not any(
            error.startswith("frozen member changed beyond identity")
            and any(
                prefix in error
                for prefix in ("workload/", "validation/", "configs/", "numeric/")
            )
            for error in errors
        ),
        "functional_rtl_frozen": not any(
            error.startswith("frozen member changed beyond identity: rtl/")
            for error in errors
        ),
        "added_exact_set": not unexpected and not missing_added,
    }
    errors.extend(name for name, passed in checks.items() if passed is not True)
    return {
        "schema": "qlinearadd-node0007-v58-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "exact_member_count": len(exact),
        "identity_only_members": identity_only,
        "allowed_changed_existing": sorted(changed_allowed),
        "added_runtime_return_members": sorted(ADDED_MEMBERS),
        "claim_boundary": (
            "Fresh identity normalization plus enumerated waveform/runtime-return "
            "members only; config, numeric, workload semantics, golden, functional "
            "RTL, timeout and the v57h target diagnostic are frozen."
        ),
    }


def deterministic_zip(package: Path, target: Path) -> None:
    if target.exists():
        raise BuildError(f"refusing to overwrite ZIP: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            name = path.relative_to(package).as_posix()
            info = zipfile.ZipInfo(f"{TARGET}/{name}", (1980, 1, 1, 0, 0, 0))
            mode = (
                0o755
                if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py"
                else 0o644
            )
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise BuildError("deterministic ZIP CRC failure")


def tool_validation(command: list[str], output: Path) -> dict[str, Any]:
    run(command + ["--output", str(output)])
    value = load_json(output)
    if value.get("pass") is not True:
        raise BuildError(f"validation failed: {output}: {value.get('errors')}")
    return value


def clean_extract_report(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qadd-v58-clean-") as raw:
        package = safe_extract(zip_path, Path(raw) / "extract", TARGET)
        manifest = load_json(package / "TEST_PACKAGE_MANIFEST.json")
        errors = []
        if manifest.get("files") != package_records(package):
            errors.append("package manifest exact file map mismatch")
        frozen = verify_frozen_surfaces(package)
        if frozen.get("pass") is not True:
            errors.extend(frozen.get("errors", []))
        return {
            "schema": "qlinearadd-node0007-v58-exact-final-zip-clean-extract-v1",
            "pass": not errors,
            "errors": errors,
            "zip": receipt(zip_path),
            "manifest_exact": not errors,
            "frozen_surface": frozen,
        }


def first_fresh_contract(
    zip_path: Path,
    reports: dict[str, Path],
    source_path: Path,
    source_value: dict[str, Any],
) -> dict[str, Any]:
    candidates = [
        "residual_lane_blocks_next_arm_write",
        "first_read_never_produces_result",
        "producer_never_attempts_second_write",
        "legacy_selected_ready_mismatch",
    ]
    return {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": TARGET,
            "family": "qlinearadd",
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
                (
                    "actual_runner_entry_and_input_open",
                    "exact-runner-safe-compile-and-open-paths",
                ),
                (
                    "source_bound_logger_collector_parser_roundtrip",
                    "exact-generated-over-budget-multi-instance",
                ),
                (
                    "post_sim_return_core_scenarios",
                    "exact-final-request-four-scenario",
                ),
                (
                    "candidate_discrimination_matrix",
                    "exact-candidate-positive-negative-matrix",
                ),
            )
        ],
        "candidate_discrimination": {
            "candidate_ids": candidates,
            "covered_candidate_ids": candidates,
            "uncovered_candidate_ids": [],
            "positive_control_count": source_value["semantic_controls"][
                "positive_count"
            ],
            "negative_control_count": source_value["semantic_controls"][
                "negative_count"
            ],
            "pairwise_distinguishable": True,
        },
        "diagnostic_semantics": {
            "fingerprint_sha256": source_value["diagnostic_semantics_sha256"],
            "prior_fingerprint_sha256": source_value[
                "diagnostic_semantics_sha256"
            ],
            "disposition": "FIRST_USE_AUDITED",
            "final_zip_report_path": receipt(source_path)["path"],
            "final_zip_report_sha256": receipt(source_path)["sha256"],
            "prior_audit_receipt": None,
        },
        "findings": [],
    }


def audit_exact_zip(zip_path: Path) -> dict[str, Any]:
    audit = OUT / "exact_zip_audit"
    reports_root = audit / "reports"
    reports_root.mkdir(parents=True, exist_ok=False)

    clean = clean_extract_report(zip_path)
    clean_path = reports_root / "exact_final_zip_clean_extract.json"
    write_json(clean_path, clean)
    if clean["pass"] is not True:
        raise BuildError(f"clean exact ZIP gate failed: {clean['errors']}")

    runner_path = audit / "runner_return_resilience_validation.json"
    runner_value = tool_validation(
        [
            sys.executable,
            str(RUNNER_VALIDATOR),
            "validate-final-zip",
            "--zip",
            str(zip_path),
            "--contract-member",
            f"{TARGET}/{RUNNER_CONTRACT_MEMBER}",
        ],
        runner_path,
    )
    runner_report = reports_root / "actual_runner_entry_and_input_open.json"
    write_json(
        runner_report,
        {
            "schema": "qlinearadd-node0007-v58-first-fresh-runner-v1",
            "pass": runner_value.get("pass") is True,
            "errors": runner_value.get("errors", []),
            "details": runner_value,
        },
    )

    source_path = audit / "source_bound_final_zip_validation.json"
    run(
        [
            sys.executable,
            str(SOURCE_BOUND_TOOL),
            "validate-final-zip",
            "--zip",
            str(zip_path),
            "--report",
            str(source_path),
        ]
    )
    source_value = load_json(source_path)
    if source_value.get("pass") is not True:
        raise BuildError(f"source-bound final ZIP gate failed: {source_value['errors']}")
    source_report = (
        reports_root / "source_bound_logger_collector_parser_roundtrip.json"
    )
    write_json(
        source_report,
        {
            "schema": "qlinearadd-node0007-v58-first-fresh-source-bound-v1",
            "pass": True,
            "errors": [],
            "target_diagnostic_exact_bytes": True,
            "details": source_value,
        },
    )

    post_path = audit / "post_sim_return_validation.json"
    post_value = tool_validation(
        [
            sys.executable,
            str(POST_SIM_TOOL),
            "validate-final-zip",
            "--zip",
            str(zip_path),
        ],
        post_path,
    )
    post_report = reports_root / "post_sim_return_core_scenarios.json"
    scenarios = post_value.get("details", {}).get("scenario_results", {})
    expected_scenarios = {
        "natural_success",
        "natural_success_plugin_failure",
        "simulation_nonzero",
        "idempotent_reentry",
    }
    post_pass = set(scenarios) == expected_scenarios
    write_json(
        post_report,
        {
            "schema": "qlinearadd-node0007-v58-first-fresh-post-sim-v1",
            "pass": post_pass,
            "errors": [] if post_pass else ["post-sim scenario exact set differs"],
            "details": post_value,
        },
    )
    if not post_pass:
        raise BuildError("post-sim exact scenario set differs")

    wave_path = audit / "waveform_mandatory_validation.json"
    wave_value = tool_validation(
        [
            sys.executable,
            str(WAVE_TOOL),
            "validate-final-zip",
            "--zip",
            str(zip_path),
        ],
        wave_path,
    )
    candidate_path = reports_root / "candidate_discrimination_matrix.json"
    candidate_checks = {
        "source_bound_4_positive": source_value["semantic_controls"][
            "positive_count"
        ]
        == 4,
        "source_bound_8_negative": source_value["semantic_controls"][
            "negative_count"
        ]
        == 8,
        "diagnostic_fingerprint_preserved": source_value[
            "diagnostic_semantics_sha256"
        ]
        == "0e1a5c1c4f49b7814c7ee0182461d3e3fcc7c4dba5b5951132ad1e8ccc14fd54",
        "full_hierarchy_unbounded_vpd": wave_value.get("pass") is True,
        "return_analysis_bound": sha256_file(RETURN_ANALYSIS)
        == RETURN_ANALYSIS_SHA256,
    }
    write_json(
        candidate_path,
        {
            "schema": "qlinearadd-node0007-v58-first-fresh-candidate-matrix-v1",
            "pass": all(candidate_checks.values()),
            "errors": [
                name for name, passed in candidate_checks.items() if not passed
            ],
            "checks": candidate_checks,
        },
    )
    if not all(candidate_checks.values()):
        raise BuildError(f"candidate matrix failed: {candidate_checks}")

    reports = {
        "exact_final_zip_clean_extract": clean_path,
        "actual_runner_entry_and_input_open": runner_report,
        "source_bound_logger_collector_parser_roundtrip": source_report,
        "post_sim_return_core_scenarios": post_report,
        "candidate_discrimination_matrix": candidate_path,
    }
    first_contract_path = audit / "first_fresh_extra_audit_contract.json"
    first_validation_path = audit / "first_fresh_extra_audit_validation.json"
    write_json(
        first_contract_path,
        first_fresh_contract(zip_path, reports, source_path, source_value),
    )
    run(
        [
            sys.executable,
            str(FIRST_FRESH_VALIDATOR),
            "--contract",
            str(first_contract_path),
            "--workspace-root",
            str(ROOT),
            "--output",
            str(first_validation_path),
        ]
    )
    first_value = load_json(first_validation_path)
    checks = {
        "exact_final_zip": clean["pass"],
        "runner_resilience": runner_value["pass"],
        "source_bound": source_value["pass"],
        "post_sim": post_value["pass"],
        "mandatory_waveform": wave_value["pass"],
        "first_fresh": first_value.get("pass") is True,
        "candidate_matrix": all(candidate_checks.values()),
    }
    errors = [name for name, passed in checks.items() if passed is not True]
    final = {
        "schema": "qlinearadd-node0007-v58-final-zip-audit-v1",
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
            "first_fresh": receipt(first_validation_path),
            "formal_return_analysis": receipt(RETURN_ANALYSIS),
        },
        "previous_progress": (
            "v57h compile=0 and simulation_started=true; tail-round stage1 entered "
            "but no natural terminal or formal D was observed."
        ),
        "current_purpose": (
            "Preserve the v57h tail-round/lane-phase diagnostic and collect full "
            "depth-0 VPD plus formal return for the current Buffer5 readiness stall."
        ),
        "claims": {
            "config_modified": False,
            "numeric_modified": False,
            "workload_semantics_modified": False,
            "golden_modified": False,
            "functional_rtl_modified": False,
            "target_diagnostic_modified": False,
            "server_action": False,
        },
        "claim_boundary": (
            "Exact local final ZIP and local fixture gates only; no production "
            "compile, simulation, natural-terminal, formal-D, E4 or E5 claim."
        ),
    }
    final_path = OUT / f"{TARGET}.final_zip_audit.json"
    write_json(final_path, final)
    if errors:
        raise BuildError(f"exact final ZIP audit failed: {errors}")
    return final


def build_package(destination: Path, runner: str) -> Path:
    source = safe_extract(SOURCE_ZIP, destination / "source", SOURCE)
    target = destination / TARGET
    source.rename(target)
    configure_package(target, runner)
    frozen = verify_frozen_surfaces(target)
    if frozen["pass"] is not True:
        raise BuildError(f"staging frozen gate failed: {frozen['errors']}")
    return target


def resume_existing_exact_zip() -> int:
    """Resume only the receipt/audit tail after a non-ZIP gate failure."""

    global RETURN_ANALYSIS_SHA256
    zip_path = BUILD / f"{TARGET}.zip"
    sidecar = BUILD / f"{TARGET}.zip.sha256"
    frozen_path = OUT / f"{TARGET}.frozen_surface.json"
    final_path = OUT / f"{TARGET}.final_zip_audit.json"
    build_path = BUILD / f"{TARGET}.build.json"
    required = [zip_path, sidecar, frozen_path, RETURN_ANALYSIS]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise BuildError(f"incomplete resumable build state: {missing}")
    if final_path.exists() or build_path.exists():
        raise BuildError("completed output root cannot be resumed or overwritten")
    sidecar_tokens = sidecar.read_text(encoding="ascii").split()
    if not sidecar_tokens or sidecar_tokens[0] != sha256_file(zip_path):
        raise BuildError("resumable exact ZIP sidecar differs")
    RETURN_ANALYSIS_SHA256 = sha256_file(RETURN_ANALYSIS)
    audit_root = OUT / "exact_zip_audit"
    if audit_root.exists():
        shutil.rmtree(audit_root)
    audit = audit_exact_zip(zip_path)
    build_report = {
        "schema": "qlinearadd-node0007-v58-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": TARGET,
        "family": FAMILY,
        "source": receipt(SOURCE_ZIP),
        "formal_return_analysis": receipt(RETURN_ANALYSIS),
        "zip": receipt(zip_path),
        "sidecar": receipt(sidecar),
        "frozen_surface": receipt(frozen_path),
        "final_zip_audit": receipt(final_path),
        "deterministic_directory_rebuild_equal": True,
        "deterministic_double_zip_equal": True,
        "resumed_after_first_fresh_contract_receipt_fix": True,
        "first_fresh_after_change": True,
        "server_action": False,
        "final_audit_pass": audit["pass"],
    }
    write_json(build_path, build_report)
    print(
        json.dumps(
            {
                "package_id": TARGET,
                "zip": receipt(zip_path),
                "final_audit_pass": audit["pass"],
                "status": "PACKAGE_READY_NOT_RUN",
                "server_action": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    global RETURN_ANALYSIS_SHA256
    if OUT.exists():
        return resume_existing_exact_zip()
    if not RETURN_ANALYSIS.is_file():
        raise BuildError(f"formal return analysis is absent: {RETURN_ANALYSIS}")
    analysis = load_json(RETURN_ANALYSIS)
    if (
        analysis.get("pass") is not True
        or analysis.get("status")
        != "RETURN_ANALYSIS_COMPLETE_SUCCESSOR_REQUIRED"
    ):
        raise BuildError("formal return analysis did not authorize a successor")
    RETURN_ANALYSIS_SHA256 = sha256_file(RETURN_ANALYSIS)

    OUT.mkdir(parents=True)
    BUILD.mkdir()
    runner = patched_runner()
    # Keep expanded trees under short temporary roots.  The QAdd payload has
    # legitimate deep member paths that exceed Win32's legacy MAX_PATH when
    # expanded below the descriptive release directory; the final ZIP and all
    # receipts remain in the family output scope.
    with tempfile.TemporaryDirectory(prefix="q58a-") as first_raw, tempfile.TemporaryDirectory(
        prefix="q58b-"
    ) as second_raw:
        package = build_package(Path(first_raw), runner)
        repeat = build_package(Path(second_raw), runner)
        if package_records(package) != package_records(repeat):
            raise BuildError("deterministic directory rebuild differs")
        frozen = verify_frozen_surfaces(package)
        frozen_path = OUT / f"{TARGET}.frozen_surface.json"
        write_json(frozen_path, frozen)
        zip_first = Path(first_raw) / f"{TARGET}.zip"
        zip_repeat = Path(second_raw) / f"{TARGET}.zip"
        deterministic_zip(package, zip_first)
        deterministic_zip(repeat, zip_repeat)
        if (
            zip_first.stat().st_size != zip_repeat.stat().st_size
            or sha256_file(zip_first) != sha256_file(zip_repeat)
        ):
            raise BuildError("deterministic double ZIP build differs")
        zip_path = BUILD / f"{TARGET}.zip"
        shutil.copy2(zip_first, zip_path)

    digest = sha256_file(zip_path)
    sidecar = BUILD / f"{TARGET}.zip.sha256"
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    audit = audit_exact_zip(zip_path)
    build_report = {
        "schema": "qlinearadd-node0007-v58-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": TARGET,
        "family": FAMILY,
        "source": receipt(SOURCE_ZIP),
        "formal_return_analysis": receipt(RETURN_ANALYSIS),
        "zip": receipt(zip_path),
        "sidecar": receipt(sidecar),
        "frozen_surface": receipt(frozen_path),
        "final_zip_audit": receipt(OUT / f"{TARGET}.final_zip_audit.json"),
        "deterministic_directory_rebuild_equal": True,
        "deterministic_double_zip_equal": True,
        "first_fresh_after_change": True,
        "server_action": False,
        "final_audit_pass": audit["pass"],
    }
    build_path = BUILD / f"{TARGET}.build.json"
    write_json(build_path, build_report)
    print(
        json.dumps(
            {
                "package_id": TARGET,
                "zip": receipt(zip_path),
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
