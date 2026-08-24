#!/usr/bin/env python3
"""Exact-final-ZIP HDL/source-bound gate for serialized Conv v112."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v112b_tupleleaf_tbvcd"
TB_MEMBER = f"{PACKAGE}/tb_probe/tb_vcd_bounded_causal_cone.svh"
CONTRACT_MEMBER = f"{PACKAGE}/contracts/tb_vcd_bounded_causal_cone_contract.json"
ALIAS_MEMBER = f"{PACKAGE}/provenance/v112_tuple_leaf_alias_binding.json"
ACTUAL_SOURCE_MEMBER = (
    f"{PACKAGE}/provenance/v111_actual_compiled_source_identity.json"
)
ACTUAL_MEMORY_AG_MEMBER = (
    f"{PACKAGE}/provenance/v111_actual_source_Memory_AG_Idx_Queue.sv"
)
SOURCE_RECONCILIATION_MEMBER = (
    f"{PACKAGE}/provenance/"
    "v112_actual_compiled_source_catalog_reconciliation.json"
)
MODULE = "codex_node0004_tb_vcd_cone"
TARGET_PREFIX = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def focused_source(source: str) -> str:
    module = source.split("\n      bind ", 1)[0] + "\n"
    return re.sub(r"\$dumpvars\(0,\s*[^;]+\);", "$dumpvars;", module)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []

    with zipfile.ZipFile(args.zip) as archive:
        roots = {
            PurePosixPath(name).parts[0]
            for name in archive.namelist()
            if PurePosixPath(name).parts
        }
        if roots != {PACKAGE}:
            errors.append("zip_single_root_identity")
        bad_crc = archive.testzip()
        if bad_crc is not None:
            errors.append(f"zip_crc:{bad_crc}")
        tb_data = archive.read(TB_MEMBER)
        contract = json.loads(archive.read(CONTRACT_MEMBER))
        alias_receipt = json.loads(archive.read(ALIAS_MEMBER))
        actual_source_receipt = json.loads(archive.read(ACTUAL_SOURCE_MEMBER))
        actual_memory_ag = archive.read(ACTUAL_MEMORY_AG_MEMBER)
        source_reconciliation = json.loads(
            archive.read(SOURCE_RECONCILIATION_MEMBER)
        )

    source = tb_data.decode("utf-8", errors="strict")
    signals = contract.get("signals", [])
    signal_by_id = {row.get("signal_id"): row for row in signals}
    aliases = alias_receipt.get("aliases", [])
    alias_by_id = {row.get("successor_signal_id"): row for row in aliases}
    leaf_ids = sorted(sid for sid in signal_by_id if str(sid).endswith("_leafv112"))
    dump_hierarchies = re.findall(r"\$dumpvars\(0,\s*([^;]+)\);", source)
    catalog_hierarchies = [row.get("exact_hierarchy") for row in signals]

    # The authoritative identity is the source captured from the successful v111
    # production compile, not a potentially different local checkout.  Keep the
    # local hashes as informational evidence, while gating every catalog row
    # against the returned actual-compile identity receipt.
    actual_sources = {
        row["relative_path"]: row
        for row in actual_source_receipt.get("sources", [])
        if row.get("exists") is True
    }
    reconciliation_by_id = {
        row["signal_id"]: row
        for row in source_reconciliation.get("rows", [])
    }
    source_root = args.source_root.resolve()
    local_sources: dict[str, bytes] = {}
    source_errors: list[str] = []
    for row in signals:
        rel = str(row.get("source_path", ""))
        actual = actual_sources.get(rel)
        reconciliation = reconciliation_by_id.get(row.get("signal_id"))
        if actual is None:
            source_errors.append(f"{row.get('signal_id')}:actual_source_missing:{rel}")
        elif reconciliation is None:
            source_errors.append(f"{row.get('signal_id')}:reconciliation_missing")
        elif any(
            (
                reconciliation.get("source_path") != rel,
                reconciliation.get("catalog_source_sha256")
                != row.get("source_sha256"),
                reconciliation.get("catalog_declaration_span_sha256")
                != row.get("declaration_span_sha256"),
                reconciliation.get("actual_compiled_source_sha256")
                != actual.get("sha256"),
            )
        ):
            source_errors.append(f"{row.get('signal_id')}:reconciliation_identity")
        elif str(row.get("signal_id", "")).endswith("_leafv112") and (
            row.get("source_sha256") != actual.get("sha256")
            or reconciliation.get("disposition")
            != "FRESH_PASSIVE_ALIAS_BOUND_TO_ACTUAL_COMPILED_SOURCE"
        ):
            source_errors.append(f"{row.get('signal_id')}:fresh_alias_not_actual_bound")
        path = (source_root / rel).resolve()
        try:
            path.relative_to(source_root)
        except ValueError:
            source_errors.append(f"{row.get('signal_id')}:source_escape")
            continue
        if path.is_file():
            local_sources.setdefault(rel, path.read_bytes())

    alias_checks: dict[str, bool] = {}
    for sid in leaf_ids:
        signal = signal_by_id[sid]
        alias = alias_by_id.get(sid, {})
        actual = str(alias.get("actual_source_exact_hierarchy", ""))
        expected_rhs = actual.removeprefix(TARGET_PREFIX + ".")
        alias_checks[sid] = all(
            (
                alias.get("binding_kind")
                == "PASSIVE_BIND_INPUT_ALIAS_OF_ACTUAL_SOURCE_PACKED_BIT_SELECT",
                alias.get("passive_proxy_exact_hierarchy") == signal.get("exact_hierarchy"),
                alias.get("source_path") == signal.get("source_path"),
                alias.get("source_sha256") == signal.get("source_sha256"),
                alias.get("declaration_span_sha256")
                == signal.get("declaration_span_sha256"),
                alias.get("width_bits") == signal.get("width_bits"),
                alias.get("drives_dut") is False,
                actual.startswith(TARGET_PREFIX + ".u_Memory_AG_Idx_Queue."),
                re.search(r"\[[012]\]$", actual) is not None,
                f".{sid}({expected_rhs})" in source,
                signal.get("source_binding") == "ACTUAL_SOURCE_NET",
                signal.get("derived_expected_equation") is False,
                signal.get("drives_dut") is False,
            )
        )

    candidate_ids = [row.get("candidate_id") for row in contract.get("candidates", [])]
    boundary_ids = [row.get("boundary_id") for row in contract.get("boundaries", [])]
    matrix = contract.get("candidate_boundary_matrix", [])
    matrix_pairs = {(row.get("candidate_id"), row.get("boundary_id")) for row in matrix}
    expected_pairs = {(candidate, boundary) for candidate in candidate_ids for boundary in boundary_ids}
    # Pairwise distinguishability is a candidate property across the complete
    # four-boundary signature.  Requiring every individual row to be globally
    # unique incorrectly rejects legitimate reuse of one predicate at different
    # boundaries for the same candidate.
    candidate_signatures = {
        candidate: json.dumps(
            [
                {
                    "boundary_id": boundary,
                    "expected_signature": next(
                        row.get("expected_signature")
                        for row in matrix
                        if row.get("candidate_id") == candidate
                        and row.get("boundary_id") == boundary
                    ),
                }
                for boundary in boundary_ids
            ],
            sort_keys=True,
        )
        for candidate in candidate_ids
        if all(
            (candidate, boundary) in matrix_pairs for boundary in boundary_ids
        )
    }
    required_discriminators = {
        "memory_input0_keep_token_or_epoch_ends_early",
        "memory_input2_keep_token_or_epoch_ends_early",
        "buffer_data_generation_lifetime_overruns",
        "memory_wdata_drain_block",
        "successful_tuple_lifetime_and_drain",
    }

    checks = {
        "single_exact_module": source.count(f"module {MODULE}(") == 1,
        "target_bind_exact": f"bind {TARGET_PREFIX} {MODULE} codex_node0004_tb_vcd_cone_inst" in source,
        "signal_count_153": len(signals) == 153 == len(signal_by_id),
        "leaf_alias_count_51": len(leaf_ids) == len(aliases) == len(alias_by_id) == 51,
        "all_aliases_exact_and_passive": all(alias_checks.values()),
        "exact_dumpvars_union": len(dump_hierarchies) == 153
        and set(dump_hierarchies) == set(catalog_hierarchies),
        "standard_tasks_complete": all(
            token in source
            for token in ("$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush")
        ),
        "observer_never_drives_dut": not re.search(
            r"\b(?:assign|force)\s+sig_|\bsig_[A-Za-z0-9_]+\s*(?:<=|=(?!=))", source
        ),
        "retired_derived_ack_comparator_absent": "buf_idx_queue_bp_pre" not in source,
        "qualified_progress_only": all(
            token in source
            for token in (
                "sig_row_wr && !sig_row_full",
                "sig_row_rd && !sig_row_empty",
                "sig_col_wr && !sig_col_full",
                "sig_col_rd && !sig_col_empty",
                "sig_mem_req_valid & sig_mem_req_ready",
                "sig_wdata_valid & sig_wdata_ready",
                "sig_prepared_wr_hs || sig_prepared_rd_hs",
            )
        ),
        "plateau_requires_state_global_and_known": all(
            token in source
            for token in (
                "codex_state_previous",
                "codex_global_previous",
                "=== codex_state_previous",
                "=== codex_global_previous",
                "!== 1'bx",
            )
        ),
        "thresholds_exact": all(
            token in source
            for token in (
                "CODEX_SUSPECT_CYCLES = 64'd1048576",
                "CODEX_DUMPOFF_CYCLES = 64'd4194304",
                "CODEX_GRACE_CYCLES = 64'd262144",
            )
        ),
        "all_41_roles": len(contract.get("role_coverage", [])) == 41,
        "four_boundaries": len(boundary_ids) == 4,
        "matrix_complete": matrix_pairs == expected_pairs,
        "matrix_pairwise_distinguishable": len(candidate_signatures)
        == len(candidate_ids)
        == len(set(candidate_signatures.values())),
        "required_discriminators_present": required_discriminators.issubset(set(candidate_ids)),
        "actual_compiled_sources_bound": not source_errors
        and source_reconciliation.get("pass") is True
        and len(reconciliation_by_id) == len(signals)
        and actual_source_receipt.get("compile_exit") == 0
        and actual_source_receipt.get("status") == "COMPLETE"
        and bool(actual_source_receipt.get("actual_vcs_argv"))
        and bool(actual_source_receipt.get("filelists"))
        and bool(actual_source_receipt.get("include_tokens"))
        and sha(actual_memory_ag)
        == actual_sources.get(
            "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_AG_Idx_Queue.sv",
            {},
        ).get("sha256"),
    }
    errors.extend(name for name, passed in checks.items() if not passed)

    focus = focused_source(source)
    with tempfile.TemporaryDirectory(prefix="node0004-v112-hdl-") as temporary:
        root = Path(temporary)
        positive = root / "positive.sv"
        negative = root / "syntax_negative.sv"
        positive.write_text(focus, encoding="utf-8", newline="\n")
        negative.write_text(
            focus.replace("codex_owner_cycles = 0;", "codex_owner_cycles = ;", 1),
            encoding="utf-8",
            newline="\n",
        )
        command = [str(args.iverilog), "-g2012", "-tnull", "-s", MODULE]
        good = subprocess.run(
            command + [str(positive)], capture_output=True, text=True, timeout=60, check=False
        )
        bad = subprocess.run(
            command + [str(negative)], capture_output=True, text=True, timeout=60, check=False
        )
    if good.returncode != 0:
        errors.append("iverilog_exact_module_frontend_failed")
    if bad.returncode == 0:
        errors.append("syntax_negative_not_rejected")

    wrong_alias = dict(alias_by_id[leaf_ids[0]])
    wrong_alias["actual_source_exact_hierarchy"] = wrong_alias[
        "actual_source_exact_hierarchy"
    ].replace("[0]", "[3]", 1)
    negative_controls = {
        "syntax_negative_rejected": bad.returncode != 0,
        "missing_alias_rejected": len(aliases[:-1]) != 51,
        "wrong_lane_index_rejected": not str(
            wrong_alias["actual_source_exact_hierarchy"]
        ).endswith(("[0]", "[1]", "[2]")),
        "held_level_not_raw_progress": checks["qualified_progress_only"],
        "retired_ack_not_reintroduced": checks[
            "retired_derived_ack_comparator_absent"
        ],
    }
    if not all(negative_controls.values()):
        errors.append("negative_control_failure")

    report = {
        "schema": "node0004-v112-tupleleaf-tbvcd-hdl-source-bound-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "all_errors_collected": True,
        "checks": checks,
        "negative_controls": negative_controls,
        "probe": {"member": TB_MEMBER, "bytes": len(tb_data), "sha256": sha(tb_data)},
        "catalog": {
            "signal_count": len(signals),
            "leaf_alias_count": len(leaf_ids),
            "candidate_count": len(candidate_ids),
            "boundary_count": len(boundary_ids),
            "matrix_rows": len(matrix),
        },
        "source_files": {name: sha(data) for name, data in sorted(local_sources.items())},
        "actual_compiled_source_identity": {
            "member": ACTUAL_SOURCE_MEMBER,
            "compile_exit": actual_source_receipt.get("compile_exit"),
            "status": actual_source_receipt.get("status"),
            "source_count": len(actual_sources),
            "filelist_count": len(actual_source_receipt.get("filelists", [])),
            "include_count": len(actual_source_receipt.get("include_tokens", [])),
            "define_count": len(actual_source_receipt.get("define_tokens", [])),
            "parameter_count": len(actual_source_receipt.get("parameter_tokens", [])),
            "memory_ag_source_member": ACTUAL_MEMORY_AG_MEMBER,
            "memory_ag_source_sha256": sha(actual_memory_ag),
        },
        "source_catalog_reconciliation": {
            "member": SOURCE_RECONCILIATION_MEMBER,
            "pass": source_reconciliation.get("pass"),
            "row_count": len(reconciliation_by_id),
            "retained_identity_policy": source_reconciliation.get(
                "retained_identity_policy"
            ),
        },
        "source_errors": source_errors,
        "frontend": {
            "tool": str(args.iverilog.resolve()),
            "positive_exit": good.returncode,
            "positive_stderr": good.stderr[-4096:],
            "syntax_negative_exit": bad.returncode,
        },
        "claim_boundary": (
            "Exact-final-ZIP focused HDL frontend and local actual-source/passive-alias "
            "identity proof only; production VCS compile, mapping and runtime remain unclaimed."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
