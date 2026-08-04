from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True

INSTALL_NAME = "r5_n4_hw_v25_terminal_match_diag"
MARKER = "    // v25: exact raw-last -> qualified terminal-match boundary."
CONTROL_RELATIVE = (
    "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/"
    "SA_PE_Control_Block.sv"
)
XMR_LEAVES = (
    "sa_pe_inport_valid_bit_unmasked",
    "sa_pe_inport_last_bit_unmasked",
    "sa_pe_inport_same_bit_unmasked",
    "sa_pe_inport_gotten_bit",
    "sa_pe_inport_valid_bit_masked",
    "sa_pe_inport_last_bit_masked",
    "sa_pe_inport_last_index",
    "sa_pe_all_inport_matched",
    "sa_pe_alu_pipeline0_enable",
    "sa_pe_transout_last_index",
    "sa_pe_transout_last_index_diff",
    "sa_pe_transout_last_ignore",
    "sa_pe_transout_last_matched",
    "sa_pe_transout_last_out",
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path) -> tuple[dict[str, bytes], list[str]]:
    entries: dict[str, bytes] = {}
    errors: list[str] = []
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failed: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                errors.append(f"unsafe/duplicate/symlink: {info.filename}")
                continue
            seen.add(info.filename)
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            if pure.parts[0] != INSTALL_NAME or len(pure.parts) < 2:
                errors.append(f"root differs: {info.filename}")
                continue
            entries[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(
                info
            )
    if roots != {INSTALL_NAME}:
        errors.append(f"root set differs: {sorted(roots)}")
    return entries, errors


def stub_prefix() -> str:
    control_declarations = """
module terminal_match_control_stub;
  logic [2:0] sa_pe_inport_valid_bit_unmasked;
  logic [2:0] sa_pe_inport_last_bit_unmasked;
  logic [2:0] sa_pe_inport_same_bit_unmasked;
  logic [2:0] sa_pe_inport_gotten_bit;
  logic [2:0] sa_pe_inport_valid_bit_masked;
  logic [2:0] sa_pe_inport_last_bit_masked;
  logic [2:0][3:0] sa_pe_inport_last_index;
  logic sa_pe_all_inport_matched;
  logic sa_pe_alu_pipeline0_enable;
  logic [3:0] sa_pe_transout_last_index;
  logic [4:0] sa_pe_transout_last_index_diff;
  logic sa_pe_transout_last_ignore;
  logic sa_pe_transout_last_matched;
  logic sa_pe_transout_last_out;
endmodule
"""
    return (
        "`timescale 1ns/1ps\n"
        "`define SLICE_GROUP_SIZE 1\n"
        "`define SLICE_GROUP_NUM 1\n"
        "`define SA_ROW_PE_NUM 1\n"
        "`define SA_COL_PE_NUM 1\n"
        "`define SA_PE_INPORT_NUM 3\n"
        "`define PORT_LAST_INDEX 4\n"
        + control_declarations
        + """
module terminal_match_pe_stub;
  terminal_match_control_stub u_SA_PE_Control_Block();
endmodule
module terminal_match_pe_group_stub;
  generate
    for (genvar r = 0; r < 1; r++) begin : SA_ROW_PE
      for (genvar c = 0; c < 1; c++) begin : SA_COL_PE
        terminal_match_pe_stub u_SA_PE();
      end
    end
  endgenerate
endmodule
module terminal_match_specialized_stub;
  terminal_match_pe_group_stub u_SA_PE_Group();
endmodule
module terminal_match_slice_stub;
  terminal_match_specialized_stub u_Specialized_Array();
endmodule
module terminal_match_wrapper_stub;
  terminal_match_slice_stub u_Slice();
endmodule
module terminal_match_group_stub;
  generate
    for (genvar s = 0; s < 1; s++) begin : slice_group_gen
      terminal_match_wrapper_stub u_slice_wrapper();
    end
  endgenerate
endmodule
module terminal_match_ndp_stub;
  logic clk_db;
  logic rst_n_db;
  generate
    for (genvar g = 0; g < 1; g++) begin : slice_with_datahub_mc_group_gen
      terminal_match_group_stub u_slice_with_datahub_mc_group();
    end
  endgenerate
endmodule
module terminal_match_focus_top;
  terminal_match_ndp_stub u_NDP_Top_new();
  bit return_obs_fr_enabled;
  bit return_obs_active;
  integer return_obs_fd;
  integer return_obs_fr_limit;
  integer return_obs_group_id;
  integer return_obs_local_slice_id;
  logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
        return_obs_fr_input_last_mon;
  logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
        [`PORT_LAST_INDEX-1:0] return_obs_fr_input_last_index_mon;
"""
    )


def focus_source(block: str) -> str:
    # Icarus does not elaborate variable selects on the packed dimensions
    # used by the production observer. Server VCS already compiled the same
    # legacy packed-index pattern in v24. Normalize only those selects in this
    # focused projection; declarations, uses, XMR leaves and new control flow
    # remain the exact v25 text.
    projected = block
    for old, new in (
        ("[return_obs_group_id]", "[0]"),
        ("[return_obs_local_slice_id]", "[0]"),
        ("[return_obs_tm_r]", "[0]"),
        ("[return_obs_tm_c]", "[0]"),
        ("[return_obs_tm_p]", "[0]"),
    ):
        projected = projected.replace(old, new)
    return (
        stub_prefix()
        + projected
        + """
  initial begin
    return_obs_fr_enabled = 1'b0;
    return_obs_active = 1'b0;
    return_obs_fd = 0;
    return_obs_fr_limit = 1;
    return_obs_group_id = 0;
    return_obs_local_slice_id = 0;
    return_obs_write_terminal_match_state("FOCUS");
    #1 $finish;
  end
endmodule
"""
    )


def compile_case(
    iverilog: Path, root: Path, name: str, source: str
) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    process = subprocess.run(
        [
            str(iverilog),
            "-g2012",
            "-s",
            "terminal_match_focus_top",
            "-o",
            str(output_path),
            str(source_path),
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "command": [
            str(iverilog),
            "-g2012",
            "-s",
            "terminal_match_focus_top",
            "-o",
            str(output_path),
            str(source_path),
        ],
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def main() -> int:
    global INSTALL_NAME
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--install-name", default=INSTALL_NAME)
    args = parser.parse_args()

    INSTALL_NAME = args.install_name
    project = args.project_root.resolve()
    zip_path = args.zip.resolve()
    iverilog = args.iverilog.resolve()
    entries, errors = read_zip(zip_path)
    observer_payload = entries.get(
        "tb_probe/native_return_observer.svh", b""
    )
    observer = observer_payload.decode("utf-8", errors="replace")
    if observer.count(MARKER) != 1:
        errors.append("v25 observer marker count differs")
        block = ""
    else:
        block = observer[observer.index(MARKER) :]

    control_path = project / CONTROL_RELATIVE
    control = control_path.read_text(encoding="utf-8")
    leaf_checks = {
        leaf: bool(re.search(rf"\b{re.escape(leaf)}\b", control))
        for leaf in XMR_LEAVES
    }
    if not all(leaf_checks.values()):
        errors.append("one or more v25 XMR leaves absent from active RTL")

    with tempfile.TemporaryDirectory(
        prefix="node0004-v25-scope-", dir=project / "outputs"
    ) as temp:
        temp_root = Path(temp)
        positive = compile_case(
            iverilog, temp_root, "positive", focus_source(block)
        )
        negatives: dict[str, dict[str, Any]] = {}
        mutations = {
            "delete_counter_declaration": (
                "    longint unsigned return_obs_tm_qualified_terminal_accepts;\n",
                "",
                None,
            ),
            "typo_xmr_leaf": (
                ".sa_pe_inport_last_bit_unmasked",
                ".sa_pe_inport_last_bit_unmasked_typo",
                None,
            ),
            "typo_counter_use": (
                "return_obs_tm_qualified_terminal_accepts++;",
                "return_obs_tm_qualified_terminal_accepts_typo++;",
                None,
            ),
            "delete_qualified_update": (
                "                        return_obs_tm_qualified_terminal_accepts++;\n",
                "",
                "return_obs_tm_qualified_terminal_accepts++;",
            ),
        }
        for name, (old, new, required_update) in mutations.items():
            if block.count(old) != 1:
                errors.append(f"negative mutation anchor differs: {name}")
                continue
            mutated_block = block.replace(old, new, 1)
            result = compile_case(
                iverilog,
                temp_root,
                name,
                focus_source(mutated_block),
            )
            semantic_closure_pass = (
                required_update is None or required_update in mutated_block
            )
            result["semantic_closure_pass"] = semantic_closure_pass
            result["validator_exit_code"] = (
                0
                if result["exit_code"] == 0 and semantic_closure_pass
                else 1
            )
            result["failed_closed"] = result["validator_exit_code"] != 0
            negatives[name] = result

    positive_pass = positive["exit_code"] == 0
    negatives_pass = (
        len(negatives) == 4
        and all(row["failed_closed"] for row in negatives.values())
    )
    if not positive_pass:
        errors.append("focused compatible frontend positive failed")
    if not negatives_pass:
        errors.append("one or more focused HDL negatives did not fail closed")

    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    manifest_exact = (
        set(manifest.get("files", {}))
        == set(entries) - {"package_manifest.json"}
        and all(
            path in entries
            and sha256_bytes(entries[path]) == digest
            for path, digest in manifest.get("files", {}).items()
        )
    )
    if not manifest_exact:
        errors.append("final ZIP manifest exact-set differs")

    report = {
        "schema": "node0004-v25-terminal-match-observer-syntax-scope-v1",
        "valid": not errors,
        "errors": errors,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": sha256_file(zip_path),
            "manifest_exact_set": manifest_exact,
        },
        "observer": {
            "bytes": len(observer_payload),
            "sha256": sha256_bytes(observer_payload),
            "new_block_marker_count": observer.count(MARKER),
        },
        "active_rtl_leaf": {
            "path": CONTROL_RELATIVE,
            "bytes": control_path.stat().st_size,
            "sha256": sha256_file(control_path),
            "xmr_leaf_checks": leaf_checks,
        },
        "focused_compatible_frontend": {
            "tool": str(iverilog),
            "positive": positive,
            "claim": (
                "syntax and identifier/scope resolution for the v25 new "
                "terminal-match block against a focused hierarchy, with "
                "only Icarus-unsupported packed variable selects normalized"
            ),
            "projection_normalization": [
                "return_obs_group_id -> 0",
                "return_obs_local_slice_id -> 0",
                "return_obs_tm_r -> 0",
                "return_obs_tm_c -> 0",
                "return_obs_tm_p -> 0",
            ],
            "not_claimed": [
                "full-design elaboration",
                "server VCS compatibility beyond the used SV subset",
                "functional correctness or E3/E4/E5",
            ],
        },
        "negative_controls": negatives,
        "all_negative_controls_fail_closed": negatives_pass,
        "safe_compile_stub_used_as_hdl_evidence": False,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
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
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
