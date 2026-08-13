from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = "r5_n71_gap_v48_multislice_pipeline_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 152874
RETURN_SHA = "94c448d3cc14e51afb7daad9b41a04f38de87d31fc960b6216506cfd1589a508"
SOURCE_SIZE = 1952375
SOURCE_SHA = "122257a3b7441e9af2a036f8d8fff1bb7339f014f9c6177f607587525ef359d3"
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
PYTHON = Path(
    r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\python\python.exe"
)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def obj(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root is not object")
    return value


def run(argv: list[str], timeout: int = 30) -> dict[str, Any]:
    result = subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
    )
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def analyze(return_zip: Path, source_zip: Path, replay_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    if return_zip.stat().st_size != RETURN_SIZE:
        errors.append("return size differs")
    if sha_file(return_zip) != RETURN_SHA:
        errors.append("return sha differs")
    if source_zip.stat().st_size != SOURCE_SIZE:
        errors.append("source size differs")
    if sha_file(source_zip) != SOURCE_SHA:
        errors.append("source sha differs")

    with zipfile.ZipFile(source_zip) as source:
        source_crc = source.testzip()
        source_manifest_bytes = source.read(
            f"{IDENTITY}/TEST_PACKAGE_MANIFEST.json"
        )
        source_manifest = obj(source_manifest_bytes)
        runner = source.read(f"{IDENTITY}/PREPARE_AND_RUN.sh").decode(
            "utf-8", errors="replace"
        )
        stage_tool = source.read(
            f"{IDENTITY}/package_tools/gap_node0071_stage_transition_decision.py"
        )
        multislice_tool = source.read(
            f"{IDENTITY}/package_tools/gap_node0071_multislice_pipeline_decision.py"
        )
        canonical_tool = source.read(
            f"{IDENTITY}/package_tools/gap_node0071_canonical_decision.py"
        )

    with zipfile.ZipFile(return_zip) as archive:
        crc = archive.testzip()
        infos = archive.infolist()
        names = [item.filename for item in infos]
        roots = {
            PurePosixPath(name).parts[0] for name in names if name
        }
        duplicates = len(names) != len(set(names))
        unsafe = [
            name for name in names
            if PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ]
        symlinks = [
            item.filename for item in infos
            if stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF)
        ]
        prefix = f"{RETURN_ROOT}/"

        def read(relative: str) -> bytes:
            return archive.read(prefix + relative)

        manifest = obj(read("RETURN_MANIFEST.json"))
        returned_package_manifest = read("evidence/PACKAGE_MANIFEST.json")
        gate = obj(read("evidence/SERVER_RESULT_GATE.json"))
        preflight = obj(read("evidence/installed_preflight.json"))
        observer_guard = obj(read("evidence/observer_precompile.json"))
        root_exact = obj(read("evidence/ndp_root_toplevel_exact_set.json"))
        observer = read("runs/return_observer.log")
        sim_log = read("logs/sim.log")
        progress = read("evidence/progress_samples.log").decode(
            "utf-8", errors="replace"
        )
        signal_text = read("evidence/signal_status.txt").decode()
        binding = read("evidence/observer_binding.txt").decode()
        actual_compile = read("evidence/actual_compile_argv.txt").decode()
        actual_sim = read("evidence/actual_simulator_argv.txt").decode()
        compile_status = int(read("evidence/compile_exit_status.txt").decode())
        simulation_status = int(
            read("evidence/simulation_exit_status.txt").decode()
        )
        runner_status = int(read("evidence/runner_exit_status.txt").decode())

        listed = manifest.get("files", [])
        listed_paths = [row.get("path") for row in listed]
        expected_set = {prefix + "RETURN_MANIFEST.json"} | {
            prefix + path for path in listed_paths if isinstance(path, str)
        }
        receipt_errors: list[str] = []
        for row in listed:
            relative = row.get("path")
            if not isinstance(relative, str):
                receipt_errors.append("malformed path receipt")
                continue
            data = read(relative)
            if len(data) != row.get("size_bytes"):
                receipt_errors.append(f"size differs: {relative}")
            if sha_bytes(data) != row.get("sha256"):
                receipt_errors.append(f"sha differs: {relative}")
        allowlist = {
            row["target_path"]: row
            for row in source_manifest["return_allowlist"]
        }
        outside = sorted(
            path for path in listed_paths if path not in allowlist
        )
        expected_missing = sorted(
            path for path, row in allowlist.items()
            if row["required"] and path not in listed_paths
        )
        missing = sorted(manifest.get("required_missing", []))

    if source_crc is not None:
        errors.append(f"source CRC failure: {source_crc}")
    if crc is not None:
        errors.append(f"return CRC failure: {crc}")
    if roots != {RETURN_ROOT}:
        errors.append("return root differs")
    if duplicates:
        errors.append("duplicate return members")
    if unsafe:
        errors.append("unsafe return paths")
    if symlinks:
        errors.append("return symlinks")
    if set(names) != expected_set:
        errors.append("RETURN_MANIFEST exact-set differs")
    if receipt_errors:
        errors.extend(receipt_errors)
    if outside:
        errors.append("return outside source allowlist")
    if missing != expected_missing:
        errors.append("required_missing differs")
    if returned_package_manifest != source_manifest_bytes:
        errors.append("returned source manifest differs")

    replay_root.mkdir(parents=True, exist_ok=True)
    observer_path = replay_root / "return_observer.log"
    sim_path = replay_root / "sim.log"
    observer_path.write_bytes(observer)
    sim_path.write_bytes(sim_log)
    tools = {
        "stage": (
            "gap_node0071_stage_transition_decision.py", stage_tool,
            ["analyze", "--observer-log", str(observer_path), "--output",
             str(replay_root / "stage_transition_decision.json")],
        ),
        "multislice": (
            "gap_node0071_multislice_pipeline_decision.py", multislice_tool,
            ["analyze", "--observer-log", str(observer_path), "--output",
             str(replay_root / "multislice_pipeline_decision.json")],
        ),
        "canonical": (
            "gap_node0071_canonical_decision.py", canonical_tool,
            ["observe", "--observer-log", str(observer_path), "--sim-log",
             str(sim_path), "--signal", "INT", "--simulation-status", "125",
             "--stall-window-cycles", "1048576", "--heartbeat-cycles",
             "262144", "--manifest", str(replay_root / "manifest.json"),
             "--output", str(replay_root / "canonical_decision.json")],
        ),
    }
    (replay_root / "manifest.json").write_bytes(source_manifest_bytes)
    replay_results: dict[str, Any] = {}
    for key, (name, payload, argv) in tools.items():
        tool = replay_root / name
        tool.write_bytes(payload)
        replay_results[key] = run([str(PYTHON), str(tool), *argv])
    stage = obj((replay_root / "stage_transition_decision.json").read_bytes())
    multislice = obj(
        (replay_root / "multislice_pipeline_decision.json").read_bytes()
    )
    canonical = obj(
        (replay_root / "canonical_decision.json").read_bytes()
    )

    syntax_split = (
        'path.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n'
        '",encoding="utf-8")'
    )
    syntax_error_bound = syntax_split in runner
    last_masks = multislice["last_masks"]
    full_front = all(
        int(last_masks[name], 0) == 0xFFFF
        for name in (
            "cfg_start", "cfg_finish", "mse0", "mse3", "ga_in", "ga_out"
        )
    )
    slice0_only_tail = all(
        int(last_masks[name], 0) == 1
        for name in ("mse4_req", "mse4_wdata", "finish")
    )
    heartbeat_rows = [
        line for line in progress.splitlines()
        if "MULTISLICE_PIPELINE_STATE_V1" in line
        and "HEARTBEAT" in line
    ]
    final_heartbeat_ps = int(
        re.search(r"\t(\d+) \|", heartbeat_rows[-1]).group(1)
    )
    first_same = int(
        re.search(r"\t(\d+) \|", heartbeat_rows[0]).group(1)
    )
    stable_span_ps = final_heartbeat_ps - first_same
    result_terms = gate["result_gate_conjunction"]
    formal_expected = int(gate["readback_count"])
    formal_missing = int(gate["missing_count"])
    formal_present = formal_expected - formal_missing
    dynamic_evidence_valid = (
        not errors
        and compile_status == 0
        and "+RETURN_OBS_MULTISLICE_PIPELINE" in actual_sim
        and "multislice_pipeline_enabled=true" in binding
        and "multislice_pipeline_records_returned=true" in binding
        and replay_results["stage"]["exit_code"] == 0
        and replay_results["multislice"]["exit_code"] == 0
        and full_front and slice0_only_tail
    )

    return {
        "schema": "gap-node0071-v48-return-analysis-v1",
        "status": (
            "PARTIAL_INTERRUPTED_AFTER_QUALIFIED_STALL_AT_"
            "GA_OUTPUT_TO_MSE4_REQUEST_WDATA_FINISH"
        ),
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "return_analysis": {
            "path": str(return_zip),
            "bytes": return_zip.stat().st_size,
            "sha256": sha_file(return_zip),
            "adjacent_sidecar_present": False,
            "transport_policy":
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            "crc_valid": crc is None,
            "single_root": roots == {RETURN_ROOT},
            "path_safe": not unsafe,
            "duplicate_free": not duplicates,
            "symlink_free": not symlinks,
            "manifest_exact_set": set(names) == expected_set,
            "allowlist_only": not outside,
            "per_file_receipts_valid": not receipt_errors,
            "required_missing_count": len(missing),
            "required_missing_exact": missing == expected_missing,
            "formal_return_complete": False,
            "errors": errors,
        },
        "source_binding": {
            "path": str(source_zip),
            "bytes": source_zip.stat().st_size,
            "sha256": sha_file(source_zip),
            "source_crc_valid": source_crc is None,
            "returned_manifest_byte_equal":
                returned_package_manifest == source_manifest_bytes,
            "package": source_manifest.get("package_name"),
            "install": source_manifest.get("install_name"),
            "run": source_manifest.get("run_name"),
            "return": source_manifest.get("return_name"),
        },
        "runtime_binding": {
            "installed_preflight_valid": preflight.get("valid") is True,
            "formal_targets_initially_absent":
                preflight.get("formal_readback_targets_absent") is True,
            "observer_precompile_valid": observer_guard.get("valid") is True,
            "observer_identity_match":
                observer_guard.get("identity_match") is True,
            "compile_macro": "+define+NATIVE_RETURN_OBSERVER_ENABLE"
                in actual_compile,
            "package_local_incdir":
                f"/{IDENTITY}/tb_probe" in actual_compile,
            "actual_compile_argv_returned": True,
            "actual_simulator_argv_returned": True,
            "feature_time0_and_return_bound":
                "multislice_pipeline_enabled=true" in binding
                and "multislice_pipeline_records_returned=true" in binding,
            "actual_compiled_cloud_identity":
                "not proven by this return",
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": runner_status,
            "signal": "INT" if "signal=INT" in signal_text else "UNKNOWN",
            "natural_terminal": False,
            "termination_class":
                "EXTERNAL_INT_AFTER_LONG_QUALIFIED_STALL",
            "stable_heartbeat_span_ps": stable_span_ps,
            "stable_level_counts_as_progress": False,
        },
        "package_local_syntax_error": {
            "classification":
                "FINALIZER_FALLBACK_JSON_HEREDOC_UNTERMINATED_STRING",
            "control_flow":
                "EXIT/HUP/INT/TERM shared finalizer after decision parser calls "
                "and before runtime analyze/collect",
            "exact_source_pattern_present": syntax_error_bound,
            "root": (
                "outer Python f-string consumed the intended backslash in "
                '+"\\n", emitting a literal newline inside the heredoc string'
            ),
            "impact": (
                "fallback decision creation failed; all three required decision "
                "artifacts were absent. Later runtime analysis and collector "
                "still ran under set +e, preserving raw observer/logs and "
                "atomically publishing an incomplete return."
            ),
            "return_destroyed": False,
            "formal_return_completeness_affected": True,
            "functional_simulation_affected": False,
        },
        "local_exact_parser_replay": {
            "source_tools_from_frozen_zip": True,
            "runs": replay_results,
            "stage": stage,
            "multislice": multislice,
            "canonical": canonical,
            "claim_boundary":
                "Read-only parser replay over returned raw observer/logs; "
                "not a replacement for missing formal return artifacts.",
        },
        "qualified_progress": {
            "evaluable": dynamic_evidence_valid,
            "last_masks": last_masks,
            "frontier_all_16": full_front,
            "mse4_and_finish_slice0_only": slice0_only_tail,
            "qualified_record_count":
                multislice.get("qualified_record_count"),
            "state_record_count": multislice.get("state_record_count"),
            "stage_decision": stage.get("decision"),
            "selected_mask": stage.get("selected_mask"),
            "blocked_ready_mask": stage.get("blocked_ready_mask"),
            "compute_active_blocked_mask":
                stage.get("compute_active_blocked_mask"),
            "ready_mask": stage.get("ready_mask"),
            "canonical_parser_status": canonical.get("decision"),
            "canonical_parser_claim":
                "diagnostic summary unavailable; it does not override the "
                "independent bound multislice qualified evidence",
        },
        "formal_d": {
            "expected_count": formal_expected,
            "present_count": formal_present,
            "missing_count": formal_missing,
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "mismatch_zero_evaluable": False,
            "exact_set_complete":
                result_terms.get("formal_readback_exact_set_complete"),
            "all_result_terms_true": result_terms.get("all_terms_true"),
            "server_result_status": gate.get("status"),
        },
        "last_proven_good": (
            "All 16 slices have qualified cfg_start/cfg_finish, MSE0/MSE3 "
            "acceptance and GA input/output acceptance; slice0 additionally "
            "has MSE4 request/write-data and finish."
        ),
        "first_divergence": (
            "SLICES_1_TO_15_GA_OUTPUT_ACCEPTED_WITHOUT_MSE4_REQUEST_"
            "WRITE_DATA_OR_FINISH"
        ),
        "hang_root_cause": (
            "LONG_RUNNING_HANG_AT_NONZERO_SLICE_GA_OUTPUT_TO_MSE4_"
            "REQUEST_WDATA_FINISH_PENDING_LEAF"
        ),
        "root_cause_scope": {
            "unique": False,
            "remaining_candidates": [
                "GA outbuffer write-to-read availability",
                "MSE4 tag/index request generation",
                "MSE4 request ready/queue pairing",
                "MSE4 buffer/prepared-data transport",
                "MSE4 output-buffer write/read and finish release",
            ],
            "functional_rtl_implicated": False,
            "config_implicated": False,
            "package_runner_defect_also_present":
                "finalizer fallback JSON quoting",
        },
        "e3_e4_e5": {
            "E3": False,
            "E4": False,
            "E5": False,
            "reason":
                "No natural terminal and 0/48 formal D; mismatch=0 is "
                "unevaluable. Production compiled commit is not returned.",
        },
        "blocker_delta": {
            "closed": [
                "slices1-15 config delivery",
                "slices1-15 MSE0/MSE3 acceptance",
                "slices1-15 GA input/output acceptance",
            ],
            "opened": [
                "nonzero-slice GA output to MSE4 request/write-data/finish leaf",
                "v48 finalizer fallback SyntaxError",
            ],
            "unchanged": [
                "natural terminal",
                "48 formal D",
                "actual compiled production commit identity",
            ],
        },
        "successor_proposal": {
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "fresh_identity": "r5_n71_gap_v49_mse4_maskwide_diag",
            "fix_package_local_finalizer": True,
            "information_gain_scope": (
                "all slices, owner-clock qualified GA outbuffer wr/rd through "
                "MSE4 tag/request/queue/buffer/prepared/output-buffer/finish"
            ),
            "freeze": (
                "numeric/sum/tail/workload/config/golden/timeout/backpressure/"
                "functional RTL"
            ),
        },
        "rule_confirmation": [
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
            "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
        ],
        "rule_delta_proposal": (
            "Require local syntax execution of every package-local heredoc "
            "embedded by an outer generator, including signal-finalizer fallback "
            "branches; static runner token checks did not catch backslash loss."
        ),
        "package_release": "PENDING_SUCCESSOR_BUILD",
        "numeric_or_workload_repeated": False,
        "functional_rtl_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--replay-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(
        args.return_zip.resolve(), args.source_zip.resolve(),
        args.replay_root.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps({
        "output": str(args.output),
        "sha256": sha_file(args.output),
        "errors": report["return_analysis"]["errors"],
        "status": report["status"],
    }, ensure_ascii=False))
    return 0 if not report["return_analysis"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
