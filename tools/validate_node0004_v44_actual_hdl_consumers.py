from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n4_hw_v44_lc9_split_diag"
BEGIN = "// v44 LC9_SPLIT_ACTUAL_CONSUMER_BEGIN"
END = "// v44 LC9_SPLIT_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)
LEAF_OWNERS = {
    "clk_db": "NDP_copy01/rtl/NDP_Top.sv",
    "rst_n_db": "NDP_copy01/rtl/NDP_Top.sv",
    "iga_lc_outport": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/"
        "Index_Generation_Array.sv"
    ),
    "iga_lc_outport_bp_post": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/"
        "Index_Generation_Array.sv"
    ),
    "iga_pe_inport_bp_pre": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/"
        "Index_Generation_Array.sv"
    ),
    "iga_pe_outport": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/"
        "Index_Generation_Array.sv"
    ),
    "iga_pe_outport_bp_post": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/"
        "Index_Generation_Array.sv"
    ),
    "iga_pe_inbuffer_matched": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/"
        "IGA_PE_Inbuffer.sv"
    ),
    "mse_mem_queue_tag": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
    ),
    "mse_mem_queue_bp_pre": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/Memory_WR_Stream_Engine.sv"
    ),
    "iga_row_lc_inbuffer_bp_pre": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC.sv"
    ),
    "iga_row_lc_inport_valid_bit_masked": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC_Inbuffer.sv"
    ),
    "iga_row_lc_cnt_outport_valid_bit": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC_Counter.sv"
    ),
    "iga_row_lc_cnt_bp_post": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC.sv"
    ),
    "iga_row_lc_outport": (
        "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_ROW_LC/"
        "IGA_ROW_LC.sv"
    ),
    "buf_ag_idx_queue_wr_en": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    ),
    "buf_ag_idx_queue_full": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    ),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def leaf(expression: str) -> str:
    return re.sub(r"\[.*", "", expression.rsplit(".", 1)[-1])


def classify(
    expression: str, owner_text: dict[str, str]
) -> dict[str, Any]:
    name = leaf(expression)
    owner = LEAF_OWNERS.get(name)
    owner_known = owner is not None
    declaration_present = (
        owner_known
        and re.search(rf"\b{re.escape(name)}\b", owner_text[owner]) is not None
    )
    exact_slice = (
        "slice_with_datahub_mc_group_gen[" not in expression
        or "slice_with_datahub_mc_group_gen[0]" in expression
    )
    mse_instance = "MSE_INST[" not in expression or "MSE_INST[4]" in expression
    pe_instance = "IGA_PE[" not in expression or "IGA_PE[1]" in expression
    if name in {
        "iga_pe_inport_bp_pre",
        "iga_pe_outport",
        "iga_pe_outport_bp_post",
    }:
        pe_instance = re.search(
            rf"\.{re.escape(name)}\[1\](?:\[|$)", expression
        ) is not None
    row_instance = (
        "IGA_ROW_LC[" not in expression or "IGA_ROW_LC[4]" in expression
    )
    covered = (
        owner_known
        and declaration_present
        and exact_slice
        and mse_instance
        and pe_instance
        and row_instance
    )
    return {
        "expression": expression,
        "leaf": name,
        "owner_path": owner,
        "owner_known": owner_known,
        "declaration_present": declaration_present,
        "exact_slice": exact_slice,
        "mse_instance": mse_instance,
        "pe_instance": pe_instance,
        "row_instance": row_instance,
        "covered": covered,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    with zipfile.ZipFile(args.zip) as archive:
        observer_bytes = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = observer_bytes.decode()
    block = observer[observer.index(BEGIN) : observer.index(END)]
    occurrences = XMR_RE.findall(block)
    unique = sorted(set(occurrences))

    owner_text: dict[str, str] = {}
    owner_receipts: dict[str, dict[str, Any]] = {}
    for path in sorted(set(LEAF_OWNERS.values())):
        payload = (ROOT / path).read_bytes()
        owner_text[path] = payload.decode()
        owner_receipts[path] = {
            "bytes": len(payload),
            "sha256": sha256(payload),
        }
    coverage = [classify(item, owner_text) for item in unique]
    uncovered = [item for item in coverage if not item["covered"]]

    exact = next(
        item
        for item in unique
        if item.endswith(".iga_lc_outport_bp_post[9]")
    )
    typo = exact.replace("iga_lc_outport_bp_post", "iga_lc_outport_bp_pots")
    pe_exact = next(
        item for item in unique if ".iga_pe_inport_bp_pre[1][9][2]" in item
    )
    wrong_pe = pe_exact.replace("[1][9][2]", "[2][9][2]")
    mem_exact = next(
        item for item in unique if item.endswith(".mse_mem_queue_tag[1]")
    )
    wrong_mse = mem_exact.replace("MSE_INST[4]", "MSE_INST[3]")
    owner_path = LEAF_OWNERS[leaf(exact)]
    deleted_owner = {
        **owner_text,
        owner_path: re.sub(
            rf"\b{re.escape(leaf(exact))}\b",
            f"{leaf(exact)}_DELETED",
            owner_text[owner_path],
        ),
    }
    negatives = {
        "actual_consumer_typo_fail_closed": not classify(
            typo, owner_text
        )["covered"],
        "wrong_pe_sibling_fail_closed": not classify(
            wrong_pe, owner_text
        )["covered"],
        "wrong_mse_sibling_fail_closed": not classify(
            wrong_mse, owner_text
        )["covered"],
        "actual_leaf_deleted_fail_closed": not classify(
            exact, deleted_owner
        )["covered"],
    }
    checks = {
        "observer_exact_block_present": BEGIN in observer and END in observer,
        "actual_consumer_occurrences_nonzero": len(occurrences) > 0,
        "actual_consumer_uncovered_zero": not uncovered,
        "negatives_fail_closed": all(negatives.values()),
    }
    report = {
        "schema": "node0004-v44-actual-final-hdl-consumer-coverage-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "final_observer": {
            "bytes": len(observer_bytes),
            "sha256": sha256(observer_bytes),
            "changed_span": {
                "begin": BEGIN,
                "end": END,
                "sha256": sha256(block.encode()),
            },
        },
        "actual_consumer_occurrences": len(occurrences),
        "actual_consumer_unique": len(unique),
        "classified": len(coverage) - len(uncovered),
        "uncovered": len(uncovered),
        "uncovered_records": uncovered,
        "coverage": coverage,
        "owner_receipts": owner_receipts,
        "negative_controls": negatives,
        "claim_boundary": (
            "identifier/declaration/use and exact-instance closure for the "
            "changed v44 LC9 split span; no fabricated wrapper leaf, no DUT run, "
            "and no full-design functional claim"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
