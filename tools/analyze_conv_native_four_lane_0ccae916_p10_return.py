#!/usr/bin/env python3
"""Validate and classify the formal native-four-lane p10 triggered return."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-08\r5_n4_0cc_p10_trig_return.zip"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p10_return_analysis"
    / "report.json"
)
INSTALL_NAME = "r5_n4_0cc_p10_trig"
RETURN_ROOT = f"{INSTALL_NAME}_return"
EXPECTED_SOURCE_SHA256 = (
    "25c9c01fe7feb42ec8de3eef701386420e7ab014ad24630022539d97a9fb03b5"
)
EXPECTED_RETURN_BYTES = 97_182
EXPECTED_RETURN_SHA256 = (
    "568a0c63f0db3e21a63a9fae94a711f91583fabb4f00a1a47ced0d613d721434"
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


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def source_zip() -> Path:
    storage = (
        ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
    )
    candidates = [
        storage / "pending" / f"{INSTALL_NAME}.zip",
        storage
        / "tested/conv_native_four_lane"
        / INSTALL_NAME
        / f"{INSTALL_NAME}.zip",
        storage
        / "superseded/conv_native_four_lane"
        / INSTALL_NAME
        / f"{INSTALL_NAME}.zip",
    ]
    for candidate in candidates:
        if candidate.is_file() and sha256(candidate) == EXPECTED_SOURCE_SHA256:
            return candidate
    raise FileNotFoundError("exact p10 source ZIP is unavailable")


def safe_records(
    archive: zipfile.ZipFile, expected_root: str
) -> tuple[dict[str, dict[str, Any]], dict[str, bytes], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    payloads: dict[str, bytes] = {}
    errors: list[str] = []
    seen: set[str] = set()
    failed_crc = archive.testzip()
    if failed_crc is not None:
        errors.append(f"CRC:{failed_crc}")
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or not pure.parts
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


def fields(row: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r"(?:^| )([A-Za-z0-9_]+)=([^ ]+)", row)
    }


def csv_ints(value: str) -> list[int]:
    return [int(item, 0) for item in value.split(",")]


def parse_triggered(text: str) -> dict[str, Any]:
    rows = [
        fields(row)
        for row in text.splitlines()
        if row.startswith("N4T_TRIGGER_V1 ")
    ]
    markers = [
        fields(row)
        for row in text.splitlines()
        if row.startswith("N4T_FEATURE_ENABLE_V1 ")
    ]
    no_progress = [
        row for row in rows if row.get("trigger") == "NO_PROGRESS_WINDOW"
    ]
    terminal = next(
        (row for row in rows if row.get("trigger") == "TERMINAL_GAP"),
        {},
    )
    last = rows[-1] if rows else {}
    key_totals = [int(row.get("key_total", "0"), 0) for row in rows]
    no_progress_keys = [
        int(row.get("key_total", "0"), 0) for row in no_progress
    ]
    qualified_snapshot = {
        "key_total": int(last.get("key_total", "0"), 0),
        "request_counts": csv_ints(last.get("req", "0,0,0,0,0")),
        "arm_request_counts": csv_ints(
            last.get("armreq", "0,0,0,0,0,0")
        ),
        "arm_response_counts": csv_ints(
            last.get("armresp", "0,0,0,0,0,0")
        ),
        "arm_finish_counts": csv_ints(
            last.get("armfin", "0,0,0,0,0,0")
        ),
        "sa_input_accepted": int(last.get("sain", "0"), 0),
        "sa_output_accepted": int(last.get("saout", "0"), 0),
        "mse4_index_accepted": int(last.get("mse4", "0"), 0),
        "buffer5_active_cycles": int(last.get("b5_active", "0"), 0),
        "buffer5_rising_edges": int(last.get("b5_rise", "0"), 0),
        "buffer5_mask": last.get("b5_mask"),
        "sa_input_last_seen_mask": last.get("sa_in_last_seen"),
        "sa_output_last_seen_mask": last.get("sa_out_last_seen"),
        "sa_input_last_tag": last.get("sa_in_tag"),
        "sa_output_last_tag": last.get("sa_out_tag"),
    }
    return {
        "feature_markers": markers,
        "record_count": len(rows),
        "trigger_counts": {
            name: sum(row.get("trigger") == name for row in rows)
            for name in sorted({row.get("trigger", "") for row in rows})
        },
        "records": rows,
        "key_totals": key_totals,
        "terminal_gap_key_total": (
            int(terminal.get("key_total", "0"), 0) if terminal else None
        ),
        "no_progress_window_count": len(no_progress),
        "no_progress_key_totals": no_progress_keys,
        "last_cycle": int(last.get("sg_cycle", "0"), 0),
        "qualified_snapshot": qualified_snapshot,
        "qualified_stall_confirmed": (
            len(no_progress_keys) >= 4
            and len(set(no_progress_keys[-4:])) == 1
            and terminal
            and no_progress_keys[-1]
            == int(terminal.get("key_total", "-1"), 0)
        ),
    }


def parse_legacy_progress(observer_text: str, host_text: str) -> dict[str, Any]:
    rows = [
        fields(row)
        for row in observer_text.splitlines()
        if row.startswith("N4D_PROGRESS_V1 ")
    ]
    host_rows = [
        fields(row)
        for row in host_text.splitlines()
        if row.startswith("host_epoch=")
    ]
    last = rows[-1] if rows else {}
    return {
        "record_count": len(rows),
        "reported_still_progressing_count": sum(
            row.get("decision") == "STILL_PROGRESSING" for row in rows
        ),
        "last_reported_total": int(last.get("total", "0"), 0),
        "last_request_counts": csv_ints(
            last.get("req", "0,0,0,0,0")
        ),
        "last_arm_request_counts": csv_ints(
            last.get("armreq", "0,0,0,0,0,0")
        ),
        "last_arm_response_counts": csv_ints(
            last.get("armresp", "0,0,0,0,0,0")
        ),
        "last_arm_finish_counts": csv_ints(
            last.get("armfin", "0,0,0,0,0,0")
        ),
        "last_sa_input": int(last.get("sain", "0"), 0),
        "last_sa_output": int(last.get("saout", "0"), 0),
        "last_mse4_index": int(last.get("m4idx", "0"), 0),
        "last_buffer5_level_samples": int(last.get("b5wr", "0"), 0),
        "host_sample_count": len(host_rows),
        "host_start_epoch": (
            int(host_rows[0]["host_epoch"], 0) if host_rows else None
        ),
        "host_end_epoch": (
            int(host_rows[-1]["host_epoch"], 0) if host_rows else None
        ),
        "host_span_seconds": (
            int(host_rows[-1]["host_epoch"], 0)
            - int(host_rows[0]["host_epoch"], 0)
            if host_rows
            else None
        ),
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    exact_source = source_zip()
    outer = {
        "path": str(return_zip),
        "size_bytes": return_zip.stat().st_size,
        "sha256": sha256(return_zip),
        "adjacent_sidecar_present": Path(
            str(return_zip) + ".sha256"
        ).is_file(),
        "transport": "USER_ATTESTED_FORMAL_RETURN_PATH",
    }
    source = {
        "path": str(exact_source),
        "size_bytes": exact_source.stat().st_size,
        "sha256": sha256(exact_source),
    }
    with zipfile.ZipFile(return_zip) as archive:
        records, payloads, return_errors = safe_records(
            archive, RETURN_ROOT
        )
    with zipfile.ZipFile(exact_source) as archive:
        source_records, source_payloads, source_errors = safe_records(
            archive, INSTALL_NAME
        )

    return_manifest = json.loads(payloads["RETURN_MANIFEST.json"])
    allowlist = json.loads(payloads["RETURN_ALLOWLIST.json"])
    result_gate = json.loads(payloads["evidence/SERVER_RESULT_GATE.json"])
    identity = json.loads(
        payloads["evidence/production_rtl_identity.json"]
    )
    package_preflight = json.loads(
        payloads["evidence/package_preflight.json"]
    )
    install_preflight = json.loads(
        payloads["evidence/install_preflight.json"]
    )
    observer_precompile = json.loads(
        payloads["evidence/observer_precompile.json"]
    )
    trigger_summary = json.loads(
        payloads["evidence/triggered_causal_summary.json"]
    )
    source_manifest_bytes = source_payloads["package_manifest.json"]
    returned_manifest_bytes = payloads[
        "source_package/package_manifest.json"
    ]
    source_manifest = json.loads(source_manifest_bytes)
    compile_status = int(
        payloads["evidence/compile_exit_status.txt"].decode().strip()
    )
    run_status = int(
        payloads["evidence/run_exit_status.txt"].decode().strip()
    )
    signal_status = payloads["evidence/signal_status.txt"].decode().strip()
    compile_driver = payloads["runs/compile/compile_driver.log"].decode(
        errors="replace"
    )
    sim_text = payloads["runs/c0/sim.log"].decode(errors="replace")
    triggered = parse_triggered(
        payloads["runs/c0/triggered_observer.log"].decode(
            errors="replace"
        )
    )
    legacy = parse_legacy_progress(
        payloads["runs/c0/return_observer.log"].decode(errors="replace"),
        payloads["runs/c0/host_progress.log"].decode(errors="replace"),
    )

    declared = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in return_manifest["records_excluding_this_manifest"]
    }
    expected_set = set(declared) | {
        "RETURN_MANIFEST.json",
        "RETURN_ALLOWLIST.json",
    }
    mismatches = {
        path: {"expected": value, "observed": records.get(path)}
        for path, value in declared.items()
        if records.get(path) != value
    }
    allow_records = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in allowlist["records"]
    }
    allow_expected = set(allow_records) | {"RETURN_ALLOWLIST.json"}
    source_files = {
        path: value
        for path, value in source_records.items()
        if path != "package_manifest.json"
    }
    gate = result_gate["execution_gate"]
    actual_cloud_mismatches = {
        name: {
            "actual_sha256": leaf["sha256"],
            "cloud_sha256": leaf["cloud_authority_sha256"],
            "actual_size_bytes": leaf["size_bytes"],
        }
        for name, leaf in identity["leaves"].items()
        if not leaf["matches_cloud_authority"]
    }
    snapshot = triggered["qualified_snapshot"]
    fixed_config_scope = (
        source_manifest.get("conv_run_ids") == ["c0"]
        and source_manifest.get("tail_run_ids") == []
        and source_manifest.get("formal_readback_count") == 0
        and source_manifest.get("readback_checks") == []
    )
    no_natural = (
        run_status == 125
        and signal_status == "HUP"
        and gate["c0_natural_terminal"] is False
        and gate["diagnostic_natural_complete"] is False
        and "$finish at simulation time" not in sim_text
    )
    held_level_escape = (
        triggered["qualified_stall_confirmed"]
        and snapshot["buffer5_rising_edges"] == 1
        and snapshot["buffer5_active_cycles"] > 1_000_000
        and legacy["last_buffer5_level_samples"] > 1_000_000
        and legacy["last_arm_finish_counts"]
        == snapshot["arm_finish_counts"]
        == [0, 0, 0, 0, 0, 0]
        and legacy["last_sa_input"] == snapshot["sa_input_accepted"]
        and legacy["last_sa_output"] == snapshot["sa_output_accepted"]
        and legacy["last_mse4_index"] == snapshot["mse4_index_accepted"]
    )
    checks = {
        "outer_identity_exact": (
            outer["size_bytes"] == EXPECTED_RETURN_BYTES
            and outer["sha256"] == EXPECTED_RETURN_SHA256
        ),
        "source_identity_exact": (
            source["sha256"] == EXPECTED_SOURCE_SHA256
        ),
        "return_safe_crc": not return_errors,
        "source_safe_crc": not source_errors,
        "return_exact_set": set(records) == expected_set,
        "return_record_hashes_exact": not mismatches,
        "return_allowlist_exact": (
            set(records) == allow_expected
            and all(
                records.get(path) == value
                for path, value in allow_records.items()
            )
        ),
        "source_manifest_binding": (
            returned_manifest_bytes == source_manifest_bytes
            and digest(returned_manifest_bytes)
            == return_manifest["source_package_manifest_sha256"]
        ),
        "source_manifest_files_exact": (
            source_manifest["files"] == source_files
        ),
        "preflights_valid": (
            package_preflight.get("valid") is True
            and install_preflight.get("valid") is True
            and observer_precompile.get("valid") is True
        ),
        "compile_succeeded": (
            compile_status == 0
            and gate["compile_succeeded"] is True
            and "Compilation completed!" in compile_driver
            and "0 error(s)" in compile_driver
        ),
        "identity_collected_nonblocking": (
            identity.get("collection_valid") is True
            and identity.get("identity_difference_blocks_simulator") is False
            and identity == result_gate["production_rtl_identity"]
            and identity["compile_log_sha256"]
            == digest(payloads["runs/compile/compile_driver.log"])
        ),
        "trigger_feature_started": (
            len(triggered["feature_markers"]) == 1
            and triggered["feature_markers"][0].get("enabled") == "1"
            and triggered["record_count"] == 8
            and trigger_summary.get("valid") is True
        ),
        "qualified_stall_confirmed": triggered[
            "qualified_stall_confirmed"
        ],
        "legacy_held_level_escape_reproduced": held_level_escape,
        "external_hup_after_stall": no_natural,
        "formal_scope_absent_by_design": fixed_config_scope
        and gate["formal_D_claimed"] is False,
    }
    valid = all(checks.values())
    current_receipts = {
        path: sha256(ROOT / path)
        for path in RULE_PATHS
        if (ROOT / path).is_file()
    }
    return {
        "schema": "conv-native-four-lane-0ccae916-p10-return-analysis-v1",
        "status": (
            "EXTERNAL_HUP_AFTER_QUALIFIED_C0_STALL_SUCCESSOR_REQUIRED"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "valid": valid,
        "classification": (
            "LONG_RUNNING_HANG_CONFIRMED_BEFORE_EXTERNAL_HUP"
            if valid
            else "RETURN_VALIDATION_FAILED"
        ),
        "outer_return_identity": outer,
        "source_package_identity": source,
        "internal_receipt": {
            "return_root": RETURN_ROOT,
            "entry_count": len(records),
            "return_manifest_sha256": records[
                "RETURN_MANIFEST.json"
            ]["sha256"],
            "return_allowlist_sha256": records[
                "RETURN_ALLOWLIST.json"
            ]["sha256"],
            "source_package_manifest_sha256": digest(
                returned_manifest_bytes
            ),
            "return_errors": return_errors,
            "source_errors": source_errors,
            "exact_set_missing": sorted(expected_set - set(records)),
            "exact_set_extra": sorted(set(records) - expected_set),
            "record_mismatches": mismatches,
            "checks": checks,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "natural_terminal": False,
            "external_interruption": True,
            "interrupted_while_qualified_progress": False,
            "adjudication": (
                "HUP is genuine, but it followed four consecutive "
                "qualified no-progress windows; not PARTIAL_INTERRUPTED"
            ),
            "package_preflight": package_preflight,
            "install_preflight": install_preflight,
            "observer_precompile": observer_precompile,
            "production_rtl_identity": identity,
            "actual_cloud_mismatches": actual_cloud_mismatches,
            "trigger_summary": trigger_summary,
        },
        "qualified_causal_evidence": {
            "triggered": triggered,
            "legacy_progress": legacy,
            "held_level_adjudication": {
                "escape_reproduced": held_level_escape,
                "old_observer_decision_invalid": "STILL_PROGRESSING",
                "reason": (
                    "legacy totals add Buffer_AG/Buffer write-enable levels "
                    "every cycle; request, ARM, SA, MSE4 and Buffer5 rising "
                    "edge all remain constant while those raw levels grow"
                ),
                "buffer5_active_cycles_are_transactions": False,
                "buffer5_rising_edges_are_edge_witness_only": True,
            },
        },
        "causal_adjudication": {
            "arm_terminal": {
                "requests": snapshot["arm_request_counts"],
                "responses": snapshot["arm_response_counts"],
                "finishes": snapshot["arm_finish_counts"],
                "decision": (
                    "RESPONSES_ACCEPTED_BUT_ALL_PUBLIC_FINISH_COUNTS_ZERO"
                ),
            },
            "sa_to_buffer5": {
                "sa_input_accepted": snapshot["sa_input_accepted"],
                "sa_output_accepted": snapshot["sa_output_accepted"],
                "sa_input_last_seen_mask": snapshot[
                    "sa_input_last_seen_mask"
                ],
                "sa_output_last_seen_mask": snapshot[
                    "sa_output_last_seen_mask"
                ],
                "buffer5_active_cycles": snapshot[
                    "buffer5_active_cycles"
                ],
                "buffer5_rising_edges": snapshot[
                    "buffer5_rising_edges"
                ],
                "decision": (
                    "INPUT_LAST_4_AND_5_ACCEPTED; ONLY_3_OUTPUTS; "
                    "NO_OUTPUT_LAST; BUFFER5_ENABLE_HELD_AFTER_ONE_RISE"
                ),
            },
            "mse4": {
                "accepted_index_count": snapshot["mse4_index_accepted"],
                "decision": "ONLY_ONE_ACCEPTED_INDEX_BEFORE_STALL",
            },
            "root_uniqueness": (
                "NOT_UNIQUE_AT_PUBLIC_BOUNDARIES: the return proves a "
                "stable qualified stall and eliminates the held-level "
                "progress interpretation, but it does not expose the "
                "payload/order needed to choose among ARM completion, SA "
                "last/output classification, and MSE4/Buffer5 consumption"
            ),
        },
        "failure_localization": {
            "LAST_PROVEN_GOOD": (
                "c0 exec; 302 qualified events including ARM responses, "
                "28 SA input accepts with last-index 4/5, 3 SA output "
                "accepts, one MSE4 index accept and one Buffer5 enable rise"
            ),
            "FIRST_DIVERGENCE": (
                "after accepted SA input last-index 4/5, SA output stays "
                "at 3 with no output-last, ARM finish remains zero, MSE4 "
                "index remains one and Buffer5 write-enable remains held"
            ),
            "HANG_ROOT_CAUSE": (
                "QUALIFIED_STALL_CONFIRMED_BEFORE_HUP; FUNCTIONAL LEAF "
                "REMAINS NON-UNIQUE WITHIN P10 PUBLIC PAYLOAD-FREE COUNTERS"
            ),
        },
        "blocker_delta": {
            "closed": [
                "B_CONV_NATIVE4_INTERRUPTED_WHILE_QUALIFIED_PROGRESS",
                "B_CONV_NATIVE4_BUFFER5_HELD_LEVEL_MISTAKEN_FOR_TRANSACTIONS",
                "B_CONV_NATIVE4_SIMULATOR_OR_TRIGGER_FEATURE_NOT_STARTED",
            ],
            "preserved": [
                "B_CONV_NATIVE4_ARM_FINISH_ZERO_CAUSAL_LEAF",
                "B_CONV_NATIVE4_SA_OUTPUT_LAST_PROPAGATION_CAUSAL_LEAF",
                "B_CONV_NATIVE4_MSE4_BUFFER5_ACCEPTANCE_CAUSAL_LEAF",
                "B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN",
                "B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN",
                "B_CONV_NATIVE4_FORMAL_320D_UNPROVEN",
                "B_CONV_NATIVE4_E3_E4_E5_UNPROVEN",
            ],
        },
        "successor_decision": {
            "required": True,
            "rerun_exact_p10": False,
            "reason": (
                "p10 already proves a stable stall before HUP; an exact "
                "rerun would repeat the same payload-free ambiguity"
            ),
            "scope": (
                "fresh c0 triggered causal observer using public surfaces, "
                "bounded accepted payload/tag/order witnesses and a shared "
                "fixed-result finalizer; config/numeric/W3/golden/address/"
                "functional RTL remain byte-identical"
            ),
            "full_27_320_now": False,
            "functional_rtl_change": False,
            "server_action_by_analyzer": False,
        },
        "claim_boundary": {
            "p10_diagnostic_c0_only": True,
            "formal_320d_absent_by_design": True,
            "E3": False,
            "E4": False,
            "E5": False,
            "performance_claimed": False,
        },
        "current_rule_receipts": current_receipts,
        "rule_feedback": {
            "kind": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
                "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
                "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            ],
            "claim_boundary": (
                "p10 exact return receipt, external HUP classification, "
                "qualified no-progress and held-level observer escape"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=RETURN_ZIP)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve())
    write_json(args.output.resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
