#!/usr/bin/env python3
"""Audit exact p34 ZIP and live ARM-token correlation semantics."""

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
PACKAGE = "r5_n4_0cc_p34_armtoken"
SOURCE = "r5_n4_0cc_p33b_wrowner"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p33b_wrowner.zip"
SOURCE_SHA = "62b225be794774e1cd8c9a4f8a8d26e2cf5ecb1795ed44fe3d1ed748d81077df"
PRIOR_FIRST_FRESH_SHA = "48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def encode(layout: list[dict], values: dict[str, int]) -> str:
    payload = 0
    for field in layout:
        width = int(field["width_bits"])
        payload = (payload << width) | (int(values.get(field["name"], 0)) & ((1 << width) - 1))
    return f"{payload:x}"


def target_case(parser: Path, contract_path: Path, root: Path, case: str, mode: str, *, missing_enable: bool = False, wrong_instance: bool = False, mismatched_time: bool = False, noise_bytes: int = 0) -> dict:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    target = contract["target_parent"]
    other = target.replace("slice_group_gen[0]", "slice_group_gen[1]")
    buffer_instance = target + ".u_Buffer.codex_probe"
    arm_instance = target + ".u_Array_Request_Manager.codex_probe"
    lines: list[str] = []
    if not missing_enable:
        for boundary in contract["required_boundaries"]:
            instance = arm_instance if boundary in {contract["arm_boundary"], contract["final_boundary"]} else buffer_instance
            lines.append(f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance={instance}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['buffer_boundary']} instance={buffer_instance} time=100 mask=1 payload=0 seq=0")
    count = 1 if mode == "single" else 2
    for index in range(count):
        time = 110 + index * 10
        values = {
            "arm2buf_req_addr": 2, "arm2buf_req_valid": 255, "arm2buf_req_rw": 1,
            "arm2buf_wvalid": 1, "buf2arm_req_ready": 1, "array_req_addr": 2,
            "array_counter_0": index if mode == "progress" else 0,
            "array_counter_1": 0, "array_life_cnt": 0, "array2buf_valid_bit": 255,
            "array2buf_last_bit": 0, "array2buf_last_index": 15, "array2buf_same_bit": 0,
            "array_wreq_addr_rst": 1 if mode == "reset" and index == 1 else 0,
            "arm_addr_update": 1, "add_array_req_addr": 0,
            "add_array_counter_0": 1 if mode == "progress" else 0,
            "add_array_counter_1": 0, "add_array_life_cnt": 0,
        }
        mask = 1 | ((1 << 2) if mode == "progress" else 0) | ((1 << 5) if mode == "reset" and index == 1 else 0)
        buffer_target = other + ".u_Buffer.codex_probe" if wrong_instance else buffer_instance
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['buffer_boundary']} instance={buffer_target} time={time} mask=2 payload=0 seq={index}")
        arm_time = time + (1 if mismatched_time and index == count - 1 else 0)
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['arm_boundary']} instance={arm_instance} time={arm_time} mask={mask:x} payload={encode(contract['arm_payload_layout_msb_to_lsb'], values)} seq={index}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['final_boundary']} instance={arm_instance} time=130 mask=1 payload=0 seq=0")
    log = root / f"{case}.log"
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        if noise_bytes:
            chunk = "NON_TARGET_MULTI_INSTANCE_NOISE %m " + "x" * 980 + "\n"
            for _ in range((noise_bytes // len(chunk)) + 1):
                stream.write(chunk)
        stream.write("\n".join(lines) + "\n")
    output = root / f"{case}.json"
    process = run([sys.executable, str(parser), "--log", str(log), "--contract", str(contract_path), "--output", str(output)])
    decision = (
        json.loads(output.read_text(encoding="utf-8"))
        if output.is_file()
        else {"decision": "PARSER_DID_NOT_PUBLISH", "errors": [process.stderr[-4000:]]}
    )
    return {"exit_code": process.returncode, "log_bytes": log.stat().st_size, "decision": decision}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("refusing to overwrite p34 family audit")
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("p33b exact source differs")
    zip_path = args.zip.resolve()
    errors: list[str] = []
    checks: dict[str, bool] = {}
    case_results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="p34_family_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [row.filename for row in infos]
            checks["zip_crc"] = archive.testzip() is None
            checks["zip_duplicate_free"] = len(names) == len(set(names))
            checks["zip_single_root"] = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
            checks["zip_safe_members"] = all(not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16) for row in infos)
            archive.extractall(root)
        package = root / PACKAGE
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        actual = {row.relative_to(package).as_posix(): {"sha256": sha(row), "size_bytes": row.stat().st_size} for row in sorted(package.rglob("*")) if row.is_file() and row.name != "package_manifest.json"}
        checks["manifest_exact_set"] = manifest.get("files") == actual
        epoch = manifest.get("rule_change_epoch", {})
        checks["epoch_prior_pass_reuse"] = epoch.get("epoch_id") == "20260810-first-fresh-extra-audit-v1" and epoch.get("package_id") == PACKAGE and epoch.get("first_fresh_after_change") is False and epoch.get("prior_pass_sha256") == PRIOR_FIRST_FRESH_SHA
        checks["diagnostic_claim_only"] = manifest.get("candidate_release") is False and manifest.get("formal_readback_count") == 0
        preflight = run([sys.executable, str(package / "package_tools/node0004_assumed_hardware_server_runtime.py"), "preflight", "--package-root", str(package)])
        guard = run([sys.executable, str(package / "package_tools/node0004_package_observer_guard.py"), "--package-root", str(package)])
        syntax = run([sys.executable, "-W", "error", "-m", "py_compile", *map(str, sorted(package.rglob("*.py")))])
        checks["package_preflight"] = preflight.returncode == 0
        checks["observer_guard"] = guard.returncode == 0
        checks["python_syntax"] = syntax.returncode == 0
        with zipfile.ZipFile(SOURCE_ZIP) as source_archive:
            prefix = SOURCE + "/"
            frozen = sorted(name[len(prefix):] for name in source_archive.namelist() if name.startswith(prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/"))
            checks["frozen_87_payload"] = len(frozen) == 87 and all((package / name).read_bytes() == source_archive.read(prefix + name) for name in frozen)
            checks["sca_normalized_equal"] = all((package / name).read_text(encoding="utf-8").replace(PACKAGE, SOURCE) == source_archive.read(prefix + name).decode() for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json"))
        family_parser = package / "package_tools/arm_token_parser.py"
        contract_path = package / "diagnostics/arm_token_contract.json"
        expected_decisions = {
            "stable": "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT",
            "progress": "TARGET_ARM_ROW2_DISTINCT_TOKEN_STATE_PROGRESS",
            "reset": "TARGET_ARM_ROW2_RESET_OR_WRAP",
            "single": "TARGET_ARM_ROW2_SINGLE_ACCEPT_ONLY",
        }
        for mode, decision in expected_decisions.items():
            case_results[mode] = target_case(family_parser, contract_path, root, f"positive_{mode}", mode, noise_bytes=(17 * 1024 * 1024 if mode == "stable" else 0))
        checks["four_live_token_positive_controls"] = all(case_results[mode]["exit_code"] == 0 and case_results[mode]["decision"]["decision"] == decision for mode, decision in expected_decisions.items())
        checks["overbudget_multi_instance_parser"] = case_results["stable"]["log_bytes"] > 16 * 1024 * 1024
        negatives = {
            "missing_enable": target_case(family_parser, contract_path, root, "negative_missing_enable", "stable", missing_enable=True),
            "wrong_instance": target_case(family_parser, contract_path, root, "negative_wrong_instance", "stable", wrong_instance=True),
            "mismatched_time": target_case(family_parser, contract_path, root, "negative_mismatched_time", "stable", mismatched_time=True),
        }
        checks["three_target_time_negatives_fail_closed"] = all(row["exit_code"] != 0 and row["decision"]["decision"] == "EVIDENCE_INCOMPLETE" for row in negatives.values())
        case_results.update(negatives)
        observer = (package / "tb_probe/source_bound_causal_observer.svh").read_text(encoding="utf-8")
        checks["generated_live_arm_token_boundary"] = "EVENT boundary=arm_row2_accept_token_state" in observer and "bind Array_Request_Manager codex_probe_arm_row2_accept_token_state" in observer
        request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        plugins = [row for row in request["plugins"] if row.get("plugin_id") == "arm_token_parser"]
        checks["post_sim_target_plugin_exact"] = len(plugins) == 1 and plugins[0].get("required_for_adjudication") is True and any(row.get("archive") == "evidence/arm_token_decision.json" and row.get("required") is True for row in request["core_entries"])
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        checks["target_parser_source_contract_bound"] = contract.get("target_parser_source_sha256") == sha(ROOT / "tools/conv_native_four_lane_p34_arm_token_parser.py") and sha(family_parser) == contract.get("target_parser_source_sha256")
    errors.extend(name for name, passed in checks.items() if not passed)
    report = {
        "schema": "conv-native-four-lane-p34-armtoken-family-audit-v1", "valid": not errors, "pass": not errors,
        "errors": errors, "checks": checks, "case_results": case_results,
        "positive_control_count": 4, "negative_control_count": 3,
        "pairwise_distinguishable": checks.get("four_live_token_positive_controls", False),
        "zip": {"path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size, "sha256": sha(zip_path)},
        "claim_boundary": "Static/package-local live target token audit only; no production natural terminal, formal D or E3-E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
