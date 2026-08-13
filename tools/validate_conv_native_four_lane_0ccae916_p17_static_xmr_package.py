#!/usr/bin/env python3
"""Final-ZIP audit for native-four-lane p17 genvar-static XMR successor."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import types
import zipfile
from pathlib import Path
from typing import Any


if "jsonschema" not in sys.modules:
    sys.modules["jsonschema"] = types.SimpleNamespace(validate=lambda *_a, **_k: None)

import build_conv_native_four_lane_0ccae916_p17_static_xmr_package as build
import validate_conv_native_four_lane_0ccae916_p16_buffer5_public_package as p16
from validate_server_package_runtime_layout import validate as validate_layout


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = build.SOURCE_ID
PACKAGE_ID = build.PACKAGE_ID
WORKLOAD_INSTALL_NAME = build.WORKLOAD_INSTALL_NAME
SOURCE_SHA256 = build.SOURCE_SHA256
SOURCE_ZIP = build.SOURCE_ZIP
OUTPUT_ROOT = build.DEFAULT_OUTPUT
ZIP_PATH = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
SIDECAR = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
BUILD_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.build.json"
BUILD_PROFILE = OUTPUT_ROOT / f"{PACKAGE_ID}.build_profile.json"
HARNESS_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.runtime_layout_harness.json"
SHARED_REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.shared_runtime_layout.json"
REPORT = OUTPUT_ROOT / f"{PACKAGE_ID}.final_zip_audit.json"
SOURCE_ANALYSIS = build.SOURCE_ANALYSIS
LAYOUT_HELPER = ROOT / "tools/server_package_runtime_layout.py"
OBSERVER = build.OBSERVER
FINALIZER = p16.FINALIZER
INPUT_PREFIX = build.INPUT_PREFIX
OLD_INPUT_PREFIX = build.OLD_INPUT_PREFIX
OLD_OUTPUT_PREFIX = build.OLD_OUTPUT_PREFIX
OUTPUT_PREFIX = build.OUTPUT_PREFIX
ALLOWED_CHANGED_PATHS = build.ALLOWED_CHANGED_PATHS
BUFFER_LEAF = p16.BUFFER_LEAF
BUFFER_LEAF_SHA256 = p16.BUFFER_LEAF_SHA256
REQUIRED_PUBLIC_PORTS = p16.REQUIRED_PUBLIC_PORTS
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return p16.sha256(path)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    p16.write_json(path, value)


def configure_family() -> None:
    values = {
        "SOURCE_ID": SOURCE_ID,
        "PACKAGE_ID": PACKAGE_ID,
        "SOURCE_SHA256": SOURCE_SHA256,
        "SOURCE_ZIP": SOURCE_ZIP,
        "OUTPUT_ROOT": OUTPUT_ROOT,
        "ZIP_PATH": ZIP_PATH,
        "SIDECAR": SIDECAR,
        "BUILD_REPORT": BUILD_REPORT,
        "BUILD_PROFILE": BUILD_PROFILE,
        "HARNESS_REPORT": HARNESS_REPORT,
        "SHARED_REPORT": SHARED_REPORT,
        "REPORT": REPORT,
        "LAYOUT_HELPER": LAYOUT_HELPER,
        "OLD_OUTPUT_PREFIX": OLD_OUTPUT_PREFIX,
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
        "ALLOWED_CHANGED_PATHS": ALLOWED_CHANGED_PATHS,
        "WORKLOAD_INSTALL_NAME": WORKLOAD_INSTALL_NAME,
    }
    for name, value in values.items():
        setattr(p16, name, value)
        setattr(p16.p15, name, value)
    p16.configure_family()
    setattr(p16.p15, "WORKLOAD_INSTALL_NAME", WORKLOAD_INSTALL_NAME)
    setattr(p16.p15.base, "WORKLOAD_INSTALL_NAME", WORKLOAD_INSTALL_NAME)
    setattr(p16.p15.base, "RUNTIME_PREFIX", INPUT_PREFIX)


def payloads(zip_path: Path, root: str) -> dict[str, bytes]:
    return p16.payloads(zip_path, root)


def walk_paths(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "path" and isinstance(child, str):
                result.append(child)
            else:
                result.extend(walk_paths(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(walk_paths(child))
    return result


def mechanical_json_paths(
    left_bytes: bytes,
    right_bytes: bytes,
    old_prefix: str,
    new_prefix: str,
    expected: int,
) -> bool:
    left = json.loads(left_bytes)
    right = json.loads(right_bytes)
    if set(left) != set(right):
        return False
    left_paths = walk_paths(left)
    right_paths = walk_paths(right)
    if len(left_paths) != expected or len(right_paths) != expected:
        return False

    def strip_paths(value: Any, prefix: str) -> Any:
        result = copy.deepcopy(value)

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for key, child in node.items():
                    if key == "path" and isinstance(child, str):
                        if not child.startswith(prefix):
                            raise AuditError(f"path prefix differs: {child}")
                        node[key] = child[len(prefix) :]
                    else:
                        walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)

        walk(result)
        return result

    return strip_paths(left, old_prefix) == strip_paths(right, new_prefix)


def frozen_surface_audit() -> dict[str, Any]:
    source = payloads(SOURCE_ZIP, SOURCE_ID)
    successor = payloads(ZIP_PATH, PACKAGE_ID)
    all_paths = sorted(set(source) | set(successor))
    changed = [
        path for path in all_paths if source.get(path) != successor.get(path)
    ]
    unexpected = sorted(set(changed) - ALLOWED_CHANGED_PATHS)
    missing = sorted(ALLOWED_CHANGED_PATHS - set(changed))
    frozen = [
        path
        for path in all_paths
        if path not in ALLOWED_CHANGED_PATHS
        and source.get(path) != successor.get(path)
    ]
    sca_input = mechanical_json_paths(
        source["workload/runtime/runs/c0/sca_cfg.json"],
        successor["workload/runtime/runs/c0/sca_cfg.json"],
        OLD_INPUT_PREFIX,
        INPUT_PREFIX,
        86,
    )
    sca_d = mechanical_json_paths(
        source["workload/runtime/runs/c0/sca_cfg_D.json"],
        successor["workload/runtime/runs/c0/sca_cfg_D.json"],
        OLD_OUTPUT_PREFIX,
        OUTPUT_PREFIX,
        28,
    )
    frozen_payload_paths = [
        path
        for path in all_paths
        if any(
            token in path
            for token in (
                "golden/",
                "mapping",
                "bitstream",
                "execplan",
                "matrix_A",
                "matrix_B",
                "typed",
                "qparam",
            )
        )
        and path
        not in {
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        }
    ]
    payload_equal = all(
        source.get(path) == successor.get(path)
        for path in frozen_payload_paths
    )
    valid = (
        sha256(SOURCE_ZIP) == SOURCE_SHA256
        and not unexpected
        and not missing
        and not frozen
        and sca_input
        and sca_d
        and payload_equal
    )
    return {
        "source_zip_sha256": sha256(SOURCE_ZIP),
        "source_identity_valid": sha256(SOURCE_ZIP) == SOURCE_SHA256,
        "changed_paths": changed,
        "allowed_changed_paths": sorted(ALLOWED_CHANGED_PATHS),
        "unexpected_changes": unexpected,
        "missing_expected_changes": missing,
        "frozen_member_count": len(all_paths) - len(ALLOWED_CHANGED_PATHS),
        "frozen_mismatch": frozen,
        "sca_input_install_prefix_change_mechanical_only": sca_input,
        "sca_d_run_prefix_change_mechanical_only": sca_d,
        "numeric_w3_golden_mapping_bitstream_execplan_equal": payload_equal,
        "valid": valid,
    }


def projected_paths(package: Path, contract: dict[str, Any]) -> set[str]:
    sca = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg.json").read_text(
            encoding="utf-8"
        )
    )
    sca_d = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg_D.json").read_text(
            encoding="utf-8"
        )
    )
    attempt = "a" * build.p16.base.ATTEMPT_MAX_CHARS
    result = set(walk_paths(sca)) | set(walk_paths(sca_d))
    result.update(
        path.replace("{attempt}", attempt)
        for path in contract["path_budget"]["additional_projected_paths"]
    )
    result.update(
        value.replace("{attempt}", attempt)
        for value in contract["runtime_roots"].values()
    )
    return result


def static_audit(package: Path) -> dict[str, Any]:
    manifest = json.loads(
        (package / "package_manifest.json").read_text(encoding="utf-8")
    )
    contract = json.loads(
        (package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    observed = p16.p15.base.package_records(package)
    sidecar = SIDECAR.read_text(encoding="ascii").split()
    sca = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg.json").read_text(
            encoding="utf-8"
        )
    )
    input_rows = []
    for consumer in sorted(set(walk_paths(sca))):
        relative = (
            consumer[len(INPUT_PREFIX) :]
            if consumer.startswith(INPUT_PREFIX)
            else None
        )
        target = (
            package / "workload/runtime" / relative
            if relative is not None
            else package / "__invalid__"
        )
        input_rows.append(
            {
                "path": consumer,
                "member": (
                    f"workload/runtime/{relative}"
                    if relative is not None
                    else None
                ),
                "bytes": target.stat().st_size if target.is_file() else None,
                "sha256": sha256(target) if target.is_file() else None,
                "valid": relative is not None and target.is_file(),
            }
        )
    sca_d = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg_D.json").read_text(
            encoding="utf-8"
        )
    )
    output_paths = sorted(set(walk_paths(sca_d)))
    outputs_valid = (
        len(output_paths) == 28
        and all(path.startswith(OUTPUT_PREFIX) for path in output_paths)
    )
    paths = projected_paths(package, contract)
    exact_longest = max(paths, key=lambda value: (len(value), value))
    budget = manifest["path_length_budget"]
    budget_exact = (
        budget["longest_projected_relative_path"] == exact_longest
        and budget["longest_projected_relative_path_chars"]
        == len(exact_longest)
        and budget["max_projected_relative_path_chars"]
        == len(exact_longest)
        and budget["max_projected_absolute_path_chars"]
        == budget["declared_target_root_max_chars"] + 1 + len(exact_longest)
        and budget["max_projected_absolute_path_chars"]
        <= budget["absolute_path_limit_chars"]
    )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    install_contract = (
        contract["package_id"] == PACKAGE_ID
        and contract["install_name"] == WORKLOAD_INSTALL_NAME
        and contract["runtime_roots"]["cfg_root"]
        == f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}"
        and contract["required_preexisting_parents"] == ["install"]
        and contract["package_creatable_parent_dirs"]
        == ["install/cfg_pkg", "install/codex_runs"]
    )
    stale_install = OLD_INPUT_PREFIX.rstrip("/") in runner
    valid = (
        sidecar == [sha256(ZIP_PATH), ZIP_PATH.name]
        and manifest.get("files") == observed
        and manifest.get("package_identity") == PACKAGE_ID
        and manifest.get("install_name") == WORKLOAD_INSTALL_NAME
        and install_contract
        and all(row["valid"] for row in input_rows)
        and outputs_valid
        and budget_exact
        and not stale_install
        and "/home/panqs/ndp/simresult" in runner
        and manifest.get("formal_readback_count") == 0
    )
    return {
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "sidecar_valid": sidecar == [sha256(ZIP_PATH), ZIP_PATH.name],
        "manifest_exact_set_valid": manifest.get("files") == observed,
        "package_identity_valid": (
            manifest.get("package_identity") == PACKAGE_ID
        ),
        "fresh_install_namespace_valid": install_contract and not stale_install,
        "sca_read_input_count": len(input_rows),
        "sca_read_inputs_all_open_exact": all(
            row["valid"] for row in input_rows
        ),
        "sca_read_input_receipts": input_rows,
        "sca_d_output_count": len(output_paths),
        "sca_d_output_prefix_valid": outputs_valid,
        "exact_longest_projected_relative_path": exact_longest,
        "exact_longest_projected_relative_path_chars": len(exact_longest),
        "path_budget_self_consistent": budget_exact,
        "formal_readback_count": manifest.get("formal_readback_count"),
        "valid": valid,
    }


def exact_runtime_audit(package: Path, target: Path) -> dict[str, Any]:
    value = p16.p15.base.exact_runtime_audit(package, target)
    mutated = target / "declared_exact_minus_one" / PACKAGE_ID
    shutil.copytree(package, mutated)
    manifest_path = mutated / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    budget = manifest["path_length_budget"]
    exact = budget["max_projected_relative_path_chars"]
    budget["longest_projected_relative_path_chars"] = exact - 1
    budget["max_projected_relative_path_chars"] = exact - 1
    write_json(manifest_path, manifest)
    runtime = (
        mutated
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    server_root = target / "declared_exact_minus_one/NDP_copy_exact"
    (server_root / "install").mkdir(parents=True)
    completed = p16.p15.base.run_python(
        runtime,
        "path-budget",
        "--package-root",
        str(mutated),
        "--server-root",
        str(server_root),
    )
    minus_one = {
        "actual_exact_relative_chars": exact,
        "mutated_declared_relative_chars": exact - 1,
        "exit_code": completed.returncode,
        "stderr_tail": completed.stderr[-4000:],
        "expected_error": "path budget is malformed",
        "valid": (
            completed.returncode != 0
            and "path budget is malformed" in completed.stderr
        ),
    }
    negatives = value["path_budget_negatives"]
    negatives["declared_112"]["applicability"] = (
        "not_applicable_equal_to_exact_positive_value"
    )
    negatives["declared_112"]["valid"] = True
    negatives["declared_exact_minus_one"] = minus_one
    value["valid"] = (
        value["positive_path_budget"]["exit_code"] == 0
        and value["positive_preflight"]["exit_code"] == 0
        and all(row["valid"] for row in negatives.values())
        and value["package_file_mutation_negative"]["valid"]
    )
    return value


def exact_guard_prepare(
    original: Any,
    package: Path,
    scenario_root: Path,
    mode: str,
) -> tuple[Path, Path, Path, Path, dict[str, str]]:
    value = p16.exact_guard_prepare(
        original, package, scenario_root, mode
    )
    if mode == "preflight_fail":
        exact_package = scenario_root / "exact" / PACKAGE_ID
        manifest_path = exact_package / "package_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        budget = manifest["path_length_budget"]
        exact = budget["max_projected_relative_path_chars"]
        budget["longest_projected_relative_path_chars"] = exact - 1
        budget["max_projected_relative_path_chars"] = exact - 1
        write_json(manifest_path, manifest)
    return value


def public_surface_and_constant_xmr(package: Path) -> dict[str, Any]:
    if sha256(BUFFER_LEAF) != BUFFER_LEAF_SHA256:
        raise AuditError("current Buffer.sv identity differs")
    leaf_text = BUFFER_LEAF.read_text(encoding="utf-8")
    header = leaf_text[: leaf_text.find(");") + 2]
    leaf_ports = {
        port for port in REQUIRED_PUBLIC_PORTS if port in header
    }
    observer = (package / OBSERVER).read_text(encoding="utf-8")
    if observer.count(build.P17_ANCHOR) != 1:
        raise AuditError("p17 exact observer anchor differs")
    append = build.P17_ANCHOR + observer.split(build.P17_ANCHOR, 1)[1]
    referenced_ports = {
        port
        for port in REQUIRED_PUBLIC_PORTS
        if f".u_Buffer.{port}" in append
    }
    dynamic_instance_patterns = re.findall(
        r"(?:slice_with_datahub_mc_group_gen|slice_group_gen|"
        r"BUFFER_MANAGER|MSE_INST)\[(?:n4d_group_id|"
        r"n4d_local_slice_id|[A-Za-z_][A-Za-z0-9_]*_id)\]",
        append,
    )
    static_assignments = len(
        re.findall(
            r"assign\s+n4b5_[A-Za-z0-9_]+_mon"
            r"\[n4b5_group\]\[n4b5_slice\]\s*=",
            append,
        )
    )
    procedural = append.split("endgenerate", 1)[1]
    procedural_local_reads = len(
        re.findall(
            r"n4b5_[A-Za-z0-9_]+_mon"
            r"\[n4d_group_id\]\[n4d_local_slice_id\]",
            procedural,
        )
    )
    private_tokens = [
        token
        for token in (
            ".valid_buf",
            ".buf_wr_en",
            ".buf_rd_en",
            ".arm_addr_reg",
            ".nrm_clear_reg",
        )
        if token in append
    ]
    wrong_sibling = append.replace("BUFFER_MANAGER[5]", "BUFFER_MANAGER[4]", 1)
    valid = (
        leaf_ports == REQUIRED_PUBLIC_PORTS
        and referenced_ports == REQUIRED_PUBLIC_PORTS
        and not dynamic_instance_patterns
        and static_assignments == 12
        and procedural_local_reads == 34
        and not private_tokens
        and append.count("BUFFER_MANAGER[5]") == 12
        and "BUFFER_MANAGER[4]" in wrong_sibling
    )
    return {
        "actual_target_leaf": str(BUFFER_LEAF),
        "actual_target_leaf_bytes": BUFFER_LEAF.stat().st_size,
        "actual_target_leaf_sha256": sha256(BUFFER_LEAF),
        "actual_target_module": "Buffer",
        "instance_path": (
            "u_NDP_Top_new.slice_with_datahub_mc_group_gen[genvar]."
            "u_slice_with_datahub_mc_group.slice_group_gen[genvar]."
            "u_slice_wrapper.u_Slice.u_LSU.u_Buffer_Manager_Cluster."
            "BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
        ),
        "leaf_public_ports": sorted(leaf_ports),
        "observer_referenced_public_ports": sorted(referenced_ports),
        "static_genvar_assignment_count": static_assignments,
        "procedural_local_monitor_read_count": procedural_local_reads,
        "runtime_indexed_instance_paths": dynamic_instance_patterns,
        "private_xmr_tokens": private_tokens,
        "wrong_sibling_path_negative": "BUFFER_MANAGER[4]" in wrong_sibling,
        "valid": valid,
    }


def focus_wrapper() -> str:
    return r"""`define SLICE_GROUP_SIZE 14
`define SLICE_GROUP_NUM 2
`define BUFFER_BANK_NUM 8
`define BUFFER_BANK_ADDR_WIDTH 2
`define BUFFER_STRB_WIDTH 4

module n4b5_buffer_public_stub;
  logic [`BUFFER_BANK_NUM-1:0] arm2buf_req_valid;
  logic arm2buf_req_rw;
  logic [`BUFFER_BANK_ADDR_WIDTH-1:0] arm2buf_req_addr;
  logic buf2arm_req_ready;
  logic arm2buf_wvalid;
  logic [`BUFFER_BANK_NUM-1:0] arm2buf_clear;
  logic [`BUFFER_BANK_NUM-1:0] mrm2buf_req_valid;
  logic mrm2buf_req_rw;
  logic [`BUFFER_BANK_ADDR_WIDTH-1:0] mrm2buf_req_addr;
  logic [`BUFFER_BANK_NUM-1:0][`BUFFER_STRB_WIDTH-1:0]
      mrm2buf_req_strb;
  logic buf2mrm_req_ready;
  logic [`BUFFER_BANK_NUM-1:0] mrm2buf_clear;
endmodule

module n4b5_buffer_manager_stub;
  n4b5_buffer_public_stub u_Buffer();
endmodule

module n4b5_cluster_stub;
  generate
    for (genvar b = 0; b < 6; b++) begin : BUFFER_MANAGER
      n4b5_buffer_manager_stub u_Buffer_Manager();
    end
  endgenerate
endmodule

module n4b5_lsu_stub;
  n4b5_cluster_stub u_Buffer_Manager_Cluster();
endmodule

module n4b5_slice_stub;
  n4b5_lsu_stub u_LSU();
endmodule

module n4b5_slice_wrapper_stub;
  n4b5_slice_stub u_Slice();
endmodule

module n4b5_group_stub;
  generate
    for (genvar s = 0; s < `SLICE_GROUP_NUM; s++) begin : slice_group_gen
      n4b5_slice_wrapper_stub u_slice_wrapper();
    end
  endgenerate
