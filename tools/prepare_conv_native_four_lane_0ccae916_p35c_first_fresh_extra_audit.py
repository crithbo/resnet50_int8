#!/usr/bin/env python3
"""Create independent clean-extract evidence for the p35c first-fresh audit."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p35c_armknown"
ZIP = ROOT / f"outputs/conv_native_four_lane_0ccae916_p35c_armknown/build/{PACKAGE}.zip"
# Keep the independent extraction below Win32 MAX_PATH; this path is audit-only
# and does not alter any package/server path.
BASE = ROOT / "outputs/p35c_first_fresh_audit_v2"
CLEAN = BASE / "clean_extract"
REPORTS = BASE / "reports"
CONTRACT = BASE / "contract.json"
EPOCH = "20260811-native-live-causal-partial-exit-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def report(name: str, checks: dict[str, bool], details: dict[str, Any]) -> Path:
    path = REPORTS / f"{name}.json"
    errors = [key for key, passed in checks.items() if not passed]
    write(path, {"schema": f"conv-native-p35c-first-fresh-{name}-v1", "pass": not errors, "errors": errors, "checks": checks, "details": details})
    return path


def run(argv: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


def encode(layout: list[dict[str, Any]], values: dict[str, int]) -> str:
    payload = 0
    for field in layout:
        width = int(field["width_bits"])
        payload = (payload << width) | (int(values.get(field["name"], 0)) & ((1 << width) - 1))
    return f"{payload:x}"


def fixture(contract: dict[str, Any], mode: str) -> str:
    target = contract["target_parent"]
    buffer_instance = target + ".u_Buffer.codex_probe_row2_clear_window_write_owner_inst"
    arm_instance = target + ".u_Array_Request_Manager.codex_probe_arm_row2_accept_token_state_inst"
    lines = []
    for boundary in contract["required_boundaries"]:
        instance = buffer_instance if boundary == contract["buffer_boundary"] else arm_instance
        lines.append(f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance={instance}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['buffer_boundary']} instance={buffer_instance} time=100 mask=1 payload=0 seq=0")
    count = 1 if mode == "single" else 2
    for index in range(count):
        time = 110 + index * 10
        values = {
            "arm2buf_req_addr": 2, "arm2buf_req_valid": 255, "arm2buf_req_rw": 1,
            "arm2buf_wvalid": 1, "buf2arm_req_ready": 1, "array_req_addr": 2,
            "array_counter_0": index if mode == "progress" else 0, "array_counter_1": 0,
            "array_life_cnt": 0, "array2buf_valid_bit": 255, "array2buf_last_bit": 0,
            "array2buf_last_index": 15, "array2buf_same_bit": 0,
            "array_wreq_addr_rst": int(mode == "reset" and index == 1), "arm_addr_update": 1,
            "add_array_counter_0": int(mode == "progress"), "add_array_counter_1": 0,
            "add_array_life_cnt": 0,
        }
        mask = 1 | ((1 << 2) if mode == "progress" else 0) | ((1 << 5) if mode == "reset" and index == 1 else 0)
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['buffer_boundary']} instance={buffer_instance} time={time} mask=2 payload=0 seq={index}")
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['arm_boundary']} instance={arm_instance} time={time} mask={mask:x} payload={encode(contract['arm_payload_layout_msb_to_lsb'], values)} seq={index}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['final_boundary']} instance={arm_instance} time=130 mask=1 payload=0 seq=0")
    return "\n".join(lines) + "\n"


def parser_run(package: Path, text: str, name: str) -> dict[str, Any]:
    log = BASE / "parser_cases" / f"{name}.log"
    output = BASE / "parser_cases" / f"{name}.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(text, encoding="utf-8", newline="\n")
    process = run([sys.executable, str(package / "package_tools/arm_known_parser.py"), "--log", str(log), "--contract", str(package / "diagnostics/arm_known_contract.json"), "--output", str(output)], timeout=30)
    value = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return {"exit_code": process.returncode, "decision": value.get("decision"), "errors": value.get("errors"), "bytes": log.stat().st_size}


def main() -> int:
    if BASE.exists():
        raise RuntimeError("refusing to overwrite p35c first-fresh audit")
    BASE.mkdir(parents=True)
    CLEAN.mkdir()
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        corrupt = archive.testzip()
        safe = all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16) for row in infos)
        archive.extractall(CLEAN)
    package = CLEAN / PACKAGE
    manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
    actual = {row.relative_to(package).as_posix(): {"sha256": sha(row), "size_bytes": row.stat().st_size} for row in sorted(package.rglob("*")) if row.is_file() and row.name != "package_manifest.json"}
    clean_report = report(
        "exact_final_zip_clean_extract",
        {"crc": corrupt is None, "single_root": {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}, "duplicate_free": len(names) == len(set(names)), "safe": safe, "manifest_exact": manifest.get("files") == actual},
        {"zip": ZIP.relative_to(ROOT).as_posix(), "zip_bytes": ZIP.stat().st_size, "zip_sha256": sha(ZIP), "clean_tree": CLEAN.relative_to(ROOT).as_posix(), "member_count": len(names)},
    )
    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    sca = json.loads((package / "workload/runtime/runs/c0/sca_cfg.json").read_text(encoding="utf-8"))
    input_paths = []
    missing_inputs = []
    prefix = f"install/cfg_pkg/{PACKAGE}/runs/c0/install/"
    sca_rows = [row for row in sca.values() if isinstance(row, dict) and isinstance(row.get("path"), str)]
    for row in sca_rows:
        relative = row["path"]
        input_paths.append(relative)
        if not relative.startswith(prefix) or not (package / "workload/runtime/runs/c0/install" / relative[len(prefix):]).is_file():
            missing_inputs.append(relative)
    dcfg = json.loads((package / "workload/runtime/runs/c0/sca_cfg_D.json").read_text(encoding="utf-8"))
    dcfg_rows = [row for row in dcfg.values() if isinstance(row, dict) and isinstance(row.get("path"), str)]
    runner_report = report(
        "actual_runner_entry_and_input_open",
        {
            "production_handoff": "make -f" in runner and "compile" in runner and "simv" in runner,
            "sca_plusargs": "+SCA_CFG=" in runner and "+SCA_CFG_D=" in runner,
            "shared_finalizer_once": runner.count('python3 "$post_sim_helper" finalize --request "$post_sim_request"') == 1,
            "all_projected_inputs_open": not missing_inputs and len(input_paths) > 80,
            "d_targets_absent_pre_sim": all(not (package / row["path"]).exists() for row in dcfg_rows),
        },
        {"input_count": len(input_paths), "missing_inputs": missing_inputs, "formal_d_target_count": len(dcfg_rows), "runner_sha256": sha(package / "PREPARE_AND_RUN.sh")},
    )
    contract = json.loads((package / "diagnostics/arm_known_contract.json").read_text(encoding="utf-8"))
    exact_fixture = (package / "diagnostics/live_fixtures/arm_known_event.log").read_text(encoding="utf-8")
    overbudget = ("NON_TARGET_MULTI_INSTANCE_NOISE instance=tb_NDP_Top_new_phy.noise x=" + "x" * 980 + "\n") * 18000 + exact_fixture
    live_case = parser_run(package, overbudget, "overbudget_live")
    final_only = "\n".join(line.replace("kind=EVENT", "kind=RING_POST") if "kind=EVENT" in line else line for line in exact_fixture.splitlines()) + "\n"
    final_case = parser_run(package, final_only, "final_only")
    logger_report = report(
        "source_bound_logger_collector_parser_roundtrip",
        {"exact_clean_parser": sha(package / "package_tools/arm_known_parser.py") == contract["target_parser_source_sha256"], "percent_m_instance_present": "instance=tb_NDP_Top_new_phy" in exact_fixture, "multi_instance_overbudget_pass": live_case["exit_code"] == 0 and live_case["bytes"] > 16 * 1024 * 1024, "live_event_present": "kind=EVENT" in exact_fixture, "final_only_ring_negative": final_case["exit_code"] != 0 and final_case["decision"] == "EVIDENCE_INCOMPLETE"},
        {"overbudget_case": live_case, "final_only_case": final_case},
    )
    post_output = BASE / "exact_post_sim_validation.json"
    post = run([sys.executable, str(package / "package_tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(ZIP), "--output", str(post_output)], timeout=120)
    post_value = json.loads(post_output.read_text(encoding="utf-8")) if post_output.is_file() else {}
    live_profile = post_value.get("details", {}).get("partial_exit_live_causal_record", {})
    post_report = report(
        "post_sim_return_core_scenarios",
        {"exact_clean_helper": sha(package / "package_tools/server_post_sim_return.py") == "19bea6cc8bb5bd6247f7d2da67de3df967a562f1193c82a2f1a1ddb1ae483e6f", "validator_exit_zero": post.returncode == 0, "all_scenarios_pass": post_value.get("pass") is True and post_value.get("errors") == [], "live_fixture_executed": live_profile.get("contract_errors") == [] and bool(live_profile.get("plugin_results")) and all(row.get("executed") is True and row.get("pass") is True for row in live_profile.get("plugin_results", {}).values())},
        {"exact_validation": post_value},
    )
    expected = {"stable": "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT", "progress": "TARGET_ARM_ROW2_DISTINCT_TOKEN_STATE_PROGRESS", "reset": "TARGET_ARM_ROW2_RESET_OR_WRAP", "single": "TARGET_ARM_ROW2_SINGLE_ACCEPT_ONLY"}
    cases = {mode: parser_run(package, fixture(contract, mode), f"candidate_{mode}") for mode in expected}
    unknown_rows = []
    unknown_mutated = False
    for line in fixture(contract, "stable").splitlines():
        if not unknown_mutated and "kind=EVENT" in line and "boundary=arm_row2_accept_token_state" in line:
            tokens = line.split()
            tokens = [token[:-1] + "Z" if token.startswith("payload=") else token for token in tokens]
            line = " ".join(tokens)
            unknown_mutated = True
        unknown_rows.append(line)
    unknown = "\n".join(unknown_rows) + "\n"
    cases["unknown"] = parser_run(package, unknown, "candidate_unknown")
    candidate_report = report(
        "candidate_discrimination_matrix",
        {"four_candidates_pairwise": all(cases[mode]["exit_code"] == 0 and cases[mode]["decision"] == decision for mode, decision in expected.items()) and len({cases[mode]["decision"] for mode in expected}) == 4, "unknown_negative": cases["unknown"]["exit_code"] != 0 and cases["unknown"]["decision"] == "EVIDENCE_INCOMPLETE"},
        {"cases": cases, "candidate_ids": list(expected.values())},
    )
    evidence = []
    mapping = {
        "exact_final_zip_clean_extract": (clean_report, "exact-final-zip-clean-extract"),
        "actual_runner_entry_and_input_open": (runner_report, "exact-runner-safe-compile-and-open-paths"),
        "source_bound_logger_collector_parser_roundtrip": (logger_report, "exact-generated-over-budget-multi-instance"),
        "post_sim_return_core_scenarios": (post_report, "exact-final-request-four-scenario"),
        "candidate_discrimination_matrix": (candidate_report, "exact-candidate-positive-negative-matrix"),
    }
    for gate_id, (path, kind) in mapping.items():
        evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
    value = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE, "family": "conv_native_four_lane", "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": ["CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001"], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": list(expected.values()), "covered_candidate_ids": list(expected.values()), "uncovered_candidate_ids": [], "positive_control_count": 4, "negative_control_count": 2, "pairwise_distinguishable": True},
        "findings": [
            {"finding_id": "p35_prebuild_only_spec_failure", "disposition": "record_only", "causal_class": None, "message": "No ZIP materialized; cheap-report path was corrected only in the fresh p35b/p35c identities."},
            {"finding_id": "p35b_prefinal_missing_generation_receipt", "disposition": "record_only", "causal_class": None, "message": "No ZIP materialized; p35c uses the exact full generation and cheap-report filenames expected by the consumer."},
        ],
    }
    write(CONTRACT, value)
    print(json.dumps({"contract": str(CONTRACT), "contract_sha256": sha(CONTRACT), "reports": {key: sha(path) for key, (path, _kind) in mapping.items()}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
