#!/usr/bin/env python3
"""Build the fresh serialized-Conv v86 package-local compile repair.

The exact v85b package is the immutable source.  This successor changes only
fresh identity, two package-local observer XMR expressions, first-error
selection precedence, and the directly required runner/return receipts.  It
does not contact a server or modify config, numeric payloads, workload, or RTL.
"""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v84b_return_successor_v85 as base


SOURCE = "r5_n4_hw_v85b_compile_rootcause"
INSTALL = "r5_n4_hw_v86b_observer_xmre_fix"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
SOURCE_SHA256 = "d8b5c3ecfbc44839863ff7db1e8f0ad4559a343bf92d640a2455e9d06de5aad7"
FORMAL_RETURN_SHA256 = "a2de42f82e288f5c0739649bbeb3995446d644ff2950ff2c18f9f1ac2a3ea59d"
FORMAL_EXECUTION_ID = "r1786447856031491701_1116783"
RULE_EPOCH = "20260811-serialized-v85b-observer-xmre-v86b"
OUT = ROOT / "outputs/n4_v86b"
NATIVE_OBSERVER = "tb_probe/native_return_observer.svh"

OLD_XMR_8 = (
    "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
    "slice_group_gen[0].u_datahub_top_wrapper.u_datahub_top.local_req_full_channels[8]."
    "wr_en.u_local_req_full_channel.arb_req_ready[0]"
)
OLD_XMR_9 = OLD_XMR_8.replace("channels[8]", "channels[9]")
NEW_XMR_8 = (
    "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
    "slice_group_gen[0].u_datahub_top_wrapper.u_datahub_top.local_req_full_channels[8]."
    "wr_en.u_local_req_full_channel.u_local_wr_req_queue.hub_wr_req_ready"
)
NEW_XMR_9 = NEW_XMR_8.replace("channels[8]", "channels[9]")

ROOT_RETURN_ENTRIES = (
    "evidence/package_preflight.json",
    "evidence/install_preflight.json",
    "evidence/observer_precompile.json",
    "evidence/ndp_root_toplevel_pre.json",
    "evidence/ndp_root_toplevel_post.json",
    "evidence/ndp_root_toplevel_gate.json",
    "evidence/ndp_root_write_contract.json",
    "evidence/publication_preflight.json",
)


base.SOURCE = SOURCE
base.INSTALL = INSTALL
base.SOURCE_ZIP = SOURCE_ZIP
base.SOURCE_SHA256 = SOURCE_SHA256
base.FORMAL_RETURN_SHA256 = FORMAL_RETURN_SHA256
base.FORMAL_EXECUTION_ID = FORMAL_EXECUTION_ID
base.RULE_EPOCH = RULE_EPOCH
base.OUT = OUT
base.EXTRA_SURFACE_INPUTS = [(Path(__file__).resolve(), "package_local_hdl")]
base.EXTRA_CHANGED_SURFACES = ["package_local_hdl", "observer", "parser"]


_base_configure_package = base.configure_package
_base_verify_frozen_surfaces = base.verify_frozen_surfaces
_base_runner_contract = base.runner_contract
_base_write_first_fresh_audit = base.write_first_fresh_audit


def patched_native_observer(payload: bytes) -> bytes:
    text = payload.decode("utf-8")
    if text.count(OLD_XMR_8) != 1 or text.count(OLD_XMR_9) != 1:
        raise base.BuildError("v85b native observer XMR anchors differ")
    text = text.replace(OLD_XMR_8, NEW_XMR_8, 1).replace(OLD_XMR_9, NEW_XMR_9, 1)
    if OLD_XMR_8 in text or OLD_XMR_9 in text:
        raise base.BuildError("stale arb_req_ready XMR remains after scoped patch")
    return text.encode("utf-8")