endmodule

module n4b5_dut_stub;
  logic clk_sg;
  logic rst_n_sg;
  generate
    for (genvar g = 0; g < `SLICE_GROUP_SIZE; g++)
      begin : slice_with_datahub_mc_group_gen
        n4b5_group_stub u_slice_with_datahub_mc_group();
      end
  endgenerate
endmodule

module tb_focus;
  n4b5_dut_stub u_NDP_Top_new();
  logic n4d_active;
  integer n4d_group_id;
  integer n4d_local_slice_id;
  logic n4p_sa_out_raw_valid_now;
  logic n4p_sa_out_ready_now;
  logic [15:0] n4p_sa_out_raw_tag_now;
`include "p17_append.svh"
endmodule
"""


def run_iverilog(
    root: Path, append: str, label: str
) -> subprocess.CompletedProcess[str]:
    case = root / label
    case.mkdir(parents=True)
    (case / "p17_append.svh").write_text(
        append, encoding="utf-8", newline="\n"
    )
    wrapper = case / "focused_wrapper.sv"
    wrapper.write_text(focus_wrapper(), encoding="utf-8", newline="\n")
    return subprocess.run(
        [
            str(IVERILOG),
            "-g2012",
            "-s",
            "tb_focus",
            "-I",
            str(case),
            "-o",
            str(case / "focus.vvp"),
            str(wrapper),
        ],
        cwd=case,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=60,
        check=False,
    )


def changed_hdl_closure(append: str) -> dict[str, Any]:
    ports = sorted(REQUIRED_PUBLIC_PORTS)
    declaration_span = append.split("generate", 1)[0]
    declared = {
        port
        for port in ports
        if re.search(
            rf"\bn4b5_{port}_mon\b[^;]*;",
            declaration_span,
            flags=re.DOTALL,
        )
    }
    assigned = {
        port
        for port in ports
        if re.search(
            rf"assign\s+n4b5_{port}_mon"
            r"\[n4b5_group\]\[n4b5_slice\]\s*=",
            append,
        )
    }
    procedural = append.split("endgenerate", 1)[1]
    used = {
        port
        for port in ports
        if (
            f"n4b5_{port}_mon[n4d_group_id][n4d_local_slice_id]"
            in procedural
        )
    }
    unresolved = sorted((assigned | used) - declared)
    ownerless = sorted(used - assigned)
    valid = (
        declared == set(ports)
        and assigned == set(ports)
        and used == set(ports)
        and not unresolved
        and not ownerless
    )
    return {
        "scope": "p17 changed Buffer5 public monitor leaves",
        "declared": len(declared),
        "assigned": len(assigned),
        "used": len(used),
        "unresolved": unresolved,
        "ownerless_state": ownerless,
        "valid": valid,
    }


def package_local_hdl_gate(
    package: Path, temp_root: Path
) -> dict[str, Any]:
    observer = package / OBSERVER
    text = observer.read_text(encoding="utf-8")
    append = build.P17_ANCHOR + text.split(build.P17_ANCHOR, 1)[1]
    final_pattern = re.compile(
        r"\nfinal begin\n"
        r"\s+if \(n4b5_fd != 0\) begin\n"
        r'\s+n4b5_emit\("final"\);\n'
        r"\s+\$fclose\(n4b5_fd\);\n"
        r"\s+end\n"
        r"end\n?$"
    )
    final_match = final_pattern.search(append)
    omitted_final_span = final_match.group(0) if final_match else ""
    focused_append, final_count = final_pattern.subn(
        "\n// Focused-frontend specialization: final-to-task call omitted.\n",
        append,
        count=1,
    )
    if final_count != 1:
        raise AuditError("p17 focused final-block specialization differs")
    positive = run_iverilog(temp_root, focused_append, "positive")
    declaration_pattern = re.compile(
        r"logic \[`BUFFER_BANK_NUM-1:0\] "
        r"n4b5_arm2buf_req_valid_mon\n"
        r"\s+\[0:`SLICE_GROUP_SIZE-1\]\[0:`SLICE_GROUP_NUM-1\];\n"
    )
    missing_decl, decl_count = declaration_pattern.subn(
        "", focused_append, count=1
    )
    misspelled, use_count = re.subn(
        r"n4b5_arm2buf_req_valid_mon"
        r"\[n4d_group_id\]\[n4d_local_slice_id\]",
        "n4b5_arm2buf_req_valid_mon_typo"
        "[n4d_group_id][n4d_local_slice_id]",
        focused_append,
        count=1,
    )
    assignment_pattern = re.compile(
        r"\s*assign n4b5_arm2buf_req_valid_mon"
        r"\[n4b5_group\]\[n4b5_slice\] =\n"
        r"(?:\s+.*\n)*?"
        r"\s+\.u_Buffer_Manager\.u_Buffer\.arm2buf_req_valid;\n"
    )
    missing_assignment, assignment_count = assignment_pattern.subn(
        "\n", focused_append, count=1
    )
    if decl_count != 1 or use_count != 1 or assignment_count != 1:
        raise AuditError("p17 focused negative mutation anchor differs")
    neg_decl = run_iverilog(temp_root, missing_decl, "delete_declaration")
    neg_use = run_iverilog(temp_root, misspelled, "misspell_consumer")
    positive_closure = changed_hdl_closure(append)
    missing_assignment_closure = changed_hdl_closure(missing_assignment)
    wrapper_sha = sha256_bytes(focus_wrapper().encode())
    version = subprocess.run(
        [str(IVERILOG), "-V"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=20,
        check=False,
    )
    valid = (
        positive.returncode == 0
        and positive_closure["valid"]
        and neg_decl.returncode != 0
        and neg_use.returncode != 0
        and not missing_assignment_closure["valid"]
    )
    return {
        "applicable": True,
        "rule_id": (
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001"
        ),
        "exact_members": [
            {
                "path": OBSERVER,
                "bytes": observer.stat().st_size,
                "sha256": sha256(observer),
                "role": "package-local observer include",
            }
        ],
        "changed_span": {
            "anchor": build.P17_ANCHOR,
            "bytes": len(append.encode()),
            "sha256": sha256_bytes(append.encode()),
            "exact_subspan_of_member": True,
        },
        "include_or_concatenation_order_sha256": sha256_bytes(
            f"{OBSERVER}\n{build.P17_ANCHOR}\n".encode()
        ),
        "frontend": {
            "name": "Icarus Verilog",
            "version": (version.stdout + version.stderr).splitlines()[:3],
            "command": (
                "iverilog -g2012 -s tb_focus -I <case> "
                "-o <case>/focus.vvp <case>/focused_wrapper.sv"
            ),
            "cwd": str(temp_root),
            "exit": positive.returncode,
            "stderr_tail": positive.stderr[-4000:],
            "coverage": "focused exact p17 changed observer span",
        },
        "focused_harness_sha256": wrapper_sha,
        "specializations": [
            {
                "scope": (
                    "external DUT hierarchy/current public port widths and "
                    "the unchanged terminal final-to-task block"
                ),
                "reason": (
                    "full production VCS/vendor/full-DUT frontend is not "
                    "available locally; Icarus rejects task calls from final"
                ),
                "package_local_identifier_rewritten": False,
                "omitted_exact_final_span_sha256": sha256_bytes(
                    omitted_final_span.encode()
                ),
                "changed_monitor_declaration_assignment_use_omitted": False,
            }
        ],
        "closure": positive_closure,
        "negative_controls": {
            "delete_declaration": {
                "frontend_exit": neg_decl.returncode,
                "fail_closed": neg_decl.returncode != 0,
            },
            "misspell_consumer_use": {
                "frontend_exit": neg_use.returncode,
                "fail_closed": neg_use.returncode != 0,
            },
            "delete_continuous_assignment": {
                "frontend_exit_not_required": True,
                "semantic_closure": missing_assignment_closure,
                "fail_closed": not missing_assignment_closure["valid"],
            },
        },
        "claim_boundary": (
            "Compatible focused frontend proves syntax/elaboration/name "
            "closure of exact p17 changed declarations, genvar-static XMR "
            "assignments and procedural local-array consumers. Production "
            "full-design VCS remains the final compile/elaboration evidence."
        ),
        "pass": valid,
    }


def legacy_namespace_regression(
    package: Path, harness_root: Path
) -> dict[str, Any]:
    original_prepare = p16.p15.base.prepare_runner_harness

    def prepare_with_legacy(
        pkg: Path, root: Path, mode: str
    ) -> tuple[Path, Path, Path, Path, dict[str, str]]:
        value = p16.p15.install_only_prepare(pkg, root, mode)
        server_root = value[1]
        legacy_cfg = (
            server_root / "install/cfg_pkg" / build.OLD_INSTALL_NAME
        )
        legacy_run = server_root / "install/codex_runs" / SOURCE_ID
        legacy_cfg.mkdir(parents=True)
        legacy_run.mkdir(parents=True)
        (legacy_cfg / "preserve.marker").write_text(
            "preserve\n", encoding="utf-8"
        )
        (legacy_run / "preserve.marker").write_text(
            "preserve\n", encoding="utf-8"
        )
        return value

    p16.p15.base.prepare_runner_harness = prepare_with_legacy
    try:
        value = p16.p15.base.run_runner_scenario(
            package, harness_root, "normal"
        )
    finally:
        p16.p15.base.prepare_runner_harness = original_prepare
    server_root = harness_root / "normal/NDP_copy_stub"
    cfg_marker = (
        server_root
        / "install/cfg_pkg"
        / build.OLD_INSTALL_NAME
        / "preserve.marker"
    )
    run_marker = (
        server_root
        / "install/codex_runs"
        / SOURCE_ID
        / "preserve.marker"
    )
    fresh_cfg = server_root / "install/cfg_pkg" / WORKLOAD_INSTALL_NAME
    valid = (
        value["valid"]
        and value["compile_started"]
        and value["simulation_started"]
        and cfg_marker.read_text(encoding="utf-8") == "preserve\n"
        and run_marker.read_text(encoding="utf-8") == "preserve\n"
        and fresh_cfg.is_dir()
    )
    return {
        "source_legacy_cfg_preserved": cfg_marker.is_file(),
        "source_legacy_run_preserved": run_marker.is_file(),
        "fresh_cfg_created": fresh_cfg.is_dir(),
        "compile_started": value["compile_started"],
        "simulation_started": value["simulation_started"],
        "root_direct_child_exact_set_unchanged": value[
            "root_direct_child_exact_set_unchanged"
        ],
        "valid": valid,
    }


def main() -> int:
    configure_family()
    for path in (HARNESS_REPORT, SHARED_REPORT, REPORT):
        if path.exists():
            raise AuditError(f"refusing to overwrite audit output: {path}")
    required = (
        ZIP_PATH,
        SIDECAR,
        SOURCE_ZIP,
        BUILD_REPORT,
        BUILD_PROFILE,
        SOURCE_ANALYSIS,
    )
    if not all(path.is_file() for path in required):
        raise AuditError("p17 final audit input is missing")
    with tempfile.TemporaryDirectory(prefix=".p17_audit_", dir=ROOT) as temp:
        temp_root = Path(temp)
        package = p16.p15.base.safe_extract(
            ZIP_PATH, temp_root / "extract", PACKAGE_ID
        )
        static = static_audit(package)
        frozen = frozen_surface_audit()
        runtime = exact_runtime_audit(package, temp_root / "exact_runtime")
        guard = p16.exact_observer_guard(package, temp_root)
        public = public_surface_and_constant_xmr(package)
        hdl = package_local_hdl_gate(package, temp_root / "hdl")
        trace = p16.trace_unit(package, temp_root)
        syntax = p16.syntax_checks(package, temp_root)
        original_prepare = p16.p15.ORIGINAL_PREPARE
        p16.p15.ORIGINAL_PREPARE = (
            lambda pkg, root, mode: exact_guard_prepare(
                original_prepare, pkg, root, mode
            )
        )
        try:
            scenarios = {
                name: p16.runner_scenario(
                    package, temp_root / "runner", name
                )
                for name in (
                    "normal",
                    "preflight_fail",
                    "compile_fail",
                    "HUP",
                    "INT",
                    "TERM",
                    "missing_parent",
                )
            }
        finally:
            p16.p15.ORIGINAL_PREPARE = original_prepare
        legacy = legacy_namespace_regression(
            package, temp_root / "legacy_namespace"
        )
        harness = p16.p15.shared_harness(scenarios)
        write_json(HARNESS_REPORT, harness)
        shared = validate_layout(ZIP_PATH, HARNESS_REPORT, LAYOUT_HELPER)
        write_json(SHARED_REPORT, shared)
    common = p16.shared_public_regression()
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    profile_valid = (
        profile.get("contract_valid") is True
        and profile.get("package_id") == PACKAGE_ID
        and {
            "package_identity",
            "install_name",
            "observer",
            "sca_path_binding",
        }
        <= set(profile.get("changed_surfaces", []))
    )
    positive_chain = (
        scenarios["normal"]["valid"]
        and scenarios["normal"]["compile_started"]
        and scenarios["normal"]["simulation_started"]
    )
    valid = (
        static["valid"]
        and frozen["valid"]
        and runtime["valid"]
        and guard["valid"]
        and public["valid"]
        and hdl["pass"]
        and trace["valid"]
        and syntax["valid"]
        and all(row["valid"] for row in scenarios.values())
        and legacy["valid"]
        and positive_chain
        and shared["pass"]
        and not shared["errors"]
        and common["valid"]
        and profile_valid
    )
    result = {
        "schema": (
            "conv-native-four-lane-p17-genvar-xmr-final-zip-audit-v1"
        ),
        "status": "PACKAGE_READY_NOT_RUN" if valid else "PACKAGE_AUDIT_FAILED",
        "valid": valid,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": valid,
        "package_identity": PACKAGE_ID,
        "zip": str(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "zip_sha256": sha256(ZIP_PATH),
        "source_p16_zip_sha256": sha256(SOURCE_ZIP),
        "source_p16_return_analysis_sha256": sha256(SOURCE_ANALYSIS),
        "static_zip_audit": static,
        "frozen_surface_audit": frozen,
        "exact_runtime_path_budget_and_preflight": runtime,
        "exact_observer_guard": guard,
        "public_surface_and_constant_xmr": public,
        "package_local_hdl_gate": hdl,
        "diagnostic_predicate_trace": trace,
        "syntax_checks": syntax,
        "exact_runner_harness": scenarios,
        "legacy_namespace_collision_regression": legacy,
        "exact_runner_to_compile_and_simulator_stub_positive": positive_chain,
        "runtime_layout_harness": {
            "path": str(HARNESS_REPORT),
            "bytes": HARNESS_REPORT.stat().st_size,
            "sha256": sha256(HARNESS_REPORT),
        },
        "shared_runtime_layout": {
            "path": str(SHARED_REPORT),
            "bytes": SHARED_REPORT.stat().st_size,
            "sha256": sha256(SHARED_REPORT),
            "pass": shared["pass"],
            "errors": len(shared["errors"]),
            "exact_final_zip_invocation_count": 1,
        },
        "shared_public_regression": common,
        "shadow_profile_compare": {
            "profile": str(BUILD_PROFILE),
            "profile_sha256": sha256(BUILD_PROFILE),
            "contract_valid": profile_valid,
            "family_validator_authoritative": True,
        },
        "release_gate_matrix": {
            "core_identity_bootstrap": {
                "disposition": "blocking_applicable",
                "pass": static["valid"] and frozen["valid"],
            },
            "runner_control_flow": {
                "disposition": "blocking_applicable",
                "pass": runtime["valid"]
                and all(row["valid"] for row in scenarios.values())
                and legacy["valid"]
                and positive_chain,
            },
            "package_local_hdl": {
                "disposition": "blocking_applicable",
                "pass": hdl["pass"] and public["valid"],
            },
            "materialized_config": {
                "disposition": "blocking_applicable_path_prefix_only",
                "pass": frozen[
                    "sca_input_install_prefix_change_mechanical_only"
                ]
                and frozen["sca_d_run_prefix_change_mechanical_only"],
                "causal_transaction_ledger": (
                    "receipt_reuse_semantics_byte_equal"
                ),
                "boundary_microtrace": "not_applicable_path_prefix_only",
                "physical_bank_row_validity": (
                    "receipt_reuse_addresses_byte_equal"
                ),
            },
            "diagnostic_semantics": {
                "disposition": "receipt_reuse_predicate_byte_equal",
                "pass": trace["valid"] and guard["valid"],
            },
            "return_result_contract": {
                "disposition": "blocking_applicable",
                "pass": all(row["valid"] for row in scenarios.values()),
            },
            "runtime_layout": {
                "disposition": "blocking_applicable",
                "pass": shared["pass"] and common["valid"],
                "rule_id": "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "semantic_version": "2",
            },
            "storage_rotation": {
                "disposition": "blocking_applicable",
                "pass": None,
                "reason": "performed after exact final-ZIP audit",
            },
            "numeric_w3_golden": {
                "disposition": "record_only",
                "pass": frozen[
                    "numeric_w3_golden_mapping_bitstream_execplan_equal"
                ],
            },
        },
        "server_action": False,
        "claim_boundary": (
            "PACKAGE_READY_NOT_RUN means local package release only. "
            "Production full-design VCS, c0 natural terminal, formal 320D, "
            "performance, E3, E4 and E5 remain unclaimed."
        ),
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
                "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
                "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
                "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            ],
            "delta": None,
        },
    }
    write_json(REPORT, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
