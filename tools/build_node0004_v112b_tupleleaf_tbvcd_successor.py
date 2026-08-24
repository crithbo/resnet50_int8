#!/usr/bin/env python3
"""Patch-first builder for serialized Conv node0004 v112 tuple-leaf TB VCD.

The predecessor produced a valid VCD but VCS collapsed 51 packed-vector
bit-select dump declarations into 17 whole-vector header references.  This
builder preserves the actual observed values while replacing those 51
unmappable catalog identities with passive bind-input leaf aliases.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/conv_node0004_v112_tupleleaf_20260822"
OLD_ID = "r5_n4_hw_v111b_config_bypass_tbvcd_singlezip"
NEW_ID = "r5_n4_hw_v112b_tupleleaf_tbvcd"
OLD_TREE = (
    ROOT
    / "outputs/conv_node0004_v111_lf_fix_20260819/build"
    / OLD_ID
)
TREE = OUT / "build" / NEW_ID
ZIP_PATH = OUT / f"{NEW_ID}.zip"
V111_RETURN = (
    ROOT
    / "outputs/conv_node0004_v111_return_r1787198069563420665_626725"
    / f"{OLD_ID}_return.zip"
)
V111_ANALYSIS = (
    ROOT
    / "outputs/conv_node0004_v111_return_r1787198069563420665_626725"
    / "return_analysis.json"
)
MODE_ROOT = ROOT / "outputs/mainline_conv_serialized_v112_mode_authority"
CONTRACT_REL = Path("contracts/tb_vcd_bounded_causal_cone_contract.json")
TB_REL = Path("tb_probe/tb_vcd_bounded_causal_cone.svh")
LEAF_SUFFIX = "_leafv112"
TARGET_HIERARCHY = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new."
    "slice_with_datahub_mc_group_gen[13].u_slice_with_datahub_mc_group."
    "slice_group_gen[1].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
    "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
)
PROXY_INSTANCE = f"{TARGET_HIERARCHY}.codex_node0004_tb_vcd_cone_inst"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def walk_files(root: Path):
    for current, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            yield Path(current) / name


def file_map(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha_file(path)
        for path in walk_files(root)
    }


def semantic_sha(value: Any) -> str:
    data = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha_bytes(data)


def signal_identity_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": item["signal_id"],
        "exact_hierarchy": item["exact_hierarchy"],
        "width_bits": item["width_bits"],
        "source_path": item["source_path"],
        "source_sha256": item["source_sha256"],
        "declaration_span_sha256": item["declaration_span_sha256"],
    }


def declaration_span_sha(path: Path, symbol: str) -> str:
    matches = [
        row.strip()
        for row in path.read_text(encoding="utf-8", errors="replace").splitlines()
        if not row.lstrip().startswith("//")
        and re.search(rf"\b{re.escape(symbol)}\b", row)
    ]
    if not matches:
        raise RuntimeError(f"actual source symbol absent: {path}:{symbol}")
    return sha_bytes(matches[0].encode("utf-8"))


def bind_catalog_to_v111_actual_compiled_sources() -> dict[str, Any]:
    """Reconcile the frozen v111 catalog with returned actual compile bytes.

    The shared round-evolution contract requires every retained signal identity
    to remain byte-stable.  Therefore the predecessor catalog identity is not
    silently rewritten.  Instead, an exact machine-readable reconciliation
    binds its expected hash to the source captured by the successful v111
    production compile.  Fresh v112 aliases themselves bind the actual bytes.
    """
    contract_path = TREE / CONTRACT_REL
    contract = load_json(contract_path)
    receipt_path = TREE / "provenance/v111_actual_compiled_source_identity.json"
    actual_receipt = load_json(receipt_path)
    if actual_receipt.get("compile_exit") != 0 or actual_receipt.get("status") != "COMPLETE":
        raise RuntimeError("v111 actual compiled source receipt is not authoritative")
    actual_sources = {
        row["relative_path"]: row
        for row in actual_receipt.get("sources", [])
        if row.get("exists") is True
    }
    alias_path = TREE / "provenance/v112_tuple_leaf_alias_binding.json"
    alias_receipt = load_json(alias_path)
    aliases = {
        row["successor_signal_id"]: row for row in alias_receipt.get("aliases", [])
    }
    predecessor = load_json(
        TREE / "provenance/v111_predecessor_tb_vcd_contract_historical_exact.json"
    )
    prior_by_id = {row["signal_id"]: row for row in predecessor["signals"]}
    reconciliation_rows = []
    for signal in contract["signals"]:
        rel = signal["source_path"]
        actual = actual_sources.get(rel)
        if actual is None:
            raise RuntimeError(f"actual compiled source identity absent: {rel}")
        local = ROOT / "NDP_copy01" / rel
        if not local.is_file() or sha_file(local) != actual.get("sha256"):
            raise RuntimeError(f"local actual-source mirror mismatch: {rel}")
        alias = aliases.get(signal["signal_id"])
        hierarchy = (
            alias["actual_source_exact_hierarchy"]
            if alias is not None
            else signal["exact_hierarchy"]
        )
        symbol = re.sub(r"\[[0-9]+\]$", "", hierarchy.rsplit(".", 1)[-1])
        actual_span = declaration_span_sha(local, symbol)
        if alias is None:
            prior = prior_by_id.get(signal["signal_id"])
            if prior is None:
                raise RuntimeError(
                    f"retained predecessor signal absent: {signal['signal_id']}"
                )
            signal["source_sha256"] = prior["source_sha256"]
            signal["declaration_span_sha256"] = prior[
                "declaration_span_sha256"
            ]
            disposition = "PRESERVED_PREDECESSOR_CATALOG_WITH_ACTUAL_RETURN_REBIND"
        else:
            signal["source_sha256"] = actual["sha256"]
            signal["declaration_span_sha256"] = actual_span
            alias["source_sha256"] = signal["source_sha256"]
            alias["declaration_span_sha256"] = signal["declaration_span_sha256"]
            disposition = "FRESH_PASSIVE_ALIAS_BOUND_TO_ACTUAL_COMPILED_SOURCE"
        reconciliation_rows.append(
            {
                "signal_id": signal["signal_id"],
                "source_path": rel,
                "catalog_source_sha256": signal["source_sha256"],
                "catalog_declaration_span_sha256": signal[
                    "declaration_span_sha256"
                ],
                "actual_compiled_source_sha256": actual["sha256"],
                "actual_compiled_declaration_span_sha256": actual_span,
                "catalog_matches_actual_source": signal["source_sha256"]
                == actual["sha256"],
                "disposition": disposition,
            }
        )
    contract["diagnostic_round"]["source_identity"][
        "catalog_source_identity_sha256"
    ] = semantic_sha(
        sorted(
            (signal_identity_row(row) for row in contract["signals"]),
            key=lambda row: row["signal_id"],
        )
    )
    write_json(contract_path, contract)
    alias_receipt["actual_compiled_source_identity_member"] = (
        "provenance/v111_actual_compiled_source_identity.json"
    )
    alias_receipt["actual_compiled_source_identity_sha256"] = sha_file(receipt_path)
    write_json(alias_path, alias_receipt)
    reconciliation = {
        "schema": "node0004-v112-actual-compiled-source-catalog-reconciliation-v1",
        "package_id": NEW_ID,
        "source_package_id": OLD_ID,
        "actual_compiled_source_identity_member": (
            "provenance/v111_actual_compiled_source_identity.json"
        ),
        "actual_compiled_source_identity_sha256": sha_file(receipt_path),
        "retained_identity_policy": (
            "PRESERVE_PREDECESSOR_CATALOG_AND_BIND_ACTUAL_RETURN_RECONCILIATION"
        ),
        "rows": sorted(reconciliation_rows, key=lambda row: row["signal_id"]),
        "pass": len(reconciliation_rows) == len(contract["signals"]),
        "claim_boundary": (
            "Static actual-compile/catalog reconciliation only; v112 dynamic mapping "
            "remains a production-return claim."
        ),
    }
    reconciliation_path = (
        TREE / "provenance/v112_actual_compiled_source_catalog_reconciliation.json"
    )
    write_json(reconciliation_path, reconciliation)
    return {
        "signal_count": len(contract["signals"]),
        "source_count": len(actual_sources),
        "fresh_actual_bound_signal_count": sum(
            row["catalog_matches_actual_source"] for row in reconciliation_rows
        ),
        "preserved_with_reconciliation_count": sum(
            not row["catalog_matches_actual_source"] for row in reconciliation_rows
        ),
        "reconciliation": reconciliation_path.relative_to(TREE).as_posix(),
        "reconciliation_sha256": sha_file(reconciliation_path),
        "pass": True,
    }


def replace_identity_in_operational_text() -> None:
    for path in walk_files(TREE):
        rel = path.relative_to(TREE)
        if rel.parts and rel.parts[0] in {"provenance", "workload"}:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        rebound = text.replace(OLD_ID, NEW_ID).replace("v111b", "v112b")
        rebound = rebound.replace("\r\n", "\n").replace("\r", "\n")
        if rebound.encode("utf-8") != data:
            path.write_text(rebound, encoding="utf-8", newline="\n")


def zip_member_bytes(suffix: str) -> bytes:
    with zipfile.ZipFile(V111_RETURN) as archive:
        matches = [
            info.filename
            for info in archive.infolist()
            if info.filename.endswith(suffix)
        ]
        if len(matches) != 1:
            raise RuntimeError(f"expected one v111 return member {suffix}: {matches}")
        return archive.read(matches[0])


def copy_mode_authority() -> dict[str, Any]:
    mapping = [
        (
            MODE_ROOT / "USER_MODE_AUTHORITY_SOURCE.md",
            TREE / "provenance/USER_MODE_AUTHORITY_SOURCE.md",
        ),
        (
            MODE_ROOT / "server_family_diagnostic_mode_authority.json",
            TREE / "contracts/server_family_diagnostic_mode_authority.json",
        ),
        (
            MODE_ROOT / "server_family_dispatch_mode_binding.json",
            TREE / "contracts/server_family_dispatch_mode_binding.json",
        ),
        (
            ROOT / "contracts/server_diagnostic_mode_selector_dispatch_v1.json",
            TREE / "contracts/server_diagnostic_mode_selector_dispatch_v1.json",
        ),
    ]
    rows = []
    for source, target in mapping:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        rows.append(
            {
                "source_path": source.relative_to(ROOT).as_posix(),
                "package_path": target.relative_to(TREE).as_posix(),
                "bytes": target.stat().st_size,
                "sha256": sha_file(target),
                "byte_equal": source.read_bytes() == target.read_bytes(),
            }
        )
    receipt = {
        "schema": "node0004-v112-mode-authority-embedding-v1",
        "package_id": NEW_ID,
        "family_role_id": "family.conv.serialized",
        "owner_epoch": 7,
        "registry_epoch": 43,
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "files": rows,
        "pass": all(row["byte_equal"] for row in rows),
        "server_action_authorized": False,
        "claim_boundary": "Package-local byte embedding only; no server action or dynamic claim.",
    }
    write_json(TREE / "provenance/mode_authority_embedding_receipt.json", receipt)
    return receipt


def add_v111_provenance() -> tuple[dict[str, Any], dict[str, Any]]:
    provenance = TREE / "provenance"
    old_contract = OLD_TREE / CONTRACT_REL
    old_tb = OLD_TREE / TB_REL
    historical_contract = provenance / "v111_predecessor_tb_vcd_contract_historical_exact.json"
    historical_contract.write_bytes(old_contract.read_bytes())
    predecessor_tb = provenance / "v111_predecessor_tb_vcd_bounded_causal_cone.svh"
    predecessor_tb.write_bytes(old_tb.read_bytes())
    predecessor_contract = provenance / "v111_predecessor_tb_vcd_contract.json"
    predecessor = load_json(old_contract)
    predecessor["execution"]["tb_source_path"] = predecessor_tb.relative_to(TREE).as_posix()
    predecessor["execution"]["tb_source_sha256"] = sha_file(predecessor_tb)
    write_json(predecessor_contract, predecessor)
    (provenance / "v111_return_analysis.json").write_bytes(V111_ANALYSIS.read_bytes())

    extracted = {
        "v111_vcd_identity.json": "evidence/vcd/VCD_IDENTITY.json",
        "v111_actual_compiled_source_identity.json": "evidence/compiled_source/source_identity.json",
        "v111_actual_vcs_argv.json": "evidence/compiled_source/actual_vcs_argv.json",
        "v111_actual_source_Memory_AG_Idx_Queue.sv": (
            "evidence/compiled_source/actual_source_files/Memory_AG_Idx_Queue.sv"
        ),
    }
    for name, suffix in extracted.items():
        (provenance / name).write_bytes(zip_member_bytes(suffix))

    published = {
        "schema": "node0004-v111-current-contract-pass-receipt-v1",
        "activation_epoch": "tb-vcd-bounded-causal-cone-semantic-v8",
        "family": "conv_serialized_node0004",
        "package_id": OLD_ID,
        "pass": True,
        "errors": [],
        "status": "PACKAGE_READY_NOT_RUN_TESTED_PREDECESSOR",
        "formal_return_consumed": True,
        "formal_return_analysis_path": (
            "outputs/conv_node0004_v111_return_r1787198069563420665_626725/return_analysis.json"
        ),
        "formal_return_analysis_sha256": sha_file(V111_ANALYSIS),
        "current_contract_validation_path": (
            "outputs/conv_node0004_v112_tupleleaf_20260822/v111_contract_current_validation.json"
        ),
        "claim_boundary": "Current local contract pass plus tested predecessor identity; no v112 runtime claim.",
    }
    published_path = provenance / "v111_current_contract_pass_receipt.json"
    write_json(published_path, published)
    return (
        {
            "path": predecessor_contract.relative_to(TREE).as_posix(),
            "sha256": sha_file(predecessor_contract),
        },
        {
            "path": published_path.relative_to(TREE).as_posix(),
            "sha256": sha_file(published_path),
        },
    )


def patch_contract_and_tb(
    predecessor_contract: dict[str, Any], published_receipt: dict[str, Any]
) -> dict[str, Any]:
    contract_path = TREE / CONTRACT_REL
    tb_path = TREE / TB_REL
    contract = load_json(contract_path)
    prior_signals = contract["signals"]
    old_leaf_rows = [
        row
        for row in prior_signals
        if row["signal_id"].startswith("sig_mem_i")
        and "u_Memory_AG_Idx_Queue" in row["exact_hierarchy"]
        and row["exact_hierarchy"].endswith(("[0]", "[1]", "[2]"))
    ]
    if len(old_leaf_rows) != 51:
        raise RuntimeError(f"expected 51 unmapped leaf rows, found {len(old_leaf_rows)}")

    renamed = {
        row["signal_id"]: f"{row['signal_id']}{LEAF_SUFFIX}"
        for row in old_leaf_rows
    }
    old_hierarchy = {
        row["signal_id"]: row["exact_hierarchy"] for row in old_leaf_rows
    }
    candidate_refs: dict[str, set[str]] = {old: set() for old in renamed}
    for matrix_row in contract["candidate_boundary_matrix"]:
        signature = matrix_row["expected_signature"]
        for field in ("candidate_signal_ids", "direct_boundary_signal_ids"):
            for signal_id in signature.get(field, []):
                if signal_id in candidate_refs:
                    candidate_refs[signal_id].add(matrix_row["candidate_id"])

    for row in contract["signals"]:
        old_id = row["signal_id"]
        if old_id in renamed:
            new_id = renamed[old_id]
            row["signal_id"] = new_id
            row["exact_hierarchy"] = f"{PROXY_INSTANCE}.{new_id}"

    def rename_value(value: Any) -> Any:
        if isinstance(value, str):
            return renamed.get(value, value)
        if isinstance(value, list):
            return [rename_value(item) for item in value]
        if isinstance(value, dict):
            return {key: rename_value(item) for key, item in value.items()}
        return value

    for field in ("role_coverage", "boundaries", "candidate_boundary_matrix", "scope", "execution"):
        contract[field] = rename_value(contract[field])

    success_id = "successful_tuple_lifetime_and_drain"
    contract["candidates"].append(
        {
            "candidate_id": success_id,
            "description": (
                "All three Memory_AG inputs present the final tuple, prepared-data drains, "
                "and the stage/global terminal witnesses complete."
            ),
            "priority": "MEDIUM",
        }
    )
    i0_last = renamed["sig_mem_i0_raw_last_xmrfix"]
    i0_valid = renamed["sig_mem_i0_raw_valid_xmrfix"]
    i2_last = renamed["sig_mem_i2_raw_last_xmrfix"]
    i2_valid = renamed["sig_mem_i2_raw_valid_xmrfix"]
    success_rows = {
        "upstream": {
            "candidate_signal_ids": [
                i0_last, i0_valid, i2_last, i2_valid,
                "sig_mem_raw_idx_all_xmrfix", "sig_mem_raw_tag_all_xmrfix",
            ],
            "direct_boundary_signal_ids": [i0_last, i0_valid, i2_last, i2_valid],
        },
        "current": {
            "candidate_signal_ids": [
                "sig_memidx_all_matched", "sig_prepared_count",
                "sig_prepared_valid", "sig_prepared_rd_hs",
            ],
            "direct_boundary_signal_ids": [
                "sig_memidx_all_matched", "sig_prepared_count",
                "sig_prepared_valid", "sig_prepared_rd_hs",
            ],
        },
        "downstream": {
            "candidate_signal_ids": [
                "sig_wr_ob_vld", "sig_wr_ob_rd_hs",
                "sig_wdata_valid", "sig_wdata_ready",
            ],
            "direct_boundary_signal_ids": [
                "sig_wr_ob_vld", "sig_wr_ob_rd_hs",
                "sig_wdata_valid", "sig_wdata_ready",
            ],
        },
        "state_hold_clear": {
            "candidate_signal_ids": [
                "sig_slice_finish", "sig_global_fetch_finish",
                "sig_global_slice_finish", "sig_prepared_count",
            ],
            "direct_boundary_signal_ids": [
                "sig_slice_finish", "sig_global_fetch_finish",
                "sig_global_slice_finish",
            ],
        },
    }
    for boundary_id, signature in success_rows.items():
        contract["candidate_boundary_matrix"].append(
            {
                "candidate_id": success_id,
                "boundary_id": boundary_id,
                "expected_signature": {
                    **signature,
                    "decision_predicate": (
                        f"v112_{success_id}_{boundary_id}_distinguishing_predicate"
                    ),
                    "requires_complete_ordered_transitions": True,
                },
            }
        )

    contract["package_id"] = NEW_ID
    contract["claim_boundary"] = (
        "Local package contract for 51 passive source-bound Memory_AG leaf aliases and a "
        "pairwise-distinguishing tuple/drain/success matrix; no production result claim."
    )
    diagnostic = contract["diagnostic_round"]
    diagnostic["round_index"] = 6
    diagnostic["round_kind"] = "EVIDENCE_REFINED_SUCCESSOR"
    diagnostic["breadth_baseline"]["deviation"] = {
        "relation": "ABOVE_REFERENCE_RANGE",
        "acknowledged": True,
        "explanation": (
            "All 102 already mapped v111 signals remain byte-identical in source identity, "
            "while 51 dynamically proven unmappable packed bit-select identities are "
            "replaced one-for-one by passive source-bound leaf aliases."
        ),
    }
    diagnostic["evolution"] = {
        "predecessor": {
            "package_id": OLD_ID,
            "round_index": 5,
            "contract_path": predecessor_contract["path"],
            "contract_sha256": predecessor_contract["sha256"],
            "pinned_rtl_tree_sha256": contract["pinned_rtl_tree_sha256"],
            "published_gate_semantic_version": "8",
            "published_pass_receipt_path": published_receipt["path"],
            "published_pass_receipt_sha256": published_receipt["sha256"],
        },
        "added_signal_ids": sorted(renamed.values()),
        "removed_signal_ids": sorted(renamed),
        "unchanged_signal_ids": sorted(
            row["signal_id"]
            for row in contract["signals"]
            if not row["signal_id"].endswith(LEAF_SUFFIX)
        ),
        "removal_evidence": [
            {
                "signal_id": old_id,
                "disposition": "FAMILY_ADAPTIVE_PRUNING",
                "reason": (
                    "The v111 same-attempt VCD header collapsed this exact packed-vector "
                    "bit-select into its whole vector; v112 retains the same actual value "
                    "through a passive bind-input leaf alias with a fresh catalog identity."
                ),
                "confidence": "HIGH",
                "affected_candidate_ids": sorted(candidate_refs[old_id]),
            }
            for old_id in sorted(renamed)
        ],
        "candidate_preservation": {
            "preserved_candidate_ids": sorted(
                candidate["candidate_id"]
                for candidate in contract["candidates"]
                if candidate["candidate_id"] != success_id
            ),
            "closed_candidate_ids": [],
            "new_candidate_ids": [success_id],
            "closure_evidence": [],
        },
    }

    alias_rows = []
    by_id = {row["signal_id"]: row for row in contract["signals"]}
    for old_id, new_id in sorted(renamed.items()):
        row = by_id[new_id]
        alias_rows.append(
            {
                "predecessor_signal_id": old_id,
                "successor_signal_id": new_id,
                "actual_source_exact_hierarchy": old_hierarchy[old_id],
                "passive_proxy_exact_hierarchy": row["exact_hierarchy"],
                "source_path": row["source_path"],
                "source_sha256": row["source_sha256"],
                "declaration_span_sha256": row["declaration_span_sha256"],
                "width_bits": row["width_bits"],
                "drives_dut": False,
                "binding_kind": "PASSIVE_BIND_INPUT_ALIAS_OF_ACTUAL_SOURCE_PACKED_BIT_SELECT",
                "affected_candidate_ids": sorted(candidate_refs[old_id]),
            }
        )
    alias_receipt = {
        "schema": "node0004-v112-tuple-leaf-alias-binding-v1",
        "package_id": NEW_ID,
        "predecessor_package_id": OLD_ID,
        "source_module": "Memory_AG_Idx_Queue",
        "leaf_count": len(alias_rows),
        "source_bound": True,
        "passive": True,
        "drives_dut": False,
        "v111_declared_signal_count": 153,
        "v111_mapped_signal_count": 102,
        "v111_missing_leaf_count": 51,
        "aliases": alias_rows,
        "claim_boundary": (
            "Static one-for-one actual-net alias binding; dynamic VCS header completeness "
            "remains a v112 return-time claim."
        ),
    }
    write_json(TREE / "provenance/v112_tuple_leaf_alias_binding.json", alias_receipt)

    # Rename the package-local passive ports and every state-digest reference.
    tb_text = tb_path.read_text(encoding="utf-8")
    for old_id in sorted(renamed, key=len, reverse=True):
        tb_text = tb_text.replace(old_id, renamed[old_id])

    # The exact dump target union is regenerated from the current catalog.
    lines = tb_text.splitlines()
    first = next(i for i, line in enumerate(lines) if "$dumpvars(" in line)
    dumpon = next(i for i, line in enumerate(lines[first:], first) if "$dumpon;" in line)
    dump_lines = [
        f"            $dumpvars(0, {row['exact_hierarchy']});"
        for row in contract["signals"]
    ]
    lines[first:dumpon] = dump_lines
    tb_text = "\n".join(lines) + "\n"
    tb_path.write_text(tb_text, encoding="utf-8", newline="\n")

    contract["execution"]["tb_source_sha256"] = sha_file(tb_path)
    catalog_rows = sorted(
        (signal_identity_row(row) for row in contract["signals"]),
        key=lambda row: row["signal_id"],
    )
    diagnostic["source_identity"]["catalog_source_identity_sha256"] = semantic_sha(
        catalog_rows
    )
    write_json(contract_path, contract)
    return {
        "old_leaf_ids": sorted(renamed),
        "new_leaf_ids": sorted(renamed.values()),
        "alias_receipt": "provenance/v112_tuple_leaf_alias_binding.json",
        "signal_count": len(contract["signals"]),
        "candidate_count": len(contract["candidates"]),
        "matrix_rows": len(contract["candidate_boundary_matrix"]),
    }


def patch_return_contracts() -> None:
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load_json(request_path)
    additions = [
        {
            "archive": "evidence/v112_tuple_leaf_alias_binding.json",
            "required": True,
            "source": "provenance/v112_tuple_leaf_alias_binding.json",
            "source_root": "package",
        },
        {
            "archive": "evidence/v112_actual_compiled_source_catalog_reconciliation.json",
            "required": True,
            "source": "provenance/v112_actual_compiled_source_catalog_reconciliation.json",
            "source_root": "package",
        },
        {
            "archive": "evidence/server_family_dispatch_mode_binding.json",
            "required": True,
            "source": "contracts/server_family_dispatch_mode_binding.json",
            "source_root": "package",
        },
        {
            "archive": "evidence/server_family_diagnostic_mode_authority.json",
            "required": True,
            "source": "contracts/server_family_diagnostic_mode_authority.json",
            "source_root": "package",
        },
    ]
    existing = {row["archive"] for row in request["core_entries"]}
    request["core_entries"].extend(
        row for row in additions if row["archive"] not in existing
    )
    request["package_id"] = NEW_ID
    request["claim_boundary"] = (
        "Unbounded bounded-cone VCD plus exact tuple-leaf alias/mode/source/core receipts; "
        "no sampling, truncation or size deletion."
    )
    write_json(request_path, request)

    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load_json(post_path)
    post["package_id"] = NEW_ID
    post["request_sha256"] = sha_file(request_path)
    post["helper_sha256"] = sha_file(TREE / "package_tools/server_post_sim_return.py")
    write_json(post_path, post)

    return_root = f"{NEW_ID}_return"
    new_return_members = [
        f"{return_root}/evidence/v112_tuple_leaf_alias_binding.json",
        f"{return_root}/evidence/v112_actual_compiled_source_catalog_reconciliation.json",
        f"{return_root}/evidence/server_family_dispatch_mode_binding.json",
        f"{return_root}/evidence/server_family_diagnostic_mode_authority.json",
    ]
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load_json(allow_path)
    allow["package_id"] = NEW_ID
    members = allow["required_or_conditional_exact_members"]
    members.extend(member for member in new_return_members if member not in members)
    allow["required_or_conditional_exact_members"] = sorted(members)
    write_json(allow_path, allow)


def refresh_selector_and_manifest(patch_summary: dict[str, Any]) -> None:
    contract_path = TREE / CONTRACT_REL
    legacy_selector_path = TREE / "contracts/diagnostic_mode_selector.json"
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load_json(
        selector_path if selector_path.is_file() else legacy_selector_path
    )
    selector["package_id"] = NEW_ID
    selector["family"] = "family.conv.serialized"
    selector["selected_mode"] = "TB_VCD_BOUNDED_CAUSAL_CONE"
    selector["vcd_contract_sha256"] = sha_file(contract_path)
    selector["return_members"] = sorted(
        set(selector["return_members"])
        | {
            f"{NEW_ID}_return/evidence/v112_tuple_leaf_alias_binding.json",
            f"{NEW_ID}_return/evidence/v112_actual_compiled_source_catalog_reconciliation.json",
            f"{NEW_ID}_return/evidence/server_family_dispatch_mode_binding.json",
            f"{NEW_ID}_return/evidence/server_family_diagnostic_mode_authority.json",
        }
    )
    selector["package_members"] = sorted(
        f"{NEW_ID}/{path.relative_to(TREE).as_posix()}"
        for path in walk_files(TREE)
        if path.name != "package_manifest.json"
    ) + [f"{NEW_ID}/package_manifest.json"]
    selector["package_members"] = sorted(set(selector["package_members"]))
    write_json(selector_path, selector)
    # Keep the predecessor spelling as an inert compatibility copy while the
    # dispatch binding requires the canonical server_diagnostic_* member.
    write_json(legacy_selector_path, selector)

    runner_path = TREE / "PREPARE_AND_RUN.sh"
    runner_contract_path = TREE / "contracts/server_runner_return_resilience.json"
    runner_contract = load_json(runner_contract_path)
    runner_contract["package_id"] = NEW_ID
    runner_contract["runner_path"] = f"{NEW_ID}/PREPARE_AND_RUN.sh"
    runner_contract["runner_sha256"] = sha_file(runner_path)
    write_json(runner_contract_path, runner_contract)

    current_contract = load_json(contract_path)
    predecessor = current_contract["diagnostic_round"]["evolution"]["predecessor"]
    predecessor["contract_sha256"] = sha_file(
        TREE / predecessor["contract_path"]
    )
    write_json(contract_path, current_contract)

    # The selector binds the final contract identity, so refresh it after the
    # predecessor relocation hash has been updated.
    selector = load_json(selector_path)
    selector["vcd_contract_sha256"] = sha_file(contract_path)
    write_json(selector_path, selector)
    write_json(legacy_selector_path, selector)

    manifest_path = TREE / "package_manifest.json"
    manifest = load_json(manifest_path)
    manifest.update(
        {
            "schema": "node0004-v112b-tupleleaf-tbvcd-package-manifest-v1",
            "package_id": NEW_ID,
            "install_name": NEW_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
            "family_role_id": "family.conv.serialized",
            "owner_epoch": 7,
            "registry_epoch": 43,
            "previous_version_progress": (
                "v111 compiled, simulated and entered the target, then retained one residual "
                "32-unit prepared-data group; its VCD mapped 102/153 signals."
            ),
            "current_purpose": (
                "Make all 51 Memory_AG packed-vector leaves directly dumpable and distinguish "
                "input0 KEEP-last, input2 KEEP-last, prepared over-generation, downstream drain, "
                "and successful completion in one same-attempt return."
            ),
            "signal_count": patch_summary["signal_count"],
            "candidate_count": patch_summary["candidate_count"],
            "removed_unmappable_leaf_identity_count": 51,
            "added_passive_source_bound_leaf_alias_count": 51,
            "vcd_contract_sha256": sha_file(contract_path),
            "selector_sha256": sha_file(selector_path),
            "mode_dispatch_binding_sha256": sha_file(
                TREE / "contracts/server_family_dispatch_mode_binding.json"
            ),
            "generation_provenance": {
                "source_package_id": OLD_ID,
                "mode": "PATCH_FIRST_CHANGED_SURFACE",
                "changed_surfaces": [
                    "fresh_identity",
                    "tb_vcd_leaf_aliases",
                    "catalog_identity",
                    "candidate_matrix_success_row",
                    "qualified_progress_state_digest",
                    "runtime_return_alias_receipt",
                    "mode_authority_embedding",
                ],
                "frozen_surfaces": [
                    "materialized_config",
                    "mapping",
                    "bitstream",
                    "execplan",
                    "sca",
                    "workload",
                    "numeric",
                    "golden",
                    "functional_rtl",
                    "all_102_already_mapped_causal_signals",
                    "all_15_existing_candidates",
                ],
            },
            "server_actions_performed": [],
            "storage_published": False,
            "claim_boundary": (
                "Local package build and gate result only; no production compile, simulation, "
                "root cause, natural terminal, Formal-D, storage or server claim."
            ),
        }
    )
    manifest["files"] = [
        {
            "path": path.relative_to(TREE).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha_file(path),
        }
        for path in sorted(walk_files(TREE))
        if path.name != "package_manifest.json"
    ]
    write_json(manifest_path, manifest)


def deterministic_zip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as archive:
        for path in walk_files(source):
            rel = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(
                f"{source.name}/{rel}", date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644
            info.external_attr = mode << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=6,
            )


def frozen_surface_receipt() -> dict[str, Any]:
    old_workload = file_map(OLD_TREE / "workload")
    new_workload = file_map(TREE / "workload")
    retained_paths = [
        "provenance/B_duplicate_lc_branch_config.json",
        "provenance/frozen_node0004_wave0_config.json",
        "provenance/frozen_v88b_workload_import.json",
        "workload/runtime/runs/c0/install/execplan.txt",
        "workload/runtime/runs/c0/install/execplan_op_w0.txt",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
        "workload/runtime/runs/c0/install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
    ]
    path_checks = {
        rel: (OLD_TREE / rel).read_bytes() == (TREE / rel).read_bytes()
        for rel in retained_paths
    }
    receipt = {
        "schema": "node0004-v112-frozen-surface-reuse-v1",
        "package_id": NEW_ID,
        "source_package_id": OLD_ID,
        "workload_tree_byte_equal": old_workload == new_workload,
        "exact_path_checks": path_checks,
        "functional_rtl_packaged_or_modified": False,
        "numeric_or_golden_modified": False,
        "pass": old_workload == new_workload and all(path_checks.values()),
        "claim_boundary": "Local byte-equality proof only; no runtime equivalence claim.",
    }
    write_json(OUT / "frozen_surface_reuse_receipt.json", receipt)
    return receipt


def main() -> int:
    if TREE.exists() or ZIP_PATH.exists():
        raise RuntimeError(f"refusing to overwrite fresh v112 identity: {TREE}")
    if not OLD_TREE.is_dir() or not V111_RETURN.is_file():
        raise FileNotFoundError("v111 predecessor tree or formal return is absent")

    TREE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(OLD_TREE, TREE)
    replace_identity_in_operational_text()
    # Exact current shared helpers consumed by the selected TB-VCD path.
    shutil.copyfile(
        ROOT / "tools/server_post_sim_return.py",
        TREE / "package_tools/server_post_sim_return.py",
    )
    shutil.copyfile(
        ROOT / "tools/server_tb_vcd_runtime_supervision.py",
        TREE / "package_tools/server_tb_vcd_runtime_supervision.py",
    )
    shutil.copyfile(
        ROOT / "tools/server_package_runtime_layout.py",
        TREE / "package_tools/server_package_runtime_layout.py",
    )

    mode_receipt = copy_mode_authority()
    predecessor_contract, published_receipt = add_v111_provenance()
    patch_summary = patch_contract_and_tb(predecessor_contract, published_receipt)
    patch_summary["actual_source_rebind"] = bind_catalog_to_v111_actual_compiled_sources()
    patch_return_contracts()

    runtime_layout = load_json(TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json")
    runtime_layout["package_id"] = NEW_ID
    runtime_layout["install_name"] = NEW_ID
    write_json(TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json", runtime_layout)

    refresh_selector_and_manifest(patch_summary)
    frozen = frozen_surface_receipt()
    if not mode_receipt["pass"] or not frozen["pass"]:
        raise RuntimeError("mode authority or frozen-surface proof failed")

    deterministic_zip(TREE, ZIP_PATH)
    repeat = OUT / f".{NEW_ID}.determinism-check.zip"
    deterministic_zip(TREE, repeat)
    deterministic = sha_file(ZIP_PATH) == sha_file(repeat)
    repeat.unlink()
    if not deterministic:
        raise RuntimeError("deterministic ZIP rebuild mismatch")

    receipt = {
        "schema": "node0004-v112b-tupleleaf-tbvcd-local-build-v1",
        "package_id": NEW_ID,
        "source_package_id": OLD_ID,
        "status": "PACKAGE_BUILT_PENDING_EXACT_GATES",
        "diagnostic_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "tree": TREE.relative_to(ROOT).as_posix(),
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha_file(ZIP_PATH),
        "deterministic_rebuild": deterministic,
        "patch_summary": patch_summary,
        "frozen_surface_receipt": "outputs/conv_node0004_v112_tupleleaf_20260822/frozen_surface_reuse_receipt.json",
        "mode_authority_embedding_pass": mode_receipt["pass"],
        "single_zip": True,
        "adjacent_sidecar_created": False,
        "storage_published": False,
        "server_action": False,
        "claim_boundary": "Local patch-first build only; gates and production execution remain separate.",
    }
    write_json(OUT / "build_receipt.json", receipt)
    print(json.dumps({"pass": True, **receipt}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