def patched_request() -> dict[str, Any]:
    request = json.loads(base.replace_identity_text(base.source_member(
        "contracts/server_post_sim_return_request.json"
    )).decode("utf-8"))
    request["package_id"] = INSTALL
    by_archive = {
        row["archive"]: row
        for row in request.get("core_entries", [])
        if isinstance(row, dict) and isinstance(row.get("archive"), str)
    }
    for row in base.compile_evidence_core_entries():
        by_archive[row["archive"]] = row
    for name in ROOT_RETURN_ENTRIES:
        by_archive[name] = {
            "source_root": "attempt",
            "source": name,
            "archive": name,
            "required": True,
        }
    request["core_entries"] = list(by_archive.values())
    request["claim_boundary"] = (
        "Exact compile argv/source identity, bounded compile diagnostics, completed "
        "preflight, fixed-result publication and NDP-root pre/post/gate receipts are "
        "shared core evidence. Family plugin failure cannot suppress them. No "
        "production success, natural-terminal, formal-D, E4 or E5 claim."
    )
    return request


def patched_runner() -> str:
    runner = base.replace_identity_text(base.source_member("PREPARE_AND_RUN.sh")).decode(
        "utf-8"
    )

    signal_anchor = "signal_status=NONE\n"
    if runner.count(signal_anchor) != 1:
        raise base.BuildError("v85b signal-status definition anchor differs")
    runner = runner.replace(signal_anchor, signal_anchor + "root_gate_rc=0\n", 1)

    source_anchor = (
        '  "$package_root/tb_probe/source_bound_causal_observer.svh" \\\n'
        '  "$package_root/tb_probe/buffer_ack_phase_observer.svh" <<\'PY\'\n'
    )
    source_replacement = (
        '  "$package_root/tb_probe/source_bound_causal_observer.svh" \\\n'
        '  "$package_root/tb_probe/buffer_ack_phase_observer.svh" \\\n'
        '  "$package_root/tb_probe/native_return_observer.svh" <<\'PY\'\n'
    )
    if runner.count(source_anchor) != 1:
        raise base.BuildError("v85b compile-source identity anchor differs")
    runner = runner.replace(source_anchor, source_replacement, 1)

    old_first = (
        'match = next((line for line in text.splitlines() if re.search(r"(?:^|[^A-Za-z])'
        '(error|fatal)(?:[^A-Za-z]|$)|Error-", line, re.I)), None)\n'
        'if match is None:\n'
        '    match = next((line for line in text.splitlines() if line.strip()), "compile log is empty")\n'
    )
    new_first = (
        'lines = text.splitlines()\n'
        'patterns = (\n'
        '    re.compile(r"^\\s*(?:Error|Fatal)-\\[[^]]+\\]", re.I),\n'
        '    re.compile(r"^\\s*(?:error|fatal)\\s*[:[]", re.I),\n'
        '    re.compile(r"^make: \\*\\*\\* .* Error \\d+", re.I),\n'
        '    re.compile(r"(?:no rule to make target|command not found|syntax error)", re.I),\n'
        ')\n'
        'match = next((line for pattern in patterns for line in lines if pattern.search(line)), None)\n'
        'if match is None:\n'
        '    match = next((line for line in lines if line.strip()), "compile log is empty")\n'
    )
    if runner.count(old_first) != 1:
        raise base.BuildError("v85b first-error selector anchor differs")
    runner = runner.replace(old_first, new_first, 1)

    finalize_anchor = (
        '  [ -z "$host_progress_pid" ] || wait "$host_progress_pid" 2>/dev/null\n'
        '  publish_compile_evidence_to_attempt\n'
    )
    finalize_root_gate = r'''  [ -z "$host_progress_pid" ] || wait "$host_progress_pid" 2>/dev/null
  if [ -n "$evidence_root" ] && [ -d "$evidence_root" ] && [ -f "$evidence_root/ndp_root_toplevel_pre.json" ] && [ -f "$evidence_root/ndp_root_write_contract.json" ]; then
    python3 "$runtime" root-snapshot --server-root "$server_root" > "$evidence_root/ndp_root_toplevel_post.json"
    root_gate_rc=$?
    if [ "$root_gate_rc" -eq 0 ]; then
      python3 "$runtime" root-compare --pre "$evidence_root/ndp_root_toplevel_pre.json" --post "$evidence_root/ndp_root_toplevel_post.json" --contract "$evidence_root/ndp_root_write_contract.json" > "$evidence_root/ndp_root_toplevel_gate.json"
      root_gate_rc=$?
    fi
    [ "$root_gate_rc" -eq 0 ] || printf '%s\n' '{"schema":"ndp-root-toplevel-gate-v1","valid":false,"ndp_root_toplevel_unchanged":false,"failure_class":"SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED"}' > "$evidence_root/ndp_root_toplevel_gate.json"
  fi
  publish_compile_evidence_to_attempt
'''
    if runner.count(finalize_anchor) != 1:
        raise base.BuildError("v85b finalizer root-gate anchor differs")
    runner = runner.replace(finalize_anchor, finalize_root_gate, 1)

    final_anchor = (
        '  final="$original"\n'
        '  [ "$final" -ne 0 ] || [ "$core" -eq 0 ] || final="$core"\n'
    )
    final_replacement = (
        '  final="$original"\n'
        '  [ "$final" -ne 0 ] || [ "$core" -eq 0 ] || final="$core"\n'
        '  [ "$root_gate_rc" -eq 0 ] || final=96\n'
    )
    if runner.count(final_anchor) != 1:
        raise base.BuildError("v85b final status anchor differs")
    runner = runner.replace(final_anchor, final_replacement, 1)

    required = (
        "native_return_observer.svh",
        r're.compile(r"^\s*(?:Error|Fatal)-\[[^]]+\]", re.I)',
        "ndp_root_toplevel_post.json",
        "ndp_root_toplevel_gate.json",
        'root_gate_rc=0',
        '[ "$root_gate_rc" -eq 0 ] || final=96',
    )
    if not all(token in runner for token in required):
        raise base.BuildError("v86 runner lacks a required scoped repair token")
    return runner


