from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True
INSTALL_NAME = "r5_n4_hw_v24_final_release_diag_compilefix"
OBSERVER_MEMBER = f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
EDGE_COUNTER = "return_obs_fr_buffer5_write_edges"
PREV_LEVEL = "return_obs_fr_prev_buffer5_write"
V23_BAD_IDENTIFIER = "return_obs_buf45_wr_edge_count"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_observer(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC failed")
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise ValueError(f"unsafe ZIP member: {name}")
        return archive.read(OBSERVER_MEMBER).decode("utf-8")


def declarations(text: str) -> set[str]:
    declared: set[str] = set()
    pattern = re.compile(
        r"\b(?:logic|bit|wire|reg|integer|int|longint|genvar|string|"
        r"parameter|localparam)\b(?P<body>[^;]+);",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        declared.update(
            re.findall(r"\breturn_obs_[A-Za-z0-9_]+\b", match.group("body"))
        )
    declared.update(
        re.findall(
            r"\b(?:task|function)\b(?:\s+automatic)?(?:\s+\w+)*\s+"
            r"(return_obs_[A-Za-z0-9_]+)\b",
            text,
        )
    )
    return declared


def focused_identifiers(text: str) -> set[str]:
    return set(re.findall(r"\breturn_obs_fr_[A-Za-z0-9_]+\b", text)) | set(
        re.findall(r"\breturn_obs_buf45_wr_edge_count\b", text)
    )


def semantic_checks(text: str) -> dict[str, bool]:
    declared = declarations(text)
    used = focused_identifiers(text)
    return {
        "all_final_release_identifiers_declared": used <= declared,
        "v23_bad_identifier_absent": V23_BAD_IDENTIFIER not in text,
        "edge_counter_declared_once": text.count(
            f"longint unsigned {EDGE_COUNTER};"
        )
        == 1,
        "edge_counter_reset_once": text.count(f"{EDGE_COUNTER} = 0;") == 1,
        "edge_counter_increment_once": text.count(f"{EDGE_COUNTER}++;") == 1,
        "edge_counter_boundary_use_once": text.count(
            f"{EDGE_COUNTER},"
        )
        == 1,
        "previous_level_declared_once": text.count(
            f"logic {PREV_LEVEL};"
        )
        == 1,
        "previous_level_reset_once": text.count(
            f"{PREV_LEVEL} = 1'b0;"
        )
        == 1,
        "qualified_rising_edge_predicate": (
            "|return_obs_buf45_wr_en_mon" in text
            and f"!{PREV_LEVEL}" in text
            and f"{EDGE_COUNTER}++;" in text
        ),
        "count_empty_not_used_as_progress": (
            "corroborating_state_only" not in text
            and "count_state=" in text
            and "empty_state=" in text
        ),
    }


def focused_source(text: str) -> str:
    edge_decl = (
        f"  longint unsigned {EDGE_COUNTER};\n"
        if f"longint unsigned {EDGE_COUNTER};" in text
        else ""
    )
    prev_decl = (
        f"  logic {PREV_LEVEL};\n"
        if f"logic {PREV_LEVEL};" in text
        else ""
    )
    update_match = re.search(
        r"\b(return_obs_fr_buffer5_write_edges(?:_TYPO)?)\+\+;", text
    )
    update = (
        f"      {update_match.group(1)}++;\n"
        if update_match
        else "      /* update deliberately absent */\n"
    )
    return (
        "module observer_scope_focus;\n"
        "  logic clk, rst_n, enabled, active;\n"
        "  logic [1:0] buffer5_wr_en;\n"
        f"{prev_decl}{edge_decl}"
        "  always @(posedge clk or negedge rst_n) begin\n"
        "    if (!rst_n) begin\n"
        f"      {PREV_LEVEL} <= 1'b0;\n"
        f"      {EDGE_COUNTER} <= 0;\n"
        "    end else if (enabled && active) begin\n"
        f"      if ((|buffer5_wr_en) && !{PREV_LEVEL}) begin\n"
        f"{update}"
        "      end\n"
        f"      {PREV_LEVEL} <= |buffer5_wr_en;\n"
        "    end\n"
        "  end\n"
        "endmodule\n"
    )


def compile_focus(
    text: str, iverilog: Path, temporary: Path, name: str
) -> dict[str, Any]:
    source = temporary / f"{name}.sv"
    output = temporary / f"{name}.vvp"
    source.write_text(
        focused_source(text), encoding="utf-8", newline="\n"
    )
    process = subprocess.run(
        [
            str(iverilog),
            "-g2012",
            "-s",
            "observer_scope_focus",
            "-o",
            str(output),
            str(source),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": (
            f"{iverilog} -g2012 -s observer_scope_focus "
            f"-o {output.name} {source.name}"
        ),
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "source_sha256": sha256_bytes(source.read_bytes()),
    }


def evaluate(
    text: str, iverilog: Path, temporary: Path, name: str
) -> tuple[bool, dict[str, bool], dict[str, Any]]:
    checks = semantic_checks(text)
    compile_result = compile_focus(text, iverilog, temporary, name)
    passed = all(checks.values()) and compile_result["exit_code"] == 0
    return passed, checks, compile_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    iverilog = args.iverilog.resolve()
    observer = read_observer(zip_path)

    with tempfile.TemporaryDirectory(
        prefix="node0004-v24-observer-scope-"
    ) as temp:
        temporary = Path(temp)
        positive, checks, compile_result = evaluate(
            observer, iverilog, temporary, "positive"
        )
        mutations = {
            "delete_edge_counter_declaration": observer.replace(
                f"    longint unsigned {EDGE_COUNTER};\n", "", 1
            ),
            "typo_edge_counter_use": observer.replace(
                f"{EDGE_COUNTER}++;", f"{EDGE_COUNTER}_TYPO++;", 1
            ),
            "delete_edge_counter_update": observer.replace(
                f"                {EDGE_COUNTER}++;\n", "", 1
            ),
        }
        negatives: dict[str, Any] = {}
        for name, changed in mutations.items():
            valid, neg_checks, neg_compile = evaluate(
                changed, iverilog, temporary, name
            )
            negatives[name] = {
                "expected_validator_exit": 1,
                "observed_validator_exit": 0 if valid else 1,
                "failed_closed": not valid,
                "semantic_checks": neg_checks,
                "focused_compile": neg_compile,
            }
        all_negatives = all(
            item["failed_closed"] for item in negatives.values()
        )

    version = subprocess.run(
        [str(iverilog), "-V"],
        text=True,
        capture_output=True,
        check=False,
    )
    report = {
        "schema": "node0004-v24-observer-syntax-scope-gate-v1",
        "valid": positive and all_negatives,
        "status": (
            "OBSERVER_FOCUSED_SYNTAX_SCOPE_PASS"
            if positive and all_negatives
            else "OBSERVER_FOCUSED_SYNTAX_SCOPE_FAILED"
        ),
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        },
        "observer_member": OBSERVER_MEMBER,
        "observer_sha256": sha256_bytes(observer.encode("utf-8")),
        "machine_identifier_declaration_use_checks": checks,
        "focused_compatible_frontend": {
            "tool": str(iverilog),
            "version_exit": version.returncode,
            "version_stdout_first_line": (
                version.stdout.splitlines()[0] if version.stdout else ""
            ),
            "claim_boundary": (
                "Icarus compiles the exact corrected counter declaration/use "
                "subset; whole-observer generated XMR remains guarded by the "
                "machine declaration/use scan and existing XMR constant scan, "
                "while server VCS remains final full elaboration evidence."
            ),
            "positive": compile_result,
        },
        "negative_controls": negatives,
        "all_negative_controls_fail_closed": all_negatives,
        "safe_compile_stub_used_as_hdl_evidence": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
