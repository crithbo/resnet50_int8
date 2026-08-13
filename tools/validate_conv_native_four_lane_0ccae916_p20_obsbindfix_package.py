#!/usr/bin/env python3
"""Final family audit for the p20 observer-scope-only successor."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import validate_conv_native_four_lane_0ccae916_p19_dflow_package as base


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p20_obsbindfix"
SOURCE_ID = "r5_n4_0cc_p19b_dflow"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_SHA256 = (
    "ac920faca1e90bcf31371a49529579bd8ec31a0c711a10f6f4820f60778114ef"
)
TAIL_BEGIN = "    // p19 imported qualified D-flow diagnostic tail begin"
TAIL_END = "    // p19 imported qualified D-flow diagnostic tail end"
CONTROL_DECLARATIONS = (
    "bit n4d_enabled;",
    "integer n4d_fd;",
    "bit n4d_active;",
)


def generation_depth(text: str) -> int:
    depth = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "generate":
            depth += 1
        elif stripped == "endgenerate":
            depth -= 1
        if depth < 0:
            return -1
    return depth


def focused_combined_scope_compile(
    observer: str, iverilog: Path, temp_root: Path
) -> dict[str, Any]:
    if observer.count(TAIL_BEGIN) != 1 or observer.count(TAIL_END) != 1:
        raise base.ValidationError("p20 imported-tail markers differ")
    begin = observer.index(TAIL_BEGIN)
    end = observer.index(TAIL_END)
    prefix = observer[:begin]
    tail = observer[begin:end]
    exact_lines: list[str] = []
    declaration_rows: dict[str, int] = {}
    for declaration in CONTROL_DECLARATIONS:
        matches = [
            (index, line)
            for index, line in enumerate(prefix.splitlines(), 1)
            if line.strip() == declaration
        ]
        if len(matches) != 1:
            raise base.ValidationError(
                f"combined-scope declaration differs: {declaration}"
            )
        declaration_rows[declaration] = matches[0][0]
        exact_lines.append(matches[0][1].strip())
    prefix_to_last_decl = "\n".join(
        prefix.splitlines()[: max(declaration_rows.values())]
    )
    declarations_at_module_scope = generation_depth(prefix_to_last_decl) == 0

    expressions = sorted(set(base.XMR_RE.findall(tail)), key=len, reverse=True)
    replacements = {
        expression: f"p20_xmr_{index}"
        for index, expression in enumerate(expressions)
    }
    normalized = tail
    for expression, local in replacements.items():
        normalized = normalized.replace(expression, local)
    normalized = re.sub(
        r"(p20_xmr_[0-9]+)\s*\[\s*p20_xmr_[0-9]+",
        r"\1",
        normalized,
    )
    normalized = re.sub(r"(p20_xmr_[0-9]+)\]", r"\1", normalized)
    normalized = normalized.replace(
        "logic [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0]", "logic [255:0]"
    )
    xmr_declarations = "\n".join(
        f"  logic [255:0] {local};" for local in replacements.values()
    )
    exact_control_source = "\n".join(
        f"  {declaration}" for declaration in exact_lines
    )
    source = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        f"{exact_control_source}\n{xmr_declarations}\n"
        f"{normalized}\nendmodule\n"
    )
    positive = base.compile_case(
        iverilog, temp_root, "p20_combined_scope_positive", source
    )
    missing_controls: dict[str, dict[str, Any]] = {}
    renamed_controls: dict[str, dict[str, Any]] = {}
    for declaration in exact_lines:
        token = declaration.rstrip(";").split()[-1]
        missing_controls[token] = base.compile_case(
            iverilog,
            temp_root,
            f"p20_missing_{token}",
            source.replace(f"  {declaration}\n", "", 1),
        )
        renamed_controls[token] = base.compile_case(
            iverilog,
            temp_root,
            f"p20_renamed_{token}",
            source.replace(token, token + "_wrong", 1),
        )
    valid = (
        positive["exit_code"] == 0
        and declarations_at_module_scope
        and all(row["exit_code"] != 0 for row in missing_controls.values())
        and all(row["exit_code"] != 0 for row in renamed_controls.values())
        and not any(
            token in tail
            for token in (
                "return_obs_enabled",
                "return_obs_fd",
                "return_obs_active",
            )
        )
    )
    return {
        "valid": valid,
        "positive": positive,
        "negative_missing_combined_scope_declaration": missing_controls,
        "negative_renamed_combined_scope_declaration": renamed_controls,
        "declaration_rows": declaration_rows,
        "declarations_at_module_scope": declarations_at_module_scope,
        "legacy_private_symbol_absent": True,
        "xmr_expression_count": len(expressions),
        "tail_sha256": base.digest(tail.encode()),
        "expressions": expressions,
    }


def output_argument() -> Path:
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).resolve()
    raise base.ValidationError("--output is required")


def main() -> int:
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ID = SOURCE_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.focused_tail_compile = focused_combined_scope_compile
    rc = base.main()
    report_path = output_argument()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["schema"] = "conv-native-four-lane-p20-obsbindfix-family-audit-v1"
    report["source_scope"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "changed_surface": (
            "three imported-tail observer control/file symbol bindings only"
        ),
        "xmr_or_predicate_changed": False,
    }
    report["observer"]["combined_scope_escape_regression"] = {
        "p19b_escape": (
            "focused tail compile fabricated return_obs_* declarations"
        ),
        "p20_control": (
            "positive uses exact package n4d declarations; missing and renamed "
            "declaration controls fail closed"
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
