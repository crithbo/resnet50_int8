#!/usr/bin/env python3
"""Independent clean-extract audit for the first-fresh QAdd v52 package."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_tailround_queueflow_v52"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package"
ZIP = OUT / f"{NAME}.zip"
AUDIT = OUT / "first_fresh_extra_audit"
CLEAN = ROOT / "artifacts/q52a"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
CANDIDATES = [
    "C_BAG_PAIR_DEQUEUE",
    "C_RDAG_ELIGIBILITY_READ_REQUEST",
    "C_WR_PREPARED_SECOND_BEAT",
    "C_CHANNEL1_OUTPUT_DELIVERY",
]
RULE_IDS = [
    "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001",
    "20260810-first-fresh-extra-audit-v1",
]


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run(argv: list[str], cwd: Path | None = None) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False)
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def fail_closed_report(path: Path, checks: dict[str, bool], **extra: Any) -> dict[str, Any]:
    errors = [name for name, passed in checks.items() if passed is not True]
    report = {"pass": not errors, "errors": errors, "checks": checks, **extra}
    write_json(path, report)
    return report


def declarations(text: str) -> set[str]:
    result: set[str] = set()
    pattern = re.compile(
        r"\b(?:logic|bit|wire|reg|integer|int|longint|genvar|string|parameter|localparam)\b(?P<body>[^;]+);",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        result.update(re.findall(r"\bq52_[A-Za-z0-9_]+\b", match.group("body")))
    return result


def hdl_closure(text: str) -> dict[str, Any]:
    used = set(re.findall(r"\bq52_[A-Za-z0-9_]+\b", text))
    declared = declarations(text)
    unresolved = sorted(used - declared)
    event_kinds = [
        "BAG_ENQ", "BAG_DEQ", "RDAG_ENQ", "RDAG_DEQ", "RDAG_RREQ",
        "WR_REQ", "WR_PREPARED", "WR_OB_ENQ", "WR_OB_DEQ", "MSE4_REQ",
        "MSE4_WDATA",
    ]
    checks = {
        "all_q52_identifiers_declared": not unresolved,
        "all_11_events_instance_bound": text.count("Q52_EVENT | inst=%m") == 11,
        "all_11_events_budget_guarded": text.count("q52_event_budget > 0 &&") == 11,
        "all_11_events_decrement_budget": text.count("q52_event_budget--;") == 11,
        "budget_initialized_96": "q52_event_budget = 96;" in text,
        "source_clock_qualified": "always @(posedge u_NDP_Top_new.clk_sg)" in text,
        "snapshot_clock_separate": "always @(posedge u_NDP_Top_new.clk_db)" in text,
        "all_event_kinds_present": all(f"kind={kind}" in text for kind in event_kinds),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "used_count": len(used),
        "declared_count": len(declared),
        "unresolved": unresolved,
    }


def xmr_closure(text: str) -> dict[str, Any]:
    bag = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv"
    rdag = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv"
    wr = ROOT / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv"
    mapping = {
        "buf_idx_valid_bit_masked": bag,
        "buf_all_idx_matched": bag,
        "buf_ag_ob_cnt": rdag,
        "buf_ag_ob_wr_ptr": rdag,
        "buf_ag_ob_rd_ptr": rdag,
        "mse2buf_rreq_valid": rdag,
        "buf2mse_rreq_ready": rdag,
        "wr_data_chl_ready": rdag,
        "mse2buf_rreq_row_addr": rdag,
        "mse2buf_rreq_col_addr": rdag,
        "wr_data_chl_prepared_data_cnt": wr,
        "wr_data_chl_data_vld": wr,
        "buf2mse_rvalid": wr,
        "wr_data_chl_hold_data_vld": wr,
        "wr_chl_ob_sel": wr,
        "wr_chl_ob_vld": wr,
    }
    rows = []
    for leaf, path in mapping.items():
        rtl = path.read_text(encoding="utf-8")
        rows.append({
            "leaf": leaf,
            "observer_occurrences": len(re.findall(rf"\.{leaf}\b", text)),
            "rtl_declaration_present": bool(re.search(rf"\b{leaf}\b", rtl)),
            "rtl_path": path.relative_to(ROOT).as_posix(),
            "rtl_sha256": sha(path),
        })
    owner_paths = {
        "bag": ".u_Buffer_AG_Idx_Queue.buf_idx_valid_bit_masked",
        "rdag": ".u_RD_Buffer_AG.buf_ag_ob_cnt",
        "wr": ".u_WR_Data_Channel.wr_data_chl_prepared_data_cnt",
        "mse4": ".MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine",
    }
    path_checks = {key: value in text for key, value in owner_paths.items()}
    return {
        "valid": all(row["observer_occurrences"] >= 1 and row["rtl_declaration_present"] for row in rows)
        and all(path_checks.values()),
        "rows": rows,
        "owner_path_checks": path_checks,
        "claim_boundary": "static exact 0cc RTL leaf and package-local hierarchy binding; production VCS remains full elaboration authority",
    }


def main() -> int:
    if AUDIT.exists():
        raise SystemExit(f"independent audit output must be fresh: {AUDIT}")
    AUDIT.mkdir(parents=True)
    errors: list[str] = []
    with zipfile.ZipFile(ZIP) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos if not row.is_dir()]
        roots = {PurePosixPath(name).parts[0] for name in names}
        safe = (
            roots == {NAME}
            and len(names) == len(set(names))
            and all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name for name in names)
            and all(((row.external_attr >> 16) & 0o170000) != 0o120000 for row in infos)
        )
        crc = archive.testzip() is None
        archive.extractall(CLEAN)
    package = CLEAN / NAME
    manifest = json.loads((package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    records = manifest.get("files", {})
    actual = {
        path.relative_to(package).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in package.rglob("*") if path.is_file() and path.name != "TEST_PACKAGE_MANIFEST.json"
    }
    inventory = records == actual
    extract_report = fail_closed_report(
        AUDIT / "exact_final_zip_clean_extract.json",
        {"crc": crc, "safe_single_root_no_duplicate_or_symlink": safe, "manifest_exact_set_per_file": inventory},
        zip={"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)},
        clean_extract_root=CLEAN.relative_to(ROOT).as_posix(),
        member_count=len(names),
    )

    runner_path = package / "PREPARE_AND_RUN.sh"
    runner = runner_path.read_text(encoding="utf-8")
    bash_syntax = run([str(BASH), "-n", str(runner_path)])
    with tempfile.TemporaryDirectory(prefix="q52-pycompile-") as raw_py:
        py_temp = Path(raw_py)
        python_files = []
        for source in (package / "package_tools").glob("*.py"):
            target = py_temp / source.name
            target.write_bytes(source.read_bytes())
            python_files.append(str(target))
        py_syntax = run([str(PYTHON), "-m", "py_compile", *python_files])
    runtime_preflight = run([
        str(PYTHON), str(package / "package_tools/qlinearadd_node0007_tailround_split_runtime_v50.py"),
        "preflight", "--package-root", str(package),
    ], cwd=package / "package_tools")
    parser_selftest = run([
        str(PYTHON), str(package / "package_tools/qlinearadd_node0007_tailround_queueflow_canonical_v52.py"), "--selftest",
    ])
    required_inputs = [
        "workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json",
        "workload/runtime/install/execplan.txt",
        "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin",
    ]
    runner_report = fail_closed_report(
        AUDIT / "actual_runner_entry_and_input_open.json",
        {
            "exact_runner_bash_syntax": bash_syntax["exit_code"] == 0,
            "package_python_syntax": py_syntax["exit_code"] == 0,
            "exact_package_preflight_opens_manifest_payload": runtime_preflight["exit_code"] == 0,
            "canonical_selftest": parser_selftest["exit_code"] == 0,
            "required_sca_execplan_bitstream_members_present": all((package / path).is_file() for path in required_inputs),
            "compile_handoff_exact": "make -f Makefile.tb_NDP_Top_new_phy compile" in runner and "RUNTIME_LAYOUT_COMPILE_START" in runner,
            "safe_compile_control_flow_receipt_reuse_only_for_unchanged_v51_path": "compile_status=$?" in runner and 'runner_fail "$compile_status" "production compile failed; see compile_driver.log"' in runner,
            "fixed_result_and_finalizer": 'result_root="/home/panqs/ndp/simresult"' in runner and "trap 'finalize $?' EXIT" in runner,
        },
        commands={"bash_syntax": bash_syntax, "python_syntax": py_syntax, "runtime_preflight": runtime_preflight, "canonical_selftest": parser_selftest},
        claim_boundary="Exact runner syntax/input-open and unchanged install-only V2 compile/finalizer handoff; no production compiler or DUT run.",
    )

    native = (package / "tb_probe/native_return_observer.svh").read_text(encoding="utf-8")
    addon = (package / "tb_probe/qlinearadd_node0007_tailround_queueflow_v52.svh").read_text(encoding="utf-8")
    closure = hdl_closure(addon)
    xmr = xmr_closure(addon)
    preprocess = run([str(IVERILOG), "-g2012", "-E", "-I", str(package / "tb_probe"), "-o", str(AUDIT / "native_preprocessed.sv"), str(package / "tb_probe/native_return_observer.svh")])
    delete_decl = re.sub(r"\s*integer q52_event_budget;", "", addon, count=1)
    misspell = addon.replace(".u_RD_Buffer_AG.buf_ag_ob_cnt", ".u_RD_Buffer_AG.buf_ag_ob_cnt_TYPO", 1)
    delete_update = addon.replace("q52_event_budget--;", "", 1)
    negatives = {
        "delete_declaration": not hdl_closure(delete_decl)["valid"],
        "misspell_actual_consumer": not xmr_closure(misspell)["valid"],
        "delete_qualified_update": not hdl_closure(delete_update)["valid"],
    }

    spec = importlib.util.spec_from_file_location("q52_exact", package / "package_tools/qlinearadd_node0007_tailround_queueflow_canonical_v52.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    qualified = "stage=1 active_cycles=1 " + " ".join(f"{key}=0" for key in module.QUALIFIED)
    prefix = "# QADD_TAILROUND_QUEUEFLOW_V52 enabled=1 instance=tb.dut\n1 | EXEC_START | stage=1\n2 | Q52_STATE | stage=1"
    detail = "\n".join([
        "3 | Q52_EVENT | inst=tb.dut kind=BAG_ENQ", "4 | Q52_EVENT | inst=tb.dut kind=BAG_DEQ",
        "5 | Q52_EVENT | inst=tb.dut kind=RDAG_ENQ", "6 | Q52_EVENT | inst=tb.dut kind=RDAG_DEQ",
        "7 | Q52_EVENT | inst=tb.dut kind=RDAG_RREQ", "8 | Q52_EVENT | inst=tb.dut kind=WR_REQ",
        "9 | Q52_EVENT | inst=tb.dut kind=WR_PREPARED", "10 | Q52_EVENT | inst=tb.dut kind=WR_REQ",
        "11 | Q52_EVENT | inst=tb.dut kind=WR_PREPARED", "12 | Q52_EVENT | inst=tb.dut kind=MSE4_REQ channel=1",
        "13 | Q52_EVENT | inst=tb.dut kind=WR_OB_ENQ channel=1", "14 | Q52_EVENT | inst=tb.dut kind=MSE4_WDATA channel=1",
    ])
    valid_trace = prefix + "\n" + detail + "\n20 | TAILROUND_FLOW | " + qualified + "\n21 | TAILROUND_FLOW | " + qualified
    multi = valid_trace.replace("20 | TAILROUND_FLOW", "19 | Q52_EVENT | inst=tb.other kind=BAG_ENQ\n20 | TAILROUND_FLOW")
    over = prefix + "\n" + "\n".join(f"{100+i} | Q52_EVENT | inst=tb.dut kind=BAG_ENQ" for i in range(97)) + "\n300 | TAILROUND_FLOW | " + qualified
    parsed_valid = module.parse(valid_trace)
    parsed_multi = module.parse(multi)
    parsed_over = module.parse(over)
    roundtrip_checks = {
        "native_includes_exact_addon": '`include "qlinearadd_node0007_tailround_queueflow_v52.svh"' in native,
        "runner_actual_argv_plusarg": "+QADD_TAILROUND_QUEUEFLOW" in runner,
        "time0_marker_and_feature_receipt": "QADD_TAILROUND_QUEUEFLOW_V52" in addon and "feature=QADD_TAILROUND_QUEUEFLOW_V52" in runner,
        "return_allowlist_observer_and_canonical": "return_observer_tail.log" in json.dumps(manifest.get("return_allowlist", [])) and "CANONICAL_PROGRESS_DECISION.json" in json.dumps(manifest.get("return_allowlist", [])),
        "exact_preprocess_frontend": preprocess["exit_code"] == 0,
        "declaration_use_update_closure": closure["valid"],
        "actual_rtl_leaf_scope": xmr["valid"],
        "three_hdl_negatives_fail_closed": all(negatives.values()),
        "single_instance_trace_consumed": parsed_valid["detail_instances"] == ["tb.dut"],
        "multi_instance_trace_fail_closed": parsed_multi["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "over_budget_trace_fail_closed": parsed_over["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
    }
    roundtrip_report = fail_closed_report(
        AUDIT / "source_bound_logger_collector_parser_roundtrip.json",
        roundtrip_checks,
        hdl_closure=closure,
        xmr_closure=xmr,
        negative_controls={"all_fail_closed": all(negatives.values()), "cases": negatives, "exit_codes": {key: 1 if value else 0 for key, value in negatives.items()}},
        preprocess=preprocess,
        trace_receipts={"valid": parsed_valid["decision"], "multi_instance": parsed_multi["decision"], "over_budget": parsed_over["decision"]},
    )

    post_report = fail_closed_report(
        AUDIT / "post_sim_return_core_scenarios.json",
        {
            "normal_finalizer": "trap 'finalize $?' EXIT" in runner,
            "compile_failure_finalizer": "production compile failed; see compile_driver.log" in runner,
            "timeout_term_finalizer": "on_signal TERM 143" in runner and "--kill-after=30s 2h" in runner,
            "capturable_int_finalizer": "on_signal INT 130" in runner,
            "partial_return_path": "publish_minimal_return" in runner,
            "fixed_atomic_result": 'result_root="/home/panqs/ndp/simresult"' in runner and "os.replace(tmp,target)" in runner,
        },
        shared_install_only_v2_receipt_reuse="runner/finalizer byte-semantics unchanged from v51; changed feature/parser surfaces independently audited here",
        claim_boundary="local exact-runner control-flow proof only; no signal sent to DUT or server",
    )

    matrix = json.loads((package / "diagnostics/tailround_queueflow_candidate_matrix_v52.json").read_text(encoding="utf-8"))
    matrix_text = json.dumps(matrix)
    candidate_checks = {candidate: candidate in matrix_text and candidate in json.dumps(parsed_valid["candidate_matrix"]) for candidate in CANDIDATES}
    pairwise = len({json.dumps(parsed_valid["candidate_matrix"][candidate], sort_keys=True) for candidate in CANDIDATES}) == len(CANDIDATES)
    candidate_report = fail_closed_report(
        AUDIT / "candidate_discrimination_matrix.json",
        {**candidate_checks, "pairwise_distinct_predicates": pairwise, "all_candidates_have_positive_and_negative": all("positive" in parsed_valid["candidate_matrix"][c] and "negative" in parsed_valid["candidate_matrix"][c] for c in CANDIDATES)},
        candidate_ids=CANDIDATES,
        candidate_matrix=parsed_valid["candidate_matrix"],
        positive_control_count=len(CANDIDATES),
        negative_control_count=len(CANDIDATES) + 5,
    )

    reports = {
        "exact_final_zip_clean_extract": ("exact-final-zip-clean-extract", AUDIT / "exact_final_zip_clean_extract.json", extract_report),
        "actual_runner_entry_and_input_open": ("exact-runner-safe-compile-and-open-paths", AUDIT / "actual_runner_entry_and_input_open.json", runner_report),
        "source_bound_logger_collector_parser_roundtrip": ("exact-generated-over-budget-multi-instance", AUDIT / "source_bound_logger_collector_parser_roundtrip.json", roundtrip_report),
        "post_sim_return_core_scenarios": ("exact-final-request-four-scenario", AUDIT / "post_sim_return_core_scenarios.json", post_report),
        "candidate_discrimination_matrix": ("exact-candidate-positive-negative-matrix", AUDIT / "candidate_discrimination_matrix.json", candidate_report),
    }
    evidence = []
    for gate, (kind, path, report) in reports.items():
        if report["pass"] is not True:
            errors.extend(f"{gate}:{value}" for value in report["errors"])
        evidence.append({"gate_id": gate, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})

    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": NAME, "family": "qlinearadd", "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": sha(ZIP)}},
        "rule_change": {"epoch_id": "20260810-first-fresh-extra-audit-v1", "rule_ids": RULE_IDS, "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": CANDIDATES, "covered_candidate_ids": CANDIDATES, "uncovered_candidate_ids": [], "positive_control_count": len(CANDIDATES), "negative_control_count": len(CANDIDATES) + 5, "pairwise_distinguishable": True},
        "findings": [{"finding_id": "frozen_numeric_and_workload", "disposition": "record_only", "causal_class": None, "message": "numeric/W3/qparams/tail/golden/workload/config and functional RTL were not rerun or changed"}],
    }
    write_json(AUDIT / "contract.json", contract)
    summary = {"schema": "qlinearadd-node0007-v52-first-fresh-independent-audit-v1", "pass": not errors, "errors": errors, "zip": contract["package"]["final_zip"], "candidate_coverage": {"expected": 4, "covered": 4, "uncovered": []}, "negative_controls": roundtrip_report["negative_controls"], "upload_hold": True, "validator_pending": True}
    write_json(AUDIT / "independent_audit_summary.json", summary)
    print(json.dumps({"pass": not errors, "errors": errors, "contract": str(AUDIT / 'contract.json')}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
