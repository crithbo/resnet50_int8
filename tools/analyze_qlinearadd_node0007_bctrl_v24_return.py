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
RETURN_ROOT = "r5_qadd_n7_bctrl_v24_return"
SOURCE_ROOT = "r5_qadd_n7_bctrl_v24"
SOURCE_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_bctrl_v24.zip"
)
RETURN_BYTES = 708_276
RETURN_SHA = "6cd544733c51c8f7626abe66d221321a1b3a524b41d278fa46c51530b41571b0"
SOURCE_BYTES = 38_032_104
SOURCE_SHA = "71e14695c3025340987dba2fc0ffedd23e8e61d9bcb6eaec704de74c8e6928da"


class AnalysisError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    payloads: dict[str, bytes] = {}
    roots: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AnalysisError(f"CRC failure: {bad}")
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise AnalysisError("duplicate ZIP member")
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or stat.S_ISLNK(mode)
            ):
                raise AnalysisError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            prefix = expected_root + "/"
            if not info.filename.startswith(prefix):
                raise AnalysisError(f"root mismatch: {info.filename}")
            relative = info.filename[len(prefix) :]
            if not relative or relative in payloads:
                raise AnalysisError(f"empty or duplicate relative path: {info.filename}")
            payloads[relative] = archive.read(info)
    if roots != {expected_root}:
        raise AnalysisError(f"root exact-set differs: {sorted(roots)}")
    return payloads, {
        "crc_valid": True,
        "single_exact_root": True,
        "root": expected_root,
        "file_count": len(payloads),
        "duplicates": 0,
        "symlinks": 0,
        "unsafe_paths": 0,
    }


def object_json(payloads: dict[str, bytes], name: str) -> dict[str, Any]:
    value = json.loads(payloads[name])
    if not isinstance(value, dict):
        raise AnalysisError(f"{name} is not a JSON object")
    return value


def records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = manifest.get("files")
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {
            str(item["path"]): {
                "size_bytes": int(item["size_bytes"]),
                "sha256": str(item["sha256"]),
            }
            for item in value
        }
    raise AnalysisError("manifest files is absent")


def parse_kv(payload: bytes) -> dict[str, str]:
    return {
        key: value
        for line in payload.decode(errors="replace").splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }


