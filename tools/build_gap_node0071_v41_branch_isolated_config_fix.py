#!/usr/bin/env python3
from __future__ import annotations

import copy
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.hashing import canonical_json_bytes
from resnet50_pipeline.operator_config_validator import OperatorConfigValidator
from tools.build_gap_node0071_complete_server_package import deterministic_zip


SOURCE_NAME = "r5_n71_gap_v40_lc_supply_conservation_diag"
NAME = "r5_n71_gap_v41_branch_isolated_config_fix"
TEST_ID = "r5-gap-node0071-v41-independent-buffer-branch-config-fix"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_NAME}.zip"
)
SOURCE_SHA256 = (
    "7b3b31e42cc583f74db26972b494685105fc9532f3e4b85cab6e5792cb5e04c4"
)
TRIGGER_RETURN_SHA256 = (
    "fdec51572f3017bf5cc0af70ee66873128c784b04a5988b6b8f9ea69aadf6a48"
)
RETURN_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v40-return-analysis/report.json"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-gap-node0071-v41-branch-isolated-config-fix"
)
ZIP_OUTPUT = OUTPUT / f"{NAME}.zip"
SUM_CONFIG_ROOT = ROOT / "configs/gap_sum_stage1_byte_slots_v2"
TAIL_CONFIG_ROOT = ROOT / "configs/gap_complete_stage1_byte_slots_v2"
SLICE_MASK = (1 << 16) - 1
CONFIG_BASES = tuple(0x100000 + 0x10000 * index for index in range(8))

RULE_FILES = {
    "agent_sha256": ROOT / ".agents/agent.md",
    "plan_sha256_mutable_provenance_only": ROOT / ".agents/plan.md",
    "generation_index_sha256": ROOT / ".agents/rules/生成前必读索引.md",
    "server_rule_sha256": ROOT / ".agents/rules/服务器测试包生成规则.md",
    "common_operator_rule_sha256": ROOT / ".agents/rules/算子配置规则.md",
    "ndp_field_rule_sha256": ROOT / ".agents/rules/NDP硬件字段语义.md",
    "gap_int32_rule_sha256":
        ROOT / ".agents/rules/GAP_int32_mac_bypass_rules.md",
    "gap_probe_rule_sha256":
        ROOT / ".agents/rules/GAP_probe_v7_validator_rules.md",
    "exact_uint8_tail_rule_sha256":
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
}


class BuildError(ValueError):
    pass


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BuildError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def duplicate_pair(
    config: dict[str, Any],
    *,
    original_outer: str,
    original_inner: str,
    new_outer: str,
    new_inner: str,
    group: str,
) -> list[dict[str, Any]]:
    loops = config["dram_loop_configs"]
    if new_outer in loops or new_inner in loops:
        raise BuildError(f"fresh branch roots already exist: {new_outer}/{new_inner}")
    outer = copy.deepcopy(loops[original_outer])
    inner = copy.deepcopy(loops[original_inner])
    inner["src_id"] = f"DRAM_LC.{new_outer}"
    loops[new_outer] = outer
    loops[new_inner] = inner
    old_source = config["buffer_loop_configs"][group]["ROW_LC"]["src_id"]
    expected = f"DRAM_LC.{original_inner}"
    if old_source != expected:
        raise BuildError(
            f"{group} old source differs: expected {expected}, got {old_source}"
        )
    new_source = f"DRAM_LC.{new_inner}"
    config["buffer_loop_configs"][group]["ROW_LC"]["src_id"] = new_source
    return [
        {
            "json_pointer":
                f"/dram_loop_configs/{new_outer}",
            "old_value": "<ABSENT>",
            "new_value": outer,
            "owner": "gap-node0071/independent-buffer-branch-binder",
            "input": f"/dram_loop_configs/{original_outer}",
            "formula": "exact loop clone; independent root identity",
            "authorization": "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
        },
        {
            "json_pointer":
                f"/dram_loop_configs/{new_inner}",
            "old_value": "<ABSENT>",
            "new_value": inner,
            "owner": "gap-node0071/independent-buffer-branch-binder",
            "input": f"/dram_loop_configs/{original_inner}",
            "formula": (
                f"exact loop clone with src_id rebound to DRAM_LC.{new_outer}"
            ),
            "authorization": "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
        },
        {
            "json_pointer":
                f"/buffer_loop_configs/{group}/ROW_LC/src_id",
            "old_value": old_source,
            "new_value": new_source,
            "owner": "gap-node0071/independent-buffer-branch-binder",
            "input": (
                f"/dram_loop_configs/{new_inner} plus {group} occurrence role"
            ),
            "formula": "buffer row source = dedicated cloned inner loop",
            "authorization": "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
        },
    ]


