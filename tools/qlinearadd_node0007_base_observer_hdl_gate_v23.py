from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


HDL_RULE_ID = "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
NATIVE = "tb_probe/native_return_observer.svh"
TAIL = "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")


class GateError(ValueError):
    pass


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def declared_identifiers(text: str, prefix: str) -> set[str]:
    declared: set[str] = set()
    declaration = re.compile(
        r"\b(?:logic|bit|wire|reg|integer|int|longint|genvar|string|"
        r"parameter|localparam)\b(?P<body>[^;]+);",
        re.DOTALL,
    )
    token = re.compile(rf"\b{re.escape(prefix)}[A-Za-z0-9_]+\b")
    for match in declaration.finditer(text):
        declared.update(token.findall(match.group("body")))
    declared.update(
        re.findall(
            rf"\b(?:task|function)\b(?:\s+automatic)?(?:\s+\w+)*\s+"
            rf"({re.escape(prefix)}[A-Za-z0-9_]+)\b",
            text,
        )
    )
    return declared


def closure(text: str, prefix: str) -> dict[str, Any]:
    used = set(re.findall(rf"\b{re.escape(prefix)}[A-Za-z0-9_]+\b", text))
    declared = declared_identifiers(text, prefix)
    unresolved = sorted(used - declared)
    return {
        "prefix": prefix,
        "used_count": len(used),
        "declared_count": len(declared),
        "unresolved": unresolved,
        "valid": not unresolved,
    }


def require_one(pattern: str, text: str, name: str, flags: int = 0) -> str:
    matches = re.findall(pattern, text, flags)
    if len(matches) != 1:
        raise GateError(f"{name} exact-count differs: {len(matches)}")
    value = matches[0]
    return value if isinstance(value, str) else value[0]


def semantic_checks(native: str, tail: str) -> dict[str, bool]:
    full = native + "\n" + tail
    return {
        "native_includes_tail_once": native.count(
            '`include "qlinearadd_node0007_first_request_observer_tail_v9.svh"'
        )
        == 1,
        "return_obs_declaration_use_closed": closure(full, "return_obs_")["valid"],
        "qadd_fr_declaration_use_closed": closure(full, "qadd_fr_")["valid"],
        "base_req_declaration_once": native.count(
            "longint unsigned return_obs_req_count "
        )
        == 1,
        "base_req_consumer_once": native.count(
            "request_total += return_obs_req_count[mse];"
        )
        == 1,
        "base_req_qualified_update_once": native.count(
            "return_obs_req_count[mse]++;"
        )
        == 1,
        "tail_enqueue_declaration_once": tail.count(
            "longint unsigned qadd_fr_mse0_req_enqueue_count;"
        )
        == 1,
        "tail_enqueue_qualified_update_once": tail.count(
            "qadd_fr_mse0_req_enqueue_count++;"
        )
        == 1,
        "tail_enqueue_consumer_once": tail.count(
            "qadd_fr_mse0_req_enqueue_count,"
        )
        == 1,
    }


