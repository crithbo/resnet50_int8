#!/usr/bin/env python3
"""Bounded streaming analysis for the exact QAdd v67 config42 return.

The supplied archive is never extracted or modified.  Text evidence is read
line-by-line from ZipExtFile streams and durable checkpoints are appended as
each bounded phase completes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v67_cfg42_tg"
EXECUTION = "r1786793338560402996_2911236"
ATTEMPT = "a2911236"
EXPECTED_RETURN_BYTES = 131_087
EXPECTED_RETURN_SHA = "484fe4cad1e4b18db1c541eafe497720720465d38ac54e2f2c35d771902897b8"
EXPECTED_PACKAGE_BYTES = 108_687_211
EXPECTED_PACKAGE_SHA = "dbd18a58144321cdb252a9edf17b3fdc7d4087a00d6458d49bdb5d1a75443740"
CORRECT_BITSTREAM = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
REJECTED_BITSTREAM = "a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0"
OUT = ROOT / f"outputs/qlinearadd_node0007_v67_return_{EXECUTION}"
STREAM = OUT / "streaming_analysis"
CHUNKS = STREAM / "chunks"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temp.write_bytes(canonical(value))
    os.replace(temp, path)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_stream(stream: Any) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1 << 16), b""):
        size += len(block)
        digest.update(block)
    return size, digest.hexdigest()


def append_checkpoint(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = path.read_text(encoding="utf-8") if path.is_file() else ""
    marker = f'"checkpoint_id": "{value["checkpoint_id"]}"'
    if marker in prior:
        return
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def append_report(path: Path, heading: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = path.read_text(encoding="utf-8") if path.is_file() else ""
    if heading in prior:
        return
    with path.open("a", encoding="utf-8", newline="\n") as output:
        output.write(f"\n{heading}\n\n{body.rstrip()}\n")


def json_member(archive: zipfile.ZipFile, prefix: str, relative: str) -> dict[str, Any]:
    value = json.loads(archive.read(prefix + relative))
    if not isinstance(value, dict):
        raise ValueError(f"object required: {relative}")
    return value


def lines(archive: zipfile.ZipFile, member: str) -> Iterator[str]:
    with archive.open(member) as raw:
        for blob in raw:
            yield blob.decode("utf-8", errors="replace").rstrip("\r\n")


def scan_log(archive: zipfile.ZipFile, member: str) -> dict[str, Any]:
    counts = {
        "lines": 0,
        "matrix_loads": 0,
        "matrix_completions": 0,
        "read_bursts": 0,
        "heartbeats": 0,
        "pretarget_snapshots": 0,
        "target_entries": 0,
        "planned_dumpoff": 0,
        "one_shot_stop": 0,
        "terminal_witnesses": 0,
    }
    last: dict[str, Any] = {}
    for line in lines(archive, member):
        counts["lines"] += 1
        lower = line.lower()
        if "json: loading matrix[" in lower:
            counts["matrix_loads"] += 1
            last["matrix_load"] = {"line": counts["lines"], "text": line[:1024]}
        if "matrix transfer completed" in lower:
            counts["matrix_completions"] += 1
            last["matrix_completion"] = {"line": counts["lines"], "text": line[:1024]}
        burst = re.search(r"\[Read Burst (\d+)\].*Addr=(0x[0-9A-Fa-f]+).*Length=(\d+)", line)
        if burst:
            counts["read_bursts"] += 1
            last["read_burst"] = {
                "line": counts["lines"],
                "index": int(burst.group(1)),
                "address": burst.group(2).lower(),
                "length_words": int(burst.group(3)),
            }
        marker_map = {
            "codex_tbvcd_heartbeat": "heartbeats",
            "codex_tbvcd_pretarget_safety_snapshot": "pretarget_snapshots",
            "codex_tbvcd_target_entry": "target_entries",
            "codex_tbvcd_planned_dumpoff": "planned_dumpoff",
            "codex_tbvcd_stop_v5": "one_shot_stop",
            "codex_tbvcd_terminal_witness": "terminal_witnesses",
        }
        for marker, key in marker_map.items():
            if marker in lower:
                counts[key] += 1
                last[key] = {"line": counts["lines"], "text": line[:2048]}
    return {"counts": counts, "last": last}


def scan_vcd(archive: zipfile.ZipFile, member: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "bytes": archive.getinfo(member).file_size,
        "lines": 0,
        "var_count": 0,
        "timestamps": 0,
        "last_timestamp_ticks": None,
        "value_changes": 0,
        "value_characters": set(),
        "timescale": None,
        "eof_reached": False,
    }
    in_timescale = False
    timescale_parts: list[str] = []
    for line in lines(archive, member):
        result["lines"] += 1
        stripped = line.strip()
        if stripped.startswith("$var "):
            result["var_count"] += 1
        if stripped.startswith("$timescale"):
            in_timescale = True
            timescale_parts.append(stripped.removeprefix("$timescale").replace("$end", "").strip())
            if "$end" in stripped:
                in_timescale = False
        elif in_timescale:
            timescale_parts.append(stripped.replace("$end", "").strip())
            if "$end" in stripped:
                in_timescale = False
        if stripped.startswith("#") and stripped[1:].isdigit():
            result["timestamps"] += 1
            result["last_timestamp_ticks"] = int(stripped[1:])
        elif stripped and not stripped.startswith("$") and not stripped.startswith("#"):
            if stripped[0] in "01xXzZbBrR":
                result["value_changes"] += 1
                payload = stripped.split(None, 1)[0].lower()
                result["value_characters"].update(ch for ch in payload if ch in "01xz")
    result["timescale"] = "".join(timescale_parts).replace(" ", "") or None
    result["value_characters"] = sorted(result["value_characters"])
    result["eof_reached"] = True
    return result


def manifest_member(manifest: dict[str, Any], suffix: str) -> dict[str, Any] | None:
    files = manifest.get("files", {})
    if not isinstance(files, dict):
        return None
    for path, row in files.items():
        if path.endswith(suffix) and isinstance(row, dict):
            return {"path": path, **row}
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--package-zip", type=Path, required=True)
    args = parser.parse_args()
    return_zip = args.return_zip.resolve()
    package_zip = args.package_zip.resolve()
    if return_zip.stat().st_size != EXPECTED_RETURN_BYTES or sha_file(return_zip) != EXPECTED_RETURN_SHA:
        raise RuntimeError("exact formal return identity mismatch")
    if package_zip.stat().st_size != EXPECTED_PACKAGE_BYTES or sha_file(package_zip) != EXPECTED_PACKAGE_SHA:
        raise RuntimeError("exact source package identity mismatch")

    STREAM.mkdir(parents=True, exist_ok=True)
    checkpoint_path = STREAM / "checkpoints.jsonl"
    report_path = STREAM / "report.md"
    state_path = STREAM / "analysis_state.json"
    initial_state = {
        "schema": "qadd-v67-bounded-streaming-analysis-state-v1",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "status": "IDENTITY_VERIFIED",
        "return_zip": {"bytes": EXPECTED_RETURN_BYTES, "sha256": EXPECTED_RETURN_SHA},
        "source_package_zip": {"bytes": EXPECTED_PACKAGE_BYTES, "sha256": EXPECTED_PACKAGE_SHA},
        "bounded_member_policy": "Zip members are consumed one-at-a-time; sim.log and VCD are streamed line-by-line.",
    }
    atomic_json(state_path, initial_state)
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v67-stream-checkpoint-v1", "checkpoint_id": "001_identity",
        "sequence": 1, "status": "IDENTITY_VERIFIED", "return_sha256": EXPECTED_RETURN_SHA,
    })
    append_report(report_path, "# QAdd v67 formal return analysis", "Exact return and source package identities verified. Analysis is bounded and resumable.")

    with zipfile.ZipFile(return_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC failure: {bad}")
        names = archive.namelist()
        roots = {name.split("/", 1)[0] for name in names if name}
        if roots != {f"{PACKAGE}_return"}:
            raise RuntimeError(f"unexpected archive roots: {sorted(roots)}")
        if any(name.startswith("/") or ".." in Path(name).parts or "\\" in name for name in names):
            raise RuntimeError("unsafe ZIP member")
        prefix = f"{PACKAGE}_return/"
        actual = json_member(archive, prefix, "evidence/ACTUAL_COMPILE_SIM_ARGV.json")
        attempt = json_member(archive, prefix, "evidence/NATIVE_FAILURE_ATTEMPT.json")
        process = json_member(archive, prefix, "evidence/PROCESS_TREE_RECEIPT.json")
        decision = json_member(archive, prefix, "evidence/TB_VCD_LIVE_DECISION_RECEIPT.json")
        safety = json_member(archive, prefix, "evidence/TB_VCD_LIVE_SAFETY_RECEIPT.json")
        identity = json_member(archive, prefix, "evidence/TB_VCD_IDENTITY.json")
        dump = json_member(archive, prefix, "evidence/TB_VCD_DUMP_CONTROL_RECEIPT.json")
        stop = json_member(archive, prefix, "evidence/TB_VCD_STOP_RECEIPT.json")
        target = json_member(archive, prefix, "evidence/TB_VCD_TARGET_ENTRY_RECEIPT.json")
        sim_exit = json_member(archive, prefix, "return_core/SIM_EXIT_RECEIPT.json")
        core = json_member(archive, prefix, "return_core/RETURN_CORE_STATUS.json")
        lineage = json_member(archive, prefix, "source_package/CONFIG_LINEAGE_CONTRACT.json")
        config = json_member(archive, prefix, "source_package/op_tail_round_4_2.json")
        acceptance = json_member(archive, prefix, "source_package/qadd_config42_dynamic_acceptance.json")
        matrix = json_member(archive, prefix, "source_package/tb_vcd_candidate_matrix.json")
        manifest = json_member(archive, prefix, "source_package/TEST_PACKAGE_MANIFEST.json")
        compile_source = json_member(archive, prefix, "evidence/compile_source_identity.json")

        sim_log = scan_log(archive, prefix + "runs/sim.log")
        log_chunk = {
            "schema": "qadd-v67-stream-chunk-v1", "sequence": 2, "kind": "SIM_LOG",
            **sim_log,
        }
        atomic_json(CHUNKS / "002_sim_log.json", log_chunk)
        append_checkpoint(checkpoint_path, {
            "schema": "qadd-v67-stream-checkpoint-v1", "checkpoint_id": "002_sim_log",
            "sequence": 2, "status": "SIM_LOG_EOF", "lines": sim_log["counts"]["lines"],
            "matrix_completions": sim_log["counts"]["matrix_completions"],
            "target_entries": sim_log["counts"]["target_entries"],
        })
        append_report(
            report_path,
            "## Production log stream",
            f"Compile exit 0; simulation started. The log reached {sim_log['counts']['matrix_completions']} completed preloads and "
            f"{sim_log['counts']['read_bursts']} read bursts, but contains no target-entry or terminal marker.",
        )

        vcd_member = prefix + "evidence/vcd/wave.vcd"
        vcd = scan_vcd(archive, vcd_member)
        with archive.open(vcd_member) as raw:
            vcd_bytes, vcd_sha = sha_stream(raw)
        vcd["sha256"] = vcd_sha
        vcd["identity_exact"] = vcd_bytes == identity.get("identity_bytes") and vcd_sha == identity.get("identity_sha256")
        vcd_chunk = {"schema": "qadd-v67-stream-chunk-v1", "sequence": 3, "kind": "VCD", **vcd}
        atomic_json(CHUNKS / "003_vcd.json", vcd_chunk)
        append_checkpoint(checkpoint_path, {
            "schema": "qadd-v67-stream-checkpoint-v1", "checkpoint_id": "003_vcd",
            "sequence": 3, "status": "VCD_EOF", "bytes": vcd["bytes"], "lines": vcd["lines"],
            "last_timestamp_ticks": vcd["last_timestamp_ticks"], "var_count": vcd["var_count"],
        })
        append_report(
            report_path,
            "## VCD stream",
            f"The complete {vcd['bytes']}-byte VCD has {vcd['var_count']} variables but its last timestamp is "
            f"{vcd['last_timestamp_ticks']}; it contains only the time-0 snapshot and is partial evidence.",
        )

    samples = process.get("samples", [])
    sample_projection = [
        {
            "seq": row.get("seq"),
            "wall_seconds": row.get("wall_seconds"),
            "owner_clock_cycles": row.get("owner_clock_cycles"),
            "sim_time_ticks": row.get("sim_time_ticks"),
            "appended_vcd_timestamp_ticks": row.get("appended_vcd_timestamp_ticks"),
            "pretarget_matrix_completions": row.get("global_progress_witness", {}).get("pretarget_matrix_completions"),
        }
        for row in samples
    ]
    owner_advancing = all(
        int(samples[index].get("owner_clock_cycles", 0)) > int(samples[index - 1].get("owner_clock_cycles", 0))
        for index in range(1, len(samples))
    )
    execution_time_advancing = all(
        int(samples[index].get("sim_time_ticks", 0)) > int(samples[index - 1].get("sim_time_ticks", 0))
        for index in range(1, len(samples))
    )
    vcd_time_static = len(samples) >= 4 and len({int(row.get("appended_vcd_timestamp_ticks", 0)) for row in samples}) == 1
    semantic_chunk = {
        "schema": "qadd-v67-stream-chunk-v1", "sequence": 4, "kind": "SEMANTIC_V5_EXIT",
        "samples": sample_projection,
        "owner_clock_advancing": owner_advancing,
        "execution_sim_time_advancing": execution_time_advancing,
        "appended_vcd_timestamp_static": vcd_time_static,
        "planned_dumpoff_observed": dump.get("planned_dumpoff_observed"),
        "decision": decision.get("decision"),
        "adjudication": "RULE_CONFORMING_FREEZE_FROM_PACKAGE_LOCAL_PRETARGET_DUMP_CONTROL_DEFECT",
        "reason": "Before a planned dumpoff semantic-v5 intentionally uses appended VCD timestamps. v67 opened and closed each pretarget snapshot in one simulation time slot, so no timestamp advanced despite owner-clock and execution-time progress.",
    }
    atomic_json(CHUNKS / "004_semantic_v5_exit.json", semantic_chunk)
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v67-stream-checkpoint-v1", "checkpoint_id": "004_exit",
        "sequence": 4, "status": "EXIT_ADJUDICATED", "decision": decision.get("decision"),
        "owner_clock_advancing": owner_advancing, "execution_time_advancing": execution_time_advancing,
        "vcd_time_static": vcd_time_static,
    })

    bitstream = manifest_member(manifest, "op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin")
    config42 = (
        config["buffer_loop_configs"]["GROUP2"]["COL_LC"]["end"] == 4
        and config["buffer_loop_configs"]["GROUP2"]["COL_LC"]["stride"] == 2
    )
    identity_binding = (
        actual.get("package_id") == PACKAGE
        and actual.get("execution_id") == EXECUTION
        and actual.get("attempt_id") == ATTEMPT
        and manifest.get("package_id") == PACKAGE
        and manifest.get("install_name") == PACKAGE
    )
    lineage_exact = (
        lineage.get("pass") is True
        and config42
        and lineage.get("packaged_bitstream_sha256") == CORRECT_BITSTREAM
        and lineage.get("rejected_bad_bitstream") == {"rejected": True, "sha256": REJECTED_BITSTREAM}
        and bitstream is not None and bitstream.get("sha256") == CORRECT_BITSTREAM
        and actual.get("source_identity_status") == "COMPLETE"
        and actual.get("sca_cfg", "").endswith(f"/{PACKAGE}/sca_cfg.json")
        and actual.get("sca_cfg_d", "").endswith(f"/{PACKAGE}/sca_cfg_D.json")
    )
    candidates = [row.get("candidate_id") for row in matrix.get("candidates", [])]
    target_entered = target.get("observed") is True or sim_log["counts"]["target_entries"] > 0
    natural = stop.get("natural_terminal") is True or sim_exit.get("natural_terminal_observed") is True
    dynamic = {
        "schema": "qadd-v67-stream-chunk-v1", "sequence": 5, "kind": "DYNAMIC_ACCEPTANCE",
        "required_order": acceptance.get("required_ordered_sequence"),
        "observed": {
            "target_entry": target_entered,
            "request_0x33333333": False,
            "first_accept": False,
            "first_clear": False,
            "request_0xcccccccc": False,
            "second_accept": False,
            "second_clear": False,
            "repeated_first_alias_absent": None,
            "output": False,
            "natural_terminal": natural,
            "formal_D": False,
        },
        "status": "NOT_EXERCISED",
    }
    atomic_json(CHUNKS / "005_dynamic_acceptance.json", dynamic)

    compile_exit = int(attempt.get("compile_exit", -1))
    sim_code = int(attempt.get("simulation_exit", sim_exit.get("sim_exit_code", -1)))
    process_reaped = process.get("process_tree_reaped") is True
    termination_count = len(process.get("termination", []))
    analysis = {
        "schema": "qlinearadd-node0007-v67-config42-tg-formal-return-analysis-v1",
        "role_id": "family.qlinearadd",
        "package_id": PACKAGE,
        "execution_id": EXECUTION,
        "attempt_id": ATTEMPT,
        "status": "RETURN_ANALYSIS_COMPLETE_PACKAGE_BUILD_FAILURE_RULE_AUDIT_REQUIRED",
        "integrity": {
            "return_identity_exact": True,
            "source_package_identity_exact": True,
            "zip_crc_pass": True,
            "single_safe_root": True,
            "identity_binding_pass": identity_binding,
            "return_disposition": core.get("disposition"),
        },
        "production": {
            "compile_exit": compile_exit,
            "compile_succeeded": compile_exit == 0,
            "simulation_started": attempt.get("simulation_started") is True,
            "simulation_exit": sim_code,
            "stop_reason": safety.get("stop_reason"),
            "target_entry_observed": target_entered,
            "log_stream": sim_log,
            "process_tree_reaped": process_reaped,
            "owned_pids_remaining": process.get("owned_pids_remaining", []),
            "termination_action_count": termination_count,
        },
        "DIRECT_CONFIG_EVIDENCE": {
            "group2_col_lc": {"end": 4, "stride": 2},
            "lineage_exact": lineage_exact,
            "bitstream_sha256": CORRECT_BITSTREAM,
            "rejected_32_16_bitstream_sha256": REJECTED_BITSTREAM,
            "actual_sca_cfg": actual.get("sca_cfg"),
            "actual_sca_cfg_D": actual.get("sca_cfg_d"),
        },
        "DIRECT_ACTUAL_RTL_EVIDENCE": {
            "compile_source_identity": compile_source,
            "functional_rtl_identity_boundary": "The return hashes the package-local bound TB and server Makefile, but not the transitive NDP_copy04 functional RTL tree. No byte-exact claim about actual compiled functional RTL is made from this return.",
            "historical_consumer_contract": lineage.get("actual_rtl_consumer_sources"),
        },
        "DYNAMIC_EXECUTION_EVIDENCE": dynamic,
        "root_disposition": {
            "historical_validated_root_cause": lineage.get("validated_root_cause"),
            "config_lineage_repair_materialized_and_compiled": lineage_exact,
            "functional_repair_dynamically_validated": False,
            "classification": "OPEN_UNVALIDATED_MECHANISM",
            "reason": "The target did not enter, so the ordered masks, accepts, clears, alias exclusion, output and terminal contract were not exercised.",
        },
        "last_proven_good": {
            "classification": "EXACT_4_2_LINEAGE_PRODUCTION_COMPILE_AND_FAST_PRETARGET_PROGRESS",
            "detail": "The exact 4/2 package compiled and the same attempt completed two package/config preloads, entered slice00 matrix reads and reached read burst 45 while owner-clock and execution time advanced.",
        },
        "first_divergence": {
            "classification": "PACKAGE_LOCAL_ZERO_DURATION_PRETARGET_SNAPSHOT_FALSE_FREEZE",
            "detail": "At 90 seconds the supervisor saw three static appended-VCD intervals because each snapshot opened and closed in one time slot; it terminated before target entry even though execution time advanced 0 -> 102501 -> 348261 -> 532581 ticks.",
        },
        "semantic_v5_exit": semantic_chunk,
        "candidate_matrix": {
            "pairwise_complete": matrix.get("pairwise_complete"),
            "rows": [
                {"candidate_id": candidate, "status": "NOT_REACHED_NOT_ADJUDICABLE", "reason": "target entry absent"}
                for candidate in candidates
            ],
        },
        "boundaries": {
            "natural_terminal": False,
            "formal_D": False,
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": "Non-natural package-local pretarget stop with partial VCD and incomplete process-tree reap.",
        },
        "package_local_defects": [
            "pretarget snapshot does not span an owner-clock/time advance, so appended VCD timestamps remain static",
            "target-capture validator checks cadence but not timestamp advancement or shared-evaluator replay of the real snapshot trace",
            "PID ownership is not start-time bound; persistent known PID tracking can retain/re-signal a dead or reused PID",
            f"termination loop emitted {termination_count} actions and still reported unreaped descendants",
            "compile_first_error extraction labels a normal 'Parsing design file' line as an error even though compile_exit=0",
        ],
        "audit_trigger": "SECOND_CONSECUTIVE_PACKAGE_LOCAL_PRETARGET_FAILURE_BEFORE_THIRD_ATTEMPT",
        "successor_status": "BLOCKED_PENDING_MACHINE_READABLE_AUDIT_AND_PACKAGE_LOCAL_NEGATIVE_CONTROLS",
        "frozen_surfaces": ["validated_config42", "numeric", "workload", "golden", "functional_rtl", "tail_round_target", "64_signal_target_cone", "candidate_matrix"],
        "pass": identity_binding and compile_exit == 0 and attempt.get("simulation_started") is True and lineage_exact and not target_entered,
        "errors": [],
        "claim_boundary": "This return proves exact 4/2 lineage selection, production compile and advancing pretarget execution only. It does not dynamically validate the repair or prove root closure, natural/formal-D/E3/E4/E5.",
    }
    atomic_json(OUT / "formal_return_analysis.json", analysis)
    applicability = {
        "schema": "qadd-package-build-failure-rule-audit-applicability-v1",
        "role_id": "family.qlinearadd",
        "target": "validated config42 dynamic tail-round acceptance",
        "consecutive_package_local_pretarget_failures": [
            {
                "package_id": "r5_qadd_n7_tailround_lanephase_v66_cfg42",
                "failure": "full-rate pretarget VCD imposed sufficient overhead to hit the wall ceiling before target entry",
            },
            {
                "package_id": PACKAGE,
                "failure": "zero-duration pretarget snapshots left appended VCD time at zero and triggered semantic-v5 SIM_TIME_FREEZE before target entry",
            },
        ],
        "triggered": True,
        "third_attempt_forbidden_until_audit": True,
        "pass": True,
        "errors": [],
    }
    audit = {
        "schema": "qadd-v67-package-build-failure-rule-audit-v1",
        "role_id": "family.qlinearadd",
        "package_id": PACKAGE,
        "trigger": "SECOND_CONSECUTIVE_PACKAGE_LOCAL_PRETARGET_FAILURE_BEFORE_THIRD_ATTEMPT",
        "attempts": applicability["consecutive_package_local_pretarget_failures"],
        "shared_rule_audit": {
            "semantic_v5_confirmed": True,
            "rule_gap": False,
            "reason": "The active rule explicitly uses appended VCD time before planned dumpoff. The v67 package violated that premise; the evaluator did not escape its contract.",
        },
        "hard_gate_gap": {
            "present": True,
            "validator": "tools/validate_qlinearadd_node0007_v67_cfg42_target_capture.py",
            "missing_negative_controls": [
                "pretarget snapshot must span a real owner-clock/time advance",
                "the actual package snapshot trace must keep appended VCD timestamps advancing under the shared evaluator",
                "same-time dumpon/dumpflush/dumpoff must fail",
                "PID reuse must not remain in the owned-process set",
                "a non-child zombie must not trigger repeated KILL",
                "termination receipt action count must be bounded",
            ],
        },
        "runner_gap": {
            "present": True,
            "evidence": {
                "termination_action_count": termination_count,
                "owned_pids_remaining": process.get("owned_pids_remaining", []),
            },
            "required_fix": "Bind tracked PIDs to immutable process start time, discard reused identities/non-owned zombies, reap adopted children, and send bounded TERM/KILL actions.",
        },
        "disposition": "MACHINE_READABLE_PACKAGE_LOCAL_EXEMPTION_WITH_NEGATIVE_CONTROLS",
        "public_rule_delta_proposed": False,
        "machine_readable_exemption": {
            "exemption_id": "qadd-pretarget-safety-pulse-v1",
            "scope": "fresh successor only",
            "allowed": "Before target entry, one safety pulse per 16384 owner cycles may open the already source-bound VCD for at least one subsequent owner-clock edge; it is transport evidence only.",
            "required": [
                "each pulse advances appended VCD time",
                "all 64 source-bound variables remain catalogued",
                "continuous untruncated capture is armed before the target-entry marker",
                "no pretarget pulse supports a functional/root claim",
                "no byte/event/time cap, truncation, or size deletion",
            ],
            "forbidden": [
                "same-time dumpon and dumpoff",
                "target-window sampling",
                "pretending a safety pulse is functional evidence",
                "changing config, numeric, workload, golden, functional RTL, causal target, catalog, or candidate matrix",
            ],
        },
        "third_attempt_admission": {
            "package_id": "r5_qadd_n7_tailround_lanephase_v68_cfg42_t2",
            "requires_all_negative_controls": True,
            "requires_exact_final_zip_replay": True,
            "requires_current_first_fresh": True,
            "storage_manager_allowed": False,
        },
        "pass": True,
        "errors": [],
        "claim_boundary": "This audit authorizes only a package-local transport/runner repair under the existing public rule. It does not authorize server action or any functional/config delta beyond the already frozen 4/2 lineage.",
    }
    atomic_json(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT_APPLICABILITY.json", applicability)
    atomic_json(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json", audit)
    append_checkpoint(checkpoint_path, {
        "schema": "qadd-v67-stream-checkpoint-v1", "checkpoint_id": "005_family_disposition",
        "sequence": 5, "status": analysis["status"],
        "last_proven_good": analysis["last_proven_good"]["classification"],
        "first_divergence": analysis["first_divergence"]["classification"],
        "analysis_sha256": sha_file(OUT / "formal_return_analysis.json"),
    })
    append_report(
        report_path,
        "## Family disposition",
        "- exact 4/2 lineage and production compile: `PROVEN`\n"
        "- target entry / ordered masks / accepts / clears / output / terminal: `NOT EXERCISED`\n"
        "- LAST_PROVEN_GOOD: exact 4/2 compile plus advancing pretarget slice00 reads\n"
        "- FIRST_DIVERGENCE: `PACKAGE_LOCAL_ZERO_DURATION_PRETARGET_SNAPSHOT_FALSE_FREEZE`\n"
        "- semantic-v5: evaluator behavior matches the active rule; the package snapshot trace violates its pre-dumpoff timestamp premise\n"
        "- natural/formal-D/E3/E4/E5: not proven\n"
        "- third attempt requires `PACKAGE_BUILD_FAILURE_RULE_AUDIT` and machine-checked package-local fixes.",
    )
    final_state = dict(initial_state)
    final_state.update({
        "status": "EOF_REACHED_FAMILY_ANALYSIS_COMPLETE",
        "sim_log": {"lines": sim_log["counts"]["lines"], "eof_reached": True},
        "vcd": {"bytes": vcd["bytes"], "lines": vcd["lines"], "last_timestamp_ticks": vcd["last_timestamp_ticks"], "eof_reached": True},
        "last_proven_good": analysis["last_proven_good"]["classification"],
        "first_divergence": analysis["first_divergence"]["classification"],
        "formal_analysis_sha256": sha_file(OUT / "formal_return_analysis.json"),
        "package_build_failure_rule_audit_sha256": sha_file(OUT / "PACKAGE_BUILD_FAILURE_RULE_AUDIT.json"),
    })
    atomic_json(state_path, final_state)
    print(json.dumps({"analysis": str(OUT / "formal_return_analysis.json"), "pass": analysis["pass"]}, sort_keys=True))
    return 0 if analysis["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
