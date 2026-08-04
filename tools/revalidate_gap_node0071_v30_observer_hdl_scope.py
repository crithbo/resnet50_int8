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


INSTALL_NAME = "r5_n71_gap_v30_arm_ready_factor_diag"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
EXPECTED_ZIP_SHA256 = "f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931"
EXPECTED_ZIP_BYTES = 1_819_468
ANCHOR = "    // v30: Buffer0 ARM read-ready conjunction factor diagnostic."
LOCAL_ANCHOR = "    bit return_obs_armf_enabled;"
DECL_END = "\n    bit return_obs_enabled;"
SAMPLER_ANCHOR = "    // v30 factor sampler: only qualified accepts and factor edges advance."
SAMPLER_END = "\n    final begin"
PREFIX = "return_obs_armf_"
CRITICAL_UPDATE = "return_obs_armf_block_entry_count++;"
XMR_LEAVES = [
    ".u_Buffer.buffer_mask;",
    ".u_Buffer.buf2arm_rreq_bank_ready;",
    ".u_Buffer.arm_clear_reg;",
    ".u_Buffer.nrm2buf_rd_barrier;",
]
REQUIRED = {
    "return_obs_armf_enabled",
    "return_obs_armf_limit",
    "return_obs_armf_emit_count",
    "return_obs_armf_started",
    "return_obs_armf_prev_bank_ready",
    "return_obs_armf_prev_barrier",
    "return_obs_armf_prev_ready",
    "return_obs_armf_prev_blocked",
    "return_obs_armf_accept_count",
    "return_obs_armf_bank_edge_count",
    "return_obs_armf_barrier_edge_count",
    "return_obs_armf_ready_edge_count",
    "return_obs_armf_block_entry_count",
    "return_obs_armf_reset",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(argv: list[str], cwd: Path | None = None) -> dict[str, Any]:
    process = subprocess.run(
        argv, cwd=cwd, text=True, capture_output=True, check=False
    )
    return {
        "argv": argv,
        "cwd": str(cwd) if cwd else None,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "stdout_sha256": sha256_bytes(process.stdout.encode()),
        "stderr_sha256": sha256_bytes(process.stderr.encode()),
    }


def section(text: str, start_token: str, end_token: str) -> str:
    start = text.find(start_token)
    end = text.find(end_token, start)
    if start < 0 or end < 0 or end <= start:
        raise ValueError(f"focused section absent: {start_token}")
    return text[start:end]


def read_exact(path: Path) -> tuple[str, dict[str, Any]]:
    if path.stat().st_size != EXPECTED_ZIP_BYTES:
        raise ValueError("final ZIP byte size differs")
    if sha256_path(path) != EXPECTED_ZIP_SHA256:
        raise ValueError("final ZIP SHA256 differs")
    member = f"{INSTALL_NAME}/{OBSERVER_RELATIVE}"
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC differs")
        payload = archive.read(member)
    return payload.decode("utf-8"), {
        "zip": str(path),
        "zip_size_bytes": path.stat().st_size,
        "zip_sha256": sha256_path(path),
        "observer_member": member,
        "observer_size_bytes": len(payload),
        "observer_sha256": sha256_bytes(payload),
    }


def ledger(observer: str) -> dict[str, Any]:
    xmr_decl = section(observer, ANCHOR, LOCAL_ANCHOR)
    local = section(observer, LOCAL_ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    code = local + sampler
    identifiers = set(re.findall(r"\breturn_obs_armf_[A-Za-z0-9_]+\b", code))
    declared = set(
        re.findall(
            r"\b(?:bit|int|longint unsigned|logic\s+"
            r"\[`BUFFER_BANK_NUM-1:0\])\s+"
            r"(return_obs_armf_[A-Za-z0-9_]+)",
            local,
        )
    )
    declared.update(
        re.findall(
            r"\btask\s+automatic\s+(return_obs_armf_[A-Za-z0-9_]+)",
            local,
        )
    )
    for name in (
        "return_obs_armf_mask_mon",
        "return_obs_armf_bank_ready_mon",
        "return_obs_armf_clear_reg_mon",
        "return_obs_armf_nrm_barrier_mon",
    ):
        if name in xmr_decl:
            declared.add(name)
    undeclared = sorted(identifiers - declared)
    missing = sorted(REQUIRED - identifiers)
    updates = {
        token: token in sampler
        for token in (
            "return_obs_armf_accept_count++;",
            "return_obs_armf_bank_edge_count++;",
            "return_obs_armf_barrier_edge_count++;",
            "return_obs_armf_ready_edge_count++;",
            CRITICAL_UPDATE,
        )
    }
    xmr = {leaf: observer.count(leaf) == 1 for leaf in XMR_LEAVES}
    records = {
        name: name in observer
        for name in (
            "BUFFER0_ARM_READY_FACTOR_EVENT_V1",
            "BUFFER0_ARM_READY_FACTOR_COUNTS_V1",
            "BUFFER0_ARM_READY_FACTOR_STATE_V1",
            "BUFFER0_ARM_READY_FACTOR_WITNESS_V1",
        )
    }
    group_fix = {
        "stable_nonzero_expression_absent":
            "(|return_obs_ga_group_out_tag_mon[return_obs_group_id]"
            "[return_obs_local_slice_id][0][0])" not in observer,
        "valid_bit_used":
            "[m0_group_row][`GA_INPORT_TAG-1]" in observer,
        "qualified_bp_used": "m0_group0_accept &=" in observer,
    }
    valid = (
        not undeclared
        and not missing
        and all(updates.values())
        and all(xmr.values())
        and all(records.values())
        and all(group_fix.values())
    )
    return {
        "identifiers": sorted(identifiers),
        "declared": sorted(declared),
        "undeclared_identifiers": undeclared,
        "missing_required_identifiers": missing,
        "qualified_updates": updates,
        "xmr_leaf_exact_set": xmr,
        "required_records": records,
        "v29_group0_correction": group_fix,
        "valid": valid,
    }


def local_projection(observer: str) -> str:
    local = section(observer, LOCAL_ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    update_lines = []
    for line in sampler.splitlines():
        stripped = line.strip()
        if stripped.startswith(PREFIX) and (
            stripped.endswith("++;")
            or " = return_obs_sg_clock_edge_count;" in stripped
        ):
            update_lines.append("        " + stripped)
    return (
        "`define BUFFER_BANK_NUM 8\n"
        "module v30_armf_local_projection;\n"
        + local
        + "\n    longint unsigned return_obs_sg_clock_edge_count;\n"
        "    initial begin\n"
        "        return_obs_sg_clock_edge_count = 1;\n"
        "        return_obs_armf_reset();\n"
        + "\n".join(update_lines)
        + "\n        if (return_obs_armf_block_entry_count != 1) $fatal;\n"
        "    end\n"
        "endmodule\n"
    )


def xmr_projection(observer: str) -> str:
    block = section(observer, ANCHOR, LOCAL_ANCHOR)
    return (
        "`define SLICE_GROUP_SIZE 1\n"
        "`define SLICE_GROUP_NUM 1\n"
        "`define BUFFER_BANK_NUM 8\n"
        "`define VALID_BUFFER_BANK_WIDTH 4\n"
        "module v30_buffer;\n"
        "  logic [7:0] buffer_mask, buf2arm_rreq_bank_ready;\n"
        "  logic [3:0] arm_clear_reg;\n"
        "  logic nrm2buf_rd_barrier;\n"
        "endmodule\n"
        "module v30_buffer_manager; v30_buffer u_Buffer(); endmodule\n"
        "module v30_bmc; generate for(genvar i=0;i<1;i++) begin: BUFFER_MANAGER v30_buffer_manager u_Buffer_Manager(); end endgenerate endmodule\n"
        "module v30_lsu; v30_bmc u_Buffer_Manager_Cluster(); endmodule\n"
        "module v30_slice; v30_lsu u_LSU(); endmodule\n"
        "module v30_wrapper; v30_slice u_Slice(); endmodule\n"
        "module v30_group; generate for(genvar i=0;i<1;i++) begin: slice_group_gen v30_wrapper u_slice_wrapper(); end endgenerate endmodule\n"
        "module v30_ndp; generate for(genvar i=0;i<1;i++) begin: slice_with_datahub_mc_group_gen v30_group u_slice_with_datahub_mc_group(); end endgenerate endmodule\n"
        "module v30_armf_xmr_focus;\n"
        "  v30_ndp u_NDP_Top_new();\n"
        + block
        + "\nendmodule\n"
    )


def compile_source(
    source: str, top: str, path: Path, iverilog: Path
) -> dict[str, Any]:
    path.write_text(source, encoding="utf-8", newline="\n")
    return run(
        [str(iverilog), "-g2012", "-tnull", "-s", top, str(path)],
        path.parent,
    )


def evaluate(
    observer: str, iverilog: Path, temporary: Path, stem: str
) -> dict[str, Any]:
    try:
        closure = ledger(observer)
    except Exception as error:
        return {
            "valid": False,
            "scoped_identifier_closure": {
                "valid": False,
                "error": str(error),
            },
            "local_projection_compile": {
                "exit_code": 1,
                "stderr": str(error),
                "stdout": "",
            },
            "focused_xmr_compile": {
                "exit_code": 1,
                "stderr": str(error),
                "stdout": "",
            },
        }
    try:
        local = local_projection(observer)
        local_compile = compile_source(
            local, "v30_armf_local_projection",
            temporary / f"{stem}_local.sv", iverilog,
        )
    except Exception as error:
        local_compile = {"exit_code": 1, "stderr": str(error), "stdout": ""}
    try:
        xmr = xmr_projection(observer)
        xmr_compile = compile_source(
            xmr, "v30_armf_xmr_focus",
            temporary / f"{stem}_xmr.sv", iverilog,
        )
    except Exception as error:
        xmr_compile = {"exit_code": 1, "stderr": str(error), "stdout": ""}
    return {
        "valid": (
            closure["valid"]
            and local_compile["exit_code"] == 0
            and xmr_compile["exit_code"] == 0
        ),
        "scoped_identifier_closure": closure,
        "local_projection_compile": local_compile,
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
        with tempfile.TemporaryDirectory(prefix="gap-v30-hdl-") as temp:
            temporary = Path(temp)
            positive = evaluate(
                observer, args.iverilog.resolve(), temporary, "positive"
            )
            mutations = {
                "delete_required_declaration": observer.replace(
                    "    bit return_obs_armf_enabled;\n", "", 1
                ),
                "typo_required_use": observer.replace(
                    "            return_obs_armf_enabled &&\n",
                    "            return_obs_armf_enabled_typo &&\n",
                    1,
                ),
                "delete_required_update": observer.replace(
                    "                return_obs_armf_block_entry_count++;\n",
                    "",
                    1,
                ),
                "delete_barrier_xmr": observer.replace(
                    ".u_Buffer.nrm2buf_rd_barrier;",
                    ".u_Buffer.nrm_barrier_removed;",
                    1,
                ),
                "delete_group0_valid_bit": observer.replace(
                    "[m0_group_row][`GA_INPORT_TAG-1]",
                    "[m0_group_row]",
                    1,
                ),
            }
            negatives = {
                name: evaluate(
                    mutated, args.iverilog.resolve(), temporary,
                    f"negative_{name}",
                )
                for name, mutated in mutations.items()
            }
        all_negatives = all(not item["valid"] for item in negatives.values())
        passed = positive["valid"] and all_negatives
        result = {
            "schema": "gap-node0071-v30-focused-observer-hdl-scope-v1",
            "status": "PASS" if passed else "FAIL",
            "pass": passed,
            "rule_id": (
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-"
                "POSITIVE-001"
            ),
            "target_receipt": receipt,
            "tool": {"name": "iverilog", "version_command": version},
            "positive": positive,
            "negative_controls": {
                name: {
                    "failed_closed": not item["valid"],
                    "closure_valid":
                        item["scoped_identifier_closure"]["valid"],
                    "local_compile_exit":
                        item["local_projection_compile"]["exit_code"],
                    "xmr_compile_exit":
                        item["focused_xmr_compile"]["exit_code"],
                }
                for name, item in negatives.items()
            },
            "all_negative_controls_fail_closed": all_negatives,
            "scope": (
                "exact final v30 local declarations/reset/update/use, four "
                "focused Buffer0 XMR leaves, and corrected v29 group0 "
                "valid-bit expression; no full-design elaboration"
            ),
            "full_design_elaboration_claimed": False,
            "server_source_files_inspected": False,
            "package_bytes_changed": False,
        }
    except Exception as error:
        result = {
            "schema": "gap-node0071-v30-focused-observer-hdl-scope-v1",
            "status": "FAIL",
            "pass": False,
            "error": str(error),
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
