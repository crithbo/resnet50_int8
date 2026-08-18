#!/usr/bin/env python3
"""Independent clean-extract and first-fresh audit for serialized Conv v92b."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v92b_tbvcdcone"
FAMILY = "conv_serialized_node0004"
EPOCH = "tb-vcd-bounded-causal-cone-optional-v1-0820e1733437"
OUT = ROOT / "outputs/conv_node0004_v92b_tbvcdcone_release1"
ZIP = OUT / f"{PACKAGE_ID}.zip"
V91 = ROOT / "outputs/conv_node0004_v91b_normfix_release1/build/r5_n4_hw_v91b_normfix"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str], cwd: Path | None = None) -> dict[str, object]:
    result = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": result.returncode, "stdout_tail": result.stdout[-8192:], "stderr_tail": result.stderr[-8192:]}


def safe_extract(path: Path, destination: Path) -> tuple[Path, list[zipfile.ZipInfo]]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise RuntimeError("duplicate ZIP members")
        roots = set()
        for name in names:
            item = PurePosixPath(name)
            if item.is_absolute() or ".." in item.parts or "\\" in name:
                raise RuntimeError(f"unsafe ZIP member: {name}")
            if item.parts:
                roots.add(item.parts[0])
        if roots != {PACKAGE_ID}:
            raise RuntimeError(f"single exact root required: {sorted(roots)}")
        archive.extractall(destination)
    return destination / PACKAGE_ID, infos


def member_map(package: Path) -> dict[str, tuple[int, str]]:
    return {
        path.relative_to(package).as_posix(): (path.stat().st_size, digest(path))
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }


def exact_repack(source: Path, target: Path) -> str:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w", allowZip64=True) as output:
        for old in original.infolist():
            info = zipfile.ZipInfo(old.filename, old.date_time)
            info.compress_type = old.compress_type
            info.comment = old.comment
            info.extra = old.extra
            info.internal_attr = old.internal_attr
            info.external_attr = old.external_attr
            info.create_system = old.create_system
            info.flag_bits = old.flag_bits
            output.writestr(info, original.read(old), compress_type=old.compress_type, compresslevel=6)
    return digest(target)


def workload_map(root: Path) -> dict[str, str]:
    path = root / "workload/runtime"
    rows: dict[str, str] = {}
    for item in sorted(x for x in path.rglob("*") if x.is_file()):
        data = item.read_bytes().replace(PACKAGE_ID.encode(), b"r5_n4_hw_v91b_normfix")
        rows[item.relative_to(path).as_posix()] = hashlib.sha256(data).hexdigest()
    return rows


def synthetic_vcd_roundtrip(package: Path, work: Path) -> dict[str, object]:
    contract = json.loads((package / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
    evidence = work / "attempt/evidence"
    c0 = work / "attempt/c0"
    evidence.mkdir(parents=True)
    c0.mkdir(parents=True)
    source = evidence / "compiled_source/source_identity.json"
    argv = evidence / "ACTUAL_COMPILE_SIM_ARGV.json"
    process = evidence / "PROCESS_TREE_RECEIPT.json"
    sim_log = c0 / "sim.log"
    vcd = c0 / "causal_cone.vcd"
    write_json(source, {"schema": "node0004-tb-vcd-actual-source-identity-v1", "status": "COMPLETE"})
    write_json(argv, {"schema": "server-tb-vcd-actual-argv-v1", "compile_argv": contract["execution"]["compile_argv"], "sim_argv": contract["execution"]["sim_argv"]})
    state = "1" * 64
    samples = [
        {"seq": 0, "wall_seconds": 0, "sim_time_ticks": 1, "owner_clock_cycles": 1, "sim_cycles": 1, "vcd_bytes": 1024, "causal_progress_events": 1, "causal_state_digest": state, "global_progress_witness": {"finish": 0}, "qualified_progress_counters": {"accept": 1}, "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True, "quota_ok": True},
        {"seq": 1, "wall_seconds": 1, "sim_time_ticks": 1000, "owner_clock_cycles": 100, "sim_cycles": 100, "vcd_bytes": 2048, "causal_progress_events": 2, "causal_state_digest": "2" * 64, "global_progress_witness": {"finish": 1}, "qualified_progress_counters": {"accept": 2}, "unresolved_xz_absent": True, "write_ok": True, "disk_space_ok": True, "quota_ok": True, "natural_terminal": True},
    ]
    write_json(process, {"schema": "node0004-tb-vcd-process-supervision-v1", "root_exit": 0, "stop_reason": "NATURAL_TERMINAL", "process_tree_reaped": True, "vcd_stable": True, "samples": samples, "process_tree": {"term_sent": False, "wait_completed": True, "kill_sent_if_needed": False, "all_reaped": True}})
    sim_log.write_text("CODEX_TB_VCD_DUMPOFF_FLUSH_V1 sim_time=1000 owner_cycles=100\nCODEX_TB_VCD_NATURAL_TERMINAL_WITNESS_V1 sim_time=1000 owner_cycles=100\nCODEX_TB_VCD_FINAL_FLUSH_V1 sim_time=1000 owner_cycles=100\n", encoding="utf-8")
    rows = ["$date\n  synthetic\n$end\n", "$version\n  codex synthetic\n$end\n", "$timescale 1ps $end\n", "$scope module codex_node0004_tb_vcd_cone_inst $end\n"]
    codes = []
    for index, item in enumerate(contract["signals"]):
        code = f"s{index}"
        codes.append(code)
        rows.append(f"$var wire {item['width_bits']} {code} {item['signal_id']} $end\n")
    rows.extend(["$upscope $end\n", "$enddefinitions $end\n", "#0\n"])
    for item, code in zip(contract["signals"], codes):
        width = int(item["width_bits"])
        rows.append((f"0{code}\n" if width == 1 else f"b{'0'*width} {code}\n"))
    rows.append("#1000\n")
    for item, code in zip(contract["signals"], codes):
        width = int(item["width_bits"])
        rows.append((f"1{code}\n" if width == 1 else f"b{'1'*width} {code}\n"))
    vcd.write_text("".join(rows), encoding="utf-8", newline="\n")
    invocation = run([
        str(PYTHON), str(package / "package_tools/node0004_tb_vcd_finalize.py"),
        "--contract", str(package / "contracts/tb_vcd_bounded_causal_cone_contract.json"),
        "--selector", str(package / "contracts/diagnostic_mode_selector.json"),
        "--tb-source", str(package / "tb_probe/tb_vcd_bounded_causal_cone.svh"),
        "--vcd", str(vcd), "--sim-log", str(sim_log), "--process-receipt", str(process),
        "--source-identity", str(source), "--actual-argv", str(argv), "--output-dir", str(evidence / "vcd"),
        "--package-id", PACKAGE_ID, "--execution-id", "r_synthetic", "--attempt-id", "a_synthetic",
        "--compile-exit", "0", "--run-exit", "0",
    ])
    receipt_path = evidence / "vcd/VCD_RUNTIME_RECEIPT.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
    checks = {
        "finalizer_exit_zero": invocation["exit_code"] == 0,
        "natural_complete": receipt.get("completeness") == "COMPLETE" and receipt.get("natural_terminal") is True,
        "catalog_complete": receipt.get("vcd_identity", {}).get("catalog_complete") is True,
        "xz_transport_preserved": receipt.get("vcd_identity", {}).get("xz_preserved") is True,
        "process_tree_reaped": receipt.get("process_tree", {}).get("all_reaped") is True,
    }
    return {"schema": "node0004-v92b-synthetic-vcd-roundtrip-v1", "pass": all(checks.values()), "checks": checks, "invocation": invocation, "receipt": receipt}


def runtime_matrix() -> dict[str, object]:
    spec = importlib.util.spec_from_file_location("tb_vcd_runtime", ROOT / "tools/server_tb_vcd_runtime_supervision.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    identity = {"header_valid": True, "timescale": "1ps", "catalog_complete": True, "transitions_complete": True, "xz_preserved": True, "return_allowlist_member": True}
    process = {"term_sent": True, "wait_completed": True, "kill_sent_if_needed": False, "all_reaped": True}
    flush = {"dumpoff": True, "dumpflush": True, "closed": True}
    base = {"package_id": PACKAGE_ID, "execution_id": "r_matrix", "attempt_id": "a_matrix", "started": True, "actual_argv_sha256": "1" * 64, "catalog_sha256": "2" * 64, "candidate_matrix_sha256": "3" * 64, "tb_source_sha256": "4" * 64, "elaboration_sha256": "5" * 64, "candidate_catalog_complete": True, "unresolved_xz": False, "vcd_identity": identity, "flush": flush, "process_tree": process}
    def sample(seq: int, wall: int, ticks: int, cycles: int, *, signal: str | None = None, natural: bool = False, global_value: int = 0) -> dict[str, object]:
        row = {"seq": seq, "wall_seconds": wall, "sim_time_ticks": ticks, "owner_clock_cycles": cycles, "sim_cycles": cycles, "vcd_bytes": 4096 + seq, "causal_progress_events": 0, "causal_state_digest": "a" * 64, "global_progress_witness": {"value": global_value}, "qualified_progress_counters": {"accept": 0}, "write_ok": True, "disk_space_ok": True, "quota_ok": True}
        if signal:
            row["signal"] = signal
        if natural:
            row["natural_terminal"] = True
        return row
    cases: dict[str, list[dict[str, object]]] = {
        "natural": [sample(0, 0, 1, 1), sample(1, 1, 100, 100, natural=True)],
        "wall": [sample(0, 0, 1, 1), sample(1, 3600, 100, 100)],
        "nonzero": [sample(0, 0, 1, 1), {**sample(1, 1, 100, 100), "exit_code": 9}],
        "hup": [sample(0, 0, 1, 1), sample(1, 1, 100, 100, signal="HUP")],
        "int": [sample(0, 0, 1, 1), sample(1, 1, 100, 100, signal="INT")],
        "term": [sample(0, 0, 1, 1), sample(1, 1, 100, 100, signal="TERM")],
        "plateau": [
            sample(0, 0, 1, 1),
            sample(1, 1, 4194305, 4194305),
            sample(2, 2, 4456449, 4456449),
        ],
        "global_advances": [sample(0, 0, 1, 1), {**sample(1, 1, 5000000, 4456449, global_value=1), "exit_code": 9}],
        "freeze": [sample(0, 0, 1, 1), sample(1, 30, 1, 1), sample(2, 60, 1, 1), sample(3, 90, 1, 1)],
    }
    receipts = {}
    for name, samples in cases.items():
        request = {**base, "samples": samples}
        receipts[name] = module.evaluate(request)
    checks = {
        "natural_only_complete": receipts["natural"]["completeness"] == "COMPLETE" and all(receipts[name]["completeness"] == "PARTIAL" for name in cases if name != "natural"),
        "six_exit_classified": [receipts[name]["stop_reason"] for name in ("natural", "wall", "nonzero", "hup", "int", "term")] == ["NATURAL_TERMINAL", "WALL_CEILING", "NONZERO_EXIT", "HUP", "INT", "TERM"],
        "strict_plateau": receipts["plateau"]["stop_reason"] == "CAUSAL_PLATEAU" and receipts["plateau"]["plateau_qualification"]["eligible"] is True,
        "global_progress_forbids_plateau": receipts["global_advances"]["stop_reason"] != "CAUSAL_PLATEAU",
        "three_interval_freeze": receipts["freeze"]["stop_reason"] == "SIM_TIME_FREEZE",
        "no_nonnatural_terminal_claim": all(receipts[name]["natural_terminal"] is False for name in cases if name != "natural"),
    }
    return {"schema": "node0004-v92b-runtime-six-exit-matrix-v1", "pass": all(checks.values()), "checks": checks, "receipts": receipts}


def main() -> int:
    reports = OUT / "first_fresh_extra_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v92b-firstfresh-") as temporary:
        temp = Path(temporary)
        package, infos = safe_extract(ZIP, temp / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        selector = json.loads((package / "contracts/diagnostic_mode_selector.json").read_text(encoding="utf-8"))
        contract = json.loads((package / "contracts/tb_vcd_bounded_causal_cone_contract.json").read_text(encoding="utf-8"))
        declared = {row["path"]: (row["bytes"], row["sha256"]) for row in manifest["files"]}
        actual = member_map(package)
        names = {info.filename for info in infos if not info.is_dir()}
        package_members = set(selector["package_members"])
        # The original 38-net baseline is deliberately frozen to v88/v91's
        # production-captured source identities.  Only the four newly added
        # global witnesses are checked against current local source bytes;
        # production refresh remains a runtime evidence boundary.
        new_source_matches = all(
            digest(ROOT / "NDP_copy01" / row["source_path"]) == row["source_sha256"]
            for row in contract["signals"]
            if row["signal_id"].startswith("sig_global_")
        )
        old_contract = json.loads((V91 / "contracts/observer_only_wide_causal_contract.json").read_text(encoding="utf-8"))
        frozen38 = {(row["signal_id"], row["exact_hierarchy"], row["width_bits"], row["source_path"], row["source_sha256"]) for row in old_contract["signals"]}
        fresh38 = {(row["signal_id"], row["exact_hierarchy"], row["width_bits"], row["source_path"], row["source_sha256"]) for row in contract["signals"] if not row["signal_id"].startswith("sig_global_")}
        probe = (package / "tb_probe/tb_vcd_bounded_causal_cone.svh").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        allowlist = json.loads((package / "RETURN_ALLOWLIST.json").read_text(encoding="utf-8"))
        clean_checks = {
            "manifest_member_map_exact": declared == actual,
            "selector_package_members_exact": package_members == names,
            "canonical_post_helper_exact": (package / "package_tools/server_post_sim_return.py").read_bytes() == (ROOT / "tools/server_post_sim_return.py").read_bytes(),
            "workload_byte_frozen": workload_map(package) == workload_map(V91),
            "frozen_actual_source_38_exact": fresh38 == frozen38,
            "new_global_source_bytes_bound_to_current_local_baseline": new_source_matches,
            "mode_exact": selector.get("selected_mode") == "TB_VCD_BOUNDED_CAUSAL_CONE",
            "no_runtime_wave_member_in_package": not any(name.lower().endswith((".vcd", ".vpd", ".fsdb", ".fst")) for name in names),
            "retired_derived_ack_comparator_absent": "buf_idx_queue_bp_pre" not in probe,
            "standard_tasks_present": all(token in probe for token in ("$dumpfile", "$dumpvars", "$dumpon", "$dumpoff", "$dumpflush")),
            "passive_input_only_probe": "output " not in probe and "inout " not in probe and "force " not in probe and "assign " not in probe,
            "single_production_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "make_dump_argv_zero": all(token in runner for token in ("DUMP_VCD=0", "DUMP_FSDB=0", "TB_DUMP_FSDB=0")) and all(token not in runner for token in ("DUMP_VCD=1", "DUMP_FSDB=1", "TB_DUMP_FSDB=1")),
            "normalizer_five_to_five": '"$compile_log_tail_txt" <<\'PY\'' in runner and "s,d,f,h,t=map(pathlib.Path,sys.argv[1:])" in runner,
            "runtime_safeguards_bound": all(token in runner for token in ("node0004_tb_vcd_process_supervisor.py", "causal_cone.vcd", "+CODEX_TB_VCD_BOUNDED_CAUSAL_CONE")),
            "unbounded_return_allowlist": allowlist.get("no_size_limit") is True and allowlist.get("hard_truncation") is False and allowlist.get("sampling") is False and allowlist.get("size_based_deletion") is False,
            "streaming_contract_present": (package / "contracts/streaming_retention_contract.json").is_file(),
        }
        write_json(reports / "clean_extract_frozen_surface.json", {"schema": "node0004-v92b-clean-extract-frozen-surface-v1", "pass": all(clean_checks.values()), "checks": clean_checks, "errors": [key for key, value in clean_checks.items() if not value]})

        stripped = probe[: probe.index("bind tb_NDP_Top_new_phy")]
        synthetic_hdl = temp / "tb_vcd_probe_compile.sv"
        synthetic_hdl.write_text(stripped, encoding="utf-8")
        hdl_compile = run([str(IVERILOG), "-g2012", "-tnull", str(synthetic_hdl)])
        bash_syntax = run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")])
        hdl_checks = {
            "iverilog_module_frontend": hdl_compile["exit_code"] == 0,
            "runner_bash_syntax": bash_syntax["exit_code"] == 0,
            "signal_count_42": len(contract["signals"]) == 42,
            "role_count_41": len(contract["role_coverage"]) == 41,
            "four_boundaries": {row["layer"] for row in contract["boundaries"]} == {"FIRST_DIVERGENCE_UPSTREAM_ONE", "FIRST_DIVERGENCE_CURRENT", "FIRST_DIVERGENCE_DOWNSTREAM_ONE", "STATE_HOLD_CLEAR"},
            "full_candidate_matrix": len(contract["candidate_boundary_matrix"]) == len(contract["candidates"]) * len(contract["boundaries"]),
            "actual_ack_and_driver_inputs": all(item in {row["signal_id"] for row in contract["signals"]} for item in ("sig_public_ack", "sig_valid_mask", "sig_row_full", "sig_col_full")),
            "global_terminal_witness": all(item in {row["signal_id"] for row in contract["signals"]} for item in ("sig_global_fetch_finish", "sig_global_slice_finish", "sig_global_valid", "sig_global_ready")),
        }
        write_json(reports / "full_hdl_source_bound.json", {"schema": "node0004-v92b-full-hdl-source-bound-v1", "pass": all(hdl_checks.values()), "checks": hdl_checks, "iverilog": hdl_compile, "bash": bash_syntax, "errors": [key for key, value in hdl_checks.items() if not value]})

        roundtrip = synthetic_vcd_roundtrip(package, temp / "roundtrip")
        write_json(reports / "synthetic_vcd_roundtrip.json", roundtrip)
        matrix = runtime_matrix()
        write_json(reports / "runtime_six_exit_matrix.json", matrix)

        repacked = temp / "repacked.zip"
        repack_sha = exact_repack(ZIP, repacked)
        deterministic = {"schema": "node0004-v92b-deterministic-zip-v1", "pass": repack_sha == digest(ZIP), "source_sha256": digest(ZIP), "repack_sha256": repack_sha, "errors": [] if repack_sha == digest(ZIP) else ["deterministic repack differs"]}
        write_json(reports / "deterministic_zip.json", deterministic)

    gate_paths = [
        OUT / "gates/tb_vcd_contract.json", OUT / "gates/mode_selector.json", OUT / "gates/hdl_lexical.json",
        OUT / "gates/runtime_preflight.json", OUT / "gates/normalizer_arity.json", OUT / "gates/runner_resilience.json",
        OUT / "gates/post_sim_return.json", reports / "clean_extract_frozen_surface.json", reports / "full_hdl_source_bound.json",
        reports / "synthetic_vcd_roundtrip.json", reports / "runtime_six_exit_matrix.json", reports / "deterministic_zip.json",
    ]
    evidence = []
    for path in gate_paths:
        if not path.is_file():
            errors.append(f"gate receipt absent: {path.relative_to(ROOT).as_posix()}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True:
            errors.append(f"gate failed: {path.relative_to(ROOT).as_posix()}")
        evidence.append({"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path), "pass": value.get("pass")})
    report = {
        "schema": "server-first-fresh-extra-audit-validation-v1", "package_id": PACKAGE_ID, "family": FAMILY,
        "rule_change_epoch_id": EPOCH, "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE", "pass": not errors,
        "exact_final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "sha256": digest(ZIP)},
        "clean_extract_from_final_zip": True, "family_build_reports_reused": False, "evidence": evidence, "errors": errors,
        "claim_boundary": "Independent local exact-ZIP/source/runtime/return audit only; no production compile, simulation, root cause, natural terminal, formal-D or E3/E4/E5 claim.",
    }
    write_json(OUT / "first_fresh_extra_audit/validation.json", report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
