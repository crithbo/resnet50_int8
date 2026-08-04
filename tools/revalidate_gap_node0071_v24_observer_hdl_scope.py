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

INSTALL_NAME = "r5_n71_gap_v24_prep_count_cause_diag"
OBSERVER_MEMBER = f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
EXPECTED_ZIP_BYTES = 1_812_177
EXPECTED_ZIP_SHA256 = (
    "ad71f6d6ab75f0992505d9d4656c058aa4011776bfc9b7c1c14bd78ec9b428ab"
)
EXPECTED_OBSERVER_SHA256 = (
    "a4499c2532a3b0709a3cde34c0f6d29260195a469047fe29d6fd223f3df4fb5f"
)

TYPE_PATTERN = (
    r"(?:logic|bit|wire|reg|integer|string|time|"
    r"int(?:\s+unsigned)?|longint(?:\s+unsigned)?)"
)
IDENTIFIER_PATTERN = r"return_obs_[A-Za-z0-9_]+"
PC_DECLARATION_ANCHOR = (
    "    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0][1:0]\n"
    "          return_obs_pc_rst_n_mon"
)
PC_END_ANCHOR = "\n    bit return_obs_pc_enabled;"
CRITICAL_UPDATE = "return_obs_pc_wr_count[pc_flow]++;"
DECLARATION_NEGATIVE = "    bit return_obs_pc_enabled;\n"
TYPO_IDENTIFIER = "return_obs_pc_enabled_typo"
PC_RTL_LEAVES = {
    "rst_n": 1,
    "slice_rst": 1,
    "rd_data_chl_prepared_data_wr_hs": 1,
    "rd_data_chl_prepared_data_rd_hs": 1,
    "rd_data_chl_data_vld": 1,
    "prepared_data_lt_req": 1,
    "rd_data_chl_prepared_data_bp_pre": 1,
    "rd_data_chl_ob_bp_pre": 1,
    "rd_data_chl_prepared_data_cnt": 8,
    "rd_chl_queue_rd_tsf_size": 8,
    "mse_buf_spatial_size": 8,
}

RULE_RECEIPTS = {
    ".agents/agent.md": (
        "aae402d48b82d026c5512c8a6a5d4c9ff9db4bcc6a94576cd618c168f3fd188e"
    ),
    ".agents/rules/生成前必读索引.md": (
        "3f992273e86f02b8ea4f68f217e686a5a525a045b5fd4d6c88f2f8ef5d1ff4c5"
    ),
    ".agents/rules/算子配置规则.md": (
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "c230db601433cd3f8f4344e7e43b3be4d069d8dd8a28057f07b56910dba555cd"
    ),
    ".agents/rules/GAP_int32_mac_bypass_rules.md": (
        "4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b"
    ),
    ".agents/rules/GAP_probe_v7_validator_rules.md": (
        "db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1"
    ),
    ".agents/rules/精确UINT8量化尾专项规则.md": (
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
    ),
}

