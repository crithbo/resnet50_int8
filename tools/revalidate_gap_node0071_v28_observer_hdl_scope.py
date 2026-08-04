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


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_n71_gap_v28_ga_mse4_final_pair_diag"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
OBSERVER_MEMBER = f"{INSTALL_NAME}/{OBSERVER_RELATIVE}"
EXPECTED_ZIP_BYTES = 1_815_690
EXPECTED_ZIP_SHA256 = (
    "7b34ef0b592ebfd86d3e75a0983a91c8d87271454139e609174cdce8afc7d422"
)
EXPECTED_OBSERVER_SHA256 = (
    "817fb9b91a2df69105a75cfc75edaf56adaacaca7f5cf084eaa76789cddf4943"
)
PAIR_ANCHOR = "    // v28: bounded GA-final-pipeline to MSE4 write-pair diagnostic."
PAIR_END = "\n    bit return_obs_pair_enabled;"
CRITICAL_UPDATE = "return_obs_pair_ga_accept_count++;"
RULE_ID = (
    "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


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
        "stdout_sha256": sha256_bytes(process.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(process.stderr.encode("utf-8")),
    }


def read_exact(zip_path: Path) -> tuple[str, dict[str, Any]]:
    if zip_path.stat().st_size != EXPECTED_ZIP_BYTES:
        raise ValueError("final ZIP byte size differs")
    if sha256_path(zip_path) != EXPECTED_ZIP_SHA256:
        raise ValueError("final ZIP SHA256 differs")
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failed at {bad}")
        infos = archive.infolist()
        names = [item.filename for item in infos if not item.is_dir()]
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        for item in infos:
            path = PurePosixPath(item.filename)
            mode = (item.external_attr >> 16) & 0xFFFF
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in item.filename
                or (mode & 0o170000) == 0o120000
            ):
                raise ValueError(f"unsafe ZIP member: {item.filename}")
        payload = archive.read(OBSERVER_MEMBER)
    digest = sha256_bytes(payload)
    if digest != EXPECTED_OBSERVER_SHA256:
        raise ValueError("exact observer SHA256 differs")
    return payload.decode("utf-8"), {
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": EXPECTED_ZIP_SHA256,
        "crc_pass": True,
        "path_safe": True,
        "duplicate_free": True,
        "symlink_free": True,
        "observer_member": OBSERVER_MEMBER,
        "observer_bytes": len(payload),
        "observer_sha256": digest,
    }


def macro_prelude() -> str:
    macros = {
        "SLICE_GROUP_SIZE": 1,
        "SLICE_GROUP_NUM": 1,
        "GA_ROW_PE_NUM": 4,
        "GA_PE_ALU_TAG_WIDTH": 8,
        "GA_PE_OUTBUFFER_CNT_WIDTH": 3,
        "MSE_REQ_CHL_NUM": 2,
    }
    return "".join(f"`define {key} {value}\n" for key, value in macros.items())


def pair_block(observer: str) -> str:
    start = observer.find(PAIR_ANCHOR)
    end = observer.find(PAIR_END, start)
    if start < 0 or end < 0:
        raise ValueError("v28 pair declaration/XMR block anchors absent")
    return observer[start:end]


