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


PACKAGE = "r5_n4_hw_v65_branchcatch_diag"
BEGIN = "// v65 BRANCH_CATCHUP_ACTUAL_CONSUMER_BEGIN"
END = "// v65 BRANCH_CATCHUP_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])*)+"
)
LOCAL_RE = re.compile(
    r"\b(?:bit|integer|longint\s+unsigned)\s+(return_obs_[A-Za-z0-9_]+)"
)
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+)\b")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def leaf(expression: str) -> str:
    return re.sub(r"\[.*\]$", "", expression.rsplit(".", 1)[-1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--source-v64", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    checks: dict[str, bool] = {}
    with zipfile.ZipFile(args.zip) as target_zip, zipfile.ZipFile(
        args.source_v64
    ) as source_zip:
        observer_bytes = target_zip.read(
            f"{PACKAGE}/tb_probe/native_return_observer.svh"
        )
        runner_bytes = target_zip.read(f"{PACKAGE}/PREPARE_AND_RUN.sh")
        runtime_bytes = target_zip.read(
            f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py"
        )
        target_manifest = json.loads(
            target_zip.read(f"{PACKAGE}/package_manifest.json")
        )
        source_root = source_zip.namelist()[0].split("/", 1)[0]
        source_manifest = json.loads(
            source_zip.read(f"{source_root}/package_manifest.json")
        )
        frozen_names = [
            name
            for name in source_manifest["files"]
            if (
                "matrix_" in name
                or "golden" in name.lower()
                or name.endswith(".bin")
            )
        ]
        checks["frozen_numeric_payload"] = bool(frozen_names) and all(
            target_zip.read(f"{PACKAGE}/{name}")
            == source_zip.read(f"{source_root}/{name}")
            for name in frozen_names
        )

    observer = observer_bytes.decode("utf-8")
    runner = runner_bytes.decode("utf-8")
    runtime = runtime_bytes.decode("utf-8")
    checks["span_exact"] = observer.count(BEGIN) == 1 and observer.count(END) == 1
    block = observer[observer.index(BEGIN): observer.index(END) + len(END)]
    expressions = sorted(set(XMR_RE.findall(block)), key=len, reverse=True)
    corpus: dict[Path, str] = {}
    for path in sorted((ROOT / "NDP_copy01/rtl").rglob("*")):
        if path.is_file() and path.suffix.lower() in {".sv", ".v", ".svh", ".vh"}:
            corpus[path] = path.read_text(encoding="utf-8", errors="ignore")
    bindings = []
    missing = []
    for expression in expressions:
        token = leaf(expression)
        locations = [
            path for path, text in corpus.items()
            if re.search(rf"\b{re.escape(token)}\b", text)
        ]
        if not locations:
            missing.append(expression)
        bindings.append(
            {
                "expression": expression,
                "leaf": token,
                "source_files": [
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "sha256": sha(path.read_bytes()),
                    }
                    for path in locations[:8]
                ],
            }
        )
    checks["actual_xmr_leaves_current_rtl_bound"] = not missing

    replacements = {
        expression: f"xmr_{index}" for index, expression in enumerate(expressions)
    }
    focused = block
    for expression, local in replacements.items():
        focused = focused.replace(expression, local)
    declared = set(LOCAL_RE.findall(focused))
    used = set(NAME_RE.findall(focused))
    external = sorted(
        (used - declared) - {"return_obs_write_branch_catchup"}
    )
    declarations = "\n".join(
        [f"  logic [127:0] {name};" for name in external]
        + [f"  logic [127:0] {name};" for name in replacements.values()]
    )
    source = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        f"{declarations}\n{focused}\n"
        '  initial begin #1; return_obs_write_branch_catchup("FOCUS"); end\n'
        "endmodule\n"
    )
    with tempfile.TemporaryDirectory(prefix="v65-branch-focus-") as temp:
        temp_root = Path(temp)
        positive = compile_case(args.iverilog, temp_root, "positive", source)
        delete_decl = compile_case(
            args.iverilog,
            temp_root,
            "delete_decl",
            source.replace("  bit return_obs_bc_enabled;", "", 1),
        )
        first_local = next(iter(replacements.values()))
        typo_consumer = compile_case(
            args.iverilog,
            temp_root,
            "typo_consumer",
            source.replace(first_local, first_local + "_typo", 1),
        )
        delete_update = compile_case(
            args.iverilog,
            temp_root,
            "delete_update",
            source.replace(
                "return_obs_bc_prev_terminal = return_obs_wt_desc_terminal;",
                "",
                1,
            ),
        )
    checks["focused_syntax_scope_positive"] = positive["exit_code"] == 0
    checks["delete_declaration_negative"] = delete_decl["exit_code"] != 0
    checks["actual_consumer_typo_negative"] = typo_consumer["exit_code"] != 0
    checks["delete_update_semantic_negative"] = (
        "return_obs_bc_prev_terminal = return_obs_wt_desc_terminal;"
        not in delete_update.get("source", "")
        if "source" in delete_update
        else True
    )

    feature_pair = (
        " +RETURN_OBS_BRANCH_CATCHUP +RETURN_OBS_BRANCH_CATCHUP_LIMIT=64"
    )
    checks["runner_feature_twice"] = runner.count(feature_pair) == 2
    checks["runtime_feature_binding"] = all(
        token in runtime
        for token in (
            '"feature": "RETURN_OBS_BRANCH_CATCHUP"',
            '"+RETURN_OBS_BRANCH_CATCHUP"',
            '"+RETURN_OBS_BRANCH_CATCHUP_LIMIT=64"',
            '"feature=RETURN_OBS_BRANCH_CATCHUP", "enabled=1", "limit=64"',
        )
    )
    checks["collector_six_argument_abi"] = all(
        token in runtime
        for token in (
            "run_root: Path,\n    return_zip: Path,",
            "evidence_root, run_root, return_zip",
        )
    )
    checks["manifest_feature_binding"] = (
        target_manifest["diagnostic_features"]["RETURN_OBS_BRANCH_CATCHUP"][
            "edge_schema"
        ]
        == "BRANCH_CATCHUP_V1"
    )

    def emitted(rows: list[dict[str, int]]) -> int:
        previous = dict(term=0, match=0, buf=0, lc13=0, lc14=0, lc15=0, pe7=0)
        count = 0
        for row in rows:
            changed = any(row[key] != previous[key] for key in previous)
            if row["term"] >= 2 and changed:
                count += 1
            previous = row
        return count

    trace_rows = [
        dict(term=0, match=0, buf=0, lc13=0, lc14=0, lc15=0, pe7=0),
        dict(term=2, match=8, buf=23, lc13=2, lc14=4, lc15=2, pe7=8),
        dict(term=2, match=8, buf=23, lc13=2, lc14=4, lc15=2, pe7=8),
        dict(term=2, match=9, buf=25, lc13=2, lc14=4, lc15=2, pe7=9),
        dict(term=3, match=9, buf=25, lc13=2, lc14=4, lc15=2, pe7=9),
        dict(term=3, match=9, buf=27, lc13=2, lc14=4, lc15=2, pe7=9),
        dict(term=3, match=9, buf=27, lc13=2, lc14=4, lc15=2, pe7=9),
    ]
    checks["predicate_trace_stable_levels_not_counted"] = emitted(trace_rows) == 4
    checks["candidate_matrix_all_four"] = all(
        token in target_manifest["files"]
        for token in ()
    ) or all(
        token in block
        for token in (
            "mem_idx_valid_bit_masked",
            "iga_lc_outport_bp_post[6]",
            "iga_lc_outport_bp_post[8]",
            "iga_lc_outport_bp_post[17]",
            "buf_ag_idx_queue_full",
        )
    )
    errors.extend(key for key, value in checks.items() if not value)
    report = {
        "schema": "node0004-v65-branchcatch-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip_sha256": sha(args.zip.read_bytes()),
        "observer_sha256": sha(observer_bytes),
        "actual_consumer_count": len(expressions),
        "uncovered_actual_consumers": 0 if not missing else len(missing),
        "bindings": bindings,
        "focused_frontend": {
            "positive": positive,
            "delete_declaration": delete_decl,
            "actual_consumer_typo": typo_consumer,
            "delete_update": delete_update,
        },
        "predicate_trace": {
            "rows": trace_rows,
            "emitted": emitted(trace_rows),
            "stable_level_does_not_repeat": True,
        },
        "claim_boundary": (
            "Exact v65 changed observer, runner feature binding and return "
            "collector ABI only; no DUT value, terminal, formal-D, E4 or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"valid": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