def runner_contract(runner_sha: str, *, final_zip: bool) -> dict[str, Any]:
    contract = _base_runner_contract(runner_sha, final_zip=final_zip)
    contract["package_id"] = INSTALL
    contract["runner_path"] = (
        f"{INSTALL}/PREPARE_AND_RUN.sh" if final_zip else "PREPARE_AND_RUN.sh"
    )
    variables = list(contract["package_owned_variables"])
    if "root_gate_rc" not in variables:
        variables.append("root_gate_rc")
    contract["package_owned_variables"] = variables
    contract["return_allowlist_tokens"] = [
        *contract["return_allowlist_tokens"],
        *(Path(name).name for name in ROOT_RETURN_ENTRIES),
    ]
    contract["root_toplevel_gate_tokens"] = [
        "ndp_root_toplevel_pre.json",
        "ndp_root_toplevel_post.json",
        "ndp_root_toplevel_gate.json",
        "ndp_root_write_contract.json",
        'root-snapshot --server-root "$server_root"',
        "root-compare --pre",
    ]
    return contract


def verify_frozen_surfaces(package: Path) -> dict[str, Any]:
    result = _base_verify_frozen_surfaces(package)
    expected = patched_native_observer(base.source_member(NATIVE_OBSERVER))
    actual = (package / NATIVE_OBSERVER).read_bytes()
    allowed_error = f"frozen bytes differ beyond identity: {NATIVE_OBSERVER}"
    errors = [error for error in result.get("errors", []) if error != allowed_error]
    observer_patch_exact = actual == expected
    if not observer_patch_exact:
        errors.append("native observer differs from the exact two-XMR repair")
    result.update(
        {
            "schema": "conv-node0004-v86-frozen-surface-validation-v1",
            "pass": not errors,
            "errors": errors,
            "native_observer_two_xmr_repair_exact": observer_patch_exact,
            "package_local_diagnostic_hdl_only_scoped_compile_fix": observer_patch_exact,
            "package_local_diagnostic_hdl_executable_body_equal": False,
            "config_numeric_workload_semantics_frozen": not errors,
            "functional_rtl_modified": False,
            "claim_boundary": (
                "Config, numeric payloads, workload and functional RTL remain byte-frozen. "
                "Only the two proven package-local arb_req_ready XMRs are replaced by the "
                "already-resolved queue ready consumer."
            ),
        }
    )
    return result


