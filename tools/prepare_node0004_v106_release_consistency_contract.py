#!/usr/bin/env python3
"""Prepare the exact external final-ZIP release-consistency contract for v106."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v106b_lcdup_return2pflight"
OUT = ROOT / "outputs/conv_node0004_v106b_lcdup_return2pflight_release1"
TREE = OUT / "build" / PACKAGE
ZIP = OUT / f"{PACKAGE}.zip"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def span(source: bytes, literal: bytes) -> tuple[int, int, str]:
    if source.count(literal) != 1:
        raise RuntimeError(f"progress literal count differs: {literal!r}")
    start = source.index(literal)
    end = start + len(literal)
    return start, end, sha_bytes(source[start:end])


def main() -> int:
    if not ZIP.is_file():
        raise SystemExit("exact v106 ZIP is absent")
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request_sha = sha(request_path)
    producers = []
    for item in request.get("core_entries", []):
        if isinstance(item, dict) and item.get("required") is True:
            producers.append({
                "source_root": item["source_root"],
                "source": item["source"],
                "archive": item["archive"],
                "producer_member": "contracts/server_post_sim_return_request.json",
                "producer_sha256": request_sha,
                "producer_output_literal": item["archive"],
            })

    observer_path = TREE / "tb_probe/observer_only_wide_causal.svh"
    observer = observer_path.read_bytes()
    lc3_literal = b"if (sig_lc3_valid && !sig_lc3_bp) begin cnt_lc3_accept = cnt_lc3_accept + 1; codex_accept_qualified_progress = 1; end"
    wdata_literal = b"if (sig_wdata_valid[0] && sig_wdata_ready[0]) begin cnt_wdata0_accept = cnt_wdata0_accept + 1; codex_accept_qualified_progress = 1; end"
    lc3_start, lc3_end, lc3_sha = span(observer, lc3_literal)
    wdata_start, wdata_end, wdata_sha = span(observer, wdata_literal)

    contract = {
        "schema": "server-release-consistency-v1",
        "package": {
            "package_id": PACKAGE,
            "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
            "zip_root_member": PACKAGE,
        },
        "manifest": {
            "member": "package_manifest.json",
            "top_status_pointer": "/status",
            "top_ready_status": "PACKAGE_READY_NOT_RUN",
            "release_critical_statuses": [
                {"pointer": "/final_zip_rule_self_audit/status", "expected_terminal_status": "PASS"},
                {"pointer": "/status", "expected_terminal_status": "PACKAGE_READY_NOT_RUN"},
            ],
        },
        "cross_member_identities": [
            {
                "identity_id": "selected_wall_seconds",
                "expected_value": 3660,
                "endpoints": [
                    {"member": "package_manifest.json", "pointer": "/runtime_budget/selected_wall_seconds"},
                    {"member": "contracts/observer_operational_guard_contract.json", "pointer": "/runtime_budget/selected_wall_seconds"},
                ],
            },
            {
                "identity_id": "absolute_maximum_wall_seconds",
                "expected_value": 86400,
                "endpoints": [
                    {"member": "package_manifest.json", "pointer": "/runtime_budget/absolute_maximum_wall_seconds"},
                    {"member": "contracts/observer_operational_guard_contract.json", "pointer": "/runtime_budget/absolute_maximum_wall_seconds"},
                ],
            },
        ],
        "return_phase": {
            "request_member": "contracts/server_post_sim_return_request.json",
            "allowlist_member": "RETURN_ALLOWLIST.json",
            "allowlist_required_pointer": "/prepublication_required_archives",
            "prepublication_producers": producers,
            "finalization_guard_archive": "evidence/FINALIZATION_OPERATIONAL_GUARD_RECEIPT.json",
            "postpublication_receipts": [
                {"path": "EXTERNAL_DURABLE_RETURN_RECEIPT.json", "location": "EXTERNAL_IMMUTABLE_SIDECAR"},
                {"path": "EXTERNAL_POST_DURABLE_CLEANUP_RECEIPT.json", "location": "EXTERNAL_IMMUTABLE_SIDECAR"},
            ],
            "runner_member": "PREPARE_AND_RUN.sh",
            "runner_sha256": sha(TREE / "PREPARE_AND_RUN.sh"),
            "ordered_runner_markers": [
                {"phase": "FINALIZATION_GUARD_COMPLETE", "literal": "# RELEASE_PHASE_FINALIZATION_GUARD_COMPLETE"},
                {"phase": "RETURN_PUBLISH", "literal": "# RELEASE_PHASE_RETURN_PUBLISH"},
                {"phase": "DURABLE_RETURN_RECEIPT", "literal": "# RELEASE_PHASE_DURABLE_RETURN_RECEIPT"},
                {"phase": "POST_DURABLE_CLEANUP_RECEIPT", "literal": "# RELEASE_PHASE_POST_DURABLE_CLEANUP_RECEIPT"},
            ],
        },
        "progress_qualification": {
            "source_member": "tb_probe/observer_only_wide_causal.svh",
            "source_sha256": sha(observer_path),
            "held_level_replay_required": True,
            "events": [
                {
                    "event_id": "lc3_accept",
                    "counter_symbol": "cnt_lc3_accept",
                    "event_kind": "QUALIFIED_HANDSHAKE",
                    "source_span_start_byte": lc3_start,
                    "source_span_end_byte": lc3_end,
                    "source_span_sha256": lc3_sha,
                    "source_signal_tokens": ["sig_lc3_valid"],
                    "qualifier_signal_tokens": ["!sig_lc3_bp"],
                    "state_memory_tokens": [],
                },
                {
                    "event_id": "wdata0_accept",
                    "counter_symbol": "cnt_wdata0_accept",
                    "event_kind": "QUALIFIED_HANDSHAKE",
                    "source_span_start_byte": wdata_start,
                    "source_span_end_byte": wdata_end,
                    "source_span_sha256": wdata_sha,
                    "source_signal_tokens": ["sig_wdata_valid[0]"],
                    "qualifier_signal_tokens": ["sig_wdata_ready[0]"],
                    "state_memory_tokens": [],
                },
            ],
            "held_level_replays": [
                {"event_id": "lc3_accept", "source_samples": [0, 1, 1, 1, 0, 1], "qualifier_samples": [0, 1, 0, 0, 0, 1], "expected_counter_deltas": [0, 1, 0, 0, 0, 1]},
                {"event_id": "wdata0_accept", "source_samples": [0, 1, 1, 1, 0, 1], "qualifier_samples": [0, 1, 0, 0, 0, 1], "expected_counter_deltas": [0, 1, 0, 0, 0, 1]},
            ],
        },
        "claim_boundary": "Exact local final-ZIP cross-member and temporal consistency only; no production execution or DUT-result claim.",
    }
    path = OUT / "release_consistency_contract.json"
    path.write_bytes(canonical(contract))
    print(path.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
