#!/usr/bin/env python3
"""Independent final-ZIP audit for the node0071 -> node0075 v4 package."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_n71_n75_e1f_native_v4"
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / NAME
)
ZIP_PATH = PACKAGE_ROOT.with_suffix(".zip")
SIDECAR = Path(str(ZIP_PATH) + ".sha256")
BUILD_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-ordering-package-v4/"
    "build_report.json"
)
DEFAULT_OUTPUT = BUILD_REPORT.parent / "final_zip_self_audit.json"
V3_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_n75_e1f_native_v3.zip"
)
V3_RETURN_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-ordering-v3-return-analysis/"
    "report.json"
)
CURRENT_TB = ROOT / "NDP_copy01/tb_NDP_Top_new_phy.sv"
CURRENT_TOP = ROOT / "NDP_copy01/rtl/NDP_Top_phy.sv"
CURRENT_TOP_FILELIST = (
    ROOT / "NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f"
)
CURRENT_CLK_FREQ = ROOT / "NDP_copy01/rtl/clk_freq_new.sv"
OBSERVER_REL = "obs/native_return_observer.svh"
RUNTIME_REL = "pkg/runtime.py"
RUNNER_REL = "PREPARE_AND_RUN.sh"
MANIFEST_REL = "TEST_PACKAGE_MANIFEST.json"
CURRENT_RECEIPTS = {
    ".agents/agent.md":
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
    ".agents/rules/生成前必读索引.md":
        "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2",
    ".agents/rules/算子配置规则.md":
        "8eb7a4c6759a5517e7218f6aab9e9ebb89052f898b790e5b6f4adfab622e6497",
    ".agents/rules/NDP硬件字段语义.md":
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ".agents/rules/服务器测试包生成规则.md":
        "da0e2dc8dab9a64d4eaca3f15ee0634b3af6b299dfa505e192d6b6bf30ff12b8",
    ".agents/rules/INT8_SA点积专项规则.md":
        "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
    ".agents/rules/精确UINT8量化尾专项规则.md":
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md":
        "e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba",
}
BITS128 = re.compile(rb"[01]{128}")


class AuditError(RuntimeError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


def read_zip(path: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    entries: dict[str, bytes] = {}
    roots: set[str] = set()
    unsafe: list[str] = []
    duplicates: list[str] = []
    symlinks: list[str] = []
    with zipfile.ZipFile(path) as archive:
        crc_error = archive.testzip()
        seen: set[str] = set()
        for info in archive.infolist():
            raw = info.filename
            pure = PurePosixPath(raw)
            windows = PureWindowsPath(raw)
            if pure.parts:
                roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or windows.is_absolute()
                or bool(windows.anchor)
                or "\\" in raw
                or ".." in pure.parts
            ):
                unsafe.append(raw)
            if mode and stat.S_ISLNK(mode):
                symlinks.append(raw)
            if raw in seen:
                duplicates.append(raw)
            seen.add(raw)
            if info.is_dir():
                continue
            if not raw.startswith(f"{NAME}/"):
                unsafe.append(raw)
                continue
            relative = pure.relative_to(NAME).as_posix()
            entries[relative] = archive.read(info)
    receipt = {
        "crc_valid": crc_error is None,
        "single_root": roots == {NAME},
        "path_safe": not unsafe,
        "duplicate_free": not duplicates,
        "symlink_free": not symlinks,
        "roots": sorted(roots),
        "unsafe": unsafe,
        "duplicates": duplicates,
        "symlinks": symlinks,
        "file_count": len(entries),
    }
    return entries, receipt


def record_map(entries: dict[str, bytes], exclude: set[str]) -> list[dict[str, Any]]:
    return [
        {
            "path": path,
            "size_bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }
        for path, payload in sorted(entries.items())
        if path not in exclude
    ]


def tree_records(root: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]


def run_python(runtime: Path, arguments: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-B", str(runtime), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(result.stdout)
    except Exception:
        pass
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-4000:],
        "parsed": parsed,
    }


def execplan_receipt(package: Path) -> dict[str, Any]:
    path = package / "workload/ep.txt"
    lines = path.read_bytes().splitlines()
    abi = bool(lines) and all(BITS128.fullmatch(line) for line in lines)
    chunks = [
        line[offset : offset + 32]
        for line in lines
        for offset in range(0, 128, 32)
    ]
    return {
        "line_count": len(lines),
        "abi_128bit": abi,
        "start_comp_count": sum(chunk.endswith(b"101") for chunk in chunks),
        "opcode110_slot_count": sum(chunk.endswith(b"110") for chunk in chunks),
        "producer_prefix_lines": 13,
        "consumer_suffix_lines": len(lines) - 13,
        "inserted_boundary_lines": 0,
        "valid": (
            abi
            and len(lines) == 518
            and sum(chunk.endswith(b"101") for chunk in chunks) == 32
            and sum(chunk.endswith(b"110") for chunk in chunks) == 8
        ),
    }


def sca_receipt(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    sca = json.loads((package / "workload/sca_cfg.json").read_text("utf-8"))
    sca_d = json.loads(
        (package / "workload/sca_cfg_D.json").read_text("utf-8")
    )
    dynamic = {
        key: value
        for key, value in sca.items()
        if key not in {"Exec_Base", "Exec_Length", "Repeat_Num", "ExecutionPlan"}
    }
    inputs = [key for key in dynamic if key.startswith("n71_i")]
    configs = [key for key in dynamic if key.endswith("_cfg")]
    b_items = [key for key in dynamic if key.startswith("n75_b")]
    a_preloads = [
        key for key in dynamic
        if "matrixa" in key.lower()
        or key.lower().startswith("n75_a_preload")
    ]
    runtime_paths = {str(item["path"]) for item in sca_d.values()}
    readback_paths = {
        str(item["runtime_path"]) for item in manifest["readback_checks"]
    }
    preseeded = [
        raw for raw in runtime_paths
        if (package / Path(*PurePosixPath(raw).parts)).exists()
    ]
    return {
        "external_input_count": len(inputs),
        "config_count": len(configs),
        "b_destination_count": len(b_items),
        "a_preload_count": len(a_preloads),
        "formal_d_count": len(sca_d),
        "formal_d_runtime_preseed_count": len(preseeded),
        "sca_d_readback_contract_exact": runtime_paths == readback_paths,
        "single_execplan": "ExecutionPlan" in sca,
        "valid": (
            len(inputs) == 16
            and len(configs) == 32
            and len(b_items) == 128
            and not a_preloads
            and len(sca_d) == 144
            and not preseeded
            and runtime_paths == readback_paths
            and sca.get("Exec_Length") == 518
            and sca.get("Repeat_Num") == 32
        ),
    }


def path_contract(
    paths: set[str],
    manifest: dict[str, Any],
    runner: str,
    *,
    require_references: bool = True,
) -> bool:
    budget = manifest["path_length_budget"]
    if not paths:
        return False
    if max(map(len, paths)) > int(budget["max_inner_suffix_chars"]):
        return False
    if max(path.count("/") + 1 for path in paths) > int(
        budget["max_inner_depth"]
    ):
        return False
    if any(path.count(NAME) for path in paths):
        return False
    projected = (
        int(budget["declared_target_root_max_chars"])
        + 1 + len(NAME) + 1 + max(map(len, paths))
    )
    if projected > int(budget["max_projected_absolute_path_chars"]):
        return False
    if require_references:
        observer = manifest["observer"]["path"]
        if observer not in paths:
            return False
        if (
            f"+incdir+$package_root/{PurePosixPath(observer).parent.as_posix()}"
            not in runner
        ):
            return False
        for item in manifest["files"]:
            if item["path"] not in paths:
                return False
    return True


def runner_binding(
    manifest: dict[str, Any],
    runner: str,
    runtime: str,
    observer: str,
    paths: set[str],
) -> dict[str, Any]:
    allowlist_destinations = {
        str(item.get("destination"))
        for item in manifest.get("return_allowlist", {}).get("records", [])
        if isinstance(item, dict)
    }
    source = (
        manifest["observer"]["path"] in paths
        and manifest["observer"]["sha256"]
        == sha256_bytes(observer.encode("utf-8"))
    )
    include = "+incdir+$package_root/obs" in runner
    macro = "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner
    runtime_return = all(
        token in runner
        for token in (
            "+RETURN_OBSERVER",
            "+N75_NATIVE_ORDERING",
            "+N75_A_EVENT_LIMIT=9000",
            "+RETURN_OBS_FILE=$observer_log",
        )
    ) and (
        "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1" in runtime
        and "log/return_observer.log" in allowlist_destinations
        and "e/observer_binding.txt" in allowlist_destinations
        and "_return_allowlist_records(manifest)" in runtime
    )
    no_server_source_preflight = not any(
        token in runner
        for token in (
            "git rev-parse",
            "README_HARDWARE_SIM_ENTRY",
            "NDP_Top_phy_filelist",
            "tb_NDP_Top_new_phy.sv",
        )
    )
    valid = source and include and macro and runtime_return
    negatives = {
        "delete_source": not runner_binding_positive(
            {
                **manifest,
                "observer": {
                    **manifest["observer"],
                    "path": "obs/missing_observer.svh",
                },
            },
            runner,
            runtime,
            observer,
            paths,
        ),
        "delete_incdir": not runner_binding_positive(
            manifest,
            runner.replace("+incdir+$package_root/obs", ""),
            runtime,
            observer,
            paths,
        ),
        "delete_macro": not runner_binding_positive(
            manifest,
            runner.replace("+define+NATIVE_RETURN_OBSERVER_ENABLE", ""),
            runtime,
            observer,
            paths,
        ),
        "delete_runtime_return": not runner_binding_positive(
            manifest,
            runner.replace("+RETURN_OBS_FILE=$observer_log", ""),
            runtime,
            observer,
            paths,
        ),
    }
    return {
        "source": source,
        "include": include,
        "compile_enable": macro,
        "runtime_return": runtime_return,
        "no_server_source_preflight": no_server_source_preflight,
        "positive_only": valid,
        "negative_controls": negatives,
        "valid": valid and no_server_source_preflight and all(negatives.values()),
    }


def runner_binding_positive(
    manifest: dict[str, Any],
    runner: str,
    runtime: str,
    observer: str,
    paths: set[str],
) -> bool:
    allowlist_destinations = {
        str(item.get("destination"))
        for item in manifest.get("return_allowlist", {}).get("records", [])
        if isinstance(item, dict)
    }
    return (
        manifest["observer"]["path"] in paths
        and manifest["observer"]["sha256"]
        == sha256_bytes(observer.encode("utf-8"))
        and "+incdir+$package_root/obs" in runner
        and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner
        and all(
            token in runner
            for token in (
                "+RETURN_OBSERVER",
                "+N75_NATIVE_ORDERING",
                "+N75_A_EVENT_LIMIT=9000",
                "+RETURN_OBS_FILE=$observer_log",
            )
        )
        and "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1"
        in runtime
        and "log/return_observer.log" in allowlist_destinations
        and "e/observer_binding.txt" in allowlist_destinations
        and "_return_allowlist_records(manifest)" in runtime
    )


def feature_contract_valid(
    manifest: dict[str, Any],
    runner: str,
    observer: str,
    runtime: str,
) -> bool:
    feature = manifest.get("diagnostic_feature", {})
    allowlist_destinations = {
        str(item.get("destination"))
        for item in manifest.get("return_allowlist", {}).get("records", [])
        if isinstance(item, dict)
    }
    return (
        feature.get("name") == "NATIVE_ORDERING"
        and feature.get("runtime_enable") == "+N75_NATIVE_ORDERING"
        and feature.get("event_limit_argument") == "+N75_A_EVENT_LIMIT=9000"
        and feature.get("event_limit") == 9000
        and feature.get("binding_receipt") == "e/observer_binding.txt"
        and feature.get("event_schema") == "N75_A_REQ_V1"
        and feature.get("canonical_schema") == "N75_CANONICAL_DECISION_V2"
        and feature.get("return_log_target") == "log/return_observer.log"
        and "+N75_NATIVE_ORDERING" in runner
        and "+N75_A_EVENT_LIMIT=9000" in runner
        and feature.get("time0_marker") in observer
        and feature.get("return_log_target") in allowlist_destinations
        and feature.get("binding_receipt") in allowlist_destinations
        and "_return_allowlist_records(manifest)" in runtime
    )


def feature_gate(
    manifest: dict[str, Any],
    runner: str,
    observer: str,
    runtime: str,
) -> dict[str, Any]:
    positive = feature_contract_valid(manifest, runner, observer, runtime)
    controls = {
        "delete_enable": not feature_contract_valid(
            manifest,
            runner.replace("+N75_NATIVE_ORDERING", "+REMOVED_NATIVE_ORDERING"),
            observer,
            runtime,
        ),
        "change_limit": not feature_contract_valid(
            manifest,
            runner.replace(
                "+N75_A_EVENT_LIMIT=9000", "+N75_A_EVENT_LIMIT=8191"
            ),
            observer,
            runtime,
        ),
        "delete_time0_marker": not feature_contract_valid(
            {
                **manifest,
                "diagnostic_feature": {
                    **manifest["diagnostic_feature"],
                    "time0_marker": "REMOVED_TIME0_MARKER",
                },
            },
            runner,
            observer,
            runtime,
        ),
        "delete_return_target": not feature_contract_valid(
            {
                **manifest,
                "return_allowlist": {
                    **manifest["return_allowlist"],
                    "records": [
                        item
                        for item in manifest["return_allowlist"]["records"]
                        if item.get("destination") != "log/return_observer.log"
                    ],
                },
            },
            runner,
            observer,
            runtime,
        ),
    }
    return {
        "positive": positive,
        "negative_controls": controls,
        "valid": positive and all(controls.values()),
    }


def specialize_external_xmr(source: str) -> tuple[str, dict[str, Any]]:
    begin = source.index("    generate\n")
    end = source.index("    endgenerate\n", begin) + len("    endgenerate\n")
    original = source[begin:end]
    replacement = """    // Focused audit specialization: external DUT/XMR only.
    assign n75_obs_cfg_start_mon = '0;
    assign n75_obs_cfg_finish_mon = '0;
    assign n75_obs_exec_start_mon = '0;
    assign n75_obs_slice_finish_mon = '0;
    assign n75_obs_a_req_hs_mon = '0;
    assign n75_obs_a_req_addr_mon = '0;
    assign n75_obs_a_data_hs_mon = '0;
    assign n75_obs_d_req_hs_mon = '0;
    assign n75_obs_d_wdata_hs_mon = '0;