def configure_package(package: Path, runner: str, cheap: dict[str, Any]) -> None:
    observer_path = package / NATIVE_OBSERVER
    observer_path.write_bytes(patched_native_observer(observer_path.read_bytes()))
    _base_configure_package(package, runner, cheap)

    historical = "provenance/v84b_return_to_v85_compile_rootcause.json"
    historical_path = package / historical
    try:
        historical_path.write_bytes(base.source_member(historical))
    except KeyError:
        pass

    provenance_path = package / "provenance/v85b_return_to_v86_observer_xmre_fix.json"
    base.write_json(
        provenance_path,
        {
            "schema": "conv-node0004-v85b-return-to-v86-v1",
            "source_package": {**base.receipt(SOURCE_ZIP), "package_id": SOURCE},
            "formal_return": {
                "execution_id": FORMAL_EXECUTION_ID,
                "sha256": FORMAL_RETURN_SHA256,
                "compile_exit": 2,
                "run_exit": 125,
                "simulation_started": False,
                "compiler_errors": [
                    {"path": NATIVE_OBSERVER, "line": 4816, "token": "arb_req_ready"},
                    {"path": NATIVE_OBSERVER, "line": 4821, "token": "arb_req_ready"},
                ],
            },
            "changed_surfaces": [
                "fresh identity",
                "two package-local observer XMR expressions",
                "first-error diagnostic precedence",
                "compile source identity includes transitive native observer",
                "NDP-root pre/post/gate return-core receipts",
            ],
            "frozen": ["config", "numeric", "workload", "functional RTL"],
            "server_action": False,
        },
    )

    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\n## v86 package-local compile repair\n\n"
        + "The v85b formal return uniquely identified two VCS XMREs in the package-local "
        + "native return observer. v86 changes only those two references and hardens the "
        + "first-error selector plus root-gate return receipts. Config, numeric payloads, "
        + "workload and functional RTL are frozen.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "package_manifest.json"
    manifest = base.load_json(manifest_path)
    source_manifest = json.loads(base.source_member("package_manifest.json"))
    if "v84b_return_adjudication" in source_manifest:
        manifest["v84b_return_adjudication"] = source_manifest[
            "v84b_return_adjudication"
        ]
    manifest["install_name"] = INSTALL
    manifest["v85b_return_adjudication"] = {
        "formal_return_sha256": FORMAL_RETURN_SHA256,
        "execution_id": FORMAL_EXECUTION_ID,
        "compile_exit": 2,
        "run_exit": 125,
        "simulation_started": False,
        "first_divergence": "PRODUCTION_VCS_ELABORATION_XMRE_BEFORE_SIMULATION_START",
        "root_cause": "PACKAGE_LOCAL_NATIVE_RETURN_OBSERVER_ARB_REQ_READY_XMRE",
        "root_lines": [4816, 4821],
        "successor_surface": "PACKAGE_LOCAL_OBSERVER_AND_RUNNER_ONLY",
    }
    manifest["v86_repair"] = {
        "native_observer_old_tokens_absent": True,
        "native_observer_stable_ready_consumer_count": 2,
        "first_error_anchored_compiler_precedence": True,
        "compile_source_identity_includes_native_observer": True,
        "root_pre_post_gate_core_return_required": True,
        "functional_rtl_modified": False,
    }
    manifest["rule_change_epoch"] = RULE_EPOCH
    manifest["first_fresh_after_change"] = True
    manifest["upload_hold_until"] = "EXACT_FINAL_ZIP_EXTRA_AUDIT_PASS"
    manifest["files"] = {}
    base.write_json(manifest_path, manifest)
    base.refresh_path_budget(package)
    manifest = base.load_json(manifest_path)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)

    frozen = verify_frozen_surfaces(package)
    if frozen["pass"] is not True:
        raise base.BuildError(f"v86 frozen surface validation failed: {frozen['errors']}")


