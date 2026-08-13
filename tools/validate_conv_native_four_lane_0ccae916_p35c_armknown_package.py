#!/usr/bin/env python3
"""Audit exact p35c ZIP and binary-known live ARM diagnostics."""

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

import validate_conv_native_four_lane_0ccae916_p34_armtoken_package as p34


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p35c_armknown"
SOURCE = "r5_n4_0cc_p34b_armtoken"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE}.zip"
SOURCE_SHA = "98d9f8b23824d2b5ec9e90f87fdfa1a3ee6bc61df5c9edca81ff19cf5f5b5fd1"
HELPER_SHA = "19bea6cc8bb5bd6247f7d2da67de3df967a562f1193c82a2f1a1ddb1ae483e6f"
EPOCH = "20260811-native-live-causal-partial-exit-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def parser_case(parser: Path, contract: Path, log_text: str, root: Path, name: str) -> dict:
    log = root / f"{name}.log"
    output = root / f"{name}.json"
    log.write_text(log_text, encoding="utf-8", newline="\n")
    process = run([sys.executable, str(parser), "--log", str(log), "--contract", str(contract), "--output", str(output)])
    decision = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {"decision": "PARSER_DID_NOT_PUBLISH"}
    return {"exit_code": process.returncode, "decision": decision, "log_bytes": log.stat().st_size}


