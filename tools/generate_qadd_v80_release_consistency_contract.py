#!/usr/bin/env python3
"""Generate an external, content-neutral release-consistency contract for v80."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tr_v80_w15kqf"
OUT = ROOT / "outputs/qadd_v80_w15kqf"
ZIP = OUT / f"{PACKAGE}.zip"
CONTRACT = OUT / "gates/release_cross_member_temporal_consistency_contract.json"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("JSON root is not an object")
    return value


def main() -> int:
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("v80 ZIP CRC failure")
        prefix = f"{PACKAGE}/"
        members = {
            name[len(prefix):]: archive.read(name)
            for name in archive.namelist()
            if name.startswith(prefix) and not name.endswith("/")
        }
    request = load(members["contracts/server_post_sim_return_request.json"])
    required = [row for row in request["core_entries"] if row.get("required") is True]
    publisher_member = "package_tools/server_post_sim_return.py"
    finalizer_member = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v80.py"
    canonical_alias_archives = {
        "evidence/vcd/catalog.json",
        "evidence/vcd/candidate_matrix.json",
        "evidence/vcd/tb_source.json",
        "evidence/vcd/elaboration.json",
        "evidence/vcd/runtime.json",
        "evidence/vcd/return_manifest.json",
        "evidence/vcd/finalization_receipt.json",
    }
    producers = []
    for row in required:
        member = finalizer_member if row["archive"] in canonical_alias_archives else publisher_member
        literal = Path(row["archive"]).name if member == finalizer_member else "source_root"
        producers.append({
            "source_root": row["source_root"],
            "source": row["source"],
            "archive": row["archive"],
            "producer_member": member,
            "producer_sha256": sha_bytes(members[member]),
            "producer_output_literal": literal,
        })

    source_member = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v80.svh"
    source = members[source_member]
    start = source.index(b"  wire tbvcd_accept_event")
    end_token = b"      tbvcd_slice_finish_previous <= sig_slice_finish;"
    end = source.index(end_token, start) + len(end_token)
    span = source[start:end]
    events = [
        {
            "event_id": "target_accept",
            "counter_symbol": "tbvcd_accept_count",
            "event_kind": "QUALIFIED_HANDSHAKE",
            "source_signal_tokens": ["sig_arm_rd_en", "sig_mrm_rd_en"],
            "qualifier_signal_tokens": ["sig_arm_rreq_ready", "sig_mrm_rreq_ready"],
            "state_memory_tokens": [],
        },
        {
            "event_id": "mrm_output_rise",
            "counter_symbol": "tbvcd_output_count",
            "event_kind": "RISING_EDGE_TRANSITION",
            "source_signal_tokens": ["sig_mrm_rvalid"],
            "qualifier_signal_tokens": [],
            "state_memory_tokens": ["tbvcd_mrm_rvalid_previous"],
        },
        {
            "event_id": "arm_output_rise",
            "counter_symbol": "tbvcd_output_count",
            "event_kind": "RISING_EDGE_TRANSITION",
            "source_signal_tokens": ["sig_arm_rvalid"],
            "qualifier_signal_tokens": [],
            "state_memory_tokens": ["tbvcd_arm_rvalid_previous"],
        },
        {
            "event_id": "slice_finish_rise",
            "counter_symbol": "tbvcd_progress_count",
            "event_kind": "TERMINAL_TRANSITION",
            "source_signal_tokens": ["sig_slice_finish"],
            "qualifier_signal_tokens": [],
            "state_memory_tokens": ["tbvcd_slice_finish_previous"],
        },
    ]
    for row in events:
        row.update({
            "source_span_start_byte": start,
            "source_span_end_byte": end,
            "source_span_sha256": sha_bytes(span),
        })
    replays = [
        {
            "event_id": "target_accept",
            "source_samples": [0, 1, 1, 1, 0],
            "qualifier_samples": [0, 1, 0, 0, 0],
            "expected_counter_deltas": [0, 1, 0, 0, 0],
        },
    ]
    for event_id in ("mrm_output_rise", "arm_output_rise", "slice_finish_rise"):
        replays.append({
            "event_id": event_id,
            "source_samples": [0, 1, 1, 1, 0],
            "qualifier_samples": [0, 0, 0, 0, 0],
            "expected_counter_deltas": [0, 1, 0, 0, 0],
        })

    runner = members["PREPARE_AND_RUN.sh"]
    contract = {
        "schema": "server-release-consistency-v1",
        "package": {
            "package_id": PACKAGE,
            "final_zip": {
                "path": ZIP.relative_to(ROOT).as_posix(),
                "bytes": ZIP.stat().st_size,
                "sha256": sha_file(ZIP),
            },
            "zip_root_member": PACKAGE,
        },
        "manifest": {
            "member": "TEST_PACKAGE_MANIFEST.json",
            "top_status_pointer": "/status",
            "top_ready_status": "PACKAGE_READY_NOT_RUN",
            "release_critical_statuses": [
                {
                    "pointer": "/final_zip_rule_self_audit/status",
                    "expected_terminal_status": "FINAL_EXACT_ZIP_AND_FIRST_FRESH_AUDIT_PASS",
                }
            ],
        },
        "cross_member_identities": [
            {
                "identity_id": "selected_wall_seconds",
                "endpoints": [
                    {"member": "diagnostics/runtime_budget_admission.json", "pointer": "/selected_wall_ceiling_seconds"},
                    {"member": "contracts/server_tb_vcd_bounded_causal_cone_contract.json", "pointer": "/budget/wall_ceiling_seconds"},
                ],
                "expected_value": 15000,
            },
            {
                "identity_id": "absolute_maximum_wall_seconds",
                "endpoints": [
                    {"member": "diagnostics/runtime_budget_admission.json", "pointer": "/absolute_maximum_wall_seconds"},
                    {"member": "contracts/server_tb_vcd_bounded_causal_cone_contract.json", "pointer": "/budget/absolute_maximum_wall_seconds"},
                ],
                "expected_value": 86400,
            },
        ],
        "return_phase": {
            "request_member": "contracts/server_post_sim_return_request.json",
            "allowlist_member": "RETURN_ALLOWLIST.json",
            "allowlist_required_pointer": "/required",
            "prepublication_producers": producers,
            "finalization_guard_archive": "evidence/vcd/finalization_receipt.json",
            "postpublication_receipts": [
                {"path": "external/DURABLE_RETURN_RECEIPT.json", "location": "EXTERNAL_IMMUTABLE_SIDECAR"},
                {"path": "external/POST_DURABLE_CLEANUP_RECEIPT.json", "location": "EXTERNAL_IMMUTABLE_SIDECAR"},
            ],
            "runner_member": "PREPARE_AND_RUN.sh",
            "runner_sha256": sha_bytes(runner),
            "ordered_runner_markers": [
                {"phase": "FINALIZATION_GUARD_COMPLETE", "literal": "phase_FINALIZATION_GUARD_COMPLETE=1"},
                {"phase": "RETURN_PUBLISH", "literal": "phase_RETURN_PUBLISH=1"},
                {"phase": "DURABLE_RETURN_RECEIPT", "literal": "phase_DURABLE_RETURN_RECEIPT=1"},
                {"phase": "POST_DURABLE_CLEANUP_RECEIPT", "literal": "phase_POST_DURABLE_CLEANUP_RECEIPT=1"},
            ],
        },
        "progress_qualification": {
            "source_member": source_member,
            "source_sha256": sha_bytes(source),
            "events": events,
            "held_level_replay_required": True,
            "held_level_replays": replays,
        },
        "claim_boundary": "External content-neutral audit of frozen preactivation v80 only; no ZIP mutation, publication, server run or DUT claim.",
    }
    CONTRACT.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"contract": CONTRACT.relative_to(ROOT).as_posix(), "required_producers": len(producers)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
