#!/usr/bin/env python3
"""Build the fresh QAdd v58-equivalent portable VCD/query successor.

The exact pending v58 ZIP is the immutable functional source.  Only fresh
identity and portable waveform/query/runtime-return surfaces are changed.
This builder performs local deterministic construction and exact-final-ZIP
audits; it never uploads, leases, compiles with VCS, or runs a DUT simulation.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_qlinearadd_node0007_v58_mandatory_vpd as base
from tools.server_waveform_portable_query import catalog_sha


SOURCE = "r5_qadd_n7_tailround_lanephase_qual_v58_mandatory_vpd"
TARGET = "r5_qadd_n7_tailround_lanephase_qual_v59_portable_vcd_query"
FAMILY = "qlinearadd_node0007"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
if not SOURCE_ZIP.is_file():
    SOURCE_ZIP = (
        ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages/superseded"
        / "qlinearadd_node0007"
        / SOURCE
        / f"{SOURCE}.zip"
    )
SOURCE_BYTES = 46652561
SOURCE_SHA256 = "97c5fce6714e9a53937043fb7626d2b462c52ce362147341b834fa33c2b9582d"
OUT = ROOT / "outputs/qlinearadd_node0007_v59_portable_vcd_query_release"
BUILD = OUT / "build"
FORMAL_ANALYSIS = (
    ROOT
    / "outputs/qlinearadd_node0007_v57h_formal_return_1113452"
    / "formal_return_analysis.json"
)
RULE_ID = "CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001"
RULE_EPOCH = "waveform-portable-local-decodability-v1-b0a94cf60d6e"
MANDATORY_RULE_ID = "CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001"
PORTABLE_TOOL = ROOT / "tools/server_waveform_portable_query.py"
LOCAL_ANALYSIS_TOOL = ROOT / "tools/server_waveform_local_analysis.py"
PORTABLE_RUNTIME = ROOT / "tools/qlinearadd_node0007_portable_query_runtime_v59.py"
PORTABLE_PROFILE_MEMBER = "contracts/server_waveform_portable_profile.json"
PORTABLE_CONTRACT_MEMBER = "contracts/server_waveform_portable_runtime_contract.json"
PORTABLE_TOOL_MEMBER = "tools/server_waveform_portable_query.py"
LOCAL_ANALYSIS_MEMBER = "tools/server_waveform_local_analysis.py"
PORTABLE_RUNTIME_MEMBER = (
    "package_tools/qlinearadd_node0007_portable_query_runtime_v59.py"
)
PROVENANCE_MEMBER = "provenance/v58_to_v59_portable_waveform.json"
ZIP_COMPRESSION_LEVEL = 6
WAVE_PLAN_MEMBER = base.WAVE_PLAN_MEMBER
WAVE_CONTROL_MEMBER = base.WAVE_CONTROL_MEMBER
POST_REQUEST_MEMBER = base.POST_REQUEST_MEMBER
POST_CONTRACT_MEMBER = base.POST_CONTRACT_MEMBER
RUNNER_CONTRACT_MEMBER = base.RUNNER_CONTRACT_MEMBER


class BuildError(RuntimeError):
    """A deterministic construction or exact release gate failed."""


def _configure_base() -> None:
    base.SOURCE = SOURCE
    base.TARGET = TARGET
    base.FAMILY = FAMILY
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_BYTES = SOURCE_BYTES
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.OUT = OUT
    base.BUILD = BUILD
    base.RULE_ID = RULE_ID
    base.RULE_EPOCH = RULE_EPOCH
    base.SOURCE_MEMBERS = base.inspect_source()


_configure_base()
SOURCE_MEMBERS = base.SOURCE_MEMBERS

IDENTITY_ONLY_MEMBERS = {
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "workload/runtime/sca_cfg.json",
    "workload/runtime/sca_cfg_D.json",
}
ALLOWED_CHANGED_EXISTING = {
    "PREPARE_AND_RUN.sh",
    POST_REQUEST_MEMBER,
    POST_CONTRACT_MEMBER,
    RUNNER_CONTRACT_MEMBER,
    WAVE_PLAN_MEMBER,
    WAVE_CONTROL_MEMBER,
    "contracts/waveform_policy.json",
    "README.md",
    "TEST_PACKAGE_MANIFEST.json",
}
ADDED_MEMBERS = {
    PORTABLE_PROFILE_MEMBER,
    PORTABLE_CONTRACT_MEMBER,
    PORTABLE_TOOL_MEMBER,
    LOCAL_ANALYSIS_MEMBER,
    PORTABLE_RUNTIME_MEMBER,
    PROVENANCE_MEMBER,
}


def sha256_file(path: Path) -> str:
    return base.sha256_file(path)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: Any) -> None:
    base.write_json(path, value)


def load_json(path: Path) -> dict[str, Any]:
    return base.load_json(path)


def receipt(path: Path) -> dict[str, Any]:
    return base.receipt(path)


def run(command: list[str], *, allowed: set[int] | None = None) -> subprocess.CompletedProcess[str]:
    return base.run(command, allowed=allowed)


def _identity_bytes(name: str) -> bytes:
    data = SOURCE_MEMBERS[name]
    if name in IDENTITY_ONLY_MEMBERS:
        return data.replace(SOURCE.encode(), TARGET.encode())
    return data


def normalize_identity(package: Path) -> None:
    for name in IDENTITY_ONLY_MEMBERS:
        path = package / Path(*PurePosixPath(name).parts)
        data = path.read_bytes()
        if SOURCE.encode() not in data:
            raise BuildError(f"source identity anchor absent: {name}")
        path.write_bytes(data.replace(SOURCE.encode(), TARGET.encode()))


def probe_catalog() -> list[dict[str, Any]]:
    base_path = (
        "tb_NDP_Top_new_phy.u_NDP_Top_new."
        "slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
        "slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU."
        "u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
    )
    rows = [
        ("producer_arm_write_valid", "arm2buf_wvalid", 1),
        ("producer_write_ready", "buf_wreq_ready", 1),
        ("selected_read_request_rw", "mrm2buf_req_rw", 1),
        ("selected_read_clear_mask", "mrm2buf_clear", 8),
        ("valid_bank_clear_mask", "valid_buf_clear", 8),
        ("selected_read_bank_ready", "buf2mrm_rreq_bank_ready", 8),
        ("selected_read_ready", "buf2mrm_rreq_ready", 1),
        ("selected_read_result_valid", "buf2mrm_rvalid", 1),
    ]
    return [
        {
            "candidate_id": candidate_id,
            "hierarchical_path": f"{base_path}.{signal}",
            "width": width,
        }
        for candidate_id, signal, width in rows
    ]


def portable_profile() -> dict[str, Any]:
    generation = SOURCE_MEMBERS[
        "diagnostics/source_bound_observer_generation_report.json"
    ]
    catalog = probe_catalog()
    return {
        "schema": "server-waveform-portable-query-profile-v1",
        "rule_id": RULE_ID,
        "activation": "required_next_fresh",
        "activation_epoch": RULE_EPOCH,
        "raw_vpd": {
            "authoritative": True,
            "existing_dump_vcd_semantics": "VPD",
            "make_arguments": {
                "DUMP_VCD": "1",
                "DUMP_FSDB": "0",
                "TB_DUMP_FSDB": "0",
            },
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
                "source_receipt_sha256": sha256_bytes(generation),
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
            "preserve": [
                "raw_vpd",
                "compile_core",
                "sim_core",
                "signal_core",
                "return_core",
            ],
        },
        "claim_boundary": (
            "Direct unbounded VCD plus every transition for the exact source-bound "
            "QAdd Buffer5 causal candidates; diagnosis remains family-owned."
        ),
    }


def patched_waveform_plan() -> dict[str, Any]:
    plan = json.loads(SOURCE_MEMBERS[WAVE_PLAN_MEMBER])
    plan["package_id"] = TARGET
    plan["dump"]["runtime_search_roots"] = ["run/sim_results"]
    plan["claim_boundary"] = (
        "Authoritative full tb_NDP_Top_new_phy depth-0 unbounded VPD from the "
        "same original attempt as direct VCD/query; no DUT result claim."
    )
    return plan


def _portable_core_entries() -> list[dict[str, Any]]:
    rows = [
        ("evidence/actual_simulator_argv.json", "evidence/actual_simulator_argv.json"),
        ("codex_wave_dump.tcl", "waveforms/codex_wave_dump.tcl"),
        ("run/sim_results/wave.vcd", "waveforms/run/sim_results/wave.vcd"),
        (
            "evidence/portable/source_generation_report.json",
            "waveforms/source_generation_report.json",
        ),
        (
            "evidence/portable/SIGNAL_QUERY_RECEIPT.json",
            "waveforms/SIGNAL_QUERY_RECEIPT.json",
        ),
        (
            "evidence/portable/SIGNAL_QUERY_FAILURE.json",
            "waveforms/SIGNAL_QUERY_FAILURE.json",
        ),
        (
            "evidence/portable/PORTABLE_RUNTIME_REQUEST.json",
            "waveforms/PORTABLE_RUNTIME_REQUEST.json",
        ),
        (
            "evidence/portable/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json",
            "waveforms/PORTABLE_WAVEFORM_RUNTIME_RECEIPT.json",
        ),
        (
            "evidence/portable/PORTABLE_WAVEFORM_VALIDATION.json",
            "waveforms/PORTABLE_WAVEFORM_VALIDATION.json",
        ),
        (
            "evidence/portable/PORTABLE_WAVEFORM_STATUS.json",
            "waveforms/PORTABLE_WAVEFORM_STATUS.json",
        ),
        (
            "evidence/portable/PORTABLE_RETURN_ALLOWLIST.json",
            "waveforms/PORTABLE_RETURN_ALLOWLIST.json",
        ),
    ]
    return [
        {
            "archive": archive,
            "required": False,
            "source": source,
            "source_root": "attempt",
        }
        for source, archive in rows
    ]


def patched_post_request() -> dict[str, Any]:
    request = json.loads(SOURCE_MEMBERS[POST_REQUEST_MEMBER])
    request["package_id"] = TARGET
    request["core_entries"].extend(_portable_core_entries())
    request["claim_boundary"] = (
        "The frozen v58 tail-round return remains independent.  Raw VPD is "
        "authoritative and unbounded; same-attempt direct VCD/query artifacts are "
        "returned when present, and portable failure remains evidence-incomplete "
        "without suppressing raw or compile/sim/signal/core return."
    )
    return request


def patched_runner() -> str:
    runner = SOURCE_MEMBERS["PREPARE_AND_RUN.sh"].decode("utf-8")
    runner = runner.replace(SOURCE, TARGET)
    if SOURCE in runner:
        raise BuildError("runner identity normalization is incomplete")

    anchor = "runtime_dump_tcl=\n"
    replacement = (
        anchor
        + "portable_receipt_rc=0\n"
        + "portable_attempt_relative=\n"
        + "raw_wave_name=wave.vpd\n"
        + "portable_wave_name=wave.vcd\n"
        + f'portable_helper="$package_root/{PORTABLE_RUNTIME_MEMBER}"\n'
        + f'portable_profile="$package_root/{PORTABLE_PROFILE_MEMBER}"\n'
    )
    if runner.count(anchor) != 1:
        raise BuildError("v58 runner portable variable anchor differs")
    runner = runner.replace(anchor, replacement, 1)

    repeated_anchor = (
        'post_sim_request="$package_root/contracts/server_post_sim_return_request.json"\n'
        'source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"\n'
    )
    repeated_replacement = (
        'post_sim_request="$package_root/contracts/server_post_sim_return_request.json"\n'
        f'portable_helper="$package_root/{PORTABLE_RUNTIME_MEMBER}"\n'
        f'portable_profile="$package_root/{PORTABLE_PROFILE_MEMBER}"\n'
        'source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"\n'
    )
    if runner.count(repeated_anchor) != 2:
        raise BuildError("v58 runner resolved portable helper anchor differs")
    runner = runner.replace(repeated_anchor, repeated_replacement)

    finalizer_anchor = "    waveform_receipt_rc=$?\n    export CODEX_PACKAGE_ROOT=\"$package_root\"\n"
    finalizer_replacement = f'''    waveform_receipt_rc=$?
    portable_attempt_relative="install/codex_runs/$package_id/$attempt"
    python3 "$portable_helper" finalize \\
      --profile "$portable_profile" --asset-root "$server_root" \\
      --attempt-root "$run_root" --attempt-relative "$portable_attempt_relative" \\
      --package-id "$package_id" --execution-id "$return_tag" --attempt-id "$attempt" \\
      --exit-kind "$waveform_exit_kind" \\
      $([ "$simulation_started" = true ] && printf %s --simulation-started) \\
      --source-generation-report "$package_root/diagnostics/source_bound_observer_generation_report.json"
    portable_receipt_rc=$?
    if [ "$portable_receipt_rc" -ne 0 ]; then
      mkdir -p -- "$evidence_root/portable"
      printf '{{"schema":"qlinearadd-node0007-portable-waveform-status-v1","diagnostic_status":"DIAGNOSTIC_EVIDENCE_INCOMPLETE","return_must_publish":true,"raw_core_return_preserved":true,"helper_exit_code":%s}}\\n' "$portable_receipt_rc" >"$evidence_root/portable/PORTABLE_WAVEFORM_STATUS.json"
    fi
    export CODEX_PACKAGE_ROOT="$package_root"
'''
    if runner.count(finalizer_anchor) != 1:
        raise BuildError("v58 runner portable finalizer anchor differs")
    runner = runner.replace(finalizer_anchor, finalizer_replacement, 1)

    compile_anchor = (
        '  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=1 DUMP_FSDB=0\n'
        '  TB_DUMP_FSDB=0 "RUN_DIR=$compile_root"\n'
    )
    compile_replacement = (
        '  make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=1 '
        'DUMP_PORTABLE_VCD=1 DUMP_FSDB=0\n'
        '  TB_DUMP_FSDB=0 "RUN_DIR=$compile_root"\n'
    )
    if runner.count(compile_anchor) != 1:
        raise BuildError("v58 runner compile waveform argv anchor differs")
    runner = runner.replace(compile_anchor, compile_replacement, 1)

    dump_anchor = (
        'runtime_dump_tcl="$compile_root/sim_results/codex_wave_dump.tcl"\n'
        'printf \'set CODEX_WAVE_PATH {%s}\\n\' "$compile_root/sim_results/wave.vpd" > "$runtime_dump_tcl" || runner_fail 15 "cannot bind runtime VPD path"\n'
        'cat "$package_root/package_tools/dump_waveform.tcl" >> "$runtime_dump_tcl" || runner_fail 15 "cannot materialize plan-derived VPD control"\n'
    )
    dump_replacement = (
        'runtime_dump_tcl="$run_root/codex_wave_dump.tcl"\n'
        'portable_attempt_relative="install/codex_runs/$package_id/$attempt"\n'
        'python3 "$portable_helper" prepare --profile "$portable_profile" '
        '--attempt-root "$run_root" --attempt-relative "$portable_attempt_relative" '
        '--output-tcl "$runtime_dump_tcl" || runner_fail 15 '
        '"cannot materialize exact dual-format waveform control"\n'
    )
    if runner.count(dump_anchor) != 1:
        raise BuildError("v58 runner dump Tcl anchor differs")
    runner = runner.replace(dump_anchor, dump_replacement, 1)

    display_anchor = (
        "printf 'DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout "
        "--foreground --signal=TERM --kill-after=30s 2h %q' \"$simv\" "
        ">\"$evidence_root/actual_simulator_argv.txt\"\n"
    )
    display_replacement = (
        "printf 'DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 "
        "TB_DUMP_FSDB=0 timeout --foreground --signal=TERM "
        "--kill-after=30s 2h %q' \"$simv\" "
        ">\"$evidence_root/actual_simulator_argv.txt\"\n"
    )
    if runner.count(display_anchor) != 1:
        raise BuildError("v58 runner displayed simulator argv anchor differs")
    runner = runner.replace(display_anchor, display_replacement, 1)

    argv_anchor = "printf '\\n' >>\"$evidence_root/actual_simulator_argv.txt\"\n"
    argv_replacement = argv_anchor + r'''python3 - "$evidence_root/actual_simulator_argv.json" "$server_root" "$simv" "${sim_args[@]}" <<'PY'
import json,pathlib,sys
target=pathlib.Path(sys.argv[1]); cwd=sys.argv[2]; simv=sys.argv[3]; args=sys.argv[4:]
argv=["DUMP_VCD=1","DUMP_PORTABLE_VCD=1","DUMP_FSDB=0","TB_DUMP_FSDB=0","timeout","--foreground","--signal=TERM","--kill-after=30s","2h",simv,*args]
target.write_text(json.dumps(argv,separators=(",",":"))+"\n",encoding="utf-8")
PY
'''
    if runner.count(argv_anchor) != 1:
        raise BuildError("v58 runner actual simulator JSON anchor differs")
    runner = runner.replace(argv_anchor, argv_replacement, 1)

    invoke_anchor = (
        "DUMP_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 timeout --foreground "
        "--signal=TERM --kill-after=30s 2h \"$simv\" \"${sim_args[@]}\" &\n"
    )
    invoke_replacement = (
        "DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0 "
        "timeout --foreground --signal=TERM --kill-after=30s 2h \"$simv\" "
        "\"${sim_args[@]}\" &\n"
    )
    if runner.count(invoke_anchor) != 1:
        raise BuildError("v58 runner simulator invocation anchor differs")
    runner = runner.replace(invoke_anchor, invoke_replacement, 1)

    required = (
        "DUMP_VCD=1",
        "DUMP_PORTABLE_VCD=1",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        PORTABLE_RUNTIME_MEMBER,
        PORTABLE_PROFILE_MEMBER,
        "actual_simulator_argv.json",
        "portable_receipt_rc=$?",
        "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "server_waveform_mandatory_return.py\" collect-runtime",
    )
    if not all(token in runner for token in required):
        raise BuildError("fresh portable runner required token set differs")
    return runner


def runner_contract(runner: str) -> dict[str, Any]:
    contract = json.loads(SOURCE_MEMBERS[RUNNER_CONTRACT_MEMBER])
    contract["package_id"] = TARGET
    contract["runner_path"] = f"{TARGET}/PREPARE_AND_RUN.sh"
    contract["runner_sha256"] = sha256_bytes(runner.encode("utf-8"))
    for name in (
        "portable_receipt_rc",
        "portable_attempt_relative",
        "raw_wave_name",
        "portable_wave_name",
        "portable_helper",
        "portable_profile",
    ):
        if name not in contract["package_owned_variables"]:
            contract["package_owned_variables"].append(name)
    for token in (
        "DUMP_PORTABLE_VCD=1",
        "wave.vcd",
        PORTABLE_RUNTIME_MEMBER,
        PORTABLE_PROFILE_MEMBER,
        "actual_simulator_argv.json",
        "PORTABLE_WAVEFORM_STATUS.json",
    ):
        if token not in contract["return_allowlist_tokens"]:
            contract["return_allowlist_tokens"].append(token)
    return contract


def configure_package(package: Path, runner: str) -> None:
    normalize_identity(package)
    (package / "PREPARE_AND_RUN.sh").write_text(
        runner, encoding="utf-8", newline="\n"
    )
    (package / PORTABLE_TOOL_MEMBER).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PORTABLE_TOOL, package / PORTABLE_TOOL_MEMBER)
    shutil.copy2(LOCAL_ANALYSIS_TOOL, package / LOCAL_ANALYSIS_MEMBER)
    shutil.copy2(PORTABLE_RUNTIME, package / PORTABLE_RUNTIME_MEMBER)

    profile_path = package / PORTABLE_PROFILE_MEMBER
    write_json(profile_path, portable_profile())
    write_json(
        package / PORTABLE_CONTRACT_MEMBER,
        {
            "schema": "qlinearadd-node0007-portable-runtime-contract-v1",
            "package_id": TARGET,
            "rule_id": RULE_ID,
            "rule_change_epoch": RULE_EPOCH,
            "first_fresh_for_profile": True,
            "capture_mode": "DIRECT_VCD_AND_QUERY",
            "actual_make_arguments": {
                "DUMP_VCD": "1",
                "DUMP_PORTABLE_VCD": "1",
                "DUMP_FSDB": "0",
                "TB_DUMP_FSDB": "0",
            },
            "scope": "tb_NDP_Top_new_phy",
            "depth": 0,
            "excluded_scopes": [],
            "profile_member": PORTABLE_PROFILE_MEMBER,
            "profile_sha256": sha256_file(profile_path),
            "portable_tool_member": PORTABLE_TOOL_MEMBER,
            "portable_tool_sha256": sha256_file(PORTABLE_TOOL),
            "local_analysis_member": LOCAL_ANALYSIS_MEMBER,
            "local_analysis_sha256": sha256_file(LOCAL_ANALYSIS_TOOL),
            "runtime_member": PORTABLE_RUNTIME_MEMBER,
            "runtime_sha256": sha256_file(PORTABLE_RUNTIME),
            "authoritative_raw_vpd": True,
            "direct_vcd_unbounded": True,
            "query_events_unbounded": True,
            "every_0_1_x_z_transition": True,
            "byte_cap": None,
            "event_cap": None,
            "time_window_cap": None,
            "truncation": False,
            "sampling": False,
            "size_based_deletion": False,
            "portable_failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "portable_failure_preserves_raw_core_return": True,
        },
    )

    plan_path = package / WAVE_PLAN_MEMBER
    write_json(plan_path, patched_waveform_plan())
    run(
        [
            sys.executable,
            str(base.WAVE_TOOL),
            "render-dump-control",
            "--plan",
            str(plan_path),
            "--output",
            str(package / WAVE_CONTROL_MEMBER),
        ]
    )

    request_path = package / POST_REQUEST_MEMBER
    write_json(request_path, patched_post_request())
    post_contract = json.loads(SOURCE_MEMBERS[POST_CONTRACT_MEMBER])
    post_contract["package_id"] = TARGET
    post_contract["request_sha256"] = sha256_file(request_path)
    post_contract["claim_boundary"] = (
        "Shared raw/core publication plus optional portable evidence entries; "
        "portable failure cannot suppress the formal return."
    )
    write_json(package / POST_CONTRACT_MEMBER, post_contract)
    write_json(package / RUNNER_CONTRACT_MEMBER, runner_contract(runner))

    policy = json.loads(SOURCE_MEMBERS["contracts/waveform_policy.json"])
    policy["package_id"] = TARGET
    policy["portable_profile"] = {
        "rule_id": RULE_ID,
        "activation_epoch": RULE_EPOCH,
        "raw_vpd_authoritative": True,
        "direct_vcd_same_attempt": True,
        "registered_query_receipt": True,
        "portable_failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
    }
    write_json(package / "contracts/waveform_policy.json", policy)

    write_json(
        package / PROVENANCE_MEMBER,
        {
            "schema": "qlinearadd-node0007-v58-to-v59-portable-waveform-v1",
            "source_package": {
                "package_id": SOURCE,
                "bytes": SOURCE_BYTES,
                "sha256": SOURCE_SHA256,
                "path": base.relative(SOURCE_ZIP),
            },
            "rule_id": RULE_ID,
            "activation_epoch": RULE_EPOCH,
            "previous_progress": (
                "v57h passed production compile, entered tail-round stage1 and "
                "localized the first divergence to selected ping-pong required "
                "lanes not becoming ready; v58 preserved that diagnostic under "
                "authoritative full-hierarchy unbounded raw VPD."
            ),
            "current_purpose": (
                "Preserve the v58 lane-phase/read-accept target while adding "
                "same-attempt direct VCD and a complete registered event receipt "
                "for producer, clear, selected-bank-ready and read-result timing."
            ),
            "LAST_PROVEN_GOOD": "C_BUFFER5_MRM_REQUEST_DECODE",
            "FIRST_DIVERGENCE": (
                "C_BUFFER5_ROW_BANK_LANE_VALIDITY_TO_C_BUFFER5_READ_ACCEPT"
            ),
            "changed_surfaces": [
                "fresh identity",
                "portable waveform",
                "registered signal query",
                "runtime/formal return",
            ],
            "frozen": [
                "config",
                "numeric",
                "workload",
                "golden",
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
        + "\n## v59 portable VCD and registered query\n\n"
        + "This fresh v58-equivalent successor retains authoritative full, "
        + "unbounded raw VPD and adds DUMP_PORTABLE_VCD=1 direct standard VCD "
        + "from the same attempt. The source-bound QAdd candidate catalog is "
        + "streamed into a registered receipt containing every ordered 0/1/X/Z "
        + "transition and end state without byte, event or time-window limits. "
        + "Portable failure preserves raw/core return and marks diagnostic "
        + "evidence incomplete. No server action is performed by the package "
        + "builder.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load_json(manifest_path)
    manifest["schema"] = (
        "qlinearadd-node0007-tailround-lanephase-server-package-v59-portable-vcd-query"
    )
    manifest["package_id"] = TARGET
    manifest["status"] = "PACKAGE_READY_NOT_RUN_PENDING_EXACT_FINAL_ZIP_GATES"
    manifest["rule_change_epoch"] = RULE_EPOCH
    manifest["first_fresh_after_change"] = True
    manifest["portable_waveform_gate"] = {
        "rule_id": RULE_ID,
        "make_arguments": (
            "DUMP_VCD=1 DUMP_PORTABLE_VCD=1 DUMP_FSDB=0 TB_DUMP_FSDB=0"
        ),
        "authoritative_raw_vpd": True,
        "direct_vcd_same_attempt": True,
        "scope": "tb_NDP_Top_new_phy",
        "hierarchy_depth": 0,
        "excluded_scopes": [],
        "registered_query_profile": PORTABLE_PROFILE_MEMBER,
        "probe_catalog_sha256": portable_profile()["probe_catalog_sha256"],
        "hard_byte_limit": None,
        "hard_event_limit": None,
        "time_window_limit": None,
        "truncation": False,
        "sampling": False,
        "size_based_deletion": False,
        "failure_status": "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
        "failure_preserves_raw_core_return": True,
    }
    manifest["v59_portable_successor"] = {
        "source_package": SOURCE,
        "source_sha256": SOURCE_SHA256,
        "v58_target_diagnostic_preserved": True,
        "config_numeric_workload_golden_functional_rtl_frozen": True,
        "runtime_formal_return_only": True,
        "server_action": False,
    }
    manifest["active_waveform_receipts"] = {
        **manifest.get("active_waveform_receipts", {}),
        "portable_dispatch_sha256": sha256_file(
            ROOT / "contracts/server_waveform_portable_query_profile_v1.json"
        ),
        "portable_tool_sha256": sha256_file(PORTABLE_TOOL),
        "portable_runtime_sha256": sha256_file(PORTABLE_RUNTIME),
        "activation_record_sha256": sha256_file(
            ROOT
            / ".agents/task_records/20260812_portable_vcd_query_profile_v1_mainline_activation.md"
        ),
    }
    manifest["files"] = {}
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)


def verify_frozen_surfaces(package: Path) -> dict[str, Any]:
    errors: list[str] = []
    exact: list[str] = []
    identity_only: list[str] = []
    allowed_changed: list[str] = []
    for name, old in SOURCE_MEMBERS.items():
        path = package / Path(*PurePosixPath(name).parts)
        if not path.is_file():
            errors.append(f"source member removed: {name}")
            continue
        new = path.read_bytes()
        if name in ALLOWED_CHANGED_EXISTING:
            allowed_changed.append(name)
        elif name in IDENTITY_ONLY_MEMBERS:
            if new.replace(TARGET.encode(), SOURCE.encode()) != old:
                errors.append(f"identity-only member changed beyond identity: {name}")
            else:
                identity_only.append(name)
        elif new != old:
            errors.append(f"frozen source member changed: {name}")
        else:
            exact.append(name)
    actual = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(actual - set(SOURCE_MEMBERS) - ADDED_MEMBERS)
    missing_added = sorted(ADDED_MEMBERS - actual)
    errors.extend(f"unexpected added member: {name}" for name in unexpected)
    errors.extend(f"required portable member absent: {name}" for name in missing_added)
    checks = {
        "source_v58_exact_identity": (
            SOURCE_ZIP.is_file()
            and SOURCE_ZIP.stat().st_size == SOURCE_BYTES
            and sha256_file(SOURCE_ZIP) == SOURCE_SHA256
        ),
        "target_diagnostic_exact_bytes": all(
            (package / Path(*PurePosixPath(name).parts)).read_bytes() == old
            for name, old in SOURCE_MEMBERS.items()
            if name.startswith(base.EXACT_FROZEN_PREFIXES)
        ),
        "config_numeric_workload_golden_frozen": not any(
            error.startswith("frozen source member changed")
            and any(prefix in error for prefix in ("workload/", "validation/", "numeric/", "config/"))
            for error in errors
        ),
        "functional_rtl_frozen": not any("rtl/" in error for error in errors),
        "portable_added_exact_set": not unexpected and not missing_added,
    }
    errors.extend(name for name, passed in checks.items() if passed is not True)
    return {
        "schema": "qlinearadd-node0007-v59-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "exact_member_count": len(exact),
        "identity_only_members": sorted(identity_only),
        "allowed_changed_existing": sorted(allowed_changed),
        "added_portable_members": sorted(ADDED_MEMBERS),
        "claim_boundary": (
            "Only fresh identity and portable waveform/query/runtime-return "
            "surfaces may differ from exact v58."
        ),
    }


def build_package(destination: Path, runner: str) -> Path:
    source = base.safe_extract(SOURCE_ZIP, destination / "source", SOURCE)
    target = destination / TARGET
    source.rename(target)
    configure_package(target, runner)
    frozen = verify_frozen_surfaces(target)
    if frozen.get("pass") is not True:
        raise BuildError(f"staging frozen-surface gate failed: {frozen.get('errors')}")
    return target


def deterministic_zip(package: Path, target: Path) -> None:
    if target.exists():
        raise BuildError(f"refusing to overwrite ZIP: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=ZIP_COMPRESSION_LEVEL,
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            name = path.relative_to(package).as_posix()
            info = zipfile.ZipInfo(f"{TARGET}/{name}", (1980, 1, 1, 0, 0, 0))
            mode = 0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=ZIP_COMPRESSION_LEVEL,
            )
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise BuildError("deterministic ZIP CRC failure")


def _synthetic_vcd(profile: dict[str, Any]) -> str:
    catalog = profile["probe_catalog"]
    parent = catalog[0]["hierarchical_path"].rsplit(".", 1)[0]
    scopes = parent.split(".")
    identifiers = [chr(33 + index) for index in range(len(catalog))]
    lines = [
        "$date 2026-08-12 $end",
        "$version qadd-v59-local-portable-audit $end",
        "$timescale 1ns $end",
    ]
    lines.extend(f"$scope module {scope} $end" for scope in scopes)
    for identifier, candidate in zip(identifiers, catalog):
        leaf = candidate["hierarchical_path"].rsplit(".", 1)[1]
        lines.append(f"$var wire {candidate['width']} {identifier} {leaf} $end")
    lines.extend("$upscope $end" for _ in scopes)
    lines.append("$enddefinitions $end")
    for time_tick, flavor in ((0, "zero"), (5, "x"), (10, "one"), (15, "z")):
        lines.append(f"#{time_tick}")
        for identifier, candidate in zip(identifiers, catalog):
            width = candidate["width"]
            if width == 1:
                value = {"zero": "0", "x": "x", "one": "1", "z": "z"}[flavor]
                lines.append(f"{value}{identifier}")
            else:
                bit = {"zero": "0", "x": "x", "one": "1", "z": "z"}[flavor]
                lines.append(f"b{bit * width} {identifier}")
    return "\n".join(lines) + "\n"


def portable_exact_zip_audit(package: Path) -> dict[str, Any]:
    profile_path = package / PORTABLE_PROFILE_MEMBER
    profile = load_json(profile_path)
    profile_validation = OUT / "exact_zip_audit/portable_profile_validation.json"
    run(
        [
            sys.executable,
            str(package / PORTABLE_TOOL_MEMBER),
            "validate-profile",
            "--profile",
            str(profile_path),
            "--output",
            str(profile_validation),
        ]
    )
    profile_value = load_json(profile_validation)
    if profile_value.get("pass") is not True:
        raise BuildError(f"portable profile gate failed: {profile_value.get('errors')}")

    with tempfile.TemporaryDirectory(prefix="q59-portable-fixture-") as raw:
        asset_root = Path(raw) / "asset"
        attempt_relative = f"install/codex_runs/{TARGET}/a_fixture"
        attempt = asset_root / Path(*PurePosixPath(attempt_relative).parts)
        (attempt / "run/sim_results").mkdir(parents=True)
        (attempt / "evidence/waveform").mkdir(parents=True)
        (attempt / "evidence").mkdir(exist_ok=True)
        (attempt / "run/sim_results/wave.vpd").write_bytes(b"authoritative-vpd-fixture")
        (attempt / "run/sim_results/wave.vcd").write_text(
            _synthetic_vcd(profile), encoding="utf-8", newline="\n"
        )
        run(
            [
                sys.executable,
                str(package / PORTABLE_RUNTIME_MEMBER),
                "prepare",
                "--profile",
                str(profile_path),
                "--attempt-root",
                str(attempt),
                "--attempt-relative",
                attempt_relative,
                "--output-tcl",
                str(attempt / "codex_wave_dump.tcl"),
            ]
        )
        argv = [
            "DUMP_VCD=1",
            "DUMP_PORTABLE_VCD=1",
            "DUMP_FSDB=0",
            "TB_DUMP_FSDB=0",
            "timeout",
            "simv",
        ]
        write_json(attempt / "evidence/actual_simulator_argv.json", argv)
        vpd = attempt / "run/sim_results/wave.vpd"
        write_json(
            attempt / "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
            {
                "schema": "server-waveform-runtime-receipt-v2",
                "package_id": TARGET,
                "execution_id": "exec_fixture",
                "plan_sha256": "b" * 64,
                "simulation_started": True,
                "exit_kind": "NATURAL",
                "waveforms": [
                    {
                        "source_path": "run/sim_results/wave.vpd",
                        "archive_path": "waveforms/run/sim_results/wave.vpd",
                        "bytes": vpd.stat().st_size,
                        "sha256": sha256_file(vpd),
                        "format": "VPD",
                        "completeness": "COMPLETE",
                    }
                ],
                "no_size_limit": True,
                "all_matching_collected": True,
                "pass": True,
                "errors": [],
                "claim_boundary": "local exact-final-ZIP portable fixture",
            },
        )
        run(
            [
                sys.executable,
                str(package / PORTABLE_RUNTIME_MEMBER),
                "finalize",
                "--profile",
                str(profile_path),
                "--asset-root",
                str(asset_root),
                "--attempt-root",
                str(attempt),
                "--attempt-relative",
                attempt_relative,
                "--package-id",
                TARGET,
                "--execution-id",
                "exec_fixture",
                "--attempt-id",
                "a_fixture",
                "--exit-kind",
                "NATURAL",
                "--simulation-started",
                "--source-generation-report",
                str(package / "diagnostics/source_bound_observer_generation_report.json"),
            ]
        )
        portable_dir = attempt / "evidence/portable"
        validation = load_json(portable_dir / "PORTABLE_WAVEFORM_VALIDATION.json")
        query = load_json(portable_dir / "SIGNAL_QUERY_RECEIPT.json")
        status = load_json(portable_dir / "PORTABLE_WAVEFORM_STATUS.json")
        values = [event["value"] for event in query["events"]]
        positive_checks = {
            "shared_profile": profile_value.get("pass") is True,
            "runtime_contract": validation.get("contract_valid") is True,
            "diagnostic_complete": validation.get("diagnostic_complete") is True,
            "registered_query_available": status.get("query_available") is True,
            "candidate_exact_set": query.get("catalog") == profile["probe_catalog"],
            "contiguous_sequence": [event["sequence"] for event in query["events"]]
            == list(range(len(query["events"]))),
            "x_preserved": any("x" in value for value in values),
            "z_preserved": any("z" in value for value in values),
            "no_caps": (
                query["capture"]["no_byte_limit"] is True
                and query["capture"]["no_event_limit"] is True
                and query["capture"]["sampling"] is False
                and query["capture"]["truncation"] is False
            ),
        }
        failure_attempt = asset_root / "install/codex_runs/failure/a_fail"
        shutil.copytree(attempt, failure_attempt)
        (failure_attempt / "run/sim_results/wave.vcd").unlink()
        failure_relative = "install/codex_runs/failure/a_fail"
        run(
            [
                sys.executable,
                str(package / PORTABLE_RUNTIME_MEMBER),
                "prepare",
                "--profile",
                str(profile_path),
                "--attempt-root",
                str(failure_attempt),
                "--attempt-relative",
                failure_relative,
                "--output-tcl",
                str(failure_attempt / "codex_wave_dump.tcl"),
            ]
        )
        raw_failure = load_json(
            failure_attempt / "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json"
        )
        raw_failure["execution_id"] = "exec_failure"
        write_json(
            failure_attempt / "evidence/waveform/WAVEFORM_RUNTIME_RECEIPT.json",
            raw_failure,
        )
        write_json(
            failure_attempt / "evidence/actual_simulator_argv.json",
            argv,
        )
        run(
            [
                sys.executable,
                str(package / PORTABLE_RUNTIME_MEMBER),
                "finalize",
                "--profile",
                str(profile_path),
                "--asset-root",
                str(asset_root),
                "--attempt-root",
                str(failure_attempt),
                "--attempt-relative",
                failure_relative,
                "--package-id",
                TARGET,
                "--execution-id",
                "exec_failure",
                "--attempt-id",
                "a_fail",
                "--exit-kind",
                "TIMEOUT",
                "--simulation-started",
                "--source-generation-report",
                str(package / "diagnostics/source_bound_observer_generation_report.json"),
            ]
        )
        failed_status = load_json(
            failure_attempt / "evidence/portable/PORTABLE_WAVEFORM_STATUS.json"
        )
        negative_checks = {
            "missing_vcd_incomplete": failed_status.get("diagnostic_status")
            == "DIAGNOSTIC_EVIDENCE_INCOMPLETE",
            "missing_vcd_raw_core_preserved": failed_status.get("raw_core_return_preserved")
            is True,
            "missing_vcd_return_publishes": failed_status.get("return_must_publish")
            is True,
        }
        artifact_receipts = {
            "profile": {
                "path": profile_path.relative_to(package).as_posix(),
                "bytes": profile_path.stat().st_size,
                "sha256": sha256_file(profile_path),
            },
            "shared_portable_tool": {
                "path": (package / PORTABLE_TOOL_MEMBER).relative_to(package).as_posix(),
                "bytes": (package / PORTABLE_TOOL_MEMBER).stat().st_size,
                "sha256": sha256_file(package / PORTABLE_TOOL_MEMBER),
            },
            "shared_local_analysis": {
                "path": (package / LOCAL_ANALYSIS_MEMBER).relative_to(package).as_posix(),
                "bytes": (package / LOCAL_ANALYSIS_MEMBER).stat().st_size,
                "sha256": sha256_file(package / LOCAL_ANALYSIS_MEMBER),
            },
            "family_runtime": {
                "path": (package / PORTABLE_RUNTIME_MEMBER).relative_to(package).as_posix(),
                "bytes": (package / PORTABLE_RUNTIME_MEMBER).stat().st_size,
                "sha256": sha256_file(package / PORTABLE_RUNTIME_MEMBER),
            },
        }
    checks = {**positive_checks, **negative_checks}
    report = {
        "schema": "qlinearadd-node0007-v59-portable-query-final-zip-audit-v1",
        "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if passed is not True],
        "checks": checks,
        **artifact_receipts,
        "candidate_count": len(profile["probe_catalog"]),
        "claim_boundary": "Exact final package-local portable plumbing and fixtures only.",
    }
    report_path = OUT / "exact_zip_audit/portable_query_validation.json"
    write_json(report_path, report)
    if report["pass"] is not True:
        raise BuildError(f"portable exact ZIP gate failed: {report['errors']}")
    return report


def first_fresh_contract(
    zip_path: Path,
    reports: dict[str, Path],
    source_path: Path,
    source_value: dict[str, Any],
) -> dict[str, Any]:
    value = base.first_fresh_contract(zip_path, reports, source_path, source_value)
    value["package"]["package_id"] = TARGET
    value["package"]["family"] = "qlinearadd"
    value["rule_change"] = {
        "epoch_id": RULE_EPOCH,
        "rule_ids": [
            MANDATORY_RULE_ID,
            RULE_ID,
            "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
            "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
        ],
        "first_fresh_for_family": True,
        "notification_acknowledged": True,
    }
    return value


def clean_extract_report(zip_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="qadd-v59-clean-") as raw:
        package = base.safe_extract(zip_path, Path(raw) / "extract", TARGET)
        manifest = load_json(package / "TEST_PACKAGE_MANIFEST.json")
        errors: list[str] = []
        if manifest.get("files") != base.package_records(package):
            errors.append("package manifest exact file map mismatch")
        frozen = verify_frozen_surfaces(package)
        errors.extend(frozen.get("errors", []))
        return {
            "schema": "qlinearadd-node0007-v59-exact-final-zip-clean-extract-v1",
            "pass": not errors,
            "errors": errors,
            "zip": receipt(zip_path),
            "manifest_exact": not errors,
            "frozen_surface": frozen,
        }


def audit_exact_zip(zip_path: Path) -> dict[str, Any]:
    audit = OUT / "exact_zip_audit"
    reports_root = audit / "reports"
    reports_root.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="qadd-v59-audit-") as raw:
        package = base.safe_extract(zip_path, Path(raw) / "extract", TARGET)
        clean = clean_extract_report(zip_path)
        clean_path = reports_root / "exact_final_zip_clean_extract.json"
        write_json(clean_path, clean)
        if clean.get("pass") is not True:
            raise BuildError(f"clean extract failed: {clean.get('errors')}")

        runner_path = audit / "runner_return_resilience_validation.json"
        runner_value = base.tool_validation(
            [
                sys.executable,
                str(base.RUNNER_VALIDATOR),
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
                "schema": "qlinearadd-node0007-v59-first-fresh-runner-v1",
                "pass": runner_value.get("pass") is True,
                "errors": runner_value.get("errors", []),
                "six_exit_scenarios": ["normal", "preflight", "compilefail", "HUP", "INT", "TERM"],
                "details": runner_value,
            },
        )

        source_path = audit / "source_bound_final_zip_validation.json"
        run(
            [
                sys.executable,
                str(base.SOURCE_BOUND_TOOL),
                "validate-final-zip",
                "--zip",
                str(zip_path),
                "--report",
                str(source_path),
            ]
        )
        source_value = load_json(source_path)
        if source_value.get("pass") is not True:
            raise BuildError(f"source-bound gate failed: {source_value.get('errors')}")
        source_report = reports_root / "source_bound_logger_collector_parser_roundtrip.json"
        write_json(
            source_report,
            {
                "schema": "qlinearadd-node0007-v59-first-fresh-source-bound-v1",
                "pass": True,
                "errors": [],
                "target_diagnostic_exact_bytes": True,
                "details": source_value,
            },
        )

        post_path = audit / "post_sim_return_validation.json"
        post_value = base.tool_validation(
            [
                sys.executable,
                str(base.POST_SIM_TOOL),
                "validate-final-zip",
                "--zip",
                str(zip_path),
            ],
            post_path,
        )
        scenarios = post_value.get("details", {}).get("scenario_results", {})
        expected_scenarios = {
            "natural_success",
            "natural_success_plugin_failure",
            "simulation_nonzero",
            "idempotent_reentry",
        }
        post_pass = set(scenarios) == expected_scenarios
        post_report = reports_root / "post_sim_return_core_scenarios.json"
        write_json(
            post_report,
            {
                "schema": "qlinearadd-node0007-v59-first-fresh-post-sim-v1",
                "pass": post_pass,
                "errors": [] if post_pass else ["post-sim scenario exact set differs"],
                "details": post_value,
            },
        )
        if not post_pass:
            raise BuildError("post-sim scenario gate failed")

        wave_path = audit / "waveform_mandatory_validation.json"
        wave_value = base.tool_validation(
            [
                sys.executable,
                str(base.WAVE_TOOL),
                "validate-final-zip",
                "--zip",
                str(zip_path),
            ],
            wave_path,
        )
        portable_value = portable_exact_zip_audit(package)
        portable_path = audit / "portable_query_validation.json"

        candidate_checks = {
            "source_bound_4_positive": source_value["semantic_controls"]["positive_count"] == 4,
            "source_bound_8_negative": source_value["semantic_controls"]["negative_count"] == 8,
            "diagnostic_fingerprint_preserved": source_value["diagnostic_semantics_sha256"]
            == "0e1a5c1c4f49b7814c7ee0182461d3e3fcc7c4dba5b5951132ad1e8ccc14fd54",
            "full_hierarchy_unbounded_raw_vpd": wave_value.get("pass") is True,
            "same_attempt_portable_vcd_query": portable_value.get("pass") is True,
            "formal_return_analysis_bound": FORMAL_ANALYSIS.is_file(),
        }
        candidate_path = reports_root / "candidate_discrimination_matrix.json"
        write_json(
            candidate_path,
            {
                "schema": "qlinearadd-node0007-v59-first-fresh-candidate-matrix-v1",
                "pass": all(candidate_checks.values()),
                "errors": [name for name, passed in candidate_checks.items() if not passed],
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
                str(base.FIRST_FRESH_VALIDATOR),
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
        "runner_six_exit": runner_value["pass"],
        "source_bound": source_value["pass"],
        "post_sim": post_value["pass"],
        "mandatory_waveform": wave_value["pass"],
        "portable_query": portable_value["pass"],
        "new_epoch_first_fresh": first_value.get("pass") is True,
        "candidate_matrix": all(candidate_checks.values()),
    }
    errors = [name for name, passed in checks.items() if passed is not True]
    final = {
        "schema": "qlinearadd-node0007-v59-final-zip-audit-v1",
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
            "mandatory_waveform": receipt(wave_path),
            "portable_query": receipt(portable_path),
            "first_fresh": receipt(first_validation_path),
            "formal_return_analysis": receipt(FORMAL_ANALYSIS),
        },
        "previous_progress": (
            "v57h compiled and entered tail-round stage1; v58 preserved the "
            "selected ping-pong/lane-readiness diagnostic under mandatory raw VPD."
        ),
        "current_purpose": (
            "Add same-attempt locally decodable direct VCD and registered complete "
            "events for producer/clear/selected-port-ready timing without changing "
            "the v58 functional or diagnostic target."
        ),
        "claims": {
            "config_modified": False,
            "numeric_modified": False,
            "workload_modified": False,
            "golden_modified": False,
            "functional_rtl_modified": False,
            "target_diagnostic_modified": False,
            "server_action": False,
        },
        "claim_boundary": (
            "Exact local final-ZIP and fixture gates only; no production compile, "
            "simulation, natural terminal, formal D, E3, E4 or E5 claim."
        ),
    }
    final_path = OUT / f"{TARGET}.final_zip_audit.json"
    write_json(final_path, final)
    if errors:
        raise BuildError(f"exact final ZIP audit failed: {errors}")
    return final


def main() -> int:
    if OUT.exists():
        raise BuildError(f"fresh output root required: {OUT}")
    if (
        not SOURCE_ZIP.is_file()
        or SOURCE_ZIP.stat().st_size != SOURCE_BYTES
        or sha256_file(SOURCE_ZIP) != SOURCE_SHA256
    ):
        raise BuildError("exact pending v58 source ZIP identity differs")
    if not FORMAL_ANALYSIS.is_file():
        raise BuildError("formal v57h analysis is absent")
    OUT.mkdir(parents=True)
    BUILD.mkdir()
    runner = patched_runner()
    with tempfile.TemporaryDirectory(prefix="q59a-") as first_raw, tempfile.TemporaryDirectory(
        prefix="q59b-"
    ) as second_raw:
        package = build_package(Path(first_raw), runner)
        repeat = build_package(Path(second_raw), runner)
        if base.package_records(package) != base.package_records(repeat):
            raise BuildError("deterministic directory rebuild differs")
        frozen = verify_frozen_surfaces(package)
        frozen_path = OUT / f"{TARGET}.frozen_surface.json"
        write_json(frozen_path, frozen)
        first_zip = Path(first_raw) / f"{TARGET}.zip"
        second_zip = Path(second_raw) / f"{TARGET}.zip"
        deterministic_zip(package, first_zip)
        deterministic_zip(repeat, second_zip)
        if (
            first_zip.stat().st_size != second_zip.stat().st_size
            or sha256_file(first_zip) != sha256_file(second_zip)
        ):
            raise BuildError("deterministic double ZIP build differs")
        zip_path = BUILD / f"{TARGET}.zip"
        shutil.copy2(first_zip, zip_path)
    digest = sha256_file(zip_path)
    sidecar = BUILD / f"{TARGET}.zip.sha256"
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    audit = audit_exact_zip(zip_path)
    build_report = {
        "schema": "qlinearadd-node0007-v59-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": TARGET,
        "family": FAMILY,
        "source": receipt(SOURCE_ZIP),
        "formal_return_analysis": receipt(FORMAL_ANALYSIS),
        "zip": receipt(zip_path),
        "sidecar": receipt(sidecar),
        "frozen_surface": receipt(OUT / f"{TARGET}.frozen_surface.json"),
        "final_zip_audit": receipt(OUT / f"{TARGET}.final_zip_audit.json"),
        "deterministic_directory_rebuild_equal": True,
        "deterministic_double_zip_equal": True,
        "first_fresh_after_change": True,
        "activation_epoch": RULE_EPOCH,
        "server_action": False,
        "final_audit_pass": audit["pass"],
    }
    build_path = BUILD / f"{TARGET}.build.json"
    write_json(build_path, build_report)
    print(
        json.dumps(
            {
                "package_id": TARGET,
                "status": "PACKAGE_READY_NOT_RUN",
                "zip": receipt(zip_path),
                "final_audit_pass": audit["pass"],
                "server_action": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