def focus_source(native: str, tail: str) -> str:
    base_decl = require_one(
        r"(longint unsigned return_obs_req_count "
        r"\[0:`MEMORY_STREAM_ENGINE_NUM-1\];)",
        native,
        "base declaration",
    )
    base_update = require_one(
        r"(return_obs_req_count\[mse\]\+\+;)",
        native,
        "base qualified update",
    )
    base_use = require_one(
        r"(request_total \+= return_obs_req_count(?:_TYPO)?\[mse\];)",
        native,
        "base consumer use",
    )
    tail_decl = require_one(
        r"(longint unsigned qadd_fr_mse0_req_enqueue_count;)",
        tail,
        "tail declaration",
    )
    tail_update = require_one(
        r"(qadd_fr_mse0_req_enqueue_count\+\+;)",
        tail,
        "tail qualified update",
    )
    return (
        "`timescale 1ns/1ps\n"
        "`define MEMORY_STREAM_ENGINE_NUM 1\n"
        "module observer_scope_focus;\n"
        "  logic clk;\n"
        "  logic local_req_hs [0:0][0:0][0:0][0:0];\n"
        "  logic qadd_fr_mse0_req_enqueue_hs_mon [0:0][0:0];\n"
        "  integer return_obs_group_id = 0;\n"
        "  integer return_obs_local_slice_id = 0;\n"
        f"  {base_decl}\n"
        f"  {tail_decl}\n"
        "  always @(posedge clk) begin\n"
        "    for (int mse=0; mse<`MEMORY_STREAM_ENGINE_NUM; mse++) begin\n"
        "      for (int req=0; req<1; req++) begin\n"
        "        if (local_req_hs[return_obs_group_id]"
        "[return_obs_local_slice_id][mse][req]) begin\n"
        f"          {base_update}\n"
        "        end\n"
        "      end\n"
        "    end\n"
        "    if (qadd_fr_mse0_req_enqueue_hs_mon"
        "[return_obs_group_id][return_obs_local_slice_id])\n"
        f"      {tail_update}\n"
        "  end\n"
        "  initial begin\n"
        "    longint unsigned request_total = 0;\n"
        "    for (int mse=0; mse<`MEMORY_STREAM_ENGINE_NUM; mse++) begin\n"
        f"      {base_use}\n"
        "    end\n"
        "    $display(\"%0d %0d\", request_total, "
        "qadd_fr_mse0_req_enqueue_count);\n"
        "  end\n"
        "endmodule\n"
    )


