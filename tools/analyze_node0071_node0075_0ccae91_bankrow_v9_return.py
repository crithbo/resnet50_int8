#!/usr/bin/env python3
"""Validate and adjudicate the formal node0071 -> node0075 bank-row v9 return."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools/analyze_node0071_node0075_e1fb0f7_native_v3_return.py"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_0cc_bankrow_v9.zip"
)
SOURCE_ROOT = "r5_n71_n75_0cc_bankrow_v9"
RETURN_ROOT = "r5_n71_n75_0cc_bankrow_v9_return"
DEFAULT_RETURN = Path(
    "C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/"
    "2026-08/r5_n71_n75_0cc_bankrow_v9_return.zip"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-0ccae91-bankrow-v9-return-analysis-v1/report.json"
)
CLOUD_IMPACT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-bankrow-relocated-integration-v2/"
    "cloud_rtl_0ccae91_impact_audit.json"
)
EXPECTED_RETURN_BYTES = 150747
EXPECTED_RETURN_SHA256 = (
    "fb1aef2c0699b5115f1e461cbca827a018359288c06cb6024451bc9ba3486482"
)
EXPECTED_SOURCE_SHA256 = (
    "f0034876998f636ea0cdd473f830daed896cc7b315fdb73ab617e59d6f3c8165"
)
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "242abe93ed9d290ff95688d1f4a259e2f349e06b235fde67861221f0ee116350"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


class AnalysisError(RuntimeError):
    pass


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("v3_return_helpers", BASE)
    if spec is None or spec.loader is None:
        raise AnalysisError(f"cannot load helper: {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json_bytes(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise AnalysisError(f"cannot parse {name}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"{name} root differs")
    return value


def load_json_path(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AnalysisError(f"{path} root differs")
    return value


def text(entries: dict[str, bytes], name: str) -> str:
    try:
        return entries[name].decode("utf-8", errors="replace")
    except KeyError as exc:
        raise AnalysisError(f"return member missing: {name}") from exc


def integer(entries: dict[str, bytes], name: str) -> int:
    return int(text(entries, name).strip())


SNAPSHOT_RE = re.compile(
    r"^N75_SNAPSHOT_V2 kind=(?P<kind>\S+) "
    r"time=(?P<time>\d+) cycle=(?P<cycle>\d+) stage=(?P<stage>\d+) "
    r"cfg_start=(?P<cfg_start>\d+) cfg_finish=(?P<cfg_finish>\d+) "
    r"exec=(?P<exec>\d+) finish=(?P<finish>\d+) "
    r"producer_req=(?P<producer_req>\d+) "
    r"producer_wdata=(?P<producer_wdata>\d+) "
    r"producer_finish=(?P<producer_finish>\d+) "
    r"a_req=(?P<a_req>\d+) a_data=(?P<a_data>\d+) "
    r"last_progress=(?P<last_progress>\d+)$",
    re.MULTILINE,
)


def parse_snapshots(observer_log: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for match in SNAPSHOT_RE.finditer(observer_log):
        record: dict[str, Any] = {"kind": match.group("kind")}
        for key, value in match.groupdict().items():
            if key != "kind":
                record[key] = int(value)
        records.append(record)
    return records


def parse_host_progress(host_log: str) -> dict[str, Any]:
    records: list[tuple[int, str]] = []
    for line in host_log.splitlines():
        fields = line.split("\t", 1)
        if len(fields) != 2:
            continue
        try:
            host_ns = int(fields[0])
        except ValueError:
            continue
        records.append((host_ns, fields[1]))
    first_stage1 = next(
        (item for item in records if "stage=1 " in item[1]), None
    )
    last = records[-1] if records else None
    return {
        "record_count": len(records),
        "first_host_ns": records[0][0] if records else None,
        "last_host_ns": last[0] if last else None,
        "observed_wallclock_seconds": (
            (last[0] - records[0][0]) / 1_000_000_000
            if records and last
            else None
        ),
        "first_stage1_host_ns": first_stage1[0] if first_stage1 else None,
        "stage1_observed_wallclock_seconds": (
            (last[0] - first_stage1[0]) / 1_000_000_000
            if first_stage1 and last
            else None
        ),
        "last_line": last[1] if last else None,
    }


def cloud_identity(
    observer_binding: str, cloud_impact: dict[str, Any]
) -> dict[str, Any]:
    prefix = "cloud_rtl_identity_json="
    lines = [
        line[len(prefix) :].strip()
        for line in observer_binding.splitlines()
        if line.startswith(prefix)
    ]
    if len(lines) != 1:
        raise AnalysisError("cloud identity receipt count differs")
    actual = json.loads(lines[0])
    expected = {
        item["path"].replace("code/NDP_rtl/", "rtl/"): item["cloud"]
        for item in cloud_impact["changed_files"]
        if item.get("cloud") is not None
    }
    comparisons = []
    for item in actual.get("actual_files", []):
        exp = expected.get(item["path"])
        comparisons.append(
            {
                "path": item["path"],
                "actual_bytes": item.get("bytes"),
                "actual_sha256": item.get("sha256"),
                "cloud_bytes": exp.get("bytes") if exp else None,
                "cloud_sha256": exp.get("sha256") if exp else None,
                "matches_cloud_commit": bool(
                    exp
                    and item.get("bytes") == exp.get("bytes")
                    and item.get("sha256") == exp.get("sha256")
                ),
            }
        )
    mismatches = [item["path"] for item in comparisons if not item["matches_cloud_commit"]]
    matches = [item["path"] for item in comparisons if item["matches_cloud_commit"]]
    return {
        "receipt_schema": actual.get("schema"),
        "declared_cloud_authority_commit": actual.get("cloud_authority_commit"),
        "compile_exit_status": actual.get("compile_exit_status"),
        "identity_difference_is_simulation_blocker": actual.get(
            "identity_difference_is_simulation_blocker"
        ),
        "actual_file_count": len(comparisons),
        "exact_cloud_match_count": len(matches),
        "exact_cloud_mismatch_count": len(mismatches),
        "exact_cloud_matches": matches,
        "exact_cloud_mismatches": mismatches,
        "comparisons": comparisons,
        "actual_compile_set_fully_bound_to_cloud_commit": not mismatches,
        "impact_classification": (
            "AFFECTED_CAUSAL_CONE_CLOUD_RTL_IMPACT_REVIEW_PENDING"
            if mismatches
            else "EXACT_CLOUD_COMMIT_MATCH"
        ),
        "cloud_access_during_analysis": (
            "UNAVAILABLE_GIT_HTTPS_SEC_E_NO_CREDENTIALS"
        ),
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    helper = load_base()
    return_entries, return_zip_receipt = helper.safe_zip(return_zip, RETURN_ROOT)
    source_entries, source_zip_receipt = helper.safe_zip(SOURCE_ZIP, SOURCE_ROOT)
    errors: list[str] = []

    return_identity = {
        "path": str(return_zip),
        "bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "adjacent_sidecar_present": Path(str(return_zip) + ".sha256").is_file(),
        "transport_basis": "USER_FORMAL_RETURN_PATH_AND_SHA_ATTESTATION",
    }
    source_identity = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "bytes": SOURCE_ZIP.stat().st_size,
        "sha256": sha256(SOURCE_ZIP),
    }
    if return_identity["bytes"] != EXPECTED_RETURN_BYTES:
        errors.append("return_bytes")
    if return_identity["sha256"] != EXPECTED_RETURN_SHA256:
        errors.append("return_sha256")
    if source_identity["sha256"] != EXPECTED_SOURCE_SHA256:
        errors.append("source_sha256")
    for name, receipt in (
        ("return_zip", return_zip_receipt),
        ("source_zip", source_zip_receipt),
    ):
        for gate in (
            "crc_valid",
            "single_root",
            "path_safe",
            "duplicate_free",
            "symlink_free",
        ):
            if not receipt[gate]:
                errors.append(f"{name}:{gate}")

    return_manifest = load_json_bytes(
        return_entries["RETURN_MANIFEST.json"], "RETURN_MANIFEST.json"
    )
    return_allowlist = load_json_bytes(
        return_entries["RETURN_ALLOWLIST.json"], "RETURN_ALLOWLIST.json"
    )
    source_manifest_local = source_entries["TEST_PACKAGE_MANIFEST.json"]
    source_manifest_returned = return_entries["src/TEST_PACKAGE_MANIFEST.json"]
    source_manifest_sha = sha256_bytes(source_manifest_local)
    if source_manifest_sha != EXPECTED_SOURCE_MANIFEST_SHA256:
        errors.append("source_manifest_sha")
    if source_manifest_returned != source_manifest_local:
        errors.append("returned_source_manifest_bytes")
    if (
        return_manifest.get("source_package_manifest_sha256")
        != EXPECTED_SOURCE_MANIFEST_SHA256
    ):
        errors.append("return_source_binding")

    actual_return_records = helper.manifest_records(
        return_entries, {"RETURN_MANIFEST.json"}
    )
    if return_manifest.get("files") != actual_return_records:
        errors.append("return_manifest_exact_set")
    actual_copied = sorted(
        name
        for name in return_entries
        if name not in {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    )
    if return_allowlist.get("copied_exact_set") != actual_copied:
        errors.append("return_allowlist_exact_set")
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        if return_entries[f"src/{name}"] != source_entries[f"workload/{name}"]:
            errors.append(f"source_{name}_bytes")

    package_preflight = load_json_bytes(
        return_entries["e/package_preflight.json"], "package_preflight.json"
    )
    install_preflight = load_json_bytes(
        return_entries["e/install_preflight.json"], "install_preflight.json"
    )
    runtime_d_absent = load_json_bytes(
        return_entries["e/runtime_d_absent.json"], "runtime_d_absent.json"
    )
    if package_preflight.get("status") != "PACKAGE_PREFLIGHT_PASS":
        errors.append("package_preflight")
    if install_preflight.get("status") != "INSTALLED_WORKLOAD_PREFLIGHT_PASS":
        errors.append("install_preflight")
    if runtime_d_absent.get("status") != "RUNTIME_D_ABSENT_PRE_SIM_PASS":
        errors.append("runtime_d_absent")

    compile_exit = integer(return_entries, "e/compile_exit_status.txt")
    run_exit = integer(return_entries, "e/run_exit_status.txt")
    runner_exit = integer(return_entries, "e/runner_exit_status.txt")
    signal_status = text(return_entries, "e/signal_status.txt").strip()
    observer_binding = text(return_entries, "e/observer_binding.txt")
    observer_log = text(return_entries, "log/return_observer.log")
    host_log = text(return_entries, "log/host_progress.log")
    sim_log = text(return_entries, "log/sim.head_tail.log")
    gate = load_json_bytes(
        return_entries["e/SERVER_RESULT_GATE.json"], "SERVER_RESULT_GATE.json"
    )
    cloud = cloud_identity(observer_binding, load_json_path(CLOUD_IMPACT))

    snapshots = parse_snapshots(observer_log)
    exec_start = [item for item in snapshots if item["kind"] == "EXEC_START"]
    heartbeats = [item for item in snapshots if item["kind"] == "HEARTBEAT"]
    stall_records = [
        item
        for item in snapshots
        if item["kind"] == "LONG_RUNNING_HANG_AT_LAST_PROGRESS"
    ]
    final_summaries = [
        item for item in snapshots if item["kind"] == "FINAL_SUMMARY"
    ]
    canonical_records = re.findall(
        r"^N75_CANONICAL_DECISION_V2 .+$", observer_log, re.MULTILINE
    )
    last = snapshots[-1] if snapshots else {}
    stage1_zero_target_counters = all(
        last.get(key) == 0
        for key in (
            "finish",
            "producer_req",
            "producer_wdata",
            "producer_finish",
            "a_req",
            "a_data",
        )
    )
    host = parse_host_progress(host_log)
    preload_pass_count = len(
        re.findall(
            r"\*\*\* PASS: Continuous transfer completed successfully!",
            sim_log,
        )
    )

    reached_stage1 = (
        len(exec_start) == 1
        and last.get("stage") == 1
        and "JSON config: Exec_Base=0x002acc00 Exec_Length=518" in sim_log
        and "Reg Started." in sim_log
        and "INFO: slice start" in sim_log
    )
    if compile_exit != 0:
        errors.append("production_compile")
    if not reached_stage1:
        errors.append("stage1_reachability")
    if preload_pass_count != 177:
        errors.append("preload_pass_count")
    if signal_status != "INT" or run_exit != 125 or runner_exit != 125:
        errors.append("interrupt_receipt")
    if not heartbeats or not stage1_zero_target_counters:
        errors.append("observer_chronology")

    empty_hash = sha256_bytes(b"[]")
    raw_a = gate.get("a_consumer_actual_acceptance", {})
    raw_empty_records = raw_a.get("records", [])
    raw_empty_record_count = sum(
        1
        for item in raw_empty_records
        if item.get("event_count") == 0
        and item.get("ordered_address_sha256") == empty_hash
        and item.get("read_byte_set_sha256") == empty_hash
    )

    dynamic_gates = {
        "producer_downstream_acceptance_to_pass00_ordering": {
            "status": "NOT_REACHED",
            "producer_acceptance_actual": None,
            "pass00_first_read_actual": None,
            "ordering_claim": None,
            "reason": (
                "execution remained in node0071 stage01; stage08 producer "
                "downstream acceptance and node0075 pass00 were not reached"
            ),
        },
        "node0075_a_actual_acceptance": {
            "status": "NOT_REACHED",
            "expected_read_count": 8192,
            "actual_read_count": None,
            "expected_traffic_bytes": 262144,
            "actual_traffic_bytes": None,
            "expected_pass_slice_record_count": 128,
            "actual_pass_slice_hashes": None,
            "raw_gate_zero_event_count": raw_a.get("event_count"),
            "raw_gate_empty_hash_record_count": raw_empty_record_count,
            "raw_gate_zero_promoted_to_actual_acceptance": False,
        },
        "natural_terminal": {
            "status": "NOT_REACHED",
            "expected_stage_count": 32,
            "expected_slice_finish_count": 512,
            "actual_stage_count": 1,
            "actual_slice_finish_count": 0,
            "canonical_record_count": len(canonical_records),
            "final_summary_count": len(final_summaries),
        },
        "formal_d": {
            "status": "NOT_REACHED",
            "expected_count": 144,
            "actual_count": None,
            "missing_count": 144,
            "mismatch_count": None,
            "raw_gate_actual_count": gate.get("formal_readback_actual_count"),
            "raw_gate_mismatch_count": gate.get("mismatch_count"),
            "raw_zero_promoted_to_actual_observation": False,
        },
    }

    observer_blind_boundary = {
        "stage1_qualified_progress_covered": False,
        "why": (
            "v9 monotonic progress counts only cfg/exec/slice-finish, stage08 "
            "producer output, and node0075 stages09-16 A traffic; it contains "
            "no stage01 MSE0/MSE3 Buffer_AG/Memory_AG/RD qualified counters"
        ),
        "stall_record_count": len(stall_records),
        "stall_marker_is_unique_root_cause": False,
        "candidate_matrix": [
            {
                "candidate": "STAGE01_ACTIVE_BUT_V9_OBSERVER_BLIND",
                "discriminator": "qualified stage01 FIFO/request counters advance",
            },
            {
                "candidate": "STAGE01_BUFFER_OR_MEMORY_SUPPLY_STALL",
                "discriminator": (
                    "Buffer_AG/Memory_AG enqueue-dequeue conservation and "
                    "request valid/ready stop at a stable boundary"
                ),
            },
            {
                "candidate": "STAGE01_ACTUAL_RTL_VARIANT_EFFECT",
                "discriminator": (
                    "bind the three mismatching Buffer-path leaves to current "
                    "cloud content, then correlate the same qualified boundary"
                ),
            },
        ],
        "existing_information_gain_successor": {
            "package_name": "r5_n71_gap_v40_lc_supply_conservation_diag",
            "package_path": (
                "artifacts/operator_config_validation/r5-server-test-packages/"
                "r5_n71_gap_v40_lc_supply_conservation_diag.zip"
            ),
            "package_sha256": (
                "7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4"
            ),
            "covers_exact_missing_boundary": True,
            "node0075_duplicate_package_needed_now": False,
        },
    }

    status = (
        "RETURN_ANALYSIS_VALID_STAGE01_PREFIX_UNRESOLVED_EXISTING_GAP_V40_REQUIRED"
        if not errors
        else "RETURN_ANALYSIS_INTEGRITY_OR_ADJUDICATION_FAIL"
    )
    return {
        "schema": "node0071-node0075-0ccae91-bankrow-v9-return-analysis-v1",
        "status": status,
        "valid": not errors,
        "errors": errors,
        "return_identity": return_identity,
        "source_identity": source_identity,
        "receipts": {
            "return_zip": return_zip_receipt,
            "source_zip": source_zip_receipt,
            "return_manifest_exact": (
                return_manifest.get("files") == actual_return_records
            ),
            "return_allowlist_exact": (
                return_allowlist.get("copied_exact_set") == actual_copied
            ),
            "source_manifest_sha256": source_manifest_sha,
            "source_manifest_returned_byte_equal": (
                source_manifest_returned == source_manifest_local
            ),
            "sca_returned_byte_equal": (
                return_entries["src/sca_cfg.json"]
                == source_entries["workload/sca_cfg.json"]
            ),
            "sca_d_returned_byte_equal": (
                return_entries["src/sca_cfg_D.json"]
                == source_entries["workload/sca_cfg_D.json"]
            ),
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "runtime_d_absent": runtime_d_absent,
        },
        "actual_cloud_rtl_identity": cloud,
        "execution": {
            "compile_exit_status": compile_exit,
            "run_exit_status": run_exit,
            "runner_exit_status": runner_exit,
            "signal_status": signal_status,
            "simulator_started": reached_stage1,
            "preload_pass_count": preload_pass_count,
            "exec_base": "0x002acc00",
            "exec_length": 518,
            "snapshot_count": len(snapshots),
            "heartbeat_count": len(heartbeats),
            "exec_start_count": len(exec_start),
            "stall_record_count": len(stall_records),
            "last_snapshot": last,
            "host_progress": host,
        },
        "last_proven_good": (
            "internal receipt/source/SCA/SCA_D exact binding; package/install/"
            "runtime-D preflight pass; production compile=0; 177/177 matrix "
            "preloads pass; Exec_Base 0x002acc00/length518; CONFIG start+finish "
            "and node0071 stage01 EXEC_START observed"
        ),
        "first_divergence": (
            "after node0071 stage01 EXEC_START and before its first slice_finish; "
            "v9 target counters remain zero, but stage01 internal qualified "
            "progress is outside the v9 observer"
        ),
        "hang_root_cause": (
            "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT_AT_NODE0071_STAGE01_"
            "BUFFER_MEMORY_SUPPLY_BOUNDARY"
        ),
        "observer_blind_boundary": observer_blind_boundary,
        "dynamic_gates": dynamic_gates,
        "claim_boundary": {
            "NO_EXPLICIT_BARRIER_CLAIM": True,
            "opcode110_is_barrier": False,
            "identity_difference_blocked_simulation": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": (
                "no natural terminal, no formal D, no node0075 actual A "
                "acceptance, and actual compiled RTL is not fully bound to "
                f"cloud commit {CLOUD_COMMIT}"
            ),
        },
        "server_result_gate_receipt": {
            "status": gate.get("status"),
            "passed": gate.get("passed"),
            "canonical_record_count": gate.get("canonical_record_count"),
            "formal_readback_expected_count": gate.get(
                "formal_readback_expected_count"
            ),
            "formal_readback_actual_count_raw": gate.get(
                "formal_readback_actual_count"
            ),
            "missing_count": gate.get("missing_count"),
            "mismatch_count_raw": gate.get("mismatch_count"),
            "a_event_count_raw": raw_a.get("event_count"),
            "raw_zero_counters_promoted_to_actual_observation": False,
        },
        "successor_decision": {
            "package_release": "NONE",
            "fresh_node0075_package_generated": False,
            "reason": (
                "the exact missing stage01 discriminator already exists in the "
                "current GAP node0071 v40 package; creating another 32-stage "
                "integration package would duplicate the same longest producer "
                "prefix before that prerequisite is adjudicated"
            ),
            "required_next_evidence": (
                "consume the formal r5_n71_gap_v40_lc_supply_conservation_diag "
                "return; only if it does not negate the node0071 causal prefix "
                "may unchanged bank-row v9 qualification resume"
            ),
            "server_upload_run_lease_authorized": False,
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed_rule_ids": [
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
            ],
            "rule_delta_proposal": [],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = analyze(args.return_zip.resolve())
    except Exception as exc:
        report = {
            "schema": "node0071-node0075-0ccae91-bankrow-v9-return-analysis-v1",
            "status": "RETURN_ANALYSIS_FAIL",
            "valid": False,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "valid": report.get("valid"),
                "errors": report.get("errors"),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
