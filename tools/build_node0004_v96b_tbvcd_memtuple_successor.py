#!/usr/bin/env python3
"""Build the local-only v96 Memory_AG three-input tuple discriminator."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v96b_tbvcd_memtuple"
PREVIOUS = "r5_n4_hw_v95b_tbvcd_metapair"
OUT = ROOT / "outputs/conv_node0004_v96b_tbvcd_memtuple_release1"
TREE = OUT / "build" / PACKAGE
FINAL_ZIP = OUT / f"{PACKAGE}.zip"
SOURCE_TREE = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_release1/build" / PREVIOUS
V95_BUILDER = ROOT / "tools/build_node0004_v95b_tbvcd_metapair_successor.py"
RETURN_BASE = ROOT / "outputs/conv_node0004_v95b_tbvcd_metapair_return_r1786734268630496410_2597866"
ANALYSIS = RETURN_BASE / "return_analysis.json"
RULE_AUDIT = RETURN_BASE / "rule_gap_audit.json"
ACTUAL_SOURCE = RETURN_BASE / "actual_source/Memory_AG_Idx_Queue.sv"
ACTUAL_IDENTITY = RETURN_BASE / "evidence_small/source_identity.json"
TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
)
MEM_SCOPE = f"{TARGET}.u_Memory_AG_Idx_Queue"
MEM_PATH = "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def semantic_sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def load_v95() -> Any:
    spec = importlib.util.spec_from_file_location("node0004_v95_builder_for_v96", V95_BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def declaration_span(symbol: str) -> str:
    rows = [
        row.strip()
        for row in ACTUAL_SOURCE.read_text(encoding="utf-8", errors="replace").splitlines()
        if re.search(r"\b" + re.escape(symbol) + r"\b", row)
    ]
    if not rows:
        raise RuntimeError(f"actual-source symbol absent: {symbol}")
    return hashlib.sha256(rows[0].encode("utf-8")).hexdigest()


def actual_signal(
    signal_id: str,
    suffix: str,
    width: int,
    roles: list[str],
    symbol: str,
    candidates: list[str],
) -> dict[str, Any]:
    return {
        "signal_id": signal_id,
        "exact_hierarchy": f"{MEM_SCOPE}.{suffix}",
        "width_bits": width,
        "roles": roles,
        "source_path": MEM_PATH,
        "source_sha256": sha(ACTUAL_SOURCE),
        "declaration_span_sha256": declaration_span(symbol),
        "source_binding": "ACTUAL_SOURCE_NET",
        "derived_expected_equation": False,
        "drives_dut": False,
        "driver_leaf_for_candidate_ids": sorted(candidates),
        "driver_depth_edges": 0 if candidates else None,
    }


INPUT_CANDIDATES = {
    0: "memory_input0_keep_token_or_epoch_ends_early",
    1: "memory_input1_buffer_token_or_last_ends_early",
    2: "memory_input2_keep_token_or_epoch_ends_early",
}
MASK_CANDIDATE = "memory_same_gotten_mask_suppresses_tenth_tuple"
FIFO_CANDIDATE = "memory_split_fifo_or_keep_release_suppresses_tenth_tuple"


def additions() -> list[dict[str, Any]]:
    rows = [
        actual_signal("sig_mem_raw_idx_all", "u_Memory_AG_Idx_Queue.mse_mem_queue_idx", 48, ["index", "producer"], "mse_mem_queue_idx", []),
        actual_signal("sig_mem_raw_tag_all", "u_Memory_AG_Idx_Queue.mse_mem_queue_tag", 21, ["tag", "producer", "last"], "mse_mem_queue_tag", []),
    ]
    for index, candidate in INPUT_CANDIDATES.items():
        base = f"u_Memory_AG_Idx_Queue."
        specs = [
            ("raw_valid", "mem_idx_valid_bit_unmasked", 1, ["valid", "producer"], [candidate, MASK_CANDIDATE]),
            ("raw_last", "mem_idx_last_bit_unmasked", 1, ["last", "producer", "lifetime"], [candidate]),
            ("raw_same", "mem_idx_same_bit_unmasked", 1, ["valid", "state", "lifetime"], [candidate, MASK_CANDIDATE]),
            ("raw_last_index", "mem_idx_last_index", 4, ["index", "last", "lifetime"], [candidate]),
            ("gotten", "mem_idx_gotten_bit", 1, ["state", "lifetime"], [candidate, MASK_CANDIDATE]),
            ("same_gotten_mask", "mem_idx_same_gotten_mask", 1, ["mask", "state"], [candidate, MASK_CANDIDATE]),
            ("valid_masked", "mem_idx_valid_bit_masked", 1, ["valid", "mask"], [candidate, MASK_CANDIDATE]),
            ("split_wr", "mem_idx_split_fifo_wr_en", 1, ["fifo_enqueue", "accept"], [candidate, FIFO_CANDIDATE]),
            ("split_empty", "idx_split_fifo_empty", 1, ["fifo_empty", "state"], [candidate, FIFO_CANDIDATE]),
            ("split_full", "idx_split_fifo_full", 1, ["fifo_full", "backpressure"], [candidate, FIFO_CANDIDATE]),
            ("fifo_valid_masked", "mem_idx_fifo_valid_bit_masked", 1, ["valid", "mask"], [candidate, FIFO_CANDIDATE]),
            ("fifo_last_masked", "mem_idx_fifo_last_bit_masked", 1, ["last", "mask", "lifetime"], [candidate, FIFO_CANDIDATE]),
            ("fifo_last_index", "mem_idx_fifo_last_index_masked", 4, ["index", "last", "lifetime"], [candidate, FIFO_CANDIDATE]),
            ("source_bp", "mse_mem_queue_bp_pre", 1, ["ready", "backpressure", "producer"], [candidate, FIFO_CANDIDATE]),
            ("queue_bp", "mem_idx_queue_bp_pre", 1, ["ready", "backpressure"], [candidate, FIFO_CANDIDATE]),
            ("keep_mask", "mem_idx_bp_pre_keep_mask", 1, ["mask", "lifetime", "configuration"], [candidate, FIFO_CANDIDATE]),
            ("bp_mask", "mem_idx_bp_pre_mask", 1, ["mask", "backpressure"], [candidate, FIFO_CANDIDATE]),
        ]
        for leaf, symbol, width, roles, candidates in specs:
            rows.append(
                actual_signal(
                    f"sig_mem_i{index}_{leaf}",
                    f"{base}{symbol}[{index}]",
                    width,
                    roles,
                    symbol,
                    candidates,
                )
            )
    return rows


def new_candidates() -> list[dict[str, str]]:
    return [
        {
            "candidate_id": INPUT_CANDIDATES[0],
            "description": "Memory_AG input0 KEEP token/epoch fails to furnish the tenth all-input tuple.",
            "priority": "HIGH",
        },
        {
            "candidate_id": INPUT_CANDIDATES[1],
            "description": "Memory_AG input1 BUFFER token/last lifetime ends before the tenth all-input tuple.",
            "priority": "HIGH",
        },
        {
            "candidate_id": INPUT_CANDIDATES[2],
            "description": "Memory_AG input2 KEEP token/epoch fails to furnish the tenth all-input tuple.",
            "priority": "HIGH",
        },
        {
            "candidate_id": MASK_CANDIDATE,
            "description": "same/gotten state masks an otherwise available input token at tuple ten.",
            "priority": "HIGH",
        },
        {
            "candidate_id": FIFO_CANDIDATE,
            "description": "per-input split FIFO or keep-release/backpressure gating suppresses tuple ten.",
            "priority": "HIGH",
        },
    ]


def source_identity_sha(signals: list[dict[str, Any]]) -> str:
    keys = ("signal_id", "exact_hierarchy", "width_bits", "source_path", "source_sha256", "declaration_span_sha256")
    return semantic_sha(sorted(({key: row[key] for key in keys} for row in signals), key=lambda row: row["signal_id"]))


def pinned_identity() -> str:
    actual = json.loads(ACTUAL_IDENTITY.read_text(encoding="utf-8"))
    value = {
        "filelists": [{"sha256": row.get("sha256"), "exists": row.get("exists")} for row in actual.get("filelists", [])],
        "defines": actual.get("define_tokens", []),
        "parameters": actual.get("parameter_tokens", []),
        "sources": sorted({row.get("relative_path"): row.get("sha256") for row in actual.get("sources", []) if isinstance(row, dict)}.items()),
    }
    return semantic_sha(value)


def candidate_signal_sets(signals: list[dict[str, Any]], prior: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in prior["candidate_boundary_matrix"]:
        candidate = row["candidate_id"]
        result.setdefault(candidate, list(row["expected_signature"]["candidate_signal_ids"]))
    for index, candidate in INPUT_CANDIDATES.items():
        result[candidate] = sorted(row["signal_id"] for row in signals if row["signal_id"].startswith(f"sig_mem_i{index}_")) + ["sig_mem_raw_idx_all", "sig_mem_raw_tag_all"]
    result[MASK_CANDIDATE] = sorted(row["signal_id"] for row in signals if any(token in row["signal_id"] for token in ("raw_valid", "raw_same", "gotten", "same_gotten_mask", "valid_masked")) and row["signal_id"].startswith("sig_mem_i"))
    result[FIFO_CANDIDATE] = sorted(row["signal_id"] for row in signals if any(token in row["signal_id"] for token in ("split_", "fifo_", "source_bp", "queue_bp", "keep_mask", "bp_mask")) and row["signal_id"].startswith("sig_mem_i"))
    return result


def patch_contract(signals: list[dict[str, Any]], probe_sha: str) -> dict[str, Any]:
    prior_path = SOURCE_TREE / "contracts/tb_vcd_bounded_causal_cone_contract.json"
    prior = json.loads(prior_path.read_text(encoding="utf-8"))
    contract = json.loads(prior_path.read_text(encoding="utf-8"))
    predecessor_probe = TREE / "provenance/v95b_predecessor_tb_vcd_bounded_causal_cone.svh"
    shutil.copyfile(SOURCE_TREE / "tb_probe/tb_vcd_bounded_causal_cone.svh", predecessor_probe)
    prior["execution"]["tb_source_path"] = "provenance/v95b_predecessor_tb_vcd_bounded_causal_cone.svh"
    prior["execution"]["tb_source_sha256"] = sha(predecessor_probe)
    contract["package_id"] = PACKAGE
    contract["signals"] = signals
    contract["execution"]["tb_source_sha256"] = probe_sha
    contract["execution"]["dump_targeting"]["signal_ids"] = [row["signal_id"] for row in signals]
    contract["scope"]["dump_scopes"][0]["source_bound_signal_ids"] = [row["signal_id"] for row in signals if not row["signal_id"].startswith("sig_global_")]
    contract["candidates"] = [*prior["candidates"], *new_candidates()]

    added_ids = {row["signal_id"] for row in signals} - {row["signal_id"] for row in prior["signals"]}
    upstream = contract["boundaries"][0]["signal_ids"]
    current = contract["boundaries"][1]["signal_ids"]
    state = contract["boundaries"][3]["signal_ids"]
    for signal_id in sorted(added_ids):
        if signal_id not in upstream:
            upstream.append(signal_id)
        if any(token in signal_id for token in ("gotten", "mask", "empty", "full", "last_index")):
            if signal_id not in state:
                state.append(signal_id)
        else:
            if signal_id not in current:
                current.append(signal_id)

    sets = candidate_signal_sets(signals, prior)
    contract["candidate_boundary_matrix"] = []
    for candidate in contract["candidates"]:
        candidate_id = candidate["candidate_id"]
        for boundary in contract["boundaries"]:
            boundary_ids = set(boundary["signal_ids"])
            contract["candidate_boundary_matrix"].append(
                {
                    "candidate_id": candidate_id,
                    "boundary_id": boundary["boundary_id"],
                    "expected_signature": {
                        "decision_predicate": f"v96_{candidate_id}_distinguishing_predicate",
                        "candidate_signal_ids": sets[candidate_id],
                        "direct_boundary_signal_ids": [signal_id for signal_id in sets[candidate_id] if signal_id in boundary_ids],
                        "requires_complete_ordered_transitions": True,
                    },
                }
            )

    predecessor = TREE / "provenance/v95b_predecessor_contract.json"
    write_json(predecessor, prior)
    prior_ids = {row["signal_id"] for row in prior["signals"]}
    candidate_ids = {row["candidate_id"] for row in contract["candidates"]}
    prior_candidates = {row["candidate_id"] for row in prior["candidates"]}
    count = len(signals)
    contract["diagnostic_round"] = {
        "round_index": 3,
        "round_kind": "EVIDENCE_REFINED_SUCCESSOR",
        "breadth_baseline": {
            "mode": "FAMILY_CURRENT_ROUND_AT_LEAST_THREE_SOFT_REFERENCE",
            "reference_round_index": 3,
            "reference_package_id": "r5_n4_hw_v94b_tbvcd_wrdrain",
            "receipt_path": "provenance/v94b_round3_breadth_baseline.json",
            "receipt_sha256": sha(TREE / "provenance/v94b_round3_breadth_baseline.json"),
            "reference_signal_count": 73,
            "reference_direct_driver_leaf_count": 9,
            "reference_candidate_count": 8,
            "reference_boundary_count": 4,
            "reasonable_signal_count_range": {"minimum": 60, "maximum": 104},
            "deviation": {
                "relation": "ABOVE_REFERENCE_RANGE" if count > 104 else "WITHIN_REFERENCE_RANGE",
                "explanation": "The v95 aggregate boundary validated a one-transaction deficit but omitted the three input formation leaves. Fifty-three one-bit/four-bit source-bound leaves are retained as HIGH drivers; raw count is a soft reference.",
                "acknowledged": count > 104,
            },
        },
        "source_identity": {
            "pinned_rtl_tree_sha256": prior["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
            "catalog_source_identity_sha256": source_identity_sha(signals),
        },
        "coverage_gaps": [],
        "evolution": {
            "predecessor": {
                "package_id": PREVIOUS,
                "round_index": 2,
                "contract_path": "provenance/v95b_predecessor_contract.json",
                "contract_sha256": sha(predecessor),
                "pinned_rtl_tree_sha256": prior["diagnostic_round"]["source_identity"]["pinned_rtl_tree_sha256"],
            },
            "added_signal_ids": sorted(added_ids),
            "removed_signal_ids": [],
            "unchanged_signal_ids": sorted(prior_ids),
            "removal_evidence": [],
            "candidate_preservation": {
                "preserved_candidate_ids": sorted(prior_candidates),
                "closed_candidate_ids": [],
                "new_candidate_ids": sorted(candidate_ids - prior_candidates),
                "closure_evidence": [],
            },
        },
    }
    contract["first_fresh_controls"] = {
        "required_for_family_epoch": True,
        "clean_exact_zip_revalidation": True,
        "negative_controls": {
            "missing_soft_reference_receipt": True,
            "deviation_without_explanation": True,
            "low_confidence_removal": True,
            "add_remove_diff_mismatch": True,
            "candidate_loss": True,
            "source_identity_drift": True,
            "size_or_stop_protection_weakened": True,
        },
    }
    contract["claim_boundary"] = "v95-return-driven Memory_AG three-input tuple discriminator; all v95 evidence retained, actual-source HIGH leaves added, and no production, natural-terminal, formal-D, E3, E4 or E5 claim."
    return contract


def replace_identity() -> None:
    for path in TREE.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".py", ".sh", ".json", ".md", ".txt"}:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if PREVIOUS in text:
                path.write_text(text.replace(PREVIOUS, PACKAGE), encoding="utf-8", newline="\n")


def update_post_and_bound_contracts() -> None:
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = PACKAGE
    write_json(request_path, request)
    runner_path = TREE / "contracts/server_runner_return_resilience.json"
    runner = json.loads(runner_path.read_text(encoding="utf-8"))
    runner["package_id"] = PACKAGE
    runner["runner_sha256"] = sha(TREE / "PREPARE_AND_RUN.sh")
    # The current resilience schema is closed.  These cross-contract links
    # are validated by their own conjunction gates, not embedded here.
    for key in (
        "compile_log_normalizer_arity_contract",
        "diagnostic_mode_selector",
        "runtime_supervisor",
        "tb_vcd_contract",
    ):
        runner.pop(key, None)
    write_json(runner_path, runner)
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = json.loads(post_path.read_text(encoding="utf-8"))
    post["package_id"] = PACKAGE
    post["request_sha256"] = sha(request_path)
    post["helper_sha256"] = sha(TREE / "package_tools/server_post_sim_return.py")
    write_json(post_path, post)


def update_allowlist_and_selector() -> None:
    request = json.loads((TREE / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
    allow = {
        "schema": "server-tb-vcd-return-allowlist-v1",
        "package_id": PACKAGE,
        "required_or_conditional_exact_members": sorted({f"{PACKAGE}_return/{row['archive']}" for row in request["core_entries"]} | {f"{PACKAGE}_return/RETURN_CORE_MANIFEST.json"}),
        "prefixes": [],
        "no_size_limit": True,
        "hard_truncation": False,
        "sampling": False,
        "size_based_deletion": False,
    }
    write_json(TREE / "RETURN_ALLOWLIST.json", allow)
    selector_path = TREE / "contracts/diagnostic_mode_selector.json"
    selector = json.loads(selector_path.read_text(encoding="utf-8"))
    selector["package_id"] = PACKAGE
    selector["package_members"] = sorted(f"{PACKAGE}/{path.relative_to(TREE).as_posix()}" for path in TREE.rglob("*") if path.is_file())
    write_json(selector_path, selector)


def file_rows() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(TREE).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in TREE.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def deterministic_zip(signal_count: int) -> None:
    manifest_path = TREE / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "node0004-v96b-tbvcd-memtuple-package-manifest-v1",
            "package_id": PACKAGE,
            "status": "PACKAGE_READY_NOT_RUN",
            "previous_version_progress": "v95 compiled, entered the target and validated a 32-unit Memory_AG metadata supply deficit: nine 32-unit tuples versus twenty 16-unit prepared groups.",
            "current_purpose": "Identify which of the three Memory_AG inputs or same/gotten/split-FIFO/keep-release mechanism suppresses tuple ten.",
            "source_return_analysis": "provenance/v95b_return_analysis.json",
            "rule_gap_audit": "provenance/v95b_rule_gap_audit.json",
            "rule_audit_disposition": "RULE_DELTA_PROPOSAL_WITH_PACKAGE_IMPLEMENTATION",
            "signal_count": signal_count,
            "retained_predecessor_signal_count": 100,
            "removed_signal_count": 0,
            "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            "retired_ack_comparator_present": False,
        }
    )
    manifest["files"] = file_rows()
    write_json(manifest_path, manifest)
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FINAL_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(TREE.rglob("*"), key=lambda item: item.relative_to(TREE).as_posix()):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(f"{PACKAGE}/{path.relative_to(TREE).as_posix()}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.suffix in {".sh", ".py"} else 0o644) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def main() -> int:
    required = (SOURCE_TREE, ANALYSIS, RULE_AUDIT, ACTUAL_SOURCE, ACTUAL_IDENTITY)
    if not all(path.exists() for path in required):
        raise RuntimeError("v95 source/analysis/audit/actual-source inputs are incomplete")
    OUT.mkdir(parents=True, exist_ok=True)
    if TREE.exists():
        shutil.rmtree(TREE)
    shutil.copytree(SOURCE_TREE, TREE)
    for cache in sorted(TREE.rglob("__pycache__"), reverse=True):
        if cache.is_dir():
            shutil.rmtree(cache)
    for bytecode in TREE.rglob("*.pyc"):
        bytecode.unlink()
    replace_identity()

    provenance = TREE / "provenance"
    shutil.copyfile(ANALYSIS, provenance / "v95b_return_analysis.json")
    shutil.copyfile(RULE_AUDIT, provenance / "v95b_rule_gap_audit.json")
    shutil.copyfile(RETURN_BASE / "dynamic_adjudication.json", provenance / "v95b_dynamic_adjudication.json")
    shutil.copyfile(ACTUAL_IDENTITY, provenance / "v95b_actual_compiled_source_identity.json")
    shutil.copyfile(ACTUAL_SOURCE, provenance / "v95b_actual_source_Memory_AG_Idx_Queue.sv")

    prior = json.loads((SOURCE_TREE / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
    signals = [dict(row) for row in prior["signals"]]
    signals.extend(additions())
    v95 = load_v95()
    v94 = v95.load_v94()
    probe = v95.patch_probe_stop_token(v94.make_probe(signals))
    probe_path = TREE / "tb_probe/tb_vcd_bounded_causal_cone.svh"
    probe_path.write_text(probe, encoding="utf-8", newline="\n")
    contract = patch_contract(signals, sha(probe_path))
    write_json(TREE / "contracts/tb_vcd_bounded_causal_cone_contract.json", contract)

    readme = (
        f"# {PACKAGE}\n\n"
        "Previous progress: v95 production compile passed, target execution began, and same-attempt config/source/VCD evidence validated a one-transaction Memory_AG metadata deficit: 9 x 32 units versus 20 x 16 prepared-data units. The prepared side exactly reaches the expected 320 units, rebutting data over-generation.\n\n"
        "Current purpose: distinguish the exact missing tenth Memory_AG tuple leaf. All 100 v95 signals remain. The package adds per-input raw tag validity/last/same/index, gotten/masks, split-FIFO valid/full/empty, and keep/backpressure release for inputs 0/1/2 using the returned actual compiled source identity.\n\n"
        "Run only after separate authorization:\n\n"
        f"    bash {PACKAGE}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01\n\n"
        "No upload, lease, connection or server run occurred. This ZIP is local staging only and storage publication is intentionally blocked.\n"
    )
    (TREE / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    update_post_and_bound_contracts()
    update_allowlist_and_selector()
    deterministic_zip(len(signals))
    write_json(
        OUT / "build_receipt.json",
        {
            "schema": "node0004-v96b-tbvcd-memtuple-build-v1",
            "package_id": PACKAGE,
            "source_return_analysis": ANALYSIS.relative_to(ROOT).as_posix(),
            "rule_gap_audit": RULE_AUDIT.relative_to(ROOT).as_posix(),
            "signal_count": len(signals),
            "retained_predecessor_signal_count": len(prior["signals"]),
            "added_signal_count": len(signals) - len(prior["signals"]),
            "removed_signal_count": 0,
            "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
            "storage_status": "STORAGE_WAIT_MAINLINE_SERIAL_RELEASE",
            "zip": {"path": FINAL_ZIP.relative_to(ROOT).as_posix(), "bytes": FINAL_ZIP.stat().st_size, "sha256": sha(FINAL_ZIP)},
            "pass": True,
            "errors": [],
        },
    )
    print(FINAL_ZIP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
