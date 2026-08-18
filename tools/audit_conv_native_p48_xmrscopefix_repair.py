#!/usr/bin/env python3
"""Exact p47-return XMRE negative/positive control for the p48 repair."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
P47 = "r5_n4_0cc_p47_tbvcdcone"
P48 = "r5_n4_0cc_p48_xmrscopefix"
P47_ZIP = ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/pending/{P47}.zip"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release"
P48_ZIP = OUT / f"{P48}.zip"
P48_TREE = OUT / "build" / P48
RECEIPT = OUT / "gates/p47_xmr_scope_repair.json"
TB_REL = "tb_probe/native_mse4_bounded_causal_cone_vcd.sv"
BAD = tuple(f".MSE_INST[{index}].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish" for index in (5, 6, 7))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def zip_bytes(path: Path, package: str, relative: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        name = f"{package}/{relative}"
        if name not in archive.namelist():
            raise RuntimeError(f"missing ZIP member: {name}")
        return archive.read(name)


def normalized_json(payload: bytes, package: str) -> Any:
    value = json.loads(payload)

    def walk(item: Any) -> Any:
        if isinstance(item, dict):
            return {key: walk(child) for key, child in item.items() if key not in {"tb_source_sha256"}}
        if isinstance(item, list):
            return [walk(child) for child in item]
        if isinstance(item, str):
            return item.replace(package, "<PACKAGE>")
        return item

    return walk(value)


def workload_map(path: Path, package: str) -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts
            if len(parts) < 3 or parts[0] != package or parts[1] != "workload":
                continue
            relative = PurePosixPath(*parts[1:]).as_posix()
            digest = hashlib.sha256()
            with archive.open(info) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            result[relative] = (info.file_size, digest.hexdigest())
    return result


def main() -> int:
    old_tb = zip_bytes(P47_ZIP, P47, TB_REL).decode("utf-8")
    new_tb_tree = (P48_TREE / TB_REL).read_text(encoding="utf-8")
    new_tb_zip = zip_bytes(P48_ZIP, P48, TB_REL).decode("utf-8")
    expected_new = "\n".join(line for line in old_tb.splitlines() if not any(token in line for token in BAD)) + "\n"
    synthetic_bad = new_tb_tree.replace(
        "      $dumpvars(0, tb_NDP_Top_new_phy.slice2gexec_ready_mon);",
        "      $dumpvars(0, tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[5].WR_MSE.u_Memory_WR_Stream_Engine.slice_cmpt_finish);\n"
        "      $dumpvars(0, tb_NDP_Top_new_phy.slice2gexec_ready_mon);",
    )
    negative_detector = lambda source: any(token in source for token in BAD)
    checks = {
        "p47_reproduces_exact_three_invalid_dump_scopes": sum(old_tb.count(token) for token in BAD) == 3 and all(old_tb.count(token) == 1 for token in BAD),
        "p48_tree_removes_all_invalid_dump_scopes": not negative_detector(new_tb_tree),
        "p48_zip_removes_all_invalid_dump_scopes": not negative_detector(new_tb_zip),
        "p48_change_is_exact_three_line_deletion": new_tb_tree == expected_new and new_tb_zip == expected_new,
        "selected_mse4_full_scope_preserved": "$dumpvars(0, tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine);" in new_tb_tree,
        "parent_stream_engine_aggregate_preserved": "$dumpvars(1, tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine);" in new_tb_tree,
        "slice_and_global_terminal_scopes_preserved": "u_Slice.u_Slice_Execution_Manager);" in new_tb_tree and "tb_NDP_Top_new_phy.slice2gexec_ready_mon);" in new_tb_tree,
        "negative_control_reinsertion_fails_closed": negative_detector(synthetic_bad),
        "workload_byte_equal": workload_map(P47_ZIP, P47) == workload_map(P48_ZIP, P48),
        "catalog_semantics_equal": normalized_json(zip_bytes(P47_ZIP, P47, "diagnostics/tb_vcd_causal_signal_catalog.json"), P47) == normalized_json(zip_bytes(P48_ZIP, P48, "diagnostics/tb_vcd_causal_signal_catalog.json"), P48),
        "candidate_matrix_semantics_equal": normalized_json(zip_bytes(P47_ZIP, P47, "diagnostics/tb_vcd_candidate_boundary_matrix.json"), P47) == normalized_json(zip_bytes(P48_ZIP, P48, "diagnostics/tb_vcd_candidate_boundary_matrix.json"), P48),
        "runner_identity_only_normalized_equal": zip_bytes(P48_ZIP, P48, "PREPARE_AND_RUN.sh").decode("utf-8").replace(P48, P47) == zip_bytes(P47_ZIP, P47, "PREPARE_AND_RUN.sh").decode("utf-8"),
        "formal_return_rootcause_bound": (P48_TREE / "diagnostics/p47_formal_return_rootcause.json").is_file(),
        "functional_rtl_absent": not any(PurePosixPath(name).parts[1:2] == ("rtl",) for name in zipfile.ZipFile(P48_ZIP).namelist()),
    }
    errors = [name for name, passed in checks.items() if not passed]
    value = {
        "schema": "conv-native-p48-xmr-scope-repair-audit-v1",
        "package_id": P48,
        "source_formal_package": P47,
        "pass": not errors,
        "checks": checks,
        "errors": errors,
        "p48_zip": {"path": P48_ZIP.relative_to(ROOT).as_posix(), "bytes": P48_ZIP.stat().st_size, "sha256": sha(P48_ZIP)},
        "repair_boundary": "Exactly three dump-only nonexistent MSE_INST[5..7] references are deleted; selected MSE4, aggregate scopes, workload, catalog, matrix, runner semantics and functional RTL remain frozen.",
        "claim_boundary": "Local exact-return negative/positive control only; it does not claim production compile or simulation success.",
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": value["pass"], "errors": errors}, ensure_ascii=False))
    return 0 if value["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
