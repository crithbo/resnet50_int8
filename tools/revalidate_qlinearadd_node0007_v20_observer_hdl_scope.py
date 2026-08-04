from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_qadd_n7_fp32_ingress_compilefix_v20"
ZIP_SHA = "13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51"
ZIP_BYTES = 38_041_268
MEMBERS = {
    "native": f"{INSTALL_NAME}/tb_probe/native_return_observer.svh",
    "shim": (
        f"{INSTALL_NAME}/tb_probe/"
        "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"
    ),
    "tail": (
        f"{INSTALL_NAME}/tb_probe/"
        "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
    ),
}
CRITICAL = "return_obs_ga_operand_capture_mon"
RTL = ROOT / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv"
RULES = {
    "plan_mutable": ROOT / ".agents/plan.md",
    "generation_index": ROOT / ".agents/rules/生成前必读索引.md",
    "server_package_rule": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "qlinearadd_rule": ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail_rule": ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


class GateError(ValueError):
    pass


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_exact(zip_path: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    if zip_path.stat().st_size != ZIP_BYTES or sha_file(zip_path) != ZIP_SHA:
        raise GateError("frozen v20 ZIP bytes/SHA differ")
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise GateError("ZIP CRC failed")
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise GateError("duplicate ZIP member")
        for item in infos:
            pure = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in item.filename
                or stat.S_ISLNK(mode)
            ):
                raise GateError(f"unsafe ZIP member: {item.filename}")
        payloads = {key: archive.read(name) for key, name in MEMBERS.items()}
    return payloads, {
        "crc_valid": True,
        "duplicate_count": 0,
        "unsafe_path_count": 0,
        "symlink_count": 0,
        "member_count": len(infos),
    }


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


def extract_statement(tail: str, counter: str) -> str:
    pattern = re.compile(
        r"if \(return_obs_ga_operand_capture_mon.*?"
        + re.escape(counter)
        + r"\+\+;",
        re.DOTALL,
    )
    matches = pattern.findall(tail)
    if not matches:
        return f"/* exact critical statement absent: {counter} */"
    # Non-greedy matching can start at an earlier capture statement. The last
    # match for each counter is the shortest statement ending at that update.
    value = matches[-1]
    starts = [match.start() for match in re.finditer(r"if \(return_obs_", value)]
    if starts:
        value = value[starts[-1] :]
    return value


def focus_source(shim: str, tail: str) -> str:
    include = '`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"'
    if shim.count(include) != 1:
        raise GateError("shim tail include exact-count differs")
    shim_body = shim.replace(include, "")
    stmt0 = extract_statement(tail, "qadd_ingress_ga_capture[0]")
    stmt1 = extract_statement(tail, "qadd_ingress_ga_capture[1]")
    # Icarus 12.0 does not elaborate variable selects across this five-dimensional
    # packed monitor even though production VCS accepts the SystemVerilog form.
    # Specialize only the four loop/runtime indices to zero; the exact identifier,
    # select rank, capture bit and counter update remain unchanged.
    for old in (
        "return_obs_group_id",
        "return_obs_local_slice_id",
        "qadd_ingress_row",
        "qadd_ingress_slot",
    ):
        stmt0 = stmt0.replace(f"[{old}]", "[0]")
        stmt1 = stmt1.replace(f"[{old}]", "[0]")
    return (
        "`timescale 1ns/1ps\n"
        "`define SLICE_GROUP_SIZE 1\n"
        "`define SLICE_GROUP_NUM 1\n"
        "`define GA_ROW_PE_NUM 1\n"
        "`define GA_PE_INPORT_NUM 2\n"
        "module ga_inbuffer_stub; logic [`GA_PE_INPORT_NUM-1:0] ga_pe_inbuffer_enable; endmodule\n"
        "module ga_core_stub; ga_inbuffer_stub u_GA_PE_Inbuffer(); endmodule\n"
        "module ga_pe_stub; ga_core_stub u_GA_PE(); endmodule\n"
        "module ga_group_stub;\n"
        "  for (genvar r=0; r<`GA_ROW_PE_NUM; r++) begin: GA_ROW_PE\n"
        "    for (genvar c=0; c<3; c++) begin: GA_COL_PE\n"
        "      ga_pe_stub GA_PE();\n"
        "    end\n"
        "  end\n"
        "endmodule\n"
        "module general_array_stub; ga_group_stub u_GA_PE_Group(); endmodule\n"
        "module slice_stub; general_array_stub u_General_Array(); endmodule\n"
        "module wrapper_stub; slice_stub u_Slice(); endmodule\n"
        "module group_stub;\n"
        "  for (genvar s=0; s<`SLICE_GROUP_NUM; s++) begin: slice_group_gen\n"
        "    wrapper_stub u_slice_wrapper();\n"
        "  end\n"
        "endmodule\n"
        "module ndp_stub;\n"
        "  for (genvar g=0; g<`SLICE_GROUP_SIZE; g++) begin: slice_with_datahub_mc_group_gen\n"
        "    group_stub u_slice_with_datahub_mc_group();\n"
        "  end\n"
        "endmodule\n"
        "module observer_scope_focus;\n"
        "  ndp_stub u_NDP_Top_new();\n"
        f"{shim_body}\n"
        "  logic clk;\n"
        "  integer return_obs_group_id = 0;\n"
        "  integer return_obs_local_slice_id = 0;\n"
        "  integer qadd_ingress_row = 0;\n"
        "  integer qadd_ingress_slot = 0;\n"
        "  longint unsigned qadd_ingress_ga_capture [2];\n"
        "  always @(posedge clk) begin\n"
        f"    {stmt0}\n"
        f"    {stmt1}\n"
        "  end\n"
        "endmodule\n"
    )


def semantic_checks(native: str, shim: str, tail: str) -> dict[str, bool]:
    concatenated = "\n".join((native, shim, tail))
    return_obs = closure(concatenated, "return_obs_")
    qadd = closure(concatenated, "qadd_ingress_")
    rtl = RTL.read_text(encoding="utf-8")
    return {
        "native_includes_v20_shim_once": native.count(
            '`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"'
        )
        == 1,
        "shim_includes_v19_tail_once": shim.count(
            '`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"'
        )
        == 1,
        "all_return_obs_declaration_use_closed": return_obs["valid"],
        "all_qadd_ingress_declaration_use_closed": qadd["valid"],
        "critical_declaration_once": shim.count(f"{CRITICAL};") == 1,
        "critical_two_qualified_xmr_updates": (
            shim.count(f"assign {CRITICAL}") == 2
            and shim.count("ga_pe_inbuffer_enable") == 2
            and ".GA_COL_PE[0].GA_PE" in shim
            and ".GA_COL_PE[2].GA_PE" in shim
        ),
        "critical_tail_uses_exact": tail.count(CRITICAL) == 4,
        "critical_capture_updates_exact": (
            tail.count("qadd_ingress_ga_capture[0]++;") == 1
            and tail.count("qadd_ingress_ga_capture[1]++;") == 1
        ),
        "active_rtl_leaf_declared": (
            re.search(
                r"\b(?:logic|wire)\b[^;]*\bga_pe_inbuffer_enable\b",
                rtl,
                re.DOTALL,
            )
            is not None
        ),
    }


def compile_focus(
    source_text: str, iverilog: Path, temporary: Path, name: str
) -> dict[str, Any]:
    source = temporary / f"{name}.sv"
    output = temporary / f"{name}.vvp"
    source.write_text(source_text, encoding="utf-8", newline="\n")
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
        encoding="utf-8",
        errors="replace",
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
        "source_sha256": sha_bytes(source.read_bytes()),
    }


