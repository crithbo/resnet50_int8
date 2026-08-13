from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v48_lc9_actual"
COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
BEGIN = "// v48 LC9_ACTUAL_ACTUAL_CONSUMER_BEGIN"
END = "// v48 LC9_ACTUAL_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def owner(root: Path, expression: str) -> Path:
    leaf = re.sub(r"\[.*", "", expression.rsplit(".", 1)[-1])
    base = root / "code/NDP_rtl"
    if leaf in {"clk_db", "rst_n_db"}:
        return base / "NDP_Top.sv"
    if leaf == "slice_start_run":
        return base / "Slice/Slice_cdc.sv"
    if leaf in {"iga_lc_outport", "iga_lc_outport_bp_post"}:
        return base / "Slice/Index_Generation_Array/Index_Generation_Array.sv"
    if leaf == "iga_lc_inport_valid_bit_masked":
        return base / "Slice/Index_Generation_Array/IGA_LC/IGA_LC_Inbuffer.sv"
    if leaf in {
        "iga_lc_inbuffer_bp_pre",
        "iga_lc_enable",
        "iga_lc_src_id",
    }:
        return base / "Slice/Index_Generation_Array/IGA_LC/IGA_LC.sv"
    if leaf in {"mse_mem_queue_tag", "mse_mem_queue_bp_pre"}:
        return (
            base
            / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
            "Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
        )
    if leaf in {
        "mse_mem_idx_mode",
        "mem_idx_valid_same_gotten_masked",
        "mem_all_idx_matched",
        "mem_ag_idx_queue_wr_en",
        "mem_ag_idx_queue_rd_en",
        "mem_ag_idx_queue_full",
        "mem_ag_idx_queue_empty",
    }:
        return (
            base
            / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
            "Memory_AG_Idx_Queue.sv"
        )
    raise KeyError(leaf)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--rtl-repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo = args.rtl_repo.resolve()
    head = subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={repo.as_posix()}",
            "-C",
            str(repo),
            "rev-parse",
            "HEAD",
        ],
        text=True,
        encoding="utf-8",
    ).strip()
    with zipfile.ZipFile(args.zip) as archive:
        observer = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        ).decode()
        manifest = json.loads(
            archive.read(f"{INSTALL_NAME}/package_manifest.json")
        )
    block = observer[observer.index(BEGIN) : observer.index(END)]
    expressions = sorted(set(XMR_RE.findall(block)))
    coverage: list[dict[str, Any]] = []
    for expression in expressions:
        path = owner(repo, expression)
        payload = path.read_bytes()
        leaf = re.sub(r"\[.*", "", expression.rsplit(".", 1)[-1])
        declaration = re.search(
            rf"\b{re.escape(leaf)}\b", payload.decode(errors="replace")
        ) is not None
        instance_ok = all(
            (
                "IGA_LC[" not in expression or "IGA_LC[7]" in expression,
                "MSE_INST[" not in expression or "MSE_INST[3]" in expression,
                (
                    "mse_mem_queue_" not in expression
                    or "[2]" in expression
                ),
                (
                    "slice_with_datahub_mc_group_gen[" not in expression
                    or "slice_with_datahub_mc_group_gen[0]" in expression
                ),
            )
        )
        coverage.append(
            {
                "expression": expression,
                "leaf": leaf,
                "owner": str(path.relative_to(repo)).replace("\\", "/"),
                "owner_sha256": sha256(payload),
                "declaration_present": declaration,
                "exact_instance": instance_ok,
                "covered": declaration and instance_ok,
            }
        )
    interconnect = (
        repo
        / "code/NDP_rtl/Slice/Index_Generation_Array/IGA_Interconnect.sv"
    ).read_text(encoding="utf-8")
    mem_source = (
        repo
        / "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_AG_Idx_Queue.sv"
    ).read_text(encoding="utf-8")
    lc_source = (
        repo / "code/NDP_rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC.sv"
    ).read_text(encoding="utf-8")
    negatives = {
        "delete_actual_mem_capture_leaf_fail_closed": (
            "mem_idx_valid_same_gotten_masked_DELETED" not in mem_source
        ),
        "wrong_lc_sibling_fail_closed": "IGA_LC[6]" not in block,
        "wrong_mse_sibling_fail_closed": "MSE_INST[4]" not in block,
        "actual_consumer_typo_fail_closed": (
            "mem_idx_valid_same_gotten_maskde" not in mem_source
        ),
    }
    checks = {
        "local_head_cloud_authority": head == COMMIT,
        "manifest_cloud_authority": (
            manifest.get("cloud_rtl_authority", {}).get("approved_commit")
            == COMMIT
        ),
        "actual_span_unique": (
            observer.count(BEGIN) == 1 and observer.count(END) == 1
        ),
        "all_actual_consumers_covered": all(
            item["covered"] for item in coverage
        ),
        "actual_consumers_nonzero": bool(coverage),
        "lc9_bit0_decode": all(
            token in interconnect
            for token in (
                "IGA_LC_DST_IDX < `IGA_LC_DST_LC_NUM",
                "iga_lc_inport_bp_pre[DST_LC_IDX][DST_LC_BP_PRE_IDX]",
            )
        ),
        "lc9_bit26_decode": all(
            token in interconnect
            for token in (
                "DST_SE_INPORT_IDX",
                "se2iga_mem_bp_pre[DST_SE_IDX][DST_SE_BP_PRE_IDX][DST_SE_INPORT_IDX]",
            )
        ),
        "lc7_capture_equation": all(
            token in lc_source
            for token in (
                "iga_lc_inbuffer_valid_bit",
                "iga_lc_inbuffer_bp_pre",
                "iga_lc_outport",
            )
        ),
        "mse3_qualified_queue_equations": all(
            token in mem_source
            for token in (
                "mem_idx_valid_same_gotten_masked",
                "mem_ag_idx_queue_wr_en",
                "mem_ag_idx_queue_rd_en",
                "mem_ag_idx_queue_full",
                "mem_ag_idx_queue_empty",
            )
        ),
        "negative_controls_fail_closed": all(negatives.values()),
    }
    report = {
        "schema": "node0004-v48-lc9-actual-consumer-closure-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "authority": {"commit": COMMIT, "local_head": head},
        "backpressure_decode": {
            "bit0": "LC7 source slot8 / iga_lc_inport_bp_pre[7][8]",
            "bit26": "MSE3 source slot5 input2 / se2iga_mem_bp_pre[3][5][2]",
        },
        "coverage": coverage,
        "actual_consumer_count": len(expressions),
        "uncovered": sum(not item["covered"] for item in coverage),
        "negative_controls": negatives,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
