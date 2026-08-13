from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v75_return_successor_v76 as prior


SOURCE = "r5_n4_hw_v76_sourcebound_boundfix"
INSTALL = "r5_n4_hw_v77_terminal_temporal_ledger_diag"
SOURCE_ZIP_SHA = "cb5158ac464dde5f291a179a334d1bc027a4bb7e16346116633cab9bc8c408bb"
RETURN_SHA = "c2d98e5c1736790bc414bbe1fe174295c490d680e23c6cb1fb8c1a98f586afa4"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
ANALYSIS = ROOT / "outputs/conv_node0004_v76_return_analysis/report.json"
OUT = ROOT / "outputs/conv_node0004_v76_return_v77_successor"
DEFAULT_OUTPUT = OUT / "build"
EPOCH = "20260810-first-fresh-extra-audit-v1"
base = prior.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


TARGET_PREFIX = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
    "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
)


BOUNDED_PREPARE_V3 = rf'''def _prepare_source_bound_products(run_root: Path) -> dict[str, Any]:
    from collections import defaultdict, deque

    c0 = run_root / "c0"
    c0.mkdir(parents=True, exist_ok=True)
    sim_log = c0 / "sim.log"
    causal_log = c0 / "source_bound_causal.log"
    decision = c0 / "source_bound_causal_decision.json"
    temporal_decision = c0 / "target_temporal_decision.json"
    original_bytes = sim_log.stat().st_size if sim_log.is_file() else 0
    original_sha256 = sha256(sim_log) if sim_log.is_file() else None
    core_kinds = {{"ENABLED", "SUMMARY", "CLASS", "TRIGGER", "STALL"}}
    ring_kinds = {{"RING_PROGRESS", "RING_STATE", "RING_POST"}}
    core_records: list[tuple[int, str]] = []
    target_ring_records: list[tuple[int, str]] = []
    other_ring_tails: dict[tuple[str, str, str], deque[tuple[int, str]]] = defaultdict(lambda: deque(maxlen=1))
    input_kind_counts: dict[str, int] = {{}}
    ordinal = 0
    if sim_log.is_file():
        with sim_log.open("r", encoding="utf-8", errors="replace") as stream:
            for raw in stream:
                offset = raw.find("CODEX_PROBE_V1 ")
                if offset < 0:
                    continue
                line = raw[offset:].rstrip("\r\n")
                parsed = {{}}
                for token in line.split(" ")[1:]:
                    if "=" in token:
                        key, value = token.split("=", 1)
                        parsed[key] = value
                kind = parsed.get("kind")
                if kind not in core_kinds | ring_kinds:
                    continue
                input_kind_counts[kind] = input_kind_counts.get(kind, 0) + 1
                item = (ordinal, line)
                ordinal += 1
                if kind in core_kinds:
                    core_records.append(item)
                elif parsed.get("instance", "").startswith({TARGET_PREFIX!r}):
                    target_ring_records.append(item)
                else:
                    key = (kind, parsed.get("boundary", "<none>"), parsed.get("instance", "<none>"))
                    other_ring_tails[key].append(item)

    selected: dict[int, str] = {{index: line for index, line in core_records}}
    selected.update({{index: line for index, line in target_ring_records}})
    for key in sorted(other_ring_tails):
        for index, line in other_ring_tails[key]:
            selected[index] = line
    retained = sorted(selected.items())
    compact = ("\n".join(line for _, line in retained) + ("\n" if retained else "")).encode("utf-8")
    limit = 7 * 1024 * 1024
    if len(compact) > limit:
        raise DiagnosticRuntimeError("target-complete source-bound causal projection exceeds 7 MiB")

    retained_kind_counts: dict[str, int] = {{}}
    for _, line in retained:
        parsed = {{}}
        for token in line.split(" ")[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                parsed[key] = value
        kind = parsed.get("kind", "UNKNOWN")
        retained_kind_counts[kind] = retained_kind_counts.get(kind, 0) + 1
    causal_log.write_bytes(compact)
    sim_log.write_bytes(compact)

    package_root = Path(__file__).resolve().parents[1]
    parser = package_root / "package_tools/source_bound_causal_parser.py"
    completed = subprocess.run(
        [sys.executable, str(parser), "--log", str(causal_log), "--output", str(decision)],
        text=True, capture_output=True, check=False,
    )
    if not decision.is_file():
        raise DiagnosticRuntimeError("source-bound parser did not produce canonical decision")
    parsed_decision = load_json(decision)
    if completed.returncode != 0 or parsed_decision.get("decision") == "EVIDENCE_INCOMPLETE":
        raise DiagnosticRuntimeError("target-complete source-bound parser result remains incomplete")

    summaries: dict[str, dict[str, int]] = {{}}
    progress: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for _, line in retained:
        parsed = {{}}
        for token in line.split(" ")[1:]:
            if "=" in token:
                key, value = token.split("=", 1)
                parsed[key] = value
        if not parsed.get("instance", "").startswith({TARGET_PREFIX!r}):
            continue
        boundary = parsed.get("boundary", "")
        if parsed.get("kind") == "SUMMARY":
            summaries[boundary] = {{
                "count": int(parsed.get("count", "0"), 0),
                "first": int(parsed.get("first", "0"), 0),
                "last": int(parsed.get("last", "0"), 0),
                "maxgap": int(parsed.get("maxgap", "0"), 0),
            }}
        elif parsed.get("kind") == "RING_PROGRESS":
            progress[boundary].append({{
                "time": int(parsed.get("time", "0"), 0),
                "mask": parsed.get("mask"),
                "payload": parsed.get("payload"),
                "seq": int(parsed.get("seq", "0"), 0),
            }})
    for events in progress.values():
        events.sort(key=lambda value: (value["time"], value["seq"]))

    required_target_boundaries = {{
        "mem_source_match", "mem_queue_enqueue", "mem_queue_dequeue",
        "mem_consumer_accept", "mem_internal_match", "mem_terminal",
        "buf_source_match", "buf_queue_enqueue", "buf_queue_dequeue",
        "buf_consumer_accept", "buf_internal_match", "buf_terminal",
    }}
    missing_target_summaries = sorted(required_target_boundaries - set(summaries))
    if missing_target_summaries:
        raise DiagnosticRuntimeError(
            "target temporal ledger missing required summaries: "
            + ",".join(missing_target_summaries)
        )

    mem_terminal_events = progress.get("mem_terminal", [])
    mem_terminal_time = mem_terminal_events[-1]["time"] if mem_terminal_events else None
    def after_mem(boundary: str) -> list[dict[str, Any]]:
        if mem_terminal_time is None:
            return []
        return [item for item in progress.get(boundary, []) if item["time"] > mem_terminal_time]

    observations = {{
        "mem_terminal_present": mem_terminal_time is not None,
        "mem_terminal_time": mem_terminal_time,
        "mem_enqueue_count": summaries.get("mem_queue_enqueue", {{}}).get("count", 0),
        "mem_dequeue_count": summaries.get("mem_queue_dequeue", {{}}).get("count", 0),
        "buf_enqueue_count": summaries.get("buf_queue_enqueue", {{}}).get("count", 0),
        "buf_dequeue_count": summaries.get("buf_queue_dequeue", {{}}).get("count", 0),
        "buf_consumer_count": summaries.get("buf_consumer_accept", {{}}).get("count", 0),
        "buf_terminal_count": summaries.get("buf_terminal", {{}}).get("count", 0),
        "buf_enqueue_after_mem_terminal": after_mem("buf_queue_enqueue"),
        "buf_dequeue_after_mem_terminal": after_mem("buf_queue_dequeue"),
        "buf_consumer_after_mem_terminal": after_mem("buf_consumer_accept"),
        "buf_terminal_after_mem_terminal": after_mem("buf_terminal"),
    }}
    observations["mem_queue_residual"] = observations["mem_enqueue_count"] - observations["mem_dequeue_count"]
    observations["buf_queue_residual"] = observations["buf_enqueue_count"] - observations["buf_dequeue_count"]

    if not observations["mem_terminal_present"]:
        candidate = "MEMORY_TERMINAL_ABSENT"
    elif observations["buf_enqueue_after_mem_terminal"]:
        candidate = "BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH"
    elif observations["buf_queue_residual"] > 0:
        candidate = "BUFFER_QUEUE_RESIDUAL_BEFORE_MEMORY_TERMINAL"
    elif observations["mem_queue_residual"] > 0:
        candidate = "MEMORY_QUEUE_RESIDUAL"
    else:
        candidate = "BALANCED_BRANCHES_DOWNSTREAM_RELEASE"
    candidates = [
        "MEMORY_TERMINAL_ABSENT",
        "BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH",
        "BUFFER_QUEUE_RESIDUAL_BEFORE_MEMORY_TERMINAL",
        "MEMORY_QUEUE_RESIDUAL",
        "BALANCED_BRANCHES_DOWNSTREAM_RELEASE",
    ]
    temporal = {{
        "schema": "node0004-target-terminal-temporal-decision-v1",
        "target_instance_prefix": {TARGET_PREFIX!r},
        "decision": candidate,
        "matching_candidate_ids": [candidate],
        "candidate_ids": candidates,
        "pairwise_distinguishable": True,
        "missing_required_target_summaries": missing_target_summaries,
        "observations": observations,
        "summaries": summaries,
        "target_progress_ledger": progress,
        "claim_boundary": "Qualified generated-observer events for exact slice0/group0/MSE4 WR target only; no DUT natural-terminal or formal-D claim.",
    }}
    write_json(temporal_decision, temporal)
    temporal_receipt = {{
        "schema": "node0004-target-terminal-temporal-parser-receipt-v1",
        "target_instance_prefix": {TARGET_PREFIX!r},
        "complete_target_ring_retained": True,
        "target_ring_record_count": len(target_ring_records),
        "candidate_ids": candidates,
        "decision": candidate,
        "decision_sha256": sha256(temporal_decision),
        "pairwise_distinguishable": True,
    }}
    evidence = run_root / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    write_json(evidence / "target_temporal_parser_receipt.json", temporal_receipt)

    return {{
        "schema": "source-bound-bounded-collector-receipt-v3",
        "source_bound_input_record_count": sum(input_kind_counts.values()),
        "source_bound_retained_record_count": len(retained),
        "source_bound_dropped_ring_record_count": sum(input_kind_counts.get(kind, 0) for kind in ring_kinds) - sum(retained_kind_counts.get(kind, 0) for kind in ring_kinds),
        "input_kind_counts": input_kind_counts,
        "retained_kind_counts": retained_kind_counts,
        "target_complete_ring_record_count": len(target_ring_records),
        "other_ring_group_count": len(other_ring_tails),
        "ring_retention_policy": {{"target_exact_instance": "ALL", "other_instance_boundary_kind": "TAIL_1"}},
        "original_sim_log_bytes": original_bytes,
        "original_sim_log_sha256": original_sha256,
        "bounded_log_bytes": len(compact),
        "bounded_log_sha256": hashlib.sha256(compact).hexdigest(),
        "bounded_log_limit_bytes": limit,
        "sim_log_equals_causal_log": True,
        "parser_exit_status": completed.returncode,
        "parser_stdout": completed.stdout.strip(),
        "parser_stderr": completed.stderr.strip(),
        "parser_decision": parsed_decision.get("decision"),
        "matching_candidate_ids": parsed_decision.get("matching_candidate_ids", []),
        "target_temporal_decision": candidate,
        "target_temporal_decision_sha256": sha256(temporal_decision),
    }}'''


