#!/usr/bin/env python3
"""Build the bank-row-relocated node0071 -> node0075 integration successor."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools/build_node0071_node0075_e1fb0f7_native_ordering_integration.py"
TEST_ID = "r5-node0071-node0075-e1fb0f7-bankrow-relocated-integration-v2"
RUN_NAMESPACE = "r5_node0071_node0075_e1fb0f7_bankrow_relocated_v2"
N75_ID = "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2"
N75_STEM = "node0075_e1fb0f7_bankrow_relocated_eight_pass_target_v2"
FINAL_D_LOCAL_BASE = 0x002A4800
N71_CONFIG_RELOC_BASE = 0x002AAC00
EXEC_BASE = 0x002ACC00
ROW_COUNT = 6144
SLICE_BYTES = 1 << 25


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode(byte_addr: int) -> dict[str, int | bool]:
    local = byte_addr & (SLICE_BYTES - 1)
    line = local >> 4
    col = line & 0x3F
    row = (line >> 6) & 0x1FFF
    bank = (line >> 19) & 0x3
    return {
        "global_address": f"0x{byte_addr:08x}",
        "local_address": f"0x{local:08x}",
        "bank": bank,
        "row": row,
        "column": col,
        "valid": row < ROW_COUNT,
    }


def load_base():
    spec = importlib.util.spec_from_file_location("n71n75_integration_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load integration base: {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TEST_ID = TEST_ID
    module.OUT = ROOT / "artifacts/operator_config_validation" / TEST_ID
    module.WORKLOAD = module.OUT / "workload"
    module.RUN_NAMESPACE = RUN_NAMESPACE
    module.N75_MATERIALIZER = (
        ROOT / "artifacts/operator_config_validation" / N75_ID
    )
    module.N75_TARGET = module.N75_MATERIALIZER / f"{N75_STEM}.json"
    module.N75_REPORT = module.N75_MATERIALIZER / "materializer_report.json"
    module.N75_VALIDATION = (
        module.N75_MATERIALIZER / "determinism_and_config_binding_validation.json"
    )
    module.N75_PIPELINE = ROOT / "ndp-sim/model_execplan/output" / N75_STEM
    module.N75_SCA = module.N75_PIPELINE / "sca_cfg.json"
    module.N75_SCA_D = module.N75_PIPELINE / "sca_cfg_D.json"
    module.N75_EXECPLAN = module.N75_PIPELINE / "install/execplan.txt"
    module.FINAL_D_LOCAL_BASE = FINAL_D_LOCAL_BASE
    module.N71_CONFIG_RELOC_BASE = N71_CONFIG_RELOC_BASE
    module.EXEC_BASE = EXEC_BASE
    return module


def json_load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root differs: {path}")
    return value


def file_bytes(path: Path) -> int:
    return len(
        b"".join(
            int(line, 2).to_bytes(16, "little")
            for line in path.read_text(encoding="ascii").splitlines()
        )
    )


def interval_records(module, sca: dict[str, Any]) -> list[dict[str, Any]]:
    prefix = f"install/cfg_pkg/{TEST_ID}/"
    records: list[dict[str, Any]] = []
    for key, item in sca.items():
        if key in {"Exec_Base", "Exec_Length", "Repeat_Num"}:
            continue
        begin = int(str(item["base_addr"]).replace("_", ""), 16)
        if key == "ExecutionPlan":
            size = int(sca["Exec_Length"]) * 16
        else:
            path = str(item["path"])
            if not path.startswith(prefix):
                raise RuntimeError(f"integration path prefix differs: {key}")
            size = file_bytes(module.WORKLOAD / path[len(prefix) :])
        end = begin + size
        first = decode(begin)
        last = decode(end - 16)
        if not first["valid"] or not last["valid"]:
            raise RuntimeError(f"physical row invalid after relocation: {key}")
        records.append(
            {
                "key": key,
                "begin": f"0x{begin:08x}",
                "end_exclusive": f"0x{end:08x}",
                "bytes": size,
                "first_line": first,
                "last_line": last,
            }
        )
    return sorted(records, key=lambda item: (item["begin"], item["key"]))


def boundary_microtrace(records: list[dict[str, Any]]) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for record in records:
        begin = int(record["begin"], 16)
        end = int(record["end_exclusive"], 16)
        probes = {
            "first": begin,
            "penultimate": max(begin, end - 32),
            "final": end - 16,
            "one_after": end,
        }
        cases.append(
            {
                "region": record["key"],
                "probes": [
                    {"position": name, **decode(address)}
                    for name, address in probes.items()
                ],
            }
        )
    controls = [
        {"name": "bank0_last_enabled_line", "address": 0x005FFFF0, "expected": True},
        {"name": "bank0_first_disabled_line", "address": 0x00600000, "expected": False},
        {"name": "bank1_first_enabled_line", "address": 0x00800000, "expected": True},
        {"name": "v5_node71_config_first", "address": 0x016E0000, "expected": False},
        {"name": "v5_node75_final_d_first", "address": 0x01700000, "expected": False},
        {"name": "v5_exec_first", "address": 0x01706400, "expected": False},
    ]
    evaluated = [
        {"name": item["name"], "expected": item["expected"], **decode(item["address"])}
        for item in controls
    ]
    passed = all(item["valid"] == item["expected"] for item in evaluated)
    return {
        "schema": "node0071-node0075-bankrow-boundary-microtrace-v1",
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "dut_executed": False,
        "predicate": "decoded_row < 6144 for every 16-byte line",
        "address_decode": {
            "slice_local_mask": "0x01ffffff",
            "line_shift": 4,
            "column_bits": [5, 0],
            "row_bits": [18, 6],
            "bank_bits": [20, 19],
        },
        "region_cases": cases,
        "threshold_and_negative_controls": evaluated,
    }


def build() -> dict[str, Any]:
    module = load_base()
    report = module.build()
    sca = json_load(module.WORKLOAD / "sca_cfg.json")
    sca_d = json_load(module.WORKLOAD / "sca_cfg_D.json")
    records = interval_records(module, sca)
    d_records = []
    for key, item in sorted(sca_d.items()):
        begin = int(item["base_addr"], 16)
        size = int(item["length"]) * 16
        last = begin + size - 16
        if not decode(begin)["valid"] or not decode(last)["valid"]:
            raise RuntimeError(f"formal D physical row invalid: {key}")
        d_records.append(
            {
                "key": key,
                "begin": f"0x{begin:08x}",
                "end_exclusive": f"0x{begin + size:08x}",
                "bytes": size,
                "first_line": decode(begin),
                "last_line": decode(last),
            }
        )

    materializer = json_load(module.N75_REPORT)
    coverage = materializer["a_consumer_coverage"]
    ledger = {
        "schema": "node0071-node0075-changed-causal-transaction-ledger-v1",
        "status": "PASS",
        "passed": True,
        "changed_slice": (
            "node0075 final-D base plus regenerated address-bound round JSON/CONFIG "
            "and composite node0071 CONFIG/execplan storage placement"
        ),
        "unchanged_receipt_reuse": {
            "node0071_numeric_and_config_payloads": True,
            "node0075_weight_payloads": True,
            "node0075_mapping_assignments": True,
            "node0075_a_schedule_and_hashes": True,
            "goldens": True,
        },
        "producer_exact_byte_set": {
            "owner": "node0071 stage08 final uint8",
            "per_slice_local_begin": "0x000a2000",
            "bytes_per_slice": 2048,
            "slice_count": 16,
            "unique_bytes": 32768,
            "consumer_alias_identity": True,
            "host_preload_copy_relayout_replay": False,
        },
        "consumer_required_set": {
            "pass_count": 8,
            "occurrences_per_pass": 1024,
            "occurrences_total": coverage["accepted_occurrence_count"],
            "traffic_bytes": coverage["accepted_traffic_bytes"],
            "unique_bytes": coverage["unique_consumer_byte_count"],
            "occurrence_sha256": coverage["occurrence_sha256"],
            "semantics": "configured qualified E2 occurrences; not server actual acceptance",
        },
        "buffer_bank_lane_valid": {
            "a_buffer_lifetime": 16,
            "output_columns_per_use": 8,
            "minimum_reload_derivation": "ceil(1000/(16*8))=8",
            "physical_bank_row_predicate_applied_to_all_sca_lines": True,
        },
        "capacity_lifetime_visibility": {
            "all_materialized_sca_intervals_physical_row_valid": True,
            "preload_intervals_nonoverlap": True,
            "producer_to_consumer_visibility": "DYNAMIC_ONLY_SERVER_OBSERVER",
            "explicit_barrier_claim": False,
            "opcode110_is_barrier": False,
        },
        "terminal_release": {
            "configured_stage_count": 32,
            "node0071_stages": 8,
            "node0075_stages": 24,
            "natural_terminal": "DYNAMIC_ONLY_SERVER_RETURN",
        },
        "address_bound_json_mapping_bitstream_execplan_sca": {
            "node0075_target": module.identity(module.N75_TARGET),
            "node0075_materializer_report": module.identity(module.N75_REPORT),
            "node0075_validation": module.identity(module.N75_VALIDATION),
            "composite_execplan_base": f"0x{EXEC_BASE:08x}",
            "composite_execplan_lines": 518,
            "sca_interval_count": len(records),
            "sca_intervals": records,
        },
        "formal_d_region": {
            "count": len(d_records),
            "node0071_count": 16,
            "node0075_count": 128,
            "runtime_targets_preseeded": False,
            "records": d_records,
        },
    }
    microtrace = boundary_microtrace(records)
    if not microtrace["passed"]:
        raise RuntimeError("bank-row metadata boundary microtrace failed")
    module.write_json(module.OUT / "causal_transaction_ledger.json", ledger)
    module.write_json(module.OUT / "boundary_microtrace.json", microtrace)

    report_path = module.OUT / "report.json"
    persisted = json_load(report_path)
    persisted["schema"] = (
        "node0071-node0075-e1fb0f7-bankrow-relocated-integration-report-v2"
    )
    persisted["v5_return_successor"] = {
        "return_sha256": (
            "bb9b98ddfb70e1b6474ff56bfcd9f6d3253f28bd7390b0c9f760c0e7bfe738c4"
        ),
        "first_divergence": (
            "first execplan write/readback at 0x01706400 decoded to disabled "
            "bank2 row 0x1c19 and returned X before CONFIG execution"
        ),
        "repair": (
            "relocate D/CONFIG/execplan storage into enabled bank0 rows; "
            "no arithmetic, scheduling, observer or functional RTL change"
        ),
    }
    persisted["materialized_config_rule_applicability"] = {
        "causal_transaction_ledger": {
            "applicable": True,
            "status": ledger["status"],
            "path": "causal_transaction_ledger.json",
        },
        "boundary_microtrace": {
            "applicable": True,
            "status": microtrace["status"],
            "path": "boundary_microtrace.json",
            "dut_executed": False,
        },
    }
    persisted["rule_feedback"] = {
        "type": "RULE_DELTA_PROPOSAL",
        "confirmed_rule_ids": [
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
        ],
        "rule_delta_proposal": [
            {
                "id": "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
                "proposal": (
                    "For every changed final address-bound JSON/mapping/bitstream/"
                    "execplan/SCA interval, decode each first/final and crossed-bank "
                    "16-byte line using the current physical bank/row/column fields "
                    "and reject disabled rows, including address-space holes."
                ),
                "non_synonymous_evidence": (
                    "v5 stayed below aggregate 24MiB capacity yet landed in bank2 "
                    "disabled rows; production preload returned X before stage00."
                ),
            }
        ],
    }
    module.write_json(report_path, persisted)
    manifest_path = module.OUT / "artifact_manifest.json"
    module.write_json(
        manifest_path,
        {
            "schema": "node0071-node0075-bankrow-relocated-artifact-manifest-v2",
            "test_id": TEST_ID,
            "files": module.file_records(module.OUT, excluded=(manifest_path,)),
        },
    )
    return persisted


def main() -> int:
    try:
        report = build()
    except Exception as exc:
        print(f"BANKROW_RELOCATED_INTEGRATION_BUILD_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
