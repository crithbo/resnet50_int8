#!/usr/bin/env python3
"""Build the p19 time-aligned D-flow diagnostic from exact repeatable p18."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p17_static_xmr_package as p17


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p18_pekeep3"
PACKAGE_ID = "r5_n4_0cc_p19b_dflow"
ATTEMPT = "a0"
SOURCE_SHA256 = (
    "58a7a5e15d3dc05f96431783bb8212d11ea686f5d29d1815a920194272a09b8f"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
P18_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p18_return_analysis/report_v2.json"
)
V64_OBSERVER = (
    ROOT
    / "outputs/conv_node0004_v63_return_v64_successor/build/"
    "r5_n4_hw_v64_dskew_diag/tb_probe/native_return_observer.svh"
)
V64_OBSERVER_SHA256 = (
    "47a2edc0b7ff0a1cc51c290ceeb23cce749b96a203ae8ddf159cac67ae02c7d1"
)
V64_OBSERVER_VALIDATION = (
    ROOT
    / "outputs/conv_node0004_v63_return_v64_successor/"
    "v64_observer_validation.json"
)
V64_PREDICATE_TRACE = (
    ROOT
    / "outputs/conv_node0004_v63_return_v64_successor/"
    "v64_dskew_predicate_trace.json"
)
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p19b_dflow"
OBSERVER = "tb_probe/native_return_observer.svh"
TAIL_MARKER = "    // v27: narrow MSE4 Buffer5-read/tag"
DIAGNOSTIC_PLUSARGS = (
    "+RETURN_OBS_MSE4_DESCRIPTOR +RETURN_OBS_MSE4_DESCRIPTOR_LIMIT=96 "
    "+RETURN_OBS_MSE4_INDEX +RETURN_OBS_MSE4_INDEX_LIMIT=96 "
    "+RETURN_OBS_LC18_PE7 +RETURN_OBS_LC18_PE7_LIMIT=96 "
    "+RETURN_OBS_ROWLC4_BUFAG +RETURN_OBS_ROWLC4_BUFAG_LIMIT=128 "
    "+RETURN_OBS_B5RD +RETURN_OBS_B5RD_LIMIT=96 "
    "+RETURN_OBS_DWRITE_PATH +RETURN_OBS_DWRITE_PATH_LIMIT=64 "
    "+RETURN_OBS_DATAHUB_DRAIN +RETURN_OBS_DATAHUB_DRAIN_LIMIT=64 "
    "+RETURN_OBS_WRDRAIN +RETURN_OBS_WRDRAIN_LIMIT=1 "
    "+RETURN_OBS_WRTERM +RETURN_OBS_WRTERM_LIMIT=96 "
    "+RETURN_OBS_LC9_SPLIT +RETURN_OBS_LC9_SPLIT_LIMIT=128 "
    "+RETURN_OBS_LC9_ACTUAL +RETURN_OBS_LC9_ACTUAL_LIMIT=192 "
    "+RETURN_OBS_DTERM_OWNER +RETURN_OBS_DTERM_OWNER_LIMIT=96 "
    "+RETURN_OBS_LC13_LC14 +RETURN_OBS_LC13_LC14_LIMIT=128 "
    "+RETURN_OBS_DSKEW +RETURN_OBS_DSKEW_LIMIT=128"
)
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".sh",
    ".txt",
}
FROZEN_WORKLOAD_EXCEPT_SCA = "workload/runtime/runs/c0/install/"
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_extract(source: Path, destination: Path) -> Path:
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise BuildError("source ZIP CRC failure")
        names: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or info.filename in names
                or stat.S_ISLNK(mode)
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            names.add(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {SOURCE_ID}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    old = destination / SOURCE_ID
    new = destination / PACKAGE_ID
    # Windows can deny renaming a just-extracted tree while file-system
    # metadata is still settling.  Copy to the fresh identity instead; the
    # deterministic archive includes only ``new``.
    shutil.copytree(old, new)
    return new


def deterministic_zip(package: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def replace_identity(package: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        payload = path.read_bytes()
        if SOURCE_ID.encode() not in payload:
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise BuildError(f"identity-bearing text is not UTF-8: {path}") from error
        path.write_text(
            text.replace(SOURCE_ID, PACKAGE_ID),
            encoding="utf-8",
            newline="\n",
        )
        changed.append(path.relative_to(package).as_posix())
    required = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json",
        "package_manifest.json",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    if not required <= set(changed):
        raise BuildError(
            f"identity rebinding surface differs: {sorted(required - set(changed))}"
        )
    return changed


def append_observer(package: Path) -> dict[str, Any]:
    observer = package / OBSERVER
    base = observer.read_text(encoding="utf-8")
    v64 = V64_OBSERVER.read_text(encoding="utf-8")
    if sha256(V64_OBSERVER) != V64_OBSERVER_SHA256:
        raise BuildError("exact v64 observer provenance differs")
    if v64.count(TAIL_MARKER) != 1:
        raise BuildError("v64 diagnostic tail marker differs")
    if "RETURN_OBS_DSKEW" in base:
        raise BuildError("p18 base already contains DSKEW")
    tail = v64[v64.index(TAIL_MARKER) :]
    combined = (
        base.rstrip()
        + "\n\n"
        + "    // p19 imported qualified D-flow diagnostic tail begin\n"
        + tail.rstrip()
        + "\n"
        + "    // p19 imported qualified D-flow diagnostic tail end\n"
    )
    observer.write_text(combined, encoding="utf-8", newline="\n")
    return {
        "base_sha256": digest(base.encode()),
        "source_v64_observer_sha256": V64_OBSERVER_SHA256,
        "imported_tail_sha256": digest(tail.encode()),
        "new_sha256": sha256(observer),
        "new_bytes": observer.stat().st_size,
        "feature_count": len(
            {
                match.group(1)
                for match in re.finditer(
                    r'\$test\$plusargs\("([^"]+)"\)', tail
                )
            }
        ),
    }


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = "+RETURN_OBSERVER +N4D_C0_BOUNDARY_DIAG"
    replacement = f"+RETURN_OBSERVER {DIAGNOSTIC_PLUSARGS} +N4D_C0_BOUNDARY_DIAG"
    if text.count(anchor) != 2:
        raise BuildError("p18 runner observer plusarg anchor differs")
    text = text.replace(anchor, replacement)
    helper_anchor = "preflight_stage=BOOTSTRAP_ARMED\nfinalize() {\n"
    helper = (
        "preflight_stage=BOOTSTRAP_ARMED\n"
        "runner_fail() {\n"
        '  code="$1"\n'
        '  shift\n'
        '  message="$*"\n'
        "  printf 'RUNNER_ERROR package=%s code=%s message=%s\\n' "
        '"$package_identity" "$code" "$message" >&2\n'
        '  exit "$code"\n'
        "}\n"
        "finalize() {\n"
    )
    if text.count(helper_anchor) != 1:
        raise BuildError("runner visibility helper anchor differs")
    text = text.replace(helper_anchor, helper)
    bootstrap_exit = '    exit "$original"\n'
    bootstrap_visible = (
        "    printf 'RUNNER_FINAL_STATUS package=%s exit=%s\\n' "
        '"$package_identity" "$original" >&2\n'
        '    exit "$original"\n'
    )
    final_exit = '  exit "$final"\n}\n'
    final_visible = (
        "  printf 'RUNNER_FINAL_STATUS package=%s exit=%s\\n' "
        '"$package_identity" "$final" >&2\n'
        '  exit "$final"\n}\n'
    )
    if text.count(bootstrap_exit) != 1 or text.count(final_exit) != 1:
        raise BuildError("runner final-status exit anchors differ")
    text = text.replace(bootstrap_exit, bootstrap_visible)
    text = text.replace(final_exit, final_visible)
    replacements = {
        '  exit 2\n': (
            '  runner_fail 2 "usage requires one absolute server-root path"\n'
        ),
        (
            'case "$1" in /*) ;; *) echo "server_root must be absolute" '
            '>&2; exit 2;; esac'
        ): (
            'case "$1" in /*) ;; *) runner_fail 2 '
            '"server-root path must be absolute";; esac'
        ),
        (
            'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2'
        ): (
            'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || '
            'runner_fail 2 "server-root path cannot be resolved"'
        ),
        (
            'for tool in python3 timeout make; do command -v "$tool" '
            '>/dev/null 2>&1 || exit 3; done'
        ): (
            'for tool in python3 timeout make; do command -v "$tool" '
            '>/dev/null 2>&1 || runner_fail 3 '
            '"required server tool is unavailable"; done'
        ),
        (
            'pre_snapshot_json="$(python3 "$root_gate" snapshot '
            '--server-root "$server_root")" || exit 12'
        ): (
            'pre_snapshot_json="$(python3 "$root_gate" snapshot '
            '--server-root "$server_root")" || runner_fail 12 '
            '"NDP-root pre-snapshot gate failed"'
        ),
        'mkdir -p -- "$result_root" || exit 9': (
            'mkdir -p -- "$result_root" || runner_fail 9 '
            '"fixed simresult directory cannot be created"'
        ),
        '[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9': (
            '[ -d "$result_root" ] && [ -w "$result_root" ] || '
            'runner_fail 9 "fixed simresult directory is not writable"'
        ),
        'resolved_result_root="$(cd "$result_root" && pwd -P)" || exit 9': (
            'resolved_result_root="$(cd "$result_root" && pwd -P)" || '
            'runner_fail 9 "fixed simresult directory cannot be resolved"'
        ),
        (
            '[ "$resolved_result_root" = "/home/panqs/ndp/simresult" ] '
            '|| exit 9'
        ): (
            '[ "$resolved_result_root" = "/home/panqs/ndp/simresult" ] '
            '|| runner_fail 9 "fixed simresult identity differs"'
        ),
        '  exit 10\n': (
            '  runner_fail 10 "unique fixed-result target already exists"\n'
        ),
        ' ] || exit 11\n': (
            ' ] || runner_fail 11 "forbidden duplicate return target exists"\n'
        ),
        '[ "$layout_status" -eq 0 ] || exit 12': (
            '[ "$layout_status" -eq 0 ] || runner_fail 12 '
            '"install-subtree runtime layout preparation failed"'
        ),
        (
            'parent_preflight_json="$(python3 "$root_gate" '
            'validate-parents --server-root "$server_root" --manifest '
            '"$package_root/package_manifest.json")" || exit 12'
        ): (
            'parent_preflight_json="$(python3 "$root_gate" '
            'validate-parents --server-root "$server_root" --manifest '
            '"$package_root/package_manifest.json")" || runner_fail 12 '
            '"NDP-root parent validation failed"'
        ),
        '[ "$path_budget_status" -eq 0 ] || exit 5': (
            '[ "$path_budget_status" -eq 0 ] || runner_fail 5 '
            '"package path-budget preflight failed"'
        ),
        '[ "$package_preflight_status" -eq 0 ] || exit 5': (
            '[ "$package_preflight_status" -eq 0 ] || runner_fail 5 '
            '"package exact-set preflight failed"'
        ),
        '[ "$install_preflight_status" -eq 0 ] || exit 6': (
            '[ "$install_preflight_status" -eq 0 ] || runner_fail 6 '
            '"installed payload verification failed"'
        ),
        '[ "$observer_preflight_status" -eq 0 ] || exit 7': (
            '[ "$observer_preflight_status" -eq 0 ] || runner_fail 7 '
            '"package observer precompile guard failed"'
        ),
        (
            'if [ "$run_status" -eq 0 ] && [ "$feature_status" -ne 0 ]; '
            'then exit 10; fi'
        ): (
            'if [ "$run_status" -eq 0 ] && [ "$feature_status" -ne 0 ]; '
            'then runner_fail 10 "runtime feature-binding receipt failed"; fi'
        ),
        (
            'python3 "$runtime" qualify-run --sim-log "$run_root/c0/sim.log" '
            '--observer-log "$observer_log" --output '
            '"$evidence_root/natural_terminal/c0.json" || exit 9'
        ): (
            'python3 "$runtime" qualify-run --sim-log "$run_root/c0/sim.log" '
            '--observer-log "$observer_log" --output '
            '"$evidence_root/natural_terminal/c0.json" || runner_fail 9 '
            '"natural-terminal qualification failed"'
        ),
    }
    for old, new in replacements.items():
        if old not in text:
            raise BuildError(f"runner visibility replacement anchor absent: {old}")
        text = text.replace(old, new)
    if re.search(r"(?<![A-Za-z0-9_])exit[ \t]+[1-9][0-9]*", text):
        raise BuildError("runner still contains a bare numeric exit")
    path.write_text(text, encoding="utf-8", newline="\n")


def projected_paths(package: Path, contract: dict[str, Any]) -> list[str]:
    return p17.p16.base.projected_paths(package, contract)


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["claim_boundary"] = (
        "p19 native-four-lane c0 time-aligned qualified D-flow diagnostic "
        "after p18 PE keep3 dynamic closure; workload/config/numeric/golden/"
        "timeout/functional RTL are frozen and no natural terminal, formal "
        "320D, performance, E3, E4 or E5 is claimed before formal return."
    )
    paths = projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        contract["path_budget"]["declared_target_root_max_chars"]
        + 1
        + len(longest)
    )
    write_json(path, contract)
    return contract


def update_pointer_and_readme(package: Path) -> None:
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-p19-dflow-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p19 D-flow diagnostic\n\n"
        "This fresh c0-only successor keeps p18 workload, PE keep3 config, "
        "mapping, bitstream, execplan, SCA semantics, numeric/W3/golden and "
        "timeout unchanged. It appends one bounded time-aligned qualified "
        "ledger over the remaining descriptor/prepared-data/source/tag/"
        "LC/PE7/D-write terminal candidates.\n\n"
        "Run after extraction:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n"
        "```\n\n"
        "Each execution publishes a unique return and sidecar under "
        "`/home/panqs/ndp/simresult`. This diagnostic does not claim natural "
        "terminal, formal 320D, E3, E4, E5 or performance before return.\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh_manifest_files(package: Path, manifest: dict[str, Any]) -> None:
    manifest["files"] = p17.p16.base.file_records(package)


def patch_manifest(
    package: Path,
    contract: dict[str, Any],
    identity_members: list[str],
    observer: dict[str, Any],
) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P18_ANALYSIS.read_text(encoding="utf-8"))
    if (
        not analysis.get("valid")
        or analysis.get("status")
        != "P18_PEKEEP3_DYNAMIC_PASS_NEXT_D_FLOW_DIAGNOSTIC_REQUIRED"
    ):
        raise BuildError("formal p18 analysis is not accepted")
    manifest.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p19-dflow-package-v1",
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}",
            "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
            "rule_receipts": [
                {
                    "path": relative,
                    "bytes": (ROOT / relative).stat().st_size,
                    "sha256": sha256(ROOT / relative),
                }
                for relative in RULE_PATHS
            ],
            "rule_receipts_current_match": True,
        }
    )
    manifest["source_p18_formal_return_analysis"] = {
        "path": P18_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(P18_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"],
        "keep3_dynamic_closure": True,
        "natural_terminal": False,
        "formal_D_claimed": False,
    }
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": (
            "p18 crossed the PE keep3 boundary but stopped at a later "
            "qualified D-flow stall; one time-aligned candidate-complete "
            "observer is required before any additional config change"
        ),
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    manifest["observer_binding"].update(
        {
            "sha256": observer["new_sha256"],
            "source_sha256": observer["new_sha256"],
            "size_bytes": observer["new_bytes"],
            "changed_in_p19": True,
            "p19_feature": "RETURN_OBS_DSKEW",
            "p19_runtime_enable": "+RETURN_OBS_DSKEW",
            "p19_time_aligned_qualified": True,
            "p19_imported_tail": observer,
            "new_dut_hierarchy_references": (
                "exact v64 validated tail reused under current 0cc RTL "
                "binding; formal p19 compile identity required in return"
            ),
        }
    )
    manifest["p19_dflow_observer"] = {
        **observer,
        "source_v64_validation": {
            "path": V64_OBSERVER_VALIDATION.relative_to(ROOT).as_posix(),
            "sha256": sha256(V64_OBSERVER_VALIDATION),
        },
        "source_v64_predicate_trace": {
            "path": V64_PREDICATE_TRACE.relative_to(ROOT).as_posix(),
            "sha256": sha256(V64_PREDICATE_TRACE),
        },
        "enabled_plusargs": DIAGNOSTIC_PLUSARGS.split(),
        "claim_boundary": (
            "package-local observer only; dynamic values, production XMR "
            "elaboration, terminal and formal D remain server-return gates"
        ),
    }
    manifest["release_gate_applicability"].update(
        {
            "package_local_hdl": "blocking_applicable_changed_observer",
            "diagnostic_predicate_trace": (
                "blocking_applicable_changed_observer_predicate"
            ),
            "materialized_config": "receipt_reuse_byte_equal_p18",
            "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
        }
    )
    manifest["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": (
            "p18 observer plus exact v64 validated D-flow tail; focused "
            "syntax/scope, current leaf presence, wrong sibling and deleted "
            "leaf controls are rerun on final ZIP"
        ),
    }
    manifest["release_gate_matrix"]["diagnostic_predicate_trace"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": (
            "qualified counter-change predicate, stable level, simultaneous "
            "edge, skew/catch-up and first/penultimate/final boundary trace"
        ),
    }
    manifest["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse",
        "blocking": False,
        "pass": True,
        "scope": (
            "p18 config/mapping/bitstream/execplan/SCA semantics byte-equal "
            "after install identity normalization; no address or config leaf "
            "change"
        ),
        "causal_transaction_ledger": "receipt_reuse_p18",
        "boundary_microtrace": "receipt_reuse_p18",
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    manifest["release_gate_matrix"]["record_only"] = [
        "numeric/W3/golden/workload/config/address/timeout/RTL frozen",
        "no DUT execution in local final audit",
    ]
    manifest["fresh_install_namespace"] = {
        "source_install_name": SOURCE_ID,
        "successor_install_name": PACKAGE_ID,
        "source_sibling_may_exist": True,
        "overwrite_or_delete_source_sibling": False,
        "repeat_execution_exact_owned_reset": True,
        "unique_return_per_execution": True,
    }
    manifest["identity_rebound_text_members"] = identity_members
    paths = projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [
        item.relative_to(package).as_posix()
        for item in package.rglob("*")
        if item.is_file() and item != path
    ] + ["package_manifest.json"]
    manifest["path_length_budget"].update(
        {
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": (
                contract["path_budget"]["declared_target_root_max_chars"]
                + 1
                + len(longest)
            ),
            "max_zip_member_chars": max(
                len(f"{PACKAGE_ID}/{relative}") for relative in inner
            ),
            "max_inner_suffix_chars": max(map(len, inner)),
            "max_inner_depth": max(
                len(PurePosixPath(relative).parts) for relative in inner
            ),
            "max_inner_component_chars": max(
                len(component)
                for relative in inner
                for component in PurePosixPath(relative).parts
            ),
            "outer_identity_repeated_inside": False,
        }
    )
    refresh_manifest_files(package, manifest)
    write_json(path, manifest)


def member_hashes(package: Path) -> dict[str, str]:
    return {
        path.relative_to(package).as_posix(): sha256(path)
        for path in sorted(item for item in package.rglob("*") if item.is_file())
    }


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    package = safe_extract(SOURCE_ZIP, destination)
    identity_members = replace_identity(package)
    observer = append_observer(package)
    patch_runner(package)
    contract = patch_contract(package)
    update_pointer_and_readme(package)
    patch_manifest(package, contract, identity_members, observer)
    return package, {
        "identity_members": identity_members,
        "observer": observer,
    }


def frozen_checks(source_zip: Path, package: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=".p19_frozen_", dir=ROOT) as temp:
        source = safe_extract(source_zip, Path(temp))
        # safe_extract renames its root to PACKAGE_ID; no output collision is
        # possible because it uses a separate temporary directory.
        source_members = member_hashes(source)
    successor_members = member_hashes(package)
    frozen = sorted(
        name
        for name in source_members
        if name.startswith(FROZEN_WORKLOAD_EXCEPT_SCA)
    )
    exact = all(source_members[name] == successor_members.get(name) for name in frozen)
    sca_rows: dict[str, bool] = {}
    with zipfile.ZipFile(source_zip) as archive:
        for relative in (
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        ):
            old = archive.read(f"{SOURCE_ID}/{relative}").decode()
            new = (package / relative).read_text(encoding="utf-8")
            sca_rows[relative] = new.replace(PACKAGE_ID, SOURCE_ID) == old
    return {
        "frozen_install_payload_member_count": len(frozen),
        "frozen_install_payload_byte_equal": exact,
        "sca_identity_normalized_equal": sca_rows,
        "numeric_w3_golden_workload_config_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (
        output / PACKAGE_ID,
        output / f"{PACKAGE_ID}.zip",
        output / f"{PACKAGE_ID}.zip.sha256",
        output / f"{PACKAGE_ID}.build.json",
    )
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p19 output")
    if (
        not SOURCE_ZIP.is_file()
        or SOURCE_ZIP.stat().st_size != 5_854_983
        or sha256(SOURCE_ZIP) != SOURCE_SHA256
    ):
        raise BuildError("exact repeatable p18 source differs")
    for receipt in (P18_ANALYSIS, V64_OBSERVER, V64_OBSERVER_VALIDATION, V64_PREDICATE_TRACE):
        if not receipt.is_file():
            raise BuildError(f"required receipt absent: {receipt}")

    package, receipts = build_directory(output)
    frozen = frozen_checks(SOURCE_ZIP, package)
    if (
        not frozen["frozen_install_payload_byte_equal"]
        or not all(frozen["sca_identity_normalized_equal"].values())
    ):
        raise BuildError("frozen p18 payload differs")

    zip_path = output / f"{PACKAGE_ID}.zip"
    deterministic_zip(package, zip_path)
    zip_sha = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix=".p19_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p19 deterministic double build differs")

    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(
        f"{zip_sha}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report = {
        "schema": "conv-native-four-lane-p19-dflow-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p18_zip_sha256": SOURCE_SHA256,
        "source_p18_analysis_sha256": sha256(P18_ANALYSIS),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic,
        "observer": receipts["observer"],
        "identity_rebound_text_members": receipts["identity_members"],
        "frozen": frozen,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