def main() -> int:
    cli = argparse.ArgumentParser()
    cli.add_argument("--zip", required=True, type=Path)
    cli.add_argument("--output", required=True, type=Path)
    args = cli.parse_args()
    if args.output.exists():
        raise RuntimeError("refusing to overwrite p35c family audit")
    if sha(SOURCE_ZIP) != SOURCE_SHA:
        raise RuntimeError("p34b exact source differs")
    zip_path = args.zip.resolve()
    checks: dict[str, bool] = {}
    cases: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="p35c_family_") as temporary:
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
        checks["new_rule_epoch_ack"] = epoch.get("epoch_id") == EPOCH and epoch.get("package_id") == PACKAGE and epoch.get("first_fresh_after_change") is True and epoch.get("notification_acknowledged") is True and epoch.get("rule_ids") == ["CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001"]
        checks["diagnostic_claim_only"] = manifest.get("candidate_release") is False and manifest.get("formal_readback_count") == 0
        checks["package_preflight"] = run([sys.executable, str(package / "package_tools/node0004_assumed_hardware_server_runtime.py"), "preflight", "--package-root", str(package)]).returncode == 0
        checks["observer_guard"] = run([sys.executable, str(package / "package_tools/node0004_package_observer_guard.py"), "--package-root", str(package)]).returncode == 0
        checks["python_syntax"] = run([sys.executable, "-W", "error", "-m", "py_compile", *map(str, sorted(package.rglob("*.py")))]).returncode == 0
        with zipfile.ZipFile(SOURCE_ZIP) as source_archive:
            prefix = SOURCE + "/"
            frozen = sorted(name[len(prefix):] for name in source_archive.namelist() if name.startswith(prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/"))
            checks["frozen_87_payload"] = len(frozen) == 87 and all((package / name).read_bytes() == source_archive.read(prefix + name) for name in frozen)
            checks["sca_normalized_equal"] = all((package / name).read_text(encoding="utf-8").replace(PACKAGE, SOURCE) == source_archive.read(prefix + name).decode() for name in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json"))
        family_parser = package / "package_tools/arm_known_parser.py"
        contract_path = package / "diagnostics/arm_known_contract.json"
        expected = {"stable": "TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT", "progress": "TARGET_ARM_ROW2_DISTINCT_TOKEN_STATE_PROGRESS", "reset": "TARGET_ARM_ROW2_RESET_OR_WRAP", "single": "TARGET_ARM_ROW2_SINGLE_ACCEPT_ONLY"}
        for mode, decision in expected.items():
            cases[mode] = p34.target_case(family_parser, contract_path, root, f"positive_{mode}", mode, noise_bytes=(17 * 1024 * 1024 if mode == "stable" else 0))
        checks["four_live_token_positive_controls"] = all(cases[mode]["exit_code"] == 0 and cases[mode]["decision"]["decision"] == decision for mode, decision in expected.items())
        checks["overbudget_multi_instance_parser"] = cases["stable"]["log_bytes"] > 16 * 1024 * 1024
        for name, kwargs in {"missing_enable": {"missing_enable": True}, "wrong_instance": {"wrong_instance": True}, "mismatched_time": {"mismatched_time": True}}.items():
            cases[name] = p34.target_case(family_parser, contract_path, root, f"negative_{name}", "stable", **kwargs)
        checks["three_target_time_negatives_fail_closed"] = all(cases[name]["exit_code"] != 0 and cases[name]["decision"]["decision"] == "EVIDENCE_INCOMPLETE" for name in ("missing_enable", "wrong_instance", "mismatched_time"))
        live_fixture = (package / "diagnostics/live_fixtures/arm_known_event.log").read_text(encoding="utf-8")
        cases["live_only_fixture"] = parser_case(family_parser, contract_path, live_fixture, root, "live_only_fixture")
        checks["tiny_live_only_fixture"] = cases["live_only_fixture"]["exit_code"] == 0 and "kind=EVENT" in live_fixture and "RING_POST" not in live_fixture
        unknown_lines = []
        mutated = False
        for line in live_fixture.splitlines():
            if not mutated and "kind=EVENT" in line and "boundary=arm_row2_accept_token_state" in line:
                tokens = line.split()
                tokens = [token[:-1] + "Z" if token.startswith("payload=") else token for token in tokens]
                line = " ".join(tokens)
                mutated = True
            unknown_lines.append(line)
        cases["unknown_payload"] = parser_case(family_parser, contract_path, "\n".join(unknown_lines) + "\n", root, "unknown_payload")
        checks["unknown_payload_fail_closed"] = cases["unknown_payload"]["exit_code"] != 0 and cases["unknown_payload"]["decision"]["decision"] == "EVIDENCE_INCOMPLETE" and cases["unknown_payload"]["decision"]["unknown_payload_rows"]
        final_only = "\n".join(line.replace("kind=EVENT", "kind=RING_POST") if "kind=EVENT" in line else line for line in live_fixture.splitlines()) + "\n"
        cases["final_ring_only"] = parser_case(family_parser, contract_path, final_only, root, "final_ring_only")
        checks["final_only_ring_sole_input_negative"] = cases["final_ring_only"]["exit_code"] != 0 and cases["final_ring_only"]["decision"]["decision"] == "EVIDENCE_INCOMPLETE"
        observer = (package / "tb_probe/source_bound_causal_observer.svh").read_text(encoding="utf-8")
        checks["undriven_leaf_excluded"] = "add_array_req_addr" not in observer and "wire [45:0] payload_now" in observer
        request = json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))
        core_contract = json.loads((package / "contracts/server_post_sim_return_contract.json").read_text(encoding="utf-8"))
        required = [row for row in request["plugins"] if row.get("required_for_adjudication")]
        dispositions = core_contract.get("partial_exit_live_causal_record", {}).get("plugin_dispositions", [])
        checks["required_plugin_exact_disposition"] = [row["plugin_id"] for row in required] == ["arm_known_parser"] and [row["plugin_id"] for row in dispositions] == ["arm_known_parser"] and dispositions[0].get("disposition") == "LIVE_CAUSAL_FIXTURE"
        checks["current_post_sim_helper_bound"] = sha(package / "package_tools/server_post_sim_return.py") == HELPER_SHA and core_contract.get("helper_sha256") == HELPER_SHA
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        checks["target_parser_source_contract_bound"] = contract.get("target_parser_source_sha256") == sha(ROOT / "tools/conv_native_four_lane_p35_arm_known_parser.py") and sha(family_parser) == contract.get("target_parser_source_sha256")
    errors = [name for name, passed in checks.items() if not passed]
    report = {
        "schema": "conv-native-four-lane-p35c-armknown-family-audit-v1",
        "valid": not errors, "pass": not errors, "errors": errors, "checks": checks, "case_results": cases,
        "positive_control_count": 5, "negative_control_count": 5, "pairwise_distinguishable": checks.get("four_live_token_positive_controls", False),
        "zip": {"path": zip_path.relative_to(ROOT).as_posix(), "bytes": zip_path.stat().st_size, "sha256": sha(zip_path)},
        "claim_boundary": "Static/package-local binary-known live target audit only; no production natural terminal, formal D or E3-E5 claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
