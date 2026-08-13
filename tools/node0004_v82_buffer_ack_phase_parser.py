#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue"
)
PHASES = ("ACTIVE", "INACTIVE", "POSTNBA", "HALF", "NEXT")
LINE = re.compile(
    r"CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target "
    r"instance=(?P<instance>\S+) time=(?P<time>\d+) mask=1 "
    r"payload=(?P<payload>\S+) payload_known=(?P<payload_known>\S+) "
    r"payload_width=(?P<payload_width>\S+) "
    r"seq=(?P<seq>\d+) phase=(?P<phase>ACTIVE|INACTIVE|POSTNBA|HALF|NEXT) "
    r"wr=(?P<wr>\S+) full=(?P<full>\S+) all=(?P<all>\S+) "
    r"valid=(?P<valid>\S+) same=(?P<same>\S+) gotten=(?P<gotten>\S+) "
    r"keep=(?P<keep>\S+) bpmask=(?P<bpmask>\S+) bp=(?P<bp>\S+) "
    r"mode=(?P<mode>\S+) row=(?P<row>\S+) col=(?P<col>\S+) "
    r"rowtag=(?P<rowtag>\S+) coltag=(?P<coltag>\S+)"
)
WIDTHS = {
    "wr": 1,
    "full": 1,
    "all": 1,
    "valid": 2,
    "same": 2,
    "gotten": 2,
    "keep": 2,
    "bpmask": 2,
    "bp": 2,
    "mode": 2,
    "row": 2,
    "col": 5,
    "rowtag": 7,
    "coltag": 7,
}
PAYLOAD_ORDER = tuple(WIDTHS)
PAYLOAD_WIDTH = sum(WIDTHS.values())


def known_width(value: str, width: int) -> bool:
    if not re.fullmatch(r"[0-9a-fA-F]+", value):
        return False
    return int(value, 16) < (1 << width)


def encoded_payload(event: dict[str, str]) -> int:
    result = 0
    for name in PAYLOAD_ORDER:
        result = (result << WIDTHS[name]) | int(event[name], 16)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    events = []
    foreign = 0
    unknown_or_width_invalid = []
    for line_number, line in enumerate(
        args.log.read_text(encoding="utf-8", errors="replace").splitlines(), 1
    ):
        match = LINE.search(line)
        if not match:
            continue
        event = match.groupdict()
        if event["instance"] != TARGET:
            foreign += 1
            continue
        invalid = [name for name, width in WIDTHS.items() if not known_width(event[name], width)]
        if event["payload_known"] != "1":
            invalid.append("payload_known")
        if event["payload_width"] != str(PAYLOAD_WIDTH):
            invalid.append("payload_width")
        if not known_width(event["payload"], PAYLOAD_WIDTH):
            invalid.append("payload")
        elif not invalid and int(event["payload"], 16) != encoded_payload(event):
            invalid.append("payload_named_field_mismatch")
        if invalid:
            unknown_or_width_invalid.append(
                {"line": line_number, "fields": invalid, "values": {name: event[name] for name in invalid}}
            )
            continue
        event["time"] = int(event["time"])
        event["seq"] = int(event["seq"])
        events.append(event)

    grouped = {}
    duplicate = False
    for event in events:
        key = (event["instance"], event["seq"])
        duplicate |= event["phase"] in grouped.setdefault(key, {})
        grouped[key][event["phase"]] = event
    complete = [value for value in grouped.values() if set(PHASES) <= set(value)]
    classes = []
    for value in complete:
        active, inactive, postnba, half, nxt = (value[item] for item in PHASES)
        stable_fields = (
            "full",
            "all",
            "valid",
            "same",
            "keep",
            "bpmask",
            "mode",
            "row",
            "col",
            "rowtag",
            "coltag",
        )
        stable = all(
            active[field] == inactive[field] == postnba[field] == half[field]
            for field in stable_fields
        )
        expected = half["full"] == "0" and half["bpmask"].lower() == "3"
        if not stable:
            classification = "OPERAND_OR_EPOCH_TRANSITION"
        elif expected and postnba["bp"].lower() == "3" and (
            postnba["gotten"].lower() == "3" or half["gotten"].lower() == "3"
        ):
            classification = "POSTNBA_SETTLE_WITH_SAME_CYCLE_CONSUMER_ACCEPT"
        elif (
            expected
            and half["bp"].lower() == "3"
            and half["gotten"].lower() != "3"
            and nxt["gotten"].lower() == "3"
        ):
            classification = "HALF_SETTLE_THEN_NEXT_EDGE_CONSUMER_ACCEPT"
        elif (
            expected
            and half["bp"].lower() == "3"
            and half["gotten"].lower() != "3"
            and nxt["gotten"].lower() != "3"
        ):
            classification = "SETTLED_PUBLIC_ACK_BUT_CONSUMER_STALE"
        elif expected and active["bp"].lower() != "3" and inactive["bp"].lower() == "3":
            classification = "INACTIVE_DELTA_SETTLE"
        elif expected and all(value[item]["bp"].lower() != "3" for item in PHASES):
            classification = "PERSISTENT_EQUATION_OR_COMPILED_SOURCE_MISMATCH"
        else:
            classification = "UNCLASSIFIED_TARGET_PHASE_SEQUENCE"
        classes.append(classification)

    if unknown_or_width_invalid:
        decision = "UNKNOWN_OR_WIDTH_INVALID_PAYLOAD_FAIL_CLOSED"
    elif duplicate:
        decision = "DUPLICATE_PHASE_FAIL_CLOSED"
    elif not grouped:
        decision = "NO_EXACT_TARGET_LIVE_EVENT"
    elif len(complete) != len(grouped):
        decision = "INCOMPLETE_EXACT_TARGET_PHASE_SEQUENCE"
    elif len(set(classes)) != 1:
        decision = "MULTIPLE_TARGET_PHASE_CLASSES"
    else:
        decision = classes[0]

    output = {
        "schema": "node0004-buffer-ack-phase-decision-v3",
        "decision": decision,
        "target_instance": TARGET,
        "payload_width_bits": PAYLOAD_WIDTH,
        "payload_field_widths": WIDTHS,
        "live_event_count": len(events),
        "foreign_event_count": foreign,
        "unknown_or_width_invalid_count": len(unknown_or_width_invalid),
        "unknown_or_width_invalid": unknown_or_width_invalid,
        "sequence_count": len(grouped),
        "complete_sequence_count": len(complete),
        "classes": classes,
        "sequences": {str(key[1]): value for key, value in grouped.items()},
        "claim_boundary": (
            "Exact slice13/group1/MSE4, exact-instance, binary-known declared-width qualified live EVENT "
            "phase sequence only; no config, RTL, numeric, natural-terminal or formal-D claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    valid_decisions = {
        "POSTNBA_SETTLE_WITH_SAME_CYCLE_CONSUMER_ACCEPT",
        "HALF_SETTLE_THEN_NEXT_EDGE_CONSUMER_ACCEPT",
        "SETTLED_PUBLIC_ACK_BUT_CONSUMER_STALE",
        "INACTIVE_DELTA_SETTLE",
        "PERSISTENT_EQUATION_OR_COMPILED_SOURCE_MISMATCH",
        "OPERAND_OR_EPOCH_TRANSITION",
    }
    return 0 if complete and not duplicate and decision in valid_decisions else 2


if __name__ == "__main__":
    raise SystemExit(main())
