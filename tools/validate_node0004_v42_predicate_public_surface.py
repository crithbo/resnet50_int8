from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n4_hw_v42_wrterm2_compilefix"
SOURCE_NAME = "r5_n4_hw_v41_wrterm2_diag"
RTL_REL = (
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Memory_AG_Idx_Queue.sv"
)
FILELIST_REL = (
    "NDP_copy01/rtl/filelists/LSU_Memory_WR_Stream_Engine_filelist.f"
)
RTL_SHA256 = "b555ab22523540a9aa49d3eb51dee6eea9962086a71429028c69964de3819989"
FILELIST_SHA256 = "e044ac673242482d0f61cc8f1208932c15fcef028cbc451c8ac5d7b6234a7d5e"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_member(path: Path, root: str, member: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(f"{root}/{member}")


def normalize_identity(data: bytes, identity: str) -> bytes:
    return data.replace(identity.encode(), b"<IDENTITY>")


def extract_predicate(observer: str) -> tuple[str, str]:
    match = re.search(
        r"wt_final_desc_pop\s*=\s*wt_desc_pop\s*&&\s*!wt_desc_push\s*&&\s*"
        r"\((?P<count>[^;]+?fifo_counter)\s*==\s*1\)\s*;",
        observer,
        re.DOTALL,
    )
    if not match:
        raise ValueError("final exact predicate not found")
    source = re.sub(r"\s+", " ", match.group(0)).strip()
    executable = "pop and (not push) and (pre_count == 1)"
    return source, executable


def safe_eval(expression: str, values: dict[str, Any]) -> bool:
    tree = ast.parse(expression, mode="eval")
    allowed = (
        ast.Expression,
        ast.BoolOp,
        ast.And,
        ast.UnaryOp,
        ast.Not,
        ast.Compare,
        ast.Eq,
        ast.Name,
        ast.Load,
        ast.Constant,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise ValueError("unexpected predicate AST")
    return bool(eval(compile(tree, "<final-exact-predicate>", "eval"), {}, values))


def trace_cases(expression: str) -> list[dict[str, Any]]:
    cases = [
        ("reset", 0, 0, 1, False, "reset owns state, event ignored"),
        ("before_empty", 0, 0, 0, True, "count conjunct near miss"),
        ("before_two", 1, 0, 2, True, "count conjunct near miss"),
        ("stable_count_one", 0, 0, 1, True, "stable level is not an event"),
        ("push_only", 0, 1, 1, True, "pop conjunct near miss"),
        ("simultaneous_push_pop", 1, 1, 1, True, "recent v40 escape"),
        ("true_final", 1, 0, 1, True, "unique final event"),
        ("after_empty", 0, 0, 0, True, "cycle after final"),
        ("pop_empty_illegal", 1, 0, 0, True, "count conjunct rejects"),
    ]
    result: list[dict[str, Any]] = []
    previous = False
    for name, pop, push, count, rst_n, reason in cases:
        raw = safe_eval(
            expression, {"pop": bool(pop), "push": bool(push), "pre_count": count}
        )
        qualified = raw if rst_n else False
        result.append(
            {
                "name": name,
                "clock_edge": "posedge clk_db",
                "rst_n": rst_n,
                "pop": pop,
                "push": push,
                "pre_count": count,
                "raw_predicate": raw,
                "qualified_event": qualified,
                "event_edge": qualified and not previous,
                "reason": reason,
            }
        )
        previous = qualified
    return result


def evaluate_variant(observer: str, rtl: str, filelist: str) -> bool:
    expected_instance = (
        "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
        "u_Memory_AG_Idx_Queue"
    )
    required = [
        f"{expected_instance}.mse_mem_queue_tag[1]",
        f"{expected_instance}.mse_mem_queue_bp_pre[1]",
        "mem_idx_valid_same_gotten_masked[1]",
        "wt_addr1",
    ]
    public_ports = (
        re.search(r"\binput\b[^;]*mse_mem_queue_tag\s*,", rtl, re.DOTALL)
        is not None
        and re.search(r"\boutput\b[^;]*mse_mem_queue_bp_pre\s*,", rtl, re.DOTALL)
        is not None
    )
    return (
        all(token in observer for token in required)
        and "mem_idx_gotten[1]" not in observer
        and "Memory_AG_Idx_Queue.sv" in filelist
        and public_ports
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--source-v41", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    observer_bytes = read_member(
        args.zip, INSTALL_NAME, "tb_probe/native_return_observer.svh"
    )
    source_bytes = read_member(
        args.source_v41, SOURCE_NAME, "tb_probe/native_return_observer.svh"
    )
    observer = observer_bytes.decode()
    source = source_bytes.decode()
    rtl_path = ROOT / RTL_REL
    filelist_path = ROOT / FILELIST_REL
    rtl_bytes = rtl_path.read_bytes()
    filelist_bytes = filelist_path.read_bytes()
    rtl = rtl_bytes.decode()
    filelist = filelist_bytes.decode()

    predicate_source, predicate_expression = extract_predicate(observer)
    trace = trace_cases(predicate_expression)
    event_names = [
        item["name"] for item in trace if item["qualified_event"] is True
    ]
    predicate_pass = event_names == ["true_final"]

    diff = list(
        difflib.unified_diff(
            normalize_identity(source_bytes, SOURCE_NAME)
            .decode()
            .splitlines(),
            normalize_identity(observer_bytes, INSTALL_NAME)
            .decode()
            .splitlines(),
            lineterm="",
        )
    )
    semantic_diff = [
        line
        for line in diff
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    only_expected_observer_change = (
        len(semantic_diff) == 2
        and any("mem1_gotten=%0d" in line for line in semantic_diff)
        and any("mem1_bp=%0d desc_count" in line for line in semantic_diff)
        and not any("mem_idx_gotten[1]" in line for line in semantic_diff)
    )
    # The removed argument is a whole source line, so account for it separately.
    only_expected_observer_change = (
        len(semantic_diff) == 3
        and sum("mem1_gotten=%0d" in line for line in semantic_diff) == 1
        and sum("mem1_bp=%0d desc_count" in line for line in semantic_diff) == 1
        and sum("mem_idx_gotten[1]" in line for line in semantic_diff) == 1
    )

    public_surface_pass = evaluate_variant(observer, rtl, filelist)
    negatives: dict[str, bool] = {}
    negatives["reinsert_private_missing_leaf_fail_closed"] = not evaluate_variant(
        observer.replace(
            "desc_count=%0d",
            "mem1_gotten=%0d desc_count=%0d",
            1,
        )
        + "\n// u_Memory_AG_Idx_Queue.mem_idx_gotten[1]\n",
        rtl,
        filelist,
    )
    negatives["rename_public_tag_fail_closed"] = not evaluate_variant(
        observer.replace("mse_mem_queue_tag[1]", "mse_mem_queue_taq[1]"),
        rtl,
        filelist,
    )
    negatives["wrong_sibling_path_fail_closed"] = not evaluate_variant(
        observer.replace(
            "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
            "u_Memory_AG_Idx_Queue",
            "MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine."
            "u_Memory_AG_Idx_Queue",
        ),
        rtl,
        filelist,
    )
    predicate_negatives = {
        "drop_no_push_conjunct_fail_closed": [
            item["name"]
            for item in trace_cases("pop and (pre_count == 1)")
            if item["qualified_event"]
        ]
        != ["true_final"],
        "wrong_count_fail_closed": [
            item["name"]
            for item in trace_cases("pop and (not push) and (pre_count == 2)")
            if item["qualified_event"]
        ]
        != ["true_final"],
        "stable_level_not_progress": all(
            not item["qualified_event"]
            for item in trace
            if item["name"] == "stable_count_one"
        ),
    }

    checks = {
        "exact_final_predicate_bound": (
            "wt_desc_pop" in predicate_source
            and "!wt_desc_push" in predicate_source
            and "fifo_counter == 1" in predicate_source
        ),
        "predicate_trace_unique_true_final": predicate_pass,
        "predicate_trace_negatives": all(predicate_negatives.values()),
        "observer_diff_only_expected_compilefix": only_expected_observer_change,
        "public_surface_preferred_no_new_private_xmr": public_surface_pass,
        "public_surface_negatives": all(negatives.values()),
        "actual_rtl_sha": sha256(rtl_bytes) == RTL_SHA256,
        "actual_filelist_sha": sha256(filelist_bytes) == FILELIST_SHA256,
        "actual_width_three": "`define MSE_MQ_INPORT_NUM                  3" in (
            ROOT / "NDP_copy01/rtl/includes/NDP_Parameters.svh"
        ).read_text(),
        "actual_clock_reset_owner": (
            "input                                                                 clk,"
            in rtl
            and "input                                                                 rst_n," in rtl
            and "input                                                                 slice_rst," in rtl
        ),
    }
    report = {
        "schema": "node0004-v42-predicate-public-surface-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "predicate_trace": {
            "rule_id": "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "final_exact_source": predicate_source,
            "same_source_executable": predicate_expression,
            "clock_owner": "u_NDP_Top_new.clk_db",
            "reset_owner": "u_NDP_Top_new.rst_n_db",
            "events": trace,
            "qualified_events": event_names,
            "negatives": predicate_negatives,
        },
        "public_surface_or_xmr": {
            "rule_id": "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
            "private_xmr_required_for_changed_surface": False,
            "removed_leaf": "u_Memory_AG_Idx_Queue.mem_idx_gotten[1]",
            "replacement_private_leaf_added": False,
            "public_surface": [
                "Memory_AG_Idx_Queue.mse_mem_queue_tag[1] input port",
                "Memory_AG_Idx_Queue.mse_mem_queue_bp_pre[1] output port",
                "qualified wt_addr1 event",
            ],
            "actual_target_module": {
                "path": RTL_REL,
                "bytes": len(rtl_bytes),
                "sha256": sha256(rtl_bytes),
                "instance_path": (
                    "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
                    "u_slice_with_datahub_mc_group.slice_group_gen[0]."
                    "u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine."
                    "MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
                    "u_Memory_AG_Idx_Queue"
                ),
                "port_width": 3,
                "clock": "clk_db -> module clk",
                "reset": "rst_n_db/slice_rst",
            },
            "actual_filelist": {
                "path": FILELIST_REL,
                "bytes": len(filelist_bytes),
                "sha256": sha256(filelist_bytes),
            },
            "negatives": negatives,
        },
        "observer_sha256": sha256(observer_bytes),
        "source_observer_sha256": sha256(source_bytes),
        "semantic_diff": semantic_diff,
        "server_dut_run": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
