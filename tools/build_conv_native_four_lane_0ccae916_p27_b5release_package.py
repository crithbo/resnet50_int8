#!/usr/bin/env python3
"""Build p27 with the required source-bound Buffer5 release observer."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p26_memag_package as previous


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p26_memag"
PACKAGE_ID = "r5_n4_0cc_p27_b5release"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_881_902
SOURCE_SHA256 = "844360af973a6687fe9b0e202e169cfe176df42000859fbd88a15b559b3cce25"
P26_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p26_return_analysis/report.json"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p27_b5release_source_bound"
GENERATED = SOURCE_BOUND / "generated"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p27_b5release/build"
LEGACY_OBSERVER = "tb_probe/native_return_observer.svh"
SOURCE_LEGACY_OBSERVER_SHA256 = "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1"
base = previous.base
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def replace_identity(package: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in base.TEXT_SUFFIXES:
            continue
        payload = path.read_bytes()
        if SOURCE_ID.encode() not in payload:
            continue
        path.write_text(
            payload.decode().replace(SOURCE_ID, PACKAGE_ID),
            encoding="utf-8",
            newline="\n",
        )
        changed.append(path.relative_to(package).as_posix())
    required = {
        "PREPARE_AND_RUN.sh",
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json",
        "package_manifest.json",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    if not required <= set(changed):
        raise BuildError(f"identity rebinding surface differs: {sorted(required - set(changed))}")
    return changed


def install_generated(package: Path) -> dict[str, dict[str, Any]]:
    generation = json.loads((SOURCE_BOUND / "source_bound_generation_report.json").read_text(encoding="utf-8"))
    cheap = json.loads((SOURCE_BOUND / "source_bound_observer_generation.json").read_text(encoding="utf-8"))
    if generation.get("pass") is not True or generation.get("errors") or cheap.get("pass") is not True:
        raise BuildError("source-bound generation gate is not PASS")
    mapping = {
        SOURCE_BOUND / "source_bound_probe_catalog.json": package / "diagnostics/source_bound_probe_catalog.json",
        SOURCE_BOUND / "source_bound_probe_plan.json": package / "diagnostics/source_bound_probe_plan.json",
        SOURCE_BOUND / "source_bound_generation_report.json": package / "diagnostics/source_bound_generation_report.json",
        SOURCE_BOUND / "source_bound_observer_generation.json": package / "diagnostics/source_bound_observer_generation.json",
        GENERATED / "source_bound_probe_binding.json": package / "diagnostics/source_bound_probe_binding.json",
        GENERATED / "source_bound_causal_observer.svh": package / "tb_probe/source_bound_causal_observer.svh",
        GENERATED / "source_bound_observer_focus.sv": package / "tb_probe/source_bound_observer_focus.sv",
        GENERATED / "source_bound_causal_parser.py": package / "package_tools/source_bound_causal_parser.py",
    }
    receipts: dict[str, dict[str, Any]] = {}
    for source, target in mapping.items():
        if not source.is_file():
            raise BuildError(f"generated source is absent: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        relative = target.relative_to(package).as_posix()
        receipts[relative] = {
            "bytes": target.stat().st_size,
            "sha256": base.sha256(target),
        }
    contract = {
        "schema": "server-source-bound-final-zip-contract-v1",
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "enforcement": "required_next_fresh",
        "members": {
            "catalog": "diagnostics/source_bound_probe_catalog.json",
            "plan": "diagnostics/source_bound_probe_plan.json",
            "observer": "tb_probe/source_bound_causal_observer.svh",
            "parser": "package_tools/source_bound_causal_parser.py",
            "binding": "diagnostics/source_bound_probe_binding.json",
            "generation_report": "diagnostics/source_bound_generation_report.json",
            "runner": "PREPARE_AND_RUN.sh",
        },
        "compile_observer_token": "source_bound_causal_observer.svh",
        "runtime_plusarg": "+CODEX_CAUSAL_OBSERVER",
        "return_log_token": "source_bound_causal.log",
        "return_decision_token": "source_bound_causal_decision.json",
        "claim_boundary": (
            "p27 source-bound Buffer5 c0 diagnostic only; production compile/simulation, natural terminal, "
            "formal D, E3, E4 and E5 remain dynamic and unclaimed."
        ),
    }
    target = package / "diagnostics/source_bound_final_zip_contract.json"
    write_json(target, contract)
    receipts[target.relative_to(package).as_posix()] = {
        "bytes": target.stat().st_size,
        "sha256": base.sha256(target),
    }
    return receipts


def patch_runner(package: Path) -> dict[str, Any]:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = 'observer_guard="$package_root/package_tools/node0004_package_observer_guard.py"\n'
    insertion = (
        anchor
        + 'source_bound_parser="$package_root/package_tools/source_bound_causal_parser.py"\n'
        + 'source_bound_observer="$package_root/tb_probe/source_bound_causal_observer.svh"\n'
    )
    if text.count(anchor) != 1 or "source_bound_parser=" in text:
        raise BuildError("runner source-bound variable anchor differs")
    text = text.replace(anchor, insertion)

    compile_token = "+define+NATIVE_RETURN_OBSERVER_ENABLE +incdir+$package_root/tb_probe"
    compile_replacement = compile_token + " $source_bound_observer"
    if text.count(compile_token) != 2:
        raise BuildError("runner production compile option surface differs")
    text = text.replace(compile_token, compile_replacement)

    sim_print_token = "+vcs+lic+wait +SCA_CFG="
    sim_exec_token = '+vcs+lic+wait "+SCA_CFG='
    if text.count(sim_print_token) != 1 or text.count(sim_exec_token) != 1:
        raise BuildError("runner simulation argument surface differs")
    text = text.replace(sim_print_token, "+vcs+lic+wait +CODEX_CAUSAL_OBSERVER +SCA_CFG=")
    text = text.replace(sim_exec_token, '+vcs+lic+wait +CODEX_CAUSAL_OBSERVER "+SCA_CFG=')

    analyze_anchor = '  python3 "$runtime" analyze --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root"\n'
    analyze_insertion = (
        '  source_bound_log="$run_root/c0/source_bound_causal.log"\n'
        '  source_bound_decision="$evidence_root/source_bound_causal_decision.json"\n'
        '  if [ -s "$run_root/c0/sim.log" ]; then\n'
        '    grep \'^CODEX_PROBE_V1 \' "$run_root/c0/sim.log" > "$source_bound_log" || true\n'
        '  else\n'
        '    : > "$source_bound_log"\n'
        '  fi\n'
        '  python3 "$source_bound_parser" --log "$source_bound_log" --output "$source_bound_decision" >/dev/null 2>&1 || true\n'
        + analyze_anchor
    )
    if text.count(analyze_anchor) != 1 or "source_bound_causal_decision.json" in text:
        raise BuildError("runner finalizer integration anchor differs")
    text = text.replace(analyze_anchor, analyze_insertion)
    path.write_text(text, encoding="utf-8", newline="\n")
    required = (
        "source_bound_causal_observer.svh",
        "+CODEX_CAUSAL_OBSERVER",
        "source_bound_causal.log",
        "source_bound_causal_decision.json",
    )
    if any(token not in text for token in required):
        raise BuildError("runner source-bound four-way binding is incomplete")
    return {
        "path": "PREPARE_AND_RUN.sh",
        "sha256": base.sha256(path),
        "compile_source_occurrences": text.count("$source_bound_observer"),
        "runtime_plusarg_occurrences": text.count("+CODEX_CAUSAL_OBSERVER"),
        "parser_invocation_occurrences": text.count('python3 "$source_bound_parser"'),
        "return_log_token_occurrences": text.count("source_bound_causal.log"),
        "return_decision_token_occurrences": text.count("source_bound_causal_decision.json"),
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p27 mechanically preserves p26 installed payload/config and adds the required generated, source-bound "
        "Buffer5 release observer/parser under the existing install-only V2 runtime layout."
    )
    paths = base.projected_paths(package, value)
    longest = max(paths, key=lambda item: (len(item), item))
    value["path_budget"]["max_projected_absolute_path_chars"] = (
        value["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    )
    write_json(path, value)
    return value


def patch_pointer_readme(package: Path) -> None:
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-p27-source-bound-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p27 source-bound Buffer5 release diagnostic\n\n"
        "Fresh c0 successor of formal p26. The 87 installed payload members remain byte-identical. "
        "The new Buffer/Memory_Req_Manager diagnostic is generated from the pinned 0cc RTL symbol catalog.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_manifest(
    package: Path,
    contract: dict[str, Any],
    changed: list[str],
    runner: dict[str, Any],
    generated: dict[str, dict[str, Any]],
) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P26_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P26_ACTUAL_MEMORY_AG_FLOW_PASS_BUFFER5_RELEASE_SUCCESSOR_REQUIRED":
        raise BuildError("formal p26 analysis is not accepted")
    legacy = package / LEGACY_OBSERVER
    if base.sha256(legacy) != SOURCE_LEGACY_OBSERVER_SHA256:
        raise BuildError("exact inherited p26 observer identity differs")
    value.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p27-source-bound-package-v1",
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
            "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
            "rule_receipts": [
                {
                    "path": relative,
                    "bytes": (ROOT / relative).stat().st_size,
                    "sha256": base.sha256(ROOT / relative),
                }
                for relative in RULE_PATHS
            ],
            "rule_receipts_current_match": True,
        }
    )
    value["source_p26_formal_return_analysis"] = {
        "path": P26_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": base.sha256(P26_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"],
        "compile_exit_status": 0,
        "run_exit_status": 125,
        "signal_status": "INT",
        "actual_memory_ag_queue_write_read_passed": True,
        "buffer_ag_downstream_accept_passed": True,
        "c0_natural_terminal": False,
        "formal_D_claimed": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p26 moved the first divergence to Buffer5 occupied-row release after actual Memory_AG flow",
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["source_bound_observer_binding"] = {
        "rule_id": "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
        "enforcement": "required_next_fresh",
        "rtl_tree_sha256": "c6902de6fabfce81ee10af02cec238e5b11d2fdece9454041415c455556e1093",
        "generated_members": generated,
        "runner": runner,
        "functional_rtl_changed": False,
        "legacy_observer_byte_equal_p26": True,
        "claim_boundary": "c0 Buffer5 last-write/read-response timing only",
    }
    value["observer_binding"].update(
        {
            "sha256": SOURCE_LEGACY_OBSERVER_SHA256,
            "source_sha256": SOURCE_LEGACY_OBSERVER_SHA256,
            "size_bytes": legacy.stat().st_size,
            "changed_in_p27": False,
            "production_compile_receipt_reuse": "formal p26 compile_exit_status=0 exact inherited observer bytes",
        }
    )
    allowlist = value.get("return_allowlist")
    if not isinstance(allowlist, list):
        raise BuildError("source return allowlist differs")
    additions = [
        {
            "source_root": "run",
            "source_path": "c0/source_bound_causal.log",
            "target_path": "runs/c0/source_bound_causal.log",
            "required": False,
            "max_bytes": 16777216,
            "missing_semantics": "absent only before DUT simulation or before source-bound logger initialization",
        },
        {
            "source_root": "evidence",
            "source_path": "source_bound_causal_decision.json",
            "target_path": "evidence/source_bound_causal_decision.json",
            "required": False,
            "max_bytes": 2097152,
            "missing_semantics": "absent only before the shared finalizer can invoke the generated parser",
        },
    ]
    existing_targets = {item.get("target_path") for item in allowlist if isinstance(item, dict)}
    for item in additions:
        if item["target_path"] in existing_targets:
            raise BuildError("source-bound return member already exists")
        allowlist.append(item)
    value["return_budget"]["uncompressed_max_bytes"] = max(
        int(value["return_budget"]["uncompressed_max_bytes"]), 48 * 1024 * 1024
    )
    value["return_budget"]["zip_max_bytes"] = max(
        int(value["return_budget"]["zip_max_bytes"]), 32 * 1024 * 1024
    )
    value["release_gate_applicability"].update(
        {
            "package_local_hdl": "blocking_applicable_generated_source_bound_observer",
            "diagnostic_predicate_trace": "blocking_applicable_generated_exact_logic",
            "runner_control_flow": "blocking_applicable_compile_runtime_parser_return_binding",
            "materialized_config": "receipt_reuse_byte_equal_p26",
            "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
            "source_bound_observer_generation": "blocking_applicable_required_next_fresh",
            "source_bound_final_zip": "blocking_applicable_required_next_fresh",
        }
    )
    value["release_gate_matrix"].update(
        {
            "package_local_hdl": {
                "applicability": "blocking_applicable",
                "blocking": True,
                "pass": True,
                "scope": "generated source-bound observer focused syntax PASS; production compile remains dynamic",
            },
            "diagnostic_semantics": {
                "applicability": "blocking_applicable",
                "blocking": True,
                "pass": True,
                "scope": "generated logger/parser/binding share one exact machine plan and bitmap multiclass encoding",
            },
            "diagnostic_multiclass_edge_no_loss": {
                "applicability": "blocking_applicable",
                "blocking": True,
                "pass": True,
                "scope": "generated BITMAP_ALL_TRUE_CLASSES with separate qualified/state rings",
            },
            "runner_control_flow": {
                "applicability": "blocking_applicable",
                "blocking": True,
                "pass": True,
                "scope": "exact compile source, runtime plusarg, log extraction, generated parser and return allowlist binding",
            },
            "materialized_config": {
                "applicability": "receipt_reuse",
                "blocking": False,
                "pass": True,
                "scope": "87 p26 installed payload members byte-equal and SCA identity-normalized equal",
                "causal_transaction_ledger": "receipt_reuse_p18",
                "boundary_microtrace": "receipt_reuse_p18",
                "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
            },
            "source_bound_observer_generation": {
                "applicability": "blocking_applicable",
                "blocking": True,
                "pass": True,
                "enforcement": "required_next_fresh",
                "scope": "catalog plus symbol-id plan generated exact observer/parser/binding with focused syntax PASS",
            },
            "source_bound_final_zip": {
                "applicability": "blocking_applicable",
                "blocking": True,
                "pass": None,
                "enforcement": "required_next_fresh",
                "scope": "filled by exact final-ZIP regeneration validator",
            },
        }
    )
    value["identity_rebound_text_members"] = changed
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [
        item.relative_to(package).as_posix()
        for item in package.rglob("*")
        if item.is_file() and item != path
    ] + ["package_manifest.json"]
    value["path_length_budget"].update(
        {
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
            "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
            "max_inner_suffix_chars": max(map(len, inner)),
            "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
            "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
            "outer_identity_repeated_inside": False,
        }
    )
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    package = base.safe_extract(SOURCE_ZIP, destination)
    changed = replace_identity(package)
    generated = install_generated(package)
    runner = patch_runner(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, changed, runner, generated)
    return package, {"identity_members": changed, "runner": runner, "generated": generated}


def frozen_checks(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source = {
            name[len(SOURCE_ID) + 1 :]: archive.read(name)
            for name in archive.namelist()
            if name.startswith(SOURCE_ID + "/") and not name.endswith("/")
        }
    frozen = sorted(name for name in source if name.startswith("workload/runtime/runs/c0/install/"))
    exact = all((package / name).read_bytes() == source[name] for name in frozen)
    sca: dict[str, bool] = {}
    for relative in (
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    ):
        sca[relative] = (
            (package / relative).read_text(encoding="utf-8").replace(PACKAGE_ID, SOURCE_ID)
            == source[relative].decode()
        )
    return {
        "frozen_install_payload_member_count": len(frozen),
        "frozen_install_payload_byte_equal": exact,
        "sca_identity_normalized_equal": sca,
        "legacy_observer_byte_equal": (package / LEGACY_OBSERVER).read_bytes() == source[LEGACY_OBSERVER],
        "numeric_w3_golden_workload_config_mapping_bitstream_execplan_changed": False,
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
    if any(target.exists() for target in targets):
        raise BuildError("refusing to overwrite p27 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p26 source differs")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if (
        not frozen["frozen_install_payload_byte_equal"]
        or not frozen["legacy_observer_byte_equal"]
        or not all(frozen["sca_identity_normalized_equal"].values())
        or frozen["frozen_install_payload_member_count"] != 87
    ):
        raise BuildError("frozen p26 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p27_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeat_zip = Path(temporary) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p27 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(
        f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "conv-native-four-lane-p27-source-bound-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p26_zip_sha256": SOURCE_SHA256,
        "source_p26_analysis_sha256": base.sha256(P26_ANALYSIS),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic,
        "runner": receipts["runner"],
        "generated": receipts["generated"],
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
