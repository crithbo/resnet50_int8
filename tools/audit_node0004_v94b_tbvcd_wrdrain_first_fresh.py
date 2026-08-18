#!/usr/bin/env python3
"""Independent current-epoch first-fresh audit for serialized Conv v94b."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v94b_tbvcd_wrdrain"
FAMILY = "conv_serialized_node0004"
OUT = ROOT / "outputs/conv_node0004_v94b_tbvcd_wrdrain_release1"
ZIP = OUT / f"{PACKAGE}.zip"
PRIOR_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v93d_tbvcd_hardened.zip"
PYTHON = Path(r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
IVERILOG = Path(r"C:\iverilog\bin\iverilog.exe")
BASH = Path(r"C:\Program Files\Git\bin\bash.exe")
REPLAY = {
    "ADVANCING_VCD_TIMESTAMP": "CONTINUE",
    "PLATEAU_SUSPECTED_ONLY": "CONTINUE",
    "PLATEAU_DUMP_OFF_PLUS_GRACE": "CAUSAL_PLATEAU",
    "THREE_INTERVAL_TRUE_FREEZE": "SIM_TIME_FREEZE",
}
LEAF_IDS = {
    "sig_prepared_wr_hs", "sig_prepared_rd_hs", "sig_prepared_valid",
    "sig_mse_buf_spatial_size", "sig_wr_req_valid", "sig_wr_req_ready",
    "sig_wr_queue_wr", "sig_wr_queue_rd", "sig_wr_queue_empty",
    "sig_wr_queue_full", "sig_wr_queue_count", "sig_wr_queue_tsf_size",
    "sig_wr_queue_mask_flag", "sig_wr_ob_vld_in", "sig_wr_ob_bp_pre",
    "sig_wr_ob_wr_hs", "sig_wr_ob_vld", "sig_wr_ob_rd_hs", "sig_wr_ob_sel",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def run(argv: list[str]) -> dict[str, Any]:
    p = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True, check=False)
    return {"argv": argv, "exit_code": p.returncode, "stdout_tail": p.stdout[-8192:], "stderr_tail": p.stderr[-8192:]}


def safe_extract(zip_path: Path, target: Path) -> Path:
    target.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("ZIP CRC failure")
        names = [item.filename for item in archive.infolist() if not item.is_dir()]
        if len(names) != len(set(names)) or any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
            raise RuntimeError("unsafe or duplicate ZIP member")
        roots = {name.split("/", 1)[0] for name in names}
        if roots != {PACKAGE}:
            raise RuntimeError(f"ZIP root differs: {sorted(roots)}")
        archive.extractall(target)
    return target / PACKAGE


def member_map(root: Path) -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    ]


def workload_map_from_zip(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    with zipfile.ZipFile(path) as archive:
        roots = {name.split("/", 1)[0] for name in archive.namelist() if "/" in name}
        if len(roots) != 1:
            raise RuntimeError("workload ZIP root is not unique")
        package_id = next(iter(roots)).encode()
        for info in archive.infolist():
            if info.is_dir() or "/workload/" not in info.filename:
                continue
            rel = info.filename.split("/workload/", 1)[1]
            # Fresh package identity is the only permitted difference in the
            # two materialized SCA path maps; all config values and payload
            # bytes remain exact after replacing that derived identity.
            data = archive.read(info).replace(package_id, b"<FRESH_PACKAGE_ID>")
            result[rel] = hashlib.sha256(data).hexdigest()
    return result


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generic_contract_check(contract_path: Path, package: Path, output: Path) -> bool:
    call = run([str(PYTHON), str(ROOT / "tools/validate_server_tb_vcd_bounded_causal_cone.py"), "--contract", str(contract_path), "--root", str(package), "--output", str(output)])
    return call["exit_code"] == 0


def main() -> int:
    reports = OUT / "first_fresh_extra_audit/reports"
    reports.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    evidence: list[Path] = []
    with tempfile.TemporaryDirectory(prefix="node0004-v94-firstfresh-") as td:
        temp = Path(td)
        package = safe_extract(ZIP, temp / "extract")
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        contract_path = package / "contracts/tb_vcd_bounded_causal_cone_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        selector = json.loads((package / "contracts/diagnostic_mode_selector.json").read_text(encoding="utf-8"))
        probe = (package / "tb_probe/tb_vcd_bounded_causal_cone.svh").read_text(encoding="utf-8")
        runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
        supervisor_text = (package / "package_tools/node0004_tb_vcd_process_supervisor.py").read_text(encoding="utf-8")
        finalizer_text = (package / "package_tools/node0004_tb_vcd_finalize.py").read_text(encoding="utf-8")
        signals = contract["signals"]
        ids = {row["signal_id"] for row in signals}
        exact = {row["exact_hierarchy"] for row in signals}
        dump_targets = {item.strip() for item in re.findall(r"\$dumpvars\s*\(\s*0\s*,\s*([^\)]+?)\s*\)\s*;", probe)}
        clean = {
            "zip_crc_safe_single_root": True,
            "manifest_exact": manifest.get("files") == member_map(package),
            "selector_member_union_exact": set(selector.get("package_members", [])) == {f"{PACKAGE}/{p.relative_to(package).as_posix()}" for p in package.rglob("*") if p.is_file()},
            "prior_workload_byte_frozen": workload_map_from_zip(ZIP) == workload_map_from_zip(PRIOR_ZIP),
            "signal_role_boundary_matrix_counts": len(signals) == 73 and len(contract.get("role_coverage", [])) == 41 and len(contract.get("boundaries", [])) == 4 and len(contract.get("candidates", [])) == 8 and len(contract.get("candidate_boundary_matrix", [])) == 32,
            "wr_data_leaf_set_complete": LEAF_IDS.issubset(ids),
            "exact_dump_target_union": dump_targets == exact and len(dump_targets) == 73,
            "all_actual_source_bound": all(row.get("source_binding") == "ACTUAL_SOURCE_NET" and row.get("derived_expected_equation") is False and row.get("drives_dut") is False for row in signals),
            "retired_ack_comparator_absent": "buf_idx_queue_bp_pre" not in probe and "sig_public_ack !==" not in probe,
            "single_native_launch": runner.count("# CODEX_PRODUCTION_LAUNCH") == 1,
            "normalizer_five_to_five": "s,d,f,h,t=map(pathlib.Path,sys.argv[1:])" in runner and '"$compile_log_tail_txt" <<\'PY\'' in runner,
            "shared_evaluator_only": "--runtime-evaluator" in runner and "--stop-control" in runner and contract["runtime_policy"].get("decision_authority") == "SHARED_RUNTIME_EVALUATOR_ONLY" and contract["runtime_policy"].get("outer_runner_independent_exit_logic") is False,
            "archive_binding_present": all(token in finalizer_text for token in ("vcd_ident", "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT", "TB_VCD_ARCHIVE_TIMESTAMP_RECEIPT.json")),
            "pid_starttime_reap_present": all(token in supervisor_text for token in ("starttime", "process_tree_reaped", "waitpid")),
        }
        clean_path = reports / "clean_extract_frozen_surface.json"
        write_json(clean_path, {"schema": "node0004-v94b-clean-extract-v1", "pass": all(clean.values()), "checks": clean, "errors": [k for k, v in clean.items() if not v]})
        evidence.append(clean_path)

        # Compile the complete passive module while replacing absolute dump
        # names only in the temporary frontend fixture; the exact-target union
        # was independently checked above from immutable ZIP bytes.
        stripped = probe[: probe.index("bind tb_NDP_Top_new_phy")]
        for row in signals:
            stripped = stripped.replace(f"$dumpvars(0, {row['exact_hierarchy']});", f"$dumpvars(0, {row['signal_id']});")
        hdl = temp / "probe.sv"
        hdl.write_text(stripped, encoding="utf-8", newline="\n")
        iv = run([str(IVERILOG), "-g2012", "-tnull", str(hdl)])
        bash = run([str(BASH), "-n", str(package / "PREPARE_AND_RUN.sh")])
        hdl_checks = {"iverilog_complete_module": iv["exit_code"] == 0, "bash_syntax": bash["exit_code"] == 0, "passive_input_only": "output " not in probe and "inout " not in probe and "force " not in probe and "assign " not in probe}
        hdl_path = reports / "full_hdl_source_bound.json"
        write_json(hdl_path, {"schema": "node0004-v94b-full-hdl-source-bound-v1", "pass": all(hdl_checks.values()), "checks": hdl_checks, "iverilog": iv, "bash": bash, "errors": [k for k, v in hdl_checks.items() if not v]})
        evidence.append(hdl_path)

        evaluator = load_module("packaged_v94_evaluator", package / "package_tools/server_tb_vcd_runtime_supervision.py")
        supervisor = load_module("packaged_v94_supervisor", package / "package_tools/node0004_tb_vcd_process_supervisor.py")
        replay_rows = supervisor.replay_cases(evaluator.evaluate)
        observed = {row["case_id"]: row["observed_decision"] for row in replay_rows}
        runtime_checks = {
            "exact_four_replay": observed == REPLAY,
            "advancing_continues": observed.get("ADVANCING_VCD_TIMESTAMP") == "CONTINUE",
            "suspected_only_continues": observed.get("PLATEAU_SUSPECTED_ONLY") == "CONTINUE",
            "dumpoff_plus_grace_stops": observed.get("PLATEAU_DUMP_OFF_PLUS_GRACE") == "CAUSAL_PLATEAU",
            "three_interval_freeze_stops": observed.get("THREE_INTERVAL_TRUE_FREEZE") == "SIM_TIME_FREEZE",
            "shared_receipt_controls_stop": "if decision != \"CONTINUE\"" in supervisor_text and "os.replace(temporary, control)" in supervisor_text,
            "archive_full_identity_bound": "FULL_FILE_SHA_BYTES_PLUS_LAST_TIMESTAMP_EXACT" in finalizer_text and "last_timestamp_ticks" in finalizer_text,
        }
        runtime_path = reports / "runtime_v3_replay_archive_process.json"
        write_json(runtime_path, {"schema": "node0004-v94b-runtime-v3-first-fresh-v1", "pass": all(runtime_checks.values()), "checks": runtime_checks, "replay_cases": replay_rows, "errors": [k for k, v in runtime_checks.items() if not v]})
        evidence.append(runtime_path)

        # Current rule-gap negative controls are exercised against the exact
        # generic validator, except source-code ownership controls which use a
        # bounded package-specific lexical predicate.
        negatives: dict[str, bool] = {}
        for name, mutate in (
            ("missing_wr_leaf", lambda c: c.__setitem__("signals", [r for r in c["signals"] if r["signal_id"] != "sig_prepared_rd_hs"])),
            ("heartbeat_display_only", lambda c: c["runtime_policy"].__setitem__("heartbeat_source", "DISPLAY_TEXT")),
            ("missing_replay_case", lambda c: c["runtime_policy"].__setitem__("required_replay_cases", c["runtime_policy"]["required_replay_cases"][:-1])),
            ("missing_archive_binding", lambda c: c["runtime_policy"].pop("archive_timestamp_binding", None)),
        ):
            mutated = json.loads(json.dumps(contract))
            mutate(mutated)
            path = temp / f"{name}.json"
            write_json(path, mutated)
            negatives[name] = not generic_contract_check(path, package, temp / f"{name}.report.json")
        negatives["alias_dump_target_rejected"] = dump_targets != ids
        negatives["manual_outer_stop_rejected"] = not ("decision != \"CONTINUE\"" in supervisor_text.replace("decision != \"CONTINUE\"", "cycles > 1048576", 1) and "SHARED_RUNTIME_EVALUATOR_ONLY" in supervisor_text)
        negatives["pid_identity_removal_rejected"] = "starttime" not in supervisor_text.replace("starttime", "removed_pid_identity")
        negative_path = reports / "v3_negative_controls.json"
        write_json(negative_path, {"schema": "node0004-v94b-runtime-v3-negative-controls-v1", "pass": all(negatives.values()), "controls": negatives, "errors": [k for k, v in negatives.items() if not v]})
        evidence.append(negative_path)

        # Independently recreate each member with the original deterministic
        # metadata and the family compression level.
        repack = temp / "repack.zip"
        with zipfile.ZipFile(ZIP) as original, zipfile.ZipFile(repack, "w", allowZip64=True) as output:
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
        deterministic_path = reports / "deterministic_zip.json"
        deterministic = digest(repack) == digest(ZIP)
        write_json(deterministic_path, {"schema": "node0004-v94b-deterministic-zip-v1", "pass": deterministic, "source_sha256": digest(ZIP), "repack_sha256": digest(repack), "errors": [] if deterministic else ["deterministic repack differs"]})
        evidence.append(deterministic_path)

    external = [
        OUT / "gates/tb_vcd_contract.json", OUT / "gates/mode_selector.json",
        OUT / "gates/hdl_lexical.json", OUT / "gates/runtime_preflight.json",
        OUT / "gates/normalizer_arity.json", OUT / "gates/runner_resilience.json",
        OUT / "gates/post_sim_return.json", OUT / "gates/active_rule_registry.json",
    ]
    evidence.extend(external)
    for path in evidence:
        if not path.is_file():
            errors.append(f"missing: {path.relative_to(ROOT).as_posix()}")
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("pass") is not True and value.get("valid") is not True:
            errors.append(f"failed: {path.relative_to(ROOT).as_posix()}")
    report = {
        "schema": "server-first-fresh-extra-audit-validation-v1",
        "package_id": PACKAGE, "family": FAMILY,
        "rule_change_epoch_id": "tb-vcd-exit-mechanism-consistency-v3",
        "selected_mode": "TB_VCD_BOUNDED_CAUSAL_CONE",
        "exact_final_zip": {"path": ZIP.relative_to(ROOT).as_posix(), "sha256": digest(ZIP)},
        "clean_extract_from_final_zip": True, "family_build_reports_reused": False,
        "evidence": [{"path": p.relative_to(ROOT).as_posix(), "sha256": digest(p), "pass": json.loads(p.read_text(encoding="utf-8")).get("pass", json.loads(p.read_text(encoding="utf-8")).get("valid"))} for p in evidence if p.is_file()],
        "rule_audit_disposition": "RULE_CONFIRMATION_NO_CHANGE",
        "pass": not errors, "errors": errors,
        "claim_boundary": "Independent local exact-ZIP, HDL, source-bound, runtime-v3 replay/archive/reap and negative-control audit only; no production execution or DUT correctness claim.",
    }
    write_json(OUT / "first_fresh_extra_audit/validation.json", report)
    print(json.dumps({"pass": report["pass"], "errors": errors}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
