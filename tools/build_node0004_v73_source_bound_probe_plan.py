from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_server_source_bound_observer import semantic_sha256


def signal(symbol_id: str) -> dict[str, object]:
    return {"op": "SIGNAL", "symbol_id": symbol_id}


def neg(symbol_id: str) -> dict[str, object]:
    return {"op": "NOT", "arg": signal(symbol_id)}


def conjunction(*predicates: dict[str, object]) -> dict[str, object]:
    return {"op": "AND", "args": list(predicates)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--package-id", default="r5_n4_hw_v73_sourcebound_epoch_diag")
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if catalog.get("valid") is not True:
        raise ValueError("catalog is not valid")
    symbols = {
        (item["module"], item["name"]): item["symbol_id"]
        for item in catalog["symbols"]
    }

    def sym(module: str, name: str) -> str:
        try:
            return symbols[(module, name)]
        except KeyError as exc:
            raise ValueError(f"missing source-bound symbol: {module}.{name}") from exc

    def module_ids(prefix: str) -> dict[str, str]:
        if prefix == "mem":
            module = "Memory_AG_Idx_Queue"
            names = {
                "clk": "clk",
                "rst": "rst_n",
                "enable": "mse_enable",
                "match": "mem_all_idx_matched",
                "last": "mem_buffer_idx_last_bit",
                "wr": "mem_ag_idx_queue_wr_en",
                "rd": "mem_ag_idx_queue_rd_en",
                "full": "mem_ag_idx_queue_full",
                "empty": "mem_ag_idx_queue_empty",
                "out_valid": "mse_mem_ag_tag_valid",
                "out_ready": "mse_mem_ag_bp_post",
            }
        else:
            module = "Buffer_AG_Idx_Queue"
            names = {
                "clk": "clk",
                "rst": "rst_n",
                "enable": "mse_enable",
                "match": "buf_all_idx_matched",
                "last": "buf_buffer_idx_last_bit",
                "wr": "buf_ag_idx_queue_wr_en",
                "rd": "buf_ag_idx_queue_rd_en",
                "full": "buf_ag_idx_queue_full",
                "empty": "buf_ag_idx_queue_empty",
                "out_valid": "mse_buf_ag_tag_valid",
                "out_ready": "mse_buf_ag_bp_post",
            }
        return {"module": module, **{key: sym(module, value) for key, value in names.items()}}

    boundaries: list[dict[str, object]] = []
    role_ids: dict[str, list[str]] = {
        "source_produce": [],
        "queue_enqueue": [],
        "queue_dequeue": [],
        "consumer_accept": [],
        "internal_match_compute": [],
        "terminal_propagation": [],
    }

    for prefix in ("mem", "buf"):
        ids = module_ids(prefix)
        module = str(ids["module"])
        common = {
            "target_module": module,
            "clock_symbol_id": ids["clk"],
            "reset": {"symbol_id": ids["rst"], "active_low": True},
            "stage_gate": signal(ids["enable"]),
        }
        payload = [
            ids["match"], ids["last"], ids["wr"], ids["rd"], ids["full"],
            ids["empty"], ids["out_valid"], ids["out_ready"],
        ]

        boundary_id = f"{prefix}_source_match"
        role_ids["source_produce"].append(boundary_id)
        boundaries.append({
            "boundary_id": boundary_id,
            "role": "source_produce",
            **common,
            "classes": [
                {"class_id": f"{prefix}_source_match", "bit": 0, "progress": False,
                 "trigger": False, "predicate": signal(ids["match"])},
                {"class_id": f"{prefix}_source_terminal", "bit": 1, "progress": False,
                 "trigger": True, "predicate": conjunction(signal(ids["match"]), signal(ids["last"]))},
                {"class_id": f"{prefix}_source_wait", "bit": 2, "progress": False,
                 "trigger": False, "predicate": neg(ids["match"])},
            ],
            "payload_symbol_ids": payload,
        })

        boundary_id = f"{prefix}_queue_enqueue"
        role_ids["queue_enqueue"].append(boundary_id)
        accepted_write = conjunction(signal(ids["wr"]), neg(ids["full"]))
        boundaries.append({
            "boundary_id": boundary_id,
            "role": "queue_enqueue",
            **common,
            "classes": [
                {"class_id": f"{prefix}_enqueue_accept", "bit": 0, "progress": True,
                 "trigger": False, "predicate": accepted_write},
                {"class_id": f"{prefix}_enqueue_terminal", "bit": 1, "progress": True,
                 "trigger": True, "predicate": conjunction(accepted_write, signal(ids["last"]))},
                {"class_id": f"{prefix}_enqueue_blocked_full", "bit": 2, "progress": False,
                 "trigger": True, "predicate": conjunction(signal(ids["wr"]), signal(ids["full"]))},
            ],
            "payload_symbol_ids": payload,
        })

        boundary_id = f"{prefix}_queue_dequeue"
        role_ids["queue_dequeue"].append(boundary_id)
        boundaries.append({
            "boundary_id": boundary_id,
            "role": "queue_dequeue",
            **common,
            "classes": [
                {"class_id": f"{prefix}_dequeue_accept", "bit": 0, "progress": True,
                 "trigger": False, "predicate": conjunction(signal(ids["rd"]), neg(ids["empty"]))},
                {"class_id": f"{prefix}_dequeue_empty_attempt", "bit": 1, "progress": False,
                 "trigger": True, "predicate": conjunction(signal(ids["rd"]), signal(ids["empty"]))},
            ],
            "payload_symbol_ids": payload,
        })

        boundary_id = f"{prefix}_consumer_accept"
        role_ids["consumer_accept"].append(boundary_id)
        boundaries.append({
            "boundary_id": boundary_id,
            "role": "consumer_accept",
            **common,
            "classes": [
                {"class_id": f"{prefix}_consumer_accept", "bit": 0, "progress": True,
                 "trigger": False, "predicate": conjunction(signal(ids["out_valid"]), signal(ids["out_ready"]))},
                {"class_id": f"{prefix}_consumer_blocked", "bit": 1, "progress": False,
                 "trigger": True, "predicate": conjunction(signal(ids["out_valid"]), neg(ids["out_ready"]))},
            ],
            "payload_symbol_ids": payload,
        })

        boundary_id = f"{prefix}_internal_match"
        role_ids["internal_match_compute"].append(boundary_id)
        boundaries.append({
            "boundary_id": boundary_id,
            "role": "internal_match_compute",
            **common,
            "classes": [
                {"class_id": f"{prefix}_all_match", "bit": 0, "progress": False,
                 "trigger": False, "predicate": signal(ids["match"])},
                {"class_id": f"{prefix}_match_absent", "bit": 1, "progress": False,
                 "trigger": True, "predicate": neg(ids["match"])},
            ],
            "payload_symbol_ids": payload,
        })

        boundary_id = f"{prefix}_terminal"
        role_ids["terminal_propagation"].append(boundary_id)
        boundaries.append({
            "boundary_id": boundary_id,
            "role": "terminal_propagation",
            **common,
            "classes": [
                {"class_id": f"{prefix}_terminal_enqueue", "bit": 0, "progress": True,
                 "trigger": True, "predicate": conjunction(accepted_write, signal(ids["last"]))},
                {"class_id": f"{prefix}_terminal_held_full", "bit": 1, "progress": False,
                 "trigger": True, "predicate": conjunction(signal(ids["wr"]), signal(ids["full"]), signal(ids["last"]))},
            ],
            "payload_symbol_ids": payload,
        })

    observations = [
        {"observation_id": "mem_terminal_seen", "boundary_id": "mem_terminal",
         "metric": "class_seen", "class_id": "mem_terminal_enqueue"},
        {"observation_id": "buf_terminal_seen", "boundary_id": "buf_terminal",
         "metric": "class_seen", "class_id": "buf_terminal_enqueue"},
    ]
    candidates = []
    for candidate_id, root_class, mem_seen, buf_seen in (
        ("memory_terminal_absent_buffer_present", "MEMORY_SOURCE_TERMINAL_ABSENT", False, True),
        ("buffer_terminal_absent_memory_present", "BUFFER_SOURCE_TERMINAL_ABSENT", True, False),
        ("both_terminals_present_temporal_skew", "POST_TERMINAL_TEMPORAL_OWNERSHIP_REQUIRES_RING", True, True),
        ("neither_terminal_present_upstream_stop", "BOTH_SOURCE_TERMINALS_ABSENT", False, False),
    ):
        candidates.append({
            "candidate_id": candidate_id,
            "root_cause_class": root_class,
            "signature": {
                "mem_terminal_seen": mem_seen,
                "buf_terminal_seen": buf_seen,
            },
        })

    role_coverage = [
        {"role": role, "disposition": "covered", "boundary_ids": ids,
         "reason": "Exact generated source-bound boundary in the changed MSE4 token ownership slice."}
        for role, ids in role_ids.items()
    ]
    role_coverage.extend([
        {"role": "output_accept", "disposition": "not_applicable", "boundary_ids": [],
         "reason": "The changed causal slice ends at the Memory_AG/Buffer_AG public consumer accept; later descriptor/prepared output acceptance remains byte-identical and is retained by the frozen observer."},
        {"role": "formal_d_collection", "disposition": "not_applicable", "boundary_ids": [],
         "reason": "Formal D collection remains the unchanged 320-item result gate and is not a source-bound signal-generation change."},
    ])

    plan = {
        "schema": "server-source-bound-probe-plan-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "profile": "HIGH_INFORMATION_CAUSAL_V1",
        "package_id": args.package_id,
        "family": "conv_serialized_node0004",
        "catalog_identity": {
            "rtl_tree_sha256": catalog["rtl_identity"]["rtl_tree_sha256"],
            "catalog_semantic_sha256": semantic_sha256(catalog),
        },
        "boundaries": boundaries,
        "role_coverage": role_coverage,
        "decision_observations": observations,
        "candidates": candidates,
        "runtime_budget": {
            "qualified_ring_depth": 32,
            "non_progress_ring_depth": 16,
            "first_payload_samples": 8,
            "post_trigger_samples": 16,
            "no_progress_cycles": 4096,
            "max_log_bytes": 8388608,
            "state_activity_consumes_qualified_budget": False,
            "multiclass_encoding": "BITMAP_ALL_TRUE_CLASSES",
            "text_io_policy": "FIRST_SAMPLES_TRIGGER_AND_FINAL_ONLY",
            "slowdown_limit_hard": False,
        },
        "claim_boundary": (
            "Generated read-only Memory_AG/Buffer_AG source-match, accepted enqueue/dequeue, "
            "consumer, internal-match and terminal chronology only. It does not modify DUT, "
            "configuration, numeric payload, timeout, backpressure or formal-D logic."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "output": str(args.output),
        "catalog_semantic_sha256": plan["catalog_identity"]["catalog_semantic_sha256"],
        "plan_semantic_sha256": semantic_sha256(plan),
        "boundaries": len(boundaries),
        "candidates": len(candidates),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
