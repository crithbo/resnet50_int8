from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n4_hw_v43_wrterm2_compilefix"
BEGIN = "// v41 WRTERM2_ACTUAL_CONSUMER_BEGIN"
END = "// v41 WRTERM2_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])?)+"
)
OWNERS = {
    "u_wr_chl_queue": "NDP_copy01/rtl/utils/FIFO/FIFO.sv",
    "u_buf_ag_idx_queue": "NDP_copy01/rtl/utils/FIFO/FIFO.sv",
    "u_WR_Data_Channel": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    ),
    "u_RD_Buffer_AG": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    ),
    "u_Memory_AG_Idx_Queue": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_AG_Idx_Queue.sv"
    ),
    "u_Buffer_AG_Idx_Queue": (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Buffer_AG_Idx_Queue.sv"
    ),
    "u_NDP_Top_new": "NDP_copy01/rtl/NDP_Top.sv",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def owner_for(expression: str) -> tuple[str, str]:
    for token in [
        "u_wr_chl_queue",
        "u_buf_ag_idx_queue",
        "u_WR_Data_Channel",
        "u_RD_Buffer_AG",
        "u_Memory_AG_Idx_Queue",
        "u_Buffer_AG_Idx_Queue",
    ]:
        if f".{token}" in expression:
            return token, OWNERS[token]
    return "u_NDP_Top_new", OWNERS["u_NDP_Top_new"]


def leafs(expression: str) -> set[str]:
    result = {
        re.sub(r"\[.*", "", expression.rsplit(".", 1)[-1])
    }
    for special in ["buf_ag_ob_row_addr", "buf_ag_ob_col_addr"]:
        if f".{special}[" in expression:
            result.add(special)
    return result


def classify(
    expression: str, owner_text: dict[str, str]
) -> dict[str, Any]:
    owner, path = owner_for(expression)
    candidate_leafs = sorted(leafs(expression))
    source = owner_text[path]
    leaf_valid = all(
        re.search(rf"\b{re.escape(leaf)}\b", source) is not None
        for leaf in candidate_leafs
    )
    instance_valid = (
        "MSE_INST[" not in expression or "MSE_INST[4]" in expression
    )
    fixed_generate_valid = (
        "slice_with_datahub_mc_group_gen[" not in expression
        or "slice_with_datahub_mc_group_gen[0]" in expression
    )
    return {
        "expression": expression,
        "owner_instance": owner,
        "owner_path": path,
        "leafs": candidate_leafs,
        "leaf_valid": leaf_valid,
        "instance_valid": instance_valid,
        "fixed_generate_valid": fixed_generate_valid,
        "covered": leaf_valid and instance_valid and fixed_generate_valid,
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
    for path in sorted(set(OWNERS.values())):
        payload = (ROOT / path).read_bytes()
        owner_text[path] = payload.decode()
        owner_receipts[path] = {
            "bytes": len(payload),
            "sha256": sha256(payload),
        }
    coverage = [classify(item, owner_text) for item in unique]
    uncovered = [item for item in coverage if not item["covered"]]

    exact_actual = next(
        item
        for item in unique
        if item.endswith(".mse_mem_queue_bp_pre[1]")
    )
    typo = exact_actual.replace(
        "mse_mem_queue_bp_pre", "mse_mem_queue_bp_per"
    )
    wrong_sibling = exact_actual.replace("MSE_INST[4]", "MSE_INST[3]")
    owner, owner_path = owner_for(exact_actual)
    leaf = next(iter(leafs(exact_actual)))
    deleted_owner = {
        **owner_text,
        owner_path: re.sub(
            rf"\b{re.escape(leaf)}\b", f"{leaf}_DELETED", owner_text[owner_path]
        ),
    }
    negatives = {
        "actual_consumer_typo_fail_closed": not classify(
            typo, owner_text
        )["covered"],
        "wrong_sibling_path_fail_closed": not classify(
            wrong_sibling, owner_text
        )["covered"],
        "actual_leaf_deleted_fail_closed": not classify(
            exact_actual, deleted_owner
        )["covered"],
    }
    checks = {
        "observer_exact_block_present": BEGIN in observer and END in observer,
        "failing_v41_leaf_absent": "mem_idx_gotten[1]" not in block,
        "actual_consumer_occurrences_nonzero": len(occurrences) > 0,
        "actual_consumer_uncovered_zero": not uncovered,
        "negatives_fail_closed": all(negatives.values()),
    }
    report = {
        "schema": "node0004-v43-actual-final-hdl-consumer-coverage-v1",
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
            "machine identifier/declaration/use and exact-instance closure for "
            "the changed WRTERM2 span; no fabricated focused target leaf and "
            "no full-design or DUT execution"
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
