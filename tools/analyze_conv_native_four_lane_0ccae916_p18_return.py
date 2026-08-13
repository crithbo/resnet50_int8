#!/usr/bin/env python3
"""Validate and adjudicate the formal repeatable-runtime native Conv p18 return."""

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
    r"C:\Users\15383\Downloads"
    r"\r5_n4_0cc_p18_pekeep3_r1786110514921865390_3724786_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n4_0cc_p18_pekeep3.zip"
)
PACKAGE_ID = "r5_n4_0cc_p18_pekeep3"
RETURN_ROOT = f"{PACKAGE_ID}_return"
RETURN_BYTES = 2_122_559
RETURN_SHA256 = (
    "7e4aeaed79a344dc35f392248f17505dbdba3a7b8eda1ae1328c67ef4a609dc5"
)
SOURCE_BYTES = 5_854_983
SOURCE_SHA256 = (
    "58a7a5e15d3dc05f96431783bb8212d11ea686f5d29d1815a920194272a09b8f"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p18_return_analysis"
    / "report_v2.json"
)
P17_REPORT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p17_return_analysis/report.json"
)
LOCAL_REBUILD = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p18-pekeep3-c0/local_rebuild_report.json"
)
REPEAT_RECEIPT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "pending_receipts/conv_native_four_lane/r5_n4_0cc_p18_pekeep3/"
    "r5_n4_0cc_p18_pekeep3.repeatable_runtime_validation.json"
)
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


def record_map(value: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in value[key]
    }


def fields(line: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", line)
    }


def parse_triggered(text: str) -> dict[str, Any]:
    rows = [
        fields(line)
        for line in text.splitlines()
        if line.startswith("N4T_TRIGGER_V1 ")
    ]
    no_progress = [
        row for row in rows if row.get("trigger") == "NO_PROGRESS_WINDOW"
    ]
    return {
        "record_count": len(rows),
        "no_progress_count": len(no_progress),
        "qualified_key_totals": [
            int(row.get("key_total", "0"), 0) for row in no_progress
        ],
        "digests": [row.get("digest") for row in no_progress],
        "four_identical_qualified_windows": (
            len(no_progress) == 4
            and len({row.get("key_total") for row in no_progress}) == 1
            and len({row.get("digest") for row in no_progress}) == 1
        ),
        "last": no_progress[-1] if no_progress else {},
    }


