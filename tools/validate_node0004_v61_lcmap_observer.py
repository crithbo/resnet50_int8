from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_node0004_v44_observer_syntax import compile_case


INSTALL = "r5_n4_hw_v61_lcmap_argv_fix"
RTL_ROOT = ROOT / "NDP_copy01/rtl"
MAPPING = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-conv-native-four-lane-0cc-p9-tx5-c0"
    / "execplan_conv/wave-0/pipeline_output/config/op_w0/mapping_review.json"
)
SPANS = {
    "dterm": (
        "// v50 DTERM_OWNER_ACTUAL_CONSUMER_BEGIN",
        "// v50 DTERM_OWNER_ACTUAL_CONSUMER_END",
        (6, 8, 17, 18),
    ),
    "lcchain": (
        "// v51 LC13_LC14_ACTUAL_CONSUMER_BEGIN",
        "// v51 LC13_LC14_ACTUAL_CONSUMER_END",
        (6, 8, 17),
    ),
}
EXPECTED_MAP = {
    "DRAM_LC.LC13": "LC6",
    "DRAM_LC.LC14": "LC8",
    "DRAM_LC.LC15": "LC17",
    "DRAM_LC.LC9": "LC18",
}
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)
PLUSARG_RE = re.compile(r"\+RETURN_[A-Za-z0-9_]+(?:=[^\s\"']+)?")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def span(text: str, begin: str, end: str) -> str:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise ValueError(f"span identity differs:{begin}")
    return text[text.index(begin): text.index(end) + len(end)]


def leaf(expression: str) -> str:
    return re.sub(r"\[.*\]$", "", expression.rsplit(".", 1)[-1])