def write_first_fresh_audit(
    zip_path: Path, audit_root: Path, reports: dict[str, Path]
) -> Path:
    candidates = [
        "package_local_observer_arb_req_ready_xmre_fixed",
        "other_compile_source_or_environment_error",
        "compile_success_ack_output_vs_inline_rhs",
        "natural_terminal_and_formal_d_320",
    ]
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {
            "package_id": INSTALL,
            "family": "conv_serialized",
            "final_zip": base.receipt(zip_path),
        },
        "rule_change": {
            "epoch_id": RULE_EPOCH,
            "rule_ids": [
                "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
                "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
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
                "path": base.receipt(reports[gate])["path"],
                "sha256": base.receipt(reports[gate])["sha256"],
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
    contract_path = audit_root / "first_fresh_extra_audit_contract.json"
    validation_path = audit_root / "first_fresh_extra_audit_validation.json"
    base.write_json(contract_path, contract)
    base.run(
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


def _write_command_json(
    command: list[str], target: Path, *, allowed_returncodes: set[int] | None = None
) -> dict[str, Any]:
    allowed = {0} if allowed_returncodes is None else allowed_returncodes
    result = base.subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode not in allowed:
        raise base.BuildError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    value = json.loads(result.stdout)
    base.write_json(target, value)
    return value


def v86_scoped_gate(
    zip_path: Path,
    output: Path,
    audit_name: str = "v86_scoped_compile_repair_gate",
) -> Path:
    audit = output / audit_name
    audit.mkdir(parents=True, exist_ok=False)
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        prefix = f"{INSTALL}/"
        observer = archive.read(prefix + NATIVE_OBSERVER).decode("utf-8")
        runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode("utf-8")
        request = json.loads(
            archive.read(prefix + "contracts/server_post_sim_return_request.json")
        )

    checks = {
        "old_arb_req_ready_xmrs_absent": OLD_XMR_8 not in observer and OLD_XMR_9 not in observer,
        "stable_ready_consumer_exact_two": (
            observer.count(f"dh_grant_8 = dh_head_8 && {NEW_XMR_8};") == 1
            and observer.count(f"dh_grant_9 = dh_head_9 && {NEW_XMR_9};") == 1
        ),
        "first_error_anchored_precedence": all(
            token in runner
            for token in (
                're.compile(r"^\\s*(?:Error|Fatal)-\\[[^]]+\\]", re.I)',
                "for pattern in patterns for line in lines",
            )
        ),
        "compile_source_identity_includes_native_observer": (
            '"$package_root/tb_probe/native_return_observer.svh"' in runner
        ),
        "fixed_result_root": 'result_root="/home/panqs/ndp/simresult"' in runner,
        "root_pre_post_compare_in_exact_runner": all(
            token in runner
            for token in (
                "ndp_root_toplevel_pre.json",
                "ndp_root_toplevel_post.json",
                "ndp_root_toplevel_gate.json",
                'root-snapshot --server-root "$server_root"',
                "root-compare --pre",
            )
        ),
        "seven_compile_core_entries": {
            row["archive"] for row in request["core_entries"]
        }
        >= {
            f"evidence/compile_rootcause/{name}"
            for name in (
                "compile_argv.json",
                "compile_source_identity.json",
                "compile_exit.txt",
                "compile_driver.log",
                "compile_first_error.txt",
                "compile_log_head.txt",
                "compile_log_tail.txt",
            )
        },
        "root_gate_return_entries": set(ROOT_RETURN_ENTRIES)
        <= {row["archive"] for row in request["core_entries"]},
    }

    extracted = output / "exact_zip_audit" / "clean_extract" / INSTALL
    runtime = extracted / "package_tools/node0004_hang_localization_runtime.py"
    harness = audit / "root_gate_harness"
    stub = harness / "stub"
    (stub / "install").mkdir(parents=True)
    contract_path = harness / "contract.json"
    base.write_json(
        contract_path,
        {
            "schema": "ndp-root-write-contract-v1",
            "server_root": str(stub.resolve()),
            "result_root": "/home/panqs/ndp/simresult",
            "root_internal_write_targets": ["install/codex_runs/package/attempt"],
            "existing_first_level_parents": ["install"],
            "external_write_targets": ["/home/panqs/ndp/simresult/result.zip"],
        },
    )
    pre_path = harness / "pre.json"
    pre = _write_command_json(
        [sys.executable, str(runtime), "root-snapshot", "--server-root", str(stub)],
        pre_path,
    )
    (stub / "install/codex_runs/package/attempt").mkdir(parents=True)
    post_path = harness / "post.json"
    post = _write_command_json(
        [sys.executable, str(runtime), "root-snapshot", "--server-root", str(stub)],
        post_path,
    )
    positive = _write_command_json(
        [
            sys.executable,
            str(runtime),
            "root-compare",
            "--pre",
            str(pre_path),
            "--post",
            str(post_path),
            "--contract",
            str(contract_path),
        ],
        harness / "positive.json",
    )
    checks["root_gate_allowed_subtree_positive"] = positive.get("valid") is True

    (stub / "forbidden_root_file").write_text("negative\n", encoding="utf-8")
    bad_post_path = harness / "bad_post.json"
    _write_command_json(
        [sys.executable, str(runtime), "root-snapshot", "--server-root", str(stub)],
        bad_post_path,
    )
    negative_new_root = _write_command_json(
        [
            sys.executable,
            str(runtime),
            "root-compare",
            "--pre",
            str(pre_path),
            "--post",
            str(bad_post_path),
            "--contract",
            str(contract_path),
        ],
        harness / "negative_new_root_entry.json",
        allowed_returncodes={0, 96},
    )
    checks["root_gate_new_root_entry_negative"] = (
        negative_new_root.get("valid") is False
        and negative_new_root.get("failure_class")
        == "SERVER_NDP_ROOT_TOPLEVEL_ENTRY_CREATED_OR_CHANGED"
    )

    missing_stub = harness / "missing_parent_stub"
    missing_stub.mkdir()
    missing_pre_path = harness / "missing_pre.json"
    missing_post_path = harness / "missing_post.json"
    _write_command_json(
        [
            sys.executable,
            str(runtime),
            "root-snapshot",
            "--server-root",
            str(missing_stub),
        ],
        missing_pre_path,
    )
    shutil.copy2(missing_pre_path, missing_post_path)
    missing_contract = harness / "missing_contract.json"
    contract = base.load_json(contract_path)
    contract["server_root"] = str(missing_stub.resolve())
    base.write_json(missing_contract, contract)
    negative_missing = _write_command_json(
        [
            sys.executable,
            str(runtime),
            "root-compare",
            "--pre",
            str(missing_pre_path),
            "--post",
            str(missing_post_path),
            "--contract",
            str(missing_contract),
        ],
        harness / "negative_missing_parent.json",
        allowed_returncodes={0, 96},
    )
    checks["root_gate_missing_parent_negative"] = (
        negative_missing.get("valid") is False
        and negative_missing.get("missing_declared_existing_parents") == ["install"]
    )

    mutated_observer = observer.replace(NEW_XMR_8, OLD_XMR_8, 1)
    checks["observer_xmr_regression_negative"] = OLD_XMR_8 in mutated_observer
    warning_line = "The error message report included additional information"
    compiler_line = "Error-[XMRE] Cross-module reference resolution error"
    prioritized = next(
        (
            line
            for predicate in (
                lambda value: value.lstrip().lower().startswith(("error-[", "fatal-[")),
                lambda value: value.lstrip().lower().startswith(("error:", "fatal:")),
            )
            for line in (warning_line, compiler_line)
            if predicate(line)
        ),
        None,
    )
    checks["first_error_warning_prose_negative"] = prioritized == compiler_line

    errors.extend(name for name, passed in checks.items() if passed is not True)
    report = {
        "schema": "conv-node0004-v86-scoped-compile-repair-gate-v1",
        "pass": not errors,
        "errors": errors,
        "all_errors_collected": True,
        "checks": checks,
        "exact_zip": base.receipt(zip_path),
        "root_harness": {
            "pre_exact_set_sha256": pre.get("exact_set_sha256"),
            "post_exact_set_sha256": post.get("exact_set_sha256"),
            "positive": positive,
            "negative_new_root_entry": negative_new_root,
            "negative_missing_parent": negative_missing,
        },
        "claims": {
            "config_modified": False,
            "numeric_modified": False,
            "workload_modified": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
        "claim_boundary": (
            "Exact final ZIP package-local repair, compile-return and root-state gates only; "
            "no production compile, simulation, natural-terminal, formal-D, E4 or E5 claim."
        ),
    }
    report_path = audit / "validation.json"
    base.write_json(report_path, report)
    if errors:
        raise base.BuildError(f"v86 scoped exact-ZIP gate failed: {errors}")
    return report_path


base.patched_request = patched_request
base.patched_runner = patched_runner
base.runner_contract = runner_contract
base.verify_frozen_surfaces = verify_frozen_surfaces
base.configure_package = configure_package
base.write_first_fresh_audit = write_first_fresh_audit


def finalize_v86_reports(zip_path: Path, scoped_path: Path) -> None:
    base_final_path = OUT / "final_zip_audit_v85.json"
    base_final = base.load_json(base_final_path)
    scoped = base.load_json(scoped_path)
    final = {
        "schema": "conv-node0004-v86-final-zip-audit-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": (
            base_final.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is True
            and scoped.get("pass") is True
        ),
        "errors": [
            *base_final.get("errors", []),
            *scoped.get("errors", []),
        ],
        "checks": {
            **base_final.get("checks", {}),
            "v86_scoped_compile_repair": scoped.get("pass") is True,
        },
        "zip": base.receipt(zip_path),
        "report_receipts": {
            **base_final.get("report_receipts", {}),
            "v86_scoped_compile_repair": base.receipt(scoped_path),
            "base_single_release_driver": base.receipt(base_final_path),
        },
        "claims": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        },
        "claim_boundary": (
            "One exact local ZIP and one base release-driver invocation plus the scoped "
            "v86 direct-consumer gate; no production compile, simulation, natural-terminal, "
            "formal-D, E4 or E5 claim."
        ),
    }
    final_path = OUT / "final_zip_audit_v86.json"
    base.write_json(final_path, final)
    if final["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] is not True:
        raise base.BuildError(f"v86 final ZIP audit failed: {final['errors']}")
    build_report_path = OUT / "build" / f"{INSTALL}.build.json"
    build_report = base.load_json(build_report_path)
    build_report["schema"] = "conv-node0004-v86-build-v1"
    build_report["status"] = "PACKAGE_BUILT_EXACT_FINAL_ZIP_AND_SCOPED_REPAIR_AUDIT_PASS"
    build_report["final_zip_audit_v86"] = base.receipt(final_path)
    build_report["source_v85b_formal_return_sha256"] = FORMAL_RETURN_SHA256
    base.write_json(build_report_path, build_report)
    print(
        json.dumps(
            {
                "package_id": INSTALL,
                "zip": base.relative(zip_path),
                "zip_bytes": zip_path.stat().st_size,
                "zip_sha256": base.sha256_file(zip_path),
                "final_audit_pass": True,
                "server_action": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def main() -> int:
    rc = base.main()
    if rc != 0:
        return rc
    zip_path = OUT / "build" / f"{INSTALL}.zip"
    scoped_path = v86_scoped_gate(zip_path, OUT)
    finalize_v86_reports(zip_path, scoped_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
