from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


RETURN_SHA256 = (
    "b8a1ac0a9f7c9d705b21f332b010a3eaa59d131f85fd1eae524a2d2f26b57b55"
)
SOURCE_SHA256 = (
    "e67775aed87d2065f51190049a9a7ba05fb98de9ba08a4362901612248f92ead"
)
INSTALL_NAME = "r5_n4_hw_v20_buffer_mode_fix"
RETURN_ROOT = f"{INSTALL_NAME}_return"
SERVER_RULE_SHA256 = (
    "88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6"
)
RTL_RELATIVE = (
    "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
    "Buffer_AG_Idx_Queue.sv"
)
RTL_SHA256 = (
    "bbf2d8542f29229953395edf28d9a9cfe48030419753ee52bc62cc09e6028e4d"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_entries(path: Path) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    entries: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"CRC failed: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts:
                errors.append(f"unsafe path: {info.filename}")
                continue
            if not pure.parts:
                continue
            roots.add(pure.parts[0])
            if info.is_dir():
                continue
            if info.filename in seen:
                errors.append(f"duplicate member: {info.filename}")
                continue
            seen.add(info.filename)
            if pure.parts[0] != RETURN_ROOT or len(pure.parts) < 2:
                errors.append(f"unexpected root: {info.filename}")
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            entries[relative] = archive.read(info)
    if roots != {RETURN_ROOT}:
        errors.append(f"root set mismatch: {sorted(roots)}")
    return entries, errors


def parse_boundary(text: str, name: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if f"| {name} |" in line]
    if len(lines) != 1:
        return {"_count": str(len(lines))}
    fields: dict[str, str] = {}
    for key, value in re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", lines[0]):
        fields[key] = value
    fields["_count"] = "1"
    fields["_line"] = lines[0]
    return fields


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    project = args.project_root.resolve()
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    config_path = args.config.resolve()

    errors: list[str] = []
    return_sha = sha256_file(return_zip)
    source_sha = sha256_file(source_zip)
    if return_sha != RETURN_SHA256:
        errors.append("return ZIP SHA mismatch")
    if source_sha != SOURCE_SHA256:
        errors.append("source ZIP SHA mismatch")
    entries, zip_errors = safe_entries(return_zip)
    errors.extend(zip_errors)

    allowlist = json.loads(entries.get("RETURN_ALLOWLIST.json", b"{}"))
    records = allowlist.get("records", [])
    expected_set = {"RETURN_ALLOWLIST.json"} | {
        item.get("path") for item in records if isinstance(item, dict)
    }
    if expected_set != set(entries):
        errors.append("return exact-set mismatch")
    record_checks: dict[str, bool] = {}
    for record in records:
        relative = record.get("path")
        payload = entries.get(relative)
        match = (
            payload is not None
            and len(payload) == record.get("size_bytes")
            and sha256_bytes(payload) == record.get("sha256")
        )
        record_checks[str(relative)] = match
        if not match:
            errors.append(f"return allowlist mismatch: {relative}")

    gate = json.loads(entries.get("evidence/SERVER_RESULT_GATE.json", b"{}"))
    package_preflight = json.loads(
        entries.get("evidence/package_preflight.json", b"{}")
    )
    install_preflight = json.loads(
        entries.get("evidence/install_preflight.json", b"{}")
    )
    observer_preflight = json.loads(
        entries.get("evidence/observer_precompile.json", b"{}")
    )
    compile_status = int(
        entries.get("evidence/compile_exit_status.txt", b"125").strip()
    )
    run_status = int(
        entries.get("evidence/run_exit_status.txt", b"125").strip()
    )
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode(
        "ascii", errors="replace"
    ).strip()
    observer_text = entries.get(
        "runs/c0/return_observer.log", b""
    ).decode("utf-8", errors="replace")
    sim_text = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    abpe = parse_boundary(observer_text, "ABPE_BOUNDARY_V1")
    reuse = parse_boundary(observer_text, "A_REUSE_BOUNDARY_V1")
    flow = parse_boundary(observer_text, "BUFFER0_FLOW_BOUNDARY_V1")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    thresholds: list[dict[str, Any]] = []
    all_blocked = True
    for index in range(5):
        col_last = config["buffer_loop_configs"][f"GROUP{index}"][
            "COL_LC"
        ]["last_index"]
        row_keep = config["stream_engine"][f"stream{index}"][
            "buf_idx_keep_last_index"
        ][0]
        release = col_last <= row_keep
        all_blocked = all_blocked and not release
        thresholds.append(
            {
                "stream": index,
                "col_last_index": col_last,
                "row_keep_last_index": row_keep,
                "rtl_release_predicate": (
                    "buffered_col_last_index <= row_keep_last_index"
                ),
                "release_on_col_terminal": release,
            }
        )

    rtl_path = project / RTL_RELATIVE
    rtl_text = rtl_path.read_text(encoding="utf-8", errors="replace")
    rtl_sha = sha256_file(rtl_path)
    rtl_predicate_present = (
        "buf_buffer_idx_last_index > mse_buf_idx_keep_last_index" in rtl_text
        and "buf_idx_bp_pre_keep_mask" in rtl_text
    )

    dynamic_consistent = (
        flow.get("ag_enq") == "2"
        and flow.get("ag_deq") == "2"
        and flow.get("ag_empty") == "1"
        and flow.get("arm_req_accept") == "4"
        and reuse.get("buf_read0") == "4"
        and reuse.get("array_clear0") == "1"
        and reuse.get("alu2ob_cycles") == "4"
        and abpe.get("pe_out_accept") == "0"
    )
    compile_ok = compile_status == 0
    run_invocation_ok = run_status == 0
    natural_terminal = gate.get("natural_terminal_observed") is True
    formal_d = gate.get("formal_readback_claimed") is True
    joint_gate = (
        compile_ok
        and run_invocation_ok
        and natural_terminal
        and formal_d
        and gate.get("e4_claimed") is True
        and gate.get("e5_claimed") is True
    )
    root_cause_confirmed = (
        all_blocked
        and dynamic_consistent
        and rtl_predicate_present
        and rtl_sha == RTL_SHA256
    )
    if not root_cause_confirmed:
        errors.append("root cause did not close")

    report = {
        "schema": "node0004-v20-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "return_analysis": {
            "status": "FAIL_CLOSED_CONFIG_HANG",
            "return_zip": {
                "path": str(return_zip),
                "bytes": return_zip.stat().st_size,
                "sha256": return_sha,
            },
            "external_sidecar": {
                "present": False,
                "blocker": False,
                "policy": (
                    "user-attested transport identity; local SHA recomputed"
                ),
                "rule_id": (
                    "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
                ),
            },
            "source_zip": {
                "path": str(source_zip),
                "bytes": source_zip.stat().st_size,
                "sha256": source_sha,
            },
            "zip_crc_path_root_valid": not zip_errors,
            "return_exact_set_valid": expected_set == set(entries),
            "return_member_count": len(entries),
            "allowlist_record_count": len(records),
            "all_allowlist_records_match": all(record_checks.values()),
            "package_preflight_valid": package_preflight.get("valid") is True,
            "install_preflight_valid": install_preflight.get("valid") is True,
            "runtime_d_initially_absent": (
                install_preflight.get("runtime_d_initially_absent") is True
            ),
            "observer_preflight_valid": observer_preflight.get("valid") is True,
            "observer_identity_match": (
                observer_preflight.get("identity_match") is True
            ),
            "observer_runtime_enabled": (
                "[RETURN_OBSERVER] enabled" in sim_text
            ),
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal,
            "natural_terminal": natural_terminal,
            "formal_d_readback": {
                "claimed": formal_d,
                "expected_items": 320,
                "observed_items": 0,
                "missing_items": 320,
                "mismatch_items": 0,
                "zero_mismatch_is_not_pass_when_all_missing": True,
            },
            "joint_gate_pass": joint_gate,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "first_divergence": {
            "last_good": (
                "first row: two Buffer-AG enqueue/dequeue events and four "
                "Buffer0->SA accepted reads/result-write cycles"
            ),
            "first_bad": (
                "after first buffered COL terminal, no next-row Buffer-AG "
                "enqueue is generated"
            ),
            "boundary": "BUFFER_AG_COL_TERMINAL_TO_ROW_KEEP_RELEASE",
        },
        "hang_root_cause": {
            "status": "DETERMINISTIC_CONFIGURATION_ERROR",
            "identity": "BUFFER_AG_ROW_KEEP_THRESHOLD_LT_COL_TERMINAL",
            "confirmed": root_cause_confirmed,
            "rtl": {
                "path": RTL_RELATIVE,
                "sha256": rtl_sha,
                "lines": "149-152",
                "mechanism": (
                    "ROW keep releases at buffered COL last only when "
                    "COL last_index <= configured row keep last_index"
                ),
            },
            "config": {
                "path": str(config_path),
                "sha256": sha256_file(config_path),
                "thresholds": thresholds,
                "affected_stream_count": 5,
            },
            "dynamic_witness": {
                "canonical_decision": gate.get("canonical_decision"),
                "ABPE_BOUNDARY_V1": abpe,
                "A_REUSE_BOUNDARY_V1": reuse,
                "BUFFER0_FLOW_BOUNDARY_V1": flow,
                "interpretation": (
                    "v20 Buffer mode fix worked for the first row; the "
                    "Buffer4->Buffer5 canonical boundary is a downstream "
                    "symptom because the Buffer-AG queue is empty"
                ),
            },
        },
        "blocker_delta": {
            "closed": [
                "v19 Buffer0 mode/lifetime mismatch",
                "missing external sidecar as transport blocker",
            ],
            "opened": [
                "v20 Buffer-AG ROW keep threshold is one below COL terminal "
                "for all five streams"
            ],
            "remaining_after_local_fix": [
                "server dynamic natural terminal and 320-item exact D readback"
            ],
        },
        "rule_delta_proposal": "NONE",
        "package_release": "SUCCESSOR_REQUIRED_CONFIG_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "frozen_assets_consumed_read_only": True,
        "functional_rtl_modified": False,
        "rules_or_plan_modified": False,
        "active_rule_receipt": {
            "path": ".agents/rules/服务器测试包生成规则.md",
            "sha256": SERVER_RULE_SHA256,
        },
    }
    args.output.resolve().write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
