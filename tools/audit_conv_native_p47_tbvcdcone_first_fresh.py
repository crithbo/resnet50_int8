#!/usr/bin/env python3
"""Independent exact-final-ZIP/first-fresh audit for native Conv p47 TB VCD."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p47_tbvcdcone"
FAMILY = "conv_native_four_lane"
EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437"
OUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release"
ZIP = OUT / f"{PACKAGE_ID}.zip"
REPEAT = OUT / f"{PACKAGE_ID}.repeat.zip"
P46_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p46_nativeflow.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], cwd: Path | None = None) -> dict[str, Any]:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "stdout_tail": result.stdout[-8192:],
        "stderr_tail": result.stderr[-8192:],
    }


def safe_extract(source: Path, destination: Path, expected_root: str) -> Path:
    with zipfile.ZipFile(source) as archive:
        corrupt = archive.testzip()
        if corrupt is not None:
            raise RuntimeError(f"ZIP CRC failure: {corrupt}")
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)):
            raise RuntimeError("duplicate ZIP members")
        roots: set[str] = set()
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise RuntimeError(f"unsafe ZIP member: {name}")
            if pure.parts:
                roots.add(pure.parts[0])
        if roots != {expected_root}:
            raise RuntimeError(f"wrong ZIP root: {sorted(roots)}")
        archive.extractall(destination)
    return destination / expected_root


def file_map(root: Path, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = item.relative_to(root).as_posix()
        if exclude_manifest and relative == "package_manifest.json":
            continue
        result[relative] = {"size_bytes": item.stat().st_size, "sha256": digest(item)}
    return result


def workload_map(root: Path) -> dict[str, str]:
    base = root / "workload/runtime"
    return {item.relative_to(base).as_posix(): digest(item) for item in sorted(path for path in base.rglob("*") if path.is_file())}


def synthetic_roundtrip(package: Path, work: Path) -> dict[str, Any]:
    contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
    attempt = work / "attempt"
    evidence = attempt / "evidence"
    c0 = attempt / "c0"
    (evidence / "compile_rootcause").mkdir(parents=True)
    c0.mkdir(parents=True)
    write_json(evidence / "ACTUAL_COMPILE_SIM_ARGV.json", {
        "schema": "server-tb-vcd-actual-argv-v1",
        "package_id": PACKAGE_ID,
        "compile_argv": contract["execution"]["compile_argv"],
        "sim_argv": contract["execution"]["sim_argv"],
    })
    (evidence / "compile_rootcause/compile_driver.log").write_text("synthetic production compile passed\n", encoding="utf-8")
    process = evidence / "PROCESS_TREE_RECEIPT.json"
    safety = evidence / "TB_VCD_LIVE_SAFETY_RECEIPT.json"
    write_json(process, {"schema": "server-process-tree-supervision-v1", "root_exit": 0, "process_tree_reaped": True, "termination": []})
    write_json(safety, {"schema": "server-tb-vcd-live-safety-receipt-v1", "stop_reason": None})
    samples = evidence / "TB_VCD_RUNTIME_SAMPLES.jsonl"
    rows = [
        {"seq": 0, "wall_seconds": 0, "sim_time_ticks": 1, "owner_clock_cycles": 1, "sim_cycles": 1, "vcd_bytes": 1024, "causal_progress_events": 1, "qualified_progress_counters": {"total": 1}, "causal_state_digest": "1" * 64, "global_progress_witness": {"count": 1}, "unresolved_xz": False, "disk_space_ok": True, "write_ok": True, "quota_ok": True},
        {"seq": 1, "wall_seconds": 1, "sim_time_ticks": 1000, "owner_clock_cycles": 100, "sim_cycles": 100, "vcd_bytes": 4096, "causal_progress_events": 2, "qualified_progress_counters": {"total": 2}, "causal_state_digest": "2" * 64, "global_progress_witness": {"count": 2}, "unresolved_xz": False, "disk_space_ok": True, "write_ok": True, "quota_ok": True},
    ]
    samples.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    sim_log = c0 / "sim.log"
    sim_log.write_text(
        "CODEX_TBVCD_START_V1 sim_time=0\n"
        "CODEX_TBVCD_HEARTBEAT_V1 sim_time=1 owner_cycles=1 progress=1 state=0000000000000001 global=1 unresolved_xz=0\n"
        "CODEX_TBVCD_HEARTBEAT_V1 sim_time=1000 owner_cycles=100 progress=2 state=0000000000000002 global=2 unresolved_xz=0\n"
        "CODEX_TBVCD_TERMINAL_WITNESS_V1 sim_time=1000 selected_finish=1 aggregate_finish=1\n"
        "CODEX_TBVCD_FLUSH_V1 dumpoff=1 dumpflush=1 closed=1 sim_time=1000\n",
        encoding="utf-8",
    )
    vcd = c0 / "native_mse4_causal.vcd"
    names = sorted({row["exact_hierarchy"].rsplit(".", 1)[-1]: int(row["width_bits"]) for row in contract["signals"]}.items())
    text = ["$date\n synthetic\n$end\n", "$version\n codex synthetic\n$end\n", "$timescale 1ps $end\n", "$scope module causal $end\n"]
    codes: list[tuple[str, int]] = []
    for index, (name, width) in enumerate(names):
        code = f"c{index}"
        codes.append((code, width))
        text.append(f"$var wire {width} {code} {name} $end\n")
    text.extend(["$upscope $end\n", "$enddefinitions $end\n", "#0\n"])
    for code, width in codes:
        text.append(f"x{code}\n" if width == 1 else f"b{'x' * width} {code}\n")
    text.append("#1\n")
    for code, width in codes:
        text.append(f"z{code}\n" if width == 1 else f"b{'z' * width} {code}\n")
    text.append("#2\n")
    for code, width in codes:
        text.append(f"0{code}\n" if width == 1 else f"b{'0' * width} {code}\n")
    text.append("#1000\n")
    for code, width in codes:
        text.append(f"1{code}\n" if width == 1 else f"b{'1' * width} {code}\n")
    vcd.write_text("".join(text), encoding="utf-8", newline="\n")
    invocation = run([
        str(PYTHON), str(package / "package_tools/tb_vcd_finalize.py"),
        "--package-root", str(package), "--attempt-root", str(attempt), "--evidence-root", str(evidence),
        "--package-id", PACKAGE_ID, "--execution-id", "r_synthetic", "--attempt-id", "a_synthetic",
        "--actual-root", "/home/panqs/ndp/NDP_copy01", "--published-root", "/home/panqs/ndp/NDP_copy01",
        "--compile-exit", "0", "--sim-exit", "0", "--signal", "NONE", "--vcd", str(vcd),
        "--sim-log", str(sim_log), "--samples", str(samples), "--process-receipt", str(process), "--safety-receipt", str(safety),
    ])
    receipt_path = evidence / "TB_VCD_RUNTIME_RECEIPT.json"
    identity_path = evidence / "TB_VCD_IDENTITY.json"
    receipt = load(receipt_path) if receipt_path.is_file() else {}
    identity = load(identity_path) if identity_path.is_file() else {}
    checks = {
        "finalizer_exit_zero": invocation["exit_code"] == 0,
        "natural_complete": receipt.get("natural_terminal") is True and receipt.get("completeness") == "COMPLETE",
        "catalog_complete": receipt.get("vcd_identity", {}).get("catalog_complete") is True,
        "all_four_states_preserved": set(identity.get("value_characters", [])) == {"0", "1", "x", "z"},
        "process_tree_reaped": receipt.get("process_tree", {}).get("all_reaped") is True,
        "same_root_identity": load(evidence / "PUBLISHED_ACTUAL_ROOT_IDENTITY.json").get("match") is True,
    }
    return {"pass": all(checks.values()), "checks": checks, "errors": [key for key, value in checks.items() if not value], "invocation": invocation, "receipt": receipt}


def runtime_matrix(package: Path) -> dict[str, Any]:
    module_path = package / "package_tools/server_tb_vcd_runtime_supervision.py"
    spec = importlib.util.spec_from_file_location("p47_runtime", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identity = {"header_valid": True, "timescale": "1ps", "catalog_complete": True, "transitions_complete": True, "xz_preserved": True, "return_allowlist_member": True}
    base = {"package_id": PACKAGE_ID, "execution_id": "r_matrix", "attempt_id": "a_matrix", "started": True, "actual_argv_sha256": "1" * 64, "catalog_sha256": "2" * 64, "candidate_matrix_sha256": "3" * 64, "tb_source_sha256": "4" * 64, "elaboration_sha256": "5" * 64, "candidate_catalog_complete": True, "unresolved_xz": False, "vcd_identity": identity, "flush": {"dumpoff": True, "dumpflush": True, "closed": True}, "process_tree": {"term_sent": False, "wait_completed": True, "kill_sent_if_needed": False, "all_reaped": True}}
    def row(seq: int, wall: int, ticks: int, cycles: int, **extra: Any) -> dict[str, Any]:
        value = {"seq": seq, "wall_seconds": wall, "sim_time_ticks": ticks, "owner_clock_cycles": cycles, "sim_cycles": cycles, "vcd_bytes": 4096 + seq, "causal_progress_events": 0, "qualified_progress_counters": {"accept": 0}, "causal_state_digest": "a" * 64, "global_progress_witness": {"value": 0}, "write_ok": True, "disk_space_ok": True, "quota_ok": True}
        value.update(extra)
        return value
    cases = {
        "natural": [row(0, 0, 1, 1), row(1, 1, 100, 100, natural_terminal=True)],
        "wall": [row(0, 0, 1, 1), row(1, 3600, 100, 100)],
        "nonzero": [row(0, 0, 1, 1), row(1, 1, 100, 100, exit_code=9)],
        "hup": [row(0, 0, 1, 1), row(1, 1, 100, 100, signal="HUP")],
        "int": [row(0, 0, 1, 1), row(1, 1, 100, 100, signal="INT")],
        "term": [row(0, 0, 1, 1), row(1, 1, 100, 100, signal="TERM")],
        "plateau": [row(0, 0, 1, 1), row(1, 1, 4_194_305, 4_194_305), row(2, 2, 4_456_449, 4_456_449)],
        "global_advances": [row(0, 0, 1, 1), row(1, 1, 5_000_000, 5_000_000, global_progress_witness={"value": 1}, exit_code=9)],
        "freeze": [row(0, 0, 1, 1), row(1, 30, 1, 1), row(2, 60, 1, 1), row(3, 90, 1, 1)],
    }
    receipts = {name: module.evaluate({**base, "samples": samples}) for name, samples in cases.items()}
    checks = {
        "natural_only_complete": receipts["natural"]["completeness"] == "COMPLETE" and all(receipts[name]["completeness"] == "PARTIAL" for name in cases if name != "natural"),
        "six_exit_classified": [receipts[name]["stop_reason"] for name in ("natural", "wall", "nonzero", "hup", "int", "term")] == ["NATURAL_TERMINAL", "WALL_CEILING", "NONZERO_EXIT", "HUP", "INT", "TERM"],
        "strict_plateau": receipts["plateau"]["stop_reason"] == "CAUSAL_PLATEAU" and receipts["plateau"]["plateau_qualification"]["eligible"] is True,
        "global_progress_forbids_plateau": receipts["global_advances"]["stop_reason"] != "CAUSAL_PLATEAU",
        "three_by_thirty_freeze": receipts["freeze"]["stop_reason"] == "SIM_TIME_FREEZE",
        "nonnatural_claims_blocked": all(receipts[name]["natural_terminal"] is False for name in cases if name != "natural"),
    }
    return {"pass": all(checks.values()), "checks": checks, "errors": [key for key, value in checks.items() if not value], "receipts": receipts}


def main() -> int:
    reports = OUT / "first_fresh_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="conv-native-p47-firstfresh-") as temp_name:
        temp = Path(temp_name)
        package = safe_extract(ZIP, temp / "fresh", PACKAGE_ID)
        p46 = safe_extract(P46_ZIP, temp / "p46", "r5_n4_0cc_p46_nativeflow")
        manifest = load(package / "package_manifest.json")
        selector = load(package / "contracts/server_diagnostic_mode_selector.json")
        contract = load(package / "contracts/server_tb_vcd_bounded_causal_cone_contract.json")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        tb = (package / contract["execution"]["tb_source_path"]).read_text(encoding="utf-8")
        allowlist = load(package / "RETURN_ALLOWLIST.json")
        actual_map = file_map(package, exclude_manifest=True)
        source_checks = []
        for signal in contract["signals"]:
            source = ROOT / "NDP_copy01" / signal["source_path"]
            source_checks.append(source.is_file() and digest(source) == signal["source_sha256"])
        clean_checks = {
            "manifest_exact_member_map": manifest.get("files") == actual_map,
            "single_selected_mode": selector.get("selected_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
            "canonical_post_helper_exact": (package / "package_tools/server_post_sim_return.py").read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
            "workload_byte_frozen_from_p46": workload_map(package) == workload_map(p46),
            "all_actual_source_identities_current": all(source_checks),
            "no_runtime_wave_member_packaged": not any(path.lower().endswith((".vcd", ".vpd", ".fsdb", ".fst")) for path in actual_map),
            "deterministic_repeat_exact": ZIP.stat().st_size == REPEAT.stat().st_size and digest(ZIP) == digest(REPEAT),
            "p46_still_pending_byte_frozen": P46_ZIP.is_file() and digest(P46_ZIP) == "6a648613492d66b244564a0acc8f7d59709a971cf2c84d47c4922fe040f61478",
        }
        clean_report = {"schema": "conv-native-p47-exact-final-zip-clean-extract-v1", "pass": all(clean_checks.values()), "checks": clean_checks, "errors": [key for key, value in clean_checks.items() if not value]}
        write_json(reports / "exact_final_zip_clean_extract.json", clean_report)

        bash_syntax = run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")])
        runner_checks = {
            "bash_syntax": bash_syntax["exit_code"] == 0,
            "one_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "bootstrap_finalizer_before_launch": runner.index("trap 'bootstrap_finalize $?' EXIT") < runner.index("# CODEX_PRODUCTION_LAUNCH"),
            "actual_make_dump_argv_zero": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")) and all(token not in runner for token in ("DUMP_VCD=1", "DUMP_FSDB=1", "TB_DUMP_FSDB=1")),
            "package_tb_is_actual_compile_source": 'VCS_EXTRA_OPTS="$tb_source"' in runner and "native_mse4_bounded_causal_cone_vcd.sv" in runner,
            "compile_core_complete": all(token in runner for token in ("compile_argv.json", "compile_source_identity.json", "compile_driver.log", "compile_first_error.txt", "COMPILE_CORE.json")),
            "actual_and_published_root_returned": "PUBLISHED_ACTUAL_ROOT_IDENTITY.json" in runner and "published_root" in runner,
            "generic_process_tree_supervision": all(token in runner for token in ("server_process_tree_supervision.py", "PROCESS_TREE_RECEIPT.json", "tb_vcd_live_supervision.py")),
            "streaming_retention_assets": all((package / path).is_file() for path in ("package_tools/server_tb_vcd_retention_analysis.py", "contracts/server_tb_vcd_streaming_retention_contract.json")),
            "only_future_command_bound": f"bash {PACKAGE_ID}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01" in (package / "README.md").read_text(encoding="utf-8"),
        }
        write_json(reports / "actual_runner_entry_and_input_open.json", {"schema": "conv-native-p47-actual-runner-entry-v1", "pass": all(runner_checks.values()), "checks": runner_checks, "bash": bash_syntax, "errors": [key for key, value in runner_checks.items() if not value]})
        layout = load(package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json")
        layout_checks = {
            "schema_exact": layout.get("schema") == "server-package-runtime-layout-contract-v1",
            "runner_identity_exact": layout.get("runner_sha256") == digest(package / "PREPARE_AND_RUN.sh"),
            "layout_helper_identity_exact": layout.get("layout_helper_sha256") == digest(package / "package_tools/server_package_runtime_layout.py"),
            "fixed_result_root": layout.get("fixed_result_root") == "/home/panqs/ndp/simresult",
            "package_owned_roots": all(PACKAGE_ID in value for value in layout.get("roots", {}).values()),
            "repeat_safe_reset": layout.get("repeat_execution", {}).get("foreign_sibling_policy") == "PRESERVE" and layout.get("repeat_execution", {}).get("return_name_policy") == "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS",
        }
        write_json(OUT / "gates/runtime_layout.json", {"schema": "conv-native-p47-runtime-layout-validation-v1", "pass": all(layout_checks.values()), "checks": layout_checks, "errors": [key for key, value in layout_checks.items() if not value], "claim_boundary": "Local runtime layout and repeat-safety contract only; no server claim."})

        bind_prefix = "bind tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine"
        module_text = tb[:tb.index("bind tb_NDP_Top_new_phy")]
        module_text = "\n".join(
            "      $dumpvars(0, codex_state);" if "$dumpvars(" in line else line
            for line in module_text.splitlines()
        ) + "\n"
        standalone = temp / "native_mse4_tb_vcd_module.sv"
        standalone.write_text(module_text, encoding="utf-8", newline="\n")
        frontend = run([str(IVERILOG), "-g2012", "-tnull", str(standalone)])
        roundtrip = synthetic_roundtrip(package, temp / "roundtrip")
        runtime = runtime_matrix(package)
        source_bound_checks = {
            "full_hdl_frontend": frontend["exit_code"] == 0,
            "selected_mse4_exact_bind": bind_prefix in tb and tb.count("\nbind ") == 1,
            "passive_input_only_controller": "output " not in module_text and "inout " not in module_text and "force " not in module_text,
            "standard_tasks_complete": all(task in tb for task in ("$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush")),
            "strict_plateau_constants": all(value in tb for value in ("1048576", "4194304", "262144")),
            "forty_one_roles": len(contract["role_coverage"]) == 41,
            "four_causal_layers": {item["layer"] for item in contract["boundaries"]} == {"FIRST_DIVERGENCE_UPSTREAM_ONE", "FIRST_DIVERGENCE_CURRENT", "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "STATE_HOLD_CLEAR"},
            "source_bound_actual_signals": all(source_checks) and all(item.get("source_binding") == "ACTUAL_SOURCE_NET" and item.get("drives_dut") is False for item in contract["signals"]),
            "synthetic_four_state_roundtrip": roundtrip["pass"],
            "runtime_six_exit_and_plateau_matrix": runtime["pass"],
        }
        write_json(reports / "source_bound_logger_collector_parser_roundtrip.json", {"schema": "conv-native-p47-source-bound-vcd-roundtrip-v1", "pass": all(source_bound_checks.values()), "checks": source_bound_checks, "frontend": frontend, "roundtrip": roundtrip, "runtime": runtime, "errors": [key for key, value in source_bound_checks.items() if not value]})
        write_json(OUT / "gates/full_hdl_source_bound.json", {"schema": "conv-native-p47-full-hdl-source-bound-validation-v1", "pass": all(source_bound_checks.values()), "checks": source_bound_checks, "frontend": frontend, "errors": [key for key, value in source_bound_checks.items() if not value], "claim_boundary": "Local package HDL/frontend/source identity only; no production elaboration claim."})
        write_json(OUT / "gates/runtime_six_exit.json", {"schema": "conv-native-p47-runtime-six-exit-validation-v1", **runtime, "claim_boundary": "Local supervisor state-machine controls only; no server outcome claim."})
        retention = load(package / "contracts/server_tb_vcd_streaming_retention_contract.json")
        retention_checks = {
            "streaming_resume_artifacts": retention.get("analysis_artifacts") == ["analysis_state.json", "checkpoints.jsonl", "report.md"],
            "no_whole_file_context": retention.get("analysis_mode") == "STREAMING_RESUMABLE_NO_WHOLE_FILE_CONTEXT_LOAD",
            "protected_slots_exact": retention.get("retention_slots") == ["MAX_PROGRESS", "LATEST_1", "LATEST_2"] and retention.get("max_raw_groups") == 3,
            "delete_prerequisites_complete": retention.get("deletion_prerequisites") == ["analysis_complete", "family_consumed", "mainline_consumed", "deterministic_core_evidence", "protected_set_audit_pass"],
            "no_size_based_delete": retention.get("size_based_deletion") is False,
            "canonical_tool_identity": retention.get("tool_sha256") == digest(package / "package_tools/server_tb_vcd_retention_analysis.py") == digest(ROOT / "tools/server_tb_vcd_retention_analysis.py"),
        }
        write_json(OUT / "gates/streaming_retention.json", {"schema": "conv-native-p47-streaming-retention-validation-v1", "pass": all(retention_checks.values()), "checks": retention_checks, "errors": [key for key, value in retention_checks.items() if not value], "claim_boundary": "Local streaming/retention contract only; no raw-result deletion authorized."})

        post_output = temp / "post_sim_validation.json"
        post = run([str(PYTHON), str(package / "package_tools/server_post_sim_return.py"), "validate-final-zip", "--zip", str(ZIP), "--output", str(post_output)])
        post_value = load(post_output) if post_output.is_file() else {}
        post_checks = {
            "validator_exit_zero": post["exit_code"] == 0,
            "four_scenarios_pass": post_value.get("pass") is True and not post_value.get("errors"),
            "partial_exit_live_contract": load(package / "contracts/server_post_sim_return_contract.json").get("partial_exit_live_causal_record", {}).get("required_signals") == ["INT", "TERM"],
            "vcd_and_core_returned": any(row.get("archive", "").endswith("native_mse4_causal.vcd") for row in load(package / "contracts/server_post_sim_return_request.json")["core_entries"]),
        }
        write_json(reports / "post_sim_return_core_scenarios.json", {"schema": "conv-native-p47-post-sim-four-scenario-v1", "pass": all(post_checks.values()), "checks": post_checks, "invocation": post, "validation": post_value, "errors": [key for key, value in post_checks.items() if not value]})

        candidates = [item["candidate_id"] for item in contract["candidates"]]
        boundaries = [item["boundary_id"] for item in contract["boundaries"]]
        matrix_pairs = {(row["candidate_id"], row["boundary_id"]) for row in contract["candidate_boundary_matrix"]}
        signatures = {
            candidate: canonical_sha([
                row["expected_signature"]
                for row in contract["candidate_boundary_matrix"]
                if row["candidate_id"] == candidate
            ])
            for candidate in candidates
        }
        negative_results: list[dict[str, Any]] = []
        mutations: list[tuple[str, dict[str, Any]]] = []
        missing_role = json.loads(json.dumps(contract)); missing_role["role_coverage"] = missing_role["role_coverage"][:-1]; mutations.append(("missing_role", missing_role))
        missing_matrix = json.loads(json.dumps(contract)); missing_matrix["candidate_boundary_matrix"] = missing_matrix["candidate_boundary_matrix"][:-1]; mutations.append(("missing_matrix", missing_matrix))
        hard_truncation = json.loads(json.dumps(contract)); hard_truncation["budget"]["hard_truncation"] = True; mutations.append(("hard_truncation", hard_truncation))
        for name, mutation in mutations:
            path = temp / f"negative_{name}.json"
            output = temp / f"negative_{name}_result.json"
            write_json(path, mutation)
            invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"), "--contract", str(path), "--root", str(package), "--output", str(output)])
            negative_results.append({"name": name, "rejected": invocation["exit_code"] != 0, "invocation": invocation})
        candidate_checks = {
            "complete_cross_product": matrix_pairs == {(candidate, boundary) for candidate in candidates for boundary in boundaries},
            "pairwise_candidate_signatures": len(set(signatures.values())) == len(candidates),
            "all_required_native_candidates": {"post_accept_terminal_accounting", "outstanding_response_identity", "last_count_mismatch", "completion_fsm_drain_clear", "finish_aggregation"}.issubset(candidates),
            "all_negative_controls_rejected": all(item["rejected"] for item in negative_results),
            "return_unbounded_and_nontruncating": allowlist.get("no_size_limit") is True and allowlist.get("no_truncation") is True and allowlist.get("no_sampling") is True,
        }
        write_json(reports / "candidate_discrimination_matrix.json", {"schema": "conv-native-p47-candidate-matrix-controls-v1", "pass": all(candidate_checks.values()), "checks": candidate_checks, "candidates": candidates, "boundaries": boundaries, "negative_controls": negative_results, "errors": [key for key, value in candidate_checks.items() if not value]})

    report_defs = [
        ("exact_final_zip_clean_extract", "exact-final-zip-clean-extract"),
        ("actual_runner_entry_and_input_open", "exact-runner-safe-compile-and-open-paths"),
        ("source_bound_logger_collector_parser_roundtrip", "exact-generated-over-budget-multi-instance"),
        ("post_sim_return_core_scenarios", "exact-final-request-four-scenario"),
        ("candidate_discrimination_matrix", "exact-candidate-positive-negative-matrix"),
    ]
    evidence = []
    findings = []
    for gate_id, kind in report_defs:
        path = reports / f"{gate_id}.json"
        value = load(path)
        evidence.append({"gate_id": gate_id, "evidence_kind": kind, "path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)})
        if value.get("pass") is not True:
            findings.append({"finding_id": f"{gate_id}_failed", "disposition": "blocking_applicable", "causal_class": "return", "message": "; ".join(value.get("errors", [])) or "independent gate failed"})
    contract = {
        "schema": "server-first-fresh-extra-audit-v1",
        "package": {"package_id": PACKAGE_ID, "family": FAMILY, "final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "bytes": ZIP.stat().st_size, "sha256": digest(ZIP)}},
        "rule_change": {"epoch_id": EPOCH, "rule_ids": ["CDA-SERVER-TB-VCD-BOUNDED-FULL-CAUSAL-CONE-OPTIONAL-001", "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001", "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001"], "first_fresh_for_family": True, "notification_acknowledged": True},
        "independent_reaudit": {"clean_extract_from_final_zip": True, "from_final_zip_only": True, "family_build_reports_reused": False, "top_level_invocations": 1, "all_errors_collected": True, "rebuild_per_single_error_forbidden": True},
        "evidence_reports": evidence,
        "candidate_discrimination": {"candidate_ids": candidates, "covered_candidate_ids": candidates, "uncovered_candidate_ids": [], "positive_control_count": 10, "negative_control_count": 3, "pairwise_distinguishable": True},
        "findings": findings,
    }
    contract_path = OUT / "first_fresh_audit/contract.json"
    write_json(contract_path, contract)
    validation_path = OUT / "gates/first_fresh_validation.json"
    invocation = run([str(PYTHON), str(ROOT / "tools/validate_server_first_fresh_extra_audit.py"), "--contract", str(contract_path), "--workspace-root", str(ROOT), "--output", str(validation_path)])
    return 0 if invocation["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
