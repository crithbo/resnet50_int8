#!/usr/bin/env python3
"""Adjudicate exact MSE4 descriptor/data unit flow from generated live events."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_row(line: str) -> dict[str, str] | None:
    if not line.startswith("CODEX_PROBE_V1 "):
        return None
    result: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--log", required=True, type=Path)
    cli.add_argument("--contract", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    specs = {row["boundary_id"]: row for row in contract["boundaries"]}
    enabled: set[str] = set()
    rows: dict[str, list[dict[str, object]]] = {key: [] for key in specs}
    errors: list[str] = []
    wrong_instance_rows = 0
    raw_rows = 0
    for line_number, line in enumerate(args.log.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        row = parse_row(line)
        if row is None or row.get("boundary") not in specs:
            continue
        raw_rows += 1
        boundary = row["boundary"]
        spec = specs[boundary]
        if row.get("instance") != spec["expected_instance"]:
            wrong_instance_rows += 1
            continue
        if row.get("kind") == "ENABLED":
            enabled.add(boundary)
            continue
        if row.get("kind") != "EVENT":
            continue
        payload = row.get("payload", "")
        width = row.get("payload_width")
        known = row.get("payload_known")
        if known != "1" or not payload or any(char not in "0123456789abcdefABCDEF" for char in payload):
            errors.append(f"line {line_number}: non-binary-known payload")
            continue
        if width != str(spec["payload_width_bits"]):
            errors.append(f"line {line_number}: payload width differs")
            continue
        try:
            time = int(row["time"], 0)
            value = int(payload, 16)
        except (KeyError, ValueError):
            errors.append(f"line {line_number}: malformed time/payload")
            continue
        rows[boundary].append({"line": line_number, "time": time, "payload": payload, "value": value})

    missing_enabled = sorted(set(specs) - enabled)
    if missing_enabled:
        errors.append(f"missing enabled boundaries: {missing_enabled}")
    descriptor = rows["mse4_descriptor_accept"]
    data = rows["mse4_buffer_data_accept"]
    memag = rows["mse4_memag_output_accept"]
    wdata = rows["mse4_wdata_output_accept"]
    finish = rows["mse4_slice_finish"]
    unit = int(contract["expected_unit_elements"])
    delta = len(data) - len(descriptor)
    data_after_last_descriptor = bool(descriptor and data and data[-1]["time"] > descriptor[-1]["time"])
    if errors or not descriptor or not data or not memag:
        decision = "EVIDENCE_INCOMPLETE"
        matching: list[str] = []
        exit_code = 1
    elif finish:
        decision = "MSE4_SLICE_FINISH_OBSERVED"
        matching = ["natural_finish"]
        exit_code = 0
    elif delta > 0 and data_after_last_descriptor:
        decision = "MSE4_BUFFER_DATA_OUTRUNS_DESCRIPTOR_PRODUCTION"
        matching = ["address_descriptor_ends_before_buffer_data"]
        exit_code = 0
    elif delta == 0:
        decision = "MSE4_DESCRIPTOR_DATA_BALANCED_TERMINAL_ELSEWHERE"
        matching = ["descriptor_data_balanced"]
        exit_code = 0
    else:
        decision = "EVIDENCE_INCOMPLETE"
        matching = []
        exit_code = 1
    result = {
        "schema": "conv-native-four-lane-p38-mse4-join-decision-v1",
        "decision": decision,
        "matching_candidate_ids": matching,
        "errors": errors,
        "raw_boundary_record_count": raw_rows,
        "wrong_instance_rows_ignored": wrong_instance_rows,
        "missing_enabled_boundaries": missing_enabled,
        "counts": {"memag_output": len(memag), "descriptor": len(descriptor), "buffer_data": len(data), "wdata_output": len(wdata), "slice_finish": len(finish)},
        "descriptor_minus_data_delta": len(descriptor) - len(data),
        "data_minus_descriptor_delta": delta,
        "data_after_last_descriptor": data_after_last_descriptor,
        "last_times": {
            "memag_output": memag[-1]["time"] if memag else None,
            "descriptor": descriptor[-1]["time"] if descriptor else None,
            "buffer_data": data[-1]["time"] if data else None,
            "wdata_output": wdata[-1]["time"] if wdata else None,
            "slice_finish": finish[-1]["time"] if finish else None,
        },
        "expected_unit_elements": unit,
        "all_descriptor_payloads_binary_known": bool(descriptor),
        "all_buffer_payloads_binary_known": bool(data),
        "unit_binding": contract.get("unit_binding"),
        "natural_terminal_claimed": False,
        "formal_d_claimed": False,
        "claim_boundary": contract["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"decision": decision, "errors": len(errors), "output": str(args.output)}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
