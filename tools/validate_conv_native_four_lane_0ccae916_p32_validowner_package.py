#!/usr/bin/env python3
"""Audit exact p32 ZIP, frozen payload and target/epoch parser semantics."""

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
PACKAGE = "r5_n4_0cc_p32b_validowner"
SOURCE = "r5_n4_0cc_p31_postclear"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p31_postclear.zip"
SOURCE_SHA = "d022977daebb1c633d0c4fa32ca58cf5b660a6f4c4dff6cb11d499a21d2345c9"
PRIOR_FIRST_FRESH_SHA = "48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def target_case(
    parser: Path,
    contract_path: Path,
    root: Path,
    case: str,
    state_boundary: str | None,
    *,
    missing_enable: bool = False,
    conflicting_boundary: str | None = None,
    state_time: int = 101,
    state_other_instance: bool = False,
    noise_bytes: int = 0,
) -> dict:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    target = contract["target_parent"]
    other = target.replace("slice_group_gen[0]", "slice_group_gen[1]")
    buffer_instance = target + ".u_Buffer.codex_probe"
    final_instance = target + ".u_Array_Request_Manager.codex_probe"
    lines: list[str] = []
    if not missing_enable:
        for boundary in contract["required_boundaries"]:
            instance = final_instance if boundary == contract["final_boundary"] else buffer_instance
            lines.append(f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance={instance}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['clear_boundary']} instance={buffer_instance} time=100 mask=1 payload=0 seq=0")
    if state_boundary is not None:
        instance = other + ".u_Buffer.codex_probe" if state_other_instance else buffer_instance
        lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={state_boundary} instance={instance} time={state_time} mask=1 payload=0 seq=0")
    if conflicting_boundary is not None:
        lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={conflicting_boundary} instance={buffer_instance} time=102 mask=1 payload=0 seq=0")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['final_boundary']} instance={final_instance} time=132 mask=1 payload=0 seq=0")
    log = root / f"{case}.log"
    with log.open("w", encoding="utf-8", newline="\n") as stream:
        if noise_bytes:
            chunk = "NON_TARGET_MULTI_INSTANCE_NOISE %m " + "x" * 980 + "\n"
            for _ in range((noise_bytes // len(chunk)) + 1):
                stream.write(chunk)
        stream.write("\n".join(lines) + "\n")
    output = root / f"{case}.json"
    process = run([sys.executable, str(parser), "--log", str(log), "--contract", str(contract_path), "--output", str(output)])
    decision = json.loads(output.read_text(encoding="utf-8"))
    return {"exit_code": process.returncode, "log_bytes": log.stat().st_size, "decision": decision}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("refusing to overwrite p32 family audit")
    zip_path = args.zip.resolve()
    errors: list[str] = []
    checks: dict[str, bool] = {}
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("p31 exact source differs")
    with tempfile.TemporaryDirectory(prefix="p32_family_") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [row.filename for row in infos]
            checks["zip_crc"] = archive.testzip() is None
            checks["zip_duplicate_free"] = len(names) == len(set(names))
            checks["zip_single_root"] = {PurePosixPath(name).parts[0] for name in names if name} == {PACKAGE}
            checks["zip_safe_members"] = all(
                not PurePosixPath(row.filename).is_absolute() and ".." not in PurePosixPath(row.filename).parts
                and "\\" not in row.filename and not stat.S_ISLNK(row.external_attr >> 16)
                for row in infos
            )
            archive.extractall(root)
        package = root / PACKAGE
        manifest = json.loads((package / "package_manifest.json").read_text(encoding="utf-8"))
        actual = {
            row.relative_to(package).as_posix(): {"sha256": sha(row), "size_bytes": row.stat().st_size}
            for row in sorted(package.rglob("*")) if row.is_file() and row.name != "package_manifest.json"
        }
        checks["manifest_exact_set"] = manifest.get("files") == actual
        epoch = manifest.get("rule_change_epoch", {})
        checks["epoch_prior_pass_reuse"] = (
            epoch.get("epoch_id") == "20260810-first-fresh-extra-audit-v1"
            and epoch.get("package_id") == PACKAGE and epoch.get("first_fresh_after_change") is False
            and epoch.get("prior_pass_sha256") == PRIOR_FIRST_FRESH_SHA
        )
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
            checks["sca_normalized_equal"] = all(
                (package / name).read_text(encoding="utf-8").replace(PACKAGE, SOURCE) == source_archive.read(prefix + name).decode()
                for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json")
            )
        target_parser = package / "package_tools/target_epoch_valid_owner_parser.py"
        target_contract = package / "diagnostics/target_epoch_correlator_contract.json"
        contract = json.loads(target_contract.read_text(encoding="utf-8"))
        state_expected = {
            "row2_postclear_bank_0f_no_write_accept": "TARGET_POSTCLEAR_0F_NO_WRITE_ACCEPT",
            "row2_postclear_bank_0f_write_accept": "TARGET_POSTCLEAR_0F_WRITE_ACCEPT",
            "row2_postclear_bank_00": "TARGET_POSTCLEAR_BANK_READY_00",
            "row2_postclear_bank_f0": "TARGET_POSTCLEAR_BANK_READY_F0",
            "row2_postclear_bank_ff": "TARGET_POSTCLEAR_BANK_READY_FF",
            "row2_postclear_bank_other": "TARGET_POSTCLEAR_BANK_READY_OTHER",
            None: "TARGET_POST_STATE_NOT_REACHED",
        }
        cases = {
            str(state): target_case(target_parser, target_contract, root, f"positive_{index}", state, noise_bytes=(17 * 1024 * 1024 if index == 0 else 0))
            for index, state in enumerate(state_expected)
        }
        checks["seven_target_candidate_positive_controls"] = all(
            cases[str(state)]["exit_code"] == 0
            and cases[str(state)]["decision"]["decision"] == expected
            and len(cases[str(state)]["decision"]["matching_candidate_ids"]) == 1
            for state, expected in state_expected.items()
        )
        checks["overbudget_multi_instance_parser"] = cases["row2_postclear_bank_0f_no_write_accept"]["log_bytes"] > 16 * 1024 * 1024
        missing = target_case(target_parser, target_contract, root, "negative_missing_enable", "row2_postclear_bank_0f_no_write_accept", missing_enable=True)
        conflict = target_case(target_parser, target_contract, root, "negative_conflict", "row2_postclear_bank_0f_no_write_accept", conflicting_boundary="row2_postclear_bank_ff")
        wrong_epoch = target_case(target_parser, target_contract, root, "negative_wrong_epoch", "row2_postclear_bank_0f_no_write_accept", state_time=99)
        wrong_instance = target_case(target_parser, target_contract, root, "negative_wrong_instance", "row2_postclear_bank_0f_no_write_accept", state_other_instance=True)
        checks["negative_missing_enable_fail_closed"] = missing["exit_code"] != 0 and missing["decision"]["decision"] == "EVIDENCE_INCOMPLETE"
        checks["negative_simultaneous_class_fail_closed"] = conflict["exit_code"] != 0 and conflict["decision"]["decision"] == "EVIDENCE_INCOMPLETE"
        checks["negative_wrong_epoch_fail_closed"] = wrong_epoch["exit_code"] != 0 and wrong_epoch["decision"]["decision"] == "EVIDENCE_INCOMPLETE"
        checks["wrong_instance_cannot_satisfy_target_candidate"] = wrong_instance["decision"]["decision"] == "TARGET_POST_STATE_NOT_REACHED"
        request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        target_plugins = [row for row in request["plugins"] if row.get("plugin_id") == "target_epoch_valid_owner_parser"]
        checks["post_sim_target_plugin_exact"] = (
            len(target_plugins) == 1 and target_plugins[0].get("required_for_adjudication") is True
            and any(row.get("archive") == "evidence/target_epoch_valid_owner_decision.json" and row.get("required") is True for row in request["core_entries"])
        )
        checks["target_parser_source_contract_bound"] = (
            contract.get("target_parser_source_sha256") == hashlib.sha256((ROOT / "tools/conv_native_four_lane_p32_target_epoch_parser.py").read_bytes()).hexdigest()
            and sha(target_parser) == contract.get("target_parser_source_sha256")
        )
    errors.extend(name for name, passed in checks.items() if not passed)
    report = {
        "schema": "conv-native-four-lane-p32b-validowner-family-audit-v1",
        "valid": not errors, "pass": not errors, "errors": errors, "checks": checks,
        "target_candidate_case_results": cases, "positive_control_count": 7, "negative_control_count": 4,
        "pairwise_distinguishable": checks.get("seven_target_candidate_positive_controls", False),
        "zip": {"path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size, "sha256": sha(zip_path)},
        "claim_boundary": "Static/package-local target-instance epoch audit only; no production natural terminal, formal D or E3-E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