def focused_xmr_source(observer: str) -> tuple[str, dict[str, Any]]:
    exact = pair_block(observer)
    source = (
        macro_prelude()
        + r'''
module v28_ga_outbuffer_leaf;
    logic ga_pe_outbuffer_full;
    logic normal_mode_wr_req;
    logic normal_mode_wr_handshake;
    logic normal_mode_rd_handshake;
endmodule
module v28_ga_pe_scope;
    v28_ga_outbuffer_leaf u_GA_PE_Outbuffer();
endmodule
module v28_ga_group;
    generate
        for (genvar row = 0; row < `GA_ROW_PE_NUM; row++) begin : GA_ROW_PE
            for (genvar col = 0; col < 3; col++) begin : GA_COL_PE
                if (col == 0 || col == 2) begin : GA_PE
                    v28_ga_pe_scope u_GA_PE();
                end
            end
        end
    endgenerate
endmodule
module v28_ga;
    v28_ga_group u_GA_PE_Group();
endmodule
module v28_wr_data_channel;
    logic wr_data_chl_req_valid, wr_data_chl_req_ready;
    logic wr_chl_queue_wr_en, wr_chl_queue_rd_en;
    logic wr_chl_queue_full, wr_chl_queue_empty;
    logic buf2mse_rvalid, wr_data_chl_ready, buf_ag_last_req_flag;
    logic wr_data_chl_hold_data_vld;
    logic wr_data_chl_prepared_data_wr_hs;
    logic wr_data_chl_prepared_data_rd_hs;
    logic wr_data_chl_prepared_data_vld;
    logic [5:0] wr_data_chl_prepared_data_cnt;
    logic [`MSE_REQ_CHL_NUM-1:0] wr_chl_ob_vld_in;
    logic [`MSE_REQ_CHL_NUM-1:0] wr_chl_ob_wr_hs;
    logic [`MSE_REQ_CHL_NUM-1:0] wr_chl_ob_rd_hs;
    logic [`MSE_REQ_CHL_NUM-1:0] wr_chl_ob_vld;
    logic [`MSE_REQ_CHL_NUM-1:0] wr_chl_ob_vld_o;
    logic [`MSE_REQ_CHL_NUM-1:0] mem2mse_wdata_ready;
    logic [`MSE_REQ_CHL_NUM-1:0] wr_data_chl_ob_last_data_flag;
    logic wr_data_chl_ob_last_data_arv_arr_flag;
endmodule
module v28_wr_stream;
    v28_wr_data_channel u_WR_Data_Channel();
endmodule
module v28_stream_engine;
    generate
        for (genvar mse = 0; mse < 5; mse++) begin : MSE_INST
            if (mse == 4) begin : WR_MSE
                v28_wr_stream u_Memory_WR_Stream_Engine();
            end
        end
    endgenerate
endmodule
module v28_lsu;
    v28_stream_engine u_Stream_Engine();
endmodule
module v28_slice;
    v28_ga u_General_Array();
    v28_lsu u_LSU();
endmodule
module v28_wrapper;
    v28_slice u_Slice();
endmodule
module v28_group;
    generate
        for (genvar slice = 0; slice < `SLICE_GROUP_NUM; slice++) begin : slice_group_gen
            v28_wrapper u_slice_wrapper();
        end
    endgenerate
endmodule
module v28_ndp;
    generate
        for (genvar group = 0; group < `SLICE_GROUP_SIZE; group++) begin : slice_with_datahub_mc_group_gen
            v28_group u_slice_with_datahub_mc_group();
        end
    endgenerate
endmodule
module v28_pair_xmr_focus;
    v28_ndp u_NDP_Top_new();
'''
        + exact
        + "\nendmodule\n"
    )
    rhs = re.findall(
        r"(?ms)\bassign\s+return_obs_pair_[^;]*?=\s*"
        r"(u_NDP_Top_new\.[^;]+);",
        exact,
    )
    return source, {
        "exact_block_bytes": len(exact.encode("utf-8")),
        "exact_block_sha256": sha256_bytes(exact.encode("utf-8")),
        "exact_xmr_assignment_count": len(rhs),
        "resolved_leaf_names": sorted(
            {item.strip().split(".")[-1] for item in rhs}
        ),
        "claim_boundary": (
            "Exact v28 declaration/generate/continuous-assignment bytes are "
            "elaborated against a focused hierarchy preserving all new GA "
            "and MSE4 path components and leaf names. Production VCS remains "
            "the full-design elaboration authority."
        ),
    }


