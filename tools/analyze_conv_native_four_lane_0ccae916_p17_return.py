#!/usr/bin/env python3
"""Validate and adjudicate the formal native-four-lane p17 return."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\Downloads\r5_n4_0cc_p17_gxmr_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n4_0cc_p17_gxmr.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p17_return_analysis"
    / "report.json"
)
PACKAGE_ID = "r5_n4_0cc_p17_gxmr"
RETURN_ROOT = f"{PACKAGE_ID}_return"
RETURN_BYTES = 2_095_774
RETURN_SHA256 = (
    "5c345560ab943c2875879cd5dab75b185fc6311d6d07d5429bb7ebb67c3d30d4"
)
SOURCE_BYTES = 45_937_639
SOURCE_SHA256 = (
    "3828628f2573c3cd970330fba60bd3393b305555085c5517ea074a919f40a978"
)
V61_REPORT = ROOT / "outputs/conv_node0004_v61_return_analysis/report.json"
CONFIG = (
    ROOT
    / "configs/native_ndp_sim/r5_conv_native_four_lane_0cc_p9_tx5_c0"
    / "accumulate_waves/wave-0.json"
)
KEEP_RTL = (
    ROOT
    / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE"
    / "IGA_PE_Inbuffer.sv"
)
RULE_PATHS = [
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
]


class AnalysisError(RuntimeError):
    pass


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise AnalysisError(f"refusing to overwrite formal analysis: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_records(
    archive: zipfile.ZipFile, expected_root: str
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    errors: list[str] = []
    seen: set[str] = set()
    bad = archive.testzip()
    if bad is not None:
        errors.append(f"CRC:{bad}")
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            not pure.parts
            or pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or pure.parts[0] != expected_root
            or info.filename in seen
            or stat.S_ISLNK(mode)
        ):
            errors.append(info.filename)
            continue
        seen.add(info.filename)
        if info.is_dir():
            continue
        payload = archive.read(info)
        relative = PurePosixPath(*pure.parts[1:]).as_posix()
        records[relative] = {
            "size_bytes": len(payload),
            "sha256": digest(payload),
        }
        payloads[relative] = payload
    return records, payloads, errors


def fields(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", line)
    }


def parse_triggered(text: str) -> dict[str, Any]:
    records = [
        fields(line)
        for line in text.splitlines()
        if line.startswith("N4T_TRIGGER_V1 ")
    ]
    no_progress = [
        row for row in records if row.get("trigger") == "NO_PROGRESS_WINDOW"
    ]
    last = no_progress[-1] if no_progress else {}
    return {
        "record_count": len(records),
        "no_progress_count": len(no_progress),
        "no_progress_key_totals": [
            int(row.get("key_total", "0"), 0) for row in no_progress
        ],
        "no_progress_digests": [row.get("digest") for row in no_progress],
        "four_identical_qualified_windows": (
            len(no_progress) == 4
            and len({row.get("key_total") for row in no_progress}) == 1
            and len({row.get("digest") for row in no_progress}) == 1
        ),
        "last": last,
    }


def record_map(value: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in value[key]
    }


def main() -> int:
    if not RETURN_ZIP.is_file() or not SOURCE_ZIP.is_file():
        raise AnalysisError("exact p17 return/source is absent")
    if not V61_REPORT.is_file() or not CONFIG.is_file() or not KEEP_RTL.is_file():
        raise AnalysisError("required current causal receipt is absent")

    with zipfile.ZipFile(RETURN_ZIP) as archive:
        records, payloads, return_errors = safe_records(archive, RETURN_ROOT)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source_records, source_payloads, source_errors = safe_records(
            archive, PACKAGE_ID
        )

    manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(payloads["evidence/production_rtl_identity.json"])
    package_preflight = json.loads(payloads["evidence/package_preflight.json"])
    install_preflight = json.loads(payloads["evidence/install_preflight.json"])
    observer_preflight = json.loads(
        payloads["evidence/observer_precompile.json"]
    )
    path_budget = json.loads(payloads["evidence/path_budget.json"])
    root_gate = json.loads(payloads["evidence/ndp_root_toplevel_gate.json"])
    layout = json.loads(payloads["evidence/runtime_layout_receipt.json"])
    local_status = json.loads(
        payloads["evidence/package_local_preflight_status.json"]
    )
    public = json.loads(payloads["evidence/public_order_summary.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    triggered_summary = json.loads(
        payloads["evidence/triggered_causal_summary.json"]
    )
    triggered = parse_triggered(
        payloads["runs/c0/triggered_observer.log"].decode(errors="replace")
    )
    compile_log = payloads["runs/compile/compile_driver.log"].decode(
        errors="replace"
    )
    sim_log = payloads["runs/c0/sim.log"].decode(errors="replace")
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()

    declared = record_map(manifest, "records_excluding_this_manifest")
    expected = set(declared) | {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"}
    declared_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in declared.items()
        if records.get(path) != row
    }
    allowed = record_map(allowlist, "records")
    allowed_set = set(allowed) | {"RETURN_ALLOWLIST.json"}
    allowed_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in allowed.items()
        if records.get(path) != row
    }
    source_files = {
        path: row
        for path, row in source_records.items()
        if path != "package_manifest.json"
    }
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    returned_source_manifest = payloads[
        "source_package/package_manifest.json"
    ]

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    pe1 = config["lc_pe_configs"]["PE1"]
    v61 = json.loads(V61_REPORT.read_text(encoding="utf-8"))
    root_cause = v61["HANG_ROOT_CAUSE"]
    keep_line = next(
        (
            index
            for index, line in enumerate(
                KEEP_RTL.read_text(encoding="utf-8").splitlines(), 1
            )
            if "iga_pe_inbuffer_bp_pre_keep_mask" in line
        ),
        None,
    )
    buffer_last_index = 3
    configured_keep = pe1["inport0"]["keep_last_index"]
    direct_predicate = {
        "buffer_last_bit": 1,
        "buffer_last_index": buffer_last_index,
        "configured_keep_last_index": configured_keep,
        "old_ready": int(not (buffer_last_index > configured_keep)),
        "required_keep_last_index": 3,
        "corrected_ready": int(not (buffer_last_index > 3)),
    }

    compile_has_xmre = bool(
        re.search(
            r"Error-\[XMRE\]|Cross-module reference resolution error",
            compile_log,
            flags=re.IGNORECASE,
        )
    )
    compile_success = (
        compile_status == 0
        and not compile_has_xmre
        and (
            "Verdi KDB elaboration finished with 0 error(s)" in compile_log
            or "Verdi KDB elaboration done" in compile_log
        )
    )
    simulation_started = (
        "N4T_FEATURE_ENABLE_V1" in payloads[
            "runs/c0/triggered_observer.log"
        ].decode(errors="replace")
        and "N4B5_FEATURE_ENABLE_V1" in payloads[
            "runs/c0/buffer5_public_observer.log"
        ].decode(errors="replace")
        and "N4P_FEATURE_ENABLE_V1" in payloads[
            "runs/c0/public_order_observer.log"
        ].decode(errors="replace")
        and len(sim_log) > 0
    )
    last_b5 = buffer5["last"]
    public_counts = public["observer"]["event_counts"]
    unique_boundary = (
        public.get("valid") is True
        and public.get("status") == "SA_OUTPUT_HELD_BY_BUFFER_BACKPRESSURE"
        and public_counts
        == {
            "SA_IN_ACCEPT": 30,
            "SA_OUT_ACCEPT": 4,
            "MSE4_INDEX_ACCEPT": 3,
        }
        and last_b5["arm_valid"] == "0xff"
        and last_b5["arm_rw"] == "1"
        and last_b5["arm_ready"] == "0"
        and last_b5["mrm_valid"] == "0x0"
        and last_b5["mrm_ready"] == "1"
        and last_b5["sa_raw_valid"] == "1"
        and last_b5["sa_ready"] == "0"
        and int(last_b5["arm_accept"]) == 4
        and int(last_b5["mrm_accept"]) == 16
        and int(last_b5["mrm_clear_count"]) == 16
        and triggered["four_identical_qualified_windows"]
    )
    exact_prior_same_leaf = (
        root_cause.get("status") == "CONFIG_ROOT_CAUSE_UNIQUE"
        and root_cause.get("leaf")
        == "lc_pe_configs.PE1.inport0.keep_last_index"
        and root_cause.get("old") == 2
        and root_cause.get("required") == 3
        and root_cause.get("final_json", {}).get("sha256")
        == sha256(
            ROOT
            / "artifacts/operator_config_validation/"
            "r5-conv-native-four-lane-0cc-p9-tx5-c0/execplan_conv/"
            "wave-0/pipeline_output/jsons/"
            "op_w0_resnet50_conv_node0004_wave0.json"
        )
        and direct_predicate["old_ready"] == 0
        and direct_predicate["corrected_ready"] == 1
    )

    checks = {
        "outer_return_identity_exact": (
            RETURN_ZIP.stat().st_size == RETURN_BYTES
            and sha256(RETURN_ZIP) == RETURN_SHA256
        ),
        "source_identity_exact": (
            SOURCE_ZIP.stat().st_size == SOURCE_BYTES
            and sha256(SOURCE_ZIP) == SOURCE_SHA256
        ),
        "return_crc_root_path_safe": not return_errors,
        "source_crc_root_path_safe": not source_errors,
        "return_exact_set": set(records) == expected,
        "return_manifest_records_exact": not declared_mismatch,
        "return_allowlist_exact": (
            set(records) == allowed_set and not allowed_mismatch
        ),
        "source_files_exact": source_manifest["files"] == source_files,
        "returned_source_manifest_exact": (
            returned_source_manifest == source_payloads["package_manifest.json"]
            and manifest["source_package_manifest_sha256"]
            == digest(returned_source_manifest)
        ),
        "package_install_observer_path_preflights": (
            package_preflight.get("valid") is True
            and install_preflight.get("valid") is True
            and observer_preflight.get("valid") is True
            and path_budget.get("valid") is True
            and path_budget.get("longest_projected_relative_path_chars")
            == len(path_budget.get("longest_projected_relative_path", ""))
            == path_budget.get("max_projected_relative_path_chars")
        ),
        "install_only_root_gate": (
            root_gate.get("valid") is True
            and root_gate.get("ndp_root_toplevel_unchanged") is True
            and layout.get("root_exact_set_unchanged") is True
            and layout.get("all_package_owned_paths_under_install") is True
            and layout.get("unknown_items_deleted_or_overwritten") is False
        ),
        "static_genvar_xmr_compile_gate": compile_success,
        "production_identity_collected": identity.get("collection_valid") is True,
        "simulator_observers_started": simulation_started,
        "qualified_stall_before_external_int": (
            run_status == 125
            and signal_status == "INT"
            and triggered_summary.get("valid") is True
            and unique_boundary
        ),
        "same_config_leaf_root_cause_unique": exact_prior_same_leaf,
        "formal_320d_absent_by_design": (
            source_manifest.get("conv_run_ids") == ["c0"]
            and source_manifest.get("tail_run_ids") == []
            and source_manifest.get("formal_readback_count") == 0
            and gate["execution_gate"]["formal_D_claimed"] is False
        ),
    }
    valid = all(checks.values())

    result = {
        "schema": "conv-native-four-lane-0ccae916-p17-return-analysis-v1",
        "status": (
            "CONFIG_PE1_KEEP_LAST_INDEX_FIX_SUCCESSOR_REQUIRED"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "valid": valid,
        "classification": (
            "LONG_RUNNING_C0_MSE4_INDEX3_KEEP_RELEASE_STALL_BEFORE_EXTERNAL_INT"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "return_identity": {
            "path": str(RETURN_ZIP),
            "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha256(RETURN_ZIP),
            "adjacent_sidecar_present": Path(
                str(RETURN_ZIP) + ".sha256"
            ).is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
        },
        "internal_receipt": {
            "return_file_count": len(records),
            "source_file_count": len(source_records),
            "return_errors": return_errors,
            "source_errors": source_errors,
            "missing": sorted(expected - set(records)),
            "extra": sorted(set(records) - expected),
            "manifest_record_mismatches": declared_mismatch,
            "allowlist_record_mismatches": allowed_mismatch,
            "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "static_genvar_xmr_compile_gate_closed": compile_success,
            "dut_simulation_started": simulation_started,
            "stale_package_local_status_bit": {
                "reported_dut_simulation_started": local_status.get(
                    "dut_simulation_started"
                ),
                "contradicted_by": [
                    "simulator_argv",
                    "sim.log",
                    "N4T feature marker",
                    "N4P feature marker",
                    "N4B5 feature marker",
                ],
                "blocks_diagnostic_consumption": False,
            },
            "external_int_after_stable_stall": True,
            "natural_terminal": False,
            "formal_D_payload_present": False,
        },
        "production_rtl_identity": {
            "actual": identity,
            "identity_difference_blocks_simulator": False,
            "causal_mismatches": sorted(
                name
                for name, row in identity.get("leaves", {}).items()
                if row.get("matches_cloud_authority") is False
            ),
            "claim_boundary": (
                "actual/cloud differences are nonblocking provenance after "
                "compile; Buffer/ARM/MRM mismatches prevent claiming current-"
                "cloud RTL closure but do not explain away the exact config "
                "predicate shared with the formal v61 counterexample"
            ),
        },
        "qualified_c0_boundary": {
            "public_order": public,
            "buffer5_public": buffer5,
            "triggered": triggered,
            "triggered_summary": triggered_summary,
            "held_levels_count_as_transactions": False,
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "c0 accepted 30 SA inputs, four SA outputs, 16 Buffer5 MRM "
                "reads/clears and three MSE4 indices"
            ),
            "FIRST_DIVERGENCE": (
                "the required fourth MSE4/PE1 flattened-index occurrence is "
                "not accepted; MRM request falls to zero, Buffer5 row0 remains "
                "occupied and the next SA output is held valid with ready low"
            ),
            "HANG_ROOT_CAUSE": {
                "classification": "PE_KEEP_RELEASE_THRESHOLD_OFF_BY_ONE",
                "status": "CONFIG_ROOT_CAUSE_UNIQUE",
                "leaf": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": configured_keep,
                "required": 3,
                "direct_predicate": direct_predicate,
                "current_rtl": {
                    "path": KEEP_RTL.relative_to(ROOT).as_posix(),
                    "sha256": sha256(KEEP_RTL),
                    "line": keep_line,
                },
                "same_exact_final_config_prior_dynamic_receipt": {
                    "path": V61_REPORT.relative_to(ROOT).as_posix(),
                    "sha256": sha256(V61_REPORT),
                    "logical_to_physical": root_cause["mapping"][
                        "logical_to_physical"
                    ],
                    "dynamic_checks": root_cause["dynamic_checks"],
                },
                "functional_rtl_root_cause_proven": False,
            },
        },
        "result_conjunction": {
            "compile": True,
            "simulator_started": True,
            "c0_natural_terminal": False,
            "formal_D_expected": 0,
            "formal_D_present": 0,
            "mismatch_zero_claim": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "performance_claimed": False,
            "passed": False,
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE4_P16_DYNAMIC_GENERATE_XMR",
                "B_CONV_NATIVE4_BUFFER5_PUBLIC_BOUNDARY_UNKNOWN",
                "B_CONV_NATIVE4_MSE4_BUFFER5_DEEP_CAUSAL_LEAF_UNKNOWN",
            ],
            "opened": [
                "B_CONV_NATIVE4_PE1_INPORT0_KEEP_LAST_INDEX_CONFIG_FIX_DYNAMIC"
            ],
            "preserved": [
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor": {
            "required": valid,
            "fresh_identity": True,
            "authorized_config_change": {
                "path": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": 2,
                "new": 3,
            },
            "frozen": (
                "numeric/W3/golden/matrix/address/observer/timeout/"
                "functional-RTL/ISA/hardware"
            ),
            "server_action": False,
        },
        "current_rule_receipts": {
            path: {
                "bytes": (ROOT / path).stat().st_size,
                "sha256": sha256(ROOT / path),
            }
            for path in RULE_PATHS
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
                "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            ],
            "delta": None,
        },
    }
    write_json(OUTPUT, result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "valid": valid,
                "output": str(OUTPUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