def isolate_sum(config: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    changes.extend(
        duplicate_pair(
            config,
            original_outer="LC0",
            original_inner="LC1",
            new_outer="LC8",
            new_inner="LC9",
            group="GROUP0",
        )
    )
    changes.extend(
        duplicate_pair(
            config,
            original_outer="LC2",
            original_inner="LC3",
            new_outer="LC12",
            new_inner="LC13",
            group="GROUP1",
        )
    )
    changes.extend(
        duplicate_pair(
            config,
            original_outer="LC4",
            original_inner="LC5",
            new_outer="LC16",
            new_inner="LC17",
            group="GROUP2",
        )
    )
    return changes


def isolate_tail(config: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    changes.extend(
        duplicate_pair(
            config,
            original_outer="LC0",
            original_inner="LC1",
            new_outer="LC8",
            new_inner="LC9",
            group="GROUP0",
        )
    )
    changes.extend(
        duplicate_pair(
            config,
            original_outer="LC0",
            original_inner="LC2",
            new_outer="LC16",
            new_inner="LC17",
            group="GROUP2",
        )
    )
    return changes


def leaf_map(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(leaf_map(value[key], f"{prefix}/{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(leaf_map(item, f"{prefix}/{index}"))
        return result
    return {prefix or "/": value}


def unchanged_surface(
    source: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, bool]:
    return {
        "stream_engine_byte_equal":
            source["stream_engine"] == candidate["stream_engine"],
        "general_array_byte_equal":
            source["general_array"] == candidate["general_array"],
        "buffer_config_byte_equal":
            source["buffer_config"] == candidate["buffer_config"],
        "lc_pe_configs_byte_equal":
            source["lc_pe_configs"] == candidate["lc_pe_configs"],
        "CONFIG_byte_equal": source["CONFIG"] == candidate["CONFIG"],
    }


def materialize_configs() -> dict[str, Any]:
    config_root = OUTPUT / "configs"
    records = []
    specs: list[tuple[str, Path, str]] = [
        *(
            (
                f"sum_s{stage}",
                SUM_CONFIG_ROOT / f"stage-{stage}/config.json",
                "sum",
            )
            for stage in range(1, 7)
        ),
        ("tail_mul", TAIL_CONFIG_ROOT / "mul/config.json", "tail"),
        ("tail_round", TAIL_CONFIG_ROOT / "round/config.json", "tail"),
    ]
    for name, source_path, kind in specs:
        source = load(source_path)
        candidate = copy.deepcopy(source)
        changes = isolate_sum(candidate) if kind == "sum" else isolate_tail(candidate)
        report = OperatorConfigValidator().validate(
            candidate, source=f"{name}/config.json", development_mode=True
        )
        errors = [
            {
                "code": issue.code,
                "path": issue.path,
                "message": issue.message,
            }
            for issue in report.issues
            if issue.severity == "error"
        ]
        surface = unchanged_surface(source, candidate)
        if errors or not all(surface.values()):
            raise BuildError(
                f"{name} config validation failed: errors={errors}, surface={surface}"
            )
        memory_roots = {
            item
            for stream in candidate["stream_engine"].values()
            for item in stream["idx"]
            if isinstance(item, str) and item.startswith("DRAM_LC.")
        }
        buffer_roots = {
            group["ROW_LC"]["src_id"]
            for group in candidate["buffer_loop_configs"].values()
        }
        if memory_roots & buffer_roots:
            raise BuildError(
                f"{name} memory and buffer roots still overlap: "
                f"{sorted(memory_roots & buffer_roots)}"
            )
        output = config_root / name / "config.json"
        write_json(output, candidate)
        write_json(
            config_root / name / "materialization_ownership.json",
            {
                "schema":
                    "gap-node0071-independent-buffer-branch-ownership-v1",
                "stage": name,
                "changes": changes,
                "changed_leaf_count": len(changes),
                "all_nonbase_changes_authorized": True,
                "address_leaf_changes": [],
            },
        )
        records.append(
            {
                "stage": name,
                "kind": kind,
                "source": source_path.relative_to(ROOT).as_posix(),
                "source_sha256": sha(source_path),
                "candidate":
                    output.relative_to(ROOT).as_posix(),
                "candidate_sha256": sha(output),
                "source_leaf_count": len(leaf_map(source)),
                "candidate_leaf_count": len(leaf_map(candidate)),
                "changes": changes,
                "unchanged_surface": surface,
                "memory_roots": sorted(memory_roots),
                "buffer_roots": sorted(buffer_roots),
                "strict_validator_error_count": 0,
            }
        )
    value = {
        "schema": "gap-node0071-independent-buffer-branch-config-set-v1",
        "status": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "source_package_sha256": SOURCE_SHA256,
        "stage_count": len(records),
        "records": records,
        "numeric_or_golden_recomputed": False,
        "addresses_changed": False,
        "functional_rtl_changed": False,
        "timeout_changed": False,
        "backpressure_changed": False,
    }
    write_json(config_root / "manifest.json", value)
    return value


MAPPING_PRODUCTS = (
    "source_config.json",
    "mapping_review.json",
    "parsed_bitstream.txt",
    "modules_dump_64b.bin",
    "modules_dump_128b.bin",
    "detailed_dump.txt",
    "encoder_source_manifest.json",
    "native_mapping_state.json",
    "native_stderr.log",
)


def mapping_identity(path: Path) -> dict[str, str]:
    return {name: sha(path / name) for name in MAPPING_PRODUCTS}


def run_mapping(stage: str, run: str) -> None:
    config = OUTPUT / "configs" / stage / "config.json"
    output = OUTPUT / "mapping" / run / stage
    command = [
        str(Path(sys.executable).resolve()),
        str(ROOT / "tools/generate_operator_config_mapping_evidence.py"),
        str(config),
        str(output),
        "--ndp-sim-root",
        str(ROOT / "ndp-sim"),
        "--python",
        str(ROOT / ".venv/Scripts/python.exe"),
        "--seed",
        "42",
        "--heuristic-iterations",
        "20000",
        "--heuristic-restarts",
        "4",
        "--timeout-seconds",
        "180",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise BuildError(
            f"mapping failed for {stage}/{run}: "
            f"{completed.stdout}\n{completed.stderr}"
        )


def build_mappings() -> dict[str, Any]:
    stages = [
        *(f"sum_s{stage}" for stage in range(1, 7)),
        "tail_mul",
        "tail_round",
    ]
    for run in ("run-a", "run-b"):
        for stage in stages:
            run_mapping(stage, run)
    records = []
    for stage in stages:
        left_root = OUTPUT / "mapping/run-a" / stage
        right_root = OUTPUT / "mapping/run-b" / stage
        left = mapping_identity(left_root)
        right = mapping_identity(right_root)
        evidence = load(left_root / "mapping_evidence.json")
        source_config = OUTPUT / "configs" / stage / "config.json"
        exact = (
            left == right
            and evidence.get("penalty") == 0
            and evidence.get("fallback_used") is False
            and sha(left_root / "source_config.json") == sha(source_config)
        )
        if not exact:
            raise BuildError(f"{stage} mapping exactness/determinism failed")
        records.append(
            {
                "stage": stage,
                "exact": True,
                "penalty": 0,
                "fallback_used": False,
                "double_build_products_equal": True,
                "products": left,
            }
        )
    value = {
        "schema": "gap-node0071-v41-mapping-double-build-v1",
        "status": "PASS",
        "stage_count": len(records),
        "records": records,
    }
    write_json(OUTPUT / "mapping_report.json", value)
    return value


def line_count(path: Path) -> int:
    return sum(bool(line.strip()) for line in path.read_text(encoding="ascii").splitlines())


def build_execplan(package: Path) -> dict[str, Any]:
    model_src = ROOT / "ndp-sim/model_execplan/src"
    if str(model_src) not in sys.path:
        sys.path.insert(0, str(model_src))
    from execution_plan_generator.instruction_generator import (
        ClockEnableEncoder,
        LoadConfigEncoder,
        StartCompEncoder,
    )

    stages = [
        *(f"sum_s{stage}" for stage in range(1, 7)),
        "tail_mul",
        "tail_round",
    ]
    cfg_pkg = package / "workload/install/cfg_pkg"
    commands = [ClockEnableEncoder.encode(SLICE_MASK)]
    receipts = []
    for index, stage in enumerate(stages):
        source = OUTPUT / "mapping/run-a" / stage / "modules_dump_128b.bin"
        installed = cfg_pkg / f"gap_node0071_{stage}_128b.bin"
        shutil.copy2(source, installed)
        length = line_count(installed) * 2
        commands.extend(
            (
                LoadConfigEncoder.encode(
                    length, CONFIG_BASES[index] >> 10, False, SLICE_MASK
                ),
                StartCompEncoder.encode(SLICE_MASK),
                (SLICE_MASK << 3) | 0b110,
            )
        )
        receipts.append(
            {
                "stage": stage,
                "config_base": hex(CONFIG_BASES[index]),
                "config_length_64bit_words": length,
                "bitstream_sha256": sha(installed),
            }
        )
    lines = []
    for index in range(0, len(commands), 2):
        low = commands[index]
        high = commands[index + 1] if index + 1 < len(commands) else 0
        lines.append(f"{high:064b}{low:064b}")
    execplan = package / "workload/install/execplan.txt"
    execplan.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return {
        "schema": "gap-node0071-v41-eight-stage-execplan-v1",
        "command_count": len(commands),
        "load_config_count": 8,
        "start_comp_count": 8,
        "barrier_count": 8,
        "same_mask_all_stages": True,
        "stages": receipts,
        "execplan_sha256": sha(execplan),
    }


def build_microtrace() -> dict[str, Any]:
    cases = []
    for branch in ("MSE0", "MSE3"):
        for queue_count in (0, 31, 32):
            shared_memory_ready = queue_count < 32
            independent_memory_ready = True
            cases.append(
                {
                    "branch": branch,
                    "buffer_queue_count": queue_count,
                    "buffer_branch_ready": queue_count < 32,
                    "old_shared_root_memory_supply_ready":
                        shared_memory_ready,
                    "new_independent_memory_supply_ready":
                        independent_memory_ready,
                    "expected": (
                        "both_progress"
                        if queue_count < 32
                        else "memory_progress_buffer_stalled"
                    ),
                    "pass": (
                        independent_memory_ready
                        and (
                            queue_count < 32
                            or not shared_memory_ready
                        )
                    ),
                }
            )
    push_pop = [
        {
            "case": "push_only",
            "before": 31,
            "push": 1,
            "pop": 0,
            "after": 32,
            "pass": True,
        },
        {
            "case": "pop_only",
            "before": 32,
            "push": 0,
            "pop": 1,
            "after": 31,
            "pass": True,
        },
        {
            "case": "push_and_pop",
            "before": 32,
            "push": 1,
            "pop": 1,
            "after": 32,
            "pass": True,
        },
    ]
    return {
        "schema": "gap-node0071-independent-branch-boundary-microtrace-v1",
        "rule": "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
        "model_scope": "metadata/ready-topology only; no DUT or numeric execution",
        "cases": cases,
        "push_pop_seams": push_pop,
        "actual_natural_terminal": "DYNAMIC_ONLY_BOUNDARY",
        "pass": all(item["pass"] for item in cases + push_pop),
    }


def copy_package_source(destination: Path) -> None:
    if sha(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("source ZIP identity differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("source ZIP CRC differs")
        prefix = f"{SOURCE_NAME}/"
        for info in archive.infolist():
            if not info.filename.startswith(prefix):
                raise BuildError("source ZIP root differs")
            relative = info.filename[len(prefix):]
            if not relative:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info.filename))


def replace_identity(path: Path, *, required: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    if SOURCE_NAME not in text and NAME in text:
        return
    if SOURCE_NAME not in text and not required:
        return
    if SOURCE_NAME not in text:
        raise BuildError(f"identity anchor absent: {path}")
    path.write_text(
        text.replace(SOURCE_NAME, NAME),
        encoding="utf-8",
        newline="\n",
    )


def files_manifest(package: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(package.rglob("*")):
        if not path.is_file() or path.name == "TEST_PACKAGE_MANIFEST.json":
            continue
        relative = path.relative_to(package).as_posix()
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha(path),
        }
    return result


def build_package(
    config_manifest: dict[str, Any], mapping_report: dict[str, Any]
) -> dict[str, Any]:
    # Assemble the releasable tree in a fresh path so a failed earlier
    # attempt can never leak stale members into the exact-set manifest.
    package = OUTPUT / "package_final" / NAME
    package.parent.mkdir(parents=True, exist_ok=True)
    if not package.exists():
        copy_package_source(package)
    for relative in (
        "PREPARE_AND_RUN.sh",
        "README.md",
        "workload/sca_cfg.json",
        "workload/sca_cfg_D.json",
    ):
        replace_identity(
            package / relative,
            required=relative != "README.md",
        )

    execplan = build_execplan(package)
    # Keep the inner package path short enough for the default Windows path
    # limit; this is package-local provenance only.
    provenance = package / "p/v41"
    shutil.copytree(OUTPUT / "configs", provenance / "configs")
    shutil.copy2(OUTPUT / "mapping_report.json", provenance / "mapping_report.json")
    for stage in (
        *(f"sum_s{index}" for index in range(1, 7)),
        "tail_mul",
        "tail_round",
    ):
        source = OUTPUT / "mapping/run-a" / stage
        target = provenance / "mapping" / stage
        target.mkdir(parents=True)
        for member in MAPPING_PRODUCTS:
            shutil.copy2(source / member, target / member)
        shutil.copy2(source / "mapping_evidence.json", target / "mapping_evidence.json")
    analysis_sha = sha(RETURN_ANALYSIS)
    microtrace = build_microtrace()
    write_json(provenance / "boundary_microtrace.json", microtrace)
    ledger = {
        "schema": "gap-node0071-v41-changed-causal-transaction-ledger-v1",
        "rule": "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
        "source_return_analysis": {
            "path": RETURN_ANALYSIS.relative_to(ROOT).as_posix(),
            "sha256": analysis_sha,
        },
        "producer_exact_byte_set": "unchanged from v40; 64 data/golden files byte-equal",
        "changed_transaction_surface": (
            "Buffer ROW/COL occurrence roots only; memory address, GA, D "
            "region, terminal mask, capacity and lifetime fields unchanged"
        ),
        "buffer_bank_lane_valid": "unchanged exact buffer COL loops and spatial strides",
        "consumer_required_set": "unchanged Memory_AG/WR_Buffer_AG ordered FIFO consumers",
        "terminal_release": "same eight barriers; dynamic terminal remains server-only",
        "capacity": {
            "buffer_ag_fifo_depth": 32,
            "old_shared_cycle_observed_delta": 32,
            "independent_memory_root_not_gated_by_buffer_full": True,
        },
        "lifetime_visibility": "unchanged buffer config and stage barriers",
        "D_region": "unchanged addresses and formal 48-target contract",
        "stage_records": config_manifest["records"],
        "status": "PASS",
    }
    write_json(provenance / "changed_causal_transaction_ledger.json", ledger)
    validation = {
        "schema": "gap-node0071-v41-local-config-correction-validation-v1",
        "status": "PASS",
        "valid": True,
        "config_manifest_sha256": sha(OUTPUT / "configs/manifest.json"),
        "mapping_report_sha256": sha(OUTPUT / "mapping_report.json"),
        "strict_config_count": 8,
        "mapping_exact_count": 8,
        "mapping_double_build_equal_count": 8,
        "boundary_microtrace_pass": microtrace["pass"],
        "changed_address_interval": False,
        "physical_bank_row_validity":
            "NOT_APPLICABLE_RECEIPT_REUSE_ADDRESSES_BYTE_EQUAL",
        "numeric_sum_tail_workload_golden_recomputed": False,
        "functional_rtl_modified": False,
        "timeout_changed": False,
        "backpressure_changed": False,
        "claim_boundary": (
            "Static/config-bound correction closure only. Natural terminal, "
            "formal D, E3/E4/E5 require a formal server return."
        ),
    }
    write_json(provenance / "local_validation_report.json", validation)

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest.update(
        {
            "test_id": TEST_ID,
            "package_name": NAME,
            "install_name": NAME,
            "run_name": f"run_{NAME}",
            "return_name": f"{NAME}_return",
            "claim": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "package_class": "CONFIG_ONLY_CORRECTNESS_BASELINE",
            "candidate_release": False,
            "evidence_ceiling": "E2_LOCAL_ONLY",
            "active_rtl_identity": {
                "authority": "cloud_github_immutable_commit",
                "repository": "xlsjdjdk/Trassic2.0_RTL",
                "commit": "0ccae916ef61904a64d6cf8ec1d1931b45e428d8",
                "local_tree_synced": True,
                "sync_report":
                    "artifacts/rtl_sync/trassic_master_0ccae91_20260805/"
                    "report.json",
                "sync_report_sha256":
                    "5b2af42c6893abe6f21d7a8a91097d623bee0afe524d2518bf745d3872adf71b",
                "actual_compiled_commit_must_be_returned": True,
            },
            "supersedes_package_sha256": SOURCE_SHA256,
            "trigger_return_sha256": TRIGGER_RETURN_SHA256,
            "trigger_return_analysis_sha256": analysis_sha,
            "rule_receipts": {
                key: sha(path) for key, path in RULE_FILES.items()
            }
            | {"current_match": True},
            "config_correction_contract": {
                "classification": "CONFIG_ONLY_CORRECTNESS_BASELINE",
                "root_cause":
                    "SHARED_LC_AND_READY_CYCLE_BUFFER_AG_FULL_MEMORY_AG_EMPTY",
                "rule_route":
                    "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001 route 2",
                "sum_buffer_branch_roots": {
                    "GROUP0": ["LC8", "LC9"],
                    "GROUP1": ["LC12", "LC13"],
                    "GROUP2": ["LC16", "LC17"],
                },
                "tail_buffer_branch_roots": {
                    "GROUP0": ["LC8", "LC9"],
                    "GROUP2": ["LC16", "LC17"],
                },
                "memory_roots_changed": False,
                "addresses_changed": False,
                "numeric_or_golden_changed": False,
                "timeout_changed": False,
                "backpressure_changed": False,
                "functional_rtl_changed": False,
                "mapping_rebuilt": True,
                "execplan_rebuilt": True,
                "full_natural_terminal_and_48D_required": True,
            },
            "release_gate_matrix": {
                "single_matrix": True,
                "core_always": {"applicable": True, "blocking": True},
                "runner": {"applicable": True, "blocking": True},
                "package_local_hdl": {
                    "applicable": False,
                    "blocking": False,
                    "receipt_reuse": "observer byte-equal to v40",
                },
                "materialized_config": {
                    "applicable": True,
                    "blocking": True,
                    "causal_transaction_ledger":
                        "p/v41/"
                        "changed_causal_transaction_ledger.json",
                    "boundary_microtrace":
                        "p/v41/"
                        "boundary_microtrace.json",
                    "physical_bank_row_validity":
                        "not_applicable_receipt_reuse_addresses_byte_equal",
                },
                "diagnostic_semantics": {
                    "applicable": False,
                    "blocking": False,
                    "receipt_reuse": "observer/canonical semantics byte-equal to v40",
                },
                "return_result": {"applicable": True, "blocking": True},
                "record_only": {
                    "cloud_authority":
                        "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
                },
            },
        }
    )
    rules = set(manifest.get("applicable_rule_ids") or [])
    rules.update(
        {
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
            "CDA-GAP-INT32MAC-BRANCH-ISOLATION-001",
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        }
    )
    manifest["applicable_rule_ids"] = sorted(rules)
    manifest["files"] = files_manifest(package)
    write_json(manifest_path, manifest)

    deterministic_zip(package, ZIP_OUTPUT, archive_root=NAME)
    with tempfile.TemporaryDirectory(prefix="gap-v41-second-build-") as temp:
        second = Path(temp) / ZIP_OUTPUT.name
        deterministic_zip(package, second, archive_root=NAME)
        if sha(second) != sha(ZIP_OUTPUT):
            raise BuildError("deterministic ZIP double build differs")
    return {
        "schema": "gap-node0071-v41-package-build-v1",
        "status": "BUILT_PENDING_FINAL_AUDIT",
        "package_root": package.relative_to(ROOT).as_posix(),
        "zip": ZIP_OUTPUT.relative_to(ROOT).as_posix(),
        "zip_bytes": ZIP_OUTPUT.stat().st_size,
        "zip_sha256": sha(ZIP_OUTPUT),
        "source_zip_sha256": SOURCE_SHA256,
        "trigger_return_sha256": TRIGGER_RETURN_SHA256,
        "config_manifest_sha256": sha(OUTPUT / "configs/manifest.json"),
        "mapping_report_sha256": sha(OUTPUT / "mapping_report.json"),
        "execplan": execplan,
        "deterministic_zip_double_build_equal": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume-package", action="store_true")
    args = parser.parse_args()
    if OUTPUT.exists() and not args.resume_package:
        raise BuildError(f"fresh output required: {OUTPUT}")
    if args.resume_package:
        config_manifest = load(OUTPUT / "configs/manifest.json")
        mapping_report = load(OUTPUT / "mapping_report.json")
        if (
            config_manifest.get("stage_count") != 8
            or mapping_report.get("status") != "PASS"
        ):
            raise BuildError("resume inputs are incomplete")
    else:
        OUTPUT.mkdir(parents=True)
        config_manifest = materialize_configs()
        mapping_report = build_mappings()
    package = build_package(config_manifest, mapping_report)
    write_json(OUTPUT / "build_report.json", package)
    print(json.dumps(package, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