def projection_source(observer: str) -> tuple[str, dict[str, Any]]:
    assignment = re.compile(
        r"(?ms)(^\s*assign\s+return_obs_[^;]*?=).*?;"
    )
    projected, count = assignment.subn(
        lambda match: match.group(1) + " '0;", observer
    )
    substitutions = {
        "u_NDP_Top_new.clk_db": "scope_clk_db",
        "u_NDP_Top_new.rst_n_db": "scope_rst_n_db",
        "u_NDP_Top_new.clk_sg": "scope_clk_sg",
        "u_NDP_Top_new.rst_n_sg": "scope_rst_n_sg",
    }
    for source, target in substitutions.items():
        projected = projected.replace(source, target)
    source = (
        "`define SLICE_GROUP_SIZE 1\n"
        "`define SLICE_GROUP_NUM 1\n"
        "`define GA_ROW_PE_NUM 4\n"
        "`define GA_PE_INPORT_NUM 4\n"
        "`define GA_PE_ALU_DATA_WIDTH 32\n"
        "`define GA_PE_ALU_TAG_WIDTH 8\n"
        "`define GA_PE_OUTBUFFER_PTR_WIDTH 2\n"
        "`define GA_PE_OUTBUFFER_CNT_WIDTH 3\n"
        "`define GA_PE_OUTBUFFER_DEPTH 4\n"
        "`define GA_PE_OUTBUFFER_TAG_WIDTH 8\n"
        "`define GA_PE_OUTBUFFER_DATA_WIDTH 32\n"
        "`define GA_PE_PORT_TAG_WIDTH 8\n"
        "`define GA_INPORT_NUM 4\n"
        "`define GA_INPORT_TAG 8\n"
        "`define SA_INPORT_GROUP_NUM 2\n"
        "`define SA_INPORT_SRC_NUM 4\n"
        "`define SA_INPORT_GROUP_TAG 8\n"
        "`define SA_OUTPORT_GROUP_TAG 8\n"
        "`define SA_OUTPORT_GROUP_NUM 2\n"
        "`define SA_PORT_HANDLE_BUF_NUM 2\n"
        "`define ARRAY_PORT_TAG 8\n"
        "`define BUFFER_BANK_NUM 4\n"
        "`define VALID_BUFFER_DEPTH 4\n"
        "`define VALID_BUFFER_BANK_WIDTH 8\n"
        "`define BUFFER_BANK_ADDR_WIDTH 8\n"
        "`define BUFFER_LIFE_TIME_WIDTH 8\n"
        "`define MSE_REQ_CHL_NUM 2\n"
        "`define MSE_MEM_REQ_ADDR_WIDTH 32\n"
        "`define MSE_MEM_AG_INPORT_NUM 3\n"
        "`define MSE_MEM_AG_INPORT_IDX_WIDTH 8\n"
        "`define MSE_TSA_IDX_WIDTH 8\n"
        "`define MSE_TSA_ADDR_WIDTH 16\n"
        "`define MSE_TSF_ADDR_WIDTH 16\n"
        "`define MSE_TSF_SIZE_WIDTH 8\n"
        "`define MSE_VALID_MASK_WIDTH 16\n"
        "`define MSE_PADDING_MASK_WIDTH 16\n"
        "`define MSE_BUF_REQ_NUM 16\n"
        "`define MSE_BUF_REQ_DATA_WIDTH 32\n"
        "`define DDR_ADDR_OFFSET_WIDTH 32\n"
        "`define DDR_COL_DATA_WIDTH 128\n"
        "`define IGA_LC_PORT_WIDTH 32\n"
        "`define IGA_PE_PORT_WIDTH 32\n"
        "`define MEMORY_STREAM_ENGINE_NUM 6\n"
        "`define BANK_NUM_PER_SLICE 8\n"
        "module v28_exact_observer_projection;\n"
        "logic scope_clk_db, scope_rst_n_db, scope_clk_sg, scope_rst_n_sg;\n"
        + projected
        + "\nendmodule\nmodule v28_projection_driver; endmodule\n"
    )
    return source, {
        "continuous_assignment_rhs_neutralized": count,
        "remaining_external_xmr": source.count("u_NDP_Top_new."),
        "projection_sha256": sha256_bytes(source.encode("utf-8")),
        "claim_boundary": (
            "Icarus parses the exact final observer declarations/tasks/"
            "procedural syntax with only external DUT continuous-assignment "
            "RHS and four TB clock/reset leaves neutralized. The separate "
            "focused XMR compile resolves every new v28 hierarchy leaf."
        ),
    }


