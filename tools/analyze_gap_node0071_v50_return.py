from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
RETURN_PATH = Path(
    r"C:\Users\15383\Downloads"
    r"\r5_n71_gap_v50_ga_ob_conjunction_diag_r1786110415338387175_3719505_return.zip"
)
RETURN_SHA = "af493115127b0040d8bec83815d0e00d2fc90a7a9c559b11758ddb42982adfc2"
SOURCE_PATH = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n71_gap_v50_ga_ob_conjunction_diag.zip"
)
SOURCE_SHA = "96c23c3762b9fca323ff3d76250f8ca9482c74d536a93b843321c8be3f37252d"
INSTALL = "r5_n71_gap_v50_ga_ob_conjunction_diag"
RETURN_ROOT = f"{INSTALL}_return"
EXECUTION_RE = re.compile(
    rf"^{re.escape(INSTALL)}_r(?P<epoch_ns>[0-9]+)_(?P<pid>[0-9]+)_return\.zip$"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def safe_archive(archive: zipfile.ZipFile, root: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    names: set[str] = set()
    roots: set[str] = set()
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
            errors.append(f"unsafe path:{info.filename}")
        if info.filename in names:
            errors.append(f"duplicate:{info.filename}")
        names.add(info.filename)
        if pure.parts:
            roots.add(pure.parts[0])
        if stat.S_ISLNK(info.external_attr >> 16):
            errors.append(f"symlink:{info.filename}")
    if roots != {root}:
        errors.append(f"root:{sorted(roots)}")
    bad = archive.testzip()
    if bad:
        errors.append(f"crc:{bad}")
    return not errors, errors


def run_parser(argv: list[str], output: Path) -> dict[str, object]:
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "output": json.loads(output.read_text(encoding="utf-8"))
        if output.is_file() else None,
    }


def analyze(output: Path) -> dict[str, object]:
    errors: list[str] = []
    if not RETURN_PATH.is_file() or sha(RETURN_PATH) != RETURN_SHA:
        raise RuntimeError("return identity mismatch")
    if not SOURCE_PATH.is_file() or sha(SOURCE_PATH) != SOURCE_SHA:
        raise RuntimeError("source identity mismatch")
    execution = EXECUTION_RE.match(RETURN_PATH.name)
    if execution is None:
        errors.append("outer unique return basename invalid")

    with tempfile.TemporaryDirectory(prefix="gap-v50-return-") as tmp_name:
        tmp = Path(tmp_name)
        with zipfile.ZipFile(RETURN_PATH) as archive:
            return_safe, return_errors = safe_archive(archive, RETURN_ROOT)
            errors.extend(return_errors)
            archive.extractall(tmp / "return")
            names = {
                PurePosixPath(i.filename).relative_to(RETURN_ROOT).as_posix()
                for i in archive.infolist() if not i.is_dir()
            }
        returned = tmp / "return" / RETURN_ROOT
        manifest = json.loads(
            (returned / "RETURN_MANIFEST.json").read_text(encoding="utf-8")
        )
        listed = {row["path"] for row in manifest["files"]}
        exact_set = names == listed | {"RETURN_MANIFEST.json"}
        if not exact_set:
            errors.append("return manifest exact-set mismatch")
        per_file = all(
            (returned / row["path"]).is_file()
            and (returned / row["path"]).stat().st_size == row["size_bytes"]
            and sha(returned / row["path"]) == row["sha256"]
            for row in manifest["files"]
        )
        if not per_file:
            errors.append("return per-file receipt mismatch")

        with zipfile.ZipFile(SOURCE_PATH) as archive:
            source_safe, source_errors = safe_archive(archive, INSTALL)
            errors.extend(source_errors)
            archive.extractall(tmp / "source")
        source = tmp / "source" / INSTALL
        source_manifest = source / "TEST_PACKAGE_MANIFEST.json"
        returned_manifest = returned / "evidence/PACKAGE_MANIFEST.json"
        source_bound = source_manifest.read_bytes() == returned_manifest.read_bytes()
        if not source_bound:
            errors.append("returned package manifest mismatch")
        package_manifest = json.loads(source_manifest.read_text(encoding="utf-8"))

        sca_d = json.loads(
            (returned / "config/sca_cfg_D.json").read_text(encoding="utf-8")
        )
        sca_paths = json.dumps(sca_d, sort_keys=True)
        attempts = sorted(set(re.findall(r"/(a[0-9]+)/readback/", sca_paths)))
        actual_compile = (
            returned / "evidence/actual_compile_argv.txt"
        ).read_text(encoding="utf-8")
        actual_sim = (
            returned / "evidence/actual_simulator_argv.txt"
        ).read_text(encoding="utf-8")
        pid = execution.group("pid") if execution else None
        execution_bound = (
            len(attempts) == 1
            and pid is not None
            and attempts[0] == f"a{pid}"
            and attempts[0] in actual_compile
            and attempts[0] in actual_sim
            and package_manifest["repeat_execution_contract"]["return_name_policy"]
            == "UNIQUE_PER_EXECUTION_PRESERVE_PRIOR_RETURNS"
        )
        if not execution_bound:
            errors.append("per-execution identity binding failed")

        observer = returned / "runs/return_observer.log"
        sim_log = returned / "logs/sim.log"
        tools = source / "package_tools"
        replay_dir = output / "formal_replay"
        replay_dir.mkdir(parents=True, exist_ok=True)
        parser_names = {
            "stage": "gap_node0071_stage_transition_decision.py",
            "multislice": "gap_node0071_multislice_pipeline_decision.py",
            "mse4": "gap_node0071_mse4_maskwide_decision.py",
            "ga_ob": "gap_node0071_ga_ob_conjunction_decision.py",
        }
        replays: dict[str, object] = {}
        for name, tool in parser_names.items():
            target = replay_dir / f"{name}.json"
            replays[name] = run_parser(
                [sys.executable, str(tools / tool), "analyze",
                 "--observer-log", str(observer), "--output", str(target)],
                target,
            )
        canonical_target = replay_dir / "canonical.json"
        replays["canonical"] = run_parser(
            [
                sys.executable,
                str(tools / "gap_node0071_canonical_decision.py"),
                "observe",
                "--observer-log", str(observer),
                "--sim-log", str(sim_log),
                "--signal", "INT",
                "--simulation-status", "125",
                "--stall-window-cycles", "1048576",
                "--heartbeat-cycles", "262144",
                "--manifest", str(source_manifest),
                "--output", str(canonical_target),
            ],
            canonical_target,
        )
        replay_ok = all(row["exit_code"] == 0 for row in replays.values())

        def integer(path: str) -> int:
            return int((returned / path).read_text(encoding="utf-8").strip())

        gate = json.loads(
            (returned / "evidence/SERVER_RESULT_GATE.json").read_text(encoding="utf-8")
        )
        installed = json.loads(
            (returned / "evidence/installed_preflight.json").read_text(encoding="utf-8")
        )
        precompile = json.loads(
            (returned / "evidence/observer_precompile.json").read_text(encoding="utf-8")
        )
        root_gate = json.loads(
            (returned / "evidence/ndp_root_toplevel_exact_set.json").read_text(
                encoding="utf-8"
            )
        )
        parser_status = (
            returned / "evidence/decision_parser_status.txt"
        ).read_text(encoding="utf-8")
        parser_stderr = (
            returned / "evidence/decision_parser_stderr.log"
        ).read_text(encoding="utf-8")
        stage = replays["stage"]["output"]
        multi = replays["multislice"]["output"]
        mse4 = replays["mse4"]["output"]
        ga_ob = replays["ga_ob"]["output"]
        observer_text = observer.read_text(encoding="utf-8", errors="replace")
        ga_ob_records = [
            (int(match.group(1)), int(match.group(2)))
            for match in re.finditer(
                r"^([0-9]+)\s+\|\s+GA_OB_CONJ_STATE_V1\s+\|.*?"
                r"\bn=([0-9]+)\b",
                observer_text,
                re.MULTILINE,
            )
        ]
        later_slice_ga_output = next(
            (
                (int(match.group(1)), int(match.group(2), 16))
                for match in re.finditer(
                    r"^([0-9]+)\s+\|\s+MULTISLICE_PIPELINE_STATE_V1"
                    r"\s+\|.*?\bga_out=0x([0-9a-fA-F]+)",
                    observer_text,
                    re.MULTILINE,
                )
                if int(match.group(2), 16) & 0xFFFE
            ),
            None,
        )
        ga_ob_budget_exhausted_before_target_slices = (
            bool(ga_ob_records)
            and ga_ob_records[-1][1] == 256
            and later_slice_ga_output is not None
            and ga_ob_records[-1][0] < later_slice_ga_output[0]
        )

        report = {
            "schema": "gap-node0071-v50-repeatable-return-analysis-v1",
            "status":
                "PARTIAL_INTERRUPTED_DIAGNOSTIC_TRACE_SATURATED_BEFORE_TARGET_SLICES",
            "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "return_analysis": {
                "path": str(RETURN_PATH),
                "bytes": RETURN_PATH.stat().st_size,
                "sha256": sha(RETURN_PATH),
                "adjacent_sidecar_present":
                    Path(str(RETURN_PATH) + ".sha256").is_file(),
                "crc_root_path_duplicate_symlink_valid": return_safe,
                "manifest_exact_set": exact_set,
                "allowlist_only": manifest.get("allowlist_only") is True,
                "per_file_receipts_valid": per_file,
                "errors": errors,
            },
            "source_binding": {
                "path": str(SOURCE_PATH),
                "bytes": SOURCE_PATH.stat().st_size,
                "sha256": sha(SOURCE_PATH),
                "source_crc_root_valid": source_safe,
                "returned_manifest_byte_equal": source_bound,
                "runtime_only_reissue": True,
            },
            "repeat_execution_identity": {
                "outer_basename": RETURN_PATH.name,
                "epoch_ns": execution.group("epoch_ns") if execution else None,
                "pid": pid,
                "attempts_in_sca_d": attempts,
                "attempt_bound_in_compile_argv": attempts[0] in actual_compile
                if len(attempts) == 1 else False,
                "attempt_bound_in_simulator_argv": attempts[0] in actual_sim
                if len(attempts) == 1 else False,
                "source_policy":
                    package_manifest["repeat_execution_contract"],
                "valid": execution_bound,
                "internal_return_root_is_package_stable": True,
                "legacy_nominal_fixed_result_fields_present": True,
            },
            "runtime_binding": {
                "installed_preflight_valid": installed["valid"],
                "formal_targets_initially_absent":
                    installed["formal_readback_targets_absent"],
                "observer_precompile_valid": precompile["valid"],
                "observer_identity_match": precompile["identity_match"],
                "ndp_root_toplevel_unchanged":
                    root_gate["ndp_root_toplevel_unchanged"],
                "observer_features_returned":
                    (returned / "evidence/observer_binding.txt").read_text(
                        encoding="utf-8"
                    ).count("=true") == 7,
                "actual_compile_and_simulator_argv_returned": True,
                "actual_compiled_cloud_identity": "not proven by this return",
            },
            "execution": {
                "compile_exit_status": integer("evidence/compile_exit_status.txt"),
                "simulation_exit_status":
                    integer("evidence/simulation_exit_status.txt"),
                "runner_exit_status": integer("evidence/runner_exit_status.txt"),
                "signal": "INT",
                "natural_terminal": False,
                "stable_level_counts_as_progress": False,
            },
            "formal_decision_collection": {
                "returned_parser_status": parser_status,
                "returned_parser_stderr": parser_stderr,
                "classification":
                    "PACKAGE_LOCAL_FINALIZER_BINDS_PARSER_TO_PRECANONICAL_CWD_RELATIVE_PACKAGE_ROOT",
                "local_exact_source_parser_replay_all_exit_zero": replay_ok,
                "raw_observer_sha256": sha(observer),
            },
            "local_exact_parser_replay": replays,
            "qualified_progress": {
                "stage": stage,
                "multislice_last_masks": multi.get("last_masks"),
                "mse4_last_qualified_masks": mse4.get("last_qualified_masks"),
                "mse4_last_state_masks": mse4.get("last_state_masks"),
                "ga_ob_last_qualified_masks": ga_ob.get("last_qualified_masks"),
                "ga_ob_last_state_masks": ga_ob.get("last_state_masks"),
            },
            "last_proven_good": {
                "boundary":
                    "SUM_S1_ALL_SLICES_GA_SELECTED_WRITE_AND_MSE4_IDX_REQ_QWR",
                "qualified_masks": {
                    "mse0": multi.get("last_masks", {}).get("mse0"),
                    "mse3": multi.get("last_masks", {}).get("mse3"),
                    "ga_in": multi.get("last_masks", {}).get("ga_in"),
                    "ga_selected_outbuffer_write":
                        multi.get("last_masks", {}).get("ga_out"),
                    "mse4_idx_hs":
                        mse4.get("last_qualified_masks", {}).get("idx_hs"),
                    "mse4_req":
                        mse4.get("last_qualified_masks", {}).get("req"),
                    "mse4_q_wr":
                        mse4.get("last_qualified_masks", {}).get("q_wr"),
                },
            },
            "first_divergence": {
                "boundary":
                    "V50_GA_OB_CONJUNCTION_TRACE_BUDGET_EXHAUSTED_ON_SLICE0_STATE_EDGES_BEFORE_SLICES1_15",
                "ga_ob_last_record_time_ps":
                    ga_ob_records[-1][0] if ga_ob_records else None,
                "ga_ob_last_record_n":
                    ga_ob_records[-1][1] if ga_ob_records else None,
                "first_later_slice_ga_output_time_ps":
                    later_slice_ga_output[0]
                    if later_slice_ga_output is not None else None,
                "first_later_slice_ga_output_mask":
                    f"0x{later_slice_ga_output[1]:04x}"
                    if later_slice_ga_output is not None else None,
                "budget_exhausted_before_target_slices":
                    ga_ob_budget_exhausted_before_target_slices,
                "functional_interpretation":
                    "v50 cannot adjudicate the slices1-15 GA outbuffer "
                    "write/nonempty/read conjunction; zero masks after slice0 "
                    "are observer saturation, not functional absence.",
            },
            "hang_root_cause": {
                "classification":
                    "LONG_RUNNING_HANG_AT_GA_OUTBUFFER_TO_MSE4_POST_QUEUE_PENDING_LEAF",
                "unique_leaf_closed": False,
                "remaining_candidates": [
                    "normal-vs-transout mode selection",
                    "selected-mode GA outbuffer write acceptance",
                    "outbuffer nonempty/read acceptance",
                    "MSE4 q_rd/buffer/prepared/direct-consumer acceptance",
                ],
                "package_side_issue":
                    "finalizer parser paths were captured before package_root "
                    "canonicalization; returned formal decisions fail closed.",
            },
            "blocker_delta": {
                "closed": [
                    "repeatable unique-return and exact-owned-reset binding",
                    "compile succeeds through v50 observer",
                ],
                "opened_or_refined": [
                    "B_GAP_NODE0071_V50_OBSERVER_STATE_EDGE_BUDGET_SATURATION",
                    "B_GAP_NODE0071_FINALIZER_PRECANONICAL_PARSER_PATH",
                ],
                "remaining":
                    "B_GAP_NODE0071_GA_OUTBUFFER_TO_MSE4_POST_QUEUE_PENDING_LEAF",
            },
            "formal_d": {
                "expected_count": 48,
                "present_count": 48 - gate["missing_count"],
                "missing_count": gate["missing_count"],
                "mismatch_byte_count": gate["mismatch_byte_count"],
                "mismatch_zero_evaluable": gate["missing_count"] == 0,
                "exact_set_complete":
                    gate["result_gate_conjunction"][
                        "formal_readback_exact_set_complete"
                    ],
                "all_result_terms_true":
                    gate["result_gate_conjunction"]["all_terms_true"],
            },
            "e3_e4_e5": {
                "E3": False,
                "E4": False,
                "E5": False,
                "reason": "INT, no natural terminal, and 0/48 formal D.",
            },
            "numeric_or_workload_repeated": False,
            "functional_rtl_modified": False,
            "successor_required": True,
            "successor_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        }
        write_json(output / "report.json", report)
        return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    report = analyze(args.output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["return_analysis"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
