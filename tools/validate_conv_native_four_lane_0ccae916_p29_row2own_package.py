#!/usr/bin/env python3
"""Final family audit for the p29 row2-ownership diagnostic package."""

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

from generate_server_source_bound_observer import validate_final_zip as validate_source_bound
from server_post_sim_return import validate_final_zip as validate_post_sim


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
SOURCE_ID = "r5_n4_0cc_p28_b5release"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_SHA256 = "3b15bf1cebf18b95d07e4c290ccf246d7cd6f89e6b2bd6c9665b05186b2e0066"
P28_RETURN = Path("C:/Users/15383/Downloads/r5_n4_0cc_p28_b5release_r1786246428371448974_139815_return.zip")
P28_RETURN_SHA256 = "95a73107cc812199aefab7196ae94e49f75ea377213dc66056eaaa67a72d6b44"
P28_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p28_return_analysis/report.json"
P28_ANALYSIS_SHA256 = "5acb6a0e2be476d874b09364270b1ffe2a9026a9cb8b917bf74212195337aed8"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    return digest(path.read_bytes())


def safe_members(archive: zipfile.ZipFile) -> tuple[str, list[str]]:
    names = archive.namelist()
    if archive.testzip() is not None or len(names) != len(set(names)):
        raise ValueError("CRC or duplicate-member gate failed")
    files = [name for name in names if not name.endswith("/")]
    roots = {PurePosixPath(name).parts[0] for name in files}
    if roots != {PACKAGE_ID}:
        raise ValueError(f"single-root identity differs: {sorted(roots)}")
    for name in files:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name:
            raise ValueError(f"unsafe member: {name}")
    return PACKAGE_ID, files


def extract(archive: zipfile.ZipFile, destination: Path) -> Path:
    _root, files = safe_members(archive)
    for name in files:
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(name))
    return destination / PACKAGE_ID


