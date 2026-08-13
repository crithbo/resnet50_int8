from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


INSTALL_NAME = "r5_n4_hw_v44_lc9_split_diag"
VERSION = 44
BEGIN = "    // v44 LC9_SPLIT_ACTUAL_CONSUMER_BEGIN"
END = "    // v44 LC9_SPLIT_ACTUAL_CONSUMER_END"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compile_case(
    iverilog: Path, root: Path, name: str, source: str
) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    command = [
        str(iverilog),
        "-g2012",
        "-s",
        "lc9_split_focus_top",
        "-o",
        str(output_path),
        str(source_path),
    ]
    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def normalized_source(block: str) -> tuple[str, dict[str, str]]:
    unique = sorted(set(XMR_RE.findall(block)), key=len, reverse=True)
    replacements = {
        expression: f"actual_consumer_{index}"
        for index, expression in enumerate(unique)
    }
    normalized = block
    for expression, local in replacements.items():
        normalized = normalized.replace(expression, local)
    declarations = "\n".join(
        f"  logic [63:0] {local};" for local in replacements.values()
    )
    source = (
        "`timescale 1ns/1ps\n"
        "module lc9_split_focus_top;\n"
        "  bit return_obs_enabled, return_obs_active;\n"
        "  integer return_obs_fd;\n"
        f"{declarations}\n"
        f"{normalized}\n"
        "  initial begin\n"
        "    #1; return_obs_write_lc9_split_state(\"FOCUS\");\n"
        "  end\n"
        "endmodule\n"
    )
    return source, replacements


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
    begin = observer.index(BEGIN)
    end = observer.index(END) + len(END)
    block = observer[begin:end]
    source, replacements = normalized_source(block)
    with tempfile.TemporaryDirectory(
        prefix=f"v{VERSION}-lc9-syntax-"
    ) as temp:
        root = Path(temp)
        positive = compile_case(args.iverilog, root, "positive", source)
        missing_enable = compile_case(
            args.iverilog,
            root,
            "negative_missing_enable",
            source.replace(
                "    bit return_obs_ls_enabled;",
                "    // deleted return_obs_ls_enabled",
                1,
            ),
        )
        task_typo = compile_case(
            args.iverilog,
            root,
            "negative_task_typo",
            source.replace(
                'return_obs_write_lc9_split_state("FOCUS")',
                'return_obs_write_lc9_split_state_typo("FOCUS")',
                1,
            ),
        )
        local_typo = compile_case(
            args.iverilog,
            root,
            "negative_normalized_consumer_typo",
            source.replace(
                next(iter(replacements.values())),
                next(iter(replacements.values())) + "_typo",
                1,
            ),
        )
    checks = {
        "exact_final_span_present_once": (
            observer.count(BEGIN) == 1 and observer.count(END) == 1
        ),
        "actual_consumer_occurrences_nonzero": bool(replacements),
        "focused_compatible_frontend_positive": positive["exit_code"] == 0,
        "missing_declaration_fail_closed": missing_enable["exit_code"] != 0,
        "task_typo_fail_closed": task_typo["exit_code"] != 0,
        "normalized_consumer_typo_fail_closed": local_typo["exit_code"] != 0,
    }
    report = {
        "schema": f"node0004-v{VERSION}-lc9-split-observer-syntax-v1",
        "valid": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "final_observer": {
            "bytes": len(payload),
            "sha256": sha256(payload),
            "span_sha256": sha256(block.encode()),
        },
        "normalized_actual_consumer_count": len(replacements),
        "frontend_positive": positive,
        "negative_controls": {
            "missing_declaration": missing_enable,
            "task_typo": task_typo,
            "normalized_consumer_typo": local_typo,
        },
        "claim_boundary": (
            "compatible-frontend syntax and package-local declaration/use "
            f"closure for the exact final v{VERSION} span. XMR scope is not fabricated "
            "here; it is independently bound to actual RTL declarations and "
            "instances by actual_hdl_consumers.json."
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
