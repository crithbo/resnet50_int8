#!/usr/bin/env python3
"""Validate and adjudicate the formal node0071 -> node0075 v5 return."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools/analyze_node0071_node0075_e1fb0f7_native_v3_return.py"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_e1f_native_v5.zip"
)
RETURN_ROOT = "r5_n71_n75_e1f_native_v5_return"
SOURCE_ROOT = "r5_n71_n75_e1f_native_v5"
DEFAULT_RETURN = Path(
    "C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/"
    "2026-08/r5_n71_n75_e1f_native_v5_return.zip"
)
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-v5-return-analysis/report.json"
)
EXPECTED_RETURN_BYTES = 127533
EXPECTED_RETURN_SHA256 = (
    "bb9b98ddfb70e1b6474ff56bfcd9f6d3253f28bd7390b0c9f760c0e7bfe738c4"
)
EXPECTED_SOURCE_SHA256 = (
    "c2189b3d7f1153f2c47cee6887ea44603e6683ddada77d0eb7d2a57748c3e08b"
)
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "4290fd989364e227dff952bba9bd2e06c0dcdf72607011bff44398abb40d9df0"
)


class AnalysisError(RuntimeError):
    pass


def load_base():
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


def decode_local(byte_addr: int) -> dict[str, int | bool | str]:
    line = byte_addr >> 4
    column = line & 0x3F
    row = (line >> 6) & 0x1FFF
    bank = (line >> 19) & 0x3
    return {
        "address": f"0x{byte_addr:08x}",
        "bank": bank,
        "row": row,
        "row_hex": f"0x{row:04x}",
        "column": column,
        "enabled_row": row < 6144,
    }


def load_json(payload: bytes, name: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise AnalysisError(f"cannot parse {name}") from exc
    if not isinstance(value, dict):
        raise AnalysisError(f"{name} root differs")
    return value


def text(entries: dict[str, bytes], name: str) -> str:
    try:
        return entries[name].decode("utf-8", errors="replace")
    except KeyError as exc:
        raise AnalysisError(f"return member missing: {name}") from exc


def integer(entries: dict[str, bytes], name: str) -> int:
    return int(text(entries, name).strip())


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
        "transport_basis": "USER_ATTESTED_DUPLICATE_UPLOAD_SAME_PATH_ONLY_ONE_CONSUMED",
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

    return_manifest = load_json(
        return_entries["RETURN_MANIFEST.json"], "RETURN_MANIFEST.json"
    )
    return_allowlist = load_json(
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

    compile_exit = integer(return_entries, "e/compile_exit_status.txt")
    run_exit = integer(return_entries, "e/run_exit_status.txt")
    runner_exit = integer(return_entries, "e/runner_exit_status.txt")
    signal_status = text(return_entries, "e/signal_status.txt").strip()
    compile_log = text(return_entries, "log/compile.head_tail.log")
    sim_log = text(return_entries, "log/sim.head_tail.log")
    observer_log = text(return_entries, "log/return_observer.log")
    host_log = text(return_entries, "log/host_progress.log")
    gate = load_json(
        return_entries["e/SERVER_RESULT_GATE.json"], "SERVER_RESULT_GATE.json"
    )
    sca = load_json(return_entries["src/sca_cfg.json"], "src/sca_cfg.json")

    old_scope_errors = [
        leaf
        for leaf in ("clk_sg", "rst_n_sg")
        if re.search(
            rf"(undeclared|undefined|not found|unresolved).{{0,120}}\b{leaf}\b"
            rf"|\b{leaf}\b.{{0,120}}(undeclared|undefined|not found|unresolved)",
            compile_log,
            re.IGNORECASE | re.DOTALL,
        )
    ]
    production_compile_scope_fix_closed = compile_exit == 0 and not old_scope_errors
    if not production_compile_scope_fix_closed:
        errors.append("production_compile_scope_fix")

    exec_base = int(str(sca["Exec_Base"]).replace("_", ""), 16)
    n71_config_base = int(sca["n71_s01_cfg"]["base_addr"], 16)
    n75_config_base = int(sca["n75_a00_cfg"]["base_addr"], 16)
    n75_d_base = int(
        load_json(return_entries["src/sca_cfg_D.json"], "src/sca_cfg_D.json")[
            "n75_d_p00_s00"
        ]["base_addr"],
        16,
    )
    critical_addresses = {
        "node0071_config_first": decode_local(n71_config_base),
        "node0075_config_first": decode_local(n75_config_base),
        "node0075_final_d_first": decode_local(n75_d_base),
        "execplan_first": decode_local(exec_base),
    }
    if any(item["enabled_row"] for item in critical_addresses.values()):
        errors.append("v5_critical_address_expected_disabled_row")

    exec_load_marker = (
        "JSON: Loading matrix[0]" in sim_log
        and "-> 0x01706400" in sim_log
    )
    first_exec_readback_failure = (
        "gradd_n is out of range, bank disable" in sim_log
        and "*** FAIL: Continuous transfer found 518 errors!" in sim_log
    )
    register_started = "Reg Started." in sim_log
    feature_enabled = (
        "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1" in observer_log
    )
    heartbeat_records = re.findall(r"^N75_SNAPSHOT_V2 kind=HEARTBEAT .+$", observer_log, re.M)
    heartbeat_all_stage0 = bool(heartbeat_records) and all(
        all(
            field in line
            for field in (
                "stage=0",
                "cfg_start=0",
                "cfg_finish=0",
                "exec=0",
                "finish=0",
                "producer_req=0",
                "producer_wdata=0",
                "producer_finish=0",
                "a_req=0",
                "a_data=0",
            )
        )
        for line in heartbeat_records
    )
    sim_started = feature_enabled and exec_load_marker
    if not (
        first_exec_readback_failure
        and register_started
        and heartbeat_all_stage0
        and signal_status == "INT"
    ):
        errors.append("dynamic_root_cause_evidence")

    dynamic = {
        "producer_downstream_acceptance": {
            "arrived": False,
            "actual": None,
            "reason": "CONFIG/Start_Comp never entered; observer stayed at stage0",
        },
        "node0075_pass00_first_actual_read": {
            "arrived": False,
            "actual": None,
        },
        "node0075_a_reads": {
            "arrived": False,
            "actual_event_count": None,
            "actual_traffic_bytes": None,
            "actual_per_pass_slice_hashes": None,
            "configured_budget_not_promoted": {
                "event_count": 8192,
                "traffic_bytes": 262144,
            },
        },
        "natural_terminal": {"arrived": False, "actual": None},
        "formal_d": {
            "arrived": False,
            "expected_count": 144,
            "actual_count": None,
            "missing_count": 144,
            "mismatch_count": None,
            "semantic_note": (
                "gate JSON zeros are post-hoc missing/default counters; because "
                "execution never reached the predicate, they are not actual zero observations"
            ),
        },
    }

    status = (
        "RETURN_ANALYSIS_PASS_SUCCESSOR_REQUIRED_BANKROW_RELOCATION"
        if not errors
        else "RETURN_ANALYSIS_INTEGRITY_OR_ADJUDICATION_FAIL"
    )
    return {
        "schema": "node0071-node0075-e1fb0f7-native-v5-return-analysis-v1",
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
        },
        "production_compile": {
            "compile_exit_status": compile_exit,
            "old_bare_scope_error_leafs": old_scope_errors,
            "old_bare_sg_scope_blocker_closed": production_compile_scope_fix_closed,
        },
        "execution": {
            "simulator_started": sim_started,
            "runner_exit_status": runner_exit,
            "run_exit_status": run_exit,
            "signal_status": signal_status,
            "external_interrupt_not_timeout": signal_status == "INT",
            "observer_feature_enabled": feature_enabled,
            "heartbeat_count": len(heartbeat_records),
            "heartbeat_all_stage0": heartbeat_all_stage0,
            "register_started_after_preloads": register_started,
        },
        "first_divergence": {
            "phase": "SCA_PRELOAD_BEFORE_CONFIG_EXECUTION",
            "operation": "first execplan write/readback",
            "address": f"0x{exec_base:08x}",
            "production_log_evidence": {
                "execplan_load_marker": exec_load_marker,
                "gradd_out_of_range": "gradd_n is out of range, bank disable" in sim_log,
                "execplan_readback_error_count": 518,
                "readback_all_x_failure_marker": first_exec_readback_failure,
            },
            "physical_decode": critical_addresses["execplan_first"],
        },
        "physical_address_root_cause": {
            "classification": "MATERIALIZED_CONFIG_ADDRESS_PLACEMENT",
            "functional_rtl_bug_claimed": False,
            "instance_scheduling_or_ordering_reached": False,
            "address_unit_bytes": 16,
            "bank_width": 2,
            "row_width": 13,
            "column_width": 6,
            "enabled_rows_per_bank": 6144,
            "aggregate_capacity_only_check_is_insufficient": True,
            "critical_addresses": critical_addresses,
            "root_cause_unique": True,
        },
        "dynamic_gates": dynamic,
        "server_result_gate_receipt": {
            "status": gate.get("status"),
            "passed": gate.get("passed"),
            "compile_exit_status": gate.get("compile_exit_status"),
            "run_exit_status": gate.get("run_exit_status"),
            "signal_status": gate.get("signal_status"),
            "canonical_record_count": gate.get("canonical_record_count"),
            "formal_readback_expected_count": gate.get("formal_readback_expected_count"),
            "formal_readback_actual_count_raw": gate.get("formal_readback_actual_count"),
            "missing_count": gate.get("missing_count"),
            "mismatch_count_raw": gate.get("mismatch_count"),
            "a_event_count_raw": gate.get("a_consumer_actual_acceptance", {}).get(
                "event_count"
            ),
            "raw_zero_counters_promoted_to_actual_observation": False,
        },
        "lpg_fd_hang": {
            "LPG": (
                "production VCS compile=0; simulator and observer enabled; "
                "returned SCA/SCA_D byte-bound"
            ),
            "FD": (
                "first execplan preload at 0x01706400 -> bank2 row 0x1c19 "
                "disabled; 518-word readback returned X"
            ),
            "HANG_ROOT_CAUSE": (
                "invalid materialized physical bank-row placement prevented valid "
                "execplan/CONFIG loading; observer clock remained live at stage0 until INT"
            ),
        },
        "successor": {
            "required": not errors,
            "unique_repair": (
                "fresh address-bound node0075/integration materialization with D, "
                "all CONFIG and combined execplan in enabled physical bank rows"
            ),
            "observer_change_required": False,
            "functional_rtl_change_required": False,
            "server_upload_run_lease_authorized": False,
        },
        "rule_feedback": {
            "type": "RULE_DELTA_PROPOSAL",
            "confirmed_rule_ids": [
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
                "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            ],
            "proposal": {
                "id": "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
                "reason": (
                    "aggregate capacity accepted v5, but exact bank2 row decode "
                    "landed in a disabled-row hole and blocked execution at preload"
                ),
            },
        },
        "host_progress_contains_same_stage0_heartbeat": (
            "stage=0 cfg_start=0 cfg_finish=0 exec=0 finish=0" in host_log
        ),
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
            "schema": "node0071-node0075-e1fb0f7-native-v5-return-analysis-v1",
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
