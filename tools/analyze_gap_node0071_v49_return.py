from __future__ import annotations

import argparse
import hashlib
import json
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
RETURN_PATH = Path(
    r"C:\Users\15383\Downloads\r5_n71_gap_v49_mse4_maskwide_diag_return.zip"
)
RETURN_SHA = "ec3811f7024e8b2ce4e90681d7d9faffbc8f4c5509d3da91ea69d4b9eb86314d"
SOURCE_PATH = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n71_gap_v49_mse4_maskwide_diag.zip"
)
SOURCE_SHA = "eb2f5f02b3dce69aad51a3319972622b7cff8d594ef9cbf5909efb7c4114d85a"
INSTALL = "r5_n71_gap_v49_mse4_maskwide_diag"
RETURN_ROOT = f"{INSTALL}_return"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_members(archive: zipfile.ZipFile, expected_root: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    seen: set[str] = set()
    roots: set[str] = set()
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
            errors.append(f"unsafe path: {info.filename}")
        if info.filename in seen:
            errors.append(f"duplicate member: {info.filename}")
        seen.add(info.filename)
        if pure.parts:
            roots.add(pure.parts[0])
        if stat.S_ISLNK(mode):
            errors.append(f"symlink member: {info.filename}")
    if roots != {expected_root}:
        errors.append(f"root mismatch: {sorted(roots)}")
    bad = archive.testzip()
    if bad is not None:
        errors.append(f"CRC failure: {bad}")
    return not errors, errors


def run_parser(argv: list[str], output: Path) -> dict[str, object]:
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    value = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else None
    return {
        "argv": argv,
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "output": value,
    }


def analyze(output: Path) -> dict[str, object]:
    errors: list[str] = []
    if not RETURN_PATH.is_file() or sha(RETURN_PATH) != RETURN_SHA:
        raise RuntimeError("formal return identity mismatch")
    if not SOURCE_PATH.is_file() or sha(SOURCE_PATH) != SOURCE_SHA:
        raise RuntimeError("source v49 identity mismatch")

    with tempfile.TemporaryDirectory(prefix="gap-v49-return-") as tmp:
        temp = Path(tmp)
        with zipfile.ZipFile(RETURN_PATH) as archive:
            return_safe, return_errors = safe_members(archive, RETURN_ROOT)
            errors.extend(return_errors)
            archive.extractall(temp / "return")
            return_names = {
                PurePosixPath(info.filename).relative_to(RETURN_ROOT).as_posix()
                for info in archive.infolist()
                if not info.is_dir()
            }
        returned = temp / "return" / RETURN_ROOT
        manifest_path = returned / "RETURN_MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        listed = {row["path"] for row in manifest["files"]}
        exact_set = return_names == listed | {"RETURN_MANIFEST.json"}
        if not exact_set:
            errors.append("RETURN_MANIFEST exact-set mismatch")
        per_file_valid = True
        for row in manifest["files"]:
            path = returned / row["path"]
            valid = (
                path.is_file()
                and path.stat().st_size == row["size_bytes"]
                and sha(path) == row["sha256"]
            )
            per_file_valid &= valid
            if not valid:
                errors.append(f"per-file receipt mismatch: {row['path']}")

        with zipfile.ZipFile(SOURCE_PATH) as archive:
            source_safe, source_errors = safe_members(archive, INSTALL)
            errors.extend(source_errors)
            archive.extractall(temp / "source")
        source = temp / "source" / INSTALL
        returned_package_manifest = returned / "evidence/PACKAGE_MANIFEST.json"
        source_manifest = source / "TEST_PACKAGE_MANIFEST.json"
        source_bound = returned_package_manifest.read_bytes() == source_manifest.read_bytes()
        if not source_bound:
            errors.append("returned package manifest differs from frozen source")

        replay = output / "formal_replay"
        replay.mkdir(parents=True, exist_ok=True)
        observer = returned / "runs/return_observer.log"
        sim_log = returned / "logs/sim.log"
        tools = source / "package_tools"
        parser_specs = {
            "stage": "gap_node0071_stage_transition_decision.py",
            "multislice": "gap_node0071_multislice_pipeline_decision.py",
            "mse4_maskwide": "gap_node0071_mse4_maskwide_decision.py",
        }
        replay_runs: dict[str, object] = {}
        for name, tool_name in parser_specs.items():
            target = replay / f"{name}.json"
            replay_runs[name] = run_parser(
                [
                    sys.executable,
                    str(tools / tool_name),
                    "analyze",
                    "--observer-log",
                    str(observer),
                    "--output",
                    str(target),
                ],
                target,
            )
        canonical_target = replay / "canonical.json"
        replay_runs["canonical"] = run_parser(
            [
                sys.executable,
                str(tools / "gap_node0071_canonical_decision.py"),
                "observe",
                "--observer-log",
                str(observer),
                "--sim-log",
                str(sim_log),
                "--signal",
                "INT",
                "--simulation-status",
                "125",
                "--stall-window-cycles",
                "1048576",
                "--heartbeat-cycles",
                "262144",
                "--manifest",
                str(source_manifest),
                "--output",
                str(canonical_target),
            ],
            canonical_target,
        )
        replay_ok = all(row["exit_code"] == 0 for row in replay_runs.values())

        gate = json.loads(
            (returned / "evidence/SERVER_RESULT_GATE.json").read_text(encoding="utf-8")
        )
        installed = json.loads(
            (returned / "evidence/installed_preflight.json").read_text(encoding="utf-8")
        )
        observer_precompile = json.loads(
            (returned / "evidence/observer_precompile.json").read_text(encoding="utf-8")
        )
        root_gate = json.loads(
            (returned / "evidence/ndp_root_toplevel_exact_set.json").read_text(
                encoding="utf-8"
            )
        )
        returned_mse4 = json.loads(
            (returned / "evidence/mse4_maskwide_decision.json").read_text(
                encoding="utf-8"
            )
        )
        replay_mse4 = replay_runs["mse4_maskwide"]["output"]
        replay_multi = replay_runs["multislice"]["output"]
        replay_stage = replay_runs["stage"]["output"]

        report = {
            "schema": "gap-node0071-v49-return-analysis-v1",
            "status":
                "PARTIAL_INTERRUPTED_AT_SLICES1_15_GA_OUTBUFFER_READ_BEFORE_MSE4_DATA_PATH",
            "analysis_owner_thread": "019fa366-cb1f-7ae2-880c-f527be0680cd",
            "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
            "return_analysis": {
                "path": str(RETURN_PATH),
                "bytes": RETURN_PATH.stat().st_size,
                "sha256": sha(RETURN_PATH),
                "adjacent_sidecar_present": Path(str(RETURN_PATH) + ".sha256").is_file(),
                "transport_policy":
                    "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
                "crc_root_path_duplicate_symlink_valid": return_safe,
                "manifest_exact_set": exact_set,
                "allowlist_only": manifest.get("allowlist_only") is True,
                "per_file_receipts_valid": per_file_valid,
                "required_missing_count": len(manifest["required_missing"]),
                "formal_return_complete": manifest["status"] == "complete",
                "errors": errors,
            },
            "source_binding": {
                "path": str(SOURCE_PATH),
                "bytes": SOURCE_PATH.stat().st_size,
                "sha256": sha(SOURCE_PATH),
                "source_crc_root_valid": source_safe,
                "returned_manifest_byte_equal": source_bound,
                "package": f"{INSTALL}.zip",
                "install": INSTALL,
                "return": RETURN_ROOT,
            },
            "runtime_binding": {
                "installed_preflight_valid": installed["valid"],
                "formal_targets_initially_absent":
                    installed["formal_readback_targets_absent"],
                "observer_precompile_valid": observer_precompile["valid"],
                "observer_identity_match": observer_precompile["identity_match"],
                "observer_feature_bound": (
                    returned / "evidence/observer_binding.txt"
                ).read_text(encoding="utf-8").count("=true") == 5,
                "ndp_root_toplevel_unchanged":
                    root_gate["ndp_root_toplevel_unchanged"],
                "actual_compile_and_simulator_argv_returned": True,
                "actual_compiled_cloud_identity": "not proven by this return",
            },
            "execution": {
                "compile_exit_status": 0,
                "simulation_exit_status": 125,
                "runner_exit_status": 130,
                "signal": "INT",
                "natural_terminal": False,
                "termination_class": "EXTERNAL_INT_AFTER_LONG_STABLE_QUALIFIED_FRONTIER",
                "stable_level_counts_as_progress": False,
            },
            "formal_return_decision_collection": {
                "returned_decision": returned_mse4,
                "classification":
                    "PACKAGE_LOCAL_FINALIZER_PARSER_OUTPUTS_ALL_FELL_BACK_FAIL_CLOSED",
                "raw_observer_present_and_bound": observer.is_file(),
                "raw_observer_sha256": sha(observer),
                "local_exact_source_tool_replay_all_exit_zero": replay_ok,
                "claim_boundary":
                    "Local exact replay is diagnostic evidence, not a replacement for missing "
                    "formal decision artifacts or formal D.",
            },
            "local_exact_parser_replay": replay_runs,
            "qualified_progress": {
                "multislice_last_masks": replay_multi["last_masks"],
                "mse4_last_qualified_masks": replay_mse4["last_qualified_masks"],
                "mse4_last_state_masks": replay_mse4["last_state_masks"],
                "stage": replay_stage,
                "slices_1_to_15_first_missing": "ga_rd",
                "qualified_frontier": (
                    "GA outbuffer write and MSE4 index/request/queue-write occurred; "
                    "GA outbuffer read and MSE4 queue-read/data path did not."
                ),
            },
            "formal_d": {
                "expected_count": 48,
                "present_count": 0,
                "missing_count": gate["missing_count"],
                "mismatch_byte_count": gate["mismatch_byte_count"],
                "mismatch_zero_evaluable": False,
                "exact_set_complete": False,
                "all_result_terms_true":
                    gate["result_gate_conjunction"]["all_terms_true"],
            },
            "last_proven_good":
                "All 16 slices reached cfg start/finish, MSE0/MSE3 acceptance, GA input and "
                "GA outbuffer write; all 16 reached MSE4 index/request/queue-write.",
            "first_divergence":
                "SLICES_1_TO_15_GA_OUTBUFFER_WRITE_WITHOUT_GA_OUTBUFFER_READ; "
                "MSE4_REQUEST_QUEUES_FILL_WITHOUT_QUEUE_READ_OR_DATA_ACCEPT",
            "hang_root_cause":
                "LONG_RUNNING_HANG_AT_NONZERO_SLICE_GA_OUTBUFFER_READ_CONJUNCTION_"
                "PENDING_OUTBUFFER_NONEMPTY_OR_DOWNSTREAM_BP_LEAF",
            "root_cause_scope": {
                "unique": False,
                "remaining_candidates": [
                    "GA outbuffer nonempty/read-ready after write",
                    "GA connect downstream all-destination backpressure/read-request",
                    "GA outbuffer read handshake direct consumer mapping",
                ],
                "config_implicated": False,
                "functional_rtl_implicated": False,
                "package_runner_defect_also_present":
                    "formal decision parsers produced no artifacts in signal finalizer",
            },
            "e3_e4_e5": {
                "E3": False,
                "E4": False,
                "E5": False,
                "reason":
                    "INT, no natural terminal, 0/48 formal D; mismatch=0 is unevaluable.",
            },
            "blocker_delta": {
                "closed": [
                    "all-slice MSE4 index handshake",
                    "all-slice MSE4 request acceptance",
                    "all-slice MSE4 request queue write",
                ],
                "opened": [
                    "slice1-15 GA outbuffer read conjunction",
                    "v49 finalizer parser execution/receipt",
                ],
                "unchanged": [
                    "natural terminal",
                    "48 formal D",
                    "actual compiled production identity",
                ],
            },
            "successor_proposal": {
                "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "information_gain_scope":
                    "all-slice GA outbuffer write/nonempty/read-request/downstream-bp/read-handshake "
                    "plus existing MSE4 queue/data frontier",
                "runner_fix":
                    "capture parser exit/stderr and use one fail-closed decision bundle path",
                "freeze":
                    "numeric/sum/tail/workload/config/golden/timeout/backpressure/functional RTL",
            },
            "rule_confirmation": [
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-DIAGNOSTIC-TIME-TO-ROOT-CAUSE-OPTIMIZATION-001",
                "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            ],
            "rule_delta_proposal":
                "Required finalizer decision commands must return their exit/stderr receipts; "
                "fallback presence alone cannot distinguish absent input from parser execution failure.",
            "package_release": "PENDING_SUCCESSOR_BUILD",
            "numeric_or_workload_repeated": False,
            "functional_rtl_modified": False,
        }
        write_json(output / "report.json", report)
        return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.output.resolve())
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["return_analysis"]["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
