#!/usr/bin/env python3
"""Final family audit for the p30 bank-valid/ready diagnostic package."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
SOURCE_ID = "r5_n4_0cc_p29_row2own"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_SHA256 = "43cfd63753ee964a92efec955f1dcba05c772c659406bd0142da8e37d2bd0f49"
P29_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_return_analysis/report_v2.json"
P29_ANALYSIS_SHA256 = "7e290b1bcfc83061133996561ba3c04acc2185cd5aee3a63f0680ce35c7fdd98"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return {"exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def extract(archive: zipfile.ZipFile, destination: Path) -> tuple[Path, list[str]]:
    names = archive.namelist()
    if archive.testzip() is not None or len(names) != len(set(names)):
        raise RuntimeError("CRC or duplicate-member gate failed")
    files = [name for name in names if not name.endswith("/")]
    roots = {PurePosixPath(name).parts[0] for name in files}
    if roots != {PACKAGE_ID}:
        raise RuntimeError(f"single-root identity differs: {sorted(roots)}")
    for name in files:
        pure = PurePosixPath(name)
        if pure.is_absolute() or ".." in pure.parts or "\\" in name:
            raise RuntimeError(f"unsafe ZIP member: {name}")
        target = destination.joinpath(*pure.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(name))
    return destination / PACKAGE_ID, files


def parser_trace(parser: Path, root: Path, name: str, lines: list[str]) -> dict[str, Any]:
    log = root / f"{name}.log"
    output = root / f"{name}.json"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    result = run([sys.executable, str(parser), "--log", str(log), "--output", str(output)])
    return {"process": result, "decision": json.loads(output.read_text(encoding="utf-8"))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite p30 family audit")
    if sha256(SOURCE_ZIP) != SOURCE_SHA256 or sha256(P29_ANALYSIS) != P29_ANALYSIS_SHA256:
        raise RuntimeError("p29 source/analysis identity differs")
    analysis = json.loads(P29_ANALYSIS.read_text(encoding="utf-8"))
    build = json.loads((zip_path.parent / f"{PACKAGE_ID}.build.json").read_text(encoding="utf-8"))
    source_bound = json.loads((zip_path.parent / f"{PACKAGE_ID}.source_bound_final_zip.json").read_text(encoding="utf-8"))
    post_sim = json.loads((zip_path.parent / f"{PACKAGE_ID}.post_sim.json").read_text(encoding="utf-8"))
    harness = json.loads((zip_path.parent / f"{PACKAGE_ID}.runner_harness.json").read_text(encoding="utf-8"))
    shared = json.loads((zip_path.parent / f"{PACKAGE_ID}.shared_layout.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="p30_family_") as temporary:
        temp = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            package, files = extract(archive, temp)
            manifest = json.loads(archive.read(f"{PACKAGE_ID}/package_manifest.json"))
            runner = archive.read(f"{PACKAGE_ID}/PREPARE_AND_RUN.sh").decode("utf-8")
            with zipfile.ZipFile(SOURCE_ZIP) as source:
                prefix = SOURCE_ID + "/"
                frozen = sorted(name[len(prefix):] for name in source.namelist() if name.startswith(prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/"))
                frozen_equal = all(archive.read(f"{PACKAGE_ID}/{name}") == source.read(prefix + name) for name in frozen)
                sca_equal = all(
                    archive.read(f"{PACKAGE_ID}/{name}").decode().replace(PACKAGE_ID, SOURCE_ID) == source.read(prefix + name).decode()
                    for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json")
                )
        runtime = package / "package_tools/node0004_assumed_hardware_server_runtime.py"
        observer_guard = package / "package_tools/node0004_package_observer_guard.py"
        preflight = run([sys.executable, str(runtime), "preflight", "--package-root", str(package)])
        guard = run([sys.executable, str(observer_guard), "--package-root", str(package)])
        python_syntax = run([sys.executable, "-W", "error", "-m", "py_compile", *[str(path) for path in sorted(package.rglob("*.py"))]])
        exact_parser = package / "package_tools/source_bound_causal_parser.py"
        identity = "instance=tb_NDP_Top_new_phy.U.U_Slice[0].u_Slice.u_LSU.u_Buffer_Manager_Cluster.BUFFER_MANAGER[5].u_Buffer_Manager.u_Buffer"
        enabled = [
            f"CODEX_PROBE_V1 kind=ENABLED boundary=row2_arm_bank_valid_timeline {identity}",
            f"CODEX_PROBE_V1 kind=ENABLED boundary=row2_mrm_clear_valid_timeline {identity}",
        ]
        all_ready_low_aggregate = parser_trace(exact_parser, temp, "bank_ff_ready_low", enabled + [
            f"CODEX_PROBE_V1 kind=EVENT boundary=row2_arm_bank_valid_timeline {identity} mask=22",
            f"CODEX_PROBE_V1 kind=EVENT boundary=row2_mrm_clear_valid_timeline {identity} mask=3",
        ])
        occupied_bank = parser_trace(exact_parser, temp, "bank_nonff_ready_low", enabled + [
            f"CODEX_PROBE_V1 kind=EVENT boundary=row2_arm_bank_valid_timeline {identity} mask=42",
            f"CODEX_PROBE_V1 kind=EVENT boundary=row2_mrm_clear_valid_timeline {identity} mask=5",
        ])
        incomplete = parser_trace(exact_parser, temp, "missing_enable", [
            f"CODEX_PROBE_V1 kind=EVENT boundary=row2_arm_bank_valid_timeline {identity} mask=22",
        ])

    scenarios = harness.get("scenarios", {})
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    six_state = all(
        scenarios.get(name, {}).get("runner_exit") == code
        and scenarios[name].get("finalizer_reached") is True
        and scenarios[name].get("fixed_result_return_published") is True
        and scenarios[name].get("root_exact_set_unchanged") is True
        and scenarios[name].get("writes_outside_install") is False
        for name, code in expected.items()
    )
    checks = {
        "transport_crc_root_path_exact_set": len(files) == 119,
        "source_p29_identity": analysis.get("valid") is True and analysis.get("status") == "P29_COMPETING_WRITER_CLOSED_BANK_VALID_READY_RECOMPUTE_SUCCESSOR_REQUIRED",
        "manifest_preflight": preflight["exit_code"] == 0 and json.loads(preflight["stdout"])["valid"] is True,
        "observer_guard": guard["exit_code"] == 0 and json.loads(guard["stdout"])["valid"] is True,
        "package_python_syntax": python_syntax["exit_code"] == 0,
        "frozen_87_payload": len(frozen) == 87 and frozen_equal and sca_equal,
        "deterministic_double_build": build["deterministic_double_build"] is True,
        "source_bound_exact_regeneration": source_bound["pass"] is True and not source_bound["errors"],
        "post_sim_independent_core": post_sim["pass"] is True and not post_sim["errors"],
        "runner_six_state": six_state,
        "shared_runtime_layout": shared["pass"] is True and not shared["errors"],
        "exact_parser_all_ready_split": all_ready_low_aggregate["process"]["exit_code"] == 0 and all_ready_low_aggregate["decision"]["decision"] == "BUFFER5_ROW2_BANKVALID_SIGNATURE_0100010100",
        "exact_parser_occupied_bank_split": occupied_bank["process"]["exit_code"] == 0 and occupied_bank["decision"]["decision"] == "BUFFER5_ROW2_BANKVALID_SIGNATURE_0100001010",
        "exact_parser_missing_enable_fail_closed": incomplete["process"]["exit_code"] == 1 and incomplete["decision"]["decision"] == "EVIDENCE_INCOMPLETE",
        "diagnostic_claim_boundary": manifest["candidate_release"] is False and manifest["formal_readback_count"] == 0 and manifest["formal_readback_claimed"] is False,
        "post_sim_single_json_core": runner.count('python3 "$post_sim_helper" finalize --request "$post_sim_request"') == 1,
    }
    valid = all(checks.values())
    report = {
        "schema": "conv-native-four-lane-0ccae916-p30-family-audit-v1",
        "status": "PASS" if valid else "FAIL",
        "valid": valid,
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {"path": str(zip_path), "bytes": zip_path.stat().st_size, "sha256": sha256(zip_path)},
        "source_bound_final_zip": source_bound,
        "post_sim_return_core": post_sim,
        "diagnostic_predicate_trace": {
            "all_banks_ready_aggregate_low": all_ready_low_aggregate["decision"],
            "occupied_bank_aggregate_low": occupied_bank["decision"],
            "missing_enable_negative": incomplete["decision"],
        },
        "runner_scenarios": {name: {"exit": scenarios.get(name, {}).get("runner_exit"), "published": scenarios.get(name, {}).get("fixed_result_return_published")} for name in expected},
        "frozen": {"install_payload_members": len(frozen), "byte_equal": frozen_equal, "sca_identity_normalized_equal": sca_equal},
        "claim_boundary": "Local/package gates only; no DUT run, natural terminal, formal 320D, E3, E4, E5 or performance claim.",
        "server_action": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": valid, "errors": report["errors"], "output": str(output)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