def main() -> int:
    required = (
        RETURN_ZIP,
        SOURCE_ZIP,
        P17_REPORT,
        LOCAL_REBUILD,
        REPEAT_RECEIPT,
    )
    if not all(path.is_file() for path in required):
        raise AnalysisError("required p18 return/source/causal receipt is absent")

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
    publication = json.loads(
        payloads["evidence/publication_preflight.json"]
    )
    public = json.loads(payloads["evidence/public_order_summary.json"])
    buffer5 = json.loads(payloads["evidence/buffer5_public_summary.json"])
    triggered_summary = json.loads(
        payloads["evidence/triggered_causal_summary.json"]
    )
    triggered_text = payloads["runs/c0/triggered_observer.log"].decode(
        errors="replace"
    )
    triggered = parse_triggered(triggered_text)
    return_observer = payloads["runs/c0/return_observer.log"].decode(
        errors="replace"
    )
    compile_log = payloads["runs/compile/compile_driver.log"].decode(
        errors="replace"
    )
    sim_log = payloads["runs/c0/sim.log"].decode(errors="replace")
    simulator_argv = payloads["runs/c0/simulator_argv.txt"].decode(
        errors="replace"
    )
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()

    declared = record_map(manifest, "records_excluding_this_manifest")
    expected = set(declared) | {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"}
    allowed = record_map(allowlist, "records")
    allowed_set = set(allowed) | {"RETURN_ALLOWLIST.json"}
    declared_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in declared.items()
        if records.get(path) != row
    }
    allowed_mismatch = {
        path: {"expected": row, "observed": records.get(path)}
        for path, row in allowed.items()
        if records.get(path) != row
    }
    source_manifest = json.loads(source_payloads["package_manifest.json"])
    source_files = {
        path: row
        for path, row in source_records.items()
        if path != "package_manifest.json"
    }
    returned_source_manifest = payloads[
        "source_package/package_manifest.json"
    ]

    p17 = json.loads(P17_REPORT.read_text(encoding="utf-8"))
    rebuild = json.loads(LOCAL_REBUILD.read_text(encoding="utf-8"))
    repeat = json.loads(REPEAT_RECEIPT.read_text(encoding="utf-8"))
    p17_counts = p17["qualified_c0_boundary"]["public_order"]["observer"][
        "event_counts"
    ]
    counts = public["observer"]["event_counts"]
    last_b5 = buffer5["last"]

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
        "N4T_FEATURE_ENABLE_V1" in triggered_text
        and "N4P_FEATURE_ENABLE_V1" in payloads[
            "runs/c0/public_order_observer.log"
        ].decode(errors="replace")
        and "N4B5_FEATURE_ENABLE_V1" in payloads[
            "runs/c0/buffer5_public_observer.log"
        ].decode(errors="replace")
        and "+RETURN_OBSERVER" in simulator_argv
        and len(sim_log) > 0
    )
    unique_return = (
        re.fullmatch(
            rf"{re.escape(PACKAGE_ID)}_r[0-9]+_[0-9]+_return\.zip",
            RETURN_ZIP.name,
        )
        is not None
        and manifest["fixed_result_publication"]["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["return_zip"]
        == f"/home/panqs/ndp/simresult/{RETURN_ZIP.name}"
        and publication["publication_state"]
        == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING"
    )
    repeat_reset = (
        repeat.get("pass") is True
        and next(
            row
            for row in repeat.get("packages", [])
            if row.get("package_id") == PACKAGE_ID
        ).get("pass")
        is True
        and repeat.get("repeat_layout", {}).get("pass") is True
        and layout["repeat_execution"]["mode"]
        == "RESET_EXACT_PACKAGE_OWNED_RUNTIME_ROOTS"
        and layout["repeat_execution"]["replacements"][1][
            "reset_performed"
        ]
        is True
        and layout["unknown_items_deleted_or_overwritten"] is False
    )
    keep3_dynamic = (
        rebuild.get("status") == "LOCAL_C0_SINGLE_LEAF_REBUILD_PASS"
        and rebuild.get("authorized_leaf_changes")
        == [
            {
                "path": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": 2,
                "new": 3,
            }
        ]
        and p17_counts
        == {
            "SA_IN_ACCEPT": 30,
            "SA_OUT_ACCEPT": 4,
            "MSE4_INDEX_ACCEPT": 3,
        }
        and counts
        == {
            "SA_IN_ACCEPT": 30,
            "SA_OUT_ACCEPT": 5,
            "MSE4_INDEX_ACCEPT": 3,
        }
        and int(last_b5["arm_accept"]) == 5
        and last_b5["arm_valid"] == "0xff"
        and last_b5["arm_ready"] == "0"
        and last_b5["mrm_valid"] == "0x0"
        and last_b5["sa_raw_valid"] == "1"
        and last_b5["sa_ready"] == "0"
    )
    qualified_stall = (
        run_status == 125
        and signal_status == "INT"
        and triggered_summary.get("valid") is True
        and triggered_summary.get("status") == "DYNAMIC_FLOW_CONTROL_STALL"
        and triggered["four_identical_qualified_windows"]
        and triggered_summary["observer"]["natural_slice_finish_observed"]
        is False
    )
    source_expected_formal = source_manifest.get("formal_readback_count") == 0
    no_formal = (
        source_expected_formal
        and gate["execution_gate"]["formal_D_claimed"] is False
        and not any(path.startswith("formal_D/") for path in records)
    )
    held_counter_warning = (
        "decision=STILL_PROGRESSING" in return_observer
        and int(last_b5["blocked_cycles"]) > 1_000_000
        and triggered["four_identical_qualified_windows"]
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
        "repeat_execution_unique_return": unique_return and repeat_reset,
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
        "production_compile_and_identity": (
            compile_success and identity.get("collection_valid") is True
        ),
        "simulator_observers_started": simulation_started,
        "pekeep3_dynamic_boundary_closed": keep3_dynamic,
        "qualified_new_stall_before_external_int": qualified_stall,
        "formal_320d_absent_by_diagnostic_design": no_formal,
    }
    valid = all(checks.values())

    result = {
        "schema": "conv-native-four-lane-0ccae916-p18-return-analysis-v1",
        "status": (
            "P18_PEKEEP3_DYNAMIC_PASS_NEXT_D_FLOW_DIAGNOSTIC_REQUIRED"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "valid": valid,
        "classification": (
            "LONG_RUNNING_C0_AFTER_KEEP3_PASS_NEW_FLOW_STALL_BEFORE_EXTERNAL_INT"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "return_identity": {
            "path": str(RETURN_ZIP),
            "bytes": RETURN_ZIP.stat().st_size,
            "sha256": sha256(RETURN_ZIP),
            "adjacent_sidecar_present": Path(str(RETURN_ZIP) + ".sha256").is_file(),
            "transport_policy": "USER_ATTESTED_EXTERNAL_SIDECAR_WAIVER",
            "unique_per_execution_basename_valid": unique_return,
            "inner_root": RETURN_ROOT,
            "source_mismatch_from_unique_basename": False,
        },
        "source_identity": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": sha256(SOURCE_ZIP),
            "source_manifest_sha256": digest(
                source_payloads["package_manifest.json"]
            ),
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
        "repeat_execution": {
            "local_validation": {
                "path": REPEAT_RECEIPT.relative_to(ROOT).as_posix(),
                "sha256": sha256(REPEAT_RECEIPT),
                "valid": repeat.get("pass"),
            },
            "runtime_reset": layout["repeat_execution"],
            "unique_return": manifest["fixed_result_publication"],
            "duplicate_absent": True,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "compile_succeeded": compile_success,
            "dut_simulation_started": simulation_started,
            "stale_package_local_status_bit": {
                "reported": local_status.get("dut_simulation_started"),
                "contradicted_by": [
                    "simulator argv",
                    "sim.log",
                    "N4T feature marker",
                    "N4P feature marker",
                    "N4B5 feature marker",
                ],
                "blocking": False,
            },
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
                "The diagnostic is valid under exact actual compiled leaves. "
                "Relevant Buffer/ARM/MRM differences remain nonblocking "
                "provenance and preclude claiming current-cloud E3/E4/E5."
            ),
        },
        "qualified_c0_boundary": {
            "p17_event_counts": p17_counts,
            "p18_event_counts": counts,
            "dynamic_delta": {
                "SA_IN_ACCEPT": counts["SA_IN_ACCEPT"] - p17_counts["SA_IN_ACCEPT"],
                "SA_OUT_ACCEPT": (
                    counts["SA_OUT_ACCEPT"] - p17_counts["SA_OUT_ACCEPT"]
                ),
                "MSE4_INDEX_ACCEPT": (
                    counts["MSE4_INDEX_ACCEPT"]
                    - p17_counts["MSE4_INDEX_ACCEPT"]
                ),
                "BUFFER5_ARM_ACCEPT": (
                    int(last_b5["arm_accept"])
                    - int(
                        p17["qualified_c0_boundary"]["buffer5_public"]["last"][
                            "arm_accept"
                        ]
                    )
                ),
            },
            "pekeep3_dynamic_closure": keep3_dynamic,
            "public_order": public,
            "buffer5_public": buffer5,
            "triggered": triggered,
            "triggered_summary": triggered_summary,
            "held_levels_count_as_transactions": False,
            "legacy_progress_record_warning": {
                "present": held_counter_warning,
                "disposition": "record_only_not_canonical",
                "reason": (
                    "N4D level-based counters can grow while qualified N4T "
                    "event totals remain unchanged; canonical stall decision "
                    "comes from the qualified triggered predicate."
                ),
            },
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "PE1 keep_last_index=3 admitted the previously blocked fifth "
                "SA output and fifth Buffer5 ARM acceptance after p17 stopped "
                "at four; compile and simulation remained active."
            ),
            "FIRST_DIVERGENCE": (
                "After that new acceptance, qualified SA/MSE4/Buffer5 progress "
                "stops for four identical windows: Buffer5 arm_valid=0xff, "
                "arm_ready=0, mrm_valid=0, SA valid=1 and ready=0; no "
                "slice_finish follows."
            ),
            "HANG_ROOT_CAUSE": {
                "status": "ROOT_NOT_YET_UNIQUE",
                "classification": "POST_PEKEEP3_D_FLOW_CONTROL_STALL",
                "closed_prior_root": "PE_KEEP_RELEASE_THRESHOLD_OFF_BY_ONE",
                "remaining_low_cost_candidates": [
                    "prepared-data and descriptor issuance/pop skew",
                    "MSE4 descriptor/index propagation after index3",
                    "Buffer_AG source/tag/row-column lifetime skew",
                    "D-write terminal ownership or inter-burst/global terminal skew",
                ],
                "required_observation": (
                    "one time-aligned qualified ledger spanning descriptor, "
                    "prepared-data, source/tag, LC13/14/15, PE7 and D-write "
                    "terminal edges"
                ),
                "serialized_v63_analogy_is_root_proof": False,
                "functional_rtl_root_cause_proven": False,
                "authorized_config_fix": None,
            },
        },
        "result_conjunction": {
            "compile": compile_success,
            "simulator_started": simulation_started,
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
                "B_CONV_NATIVE_P18_FORMAL_RETURN",
                "B_CONV_NATIVE_P18_REPEATABLE_RUNTIME_UNPROVEN",
                "B_CONV_NATIVE_P18_PEKEEP3_DYNAMIC_C0_CLOSURE",
            ],
            "opened": [
                "B_CONV_NATIVE_POST_PEKEEP3_D_FLOW_FIRST_DIVERGENCE_UNKNOWN"
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
            "candidate_class": "C0_DIAGNOSTIC_ONLY",
            "scope": (
                "append qualified time-aligned causal observer and parser "
                "only; freeze p18 workload/config/mapping/bitstream/execplan/"
                "SCA/numeric/W3/golden/timeout/functional RTL"
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
                "CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-DIAGNOSTIC-EVENT-QUALIFICATION-001",
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