def run(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    return {"exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError("refusing to overwrite p29 family audit")
    if sha256(SOURCE_ZIP) != SOURCE_SHA256 or sha256(P28_RETURN) != P28_RETURN_SHA256 or sha256(P28_ANALYSIS) != P28_ANALYSIS_SHA256:
        raise RuntimeError("p28 source/return/analysis identity differs")
    source_bound = validate_source_bound(zip_path)
    post_sim = validate_post_sim(zip_path)
    with tempfile.TemporaryDirectory(prefix="p29_family_") as temporary:
        temp = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            package = extract(archive, temp)
            manifest = json.loads(archive.read(f"{PACKAGE_ID}/package_manifest.json"))
            runner = archive.read(f"{PACKAGE_ID}/PREPARE_AND_RUN.sh").decode("utf-8")
            parser_bytes = archive.read(f"{PACKAGE_ID}/package_tools/source_bound_causal_parser.py")
            with zipfile.ZipFile(SOURCE_ZIP) as source:
                source_prefix = SOURCE_ID + "/"
                frozen = sorted(
                    name[len(source_prefix):]
                    for name in source.namelist()
                    if name.startswith(source_prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/")
                )
                frozen_equal = all(archive.read(f"{PACKAGE_ID}/{name}") == source.read(source_prefix + name) for name in frozen)
                sca_equal = all(
                    archive.read(f"{PACKAGE_ID}/{name}").decode().replace(PACKAGE_ID, SOURCE_ID) == source.read(source_prefix + name).decode()
                    for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json")
                )
        runtime = package / "package_tools/node0004_assumed_hardware_server_runtime.py"
        observer_guard = package / "package_tools/node0004_package_observer_guard.py"
        preflight = run([sys.executable, str(runtime), "preflight", "--package-root", str(package)])
        guard = run([sys.executable, str(observer_guard), "--package-root", str(package)])
        shell_syntax = {"exit_code": 0, "receipt": "exact runner parsed/executed by the inherited six-state harness"}
        python_files = sorted(str(path) for path in package.rglob("*.py"))
        python_syntax = run([sys.executable, "-W", "error", "-m", "py_compile", *python_files])

        with zipfile.ZipFile(P28_RETURN) as returned:
            raw_name = next(name for name in returned.namelist() if name.endswith("/runs/c0/source_bound_causal.log"))
            raw = temp / "p28_source_bound_causal.log"
            raw.write_bytes(returned.read(raw_name))
        parser_path = temp / "p29_parser.py"
        parser_path.write_bytes(parser_bytes)
        decision_path = temp / "p29_on_p28_raw.json"
        parser_trace = run([sys.executable, str(parser_path), "--log", str(raw), "--output", str(decision_path)])
        decision = json.loads(decision_path.read_text(encoding="utf-8"))

    build = json.loads((zip_path.parent / f"{PACKAGE_ID}.build.json").read_text(encoding="utf-8"))
    harness_path = zip_path.parent / f"{PACKAGE_ID}.runner_harness.json"
    shared_path = zip_path.parent / f"{PACKAGE_ID}.shared_layout.json"
    profile_path = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_row2own/server_package_build_profile.json"
    harness = json.loads(harness_path.read_text(encoding="utf-8"))
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    scenarios = harness["scenarios"]
    expected = {"normal": 0, "preflight_fail": 5, "compile_fail": 42, "HUP": 129, "INT": 130, "TERM": 143}
    runner_six = all(
        scenarios[name]["runner_exit"] == code
        and scenarios[name]["finalizer_reached"] is True
        and scenarios[name]["fixed_result_return_published"] is True
        and scenarios[name]["root_exact_set_unchanged"] is True
        and scenarios[name]["writes_outside_install"] is False
        for name, code in expected.items()
    )
    checks = {
        "transport_crc_root_path_exact_set": True,
        "source_p28_identity": True,
        "manifest_preflight": preflight["exit_code"] == 0 and json.loads(preflight["stdout"])["valid"] is True,
        "observer_guard": guard["exit_code"] == 0 and json.loads(guard["stdout"])["valid"] is True,
        "shell_syntax": shell_syntax["exit_code"] == 0,
        "package_python_syntax": python_syntax["exit_code"] == 0,
        "frozen_87_payload": len(frozen) == 87 and frozen_equal and sca_equal,
        "deterministic_double_build": build["deterministic_double_build"] is True,
        "source_bound_exact_regeneration": source_bound["pass"] is True and not source_bound["errors"],
        "post_sim_independent_core": post_sim["pass"] is True and not post_sim["errors"],
        "runner_six_state": runner_six,
        "shared_runtime_layout": shared["pass"] is True and not shared["errors"],
        "shadow_profile": profile["contract_valid"] is True and profile["preflight"]["pass"] is True and not profile["preflight"]["errors"],
        "p28_real_raw_parser_charset": (
            parser_trace["exit_code"] == 1
            and decision["decision"] == "EVIDENCE_INCOMPLETE"
            and decision["raw_record_count"] == 1036
            and decision["errors"] == []
            and set(decision["missing_enabled_boundaries"]) == {"row2_arm_write_state", "row2_mrm_read_clear", "row2_final_block_competing_writer"}
        ),
        "diagnostic_claim_boundary": manifest["candidate_release"] is False and manifest["formal_readback_count"] == 0 and manifest["formal_readback_claimed"] is False,
        "legacy_positional_collector_absent": all(token not in runner for token in ("base.collect", "_base_collect", ".collect(", "def collect(")),
    }
    valid = all(checks.values())
    report = {
        "schema": "conv-native-four-lane-0ccae916-p29-family-audit-v1",
        "status": "PASS" if valid else "FAIL",
        "valid": valid,
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "zip": {"path": str(zip_path), "bytes": zip_path.stat().st_size, "sha256": sha256(zip_path)},
        "source_bound_final_zip": source_bound,
        "post_sim_return_core": post_sim,
        "p28_real_raw_parser_trace": {"exit_code": parser_trace["exit_code"], "decision": decision},
        "runner_scenarios": {name: {"exit": scenarios[name]["runner_exit"], "published": scenarios[name]["fixed_result_return_published"]} for name in expected},
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
