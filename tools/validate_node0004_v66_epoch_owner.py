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

from tools.validate_node0004_v44_observer_syntax import compile_case  # noqa: E402


PACKAGE = "r5_n4_hw_v66_epoch_owner_diag"
BEGIN = "// v66 EPOCH_OWNER_ACTUAL_CONSUMER_BEGIN"
END = "// v66 EPOCH_OWNER_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]\n]+\])*)+"
)
LOCAL_RE = re.compile(
    r"\b(?:bit|integer|longint\s+unsigned|logic(?:\s+\[[^\]]+\])?)\s+"
    r"(return_obs_[A-Za-z0-9_]+)"
)
NAME_RE = re.compile(r"\b(return_obs_[A-Za-z0-9_]+)\b")


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def leaf(expression: str) -> str:
    return re.sub(r"\[.*\]$", "", expression.rsplit(".", 1)[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--source-v65", required=True, type=Path)
    ap.add_argument("--iverilog", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    checks: dict[str, bool] = {}
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as target, zipfile.ZipFile(
        args.source_v65
    ) as source:
        observer_bytes = target.read(
            f"{PACKAGE}/tb_probe/native_return_observer.svh"
        )
        runner = target.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode()
        runtime = target.read(
            f"{PACKAGE}/package_tools/node0004_hang_localization_runtime.py"
        ).decode()
        manifest = json.loads(target.read(f"{PACKAGE}/package_manifest.json"))
        source_root = source.namelist()[0].split("/", 1)[0]
        source_manifest = json.loads(
            source.read(f"{source_root}/package_manifest.json")
        )
        frozen = [
            name
            for name in source_manifest["files"]
            if (
                name.startswith("workload/")
                or "golden" in name.lower()
                or name.endswith(".bin")
            )
        ]
        checks["frozen_payload"] = bool(frozen) and all(
            target.read(f"{PACKAGE}/{name}").replace(
                PACKAGE.encode(), source_root.encode()
            )
            == source.read(f"{source_root}/{name}")
            for name in frozen
        )

    observer = observer_bytes.decode("utf-8")
    checks["span_exact"] = observer.count(BEGIN) == observer.count(END) == 1
    block = observer[observer.index(BEGIN) : observer.index(END) + len(END)]
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
            path
            for path, text in corpus.items()
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
    checks["actual_consumers_bound"] = not missing

    replacements = {
        expression: f"xmr_{index}" for index, expression in enumerate(expressions)
    }
    focused = block
    for expression, local in replacements.items():
        focused = focused.replace(expression, local)
    declared = set(LOCAL_RE.findall(focused))
    used = set(NAME_RE.findall(focused))
    external = sorted((used - declared) - {"return_obs_write_epoch_owner"})
    declarations = "\n".join(
        [f"  logic [127:0] {name};" for name in external]
        + [f"  logic [127:0] {name};" for name in replacements.values()]
    )
    focused_source = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        f"{declarations}\n{focused}\n"
        '  initial begin #1; return_obs_write_epoch_owner("FOCUS"); end\n'
        "endmodule\n"
    )
    with tempfile.TemporaryDirectory(prefix="v66-epoch-focus-") as temp:
        temp_root = Path(temp)
        positive = compile_case(
            args.iverilog, temp_root, "positive", focused_source
        )
        missing_decl = compile_case(
            args.iverilog,
            temp_root,
            "missing_decl",
            focused_source.replace(
                "  bit return_obs_eo_enabled;", "", 1
            ),
        )
        first_local = next(iter(replacements.values()))
        consumer_typo = compile_case(
            args.iverilog,
            temp_root,
            "consumer_typo",
            focused_source.replace(first_local, first_local + "_typo", 1),
        )
    checks["focused_syntax_scope_positive"] = positive["exit_code"] == 0
    checks["missing_declaration_negative"] = missing_decl["exit_code"] != 0
    checks["actual_consumer_typo_negative"] = consumer_typo["exit_code"] != 0

    feature = " +RETURN_OBS_EPOCH_OWNER +RETURN_OBS_EPOCH_OWNER_LIMIT=128"
    checks["runner_feature_twice"] = runner.count(feature) == 2
    checks["runtime_feature_binding"] = all(
        token in runtime
        for token in (
            '"feature": "RETURN_OBS_EPOCH_OWNER"',
            '"+RETURN_OBS_EPOCH_OWNER"',
            '"+RETURN_OBS_EPOCH_OWNER_LIMIT=128"',
            '"feature=RETURN_OBS_EPOCH_OWNER", "enabled=1", "limit=128"',
        )
    )
    contract = manifest["diagnostic_features"]["RETURN_OBS_EPOCH_OWNER"]
    checks["manifest_feature_binding"] = (
        contract["edge_schema"] == "EPOCH_OWNER_V1"
        and contract["runtime_enable_parameter"] == "+RETURN_OBS_EPOCH_OWNER"
    )
    checks["candidate_matrix_complete"] = all(
        token in block
        for token in (
            "mse_mem_queue_tag[0]",
            "mse_mem_queue_tag[1]",
            "mse_mem_queue_tag[2]",
            "mse_mem_idx_mode[0]",
            "mse_mem_idx_keep_last_index[2]",
            "iga_lc_outport[6]",
            "iga_lc_outport[8]",
            "iga_lc_outport[17]",
            "return_obs_rb_buf_push",
            "return_obs_md_desc_hs",
            "return_obs_md_prepared_wr",
        )
    )

    def emitted(rows: list[tuple[int, ...]]) -> int:
        previous = (0,) * len(rows[0])
        count = 0
        for terminal, *state in rows:
            current = tuple(state)
            if terminal >= 2 and current != previous:
                count += 1
            previous = current
        return count

    trace = [
        (1, 1, 1, 7, 0, 18, 18, 23),
        (2, 1, 1, 7, 0, 18, 19, 23),
        (2, 1, 1, 7, 0, 18, 19, 23),
        (2, 3, 1, 7, 2, 18, 19, 23),
        (3, 1, 1, 7, 0, 18, 20, 27),
        (3, 1, 1, 7, 0, 18, 20, 27),
    ]
    checks["predicate_trace_stable_level_not_progress"] = emitted(trace) == 3

    errors.extend(key for key, value in checks.items() if not value)
    report = {
        "schema": "node0004-v66-epoch-owner-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "zip_sha256": sha(args.zip.read_bytes()),
        "observer_sha256": sha(observer_bytes),
        "actual_consumer_count": len(expressions),
        "uncovered_actual_consumers": len(missing),
        "bindings": bindings,
        "focused_frontend": {
            "positive": positive,
            "missing_declaration": missing_decl,
            "actual_consumer_typo": consumer_typo,
        },
        "predicate_trace": {
            "rows": trace,
            "emitted": emitted(trace),
        },
        "claim_boundary": (
            "Exact v66 per-input epoch-owner observer and feature binding only; "
            "no DUT, natural terminal, formal-D, E4 or E5 claim."
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