MACROS = {
    "SLICE_GROUP_SIZE": 1,
    "SLICE_GROUP_NUM": 1,
    "GA_ROW_PE_NUM": 4,
    "GA_PE_INPORT_NUM": 4,
    "GA_PE_ALU_DATA_WIDTH": 32,
    "GA_PE_ALU_TAG_WIDTH": 8,
    "GA_PE_OUTBUFFER_PTR_WIDTH": 2,
    "GA_PE_OUTBUFFER_CNT_WIDTH": 3,
    "GA_PE_OUTBUFFER_DEPTH": 4,
    "GA_PE_OUTBUFFER_TAG_WIDTH": 8,
    "GA_PE_OUTBUFFER_DATA_WIDTH": 32,
    "GA_PE_PORT_TAG_WIDTH": 8,
    "GA_INPORT_NUM": 4,
    "GA_INPORT_TAG": 8,
    "SA_INPORT_GROUP_NUM": 2,
    "SA_INPORT_SRC_NUM": 4,
    "SA_INPORT_GROUP_TAG": 8,
    "SA_OUTPORT_GROUP_TAG": 8,
    "SA_OUTPORT_GROUP_NUM": 2,
    "SA_PORT_HANDLE_BUF_NUM": 2,
    "ARRAY_PORT_TAG": 8,
    "BUFFER_BANK_NUM": 4,
    "VALID_BUFFER_DEPTH": 4,
    "VALID_BUFFER_BANK_WIDTH": 8,
    "BUFFER_BANK_ADDR_WIDTH": 8,
    "BUFFER_LIFE_TIME_WIDTH": 8,
    "MSE_REQ_CHL_NUM": 2,
    "MSE_MEM_REQ_ADDR_WIDTH": 32,
    "MSE_MEM_AG_INPORT_NUM": 3,
    "MSE_MEM_AG_INPORT_IDX_WIDTH": 8,
    "MSE_TSA_IDX_WIDTH": 8,
    "MSE_TSA_ADDR_WIDTH": 16,
    "MSE_TSF_ADDR_WIDTH": 16,
    "MSE_TSF_SIZE_WIDTH": 8,
    "MSE_VALID_MASK_WIDTH": 16,
    "MSE_PADDING_MASK_WIDTH": 16,
    "MSE_BUF_REQ_NUM": 16,
    "MSE_BUF_REQ_DATA_WIDTH": 32,
    "DDR_ADDR_OFFSET_WIDTH": 32,
    "DDR_COL_DATA_WIDTH": 128,
    "IGA_LC_PORT_WIDTH": 32,
    "IGA_PE_PORT_WIDTH": 32,
    "MEMORY_STREAM_ENGINE_NUM": 6,
    "BANK_NUM_PER_SLICE": 8,
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "argv": command,
        "cwd": str(cwd) if cwd else None,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def read_exact_observer(
    zip_path: Path,
    install_name: str,
    expected_zip_bytes: int,
    expected_zip_sha256: str,
    expected_observer_sha256: str,
) -> tuple[bytes, bytes, dict[str, Any]]:
    observer_member = f"{install_name}/tb_probe/native_return_observer.svh"
    manifest_member = f"{install_name}/TEST_PACKAGE_MANIFEST.json"
    if zip_path.stat().st_size != expected_zip_bytes:
        raise ValueError("frozen ZIP byte size differs")
    zip_sha = sha256_path(zip_path)
    if zip_sha != expected_zip_sha256:
        raise ValueError("frozen ZIP SHA256 differs")
    with zipfile.ZipFile(zip_path) as archive:
        crc_bad = archive.testzip()
        if crc_bad is not None:
            raise ValueError(f"ZIP CRC failed at {crc_bad}")
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        unsafe = []
        symlinks = []
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if (unix_mode & 0o170000) == 0o120000:
                symlinks.append(info.filename)
        if unsafe or symlinks:
            raise ValueError(
                f"unsafe={unsafe!r}, symlinks={symlinks!r}"
            )
        if observer_member not in names or manifest_member not in names:
            raise ValueError("observer member absent")
        payload = archive.read(observer_member)
        manifest_payload = archive.read(manifest_member)
    observer_sha = sha256_bytes(payload)
    if observer_sha != expected_observer_sha256:
        raise ValueError("exact observer member SHA256 differs")
    return payload, manifest_payload, {
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "crc_pass": True,
        "duplicate_free": True,
        "path_safe": True,
        "symlink_free": True,
        "observer_member": observer_member,
        "observer_bytes": len(payload),
        "observer_sha256": observer_sha,
    }


def strip_comments_and_strings(text: str) -> str:
    pattern = re.compile(
        r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"",
        re.DOTALL,
    )
    return pattern.sub(lambda match: " " * len(match.group(0)), text)


def declaration_spans(code: str) -> tuple[set[str], dict[str, int]]:
    declared: set[str] = set()
    counts: dict[str, int] = {}
    statement = re.compile(rf"\b{TYPE_PATTERN}\b(?P<body>[^;]*);", re.DOTALL)
    for match in statement.finditer(code):
        for identifier in re.findall(rf"\b{IDENTIFIER_PATTERN}\b", match.group()):
            declared.add(identifier)
            counts[identifier] = counts.get(identifier, 0) + 1
    for pattern in (
        rf"\btask\s+automatic\s+({IDENTIFIER_PATTERN})\b",
        rf"\bfunction(?:\s+automatic)?(?:\s+\w+)*\s+({IDENTIFIER_PATTERN})\b",
        rf"\bgenvar\s+({IDENTIFIER_PATTERN})\b",
    ):
        for identifier in re.findall(pattern, code):
            declared.add(identifier)
            counts[identifier] = counts.get(identifier, 0) + 1
    return declared, counts


def identifier_ledger(text: str) -> dict[str, Any]:
    code = strip_comments_and_strings(text)
    declared, declaration_counts = declaration_spans(code)
    tokens = re.findall(rf"\b{IDENTIFIER_PATTERN}\b", code)
    token_counts = {identifier: tokens.count(identifier) for identifier in set(tokens)}
    used = set(tokens)
    task_names = set(
        re.findall(rf"\btask\s+automatic\s+({IDENTIFIER_PATTERN})\b", code)
    )
    genvars = set(
        re.findall(rf"\bgenvar\s+({IDENTIFIER_PATTERN})\b", code)
    )
    updates: dict[str, int] = {}
    update_pattern = re.compile(
        rf"\b(?P<id>{IDENTIFIER_PATTERN})\b"
        r"(?:\s*\[[^\]\n]+\])*\s*"
        r"(?:<=|(?<![=!<>])=(?!=)|\+\+|--|\+=|-=)",
    )
    for match in update_pattern.finditer(code):
        identifier = match.group("id")
        updates[identifier] = updates.get(identifier, 0) + 1
    callable_calls = {}
    for identifier in task_names:
        callable_calls[identifier] = max(
            0,
            len(re.findall(rf"\b{re.escape(identifier)}\s*\(", code)) - 1,
        )
    undeclared_uses = sorted(used - declared)
    declared_without_non_declaration_use = sorted(
        identifier
        for identifier in declared
        if token_counts.get(identifier, 0) <= declaration_counts.get(identifier, 0)
    )
    state_without_update = sorted(
        identifier
        for identifier in declared - task_names - genvars
        if updates.get(identifier, 0) == 0
    )
    uncalled_tasks = sorted(
        identifier
        for identifier, count in callable_calls.items()
        if count == 0
    )
    critical_update_count = code.count(CRITICAL_UPDATE)
    summary = {
        "identifier_count": len(used),
        "declared_identifier_count": len(declared),
        "undeclared_uses": undeclared_uses,
        "declared_without_non_declaration_use": declared_without_non_declaration_use,
        "state_without_update": state_without_update,
        "uncalled_tasks": uncalled_tasks,
        "critical_update": CRITICAL_UPDATE,
        "critical_update_count": critical_update_count,
        "valid": (
            not undeclared_uses
            and not declared_without_non_declaration_use
            and not state_without_update
            and not uncalled_tasks
            and critical_update_count == 1
        ),
    }
    ledger = {
        identifier: {
            "declarations": declaration_counts.get(identifier, 0),
            "tokens_excluding_declarations": (
                token_counts.get(identifier, 0)
                - declaration_counts.get(identifier, 0)
            ),
            "updates": updates.get(identifier, 0),
            "kind": (
                "task"
                if identifier in task_names
                else "genvar"
                if identifier in genvars
                else "state_or_monitor"
            ),
        }
        for identifier in sorted(used | declared)
    }
    return {"summary": summary, "ledger": ledger}


def macro_prelude() -> str:
    return "".join(
        f"`define {name} {value}\n" for name, value in MACROS.items()
    )


def make_scope_projection(observer: str) -> tuple[str, dict[str, Any]]:
    assignment_pattern = re.compile(
        r"(?ms)(^\s*assign\s+return_obs_[^;]*?=).*?;"
    )
    projected, assignment_count = assignment_pattern.subn(
        lambda match: match.group(1) + " '0;",
        observer,
    )
    substitutions = {
        "u_NDP_Top_new.clk_db": "return_obs_scope_clk_db",
        "u_NDP_Top_new.rst_n_db": "return_obs_scope_rst_n_db",
        "u_NDP_Top_new.clk_sg": "return_obs_scope_clk_sg",
        "u_NDP_Top_new.rst_n_sg": "return_obs_scope_rst_n_sg",
    }
    substitution_counts = {}
    for source, target in substitutions.items():
        substitution_counts[source] = projected.count(source)
        projected = projected.replace(source, target)
    remaining_xmr = projected.count("u_NDP_Top_new.")
    source = (
        macro_prelude()
        + "module gap_v24_exact_observer_scope_projection;\n"
        + "logic return_obs_scope_clk_db, return_obs_scope_rst_n_db;\n"
        + "logic return_obs_scope_clk_sg, return_obs_scope_rst_n_sg;\n"
        + projected
        + "\nendmodule\n"
        + "module gap_v24_scope_parse_driver;\n"
        + "endmodule\n"
    )
    return source, {
        "continuous_assignment_rhs_neutralized": assignment_count,
        "clock_reset_substitutions": substitution_counts,
        "remaining_external_xmr": remaining_xmr,
        "projection_sha256": sha256_bytes(source.encode("utf-8")),
        "claim_boundary": (
            "The projection compiles every exact final observer declaration, "
            "task, procedural use and update while neutralizing only external "
            "DUT XMR RHS values and four TB clock/reset leaves. Icarus parses "
            "this complete projection without elaborating its packed-array "
            "procedures; the machine ledger proves observer-internal lexical "
            "declaration/use/update closure. This is not whole-production-NDP "
            "elaboration."
        ),
    }


def extract_pc_block(observer: str) -> str:
    start = observer.find(PC_DECLARATION_ANCHOR)
    end = observer.find(PC_END_ANCHOR, start)
    if start < 0 or end < 0:
        raise ValueError("v24 prepared-count focused block anchors absent")
    return observer[start:end]


def extract_pc_state_spans(observer: str) -> dict[str, str]:
    declaration_start = observer.find("    bit return_obs_pc_enabled;")
    declaration_end = observer.find(
        "\n    bit return_obs_enabled;", declaration_start
    )
    consumer_start = observer.rfind(
        "    always @(posedge u_NDP_Top_new.clk_sg) begin"
    )
    consumer_end = observer.find(
        "\n    final begin", consumer_start
    )
    if min(
        declaration_start,
        declaration_end,
        consumer_start,
        consumer_end,
    ) < 0:
        raise ValueError("v24 prepared-count state span anchors absent")
    return {
        "declaration_reset": observer[declaration_start:declaration_end],
        "qualified_update_consumer": observer[consumer_start:consumer_end],
        "initialization": (
            '        return_obs_pc_enabled =\n'
            '            $test$plusargs("RETURN_OBS_PREP_COUNT_CAUSE");\n'
            "        return_obs_pc_limit = 512;\n"
            "        return_obs_pc_reset();\n"
        ),
    }


def make_state_focus(observer: str) -> tuple[str, dict[str, Any]]:
    spans = extract_pc_state_spans(observer)
    monitor_bits = (
        "return_obs_pc_rst_n_mon return_obs_pc_slice_rst_mon "
        "return_obs_pc_wr_mon return_obs_pc_rd_mon "
        "return_obs_pc_data_vld_mon return_obs_pc_lt_req_mon "
        "return_obs_pc_bp_pre_mon return_obs_pc_ob_bp_pre_mon"
    ).split()
    monitor_bytes = (
        "return_obs_pc_count_mon return_obs_pc_tsf_mon "
        "return_obs_pc_spatial_mon"
    ).split()
    external = [
        "module gap_v24_state_clock_focus;",
        "    logic clk_sg, rst_n_sg;",
        "endmodule",
        "module gap_v24_prepared_count_state_focus;",
        "    gap_v24_state_clock_focus u_NDP_Top_new();",
        *(
            f"    logic {name} [0:0][0:0][0:1];"
            for name in monitor_bits
        ),
        *(
            f"    logic [7:0] {name} [0:0][0:0][0:1];"
            for name in monitor_bytes
        ),
        "    bit return_obs_enabled, return_obs_active;",
        "    integer return_obs_fd;",
        "    int return_obs_group_id, return_obs_local_slice_id;",
        "    longint unsigned return_obs_sg_clock_edge_count;",
    ]
    initialization = (
        "    initial begin\n"
        + spans["initialization"]
        + "    end\n"
    )
    source = (
        "\n".join(external)
        + "\n"
        + spans["declaration_reset"]
        + "\n"
        + initialization
        + spans["qualified_update_consumer"]
        + "\nendmodule\n"
    )
    specialization = {
        "kind": "external_monitor_array_unpacked_projection",
        "reason": (
            "Icarus 12.0 rejects runtime indexing of the production packed "
            "multidimensional monitor arrays. Only external monitor array "
            "container declarations are specialized to unpacked arrays; "
            "the exact v24 state declarations, reset task, initialization "
            "statements, qualified update and consumer always block remain "
            "byte-identical spans."
        ),
        "target_state_spans_unchanged": True,
        "spans": {
            name: {
                "bytes": len(value.encode("utf-8")),
                "sha256": sha256_bytes(value.encode("utf-8")),
            }
            for name, value in spans.items()
        },
    }
    return source, {
        "source_sha256": sha256_bytes(source.encode("utf-8")),
        "allowed_specialization": specialization,
        "claim_boundary": (
            "Icarus elaborates the exact v24 state declarations, reset task, "
            "feature initialization, qualified counter updates and real "
            "consumer uses. Only external packed monitor containers are "
            "specialized for Icarus runtime-index compatibility."
        ),
    }


def make_xmr_focus(observer: str) -> tuple[str, dict[str, Any]]:
    exact_block = extract_pc_block(observer)
    leaf_declarations = "\n".join(
        (
            f"    logic {name};"
            if width == 1
            else f"    logic [{width - 1}:0] {name};"
        )
        for name, width in PC_RTL_LEAVES.items()
    )
    hierarchy = (
        macro_prelude()
        + "\nmodule gap_v24_rd_data_channel_leaf_focus;\n"
        + leaf_declarations
        + "\nendmodule\n"
        + r"""
module gap_v24_memrd_focus;
    gap_v24_rd_data_channel_leaf_focus u_RD_Data_Channel();
endmodule
module gap_v24_stream_engine_focus;
    generate
        for (genvar mse_idx = 0; mse_idx < 4; mse_idx++) begin : MSE_INST
            if (mse_idx == 0 || mse_idx == 3) begin : RD_MSE
                gap_v24_memrd_focus u_Memory_RD_Stream_Engine();
            end
        end
    endgenerate
endmodule
module gap_v24_lsu_focus;
    gap_v24_stream_engine_focus u_Stream_Engine();
endmodule
module gap_v24_slice_focus;
    gap_v24_lsu_focus u_LSU();
endmodule
module gap_v24_slice_wrapper_focus;
    gap_v24_slice_focus u_Slice();
endmodule
module gap_v24_group_focus;
    generate
        for (genvar slice_idx = 0; slice_idx < `SLICE_GROUP_NUM; slice_idx++) begin : slice_group_gen
            gap_v24_slice_wrapper_focus u_slice_wrapper();
        end
    endgenerate
endmodule
module gap_v24_ndp_focus;
    generate
        for (genvar group_idx = 0; group_idx < `SLICE_GROUP_SIZE; group_idx++) begin : slice_with_datahub_mc_group_gen
            gap_v24_group_focus u_slice_with_datahub_mc_group();
        end
    endgenerate
endmodule
module gap_v24_prepared_count_xmr_focus;
    gap_v24_ndp_focus u_NDP_Top_new();
"""
    )
    source = hierarchy + exact_block + "\nendmodule\n"
    rhs_paths = re.findall(
        r"(?ms)\bassign\s+return_obs_pc_[^;]*?=\s*(u_NDP_Top_new\.[^;]+);",
        exact_block,
    )
    leaf_names = sorted(
        {path.strip().split(".")[-1] for path in rhs_paths}
    )
    return source, {
        "focused_block_sha256": sha256_bytes(exact_block.encode("utf-8")),
        "exact_assignment_count": len(rhs_paths),
        "resolved_leaf_names": leaf_names,
        "claim_boundary": (
            "The exact v24 prepared-count declaration/generate/assignment "
            "block is elaborated against a focused leaf module and synthetic "
            "wrapper that preserve the production XMR path components and "
            "MSE_INST[0]/[3] generate scopes. Each leaf is independently "
            "bound to an exact declaration in the local RD_Data_Channel RTL, "
            "which is separately parsed by Icarus. Server VCS and its full "
            "NDP hierarchy remain final production elaboration evidence."
        ),
    }


def rtl_leaf_receipts(rtl_path: Path) -> dict[str, Any]:
    text = rtl_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    receipts = {}
    for leaf in PC_RTL_LEAVES:
        matches = []
        token = re.compile(rf"\b{re.escape(leaf)}\b")
        for line_number, line in enumerate(lines, start=1):
            without_comment = line.split("//", 1)[0]
            if token.search(without_comment):
                matches.append(
                    {
                        "line": line_number,
                        "text": without_comment.strip(),
                        "line_sha256": sha256_bytes(
                            (without_comment.strip() + "\n").encode("utf-8")
                        ),
                    }
                )
        declaration_matches = [
            match
            for match in matches
            if re.search(
                rf"\b(?:input|output|wire|reg|logic)\b.*\b{re.escape(leaf)}\b",
                match["text"],
            )
        ]
        receipts[leaf] = {
            "all_occurrence_count": len(matches),
            "declaration_matches": declaration_matches,
            "declaration_found": bool(declaration_matches),
            "update_or_assignment_occurrence_count": sum(
                1
                for match in matches
                if re.search(
                    rf"\b{re.escape(leaf)}\b\s*(?:<=|(?<![=!<>])=(?!=))",
                    match["text"],
                )
            ),
        }
    return {
        "rtl_path": str(rtl_path),
        "rtl_bytes": rtl_path.stat().st_size,
        "rtl_sha256": sha256_path(rtl_path),
        "leaves": receipts,
        "all_leaf_declarations_found": all(
            item["declaration_found"] for item in receipts.values()
        ),
    }


def compile_sv(
    iverilog: Path,
    source: str,
    temporary: Path,
    stem: str,
    extra_sources: list[Path] | None = None,
    include_dirs: list[Path] | None = None,
    top: str | None = None,
) -> dict[str, Any]:
    source_path = temporary / f"{stem}.sv"
    output_path = temporary / f"{stem}.vvp"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    argv = [str(iverilog), "-g2012", "-Wall"]
    for include_dir in include_dirs or []:
        argv.extend(["-I", str(include_dir)])
    selected_top = top or source.split("module ")[-1].split(";")[0].strip()
    argv.extend(["-s", selected_top])
    argv.extend(["-o", str(output_path)])
    argv.extend(str(path) for path in (extra_sources or []))
    argv.append(str(source_path))
    result = run(argv, cwd=temporary)
    result.update(
        {
            "source_sha256": sha256_path(source_path),
            "source_bytes": source_path.stat().st_size,
            "output_exists": output_path.is_file(),
            "output_sha256": (
                sha256_path(output_path) if output_path.is_file() else None
            ),
        }
    )
    return result


def mutate_typo_use(observer: str) -> str:
    start = observer.rfind(
        "    always @(posedge u_NDP_Top_new.clk_sg) begin"
    )
    index = observer.find("return_obs_pc_enabled", start)
    if index < 0:
        raise ValueError("typo mutation use anchor absent")
    return (
        observer[:index]
        + TYPO_IDENTIFIER
        + observer[index + len("return_obs_pc_enabled") :]
    )


def evaluate_projection(
    observer: str,
    iverilog: Path,
    temporary: Path,
    stem: str,
) -> dict[str, Any]:
    closure = identifier_ledger(observer)
    projection, projection_meta = make_scope_projection(observer)
    compile_result = compile_sv(
        iverilog,
        projection,
        temporary,
        stem,
        top="gap_v24_scope_parse_driver",
    )
    valid = (
        closure["summary"]["valid"]
        and projection_meta["remaining_external_xmr"] == 0
        and compile_result["exit_code"] == 0
    )
    return {
        "valid": valid,
        "identifier_closure": closure,
        "projection": projection_meta,
        "compile": compile_result,
    }


def manifest_hdl_contract(
    manifest_payload: bytes,
    observer_sha256: str,
) -> dict[str, Any]:
    manifest = json.loads(manifest_payload)
    contract = manifest.get(
        "package_local_hdl_syntax_scope_contract", {}
    )
    members = contract.get("members", [])
    member = next(
        (
            item
            for item in members
            if item.get("relative_path")
            == "tb_probe/native_return_observer.svh"
        ),
        None,
    )
    features = contract.get("features", [])
    feature = next(
        (
            item
            for item in features
            if item.get("name") == "prepared_count_cause"
        ),
        None,
    )
    state_leaves = feature.get("state_leaves", []) if feature else []
    identifiers = {
        item.get("identifier")
        for item in state_leaves
        if isinstance(item, dict)
    }
    required_state = {
        "return_obs_pc_enabled",
        "return_obs_pc_limit",
        "return_obs_pc_emit_count",
        "return_obs_pc_started",
        "return_obs_pc_prev_rst_n",
        "return_obs_pc_prev_slice_rst",
        "return_obs_pc_prev_wr",
        "return_obs_pc_prev_rd",
        "return_obs_pc_prev_count",
        "return_obs_pc_prev_tsf",
        "return_obs_pc_prev_spatial",
        "return_obs_pc_wr_count",
        "return_obs_pc_rd_count",
        "return_obs_pc_count_change",
        "return_obs_pc_slice_rst_edge",
        "return_obs_pc_rst_n_edge",
        "return_obs_pc_no_effect_count",
        "return_obs_pc_first_no_effect",
        "return_obs_pc_last_no_effect",
        "return_obs_pc_first_local_reset",
        "return_obs_pc_last_local_reset",
        "return_obs_pc_no_effect_seen",
        "return_obs_pc_local_reset_seen",
    }
    checks = {
        "rule_id_current": contract.get("rule_id")
        == "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
        "member_declared": member is not None,
        "member_sha_exact": (
            member is not None
            and member.get("sha256") == observer_sha256
        ),
        "include_order_declared": bool(contract.get("include_order")),
        "compile_macro_profile_declared": bool(
            contract.get("compile_macro_profile")
        ),
        "prepared_count_feature_declared": feature is not None,
        "all_required_state_leaves_declared": required_state <= identifiers,
        "state_leaf_roles_complete": (
            bool(state_leaves)
            and all(
                all(
                    item.get(key)
                    for key in (
                        "identifier",
                        "type",
                        "owner",
                        "initialization_or_reset",
                        "qualified_update",
                        "consumer",
                    )
                )
                for item in state_leaves
            )
        ),
    }
    return {
        "checks": checks,
        "valid": all(checks.values()),
        "declared_state_leaf_count": len(state_leaves),
        "missing_required_state_leaves": sorted(required_state - identifiers),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--rtl-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--install-name", default=INSTALL_NAME)
    parser.add_argument(
        "--expected-zip-bytes", type=int, default=EXPECTED_ZIP_BYTES
    )
    parser.add_argument(
        "--expected-zip-sha256", default=EXPECTED_ZIP_SHA256
    )
    parser.add_argument(
        "--expected-observer-sha256", default=EXPECTED_OBSERVER_SHA256
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    zip_path = args.zip.resolve()
    iverilog = args.iverilog.resolve()
    rtl_root = args.rtl_root.resolve()
    output = args.output.resolve()

    receipt_results = {}
    for relative, expected in RULE_RECEIPTS.items():
        path = workspace / relative
        actual = sha256_path(path)
        receipt_results[relative] = {
            "bytes": path.stat().st_size,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "current_match": actual == expected,
        }
    plan_path = workspace / ".agents/plan.md"
    receipt_results[".agents/plan.md"] = {
        "bytes": plan_path.stat().st_size,
        "actual_sha256": sha256_path(plan_path),
        "mutable_provenance_only": True,
    }

    observer_bytes, manifest_payload, zip_receipt = read_exact_observer(
        zip_path,
        args.install_name,
        args.expected_zip_bytes,
        args.expected_zip_sha256,
        args.expected_observer_sha256,
    )
    observer = observer_bytes.decode("utf-8")
    manifest_contract = manifest_hdl_contract(
        manifest_payload,
        zip_receipt["observer_sha256"],
    )
    version = run([str(iverilog), "-V"])

    include_dir = rtl_root / "includes"
    rd_dir = (
        rtl_root
        / "Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine"
    )
    actual_rtl_sources = [rd_dir / "RD_Data_Channel.sv"]
    rtl_receipts = {
        str(path.relative_to(workspace)): {
            "bytes": path.stat().st_size,
            "sha256": sha256_path(path),
        }
        for path in actual_rtl_sources
    }

    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v24-hdl-scope-"
    ) as temp_name:
        temporary = Path(temp_name)
        positive_projection = evaluate_projection(
            observer, iverilog, temporary, "positive_exact_scope_projection"
        )
        state_source, state_meta = make_state_focus(observer)
        state_compile = compile_sv(
            iverilog,
            state_source,
            temporary,
            "positive_v24_state_focus",
            top="gap_v24_prepared_count_state_focus",
        )
        state_positive = state_compile["exit_code"] == 0
        xmr_source, xmr_meta = make_xmr_focus(observer)
        xmr_compile = compile_sv(
            iverilog,
            xmr_source,
            temporary,
            "positive_v24_xmr_focus",
        )
        rtl_parse_source = (
            "module gap_v24_actual_rtl_parse_driver;\nendmodule\n"
        )
        rtl_parse_compile = compile_sv(
            iverilog,
            rtl_parse_source,
            temporary,
            "positive_actual_rd_data_channel_parse",
            extra_sources=actual_rtl_sources,
            include_dirs=[include_dir],
            top="gap_v24_actual_rtl_parse_driver",
        )
        leaf_receipts = rtl_leaf_receipts(actual_rtl_sources[0])
        xmr_positive = (
            xmr_compile["exit_code"] == 0
            and rtl_parse_compile["exit_code"] == 0
            and leaf_receipts["all_leaf_declarations_found"]
        )

        mutations = {
            "delete_declaration": observer.replace(
                DECLARATION_NEGATIVE, "", 1
            ),
            "misspell_use": mutate_typo_use(observer),
            "delete_critical_update": observer.replace(
                CRITICAL_UPDATE, "/* critical update deleted */", 1
            ),
        }
        negatives = {}
        for name, mutated in mutations.items():
            result = evaluate_projection(
                mutated, iverilog, temporary, f"negative_{name}"
            )
            negatives[name] = {
                "expected_validator_exit": 1,
                "observed_validator_exit": 0 if result["valid"] else 1,
                "failed_closed": not result["valid"],
                "identifier_closure_summary": result["identifier_closure"][
                    "summary"
                ],
                "compile_exit": result["compile"]["exit_code"],
                "compile_stderr": result["compile"]["stderr"],
            }

    all_receipts_match = all(
        item.get("current_match", True) for item in receipt_results.values()
    )
    all_negatives_fail_closed = all(
        item["failed_closed"] for item in negatives.values()
    )
    valid = (
        all_receipts_match
        and positive_projection["valid"]
        and state_positive
        and xmr_positive
        and manifest_contract["valid"]
        and all_negatives_fail_closed
    )
    report = {
        "schema": "gap-node0071-v24-external-observer-hdl-scope-revalidation-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "valid": valid,
        "status": (
            "PACKAGE_HDL_SCOPE_REVALIDATION_PASS"
            if valid
            else "PACKAGE_HDL_SCOPE_REVALIDATION_FAILED"
        ),
        "package_release": (
            "PACKAGE_READY_NOT_RUN" if valid else "NONE"
        ),
        "frozen_zip_unchanged": True,
        "zip_receipt": zip_receipt,
        "current_control_receipts": receipt_results,
        "compatible_frontend": {
            "tool": str(iverilog),
            "version_exit": version["exit_code"],
            "version_stdout": version["stdout"],
            "version_stderr": version["stderr"],
        },
        "exact_observer_internal_scope_positive": positive_projection,
        "v24_exact_state_declaration_reset_update_consumer_positive": {
            "valid": state_positive,
            "metadata": state_meta,
            "compile": state_compile,
        },
        "v24_focused_actual_rtl_xmr_positive": {
            "valid": xmr_positive,
            "metadata": xmr_meta,
            "rtl_member_receipts": rtl_receipts,
            "actual_rtl_leaf_declaration_receipts": leaf_receipts,
            "actual_rtl_parse_only_compile": rtl_parse_compile,
            "compile": xmr_compile,
        },
        "negative_controls": negatives,
        "manifest_hdl_contract": manifest_contract,
        "all_negative_controls_fail_closed": all_negatives_fail_closed,
        "safe_compile_stub_used_as_hdl_evidence": False,
        "token_presence_used_as_hdl_evidence": False,
        "xmr_text_scan_used_as_hdl_evidence": False,
        "functional_rtl_modified": False,
        "package_bytes_modified": False,
        "server_action": False,
        "claim_boundary": (
            "This external receipt proves the exact ZIP observer's internal "
            "SystemVerilog declaration/use/update scope through a complete "
            "scope projection, and proves the exact new v24 prepared-count "
            "XMR block against the local RD_Data_Channel RTL with Icarus "
            "12.0 elaboration. It does not prove the server's complete NDP "
            "hierarchy, VCS-specific semantics, runtime observer enablement, "
            "numeric correctness, E3, E4 or E5."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "valid": valid,
                "status": report["status"],
                "package_release": report["package_release"],
                "zip_sha256": zip_receipt["zip_sha256"],
                "observer_sha256": zip_receipt["observer_sha256"],
                "identifier_closure": positive_projection[
                    "identifier_closure"
                ]["summary"],
                "projection_compile_exit": positive_projection["compile"][
                    "exit_code"
                ],
                "state_compile_exit": state_compile["exit_code"],
                "xmr_compile_exit": xmr_compile["exit_code"],
                "manifest_hdl_contract": manifest_contract,
                "negative_controls": {
                    name: item["observed_validator_exit"]
                    for name, item in negatives.items()
                },
            },
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