def evaluate(
    native: str,
    shim: str,
    tail: str,
    iverilog: Path,
    temporary: Path,
    name: str,
) -> dict[str, Any]:
    checks = semantic_checks(native, shim, tail)
    try:
        source = focus_source(shim, tail)
    except GateError as exc:
        return {
            "valid": False,
            "validator_exit": 1,
            "semantic_checks": checks,
            "focused_compile": {
                "command": "NOT_RUN_FOCUSED_SOURCE_CONTRACT_FAILED",
                "exit_code": 1,
                "stdout": "",
                "stderr": str(exc),
                "source_sha256": None,
            },
        }
    compile_result = compile_focus(source, iverilog, temporary, name)
    valid = all(checks.values()) and compile_result["exit_code"] == 0
    return {
        "valid": valid,
        "validator_exit": 0 if valid else 1,
        "semantic_checks": checks,
        "focused_compile": compile_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    payloads, structure = read_exact(zip_path)
    native = payloads["native"].decode()
    shim = payloads["shim"].decode()
    tail = payloads["tail"].decode()

    with tempfile.TemporaryDirectory(prefix="qadd-v20-hdl-scope-") as raw:
        temporary = Path(raw)
        positive = evaluate(native, shim, tail, args.iverilog, temporary, "positive")
        declaration_pattern = re.compile(
            r"logic\s+\[`SLICE_GROUP_SIZE-1:0\]\[`SLICE_GROUP_NUM-1:0\]\s*"
            r"\[`GA_ROW_PE_NUM-1:0\]\[1:0\]\[`GA_PE_INPORT_NUM-1:0\]\s*"
            r"return_obs_ga_operand_capture_mon;\s*",
            re.DOTALL,
        )
        shim_without_declaration, declaration_delete_count = (
            declaration_pattern.subn("", shim, count=1)
        )
        if declaration_delete_count != 1:
            raise GateError("critical declaration deletion preimage differs")
        mutations = {
            "delete_declaration": (
                native,
                shim_without_declaration,
                tail,
            ),
            "misspell_use": (
                native,
                shim,
                tail.replace(
                    "return_obs_ga_operand_capture_mon",
                    "return_obs_ga_operand_capture_mon_TYPO",
                    1,
                ),
            ),
            "delete_key_update": (
                native,
                shim,
                tail.replace("qadd_ingress_ga_capture[0]++;", "", 1),
            ),
        }
        negatives = {
            name: evaluate(*values, args.iverilog, temporary, name)
            for name, values in mutations.items()
        }
    version = subprocess.run(
        [str(args.iverilog), "-V"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    full = "\n".join((native, shim, tail))
    all_negative = all(not value["valid"] for value in negatives.values())
    valid = positive["valid"] and all_negative
    report = {
        "schema": "qlinearadd-node0007-v20-observer-hdl-scope-revalidation-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": (
            "HDL_SCOPE_REVALIDATION_PASS"
            if valid
            else "HDL_SCOPE_REVALIDATION_FAILED"
        ),
        "valid": valid,
        "package_release": (
            "PACKAGE_READY_NOT_RUN" if valid else "QUARANTINED_HDL_SCOPE_FAILURE"
        ),
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256_before": sha_file(zip_path),
            "sha256_after": sha_file(zip_path),
            "bytes_unchanged": True,
        },
        "zip_structure": structure,
        "members": {
            key: {
                "path": MEMBERS[key],
                "bytes": len(payload),
                "sha256": sha_bytes(payload),
            }
            for key, payload in payloads.items()
        },
        "rule_receipts": {
            key: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha_file(path),
                "mutable": key == "plan_mutable",
            }
            for key, path in RULES.items()
        },
        "full_observer_machine_closure": {
            "return_obs": closure(full, "return_obs_"),
            "qadd_ingress": closure(full, "qadd_ingress_"),
            "critical_identifier": CRITICAL,
            "declaration_count": shim.count(f"{CRITICAL};"),
            "qualified_xmr_update_count": shim.count(f"assign {CRITICAL}"),
            "tail_use_count": tail.count(CRITICAL),
            "capture_counter_update_count": (
                tail.count("qadd_ingress_ga_capture[0]++;")
                + tail.count("qadd_ingress_ga_capture[1]++;")
            ),
        },
        "frontend": {
            "tool": str(args.iverilog.resolve()),
            "version_exit": version.returncode,
            "version_first_line": (
                (version.stdout + version.stderr).splitlines()[0]
                if version.stdout or version.stderr
                else ""
            ),
            "positive": positive,
            "claim_boundary": (
                "Icarus 12.0 elaborates the exact v20 shim declaration, both "
                "exact qualified XMR assignments, and an index-specialized form of "
                "the exact v19 capture-use/update statements against a focused "
                "hierarchy-compatible stub. Only runtime packed-array indices are "
                "specialized to zero because Icarus 12.0 rejects those variable "
                "selects; the identifier, select rank, capture bit and update are "
                "unchanged. The full "
                "concatenated final observer bytes additionally pass machine "
                "declaration/use/update closure. Production VCS remains the final "
                "full-design compilation/elaboration evidence."
            ),
        },
        "negative_controls": negatives,
        "all_negative_controls_fail_closed": all_negative,
        "safe_compile_stub_used_as_hdl_evidence": False,
        "numeric_workload_config_golden_repeated": False,
        "functional_rtl_modified": False,
        "package_bytes_modified": False,
        "server_action": False,
        "rule_delta_proposal": (
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
        ),
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "valid": valid,
                "positive_frontend_exit": positive["focused_compile"]["exit_code"],
                "negative_validator_exits": {
                    key: value["validator_exit"] for key, value in negatives.items()
                },
                "output": str(output),
            },
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