def scoped_ledger(observer: str) -> dict[str, Any]:
    code = re.sub(
        r"//[^\n]*|/\*.*?\*/|\"(?:\\.|[^\"\\])*\"",
        lambda match: " " * len(match.group(0)),
        observer,
        flags=re.DOTALL,
    )
    identifiers = sorted(set(re.findall(r"\breturn_obs_pair_[A-Za-z0-9_]+\b", code)))
    declarations = set()
    for match in re.finditer(
        r"\b(?:logic|bit|int|longint(?:\s+unsigned)?)\b[^;]*;",
        code,
        re.DOTALL,
    ):
        declarations.update(
            re.findall(r"\breturn_obs_pair_[A-Za-z0-9_]+\b", match.group())
        )
    declarations.update(
        re.findall(
            r"\btask\s+automatic\s+(return_obs_pair_[A-Za-z0-9_]+)\b",
            code,
        )
    )
    declarations.update(
        re.findall(
            r"\bgenvar\s+(return_obs_pair_[A-Za-z0-9_]+)\b",
            code,
        )
    )
    token_count = {
        identifier: len(re.findall(rf"\b{re.escape(identifier)}\b", code))
        for identifier in identifiers
    }
    undeclared = sorted(set(identifiers) - declarations)
    unused = sorted(
        identifier
        for identifier in declarations
        if token_count.get(identifier, 0) < 2
    )
    critical_count = code.count(CRITICAL_UPDATE)
    required = {
        "return_obs_pair_enabled",
        "return_obs_pair_limit",
        "return_obs_pair_reset",
        "return_obs_pair_ga_accept_count",
        "return_obs_pair_ga_p0_retire_count",
        "return_obs_pair_m4_req_accept_count",
        "return_obs_pair_m4_buf_accept_count",
        "return_obs_pair_m4_ob_wr_count",
        "return_obs_pair_m4_ob_rd_count",
    }
    missing_required = sorted(required - set(identifiers))
    return {
        "scope_prefix": "return_obs_pair_",
        "identifier_count": len(identifiers),
        "declared_count": len(declarations),
        "undeclared_uses": undeclared,
        "declared_without_use": unused,
        "critical_update": CRITICAL_UPDATE,
        "critical_update_count": critical_count,
        "missing_required_identifiers": missing_required,
        "valid": (
            not undeclared
            and not unused
            and not missing_required
            and critical_count == 1
        ),
        "claim_boundary": (
            "Machine closure is intentionally restricted to identifiers "
            "added by v28 and used by required GA_MSE4_FINAL_PAIR records; "
            "unrelated historical observer state is outside this audit."
        ),
    }


def compile_sv(
    iverilog: Path,
    source: str,
    temporary: Path,
    stem: str,
    top: str,
) -> dict[str, Any]:
    source_path = temporary / f"{stem}.sv"
    output_path = temporary / f"{stem}.vvp"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    result = run(
        [
            str(iverilog),
            "-g2012",
            "-Wall",
            "-s",
            top,
            "-o",
            str(output_path),
            str(source_path),
        ],
        cwd=temporary,
    )
    result.update(
        {
            "source_bytes": source_path.stat().st_size,
            "source_sha256": sha256_path(source_path),
            "output_exists": output_path.is_file(),
            "output_sha256": (
                sha256_path(output_path) if output_path.is_file() else None
            ),
        }
    )
    return result