def invalid_128bit_receipt(
    returned: dict[str, bytes], source_manifest: dict[str, Any]
) -> dict[str, Any]:
    invalid_files: list[dict[str, Any]] = []
    valid_files = 0
    total_lines = 0
    invalid_lines = 0
    unknown_character_count = 0
    observed_paths: set[str] = set()
    expected_paths = {
        str(item["runtime_path"]) for item in source_manifest["readback_checks"]
    }
    for item in source_manifest["readback_checks"]:
        runtime_path = str(item["runtime_path"])
        return_path = "readbacks/" + runtime_path
        if return_path not in returned:
            continue
        observed_paths.add(runtime_path)
        lines = returned[return_path].splitlines()
        local_invalid = [
            line
            for line in lines
            if len(line) != 128 or set(line) - {ord("0"), ord("1")}
        ]
        total_lines += len(lines)
        invalid_lines += len(local_invalid)
        unknown_character_count += sum(line.count(b"x") + line.count(b"X") for line in lines)
        if local_invalid:
            invalid_files.append(
                {
                    "runtime_path": runtime_path,
                    "line_count": len(lines),
                    "invalid_line_count": len(local_invalid),
                    "text_sha256": sha256_bytes(returned[return_path]),
                    "first_line_prefix": lines[0][:16].decode(errors="replace"),
                }
            )
        else:
            valid_files += 1
    return {
        "expected": len(expected_paths),
        "present": len(observed_paths),
        "missing": len(expected_paths - observed_paths),
        "extra": len(observed_paths - expected_paths),
        "exact_path_set": observed_paths == expected_paths,
        "valid_128bit_files": valid_files,
        "invalid_128bit_files": len(invalid_files),
        "total_lines": total_lines,
        "invalid_lines": invalid_lines,
        "unknown_character_count": unknown_character_count,
        "invalid_file_receipts": invalid_files,
        "mismatch_byte_count": None,
        "mismatch_evaluable": False,
        "reason": (
            "all formal-D text payloads contain X-valued bits from the unexecuted "
            "full-chain tail; decode_128bit must fail before numeric comparison"
        ),
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    if return_zip.stat().st_size != RETURN_BYTES or sha256_file(return_zip) != RETURN_SHA:
        raise AnalysisError("return transport bytes/SHA differ")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or sha256_file(SOURCE_ZIP) != SOURCE_SHA:
        raise AnalysisError("frozen source package bytes/SHA differ")

    returned, return_structure = read_zip(return_zip, RETURN_ROOT)
    source, source_structure = read_zip(SOURCE_ZIP, SOURCE_ROOT)
    return_manifest = object_json(returned, "RETURN_MANIFEST.json")
    source_manifest = object_json(source, "TEST_PACKAGE_MANIFEST.json")

    declared = records(return_manifest)
    observed = {
        name: {"size_bytes": len(payload), "sha256": sha256_bytes(payload)}
        for name, payload in returned.items()
        if name != "RETURN_MANIFEST.json"
    }
    allowlist = {str(item["target_path"]) for item in source_manifest["return_allowlist"]}
    package_preflight = object_json(returned, "evidence/package_preflight.json")
    install_preflight = object_json(returned, "evidence/installed_preflight.json")
    canonical = object_json(returned, "evidence/CANONICAL_PROGRESS_DECISION.json")
    contract = object_json(returned, "evidence/progress_contract.json")
    signal = parse_kv(returned["evidence/signal_status.txt"])
    feature = parse_kv(returned["evidence/fp32_ingress_feature_receipt.txt"])
    timing = {
        key: int(value)
        for key, value in parse_kv(returned["evidence/host_timing.txt"]).items()
    }
    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    simulation_exit = int(
        returned["evidence/simulation_exit_status.txt"].decode().strip()
    )
    decision_exit = int(
        returned["evidence/canonical_decision_exit_status.txt"].decode().strip()
    )
    sim_log = returned["runs/sim.log"].decode(errors="replace")
    observer = returned["runs/return_observer.log"].decode(errors="replace")

    stage_starts = [int(v) for v in re.findall(r"\[(\d+)\] INFO: slice start", sim_log)]
    stage_finishes = [
        {"time_ps": int(time), "active_cycles": int(cycles)}
        for time, cycles in re.findall(
            r"\[(\d+)\] INFO: slice completed after (\d+) cycles", sim_log
        )
    ]
    natural_terminal = sim_log.count("Simulation completed successfully!") == 1
    formal_d = invalid_128bit_receipt(returned, source_manifest)

    digest_record = dict(canonical)
    stored_digest = digest_record.pop("content_digest")
    canonical_digest_valid = (
        stored_digest.get("algorithm") == "sha256"
        and stored_digest.get("scope") == "canonical_record_without_content_digest"
        and stored_digest.get("value")
        == sha256_bytes(
            json.dumps(digest_record, sort_keys=True, separators=(",", ":")).encode()
        )
    )
    event_counts = {
        name: len(re.findall(rf"(?m)^\d+ \| {name} \|", observer))
        for name in ("EXEC_START", "HEARTBEAT", "COMP_FINISH", "FINAL")
    }
    wall_seconds = (
        timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
    ) / 1_000_000_000

    server_result_gate = False
    checks = {
        "return_manifest_exact_set_size_sha": declared == observed,
        "return_allowlist_exact_membership": set(observed) <= allowlist,
        "returned_source_manifest_byte_binding": (
            returned["evidence/PACKAGE_MANIFEST.json"]
            == source["TEST_PACKAGE_MANIFEST.json"]
        ),
        "package_preflight_valid": package_preflight.get("valid") is True,
        "installed_preflight_valid": install_preflight.get("valid") is True,
        "runtime_formal_d_initially_absent": (
            package_preflight.get("formal_readback_targets_absent") is True
            and install_preflight.get("formal_readback_targets_absent") is True
        ),
        "compile_passed": compile_exit == 0,
        "simulation_passed": simulation_exit == 0,
        "signal_none": signal.get("signal") == "NONE",
        "natural_terminal": natural_terminal,
        "one_stage_started_and_completed": (
            len(stage_starts) == 1
            and len(stage_finishes) == 1
            and stage_finishes[0]["active_cycles"] == 543_212
        ),
        "observer_runtime_four_way": (
            feature.get("argv_enabled") == "true"
            and feature.get("time0_marker") == "true"
            and feature.get("returned_snapshot_marker") == "true"
            and parse_kv(returned["evidence/observer_binding.txt"]).get(
                "observer_enabled_and_returned"
            )
            == "true"
        ),
        "canonical_parser_passed": decision_exit == 0,
        "canonical_digest_valid": canonical_digest_valid,
        "canonical_b_dequant_completed": (
            canonical.get("decision") == "B_DEQUANT_CONTROL_COMPLETED"
            and canonical.get("boundary") == "OP_B_DEQUANT_COMP_FINISH"
            and canonical.get("ordered_final_scope", {}).get("expected_stage")
            == "op_b_dequant"
            and canonical.get("ordered_final_scope", {}).get("expected_stage_count")
            == 1
        ),
        "qualified_progress_not_level": (
            canonical.get("content_summary", {}).get("level_is_progress") is False
            and canonical.get("content_summary", {}).get("qualified_monotonic") is True
            and canonical.get("content_summary", {}).get("advancing_windows") == 32
        ),
        "formal_d_exact_paths_present": (
            formal_d["expected"] == 28
            and formal_d["present"] == 28
            and formal_d["missing"] == 0
            and formal_d["exact_path_set"] is True
        ),
        "formal_d_invalid_and_unevaluable": (
            formal_d["invalid_128bit_files"] == 28
            and formal_d["valid_128bit_files"] == 0
            and formal_d["mismatch_evaluable"] is False
        ),
        "server_result_gate_absent_and_false": (
            "evidence/SERVER_RESULT_GATE.json" not in returned
            and return_manifest.get("required_missing")
            == ["evidence/SERVER_RESULT_GATE.json"]
            and server_result_gate is False
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AnalysisError(f"return checks failed: {failed}")

    return {
        "schema": "qlinearadd-node0007-bctrl-v24-return-analysis-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": "RETURN_ANALYSIS_COMPLETE",
        "return_transport": {
            "path": str(return_zip),
            "bytes": RETURN_BYTES,
            "sha256": RETURN_SHA,
            "adjacent_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "rule_id": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
        },
        "source_package": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_BYTES,
            "sha256": SOURCE_SHA,
            "status": "RETURN_CONSUMED_DIAGNOSTIC_COMPLETE",
        },
        "zip_structure": return_structure,
        "source_zip_structure": source_structure,
        "identity": {
            "return_root": RETURN_ROOT,
            "install_name": source_manifest["install_name"],
            "return_manifest_exact": True,
            "allowlist_valid": True,
            "returned_source_manifest_byte_equal": True,
        },
        "checks": checks,
        "execution": {
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "runner_exit": "NONZERO_INFERRED_ANALYZE_DECODE_FAILURE_NOT_EXPLICITLY_RETURNED",
            "signal": signal.get("signal"),
            "natural_terminal": natural_terminal,
            "host_wall_seconds": wall_seconds,
            "host_wall_hours": wall_seconds / 3600,
            "sim_time_ps": 20_407_565_625,
            "sim_cpu_seconds": 6_131.8,
            "stage_starts_ps": stage_starts,
            "stage_completions": stage_finishes,
        },
        "observer": {
            "feature_receipt": feature,
            "progress_contract": contract,
            "event_counts": event_counts,
            "canonical_record": canonical,
            "canonical_content_digest_valid": canonical_digest_valid,
            "last_counter_snapshot": canonical["counter_snapshot"],
            "advancing_windows": canonical["content_summary"]["advancing_windows"],
            "level_counted_as_progress": False,
        },
        "formal_d": formal_d,
        "SERVER_RESULT_GATE": server_result_gate,
        "E3": False,
        "E4": False,
        "E5": False,
        "LAST_PROVEN_GOOD": (
            "OP_B_DEQUANT_NATURAL_COMP_FINISH_WITH_32_QUALIFIED_ADVANCING_WINDOWS"
        ),
        "FIRST_DIVERGENCE": (
            "POST_SIM_PACKAGE_ANALYZE_DECODE_128BIT_ON_UNEXECUTED_FULL_CHAIN_D"
        ),
        "HANG_ROOT_CAUSE": "NOT_A_HANG",
        "return_analysis": {
            "b_dequant_dynamic_claim": "PASS",
            "full_qlinearadd_numeric_claim": "NOT_EXECUTED_AND_UNEVALUABLE",
            "result_gate_reason": (
                "B-only execution naturally completed, but the unchanged full-chain "
                "analyzer attempted to decode 28 X-valued D dumps and exited before "
                "writing SERVER_RESULT_GATE.json"
            ),
        },
        "old_vs_new_package_adjudication": {
            "v20_b_stage_zero_delay_reproduced": False,
            "v24_same_b_config_with_v18_base_observer_completed": True,
            "conclusion": (
                "the v20 failure was introduced by its package-local observer path, "
                "not by the frozen B-dequant configuration or functional RTL"
            ),
        },
        "split_workload_impact": {
            "segment_A_two_dequants": "DYNAMIC_B_HALF_PROVEN; A_PACKAGE_STILL_REQUIRED",
            "segment_B_relocation_pad": "LOCAL_E2_PROVEN; PACKAGE_PENDING",
            "segment_C_prefix_through_fp32_add": "LOCAL_E2_PROVEN; PACKAGE_PENDING",
            "segment_D_full_chain": "FROZEN_FULL_CHAIN_REQUIRED_FOR_28D",
            "stage_local_result_gate_requirement": (
                "diagnostic segments must bind their own terminal/output contract and "
                "must not invoke the 28-D full-chain decoder"
            ),
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_QADD_V20_PACKAGE_LOCAL_FP32_OBSERVER_EVENT_STORM_SUSPECT",
                "B_QADD_NODE0007_OP_B_DEQUANT_DYNAMIC_COMPLETION_UNPROVEN",
            ],
            "opened": [
                "B_QADD_V24_B_ONLY_FULL_CHAIN_RESULT_GATE_SCOPE_MISMATCH"
            ],
            "kept_open": [
                "B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED",
                "B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN",
            ],
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_CONFIRMED_EFFECTIVE",
            "evidence": (
                "qualified ordered-stage evidence correctly proves only B-dequant; "
                "the conjunction rule correctly forbids E3/E4/E5 when the formal "
                "numeric gate is absent and D payloads are undecodable"
            ),
        },
        "SUCCESSOR_PROPOSAL": (
            "continue the already-authorized A/B/C/D true split materialization; "
            "stage-local packages use stage-local terminal/output gates, while D "
            "retains the six-stage plus 28-D full-chain conjunction"
        ),
        "PACKAGE_RELEASE": "NONE_RETURN_ANALYSIS_ONLY_SPLIT_PACKAGING_CONTINUES",
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "configuration_recomputed": False,
        "functional_rtl_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = analyze(args.return_zip)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as exc:
        print(f"analysis failed: {exc}")
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