def syntax_case(
    iverilog: Path, root: Path, name: str, block: str
) -> dict[str, object]:
    expressions = sorted(set(XMR_RE.findall(block)), key=len, reverse=True)
    replacements = {
        expression: f"actual_consumer_{index}"
        for index, expression in enumerate(expressions)
    }
    normalized = block
    for expression, local in replacements.items():
        normalized = normalized.replace(expression, local)
    normalized = normalized.replace(
        "logic [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0]", "logic [63:0]"
    )
    declarations = "\n".join(
        f"  logic [63:0] {local};" for local in replacements.values()
    )
    task_name = (
        "return_obs_write_dterm_owner_state"
        if name == "dterm"
        else "return_obs_write_lc13_lc14_state"
    )
    source = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        "  bit return_obs_enabled, return_obs_active;\n"
        "  integer return_obs_fd;\n"
        f"{declarations}\n{normalized}\n"
        f'  initial begin #1; {task_name}("FOCUS"); end\nendmodule\n'
    )
    positive = compile_case(iverilog, root, f"{name}_positive", source)
    missing = compile_case(
        iverilog,
        root,
        f"{name}_missing_declaration",
        source.replace("    bit return_obs_", "    // deleted bit return_obs_", 1),
    )
    task_typo = compile_case(
        iverilog,
        root,
        f"{name}_task_typo",
        source.replace(f'{task_name}("FOCUS")', f'{task_name}_typo("FOCUS")', 1),
    )
    first_local = next(iter(replacements.values()))
    consumer_typo = compile_case(
        iverilog,
        root,
        f"{name}_consumer_typo",
        source.replace(first_local, first_local + "_typo", 1),
    )
    return {
        "positive": positive,
        "negative_missing_declaration": missing,
        "negative_task_typo": task_typo,
        "negative_actual_consumer_typo": consumer_typo,
        "valid": (
            positive["exit_code"] == 0
            and missing["exit_code"] != 0
            and task_typo["exit_code"] != 0
            and consumer_typo["exit_code"] != 0
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        observer_payload = archive.read(
            f"{INSTALL}/tb_probe/native_return_observer.svh"
        )
        runner_payload = archive.read(f"{INSTALL}/PREPARE_AND_RUN.sh")
    observer = observer_payload.decode()
    runner = runner_payload.decode()
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    node_to_resource = {
        item["node"]: item["resource"] for item in mapping["node_to_resource"]
    }

    corpus: dict[Path, str] = {}
    for path in sorted(RTL_ROOT.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".sv", ".v", ".svh", ".vh"}:
            corpus[path] = path.read_text(encoding="utf-8", errors="ignore")

    blocks: dict[str, str] = {}
    bindings: dict[str, object] = {}
    syntax: dict[str, object] = {}
    missing_leaves: list[str] = []
    with tempfile.TemporaryDirectory(prefix="v61-lcmap-observer-") as temp:
        temp_root = Path(temp)
        for name, (begin, end, expected_indices) in SPANS.items():
            block = span(observer, begin, end)
            blocks[name] = block
            expressions = sorted(set(XMR_RE.findall(block)))
            rows = []
            for expression in expressions:
                token = leaf(expression)
                locations = [
                    path for path, text in corpus.items()
                    if re.search(rf"\b{re.escape(token)}\b", text)
                ]
                if not locations:
                    missing_leaves.append(expression)
                rows.append(
                    {
                        "expression": expression,
                        "leaf": token,
                        "binding_files": [
                            {
                                "path": path.relative_to(ROOT).as_posix(),
                                "bytes": path.stat().st_size,
                                "sha256": digest(path.read_bytes()),
                            }
                            for path in locations[:8]
                        ],
                    }
                )
            physical_indices = sorted(
                {
                    int(value)
                    for value in re.findall(
                        r"(?:IGA_LC|iga_lc_outport|iga_lc_outport_bp_post)"
                        r"\[(\d+)\]",
                        block,
                    )
                }
            )
            bindings[name] = {
                "sha256": digest(block.encode()),
                "actual_consumer_count": len(expressions),
                "physical_indices": physical_indices,
                "expected_indices": list(expected_indices),
                "rows": rows,
            }
            syntax[name] = syntax_case(
                args.iverilog, temp_root, name, block
            )

    receipt_line = next(
        line for line in runner.splitlines()
        if "simulator_argv.txt" in line and line.lstrip().startswith("printf")
    )
    invocation_line = next(
        line for line in runner.splitlines()
        if 'timeout --foreground --signal=TERM --kill-after=30s 6h "$simv"' in line
    )
    receipt_args = set(PLUSARG_RE.findall(receipt_line))
    invocation_args = set(PLUSARG_RE.findall(invocation_line))
    required_features = {
        "+RETURN_OBS_DTERM_OWNER",
        "+RETURN_OBS_LC13_LC14",
        "+RETURN_OBS_LC9_ACTUAL",
        "+RETURN_HANG_DIAG",
    }

    def accepts(candidate: dict[str, str], receipt: set[str]) -> bool:
        observed = {
            name: sorted(
                {
                    int(value)
                    for value in re.findall(
                        r"(?:IGA_LC|iga_lc_outport|iga_lc_outport_bp_post)"
                        r"\[(\d+)\]",
                        block,
                    )
                }
            )
            for name, block in candidate.items()
        }
        return (
            all(node_to_resource.get(key) == value
                for key, value in EXPECTED_MAP.items())
            and observed["dterm"] == [6, 8, 17, 18]
            and observed["lcchain"] == [6, 8, 17]
            and required_features <= receipt
            and receipt == invocation_args
            and not missing_leaves
        )

    wrong_sibling = dict(blocks)
    wrong_sibling["lcchain"] = wrong_sibling["lcchain"].replace(
        "IGA_LC[8]", "IGA_LC[7]", 1
    )
    old_logical = dict(blocks)
    old_logical["dterm"] = old_logical["dterm"].replace(
        "iga_lc_outport[6]", "iga_lc_outport[13]", 1
    )
    missing_feature = set(receipt_args)
    missing_feature.discard("+RETURN_OBS_LC13_LC14")
    negatives = {
        "wrong_physical_sibling_fail_closed":
            not accepts(wrong_sibling, receipt_args),
        "logical_index_reintroduced_fail_closed":
            not accepts(old_logical, receipt_args),
        "runtime_feature_receipt_drop_fail_closed":
            not accepts(blocks, missing_feature),
    }
    checks = {
        "mapping_review_exact": all(
            node_to_resource.get(key) == value
            for key, value in EXPECTED_MAP.items()
        ),
        "observer_spans_exact_once": all(
            observer.count(begin) == 1 and observer.count(end) == 1
            for begin, end, _ in SPANS.values()
        ),
        "physical_indices_exact": (
            bindings["dterm"]["physical_indices"] == [6, 8, 17, 18]
            and bindings["lcchain"]["physical_indices"] == [6, 8, 17]
        ),
        "all_leaf_definitions_found_in_current_rtl": not missing_leaves,
        "owner_clock_reset_exact": all(
            "posedge u_NDP_Top_new.clk_db" in block
            and "negedge u_NDP_Top_new.rst_n_db" in block
            for block in blocks.values()
        ),
        "focused_syntax_and_scope_controls": all(
            row["valid"] for row in syntax.values()
        ),
        "simulator_argv_receipt_equals_actual_invocation":
            receipt_args == invocation_args,
        "required_features_in_receipt": required_features <= receipt_args,
        "negative_controls_fail_closed": all(negatives.values()),
    }
    report = {
        "schema": "node0004-v61-lcmap-observer-validation-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": digest(args.zip.read_bytes()),
        },
        "observer": {
            "bytes": len(observer_payload),
            "sha256": digest(observer_payload),
            "bindings": bindings,
            "missing_leaves": missing_leaves,
        },
        "mapping_review": {
            "path": str(MAPPING),
            "bytes": MAPPING.stat().st_size,
            "sha256": digest(MAPPING.read_bytes()),
            "logical_to_physical": EXPECTED_MAP,
        },
        "runner_argv": {
            "receipt_plusargs": sorted(receipt_args),
            "invocation_plusargs": sorted(invocation_args),
        },
        "syntax_controls": syntax,
        "negative_controls": negatives,
        "current_rtl": {
            "root": str(RTL_ROOT),
            "scanned_source_files": len(corpus),
            "cloud_authority_commit": (
                "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
            ),
        },
        "claim_boundary": (
            "Package-local changed observer syntax, declaration/use, current "
            "RTL leaf presence, exact mapper indices, and runner argv receipt "
            "were validated. Dynamic values remain a server-run question."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"valid": report["valid"], "errors": report["errors"]}))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