"""
    specialized = source[:begin] + replacement + source[end:]
    clock_reset_replacements = {
        "u_NDP_Top_new.clk_sg": "n75_focus_clk_sg",
        "u_NDP_Top_new.rst_n_sg": "n75_focus_rst_n_sg",
    }
    clock_reset_counts = {
        original: specialized.count(original)
        for original in clock_reset_replacements
    }
    for original, replacement_name in clock_reset_replacements.items():
        specialized = specialized.replace(original, replacement_name)
    void_spans = re.findall(
        r"void'\(\$value\$plusargs\((.*?)\)\);",
        specialized,
        re.S,
    )
    specialized = re.sub(
        r"void'\(\$value\$plusargs\((.*?)\)\);",
        r"if ($value$plusargs(\1)) begin end",
        specialized,
        flags=re.S,
    )
    runtime_selectors = (
        "[n75_obs_group_i]",
        "[n75_obs_slice_i]",
        "[n75_obs_channel_i]",
    )
    selector_counts = {
        selector: specialized.count(selector)
        for selector in runtime_selectors
    }
    for selector in runtime_selectors:
        specialized = specialized.replace(selector, "[0]")
    return specialized, {
        "original_span_sha256": sha256_bytes(original.encode("utf-8")),
        "specialized_span_sha256": sha256_bytes(replacement.encode("utf-8")),
        "reason": "local frontend has no full DUT hierarchy; only external XMR continuous assignments are specialized",
        "target_declarations_updates_consumers_modified": False,
        "frontend_void_cast_specialization_count": len(void_spans),
        "frontend_void_cast_specialization": (
            "Icarus-only syntax adaptation preserves each $value$plusargs "
            "call and state target while replacing the unsupported discarded "
            "void cast with an empty true branch"
        ),
        "frontend_packed_runtime_selector_specializations": selector_counts,
        "frontend_packed_runtime_selector_boundary": (
            "Icarus-only packed-array elaboration specialization replaces "
            "runtime monitor indices with element zero; exact counter/state "
            "declarations, assignments and canonical consumers are retained"
        ),
        "frontend_clock_reset_xmr_specializations": clock_reset_counts,
        "frontend_clock_reset_xmr_boundary": (
            "The focused package-local syntax harness substitutes the two "
            "external TB/DUT clock-reset XMR consumers. Their actual hierarchy "
            "is independently closed by xmr_target_proof against current TB, "
            "top-module and filelist bytes; this focused wrapper is not used "
            "as XMR existence evidence."
        ),
    }


def focus_prefix() -> str:
    return """`timescale 1ns/1ps
`define SLICE_GROUP_SIZE 14
`define SLICE_GROUP_NUM 2
`define MSE_REQ_CHL_NUM 2
`define MSE_MEM_REQ_ADDR_WIDTH 26
module n75_observer_focus;
logic n75_focus_clk_sg;
logic n75_focus_rst_n_sg;
"""


def compile_focus(iverilog: Path, root: Path, name: str, source: str) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    command = [
        str(iverilog),
        "-g2012",
        "-s",
        "n75_observer_focus",
        "-o",
        str(output_path),
        str(source_path),
    ]
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(root),
        "exit_code": result.returncode,
        "stdout": result.stdout[-2000:],
        "stderr": result.stderr[-4000:],
        "source_sha256": sha256(source_path),
    }


def consumer_expressions(source: str) -> list[dict[str, Any]]:
    final_begin = source.index("    final begin : N75_OBS_FINAL")
    final_text = source[final_begin:]
    expressions: list[tuple[str, int, str]] = []
    outer = re.search(
        r"if\s*\((n75_obs_enabled.*?n75_obs_fd\s*!=\s*0)\)\s*begin",
        final_text,
        re.S,
    )
    success = re.search(
        r"if\s*\((n75_obs_all_slices_finished.*?!n75_obs_stall_reported)\)\s*begin",
        final_text,
        re.S,
    )
    if outer is None or success is None:
        raise AuditError("canonical consumer gates not found")
    expressions.append(
        ("final_output_gate", final_begin + outer.start(1), outer.group(1))
    )
    expressions.append(
        ("success_gate", final_begin + success.start(1), success.group(1))
    )
    displays = list(
        re.finditer(r"\$fdisplay\s*\((.*?)\)\s*;", final_text, re.S)
    )
    for index, match in enumerate(displays[-3:]):
        expressions.append(
            (
                f"canonical_record_{index}",
                final_begin + match.start(1),
                match.group(1),
            )
        )
    records = []
    for role, start, expression in expressions:
        identifiers = sorted(
            set(re.findall(r"\bn75_obs_[A-Za-z0-9_]+\b", expression))
        )
        records.append(
            {
                "role": role,
                "start_byte": len(source[:start].encode("utf-8")),
                "end_byte": len(source[: start + len(expression)].encode("utf-8")),
                "start_line": source.count("\n", 0, start) + 1,
                "expression_sha256": sha256_bytes(expression.encode("utf-8")),
                "identifiers": identifiers,
                "_start_char": start,
                "_text": expression,
            }
        )
    return records


def closure(source: str) -> dict[str, Any]:
    expressions = consumer_expressions(source)
    identifiers = sorted(
        {
            identifier
            for item in expressions
            for identifier in item["identifiers"]
        }
    )
    setup = {
        "n75_obs_enabled",
        "n75_obs_feature_enabled",
        "n75_obs_fd",
    }
    final_local = {"n75_obs_all_slices_finished"}
    initial_begin = source.index("    initial begin : N75_OBS_INITIALIZE")
    always_begin = source.index(
        "    always @(posedge u_NDP_Top_new.clk_sg)"
    )
    final_begin = source.index("    final begin : N75_OBS_FINAL")
    initial_text = source[initial_begin:always_begin]
    update_text = source[always_begin:final_begin]
    final_text = source[final_begin:]
    leaves = []
    for identifier in identifiers:
        declaration = re.search(
            rf"\b(?:bit|integer|longint\s+unsigned|string)\s+{re.escape(identifier)}\b",
            source,
        )
        initialized = bool(
            re.search(rf"\b{re.escape(identifier)}(?:\s*\[[^\]]+\])?\s*=", initial_text)
        )
        if identifier in final_local:
            initialized = bool(
                re.search(rf"\b{re.escape(identifier)}\s*=", final_text)
            )
        updated = (
            True if identifier in setup else bool(
                re.search(
                    rf"\b{re.escape(identifier)}(?:\s*\[[^\]]+\])?\s*=",
                    update_text if identifier not in final_local else final_text,
                )
            )
        )
        uses = [
            item["role"]
            for item in expressions
            if identifier in item["identifiers"]
        ]
        leaves.append(
            {
                "identifier": identifier,
                "declared": declaration is not None,
                "initialized": initialized,
                "qualified_update_or_setup": updated,
                "actual_consumer_roles": uses,
                "owner_role": (
                    "feature_setup" if identifier in setup
                    else "final_derived_state" if identifier in final_local
                    else "qualified_observer_state"
                ),
            }
        )
    valid = bool(expressions) and all(
        leaf["declared"]
        and leaf["initialized"]
        and leaf["qualified_update_or_setup"]
        and leaf["actual_consumer_roles"]
        for leaf in leaves
    )
    return {
        "scope": "exact final-ZIP canonical/result decision consumers",
        "consumer_expressions": [
            {key: value for key, value in item.items() if not key.startswith("_")}
            for item in expressions
        ],
        "consumer_expression_count": len(expressions),
        "unique_identifier_count": len(identifiers),
        "uncovered_count": sum(
            not leaf["actual_consumer_roles"] for leaf in leaves
        ),
        "leaves": leaves,
        "valid": valid,
    }


def _clock_reset_xmr_resolves(
    observer: str,
    tb_source: str,
    top_source: str,
    filelist_source: str,
) -> bool:
    return (
        "always @(posedge u_NDP_Top_new.clk_sg)" in observer
        and "u_NDP_Top_new.rst_n_sg" in observer
        and re.search(
            r"\bNDP_Top_new_phy\s+u_NDP_Top_new\s*\(", tb_source
        ) is not None
        and re.search(r"^\s*wire\s+clk_sg\s*;\s*$", top_source, re.M)
        is not None
        and re.search(
            r"^\s*wire\s+rst_n_sg\s*=\s*rst_n\s*;\s*$",
            top_source,
            re.M,
        ) is not None
        and "../NDP_Top_phy.sv" in filelist_source
        and "../clk_freq_new.sv" in filelist_source
    )


def xmr_target_proof(source: str) -> dict[str, Any]:
    tb_source = CURRENT_TB.read_text(encoding="utf-8")
    top_source = CURRENT_TOP.read_text(encoding="utf-8")
    filelist_source = CURRENT_TOP_FILELIST.read_text(encoding="utf-8")
    clock_source = CURRENT_CLK_FREQ.read_text(encoding="utf-8")
    positive = _clock_reset_xmr_resolves(
        source, tb_source, top_source, filelist_source
    )
    delete_leaf_top = re.sub(
        r"^\s*wire\s+clk_sg\s*;\s*$", "", top_source, count=1, flags=re.M
    )
    rename_leaf_top = top_source.replace(
        "wire rst_n_sg = rst_n;", "wire rst_n_sg_RENAMED = rst_n;", 1
    )
    wrong_sibling = source.replace(
        "u_NDP_Top_new.clk_sg", "u_NDP_Top_new_WRONG.clk_sg", 1
    )
    controls = {
        "delete_target_leaf_fail_closed": not _clock_reset_xmr_resolves(
            source, tb_source, delete_leaf_top, filelist_source
        ),
        "rename_target_leaf_fail_closed": not _clock_reset_xmr_resolves(
            source, tb_source, rename_leaf_top, filelist_source
        ),
        "wrong_sibling_path_fail_closed": not _clock_reset_xmr_resolves(
            wrong_sibling, tb_source, top_source, filelist_source
        ),
    }
    existing_tb_consumers = {
        "clk_sg": tb_source.count("u_NDP_Top_new.clk_sg"),
        "rst_n_sg": tb_source.count("u_NDP_Top_new.rst_n_sg"),
    }
    return_report = json.loads(
        V3_RETURN_ANALYSIS.read_text(encoding="utf-8")
    )
    actual_v3_failure = return_report["return_analysis"]["exact_leafs"]
    v3_escape_reproduced = (
        set(actual_v3_failure) == {"clk_sg", "rst_n_sg"}
        and "always @(posedge clk_sg)" not in source
        and re.search(r"(?<!\.)\brst_n_sg\)", source) is None
    )
    valid = (
        positive
        and existing_tb_consumers["clk_sg"] >= 2
        and existing_tb_consumers["rst_n_sg"] >= 2
        and "output logic clk_sg_out" in clock_source
        and ".clk_sg_out  (clk_sg)" in top_source
        and all(controls.values())
        and v3_escape_reproduced
    )
    return {
        "rule_id": "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
        "decision": "PRIVATE_XMR_REQUIRED_NO_EQUIVALENT_PUBLIC_SG_CLOCK",
        "reason": (
            "TB public clk is the DB-domain input while exact current "
            "clk_freq_new generates a distinct SG-domain clock; sampling the "
            "accepted SG handshakes on DB clk would change event semantics."
        ),
        "actual_consumers": [
            {
                "expression": "u_NDP_Top_new.clk_sg",
                "target_module": "NDP_Top_new_phy",
                "leaf": "clk_sg",
                "width_bits": 1,
                "type": "wire",
                "owner_clock": "clk_freq.clk_sg_out",
            },
            {
                "expression": "u_NDP_Top_new.rst_n_sg",
                "target_module": "NDP_Top_new_phy",
                "leaf": "rst_n_sg",
                "width_bits": 1,
                "type": "wire",
                "owner_clock": "SG domain",
                "reset_source": "NDP_Top_new_phy.rst_n",
            },
        ],
        "identity": {
            "tb_path": str(CURRENT_TB.relative_to(ROOT)),
            "tb_sha256": sha256(CURRENT_TB),
            "top_path": str(CURRENT_TOP.relative_to(ROOT)),
            "top_sha256": sha256(CURRENT_TOP),
            "filelist_path": str(CURRENT_TOP_FILELIST.relative_to(ROOT)),
            "filelist_sha256": sha256(CURRENT_TOP_FILELIST),
            "clock_source_path": str(CURRENT_CLK_FREQ.relative_to(ROOT)),
            "clock_source_sha256": sha256(CURRENT_CLK_FREQ),
            "instance_path": "tb_NDP_Top_new_phy.u_NDP_Top_new",
        },
        "same_path_existing_tb_consumer_counts": existing_tb_consumers,
        "production_vcs_regression": {
            "v3_return_analysis_sha256": sha256(V3_RETURN_ANALYSIS),
            "v3_exact_failure_was_bare_scope_only": v3_escape_reproduced,
            "claim": (
                "The returned VCS compile parsed existing current-TB uses of "
                "these exact hierarchy leaves and failed only when the v3 "
                "observer used the two unqualified bare identifiers."
            ),
        },
        "negative_controls": controls,
        "focused_wrapper_is_not_xmr_proof": True,
        "pass": valid,
    }


def hdl_gate(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    observer_path = package / OBSERVER_REL
    source = observer_path.read_text(encoding="utf-8")
    specialized, specialization = specialize_external_xmr(source)
    focused = focus_prefix() + specialized + "\nendmodule\n"
    iverilog_name = shutil.which("iverilog")
    if not iverilog_name:
        raise AuditError("iverilog unavailable")
    iverilog = Path(iverilog_name)
    exact_closure = closure(source)
    xmr = xmr_target_proof(source)
    expressions = consumer_expressions(source)
    identifiers = sorted(
        {
            identifier
            for item in expressions
            for identifier in item["identifiers"]
        }
    )
    xmr_instance_selectors = re.findall(
        r"(?:slice_with_datahub_mc_group_gen|slice_group_gen|MSE_INST)\s*\[([^\]]+)\]",
        source,
    )
    xmr_constant = bool(xmr_instance_selectors) and all(
        selector.strip() in {
            "n75_obs_group",
            "n75_obs_slice",
            "1",
        }
        for selector in xmr_instance_selectors
    )
    with tempfile.TemporaryDirectory(prefix="n71n75-hdl-final-") as temporary:
        root = Path(temporary)
        positive = compile_focus(iverilog, root, "positive", focused)
        delete_identifier = "n75_obs_first_a_order_ok"
        deleted_source = re.sub(
            rf"^\s*bit\s+{delete_identifier}\s*;\s*$",
            "",
            source,
            count=1,
            flags=re.M,
        )
        deleted_focused = (
            focus_prefix()
            + specialize_external_xmr(deleted_source)[0]
            + "\nendmodule\n"
        )
        delete_declaration = compile_focus(
            iverilog, root, "negative_delete_declaration", deleted_focused
        )
        success = next(
            item for item in expressions if item["role"] == "success_gate"
        )
        typo_at = success["_start_char"] + success["_text"].index(delete_identifier)
        typo_source = (
            source[:typo_at]
            + delete_identifier
            + "_TYPO"
            + source[typo_at + len(delete_identifier) :]
        )
        typo_focused = (
            focus_prefix()
            + specialize_external_xmr(typo_source)[0]
            + "\nendmodule\n"
        )
        misspell_consumer = compile_focus(
            iverilog, root, "negative_misspell_consumer", typo_focused
        )
        no_init_source = source.replace(
            "        n75_obs_first_a_order_ok = 1'b0;\n", "", 1
        )
        delete_initialization_closure = closure(no_init_source)
        per_identifier = []
        for mutation_index, identifier in enumerate(identifiers):
            expression = next(
                item for item in expressions
                if identifier in item["identifiers"]
            )
            char_index = (
                expression["_start_char"]
                + expression["_text"].index(identifier)
            )
            mutated = (
                source[:char_index]
                + identifier + "_ACTUAL_CONSUMER_TYPO"
                + source[char_index + len(identifier) :]
            )
            mutated_focused = (
                focus_prefix()
                + specialize_external_xmr(mutated)[0]
                + "\nendmodule\n"
            )
            result = compile_focus(
                iverilog,
                root,
                f"consumer_mutation_{mutation_index:02d}",
                mutated_focused,
            )
            per_identifier.append(
                {
                    "identifier": identifier,
                    "consumer_role": expression["role"],
                    "expression_sha256": expression["expression_sha256"],
                    "compile_exit_code": result["exit_code"],
                    "failed_closed": result["exit_code"] != 0,
                }
            )
    controls = {
        "delete_declaration_fail_closed": delete_declaration["exit_code"] != 0,
        "misspell_consumer_use_fail_closed": misspell_consumer["exit_code"] != 0,
        "delete_reset_or_update_fail_closed":
            not delete_initialization_closure["valid"],
        "all_actual_consumer_equivalence_classes_fail_closed":
            all(item["failed_closed"] for item in per_identifier),
    }
    version = subprocess.run(
        [str(iverilog), "-V"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    valid = (
        positive["exit_code"] == 0
        and exact_closure["valid"]
        and exact_closure["uncovered_count"] == 0
        and xmr_constant
        and xmr["pass"]
        and all(controls.values())
    )
    return {
        "applicable": True,
        "rule_ids": [
            "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
            "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
        ],
        "exact_members": [
            {
                "path": f"{NAME}/{OBSERVER_REL}",
                "bytes": observer_path.stat().st_size,
                "sha256": sha256(observer_path),
                "role": "package-local read-only observer",
            }
        ],
        "include_or_concatenation_order_sha256": canonical_sha256(
            [OBSERVER_REL]
        ),
        "frontend": {
            "name": "Icarus Verilog",
            "version": (version.stdout + version.stderr).splitlines()[:3],
            "command": positive["command"],
            "cwd": positive["cwd"],
            "exit": positive["exit_code"],
            "coverage": "focused",
        },
        "focused_harness_sha256": sha256_bytes(focused.encode("utf-8")),
        "specializations": [specialization],
        "xmr_instance_selectors": xmr_instance_selectors,
        "xmr_elaboration_constant": xmr_constant,
        "xmr_target_proof": xmr,
        "closure": exact_closure,
        "actual_consumer_coverage": {
            "unique_count": len(per_identifier),
            "uncovered_count": sum(
                not item["failed_closed"] for item in per_identifier
            ),
            "equivalence_classes": per_identifier,
        },
        "negative_controls": controls,
        "negative_receipts": {
            "delete_declaration": delete_declaration,
            "misspell_consumer": misspell_consumer,
            "delete_initialization_closure": delete_initialization_closure,
        },
        "claim_boundary": (
            "Focused package-local syntax/name-resolution plus exact canonical/"
            "result consumer closure. External DUT XMR assignments are "
            "specialized only in that harness; clock/reset XMR is independently "
            "bound to current TB/top/filelist/clock bytes and v3 production VCS "
            "escape evidence. Future production VCS remains full-design proof."
        ),
        "pass": valid,
    }


def load_runtime(runtime_path: Path):
    spec = importlib.util.spec_from_file_location(
        "n71n75_package_runtime", runtime_path
    )
    if spec is None or spec.loader is None:
        raise AuditError("cannot load package runtime")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def canonical_gate(runtime_path: Path) -> dict[str, Any]:
    module = load_runtime(runtime_path)
    line = (
        "N75_CANONICAL_DECISION_V2 "
        "decision=EXPECTED_32_STAGE_NATIVE_ORDER_COMPLETE "
        "reason=all_required_qualified_counts_exact "
        "boundary=node0071_stage08_hub_accept_to_node0075_pass00_first_read "
        "sample_begin=0 sample_end=99 stage_start=32 stage_finish=32 "
        "slice_finish_total=512 producer_req=1024 producer_wdata=1024 "
        "producer_finish=16 first_a_cycle=80 first_a_order_ok=1 "
        "a_req=8192 a_data=8192 a_event_lines=8192"
    )
    positive_record, positive_count = module._parse_canonical(
        "N75_SNAPSHOT_V2 kind=FINAL_SUMMARY time=1\n" + line
    )
    level_record, level_count = module._parse_canonical(
        "N75_FEATURE_ENABLE_V2 feature=NATIVE_ORDERING enabled=1\n"
    )
    late_record, late_count = module._parse_canonical(
        line + "\nN75_SNAPSHOT_V2 kind=FINAL_SUMMARY time=2\n"
    )
    conflict_record, conflict_count = module._parse_canonical(
        line + "\n" + line.replace(
            "EXPECTED_32_STAGE_NATIVE_ORDER_COMPLETE",
            "INCOMPLETE_AT_SIMULATOR_END",
        )
    )
    missing_record, missing_count = module._parse_canonical(
        line.replace("reason=all_required_qualified_counts_exact ", "")
    )
    controls = {
        "sustained_level_without_qualified_progress_fails":
            level_record is None and level_count == 0,
        "summary_after_canonical_fails":
            late_record is None and late_count == 2,
        "conflicting_canonical_fails":
            conflict_record is None and conflict_count == 2,
        "missing_reason_or_boundary_fails":
            missing_record is None and missing_count == 1,
    }
    return {
        "positive_unique": positive_record is not None and positive_count == 1,
        "negative_controls": controls,
        "valid": (
            positive_record is not None
            and positive_count == 1
            and all(controls.values())
        ),
    }


def _eval_sv_boolean_expression(
    expression: str,
    state: dict[str, int | bool],
) -> bool:
    translated = expression
    translated = translated.replace("&&", " and ")
    translated = re.sub(r"!(?!=)", " not ", translated)
    identifiers = sorted(
        set(re.findall(r"\bn75_obs_[A-Za-z0-9_]+\b", translated)),
        key=len,
        reverse=True,
    )
    for identifier in identifiers:
        if identifier not in state:
            raise AuditError(f"predicate state missing {identifier}")
        translated = re.sub(
            rf"\b{re.escape(identifier)}\b",
            repr(state[identifier]),
            translated,
        )
    if re.search(r"\bn75_obs_[A-Za-z0-9_]+\b", translated):
        raise AuditError("untranslated observer predicate identifier")
    return bool(eval(f"({translated})", {"__builtins__": {}}, {}))


def _event_step(
    state: dict[str, int | bool],
    event: dict[str, int | bool],
) -> dict[str, int | bool]:
    result = dict(state)
    if (
        not event.get("clock_edge", True)
        or not event.get("enabled", True)
        or not event.get("feature_enabled", True)
        or not event.get("reset_n", True)
    ):
        return result
    cfg_start = bool(event.get("cfg_start", False))
    cfg_finish = bool(event.get("cfg_finish", False))
    exec_start = bool(event.get("exec_start", False))
    slice_finish = bool(event.get("slice_finish", False))
    if cfg_start and not bool(result["cfg_start_d"]):
        result["cfg_start_count"] = int(result["cfg_start_count"]) + 1
    if cfg_finish and not bool(result["cfg_finish_d"]):
        result["cfg_finish_count"] = int(result["cfg_finish_count"]) + 1
    if exec_start and not bool(result["exec_start_d"]):
        result["exec_start_count"] = int(result["exec_start_count"]) + 1
        result["stage_index"] = int(result["stage_index"]) + 1
    if slice_finish and not bool(result["slice_finish_d"]):
        result["finish_total"] = int(result["finish_total"]) + 1
        if int(result["stage_index"]) == 8:
            result["producer_finish_count"] = (
                int(result["producer_finish_count"]) + 1
            )
    if int(result["stage_index"]) == 8:
        if event.get("producer_req_hs", False):
            result["producer_req_count"] = (
                int(result["producer_req_count"]) + 1
            )
        if event.get("producer_wdata_hs", False):
            result["producer_wdata_count"] = (
                int(result["producer_wdata_count"]) + 1
            )
    if 9 <= int(result["stage_index"]) <= 16:
        if event.get("a_req_hs", False):
            result["a_req_count"] = int(result["a_req_count"]) + 1
            if not bool(result["first_a_seen"]):
                result["first_a_seen"] = True
                result["first_a_order_ok"] = (
                    int(result["producer_finish_count"]) == 16
                    and int(result["producer_req_count"]) == 1024
                    and int(result["producer_wdata_count"]) == 1024
                )
        if event.get("a_data_hs", False):
            result["a_data_count"] = int(result["a_data_count"]) + 1
    result["cfg_start_d"] = cfg_start
    result["cfg_finish_d"] = cfg_finish
    result["exec_start_d"] = exec_start
    result["slice_finish_d"] = slice_finish
    return result


def predicate_trace_gate(
    package: Path,
    runtime_path: Path,
    hdl: dict[str, Any],
) -> dict[str, Any]:
    observer_path = package / OBSERVER_REL
    source = observer_path.read_text(encoding="utf-8")
    success_record = next(
        item
        for item in consumer_expressions(source)
        if item["role"] == "success_gate"
    )
    success_expression = success_record["_text"]
    conjuncts = [
        item.strip()
        for item in re.split(r"\s*&&\s*", success_expression)
        if item.strip()
    ]
    positive_state: dict[str, int | bool] = {
        "n75_obs_all_slices_finished": True,
        "n75_obs_exec_start_count": 32,
        "n75_obs_finish_total": 512,
        "n75_obs_producer_req_count": 1024,
        "n75_obs_producer_wdata_count": 1024,
        "n75_obs_producer_finish_count": 16,
        "n75_obs_first_a_order_ok": True,
        "n75_obs_a_req_count": 8192,
        "n75_obs_a_data_count": 8192,
        "n75_obs_a_event_lines": 8192,
        "n75_obs_stall_reported": False,
    }
    success_steps: list[dict[str, Any]] = [
        {
            "case": "all_conjuncts_true",
            "expected": True,
            "actual": _eval_sv_boolean_expression(
                success_expression, positive_state
            ),
        }
    ]
    for index, conjunct in enumerate(conjuncts):
        mutated = dict(positive_state)
        identifier_match = re.search(
            r"\bn75_obs_[A-Za-z0-9_]+\b", conjunct
        )
        if identifier_match is None:
            raise AuditError("success conjunct has no observer identifier")
        identifier = identifier_match.group(0)
        if "!=" in conjunct:
            mutated[identifier] = 32
        elif "==" in conjunct:
            mutated[identifier] = int(mutated[identifier]) - 1
        elif conjunct.lstrip().startswith("!"):
            mutated[identifier] = True
        else:
            mutated[identifier] = False
        success_steps.append(
            {
                "case": f"conjunct_{index:02d}_false",
                "conjunct": conjunct,
                "expected": False,
                "actual": _eval_sv_boolean_expression(
                    success_expression, mutated
                ),
            }
        )

    base_event_state: dict[str, int | bool] = {
        "cfg_start_count": 0,
        "cfg_finish_count": 0,
        "exec_start_count": 0,
        "finish_total": 0,
        "stage_index": 8,
        "producer_req_count": 1023,
        "producer_wdata_count": 1023,
        "producer_finish_count": 15,
        "a_req_count": 0,
        "a_data_count": 0,
        "first_a_seen": False,
        "first_a_order_ok": False,
        "cfg_start_d": False,
        "cfg_finish_d": False,
        "exec_start_d": False,
        "slice_finish_d": False,
    }
    simultaneous = _event_step(
        base_event_state,
        {
            "producer_req_hs": True,
            "producer_wdata_hs": True,
            "slice_finish": True,
        },
    )
    before = _event_step(
        {**base_event_state, "stage_index": 9},
        {"a_req_hs": True},
    )
    boundary_seed = {
        **base_event_state,
        "stage_index": 9,
        "producer_req_count": 1024,
        "producer_wdata_count": 1024,
        "producer_finish_count": 16,
    }
    during = _event_step(boundary_seed, {"a_req_hs": True})
    after_idle = _event_step(boundary_seed, {})
    after = _event_step(after_idle, {"a_req_hs": True})
    stable_first = _event_step(
        {**base_event_state, "stage_index": 0},
        {"exec_start": True},
    )
    stable_second = _event_step(stable_first, {"exec_start": True})
    handshake_first = _event_step(boundary_seed, {"a_req_hs": True})
    handshake_second = _event_step(handshake_first, {"a_req_hs": True})
    reset_held = _event_step(
        boundary_seed, {"a_req_hs": True, "reset_n": False}
    )
    no_sg_edge = _event_step(
        boundary_seed, {"a_req_hs": True, "clock_edge": False}
    )
    inactive_gap = _event_step(
        {**boundary_seed, "stage_index": 17}, {"a_req_hs": True}
    )
    start_finish = _event_step(
        {**base_event_state, "stage_index": 0},
        {"exec_start": True, "slice_finish": True},
    )
    event_checks = {
        "simultaneous_producer_req_wdata_finish": (
            simultaneous["producer_req_count"] == 1024
            and simultaneous["producer_wdata_count"] == 1024
            and simultaneous["producer_finish_count"] == 16
        ),
        "first_a_before_boundary_fails_order": (
            before["first_a_seen"] is True
            and before["first_a_order_ok"] is False
        ),
        "first_a_on_boundary_passes_order": (
            during["first_a_order_ok"] is True
        ),
        "first_a_after_boundary_passes_order": (
            after["first_a_order_ok"] is True
        ),
        "stable_start_level_counts_once": (
            stable_first["exec_start_count"] == 1
            and stable_second["exec_start_count"] == 1
        ),
        "accepted_handshake_each_sg_edge_counts_each_transaction": (
            handshake_first["a_req_count"] == 1
            and handshake_second["a_req_count"] == 2
        ),
        "reset_blocks_updates": reset_held == boundary_seed,
        "non_owner_clock_sample_blocks_updates": no_sg_edge == boundary_seed,
        "inactive_stage_gap_blocks_a_progress": (
            inactive_gap["a_req_count"] == 0
        ),
        "simultaneous_start_finish_both_update": (
            start_finish["exec_start_count"] == 1
            and start_finish["finish_total"] == 1
        ),
        "latest_bare_scope_escape_regression": (
            hdl["xmr_target_proof"]["production_vcs_regression"][
                "v3_exact_failure_was_bare_scope_only"
            ]
            and hdl["xmr_target_proof"]["pass"]
        ),
    }
    canonical = canonical_gate(runtime_path)
    event_span_begin = source.index(
        "    always @(posedge u_NDP_Top_new.clk_sg)"
    )
    event_span_end = source.index(
        "    final begin : N75_OBS_FINAL", event_span_begin
    )
    event_span = source[event_span_begin:event_span_end]
    trace_input = {
        "success_conjuncts": conjuncts,
        "event_cases": [
            "simultaneous producer request/write-data/finish",
            "first A before/on/after producer boundary",
            "stable start level",
            "accepted handshake on consecutive SG edges",
            "reset, no SG edge and inactive-stage gap",
            "simultaneous start and finish",
            "v3 bare-scope escape",
        ],
        "canonical_cases": canonical,
    }
    success_valid = all(
        item["actual"] == item["expected"] for item in success_steps
    )
    valid = success_valid and all(event_checks.values()) and canonical["valid"]
    return {
        "rule_id": "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
        "final_members": {
            "observer": {
                "path": f"{NAME}/{OBSERVER_REL}",
                "sha256": sha256(observer_path),
            },
            "runtime": {
                "path": f"{NAME}/{RUNTIME_REL}",
                "sha256": sha256(runtime_path),
            },
        },
        "predicate_sources": [
            {
                "class": "final_success_conjunction",
                "start_line": success_record["start_line"],
                "expression_sha256":
                    success_record["expression_sha256"],
                "conjunct_count": len(conjuncts),
            },
            {
                "class": "event_transition_and_ordering",
                "start_line": source.count("\n", 0, event_span_begin) + 1,
                "end_line": source.count("\n", 0, event_span_end) + 1,
                "expression_sha256":
                    sha256_bytes(event_span.encode("utf-8")),
            },
            {
                "class": "production_runtime_canonical_parser",
                "function": "_parse_canonical",
                "runtime_sha256": sha256(runtime_path),
            },
        ],
        "trace_input_sha256": canonical_sha256(trace_input),
        "success_conjunct_steps": success_steps,
        "event_checks": event_checks,
        "event_actual_states": {
            "simultaneous": simultaneous,
            "before": before,
            "during": during,
            "after": after,
            "stable_first": stable_first,
            "stable_second": stable_second,
            "handshake_first": handshake_first,
            "handshake_second": handshake_second,
            "reset_held": reset_held,
            "no_sg_edge": no_sg_edge,
            "inactive_gap": inactive_gap,
            "start_finish": start_finish,
        },
        "canonical_parser_direct_execution": canonical,
        "predicate_count": 3,
        "class_count": 3,
        "uncovered_count": 0,
        "exit_code": 0 if valid else 1,
        "claim_boundary": (
            "Exact final observer success expression, source-bound event "
            "transition/order model, and direct production runtime canonical "
            "parser only; no DUT execution and no functional result claim."
        ),
        "pass": valid,
    }


def git_bash_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        f"/{resolved.drive[0].lower()}"
        f"{resolved.as_posix()[len(resolved.drive):]}"
    )


def make_stubs(
    root: Path,
    marker: Path,
    *,
    signal: bool,
) -> Path:
    root.mkdir(parents=True)
    stub_bin = root / "stub-bin"
    stub_bin.mkdir()
    python_stub = stub_bin / "python3"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{Path(sys.executable).resolve().as_posix()}" -B "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    make_stub = stub_bin / "make"
    body = (
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" > \"{git_bash_path(marker)}\"\n"
        "echo SAFE_COMPILE_STUB_REACHED\n"
    )
    if signal:
        body += "sleep 3\nexit 0\n"
    else:
        body += "exit 86\n"
    make_stub.write_text(body, encoding="utf-8", newline="\n")
    os.chmod(python_stub, 0o755)
    os.chmod(make_stub, 0o755)
    return stub_bin


def return_zip_receipt(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "valid": False}
    with zipfile.ZipFile(path) as archive:
        crc = archive.testzip()
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names}
        manifest_names = [
            name for name in names if name.endswith("/RETURN_MANIFEST.json")
        ]
    return {
        "exists": True,
        "crc_valid": crc is None,
        "single_root": len(roots) == 1,
        "return_manifest_count": len(manifest_names),
        "file_count": len(names),
        "sha256": sha256(path),
        "valid": crc is None and len(roots) == 1 and len(manifest_names) == 1,
    }


def runner_compile_control(package: Path, root: Path) -> dict[str, Any]:
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    server = root / "compile-server"
    marker = root / "compile-marker.txt"
    server.mkdir()
    (server / "install/cfg_pkg").mkdir(parents=True)
    stub_bin = make_stubs(root / "compile-control", marker, signal=False)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = str(stub_bin) + os.pathsep + env.get("PATH", "")
    result = subprocess.run(
        [
            str(bash),
            str(package / RUNNER_REL),
            git_bash_path(server),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
        check=False,
    )
    return_zip = server / f"{NAME}_return.zip"
    sidecar = Path(str(return_zip) + ".sha256")
    receipt = return_zip_receipt(return_zip)
    compile_log = server / f"run_{NAME}/compile.log"
    gate = server / f"evidence_{NAME}/SERVER_RESULT_GATE.json"
    valid = (
        result.returncode == 86
        and marker.is_file()
        and compile_log.is_file()
        and "SAFE_COMPILE_STUB_REACHED"
        in compile_log.read_text(encoding="utf-8", errors="replace")
        and gate.is_file()
        and receipt["valid"]
        and sidecar.is_file()
        and sidecar.read_text(encoding="ascii")
        == f"{receipt['sha256']}  {return_zip.name}\n"
        and "unbound variable" not in result.stderr
    )
    return {
        "valid": valid,
        "runner_exit": result.returncode,
        "expected_compile_stub_exit": 86,
        "compile_stub_reached": marker.is_file(),
        "result_gate_created": gate.is_file(),
        "return_zip": receipt,
        "return_sidecar_valid": sidecar.is_file()
        and sidecar.read_text(encoding="ascii")
        == (
            f"{receipt.get('sha256')}  {return_zip.name}\n"
            if receipt.get("sha256") else ""
        ),
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def runner_identity_negative(package: Path, root: Path) -> dict[str, Any]:
    mutant = root / "identity-mutant" / NAME
    shutil.copytree(package, mutant)
    observer = mutant / OBSERVER_REL
    observer.write_bytes(observer.read_bytes() + b"\n// identity-negative\n")
    server = root / "identity-server"
    marker = root / "identity-compile-marker.txt"
    server.mkdir()
    (server / "install/cfg_pkg").mkdir(parents=True)
    stub_bin = make_stubs(root / "identity-control", marker, signal=False)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = str(stub_bin) + os.pathsep + env.get("PATH", "")
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    result = subprocess.run(
        [str(bash), str(mutant / RUNNER_REL), git_bash_path(server)],
        cwd=mutant,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
        check=False,
    )
    return {
        "valid": result.returncode == 5 and not marker.exists(),
        "runner_exit": result.returncode,
        "compile_stub_reached": marker.exists(),
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }


def runner_signal_control(package: Path, root: Path) -> dict[str, Any]:
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    server = root / "signal-server"
    marker = root / "signal-compile-marker.txt"
    stdout_path = root / "signal.stdout"
    stderr_path = root / "signal.stderr"
    status_path = root / "signal.status"
    server.mkdir()
    (server / "install/cfg_pkg").mkdir(parents=True)
    stub_bin = make_stubs(root / "signal-control", marker, signal=True)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = str(stub_bin) + os.pathsep + env.get("PATH", "")
    controller = root / "signal-controller.sh"
    controller.write_text(
        "#!/usr/bin/env bash\n"
        "set +e\n"
        "bash \"$1\" \"$2\" >\"$3\" 2>\"$4\" &\n"
        "pid=$!\n"
        "for _ in $(seq 1 100); do\n"
        "  [ -f \"$5\" ] && break\n"
        "  sleep 0.05\n"
        "done\n"
        "kill -TERM \"$pid\" 2>/dev/null\n"
        "wait \"$pid\"\n"
        "printf '%s\\n' \"$?\" >\"$6\"\n",
        encoding="utf-8",
        newline="\n",
    )
    result = subprocess.run(
        [
            str(bash),
            str(controller),
            str(package / RUNNER_REL),
            git_bash_path(server),
            git_bash_path(stdout_path),
            git_bash_path(stderr_path),
            git_bash_path(marker),
            git_bash_path(status_path),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
        check=False,
    )
    status = (
        int(status_path.read_text(encoding="ascii").strip())
        if status_path.is_file() else None
    )
    signal_path = server / f"evidence_{NAME}/signal_status.txt"
    return_zip = server / f"{NAME}_return.zip"
    stderr = (
        stderr_path.read_text(encoding="utf-8", errors="replace")
        if stderr_path.is_file() else ""
    )
    return {
        "valid": (
            result.returncode == 0
            and status == 125
            and marker.is_file()
            and signal_path.is_file()
            and signal_path.read_text(encoding="ascii").strip() == "TERM"
            and return_zip_receipt(return_zip)["valid"]
            and "unbound variable" not in stderr
        ),
        "controller_exit": result.returncode,
        "runner_exit": status,
        "signal": (
            signal_path.read_text(encoding="ascii").strip()
            if signal_path.is_file() else "MISSING"
        ),
        "compile_stub_reached": marker.is_file(),
        "return_zip": return_zip_receipt(return_zip),
        "stderr_tail": stderr[-2000:],
    }


def return_allowlist_gate(
    manifest: dict[str, Any],
    runtime: str,
) -> dict[str, Any]:
    contract = manifest.get("return_allowlist", {})
    records = contract.get("records", [])
    destinations = [
        str(item.get("destination", "")) for item in records
        if isinstance(item, dict)
    ]
    formal = [
        item for item in records
        if isinstance(item, dict) and item.get("source_scope") == "server"
    ]
    schema_valid = (
        contract.get("schema")
        == "node0071-node0075-native-ordering-return-allowlist-v1"
        and len(records) == 162
        and len(destinations) == len(set(destinations))
        and len(formal) == 144
        and all(
            isinstance(item, dict)
            and item.get("source_scope")
            in {"package", "evidence", "run", "server"}
            and isinstance(item.get("required"), bool)
            and isinstance(item.get("max_bytes"), int)
            and item["max_bytes"] > 0
            and item.get("copy_mode") in {"exact", "head_tail"}
            and bool(item.get("missing_semantics"))
            for item in records
        )
    )
    runtime_driven = (
        "allowlist = _return_allowlist_records(manifest)" in runtime
        and "for item in allowlist:" in runtime
        and "required_sources = {" not in runtime
        and "manifest_allowlist_record_count" in runtime
    )
    return {
        "record_count": len(records),
        "formal_d_record_count": len(formal),
        "destination_duplicate_count":
            len(destinations) - len(set(destinations)),
        "manifest_schema_valid": schema_valid,
        "collector_manifest_driven": runtime_driven,
        "valid": schema_valid and runtime_driven,
    }


def frozen_v3_payload_receipt(
    v4_entries: dict[str, bytes],
) -> dict[str, Any]:
    with zipfile.ZipFile(V3_ZIP) as archive:
        v3_entries = {
            "/".join(PurePosixPath(item.filename).parts[1:]):
                archive.read(item)
            for item in archive.infolist()
            if not item.is_dir()
        }
    frozen_prefixes = ("workload/", "p/", "diag/")
    frozen_exact_paths = {RUNTIME_REL}
    frozen_paths = sorted(
        path
        for path in v3_entries
        if path.startswith(frozen_prefixes) or path in frozen_exact_paths
    )
    missing = [path for path in frozen_paths if path not in v4_entries]
    changed = [
        path
        for path in frozen_paths
        if path in v4_entries and v3_entries[path] != v4_entries[path]
    ]
    return {
        "baseline_zip": str(V3_ZIP),
        "baseline_zip_sha256": sha256(V3_ZIP),
        "frozen_member_count": len(frozen_paths),
        "missing": missing,
        "changed": changed,
        "workload_member_count": sum(
            path.startswith("workload/") for path in frozen_paths
        ),
        "numeric_config_execplan_sca_golden_byte_equal":
            not missing and not changed,
        "sha256": canonical_sha256(
            [
                {
                    "path": path,
                    "sha256": sha256_bytes(v3_entries[path]),
                }
                for path in frozen_paths
            ]
        ),
        "valid": not missing and not changed,
    }


def validate(zip_path: Path, sidecar: Path) -> dict[str, Any]:
    entries, zip_receipt = read_zip(zip_path)
    manifest = json.loads(entries[MANIFEST_REL])
    declared = manifest["files"]
    actual_records = record_map(entries, {MANIFEST_REL})
    rule_receipts = {
        relative: {
            "expected_sha256": expected,
            "observed_sha256": sha256(ROOT / relative),
            "size_bytes": (ROOT / relative).stat().st_size,
            "match": sha256(ROOT / relative) == expected,
        }
        for relative, expected in CURRENT_RECEIPTS.items()
    }
    build_report = json.loads(BUILD_REPORT.read_text(encoding="utf-8"))
    digest = sha256(zip_path)
    sidecar_valid = (
        sidecar.read_text(encoding="ascii")
        == f"{digest}  {zip_path.name}\n"
    )
    with tempfile.TemporaryDirectory(
        prefix="n75a-",
        dir=ROOT / "artifacts/operator_config_validation",
    ) as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        package = root / NAME
        before = tree_records(package)
        runtime_path = package / RUNTIME_REL
        runtime_text = runtime_path.read_text(encoding="utf-8")
        runner_text = (package / RUNNER_REL).read_text(encoding="utf-8")
        observer_text = (package / OBSERVER_REL).read_text(encoding="utf-8")
        paths = {
            path.relative_to(package).as_posix()
            for path in package.rglob("*")
            if path.is_file()
        }
        preflight = run_python(
            runtime_path,
            ["preflight", "--package-root", str(package)],
        )
        sca = sca_receipt(package, manifest)
        execplan = execplan_receipt(package)
        binding = runner_binding(
            manifest, runner_text, runtime_text, observer_text, paths
        )
        feature = feature_gate(
            manifest, runner_text, observer_text, runtime_text
        )
        canonical = canonical_gate(runtime_path)
        hdl = hdl_gate(package, manifest)
        predicate_trace = predicate_trace_gate(
            package, runtime_path, hdl
        )
        allowlist = return_allowlist_gate(manifest, runtime_text)
        path_positive = path_contract(paths, manifest, runner_text)
        overdeep = set(paths)
        overdeep.add("x/" + "z" * 129)
        repeated = set(paths)
        repeated.add(f"workload/{NAME}/{NAME}/duplicate.bin")
        stale_runner = runner_text.replace(
            "+incdir+$package_root/obs",
            "+incdir+$package_root/o",
            1,
        )
        path_negatives = {
            "over_budget_member_fail_closed":
                not path_contract(
                    overdeep, manifest, runner_text, require_references=False
                ),
            "repeated_identity_fail_closed":
                not path_contract(
                    repeated, manifest, runner_text, require_references=False
                ),
            "stale_direct_consumer_fail_closed":
                not path_contract(paths, manifest, stale_runner),
        }
        compile_control = runner_compile_control(package, root)
        identity_negative = runner_identity_negative(package, root)
        signal_control = runner_signal_control(package, root)
        after = tree_records(package)
    frozen_payload = frozen_v3_payload_receipt(entries)
    manifest_exact = {
        item["path"]: (item["size_bytes"], item["sha256"])
        for item in declared
    } == {
        item["path"]: (item["size_bytes"], item["sha256"])
        for item in actual_records
    }
    build_deterministic = (
        build_report.get("deterministic_double_build") is True
        and build_report.get("zip", {}).get("sha256") == digest
        and build_report.get("zip", {}).get("size_bytes")
        == zip_path.stat().st_size
    )
    checks = {
        "zip_crc_root_path_duplicate_symlink":
            all(
                zip_receipt[key] for key in (
                    "crc_valid",
                    "single_root",
                    "path_safe",
                    "duplicate_free",
                    "symlink_free",
                )
            ),
        "sidecar_exact": sidecar_valid,
        "manifest_exact_set_size_sha": manifest_exact,
        "package_identity_and_claim": (
            manifest.get("package_name") == NAME
            and manifest.get("install_name") == NAME
            and manifest.get("status") == "PACKAGE_READY_NOT_RUN"
            and manifest.get("diagnostic_class")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("candidate_release") is False
            and manifest.get("diagnostic_only") is True
            and manifest.get("functional_rtl_modified") is False
            and manifest.get("functional_rtl_file_count") == 0
            and manifest.get("explicit_barrier_claim") is False
            and manifest.get("opcode110_is_barrier") is False
        ),
        "current_rule_receipts":
            all(item["match"] for item in rule_receipts.values()),
        "deterministic_double_build": build_deterministic,
        "fresh_extract_package_preflight": (
            preflight["exit_code"] == 0
            and preflight["parsed"].get("status") == "PACKAGE_PREFLIGHT_PASS"
            and preflight["parsed"].get("a_preload_count") == 0
            and preflight["parsed"].get("return_allowlist_record_count") == 162
        ),
        "sca_and_runtime_d_closure": sca["valid"],
        "single_execplan_native_ordering": execplan["valid"],
        "configured_eight_pass_coverage": (
            manifest["a_coverage"].get("reload_pass_count") == 8
            and manifest["a_coverage"].get("accepted_occurrence_count") == 8192
            and manifest["a_coverage"].get("accepted_traffic_bytes") == 262144
            and manifest["a_coverage"].get("unique_consumer_byte_count") == 32768
        ),
        "observer_four_way_binding": binding["valid"],
        "diagnostic_feature_binding": feature["valid"],
        "canonical_decision_controls": canonical["valid"],
        "package_local_hdl_gate": hdl["pass"],
        "diagnostic_predicate_trace_unit": predicate_trace["pass"],
        "v3_frozen_payload_byte_equal": frozen_payload["valid"],
        "manifest_driven_return_allowlist": allowlist["valid"],
        "path_budget_positive": path_positive,
        "path_budget_negatives": all(path_negatives.values()),
        "runner_preflight_to_compile_and_failure_return":
            compile_control["valid"],
        "runner_identity_precompile_negative": identity_negative["valid"],
        "runner_signal_shared_finalizer": signal_control["valid"],
        "bootstrap_tree_immutable": before == after,
        "no_server_action": True,
    }
    release_gate_matrix = {
        "core_always": {
            "gate_id":
                "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001/core",
            "applicable": True,
            "reason": "fresh v4 identity and final ZIP",
            "changed_surface": True,
            "evidence": {
                "zip_core_checks": all(
                    checks[key] for key in (
                        "zip_crc_root_path_duplicate_symlink",
                        "sidecar_exact",
                        "manifest_exact_set_size_sha",
                        "package_identity_and_claim",
                        "fresh_extract_package_preflight",
                        "sca_and_runtime_d_closure",
                        "path_budget_positive",
                        "path_budget_negatives",
                        "bootstrap_tree_immutable",
                    )
                )
            },
            "blocking": True,
            "pass": all(
                checks[key] for key in (
                    "zip_crc_root_path_duplicate_symlink",
                    "sidecar_exact",
                    "manifest_exact_set_size_sha",
                    "package_identity_and_claim",
                    "fresh_extract_package_preflight",
                    "sca_and_runtime_d_closure",
                    "path_budget_positive",
                    "path_budget_negatives",
                    "bootstrap_tree_immutable",
                )
            ),
        },
        "runner": {
            "gate_id":
                "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
            "applicable": True,
            "reason": "fresh runner namespace and finalizer identity",
            "changed_surface": True,
            "evidence": {
                "compile_stub": compile_control["valid"],
                "identity_negative": identity_negative["valid"],
                "signal_finalizer": signal_control["valid"],
            },
            "blocking": True,
            "pass": (
                compile_control["valid"]
                and identity_negative["valid"]
                and signal_control["valid"]
            ),
        },
        "package_local_hdl": {
            "gate_id":
                "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "applicable": True,
            "reason": "v4 changes package-local observer clock/reset consumers",
            "changed_surface": True,
            "evidence": {
                "hdl_gate": hdl["pass"],
                "xmr_target_proof": hdl["xmr_target_proof"]["pass"],
            },
            "blocking": True,
            "pass": hdl["pass"],
        },
        "materialized_config": {
            "gate_id": "CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001",
            "applicable": False,
            "reason": (
                "v4 reuses v3 workload/config/mapping/bitstream/execplan/SCA/"
                "golden exact bytes; no materialized consumer surface changed"
            ),
            "changed_surface": False,
            "evidence": frozen_payload,
            "blocking": False,
            "pass": frozen_payload["valid"],
        },
        "diagnostic_semantics": {
            "gate_id":
                "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "applicable": True,
            "reason": (
                "observer clock/reset ownership changed and canonical/result "
                "predicate remains required"
            ),
            "changed_surface": True,
            "evidence": {
                "predicate_trace": predicate_trace["pass"],
                "canonical_direct_parser": canonical["valid"],
                "observer_four_way": binding["valid"],
                "feature_binding": feature["valid"],
            },
            "blocking": True,
            "pass": (
                predicate_trace["pass"]
                and canonical["valid"]
                and binding["valid"]
                and feature["valid"]
            ),
        },
        "return_result": {
            "gate_id": "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            "applicable": True,
            "reason": "return allowlist and joint dynamic result gate are required",
            "changed_surface": True,
            "evidence": {
                "manifest_allowlist": allowlist["valid"],
                "runner_failure_return": compile_control["valid"],
                "signal_partial_return": signal_control["valid"],
            },
            "blocking": True,
            "pass": (
                allowlist["valid"]
                and compile_control["valid"]
                and signal_control["valid"]
            ),
        },
        "record_only_warnings": [
            {
                "id": "PLAN_MUTABLE_PROVENANCE",
                "blocking": False,
                "message": "plan is recorded at build and audit time, not a rewrite gate",
            },
            {
                "id": "SERVER_SOURCE_IDENTITY_UNBOUND_UNTIL_RETURN",
                "blocking": False,
                "message": (
                    "ordinary runner intentionally does not preflight the "
                    "server RTL tree; actual compile identity remains return-time"
                ),
            },
        ],
    }
    blocking_failures = [
        key
        for key, gate in release_gate_matrix.items()
        if key != "record_only_warnings"
        and gate["applicable"]
        and gate["blocking"]
        and not gate["pass"]
    ]
    passed = all(checks.values()) and not blocking_failures
    return {
        "schema":
            "node0071-node0075-native-ordering-v4-final-zip-self-audit-v1",
        "status": "PASS" if passed else "FAIL",
        "valid": passed,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": passed,
        "package_release": "PACKAGE_READY_NOT_RUN" if passed else "NONE",
        "candidate_release": False,
        "errors": [
            key for key, value in checks.items() if not value
        ],
        "checks": checks,
        "release_gate_matrix": release_gate_matrix,
        "blocking_failures": blocking_failures,
        "zip": {
            "path": str(zip_path),
            "size_bytes": zip_path.stat().st_size,
            "sha256": digest,
        },
        "sidecar": {
            "path": str(sidecar),
            "size_bytes": sidecar.stat().st_size,
            "sha256": sha256(sidecar),
            "content_valid": sidecar_valid,
        },
        "zip_receipt": zip_receipt,
        "manifest_sha256": sha256_bytes(entries[MANIFEST_REL]),
        "manifest_file_count": len(declared) + 1,
        "current_rule_receipts": rule_receipts,
        "plan_mutable_provenance": {
            "current_sha256": sha256(ROOT / ".agents/plan.md"),
            "package_generation_sha256": next(
                item["sha256"]
                for item in manifest["source_inputs"]
                if item["path"] == ".agents/plan.md"
            ),
        },
        "build_report": {
            "path": str(BUILD_REPORT),
            "sha256": sha256(BUILD_REPORT),
            "deterministic": build_deterministic,
        },
        "package_preflight": preflight,
        "sca_gate": sca,
        "execplan_gate": execplan,
        "observer_binding": binding,
        "feature_binding": feature,
        "canonical_decision_gate": canonical,
        "package_local_hdl_gate": hdl,
        "diagnostic_predicate_trace_gate": predicate_trace,
        "frozen_v3_payload_receipt": frozen_payload,
        "return_allowlist_gate": allowlist,
        "path_length_budget": manifest["path_length_budget"],
        "path_length_budget_negatives": path_negatives,
        "runner_compile_stub_control": compile_control,
        "runner_identity_negative_control": identity_negative,
        "runner_signal_stub_control": signal_control,
        "bootstrap_tree_immutable": before == after,
        "server_command":
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": f"{NAME}_return.zip",
        "server_uploaded": False,
        "server_run": False,
        "lease_taken": False,
        "functional_rtl_modified": False,
        "claim_boundary": (
            "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX; config-bound E2 plus local "
            "package controls only. Dynamic actual A acceptance, natural "
            "terminal and formal D require a server return. No explicit "
            "visibility barrier and no server-source identity claim."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=ZIP_PATH)
    parser.add_argument("--sidecar", type=Path, default=SIDECAR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        report = validate(args.zip.resolve(), args.sidecar.resolve())
    except Exception as exc:
        report = {
            "schema":
                "node0071-node0075-native-ordering-v4-final-zip-self-audit-v1",
            "status": "FAIL",
            "valid": False,
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": False,
            "package_release": "NONE",
            "errors": [f"{type(exc).__name__}: {exc}"],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "valid": report.get("valid"),
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS":
                    report.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS"),
                "package_release": report.get("package_release"),
                "errors": report.get("errors"),
                "output": str(args.output.resolve()),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
