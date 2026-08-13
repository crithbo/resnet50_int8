from __future__ import annotations

import argparse
import hashlib
import json
import re
import tempfile
import zipfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_node0004_v44_observer_syntax import compile_case


INSTALL_NAME = "r5_n4_hw_v51_lc13_lc14_diag"
BEGIN = "// v51 LC13_LC14_ACTUAL_CONSUMER_BEGIN"
END = "// v51 LC13_LC14_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        payload = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    observer = payload.decode()
    block = observer[
        observer.index(BEGIN) : observer.index(END) + len(END)
    ]
    xmrs = sorted(set(XMR_RE.findall(block)), key=len, reverse=True)
    replacements = {
        expression: f"actual_consumer_{index}"
        for index, expression in enumerate(xmrs)
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
    source = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        "  bit return_obs_enabled, return_obs_active;\n"
        "  integer return_obs_fd;\n"
        f"{declarations}\n{normalized}\n"
        "  initial begin #1; "
        'return_obs_write_lc13_lc14_state("FOCUS"); end\nendmodule\n'
    )
    with tempfile.TemporaryDirectory(prefix="v51-lc13-lc14-syntax-") as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog, root, "positive", source)
        missing = compile_case(
            args.iverilog,
            root,
            "negative_missing_declaration",
            source.replace(
                "    bit return_obs_lx_enabled;",
                "    // deleted return_obs_lx_enabled",
                1,
            ),
        )
        task_typo = compile_case(
            args.iverilog,
            root,
            "negative_task_typo",
            source.replace(
                'return_obs_write_lc13_lc14_state("FOCUS")',
                'return_obs_write_lc13_lc14_state_typo("FOCUS")',
                1,
            ),
        )
        first_local = next(iter(replacements.values()))
        consumer_typo = compile_case(
            args.iverilog,
            root,
            "negative_actual_consumer_typo",
            source.replace(first_local, first_local + "_typo", 1),
        )
    checks = {
        "exact_span_once": (
            observer.count(BEGIN) == 1 and observer.count(END) == 1
        ),
        "actual_consumer_nonzero": bool(replacements),
        "positive_exit_zero": positive["exit_code"] == 0,
        "missing_declaration_fail_closed": missing["exit_code"] != 0,
        "task_typo_fail_closed": task_typo["exit_code"] != 0,
        "consumer_typo_fail_closed": consumer_typo["exit_code"] != 0,
    }
    report = {
        "schema": "node0004-v51-lc13-lc14-observer-syntax-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "observer": {
            "bytes": len(payload),
            "sha256": digest(payload),
            "span_sha256": digest(block.encode()),
            "actual_consumer_count": len(replacements),
        },
        "positive": positive,
        "negative_controls": {
            "missing_declaration": missing,
            "task_typo": task_typo,
            "actual_consumer_typo": consumer_typo,
        },
        "claim_boundary": (
            "Compatible-front-end syntax and declaration/use closure for the "
            "exact v51 changed span; hierarchy binding is checked separately."
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
