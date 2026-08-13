#!/usr/bin/env python3
"""Validate exact s4 runner integration with the current FSDB quiescence gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s4"
RULE_ID = "CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runner_errors(text: str, request: dict[str, object]) -> list[str]:
    required = {
        "supervise": '"$quiescence_helper" supervise',
        "quiesce": '"$quiescence_helper" quiesce',
        "subreaper_receipt": 'fsdb_process_tree_receipt.json',
        "sim_time_heartbeat": 'sim_time_heartbeat.jsonl',
        "stable_snapshot_receipt": 'fsdb_quiescence_receipt.json',
        "fresh_execution": '--execution-id "$return_tag"',
        "fresh_attempt": '--attempt-id "$attempt"',
        "attempt_root": '--attempt-root "$run_root"',
        "source_log": '--heartbeat-source "$run_root/c0/sim.log"',
        "heartbeat_regex": "--heartbeat-regex 'CODEX_FSDB_SMOKE_EVENT_V1.*time_tick=([0-9]+)'",
        "timescale": '--timescale 1ps',
        "internal_timeout": '--runtime-timeout-seconds 21600',
        "term_grace": '--term-grace 30',
        "kill_grace": '--kill-grace 10',
        "two_snapshots": '--settle-seconds 2',
        "plateau_window": '--plateau-seconds 300',
        "partial_isolation": 'quiescence_rc',
        "signal_wait": 'wait "$sim_pid" 2>/dev/null',
    }
    errors = [f"missing_runner_token:{name}" for name, token in required.items() if token not in text]
    positions = {
        "supervise": text.find('"$quiescence_helper" supervise'),
        "signal_wait": text.find('wait "$sim_pid" 2>/dev/null'),
        "quiesce": text.find('"$quiescence_helper" quiesce'),
        "wave_collect": text.find('server_waveform_mandatory_return.py" collect-runtime'),
        "post_sim": text.find('server_post_sim_return.py" finalize'),
    }
    if min(positions.values()) < 0:
        errors.append("runner_order_unavailable")
    elif not (positions["quiesce"] < positions["wave_collect"] < positions["post_sim"]):
        errors.append("quiescence_must_precede_waveform_snapshot_and_return_publish")
    core = request.get("core_entries", [])
    sources = {row.get("source") for row in core if isinstance(row, dict)}
    for source in (
        "evidence/fsdb_process_tree_receipt.json",
        "evidence/sim_time_heartbeat.jsonl",
        "evidence/fsdb_quiescence_receipt.json",
    ):
        if source not in sources:
            errors.append(f"return_allowlist_missing:{source}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--reference-helper", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as archive:
        if archive.testzip() is not None:
            errors.append("zip_crc")
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names}
        if roots != {PACKAGE_ID}:
            errors.append("single_root")
        prefix = f"{PACKAGE_ID}/"
        members = {name[len(prefix):]: archive.read(name) for name in names if name.startswith(prefix) and not name.endswith("/")}
    helper = members.get("package_tools/server_fsdb_runtime_quiescence.py", b"")
    reference = args.reference_helper.read_bytes()
    if helper != reference:
        errors.append("embedded_helper_identity_drift")
    try:
        contract = json.loads(members["contracts/server_fsdb_runtime_quiescence.json"])
        request = json.loads(members["contracts/server_post_sim_return_request.json"])
        manifest = json.loads(members["package_manifest.json"])
        runner = members["PREPARE_AND_RUN.sh"].decode("utf-8")
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        errors.append(f"required_member:{exc}")
        contract, request, manifest, runner = {}, {}, {}, ""
    errors.extend(runner_errors(runner, request))
    if contract.get("rule_id") != RULE_ID or contract.get("helper", {}).get("sha256") != digest(reference):
        errors.append("quiescence_contract_identity")
    if contract.get("failure") != "PRESERVE_PARTIAL_RAW_AND_CORE_RETURN_DIAGNOSTIC_EVIDENCE_INCOMPLETE":
        errors.append("failure_isolation_contract")
    frozen = manifest.get("frozen", {})
    if not all(frozen.get(key) is True for key in ("config", "numeric", "workload", "golden", "functional_rtl")):
        errors.append("frozen_surface")
    if manifest.get("formal_operator_successor") is not False:
        errors.append("formal_successor_misclassification")

    # Mutate the exact runner/request one causal mechanism at a time.  Every
    # variant must be rejected by the same integration predicate.
    controls = {}
    mutations = {
        "missing_supervise": (runner.replace('"$quiescence_helper" supervise', '"$quiescence_helper" disabled', 1), request),
        "missing_signal_wait": (runner.replace('wait "$sim_pid" 2>/dev/null', ': # wait removed', 1), request),
        "missing_heartbeat_binding": (runner.replace("--heartbeat-regex 'CODEX_FSDB_SMOKE_EVENT_V1.*time_tick=([0-9]+)'", "", 1), request),
        "missing_stable_snapshot": (runner.replace('"$quiescence_helper" quiesce', '"$quiescence_helper" disabled-quiesce', 1), request),
    }
    bad_request = json.loads(json.dumps(request))
    bad_request["core_entries"] = [row for row in bad_request.get("core_entries", []) if row.get("source") != "evidence/fsdb_quiescence_receipt.json"]
    mutations["return_omits_quiescence"] = (runner, bad_request)
    for name, (variant, variant_request) in mutations.items():
        findings = runner_errors(variant, variant_request)
        controls[name] = {"fail_closed": bool(findings), "findings": findings}
        if not findings:
            errors.append(f"negative_control_did_not_fail:{name}")

    test = subprocess.run(
        [str(args.python), "-m", "unittest", "tests.test_server_fsdb_runtime_quiescence"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if test.returncode != 0:
        errors.append("shared_quiescence_tests")
    report = {
        "schema": "node0004-fsdb-smoke-quiescence-final-zip-validation-v1",
        "package_id": PACKAGE_ID,
        "rule_id": RULE_ID,
        "pass": not errors,
        "errors": errors,
        "zip": {"path": str(args.zip.resolve()), "bytes": args.zip.stat().st_size, "sha256": digest(args.zip.read_bytes())},
        "helper": {"member": "package_tools/server_fsdb_runtime_quiescence.py", "bytes": len(helper), "sha256": digest(helper), "reference_sha256": digest(reference), "exact": helper == reference},
        "runner": {"sha256": digest(runner.encode("utf-8")), "findings": runner_errors(runner, request)},
        "negative_controls": controls,
        "shared_tests": {"command": test.args, "exit": test.returncode, "stdout_tail": test.stdout[-2000:], "stderr_tail": test.stderr[-2000:]},
        "claim_boundary": "Exact helper/runner/return integration and local shared controls only; the first Linux/VCS execution remains the production process-tree and writer-quiescence proof boundary.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
