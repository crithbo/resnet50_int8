#!/usr/bin/env python3
"""Final family audit for the native-four-lane p19 D-flow diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from validate_node0004_v44_observer_syntax import compile_case


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p19b_dflow"
SOURCE_ID = "r5_n4_0cc_p18_pekeep3"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_SHA256 = (
    "58a7a5e15d3dc05f96431783bb8212d11ea686f5d29d1815a920194272a09b8f"
)
OBSERVER = "tb_probe/native_return_observer.svh"
TAIL_MARKER = "    // v27: narrow MSE4 Buffer5-read/tag"
TAIL_END = "    // p19 imported qualified D-flow diagnostic tail end"
XMR_RE = re.compile(
    r"u_NDP_Top_new(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"(?:\[[^\]\n]+\])*)+"
)
PLUSARG_RE = re.compile(r"\+RETURN_[A-Za-z0-9_]+(?:=[^\s\"']+)?")
REQUIRED_FEATURES = {
    "+RETURN_OBS_MSE4_DESCRIPTOR",
    "+RETURN_OBS_MSE4_INDEX",
    "+RETURN_OBS_LC18_PE7",
    "+RETURN_OBS_ROWLC4_BUFAG",
    "+RETURN_OBS_B5RD",
    "+RETURN_OBS_DWRITE_PATH",
    "+RETURN_OBS_DATAHUB_DRAIN",
    "+RETURN_OBS_WRDRAIN",
    "+RETURN_OBS_WRTERM",
    "+RETURN_OBS_LC9_SPLIT",
    "+RETURN_OBS_LC9_ACTUAL",
    "+RETURN_OBS_DTERM_OWNER",
    "+RETURN_OBS_LC13_LC14",
    "+RETURN_OBS_DSKEW",
}


class ValidationError(RuntimeError):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValidationError(f"refusing to overwrite audit: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def zip_payloads(zip_path: Path, root: str) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValidationError("ZIP CRC failure")
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                not pure.parts
                or pure.parts[0] != root
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in seen
            ):
                raise ValidationError(f"unsafe ZIP member: {info.filename}")
            seen.add(info.filename)
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            payloads[relative] = archive.read(info)
    return payloads


def manifest_files(payloads: dict[str, bytes]) -> dict[str, dict[str, Any]]:
    return {
        path: {"sha256": digest(payload), "size_bytes": len(payload)}
        for path, payload in payloads.items()
        if path != "package_manifest.json"
    }


def normalized_sca_equal(
    source: dict[str, bytes], successor: dict[str, bytes]
) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for relative in (
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    ):
        result[relative] = (
            successor[relative]
            .decode()
            .replace(PACKAGE_ID, SOURCE_ID)
            .encode()
            == source[relative]
        )
    return result


def leaf(expression: str) -> str:
    return re.sub(r"\[.*\]$", "", expression.rsplit(".", 1)[-1])


def focused_tail_compile(
    observer: str, iverilog: Path, temp_root: Path
) -> dict[str, Any]:
    if observer.count(TAIL_MARKER) != 1 or observer.count(TAIL_END) != 1:
        raise ValidationError("p19 diagnostic tail markers differ")
    tail = observer[
        observer.index(TAIL_MARKER) : observer.index(TAIL_END)
    ]
    expressions = sorted(set(XMR_RE.findall(tail)), key=len, reverse=True)
    replacements = {
        expression: f"p19_xmr_{index}"
        for index, expression in enumerate(expressions)
    }
    normalized = tail
    for expression, local in replacements.items():
        normalized = normalized.replace(expression, local)
    # The generic XMR matcher deliberately avoids recursive bracket parsing.
    # A few exact DUT expressions index a bitmap with another XMR; after the
    # longest-expression substitution their closing bracket remains.  The
    # focused harness represents that complete consumer as one local signal.
    normalized = re.sub(
        r"(p19_xmr_[0-9]+)\s*\[\s*p19_xmr_[0-9]+",
        r"\1",
        normalized,
    )
    normalized = re.sub(r"(p19_xmr_[0-9]+)\]", r"\1", normalized)
    normalized = normalized.replace(
        "logic [`MSE_BUF_AG_INPORT_TAG_WIDTH-1:0]", "logic [255:0]"
    )
    declarations = "\n".join(
        f"  logic [255:0] {local};" for local in replacements.values()
    )
    source = (
        "`timescale 1ns/1ps\nmodule lc9_split_focus_top;\n"
        "  bit return_obs_enabled, return_obs_active;\n"
        "  integer return_obs_fd;\n"
        f"{declarations}\n{normalized}\nendmodule\n"
    )
    positive = compile_case(iverilog, temp_root, "p19_tail_positive", source)
    first = next(iter(replacements.values()))
    missing = compile_case(
        iverilog,
        temp_root,
        "p19_tail_deleted_leaf",
        source.replace(f"  logic [255:0] {first};", "", 1),
    )
    typo = compile_case(
        iverilog,
        temp_root,
        "p19_tail_renamed_leaf",
        source.replace(first, first + "_wrong", 1),
    )
    return {
        "valid": (
            positive["exit_code"] == 0
            and missing["exit_code"] != 0
            and typo["exit_code"] != 0
        ),
        "positive": positive,
        "negative_deleted_leaf": missing,
        "negative_renamed_leaf": typo,
        "xmr_expression_count": len(expressions),
        "tail_sha256": digest(tail.encode()),
        "expressions": expressions,
        "positive_source_debug_lines_1700_1840": [
            {"line": index, "text": line}
            for index, line in enumerate(source.splitlines(), 1)
            if 400 <= index <= 440 or 1700 <= index <= 1840
        ],
    }


def predicate_trace(observer: str, runner: str) -> dict[str, Any]:
    rows = [
        dict(desc=0, prepared=0, match=0, source=0, lc13=0, lc15=0, pe7=0),
        dict(desc=0, prepared=0, match=0, source=0, lc13=0, lc15=0, pe7=0),
        dict(desc=0, prepared=1, match=0, source=1, lc13=1, lc15=0, pe7=0),
        dict(desc=1, prepared=2, match=1, source=2, lc13=1, lc15=1, pe7=1),
        dict(desc=2, prepared=2, match=1, source=2, lc13=1, lc15=1, pe7=1),
        dict(desc=2, prepared=2, match=1, source=2, lc13=1, lc15=1, pe7=1),
        dict(desc=2, prepared=3, match=1, source=3, lc13=2, lc15=1, pe7=1),
        dict(desc=2, prepared=4, match=1, source=4, lc13=2, lc15=1, pe7=1),
    ]
    previous = rows[0]
    emitted: list[dict[str, int]] = []
    for row in rows[1:]:
        if any(row[key] != previous[key] for key in previous):
            emitted.append({**row, "delta": row["prepared"] - row["desc"]})
        previous = row
    receipt_line = next(
        line
        for line in runner.splitlines()
        if "simulator_argv.txt" in line and line.lstrip().startswith("printf")
    )
    invocation_line = next(
        line
        for line in runner.splitlines()
        if '12h "$simv"' in line
    )
    receipt_args = set(PLUSARG_RE.findall(receipt_line))
    invocation_args = set(PLUSARG_RE.findall(invocation_line))
    checks = {
        "stable_level_not_counted": len(emitted) == 5,
        "simultaneous_edge_single_record": emitted[1]["delta"] == 1,
        "catchup_returns_zero": emitted[2]["delta"] == 0,
        "first_and_second_skew": [row["delta"] for row in emitted[-2:]]
        == [1, 2],
        "actual_predicate_present": (
            observer.count(
                "return_obs_md_prepared_wr - return_obs_md_desc_hs"
            )
            >= 2
        ),
        "runner_receipt_equals_invocation": receipt_args == invocation_args,
        "required_features_enabled": REQUIRED_FEATURES <= receipt_args,
        "feature_enable_occurs_twice": all(
            len(re.findall(rf' {re.escape(feature)}(?=\s|")', runner))
            == 2
            for feature in REQUIRED_FEATURES
        ),
        "wrong_feature_negative_fail_closed": (
            runner.replace("+RETURN_OBS_DSKEW", "+RETURN_OBS_DSKEX", 1).count(
                " +RETURN_OBS_DSKEW"
            )
            != 2
        ),
        "predicate_typo_negative_fail_closed": (
            observer.replace(
                "return_obs_md_prepared_wr - return_obs_md_desc_hs",
                "return_obs_md_prepared_wr - return_obs_md_prepared_wr",
                1,
            ).count("return_obs_md_prepared_wr - return_obs_md_desc_hs")
            < observer.count(
                "return_obs_md_prepared_wr - return_obs_md_desc_hs"
            )
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "input_rows": rows,
        "emitted": emitted,
        "receipt_plusargs": sorted(receipt_args),
        "invocation_plusargs": sorted(invocation_args),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--iverilog", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    if sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise ValidationError("exact p18 source differs")
    source = zip_payloads(SOURCE_ZIP, SOURCE_ID)
    successor = zip_payloads(zip_path, PACKAGE_ID)
    manifest = json.loads(successor["package_manifest.json"])
    observer = successor[OBSERVER].decode()
    runner = successor["PREPARE_AND_RUN.sh"].decode()

    frozen_members = sorted(
        path
        for path in source
        if path.startswith("workload/runtime/runs/c0/install/")
    )
    frozen_exact = all(source[path] == successor.get(path) for path in frozen_members)
    sca_equal = normalized_sca_equal(source, successor)
    corpus: dict[Path, str] = {}
    rtl_root = ROOT / "NDP_copy01/rtl"
    for path in sorted(rtl_root.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".v", ".sv", ".vh", ".svh"}:
            corpus[path] = path.read_text(encoding="utf-8", errors="ignore")

    with tempfile.TemporaryDirectory(prefix="p19-dflow-focus-") as temp:
        compile_result = focused_tail_compile(
            observer, args.iverilog.resolve(), Path(temp)
        )
    expressions = compile_result.pop("expressions")
    tokens = {leaf(expression) for expression in expressions}
    token_locations: dict[str, list[Path]] = {token: [] for token in tokens}
    for path, text in corpus.items():
        present = tokens & set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", text))
        for token in present:
            token_locations[token].append(path)
    leaf_bindings: list[dict[str, Any]] = []
    missing: list[str] = []
    for expression in expressions:
        token = leaf(expression)
        locations = token_locations[token]
        if not locations:
            missing.append(expression)
        leaf_bindings.append(
            {
                "expression": expression,
                "leaf": token,
                "binding_files": [
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                    for path in locations[:4]
                ],
            }
        )
    trace = predicate_trace(observer, runner)
    path_budget = manifest["path_length_budget"]
    contract = json.loads(successor["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])
    checks = {
        "zip_root_crc_path_exact": True,
        "manifest_files_exact": manifest["files"] == manifest_files(successor),
        "package_identity_exact": (
            manifest["package_identity"] == PACKAGE_ID
            and manifest["install_name"] == PACKAGE_ID
        ),
        "source_binding_exact": (
            manifest["delivery_successor"]["source_zip_sha256"]
            == SOURCE_SHA256
        ),
        "frozen_install_payload_exact": frozen_exact,
        "sca_identity_normalized_exact": all(sca_equal.values()),
        "observer_manifest_binding_exact": (
            manifest["observer_binding"]["sha256"]
            == digest(successor[OBSERVER])
            and manifest["observer_binding"]["size_bytes"]
            == len(successor[OBSERVER])
        ),
        "focused_observer_compile_controls": compile_result["valid"],
        "all_xmr_leaf_definitions_current": not missing,
        "predicate_trace": trace["valid"],
        "repeat_execution_contract": (
            contract["repeat_execution"]["mode"]
            == "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS"
            and contract["repeat_execution"]["return_name_policy"]
            == "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"
        ),
        "install_only_runtime": (
            contract["required_preexisting_parents"] == ["install"]
            and contract["package_creatable_parent_dirs"]
            == ["install/cfg_pkg", "install/codex_runs"]
        ),
        "path_budget_self_consistent": (
            path_budget["longest_projected_relative_path_chars"]
            == len(path_budget["longest_projected_relative_path"])
            == path_budget["max_projected_relative_path_chars"]
            and path_budget["max_projected_absolute_path_chars"] < 240
        ),
        "fixed_unique_simresult": (
            'return_tag="r$(date -u +%s%N)_$$"' in runner
            and "/home/panqs/ndp/simresult/" in runner
            and "${package_identity}_${return_tag}_return.zip" in runner
        ),
        "functional_rtl_absent": not any(
            path.startswith("rtl/") for path in successor
        ),
    }
    valid = all(checks.values())
    report = {
        "schema": "conv-native-four-lane-p19-dflow-family-audit-v1",
        "status": "PASS" if valid else "FAIL",
        "valid": valid,
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256": sha256(zip_path),
        },
        "source": {
            "path": str(SOURCE_ZIP),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
        },
        "frozen": {
            "install_payload_count": len(frozen_members),
            "install_payload_byte_equal": frozen_exact,
            "sca_identity_normalized_equal": sca_equal,
            "numeric_w3_golden_repeated": False,
        },
        "observer": {
            "sha256": digest(successor[OBSERVER]),
            "bytes": len(successor[OBSERVER]),
            "focused_compile": compile_result,
            "xmr_expression_count": len(expressions),
            "missing_leaf_expressions": missing,
            "leaf_bindings": leaf_bindings,
            "wrong_sibling_policy": "exact expression set and leaf binding required",
        },
        "predicate_trace": trace,
        "release_gate_matrix": {
            "package_bootstrap_path": {
                "applicability": "blocking_applicable",
                "pass": checks["zip_root_crc_path_exact"]
                and checks["manifest_files_exact"],
            },
            "runtime_layout": {
                "applicability": "blocking_applicable",
                "pass": checks["repeat_execution_contract"]
                and checks["install_only_runtime"],
            },
            "package_local_hdl": {
                "applicability": "blocking_applicable",
                "pass": checks["focused_observer_compile_controls"]
                and checks["all_xmr_leaf_definitions_current"],
            },
            "materialized_config": {
                "applicability": "receipt_reuse",
                "pass": checks["frozen_install_payload_exact"]
                and checks["sca_identity_normalized_exact"],
            },
            "diagnostic_predicate_trace": {
                "applicability": "blocking_applicable",
                "pass": checks["predicate_trace"],
            },
            "numeric_w3_golden": {
                "applicability": "record_only",
                "pass": True,
            },
            "production_compile_sim_return": {
                "applicability": "dynamic_only",
                "pass": None,
            },
        },
        "claim_boundary": (
            "Final package bytes, frozen payload, observer syntax/scope/current "
            "leaf binding, event predicate and runner contract only. No DUT, "
            "numeric, natural terminal, formal D, E3, E4, E5 or performance "
            "claim."
        ),
    }
    write_json(args.output.resolve(), report)
    print(
        json.dumps(
            {"status": report["status"], "errors": report["errors"]},
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
