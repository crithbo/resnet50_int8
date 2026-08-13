#!/usr/bin/env python3
"""Changed-surface validation for the exact GAP node0071 v51 ZIP."""

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
NAME = "r5_n71_gap_v51_ga_ob_mode_factor_diag"
SOURCE_NAME = "r5_n71_gap_v50_ga_ob_conjunction_diag"
SOURCE = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
SOURCE_SHA = "96c23c3762b9fca323ff3d76250f8ca9482c74d536a93b843321c8be3f37252d"
MARKER = "    // v51: all-slice GA outbuffer mode/factor information-gain observer."
RTL = (
    ROOT / "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/"
    "GA_PE_Outbuffer.sv"
)
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
LEAVES = (
    "normal_mode_wr_req",
    "normal_mode_bp_pre",
    "normal_mode_wr_handshake",
    "transout_mode_wr_req",
    "transout_mode_bp_pre",
    "transout_mode_wr_handshake",
    "alu_op_is_transout",
    "ga_pe_outbuffer_rd_en",
)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def zip_members(path: Path, root: str) -> tuple[dict[str, bytes], dict[str, bool]]:
    members: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        roots = {
            PurePosixPath(name).parts[0] for name in names if name
        }
        checks = {
            "crc": archive.testzip() is None,
            "single_root": roots == {root},
            "path_safe": all(
                not PurePosixPath(name).is_absolute()
                and ".." not in PurePosixPath(name).parts
                and "\\" not in name
                for name in names
            ),
            "duplicate_free": len(names) == len(set(names)),
            "symlink_free": all(
                not stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)
                for info in infos
            ),
        }
        for info in infos:
            if info.is_dir():
                continue
            pure = PurePosixPath(info.filename)
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            members[relative] = archive.read(info)
    return members, checks


def run(argv: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(
        argv, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30, check=False
    )
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "stderr_sha256": sha_bytes(result.stderr.encode()),
    }


def project(extension: str) -> str:
    body = extension
    packed_monitor_decl = """\
logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`GA_ROW_PE_NUM-1:0][1:0]
          return_obs_v51_normal_req_mon,
          return_obs_v51_normal_bp_mon,
          return_obs_v51_normal_hs_mon,
          return_obs_v51_transout_req_mon,
          return_obs_v51_transout_bp_mon,
          return_obs_v51_transout_hs_mon,
          return_obs_v51_is_transout_mon,
          return_obs_v51_selected_rd_mon;"""
    unpacked_monitor_decl = """\
logic return_obs_v51_normal_req_mon [4][4][4][2];
    logic return_obs_v51_normal_bp_mon [4][4][4][2];
    logic return_obs_v51_normal_hs_mon [4][4][4][2];
    logic return_obs_v51_transout_req_mon [4][4][4][2];
    logic return_obs_v51_transout_bp_mon [4][4][4][2];
    logic return_obs_v51_transout_hs_mon [4][4][4][2];
    logic return_obs_v51_is_transout_mon [4][4][4][2];
    logic return_obs_v51_selected_rd_mon [4][4][4][2];"""
    if body.count(packed_monitor_decl) != 1:
        raise ValueError("packed v51 monitor declaration differs")
    body = body.replace(packed_monitor_decl, unpacked_monitor_decl, 1)
    for leaf in LEAVES:
        pattern = re.compile(
            r"u_NDP_Top_new\.slice_with_datahub_mc_group_gen\s*"
            r"\[return_obs_v51_g\].*?"
            r"\.u_GA_PE_Outbuffer\." + re.escape(leaf),
            re.DOTALL,
        )
        body, count = pattern.subn("1'b0", body, count=1)
        if count != 1:
            raise ValueError(f"projection XMR count differs for {leaf}: {count}")
    for old, new in (
        ("u_NDP_Top_new.clk_sg", "clk_sg"),
        ("u_NDP_Top_new.rst_n_sg", "rst_n_sg"),
        ("u_NDP_Top_new.clk_db", "clk_db"),
        ("u_NDP_Top_new.rst_n_db", "rst_n_db"),
    ):
        body = body.replace(old, new)
    return """\
`define GLB_SLICE_NUM 16
`define SLICE_GROUP_SIZE 4
`define SLICE_GROUP_NUM 4
`define GA_ROW_PE_NUM 4
`define GA_PE_OUTBUFFER_CNT_WIDTH 2
module gap_v51_changed_surface;
  logic clk_sg,clk_db,rst_n_sg,rst_n_db;
  bit return_obs_enabled;
  integer return_obs_fd;
  logic return_obs_ga_outbuffer_wr_mon [4][4][4][2];
  logic [`GA_PE_OUTBUFFER_CNT_WIDTH-1:0]
        return_obs_ga_ob_count_mon [4][4][4][2];
""" + body + "\nendmodule\n"