def evaluate(
    observer: str,
    iverilog: Path,
    temporary: Path,
    stem: str,
) -> dict[str, Any]:
    ledger = scoped_ledger(observer)
    projection, projection_meta = projection_source(observer)
    projection_compile = compile_sv(
        iverilog, projection, temporary, f"{stem}_projection",
        "v28_projection_driver",
    )
    try:
        xmr_source, xmr_meta = focused_xmr_source(observer)
        xmr_compile = compile_sv(
            iverilog, xmr_source, temporary, f"{stem}_xmr",
            "v28_pair_xmr_focus",
        )
    except Exception as error:
        xmr_meta = {"error": str(error)}
        xmr_compile = {
            "exit_code": 1,
            "stderr": str(error),
            "stdout": "",
        }
    valid = (
        ledger["valid"]
        and projection_meta["remaining_external_xmr"] == 0
        and projection_compile["exit_code"] == 0
        and xmr_compile["exit_code"] == 0
    )
    return {
        "valid": valid,
        "scoped_identifier_closure": ledger,
        "exact_observer_projection": projection_meta,
        "projection_compile": projection_compile,
        "focused_xmr": xmr_meta,
        "focused_xmr_compile": xmr_compile,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--iverilog", type=Path,
        default=Path(r"C:\iverilog\bin\iverilog.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        observer, receipt = read_exact(args.target_zip.resolve())
        version = run([str(args.iverilog.resolve()), "-V"])
        with tempfile.TemporaryDirectory(prefix="gap-v28-hdl-") as temp:
            temporary = Path(temp)
            positive = evaluate(
                observer, args.iverilog.resolve(), temporary, "positive"
            )
            mutations = {
                "delete_required_declaration": observer.replace(
                    "    bit return_obs_pair_enabled;\n", "", 1
                ),
                "typo_required_use": observer.replace(
                    "            return_obs_pair_enabled &&\n",
                    "            return_obs_pair_enabled_typo &&\n",
                    1,
                ),
                "delete_required_update": observer.replace(
                    f"                        {CRITICAL_UPDATE}\n", "", 1
                ),
            }
            negatives = {}
            for name, mutated in mutations.items():
                check = evaluate(
                    mutated, args.iverilog.resolve(), temporary,
                    f"negative_{name}",
                )
                negatives[name] = {
                    "failed_closed": not check["valid"],
                    "scoped_identifier_closure":
                        check["scoped_identifier_closure"],
                    "projection_compile_exit":
                        check["projection_compile"]["exit_code"],
                    "focused_xmr_compile_exit":
                        check["focused_xmr_compile"]["exit_code"],
                }
        all_negatives = all(
            item["failed_closed"] for item in negatives.values()
        )
        current_rules = {
            ".agents/rules/生成前必读索引.md":
                sha256_path(ROOT / ".agents/rules/生成前必读索引.md"),
            ".agents/rules/服务器测试包生成规则.md":
                sha256_path(ROOT / ".agents/rules/服务器测试包生成规则.md"),
            ".agents/rules/GAP_int32_mac_bypass_rules.md":
                sha256_path(ROOT / ".agents/rules/GAP_int32_mac_bypass_rules.md"),
            ".agents/rules/GAP_probe_v7_validator_rules.md":
                sha256_path(ROOT / ".agents/rules/GAP_probe_v7_validator_rules.md"),
            ".agents/rules/精确UINT8量化尾专项规则.md":
                sha256_path(ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"),
        }
        valid = (
            version["exit_code"] == 0
            and positive["valid"]
            and all_negatives
        )
        result = {
            "schema": "gap-node0071-v28-focused-observer-hdl-revalidation-v1",
            "status": "PASS" if valid else "FAIL",
            "pass": valid,
            "rule_id": RULE_ID,
            "target_receipt": receipt,
            "tool": {
                "path": str(args.iverilog.resolve()),
                "version_exit": version["exit_code"],
                "version_stdout": version["stdout"],
                "version_stderr": version["stderr"],
            },
            "current_rule_receipts": current_rules,
            "scope": (
                "v28-added and required-result GA_MSE4_FINAL_PAIR local "
                "identifiers/state plus exact new GA/MSE4 XMR assignments"
            ),
            "positive": positive,
            "negative_controls": negatives,
            "all_negative_controls_fail_closed": all_negatives,
            "package_bytes_changed": False,
            "full_design_elaboration_claimed": False,
            "server_vcs_remains_final_authority": True,
            "errors": [] if valid else ["focused HDL positive/control gate failed"],
        }
    except Exception as error:
        result = {
            "schema": "gap-node0071-v28-focused-observer-hdl-revalidation-v1",
            "status": "FAIL",
            "pass": False,
            "rule_id": RULE_ID,
            "errors": [str(error)],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