def run_frontend(
    native: str, tail: str, temporary: Path, name: str
) -> dict[str, Any]:
    case = temporary / name
    case.mkdir()
    native_path = case / "native_return_observer.svh"
    tail_path = case / "qlinearadd_node0007_first_request_observer_tail_v9.svh"
    native_path.write_text(native, encoding="utf-8", newline="\n")
    tail_path.write_text(tail, encoding="utf-8", newline="\n")
    preprocessed = case / "preprocessed.sv"
    preprocess = subprocess.run(
        [
            str(IVERILOG),
            "-g2012",
            "-E",
            "-I",
            str(case),
            "-o",
            str(preprocessed),
            str(native_path),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    try:
        focus = focus_source(native, tail)
        focus_error = None
    except GateError as exc:
        focus = "module observer_scope_focus; INVALID_FOCUS_CONTRACT x; endmodule\n"
        focus_error = str(exc)
    focus_path = case / "focus.sv"
    focus_path.write_text(focus, encoding="utf-8", newline="\n")
    output = case / "focus.vvp"
    compile_result = subprocess.run(
        [
            str(IVERILOG),
            "-g2012",
            "-s",
            "observer_scope_focus",
            "-o",
            str(output),
            str(focus_path),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    checks = semantic_checks(native, tail)
    valid = (
        preprocess.returncode == 0
        and compile_result.returncode == 0
        and focus_error is None
        and all(checks.values())
    )
    return {
        "valid": valid,
        "validator_exit": 0 if valid else 1,
        "semantic_checks": checks,
        "exact_member_preprocess": {
            "command": (
                f"{IVERILOG} -g2012 -E -I <exact-tb_probe> "
                "-o preprocessed.sv native_return_observer.svh"
            ),
            "exit_code": preprocess.returncode,
            "stderr_sha256": sha_bytes(preprocess.stderr.encode()),
            "warning_line_count": len(preprocess.stderr.splitlines()),
            "preprocessed_sha256": (
                sha_bytes(preprocessed.read_bytes())
                if preprocessed.is_file()
                else None
            ),
        },
        "focused_compile": {
            "command": (
                f"{IVERILOG} -g2012 -s observer_scope_focus "
                "-o focus.vvp focus.sv"
            ),
            "exit_code": compile_result.returncode,
            "stdout": compile_result.stdout,
            "stderr": compile_result.stderr,
            "source_sha256": sha_bytes(focus.encode()),
            "focus_contract_error": focus_error,
        },
    }


def package_local_hdl_gate(
    files: dict[str, bytes], manifest: dict[str, Any]
) -> dict[str, Any]:
    native = files[NATIVE].decode()
    tail = files[TAIL].decode()
    contract = manifest.get("package_local_hdl_syntax_scope_contract", {})
    exact_members = [
        {
            "path": path,
            "bytes": len(files[path]),
            "sha256": sha_bytes(files[path]),
            "role": role,
        }
        for path, role in (
            (NATIVE, "package-local observer body"),
            (TAIL, "included first-request qualified tail"),
        )
    ]
    declared_members = contract.get("members", [])
    member_binding = all(
        any(
            item.get("relative_path") == record["path"]
            and item.get("bytes") == record["bytes"]
            and item.get("sha256") == record["sha256"]
            for item in declared_members
        )
        for record in exact_members
    )
    include_order = [
        "package-local +incdir tb_probe",
        "native_return_observer.svh",
        "qlinearadd_node0007_first_request_observer_tail_v9.svh",
    ]
    include_sha = sha_bytes(
        json.dumps(include_order, separators=(",", ":")).encode()
    )
    with tempfile.TemporaryDirectory(prefix="qadd-v23-hdl-gate-") as raw:
        temporary = Path(raw)
        positive = run_frontend(native, tail, temporary, "positive")
        declaration_pattern = re.compile(
            r"\s*longint unsigned return_obs_req_count "
            r"\[0:`MEMORY_STREAM_ENGINE_NUM-1\];"
        )
        no_declaration, count = declaration_pattern.subn("", native, count=1)
        if count != 1:
            raise GateError("delete declaration preimage differs")
        mutations = {
            "delete_declaration": (no_declaration, tail),
            "misspell_consumer_use": (
                native.replace(
                    "request_total += return_obs_req_count[mse];",
                    "request_total += return_obs_req_count_TYPO[mse];",
                    1,
                ),
                tail,
            ),
            "delete_qualified_update": (
                native,
                tail.replace("qadd_fr_mse0_req_enqueue_count++;", "", 1),
            ),
        }
        negatives = {
            name: run_frontend(nat, tai, temporary, name)
            for name, (nat, tai) in mutations.items()
        }
    version = subprocess.run(
        [str(IVERILOG), "-V"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    all_negative = all(not item["valid"] for item in negatives.values())
    checks = {
        "contract_rule_id": contract.get("rule_id") == HDL_RULE_ID,
        "exact_member_binding": member_binding,
        "include_order": contract.get("include_order") == include_order,
        "compile_macro_profile": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE"
            in contract.get("compile_macro_profile", "")
        ),
        "positive_frontend": positive["valid"],
        "three_negative_controls_fail_closed": all_negative,
    }
    return {
        "applicable": True,
        "rule_id": HDL_RULE_ID,
        "valid": all(checks.values()),
        "checks": checks,
        "exact_members": exact_members,
        "include_or_concatenation_order_sha256": include_sha,
        "frontend": {
            "name": "Icarus Verilog",
            "path": str(IVERILOG),
            "version_exit": version.returncode,
            "version_first_line": (
                (version.stdout + version.stderr).splitlines()[0]
                if version.stdout or version.stderr
                else ""
            ),
            "positive": positive,
            "claim_boundary": (
                "Icarus preprocesses both exact final-ZIP HDL members in actual "
                "include order and compiles an exact-snippet focused subset for "
                "the base request counter and first-request enqueue counter. "
                "Machine closure covers every return_obs_ and qadd_fr_ identifier. "
                "Production VCS remains final full-design elaboration evidence."
            ),
        },
        "declaration_use_update_closure": {
            "return_obs": closure(native + "\n" + tail, "return_obs_"),
            "qadd_fr": closure(native + "\n" + tail, "qadd_fr_"),
            "required_state_leaves": [
                "return_obs_req_count",
                "qadd_fr_mse0_req_enqueue_count",
            ],
        },
        "negative_controls": negatives,
        "all_negative_controls_fail_closed": all_negative,
        "safe_compile_stub_used_as_hdl_evidence": False,
    }