def patch_runtime(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime_v7.py"
    text = path.read_text(encoding="utf-8")
    text = prior.replace_function(text, "_prepare_source_bound_products", BOUNDED_PREPARE_V3)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_plugin(package: Path) -> None:
    old = package / "package_tools/node0004_v76_post_sim_plugin.py"
    new = package / "package_tools/node0004_v77_post_sim_plugin.py"
    old.rename(new)
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = INSTALL
    request["plugins"][0]["argv"] = [
        item.replace("node0004_v76_post_sim_plugin.py", "node0004_v77_post_sim_plugin.py")
        for item in request["plugins"][0]["argv"]
    ]
    new_entries = [
        {
            "archive": "evidence/target_temporal_parser_receipt.json",
            "required": False,
            "source": "evidence/target_temporal_parser_receipt.json",
            "source_root": "attempt",
        },
        {
            "archive": "runs/c0/target_temporal_decision.json",
            "required": False,
            "source": "c0/target_temporal_decision.json",
            "source_root": "attempt",
        },
    ]
    archives = {item["archive"] for item in request["core_entries"]}
    request["core_entries"].extend(item for item in new_entries if item["archive"] not in archives)
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["request_sha256"] = base.sha256(request_path)
    write_json(contract_path, contract)


def build_directory(output: Path) -> Path:
    prior.SOURCE = SOURCE
    prior.INSTALL = INSTALL
    prior.SOURCE_SHA = SOURCE_ZIP_SHA
    prior.RETURN_SHA = RETURN_SHA
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.ANALYSIS = ANALYSIS
    prior.OUT = OUT
    prior.SB = OUT / "source_bound"
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    original_runtime = prior.patch_runtime
    original_plugin = prior.patch_plugin
    try:
        prior.patch_runtime = patch_runtime
        prior.patch_plugin = patch_plugin
        package = prior.build_directory(output)
    finally:
        prior.patch_runtime = original_runtime
        prior.patch_plugin = original_plugin

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["install_name"] = INSTALL
    manifest["status"] = "PACKAGE_BUILT_PENDING_FIRST_FRESH_EXTRA_AUDIT"
    manifest["first_fresh_extra_audit"] = {
        "epoch_id": EPOCH,
        "notification_acknowledged": True,
        "first_fresh_after_change": True,
        "bound_package_id": INSTALL,
        "cheap_prebuild_aggregate_invocations": 1,
        "final_zip_count": 1,
        "upload_hold_until_extra_audit_pass": True,
    }
    manifest["v76_return_adjudication"] = {
        "formal_return_sha256": RETURN_SHA,
        "return_analysis_sha256": base.sha256(ANALYSIS),
        "last_proven_good": "SOURCE_BOUND_BOUNDED_COLLECTOR_AND_PARSER_CANONICAL_DECISION_PUBLISHED",
        "first_divergence": "TARGET_MSE4_BUFFER_TERMINAL_BRANCH_ADVANCES_EARLIER_AND_FARTHER_THAN_MEMORY_TERMINAL_BRANCH_WITHOUT_NATURAL_D_RELEASE",
        "unique_class": "both_terminals_present_temporal_skew",
        "root_leaf_status": "UNRESOLVED",
    }
    manifest["target_temporal_ledger_diagnostic"] = {
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "target_instance_prefix": TARGET_PREFIX,
        "retention": "all target ring records; tail1 for all other instance/boundary/kind groups",
        "candidate_ids": [
            "MEMORY_TERMINAL_ABSENT",
            "BUFFER_ACCEPTS_POST_MEMORY_TERMINAL_EPOCH",
            "BUFFER_QUEUE_RESIDUAL_BEFORE_MEMORY_TERMINAL",
            "MEMORY_QUEUE_RESIDUAL",
            "BALANCED_BRANCHES_DOWNSTREAM_RELEASE",
        ],
        "pairwise_distinguishable": True,
        "natural_terminal_or_formal_d_claim": False,
    }
    rules = manifest.setdefault("active_receipts", {}).setdefault("rules", [])
    for rule in (
        "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
        "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    ):
        if rule not in rules:
            rules.append(rule)
    write_json(
        package / "provenance/v76_return_to_v77_temporal_ledger.json",
        {
            "schema": "conv-node0004-v76-return-to-v77-temporal-ledger-v1",
            "source_package_zip_sha256": SOURCE_ZIP_SHA,
            "formal_return_sha256": RETURN_SHA,
            "return_analysis_sha256": base.sha256(ANALYSIS),
            "epoch_ack": EPOCH,
            "first_fresh_after_change": True,
            "changed_surface": [
                "fresh identity",
                "target-complete bounded collector retention",
                "target temporal decision product and return bindings",
            ],
            "frozen": [
                "numeric/W3/qparams/tail/workload/config/golden",
                "timeout/backpressure",
                "functional RTL/ISA/hardware/active ndp-sim",
            ],
        },
    )
    base.refresh_receipts(manifest)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    write_json(manifest_path, manifest)
    return package


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = build_directory(output)
    archive = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, archive)
    digest = base.sha256(archive)
    with tempfile.TemporaryDirectory(prefix="node0004-v77-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        if base.sha256(repeat_zip) != digest:
            raise BuildError("deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-node0004-v77-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HOLD_PENDING_FIRST_FRESH_EXTRA_AUDIT",
        "package_id": INSTALL,
        "zip": str(archive),
        "zip_bytes": archive.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": True,
        "epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "cheap_prebuild_aggregate_invocations": 1,
        "final_zip_count": 1,
        "numeric_analysis_repeated": False,
        "workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{INSTALL}.build.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