def compile_projection(source: str, directory: Path, label: str) -> dict[str, Any]:
    path = directory / f"{label}.sv"
    path.write_text(source, encoding="utf-8", newline="\n")
    receipt = run(
        [
            str(IVERILOG), "-g2012", "-tnull", "-s",
            "gap_v51_changed_surface", str(path)
        ],
        directory,
    )
    receipt["source_sha256"] = sha_bytes(source.encode())
    return receipt


def xmr_proof(extension: str, rtl_text: str) -> dict[str, Any]:
    rows = {}
    for leaf in LEAVES:
        use_count = len(re.findall(
            r"\.u_GA_PE_Outbuffer\." + re.escape(leaf) + r"\b", extension
        ))
        declaration = bool(re.search(
            r"\b(?:wire|reg|logic|output)\b[^;]*\b" +
            re.escape(leaf) + r"\b", rtl_text
        ))
        rows[leaf] = {
            "observer_use_count": use_count,
            "target_declaration_present": declaration,
            "pass": use_count == 1 and declaration,
        }
    typo = extension.replace(
        ".u_GA_PE_Outbuffer.normal_mode_wr_req",
        ".u_GA_PE_Outbuffer.normal_mode_wr_rex",
        1,
    )
    sibling = extension.replace(
        ".u_GA_PE_Outbuffer.normal_mode_wr_req",
        ".u_GA_PE_Inbuffer.normal_mode_wr_req",
        1,
    )
    typo_detected = (
        len(re.findall(r"\.u_GA_PE_Outbuffer\.normal_mode_wr_req\b", typo)) == 0
    )
    sibling_detected = (
        len(re.findall(
            r"\.u_GA_PE_Outbuffer\.normal_mode_wr_req\b", sibling
        )) == 0
    )
    return {
        "target_relative_path": str(RTL.relative_to(ROOT)).replace("\\", "/"),
        "target_bytes": RTL.stat().st_size,
        "target_sha256": sha(RTL),
        "rows": rows,
        "all_actual_leaves_bound": all(row["pass"] for row in rows.values()),
        "leaf_rename_negative_fail_closed": typo_detected,
        "wrong_sibling_negative_fail_closed": sibling_detected,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-zip", type=Path, required=True)
    ap.add_argument("--runner-report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()
    target = ns.target_zip.resolve()
    runner_report = json.loads(ns.runner_report.read_text(encoding="utf-8"))
    errors: list[str] = []
    members, archive_checks = zip_members(target, NAME)
    source, source_archive_checks = zip_members(SOURCE, SOURCE_NAME)
    if sha(SOURCE) != SOURCE_SHA:
        errors.append("source_sha")
    errors.extend(
        f"archive:{name}" for name, ok in archive_checks.items() if not ok
    )
    manifest = json.loads(members["TEST_PACKAGE_MANIFEST.json"].decode())
    payload = {
        name: value for name, value in members.items()
        if name != "TEST_PACKAGE_MANIFEST.json"
    }
    declared = manifest.get("files", {})
    manifest_checks = {
        "exact_set": set(declared) == set(payload),
        "receipts": all(
            declared[name]["size_bytes"] == len(data)
            and declared[name]["sha256"] == sha_bytes(data)
            for name, data in payload.items()
        ),
        "identity": manifest.get("install_name") == NAME
            and manifest.get("package_name") == f"{NAME}.zip",
        "source": manifest.get("source_package", {}).get("sha256") == SOURCE_SHA,
        "allowlist_83": len(manifest.get("return_allowlist", [])) == 83,
        "formal_d_48": len(manifest.get("readback_checks", [])) == 48,
        "repeat_contract": manifest.get("repeat_execution_contract", {}).get(
            "return_name_policy"
        ) == "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS",
        "current_rules":
            manifest["rule_receipts"]["server_package_rule_sha256"]
            == "7cf2cb4511cba04cb8a14d06473d67061deae64f602988d27053d8289c964b13"
            and manifest["rule_receipts"]["generation_index_sha256"]
            == "d4ff32f162538574a0dd48402e299fa25a11fb95074352c19fcfb007ebb77603",
    }
    errors.extend(
        f"manifest:{name}" for name, ok in manifest_checks.items() if not ok
    )
    normalized = {
        name: data.replace(NAME.encode(), SOURCE_NAME.encode())
        for name, data in members.items()
    }
    changed = sorted(
        name for name in set(source) | set(normalized)
        if source.get(name) != normalized.get(name)
    )
    expected_changed = sorted([
        "PREPARE_AND_RUN.sh",
        "README.md",
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json",
        "package_tools/gap_node0071_complete_server_runtime.py",
        "package_tools/gap_node0071_ga_ob_mode_factor_decision.py",
        "provenance/v50_to_v51_ga_ob_mode_factor.json",
        "tb_probe/native_return_observer.svh",
    ])
    freeze_checks = {
        "normalized_changed_exact_set": changed == expected_changed,
        "source_archive_safe": all(source_archive_checks.values()),
        "numeric_workload_config_golden_byte_equal": all(
            source.get(name) == normalized.get(name)
            for name in source
            if name.startswith("workload/")
        ),
        "timeout_unchanged": [
            line for line in
            normalized["PREPARE_AND_RUN.sh"].splitlines()
            if b"timeout " in line
        ] == [
            line for line in source["PREPARE_AND_RUN.sh"].splitlines()
            if b"timeout " in line
        ],
        "functional_rtl_absent": not any(
            name.startswith("rtl/") for name in members
        ),
    }
    errors.extend(
        f"freeze:{name}" for name, ok in freeze_checks.items() if not ok
    )
    observer = members["tb_probe/native_return_observer.svh"].decode()
    extension = observer[observer.index(MARKER):]
    semantics = {
        "qualified_owner": "always @(posedge u_NDP_Top_new.clk_sg" in extension,
        "reporter_owner": "always @(posedge u_NDP_Top_new.clk_db" in extension,
        "qualified_limit": (
            "qualified_changed &&\n"
            "                 return_obs_v51_emit_count < 128"
        ) in extension,
        "heartbeat_outside_qualified_budget":
            "|| heartbeat" in extension
            and "if (qualified_changed)\n"
                "                    return_obs_v51_emit_count++;" in extension,
        "stable_not_progress":
            '(qualified_changed ? "QUALIFIED_EDGE" : "HEARTBEAT")' in extension,
        "selected_write_update":
            "if (selected_wr)\n"
            "                        return_obs_v51_selected_wr_seen[id] <= 1'b1;"
            in extension,
        "selected_read_update":
            "if (selected_rd)\n"
            "                        return_obs_v51_selected_rd_seen[id] <= 1'b1;"
            in extension,
    }
    errors.extend(
        f"semantics:{name}" for name, ok in semantics.items() if not ok
    )
    rtl_text = RTL.read_text(encoding="utf-8")
    xmr = xmr_proof(extension, rtl_text)
    if not all((
        xmr["all_actual_leaves_bound"],
        xmr["leaf_rename_negative_fail_closed"],
        xmr["wrong_sibling_negative_fail_closed"],
    )):
        errors.append("xmr_proof")
    with tempfile.TemporaryDirectory(prefix="gap-v51-hdl-") as temporary:
        directory = Path(temporary)
        projected = project(extension)
        positive = compile_projection(projected, directory, "positive")
        delete_decl = compile_projection(
            projected.replace(
                "  logic [`GLB_SLICE_NUM-1:0] return_obs_v51_alu_req_seen;\n",
                "", 1
            ),
            directory, "delete_declaration"
        )
        typo_use = compile_projection(
            projected.replace(
                "return_obs_v51_alu_req_seen[id] <= 1'b1;",
                "return_obs_v51_alu_req_seex[id] <= 1'b1;", 1
            ),
            directory, "typo_use"
        )
    hdl = {
        "tool": str(IVERILOG),
        "positive": positive,
        "delete_declaration": delete_decl,
        "typo_use": typo_use,
        "checks": {
            "positive_exit_zero": positive["exit_code"] == 0,
            "delete_declaration_exit_nonzero":
                delete_decl["exit_code"] != 0,
            "typo_use_exit_nonzero": typo_use["exit_code"] != 0,
        },
        "claim_boundary": (
            "Exact changed observer syntax after XMR RHS projection plus "
            "separate exact current-RTL leaf/path binding; not full-design "
            "elaboration or production simulation."
        ),
    }
    errors.extend(
        f"hdl:{name}" for name, ok in hdl["checks"].items() if not ok
    )
    with tempfile.TemporaryDirectory(prefix="gap-v51-parser-") as temporary:
        parser_path = Path(temporary) / "parser.py"
        output_path = Path(temporary) / "selftest.json"
        parser_path.write_bytes(
            members[
                "package_tools/gap_node0071_ga_ob_mode_factor_decision.py"
            ]
        )
        predicate = run(
            [
                str(ROOT / (
                    "C:/never"
                )) if False else
                str(Path(__import__("sys").executable)),
                str(parser_path), "self-test", "--output", str(output_path)
            ],
            Path(temporary),
        )
        predicate_payload = (
            json.loads(output_path.read_text(encoding="utf-8"))
            if output_path.is_file() else {}
        )
    predicate["payload"] = predicate_payload
    predicate["all_checks_true"] = (
        predicate["exit_code"] == 0
        and predicate_payload.get("pass") is True
        and all(predicate_payload.get("checks", {}).values())
    )
    if not predicate["all_checks_true"]:
        errors.append("predicate_trace")
    runner = members["PREPARE_AND_RUN.sh"].decode()
    canonical_index = runner.index(
        'package_root="$(cd "$package_root" && pwd -P)"'
    )
    rebound_index = runner.index(
        'stage_tool="$package_root/package_tools/'
        'gap_node0071_stage_transition_decision.py"',
        canonical_index,
    )
    runner_checks = {
        "absolute_rebind_after_canonicalization":
            rebound_index > canonical_index,
        "new_parser_rebound":
            'gaobmode_tool="$package_root/package_tools/'
            'gap_node0071_ga_ob_mode_factor_decision.py"' in
            runner[canonical_index:],
        "unique_return":
            'return_tag="r$(date -u +%s%N)_$$"' in runner,
        "runner_harness_valid":
            runner_report.get("valid") is True
            and runner_report.get("errors") == [],
        "normal_parser_status_zero":
            runner_report["checks"].get(
                "normal_all_decision_parsers_exit_zero"
            ) is True,
        "normal_parser_stderr_empty":
            runner_report["checks"].get(
                "normal_decision_parser_stderr_empty"
            ) is True,
    }
    errors.extend(
        f"runner:{name}" for name, ok in runner_checks.items() if not ok
    )
    result = {
        "schema": "gap-node0071-v51-family-validation-v1",
        "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "target_zip": str(target.relative_to(ROOT)).replace("\\", "/"),
        "target_zip_bytes": target.stat().st_size,
        "target_zip_sha256": sha(target),
        "archive_checks": archive_checks,
        "manifest_checks": manifest_checks,
        "freeze_checks": freeze_checks,
        "normalized_changed_members": changed,
        "observer_semantics": semantics,
        "xmr_proof": xmr,
        "hdl_scope": hdl,
        "predicate_trace": predicate,
        "runner_checks": runner_checks,
        "errors": errors,
        "valid": not errors,
        "claim_boundary": (
            "Exact final package-local changed surfaces and frozen-byte "
            "receipts only; no DUT/server run, natural terminal, formal D, "
            "E3, E4, or E5 claim."
        ),
    }
    write_json(ns.output, result)
    print(json.dumps({
        "output": str(ns.output),
        "sha256": sha(ns.output),
        "valid": not errors,
        "errors": errors,
    }))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
