#!/usr/bin/env python3
"""Independently validate the exact v66 config-lineage repair staging and ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
PRIOR = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"
GOOD = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
BAD = "a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0"
BITSTREAM = "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"
CONFIG = "provenance/config_lineage/op_tail_round_4_2.json"
CONTRACT = "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def leaves(value: Any, prefix: str = "$") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result.update(leaves(item, f"{prefix}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(leaves(item, f"{prefix}[{index}]"))
        return result
    return {prefix: value}


def safe_extract(source: Path, target: Path, expected_root: str) -> Path:
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"CRC failure: {source}")
        roots = {PurePosixPath(row.filename).parts[0] for row in archive.infolist() if row.filename}
        if roots != {expected_root}:
            raise ValueError(f"unexpected ZIP roots: {roots}")
        for row in archive.infolist():
            pure = PurePosixPath(row.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in row.filename:
                raise ValueError(f"unsafe member: {row.filename}")
            if stat.S_ISLNK(row.external_attr >> 16):
                raise ValueError(f"symlink member: {row.filename}")
            output = target.joinpath(*pure.parts)
            if row.is_dir():
                output.mkdir(parents=True, exist_ok=True)
            else:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(archive.read(row))
    return target / expected_root


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def subset_hashes(root: Path, prefixes: tuple[str, ...]) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha(path)
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).as_posix().startswith(prefixes)
    }


def validate_tree(package: Path, prior: Path) -> tuple[dict[str, bool], list[str], dict[str, Any]]:
    errors: list[str] = []
    checks: dict[str, bool] = {}
    manifest = load(package / "TEST_PACKAGE_MANIFEST.json")
    contract = load(package / CONTRACT)
    config = load(package / CONFIG)
    source = load(ROOT / "configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36/op_tail_round.json")
    native = load(ROOT / "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json")
    lhs, rhs = leaves(source), leaves(config)
    delta = [
        {"path": key, "old": lhs.get(key), "new": rhs.get(key)}
        for key in sorted(set(lhs) | set(rhs))
        if lhs.get(key) != rhs.get(key)
    ]
    expected_delta = [
        {"path": "$.buffer_loop_configs.GROUP2.COL_LC.end", "old": 32, "new": 4},
        {"path": "$.buffer_loop_configs.GROUP2.COL_LC.stride", "old": 16, "new": 2},
    ]
    bitstream = package / BITSTREAM
    sca = load(package / "workload/runtime/sca_cfg.json")
    sca_d = load(package / "workload/runtime/sca_cfg_D.json")
    dynamic = load(package / "diagnostics/qadd_config42_dynamic_acceptance.json")
    signal_ids = {row["signal_id"] for row in load(package / "diagnostics/tb_vcd_signal_catalog.json")["signals"]}
    required_dynamic_ids = {
        "sig_mrm_req_strb", "sig_mrm_req_valid", "sig_mrm_rreq_ready", "sig_mrm_rd_en",
        "sig_mrm_clear", "sig_valid_clear", "sig_valid_clr_mask", "sig_valid_buf",
        "sig_mrm_rvalid", "sig_mrm_rdata", "sig_data_out", "sig_slice_finish", "sig_global_done_pulse",
    }
    positive_a = ROOT / "outputs/qlinearadd_node0007_v66_tbvcdcfg42_release/config_lineage/positive_a/mapping/modules_dump_128b.bin"
    positive_b = ROOT / "outputs/qlinearadd_node0007_v66_tbvcdcfg42_release/config_lineage/positive_b/mapping/modules_dump_128b.bin"
    negative = ROOT / "outputs/qlinearadd_node0007_v66_tbvcdcfg42_release/config_lineage/negative_restore_32_16/mapping/modules_dump_128b.bin"
    frozen_prefixes = ("workload/runtime/install/op_tail_round/", "validation/golden/")
    checks.update(
        {
            "manifest_identity_exact": manifest.get("package_id") == PACKAGE and manifest.get("package_identity") == PACKAGE and manifest.get("install_name") == PACKAGE,
            "manifest_ready": manifest.get("status") == "PACKAGE_READY_NOT_RUN",
            "manifest_file_map_exact": manifest.get("files") == file_map(package),
            "authorized_leaf_delta_exact": delta == expected_delta == contract.get("authorized_leaf_deltas"),
            "native_4_2_authority_exact": config["buffer_loop_configs"]["GROUP2"]["COL_LC"] == native["buffer_loop_configs"]["GROUP2"]["COL_LC"],
            "fresh_mapping_reports_valid": all(load(ROOT / contract[key]["path"]).get("valid") is True for key in ("positive_mapping_a", "positive_mapping_b", "negative_restore_mapping")),
            "positive_recompute_byte_equal": positive_a.read_bytes() == positive_b.read_bytes() == bitstream.read_bytes(),
            "corrected_bitstream_exact": sha(bitstream) == GOOD == contract.get("packaged_bitstream_sha256"),
            "old_bad_bitstream_rejected": sha(negative) == BAD and BAD != sha(bitstream) and contract.get("rejected_bad_bitstream", {}).get("rejected") is True,
            "sca_selects_exact_bitstream": sca.get("op_tail_round_config", {}).get("path") == f"install/cfg_pkg/{PACKAGE}/install/cfg_pkg/{Path(BITSTREAM).name}",
            "sca_single_stage_exact": sca.get("Repeat_Num") == 1 and sca.get("Exec_Length") == 29,
            "sca_d_28_execution_bound": len(sca_d) == 28 and all(f"install/codex_runs/{PACKAGE}/{{attempt}}/" in row.get("path", "") for row in sca_d.values()),
            "dynamic_order_3333_then_cccc": [row.get("request_mask") for row in dynamic.get("required_ordered_sequence", [])] == ["0x33333333", "0xcccccccc"],
            "dynamic_both_accept_clear": all(row.get("require_accept") is True and row.get("require_clear") is True for row in dynamic.get("required_ordered_sequence", [])),
            "dynamic_second_alias_forbidden": dynamic.get("forbidden_between_first_and_second") == ["second_occurrence_request_mask=0x33333333"],
            "dynamic_actual_signals_source_bound": required_dynamic_ids <= signal_ids,
            "dynamic_downstream_terminal_formal_d": dynamic.get("downstream_requirements") == ["read_data", "output_progress", "natural_terminal_witness", "formal_D_return"],
            "positive_row_window_proof": all(contract.get("positive_checks", {}).values()),
            "all_32_16_and_alias_negative_controls_fail_closed": len(contract.get("negative_controls", {})) == 7 and all(row.get("exit_code") == 1 and row.get("failed_closed") is True for row in contract.get("negative_controls", {}).values()),
            "matrix_golden_byte_frozen": subset_hashes(prior, frozen_prefixes) == subset_hashes(package, frozen_prefixes),
            "execplan_byte_frozen": (prior / "workload/runtime/install/execplan.txt").read_bytes() == (package / "workload/runtime/install/execplan.txt").read_bytes() and (prior / "workload/runtime/install/execplan_op_tail_round.txt").read_bytes() == (package / "workload/runtime/install/execplan_op_tail_round.txt").read_bytes(),
            "functional_rtl_absent": not (package / "rtl").exists(),
            "diagnosis_authority_bound": contract.get("validated_root_cause") == "QADD_TAIL_ROUND_STALE_CONFIG_LINEAGE_REINTRODUCES_INTERLEAVED_COLUMN_ALIAS",
        }
    )
    for name, passed in checks.items():
        if not passed:
            errors.append(name)
    facts = {"authorized_leaf_deltas": delta, "bitstream_sha256": sha(bitstream), "signal_count": len(signal_ids), "sca_D_count": len(sca_d)}
    return checks, errors, facts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--repeat-zip", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="qadd-v66-config42-") as raw:
        temp = Path(raw)
        package = safe_extract(args.zip, temp / "current", PACKAGE)
        prior = safe_extract(args.prior_zip, temp / "prior", PRIOR)
        tree_checks, tree_errors, tree_facts = validate_tree(args.tree.resolve(), prior)
        zip_checks, zip_errors, zip_facts = validate_tree(package, prior)
        checks = {
            "staging": not tree_errors,
            "exact_final_zip": not zip_errors,
            "tree_zip_file_map_equal": file_map(args.tree.resolve()) == file_map(package),
            "deterministic_zip_recompute_equal": args.zip.read_bytes() == args.repeat_zip.read_bytes(),
            "v65_pending_preserved": sha(args.prior_zip) == "ed204d677bd379f30aba96c2a3d4c228a646dd8c885a9b07ebe545278948c800",
        }
        errors.extend(f"tree:{item}" for item in tree_errors)
        errors.extend(f"zip:{item}" for item in zip_errors)
        errors.extend(name for name, passed in checks.items() if not passed)
        report = {
            "schema": "qadd-v66-config42-exact-release-validation-v1",
            "package_id": PACKAGE,
            "status": "PASS" if not errors else "FAIL",
            "checks": checks,
            "staging_checks": tree_checks,
            "exact_zip_checks": zip_checks,
            "staging_facts": tree_facts,
            "exact_zip_facts": zip_facts,
            "package": identity(args.zip.resolve()),
            "prior_pending": identity(args.prior_zip.resolve()),
            "server_actions_performed": [],
            "pass": not errors,
            "errors": errors,
            "claim_boundary": "Local config materialization/roundtrip and exact package identity only; no production or E3-E5 claim.",
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"package_id": PACKAGE, "pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
